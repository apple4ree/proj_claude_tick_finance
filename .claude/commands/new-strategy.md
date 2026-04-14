---
description: Run one full strategy iteration — ideator → spec-writer → (code-generator if needed) → backtest-runner → feedback-analyst.
argument-hint: <seed — natural-language idea or constraint>
---

You are orchestrating ONE iteration of the tick strategy chain.

**Seed**: $ARGUMENTS

## Steps (strictly sequential — never parallel)

1. **Ideate**: delegate to `strategy-ideator` (Agent tool, subagent_type=strategy-ideator). Pass the seed.
   - Capture the JSON idea.
   - If `missing_primitive` is non-null, go to step 2a.

2. **Spec**: delegate to `spec-writer` with the idea JSON.
   - Capture `{strategy_id, spec_path}`.
   - If it returns `{"error": "missing_primitive", ...}`:
     - **2a**: delegate to `code-generator` with the primitive description.
     - On success, re-run step 2 with the same idea.
     - On failure, STOP and report the error.

3. **Backtest**: delegate to `backtest-runner` with the `strategy_id`.
   - Capture the metrics JSON.
   - On error, STOP and report.

4. **Feedback**: delegate to `feedback-analyst` with `{strategy_id, metrics}`.
   - Capture `{lesson_id, next_idea_seed, stop_suggested}`.

## Final report (to the user)

```json
{
  "strategy_id": "...",
  "metrics": {"return_pct": ..., "n_trades": ..., "total_fees": ...},
  "lesson_id": "...",
  "next_idea_seed": "...",
  "stop_suggested": false
}
```

Keep the final report tight — no prose around it.
