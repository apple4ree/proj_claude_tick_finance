# Counterfactual PnL Attribution (Engine Intervention) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute true counterfactual PnL (`clean_pnl` vs `bug_pnl`) by running each strategy twice — normal mode + strict mode where the engine intervenes to prevent every invariant violation — so that iterate loop distinguishes bug-generated profit from real signal edge.

**Architecture:** `InvariantRunner` gains a `strict_mode` flag and two query methods: `should_block_order()` for REJECT-type interventions (gate bypass, max entries, max position) and `should_force_sell()` for FORCE-type interventions (bid-based SL, time_stop, PT overshoot). Backtester queries the runner before each fill and each per-tick position update. A new script `scripts/attribute_pnl.py` runs both modes and emits `clean_pnl` / `bug_pnl` / per-invariant impact. In parallel, `strategy-coder.md` is updated with a 7-invariant checklist (Path C) so future strategies avoid the bugs at generation time.

**Tech Stack:** Python 3.10+, existing engine.simulator, pytest

**Design principles:**
- Agent overload: 0 new agents, only strategy-coder prompt gets a short checklist
- Engine overhead: intervention checks are O(1) per fill / per position-tick
- True counterfactual: cascading effects captured because the entire backtest reruns with strict engine

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `engine/invariants.py` | MODIFY | Add `strict_mode`, `should_block_order()`, `should_force_sell()` |
| `engine/simulator.py` | MODIFY | Query runner pre-fill (reject) and per-tick (force) when strict |
| `engine/runner.py` | MODIFY | Add `--strict` CLI flag; pass through to Backtester |
| `scripts/attribute_pnl.py` | CREATE | Dual-run + counterfactual PnL diff |
| `.claude/agents/strategy-coder.md` | MODIFY | Add invariant-aware coding checklist (Path C) |
| `tests/test_invariants.py` | MODIFY | Add strict_mode unit tests |
| `CLAUDE.md` | MODIFY | Document strict mode + attribute_pnl usage |

---

## Task 1: Strict-mode flag and reject-type query methods

**Files:**
- Modify: `engine/invariants.py`
- Modify: `tests/test_invariants.py`

- [ ] **Step 1: Write failing tests for strict-mode reject queries**

Append to `tests/test_invariants.py`:

```python
def test_runner_strict_mode_blocks_gate_end_bypass():
    r = InvariantRunner(
        invariants=infer_invariants({
            "params": {"entry_end_time_seconds": 46800, "entry_start_time_seconds": 36000},
        }),
        strict_mode=True,
    )
    # BUY at 13:22 (past 13:00) — should be blocked
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
    # pos=5 already, incoming BUY would make it 10 → block
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_invariants.py -v -k strict_mode`
Expected: FAIL on missing `strict_mode` parameter and `should_block_order` method

- [ ] **Step 3: Implement strict_mode + should_block_order**

In `engine/invariants.py`, modify `InvariantRunner.__init__`:

```python
    def __init__(self, invariants: list[dict], strict_mode: bool = False) -> None:
        self.invariants = invariants
        self.strict_mode = strict_mode
        self._by_name = {inv["name"]: inv for inv in invariants}
        self._entries_per_day: dict[tuple[str, str], int] = {}
        self._open_entry: dict[str, dict] = {}
        self._violations: list[InvariantViolation] = []
        # Track strict-mode blocks for reporting
        self.strict_blocks: list[dict] = []
```

Add `should_block_order` method:

```python
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
          - max_position_exceeded: post-fill position would exceed cap × lot_size
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_invariants.py -v -k strict_mode`
Expected: 4 PASS (test_runner_strict_mode_blocks_gate_end_bypass, test_runner_strict_mode_blocks_max_entries, test_runner_strict_mode_blocks_max_position, test_runner_permissive_mode_does_not_block)

- [ ] **Step 5: Commit**

```bash
git add engine/invariants.py tests/test_invariants.py
git commit -m "feat(invariants): add strict_mode + should_block_order for REJECT interventions"
```

---

