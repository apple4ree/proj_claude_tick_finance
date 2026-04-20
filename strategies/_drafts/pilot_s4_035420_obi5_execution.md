---
stage: execution
name: pilot_s4_035420_obi5
created: 2026-04-17
symbol: 035420
signal_brief_rank: 1
---

# Execution Design: pilot_s4_035420_obi5

## Tick Size Verification

035420 (NAVER) at ~222,850 KRW mid. Empirical check from `035420_features.csv` (2000 ticks):
- Mode spread_px = 500 KRW (1079/2000 = 54% of ticks)
- Implied tick from spread_bps * mid / 10000 = 500 KRW in 99.3% of samples
- **Confirmed: tick = 500 KRW = 22.44 bps/tick at current mid**

This is the 100k–500k KRW KRX band (tick=500 KRW). The initial constraint note mentioning "verify from data" is resolved: 500 KRW / 222,850 KRW = 22.44 bps per tick.

## Adverse Selection Assessment

**Severity: LOW-MODERATE** — entry is LIMIT at ask (aggressive/taker-side), not passive BID.

Ask-side entry does not suffer the structural adverse selection of passive BID fills (where the
book has moved against you to reach your price). Instead:
- LIMIT at ask fills only when the ask is hit by a seller OR an aggressive buyer takes us out
- With TTL=1 tick, if the order is not filled immediately, it is cancelled before the OBI
  can decay meaningfully (lesson_20260417_004: OBI decayed 0.58→0.56 during 5ms MARKET BUY
  latency window)
- Risk is slippage if ask moves up before fill — but this is favorable (we buy lower than
  intended rather than higher)
- No bid-drop cancel needed: we are not resting passively; TTL=1 enforces immediacy

**Lesson references applied:**
- lesson_20260417_004: LIMIT at ask with TTL=1 chosen specifically to prevent 5ms OBI flip
  that occurs during MARKET BUY processing
- lesson_20260417_001: aggressive entry at ask was the recommended fix to fill-rate problem

## Entry Order

- **Price**: `ask` (LIMIT at best ask — marketable limit, taker-side)
- **TTL**: 1 tick (cancel immediately if not filled; ensures OBI check is current at fill time)
- **Bid-drop cancel**: disabled (irrelevant for ask-side entry; TTL=1 provides the same
  immediacy protection)
- **Rationale**: lesson_20260417_004 established that MARKET BUY creates a 5ms window during
  which OBI can flip from >= threshold to < threshold. LIMIT at ask with TTL=1 narrows this
  window to a single tick event: either the ask is taken immediately or we cancel and wait for
  the next signal fire. This is the cleanest ask-gate implementation consistent with
  lesson_004's recommendation.

## Exit Structure

### Brief Baseline (rank-1 optimal_exit)
- pt_bps = 79, sl_bps = 3, win_rate_pct = 62.93%
- exit_mix: pt=0%, sl=13%, ts=85%

### Tick-size Constraint on SL

Brief SL of 3 bps is **sub-tick** for 035420:
- 1 tick = 22.44 bps; 3 bps < 22.44 bps — no bid level exists at 3 bps below entry
- The invariant checker would always flag sl_overshoot (lesson_20260417_001 structural finding)
- **SL raised to 22.44 bps (1 tick) — mandatory tick-size alignment, not a design choice**
- This is a +648% deviation from brief's sl_bps=3, but it is a physical constraint:
  the tick grid cannot represent a 3 bps stop on this symbol

**SL deviation rationale (tick-size constraint):** brief sl_bps=3 is below the 22.44 bps/tick
floor for 035420. A 3 bps SL is unreachable; the engine would overshoot to the first
available tick level regardless. Setting sl_bps=22.44 eliminates spurious invariant violations
and reflects the true minimum risk per trade.

### Exit Mix Flag

