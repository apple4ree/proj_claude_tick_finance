---
id: lesson_20260414_015_trailing_stop_prematurely_exits_momentum_winners_before_profit_target
created: 2026-04-14T09:52:56
tags: [lesson, trailing_stop, exit_management, momentum, winner_cutting, 005930]
source: strat_20260414_0017_momentum_continuation_1000t_long
links: ["[[pattern_win_rate_ceiling_mandates_hold_duration]]", "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"]
metric: "return_pct=-0.2067 trades=46 fees=9365.6 win_rate=21.7"
---

# trailing_stop_prematurely_exits_momentum_winners_before_profit_target

Observation: Best trade gross return (~80 bps) is below the 150 bps profit target, indicating no trade reached the target; the trailing stop (activate at 75 bps, floor at 30 bps) is consistently terminating positions mid-run, capping upside at ~80 bps.

Why: The trailing floor is set 45 bps below the activation point (75 - 30 = 45 bps). For a momentum continuation strategy, this gap is too tight — any normal intraday oscillation after a 75 bps move will trigger the floor, exiting before the 150 bps target is reached. The asymmetry (150 take / 50 stop) becomes meaningless when the effective take is ~80 bps, reducing the reward/risk from 3:1 to ~1.6:1 and pushing win-rate breakeven from 25% up toward 38%.

How to apply next: Remove the trailing stop or widen its parameters substantially (activate at 120 bps, floor at 60 bps so gap = 60 bps). Alternatively raise the profit target to 200 bps and stop to 60 bps to achieve a breakeven of (60+21)/(200+60) = 31.2% win rate, which sits below the oracle ceiling of 40% on this universe.
