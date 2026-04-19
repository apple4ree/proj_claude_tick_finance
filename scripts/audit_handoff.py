#!/usr/bin/env python3
"""Audit multi-agent handoff artifact completeness per strategy.

Pure measurement. Does NOT modify strategies or agent behavior — it records
which mandated artifacts are present/missing so the paper can quantify
handoff fidelity.

Checked artifacts (per strategy directory):
  - spec.yaml, strategy.py, report.json, report_strict.json
  - idea.json (+ internal fields: signal_brief_rank, deviation_from_brief,
    per_symbol_alpha, model_version)
  - alpha_design.md, execution_design.md (spec-writer copies)
  - alpha_critique.md, execution_critique.md (critics)
  - feedback.json (feedback-analyst)
  - agent_trace.jsonl (orchestrator trace)

Cross-strategy:
  - strategies/_iterate_context.md mentions this strategy_id

Usage:
  python scripts/audit_handoff.py --strategy <id>
  python scripts/audit_handoff.py --all
  python scripts/audit_handoff.py --all --out data/handoff_audit.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = REPO_ROOT / "strategies"
ITERATE_CTX_PATH = STRATEGIES_DIR / "_iterate_context.md"


FILE_SPECS: list[tuple[str, str]] = [
    ("spec.yaml", "spec_writer"),
    ("strategy.py", "strategy_coder_or_template"),
    ("idea.json", "spec_writer"),
    ("report.json", "backtest_runner"),
    ("report_strict.json", "attribute_pnl"),
    ("alpha_design.md", "spec_writer_copy_of_alpha_draft"),
    ("execution_design.md", "spec_writer_copy_of_execution_draft"),
    ("alpha_critique.md", "alpha_critic"),
    ("execution_critique.md", "execution_critic"),
    ("feedback.json", "feedback_analyst"),
    ("agent_trace.jsonl", "orchestrator"),
]


IDEA_JSON_FIELDS: list[str] = [
    "signal_brief_rank",
    "deviation_from_brief",
]

IDEA_JSON_ALPHA_ANY: list[str] = ["per_symbol_alpha", "entry_condition", "hypothesis"]

IDEA_JSON_EXECUTION_ANY: list[str] = ["execution", "entry_execution", "exit_execution"]


def _load_json_safely(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _field_present(obj: Any, field: str) -> bool:
    """A field is 'present' if the key exists AND value is not null/empty.

    For nested fields a dot notation could be added later; currently top-level only.
    """
    if not isinstance(obj, dict):
        return False
    if field not in obj:
        return False
    value = obj[field]
    if value is None:
        return False
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return False
    return True


def audit_strategy(strategy_dir: Path, iterate_ctx_text: str | None) -> dict:
    strategy_id = strategy_dir.name
    result: dict[str, Any] = {"strategy_id": strategy_id, "path": str(strategy_dir)}

    files_present: dict[str, bool] = {}
    for filename, _responsible in FILE_SPECS:
        files_present[filename] = (strategy_dir / filename).exists()
    result["files_present"] = files_present
    result["files_missing"] = [f for f, present in files_present.items() if not present]

    idea = _load_json_safely(strategy_dir / "idea.json")
    idea_fields: dict[str, bool] = {f: _field_present(idea, f) for f in IDEA_JSON_FIELDS}
    alpha_any = any(_field_present(idea, f) for f in IDEA_JSON_ALPHA_ANY)
    exec_any = any(_field_present(idea, f) for f in IDEA_JSON_EXECUTION_ANY)
    idea_fields["alpha_specified"] = alpha_any
    idea_fields["execution_specified"] = exec_any
    result["idea_fields_present"] = idea_fields
    result["idea_fields_missing"] = [f for f, present in idea_fields.items() if not present]
    agent_trace_path_check = strategy_dir / "agent_trace.jsonl"
    result["model_version_logged"] = False
    if agent_trace_path_check.exists():
        try:
            text = agent_trace_path_check.read_text()
        except Exception:
            text = ""
        for ln in text.splitlines():
            if not ln.strip():
                continue
            try:
                entry = json.loads(ln)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(entry, dict) and entry.get("model") and entry.get("model") != "unknown":
                result["model_version_logged"] = True
                break

    report = _load_json_safely(strategy_dir / "report.json")
    report_strict = _load_json_safely(strategy_dir / "report_strict.json")
    if report and report_strict:
        n_normal = report.get("total_pnl")
        n_strict = report_strict.get("total_pnl")
        if n_normal is not None and n_strict is not None:
            bug_pnl = n_normal - n_strict
            clean_pct = (n_strict / n_normal * 100.0) if n_normal != 0 else None
            result["attribution"] = {
                "normal_pnl": n_normal,
                "strict_pnl_clean": n_strict,
                "bug_pnl": bug_pnl,
                "clean_pct_of_total": clean_pct,
            }
        else:
            result["attribution"] = None
    else:
        result["attribution"] = None

    inv_violations_raw = (report or {}).get("invariant_violations") or []
    if not isinstance(inv_violations_raw, list):
        inv_violations_raw = []
    inv_violations = [v for v in inv_violations_raw if isinstance(v, dict)]
    violation_by_type: dict[str, int] = {}
    for v in inv_violations:
        t = v.get("invariant_type", "unknown")
        violation_by_type[t] = violation_by_type.get(t, 0) + 1
    result["invariant_violation_count"] = len(inv_violations)
    result["invariant_violation_by_type"] = violation_by_type
    if len(inv_violations) != len(inv_violations_raw):
        result["invariant_violations_malformed"] = len(inv_violations_raw) - len(inv_violations)

    agent_trace_path = strategy_dir / "agent_trace.jsonl"
    if agent_trace_path.exists():
        try:
            lines = [ln for ln in agent_trace_path.read_text().splitlines() if ln.strip()]
            agents_logged = []
            models_used: set[str] = set()
            for ln in lines:
                try:
                    entry = json.loads(ln)
                    agents_logged.append(entry.get("agent"))
                    if entry.get("model"):
                        models_used.add(entry["model"])
                except Exception:
                    continue
            result["agent_trace"] = {
                "n_entries": len(lines),
                "agents_logged": agents_logged,
                "models_used": sorted(models_used),
            }
        except Exception:
            result["agent_trace"] = {"error": "failed_to_parse"}
    else:
        result["agent_trace"] = None

    if iterate_ctx_text is not None:
        result["referenced_in_iterate_context"] = strategy_id in iterate_ctx_text
    else:
        result["referenced_in_iterate_context"] = False

    required_critical = [
        "spec.yaml",
        "report.json",
    ]
    optional_fidelity = [
        "idea.json",
        "report_strict.json",
        "alpha_critique.md",
        "execution_critique.md",
        "feedback.json",
        "agent_trace.jsonl",
    ]
    crit_missing = [f for f in required_critical if not files_present.get(f, False)]
    fid_missing = [f for f in optional_fidelity if not files_present.get(f, False)]
    result["summary"] = {
        "critical_missing": crit_missing,
        "fidelity_missing": fid_missing,
        "idea_fields_missing_count": len(result["idea_fields_missing"]),
        "fully_instrumented": (not crit_missing) and (not fid_missing) and (not result["idea_fields_missing"]),
    }

    return result


def _is_strategy_dir(path: Path) -> bool:
    """All non-underscore subdirectories count as strategy attempts.

    Dirs without spec.yaml will be flagged as critical_missing rather than
    invisible — otherwise failed/incomplete strategies quietly inflate
    aggregate completion rates.
    """
    if not path.is_dir():
        return False
    if path.name.startswith("_"):
        return False
    return True


def audit_all(strategies_dir: Path) -> dict:
    ctx_text = ITERATE_CTX_PATH.read_text() if ITERATE_CTX_PATH.exists() else None
    strategies = sorted(p for p in strategies_dir.iterdir() if _is_strategy_dir(p))

    per_strategy = [audit_strategy(p, ctx_text) for p in strategies]

    n = len(per_strategy)
    agg: dict[str, Any] = {
        "n_strategies": n,
        "iterate_context_exists": ctx_text is not None,
    }

    if n == 0:
        agg["message"] = "no strategies found"
        return {"aggregate": agg, "strategies": []}

    file_counts: dict[str, int] = {fname: 0 for fname, _ in FILE_SPECS}
    for s in per_strategy:
        for fname, present in s["files_present"].items():
            if present:
                file_counts[fname] += 1
    agg["file_presence_rate"] = {
        fname: {"present": count, "rate": count / n} for fname, count in file_counts.items()
    }

    all_field_keys: set[str] = set()
    for s in per_strategy:
        all_field_keys.update(s["idea_fields_present"].keys())
    field_counts: dict[str, int] = {f: 0 for f in all_field_keys}
    for s in per_strategy:
        for fname, present in s["idea_fields_present"].items():
            if present:
                field_counts[fname] += 1
    agg["idea_field_presence_rate"] = {
        fname: {"present": count, "rate": count / n} for fname, count in field_counts.items()
    }

    model_logged = sum(1 for s in per_strategy if s.get("model_version_logged"))
    agg["model_version_logged_rate"] = {"present": model_logged, "rate": model_logged / n}

    fully = sum(1 for s in per_strategy if s["summary"]["fully_instrumented"])
    agg["fully_instrumented_count"] = fully
    agg["fully_instrumented_rate"] = fully / n

    clean_pcts = [
        s["attribution"]["clean_pct_of_total"]
        for s in per_strategy
        if s.get("attribution") and s["attribution"].get("clean_pct_of_total") is not None
    ]
    if clean_pcts:
        clean_pcts_sorted = sorted(clean_pcts)
        agg["clean_pct_of_total"] = {
            "n": len(clean_pcts),
            "mean": sum(clean_pcts) / len(clean_pcts),
            "min": clean_pcts_sorted[0],
            "max": clean_pcts_sorted[-1],
            "median": clean_pcts_sorted[len(clean_pcts_sorted) // 2],
        }
    else:
        agg["clean_pct_of_total"] = None

    violation_totals: dict[str, int] = {}
    total_violations = 0
    strategies_with_violations = 0
    for s in per_strategy:
        vbt = s.get("invariant_violation_by_type", {})
        total_violations += s.get("invariant_violation_count", 0)
        if s.get("invariant_violation_count", 0) > 0:
            strategies_with_violations += 1
        for t, c in vbt.items():
            violation_totals[t] = violation_totals.get(t, 0) + c
    agg["invariant_violations"] = {
        "total": total_violations,
        "by_type": violation_totals,
        "strategies_with_any_violation": strategies_with_violations,
        "strategies_with_any_violation_rate": strategies_with_violations / n,
    }

    return {"aggregate": agg, "strategies": per_strategy}


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit multi-agent handoff artifacts.")
    ap.add_argument("--strategy", help="Single strategy id", default=None)
    ap.add_argument("--all", action="store_true", help="Audit every strategy under strategies/")
    ap.add_argument("--out", help="Write JSON to this path", default=None)
    ap.add_argument("--quiet", action="store_true", help="Suppress per-strategy stdout")
    args = ap.parse_args()

    if not args.strategy and not args.all:
        ap.error("specify --strategy <id> or --all")

    if args.strategy:
        strategy_dir = STRATEGIES_DIR / args.strategy
        if not strategy_dir.exists():
            raise SystemExit(f"strategy directory not found: {strategy_dir}")
        ctx_text = ITERATE_CTX_PATH.read_text() if ITERATE_CTX_PATH.exists() else None
        result = audit_strategy(strategy_dir, ctx_text)
    else:
        result = audit_all(STRATEGIES_DIR)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output)
        if not args.quiet:
            print(f"wrote {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
