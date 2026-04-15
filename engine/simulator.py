"""Tick-level backtest simulator.

Self-contained matching engine, fee/latency model, portfolio bookkeeper,
and backtester orchestrator. Built for H0STASP0 10-level order book data.

Design decisions (Phase 3):
- **Limit orders**: MARKET and LIMIT both supported.
  - Marketable LIMIT: filled immediately (taker, walks book).
  - Non-marketable LIMIT: queued as a resting order; filled when (a) price
    crosses the limit AND (b) estimated queue_ahead reaches 0.  queue_ahead
    is initialised to the LOB depth at the order's price level (back-of-queue)
    and decremented each tick by the observed depth decrease at that level.
  - Resting limits cancelled at EOD and counted in n_resting_cancelled.
- **Cancel orders**: `Order(symbol, side=None, qty=0, order_type=CANCEL)` is
  a first-class cancel primitive. When on_tick returns a CANCEL order for a
  symbol, ALL resting LIMIT orders (and pending orders not yet matched) for
  that symbol are removed immediately — no latency applied. Use this to clean
  up orphaned resting limits after a stop-market exit fires. Example:
    `Order(sym, side=None, qty=0, order_type=CANCEL, tag="cancel_after_stop")`
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
CANCEL = "CANCEL"  # Cancel all resting LIMIT orders for the given symbol


@dataclass
class Order:
    symbol: str
    side: str | None  # BUY | SELL | None (for CANCEL orders)
    qty: int
    order_type: str = MARKET  # MARKET | LIMIT | CANCEL
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
    context: dict = field(default_factory=dict)  # signal snapshot at fill time


def _snap_context(snap: "OrderBookSnapshot") -> dict:
    """Capture key LOB signal values at fill time for post-analysis."""
    total_bid = int(snap.total_bid_qty)
    total_ask = int(snap.total_ask_qty)
    denom = total_bid + total_ask
    obi = round((total_bid - total_ask) / denom, 4) if denom > 0 else 0.0
    bid0 = int(snap.bid_px[0])
    ask0 = int(snap.ask_px[0])
    spread_bps = round((ask0 - bid0) / bid0 * 1e4, 2) if bid0 > 0 else 0.0
    return {
        "obi": obi,
        "spread_bps": spread_bps,
        "bid_px": bid0,
        "ask_px": ask0,
        "mid": round(float(snap.mid), 2),
        "acml_vol": int(snap.acml_vol),
    }


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


@dataclass
class _RestingOrder:
    """A non-marketable LIMIT order waiting for price to cross its limit.

    queue_ahead tracks the estimated number of shares ahead of this order
    in the queue at its price level.  Initialised to the full LOB depth at
    that level (back-of-queue).  Decremented each tick by the decrease in
    LOB depth at that level (proxy for queue consumption via trades/cancels).
    The order only fills once queue_ahead <= 0 AND the price becomes
    marketable.
    """
    order: Order
    queue_ahead: int      # estimated units still ahead of us
    prev_level_qty: int   # LOB qty at our price level on the previous tick


def _level_qty(snap: "OrderBookSnapshot", side: str, price: int) -> int:
    """Return the displayed LOB quantity at `price` on the given side, or 0."""
    prices = snap.bid_px if side == BUY else snap.ask_px
    qtys   = snap.bid_qty if side == BUY else snap.ask_qty
    for i in range(len(prices)):
        p = int(prices[i])
        if p <= 0:
            break
        if p == price:
            return int(qtys[i])
    return 0


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
        self.resting_limits: list[_RestingOrder] = []  # non-marketable LIMITs with queue model
        self.n_resting_cancelled: int = 0              # resting limits cancelled at EOD
        self.last_mids: dict[str, float] = {}
        self.last_bids: dict[str, float] = {}   # best bid px at last observed tick per symbol
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
                # Non-marketable: queue as resting order with back-of-queue initialisation.
                # queue_ahead = current LOB depth at our price level (all orders placed
                # before ours at the same price).  0 if our price isn't in the book yet
                # (e.g. a SELL LIMIT far above market where we may be first in queue).
                lq = _level_qty(snap, order.side, order.limit_price)
                self.resting_limits.append(
                    _RestingOrder(order=order, queue_ahead=lq, prev_level_qty=lq)
                )
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
                context=_snap_context(snap),
            )
            self.portfolio.apply_fill(fill)
        self.pending = still

    def _check_resting_limits(self, snap: OrderBookSnapshot) -> None:
        """Advance queue model and fill resting limit orders when conditions are met.

        Queue model (back-of-queue, LOB-depth proxy):
          - queue_ahead initialised at order submission to the full LOB depth at the
            order's price level on the same side (BUY → bid depth, SELL → ask depth).
            If the price level isn't in the book yet (e.g. SELL LIMIT far above market),
            queue_ahead = 0 and the order fills as soon as price crosses.
          - Each tick, queue_ahead is decremented by the decrease in LOB depth at that
            price level since the previous tick (proxy for queue consumption by trades /
            cancellations).
          - Fill condition: queue_ahead <= 0  AND  is_marketable.
          - Fill price = limit_price (maker, no book walk).
        """
        if not self.resting_limits:
            return
        remaining: list[_RestingOrder] = []
        for ro in self.resting_limits:
            order = ro.order
            if order.symbol != snap.symbol:
                remaining.append(ro)
                continue

            # --- Update queue_ahead via LOB depth change at our price level ---
            curr_qty = _level_qty(snap, order.side, order.limit_price)
            depth_drop = ro.prev_level_qty - curr_qty
            if depth_drop > 0:
                ro.queue_ahead = max(0, ro.queue_ahead - depth_drop)
            ro.prev_level_qty = curr_qty

            # --- Check fill conditions ---
            if not is_marketable(snap, order.side, order.limit_price):
                remaining.append(ro)
                continue
            if ro.queue_ahead > 0:
                remaining.append(ro)
                continue

            # Fill at limit_price (maker, no book walk)
            filled_qty = order.qty
            avg_px = float(order.limit_price)

            if order.side == SELL:
                pos = self.portfolio.positions.get(order.symbol)
                pos_qty = pos.qty if pos else 0
                if pos_qty < filled_qty:
                    self.rejected["short"] += 1
                    continue

            fee = self.config.fee_model.compute(order.side, filled_qty, avg_px)

            if order.side == BUY:
                cost = filled_qty * avg_px + fee
                if cost > self.portfolio.cash:
                    self.rejected["cash"] += 1
                    continue

            fill = Fill(
                ts_ns=snap.ts_ns,
                symbol=order.symbol,
                side=order.side,
                qty=filled_qty,
                avg_price=avg_px,
                fee=fee,
                tag=order.tag,
                context=_snap_context(snap),
            )
            self.portfolio.apply_fill(fill)
        self.resting_limits = remaining

    def _eod_close(self, last_ts_ns: int) -> None:
        """Force-close all open long positions at end of day.

        Cancels pending orders first, then creates synthetic fills at the last
        known best-bid price for every symbol with qty > 0 (bid side used
        because a forced market sell hits the bid, not the mid).  Falls back
        to mid only when no bid was observed.  Tagged 'exit_eod' so reports
        can distinguish forced closes from strategy-driven exits.
        """
        # Cancel all queued but unfilled orders — they are stale at EOD.
        self.pending.clear()
        self.n_resting_cancelled += len(self.resting_limits)
        self.resting_limits.clear()

        for symbol, pos in list(self.portfolio.positions.items()):
            if pos.qty <= 0:
                continue
            # Use best bid (not mid) — forced market sell hits the bid side,
            # not the theoretical mid.  Fallback to mid only when bid is absent.
            exit_px = self.last_bids.get(symbol) or self.last_mids.get(symbol)
            if exit_px is None:
                continue
            fee = self.config.fee_model.compute(SELL, pos.qty, exit_px)
            fill = Fill(
                ts_ns=last_ts_ns,
                symbol=symbol,
                side=SELL,
                qty=pos.qty,
                avg_price=exit_px,
                fee=fee,
                tag="exit_eod",
            )
            self.portfolio.apply_fill(fill)

    def run(self) -> BacktestReport:
        import time
        t0 = time.time()
        trace_every = max(1, int(self.config.trace_every))
        for date in self.dates:
            last_ts_ns: int = 0
            for snap in iter_events(date, self.symbols, regular_only=self.config.regular_only):
                self.total_events += 1
                self.last_mids[snap.symbol] = snap.mid
                bid0 = float(snap.bid_px[0]) if snap.bid_px[0] > 0 else snap.mid
                self.last_bids[snap.symbol] = bid0
                last_ts_ns = snap.ts_ns

                sr = self.per_symbol[snap.symbol]
                if sr.n_events == 0:
                    sr.first_mid = snap.mid
                    sr.first_ts_ns = snap.ts_ns
                sr.last_mid = snap.mid
                sr.last_ts_ns = snap.ts_ns
                sr.n_events += 1

                # 1) settle any orders whose latency window has elapsed
                self._match_pending(snap)
                # 1b) check resting limit orders for price-crossing fills
                self._check_resting_limits(snap)

                # 2) let strategy observe tick
                ctx = Context(
                    portfolio=self.portfolio,
                    last_mids=self.last_mids,
                    current_ts_ns=snap.ts_ns,
                )
                new_orders = self.strategy.on_tick(snap, ctx)
                for order in new_orders or []:
                    if order.order_type == CANCEL:
                        # Immediate cancel: remove all resting LIMIT orders for this
                        # symbol.  Pending (in-flight, latency-queued) orders are NOT
                        # cleared — a CANCEL targets the resting maker book only.
                        # This preserves co-submitted MARKET orders (e.g., stop-loss
                        # MARKET SELL + CANCEL for orphaned resting LIMIT) from being
                        # accidentally wiped.  No latency applied — cancels in KRX
                        # equity market are near-instant (sub-ms ACK).
                        before = len(self.resting_limits)
                        self.resting_limits = [
                            ro for ro in self.resting_limits
                            if ro.order.symbol != order.symbol
                        ]
                        cancelled = before - len(self.resting_limits)
                        self.n_resting_cancelled += cancelled
                        continue
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

            # End-of-day: force-close all open positions before next date.
            if last_ts_ns:
                self._eod_close(last_ts_ns)

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
        report.n_resting_cancelled = self.n_resting_cancelled
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
