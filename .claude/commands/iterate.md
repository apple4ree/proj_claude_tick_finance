---
description: "[DEPRECATED] Use /experiment instead. Open-ended autonomous meta-loop; superseded by the unified /experiment framework."
argument-hint: <N> [<initial seed — optional>]
---

> ⚠ **DEPRECATED — `/experiment` is the canonical entry point.**
>
> Replace `/iterate <N> "<seed>"` with:
>
> ```
> /experiment --market <m> --symbols <s> \
>             --is-start <...> --is-end <...> \
>             --oos-start <...> --oos-end <...> \
>             --design-mode agent --feedback-mode agent \
>             --n-iterations <N> --meta-review-every 5
> ```
>
> `/experiment` adds raw-EDA Phase 1, 4-gate validation (invariants / OOS / IR vs
> buy-and-hold / cross-symbol), BH benchmark, IC/ICIR/IR metrics, and programmatic
> feedback alongside the legacy agent chain. The agent chain still runs when
> `--design-mode agent` and `--feedback-mode agent` are set.
>
> The body below is retained for archival reference only.

---

You are orchestrating an **open-ended autonomous meta-loop** for the tick strategy framework.

## Parse arguments

- `N` (required): iteration budget, integer 1–20. This is a soft cap — you can stop earlier if you conclude progress is saturated AND the meta-reviewer confirms no structural fix unblocks it.
- `initial_seed` (optional): natural-language seed for iteration 1. If absent, derive one:
  1. Run `python scripts/list_strategies.py --limit 5` and `python knowledge/graph.py stats` to orient.
  2. If there are no strategies yet, default seed: `"entry on strong positive order book imbalance with short-term upward momentum, exit on imbalance flip"`.
  3. Otherwise invoke `meta-reviewer` with the last 5 strategies as input and use its `meta_seed` as the initial seed.

Pick `K = 3` (meta-reviewer cadence) unless the seed explicitly asks otherwise.

## Core principle

This loop is NOT a fixed "ideate → spec → backtest → feedback" pipeline. That rigid shape is what previously caused 3 iterations of parameter tuning to miss the structural fee/turnover problem. You are now authorized to **evolve the framework itself mid-loop** under these rules:

- Each iteration decides what needs to happen based on current project state, not a hard-coded order.
- When an agent returns a signal that another path is needed (e.g., `backtest-runner.anomaly_flag != null`, `feedback-analyst.structural_concern != null`, `spec-writer` reports DSL gap), route to the appropriate specialist BEFORE retrying the failing step.
- Every K iterations (or immediately if stop_suggested fires), call `meta-reviewer` and let its `meta_seed` steer the next ideation.
- The framework is allowed to change — engine/, DSL schema, knowledge categories, agent instructions — as long as `scripts/audit_principles.py` stays green.

## Allowed per-iteration action types

At each iteration boundary, decide which of these applies. Pick exactly one. (If more than one is needed, do them over consecutive iterations.)

1. **New strategy** (standard path) — alpha-designer → execution-designer → spec-writer → [code-generator if missing primitive] → [strategy-coder if needs_strategy_coder=true] → backtest-runner → **attribute_pnl (strict-mode counterfactual)** → [alpha-critic + execution-critic in parallel] → feedback-analyst (reconciler) → **iterate_finalize**. After backtest-runner, run `python scripts/attribute_pnl.py --strategy <id>` to produce `report_strict.json` and update `data/attribution_summary.json` — metrics passed to critics must include `strict_pnl_clean`, `bug_pnl`, `clean_pct_of_total` (schema exactly as emitted by `attribute_pnl.py`). After backtest, invoke alpha-critic and execution-critic **in parallel**. Then pass both critiques to feedback-analyst. Finally invoke `scripts/iterate_finalize.py` (see "Fidelity measurement plumbing" below).
2. **Engine fix** — when backtest-runner's `anomaly_flag` or an audit check flags a principle violation that blocks progress. Route: code-generator (mode=bugfix) → re-run audit → return to the strategy that triggered it.
3. **DSL extension** — when spec-writer reports the current grammar cannot express an idea pattern you're seeing repeatedly. Route: spec-writer (meta-authority) or code-generator (mode=dsl_ext), followed by example update.
4. **Pattern consolidation** — when ≥3 lessons share a root cause. Route: feedback-analyst or strategy-ideator writes `knowledge/patterns/<id>.md` and rebuilds the graph.
5. **Meta-review** — on K boundary or when stuck. Route: meta-reviewer, then use its `meta_seed` as input to action #1 on the next iteration.

