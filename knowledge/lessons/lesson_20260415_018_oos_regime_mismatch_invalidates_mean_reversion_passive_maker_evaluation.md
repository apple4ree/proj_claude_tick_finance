---
id: lesson_20260415_018_oos_regime_mismatch_invalidates_mean_reversion_passive_maker_evaluation
created: 2026-04-15T06:44:48
tags: [lesson, oos, regime, mean-reversion, passive-maker, market-crash, statistical-power, is-overfitting, regime-dependency, session-drop, oos-failure]
source: strat_20260415_0023_oos_4sym_vol_gate
metric: "return_pct=-0.0878 trades=5 win_rate=20.0 is_return_pct=0.506 is_trades=15"
---

# OOS regime mismatch invalidates mean-reversion passive maker evaluation

Observation: OOS validation of strat_0014 on 20260326-20260330 returned -0.088% with N=5 roundtrips vs IS +0.506%, but the OOS period saw a 9%+ market selloff (000660 -9.43%, 006800 -9.26%) -- a sustained momentum-down regime fundamentally hostile to passive mean-reversion.

Why: A passive limit-order maker earns spread by fading short-term imbalances. In a directional momentum crash, the book is one-sided, fill rates collapse on the profitable side, and resting bids are hit repeatedly as price slides. N=5 is also insufficient for statistical inference (WR CI +/-44pp). avg_win=128.71 bps and avg_loss=-81.71 bps matched IS exactly, confirming exit mechanics are intact -- the degradation is pure regime, not signal decay.

How to apply next: Before accepting an OOS result as signal-evidence, check the OOS buy-hold return of the universe; if |universe_return| > 3% over the OOS window, flag the run as regime-confounded and require a regime-neutral holdout before concluding.

## IS bullish bias confirmed -- strat_0026_oos_regime_filter (2026-04-15)

strat_0025 earned IS WR=66.7% on 20260316-20260325 (+6.5% buy-hold for 000660), but both OOS holdouts -- post-IS (20260326-20260330, -9.4% buy-hold) and pre-IS (20260305-20260313, -7.4% buy-hold) -- returned negative with N=4 and N=5 roundtrips respectively. An 80 bps session-drop gate was not sufficient to block entries during the broader multi-day downtrend.

The IS window captured a distinctly bullish 8-day rally; passive mean-reversion BID fills work when price oscillates around a level. In sustained directional downtrends the intraday session-drop gate triggers too late -- individual session drops can stay below 80 bps while multi-day cumulative trend is deeply negative.

Remedy: Add a multi-day trend filter (e.g., 3-day rolling return of universe < -2%) that blocks all entries regardless of intraday session drop. Alternatively, require IS validation window to include at least one flat/down week alongside any bullish week to confirm the edge is regime-agnostic.
