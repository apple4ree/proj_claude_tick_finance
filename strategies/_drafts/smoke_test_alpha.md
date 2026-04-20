---
stage: alpha
name: smoke_test
created: 2026-04-17
---

# Alpha Design: smoke_test

## Hypothesis
When the LOB price-slope differential (slope_diff) exceeds its 95th-percentile threshold (6.6215) on 042700, the ask-side queue is steeper than the bid-side, signaling a transient supply imbalance that resolves upward over the next 3000 ticks with EV 11.4 bps after fees.

## Market Context
Single symbol 042700 (KRX). Any session after the 09:30 opening noise window clears. No regime filter required — the brief's 5.17% entry rate already provides adequate selectivity at the 95th-percentile threshold.

## Entry Condition
Enter long when `slope_diff >= 6.6215` (rank-1 from signal_brief, threshold_percentile=95). No additional confirmation gate — this is a smoke test targeting instrumentation fidelity, not PnL maximization. Signal fires on approximately 5.17% of ticks (n_entry ~4837 over 100k-tick sample).

## Signals Needed
- `slope_diff` (rolling price-slope differential between ask and bid sides of LOB)

## Universe Rationale
Single symbol 042700 per the smoke-test specification. Isolates one symbol to reduce confounding variables when verifying end-to-end pipeline instrumentation.

## Knowledge References
- Iteration 1 context: prior trajectory run had execution violations (`max_position_exceeded x3`) — entry design here is intentionally single-symbol, single-signal to keep execution surface minimal.
- Brief recommendation: "Rank-1 (slope_diff) has highest Sharpe; alternatives diversify signal family risk."

## Constraints Passed To Execution-Designer
- Entry is valid only when `slope_diff >= 6.6215` (do not loosen threshold).
- Brief's optimal_exit baseline: pt_bps=66, sl_bps=3, Sharpe=0.5853, WR=67.31%.
- Exit mix from brief: 84% time-stop, 7% PT, 8% SL — time-stop dominates; execution-designer should respect this exit distribution shape.
- Signal horizon is 3000 ticks; TTL should align with this horizon.
- Smoke-test purpose: exercise pipeline instrumentation, not maximize PnL — keep lot_size minimal (1 lot per entry).

```json
{
  "name": "smoke_test",
  "hypothesis": "When slope_diff >= 6.6215 (95th pct) on 042700, the ask-side LOB slope exceeds bid-side slope, indicating a transient supply imbalance that resolves upward over 3000 ticks with EV 11.4 bps post-fee; rank-1 from signal_brief.",
  "entry_condition": "Enter long when slope_diff >= 6.6215 (brief rank-1, threshold_percentile=95, no additional filter)",
  "market_context": "Single symbol 042700, KRX, any session after 09:30 opening noise window; no regime filter; 5.17% entry rate at 95th-percentile threshold provides adequate selectivity",
  "signals_needed": ["slope_diff"],
  "missing_primitive": "slope_diff",
  "needs_python": true,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "Iteration 1: execution violations on multi-symbol run; smoke test isolates single symbol to verify instrumentation cleanly",
  "signal_brief_rank": 1,
  "universe_rationale": "Single symbol 042700 per smoke-test spec; isolates instrumentation verification from cross-symbol confounds",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/smoke_test_alpha.md"
}
```
