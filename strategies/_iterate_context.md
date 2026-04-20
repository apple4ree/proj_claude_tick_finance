# Iterate Context Log

Per-iteration summaries across `/iterate` runs. Read by downstream agents (alpha-designer / execution-designer / feedback-analyst). Handoff-fidelity measurement data is deliberately excluded — see `strategies/<id>/handoff_audit.json` instead. Automatically appended by `scripts/iterate_finalize.py`.

## Iteration 0 — strat_20260417_0001_trajectory_multi_3sym [meta]
- **Timestamp**: 2026-04-17T03:07:39+00:00
- **Result**: return -0.0629%, WR 16.7%, 6 roundtrips
- **Attribution**: clean_pct=59.9%, bug_pnl=-2520.51
- **Alpha**: trajectory crossover multi-symbol; 1 WIN of 6
- **Execution**: max_position_exceeded x3 on 010140 (bug-driven loss)
- **Priority**: execution
- **Seed → next**: smoke test with explicit field propagation

## Iteration 1 — strat_20260417_0002_smoke_042700_obi5 [local]
- **Timestamp**: 2026-04-17T03:07:39+00:00
- **Result**: return -0.0327%, WR 0.0%, 1 roundtrips
- **Attribution**: clean_pct=100.0%, bug_pnl=+0.00
- **Alpha**: inconclusive; OBI decayed by fill time (0.56 < 0.58); passive-fill suppression
- **Execution**: sl_overshoot structural (tick-grid gap), bug_pnl=0; limit→marketable adverse selection
- **Priority**: both
- **Seed → next**: SL=33bps floor + aggressive entry at ask

## Iteration 2 — strat_20260417_0003_pilot_s1_042700_obi10 [local]
- **Timestamp**: 2026-04-17T05:04:36+00:00
- **Result**: return +0.0076%, WR 66.7%, 3 roundtrips
- **Attribution**: clean_pct=-1150.1%, bug_pnl=+9537.37
- **Alpha**: obi_10 inconclusive n=3; OBI inverted in sample; exit mismatch to brief (no trailing)
- **Execution**: 0 violations BUT bug_pnl=+9537 (strict force_sell ignores 5-tick guard) — methodology artifact
- **Priority**: both
- **Seed → next**: add sl_guard_ticks to spec + re-enable trailing

## Iteration 2 — strat_20260417_0004_pilot_s2_010140_spread [local]
- **Timestamp**: 2026-04-17T05:20:35+00:00
- **Result**: return -0.0182%, WR 12.5%, 8 roundtrips
- **Attribution**: clean_pct=91.8%, bug_pnl=-149.71
- **Alpha**: spread_bps direction-agnostic; 7/8 SL; symbol in -6.94% downtrend (long-only disadvantage)
- **Execution**: tick size LLM error (100 vs 50 KRW); trailing never activated (7 immediate stops)
- **Priority**: alpha
- **Seed → next**: OBI gate + regime filter

## Iteration 3 — strat_20260417_0005_pilot_s3_034020_spread [local]
- **Timestamp**: 2026-04-17T05:41:31+00:00
- **Result**: return -0.1549%, WR 0.0%, 18 roundtrips
- **Attribution**: clean_pct=-0.0%, bug_pnl=-15485.80
- **Alpha**: 0% WR; 034020 -6.6% downtrend; long-only mean-reversion fail
- **Execution**: entry_gate_end_bypass=18 (false+: sec convention mismatch); sl_overshoot=7; OBI/spread gate leak (8/18, 7/18)
- **Priority**: alpha
- **Seed → next**: trend filter + gate audit + bid-rebound SL

## Iteration 4 — strat_20260417_0006_pilot_s4_035420_obi5 [local]
- **Timestamp**: 2026-04-17T06:11:40+00:00
- **Result**: return -0.1347%, WR 0.0%, 6 roundtrips
- **Attribution**: clean_pct=100.0%, bug_pnl=+0.00
- **Alpha**: 035420 obi_5 + trend filter: 0% WR all SL; clean_pct=100% (pure alpha failure, no bugs)
- **Execution**: 2 sl_overshoot (tick-gap 1-tick gap artifact); trailing never activated
- **Priority**: alpha
- **Seed → next**: S5 skipped; pivot to HFTBacktest


