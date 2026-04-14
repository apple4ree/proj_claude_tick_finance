---
id: lesson_20260414_002_obi_momentum_has_no_edge_over_spread_cost_at_tick_horizon
created: 2026-04-14T01:45:44
tags: [lesson, turnover, fees, edge, failure]
source: strat_20260414_0002_obi_momentum_bps
metric: "return_pct=-0.86 trades=292 fees=65405"
links:
  - "[[lesson_20260414_001_absolute_spread_filter_breaks_cross_symbol]]"
---

# obi_momentum has no edge over spread cost at tick horizon

Observation: iter2 applied the bps spread fix from lesson_20260414_001 and 000660 traded (7 losers vs 0 trades before). Net return still negative (-0.86%) — realized -20200 dwarfed by 65405 in fees across 292 trades. Why: obi>0.5 + short positive mid return is a mean-reverting crossing signal at tick scale; expected move is a few bps but each round-trip pays ~2bps commission + 18bps sell tax. Unless entry captures >20bps move with hit-rate > 60%, net edge is negative by construction. How to apply next: either (a) target much longer holds (hundreds of ticks) with a volatility or trend filter, (b) add an inventory model that avoids mean-reverting crosses, or (c) restrict to maker-side orders once resting-limit simulation is implemented (Phase 4+ on backlog).

## Additional observation — strat_20260414_0005_duration_extended_trend_v2 (2026-04-14)

Observation: Extending hold to 200 ticks and reducing turnover cut the loss 5x (-0.17% vs -0.95%), confirming the fee-burn diagnosis. But win_rate remains 0% and avg pre-fee pnl per roundtrip is -320 KRW — the signal direction is wrong, not just the sizing. entry condition "ret200 > 15 bps + obi5 > 0.15" reliably fires at the tail end of a completed move, capturing reversal rather than continuation. Why: a 200-tick lookback mid-return of >15 bps on 005930 implies the price has already run; the subsequent 200-tick hold window straddles the mean-reversion leg. This is a structural anti-edge: the entry is a lagging trend-follower on a single stock with intraday mean-reversion dynamics. How to apply next: invert the signal — treat ret200 > threshold as a short/counter-trend entry, or require acceleration (ret50 > ret_prev_50) to confirm momentum is still live before entering, or extend hold to 500+ ticks to straddle both the tail and recovery phases.
