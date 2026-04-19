#!/usr/bin/env python3
"""Run an LLM-generated bar-level strategy from strategies_bar/<id>/.

Loads strategy.py's generate_signal() + spec.yaml, backtests on the target
symbol's IS + OOS splits, emits GenericFill list, runs invariant check,
and writes report.json + fills.json + attribution.json for paper use.

Usage:
  python scripts/bar_run_llm_strategy.py --id bar_s1_sol_vol_momentum
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.bar_baselines import load_daily, split_is_oos, backtest
from scripts.bar_backtest import generate_fills
from scripts.check_invariants_from_fills import GenericFill, run_checker


def _load_strategy_module(strategy_path: Path):
    spec = importlib.util.spec_from_file_location("llm_strategy", strategy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(strat_id: str) -> dict:
    strat_dir = REPO / "strategies_bar" / strat_id
    spec_path = strat_dir / "spec.yaml"
    strategy_path = strat_dir / "strategy.py"
    spec_dict = yaml.safe_load(spec_path.read_text())

    symbol = spec_dict["target_symbol"]
    params = spec_dict.get("params", {})
    fee_bps = float(params.get("fee_side_bps", 5.0))
    lot_size = int(params.get("lot_size", 1))

    module = _load_strategy_module(strategy_path)

    df = load_daily(symbol)
    is_df, oos_df = split_is_oos(df)

    results = {}
    for split_name, split_df in [("is", is_df), ("oos", oos_df)]:
        signal = module.generate_signal(split_df, **params)
        metrics = backtest(split_df, signal, fee_side_bps=fee_bps)
        fills = generate_fills(split_df, signal, symbol, lot_size=lot_size)

        # Run invariant check — for bar-level, main invariant parameter is
        # max_entries_per_session. Note: 'session' interpretation maps to
        # calendar date, and we honor that in the daily fill timestamps.
        violations = run_checker(spec_dict, fills)
        v_by_type: dict[str, int] = {}
        for v in violations:
            v_by_type[v.invariant_type] = v_by_type.get(v.invariant_type, 0) + 1

        results[split_name] = {
            "metrics": metrics,
            "n_fills": len(fills),
            "invariant_violations": [v.to_dict() for v in violations],
            "invariant_violation_by_type": v_by_type,
            "fills": [
                {"ts_ns": f.ts_ns, "symbol": f.symbol, "side": f.side,
                 "qty": f.qty, "price": f.price, "tag": f.tag,
                 "position_after": f.position_after, "lot_size": f.lot_size,
                 "context": f.context}
                for f in fills
            ],
        }

    report = {
        "strategy_id": strat_id,
        "symbol": symbol,
        "fee_side_bps": fee_bps,
        "lot_size": lot_size,
        "is": results["is"],
        "oos": results["oos"],
    }

    (strat_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))

    # Human-readable summary
    def fmt(m: dict) -> str:
        return (f"ret={m['total_return_pct']:.2f}%  sharpe={m['sharpe_annualized']:.3f}  "
                f"MDD={m['mdd_pct']:.2f}%  trades={m['n_trades']}  "
                f"exposure={m['avg_exposure']:.2f}")

    print(f"=== {strat_id} on {symbol} ===")
    print(f"  IS ({spec_dict.get('target_horizon', 'daily')}):  {fmt(results['is']['metrics'])}")
    print(f"       violations: {results['is']['invariant_violation_by_type']}")
    print(f"  OOS:              {fmt(results['oos']['metrics'])}")
    print(f"       violations: {results['oos']['invariant_violation_by_type']}")

    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Strategy id under strategies_bar/")
    args = ap.parse_args()
    run(args.id)


if __name__ == "__main__":
    main()
