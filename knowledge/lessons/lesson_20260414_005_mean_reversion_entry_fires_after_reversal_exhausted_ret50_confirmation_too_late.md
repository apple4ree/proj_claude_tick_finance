---
id: lesson_20260414_005_mean_reversion_entry_fires_after_reversal_exhausted_ret50_confirmation_too_late
created: 2026-04-14T06:23:01
tags: [lesson, mean-reversion, entry-latency, hold-time, 005930, confirmation-lag]
source: strat_20260414_0006_mean_reversion_005930
metric: "return_pct=-0.0391 trades=14 fees=2711.7"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
---

# mean_reversion_entry_fires_after_reversal_exhausted_ret50_confirmation_too_late

Observation: 7 roundtrips, 0% win rate, best trade still -390 KRW — all trades lost including the theoretically best setup. The entry requires ret50 > 5 bps as a reversal-confirmation gate, but this means 50 ticks of upward move have already elapsed before the order fires. The remaining mean-reversion edge is consumed; the 100-tick minimum hold then forces exposure into the re-mean-reversion leg.

Why: Mean-reversion moves on 005930 at intraday tick scale are short-lived. Using ret50 > 5 as confirmation delays entry until the move is partially complete. Pairing this with a 100-tick minimum hold creates a structural entry-too-late / hold-too-long mismatch — the position is entered near the reversion peak and exits during the pullback.

How to apply next: Replace the ret50 confirmation with a contemporaneous accelerating-signal (e.g. ret10 > 2 bps, not ret50 > 5) to enter earlier in the reversal. Reduce minimum hold to 30-50 ticks to match mean-reversion speed. Alternatively, remove the minimum-hold constraint entirely and rely only on ret50 < 0 as exit.
