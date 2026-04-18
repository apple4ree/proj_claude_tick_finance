---
name: experiment
description: Unified end-to-end alpha discovery + validation + autonomous iteration framework. Supersedes /iterate and /new-strategy. Combines programmatic raw-EDA (Phase 1), optional LLM-agent design, 4-gate validation, BH benchmark, and N-iteration orchestration with meta-reviewer checkpoints.
---

# /experiment — Unified Alpha-Discovery Pipeline

Runs the full alpha-discovery-to-feedback loop as a single sequence. Supersedes the legacy `/iterate` and `/new-strategy` commands — this is the canonical entry point for every strategy-generation experiment.

## Arguments (parsed from the user message)

| Key | Default | Example |
|---|---|---|
| `--market` | **required** | `crypto_1h` `crypto_1d` `crypto_15m` |
| `--symbols` | **required** | `BTCUSDT,ETHUSDT,SOLUSDT` |
| `--is-start --is-end` | **required** | `2025-07-01 2025-10-31` |
| `--oos-start --oos-end` | **required** | `2025-11-01 2025-12-31` |
| `--design-mode` | `auto` | `auto` (rule templates) · `agent` (alpha-designer Agent chain) · `skip` (strategies already exist) |
| `--feedback-mode` | `both` | `programmatic` · `agent` · `both` |
| `--ranks` | `0,1,2` | top_robust ranks to promote to strategies |
| `--strategies-pattern` | derived | Glob pattern for an existing set |
| `--n-iterations` | `1` | Number of design→validate→feedback cycles |
| `--meta-review-every` | `5` | Invoke meta-reviewer every K iterations |
| `--output-dir` | `experiments/run_<date>` | — |

## Top-level execution flow

```
[0]  audit_principles.py                       # engine sanity before anything
[1]  Phase 1  discover_alpha.py                # signal_brief_v2 (ONCE per run)
[2]  Loop iterations (1..N):
       a. Phase 2 design (auto | agent | skip)
       b. Phase 2.5 backtest per new strategy
       c. Phase 3 validate (4 gates)
       d. Phase 3.5 BH benchmark
       e. Phase 4 programmatic feedback (ALWAYS) + optional agent feedback
       f. iterate_finalize per strategy → _iterate_context.md
       g. Check stop conditions
       h. Every K iterations → meta-reviewer
[3]  Aggregate summary + optional paper-section update
[4]  audit_principles.py                       # engine sanity after
```

Create a TaskList entry for each numbered step. Mark in_progress/completed as you go.

---

## Step 0 — Pre-flight

```bash
python scripts/audit_principles.py
```

If not 12/12 PASS, invoke `code-generator` agent with mode=`bugfix` and `audit_principles.py` output. Block all further steps until fixed.

## Step 1 — Phase 1: alpha discovery (once per run)

```bash
python scripts/discover_alpha.py \
  --market <market> --symbols <symbols> \
  --is-start <is-start> --is-end <is-end> \
  --output data/signal_briefs_v2/<market>.json
```

Read the resulting `signal_briefs_v2/<market>.json`. The discovery is run **once per experiment run** — subsequent iterations re-use it unless the outer loop decides a rediscovery is warranted (e.g., after a pivot).

## Step 2 — Iteration loop (repeats up to N)

For iteration `i` in 1..N:

### 2a. Design (branch on `--design-mode`)

**auto** (programmatic):
For each rank in `--ranks`:
```bash
python scripts/gen_strategy_from_brief.py \
  --brief data/signal_briefs_v2/<market>.json \
  --rank <rank> --symbols <symbols> --market <market>
```

**agent** (sub-agent chain):
For each symbol × rank:
1. `Agent(subagent_type="alpha-designer", prompt="... see below ...")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent alpha-designer --output '<alpha_json>'
   ```
   If `ok=false`: log `failures` to `strategies/_iterate_context.md` as `"<iter>: alpha-designer schema fail — <first failure>"`, SKIP execution-designer, advance to next seed (or abort run).

