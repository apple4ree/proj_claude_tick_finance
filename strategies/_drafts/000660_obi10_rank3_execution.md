---
stage: execution
name: 000660_obi10_rank3
created: 2026-04-17
---

# Execution Design: 000660 obi_10 rank-3

## Structural Concern (ESCALATE)

The alpha signal `obi_10 >= 0.6` is NOT present in the 000660 signal brief's top_signals (ranks 1–10). The brief contains `obi_1` at rank 10 (only OBI variant present, viable=false). The signal `obi_10` at threshold 0.6 is an uninvestigated signal for this symbol — alpha-designer should verify this signal has empirical edge on 000660 before proceeding. Proceeding with execution design using brief's obi_1 (rank 10) optimal_exit as the nearest proxy.

## Sub-Tick Check (CRITICAL)

- Symbol: 000660, price: 150,000 KRW
- KRX tick size at 50,000–499,999 KRW: **100 KRW per tick**
- 1 tick in bps: (100 / 150,000) × 10,000 = **6.67 bps**
- User-supplied sl_bps = 3.0 → **3.0 < 6.67 → sub-tick: TRUE**
- A 3 bps stop is physically unexecutable on KRX 000660 at 150,000 KRW.
- Nearest executable SL = 1 tick = 6.67 bps; applying 1.5× safety buffer → **10.0 bps**
- Deviation from brief sl=3 bps: +233% — exceeds ±20% protocol.
- Classification: **structural_concern** (tick-size physical constraint, not discretionary adjustment)

## Adverse Selection Assessment

obi_10 >= 0.6 is a passive BID LIMIT entry triggered when order book imbalance strongly favors bids. Structural adverse selection is HIGH: fills occur when sufficient sell pressure overrides the imbalanced book — exactly the moment when momentum turns against the long position. Per iteration context (strat_0002 smoke test): OBI signals decay by fill time, confirmed fill-time OBI < threshold. TTL and bid-drop cancel are mandatory.

## Entry Order

- Price: bid
- TTL: 30 ticks (OBI spikes are fleeting, <30 tick duration empirically; beyond 30 ticks the OBI condition has likely decayed)
- Bid-drop cancel: 3 ticks (at 150k KRW, 3 ticks = 300 KRW = 2.0 bps; guards against fills into trending decline)
- Rationale: Passive BID at fleeting OBI spike requires strict TTL + bid-drop cancel to prevent stale fills at deteriorating prices. 30-tick TTL consistent with OBI signal duration from iteration context.

## Exit Structure

- Profit target: 60.0 bps (LIMIT SELL) — user-supplied brief baseline, 9 ticks above entry at 150k. PT is on-tick executable (9 × 6.67 = 60 bps).
- Stop loss: 10.0 bps (MARKET SELL, monitor snap.bid_px[0]) — raised from brief's 3 bps due to sub-tick constraint (3 bps < 1 tick = 6.67 bps). Nearest executable floor × 1.5 safety.
- Trailing stop: enabled
  - Activation: 25.0 bps profit (after round-trip cost of 21 bps is covered, ~4 bps net buffer)
  - Distance: 10.0 bps from peak (equal to SL, tighter lock once PT partially reached)
- Rationale:
  - PT=60 bps: net win after 21 bps round-trip = 39 bps. 9-tick target is realistic for OBI-driven momentum.
  - SL=10 bps: cannot physically place 3 bps stop; 10 bps = 1.5 ticks is minimum safe executable. Raised 233% from brief — structural_concern logged.
  - Trailing: activated at 25 bps (just past fee break-even) to protect gains if momentum stalls. Distance=10 bps = SL distance for consistency.
  - Warning: obi_1 (nearest brief proxy) win_rate_pct=34.89% < 40%. Effective break-even WR with pt=60/sl=10 and 21 bps round-trip = (10+21)/(39+31) ≈ 44%. Signal WR ~35% is below break-even — alpha-designer must verify obi_10 has stronger edge than obi_1 for this symbol.

## Position & Session

- Lot size: 2 (minimum to amortize 21 bps fixed round-trip cost)
- Max entries per session: 2 (TTL=30 allows cancelled orders to be retried; OBI spikes may recur intraday)

