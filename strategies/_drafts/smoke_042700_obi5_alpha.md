---
stage: alpha
name: smoke_042700_obi5
created: 2026-04-17
---

# Alpha Design: smoke_042700_obi5

## Hypothesis
When the 5-level order book imbalance for 042700 exceeds 0.581 (top-5% threshold), buy-side pressure materially outweighs sell-side depth, creating a short-horizon drift that covers the 21 bps KRX round-trip fee — rank-2 from signal_brief.

## Market Context
Single symbol 042700 (Hanmi Science), any session tick after 09:30 (post-open noise filter per lesson_20260415_009). No regime filter required for smoke test purposes; signal fires at 95th-percentile OBI events (~4% of ticks), providing adequate selectivity.

## Entry Condition
Enter LONG when `obi(depth=5) >= 0.581266` (brief threshold, rank-2). No additional confirmation required. Signal is instantaneous (snapshot primitive) — no stateful rolling needed.

## Signals Needed
- `obi(depth=5)` — order book imbalance across best 5 bid/ask levels

## Universe Rationale
Single symbol 042700 for end-to-end chain smoke test. Symbol is in the standard top-10 IS universe and has a valid signal brief with 10 viable signals.

## Knowledge References
- lesson_20260415_009: block entries before 09:30 (KRX open noise)
- lesson_20260414_017: transition-based entry fires at informationally neutral points — OBI snapshot avoids this by reading live imbalance, not a state change event

## Constraints Passed To Execution-Designer
- Brief optimal_exit baseline: pt_bps=79, sl_bps=3, sharpe=0.4053, win_rate=61.63%
- Exit mix from brief: 16% PT / 20% SL / 63% time-stop — time-stop dominates; execution must respect this
- Signal is fleeting (snapshot at 95th pct); entry window should be tight (do not hold entry gate open beyond a few ticks after signal fires)
- Entry gate: 09:30 onward only

```json
{
  "name": "smoke_042700_obi5",
  "hypothesis": "When obi(depth=5) for 042700 crosses 0.581 (95th pct), buy-side depth dominance produces a short-horizon positive drift sufficient to clear the 21 bps KRX fee — rank-2 from signal_brief.",
  "entry_condition": "obi(depth=5) >= 0.581266; entry after 09:30 only",
  "market_context": "042700 single-symbol, any IS date, post-09:30 session; no regime filter for smoke test",
  "signals_needed": ["obi(depth=5)"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": null,
  "signal_brief_rank": 2,
  "universe_rationale": "Single symbol 042700 for smoke-test plumbing; valid signal brief with n_viable_in_top=10",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/smoke_042700_obi5_alpha.md"
}
```
