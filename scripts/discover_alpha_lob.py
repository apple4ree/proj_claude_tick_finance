#!/usr/bin/env python3
"""Phase 1 (LOB variant) — Alpha discovery on Binance L2 order-book snapshots.

Parallel to scripts/discover_alpha.py but operates on tick-level LOB data.

Differences from the bar variant:
    * Features are LOB primitives (OBI, microprice, total imbalance, OFI, depth
      slope) computed per snapshot — not OHLCV rollups.
    * Forward returns use mid-price moves over tick-count horizons (e.g., 10,
      100, 1000 ticks ≈ 1s, 10s, 100s at 100ms cadence), not bar closes.
    * Default fee assumption is 0 bps (maker) since MM / spread-capture
      paradigms on LOB are passive. Override with --fee-bps for taker
      scenarios.

The emitted JSON brief conforms to signal_briefs_v2 schema so that
/experiment's Phase 2 (alpha-designer) can consume it identically.

Usage:
    python scripts/discover_alpha_lob.py \\
        --symbols BTCUSDT,ETHUSDT,SOLUSDT \\
        --is-start '2026-04-19T06:00:00' --is-end '2026-04-19T22:00:00' \\
        --horizons-ticks 10,100,1000,10000 \\
        --fee-bps 0 \\
        --threshold-percentile 90 \\
        --output data/signal_briefs_v2/crypto_lob.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

LOB_ROOT = Path("data/binance_lob")
MARKET = "crypto_lob"


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def _ts_parse(s: str) -> int:
    """Accept '2026-04-19T06:00:00' or '2026-04-19 06:00' etc. UTC assumed."""
    return int(pd.Timestamp(s, tz="UTC").value)


def load_lob_is(symbol: str, start_ns: int, end_ns: int) -> pd.DataFrame:
    """Load all parquet partitions for `symbol` and filter ts_ns window.

    Returns columns subset (top-10 levels + totals) sorted by ts_ns.
    """
    sym_dir = LOB_ROOT / symbol
    if not sym_dir.exists():
        raise FileNotFoundError(f"LOB data missing for {symbol} at {sym_dir}")
    files = sorted(sym_dir.glob("*/*.parquet"))
    if not files:
        raise FileNotFoundError(f"no parquet under {sym_dir}")

    # Top-10 levels only (CRYPTO_LEVELS=10); drop levels 10-19 + unused totals
    keep_cols = ["ts_ns"]
    for side in ("ask", "bid"):
        for lvl in range(10):
            keep_cols += [f"{side}_px_{lvl}", f"{side}_qty_{lvl}"]
    keep_cols += ["total_ask_qty", "total_bid_qty"]

    parts = []
    for f in files:
        # Cheap filter: read only ts_ns first to check range overlap
        meta = pd.read_parquet(f, columns=["ts_ns"])
        if len(meta) == 0:
            continue
        fmin, fmax = int(meta["ts_ns"].iloc[0]), int(meta["ts_ns"].iloc[-1])
        if fmax < start_ns or fmin > end_ns:
            continue
        df = pd.read_parquet(f, columns=keep_cols)
        parts.append(df)

    if not parts:
        return pd.DataFrame(columns=keep_cols)
    df = pd.concat(parts, ignore_index=True)
    df = df[(df["ts_ns"] >= start_ns) & (df["ts_ns"] <= end_ns)]
    df = df.sort_values("ts_ns").reset_index(drop=True)
    return df


# --------------------------------------------------------------------------- #
# Feature engineering (LOB primitives)
# --------------------------------------------------------------------------- #

def _ewm_mean(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def build_lob_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ~11 LOB-native features per snapshot."""
    feat = pd.DataFrame(index=df.index)

    ask0 = df["ask_px_0"].values
    bid0 = df["bid_px_0"].values
    aqty0 = df["ask_qty_0"].values
    bqty0 = df["bid_qty_0"].values

    mid = (ask0 + bid0) / 2.0
    spread = ask0 - bid0
    feat["spread_bps"] = np.where(mid > 0, spread / mid * 1e4, 0.0)

    # OBI(1): best-level only
    denom_1 = bqty0 + aqty0
    feat["obi_1"] = np.where(denom_1 > 0, (bqty0 - aqty0) / denom_1, 0.0)

    # OBI(5), OBI(10): cumulative depth
    for depth in (5, 10):
        ask_sum = np.zeros(len(df))
        bid_sum = np.zeros(len(df))
        for lvl in range(depth):
            ask_sum = ask_sum + df[f"ask_qty_{lvl}"].values
            bid_sum = bid_sum + df[f"bid_qty_{lvl}"].values
        denom = bid_sum + ask_sum
        feat[f"obi_{depth}"] = np.where(denom > 0, (bid_sum - ask_sum) / denom, 0.0)

    # Microprice (L1-weighted) and its deviation from mid (bps)
    microprice = np.where(
        denom_1 > 0,
        (ask0 * bqty0 + bid0 * aqty0) / denom_1,
        mid,
    )
    feat["microprice_diff_bps"] = np.where(mid > 0, (microprice - mid) / mid * 1e4, 0.0)

    # Total imbalance (full book — sum across 10 kept levels via the
    # parquet's precomputed totals across all 20, but we only loaded 10).
    # We re-sum from the loaded levels to be consistent with CRYPTO_LEVELS.
    t_ask = sum(df[f"ask_qty_{l}"].values for l in range(10))
    t_bid = sum(df[f"bid_qty_{l}"].values for l in range(10))
    t_den = t_bid + t_ask
    feat["total_imbalance"] = np.where(t_den > 0, (t_bid - t_ask) / t_den, 0.0)

    # Depth slope: how fast does cumulative qty grow moving away from best.
    # Positive slope = bid side builds faster (absorption on buy side).
    bid_sum_5 = sum(df[f"bid_qty_{l}"].values for l in range(5))
    ask_sum_5 = sum(df[f"ask_qty_{l}"].values for l in range(5))
    eps = 1e-12
    feat["depth_slope_5"] = (bid_sum_5 / (bqty0 + eps)) - (ask_sum_5 / (aqty0 + eps))

    # Rolling / dynamic features (tick-count based)
    obi5 = pd.Series(feat["obi_5"].values)
    feat["obi_5_ewm_10"] = _ewm_mean(obi5, span=10).values
    feat["obi_5_ewm_100"] = _ewm_mean(obi5, span=100).values

    # Order flow imbalance (Cont-Kukanov 2014) — tick-level price+qty deltas
    # OFI(t) = Δbid_qty0·I(bid_px0 ↑) − Δask_qty0·I(ask_px0 ↓)
    ask_px0 = pd.Series(ask0)
    bid_px0 = pd.Series(bid0)
    dask_qty = pd.Series(aqty0).diff().fillna(0.0).values
    dbid_qty = pd.Series(bqty0).diff().fillna(0.0).values
    bid_up = (bid_px0 >= bid_px0.shift(1)).fillna(False).astype(int).values
    ask_down = (ask_px0 <= ask_px0.shift(1)).fillna(False).astype(int).values
    ofi_raw = dbid_qty * bid_up - dask_qty * ask_down
    feat["ofi_rolling_10"] = pd.Series(ofi_raw).rolling(10, min_periods=1).sum().values
    feat["ofi_rolling_100"] = pd.Series(ofi_raw).rolling(100, min_periods=1).sum().values

    return feat


