#!/usr/bin/env python3
"""Naive baseline bar-level strategies on Binance daily OHLCV.

Implements three classic long-only strategies — MA-cross, momentum,
RSI-reversion — on BTC/ETH/SOL daily, split into in-sample (2023-01-01 ..
2024-12-31) and out-of-sample (2025-01-01 .. 2025-12-31).

Produces Sharpe / total-return / max-drawdown baselines for each
(strategy × symbol) on both IS and OOS. Output:
  data/bar_baselines/<strategy>_<symbol>.json
  data/bar_baselines/summary.json

Also produces Buy-Hold baseline for each symbol.

Fee model: Binance spot 10 bps round-trip (5 bps per side; academic
standard).

No external dependencies beyond numpy/pandas (avoids vectorbt to keep
reproducibility simple).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data" / "binance_daily"
OUT_DIR = REPO / "data" / "bar_baselines"

IS_START = "2023-01-01"
IS_END = "2024-12-31"
OOS_START = "2025-01-01"
OOS_END = "2025-12-31"

FEE_PER_SIDE_BPS = 5.0  # Binance spot; 10 bps round-trip


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily(symbol: str) -> pd.DataFrame:
    path = DATA_DIR / f"{symbol}.csv"
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("open_time").reset_index(drop=True)
    df["date"] = df["open_time"].dt.strftime("%Y-%m-%d")
    return df


def split_is_oos(df: pd.DataFrame):
    is_df = df[(df["date"] >= IS_START) & (df["date"] <= IS_END)].copy().reset_index(drop=True)
    oos_df = df[(df["date"] >= OOS_START) & (df["date"] <= OOS_END)].copy().reset_index(drop=True)
    return is_df, oos_df


# ---------------------------------------------------------------------------
# Backtest engine (vectorized, long-only, fixed-capital, mark-to-close)
# ---------------------------------------------------------------------------

def backtest(df: pd.DataFrame, signal: pd.Series, fee_side_bps: float = FEE_PER_SIDE_BPS) -> dict:
    """Backtest a signed signal.

    signal: +1 = long next day, 0 = flat, -1 = short next day (long-short strategies).
    Signal at index i applies to period i+1 (avoid look-ahead).
    """
    close = df["close"].to_numpy()
    signal_arr = signal.fillna(0).astype(int).to_numpy()
    # Shift: today's signal applies tomorrow (execute on tomorrow's open, mark on tomorrow's close)
    position = np.concatenate([[0], signal_arr[:-1]])
    ret = np.diff(close) / close[:-1]  # length = len(close)-1, ret[i] is return from day i to i+1
    pos = position[1:]  # align: position[i] is whether we hold during ret[i]
    strategy_ret = pos * ret  # signed position × return captures long/short

    # Turnover: fee proportional to |change| (flat→long = 1 side, long→short = 2 sides)
    change = np.abs(np.diff(np.concatenate([[0], position])))  # magnitude of change
    fee_cost = change[1:] * (fee_side_bps / 1e4)
    net_ret = strategy_ret - fee_cost

    equity = np.cumprod(1.0 + net_ret)
    total_return = float(equity[-1] - 1.0) if len(equity) > 0 else 0.0
    # Sharpe: daily-return based, annualize by sqrt(365)
    if len(net_ret) > 1 and np.std(net_ret) > 0:
        sharpe = float(np.mean(net_ret) / np.std(net_ret) * np.sqrt(365.0))
    else:
        sharpe = 0.0

    # Max drawdown
    peak = np.maximum.accumulate(equity) if len(equity) > 0 else np.array([1.0])
    dd = (equity - peak) / peak if len(equity) > 0 else np.array([0.0])
    mdd = float(np.min(dd)) if len(dd) > 0 else 0.0

    n_trades = int(np.sum(change[1:] > 0))
    n_days_in_market = int(np.sum(np.abs(pos) > 0))
    avg_exposure = float(np.mean(np.abs(pos))) if len(pos) > 0 else 0.0

    return {
        "total_return_pct": total_return * 100.0,
        "sharpe_annualized": sharpe,
        "mdd_pct": mdd * 100.0,
        "n_trades": n_trades,
        "n_days_in_market": n_days_in_market,
        "avg_exposure": avg_exposure,
        "n_days": len(net_ret),
        "final_equity": float(equity[-1]) if len(equity) > 0 else 1.0,
    }


# ---------------------------------------------------------------------------
# Signal generators
# ---------------------------------------------------------------------------

def signal_buy_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1, index=df.index)


def signal_ma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
    close = df["close"]
    ma_f = close.rolling(fast).mean()
    ma_s = close.rolling(slow).mean()
    sig = (ma_f > ma_s).astype(int)
    sig.iloc[: slow] = 0  # no signal until window ready
    return sig


def signal_momentum(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    ret = df["close"].pct_change(lookback)
    sig = (ret > 0).astype(int)
    sig.iloc[: lookback] = 0
    return sig


def signal_rsi_reversion(df: pd.DataFrame, period: int = 14, buy_below: float = 30,
                         sell_above: float = 70) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Long when RSI < buy_below, exit when RSI > sell_above, else hold previous state
    state = np.zeros(len(df), dtype=int)
    for i, v in enumerate(rsi.values):
        if np.isnan(v):
            state[i] = 0
        elif v < buy_below:
            state[i] = 1
        elif v > sell_above:
            state[i] = 0
        else:
            state[i] = state[i - 1] if i > 0 else 0
    return pd.Series(state, index=df.index)


STRATEGIES = {
    "buy_hold": signal_buy_hold,
    "ma_cross_20_50": lambda df: signal_ma_cross(df, 20, 50),
    "momentum_20": lambda df: signal_momentum(df, 20),
    "momentum_50": lambda df: signal_momentum(df, 50),
    "rsi_reversion_14": lambda df: signal_rsi_reversion(df, 14, 30, 70),
}


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def run_all(symbols: list[str]) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_result: list[dict] = []
    for sym in symbols:
        df = load_daily(sym)
        is_df, oos_df = split_is_oos(df)
        for strat_name, strat_fn in STRATEGIES.items():
            try:
                sig_is = strat_fn(is_df)
                sig_oos = strat_fn(oos_df)
            except Exception as exc:
                print(f"  {strat_name}/{sym}: signal gen FAILED — {exc}", file=sys.stderr)
                continue
            r_is = backtest(is_df, sig_is)
            r_oos = backtest(oos_df, sig_oos)
            row = {
                "strategy": strat_name,
                "symbol": sym,
                "is": r_is,
                "oos": r_oos,
            }
            per_result.append(row)
            (OUT_DIR / f"{strat_name}__{sym}.json").write_text(json.dumps(row, indent=2))

    summary = {"strategies": per_result}
    summary["aggregate"] = _aggregate(per_result)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _aggregate(rows: list[dict]) -> dict:
    by_strat: dict[str, list[float]] = {}
    for r in rows:
        by_strat.setdefault(r["strategy"], []).append(r["is"]["sharpe_annualized"])
    return {
        "is_sharpe_mean_by_strategy": {k: float(np.mean(v)) for k, v in by_strat.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Naive baseline strategies on Binance daily.")
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    args = ap.parse_args()

    print(f"Running {len(STRATEGIES)} strategies × {len(args.symbols)} symbols")
    print(f"  IS: {IS_START} .. {IS_END}")
    print(f"  OOS: {OOS_START} .. {OOS_END}")
    print(f"  fee: {FEE_PER_SIDE_BPS*2:.1f} bps round-trip")
    print()

    summary = run_all(args.symbols)

    # Table print
    header = f"{'Strategy':<18} {'Symbol':<10} {'IS Sharpe':>10} {'IS Ret%':>9} {'IS MDD%':>9} {'IS #Tr':>7} {'OOS Sharpe':>11} {'OOS Ret%':>10}"
    print(header)
    print("-" * len(header))
    for row in summary["strategies"]:
        r_is = row["is"]
        r_oos = row["oos"]
        print(f"{row['strategy']:<18} {row['symbol']:<10} "
              f"{r_is['sharpe_annualized']:>10.3f} {r_is['total_return_pct']:>9.1f} "
              f"{r_is['mdd_pct']:>9.1f} {r_is['n_trades']:>7d} "
              f"{r_oos['sharpe_annualized']:>11.3f} {r_oos['total_return_pct']:>10.1f}")

    print()
    print("IS Sharpe mean by strategy:")
    for k, v in summary["aggregate"]["is_sharpe_mean_by_strategy"].items():
        print(f"  {k:<18} {v:.3f}")
    print(f"\nSaved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
