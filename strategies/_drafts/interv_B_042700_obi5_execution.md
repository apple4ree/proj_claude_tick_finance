---
stage: execution
name: interv_B_042700_obi5
created: 2026-04-17
---

# Execution Design: interv_B_042700_obi5

## Tick-Grid Validation (MANDATORY — performed before PT/SL selection)

Symbol 042700 mid price ~303,000 KRW.
KRX bracket: 200,000–500,000 KRW → tick size = 500 KRW.

1 tick in bps = 500 / 303,000 × 10,000 = **16.50 bps**

Tick ladder from entry (downward):
- tick-1: 16.50 bps
- tick-2: 33.00 bps
- tick-3: 49.50 bps

Brief's sl_bps = 3.  Sub-tick check: 3 < 16.50 → **sub_tick_flag = TRUE**.

The brief optimizer computed sl_bps from a continuous return distribution.
No KRX bid level exists within 3 bps of entry. Any adverse move that crosses the SL
threshold will deterministically overshoot to tick-1 minimum (16.50 bps) or tick-2
(33.00 bps) depending on whether tick-1 is sufficient to trigger the market sell.
In practice, a MARKET SELL executes at the best bid, which is exactly tick-1 below
the last traded level — so realized loss when SL fires = 16.50 bps minimum.

This is the same structural defect documented in lesson_20260417_001 (042700 smoke test,
prior iteration: 21 bps SL → overshoot to 33 bps). SL must be set to a realizable tick
boundary. Setting SL = 33.00 bps (tick-2) is the minimum defensible floor given:
- tick-1 (16.50 bps) barely covers half the round-trip cost (21.0 bps); exit at tick-1
  would realize a loss only slightly smaller than full round-trip, while tick-2 gives a
  meaningful loss threshold that preserves break-even math.
- Brief's exit_mix.sl = 20% (non-trivial); 20% of exits hitting 33 bps instead of
  theoretically-3 bps shifts the P&L impact considerably but is accurate.

Chosen SL = 33.00 bps (tick-2 floor). Deviation from brief: +1000% (3 → 33 bps).
This deviation exceeds the standard ±20% bound but is MANDATORY due to tick-size
constraint. Escalated as structural_concern below.

## Structural Concern

Brief sl_bps=3 is sub-tick by 5.5x on this symbol at this price level. It cannot be
implemented. The minimum realizable SL is 16.50 bps (tick-1), but setting SL there
produces a realized loss almost equal to round-trip cost (16.50 vs 21.0 bps). Tick-2
(33.00 bps) is the operationally sound floor. This concern should be escalated to
alpha-designer: the brief's optimizer must be re-run with tick-grid awareness, or
a tick-aware floor must be applied post-hoc before any spec.yaml is written.

## Adverse Selection Assessment

Entry signal: obi_5 >= 0.581266 (95th percentile, top 4% of ticks).
Entry order type: passive LIMIT BUY at bid.

Adverse selection risk: HIGH.
- Passive bid fill occurs when price moves down through the bid → fill coincides with
  directional sell pressure, which is structurally anti-momentum for a long entry.
- OBI imbalance signals are fleeting: lesson_20260417_001 showed OBI decaying from
  0.581 to 0.563 between submission and fill on this exact symbol/signal.
- TTL must be short to avoid fills on decayed OBI.
- Bid-drop cancel provides additional protection.

## Entry Order

- Price: bid
- TTL: 30 ticks (OBI spike expected to persist <30 ticks; consistent with smoke test)
- Bid-drop cancel: 2 ticks (= 33.00 bps drop from submission bid — coincides with tick-2)
- Rationale: TTL=30 limits stale fills on decayed OBI. Bid-drop cancel at 2 ticks = 33 bps
  matches the SL floor; if price moves 2 ticks against us before fill, the trade is already
  at the SL boundary — cancel avoids entering a losing position at all.

## Exit Structure

