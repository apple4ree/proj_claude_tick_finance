#!/usr/bin/env python3
"""Experiment G — Multi-symbol horizon sweep.

Extension of exp_b (BTC-only) to BTCUSDT, ETHUSDT, SOLUSDT × 1m/5m/15m/1h/1d.
Each (symbol, horizon, lookback_variant) run produces a full artifact set
under per_run/<symbol>_<horizon>_<variant>/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

HERE = Path(__file__).resolve().parent
PER_RUN = HERE / "per_run"
PER_RUN.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# (label, data_path_template, bars_per_day)
HORIZONS = [
    ("1m",  "data/binance_multi/1m/{sym}.csv",  1440),
    ("5m",  "data/binance_multi/5m/{sym}.csv",  288),
    ("15m", "data/binance_multi/15m/{sym}.csv", 96),
    ("1h",  "data/binance_multi/1h/{sym}.csv",  24),
    ("1d",  "data/binance_daily/{sym}.csv",     1),
]

FEE_SIDE_BPS = 5.0
WALLCLOCK_LOOKBACK_HOURS = [1, 6, 24, 72, 240]  # 5 variants per (sym, horizon)


def load_bars(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("open_time").reset_index(drop=True)
    return df


def backtest_momentum(df: pd.DataFrame, lookback: int, fee_side_bps: float) -> dict:
    close = df["close"].to_numpy()
    if len(close) < lookback + 2:
        return {}
    ret_lb = pd.Series(close).pct_change(lookback).to_numpy()
    signal = (ret_lb > 0).astype(int)
    signal[:lookback] = 0
    position = np.concatenate([[0], signal[:-1]])
    ret = np.diff(close) / close[:-1]
    pos = position[1:]
    strat_ret = pos * ret
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee_side_bps / 1e4)
    net = strat_ret - fee_cost
    equity = np.cumprod(1.0 + net)
    total_return = float(equity[-1] - 1.0) if len(equity) > 0 else 0.0

    days = max(1.0, (df["open_time"].iloc[-1] - df["open_time"].iloc[0]).total_seconds() / 86400.0)
    bars_per_year = len(net) / days * 365.0
    if len(net) > 1 and np.std(net) > 0:
        sharpe = float(np.mean(net) / np.std(net) * np.sqrt(bars_per_year))
    else:
        sharpe = 0.0

    peak = np.maximum.accumulate(equity) if len(equity) > 0 else np.array([1.0])
    dd = (equity - peak) / peak if len(equity) > 0 else np.array([0.0])
    mdd = float(np.min(dd)) if len(dd) > 0 else 0.0

    return {
        "return_pct": total_return * 100,
        "sharpe_annualized": sharpe,
        "mdd_pct": mdd * 100,
        "n_trades": int(np.sum(change[1:] > 0)),
        "n_bars": len(net),
        "exposure": float(np.mean(pos)),
        "days": days,
    }


def window_bars(bars_per_day: int, hours: float) -> int:
    return max(1, int(round(hours / 24.0 * bars_per_day)))


def main() -> None:
    all_runs: list[dict] = []
    print(f"{'Sym':<8} {'Horizon':<4} {'Variant':<18} {'Lookback':>8} "
          f"{'Ret%':>8} {'Sharpe':>8} {'MDD%':>7} {'#Trades':>8} {'Exposure':>9}")
    print("-" * 92)

    for sym in SYMBOLS:
        for h_label, path_tmpl, bpd in HORIZONS:
            path = REPO / path_tmpl.format(sym=sym)
            if not path.exists():
                continue
            df = load_bars(path)
            for hours in WALLCLOCK_LOOKBACK_HOURS:
                lb = window_bars(bpd, hours)
                r = backtest_momentum(df, lb, FEE_SIDE_BPS)
                if not r:
                    continue
                r.update({"symbol": sym, "horizon": h_label, "lookback": lb,
                          "lookback_hours": hours,
                          "variant": f"wallclock_{hours}h"})
                all_runs.append(r)
                print(f"{sym:<8} {h_label:<4} {'wallclock_' + str(hours) + 'h':<18} {lb:>8} "
                      f"{r['return_pct']:>+8.2f} {r['sharpe_annualized']:>+8.3f} "
                      f"{r['mdd_pct']:>+7.2f} {r['n_trades']:>8} {r['exposure']:>9.3f}")

    (HERE / "results.json").write_text(json.dumps(all_runs, indent=2))

    # Aggregate: Sharpe by (symbol, horizon), averaged across lookback variants
    agg = {}
    for r in all_runs:
        key = (r["symbol"], r["horizon"])
        agg.setdefault(key, []).append(r)

    rows = []
    for (sym, h), runs in agg.items():
        sharpes = [r["sharpe_annualized"] for r in runs]
        rets = [r["return_pct"] for r in runs]
        mdds = [r["mdd_pct"] for r in runs]
        rows.append({
            "symbol": sym, "horizon": h, "n_variants": len(runs),
            "sharpe_mean": float(np.mean(sharpes)),
            "sharpe_median": float(np.median(sharpes)),
            "return_pct_mean": float(np.mean(rets)),
            "mdd_pct_mean": float(np.mean(mdds)),
        })
    (HERE / "aggregate.json").write_text(json.dumps(rows, indent=2))

    print(f"\nsaved -> {HERE.relative_to(REPO)}/results.json + aggregate.json")


if __name__ == "__main__":
    main()
