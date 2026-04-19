#!/usr/bin/env python3
"""Append a single agent-call record to strategies/<id>/agent_trace.jsonl.

Called by the orchestrator (Claude main session) after each subagent invocation
during /iterate or /new-strategy. Pure record-keeping; it does not re-run
anything or alter agent behavior.

The trace is consumed by audit_handoff.py to measure multi-agent handoff
fidelity for the paper.

Usage:
  python scripts/log_agent_call.py --strategy <id> --agent alpha-designer \
      --model sonnet --status ok --output-hash <sha1-or-blank> \
      --note "optional short note"

Fields recorded per line:
  - timestamp (UTC ISO8601)
  - agent (e.g. "alpha-designer")
  - model (e.g. "sonnet" — model family; version pinning is TBD)
  - status ("ok" | "error" | "skipped")
  - output_hash (optional SHA1 of the agent's JSON output, for verification)
  - note (optional free-form)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = REPO_ROOT / "strategies"


def main() -> None:
    ap = argparse.ArgumentParser(description="Log a single agent call.")
    ap.add_argument("--strategy", required=True, help="Strategy id (target dir)")
    ap.add_argument("--agent", required=True, help="Agent name")
    ap.add_argument("--model", default="unknown", help="Model family (sonnet/opus/haiku/unknown)")
    ap.add_argument("--status", default="ok", choices=["ok", "error", "skipped"])
    ap.add_argument("--output-hash", default=None, dest="output_hash")
    ap.add_argument("--note", default=None)
    ap.add_argument("--iteration", type=int, default=None)
    ap.add_argument(
        "--timestamp",
        default=None,
        help="UTC ISO8601 timestamp. If omitted, uses time of invocation. "
        "Pass the agent's actual call time when logging retroactively (e.g. "
        "for alpha-designer / execution-designer buffered before spec-writer).",
    )
    args = ap.parse_args()

    strat_dir = STRATEGIES_DIR / args.strategy
    if not strat_dir.exists():
        raise SystemExit(
            f"[log_agent_call] strategy dir does not exist: {strat_dir}. "
            f"Call this script only after spec-writer has created the directory. "
            f"For pre-spec-writer agents (alpha-designer, execution-designer), "
            f"log retroactively once strategy_id is known, or buffer the entries."
        )

    ts = args.timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {
        "timestamp": ts,
        "iteration": args.iteration,
        "agent": args.agent,
        "model": args.model,
        "status": args.status,
        "output_hash": args.output_hash,
        "note": args.note,
    }

    trace_path = strat_dir / "agent_trace.jsonl"
    with trace_path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"[log_agent_call] {args.agent} ({args.model}) {args.status} -> {trace_path}")


if __name__ == "__main__":
    main()
