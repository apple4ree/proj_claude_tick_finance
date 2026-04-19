---
id: pattern_win_rate_ceiling_mandates_hold_duration
created: 2026-04-14T00:00:00
tags: [pattern, win-rate-estimate, fees, hold-time, anti-edge, krx, methodology, breakeven, oracle]
severity: critical
lessons:
  - "[[lesson_20260414_003_tax_heavy_korean_market_tight_spread_entry_filter_increases_turnover_fees_dominate_pnl]]"
  - "[[lesson_20260414_013_obi_sign_flip_long_only_fee_math_kills_positive_ev_at_30_20_bps_targets]]"
  - "[[lesson_20260414_014_mean_reversion_at_15_30_min_timescale_is_anti_edge_with_18_win_rate_and_oversized_lots_causing_cash_rejections]]"
  - "[[lesson_20260414_021_time_exit_suppresses_avg_win_bps_below_resting_limit_target]]"
---

# Pattern: Oracle win-rate ceiling mandates minimum hold duration on 005930

## Empirical finding (do not speculate around this — it is measured)

An oracle analysis across 7 IS dates (623k ticks) for 005930 measured the **maximum physically achievable win rate** at each holding horizon — i.e., the fraction of entry ticks where the future price reaches at least 21 bps above entry (the round-trip fee floor) at ANY point within the horizon. No real signal can exceed this ceiling.

| Holding horizon | Approx wall-clock time | Oracle win-rate ceiling |
|---|---|---|
| 100 ticks | ~1 min | 0.6% |
| 500 ticks | ~4 min | 10% |
| 1000 ticks | ~5 min | 23% |
| 2000 ticks | ~11 min | 34% |
| 3000 ticks | ~16 min | 40% |
| 5000 ticks | ~27 min | 51% |
| 8000 ticks | ~44 min | 58% |
| 12000 ticks | ~1.1 hr | 65% |

(Timing: ~71,500 ticks per session on 005930; KRX session = 390 min)

## Why short-horizon strategies are mathematically impossible to profit from

At 100 ticks, even a perfect clairvoyant oracle wins only 0.6% of the time. A real signal operating at this horizon cannot exceed 0.6% win rate regardless of signal quality. The breakeven win rate for any profitable strategy with 21 bps fee floor is at minimum ~21% (achievable only with 200 bps target / 25 bps stop). This is unreachable below ~1500 ticks horizon.

**Conclusion: no tick-horizon strategy (< 1000 ticks hold) can be profitable on 005930 regardless of signal design. This is not a signal quality problem — it is a physical market microstructure constraint.**

## Breakeven win-rate feasibility table (21 bps round-trip fee)

Formula: breakeven_W = (stop_bps + 21) / (profit_bps + stop_bps)

| Profit target (bps) | Stop loss (bps) | Breakeven W | Min oracle-viable horizon |
|---|---|---|---|
| 50 | 25 | 61% | Not achievable (oracle ceiling < 61% at any horizon tested) |
| 75 | 25 | 46% | Not achievable reliably (oracle reaches ~51% at 5000t) |
| 100 | 25 | 37% | 5000+ ticks (oracle 51%) — just barely viable |
| 150 | 25 | 26% | 3000+ ticks (oracle 40%) — viable |
| 150 | 50 | 36% | 5000+ ticks (oracle 51%) — viable |
| 200 | 25 | 20% | 2000+ ticks (oracle 34%) — viable |
| 200 | 50 | 28% | 3000+ ticks (oracle 40%) — viable |
| 200 | 75 | 35% | 5000+ ticks (oracle 51%) — viable |

**Actionable rule: minimum holding target must be 3000 ticks; profit target must be >= 150 bps; stop must be <= 50 bps. Any combination outside these ranges requires an oracle win rate that this market does not supply.**

## Implications for strategy design

1. **Lot-sizing constraint**: At 3000+ tick hold, position is committed for ~16 min. 000660 at 934,500 KRW × lot_size=1 = 9.3% of 10M capital per lot. Use lot_size=1 for both symbols; never use lot_size >= 2 on 000660.

2. **Signal role shifts from trigger to filter**: At 3000-tick hold, the signal does not need to predict the next 27 minutes tick-by-tick. It needs to identify which 27-minute windows have directional momentum. Use VWAP deviation, day-open momentum, or time-of-day regime as filter rather than LOB microstructure signals that fire at absorption.

3. **Mean reversion is ruled out at this horizon**: 005930 tick return autocorrelation at lag=500 is +0.002 and at lag=1000 is +0.003 — indistinguishable from zero. There is no measurable mean-reversion signal. Any mean-reversion strategy at this horizon is noise-trading.

4. **Trailing stop is required**: A 150 bps profit target with 3000-tick minimum hold needs a trailing stop to lock in gains if price runs early. Otherwise wins and losses are symmetric and fees determine outcome.

5. **Intraday trend is the only viable signal direction**: The oracle ceiling rises monotonically with horizon, meaning the price does move directionally across sessions. The question is whether a signal can identify which direction. Day-open momentum (first N ticks after open directional bias) and VWAP deviation are the two candidates that have not yet been tested.

## Anti-patterns that caused 16 consecutive losing strategies

- DO NOT enter on a 100-tick or shorter lookback signal and exit within 200 ticks. Oracle ceiling = 0.6%. Physically impossible to profit.
- DO NOT use OBI or LOB imbalance as a primary entry trigger. All 5+ tests show anti-edge (fires after absorption). These are post-event descriptors.
- DO NOT use mean reversion on 005930 at any timescale. Autocorrelation is zero; wins and losses are coin-flips minus fees.
- DO NOT stack entry conditions that individually fire on > 5% of ticks. Combined they become regime descriptors (Mode D) not signals.
- DO NOT use 000660 as the primary target. Price of 934,500 KRW constrains lot_size to 1, which is viable but leaves no room for error.

## Mandatory pre-spec checks (append to pattern_spec_calibration_failure checklist)

6. **Oracle ceiling check**: Estimate the holding horizon in ticks. Look up oracle win-rate from this table. Verify breakeven_W is below the oracle ceiling. If not, extend the holding horizon or widen profit/stop ratio before proceeding.
7. **Trend vs mean-reversion check**: For 005930, confirm signal direction is WITH momentum, not against it. Autocorrelation is near zero so mean-reversion has no edge advantage — but anti-trend entries are confirmed losers across 8 strategies.

## Empirical validation (resting-limit series)

The oracle table predicted that 3000+ tick unbounded hold with 150/50 bps target was viable (oracle ceiling ~40% vs 35.5% breakeven). This was confirmed in practice: removing the 8000-tick time exit in strat_0024 produced the first positive return in the series. See [[lesson_20260414_021_time_exit_suppresses_avg_win_bps_below_resting_limit_target]] and [[lesson_20260414_021_time_exit_suppresses_avg_win_bps_below_resting_limit_target]].
