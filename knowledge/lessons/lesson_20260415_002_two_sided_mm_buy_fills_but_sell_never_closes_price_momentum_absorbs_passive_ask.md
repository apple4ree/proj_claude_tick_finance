---
id: lesson_20260415_002_two_sided_mm_buy_fills_but_sell_never_closes_price_momentum_absorbs_passive_ask
created: 2026-04-15T03:05:49
tags: [lesson, market-making, fill-asymmetry, two-sided-quoting, sequential-quoting, 000660]
source: strat_20260415_0002_krx_as_mm_000660_wider_stop
metric: "return_pct=-0.1025 trades=2 fees=10248.0"
---

# two-sided MM BUY fills but SELL never closes price momentum absorbs passive ask

Observation: Across two AS market-maker iterations on 000660 (v1: 2 RT, v2: 1 RT), the BUY leg fills as a resting bid catches a downtick, but the passive SELL ask is never hit before price reverses upward — leaving a naked long that either stops out or times out with zero spread capture.
Why: In a trending or mean-reverting intraday market, the same momentum that causes a passive bid to fill (price falling into it) immediately moves price further away from the passive ask (price has fallen, ask is now above market, never touched). Two-sided simultaneous quoting structurally fails when the adverse side fills: the 'earn-side' is always on the wrong side of momentum by construction.
How to apply next: Replace simultaneous two-sided quoting with a sequential one-sided approach — only post the ask after the bid is filled and mid has reverted at least half the spread; or switch to directional execution (taker entry on OBI signal, maker exit only) to align entry momentum with the fill-side.
