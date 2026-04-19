#!/usr/bin/env python3
"""Experiment H — Risk-adjusted metrics: Calmar, Sortino, alpha vs Buy-Hold.

For every bar strategy in strategies/bar_*, compute:
  - Calmar = ann_return / |MDD|
  - Sortino = mean_return / downside_std * sqrt(365)
  - Alpha vs Buy-Hold (CAPM-style beta + alpha regression)
  - Information Ratio vs BH = (strat_return - bh_return) / tracking_error
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from scripts.bar_baselines import load_daily, split_is_oos

HERE = Path(__file__).resolve().parent
HERE.mkdir(parents=True, exist_ok=True)


def _load_strategy(path: Path):
    sp = importlib.util.spec_from_file_location(f"_{path.parent.name}", path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def risk_metrics(strat_ret: np.ndarray, bh_ret: np.ndarray,
                 bars_per_year: float = 365.0) -> dict:
    """Return dict with Calmar, Sortino, alpha vs BH, IR."""
    if len(strat_ret) < 2:
        return {}

    total_strat = float(np.prod(1.0 + strat_ret) - 1.0)
    total_bh = float(np.prod(1.0 + bh_ret) - 1.0)

    # Annualized
    days = len(strat_ret) / bars_per_year * 365.0
    years = max(days / 365.0, 0.01)
    ann_strat = (1.0 + total_strat) ** (1.0 / years) - 1.0
    ann_bh = (1.0 + total_bh) ** (1.0 / years) - 1.0

    # Sharpe
    sharpe = float(np.mean(strat_ret) / max(np.std(strat_ret), 1e-12) * np.sqrt(bars_per_year))

    # Sortino (downside deviation only)
    downside = strat_ret[strat_ret < 0]
    if len(downside) > 1:
        sortino = float(np.mean(strat_ret) / np.std(downside) * np.sqrt(bars_per_year))
    else:
        sortino = float("inf") if np.mean(strat_ret) > 0 else 0.0

    # MDD
    equity = np.cumprod(1.0 + strat_ret)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    mdd = float(np.min(dd))

    # Calmar
    calmar = ann_strat / abs(mdd) if mdd < 0 else float("inf")

    # Alpha vs BH (single-factor regression: strat_ret = alpha + beta * bh_ret)
    if len(strat_ret) > 5 and np.std(bh_ret) > 0:
        cov = np.cov(strat_ret, bh_ret)[0, 1]
        beta = cov / np.var(bh_ret)
        alpha = float(np.mean(strat_ret) - beta * np.mean(bh_ret))
        alpha_ann = alpha * bars_per_year
    else:
        beta = 0.0
        alpha = 0.0
        alpha_ann = 0.0

    # Information Ratio
    tracking_error = np.std(strat_ret - bh_ret)
    ir = float(np.mean(strat_ret - bh_ret) / max(tracking_error, 1e-12) * np.sqrt(bars_per_year))

    return {
        "total_return_pct": total_strat * 100,
        "ann_return_pct": ann_strat * 100,
        "bh_total_return_pct": total_bh * 100,
        "bh_ann_return_pct": ann_bh * 100,
        "sharpe": sharpe,
        "sortino": sortino if sortino != float("inf") else 999.9,
        "mdd_pct": mdd * 100,
        "calmar": calmar if calmar != float("inf") else 999.9,
        "alpha_ann": alpha_ann,
        "beta_vs_bh": float(beta),
        "information_ratio": ir,
        "n_bars": len(strat_ret),
    }


def compute_for_strategy(strat_dir: Path) -> dict:
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    symbol = spec["target_symbol"]
    params = spec.get("params", {})
    fee = float(params.get("fee_side_bps", 5.0))
    module = _load_strategy(strat_dir / "strategy.py")

    df = load_daily(symbol)
    signal = module.generate_signal(df, **params)

    close = df["close"].to_numpy()
    signal_arr = signal.fillna(0).astype(int).to_numpy()
    position = np.concatenate([[0], signal_arr[:-1]])
    ret = np.diff(close) / close[:-1]
    pos = position[1:]
    strat_ret_raw = pos * ret
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee / 1e4)
    strat_ret = strat_ret_raw - fee_cost
    bh_ret = ret  # buy and hold

    m = risk_metrics(strat_ret, bh_ret, bars_per_year=365.0)
    m["strategy_id"] = strat_dir.name
    m["symbol"] = symbol
    return m


def main() -> None:
    results = []
    print(f"{'Strategy':<32} {'Sym':<8} {'Ret%':>8} {'BH Ret%':>8} {'Sharpe':>7} "
          f"{'Sortino':>8} {'Calmar':>7} {'Alpha':>7} {'IR':>6}")
    print("-" * 98)
    for d in sorted((REPO / "strategies").iterdir()):
        if not d.is_dir() or not d.name.startswith("bar_"):
            continue
        try:
            m = compute_for_strategy(d)
            results.append(m)
            print(f"{m['strategy_id']:<32} {m['symbol']:<8} "
                  f"{m['total_return_pct']:>+8.1f} {m['bh_total_return_pct']:>+8.1f} "
                  f"{m['sharpe']:>+7.2f} {m['sortino']:>+8.2f} {m['calmar']:>+7.2f} "
                  f"{m['alpha_ann']*100:>+7.2f} {m['information_ratio']:>+6.2f}")
        except Exception as e:
            print(f"  {d.name}: FAILED — {e}")

    (HERE / "results.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"\nsaved -> {HERE.relative_to(REPO)}/results.json")

    # Summary stats
    alphas = [r["alpha_ann"] * 100 for r in results]
    positive_alpha = sum(1 for a in alphas if a > 0)
    positive_ir = sum(1 for r in results if r["information_ratio"] > 0)
    print(f"\nPositive alpha (vs BH): {positive_alpha}/{len(results)}")
    print(f"Positive IR: {positive_ir}/{len(results)}")


if __name__ == "__main__":
    main()
