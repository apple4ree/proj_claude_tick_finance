---
stage: alpha
name: lob_run20260420_iter2_obi1_maker_fixed
created: 2026-04-20
---

# Alpha Design: lob_run20260420_iter2_obi1_maker_fixed

## Hypothesis

When top-of-book order book imbalance (obi_1) is strongly bid-heavy (>= per-symbol p90 threshold), resting a passive LIMIT buy at the best bid harvests the directional half-spread edge over the next 10 ticks; iter1 proved the signal is valid for BTC+ETH but the OBI gate was never applied in the LIMIT path, so this iteration wires the gate correctly.

## Market Context

- Market: crypto_lob (100ms LOB snapshots, BTCUSDT, ETHUSDT, SOLUSDT)
- IS window: 2026-04-19 06:00 UTC – 2026-04-19 22:00 UTC (16h)
- Regime: slight positive intraday drift (~+0.1% portfolio in IS); spread_capture long paradigm compatible
- OBI signal strongest on top-of-book (obi_1 avg_IC 0.2514, min_abs_IC 0.2352 — highest robust IC in brief)
- Spread gate: reject entry if spread_bps >= profit_target_bps (prevents structural entry loss on SOL, as identified in iter1/iter2 feedback)

## Entry Condition

For each symbol independently:
1. Compute obi_1 = (bid_qty[0] - ask_qty[0]) / (bid_qty[0] + ask_qty[0])
2. Gate A (OBI threshold, PER-SYMBOL, MUST be checked BEFORE posting LIMIT order):
   - BTCUSDT: obi_1 >= 0.919
   - ETHUSDT: obi_1 >= 0.942
   - SOLUSDT: obi_1 >= 0.750
3. Gate B (spread gate): if spread_bps >= profit_target_bps → skip (do NOT post)
4. Gate C (position cap pre-check): if current_position >= max_position_per_symbol → skip
5. If all gates pass: post passive LIMIT BUY at best_bid
6. TTL: ≥ 30 ticks (3 seconds at 100ms cadence) — NOT 10 ticks (iter1 used TTL=10 which suppressed fills)
7. Cancel trigger: cancel if best_bid drops ≥ 3 ticks (NOT 1 tick as in iter1 — too aggressive)

Critical fix vs iter1: The OBI gate (step 2) MUST execute BEFORE the LIMIT order is posted. In iter1, the gate was absent in the LIMIT path, causing all 11 entries to fire at avg obi_1 = -0.455 (opposite direction). This invalidated the signal test entirely.

## Signals Needed

- obi(depth=1) [SIGNAL_REGISTRY: obi]
- spread_bps [SIGNAL_REGISTRY: spread_bps]
- best_bid [SIGNAL_REGISTRY: best_bid]
- mid [SIGNAL_REGISTRY: mid]

## Universe Rationale

BTCUSDT, ETHUSDT, SOLUSDT: standard 3-symbol crypto universe with LOB data available from 2026-04-19. obi_1 is robust across all three symbols (per_symbol_IC: BTC 0.2556, ETH 0.2633, SOL 0.2352 — all same-sign and min_abs_IC 0.2352 >> 0.04 threshold). SOL inclusion gated by spread_bps filter to prevent structural entry loss (SOL spread 1.17 bps > typical PT ~1.09 bps in iter2 baseline).

## Knowledge References

- lesson_20260420_001_lob_spread_gt_pt_blocks_symbol (spread gate lesson from iter1/iter2)
- iter1 (lob_run20260420_iter1_obi1_maker): OBI gate missing in LIMIT_AT_BID path → all entries at avg obi=-0.455; max_position_exceeded x4 from post-fill position check; only 26 fills / 11 RTs from TTL=10 + bid_drop=1 too tight
- iter2 (lob_iter2_obi1_spread_gate): Confirmed BTC+ETH edge +0.226 bps at fee=0; SOL excluded by spread gate; architecture validated
- microstructure_primer.md §1.1: obi(1) depth interpretation and entry_side=high for directional passive entry
- microstructure_primer.md §1.7: queue position model for passive LIMIT fill — longer TTL needed for back-of-queue fill probability
- fee_aware_sizing.md §0, §2: maker vs taker trade-off; passive LIMIT fills at bid reduce entry cost vs market order

