---
id: lesson_20260415_020_is_period_was_uniquely_bullish_window_passive_maker_is_wr_does_not_generalize_across_regimes
created: 2026-04-15T06:57:36
tags: [lesson, is-overfitting, regime-dependency, passive-maker, session-drop, oos-failure, mean-reversion]
source: strat_20260415_0026_oos_regime_filter
metric: "return_pct=-0.0139 trades=4 win_rate=25.0 avg_win_bps=128.71 avg_loss_bps=-69.10"
---

# IS period was uniquely bullish window passive maker IS WR does not generalize across regimes

Observation: strat_0025 earned IS WR=66.7% on 20260316-20260325 (+6.5% buy-hold for 000660), but both OOS holdouts — post-IS (20260326-20260330, -9.4% buy-hold) and pre-IS (20260305-20260313, -7.4% buy-hold) — returned negative with N=4 and N=5 roundtrips respectively. An 80 bps session-drop gate was not sufficient to block entries during the broader multi-day downtrend.

Why: The IS window captured a distinctly bullish 8-day rally; passive mean-reversion BID fills work when price oscillates around a level. In sustained directional downtrends the intraday session-drop gate triggers too late — individual session drops can stay below 80 bps while multi-day cumulative trend is deeply negative. The 80 bps gate is a session-level filter, not a regime-level filter.

How to apply next: Add a multi-day trend filter (e.g., 3-day rolling return of universe < -2%) that blocks all entries regardless of intraday session drop. Alternatively, require IS validation window to include at least one flat/down week alongside any bullish week to confirm the edge is regime-agnostic before treating IS WR as evidence of persistent edge.
