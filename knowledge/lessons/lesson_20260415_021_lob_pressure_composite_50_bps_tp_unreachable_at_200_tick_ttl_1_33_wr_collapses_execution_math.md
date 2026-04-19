---
id: lesson_20260415_021_lob_pressure_composite_50_bps_tp_unreachable_at_200_tick_ttl_1_33_wr_collapses_execution_math
created: 2026-04-15T12:30:39
tags: [lesson, lob, mofi, composite-threshold, time-stop, profit-target-calibration, fee-burden, python-stateful]
source: strat_20260415_0023_lob_pressure_mofi_slope
metric: "return_pct=-3.65 trades=225 fees=233169"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
  - "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"
  - "[[pattern_lob_signal_fires_after_absorption]]"
---

# LOB-pressure composite: 50 bps TP unreachable at 200-tick TTL, 1.33% WR collapses execution math

Observation: A stateful LOB-pressure strategy (mOFI + BVI + slope_asym composite) produced 225 trades at 1.33% WR and -3.65% return, with 83.6% of exits via time_stop at avg -35.25 bps — both the signal threshold and exit calibration were wrong simultaneously.

Alpha Critique (from alpha-critic): Signal-edge is genuinely present — WIN entries show OBI 0.71 vs LOSS entries 0.29 (delta +0.42), confirming OBI separation is predictive. However, the composite threshold=0.15 admits only 0.0045% of ticks, making it over-restrictive: 225 trades across 8 days is adequate volume, but the 1.33% WR (not 55-67% target) means the composite fires at structurally weak moments despite the good OBI signal. Hypothesis is not supported: price did not move 50 bps within 200 ticks at any meaningful frequency.

Execution Critique (from execution-critic): Execution math was calibrated for 67% WR that never materialized. The 50 bps profit target is unreachable at KRX tick-velocity inside 200 ticks — only 1 TP in 225 trades confirms this. The time_stop at 200 ticks allows slow adverse drift past the 20 bps hard stop (avg EOD/time exit = -35.25 bps vs -35.25 bps SL — identical, indicating the stop is not cutting losses early). Fees = 176% of gross loss (233k KRW on -132k gross PnL), making fee drag secondary to the broken exit structure.

Agreement: Both critics agree the exit structure is the binding failure — TP too far, time_stop too long, trailing never activated.

Disagreement: Alpha-critic says threshold is too restrictive; execution-critic says the execution math was wrong from calibration. Both are correct — they are independent failures.

Priority: both — but execution first because even a strong signal cannot recover from a TP that never fires.

How to apply next: Reduce profit_target 50→15-20 bps, time_stop 200→30-50 ticks. Add OBI > 0.50 hard pre-filter. Relax composite_threshold 0.15→0.08 to increase sample size.
