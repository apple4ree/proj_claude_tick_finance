---
id: lesson_20260414_008_signal_threshold_outside_observed_distribution_fires_zero_ticks_mode_c_calibration_failure
created: 2026-04-14T07:24:37
tags: [lesson, calibration, imbalance, threshold, distribution, zero-trades, mode-c]
source: strat_20260414_0010_imbalance_exhaustion_fade
metric: "return_pct=0.0 trades=0 fees=0.0"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
---

# signal threshold outside observed distribution fires zero ticks mode C calibration failure

Observation: imbalance_exhaustion_fade set low_threshold=-0.45 but 005930/20260313 total_imbalance minimum was -0.405 and median +0.467 (strongly bid-heavy day). The threshold fell outside the entire observable range, producing 0 qualifying ticks and 0 trades.
Why: Thresholds derived from theoretical or cross-asset intuition can miss the realized intraday distribution. On a one-sided day (bid-heavy), ask-side imbalance extremes never reached the required depth. The parameter was not validated against percentiles of the signal's actual distribution before spec submission.
How to apply next: Before setting any signal threshold, compute p1/p5/p50/p95/p99 of the signal on the target symbol/date. Set extreme-entry thresholds at p5 or tighter only if sufficient ticks (>=500) qualify; if p5 produces <100 ticks, widen to p10. For total_imbalance on 005930, use -0.20 to -0.25 for moderate entry gates; -0.45 is inaccessible on bid-heavy days.
