"""Template for a stateful Python strategy.

When a spec.yaml has `strategy_kind: python`, the runner imports
`strategy.py` from the same directory and instantiates its `Strategy`
class with the parsed spec dict.

Use this path when the logic cannot be expressed as a pure boolean
expression over signal primitives — e.g., state machines, multi-stage
entries, inventory models, trailing stops, or anything that needs to
carry arbitrary state across ticks.

Contract
--------
- Define a top-level class named `Strategy`.
- `__init__(self, spec: dict)` receives the full parsed spec.yaml as a
  Python dict. Read any custom parameters from `spec["params"]`.
- `on_tick(self, snap, ctx) -> list[Order]` is called on every tick in
  chronological order, across all symbols in the universe. Return a list
  of `Order` instances to submit at this tick (may be empty).

Available inputs per tick
-------------------------
- `snap.symbol`                    — current symbol (6-digit string)
- `snap.ts_ns`                     — tick timestamp (KST epoch ns)
- `snap.ask_px[0..9]`              — 10 levels of ask price (numpy int64)
- `snap.ask_qty[0..9]`             — 10 levels of ask quantity
- `snap.bid_px[0..9]` / `bid_qty`  — same for bids
- `snap.total_ask_qty`, `snap.total_bid_qty`
- `snap.acml_vol`                  — accumulated traded volume
- `snap.mid`                       — property (best_ask + best_bid) / 2
- `snap.spread`                    — property best_ask - best_bid (KRW)
- `ctx.portfolio`                  — Portfolio (read-only observation)
- `ctx.portfolio.positions[sym]`   — Position(qty, avg_cost, realized_pnl)
- `ctx.portfolio.cash`             — current cash
- `ctx.last_mids`                  — dict[symbol] -> most recent mid
- `ctx.current_ts_ns`              — same as snap.ts_ns

Orders
------
Return a list of Order instances from `engine.simulator`:

    Order(symbol, side, qty, order_type=MARKET, limit_price=None, tag="")

- `side`       : BUY or SELL
- `order_type` : MARKET or LIMIT (limit non-marketable orders are dropped)
- Orders are queued with the configured latency and matched against the
  first future tick whose timestamp >= submission + latency.

The matching engine enforces:
- no cash overdraft on BUY (notional + fee must fit in cash)
- no naked short (SELL requires sufficient long position)
- partial fills are tracked in the report

Reusing signal primitives
-------------------------
You can reuse the engine's signal primitives from `engine.signals`:

    from engine.signals import SIGNAL_REGISTRY, SymbolState, update_state
    obi = SIGNAL_REGISTRY["obi"]
    value = obi(snap, state, depth=5)
"""
from __future__ import annotations

from engine.data_loader import OrderBookSnapshot
from engine.signals import SIGNAL_REGISTRY, SymbolState, update_state
from engine.simulator import BUY, LIMIT, MARKET, SELL, Context, Order


class Strategy:
    def __init__(self, spec: dict) -> None:
        self.params = (spec.get("params") or {})
        self.states: dict[str, SymbolState] = {}
        # Add any custom state here
        #
        # Example parameters you might read from spec.params:
        # self.entry_threshold = float(self.params.get("entry_threshold", 0.3))
        # self.max_hold_ticks  = int(self.params.get("max_hold_ticks", 100))

    def _state(self, symbol: str) -> SymbolState:
        if symbol not in self.states:
            self.states[symbol] = SymbolState(symbol=symbol)
        return self.states[symbol]

    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        st = self._state(snap.symbol)
        update_state(st, snap)

        # ── your logic here ──────────────────────────────────────────────
        # Example: market-buy 1 share the first time OBI(5) crosses 0.5.
        #
        # obi = SIGNAL_REGISTRY["obi"](snap, st, depth=5)
        # pos = ctx.portfolio.positions.get(snap.symbol)
        # if obi > 0.5 and (pos is None or pos.qty == 0):
        #     return [Order(snap.symbol, BUY, qty=1, order_type=MARKET, tag="entry")]
        # ─────────────────────────────────────────────────────────────────

        return []
