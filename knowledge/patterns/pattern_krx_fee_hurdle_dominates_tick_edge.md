---
id: pattern_krx_fee_hurdle_dominates_tick_edge
created: 2026-04-14T00:00:00
tags: [pattern, fees, tax, korea, turnover, tick-scale, lot-size]
lessons:
  - "[[lesson_20260414_001_absolute_spread_filter_breaks_cross_symbol]]"
  - "[[lesson_20260414_003_tax_heavy_korean_market_tight_spread_entry_filter_increases_turnover_fees_dominate_pnl]]"
---

# Pattern: KRX fee hurdle dominates tick-scale edge

## Root cause

KRX equities carry a ~21 bps round-trip cost floor (18 bps sell tax + 1.5 bps commission each side). Any strategy that:

1. exits within tens of ticks (tick-horizon holds), AND
2. sizes at lot_size = 1 share (absolute fee per trade ~193 KRW on 005930), AND
3. uses a noisy real-time signal (OBI, OFI, short-window momentum)

will systematically lose to fees. The expected edge per trade at tick horizon is 1–5 bps; the fee floor is 21 bps. Even with a 60% win rate the strategy cannot break even.

## Evidence

| Strategy | return_pct | fees | fees / |total_loss| |
|---|---|---|---|
| strat_0001 obi_momentum_tight | -0.79% | 64,476 | ~82% |
| strat_0002 obi_momentum_bps   | -0.86% | 65,405 | ~76% |
| strat_0003 tight_spread_ofi   | -0.95% | 71,744 | ~75% |

Fees are 75–82% of total loss across all three. Tightening entry filters did not reduce fee burn — it increased trade count (334 → 372) because the filter selects a common market regime, not a rare high-edge moment.

## Escape routes (in order of estimated leverage)

1. **Increase lot_size**: Use `lot_size >= 100` to amortize the fixed-cost component. At 100 shares, fee-per-notional stays constant but absolute edge scales with position size, improving the edge-to-fee ratio. Note: the Korean sell tax remains 18 bps regardless of lot size — this only helps with the commission component.

2. **Increase holding duration**: Target multi-hundred-tick holds so mid-return can accumulate to >25 bps. Use a trend or volatility-breakout entry (e.g., `mid_return_bps(lookback=200) > 15`) rather than a short-window momentum flip. This requires a `min_holding_ticks` guard in the exit condition (expressible via `holding_ticks` in the DSL eval context).

3. **Switch to ETF universe**: Korean ETFs (e.g., 069500 KODEX 200) have 0 sell tax; round-trip cost drops to ~3 bps. The 21 bps hurdle becomes a 3 bps hurdle, making tick-scale strategies viable.

4. **Maker-side fills only**: Avoid the taker spread cost by resting limit orders. Deferred until Phase 4 queue-model is implemented.

## Anti-patterns to avoid

- Do NOT tighten entry spread filters further without also reducing trade frequency or raising minimum expected move threshold.
- Do NOT tune OBI/OFI thresholds in isolation; the signal has no edge once fees are accounted for at tick scale (lessons 001, 002, 003).
- Do NOT assume higher signal confidence (e.g., stacking OBI + OFI + ret5) reduces fee cost; it reduces trade count only marginally while still yielding subthreshold edge per trade.
