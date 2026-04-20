---
stage: execution
name: 005930_obi5
created: 2026-04-17
symbol: 005930
price_ref_krw: 80000
---

# Execution Design: 005930_obi5 (Samsung, obi_5 >= 0.55)

## Adverse Selection Assessment

obi_5 >= 0.55 is a passive BID LIMIT entry triggered by order-book imbalance. Adverse selection
risk is HIGH: passive fills occur when sellers are active (price moving against buyer). The signal
is fleeting (<30 ticks for OBI spikes), so TTL must be short. Iteration 1 (strat_0002) confirmed
OBI had decayed to 0.56 < 0.58 threshold by fill time — TTL and bid-drop cancel are mandatory.

## STRUCTURAL CONCERN: Brief SL is Sub-Tick

brief optimal_exit.sl_bps = 3.0 bps. At 80,000 KRW with tick size 100 KRW:
- 1 tick = 100 / 80000 * 10000 = 12.50 bps
- 3 bps in KRW = 80000 * 0.0003 = 24 KRW < 100 KRW (minimum price increment)

The brief SL of 3 bps is physically unrepresentable on KRX. Any SL below 12.50 bps triggers
at the same grid point as a 12.50 bps SL. Deviation from brief: +316.7%, far exceeding the 20%
cap. This is escalated as a structural_concern — the brief's optimal_exit was computed against
a continuous return distribution, not the KRX tick grid.

Minimum viable SL = 1 tick = 12.50 bps.

## Additional Flags

- PT exit rate = 7% (< 10% threshold): strategy will rely almost entirely on time_stop exits.
  PT=79 bps will rarely be reached; most exits are time_stop or SL. Review time_stop calibration.
- Win rate from brief = 31.41% (rank-2 vol_delta_10 as proxy); obi_5 not in brief top-10.
  Win rate BELOW 30% warning threshold. Alpha-designer should verify obi_5 edge independently.
- n_viable_in_top = 0: ALL 10 signals for 005930 have EV < 0 after 21 bps fee. Brief
  recommendation: "No viable signal." This is a pre-existing structural concern.

## Entry Order

- Price: bid (passive LIMIT at best bid)
- TTL: 30 ticks (OBI signal is fleeting; decay confirmed by iteration 1)
- Bid-drop cancel: 2 ticks (100 KRW * 2 = 200 KRW drop from submission bid)
- Rationale: High adverse selection risk with passive fill. 30-tick TTL prevents stale
  fill into decayed OBI. 2-tick bid-drop cancel screens for aggressive selling pressure
  that would indicate adverse information. Small TTL also allows max_entries_per_session=2
  for recovery if first attempt cancels.

## Exit Structure

- Profit target: 79.0 bps (LIMIT SELL) — brief baseline, no deviation
- Stop loss: 12.50 bps (MARKET SELL) — raised from brief's 3 bps; 1-tick minimum constraint
- Trailing stop: enabled
  - Activation: 25.0 bps profit (after round-trip cost of 21.0 bps cleared)
  - Distance: 12.50 bps from peak (1 tick, matches SL width)
- Rationale: PT=79 hit rate is only 7%; trailing stop captures partial profits on the 44%
  time_stop path. Activation at 25 bps ensures trailing only engages when position is net
  profitable after fees. Distance = 1 tick is the minimum granularity on KRX.
- SL must monitor snap.bid_px[0], NOT snap.mid (lesson_024: mid-to-bid gap caused 362 bps
  realized loss vs 50 bps nominal SL in strat_0028).

## Position & Session

- Lot size: 2
- Max entries per session: 2
- Rationale: TTL=30 ticks means first attempt may cancel; allow one retry. Lot=2 amortizes
  fixed fee components. With n_viable_in_top=0 on 005930, limit exposure.

## Fee Math

- Round-trip cost: 21.0 bps (commission 1.5 bps x2 + sell tax 18.0 bps)
- Break-even WR at PT=79, SL=12.50: 12.50 / (79 + 12.50) * 100 = 13.7%
- Brief win rate (rank-2 proxy): 31.41% — exceeds break-even by 17.7 pp
- Note: Win rate above break-even does NOT guarantee profitability given EV < 0 from brief.
  The brief explicitly flags this symbol as non-viable at 21 bps fee.

## Implementation Notes for spec-writer

1. SL must monitor snap.bid_px[0], not snap.mid:
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
   if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
       # submit MARKET SELL
   ```
2. Per-symbol spread gate (not universal):
   ```python
   SPREAD_GATES = {"005930": 15.0}  # floor = 12.50 bps * 1.5 = 18.75; use 15.0 as light gate
   ```
   Actually floor * 1.5 = 18.75 bps; set gate = 18.75 bps minimum.
3. TTL cancel: track bid_px at submission time; cancel if bid drops 2 ticks (200 KRW).
4. Trailing stop: track peak_mid since entry; sell MARKET if (peak_mid - snap.bid_px[0]) /
   entry_mid * 10000 >= trailing_distance_bps AND unrealized_bps >= trailing_activation_bps.
5. sl_guard_ticks = 5: do not trigger SL within first 5 ticks of entry (prevents immediate-fill
   noise from causing instant exit; consistent with engine 5ms jitter).
6. STRUCTURAL CONCERN (escalate to alpha-designer): 005930 has n_viable_in_top=0 at 21 bps fee.
   Brief recommends against trading this symbol. Proceed only with explicit override from alpha-designer.

## Deviation from Brief

- PT: 0.0% (79.0 bps → 79.0 bps, no change)
- SL: +316.7% (3.0 bps → 12.50 bps) — STRUCTURAL CONCERN, tick-size constraint; 24 KRW < 100 KRW tick

```json
{
  "name": "005930_obi5",
  "hypothesis": "obi_5 >= 0.55 rank-2 threshold signals sustained buy-side pressure sufficient to overcome 21 bps round-trip cost on Samsung Electronics",
  "entry_condition": "obi_5 >= 0.55",
  "market_context": "005930 KRX, price ~80000 KRW, tick=100 KRW, fee=21 bps",
  "signals_needed": ["obi_5"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "momentum",
  "multi_date": true,
  "parent_lesson": "lesson_20260415_024",
  "structural_concern": "n_viable_in_top=0 for 005930 at 21 bps fee; brief SL=3 bps is sub-tick (24 KRW < 100 KRW tick); SL raised to 12.50 bps (1 tick minimum); deviation +316.7% exceeds 20% cap — mandatory escalation",
  "entry_execution": {
    "price": "bid",
    "ttl_ticks": 30,
    "cancel_on_bid_drop_ticks": 2
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 12.5,
    "trailing_stop": true,
    "trailing_activation_bps": 25.0,
    "trailing_distance_bps": 12.5
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 2
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 316.7,
    "rationale": "Brief SL=3 bps is physically sub-tick at 80000 KRW (24 KRW < 100 KRW tick size). Minimum representable SL is 1 tick = 12.50 bps. This is a tick-size structural constraint, not a discretionary adjustment. Deviation exceeds 20% cap; escalated as structural_concern."
  },
  "sub_tick_check": true,
  "alpha_draft_path": "strategies/_drafts/005930_obi5_alpha.md",
  "execution_draft_path": "strategies/_drafts/005930_obi5_execution.md"
}
```
