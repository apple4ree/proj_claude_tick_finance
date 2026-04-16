---
description: Run one full strategy iteration — alpha-designer → execution-designer → spec-writer → [strategy-coder if python] → [code-generator if needed] → backtest-runner → feedback-analyst.
argument-hint: <seed — natural-language idea or constraint>
---

You are orchestrating ONE iteration of the tick strategy chain.

**Seed**: $ARGUMENTS

## Steps (strictly sequential — never parallel)

## Step 0: Signal Brief Generation (MANDATORY)

Before invoking any agent, you MUST ensure a fresh signal brief exists for each
target symbol in the seed's universe.

### Protocol

1. Parse the seed for target symbols (default: `005930` for KRX, `BTC` for crypto).

2. For each symbol, check if `data/signal_briefs/<SYMBOL>.json` exists AND was
   generated within the last 24 hours (`generated_at` field).

3. If missing or stale, run:
   ```bash
   # KRX symbol (fee 21 bps)
   python scripts/generate_signal_brief.py --symbol <SYM> --features-dir data/signal_research --fee 21.0

   # Crypto symbol (fee 4 bps, Upbit data root)
   python scripts/generate_signal_brief.py --symbol <SYM> --features-dir data/signal_research/crypto --fee 4.0
   ```

4. If `generate_signal_brief.py` fails because the underlying features CSV is
   missing, FIRST run:
   ```bash
   # KRX
   python scripts/signal_research.py extract --symbol <SYM> --dates <IS_DATES> --horizons 50,100,200,500,1000,3000

   # Crypto (from /home/dgu/tick/crypto/)
   python scripts/signal_research.py --data-root /home/dgu/tick/crypto extract \
       --symbol <SYM> --dates <DATE> --horizons 50,100,200,500,1000 \
       --regular-only false --outdir data/signal_research/crypto
   ```
   Then retry brief generation.

5. After briefs are confirmed fresh, check each brief's `n_viable_in_top`:
   - If 0, skip the symbol (log "no viable signal; skipping")
   - If all symbols are skipped, ABORT the iteration with reason "no market has viable signals at current fee"

6. Only then proceed to invoke `alpha-designer`.

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
