"""chain2-gate (stage 6) — Chain 2 promotion candidate selector.

Hybrid design:
  - Deterministic scorer (the 7-step flow in scoring_flow.md) produces the
    numeric score 0-1 per candidate. LLM cannot override this.
  - Optional LLM narrative layer fills `rationale_kr` and
    `expected_chain2_concerns` fields — pure colour, no score influence.

Runs per iteration (orchestrator auto-call) or over an arbitrary set of
iterations (CLI: `python -m chain1.agents.chain2_gate --iterations 0 1 2`).
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
AGENT_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "chain2-gate"

for p in (str(REPO_ROOT), str(SHARED_DIR), str(AGENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import (  # noqa: E402
    SignalSpec, BacktestResult, Feedback,
    Chain2Candidate, Chain2Priority, Chain2ScenarioResult, Chain2GateOutput,
)
from chain1.llm_client import LLMClient  # noqa: E402


def _load_io_schemas():
    in_path = AGENT_DIR / "input_schema.py"
    out_path = AGENT_DIR / "output_schema.py"
    spec_in = importlib.util.spec_from_file_location("c2g_in", in_path)
    spec_out = importlib.util.spec_from_file_location("c2g_out", out_path)
    mi = importlib.util.module_from_spec(spec_in); spec_in.loader.exec_module(mi)
    mo = importlib.util.module_from_spec(spec_out); spec_out.loader.exec_module(mo)
    for cls_name, mod in (("GateTriple", mi), ("GateInput", mi), ("GateOutput", mo)):
        try:
            getattr(mod, cls_name).model_rebuild(_types_namespace={**mi.__dict__, **mo.__dict__})
        except Exception:  # noqa: BLE001
            pass
    return mi.GateInput, mi.GateTriple, mo.GateOutput


GateInput, GateTriple, GateOutput = _load_io_schemas()


# ---------------------------------------------------------------------------
# Fee scenarios (must match fee_scenarios.md)
# ---------------------------------------------------------------------------

FEE_SCENARIOS: dict[str, dict[str, float]] = {
    # Market = KRX. We measure signal on KRX data, so only KRX fee tables apply.
    # Cross-market comparison (crypto) requires re-measuring signal on crypto
    # data — not done here. Do NOT add crypto_* scenarios without first running
    # Chain 1 on crypto LOB data (see data/binance_lob/).
    "krx_cash_23bps": {
        "rt_bps": 23.0,
        "maker_bps": 1.5, "taker_bps": 1.5, "sell_tax_bps": 20.0,
    },
    # Research-only hypothetical low-fee scenario (e.g., if KRX introduces maker
    # rebate or if we hypothesize a cheaper venue). NOT a deployable scenario.
    "hypothetical_low_fee_5bps": {
        "rt_bps": 5.0,
        "maker_bps": 2.5, "taker_bps": 2.5, "sell_tax_bps": 0.0,
    },
}


# ---------------------------------------------------------------------------
# Scoring constants (must match scoring_flow.md)
# ---------------------------------------------------------------------------

GATE_MIN_DENSITY = 300.0
GATE_MIN_WR = 0.55

WEIGHTS = {"edge": 0.35, "density": 0.20, "filter": 0.15, "simple": 0.15, "multi": 0.15}

EDGE_MIN_BPS, EDGE_CAP_BPS = 0.0, 10.0
DENSITY_MIN_LOG, DENSITY_CAP_LOG = math.log10(GATE_MIN_DENSITY), math.log10(10000.0)
COMPLEXITY_MAX = 6
COMPLEXITY_MIN = 1

PRIORITY_MUST = 0.75
PRIORITY_STRONG = 0.55

STATEFUL_HELPERS = {"zscore", "rolling_mean", "rolling_std"}
REGIME_FILTER_PRIMITIVES = {"spread_bps", "acml_vol"}   # presence indicates self-filter


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# Derived metrics per spec
# ---------------------------------------------------------------------------


def _derived_metrics(
    spec: SignalSpec, result: BacktestResult, n_symbols: int, n_dates: int
) -> dict[str, Any]:
    denom = max(1, n_symbols * n_dates)
    trade_density = result.aggregate_n_trades / denom

    formula = spec.formula or ""
    formula_norm = formula.lower()
    uses_stateful = any(h in formula_norm for h in STATEFUL_HELPERS)
    uses_compound = any(op in formula_norm for op in (" and ", " or ", " AND ", " OR "))
    complexity = len(spec.primitives_used) + (1 if uses_stateful else 0) + (1 if uses_compound else 0)

    regime_filter = any(p in formula_norm for p in REGIME_FILTER_PRIMITIVES)

    return {
        "wr": result.aggregate_wr,
        "expectancy_bps": result.aggregate_expectancy_bps,
        "trade_density_per_day_per_sym": trade_density,
        "complexity_score": float(complexity),
        "has_regime_self_filter": regime_filter,
        "n_trades": result.aggregate_n_trades,
    }


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------


def _apply_gates(
    spec: SignalSpec, result: BacktestResult, feedback: Feedback, m: dict[str, Any],
    fee_rt_bps: float,
) -> str | None:
    """Return None if pass, else a string describing the gate failure."""
    if m["trade_density_per_day_per_sym"] < GATE_MIN_DENSITY:
        return f"gate_failed:G1_density:{m['trade_density_per_day_per_sym']:.1f}<{GATE_MIN_DENSITY}"
    if m["wr"] < GATE_MIN_WR:
        return f"gate_failed:G2_wr:{m['wr']:.4f}<{GATE_MIN_WR}"
    exp_post = m["expectancy_bps"] - fee_rt_bps
    if exp_post <= 0:
        return f"gate_failed:G3_exp_post_fee:{exp_post:.3f}<=0"
    cross = feedback.cross_symbol_consistency
    if cross == "inconsistent":
        return "gate_failed:G4_cross_inconsistent"
    return None


# ---------------------------------------------------------------------------
# Dominance
# ---------------------------------------------------------------------------


def _is_extension(a_formula: str, b_formula: str) -> bool:
    """Rough 'A extends B' detector. True if b is a substring of a (normalized)
    OR if a has every conjunct b has (AND extension)."""
    af = a_formula.strip()
    bf = b_formula.strip()
    if bf in af:
        return True
    # Split by AND (case-normalized)
    a_parts = set(p.strip().lower() for p in re.split(r"\bAND\b", af, flags=re.IGNORECASE))
    b_parts = set(p.strip().lower() for p in re.split(r"\bAND\b", bf, flags=re.IGNORECASE))
    return b_parts.issubset(a_parts) and a_parts != b_parts


def _check_dominance(
    a_spec: SignalSpec, a_res: BacktestResult, a_m: dict,
    b_spec: SignalSpec, b_res: BacktestResult, b_m: dict,
) -> bool:
    """True if a dominates b."""
    if not set(b_spec.primitives_used).issubset(set(a_spec.primitives_used)):
        return False
    if not _is_extension(a_spec.formula, b_spec.formula):
        return False
    if a_spec.direction != b_spec.direction:
        return False
    if a_spec.prediction_horizon_ticks != b_spec.prediction_horizon_ticks:
        return False
    if a_res.aggregate_expectancy_bps < b_res.aggregate_expectancy_bps - 1e-9:
        return False
    if a_m["trade_density_per_day_per_sym"] < 0.5 * b_m["trade_density_per_day_per_sym"]:
        return False
    return True


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------


def _multi_day_bonus(n_dates: int) -> float:
    if n_dates >= 3:
        return 1.0
    if n_dates == 2:
        return 0.5
    return 0.2


def _composite_score(m: dict[str, Any], fee_rt_bps: float, n_dates: int) -> tuple[float, dict[str, float]]:
    exp_post = m["expectancy_bps"] - fee_rt_bps
    s_edge = _clamp01((exp_post - EDGE_MIN_BPS) / max(1e-9, EDGE_CAP_BPS - EDGE_MIN_BPS))

    td = m["trade_density_per_day_per_sym"]
    log_td = math.log10(max(td, 1.0))
    s_density = _clamp01((log_td - DENSITY_MIN_LOG) / max(1e-9, DENSITY_CAP_LOG - DENSITY_MIN_LOG))

    s_filter = 1.0 if m["has_regime_self_filter"] else 0.0

    cscore = m["complexity_score"]
    s_simple = _clamp01((COMPLEXITY_MAX - cscore) / max(1e-9, COMPLEXITY_MAX - COMPLEXITY_MIN))

    s_multi = _multi_day_bonus(n_dates)

    composite = (
        WEIGHTS["edge"]     * s_edge
        + WEIGHTS["density"]* s_density
        + WEIGHTS["filter"] * s_filter
        + WEIGHTS["simple"] * s_simple
        + WEIGHTS["multi"]  * s_multi
    )
    breakdown = {
        "edge_w":     WEIGHTS["edge"]     * s_edge,
        "density_w":  WEIGHTS["density"]  * s_density,
        "filter_w":   WEIGHTS["filter"]   * s_filter,
        "simple_w":   WEIGHTS["simple"]   * s_simple,
        "multi_w":    WEIGHTS["multi"]    * s_multi,
        "raw_edge":       s_edge,
        "raw_density":    s_density,
        "raw_filter":     s_filter,
        "raw_simple":     s_simple,
        "raw_multi":      s_multi,
    }
    return _clamp01(composite), breakdown


def _priority(score: float) -> Chain2Priority:
    if score >= PRIORITY_MUST:
        return Chain2Priority.MUST_INCLUDE
    if score >= PRIORITY_STRONG:
        return Chain2Priority.STRONG
    return Chain2Priority.MARGINAL


# ---------------------------------------------------------------------------
# LLM rationale layer (optional, hybrid)
# ---------------------------------------------------------------------------


def _synthesize_rationale_kr(
    cand: Chain2Candidate, spec: SignalSpec, feedback: Feedback, fee_scenario: str
) -> str:
    """Deterministic one-liner rationale as default fallback."""
    fb = cand.factor_breakdown
    top_factor = max(
        [("edge", fb.get("edge_w", 0)), ("density", fb.get("density_w", 0)),
         ("filter", fb.get("filter_w", 0)), ("simple", fb.get("simple_w", 0)),
         ("multi", fb.get("multi_w", 0))],
        key=lambda x: x[1],
    )
    factor_kr = {
        "edge": "fee 후 기대수익이 양수로 확보됨",
        "density": f"거래 빈도 {cand.trade_density_per_day_per_sym:.0f}/day/심볼 로 통계적 안정성 확보",
        "filter": "공식에 spread/volume regime filter 내장 → Chain 2 fee 회피 유리",
        "simple": "단순 공식 → Chain 2 execution 설계·디버그 용이",
        "multi": "multi-day 재현성 확보",
    }
    return (
        f"시나리오 `{fee_scenario}` 하에서 score **{cand.score:.3f}** "
        f"({cand.priority.value}). 주요 기여 factor: **{top_factor[0]}** "
        f"({top_factor[1]:.3f}) — {factor_kr[top_factor[0]]}. "
        f"WR {cand.wr:.3f}, post-fee expectancy {cand.expectancy_post_fee_bps:+.3f} bps."
    )


def _default_concerns(cand: Chain2Candidate, spec: SignalSpec) -> list[str]:
    out: list[str] = []
    if cand.expectancy_post_fee_bps < 2.0:
        out.append(f"post-fee edge 얇음 ({cand.expectancy_post_fee_bps:+.2f} bps) — Chain 2 adverse selection 에 민감")
    if cand.complexity_score >= 4:
        out.append(f"complexity={cand.complexity_score:.0f} — execution 튜닝 공간 복잡")
    if not cand.has_regime_self_filter:
        out.append("regime filter 부재 — high-spread 구간에서 fee 손실 누적 가능")
    if cand.trade_density_per_day_per_sym < 500:
        out.append(f"density {cand.trade_density_per_day_per_sym:.0f}/day — Chain 2 에서 sample size 부족 위험")
    return out[:3]


def _llm_narrative_layer(
    candidates_by_scenario: dict[str, list[Chain2Candidate]],
    specs_by_id: dict[str, SignalSpec],
    feedbacks_by_id: dict[str, Feedback],
    client: LLMClient | None,
) -> str | None:
    """If LLM available, generate a meta_narrative_kr. Otherwise return a deterministic one."""
    # Deterministic fallback
    scenario_lines = []
    for sc, cands in candidates_by_scenario.items():
        if not cands:
            scenario_lines.append(f"- **{sc}**: 통과 후보 없음")
            continue
        top = cands[0]
        scenario_lines.append(
            f"- **{sc}**: 최상위 `{top.spec_id}` score={top.score:.3f} "
            f"(priority={top.priority.value}, post-fee exp {top.expectancy_post_fee_bps:+.2f} bps)"
        )
    return "**시나리오별 요약**\n" + "\n".join(scenario_lines)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def run_gate(
    triples: list[dict | Any],
    iterations_scanned: list[int],
    fee_scenarios: list[str],
    n_symbols: int,
    n_dates: int,
    top_k: int = 3,
    use_llm_narrative: bool = False,
    client: LLMClient | None = None,
) -> Chain2GateOutput:
    """Core deterministic entry. Accepts dicts or GateTriple objects."""

    # Normalize inputs
    normalized: list[GateTriple] = []
    for t in triples:
        if isinstance(t, GateTriple):
            normalized.append(t)
        else:
            normalized.append(GateTriple(**t))

    specs_by_id = {t.spec.spec_id: t.spec for t in normalized}
    results_by_id = {t.result.spec_id: t.result for t in normalized}
    feedbacks_by_id = {t.feedback.spec_id: t.feedback for t in normalized}
    metrics_by_id: dict[str, dict[str, Any]] = {}
    for t in normalized:
        metrics_by_id[t.spec.spec_id] = _derived_metrics(t.spec, t.result, n_symbols, n_dates)

    scenario_results: list[Chain2ScenarioResult] = []
    candidates_per_scenario: dict[str, list[Chain2Candidate]] = {}

    for fs in fee_scenarios:
        if fs not in FEE_SCENARIOS:
            raise ValueError(f"unknown fee_scenario: {fs!r}")
        rt_bps = FEE_SCENARIOS[fs]["rt_bps"]
        excluded: dict[str, str] = {}

        # Apply gates
        survivors: list[str] = []
        for t in normalized:
            m = metrics_by_id[t.spec.spec_id]
            failure = _apply_gates(t.spec, t.result, t.feedback, m, rt_bps)
            if failure is not None:
                excluded[t.spec.spec_id] = failure
            else:
                survivors.append(t.spec.spec_id)

        # Dominance (pairwise)
        still_alive: list[str] = list(survivors)
        for i, a_id in enumerate(survivors):
            for j, b_id in enumerate(survivors):
                if i == j:
                    continue
                if a_id not in still_alive or b_id not in still_alive:
                    continue
                a_spec = specs_by_id[a_id]; a_res = results_by_id[a_id]; a_m = metrics_by_id[a_id]
                b_spec = specs_by_id[b_id]; b_res = results_by_id[b_id]; b_m = metrics_by_id[b_id]
                if _check_dominance(a_spec, a_res, a_m, b_spec, b_res, b_m):
                    excluded[b_id] = f"dominated_by:{a_id}"
                    if b_id in still_alive:
                        still_alive.remove(b_id)

        # Score survivors
        cands: list[Chain2Candidate] = []
        for sid in still_alive:
            m = metrics_by_id[sid]
            score, breakdown = _composite_score(m, rt_bps, n_dates)
            cand = Chain2Candidate(
                spec_id=sid,
                score=score,
                priority=_priority(score),
                wr=m["wr"],
                expectancy_bps=m["expectancy_bps"],
                expectancy_post_fee_bps=m["expectancy_bps"] - rt_bps,
                fee_absorption_ratio=m["expectancy_bps"] / max(rt_bps / 2, 1e-9),
                trade_density_per_day_per_sym=m["trade_density_per_day_per_sym"],
                complexity_score=m["complexity_score"],
                has_regime_self_filter=m["has_regime_self_filter"],
                factor_breakdown=breakdown,
            )
            # Default concerns + rationale (deterministic fallback)
            cand.expected_chain2_concerns = _default_concerns(cand, specs_by_id[sid])
            cand.rationale_kr = _synthesize_rationale_kr(cand, specs_by_id[sid], feedbacks_by_id[sid], fs)
            cands.append(cand)

        cands.sort(key=lambda c: c.score, reverse=True)
        top = cands[:top_k]

        scenario_results.append(Chain2ScenarioResult(
            fee_scenario=fs, fee_rt_bps=rt_bps,
            top_candidates=top, excluded=excluded,
        ))
        candidates_per_scenario[fs] = top

    # Cross-scenario consensus
    sets_by_scen = [set(c.spec_id for c in v) for v in candidates_per_scenario.values()]
    consensus = sorted(set.intersection(*sets_by_scen)) if sets_by_scen else []

    # Warnings
    warnings: list[str] = []
    if n_dates < 2:
        warnings.append("single-day measurement — multi-day replication required before true promotion")
    if n_symbols < 2:
        warnings.append("limited symbol universe — cross-symbol robustness unverified")
    for sr in scenario_results:
        if not sr.top_candidates:
            warnings.append(f"no candidates passed gates under {sr.fee_scenario}")

    # Meta narrative (LLM optional but deterministic fallback always populates)
    meta_narrative = _llm_narrative_layer(
        candidates_per_scenario, specs_by_id, feedbacks_by_id,
        client if use_llm_narrative else None,
    )

    return Chain2GateOutput(
        agent_name="chain2-gate",
        iteration_idx=max(iterations_scanned),
        iterations_scanned=iterations_scanned,
        total_valid_specs=len(normalized),
        scenarios=scenario_results,
        cross_scenario_consensus=consensus,
        warnings=warnings,
        meta_narrative_kr=meta_narrative,
    )


# ---------------------------------------------------------------------------
# Convenience: load from iterations dir
# ---------------------------------------------------------------------------


def load_triples_from_iterations(iteration_indices: list[int]) -> list[dict]:
    """Scan iterations/iter_<NNN>/{specs,results,feedback}/ and build triples."""
    triples: list[dict] = []
    for idx in iteration_indices:
        idir = REPO_ROOT / "iterations" / f"iter_{idx:03d}"
        specs_dir = idir / "specs"
        results_dir = idir / "results"
        feedback_dir = idir / "feedback"
        if not specs_dir.exists():
            continue
        for spec_path in sorted(specs_dir.glob("*.json")):
            sid = spec_path.stem
            result_path = results_dir / f"{sid}.json"
            feedback_path = feedback_dir / f"{sid}.json"
            if not (result_path.exists() and feedback_path.exists()):
                continue
            triples.append({
                "spec": json.loads(spec_path.read_text()),
                "result": json.loads(result_path.read_text()),
                "feedback": json.loads(feedback_path.read_text()),
            })
    return triples


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, nargs="+", required=True,
                    help="Iteration indices to include")
    ap.add_argument("--fee-scenarios", nargs="+",
                    default=[os.getenv("CHAIN2_GATE_FEE_SCENARIO", "krx_cash_23bps"),
                             "hypothetical_low_fee_5bps"],
                    help="Fee scenario IDs (see fee_scenarios.md)")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--n-symbols", type=int, default=None,
                    help="Symbols count in backtests. Auto-detect from results if omitted.")
    ap.add_argument("--n-dates", type=int, default=None,
                    help="Dates count. Auto-detect if omitted.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--use-llm", action="store_true")
    args = ap.parse_args()

    # Deduplicate scenarios and drop invalids
    fee_scen = []
    for s in args.fee_scenarios:
        if s in FEE_SCENARIOS and s not in fee_scen:
            fee_scen.append(s)
    if not fee_scen:
        fee_scen = ["krx_cash_23bps"]

    triples = load_triples_from_iterations(args.iterations)
    if not triples:
        print(f"[chain2-gate] no valid triples found for iterations {args.iterations}")
        raise SystemExit(1)

    # Auto-detect n_symbols / n_dates from results
    auto_symbols = set()
    auto_dates = set()
    for t in triples:
        for ps in t["result"].get("per_symbol", []):
            auto_symbols.add(ps.get("symbol"))
            auto_dates.add(ps.get("date"))
    n_symbols = args.n_symbols or max(1, len(auto_symbols))
    n_dates = args.n_dates or max(1, len(auto_dates))

    output = run_gate(
        triples=triples,
        iterations_scanned=args.iterations,
        fee_scenarios=fee_scen,
        n_symbols=n_symbols,
        n_dates=n_dates,
        top_k=args.top_k,
        use_llm_narrative=args.use_llm,
    )

    out_json = output.model_dump_json(indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out_json)
        print(f"[chain2-gate] saved → {args.out}")
    else:
        print(out_json)
