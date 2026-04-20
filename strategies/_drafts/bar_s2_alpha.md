---
stage: alpha
name: bar_s2_btc_bb_dip_reversion
created: 2026-04-17
target_symbol: BTCUSDT
target_horizon: daily
paradigm: mean_reversion
signal_brief_rank: null
deviation_from_brief: null
---

# Alpha Design: bar_s2_btc_bb_dip_reversion

## Hypothesis

BTC daily price exhibits short-horizon mean-reversion after oversold dips within an intact uptrend: when the close touches or breaches the lower Bollinger Band (20-day, 2-std) while the 50-day MA slope is still positive, the subsequent 1-5 day rebound to the mid-band yields a positive expected return that more than covers the 10 bps round-trip fee, at an exposure level (~25-40% of trading days) that meaningfully participates in the bull-market trend.

## Why Mean-Reversion, Not Trend-Follow

S1 (bar_s1_sol_vol_momentum) uses trend_follow with a 3-condition AND gate, producing only ~3% exposure — too selective to compound returns. Mean-reversion on BTC daily has a fundamentally different exposure profile: in a bull market, BTC corrects to its lower Bollinger Band roughly every 10-20 days and reliably bounces, so the strategy holds positions for clusters of days rather than sitting in cash. The paradigm difference is directional: S1 enters on momentum confirmation, S2 enters specifically AGAINST the short-term move (buying weakness) with a trend anchor preventing knife-catching.

## Market Context

- Domain: Binance spot BTCUSDT, daily OHLCV bars
- IS: 2023-01-01 to 2024-12-31 (crypto bull run; BTC +300% with 20-40% interim corrections)
- OOS: 2025 generalization check
- Regime required: positive 50-day MA slope (uptrend intact), meaning the strategy sits in cash during bear regimes
- Rebalance: daily at open of next day after signal fires on prior close
- Long-only (default); long-short extension notes in Constraints

## Entry Condition

Enter long the NEXT day's open when BOTH of the following hold on the prior day's close:

1. **Bollinger Band lower touch** (primary signal):
   `close[-1] <= BB_lower[-1]`
   where `BB_lower = SMA(close, 20) - 2.0 * std(close, 20)`
   — Price has dipped to or below the lower Bollinger Band, indicating a short-term oversold condition.

2. **Trend anchor** (regime gate):
   `SMA(close, 50)[-1] > SMA(close, 50)[-6]`
   — The 50-day simple moving average is higher now than 5 trading days ago (slope is positive), confirming the broader trend has not broken down.

Hold until exit (defined by execution-designer), but the signal rationale targets reversion to the 20-day mid-band (BB_mid = SMA_20).

### Why 2 conditions not 3

S1's 3-condition AND reduced exposure to ~3%. Two conditions here maintain selectivity (noise-filtering via trend anchor) without over-gating. In a 2-year IS with ~500 trading days, BTC touches BB_lower roughly 25-40 times; adding a third AND condition would shrink that to <10 signals.

## Signals Needed

- `bb_lower`: `close.rolling(20).mean() - 2.0 * close.rolling(20).std()`  
  — 20-day Bollinger Band lower band (2-sigma)
- `bb_mid`: `close.rolling(20).mean()`  
  — 20-day simple moving average (also the BB midline, serves as mean-reversion target)
- `sma_50`: `close.rolling(50).mean()`  
  — 50-day simple moving average
- `sma_50_slope`: `sma_50 - sma_50.shift(5)`  
  — 5-bar change in SMA-50 (positive = uptrend intact)
- Composite entry signal: `(close <= bb_lower) & (sma_50_slope > 0)`

All inputs are standard OHLCV pandas operations — no custom primitives required.

## Why Bollinger Band Lower Touch (Not RSI)

RSI oversold (<30) and BB lower touch are correlated but BB lower touch is sharper: it is a direct volatility-normalized distance measure from the recent mean. RSI can remain <30 for many consecutive days in a trending decline, whereas a single-bar BB lower touch is a more precise "today specifically hit an extreme" signal. BB touch also naturally widens during high-vol periods, avoiding over-triggering in calm markets.

Choosing BB over RSI also differentiates this alpha from the most common RSI-bounce strategies already well-known in the space.

## Why 50-Day MA Slope (Not 50/200 Cross)

A 50/200 MA cross ("golden cross") changes state very slowly — once the signal turns negative, the market has already fallen 20-30%. The 5-day slope of SMA-50 is more responsive: it turns negative within 1-2 weeks of a sustained breakdown, limiting exposure to protracted bear legs. This avoids the knife-catching failure mode (Lesson 005) where mean-reversion entries fire repeatedly into a downtrend.

## Exposure Estimate

BTC in a 2-year IS with 2-sigma lower band touches: approximately 25-40 entry signals. If average hold is 3-7 days (to mid-band), that implies 75-280 days held = 15-55% exposure. Combined with the trend gate (exits during bear regimes), expect IS exposure in the 20-40% range, meeting the >20% target.

