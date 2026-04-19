---
stage: alpha
name: crypto_1h_btc_mean_rev_168h_iter1
created: 2026-04-17
---

# Alpha Design: crypto_1h_btc_mean_rev_168h_iter1

## Hypothesis

When BTCUSDT has lost more than 5.6% over the trailing 168 hours (7 days), the market has overextended to the downside and exhibits mean-reverting behavior over the subsequent 168-hour window — exploiting the well-documented weekly return reversal premium in large-cap crypto (rank-0 from signal_brief).

## Market Context

- **Symbol**: BTCUSDT (Binance spot, 1-hour bars)
- **Regime**: Ranging to mildly uptrending markets; IS window 2025-07-01 to 2025-10-31 showed +2.3% BTC buy-and-hold, which is regime-compatible with mean-reversion longs off oversold dips
- **Trigger frequency**: ~10% of bars fire the entry condition (n_entry=262 over IS period)
- **Time of day**: No time-of-day restriction — 1h bar data is continuous, 24/7 crypto market
- **Volume**: No specific volume filter at entry; the 168h ROC signal already encodes multi-day momentum exhaustion

## Entry Condition

Enter LONG on BTCUSDT at the **close** of a 1-hour bar when:

- `roc_168h` (the 168-bar rolling log-return or simple return) <= **-0.056226** (i.e., BTC has fallen at least 5.6% over the past 168 hours)

This is an "entry_side: low" condition — fire only when the trailing weekly return falls into the bottom 10th percentile (threshold_percentile=90 of the low tail).

Execute via **MARKET BUY** at bar close (taker, Binance).

## Signals Needed

- `roc_168h`: 168-bar rolling rate-of-change of BTCUSDT close price (simple return: (close_now / close_168_bars_ago) - 1)

## Universe Rationale

BTCUSDT is the highest-liquidity crypto pair on Binance with the lowest effective spread (~1-2 bps) and deepest order book. It is the target rank-0 symbol in `top_robust` of `data/signal_briefs_v2/crypto_1h.json`. The `roc_168h` signal's IC for BTC is -0.2907 — the strongest cross-symbol (pooled avg_ic = -0.2093, all three symbols show same-sign IC, satisfying the robustness criterion min_abs_ic >= 0.04).

Note: BTC-specific entry-stats show mean_fwd_bps = -10 at the raw unfiltered entry horizon, which is weaker than ETHUSDT (+613 bps) and SOLUSDT (+733 bps). The pooled optimal_exit with PT_bps=1312 / SL_bps=451 is expected to carve out the profitable subset (61.96% pooled win rate). The execution designer must account for BTC's weaker raw edge at the terminal-return level.

## Knowledge References

- Iterate context `crypto_1h_btc_rsi_atr` (2026-04-18): positive IS return +4.30%, Sharpe +1.32, IR +1.039, 4-Gate PASS — confirms BTC mean-reversion on 1h bars can achieve viable IS performance with selective entry
- `crypto_1h_weekly_meanrev_btc` (2026-04-18): used roc-based signal but achieved only -6.46% IS return with 23 roundtrips — prior version may have lacked proper PT/SL exit discipline; this design explicitly uses brief's optimal_exit baseline
- Lesson: sparse entry (<10% of bars) with intentional filtering is acceptable and can produce positive IR vs buy-and-hold
- Lesson: trend_follow on zscore failed for BTC (4-Gate FAIL) — mean_reversion paradigm is the correct choice

## Constraints Passed To Execution-Designer

1. **Baseline exits from brief**: pt_bps=1312.07, sl_bps=450.79, horizon_bars=168 (time stop). Deviations must stay within ±20% of these values.
2. **Entry order**: MARKET BUY at bar close (taker). No LIMIT entry — the 1h bar resolution does not support intra-bar limit queue modeling.
3. **BTC-specific caveat**: Raw entry-level mean_fwd for BTC is weakly negative (-10 bps). The brief's PT/SL filter is load-bearing — execution must implement both hard profit target and stop loss; no pure time-exit-only variant.
4. **Entry threshold**: roc_168h <= -0.056226 (±10% band: -0.05061 to -0.06185). Do NOT loosen threshold above -0.0506 as it degrades selectivity.
5. **Horizon**: plan to hold up to 168 bars (7 days); exit at PT, SL, or 168-bar time stop — whichever triggers first.
6. **Fee**: 4 bps round-trip (taker both legs). Execution must not use LIMIT exit if it reduces fill certainty and creates adverse selection risk beyond the 4 bps budget.

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-17T00:00:00+00:00",
  "agent_name": "alpha-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/crypto_1h_btc_mean_rev_168h_iter1_alpha.md",
  "name": "crypto_1h_btc_mean_rev_168h_iter1",
  "hypothesis": "When BTCUSDT has lost more than 5.6% over the trailing 168 hours, the market has overextended to the downside and exhibits mean-reverting behavior over the subsequent 168-hour window — exploiting weekly return reversal (rank-0 from signal_brief).",
  "entry_condition": "Enter LONG on BTCUSDT at bar close via MARKET BUY when roc_168h <= -0.056226 (168-bar trailing return in bottom 10th percentile).",
  "market_context": "BTCUSDT 1h bars, 24/7 Binance spot market, ranging to mildly uptrending regime (IS window +2.3% BTC trend). Signal fires ~10% of bars. No time-of-day restriction.",
  "signals_needed": ["roc_168h"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "crypto_1h_btc_rsi_atr: BTC mean-reversion on 1h bars viable with selective entry (Sharpe +1.32, IR +1.039, 4-Gate PASS)",
  "signal_brief_rank": 1,
  "universe_rationale": "BTCUSDT is the top-liquidity Binance pair with strongest IC for roc_168h signal (-0.2907 vs pooled -0.2093); rank-0 in top_robust of crypto_1h.json signal brief.",
  "escape_route": null,
  "brief_realism": {
    "brief_ev_bps_raw": 445.49,
    "entry_order_type": "MARKET",
    "spread_cross_cost_bps": 1.0,
    "brief_horizon_ticks": 168,
    "planned_holding_ticks_estimate": 168,
    "horizon_scale_factor": 1.0,
    "symbol_trend_pct_during_target_window": 2.3,
    "regime_compatibility": "partial",
    "regime_adjustment_bps": 30.0,
    "adjusted_ev_bps": 414.49,
    "decision": "proceed",
    "rationale": "BTC IS window was +2.3% (mildly uptrending), which is regime-compatible with mean-reversion longs off oversold dips; partial match due to BTC-specific raw entry_stats showing weak mean_fwd (-10 bps vs pooled +445 bps), warranting a 30 bps haircut. Adjusted EV of +414 bps remains strongly positive, supporting a proceed decision contingent on execution enforcing both PT and SL exits."
  }
}
```
