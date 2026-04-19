---
id: lesson_20260415_022_taker_market_buy_fee_264pct_gross_signal_reversal_exit_acting_as_second_stop
created: 2026-04-15T12:56:22
tags: [lesson, taker, signal-reversal-exit, fee-burn, obi-filter, regime-dependency, python-stateful]
source: strat_20260415_0024_lob_pressure_mofi_calibrated
metric: "return_pct=-0.31 trades=83 fees=50040"
links:
  - "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"
  - "[[pattern_lob_signal_fires_after_absorption]]"
  - "[[pattern_exit_path_distorts_win_rate_bps_required]]"
---

# taker_market_buy_fee_264pct_gross_signal_reversal_exit_acting_as_second_stop

Observation: Gross PnL was positive (+18,900 KRW) but 50,040 KRW in fees produced -0.31% net — fees consumed 264.8% of realized gross; signal_reversal exits (37.3% of trades) are acting as an unintended second stop at avg -42 bps, worse than the 25 bps hard SL.

Alpha Critique (from alpha-critic): Signal edge is weak at iter2 — OBI delta shrinks from +0.42 (iter1) to +0.12; spread separation is negligible (+0.06 bps). OBI pre-filter at 0.50 is leaking: LOSS avg OBI=0.425 < 0.50 gate implies latency races are delivering fills after the edge has decayed. Selectivity 0.0017% is too restrictive. Severe regime dependency: only 3/23 sessions (9W/3L) profitable; remaining 7 sessions 12W/59L.

Execution Critique (from execution-critic): Execution is poor. Profit target (100 bps) was hit only 5/83 times (6%); trailing stop never activated (70 bps activation unreachable). Signal reversal exits at 37.3% produce avg -42 bps — worse than the -25 bps hard SL they should be complementing. Trailing activation at 70 bps requires the price to run far beyond mean reversion range first. Two-stage exit (partial at 30-35 bps) and gating signal_reversal to gain > -10 bps would reduce exit-path distortion.

Agreement: Both critics agree that the regime is the binding constraint — 3/23 sessions are profitable, meaning the signal fires in adverse regimes indiscriminately. Both agree fee burden (264.8% of gross) is critical.

Disagreement: Alpha-critic attributes weakness to leaky OBI threshold and latency decay; execution-critic attributes it to uncalibrated exit path. Both are independently correct and compound each other.

Priority: both — signal selectivity and exit calibration must improve simultaneously.

How to apply next: Add 3-tick OBI confirmation window to reduce latency-race fills; gate signal_reversal exits to positions with gain > -10 bps; reduce TP to 30-35 bps partial exit to make first profit target reachable.
