---
stage: execution
name: pilot_s2_010140_spread
created: 2026-04-17
signal_brief_rank: 1
---

# Execution Design: pilot_s2_010140_spread

## Adverse Selection Assessment

Entry is MARKET BUY at ask (taker). Adverse selection risk: **low**. Taker entry eliminates passive fill adverse selection entirely — the fill occurs immediately at the current ask, not at a resting bid that gets hit because the price is moving against us. The signal (spread_bps >= 17.498) fires on a snapshot condition; no multi-tick confirmation is required, so the entry can be executed aggressively on the tick the condition is first observed. This mirrors the lesson from strat_20260417_0002: passive bid entry into 042700's OBI signal suffered adverse selection (fill only when price falling), which degraded edge. For a spread-reversion mean-reversion signal, taker entry captures the early part of the reversion move.

## Tick-Size Structural Concern (ESCALATED)

010140 (Samsung Electro-Mechanics) trades at ~30,625 KRW mid-price. KRX tick grid for prices in the 10,000–50,000 KRW band is 100 KRW per tick.

- **1 tick = 100 / 30,625 * 10,000 = 32.65 bps**
- Brief `sl_bps = 3` implies 0.09 ticks — this is **physically sub-tick** and cannot be realized on any KRX order book
- Brief `pt_bps = 79` implies 2.42 ticks — must round to 2 or 3 ticks (65.31 or 97.96 bps)

This is a tick-size constraint, not a discretionary deviation. The same structural constraint forced SL from 3 bps to 33 bps in the prior pilot (042700, strat_20260417_0003); the root cause there was 042700's 500 KRW tick at ~300k KRW price. Here 010140 has a 100 KRW tick at ~30k KRW — qualitatively the same constraint but with different magnitude because 010140 is lower-priced.

**SL deviation = +988% from brief's optimal. This exceeds the 20% adjustment limit and is flagged as `structural_concern`.**

The brief's SL optimizer worked on continuous bps values derived from the tick-by-tick mid_ret distribution; it did not enforce the KRX tick grid. The realized SL must snap to the nearest feasible tick level.

## Entry Order

- **Price**: ask (MARKET BUY — taker fill at current best ask)
- **TTL**: 15 ticks — signal fires on snapshot condition; if the ask is not reachable within 15 ticks the quote has moved and the opportunity is stale
- **Bid-drop cancel**: disabled — irrelevant for taker entry (no resting bid order placed)
- **Rationale**: Taker entry at ask eliminates passive adverse selection and ensures fill on the tick the spread condition is met. TTL=15 ticks matches the prior pilot (strat_20260417_0003) which was also a single-snapshot signal. TTL serves as a staleness gate if the ask price has moved after signal fire (engine latency: 5 ms ± 1 ms jitter). Bid-drop cancel applies only to resting bid limits — not applicable here.

## Exit Structure

### Profit Target

- **65.31 bps** (LIMIT SELL, resting) — corresponds to 2 ticks above entry ask price at 100 KRW/tick resolution
- Deviation from brief: **-17.3%** from optimal 79 bps (within the -20% maximum allowed by protocol)
- Rationale: 79 bps / 32.65 bps-per-tick = 2.42 ticks. Rounding up to 3 ticks (97.96 bps, +24%) would exceed the +20% deviation limit. Rounding down to 2 ticks (65.31 bps, -17.3%) stays within the -20% floor. 65.31 bps >> 21.0 bps round-trip cost, so the PT still covers fees with ample margin.

### Stop Loss

- **32.65 bps** (MARKET SELL, bid_px[0] reference) — 1 tick below entry price
- Deviation from brief: **+988.4%** from optimal 3 bps — STRUCTURAL CONCERN (tick-grid constraint, not discretionary)
- Rationale: The minimum physically realizable SL on 010140 is 1 tick = 32.65 bps. The brief's 3 bps SL was derived from continuous mid_ret quantiles and does not account for KRX tick discretization. Setting SL to 3 bps would never trigger before the market has already moved 1 full tick (32.65 bps), making the SL ineffective and creating sl_overshoot invariant violations on every stop. Using 1-tick SL is the only correct choice. This is identical in nature to the 042700 fix in strat_20260417_0003 where SL was raised from 3 bps to 33 bps (2-tick floor there, 1-tick floor here because 010140's tick is smaller in KRW but similar in bps given the lower price).
- **SL must monitor snap.bid_px[0], not snap.mid** (lesson_024). MARKET SELL fills at the best bid; using mid as reference understates realized loss by half the spread (17.5 bps on this symbol). Correct implementation: `unrealized_bps = (snap.bid_px[0] - entry_px) / entry_px * 10000`

