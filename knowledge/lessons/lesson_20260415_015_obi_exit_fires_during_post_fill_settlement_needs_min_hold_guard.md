---
id: lesson_20260415_015_obi_exit_fires_during_post_fill_settlement_needs_min_hold_guard
created: 2026-04-15T06:12:54
tags: [lesson, obi, exit-signal, passive-fill, min-hold, settlement-period, winner-cut]
source: strat_20260415_0017_krx_resting_limit_4sym_obi_exit
metric: "return_pct=-0.4376 trades=15 win_rate_pct=6.667 avg_win_bps=128.71 avg_loss_bps=-30.39"
---

# OBI exit fires during post-fill settlement — needs min_hold guard

Observation: OBI exit (threshold=0.40, ticks=3) triggered on 14/15 positions including winners. Passive BUY LIMIT fills occur on down-moves, so bid book dominates immediately after fill — OBI is structurally high in the settlement period and is not predictive.

Why: The hypothesis that high OBI post-fill signals adverse conditions is inverted for passive limit entries: a fill on a down-move guarantees high bid pressure momentarily. The early-exit fired within the first few ticks, converting future winners into small losses (win_rate dropped to 6.7%).

How to apply next: Add min_hold_ticks_before_obi_exit (5–10 ticks) so OBI exit is suppressed during settlement. Raise exit_obi_threshold to 0.55–0.60 and exit_obi_ticks to 8–10 to require a stronger and more persistent signal before exiting. Validate by checking that OBI remains elevated beyond the settlement window before treating it as predictive.

---

## Update — strat_20260415_0019_krx_resting_limit_4sym_obi_exit_v2

Observation: Raising min_hold_ticks to 7 and threshold to 0.57 still failed: 11/15 exits were obi_exit losses (all LOSS, avg -29.74 bps), 3/15 limit_exit were wins (avg +128.71 bps). Trace showed fill-to-obi_exit = 3 seconds real time. On KRX, 7 ticks = ~3–7 wall-clock seconds because tick frequency is in the hundreds per second — ticks are not a meaningful time proxy.

Why: min_hold_ticks uses event count, not wall-clock time. The 30–60 second settlement window that justifies suppressing OBI exit requires roughly 500–3000 ticks on KRX liquid names, not 7. Even with a stronger persistence requirement (exit_obi_ticks=9), once the guard expires at 3 seconds the OBI signal has no predictive power at that latency.

How to apply next: Replace min_hold_ticks with a wall-clock guard: min_hold_ns = 30 * 10**9 (30 seconds). Alternatively, abandon the OBI exit mechanism entirely for this strategy family and instead pursue universe expansion (add 035420/Naver, 055550/Hana) to raise roundtrip count toward 30, which is the primary bottleneck for significance.
