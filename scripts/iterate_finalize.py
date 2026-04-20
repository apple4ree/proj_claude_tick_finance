#!/usr/bin/env python3
"""End-of-iteration plumbing for /iterate and /new-strategy.

Guarantees that every completed iteration leaves behind the measurement
artifacts needed for the fidelity paper:

  1. Runs attribute_pnl for this strategy (produces report_strict.json and
     updates data/attribution_summary.json).
  2. Runs audit_handoff for this strategy (records presence/absence of
     mandated handoff artifacts).
  3. Appends a block to strategies/_iterate_context.md summarizing this
     iteration.

The orchestrator (Claude main session) calls this after the normal
per-iteration chain completes — it does NOT change agent behavior, it only
records what happened.

Usage:
  python scripts/iterate_finalize.py --strategy <id> \
      --iter <n> --seed-type <local|escape|paradigm|meta> \
      [--return-pct <x>] [--n-roundtrips <n>] [--win-rate <x>] \
      [--alpha-finding "..."] [--execution-finding "..."] \
      [--priority <alpha|execution|both>] [--next-seed "..."]

All metric fields are optional — missing ones are written as "n/a".
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = REPO_ROOT / "strategies"
ITERATE_CTX_PATH = STRATEGIES_DIR / "_iterate_context.md"


def _strategy_dir(strategy_id: str) -> Path:
    return STRATEGIES_DIR / strategy_id


def _run(cmd: list[str], log_prefix: str, fail_mode: str = "warn") -> int:
    """Run a subprocess. fail_mode='warn' => log non-zero exits and continue;
    'raise' => raise on non-zero."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as exc:
        print(f"[iterate_finalize] {log_prefix} FAILED (exception): {exc}", file=sys.stderr)
        return -1
    if proc.returncode != 0:
        msg = f"[iterate_finalize] {log_prefix} exited {proc.returncode}"
        if proc.stderr.strip():
            msg += f"\nstderr: {proc.stderr.strip()}"
        print(msg, file=sys.stderr)
        if fail_mode == "raise":
            raise SystemExit(proc.returncode)
    return proc.returncode


def run_attribute_pnl(strategy_id: str) -> int:
    """Run attribute_pnl if report_strict.json missing. Returns subprocess rc
    (0 on skip or success, nonzero on failure)."""
    strat_dir = _strategy_dir(strategy_id)
    if (strat_dir / "report_strict.json").exists():
        print(f"[iterate_finalize] report_strict.json already exists for {strategy_id}; skipping attribute_pnl")
        return 0
    if not (strat_dir / "spec.yaml").exists():
        print(f"[iterate_finalize] no spec.yaml for {strategy_id}; skipping attribute_pnl", file=sys.stderr)
        return 0
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "attribute_pnl.py"), "--strategy", strategy_id]
    return _run(cmd, f"attribute_pnl({strategy_id})")


def run_audit_handoff(strategy_id: str) -> dict | None:
    """Run audit_handoff; only load result if subprocess succeeded this call."""
    strat_dir = _strategy_dir(strategy_id)
    if not strat_dir.exists():
        print(f"[iterate_finalize] strategy dir missing for audit: {strat_dir}", file=sys.stderr)
        return None
    out_path = strat_dir / "handoff_audit.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "audit_handoff.py"),
        "--strategy",
        strategy_id,
        "--out",
        str(out_path),
        "--quiet",
    ]
    rc = _run(cmd, f"audit_handoff({strategy_id})")
    if rc != 0:
        print(f"[iterate_finalize] audit_handoff failed (rc={rc}); not reading possibly-stale {out_path}", file=sys.stderr)
        return None
    if out_path.exists():
        try:
            return json.loads(out_path.read_text())
        except Exception:
            return None
    return None


