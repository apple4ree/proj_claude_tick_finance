---
id: lesson_20260415_007_cancel_order_must_not_evict_co_submitted_market_sell_stop_orders_from_pending_queue
created: 2026-04-15T05:02:25
tags: [lesson, engine, cancel, stop-loss, order-management, bug]
source: strat_20260415_0008_krx_resting_limit_2sym_obi35_lot2_cancel
metric: "return_pct=0.1038 trades=15 fees=31059.58"
links: ["[[pattern_stop_exit_leaves_orphaned_resting_limit]]"]
---

# CANCEL order must not evict co-submitted MARKET SELL stop orders from pending queue

Observation: When a CANCEL order and a MARKET SELL stop were submitted in the same tick, the engine's cancel-processing pass cleared the MARKET SELL from the pending queue before it could fire, silently suppressing all stop exits — all 7 losses became exit_eod overrides instead of clean stops.

Why: The engine iterated over the full pending-order queue when processing CANCEL, matching on symbol/side without scoping to LIMIT orders only, so co-submitted MARKET orders were collateral victims.

How to apply next: Any CANCEL implementation must scope its queue eviction strictly to LIMIT orders (or to the specific order_id being cancelled). Co-submitted protective orders (MARKET SELL, stop-limit) must be excluded from the cancel sweep. Add a regression test asserting that a CANCEL + MARKET SELL pair submitted together results in exactly one fill from the MARKET SELL.
