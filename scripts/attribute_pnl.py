#!/usr/bin/env python3
"""Counterfactual PnL attribution via dual backtest runs.

For each strategy:
  1. Run backtest in normal mode (if report.json missing)
  2. Run backtest in strict mode (if report_strict.json missing)
  3. Compute strict_pnl_clean = strict_pnl, bug_pnl = normal_pnl - strict_pnl
  4. Per-invariant impact = sum of (normal - strict) PnL attributable to each type

Usage:
  python scripts/attribute_pnl.py --strategy strat_20260415_0032_passive_maker_bid_sl_3entry_005930
  python scripts/attribute_pnl.py --all
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _run_if_missing(spec_path: Path, strict: bool) -> None:
    """Run backtest if the corresponding report is missing."""
    strategy_dir = spec_path.parent
    report_name = "report_strict.json" if strict else "report.json"
    if (strategy_dir / report_name).exists():
        return
    cmd = ["python", "-m", "engine.runner", "--spec", str(spec_path), "--summary"]
    if strict:
        cmd.append("--strict")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _load_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def attribute(strategy_dir: Path) -> dict | None:
    spec_path = strategy_dir / "spec.yaml"
    if not spec_path.exists():
        return None
    _run_if_missing(spec_path, strict=False)
    _run_if_missing(spec_path, strict=True)

    normal = _load_report(strategy_dir / "report.json") or _load_report(strategy_dir / "report_per_symbol.json")
    strict = _load_report(strategy_dir / "report_strict.json") or _load_report(strategy_dir / "report_per_symbol_strict.json")
    if normal is None or strict is None:
        return None

    # PnL extraction — handle both single-symbol and per-symbol reports
    def _total_pnl(r: dict) -> float:
        if "total_pnl" in r:
            return float(r["total_pnl"])
        # per-symbol
        return sum(float(v.get("total_pnl", 0)) for v in (r.get("per_symbol") or {}).values())

    def _return_pct(r: dict) -> float:
        if "return_pct" in r:
            return float(r["return_pct"])
        return float(r.get("avg_return_pct", 0))

    normal_pnl = _total_pnl(normal)
    strict_pnl = _total_pnl(strict)
    bug_pnl = normal_pnl - strict_pnl

    normal_viol_by_type = normal.get("invariant_violation_by_type") or {}
    strict_blocks = strict.get("rejected", {}).get("strict_invariant", 0)

    return {
        "strategy_id": strategy_dir.name,
        "normal_return_pct": _return_pct(normal),
        "strict_return_pct": _return_pct(strict),
        "normal_pnl": round(normal_pnl, 2),
        "strict_pnl_clean": round(strict_pnl, 2),
        "bug_pnl": round(bug_pnl, 2),
        "clean_pct_of_total": (
            round(strict_pnl / normal_pnl * 100, 2)
            if normal_pnl != 0 else None
        ),
        "normal_violations_by_type": normal_viol_by_type,
        "strict_blocks_total": strict_blocks,
        "interpretation": (
            "strict_pnl_clean is the return if strategy obeyed spec exactly; "
            "bug_pnl is the portion attributable to spec violations"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Counterfactual PnL attribution")
    parser.add_argument("--strategy", help="Single strategy directory name")
    parser.add_argument("--all", action="store_true", help="Attribute all strategies in strategies/")
    args = parser.parse_args()

    if args.all:
        roots = sorted(
            d for d in Path("strategies").iterdir()
            if d.is_dir() and d.name.startswith("strat_")
        )
    elif args.strategy:
        roots = [Path("strategies") / args.strategy]
    else:
        parser.print_help()
        return

    results = []
    for r in roots:
        out = attribute(r)
        if out is not None:
            results.append(out)

    # Summary table
    print(f"{'Strategy':<60s} {'Normal':>8s} {'Clean':>8s} {'Bug':>8s}  {'Clean %':>7s}  Violations")
    print("-" * 110)
    for r in sorted(results, key=lambda x: -(x["bug_pnl"] or 0)):
        viol_summary = ", ".join(f"{t}={c}" for t, c in (r["normal_violations_by_type"] or {}).items())
        clean_pct = r["clean_pct_of_total"]
        clean_pct_str = f"{clean_pct:>6.1f}%" if clean_pct is not None else "    --"
        print(f"{r['strategy_id']:<60s} {r['normal_pnl']:>+8.0f} {r['strict_pnl_clean']:>+8.0f} "
              f"{r['bug_pnl']:>+8.0f}  {clean_pct_str}  {viol_summary}")

    # Save JSON
    outpath = Path("data/attribution_summary.json")
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(results, indent=2))
    print(f"\nFull results saved to {outpath}")


if __name__ == "__main__":
    main()
