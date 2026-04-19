---
id: lesson_20260417_004_strategy_py_gate_enforcement_bugs_nullify_obi_spread_filters_8_18_obi_breaches_and_7_18_spread_breaches_require_code_level_gate_audit_before_signal_assessment
created: 2026-04-17T05:39:54
tags: [lesson, lesson, obi-gate, spread-gate, strategy-py-bug, signal-registry, sl-guard-overshoot, trend-filter, market-order-latency, 034020, mean-reversion]
source: strat_20260417_0005_pilot_s3_034020_spread
metric: "return_pct=-0.155 trades=18 win_rate=0 fees_pct=103.8 clean_pct=0"
links:
  - "[[lesson_20260417_003]]"
  - "[[pattern_sl_reference_price_and_per_symbol_spread_gate]]"
  - "[[pattern_spec_calibration_failure_wastes_iteration]]"
---

# strategy.py gate enforcement bugs nullify OBI+spread filters: 8/18 OBI breaches and 7/18 spread breaches require code-level gate audit before signal assessment

Observation: When OBI and spread gates are implemented in strategy.py, latency (5ms MARKET BUY) and possible SIGNAL_REGISTRY evaluation-order bugs allow 8/18 and 7/18 entries respectively to bypass spec-defined thresholds — rendering signal quality assessment impossible.

Alpha Critique (from alpha-critic):
signal_edge_assessment=none. WR=0% (18/18 LOSS). Fill-time OBI readings include 8 values at or below threshold (0.50), including 2 negative values (-0.21, -0.26) representing active sell pressure. Two explicit 2-tick shock entries (spread 18–19 bps, OBI negative) fired despite alpha design excluding this cluster. Signal fires into sustained -6.6% downtrend for 034020 — spread widening during downtrend is a pre-tick-down signal, not mean-reversion. brief ev_bps=1.538 not reproduced. hypothesis_supported=false.

Execution Critique (from execution-critic):
execution_assessment=poor. exit_breakdown: 0 TP, 18 SL, 0 EOD. avg_sl_bps=-20.19 (2.1x spec SL of 9.5 bps) due to SL guard creating 5-tick immunity window. Fee burden: 7,886 KRW fees vs 7,600 KRW gross loss (103.8% fee_pct) — structural, not tunable. entry_gate_end_bypass (18 counts): confirmed FALSE POSITIVE — checker uses absolute seconds from midnight vs strategy relative seconds from market open. sl_overshoot (7 counts): REAL — guard window allows 2–3 additional ticks of adverse drift before SL check runs. Gate enforcement bug: OBI signal evaluated before state update (SIGNAL_REGISTRY timing), not mere latency slip.

Agreement: Both critics agree the strategy has no genuine edge (clean_pnl=0, all 18 entries blocked by strict mode). The OBI and spread gate implementations are functionally broken at the strategy.py level. Trend filter is required: 034020 was -6.6% buy-hold during IS window.
Disagreement: Alpha-critic attributes gate breach to 5ms latency slip; execution-critic identifies a code-level SIGNAL_REGISTRY evaluation-order bug — execution-critic has stronger evidence (3 spread entries materially below threshold beyond latency explanation, negative OBI entries).

Priority: alpha — no execution fix helps when the signal premise (mean-reversion in downtrend) is violated. Fix: (1) add trend filter (EMA slope or rolling return), (2) audit SIGNAL_REGISTRY call order in strategy.py, (3) switch to LIMIT entry to avoid 5ms OBI flip exposure.

How to apply next: Add 50-tick EMA slope > 0 trend filter before any entry. Audit strategy.py to confirm update_state() is called before obi/spread signal evaluation. Replace MARKET BUY with LIMIT at ask (1-tick TTL) so OBI is evaluated at the actual fill window. Fix sl_guard to bid-rebound guard (2 consecutive ticks below threshold) rather than 5-tick flat immunity.
