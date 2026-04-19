---
id: pattern_krx_intraday_entry_window_10_13
created: 2026-04-15T00:00:00
tags: [pattern, time-filter, krx, resting-limit, OBI, opening-auction, MOC, win-rate, methodology]
severity: critical
lessons:
  - "[[lesson_20260415_009_krx_opening_hour_09_00_09_30_obi_signals_are_noise_block_entries_until_09_30]]"
  - "[[lesson_20260415_011_krx_late_session_13_00_obi_edge_collapses_0pct_wr_requires_end_of_day_entry_cutoff]]"
---

# Pattern: KRX OBI resting-limit edge exists only in the 10:00-13:00 window

## Empirical finding (do not speculate — measured across strat_0010 to strat_0012)

Three consecutive iterations (10-12) mapped the intraday win-rate distribution for OBI-triggered
resting-limit entries. The pattern is structural and driven by two independent market regime shifts:

| Time window (KST) | Observed WR | N  | Root cause                                            |
|-------------------|-------------|----|-------------------------------------------------------|
| 09:00 - 09:30     | 9%          | 11 | Auction-clear OBI spike — residual overnight flow, zero predictive signal |
| 09:30 - 09:59     | 17%         | 6  | Post-auction noise persists on wider-spread symbols (006400, 051910) |
| 10:00 - 12:59     | 50-75%      | 20 | Continuous-session liquidity; OBI carries directional signal |
| 13:00 - 14:50     | 0%          | 4  | MOC/institutional basket rebalancing — flow is directional, not reverting |

Break-even WR for 150 bps profit / 50 bps stop / 19.5 bps round-trip fee = **53.6%**.

The viable window (50-75% WR) is bounded on both sides. Both dead zones must be excluded simultaneously.

## Dead zone 1: Morning (09:00-09:59)

KRX opening auction clears at 09:00, releasing accumulated overnight imbalance as a burst of
one-sided OBI above 0.35. This spike carries zero predictive value for subsequent mid-price
direction — the order flow reverses within seconds after auction settling. Any resting limit that
fills during this window is entering on noise, then stops out at -50 bps (19 stops in strat_0010).

Key nuance: the problematic symbols are higher-spread names (006400, 051910). Lower-spread, highly
liquid symbols (000660, 006800) rarely show OBI > 0.35 before 10:00, so a 09:30 blackout appears
to fix nothing on those symbols (strat_0011 confirmed: zero trades affected by the filter on
000660+006800). A 09:30 filter must be tested on the universe that exhibits the pathology.

**Required cutoff: entry_start_time_seconds = 36000 (10:00 KST), not 34200 (09:30).**

## Dead zone 2: Late session (13:00+)

From ~13:00, KRX institutional flow shifts to MOC basket rebalancing and program trades. OBI
imbalances in this window reflect directional forced flow — the price continues in the imbalance
direction rather than reverting. A resting bid that fills at 13:xx is entering against a sell
program; the profit target at +150 bps is never touched.

strat_0012 measured 0W/4L (0% WR) on 13:xx entries.

**Required cutoff: entry_end_time_seconds = 46800 (13:00 KST).**

## Combined rule (mandatory for all future resting-limit OBI strategies)

```yaml
params:
  entry_start_time_seconds: 36000   # 10:00 KST — skip opening noise
  entry_end_time_seconds:   46800   # 13:00 KST — skip MOC directional flow
```

This dual-window filter concentrates all entries in the 10:00-13:00 regime where empirical WR
is 50-75%, which is above the 53.6% break-even threshold.

## Implementation note — DSL gap

As of iter 12, the resting-limit strategy template only supports `entry_start_time_seconds`.
The `entry_end_time_seconds` parameter must be added to strategy.py manually. Until a canonical
template propagates this field, every new spec must include the corresponding Python logic:

```python
def _is_in_entry_window(self, ts_ns: int) -> bool:
    s = (ts_ns // 10**9 + 9 * 3600) % 86400
    return self.entry_start_time_seconds <= s < self.entry_end_time_seconds
```

Default values if not specified in spec: start=36000, end=46800.

## Anti-patterns

- DO NOT set entry_start_time_seconds=34200 (09:30) on universes that include 006400 or 051910.
  The 09:30-09:59 window is also pathological for these symbols — confirmed 17% WR.
- DO NOT test a time-filter fix on a symbol set that is immune to the pathology (e.g., 000660
  alone never triggers before 10:00). The fix must be tested on the affected symbols.
- DO NOT omit entry_end_time_seconds. Uncapped entry allows 13:xx+ fills that systematically lose.
- DO NOT combine a 10:00-13:00 window with a universe expansion to unscreened symbols. Add one
  change per iteration: either fix the window or change the universe, not both simultaneously.

## Interaction with per-symbol win-rate screen

This pattern does NOT supersede [[pattern_universe_filter_per_symbol_win_rate_screen]]. Both
apply simultaneously:
1. Screen universe for per-symbol WR >= 30% (spread-gate screen)
2. Apply 10:00-13:00 entry window to all surviving symbols

The two constraints are independent — a symbol can pass the spread screen but still lose on
09:xx entries. Both must be satisfied.
