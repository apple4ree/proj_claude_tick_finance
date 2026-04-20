---
stage: alpha
name: pilot_s1_042700_obi10
created: 2026-04-17
signal_brief_rank: 3
---

# Alpha Design: pilot_s1_042700_obi10

## Hypothesis
When the 10-level order book imbalance (obi_10) on 042700 exceeds 0.469, buy-side pressure dominates all 10 depth levels, signaling a high-probability upward price continuation over the next 3000 ticks (rank-3 from signal_brief, ev_bps 11.8 after 21 bps round-trip fee).

## Market Context
- Symbol: 042700 (Hanmi Semiconductor, KRX)
- Signal fires at the 90th percentile of obi_10 distribution (~8.72% of ticks qualify)
- Horizon: 3000 ticks forward; signal exploits persistent order flow imbalance at the full book depth, not just top-of-book
- No opening-hour restriction currently specified, but prior lesson (lesson_20260415_009) warns against 09:00–09:30 entries on KRX OBI signals; this constraint passes to execution-designer

## Entry Condition
Enter long when `obi(depth=10) >= 0.469` on 042700. The condition must be evaluated on the live tick snapshot. Signal is considered valid at the tick it fires; entry should execute within the same or next tick to avoid imbalance decay (observed in iteration 1 with obi_5: signal decayed from 0.56 to below threshold by fill time).

## Signals Needed
- `obi(depth=10)` — 10-level order book imbalance, snapshot primitive

## Universe Rationale
042700 (Hanmi Semiconductor) is one of the KRX top-10 liquid symbols in the IS universe. Its signal brief shows 10 viable signals at 21 bps round-trip fee, with obi_10 at rank 3 offering the highest EV per trade (11.846 bps) among built-in-primitive-only signals (slope_diff at rank 1 is excluded per pilot constraint). High entry frequency (~8.72% of ticks, 8152 entries in sample) provides sufficient data for fidelity-pipeline measurement.

## Knowledge References
- Iteration 1 (strat_20260417_0002_smoke_042700_obi5): OBI signal decayed by fill time when using passive limit entry — aggressive entry at ask recommended
- lesson_20260415_009: KRX opening 09:00–09:30 OBI signals are noise; block entries until 09:30
- lesson_20260414_005: mean-reversion confirmation too late; here we are trend-following the imbalance onset, which is consistent with the signal's forward return structure

## Constraints Passed To Execution-Designer
- Entry must be aggressive (marketable limit or market order at ask) to avoid imbalance decay before fill
- Block entries during 09:00–09:30 KRX opening auction noise window
- Brief's optimal_exit baseline: pt_bps=79, sl_bps=3, exit mix 25% PT / 26% SL / 47% trailing — use as-is or within ±20%
- SL of 3 bps is below tick-grid on this symbol (observed sl_overshoot in prior iteration); execution-designer should floor SL at a value that avoids structural overshoot given KRX tick size for 042700
- Signal horizon is 3000 ticks; entries not filled within ~15 ticks of signal fire should be cancelled (signal fleeting)

```json
{
  "name": "pilot_s1_042700_obi10",
  "hypothesis": "When obi(depth=10) on 042700 exceeds 0.469 (90th percentile), sustained full-book buy-side pressure predicts upward continuation over 3000 ticks, yielding 11.8 bps EV after fees — rank-3 from signal_brief.",
  "entry_condition": "Enter long on 042700 when obi(depth=10) >= 0.469 on the current tick snapshot; execute aggressively (at ask) to avoid imbalance decay before fill.",
  "market_context": "042700 KRX in-sample universe; signal fires at 90th percentile of obi_10 distribution (~8.72% of ticks); avoid 09:00–09:30 opening window.",
  "signals_needed": ["obi(depth=10)"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "strat_20260417_0002_smoke_042700_obi5",
  "universe_rationale": "042700 is a top-10 KRX liquid symbol; signal brief shows 10 viable signals at 21 bps fee; obi_10 rank-3 is the highest-EV built-in-primitive-only signal after excluding slope_diff per pilot constraint.",
  "escape_route": null,
  "signal_brief_rank": 3,
  "alpha_draft_path": "strategies/_drafts/pilot_s1_042700_obi10_alpha.md"
}
```
