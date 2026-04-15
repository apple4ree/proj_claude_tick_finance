---
id: lesson_20260415_009_krx_opening_hour_09_00_09_30_obi_signals_are_noise_block_entries_until_09_30
created: 2026-04-15T05:27:15
tags: [lesson, time-filter, opening-auction, OBI, KRX, market-making]
source: strat_20260415_0010_krx_resting_limit_5sym_no_imbalance
metric: "return_pct=-0.1026 trades=30 win_rate=36.67 fees_bps=21"
---

# KRX opening hour (09:00-09:30) OBI signals are noise — block entries until 09:30

Observation: In iter 10, 09:xx entries produced 1W/10L (9% WR) vs 71% WR at 11:xx. KRX auction clear at 09:00 floods the tape with one-sided OBI spikes that reverse within seconds — the resting-limit entry fires but the order-flow immediately flips, triggering stops at -84 bps each.

Why: The OBI gate (threshold=0.35) was designed for continuous-session liquidity. At auction clear, residual imbalance from overnight orders momentarily pushes OBI well above 0.35 but this carries zero predictive signal for mid-price direction. The 19 stops in this run were overwhelmingly 09:xx fills.

How to apply next: Add a hard time-of-day filter: suppress all entries before 09:30. Secondary: consider also filtering 12:00-12:10 (lunch auction) for the same reason. This alone should lift WR from 36.7% to near the observed 10:xx-11:xx regime of 57-71%, pushing past the 53.6% break-even threshold.

See also: [[pattern_krx_intraday_entry_window_10_13]]

---

## Update — strat_20260415_0012 (2026-04-15)

Observation: With the 09:30 blackout active, 09:30-09:59 entries still produced 1W/5L (17% WR) on 006400 and 051910 — the fix was insufficient. The noise regime extends to 10:00 on these higher-spread symbols. entry_start_time_seconds must be set to 36000 (10:00 KST), not 34200 (09:30).
