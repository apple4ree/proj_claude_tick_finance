---
id: lesson_20260414_021_time_exit_suppresses_avg_win_bps_below_resting_limit_target
created: 2026-04-14T12:19:14
tags: [lesson, time_exit, resting_limit, avg_win_bps, payoff_asymmetry, krx, win-rate, universe-filter, trade-count]
source: strat_20260414_0023_krx_resting_limit_150bps_6sym
links: ["[[pattern_exit_path_distorts_win_rate_bps_required]]", "[[pattern_win_rate_ceiling_mandates_hold_duration]]"]
metric: "return_pct=-0.0076 trades=30 fees=15189.47 avg_win_bps=46.26 avg_loss_bps=-67.86 win_rate_pct=43.33"
---

# Time exit suppresses resting limit payoff -- removing it reveals the natural holding advantage

Observation: With a 150 bps resting SELL LIMIT and 8000-tick time exit, avg_win_bps landed at only 46 bps -- far below the 129 bps net the resting limit would deliver. Most winning trades exited via the time gate at modest gains, not via the limit fill. This produced a deeply negative EV (net -18.5 bps/trade) even though win rate (43.3%) exceeded the breakeven threshold (35.5%).

Why: The time exit acts as an early escape valve that harvests small unrealised gains before the resting limit has a chance to fill. The winning payoff distribution is then dominated by small time-exit gains rather than genuine 150 bps hits, collapsing avg_win_bps and breaking the expected payoff asymmetry the strategy was designed around.

How to apply next: Remove max_hold_ticks entirely. Let every position run until the resting SELL LIMIT fills (+150 bps), the hard stop fires (-50 bps), or EOD close. With avg_win_bps -> ~129 bps net, EV projects to +15.7 bps/trade at the observed 43.3% win rate. Only add a time exit if the resting limit fill-rate can be measured and shown to be negligible.

## Validation -- strat_20260414_0024_krx_resting_limit_no_time_exit (2026-04-14)

Confirmed: Eliminating max_hold_ticks produced the first positive avg_return_pct (+0.0069%) across the iteration series. With a time exit, winners were cut before the +150 bps resting SELL LIMIT could fill; without it, 000660 harvested +7.95% on 4 roundtrips. The asymmetric payoff (129 bps net win vs 71 bps net loss) operated as designed.

Key rule: Never combine a wide resting profit target with a tight time exit -- they are structurally contradictory. Universe-filter by symbol win rate (drop any symbol below 30% win rate across 5+ trades, e.g. 034020 at 20%). To increase trade count, loosen the spread gate from 21 to 18 bps; OBI and imbalance thresholds are the binding constraints, not spread width.
