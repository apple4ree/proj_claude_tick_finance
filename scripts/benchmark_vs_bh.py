#!/usr/bin/env python3
"""Period-matched buy-and-hold benchmarking.

For each strategy's report.json, compute BH over the strategy's exact date
range and horizon, report strategy ret vs BH ret, diff, and whether
strategy beat BH on absolute return. Optionally filter which strategies to
include.

Usage:
    # benchmark every strategy under strategies/
    python scripts/benchmark_vs_bh.py --all --out docs/bh_benchmark.json

    # one strategy
    python scripts/benchmark_vs_bh.py --id crypto_1h_weekly_meanrev_btc

    # filter (wildcards)
    python scripts/benchmark_vs_bh.py --pattern 'crypto_1h_*' --out /tmp/bh.json
"""
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent

HORIZON_PATH = {
    "1d":    "data/binance_daily/{sym}.csv",
    "daily": "data/binance_daily/{sym}.csv",
    "1h":    "data/binance_multi/1h/{sym}.csv",
    "15m":   "data/binance_multi/15m/{sym}.csv",
    "5m":    "data/binance_multi/5m/{sym}.csv",
    "1m":    "data/binance_multi/1m/{sym}.csv",
}


def bh_matched(symbol: str, horizon: str,
               start_date: str, end_date: str,
               fee_side_bps: float = 5.0) -> float | None:
    tmpl = HORIZON_PATH.get(horizon)
    if not tmpl:
        return None
    path = REPO / tmpl.format(sym=symbol)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["date"] = df["ts"].dt.strftime("%Y-%m-%d")
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].reset_index(drop=True)
    if len(df) < 2:
        return None
    ret = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
    # single entry fee (BH only pays once on entry)
    ret -= fee_side_bps / 1e4 * 100
    return float(ret)


def benchmark_one(strat_dir: Path) -> dict | None:
    rp = strat_dir / "report.json"
    sp = strat_dir / "spec.yaml"
    if not (rp.exists() and sp.exists()):
        return None
    r = json.loads(rp.read_text())
    spec = yaml.safe_load(sp.read_text())
    symbol = spec.get("target_symbol") or (
        r.get("symbols", ["?"])[0] if r.get("symbols") else "?"
    )
    horizon = spec.get("target_horizon", "tick")
    dates = r.get("dates", [])
    bh = None
    if len(dates) == 2 and horizon in HORIZON_PATH:
        bh = bh_matched(symbol, horizon, dates[0], dates[1])
    diff = None if bh is None else r.get("return_pct", 0.0) - bh
    return {
        "id": strat_dir.name,
        "symbol": symbol,
        "horizon": horizon,
        "dates": dates,
        "strategy_return_pct": r.get("return_pct"),
        "strategy_sharpe": r.get("sharpe_annualized"),
        "strategy_mdd_pct": r.get("mdd_pct"),
        "information_ratio": r.get("information_ratio"),
        "bh_return_pct": bh,
        "diff_pct": diff,
        "beats_bh_absolute": None if bh is None else bool(r.get("return_pct", 0.0) > bh),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--id")
    group.add_argument("--pattern")
    ap.add_argument("--out", default="docs/bh_benchmark.json")
    args = ap.parse_args()

    strategies_dir = REPO / "strategies"
    if args.id:
        targets = [strategies_dir / args.id]
    elif args.pattern:
        targets = [d for d in sorted(strategies_dir.iterdir())
                   if d.is_dir() and fnmatch.fnmatch(d.name, args.pattern)]
    else:
        targets = [d for d in sorted(strategies_dir.iterdir())
                   if d.is_dir() and not d.name.startswith("_")]

    rows = []
    for d in targets:
        res = benchmark_one(d)
        if res is None:
            continue
        rows.append(res)
        # terse per-row report
        bh_str = "—" if res["bh_return_pct"] is None else f"{res['bh_return_pct']:+7.2f}%"
        ret = res["strategy_return_pct"] or 0.0
        beats = "★" if res["beats_bh_absolute"] else (" " if res["bh_return_pct"] is not None else "·")
        print(f"  {beats} {res['id']:<48} ret={ret:+8.2f}%  BH={bh_str}  "
              f"IR={res['information_ratio']:+.2f}")

    cmp_rows = [r for r in rows if r["beats_bh_absolute"] is not None]
    beats = [r for r in cmp_rows if r["beats_bh_absolute"]]
    pos_ir = sum(1 for r in cmp_rows if (r["information_ratio"] or 0) > 0)

    payload = {
        "strategies": rows,
        "summary": {
            "total": len(rows),
            "comparable": len(cmp_rows),
            "beat_bh_absolute": len(beats),
            "positive_ir_vs_bh": pos_ir,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nsummary: beat_BH {len(beats)}/{len(cmp_rows)}  |  positive_IR {pos_ir}/{len(cmp_rows)}")
    print(f"saved → {out}")


if __name__ == "__main__":
    main()
