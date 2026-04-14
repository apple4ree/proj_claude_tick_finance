"""Tick-level backtest simulator.

Self-contained matching engine, fee/latency model, portfolio bookkeeper,
and backtester orchestrator. Built for H0STASP0 10-level order book data.

Design decisions (Phase 3):
- **Taker-only** orders (MARKET or marketable LIMIT). Resting limit orders
  require a queue-position model that tick data alone cannot support
  faithfully; deferred until real trade-print data is integrated.
- **Latency**: orders submitted at tick T are matched against the order
  book at the first tick whose ts >= T + submit_latency. No lookahead.
- **Fee model**: KRX — commission (bps, both sides) + transaction tax
  (bps, sells only).
- **Portfolio**: single pooled cash, per-symbol positions, avg-cost basis
  for realized PnL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

import numpy as np

from engine.data_loader import OrderBookSnapshot, iter_events
from engine.metrics import BacktestReport, SymbolResult


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

BUY = "BUY"
SELL = "SELL"
MARKET = "MARKET"
LIMIT = "LIMIT"


@dataclass
class Order:
    symbol: str
    side: str   # BUY | SELL
    qty: int
    order_type: str = MARKET  # MARKET | LIMIT
    limit_price: int | None = None
    tag: str = ""


@dataclass
class Fill:
    ts_ns: int
    symbol: str
    side: str
    qty: int
    avg_price: float
    fee: float
    tag: str = ""


# ---------------------------------------------------------------------------
# Fee / latency
# ---------------------------------------------------------------------------

@dataclass
class FeeModel:
    commission_bps: float = 1.5       # both sides
    tax_bps: float = 18.0             # sells only (KOSPI 0.18%)

    def compute(self, side: str, qty: int, price: float) -> float:
        notional = float(qty) * float(price)
        fee = notional * self.commission_bps / 1e4
        if side == SELL:
            fee += notional * self.tax_bps / 1e4
        return fee


@dataclass
class LatencyModel:
    submit_ms: float = 5.0
    jitter_ms: float = 1.0
    seed: int | None = 42

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.seed)

    def sample_ns(self) -> int:
        if self.jitter_ms <= 0:
            return int(self.submit_ms * 1e6)
        val = self.submit_ms + float(self._rng.normal(0.0, self.jitter_ms))
        return int(max(0.0, val) * 1e6)


# ---------------------------------------------------------------------------
# Matching — walk 10-level book
# ---------------------------------------------------------------------------

def walk_book(snap: OrderBookSnapshot, side: str, qty: int) -> tuple[int, float]:
    """Walk levels to fill `qty` on a taker order. Returns (filled, avg_px)."""
    if side == BUY:
        prices, quantities = snap.ask_px, snap.ask_qty
    else:
        prices, quantities = snap.bid_px, snap.bid_qty

    remaining = int(qty)
    total_cost = 0.0
    total_filled = 0
    for lvl in range(len(prices)):
        p = int(prices[lvl])
        q = int(quantities[lvl])
        if p <= 0 or q <= 0:
            continue
        take = min(q, remaining)
        total_cost += take * p
        total_filled += take
        remaining -= take
        if remaining <= 0:
            break
    if total_filled == 0:
        return 0, 0.0
    return total_filled, total_cost / total_filled


def is_marketable(snap: OrderBookSnapshot, side: str, limit_price: int | None) -> bool:
    if limit_price is None:
        return True
    if side == BUY:
        best_ask = int(snap.ask_px[0])
        return best_ask > 0 and limit_price >= best_ask
    best_bid = int(snap.bid_px[0])
    return best_bid > 0 and limit_price <= best_bid


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@dataclass
class Position:
    qty: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Portfolio:
    starting_cash: float
    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    total_fees: float = 0.0
    n_trades: int = 0
    fills: list[Fill] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = self.starting_cash

    def _pos(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position()
        return self.positions[symbol]

    def apply_fill(self, fill: Fill) -> None:
        pos = self._pos(fill.symbol)
        notional = fill.avg_price * fill.qty
        if fill.side == BUY:
            new_qty = pos.qty + fill.qty
            if new_qty != 0:
                pos.avg_cost = (pos.avg_cost * pos.qty + notional) / new_qty
            pos.qty = new_qty
            self.cash -= notional
        else:  # SELL
            pos.realized_pnl += (fill.avg_price - pos.avg_cost) * fill.qty
            pos.qty -= fill.qty
            self.cash += notional
            if pos.qty == 0:
                pos.avg_cost = 0.0
        self.cash -= fill.fee
        self.total_fees += fill.fee
        self.n_trades += 1
        self.fills.append(fill)

    def mark_to_mid(self, last_mids: dict[str, float]) -> float:
        unrealized = 0.0
        for sym, pos in self.positions.items():
            mid = last_mids.get(sym, pos.avg_cost)
            unrealized += (mid - pos.avg_cost) * pos.qty
        return unrealized

    def total_equity(self, last_mids: dict[str, float]) -> float:
        """Cash + mark-to-mid value of open positions. Starting_cash = flat no-position equity."""
        val = self.cash
        for sym, pos in self.positions.items():
            if pos.qty != 0:
                mid = last_mids.get(sym, pos.avg_cost)
                val += pos.qty * mid
        return val

    def total_pnl(self, last_mids: dict[str, float]) -> float:
        realized = sum(p.realized_pnl for p in self.positions.values())
        return realized + self.mark_to_mid(last_mids) - self.total_fees + 0.0


# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------

class Strategy(Protocol):
    def on_tick(self, snap: OrderBookSnapshot, ctx: "Context") -> list[Order]:
        ...


@dataclass
class Context:
    portfolio: Portfolio
    last_mids: dict[str, float]
    current_ts_ns: int = 0


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    starting_cash: float = 10_000_000.0
    fee_model: FeeModel = field(default_factory=FeeModel)
    latency_model: LatencyModel = field(default_factory=LatencyModel)
    regular_only: bool = True
    trace_every: int = 500  # sample equity/mid every N global events


@dataclass
class _PendingOrder:
    target_ts_ns: int
    order: Order


class Backtester:
    def __init__(
        self,
        dates: Iterable[str],
        symbols: Iterable[str],
        strategy: Strategy,
        config: BacktestConfig | None = None,
    ) -> None:
        self.dates = list(dates)
        self.symbols = [str(s).zfill(6) for s in symbols]
        self.strategy = strategy
        self.config = config or BacktestConfig()
        self.portfolio = Portfolio(starting_cash=self.config.starting_cash)
        self.pending: list[_PendingOrder] = []
        self.last_mids: dict[str, float] = {}
        self.per_symbol: dict[str, SymbolResult] = {s: SymbolResult(symbol=s) for s in self.symbols}
        self.total_events = 0
        # Principle-enforcement counters
        self.n_partial_fills = 0
        self.rejected: dict[str, int] = {
            "cash": 0,              # BUY rejected: notional + fee > cash
            "short": 0,             # SELL rejected: insufficient long position
            "no_liquidity": 0,      # book empty → walk_book returned 0
            "non_marketable": 0,    # LIMIT order that was never marketable
        }
        # Trace samples for HTML rendering (kept in memory; serialized by runner)
        self.equity_samples: list[tuple[int, float]] = []
        self.mid_samples: dict[str, list[tuple[int, float]]] = {}

    def _match_pending(self, snap: OrderBookSnapshot) -> None:
        if not self.pending:
            return
        still: list[_PendingOrder] = []
        for p in self.pending:
            if p.target_ts_ns > snap.ts_ns:
                still.append(p)
                continue
            if p.order.symbol != snap.symbol:
                # We can only fill against the current symbol's book; requeue.
                still.append(p)
                continue
            order = p.order

            if order.order_type == LIMIT and not is_marketable(snap, order.side, order.limit_price):
                # Taker-only simplification: drop non-marketable limits.
                self.rejected["non_marketable"] += 1
                continue

            # Pre-matching inventory check for SELLs: long-only — no naked shorts.
            if order.side == SELL:
                pos = self.portfolio.positions.get(order.symbol)
                pos_qty = pos.qty if pos else 0
                if pos_qty < order.qty:
                    self.rejected["short"] += 1
                    continue

            filled_qty, avg_px = walk_book(snap, order.side, order.qty)
            if filled_qty <= 0:
                self.rejected["no_liquidity"] += 1
                continue

            fee = self.config.fee_model.compute(order.side, filled_qty, avg_px)

            # Cash check for BUYs — no overdraft / no implicit leverage.
            if order.side == BUY:
                cost = filled_qty * avg_px + fee
                if cost > self.portfolio.cash:
                    self.rejected["cash"] += 1
                    continue

            if filled_qty < order.qty:
                self.n_partial_fills += 1

            fill = Fill(
                ts_ns=snap.ts_ns,
                symbol=order.symbol,
                side=order.side,
                qty=filled_qty,
                avg_price=avg_px,
                fee=fee,
                tag=order.tag,
            )
            self.portfolio.apply_fill(fill)
        self.pending = still

    def run(self) -> BacktestReport:
        import time
        t0 = time.time()
        trace_every = max(1, int(self.config.trace_every))
        for date in self.dates:
            for snap in iter_events(date, self.symbols, regular_only=self.config.regular_only):
                self.total_events += 1
                self.last_mids[snap.symbol] = snap.mid

                sr = self.per_symbol[snap.symbol]
                if sr.n_events == 0:
                    sr.first_mid = snap.mid
                    sr.first_ts_ns = snap.ts_ns
                sr.last_mid = snap.mid
                sr.last_ts_ns = snap.ts_ns
                sr.n_events += 1

                # 1) settle any orders whose latency window has elapsed
                self._match_pending(snap)

                # 2) let strategy observe tick
                ctx = Context(
                    portfolio=self.portfolio,
                    last_mids=self.last_mids,
                    current_ts_ns=snap.ts_ns,
                )
                new_orders = self.strategy.on_tick(snap, ctx)
                for order in new_orders or []:
                    target = snap.ts_ns + self.config.latency_model.sample_ns()
                    self.pending.append(_PendingOrder(target_ts_ns=target, order=order))

                # 3) trace sample
                if self.total_events % trace_every == 0:
                    self.equity_samples.append(
                        (snap.ts_ns, self.portfolio.total_equity(self.last_mids))
                    )
                    self.mid_samples.setdefault(snap.symbol, []).append(
                        (snap.ts_ns, float(snap.mid))
                    )

        # Realize per-symbol results
        for sym, sr in self.per_symbol.items():
            pos = self.portfolio.positions.get(sym)
            if pos is not None:
                sr.position = pos.qty
                sr.realized_pnl = pos.realized_pnl
                mid = self.last_mids.get(sym, pos.avg_cost)
                sr.mark_to_mid_pnl = (mid - pos.avg_cost) * pos.qty if pos.qty else 0.0

        report = BacktestReport(
            spec_name="",
            symbols=self.symbols,
            dates=self.dates,
            total_events=self.total_events,
            per_symbol=self.per_symbol,
        )
        report.total_pnl = self.portfolio.total_pnl(self.last_mids)
        report.duration_sec = time.time() - t0
        report.n_partial_fills = self.n_partial_fills
        report.pending_at_end = len(self.pending)
        report.rejected = dict(self.rejected)
        return report


# ---------------------------------------------------------------------------
# Built-in dummy strategies (for Phase 3 validation; replaced in Phase 4)
# ---------------------------------------------------------------------------

class BuyHoldStrategy:
    """Market-buy 1 share of each symbol on its first tick, hold."""

    def __init__(self, qty: int = 1) -> None:
        self.qty = qty
        self._bought: set[str] = set()

    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        if snap.symbol in self._bought:
            return []
        self._bought.add(snap.symbol)
        return [Order(symbol=snap.symbol, side=BUY, qty=self.qty, order_type=MARKET, tag="init")]


class AlternatingTakerStrategy:
    """Every `interval` ticks per symbol, alternate BUY/SELL a single share.

    Exercises full matching/fee/portfolio path for validation.
    """

    def __init__(self, interval: int = 5000, qty: int = 1) -> None:
        self.interval = interval
        self.qty = qty
        self._count: dict[str, int] = {}
        self._side_toggle: dict[str, str] = {}

    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        self._count[snap.symbol] = self._count.get(snap.symbol, 0) + 1
        if self._count[snap.symbol] % self.interval != 0:
            return []
        pos = ctx.portfolio.positions.get(snap.symbol)
        if pos is None or pos.qty <= 0:
            side = BUY
        else:
            side = SELL
        return [Order(symbol=snap.symbol, side=side, qty=self.qty, order_type=MARKET, tag="alt")]
