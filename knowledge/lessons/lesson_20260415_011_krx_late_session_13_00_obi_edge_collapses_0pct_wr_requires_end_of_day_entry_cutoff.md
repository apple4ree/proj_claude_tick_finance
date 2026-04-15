---
id: lesson_20260415_011_krx_late_session_13_00_obi_edge_collapses_0pct_wr_requires_end_of_day_entry_cutoff
created: 2026-04-15T05:37:57
tags: [lesson, time-filter, late-session, KRX, MOC, resting-limit, OBI]
source: strat_20260415_0012_krx_resting_limit_4sym_time_filter
metric: "return_pct=0.0474 trades=27 win_rate=44.4 late_session_wr=0.0"
---

# KRX late session (13:00+) OBI edge collapses — 0pct WR requires end-of-day entry cutoff

Observation: In strat_0012 (4-symbol universe, 09:30 filter active), entries from 13:xx+ produced 0W/4L (0% WR), mirroring the 09:xx early-session failure pattern at the other end of the day.

Why: Late-session KRX flow is dominated by MOC (market-on-close) basket rebalancing and institutional unwinding. OBI imbalances during 13:xx-14:50 reflect directional forced flow, not temporary mid-price deviation that a resting limit can harvest — the price continues in the imbalance direction rather than reverting.

How to apply next: Add a hard entry cutoff at 13:00 KST (entry_end_time_seconds: 46800). See [[pattern_krx_intraday_entry_window_10_13]] for the combined dual-window rule. Combine with the extended morning blackout to 10:00 KST, concentrating all entries in the 10:00-13:00 window where observed WR is 50-75%. This dual-window filter should structurally lift WR above the 53.6% break-even threshold.
