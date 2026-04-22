# Prior Iterations Index

This file is populated automatically by the orchestrator at the end of each Chain 1 iteration.

---

## ⚠️ Block C expansion — new primitives available (2026-04-21)

As of iter_009 onward, **4 new primitives** are in the whitelist (see
`../../_shared/references/cheat_sheets/microstructure_advanced.md`):

- `trade_imbalance_signed` (stateful, Lee-Ready signed volume)
- `bid_depth_concentration`, `ask_depth_concentration` (stateless, shape)
- `obi_ex_bbo` (stateless, deep-book imbalance)

**Pre-validated findings from multi-day smoke (2 syms × 3 dates, not logged as regular iters)**:

| spec formula | direction | threshold | H | WR | exp bps | n | meaning |
|---|---|---|---|---|---|---|---|
| `ask_depth_concentration` | **long_if_neg** (contra) | 0.3 | 20 | 0.889 | +5.93 | 10,797 | ask wall = resistance → price drops |
| `zscore(trade_imbalance_signed, 300) + 3*obi_1` | long_if_pos | 1.5 | 20 | 0.878 | +6.10 | 57,825 | compound trade-flow × OBI |
| `obi_1 > 0.5 AND obi_ex_bbo > 0.2` | long_if_pos | 0.5 | 5 | 0.931 | +6.33 | 7,590 | BBO + deep-book consensus |
| `bid_depth_concentration` | long_if_pos | 0.3 | 20 | 0.826 | +5.01 | 1,386 | bid wall = support → price rises |
| `zscore(trade_imbalance_signed, 300)` | **long_if_neg** (contra) | 2.0 | 50 | 0.603 | +1.77 | 2,572 | trade-flow spike = exhaustion |
| `obi_ex_bbo` | **long_if_neg** (contra) | 0.3 | 20 | 0.545 | +0.43 | 66,623 | deep-book contra, weak but robust |

**Key lessons (hard-earned)**:
1. **Direction flips matter.** `obi_ex_bbo`, `ask_depth_concentration`, and `zscore(trade_imbalance_signed)` all measure as CONTRA-directional — high raw value predicts OPPOSITE mid move. Do NOT default to `long_if_pos` for these primitives.
2. **`ask_depth_concentration` is the strongest new single-feature signal** (WR 0.89, +5.93 bps) but contra direction is mandatory.
3. **Compounds win**: `zscore(trade_imbalance_signed, 300) + 3*obi_1` has WR 0.88 with 57K trades/6 pairs — high density AND good WR. Prioritize compound formulas mixing Block C + OBI.
4. **All prior specs (iter_000 to iter_008) plateaued at expectancy ≤ +6.65 bps**. Don't propose minor variations of obi_1. Target: break the +7 bps ceiling via new primitive combinations.

**Suggested axes for iter_009+**:
- Multi-primitive compounds: Block C × OBI × regime filter
- Triple-primitive formulas (e.g., `ask_depth_concentration * -1 + 2*obi_1 - 3*trade_imbalance_z`)
- `obi_ex_bbo` as REJECT FILTER when opposite sign to `obi_1`
- `bid/ask_depth_concentration` as regime gate (only enter when book is front-loaded)

---

## Entries

_(Empty — no iterations completed yet.)_

---

## Format (auto-populated)

```
### iter{NNN}_{slug}
- **Formula**: <formula>
- **Primitives**: [list]
- **Threshold / Horizon**: <threshold>, <horizon> ticks
- **WR**: <measured_wr>
- **Expectancy**: <measured_expectancy_bps> bps
- **Feedback tag**: <recommended_next_direction>
- **Notes**: <one-line rationale summary>
```

Entries are append-only.

### iteration 000 (2026-04-21T08:20:58.092014Z)


