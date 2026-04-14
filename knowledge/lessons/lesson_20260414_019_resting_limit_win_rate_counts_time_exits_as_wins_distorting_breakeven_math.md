---
id: lesson_20260414_019_resting_limit_win_rate_counts_time_exits_as_wins_distorting_breakeven_math
created: 2026-04-14T11:54:46
tags: [lesson, win_rate, time_exit, resting_limit, breakeven_math, fee_math, exit_path]
source: strat_20260414_0021_krx_wide_spread_resting_limit_directional
links: ["[[pattern_exit_path_distorts_win_rate_bps_required]]", "[[pattern_win_rate_ceiling_mandates_hold_duration]]"]
metric: "return_pct=-0.2357 trades=105 fees=111550"
---

# resting-limit win-rate counts time-exits as wins distorting breakeven math

Observation: 272210 achieved 53.85% win rate (above the 39.2% breakeven for 100/30 bps targets with 21 bps round-trip fees) yet delivered -0.015% return. At face value this is impossible: 7 wins×79 bps net minus 6 losses×51 bps net = +247 bps expected. The explanation is that win_rate_pct counts any positive-return round-trip as a win regardless of whether the resting SELL LIMIT at +100 bps was actually hit. A 2000-tick time-exit at +5 bps registers as a win but nets 5-21=-16 bps after fees, indistinguishable from a loss in EV terms.

Why: The resting SELL LIMIT at avg_cost+100 bps is a conditional exit — it only fills if price reaches that level within max_hold_ticks. When price drifts directionlessly, the time exit fires at an arbitrary intermediate price. Wins by sign are not wins by fee-adjusted EV. The breakeven formula only holds when the profit exit reliably hits its target bps. With a time-exit path, the realized win size distribution is left-skewed relative to the nominal 100 bps target.

How to apply next: Track average_win_bps and average_loss_bps separately. Replace binary win_rate_pct as the primary diagnostic. Extend max_hold_ticks to 5000+ so price has time to reach the +100 bps limit, or add a trailing stop that locks in gains above +40 bps so time exits do not return near zero.