## 2026-04-18 15:49Z — crypto_1h_weekly_meanrev_btc [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return -6.46%, Sharpe -0.90, MDD -14.58%, RT 23
- **IC/ICIR/IR**: -0.0085 / +4.147 / +0.521
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -7.829447543806777, IR 1.7495750099664795
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 15:49Z — crypto_1h_weekly_meanrev_eth [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +8.19%, Sharpe +0.59, MDD -28.33%, RT 44
- **IC/ICIR/IR**: +0.0064 / +2.887 / -0.624
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.1975035246054055, IR 2.4358737809002595
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 15:49Z — crypto_1h_weekly_meanrev_sol [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -5.83%, Sharpe -0.01, MDD -30.77%, RT 63
- **IC/ICIR/IR**: +0.0051 / +3.941 / +0.243
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.674965079097049, IR 3.8873635282894647
- **Notes**: (none)


## 2026-04-18 15:50Z — crypto_1h_weekly_meanrev_btc [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return -6.46%, Sharpe -0.90, MDD -14.58%, RT 23
- **IC/ICIR/IR**: -0.0085 / +4.147 / +0.521
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -7.829447543806777, IR 1.7495750099664795
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 15:50Z — crypto_1h_weekly_meanrev_eth [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +8.19%, Sharpe +0.59, MDD -28.33%, RT 44
- **IC/ICIR/IR**: +0.0064 / +2.887 / -0.624
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.1975035246054055, IR 2.4358737809002595
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 15:50Z — crypto_1h_weekly_meanrev_sol [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -5.83%, Sharpe -0.01, MDD -30.77%, RT 63
- **IC/ICIR/IR**: +0.0051 / +3.941 / +0.243
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.674965079097049, IR 3.8873635282894647
- **Notes**: (none)


## 2026-04-18 18:41Z — crypto_1h_btc_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return +4.30%, Sharpe +1.32, MDD -3.24%, RT 10
- **IC/ICIR/IR**: +0.0184 / +6.871 / +1.039
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 3.4507127341798283, IR 3.0329472636699073
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 18:41Z — crypto_1h_eth_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +5.59%, Sharpe +2.02, MDD -1.23%, RT 4
- **IC/ICIR/IR**: +0.0194 / +0.000 / -0.691
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 4.443008463409925, IR 2.2982107012765702
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:41Z — crypto_1h_sol_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -2.73%, Sharpe -1.01, MDD -4.19%, RT 2
- **IC/ICIR/IR**: -0.0095 / +0.000 / +0.125
- **4-Gate**: FAIL  (1_invariants, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 0.0, IR 2.7565734467843885
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry


## 2026-04-18 18:41Z — crypto_1h_weekly_meanrev_btc [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return -6.46%, Sharpe -0.90, MDD -14.58%, RT 23
- **IC/ICIR/IR**: -0.0085 / +4.147 / +0.521
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -7.829447543806777, IR 1.7495750099664795
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 18:41Z — crypto_1h_weekly_meanrev_eth [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +8.19%, Sharpe +0.59, MDD -28.33%, RT 44
- **IC/ICIR/IR**: +0.0064 / +2.887 / -0.624
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.1975035246054055, IR 2.4358737809002595
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:41Z — crypto_1h_weekly_meanrev_sol [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -5.83%, Sharpe -0.01, MDD -30.77%, RT 63
- **IC/ICIR/IR**: +0.0051 / +3.941 / +0.243
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.674965079097049, IR 3.8873635282894647
- **Notes**: (none)


## 2026-04-18 18:41Z — crypto_1h_zscore_trend_btc [programmatic feedback]
- **Spec**: trend_follow on BTCUSDT 1h
- **Backtest**: return -13.14%, Sharpe -1.52, MDD -22.01%, RT 70
- **IC/ICIR/IR**: -0.0032 / -5.491 / +0.140
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe)
- **OOS**: ret -18.857792325354684, IR -0.10238098094127715
- **Notes**: (none)


## 2026-04-18 18:41Z — crypto_1h_zscore_trend_eth [programmatic feedback]
- **Spec**: trend_follow on ETHUSDT 1h
- **Backtest**: return +35.98%, Sharpe +2.11, MDD -18.19%, RT 51
- **IC/ICIR/IR**: +0.0230 / -3.323 / +0.177
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -9.77001387263633, IR 1.1054700114478009
- **Notes**: (none)


## 2026-04-18 18:41Z — crypto_1h_zscore_trend_sol [programmatic feedback]
- **Spec**: trend_follow on SOLUSDT 1h
- **Backtest**: return +0.25%, Sharpe +0.19, MDD -25.26%, RT 72
- **IC/ICIR/IR**: +0.0082 / -4.041 / +0.325
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -17.779926261951363, IR 1.3156340993166153
- **Notes**: (none)


## 2026-04-18 18:43Z — crypto_1h_btc_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return +4.30%, Sharpe +1.32, MDD -3.24%, RT 10
- **IC/ICIR/IR**: +0.0184 / +6.871 / +1.039
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 3.4507127341798283, IR 3.0329472636699073
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 18:43Z — crypto_1h_eth_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +5.59%, Sharpe +2.02, MDD -1.23%, RT 4
- **IC/ICIR/IR**: +0.0194 / +0.000 / -0.691
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 4.443008463409925, IR 2.2982107012765702
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:43Z — crypto_1h_sol_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -2.73%, Sharpe -1.01, MDD -4.19%, RT 2
- **IC/ICIR/IR**: -0.0095 / +0.000 / +0.125
- **4-Gate**: FAIL  (1_invariants, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 0.0, IR 2.7565734467843885
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry


## 2026-04-18 18:43Z — crypto_1h_taker_flow_btc [programmatic feedback]
- **Spec**: order_flow on BTCUSDT 1h
- **Backtest**: return -17.78%, Sharpe -1.60, MDD -26.89%, RT 288
- **IC/ICIR/IR**: +0.0182 / +1.259 / -0.156
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -14.915577534041491, IR 0.684664848100484
- **Notes**: (none)


## 2026-04-18 18:43Z — crypto_1h_taker_flow_eth [programmatic feedback]
- **Spec**: order_flow on ETHUSDT 1h
- **Backtest**: return +7.09%, Sharpe +0.58, MDD -26.58%, RT 265
- **IC/ICIR/IR**: +0.0207 / +2.314 / -0.654
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 2.4587010135266096, IR 2.587834520336305
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:43Z — crypto_1h_taker_flow_sol [programmatic feedback]
- **Spec**: order_flow on SOLUSDT 1h
- **Backtest**: return -5.82%, Sharpe -0.09, MDD -29.75%, RT 271
- **IC/ICIR/IR**: +0.0170 / +1.351 / +0.174
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -5.3388775669956035, IR 3.1288201457443403
- **Notes**: (none)


## 2026-04-18 18:43Z — crypto_1h_weekly_meanrev_btc [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return -6.46%, Sharpe -0.90, MDD -14.58%, RT 23
- **IC/ICIR/IR**: -0.0085 / +4.147 / +0.521
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -7.829447543806777, IR 1.7495750099664795
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 18:43Z — crypto_1h_weekly_meanrev_eth [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +8.19%, Sharpe +0.59, MDD -28.33%, RT 44
- **IC/ICIR/IR**: +0.0064 / +2.887 / -0.624
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.1975035246054055, IR 2.4358737809002595
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:43Z — crypto_1h_weekly_meanrev_sol [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -5.83%, Sharpe -0.01, MDD -30.77%, RT 63
- **IC/ICIR/IR**: +0.0051 / +3.941 / +0.243
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.674965079097049, IR 3.8873635282894647
- **Notes**: (none)


## 2026-04-18 18:43Z — crypto_1h_zscore_trend_btc [programmatic feedback]
- **Spec**: trend_follow on BTCUSDT 1h
- **Backtest**: return -13.14%, Sharpe -1.52, MDD -22.01%, RT 70
- **IC/ICIR/IR**: -0.0032 / -5.491 / +0.140
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe)
- **OOS**: ret -18.857792325354684, IR -0.10238098094127715
- **Notes**: (none)


## 2026-04-18 18:43Z — crypto_1h_zscore_trend_eth [programmatic feedback]
- **Spec**: trend_follow on ETHUSDT 1h
- **Backtest**: return +35.98%, Sharpe +2.11, MDD -18.19%, RT 51
- **IC/ICIR/IR**: +0.0230 / -3.323 / +0.177
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -9.77001387263633, IR 1.1054700114478009
- **Notes**: (none)


## 2026-04-18 18:43Z — crypto_1h_zscore_trend_sol [programmatic feedback]
- **Spec**: trend_follow on SOLUSDT 1h
- **Backtest**: return +0.25%, Sharpe +0.19, MDD -25.26%, RT 72
- **IC/ICIR/IR**: +0.0082 / -4.041 / +0.325
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -17.779926261951363, IR 1.3156340993166153
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_btc_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return +4.30%, Sharpe +1.32, MDD -3.24%, RT 10
- **IC/ICIR/IR**: +0.0184 / +6.871 / +1.039
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 3.4507127341798283, IR 3.0329472636699073
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 18:59Z — crypto_1h_eth_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +5.59%, Sharpe +2.02, MDD -1.23%, RT 4
- **IC/ICIR/IR**: +0.0194 / +0.000 / -0.691
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 4.443008463409925, IR 2.2982107012765702
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:59Z — crypto_1h_portfolio_basket_btc [programmatic feedback]
- **Spec**: portfolio on BTCUSDT 1h
- **Backtest**: return -24.12%, Sharpe -1.73, MDD -33.93%, RT 263
- **IC/ICIR/IR**: +0.0085 / +1.749 / -0.743
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -15.888593607946733, IR 0.8268843506340933
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:59Z — crypto_1h_portfolio_basket_eth [programmatic feedback]
- **Spec**: portfolio on ETHUSDT 1h
- **Backtest**: return +23.37%, Sharpe +1.12, MDD -37.36%, RT 214
- **IC/ICIR/IR**: +0.0229 / +3.407 / -0.067
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 3.258501982584261, IR 3.934473237829302
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_portfolio_basket_sol [programmatic feedback]
- **Spec**: portfolio on SOLUSDT 1h
- **Backtest**: return -9.19%, Sharpe -0.06, MDD -37.29%, RT 225
- **IC/ICIR/IR**: +0.0139 / +3.794 / +0.225
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -12.96958063444239, IR 3.521529337226478
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_range_filter_btc [programmatic feedback]
- **Spec**: volatility on BTCUSDT 1h
- **Backtest**: return -18.33%, Sharpe -1.19, MDD -33.91%, RT 57
- **IC/ICIR/IR**: -0.0052 / +0.001 / -0.176
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.5206785733902795, IR 3.187767631520538
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_range_filter_eth [programmatic feedback]
- **Spec**: volatility on ETHUSDT 1h
- **Backtest**: return +24.05%, Sharpe +1.13, MDD -34.93%, RT 55
- **IC/ICIR/IR**: +0.0130 / +2.005 / -0.029
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -9.326206478093479, IR 1.9867568603238683
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_range_filter_sol [programmatic feedback]
- **Spec**: volatility on SOLUSDT 1h
- **Backtest**: return -12.76%, Sharpe -0.19, MDD -38.41%, RT 46
- **IC/ICIR/IR**: +0.0016 / -0.033 / +0.080
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -12.599560045621505, IR 2.8717785120145765
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_sol_rsi_atr [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -2.73%, Sharpe -1.01, MDD -4.19%, RT 2
- **IC/ICIR/IR**: -0.0095 / +0.000 / +0.125
- **4-Gate**: FAIL  (1_invariants, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 0.0, IR 2.7565734467843885
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry


## 2026-04-18 18:59Z — crypto_1h_taker_flow_btc [programmatic feedback]
- **Spec**: order_flow on BTCUSDT 1h
- **Backtest**: return -17.78%, Sharpe -1.60, MDD -26.89%, RT 288
- **IC/ICIR/IR**: +0.0182 / +1.259 / -0.156
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -14.915577534041491, IR 0.684664848100484
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_taker_flow_eth [programmatic feedback]
- **Spec**: order_flow on ETHUSDT 1h
- **Backtest**: return +7.09%, Sharpe +0.58, MDD -26.58%, RT 265
- **IC/ICIR/IR**: +0.0207 / +2.314 / -0.654
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 2.4587010135266096, IR 2.587834520336305
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:59Z — crypto_1h_taker_flow_sol [programmatic feedback]
- **Spec**: order_flow on SOLUSDT 1h
- **Backtest**: return -5.82%, Sharpe -0.09, MDD -29.75%, RT 271
- **IC/ICIR/IR**: +0.0170 / +1.351 / +0.174
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -5.3388775669956035, IR 3.1288201457443403
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_trend_follow_on_zscore_btc [programmatic feedback]
- **Spec**: trend_follow on BTCUSDT 1h
- **Backtest**: return -13.14%, Sharpe -1.52, MDD -22.01%, RT 70
- **IC/ICIR/IR**: -0.0032 / -5.491 / +0.140
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe)
- **OOS**: ret -18.857792325354684, IR -0.10238098094127715
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_trend_follow_on_zscore_eth [programmatic feedback]
- **Spec**: trend_follow on ETHUSDT 1h
- **Backtest**: return +35.98%, Sharpe +2.11, MDD -18.19%, RT 51
- **IC/ICIR/IR**: +0.0230 / -3.323 / +0.177
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -9.77001387263633, IR 1.1054700114478009
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_trend_follow_on_zscore_sol [programmatic feedback]
- **Spec**: trend_follow on SOLUSDT 1h
- **Backtest**: return +0.25%, Sharpe +0.19, MDD -25.26%, RT 72
- **IC/ICIR/IR**: +0.0082 / -4.041 / +0.325
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -17.779926261951363, IR 1.3156340993166153
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_weekly_meanrev_btc [programmatic feedback]
- **Spec**: mean_reversion on BTCUSDT 1h
- **Backtest**: return -6.46%, Sharpe -0.90, MDD -14.58%, RT 23
- **IC/ICIR/IR**: -0.0085 / +4.147 / +0.521
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -7.829447543806777, IR 1.7495750099664795
- **Notes**: low exposure (<10%) — signal rarely fires; intentional sparse entry; strong positive IR vs buy-and-hold


## 2026-04-18 18:59Z — crypto_1h_weekly_meanrev_eth [programmatic feedback]
- **Spec**: mean_reversion on ETHUSDT 1h
- **Backtest**: return +8.19%, Sharpe +0.59, MDD -28.33%, RT 44
- **IC/ICIR/IR**: +0.0064 / +2.887 / -0.624
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.1975035246054055, IR 2.4358737809002595
- **Notes**: strongly negative IR — strategy materially underperforms BH


## 2026-04-18 18:59Z — crypto_1h_weekly_meanrev_sol [programmatic feedback]
- **Spec**: mean_reversion on SOLUSDT 1h
- **Backtest**: return -5.83%, Sharpe -0.01, MDD -30.77%, RT 63
- **IC/ICIR/IR**: +0.0051 / +3.941 / +0.243
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -4.674965079097049, IR 3.8873635282894647
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_zscore_trend_btc [programmatic feedback]
- **Spec**: trend_follow on BTCUSDT 1h
- **Backtest**: return -13.14%, Sharpe -1.52, MDD -22.01%, RT 70
- **IC/ICIR/IR**: -0.0032 / -5.491 / +0.140
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe)
- **OOS**: ret -18.857792325354684, IR -0.10238098094127715
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_zscore_trend_eth [programmatic feedback]
- **Spec**: trend_follow on ETHUSDT 1h
- **Backtest**: return +35.98%, Sharpe +2.11, MDD -18.19%, RT 51
- **IC/ICIR/IR**: +0.0230 / -3.323 / +0.177
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -9.77001387263633, IR 1.1054700114478009
- **Notes**: (none)


## 2026-04-18 18:59Z — crypto_1h_zscore_trend_sol [programmatic feedback]
- **Spec**: trend_follow on SOLUSDT 1h
- **Backtest**: return +0.25%, Sharpe +0.19, MDD -25.26%, RT 72
- **IC/ICIR/IR**: +0.0082 / -4.041 / +0.325
- **4-Gate**: FAIL  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh)
- **OOS**: ret -17.779926261951363, IR 1.3156340993166153
- **Notes**: (none)


## 2026-04-19 04:12Z — crypto_1h_btc_mean_rev_168h_iter1 [programmatic feedback]
- **Spec**: None on BTCUSDT 1h
- **Backtest**: return -7.07%, Sharpe -0.42, MDD -22.70%, RT 12
- **IC/ICIR/IR**: +0.0012 / +2.397 / +0.709
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -8.41489300247893, IR 2.3538765705694984
- **Notes**: strong positive IR vs buy-and-hold

## Iteration 1 — crypto_1h_btc_mean_rev_168h_iter1 [feedback-analyst]
- **Timestamp**: 2026-04-19T00:00:00Z
- **Result**: return -7.07%, WR 41.67%, 12 roundtrips, IS Sharpe -0.42
- **OOS**: ret -8.41%, IR +2.35 (BH -19.62%) — outperforms BH but negative absolute
- **Attribution**: clean_pct=N/A (no invariant violations, all returns are genuine signal)
- **Alpha**: weak — BTC raw mean_fwd -10 bps vs pooled +441 bps; regime dependency in Nov 2025 downtrend (4 of 7 losses clustered); hypothesis NOT supported
- **Execution**: poor — ALL 12 exits tagged exit_signal; PT/SL/trailing never fired; 5 trades exceeded SL threshold by 38-101 bps without being cut
- **Priority**: both — exit wiring bug + wrong symbol (BTC has no 168h mean-rev edge; ETH/SOL do)
- **Structural concern**: exit_signal condition in generate_signal() overrides PT/SL/time_stop; SL check is only in the signal=1 branch, not enforced before re-entry gate
- **Seed → next**: fix SL/PT exit loop wiring AND move to ETHUSDT where raw mean_fwd is +613 bps; add roc_24h >= 0 confirmation gate if BTC is retried

## Iteration 1 (crypto_lob) — lob_iter1_obi1_spread_capture [feedback-analyst]
- **Timestamp**: 2026-04-20T05:25:13Z
- **Result**: return +0.1017%, WR 26.0%, 1500 roundtrips, fee=0 bps (zero-fee construct)
- **Attribution**: clean_pct=N/A (attribute_pnl.py not run; 0 invariant_violations)
- **Alpha**: moderate for BTC+ETH only — BTC edge +0.267 bps (WR 37.0%), ETH edge +0.184 bps (WR 37.8%), SOL edge −0.962 bps (WR 3.0% — implementation bug: avg_entry_obi=−0.028 vs threshold 0.749589, all 500 SOL entries fired without OBI gate). Portfolio total_edge = −0.170 bps (SOL drag dominates). Hypothesis supported for BTC/ETH; untested/invalidated for SOL.
- **Execution**: suboptimal — time_stop-as-primary-exit architecture is correct (91.3%, BTC/ETH +0.147/+0.113 bps). Two defects: (1) no per-symbol spread gate (SOL spread 1.17 bps > PT 1.09 bps — structural entry loss independent of OBI); (2) at real 4 bps taker fee, fee_to_edge_ratio=94.7% — non-deployable with MARKET orders.
- **Priority**: both — fix SOL OBI threshold bypass in strategy.py AND add spread gate (reject if spread_bps >= profit_target_bps)
- **Key number**: BTC+ETH combined edge without SOL = +0.226 bps; fee_to_edge at 4 bps = 94.7% → maker-only execution required for viability
- **Lesson recorded**: lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment
- **Seed → iter 2**: (local) Fix strategy.py SOL OBI gate; add per-symbol spread gate (`if spread_bps >= profit_target_bps: skip`); enable track_mfe=true; rerun BTC/ETH/SOL with corrected implementation — expect BTC+ETH portfolio edge ~+0.226 bps at fee=0 and SOL exclusion via spread gate; (escape) pivot to passive LIMIT maker entry (post at bid, wait for fill within 2 ticks) to reduce entry cost from taker 4 bps to near-zero maker — at fee=0 maker, BTC+ETH edge is already viable; LOB depth data enables queue-position estimation

## Iteration 1 — lob_iter1_obi1_spread_capture [local]
- **Timestamp**: 2026-04-20T05:28:59+00:00
- **Result**: return +0.1000%, WR n/a%, 1500 roundtrips
- **Attribution**: clean_pct=98.9%, bug_pnl=+1093095484.00
- **Alpha**: SOL OBI threshold bypass + spread 1.17 bps > PT 1.09 bps; BTC/ETH +0.226 bps gross
- **Execution**: time_stop (91%) architecture correct; SL gap risk 10/11 overshoot; fee_to_edge 94.7% at 4bps taker = non-deployable
- **Priority**: both
- **Seed → next**: lob_iter2: fix SOL OBI gate in strategy.py + add per-symbol spread gate (reject if spread_bps >= profit_target_bps); enable track_mfe=true; rerun BTC/ETH/SOL

## Iteration 2 — lob_iter2_obi1_spread_gate [local]
- **Timestamp**: 2026-04-20T05:42:01+00:00
- **Result**: return +0.1000%, WR n/a%, 1000 roundtrips
- **Attribution**: clean_pct=98.9%, bug_pnl=+1149095485.00
- **Alpha**: spread_gate + OBI_strict fix: BTC +0.267/37.2%, ETH +0.184/37.8%, SOL excluded (1.17>1.09)
- **Execution**: time_stop 91% unchanged; 0 rejected.cash; 4-gate pass ✓✓✓✓; IR beats BH (-1.53%) by +1.63%
- **Priority**: alpha
- **Seed → next**: iter3+ maker execution (passive LIMIT_AT_BID/ASK) to make BTC+ETH +0.226 bps edge fee-viable; avg_capture_pct still NaN-heavy — enable track_mfe=true in engine or dense mid_series sampling for LOB


## 2026-04-20 05:47Z — lob_iter2_obi1_spread_gate [programmatic feedback]
- **Spec**: — on BTCUSDT,ETHUSDT,SOLUSDT crypto_lob
- **Backtest**: return +0.10%, Sharpe +2.11, MDD -0.00%, RT 1000
- **IC/ICIR/IR**: +0.0000 / +0.000 / +0.000
- **4-Gate**: PASS  (1_invariants, 2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret 0.0664, IR 1.0693796354824576
- **Notes**: (none)


## 2026-04-20 13:04Z — lob_run20260420_iter1_obi1_maker [programmatic feedback]
- **Spec**: — on BTCUSDT,ETHUSDT,SOLUSDT crypto_lob
- **Backtest**: return -0.01%, Sharpe -0.36, MDD -0.01%, RT 11
- **IC/ICIR/IR**: +0.0000 / +0.000 / +0.000
- **4-Gate**: FAIL  (2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -0.0114, IR 0.9765336113362487
- **Notes**: invariant violations: 4 (['max_position_exceeded'])

## Iteration 1 — lob_run20260420_iter1_obi1_maker [local]
- **Timestamp**: 2026-04-20T13:21:43+00:00
- **Result**: return -0.0100%, WR n/a%, 11 roundtrips
- **Attribution**: clean_pct=53.8%, bug_pnl=-2731000000.00
- **Alpha**: OBI gate NOT applied in LIMIT_AT_BID path — all 11 entries fired at NEGATIVE OBI (avg -0.455) instead of +0.75-0.94 threshold; brief IC=0.2514 untested
- **Execution**: max_position_exceeded ×4 (duplicate entries at same ts) — position check runs post-fill not pre-order; TTL=10 & bid_drop=1 likely too aggressive (only 26 fills / 11 RTs in 16h)
- **Priority**: both
- **Seed → next**: Fix strategy.py: (1) apply obi_threshold gate BEFORE LIMIT order post in maker path; (2) pre-order position-cap check; (3) increase entry_ttl_ticks 10→30 and cancel_on_bid_drop 1→3 to retain fill rate at passive bid


## 2026-04-20 13:36Z — lob_run20260420_iter2_obi1_maker_fixed [programmatic feedback]
- **Spec**: — on BTCUSDT,ETHUSDT,SOLUSDT crypto_lob
- **Backtest**: return -0.01%, Sharpe -0.36, MDD -0.01%, RT 11
- **IC/ICIR/IR**: +0.0000 / +0.000 / +0.000
- **4-Gate**: FAIL  (2_oos_sharpe, 3_ir_vs_bh, 4_cross_symbol)
- **OOS**: ret -0.0114, IR 0.9765336113362487
- **Notes**: invariant violations: 4 (['max_position_exceeded'])

## Iteration 2 — lob_run20260420_iter2_obi1_maker_fixed [local]
- **Timestamp**: 2026-04-20T13:37:39+00:00
- **Result**: return -0.0100%, WR n/a%, 11 roundtrips
- **Attribution**: clean_pct=53.8%, bug_pnl=-2731000000.00
- **Alpha**: TTL 10→30 + bid_drop 1→3 did NOT improve fill rate — still 11 RTs / 26 fills; true cause of low RT is queue-back LIMIT_AT_BID adverse selection (fills only when OBI reverses from bid-heavy to ask-heavy)
- **Execution**: max_position_exceeded ×4 persists at identical fill_indices — engine counts concurrent buy+exit pairs as pos=2; not a strategy bug, interpretation quirk; passive maker paradigm fundamentally breaks OBI bid-pressure signal
- **Priority**: alpha
- **Seed → next**: PIVOT iter 3: abandon LIMIT_AT_BID, use MARKET (taker 4bps) BUT with stricter OBI threshold (0.99 per-symbol instead of 0.92/0.94/0.75) + tighter spread gate + smaller size; goal: trade quality over quantity, verify if selective MARKET entries can survive 4bps fee
