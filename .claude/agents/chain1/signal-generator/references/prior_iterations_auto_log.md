# Prior Iterations Auto-Log

Auto-appended by orchestrator. This file is **not** in signal-generator's
required-reading list. Use `grep` to look up a specific spec_id.
Curated lessons live in `prior_iterations_index.md`.

### iteration 000 (2026-04-27T21:15:05.450484Z)


#### iter000_zscore_trade_imb_reversal
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 50 ticks
- **WR**: 0.458041958041958
- **Expectancy**: -0.0711583643715944 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is severe signal flickering: mean regime duration is only 1.4 ticks, compared to a target of 50-150


#### iter000_sticky_obi_long_hold
- **Formula**: `rolling_mean(obi_1, 1000)`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.2, 500 ticks
- **WR**: 0.48484848484848486
- **Expectancy**: -0.06460416796693935 bps
- **Feedback tag**: change_horizon
- **Notes**: With a WR of 48.5% and expectancy of -0.06 bps, the signal currently has no edge. The primary issue is magnitude: the av


#### iter000_multi_family_consensus
- **Formula**: `(ofi_proxy > 0.3) AND (obi_ex_bbo > 0.1) AND (rolling_mean(trade_imbalance_signed, 50) > 0)`
- **Primitives**: ['obi_ex_bbo', 'ofi_proxy', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.5242105263157895
- **Expectancy**: 0.005383654380558492 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is signal flickering, identified by the extremely short mean regime duration of 2.35 ticks over 17,


#### iter000_closing_burst_pressure
- **Formula**: `(obi_1 > 0.5) AND (minute_of_session > 350)`
- **Primitives**: ['obi_1', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The signal produced zero trades (`aggregate_n_trades = 0`) and zero regimes (`aggregate_n_regimes = 0`), making it impos

### iteration 000 (2026-04-28T03:32:25.304339Z)


#### iter000_zscore_trade_imb_reversal
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 50 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The signal is flickering, with a mean regime duration of only 2.13 ticks, far too short for a stable holding period and 


#### iter000_sticky_obi_long_hold
- **Formula**: `rolling_mean(obi_1, 1000)`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.2, 500 ticks
- **WR**: 0.4825511432009627
- **Expectancy**: -0.38717453157018106 bps
- **Feedback tag**: swap_feature
- **Notes**: With a Win Rate of 48.3% over a large sample of 2570 trades, this signal demonstrates no predictive power. The core issu


#### iter000_multi_family_consensus
- **Formula**: `(ofi_proxy > 0.3) AND (obi_ex_bbo > 0.1) AND (rolling_mean(trade_imbalance_signed, 50) > 0)`
- **Primitives**: ['ofi_proxy', 'obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.5254988913525499
- **Expectancy**: 0.0023587563537822856 bps
- **Feedback tag**: add_filter
- **Notes**: The primary issue is signal flickering, with an aggregate mean regime duration of just 2.11 ticks, well below the minimu


#### iter000_closing_burst_pressure
- **Formula**: `(obi_1 > 0.5) AND (minute_of_session > 350)`
- **Primitives**: ['obi_1', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The signal is too restrictive, generating 0 trades and 0 regimes across 24 symbol-days. To gather any statistical eviden

### iteration 001 (2026-04-28T03:42:57.205111Z)


#### iter001_robust_pressure_vs_concentration
- **Formula**: `obi_1 * (1.1 - bid_depth_concentration)`
- **Primitives**: ['obi_1', 'bid_depth_concentration']
- **Threshold / Horizon**: 0.45, 100 ticks
- **WR**: 0.4547294324681038
- **Expectancy**: -0.26566558798432544 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal is fundamentally flawed, with a win rate of 45.5% over 32,054 trades and a negative expectancy of -0.27 bps. 


#### iter001_deep_book_divergence
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.8, 100 ticks
- **WR**: 0.5892281724719963
- **Expectancy**: 0.5732745395540142 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal exhibits extreme inconsistency, with daily win rates ranging from 8.2% to 98.1%, which invalidates it as a re


#### iter001_closing_pressure_relaxed
- **Formula**: `(obi_1 > 0.35) AND (minute_of_session > 350)`
- **Primitives**: ['obi_1', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is too restrictive, generating 0 trades and 0 regimes across the entire backtest period. Despite following the 

### iteration 002 (2026-04-28T04:10:54.962794Z)


#### iter002_persistent_pressure_long_hold
- **Formula**: `rolling_mean(obi_1, 500)`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.15, 500 ticks
- **WR**: 0.477734235838974
- **Expectancy**: -0.5733529666954852 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec fails on its core objective, with a WR of 47.8% and negative expectancy of -0.57 bps over 4,380 trades. Crucial


#### iter002_trade_flow_exhaustion_reversal
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 100 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The primary issue is signal flickering. An average regime duration of 2.13 ticks is too noisy and unstable for a viable 


#### iter002_conviction_in_high_vol
- **Formula**: `(obi_1 > 0.4) AND (obi_ex_bbo > 0.15) AND (rolling_realized_vol(mid_px, 100) > 40)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'mid_px']
- **Threshold / Horizon**: 0.5, 150 ticks
- **WR**: 0.9476304261250498
- **Expectancy**: 2.9631571377014834 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal is `capped_post_fee`. Despite a phenomenal win rate of 94.8%, the average win of 5.37 bps is too small to ove


#### iter002_ask_wall_reversion
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 2.0, 200 ticks
- **WR**: 0.45085015940488843
- **Expectancy**: -0.326781773429734 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec is fundamentally flawed, with a win rate of 45.1% and negative expectancy (-0.33 bps) over 28,849 trades. More 

### iteration 003 (2026-04-28T04:29:22.932290Z)


#### iter003_bbo_deep_book_disagreement
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.8, 1 ticks
- **WR**: 0.5892281724719963
- **Expectancy**: 0.5732745395540142 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal's primary weakness is its severe inconsistency across symbols and days, with daily win rates ranging from 8.2


#### iter003_sticky_ofi_in_high_vol
- **Formula**: `where(rolling_realized_vol(mid_px, 100) > 50, rolling_mean(ofi_proxy, 500), 0)`
- **Primitives**: ['ofi_proxy', 'mid_px']
- **Threshold / Horizon**: 0.15, 1 ticks
- **WR**: 0.49315738025415445
- **Expectancy**: 0.10546313933355494 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec fails to demonstrate any predictive power, with a win rate of 49.3% over 6,850 trades, which is functionally eq


#### iter003_closing_auction_pressure
- **Formula**: `where(minute_of_session > 350, obi_1, 0)`
- **Primitives**: ['minute_of_session', 'obi_1']
- **Threshold / Horizon**: 0.6, 1 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The primary issue is that the signal is too rare, generating zero trades and zero regimes across all 24 symbol-sessions.

### iteration 004 (2026-04-28T04:56:12.425636Z)


#### iter004_trade_flow_exhaustion
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 100 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The signal's primary failure is its extreme noise, leading to flickering with a mean duration of only 2.13 ticks, far to


#### iter004_durable_book_consensus
- **Formula**: `(rolling_mean(obi_1, 500) > 0.2) AND (rolling_mean(obi_ex_bbo, 500) > 0.1)`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 1.0, 250 ticks
- **WR**: 0.7439024390243902
- **Expectancy**: 4.46189815395508 bps
- **Feedback tag**: drop_feature
- **Notes**: Despite a high aggregate Win Rate of 0.744, the signal is not viable due to severe cross-symbol inconsistency, with dail


#### iter004_ask_wall_reversion
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 2.0, 100 ticks
- **WR**: 0.45085015940488843
- **Expectancy**: -0.326781773429734 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal fails to show any edge, with a WR of 45.1% and negative expectancy (-0.33 bps) over 28,849 trades. The core h

### iteration 005 (2026-04-28T05:16:54.213296Z)


#### iter005_extreme_ask_wall_reversion
- **Formula**: `zscore(ask_depth_concentration, 300) > 3.5`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 1.0, 100 ticks
- **WR**: 0.9129438717067583
- **Expectancy**: 1.3240021824978867 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal is `capped_post_fee` and economically unviable due to an average win of only 7.51 bps. More importantly, it i


#### iter005_long_horizon_ofi_trend
- **Formula**: `rolling_mean(ofi_proxy, 1000) > 0`
- **Primitives**: ['ofi_proxy']
- **Threshold / Horizon**: 1.0, 500 ticks
- **WR**: 0.6847290640394089
- **Expectancy**: 0.9012957432351405 bps
- **Feedback tag**: change_horizon
- **Notes**: Despite a strong win rate of 68.5%, the signal is economically unviable due to an extremely low raw expectancy (+0.90 bp

### iteration 006 (2026-04-28T05:41:32.194300Z)


#### iter006_trade_flow_exhaustion
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 100 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is severe signal flickering, evidenced by a mean regime duration of just 2.1 ticks over 44,840 regi


#### iter006_sticky_pressure_in_high_vol
- **Formula**: `(rolling_mean(obi_1, 500) > 0.15) AND (rolling_realized_vol(mid_px, 100) > 50)`
- **Primitives**: ['obi_1', 'mid_px']
- **Threshold / Horizon**: 1.0, 500 ticks
- **WR**: 0.6116102280580511
- **Expectancy**: 1.052167308826954 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal is `capped_post_fee` with an average win of only 13.31 bps, making it impossible to deploy profitably on KRX 


#### iter006_deep_book_reversion
- **Formula**: `obi_ex_bbo`
- **Primitives**: ['obi_ex_bbo']
- **Threshold / Horizon**: 0.4, 100 ticks
- **WR**: 0.5639821554355483
- **Expectancy**: 0.677287897900243 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal is economically undeployable (`capped_post_fee` with an average win of 13.0 bps) and exhibits extreme cross-s


#### iter006_closing_microprice_trend
- **Formula**: `where(minute_of_session > 360, microprice_dev_bps, 0)`
- **Primitives**: ['microprice_dev_bps', 'minute_of_session']
- **Threshold / Horizon**: 1.5, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The signal is too rare to evaluate, generating zero trades (`aggregate_n_trades = 0`). The threshold of 1.5 bps for `mic

### iteration 007 (2026-04-28T06:19:56.287421Z)


#### iter007_trade_flow_exhaustion_reversal
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 100 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The primary issue is signal flickering, evidenced by an extremely short mean regime duration of 2.13 ticks (target < 5) 


#### iter007_sticky_full_book_pressure
- **Formula**: `rolling_mean(obi_1, 1000) + rolling_mean(obi_ex_bbo, 1000)`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.3, 1000 ticks
- **WR**: 0.5165562913907285
- **Expectancy**: -0.47064280599131286 bps
- **Feedback tag**: swap_feature
- **Notes**: The signal shows no predictive power, with a Win Rate of 51.7% over a large sample of 1027 trades being statistically eq


#### iter007_consensus_vs_patient_liquidity
- **Formula**: `(obi_1 > 0.4) AND (obi_ex_bbo > 0.2) AND (ask_depth_concentration < 0.1)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration']
- **Threshold / Horizon**: 1.0, 200 ticks
- **WR**: 0.9587468379062074
- **Expectancy**: 3.2955418980451805 bps
- **Feedback tag**: add_regime_filter
- **Notes**: The signal has an excellent WR of 95.9% but is fundamentally unprofitable (`capped_post_fee`) because the average win of

### iteration 008 (2026-04-28T06:44:48.304683Z)


#### iter008_exhaustion_reversal_in_low_vol
- **Formula**: `zscore(trade_imbalance_signed, 300) > 2.5 AND rolling_realized_vol(mid_px, 100) < 30`
- **Primitives**: ['trade_imbalance_signed', 'mid_px']
- **Threshold / Horizon**: 1.0, 100 ticks
- **WR**: 0.8571428571428571
- **Expectancy**: 0.07539615364627991 bps
- **Feedback tag**: add_filter
- **Notes**: The core issue remains severe signal flickering, with an aggregate mean duration of only 2.77 ticks. This is a primary f


#### iter008_consensus_in_high_vol
- **Formula**: `(obi_1 > 0.4) AND (obi_ex_bbo > 0.2) AND (ask_depth_concentration < 0.1) AND (rolling_realized_vol(mid_px, 100) > 40)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'mid_px']
- **Threshold / Horizon**: 1.0, 100 ticks
- **WR**: 0.9523370941745337
- **Expectancy**: 2.964198712713347 bps
- **Feedback tag**: combine_with_other_spec
- **Notes**: The spec has an exceptionally high Win Rate (95.2%) but is `capped_post_fee` because its average win of +7.68 bps cannot


#### iter008_sticky_microprice_trend
- **Formula**: `rolling_mean(microprice_dev_bps, 500) > 0.2`
- **Primitives**: ['microprice_dev_bps']
- **Threshold / Horizon**: 1.0, 1000 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The signal condition `rolling_mean(microprice_dev_bps, 500) > 0.2` was never satisfied, resulting in 0 regimes and 0 tra


#### iter008_closing_auction_conviction
- **Formula**: `(rolling_mean(obi_1, 50) > 0.3) AND (obi_ex_bbo > 0.1) AND (rolling_mean(trade_imbalance_signed, 50) > 0) AND (minute_of_session > 350)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'trade_imbalance_signed', 'minute_of_session']
- **Threshold / Horizon**: 1.0, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The primary finding is that the signal is far too selective, resulting in zero trades (`aggregate_n_trades = 0`) across 

### iteration 009 (2026-04-28T07:07:37.698861Z)


#### iter009_confirmed_long_hold_pressure
- **Formula**: `(rolling_mean(obi_1, 1000) > 0.1) AND (obi_1 > 0.4 AND obi_ex_bbo > 0.2 AND ask_depth_concentration < 0.1)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration']
- **Threshold / Horizon**: 1.0, 1 ticks
- **WR**: 0.9503127171646977
- **Expectancy**: 3.212620439730567 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal is `capped_post_fee`. Despite a very high Win Rate of 95.0%, the average win magnitude of +8.82 bps is insuff


#### iter009_sticky_microprice_relaxed
- **Formula**: `rolling_mean(microprice_dev_bps, 500)`
- **Primitives**: ['microprice_dev_bps']
- **Threshold / Horizon**: 0.05, 1 ticks
- **WR**: 0.4838930774503084
- **Expectancy**: -0.33895957867730464 bps
- **Feedback tag**: swap_feature
- **Notes**: With a WR of 48.4% over 4454 trades, the signal is statistically equivalent to a random walk. The underlying primitive, 


#### iter009_closing_momentum_burst
- **Formula**: `rolling_momentum(mid_px, 100) * (minute_of_session > 350)`
- **Primitives**: ['mid_px', 'minute_of_session']
- **Threshold / Horizon**: 100.0, 1 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The primary issue is that the signal never triggered, producing an `aggregate_n_trades` of 0. This makes it impossible t

### iteration 010 (2026-04-28T07:45:11.975567Z)


#### iter010_trade_flow_exhaustion_reversal
- **Formula**: `zscore(trade_imbalance_signed, 500)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 3.0, 100 ticks
- **WR**: 0.5114285714285715
- **Expectancy**: 0.0006613710614631648 bps
- **Feedback tag**: add_filter
- **Notes**: The primary issue is signal flickering. The aggregate mean regime duration of 2.06 ticks is below the stability threshol


#### iter010_sticky_deep_book_pressure
- **Formula**: `rolling_mean(obi_ex_bbo, 2000)`
- **Primitives**: ['obi_ex_bbo']
- **Threshold / Horizon**: 0.05, 1000 ticks
- **WR**: 0.4666666666666667
- **Expectancy**: -4.090999883697802 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec fails its primary objective due to an extremely high signal duty cycle of 97.3%, making it a buy-and-hold artif


#### iter010_microprice_velocity_stable_spread
- **Formula**: `where(abs(spread_change_bps) < 1.0, microprice_velocity, 0)`
- **Primitives**: ['microprice_velocity', 'spread_change_bps']
- **Threshold / Horizon**: 0.5, 50 ticks
- **WR**: 0.48172697957721244
- **Expectancy**: -0.0005507117359542288 bps
- **Feedback tag**: add_filter
- **Notes**: The primary issue is extreme signal flickering, evidenced by a mean regime duration of just 1.3 ticks, which is far too 


#### iter010_bbo_deep_book_divergence
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.7, 100 ticks
- **WR**: 0.5782628195544924
- **Expectancy**: 0.4859479671312513 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal is `capped_post_fee` with an average win of only +3.63 bps. More importantly, its performance is highly incon

### iteration 011 (2026-04-28T08:02:24.763646Z)


#### iter011_long_horizon_microprice_stickiness
- **Formula**: `rolling_mean(microprice_dev_bps, 500)`
- **Primitives**: ['microprice_dev_bps']
- **Threshold / Horizon**: 0.3, 500 ticks
- **WR**: 0.5069238377843719
- **Expectancy**: -0.2271333991631417 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec fails to show any predictive edge, with an aggregate Win Rate of 50.7% over 3,286 trades being statistically eq


#### iter011_book_shape_reversion
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 3.0, 100 ticks
- **WR**: 0.41644774414620217
- **Expectancy**: -0.45536246801759644 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal demonstrates no predictive power (WR=41.6% over 34,503 trades) and is fundamentally unprofitable (`capped_pos

### iteration 012 (2026-04-28T08:23:33.051476Z)


#### iter012_extreme_trade_flow_reversion
- **Formula**: `zscore(trade_imbalance_signed, 500)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 3.0, 100 ticks
- **WR**: 0.5114285714285715
- **Expectancy**: 0.0006613710614631648 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is severe signal flickering, with an aggregate mean duration of just 2.1 ticks over 31,344 regimes.


#### iter012_sticky_ofi_long_hold
- **Formula**: `rolling_mean(ofi_proxy, 500)`
- **Primitives**: ['ofi_proxy']
- **Threshold / Horizon**: 0.1, 500 ticks
- **WR**: 0.48976203652462647
- **Expectancy**: -0.08546965918555374 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec has failed to demonstrate any predictive edge, with an aggregate Win Rate of 49.0% over 13,465 trades being equ


#### iter012_conviction_at_closing
- **Formula**: `(obi_1 > 0.5 AND obi_ex_bbo > 0.2) AND (minute_of_session > 350 AND minute_of_session < 380)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The primary issue is the complete lack of signal generation, with 0 trades and 0 regimes observed across all 24 backtest

### iteration 013 (2026-04-28T08:54:56.037798Z)


#### iter013_full_book_conviction_long_hold
- **Formula**: `rolling_mean(obi_1, 500) + rolling_mean(obi_ex_bbo, 500)`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.4, 500 ticks
- **WR**: 0.52
- **Expectancy**: 0.16756375023087164 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec fails to show any predictive edge, with an aggregate Win Rate of 52.0% over a large sample (1736 regimes), whic


#### iter013_closing_burst_pressure_relaxed
- **Formula**: `where(minute_of_session > 350 and minute_of_session < 380, rolling_mean(obi_1, 50), -1)`
- **Primitives**: ['minute_of_session', 'obi_1']
- **Threshold / Horizon**: 0.25, 100 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec is a buy-and-hold artifact, evidenced by the aggregate signal duty cycle of 1.0, which violates the regime-stat


#### iter013_ask_wall_reversion_in_high_vol
- **Formula**: `where(rolling_realized_vol(mid_px, 200) > 60, zscore(ask_depth_concentration, 300), -99)`
- **Primitives**: ['mid_px', 'ask_depth_concentration']
- **Threshold / Horizon**: 2.0, 100 ticks
- **WR**: 0.5310719131614654
- **Expectancy**: 0.12353761962350308 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal demonstrates a marginal pre-fee edge (WR=53.1% over 14,626 trades) but is fundamentally undeployable due to i

### iteration 014 (2026-04-28T09:15:34.634901Z)


#### iter014_trade_flow_exhaustion
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 100 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is signal flickering, evidenced by a very low mean regime duration of 2.13 ticks (below the sanity 


#### iter014_velocity_consensus
- **Formula**: `(microprice_velocity > 0.1) AND (book_imbalance_velocity > 0.05) AND (abs(spread_change_bps) < 1.0)`
- **Primitives**: ['microprice_velocity', 'book_imbalance_velocity', 'spread_change_bps']
- **Threshold / Horizon**: 0.5, 100 ticks
- **WR**: 0.8047728579643473
- **Expectancy**: 0.2411472996226347 bps
- **Feedback tag**: add_filter
- **Notes**: The signal is unusable in its current form due to severe 'flickering', where the mean regime duration is only 1.14 ticks


#### iter014_patient_trader_consensus
- **Formula**: `(rolling_mean(obi_ex_bbo, 200) > 0.1) AND (rolling_mean(trade_imbalance_signed, 200) > 0)`
- **Primitives**: ['obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 200 ticks
- **WR**: 0.2822384428223844
- **Expectancy**: -1.436445294968778 bps
- **Feedback tag**: drop_feature
- **Notes**: The spec fails catastrophically with a Win Rate of 28.2% and negative raw expectancy (-1.44 bps) over a large sample (63

### iteration 015 (2026-04-28T09:46:57.656268Z)


#### iter015_extreme_trade_flow_reversion
- **Formula**: `(zscore(trade_imbalance_signed, 300) > 2.5) AND (rolling_realized_vol(mid_px, 100) < 30)`
- **Primitives**: ['trade_imbalance_signed', 'mid_px']
- **Threshold / Horizon**: 1.0, 100 ticks
- **WR**: 0.8571428571428571
- **Expectancy**: 0.07539615364627991 bps
- **Feedback tag**: add_filter
- **Notes**: The primary issue is severe signal flickering, with an aggregate mean duration of 2.77 ticks, which is below the sanity 


#### iter015_long_horizon_pressure_consensus
- **Formula**: `(rolling_mean(obi_1, 1000) > 0.1) AND (rolling_mean(obi_ex_bbo, 1000) > 0.05)`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 1.0, 1000 ticks
- **WR**: 0.7165775401069518
- **Expectancy**: 4.207231722810625 bps
- **Feedback tag**: drop_feature
- **Notes**: The primary issue is the signal's inconsistent performance across different symbols. The Win Rate for symbol 000660 (78.


#### iter015_closing_burst_reversion
- **Formula**: `(zscore(ask_depth_concentration, 300) > 2.0) AND (minute_of_session > 350)`
- **Primitives**: ['ask_depth_concentration', 'minute_of_session']
- **Threshold / Horizon**: 1.0, 150 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The primary finding is a complete lack of signal activation, with 0 trades and 0 regimes generated across all 24 backtes

### iteration 016 (2026-04-28T10:10:43.311569Z)


#### iter016_sticky_microprice_in_high_vol
- **Formula**: `where(rolling_realized_vol(mid_px, 200) > 60, rolling_mean(microprice_dev_bps, 500), -1)`
- **Primitives**: ['microprice_dev_bps', 'mid_px']
- **Threshold / Horizon**: 0.1, 500 ticks
- **WR**: 0.47534602076124566
- **Expectancy**: -0.6772185980757228 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec fails a primary sanity check for the regime-state paradigm: its aggregate signal duty cycle of 96.8% is above t


#### iter016_closing_wall_reversion_relaxed
- **Formula**: `where(minute_of_session > 350, zscore(ask_depth_concentration, 300), -99)`
- **Primitives**: ['ask_depth_concentration', 'minute_of_session']
- **Threshold / Horizon**: 1.5, 150 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: swap_feature
- **Notes**: The spec produced a buy-and-hold artifact with an aggregate signal duty cycle of 1.0, violating a key sanity check. This


#### iter016_full_book_and_velocity_consensus
- **Formula**: `(obi_1 > 0.4) AND (obi_ex_bbo > 0.15) AND (book_imbalance_velocity > 0.05)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'book_imbalance_velocity']
- **Threshold / Horizon**: 1.0, 100 ticks
- **WR**: 0.9026128266033254
- **Expectancy**: 0.6252332725236772 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is severe signal flickering. The aggregate mean regime duration is only 1.09 ticks, which triggers 

### iteration 017 (2026-04-28T10:27:23.061239Z)


#### iter017_trade_flow_exhaustion_reversal
- **Formula**: `where(rolling_realized_vol(mid_px, 200) < 60, zscore(trade_imbalance_signed, 300), 0)`
- **Primitives**: ['trade_imbalance_signed', 'mid_px']
- **Threshold / Horizon**: 2.5, 100 ticks
- **WR**: 0.5267175572519084
- **Expectancy**: 0.00921494337963717 bps
- **Feedback tag**: add_filter
- **Notes**: The primary weakness is severe signal flickering, which triggers a critical sanity check failure. The aggregate mean reg


#### iter017_closing_burst_consensus
- **Formula**: `where(minute_of_session > 350, (obi_1 > 0.3) AND (obi_ex_bbo > 0.1) AND (rolling_mean(trade_imbalance_signed, 50) > 0), 0)`
- **Primitives**: ['minute_of_session', 'obi_1', 'obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 150 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is untestable as it generated zero trades and zero regimes across the entire backtest period. The primary cause

### iteration 018 (2026-04-28T10:41:51.261238Z)


#### iter018_persistent_imbalance_acceleration
- **Formula**: `rolling_mean(book_imbalance_velocity, 100)`
- **Primitives**: ['book_imbalance_velocity']
- **Threshold / Horizon**: 0.01, 300 ticks
- **WR**: 0.4671886651752424
- **Expectancy**: -0.08170210734206196 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec fails on its core metrics, with a WR of 46.7% and negative expectancy (-0.082 bps) over a large sample, indicat


#### iter018_closing_burst_deep_book_pressure
- **Formula**: `(obi_ex_bbo > 0.3) AND (minute_of_session > 350 AND minute_of_session < 380)`
- **Primitives**: ['obi_ex_bbo', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 200 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is untestable as it produced zero trades and zero regimes across the entire backtest. This fails the core sanit


#### iter018_fragile_book_flow_break
- **Formula**: `rolling_mean(trade_imbalance_signed, 30) * (bid_depth_concentration > 0.3)`
- **Primitives**: ['trade_imbalance_signed', 'bid_depth_concentration']
- **Threshold / Horizon**: 10.0, 80 ticks
- **WR**: 0.9288461538461539
- **Expectancy**: 1.2898331299199612 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal is tagged `capped_post_fee` because its average win of +7.63 bps cannot cover KRX transaction costs, making i

### iteration 019 (2026-04-28T11:10:57.938554Z)


#### iter019_long_horizon_obi_persistence
- **Formula**: `rolling_mean(obi_1, 1000)`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.15, 1 ticks
- **WR**: 0.4673055242390079
- **Expectancy**: -0.5182509007436996 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec fails, with a WR of 46.7% and negative expectancy (-0.52 bps) over 2662 trades. More critically, it's tagged `c


#### iter019_extreme_trade_flow_reversal
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 1 ticks
- **WR**: 0.5105988341282459
- **Expectancy**: 0.001782439711199545 bps
- **Feedback tag**: add_filter
- **Notes**: The spec fails the 'signal flickering' sanity check: the mean regime duration of 2.1 ticks is critically low (<5) with a


#### iter019_book_divergence_reversal
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.7, 1 ticks
- **WR**: 0.5782628195544924
- **Expectancy**: 0.4859479671312513 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal is tagged `capped_post_fee` as its average win of +7.12 bps vs average loss of -8.42 bps makes it impossible 


#### iter019_closing_vol_burst_pressure
- **Formula**: `(rolling_mean(obi_1, 100) > 0.3) AND (minute_of_session > 350) AND (rolling_realized_vol(mid_px, 100) > 50)`
- **Primitives**: ['obi_1', 'minute_of_session', 'mid_px']
- **Threshold / Horizon**: 1.0, 1 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is untestable as it produced zero trades and zero regimes across the entire backtest, failing the core sanity c

### iteration 020 (2026-04-28T11:28:58.150560Z)


#### iter020_ofi_trend_in_calm_regime
- **Formula**: `(rolling_mean(ofi_proxy, 500) > 0.08) AND (rolling_realized_vol(mid_px, 200) < 40)`
- **Primitives**: ['ofi_proxy', 'mid_px']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.5010030090270813
- **Expectancy**: 0.1480488635867873 bps
- **Feedback tag**: swap_feature
- **Notes**: The signal has no predictive edge, with an aggregate WR of 50.1% over 4722 trades, which is firmly within the noise band


#### iter020_microprice_acceleration
- **Formula**: `microprice_velocity`
- **Primitives**: ['microprice_velocity']
- **Threshold / Horizon**: 3.0, 1 ticks
- **WR**: 0.49595346484572583
- **Expectancy**: -0.018557222225254747 bps
- **Feedback tag**: add_filter
- **Notes**: The spec fails the critical 'signal flickering' sanity check, with a mean regime duration of only 1.20 ticks (<5) over 2


#### iter020_closing_auction_obi_ramp
- **Formula**: `(rolling_mean(obi_1, 100) > 0.3) AND (minute_of_session > 380)`
- **Primitives**: ['obi_1', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is untestable as it generated zero trades and zero regimes, failing the core sanity check for signal rarity (0.
