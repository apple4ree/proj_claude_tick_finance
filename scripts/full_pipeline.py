#!/usr/bin/env python3
"""End-to-end pipeline orchestrator.

Runs:
  1. Phase 1 — discover_alpha.py        → signal_brief_v2.json
  2. Phase 2 — (skipped; strategies to test are passed in)
  3. Phase 2.5 — backtest (intraday/bar artifact generator)
  4. Phase 3 — validate_strategy.py     → validation.json per strategy
  5. Phase 3.5 — benchmark_vs_bh.py     → bh_benchmark.json
  6. Phase 4 — run_feedback.py          → feedback_auto.{json,md}, _iterate_context.md

Usage:
    python scripts/full_pipeline.py \\
        --market crypto_1h --symbols BTCUSDT,ETHUSDT,SOLUSDT \\
        --is-start 2025-07-01 --is-end 2025-10-31 \\
        --oos-start 2025-11-01 --oos-end 2025-12-31 \\
        --strategies-pattern 'crypto_1h_weekly_meanrev_*' \\
        --output-dir experiments/pipeline_$(date +%Y%m%d_%H%M)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run(cmd: list[str], label: str) -> int:
    print(f"\n═══════ {label} ═══════")
    print(" ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print(f"  ⚠ exit code {rc}")
    return rc


def phase1_discover(market: str, symbols: str, is_start: str, is_end: str,
                    brief_path: Path) -> int:
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    return run([
        sys.executable, "scripts/discover_alpha.py",
        "--market", market,
        "--symbols", symbols,
        "--is-start", is_start,
        "--is-end", is_end,
        "--output", str(brief_path),
    ], label="Phase 1 — discover_alpha")


def phase25_backtest(strategies: list[str], market: str) -> int:
    # Use intraday for non-daily horizons, bar for daily
    runner = ("scripts/intraday_full_artifacts.py"
              if market != "crypto_1d" else "scripts/bar_full_artifacts.py")
    rcs = []
    for sid in strategies:
        rc = run([sys.executable, runner, "--id", sid], label=f"Backtest {sid}")
        rcs.append(rc)
    return max(rcs) if rcs else 0


def phase3_validate(strategies: list[str], oos_start: str, oos_end: str) -> int:
    # Pattern-based to let gate 4 (sibling check) walk all
    # Build a pattern covering the listed strategies
    if len(strategies) == 1:
        flag = ["--id", strategies[0]]
    else:
        # longest common prefix + *
        from os.path import commonprefix
        pat = commonprefix(strategies).rstrip("_") + "*"
        flag = ["--pattern", pat]
    return run([
        sys.executable, "scripts/validate_strategy.py",
        *flag,
        "--oos-start", oos_start,
        "--oos-end", oos_end,
    ], label="Phase 3 — validate_strategy")


def phase35_benchmark(strategies: list[str], out_dir: Path) -> int:
    if len(strategies) == 1:
        flag = ["--id", strategies[0]]
    else:
        from os.path import commonprefix
        pat = commonprefix(strategies).rstrip("_") + "*"
        flag = ["--pattern", pat]
    return run([
        sys.executable, "scripts/benchmark_vs_bh.py",
        *flag,
        "--out", str(out_dir / "bh_benchmark.json"),
    ], label="Phase 3.5 — benchmark_vs_bh")


def phase4_feedback(strategies: list[str]) -> int:
    if len(strategies) == 1:
        flag = ["--id", strategies[0]]
    else:
        from os.path import commonprefix
        pat = commonprefix(strategies).rstrip("_") + "*"
        flag = ["--pattern", pat]
    return run([
        sys.executable, "scripts/run_feedback.py", *flag,
    ], label="Phase 4 — run_feedback")


def resolve_strategies(pattern: str | None, ids: list[str] | None) -> list[str]:
    if ids:
        return ids
    if pattern:
        strategies_dir = REPO / "strategies"
        return sorted([d.name for d in strategies_dir.iterdir()
                       if d.is_dir() and fnmatch.fnmatch(d.name, pattern)])
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--is-start", required=True)
    ap.add_argument("--is-end", required=True)
    ap.add_argument("--oos-start", required=True)
    ap.add_argument("--oos-end", required=True)

    ap.add_argument("--strategies-pattern",
                    help="Glob pattern over strategies/<name>/, e.g. 'crypto_1h_weekly_meanrev_*'")
    ap.add_argument("--strategies", nargs="+",
                    help="Explicit list of strategy ids")

    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--skip-backtest", action="store_true",
                    help="Assume report.json already exists for each strategy")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    strategies = resolve_strategies(args.strategies_pattern, args.strategies)
    if not strategies:
        print("No strategies to process.", file=sys.stderr)
        sys.exit(2)
    print(f"Processing {len(strategies)} strategies: {strategies}")

    brief_path = out_dir / "signal_brief_v2.json"

    # Phase 1: always (discovery is cheap + idempotent)
    phase1_discover(args.market, args.symbols, args.is_start, args.is_end, brief_path)

    # Phase 2.5: re-run backtest unless --skip-backtest
    if not args.skip_backtest:
        phase25_backtest(strategies, args.market)

    # Phase 3: validate
    phase3_validate(strategies, args.oos_start, args.oos_end)

    # Phase 3.5: BH benchmark
    phase35_benchmark(strategies, out_dir)

    # Phase 4: feedback
    phase4_feedback(strategies)

    # Final summary
    print("\n═══════ FINAL SUMMARY ═══════")
    summary = {"pipeline_run": datetime.utcnow().isoformat() + "Z",
               "market": args.market, "symbols": args.symbols,
               "is": [args.is_start, args.is_end],
               "oos": [args.oos_start, args.oos_end],
               "strategies": [], "pass_count": 0}
    for sid in strategies:
        d = REPO / "strategies" / sid
        v = json.loads((d / "validation.json").read_text()) if (d / "validation.json").exists() else {}
        fb = json.loads((d / "feedback_auto.json").read_text()) if (d / "feedback_auto.json").exists() else {}
        rec = {
            "id": sid,
            "passed": v.get("passed", False),
            "ir_full": fb.get("backtest", {}).get("information_ratio"),
            "ir_oos": (v.get("oos_result") or {}).get("information_ratio"),
        }
        summary["strategies"].append(rec)
        if rec["passed"]:
            summary["pass_count"] += 1
        mark = "✓" if rec["passed"] else "✗"
        print(f"  {mark} {sid:<48}  IR_full={rec['ir_full']}  IR_oos={rec['ir_oos']}")
    print(f"\n{summary['pass_count']}/{len(strategies)} strategies passed all 4 gates.")

    (out_dir / "pipeline_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    try:
        rel = out_dir.resolve().relative_to(REPO)
        print(f"\nartifacts → {rel}/")
    except ValueError:
        print(f"\nartifacts → {out_dir.resolve()}/")


if __name__ == "__main__":
    main()
