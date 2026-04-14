#!/usr/bin/env python3
"""Summarize strategies/ with key report metrics as JSON.

Output is sorted by `--sort-by` (default: return_pct) descending.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRATS = ROOT / "strategies"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--sort-by", default="return_pct")
    args = ap.parse_args()

    rows = []
    if STRATS.exists():
        for d in sorted(STRATS.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            rp = d / "report.json"
            if not rp.exists():
                rows.append({"id": d.name, "status": "pending"})
                continue
            try:
                r = json.loads(rp.read_text())
            except Exception:
                rows.append({"id": d.name, "status": "corrupt"})
                continue
            rows.append(
                {
                    "id": d.name,
                    "return_pct": r.get("return_pct"),
                    "n_trades": r.get("n_trades"),
                    "total_fees": r.get("total_fees"),
                    "total_pnl": r.get("total_pnl"),
                }
            )
    rows.sort(key=lambda r: (r.get(args.sort_by) is None, -(r.get(args.sort_by) or 0)))
    print(json.dumps(rows[:args.limit], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
