---
id: lesson_20260414_011_ideator_win_rate_optimism_lob_resilience_recovery_signal_was_anti_edge
created: 2026-04-14T07:59:31
tags: [lesson, win-rate-estimate, lob-resilience, profit-target, signal-edge, korean-equities]
source: strat_20260414_0013_price_dip_lob_resilience_recovery
metric: "return_pct=-2.5396 trades=28 fees=221958"
links:
  - "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"
  - "[[pattern_lob_signal_fires_after_absorption]]"
---

# Ideator Win-Rate Optimism: LOB Resilience Recovery Signal Was Anti-Edge

Observation: Ideator projected 54.9% forward win rate for the price-dip + resilient-LOB + stabilization entry pattern; actual win rate over 14 roundtrips was 7.1% (-1.25 bps gross per RT before fees).

Why: The profit target (40 bps) demanded a full reversal that rarely materialized within 200 ticks. The ideator's pre-analysis likely measured the frequency of ANY upward tick after the conditions, not the frequency of reaching +40 bps before -20 bps stop. Resilient bid imbalance at entry is a coincident indicator, not a predictive one; the signal fires at the bottom of a dip but doesn't distinguish genuine LOB support from passive resting orders that absorb one more wave before softening. With 14 RT and 7 independent episodes, the sample cannot confirm edge, but the direction (pre-fee negative) already points against it.

How to apply next: Either (a) compress the profit target to 10-15 bps and widen stop symmetrically to improve hit rate before large adverse moves, or (b) require the resilience condition to hold for N consecutive ticks before entry rather than a single snapshot, to confirm sustained LOB support rather than momentary imbalance.
