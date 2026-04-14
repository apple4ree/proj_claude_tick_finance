---
id: pattern_spec_calibration_failure_wastes_iteration
created: 2026-04-14T00:00:00
tags: [pattern, calibration, tick_size, entry_gate, confirmation-lag, dsl, spread, distribution, imbalance, overtrading, mode-d]
lessons:
  - "[[lesson_20260414_004_per_symbol_minimum_spread_must_exceed_physical_tick_price_floor]]"
  - "[[lesson_20260414_005_mean_reversion_entry_fires_after_reversal_exhausted_ret50_confirmation_too_late]]"
  - "[[lesson_20260414_008_signal_threshold_outside_observed_distribution_fires_zero_ticks_mode_c_calibration_failure]]"
  - "[[lesson_20260414_010_mode_d_overtrading_loose_entry_condition_saturates_on_regime_dominated_days]]"
---

# Pattern: Spec calibration failure wastes an iteration

## Root cause

A spec parameter that is numerically plausible in abstract (e.g., `spread_bps <= 3.0`, `ret50 > 5`) can be structurally impossible or mismatched once grounded against symbol-specific market microstructure. When this happens the backtest runs but produces 0 trades (gate never fires) or 0% win rate (gate fires at the wrong moment in the signal lifecycle). Either outcome yields no learnable signal and burns one of the finite iteration budget.

Four failure modes observed:

### Mode A: Threshold below physical floor (0 trades)
The entry condition is mathematically unreachable given the symbol's discrete tick spacing. The parameter appears valid in bps but the tick grid imposes a per-symbol minimum.

- Example: `spread_bps <= 3.0` on 005930 (min tick 100 KRW, price ~183,000 KRW → floor ≈ 5.46 bps). Gate never satisfies → 0 trades, return = 0.0%.
- Example: `spread_bps < 6.0` on 000660 (min tick 1,000 KRW, price ~928,000 KRW → floor ≈ 10.78 bps). Gate never satisfies → 0 trades across 81,371 ticks.
- Check: `min_spread_bps = tick_size / mid_price * 10000`. Any threshold tighter than this floor will produce 0 trades regardless of market conditions.
- Fix: Set spread gates at `>= 1.5 × min_spread_bps`. For 005930 that means `spread_bps <= 8.0`; for 000660 that means `spread_bps <= 16.0`.

### Mode B: Confirmation lookback longer than signal half-life (0% win rate)
The entry waits for confirmation over N ticks, but the signal it is trying to confirm has already reversed within those N ticks. Entry fires near the exhaustion point, not the inception point.

- Example: `ret50 > 5` as mean-reversion confirmation on 005930. Mean-reversion moves at intraday tick scale are short-lived; 50 ticks of upward move is already spent before entry. A 100-tick minimum hold then extends exposure into the re-mean-reversion leg. Result: 0% win rate across 14 trades.
- Check: Estimate mean-reversion half-life from autocorrelation or prior win-rate by hold-duration analysis. Confirmation lookback must be << half-life.
- Fix: Use a shorter contemporaneous signal (e.g., `ret10 > 2`) and reduce min_hold to match reversion speed (30–50 ticks, not 100).

### Mode C: Signal threshold outside observed distribution (0 trades)
The entry threshold for a derived signal (e.g., order-book imbalance, momentum ratio, spread delta) is set at an extreme that the signal never reaches on the target symbol/date combination. The threshold is not physically impossible (unlike Mode A) but is empirically unreachable given the day's realized signal distribution.

- Example: `low_threshold = -0.45` on total_imbalance for 005930/20260313. Realized distribution: p1=-0.220, p5=-0.120, median=+0.467. The day was strongly bid-heavy; ask-side imbalance never reached -0.405 (the observed minimum), let alone -0.45. Gate never satisfies → 0 trades, return = 0.0%.
- Differs from Mode A: there is no tick-grid floor here. The threshold is theoretically reachable on a different date or regime, but the specific date chosen makes it unreachable.
- Check: Before submitting a spec, compute p1/p5/p50/p95/p99 of every signal used as an entry gate on the target symbol/date. Confirm that the threshold sits at or looser than p5 (for lower-tail gates) or p95 (for upper-tail gates), and that at least 100 ticks qualify.
- Fix: For total_imbalance on 005930 with ask-side entry: use -0.20 to -0.25 as a moderate gate (yields ~1686 ticks at -0.20 on 20260313); reserve -0.30 only when the day is known to have two-sided flow. Never hard-code -0.45 without verifying the date's regime.

### Mode D: Entry condition saturates on regime-dominated day (catastrophic overtrading)
The opposite of Mode C. Each entry condition is individually weak and reflects a persistent background regime rather than a fresh signal event. On a strongly one-sided day all conditions are simultaneously true for the majority of ticks, producing pathological trade frequency and fee burn.

