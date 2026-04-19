#!/usr/bin/env python3
"""Signal Research Tool — LOB feature → forward return analysis.

Computes 20+ LOB features and forward returns at every tick,
then analyzes which features predict future price movement
above the fee hurdle (19.5 bps round-trip).

Usage:
    # Step 1: Extract features + forward returns (slow, one-time)
    python scripts/signal_research.py extract --symbol 005930 --dates 20260316,20260317,...

    # Step 2: Analyze predictive power (fast, iterative)
    python scripts/signal_research.py analyze --symbol 005930

    # Step 3: Conditional return analysis for a specific signal
    python scripts/signal_research.py conditional --symbol 005930 --signal obi_10 --thresholds 0.1,0.2,0.3,0.4,0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.data_loader import iter_events, OrderBookSnapshot, set_data_root
from engine.signals import SIGNAL_REGISTRY, SymbolState, update_state

# ── Feature extractors ────────────────────────────────────────────────────

def compute_features(snap: OrderBookSnapshot, st: SymbolState) -> dict:
    """Compute all LOB features at a single tick."""
    mid = float(snap.mid)
    spread = float(snap.spread)
    spread_bps = (spread / mid * 1e4) if mid > 0 else 0.0

    bid_px = snap.bid_px.astype(np.float64)
    ask_px = snap.ask_px.astype(np.float64)
    bid_qty = snap.bid_qty.astype(np.float64)
    ask_qty = snap.ask_qty.astype(np.float64)

    total_bid = bid_qty.sum()
    total_ask = ask_qty.sum()
    total_vol = total_bid + total_ask

    # ── Imbalance features ──
    obi_1 = (bid_qty[0] - ask_qty[0]) / (bid_qty[0] + ask_qty[0]) if (bid_qty[0] + ask_qty[0]) > 0 else 0.0
    obi_3 = SIGNAL_REGISTRY["obi"](snap, st, depth=3)
    obi_5 = SIGNAL_REGISTRY["obi"](snap, st, depth=5)
    obi_10 = SIGNAL_REGISTRY["obi"](snap, st, depth=10)
    total_imbalance = SIGNAL_REGISTRY["total_imbalance"](snap, st)

    # ── Microprice features ──
    microprice = SIGNAL_REGISTRY["microprice"](snap, st)
    microprice_diff_bps = (microprice - mid) / mid * 1e4 if mid > 0 else 0.0

    # ── LOB shape features ──
    # Bid slope: how quickly bid depth decays away from best bid
    bid_cumqty = np.cumsum(bid_qty)
    ask_cumqty = np.cumsum(ask_qty)

    # Depth ratio at level 5 vs level 1
    depth_ratio_bid = bid_cumqty[4] / bid_qty[0] if bid_qty[0] > 0 else 0.0
    depth_ratio_ask = ask_cumqty[4] / ask_qty[0] if ask_qty[0] > 0 else 0.0
    depth_asymmetry = depth_ratio_bid - depth_ratio_ask

    # LOB slope: price impact per unit volume (bid side vs ask side)
    bid_range = float(bid_px[0] - bid_px[4]) if bid_px[4] > 0 else 1.0
    ask_range = float(ask_px[4] - ask_px[0]) if ask_px[4] > 0 else 1.0
    bid_slope = float(bid_cumqty[4]) / bid_range if bid_range > 0 else 0.0
    ask_slope = float(ask_cumqty[4]) / ask_range if ask_range > 0 else 0.0
    slope_diff = bid_slope - ask_slope  # positive = bid side thicker

    # Top-of-book qty ratio
    tob_ratio = float(bid_qty[0]) / float(ask_qty[0]) if ask_qty[0] > 0 else 1.0

    # ── Momentum features (require buffer history) ──
    mid_ret_10 = SIGNAL_REGISTRY["mid_return_bps"](snap, st, lookback=10)
    mid_ret_50 = SIGNAL_REGISTRY["mid_return_bps"](snap, st, lookback=50)
    mid_ret_100 = SIGNAL_REGISTRY["mid_return_bps"](snap, st, lookback=100)
    mid_ret_500 = SIGNAL_REGISTRY["mid_return_bps"](snap, st, lookback=500)

    # ── Volume features ──
    vol_delta_1 = SIGNAL_REGISTRY["volume_delta"](snap, st, lookback=1)
    vol_delta_10 = SIGNAL_REGISTRY["volume_delta"](snap, st, lookback=10)

    # ── Derived features ──
    # Weighted mid-price deviation (how far is mid from the volume-weighted fair price?)
    vwap_5 = np.sum(bid_px[:5] * bid_qty[:5] + ask_px[:5] * ask_qty[:5]) / (total_vol if total_vol > 0 else 1.0)
    vwap_diff_bps = (mid - vwap_5) / mid * 1e4 if mid > 0 else 0.0

    return {
        "ts_ns": snap.ts_ns,
        "mid": mid,
        "spread_bps": spread_bps,
        # Imbalance
        "obi_1": obi_1,
        "obi_3": obi_3,
        "obi_5": obi_5,
        "obi_10": obi_10,
        "total_imbalance": total_imbalance,
        # Microprice
        "microprice_diff_bps": microprice_diff_bps,
        # LOB shape
        "depth_asymmetry": depth_asymmetry,
        "slope_diff": slope_diff,
        "tob_ratio": tob_ratio,
        # Momentum
        "mid_ret_10": mid_ret_10,
        "mid_ret_50": mid_ret_50,
        "mid_ret_100": mid_ret_100,
        "mid_ret_500": mid_ret_500,
        # Volume
        "vol_delta_1": vol_delta_1,
        "vol_delta_10": vol_delta_10,
        # Derived
        "vwap_diff_bps": vwap_diff_bps,
    }


# ── Extract command ────────────────────────────────────────────────────────

def cmd_extract(args):
    """Extract features + forward returns for a symbol across dates."""
    symbol = args.symbol
    dates = [d.strip() for d in args.dates.split(",")]
    horizons = [int(h) for h in args.horizons.split(",")]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting features for {symbol} across {len(dates)} dates")
    print(f"Forward return horizons: {horizons} ticks")

    all_rows = []
    for date in dates:
        print(f"  Processing {date}...", end="", flush=True)
        st = SymbolState(symbol=symbol)
        day_snaps = []
        day_features = []

        reg_only = getattr(args, 'regular_only', 'true').lower() != 'false'
        for snap in iter_events(date, [symbol], regular_only=reg_only):
            update_state(st, snap)
            features = compute_features(snap, st)
            features["date"] = date
            day_snaps.append(snap)
            day_features.append(features)

        n_ticks = len(day_features)
        print(f" {n_ticks} ticks", end="")

        # Compute forward returns
        # mode=mid: mid→mid returns (signal quality; ignores spread cost)
        # mode=ask_bid: ask→bid returns (realistic taker PnL; full spread cost)
        return_mode = getattr(args, 'return_mode', 'mid')
        if return_mode == "ask_bid":
            entry_prices = np.array([float(s.ask_px[0]) for s in day_snaps])  # buy at ask
            exit_prices = np.array([float(s.bid_px[0]) for s in day_snaps])   # sell at bid
        else:
            mids = np.array([f["mid"] for f in day_features])
            entry_prices = mids
            exit_prices = mids

        for h in horizons:
            col = f"fwd_{h}t_bps"
            fwd = np.full(n_ticks, np.nan)
            if n_ticks > h:
                fwd[:n_ticks - h] = (exit_prices[h:] - entry_prices[:n_ticks - h]) / entry_prices[:n_ticks - h] * 1e4
            for i, f in enumerate(day_features):
                f[col] = fwd[i]

        all_rows.extend(day_features)
        print(f" -> {n_ticks - max(horizons) if n_ticks > max(horizons) else 0} usable rows")

    df = pd.DataFrame(all_rows)
    outpath = outdir / f"{symbol}_features.csv"
    df.to_csv(outpath, index=False)
    print(f"\nSaved {len(df)} rows to {outpath}")
    print(f"Columns: {list(df.columns)}")

    # Quick stats
    for h in horizons:
        col = f"fwd_{h}t_bps"
        valid = df[col].dropna()
        print(f"\n  fwd_{h}t_bps: mean={valid.mean():.3f}, std={valid.std():.3f}, "
              f"median={valid.median():.3f}, n={len(valid)}")


# ── Analyze command ────────────────────────────────────────────────────────

def cmd_analyze(args):
    """Analyze feature-return correlations."""
    symbol = args.symbol
    indir = Path(args.outdir)
    inpath = indir / f"{symbol}_features.csv"

    if not inpath.exists():
        print(f"ERROR: {inpath} not found. Run 'extract' first.")
        return

    df = pd.read_csv(inpath)
    print(f"Loaded {len(df)} rows for {symbol}")

    # Identify feature columns and forward return columns
    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]
    feature_cols = [c for c in df.columns if c not in fwd_cols + ["ts_ns", "mid", "date"]]

    print(f"\nFeatures ({len(feature_cols)}): {feature_cols}")
    print(f"Forward returns ({len(fwd_cols)}): {fwd_cols}")

    # Drop rows with NaN forward returns
    fee_hurdle = float(args.fee_hurdle)
    print(f"\nFee hurdle: {fee_hurdle} bps (round-trip)")

    results = []
    for fwd_col in fwd_cols:
        horizon = fwd_col.replace("fwd_", "").replace("t_bps", "")
        valid = df.dropna(subset=[fwd_col])

        print(f"\n{'='*70}")
        print(f"  HORIZON: {horizon} ticks (n={len(valid)})")
        print(f"  Unconditional mean return: {valid[fwd_col].mean():.3f} bps")
        print(f"{'='*70}")

        for feat in feature_cols:
            corr = valid[feat].corr(valid[fwd_col])
            ic = corr  # Information Coefficient = Pearson correlation

            # Rank IC (Spearman correlation)
            rank_ic = valid[feat].corr(valid[fwd_col], method="spearman")

            # Quintile analysis
            try:
                valid_sorted = valid.copy()
                valid_sorted["quintile"] = pd.qcut(valid_sorted[feat], 5, labels=False, duplicates="drop")
                q_means = valid_sorted.groupby("quintile")[fwd_col].mean()
                q_spread = q_means.iloc[-1] - q_means.iloc[0] if len(q_means) >= 2 else 0.0
                q5_mean = q_means.iloc[-1] if len(q_means) >= 1 else 0.0
            except Exception:
                q_spread = 0.0
                q5_mean = 0.0

            viable = "YES" if abs(q5_mean) > fee_hurdle else "no"
            results.append({
                "feature": feat,
                "horizon": int(horizon),
                "ic": ic,
                "rank_ic": rank_ic,
                "q5_mean_bps": q5_mean,
                "q_spread_bps": q_spread,
                "viable": viable,
            })

            flag = " ***" if abs(q5_mean) > fee_hurdle else ""
            print(f"  {feat:25s}  IC={ic:+.4f}  RankIC={rank_ic:+.4f}  "
                  f"Q5={q5_mean:+.2f}bps  Spread={q_spread:+.2f}bps  {viable}{flag}")

    # Summary: top signals by |Q5 mean|
    res_df = pd.DataFrame(results)
    res_df["abs_q5"] = res_df["q5_mean_bps"].abs()
    top = res_df.sort_values("abs_q5", ascending=False).head(20)

    print(f"\n{'='*70}")
    print(f"  TOP 20 SIGNAL-HORIZON PAIRS BY |Q5 MEAN|")
    print(f"{'='*70}")
    for _, r in top.iterrows():
        flag = " *** VIABLE" if r["viable"] == "YES" else ""
        print(f"  {r['feature']:25s} @ {r['horizon']:5d}t  "
              f"Q5={r['q5_mean_bps']:+.2f}bps  IC={r['ic']:+.4f}  "
              f"RankIC={r['rank_ic']:+.4f}{flag}")

    # Save results
    res_path = indir / f"{symbol}_analysis.json"
    res_df.to_json(res_path, orient="records", indent=2)
    print(f"\nFull results saved to {res_path}")


# ── Conditional command ────────────────────────────────────────────────────

def cmd_conditional(args):
    """Analyze conditional forward returns for a specific signal at various thresholds."""
    symbol = args.symbol
    signal = args.signal
    thresholds = [float(t) for t in args.thresholds.split(",")]
    indir = Path(args.outdir)
    inpath = indir / f"{symbol}_features.csv"

    if not inpath.exists():
        print(f"ERROR: {inpath} not found. Run 'extract' first.")
        return

    df = pd.read_csv(inpath)
    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]

    if signal not in df.columns:
        print(f"ERROR: signal '{signal}' not found. Available: {[c for c in df.columns if c not in fwd_cols + ['ts_ns', 'mid', 'date']]}")
        return

    fee_hurdle = float(args.fee_hurdle)
    print(f"Conditional analysis: {signal} on {symbol}")
    print(f"Fee hurdle: {fee_hurdle} bps")
    print(f"Signal stats: mean={df[signal].mean():.4f}, std={df[signal].std():.4f}, "
          f"min={df[signal].min():.4f}, max={df[signal].max():.4f}")

    for fwd_col in fwd_cols:
        horizon = fwd_col.replace("fwd_", "").replace("t_bps", "")
        valid = df.dropna(subset=[fwd_col])
        unconditional = valid[fwd_col].mean()

        print(f"\n  Horizon: {horizon} ticks (unconditional mean: {unconditional:+.3f} bps)")
        print(f"  {'Threshold':>12s}  {'N':>8s}  {'%ticks':>8s}  {'Mean bps':>10s}  {'Std bps':>10s}  "
              f"{'Sharpe':>8s}  {'> fee?':>8s}")
        print(f"  {'-'*12}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*8}  {'-'*8}")

        for thr in thresholds:
            mask = valid[signal] >= thr
            subset = valid.loc[mask, fwd_col]
            n = len(subset)
            pct = n / len(valid) * 100 if len(valid) > 0 else 0
            mean = subset.mean() if n > 0 else 0
            std = subset.std() if n > 1 else 0
            sharpe = mean / std if std > 0 else 0
            viable = "YES" if mean > fee_hurdle else "no"
            flag = " ***" if mean > fee_hurdle else ""
            print(f"  {thr:>12.4f}  {n:>8d}  {pct:>7.2f}%  {mean:>+10.3f}  {std:>10.3f}  "
                  f"{sharpe:>+8.4f}  {viable:>8s}{flag}")

        # Also check negative side (signal < -threshold)
        print(f"\n  Negative side (signal < -threshold):")
        print(f"  {'Threshold':>12s}  {'N':>8s}  {'%ticks':>8s}  {'Mean bps':>10s}  {'Std bps':>10s}  "
              f"{'Sharpe':>8s}  {'< -fee?':>8s}")
        print(f"  {'-'*12}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*8}  {'-'*8}")
        for thr in thresholds:
            mask = valid[signal] <= -thr
            subset = valid.loc[mask, fwd_col]
            n = len(subset)
            pct = n / len(valid) * 100 if len(valid) > 0 else 0
            mean = subset.mean() if n > 0 else 0
            std = subset.std() if n > 1 else 0
            sharpe = mean / std if std > 0 else 0
            viable = "YES" if mean < -fee_hurdle else "no"
            flag = " ***" if mean < -fee_hurdle else ""
            print(f"  {-thr:>12.4f}  {n:>8d}  {pct:>7.2f}%  {mean:>+10.3f}  {std:>10.3f}  "
                  f"{sharpe:>+8.4f}  {viable:>8s}{flag}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Signal Research Tool")
    parser.add_argument("--data-root", default=None,
                        help="Override data root directory (e.g., /home/dgu/tick/crypto for Upbit data)")
    sub = parser.add_subparsers(dest="cmd")

    # extract
    p_ext = sub.add_parser("extract", help="Extract features + forward returns")
    p_ext.add_argument("--symbol", required=True)
    p_ext.add_argument("--dates", required=True, help="Comma-separated dates")
    p_ext.add_argument("--horizons", default="50,100,200,500,1000,3000",
                       help="Comma-separated forward return horizons in ticks")
    p_ext.add_argument("--outdir", default="data/signal_research")
    p_ext.add_argument("--regular-only", default="true",
                       help="Filter to regular hours only (set 'false' for 24/7 crypto)")
    p_ext.add_argument("--return-mode", default="mid", choices=["mid", "ask_bid"],
                       help="'mid' uses mid->mid (signal quality); 'ask_bid' uses ask->bid (realistic taker PnL)")

    # analyze
    p_ana = sub.add_parser("analyze", help="Analyze feature-return correlations")
    p_ana.add_argument("--symbol", required=True)
    p_ana.add_argument("--outdir", default="data/signal_research")
    p_ana.add_argument("--fee-hurdle", default="19.5", help="Round-trip fee in bps")

    # conditional
    p_cond = sub.add_parser("conditional", help="Conditional return analysis")
    p_cond.add_argument("--symbol", required=True)
    p_cond.add_argument("--signal", required=True)
    p_cond.add_argument("--thresholds", required=True, help="Comma-separated thresholds")
    p_cond.add_argument("--outdir", default="data/signal_research")
    p_cond.add_argument("--fee-hurdle", default="19.5")

    args = parser.parse_args()

    # Apply data root override
    if args.data_root:
        set_data_root(args.data_root)

    if args.cmd == "extract":
        cmd_extract(args)
    elif args.cmd == "analyze":
        cmd_analyze(args)
    elif args.cmd == "conditional":
        cmd_conditional(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
