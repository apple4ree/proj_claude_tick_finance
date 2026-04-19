#!/usr/bin/env python3
"""Phase 1 — Raw-data alpha discovery.

Loads IS period of a market, builds a broad feature matrix from raw OHLCV
+ taker-flow columns, computes IC of every feature against forward returns
at multiple horizons for every symbol, and emits a signal_brief_v2.json
that ranks feature×horizon combos by (1) robustness (same-sign across
symbols) and (2) |avg IC|.

This is the scripted version of the inline EDA that discovered
`roc_168h → fwd_168h` weekly mean-reversion (IC −0.21).

Usage:
    python scripts/discover_alpha.py \\
        --market crypto_1h --symbols BTCUSDT,ETHUSDT,SOLUSDT \\
        --is-start 2025-07-01 --is-end 2025-10-31 \\
        --output data/signal_briefs_v2/crypto_1h.json

Markets supported:
    crypto_1d   → data/binance_daily/{SYM}.csv
    crypto_1h   → data/binance_multi/1h/{SYM}.csv
    crypto_15m  → data/binance_multi/15m/{SYM}.csv
    crypto_5m   → data/binance_multi/5m/{SYM}.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

MARKET_PATHS = {
    "crypto_1d":  "data/binance_daily/{sym}.csv",
    "crypto_1h":  "data/binance_multi/1h/{sym}.csv",
    "crypto_15m": "data/binance_multi/15m/{sym}.csv",
    "crypto_5m":  "data/binance_multi/5m/{sym}.csv",
}

MARKET_BARS_PER_YEAR = {
    "crypto_1d":  365.0,
    "crypto_1h":  24 * 365.0,
    "crypto_15m": 4 * 24 * 365.0,
    "crypto_5m":  12 * 24 * 365.0,
}


def load_is(market: str, symbol: str, is_start: str, is_end: str) -> pd.DataFrame:
    path = MARKET_PATHS[market].format(sym=symbol)
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["date"] = df["ts"].dt.strftime("%Y-%m-%d")
    df = df[(df["date"] >= is_start) & (df["date"] <= is_end)].reset_index(drop=True)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """~31 features from OHLCV + taker-buy flow."""
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    o = df["open"].values
    v = df["volume"].values
    qv = df["quote_volume"].values if "quote_volume" in df else np.zeros(len(df))
    tb = df["taker_buy_base"].values if "taker_buy_base" in df else np.zeros(len(df))
    nt = df["n_trades"].values if "n_trades" in df else np.zeros(len(df))
    cs = pd.Series(c)
    feat = pd.DataFrame(index=df.index)

    for H in [1, 3, 6, 12, 24, 48, 72, 168]:
        feat[f"roc_{H}h"] = cs.pct_change(H)
    for w in [24, 48, 72, 168]:
        m = cs.rolling(w).mean()
        s = cs.rolling(w).std()
        feat[f"zscore_{w}h"] = (cs - m) / s

    hl = pd.Series((h - l) / np.where(c > 0, c, 1))
    for w in [12, 24, 48]:
        feat[f"hl_range_mean_{w}h"] = hl.rolling(w).mean()
        feat[f"hl_range_z_{w}h"] = (hl - hl.rolling(w).mean()) / hl.rolling(w).std()

    rv = cs.pct_change().rolling(24).std()
    feat["rv_24h"] = rv
    feat["rv_z_24h"] = (rv - rv.rolling(168).mean()) / rv.rolling(168).std()

    feat["close_in_range"] = (c - l) / np.where(h - l > 0, h - l, 1)

    vs = pd.Series(v)
    qvs = pd.Series(qv)
    feat["vol_z_24h"] = (vs - vs.rolling(24).mean()) / vs.rolling(24).std()
    feat["qvol_z_24h"] = (qvs - qvs.rolling(24).mean()) / qvs.rolling(24).std()

    tbr = pd.Series(tb / np.where(v > 0, v, 1))
    feat["taker_buy_ratio"] = tbr
    feat["taker_buy_z_24h"] = (tbr - tbr.rolling(24).mean()) / tbr.rolling(24).std()
    feat["taker_buy_persistence"] = tbr.rolling(6).mean() - tbr.rolling(168).mean()

    nts = pd.Series(nt)
    feat["n_trades_z_24h"] = (nts - nts.rolling(24).mean()) / nts.rolling(24).std()

    cmax = np.where(c > 0, c, 1)
    feat["upper_wick_rel"] = (h - np.maximum(o, c)) / cmax
    feat["lower_wick_rel"] = (np.minimum(o, c) - l) / cmax

    for w in [24, 48]:
        m = cs.rolling(w).mean()
        s = cs.rolling(w).std()
        feat[f"bb_pos_{w}h"] = (cs - m) / (2 * s)
    return feat


def forward_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    c = df["close"].values
    out = pd.DataFrame(index=df.index)
    for H in horizons:
        out[f"fwd_{H}h"] = pd.Series(c).pct_change(H).shift(-H)
    return out


def compute_ic_matrix(market: str, symbols: list[str],
                      is_start: str, is_end: str,
                      horizons: list[int]) -> pd.DataFrame:
    rows = []
    for sym in symbols:
        df = load_is(market, sym, is_start, is_end)
        feat = build_features(df)
        fwd = forward_returns(df, horizons)
        for fn in feat.columns:
            for hn in fwd.columns:
                a = feat[fn].replace([np.inf, -np.inf], np.nan)
                b = fwd[hn]
                mask = a.notna() & b.notna()
                if mask.sum() < 200:
                    continue
                ic = float(np.corrcoef(a[mask], b[mask])[0, 1])
                rows.append({"symbol": sym, "feature": fn,
                             "horizon": hn, "ic": ic, "n": int(mask.sum())})
    return pd.DataFrame(rows)


def rank_signals(ic_df: pd.DataFrame, symbols: list[str],
                 robustness_min_abs_ic: float = 0.04) -> pd.DataFrame:
    pv = ic_df.pivot_table(index=["feature", "horizon"], columns="symbol",
                           values="ic").reset_index()
    missing = [s for s in symbols if s not in pv.columns]
    if missing:
        raise ValueError(f"missing symbols in pivot: {missing}")
    pv["ic_avg"] = pv[symbols].mean(axis=1)
    pv["ic_min_abs"] = pv[symbols].abs().min(axis=1)
    signs = np.sign(pv[symbols].values)
    pv["same_sign"] = (signs == signs[:, [0]]).all(axis=1)
    pv["robust"] = pv["same_sign"] & (pv["ic_min_abs"] >= robustness_min_abs_ic)
    pv["abs_avg_ic"] = pv["ic_avg"].abs()
    return pv.sort_values("abs_avg_ic", ascending=False).reset_index(drop=True)


def calibrate_signal(
    market: str, symbols: list[str], is_start: str, is_end: str,
    feature: str, horizon: str, avg_ic: float,
    percentile: int, fee_bps: float,
) -> dict:
    """For one (feature, horizon), compute per-symbol threshold + entry stats + optimal_exit.

    Entry direction is chosen so the trade is always LONG (framework constraint):
      - avg_ic > 0  → feature high  predicts fwd high  → long when feature >= p{percentile}
      - avg_ic < 0  → feature high  predicts fwd low   → long when feature <= p{100 - percentile}

    optimal_exit is a terminal-return approximation: PT = p75 of entry-bar fwd returns (winners' cap),
    SL = |p25| (losers' floor). This is crude — intra-horizon path is not simulated — but provides
    the quantitative baseline that execution-designer uses as ±20% band reference.
    """
    import re
    m = re.match(r"fwd_(\d+)h", horizon)
    horizon_bars = int(m.group(1)) if m else 0

    per_symbol_threshold: dict[str, float] = {}
    per_symbol_stats: dict[str, dict] = {}
    all_fwd_bps: list[float] = []  # pooled across symbols for exit stats
    direction_side = "high" if avg_ic > 0 else "low"

    for sym in symbols:
        df = load_is(market, sym, is_start, is_end)
        feat = build_features(df)
        if feature not in feat.columns:
            continue
        fwd = forward_returns(df, [horizon_bars])
        fwd_col = f"fwd_{horizon_bars}h"
        if fwd_col not in fwd.columns:
            continue
        a = feat[feature].replace([np.inf, -np.inf], np.nan)
        b = fwd[fwd_col]
        mask = a.notna() & b.notna()
        if mask.sum() < 50:
            continue
        aa = a[mask].values
        bb = b[mask].values

        pct = percentile if direction_side == "high" else (100 - percentile)
        thr = float(np.percentile(aa, pct))
        trigger = (aa >= thr) if direction_side == "high" else (aa <= thr)
        if trigger.sum() < 10:
            continue

        fwd_bps = bb[trigger] * 10_000.0  # to bps
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
            "calibration_note": "no symbol yielded sufficient entry bars",
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
            "horizon_bars": horizon_bars,
            "win_rate_pct": round(100.0 * (arr > 0).mean(), 2),
            "mean_fwd_bps": round(mean_bps, 2),
            "note": "terminal-return approximation; no intra-horizon path simulation",
        },
        "ev_bps_after_fee": ev_bps_after_fee,
        "viable": ev_bps_after_fee > 0,
        "fee_bps_used": fee_bps,
    }


def build_brief(ranked: pd.DataFrame, market: str, symbols: list[str],
                is_start: str, is_end: str, top_k: int = 10,
                fee_bps: float = 4.0, threshold_percentile: int = 90) -> dict:
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
        entry.update(calibrate_signal(
            market, symbols, is_start, is_end,
            r["feature"], r["horizon"], r["ic_avg"],
            threshold_percentile, fee_bps,
        ))
        top_robust_out.append(entry)

    return {
        "market": market,
        "symbols": symbols,
        "is_period": {"start": is_start, "end": is_end},
        "fee_bps": fee_bps,
        "threshold_percentile": threshold_percentile,
        "robustness": {
            "min_abs_ic": 0.04,
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", required=True, choices=list(MARKET_PATHS))
    ap.add_argument("--symbols", required=True,
                    help="Comma-separated list, e.g. BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--is-start", required=True)
    ap.add_argument("--is-end", required=True)
    ap.add_argument("--horizons", default="1,3,6,12,24,48,72,168",
                    help="Comma-separated forward-return horizons (in bars)")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--fee-bps", type=float, default=4.0,
                    help="Round-trip fee in bps (Binance taker ≈ 4, KRX ≈ 21)")
    ap.add_argument("--threshold-percentile", type=int, default=90,
                    help="Entry percentile on the feature distribution (per symbol)")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    horizons = [int(x) for x in args.horizons.split(",")]

    print(f"[Phase 1] {args.market} {symbols} IS {args.is_start} → {args.is_end}")
    ic_df = compute_ic_matrix(args.market, symbols,
                              args.is_start, args.is_end, horizons)
    ranked = rank_signals(ic_df, symbols)
    brief = build_brief(ranked, args.market, symbols,
                        args.is_start, args.is_end, args.top_k,
                        fee_bps=args.fee_bps,
                        threshold_percentile=args.threshold_percentile)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(brief, indent=2))
    raw_out = out.with_suffix(".raw_ic.csv")
    ic_df.to_csv(raw_out, index=False)

    print(f"  features×horizons×symbols = {len(ic_df)} IC cells")
    print(f"  robust signals (top {args.top_k}):")
    for s in brief["top_robust"]:
        print(f"    {s['feature']:<24} {s['horizon']:<8} avg_IC={s['avg_ic']:+.4f}  "
              f"min|IC|={s['min_abs_ic']:.4f}")
    print(f"\nsaved → {out}")
    print(f"saved → {raw_out}")


if __name__ == "__main__":
    main()
