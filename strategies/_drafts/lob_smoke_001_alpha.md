---
stage: alpha
name: lob_smoke_001
created: 2026-04-20
---

# Alpha Design: lob_smoke_001

## Hypothesis

When top-of-book order book imbalance (OBI-1) exceeds the 90th-percentile threshold, passively posting a bid limit order captures a short-horizon directional edge of ~0.38 bps before fees over the next 10 LOB ticks (~1 second).

## Market Context

LOB market (`crypto_lob`), Binance 100ms snapshot cadence. Signal fires when instantaneous top-of-book demand pressure (OBI-1 ≥ p90 threshold per symbol) signals near-certain upward short-term price movement. Viable in normal-to-elevated volatility regimes; not contingent on broader directional trend (regime-neutral at 10-tick horizon). Universe: BTCUSDT, ETHUSDT, SOLUSDT (standard 3-symbol crypto robustness set). Fee assumption: 0 bps maker (Binance VIP-tier maker or maker rebate).

## Entry Condition

For each symbol, on every 100ms LOB snapshot:

1. Compute OBI-1 = (bid_qty[0] - ask_qty[0]) / (bid_qty[0] + ask_qty[0])
2. Enter if OBI-1 >= symbol-specific p90 threshold:
   - BTCUSDT: OBI-1 >= 0.91469
   - ETHUSDT: OBI-1 >= 0.942049
   - SOLUSDT: OBI-1 >= 0.749589
3. Entry is passive: post LIMIT order at best bid price (LIMIT_AT_BID)
4. Signal is fleeting — entry is only valid for the current tick; stale signals at t+1 must be discarded

The `entry_side` is `"high"` per brief: enter only when OBI-1 is extremely bid-heavy, indicating strong short-term upward pressure on the microprice (per microstructure_primer.md §1.1: OBI → +1 = all demand).

## Signals Needed

- `obi(depth=1)` — top-of-book order book imbalance, depth=1 level (in SIGNAL_REGISTRY as `obi`)

## Universe Rationale

BTCUSDT, ETHUSDT, SOLUSDT: the standard Binance 3-symbol robustness universe. All three pass the `min_abs_ic >= 0.04` cross-symbol filter with per-symbol ICs of 0.253, 0.263, 0.235 respectively — the strongest and tightest IC cluster across all LOB features in the brief. OBI-1 at `fwd_10t` is rank-0 (highest avg_ic = 0.2505) with `min_abs_ic = 0.2352`, well above the 0.04 robustness floor.

## Knowledge References

- `references/microstructure_primer.md §1.1`: OBI-1 formula and depth trade-offs; §1.7 queue position model for passive LIMIT fill probability; §4.1 fair-value estimate basis
- `references/market_making.md §0`: economic reality check — MM edge = half-spread − adverse selection − fee_net; §2.1 price-improve vs back-of-queue; §4.2 OBI-skew guard confirms OBI directional predictive power
- Signal brief: `data/signal_briefs_v2/crypto_lob.json`, `top_robust[0]`, `obi_1 / fwd_10t`, avg_ic=0.2505, ev_bps_after_fee=0.38, viable=true

## Constraints Passed To Execution-Designer

- Entry is only valid at the current snapshot tick; signal must NOT carry over to next tick (stale OBI is meaningless)
- Entry order type MUST be passive LIMIT_AT_BID — taker entry would eliminate the EV entirely (no half-spread benefit)
- Brief horizon is exactly 10 ticks (1 second at 100ms cadence); holding beyond ~20 ticks should trigger forced exit escalation
- Brief's `optimal_exit`: PT = 1.21 bps, SL = 1.62 bps, horizon = 10 ticks — execution-designer should use these as baseline (within ±20%)
- Signal fires at ~10% of ticks per symbol (p90 threshold) — capacity is bounded; avoid stacking concurrent entries per symbol
- Fee assumption: 0 bps maker; any taker exit will destroy the EV; exit must also target passive limit

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T12:00:00",
  "agent_name": "alpha-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_smoke_001_alpha.md",
  "name": "lob_smoke_001",
  "hypothesis": "When OBI-1 exceeds the symbol-specific 90th-percentile threshold (rank-0 from top_robust), passively posting a bid limit order harvests a 10-tick directional edge of ~0.38 bps ev_after_fee on BTCUSDT, ETHUSDT, SOLUSDT under 0 bps maker fee.",
  "entry_condition": "On each 100ms LOB snapshot, compute OBI-1 = (bid_qty[0] - ask_qty[0]) / (bid_qty[0] + ask_qty[0]); enter with LIMIT_AT_BID if OBI-1 >= symbol threshold (BTC: 0.91469, ETH: 0.942049, SOL: 0.749589); signal expires at next tick — no carry-forward.",
  "market_context": "crypto_lob market (Binance 100ms L2 snapshots); 0 bps maker fee assumption; regime-neutral at 10-tick (1-second) horizon; fires at top-10% OBI-1 events (~10% of ticks); viable across all three symbols with IC 0.235–0.263.",
  "signals_needed": ["obi(depth=1)"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "spread_capture",
  "multi_date": true,
  "parent_lesson": null,
  "signal_brief_rank": 1,
  "universe_rationale": "BTCUSDT, ETHUSDT, SOLUSDT: all three pass cross-symbol IC robustness with min_abs_ic=0.2352 >> 0.04 floor; highest avg_ic=0.2505 of any LOB feature in brief; thresholds are symbol-specific from p90 calibration.",
  "escape_route": null,
  "brief_realism": {
    "brief_ev_bps_raw": 0.38,
    "entry_order_type": "LIMIT_AT_BID",
    "spread_cross_cost_bps": -0.07,
    "brief_horizon_ticks": 10,
    "planned_holding_ticks_estimate": 10,
    "horizon_scale_factor": 1.0,
    "symbol_trend_pct_during_target_window": null,
    "regime_compatibility": "partial",
    "regime_adjustment_bps": 0.0,
    "adjusted_ev_bps": 0.45,
    "decision": "proceed",
    "rationale": "Passive LIMIT_AT_BID saves ~half-spread vs mid (microstructure_primer.md §1.4: BTC spread ~0.13 bps → half ~0.07 bps) yielding a negative spread_cross_cost; regime_compatibility=partial because spread_capture is broadly regime-neutral at 1-second horizon but may degrade under volatility spikes (market_making.md §4.1); adjusted_ev = 0.38 × 1.0 − (−0.07) − 0.0 = 0.45 bps, positive and above fee floor."
  }
}
```
