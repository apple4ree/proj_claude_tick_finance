---
stage: execution
name: smoke_042700_obi5
created: 2026-04-17
---

# Execution Design: smoke_042700_obi5

## Adverse Selection Assessment

**Risk level: MODERATE-HIGH.**

Entry is a passive BID LIMIT on a snapshot OBI spike. The 042700 signal fires at the 95th-percentile OBI event — a moment of extreme buy-side depth dominance. However, passive fills at bid are structurally adversely-selected: the order fills precisely when price is moving *down* to the bid. The OBI spike may be real signal or may represent a fleeting imbalance that reverses before fill completes.

Mitigations applied:
- TTL of 30 ticks: OBI spike is a snapshot signal, not a regime. If not filled within ~30 ticks the signal has decayed.
- Bid-drop cancel of 3 ticks: if bid falls 3 ticks (≈49 bps at 042700's 500 KRW tick size) after submission, the fill would be at a distressed price — cancel.

## Entry Order

- **Price**: bid (passive LIMIT at best bid)
- **TTL**: 30 ticks — OBI spike is fleeting (snapshot signal); if not filled within 30 ticks, the imbalance condition has decayed and fill would be adversely timed
- **Bid-drop cancel**: 3 ticks — 042700 tick size = 500 KRW at mid ~308,000 KRW; 3 ticks = ~49 bps drop, signaling directional sell pressure post-submission; cancel to avoid toxic fill
- **Rationale**: OBI snapshot signals are fleeting by nature (lesson_20260414_017 warns against transition-based signals; snapshot at 95th pct is better but still degrades fast). Short TTL + bid-drop cancel preserves fill quality at the cost of some fill rate. For a smoke test, this conservative stance is correct.

## Exit Structure

- **Profit target**: 79 bps (LIMIT SELL) — from brief baseline, 0% deviation; physically realizable at ~5 ticks
- **Stop loss**: 21.0 bps (MARKET SELL) — STRUCTURAL CONCERN: see rationale below
- **Trailing stop**: disabled
  - Activation: N/A
  - Distance: N/A
- **Rationale**:

  **SL structural concern — tick size constraint forces >20% deviation from brief:**

  Brief's optimal SL = 3 bps. At 042700's price level (~308,000 KRW) and KRX tick size of 500 KRW, one tick = 500/308,000 × 10,000 = **16.2 bps**. A 3 bps SL is physically sub-tick — it cannot be monitored or triggered with any precision. The first adverse tick move would produce a realized loss of 16.2 bps, already 5.4x the nominal SL. Even at the +20% maximum allowed deviation (3.6 bps), the SL remains sub-tick and is functionally a no-op until the first tick move instantly overshoots it.

  **Decision**: SL raised to 21.0 bps (= round-trip fee floor) to ensure the SL is (a) physically realizable (>1 tick = 16.2 bps) and (b) at minimum covers round-trip cost, preventing loss entry from masking as a break-even trade.

  This represents a +600% deviation from brief's 3 bps optimal. This is flagged as `structural_concern` per protocol rules (deviation >20% without brief escalation). The brief's optimizer likely found 3 bps optimal because most losses are small, but the optimizer's return distribution was continuous — in discrete-tick reality, the 3 bps SL cannot exist.

  **Exit mix from brief**: PT=16%, SL=20%, time-stop=63%. Time-stop dominates. The profit target at 79 bps will rarely hit (16%); most exits will be time-stop driven. This is consistent with OBI spike signals that produce modest, brief drift rather than sustained trends.

  **Trailing stop disabled**: win_rate=61.63% is healthy. Trailing stop would reduce wins prematurely (lesson_20260414_015). With time-stop as the primary exit, trailing activation at 79 bps would only fire on the rare PT-class winners — adding complexity without improving expected value for a smoke test.

## Position & Session

- **Lot size**: 2 — minimum to amortize 21 bps round-trip fee; smoke test keeps lot_size minimal to avoid capital distortion
- **Max entries per session**: 2 — TTL=30 ticks may expire on the first signal if spread is wide; allow one retry within the same session

## Fee Math

- Round-trip cost: 21.0 bps (commission 1.5 bps + sell tax 18.0 bps + 1.5 bps = 21.0 bps per KRX engine)
- Break-even WR at these params (SL=21, PT=79): `21 / (79 + 21) × 100 = 21%`
- Brief's actual win_rate = 61.63% — well above break-even, providing substantial margin
- Required edge above break-even: 61.63% actual WR vs 21.0% break-even = 40.6 pp buffer

## Implementation Notes for spec-writer

1. **SL must monitor `snap.bid_px[0]`, not `snap.mid`** (lesson_20260415_024, lesson_024):
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
   if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
       # submit MARKET SELL
   ```
   Monitoring mid for SL on a long position causes systematic underestimation — MARKET SELL fills at bid, so a mid-based trigger permits catastrophic slippage.

2. **Minimum hold guard**: Apply `ticks_since_entry >= 5` before SL can fire. Without this, noise in the first few ticks after a passive fill can immediately trigger the stop.

3. **Single symbol — no per-symbol spread gate dict needed**. For future multi-symbol expansion, spec-writer must use per-symbol dict (lesson_20260415_024).

4. **TTL tracking**: At submission, record `submission_tick`. Cancel at `current_tick - submission_tick >= ttl_ticks=30` if unfilled.

5. **Bid-drop tracking**: At submission, record `submission_bid = snap.bid_px[0]`. Cancel if `snap.bid_px[0] <= submission_bid - 3 × tick_size`.

6. **Time-stop** (primary exit): Set `time_stop_ticks = 3000` matching the brief's horizon to capture the optimizer's expected 63% time-stop exit proportion.

7. **Entry gate**: `kst_seconds >= 09:30:00` (= 34200 seconds). Block all entries before this threshold (lesson_20260415_009).

## Structural Concern Flag

`sl_bps = 3.0 (brief optimal) → 21.0 (implemented) = +600% deviation`

**Reason**: 042700 tick size = 500 KRW at ~308,000 KRW mid → 1 tick = 16.2 bps. Sub-tick SL (3 bps) is physically unrealizable. Raised to 21.0 bps (= 1.3 ticks, above 1-tick floor of 16.2 bps) as minimum physically meaningful SL that also covers round-trip cost. Alpha-designer and spec-writer must note that the brief's 3 bps SL represents a continuous-return optimization artifact; discrete-tick implementation requires a tick-aware floor.

```json
{
  "name": "smoke_042700_obi5",
  "hypothesis": "When obi(depth=5) for 042700 crosses 0.581 (95th pct), buy-side depth dominance produces a short-horizon positive drift sufficient to clear the 21 bps KRX fee — rank-2 from signal_brief.",
  "entry_condition": "obi(depth=5) >= 0.581266; entry after 09:30 only",
  "market_context": "042700 single-symbol, any IS date, post-09:30 session; no regime filter for smoke test",
  "signals_needed": ["obi(depth=5)"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": null,
  "signal_brief_rank": 2,
  "universe_rationale": "Single symbol 042700 for smoke-test plumbing",
  "entry_execution": {
    "price": "bid",
    "ttl_ticks": 30,
    "cancel_on_bid_drop_ticks": 3
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 21.0,
    "trailing_stop": false,
    "trailing_activation_bps": null,
    "trailing_distance_bps": null
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 2
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 600.0,
    "rationale": "PT unchanged at 79 bps (brief optimal). SL raised from 3 bps to 21.0 bps (+600%) — STRUCTURAL CONCERN: 042700 tick size is 500 KRW at mid ~308,000 KRW (1 tick = 16.2 bps). The brief's 3 bps SL is physically sub-tick and cannot be implemented; the first adverse tick overshoots it by 5.4x. SL floor set to 21.0 bps (>1 tick = 16.2 bps AND >= round-trip cost of 21.0 bps). Deviation exceeds 20% protocol limit; flagged as structural_concern."
  },
  "structural_concern": "sl_bps from brief (3.0) is sub-tick for 042700 (tick=16.2 bps at ~308k KRW mid). Minimum realizable SL = 1 tick = 16.2 bps. Setting SL=21.0 bps (round-trip cost floor). Brief optimizer used continuous return distribution — discrete-tick implementation requires tick-aware SL calibration.",
  "alpha_draft_path": "strategies/_drafts/smoke_042700_obi5_alpha.md",
  "execution_draft_path": "strategies/_drafts/smoke_042700_obi5_execution.md"
}
```
