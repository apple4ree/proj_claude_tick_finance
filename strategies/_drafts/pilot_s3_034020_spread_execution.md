---
stage: execution
name: pilot_s3_034020_spread
created: 2026-04-17
---

# Execution Design: pilot_s3_034020_spread

## Adverse Selection Assessment

**Low-to-moderate.** Entry is MARKET BUY at ask (taker), so there is no passive-fill adverse
selection risk. The position is filled immediately at the prevailing ask price. However, there
is post-fill price risk: the spread-widening event that triggered entry is transient (seconds),
so price may snap back to the prior level or beyond before the fill even settles. This is not
adverse selection in the classical passive sense — it is timing risk on a fleeting signal.

The OBI gate (obi_5 > 0.50) substantially reduces this timing risk by excluding the 2-tick
shock cluster (obi_5 ~ 0.03) where the spread widens due to sell-side pressure rather than
buy-side absorption. Entries that pass the gate have obi_5 averaging 0.73 — genuinely
bid-heavy, reducing the probability of post-fill reversal.

Structural note (lesson_024, pattern_sl_reference_price_and_per_symbol_spread_gate): for
long positions, SL must monitor `snap.bid_px[0]` not `snap.mid`. Since entry is MARKET BUY
at ask, `entry_mid` is recorded at fill-confirmation time. The bid-based SL correctly
reflects the actual MARKET SELL fill price and prevents the realized-loss-exceeds-nominal-SL
failure (strat_0028 historical: 50 bps nominal SL → 362 bps realized loss).


## Entry Order

- Price: ask (MARKET BUY)
- TTL: none — MARKET order fills immediately, TTL not applicable
- Bid-drop cancel: disabled — taker entry, no resting order to cancel
- Rationale: Alpha-designer specifies aggressive entry at ask because the spread-widening
  event is fleeting (compresses within seconds). A passive LIMIT at bid would have near-zero
  fill rate in this regime — by definition, bid is below ask and the mean-reversion bet is
  that ask will be repriced down, not that bid will be repriced up. MARKET BUY is the only
  mechanically sound entry for this signal type.


## Exit Structure

- Profit target: 79 bps (LIMIT SELL) — matches brief's optimal_exit.pt_bps exactly
- Stop loss: 9.5 bps (MARKET SELL) — MANDATORY upward deviation from brief's sl_bps=3
  (see Deviation from Brief section)
- Trailing stop: ENABLED (brief exit_mix: 56% trailing — primary exit mechanism)
  - Activation: 19.5 bps profit — round-trip cost threshold; trailing only engages after
    position is in net-profitable territory
  - Distance: 9.5 bps from peak bid — 1-tick distance; tight to preserve spread-compression
    gains before reversal

**Rationale:**

Brief's sl_bps=3 is physically unreachable. At 034020 mid ~107k KRW with tick=100 KRW,
the minimum achievable spread (and thus minimum price grid step) is:
  floor_bps = 100 / 107,000 * 10,000 = 9.35 bps per tick

A 3 bps SL cannot be represented on this tick grid — no fill occurs at 3 bps below entry
mid. The SL would either never trigger (bid never lands there) or trigger in a tick-skip
event that overshoots catastrophically. Setting SL at 9.5 bps = 1 tick, the minimum
physically representable SL for this symbol. This is a mandatory tick-size constraint
deviation (see Deviation from Brief section).

Trailing stop activation at 19.5 bps (= full round-trip cost) ensures trailing only
operates on genuine net-profit territory — if the trailing stop fires at activation, the
trade breaks even rather than losing. Trailing distance of 9.5 bps (1 tick) is intentionally
tight: the spread-compression hypothesis predicts a fast move of ~9-18 bps followed by
stabilization, not a sustained trend. Letting trailing distance be too wide (e.g., 30 bps)
would let a 1-tick reversal after compression consume all the gained bps.

PT=79 bps serves as an upside cap — only 9% of exits hit PT historically. The strategy's
EV depends on trailing exits (56%). PT is retained at brief's optimal value as a backstop.

