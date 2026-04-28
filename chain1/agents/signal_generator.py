"""signal-generator LLM wrapper (stage ①).

Takes `GenerateInput` → calls LLM with AGENTS.md prompts → validates/normalises
the returned `GenerateOutput` → returns list[SignalSpec].

The LLM's job is to propose hypotheses + formulas; this wrapper ensures the
result conforms to the project's conventions (spec_id format, iteration_idx,
measured_* fields None, references non-empty) before handoff to signal-evaluator.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
AGENT_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "signal-generator"

for p in (str(REPO_ROOT), str(SHARED_DIR), str(AGENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import SignalSpec  # noqa: E402
from chain1.llm_client import LLMClient  # noqa: E402
import importlib.util  # noqa: E402


def _load_io_schemas():
    """Dynamically import signal-generator's GenerateInput and GenerateOutput."""
    in_path = AGENT_DIR / "input_schema.py"
    out_path = AGENT_DIR / "output_schema.py"
    spec_in = importlib.util.spec_from_file_location("siggen_in", in_path)
    spec_out = importlib.util.spec_from_file_location("siggen_out", out_path)
    mi = importlib.util.module_from_spec(spec_in); spec_in.loader.exec_module(mi)
    mo = importlib.util.module_from_spec(spec_out); spec_out.loader.exec_module(mo)
    # Pydantic 2.12+ demands explicit forward-ref resolution for classes imported
    # dynamically. Rebuild validators with the loaded module's namespace.
    try:
        mi.GenerateInput.model_rebuild(_types_namespace=mi.__dict__)
    except Exception:  # noqa: BLE001
        pass
    try:
        mo.GenerateOutput.model_rebuild(_types_namespace={**mi.__dict__, **mo.__dict__})
    except Exception:  # noqa: BLE001
        pass
    return mi, mi.GenerateInput, mo.GenerateOutput


_INPUT_MODULE, GenerateInput, GenerateOutput = _load_io_schemas()
UniverseSpec = _INPUT_MODULE.UniverseSpec


_SPEC_ID_RE = re.compile(r"^iter\d{3}_[a-z0-9_]+$")


def _build_user_message(gi: Any, fee_bps_rt: float = 0.0) -> str:
    """Render the GenerateInput into the AGENTS.md user_prompt template.

    fee_bps_rt : when > 0, an extra paragraph is injected reminding the LLM
    that net_expectancy = expectancy_bps − fee_bps_rt must be > 0 for a spec
    to be deployable. This shifts the hypothesis space toward magnitude
    (longer horizons, p99+ selectivity, regime concentration) rather than
    pure WR maximisation.
    """
    prior_fb_block = "none (first iteration)"
    if gi.prior_feedback:
        prior_fb_block = json.dumps(
            [fb.model_dump() if hasattr(fb, "model_dump") else fb for fb in gi.prior_feedback],
            indent=2,
            default=str,
        )
    prior_improve_block = "none"
    if gi.prior_improvement is not None:
        prior_improve_block = json.dumps(
            gi.prior_improvement.model_dump() if hasattr(gi.prior_improvement, "model_dump") else gi.prior_improvement,
            indent=2,
            default=str,
        )

    universe_block = json.dumps(gi.universe.model_dump(), indent=2)

    fee_block = ""
    if fee_bps_rt > 0:
        fee_block = (
            f"\nDeployment fee (round-trip): {fee_bps_rt:.1f} bps. "
            f"For a spec to be deployable, expectancy_bps MUST exceed {fee_bps_rt:.1f} bps "
            f"(net_expectancy = expectancy − fee > 0). Pure WR maximisation is insufficient: "
            f"a spec with WR=0.96 but expectancy=9 bps is still capped post-fee. "
            f"Hypothesise about MAGNITUDE per fill (longer horizons → larger |Δmid|; "
            f"p99+ selectivity → bigger tail moves; regime concentration → "
            f"high-volatility windows). Include the expected expectancy_bps in your hypothesis text "
            f"so the post-hoc calibration check can score you.\n"
        )

    return (
        f"Iteration index: {gi.iteration_idx}\n"
        f"Number of candidates requested: {gi.n_candidates}\n"
        f"Universe (symbols × dates the generated specs will run against):\n{universe_block}\n\n"
        f"Prior feedback (if any):\n{prior_fb_block}\n\n"
        f"Prior improvement proposal (if any):\n{prior_improve_block}\n"
        f"{fee_block}\n"
        f"Target: produce exactly {gi.n_candidates} SignalSpec candidates, all referencing at least one "
        f"file under _shared/references/. Remember: execution is fixed at 1; do NOT propose execution "
        f"logic. Use only whitelisted primitives."
    )


