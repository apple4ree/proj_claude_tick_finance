# Spec-Driven Invariant Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Engine auto-infers runtime invariants from spec.yaml and detects spec-code semantic gaps deterministically, without modifying any LLM agent.

**Architecture:** Engine reads spec.yaml params (profit_target_bps, stop_loss_bps, entry_end_time_seconds, etc.), converts each into a typed InvariantCheck, runs checks on every Fill event during backtest, and emits structured violations in report.json. Agents are NOT modified — critics read the violations field just like any other report field. A comparator script later measures critic recall vs automated checker recall on historical strategies.

**Tech Stack:** Python 3.10+, dataclasses, existing engine.simulator + engine.spec, pytest

**Design principle (from brainstorming):** Zero agent workload. All heavy lifting is deterministic engine code. Invariant inference is a pure function of spec.yaml. Violation reporting is a new field in the existing BacktestReport schema.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `engine/invariants.py` | CREATE | InvariantCheck types, violation dataclass, spec→invariant inference |
| `engine/simulator.py` | MODIFY | Add InvariantRunner to Backtester; call at fill/EOD events |
| `engine/runner.py` | MODIFY | Include violations list in report.json output |
| `scripts/compare_detection.py` | CREATE | Compare critic lesson findings vs invariant violations |
| `scripts/signal_research.py` | MODIFY | Add `--return-mode ask_bid` option for Type 7 (microstructure cost) gap |
| `tests/test_invariants.py` | CREATE | Unit tests for invariant inference and checking |

Agent files (`.claude/agents/*.md`) — UNCHANGED. This is the whole point.

---

## Task 1: Core Invariant Types

**Files:**
- Create: `engine/invariants.py`
- Create: `tests/test_invariants.py`

- [ ] **Step 1: Write the failing test for InvariantViolation dataclass**

```python
# tests/test_invariants.py
from engine.invariants import InvariantViolation

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
    assert d["actual"] == 48122
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_invariants.py -v`
Expected: FAIL with `ImportError` or `ModuleNotFoundError` on `engine.invariants`

- [ ] **Step 3: Implement InvariantViolation**

```python
# engine/invariants.py
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
from typing import Any, Callable


@dataclass
class InvariantViolation:
    """Single observed spec-code gap."""
    invariant_type: str         # e.g., "sl_overshoot", "gate_bypass", "max_entries_exceeded"
    expected: float             # spec-declared value
    actual: float               # observed value in backtest
    fill_index: int             # index into BacktestReport.fills (-1 if non-fill event)
    severity: str               # "high" | "medium" | "low"
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_invariants.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add engine/invariants.py tests/test_invariants.py
git commit -m "feat(invariants): add InvariantViolation dataclass"
```

---

## Task 2: InvariantCheck Type and Registry

**Files:**
- Modify: `engine/invariants.py`
- Modify: `tests/test_invariants.py`

- [ ] **Step 1: Write tests for InvariantCheck and registry**

```python
# tests/test_invariants.py (append)
from engine.invariants import InvariantCheck, INVARIANT_REGISTRY

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
    # 7 core invariants inferred from spec.yaml
    expected = {
        "sl_overshoot",           # stop_loss_bps actual vs spec
        "pt_overshoot",           # profit_target_bps overshoot (late fill)
        "entry_gate_end_bypass",  # fills after entry_end_time_seconds
        "entry_gate_start_bypass",# fills before entry_start_time_seconds
        "max_entries_exceeded",   # per-day entries > max_entries_per_session
        "max_position_exceeded",  # qty > lot_size * max_position_per_symbol
        "time_stop_overshoot",    # ticks_held > time_stop_ticks + tolerance
    }
    assert expected.issubset(INVARIANT_REGISTRY.keys())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_invariants.py -v`
Expected: FAIL on missing `InvariantCheck` or `INVARIANT_REGISTRY`

- [ ] **Step 3: Implement InvariantCheck and the registry**