## Fee Math

- Round-trip cost: 21.0 bps (commission 1.5 bps × 2 + sell tax 18.0 bps)
- Break-even WR at pt=60, sl=10 with fees: (10+21)/(39+31) = 31/70 = **44.3%**
- Signal proxy WR (obi_1 rank 10): 34.89% — **below break-even; weak edge flag**
- Required edge above break-even: need ~10 percentage points additional WR above 34.89%

## Implementation Notes for spec-writer

1. SL must monitor `snap.bid_px[0]`, not `snap.mid`. At 150k KRW, mid-to-bid spread can be 1 tick (6.67 bps), meaning snap.mid-based SL would trigger 6.67 bps later than intended, causing actual realized loss to exceed stated SL significantly (lesson_024 pattern).
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
   if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
       # submit MARKET SELL
   ```
2. Per-symbol spread gate dict (if multi-symbol context):
   ```python
   SPREAD_GATES = {"000660": 16.0}  # floor = 6.67 bps × 1.5 ≈ 10 bps; gate >= 16 bps for p95 spread
   ```
3. TTL implementation: record `submit_tick` at order placement; if `current_tick - submit_tick >= 30` and order unfilled, CANCEL.
4. Bid-drop cancel: record `bid_px_at_submit`; if `snap.bid_px[0] <= bid_px_at_submit - 3 × tick_size` (3 × 100 = 300 KRW), CANCEL.
5. Trailing stop: track `peak_mid_since_entry`; once `unrealized_bps >= trailing_activation_bps (25)`, enable trailing; if `(peak_mid_since_entry - snap.bid_px[0]) / entry_mid × 10000 >= trailing_distance_bps (10)`, MARKET SELL.
6. sl_guard_ticks: apply minimum 5-tick guard before SL can fire (prevents immediate stop on stale fill, per iteration context strat_0003).

```json
{
  "name": "000660_obi10_rank3",
  "hypothesis": "When 10-level OBI for 000660 spikes to >= 0.6 (rank-3 condition), buying pressure concentration predicts short-term upward price movement sufficient to overcome 21 bps round-trip cost.",
  "entry_condition": "obi_10 >= 0.6",
  "market_context": "000660 SK Hynix, price ~150,000 KRW, KRX tick size 100 KRW (6.67 bps/tick)",
  "signals_needed": ["obi_10"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "momentum",
  "multi_date": true,
  "parent_lesson": null,
  "signal_brief_rank": null,
  "structural_concern": "obi_10 not present in 000660 brief top_signals; alpha-designer must verify empirical edge. Nearest proxy obi_1 (rank 10) is viable=false with WR 34.89%.",
  "entry_execution": {
    "price": "bid",
    "ttl_ticks": 30,
    "cancel_on_bid_drop_ticks": 3
  },
  "exit_execution": {
    "profit_target_bps": 60.0,
    "stop_loss_bps": 10.0,
    "trailing_stop": true,
    "trailing_activation_bps": 25.0,
    "trailing_distance_bps": 10.0
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 2
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 233.3,
    "rationale": "PT unchanged at 60 bps (matches user-supplied brief baseline). SL raised 233% from brief's 3 bps to 10 bps due to tick-size physical constraint: at 150,000 KRW with 100 KRW tick size, 1 tick = 6.67 bps; a 3 bps stop is sub-tick and unexecutable on KRX. Applied floor = ceil(3/6.67) × 6.67 × 1.5 = 10 bps. This is a structural_concern escalation, not a discretionary deviation."
  },
  "sub_tick_check": {
    "sl_bps_requested": 3.0,
    "tick_size_krw": 100,
    "price_krw": 150000,
    "tick_size_bps": 6.67,
    "is_sub_tick": true,
    "corrected_sl_bps": 10.0,
    "correction_reason": "3.0 bps < 6.67 bps (1 tick); minimum executable SL raised to 10.0 bps (1.5 ticks safety buffer)"
  },
  "alpha_draft_path": "strategies/_drafts/000660_obi10_rank3_alpha.md",
  "execution_draft_path": "strategies/_drafts/000660_obi10_rank3_execution.md"
}
```
