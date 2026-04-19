---
stage: execution
name: 035420_spread15_rank2
created: 2026-04-17
symbol: 035420
signal_brief_rank: 2
---

# Execution Design: 035420 spread_bps >= 15 (rank-2)

## Tick Size Verification

035420 (NAVER) at 210,000 KRW. KRX band 100k–500k KRW => tick = 500 KRW.
- tick_bps = 500 / 210,000 * 10,000 = **23.81 bps/tick**
- Prior iteration (pilot_s4) confirmed mode spread_px = 500 KRW at ~222,850 KRW; now at 210,000 the tick is unchanged (500 KRW) but bps is slightly wider.

## sub_tick_check

Brief rank-2 optimal_exit: sl_bps = 3. At 210,000 KRW mid:
- 1 tick = 23.81 bps
- 3 bps < 23.81 bps => **sub-tick: True**
- A 3 bps SL is physically unreachable on the tick grid. The nearest representable stop is 1 tick = 23.81 bps.
- This is a structural constraint (not a design choice). sl_actual = 23.81 bps.

## Adverse Selection Assessment

**Severity: LOW-MODERATE** — signal is spread_bps >= threshold (wide-spread condition). A large spread indicates thin liquidity or price uncertainty. Entry should be at ask (marketable LIMIT) to avoid passive adverse selection. With TTL=1 tick, OBI decay during 5ms MARKET BUY latency is blocked (lesson_20260417_004).

Spread widening as entry trigger: when spread is wide, the book is temporarily imbalanced. Entry at ask captures the ask while liquidity is thin. Risk: spread may widen further, meaning filled entry is already behind mid. TTL=1 mitigates staleness.

Note: brief threshold is 23.01 bps (p95). User-specified threshold of >= 15 bps is more permissive (lower selectivity). This increases entry frequency but reduces signal quality. The rank-2 signal has win_rate_pct = 60.67% at p95; at a 15 bps gate the WR will be lower. Flag for alpha-designer: consider tightening to brief threshold (23.01 bps) for better signal quality.

## Entry Order

- Price: `ask` (LIMIT at best ask, marketable, taker-side)
- TTL: 1 tick — cancel if not filled immediately; OBI/spread condition must still hold at fill
- Bid-drop cancel: disabled (TTL=1 provides equivalent immediacy; ask-side entry not subject to passive adverse selection)
- Rationale: lesson_20260417_004 — MARKET BUY creates a 5ms window where spread condition may have resolved. LIMIT at ask with TTL=1 enforces contemporaneous fill.

## Exit Structure

### Brief Baseline (rank-2 optimal_exit)
- pt_bps = 79, sl_bps = 3, win_rate_pct = 60.67%
- exit_mix: pt=0%, sl=26%, ts=72%

### PT Flag
PT=0% in exit_mix: the 79 bps profit target is rarely hit at the 3000-tick horizon. Primary exit is trailing stop (72%) and hard stop (26%). The resting LIMIT SELL at 79 bps acts as a ceiling backstop only. Do NOT raise PT to 2x brief (158 bps) — it would be phantom.

### SL: Tick-size Forced Raise
- Brief sl_bps = 3 is sub-tick (3 < 23.81 bps/tick at 210,000 KRW)
- Forced to 1 tick = **23.81 bps** (+693.7% deviation — physical constraint)
- sl_guard_ticks = 5: after ask-fill, bid is immediately 23.81 bps below ask (1-tick spread). Without a guard, SL fires on tick 1. Guard of 5 ticks gives the position minimal time to move.

### Trailing Stop
- Brief exit_mix ts=72% => trailing is primary exit path
- Activation: 23.81 bps profit (>= 21.0 bps RTC; position is above break-even before trailing engages)
- Distance: 23.81 bps from peak bid (equals SL; trailing never looser than hard stop)

### Parameters
- Profit target: **79.0 bps** (0% deviation — brief optimal, ceiling backstop)
- Stop loss: **23.81 bps** (+693.7% deviation — tick-size forced; 3 bps sub-tick at 210k KRW)
- Trailing stop: ENABLED (ts=72% primary exit)
  - Activation: 23.81 bps
  - Distance: 23.81 bps from peak

### SL Reference Price
SL must monitor `snap.bid_px[0]`, not `snap.mid` (lesson_024 / pattern_sl_reference_price_and_per_symbol_spread_gate). At 035420, spread = 1 tick = 23.81 bps. Using mid would understate realized loss by ~12 bps (half-spread).