## Task 2: FORCE-type query method (should_force_sell)

**Files:**
- Modify: `engine/invariants.py`
- Modify: `tests/test_invariants.py`

- [ ] **Step 1: Write failing tests for FORCE interventions**

Append to `tests/test_invariants.py`:

```python
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
    # bid dropped to 99400 → loss = 60 bps (> 50 + tol 10)
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_invariants.py -v -k force`
Expected: FAIL on missing `should_force_sell` method

- [ ] **Step 3: Implement should_force_sell**

Add to `InvariantRunner` in `engine/invariants.py`:

```python
    def should_force_sell(
        self,
        symbol: str,
        current_bid: float,
        current_mid: float,
        ticks_held: int,
    ) -> tuple[bool, str]:
        """In strict_mode, return (True, exit_tag) if the open position should be forced out.

        FORCE-type interventions (synthetic SELL emitted by engine):
          - strict_sl: bid-based loss crossed stop_loss_bps (+ tolerance)
          - strict_time_stop: ticks_held crossed time_stop_ticks (+ tolerance)

        Note: pt_overshoot is not forced by the engine because PT is a natural
        upper bound — if the strategy's PT logic is correct, overshoot is rare
        and small (spec tolerance=20 bps).
        """
        if not self.strict_mode:
            return False, ""
        entry = self._open_entry.get(symbol)
        if entry is None:
            return False, ""
        entry_price = entry["price"]
        if entry_price <= 0:
            return False, ""

        # Bid-anchored SL (spec-compliant): exit as soon as bid crosses threshold
        if "sl_overshoot" in self._by_name:
            sl = self._by_name["sl_overshoot"]
            threshold = sl["threshold"]
            loss_bps = (entry_price - current_bid) / entry_price * 1e4
            if loss_bps >= threshold:
                return True, "strict_sl"

        # time_stop (spec-compliant): exit at exact tick threshold
        if "time_stop_overshoot" in self._by_name:
            ts = self._by_name["time_stop_overshoot"]
            threshold = ts["threshold"]
            if ticks_held >= threshold:
                return True, "strict_time_stop"

        return False, ""
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_invariants.py -v -k force`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add engine/invariants.py tests/test_invariants.py
git commit -m "feat(invariants): add should_force_sell for FORCE-type interventions (SL, time_stop)"
```

---

## Task 3: Integrate REJECT interventions into Backtester

**Files:**
- Modify: `engine/simulator.py`

- [ ] **Step 1: Add strict_mode parameter to Backtester.__init__**

In `engine/simulator.py`, modify `Backtester.__init__`:

```python
    def __init__(
        self,
        dates: Iterable[str],
        symbols: Iterable[str],
        strategy: Strategy,
        config: BacktestConfig | None = None,
        spec_dict: dict | None = None,
        strict_mode: bool = False,
    ) -> None:
```

In the same method, replace the invariant runner initialization:

```python
        # Invariant checker (auto-inferred from spec.yaml; zero agent involvement)
        self._invariants = infer_invariants(spec_dict or {})
        self._invariant_runner = InvariantRunner(
            invariants=self._invariants, strict_mode=strict_mode,
        )
        self._strict_mode = strict_mode
```

Add a new rejection counter:

```python
        self.rejected: dict[str, int] = {
            "cash": 0,
            "short": 0,
            "no_liquidity": 0,
            "non_marketable": 0,
            "strict_invariant": 0,   # strict-mode intervention blocks
        }
```

- [ ] **Step 2: Add intervention check helper**

Add method inside `Backtester`:

```python
    def _strict_should_block_buy(self, order: Order, snap: OrderBookSnapshot) -> tuple[bool, str]:
        """Check if a BUY order should be blocked in strict mode. Returns (block, reason)."""
        if not self._strict_mode:
            return False, ""
        dt = datetime.fromtimestamp(snap.ts_ns / 1e9, tz=_KST_TZ)
        kst_sec = dt.hour * 3600 + dt.minute * 60 + dt.second
        date_str = dt.strftime("%Y%m%d")
        pos = self.portfolio.positions.get(order.symbol)
        pos_qty = int(pos.qty) if pos else 0
        entries_today = self._invariant_runner._entries_per_day.get(
            (date_str, order.symbol), 0
        )
        return self._invariant_runner.should_block_order(
            side=order.side,
            kst_sec=kst_sec,
            date_str=date_str,
            symbol=order.symbol,
            current_pos_qty=pos_qty,
            current_day_entries=entries_today,
            incoming_qty=int(order.qty),
            lot_size=self._invariant_lot_size,
        )
