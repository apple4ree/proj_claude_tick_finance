---
id: pattern_stop_exit_leaves_orphaned_resting_limit
created: 2026-04-15T00:00:00
tags: [pattern, stop-loss, resting-limit, orphaned-limit, order-management, engine-overhead, reference-price, rolling-window, fee-burn, krx, immediate-stop, fsm]
severity: critical
lessons:
  - "[[lesson_20260415_004_stop_loss_using_pre_entry_rolling_return_fires_immediately]]"
  - "[[lesson_20260415_005_orphaned_resting_limit_after_stop_market_exit_causes_mass_rejections_and_runaway_duration]]"
  - "[[lesson_20260415_006_widening_target_degrades_wr_faster_than_it_improves_payoff_use_lot_size_to_amortize_fees_instead]]"
---

# Pattern: Stop exit + resting LIMIT combo has three compounding failure modes

Iters 4-6 each failed for a different reason, but all three failures share a root:
combining a MARKET SELL stop with a pre-posted resting SELL LIMIT without a cancel
primitive. The three failure modes compose — any one of them alone destroys a strategy.

## Failure Mode 1 — Rolling-window stop fires at tick 0 (lesson_004)

**Symptom**: 3049 trades, 0% win rate, return = -90.7%. Every entry immediately
stopped out.

**Root cause**: `stop_loss_return_bps` was checked against `mid_return_bps(lookback=50)`,
which measures the 50-tick BACKGROUND return ending at the CURRENT tick — not the
return since entry. If the market has drifted >= threshold BEFORE the fill, the stop
fires on the very first tick. With lot_size=10 on 000660 (~934,500 KRW/share), each
instant stop-out burns ~19.5 bps in fees with zero directional exposure. 3049 such
stops = -90.7%.

**Rule**: Stop-loss MUST be anchored to `entry_mid` captured at fill-confirmation time.
`gain_bps = (current_mid - entry_mid) / entry_mid * 10000`. Never use a rolling
background window as a stop trigger.

**Secondary guard**: Gate stop condition by `ticks_since_entry >= min_hold_ticks` (e.g.,
5 ticks) so the condition cannot fire at tick 0 even if the anchor is correct.

## Failure Mode 2 — Orphaned resting LIMIT after stop creates mass rejections (lesson_005)

**Symptom**: 2410 rejected.short, backtest duration = 602 s (10x the ~60 s target),
return = -1.24% despite positive directional signal.

**Root cause**: The strategy posted a resting SELL LIMIT for the profit-target exit.
When the stop-MARKET SELL fired, the engine closed the long position. On the very next
tick the FSM was IDLE, but the resting SELL LIMIT was still queued. The engine attempted
to fill it against a flat book — rejected ("short"). With 58 roundtrips over 8 IS days,
this produced 2410 short rejections and inflated backtest duration to 602 s.

**Rule**: After ANY MARKET SELL (stop or forced EOD), cancel the resting SELL LIMIT
for that symbol BEFORE returning to IDLE. As of 2026-04-15 the engine supports a
first-class cancel primitive:

```python
# In on_tick, after a stop-market SELL is submitted:
return [
    Order(sym, side=None, qty=0, order_type=CANCEL, tag="cancel_after_stop"),
    Order(sym, SELL, qty=pos_qty, order_type=MARKET, tag="stop"),
]
```

The CANCEL order is processed immediately (no latency); the MARKET SELL is latency-gated.
Return CANCEL before the MARKET SELL in the list so it executes first.

**Alternative (no cancel)**: Track a per-entry flag `_sell_limit_active[sym]`. On stop
fire, set it to False. In the IDLE state, never re-post a resting SELL LIMIT unless
`_sell_limit_active[sym]` is False AND `_entry_submitted[sym]` is the current session.
This prevents the orphan from being re-activated but does NOT remove the already-queued
resting order — the cancel primitive is the correct solution.

## Failure Mode 3 — Widening target bps degrades win rate faster than it improves payoff (lesson_006)

**Symptom**: At 120 bps target / 40 bps stop (strat_0006), WR = 32.7% vs 41.6%
break-even. At 80 bps target / 60 bps stop (strat_0005), WR = 48.3% vs 43.7% break-even.
Widening target worsened profitability.

**Root cause**: The 19.5 bps round-trip fee is near-fixed per trade at lot_size=1. With
52 trades over 8 IS days, fees = 107K KRW vs realized PnL = +14K KRW. Widening the
target from 80 to 120 bps requires price to travel further — lowering fill probability
(win rate) — while the fee per trade is unchanged. The diverging dynamic: wider target
-> lower WR -> higher required WR. The strategy enters a downward spiral.

**Rule**: To reduce fee burden, scale lot_size (e.g., lot_size=10) rather than widen
the target. With lot_size=10, the notional per trade is 10x while fees remain ~19.5 bps
of notional — so the absolute fee cost per trade scales proportionally but the signal
economics are unchanged. Effective fee hurdle in bps per unit: unchanged. But the
absolute KRW profit per winning trade is 10x, which, compounded, makes the strategy
viable with fewer roundtrips.

Constraint: for 000660 at ~934,500 KRW/share with 10M capital, `lot_size=2` consumes
~18.7% of capital per position (viable). `lot_size=10` consumes ~93% — saturates cash
and will generate cash rejections. **For 000660 specifically: lot_size=2 is the maximum
safe scaling factor at 10M capital.**

## Combined stop-exit checklist

Before submitting any strategy with a stop-loss AND a resting LIMIT exit:

- [ ] Stop gain measurement uses `entry_mid` anchor (not rolling window)
- [ ] Stop condition is gated by `ticks_since_entry >= 5` (cannot fire at tick 0)
- [ ] After MARKET SELL fires, emit `Order(sym, None, 0, CANCEL)` to clear resting limits
- [ ] `lot_size * price_per_share <= capital * 0.18` (18% max per position, leaves 80%+ cash)
- [ ] `target_bps` selected from oracle table to achieve oracle ceiling >= 1.3 x breakeven_W
- [ ] Confirm `rejected.short == 0` after backtest; if > 0 diagnose orphaned limit first

## Relationship to existing patterns

- `pattern_win_rate_ceiling_mandates_hold_duration`: sets the minimum viable
  `target_bps` / `stop_bps` / horizon. Use that table first; this pattern governs the
  mechanical implementation of the stop + resting-limit combo.
- `pattern_market_making_structural_failures_krx`: MM FSM position-sync failure is
  a related symptom (FSM diverges from engine state). The canonical reconciliation
  block in that pattern also prevents re-entry into orphan-generating states.
