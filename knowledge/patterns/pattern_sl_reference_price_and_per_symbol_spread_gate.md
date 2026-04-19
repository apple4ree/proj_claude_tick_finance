---
id: pattern_sl_reference_price_and_per_symbol_spread_gate
created: 2026-04-15T00:00:00
tags: [pattern, stop-loss, reference-price, bid_price, mid_price, spread-gate, per_symbol, symbol-heterogeneity, execution_bug, krx, multi_symbol, passive-maker]
severity: critical
links:
  - "[[lesson_20260415_023_passive_maker_first_positive_return_obi_inverted_pt_phantom_time_stop_is_real_exit]]"
  - "[[lesson_20260415_024_sl_triggers_on_mid_but_exits_at_bid_permits_catastrophic_slippage_plus_spread_gate_must_be_per_symbol]]"
---

# Pattern: Two compounding design flaws in multi-symbol passive-maker strategies

These two failures always appear together in multi-symbol python-path strategies because both
stem from treating per-symbol parameters as universal constants. Either flaw alone destroys a
strategy; combined they are catastrophic.

## Failure Mode 1 — Stop-loss monitors mid-price but MARKET SELL fills at bid

**Symptom**: A trade nominally stopped at 50 bps SL produces a realized loss of 362 bps.
The SL condition fires at the correct mid-price level, but by the time the MARKET SELL order
walks the book, the bid has collapsed — the execution fills at bid_px[0], not mid.

**Root cause**: In the engine, a MARKET SELL walks the book using `bid_px[0]` as the best
available price. If the strategy monitors `(current_mid - entry_mid) / entry_mid * 10000` for
the SL trigger, there is a structural gap between trigger price and fill price equal to
approximately `spread / 2` under normal conditions. During adverse book conditions (thin bid
side, rapid LOB imbalance), this gap can exceed 10x the nominal SL level.

The engine is correct — it fills MARKET SELL at bid. The strategy is wrong to compute
unrealized loss from mid rather than from the actual exit price proxy (bid).

**Rule**: For long positions, always monitor SL trigger using `snap.bid_px[0]`:
```python
# WRONG — uses mid, understates realized loss
unrealized_bps = (snap.mid - entry_mid) / entry_mid * 10000
if unrealized_bps <= -stop_loss_bps:
    submit MARKET SELL

# CORRECT — uses bid, matches actual MARKET SELL fill price
unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
if unrealized_bps <= -stop_loss_bps:
    submit MARKET SELL
```

**Consequence of using mid**: The SL fires "on time" by the mid-price measure, but the
realized loss at fill is always `stop_loss_bps + spread/2 + adverse_selection_slippage`.
During LOB stress, spread can widen 3-10x its normal level precisely at the moment the SL
triggers — this is when adverse selection is worst and the bid-vs-mid gap is largest.

**Secondary guard**: Gate the SL condition by `ticks_since_entry >= 5` to prevent immediate
stop-outs caused by the spread at fill (the first tick after a passive BID fill, `bid_px[0]`
has already moved down by the fill itself).

---

## Failure Mode 2 — Universal spread gate silently eliminates symbols

**Symptom**: A 3-symbol strategy with `spread_gate_bps=8` produces 0 signals for 2 of 3
symbols across the full IS period, reducing the strategy to a single-symbol strategy by
accident rather than design.

**Root cause**: Each KRX symbol has a hard physical minimum spread determined by its tick
grid:
- 005930 (Samsung, ~183,000 KRW, tick=100): min spread ≈ 5.46 bps → viable gate: `< 8.2`
- 000660 (SK Hynix, ~928,000 KRW, tick=1,000): min spread ≈ 10.78 bps → viable gate: `< 16`
- 005380 (Hyundai, ~200,000 KRW, tick=500): min spread ≈ 25 bps → viable gate: `< 35`

A single universal `spread_gate=8` is below the physical minimum for 000660 and 005380. Those
symbols will fire 0 entries — not because their signals are weak but because their minimum
tradable spread exceeds the gate. This is a Mode A calibration failure (see
`pattern_spec_calibration_failure_wastes_iteration`) extended to multi-symbol context.

**Rule**: Spread gates must be per-symbol. In python-path strategies, use a dict:
```python
SPREAD_GATES_BPS = {
    "005930": 8.2,
    "000660": 16.0,
    "005380": 35.0,
    "034020": 12.0,   # ~106,150 KRW, tick=100 → floor ≈ 9.4 bps
    "272210": 14.0,   # ~145,650 KRW, tick=100 → floor ≈ 6.9 bps
}
```

Always compute the per-symbol floor before spec submission:
```
floor_bps = tick_size / mid_price * 10000
gate = max(floor_bps * 1.5, desired_gate_bps)
```

**Verification**: After a multi-symbol backtest, confirm each symbol has `n_entries > 0`.
If any symbol has 0 entries and the session gate should have qualified at least some days,
suspect Mode A — the spread gate is below the physical floor for that symbol.

---

## Combined checklist for multi-symbol python-path strategies

Before submitting the spec:
- [ ] SL condition uses `snap.bid_px[0]` (not `snap.mid`) for long-position trigger
- [ ] SL condition gated by `ticks_since_entry >= 5` (cannot fire at tick 0 post-fill)
- [ ] Per-symbol spread gate dict defined in `params`, not a single universal value
- [ ] Each symbol's spread gate >= 1.5 × (tick_size / mid_price × 10000)
- [ ] After backtest: confirm `n_entries > 0` for every symbol in the universe
- [ ] Entry time gate enforced by canceling resting orders when `kst_sec >= entry_end_sec`
  (otherwise resting BID fills 20+ minutes past the nominal entry window close)
- [ ] `time_stop_ticks` calibrated against actual session length:
  3000 ticks at ~71,500 ticks/session ≈ 25 minutes — if entry is at 10:00 and
  time_stop=3000, this fires at 10:25 — intentional? If not, use 1000-1500.

## Relationship to existing patterns

- `pattern_spec_calibration_failure_wastes_iteration`: Mode A (threshold below physical
  floor) is the underlying mechanism for Failure Mode 2. This pattern extends Mode A to
  multi-symbol context and names the per-symbol dict fix.
- `pattern_stop_exit_leaves_orphaned_resting_limit`: Failure Mode 1 here is distinct —
  that pattern covers rolling-window SL anchoring and orphaned limit orders. This pattern
  covers the bid-vs-mid reference price error that causes realized loss to exceed nominal SL.
- `pattern_win_rate_ceiling_mandates_hold_duration`: The SL bid-reference fix changes the
  effective stop level: a nominal 50 bps SL monitoring bid is triggered earlier than the
  same SL monitoring mid (by ~spread/2). Recalibrate SL levels after switching reference.