def forward_returns_lob(df: pd.DataFrame, horizons_ticks: list[int]) -> pd.DataFrame:
    """Mid-price-based forward returns in bps at given tick-count horizons."""
    mid = ((df["ask_px_0"].values + df["bid_px_0"].values) / 2.0)
    mid_s = pd.Series(mid, index=df.index)
    out = pd.DataFrame(index=df.index)
    for H in horizons_ticks:
        fwd = (mid_s.shift(-H) - mid_s) / mid_s * 1e4
        out[f"fwd_{H}t"] = fwd
    return out


# --------------------------------------------------------------------------- #
# IC + ranking
# --------------------------------------------------------------------------- #

def compute_ic_matrix_lob(symbols: list[str], start_ns: int, end_ns: int,
                          horizons_ticks: list[int]) -> pd.DataFrame:
    rows = []
    for sym in symbols:
        print(f"  loading {sym} ...", flush=True)
        df = load_lob_is(sym, start_ns, end_ns)
        if df.empty:
            print(f"    WARN: {sym} has no snapshots in window")
            continue
        print(f"    {len(df):,} snapshots", flush=True)
        feat = build_lob_features(df)
        fwd = forward_returns_lob(df, horizons_ticks)
        for fn in feat.columns:
            for hn in fwd.columns:
                a = feat[fn].replace([np.inf, -np.inf], np.nan)
                b = fwd[hn]
                mask = a.notna() & b.notna()
                if mask.sum() < 1000:
                    continue
                ic = float(np.corrcoef(a[mask], b[mask])[0, 1])
                if np.isnan(ic):
                    continue
                rows.append({
                    "symbol": sym, "feature": fn, "horizon": hn,
                    "ic": ic, "n": int(mask.sum()),
                })
    return pd.DataFrame(rows)