- Profit target: 79 bps (brief baseline, no adjustment — within single-tick rounding)
- Stop loss: 33.00 bps (tick-2 floor; raised from brief's 3 bps due to tick-size constraint)
- Trailing stop: enabled
  - Activation: 33 bps profit (≥ round-trip cost 21 bps; activation set to match SL so
    risk is symmetric once activated)
  - Distance: 33 bps from peak (= tick-2, consistent with SL distance)
- Rationale:
  - PT=79 bps: brief's optimal. No adjustment. 1 tick = 16.5 bps, so 79 bps ≈ tick-4.8;
    nearest realizable is tick-5 (82.5 bps). PT is specified in bps; engine rounds to
    tick — acceptable overshoot ≤ 4 bps, within low-severity tolerance.
  - SL=33 bps: mandatory upward adjustment from brief's 3 bps due to tick-grid constraint
    (see above). Deviation = +1000%, justified by tick-size constraint exclusively.
  - exit_mix: pt=16%, sl=20%, ts=63% — strategy is predominantly time-stop driven.
    Trailing stop at 33 bps activation / 33 bps distance mimics the time-stop role while
    locking in gains on large runners.
  - Break-even WR at PT=79, SL=33: 33 / (79 + 33) = 29.5%.
    Brief win_rate_pct = 61.63% → substantial margin above break-even.

## Position & Session

- Lot size: 2
- Max entries per session: 2
- Rationale: TTL=30 + bid-drop cancel will suppress most fills. Allowing 2 entries per
  session preserves capture rate. Lot=2 amortizes fixed fee across fills.

## Fee Math

- Round-trip cost: 21.0 bps (KRX: 1.5 bps commission × 2 + 18.0 bps sell tax)
- Break-even WR at PT=79, SL=33: 33 / (79 + 33) × 100 = **29.5%**
- Brief win_rate = 61.63% → edge = +32.1 pp above break-even
- Warning: realized SL will be 33 bps (not 3); this shifts the actual break-even WR from
  the brief's implicit ~3.6% to 29.5%. Brief WR of 61.63% still clears it comfortably,
  but the P&L expectation degrades versus the brief's optimizer assumption.

## Implementation Notes for spec-writer

1. SL must monitor snap.bid_px[0], not snap.mid. Realized exit at MARKET SELL = best bid.
   Use: unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000;
   trigger if unrealized_bps <= -33.0 and ticks_since_entry >= 5.

2. stop_loss_bps = 33.0 in spec.yaml. Do NOT use brief's 3 bps — it is sub-tick and will
   cause structural sl_overshoot invariant violations on every triggered stop.

3. Bid-drop cancel at 2 ticks (33 bps) is equivalent to the SL distance. If the order is
   not yet filled and price drops 2 ticks, cancel the limit order — we would stop out
   immediately on fill anyway.

4. Trailing stop: activate at 33 bps profit, trail 33 bps from peak. Track peak_bid since
   entry; sell MARKET when current_bid < peak_bid - trail_distance.

5. sl_guard_ticks = 5: do not fire SL within 5 ticks of entry (engine strict-mode artifact
   documented in lesson_20260417_002; prevents force_sell from ignoring guard).

6. Per-symbol spread gate (single symbol — not applicable here, but note: 042700 tick floor
   = 16.50 bps; any spread gate should be >= 24.75 bps = floor × 1.5).

## Deviation from Brief

| Parameter | Brief optimal | Chosen | Deviation | Reason |
|---|---|---|---|---|
| pt_bps | 79 | 79 | 0% | No adjustment |
| sl_bps | 3 | 33 | +1000% | Tick-size constraint (sub-tick flag; mandatory) |

deviation_from_brief:
  pt_pct: 0.0
  sl_pct: +1000.0
  rationale: "Brief sl_bps=3 is sub-tick on 042700 at 303,000 KRW (tick=500 KRW=16.50 bps).
  Minimum realizable SL is 1 tick (16.50 bps); chosen 2-tick floor (33.00 bps) to ensure
  loss is meaningful relative to round-trip cost. Deviation mandatory; exceeds ±20% bound;
  escalated as structural_concern."

```json
{
  "name": "interv_B_042700_obi5",
  "hypothesis": "OBI(5) >= 0.58 captures aggressive buy-side pressure in the top 5 bid levels, predicting short-horizon upward price continuation on 042700.",
  "entry_condition": "obi(5) >= 0.58",
  "market_context": "042700 KRX tick-level, single symbol, long-only",
  "signals_needed": ["obi_5"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "momentum",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_001",
  "signal_brief_rank": 2,
  "entry_execution": {
    "price": "bid",
    "ttl_ticks": 30,
    "cancel_on_bid_drop_ticks": 2
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 33.0,
    "trailing_stop": true,
    "trailing_activation_bps": 33.0,
    "trailing_distance_bps": 33.0
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 2
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 1000.0,
    "rationale": "Brief sl_bps=3 is sub-tick on 042700 at ~303,000 KRW (tick size=500 KRW=16.50 bps/tick). No bid level exists within 3 bps. Minimum realizable exit is tick-1 (16.50 bps); chosen tick-2 (33.00 bps) as floor because tick-1 loss is nearly equal to full round-trip cost (16.50 vs 21.0 bps). Deviation mandatory due to tick-size constraint; escalated as structural_concern."
  },
  "tick_bps_computation": {
    "symbol": "042700",
    "mid_price_krw": 303000,
    "krx_bracket": "200000-500000",
    "tick_size_krw": 500,
    "tick_bps": 16.5,
    "tick_bps_formula": "500 / 303000 * 10000 = 16.50 bps",
    "brief_sl_bps": 3,
    "brief_sl_in_ticks": 0.182,
    "tick_1_bps": 16.5,
    "tick_2_bps": 33.0,
    "tick_3_bps": 49.5
  },
  "sub_tick_flag": true,
  "structural_concern": "Brief sl_bps=3 is 0.18 ticks — unimplementable on KRX. The brief optimizer operated on continuous returns without tick-grid awareness. All 042700 strategies must apply a minimum sl_bps floor of 33.0 (tick-2) until the brief generator is made tick-aware.",
  "alpha_draft_path": "strategies/_drafts/interv_B_042700_obi5_alpha.md",
  "execution_draft_path": "strategies/_drafts/interv_B_042700_obi5_execution.md"
}
```