2. `Agent(subagent_type="execution-designer", prompt="…")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent execution-designer --output '<execution_json>'
   ```
   If `ok=false`: log failure, SKIP spec-writer and all downstream steps, advance.

   **Adapter (before invoking spec-writer):** The returned `ExecutionHandoff` nests `alpha: AlphaHandoff`. Spec-writer expects a flat shape with `entry_execution`, `exit_execution`, `position`, and alpha fields at the top level. The orchestrator flattens before calling spec-writer:
   ```
   flat = {**execution_json["alpha"], **{k: v for k, v in execution_json.items() if k != "alpha"}}
   Agent(subagent_type="spec-writer", prompt=f"... input={json.dumps(flat)} ...")
   ```

3. `Agent(subagent_type="spec-writer", prompt="…")`
4. `Agent(subagent_type="strategy-coder", prompt="…")` (skip if non-python)

After each agent call:
```bash
python scripts/log_agent_call.py --strategy <sid> --agent <name> \
  --model sonnet --status ok --output-hash <hash>
python scripts/verify_outputs.py --agent <name> --output '<agent_json>'
```

If verify_outputs returns `ok=false`: re-dispatch the agent with the failure note. If it fails twice, escalate to code-generator (for DSL/schema gaps) or skip the strategy.

**Design prompt template for alpha-designer (agent mode):**
```
The signal brief v2 is at data/signal_briefs_v2/<market>.json.
Pick the rank-<rank> entry (robust signal with cross-symbol IC).
Target: <market> <symbol>.
Read strategies/_iterate_context.md for lessons from prior iterations in this run.
Your strategy MUST use the rank-<rank> feature × horizon as its primary signal.
Output signal_brief_rank and deviation_from_brief fields in idea.json.
```

**skip**: resolve strategy set via `--strategies-pattern`.

### 2b. Backtest

For each new/selected strategy id `<sid>`:
```bash
python scripts/intraday_full_artifacts.py --id <sid>    # for 1h/15m/5m
# or
python scripts/bar_full_artifacts.py --id <sid>         # for daily
```

If the backtest reports `anomaly_flag != null` or an invariant violation of type `high`, route to code-generator (`mode=bugfix`) with the anomaly before proceeding.

### 2c. Validate (4 gates)

```bash
python scripts/validate_strategy.py \
  --pattern '<market>_*' \
  --oos-start <oos-start> --oos-end <oos-end>
```

### 2d. BH benchmark

```bash
python scripts/benchmark_vs_bh.py \
  --pattern '<market>_*' --out <output-dir>/bh_benchmark.json
```

### 2e. Feedback (branch on `--feedback-mode`)

**Always run programmatic:**
```bash
python scripts/run_feedback.py --pattern '<market>_*'
```

**If `--feedback-mode` ∈ {`agent`, `both`}**, for each strategy that failed at least one gate:
1. `Agent(subagent_type="alpha-critic", prompt="Analyse strategies/<sid>/ — WIN/LOSS bucketing, signal predictiveness. Use report.json, trace.json, analysis_trace.md. Save output to strategies/<sid>/alpha_critique.md.")`
2. `Agent(subagent_type="execution-critic", prompt="Analyse strategies/<sid>/ — fill mechanics, fee burden, stop/target calibration. Save to strategies/<sid>/execution_critique.md.")`
3. After both:
   ```bash
   python scripts/verify_outputs.py --agent alpha-critic --output '{"critique_md":"strategies/<sid>/alpha_critique.md"}'
   python scripts/verify_outputs.py --agent execution-critic --output '{"critique_md":"strategies/<sid>/execution_critique.md"}'
   ```
