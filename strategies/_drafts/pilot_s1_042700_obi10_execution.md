---
stage: execution
name: pilot_s1_042700_obi10
created: 2026-04-17
signal_brief_rank: 3
---

# Execution Design: pilot_s1_042700_obi10

## Adverse Selection Assessment

Entry is aggressive (taker) at the ask price — this eliminates passive-fill adverse selection entirely. The prior iteration (strat_20260417_0002_smoke_042700_obi5) showed OBI decaying from 0.56 to below threshold by the time a passive LIMIT BUY at bid was filled; switching to ask removes this structural fill-rate problem. Adverse selection risk here is LOW: we are the taker, so we get filled immediately at the current offer. The cost is we cross the spread (~16.5 bps on 042700), but with EV=11.8 bps and pt=79 bps, the ask-cross is absorbed within the exit structure.

## Entry Order

- Price: ask (aggressive taker limit; marketable)
- TTL: 15 ticks — signal is fleeting (OBI imbalance dissipates rapidly); cancel if unfilled after 15 ticks
- Bid-drop cancel: disabled — entry is at ask (taker), not resting at bid; cancel-on-bid-drop is only relevant for passive BID entry
- Rationale: OBI signal decays within ticks (lesson_20260417_001, lesson_20260414_007). Aggressive ask entry ensures fill on the same tick the signal fires, before the imbalance dissipates. TTL=15 ticks provides a short window; if the ask has moved away in 15 ticks, the signal context is stale and we cancel rather than chase.
- Opening-hour block: entries blocked 09:00–09:30 KRX time (lesson_20260415_009 — OBI signals are noise during auction noise window).

## Exit Structure

