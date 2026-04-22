"""signal-evaluator hybrid wrapper (stage ②).

Implements CLAUDE.md's §Agent 원칙 "evidence-based" by running the
mechanical validity checks as deterministic Python FIRST (cheap, reliable),
and only delegating the soft subjective calls (duplicate_of, expected_merit,
reasoning synthesis) to the LLM.

Pipeline per incoming SignalSpec:

  1. Deterministic gate:
     - primitive whitelist
     - formula-primitives bidirectional consistency (via chain1.code_generator.parse_formula)
     - lookahead regex check
     - threshold range check against bounded primitives
     - horizon range check
     - references existence check
     - measured_* fields None
     - spec_id format
     - iteration_idx match

     If any hard-fail: short-circuit with valid=false; skip LLM call.

  2. LLM soft judgment (only if deterministic gate passes):
     - expected_merit (high/medium/low/unknown)
     - duplicate_of (vs prior_iterations_index.md)
     - reasoning (≥ 20 chars explanation)

Return: SpecEvaluation.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
AGENT_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "signal-evaluator"

for p in (str(REPO_ROOT), str(SHARED_DIR), str(AGENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import SignalSpec, SpecEvaluation  # noqa: E402
from chain1.code_generator import parse_formula, PRIMITIVE_NAMES, FormulaParseError, STATEFUL_HELPERS  # noqa: E402
from chain1.primitives import PRIMITIVE_WHITELIST  # noqa: E402
from chain1.llm_client import LLMClient  # noqa: E402


def _load_io_schemas():
    in_path = AGENT_DIR / "input_schema.py"
    out_path = AGENT_DIR / "output_schema.py"
    spec_in = importlib.util.spec_from_file_location("sigeval_in", in_path)
    spec_out = importlib.util.spec_from_file_location("sigeval_out", out_path)
    mi = importlib.util.module_from_spec(spec_in); spec_in.loader.exec_module(mi)
    mo = importlib.util.module_from_spec(spec_out); spec_out.loader.exec_module(mo)
    for cls_name, mod in (("EvaluateInput", mi), ("EvaluateOutput", mo)):
        try:
            getattr(mod, cls_name).model_rebuild(_types_namespace={**mi.__dict__, **mo.__dict__})
        except Exception:  # noqa: BLE001
            pass
    return mi.EvaluateInput, mo.EvaluateOutput


EvaluateInput, EvaluateOutput = _load_io_schemas()


# ---------------------------------------------------------------------------
# Deterministic checks (hard-fail gate)
# ---------------------------------------------------------------------------


_LOOKAHEAD_PATTERNS = [r"\bnext_\w*", r"\bfwd_\w*", r"\bfuture_\w*", r"_t\+", r"post_trade", r"post_tick", r"_later\b"]
_SPEC_ID_RE = re.compile(r"^iter\d{3}_[a-z0-9_]+$")


def _deterministic_checks(spec: SignalSpec, iteration_idx: int) -> tuple[bool, list[str]]:
    """Return (hard_valid, concerns). hard_valid=False means spec is rejected regardless of LLM."""
    concerns: list[str] = []
    hard_valid = True

    # 1. Primitive whitelist — tolerate common LLM confusion where stateful
    # helpers (zscore, rolling_mean, etc.) get listed in primitives_used.
    # Silently strip helpers before checking against PRIMITIVE_NAMES; helpers
    # are validated structurally by parse_formula anyway.
    declared = set(spec.primitives_used)
    helpers_in_declared = declared & set(STATEFUL_HELPERS.keys())
    if helpers_in_declared:
        # Strip helpers; record informational concern (not fatal)
        declared = declared - helpers_in_declared
        concerns.append(
            f"helpers_in_primitives_used:stripped:{sorted(helpers_in_declared)} "
            f"(helpers belong in formula, not primitives_used — auto-fixed)"
        )
        # Mutate the spec's primitives_used to the cleaned set for downstream codegen
        spec.primitives_used = sorted(declared)

    unknown = declared - PRIMITIVE_NAMES
    if unknown:
        concerns.append(f"primitive_not_whitelisted:{sorted(unknown)}")
        hard_valid = False

    # 2. Formula-primitives consistency (via code_generator parser)
    if hard_valid:
        try:
            _, referenced, _, _ = parse_formula(spec.formula, set(spec.primitives_used))
            declared = set(spec.primitives_used)
            if referenced != declared:
                extra = declared - referenced
                missing = referenced - declared
                if extra:
                    concerns.append(f"declared_but_unused:{sorted(extra)}")
                if missing:
                    # Auto-add missing primitives that appear in the formula
                    spec.primitives_used = sorted(declared | missing)
                    concerns.append(
                        f"auto_added_missing_primitives:{sorted(missing)} "
                        f"(formula referenced them but not declared — auto-fixed)"
                    )
                    # Only the `extra` remains as hard-fail if any
                    if not extra:
                        pass  # not hard-fail
                    else:
                        hard_valid = False
                else:
                    hard_valid = False  # extra only
        except FormulaParseError as e:
            concerns.append(f"formula_parse_error:{e}")
            hard_valid = False

    # 3. Lookahead
    for pat in _LOOKAHEAD_PATTERNS:
        if re.search(pat, spec.formula):
            concerns.append(f"lookahead_pattern:{pat}")
            hard_valid = False

    # 4. Threshold range for bounded primitives
    bounded_primitives = {name for name, meta in PRIMITIVE_WHITELIST.items() if meta["bounded"] == (-1.0, 1.0)}
    if set(spec.primitives_used) <= bounded_primitives:
        if abs(spec.threshold) > 1.5:
            concerns.append(f"threshold_out_of_range:{spec.threshold} for bounded primitives")
            # Soft concern, not hard-fail (could be intentional z-score threshold)

    # 5. Horizon range
    if not (1 <= spec.prediction_horizon_ticks <= 100):
        concerns.append(f"horizon_out_of_range:{spec.prediction_horizon_ticks}")
        hard_valid = False

    # 6. References existence — tolerate several common relative-path conventions
    #    that the LLM may use. Search order:
    #       (a) as-given relative to REPO_ROOT
    #       (b) under .claude/agents/chain1/
    #       (c) any path inside .claude/agents/chain1/ matching the basename
    missing_refs: list[str] = []
    CHAIN1_ROOT = REPO_ROOT / ".claude" / "agents" / "chain1"
    for ref in spec.references:
        if (REPO_ROOT / ref).exists():
            continue
        # Try prefixing with chain1 root
        if (CHAIN1_ROOT / ref).exists():
            continue
        # Strip leading "./" / "_shared/..." / similar
        stripped = ref.lstrip("./")
        if (CHAIN1_ROOT / stripped).exists():
            continue
        # Last resort: basename match under chain1/
        basename = Path(ref).name
        matches = list(CHAIN1_ROOT.rglob(basename))
        if matches:
            continue
        missing_refs.append(ref)
    if missing_refs:
        concerns.append(f"references_not_found:{missing_refs}")
        hard_valid = False
    if not spec.references:
        concerns.append("no_references_cited")
        hard_valid = False

    # 7. Measured fields None
    for f in ("measured_wr", "measured_expectancy_bps", "measured_n_trades"):
        if getattr(spec, f) is not None:
            concerns.append(f"measured_field_not_none:{f}")
            hard_valid = False

    # 8. spec_id format
    if not _SPEC_ID_RE.match(spec.spec_id):
        concerns.append(f"spec_id_malformed:{spec.spec_id}")
        hard_valid = False

    # 9. iteration_idx match
    if spec.iteration_idx != iteration_idx:
        concerns.append(f"iteration_idx_mismatch:{spec.iteration_idx} vs {iteration_idx}")
        hard_valid = False

    # 10. Hypothesis length (soft)
    if len(spec.hypothesis) < 50:
        concerns.append("hypothesis_short (< 50 chars)")

    return hard_valid, concerns


# ---------------------------------------------------------------------------
# LLM soft judgment (duplicate + merit + reasoning)
# ---------------------------------------------------------------------------


def _build_user_message(spec: SignalSpec, iteration_idx: int, det_concerns: list[str]) -> str:
    prior_index_path = REPO_ROOT / ".claude" / "agents" / "chain1" / "signal-generator" / "references" / "prior_iterations_index.md"
    prior_body = prior_index_path.read_text() if prior_index_path.exists() else "(empty)"
    has_prior_entries = prior_body and "####" in prior_body  # heuristic — a real entry looks like "#### iterXXX_..."
    return (
        f"SignalSpec under review (iteration {iteration_idx}):\n{spec.model_dump_json(indent=2)}\n\n"
        f"Prior iterations index (for duplicate check — **authoritative source**):\n{prior_body}\n\n"
        f"Deterministic pre-checks completed — concerns accumulated so far:\n"
        f"{json.dumps(det_concerns, indent=2) if det_concerns else '(none)'}\n\n"
        f"Produce the final SpecEvaluation. Your job is to:\n"
        f"  - Append to `concerns` any ADDITIONAL issues (do not repeat the deterministic ones above)\n"
        f"  - Set `duplicate_of` ONLY if an entry with **EXACT** matching `formula` AND `threshold` "
        f"(within 5% tolerance) AND `prediction_horizon_ticks` AND `direction` appears in the prior "
        f"iterations index above. The current index has "
        f"{'prior entries you must check against' if has_prior_entries else 'NO prior entries — you MUST NOT mark anything as duplicate'}. "
        f"DO NOT guess based on spec_id naming conventions. Evidence must be a quote from the prior index body above.\n"
        f"  - Set `expected_merit` ∈ {{high, medium, low, unknown}} using the heuristic in "
        f"../signal-evaluator/references/formula_validity_rules.md §Expected-merit heuristic\n"
        f"  - Write `reasoning` (≥ 20 chars) summarising steps 1–9 from the Reasoning Flow. "
        f"When setting `valid=false`, the reasoning MUST cite which specific check failed.\n"
        f"  - Set `valid` — if deterministic check already marked hard-fail, preserve valid=false. "
        f"Otherwise set valid=true unless you find a new fatal concern. A fatal concern requires an "
        f"evidence-based justification (quote from the spec fields or prior index, not intuition).\n"
    )


def evaluate_signal(
    spec: SignalSpec,
    iteration_idx: int,
    client: LLMClient | None = None,
    model_override: str | None = None,
    skip_llm: bool = False,
) -> SpecEvaluation:
    """Hybrid evaluator: deterministic gate + optional LLM soft judgment.

    If `skip_llm=True` (Phase C-compatible mode), returns a SpecEvaluation
    assembled entirely from deterministic findings. Useful when offline.
    """
    hard_valid, det_concerns = _deterministic_checks(spec, iteration_idx)

    if skip_llm or not hard_valid:
        # Short-circuit: deterministic-only path
        merit = "unknown" if hard_valid else "low"
        return SpecEvaluation(
            agent_name="signal-evaluator",
            iteration_idx=iteration_idx,
            spec_id=spec.spec_id,
            valid=hard_valid,
            concerns=det_concerns,
            duplicate_of=None,
            expected_merit=merit,
            reasoning=(
                f"Deterministic-only evaluation. hard_valid={hard_valid}. "
                f"{len(det_concerns)} concern(s) recorded: {det_concerns[:5]}"
            ),
        )

    # Live LLM soft judgment
    client = client or LLMClient()
    user_msg = _build_user_message(spec, iteration_idx, det_concerns)
    result: Any = client.call_agent(
        agent_name="signal-evaluator",
        user_message=user_msg,
        response_model=EvaluateOutput,
        model_override=model_override,
    )

    # Merge deterministic concerns with any new LLM-added ones
    eval_obj = result.evaluation
    eval_data = eval_obj.model_dump()
    merged_concerns = list(dict.fromkeys(det_concerns + eval_data.get("concerns", [])))
    # If LLM set valid=false but provided no concerns, inject a synthetic one so
    # the user can see WHY it was rejected. Pull from reasoning if non-empty.
    if not eval_data.get("valid", True) and not merged_concerns:
        reasoning_brief = (eval_data.get("reasoning") or "LLM rejected without explicit concern")[:200]
        merged_concerns = [f"llm_reject_without_concern: {reasoning_brief}"]
    eval_data["concerns"] = merged_concerns
    # Preserve deterministic hard-fail outcome
    if not hard_valid:
        eval_data["valid"] = False
    # Ensure iteration_idx and spec_id match
    eval_data["iteration_idx"] = iteration_idx
    eval_data["spec_id"] = spec.spec_id
    eval_data["agent_name"] = "signal-evaluator"
    return SpecEvaluation(**eval_data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True)
    ap.add_argument("--iteration-idx", type=int, default=0)
    ap.add_argument("--skip-llm", action="store_true", help="Run deterministic checks only")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    spec_dict = json.loads(Path(args.spec_json).read_text())
    spec = SignalSpec(**spec_dict)

    result = evaluate_signal(
        spec, args.iteration_idx,
        skip_llm=args.skip_llm,
        model_override=args.model,
    )
    print(result.model_dump_json(indent=2))
