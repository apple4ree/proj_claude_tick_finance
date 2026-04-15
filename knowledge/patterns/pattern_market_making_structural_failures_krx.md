---
id: pattern_market_making_structural_failures_krx
tags: [pattern, market-making, krx, two-sided-quoting, position-sync, cash-rejection, fee-burn, adverse-selection, fsm]
created: 2026-04-15T00:00:00
links:
  - lesson_20260415_001_market_maker_stalls_at_zero_roundtrips_hard_stop_fires_before_spread_is_harvested
  - lesson_20260415_002_two_sided_mm_buy_fills_but_sell_never_closes_price_momentum_absorbs_passive_ask
  - lesson_20260415_003_sequential_taker_maker_fsm_position_state_diverges_engine_position_flood_cash_short_rejections
---

# Pattern: Market-Making Structural Failures on KRX

Three iterations of market-making on 000660 (2026-04-15) exposed three independent structural failure modes. Any future market-making strategy must avoid all three simultaneously.

## Failure Mode 1 — Hard stop too tight relative to spread (lesson_001)

**Symptom**: 0 roundtrips, return ≈ -0.30%. Stop fires before either leg has a chance to fill.

**Root cause**: A hard stop of 30 bps with a 25 bps spread gate gives only 1.2x headroom. A passive quote must survive an adverse mid move of up to 1.78x the spread before the earn-side fills. Any stop tighter than 2x the spread gate will fire before roundtrip completion in a random-walk market.

**Rule**: `hard_stop_bps >= 2.0 * spread_gate_bps`. For 000660 at 25 bps gate, minimum stop = 50 bps. Widening to 60 bps is the minimum viable floor.

## Failure Mode 2 — Simultaneous two-sided quoting fails on momentum markets (lesson_002)

**Symptom**: BUY leg fills (price fell into bid), ASK leg never fills. Position stops out as naked long.

**Root cause**: In a trending or mean-reverting intraday KRX market, the same momentum that causes a passive bid to fill (price moving down) immediately moves price further away from the passive ask (price has fallen below ask, ask is now above market and never touched). Two-sided simultaneous quoting structurally exposes the maker to adverse selection: the "wrong" side always fills first.

**Rule**: Do NOT post simultaneous two-sided passive quotes. Use one of:
  (a) Sequential: post ask only after bid fills AND mid has reverted >= 0.5x spread from fill price.
  (b) Directional: taker entry on OBI signal, maker exit only (taker-maker hybrid).
  (c) Inventory-skewed: post only the side that reduces existing inventory imbalance.

## Failure Mode 3 — FSM internal state diverges from engine position (lesson_003)

**Symptom**: 1130 cash rejections + 399 short rejections across 18 RTs. Return = -6.86%.

**Root cause**: A Python FSM (IDLE → PENDING_BUY → LONG) tracks its own state independently of `ctx.portfolio.positions`. When the engine resets the position (hard-stop market sell, EOD close, or rejected order), the FSM may remain in LONG while engine is flat — the next entry then fires a BUY against an already-long book (cash-rejected) or the FSM attempts a SELL against an already-flat book (short-rejected). With lot_size=10 on 000660 (~934,500 KRW/share), a 10M capital pool is 93% consumed per lot — any doubled position attempt is guaranteed cash-rejected.

**Rule**: Any Python FSM with more than 2 states MUST derive its state from `ctx.portfolio.positions[sym].qty` as the primary authority, not internal counters. The canonical pattern:

```python
pos_qty = (ctx.portfolio.positions.get(sym) or Position()).qty

# Reconcile FSM to engine truth
if pos_qty == 0 and self.fsm_state == "LONG":
    self.fsm_state = "IDLE"          # engine closed us (stop/EOD/reject)
    self._pending_buy.pop(sym, None)
    self._pending_sell.pop(sym, None)
if pos_qty > 0 and self.fsm_state == "IDLE":
    self.fsm_state = "LONG"          # filled during pending window
    self._pending_buy.pop(sym, None)
```

This reconciliation block must run at the TOP of `on_tick`, before any order logic.

**Additional rule on lot_size**: For 000660 (~934,500 KRW/share) with 10M capital, `lot_size >= 2` immediately saturates cash on any open position attempt while holding. Use `lot_size = 1` unless capital is scaled proportionally (`capital >= lot_size * price_per_share * 2`).

## Combined checklist for any KRX market-making strategy

Before submitting a market-making spec:
- [ ] `hard_stop_bps >= 2.0 * spread_gate_bps`
- [ ] No simultaneous two-sided passive quoting — use sequential or taker-maker hybrid
- [ ] Python FSM reconciles to `ctx.portfolio.positions[sym].qty` at top of `on_tick`
- [ ] `lot_size * price_per_share * 2 < capital * 0.90` (leave 10% cash headroom)
- [ ] `rejected.cash` and `rejected.short` monitored in post-run report; any value > 5 triggers FSM reconciliation review
