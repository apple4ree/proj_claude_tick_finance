---
stage: alpha
name: lob_iter2_obi1_spread_gate
created: 2026-04-20
parent_lesson: lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment
---

# Alpha Design: lob_iter2_obi1_spread_gate

## Hypothesis

When the top-of-book order book imbalance (obi_1) exceeds the per-symbol p90 threshold AND the live spread_bps is strictly less than the profit_target_bps, a 10-tick directional edge exists in BTCUSDT and ETHUSDT (rank-1 from top_robust); SOLUSDT is gated out structurally by its wider spread relative to PT.

## Market Context

24/7 crypto LOB (Binance, 100ms snapshots). Signal measured at tick level over a 10-tick (1-second) horizon. No session gating. Regime is direction-agnostic at this horizon — spread_capture edge does not depend on macro trend direction. SOL is expected to fail the spread gate in most observations (spread 1.17 bps vs PT 1.09 bps from iter-1 data), effectively restricting the active universe to BTC+ETH until SOL spread tightens.

## Entry Condition

Per tick snapshot, enter LONG if ALL of the following hold:
1. `obi_1 >= threshold_per_symbol[symbol]` (per-symbol p90 from brief: BTC=0.91469, ETH=0.942049, SOL=0.749589)
2. `spread_bps < profit_target_bps` (per-symbol spread gate — reject if live spread >= PT; structural loss prevention per lesson_20260420_001)
3. No existing position in this symbol

The spread gate (condition 2) is the new constraint added in iter-2. It must be enforced in strategy.py before the OBI threshold check fires, and must use the per-symbol PT in bps (not a hardcoded constant).

## Signals Needed

- `obi(depth=1)` — top-of-book imbalance
- `spread_bps` — live best_ask − best_bid in basis points (already available as `spread_bps` snapshot primitive)

## Universe Rationale

BTCUSDT, ETHUSDT, SOLUSDT — full standard universe. SOL is included in the universe spec so it can be gated by the spread filter at runtime. This allows us to measure how often SOL is excluded vs allowed in (diagnostic value) and recover SOL edge if its spread ever tightens below PT. BTC and ETH are confirmed edge-positive from iter-1: BTC +0.267 bps, ETH +0.184 bps, WR 37-38%.

## Knowledge References

- `lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_...` — dual defect: SOL OBI gate bypass + spread > PT structural block; both fixes required
- `references/microstructure_primer.md §1.1` — OBI(1) formula, depth tradeoff; obi(1) top-of-book, high-frequency sensitive, highest IC (0.2505 avg cross-symbol)
- `references/fee_aware_sizing.md §2` — fee-dominated regime detection: fee_to_edge_ratio 94.7% at 4-bps taker; at fee=0 (smoke construct), BTC+ETH gross edge +0.226 bps is viable; maker-only execution required for deployability (deferred to iter 3)

## Constraints Passed To Execution-Designer

- Spread gate must be enforced as a hard pre-entry check in strategy.py: `if spread_bps >= profit_target_bps: skip this tick`
- OBI threshold must use per-symbol values from brief exactly (BTC=0.91469, ETH=0.942049, SOL=0.749589)
- Horizon is 10 ticks (1 second at 100ms cadence); exit design must not extend beyond 2× this horizon (20 ticks) without revisiting brief
- fee=0 smoke construct is preserved for iter-2; real-fee viability requires maker-only execution — do NOT switch to MARKET order type at 4 bps without EV recompute
- Enable `track_mfe=true` if available so iter-3 can use intra-path MFE/MAE data

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T06:00:00",
  "agent_name": "alpha-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_iter2_obi1_spread_gate_alpha.md",
  "name": "lob_iter2_obi1_spread_gate",
  "hypothesis": "When obi_1 >= per-symbol p90 threshold AND spread_bps < profit_target_bps, a 10-tick directional edge exists in BTC/ETH (rank-1 from top_robust); SOL is structurally gated out by its wider spread.",
  "entry_condition": "Enter LONG when: (1) obi_1 >= threshold_per_symbol[symbol] (BTC=0.91469, ETH=0.942049, SOL=0.749589); (2) spread_bps < profit_target_bps [spread gate — new in iter-2]; (3) no existing position in this symbol.",
  "market_context": "24/7 crypto LOB (Binance 100ms snapshots); direction-agnostic at 10-tick horizon; SOL expected excluded by spread gate in most ticks; active universe effectively BTC+ETH until SOL spread normalizes.",
  "signals_needed": ["obi(depth=1)", "spread_bps"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "spread_capture",
  "multi_date": true,
  "parent_lesson": "lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment",
  "signal_brief_rank": 1,
  "universe_rationale": "BTC/ETH/SOL full standard universe; SOL self-excludes via spread gate at runtime, preserving diagnostic visibility into SOL spread regime; BTC+ETH confirmed positive edge from iter-1 (+0.267/+0.184 bps at fee=0).",
  "escape_route": "If spread gate excludes >90% of SOL ticks and BTC+ETH combined n_trade falls below statistical floor, pivot iter-3 to passive LIMIT_AT_BID maker entry (fee≈0, adverse-selection-adjusted EV per fee_aware_sizing.md §4) to restore full 3-symbol universe viability.",
  "brief_realism": {
    "brief_ev_bps_raw": 0.38,
    "entry_order_type": "MARKET",
    "spread_cross_cost_bps": 0.05,
    "brief_horizon_ticks": 10,
    "planned_holding_ticks_estimate": 10,
    "horizon_scale_factor": 1.0,
    "symbol_trend_pct_during_target_window": null,
    "regime_compatibility": "unknown",
    "regime_adjustment_bps": 0.0,
    "adjusted_ev_bps": 0.33,
    "decision": "proceed_with_caveat",
    "rationale": "Per microstructure_primer.md §1.1, BTC/ETH spread at top-of-book averages ~0.05 bps half-spread cost for MARKET entry; SOL is excluded by the spread gate so its 1.17 bps spread does not enter the EV calculation. Per fee_aware_sizing.md §2, fee_to_edge_ratio at real 4-bps taker = 94.7% — this iteration runs at fee=0 (smoke construct) confirming the gate fix; maker-only execution must be adopted before live deployment. Regime direction for 2026-04-19 LOB sample is unknown (single-day, no macro context), so regime_adjustment=0 and proceed_with_caveat is the appropriate decision pending multi-day OOS confirmation."
  }
}
```
