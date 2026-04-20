"""OBI-entry + trailing-stop exit.

Per symbol:
  - Enter long 1 share when OBI(depth=5) > entry_threshold and flat.
  - While holding, track peak_mid since entry. Exit when mid drops
    trail_bps below peak_mid OR holding_ticks > max_hold_ticks.

LATENCY-GUARD PATTERN (mandatory for all Python strategies):
  Orders have 5ms+ fill latency. During that window, pos_qty is still stale.
  Without a guard, the entry/exit condition fires every tick in that window,
  flooding the queue with duplicates and exhausting cash.

  Use _pending_buy / _pending_sell dicts (sym → tick_submitted).
  Clear on confirmed fill (pos_qty change). Reset after _MAX_PENDING_TICKS
  to recover from rejected orders (pos_qty never changes on rejection).
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.data_loader import OrderBookSnapshot
from engine.signals import SIGNAL_REGISTRY, SymbolState, update_state
from engine.simulator import BUY, MARKET, SELL, Context, Order

_MAX_PENDING_TICKS = 100  # ticks before assuming rejection; >> 5ms latency


@dataclass
class _HoldingState:
    entry_tick: int
    entry_mid: float
    peak_mid: float


class Strategy:
    def __init__(self, spec: dict) -> None:
        p = (spec.get("params") or {})
        self.entry_threshold = float(p.get("entry_threshold", 0.5))
        self.trail_bps = float(p.get("trail_bps", 8.0))
        self.max_hold_ticks = int(p.get("max_hold_ticks", 300))

        self.states: dict[str, SymbolState] = {}
        self.tick_count: dict[str, int] = {}
        self.holdings: dict[str, _HoldingState] = {}
        self._pending_buy: dict[str, int] = {}   # sym → tick when submitted
        self._pending_sell: dict[str, int] = {}  # sym → tick when submitted

        self._obi = SIGNAL_REGISTRY["obi"]

    def _state(self, symbol: str) -> SymbolState:
        if symbol not in self.states:
            self.states[symbol] = SymbolState(symbol=symbol)
        return self.states[symbol]

    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        sym = snap.symbol
        st = self._state(sym)
        update_state(st, snap)
        tc = self.tick_count.get(sym, 0) + 1
        self.tick_count[sym] = tc

        pos = ctx.portfolio.positions.get(sym)
        pos_qty = pos.qty if pos else 0

        mid = snap.mid
        hold = self.holdings.get(sym)

        # --- Clear pending flags on confirmed fills ---
        if pos_qty > 0 and sym in self._pending_buy:
            del self._pending_buy[sym]
        if pos_qty == 0 and sym in self._pending_sell:
            del self._pending_sell[sym]
            self.holdings.pop(sym, None)
            hold = None

        # --- Flat: check entry ---
        if pos_qty == 0:
            if sym in self._pending_buy:
                if tc - self._pending_buy[sym] > _MAX_PENDING_TICKS:
                    del self._pending_buy[sym]   # likely rejected — reset
                    self.holdings.pop(sym, None)
                    hold = None
                else:
                    return []  # BUY in flight — wait
            if hold is not None:
                # Position closed externally (EOD close) — clear stale state
                self.holdings.pop(sym, None)
                hold = None
            obi = self._obi(snap, st, depth=5)
            if obi > self.entry_threshold:
                self._pending_buy[sym] = tc
                self.holdings[sym] = _HoldingState(
                    entry_tick=tc, entry_mid=mid, peak_mid=mid
                )
                return [Order(sym, BUY, qty=1, order_type=MARKET, tag="entry")]
            return []

        # --- Holding: check exit ---
        if sym in self._pending_sell:
            if tc - self._pending_sell[sym] > _MAX_PENDING_TICKS:
                del self._pending_sell[sym]  # likely rejected — retry
            else:
                return []  # SELL in flight — wait

        if hold is None:
            hold = _HoldingState(entry_tick=tc, entry_mid=mid, peak_mid=mid)
            self.holdings[sym] = hold

        if mid > hold.peak_mid:
            hold.peak_mid = mid

        holding_ticks = tc - hold.entry_tick
        drawdown_bps = (hold.peak_mid - mid) / hold.peak_mid * 1e4 if hold.peak_mid > 0 else 0.0

        if drawdown_bps >= self.trail_bps or holding_ticks >= self.max_hold_ticks:
            self._pending_sell[sym] = tc
            return [Order(sym, SELL, qty=pos_qty, order_type=MARKET, tag="trail_exit")]
        return []
