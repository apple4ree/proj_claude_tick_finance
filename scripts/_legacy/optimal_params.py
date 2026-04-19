#!/usr/bin/env python3
"""Mathematical Parameter Optimizer — TiMi-inspired closed-form optimization.

Given signal→forward-return distributions from signal_research.py,
computes optimal trading parameters WITHOUT running any backtests.

Approach:
  1. Load feature+return CSV
  2. Filter to ticks where signal > threshold (entry condition)
  3. From the conditional return distribution, compute:
     - Optimal PT (profit target)
     - Optimal SL (stop loss)
     - Optimal holding horizon
     - Expected Sharpe, win rate, avg PnL
  4. Output spec-ready parameters

Usage:
    # Find optimal params for a single signal
    python scripts/optimal_params.py single \
        --symbol BTC --signal obi_1 --threshold 0.3 \
        --horizons 50,100,200 --fee 4.0

    # Sweep across all signals to find the best strategy
    python scripts/optimal_params.py sweep \
        --symbol BTC --fee 4.0

    # Generate a spec.yaml from the optimal result
    python scripts/optimal_params.py generate-spec \
        --symbol BTC --signal obi_1 --threshold 0.3 \
        --horizon 100 --pt 25 --sl 15 --fee 4.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_features(symbol: str, outdir: str = "data/signal_research") -> pd.DataFrame:
    """Load feature CSV from signal_research.py output."""
    path = Path(outdir) / f"{symbol}_features.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run signal_research.py extract first.")
    return pd.read_csv(path)


def compute_optimal_exit(
    returns: np.ndarray,
    fee_bps: float,
    pt_range: tuple = (3, 80, 1),
    sl_range: tuple = (3, 50, 1),
) -> dict:
    """Find optimal PT/SL that maximizes expected profit per trade.

    Uses empirical distribution (no normality assumption).
    For each (PT, SL) pair, simulates:
      - If return >= PT: profit = PT - fee
      - If return <= -SL: loss = -SL - fee
      - Otherwise: profit = return - fee (time-stop exit at horizon)
    """
    returns = returns[~np.isnan(returns)]
    if len(returns) < 30:
        return {"error": "insufficient data", "n": len(returns)}

    pts = np.arange(*pt_range, dtype=float)
    sls = np.arange(*sl_range, dtype=float)

    best_ev = -np.inf
    best_sharpe = -np.inf
    best_params = {}
    results_grid = []

    for pt in pts:
        for sl in sls:
            # Simulate PnL for each entry
            pnl = np.where(
                returns >= pt, pt - fee_bps,         # PT hit
                np.where(
                    returns <= -sl, -sl - fee_bps,   # SL hit
                    returns - fee_bps                # time-stop at horizon
                )
            )

            ev = pnl.mean()
            std = pnl.std()
            sharpe = ev / std if std > 0 else 0.0
            wr = (pnl > 0).mean()
            n_trades = len(pnl)

            # Win/loss breakdown
            n_pt = (returns >= pt).sum()
            n_sl = (returns <= -sl).sum()
            n_ts = n_trades - n_pt - n_sl

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = {
                    "pt_bps": float(pt),
                    "sl_bps": float(sl),
                    "ev_bps": float(ev),
                    "std_bps": float(std),
                    "sharpe": float(sharpe),
                    "win_rate": float(wr),
                    "n_pt_hits": int(n_pt),
                    "n_sl_hits": int(n_sl),
                    "n_time_stop": int(n_ts),
                    "n_trades": int(n_trades),
                    "pct_pt": float(n_pt / n_trades * 100),
                    "pct_sl": float(n_sl / n_trades * 100),
                    "pct_ts": float(n_ts / n_trades * 100),
                }

            if ev > best_ev:
                best_ev = ev

    best_params["best_ev_bps"] = float(best_ev)
    return best_params


def analyze_signal_at_threshold(
    df: pd.DataFrame,
    signal: str,
    threshold: float,
    fwd_col: str,
    fee_bps: float,
    direction: str = "long",  # "long" = signal > threshold, "short" = signal < -threshold
) -> dict:
    """Analyze a single signal at a single threshold and horizon."""
    valid = df.dropna(subset=[fwd_col])

    if direction == "long":
        mask = valid[signal] >= threshold
    else:
        mask = valid[signal] <= -threshold

    subset = valid[mask]
    n_total = len(valid)
    n_entry = len(subset)

    if n_entry < 30:
        return {
            "signal": signal,
            "threshold": threshold,
            "direction": direction,
            "horizon": fwd_col,
            "n_entry": n_entry,
            "n_total": n_total,
            "error": "insufficient entries (need >= 30)",
        }

    returns = subset[fwd_col].values
    entry_pct = n_entry / n_total * 100

    # Unconditional stats
    uncond_mean = valid[fwd_col].mean()

    # Conditional stats
    cond_mean = returns.mean()
    cond_std = returns.std()
    cond_median = np.median(returns)

    # Find optimal exit params
    optimal = compute_optimal_exit(returns, fee_bps)

    result = {
        "signal": signal,
        "threshold": threshold,
        "direction": direction,
        "horizon": fwd_col,
        "fee_bps": fee_bps,
        "n_entry": n_entry,
        "n_total": n_total,
        "entry_pct": round(entry_pct, 2),
        "uncond_mean_bps": round(uncond_mean, 3),
        "cond_mean_bps": round(cond_mean, 3),
        "cond_std_bps": round(cond_std, 3),
        "cond_median_bps": round(cond_median, 3),
        "edge_over_uncond_bps": round(cond_mean - uncond_mean, 3),
    }
    result.update(optimal)
    return result


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_single(args):
    """Optimize parameters for a single signal at a given threshold."""
    df = load_features(args.symbol, args.outdir)
    horizons = [f"fwd_{h}t_bps" for h in args.horizons.split(",")]
    fee = float(args.fee)

    print(f"Signal: {args.signal} >= {args.threshold}")
    print(f"Fee: {fee} bps RT")
    print(f"Data: {len(df)} ticks")
    print()

    for fwd_col in horizons:
        if fwd_col not in df.columns:
            print(f"  {fwd_col}: not found in data")
            continue

        result = analyze_signal_at_threshold(
            df, args.signal, float(args.threshold), fwd_col, fee
        )

        if "error" in result:
            print(f"  {fwd_col}: {result['error']} (n={result['n_entry']})")
            continue

        print(f"  ── {fwd_col} ──")
        print(f"  Entries: {result['n_entry']}/{result['n_total']} ({result['entry_pct']:.1f}%)")
        print(f"  Conditional return: {result['cond_mean_bps']:+.2f} bps "
              f"(uncond: {result['uncond_mean_bps']:+.2f}, edge: {result['edge_over_uncond_bps']:+.2f})")
        print(f"  ┌─ OPTIMAL EXIT ─────────────────────────────────┐")
        print(f"  │  PT = {result['pt_bps']:.0f} bps    SL = {result['sl_bps']:.0f} bps              │")
        print(f"  │  EV = {result['ev_bps']:+.3f} bps/trade    Sharpe = {result['sharpe']:+.4f}  │")
        print(f"  │  WR = {result['win_rate']*100:.1f}%                                │")
        print(f"  │  Exit: PT {result['pct_pt']:.0f}% / SL {result['pct_sl']:.0f}% / TimeStop {result['pct_ts']:.0f}%  │")
        viable = "YES ✓" if result['ev_bps'] > 0 else "NO ✗"
        print(f"  │  Viable after fees: {viable:>26s}  │")
        print(f"  └────────────────────────────────────────────────┘")
        print()


def cmd_sweep(args):
    """Sweep all signals × thresholds × horizons to find best strategy."""
    df = load_features(args.symbol, args.outdir)
    fee = float(args.fee)

    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]
    feature_cols = [c for c in df.columns
                    if c not in fwd_cols + ["ts_ns", "mid", "date"]
                    and not c.startswith("fwd_")]

    print(f"Sweeping {len(feature_cols)} signals × {len(fwd_cols)} horizons")
    print(f"Fee: {fee} bps RT")
    print(f"Data: {len(df)} ticks")
    print()

    all_results = []

    for signal in feature_cols:
        vals = df[signal].dropna()
        if vals.std() == 0:
            continue

        # Generate thresholds: percentiles 60, 70, 80, 90, 95
        percentiles = [60, 70, 80, 90, 95]
        thresholds = [np.percentile(vals, p) for p in percentiles]

        for thr, pct in zip(thresholds, percentiles):
            for fwd_col in fwd_cols:
                result = analyze_signal_at_threshold(df, signal, thr, fwd_col, fee)
                if "error" not in result and result.get("ev_bps", -999) > -fee:
                    result["threshold_percentile"] = pct
                    all_results.append(result)

    if not all_results:
        print("No viable strategies found!")
        return

    # Sort by Sharpe
    all_results.sort(key=lambda x: x.get("sharpe", 0), reverse=True)

    print(f"\n{'='*80}")
    print(f"  TOP 20 STRATEGIES BY SHARPE (fee={fee} bps)")
    print(f"{'='*80}")
    print(f"  {'Signal':>22s}  {'Thr':>6s}  {'Horizon':>10s}  {'PT':>4s}  {'SL':>4s}  "
          f"{'EV':>7s}  {'Sharpe':>7s}  {'WR':>5s}  {'N':>5s}  {'Viable':>6s}")
    print(f"  {'-'*22}  {'-'*6}  {'-'*10}  {'-'*4}  {'-'*4}  "
          f"{'-'*7}  {'-'*7}  {'-'*5}  {'-'*5}  {'-'*6}")

    for r in all_results[:20]:
        viable = "YES" if r["ev_bps"] > 0 else "no"
        flag = " ***" if r["ev_bps"] > 0 else ""
        print(f"  {r['signal']:>22s}  {r['threshold']:>6.3f}  {r['horizon']:>10s}  "
              f"{r['pt_bps']:>4.0f}  {r['sl_bps']:>4.0f}  "
              f"{r['ev_bps']:>+7.3f}  {r['sharpe']:>+7.4f}  "
              f"{r['win_rate']*100:>5.1f}  {r['n_entry']:>5d}  {viable:>6s}{flag}")

    # Save full results
    outpath = Path(args.outdir) / f"{args.symbol}_optimal_sweep.json"
    with open(outpath, "w") as f:
        json.dump(all_results[:100], f, indent=2)
    print(f"\nFull results saved to {outpath}")

    # Best viable strategy
    viable_results = [r for r in all_results if r["ev_bps"] > 0]
    if viable_results:
        best = viable_results[0]
        print(f"\n{'='*80}")
        print(f"  BEST VIABLE STRATEGY")
        print(f"{'='*80}")
        print(f"  Signal:    {best['signal']} >= {best['threshold']:.4f}")
        print(f"  Horizon:   {best['horizon']}")
        print(f"  PT/SL:     {best['pt_bps']:.0f} / {best['sl_bps']:.0f} bps")
        print(f"  EV:        {best['ev_bps']:+.3f} bps/trade")
        print(f"  Sharpe:    {best['sharpe']:+.4f}")
        print(f"  Win Rate:  {best['win_rate']*100:.1f}%")
        print(f"  Entries:   {best['n_entry']} ({best['entry_pct']:.1f}% of ticks)")
        print(f"  Exit mix:  PT {best['pct_pt']:.0f}% / SL {best['pct_sl']:.0f}% / TS {best['pct_ts']:.0f}%")

        # Estimate daily PnL
        daily_entries = best['n_entry'] / 8  # assume 8 days
        daily_ev = daily_entries * best['ev_bps']
        print(f"\n  Est. daily entries: {daily_entries:.0f}")
        print(f"  Est. daily EV:     {daily_ev:+.1f} bps")
    else:
        print("\n  No viable strategy found — all EV < 0 after fees.")


def cmd_generate_spec(args):
    """Generate a spec.yaml from optimal parameters."""
    print("TODO: generate spec.yaml from optimal params")
    print(f"  signal={args.signal}, threshold={args.threshold}")
    print(f"  horizon={args.horizon}, pt={args.pt}, sl={args.sl}")
    print(f"  fee={args.fee}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mathematical Parameter Optimizer")
    sub = parser.add_subparsers(dest="cmd")

    # single
    p1 = sub.add_parser("single", help="Optimize for a single signal")
    p1.add_argument("--symbol", required=True)
    p1.add_argument("--signal", required=True)
    p1.add_argument("--threshold", required=True, type=float)
    p1.add_argument("--horizons", default="50,100,200,500,1000")
    p1.add_argument("--fee", default="4.0")
    p1.add_argument("--outdir", default="data/signal_research")

    # sweep
    p2 = sub.add_parser("sweep", help="Sweep all signals to find best strategy")
    p2.add_argument("--symbol", required=True)
    p2.add_argument("--fee", default="4.0")
    p2.add_argument("--outdir", default="data/signal_research")

    # generate-spec
    p3 = sub.add_parser("generate-spec", help="Generate spec.yaml from optimal params")
    p3.add_argument("--symbol", required=True)
    p3.add_argument("--signal", required=True)
    p3.add_argument("--threshold", required=True, type=float)
    p3.add_argument("--horizon", required=True, type=int)
    p3.add_argument("--pt", required=True, type=float)
    p3.add_argument("--sl", required=True, type=float)
    p3.add_argument("--fee", default="4.0")

    args = parser.parse_args()
    if args.cmd == "single":
        cmd_single(args)
    elif args.cmd == "sweep":
        cmd_sweep(args)
    elif args.cmd == "generate-spec":
        cmd_generate_spec(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
