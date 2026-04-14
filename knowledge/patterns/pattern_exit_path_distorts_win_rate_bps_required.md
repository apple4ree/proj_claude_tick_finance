---
id: pattern_exit_path_distorts_win_rate_bps_required
created: 2026-04-14T00:00:00
tags: [pattern, win_rate, breakeven, exit_management, time_exit, resting_limit, fee_math, methodology]
severity: critical
lessons:
  - "[[lesson_20260414_013_obi_sign_flip_long_only_fee_math_kills_positive_ev_at_30_20_bps_targets]]"
  - "[[lesson_20260414_019_resting_limit_win_rate_counts_time_exits_as_wins_distorting_breakeven_math]]"
  - "[[lesson_20260414_018_hold_all_day_open_entry_23pct_win_rate_invalidates_pre_pattern_60pct_oracle_projection]]"
---

# Pattern: Exit-path mix distorts win_rate — use avg_win_bps / avg_loss_bps as primary diagnostic

## The failure mode

win_rate_pct counts any positive-return roundtrip as a win, regardless of whether the
profit-target exit or the time/trailing-stop exit actually fired. When a strategy has
multiple exit paths (profit limit, time-exit, trailing stop), the realized win-size
distribution is left-skewed relative to the nominal profit target:

- A resting SELL LIMIT at +100 bps that hits = +79 bps net (fee-adjusted win)
- A 2000-tick time exit at +5 bps = −16 bps net (fee-adjusted loss, counted as a win)
- A stop at −30 bps = −51 bps net (correct loss)

Lesson 019 confirmed: 272210 hit 53.85% win_rate yet returned −0.015% because most
"wins" were time exits at +5–15 bps, not the +100 bps resting limit. Lesson 013
showed 82% breakeven win rate was required at 30/20 bps targets with 21 bps fees —
a feasibility constraint that win_rate alone would mask if exit paths mix.

## Why win_rate alone is insufficient

The breakeven formula W × avg_win_net = (1−W) × avg_loss_net requires *realized*
avg_win and avg_loss magnitudes, not nominal targets. When exit paths include
time exits or trailing stops, the realized win size is a distribution (not a point),
and its mean can be far below the target. A 53% win rate looks above breakeven for
a 100/30 target (37% required), but if avg realized win = +10 bps and avg realized
loss = −51 bps, the actual EV is: 0.53×(−11) + 0.47×(−51) = −29.8 bps per trade.

## The fix: avg_win_bps and avg_loss_bps (now in report.json)

As of iteration 3, the engine computes and reports `avg_win_bps` and `avg_loss_bps`
in every report.json. These are fee-adjusted net PnL / buy-side notional in bps.

**Primary diagnostic rule**: A strategy is EV-positive only when:

    avg_win_bps × win_rate_pct > |avg_loss_bps| × (100 − win_rate_pct)

If this inequality fails despite win_rate above the nominal breakeven threshold, the
exit-path mix is diluting realized win size.

## Actionable rules for exit design

1. **Never report or evaluate win_rate_pct without also checking avg_win_bps**.
   If avg_win_bps < 0.5 × profit_target_bps, the time-exit path is dominant —
   extend max_hold_ticks or remove the time-exit entirely.

2. **Time exits must be conditional, not unconditional**: if the unrealized PnL at
   time-exit is below the fee hurdle (+21 bps), the time exit should be treated as
   a loss for EV purposes. Do not let a time exit convert a breakeven hold into a
   "win" that flatters win_rate_pct.

3. **Trailing stop minimum gain**: if using a trailing stop as the winning exit path,
   lock in gains only when price is already > avg_cost + fee_hurdle + trailing_buffer.
   A 25 bps trailing stop triggered at +22 bps (1 bps above fee hurdle) returns near
   zero after fees — categorically a loss in EV terms.

4. **Minimum profit-target bps per oracle table**: Use the oracle ceiling table in
   pattern_win_rate_ceiling_mandates_hold_duration to select profit_target_bps such
   that the oracle win rate at the chosen horizon exceeds the breakeven W computed
   from *realized* (not nominal) avg_win_bps. This requires testing at least one
   prior iteration's avg_win_bps before setting the next target.

## Anti-patterns

- DO NOT treat time-exit win rate as evidence of signal edge. Time exits fire when
  price drifts — they are noise, not signal.
- DO NOT use a profit target that requires avg_win_bps > 2× profit_target_bps to be
  fee-positive. The realized distribution is always left-skewed vs the nominal target.
- DO NOT set max_hold_ticks below the point where the resting limit has a reasonable
  fill probability. At 2000 ticks on KRX liquid stocks, a +100 bps limit has low
  fill probability in sideways sessions — time exits dominate.