def _compute_attribution_from_reports(strategy_id: str) -> dict | None:
    """Fallback: read report.json + report_strict.json directly.

    Used when data/attribution_summary.json is stale or missing this strategy.
    """
    strat_dir = _strategy_dir(strategy_id)
    rep = strat_dir / "report.json"
    rep_strict = strat_dir / "report_strict.json"
    if not (rep.exists() and rep_strict.exists()):
        return None
    try:
        r = json.loads(rep.read_text())
        rs = json.loads(rep_strict.read_text())
    except Exception:
        return None
    n_normal = r.get("total_pnl")
    n_strict = rs.get("total_pnl")
    if n_normal is None or n_strict is None:
        return None
    clean_pct = (n_strict / n_normal * 100.0) if n_normal != 0 else None
    return {
        "strategy_id": strategy_id,
        "normal_pnl": n_normal,
        "strict_pnl_clean": n_strict,
        "bug_pnl": n_normal - n_strict,
        "clean_pct_of_total": clean_pct,
    }


def _summary_entry_is_fresh(strategy_id: str, entry: dict) -> bool:
    """Treat a summary entry as fresh only if both report.json and
    report_strict.json are no newer than the summary file itself. Otherwise
    the reports have been rewritten since the summary was generated and the
    entry is stale."""
    summary_path = REPO_ROOT / "data" / "attribution_summary.json"
    strat_dir = _strategy_dir(strategy_id)
    rep = strat_dir / "report.json"
    rep_strict = strat_dir / "report_strict.json"
    if not (summary_path.exists() and rep.exists() and rep_strict.exists()):
        return False
    try:
        s_mtime = summary_path.stat().st_mtime
        return rep.stat().st_mtime <= s_mtime and rep_strict.stat().st_mtime <= s_mtime
    except Exception:
        return False


def _load_attribution_entry(strategy_id: str) -> dict | None:
    summary_path = REPO_ROOT / "data" / "attribution_summary.json"
    if summary_path.exists():
        try:
            entries = json.loads(summary_path.read_text())
            for entry in reversed(entries):
                if entry.get("strategy_id") == strategy_id:
                    if _summary_entry_is_fresh(strategy_id, entry):
                        return entry
                    break
        except Exception:
            pass
    return _compute_attribution_from_reports(strategy_id)


def _fmt(v, fmt: str = "") -> str:
    if v is None:
        return "n/a"
    try:
        if fmt:
            return format(v, fmt)
        return str(v)
    except Exception:
        return str(v)


def _iteration_block_exists(text: str, iteration: int | None, strategy_id: str) -> bool:
    """Check whether an existing iteration block matches (iteration, strategy_id) exactly.

    Only true on an exact header match — prevents substring collisions between
    similar strategy ids.
    """
    if not text:
        return False
    iter_tag = f"{iteration}" if iteration is not None else "?"
    header = f"## Iteration {iter_tag} — {strategy_id} "
    return header in text


