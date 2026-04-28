"""Chain 1 orchestrator — end-to-end (Phase F).

Wires together the 7 Chain 1 agents:

  ①  signal-generator    (LLM; stage 1_generation)
  ②  signal-evaluator    (hybrid; stage 2_evaluation)
  ②.5 code-generator     (deterministic; stage 2.5_codegen)
  ②.75 fidelity-checker  (deterministic; stage 2.75_fidelity)
  ③  backtest-runner     (deterministic; stage 3_backtest)
  ④  feedback-analyst    (hybrid; stage 4_feedback)
  ⑤  signal-improver     (hybrid; stage 5_improvement)

An iteration:
  - Calls signal-generator with prior feedbacks / improvement
  - For each proposed spec: evaluator → (if valid) code-gen → fidelity (retry ≤3)
    → backtest → feedback
  - Aggregates triples → signal-improver → proposals for next iteration
  - Appends a summary line to signal-generator's prior_iterations_index.md

Convergence / stop conditions:
  - Reach max_iterations (hard cap)
  - `convergence_window` consecutive iterations with no WR improvement above
    `convergence_epsilon`
  - All specs in an iteration are retired (no survivors)
  - Orchestrator-level fatal error

Offline mode: pass --skip-llm-agents at CLI to short-circuit all LLM agents
(generator will then read a user-supplied seed-specs.json instead).

CLI:
    python -m chain1.orchestrator validate-agents
    python -m chain1.orchestrator dry-run --iterations 1
    python -m chain1.orchestrator det-pipeline --spec-json <path> ...
    python -m chain1.orchestrator run --max-iter 5 --n-candidates 3 \
                                       --symbols 005930 000660 005380 \
                                       --dates 20260326
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_ROOT = REPO_ROOT / ".claude" / "agents" / "chain1"
SHARED_DIR = AGENTS_ROOT / "_shared"
ITERATIONS_ROOT = REPO_ROOT / "iterations"
CONFIG_PATH = REPO_ROOT / "config.yaml"
PRIOR_INDEX_PATH = AGENTS_ROOT / "signal-generator" / "references" / "prior_iterations_index.md"
PRIOR_AUTO_LOG_PATH = AGENTS_ROOT / "signal-generator" / "references" / "prior_iterations_auto_log.md"

if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import (  # noqa: E402
    AgentManifest,
    REQUIRED_AGENT_COMPONENTS,
    IterationLog,
    SignalSpec,
    BacktestResult,
    Feedback,
    ImprovementProposal,
)

CHAIN1_AGENT_ORDER = [
    "signal-generator",
    "signal-evaluator",
    "code-generator",
    "fidelity-checker",
    "backtest-runner",
    "feedback-analyst",
    "signal-improver",
    "chain2-gate",   # stage 6 — post-iteration promotion candidate selector
]

DEFAULT_RUN_CONFIG = {
    "universe": {"symbols": ["005930", "000660", "005380"], "dates": ["20260326"]},
    "iteration": {
        "max_iterations": 5,
        "n_candidates_per_iter": 3,
        "convergence_window": 3,
        "convergence_epsilon": 0.005,
    },
    "fidelity": {"max_retries_on_fail": 3},
    "artifacts": {"root": "iterations"},
    "execution": {"skip_llm_agents": False},
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Load config.yaml, falling back to DEFAULT_RUN_CONFIG if absent."""
    cfg = json.loads(json.dumps(DEFAULT_RUN_CONFIG))  # deep copy
    if CONFIG_PATH.exists():
        try:
            on_disk = yaml.safe_load(CONFIG_PATH.read_text()) or {}
            chain1 = on_disk.get("chain1", {})
            # deep merge
            def _merge(base: dict, overlay: dict) -> dict:
                for k, v in overlay.items():
                    if isinstance(v, dict) and isinstance(base.get(k), dict):
                        base[k] = _merge(base[k], v)
                    else:
                        base[k] = v
                return base
            cfg = _merge(cfg, chain1)
        except Exception as e:  # noqa: BLE001
            print(f"[config] WARNING: failed to parse {CONFIG_PATH}: {e}")
    return cfg


# ---------------------------------------------------------------------------
# Agent discovery + manifest validation
# ---------------------------------------------------------------------------


