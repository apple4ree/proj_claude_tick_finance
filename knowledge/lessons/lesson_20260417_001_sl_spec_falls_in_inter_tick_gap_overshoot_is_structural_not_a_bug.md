---
lesson_id: lesson_20260417_001
title: SL spec falls in inter-tick gap — overshoot is structural, not a code bug
tags: stop_loss, tick_grid, sl_overshoot, invariant_violation, krx, passive_fill, obi_decay
source: strat_20260417_0002_smoke_042700_obi5
metric: return_pct=-0.03 trades=1 fees_krw=1268.7
links: lesson_20260414_007
created: 2026-04-17
---

## Observation

When a stop-loss threshold (21 bps) falls between two physically realizable KRX tick levels (16.5 bps and 33.0 bps for 042700 at ~303,000 KRW), the invariant checker will always flag an sl_overshoot, but bug_pnl=0 confirms this is structural microstructure, not a code defect.

## Alpha Critique (from alpha-critic)

signal_edge_assessment: inconclusive (n_roundtrips=1). The sole fill showed entry_context.obi decaying from >=0.581266 at submission to 0.5631 at fill confirmation, consistent with lesson_20260414_007 (LOB imbalance fires at peak, not onset). Signal fire rate per brief is ~5.17% of ticks, but actual fill rate was 0.00027% — TTL=30 ticks, bid-drop cancel, and max_entries=2 suppressed nearly all executions. hypothesis_supported: false (single data point, not informative).

## Execution Critique (from execution-critic)

execution_assessment: inconclusive (n=1). Structural finding: 042700 at ~303,000 KRW has tick size=500 KRW = 16.50 bps/tick. The spec SL of 21 bps sits in the gap between tick-1 (16.50 bps) and tick-2 (33.0 bps). No bid level exists between them, so the SL must overshoot to 33 bps deterministically. The strict-mode backtest confirms bug_pnl=0 — enforcement cannot improve the outcome because the tick grid physically prevents a 21-bps exit. Effective break-even WR rises from 21% (nominal) to 29.5% (realistic, using 33 bps SL), still below brief WR of 61.63%.

## Agreement

Both critics agree: (1) n=1 makes statistical inference impossible; (2) the sl_overshoot is not a code defect — it is forced by KRX tick grid discreteness; (3) passive LIMIT BUY at bid has a fill-rate problem, possibly compounded by OBI decay before fill.

## Disagreement

Alpha-critic focuses on fill latency as the primary fix (switch to aggressive entry at ask/mid+1). Execution-critic focuses on SL calibration (set SL=33 bps explicitly to match tick floor). Both are valid and non-conflicting — the former addresses fill-rate, the latter eliminates the spurious invariant violation.

## Priority

both — fix SL to 33 bps immediately (removes invariant noise), then address passive-fill latency for the next iteration (aggressive entry or shorter TTL).

## How to apply next

Set `stop_loss_bps = 33.0` (2-tick floor for 042700) in spec.yaml to eliminate the structural sl_overshoot violation. Separately, test aggressive LIMIT BUY at ask or mid+1-tick to capture OBI imbalance before buy-side pressure dissipates. Require n >= 20 roundtrips before judging signal quality.