```

- [ ] **Step 3: Wire intervention into _match_pending**

Find the section in `_match_pending` where MARKET/LIMIT orders are filled. Right before `walk_book`, add:

```python
            if order.side == BUY:
                blocked, reason = self._strict_should_block_buy(order, snap)
                if blocked:
                    self.rejected["strict_invariant"] += 1
                    continue
```

(Place this right after the SELL short-check block and before `walk_book(...)`.)

- [ ] **Step 4: Wire intervention into _check_resting_limits**

Similarly, in `_check_resting_limits`, before the BUY cash check, add:

```python
            if order.side == BUY:
                blocked, reason = self._strict_should_block_buy(order, snap)
                if blocked:
                    self.rejected["strict_invariant"] += 1
                    continue
```

- [ ] **Step 5: Sanity-run existing tests**

Run: `pytest tests/test_invariants.py -v`
Expected: 19 PASS (11 original + 8 new)

Run: `python scripts/audit_principles.py`
Expected: 12/12 passed

- [ ] **Step 6: Commit**

```bash
git add engine/simulator.py
git commit -m "feat(simulator): integrate REJECT interventions into Backtester (strict_mode)"
```

---

## Task 4: Integrate FORCE interventions into Backtester

**Files:**
- Modify: `engine/simulator.py`

- [ ] **Step 1: Add per-tick intervention hook**

Find the main tick loop in `Backtester.run()`. After the `sr.n_events += 1` line and BEFORE the call to `self._match_pending(snap)`, add:

```python
                # Strict-mode: force exits when spec thresholds cross (bid-based SL, time_stop)
                if self._strict_mode and self._invariants:
                    self._strict_force_sell_check(snap)
```

- [ ] **Step 2: Implement _strict_force_sell_check**

Add method inside `Backtester`:

```python
    def _strict_force_sell_check(self, snap: OrderBookSnapshot) -> None:
        """In strict mode, synthesize SELL fills when spec thresholds cross.

        Checks only the symbol in the current snapshot. Emits a synthetic Fill
        at the current bid price if should_force_sell returns True.
        """
        sym = snap.symbol
        pos = self.portfolio.positions.get(sym)
        if pos is None or pos.qty <= 0:
            return
        # ticks_held = current event count - entry event count
        entry_event = self._entry_event_count.get(sym)
        if entry_event is None:
            return
        ticks_held = self._event_count_per_symbol.get(sym, 0) - entry_event
        current_bid = float(snap.bid_px[0]) if int(snap.bid_px[0]) > 0 else float(snap.mid)
        current_mid = float(snap.mid)

        force, tag = self._invariant_runner.should_force_sell(
            symbol=sym,
            current_bid=current_bid,
            current_mid=current_mid,
            ticks_held=ticks_held,
        )
        if not force:
            return

        # Synthesize SELL: execute MARKET SELL at current bid (same as walk_book sell)
        filled_qty, avg_px = walk_book(snap, SELL, pos.qty)
        if filled_qty <= 0:
            return
        fee = self.config.fee_model.compute(SELL, filled_qty, avg_px)
        fill = Fill(
            ts_ns=snap.ts_ns,
            symbol=sym,
            side=SELL,
            qty=filled_qty,
            avg_price=avg_px,
            fee=fee,
            tag=tag,  # "strict_sl" or "strict_time_stop"
            context=_snap_context(snap),
        )
        self.portfolio.apply_fill(fill)
        self._record_fill_for_invariants(fill)
