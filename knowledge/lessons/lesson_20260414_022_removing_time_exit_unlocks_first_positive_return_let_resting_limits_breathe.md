---
id: lesson_20260414_022_removing_time_exit_unlocks_first_positive_return_let_resting_limits_breathe
created: 2026-04-14T12:29:06
tags: [lesson, time-exit, resting-limit, win-rate, krx, universe-filter, trade-count]
source: strat_20260414_0024_krx_resting_limit_no_time_exit
metric: "return_pct=0.0069 trades=30 fees=15206.49 win_rate_pct=40.0"
---

# Removing time exit unlocks first positive return: let resting limits breathe

Observation: Eliminating the max_hold_ticks time exit produced the first positive avg_return_pct (+0.0069%) across the iteration series. With a time exit, winners were cut before the +150 bps resting SELL LIMIT could fill; without it, 000660 harvested +7.95% on 4 roundtrips.

Why: A resting-limit exit strategy needs price to travel +150 bps. Under KRX microstructure, that move may take more ticks than the time gate allowed. The time exit was systematically converting latent winners into forced flat trades, erasing edge before it materialized. Without the gate, the asymmetric payoff (129 bps net win vs 71 bps net loss) can operate as designed.

How to apply next: Never combine a wide resting profit target with a tight time exit — they are structurally contradictory. Universe-filter by symbol win rate (drop any symbol below 30% win rate across 5+ trades, e.g. 034020 at 20%). To increase trade count, loosen the spread gate from 21 to 18 bps; OBI and imbalance thresholds are the binding constraints, not spread width.
