"""Metric calculators for backtest reports."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class SymbolResult:
    symbol: str
    n_events: int = 0
    first_mid: float = 0.0
    last_mid: float = 0.0
    first_ts_ns: int = 0
    last_ts_ns: int = 0
    position: int = 0
    realized_pnl: float = 0.0
    mark_to_mid_pnl: float = 0.0

    @property
    def buy_hold_return_pct(self) -> float:
        if self.first_mid <= 0:
            return 0.0
        return (self.last_mid - self.first_mid) / self.first_mid * 100.0


@dataclass
class BacktestReport:
    spec_name: str
    symbols: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    total_events: int = 0
    per_symbol: dict[str, SymbolResult] = field(default_factory=dict)
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    n_trades: int = 0
    n_partial_fills: int = 0
    pending_at_end: int = 0
    n_resting_cancelled: int = 0   # resting limit orders cancelled at EOD
    rejected: dict = field(default_factory=dict)
    starting_cash: float = 0.0
    ending_cash: float = 0.0
    return_pct: float = 0.0
    sharpe_raw: float = 0.0
    sharpe_annualized: float = 0.0
    mdd_pct: float = 0.0
    n_roundtrips: int = 0
    win_rate_pct: float = 0.0
    avg_trade_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_win_bps: float = 0.0
    avg_loss_bps: float = 0.0
    duration_sec: float = 0.0
    ic_pearson: float = 0.0
    ic_spearman: float = 0.0
    icir: float = 0.0
    icir_chunks: int = 0
    information_ratio: float = 0.0
    ic_n: int = 0
    invariant_violations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "spec_name": self.spec_name,
            "symbols": self.symbols,
            "dates": self.dates,
            "total_events": self.total_events,
            "total_pnl": round(self.total_pnl, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "unrealized_pnl": round(self.unrealized_pnl, 4),
            "total_fees": round(self.total_fees, 4),
            "n_trades": self.n_trades,
            "n_partial_fills": self.n_partial_fills,
            "pending_at_end": self.pending_at_end,
            "n_resting_cancelled": self.n_resting_cancelled,
            "rejected": dict(self.rejected),
            "starting_cash": round(self.starting_cash, 2),
            "ending_cash": round(self.ending_cash, 2),
            "return_pct": round(self.return_pct, 4),
            "sharpe_raw": round(self.sharpe_raw, 4),
            "sharpe_annualized": round(self.sharpe_annualized, 4),
            "mdd_pct": round(self.mdd_pct, 4),
            "n_roundtrips": self.n_roundtrips,
            "win_rate_pct": round(self.win_rate_pct, 3),
            "avg_trade_pnl": round(self.avg_trade_pnl, 4),
            "best_trade": round(self.best_trade, 4),
            "worst_trade": round(self.worst_trade, 4),
            "avg_win_bps": round(self.avg_win_bps, 2),
            "avg_loss_bps": round(self.avg_loss_bps, 2),
            "duration_sec": round(self.duration_sec, 3),
            "ic_pearson": round(self.ic_pearson, 4),
            "ic_spearman": round(self.ic_spearman, 4),
            "icir": round(self.icir, 4),
            "icir_chunks": self.icir_chunks,
            "information_ratio": round(self.information_ratio, 4),
            "ic_n": self.ic_n,
            "invariant_violations": list(self.invariant_violations),
            "invariant_violation_count": len(self.invariant_violations),
            "invariant_violation_by_type": self._group_violations(),
            "per_symbol": {
                s: {
                    "n_events": r.n_events,
                    "first_mid": r.first_mid,
                    "last_mid": r.last_mid,
                    "position": r.position,
                    "realized_pnl": round(r.realized_pnl, 4),
                    "mark_to_mid_pnl": round(r.mark_to_mid_pnl, 4),
                    "buy_hold_return_pct": round(r.buy_hold_return_pct, 4),
                }
                for s, r in self.per_symbol.items()
            },
        }

    def _group_violations(self) -> dict[str, int]:
        grouped: dict[str, int] = {}
        for v in self.invariant_violations:
            t = v.get("invariant_type", "unknown") if isinstance(v, dict) else "unknown"
            grouped[t] = grouped.get(t, 0) + 1
        return grouped


# ---------------------------------------------------------------------------
# Stat helpers (computed by runner, not by Backtester)
# ---------------------------------------------------------------------------


def compute_sharpe_mdd(equity_samples: list[tuple[int, float]]) -> dict:
    """Sharpe from per-sample equity returns and max drawdown percent.

    `sharpe_raw` is mean/std of per-sample returns (no time scaling).
    `sharpe_annualized` scales raw by sqrt(252) assuming the samples span
    a single trading day — useful as a directional indicator, not a
    calibrated risk-adjusted return.
    """
    if len(equity_samples) < 2:
        return {"sharpe_raw": 0.0, "sharpe_annualized": 0.0, "mdd_pct": 0.0}
    import numpy as np

    equity = np.array([e for _, e in equity_samples], dtype=np.float64)
    denom = np.where(equity[:-1] != 0, equity[:-1], 1.0)
    rets = np.diff(equity) / denom
    mean = float(rets.mean())
    std = float(rets.std())
    sharpe_raw = mean / std if std > 1e-12 else 0.0
    sharpe_annualized = sharpe_raw * math.sqrt(252.0)

    peak = np.maximum.accumulate(equity)
    peak_safe = np.where(peak != 0, peak, 1.0)
    dd = (equity - peak) / peak_safe
    mdd_pct = float(dd.min()) * 100.0

    return {
        "sharpe_raw": sharpe_raw,
        "sharpe_annualized": sharpe_annualized,
        "mdd_pct": mdd_pct,
    }


def compute_trade_stats(fills: Iterable) -> dict:
    """FIFO-match BUY/SELL layers per symbol; return per-roundtrip stats.

    Each closed roundtrip's PnL = (sell_px - buy_px) * qty − proportional
    commission/tax. Produces win_rate, avg/best/worst trade.

    Also computes avg_win_bps and avg_loss_bps: fee-adjusted net PnL divided
    by buy-side notional (in basis points). These are the canonical diagnostic
    metrics for resting-limit strategies where time-exit paths create a
    left-skewed win distribution that makes win_rate_pct alone misleading.
    A strategy is EV-positive only when avg_win_bps * win_rate > |avg_loss_bps| * loss_rate.
    """
    inventory: dict[str, list[list[float]]] = {}  # sym -> [[qty, px, fee], ...]
    trades: list[float] = []
    trade_bps: list[float] = []  # net PnL / buy notional * 1e4

    for f in fills:
        sym = f.symbol
        side = f.side
        if side == "BUY":
            inventory.setdefault(sym, []).append([float(f.qty), float(f.avg_price), float(f.fee)])
            continue
        # SELL — unwind FIFO
        remaining = float(f.qty)
        sell_px = float(f.avg_price)
        sell_fee = float(f.fee)
        roundtrip_pnl = 0.0
        # proportional sell fee is fully allocated to this roundtrip
        fee_accum = sell_fee
        buy_notional = 0.0  # accumulated buy-side cost basis for bps denominator
        inv = inventory.get(sym, [])
        while remaining > 0 and inv:
            layer = inv[0]
            layer_qty, layer_px, layer_fee = layer[0], layer[1], layer[2]
            take = min(layer_qty, remaining)
            roundtrip_pnl += (sell_px - layer_px) * take
            fee_share = (layer_fee / layer_qty) * take if layer_qty > 0 else 0.0
            fee_accum += fee_share
            buy_notional += layer_px * take
            layer[0] -= take
            layer[2] -= fee_share
            remaining -= take
            if layer[0] <= 1e-9:
                inv.pop(0)
        net = roundtrip_pnl - fee_accum
        trades.append(net)
        bps = (net / buy_notional * 1e4) if buy_notional > 0 else 0.0
        trade_bps.append(bps)

    n = len(trades)
    if n == 0:
        return {
            "n_roundtrips": 0,
            "win_rate_pct": 0.0,
            "avg_trade_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_win_bps": 0.0,
            "avg_loss_bps": 0.0,
        }
    wins = sum(1 for t in trades if t > 0)
    win_bps_list = [b for b in trade_bps if b > 0]
    loss_bps_list = [b for b in trade_bps if b <= 0]
    avg_win_bps = sum(win_bps_list) / len(win_bps_list) if win_bps_list else 0.0
    avg_loss_bps = sum(loss_bps_list) / len(loss_bps_list) if loss_bps_list else 0.0
    return {
        "n_roundtrips": n,
        "win_rate_pct": wins / n * 100.0,
        "avg_trade_pnl": sum(trades) / n,
        "best_trade": max(trades),
        "worst_trade": min(trades),
        "avg_win_bps": round(avg_win_bps, 2),
        "avg_loss_bps": round(avg_loss_bps, 2),
    }