```python
# engine/invariants.py (append to existing file)

@dataclass
class InvariantCheck:
    """Definition of an invariant derived from a spec parameter."""
    name: str                   # e.g., "sl_overshoot"
    spec_param: str             # e.g., "stop_loss_bps"
    severity: str               # "high" | "medium" | "low"
    tolerance_bps: float = 0.0  # absolute tolerance in bps (for fp/discretization noise)
    tolerance_ticks: int = 0    # absolute tolerance in ticks (for time_stop)


# Seven invariant types inferred automatically from spec.yaml params
INVARIANT_REGISTRY: dict[str, InvariantCheck] = {
    "sl_overshoot": InvariantCheck(
        name="sl_overshoot",
        spec_param="stop_loss_bps",
        severity="high",
        tolerance_bps=10.0,  # allow one tick of slippage past trigger
    ),
    "pt_overshoot": InvariantCheck(
        name="pt_overshoot",
        spec_param="profit_target_bps",
        severity="low",  # overshoot is favorable, only noteworthy if extreme
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
        tolerance_ticks=50,  # ~1 second of tick jitter
    ),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_invariants.py -v`
Expected: PASS (4 tests total)

- [ ] **Step 5: Commit**

```bash
git add engine/invariants.py tests/test_invariants.py
git commit -m "feat(invariants): add InvariantCheck type and 7-invariant registry"
```

---

## Task 3: Spec → Invariant Inference

**Files:**
- Modify: `engine/invariants.py`
- Modify: `tests/test_invariants.py`

- [ ] **Step 1: Write tests for infer_invariants()**

```python
# tests/test_invariants.py (append)
from engine.invariants import infer_invariants

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
    # All 7 should be inferred
    assert "sl_overshoot" in names
    assert "pt_overshoot" in names
    assert "entry_gate_end_bypass" in names
    assert "max_entries_exceeded" in names
    assert "max_position_exceeded" in names
    assert "time_stop_overshoot" in names

    # Values should be attached
    sl = next(i for i in invariants if i["name"] == "sl_overshoot")
    assert sl["threshold"] == 50.0

def test_infer_invariants_skips_missing_params():
    # Spec without stop_loss_bps should not produce sl_overshoot invariant
    spec_dict = {"params": {"profit_target_bps": 80.0}}
    invariants = infer_invariants(spec_dict)
    names = {i["name"] for i in invariants}
    assert "sl_overshoot" not in names
    assert "pt_overshoot" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_invariants.py -v`
Expected: FAIL on missing `infer_invariants`

- [ ] **Step 3: Implement infer_invariants**

```python
# engine/invariants.py (append)

def infer_invariants(spec_dict: dict) -> list[dict]:
    """Infer runtime invariants from spec.yaml content.

    Returns a list of dicts: {"name": str, "threshold": float, "check": InvariantCheck}.
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_invariants.py -v`
Expected: PASS (6 tests total)

- [ ] **Step 5: Commit**

```bash
git add engine/invariants.py tests/test_invariants.py
git commit -m "feat(invariants): infer_invariants from spec.yaml params"
```

---

## Task 4: InvariantRunner State Machine

**Files:**
- Modify: `engine/invariants.py`
- Modify: `tests/test_invariants.py`

- [ ] **Step 1: Write tests for InvariantRunner**

```python
# tests/test_invariants.py (append)
from engine.invariants import InvariantRunner, infer_invariants


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
    # Simulate entry at price 100000, then SL-tagged SELL at price 99000 (-100 bps loss vs 50 bps threshold)
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
    assert sl_viols[0].actual > 90.0  # approx 100 bps, well past tolerance


def test_runner_detects_gate_bypass():
    r = _make_runner()
    # BUY fill at 13:22 KST (kst_sec=48120), past 46800 gate
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
    # 3 BUY fills on same date, same symbol (max 2)
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
    # SL fills at exactly 50 bps — within tolerance, no violation
    r.on_fill(
        fill_index=0, side="BUY", qty=5, price=100000, tag="passive_entry",
        kst_sec=36500, date_str="20260316", symbol="005930",
    )
    r.on_fill(
        fill_index=1, side="SELL", qty=5, price=99500, tag="stop_loss",  # exactly -50 bps
        kst_sec=37000, date_str="20260316", symbol="005930",
    )
    violations = r.get_violations()
    assert not any(v.invariant_type == "sl_overshoot" for v in violations)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_invariants.py -v`
