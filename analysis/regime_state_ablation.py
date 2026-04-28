"""Regime-state ablation: re-measure v3 archived specs under state-machine model.

Paradigm change tested:
    Tick-trigger model (current chain 1):
        every tick where |signal| > threshold → independent trade closing at mid[i+H]
        N_trades = O(thousands), each pays full fee → KRX 23bps × N is prohibitive

    Regime-state model (this script):
        signal ∈ {0, 1} as state indicator
        FLAT + signal=1  → ENTER  at mid[i]
        LONG + signal=1  → HOLD
        LONG + signal=0  → EXIT   at mid[i]
        FLAT + signal=0  → STAY FLAT
        N_trades = O(transitions) ≈ 5–50/day, fee paid once per RT

KRX 23bps fee floor + ~5bps spread cost = ~28bps gross threshold for deployable.
This script measures the fraction of v3 specs that clear that threshold under the
regime-state interpretation — independent of the v4 run currently in progress.

Output: regime_state_ablation_<timestamp>.csv with per-spec metrics.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.data_loader_v2 import load_day_v2  # noqa: E402
from chain1.backtest_runner import iter_snaps  # noqa: E402

# KRX cash deployment economics (per CLAUDE.md §🚫 + project_krx_only_scope memory)
KRX_RT_FEE_BPS = 23.0          # 1.5 maker × 2 + 20 sell tax
KRX_SPREAD_COST_EST_BPS = 5.0  # est. mean cross-spread cost when MARKET on both sides
DEPLOYABLE_GROSS_THRESHOLD_BPS = KRX_RT_FEE_BPS + KRX_SPREAD_COST_EST_BPS  # 28 bps


def load_signal_module(code_path: Path) -> tuple[Callable, str, float]:
    """Import a generated spec module and return (signal_fn, direction, threshold)."""
    spec_name = code_path.stem
    spec = importlib.util.spec_from_file_location(spec_name, code_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.signal, mod.DIRECTION, mod.THRESHOLD


def regime_state_backtest(
    signal_fn: Callable,
    direction: str,
    df: pd.DataFrame,
) -> dict:
    """Run regime-state backtest on one (symbol, date) frame.

    Returns: {n_regimes, mean_gross_bps, std_gross_bps, n_winners, n_losers,
              mean_duration_ticks, max_gross_bps, min_gross_bps,
              total_gross_bps, regimes: [...]}
    """
    if len(df) == 0:
        return _empty_result()

    mid = (df["BIDP1"].to_numpy(dtype=np.float64) +
           df["ASKP1"].to_numpy(dtype=np.float64)) / 2.0

    in_position = False
    entry_idx = -1
    entry_mid = 0.0
    sign = +1 if direction == "long_if_pos" else -1

    regimes: list[dict] = []

    for i, snap in enumerate(iter_snaps(df)):
        # Need prev for some primitives — set as attribute (chain 1 convention)
        snap.prev = None  # we don't track prev across; primitive helpers manage state
        try:
            s = bool(signal_fn(snap))
        except Exception:
            continue

        if s and not in_position:
            # Enter
            in_position = True
            entry_idx = i
            entry_mid = mid[i]
        elif not s and in_position:
            # Exit
            exit_mid = mid[i]
            gross_bps = (exit_mid - entry_mid) / entry_mid * 1e4 * sign
            regimes.append({
                "entry_idx": entry_idx,
                "exit_idx": i,
                "duration_ticks": i - entry_idx,
                "entry_mid": entry_mid,
                "exit_mid": exit_mid,
                "gross_bps": gross_bps,
            })
            in_position = False

    # Force-close at end of session
    if in_position:
        exit_mid = mid[-1]
        gross_bps = (exit_mid - entry_mid) / entry_mid * 1e4 * sign
        regimes.append({
            "entry_idx": entry_idx,
            "exit_idx": len(mid) - 1,
            "duration_ticks": len(mid) - 1 - entry_idx,
            "entry_mid": entry_mid,
            "exit_mid": exit_mid,
            "gross_bps": gross_bps,
            "force_closed": True,
        })

    if not regimes:
        return _empty_result()

    grosses = np.array([r["gross_bps"] for r in regimes])
    durations = np.array([r["duration_ticks"] for r in regimes])

    return {
        "n_regimes": len(regimes),
        "mean_gross_bps": float(grosses.mean()),
        "median_gross_bps": float(np.median(grosses)),
        "std_gross_bps": float(grosses.std()),
        "min_gross_bps": float(grosses.min()),
        "max_gross_bps": float(grosses.max()),
        "p25_gross_bps": float(np.percentile(grosses, 25)),
        "p75_gross_bps": float(np.percentile(grosses, 75)),
        "p90_gross_bps": float(np.percentile(grosses, 90)),
        "n_winners": int((grosses > 0).sum()),
        "n_losers": int((grosses <= 0).sum()),
        "n_above_fee": int((grosses > KRX_RT_FEE_BPS).sum()),
        "n_above_deployable": int((grosses > DEPLOYABLE_GROSS_THRESHOLD_BPS).sum()),
        "total_gross_bps": float(grosses.sum()),
        "mean_duration_ticks": float(durations.mean()),
        "median_duration_ticks": float(np.median(durations)),
        "regimes": regimes,
    }


def _empty_result() -> dict:
    return {k: 0 for k in [
        "n_regimes", "mean_gross_bps", "median_gross_bps", "std_gross_bps",
        "min_gross_bps", "max_gross_bps", "p25_gross_bps", "p75_gross_bps", "p90_gross_bps",
        "n_winners", "n_losers", "n_above_fee", "n_above_deployable",
        "total_gross_bps", "mean_duration_ticks", "median_duration_ticks",
    ]} | {"regimes": []}


def aggregate_per_spec(
    spec_id: str,
    code_path: Path,
    symbols: list[str],
    dates: list[str],
) -> dict:
    """Run regime-state backtest across all (symbol, date) and aggregate."""
    try:
        signal_fn, direction, threshold = load_signal_module(code_path)
    except Exception as e:
        return {"spec_id": spec_id, "error": f"load: {e}", "n_regimes": 0}

    all_regimes: list[float] = []
    all_durations: list[float] = []
    sessions = 0
    errors = 0

    for sym in symbols:
        for date in dates:
            try:
                df = load_day_v2(sym, date)
            except Exception:
                errors += 1
                continue
            if len(df) == 0:
                continue
            try:
                # Reload signal_fn each session — stateful helpers reset
                signal_fn, direction, threshold = load_signal_module(code_path)
                result = regime_state_backtest(signal_fn, direction, df)
                sessions += 1
                for r in result["regimes"]:
                    all_regimes.append(r["gross_bps"])
                    all_durations.append(r["duration_ticks"])
            except Exception as e:
                errors += 1

    if not all_regimes:
        return {
            "spec_id": spec_id, "n_regimes": 0, "sessions": sessions, "errors": errors,
            "direction": direction, "threshold": threshold,
        }

    grosses = np.array(all_regimes)
    durations = np.array(all_durations)

    return {
        "spec_id": spec_id,
        "direction": direction,
        "threshold": threshold,
        "sessions": sessions,
        "errors": errors,
        "n_regimes": len(grosses),
        "mean_gross_bps": float(grosses.mean()),
        "median_gross_bps": float(np.median(grosses)),
        "std_gross_bps": float(grosses.std()),
        "min_gross_bps": float(grosses.min()),
        "max_gross_bps": float(grosses.max()),
        "p90_gross_bps": float(np.percentile(grosses, 90)),
        "p99_gross_bps": float(np.percentile(grosses, 99)) if len(grosses) >= 100 else None,
        "n_winners": int((grosses > 0).sum()),
        "n_losers": int((grosses <= 0).sum()),
        "wr": float((grosses > 0).mean()),
        "n_above_fee_23bps": int((grosses > KRX_RT_FEE_BPS).sum()),
        "frac_above_fee": float((grosses > KRX_RT_FEE_BPS).mean()),
        "n_above_deployable_28bps": int((grosses > DEPLOYABLE_GROSS_THRESHOLD_BPS).sum()),
        "frac_above_deployable": float((grosses > DEPLOYABLE_GROSS_THRESHOLD_BPS).mean()),
        "total_gross_bps": float(grosses.sum()),
        "mean_duration_ticks": float(durations.mean()),
        "median_duration_ticks": float(np.median(durations)),
        # Net under regime-state model: total_gross − n_regimes × fee
        "net_total_bps": float(grosses.sum() - len(grosses) * KRX_RT_FEE_BPS),
        "mean_net_per_regime_bps": float(grosses.mean() - KRX_RT_FEE_BPS),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-root", default="iterations_v3_archive",
                    help="Path to v3 archive directory")
    ap.add_argument("--symbols", nargs="+", default=["005930", "000660", "005380"])
    ap.add_argument("--dates", nargs="+",
                    default=["20260316", "20260317", "20260318", "20260319",
                             "20260320", "20260323", "20260324", "20260325"])
    ap.add_argument("--output", default=None,
                    help="CSV output path; defaults to analysis/regime_state_ablation_<ts>.csv")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only first N specs (for debugging)")
    args = ap.parse_args()

    archive_root = Path(args.archive_root)
    if not archive_root.exists():
        print(f"ERROR: archive root not found: {archive_root}")
        return 1

    code_files = sorted(archive_root.glob("iter_*/code/*.py"))
    code_files = [f for f in code_files if not f.name.endswith(".codegen.json")]
    if args.limit:
        code_files = code_files[:args.limit]
    print(f"Found {len(code_files)} spec code files in {archive_root}")
    print(f"Symbols: {args.symbols}")
    print(f"Dates: {args.dates}")
    print(f"KRX fee floor: {KRX_RT_FEE_BPS} bps RT, deployable threshold: {DEPLOYABLE_GROSS_THRESHOLD_BPS} bps\n")

    rows = []
    t_start = time.time()
    for idx, code_path in enumerate(code_files):
        spec_id = code_path.stem
        print(f"[{idx+1}/{len(code_files)}] {spec_id} ...", flush=True, end=" ")
        t0 = time.time()
        result = aggregate_per_spec(spec_id, code_path, args.symbols, args.dates)
        dt = time.time() - t0
        if result.get("error"):
            print(f"ERROR: {result['error']}")
        elif result["n_regimes"] == 0:
            print(f"no regimes ({dt:.1f}s)")
        else:
            print(f"n={result['n_regimes']} mean={result['mean_gross_bps']:+.2f}bps "
                  f"WR={result['wr']:.3f} fee_pass={result['frac_above_fee']:.3f} ({dt:.1f}s)")
        rows.append(result)

    df = pd.DataFrame(rows)
    if args.output is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        args.output = f"analysis/regime_state_ablation_{ts}.csv"
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    elapsed = time.time() - t_start
    print(f"\n=== DONE in {elapsed/60:.1f} min ===")
    print(f"Output: {args.output}")
    print(f"Specs processed: {len(rows)}")

    # Quick summary
    df_ok = df[df["n_regimes"] > 0].copy()
    if len(df_ok) > 0:
        print(f"\n=== Summary ({len(df_ok)} specs with regimes) ===")
        print(f"  mean(mean_gross_bps): {df_ok['mean_gross_bps'].mean():+.3f} bps")
        print(f"  max(mean_gross_bps):  {df_ok['mean_gross_bps'].max():+.3f} bps")
        print(f"  Specs with mean_gross > 0:    {(df_ok['mean_gross_bps'] > 0).sum()}/{len(df_ok)}")
        print(f"  Specs with mean_gross > 23 bps (above fee): {(df_ok['mean_gross_bps'] > KRX_RT_FEE_BPS).sum()}/{len(df_ok)}")
        print(f"  Specs with mean_gross > 28 bps (deployable): {(df_ok['mean_gross_bps'] > DEPLOYABLE_GROSS_THRESHOLD_BPS).sum()}/{len(df_ok)}")
        print(f"  Specs with frac_above_fee > 0.5 (>50% regimes profitable):  {(df_ok['frac_above_fee'] > 0.5).sum()}/{len(df_ok)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