**Win rate warning**: WR=34.93% is above the 30% weak-signal threshold. The nominal
break-even WR at these parameters is `sl / (pt + sl) = 9.5 / (79 + 9.5) = 10.7%`, which
appears very comfortable. However, this calculation assumes all exits are binary (PT or SL),
ignoring the 56% trailing exits which realize intermediate returns. The true effective WR
needed for profitability is empirically captured in the brief's sharpe=0.0501 — marginal
but positive. The 5-tick SL guard is essential: without it, the immediate-stop failure
from S2 (7/8 stops on 010140) would recur.


## Position & Session

- Lot size: 2
- Max entries per session: 3
- Rationale: 034020 at ~107k KRW/share; 2 lots = 214k KRW = 2.1% of 10M capital
  (well within 18% max-per-position constraint). Signal fires at ~6.5% of ticks after
  OBI gate — moderate frequency. Max 3 entries allows recovery from a failed entry without
  over-concentrating intraday. MARKET BUY has no TTL cancel to eat into entry count, but
  the signal condition can fire again after a position closes, so 3 entries is conservative
  but not overly restrictive.


## Fee Math

- Round-trip cost: 21.0 bps (engine actual: commission 1.5 bps × 2 + sell tax 18 bps)
- Trailing activation: 19.5 bps profit (entry net of buy-side commission ≈ 0.75 bps;
  setting at 19.5 bps is conservative — guarantees profitable territory before trailing)
- Break-even WR at binary PT/SL params only: 9.5 / (79 + 9.5) = 10.7%
- Effective profitability gate: sharpe > 0 requires EV > 0; brief's EV = +1.538 bps
  post-21 bps fee. This is marginal — selectivity of OBI gate is critical to protect it.
- Required edge: WR 34.93% (brief empirical); actual realized WR must stay above 30% or
  the signal is flagged as weak.


## Deviation from Brief

| Parameter | Brief optimal | Used | Pct deviation | Reason |
|---|---|---|---|---|
| sl_bps | 3.0 | 9.5 | +216.7% | Tick-size constraint: 034020 tick=100 KRW at ~107k KRW mid → 1 tick = 9.35 bps; brief's 3 bps is sub-tick and physically unreachable on this grid. Minimum viable SL = 1 tick = 9.5 bps. |
| pt_bps | 79.0 | 79.0 | 0% | No deviation. PT is already above 2x round-trip cost (79 > 2*21=42) and rarely hit (9%); no adjustment warranted. |

**Structural concern — SL deviation exceeds 20% cap:**
The sl_bps deviation (+216.7%) far exceeds the protocol's ±20% allowed range. This is not
an execution judgment call but a physical impossibility — the tick grid forbids a 3 bps SL
on 034020. The brief's sl_bps=3 reflects the optimizer's statistical ideal under a
continuous-price assumption; the actual market is discretized at ~9.35 bps per tick.

Consequence for signal economics: the wider SL (9.5 vs 3 bps) increases the stop-loss exit
size (each SL hit is worse in bps). However, the 5-tick guard and trailing mechanism are
designed to reduce the SL hit rate — the trailing stop activating at 19.5 bps means any
trade that moves favorably even 1 tick past activation will exit via trailing rather than SL.
The brief's 33% SL exit rate at sl_bps=3 will shift under sl_bps=9.5 (fewer marginal SL
triggers, but larger loss per SL). Net EV impact is uncertain without re-running the brief
at 9.5 bps — this is an inherent constraint from the tick grid and cannot be resolved by
execution design alone.


## Implementation Notes for spec-writer

1. **Entry type**: MARKET BUY (order_type=MARKET, side=BUY). No resting limit at entry.
   Entry price = `snap.ask_px[0]` at signal tick. Record `entry_mid = snap.mid` and
   `entry_ask = snap.ask_px[0]` at fill-confirmation time.

