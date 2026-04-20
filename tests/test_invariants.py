"""Unit tests for engine.invariants."""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.invariants import (
    INVARIANT_REGISTRY,
    InvariantCheck,
    InvariantRunner,
    InvariantViolation,
    infer_invariants,
)


# ── Task 1: InvariantViolation ────────────────────────────────────────────

def test_invariant_violation_fields():
    v = InvariantViolation(
        invariant_type="sl_overshoot",
        expected=50.0,
        actual=362.0,
        fill_index=7,
        severity="high",
        context={"entry_price": 196100, "exit_price": 189000},
    )
    assert v.invariant_type == "sl_overshoot"
    assert v.actual == 362.0
    assert v.severity == "high"
    assert v.context["entry_price"] == 196100


def test_invariant_violation_to_dict():
    v = InvariantViolation(
        invariant_type="gate_bypass",
        expected=46800,
        actual=48122,
        fill_index=3,
        severity="medium",
        context={},
    )
    d = v.to_dict()
    assert d["invariant_type"] == "gate_bypass"
    assert d["actual"] == 48122.0


# ── Task 2: InvariantCheck + registry ─────────────────────────────────────

def test_invariant_check_fields():
    check = InvariantCheck(
        name="sl_overshoot",
        spec_param="stop_loss_bps",
        severity="high",
        tolerance_bps=5.0,
    )
    assert check.name == "sl_overshoot"
    assert check.tolerance_bps == 5.0


def test_invariant_registry_contains_seven_types():
    expected = {
        "sl_overshoot",
        "pt_overshoot",
        "entry_gate_end_bypass",
        "entry_gate_start_bypass",
        "max_entries_exceeded",
        "max_position_exceeded",
        "time_stop_overshoot",
    }
    assert expected.issubset(INVARIANT_REGISTRY.keys())


# ── Task 3: infer_invariants ──────────────────────────────────────────────

def test_infer_invariants_from_full_spec():
    spec_dict = {
        "params": {
            "stop_loss_bps": 50.0,
            "profit_target_bps": 80.0,
            "entry_end_time_seconds": 46800,
            "entry_start_time_seconds": 36000,
            "max_entries_per_session": 3,
            "time_stop_ticks": 3000,
            "lot_size": 5,
        },
        "risk": {
            "max_position_per_symbol": 1,
        },
    }
    invariants = infer_invariants(spec_dict)
    names = {i["name"] for i in invariants}
    assert "sl_overshoot" in names
    assert "pt_overshoot" in names
    assert "entry_gate_end_bypass" in names
    assert "entry_gate_start_bypass" in names
    assert "max_entries_exceeded" in names
    assert "max_position_exceeded" in names
    assert "time_stop_overshoot" in names

    sl = next(i for i in invariants if i["name"] == "sl_overshoot")
    assert sl["threshold"] == 50.0


def test_infer_invariants_skips_missing_params():
    spec_dict = {"params": {"profit_target_bps": 80.0}}
    invariants = infer_invariants(spec_dict)
    names = {i["name"] for i in invariants}
    assert "sl_overshoot" not in names
    assert "pt_overshoot" in names


# ── Task 4: InvariantRunner ───────────────────────────────────────────────

def _make_runner():
    spec = {
        "params": {
            "stop_loss_bps": 50.0,
            "profit_target_bps": 80.0,
            "entry_end_time_seconds": 46800,
            "entry_start_time_seconds": 36000,
            "max_entries_per_session": 2,
            "time_stop_ticks": 3000,
        },
        "risk": {"max_position_per_symbol": 1},
    }
    invariants = infer_invariants(spec)
    return InvariantRunner(invariants=invariants)


def test_runner_detects_sl_overshoot():
    r = _make_runner()
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    r.on_fill(
        fill_index=1, side="SELL", qty=5, price=99000, tag="stop_loss",
        kst_sec=37000, date_str="20260316", symbol="005930",
    )
    violations = r.get_violations()
    sl_viols = [v for v in violations if v.invariant_type == "sl_overshoot"]
    assert len(sl_viols) == 1
    assert sl_viols[0].expected == 50.0
    assert sl_viols[0].actual > 90.0


def test_runner_detects_gate_bypass():
    r = _make_runner()
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=48120, date_str="20260316", symbol="005930",
    )
    violations = r.get_violations()
    gate = [v for v in violations if v.invariant_type == "entry_gate_end_bypass"]
    assert len(gate) == 1
    assert gate[0].actual == 48120
    assert gate[0].expected == 46800


def test_runner_detects_max_entries():
    r = _make_runner()
    for i in range(3):
        r.on_fill(
            fill_index=i, side="BUY", qty=5, price=100000, tag="passive_entry",
            kst_sec=36500 + i * 100, date_str="20260316", symbol="005930",
        )
    violations = r.get_violations()
    max_viols = [v for v in violations if v.invariant_type == "max_entries_exceeded"]
    assert len(max_viols) == 1
    assert max_viols[0].actual == 3


