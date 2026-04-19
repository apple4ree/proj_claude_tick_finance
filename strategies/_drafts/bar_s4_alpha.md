---
stage: alpha
name: bar_s4_sol_vol_regime_compress
created: 2026-04-17
target_symbol: SOLUSDT
target_horizon: daily
paradigm: volatility_regime
signal_brief_rank: null
deviation_from_brief: null
---

# Alpha Design: bar_s4_sol_vol_regime_compress

## Hypothesis

SOL daily returns exhibit positive drift during low-volatility compression regimes: when 10-day realized vol falls below its own 30-day rolling percentile (below the 30th percentile), SOL is in a low-vol regime that historically precedes directional expansion with positive skew, generating Sharpe > 0.8 at 30-60% exposure (rank-N/A from signal_brief — daily-bar domain, no LOB tick brief exists).

## Why S1 Failed (Parent Lesson)

S1 (bar_s1_sol_vol_momentum) combined three AND-gated conditions: 20-day momentum, volume spike >1.5x, and vol regime filter. The volume spike condition was the binding constraint — volume exceeds 1.5x its 20-day mean on fewer than ~5-10% of trading days. Combined with the momentum gate, this produced only ~3% exposure. The strategy was structurally incapable of achieving 30-60% exposure regardless of vol regime state.

S4 design principle: vol regime is the ONLY primary entry signal. No volume gate. No momentum confirmation. The vol percentile alone determines position state — enter when compressed, exit when expanded.

## Market Context

- Domain: Binance spot SOLUSDT, daily OHLCV bars
- IS period: 2023-01-01 to 2024-12-31 (crypto bull run with embedded -30/50% corrections)
- OOS: 2025 generalization check
- Regime required: realized vol in bottom 30th percentile of its own trailing distribution
- Rebalance: daily at open of next day (signal computed at prior close, no lookahead)
- Long-only with cash parking: in cash when vol is elevated (above 70th percentile) or in the intermediate range (wait for regime clarity)

### Why vol compression predicts positive returns in SOL

Crypto assets, particularly high-beta ones like SOL, exhibit a well-documented volatility cycle:
1. Compression phase: vol contracts, price consolidates in a narrowing range
2. Expansion phase: vol expands directionally — either breakout (more common in bull markets) or breakdown
3. In a bull-market base regime (long-term uptrend intact), breakouts dominate breakdowns during low-vol compressions

The asymmetry: during vol compression in an uptrend, the probability distribution of forward returns is right-skewed. The strategy exploits this skew by entering at compression and holding through the expected expansion, exiting when vol has risen above its historical median (the compression is over).

## Entry Condition

Enter long at next-day's open when ALL of the following hold at prior day's close:

1. **Low-vol regime (primary signal)**:
   `rvol_10_pct < 0.30`
   — The 10-day realized volatility (annualized std of log returns over trailing 10 bars) is below the 30th percentile of its own 30-day rolling distribution.
   Computed as: `rvol_10.rank(pct=True, method='average')` over the trailing 30-bar window.

2. **Trend-not-broken gate (catastrophe filter)**:
   `close[-1] > close[-1].rolling(50).mean() * 0.85`
   — Price is within 15% of the 50-day moving average. This prevents entering during a confirmed -50% breakdown where vol happens to compress temporarily after the initial crash.

3. **Vol-of-vol stability (optional enhancement — include if primary signal alone has too many whipsaws)**:
   `vol_of_vol_10 < vol_of_vol_30_median`
   — The 10-day standard deviation of rvol_10 is below its 30-day median, confirming that volatility itself is stable (not oscillating), i.e., we are in a genuinely quiet/compressed regime rather than a vol spike that briefly touched a low.

   Note: if signal count with condition 1+2+3 falls below 30-60% exposure target, drop condition 3 and use 1+2 only.

Exit to cash when:
- `rvol_10_pct > 0.70` — vol has expanded above the 70th percentile (regime has shifted)
- OR price falls below `close.rolling(50).mean() * 0.80` — catastrophic breakdown exit

## Signals Needed

- `log_ret`: `np.log(close / close.shift(1))` — daily log returns
- `rvol_10`: `log_ret.rolling(10).std() * np.sqrt(365)` — 10-day annualized realized vol
- `rvol_10_pct`: `rvol_10.rolling(30).rank(pct=True)` — percentile of current rvol within trailing 30-bar window
- `sma_50`: `close.rolling(50).mean()` — 50-day simple moving average for catastrophe filter
- `vol_of_vol_10`: `rvol_10.rolling(10).std()` — standard deviation of rvol_10 (vol-of-vol)

All are standard pandas/numpy operations over OHLCV close prices. No custom tick primitives required.

## Threshold Rationale (Brief Protocol Compliance Note)

No signal brief exists for SOLUSDT at daily-bar resolution — this is a daily OHLCV domain, not a tick-level LOB domain. The 30th / 70th percentile thresholds are derived from the structure of the hypothesis (bottom quartile = compressed, top 30% = expanded). These are symmetric regime boundaries that naturally target ~30% of trading days in compression state (entry eligibility) and ~30% in expansion state (exit pressure), giving the 30-60% exposure band. If IS backtesting reveals exposure outside this band, the percentile thresholds can be widened to 35th/65th (toward 40-50% exposure) or narrowed to 25th/75th (toward 20-30% exposure).

## Exposure Estimate

In a 500-day IS period:
- Bottom 30% of rvol_10 distribution: ~150 days potentially eligible
- After catastrophe filter (remove periods where price is >15% below SMA-50): ~120-140 days
- Expected exposure: 120-140 / 500 = 24-28% ... if entries are point-in-time

