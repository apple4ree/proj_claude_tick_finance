#!/usr/bin/env python3
"""Experiment 1 — Horizon sweep.

Same momentum-style strategy applied across 5 horizons (1m, 5m, 15m, 1h, 1d)
on Binance BTCUSDT. Produces Sharpe curve showing the fee-saturation
horizon threshold.

Signal: simple momentum — enter long when N-bar return > 0, exit when <= 0.
Fee: 10 bps round-trip.

Key controls:
- Same symbol (BTCUSDT)
- Same calendar window (2025-07-01 .. 2025-12-31) — all horizons share this
- Same strategy type (momentum binary long/flat)
- Same fee
- Only horizon varies

Each horizon uses a momentum lookback that scales to represent a similar
"real-time window" (e.g., 1m horizon uses 60-bar lookback = 1 hour;
1h horizon uses 24-bar lookback = 1 day, etc.) AND a fixed-bar lookback
variant so we can disentangle "bar count" from "wall-clock window."

Output: data/experiment_1_results.json + per-horizon curve data
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUT = REPO / "data" / "experiment_1_results.json"

# Horizons: (label, data_path, bars_per_day, fixed_bar_lookback, wallclock_window_hours_lookback)
HORIZONS = [
    ("1m",  "data/binance_multi/1m/BTCUSDT.csv",  1440, 20, 1.0),   # 20 bars OR 60 bars for 1h window
    ("5m",  "data/binance_multi/5m/BTCUSDT.csv",  288,  20, 1.0),
    ("15m", "data/binance_multi/15m/BTCUSDT.csv", 96,   20, 1.0),
    ("1h",  "data/binance_multi/1h/BTCUSDT.csv",  24,   20, 1.0),
    ("1d",  "data/binance_daily/BTCUSDT.csv",     1,    20, 1.0),  # daily will use fixed=20 only
]

FEE_SIDE_BPS = 5.0  # Binance spot; 10 bps round-trip


def load_bars(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("open_time").reset_index(drop=True)
    return df


def _window_bar_count(horizon_label: str, bars_per_day: int, hours: float) -> int:
    """Convert wall-clock hours to number of bars for the horizon."""
    bars_per_hour = bars_per_day / 24.0
    n = max(1, int(round(hours * bars_per_hour)))
    return n


def _backtest_momentum(df: pd.DataFrame, lookback: int, fee_side_bps: float) -> dict:
    close = df["close"].to_numpy()
    if len(close) < lookback + 2:
        return {"total_return_pct": 0.0, "sharpe_annualized": 0.0,
                "mdd_pct": 0.0, "n_trades": 0, "n_bars": len(close),
                "exposure": 0.0, "skipped": True}

    ret_lb = pd.Series(close).pct_change(lookback).to_numpy()
    signal = (ret_lb > 0).astype(int)
    signal[:lookback] = 0
    # shift: signal[i] applies to bar i+1 return
    position = np.concatenate([[0], signal[:-1]])
    ret = np.diff(close) / close[:-1]
    pos = position[1:]
    strat_ret = pos * ret
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee_side_bps / 1e4)
    net = strat_ret - fee_cost
    equity = np.cumprod(1.0 + net)

    total_return = float(equity[-1] - 1.0) if len(equity) > 0 else 0.0

    # Annualized Sharpe: we compute standard deviation of PER-BAR net return
    # and annualize using bars-per-year. bars per year derived from len(df) / days.
    days_covered = max(1.0, (df["open_time"].iloc[-1] - df["open_time"].iloc[0]).total_seconds() / 86400.0)
    bars_per_year = len(net) / days_covered * 365.0
    if len(net) > 1 and np.std(net) > 0:
        sharpe = float(np.mean(net) / np.std(net) * np.sqrt(bars_per_year))
    else:
        sharpe = 0.0

    peak = np.maximum.accumulate(equity) if len(equity) > 0 else np.array([1.0])
    dd = (equity - peak) / peak if len(equity) > 0 else np.array([0.0])
    mdd = float(np.min(dd)) if len(dd) > 0 else 0.0

    return {
        "total_return_pct": total_return * 100.0,
        "sharpe_annualized": sharpe,
        "mdd_pct": mdd * 100.0,
        "n_trades": int(np.sum(change[1:] > 0)),
        "n_bars": len(net),
        "exposure": float(np.mean(pos)),
        "days_covered": days_covered,
        "bars_per_year": bars_per_year,
        "lookback_bars": lookback,
        "skipped": False,
    }


def main() -> None:
    results: list[dict] = []

    print(f"{'Horizon':<6} {'Variant':<12} {'Lookback':>10} {'Sharpe':>8} {'Return%':>9} "
          f"{'MDD%':>7} {'#Trades':>8} {'Exposure':>9} {'#Bars':>9}")
    print("-" * 86)

    for label, csv_path, bars_per_day, fixed_lb, wc_hours in HORIZONS:
        df = load_bars(REPO / csv_path)

        # Variant A: fixed bar lookback (same #bars across horizons)
        lb_a = fixed_lb
        r_a = _backtest_momentum(df, lb_a, FEE_SIDE_BPS)
        results.append({"horizon": label, "variant": "fixed_bars",
                        "lookback": lb_a, **r_a})
        print(f"{label:<6} {'fixed_bars':<12} {lb_a:>10} "
              f"{r_a['sharpe_annualized']:>+8.3f} {r_a['total_return_pct']:>+9.2f} "
              f"{r_a['mdd_pct']:>+7.2f} {r_a['n_trades']:>8} {r_a['exposure']:>9.3f} "
              f"{r_a['n_bars']:>9}")

        # Variant B: wallclock-scaled lookback (constant real-time window)
        lb_b = _window_bar_count(label, bars_per_day, wc_hours)
        if lb_b != lb_a:
            r_b = _backtest_momentum(df, lb_b, FEE_SIDE_BPS)
            results.append({"horizon": label, "variant": "wallclock_1h",
                            "lookback": lb_b, **r_b})
            print(f"{label:<6} {'wallclock_1h':<12} {lb_b:>10} "
                  f"{r_b['sharpe_annualized']:>+8.3f} {r_b['total_return_pct']:>+9.2f} "
                  f"{r_b['mdd_pct']:>+7.2f} {r_b['n_trades']:>8} {r_b['exposure']:>9.3f} "
                  f"{r_b['n_bars']:>9}")

    # Additional variants — longer wallclock windows to see scaling
    extra_windows = [6, 24, 72, 240]  # hours
    for hours in extra_windows:
        print(f"\n--- Wallclock window: {hours} hours ---")
        for label, csv_path, bars_per_day, fixed_lb, wc_hours in HORIZONS:
            lb = _window_bar_count(label, bars_per_day, hours)
            df = load_bars(REPO / csv_path)
            r = _backtest_momentum(df, lb, FEE_SIDE_BPS)
            results.append({"horizon": label, "variant": f"wallclock_{hours}h",
                            "lookback": lb, **r})
            print(f"{label:<6} {'wallclock_' + str(hours) + 'h':<12} {lb:>10} "
                  f"{r['sharpe_annualized']:>+8.3f} {r['total_return_pct']:>+9.2f} "
                  f"{r['mdd_pct']:>+7.2f} {r['n_trades']:>8} {r['exposure']:>9.3f} "
                  f"{r['n_bars']:>9}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nsaved -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
