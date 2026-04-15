---
id: lesson_20260415_008_lot_size_scaling_amplifies_nominal_pnl_linearly_but_does_not_improve_edge_quality
created: 2026-04-15T05:09:16
tags: [lesson, lot-size, passive-limit, adverse-selection, sample-size, krx]
source: strat_20260415_0009_krx_resting_limit_2sym_obi35_lot3_cancel
metric: "return_pct=0.1556 trades=15 fees=46589"
links: ["[[pattern_sample_size_gate_before_parameter_tuning]]", "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"]
---

# lot-size scaling amplifies nominal PnL linearly but does not improve edge quality

Observation: Increasing lot_size from 2 to 3 raised return_pct from 0.1038% to 0.1556% (+50%), exactly proportional to the notional multiplier. Win rate (46.7%), avg win (111 bps), avg loss (-83 bps), and trade count (15 roundtrips) are unchanged.

Why: Lot-size is a pure notional lever — it scales gross PnL and fees together without touching signal quality or adverse-selection dynamics. The passive LIMIT BUY at bid is still filled on pullbacks, meaning every entry already carries a directional disadvantage. 15 roundtrips over 8 days yields a ±12 pp confidence interval on win rate; statistical significance is absent.

How to apply next: Stop scaling lot_size until edge quality is validated on a larger sample (>=50 roundtrips). The next priority is reducing adverse selection at entry: shift entry from passive BID to mid-price, add a short confirmation window (2-3 ticks of OBI persistence), or filter on volume-imbalance decay to avoid chasing pullback fills.
