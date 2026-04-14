---
id: lesson_20260414_016_rolling_high_breakout_enters_at_local_top_structural_exhaustion_signal
created: 2026-04-14T10:04:00
tags: [lesson, rolling-breakout, exhaustion, anti-edge, momentum, 005930, signal-timing, local-top]
source: strat_20260414_0018_rolling_high_breakout_005930_escape8
links: ["[[pattern_all_directional_entries_fire_at_exhaustion]]", "[[pattern_win_rate_ceiling_mandates_hold_duration]]"]
metric: "return_pct=-0.5757 trades=132 fees=26923.8 win_rate=12.1"
---

# rolling_high_breakout_enters_at_local_top_structural_exhaustion_signal

Observation: 132 trades, 12.1% win rate (breakeven 31.2%), -0.58% return. The rolling 2000-tick high breakout fires when current mid first exceeds the prior 2000-tick maximum — structurally, this is the moment the market has just completed a directional run and is at its LOCAL TOP before mean-reversion or consolidation.

Why: A new rolling high is definitionally the peak of the lookback window. Any short-term momentum that caused the breakout is already priced in at the tick the signal fires. On 005930 at tick scale, there is insufficient continuation momentum above a 2000-tick high to reach +200 bps before the -60 bps stop triggers. Best trade gross ~102 bps confirms even favorable setups never reached the target; the signal direction is structurally wrong (enters at exhaustion, not onset).

How to apply next: Invert the timing — instead of entering at the new high, require a confirmed DOWN-to-UP momentum reversal: mid_return_bps(500 ticks) transitions from < -30 bps to > 0 bps within 200 ticks. This targets the onset of recovery, not peak strength. Alternatively, abandon price-signal entirely and use time-of-day entry (09:30-09:45 KST) to test whether morning session drift provides directional bias without any microstructure trigger.
