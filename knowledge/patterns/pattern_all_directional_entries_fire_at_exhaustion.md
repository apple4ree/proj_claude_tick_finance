---
id: pattern_all_directional_entries_fire_at_exhaustion
tags: [pattern]
severity: high
created: 2026-04-14
links:
  - "[[lesson_20260414_005_mean_reversion_entry_fires_after_reversal_exhausted_ret50_confirmation_too_late]]"
  - "[[lesson_20260414_011_ideator_win_rate_optimism_lob_resilience_recovery_signal_was_anti_edge]]"
  - "[[lesson_20260414_017_all_transition_based_entry_signals_fire_at_informationally_neutral_points]]"
---

# Pattern: All directional entry signals tested fire at exhaustion, not onset

## Root cause

Across five consecutive iterations covering both LOB-derived signals (OBI, imbalance acceleration, surface-depth divergence, LOB resilience) and price-derived signals (rolling high breakout), every directional entry attempted fires at the structural exhaustion point of the move it tries to capture. The confirmation or threshold condition that defines "signal is active" is only satisfiable AFTER the driving momentum has been priced in.

## Evidence

| Strategy | Signal type | Firing condition | Win rate | Lesson |
|---|---|---|---|---|
| strat_0006 mean_reversion | Price return | ret50 > 5 bps (reversal confirmed) | 0% | lesson_005 |
| strat_0009 lob_accel | LOB | imbalance acceleration > 0.15, mid flat | 0% (best trade -87 KRW) | lesson_007 |
| strat_0011 obi_surface_depth | LOB | obi(3)-obi(10) > 0.10 + mid_return in (0,5] | 0% | lesson_009 |
| strat_0013 lob_resilience | LOB | price dip + resilient bid + stabilization | 7.1% | lesson_011 |
| strat_0018 rolling_high_breakout | Price breakout | mid > max(mid[-2001:-1]) | 12.1% | lesson_016 |
| strat_0019 recovery_onset_fsm | FSM/Price return | ret500 crosses 0 after dip < -20 bps | 15.8% | lesson_017 |

In all cases: pre-fee PnL per roundtrip is negative, ruling out fees as the sole cause. The signal direction is wrong — entry fires at or after the local extremum, not before it.

## Structural mechanism

All signals tested share a common structure: they require that a condition be SUSTAINED or EXCEEDED for a minimum duration/magnitude before the entry fires. This latency is intentional (noise filtering) but on 005930 at tick scale, the duration of any directional move is shorter than or equal to the confirmation window. By the time the threshold is breached, the move has already saturated and mean-reversion or consolidation is the next regime.

## Escape routes (not yet tested)

1. **Momentum reversal onset** (TESTED — exhaustion confirmed): Recovery onset FSM (ret500 crosses 0 after dip) fires exactly at re-equilibrium; price has already completed the dip and returned to its 500-tick-ago level with no continuation bias. First-cross FSM entry is also an exhaustion signal. This escape route is now CLOSED.

2. **Time-of-day structural entry**: Abandon tick-level signal entirely. Enter at fixed session time (09:30-09:45 KST) to test if morning session drift provides directional bias independent of any microstructure trigger. This tests whether the market has intraday time structure, not signal structure.

3. **Fade the breakout**: Enter SHORT when a new rolling high is set (opposite of lesson_016 strategy), explicitly targeting the exhaustion-driven reversion. Requires short-selling capability or proxy via a correlated inverse instrument.

## Anti-patterns confirmed across 5+ iterations

- DO NOT enter long when price is at a rolling high or rolling extreme — that IS the exhaustion point.
- DO NOT use a confirmation filter (ret50, sustained imbalance, stabilization condition) on a momentum signal — confirmation selects post-exhaustion ticks by construction.
- DO NOT assume LOB resilience indicates continuation — resilient bid at a dip is a coincident indicator, not a leading one.
- DO NOT iterate on signal threshold tuning (0.1 vs 0.15, 30 bps vs 40 bps) without first verifying the signal fires BEFORE the move, not during it.

## Structural concern for orchestrator

The ideator has now proposed directional-entry variants across 5 iterations without testing reversal-onset or time-of-day entry. Each iteration refines the threshold or lookback but preserves the structural flaw (fires at exhaustion). The orchestrator should constrain the next ideation to EITHER (a) first-cross/onset detection or (b) signal-free time-of-day/session drift entry — not any variant of "enter when condition exceeds threshold."
