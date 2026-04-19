# Smoke Test Log — Agent Handoff Schema

**Date:** 2026-04-17
**Branch:** `feat/agent-handoff-schema`
**HEAD commit:** `333de58` (11-task rollout + 4 fix-ups)

---

## Automated Prerequisites (already verified)

- [x] **33/33 handoff tests pass** (`pytest tests/test_handoff_*.py tests/test_verify_outputs_schema.py`)
- [x] **Malformed alpha-designer input returns `ok=false`** with specific per-field failures (Success Criterion #4)
- [x] **Signal briefs exist** for top-10 KRX symbols + BTC
- [x] **`pilot_s3` idea.json present** and the replay test proves schema blocks it (Success Criterion #2)

## User-Driven Smoke Test (Task 11 Step 2)

The `/experiment --design-mode=agent` invocation requires running LLM agents (alpha-designer, execution-designer, etc.) which cannot be fully automated by a subagent in this session. To validate the happy path end-to-end, you should run one iteration manually.

**Recommended command (multi-symbol, per-symbol backtest mode — standard eval universe):**

```
/experiment --market krx --symbols top10 --is-start 20260316 --oos-start 20260323 \
            --design-mode agent --feedback-mode programmatic --n-iterations 1
```

`top10` expands to `005930, 000660, 005380, 034020, 010140, 006800, 272210, 042700, 015760, 035420` per `CLAUDE.md`. This exercises the validator across multiple signal briefs (not just one), including `042700` where the weakly-profitable baseline `pilot_s1_042700_obi10` exists — so Success Criterion #3 is checked as part of the multi-symbol sweep.

Per-symbol backtest mode is the standard evaluation convention (memory: `project_standard_eval_universe.md`); the runner handles the per-symbol split automatically when multiple symbols are specified.

## What To Watch

Stage | Expected behaviour | Abort signal
---|---|---
alpha-designer | Returns JSON; `verify_outputs.py --agent alpha-designer` prints `ok: true` | `ok: false` → iteration aborts, no execution-designer call
execution-designer | Returns JSON nesting `alpha`; `verify_outputs.py --agent execution-designer` prints `ok: true` | `ok: false` → iteration aborts, no spec-writer call
spec-writer | Receives flattened shape with `alpha_draft_path` and `execution_draft_path` present | Missing keys → spec-writer error (would indicate adapter bug — please flag)
backtest-runner | Runs normally (not gated) | n/a
feedback-analyst | Returns JSON; `verify_outputs.py --agent feedback-analyst` prints `ok: true` | `ok: false` → lesson not finalised (advisory only)

## Observations (fill in after running)

```
Alpha-designer validation: PASS / FAIL
  If FAIL, first failure: _________

Execution-designer validation: PASS / FAIL
  If FAIL, first failure: _________

Spec-writer invocation: PASS / FAIL
  If FAIL, was alpha_draft_path or execution_draft_path missing in flattened input? _________

Feedback-analyst validation: PASS / FAIL
  If FAIL, first failure: _________

Any prompt tweaks needed (agent got confused about new schema): _________
```

## Success Criteria Mapping (spec §10)

- **Criterion 1** — `/experiment --design-mode=agent` produces JSON that validates. ✅ if both alpha and execution validators return `ok: true`.
- **Criterion 2** — pilot_s3-like scenario blocked before backtest. ✅ already (`tests/test_handoff_pilot_s3_replay.py`).
- **Criterion 3** — `pilot_s1` currently-best strategy can be regenerated and passes validation. Tested here if `042700` iteration succeeds.
- **Criterion 4** — `verify_outputs.py --agent alpha-designer` returns `ok=false` on malformed input. ✅ already (verified above).

## If Something Fails

- **Agent returns malformed JSON on first try:** expected. The new `### Output` prose in `.claude/agents/*.md` documents the contract, but the agent may need 1-2 attempts to align. If after 3 retries it still fails, consider whether the prompt is ambiguous — edit the `### Output` section in the relevant agent file and re-run.
- **Spec-writer error about missing `alpha_draft_path`:** adapter bug in `.claude/commands/experiment.md` flatten step. Report back with the actual input spec-writer received.
- **Feedback-analyst schema fails with `extra fields not permitted`:** some extension key the agent invented. Either add the key to `FeedbackOutput.extensions` usage pattern or refine the prompt.
