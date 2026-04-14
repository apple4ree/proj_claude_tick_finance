---
id: lesson_20260414_004_per_symbol_minimum_spread_must_exceed_physical_tick_price_floor
created: 2026-04-14T04:04:23
tags: [lesson, spread, calibration, tick_size, entry_gate, 005930, 000660]
source: strat_20260414_0004_duration_extended_trend_005930
metric: "return_pct=0.0 trades=0 fees=0.0"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
---

# Per-symbol minimum spread must exceed physical tick/price floor

Observation: Setting spread_bps <= 3.0 on 005930 (price ~183 000 KRW, min tick 100 KRW) yields a physical minimum spread of 100/183 000 × 10 000 ≈ 5.46 bps — so the gate is structurally impossible and entry never fires (0 trades).
Why: spread_bps thresholds that are tighter than tick_size/mid_price × 10 000 can never be satisfied regardless of market conditions. The threshold appears valid in absolute bps but ignores that discrete tick spacing imposes a per-symbol floor.
How to apply next: Before writing spread_bps <= X in a spec, compute min_spread_bps = tick_size / mid_price × 10 000 for every symbol in the universe. Set the gate at least 1.5× above that floor (e.g., 005930 floor ≈ 5.5 bps → gate spread_bps <= 7.0 to allow 2-tick spreads).

---

## Additional observation — strat_20260414_0008_hynix_accel_trend_low_freq (000660)

Observation: Setting spread_bps < 6.0 on 000660 (price ~928 000 KRW, min tick 1 000 KRW) yields a physical minimum spread of 1 000/928 000 × 10 000 ≈ 10.78 bps — nearly double the threshold. Gate fires 0 times across 81 371 regular-session ticks.
Why: 000660 trades at a much higher price tier than 005930, so its tick-size floor in bps is roughly 2× larger. A threshold copied from a lower-priced symbol context is guaranteed to be below the floor.
How to apply next: Add 000660 to the per-symbol floor table: floor ≈ 10.8 bps → minimum viable gate spread_bps <= 16.0 (1-tick spread). Note also that 000660 round-trip cost ≈ 32 bps (21 bps commission+tax + ~11 bps spread), which is structurally worse than 005930 (~26 bps). Even with a corrected gate, 000660 is a harder target for tick-scale strategies.
