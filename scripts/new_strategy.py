#!/usr/bin/env python3
"""Create a new strategy directory with a spec.yaml from a template.

Usage:
    python scripts/new_strategy.py --name obi_momentum
    python scripts/new_strategy.py --name my_idea --from strategies/_examples/obi_momentum.yaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRATS = ROOT / "strategies"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_") or "strat"


def next_id(slug: str) -> str:
    today = dt.date.today().strftime("%Y%m%d")
    existing = [p.name for p in STRATS.glob(f"strat_{today}_*")]
    n = len(existing) + 1
    return f"strat_{today}_{n:04d}_{slug}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--from", dest="template", default=None)
    args = ap.parse_args()

    sid = next_id(slugify(args.name))
    d = STRATS / sid
    d.mkdir(parents=True, exist_ok=False)
    if args.template:
        src = Path(args.template)
        if not src.is_absolute():
            src = ROOT / src
        (d / "spec.yaml").write_text(src.read_text())
    else:
        (d / "spec.yaml").write_text(
            f"name: {sid}\n"
            f"description: \"\"\n"
            f"capital: 10000000\n"
            f"universe:\n"
            f"  symbols: [\"005930\"]\n"
            f"  dates: [\"20260313\"]\n"
            f"fees: {{commission_bps: 1.5, tax_bps: 18.0}}\n"
            f"latency: {{submit_ms: 5.0, jitter_ms: 1.0, seed: 42}}\n"
            f"signals: {{}}\n"
            f"entry: {{when: false, size: 1}}\n"
            f"exit: {{when: false}}\n"
            f"risk: {{max_position_per_symbol: 1}}\n"
        )
    print(sid)


if __name__ == "__main__":
    main()
