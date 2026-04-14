---
id: lesson_20260414_007_lob_imbalance_acceleration_fires_at_peak_not_onset
created: 2026-04-14T07:20:17
tags: [lesson, lob, imbalance, acceleration, signal-timing, anti-edge]
source: strat_20260414_0009_lob_pressure_acceleration_reversion
metric: "return_pct=-0.0721 trades=30 fees=5807.55 win_rate=0"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
---

# LOB imbalance acceleration fires at peak, not onset

Observation: When total_imbalance acceleration (delta over 20 ticks) exceeds 0.15 while mid is flat, the signal fires at or near peak imbalance — the point at which order book pressure is already exhausting and price reverts. Win rate was 0% across 15 roundtrips; best roundtrip still lost 87 KRW, meaning no trade ever reached the 25 bps target.\nWhy: A momentum-style acceleration threshold detects the steepest part of the imbalance ramp, which is structurally late. Market makers replenish or cancel at peak imbalance, causing rapid reversal. The mid-flat filter further selects moments where no price follow-through has yet occurred — confirming the signal is pre-reversal, not pre-trend.\nHow to apply next: Replace acceleration detection with an onset filter: require that imbalance crossed from near-zero to the threshold within the lookback window (first-cross logic), not that it spiked at the tail. Alternatively, fade the signal — enter in the opposite direction of the acceleration impulse, targeting mean reversion explicitly.
