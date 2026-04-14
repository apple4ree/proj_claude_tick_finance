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


def _build_config(spec: StrategySpec) -> BacktestConfig:
    raw = spec.raw
    cap = float(raw.get("capital", 10_000_000))
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
            }
            for f in bt.portfolio.fills
        ],
    }
    (strategy_dir / "trace.json").write_text(json.dumps(trace, ensure_ascii=False))


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
) -> dict:
    """Execute a backtest and persist all stage artifacts.

    Writes (relative to the strategy directory):
        trace.json    — equity curve, mid samples, fills (trace data)
        report.json   — extended metrics payload
        report.html   — interactive Plotly report

    Returns the JSON payload augmented with an `artifacts` block.
    """
    spec_path = Path(spec_path)
    strategy_dir = spec_path.parent
    spec = load_spec(spec_path)
    cfg = _build_config(spec)
    strategy = _build_strategy(spec, spec_path)
    bt = Backtester(
        dates=spec.universe.dates,
        symbols=spec.universe.symbols,
        strategy=strategy,
        config=cfg,
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

    if write_trace:
        _write_trace(bt, strategy_dir)

    report_path = report_out if report_out is not None else strategy_dir / "report.json"
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
    return payload


def run_per_symbol(
    spec_path: Path | str,
    *,
    write_html: bool = True,
    report_out: Path | None = None,
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
    spec_path = Path(spec_path)
    strategy_dir = spec_path.parent
    spec = load_spec(spec_path)
    cfg = _build_config(spec)

    symbols = spec.universe.symbols
    dates = spec.universe.dates

    per_symbol: dict[str, dict] = {}
    per_symbol_traces: dict[str, dict] = {}
    skipped: list[str] = []

    for sym in symbols:
        strategy = _build_strategy(spec, spec_path)
        bt = Backtester(dates=dates, symbols=[sym], strategy=strategy, config=cfg)
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

    report_path = (
        report_out if report_out is not None else strategy_dir / "report_per_symbol.json"
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
    args = ap.parse_args()

    if args.per_symbol:
        payload = run_per_symbol(
            args.spec,
            write_html=not args.no_html,
            report_out=Path(args.out) if args.out else None,
        )
    else:
        payload = run(
            args.spec,
            write_trace=not args.no_trace,
            write_html=not args.no_html,
            report_out=Path(args.out) if args.out else None,
        )
    if args.summary:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
