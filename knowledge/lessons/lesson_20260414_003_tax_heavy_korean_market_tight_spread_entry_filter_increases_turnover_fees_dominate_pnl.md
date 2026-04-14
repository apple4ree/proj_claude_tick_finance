---
id: lesson_20260414_003_tax_heavy_korean_market_tight_spread_entry_filter_increases_turnover_fees_dominate_pnl
created: 2026-04-14T02:41:49
tags: [lesson, fees, tax, turnover, korea, tight-spread, obi]
source: strat_20260414_0003_tight_spread_ofi_momentum
links:
  - "[[lesson_20260414_002_obi_momentum_has_no_edge_over_spread_cost_at_tick_horizon]]"
  - "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"
metric: "return_pct=-0.9504 trades=372 fees=71744"
---

# Tax-heavy Korean market: tight-spread entry filter increases turnover, fees dominate PnL

Observation: 372 trades generated 71,744 KRW in fees vs only -23,300 KRW realized PnL — fees are 3.08x the realized loss and 75.5% of total loss. Tightening the spread filter (spd_bps < 6) and adding a stricter OBI threshold (obi3 > 0.4) counterintuitively raised trade count to 372 from 334 (strat_0001), inflating fee burn further.

Why: Korean equities carry an 18 bps sell-side transaction tax (tax_bps=18) plus 1.5 bps commission each side — a ~21 bps round-trip hurdle. At single-share sizing, the absolute fee per trade (~193 KRW) exceeds typical short-hold edge. Tight-spread regimes are frequent for 005930 (liquid mega-cap), so the entry fires often without capturing enough edge to clear the 21 bps hurdle before exit conditions trigger.

How to apply next: Raise the minimum expected edge before entry — either by requiring ret5 > 5 bps (not just > 0), or by enlarging lot size to amortize the fixed-cost component of fees, or by switching to a lower-tax instrument (ETFs have 0 tax). Do not tighten spread filters further without reducing trade frequency.