def test_runner_no_false_positive_within_tolerance():
    r = _make_runner()
    # SL threshold 50 + tolerance 10 = 60. Test at 50 bps loss (within tolerance).
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    r.on_fill(
        fill_index=1, side="SELL", qty=5, price=99500, tag="stop_loss",
        kst_sec=37000, date_str="20260316", symbol="005930",
    )
    violations = r.get_violations()
    assert not any(v.invariant_type == "sl_overshoot" for v in violations)


def test_runner_detects_time_stop_overshoot():
    r = _make_runner()
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    # ticks_held=5000 > threshold 3000 + tolerance 50
    r.on_fill(
        fill_index=1, side="SELL", qty=5, price=100000, tag="time_stop",
        kst_sec=40000, date_str="20260316", symbol="005930",
        ticks_held=5000,
    )
    violations = r.get_violations()
    ts = [v for v in violations if v.invariant_type == "time_stop_overshoot"]
    assert len(ts) == 1
    assert ts[0].actual == 5000.0


# -- Task 1 (strict_mode): should_block_order -----------------------------

def test_runner_strict_mode_blocks_gate_end_bypass():
    r = InvariantRunner(
        invariants=infer_invariants({
            "params": {"entry_end_time_seconds": 46800, "entry_start_time_seconds": 36000},
        }),
        strict_mode=True,
    )
    # BUY at 13:22 (past 13:00) - should be blocked
    block, reason = r.should_block_order(
        side="BUY", kst_sec=48120, date_str="20260316",
        symbol="005930", current_pos_qty=0, current_day_entries=0,
    )
    assert block is True
    assert reason == "entry_gate_end_bypass"


def test_runner_strict_mode_blocks_max_entries():
    r = InvariantRunner(
        invariants=infer_invariants({
            "params": {"max_entries_per_session": 2},
        }),
        strict_mode=True,
    )
    block, reason = r.should_block_order(
        side="BUY", kst_sec=36500, date_str="20260316",
        symbol="005930", current_pos_qty=0, current_day_entries=2,
    )
    assert block is True
    assert reason == "max_entries_exceeded"


def test_runner_strict_mode_blocks_max_position():
    r = InvariantRunner(
        invariants=infer_invariants({
            "params": {"lot_size": 5},
            "risk": {"max_position_per_symbol": 1},
        }),
        strict_mode=True,
    )
    # pos=5 already, incoming BUY would make it 10 -> block
    block, reason = r.should_block_order(
        side="BUY", kst_sec=36500, date_str="20260316",
        symbol="005930", current_pos_qty=5, current_day_entries=0,
        incoming_qty=5, lot_size=5,
    )
    assert block is True
    assert reason == "max_position_exceeded"


def test_runner_permissive_mode_does_not_block():
    r = InvariantRunner(
        invariants=infer_invariants({
            "params": {"entry_end_time_seconds": 46800},
        }),
        strict_mode=False,
    )
    block, reason = r.should_block_order(
        side="BUY", kst_sec=48120, date_str="20260316",
        symbol="005930", current_pos_qty=0, current_day_entries=0,
    )
    assert block is False


# -- Task 2 (strict_mode): should_force_sell ------------------------------

def test_runner_force_sell_on_sl_threshold():
    """Engine should force SELL when bid-based loss crosses stop_loss_bps."""
    r = InvariantRunner(
        invariants=infer_invariants({"params": {"stop_loss_bps": 50.0}}),
        strict_mode=True,
    )
    # Seed an open entry
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    # bid dropped to 99400 -> loss = 60 bps (> 50)
    force, tag = r.should_force_sell(
        symbol="005930", current_bid=99400, current_mid=99450,
        ticks_held=10,
    )
    assert force is True
    assert tag == "strict_sl"


def test_runner_force_sell_on_time_stop():
    r = InvariantRunner(
        invariants=infer_invariants({"params": {"time_stop_ticks": 3000}}),
        strict_mode=True,
    )
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    # ticks_held = 3001 > threshold 3000
    force, tag = r.should_force_sell(
        symbol="005930", current_bid=100100, current_mid=100150,
        ticks_held=3001,
    )
    assert force is True
    assert tag == "strict_time_stop"


def test_runner_no_force_before_threshold():
    r = InvariantRunner(
        invariants=infer_invariants({
            "params": {"stop_loss_bps": 50.0, "time_stop_ticks": 3000}
        }),
        strict_mode=True,
    )
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    # bid dropped only 10 bps (under 50) and ticks_held 500 (under 3000)
    force, tag = r.should_force_sell(
        symbol="005930", current_bid=99900, current_mid=99950,
        ticks_held=500,
    )
    assert force is False


def test_runner_force_without_open_entry_returns_false():
    r = InvariantRunner(
        invariants=infer_invariants({"params": {"stop_loss_bps": 50.0}}),
        strict_mode=True,
    )
    # No entry was opened
    force, tag = r.should_force_sell(
        symbol="005930", current_bid=99000, current_mid=99050,
        ticks_held=10,
    )
    assert force is False
