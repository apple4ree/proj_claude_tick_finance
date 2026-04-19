---
id: lesson_20260414_017_all_transition_based_entry_signals_fire_at_informationally_neutral_points
created: 2026-04-14T10:10:48
tags: [lesson, entry-signal, exhaustion, transition, equilibrium, fsm, rolling-breakout, anti-edge, momentum, 005930, signal-timing, local-top]
source: strat_20260414_0019_recovery_onset_fsm_500
links:
  - "[[pattern_all_directional_entries_fire_at_exhaustion]]"
  - "[[pattern_win_rate_ceiling_mandates_hold_duration]]"
metric: "return_pct=-0.4055 trades=114 fees=23254"
---

# All transition-based entry signals fire at informationally neutral points -- directional entries fire at exhaustion

## General pattern

Every entry signal tried so far -- OBI flip, momentum threshold, rolling-high breakout, recovery onset FSM -- fires at a state *transition*, not during directional continuation. At the exact tick of FIRE, the market has just completed a move (exhausted momentum, re-crossed a level, returned to equilibrium), leaving no net directional bias.

Why: Transition-detecting signals are inherently lagged. By definition they identify when a condition has just changed, which means the causative force is already spent. For recovery onset specifically, ret500 crossing 0 means price is back where it was 500 ticks ago -- the dip is over but there is no reason price will continue upward.

## Concrete example -- rolling-high breakout (strat_0018)

132 trades, 12.1% win rate (breakeven 31.2%), -0.58% return. The rolling 2000-tick high breakout fires when current mid first exceeds the prior 2000-tick maximum -- structurally, this is the moment the market has just completed a directional run and is at its LOCAL TOP before mean-reversion or consolidation. A new rolling high is definitionally the peak of the lookback window. Best trade gross ~102 bps confirms even favorable setups never reached the +200 bps target; the signal enters at exhaustion, not onset.

How to apply next: Abandon signal-triggered entry entirely for one iteration. Try time-of-day entry (e.g., tick ~200 after session open) or volume-delta burst entry that identifies unusual flow episodes *during* the causal impulse, not after it resolves. Alternatively, invert the timing -- require a confirmed DOWN-to-UP momentum reversal targeting onset of recovery, not peak strength.
