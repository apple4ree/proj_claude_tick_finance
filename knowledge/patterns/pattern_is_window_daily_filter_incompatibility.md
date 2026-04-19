---
id: pattern_is_window_daily_filter_incompatibility
created: 2026-04-15T00:00:00
tags: [pattern, methodology, sample-size, statistical-power, regime-filter, is-overfitting, iteration-stagnation, zero-trades, krx, passive-maker]
severity: critical
links:
  - "[[lesson_20260415_025_session_gate_trend_blind_multi_day_downtrend_passes_gate_trailing_floor_consumed_by_half_spread]]"
  - "[[pattern_sample_size_gate_before_parameter_tuning]]"
  - "[[pattern_win_rate_ceiling_mandates_hold_duration]]"
  - "[[pattern_oos_regime_validity_gate]]"
---

# Pattern: Daily / multi-day filters are structurally incompatible with an 8-day IS window

## Root cause

The IS window is 8 trading days (20260316–20260325). Any filter evaluated at daily or multi-day
granularity consumes a substantial fraction of the base period before it can produce a signal.
When combined with other filters (session gate, spread gate), the compound effect eliminates
nearly all tradeable days, producing zero or near-zero trade counts that invalidate the iteration.

Observed compound failure (iters 8/9 of this session):

| Filter added | Days surviving | Trades | Outcome |
|---|---|---|---|
| 3-day trend lookback | 5 of 8 (cold start) | 0 | Trend + session gate = all days blocked |
| 1-day trend lookback | 6 of 8 | 2 | Only 034020 traded; 005930 skipped entirely |
| No daily filter | 8 of 8 | 14 | Viable base (strat_0029) |

The lookback=3 cold start alone consumed 3/8 IS days (37.5%). With session gate and spread gate
added, 0 days remained that satisfied all three conditions simultaneously.

## The asymmetry trap

Daily/multi-day filters are attractive because:
- They correctly diagnose the failure mode (regime mismatch — 034020 in -7.3% downtrend)
- They are simple to implement
- They appear to have worked in prior sessions (strat_0025 session-drop gate)

But on an 8-day IS window they are structurally broken because:
- Each additional daily gate reduces the effective N from 8 to at most 4–5
- Cold start of a multi-day lookback is not free — it costs lookback_days from the base pool
- Compound gate probability: three independent binary gates each selecting 70% of days yields
  0.70^3 = 34% of days surviving, or 2–3 days from an 8-day window
- N=2–3 trading days yields N=2–4 roundtrips, which is statistically meaningless

## Why session-drop worked but trend filters don't

`session_drop_gate_bps` (strat_0025) is an **intraday** filter: it checks the current session's
intraday return from the day's open. It does not consume prior days. It fires within the current
session, so it has 8 qualifying opportunities. The multi-day trend filter (close[t-3] < close[t-1])
requires 3 days of history and evaluates across sessions — a fundamentally different temporal scope.

## Mandatory pre-spec check (add to spec-writer Step 2)

Before creating any strategy directory, verify:

```
IF any filter is evaluated at daily or multi-day granularity AND IS window <= 10 days:
   → REJECT the filter. Return the following error before directory creation:
     {"error": "daily_filter_on_short_is",
      "description": "Filter <name> requires <N>-day lookback on an 8-day IS window.
                       After cold start, only <8-N> days are available. Combined with
                       session+spread gates, expected trade count < 3. Use an intraday
                       substitute instead."}
```

Intraday substitutes for each disallowed daily filter:

| Disallowed | Allowed intraday substitute |
|---|---|
| close[t-1] > close[t-3] | session_drop_gate_bps (current session return from open) |
| 3-day MA above 10-day MA | mid_return_bps(lookback=5000) > 0 (current session momentum) |
| daily volume rank | krw_turnover(lookback=300) relative to session threshold |
| previous-day close filter | obi snapshot at session open as regime descriptor |

## Viable regime filter approach on 8-day IS

Intraday-only regime filtering (no cross-session lookback):

1. **session_drop_gate_bps**: Track the first mid of the current session (day-open reference).
   If (current_mid - session_open_mid) / session_open_mid * 10000 < -gate_bps, block entry.
   This is confirmed working: strat_0025 (session_drop=80) raised WR 53.3%→66.7%.

2. **mid_return_bps(lookback=N) at session open**: Read mid return from session start to
   current tick. If < threshold, skip. Lookback must be within the current session only.

3. **time-of-day gating only**: Restrict entry to windows known to have signal (10:00–13:00).
   No cross-session state required.

## Escalation rule

If the primary symptom being addressed is "strategy enters downtrend symbols" and a multi-day
trend filter seems necessary, the correct response is **symbol-level pre-screening at IS setup
time**, not a dynamic daily filter during backtest:

- Pre-screen: compute buy-hold return for each symbol over the IS window. Exclude symbols with
  buy-hold < 0% (run once, not per-tick). This is already captured in `pattern_oos_regime_validity_gate`.
- This removes structurally declining symbols (e.g., 034020 at -7.3% IS buy-hold) before any
  backtest runs, without consuming the IS day budget.

## Anti-patterns confirmed from this session

- DO NOT add a multi-day lookback filter to any strategy evaluated on <= 10-day IS window.
- DO NOT combine daily trend filter + session gate + spread gate on 8-day IS (triple compound
  eliminates all days).
- DO NOT diagnose "regime mismatch on symbol X" and fix it with a daily filter — fix it by
  removing the symbol from the universe (pre-screening is cheaper than runtime filtering).
- The session_drop_gate_bps already covers single-session downtrend protection for 005930.
  Extending it to multi-day is the wrong direction; the correct fix is symbol pre-screening.