#### iter000_obi1_gt_05
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9374518224865103
- **Expectancy**: 5.846705022681945 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal demonstrates an exceptionally strong, almost suspiciously perfect, predictive power for the very next tick (W


#### iter000_ofi_proxy_zscore_gt_15
- **Formula**: `zscore(ofi_proxy, 300)`
- **Primitives**: ['ofi_proxy']
- **Threshold / Horizon**: 1.5, 1 ticks
- **WR**: 0.712298682284041
- **Expectancy**: 2.931162530183945 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec demonstrates a strong candidate edge with a 71.2% win rate over 1366 trades and positive expectancy of +2.93 bp


#### iter000_microprice_dev_gt_1
- **Formula**: `microprice_dev_bps`
- **Primitives**: ['microprice_dev_bps']
- **Threshold / Horizon**: 1.0, 1 ticks
- **WR**: 0.9115296803652968
- **Expectancy**: 5.590561987048583 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec shows an exceptionally strong candidate edge with a 91.2% Win Rate and positive expectancy of +5.59 bps. The ne

### iteration 001 (2026-04-21T08:26:48.340250Z)


#### iter001_obi1_gt_05_h5
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.5, 5 ticks
- **WR**: 0.927877278933419
- **Expectancy**: 6.344086375880789 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a remarkably strong and persistent edge, with WR=92.8% holding strong even at a 5-tick horizon. The ne


#### iter001_ofi_proxy_zscore_gt_20
- **Formula**: `zscore(ofi_proxy, 300)`
- **Primitives**: ['ofi_proxy']
- **Threshold / Horizon**: 2.0, 1 ticks
- **WR**: 0.7225806451612903
- **Expectancy**: 3.7513632376375794 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a candidate edge with WR=72.3% and expectancy=+3.75 bps over 155 trades. Tightening the threshold from


#### iter001_obi1_and_high_vol
- **Formula**: `obi_1 > 0.5 AND rolling_realized_vol(mid_px, 100) > 50`
- **Primitives**: ['obi_1', 'mid_px']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9400050415931435
- **Expectancy**: 5.851014110324435 bps
- **Feedback tag**: ensemble_vote
- **Notes**: This spec and its parent (`iter000_obi1_gt_05`) show near-perfect predictive power (WR > 93%) at the 1-tick horizon, but

### iteration 002 (2026-04-21T08:32:40.302053Z)


#### iter002_obi1_gt_075_h5
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.75, 5 ticks
- **WR**: 0.9500863557858377
- **Expectancy**: 6.563061525729028 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal has demonstrated an extraordinarily high WR of 95.0% at a 5-tick horizon. We have confirmed the signal's stre


#### iter002_ofi_proxy_zscore_gt_25
- **Formula**: `zscore(ofi_proxy, 300)`
- **Primitives**: ['ofi_proxy']
- **Threshold / Horizon**: 2.5, 1 ticks
- **WR**: 0.75
- **Expectancy**: 4.3892333811850985 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal's performance is highly inconsistent across symbols, with a 12.8 percentage point WR spread between 005930 (a


#### iter002_obi1_and_microprice_consensus
- **Formula**: `obi_1 > 0.5 AND microprice_dev_bps > 1.0`
- **Primitives**: ['obi_1', 'microprice_dev_bps']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9436201780415431
- **Expectancy**: 5.949386265732961 bps
- **Feedback tag**: add_regime_filter
- **Notes**: The spec has demonstrated an extremely high win rate (94.4%) over a large number of trades (4381). Instead of further ti

### iteration 003 (2026-04-21T08:36:22.538724Z)


#### iter003_obi1_gt_075_h20
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.75, 20 ticks
- **WR**: 0.917946493130875
- **Expectancy**: 6.532472079478203 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge with a 91.8% WR over 34,575 trades and a +6.53 bps expectancy. While perform


#### iter003_obi_micro_consensus_opening
- **Formula**: `(obi_1 > 0.5 and microprice_dev_bps > 1.0) and (minute_of_session < 15)`
- **Primitives**: ['obi_1', 'microprice_dev_bps', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9234875444839857
- **Expectancy**: 6.23485294997107 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a strong candidate edge with a WR of 92.3% and positive expectancy of +6.23 bps over 562 trades. The t

### iteration 004 (2026-04-21T08:38:53.760320Z)


#### iter004_obi1_gt_09_h20
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.9, 20 ticks
- **WR**: 0.9346015991177281
- **Expectancy**: 6.587462427642355 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal has demonstrated extraordinarily high predictive power, with WR improving to 93.5% after tightening the thres

### iteration 005 (2026-04-21T08:42:58.817045Z)


#### iter005_obi1_gt_09_h50
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.9, 50 ticks
- **WR**: 0.8869561368565485
- **Expectancy**: 6.330980088978469 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful edge with an 88.7% WR and +6.33 bps expectancy over 22,593 trades, even at a 50-tick horizo


#### iter005_obi_momentum_ensemble
- **Formula**: `obi_1 * (rolling_momentum(mid_px, 50) > 0)`
- **Primitives**: ['obi_1', 'mid_px']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.918546845124283
- **Expectancy**: 5.362728433331091 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge with a 91.9% win rate and +5.36 bps expectancy. The next logical step is to 

### iteration 006 (2026-04-21T08:48:42.623681Z)


#### iter006_obi1_gt_095_h50
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.95, 50 ticks
- **WR**: 0.8921771048405598
- **Expectancy**: 6.405072453092599 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge, with the win rate improving to 89.2% over 13,077 trades after tightening th


#### iter006_strong_obi_momentum_ensemble
- **Formula**: `obi_1 > 0.7 AND rolling_momentum(mid_px, 50) > 0`
- **Primitives**: ['obi_1', 'mid_px']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9497374343585896
- **Expectancy**: 5.8798471730172235 bps
- **Feedback tag**: ensemble_vote
- **Notes**: This spec confirms an exceptionally strong signal with a 95.0% WR over 1,333 trades. Having validated that tightening th


#### iter006_cks_ofi_zscore_opening_burst
- **Formula**: `zscore(ofi_cks_1, 300) > 2.0 AND minute_of_session < 15`
- **Primitives**: ['ofi_cks_1', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.6
- **Expectancy**: 1.1963962961251582 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal's performance is highly inconsistent across the universe, with the win rate for 005930 (67.6%) being 13.9 per

### iteration 007 (2026-04-21T08:53:28.508607Z)


#### iter007_obi1_gt_098_h50
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.98, 50 ticks
- **WR**: 0.8971892379377724
- **Expectancy**: 6.5950062909602005 bps
- **Feedback tag**: tighten_threshold
- **Notes**: This spec confirms a powerful candidate edge, improving both Win Rate to 89.7% and expectancy to +6.60 bps over 6,653 tr


#### iter007_obi_micro_momentum_trifecta
- **Formula**: `obi_1 > 0.7 AND microprice_dev_bps > 1.0 AND rolling_momentum(mid_px, 50) > 0`
- **Primitives**: ['obi_1', 'microprice_dev_bps', 'mid_px']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9497374343585896
- **Expectancy**: 5.8798471730172235 bps
- **Feedback tag**: add_filter
- **Notes**: The spec confirms an exceptionally strong edge with a 95.0% WR over 1,333 trades. However, the latest mutation proved re


#### iter007_deep_book_pressure
- **Formula**: `obi_10`
- **Primitives**: ['obi_10']
- **Threshold / Horizon**: 0.4, 1 ticks
- **WR**: 0.5187120463211411
- **Expectancy**: 0.31457354547070376 bps
- **Feedback tag**: swap_feature
- **Notes**: The aggregate Win Rate of 51.9% over a large sample of 7,081 trades is statistically indistinguishable from a random wal

### iteration 008 (2026-04-21T08:57:00.092771Z)


#### iter008_obi1_gt_099_h50
- **Formula**: `obi_1`
- **Primitives**: ['obi_1']
- **Threshold / Horizon**: 0.99, 50 ticks
- **WR**: 0.8987629386518556
- **Expectancy**: 6.646682832620407 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec has an exceptionally high WR of 89.9% and expectancy of +6.65 bps, confirming a powerful signal. However, the l


#### iter008_trifecta_plus_spread_filter
- **Formula**: `obi_1 > 0.7 AND rolling_momentum(mid_px, 50) > 0 AND spread_bps < 15`
- **Primitives**: ['obi_1', 'mid_px', 'spread_bps']
- **Threshold / Horizon**: 0.5, 1 ticks
- **WR**: 0.9589147286821705
- **Expectancy**: 6.015282031389333 bps
- **Feedback tag**: combine_with_other_spec
- **Notes**: This spec has an outstanding WR of 95.9% and expectancy of +6.02 bps over 1,290 trades, confirming its status as a top-t

### iteration 000 (2026-04-21T09:49:04.468929Z)


#### iter000_ask_concentration_contra_h20
- **Formula**: `ask_depth_concentration`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 0.3, 20 ticks
- **WR**: 0.889043252755395
- **Expectancy**: 5.932037973426586 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec demonstrates a powerful candidate edge with a WR of 88.9% over nearly 11,000 trades and a positive expectancy o


#### iter000_obi_deepbook_consensus_h5
- **Formula**: `obi_1 > 0.5 AND obi_ex_bbo > 0.2`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 5 ticks
- **WR**: 0.9312252964426877
- **Expectancy**: 6.331897974005917 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec has demonstrated an outstanding candidate edge with a WR of 93.1% and expectancy of +6.33 bps over 7,590 trades


#### iter000_deepbook_reversal_h20
- **Formula**: `obi_1 > 0.5 AND obi_ex_bbo < -0.3`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.09719758779709117
- **Expectancy**: -6.1346627989004165 bps
- **Feedback tag**: change_horizon
- **Notes**: The core hypothesis is invalidated by the 9.7% WR. While flipping the direction seems obvious, the horizon curve shows W

### iteration 001 (2026-04-21T09:55:21.762622Z)


#### iter001_ask_concentration_contra_t04_h20
- **Formula**: `ask_depth_concentration`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 0.4, 20 ticks
- **WR**: 0.9358690844758957
- **Expectancy**: 6.462403690204962 bps
- **Feedback tag**: extreme_quantile
- **Notes**: The spec has an exceptionally high Win Rate of 93.6% and expectancy of +6.46 bps, confirming its power. Since simple thr


#### iter001_obi_deepbook_consensus_tight_h5
- **Formula**: `obi_1 > 0.7 AND obi_ex_bbo > 0.3`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 5 ticks
- **WR**: 0.9496168582375479
- **Expectancy**: 6.604541488968199 bps
- **Feedback tag**: add_filter
- **Notes**: With an exceptional WR of 95.0% over 5,220 trades after tightening, the signal is already in a high-conviction state. Fu


#### iter001_tradeflow_plus_obi_h20
- **Formula**: `zscore(trade_imbalance_signed, 300) + 3 * obi_1`
- **Primitives**: ['trade_imbalance_signed', 'obi_1']
- **Threshold / Horizon**: 2.0, 20 ticks
- **WR**: 0.8936510512041909
- **Expectancy**: 6.2370010891693815 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge with a WR of 89.4% and expectancy of +6.24 bps over more than 43,000 trades.

### iteration 002 (2026-04-21T10:03:47.114085Z)


#### iter002_ask_concentration_zscore_contra_h20
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 2.5, 20 ticks
- **WR**: 0.9054790131368151
- **Expectancy**: 6.688229382682702 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge with a 90.5% Win Rate and +6.69 bps expectancy over 6,242 trades. Despite a 


#### iter002_obi_deepbook_consensus_filtered_h5
- **Formula**: `(obi_1 > 0.7 AND obi_ex_bbo > 0.3) AND (spread_bps < 10)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'spread_bps']
- **Threshold / Horizon**: 0.5, 5 ticks
- **WR**: 0.9559854219231847
- **Expectancy**: 5.384850285498004 bps
- **Feedback tag**: drop_feature
- **Notes**: The addition of the `spread_bps < 10` filter rendered the signal highly inconsistent across symbols, virtually eliminati


#### iter002_tradeflow_plus_obi_tight_h20
- **Formula**: `zscore(trade_imbalance_signed, 300) + 3 * obi_1`
- **Primitives**: ['trade_imbalance_signed', 'obi_1']
- **Threshold / Horizon**: 3.0, 20 ticks
- **WR**: 0.7576564580559254
- **Expectancy**: 3.716799859629266 bps
- **Feedback tag**: tighten_threshold
- **Notes**: While the previous tightening step from 2.0 to 3.0 degraded performance, the signal remains strong with a 75.8% WR. The 


#### iter002_full_consensus_contra_ask_h10
- **Formula**: `(obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration']
- **Threshold / Horizon**: 1.2, 10 ticks
- **WR**: 0.9280773463291935
- **Expectancy**: 6.723586608646473 bps
- **Feedback tag**: tighten_threshold
- **Notes**: With an exceptional aggregate WR of 92.8% over 12,722 trades and a +6.72 bps expectancy, this spec represents a powerful

### iteration 003 (2026-04-21T10:12:16.130718Z)


#### iter003_full_consensus_tight
- **Formula**: `(obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration']
- **Threshold / Horizon**: 1.5, 10 ticks
- **WR**: 0.9556974269684658
- **Expectancy**: 7.005526294874833 bps
- **Feedback tag**: add_regime_filter
- **Notes**: The spec has achieved an outstanding WR of 95.6% and a new peak expectancy of +7.01 bps. Having successfully tightened t


#### iter003_ask_conc_zscore_contra_tight
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 3.0, 20 ticks
- **WR**: 0.9111236909142372
- **Expectancy**: 6.906772662968384 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge, successfully improving both Win Rate (to 91.1%) and expectancy (to +6.91 bp


#### iter003_book_consensus_tradeflow_confirm
- **Formula**: `(obi_1 > 0.7 AND obi_ex_bbo > 0.3) AND (zscore(trade_imbalance_signed, 300) > 1.5)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 5 ticks
- **WR**: 0.7017543859649122
- **Expectancy**: 3.205592012990807 bps
- **Feedback tag**: drop_feature
- **Notes**: The spec's performance is highly inconsistent, with per-session Win Rates varying from 50.0% to 100.0%. The addition of 


#### iter003_tradeflow_momentum_combo_h20
- **Formula**: `zscore(trade_imbalance_signed, 300) > 2.0 AND rolling_momentum(mid_px, 100) > 0`
- **Primitives**: ['trade_imbalance_signed', 'mid_px']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.35384615384615387
- **Expectancy**: -2.503269036557488 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis was completely invalidated, yielding a WR of 35.4% and expectancy of -2.50 bps. While this perform

### iteration 004 (2026-04-21T10:19:56.021151Z)


#### iter004_full_consensus_high_vol
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND rolling_realized_vol(mid_px, 100) > 40`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'mid_px']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.9614440939362076
- **Expectancy**: 6.86405560407269 bps
- **Feedback tag**: extreme_quantile
- **Notes**: With an exceptional WR of 96.1% over 2,853 trades, the signal is already in a high-conviction state. The parent spec suc


#### iter004_ask_conc_zscore_extreme
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 3.5, 20 ticks
- **WR**: 0.9090069284064665
- **Expectancy**: 6.921753989153347 bps
- **Feedback tag**: tighten_threshold
- **Notes**: This spec confirms a powerful candidate edge with a WR of 90.9% and expectancy of +6.92 bps over 2,165 trades. Although 


#### iter004_bbo_reversal_on_tradeflow
- **Formula**: `obi_1 > 0.7 AND zscore(trade_imbalance_signed, 300) < -1.5`
- **Primitives**: ['obi_1', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.17960088691796008
- **Expectancy**: -4.922030980712066 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis was completely invalidated, with a WR of 18.0% over 451 trades. Before retiring the spec or invert


#### iter004_deep_book_reversal
- **Formula**: `obi_1 > 0.5 AND obi_ex_bbo < -0.3`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.09719758779709117
- **Expectancy**: -6.1346627989004165 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis is conclusively invalidated at the 20-tick horizon with a 9.7% Win Rate and -6.13 bps expectancy. 

### iteration 005 (2026-04-21T10:26:05.061955Z)


#### iter005_ask_conc_zscore_ultra
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 4.0, 20 ticks
- **WR**: 0.918201915991157
- **Expectancy**: 7.414707154000218 bps
- **Feedback tag**: tighten_threshold
- **Notes**: This spec confirms a powerful and consistent edge, improving both Win Rate to 91.8% and expectancy to +7.41 bps. The suc


#### iter005_bid_wall_absorption
- **Formula**: `obi_1 > 0.7 AND zscore(trade_imbalance_signed, 300) < -1.5`
- **Primitives**: ['obi_1', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.8369565217391305
- **Expectancy**: 5.069597871709422 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge with a WR of 83.7% and expectancy of +5.07 bps over 368 trades. The logical 


#### iter005_full_consensus_bid_shape
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND bid_depth_concentration < 0.2`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'bid_depth_concentration']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.9622314622314623
- **Expectancy**: 6.799421455883966 bps
- **Feedback tag**: combine_with_other_spec
- **Notes**: This spec confirmed its status as a top-tier signal with an outstanding WR of 96.2% and high expectancy of +6.80 bps. Wh

### iteration 006 (2026-04-22T01:10:02.449233Z)


#### iter006_ask_conc_zscore_pinnacle
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 4.5, 20 ticks
- **WR**: 0.9053191489361702
- **Expectancy**: 7.427487613406702 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful edge with a 90.5% Win Rate and a new peak expectancy of +7.43 bps. Despite signs of diminis


#### iter006_bid_wall_absorption_tight
- **Formula**: `obi_1 > 0.8 AND zscore(trade_imbalance_signed, 300) < -2.0`
- **Primitives**: ['obi_1', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.8780487804878049
- **Expectancy**: 5.6129332198289426 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The previous mutation successfully increased WR from 83.7% to 87.8% and expectancy from +5.07 bps to +5.61 bps. This con


#### iter006_deep_book_vs_bbo_divergence
- **Formula**: `obi_1 > 0.7 AND obi_ex_bbo < -0.3`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.05329153605015674
- **Expectancy**: -6.781742625451597 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis is conclusively invalidated with a 5.3% Win Rate over 1276 trades. The horizon curve shows WR impr


#### iter006_full_consensus_trade_confirm
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND zscore(trade_imbalance_signed, 300) > 1.0`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6470588235294118
- **Expectancy**: 2.941206473936332 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The core problem is an insufficient sample size, with only 17 trades generated. This is statistically underpowered. To p

### iteration 007 (2026-04-22T01:17:07.415774Z)


#### iter007_ask_conc_zscore_ultra
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 5.0, 20 ticks
- **WR**: 0.9028400597907325
- **Expectancy**: 7.595827752154444 bps
- **Feedback tag**: tighten_threshold
- **Notes**: This spec confirms a powerful edge, improving expectancy to a new peak of +7.60 bps with a 90.3% WR over 669 trades. The


#### iter007_bid_wall_absorption_extreme
- **Formula**: `obi_1 > 0.9 AND zscore(trade_imbalance_signed, 300) < -2.5`
- **Primitives**: ['obi_1', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.8702290076335878
- **Expectancy**: 5.615258554714463 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The parent spec's feedback correctly identified a trend where tightening thresholds improved performance. This mutation 


#### iter007_consensus_loosened_trade_confirm
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND zscore(trade_imbalance_signed, 300) > 0.5`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6296296296296297
- **Expectancy**: 2.640287085051846 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The core issue remains an insufficient sample size. Despite improving from 17 to 27 trades, this is still far too low fo


#### iter007_inverted_book_divergence
- **Formula**: `obi_1 > 0.7 AND obi_ex_bbo < -0.3`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.05329153605015674
- **Expectancy**: -6.781742625451597 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis is conclusively invalidated, with a 5.3% Win Rate over 1,276 trades. The horizon curve in the back

### iteration 008 (2026-04-22T01:23:01.419471Z)


#### iter008_ask_conc_final_push
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 5.5, 20 ticks
- **WR**: 0.8955823293172691
- **Expectancy**: 7.520299310413194 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The parent spec's feedback trend suggested one final tightening to confirm the signal's absolute conviction limit. While


#### iter008_absorption_pinnacle
- **Formula**: `obi_1 > 0.95 AND zscore(trade_imbalance_signed, 300) < -3.0`
- **Primitives**: ['obi_1', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.8947368421052632
- **Expectancy**: 5.997980567673354 bps
- **Feedback tag**: add_filter
- **Notes**: The spec has a high WR of 89.5% but a low trade count of 57, suggesting it identifies rare, high-conviction events. Whil


#### iter008_consensus_wide_trade_confirm
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND zscore(trade_imbalance_signed, 300) > 0.1`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.9622054246331703
- **Expectancy**: 6.831464167845798 bps
- **Feedback tag**: timevarying_threshold
- **Notes**: With an exceptional WR of 96.2% over 2,249 trades, simple threshold tightening offers diminishing returns. The observed 

### iteration 009 (2026-04-22T01:29:28.347152Z)


#### iter009_ask_conc_final_pinnacle
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 6.0, 20 ticks
- **WR**: 0.889763779527559
- **Expectancy**: 7.418882325852945 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The parent spec's feedback trend suggested one final tightening to confirm the signal's absolute conviction limit. While


#### iter009_absorption_high_vol
- **Formula**: `(obi_1 > 0.95 AND zscore(trade_imbalance_signed, 300) < -3.0) AND (rolling_realized_vol(mid_px, 100) > 40)`
- **Primitives**: ['obi_1', 'trade_imbalance_signed', 'mid_px']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.8947368421052632
- **Expectancy**: 5.997980567673354 bps
- **Feedback tag**: add_filter
- **Notes**: The spec has a high WR of 89.5% but the low trade count of 57 remains a statistical concern. The previous attempt to add


#### iter009_consensus_opening_burst
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND zscore(trade_imbalance_signed, 300) > 0.1 AND minute_of_session < 15`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'trade_imbalance_signed', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.7528089887640449
- **Expectancy**: 4.247610218354809 bps
- **Feedback tag**: drop_feature
- **Notes**: The addition of the `minute_of_session < 15` filter proved detrimental, introducing extreme performance instability as s

### iteration 010 (2026-04-22T01:37:17.532500Z)


#### iter010_ask_conc_extreme_push
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 7.5, 20 ticks
- **WR**: 0.8604651162790697
- **Expectancy**: 7.168413693915003 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The parent spec's feedback trend suggested one final tightening to confirm the signal's absolute conviction limit. This 


#### iter010_absorption_spread_filter
- **Formula**: `(obi_1 > 0.95 AND zscore(trade_imbalance_signed, 300) < -3.0) AND (spread_bps < 5)`
- **Primitives**: ['obi_1', 'trade_imbalance_signed', 'spread_bps']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is critically under-powered, generating exactly 0 trades. The core issue is that the entry conditions are too s


#### iter010_consensus_plus_bid_shape
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND zscore(trade_imbalance_signed, 300) > 0.1 AND bid_depth_concentration < 0.2`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'trade_imbalance_signed', 'bid_depth_concentration']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.9594594594594594
- **Expectancy**: 6.771604263147173 bps
- **Feedback tag**: add_regime_filter
- **Notes**: The spec has an outstanding aggregate WR of 95.9% and expectancy of +6.77 bps, confirming it as a top-tier signal. The p


#### iter010_tradeflow_exhaustion_into_wall
- **Formula**: `zscore(trade_imbalance_signed, 300) > 2.5 AND ask_depth_concentration > 0.4`
- **Primitives**: ['trade_imbalance_signed', 'ask_depth_concentration']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.8918918918918919
- **Expectancy**: 6.089346992294707 bps
- **Feedback tag**: drop_feature
- **Notes**: The spec's performance is highly inconsistent, particularly on symbol 000660 where the per-session Win Rate varied from 

### iteration 011 (2026-04-22T01:44:22.966765Z)


#### iter011_ask_conc_final_frontier
- **Formula**: `zscore(ask_depth_concentration, 300)`
- **Primitives**: ['ask_depth_concentration']
- **Threshold / Horizon**: 9.0, 20 ticks
- **WR**: 0.7931034482758621
- **Expectancy**: 6.161234937416383 bps
- **Feedback tag**: add_filter
- **Notes**: This spec confirms the performance peak for this signal family has been passed via simple thresholding, with WR degradin


#### iter011_consensus_opening_gate
- **Formula**: `((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND minute_of_session > 15`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'minute_of_session']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.972972972972973
- **Expectancy**: 6.814142571444106 bps
- **Feedback tag**: combine_with_other_spec
- **Notes**: This spec has achieved an elite WR of 97.3% and expectancy of +6.81 bps over 2,886 trades. Further threshold tightening 


#### iter011_tradeflow_plus_shape
- **Formula**: `zscore(trade_imbalance_signed, 300) > 2.0 AND ask_depth_concentration > 0.3`
- **Primitives**: ['trade_imbalance_signed', 'ask_depth_concentration']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.8823529411764706
- **Expectancy**: 5.80792913128961 bps
- **Feedback tag**: add_filter
- **Notes**: The spec shows high potential with an 88.2% Win Rate, but this is based on a borderline sample size of 85 trades. The ob

### iteration 012 (2026-04-22T01:51:29.195013Z)


#### iter012_ask_conc_low_vol
- **Formula**: `zscore(ask_depth_concentration, 300) * (rolling_realized_vol(mid_px, 100) < 30)`
- **Primitives**: ['ask_depth_concentration', 'mid_px']
- **Threshold / Horizon**: 5.0, 20 ticks
- **WR**: 1.0
- **Expectancy**: 9.936716288610905 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec has achieved a perfect 100% Win Rate over 260 trades, suggesting performance at the 20-tick horizon is maximize


#### iter012_mega_consensus
- **Formula**: `(((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.5 AND minute_of_session > 15) AND (zscore(trade_imbalance_signed, 300) > 2.0 AND ask_depth_concentration > 0.3)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'minute_of_session', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is critically underpowered, generating zero trades, which provides no information. The combined entry condition


#### iter012_deep_book_vs_bbo_reversal
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 1.0, 20 ticks
- **WR**: 0.09036870119274253
- **Expectancy**: -6.254305945466297 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis is conclusively invalidated with a 9.0% Win Rate and -6.25 bps expectancy over 25,739 trades. The 

### iteration 013 (2026-04-22T02:00:43.706573Z)


#### iter013_ask_conc_low_vol_h50
- **Formula**: `zscore(ask_depth_concentration, 300) * (rolling_realized_vol(mid_px, 100) < 30)`
- **Primitives**: ['ask_depth_concentration', 'mid_px']
- **Threshold / Horizon**: 5.0, 50 ticks
- **WR**: 0.9629629629629629
- **Expectancy**: 9.834049235754549 bps
- **Feedback tag**: timevarying_threshold
- **Notes**: With an outstanding WR of 96.3% and a high fixed threshold of 5.0, simple tightening offers diminishing returns. The sig


#### iter013_mega_consensus_loosened
- **Formula**: `(((obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration) > 1.2) AND (zscore(trade_imbalance_signed, 300) > 1.5)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'ask_depth_concentration', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6842105263157895
- **Expectancy**: 3.359555044206955 bps
- **Feedback tag**: drop_feature
- **Notes**: The spec's performance is highly inconsistent, with per-session Win Rates varying drastically from 100% to 50.0%. This s


#### iter013_book_divergence_inverted
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 1.0, 20 ticks
- **WR**: 0.09036870119274253
- **Expectancy**: -6.254305945466297 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis was conclusively invalidated, yielding an aggregate WR of 9.0% and expectancy of -6.25 bps over 25


#### iter013_tradeflow_into_favorable_shape
- **Formula**: `zscore(trade_imbalance_signed, 300) > 1.5 AND bid_depth_concentration < 0.2 AND ask_depth_concentration < 0.2`
- **Primitives**: ['trade_imbalance_signed', 'bid_depth_concentration', 'ask_depth_concentration']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.3850782190132371
- **Expectancy**: -1.8472263145365426 bps
- **Feedback tag**: change_horizon
- **Notes**: The signal's hypothesis is conclusively invalidated with a 38.5% Win Rate and -1.85 bps expectancy over 831 trades. The 

### iteration 014 (2026-04-22T02:09:19.479799Z)


#### iter014_wall_break_filter
- **Formula**: `(zscore(ask_depth_concentration, 300) * (rolling_realized_vol(mid_px, 100) < 30)) * (zscore(trade_imbalance_signed, 300) < 1.0)`
- **Primitives**: ['ask_depth_concentration', 'mid_px', 'trade_imbalance_signed']
- **Threshold / Horizon**: 5.0, 50 ticks
- **WR**: 0.9629629629629629
- **Expectancy**: 9.834049235754549 bps
- **Feedback tag**: add_regime_filter
- **Notes**: The spec has an outstanding WR of 96.3% over 324 trades with a high threshold of 5.0, making further tightening ineffect


#### iter014_book_shape_reversal
- **Formula**: `bid_depth_concentration - 2 * zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['bid_depth_concentration', 'trade_imbalance_signed']
- **Threshold / Horizon**: 3.0, 20 ticks
- **WR**: 0.38235294117647056
- **Expectancy**: -1.8843612742238076 bps
- **Feedback tag**: change_horizon
- **Notes**: The spec's hypothesis is conclusively invalidated with a 38.2% Win Rate and -1.88 bps expectancy. The horizon curve show


#### iter014_book_divergence_short_horizon
- **Formula**: `obi_1 - obi_ex_bbo`
- **Primitives**: ['obi_1', 'obi_ex_bbo']
- **Threshold / Horizon**: 1.2, 1 ticks
- **WR**: 0.9485657764589516
- **Expectancy**: 5.813731630213879 bps
- **Feedback tag**: add_regime_filter
- **Notes**: The spec demonstrates an exceptionally strong and consistent edge with a 94.9% Win Rate over 3,033 trades. Since the sig

### iteration 015 (2026-04-22T02:15:27.426982Z)


#### iter015_trade_flow_exhaustion_short
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 2.5, 20 ticks
- **WR**: 0.5978082191780822
- **Expectancy**: 1.5455317576839602 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec has established a candidate edge with a 59.8% Win Rate over 1,825 trades and positive expectancy of +1.55 bps. 


#### iter015_deep_book_vs_tradeflow_divergence
- **Formula**: `obi_ex_bbo > 0.3 AND zscore(trade_imbalance_signed, 300) < -2.0`
- **Primitives**: ['obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6290672451193059
- **Expectancy**: 2.1095181250754402 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec demonstrates a promising candidate edge with a 62.9% WR over 461 trades and positive expectancy of +2.11 bps. T

### iteration 016 (2026-04-22T02:21:20.123780Z)


#### iter016_trade_flow_exhaustion_tight
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 3.0, 20 ticks
- **WR**: 0.5955124317768344
- **Expectancy**: 1.5161527944293984 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a candidate edge with a WR of 59.6% over 1,649 trades and positive expectancy of +1.52 bps. Although t


#### iter016_deep_book_absorption_tight
- **Formula**: `obi_ex_bbo > 0.4 AND zscore(trade_imbalance_signed, 300) < -2.5`
- **Primitives**: ['obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6443148688046647
- **Expectancy**: 2.2388818288988075 bps
- **Feedback tag**: tighten_threshold
- **Notes**: This tightening step successfully improved the aggregate WR from 62.9% to 64.4% and expectancy from +2.11 bps to +2.24 b

### iteration 017 (2026-04-22T02:31:06.609345Z)


#### iter017_exhaustion_extreme
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 3.5, 20 ticks
- **WR**: 0.5937912813738441
- **Expectancy**: 1.4584431412720023 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a candidate edge with a WR of 59.4% and +1.46 bps expectancy over 1,514 trades. Although this tighteni


#### iter017_deep_book_absorption_extreme
- **Formula**: `obi_ex_bbo > 0.5 AND zscore(trade_imbalance_signed, 300) < -3.0`
- **Primitives**: ['obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6436363636363637
- **Expectancy**: 2.27849981021913 bps
- **Feedback tag**: drop_feature
- **Notes**: The signal's performance is fundamentally inconsistent across the universe, with the Win Rate swinging from 72.1% on one


#### iter017_bbo_divergence_trade_confirm
- **Formula**: `(obi_1 - obi_ex_bbo) * (zscore(trade_imbalance_signed, 300) > 1.0)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 1.2, 5 ticks
- **WR**: 0.8833333333333333
- **Expectancy**: 5.263463596673458 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec demonstrates a powerful candidate edge with a WR of 88.3% and expectancy of +5.26 bps over 240 trades. The next


#### iter017_fragile_ask_exhaustion
- **Formula**: `(zscore(trade_imbalance_signed, 300)) * (ask_depth_concentration > 0.3)`
- **Primitives**: ['trade_imbalance_signed', 'ask_depth_concentration']
- **Threshold / Horizon**: 3.0, 20 ticks
- **WR**: 0.6695652173913044
- **Expectancy**: 3.0666477032269817 bps
- **Feedback tag**: drop_feature
- **Notes**: The added feature, `ask_depth_concentration`, introduced extreme performance instability across sessions, with Win Rates

### iteration 018 (2026-04-22T02:39:57.069086Z)


#### iter018_exhaustion_pinnacle
- **Formula**: `zscore(trade_imbalance_signed, 300)`
- **Primitives**: ['trade_imbalance_signed']
- **Threshold / Horizon**: 4.0, 20 ticks
- **WR**: 0.5871757925072046
- **Expectancy**: 1.3906400990904528 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a candidate edge with a WR of 58.7% over 1,388 trades and expectancy of +1.39 bps. The parent spec's f


#### iter018_bbo_divergence_tight
- **Formula**: `(obi_1 - obi_ex_bbo) * (zscore(trade_imbalance_signed, 300) > 1.0)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 1.5, 5 ticks
- **WR**: 0.916030534351145
- **Expectancy**: 5.879438728355102 bps
- **Feedback tag**: tighten_threshold
- **Notes**: This tightening was a successful mutation, improving both WR (88.3% to 91.6%) and expectancy (+5.26 to +5.88 bps). This 


#### iter018_stable_deep_book_absorption
- **Formula**: `(obi_ex_bbo > 0.5 AND zscore(trade_imbalance_signed, 300) < -3.0) AND (bid_depth_concentration < 0.15)`
- **Primitives**: ['obi_ex_bbo', 'trade_imbalance_signed', 'bid_depth_concentration']
- **Threshold / Horizon**: 0.5, 10 ticks
- **WR**: 0.6175298804780877
- **Expectancy**: 1.8967921552456273 bps
- **Feedback tag**: drop_feature
- **Notes**: The added `bid_depth_concentration` filter failed to improve the parent spec's core weakness of inconsistency. Performan


#### iter018_contra_consensus
- **Formula**: `ask_depth_concentration > 0.4 AND obi_ex_bbo > 0.3`
- **Primitives**: ['ask_depth_concentration', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.9336900884132154
- **Expectancy**: 6.4045710042056285 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec has already confirmed an outstanding candidate edge with a WR of 93.4% and expectancy of +6.40 bps over 4,298 t

### iteration 019 (2026-04-22T02:44:32.278417Z)


#### iter019_contra_consensus_tight_obi
- **Formula**: `ask_depth_concentration > 0.4 AND obi_ex_bbo > 0.4`
- **Primitives**: ['ask_depth_concentration', 'obi_ex_bbo']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.9324650265315967
- **Expectancy**: 6.404752003912097 bps
- **Feedback tag**: ensemble_vote
- **Notes**: The spec has an outstanding WR of 93.2% on 4,146 trades. However, the latest tightening step showed diminishing returns,


#### iter019_ultra_consensus
- **Formula**: `((obi_1 - obi_ex_bbo) > 1.5 AND zscore(trade_imbalance_signed, 300) > 1.0) AND (ask_depth_concentration > 0.4 AND obi_ex_bbo > 0.3)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'trade_imbalance_signed', 'ask_depth_concentration']
- **Threshold / Horizon**: 0.5, 5 ticks
- **WR**: 0.5
- **Expectancy**: 0.0 bps
- **Feedback tag**: loosen_threshold
- **Notes**: The spec is untestable as it produced 0 trades, which is a critical failure. The entry criteria are not just strict but 

### iteration 020 (2026-04-22T02:49:47.492901Z)


#### iter020_contra_consensus_trade_confirm
- **Formula**: `(ask_depth_concentration > 0.4 AND obi_ex_bbo > 0.4) AND (zscore(trade_imbalance_signed, 300) < -1.0)`
- **Primitives**: ['ask_depth_concentration', 'obi_ex_bbo', 'trade_imbalance_signed']
- **Threshold / Horizon**: 0.5, 20 ticks
- **WR**: 0.6388888888888888
- **Expectancy**: 1.120013124054171 bps
- **Feedback tag**: drop_feature
- **Notes**: The addition of the `trade_imbalance_signed` feature was detrimental, causing a collapse in both trade count (from 4,146


#### iter020_exhaustion_into_stable_book
- **Formula**: `zscore(trade_imbalance_signed, 300) > 3.0 AND bid_depth_concentration < 0.15 AND ask_depth_concentration < 0.15`
- **Primitives**: ['trade_imbalance_signed', 'bid_depth_concentration', 'ask_depth_concentration']
- **Threshold / Horizon**: 0.5, 50 ticks
- **WR**: 0.5987158908507223
- **Expectancy**: 1.7451063211263713 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec demonstrates a candidate edge with a WR of 59.9% and positive expectancy of +1.75 bps over 623 trades. Given th

### iteration 021 (2026-04-22T02:57:28.116586Z)


#### iter021_tighter_trade_flow_exhaustion
- **Formula**: `zscore(trade_imbalance_signed, 300) > 3.5 AND bid_depth_concentration < 0.15 AND ask_depth_concentration < 0.15`
- **Primitives**: ['trade_imbalance_signed', 'bid_depth_concentration', 'ask_depth_concentration']
- **Threshold / Horizon**: 0.5, 50 ticks
- **WR**: 0.5961538461538461
- **Expectancy**: 1.6695384372467121 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a candidate edge with a 59.6% WR over 572 trades and +1.67 bps expectancy. However, this tightening pr


#### iter021_bbo_divergence_low_vol
- **Formula**: `(obi_1 - obi_ex_bbo) * (rolling_realized_vol(mid_px, 100) < 30)`
- **Primitives**: ['obi_1', 'obi_ex_bbo', 'mid_px']
- **Threshold / Horizon**: 1.2, 1 ticks
- **WR**: 0.9952153110047847
- **Expectancy**: 7.4122480282651795 bps
- **Feedback tag**: combine_with_other_spec
- **Notes**: With a near-perfect WR of 99.5% over 418 trades, this spec has reached peak performance for a standalone signal. Further


#### iter021_tradeflow_into_ask_wall
- **Formula**: `zscore(trade_imbalance_signed, 300) * (ask_depth_concentration > 0.4)`
- **Primitives**: ['trade_imbalance_signed', 'ask_depth_concentration']
- **Threshold / Horizon**: 2.0, 20 ticks
- **WR**: 0.6818181818181818
- **Expectancy**: 3.164315250413633 bps
- **Feedback tag**: drop_feature
- **Notes**: The core weakness is extreme performance inconsistency, with Win Rates swinging from 33.3% to 100% across sessions. This

### iteration 006 (2026-04-22T04:04:02.664002Z)


#### iter006_trade_flow_obi_compound
- **Formula**: `zscore(trade_imbalance_signed, 300) + 3 * obi_1`
- **Primitives**: ['trade_imbalance_signed', 'obi_1']
- **Threshold / Horizon**: 2.5, 20 ticks
- **WR**: 0.9025819377764337
- **Expectancy**: 6.1889960713660415 bps
- **Feedback tag**: tighten_threshold
- **Notes**: The spec confirms a powerful candidate edge with a 90.3% Win Rate over 26,453 trades and a +6.19 bps expectancy. The nex

### iteration 007 (2026-04-22T04:06:20.474186Z)
