---
id: lesson_20260415_006_widening_target_degrades_wr_faster_than_it_improves_payoff_use_lot_size_to_amortize_fees_instead
created: 2026-04-15T04:27:47
tags: [lesson, fee_burn, lot_size, win_rate, break_even, target_bps, 000660, obi]
source: strat_20260415_0006_obi_taker_price_poll_exit_000660_iter6
metric: "return_pct=-0.9294 trades=52 fees=106936"
links: ["[[pattern_stop_exit_leaves_orphaned_resting_limit]]"]
---

# Widening target degrades WR faster than it improves payoff — use lot_size to amortize fees instead

Observation: At 120 bps target / 40 bps stop (price-poll MARKET exits), WR collapsed to 32.7% against a 41.6% break-even requirement, despite realized_pnl = +14K confirming the directional signal has edge. The signal works; fee math doesn't.

Why: The 19.5 bps round-trip cost (commission + tax) is near-fixed per trade regardless of lot size. With lot_size=1 and 52 trades, fees = 107K while realized PnL = 14K. Widening the target to reach break-even lowers WR further — a diverging dynamic. The strat_0005 baseline achieved 48.3% WR at 80 bps target / 60 bps stop, clearing its 43.7% break-even at lot_size=1.

How to apply next: Switch lot_size=10 to spread the fixed per-trade fee cost over 10x the notional, dropping the effective fee hurdle from ~19.5 bps to ~2 bps per unit. Pair with 80 bps target + 60 bps stop where 48.3% WR is historically achievable, giving comfortable margin above the new ~37% break-even. Do not widen target to chase payoff ratio — reduce fee load via size instead.