## BTC vs Buy-Hold Comparison

BTC buy-hold IS Sharpe = 2.01 in a strong bull. This strategy does NOT aim to beat buy-hold Sharpe outright in-sample — that would require either better timing OR a long-short extension. Instead the design targets:
- Similar or slightly lower Sharpe than buy-hold (1.0-2.0 range)
- Meaningfully lower max drawdown (sitting in cash during extended corrections)
- Better risk-adjusted performance OOS when/if the trend weakens

A long-short extension (short when price > BB_upper AND SMA-50 slope negative) is feasible with the same primitives but is deferred to execution-designer's decision.

## Universe Rationale

BTCUSDT chosen because:
- More liquid and less volatile than SOL (daily vol ~3-5% vs SOL ~6-10%), making 2-sigma BB touches more reliable as mean-reversion signals rather than continuation patterns
- BTC bull market in IS period has cleaner corrective structure (sharp V-recoveries) than SOL which has more jagged noise
- BTC buy-hold Sharpe 2.01 sets a clear benchmark; if this strategy achieves Sharpe >1.0 with lower drawdown, it provides genuine timing value
- S1 already covers SOL; BTCUSDT provides diversification across assets

## Knowledge References

- Lesson 005 (mean_reversion_entry_fires_after_reversal_exhausted): avoided by entering on the SAME day as the BB touch (not waiting for a confirmation candle that fires after the reversal is already done)
- Lesson 017 (transition_based_signals_fire_at_informationally_neutral): this design uses a current-state condition (close <= bb_lower TODAY), not a crossover/transition event, reducing the "already-done" problem
- S1 bar_s1_alpha.md: deliberately contrasted — S1 was 3-condition AND + trend_follow + SOL; S2 is 2-condition AND + mean_reversion + BTC

## Constraints Passed To Execution-Designer

- Entry executes at the NEXT day's open (signal computed at prior close, no lookahead)
- Warm-up: minimum 50 bars required before first signal (SMA-50 lookback)
- Primary exit target: price returns to bb_mid (SMA-20); this is the mean-reversion completion signal
- Secondary exit consideration: if SMA-50 slope turns negative while in position, close immediately (trend break while holding)
- Do NOT use a time-stop shorter than 5 days — the reversion to mid-band typically takes 3-7 days, and a 1-2 day time-stop would truncate most winners
- Fee is 10 bps round-trip; reversion to mid-band from lower band is typically 2-6%, which is 20-60x the fee cost — fee is not a binding constraint at this horizon
- Position sizing: binary (full-long or full-cash) for simplicity in v1; execution-designer may explore fractional sizing based on distance-to-BB-lower
- Long-short extension (shorting when BB_upper is breached + trend negative) is optional — execution-designer decides

```json
{
  "name": "bar_s2_btc_bb_dip_reversion",
  "hypothesis": "BTC daily price mean-reverts from lower Bollinger Band (20-day, 2-sigma) to the midline within 1-7 days when the 50-day MA slope confirms the broader uptrend is intact; rank-N/A from signal_brief (daily-bar domain, no LOB brief exists), buying this oversold dip yields positive EV well above the 10 bps fee at 20-40% exposure.",
  "entry_condition": "Enter long at next-day open when BOTH hold at prior close: (1) close <= BB_lower (20-day, 2-std Bollinger Band lower), confirming an oversold daily dip; (2) SMA(50)[-1] > SMA(50)[-6], confirming 50-day MA slope is positive (uptrend intact). Exit when price reaches BB_mid (SMA-20) or SMA-50 slope turns negative.",
  "market_context": "Binance BTCUSDT daily OHLCV; IS 2023-2024 crypto bull run; long-only with cash parking during bear regimes (SMA-50 slope negative); daily rebalance at open. Requires uptrend context — strategy is inactive during sustained bear markets.",
  "signals_needed": [
    "bb_lower: close.rolling(20).mean() - 2.0 * close.rolling(20).std()",
    "bb_mid: close.rolling(20).mean()",
    "sma_50: close.rolling(50).mean()",
    "sma_50_slope: sma_50 - sma_50.shift(5)"
  ],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "bar_s1_sol_vol_momentum (S1 contrast: trend_follow 3-AND → mean_reversion 2-AND; SOL → BTC; momentum-entry → dip-entry)",
  "universe_rationale": "BTCUSDT: cleaner V-shaped mean-reversion structure in bull cycles vs SOL; lower daily vol makes 2-sigma BB touches more reliable reversion triggers; complements S1 (different asset, different paradigm, different entry logic).",
  "signal_brief_rank": null,
  "deviation_from_brief": null,
  "target_symbol": "BTCUSDT",
  "target_horizon": "daily",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/bar_s2_alpha.md"
}
```
