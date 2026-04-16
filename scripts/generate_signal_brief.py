#!/usr/bin/env python3
"""Signal brief generator.

Runs signal_research + optimal_params on a symbol's feature data and emits
a compact JSON brief that agents consume as a data-driven signal shortlist.

Usage:
    python scripts/generate_signal_brief.py \
        --symbol BTC \
        --features-dir data/signal_research/crypto \
        --fee 4.0 \
        --out-dir data/signal_briefs
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.optimal_params import (
    analyze_signal_at_threshold,
    load_features,
)


_KST = timezone(timedelta(hours=9))


def generate_brief(
    symbol: str,
    features_dir: str,
    fee_bps: float,
    top_n: int = 10,
    max_rows: int | None = 100_000,
) -> dict:
    """Build a compact signal brief for agent consumption.

    When the feature dataset has > max_rows rows, a uniform random sample is
    used for the PT/SL sweep. This keeps the sweep runtime bounded while
    preserving statistical validity (edge detection is insensitive to row
    count beyond a few tens of thousands).
    """
    df = load_features(symbol, outdir=features_dir)
    n_full = len(df)
    if max_rows is not None and n_full > max_rows:
        df = df.sample(n=max_rows, random_state=0).reset_index(drop=True)

    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]
    feature_cols = [
        c for c in df.columns
        if c not in fwd_cols + ["ts_ns", "mid", "date"]
        and not c.startswith("fwd_")
    ]

    # Sweep: per signal × threshold percentile × horizon
    candidates = []
    percentiles = [70, 80, 90, 95]
    for signal in feature_cols:
        vals = df[signal].dropna()
        if len(vals) == 0 or vals.std() == 0:
            continue
        for pct in percentiles:
            thr = float(np.percentile(vals, pct))
            for fwd_col in fwd_cols:
                result = analyze_signal_at_threshold(df, signal, thr, fwd_col, fee_bps)
                if "error" in result:
                    continue
                candidates.append({
                    "signal": signal,
                    "threshold": thr,
                    "threshold_percentile": pct,
                    "horizon": int(fwd_col.replace("fwd_", "").replace("t_bps", "")),
                    "entry_pct": result.get("entry_pct", 0),
                    "cond_mean_bps": result.get("cond_mean_bps", 0),
                    "cond_std_bps": result.get("cond_std_bps", 0),
                    "ev_bps": result.get("ev_bps", -999),
                    "sharpe": result.get("sharpe", 0),
                    "win_rate_pct": round(result.get("win_rate", 0) * 100, 2),
                    "pt_bps": result.get("pt_bps", 0),
                    "sl_bps": result.get("sl_bps", 0),
                    "pct_pt": result.get("pct_pt", 0),
                    "pct_sl": result.get("pct_sl", 0),
                    "pct_ts": result.get("pct_ts", 0),
                    "n_entry": result.get("n_entry", 0),
                    "viable": result.get("ev_bps", -999) > 0,
                })

    # Rank by Sharpe descending
    candidates.sort(key=lambda x: x["sharpe"], reverse=True)

    top = candidates[:top_n]
    top_signals = []
    for i, c in enumerate(top):
        top_signals.append({
            "rank": i + 1,
            "signal": c["signal"],
            "threshold": round(c["threshold"], 6),
            "threshold_percentile": c["threshold_percentile"],
            "horizon": c["horizon"],
            "entry_pct": round(c["entry_pct"], 2),
            "ic_bps_edge": round(c["cond_mean_bps"], 3),
            "q5_mean_bps": round(c["cond_mean_bps"], 3),
            "ev_bps": round(c["ev_bps"], 3),
            "viable": bool(c["viable"]),
            "optimal_exit": {
                "pt_bps": int(c["pt_bps"]),
                "sl_bps": int(c["sl_bps"]),
                "sharpe": round(c["sharpe"], 4),
                "win_rate_pct": c["win_rate_pct"],
                "exit_mix": {
                    "pt": int(c["pct_pt"]),
                    "sl": int(c["pct_sl"]),
                    "ts": int(c["pct_ts"]),
                },
            },
            "n_entry": c["n_entry"],
        })

    n_viable = sum(1 for s in top_signals if s["viable"])
    if n_viable == 0:
        recommendation = (
            f"No viable signal at fee={fee_bps} bps. "
            f"All {len(top_signals)} candidates have EV < 0 after fees. "
            f"Consider lower-fee market or fundamentally different signal family."
        )
    elif n_viable <= 3:
        recommendation = (
            f"{n_viable} viable signals found. Use rank-1 signal as primary; "
            f"rank-2 as secondary hypothesis if rank-1 fails."
        )
    else:
        recommendation = (
            f"{n_viable} viable signals. Rank-1 ({top_signals[0]['signal']}) has "
            f"highest Sharpe; alternatives diversify signal family risk."
        )

    brief = {
        "symbol": symbol,
        "generated_at": datetime.now(tz=_KST).isoformat(),
        "fee_bps": fee_bps,
        "n_ticks_analyzed": len(df),
        "n_ticks_full": n_full,
        "features_source": f"{features_dir}/{symbol}_features.csv",
        "top_signals": top_signals,
        "n_viable_in_top": n_viable,
        "recommendation": recommendation,
        "usage_protocol": (
            "alpha-designer: pick a signal from top_signals[0..9]; cite the rank. "
            "execution-designer: adopt optimal_exit.pt_bps/sl_bps as baseline PT/SL, "
            "only deviate if you have a concrete reason (document the deviation)."
        ),
    }
    return brief


def main():
    ap = argparse.ArgumentParser(description="Signal brief generator")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--features-dir", default="data/signal_research")
    ap.add_argument("--fee", type=float, default=21.0, help="Round-trip fee in bps")
    ap.add_argument("--out-dir", default="data/signal_briefs")
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument(
        "--max-rows",
        type=int,
        default=100_000,
        help="Cap rows used for PT/SL sweep (subsample if features CSV is larger). "
             "Pass 0 to use full dataset.",
    )
    args = ap.parse_args()

    max_rows = args.max_rows if args.max_rows > 0 else None
    try:
        brief = generate_brief(
            symbol=args.symbol,
            features_dir=args.features_dir,
            fee_bps=args.fee,
            top_n=args.top_n,
            max_rows=max_rows,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out_dir) / f"{args.symbol}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, indent=2))
    print(f"Wrote {out_path}")
    print(f"Top signal: {brief['top_signals'][0]['signal']} "
          f"(rank 1, Sharpe={brief['top_signals'][0]['optimal_exit']['sharpe']:.3f}, "
          f"viable={brief['top_signals'][0]['viable']})")
    print(f"Viable in top-{args.top_n}: {brief['n_viable_in_top']}")


if __name__ == "__main__":
    main()
