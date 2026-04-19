---
id: lesson_20260417_002_strict_mode_force_sell_ignores_sl_guard_ticks_bug_pnl_metric_is_invalid_when_spec_is_incomplete
created: 2026-04-17T05:03:19
tags: [lesson, strict_mode, invariant_checker, sl_guard, spec_incompleteness, bug_pnl, trailing_stop, 042700, obi10, fee_burden]
source: strat_20260417_0003_pilot_s1_042700_obi10
metric: "return_pct=+0.0076 trades=3 fees_pct=83.3 bug_pnl=+9537_artifact"
links:
  - "[[lesson_20260417_001]]"
  - "[[lesson_20260415_015]]"
---

# strict-mode force_sell ignores sl_guard_ticks — bug_pnl metric is invalid when spec is incomplete

Observation: strict-mode's InvariantRunner.should_force_sell fires SL on every tick from tick-1, while strategy.py only arms the stop after a 5-tick guard; when sl_guard_ticks is absent from spec.yaml, strict-mode counterfactual PnL (bug_pnl) is a methodological artifact, not a real violation signal.

Alpha Critique (from alpha-critic): signal_edge_assessment: inconclusive (n=3, far below minimum). OBI separation is inverted in the 3-sample pilot (loss entry obi=0.628 > win entries 0.619/0.573), but this is noise not evidence. Signal brief EV=11.8 bps post-fee at rank-3, but brief's Sharpe is built on 47% trailing exits — which this pilot disables. SL floor mismatch: brief uses sl_bps=3 with trailing; live uses 33 bps hard stop (2-tick grid). hypothesis_supported: false (inconclusive, not refuted).

Execution Critique (from execution-critic): execution_assessment: suboptimal. exit_breakdown: 2 PT-limit (+54.1 bps avg), 1 SL (-34.0 bps). fee_pct=83.3% — lot_size=2 at 303k KRW yields only 254 KRW net per roundtrip. fee_pct cannot improve by scaling lot_size alone; must capture larger moves (trailing stop) to raise avg_gross_bps. Strict mode turned 2 winners into losses by firing SL before the 5-tick guard elapsed, generating bug_pnl=+9537 KRW with zero actual violations. This is a spec incompleteness, not a code defect.

Agreement: Both critics agree n=3 is statistically insufficient; trailing stop must be re-enabled (brief's dominant exit path at 47%); 5-tick SL guard has real economic value (prevents noise exits) and must be formalized in spec.yaml.

Disagreement: Alpha-critic focuses on raising OBI threshold to 95th percentile; execution-critic focuses on spec incompleteness fix and trailing stop re-enable. Both are valid and non-conflicting.

Priority: both — fix spec incompleteness (sl_guard_ticks) immediately to restore valid strict-mode counterfactuals, then re-enable trailing stop to recover brief's exit structure.

How to apply next: Add sl_guard_ticks: 5 to spec.yaml; update InvariantRunner.should_force_sell to skip SL check when ticks_held < sl_guard_ticks; re-enable trailing stop with activation >= 40 bps, distance <= 25 bps; raise max_entries_per_session to 3 to generate 15+ roundtrips over 6 days.
