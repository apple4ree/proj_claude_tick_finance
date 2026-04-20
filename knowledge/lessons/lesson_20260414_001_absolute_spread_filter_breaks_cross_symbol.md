---
id: lesson_20260414_001_absolute_spread_filter_breaks_cross_symbol
created: 2026-04-14T01:44:02
tags: [lesson, dsl, spread, cross_symbol, failure]
source: strat_20260414_0001_obi_momentum_tight
metric: "return_pct=-0.79 trades=334 fees=64476"
links:
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
---

# absolute spread filter breaks cross-symbol

Observation: strat_20260414_0001_obi_momentum_tight used 'spread_px <= 200' as an entry filter. 005930 (price ~183k) traded 334 times; 000660 (price ~905k) fired 0 orders because its natural spread is ~1000 KRW. Why: absolute-KRW spread thresholds do not scale across symbols — higher-priced names have strictly wider absolute spreads even when their bps spread is comparable or tighter. How to apply next: express spread filters in bps of mid (e.g., spread / mid * 1e4 < 10) or in exchange ticks, NOT in absolute KRW. Consider per-symbol normalization for any price-denominated threshold.
