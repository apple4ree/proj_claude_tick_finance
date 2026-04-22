"""feedback-analyst hybrid wrapper (stage ④).

Implements `analysis_framework.md`'s mandatory decision tree as pure Python
first (reproducible, no prompt drift), then delegates the narrative parts
(strengths/weaknesses articulation, win/loss bucket insight prose) to the LLM.

If `--skip-llm` is requested, returns a Feedback assembled entirely from the
deterministic decision tree — `recommended_next_direction` and
`cross_symbol_consistency` are always deterministic; only the prose slots
receive placeholder summaries.
"""
from __future__ import annotations

import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
AGENT_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "feedback-analyst"

for p in (str(REPO_ROOT), str(SHARED_DIR), str(AGENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import SignalSpec, BacktestResult, Feedback  # noqa: E402
from chain1.llm_client import LLMClient  # noqa: E402


def _load_io_schemas():
    in_path = AGENT_DIR / "input_schema.py"
    out_path = AGENT_DIR / "output_schema.py"
    spec_in = importlib.util.spec_from_file_location("fa_in", in_path)
    spec_out = importlib.util.spec_from_file_location("fa_out", out_path)
    mi = importlib.util.module_from_spec(spec_in); spec_in.loader.exec_module(mi)
    mo = importlib.util.module_from_spec(spec_out); spec_out.loader.exec_module(mo)
    for cls_name, mod in (("FeedbackInput", mi), ("FeedbackOutput", mo)):
        try:
            getattr(mod, cls_name).model_rebuild(_types_namespace={**mi.__dict__, **mo.__dict__})
        except Exception:  # noqa: BLE001
            pass
    return mi.FeedbackInput, mo.FeedbackOutput


FeedbackInput, FeedbackOutput = _load_io_schemas()


# ---------------------------------------------------------------------------
# Deterministic decision tree (analysis_framework.md §Decision tree)
# ---------------------------------------------------------------------------


def _cross_symbol_consistency(result: BacktestResult) -> str:
    """std(per_symbol.wr) thresholds from analysis_framework.md §(b)."""
    if len(result.per_symbol) < 2:
        return "not_applicable"
    wrs = [ps.wr for ps in result.per_symbol]
    if any(math.isnan(w) for w in wrs):
        return "not_applicable"
    # sign-flip detection — if some symbols have wr < 0.5 and others > 0.5
    signs = {"high": sum(1 for w in wrs if w > 0.5), "low": sum(1 for w in wrs if w < 0.5)}
    if signs["high"] > 0 and signs["low"] > 0:
        sigma_pct = statistics.pstdev([w * 100 for w in wrs])
        if sigma_pct > 10:
            return "inconsistent"
    sigma_pct = statistics.pstdev([w * 100 for w in wrs])
    if sigma_pct < 2:
        return "consistent"
    if sigma_pct <= 10:
        return "mixed"
    return "inconsistent"


def _primary_recommendation(
    spec: SignalSpec,
    result: BacktestResult,
    cross_sym: str,
) -> tuple[str, str]:
    """Return (recommended_next_direction, reasoning_sentence).

    Implements analysis_framework.md §Decision tree verbatim.
    """
    n = result.aggregate_n_trades
    wr = result.aggregate_wr
    exp = result.aggregate_expectancy_bps

    if n < 30:
        return "loosen_threshold", (
            f"Under-powered: only {n} trades (< 30). Need more fills to measure WR reliably — "
            f"lower threshold to widen entry."
        )
    if 0.48 <= wr <= 0.52 and n >= 300:
        return "swap_feature", (
            f"WR={wr:.3f} over {n} trades is indistinguishable from random walk (0.48–0.52 band). "
            f"Current primitive family exhausted — swap feature."
        )
    if cross_sym == "inconsistent":
        return "drop_feature", (
            "Cross-symbol results are inconsistent (wr std > 10% or sign-flip across symbols). "
            "Feature behaves differently per symbol; drop it or restrict universe."
        )
    if wr >= 0.55 and n >= 100 and exp > 0:
        # NOTE: 2026-04-21 empirical horizon sweep showed expectancy PEAKS at
        # h=20 and DECLINES for h=50, 100, 200 on this signal family. Predictive
        # horizon ~ 2s. Aggressive horizon push REMOVED — use cycle default.
        # Diversity guard: if WR is already very high AND the spec has already
        # been threshold-tightened (heuristic: parent exists or threshold is well
        # above typical defaults), rotate to a different search axis instead of
        # endless tightening. Avoids the "WR → 1, n_trades → 0" death spiral.
        already_tight = (
            spec.parent_spec_id is not None
            or (set(spec.primitives_used) <= {"obi_1", "obi_3", "obi_5", "obi_10", "obi_total",
                                              "ofi_proxy"}
                and spec.threshold >= 0.5)
            or (("microprice_dev_bps" in spec.primitives_used) and spec.threshold >= 1.5)
        )
        if wr >= 0.93 and already_tight:
            # Deterministic rotation across alternative axes using spec_id hash.
            # Block B adds 4 new directions so rotation space is wider → more
            # diverse exploration across lineage.
            alt_options = [
                ("change_horizon", "already-tight + very high WR → change_horizon to probe a different prediction regime"),
                ("add_filter",     "already-tight + very high WR → add a filter (spread/volatility) rather than keep tightening"),
                ("combine_with_other_spec", "already-tight + very high WR → combine with a complementary spec from this batch"),
                ("add_regime_filter", "already-tight + very high WR → add a regime filter (realized_vol / time_of_day) to concentrate entries where expected move is larger"),
                ("ensemble_vote",  "already-tight + very high WR → require majority vote across 3 thresholded primitives for robustness"),
                ("extreme_quantile", "already-tight + very high WR → use zscore(primary,300)>2.5 to push to p99 selectivity"),
                ("timevarying_threshold", "already-tight + very high WR → adaptive threshold (N×rolling_std) handles regime shifts"),
            ]
            idx = hash(spec.spec_id) % len(alt_options)
            direction, reason = alt_options[idx]
            return direction, (
                f"WR={wr:.3f} on {n} trades with already-tight settings "
                f"(threshold={spec.threshold}); {reason}."
            )
        return "tighten_threshold", (
            f"Candidate edge: WR={wr:.3f} ({n} trades), expectancy={exp:+.3f}bps. "
            f"Tighten threshold to confirm — higher-conviction subset should keep WR."
        )
    if wr >= 0.60:
        return "add_filter", (
            f"High WR={wr:.3f} with only {n} trades — add a filter (spread/volatility) "
            f"to narrow to the highest-confidence tick set."
        )
    return "change_horizon", (
        f"Ambiguous: WR={wr:.3f} n={n} exp={exp:+.3f}bps does not fit a clean rule. "
        f"Change horizon (1→5→20 ticks) to probe a different prediction regime."
    )


def _headline_strengths_weaknesses(
    spec: SignalSpec,
    result: BacktestResult,
    cross_sym: str,
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []

    wr = result.aggregate_wr
    exp = result.aggregate_expectancy_bps
    n = result.aggregate_n_trades

    if wr > 0.55 and n >= 100:
        strengths.append(f"Sustained WR={wr:.3f} over {n} trades (above 55% threshold)")
    if exp > 0 and n >= 30:
        strengths.append(f"Expectancy={exp:+.3f}bps per trade is positive")
    if cross_sym == "consistent":
        strengths.append("Cross-symbol consistency: per-symbol WRs agree within 2 percentage points")

    if n < 30:
        weaknesses.append(f"Only {n} trades — statistically underpowered for any WR claim")
    if 0.48 <= wr <= 0.52:
        weaknesses.append(f"WR={wr:.3f} within noise band (0.48–0.52)")
    if exp <= 0 and n >= 30:
        weaknesses.append(f"Non-positive expectancy ({exp:+.3f} bps/trade) despite {n} trades")
    if cross_sym == "inconsistent":
        wrs_str = ", ".join(f"{ps.symbol}:{ps.wr:.2f}" for ps in result.per_symbol)
        weaknesses.append(f"Cross-symbol inconsistency: {wrs_str}")
    if cross_sym == "mixed":
        weaknesses.append("Per-symbol WR spreads 2–10 percentage points — symbol dependence likely")

    if not weaknesses:
        weaknesses.append("no material weaknesses flagged by deterministic analysis")
    return strengths, weaknesses


def _build_deterministic_feedback(
    spec: SignalSpec,
    result: BacktestResult,
    iteration_idx: int,
) -> Feedback:
    cross_sym = _cross_symbol_consistency(result)
    recommendation, reason = _primary_recommendation(spec, result, cross_sym)
    strengths, weaknesses = _headline_strengths_weaknesses(spec, result, cross_sym)

    return Feedback(
        agent_name="feedback-analyst",
        iteration_idx=iteration_idx,
        spec_id=spec.spec_id,
        strengths=strengths,
        weaknesses=weaknesses,
        win_bucket_insight="trace not available (deterministic-only mode)",
        loss_bucket_insight="trace not available (deterministic-only mode)",
        cross_symbol_consistency=cross_sym,
        recommended_next_direction=recommendation,
        recommended_direction_reasoning=reason,
    )


# ---------------------------------------------------------------------------
# LLM soft augmentation
# ---------------------------------------------------------------------------


def _build_user_message(
    spec: SignalSpec,
    result: BacktestResult,
    iteration_idx: int,
    recent_feedback: list[Feedback] | None,
    det_feedback: Feedback,
) -> str:
    recent_block = "none"
    if recent_feedback:
        recent_block = json.dumps(
            [fb.model_dump() if hasattr(fb, "model_dump") else fb for fb in recent_feedback[-5:]],
            indent=2, default=str,
        )

    return (
        f"Iteration: {iteration_idx}\n"
        f"SignalSpec:\n{spec.model_dump_json(indent=2)}\n\n"
        f"BacktestResult:\n{result.model_dump_json(indent=2)}\n\n"
        f"Recent feedback history (for trend detection):\n{recent_block}\n\n"
        f"Deterministic pre-analysis (PRESERVE cross_symbol_consistency and recommended_next_direction "
        f"verbatim in your output — those are fixed):\n{det_feedback.model_dump_json(indent=2)}\n\n"
        f"Your job: enrich the Feedback narrative:\n"
        f"  - strengths / weaknesses: you may add or refine bullets (cite specific numbers)\n"
        f"  - win_bucket_insight / loss_bucket_insight: if backtest has trace, characterise the winning "
        f"    vs losing tick buckets. Otherwise keep as 'trace not available' — do NOT fabricate.\n"
        f"  - recommended_direction_reasoning: expand the one-liner into a ≥ 20-char evidence-cited "
        f"    explanation, but do NOT change the recommendation itself.\n"
        f"  - Keep spec_id, iteration_idx, agent_name, cross_symbol_consistency, "
        f"    recommended_next_direction identical to the deterministic pre-analysis.\n"
    )


def analyze_feedback(
    spec: SignalSpec,
    result: BacktestResult,
    iteration_idx: int,
    recent_feedback: list[Feedback] | None = None,
    client: LLMClient | None = None,
    model_override: str | None = None,
    skip_llm: bool = False,
) -> Feedback:
    """Hybrid feedback analysis: deterministic decision + optional LLM narrative."""
    det_fb = _build_deterministic_feedback(spec, result, iteration_idx)
    if skip_llm:
        return det_fb

    client = client or LLMClient()
    user_msg = _build_user_message(spec, result, iteration_idx, recent_feedback, det_fb)
    response: Any = client.call_agent(
        agent_name="feedback-analyst",
        user_message=user_msg,
        response_model=FeedbackOutput,
        model_override=model_override,
    )

    fb = response.feedback
    # Enforce deterministic fields (protect against LLM drift)
    merged = fb.model_dump()
    merged["iteration_idx"] = iteration_idx
    merged["spec_id"] = spec.spec_id
    merged["agent_name"] = "feedback-analyst"
    merged["cross_symbol_consistency"] = det_fb.cross_symbol_consistency
    merged["recommended_next_direction"] = det_fb.recommended_next_direction
    return Feedback(**merged)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True)
    ap.add_argument("--result-json", required=True)
    ap.add_argument("--iteration-idx", type=int, default=0)
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    spec = SignalSpec(**json.loads(Path(args.spec_json).read_text()))
    result = BacktestResult(**json.loads(Path(args.result_json).read_text()))

    fb = analyze_feedback(
        spec, result, args.iteration_idx,
        skip_llm=args.skip_llm,
        model_override=args.model,
    )
    print(fb.model_dump_json(indent=2))
