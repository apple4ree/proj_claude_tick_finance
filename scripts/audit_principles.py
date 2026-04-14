#!/usr/bin/env python3
"""Empirical audit of backtest principles.

Constructs tiny synthetic OrderBookSnapshot streams, runs strategies through
the Backtester, and asserts that each fundamental backtest principle holds.

Prints PASS/FAIL for each check. Non-zero exit on any FAIL.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np

from engine.data_loader import OrderBookSnapshot
from engine.simulator import (
    BUY,
    LIMIT,
    MARKET,
    SELL,
    Backtester,
    BacktestConfig,
    Context,
    FeeModel,
    LatencyModel,
    Order,
    Portfolio,
    walk_book,
)


def make_snap(
    ts_ns: int,
    symbol: str,
    ask_px: list[int],
    ask_qty: list[int],
    bid_px: list[int],
    bid_qty: list[int],
    acml_vol: int = 0,
) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        ts_ns=ts_ns,
        symbol=symbol,
        ask_px=np.array(ask_px + [0] * (10 - len(ask_px)), dtype=np.int64),
        ask_qty=np.array(ask_qty + [0] * (10 - len(ask_qty)), dtype=np.int64),
        bid_px=np.array(bid_px + [0] * (10 - len(bid_px)), dtype=np.int64),
        bid_qty=np.array(bid_qty + [0] * (10 - len(bid_qty)), dtype=np.int64),
        total_ask_qty=sum(ask_qty),
        total_bid_qty=sum(bid_qty),
        acml_vol=acml_vol,
        session_cls="0",
        antc_px=0,
        antc_qty=0,
    )


class _BacktesterFixture(Backtester):
    """Backtester variant that iterates an in-memory snapshot list."""

    def __init__(
        self,
        snaps: Iterable[OrderBookSnapshot],
        strategy,
        config: BacktestConfig | None = None,
    ) -> None:
        symbols = sorted({s.symbol for s in snaps})
        super().__init__(dates=["fixture"], symbols=symbols, strategy=strategy, config=config)
        self._snaps = list(snaps)

    def run(self):
        import time
        t0 = time.time()
        for snap in self._snaps:
            self.total_events += 1
            self.last_mids[snap.symbol] = snap.mid
            sr = self.per_symbol[snap.symbol]
            if sr.n_events == 0:
                sr.first_mid = snap.mid
                sr.first_ts_ns = snap.ts_ns
            sr.last_mid = snap.mid
            sr.last_ts_ns = snap.ts_ns
            sr.n_events += 1

            self._match_pending(snap)
            self._check_resting_limits(snap)
            ctx = Context(
                portfolio=self.portfolio,
                last_mids=self.last_mids,
                current_ts_ns=snap.ts_ns,
            )
            new_orders = self.strategy.on_tick(snap, ctx)
            for order in new_orders or []:
                target = snap.ts_ns + self.config.latency_model.sample_ns()
                from engine.simulator import _PendingOrder
                self.pending.append(_PendingOrder(target_ts_ns=target, order=order))
        # EOD: cancel resting limits
        self.n_resting_cancelled += len(self.resting_limits)
        self.resting_limits.clear()
        for sym, sr in self.per_symbol.items():
            pos = self.portfolio.positions.get(sym)
            if pos is not None:
                sr.position = pos.qty
                sr.realized_pnl = pos.realized_pnl
                mid = self.last_mids.get(sym, pos.avg_cost)
                sr.mark_to_mid_pnl = (mid - pos.avg_cost) * pos.qty if pos.qty else 0.0
        from engine.metrics import BacktestReport
        rpt = BacktestReport(
            spec_name="fixture",
            symbols=self.symbols,
            dates=self.dates,
            total_events=self.total_events,
            per_symbol=self.per_symbol,
        )
        rpt.total_pnl = self.portfolio.total_pnl(self.last_mids)
        rpt.duration_sec = time.time() - t0
        rpt.n_partial_fills = self.n_partial_fills
        rpt.pending_at_end = len(self.pending)
        rpt.n_resting_cancelled = self.n_resting_cancelled
        rpt.rejected = dict(self.rejected)
        return rpt


def _make_bt(snaps, strategy, *, starting_cash: float, submit_ms: float, jitter_ms: float):
    """Convenience wrapper: build a _BacktesterFixture with given config."""
    cfg = BacktestConfig(
        starting_cash=starting_cash,
        latency_model=LatencyModel(submit_ms=submit_ms, jitter_ms=jitter_ms),
    )
    return _BacktesterFixture(snaps, strategy, cfg)


# ---------------------------------------------------------------------------
# Strategies used by the audit checks
# ---------------------------------------------------------------------------

class OneShotBuy:
    """Buys qty on the Nth tick, then stays quiet."""

    def __init__(self, symbol: str, qty: int, fire_on: int = 0) -> None:
        self.symbol = symbol
        self.qty = qty
        self.fire_on = fire_on
        self._seen = 0
        self.fired = False

    def on_tick(self, snap, ctx):
        if snap.symbol != self.symbol or self.fired:
            return []
        if self._seen == self.fire_on:
            self.fired = True
            return [Order(symbol=self.symbol, side=BUY, qty=self.qty, order_type=MARKET, tag="buy")]
        self._seen += 1
        return []


class OneShotSell:
    def __init__(self, symbol: str, qty: int) -> None:
        self.symbol = symbol
        self.qty = qty
        self.fired = False

    def on_tick(self, snap, ctx):
        if snap.symbol != self.symbol or self.fired:
            return []
        self.fired = True
        return [Order(symbol=self.symbol, side=SELL, qty=self.qty, order_type=MARKET, tag="sell")]


class ScheduledOrders:
    """Fires a fixed list of (tick_index, order) pairs."""

    def __init__(self, plan: list[tuple[int, Order]]) -> None:
        self.plan = plan
        self._i = 0

    def on_tick(self, snap, ctx):
        out = []
        for idx, order in self.plan:
            if idx == self._i and order.symbol == snap.symbol:
                out.append(order)
        self._i += 1
        return out


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def make_stream(symbol="000001", n=5, best_bid=100, best_ask=101, qty_each=100) -> list[OrderBookSnapshot]:
    return [
        make_snap(
            ts_ns=i * 1_000_000_000,
            symbol=symbol,
            ask_px=[best_ask + i for i in range(5)],
            ask_qty=[qty_each] * 5,
            bid_px=[best_bid - i for i in range(5)],
            bid_qty=[qty_each] * 5,
        )
        for i in range(n)
    ]


def check_no_cash_overdraft():
    stream = make_stream(symbol="000001", n=3, best_bid=100, best_ask=101, qty_each=100)
    # starting_cash only 50 KRW, but tries to buy 1 share @ 101 KRW
    cfg = BacktestConfig(starting_cash=50.0, latency_model=LatencyModel(submit_ms=0, jitter_ms=0))
    bt = _BacktesterFixture(stream, OneShotBuy("000001", qty=1), cfg)
    rpt = bt.run()
    ok = bt.portfolio.cash >= 0 and bt.portfolio.n_trades == 0
    check(
        "no cash overdraft",
        ok,
        f"ending_cash={bt.portfolio.cash:.2f} n_trades={bt.portfolio.n_trades}",
    )


def check_no_short_sell():
    stream = make_stream(symbol="000001", n=3, best_bid=100, best_ask=101, qty_each=100)
    cfg = BacktestConfig(starting_cash=10_000.0, latency_model=LatencyModel(submit_ms=0, jitter_ms=0))
    bt = _BacktesterFixture(stream, OneShotSell("000001", qty=1), cfg)
    rpt = bt.run()
    pos = bt.portfolio.positions.get("000001")
    pos_qty = pos.qty if pos else 0
    ok = pos_qty >= 0 and bt.portfolio.n_trades == 0
    check(
        "no naked short sell",
        ok,
        f"position={pos_qty} n_trades={bt.portfolio.n_trades}",
    )


def check_partial_fill_remainder_tracked():
    # Book has only 30 shares on ask; we ask for 100 → 30 fill, 70 unfilled.
    snap1 = make_snap(1_000_000_000, "000001", [101], [30], [100], [100])
    snap2 = make_snap(2_000_000_000, "000001", [101], [30], [100], [100])
    cfg = BacktestConfig(starting_cash=100_000.0, latency_model=LatencyModel(submit_ms=0, jitter_ms=0))
    bt = _BacktesterFixture([snap1, snap2], OneShotBuy("000001", qty=100), cfg)
    rpt = bt.run()
    fills = bt.portfolio.fills
    filled = sum(f.qty for f in fills if f.side == BUY)
    partial = rpt.n_partial_fills
    tracked = partial > 0
    ok = filled >= 100 or tracked
    check(
        "partial fill remainder is tracked",
        ok,
        f"filled={filled}/100 partial_fills={partial}",
    )


def check_unfilled_at_eod_reported():
    # Order placed on the LAST tick; target ts past end-of-stream.
    stream = make_stream(symbol="000001", n=3, qty_each=100)
    cfg = BacktestConfig(starting_cash=100_000.0, latency_model=LatencyModel(submit_ms=10.0, jitter_ms=0))
    bt = _BacktesterFixture(stream, OneShotBuy("000001", qty=1, fire_on=2), cfg)
    rpt = bt.run()
    pending = len(bt.pending)
    reported = rpt.pending_at_end
    ok = reported == pending and pending >= 1
    check(
        "unfilled pending orders at EOD are reported",
        ok,
        f"pending_in_queue={pending} reported={reported}",
    )


def check_fee_accounting_consistency():
    # Buy then sell; verify ending_cash - starting_cash == realized_pnl - fees
    # (no open position).
    snap1 = make_snap(1_000_000_000, "000001", [101], [100], [100], [100])
    snap2 = make_snap(2_000_000_000, "000001", [101], [100], [100], [100])
    snap3 = make_snap(3_000_000_000, "000001", [102], [100], [101], [100])
    snap4 = make_snap(4_000_000_000, "000001", [102], [100], [101], [100])

    class BuyThenSell:
        def __init__(self):
            self.i = 0

        def on_tick(self, snap, ctx):
            self.i += 1
            if self.i == 1:
                return [Order(symbol="000001", side=BUY, qty=10, order_type=MARKET)]
            if self.i == 3:
                return [Order(symbol="000001", side=SELL, qty=10, order_type=MARKET)]
            return []

    cfg = BacktestConfig(
        starting_cash=100_000.0,
        fee_model=FeeModel(commission_bps=1.5, tax_bps=18.0),
        latency_model=LatencyModel(submit_ms=0, jitter_ms=0),
    )
    bt = _BacktesterFixture([snap1, snap2, snap3, snap4], BuyThenSell(), cfg)
    rpt = bt.run()

    realized = sum(p.realized_pnl for p in bt.portfolio.positions.values())
    fees = bt.portfolio.total_fees
    cash_delta = bt.portfolio.cash - cfg.starting_cash
    expected = realized - fees
    ok = abs(cash_delta - expected) < 1e-6 and bt.portfolio.positions["000001"].qty == 0
    check(
        "fee accounting consistency (flat position)",
        ok,
        f"cash_delta={cash_delta:.4f} realized-fees={expected:.4f} pos={bt.portfolio.positions['000001'].qty}",
    )


def check_no_lookahead():
    # Strategy that cheats by inspecting the future is impossible through the
    # Backtester API (on_tick only receives current snap). Verify the API
    # surface: Context has no forward reference.
    ctx_fields = {"portfolio", "last_mids", "current_ts_ns"}
    actual = {f for f in Context.__dataclass_fields__}
    ok = actual == ctx_fields
    check(
        "strategy API exposes no look-ahead channel",
        ok,
        f"context_fields={sorted(actual)}",
    )


def check_latency_ordering():
    # Order submitted at tick ts=1 with latency=1.5s → must fill at tick ts>=2.5s
    # (i.e., tick 3s), not tick 2s.
    s1 = make_snap(1_000_000_000, "000001", [101], [100], [100], [100])
    s2 = make_snap(2_000_000_000, "000001", [200], [100], [199], [100])  # distinct book
    s3 = make_snap(3_000_000_000, "000001", [300], [100], [299], [100])

    class FireOnFirst:
        def __init__(self):
            self.fired = False

        def on_tick(self, snap, ctx):
            if not self.fired:
                self.fired = True
                return [Order(symbol="000001", side=BUY, qty=1, order_type=MARKET)]
            return []

    cfg = BacktestConfig(
        starting_cash=100_000.0,
        latency_model=LatencyModel(submit_ms=1500.0, jitter_ms=0),
    )
    bt = _BacktesterFixture([s1, s2, s3], FireOnFirst(), cfg)
    rpt = bt.run()
    fills = bt.portfolio.fills
    ok = len(fills) == 1 and fills[0].avg_price == 300.0 and fills[0].ts_ns == 3_000_000_000
    check(
        "latency-gated fill uses future book, not concurrent",
        ok,
        f"fill_px={fills[0].avg_price if fills else None} ts={fills[0].ts_ns if fills else None}",
    )


def check_slippage_from_walk_book():
    # Ask qty 5 @ 101, then 10 @ 102. Market buy 8 → avg px = (5*101 + 3*102)/8
    snap = make_snap(
        ts_ns=1,
        symbol="000001",
        ask_px=[101, 102],
        ask_qty=[5, 10],
        bid_px=[100],
        bid_qty=[100],
    )
    filled, px = walk_book(snap, BUY, 8)
    expected = (5 * 101 + 3 * 102) / 8
    ok = filled == 8 and abs(px - expected) < 1e-9
    check(
        "market order slippage walks book levels",
        ok,
        f"filled={filled}@{px:.4f} expected={expected:.4f}",
    )


def check_symbol_isolation_in_pending():
    # Pending order for symbol A should not match against tick of symbol B.
    s1 = make_snap(1_000_000_000, "000001", [101], [100], [100], [100])
    s2 = make_snap(1_500_000_000, "000002", [201], [100], [200], [100])
    s3 = make_snap(2_000_000_000, "000001", [105], [100], [104], [100])

    class Buy1A:
        def __init__(self): self.fired = False
        def on_tick(self, snap, ctx):
            if not self.fired and snap.symbol == "000001":
                self.fired = True
                return [Order(symbol="000001", side=BUY, qty=1, order_type=MARKET)]
            return []

    cfg = BacktestConfig(starting_cash=100_000.0, latency_model=LatencyModel(submit_ms=200, jitter_ms=0))
    bt = _BacktesterFixture([s1, s2, s3], Buy1A(), cfg)
    rpt = bt.run()
    fills = bt.portfolio.fills
    ok = len(fills) == 1 and fills[0].avg_price == 105.0
    check(
        "symbol isolation in pending queue",
        ok,
        f"fill_px={fills[0].avg_price if fills else None}",
    )


def check_python_strategy_path_loads():
    """runner.py can import a per-strategy Python file via strategy_kind=python."""
    import subprocess
    spec = _ROOT / "strategies" / "_examples" / "python_trailing_stop" / "spec.yaml"
    if not spec.exists():
        check("python strategy path loads", False, f"example missing: {spec}")
        return
    r = subprocess.run(
        ["python3", "-m", "engine.runner", "--spec", str(spec), "--summary"],
        cwd=str(_ROOT), capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        check("python strategy path loads", False, r.stderr.strip().splitlines()[-1] if r.stderr else "non-zero exit")
        return
    import json as _json
    try:
        data = _json.loads(r.stdout)
    except Exception as e:
        check("python strategy path loads", False, f"stdout parse failed: {e}")
        return
    ok = data.get("n_trades", 0) > 0 and data.get("spec_name") == "python_trailing_stop_example"
    check("python strategy path loads", ok, f"n_trades={data.get('n_trades')}")


def check_resting_limit_fills_on_price_cross():
    """Non-marketable LIMIT order queues as resting and fills when price crosses."""
    snaps = [
        # tick 0: ASK=102, strategy submits BUY LIMIT at 101 (non-marketable)
        make_snap(1_000_000_000, "000001", [102, 103], [10, 10], [99, 98], [10, 10]),
        # tick 1: ASK=103 → order promoted from pending to resting_limits (still non-marketable)
        make_snap(2_000_000_000, "000001", [103, 104], [10, 10], [99, 98], [10, 10]),
        # tick 2: ASK=101 → price crosses limit → fills at limit_price=101
        make_snap(3_000_000_000, "000001", [101, 102], [10, 10], [99, 98], [10, 10]),
        make_snap(4_000_000_000, "000001", [101, 102], [10, 10], [99, 98], [10, 10]),
    ]
    submitted = False

    class _Strat:
        def on_tick(self, snap, ctx):
            nonlocal submitted
            if not submitted:
                submitted = True
                return [Order("000001", BUY, qty=1, order_type=LIMIT, limit_price=101, tag="resting_buy")]
            return []

    bt = _make_bt(snaps, _Strat(), starting_cash=500_000, submit_ms=0, jitter_ms=0)
    rpt = bt.run()
    fills = bt.portfolio.fills
    ok = (
        len(fills) == 1
        and fills[0].avg_price == 101.0
        and fills[0].tag == "resting_buy"
    )
    check(
        "resting limit fills on price cross",
        ok,
        f"fills={len(fills)} fill_px={fills[0].avg_price if fills else None}",
    )


def check_resting_limit_eod_cancel():
    """Resting limit orders that never fill are cancelled at EOD and counted."""
    snaps = [
        make_snap(1_000_000_000, "000001", [102, 103], [10, 10], [99, 98], [10, 10]),
        make_snap(2_000_000_000, "000001", [103, 104], [10, 10], [99, 98], [10, 10]),
        # price never crosses 101 → resting order never fills
    ]
    submitted = False

    class _Strat:
        def on_tick(self, snap, ctx):
            nonlocal submitted
            if not submitted:
                submitted = True
                return [Order("000001", BUY, qty=1, order_type=LIMIT, limit_price=101, tag="resting")]
            return []

    bt = _make_bt(snaps, _Strat(), starting_cash=500_000, submit_ms=0, jitter_ms=0)
    rpt = bt.run()
    ok = rpt.n_resting_cancelled == 1 and len(bt.portfolio.fills) == 0
    check(
        "resting limit EOD cancel",
        ok,
        f"n_resting_cancelled={rpt.n_resting_cancelled} fills={len(bt.portfolio.fills)}",
    )


def main():
    checks = [
        check_no_lookahead,
        check_latency_ordering,
        check_slippage_from_walk_book,
        check_symbol_isolation_in_pending,
        check_fee_accounting_consistency,
        check_no_cash_overdraft,
        check_no_short_sell,
        check_partial_fill_remainder_tracked,
        check_unfilled_at_eod_reported,
        check_python_strategy_path_loads,
        check_resting_limit_fills_on_price_cross,
        check_resting_limit_eod_cancel,
    ]
    for fn in checks:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"exception: {e}")
    n_fail = sum(1 for _, ok, _ in _RESULTS if not ok)
    print()
    print(f"summary: {len(_RESULTS) - n_fail}/{len(_RESULTS)} passed")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