def discover_agents() -> dict[str, Path]:
    if not AGENTS_ROOT.exists():
        raise FileNotFoundError(f"Chain 1 agents root not found: {AGENTS_ROOT}")
    agents = {}
    for p in sorted(AGENTS_ROOT.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        agents_md = p / "AGENTS.md"
        if not agents_md.exists():
            raise FileNotFoundError(f"{p.name}: missing AGENTS.md")
        agents[p.name] = p
    return agents


def load_manifest(agent_dir: Path) -> AgentManifest:
    text = (agent_dir / "AGENTS.md").read_text()
    if not text.startswith("---"):
        raise ValueError(f"{agent_dir.name}: AGENTS.md has no YAML frontmatter")
    _, fm_raw, body = text.split("---", 2)
    meta = yaml.safe_load(fm_raw)
    m = AgentManifest(**meta)
    section_markers = [
        "## 1. System Prompt", "## 2. User Prompt", "## 3. Reference",
        "## 4. Input Schema", "## 5. Output Schema", "## 6. Reasoning Flow",
    ]
    missing = [s for s in section_markers if s not in body]
    if missing:
        raise ValueError(f"{agent_dir.name}: AGENTS.md missing sections: {missing}")
    return m


def load_io_schemas(agent_dir: Path, manifest: AgentManifest) -> tuple[type[BaseModel], type[BaseModel]]:
    def _load(py_rel: str, cls_name: str) -> type[BaseModel]:
        py_path = agent_dir / py_rel
        if not py_path.exists():
            raise FileNotFoundError(f"{agent_dir.name}: schema file missing: {py_rel}")
        spec = importlib.util.spec_from_file_location(f"{agent_dir.name}_{py_rel}", py_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls = getattr(mod, cls_name)
        return cls

    in_rel, in_cls = manifest.input_schema.split(":", 1)
    out_rel, out_cls = manifest.output_schema.split(":", 1)
    return _load(in_rel, in_cls), _load(out_rel, out_cls)


def validate_agents() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    agents = discover_agents()
    for name in CHAIN1_AGENT_ORDER:
        if name not in agents:
            raise FileNotFoundError(f"Missing expected agent: {name}")
    for name in agents:
        if name not in CHAIN1_AGENT_ORDER:
            raise ValueError(f"Unexpected agent dir: {name}")
    for name in CHAIN1_AGENT_ORDER:
        ad = agents[name]
        manifest = load_manifest(ad)
        InModel, OutModel = load_io_schemas(ad, manifest)
        results[name] = {
            "path": str(ad.relative_to(REPO_ROOT)),
            "stage": manifest.stage,
            "version": manifest.version,
            "input_model": InModel.__name__,
            "output_model": OutModel.__name__,
            "components_ok": all(c in manifest.required_components for c in REQUIRED_AGENT_COMPONENTS),
        }
    return results


# ---------------------------------------------------------------------------
# Iteration artifact management
# ---------------------------------------------------------------------------


def ensure_iteration_dir(idx: int) -> Path:
    d = ITERATIONS_ROOT / f"iter_{idx:03d}"
    for sub in ["specs", "evaluations", "code", "fidelity", "results", "feedback", "improvements", "traces"]:
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def write_iteration_log(idx: int, log: IterationLog) -> None:
    d = ensure_iteration_dir(idx)
    (d / "iteration_log.json").write_text(log.model_dump_json(indent=2))


def append_to_prior_index(iter_idx: int, triples: list[dict]) -> None:
    """Append compact per-spec lines to prior_iterations_auto_log.md.

    Note (post-v5): we no longer touch prior_iterations_index.md — that file is
    manually curated. Auto-bloat goes here, separate file, not in signal-generator
    required-reading list.
    """
    if not PRIOR_AUTO_LOG_PATH.exists():
        PRIOR_AUTO_LOG_PATH.write_text(
            "# Prior Iterations Auto-Log\n\n"
            "Auto-appended by orchestrator. This file is **not** in signal-generator's\n"
            "required-reading list. Use `grep` to look up a specific spec_id.\n"
            "Curated lessons live in `prior_iterations_index.md`.\n"
        )
    existing = PRIOR_AUTO_LOG_PATH.read_text()
    addition_lines = [f"\n### iteration {iter_idx:03d} ({dt.datetime.utcnow().isoformat()}Z)\n"]
    for t in triples:
        spec = t["spec"]
        result = t["result"]
        feedback = t["feedback"]
        addition_lines.append(f"""
#### {spec.get("spec_id", "?")}
- **Formula**: `{spec.get("formula", "?")}`
- **Primitives**: {spec.get("primitives_used", [])}
- **Threshold / Horizon**: {spec.get("threshold", "?")}, {spec.get("prediction_horizon_ticks", "?")} ticks
- **WR**: {result.get("aggregate_wr", "?")}
- **Expectancy**: {result.get("aggregate_expectancy_bps", "?")} bps
- **Feedback tag**: {feedback.get("recommended_next_direction", "?")}
- **Notes**: {feedback.get("recommended_direction_reasoning", "?")[:120]}
""")
    new_text = existing + "\n".join(addition_lines)
    PRIOR_AUTO_LOG_PATH.write_text(new_text)


# ---------------------------------------------------------------------------
# Stage wrappers (call the concrete implementations)
# ---------------------------------------------------------------------------


def stage_generate(
    iter_idx: int, n_candidates: int, symbols: list[str], dates: list[str],
    prior_feedback: list[Feedback] | None, prior_improvement: ImprovementProposal | None,
    skip_llm: bool,
) -> list[SignalSpec]:
    if skip_llm:
        # Offline mode: generator needs LLM. Signal the caller to use a seed-specs file instead.
        raise RuntimeError("Offline signal generation requires a seed-specs file (use run-offline-seed).")
    from chain1.agents.signal_generator import generate_signals
    return generate_signals(
        iteration_idx=iter_idx,
        n_candidates=n_candidates,
        symbols=symbols,
        dates=dates,
        prior_feedback=prior_feedback,
        prior_improvement=prior_improvement,
        fee_bps_rt=_FEE_BPS_RT,
    )


def stage_evaluate(spec: SignalSpec, iter_idx: int, skip_llm: bool):
    from chain1.agents.signal_evaluator import evaluate_signal
    return evaluate_signal(spec, iter_idx, skip_llm=skip_llm)


def stage_codegen(spec: SignalSpec, iter_idx: int):
    from chain1.code_generator import generate_code
    out = ITERATIONS_ROOT / f"iter_{iter_idx:03d}" / "code" / f"{spec.spec_id}.py"
    return generate_code(spec, out)


def stage_fidelity(spec: SignalSpec, code):
    from chain1.fidelity_checker import run_fidelity
    return run_fidelity(spec, code)


_CALIBRATION_TABLE: dict | None = None  # populated by run_loop if path supplied
_FEE_BPS_RT: float = 0.0  # populated by run_loop; 0 ⇒ legacy WR-driven behaviour
_EXECUTION_MODE: str = "mid_to_mid"  # Path B: "mid_to_mid" | "maker_optimistic"
_PARALLEL: bool = False  # G (2026-04-28): per-iter spec parallelism (LLM async + backtest in thread)


def stage_backtest(spec: SignalSpec, code, symbols: list[str], dates: list[str],
                    save_trace: bool = True,
                    horizon_grid: tuple[int, ...] | None = None):
    from chain1.backtest_runner import run_backtest, DEFAULT_HORIZON_GRID
    trace_path = None
    if save_trace:
        trace_path = str(ITERATIONS_ROOT / f"iter_{spec.iteration_idx:03d}" / "traces" / f"{spec.spec_id}.trace.json")
    # Default mode = "regime_state" (2026-04-27 paradigm shift).
    # horizon_grid is ignored in regime-state mode (no fixed horizon).
    # Pass mode="fixed_h" to opt back into legacy fixed-H backtests.
    # execution_mode (Path B, 2026-04-27): "mid_to_mid" (default) | "maker_optimistic".
    return run_backtest(spec, code, symbols, dates,
                         save_trace=save_trace, trace_path=trace_path,
                         calibration_table=_CALIBRATION_TABLE,
                         mode="regime_state",
                         execution_mode=_EXECUTION_MODE)


def stage_feedback(spec: SignalSpec, result: BacktestResult, iter_idx: int,
                   recent_feedback: list[Feedback] | None, skip_llm: bool):
    from chain1.agents.feedback_analyst import analyze_feedback
    return analyze_feedback(
        spec, result, iter_idx,
        recent_feedback=recent_feedback,
        skip_llm=skip_llm,
        fee_bps_rt=_FEE_BPS_RT,
    )


def stage_improve(triples_dicts: list[dict], iter_idx: int, budget: int, skip_llm: bool):
    from chain1.agents.signal_improver import improve_signals
    return improve_signals(
        triples_dicts, iter_idx,
        next_iteration_budget=budget,
        skip_llm=skip_llm,
        fee_bps_rt=_FEE_BPS_RT,
    )


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------


async def _run_one_spec_async(
    spec: SignalSpec,
    iter_idx: int,
    iter_dir,
    symbols: list[str],
    dates: list[str],
    prior_feedback: list[Feedback] | None,
    log: IterationLog,
    max_fidelity_retries: int,
    skip_llm_agents: bool,
) -> dict | None:
    """One spec's full pipeline (eval -> codegen -> fidelity -> backtest -> feedback).

    Returns triple dict on success, None if any stage fails."""
    from chain1.agents.signal_evaluator import evaluate_signal_async
    from chain1.agents.feedback_analyst import analyze_feedback_async
    import asyncio as _asyncio

    print(f"\n  — spec {spec.spec_id} —")
    print(f"    formula={spec.formula} threshold={spec.threshold} horizon={spec.prediction_horizon_ticks}t")

    # ② Evaluate (async)
    try:
        evaluation = await evaluate_signal_async(spec, iter_idx, skip_llm=skip_llm_agents)
        (iter_dir / "evaluations" / f"{spec.spec_id}.json").write_text(evaluation.model_dump_json(indent=2))
        log.spec_evaluations.append(str((iter_dir / "evaluations" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
        if not evaluation.valid:
            print(f"    ② evaluation REJECT: {evaluation.concerns[:3]}")
            return None
        print(f"    ② evaluation OK (merit={evaluation.expected_merit})")
    except Exception as e:  # noqa: BLE001
        print(f"    ② evaluation raised: {e}")
        return None

    # ②.5 Code-gen + ②.75 Fidelity (sync, deterministic — wrap in to_thread for IO)
    code = None
    report = None
    for attempt in range(max_fidelity_retries):
        try:
            code = await _asyncio.to_thread(stage_codegen, spec, iter_idx)
            if attempt == 0:
                (iter_dir / "code" / f"{spec.spec_id}.codegen.json").write_text(code.model_dump_json(indent=2))
                log.generated_codes.append(code.code_path)
            print(f"    ②.5 codegen OK → {code.code_path}")
        except Exception as e:  # noqa: BLE001
            print(f"    ②.5 codegen raised: {e}")
            break

        try:
            report = await _asyncio.to_thread(stage_fidelity, spec, code)
            (iter_dir / "fidelity" / f"{spec.spec_id}.json").write_text(report.model_dump_json(indent=2))
            log.fidelity_reports.append(str((iter_dir / "fidelity" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
            if report.overall_passed:
                print(f"    ②.75 fidelity PASS")
                break
            fails = [c.name for c in report.checks if not c.passed]
            print(f"    ②.75 fidelity FAIL ({attempt+1}/{max_fidelity_retries}): {fails}")
        except Exception as e:  # noqa: BLE001
            print(f"    ②.75 fidelity raised: {e}")
            break

    if code is None or report is None or not report.overall_passed:
        print(f"    [spec {spec.spec_id}] fidelity gate not satisfied — skipping downstream")
        return None

    # ③ Backtest (sync, CPU-bound — wrap in to_thread; GIL released during numpy work)
    try:
        result = await _asyncio.to_thread(stage_backtest, spec, code, symbols, dates)
        (iter_dir / "results" / f"{spec.spec_id}.json").write_text(result.model_dump_json(indent=2))
        log.backtest_results.append(str((iter_dir / "results" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
        print(f"    ③ backtest: n_trades={result.aggregate_n_trades} "
              f"WR={result.aggregate_wr:.4f} exp={result.aggregate_expectancy_bps:+.3f}bps")
    except Exception as e:  # noqa: BLE001
        print(f"    ③ backtest raised: {e}")
        return None

    # ④ Feedback (async)
    try:
        feedback = await analyze_feedback_async(
            spec, result, iter_idx,
            recent_feedback=prior_feedback,
            skip_llm=skip_llm_agents,
            fee_bps_rt=_FEE_BPS_RT,
        )
        (iter_dir / "feedback" / f"{spec.spec_id}.json").write_text(feedback.model_dump_json(indent=2))
        log.feedback.append(str((iter_dir / "feedback" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
        print(f"    ④ feedback: recommendation={feedback.recommended_next_direction}")
    except Exception as e:  # noqa: BLE001
        print(f"    ④ feedback raised: {e}")
        return None

    return {
        "spec": spec.model_dump(),
        "result": result.model_dump(),
        "feedback": feedback.model_dump(),
    }


async def run_iteration_parallel(
    iter_idx: int,
    n_candidates: int,
    symbols: list[str],
    dates: list[str],
    prior_feedback: list[Feedback] | None,
    prior_improvement: ImprovementProposal | None,
    max_fidelity_retries: int = 3,
    skip_llm_agents: bool = False,
    seed_specs: list[SignalSpec] | None = None,
) -> tuple[list[dict], ImprovementProposal | list[ImprovementProposal] | None]:
    """Parallel version of run_iteration.

    Specs in the same iter run in parallel via asyncio.gather. LLM stages use
    litellm.acompletion. Sync stages (codegen, fidelity, backtest) are
    wrapped in asyncio.to_thread so other specs' LLM I/O can progress.

    All stages of a single spec remain sequential within that spec.
    """
    import asyncio as _asyncio
    iter_dir = ensure_iteration_dir(iter_idx)
    t_start = dt.datetime.utcnow()
    log = IterationLog(iteration_idx=iter_idx, started_at=t_start)

    print(f"\n═══ Iteration {iter_idx:03d} (parallel) ═══")

    # ① Generate (single LLM call, 4 specs at once — already \"parallel\")
    if seed_specs is not None:
        specs = seed_specs
        print(f"[iter {iter_idx}] ① using {len(specs)} seed specs (offline mode)")
    else:
        try:
            specs = stage_generate(iter_idx, n_candidates, symbols, dates,
                                    prior_feedback, prior_improvement, skip_llm=skip_llm_agents)
            print(f"[iter {iter_idx}] ① generated {len(specs)} candidates")
        except RuntimeError as e:
            print(f"[iter {iter_idx}] ① generation failed: {e}")
            log.finished_at = dt.datetime.utcnow()
            log.stop_reason = f"generation_failed: {e}"
            write_iteration_log(iter_idx, log)
            return [], None

    for s in specs:
        (iter_dir / "specs" / f"{s.spec_id}.json").write_text(s.model_dump_json(indent=2))
        log.signal_specs.append(s.spec_id)

    # Run all specs concurrently — each spec's stages remain sequential within
    spec_coroutines = [
        _run_one_spec_async(spec, iter_idx, iter_dir, symbols, dates,
                             prior_feedback, log, max_fidelity_retries, skip_llm_agents)
        for spec in specs
    ]
    spec_results = await _asyncio.gather(*spec_coroutines, return_exceptions=False)
    triples = [r for r in spec_results if r is not None]

    # ⑤ Improve (sync — single LLM call after all specs finish)
    improvements: list[ImprovementProposal] = []
    if triples:
        try:
            improvements = stage_improve(triples, iter_idx, budget=n_candidates, skip_llm=skip_llm_agents)
            for p in improvements:
                ipath = iter_dir / "improvements" / f"{p.parent_spec_id}.json"
                i = 0
                while ipath.exists():
                    i += 1
                    ipath = iter_dir / "improvements" / f"{p.parent_spec_id}_v{i}.json"
                ipath.write_text(p.model_dump_json(indent=2))
                log.improvement_proposals.append(str(ipath.relative_to(REPO_ROOT)))
            print(f"  ⑤ improver: {len(improvements)} proposal(s) for iter {iter_idx+1}")
        except Exception as e:  # noqa: BLE001
            print(f"  ⑤ improver raised: {e}\n{traceback.format_exc()}")

    log.finished_at = dt.datetime.utcnow()
    log.stop_reason = None
    write_iteration_log(iter_idx, log)
    append_to_prior_index(iter_idx, triples)

    # Stage 6 + report — same as sync version
    try:
        from chain1.agents.chain2_gate import run_gate, FEE_SCENARIOS
        default_scenario = os.getenv("CHAIN2_GATE_FEE_SCENARIO", "krx_cash_23bps")
        scenarios = [default_scenario] + [s for s in FEE_SCENARIOS if s != default_scenario]
        n_syms = len({ps["symbol"] for t in triples for ps in t["result"].get("per_symbol", [])}) or len(symbols)
        n_dates = len({ps["date"] for t in triples for ps in t["result"].get("per_symbol", [])}) or len(dates)
        gate_output = run_gate(
            triples=triples, iterations_scanned=[iter_idx],
            fee_scenarios=scenarios,
            n_symbols=max(n_syms, 1), n_dates=max(n_dates, 1),
            top_k=3, use_llm_narrative=False,
        )
        (iter_dir / "chain2_gate.json").write_text(gate_output.model_dump_json(indent=2))
        total_top = sum(len(s.top_candidates) for s in gate_output.scenarios)
        print(f"  🚀 chain2-gate: {total_top} top candidate(s) across {len(gate_output.scenarios)} scenario(s)")
    except Exception as e:  # noqa: BLE001
        print(f"  (chain2-gate skipped: {e})")

    try:
        from chain1.reporting import generate_iteration_report
        report_path = generate_iteration_report(iter_idx)
        print(f"  📄 report → {report_path.relative_to(REPO_ROOT)}")
    except Exception as e:  # noqa: BLE001
        print(f"  (report generation skipped: {e})")

    return triples, improvements


def run_iteration(
    iter_idx: int,
    n_candidates: int,
    symbols: list[str],
    dates: list[str],
    prior_feedback: list[Feedback] | None,
    prior_improvement: ImprovementProposal | None,
    max_fidelity_retries: int = 3,
    skip_llm_agents: bool = False,
    seed_specs: list[SignalSpec] | None = None,
) -> tuple[list[dict], ImprovementProposal | list[ImprovementProposal] | None]:
    """Run one full iteration. Returns (triples_dicts, improvement_proposals)."""
    iter_dir = ensure_iteration_dir(iter_idx)
    t_start = dt.datetime.utcnow()
    log = IterationLog(iteration_idx=iter_idx, started_at=t_start)

    print(f"\n═══ Iteration {iter_idx:03d} ═══")

    # ① Generate
    if seed_specs is not None:
        specs = seed_specs
        print(f"[iter {iter_idx}] ① using {len(specs)} seed specs (offline mode)")
    else:
        try:
            specs = stage_generate(iter_idx, n_candidates, symbols, dates,
                                    prior_feedback, prior_improvement, skip_llm=skip_llm_agents)
            print(f"[iter {iter_idx}] ① generated {len(specs)} candidates")
        except RuntimeError as e:
            print(f"[iter {iter_idx}] ① generation failed: {e}")
            log.finished_at = dt.datetime.utcnow()
            log.stop_reason = f"generation_failed: {e}"
            write_iteration_log(iter_idx, log)
            return [], None

    # Persist generated specs
    for s in specs:
        (iter_dir / "specs" / f"{s.spec_id}.json").write_text(s.model_dump_json(indent=2))
        log.signal_specs.append(s.spec_id)

    triples: list[dict] = []

    for spec in specs:
        print(f"\n  — spec {spec.spec_id} —")
        print(f"    formula={spec.formula} threshold={spec.threshold} horizon={spec.prediction_horizon_ticks}t")

        # ② Evaluate
        try:
            evaluation = stage_evaluate(spec, iter_idx, skip_llm=skip_llm_agents)
            (iter_dir / "evaluations" / f"{spec.spec_id}.json").write_text(evaluation.model_dump_json(indent=2))
            log.spec_evaluations.append(str((iter_dir / "evaluations" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
            if not evaluation.valid:
                print(f"    ② evaluation REJECT: {evaluation.concerns[:3]}")
                continue
            print(f"    ② evaluation OK (merit={evaluation.expected_merit})")
        except Exception as e:  # noqa: BLE001
            print(f"    ② evaluation raised: {e}")
            continue

        # ②.5 Code-gen (with fidelity retry loop)
        code = None
        report = None
        for attempt in range(max_fidelity_retries):
            try:
                code = stage_codegen(spec, iter_idx)
                if attempt == 0:
                    (iter_dir / "code" / f"{spec.spec_id}.codegen.json").write_text(code.model_dump_json(indent=2))
                    log.generated_codes.append(code.code_path)
                print(f"    ②.5 codegen OK → {code.code_path}")
            except Exception as e:  # noqa: BLE001
                print(f"    ②.5 codegen raised: {e}")
                break

            # ②.75 Fidelity
            try:
                report = stage_fidelity(spec, code)
                (iter_dir / "fidelity" / f"{spec.spec_id}.json").write_text(report.model_dump_json(indent=2))
                log.fidelity_reports.append(str((iter_dir / "fidelity" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
                if report.overall_passed:
                    print(f"    ②.75 fidelity PASS")
                    break
                fails = [c.name for c in report.checks if not c.passed]
                print(f"    ②.75 fidelity FAIL ({attempt+1}/{max_fidelity_retries}): {fails}")
            except Exception as e:  # noqa: BLE001
                print(f"    ②.75 fidelity raised: {e}")
                break

        if code is None or report is None or not report.overall_passed:
            print(f"    [spec {spec.spec_id}] fidelity gate not satisfied — skipping downstream")
            continue

        # ③ Backtest
        try:
            result = stage_backtest(spec, code, symbols, dates)
            (iter_dir / "results" / f"{spec.spec_id}.json").write_text(result.model_dump_json(indent=2))
            log.backtest_results.append(str((iter_dir / "results" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
            print(f"    ③ backtest: n_trades={result.aggregate_n_trades} "
                  f"WR={result.aggregate_wr:.4f} exp={result.aggregate_expectancy_bps:+.3f}bps")
        except Exception as e:  # noqa: BLE001
            print(f"    ③ backtest raised: {e}")
            continue

        # ④ Feedback
        try:
            feedback = stage_feedback(spec, result, iter_idx,
                                      recent_feedback=prior_feedback,
                                      skip_llm=skip_llm_agents)
            (iter_dir / "feedback" / f"{spec.spec_id}.json").write_text(feedback.model_dump_json(indent=2))
            log.feedback.append(str((iter_dir / "feedback" / f"{spec.spec_id}.json").relative_to(REPO_ROOT)))
            print(f"    ④ feedback: recommendation={feedback.recommended_next_direction}")
        except Exception as e:  # noqa: BLE001
            print(f"    ④ feedback raised: {e}")
            continue

        triples.append({
            "spec": spec.model_dump(),
            "result": result.model_dump(),
            "feedback": feedback.model_dump(),
        })

    # ⑤ Improve (iteration-level, outputs seed for iter+1)
    improvements: list[ImprovementProposal] = []
    if triples:
        try:
            improvements = stage_improve(triples, iter_idx, budget=n_candidates, skip_llm=skip_llm_agents)
            for p in improvements:
                ipath = iter_dir / "improvements" / f"{p.parent_spec_id}.json"
                # Avoid overwriting when multiple variants share a parent
                i = 0
                while ipath.exists():
                    i += 1
                    ipath = iter_dir / "improvements" / f"{p.parent_spec_id}_v{i}.json"
                ipath.write_text(p.model_dump_json(indent=2))
                log.improvement_proposals.append(str(ipath.relative_to(REPO_ROOT)))
            print(f"  ⑤ improver: {len(improvements)} proposal(s) for iter {iter_idx+1}")
        except Exception as e:  # noqa: BLE001
            print(f"  ⑤ improver raised: {e}\n{traceback.format_exc()}")

    log.finished_at = dt.datetime.utcnow()
    log.stop_reason = None
    write_iteration_log(iter_idx, log)
    append_to_prior_index(iter_idx, triples)

    # Stage 6 — chain2-gate: auto-score candidates for Chain 2 promotion.
    try:
        from chain1.agents.chain2_gate import run_gate, FEE_SCENARIOS
        default_scenario = os.getenv("CHAIN2_GATE_FEE_SCENARIO", "krx_cash_23bps")
        scenarios = [default_scenario] + [s for s in FEE_SCENARIOS if s != default_scenario]
        # Determine symbol / date counts from the first result
        n_syms = len({ps["symbol"] for t in triples for ps in t["result"].get("per_symbol", [])}) or len(symbols)
        n_dates = len({ps["date"] for t in triples for ps in t["result"].get("per_symbol", [])}) or len(dates)
        gate_output = run_gate(
            triples=triples, iterations_scanned=[iter_idx],
            fee_scenarios=scenarios,
            n_symbols=max(n_syms, 1), n_dates=max(n_dates, 1),
            top_k=3, use_llm_narrative=False,
        )
        (iter_dir / "chain2_gate.json").write_text(gate_output.model_dump_json(indent=2))
        total_top = sum(len(s.top_candidates) for s in gate_output.scenarios)
        print(f"  🚀 chain2-gate: {total_top} top candidate(s) across {len(gate_output.scenarios)} scenario(s)")
    except Exception as e:  # noqa: BLE001
        print(f"  (chain2-gate skipped: {e})")

    # Auto-generate HTML report (best-effort; don't fail the iteration if it crashes)
    try:
        from chain1.reporting import generate_iteration_report
        report_path = generate_iteration_report(iter_idx)
        print(f"  📄 report → {report_path.relative_to(REPO_ROOT)}")
    except Exception as e:  # noqa: BLE001
        print(f"  (report generation skipped: {e})")

    return triples, improvements


def run_loop(
    max_iterations: int,
    n_candidates: int,
    symbols: list[str],
    dates: list[str],
    convergence_window: int = 3,
    convergence_epsilon: float = 0.005,
    max_fidelity_retries: int = 3,
    skip_llm_agents: bool = False,
    seed_specs_path: str | None = None,
    start_iter: int = 0,
) -> None:
    """Top-level Chain 1 loop. Iterates from `start_iter` up to (but not
    including) `max_iterations`. Seed-specs only apply when start_iter == 0.
    Resuming a crashed run: pass start_iter = last_completed + 1 so previous
    artifacts are preserved (the orchestrator does not rewrite earlier iter_XXX
    directories).
    """
    # Offline mode: load seed specs from disk for iteration 0
    seed_specs: list[SignalSpec] | None = None
    if seed_specs_path:
        seeds = json.loads(Path(seed_specs_path).read_text())
        if not isinstance(seeds, list):
            seeds = [seeds]
        seed_specs = [SignalSpec(**s) for s in seeds]

    print(f"[loop] start  start_iter={start_iter} max_iter={max_iterations} "
          f"n_candidates={n_candidates}  symbols={symbols} dates={dates}  "
          f"skip_llm={skip_llm_agents}")

    prior_feedback: list[Feedback] = []
    prior_improvement: ImprovementProposal | None = None
    best_metric_trajectory: list[float] = []
    stagnated = 0
    track_label = "net_exp" if _FEE_BPS_RT > 0 else "wr"

    for i in range(start_iter, max_iterations):
        # Only iter 0 uses the seed specs (if provided)
        iter_seeds = seed_specs if (i == 0 and seed_specs is not None) else None

        if _PARALLEL:
            import asyncio as _asyncio
            triples, improvements = _asyncio.run(run_iteration_parallel(
                iter_idx=i,
                n_candidates=n_candidates,
                symbols=symbols,
                dates=dates,
                prior_feedback=prior_feedback,
                prior_improvement=prior_improvement,
                max_fidelity_retries=max_fidelity_retries,
                skip_llm_agents=skip_llm_agents,
                seed_specs=iter_seeds,
            ))
        else:
            triples, improvements = run_iteration(
                iter_idx=i,
                n_candidates=n_candidates,
                symbols=symbols,
                dates=dates,
                prior_feedback=prior_feedback,
                prior_improvement=prior_improvement,
                max_fidelity_retries=max_fidelity_retries,
                skip_llm_agents=skip_llm_agents,
                seed_specs=iter_seeds,
            )

        if not triples:
            print(f"[loop] iter {i}: no surviving triples — stopping")
            break

        # Track best primary metric for convergence detection. Under net-PnL
        # objective (Fix #1) we monitor net_expectancy instead of WR; otherwise
        # legacy WR tracking remains.
        if _FEE_BPS_RT > 0:
            best_metric = max(
                (t["result"]["aggregate_expectancy_bps"] or 0.0) - _FEE_BPS_RT
                for t in triples
            )
        else:
            best_metric = max(t["result"]["aggregate_wr"] for t in triples)
        best_metric_trajectory.append(best_metric)
        if len(best_metric_trajectory) >= 2:
            delta = best_metric_trajectory[-1] - best_metric_trajectory[-2]
            if delta <= convergence_epsilon:
                stagnated += 1
            else:
                stagnated = 0
        print(f"[loop] iter {i}: best_{track_label}={best_metric:.4f}  stagnation_streak={stagnated}")
        if stagnated >= convergence_window:
            print(f"[loop] convergence: {convergence_window} consecutive iterations without {track_label} improvement > {convergence_epsilon}")
            break

        # Seed next iteration
        prior_feedback = [Feedback(**t["feedback"]) for t in triples]
        # Pick the "primary" improvement — pass the full list so generator can reason across
        prior_improvement = improvements[0] if improvements else None

    print(f"\n[loop] DONE — {track_label} trajectory: {['%.4f' % w for w in best_metric_trajectory]}")


# ---------------------------------------------------------------------------
# Dry-run (Phase A backward compat)
# ---------------------------------------------------------------------------


def dry_run(n_iterations: int, symbols: list[str], dates: list[str]) -> None:
    validation = validate_agents()
    print(f"[dry-run] all {len(validation)} agents validated:")
    for name, info in validation.items():
        print(f"  - {name:<20} stage={info['stage']:<18} {info['input_model']} → {info['output_model']}")
    for i in range(n_iterations):
        log = IterationLog(
            iteration_idx=i, started_at=dt.datetime.utcnow(),
            finished_at=dt.datetime.utcnow(), stop_reason="dry_run_stub",
        )
        write_iteration_log(i, log)
        print(f"[dry-run] iter {i}: created {(ITERATIONS_ROOT / f'iter_{i:03d}').relative_to(REPO_ROOT)}")
    print(f"[dry-run] universe: symbols={symbols} dates={dates}")


def run_deterministic_pipeline(spec_json_path: str, iteration_idx: int,
                                symbols: list[str], dates: list[str]) -> None:
    """Phase C-era smoke: ②.5 → ②.75 → ③ on a manually-supplied spec."""
    spec_dict = json.loads(Path(spec_json_path).read_text())
    spec_dict["iteration_idx"] = iteration_idx
    spec = SignalSpec(**spec_dict)

    iter_dir = ensure_iteration_dir(iteration_idx)
    (iter_dir / "specs" / f"{spec.spec_id}.json").write_text(spec.model_dump_json(indent=2))

    print(f"[det-pipeline] ②.5 code-generator for {spec.spec_id}")
    code = stage_codegen(spec, iteration_idx)
    (iter_dir / "code" / f"{spec.spec_id}.codegen.json").write_text(code.model_dump_json(indent=2))

    print(f"[det-pipeline] ②.75 fidelity-checker")
    report = stage_fidelity(spec, code)
    (iter_dir / "fidelity" / f"{spec.spec_id}.json").write_text(report.model_dump_json(indent=2))
    if not report.overall_passed:
        failures = [c.name for c in report.checks if not c.passed]
        print(f"[det-pipeline] ✗ fidelity FAILED: {failures}")
        return
    print(f"[det-pipeline] ✓ fidelity PASS")

    print(f"[det-pipeline] ③ backtest on {symbols} × {dates}")
    result = stage_backtest(spec, code, symbols, dates)
    (iter_dir / "results" / f"{spec.spec_id}.json").write_text(result.model_dump_json(indent=2))
    print(f"[det-pipeline] ✓ backtest: n_trades={result.aggregate_n_trades} "
          f"WR={result.aggregate_wr:.4f} exp={result.aggregate_expectancy_bps:+.3f}bps")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    uni = cfg["universe"]
    it = cfg["iteration"]

    p = argparse.ArgumentParser(prog="chain1.orchestrator")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate-agents", help="Verify 6-component completeness + schema import")

    dr = sub.add_parser("dry-run", help="Validate + create iteration dirs (Phase A smoke)")
    dr.add_argument("--iterations", type=int, default=1)
    dr.add_argument("--symbols", nargs="+", default=uni["symbols"])
    dr.add_argument("--dates", nargs="+", default=uni["dates"])

    dp = sub.add_parser("det-pipeline", help="Phase C deterministic path on one spec")
    dp.add_argument("--spec-json", required=True)
    dp.add_argument("--iteration-idx", type=int, default=0)
    dp.add_argument("--symbols", nargs="+", default=uni["symbols"])
    dp.add_argument("--dates", nargs="+", default=uni["dates"])

    ru = sub.add_parser("run", help="Phase F end-to-end Chain 1 loop")
    ru.add_argument("--max-iter", type=int, default=it["max_iterations"])
    ru.add_argument("--n-candidates", type=int, default=it["n_candidates_per_iter"])
    ru.add_argument("--symbols", nargs="+", default=uni["symbols"])
    ru.add_argument("--dates", nargs="+", default=uni["dates"])
    ru.add_argument("--convergence-window", type=int, default=it["convergence_window"])
    ru.add_argument("--convergence-epsilon", type=float, default=it["convergence_epsilon"])
    ru.add_argument("--max-fidelity-retries", type=int, default=cfg["fidelity"]["max_retries_on_fail"])
    ru.add_argument("--skip-llm-agents", action="store_true",
                    help="Use deterministic evaluator/feedback/improver. Generator is LLM-only — "
                         "pass --seed-specs in this mode.")
    ru.add_argument("--seed-specs", default=None,
                    help="Path to JSON (list of SignalSpec) for iteration 0 (offline mode).")
    ru.add_argument("--start-iter", type=int, default=0,
                    help="Resume loop from this iteration index (earlier iter_XXX dirs preserved).")
    ru.add_argument("--calibration-table", default=None,
                    help="Path to calibration JSON (chain1/calibration.py output). "
                         "If supplied, single-primitive specs are z-score normalized per symbol.")
    ru.add_argument("--fee-bps-rt", type=float, default=0.0,
                    help="Round-trip fee in bps. When > 0, the loop optimises net_expectancy = "
                         "expectancy_bps - fee_bps_rt instead of WR (Fix #1, 2026-04-27). "
                         "Recommended: 23.0 for KRX cash; 4.0 for crypto-maker scenario.")
    ru.add_argument("--execution-mode", default="mid_to_mid",
                    choices=["mid_to_mid", "maker_optimistic"],
                    help="Backtest execution model (Path B, 2026-04-27). "
                         "'mid_to_mid' = entry/exit at mid (legacy). "
                         "'maker_optimistic' = entry at touch BID/ASK, captures spread.")
    ru.add_argument("--parallel", action="store_true",
                    help="G (2026-04-28): run all specs of an iteration in parallel "
                         "(LLM async + backtest in thread). Each spec's stages remain "
                         "sequential within that spec. Improver remains synchronous after "
                         "all specs finish.")

    args = p.parse_args(argv)

    if args.cmd == "validate-agents":
        results = validate_agents()
        print(json.dumps(results, indent=2))
        return 0
    if args.cmd == "dry-run":
        dry_run(args.iterations, args.symbols, args.dates)
        return 0
    if args.cmd == "det-pipeline":
        run_deterministic_pipeline(args.spec_json, args.iteration_idx, args.symbols, args.dates)
        return 0
    if args.cmd == "run":
        # Optional: load calibration table for per-symbol z-score normalization (D1)
        global _CALIBRATION_TABLE, _FEE_BPS_RT, _EXECUTION_MODE, _PARALLEL
        if args.calibration_table:
            from chain1.calibration import load_table
            _CALIBRATION_TABLE = load_table(args.calibration_table)
            n_syms = len(_CALIBRATION_TABLE.get("stats", {}))
            print(f"[loop] calibration table loaded: {n_syms} symbols", flush=True)
        _FEE_BPS_RT = float(args.fee_bps_rt)
        _EXECUTION_MODE = args.execution_mode
        _PARALLEL = bool(args.parallel)
        if _PARALLEL:
            print(f"[loop] parallel mode = ON (specs run concurrently per iter)", flush=True)
        if _FEE_BPS_RT > 0:
            print(f"[loop] objective = net_expectancy (fee_bps_rt={_FEE_BPS_RT:.1f} bps RT)", flush=True)
        else:
            print(f"[loop] objective = WR (legacy mode; pass --fee-bps-rt > 0 to switch)", flush=True)
        print(f"[loop] execution_mode = {_EXECUTION_MODE}", flush=True)
        run_loop(
            max_iterations=args.max_iter,
            n_candidates=args.n_candidates,
            symbols=args.symbols,
            dates=args.dates,
            convergence_window=args.convergence_window,
            convergence_epsilon=args.convergence_epsilon,
            max_fidelity_retries=args.max_fidelity_retries,
            skip_llm_agents=args.skip_llm_agents,
            seed_specs_path=args.seed_specs,
            start_iter=args.start_iter,
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