```

- [ ] **Step 3: Verify imports (walk_book, SELL, Fill, _snap_context)**

These are already defined in the same file — no new imports needed.

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/test_invariants.py -v`
Expected: all 19 PASS

Run: `python scripts/audit_principles.py`
Expected: 12/12 passed

- [ ] **Step 5: Commit**

```bash
git add engine/simulator.py
git commit -m "feat(simulator): integrate FORCE interventions (strict_sl, strict_time_stop)"
```

---

## Task 5: Add --strict CLI flag to runner

**Files:**
- Modify: `engine/runner.py`

- [ ] **Step 1: Add CLI flag**

In `engine/runner.py`, find the argparse setup in the main block (search for `--spec`). Add:

```python
    ap.add_argument("--strict", action="store_true",
                    help="Run with strict mode: engine intervenes to prevent invariant violations")
```

- [ ] **Step 2: Pass through to run()**

Find the function signature `def run(spec_path, ...)` and add `strict: bool = False` parameter. Update the Backtester instantiation at line ~360:

```python
    bt = Backtester(
        dates=spec.universe.dates,
        symbols=spec.universe.symbols,
        strategy=strategy,
        config=cfg,
        spec_dict=spec_dict,
        strict_mode=strict,
    )
```

Also update the per-symbol runner at line ~458:

```python
        bt = Backtester(
            dates=dates, symbols=[sym],
            strategy=strategy, config=cfg,
            spec_dict=spec_dict, strict_mode=strict,
        )
```

- [ ] **Step 3: Find function signature for per-symbol runner and add strict parameter**

Search for `def run_per_symbol` or the function containing line 458. Add `strict: bool = False` parameter.

In the main `if __name__ == "__main__":` block, pass `strict=args.strict` to `run(...)` or `run_per_symbol(...)` as appropriate.

- [ ] **Step 4: Write output path disambiguation**

When `strict=True`, save report to `report_strict.json` instead of `report.json` to avoid overwriting normal run:

```python
    report_fname = "report_strict.json" if strict else "report.json"
    report_path = report_out if report_out is not None else strategy_dir / report_fname
```

Do the same for `report_per_symbol.json` → `report_per_symbol_strict.json` in the per-symbol branch.

- [ ] **Step 5: Smoke test both modes**

Run:
```bash
python -m engine.runner --spec strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/spec.yaml --summary 2>&1 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"normal: return={d['return_pct']}%, violations={d['invariant_violation_count']}, strict_blocks={d['rejected'].get('strict_invariant', 0)}\")"
```
Expected: `normal: return=0.5731%, violations=1, strict_blocks=0`

```bash
python -m engine.runner --spec strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/spec.yaml --strict --summary 2>&1 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"strict: return={d['return_pct']}%, violations={d['invariant_violation_count']}, strict_blocks={d['rejected'].get('strict_invariant', 0)}\")"
```
Expected: strict run produces different return_pct AND strict_blocks >= 1 (the double-fill is now rejected)

- [ ] **Step 6: Verify report_strict.json was created**

Run: `ls -la strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/report_strict.json`
Expected: file exists

- [ ] **Step 7: Commit**

```bash
git add engine/runner.py
git commit -m "feat(runner): add --strict CLI flag for counterfactual runs"
```

---

## Task 6: PnL attribution script

**Files:**
- Create: `scripts/attribute_pnl.py`

- [ ] **Step 1: Write the attribution script**

Create `scripts/attribute_pnl.py`:

