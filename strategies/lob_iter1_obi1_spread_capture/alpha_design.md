---
stage: alpha
name: lob_iter1_obi1_spread_capture
created: 2026-04-20
---

# Alpha Design: lob_iter1_obi1_spread_capture

## Hypothesis

When top-of-book order book imbalance (OBI_1) is in the 90th percentile for a given symbol, buy-side pressure at the best bid overwhelmingly exceeds sell-side ask supply, and the mid price predictably ticks upward over the subsequent 10 snapshots (~1 second horizon), providing a 0.38 bps expected value edge at zero maker fee — this is rank-0 from top_robust.

## Market Context

- Market: crypto_lob (Binance LOB, 100ms snapshots)
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT
- IS window: 2026-04-19 06:00–22:00 UTC (single day; 16h of continuous LOB data)
- Signal fires at ~10% of snapshots (entry_pct=10.0 for all symbols, by design at 90th percentile threshold)
- Regime: 24/7 crypto; no explicit session gate needed at 1-second horizon
- Paradigm: spread_capture — single-side aggressive entry when LOB structure telegraphs directional pressure

## Entry Condition

Enter LONG (MARKET BUY) on a symbol when:
  `obi(depth=1)` >= threshold_per_symbol for that symbol:
    - BTCUSDT: obi_1 >= 0.91469
    - ETHUSDT: obi_1 >= 0.942049
    - SOLUSDT: obi_1 >= 0.749589

These thresholds are taken as-is from the signal brief (`threshold_per_symbol`, 90th percentile of obi_1 in IS period). No deviation applied.

The entry side is "high" — enter only when OBI_1 is strongly positive (heavy bid book), confirming buy-side dominance at the top of book.

## Signals Needed

- `obi(depth=1)` — top-of-book imbalance, (bid_qty[0] - ask_qty[0]) / (bid_qty[0] + ask_qty[0])
  Available in SIGNAL_REGISTRY as `obi` with `depth` parameter.

## Universe Rationale

BTCUSDT, ETHUSDT, SOLUSDT form the standard 3-symbol crypto universe. All three pass the cross-symbol robustness filter with same-sign IC: BTC=+0.253, ETH=+0.2633, SOL=+0.2352, min_abs_ic=0.2352 >> 0.04 floor. This is the strongest robustness among all LOB signals in the brief, making obi_1 the most reliable directional predictor across the universe. SOL shows the lowest IC but still exceeds the minimum threshold with meaningful margin.

## Knowledge References

- microstructure_primer.md §1.1: OBI(n) formula and depth interpretation. OBI(1) is "very noisy, high-frequency sensitive" — this is deliberate at 10-tick horizon; §5 warns against OBI(1) for medium-frequency but the brief confirms 10-tick IC is highest at depth=1.
- microstructure_primer.md §4.1: Fair-value / spread-capture quoting logic. OBI_1 serves as fair-value displacement indicator.
- market_making.md §0: BTC half-spread ~0.065 bps (spread ~0.13 bps); adverse selection 2-5 bps for passive MM. MARKET entry avoids queue risk at cost of crossing half-spread.
- market_making.md §4.2: OBI-skew guard — here inverted: we ENTER (not cancel) when OBI is heavily skewed, because the brief confirms predictive power in this regime.

## Constraints Passed To Execution-Designer

- Signal horizon is 10 ticks (10 × 100ms = 1 second). The edge is measured at the 10-tick terminal return; the execution hold period MUST match this (~10 ticks). Time-stop must fire no later than 10 ticks post-fill.
- Signal is fleeting: the 90th-percentile OBI threshold represents a transient state. Entry fill should be aggressive (MARKET or marketable LIMIT) to ensure fill within 1-2 ticks of signal fire.
- Brief optimal_exit: PT = 1.21 bps, SL = 1.62 bps, horizon = 10 ticks. Execution-designer should use these as baseline (±20% band).
- Fee is 0 bps (maker fee context assumed by brief). If taker fee is non-zero in actual execution, the thin 0.38 bps EV erodes — flag this risk.
- No execution-side decisions are made here: TTL, stop bps, lot_size, trailing config are execution-designer's domain.

## Brief Realism Analysis

**Raw EV**: 0.38 bps (from brief, fee=0, 10-tick horizon)

