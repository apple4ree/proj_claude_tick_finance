---
name: experiment
description: Unified end-to-end alpha discovery + validation + autonomous iteration framework. Supersedes /iterate and /new-strategy. Combines programmatic raw-EDA (Phase 1), optional LLM-agent design, 4-gate validation, BH benchmark, and N-iteration orchestration with meta-reviewer checkpoints.
---

# /experiment — Unified Alpha-Discovery Pipeline

Runs the full alpha-discovery-to-feedback loop as a single sequence. Supersedes the legacy `/iterate` and `/new-strategy` commands — this is the canonical entry point for every strategy-generation experiment.

## Arguments (parsed from the user message)

| Key | Default | Example |
|---|---|---|
| `--market` | **required** | `crypto_1d` `crypto_1h` `crypto_15m` `crypto_5m` `crypto_lob` |
| `--symbols` | **required** | `BTCUSDT,ETHUSDT,SOLUSDT` |
| `--is-start --is-end` | **required** | Bar: `2025-07-01 2025-10-31` · LOB: `2026-04-19T06:00:00 2026-04-19T22:00:00` (ISO UTC) |
| `--oos-start --oos-end` | **required** | Bar: `2025-11-01 2025-12-31` · LOB: `2026-04-19T22:00:00 2026-04-20T00:00:00` |
| `--design-mode` | `auto` | `auto` (rule templates) · `agent` (alpha-designer Agent chain) · `skip` (strategies already exist) |
| `--feedback-mode` | `both` | `programmatic` · `agent` · `both` |
| `--ranks` | `1` | top_robust ranks to cycle across iterations (1-indexed; `1` = top_robust[0]). Comma-separated list, e.g. `1,2,3`. Ranks **cycle across iterations** (iter 1 uses ranks[0], iter 2 uses ranks[1 % len], …) — they do NOT spawn multiple strategies within a single iteration. |
| `--strategies-pattern` | derived | Glob pattern for an existing set |
| `--n-iterations` | **10** (**minimum enforced**) | Number of design→validate→feedback cycles; **must be ≥ 10** per 2026-04-19 policy |
| `--meta-review-every` | `5` | Invoke meta-reviewer every K iterations |
| `--output-dir` | `experiments/run_<date>` | — |
| `--smoke-test` | off | Bypass the n-iterations ≥ 10 enforcement. Only use for infrastructure verification, NOT for strategy evaluation. |

## Execution discipline (MANDATORY — 2026-04-20)

Once `/experiment` starts, the orchestrator **MUST run through all N iterations without asking the user for confirmation at any intermediate point**. Specifically:

1. **No scope-reduction questions mid-run.** Do NOT present "options" to the user (e.g., "should I run rank 0 only?", "full sprint vs narrowed?", "foreground vs /loop?"). The CLI arguments at launch are the final contract; the orchestrator follows them verbatim. Changing scope requires the user to abort (`Ctrl+C`) and re-invoke with different flags.

2. **No "context/time budget" early stops.** Orchestrator context usage is not a stop condition. Each iteration's agent chain runs in **fresh subagent contexts** (isolated from the orchestrator); only structured summaries return to the orchestrator, so N=10 iterations fits in one session. Do not pre-emptively suggest background/`/loop` pacing unless `--n-iterations >= 50`.

3. **Stop conditions are ONLY those listed in §2g.** Nothing else — not scope concerns, not wall-clock estimates, not "this might take too long", not "the smoke run already showed the answer". The loop proceeds deterministically through all N iterations or a §2g condition.

4. **ONE strategy per iteration (portfolio mode is the default).** Each iteration produces exactly ONE multi-symbol portfolio strategy under `strategies/<id>/`, with `universe.symbols` containing all targets unified (example: `[BTCUSDT, ETHUSDT, SOLUSDT]` is ONE strategy, not three). Do NOT interpret `--ranks 0,1,2` × 3 symbols as "9 strategies per iter". The correct reading: for each iteration, alpha-designer picks ONE rank from `top_robust[]` (1-indexed per CLAUDE.md §Rules), and spec-writer creates ONE spec.yaml unifying all target symbols.

5. **`--ranks` cycles across iterations, not within one iteration.** If `--ranks 1,2,3` is passed with `--n-iterations 10`, iter 1 uses rank 1, iter 2 uses rank 2, iter 3 uses rank 3, iter 4 wraps to rank 1, and so on. Never spawn multiple strategies within a single iteration — each iteration is one agent-chain + one backtest + one critique.

6. **Budget assumption**: 10-iter full run takes ~60-120 min wall-clock. Do not offer to narrow scope for perceived runtime risk — that decision already lives in the user's `--n-iterations` choice.

7. **Prior smoke runs do NOT short-circuit the current run.** Even if a recent `--smoke-test` run captured a lesson (e.g., "SOL spread-gate fix"), the current non-smoke run must still execute its full N iterations — the loop's purpose is *lesson propagation and reinforcement*, not first-time discovery.

## Iteration budget policy (2026-04-19)

**Hard rule**: `/experiment` requires `--n-iterations >= 10`. Single-shot or low-N runs are rejected at Step 0 with a clear error, unless `--smoke-test` is provided (for pipeline plumbing verification only).

Rationale: one iteration produces noise; autonomous learning requires enough cycles for `feedback-analyst` lessons to propagate back into `alpha-designer` / `execution-designer` decisions. 10 is the empirical floor below which the loop's self-correction cannot demonstrate directional improvement.

Enforcement sequence: at Step 0, after audit_principles succeeds but before Phase 1:

```
if args.n_iterations < 10 and not args.smoke_test:
    abort with message:
      "[/experiment] policy violation: --n-iterations=<N> < 10.
       Set --n-iterations >= 10, or pass --smoke-test for infra-only runs.
       (See CLAUDE.md Rules section, 2026-04-19 policy.)"
```

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

