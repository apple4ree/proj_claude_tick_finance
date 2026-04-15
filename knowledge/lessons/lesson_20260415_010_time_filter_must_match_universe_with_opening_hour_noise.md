---
id: lesson_20260415_010_time_filter_must_match_universe_with_opening_hour_noise
created: 2026-04-15T05:32:39
tags: [lesson, time_filter, universe_selection, opening_hour, krx, obi]
source: strat_20260415_0011_krx_resting_limit_2sym_obi35_time_filter
metric: "return_pct=0.1046 trades=15 fees=30985"
---

# time_filter_must_match_universe_with_opening_hour_noise

Observation: Adding a 09:30 KST entry blackout to strat_0011 (000660+006800) produced zero change vs strat_0008 — identical 15 roundtrips, +0.104% return, 46.7% WR. These two symbols never triggered OBI>0.35 before 09:30 in IS data, so the filter had no sample points to act on.

Why: A control fix is only meaningful if the target population is present. The opening-hour OBI spike problem — documented in strat_0010 traces — belongs to 005930, 006400, and 051910, not to 000660/006800. Testing the filter on a symbol set that is already immune to the problem cannot validate or refute the fix.

How to apply next: Always pair a remediation (time filter, spread gate, imbalance threshold) with the universe that exhibited the pathology. See [[pattern_krx_intraday_entry_window_10_13]] for the dual-window rule. For the 09:30 filter: test on a set that includes 006400 and 051910, which showed 9% WR on 09:xx entries. Drop 005930 (24-25 bps structural spread exceeds break-even).
