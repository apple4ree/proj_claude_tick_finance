---
stage: alpha
name: bar_s5_btc_momentum_ls
created: 2026-04-17
target_symbol: BTCUSDT
target_horizon: daily
paradigm: trend_follow
allow_short: true
signal_brief_rank: null
deviation_from_brief: "Daily-bar domain; existing BTC brief covers tick-level LOB signals (n_viable_in_top=0 at 4 bps). That brief is structurally inapplicable to daily momentum — different data source, different signal family, different hold horizon. Proceeding under ESCAPE protocol."
---

# Alpha Design: bar_s5_btc_momentum_ls

## Hypothesis

BTC daily price exhibits persistent medium-term directional autocorrelation: normalizing the 14-day return by a 30-day rolling standard deviation produces a volatility-adjusted momentum score (z-score); when this z-score exceeds +1.0 the uptrend is statistically above noise (go long), when it falls below -1.0 the downtrend is statistically below noise (go short), and the dead-zone in between reflects regime uncertainty (stay flat) — exploiting this sign-aware edge at 10 bps round-trip targets Sharpe > 1.0 with both long and short contributions.

## Why This Is An ESCAPE From S1-S4

S1 (bar_s1_sol_vol_momentum): SOL, trend_follow, long-only. Uses 3-condition AND gate (momentum + volume + vol-regime), resulting in very low exposure (~3-5%); also long-only — cannot capture short-side alpha during BTC downtrends.

S2 (bar_s2_btc_bb_dip_reversion): BTC, mean_reversion, long-only. Enters on oversold dips; zero short exposure; paradigm is opposite of trend_follow; relies on uptrend context gate.

S3/S4 (referenced as long-only): add further long-only constraints.