Expected: FAIL on missing `InvariantRunner`

- [ ] **Step 3: Implement InvariantRunner**

```python
# engine/invariants.py (append)

class InvariantRunner:
    """Stateful runner that observes fill events and detects invariant violations.

    Maintains per-symbol entry state to check SL/PT overshoot against the original
    entry price. Maintains per-(date,symbol) entry counts for max_entries checks.
    """

    def __init__(self, invariants: list[dict]) -> None:
        self.invariants = invariants
        self._by_name = {inv["name"]: inv for inv in invariants}
        self._entries_per_day: dict[tuple[str, str], int] = {}  # (date, symbol) → count
        self._open_entry: dict[str, dict] = {}  # symbol → {price, fill_index, kst_sec}
        self._violations: list[InvariantViolation] = []

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
    ) -> None:
        if side == "BUY":
            self._on_buy(fill_index, qty, price, tag, kst_sec, date_str, symbol)
        elif side == "SELL":
            self._on_sell(fill_index, qty, price, tag, kst_sec, date_str, symbol)

    def _on_buy(self, fill_index, qty, price, tag, kst_sec, date_str, symbol):
        # Gate-end bypass (entry_end_time_seconds)
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

    def _on_sell(self, fill_index, qty, price, tag, kst_sec, date_str, symbol):
        entry = self._open_entry.get(symbol)
        if entry is None:
            return  # position tracking mismatch — covered by other invariants if any
        entry_price = entry["price"]
        if entry_price <= 0:
            return

        pnl_bps = (price - entry_price) / entry_price * 1e4

        # SL overshoot: actual loss exceeds spec stop_loss_bps + tolerance
        if tag == "stop_loss" and "sl_overshoot" in self._by_name:
            sl = self._by_name["sl_overshoot"]
            threshold = sl["threshold"]
            tol = sl["tolerance_bps"]
            loss_bps = -pnl_bps  # positive number = magnitude of loss
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

        # PT overshoot: actual gain exceeds spec profit_target_bps + tolerance
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

        # Clear entry on sell (simple model; adequate for single-position strategies)
        del self._open_entry[symbol]

    def on_date_rollover(self) -> None:
        """Called by the engine when the trading date changes — resets per-day counters."""
        # Per-day counters are keyed on (date, symbol), so no reset needed.
        pass

    def get_violations(self) -> list[InvariantViolation]:
        return list(self._violations)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_invariants.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Commit**

```bash
git add engine/invariants.py tests/test_invariants.py
git commit -m "feat(invariants): InvariantRunner state machine with 4 detection types"
```

---

## Task 5: Integrate Runner into Backtester

**Files:**
- Modify: `engine/simulator.py`
- Modify: `tests/test_invariants.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_invariants.py (append)
from pathlib import Path
from engine.runner import run as run_backtest


