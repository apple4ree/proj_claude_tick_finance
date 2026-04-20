#!/usr/bin/env python3
"""Bar-level backtest runner with GenericFill emission.

Runs a daily-OHLCV strategy and emits both (a) a performance report
(total return, Sharpe, MDD, etc.) and (b) a GenericFill list in the same
schema as the tick-level engine. This lets the engine-agnostic invariant
checker operate on bar-level strategies without modification — the paper's
C3 engine-agnostic claim extends to daily-horizon strategies as well.

Strategy interface (Python):
  A strategy is a Python module/function that takes the OHLCV DataFrame and
  returns a `signal` pd.Series (1 = long next day, 0 = flat). The runner
  wraps the signal into a fill stream using bar open prices (next-bar-open
  execution) + configurable slippage/fee.

Usage:
  python scripts/bar_backtest.py --symbol BTCUSDT --strategy ma_cross_20_50 \
      --out strategies/<id>/report.json \
      --fills-out strategies/<id>/fills.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.bar_baselines import load_daily, split_is_oos, backtest, STRATEGIES
from scripts.check_invariants_from_fills import GenericFill, run_checker


FEE_SIDE_BPS = 5.0


def generate_fills(df: pd.DataFrame, signal: pd.Series, symbol: str,
                   lot_size: int = 1) -> list[GenericFill]:
    """Convert a signed signal (+1/0/-1) into a GenericFill list.

    Execution: signal at day T applies at day T+1 open. Transitions emit
    fills to move |position| towards target. Long-short strategies may emit
    two fills in a single day (close long then open short, or vice versa).
    """
    fills: list[GenericFill] = []
    position = 0  # signed
    prev_sig = 0
    for i in range(1, len(df)):
        target = int(signal.iloc[i - 1])
        if target == prev_sig:
            continue
        ts_ns = int(pd.Timestamp(df["open_time"].iloc[i]).value)
        open_px = float(df["open"].iloc[i])
        ctx = {"bar_close": float(df["close"].iloc[i])}

        # Helper: emit one fill, update state
        def emit(side: str, qty: int, tag: str):
            nonlocal position
            if side == "BUY":
                position += qty
            else:
                position -= qty
            fills.append(GenericFill(
                ts_ns=ts_ns, symbol=symbol, side=side, qty=qty, price=open_px,
                tag=tag, position_after=position, lot_size=lot_size, context=ctx,
            ))

        # 1) If we currently hold and need to close, close first
        if prev_sig == 1 and target in (0, -1):
            emit("SELL", lot_size, "exit_signal")
        elif prev_sig == -1 and target in (0, 1):
            emit("BUY", lot_size, "exit_short_signal")
        # 2) Then open new position if target != 0
        if target == 1:
            emit("BUY", lot_size, "entry_signal")
        elif target == -1:
            emit("SELL", lot_size, "entry_short_signal")
        prev_sig = target
    return fills


def run_bar_backtest(symbol: str, strategy: str, split: str = "is",
                     lot_size: int = 1) -> dict:
    df = load_daily(symbol)
    is_df, oos_df = split_is_oos(df)
    target_df = is_df if split == "is" else oos_df

    sig_fn = STRATEGIES[strategy]
    signal = sig_fn(target_df)
    metrics = backtest(target_df, signal, fee_side_bps=FEE_SIDE_BPS)
    fills = generate_fills(target_df, signal, symbol, lot_size=lot_size)

    return {
        "strategy": strategy,
        "symbol": symbol,
        "split": split,
        "period": {
            "start": target_df["date"].iloc[0] if len(target_df) else None,
            "end": target_df["date"].iloc[-1] if len(target_df) else None,
        },
        "metrics": metrics,
        "n_fills": len(fills),
        "fills": [
            {
                "ts_ns": f.ts_ns,
                "symbol": f.symbol,
                "side": f.side,
                "qty": f.qty,
                "price": f.price,
                "tag": f.tag,
                "position_after": f.position_after,
                "lot_size": f.lot_size,
                "context": f.context,
            } for f in fills
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Bar-level backtest with GenericFill emission.")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--strategy", required=True, choices=list(STRATEGIES.keys()))
    ap.add_argument("--split", choices=["is", "oos"], default="is")
    ap.add_argument("--lot-size", type=int, default=1)
    ap.add_argument("--out", help="Write report JSON here")
    ap.add_argument("--fills-out", help="Write fills-only JSON here")
    args = ap.parse_args()

    result = run_bar_backtest(args.symbol, args.strategy, args.split, args.lot_size)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, default=str))
        print(f"report -> {args.out}")

    if args.fills_out:
        Path(args.fills_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.fills_out).write_text(json.dumps(result["fills"], indent=2, default=str))
        print(f"fills -> {args.fills_out}")

    if not args.out and not args.fills_out:
        # print summary to stdout
        m = result["metrics"]
        print(f"{args.strategy}/{args.symbol}/{args.split}: "
              f"return={m['total_return_pct']:.2f}%  "
              f"sharpe={m['sharpe_annualized']:.3f}  "
              f"MDD={m['mdd_pct']:.2f}%  "
              f"fills={result['n_fills']}")


if __name__ == "__main__":
    main()
