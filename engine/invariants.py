"""Spec-driven invariant checker.

Infers runtime invariants from spec.yaml params and checks them during backtest.
Detects spec-code semantic gaps deterministically, without LLM critic involvement.

Design:
- spec.yaml params (e.g., profit_target_bps=80) → InvariantCheck instances
- Each InvariantCheck has a check function run at fill/tick events
- Violations are collected and emitted in BacktestReport.invariant_violations
- Agents are NOT modified — they read violations as just another report field
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InvariantViolation:
    """Single observed spec-code gap."""
    invariant_type: str
    expected: float
    actual: float
    fill_index: int
    severity: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "invariant_type": self.invariant_type,
            "expected": float(self.expected),
            "actual": float(self.actual),
            "fill_index": int(self.fill_index),
            "severity": self.severity,
            "context": self.context,
        }


@dataclass
class InvariantCheck:
    """Definition of an invariant derived from a spec parameter."""
    name: str
    spec_param: str
    severity: str
    tolerance_bps: float = 0.0
    tolerance_ticks: int = 0


INVARIANT_REGISTRY: dict[str, InvariantCheck] = {
    "sl_overshoot": InvariantCheck(
        name="sl_overshoot",
        spec_param="stop_loss_bps",
        severity="high",
        tolerance_bps=10.0,
    ),
    "pt_overshoot": InvariantCheck(
        name="pt_overshoot",
        spec_param="profit_target_bps",
        severity="low",
        tolerance_bps=20.0,
    ),
    "entry_gate_end_bypass": InvariantCheck(
        name="entry_gate_end_bypass",
        spec_param="entry_end_time_seconds",
        severity="high",
        tolerance_bps=0.0,
    ),
    "entry_gate_start_bypass": InvariantCheck(
        name="entry_gate_start_bypass",
        spec_param="entry_start_time_seconds",
        severity="high",
        tolerance_bps=0.0,
    ),
    "max_entries_exceeded": InvariantCheck(
        name="max_entries_exceeded",
        spec_param="max_entries_per_session",
        severity="high",
        tolerance_bps=0.0,
    ),
    "max_position_exceeded": InvariantCheck(
        name="max_position_exceeded",
        spec_param="max_position_per_symbol",
        severity="high",
        tolerance_bps=0.0,
    ),
    "time_stop_overshoot": InvariantCheck(
        name="time_stop_overshoot",
        spec_param="time_stop_ticks",
        severity="medium",
        tolerance_ticks=50,
    ),
}


def infer_invariants(spec_dict: dict) -> list[dict]:
    """Infer runtime invariants from spec.yaml content.

    Returns a list of dicts: {"name": str, "threshold": float, ...}.
    Only invariants whose spec_param is present in the spec are returned.
    """
    params = spec_dict.get("params") or {}
    risk = spec_dict.get("risk") or {}
    all_fields = {**params, **risk}

    result = []
    for name, check in INVARIANT_REGISTRY.items():
        value = all_fields.get(check.spec_param)
        if value is None:
            continue
        result.append({
            "name": name,
            "threshold": float(value),
            "spec_param": check.spec_param,
            "severity": check.severity,
            "tolerance_bps": check.tolerance_bps,
            "tolerance_ticks": check.tolerance_ticks,
        })
    return result


class InvariantRunner:
    """Stateful runner that observes fill events and detects invariant violations.

    Maintains per-symbol entry state to check SL/PT overshoot against the original
    entry price. Maintains per-(date,symbol) entry counts for max_entries checks.
    """

    def __init__(self, invariants: list[dict], strict_mode: bool = False) -> None:
        self.invariants = invariants
        self.strict_mode = strict_mode
        self._by_name = {inv["name"]: inv for inv in invariants}
        self._entries_per_day: dict[tuple[str, str], int] = {}
        self._open_entry: dict[str, dict] = {}
        self._violations: list[InvariantViolation] = []
        # Track strict-mode blocks for reporting
        self.strict_blocks: list[dict] = []

    def should_block_order(
        self,
        side: str,
        kst_sec: int,
        date_str: str,
        symbol: str,
        current_pos_qty: int,
        current_day_entries: int,
        incoming_qty: int = 0,
        lot_size: int = 1,
    ) -> tuple[bool, str]:
        """In strict_mode, return (True, reason) if this order would violate an invariant.

        Checks 4 REJECT-type invariants:
          - entry_gate_end_bypass: BUY after end_sec
          - entry_gate_start_bypass: BUY before start_sec
          - max_entries_exceeded: day's BUY count would exceed cap
          - max_position_exceeded: post-fill position would exceed cap * lot_size
        """
        if not self.strict_mode or side != "BUY":
            return False, ""

        if "entry_gate_end_bypass" in self._by_name:
            end = self._by_name["entry_gate_end_bypass"]["threshold"]
            if kst_sec >= end:
                self.strict_blocks.append({
                    "reason": "entry_gate_end_bypass",
                    "kst_sec": kst_sec, "date": date_str, "symbol": symbol,
                })
                return True, "entry_gate_end_bypass"

        if "entry_gate_start_bypass" in self._by_name:
            start = self._by_name["entry_gate_start_bypass"]["threshold"]
            if kst_sec < start:
                self.strict_blocks.append({
                    "reason": "entry_gate_start_bypass",
                    "kst_sec": kst_sec, "date": date_str, "symbol": symbol,
                })
                return True, "entry_gate_start_bypass"

        if "max_entries_exceeded" in self._by_name:
            cap = self._by_name["max_entries_exceeded"]["threshold"]
            if current_day_entries >= cap:
                self.strict_blocks.append({
                    "reason": "max_entries_exceeded",
                    "current": current_day_entries, "cap": cap,
                    "date": date_str, "symbol": symbol,
                })
                return True, "max_entries_exceeded"

        if "max_position_exceeded" in self._by_name:
            cap = self._by_name["max_position_exceeded"]["threshold"]
            max_qty = cap * lot_size
            if current_pos_qty + incoming_qty > max_qty:
                self.strict_blocks.append({
                    "reason": "max_position_exceeded",
                    "current_qty": current_pos_qty, "incoming": incoming_qty,
                    "cap_qty": max_qty, "date": date_str, "symbol": symbol,
                })
                return True, "max_position_exceeded"

        return False, ""

    def on_fill(
        self,
        fill_index: int,
        side: str,
        qty: int,
        price: float,
        tag: str,
        kst_sec: int,
        date_str: str,
        symbol: str,
        ticks_held: int | None = None,
    ) -> None:
        if side == "BUY":
            self._on_buy(fill_index, qty, price, tag, kst_sec, date_str, symbol)
        elif side == "SELL":
            self._on_sell(fill_index, qty, price, tag, kst_sec, date_str, symbol, ticks_held)

    def _on_buy(self, fill_index, qty, price, tag, kst_sec, date_str, symbol):
        # Gate-end bypass
        if "entry_gate_end_bypass" in self._by_name:
            end = self._by_name["entry_gate_end_bypass"]["threshold"]
            if kst_sec >= end:
                self._violations.append(InvariantViolation(
                    invariant_type="entry_gate_end_bypass",
                    expected=end, actual=kst_sec,
                    fill_index=fill_index, severity="high",
                    context={"symbol": symbol, "date": date_str, "tag": tag},
                ))

        # Gate-start bypass
        if "entry_gate_start_bypass" in self._by_name:
            start = self._by_name["entry_gate_start_bypass"]["threshold"]
            if kst_sec < start:
                self._violations.append(InvariantViolation(
                    invariant_type="entry_gate_start_bypass",
                    expected=start, actual=kst_sec,
                    fill_index=fill_index, severity="high",
                    context={"symbol": symbol, "date": date_str, "tag": tag},
                ))

        # Max entries per session
        key = (date_str, symbol)
        self._entries_per_day[key] = self._entries_per_day.get(key, 0) + 1
        if "max_entries_exceeded" in self._by_name:
            cap = self._by_name["max_entries_exceeded"]["threshold"]
            count = self._entries_per_day[key]
            if count > cap:
                self._violations.append(InvariantViolation(
                    invariant_type="max_entries_exceeded",
                    expected=cap, actual=count,
                    fill_index=fill_index, severity="high",
                    context={"symbol": symbol, "date": date_str},
                ))

        # Record entry for SL/PT check on subsequent SELL
        self._open_entry[symbol] = {
            "price": float(price),
            "fill_index": fill_index,
            "kst_sec": kst_sec,
        }

    def _on_sell(self, fill_index, qty, price, tag, kst_sec, date_str, symbol, ticks_held):
        entry = self._open_entry.get(symbol)
        if entry is None:
            return
        entry_price = entry["price"]
        if entry_price <= 0:
            return

        pnl_bps = (price - entry_price) / entry_price * 1e4

        # SL overshoot
        if tag == "stop_loss" and "sl_overshoot" in self._by_name:
            sl = self._by_name["sl_overshoot"]
            threshold = sl["threshold"]
            tol = sl["tolerance_bps"]
            loss_bps = -pnl_bps
            if loss_bps > threshold + tol:
                self._violations.append(InvariantViolation(
                    invariant_type="sl_overshoot",
                    expected=threshold, actual=loss_bps,
                    fill_index=fill_index, severity="high",
                    context={
                        "symbol": symbol, "date": date_str,
                        "entry_price": entry_price, "exit_price": float(price),
                    },
                ))

        # PT overshoot
        if tag == "profit_target" and "pt_overshoot" in self._by_name:
            pt = self._by_name["pt_overshoot"]
            threshold = pt["threshold"]
            tol = pt["tolerance_bps"]
            if pnl_bps > threshold + tol:
                self._violations.append(InvariantViolation(
                    invariant_type="pt_overshoot",
                    expected=threshold, actual=pnl_bps,
                    fill_index=fill_index, severity="low",
                    context={
                        "symbol": symbol, "date": date_str,
                        "entry_price": entry_price, "exit_price": float(price),
                    },
                ))

        # time_stop overshoot
        if tag == "time_stop" and "time_stop_overshoot" in self._by_name and ticks_held is not None:
            ts = self._by_name["time_stop_overshoot"]
            threshold = ts["threshold"]
            tol = ts["tolerance_ticks"]
            if ticks_held > threshold + tol:
                self._violations.append(InvariantViolation(
                    invariant_type="time_stop_overshoot",
                    expected=threshold, actual=float(ticks_held),
                    fill_index=fill_index, severity="medium",
                    context={"symbol": symbol, "date": date_str},
                ))

        del self._open_entry[symbol]

    def on_position_update(self, symbol: str, qty: int, lot_size: int, fill_index: int,
                           date_str: str) -> None:
        """Called after each fill to check max_position_exceeded."""
        if "max_position_exceeded" in self._by_name:
            cap = self._by_name["max_position_exceeded"]["threshold"]
            max_qty = cap * lot_size
            if qty > max_qty:
                self._violations.append(InvariantViolation(
                    invariant_type="max_position_exceeded",
                    expected=max_qty, actual=qty,
                    fill_index=fill_index, severity="high",
                    context={"symbol": symbol, "date": date_str},
                ))

    def get_violations(self) -> list[InvariantViolation]:
        return list(self._violations)