2. **SL reference price**: MUST use `snap.bid_px[0]`, not `snap.mid`.
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
   if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
       # submit MARKET SELL
   ```
   This is mandatory per pattern_sl_reference_price_and_per_symbol_spread_gate and
   lesson_024. Using `snap.mid` risks realized loss far exceeding nominal SL=9.5 bps.

3. **sl_guard_ticks=5**: SL condition cannot fire at tick 0. This prevents immediate
   stop-outs from the spread already present at the moment of fill.

4. **Trailing stop state**: Track per-symbol:
   - `peak_bid[sym]`: updated every tick while in position to `max(peak_bid[sym], snap.bid_px[0])`
   - `trailing_activated[sym]`: True when `(peak_bid[sym] - entry_mid) / entry_mid * 10000 >= 19.5`
   - Trailing trigger: when `trailing_activated[sym]` AND
     `(snap.bid_px[0] - peak_bid[sym]) / entry_mid * 10000 <= -9.5`
     → submit MARKET SELL

5. **Orphaned limit cancel**: After any MARKET SELL (stop or trailing), if a LIMIT SELL
   (profit-target) is resting, emit CANCEL before the MARKET SELL in the order list.
   Per pattern_stop_exit_leaves_orphaned_resting_limit, the CANCEL must precede MARKET SELL.

6. **PT resting LIMIT**: Post LIMIT SELL at `entry_ask * (1 + 79/10000)` immediately after
   fill confirmation. Cancel it on any non-PT exit (stop, trailing, EOD).

7. **Per-symbol spread gate**: This is single-symbol (034020 only), so no multi-symbol
   dict required. However, note that 034020's spread floor is ~9.35 bps — the strategy's
   entry condition (spread_bps >= 9.501) is already above this floor by definition.

8. **Opening blackout**: No entries before 09:30 KST (1800 seconds from session open).
   The alpha condition already specifies this; spec must enforce `entry_start_time_seconds=1800`.

9. **needs_python**: alpha-designer marked `needs_python: false` (pure snapshot comparison).
   However, the trailing stop state management (peak tracking, activation flag) requires
   per-tick stateful logic. Spec-writer should confirm: if the engine's built-in trailing
   stop mechanism handles `trailing_activation_bps` and `trailing_distance_bps` natively,
   then `needs_python: false` is valid. If engine trailing requires Python implementation,
   set `needs_python: true`.

```json
{
  "name": "pilot_s3_034020_spread",
  "hypothesis": "When 034020 spread_bps exceeds p95 (9.501 bps, upper tail of 1-tick regime) and obi_5 confirms bid-side pressure (>0.50), the transient liquidity gap resolves upward as market-makers reprice — rank-1 from signal_brief, ev_bps=1.538 post-fee.",
  "entry_condition": "spread_bps >= 9.501 AND obi(depth=5) > 0.50 AND time > 09:30 KST; OBI gate excludes the 2-tick shock cluster (obi_5~0.03) that accounts for 10% of above-threshold entries and has no directional edge",
  "market_context": "034020 mid 104k-112k KRW, effective tick 100 KRW (data-derived, not KRX-band rule), 1-tick spread ~9.3 bps; entry fires in the upper tail of 1-tick spread regime (9.5-9.6 bps) where obi_5 averages 0.73 (bid-heavy); 2-tick spread events (18+ bps, obi_5~0.03) explicitly excluded; full session 09:30-15:30 KST",
  "signals_needed": ["spread_bps", "obi(depth=5)"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_003_spread_bps_threshold_is_direction_agnostic_obi_gate_required",
  "signal_brief_rank": 1,
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": null,
    "cancel_on_bid_drop_ticks": null
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 9.5,
    "trailing_stop": true,
    "trailing_activation_bps": 19.5,
    "trailing_distance_bps": 9.5
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 3
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 216.7,
    "rationale": "sl_bps raised from brief's 3 to 9.5 bps (+216.7%) due to mandatory tick-size constraint: 034020 tick=100 KRW at ~107k KRW mid yields 1 tick = 9.35 bps, making sl_bps=3 physically unreachable on the price grid. 9.5 bps is the minimum viable 1-tick SL. Deviation exceeds 20% cap — flagged as structural_concern. pt_bps unchanged at 79 (0% deviation)."
  },
  "alpha_draft_path": "strategies/_drafts/pilot_s3_034020_spread_alpha.md",
  "execution_draft_path": "strategies/_drafts/pilot_s3_034020_spread_execution.md"
}
```