## Iteration context persistence

Each iteration MUST persist its learnings for future iterations to read:

### Per-strategy critique files (after critics complete)
Write two markdown files to the strategy directory:
- `strategies/<id>/alpha_critique.md` — alpha-critic's full analysis in readable markdown
- `strategies/<id>/execution_critique.md` — execution-critic's full analysis in readable markdown

Format:
```markdown
# Alpha Critique: <strategy_id>

**Signal edge**: <strong | weak | none | inconclusive>

## WIN vs LOSS Separation
| Metric | WIN avg | LOSS avg | Delta |
|---|---|---|---|
| OBI | <val> | <val> | <val> |
| spread_bps | <val> | <val> | <val> |

## Selectivity
<entry_pct>%, assessment: <selective | too_restrictive | broad>

## Regime Dependency
<assessment>

## Critique
<2-3 sentences>

## Improvement Direction
<1 sentence>
```

### Running iterate context log
`strategies/_iterate_context.md` is the **primary context source** for all agents in subsequent iterations. **Do NOT append to it manually** — `scripts/iterate_finalize.py` (invoked at each iteration's end; see "Fidelity measurement plumbing" below) is the sole writer. The finalize script is idempotent per (iteration, strategy_id). The block it writes contains `Result / Attribution / Alpha / Execution / Priority / Seed → next`.

When invoking alpha-designer or execution-designer, include in the prompt:
```
Read strategies/_iterate_context.md for context from prior iterations in this run.
```
This context deliberately excludes handoff-fidelity measurement data (which lives in `strategies/<id>/handoff_audit.json`) so that downstream agent behavior is not affected by paper-pipeline metadata.

## Loop structure

Maintain an in-memory log of iteration outcomes. Do NOT re-read report.json files — use only the JSON each agent returns.

Initialize at loop start:
```
consecutive_negative = 0     # 연속 return_pct < 0 카운트
last_escape_seed = null      # 마지막으로 사용된 escape_seed
paradigm_shift_pending = false
seed_type = "meta"           # 첫 번째 이터레이션은 항상 "meta" (initial_seed)
```

```
for i in 1..N:
    state = summarize(log)            # brief, token-efficient
    action = decide_next_action(state, current_seed)
    result = execute(action)

    # --- output verification (run after each agent in new_strategy path) ---
    # After execution-designer:
    #   verify execution_draft_path file exists in strategies/_drafts/
    #   verify entry_execution and exit_execution fields are present
    #   if missing: abort iteration, log, do NOT run spec-writer
    #
    # After spec-writer:
    #   vfy = Bash("python scripts/verify_outputs.py --agent spec-writer --output '<spec_writer_json>'")
    #   if not vfy.ok: abort iteration, log failures, do NOT run backtest
    #   if spec_writer_json.needs_strategy_coder == true:
    #     invoke strategy-coder with strategy_id and execution_design JSON
    #     vfy_coder = Bash("python -c \"import strategies.<id>.strategy; print('OK')\"")
    #     if vfy_coder fails: abort iteration, log, do NOT run backtest
    #
    # After backtest-runner:
    #   vfy = Bash("python scripts/verify_outputs.py --agent backtest-runner --output '<backtest_json>'")
    #   if vfy.warnings contains "n_trades=0": skip feedback-analyst, go to next seed
    #   if vfy.warnings contains "n_roundtrips=...Mode D": log warning, continue to feedback
    #
    # After feedback-analyst:
    #   vfy = Bash("python scripts/verify_outputs.py --agent feedback-analyst --output '<feedback_json>'")
    #   if vfy.warnings (missing local_seed/escape_seed): note in log, use next_idea_seed as fallback
    #
    # After meta-reviewer:
    #   vfy = Bash("python scripts/verify_outputs.py --agent meta-reviewer --output '<meta_json>'")
    #   if not vfy.ok: log failures (claimed file edits didn't happen)
    # -----------------------------------------------------------------------

    log.append({iter: i, action: action.type, seed_type: seed_type, result: result.summary})

    # anomaly routing
    if result.anomaly_flag:
        route to code-generator (bugfix) or meta-reviewer (escalation)

    # meta cadence
    if i % K == 0 and i < N:
        mr = invoke meta-reviewer with log
        # paradigm_shift 라우팅
        if mr.action_taken.type == "paradigm_shift":
            paradigm_shift_pending = true
            current_seed = mr.meta_seed
            seed_type = "paradigm"
        else:
            current_seed = mr.meta_seed
            seed_type = "meta"
        continue  # seed_type 이미 설정됨

    # stop conditions
    if all of:
        - feedback-analyst.stop_suggested == true
        - meta-reviewer has been invoked this iteration
        - meta-reviewer.action_taken.type == "none"
      then break  # genuinely saturated

    # seed 선택 로직 (new_strategy 이터레이션만 해당)
    feedback = result.feedback  # feedback-analyst output

    if result.return_pct is not null:
        if result.return_pct < 0:
            consecutive_negative += 1
        else:
            consecutive_negative = 0

    if consecutive_negative >= 2:
        current_seed = feedback.escape_seed
        last_escape_seed = current_seed
        consecutive_negative = 0   # escape 시도 후 리셋
        seed_type = "escape"
    elif paradigm_shift_pending:
        current_seed = meta_reviewer.meta_seed
        paradigm_shift_pending = false
        seed_type = "paradigm"
    else:
        current_seed = feedback.local_seed or feedback.next_idea_seed
        seed_type = "local"
```

## Fidelity measurement plumbing (MANDATORY per iteration)

After each iteration's chain completes (strategy ran, critics done, feedback produced) and BEFORE moving to the next iteration, run the finalize step. This is pure measurement — it does not change agent behavior, it records what happened so the paper has per-iteration data.

### 1. Log each agent call
After each subagent in the chain returns, append one line to `strategies/<id>/agent_trace.jsonl` via:
```bash
python scripts/log_agent_call.py \
    --strategy <strategy_id> \
    --iteration <i> \
    --agent <alpha-designer|execution-designer|spec-writer|strategy-coder|backtest-runner|alpha-critic|execution-critic|feedback-analyst|meta-reviewer|code-generator|portfolio-designer> \
    --model <sonnet|opus|haiku> \
    --status <ok|error|skipped> \
    [--timestamp <UTC-ISO8601>] [--note "optional short note"]
```
Use the `model` field from the agent's frontmatter (`.claude/agents/<name>.md`). `status=skipped` is valid (e.g., when strategy-coder is skipped because `needs_strategy_coder=false`).

**Pre-spec-writer timing rule** — the strategy directory does not exist until spec-writer returns `strategy_id`. So for action-type 1 (new strategy):
- Buffer `alpha-designer` and `execution-designer` call records in memory (agent name, model, status, and call time).
- After spec-writer returns `strategy_id`, flush the buffered records using `--timestamp <original-call-time>` so retroactive logs preserve the actual call order.
- Log spec-writer itself and all subsequent agents immediately after each returns.
The logger rejects calls pointing at a nonexistent strategy dir — use this buffering sequence to avoid phantom state. The logger is not idempotent (no run-id / call-id in schema), so call it exactly once per agent invocation.

### 2. Run attribute_pnl if not yet run
If `strategies/<id>/report_strict.json` does not exist, run:
```bash
python scripts/attribute_pnl.py --strategy <strategy_id>
```
This produces the counterfactual strict-mode report and updates `data/attribution_summary.json`. The resulting `strict_pnl_clean`, `bug_pnl`, `clean_pct_of_total` must be included in the metrics passed to critics (field names match `attribute_pnl.py` output exactly).

### 3. Run iterate_finalize
At the very end of each iteration:
```bash
python scripts/iterate_finalize.py \
    --strategy <strategy_id> \
    --iter <i> \
    --seed-type <local|escape|paradigm|meta> \
    --return-pct <metrics.return_pct> \
    --n-roundtrips <metrics.n_roundtrips> \
    --win-rate <metrics.win_rate_pct> \
    --alpha-finding "<one line from alpha_critique>" \
    --execution-finding "<one line from execution_critique>" \
    --priority <feedback.priority_action> \
    --next-seed "<feedback.next_idea_seed>"
```
This:
- Runs `attribute_pnl.py` if still missing (idempotent).
- Writes `strategies/<id>/handoff_audit.json` (per-strategy handoff-fidelity snapshot).
- Appends an iteration block to `strategies/_iterate_context.md` — which subsequent iterations' agents should read.

Do NOT skip any of steps 1–3. They are what makes the iteration data usable for the fidelity paper.

## Stopping conditions (STRICT)

Stop early only when ALL of the following hold simultaneously:
1. `feedback-analyst.stop_suggested == true` in the most recent iteration.
2. `meta-reviewer` was invoked after that signal and returned `action_taken.type == "none"` — i.e., confirmed no structural fix would unblock progress.
3. No new `knowledge/patterns/` file was created in the last K iterations.

If condition 2 is NOT met, **do not stop** — invoke meta-reviewer first. A `stop_suggested` from feedback-analyst is a *request*, not a command. The meta-reviewer has the final say because only it can see the framework-level picture.

Also stop on:
- Two consecutive hard runtime errors in `backtest-runner` that survive an engine fix attempt.
- User interruption.

## Token discipline

- Delegate actual file I/O, search, and computation to specialized agents. Main session decides routing, not content.
- Never dump full `report.json` or full knowledge files into the loop log. Summarize to key fields.
- Meta-reviewer output is verbose — fold it into a 1-line log entry once consumed.
- When calling an agent, pass only the minimal context it needs (strategy_id, metrics, or summary lines). The agent will grep what it needs.

## Final report

```json
{
  "iterations_run": <n>,
  "action_histogram": {"new_strategy": <n>, "engine_fix": <n>, "dsl_extension": <n>, "pattern_consolidation": <n>, "meta_review": <n>},
  "seed_histogram": {"local": <n>, "escape": <n>, "paradigm": <n>, "meta": <n>},
  "stopped_reason": "completed | saturated_confirmed | consecutive_errors | user_interrupt",
  "framework_changes": [
    {"iter": <i>, "type": "<type>", "files": ["..."], "justification": "..."}
  ],
  "strategies": [
    {"iter": <i>, "strategy_id": "...", "return_pct": ..., "n_trades": ..., "seed_type": "local | escape | paradigm | meta"}
  ],
  "best": {"strategy_id": "...", "return_pct": ...},
  "knowledge_delta": {
    "lessons_added": <n>,
    "patterns_added": <n>,
    "graph_nodes_before": <n>,
    "graph_nodes_after": <n>
  },
  "audit_status": "<summary from final scripts/audit_principles.py run>"
}
```

The `framework_changes` list is the critical artifact — it's the record of how the framework evolved during this /iterate call. Future runs depend on it for continuity.
