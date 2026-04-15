---
description: Run one full strategy iteration — alpha-designer → execution-designer → spec-writer → [strategy-coder if python] → [code-generator if needed] → backtest-runner → feedback-analyst.
argument-hint: <seed — natural-language idea or constraint>
---

You are orchestrating ONE iteration of the tick strategy chain.

**Seed**: $ARGUMENTS

## Steps (strictly sequential — never parallel)

1. **Alpha design**: delegate to `alpha-designer` (Agent tool, subagent_type=alpha-designer). Pass the seed.
   - Capture the JSON output.
   - If `missing_primitive` is non-null, go to step 3a.

2. **Execution design**: delegate to `execution-designer` with the alpha-designer JSON.
   - Capture the JSON output (includes entry_execution, exit_execution, position).

3. **Spec**: delegate to `spec-writer` with the execution-designer JSON.
   - Capture `{strategy_id, spec_path, needs_strategy_coder}`.
   - If it returns `{"error": "missing_primitive", ...}`:
     - **3a**: delegate to `code-generator` with the primitive description.
     - On success, re-run step 3 with the same idea.
     - On failure, STOP and report the error.

4. **Strategy code** (only if `needs_strategy_coder == true`):
   - Delegate to `strategy-coder` with `{strategy_id, spec_path, execution_design}`.
   - Capture `{strategy_py_path, validation}`.
   - If validation fails, STOP and report.

5. **Backtest**: delegate to `backtest-runner` with the `strategy_id`.
   - Capture the metrics JSON.
   - On error, STOP and report.

6. **Critique** (parallel): delegate to `alpha-critic` AND `execution-critic` simultaneously, both with `{strategy_id, metrics}`.
   - Capture alpha_critique JSON and execution_critique JSON.

7. **Feedback**: delegate to `feedback-analyst` with `{strategy_id, alpha_critique, execution_critique, metrics}`.
   - Capture `{lesson_id, next_idea_seed, stop_suggested, priority_action}`.

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