def append_iterate_context(
    strategy_id: str,
    iteration: int | None,
    seed_type: str | None,
    return_pct: float | None,
    n_roundtrips: int | None,
    win_rate: float | None,
    alpha_finding: str | None,
    execution_finding: str | None,
    priority: str | None,
    next_seed: str | None,
    audit: dict | None,
) -> str:
    """Append an iteration block to _iterate_context.md. Idempotent by
    (iteration, strategy_id): re-running with the same tuple is a no-op.

    IMPORTANT: This file is read by downstream agents (alpha-designer /
    execution-designer / feedback-analyst). It intentionally does NOT include
    handoff-fidelity measurement data — that lives in
    `strategies/<id>/handoff_audit.json`, read by the paper pipeline, not by
    agents. Mixing measurement metadata into agent context would change agent
    behavior (D7=c violation).

    Returns one of: "appended", "skipped_duplicate".
    """
    attribution = _load_attribution_entry(strategy_id) or {}
    clean_pct = attribution.get("clean_pct_of_total")
    bug_pnl = attribution.get("bug_pnl")

    existing_text = ITERATE_CTX_PATH.read_text() if ITERATE_CTX_PATH.exists() else ""
    if _iteration_block_exists(existing_text, iteration, strategy_id):
        print(
            f"[iterate_finalize] iteration {iteration} for {strategy_id} already "
            f"logged in _iterate_context.md; skipping append"
        )
        return "skipped_duplicate"

    lines: list[str] = []
    iter_tag = f"{iteration}" if iteration is not None else "?"
    seed_tag = seed_type or "?"
    lines.append(f"\n## Iteration {iter_tag} — {strategy_id} [{seed_tag}]")
    lines.append(f"- **Timestamp**: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(
        f"- **Result**: return {_fmt(return_pct, '+.4f')}%, "
        f"WR {_fmt(win_rate, '.1f')}%, "
        f"{_fmt(n_roundtrips)} roundtrips"
    )
    lines.append(
        f"- **Attribution**: clean_pct={_fmt(clean_pct, '.1f')}%, "
        f"bug_pnl={_fmt(bug_pnl, '+.2f')}"
    )
    lines.append(f"- **Alpha**: {alpha_finding or 'n/a'}")
    lines.append(f"- **Execution**: {execution_finding or 'n/a'}")
    lines.append(f"- **Priority**: {priority or 'n/a'}")
    lines.append(f"- **Seed → next**: {next_seed or 'n/a'}")

    block = "\n".join(lines) + "\n"

    if not existing_text:
        header = (
            "# Iterate Context Log\n\n"
            "Per-iteration summaries across `/iterate` runs. Read by downstream "
            "agents (alpha-designer / execution-designer / feedback-analyst). "
            "Handoff-fidelity measurement data is deliberately excluded — see "
            "`strategies/<id>/handoff_audit.json` instead. Automatically appended "
            "by `scripts/iterate_finalize.py`.\n"
        )
        ITERATE_CTX_PATH.write_text(header)

    with ITERATE_CTX_PATH.open("a") as f:
        f.write(block)
    return "appended"


def main() -> None:
    ap = argparse.ArgumentParser(description="End-of-iteration plumbing (attribute + audit + context).")
    ap.add_argument("--strategy", required=True, help="Strategy id (directory name under strategies/)")
    ap.add_argument("--iter", type=int, default=None, dest="iteration")
    ap.add_argument("--seed-type", default=None, dest="seed_type")
    ap.add_argument("--return-pct", type=float, default=None, dest="return_pct")
    ap.add_argument("--n-roundtrips", type=int, default=None, dest="n_roundtrips")
    ap.add_argument("--win-rate", type=float, default=None, dest="win_rate")
    ap.add_argument("--alpha-finding", default=None, dest="alpha_finding")
    ap.add_argument("--execution-finding", default=None, dest="execution_finding")
    ap.add_argument("--priority", default=None)
    ap.add_argument("--next-seed", default=None, dest="next_seed")
    ap.add_argument("--skip-attribution", action="store_true")
    ap.add_argument("--skip-audit", action="store_true")
    ap.add_argument("--skip-context", action="store_true")
    args = ap.parse_args()

    if not _strategy_dir(args.strategy).exists():
        raise SystemExit(f"strategy dir not found: {_strategy_dir(args.strategy)}")

    if not args.skip_attribution:
        run_attribute_pnl(args.strategy)

    audit = None
    if not args.skip_audit:
        audit = run_audit_handoff(args.strategy)

    if not args.skip_context:
        append_iterate_context(
            strategy_id=args.strategy,
            iteration=args.iteration,
            seed_type=args.seed_type,
            return_pct=args.return_pct,
            n_roundtrips=args.n_roundtrips,
            win_rate=args.win_rate,
            alpha_finding=args.alpha_finding,
            execution_finding=args.execution_finding,
            priority=args.priority,
            next_seed=args.next_seed,
            audit=audit,
        )

    print(f"[iterate_finalize] done for {args.strategy}")


if __name__ == "__main__":
    main()
