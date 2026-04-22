"""Horizon sweep — empirical test of √h scaling hypothesis.

Take one SignalSpec, vary its prediction_horizon_ticks across {5, 20, 50, 100, 200},
run each across all given dates, report WR / expectancy / n_trades per horizon.

Compares against theoretical ceiling:
  expected |Δmid| at horizon h ≈ sqrt(h) × sqrt(tick_var_per_step)
  theoretical max expectancy ≈ (2 × WR − 1) × expected |Δmid|
  → horizon extension helps iff actual expectancy capture-rate stays similar.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import SignalSpec  # noqa: E402
from chain1.code_generator import generate_code  # noqa: E402
from chain1.backtest_runner import run_backtest  # noqa: E402


def sweep(
    base_spec_json: str,
    horizons: list[int],
    symbols: list[str],
    dates: list[str],
    out_path: str | None = None,
    tick_bps_estimate: float = 5.5,  # Samsung 1-tick ~ 5.5 bps at ~180K KRW
) -> dict:
    base = json.loads(Path(base_spec_json).read_text())
    for k in ("measured_wr", "measured_expectancy_bps", "measured_n_trades"):
        base[k] = None

    results = []
    for h in horizons:
        spec_dict = dict(base)
        spec_dict["prediction_horizon_ticks"] = int(h)
        spec_dict["spec_id"] = f"hsweep_h{h:03d}_{base['spec_id'][:30]}"
        spec = SignalSpec(**spec_dict)

        code_path = REPO_ROOT / "iterations" / "_horizon_sweep" / f"{spec.spec_id}.py"
        code = generate_code(spec, code_path)

        # Run across all dates, single call (aggregated result)
        result = run_backtest(spec, code, symbols, dates)

        # Theoretical ceiling
        expected_abs_move = math.sqrt(h) * tick_bps_estimate
        wr = result.aggregate_wr
        theoretical_max = (2 * wr - 1) * expected_abs_move if wr > 0.5 else 0.0
        actual = result.aggregate_expectancy_bps
        capture_rate = (actual / theoretical_max) if theoretical_max > 0 else 0.0

        results.append({
            "horizon": h,
            "n_trades": result.aggregate_n_trades,
            "wr": float(wr),
            "expectancy_bps": float(actual),
            "theoretical_ceiling_bps": float(theoretical_max),
            "capture_rate": float(capture_rate),
            "sqrt_h": float(math.sqrt(h)),
        })

    # Build comparison
    output = {
        "base_spec_id": base["spec_id"],
        "formula": base["formula"],
        "threshold": base["threshold"],
        "symbols": symbols,
        "dates": dates,
        "tick_bps_estimate": tick_bps_estimate,
        "sweep": results,
        "summary": {
            "best_horizon": max(results, key=lambda r: r["expectancy_bps"])["horizon"],
            "best_expectancy_bps": max(r["expectancy_bps"] for r in results),
            "best_wr_horizon": max(results, key=lambda r: r["wr"])["horizon"],
        },
    }
    if out_path:
        Path(out_path).write_text(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True)
    ap.add_argument("--horizons", type=int, nargs="+", default=[5, 20, 50, 100, 200])
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--dates", nargs="+", required=True)
    ap.add_argument("--tick-bps", type=float, default=5.5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = sweep(args.spec_json, args.horizons, args.symbols, args.dates, args.out, args.tick_bps)

    print(f"\n=== Horizon sweep: {out['base_spec_id']} ===")
    print(f"Formula: {out['formula']}")
    print(f"Dates: {len(out['dates'])} × Symbols: {len(out['symbols'])}")
    print()
    print(f"{'h':>4} {'n_trades':>10} {'WR':>8} {'exp_bps':>10} {'theory':>10} {'capture%':>10}")
    for r in out["sweep"]:
        print(f"{r['horizon']:>4} {r['n_trades']:>10,} {r['wr']:>8.4f} "
              f"{r['expectancy_bps']:>+10.3f} {r['theoretical_ceiling_bps']:>+10.3f} "
              f"{r['capture_rate']*100:>9.1f}%")
    print()
    print(f"Best horizon by expectancy: h={out['summary']['best_horizon']} "
          f"({out['summary']['best_expectancy_bps']:+.3f} bps)")