- Example: `microprice_threshold_bps = 1.5` AND `flat_gate_bps = 1.0` on 005930/20260313 (bid-heavy, median imbalance=+0.467). Microprice > mid is nearly always true on a bid-heavy day (microprice reflects queue weighting). Flat-price gate < 1 bps is trivially true between every tick move (one tick = 5.46 bps). Result: 902 roundtrips in one session; fees 3.48M KRW vs realized PnL -726K KRW; return = -42.1%. Even pre-fee the signal was anti-edge (-0.44 bps/RT).
- Differs from Mode C: the gate fires too much rather than too little. The conditions are regime descriptors (persistent background state), not signal events (detectable state transitions).
- Check: After confirming >= 100 qualifying ticks (Mode C check), also verify that qualifying ticks are < 20% of total ticks. If qualifying ticks exceed 20%, the condition is a regime descriptor, not a signal. Reframe the condition as a state transition (e.g., imbalance crossing a threshold from below, not merely exceeding a level).
- Fix: Require that the signal captures a detectable change in market state, not a static level. Use first-cross or derivative-based conditions. For microprice: require microprice crossed the threshold within the last N ticks, not that it exceeds the threshold now.

## Pre-spec checklist (run before submitting a YAML)

1. For every symbol, compute `min_spread_bps = tick_size / mid_price * 10000` and verify all `spread_bps` thresholds are above `1.5 × min_spread_bps`. (Catches Mode A)
2. For mean-reversion entries, confirm the confirmation lookback (in ticks) is shorter than the expected half-life of the signal being confirmed. (Catches Mode B)
3. For trend-follow entries, confirm the lookback is long enough to absorb at least one full noise cycle (empirically: at least 100 ticks on 005930 to avoid anti-momentum).
4. For every signal threshold (imbalance, OBI, momentum, etc.), check that the threshold falls within the realized p5–p95 range of the signal on the target symbol/date, and that at least 100 ticks satisfy the entry condition. (Catches Mode C)
5. **NEW — Mode D check**: After confirming >= 100 qualifying ticks, also confirm that qualifying ticks are < 20% of total ticks. If a condition qualifies on > 20% of ticks it is a regime descriptor, not a signal. Restructure it as a transition condition. (Catches Mode D)
6. Run a quick sanity check: if n_trades == 0 after a full-day backtest, the entry gate is either below the physical floor (Mode A) or outside the signal distribution (Mode C) — do not submit this spec without diagnosing which. If n_trades >> expected (e.g., > 500 roundtrips in a day), suspect Mode D.

## KRX symbol reference calibration

| Symbol | Approx price | Tick size | Min spread (bps) | Min viable spread gate | Round-trip cost floor |
|---|---|---|---|---|---|
| 005930 (Samsung) | ~183,000 KRW | 100 KRW | 5.46 bps | spread_bps <= 8.0 | ~26 bps |
| 000660 (SK Hynix) | ~928,000 KRW | 1,000 KRW | 10.78 bps | spread_bps <= 16.0 | ~32 bps |

Note: 000660 has a materially higher fee floor than 005930 due to the larger tick-size-to-price ratio and higher absolute spread. It is a structurally harder target for any tick-scale strategy on KOSPI equity.

### 005930 total_imbalance reference (20260313)
- Regime: strongly bid-heavy (median=+0.467)
- p1=-0.220, p5=-0.120, min=-0.405
- Viable ask-side entry gates: >= -0.20 (~1686 ticks), >= -0.25 (moderate), >= -0.30 (~100 ticks)
- Unreachable: any threshold below -0.405

### 005930 microprice reference (20260313)
- Regime: strongly bid-heavy (median imbalance=+0.467); microprice > mid is near-constant
- A `microprice > mid + threshold` level gate is a regime descriptor on this date, not a signal
- Transition-safe alternative: require microprice crossed threshold from below within last 20 ticks (first-cross filter)
- Mode D trip wire: if microprice_threshold_bps = 1.5 qualifies > 80% of ticks on this date, the condition is saturated

## Anti-patterns to avoid

- Do NOT copy a spread_bps threshold from one symbol to another without recomputing the physical floor.
- Do NOT use the same confirmation lookback for mean-reversion and trend-follow — they have opposite requirements.
- Do NOT submit a spec without mentally tracing whether the entry gate can fire at least once per 1000 ticks under typical market conditions.
- Do NOT set a signal threshold from intuition or theory without verifying it against the actual p5/p95 of that signal on the target symbol/date. A threshold that is correct on a balanced day may be completely unreachable on a one-sided regime day.
- Do NOT use a level-crossing condition on a strongly one-sided day without a Mode D check. If the market is bid-heavy all day, any bid-side level condition fires all day — that is the regime, not a signal.
