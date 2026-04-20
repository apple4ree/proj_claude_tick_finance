---
description: "[DEPRECATED] Use /experiment --n-iterations 1 instead. Legacy single-iteration chain."
argument-hint: <seed — natural-language idea or constraint>
---

> ⚠ **DEPRECATED — use `/experiment` instead.**
>
> Single iteration equivalent:
>
> ```
> /experiment --market <m> --symbols <s> \
>             --is-start <...> --is-end <...> \
>             --oos-start <...> --oos-end <...> \
>             --design-mode agent --feedback-mode agent \
>             --n-iterations 1
> ```
>
> Retained for archival reference only.

---

You are orchestrating ONE iteration of the tick strategy chain.

**Seed**: $ARGUMENTS

## Steps (strictly sequential — never parallel)

## Step 0: Signal Brief Generation (MANDATORY)

Before invoking any agent, you MUST ensure a fresh signal brief exists for each
target symbol in the seed's universe.

### Protocol

1. Parse the seed for target symbols.
   - KRX 기본값: top-10 전체 `["005930","000660","005380","034020","010140","006800","272210","042700","015760","035420"]`
   - Crypto 기본값: `["BTC","ETH","XRP"]`
   - 시드에서 명시적으로 종목을 지정하면 그것만 사용.

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
   - If 0 → skip that symbol (log "no viable signal for <SYM>; skipping")
   - If > 0 → add to `viable_symbols` list
   - If ALL symbols skipped → ABORT with reason "no market has viable signals at current fee"

6. Pass `viable_symbols` list to alpha-designer.
   - alpha-designer는 viable_symbols 중에서 선택 (multi-symbol 전략도 가능)
   - 단일 종목이 가장 유망하면 단일도 OK
   - 여러 종목이 viable하면 multi-symbol 전략 설계 가능

7. Only then proceed to invoke `alpha-designer`.

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

5. **Backtest (normal)**: delegate to `backtest-runner` with the `strategy_id`.
   - Capture the metrics JSON.
   - On error, STOP and report.

5b. **Backtest (strict) + Attribution**: run strict mode and compute PnL attribution.
   ```bash
   python scripts/attribute_pnl.py --strategy <strategy_id>
   ```
   This runs dual backtest (normal + strict) and produces:
   - `report_strict.json` (spec-compliant counterfactual)
   - An entry in `data/attribution_summary.json` with fields:
     `normal_pnl`, `strict_pnl_clean`, `bug_pnl`, `clean_pct_of_total`,
     `normal_violations_by_type`, `strict_blocks_total`.
   
   Capture the attribution output and include it in the metrics passed to critics
   (field names must match the schema above exactly):
   ```json
   {
     "return_pct": ...,
     "strict_pnl_clean": ...,
     "bug_pnl": ...,
     "clean_pct_of_total": ...,
     "invariant_violations": [...],
     "invariant_violation_by_type": {...}
   }
   ```

6. **Critique** (parallel — the single exception to "strictly sequential" above):
   delegate to `alpha-critic` AND `execution-critic` simultaneously, both with
   `{strategy_id, metrics}`.
   - metrics now includes `strict_pnl_clean`, `bug_pnl`, `invariant_violations`.
   - Capture alpha_critique JSON and execution_critique JSON.

7. **Feedback**: delegate to `feedback-analyst` with `{strategy_id, alpha_critique, execution_critique, metrics}`.
   - Capture `{lesson_id, next_idea_seed, stop_suggested, priority_action}`.

## Step 8: Fidelity measurement plumbing (MANDATORY)

After all agents have run, invoke the end-of-iteration finalize script. This is
a **pure measurement** step — it does not change any strategy output, it only
ensures that paper-relevant artifacts are captured.

### 8a. Log agent calls
For each agent invocation in steps 1–7, append a line to
`strategies/<strategy_id>/agent_trace.jsonl` via `scripts/log_agent_call.py`.

**Timing rule** — the strategy directory does not exist until spec-writer (step 3)
returns `strategy_id`. So:
- Buffer `alpha-designer` (step 1) and `execution-designer` (step 2) call
  records in memory (agent name, model family, ok/error status, timestamp).
- After spec-writer (step 3) returns `strategy_id`, flush the buffered records
  AND log spec-writer itself.
- For subsequent agents (strategy-coder through feedback-analyst), log
  immediately after each returns.

The logger rejects calls pointing at a nonexistent strategy dir to prevent
phantom state. Example:
```bash
python scripts/log_agent_call.py \
    --strategy <strategy_id> \
    --agent <alpha-designer|execution-designer|spec-writer|strategy-coder|backtest-runner|alpha-critic|execution-critic|feedback-analyst> \
    --model <sonnet|opus|haiku> \
    --status <ok|error|skipped> \
    [--output-hash <sha1>] [--note "..."]
```
The `model` field should reflect the model family declared in the agent's
frontmatter (see `.claude/agents/<name>.md`). There is no run-id / call-id in
the schema, so the logger is not idempotent — call it exactly once per agent
invocation.

### 8b. Run finalize
```bash
python scripts/iterate_finalize.py \
    --strategy <strategy_id> \
    --iter 0 \
    --seed-type meta \
    --return-pct <metrics.return_pct> \
    --n-roundtrips <metrics.n_roundtrips> \
    --win-rate <metrics.win_rate_pct> \
    --alpha-finding "<one line from alpha_critique>" \
    --execution-finding "<one line from execution_critique>" \
    --priority <feedback.priority_action> \
    --next-seed "<feedback.next_idea_seed>"
```
This guarantees:
- `report_strict.json` + `data/attribution_summary.json` are updated (runs
  `attribute_pnl.py` if missing) — this is the paper's counterfactual PnL.
- `strategies/<id>/handoff_audit.json` is written — the paper's handoff
  fidelity measurement per strategy.
- `strategies/_iterate_context.md` receives a new block for this iteration.

Do NOT skip step 8 even if step 5b already ran attribute_pnl — finalize also
performs the audit and context append which are independent.

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