```python
unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
    # submit MARKET SELL
```

## Position & Session

- Lot size: 2 (minimum to amortize 21 bps round-trip)
- Max entries per session: 2 (TTL=1 cancel rate is high with wide-spread signal; second slot as recovery)

## Fee Math

- Round-trip cost: 21.0 bps (commission 1.5 × 2 + tax 18.0)
- SL at tick grid: 23.81 bps
- Profit target: 79.0 bps
- Break-even WR: 23.81 / (79.0 + 23.81) × 100 = **23.16%**
- Brief WR: 60.67% — margin above BE: +37.51pp (comfortable despite tick-forced SL widening)
- Trailing activation: 23.81 bps >= 21.0 bps RTC (above break-even before trailing engages)

## Spread Gate Note

Spread gate floor for 035420: 23.81 bps (1 tick at 210k KRW). If user threshold is 15 bps, entries will fire when spread is between 15–23 bps, which is actually sub-tick spread territory (impossible at this tick size). In practice spread_bps >= 15 at this symbol means spread = 1 tick (23.81 bps) since that is the minimum non-zero spread. The signal effectively fires whenever spread widens to exactly 1 tick. The 15 bps threshold is a no-op filter (always true when spread > 0).

**Structural concern**: signal threshold 15 bps < tick floor 23.81 bps. The threshold is always satisfied whenever spread >= 1 tick. This converts a selective signal into a near-always-on condition. Recommend raising threshold to brief's 23.01 bps or the tick floor (23.81 bps). Escalated for alpha-designer review.

## Implementation Notes for spec-writer

1. Entry price = `snap.ask_px[0]`, LIMIT order, TTL=1 tick.
2. SL must monitor `snap.bid_px[0]`, not `snap.mid`.
3. sl_guard_ticks=5: no SL check for first 5 ticks after fill.
4. Trailing tracks `peak_bid = max(snap.bid_px[0])` since entry; triggers when `(peak_bid - snap.bid_px[0]) / entry_mid * 10000 >= 23.81` after activation.
5. Trailing activation: `(peak_bid - entry_ask) / entry_mid * 10000 >= 23.81`.
6. Per-symbol spread gate dict not required (single symbol). If multi-symbol: `SPREAD_GATES = {"035420": 35.7}` (1.5x tick floor).

```json
{
  "name": "035420_spread15_rank2",
  "hypothesis": "rank-2 from signal_brief: spread_bps >= 15 on 035420 captures wide-spread liquidity imbalance that predicts 3000-tick directional move; brief optimal_exit pt=79, sl=3 (sl sub-tick, forced to 23.81)",
  "entry_condition": "time >= 09:30 KST AND spread_bps >= 15 AND no open position",
  "market_context": "035420 (NAVER), mid-tier liquidity, spread-widening regime, post-09:30 session",
  "signals_needed": ["spread_bps", "mid"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_004_strategy_py_gate_enforcement_bugs_nullify_obi_spread_filters",
  "signal_brief_rank": 2,
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": 1,
    "cancel_on_bid_drop_ticks": null
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 23.81,
    "trailing_stop": true,
    "trailing_activation_bps": 23.81,
    "trailing_distance_bps": 23.81
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 2
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 693.7,
    "rationale": "PT held at 79 bps (0% deviation). SL raised from 3 bps to 23.81 bps (+693.7%) due to tick-size constraint: 035420 tick = 500 KRW = 23.81 bps/tick at 210,000 KRW mid. Brief sl_bps=3 is sub-tick and physically unreachable. Minimum representable stop on tick grid is 23.81 bps. Break-even WR rises to 23.16% vs brief WR 60.67%, margin +37.51pp — edge is sufficient to absorb tick-forced SL widening. Structural concern: user threshold 15 bps < tick floor 23.81 bps — threshold is effectively always-on; recommend raising to 23.01 bps (brief p95) or 23.81 bps (tick floor)."
  },
  "structural_concern": "signal_threshold_15_bps_is_below_tick_floor_23.81_bps: spread_bps >= 15 fires whenever spread >= 1 tick (always true for any non-zero spread on this symbol). This is equivalent to no spread gate. Alpha-designer should raise threshold to >= 23.81 bps (tick floor) or use brief's p95 threshold of 23.01 bps.",
  "alpha_draft_path": "strategies/_drafts/035420_spread15_rank2_alpha.md",
  "execution_draft_path": "strategies/_drafts/035420_spread15_rank2_execution.md"
}
```
