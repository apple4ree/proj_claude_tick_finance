---
id: lesson_20260414_014_mean_reversion_at_15_30_min_timescale_is_anti_edge_with_18_win_rate_and_oversized_lots_causing_cash_rejections
created: 2026-04-14T09:32:28
tags: [lesson, mean-reversion, anti-edge, lot-sizing, cash-rejection, negative-ev, krx]
source: strat_20260414_0016_rolling_mean_reversion_escape
links: ["[[pattern_krx_fee_hurdle_dominates_tick_edge]]"]
metric: "return_pct=-8.0244 trades=144 fees=629942.9"
---

# Mean-reversion at 15-30 min timescale is anti-edge with 18% win rate and oversized lots causing cash rejections

Observation: A 2000-tick mean-reversion signal on KRX equities yielded win_rate=18% against a required breakeven of 49%, producing -39.4 bps expected PnL per roundtrip; simultaneously lot_size=10 on 000660 (934,500 KRW/share) consumed 93.5% of 10M capital, triggering 518 cash rejections.
Why: At 2000-tick (≈15-30 min) lookback, downside deviations in Korean equities continue rather than revert — the signal is momentum-like in practice, so buying dips amplifies losses. Oversized lots block most of the order flow entirely, making the strategy effectively untradeable.
How to apply next: Swap mean-reversion entry for short-term momentum (mid_return_bps lookback=100, threshold > +10 bps). Reduce lot_size to 1-2 shares or restrict universe to 005930 (lower price) to keep notional under 5% of capital. Validate breakeven win-rate against fee structure before running any new entry signal.