def _normalize_specs(specs: list[SignalSpec], iteration_idx: int) -> list[SignalSpec]:
    """Post-process LLM output to enforce project conventions not guaranteed by the schema alone."""
    out: list[SignalSpec] = []
    for s in specs:
        # Force iteration_idx and measured_* to match invariants
        data = s.model_dump()
        data["iteration_idx"] = iteration_idx
        data["measured_wr"] = None
        data["measured_expectancy_bps"] = None
        data["measured_n_trades"] = None

        # spec_id canonical form — always normalize:
        # (1) lowercase, (2) strip any pre-existing `iterNNN_` prefix(es) from
        #     the LLM output (prevents iter000_iter000_... chains), (3) sanitize
        #     remaining slug chars, (4) re-apply canonical prefix for current iter.
        sid = data.get("spec_id", "").strip().lower()
        stripped = re.sub(r"^(iter\d{3}_)+", "", sid)
        slug = re.sub(r"[^a-z0-9]+", "_", stripped).strip("_")[:40] or "spec"
        data["spec_id"] = f"iter{iteration_idx:03d}_{slug}"
        out.append(SignalSpec(**data))

    # De-duplicate spec_ids (tie-break by appending suffix)
    seen: dict[str, int] = {}
    for s in out:
        if s.spec_id in seen:
            seen[s.spec_id] += 1
            s.spec_id = f"{s.spec_id}_v{seen[s.spec_id]}"
        else:
            seen[s.spec_id] = 1
    return out


def generate_signals(
    iteration_idx: int,
    n_candidates: int,
    symbols: list[str],
    dates: list[str],
    prior_feedback: list[Any] | None = None,
    prior_improvement: Any | None = None,
    client: LLMClient | None = None,
    model_override: str | None = None,
    fee_bps_rt: float = 0.0,
) -> list[SignalSpec]:
    """Top-level entry: build GenerateInput → LLM → normalized list[SignalSpec]."""
    client = client or LLMClient()

    gi = GenerateInput(
        iteration_idx=iteration_idx,
        n_candidates=n_candidates,
        universe=UniverseSpec(symbols=symbols, dates=dates),
        prior_feedback=prior_feedback,
        prior_improvement=prior_improvement,
    )
    user_msg = _build_user_message(gi, fee_bps_rt=fee_bps_rt)

    result: Any = client.call_agent(
        agent_name="signal-generator",
        user_message=user_msg,
        response_model=GenerateOutput,
        model_override=model_override,
    )
    return _normalize_specs(result.specs, iteration_idx)


# ---------------------------------------------------------------------------
# CLI (useful for manual triggering once .env is set)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration-idx", type=int, default=0)
    ap.add_argument("--n-candidates", type=int, default=3)
    ap.add_argument("--symbols", nargs="+", default=["005930", "000660", "005380"])
    ap.add_argument("--dates", nargs="+", default=["20260326"])
    ap.add_argument("--model", default=None, help="Override CHAIN1_DEFAULT_MODEL for this call")
    ap.add_argument("--out-dir", default=None, help="If set, saves each SignalSpec as JSON under this dir")
    args = ap.parse_args()

    specs = generate_signals(
        iteration_idx=args.iteration_idx,
        n_candidates=args.n_candidates,
        symbols=args.symbols,
        dates=args.dates,
        model_override=args.model,
    )
    print(f"generated {len(specs)} specs:")
    for s in specs:
        print(f"  - {s.spec_id}  formula={s.formula}  threshold={s.threshold}")
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for s in specs:
            (out / f"{s.spec_id}.json").write_text(s.model_dump_json(indent=2))
        print(f"saved to {out}")
