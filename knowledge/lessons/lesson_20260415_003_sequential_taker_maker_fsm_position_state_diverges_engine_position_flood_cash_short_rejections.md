---
id: lesson_20260415_003_sequential_taker_maker_fsm_position_state_diverges_engine_position_flood_cash_short_rejections
created: 2026-04-15T03:16:47
tags: [lesson, state-machine, taker-maker, cash-rejection, position-sync, krx, lot-sizing]
source: strat_20260415_0003_taker_maker_seq_000660
metric: "return_pct=-6.861 trades=36 fees=360838"
---

# sequential_taker_maker_fsm_position_state_diverges_engine_position_flood_cash_short_rejections

Observation: Sequential taker-maker state machine on 000660 (lot_size=10) produced 1130 cash rejections and 399 short rejections across 18 roundtrips, collapsing return to -6.86% vs a 72.1% required breakeven win rate.
Why: The FSM tracks an internal IDLE/PENDING_BUY/LONG state but does not read actual engine position before submitting orders. When the hard stop fires a market sell, the engine position resets to 0 while the FSM may still be in LONG state (or vice versa), causing the next entry to submit against an already-flat or already-long book -- the engine rejects these as cash-insufficient or short-side violations. With lot_size=10 on 000660 (~934,500 KRW/share), a single roundtrip consumes 93% of 10M capital; any doubled position attempt is guaranteed cash-rejected.
How to apply next: Before any new order submission, gate the FSM transition on engine.position == 0 (IDLE) or engine.position > 0 (LONG), not on internal state alone. Reduce lot_size to 1 or shrink capital notional so that position drift does not immediately saturate the cash limit.
