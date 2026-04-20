---
id: lesson_20260415_006_widening_target_degrades_wr_faster_than_it_improves_payoff_use_lot_size_to_amortize_fees_instead
created: 2026-04-15T04:27:47
tags: [lesson, fee_burn, lot_size, win_rate, break_even, target_bps, 000660, obi, passive-limit, adverse-selection, sample-size, krx]
source: strat_20260415_0006_obi_taker_price_poll_exit_000660_iter6
links: ["[[pattern_stop_exit_leaves_orphaned_resting_limit]]", "[[pattern_sample_size_gate_before_parameter_tuning]]", "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"]
metric: "return_pct=-0.9294 trades=52 fees=106936"
---

# Widening target degrades WR faster than it improves payoff -- use lot_size to amortize fees, but scaling does not fix edge

## Fee math divergence (strat_0006)

At 120 bps target / 40 bps stop (price-poll MARKET exits), WR collapsed to 32.7% against a 41.6% break-even requirement, despite realized_pnl = +14K confirming the directional signal has edge. The signal works; fee math doesn't.

Why: The 19.5 bps round-trip cost (commission + tax) is near-fixed per trade regardless of lot size. With lot_size=1 and 52 trades, fees = 107K while realized PnL = 14K. Widening the target to reach break-even lowers WR further -- a diverging dynamic.

## Lot-size scaling is a pure notional lever (strat_0009)

Increasing lot_size from 2 to 3 raised return_pct from 0.1038% to 0.1556% (+50%), exactly proportional to the notional multiplier. Win rate (46.7%), avg win (111 bps), avg loss (-83 bps), and trade count (15 roundtrips) are unchanged. Lot-size scales gross PnL and fees together without touching signal quality or adverse-selection dynamics. 15 roundtrips over 8 days yields a +/-12 pp confidence interval on win rate; statistical significance is absent.

How to apply next: Do not widen target to chase payoff ratio -- reduce fee load via size instead, but stop scaling lot_size until edge quality is validated on a larger sample (>=50 roundtrips). The next priority is reducing adverse selection at entry: shift entry from passive BID to mid-price, add a short confirmation window (2-3 ticks of OBI persistence), or filter on volume-imbalance decay to avoid chasing pullback fills.
