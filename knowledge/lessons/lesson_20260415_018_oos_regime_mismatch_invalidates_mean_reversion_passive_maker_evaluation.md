---
id: lesson_20260415_018_oos_regime_mismatch_invalidates_mean_reversion_passive_maker_evaluation
created: 2026-04-15T06:44:48
tags: [lesson, oos, regime, mean-reversion, passive-maker, market-crash, statistical-power]
source: strat_20260415_0023_oos_4sym_vol_gate
metric: "return_pct=-0.0878 trades=5 win_rate=20.0 is_return_pct=0.506 is_trades=15"
---

# OOS regime mismatch invalidates mean-reversion passive maker evaluation

Observation: OOS validation of strat_0014 on 20260326-20260330 returned -0.088% with N=5 roundtrips vs IS +0.506%, but the OOS period saw a 9%+ market selloff (000660 -9.43%, 006800 -9.26%) — a sustained momentum-down regime fundamentally hostile to passive mean-reversion.

Why: A passive limit-order maker earns spread by fading short-term imbalances. In a directional momentum crash, the book is one-sided, fill rates collapse on the profitable side, and resting bids are hit repeatedly as price slides. N=5 is also insufficient for statistical inference (WR CI ±44pp). avg_win=128.71 bps and avg_loss=-81.71 bps matched IS exactly, confirming exit mechanics are intact — the degradation is pure regime, not signal decay.

How to apply next: Before accepting an OOS result as signal-evidence, check the OOS buy-hold return of the universe; if |universe_return| > 3% over the OOS window, flag the run as regime-confounded and require a regime-neutral holdout before concluding.