```python
#!/usr/bin/env python3
"""Counterfactual PnL attribution via dual backtest runs.

For each strategy:
  1. Run backtest in normal mode (if report.json missing)
  2. Run backtest in strict mode (if report_strict.json missing)
  3. Compute clean_pnl = strict_pnl, bug_pnl = normal_pnl - strict_pnl
  4. Per-invariant impact = sum of (normal - strict) PnL attributable to each type

Usage:
  python scripts/attribute_pnl.py --strategy strat_20260415_0032_passive_maker_bid_sl_3entry_005930
  python scripts/attribute_pnl.py --all
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _run_if_missing(spec_path: Path, strict: bool) -> None:
    """Run backtest if the corresponding report is missing."""
    strategy_dir = spec_path.parent
    report_name = "report_strict.json" if strict else "report.json"
    if (strategy_dir / report_name).exists():
        return
    cmd = ["python", "-m", "engine.runner", "--spec", str(spec_path), "--summary"]
    if strict:
        cmd.append("--strict")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _load_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def attribute(strategy_dir: Path) -> dict | None:
    spec_path = strategy_dir / "spec.yaml"
    if not spec_path.exists():
        return None
    _run_if_missing(spec_path, strict=False)
    _run_if_missing(spec_path, strict=True)

    normal = _load_report(strategy_dir / "report.json") or _load_report(strategy_dir / "report_per_symbol.json")
    strict = _load_report(strategy_dir / "report_strict.json") or _load_report(strategy_dir / "report_per_symbol_strict.json")
    if normal is None or strict is None:
        return None

    # PnL extraction — handle both single-symbol and per-symbol reports
    def _total_pnl(r: dict) -> float:
        if "total_pnl" in r:
            return float(r["total_pnl"])
        # per-symbol
        return sum(float(v.get("total_pnl", 0)) for v in (r.get("per_symbol") or {}).values())

    def _return_pct(r: dict) -> float:
        if "return_pct" in r:
            return float(r["return_pct"])
        return float(r.get("avg_return_pct", 0))

    normal_pnl = _total_pnl(normal)
    strict_pnl = _total_pnl(strict)
    bug_pnl = normal_pnl - strict_pnl

    normal_viol_by_type = normal.get("invariant_violation_by_type") or {}
    strict_blocks = strict.get("rejected", {}).get("strict_invariant", 0)

    return {
        "strategy_id": strategy_dir.name,
        "normal_return_pct": _return_pct(normal),
        "strict_return_pct": _return_pct(strict),
        "normal_pnl": round(normal_pnl, 2),
        "strict_pnl_clean": round(strict_pnl, 2),
        "bug_pnl": round(bug_pnl, 2),
        "clean_pct_of_total": (
            round(strict_pnl / normal_pnl * 100, 2)
            if normal_pnl != 0 else None
        ),
        "normal_violations_by_type": normal_viol_by_type,
        "strict_blocks_total": strict_blocks,
        "interpretation": (
            "clean_pnl is the return if strategy obeyed spec exactly; "
            "bug_pnl is the portion attributable to spec violations"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Counterfactual PnL attribution")
    parser.add_argument("--strategy", help="Single strategy directory name")
    parser.add_argument("--all", action="store_true", help="Attribute all strategies in strategies/")
    args = parser.parse_args()

    if args.all:
        roots = sorted(
            d for d in Path("strategies").iterdir()
            if d.is_dir() and d.name.startswith("strat_")
        )
    elif args.strategy:
        roots = [Path("strategies") / args.strategy]
    else:
        parser.print_help()
        return

    results = []
    for r in roots:
        out = attribute(r)
        if out is not None:
            results.append(out)

    # Summary table
    print(f"{'Strategy':<60s} {'Normal':>8s} {'Clean':>8s} {'Bug':>8s}  {'Clean %':>7s}  Violations")
    print("-" * 110)
    for r in sorted(results, key=lambda x: -(x["bug_pnl"] or 0)):
        viol_summary = ", ".join(f"{t}={c}" for t, c in (r["normal_violations_by_type"] or {}).items())
        clean_pct = r["clean_pct_of_total"]
        clean_pct_str = f"{clean_pct:>6.1f}%" if clean_pct is not None else "    --"
        print(f"{r['strategy_id']:<60s} {r['normal_pnl']:>+8.0f} {r['strict_pnl_clean']:>+8.0f} "
              f"{r['bug_pnl']:>+8.0f}  {clean_pct_str}  {viol_summary}")

    # Save JSON
    outpath = Path("data/attribution_summary.json")
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(results, indent=2))
    print(f"\nFull results saved to {outpath}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test on known buggy strategy**

Run:
```bash
python scripts/attribute_pnl.py --strategy strat_20260415_0032_passive_maker_bid_sl_3entry_005930
```

Expected output format:
```
Strategy                                                 Normal    Clean      Bug  Clean %  Violations
------------------------------------------------------------------------------------------
strat_20260415_0032_passive_maker_bid_sl_3entry_005930  +57309   +XXXXX   +YYYYY   ZZ.Z%  max_position_exceeded=1
```

Where `Bug > 0` confirms the double-fill contributed to the +0.573% return.

- [ ] **Step 3: Commit**

```bash
git add scripts/attribute_pnl.py
git commit -m "feat(scripts): attribute_pnl.py for counterfactual PnL attribution"
```

---

## Task 7: Update strategy-coder agent prompt (Path C)

**Files:**
- Modify: `.claude/agents/strategy-coder.md`

- [ ] **Step 1: Read current prompt**

Run: `wc -l .claude/agents/strategy-coder.md`
Note the line count to insert the checklist before the final section.

- [ ] **Step 2: Append invariant checklist**

Append this section to `.claude/agents/strategy-coder.md` (before any final "output format" or similar trailing section — use Edit to insert in the appropriate place, ideally near other code-quality instructions):

```markdown
## Invariant Checklist (MANDATORY)

