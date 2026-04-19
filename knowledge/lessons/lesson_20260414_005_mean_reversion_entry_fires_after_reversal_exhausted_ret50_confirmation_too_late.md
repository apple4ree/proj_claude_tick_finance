---
id: lesson_20260414_005_mean_reversion_entry_fires_after_reversal_exhausted_ret50_confirmation_too_late
created: 2026-04-14T06:23:01
tags: [lesson, mean-reversion, entry-latency, hold-time, 005930, confirmation-lag, lob, imbalance, acceleration, signal-timing, anti-edge, obi, surface-depth, absorption]
source: strat_20260414_0006_mean_reversion_005930
metric: "return_pct=-0.0391 trades=14 fees=2711.7"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
  - "[[pattern_lob_signal_fires_after_absorption]]"
---

# LOB signal fires after absorption, not at onset -- confirmation lag makes entry structurally late

## Mean-reversion confirmation too late (strat_0006)

7 roundtrips, 0% win rate, best trade still -390 KRW. The entry requires ret50 > 5 bps as a reversal-confirmation gate, but 50 ticks of upward move have already elapsed before the order fires. The remaining mean-reversion edge is consumed; the 100-tick minimum hold forces exposure into the re-mean-reversion leg. Mean-reversion moves on 005930 at intraday tick scale are short-lived. Entry-too-late / hold-too-long is a structural mismatch.

## LOB imbalance acceleration fires at peak (strat_0009)

When total_imbalance acceleration (delta over 20 ticks) exceeds 0.15 while mid is flat, the signal fires at or near peak imbalance -- the point at which order book pressure is already exhausting and price reverts. Win rate was 0% across 15 roundtrips; best roundtrip still lost 87 KRW. A momentum-style acceleration threshold detects the steepest part of the imbalance ramp, which is structurally late. Market makers replenish or cancel at peak imbalance, causing rapid reversal.

## Surface-depth OBI divergence enters after absorption (strat_0011)

obi(depth=3) - obi(depth=10) > 0.10 combined with mid_return_bps(5) in (0,5] produced 0% win rate over 28 roundtrips on 005930 (Sharpe -3.84). The surface-depth divergence fires when shallow queue is already bid-heavy and a short positive return is already visible. The mid_return_bps(5) > 0 filter inadvertently selects post-absorption ticks -- the signal requires price to have already moved.

## Common root cause

All three signals detect LOB state *after* the informational content has been absorbed into price. Confirmation gates (ret50, acceleration threshold, divergence + positive return) systematically delay entry past the profitable window.

How to apply next: Replace confirmation-based detection with onset detection: first-cross logic for imbalance, contemporaneous acceleration (ret10 not ret50), or require mid_return == 0 (divergence not yet absorbed). Alternatively, fade the signal -- enter in the opposite direction of the detected state, targeting mean reversion explicitly.
