---
description: Open-ended autonomous meta-loop. Runs N iterations advancing an initial seed, with freedom to evolve the framework (engine fixes, DSL extensions, pattern synthesis, methodology shifts) — not just tune strategy parameters. Invokes meta-reviewer every K iterations.
argument-hint: <N> [<initial seed — optional>]
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

1. **New strategy** (standard path) — ideator → spec-writer → [code-generator if missing primitive] → backtest-runner → feedback-analyst. When invoking feedback-analyst, pass the full JSON returned by backtest-runner as the metrics argument — this satisfies feedback-analyst's "Optional metrics" input and prevents it from re-reading `report.json`.
2. **Engine fix** — when backtest-runner's `anomaly_flag` or an audit check flags a principle violation that blocks progress. Route: code-generator (mode=bugfix) → re-run audit → return to the strategy that triggered it.
3. **DSL extension** — when spec-writer reports the current grammar cannot express an idea pattern you're seeing repeatedly. Route: spec-writer (meta-authority) or code-generator (mode=dsl_ext), followed by example update.
4. **Pattern consolidation** — when ≥3 lessons share a root cause. Route: feedback-analyst or strategy-ideator writes `knowledge/patterns/<id>.md` and rebuilds the graph.
5. **Meta-review** — on K boundary or when stuck. Route: meta-reviewer, then use its `meta_seed` as input to action #1 on the next iteration.

## Loop structure

Maintain an in-memory log of iteration outcomes. Do NOT re-read report.json files — use only the JSON each agent returns.

```
for i in 1..N:
    state = summarize(log)            # brief, token-efficient
    action = decide_next_action(state, current_seed)
    result = execute(action)
    log.append({iter: i, action: action.type, result: result.summary})

    # anomaly routing
    if result.anomaly_flag:
        route to code-generator (bugfix) or meta-reviewer (escalation)

    # meta cadence
    if i % K == 0 and i < N:
        mr = invoke meta-reviewer with log
        current_seed = mr.meta_seed

    # stop conditions
    if all of:
        - feedback-analyst.stop_suggested == true
        - meta-reviewer has been invoked this iteration
        - meta-reviewer.action_taken.type == "none"
      then break  # genuinely saturated

    current_seed = result.next_seed or meta_seed
```

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
  "stopped_reason": "completed | saturated_confirmed | consecutive_errors | user_interrupt",
  "framework_changes": [
    {"iter": <i>, "type": "<type>", "files": ["..."], "justification": "..."}
  ],
  "strategies": [
    {"iter": <i>, "strategy_id": "...", "return_pct": ..., "n_trades": ...}
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