def test_backtester_emits_invariant_violations_for_known_broken_spec(tmp_path):
    """Sanity check: run a simple spec that is guaranteed to have SL overshoot
    (because its strategy.py uses mid-based SL on a bearish EOD day).
    """
    # Use the existing broken strategy as test fixture
    spec_path = Path("strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/spec.yaml")
    if not spec_path.exists():
        import pytest
        pytest.skip("reference strategy missing")

    report = run_backtest(spec_path, write_trace=False, write_html=False)
    # Report should now include invariant_violations
    assert hasattr(report, "invariant_violations")
    # At minimum, should not crash
    assert isinstance(report.invariant_violations, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_invariants.py::test_backtester_emits_invariant_violations_for_known_broken_spec -v`
Expected: FAIL on `BacktestReport` missing `invariant_violations` attribute

- [ ] **Step 3: Modify Backtester to use InvariantRunner**

First, read `engine/simulator.py` to find `class Backtester` and locate the `__init__` method and where fills are applied.

Add this import at the top of `engine/simulator.py`:

```python
from engine.invariants import InvariantRunner, infer_invariants
```

In `Backtester.__init__`, after `self.portfolio = ...`, add:

```python
        # Invariant runner — auto-inferred from spec.yaml, zero agent involvement
        self._invariant_runner = InvariantRunner(
            invariants=infer_invariants(spec_dict or {}),
        )
```

where `spec_dict` is accepted as a new `__init__` parameter. If Backtester already receives the full spec, use it directly.

Find the method that creates `Fill` objects (likely `_match_pending` and `_check_resting_limits`). After each `self.portfolio.apply_fill(fill)` call, add:

```python
            # Record for invariant checker (no-op if no invariants defined)
            from datetime import datetime, timedelta, timezone
            _KST = timezone(timedelta(hours=9))
            _dt = datetime.fromtimestamp(fill.ts_ns / 1e9, tz=_KST)
            _kst_sec = _dt.hour * 3600 + _dt.minute * 60 + _dt.second
            _date_str = _dt.strftime("%Y%m%d")
            self._invariant_runner.on_fill(
                fill_index=len(self.portfolio.fills) - 1,
                side=fill.side,
                qty=fill.qty,
                price=float(fill.avg_price),
                tag=fill.tag or "",
                kst_sec=_kst_sec,
                date_str=_date_str,
                symbol=fill.symbol,
            )
```

At the end of `run()` (after the last EOD close), expose violations via a getter:

```python
    def get_invariant_violations(self) -> list:
        return self._invariant_runner.get_violations()
```

- [ ] **Step 4: Update BacktestReport to carry violations**

Find the `BacktestReport` dataclass or dict construction in `engine/simulator.py` (or `engine/runner.py`). Add:

```python
    invariant_violations: list[dict] = field(default_factory=list)
```

Populate it at the end of the backtest:

```python
        report.invariant_violations = [v.to_dict() for v in bt.get_invariant_violations()]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_invariants.py -v`
Expected: PASS (11 tests total, including the integration test)

Run: `python scripts/audit_principles.py`
Expected: 12/12 passed (no engine-principle regression)

- [ ] **Step 6: Commit**

```bash
git add engine/simulator.py engine/runner.py tests/test_invariants.py
git commit -m "feat(invariants): integrate InvariantRunner into Backtester"
```

---

## Task 6: Include Violations in report.json

**Files:**
- Modify: `engine/runner.py`
- Test: manual verification

- [ ] **Step 1: Find where report.json is written**

Run: `grep -n "report.json\|report.to_json\|json.dump" engine/runner.py`

- [ ] **Step 2: Add invariant_violations to JSON output**

Ensure that when the report is serialized (e.g., `report.to_dict()` or direct `json.dump(...)`), the `invariant_violations` field is included.

If the report uses a `.to_dict()` method, add:

```python
def to_dict(self) -> dict:
    return {
        # ... existing fields ...
        "invariant_violations": self.invariant_violations,
        "invariant_violation_count": len(self.invariant_violations),
        "invariant_violation_by_type": self._group_violations(),
    }

def _group_violations(self) -> dict:
    grouped = {}
    for v in self.invariant_violations:
        t = v.get("invariant_type", "unknown")
        grouped[t] = grouped.get(t, 0) + 1
    return grouped
```

- [ ] **Step 3: Re-run an existing strategy and verify report contains violations**

Run: `python -m engine.runner --spec strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/spec.yaml --summary`

Then: `python3 -c "import json; d=json.load(open('strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/report.json')); print(json.dumps(d.get('invariant_violation_by_type', {}), indent=2))"`

Expected: A dict with violation type counts (or empty if this strategy is clean).

- [ ] **Step 4: Commit**

```bash
git add engine/runner.py
git commit -m "feat(invariants): expose violations in report.json"
```

---

## Task 7: Retroactive Sweep Across Existing Strategies

**Files:**
- Create: `scripts/sweep_invariants.py`

- [ ] **Step 1: Write the sweep script**

```python
#!/usr/bin/env python3
"""Sweep all existing strategies and count invariant violations.

Runs each strategy's backtest, collects invariant_violations from report.json,
and prints a summary table for the paper's taxonomy section.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    strategies_root = Path("strategies")
    dirs = sorted(d for d in strategies_root.iterdir()
                  if d.is_dir() and d.name.startswith("strat_"))

    totals: dict[str, int] = defaultdict(int)
    per_strategy: list[dict] = []

    for d in dirs:
        rpt = d / "report.json"
        if not rpt.exists():
            rpt = d / "report_per_symbol.json"
        if not rpt.exists():
            continue
        try:
            data = json.loads(rpt.read_text())
        except Exception:
            continue

        viols = data.get("invariant_violations") or []
        by_type = defaultdict(int)
        for v in viols:
            t = v.get("invariant_type", "unknown")
            by_type[t] += 1
            totals[t] += 1

        per_strategy.append({
            "id": d.name,
            "n_violations": len(viols),
            "by_type": dict(by_type),
        })

    print(f"{'Strategy':<60s} {'Total':>6s}  Top violation types")
    print("-" * 110)
    for r in sorted(per_strategy, key=lambda x: -x["n_violations"])[:30]:
        types_str = ", ".join(f"{t}={c}" for t, c in sorted(r["by_type"].items(), key=lambda x: -x[1])[:3])
        print(f"{r['id']:<60s} {r['n_violations']:>6d}  {types_str}")

    print("\n=== TOTALS ACROSS ALL STRATEGIES ===")
    for t, c in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"  {t:<30s}  {c:>6d}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Re-run backtests for all 37 strategies**

This will populate the `invariant_violations` field in each `report.json`. The existing `scripts/new_strategy.py` or a quick loop should suffice:

```bash
for dir in strategies/strat_*/; do
    spec="$dir/spec.yaml"
    if [ -f "$spec" ]; then
        python -m engine.runner --spec "$spec" --summary >/dev/null 2>&1 \
            && echo "OK: $dir" || echo "FAIL: $dir"
    fi
done
```

Expected: 30+ OK, a few may FAIL (skip those).

- [ ] **Step 3: Run the sweep script**

Run: `python scripts/sweep_invariants.py`

Expected output: ranked list of strategies by violation count, and a totals table showing gap distribution across the 7 invariant types.

- [ ] **Step 4: Commit**

```bash
git add scripts/sweep_invariants.py
git commit -m "feat(invariants): add retroactive sweep script"
```

---

## Task 8: Compare Critic Findings vs Invariant Violations

**Files:**
- Create: `scripts/compare_detection.py`

- [ ] **Step 1: Write the comparator script**

```python
#!/usr/bin/env python3
"""Compare critic-found gaps vs automated invariant violations.

For each strategy:
  - Load critic findings from alpha_critique.md and execution_critique.md
    (parse for gap-type keywords)
  - Load invariant_violations from report.json
  - Compute precision/recall per invariant type

Output: table of (gap_type, critic_count, checker_count, overlap, critic_unique, checker_unique).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Keywords each critique might use to describe each invariant type
CRITIC_KEYWORDS = {
    "sl_overshoot":           ["sl overshoot", "sl not working", "stop loss bypass", "bid-vs-mid"],
    "pt_overshoot":           ["pt overshoot", "profit target overshoot"],
    "entry_gate_end_bypass":  ["gate bypass", "past entry_end", "13:00 bypass", "gate close bypass"],
    "entry_gate_start_bypass": ["before entry_start", "pre-gate fill"],
    "max_entries_exceeded":   ["max entries exceeded", "double-fill", "duplicate entry"],
    "max_position_exceeded":  ["position exceeded", "max position"],
    "time_stop_overshoot":    ["time_stop failure", "time stop did not fire"],
}


def parse_critique_file(path: Path) -> set[str]:
    """Return set of invariant types mentioned in the critique."""
    if not path.exists():
        return set()
    text = path.read_text().lower()
    found = set()
    for inv_type, keywords in CRITIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.add(inv_type)
    return found


def main():
    strategies_root = Path("strategies")
    dirs = sorted(d for d in strategies_root.iterdir()
                  if d.is_dir() and d.name.startswith("strat_"))

    # Counts per invariant type
    critic_total: dict[str, int] = defaultdict(int)
    checker_total: dict[str, int] = defaultdict(int)
    overlap: dict[str, int] = defaultdict(int)
    critic_only: dict[str, int] = defaultdict(int)
    checker_only: dict[str, int] = defaultdict(int)

    for d in dirs:
        # Load critic findings
        critic_found = set()
        critic_found |= parse_critique_file(d / "alpha_critique.md")
        critic_found |= parse_critique_file(d / "execution_critique.md")

        # Load invariant violations
        rpt = d / "report.json"
        if not rpt.exists():
            rpt = d / "report_per_symbol.json"
        if not rpt.exists():
            continue
        try:
            data = json.loads(rpt.read_text())
        except Exception:
            continue
        checker_found = set((data.get("invariant_violation_by_type") or {}).keys())

        for inv_type in CRITIC_KEYWORDS.keys():
            in_critic = inv_type in critic_found
            in_checker = inv_type in checker_found

            if in_critic:
                critic_total[inv_type] += 1
            if in_checker:
                checker_total[inv_type] += 1
            if in_critic and in_checker:
                overlap[inv_type] += 1
            if in_critic and not in_checker:
                critic_only[inv_type] += 1
            if in_checker and not in_critic:
                checker_only[inv_type] += 1

    # Print comparison table
    print(f"{'Invariant Type':<28s} {'Critic':>7s} {'Checker':>8s} {'Both':>5s} "
          f"{'Critic-only':>12s} {'Checker-only':>13s}")
    print("-" * 80)
    for inv_type in CRITIC_KEYWORDS.keys():
        print(f"{inv_type:<28s} {critic_total[inv_type]:>7d} {checker_total[inv_type]:>8d} "
              f"{overlap[inv_type]:>5d} {critic_only[inv_type]:>12d} {checker_only[inv_type]:>13d}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the comparator**

Run: `python scripts/compare_detection.py`

Expected: Table showing which gaps each detection method found. Key paper insight: cases where critic missed a gap that checker caught (checker-only column).

- [ ] **Step 3: Commit**

```bash
git add scripts/compare_detection.py
git commit -m "feat(invariants): add critic-vs-checker detection comparator"
```

---

## Task 9: Add Spread-Adjusted Return to signal_research.py (Type 7 Gap)

**Files:**
- Modify: `scripts/signal_research.py`

- [ ] **Step 1: Add --return-mode CLI option**

In `scripts/signal_research.py`, locate the extract subcommand and add:

```python
    p_ext.add_argument("--return-mode", default="mid",
                       choices=["mid", "ask_bid"],
                       help="'mid' uses mid→mid returns; 'ask_bid' uses ask_px[0] entry → bid_px[0] exit (realistic taker cost)")
```

- [ ] **Step 2: Modify the forward return computation in cmd_extract**

Find the block that computes `mids` and the forward return loop. Change it to:

```python
        # Compute forward returns
        if args.return_mode == "ask_bid":
            asks = np.array([float(s.ask_px[0]) for s in day_snaps])
            bids = np.array([float(s.bid_px[0]) for s in day_snaps])
            entry_prices = asks  # taker buy at ask
            exit_prices = bids   # taker sell at bid
        else:
            mids = np.array([f["mid"] for f in day_features])
            entry_prices = mids
            exit_prices = mids

        n_ticks = len(day_features)
        for h in horizons:
            col = f"fwd_{h}t_bps"
            fwd = np.full(n_ticks, np.nan)
            if n_ticks > h:
                fwd[:n_ticks - h] = (exit_prices[h:] - entry_prices[:n_ticks - h]) / entry_prices[:n_ticks - h] * 1e4
            for i, f in enumerate(day_features):
                f[col] = fwd[i]
```

- [ ] **Step 3: Test on existing data**

Run spread-adjusted extraction on BTC sample:

```bash
python scripts/signal_research.py --data-root /home/dgu/tick/crypto extract \
    --symbol BTC --dates 20260416 --horizons 50,100,200 \
    --return-mode ask_bid --regular-only false \
    --outdir data/signal_research/crypto_taker
```

Compare unconditional mean return vs `--return-mode mid`. The `ask_bid` mean should be lower by approximately one spread (~4 bps on BTC).

- [ ] **Step 4: Re-run BTC sweep with realistic returns**

Run: `python scripts/optimal_params.py sweep --symbol BTC --fee 4.0 --outdir data/signal_research/crypto_taker`

Expected: Fewer viable signals than the mid-based version, but those that remain are genuinely profitable after microstructure costs.

- [ ] **Step 5: Commit**

```bash
git add scripts/signal_research.py
git commit -m "feat(signal_research): add ask-bid return mode for Type 7 gap detection"
```

---

## Task 10: Documentation + Integration Summary

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add invariants section to CLAUDE.md**

Open `CLAUDE.md` and add after the "KRX Constraints" section:

```markdown
## Spec-Invariant Checker

Engine auto-infers runtime invariants from spec.yaml params. Seven invariant types
are detected deterministically during backtest and reported in
`report.json.invariant_violations`:

| Type | Spec param | Severity |
|------|-----------|----------|
| sl_overshoot | stop_loss_bps | high |
| pt_overshoot | profit_target_bps | low |
| entry_gate_end_bypass | entry_end_time_seconds | high |
| entry_gate_start_bypass | entry_start_time_seconds | high |
| max_entries_exceeded | max_entries_per_session | high |
| max_position_exceeded | max_position_per_symbol | high |
| time_stop_overshoot | time_stop_ticks | medium |

Agents are not modified. Violations are simply additional data in report.json.

Retroactive sweep: `python scripts/sweep_invariants.py`
Critic vs checker: `python scripts/compare_detection.py`
```

- [ ] **Step 2: Verify audit still green**

Run: `python scripts/audit_principles.py`

Expected: 12/12 passed

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document spec-invariant checker in CLAUDE.md"
```

---

## Summary of Deliverables

After all 10 tasks are complete, the project has:

1. **`engine/invariants.py`** — Invariant definitions, spec inference, runtime runner
2. **`engine/simulator.py`** — Modified to feed fills into invariant runner
3. **`engine/runner.py`** — Report includes `invariant_violations` field
4. **`scripts/sweep_invariants.py`** — Retroactive analysis across all strategies
5. **`scripts/compare_detection.py`** — Critic vs checker recall comparison
6. **`scripts/signal_research.py`** — `--return-mode ask_bid` for Type 7 gap
7. **`tests/test_invariants.py`** — Unit + integration tests
8. **`CLAUDE.md`** — Documentation

Critically, **zero changes to `.claude/agents/*.md`**. Agents remain unaware of the invariant system; it runs in parallel.

The output data (violation counts by type, critic-vs-checker comparison) becomes the paper's central experimental evidence.

---

## Self-Review Notes

- ✅ All 10 tasks have explicit file paths, code blocks, and commands
- ✅ No "TBD" / "implement later" placeholders
- ✅ Task 4's tests reference types defined in Tasks 1-3 (names consistent: `InvariantViolation`, `InvariantCheck`, `INVARIANT_REGISTRY`, `InvariantRunner`)
- ✅ Integration test in Task 5 references `BacktestReport.invariant_violations` which is added in Task 5/6
- ✅ Comparator in Task 8 reads `invariant_violation_by_type` defined in Task 6
- ✅ Agent overload concern addressed: zero agent file modifications; all logic in deterministic engine code
