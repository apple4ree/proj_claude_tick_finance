---
id: lesson_20260415_013_exit_obi_divergence_as_early_exit_signal_for_resting_limit_stops
created: 2026-04-15T05:54:06
tags: [lesson, exit, obi, stop-loss, resting-limit, mean-reversion]
source: strat_20260415_0014_krx_resting_limit_4sym_vol_gate
metric: "return_pct=0.506 trades=15 win_rate=53.3 avg_win_bps=113.57 avg_loss_bps=-83.71"
---

# Exit OBI divergence as early-exit signal for resting-limit stops

Observation: In strat_0014 (N=15 roundtrips), winning trades exit with avg OBI=-0.370 while losing trades that hit stop show avg OBI=+0.520 at exit time — a 0.89-unit divergence in opposite directions.

Why: When OBI remains strongly positive after entry, it signals that the order book pressure is still buying-side, meaning the resting long has not yet catalyzed a reversal. Continued positive OBI is a regime mismatch for a mean-reversion limit entry; the position should exit before stop is triggered. Conversely, OBI going negative post-entry confirms the short-term reversal is occurring, leading to limit_exit wins.

How to apply next: Add an OBI-based early-exit rule: if OBI > +0.30 for N consecutive ticks after fill, cancel the profit target and exit at market or best bid. This converts stop-outs into smaller managed losses, improving WR without needing a wider stop. Threshold N=3-5 ticks and OBI floor of 0.25-0.35 are the search range.