4. `Agent(subagent_type="feedback-analyst", prompt="Reconcile strategies/<sid>/alpha_critique.md and execution_critique.md. Write knowledge/lessons/<date>_<slug>.md and update strategies/_iterate_context.md. Set stop_suggested=true if this family has exhausted its edge.")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent feedback-analyst --output '<feedback_json>'
   ```
   If `ok=false`: do NOT finalize `knowledge/lessons/<date>_<slug>.md`. Log failure, continue loop (feedback was advisory, not blocking).

### 2f. Finalize per strategy

For each strategy this iteration generated or validated:
```bash
python scripts/iterate_finalize.py \
  --strategy <sid> --iter <i> --seed-type <local|escape|paradigm|meta> \
  --return-pct <x> --n-roundtrips <n> \
  --alpha-finding "<…>" --execution-finding "<…>" \
  --priority <alpha|execution|both> \
  --next-seed "<…>"
```

This appends a block to `strategies/_iterate_context.md` (idempotent).

### 2g. Stop conditions

After this iteration, break the loop if ANY of:
- `i >= N` (reached max iterations)
- All strategies in this iteration have `validation.passed == true` AND mean OOS IR > 1.0 (strong alpha found, stop to avoid over-refining)
- ≥3 consecutive iterations with no new strategy passing all 4 gates (stalled)
- `feedback-analyst.stop_suggested == true` in agent mode (but only if meta-reviewer has weighed in at least once — see 2h)

### 2h. Meta-review (every K iterations)

If `i % --meta-review-every == 0`:
```
Agent(subagent_type="meta-reviewer",
      prompt="Audit the experiment run at <output-dir>. Read research-state.yaml,
              findings.md, strategies/_iterate_context.md, and the last <K>
              iteration artifacts. Propose: direction change (deepen/broaden/pivot/conclude),
              engine fixes needed, or DSL/schema gaps to file with code-generator.")
```
Then:
```bash
python scripts/verify_outputs.py --agent meta-reviewer --output '<mr_json>'
```

If meta-reviewer proposes `direction: pivot`, go back to Step 1 with the new hypothesis. If `direction: conclude`, exit the loop and go to Step 3.

---

## Step 3 — Aggregate summary

Write `<output-dir>/experiment_summary.md`:
```markdown
# Experiment — <timestamp>

Market: <market>  Symbols: <symbols>
IS: <is-start> → <is-end>   OOS: <oos-start> → <oos-end>
Design: <design-mode>  Feedback: <feedback-mode>  N iterations: <N>

## Top robust signals (Phase 1 v2)
| rank | feature | horizon | avg_IC | min|IC| |
| ... |

## Iterations executed
| iter | strategies generated | passed 4 gates | meta-review? |

## Final leaderboard (sorted by OOS IR)
| strategy | origin | IR_full | IR_oos | passed |

## Lessons added
- ...

## Artifacts
- signal_brief_v2.json · bh_benchmark.json · pipeline_summary.json
```

## Step 4 — Post-flight

```bash
python scripts/audit_principles.py
```

Must still be 12/12.

---

## Relationship to legacy commands

- **`/iterate`** — **DEPRECATED in favor of `/experiment --design-mode agent --n-iterations N --feedback-mode agent`.**
- **`/new-strategy`** — equivalent to `/experiment --design-mode agent --n-iterations 1` with a single symbol.

`/iterate.md` and `/new-strategy.md` are kept for archival reference; point users to `/experiment`.

## Safety and audit

- OOS dates MUST NOT overlap with IS.
- The project's locked final-OOS (2026-03-23 ~ 2026-03-30 KRX) MUST NOT be used as OOS unless this is the final validation run.
- `scripts/audit_principles.py` is run BEFORE and AFTER every experiment.
- `scripts/log_agent_call.py` records every agent invocation for telemetry.
- `scripts/verify_outputs.py` catches mis-routed or malformed agent outputs.
- `strategies/_iterate_context.md` is append-only; never rewrite prior iteration blocks.
- `knowledge/lessons/` accumulates feedback-analyst output when agent-mode is used.
