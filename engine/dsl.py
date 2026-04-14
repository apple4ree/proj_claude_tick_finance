"""Safe expression evaluator + DSL-driven strategy.

The evaluator parses a Python-like expression via ast and walks the tree
with an allowlist of node types and function calls. Anything outside the
allowlist raises a ValueError at compile time.
"""
from __future__ import annotations

import ast
import operator as op
from typing import Any

from engine.data_loader import OrderBookSnapshot
from engine.signals import SIGNAL_REGISTRY, SymbolState, update_state
from engine.simulator import BUY, LIMIT, MARKET, SELL, Context, Order
from engine.spec import StrategySpec

_BIN_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
}
_CMP_OPS = {
    ast.Lt: op.lt,
    ast.LtE: op.le,
    ast.Gt: op.gt,
    ast.GtE: op.ge,
    ast.Eq: op.eq,
    ast.NotEq: op.ne,
}
_UNARY_OPS = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
    ast.Not: op.not_,
}
_WHITELIST_FNS = {"min": min, "max": max, "abs": abs}


def safe_eval(expr: str, ctx: dict) -> Any:
    tree = ast.parse(str(expr), mode="eval")
    return _walk(tree.body, ctx)


def _walk(node: ast.AST, ctx: dict) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise NameError(f"unknown identifier: {node.id}")
        return ctx[node.id]
    if isinstance(node, ast.BinOp):
        return _BIN_OPS[type(node.op)](_walk(node.left, ctx), _walk(node.right, ctx))
    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPS[type(node.op)](_walk(node.operand, ctx))
    if isinstance(node, ast.Compare):
        left = _walk(node.left, ctx)
        for oper, comp in zip(node.ops, node.comparators):
            right = _walk(comp, ctx)
            if not _CMP_OPS[type(oper)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        vals = [_walk(v, ctx) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.IfExp):
        return _walk(node.body, ctx) if _walk(node.test, ctx) else _walk(node.orelse, ctx)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _WHITELIST_FNS:
            raise ValueError(f"disallowed call: {ast.dump(node.func)}")
        return _WHITELIST_FNS[node.func.id](*(_walk(a, ctx) for a in node.args))
    raise ValueError(f"disallowed node: {ast.dump(node)}")


# ---------------------------------------------------------------------------
# SpecStrategy — interprets a StrategySpec
# ---------------------------------------------------------------------------

def _eval_cond(cond: Any, ctx: dict) -> bool:
    if isinstance(cond, bool):
        return cond
    if cond is None:
        return False
    return bool(safe_eval(cond, ctx))


class SpecStrategy:
    def __init__(self, spec: StrategySpec) -> None:
        self.spec = spec
        self.states: dict[str, SymbolState] = {}
        self.tick_count: dict[str, int] = {}
        self.entry_tick: dict[str, int] = {}

        self.entry_when = spec.entry.get("when", False)
        self.entry_size = int(spec.entry.get("size", 1))
        self.exit_when = spec.exit.get("when", False)
        self.max_pos = int(spec.risk.get("max_position_per_symbol", 1))

        self.signal_defs: list[tuple[str, Any, dict]] = []
        for name, defn in (spec.signals or {}).items():
            if isinstance(defn, str):
                fn_name, args = defn, {}
            elif isinstance(defn, dict):
                fn_name = defn.get("fn") or defn.get("primitive")
                args = defn.get("args", {}) or {}
            else:
                raise ValueError(f"invalid signal def for {name}: {defn!r}")
            if fn_name not in SIGNAL_REGISTRY:
                raise ValueError(f"unknown signal primitive: {fn_name}")
            self.signal_defs.append((name, SIGNAL_REGISTRY[fn_name], args))

    def _state(self, symbol: str) -> SymbolState:
        if symbol not in self.states:
            self.states[symbol] = SymbolState(symbol=symbol)
        return self.states[symbol]

    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        st = self._state(snap.symbol)
        update_state(st, snap)
        tc = self.tick_count.get(snap.symbol, 0) + 1
        self.tick_count[snap.symbol] = tc

        values = {name: fn(snap, st, **args) for name, fn, args in self.signal_defs}

        pos_obj = ctx.portfolio.positions.get(snap.symbol)
        pos_qty = pos_obj.qty if pos_obj else 0
        held_since = self.entry_tick.get(snap.symbol, tc)
        holding_ticks = tc - held_since if pos_qty > 0 else 0

        eval_ctx = {
            **values,
            "position": pos_qty,
            "holding_ticks": holding_ticks,
            "mid_now": float(snap.mid),
            "spread_now": float(snap.spread),
            "true": True,
            "false": False,
            "True": True,
            "False": False,
        }

        orders: list[Order] = []
        if pos_qty < self.max_pos and _eval_cond(self.entry_when, eval_ctx):
            orders.append(
                Order(
                    symbol=snap.symbol,
                    side=BUY,
                    qty=self.entry_size,
                    order_type=MARKET,
                    tag="entry",
                )
            )
            self.entry_tick[snap.symbol] = tc
        elif pos_qty > 0 and _eval_cond(self.exit_when, eval_ctx):
            orders.append(
                Order(
                    symbol=snap.symbol,
                    side=SELL,
                    qty=pos_qty,
                    order_type=MARKET,
                    tag="exit",
                )
            )
            self.entry_tick.pop(snap.symbol, None)
        return orders
