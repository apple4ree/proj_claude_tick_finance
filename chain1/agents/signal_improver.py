"""signal-improver hybrid wrapper (stage ⑤).

Deterministic part:
  - Rank the iteration's (spec, result, feedback) triples by (expectancy, wr, n_trades).
  - Drop any triple whose feedback.recommended_next_direction == 'retire'.
  - Apply the budget allocation (analysis_framework §budget, simplified) to
    decide how many children each surviving parent seeds.
  - Synthesise an ImprovementProposal per parent using the recipes from
    `improvement_heuristics.md`.

LLM part (optional):
  - Rephrase / enrich `proposed_mutations` strings and `reasoning` text.
  - Suggest cross-spec combinations when two parents have complementary traits
    (high-WR + low-trade-count, or vice versa).

The deterministic path alone produces a valid ImprovementProposal list; LLM
augmentation is purely narrative / diversity-seeking.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
AGENT_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "signal-improver"

for p in (str(REPO_ROOT), str(SHARED_DIR), str(AGENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import SignalSpec, BacktestResult, Feedback, ImprovementProposal  # noqa: E402
from chain1.llm_client import LLMClient  # noqa: E402


def _load_io_schemas():
    in_path = AGENT_DIR / "input_schema.py"
    out_path = AGENT_DIR / "output_schema.py"
    spec_in = importlib.util.spec_from_file_location("si_in", in_path)
    spec_out = importlib.util.spec_from_file_location("si_out", out_path)
    mi = importlib.util.module_from_spec(spec_in); spec_in.loader.exec_module(mi)
    mo = importlib.util.module_from_spec(spec_out); spec_out.loader.exec_module(mo)
    # Pydantic forward-ref resolution — ensure SignalSpec/BacktestResult/Feedback (from mi's
    # namespace) are bound before we instantiate FeedbackTriple. Rebuild validator graph.
    try:
        mi.FeedbackTriple.model_rebuild(_types_namespace=mi.__dict__)
    except Exception:  # noqa: BLE001
        pass
    try:
        mi.ImproveInput.model_rebuild(_types_namespace=mi.__dict__)
    except Exception:  # noqa: BLE001
        pass
    try:
        mo.ImproveOutput.model_rebuild(_types_namespace={**mi.__dict__, **mo.__dict__})
    except Exception:  # noqa: BLE001
        pass
    return mi.ImproveInput, mi.FeedbackTriple, mo.ImproveOutput


ImproveInput, FeedbackTriple, ImproveOutput = _load_io_schemas()


# ---------------------------------------------------------------------------
# Recipe templates (paraphrases of improvement_heuristics.md)
# ---------------------------------------------------------------------------


def _mutations_for_direction(spec: SignalSpec, direction: str) -> tuple[list[str], list[str]]:
    """Return (mutations, search_axes) for a given recommendation."""
    thr = spec.threshold
    horizon = spec.prediction_horizon_ticks

    if direction == "tighten_threshold":
        new = round(thr * 1.5, 4)
        return [f"threshold {thr} -> {new}"], ["threshold"]
    if direction == "loosen_threshold":
        new = round(thr * 0.6, 4)
        return [f"threshold {thr} -> {new}"], ["threshold"]
    if direction == "add_filter":
        filt = "AND spread_bps < 10"
        return [f"add filter: {filt}"], ["filter"]
    if direction == "drop_feature":
        if len(spec.primitives_used) >= 2:
            primary = spec.primitives_used[0]
            return [f"drop primitive {primary}; simplify formula to next-ranked feature"], ["feature"]
        return [f"drop primary primitive {spec.primitives_used[0]} and swap to alternative family"], ["feature"]
    if direction == "swap_feature":
        # Heuristic swap map
        swap = {
            "obi_1": "ofi_proxy",
            "obi_5": "microprice_dev_bps",
            "obi_total": "ofi_cks_1",
            "ofi_proxy": "ofi_cks_1",
            "ofi_cks_1": "microprice_dev_bps",
            "microprice_dev_bps": "vamp_5",
        }
        primary = spec.primitives_used[0]
        new_prim = swap.get(primary, "ofi_proxy")
        return [f"swap primitive {primary} -> {new_prim}"], ["feature"]
    if direction == "change_horizon":
        # Expanded cycle per Block B: reach longer horizons where |Δmid| is larger
        # (random-walk scaling √h), at cost of predictive power decay per CKS 2014.
        # Sweet spot empirically ~h=20-50 for KRX microstructure.
        cycle = [1, 5, 20, 50, 100]
        try:
            nxt = cycle[(cycle.index(horizon) + 1) % len(cycle)]
        except ValueError:
            nxt = 20  # default jump to the sweet-spot mid
        return [f"horizon {horizon} -> {nxt} ticks"], ["horizon"]
    if direction == "combine_with_other_spec":
        return [f"combine formula with a complementary spec in same batch (to be resolved at next generation)"], ["combine"]
    if direction == "retire":
        return [], []
    # Block B: Additional mutation directions
    if direction == "ensemble_vote":
        # Require at least 2 of 3 conditions to agree (uses compound AND/OR)
        return [
            "ensemble: require majority of 3 thresholded primitives to agree, "
            "e.g. `(obi_1 > 0.5 AND ofi_proxy > 0) OR (obi_1 > 0.5 AND microprice_dev_bps > 2)`"
        ], ["combine", "filter"]
    if direction == "extreme_quantile":
        # Use zscore helper with higher threshold (p99+) — fewer but sharper trades
        primary = spec.primitives_used[0]
        return [f"tighten to extreme: `zscore({primary}, 300) > 2.5` (p99+ selectivity)"], ["threshold", "filter"]
    if direction == "timevarying_threshold":
        # Threshold scaled by rolling_std of primary primitive (adaptive)
        primary = spec.primitives_used[0]
        return [
            f"timevarying threshold: replace static threshold with "
            f"`{primary} > 2 * rolling_std({primary}, 300)` (2-sigma adaptive)"
        ], ["threshold"]
    if direction == "add_regime_filter":
        # NEW: add a regime filter using Block A primitives
        return [
            "add regime filter: AND with one of "
            "`rolling_realized_vol(mid_px, 100) > 40` (high-vol regime), "
            "`minute_of_session > 350` (closing zone), or "
            "`book_thickness > 800000` (thick book)"
        ], ["filter"]
    return [f"unspecified mutation for direction={direction}"], ["feature"]


def _allocate_budget(n_parents: int, budget: int) -> list[int]:
    """Allocate budget seats across ranked parents.

    Policy: top parent 40%, then 30%, 20%, 10% for subsequent; cap at n_parents.
    Rounds down and redistributes remainder top-down.
    """
    if n_parents == 0 or budget == 0:
        return []
    weights = [0.4, 0.3, 0.2, 0.1][:n_parents]
    # Normalize in case we have fewer parents than weights
    s = sum(weights)
    alloc = [int(budget * (w / s)) for w in weights]
    # Distribute remainder
    remainder = budget - sum(alloc)
    for i in range(remainder):
        alloc[i % len(alloc)] += 1
    return alloc


# ---------------------------------------------------------------------------
# Deterministic improvement path
# ---------------------------------------------------------------------------


def _rank_triples(triples: list[FeedbackTriple]) -> list[FeedbackTriple]:
    def key(t: FeedbackTriple) -> tuple:
        r = t.result
        return (
            -(r.aggregate_expectancy_bps or 0.0),
            -(r.aggregate_wr or 0.0),
            -(r.aggregate_n_trades or 0),
        )
    return sorted(triples, key=key)


def _build_deterministic_proposals(
    triples: list[FeedbackTriple],
    iteration_idx: int,
    next_budget: int,
) -> list[ImprovementProposal]:
    # Drop retires
    survivors = [t for t in triples if t.feedback.recommended_next_direction != "retire"]
    ranked = _rank_triples(survivors)
    if not ranked:
        return []
    alloc = _allocate_budget(len(ranked), next_budget)

    proposals: list[ImprovementProposal] = []
    for parent, seats in zip(ranked, alloc):
        if seats <= 0:
            continue
        direction = parent.feedback.recommended_next_direction
        mutations, axes = _mutations_for_direction(parent.spec, direction)
        if not mutations:
            continue
        # Duplicate the proposal `seats` times with minor variant labels if >1 seat
        for seat_idx in range(seats):
            variant_note = "" if seats == 1 else f" (variant {seat_idx+1}/{seats})"
            proposals.append(ImprovementProposal(
                agent_name="signal-improver",
                iteration_idx=iteration_idx,
                parent_spec_id=parent.spec.spec_id,
                proposed_mutations=[m + variant_note for m in mutations],
                search_axes=axes,
                reasoning=(
                    f"Parent WR={parent.result.aggregate_wr:.3f} "
                    f"exp={parent.result.aggregate_expectancy_bps:+.3f}bps "
                    f"n={parent.result.aggregate_n_trades}. Feedback direction={direction}: "
                    f"{parent.feedback.recommended_direction_reasoning[:200]}"
                ),
            ))
    # Cap at budget
    return proposals[:next_budget]


# ---------------------------------------------------------------------------
# LLM augmentation (optional)
# ---------------------------------------------------------------------------


def _build_user_message(
    triples: list[FeedbackTriple],
    iteration_idx: int,
    next_budget: int,
    det_proposals: list[ImprovementProposal],
) -> str:
    summaries = []
    for t in triples:
        summaries.append({
            "spec_id": t.spec.spec_id,
            "formula": t.spec.formula,
            "threshold": t.spec.threshold,
            "horizon": t.spec.prediction_horizon_ticks,
            "wr": t.result.aggregate_wr,
            "expectancy_bps": t.result.aggregate_expectancy_bps,
            "n_trades": t.result.aggregate_n_trades,
            "recommendation": t.feedback.recommended_next_direction,
            "reasoning": t.feedback.recommended_direction_reasoning,
        })
    det = [p.model_dump() for p in det_proposals]
    return (
        f"Iteration: {iteration_idx}\nNext-iteration budget: {next_budget}\n\n"
        f"Feedback triples this iteration:\n{json.dumps(summaries, indent=2, default=str)}\n\n"
        f"Deterministic proposal draft (use this as anchor — preserve parent_spec_id + search_axes; "
        f"you may refine proposed_mutations strings and reasoning):\n{json.dumps(det, indent=2, default=str)}\n\n"
        f"Your job: return an ImproveOutput with up to {next_budget} proposals. You MAY:\n"
        f"  - Sharpen mutation text (keep atomic — single-axis changes)\n"
        f"  - Propose cross-spec combinations when two high-merit parents have complementary traits\n"
        f"  - Add a concise reasoning per proposal citing the parent's measured numbers\n"
        f"Do NOT drop any deterministic proposal without explicit justification in its reasoning field.\n"
    )


def improve_signals(
    triples: list[Any],
    iteration_idx: int,
    next_iteration_budget: int,
    client: LLMClient | None = None,
    model_override: str | None = None,
    skip_llm: bool = False,
) -> list[ImprovementProposal]:
    """Hybrid signal-improver entry point."""
    # Accept both FeedbackTriple instances and plain dicts
    normalized: list[FeedbackTriple] = []
    for t in triples:
        if isinstance(t, FeedbackTriple):
            normalized.append(t)
        else:
            normalized.append(FeedbackTriple(**t))
    det_proposals = _build_deterministic_proposals(normalized, iteration_idx, next_iteration_budget)
    if skip_llm:
        return det_proposals

    if not normalized:
        return []

    client = client or LLMClient()
    user_msg = _build_user_message(normalized, iteration_idx, next_iteration_budget, det_proposals)
    response: Any = client.call_agent(
        agent_name="signal-improver",
        user_message=user_msg,
        response_model=ImproveOutput,
        model_override=model_override,
    )

    proposals = []
    for p in response.proposals:
        d = p.model_dump()
        d["iteration_idx"] = iteration_idx
        d["agent_name"] = "signal-improver"
        proposals.append(ImprovementProposal(**d))
    return proposals[:next_iteration_budget]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--triples-json", required=True, help="JSON list of {spec, result, feedback}")
    ap.add_argument("--iteration-idx", type=int, default=0)
    ap.add_argument("--budget", type=int, default=3)
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    triples = json.loads(Path(args.triples_json).read_text())
    proposals = improve_signals(
        triples, args.iteration_idx, args.budget,
        skip_llm=args.skip_llm, model_override=args.model,
    )
    print(json.dumps([p.model_dump() for p in proposals], indent=2, default=str))