### SL Guard

- **sl_guard_ticks = 5**: Do not check or trigger SL until 5 ticks have elapsed since entry fill. This prevents noise-triggered stops from spread bounce artifacts at entry. Lesson from strat_20260417_0003: the 5-tick guard prevented erroneous stops in normal mode but was missing from spec.yaml, causing strict-mode counterfactual to be invalid. For this iteration, sl_guard_ticks must be a formal spec.yaml parameter so InvariantRunner respects it.

### Trailing Stop

- **Enabled**
- **Activation**: 32.65 bps (1 tick profit) — trailing begins after price has moved 1 tick in our favor
- **Distance**: 32.65 bps (1 tick from peak) — lock in profit if price retraces 1 tick from its high
- Rationale: Brief exit_mix shows **59% of exits via trailing stop** — this is the dominant exit path. Omitting trailing (as in strat_20260417_0003) structurally deviates from the brief's EV assumption and suppresses realized PnL. Execution critique from iter 2 explicitly called this out as the highest-priority improvement. Activation at 1 tick (32.65 bps) is above the 19.5 bps round-trip minimum (activation >= RT cost constraint satisfied). Distance = activation = 1 tick: trail fires if price retraces to entry after touching +1 tick, locking in near-zero PnL before fees — this is conservative but prevents a winner from becoming a loser. The PT=65.31 bps (2-tick target) still acts as the ceiling; trailing will fire first if the position reaches +1 tick and then retraces before reaching +2 ticks.

## Position & Session

- **Lot size**: 2
- **Max entries per session**: 1
- **Max position per symbol**: 1
- **Rationale**: Lot size 2 is the minimum that amortizes fixed order submission costs. Prior execution critique (iter 2) noted that fee_pct=83% was primarily a function of avg_gross_bps being low, not of lot_size — scaling lot_size alone does not improve fee_pct ratio. Re-enabling trailing stop is the primary lever to improve avg_gross_bps. Keeping lot_size=2 for this pilot allows clean isolation of the trailing-stop contribution before scaling. Max entries=1 enforces single-position discipline and avoids the max_position_exceeded violations seen in iter 0 (strat_20260417_0001). The signal fires at the 95th-percentile spread level (entry_pct=5.72%), so multiple entries per session are unlikely but disallowed for safety.

## Fee Math