**Bar markets** (`crypto_1d | crypto_1h | crypto_15m | crypto_5m`):
```bash
python scripts/discover_alpha.py \
  --market <market> --symbols <symbols> \
  --is-start <is-start> --is-end <is-end> \
  --output data/signal_briefs_v2/<market>.json
```

**LOB market** (`crypto_lob`): tick-level IC on Binance L2 snapshots (100ms cadence).
```bash
python scripts/discover_alpha_lob.py \
  --symbols <symbols> \
  --is-start '<YYYY-MM-DDTHH:MM:SS>' \
  --is-end   '<YYYY-MM-DDTHH:MM:SS>' \
  --horizons-ticks 10,100,1000,10000 \
  --fee-bps 0 \
  --threshold-percentile 90 \
  --output data/signal_briefs_v2/crypto_lob.json
```
Note: LOB `--is-start/--is-end` accept ISO datetimes (UTC) rather than the date-only form used for bar markets. `--fee-bps 0` reflects the maker assumption for MM / spread_capture paradigms.

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
   Parsing convention: the script prints a JSON object on stdout with `ok: bool` and `failures: list[str]`, and exits with status 0/1. The `ok` field in the JSON is authoritative; the exit code mirrors it. Read stdout JSON — do NOT rely solely on the exit code (you will not see the failure messages).

   If `ok=false`: log `failures` to `strategies/_iterate_context.md` as `"<iter>: alpha-designer schema fail — <first failure>"`, SKIP execution-designer, advance to next seed (or abort run).

2. `Agent(subagent_type="execution-designer", prompt="…")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent execution-designer --output '<execution_json>'
   ```
   If `ok=false`: log failure, SKIP spec-writer and all downstream steps, advance.

   **Adapter (before invoking spec-writer):** The returned `ExecutionHandoff` nests `alpha: AlphaHandoff`. Spec-writer expects a flat shape with `entry_execution`, `exit_execution`, `position`, alpha fields at the top level, plus `alpha_draft_path` and `execution_draft_path` (legacy field names). The orchestrator flattens before calling spec-writer, and explicitly injects both draft-path fields so spec-writer can read the MD rationales:
   ```
   alpha_json = execution_json["alpha"]
   exec_rest = {k: v for k, v in execution_json.items() if k != "alpha"}
   flat = {**alpha_json, **exec_rest}
   # Legacy path keys that spec-writer.md reads
   flat["alpha_draft_path"] = alpha_json["draft_md_path"]
   flat["execution_draft_path"] = execution_json["draft_md_path"]
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
Pick the rank-<rank> entry (1-indexed; rank=1 means top_robust[0], the highest-ranked robust signal).
Target market: <market>. Target symbols (portfolio, unified): <symbols>.
Read strategies/_iterate_context.md for lessons from prior iterations in this run.
Your strategy MUST use the rank-<rank> feature × horizon as its primary signal.

Produce EXACTLY ONE AlphaHandoff for this iteration. The spec that follows
will unify all target symbols in a single `universe.symbols` list (portfolio
mode) — do NOT create per-symbol strategies. Output `signal_brief_rank` (1-indexed)
in the AlphaHandoff JSON.
```

**Rank-cycling rule**: The `--ranks` CLI flag (default `1`) is a list. For iteration `i` (1-based), use `ranks[(i - 1) % len(ranks)]`. Example: `--ranks 1,2,3 --n-iterations 10` → ranks [1, 2, 3, 1, 2, 3, 1, 2, 3, 1]. Each iteration still creates **one portfolio strategy**, not one-per-rank.

**skip**: resolve strategy set via `--strategies-pattern`.

### 2b. Backtest

For each new/selected strategy id `<sid>`, choose the artifact script by market:
```bash
# Daily bars (crypto_1d)
python scripts/bar_full_artifacts.py --id <sid>

# Intraday bars (crypto_1h / crypto_15m / crypto_5m)
python scripts/intraday_full_artifacts.py --id <sid>

# LOB (crypto_lob) — wraps engine.runner + MFE/MAE enrichment
python scripts/lob_full_artifacts.py --id <sid>
```

All three produce the same canonical artifact set (`report.json`, `trace.json`, `analysis_trace.{json,md}`, `report.html`) so downstream validation / BH / feedback treat them identically.

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

## LOB Collector ownership (crypto_lob market only)

When `--market crypto_lob`, data is populated by `scripts/binance_lob_collector.py` running as a long-lived background process (not spawned by `/experiment`). Orchestrator responsibilities:

1. **Before Step 1**: verify the collector daemon is alive and data exists for the requested `[is-start, oos-end]` window:
   ```bash
   pgrep -f "binance_lob_collector" > /dev/null || \
     echo "WARNING: LOB collector not running — start with: nohup python scripts/binance_lob_collector.py --symbols <syms> > /tmp/binance_lob.log 2>&1 &"
   # verify partition coverage:
   python -c "from engine.data_loader import iter_events_crypto_lob; import time; \
              n=sum(1 for _ in iter_events_crypto_lob(<is_start_ns>, <oos_end_ns>, <syms>)); \
              print(f'LOB snapshots in window: {n:,}')"
   ```
2. **During run**: do NOT kill the collector. The process must keep running to accumulate forward-going data for the next iteration.
3. **After Step 4 post-flight audit**: log current parquet size and last `recv_count` from `/tmp/binance_lob.log` so the next session knows how much was accumulated.
4. **If collector is not running** and `--market crypto_lob` was requested, abort with the message above — do NOT attempt to proceed with stale / empty data.
5. This collector is **external infrastructure**; no agent is responsible for managing it. The orchestrator (the Claude instance running `/experiment`) is the sole owner.