However, this is a regime strategy: once entered in a low-vol regime, the position is HELD until the regime exits (rvol_10_pct > 0.70). Typical low-vol regimes in SOL last 10-30 days. So exposure is computed as fraction of days INSIDE a low-vol regime, not just the first day. Estimate: 30-50% exposure, comfortably within the 30-60% target.

If realized exposure falls below 30%, reduce vol percentile entry threshold from 30th to 40th percentile.

## Comparison to S1

| Dimension | S1 (bar_s1) | S4 (bar_s4) |
|---|---|---|
| Paradigm | trend_follow | volatility_regime |
| Primary signal | 20-day momentum | rvol_10 percentile |
| Volume gate | YES (1.5x, binding) | NO |
| Vol as role | Filter (secondary) | Primary entry signal |
| Expected exposure | ~3% (failed) | ~30-50% (target met) |
| Entry logic | State = momentum confirmed | State = vol compressed |
| Exit logic | Any condition fails | Vol regime exits (>70th pct) |

## Universe Rationale

SOLUSDT retained from S1 because:
- S1's failure was structural (gate configuration), not a symbol failure
- SOL's high realized volatility makes percentile-based vol regime identification more precise (wider dynamic range between compressed and expanded states)
- BTC already covered by S2 (mean_reversion); ETH covered by potential S3; SOL provides vol-regime paradigm diversity
- High-beta crypto assets like SOL exhibit more pronounced vol compression/expansion cycles than BTC, making the regime signal more reliable

## Knowledge References

- S1 (bar_s1_alpha.md): Parent strategy; 3% exposure failure due to volume gate. Vol component demoted from filter to primary driver in S4.
- Lesson 017 (transition-based signals fire at neutral points): S4 uses a persistent STATE condition (rvol_10_pct < 0.30), not a crossover event, avoiding the "already-done" problem.
- Lesson 005 (mean-reversion entry fires after reversal exhausted): S4 does not enter on reversals; it enters during compression and holds through expansion. Not a mean-reversion of price — a regime-state detection.
- Lesson 009 (KRX opening hour noise): Not applicable to daily bars, but analogous to time-of-day filtering — here we use vol regime as the equivalent regime filter.

## Constraints Passed To Execution-Designer

- Signal computed at prior day's close; entry at next day's open (no lookahead)
- Warm-up: minimum 50 bars required before first signal (SMA-50 lookback; rvol percentile rolling window = 30 bars)
- Position: binary long or cash in v1 (no fractional sizing)
- Regime exit (rvol_10_pct > 0.70) is a SOFT trigger: exit at next day's open, not immediately
- Catastrophe exit (price < SMA-50 * 0.80) is a HARD trigger: exit immediately if intraday data available, else next open
- Do NOT add a time-stop shorter than 10 days — vol regimes last 10-30 days and a short time-stop would exit before the expansion phase pays out
- Fee is 10 bps round-trip; expected holding period is 10-30 days implying 0.3-1.0 bps/day fee drag, negligible vs SOL daily vol
- Execution-designer should use brief's optimal_exit baseline: given no brief exists, use: profit_target = 15% (typical low-to-high-vol transition move), stop_loss = 12% (below compression entry, breaks regime thesis), trailing preferred over hard target

```json
{
  "name": "bar_s4_sol_vol_regime_compress",
  "hypothesis": "SOL daily returns are right-skewed during low-volatility compression regimes (rvol_10 below the 30th percentile of its trailing 30-day distribution); entering long when vol is compressed and exiting when vol expands above the 70th percentile exploits the asymmetric breakout payoff in bull-market context at 30-50% exposure — rank-N/A from signal_brief (daily-bar domain, no LOB brief exists).",
  "entry_condition": "Enter long at next-day open when: (1) rvol_10_pct < 0.30 — 10-day realized vol is in the bottom 30th percentile of its trailing 30-bar window; (2) close > SMA(50) * 0.85 — price has not broken down catastrophically. Exit when rvol_10_pct > 0.70 (regime shifted) or price < SMA(50) * 0.80 (breakdown).",
  "market_context": "Binance SOLUSDT daily OHLCV; IS 2023-2024 crypto bull run; long-only with cash parking; daily rebalance at next-day open. Strategy is active during vol-compression regimes (~30-50% of trading days) regardless of price direction. Inactive when vol is elevated (above 70th percentile).",
  "signals_needed": [
    "log_ret: np.log(close / close.shift(1))",
    "rvol_10: log_ret.rolling(10).std() * np.sqrt(365)",
    "rvol_10_pct: rvol_10.rolling(30).rank(pct=True)",
    "sma_50: close.rolling(50).mean()",
    "vol_of_vol_10: rvol_10.rolling(10).std() [optional, for condition 3]"
  ],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "volatility_regime",
  "multi_date": true,
  "parent_lesson": "bar_s1_sol_vol_momentum — S1 achieved 3% exposure due to 3-AND gate with binding volume spike condition; S4 removes volume gate entirely, uses vol percentile as sole primary entry signal",
  "universe_rationale": "SOLUSDT: retained from S1 (failure was gate configuration not symbol); SOL has high-dynamic-range vol cycles making percentile regime detection more precise than BTC; complements S2 (BTC mean_reversion) with a different asset and different paradigm.",
  "signal_brief_rank": null,
  "deviation_from_brief": "No signal brief exists for SOLUSDT at daily-bar resolution. Percentile thresholds (30th/70th) derived from regime hypothesis structure targeting 30-50% exposure. Viable under 10 bps fee given 10-30 day holding periods.",
  "target_symbol": "SOLUSDT",
  "target_horizon": "daily",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/bar_s4_alpha.md"
}
```