The engine auto-checks 7 invariants from spec.yaml. Your generated strategy.py MUST honor each:

1. **sl_overshoot** (stop_loss_bps): SL monitoring MUST use bid_px[0], NOT mid.
   ```python
   current_bid = float(snap.bid_px[0])
   loss_bps = (entry_price - current_bid) / entry_price * 1e4
   if loss_bps >= self.stop_loss_bps:  # correct
       submit MARKET SELL
   ```
   Add a 5-tick guard to avoid false triggers from the fill-spread gap:
   `if ticks_held >= 5:` before the SL check.

2. **entry_gate_end_bypass** (entry_end_time_seconds): Cancel resting BUY when `kst_sec >= entry_end_sec`.
   ```python
   if sym in self._pending_buy and kst_sec >= self.entry_end_sec:
       del self._pending_buy[sym]
       return [Order(sym, None, 0, order_type=CANCEL, tag="cancel_past_entry_end")]
   ```

3. **entry_gate_start_bypass** (entry_start_time_seconds): Do not submit BUY before `entry_start_sec`.

4. **max_entries_exceeded** (max_entries_per_session): Track `self._entries_today[sym]`, increment on submit, compare before submitting.

5. **max_position_exceeded** (max_position_per_symbol): BEFORE submitting a new BUY, check:
   ```python
   pos = ctx.portfolio.positions.get(sym)
   if pos and pos.qty > 0:   # already holding — do not submit second BUY
       return []
   if sym in self._pending_buy:   # pending order in flight — wait for confirmation
       return []
   ```
   This prevents the double-fill bug where two BUYs fill on the same tick.

6. **time_stop_overshoot** (time_stop_ticks): Track `self._ticks_in_position[sym]` and increment each tick while in position. Submit MARKET SELL when it reaches the threshold. Reset to 0 on every new fill.

7. **pt_overshoot** (profit_target_bps): LIMIT SELL at exactly `entry_price * (1 + pt_bps/1e4)` — do not overshoot.

**Verification**: After running the backtest, check `report.json.invariant_violations`. A well-written strategy has an empty list.
```

- [ ] **Step 3: Verify the file is well-formed**

Run: `wc -l .claude/agents/strategy-coder.md`
Expected: line count increased by ~40 lines.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/strategy-coder.md
git commit -m "docs(agent): add 7-invariant checklist to strategy-coder prompt (Path C)"
```

---

## Task 8: Integration test on known buggy strategy

**Files:**
- No new files — runs existing tools

- [ ] **Step 1: Run normal + strict on strat_0032**

```bash
# Normal run (already done in earlier task, but regenerate for cleanliness)
rm -f strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/report.json
rm -f strategies/strat_20260415_0032_passive_maker_bid_sl_3entry_005930/report_strict.json
python scripts/attribute_pnl.py --strategy strat_20260415_0032_passive_maker_bid_sl_3entry_005930
```