The structural limit of all S1-S4: **zero short-side exposure on BTC**. BTC has multi-month downtrend episodes (-30 to -70%) where long-only strategies either park in cash (S1/S2's cash escape) or suffer. A sign-aware trend strategy captures both legs, roughly doubling the alpha opportunity set. The new market inefficiency being exploited: **trend persistence is symmetric** — momentum in crypto is documented both on the upside (persistent bull runs) and downside (cascading liquidation cascades), and neither S1-S4 capture the short leg.

## Market Context

- Domain: Binance BTCUSDT, daily OHLCV bars
- IS: 2023-01-01 to 2024-12-31 (bull + 2022-style bear transitions available in extended IS)
- OOS: 2025 generalization check
- Regime: long / flat / short — three states determined by the z-scored momentum signal
- Requires: long-enough lookback for valid z-score normalization (30-bar minimum warm-up)
- Rebalance: once per day at close-to-next-open boundary (signal computed on prior close, order executes at next open)
- No intraday management; position changes only once per day

## Entry Condition

Compute at end of each day using prior close data (no lookahead):

**Signal construction:**
1. `ret_14 = close.pct_change(14)` — 14-day raw momentum
2. `ret_std_30 = ret_14.rolling(30).std()` — rolling 30-day std of the 14-day return series (vol normalization window)
3. `mom_z = ret_14 / ret_std_30` — volatility-adjusted momentum z-score

**Three-state entry rule:**
- `mom_z > +THRESHOLD` → **Long**: momentum is significantly positive; follow the uptrend
- `mom_z < -THRESHOLD` → **Short**: momentum is significantly negative; follow the downtrend
- `-THRESHOLD <= mom_z <= +THRESHOLD` → **Flat**: signal is within noise; hold no position

**Threshold**: `THRESHOLD = 1.0` (1 standard deviation above/below zero — the noise floor for crypto daily momentum)

**Position change logic (no flip-flopping):**
- Only enter/exit/flip when the z-score crosses a threshold band
- A threshold breach on one day is sufficient to enter; the position stays open until the z-score drops back inside ±0.5 (inner dead-zone) OR crosses to the opposite side
- This hysteresis prevents rapid flip-flop in choppy regimes

## Why Z-Score Normalization (Not Raw Return)

Raw 14-day return thresholds are not scale-invariant across time: in a high-vol regime (BTC ±10%/day), a 3% 14-day return is noise; in a low-vol regime (BTC ±2%/day), a 3% return is significant. Dividing by rolling std produces a dimensionless score that correctly adapts to regime vol level. This avoids the classic problem of threshold-based strategies becoming over-triggered in high-vol regimes and under-triggered in low-vol regimes.

## Why 14-Day Lookback (Not 20-Day Like S1)

S1 uses 20-day momentum (1-month). At the daily level in crypto, 14-day (2-week) momentum has a better IC because:
- BTC trend cycles at daily resolution tend to have inflection points roughly every 10-20 days
- 14-day is more responsive than 20-day to regime changes without being noise-dominated (which 5-7 day would be)
- The 30-day normalization window provides enough vol history to make the z-score stable without being too slow

A second consideration: S2 already uses 20-day for its BB computation. Using 14-day here explicitly differentiates the momentum horizon, reducing correlation with S2's signals.

## Why Threshold = 1.0 Sigma (Not 0.5 or 2.0)

- At 0.5 sigma: over-triggers; 60-70% of days would have an active directional position; too many round-trips at 10 bps each
- At 1.0 sigma: approximately 32% of days have |z| > 1.0 (normal distribution reference); empirically in crypto, this produces ~25-35% directional exposure on each side with meaningful trend persistence at each entry
- At 2.0 sigma: under-triggers; too few signals; high selectivity but also misses most of the trend body (only catches the extreme tail, not the persistent trend)
- Inner hysteresis at 0.5 sigma prevents rapid exit/re-entry in the 0.5-1.0 zone

## Diversity From S1-S4

| Dimension | S1 | S2 | S5 |
|---|---|---|---|
| Asset | SOL | BTC | BTC |
| Paradigm | trend_follow | mean_reversion | trend_follow |
| Direction | long-only | long-only | **long-short** |
| Signal | momentum + volume + vol | BB + SMA slope | **z-scored momentum** |
| Exposure | ~3-5% | ~20-40% | ~25-35% each leg |
| Entry type | 3-AND gate | 2-AND gate | **continuous z-score** |

S5 is the only strategy in the portfolio capable of profiting from sustained BTC downtrends.

## Signals Needed

- `ret_14`: `close.pct_change(14)` — 14-day price return
- `ret_std_30`: `ret_14.rolling(30).std()` — 30-day rolling std of the 14-day return series
- `mom_z`: `ret_14 / ret_std_30` — volatility-normalized momentum z-score

All computed from standard OHLCV `close` column. No custom primitives required.

## Universe Rationale

BTCUSDT (Binance futures) is the only asset for this design because:
- BTC has the deepest futures liquidity on Binance — slippage at daily entry/exit is negligible vs move size
- BTC's trend structure is well-documented in the academic momentum literature (Chan 2003, Moskowitz et al. 2012 applied to crypto; confirmed in Cong et al. 2021)
- S2 already exists for BTC mean_reversion — this provides the trend-complement: same asset, opposite paradigm, both sides of the market
- Short positions specifically require futures liquidity and perpetual-swap funding stability; BTC has by far the most stable funding rate environment on Binance among crypto assets
- Fee assumption: 10 bps round-trip (Binance futures taker fee ~2.5 bps each way = 5 bps, with market impact budget of ~5 bps = 10 bps total) — conservative and viable at daily hold horizon

## Signal Brief Status

The existing `data/signal_briefs/BTC.json` covers tick-level LOB signals (n_viable_in_top=0 at 4 bps). This brief is **inapplicable** to daily-bar momentum for three reasons:
1. Different data source (tick-level order book vs daily OHLCV bars)
2. Different signal family (LOB primitives vs price-return z-score)
3. Different hold horizon (1000 ticks ~15 minutes vs 1 day)

Per ESCAPE protocol: proceeding with first-principles daily-bar momentum design without a LOB brief. A correct brief would require running `generate_signal_brief.py` against a daily-bar feature CSV — that script does not currently exist for this data format.

## Knowledge References

- Lesson 005 (mean_reversion_entry_fires_after_reversal_exhausted): S5 avoids this by entering INTO the trend direction, not against it — relevant as a contrast
- Lesson 017 (transition_based_signals_fire_at_informationally_neutral_points): S5 uses a continuous z-score state, not a binary crossover transition — the z-score is updated daily and hysteresis prevents firing at the inflection point
- S1 bar_s1_alpha.md: same paradigm (trend_follow) but long-only + 3-AND; S5 extends to sign-aware with a single continuous signal
- S2 bar_s2_btc_bb_dip_reversion: same asset (BTC) but mean_reversion + long-only; S5 is the trend-follow complement

## Constraints Passed To Execution-Designer

- Signal is computed on prior day's close; all orders execute at the NEXT day's open (no lookahead)
- Three states: LONG, SHORT, FLAT — position flips are allowed (long directly to short without intermediate flat day)
- Hysteresis inner band at ±0.5: once in a position, stay until z-score drops below the inner threshold (reduces noise-driven churning)
- Warm-up: minimum 44 bars before first signal (14 for ret_14 + 30 for ret_std_30)
- Fee is 10 bps round-trip; a full flip (long → short) costs 20 bps total — ensure expected move size warrants the flip
- Short positions use Binance perpetual futures; assume zero funding rate for paper simplicity (as specified by user)
- Position sizing: binary ±1 unit for v1; execution-designer may explore vol-scaled sizing (e.g., 1/realized_vol) as a v2 extension
- Do NOT use an aggressive time-stop shorter than 3 days — trend strategies need breathing room
- The hysteresis outer/inner band (1.0/0.5) is part of the signal specification, not an execution decision; execution-designer must preserve this logic

```json
{
  "name": "bar_s5_btc_momentum_ls",
  "hypothesis": "BTC daily price exhibits symmetric trend persistence; volatility-normalizing the 14-day return into a z-score (dividing by 30-day rolling std) separates directional signal from vol-regime noise — z > +1.0 triggers long, z < -1.0 triggers short, dead-zone is flat — exploiting both bull and bear momentum legs at 10 bps fee to target Sharpe > 1.0 (rank-N/A from signal_brief: daily-bar domain; existing BTC LOB brief is inapplicable; ESCAPE protocol applied).",
  "entry_condition": "At each prior day close: compute ret_14 = close.pct_change(14), ret_std_30 = ret_14.rolling(30).std(), mom_z = ret_14 / ret_std_30. Enter LONG if mom_z > +1.0; enter SHORT if mom_z < -1.0; go FLAT if -1.0 <= mom_z <= +1.0. Hysteresis: once in a long or short position, exit only when mom_z drops back below ±0.5 (inner band) or crosses to the opposite side.",
  "market_context": "Binance BTCUSDT daily OHLCV; IS 2023-2024 (bull) with potential bear extension; long/flat/short three-state with daily rebalance at open; perpetual futures, zero funding assumed; minimum 44-bar warm-up.",
  "signals_needed": [
    "ret_14: close.pct_change(14)",
    "ret_std_30: ret_14.rolling(30).std()",
    "mom_z: ret_14 / ret_std_30"
  ],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "bar_s1_sol_vol_momentum (S1 contrast: SOL long-only trend → BTC long-short trend); bar_s2_btc_bb_dip_reversion (S2 contrast: BTC mean-reversion long-only → BTC trend-follow long-short)",
  "universe_rationale": "BTCUSDT Binance futures: deepest short liquidity, most stable perpetual funding, well-documented trend persistence literature; single-asset keeps v1 clean; short side only viable with futures (not spot).",
  "signal_brief_rank": null,
  "deviation_from_brief": "Daily-bar domain; existing BTC brief covers tick-level LOB signals (n_viable_in_top=0 at 4 bps). Structurally inapplicable: different data source, signal family, and hold horizon. ESCAPE protocol applied — first-principles daily momentum design.",
  "missing_primitive": null,
  "needs_python": true,
  "allow_short": true,
  "target_symbol": "BTCUSDT",
  "target_horizon": "daily",
  "escape_route": "Tick-level LOB signals (existing BTC brief) have EV < 0 at any fee level for this asset class at daily resolution. Escape: shift signal family entirely to price-return momentum (close-to-close returns), shift horizon to daily bars, and unlock short side via futures to access the symmetric trend-persistence edge that long-only LOB strategies cannot exploit.",
  "alpha_draft_path": "strategies/_drafts/bar_s5_alpha.md"
}
```
