"""Backtest runner.

Loads a YAML spec, instantiates a strategy, and drives the Backtester.

Three strategy dispatch modes based on `strategy_kind` in spec.yaml:
- `dsl` (default): interpret declarative signals/entry/exit via SpecStrategy.
- `python`: dynamically import `strategies/<id>/strategy.py` and use its
  `Strategy` class. For stateful logic beyond the DSL (state machines,
  inventory models, multi-stage entries/exits).
- `buyhold` / `alternating`: built-in dummies for pipeline validation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from dataclasses import asdict

from engine.dsl import SpecStrategy
from engine.metrics import compute_sharpe_mdd, compute_trade_stats
from engine.report_html import render as render_html, render_per_symbol as render_html_per_symbol
from engine.simulator import (
    AlternatingTakerStrategy,
    BacktestConfig,
    Backtester,
    BuyHoldStrategy,
    FeeModel,
    LatencyModel,
    Strategy,
)
from engine.spec import StrategySpec, load_spec


def _resolve_time_window(spec: StrategySpec) -> tuple[int, int] | None:
    """Convert spec.universe.time_window ISO strings → (start_ns, end_ns).

    Returns None unless both start and end are specified (LOB mode). Supports
    any format pandas.Timestamp accepts ('2026-04-19T06:00:00', '2026-04-19 06:00').
    Treats as UTC when no timezone is supplied.
    """
    s = spec.universe.time_window_start
    e = spec.universe.time_window_end
    if not s or not e:
        return None
    import pandas as pd
    start_ns = int(pd.Timestamp(s, tz="UTC").value)
    end_ns = int(pd.Timestamp(e, tz="UTC").value)
    if start_ns >= end_ns:
        raise ValueError(
            f"universe.time_window invalid: start={s} >= end={e}"
        )
    return (start_ns, end_ns)


def _build_config(spec: StrategySpec) -> BacktestConfig:
    """Build a BacktestConfig from the raw spec dict.

    Capital auto-scaling for ``market: crypto_lob``: snapshots carry int64
    prices scaled by ``CRYPTO_PRICE_SCALE = 1e8`` (see engine/data_loader.py).
    `starting_cash` and per-order notional share that unit, so a spec that
    declares a human-unit figure (e.g. ``capital: 100000`` meaning $100k USD)
    must be multiplied by the same scale factor before the backtester sees
    it — otherwise every MARKET BUY is instantly rejected for lack of cash.

    Detection heuristic: if ``market == "crypto_lob"`` and ``capital`` is in
    the human range (≤ 1e9), treat it as real USD and multiply. Authors who
    already pass a pre-scaled value (> 1e9) are respected unchanged. Emits
    a one-line stderr note so the adjustment is visible in the pipeline log.
    """
    from engine.data_loader import CRYPTO_PRICE_SCALE

    raw = spec.raw
    cap_raw = float(raw.get("capital", 10_000_000))
    market = (raw.get("universe") or {}).get("market", "") or spec.universe.market

    cap = cap_raw
    if market == "crypto_lob" and cap_raw <= 1e9:
        cap = cap_raw * float(CRYPTO_PRICE_SCALE)
        print(
            f"[runner] crypto_lob: auto-scaled capital {cap_raw:.4g} × "
            f"CRYPTO_PRICE_SCALE ({CRYPTO_PRICE_SCALE}) = {cap:.4g}"
        )

    fees_cfg = raw.get("fees", {}) or {}
    lat_cfg = raw.get("latency", {}) or {}
    return BacktestConfig(
        starting_cash=cap,
        fee_model=FeeModel(
            commission_bps=float(fees_cfg.get("commission_bps", 1.5)),
            tax_bps=float(fees_cfg.get("tax_bps", 18.0)),
        ),
        latency_model=LatencyModel(
            submit_ms=float(lat_cfg.get("submit_ms", 5.0)),
            jitter_ms=float(lat_cfg.get("jitter_ms", 1.0)),
            seed=lat_cfg.get("seed", 42),
        ),
        regular_only=bool(raw.get("regular_only", True)),
    )


def _load_python_strategy(spec_path: Path, spec: StrategySpec) -> Strategy:
    """Import strategies/<id>/strategy.py and return its Strategy instance."""
    strat_py = Path(spec_path).parent / "strategy.py"
    if not strat_py.exists():
        raise FileNotFoundError(
            f"strategy_kind=python but {strat_py} does not exist"
        )
    module_name = f"user_strategy_{Path(spec_path).parent.name}"
    loader_spec = importlib.util.spec_from_file_location(module_name, strat_py)
    if loader_spec is None or loader_spec.loader is None:
        raise ImportError(f"failed to load spec for {strat_py}")
    module = importlib.util.module_from_spec(loader_spec)
    sys.modules[module_name] = module
    try:
        loader_spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"{strat_py} raised during import: {e}") from e
    if not hasattr(module, "Strategy"):
        raise AttributeError(f"{strat_py} must define a top-level `Strategy` class")
    cls = module.Strategy
    if not callable(getattr(cls, "on_tick", None)):
        raise AttributeError(f"{strat_py}:Strategy must implement on_tick(snap, ctx)")
    return cls(spec.raw)


def _build_strategy(spec: StrategySpec, spec_path: Path | str) -> Strategy:
    """Selects strategy implementation based on spec.strategy_kind.

    Supported values: dsl (default), python, buyhold, alternating.
    """
    kind = spec.raw.get("strategy_kind")
    if kind is None:
        return SpecStrategy(spec)
    kind = str(kind).lower()
    if kind == "dsl":
        return SpecStrategy(spec)
    if kind == "python":
        return _load_python_strategy(Path(spec_path), spec)
    if kind == "buyhold":
        return BuyHoldStrategy(qty=int(spec.raw.get("qty", 1)))
    if kind == "alternating":
        return AlternatingTakerStrategy(
            interval=int(spec.raw.get("interval", 5000)),
            qty=int(spec.raw.get("qty", 1)),
        )
    raise ValueError(f"Unknown strategy_kind: {kind}")


def _write_report_md(payload: dict, strategy_dir: Path) -> None:
    """Write report_summary.md — human+LLM-readable backtest summary.

    Generated alongside report.json / report_per_symbol.json so that agents
    can read structured markdown instead of parsing nested JSON.
    """
    from datetime import datetime as _dt

    mode = payload.get("mode", "single")
    sid  = payload.get("strategy_id") or strategy_dir.name
    name = payload.get("spec_name", "")
    ts   = _dt.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = [
        f"# Backtest Report: {sid}",
        f"",
        f"spec: {name} | mode: {mode} | generated: {ts}",
        "",
    ]

    if mode == "per_symbol":
        # --- per-symbol aggregate ---
        lines += [
            "## Aggregate Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| avg_return_pct | {payload.get('avg_return_pct', 0):+.4f}% |",
            f"| total_roundtrips | {payload.get('total_roundtrips', 0)} |",
            f"| pooled_win_rate_pct | {payload.get('pooled_win_rate_pct', 0):.2f}% |",
            f"| total_fees | {payload.get('total_fees', 0):,.2f} KRW |",
            f"| n_symbols_traded | {payload.get('n_symbols_traded', 0)} |",
            f"| n_symbols_skipped | {payload.get('n_symbols_skipped', 0)} |",
            "",
            "## Per-Symbol Results",
            "",
            "| symbol | return_pct | n_roundtrips | win_rate_pct | total_fees"
            " | best_trade | worst_trade |",
            "|--------|-----------|--------------|--------------|-----------|"
            "------------|-------------|",
        ]
        for sym, s in payload.get("per_symbol", {}).items():
            lines.append(
                f"| {sym} | {s.get('return_pct', 0):+.4f}% | {s.get('n_roundtrips', 0)}"
                f" | {s.get('win_rate_pct', 0):.2f}% | {s.get('total_fees', 0):,.2f}"
                f" | {s.get('best_trade', 0):+,.2f} | {s.get('worst_trade', 0):+,.2f} |"
            )
        skipped = payload.get("skipped_symbols", [])
        if skipped:
            lines += ["", f"Skipped (0 trades): {', '.join(skipped)}"]
    else:
        # --- single-run ---
        rej = payload.get("rejected", {})
        lines += [
            "## Summary Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| return_pct | {payload.get('return_pct', 0):+.4f}% |",
            f"| total_pnl | {payload.get('total_pnl', 0):+,.2f} KRW |",
            f"| realized_pnl | {payload.get('realized_pnl', 0):+,.2f} KRW |",
            f"| total_fees | {payload.get('total_fees', 0):,.2f} KRW |",
            f"| n_roundtrips | {payload.get('n_roundtrips', 0)} |",
            f"| win_rate_pct | {payload.get('win_rate_pct', 0):.3f}% |",
            f"| avg_win_bps | {payload.get('avg_win_bps', 0):+.2f} bps |",
            f"| avg_loss_bps | {payload.get('avg_loss_bps', 0):+.2f} bps |",
            f"| sharpe_raw | {payload.get('sharpe_raw', 0):.4f} |",
            f"| sharpe_annualized | {payload.get('sharpe_annualized', 0):.4f} |",
            f"| mdd_pct | {payload.get('mdd_pct', 0):.4f}% |",
            "",
            "## Status Flags",
            "",
            "| Flag | Count |",
            "|------|-------|",
            f"| partial_fills | {payload.get('n_partial_fills', 0)} |",
            f"| pending_at_end | {payload.get('pending_at_end', 0)} |",
            f"| resting_cancelled | {payload.get('n_resting_cancelled', 0)} |",
            f"| rejected.cash | {rej.get('cash', 0)} |",
            f"| rejected.short | {rej.get('short', 0)} |",
            f"| rejected.no_liquidity | {rej.get('no_liquidity', 0)} |",
            f"| rejected.non_marketable | {rej.get('non_marketable', 0)} |",
        ]

        per_sym = payload.get("per_symbol", {})
        if per_sym:
            lines += [
                "",
                "## Buy-Hold Benchmark (per symbol)",
                "",
                "| symbol | first_mid | last_mid | buy_hold_return_pct |",
                "|--------|-----------|----------|---------------------|",
            ]
            for sym, s in per_sym.items():
                lines.append(
                    f"| {sym} | {s.get('first_mid', 0):,.0f} | {s.get('last_mid', 0):,.0f}"
                    f" | {s.get('buy_hold_return_pct', 0):+.4f}% |"
                )

    lines.append("")
    (strategy_dir / "report_summary.md").write_text("\n".join(lines))


def _write_trace(bt: Backtester, strategy_dir: Path) -> None:
    trace = {
        "equity_curve": [[int(ts), float(eq)] for ts, eq in bt.equity_samples],
        "mid_series": {
            sym: [[int(ts), float(mid)] for ts, mid in series]
            for sym, series in bt.mid_samples.items()
        },
        "fills": [
            {
                "ts_ns": int(f.ts_ns),
                "symbol": f.symbol,
                "side": f.side,
                "qty": int(f.qty),
                "avg_price": float(f.avg_price),
                "fee": float(f.fee),
                "tag": f.tag,
                "context": getattr(f, "context", {}) or {},
            }
            for f in bt.portfolio.fills
        ],
    }
    (strategy_dir / "trace.json").write_text(json.dumps(trace, ensure_ascii=False))


def _compute_roundtrips_with_context(fills: list) -> list[dict]:
    """FIFO BUY→SELL matching per symbol with entry context attached.

    Each returned dict:
      symbol, entry_ts_ns, exit_ts_ns, qty, entry_price, exit_price,
      gross_pnl, net_pnl, pnl_bps, outcome (WIN|LOSS), exit_tag,
      entry_context (LOB signal snapshot at BUY fill time)
    """
    from collections import defaultdict, deque

    buy_queues: dict[str, deque] = defaultdict(deque)
    roundtrips: list[dict] = []

    for f in fills:
        if f.side == "BUY":
            buy_queues[f.symbol].append(f)
        elif f.side == "SELL":
            q = buy_queues[f.symbol]
            if not q:
                continue
            buy_f = q.popleft()
            qty = min(buy_f.qty, f.qty)
            gross_pnl = (f.avg_price - buy_f.avg_price) * qty
            net_pnl = gross_pnl - buy_f.fee - f.fee
            pnl_bps = (
                round((f.avg_price - buy_f.avg_price) / buy_f.avg_price * 1e4, 2)
                if buy_f.avg_price > 0
                else 0.0
            )
            roundtrips.append({
                "symbol": f.symbol,
                "entry_ts_ns": int(buy_f.ts_ns),
                "exit_ts_ns": int(f.ts_ns),
                "qty": int(qty),
                "entry_price": float(buy_f.avg_price),
                "exit_price": float(f.avg_price),
                "gross_pnl": round(float(gross_pnl), 2),
                "net_pnl": round(float(net_pnl), 2),
                "pnl_bps": pnl_bps,
                "outcome": "WIN" if net_pnl > 0 else "LOSS",
                "exit_tag": f.tag,
                "entry_context": getattr(buy_f, "context", {}) or {},
            })
    return roundtrips


def _compute_per_day(fills: list) -> dict[str, dict]:
    """Group fills by KST date and compute daily trading stats.

    Returns {date_str: {n_entries, n_roundtrips, n_wins, n_losses, n_stops, n_eod, net_pnl}}
    """
    from collections import defaultdict
    from datetime import datetime, timezone, timedelta

    _KST = timezone(timedelta(hours=9))

    def _kst_date(ts_ns: int) -> str:
        return datetime.fromtimestamp(ts_ns / 1e9, tz=_KST).strftime("%Y-%m-%d")

    day: dict[str, dict] = defaultdict(
        lambda: {"n_entries": 0, "n_roundtrips": 0, "n_wins": 0, "n_losses": 0,
                 "n_stops": 0, "n_eod": 0, "net_pnl": 0.0}
    )

    # Count entries by entry BUY date
    for f in fills:
        if f.side == "BUY":
            day[_kst_date(f.ts_ns)]["n_entries"] += 1

    # Count roundtrip outcomes by exit date
    for rt in _compute_roundtrips_with_context(fills):
        d = _kst_date(rt["exit_ts_ns"])
        day[d]["n_roundtrips"] += 1
        if rt["outcome"] == "WIN":
            day[d]["n_wins"] += 1
        else:
            day[d]["n_losses"] += 1
        tag_low = rt["exit_tag"].lower()
        if any(k in tag_low for k in ("sl", "stop")):
            day[d]["n_stops"] += 1
        elif "eod" in tag_low:
            day[d]["n_eod"] += 1
        day[d]["net_pnl"] = round(day[d]["net_pnl"] + rt["net_pnl"], 2)

    return dict(sorted(day.items()))


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(p)


def run(
    spec_path: Path | str,
    *,
    write_trace: bool = True,
    write_html: bool = True,
    report_out: Path | None = None,
    strict: bool = False,
) -> dict:
    """Execute a backtest and persist all stage artifacts.

    Writes (relative to the strategy directory):
        trace.json    — equity curve, mid samples, fills (trace data)
        report.json   — extended metrics payload
        report.html   — interactive Plotly report

    Returns the JSON payload augmented with an `artifacts` block.
    """
    import yaml as _yaml
    spec_path = Path(spec_path)
    strategy_dir = spec_path.parent
    spec = load_spec(spec_path)
    cfg = _build_config(spec)
    strategy = _build_strategy(spec, spec_path)
    # Load raw spec as dict for invariant inference
    try:
        with open(spec_path, "r") as _f:
            spec_dict = _yaml.safe_load(_f) or {}
    except Exception:
        spec_dict = {}
    time_window = _resolve_time_window(spec)
    bt = Backtester(
        dates=spec.universe.dates,
        symbols=spec.universe.symbols,
        strategy=strategy,
        config=cfg,
        spec_dict=spec_dict,
        strict_mode=strict,
        market=spec.universe.market,
        time_window=time_window,
    )
    report = bt.run()
    report.spec_name = spec.name
    report.starting_cash = cfg.starting_cash
    report.ending_cash = bt.portfolio.cash
    report.total_fees = bt.portfolio.total_fees
    report.n_trades = bt.portfolio.n_trades
    report.realized_pnl = sum(p.realized_pnl for p in bt.portfolio.positions.values())
    report.unrealized_pnl = bt.portfolio.mark_to_mid(bt.last_mids)
    report.return_pct = (report.total_pnl / cfg.starting_cash) * 100.0

    risk = compute_sharpe_mdd(bt.equity_samples)
    report.sharpe_raw = risk["sharpe_raw"]
    report.sharpe_annualized = risk["sharpe_annualized"]
    report.mdd_pct = risk["mdd_pct"]
    stats = compute_trade_stats(bt.portfolio.fills)
    report.n_roundtrips = stats["n_roundtrips"]
    report.win_rate_pct = stats["win_rate_pct"]
    report.avg_trade_pnl = stats["avg_trade_pnl"]
    report.best_trade = stats["best_trade"]
    report.worst_trade = stats["worst_trade"]
    report.avg_win_bps = stats["avg_win_bps"]
    report.avg_loss_bps = stats["avg_loss_bps"]

    payload = report.to_dict()
    payload["roundtrips"] = _compute_roundtrips_with_context(bt.portfolio.fills)
    payload["per_day"] = _compute_per_day(bt.portfolio.fills)

    if write_trace:
        _write_trace(bt, strategy_dir)

    report_fname = "report_strict.json" if strict else "report.json"
    report_path = report_out if report_out is not None else strategy_dir / report_fname
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    html_path: Path | None = None
    if write_html:
        try:
            html_path = render_html(strategy_dir)
        except Exception as e:
            payload.setdefault("errors", {})["report_html"] = str(e)

    payload["artifacts"] = {
        "spec": _rel(strategy_dir / "spec.yaml") if (strategy_dir / "spec.yaml").exists() else None,
        "strategy_py": _rel(strategy_dir / "strategy.py") if (strategy_dir / "strategy.py").exists() else None,
        "idea_json": _rel(strategy_dir / "idea.json") if (strategy_dir / "idea.json").exists() else None,
        "trace_json": _rel(strategy_dir / "trace.json") if (strategy_dir / "trace.json").exists() else None,
        "report_json": _rel(report_path),
        "report_html": _rel(html_path) if html_path else None,
        "feedback_json": _rel(strategy_dir / "feedback.json") if (strategy_dir / "feedback.json").exists() else None,
    }
    # Re-write report.json with artifacts included
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    _write_report_md(payload, strategy_dir)
    return payload


def run_per_symbol(
    spec_path: Path | str,
    *,
    write_html: bool = True,
    report_out: Path | None = None,
    strict: bool = False,
) -> dict:
    """Run one independent backtest per symbol and aggregate results.

    Each symbol gets a fresh Strategy instance and full starting capital so
    results are not contaminated by cross-symbol capital interactions.

    Aggregate metrics:
        avg_return_pct      — simple mean across symbols (equal-weight)
        total_roundtrips    — sum
        pooled_win_rate_pct — total wins / total roundtrips
        total_fees          — sum
        per_symbol          — per-symbol breakdown dict

    Writes:
        report_per_symbol.json  — aggregate + per-symbol metrics
        trace_per_symbol.json   — equity curves, mid series, fills per symbol
        report_per_symbol.html  — tabbed interactive report (if write_html=True)

    Returns the aggregate payload dict.
    """
    import yaml as _yaml
    spec_path = Path(spec_path)
    strategy_dir = spec_path.parent
    spec = load_spec(spec_path)
    cfg = _build_config(spec)
    # Load raw spec as dict for invariant inference
    try:
        with open(spec_path, "r") as _f:
            spec_dict = _yaml.safe_load(_f) or {}
    except Exception:
        spec_dict = {}

    symbols = spec.universe.symbols
    dates = spec.universe.dates
    market = spec.universe.market
    time_window = _resolve_time_window(spec)

    per_symbol: dict[str, dict] = {}
    per_symbol_traces: dict[str, dict] = {}
    skipped: list[str] = []

    for sym in symbols:
        strategy = _build_strategy(spec, spec_path)
        bt = Backtester(
            dates=dates, symbols=[sym], strategy=strategy,
            config=cfg, spec_dict=spec_dict, strict_mode=strict,
            market=market, time_window=time_window,
        )
        report = bt.run()
        report.starting_cash = cfg.starting_cash
        report.total_fees = bt.portfolio.total_fees
        report.n_trades = bt.portfolio.n_trades
        report.realized_pnl = sum(
            p.realized_pnl for p in bt.portfolio.positions.values()
        )
        report.unrealized_pnl = bt.portfolio.mark_to_mid(bt.last_mids)
        report.return_pct = (report.total_pnl / cfg.starting_cash) * 100.0
        stats = compute_trade_stats(bt.portfolio.fills)

        if stats["n_roundtrips"] == 0:
            skipped.append(sym)
            continue

        per_symbol[sym] = {
            "return_pct": round(report.return_pct, 4),
            "n_roundtrips": stats["n_roundtrips"],
            "win_rate_pct": round(stats["win_rate_pct"], 2),
            "total_fees": round(report.total_fees, 2),
            "best_trade": round(stats["best_trade"], 2),
            "worst_trade": round(stats["worst_trade"], 2),
            "rejected": report.rejected,
        }

        per_symbol_traces[sym] = {
            "equity_curve": [[int(ts), float(eq)] for ts, eq in bt.equity_samples],
            "mid_series": {
                s: [[int(ts), float(mid)] for ts, mid in series]
                for s, series in bt.mid_samples.items()
            },
            "fills": [
                {
                    "ts_ns": int(f.ts_ns),
                    "symbol": f.symbol,
                    "side": f.side,
                    "qty": int(f.qty),
                    "avg_price": float(f.avg_price),
                    "fee": float(f.fee),
                    "tag": f.tag,
                }
                for f in bt.portfolio.fills
            ],
        }

    returns = [v["return_pct"] for v in per_symbol.values()]
    total_roundtrips = sum(v["n_roundtrips"] for v in per_symbol.values())
    total_wins = sum(
        round(v["n_roundtrips"] * v["win_rate_pct"] / 100)
        for v in per_symbol.values()
    )
    pooled_win_rate = (
        total_wins / total_roundtrips * 100 if total_roundtrips > 0 else 0.0
    )

    payload: dict = {
        "strategy_id": strategy_dir.name,
        "spec_name": spec.name,
        "mode": "per_symbol",
        "starting_cash": cfg.starting_cash,
        "n_symbols_traded": len(per_symbol),
        "n_symbols_skipped": len(skipped),
        "skipped_symbols": skipped,
        "avg_return_pct": round(sum(returns) / len(returns), 4) if returns else 0.0,
        "total_roundtrips": total_roundtrips,
        "pooled_win_rate_pct": round(pooled_win_rate, 2),
        "total_fees": round(sum(v["total_fees"] for v in per_symbol.values()), 2),
        "per_symbol": per_symbol,
    }

    report_fname = "report_per_symbol_strict.json" if strict else "report_per_symbol.json"
    report_path = (
        report_out if report_out is not None else strategy_dir / report_fname
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    trace_path = strategy_dir / "trace_per_symbol.json"
    trace_path.write_text(json.dumps(per_symbol_traces, ensure_ascii=False))

    if write_html:
        try:
            render_html_per_symbol(strategy_dir)
        except Exception as e:
            payload.setdefault("errors", {})["report_html"] = str(e)

    _write_report_md(payload, strategy_dir)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="tick strategy backtest runner")
    ap.add_argument("--spec", required=True, help="path to spec YAML")
    ap.add_argument("--out", default=None, help="report output JSON path")
    ap.add_argument("--summary", action="store_true", help="print summary JSON to stdout")
    ap.add_argument("--no-html", action="store_true", help="skip HTML rendering")
    ap.add_argument("--no-trace", action="store_true", help="skip trace.json write")
    ap.add_argument(
        "--per-symbol",
        action="store_true",
        help="run one backtest per symbol and aggregate; writes report_per_symbol.json",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Run with strict mode: engine intervenes to prevent invariant violations",
    )
    args = ap.parse_args()

    if args.per_symbol:
        payload = run_per_symbol(
            args.spec,
            write_html=not args.no_html,
            report_out=Path(args.out) if args.out else None,
            strict=args.strict,
        )
    else:
        payload = run(
            args.spec,
            write_trace=not args.no_trace,
            write_html=not args.no_html,
            report_out=Path(args.out) if args.out else None,
            strict=args.strict,
        )
    if args.summary:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
