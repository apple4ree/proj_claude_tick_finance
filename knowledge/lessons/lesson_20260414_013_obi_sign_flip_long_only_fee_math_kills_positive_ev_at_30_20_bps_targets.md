---
id: lesson_20260414_013_obi_sign_flip_long_only_fee_math_kills_positive_ev_at_30_20_bps_targets
created: 2026-04-14T09:17:09
tags: [lesson, obi, fee_math, win_rate, breakeven, long_only, sign_flip]
source: strat_20260414_0015_obi_flip_long_only_v1
links: ["[[pattern_krx_fee_hurdle_dominates_tick_edge]]", "[[pattern_lob_signal_fires_after_absorption]]"]
metric: "return_pct=-10.83 trades=402 fees=904448"
---

# OBI sign-flip long-only: fee math kills positive-EV at 30/20 bps targets

Observation: OBI(depth=3) negative→positive flip with 30 bps profit target and 20 bps stop loss produced a 3.98% win rate (201 round-trips, fees 904k KRW) vs the 82% breakeven win rate required by fee math: W×(30−21)=(1−W)×(20+21) → W≥82%.

Why: Round-trip commission+tax totals 21 bps (1.5+18+1.5 bps each leg combined). A 30 bps target leaves only 9 bps net; a 20 bps stop costs 41 bps total loss. The risk-reward asymmetry demands near-perfect directional accuracy. OBI sign-flip is likely an anti-edge: by the time the flip registers, the favourable price move has already occurred and mean-reversion is the dominant subsequent pattern.

How to apply next: Either (a) widen targets so breakeven W drops to ~33% — profit_target≥100 bps, stop≥50 bps — or (b) invert the signal direction for mean-reversion, or (c) replace OBI-flip entirely with a momentum/VWAP-deviation approach that accumulates edge across longer holding periods (500–1000 ticks) where the 21 bps fee is a smaller fraction of expected move.
