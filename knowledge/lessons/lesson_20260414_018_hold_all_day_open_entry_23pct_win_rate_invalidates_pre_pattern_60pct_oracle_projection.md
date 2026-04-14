---
id: lesson_20260414_018_hold_all_day_open_entry_23pct_win_rate_invalidates_pre_pattern_60pct_oracle_projection
created: 2026-04-14T10:33:08
tags: [lesson, hold_all_day, trailing_stop, win_rate_projection, oracle_failure, no_liquidity, 005930, pattern_reliability]
source: strat_20260414_0020_hold_all_day_trailing_stop_005930
links: ["[[pattern_exit_path_distorts_win_rate_bps_required]]", "[[pattern_win_rate_ceiling_mandates_hold_duration]]"]
metric: "return_pct=-0.2106 trades=26 fees=10563.5 win_rate=23.1 anomaly=rejected.no_liquidity=8"
---

# hold_all_day_open_entry_23pct_win_rate_invalidates_pre_pattern_60pct_oracle_projection

Observation: Hold-all-day open-entry on 005930 (8 dates, 100 bps trailing stop) produced 23% win rate and -0.21% return. The prior pattern_005930_fee_incompatible_with_short_hold predicted 60% win rate based on 5 spot-sampled session returns — the actual per-roundtrip distribution across 26 entries was far worse, with 8 entries rejected for no-liquidity and only 6/26 winners.

Why: The pattern's 60% win-rate projection used end-of-session returns on 5 selected dates, not per-trade outcomes. Each session fires one entry at open and one exit at EOD, but the trailing stop converts some winning days into losers if intraday drawdown triggers early exit before an afternoon recovery. The no-liquidity rejections (8/26 = 31%) further skew the sample, eliminating entries on potentially favorable ticks and breaking the one-trade-per-session assumption.

How to apply next: Do not treat end-of-session return distributions as a proxy for hold-all-day strategy win rate. The trailing stop and liquidity gaps change the shape of outcomes. If testing a full-session hold on 005930, measure actual triggered-stop frequency across all IS dates before projecting win rate.
