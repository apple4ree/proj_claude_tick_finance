---
id: lesson_20260414_017_all_transition_based_entry_signals_fire_at_informationally_neutral_points
created: 2026-04-14T10:10:48
tags: [lesson, entry-signal, exhaustion, transition, equilibrium, fsm]
source: strat_20260414_0019_recovery_onset_fsm_500
metric: "return_pct=-0.4055 trades=114 fees=23254"
links:
  - "[[pattern_all_directional_entries_fire_at_exhaustion]]"
---

# All transition-based entry signals fire at informationally neutral points

Observation: Every entry signal tried so far — OBI flip, momentum threshold, rolling-high breakout, recovery onset FSM — fires at a state *transition*, not during directional continuation. At the exact tick of FIRE, the market has just completed a move (exhausted momentum, re-crossed a level, returned to equilibrium), leaving no net directional bias.

Why: Transition-detecting signals are inherently lagged. By definition they identify when a condition has just changed, which means the causative force is already spent. For recovery onset specifically, ret500 crossing 0 means price is back where it was 500 ticks ago — the dip is over but there is no reason price will continue upward.

How to apply next: Abandon signal-triggered entry entirely for one iteration. Try time-of-day entry (e.g., tick ~200 after session open) or volume-delta burst entry that identifies unusual flow episodes *during* the causal impulse, not after it resolves.