- Round-trip cost: **21.0 bps** (commission 1.5 bps each side + sell tax 18.0 bps)
- Profit target: 65.31 bps — **3.11x round-trip cost** (satisfactory)
- Break-even WR at these params: `32.65 / (65.31 + 32.65) * 100` = **33.3%**
- Brief WR: 50.34% — **17 percentage points above break-even** (healthy margin)
- Note: Win rate from brief (50.34%) reflects the continuous-bps exit model; realized WR may differ due to tick discretization raising the effective SL. With SL at 32.65 bps (10.9x the brief's 3 bps), fewer trades will be stopped out, which could raise WR — but it also means held losers will accumulate more drawdown before stopping. The trailing stop (59% exit share in brief) partially mitigates this by locking in gains before retracing to the SL.

## Implementation Notes for spec-writer

1. **Entry**: `entry_price_mode: "ask"`, `entry_ttl_ticks: 15`, `cancel_on_bid_drop_ticks: 0`
2. **SL reference**: SL must monitor `snap.bid_px[0]`, not `snap.mid`. Implementation:
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_px) / entry_px * 10000
   if ticks_since_entry >= sl_guard_ticks and unrealized_bps <= -stop_loss_bps:
       # submit MARKET SELL
   ```
3. **sl_guard_ticks**: Must be a formal `spec.yaml` param (`sl_guard_ticks: 5`). The InvariantRunner's `should_force_sell` must also respect this guard so strict-mode counterfactual is valid (lesson from iter 2 execution critique).
4. **Trailing stop state**: Track `peak_bid_px` since entry (update on each tick while in position). Fire trailing sell when `peak_bid_px - snap.bid_px[0] >= trailing_distance_bps / 10000 * entry_px` AND `peak_bid_px - entry_px >= trailing_activation_bps / 10000 * entry_px`.
5. **Spread gate**: Single symbol (010140) — no multi-symbol spread gate dict needed. If spec-writer adds a spread gate, floor = `100 / 30625 * 10000 * 1.5 = 48.98 bps` (1.5x tick floor).
6. **Time gate**: Block 09:00–09:30 (`entry_start_time_seconds: 34200`). entry_end_time_seconds: 46800 (13:00:00) per KRX session structure.
7. **Max position**: `max_position_per_symbol: 1` to prevent the max_position_exceeded violations from iter 0.

## Deviation from Brief Summary

| Parameter | Brief Optimal | Adopted | Deviation | Reason |
|-----------|--------------|---------|-----------|--------|
| pt_bps | 79.0 | 65.31 | -17.3% | Tick-grid constraint: round down from 2.42 → 2 ticks to stay within ±20% |
| sl_bps | 3.0 | 32.65 | +988.4% | STRUCTURAL CONCERN: 1-tick minimum physical floor; sub-tick SL impossible on KRX |
| trailing_activation | (implied by brief) | 32.65 | N/A | Set to 1-tick floor; brief exit_mix=59% TS mandates trailing be enabled |
| trailing_distance | (implied by brief) | 32.65 | N/A | 1-tick distance = symmetric with activation; conservative profit lock-in |

```json
{
  "name": "pilot_s2_010140_spread",
  "hypothesis": "When 010140 spread_bps crosses above its 95th-percentile threshold (17.498 bps), a temporary liquidity vacuum creates a mean-reverting mid-price drift exploitable long over a ~3000-tick horizon — rank-1 from signal_brief.",
  "entry_condition": "Enter LONG when spread_bps >= 17.498 (95th-percentile threshold, rank-1 from signal_brief for 010140)",
  "market_context": "010140 (KRX), any session regime; spread_bps itself proxies the regime — entry only when spread is at 95th-percentile width; block first 30 min (09:00–09:30) per KRX opening noise lesson",
  "signals_needed": ["spread_bps"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "strat_20260417_0001: max_position_exceeded on 010140; strat_20260417_0003: sl_guard_ticks needed + trailing stop mandatory (59% exit share in brief)",
  "signal_brief_rank": 1,
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": 15,
    "cancel_on_bid_drop_ticks": 0
  },
  "exit_execution": {
    "profit_target_bps": 65.31,
    "stop_loss_bps": 32.65,
    "trailing_stop": true,
    "trailing_activation_bps": 32.65,
    "trailing_distance_bps": 32.65
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 1
  },
  "structural_concern": "sl_bps deviation +988% from brief optimal (3 bps → 32.65 bps): tick-grid physical constraint on 010140 at ~30,625 KRW mid-price with 100 KRW tick size. Sub-tick SL is unenforceable on KRX. This is a mandatory adjustment, not discretionary.",
  "deviation_from_brief": {
    "pt_pct": -17.3,
    "sl_pct": 988.4,
    "rationale": "PT rounded down from 2.42 ticks to 2 ticks (65.31 bps, -17.3%) to stay within ±20% deviation limit. SL raised from 3 bps to 32.65 bps (+988%) because 010140's 100 KRW tick at ~30,625 KRW mid-price = 32.65 bps/tick — the brief's 3 bps SL is 0.09 ticks, physically sub-tick and unenforceable. Escalated as structural_concern per protocol."
  },
  "alpha_draft_path": "strategies/_drafts/pilot_s2_010140_spread_alpha.md",
  "execution_draft_path": "strategies/_drafts/pilot_s2_010140_spread_execution.md"
}
```
