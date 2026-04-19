#!/usr/bin/env python3
"""Sweep all existing strategies and count invariant violations.

Reads report.json (or report_per_symbol.json) from each strategy directory,
aggregates invariant_violations by type, and prints a summary table.

This is the paper's central experimental data: how often each gap type
is discovered by the automated checker.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    strategies_root = Path("strategies")
    dirs = sorted(d for d in strategies_root.iterdir()
                  if d.is_dir() and d.name.startswith("strat_"))

    totals: dict[str, int] = defaultdict(int)
    per_strategy: list[dict] = []

    for d in dirs:
        rpt = d / "report.json"
        if not rpt.exists():
            rpt = d / "report_per_symbol.json"
        if not rpt.exists():
            continue
        try:
            data = json.loads(rpt.read_text())
        except Exception:
            continue

        viols = data.get("invariant_violations") or []
        by_type = defaultdict(int)
        for v in viols:
            t = v.get("invariant_type", "unknown")
            by_type[t] += 1
            totals[t] += 1

        per_strategy.append({
            "id": d.name,
            "n_violations": len(viols),
            "by_type": dict(by_type),
            "return_pct": data.get("return_pct"),
            "n_roundtrips": data.get("n_roundtrips"),
        })

    # Per-strategy ranking
    print(f"{'Strategy':<64s} {'Return':>7s} {'RT':>4s} {'Viol':>5s}  Top types")
    print("-" * 120)
    for r in sorted(per_strategy, key=lambda x: -x["n_violations"])[:40]:
        ret = r.get("return_pct")
        rt = r.get("n_roundtrips")
        ret_str = f"{ret:+6.2f}%" if ret is not None else "  --  "
        rt_str = f"{rt:>4d}" if rt is not None else "  --"
        types_str = ", ".join(f"{t}={c}" for t, c in
                              sorted(r["by_type"].items(), key=lambda x: -x[1])[:3])
        print(f"{r['id']:<64s} {ret_str:>7s} {rt_str:>4s} {r['n_violations']:>5d}  {types_str}")

    # Totals
    print("\n=== TOTALS ACROSS ALL STRATEGIES ===")
    n_strat_with_viol = sum(1 for r in per_strategy if r["n_violations"] > 0)
    print(f"Strategies with >= 1 violation: {n_strat_with_viol} / {len(per_strategy)}")
    print()
    for t, c in sorted(totals.items(), key=lambda x: -x[1]):
        n_strat = sum(1 for r in per_strategy if t in r["by_type"])
        print(f"  {t:<30s}  total={c:>4d}  affected_strategies={n_strat:>3d}")


if __name__ == "__main__":
    main()
