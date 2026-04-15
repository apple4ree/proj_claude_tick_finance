---
id: lesson_20260415_014_passive_bid_fills_on_declining_symbols_are_toxic_universe_quality_gate_needed
created: 2026-04-15T06:07:47
tags: [lesson, universe-selection, passive-fill, declining-symbol, regime-filter, resting-limit]
source: strat_20260415_0016_krx_resting_limit_6sym_vol_gate
metric: "return_pct=0.36 trades=23 win_rate_pct=34.8 avg_win_bps=113.57 avg_loss_bps=-81.63"
---

# Passive BID fills on declining symbols are toxic — universe quality gate needed

Observation: Expanding the 4-symbol core to 6 by adding 272210 and 034020 dropped return_pct from +0.506% to +0.36% and win_rate from 53.3% to 34.8%. Both new symbols were in a downtrend during the IS period (buy-hold -6.2% and -3.3% respectively) and produced 0W/8L combined with zero recoveries.

Why: A resting-limit BID strategy relies on mean-reversion after adverse price movement. When the underlying symbol is trending down, passive fills occur at successively worse levels and the price never recovers to the profit target. The vol gate (min_entry_volume) screens for liquidity but not for directional regime — a declining symbol passes the volume check while delivering systematically adverse fills.

How to apply next: Before adding any symbol to the universe, require a positive IS buy-hold return as a minimum regime filter (e.g. >0% over the backtest window). Alternatively, add an intraday trend gate: reject entry if the symbol's VWAP is below its open by more than a configurable threshold.
