"""Multi-day robustness check for a single SignalSpec.

Run the same spec independently on each date and report per-date WR / expectancy.
Used to validate whether a "session best" spec survived out-of-sample replication.

CLI:
    python -m chain1.multi_day_robustness \
        --spec-json iterations/iter_006/specs/iter006_adaptive_momentum_imbalance.json \
        --symbols 005930 000660 \
        --dates 20260305 20260311 20260317 20260323 20260326 \
        --out /tmp/multi_day.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import SignalSpec, GeneratedCode  # noqa: E402
from chain1.code_generator import generate_code  # noqa: E402
from chain1.backtest_runner import run_backtest  # noqa: E402


def multi_day_robustness(
    spec_json_path: str,
    symbols: list[str],
    dates: list[str],
    out_path: str | None = None,
) -> dict:
    """Run the spec against each date separately; return per-date + aggregate."""
    spec_dict = json.loads(Path(spec_json_path).read_text())
    # Strip measured_* to avoid confusion
    for k in ("measured_wr", "measured_expectancy_bps", "measured_n_trades"):
        spec_dict[k] = None
    spec = SignalSpec(**spec_dict)

    # Render code once (deterministic)
    code_path = REPO_ROOT / "iterations" / "_multi_day" / f"{spec.spec_id}.py"
    code = generate_code(spec, code_path)

    per_date: list[dict] = []
    for date in dates:
        result = run_backtest(spec, code, symbols, [date])
        # Aggregate per-date (across symbols)
        ps_list = [ps.model_dump() for ps in result.per_symbol]
        n_wins = sum(ps["n_wins"] for ps in ps_list)
        n_losses = sum(ps["n_losses"] for ps in ps_list)
        n_trades = n_wins + n_losses
        wr = n_wins / max(1, n_trades)
        # Expectancy = (sum_win - sum_loss) / n_trades  (signed bps per trade)
        sum_win = sum(ps["sum_win_bps"] for ps in ps_list)
        sum_loss = sum(ps["sum_loss_bps"] for ps in ps_list)
        exp = (sum_win - sum_loss) / max(1, n_trades)

        per_date.append({
            "date": date, "n_trades": n_trades, "n_wins": n_wins, "n_losses": n_losses,
            "wr": float(wr), "expectancy_bps": float(exp),
            "sum_win_bps": float(sum_win), "sum_loss_bps": float(sum_loss),
            "per_symbol": ps_list,
        })

    # Aggregate across dates
    all_trades = sum(d["n_trades"] for d in per_date)
    all_wins = sum(d["n_wins"] for d in per_date)
    all_losses = sum(d["n_losses"] for d in per_date)
    agg_wr = all_wins / max(1, all_wins + all_losses)
    agg_sum_win = sum(d["sum_win_bps"] for d in per_date)
    agg_sum_loss = sum(d["sum_loss_bps"] for d in per_date)
    agg_exp = (agg_sum_win - agg_sum_loss) / max(1, all_trades)

    # Cross-date std
    wrs = [d["wr"] for d in per_date if d["n_trades"] > 0]
    exps = [d["expectancy_bps"] for d in per_date if d["n_trades"] > 0]
    wr_std = statistics.pstdev(wrs) if len(wrs) >= 2 else 0.0
    exp_std = statistics.pstdev(exps) if len(exps) >= 2 else 0.0

    output = {
        "spec_id": spec.spec_id,
        "formula": spec.formula,
        "threshold": spec.threshold,
        "prediction_horizon_ticks": spec.prediction_horizon_ticks,
        "direction": spec.direction.value,
        "symbols": symbols,
        "dates_scanned": dates,
        "per_date": per_date,
        "aggregate": {
            "total_n_trades": all_trades,
            "wr": float(agg_wr),
            "expectancy_bps": float(agg_exp),
        },
        "cross_date_stats": {
            "wr_mean": statistics.mean(wrs) if wrs else 0.0,
            "wr_std": float(wr_std),
            "expectancy_mean": statistics.mean(exps) if exps else 0.0,
            "expectancy_std": float(exp_std),
            "wr_min": min(wrs) if wrs else 0.0,
            "wr_max": max(wrs) if wrs else 0.0,
            "exp_min": min(exps) if exps else 0.0,
            "exp_max": max(exps) if exps else 0.0,
        },
        "verdict": _verdict(wrs, exps),
    }

    if out_path:
        Path(out_path).write_text(json.dumps(output, indent=2))
    return output


def _verdict(wrs: list[float], exps: list[float]) -> dict:
    """Heuristic robustness classification."""
    if len(wrs) < 2:
        return {"class": "insufficient_dates", "detail": "< 2 dates with trades"}
    wr_std = statistics.pstdev(wrs)
    exp_std = statistics.pstdev(exps)
    wr_min = min(wrs); wr_max = max(wrs)
    exp_min = min(exps)

    # Robust if WR always >= 0.55 AND exp_bps always > 0 AND stdev modest
    if wr_min < 0.45:
        return {"class": "regime_dependent_fail", "detail": f"WR dropped to {wr_min:.3f} on at least one date — signal sometimes inverted"}
    if exp_min <= 0:
        return {"class": "expectancy_not_stable", "detail": f"expectancy went non-positive ({exp_min:.2f} bps) on at least one date"}
    if wr_std > 0.10:
        return {"class": "high_wr_variance", "detail": f"WR std {wr_std:.3f} > 10% — regime-sensitive"}
    if exp_std / max(abs(statistics.mean(exps)), 1e-6) > 0.5:
        return {"class": "high_expectancy_variance", "detail": f"expectancy CoV > 50%"}
    return {"class": "robust", "detail": f"WR range [{wr_min:.3f}, {wr_max:.3f}], exp range [{exp_min:.2f}, {max(exps):.2f}] bps"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True)
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--dates", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = multi_day_robustness(args.spec_json, args.symbols, args.dates, args.out)
    print(f"\n=== Multi-day robustness: {out['spec_id']} ===")
    print(f"Formula: {out['formula']}")
    print(f"Threshold: {out['threshold']}  Horizon: {out['prediction_horizon_ticks']}t")
    print(f"\nPer-date (symbols={out['symbols']}):")
    print(f"{'date':<10} {'n_trades':>8}  {'WR':>8}  {'exp_bps':>10}")
    for d in out["per_date"]:
        print(f"{d['date']:<10} {d['n_trades']:>8}  {d['wr']:>8.4f}  {d['expectancy_bps']:>+10.3f}")
    print(f"\nAggregate: n={out['aggregate']['total_n_trades']:,}  "
          f"WR={out['aggregate']['wr']:.4f}  exp={out['aggregate']['expectancy_bps']:+.3f} bps")
    cd = out['cross_date_stats']
    print(f"Cross-date: WR mean={cd['wr_mean']:.4f} std={cd['wr_std']:.4f}  "
          f"exp mean={cd['expectancy_mean']:+.3f} std={cd['expectancy_std']:.3f}")
    print(f"Verdict: {out['verdict']['class']} — {out['verdict']['detail']}")