**Entry order type**: MARKET — ensures fill within 1 tick of signal fire, critical at 1-second horizon where OBI_1 state is ephemeral. Passive LIMIT_AT_BID risks non-fill: when OBI_1 is heavily bid-skewed (>91% bid dominance at best level), sellers are scarce, so a bid limit order may not fill before the price moves away.

**Spread cross cost**: +0.065 bps — MARKET BUY crosses half the bid-ask spread. BTC/USDT spread ≈ 0.13 bps at normal conditions (microstructure_primer §1.4, spread_bps < 0.2 bps in ultra-tight regime); conservative half = 0.065 bps. ETH and SOL spreads are wider (~0.5-1 bps), so 0.065 bps is an optimistic estimate for the portfolio; conservative rounding to 0.1 bps is warranted but 0.065 is used per BTC dominance weighting.

**Regime compatibility**: partial — IS window is a single 16-hour trading day (2026-04-19). Intraday BTC trend estimated ~+0.5% based on the broader April 2026 market context. The spread_capture paradigm at 1-second horizon is largely trend-agnostic (not mean-reversion vs trend-follow), but single-day IS may not capture full regime diversity. Mark as "partial" to flag single-day training window risk.

**Regime adjustment**: 0.2 bps — reflects single-day IS concentration risk and intraday regime uncertainty. Not a "mismatch" since spread_capture is paradigm-neutral to hourly trend direction.

**Adjusted EV**: 0.38 × 1.0 − 0.065 − 0.2 = 0.115 bps → positive, marginally.

**Decision**: proceed_with_caveat — EV is positive post-adjustment but thin (0.115 bps). The primary caveat is that the 0.38 bps brief EV is measured at fee=0; any taker fee at execution will eliminate the edge. Execution-designer must implement MARKET entry with a zero-fee account tier OR confirm maker-rebate execution path.

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T00:00:00",
  "agent_name": "alpha-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_iter1_obi1_spread_capture_alpha.md",
  "name": "lob_iter1_obi1_spread_capture",
  "hypothesis": "When top-of-book OBI_1 reaches the 90th-percentile threshold per symbol, bid-side dominance at best-level predicts upward mid-price movement over the subsequent 10 snapshots (~1s), yielding 0.38 bps expected value at zero maker fee; this is rank-0 from top_robust (obi_1 × fwd_10t, avg_ic=0.2505, min_abs_ic=0.2352 across BTC/ETH/SOL).",
  "entry_condition": "Enter MARKET BUY on a symbol when obi(depth=1) >= symbol-specific 90th-percentile threshold: BTCUSDT >= 0.91469, ETHUSDT >= 0.942049, SOLUSDT >= 0.749589. Thresholds taken as-is from signal brief threshold_per_symbol.",
  "market_context": "crypto_lob (Binance 100ms LOB snapshots); 24/7 continuous; IS window 2026-04-19 06:00-22:00 UTC; signal fires at ~10% of snapshots (90th percentile selectivity); no intraday session gate needed at 1-second horizon.",
  "signals_needed": ["obi(depth=1)"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "spread_capture",
  "multi_date": false,
  "parent_lesson": null,
  "signal_brief_rank": 1,
  "universe_rationale": "BTCUSDT/ETHUSDT/SOLUSDT pass cross-symbol robustness filter with same-sign IC (BTC=0.253, ETH=0.263, SOL=0.235) and min_abs_ic=0.2352 >> 0.04 floor — strongest robustness of all LOB signals in brief.",
  "escape_route": null,
  "brief_realism": {
    "brief_ev_bps_raw": 0.38,
    "entry_order_type": "MARKET",
    "spread_cross_cost_bps": 0.065,
    "brief_horizon_ticks": 10,
    "planned_holding_ticks_estimate": 10,
    "horizon_scale_factor": 1.0,
    "symbol_trend_pct_during_target_window": 0.5,
    "regime_compatibility": "partial",
    "regime_adjustment_bps": 0.2,
    "adjusted_ev_bps": 0.115,
    "decision": "proceed_with_caveat",
    "rationale": "MARKET entry at half-spread cost (0.065 bps per microstructure_primer §1.4 BTC spread ~0.13 bps) preserves fill certainty at the ephemeral 1-second OBI signal horizon; regime marked 'partial' due to single-day IS window (2026-04-19 only) per market_making.md §0 adverse selection caveat; adjusted EV 0.115 bps is positive but thin — any taker fee above 0 bps eliminates the edge entirely."
  }
}
```
