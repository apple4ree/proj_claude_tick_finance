"""Re-measure v3 archive 80 specs through chain1.backtest_runner regime_state mode.

Differs from analysis/regime_state_ablation.py (standalone) in:
  - Uses official chain1.run_backtest() pipeline (production code path)
  - No end-of-session force-close (consistent with paradigm)
  - Records full regime metrics (duty cycle, mean duration)
  - Compatible with feedback_analyst sanity checks
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"))

from schemas import SignalSpec, GeneratedCode  # noqa: E402
from chain1.backtest_runner import run_backtest  # noqa: E402

KRX_RT_FEE_BPS = 23.0
DEPLOYABLE_THRESHOLD_BPS = 28.0  # 23 fee + 5 spread cost


def load_spec_and_code(spec_path: Path):
    spec = SignalSpec(**json.loads(spec_path.read_text()))
    # codegen.json sits next to .py in archive
    iter_dir = spec_path.parent.parent
    code_dir = iter_dir / "code"
    py_path = code_dir / f"{spec.spec_id}.py"
    codegen_json = code_dir / f"{spec.spec_id}.codegen.json"
    if not py_path.exists() or not codegen_json.exists():
        return None, None
    code_dict = json.loads(codegen_json.read_text())
    code_dict["code_path"] = str(py_path)  # archive 경로 사용
    code = GeneratedCode(**code_dict)
    return spec, code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-root", default="iterations_v3_archive")
    ap.add_argument("--symbols", nargs="+", default=["005930", "000660", "005380"])
    ap.add_argument("--dates", nargs="+",
                    default=["20260319", "20260323"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    archive_root = Path(args.archive_root)
    spec_files = sorted(archive_root.glob("iter_*/specs/*.json"))
    if args.limit:
        spec_files = spec_files[:args.limit]

    print(f"Found {len(spec_files)} spec files in {archive_root}")
    print(f"Universe: {args.symbols} × {args.dates}")
    print(f"KRX fee floor: {KRX_RT_FEE_BPS} bps RT, deployable threshold: {DEPLOYABLE_THRESHOLD_BPS} bps")
    print()

    rows = []
    t_start = time.time()
    for idx, spec_path in enumerate(spec_files):
        try:
            spec, code = load_spec_and_code(spec_path)
        except Exception as e:
            print(f"[{idx+1}/{len(spec_files)}] {spec_path.stem} LOAD FAIL: {e}")
            continue
        if spec is None:
            print(f"[{idx+1}/{len(spec_files)}] {spec_path.stem} skip (no code)")
            continue

        t0 = time.time()
        try:
            result = run_backtest(
                spec, code,
                symbols=args.symbols,
                dates=args.dates,
                save_trace=False,
                mode="regime_state",
            )
        except Exception as e:
            print(f"[{idx+1}/{len(spec_files)}] {spec.spec_id} BACKTEST FAIL: {e}")
            continue
        dt = time.time() - t0

        net_exp = (result.aggregate_expectancy_bps - KRX_RT_FEE_BPS)
        deployable = result.aggregate_expectancy_bps > DEPLOYABLE_THRESHOLD_BPS

        rows.append({
            "spec_id": spec.spec_id,
            "iteration_idx": spec.iteration_idx,
            "direction": spec.direction.value if hasattr(spec.direction, "value") else str(spec.direction),
            "threshold": spec.threshold,
            "n_regimes": result.aggregate_n_regimes,
            "signal_duty_cycle": result.aggregate_signal_duty_cycle,
            "mean_duration_ticks": result.aggregate_mean_duration_ticks,
            "wr": result.aggregate_wr,
            "expectancy_bps": result.aggregate_expectancy_bps,
            "net_exp_bps_at_23fee": net_exp,
            "deployable_at_28": deployable,
            "n_sessions": len(result.per_symbol),
            "elapsed_sec": dt,
        })

        n_reg = result.aggregate_n_regimes or 0
        duty = result.aggregate_signal_duty_cycle or 0.0
        flag = "🚀" if deployable else ("⚠️" if duty > 0.95 else "")
        print(f"[{idx+1}/{len(spec_files)}] {spec.spec_id[:50]:<50} "
              f"n={n_reg:>5} duty={duty:.3f} mean_dur={result.aggregate_mean_duration_ticks or 0:.0f} "
              f"WR={result.aggregate_wr:.3f} exp={result.aggregate_expectancy_bps:+.2f}bps "
              f"net@23={net_exp:+.2f}bps {flag} ({dt:.1f}s)", flush=True)

    df = pd.DataFrame(rows)
    if args.output is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        args.output = f"analysis/v3_regime_remeasure_{ts}.csv"
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    elapsed = time.time() - t_start
    print(f"\n=== DONE in {elapsed/60:.1f} min ===")
    print(f"Output: {args.output}")
    print(f"Specs: {len(rows)}/{len(spec_files)}")
    if len(df) > 0:
        print(f"\nSummary:")
        print(f"  mean expectancy: {df['expectancy_bps'].mean():+.3f} bps")
        print(f"  max  expectancy: {df['expectancy_bps'].max():+.3f} bps")
        print(f"  expectancy > 0:        {(df['expectancy_bps']>0).sum()}/{len(df)}")
        print(f"  expectancy > 23 (fee): {(df['expectancy_bps']>23).sum()}/{len(df)}")
        print(f"  expectancy > 28 (deployable): {(df['expectancy_bps']>28).sum()}/{len(df)}")
        print(f"  duty > 0.95 (artifact):       {(df['signal_duty_cycle']>0.95).sum()}/{len(df)}")
        print(f"  n_regimes < 1.5×sessions (rare): "
              f"{(df['n_regimes'] < df['n_sessions']*1.5).sum()}/{len(df)}")


if __name__ == "__main__":
    raise SystemExit(main())
