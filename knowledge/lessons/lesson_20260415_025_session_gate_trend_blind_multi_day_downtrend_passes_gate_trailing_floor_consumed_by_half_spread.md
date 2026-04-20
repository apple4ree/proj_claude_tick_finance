---
id: lesson_20260415_025_session_gate_trend_blind_multi_day_downtrend_passes_gate_trailing_floor_consumed_by_half_spread
created: 2026-04-15T17:31:42
tags: [lesson, session_gate, trend_blind, downtrend, trailing_stop, half_spread, floor_defect, regime_filter, passive_maker, "034020"]
source: strat_20260415_0029_passive_maker_bid_sl_2sym
metric: "return_pct=0.005 trades=14 win_rate=42.9 005930_return_pct=0.197 034020_return_pct=-0.188"
links:
  - "[[pattern_sl_reference_price_and_per_symbol_spread_gate]]"
---

# session_gate_trend_blind_multi_day_downtrend_passes_gate_trailing_floor_consumed_by_half_spread

Observation: Session gate (total_imbalance >= 0.25) is blind to multi-day trends; 034020 passed gate on 4/8 days during a -7.3% downtrend, yielding 25% WR while 005930 (range-bound) posted 66.7% WR on 6 trades — and trailing_stop exits averaging net -0.5 bps reveal the floor is consumed by half-spread on MARKET SELL fills.

Alpha Critique (from alpha-critic): Signal edge is weak. Spread gate fires within 10 seconds of the 10:00 window on every gate-passing day, exhausting the 2/day cap immediately — the binding constraint is the cap, not signal quality. Entry prices show no WIN/LOSS separation. 034020 passed the imbalance gate throughout a -7.3% multi-day decline, confirming that total_imbalance is a within-session measure with zero multi-day predictive content. The hypothesis that session imbalance selects safe long entries is unsupported when symbol-level trend is bearish.

Execution Critique (from execution-critic): Assessment is suboptimal — two structural fixes from strat_0028 are confirmed working: bid-anchored SL (max overshoot 6.6 bps vs 362 bps prior) and cancel-at-gate-close (0 fills past 13:00). Remaining defects: trailing_stop floor = 50-30 = 20 bps design minus ~4.7 bps half-spread on MARKET SELL = net -0.5 bps on 2 trailing exits; one time_stop failure held a 034020 position 6.5h to EOD. WR 42.9% is below 53.5% net break-even (PT=80/SL=50 payoff too demanding).

Agreement: 034020 is a drag due to regime mismatch (trend-blind gate selects into downtrend); trailing floor design must account for bid-side exit cost.

Disagreement: Alpha says add multi-day trend filter to fix the upstream regime problem; execution says raise trailing_activation to 70 bps and widen PT to 110-120 to fix payoff math. Both diagnoses are correct and independent.

Priority: alpha — a multi-day trend filter on 034020 would eliminate the regime-mismatch losses without any execution change; execution improvements apply after the symbol-level filter is added.

How to apply next: Add close[t-1] < close[t-3] skip condition per symbol. Raise trailing_activation to 70 bps (floor ~35 bps net). Widen PT to 110-120 bps to lower break-even WR to 44-46%.
