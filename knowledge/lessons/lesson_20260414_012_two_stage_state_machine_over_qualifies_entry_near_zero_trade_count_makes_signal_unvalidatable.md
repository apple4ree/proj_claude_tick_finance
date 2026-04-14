---
id: lesson_20260414_012_two_stage_state_machine_over_qualifies_entry_near_zero_trade_count_makes_signal_unvalidatable
created: 2026-04-14T09:09:18
tags: [lesson, low-trade-count, state-machine, entry-filter, over-qualification, signal-rarity]
source: strat_20260414_0014_vol_burst_obi_cross_momentum
links: ["[[pattern_spec_calibration_failure_wastes_iteration]]"]
metric: "return_pct=-0.3741 trades=4 fees=23408.7"
---

# Two-stage state machine over-qualifies entry: near-zero trade count makes signal unvalidatable

Observation: vol_burst_obi_cross_momentum fired only 2 round-trips across 14 symbol-days (7 dates x 2 symbols). With n=2 and 0% win rate, no statistical inference about signal quality is possible.

Why: The AND-conjunction of two independent rare events — volume burst >2x 50-tick avg AND OBI sign-flip within a 5-tick arm window — multiplicatively suppresses trigger frequency. Each filter alone may fire ~5-15% of ticks; together they fire <0.02% of ticks, producing fewer trades than needed for even the weakest hypothesis test.

How to apply next: When a two-stage state machine yields fewer than ~20 trades per universe, dissolve one stage: either drop the burst gate and enter on OBI flip alone, or loosen burst_multiplier to 1.3x and widen arm_window_ticks to 15-20. Alternatively, validate each condition independently across the full universe before combining them.