- [ ] **Step 2: Verify counterfactual yields lower return**

Expected output characteristics:
- `Normal` PnL matches previously reported +57,309 KRW
- `Clean` PnL is LESS than Normal (double-fill caused by max_position_exceeded is prevented → one RT removed)
- `Bug` PnL is POSITIVE (double-fill helped in this specific case because the 10-share EOD exit landed in a rising market)
- `Clean %` indicates what fraction of profit is genuine edge

- [ ] **Step 3: Sanity test — a strategy with no violations should have clean == normal**

Run attribution on strat_0027 (Optuna-optimized, no known bugs):
```bash
python scripts/attribute_pnl.py --strategy strat_20260415_0027_passive_maker_optuna_best
```
Expected: `Clean % ≈ 100%`, `Bug` pnl ≈ 0

- [ ] **Step 4: Audit**

Run: `python scripts/audit_principles.py`
Expected: 12/12 passed

---

## Task 9: Documentation update

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Extend the invariant section**

In `CLAUDE.md`, find the "Spec-Invariant Checker" section (added previously). Append:

```markdown
### Counterfactual PnL Attribution

엔진은 `--strict` 모드를 지원합니다. 이 모드에서는 invariant 위반이 발생하려는 순간 엔진이 개입해서 spec대로 강제합니다 (REJECT 또는 FORCE SELL 주입).

```bash
# 단일 전략의 clean_pnl vs bug_pnl 계산
python scripts/attribute_pnl.py --strategy <strategy_id>

# 전 전략 일괄
python scripts/attribute_pnl.py --all
```

출력:
- `normal_pnl` — 현행 backtest 결과
- `strict_pnl_clean` — spec 완전 준수 시 기대 수익 (true counterfactual)
- `bug_pnl` — 둘의 차이, 즉 invariant 위반에 의한 기여 (양수면 버그가 수익에 도움, 음수면 해)
- `clean_pct_of_total` — 전체 수익 중 진짜 edge 비중

Iterate 루프의 feedback-analyst는 clean_pnl을 기준으로 진짜 edge 여부를 판단해야 함.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document counterfactual PnL attribution and --strict mode"
```

---

## Summary

After 9 tasks, the system gains:

1. **Dual-mode backtest** — normal + strict intervention runs for every strategy
2. **PnL attribution** — clean_pnl (true edge) vs bug_pnl (invariant-related)
3. **Agent-side gap prevention** — strategy-coder prompt includes all 7 invariant rules
4. **True counterfactual** — engine intervention reruns the full backtest with cascading effects (capital, position, subsequent decisions)

**Paper-side deliverables:**
- Attribution table across 37 strategies: "on average, X% of reported profit comes from invariant violations, not genuine edge"
- Path C measurement: gap rate before vs after strategy-coder prompt update (requires additional iterate runs post-merge)
- Concrete evidence that iterate loops following raw backtest PnL chase bugs, not edge

**Agent overload:**
- 0 new agents, 0 modified prompts except strategy-coder (~40 lines added)
- Runtime overhead: strict mode adds 1 backtest per strategy (engine-level, O(1) per fill/tick for intervention checks)

---

## Self-Review

- ✅ Task 1 defines `strict_mode`, Task 3 consumes it — consistent
- ✅ `should_block_order()` signature matches across Task 1 tests, Task 3 call sites
- ✅ `should_force_sell()` signature matches across Task 2 tests, Task 4 call site
- ✅ `strict_blocks` attribute added in Task 1, not used further but available for diagnostics
- ✅ No "TBD"/"TODO"/"implement later" placeholders
- ✅ Report filename disambiguation (`report_strict.json`) prevents file clobbering
- ✅ Attribution script handles both single-symbol and per-symbol report schemas
- ✅ Agent prompt update (Task 7) is scoped to strategy-coder only; no other agent touched
- ✅ Audit runs expected to remain 12/12 throughout
