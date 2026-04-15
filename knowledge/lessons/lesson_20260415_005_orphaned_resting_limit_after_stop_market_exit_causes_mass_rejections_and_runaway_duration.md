---
id: lesson_20260415_005_orphaned_resting_limit_after_stop_market_exit_causes_mass_rejections_and_runaway_duration
created: 2026-04-15T04:17:51
tags: [lesson, order-management, orphaned-limit, engine-overhead, stop-loss, rejection]
source: strat_20260415_0005_obi_taker_anchor_stop_000660_iter5
metric: "return_pct=-1.2352 trades=58 fees=118678 rejected_short=2410 duration_sec=602"
links: ["[[pattern_stop_exit_leaves_orphaned_resting_limit]]"]
---

# Orphaned resting LIMIT after stop-market exit causes mass rejections and runaway duration

Observation: When a hard-stop MARKET SELL fires, any previously posted resting LIMIT SELL remains live in the engine queue. On the very next tick the FSM is IDLE, that orphaned LIMIT triggers a short-entry attempt → rejected (max_position). With 58 roundtrips, 2410 short rejections accumulated, inflating backtest duration to 602 s (10x the 60 s threshold).

Why: The engine processes every queued order before advancing state; a stale resting LIMIT with a sell-side qty=1 looks identical to a new short entry. The FSM has no cancel path for previously issued limit IDs.

How to apply next: After any MARKET SELL (stop or otherwise), cancel or suppress the resting LIMIT SELL before re-entering IDLE. Concretely: (a) track the limit order ID on submission and call cancel on stop-fire, OR (b) gate re-arming the LIMIT SELL behind a per-entry flag so it is only posted once per LONG session and never re-posted after a stop.
