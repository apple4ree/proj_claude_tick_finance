---
id: lesson_20260415_004_stop_loss_using_pre_entry_rolling_return_fires_immediately
created: 2026-04-15T03:58:23
tags: [lesson, stop-loss, reference-price, rolling-window, immediate-stop, fee-burn]
source: strat_20260415_0004_obi_taker_maker_000660
metric: "return_pct=-90.7 trades=3049 fees=6027881 win_rate=0.0"
links: ["[[pattern_stop_exit_leaves_orphaned_resting_limit]]"]
---

# stop-loss using pre-entry rolling return fires immediately

Observation: stop_loss_return_bps checked against mid_return_bps(lookback=50) measures the 50-tick BACKGROUND return ending at the current tick, not the return since entry. If the market has already drifted ≥ threshold before the fill is confirmed, the stop fires on the very first tick of the position — producing 0s hold time, 100% stop-out rate, and pure fee burn with no directional exposure.

Why: mid_return_bps(lookback=50) is a rolling window anchored to the current tick, so it captures pre-entry price action. On fill confirmation, if the 50-tick background return happens to be below -60 bps, the condition is instantly true. With 3049 fills all exiting via stop, avg_loss ≈ taker spread + fees (−31.59 bps) — no directional alpha is ever expressed.

How to apply next: Stop-loss must snapshot entry_mid at fill-confirmation time and compute return_since_entry = (current_mid − entry_mid) / entry_mid × 10000 bps. Alternatively gate stop-loss by ticks_since_entry ≥ min_hold_ticks (e.g. 5) so the condition cannot fire at tick 0.
