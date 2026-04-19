---
id: pattern_005930_fee_incompatible_with_short_hold
created: 2026-04-14T00:00:00
tags: [pattern, fees, krx, oracle, breakeven, methodology, dataset, universe, anti-edge]
severity: critical
links:
  - "[[lesson_20260414_006_etf_universe_blocked_by_dataset_scope_kospi_equity_only]]"
  - "[[lesson_20260414_003_tax_heavy_korean_market_tight_spread_entry_filter_increases_turnover_fees_dominate_pnl]]"
  - "[[lesson_20260414_013_obi_sign_flip_long_only_fee_math_kills_positive_ev_at_30_20_bps_targets]]"
  - "[[lesson_20260414_014_mean_reversion_at_15_30_min_timescale_is_anti_edge_with_18_win_rate_and_oversized_lots_causing_cash_rejections]]"
  - "[[pattern_win_rate_ceiling_mandates_hold_duration]]"
---

# Pattern: 005930 long-only with 21 bps round-trip fee is structurally incompatible with any short-hold strategy

## Empirical finding (measured at meta-review K=9, iteration 10)

A direct oracle measurement across 8 IS dates establishes the **physical maximum upward move** within any 3000-tick window (~16 min) on 005930:

| Date | Max 3000t upward move | p95 max move | p75 max move |
|---|---|---|---|
| 20260316 | 81 bps | 64 bps | 38 bps |
| 20260317 | 67 bps | 41 bps | 20 bps |
| 20260318 | 98 bps | 49 bps | 24 bps |
| 20260319 | 100 bps | 74 bps | 25 bps |
| 20260320 | 75 bps | 50 bps | 25 bps |
| 20260323 | 102 bps | 74 bps | 32 bps |
| 20260324 | 122 bps | 101 bps | 48 bps |
| 20260325 | 57 bps | 37 bps | 21 bps |

**The 150 bps profit target recommended in `pattern_win_rate_ceiling_mandates_hold_duration` is physically unreachable at 3000 ticks on 7/8 IS dates.** The max upward move never reaches 150 bps on those dates even with a perfect clairvoyant oracle.

At 12000 ticks (1-hour hold), the max upward move across 3 tested dates is 61–231 bps, and oracle(150 bps) = 0–3%. The 150 bps target is still impossible on 2/3 dates.

## Why the prior pattern's recommendation was wrong

`pattern_win_rate_ceiling_mandates_hold_duration` measured the oracle win rate for a **21 bps target** (the fee floor), not for viable profit targets. The table shows:

- At 3000t: oracle ceiling to reach +21 bps = 40% ← this is what was measured
- At 3000t: oracle ceiling to reach +150 bps = 0% ← this was not checked before recommending 150 bps

The pattern correctly diagnosed the breakeven math but applied the oracle ceiling from the wrong (fee-floor) target to justify a 150 bps strategy. Iterations 7–9 used 150 bps targets that were structurally impossible to fill on most trading days.

## Why this means the dataset/universe is incompatible with any short-hold long strategy

Breakeven formula: `breakeven_W = (stop_bps + 21) / (profit_target_bps + stop_bps)`

For any viable target that 005930 can physically reach at 3000 ticks (say 50 bps):
- At 50 bps target, 25 bps stop: `breakeven_W = 46/75 = 61.3%`
- Oracle ceiling for +50 bps at 3000t: ~1.8% (20260317), 15% (20260320), 32% (20260323)
- On 6/8 IS dates, the oracle ceiling is well below the required 61.3% — impossible

For even tighter targets (20 bps):
- At 20 bps target, any stop s: `breakeven_W = (s+21)/(20+s)`. When s > 0: `(s+21)/(s+20) > 1` — the breakeven is always above 100%. Impossible by construction.

**There is no (profit_target, stop_loss) pair that simultaneously satisfies both physical achievability AND breakeven win rate requirements on 005930 with 21 bps round-trip fee at any hold duration under 12 hours.**

## What this implies about the 19 strategies tested

The 0/19 profitable rate is NOT primarily a signal quality problem. Even a perfect oracle cannot produce a profitable short-hold strategy on this symbol with these fees. The root cause is market structure incompatibility:

- 005930 daily price range: ~50-350 bps (wide variance day-to-day)
- 005930 3000-tick range: ~10-100 bps (too small for fee recovery at viable win rates)
- KRX fee structure: 1.5 bps commission + 18 bps sell tax = 21 bps non-negotiable floor

## Only empirically viable approach remaining

**Hold-all-day with trailing stop**: Enter at session first tick, no profit target, trail stop at -100 bps below peak, exit at session close EOD.

Observed daily session returns across 5 recoverable IS dates:
- 20260316: +211 bps
- 20260318: +195 bps
- 20260319: 0 bps (loses to fees)
- 20260324: +128 bps
- 20260325: -352 bps (without stop — trailing stop would limit this)

Win rate: 3/5 recoverable dates above fee floor (60%). A -100 bps trailing stop would limit the -352 bps day to approximately -100 bps, turning the overall expectation positive.

**This is a single daily directional bet with no entry signal, not a tick-level strategy.** It does not use any microstructure information. It is the only design that avoids both the exhaustion problem (no entry trigger) and the physical achievability problem (holds 60,000+ ticks = full session).

## Anti-patterns confirmed as structural (not tunable)

- DO NOT use profit targets above 50 bps for holds under 3000 ticks (physically unreachable on most days)
- DO NOT design a strategy around 150 bps profit target on 005930 at any intraday horizon
- DO NOT assume the oracle ceiling table in `pattern_win_rate_ceiling` applies to large targets — it was measured for the 21 bps fee-floor target only
- DO NOT continue searching for short-hold signals on 005930 — this is a fee/volatility incompatibility, not a signal design problem

## Escalation to user required

If the goal is to find a profitable intraday tick-level strategy (not a daily hold), this requires either:
1. A lower-fee universe (ETF with 0% sell tax, or futures with ~1-2 bps round-trip), OR
2. Short-selling capability on 005930 (enables fade-the-exhaustion trades that the pattern confirms exist), OR
3. A different dataset with higher intraday volatility

The current dataset (KOSPI equity, 40 tickers, long-only, 21 bps fee) is not compatible with profitable short-hold intraday strategies.