## Constraints Passed To Execution-Designer

1. OBI gate MUST execute BEFORE LIMIT order post (not after fill event)
2. Pre-order position cap check (max_position_per_symbol) MUST run before order submission
3. entry_ttl_ticks: RECOMMEND >= 30 ticks (3 seconds) — brief horizon=10t is post-fill, TTL governs how long we wait for fill
4. cancel_on_bid_drop: RECOMMEND >= 3 ticks — 1-tick cancel from iter1 is too aggressive for passive maker
5. Spread gate: reject entry if spread_bps >= profit_target_bps (per-symbol, using real-time spread)
6. Profit_target_bps and stop_loss_bps from brief optimal_exit: PT=1.21 bps, SL=1.64 bps (baseline; execution-designer may adjust ±20%)
7. Post-entry hold: time_stop at brief horizon = 10 ticks after fill (NOT TTL=10 ticks before fill)
8. Fee assumption: maker fee = 0 bps (LIMIT_AT_BID passive fill); brief was computed at fee_bps=0

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T14:00:00",
  "agent_name": "alpha-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_run20260420_iter2_alpha.md",
  "name": "lob_run20260420_iter2_obi1_maker_fixed",
  "hypothesis": "When obi_1 is >= per-symbol p90 threshold (rank-1 from top_robust, IC=0.2514), posting a passive LIMIT BUY at best_bid — with OBI gate correctly applied BEFORE order submission, pre-order position cap, TTL>=30t, and cancel_on_bid_drop>=3 — harvests the 10-tick directional edge suppressed by implementation bugs in iter1.",
  "entry_condition": "Gate obi_1 >= per-symbol threshold (BTC:0.919, ETH:0.942, SOL:0.750) BEFORE posting LIMIT BUY at best_bid; additionally gate spread_bps < profit_target_bps and position < max_position_per_symbol; entry_ttl_ticks >= 30; cancel_on_bid_drop >= 3",
  "market_context": "crypto_lob IS 2026-04-19 06:00-22:00 UTC; slight positive intraday drift ~+0.1%; spread_capture paradigm compatible; BTC+ETH OBI edge proven at +0.226 bps in iter1/2 but gating bug prevented signal from being tested in iter1-maker run",
  "signals_needed": ["obi(depth=1)", "spread_bps", "best_bid", "mid"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "spread_capture",
  "multi_date": false,
  "parent_lesson": "lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment",
  "signal_brief_rank": 1,
  "universe_rationale": "BTC/ETH/SOL all show consistent positive obi_1 IC (0.2556/0.2633/0.2352); SOL protected by spread gate; unified portfolio spec",
  "escape_route": null,
  "brief_realism": {
    "brief_ev_bps_raw": 0.39,
    "entry_order_type": "LIMIT_AT_BID",
    "spread_cross_cost_bps": -0.05,
    "brief_horizon_ticks": 10,
    "planned_holding_ticks_estimate": 10,
    "horizon_scale_factor": 1.0,
    "symbol_trend_pct_during_target_window": 0.1,
    "regime_compatibility": "match",
    "regime_adjustment_bps": 0.0,
    "adjusted_ev_bps": 0.44,
    "decision": "proceed",
    "rationale": "Passive LIMIT_AT_BID fill: save ~half-spread entry cost vs MARKET; adverse-selection net +0.05 bps vs mid when OBI gate properly applied (microstructure_primer.md §1.1, §1.7). fee_aware_sizing.md §0,§2: maker fee=0 so adjusted_ev = 0.39*1.0 - (-0.05) - 0.0 = 0.44 bps; regime is slight positive drift (match for spread_capture long); execution-designer should set entry_ttl_ticks>=30 and cancel_on_bid_drop>=3 to recover fill rate lost in iter1 (only 26 fills / 11 RTs from over-tight TTL=10+bid_drop=1)."
  }
}
```