- Profit target: 79.0 bps (LIMIT SELL — at brief's exact optimal; no deviation)
- Stop loss: 33.0 bps (MARKET SELL — raised from brief's 3 bps to 2-tick floor for 042700)
  - 042700 mid ~303,000 KRW; tick size = 500 KRW = 16.50 bps/tick. Brief sl=3 bps falls in the inter-tick gap between tick-1 (16.5 bps) and tick-2 (33.0 bps). No realizable bid level exists between them, so SL must be placed at tick-2 = 33 bps to avoid guaranteed sl_overshoot invariant violations (lesson_20260417_001, confirmed bug_pnl=0 — structural, not a code bug).
- Trailing stop: disabled (pilot constraint: conservative execution; no trailing stop)
  - Note: the brief's exit_mix shows trailing exits = 47% of all exits — by disabling trailing, we forgo the dominant exit path. This is flagged as a structural concern. If the pilot shows sufficient roundtrips, re-enabling trailing with activation=40 bps, distance=20 bps is recommended for iteration 2.
- SL reference: must monitor snap.bid_px[0] (not snap.mid) — MARKET SELL fills at bid; using mid would understate realized loss (lesson_024 reference: strat_0028 saw 50 bps nominal SL → 362 bps realized, 7x overshoot from mid-based monitoring).
- Rationale: PT=79 bps is brief-optimal and 3.76x round-trip cost (21 bps) — strong reward structure. SL=33 bps is the minimum physically realizable stop on this symbol's tick grid. Break-even WR = 33/(79+33) = 29.5%; brief's win_rate=49.66% provides 20+ ppt margin above break-even.

## Position & Session

- Lot size: 2 — amortizes per-trade fixed fees; signal fires at ~8.72% of ticks so quality-per-fill matters
- Max entries per session: 1 — signal fires frequently; one quality fill per day is preferred over multiple lower-quality re-entries; pilot phase prioritizes n_roundtrips accumulation across dates rather than intra-day stacking
- Rationale: With TTL=15 ticks and aggressive entry, fill probability is high when signal fires. Session cap of 1 prevents overfitting to any single intraday OBI regime. Raise to 2 in iteration 2 if win_rate is confirmed above 40%.

## Fee Math

- Round-trip cost: 21.0 bps (KRX actual: 1.5 bps commission each side + 18 bps sell tax)
- Profit target: 79.0 bps = 3.76x round-trip cost (healthy buffer)
- Stop loss: 33.0 bps (2-tick floor; realistic)
- Break-even WR at these params: 33 / (79 + 33) = **29.5%**
- Brief win_rate: 49.66% — margin above break-even: **+20.2 ppt**
- Note: win_rate=49.66% is above the 30% warning threshold; signal quality is adequate but not high-conviction. Monitor empirical WR from backtest; if it drops below 35%, escalate as structural_concern.

## Structural Concern: Trailing Disabled

The brief's exit_mix.ts = 47% — trailing is the single largest exit mode for this signal. Disabling trailing stop per pilot constraint removes the dominant exit pathway and will likely suppress avg_win_bps compared to the brief's Sharpe-optimal calibration (lesson_20260414_021 warns that suppressing trailing exits causes avg_win to degrade below the resting limit target). This is acceptable for the pilot (conservative baseline), but must be re-enabled with trailing_activation_bps >= 40 and trailing_distance_bps <= 25 for the next iteration to recover the statistical optimum.

## Deviation from Brief

- PT: 0% deviation (79 bps → 79 bps)
- SL: +1000% deviation (3 bps → 33 bps) — mandatory tick-size constraint, not a preference. 042700 tick=500 KRW=16.5 bps; SL of 3 bps is physically unrealizable. Flooring at 2-tick minimum (33 bps) per lesson_20260417_001. This exceeds the ±20% guideline and is classified as a structural_concern, not an elective adjustment.

## Implementation Notes for spec-writer

1. Entry: submit LIMIT BUY at snap.ask_px[0] (aggressive/marketable); TTL=15 ticks; no bid-drop cancel.
2. Entry gate: block entries when tick_time < 09:30:00 KRX (opening noise window).
3. SL monitoring: track unrealized_bps using snap.bid_px[0] as reference — NOT snap.mid:
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_px) / entry_px * 10000
   if unrealized_bps <= -33.0 and ticks_since_entry >= 5:
       # submit MARKET SELL
   ```
4. PT: resting LIMIT SELL at entry_px * (1 + 79/10000) placed immediately after fill.
5. Trailing stop: disabled (set trailing_stop: false in spec.yaml).
6. No per-symbol spread gate needed (single symbol strategy).
7. max_entries_per_session: 1; lot_size: 2.

```json
{
  "name": "pilot_s1_042700_obi10",
  "hypothesis": "When obi(depth=10) on 042700 exceeds 0.469 (90th percentile), sustained full-book buy-side pressure predicts upward continuation over 3000 ticks, yielding 11.8 bps EV after fees — rank-3 from signal_brief.",
  "entry_condition": "Enter long on 042700 when obi(depth=10) >= 0.469 on the current tick snapshot; execute aggressively (at ask) to avoid imbalance decay before fill.",
  "market_context": "042700 KRX in-sample universe; signal fires at 90th percentile of obi_10 distribution (~8.72% of ticks); avoid 09:00–09:30 opening window.",
  "signals_needed": ["obi(depth=10)"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "strat_20260417_0002_smoke_042700_obi5",
  "signal_brief_rank": 3,
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": 15,
    "cancel_on_bid_drop_ticks": null
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 33.0,
    "trailing_stop": false,
    "trailing_activation_bps": null,
    "trailing_distance_bps": null
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 1
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 1000.0,
    "rationale": "PT kept at brief optimal (79 bps). SL raised from 3 bps to 33 bps (+1000%) because 042700 tick size = 500 KRW = 16.5 bps/tick at ~303k KRW; SL=3 bps is physically unrealizable (falls between tick-0 and tick-1). Floor set at 2-tick minimum (33 bps) per lesson_20260417_001 and pilot constraint. This is a mandatory tick-grid structural fix, not a preference deviation."
  },
  "alpha_draft_path": "strategies/_drafts/pilot_s1_042700_obi10_alpha.md",
  "execution_draft_path": "strategies/_drafts/pilot_s1_042700_obi10_execution.md"
}
```