PT=0% in exit_mix: the profit target (79 bps = ~3.5 ticks) is rarely reached. The strategy
exits predominantly via trailing stop (85%) and occasionally via hard stop (13%). No time-stop
exit was included in the brief's simulation horizon. This means:
- A resting LIMIT SELL at 79 bps is correct to set but will almost never fill
- The trailing stop is the primary exit mechanism — its parameters are critical
- **Do NOT set PT to 2x brief (158 bps) — it would never fill and removes the resting limit
  as a backstop**

### Parameters

- **Profit target**: 79.0 bps (LIMIT SELL) — 0% deviation from brief
  (3.5 ticks at 22.44 bps/tick; the resting limit provides ceiling protection for outlier wins)
- **Stop loss**: 22.44 bps (MARKET SELL) — +648% deviation from brief
  (tick-size forced; brief's 3 bps is sub-tick and physically unreachable)
- **Trailing stop**: ENABLED — brief exit_mix ts=85% makes this the primary exit path
  - **Activation**: 22.44 bps profit (1 tick of profit before trailing engages)
    - This equals the round-trip cost ceiling (21 bps RTC; activation set to 1 full tick
      at 22.44 bps to ensure we are above break-even before trailing takes over)
  - **Distance**: 22.44 bps from peak (1 tick trailing distance)
    - Setting distance = SL ensures trailing is never looser than the hard stop
    - At peak+1 tick, a 1-tick pullback triggers the trailing exit — conservative but
      consistent with brief's ts-dominant exit distribution
- **Rationale**: WR=62.93% >> break-even WR of 22.1% (SL=22.44, PT=79). Even with the
  enlarged SL (tick constraint), the strategy has a >40pp cushion above break-even.
  Trailing activation at 22.44 bps ensures we bank at least 1 bps profit (22.44 - 21.0 RTC)
  before trailing engages.

### SL Reference Price

Per lesson_20260415 (pattern_sl_reference_price_and_per_symbol_spread_gate):
**SL must monitor `snap.bid_px[0]`, not `snap.mid`.**

At 035420's 22.44 bps/tick, spread = 1 tick = 22.44 bps. Using mid-price SL would understate
realized loss by ~11 bps (half-spread), causing the SL to fire "on time" by mid measure but
realize a loss of ~33 bps (1.5 ticks) after MARKET SELL walks the book to bid.

Correct implementation:
```python
unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
    # submit MARKET SELL
```

## Position & Session

- **Lot size**: 2
  - Minimum to amortize 21 bps round-trip fee across two units
  - Signal selectivity is 5.34% of ticks (~1 signal per 19 ticks); multiple fires per session
    are likely, making lot=2 the correct floor without oversizing
- **Max entries per session**: 2
  - TTL=1 tick means cancels are instant — a rejected fill still consumes the signal event
  - Allowing 2 entries provides a recovery path if the first is cancelled (no fill)
  - 3 entries would risk overtrading if signals cluster; 2 is the balance point
  - The 3000-tick signal horizon is long-duration: one successful entry per session is ideal,
    the second slot is a safety valve

## Fee Math

- Round-trip cost: 21.0 bps (commission 1.5 bps × 2 + sell tax 18.0 bps)
- Effective SL at tick grid: 22.44 bps
- Profit target: 79.0 bps
- Break-even WR at these params: 22.44 / (79.0 + 22.44) × 100 = **22.1%**
- Brief WR: 62.93% — margin above BE is +40.8pp (very comfortable)
- Trailing activation: 22.44 bps (>= 21.0 bps RTC — position is above break-even when
  trailing engages)

## Spread Gate for 035420

Single-symbol strategy; no multi-symbol dict required. However, spec-writer should note:
- Tick floor: 22.44 bps (1 tick at current mid)
- Viable spread gate: >= 33.65 bps (1.5 × tick floor)
- If a spread gate is applied: use 33.65 bps as minimum to avoid filtering out valid ticks
  that happen to sit at the 1-tick spread (54% of all ticks)
- Recommended: no hard spread gate for this single-symbol strategy — OBI threshold at 95th
  percentile already provides sufficient entry selectivity (5.34% entry rate)

## Implementation Notes for spec-writer

1. **Entry price = ask**: Use `snap.ask_px[0]` as limit price. Submit as LIMIT order.
   TTL=1 tick means cancel after next LOB update if unfilled.

2. **SL must monitor `snap.bid_px[0]`, not `snap.mid`**:
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
   if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
       submit MARKET SELL
   ```
   Reference: pattern_sl_reference_price_and_per_symbol_spread_gate

3. **sl_guard_ticks=5** in spec: prevents immediate stop-out after ask-fill when bid is
   already 1 tick below ask (spread = 1 tick). Without the guard, the SL at 22.44 bps
   would fire on the very first tick after fill (bid is 22.44 bps below mid ≈ 22.44 bps
   below fill price). Guard of 5 ticks gives the position minimal time to move.

4. **Trailing stop implementation**:
   - Track `peak_mid` since entry (update on every tick while position is open)
   - Activate trailing when `(peak_mid - entry_mid) / entry_mid * 10000 >= 22.44`
   - Once active, trigger exit when `(peak_mid - snap.bid_px[0]) / entry_mid * 10000 >= 22.44`
   - Use bid_px[0] for trailing monitor (same reason as SL — exit fills at bid)

5. **Gate evaluation order** (lesson_20260417_004 fix):
   Call `update_state()` BEFORE evaluating any gate condition in SIGNAL_REGISTRY.
   Order: update_state → time_gate → trend_filter → volume_gate → obi_gate → submit_entry

6. **Trend filter implementation**:
   ```python
   mid_ret_50 = (snap.mid - mid_history[-50]) / mid_history[-50] * 10000
   if mid_ret_50 <= 0:
       return  # block entry in downtrend
   ```

7. **Volume gate**: compute session median of krw_turnover(50) incrementally; gate fires only
   when current 50-tick turnover > running session median (not pre-computed static value).

8. **Per-symbol spread gate note**: single symbol — no SPREAD_GATES dict needed. If this
   strategy is later expanded to multi-symbol, apply per-symbol floor computation.

```json
{
  "name": "pilot_s4_035420_obi5",
  "hypothesis": "rank-1 from signal_brief: obi_5 >= 0.644 on 035420 captures sustained 5-level buy-side conviction that predicts a 3000-tick directional move with EV 6.2 bps after 21 bps round-trip fee",
  "entry_condition": "time >= 09:30 KST AND 50-tick mid_return_bps > 0 (trend filter) AND krw_turnover(50) above session median (volume gate) AND obi(depth=5) >= 0.644 AND no open position",
  "market_context": "035420 (NAVER), mid-tier liquidity, flat-to-upward intraday regime only, post-09:30 session, volume-confirmed order book pressure",
  "signals_needed": ["obi(depth=5)", "mid_return_bps(lookback=50)", "krw_turnover(lookback=50)", "mid"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_004_strategy_py_gate_enforcement_bugs_nullify_obi_spread_filters",
  "signal_brief_rank": 1,
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": 1,
    "cancel_on_bid_drop_ticks": null
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 22.44,
    "trailing_stop": true,
    "trailing_activation_bps": 22.44,
    "trailing_distance_bps": 22.44
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 2
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 648.0,
    "rationale": "PT held at 79 bps (0% deviation). SL raised from 3 bps to 22.44 bps (+648%) due to tick-size constraint: 035420 tick = 500 KRW = 22.44 bps/tick at ~222,850 KRW mid (confirmed from empirical features data). Brief sl_bps=3 is sub-tick and physically unreachable; the minimum representable stop on this symbol's tick grid is 22.44 bps. Break-even WR rises to 22.1% but brief WR of 62.93% provides a +40.8pp buffer — the edge is more than sufficient to absorb this tick-forced SL widening."
  },
  "alpha_draft_path": "strategies/_drafts/pilot_s4_035420_obi5_alpha.md",
  "execution_draft_path": "strategies/_drafts/pilot_s4_035420_obi5_execution.md"
}
```
