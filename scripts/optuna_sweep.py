"""Optuna parameter sweep for tick strategy specs.

Usage:
  python scripts/optuna_sweep.py --spec strategies/<id>/spec.yaml [options]

Search space definition (in spec.yaml under `optuna:` key):

  optuna:
    n_trials: 100
    metric: return_pct        # return_pct | sharpe_annualized | composite
    min_trades: 5             # trials with fewer roundtrips get penalized score
    search_space:
      profit_target_bps:
        type: float           # float | int | categorical
        low: 60.0
        high: 400.0
        step: 5.0             # optional, for float/int
      stop_loss_bps:
        type: float
        low: 20.0
        high: 150.0
        step: 5.0
      obi_threshold:
        type: float
        low: 0.2
        high: 0.7
        step: 0.05
      lot_size:
        type: int
        low: 1
        high: 10
      session_drop_gate_bps:
        type: float
        low: 30.0
        high: 200.0
        step: 10.0

Metrics:
  return_pct         — 총 수익률 (기본)
  sharpe_annualized  — 연환산 샤프 지수
  composite          — return_pct * win_rate_pct / 100  (수익 × 승률)

Example:
  python scripts/optuna_sweep.py \\
    --spec strategies/strat_20260415_0025.../spec.yaml \\
    --n-trials 100 \\
    --metric composite \\
    --min-trades 5 \\
    --out-spec strategies/strat_20260415_0025.../spec_best.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import textwrap
from copy import deepcopy
from pathlib import Path

import optuna
import yaml

# ── project root on sys.path ───────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from engine.runner import run as _run  # noqa: E402


# ── silence optuna progress noise ─────────────────────────────────────────
optuna.logging.set_verbosity(optuna.logging.WARNING)


def _suggest(trial: optuna.Trial, name: str, cfg: dict):
    """Suggest a value for one parameter from its search_space config."""
    kind = cfg.get("type", "float")
    if kind == "float":
        low  = float(cfg["low"])
        high = float(cfg["high"])
        step = cfg.get("step")
        if step is not None:
            return trial.suggest_float(name, low, high, step=float(step))
        return trial.suggest_float(name, low, high)
    if kind == "int":
        low  = int(cfg["low"])
        high = int(cfg["high"])
        step = int(cfg.get("step", 1))
        return trial.suggest_int(name, low, high, step=step)
    if kind == "categorical":
        return trial.suggest_categorical(name, cfg["choices"])
    raise ValueError(f"Unknown search_space type '{kind}' for param '{name}'")


def _score(payload: dict, metric: str, min_trades: int) -> float:
    """Compute optimization objective from a backtest payload."""
    n_rt = payload.get("n_roundtrips", 0)

    # 거래 없거나 min_trades 미달 → 강한 페널티
    if n_rt == 0:
        return -999.0
    if n_rt < min_trades:
        penalty = (min_trades - n_rt) / min_trades  # 0~1
        base = _score_raw(payload, metric)
        return base - penalty * 50.0

    return _score_raw(payload, metric)


def _score_raw(payload: dict, metric: str) -> float:
    if metric == "return_pct":
        return float(payload.get("return_pct", -999.0))
    if metric == "sharpe_annualized":
        return float(payload.get("sharpe_annualized", -999.0))
    if metric == "composite":
        ret = float(payload.get("return_pct", 0.0))
        wr  = float(payload.get("win_rate_pct", 0.0))
        return ret * wr / 100.0
    raise ValueError(f"Unknown metric: {metric}")


def build_objective(base_spec: dict, spec_path: Path, metric: str, min_trades: int, search_space: dict):
    """Return an Optuna objective closure over the given base spec."""

    def objective(trial: optuna.Trial) -> float:
        # 1. 이번 trial의 params 샘플링
        trial_params = {
            name: _suggest(trial, name, cfg)
            for name, cfg in search_space.items()
        }

        # 2. base spec을 복사해서 params 덮어쓰기
        spec_copy = deepcopy(base_spec)
        if "params" not in spec_copy:
            spec_copy["params"] = {}
        spec_copy["params"].update(trial_params)

        # 3. 임시 디렉토리에 spec.yaml 저장 후 backtest 실행
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_spec = Path(tmpdir) / "spec.yaml"
            # strategy.py가 필요한 python 전략이면 원본 디렉토리 링크
            strategy_py = spec_path.parent / "strategy.py"
            if strategy_py.exists():
                import shutil
                shutil.copy(strategy_py, Path(tmpdir) / "strategy.py")
            tmp_spec.write_text(yaml.dump(spec_copy, allow_unicode=True, sort_keys=False))
            try:
                payload = _run(
                    tmp_spec,
                    write_trace=False,
                    write_html=False,
                    report_out=Path(tmpdir) / "report.json",
                )
            except Exception as e:
                trial.set_user_attr("error", str(e))
                return -999.0

        score = _score(payload, metric, min_trades)
        trial.set_user_attr("return_pct",  round(payload.get("return_pct", 0.0), 4))
        trial.set_user_attr("n_roundtrips", payload.get("n_roundtrips", 0))
        trial.set_user_attr("win_rate_pct", round(payload.get("win_rate_pct", 0.0), 2))
        trial.set_user_attr("sharpe",       round(payload.get("sharpe_annualized", 0.0), 4))
        return score

    return objective


def print_results(study: optuna.Study, metric: str, top_n: int = 10) -> None:
    """Print top trials in a readable table."""
    completed = [
        t for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE
    ]
    if not completed:
        print("No completed trials.")
        return

    completed.sort(key=lambda t: t.value, reverse=True)

    print(f"\n{'─'*80}")
    print(f"  Optuna sweep — metric: {metric}  |  total trials: {len(study.trials)}"
          f"  |  completed: {len(completed)}")
    print(f"{'─'*80}")
    print(f"  {'#':>4}  {'score':>9}  {'return%':>8}  {'WR%':>6}  "
          f"{'trades':>6}  {'sharpe':>7}  params")
    print(f"  {'─'*4}  {'─'*9}  {'─'*8}  {'─'*6}  {'─'*6}  {'─'*7}  {'─'*30}")

    for rank, t in enumerate(completed[:top_n], 1):
        ua   = t.user_attrs
        mark = " ★" if rank == 1 else ""
        def _pv(v):
            if isinstance(v, float):
                return f"{v:g}"
            return str(v)
        param_str = "  ".join(f"{k}={_pv(v)}" for k, v in t.params.items())
        print(
            f"  {rank:>4}  {t.value:>+9.4f}  "
            f"{ua.get('return_pct', 0):>+8.4f}  "
            f"{ua.get('win_rate_pct', 0):>6.1f}%  "
            f"{ua.get('n_roundtrips', 0):>6}  "
            f"{ua.get('sharpe', 0):>+7.4f}  "
            f"{param_str}{mark}"
        )

    print(f"{'─'*80}\n")
    best = study.best_trial
    print("  Best params:")
    for k, v in best.params.items():
        print(f"    {k}: {v}")
    print()


def write_best_spec(base_spec: dict, best_params: dict, out_path: Path) -> None:
    """Write a new spec.yaml with best params applied (optuna block removed)."""
    spec = deepcopy(base_spec)
    spec.pop("optuna", None)   # sweep 설정은 제거
    if "params" not in spec:
        spec["params"] = {}
    spec["params"].update(best_params)
    spec["name"] = spec.get("name", "strategy") + "_optuna_best"
    out_path.write_text(yaml.dump(spec, allow_unicode=True, sort_keys=False))
    print(f"  Best spec saved → {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Optuna parameter sweep for a tick strategy spec",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Search space is read from spec.yaml under the `optuna.search_space` key.
            CLI flags override spec defaults where applicable.
        """),
    )
    ap.add_argument("--spec",       required=True,  help="Path to spec.yaml")
    ap.add_argument("--n-trials",   type=int,       default=None,
                    help="Number of trials (overrides spec optuna.n_trials)")
    ap.add_argument("--metric",     default=None,
                    choices=["return_pct", "sharpe_annualized", "composite"],
                    help="Optimization metric (overrides spec optuna.metric)")
    ap.add_argument("--min-trades", type=int,       default=None,
                    help="Min roundtrips; fewer → penalized score (overrides spec)")
    ap.add_argument("--out-spec",   default=None,
                    help="Write best-params spec.yaml to this path")
    ap.add_argument("--sampler",    default="tpe",  choices=["tpe", "random"],
                    help="Optuna sampler (default: tpe)")
    ap.add_argument("--top",        type=int,       default=10,
                    help="Number of top trials to display (default: 10)")
    ap.add_argument("--seed",       type=int,       default=42,
                    help="Random seed for sampler (default: 42)")
    ap.add_argument("--json",       action="store_true",
                    help="Print best trial as JSON (for agent consumption)")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    base_spec = yaml.safe_load(spec_path.read_text()) or {}
    optuna_cfg = base_spec.get("optuna") or {}
    search_space = optuna_cfg.get("search_space") or {}

    if not search_space:
        print(
            "ERROR: no search_space defined.\n"
            "Add an `optuna.search_space` block to your spec.yaml.\n"
            "See script docstring for format.",
            file=sys.stderr,
        )
        sys.exit(1)

    # CLI overrides spec defaults
    n_trials   = args.n_trials   or int(optuna_cfg.get("n_trials",   50))
    metric     = args.metric     or str(optuna_cfg.get("metric",     "return_pct"))
    min_trades = args.min_trades if args.min_trades is not None else int(optuna_cfg.get("min_trades", 3))

    print(f"\n  spec      : {spec_path}")
    print(f"  trials    : {n_trials}")
    print(f"  metric    : {metric}")
    print(f"  min_trades: {min_trades}")
    print(f"  sampler   : {args.sampler}")
    print(f"  search    : {list(search_space.keys())}\n")

    # ── sampler ────────────────────────────────────────────────────────────
    if args.sampler == "random":
        sampler = optuna.samplers.RandomSampler(seed=args.seed)
    else:
        sampler = optuna.samplers.TPESampler(seed=args.seed)

    study = optuna.create_study(direction="maximize", sampler=sampler)
    objective = build_objective(base_spec, spec_path, metric, min_trades, search_space)

    # ── progress bar via tqdm if available ─────────────────────────────────
    try:
        from tqdm import tqdm
        with tqdm(total=n_trials, desc="sweeping", unit="trial") as pbar:
            def _cb(study, trial):
                pbar.update(1)
                best_v = study.best_value if study.best_trial else float("-inf")
                pbar.set_postfix(best=f"{best_v:+.4f}", trades=trial.user_attrs.get("n_roundtrips", "?"))
            study.optimize(objective, n_trials=n_trials, callbacks=[_cb], show_progress_bar=False)
    except ImportError:
        study.optimize(objective, n_trials=n_trials)

    # ── results ────────────────────────────────────────────────────────────
    if args.json:
        best = study.best_trial
        print(json.dumps({
            "best_score":   best.value,
            "best_params":  best.params,
            "return_pct":   best.user_attrs.get("return_pct"),
            "n_roundtrips": best.user_attrs.get("n_roundtrips"),
            "win_rate_pct": best.user_attrs.get("win_rate_pct"),
            "sharpe":       best.user_attrs.get("sharpe"),
            "metric":       metric,
            "n_trials":     n_trials,
        }, ensure_ascii=False, indent=2))
    else:
        print_results(study, metric, top_n=args.top)

    if args.out_spec:
        write_best_spec(base_spec, study.best_trial.params, Path(args.out_spec))


if __name__ == "__main__":
    main()
