---
id: pattern_eod_exit_dominance_signals_regime_attribution_not_edge
created: 2026-04-15
tags: [pattern, eod_dominance, regime_dependent, passive_maker, methodology, statistical-power, is-overfitting, exit_management, krx, 005930]
severity: critical
links:
  - "[[lesson_20260416_001_passive_maker_eod_exit_dominates_fill_at_ask_erodes_passive_edge_double_fill_is_strategy_bug]]"
  - "[[lesson_20260415_018_oos_regime_mismatch_invalidates_mean_reversion_passive_maker_evaluation]]"
  - "[[pattern_oos_regime_validity_gate]]"
---

# Pattern: EOD exit dominance signals regime attribution, not persistent edge

## Empirical finding

When a strategy's EOD forced-close contributes >= 50% of gross PnL across the IS window, the
return is regime-attributed — the IS trend did the work, not the signal or execution design.

In strat_0032 (the best passive-maker result at +0.573%, 8 RT, 75% WR on 005930):

- EOD exits contributed **78.6% of gross PnL** (+213 bps avg per EOD exit)
- PT=115 bps was never hit (0/8 roundtrips)
- Trailing stop was the designed exit mechanism — it also never activated meaningfully
- Net PnL without EOD would be approximately -0.45% (fee-negative)
- The IS window (20260316-20260325) is the **only** non-bearish 8-day window in the full dataset

This means the strategy "worked" by buying passively at bid and holding through an 8-day bull run
on 005930 (+6.5% buy-hold over IS). Any passive buyer in this window would have earned positive
returns via EOD close. The signal gates added no discrimination (OBI inverted, spread zero-delta).

## Diagnostic threshold

**Flag a result as EOD-dominated if:**

```
eod_exits_pnl / gross_pnl > 0.5
```

When this condition holds:
1. The PT/trailing designed exit is NOT working — the horizon assumption is wrong
2. The WR and return_pct are not evidence of signal edge — they are evidence of IS regime
3. Further refinement of the signal (OBI threshold, momentum gate) is wasted budget
4. The only valid fix is redesigning the exit to NOT require EOD

## Root cause — why EOD dominates

In a directional IS window (sustained trend), a resting passive limit buys on small dips.
Price then continues up (trend continuation) and the EOD forced-close captures the intraday
directional move as profit. This is NOT the passive-maker edge (spread capture); it is
inadvertent trend-following by holding through EOD.

The PT/trailing exits fire BEFORE price has moved enough in a single session. The designed
holding horizon (e.g., 1200 tick time-stop ~ 1 hour) is insufficient to capture the full
daily move. EOD closes out what the designed exits left on the table.

## What this implies for the current iteration arc (iter 12+)

1. **Do NOT fix the double-fill bug and re-run expecting a different result**: The double-fill
   affected one day (03/16) and added 1-2 phantom RTs. Even correcting to 6-7 true RTs, the
   EOD dominance and regime attribution remain. Fixing the bug is correct hygiene but will
   not unlock a structurally different return profile.

2. **Do NOT add an intraday momentum gate to this architecture**: The signal gates are not the
   binding constraint. EOD is the exit mechanism and the IS trend is the edge. Adding OBI >
   threshold or mid > session_open + N bps adds selectivity without fixing the exit problem.

3. **The path to genuine passive-maker edge requires a designed intraday exit that fires
   BEFORE EOD on the majority of profitable trades**: This means either:
   - A wider PT (>= 150 bps per pattern_win_rate_ceiling_mandates_hold_duration) that the
     price actually reaches intraday on the IS window, or
   - A trailing stop with sufficient activation threshold that locks gains within session
     (trailing_activation >= 100 bps, trailing_distance <= 30 bps)

4. **If strat_0025 (+0.597%, 18 RT, 4 symbols) was NOT EOD-dominated**: Verify its exit
   path distribution. If PT/trailing fired on >= 50% of its RTs, it represents a structurally
   different (and more valid) result. If strat_0025 is also EOD-dominated, then the entire
   passive-maker series has no confirmed designed-exit evidence.

## Mandatory pre-acceptance check for any passive-maker result

Before treating a result as signal evidence, compute:

```python
eod_fraction = n_eod_exits / n_roundtrips
eod_pnl_fraction = sum(rt.pnl for rt if rt.exit_type=='eod') / total_gross_pnl
```

- If `eod_fraction > 0.5` or `eod_pnl_fraction > 0.5` → flag as EOD-dominated, not signal evidence
- If IS window is a sustained directional trend (buy-hold > 2%) → further discount the result

## Relationship to pattern_oos_regime_validity_gate

The OOS pattern established that the IS window is the only non-bearish window in the dataset.
This pattern extends that finding to the strategy level: even within IS, a positive return
with EOD dominance is evidence of the IS trend, not a persistent structural edge. The two
patterns together rule out OOS validation as a path to confirming this strategy's edge —
the edge, if any, requires a non-EOD exit mechanism to be confirmed.

## Anti-patterns

- DO NOT treat 75% WR (n=8, p=0.145) + EOD dominance as confirmation of signal quality
- DO NOT tune signal thresholds (OBI, momentum) when the exit mechanism is EOD
- DO NOT compare strat_0032 (+0.573%) favorably to strat_0025 (+0.597%) based on RT count
  alone — the comparison requires knowing each strategy's EOD contribution fraction
- DO NOT proceed to OOS validation when IS result is EOD-dominated and IS is the only
  non-bearish window in the dataset
