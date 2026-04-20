#!/usr/bin/env python3
"""Verify agent outputs after each iteration step.

Checks that claimed outputs actually exist and have required fields.
Exits 0 on success, 1 on failure. Returns JSON to stdout.

Usage:
  python scripts/verify_outputs.py --agent spec-writer   --output '<json>'
  python scripts/verify_outputs.py --agent feedback-analyst --output '<json>'
  python scripts/verify_outputs.py --agent backtest-runner  --output '<json>'
  python scripts/verify_outputs.py --agent meta-reviewer    --output '<json>'

Output JSON:
  {"ok": true, "failures": [], "warnings": []}
  {"ok": false, "failures": ["<what failed>"], "warnings": []}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STRATEGIES = ROOT / "strategies"
KNOWLEDGE = ROOT / "knowledge"
LESSONS = KNOWLEDGE / "lessons"


# Lazy import to keep verify_outputs importable even if engine/schemas/ is absent
def _import_schemas():
    from engine.schemas.alpha import AlphaHandoff
    from engine.schemas.execution import ExecutionHandoff
    from engine.schemas.feedback import FeedbackOutput
    return AlphaHandoff, ExecutionHandoff, FeedbackOutput


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _read_yaml_kind(spec_path: Path) -> str | None:
    """Return strategy_kind from spec.yaml without importing engine."""
    try:
        text = spec_path.read_text()
        for line in text.splitlines():
            if "strategy_kind" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return None


def _lesson_has_links(lesson_id: str) -> bool:
    matches = list(LESSONS.glob(f"{lesson_id}.md"))
    if not matches:
        return False
    text = matches[0].read_text()
    return "links:" in text


# ---------------------------------------------------------------------------
# Per-agent checkers
# ---------------------------------------------------------------------------

def check_spec_writer(output: dict, failures: list, warnings: list) -> None:
    strategy_id = output.get("strategy_id", "")
    spec_path_str = output.get("spec_path", "")

    if not strategy_id:
        failures.append("spec-writer: 'strategy_id' missing from output")
        return

    strat_dir = STRATEGIES / strategy_id
    if not strat_dir.exists():
        failures.append(f"spec-writer: strategy directory does not exist: {strat_dir}")
        return

    # spec.yaml must exist
    spec_path = ROOT / spec_path_str if spec_path_str else strat_dir / "spec.yaml"
    if not spec_path.exists():
        failures.append(f"spec-writer: spec.yaml not found at {spec_path}")
    else:
        # validate_spec must pass
        result = subprocess.run(
            [sys.executable, "scripts/validate_spec.py", str(spec_path)],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            failures.append(
                f"spec-writer: validate_spec.py failed — {result.stdout.strip() or result.stderr.strip()}"
            )

        # if python path, strategy.py must exist
        kind = _read_yaml_kind(spec_path)
        if kind == "python":
            strategy_py = strat_dir / "strategy.py"
            if not strategy_py.exists():
                failures.append(
                    f"spec-writer: strategy_kind=python but strategy.py missing at {strategy_py}"
                )

    # idea.json must be persisted
    idea_json = strat_dir / "idea.json"
    if not idea_json.exists():
        failures.append(f"spec-writer: idea.json not persisted at {idea_json}")

    # lot_size_used should be in output (new schema)
    if "lot_size_used" not in output:
        warnings.append(
            "spec-writer: 'lot_size_used' missing from output — spec-writer may not have run lot_size calculation (Step 2e)"
        )


def check_feedback_analyst(output: dict, failures: list, warnings: list) -> None:
    try:
        _, _, FeedbackOutput = _import_schemas()
        FeedbackOutput.model_validate(output)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            failures.append(f"feedback-analyst: {loc} — {err['msg']}")
    except Exception as e:
        failures.append(f"feedback-analyst: schema import or unexpected error — {e}")

    strategy_id = output.get("strategy_id", "")

    if not strategy_id:
        failures.append("feedback-analyst: 'strategy_id' missing from output")
        return

    # feedback.json must be persisted
    feedback_path = STRATEGIES / strategy_id / "feedback.json"
    if not feedback_path.exists():
        failures.append(f"feedback-analyst: feedback.json not written at {feedback_path}")
    else:
        saved = _read_json(feedback_path)
        if saved is None:
            failures.append(f"feedback-analyst: feedback.json is not valid JSON at {feedback_path}")
        else:
            # Verify saved file matches output for core fields
            for field in ("strategy_id", "lesson_id", "primary_finding", "stop_suggested"):
                if field not in saved:
                    failures.append(f"feedback-analyst: feedback.json missing required field '{field}'")

    # Dual seed schema check
    for field in ("local_seed", "escape_seed"):
        if not output.get(field):
            warnings.append(
                f"feedback-analyst: '{field}' missing or empty — update feedback-analyst.md schema is not yet reflected"
            )

    # lesson must exist in knowledge/lessons/
    lesson_id = output.get("lesson_id", "")
    if lesson_id:
        lesson_matches = list(LESSONS.glob(f"{lesson_id}.md"))
        if not lesson_matches:
            failures.append(
                f"feedback-analyst: lesson file not found — expected knowledge/lessons/{lesson_id}.md"
            )
        else:
            # Warn if lesson has no links (will become orphan)
            if not _lesson_has_links(lesson_id):
                warnings.append(
                    f"feedback-analyst: lesson '{lesson_id}' has no 'links:' field — "
                    "will be an orphan in the knowledge graph. Add --links to write_lesson.py call."
                )


def check_backtest_runner(output: dict, failures: list, warnings: list) -> None:
    strategy_id = output.get("strategy_id", "")

    if not strategy_id:
        failures.append("backtest-runner: 'strategy_id' missing from output")
        return

    # report.json must exist
    report_path = STRATEGIES / strategy_id / "report.json"
    if not report_path.exists():
        failures.append(f"backtest-runner: report.json not found at {report_path}")
        return

    report = _read_json(report_path)
    if report is None:
        failures.append(f"backtest-runner: report.json is not valid JSON at {report_path}")
        return

    # Required metric fields
    for field in ("return_pct", "n_trades", "win_rate_pct", "total_fees"):
        if field not in report and field not in output:
            failures.append(f"backtest-runner: '{field}' missing from report")

    # Calibration failure warnings
    n_trades = output.get("n_trades", report.get("n_trades"))
    if n_trades == 0:
        warnings.append(
            "backtest-runner: n_trades=0 — likely a calibration failure (Mode A, C, or symbol not in dataset). "
            "Do NOT proceed to feedback-analyst; diagnose the entry gate first."
        )

    anomaly = output.get("anomaly_flag") or report.get("anomaly_flag")
    if anomaly:
        warnings.append(f"backtest-runner: anomaly_flag={anomaly!r} — route to engine fix before continuing")

    # Mode D warning: if n_roundtrips > 200 on a single day, likely overtrading
    n_rt = output.get("n_roundtrips", report.get("n_roundtrips", 0))
    if n_rt and n_rt > 200:
        warnings.append(
            f"backtest-runner: n_roundtrips={n_rt} — likely Mode D overtrading (entry condition too loose). "
            "Check that qualifying ticks < 20% of total ticks."
        )


def check_meta_reviewer(output: dict, failures: list, warnings: list) -> None:
    action = output.get("action_taken", {})
    files_touched = action.get("files_touched", [])

    # All claimed files must exist
    for f in files_touched:
        p = ROOT / f
        if not p.exists():
            failures.append(
                f"meta-reviewer: claimed file_touched does not exist: {f}"
            )

    # meta_seed must be non-empty
    meta_seed = output.get("meta_seed", "")
    if not meta_seed or len(meta_seed) < 20:
        failures.append("meta-reviewer: 'meta_seed' is missing or too short (< 20 chars)")

    # If engine touched, audit must pass
    action_type = action.get("type", "")
    if action_type == "engine_fix":
        audit = output.get("audit_after_change", "")
        if "not applicable" not in audit.lower() and "pass" not in audit.lower():
            warnings.append(
                f"meta-reviewer: engine_fix taken but audit_after_change does not confirm passes: {audit!r}"
            )

    # paradigm_shift fields check
    if action_type == "paradigm_shift":
        ps = output.get("paradigm_shift")
        if not ps:
            failures.append(
                "meta-reviewer: action_taken.type='paradigm_shift' but 'paradigm_shift' extension is null"
            )
        else:
            for field in ("trigger", "direction", "concrete_seed"):
                if not ps.get(field):
                    failures.append(
                        f"meta-reviewer: paradigm_shift.{field} is missing or empty"
                    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def check_alpha_designer(output: dict, failures: list, warnings: list) -> None:
    """Pydantic validation for alpha-designer output."""
    try:
        AlphaHandoff, _, _ = _import_schemas()
        AlphaHandoff.model_validate(output)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            failures.append(f"alpha-designer: {loc} — {err['msg']}")
    except Exception as e:
        failures.append(f"alpha-designer: schema import or unexpected error — {e}")


def check_execution_designer(output: dict, failures: list, warnings: list) -> None:
    """Pydantic validation for execution-designer output."""
    try:
        _, ExecutionHandoff, _ = _import_schemas()
        ExecutionHandoff.model_validate(output)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            failures.append(f"execution-designer: {loc} — {err['msg']}")
    except Exception as e:
        failures.append(f"execution-designer: schema import or unexpected error — {e}")


def _check_critique_md(agent_name: str, output: dict, failures: list, warnings: list) -> None:
    """Shared checker for alpha-critic / execution-critic: require critique_md file exists and is non-trivial."""
    md_path_str = output.get("critique_md", "")
    if not md_path_str:
        failures.append(f"{agent_name}: 'critique_md' missing from output")
        return
    md_path = ROOT / md_path_str
    if not md_path.exists():
        failures.append(f"{agent_name}: critique_md not found at {md_path}")
        return
    try:
        text = md_path.read_text()
    except Exception as e:
        failures.append(f"{agent_name}: cannot read critique_md — {e}")
        return
    if len(text.strip()) < 100:
        failures.append(
            f"{agent_name}: critique_md at {md_path_str} is suspiciously short "
            f"({len(text.strip())} chars); expected a full critique"
        )


def check_alpha_critic(output: dict, failures: list, warnings: list) -> None:
    """File-presence check for alpha-critic output (critique_md)."""
    _check_critique_md("alpha-critic", output, failures, warnings)


def check_execution_critic(output: dict, failures: list, warnings: list) -> None:
    """File-presence check for execution-critic output (critique_md)."""
    _check_critique_md("execution-critic", output, failures, warnings)


def check_strategy_coder(output: dict, failures: list, warnings: list) -> None:
    """Verify strategy.py exists and is syntactically importable."""
    strategy_id = output.get("strategy_id", "")
    if not strategy_id:
        failures.append("strategy-coder: 'strategy_id' missing from output")
        return
    strat_py = STRATEGIES / strategy_id / "strategy.py"
    if not strat_py.exists():
        failures.append(f"strategy-coder: strategy.py not found at {strat_py}")
        return
    result = subprocess.run(
        [sys.executable, "-c", f"import importlib.util; "
         f"spec = importlib.util.spec_from_file_location('s', '{strat_py}'); "
         f"m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)"],
        capture_output=True, text=True, cwd=ROOT, timeout=15,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip().splitlines()[-1] if (result.stderr or result.stdout) else "unknown error"
        failures.append(f"strategy-coder: strategy.py import failed — {err}")


AGENT_CHECKERS = {
    "alpha-designer": check_alpha_designer,
    "execution-designer": check_execution_designer,
    "spec-writer": check_spec_writer,
    "strategy-coder": check_strategy_coder,
    "alpha-critic": check_alpha_critic,
    "execution-critic": check_execution_critic,
    "feedback-analyst": check_feedback_analyst,
    "backtest-runner": check_backtest_runner,
    "meta-reviewer": check_meta_reviewer,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agent", required=True, choices=list(AGENT_CHECKERS), help="Agent type to verify")
    ap.add_argument("--output", required=True, help="JSON output from the agent (as string)")
    args = ap.parse_args()

    try:
        output = json.loads(args.output)
    except json.JSONDecodeError as e:
        result = {"ok": False, "failures": [f"Cannot parse --output as JSON: {e}"], "warnings": []}
        print(json.dumps(result))
        sys.exit(1)

    failures: list[str] = []
    warnings: list[str] = []

    checker = AGENT_CHECKERS[args.agent]
    checker(output, failures, warnings)

    ok = len(failures) == 0
    result = {"ok": ok, "failures": failures, "warnings": warnings}
    print(json.dumps(result, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
