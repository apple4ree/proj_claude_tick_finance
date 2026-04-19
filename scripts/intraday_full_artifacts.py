#!/usr/bin/env python3
"""Full artifact runner for intraday-bar strategies on Binance multi-horizon data.

Supports 1h/15m/5m/1m horizons. Reuses bar_full_artifacts.py helpers where
possible but with intraday-aware data loading and bars-per-year calculation.

Strategy directory must contain:
  spec.yaml
  strategy.py  — exposing generate_signal(df, **params) -> pd.Series in {-1,0,+1}
Spec must have:
  target_symbol: BTCUSDT / ETHUSDT / SOLUSDT
  target_horizon: 1h / 15m / 5m / 1m
  params: {...}
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

REPO = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = REPO / "strategies"

sys.path.insert(0, str(REPO))
from scripts.bar_full_artifacts import (
    _match_roundtrips, _compute_summary, _write_md,
)
from scripts.perf_ic_metrics import compute_signal_metrics

HORIZON_BARS_PER_YEAR = {
    "1d": 365.0,
    "1h": 24 * 365.0,
    "15m": 4 * 24 * 365.0,
    "5m": 12 * 24 * 365.0,
    "1m": 60 * 24 * 365.0,
}

HORIZON_DATA_PATH = {
    "1d": "data/binance_daily/{sym}.csv",
    "1h": "data/binance_multi/1h/{sym}.csv",
    "15m": "data/binance_multi/15m/{sym}.csv",
    "5m": "data/binance_multi/5m/{sym}.csv",
    "1m": "data/binance_multi/1m/{sym}.csv",
}


def load_horizon_data(symbol: str, horizon: str) -> pd.DataFrame:
    path = REPO / HORIZON_DATA_PATH[horizon].format(sym=symbol)
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    keep = ["open_time", "open", "high", "low", "close", "volume"]
    # Optional extended columns (order-flow, trade count). Kept if present so
    # strategies using taker_buy_base / n_trades / quote_volume still work.
    for opt in ("quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote"):
        if opt in df.columns:
            keep.append(opt)
    df = df[keep].copy()
    df = df.sort_values("open_time").reset_index(drop=True)
    df["date"] = df["open_time"].dt.strftime("%Y-%m-%d")
    return df


def _load_strategy(path: Path):
    sp = importlib.util.spec_from_file_location(f"_{path.parent.name}", path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def backtest_signed(df: pd.DataFrame, signal: pd.Series, fee_side_bps: float,
                   bars_per_year: float) -> dict:
    close = df["close"].to_numpy()
    signal_arr = signal.fillna(0).astype(int).to_numpy()
    position = np.concatenate([[0], signal_arr[:-1]])
    ret = np.diff(close) / close[:-1]
    pos = position[1:]
    strategy_ret = pos * ret
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee_side_bps / 1e4)
    net_ret = strategy_ret - fee_cost
    equity = np.cumprod(1.0 + net_ret)

    total_return = float(equity[-1] - 1.0) if len(equity) > 0 else 0.0
    if len(net_ret) > 1 and np.std(net_ret) > 0:
        sharpe = float(np.mean(net_ret) / np.std(net_ret) * np.sqrt(bars_per_year))
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
        "n_bars": len(net_ret),
        "exposure": float(np.mean(np.abs(pos))),
        "equity_curve_values": equity,
        "net_returns": net_ret,
    }


def generate_fills(df: pd.DataFrame, signal: pd.Series, symbol: str,
                  lot_size: int, fee_side_bps: float,
                  exit_tags: "pd.Series | None" = None) -> list[dict]:
    """Signed signal → fills list (in standard GenericFill-style dict).

    Parameters
    ----------
    exit_tags : optional Series aligned to df/signal index, containing per-bar
        exit-reason strings (e.g. "pt_hit", "sl_hit", "trailing_stop",
        "time_stop"). When provided, the value at the bar *before* the 1→0
        flip is used as the SELL tag. When None or the value is empty/NaN,
        falls back to the legacy generic "exit_signal" tag.

    This lets strategies communicate *why* they exited (PT vs SL vs trailing
    vs time stop) to the downstream critics/feedback analysis, instead of
    collapsing all exits into a single opaque "exit_signal" label.
    """
    fills: list[dict] = []
    position = 0
    prev_sig = 0

    def _lookup_exit_tag(idx: int) -> str:
        """Fetch the exit-reason at decision bar `idx` from exit_tags Series."""
        if exit_tags is None:
            return "exit_signal"
        try:
            v = exit_tags.iloc[idx]
        except Exception:
            return "exit_signal"
        if v is None:
            return "exit_signal"
        if isinstance(v, float) and np.isnan(v):
            return "exit_signal"
        s = str(v).strip()
        return s if s else "exit_signal"

    for i in range(1, len(df)):
        target = int(signal.iloc[i - 1])
        if target == prev_sig:
            continue
        ts_ns = int(pd.Timestamp(df["open_time"].iloc[i]).value)
        open_px = float(df["open"].iloc[i])
        ctx = {"bar_close": float(df["close"].iloc[i])}

        def emit(side: str, qty: int, tag: str):
            nonlocal position
            if side == "BUY":
                position += qty
            else:
                position -= qty
            fills.append({
                "ts_ns": ts_ns, "symbol": symbol, "side": side,
                "qty": qty, "avg_price": open_px,
                "fee": open_px * fee_side_bps / 1e4 * qty,
                "tag": tag, "context": ctx,
            })

        if prev_sig == 1 and target in (0, -1):
            emit("SELL", lot_size, _lookup_exit_tag(i - 1))
        elif prev_sig == -1 and target in (0, 1):
            emit("BUY", lot_size, "exit_short_signal")
        if target == 1:
            emit("BUY", lot_size, "entry_signal")
        elif target == -1:
            emit("SELL", lot_size, "entry_short_signal")
        prev_sig = target
    return fills


def run(strat_dir: Path) -> dict:
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    params = spec.get("params", {})
    symbol = spec["target_symbol"]
    horizon = spec.get("target_horizon", "1d")
    fee = float(params.get("fee_side_bps", 5.0))
    lot_size = int(params.get("lot_size", 1))

    module = _load_strategy(strat_dir / "strategy.py")
    df = load_horizon_data(symbol, horizon)
    result = module.generate_signal(df, **params)

    # Accept three return shapes for backward compat:
    #   1. pd.Series               — legacy signal-only
    #   2. (pd.Series, pd.Series)  — signal + per-bar exit-reason tags
    #   3. pd.DataFrame with "signal" (+ optional "exit_tag") columns
    exit_tags = None
    if isinstance(result, tuple) and len(result) == 2:
        signal, exit_tags = result
    elif isinstance(result, pd.DataFrame):
        signal = result["signal"]
        if "exit_tag" in result.columns:
            exit_tags = result["exit_tag"]
    else:
        signal = result

    bpy = HORIZON_BARS_PER_YEAR[horizon]
    metrics = backtest_signed(df, signal, fee, bpy)
    fills = generate_fills(df, signal, symbol, lot_size, fee, exit_tags=exit_tags)

    close_arr = df["close"].to_numpy()
    fwd_ret = np.diff(close_arr) / close_arr[:-1]
    sig_arr = signal.fillna(0).astype(int).to_numpy()
    sig_metrics = compute_signal_metrics(
        signal=sig_arr,
        forward_ret=fwd_ret,
        strat_ret=metrics["net_returns"],
        bench_ret=fwd_ret,
        bars_per_year=bpy,
    )

    starting_cash = 10_000_000.0
    equity = np.concatenate([[1.0], metrics["equity_curve_values"]]) * starting_cash
    ts_ns_list = [int(pd.Timestamp(t).value) for t in df["open_time"]]

    trace = {
        "mid_series": {symbol: [[ts, float(px)] for ts, px in zip(ts_ns_list, df["close"].tolist())]},
        "fills": fills,
        "equity_curve": [[ts, float(eq)] for ts, eq in zip(ts_ns_list, equity.tolist())],
    }

    roundtrips = _match_roundtrips(fills)
    summary = _compute_summary(roundtrips)

    report = {
        "spec_name": strat_dir.name,
        "symbols": [symbol],
        "dates": [df["date"].iloc[0], df["date"].iloc[-1]],
        "total_events": len(df),
        "total_pnl": float(equity[-1] - starting_cash),
        "return_pct": metrics["total_return_pct"],
        "sharpe_annualized": metrics["sharpe_annualized"],
        "sharpe_raw": metrics["sharpe_annualized"] / np.sqrt(bpy) if metrics["sharpe_annualized"] else 0.0,
        "mdd_pct": metrics["mdd_pct"],
        "n_trades": metrics["n_trades"],
        "n_roundtrips": len(roundtrips),
        "starting_cash": starting_cash,
        "ending_cash": float(equity[-1]),
        "total_fees": float(sum(f.get("fee", 0.0) for f in fills)),
        "target_horizon": horizon,
        "target_symbol": symbol,
        "avg_exposure": metrics["exposure"],
        "win_rate_pct": summary.get("win_rate_pct", 0.0) if roundtrips else 0.0,
        "avg_win_bps": summary.get("avg_net_bps_wins") or 0.0,
        "avg_loss_bps": summary.get("avg_net_bps_losses") or 0.0,
        "ic_pearson": sig_metrics["ic_pearson"],
        "ic_spearman": sig_metrics["ic_spearman"],
        "icir": sig_metrics["icir"],
        "icir_chunks": sig_metrics["icir_chunks"],
        "information_ratio": sig_metrics["information_ratio"],
        "ic_n": sig_metrics["ic_n"],
        "best_trade": float(max((r["net_pnl"] for r in roundtrips), default=0.0)),
        "worst_trade": float(min((r["net_pnl"] for r in roundtrips), default=0.0)),
        "avg_trade_pnl": float(np.mean([r["net_pnl"] for r in roundtrips])) if roundtrips else 0.0,
        "invariant_violations": [],
        "invariant_violation_count": 0,
        "invariant_violation_by_type": {},
        "kind": "bar_intraday",
        "duration_sec": 0.0,
        "n_partial_fills": 0,
        "pending_at_end": 0,
        "rejected": {"cash": 0, "short": 0, "no_liquidity": 0, "non_marketable": 0, "strict_invariant": 0},
        "roundtrips": roundtrips,
    }

    (strat_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (strat_dir / "trace.json").write_text(json.dumps(trace, indent=2, default=str))
    (strat_dir / "analysis_trace.json").write_text(json.dumps(
        {"strategy_id": strat_dir.name, "trace_mode": "bar_intraday",
         "summary": summary, "roundtrips": roundtrips}, indent=2, default=str))
    _write_md(strat_dir.name, roundtrips, summary, strat_dir / "analysis_trace.md")

    # Render interactive Plotly HTML dashboard (price + fills, equity, drawdown,
    # metric cards, sensitivity panel). Without this step, report.html either
    # does not exist or carries a stale empty-trace template from another
    # rendering path. Safe to ignore failures — report.json/trace.json are
    # still canonical.
    try:
        from engine.report_html import render as _render_html
        _render_html(strat_dir)
    except Exception as e:  # pragma: no cover — defensive
        print(f"[warn] report.html render failed for {strat_dir.name}: {e}")

    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    args = ap.parse_args()
    d = STRATEGIES_DIR / args.id
    r = run(d)
    print(f"{args.id}: {r['target_horizon']} {r['target_symbol']} "
          f"ret={r['return_pct']:+.2f}% sharpe={r['sharpe_annualized']:+.2f} "
          f"MDD={r['mdd_pct']:+.2f}% RT={r['n_roundtrips']}")


if __name__ == "__main__":
    main()
