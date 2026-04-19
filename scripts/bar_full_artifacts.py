#!/usr/bin/env python3
"""Generate full artifact set for a bar-level strategy.

Produces per-strategy directory:
  spec.yaml (exists)
  strategy.py (exists)
  report.json         — metrics (return, sharpe, MDD, roundtrips)
  trace.json          — fills, equity_curve, mid_series in standard schema
  analysis_trace.json — FIFO-matched roundtrips
  analysis_trace.md   — human-readable summary
  report.html         — Plotly interactive report

For the bar-level runner the LOB enrichment from analyze_trace.py is not
applicable (daily bars have no limit-order-book), so analysis uses the
bar-close snapshot context instead.

Usage:
  python scripts/bar_full_artifacts.py --id bar_s2_btc_bb_reversion
  python scripts/bar_full_artifacts.py --all
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
from scripts.bar_baselines import load_daily, split_is_oos, backtest
from scripts.bar_backtest import generate_fills
from scripts.perf_ic_metrics import compute_signal_metrics


def _load_strategy(path: Path):
    spec = importlib.util.spec_from_file_location(f"_{path.parent.name}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_full(strat_dir: Path, split: str = "full") -> dict:
    """Run strategy and produce full artifact set."""
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    params = spec.get("params", {})
    fee = float(params.get("fee_side_bps", 5.0))
    lot_size = int(params.get("lot_size", 1))
    symbol = spec["target_symbol"]

    module = _load_strategy(strat_dir / "strategy.py")

    df = load_daily(symbol)
    is_df, oos_df = split_is_oos(df)
    if split == "is":
        target_df = is_df
    elif split == "oos":
        target_df = oos_df
    else:
        target_df = df

    sig = module.generate_signal(target_df, **params)
    metrics = backtest(target_df, sig, fee_side_bps=fee)
    fills = generate_fills(target_df, sig, symbol, lot_size=lot_size)

    # Build trace.json-compatible structure
    starting_cash = 10_000_000.0
    close = target_df["close"].to_numpy()
    signal_arr = sig.fillna(0).astype(int).to_numpy()
    position = np.concatenate([[0], signal_arr[:-1]])
    ret = np.diff(close) / close[:-1]
    pos = position[1:]
    strat_ret = pos * ret
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee / 1e4)
    net = strat_ret - fee_cost
    equity_val = starting_cash * np.cumprod(1.0 + net)
    equity_val = np.concatenate([[starting_cash], equity_val])

    ts_ns_list = [int(pd.Timestamp(t).value) for t in target_df["open_time"]]

    mid_series = {symbol: [[ts, float(px)] for ts, px in zip(ts_ns_list, close.tolist())]}
    equity_curve = [[ts, float(eq)] for ts, eq in zip(ts_ns_list, equity_val.tolist())]

    trace = {
        "mid_series": mid_series,
        "fills": [
            {"ts_ns": f.ts_ns, "symbol": f.symbol, "side": f.side,
             "qty": int(f.qty), "avg_price": float(f.price), "fee": float(f.price * fee / 1e4 * f.qty),
             "tag": f.tag, "context": f.context}
            for f in fills
        ],
        "equity_curve": equity_curve,
    }

    sig_metrics = compute_signal_metrics(
        signal=signal_arr,
        forward_ret=ret,
        strat_ret=net,
        bench_ret=ret,
        bars_per_year=365.0,
    )

    report = {
        "spec_name": strat_dir.name,
        "symbols": [symbol],
        "dates": [target_df["date"].iloc[0], target_df["date"].iloc[-1]],
        "total_events": len(target_df),
        "total_pnl": float(equity_val[-1] - starting_cash),
        "return_pct": metrics["total_return_pct"],
        "sharpe_raw": metrics["sharpe_annualized"] / np.sqrt(365.0) if metrics["sharpe_annualized"] else 0.0,
        "sharpe_annualized": metrics["sharpe_annualized"],
        "mdd_pct": metrics["mdd_pct"],
        "ic_pearson": sig_metrics["ic_pearson"],
        "ic_spearman": sig_metrics["ic_spearman"],
        "icir": sig_metrics["icir"],
        "icir_chunks": sig_metrics["icir_chunks"],
        "information_ratio": sig_metrics["information_ratio"],
        "ic_n": sig_metrics["ic_n"],
        "n_trades": metrics["n_trades"] * 2 if metrics["n_trades"] else 0,  # entry+exit approx
        "n_roundtrips": len([f for f in fills if f.side == "SELL"]),
        "n_partial_fills": 0,
        "pending_at_end": 0,
        "rejected": {"cash": 0, "short": 0, "no_liquidity": 0, "non_marketable": 0, "strict_invariant": 0},
        "starting_cash": starting_cash,
        "ending_cash": float(equity_val[-1]),
        "total_fees": float(-np.sum(fee_cost) * starting_cash) if fee_cost.size else 0.0,
        "split": split,
        "avg_exposure": metrics["avg_exposure"],
        "win_rate_pct": 0.0,  # computed from roundtrips below
        "avg_win_bps": 0.0,
        "avg_loss_bps": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "avg_trade_pnl": 0.0,
        "invariant_violations": [],
        "invariant_violation_count": 0,
        "invariant_violation_by_type": {},
        "duration_sec": 0.0,
        "kind": "bar",
    }

    (strat_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (strat_dir / "trace.json").write_text(json.dumps(trace, indent=2, default=str))

    # FIFO-match roundtrips
    roundtrips = _match_roundtrips(trace["fills"])
    summary = _compute_summary(roundtrips)

    # Update report with roundtrip stats
    if roundtrips:
        wins = [r for r in roundtrips if r["net_pnl"] > 0]
        losses = [r for r in roundtrips if r["net_pnl"] <= 0]
        report["win_rate_pct"] = len(wins) / len(roundtrips) * 100
        report["avg_trade_pnl"] = float(np.mean([r["net_pnl"] for r in roundtrips]))
        report["best_trade"] = float(max(r["net_pnl"] for r in roundtrips))
        report["worst_trade"] = float(min(r["net_pnl"] for r in roundtrips))
        if wins:
            report["avg_win_bps"] = float(np.mean([r["net_bps"] for r in wins]))
        if losses:
            report["avg_loss_bps"] = float(np.mean([r["net_bps"] for r in losses]))
        report["roundtrips"] = roundtrips
    (strat_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))

    # analysis_trace files
    analysis = {
        "strategy_id": strat_dir.name,
        "trace_mode": "bar",
        "summary": summary,
        "roundtrips": roundtrips,
    }
    (strat_dir / "analysis_trace.json").write_text(json.dumps(analysis, indent=2, default=str))
    _write_md(strat_dir.name, roundtrips, summary, strat_dir / "analysis_trace.md")

    # Interactive HTML
    _render_html(strat_dir, report, trace)

    # Static PNG chart
    _render_png(strat_dir, trace, equity_curve)

    return report


def _match_roundtrips(fills: list[dict]) -> list[dict]:
    inventory: dict[str, deque] = {}
    roundtrips = []
    KST = timezone(timedelta(hours=9))
    for f in fills:
        sym = f["symbol"]
        side = f["side"]
        if side == "BUY" and f.get("tag", "").startswith(("entry", "exit_short")):
            # Long entry (BUY for entry_signal or covering short)
            if f.get("tag", "").startswith("exit_short"):
                # Covering short — roundtrip complete for short position
                inv = inventory.get(sym + "_short", deque())
                if inv:
                    short_entry = inv.popleft()
                    _append_roundtrip(roundtrips, short_entry, f, "short", KST)
                continue
            inventory.setdefault(sym, deque()).append(f)
        elif side == "SELL":
            if f.get("tag", "").startswith("entry_short"):
                inventory.setdefault(sym + "_short", deque()).append(f)
                continue
            inv = inventory.get(sym, deque())
            if not inv:
                continue
            buy = inv.popleft()
            _append_roundtrip(roundtrips, buy, f, "long", KST)
    return roundtrips


def _append_roundtrip(roundtrips: list, entry: dict, exit: dict, direction: str, KST):
    entry_px = float(entry["avg_price"])
    exit_px = float(exit["avg_price"])
    qty = int(entry["qty"])
    fee = float(entry["fee"]) + float(exit["fee"])
    if direction == "long":
        gross = (exit_px - entry_px) * qty
    else:
        gross = (entry_px - exit_px) * qty
    net = gross - fee
    net_bps = net / (entry_px * qty) * 1e4 if entry_px > 0 else 0.0
    hold_sec = (exit["ts_ns"] - entry["ts_ns"]) / 1e9

    entry_dt = datetime.fromtimestamp(entry["ts_ns"] / 1e9, tz=KST)
    exit_dt = datetime.fromtimestamp(exit["ts_ns"] / 1e9, tz=KST)

    roundtrips.append({
        "symbol": entry["symbol"],
        "direction": direction,
        "buy_time": entry_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "buy_px": entry_px,
        "sell_time": exit_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "sell_px": exit_px,
        "hold_sec": int(hold_sec),
        "hold": _fmt_hold(hold_sec),
        "exit_tag": exit.get("tag", ""),
        "qty": qty,
        "fee": round(fee, 2),
        "gross_pnl": round(gross, 2),
        "net_pnl": round(net, 2),
        "net_bps": round(net_bps, 2),
        "result": "WIN" if net > 0 else "LOSS",
        "buy_context": entry.get("context", {}),
        "sell_context": exit.get("context", {}),
    })


def _fmt_hold(sec: float) -> str:
    sec = int(sec)
    days = sec // 86400
    hours = (sec % 86400) // 3600
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h"
    return f"{sec // 60}m"


def _enrich_roundtrips_with_mfe_mae(roundtrips: list[dict], mid_series_per_sym: dict[str, list]) -> None:
    """Add Maximum Favorable / Adverse Excursion to each roundtrip in-place.

    For each completed long roundtrip, scan the mid-price series between the
    entry fill and the exit fill. Record:
        mfe_bps  — best unrealized P&L during the hold (in bps)
        mae_bps  — worst unrealized P&L during the hold (in bps, signed negative)
        capture_pct — realized / MFE × 100.  < 50% flags a give-back pattern;
                      negative means price peaked favorably then reversed past entry.

    Without this enrichment, trajectory-level give-back patterns are invisible
    to critics and designer agents — only entry/exit endpoints are logged.
    """
    if not roundtrips or not mid_series_per_sym:
        return

    # Build per-symbol timestamp + price arrays once
    sym_arrs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for sym, series in mid_series_per_sym.items():
        if not series:
            continue
        ts_arr = np.fromiter((int(s[0]) for s in series), dtype=np.int64, count=len(series))
        px_arr = np.fromiter((float(s[1]) for s in series), dtype=np.float64, count=len(series))
        sym_arrs[sym] = (ts_arr, px_arr)

    for r in roundtrips:
        sym = r["symbol"]
        if sym not in sym_arrs:
            r["mfe_bps"] = None
            r["mae_bps"] = None
            r["capture_pct"] = None
            continue
        ts_arr, px_arr = sym_arrs[sym]
        # Parse entry / exit timestamps from buy_time / sell_time (KST+9)
        KST = timezone(timedelta(hours=9))
        b_ts = int(datetime.strptime(r["buy_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp() * 1e9)
        s_ts = int(datetime.strptime(r["sell_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp() * 1e9)
        lo = int(np.searchsorted(ts_arr, b_ts, side="left"))
        hi = int(np.searchsorted(ts_arr, s_ts, side="right"))
        if lo >= hi:
            r["mfe_bps"] = None
            r["mae_bps"] = None
            r["capture_pct"] = None
            continue
        window = px_arr[lo:hi]
        entry_px = float(r["buy_px"])
        if entry_px <= 0:
            r["mfe_bps"] = None
            r["mae_bps"] = None
            r["capture_pct"] = None
            continue
        if r["direction"] == "long":
            mfe = (float(window.max()) - entry_px) / entry_px * 1e4
            mae = (float(window.min()) - entry_px) / entry_px * 1e4
        else:  # short
            mfe = (entry_px - float(window.min())) / entry_px * 1e4
            mae = (entry_px - float(window.max())) / entry_px * 1e4
        r["mfe_bps"] = round(mfe, 2)
        r["mae_bps"] = round(mae, 2)
        # capture_pct: how much of the peak did we realize?  mfe=0 → undefined
        if mfe > 1e-6:
            r["capture_pct"] = round(r["net_bps"] / mfe * 100, 1)
        else:
            r["capture_pct"] = None


def _compute_summary(roundtrips: list[dict]) -> dict:
    if not roundtrips:
        return {"total_roundtrips": 0}
    wins = [r for r in roundtrips if r["result"] == "WIN"]
    losses = [r for r in roundtrips if r["result"] == "LOSS"]
    tag_groups = defaultdict(list)
    for r in roundtrips:
        tag_groups[r["exit_tag"]].append(r)
    tag_breakdown = {
        tag: {
            "total": len(rs),
            "wins": sum(1 for r in rs if r["result"] == "WIN"),
            "losses": sum(1 for r in rs if r["result"] == "LOSS"),
            "avg_net_bps": round(sum(r["net_bps"] for r in rs) / len(rs), 2),
        } for tag, rs in sorted(tag_groups.items())
    }
    # Give-back aggregates (requires mfe_bps field — may be absent on older data).
    mfe_vals = [r["mfe_bps"] for r in roundtrips if r.get("mfe_bps") is not None]
    mae_vals = [r["mae_bps"] for r in roundtrips if r.get("mae_bps") is not None]
    capture_vals = [r["capture_pct"] for r in roundtrips if r.get("capture_pct") is not None]
    # "missed profit" = sum over trades where realized < MFE − 50 bps
    missed = [
        max(0.0, (r["mfe_bps"] - r["net_bps"]))
        for r in roundtrips
        if r.get("mfe_bps") is not None and r["mfe_bps"] > 50
    ]
    # Give-back trades: wins that gave up >= 50% of MFE, or losses that had MFE > 100 bps
    give_back_trades = [
        r for r in roundtrips
        if r.get("mfe_bps") is not None
        and r["mfe_bps"] > 100
        and (r["result"] == "LOSS" or (r.get("capture_pct") is not None and r["capture_pct"] < 50))
    ]
    give_back_summary = None
    if mfe_vals:
        give_back_summary = {
            "avg_mfe_bps": round(float(np.mean(mfe_vals)), 2),
            "avg_mae_bps": round(float(np.mean(mae_vals)), 2),
            "avg_capture_pct": round(float(np.mean(capture_vals)), 1) if capture_vals else None,
            "sum_missed_profit_bps": round(float(sum(missed)), 2),
            "n_give_back_trades": len(give_back_trades),
        }

    return {
        "total_roundtrips": len(roundtrips),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(roundtrips) * 100, 2),
        "avg_net_pnl": round(np.mean([r["net_pnl"] for r in roundtrips]), 2),
        "avg_net_bps": round(np.mean([r["net_bps"] for r in roundtrips]), 2),
        "avg_net_bps_wins": round(np.mean([r["net_bps"] for r in wins]), 2) if wins else None,
        "avg_net_bps_losses": round(np.mean([r["net_bps"] for r in losses]), 2) if losses else None,
        "avg_hold_sec_wins": round(np.mean([r["hold_sec"] for r in wins])) if wins else None,
        "avg_hold_sec_losses": round(np.mean([r["hold_sec"] for r in losses])) if losses else None,
        "exit_tag_breakdown": tag_breakdown,
        "give_back_summary": give_back_summary,
    }


def _write_md(strat_id: str, roundtrips: list, summary: dict, out: Path):
    lines = [f"# Bar Trace Analysis: {strat_id}", "",
             f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | total_roundtrips: {summary.get('total_roundtrips', 0)}", ""]
    if summary.get("total_roundtrips", 0) == 0:
        lines.append("_No roundtrips._")
        out.write_text("\n".join(lines))
        return
    lines += ["## Summary", "",
              "| Metric | Value |", "|---|---|",
              f"| Total roundtrips | {summary['total_roundtrips']} |",
              f"| WIN / LOSS | {summary['wins']} / {summary['losses']} ({summary['win_rate_pct']:.1f}%) |",
              f"| Avg net bps | {summary.get('avg_net_bps', 0):+.2f} |",
              f"| Avg net bps (WIN) | {summary.get('avg_net_bps_wins') or 0:+.2f} |",
              f"| Avg net bps (LOSS) | {summary.get('avg_net_bps_losses') or 0:+.2f} |",
              f"| Avg hold WIN | {_fmt_hold(summary['avg_hold_sec_wins']) if summary.get('avg_hold_sec_wins') else '-'} |",
              f"| Avg hold LOSS | {_fmt_hold(summary['avg_hold_sec_losses']) if summary.get('avg_hold_sec_losses') else '-'} |",
              ""]
    lines += ["## Exit Tag Breakdown", "",
              "| tag | total | WIN | LOSS | avg_net_bps |", "|---|---|---|---|---|"]
    for tag, info in summary.get("exit_tag_breakdown", {}).items():
        lines.append(f"| {tag} | {info['total']} | {info['wins']} | {info['losses']} | {info['avg_net_bps']:+.2f} |")
    # Give-back summary (MFE/MAE aggregate) — helps critic see trajectory leakage
    gb = summary.get("give_back_summary")
    if gb:
        lines += ["## Give-Back Summary (MFE / MAE)", "",
                  "| Metric | Value | 해석 |", "|---|---|---|",
                  f"| Avg MFE (peak profit during hold) | {gb['avg_mfe_bps']:+.2f} bps | — |",
                  f"| Avg MAE (worst drawdown during hold) | {gb['avg_mae_bps']:+.2f} bps | — |",
                  f"| Avg capture_pct | {gb['avg_capture_pct'] if gb['avg_capture_pct'] is not None else '-'}% | 100% = 피크 완전 캡처; < 50% = give-back 패턴 |",
                  f"| Sum of missed profit | {gb['sum_missed_profit_bps']:+.2f} bps | MFE − realized 합계. 크면 exit 재설계 신호. |",
                  f"| n_give_back_trades | {gb['n_give_back_trades']} / {summary['total_roundtrips']} | MFE > 100 bps 였으나 LOSS or capture < 50% |",
                  ""]

    lines += ["## Roundtrips", "",
              "| # | sym | buy_time | sell_time | hold | tag | net_bps | mfe_bps | mae_bps | capture% | result |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(roundtrips, 1):
        mfe = f"{r['mfe_bps']:+.1f}" if r.get("mfe_bps") is not None else "-"
        mae = f"{r['mae_bps']:+.1f}" if r.get("mae_bps") is not None else "-"
        cap = f"{r['capture_pct']:+.0f}%" if r.get("capture_pct") is not None else "-"
        lines.append(f"| {i} | {r['symbol']} | {r['buy_time']} | {r['sell_time']} | {r['hold']} | {r['exit_tag']} | {r['net_bps']:+.2f} | {mfe} | {mae} | {cap} | {r['result']} |")
    lines.append("")
    out.write_text("\n".join(lines))


def _render_html(strat_dir: Path, report: dict, trace: dict):
    """Simple Plotly HTML report for bar strategies."""
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                         subplot_titles=("Price + fills", "Equity", "Drawdown %"),
                         vertical_spacing=0.06, row_heights=[0.5, 0.25, 0.25])

    sym = list(trace["mid_series"].keys())[0]
    series = trace["mid_series"][sym]
    xs = [pd.to_datetime(s[0], unit="ns").strftime("%Y-%m-%d") for s in series]
    ys = [s[1] for s in series]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=sym,
                             line=dict(color="#2563eb", width=1.2)), row=1, col=1)

    buys = [f for f in trace["fills"] if f["side"] == "BUY"]
    sells = [f for f in trace["fills"] if f["side"] == "SELL"]
    if buys:
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(f["ts_ns"], unit="ns").strftime("%Y-%m-%d") for f in buys],
            y=[f["avg_price"] for f in buys], mode="markers", name="BUY",
            marker=dict(symbol="triangle-up", size=10, color="#16a34a"),
        ), row=1, col=1)
    if sells:
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(f["ts_ns"], unit="ns").strftime("%Y-%m-%d") for f in sells],
            y=[f["avg_price"] for f in sells], mode="markers", name="SELL",
            marker=dict(symbol="triangle-down", size=10, color="#dc2626"),
        ), row=1, col=1)

    eq = trace["equity_curve"]
    eq_x = [pd.to_datetime(e[0], unit="ns").strftime("%Y-%m-%d") for e in eq]
    eq_y = [e[1] for e in eq]
    fig.add_trace(go.Scatter(x=eq_x, y=eq_y, mode="lines", name="Equity",
                             line=dict(color="#1f4d8b")), row=2, col=1)
    equity = np.array(eq_y)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak != 0, peak, 1) * 100
    fig.add_trace(go.Scatter(x=eq_x, y=dd.tolist(), mode="lines", name="DD",
                             fill="tozeroy", line=dict(color="#dc2626")), row=3, col=1)

    fig.update_layout(
        height=820, margin=dict(l=60, r=20, t=60, b=40),
        title=f"{strat_dir.name} — Return {report['return_pct']:+.2f}% · Sharpe {report['sharpe_annualized']:+.2f} · MDD {report['mdd_pct']:+.2f}%",
        plot_bgcolor="white", paper_bgcolor="white",
    )
    html = fig.to_html(include_plotlyjs="cdn", full_html=True)
    (strat_dir / "report.html").write_text(html)


def _render_png(strat_dir: Path, trace: dict, equity_curve: list):
    """Simple static PNG snapshot for quick preview."""
    eq_y = [e[1] for e in equity_curve]
    equity = np.array(eq_y)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak != 0, peak, 1) * 100

    fig, axes = plt.subplots(2, 1, figsize=(10, 5), constrained_layout=True)
    axes[0].plot(equity, color="#1f4d8b")
    axes[0].set_ylabel("Equity")
    axes[0].set_title(strat_dir.name)
    axes[0].grid(True, linestyle=":", alpha=0.4)
    axes[1].fill_between(range(len(dd)), dd, 0, color="#dc2626", alpha=0.3)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(True, linestyle=":", alpha=0.4)
    fig.savefig(strat_dir / "equity_dd.png", dpi=140)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="Single strategy id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--split", default="full", choices=["is", "oos", "full"])
    args = ap.parse_args()

    if args.all:
        ids = sorted(d.name for d in STRATEGIES_DIR.iterdir()
                      if d.is_dir() and d.name.startswith("bar_"))
    elif args.id:
        ids = [args.id]
    else:
        ap.error("specify --id or --all")

    for sid in ids:
        d = STRATEGIES_DIR / sid
        try:
            r = run_full(d, split=args.split)
            print(f"  {sid}: ret={r['return_pct']:+.2f}% sharpe={r['sharpe_annualized']:+.2f} "
                  f"MDD={r['mdd_pct']:+.2f}% RT={r['n_roundtrips']}")
        except Exception as e:
            print(f"  {sid}: FAILED — {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