def rank_signals_lob(ic_df: pd.DataFrame, symbols: list[str],
                     robustness_min_abs_ic: float = 0.02,
                     same_sign_frac: float = 1.0) -> pd.DataFrame:
    """LOB signals are weaker per-tick than bar IC; default threshold 0.02 (vs 0.04 for bars)."""
    pv = ic_df.pivot_table(index=["feature", "horizon"], columns="symbol",
                           values="ic").reset_index()
    missing = [s for s in symbols if s not in pv.columns]
    if missing:
        raise ValueError(f"missing symbols in pivot: {missing}")
    pv["ic_avg"] = pv[symbols].mean(axis=1)
    pv["ic_min_abs"] = pv[symbols].abs().min(axis=1)
    signs = np.sign(pv[symbols].values)
    maj_sign = np.sign(pv["ic_avg"]).values[:, None]
    agree = (signs == maj_sign).sum(axis=1) / len(symbols)
    pv["same_sign_frac"] = agree
    pv["same_sign"] = (agree >= same_sign_frac)
    pv["robust"] = pv["same_sign"] & (pv["ic_min_abs"] >= robustness_min_abs_ic)
    pv["abs_avg_ic"] = pv["ic_avg"].abs()
    return pv.sort_values("abs_avg_ic", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Per-signal calibration
# --------------------------------------------------------------------------- #

def calibrate_signal_lob(symbols: list[str], start_ns: int, end_ns: int,
                         feature: str, horizon: str, avg_ic: float,
                         percentile: int, fee_bps: float) -> dict:
    """For one (feature, horizon), compute per-symbol threshold + entry stats + optimal_exit.

    direction is always LONG (framework constraint). Sign of avg_ic determines entry_side.
    PT = p75 of winners, SL = |p25| of losers, both in bps.
    """
    import re
    m = re.match(r"fwd_(\d+)t", horizon)
    horizon_ticks = int(m.group(1)) if m else 0

    direction_side = "high" if avg_ic > 0 else "low"
    per_symbol_threshold: dict[str, float] = {}
    per_symbol_stats: dict[str, dict] = {}
    all_fwd_bps: list[float] = []

    for sym in symbols:
        df = load_lob_is(sym, start_ns, end_ns)
        if df.empty:
            continue
        feat_all = build_lob_features(df)
        if feature not in feat_all.columns:
            continue
        fwd_all = forward_returns_lob(df, [horizon_ticks])
        fwd_col = f"fwd_{horizon_ticks}t"
        if fwd_col not in fwd_all.columns:
            continue
        a = feat_all[feature].replace([np.inf, -np.inf], np.nan)
        b = fwd_all[fwd_col]
        mask = a.notna() & b.notna()
        if mask.sum() < 500:
            continue
        aa = a[mask].values
        bb = b[mask].values

        pct = percentile if direction_side == "high" else (100 - percentile)
        thr = float(np.percentile(aa, pct))
        trigger = (aa >= thr) if direction_side == "high" else (aa <= thr)
        if trigger.sum() < 50:
            continue

        fwd_bps = bb[trigger]  # already in bps
        per_symbol_threshold[sym] = round(thr, 6)
        per_symbol_stats[sym] = {
            "n_entry": int(trigger.sum()),
            "entry_pct": round(100.0 * trigger.sum() / len(aa), 2),
            "mean_fwd_bps": round(float(fwd_bps.mean()), 2),
            "std_fwd_bps": round(float(fwd_bps.std()), 2),
            "win_rate_pct": round(100.0 * (fwd_bps > 0).mean(), 2),
        }
        all_fwd_bps.extend(fwd_bps.tolist())

    if not all_fwd_bps:
        return {
            "direction": "long",
            "entry_side": direction_side,
            "threshold_percentile": percentile,
            "threshold_per_symbol": {},
            "entry_stats_per_symbol": {},
            "optimal_exit": None,
            "ev_bps_after_fee": None,
            "viable": False,
            "fee_bps_used": fee_bps,
            "calibration_note": "no symbol yielded sufficient entry snapshots",
        }

    arr = np.array(all_fwd_bps)
    pt_bps = round(float(np.percentile(arr[arr > 0], 75)) if (arr > 0).any() else 0.0, 2)
    sl_bps = round(float(abs(np.percentile(arr[arr < 0], 25))) if (arr < 0).any() else 0.0, 2)
    mean_bps = float(arr.mean())
    ev_bps_after_fee = round(mean_bps - fee_bps, 2)

    return {
        "direction": "long",
        "entry_side": direction_side,
        "threshold_percentile": percentile,
        "threshold_per_symbol": per_symbol_threshold,
        "entry_stats_per_symbol": per_symbol_stats,
        "optimal_exit": {
            "pt_bps": pt_bps,
            "sl_bps": sl_bps,
            "horizon_ticks": horizon_ticks,
            "win_rate_pct": round(100.0 * (arr > 0).mean(), 2),
            "mean_fwd_bps": round(mean_bps, 2),
            "note": "terminal-return approximation over tick horizon; no intra-horizon path simulation. "
                    "Units: ticks (100ms cadence for BTC/ETH/SOL).",
        },
        "ev_bps_after_fee": ev_bps_after_fee,
        "viable": ev_bps_after_fee > 0,
        "fee_bps_used": fee_bps,
    }


def build_brief_lob(ranked: pd.DataFrame, symbols: list[str],
                    start_ns: int, end_ns: int, top_k: int,
                    fee_bps: float, threshold_percentile: int,
                    is_start_iso: str, is_end_iso: str,
                    robust_min_abs_ic: float) -> dict:
    top_robust = ranked[ranked["robust"]].head(top_k)
    top_overall = ranked.head(top_k)

    top_robust_out = []
    for _, r in top_robust.iterrows():
        entry = {
            "feature": r["feature"],
            "horizon": r["horizon"],
            "avg_ic": round(r["ic_avg"], 4),
            "min_abs_ic": round(r["ic_min_abs"], 4),
            "per_symbol_ic": {s: round(r[s], 4) for s in symbols},
        }
        entry.update(calibrate_signal_lob(
            symbols, start_ns, end_ns,
            r["feature"], r["horizon"], r["ic_avg"],
            threshold_percentile, fee_bps,
        ))
        top_robust_out.append(entry)

    return {
        "market": MARKET,
        "symbols": symbols,
        "is_period": {
            "start": is_start_iso,
            "end": is_end_iso,
            "start_ns": start_ns,
            "end_ns": end_ns,
        },
        "fee_bps": fee_bps,
        "threshold_percentile": threshold_percentile,
        "robustness": {
            "min_abs_ic": robust_min_abs_ic,
            "criterion": "same sign across all symbols AND min |IC| >= threshold",
        },
        "top_robust": top_robust_out,
        "top_overall_any_sign": [
            {
                "feature": r["feature"],
                "horizon": r["horizon"],
                "avg_ic": round(r["ic_avg"], 4),
                "same_sign": bool(r["same_sign"]),
                "per_symbol_ic": {s: round(r[s], 4) for s in symbols},
            }
            for _, r in top_overall.iterrows()
        ],
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True,
                    help="Comma-separated, e.g. BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--is-start", required=True,
                    help="ISO datetime (UTC), e.g. 2026-04-19T06:00:00")
    ap.add_argument("--is-end", required=True,
                    help="ISO datetime (UTC), e.g. 2026-04-19T22:00:00")
    ap.add_argument("--horizons-ticks", default="10,100,1000,10000",
                    help="Comma-separated forward-return horizons in ticks "
                         "(1 tick ≈ 100ms). Default 10,100,1000,10000 = 1s/10s/100s/1000s")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--fee-bps", type=float, default=0.0,
                    help="Round-trip fee assumption in bps. Default 0 (maker). "
                         "Use 4 for taker scenarios.")
    ap.add_argument("--threshold-percentile", type=int, default=90)
    ap.add_argument("--same-sign-frac", type=float, default=1.0)
    ap.add_argument("--robust-min-abs-ic", type=float, default=0.02,
                    help="LOB per-tick IC is typically smaller than bar IC; "
                         "default 0.02 (vs 0.04 for bar markets).")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    horizons = [int(x) for x in args.horizons_ticks.split(",")]
    start_ns = _ts_parse(args.is_start)
    end_ns = _ts_parse(args.is_end)
    if start_ns >= end_ns:
        raise SystemExit("is-start must be strictly before is-end")

    hours = (end_ns - start_ns) / 1e9 / 3600
    print(f"[Phase 1 LOB] {MARKET} symbols={symbols} window={hours:.2f}h "
          f"horizons={horizons} fee={args.fee_bps} bps")

    ic_df = compute_ic_matrix_lob(symbols, start_ns, end_ns, horizons)
    if ic_df.empty:
        raise SystemExit("IC matrix empty — check that LOB data exists in the window.")

    ranked = rank_signals_lob(
        ic_df, symbols,
        robustness_min_abs_ic=args.robust_min_abs_ic,
        same_sign_frac=args.same_sign_frac,
    )
    brief = build_brief_lob(
        ranked, symbols, start_ns, end_ns,
        top_k=args.top_k,
        fee_bps=args.fee_bps,
        threshold_percentile=args.threshold_percentile,
        is_start_iso=args.is_start,
        is_end_iso=args.is_end,
        robust_min_abs_ic=args.robust_min_abs_ic,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, indent=2))
    print(f"[Phase 1 LOB] wrote {out_path}")
    print(f"  top_robust: {len(brief['top_robust'])} entries "
          f"({sum(1 for e in brief['top_robust'] if e.get('viable')) } viable)")
    if brief["top_robust"]:
        for i, e in enumerate(brief["top_robust"][:5]):
            v = "VIABLE" if e.get("viable") else "unviable"
            print(f"  #{i} {e['feature']} × {e['horizon']}  "
                  f"avg_ic={e['avg_ic']:+.4f}  ev_after_fee={e.get('ev_bps_after_fee')} bps  [{v}]")


if __name__ == "__main__":
    main()
