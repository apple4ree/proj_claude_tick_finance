---
id: lesson_20260415_023_passive_maker_first_positive_return_obi_inverted_pt_phantom_time_stop_is_real_exit
created: 2026-04-15T14:38:28
tags: [lesson, passive_maker, obi_inversion, phantom_profit_target, time_stop_as_exit, optuna, first_positive_return, 005930]
source: strat_20260415_0026_passive_maker_imbalance_proxy
metric: "return_pct=0.257 trades=6 fees=11798"
links:
  - "[[pattern_sl_reference_price_and_per_symbol_spread_gate]]"
---

# passive_maker_first_positive_return_obi_inverted_pt_phantom_time_stop_is_real_exit

Observation: First positive-return passive maker iteration (+0.257%, WR 66.7%, 6 rt) achieved profitability primarily through time_stop exits (4/6 trades), not the designed PT=150 or trailing at 60 bps — both of which were phantom targets: 0 TP hits, 0 trailing activations.

Alpha Critique (from alpha-critic): Signal edge is weak with inverted OBI separation — LOSS entries had avg OBI=0.78 vs WIN entries OBI=0.505. Higher OBI at entry predicts worse outcomes, the opposite of the hypothesis. Selectivity was 0.00083% (6 trades, 3/8 sessions active), making conclusions statistically fragile. Session gate (total_imbalance >= 0.15 at 10:00) is sound as a mechanism, but OBI >= 0.25 at tick level appears to select for adverse-selection moments rather than genuine bid-pressure. The hypothesis that higher top-3 OBI improves fill quality is not supported.

Execution Critique (from execution-critic): Assessment is suboptimal, not poor — fee structure works (31.5% of gross, lot_size=5 effective). PT=150 bps is unreachable in the observed price range; the +244 bps EOD outlier suggests volatility exists but rarely. Trailing activation=60 never fires. Time_stop at 3000 ticks is the actual profit mechanism delivering 66.7% WR. The exit design works, but the PT and trailing parameters are calibrated for a volatility regime that does not typically occur.

Agreement: OBI tick-level gate adds noise without improving entry quality; exit parameters need recalibration to match actual price volatility.

Disagreement: Alpha says remove/invert OBI gate; execution says reduce PT 150→60-80 and trailing activation 60→30-40. Both are independent fixes.

Priority: both — alpha (OBI gate) and execution (PT/trailing recalibration) must be addressed simultaneously.

How to apply next: Run Optuna sweep over obi_threshold (0.1–0.5), profit_target_bps (50–100), trailing_activation_bps (20–50) with time_stop as ground truth anchor.
