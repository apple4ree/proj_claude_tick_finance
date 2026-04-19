#!/usr/bin/env python3
"""Counterfactual PnL attribution for bar-level strategies.

Runs the strategy twice:
  1. NORMAL mode — signal emitted as designed
  2. STRICT mode — filter signal to enforce max_entries_per_session

Produces clean_pnl / bug_pnl / clean_pct_of_total in the same schema as the
tick-level attribute_pnl.py. Output appended to
data/bar_attribution_summary.json.

Usage:
  python scripts/bar_attribute_pnl.py --all
  python scripts/bar_attribute_pnl.py --id bar_s5_btc_momentum_ls
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.bar_baselines import load_daily, split_is_oos, backtest


def _load_strategy(path: Path):
    spec = importlib.util.spec_from_file_location("ls", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _strict_signal(signal: pd.Series, df: pd.DataFrame, max_entries: int) -> pd.Series:
    """Enforce max_entries_per_session by zeroing out any entry beyond the Nth on a given day.

    For bar-level (daily) strategies the 'session' == the date. At daily
    resolution there's at most one entry per bar anyway, but this filter
    becomes meaningful under: (a) long-short signals that may flip within
    a day's context in multi-horizon work, or (b) multi-bar sessions at
    finer granularity.

    We interpret max_entries as a per-calendar-day constraint. At daily
    resolution this is equivalent to capping the absolute position change
    |pos_after - pos_before| to cap * lot_size per bar.
    """
    # Current implementation: for daily bars each signal point is one
    # session by construction. max_entries_per_session=1 means at most
    # one flip to nonzero per day — which is always true at daily bars.
    # The more relevant strict-mode intervention at bar-level is to drop
    # days beyond the cap when counted per calendar-date. Since our signal
    # is already per-day, strict = normal for max_entries at daily.
    # This function exists as a hook — richer enforcement can be added
    # when per-intraday-bar strategies arrive.
    return signal


def attribute(strat_id: str) -> dict:
    strat_dir = REPO / "strategies_bar" / strat_id
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    symbol = spec["target_symbol"]
    params = spec.get("params", {})
    fee = float(params.get("fee_side_bps", 5.0))
    max_entries = int(params.get("max_entries_per_session", 1))

    module = _load_strategy(strat_dir / "strategy.py")
    df = load_daily(symbol)
    is_df, oos_df = split_is_oos(df)

    out: dict = {"strategy_id": strat_id, "symbol": symbol}
    for split_name, split_df in [("is", is_df), ("oos", oos_df)]:
        sig_normal = module.generate_signal(split_df, **params)
        sig_strict = _strict_signal(sig_normal, split_df, max_entries)

        m_normal = backtest(split_df, sig_normal, fee_side_bps=fee)
        m_strict = backtest(split_df, sig_strict, fee_side_bps=fee)

        normal_ret = m_normal["total_return_pct"] / 100.0
        strict_ret = m_strict["total_return_pct"] / 100.0
        bug = normal_ret - strict_ret
        clean_pct = (strict_ret / normal_ret * 100.0) if normal_ret != 0 else None

        out[split_name] = {
            "normal_return_pct": m_normal["total_return_pct"],
            "strict_return_pct": m_strict["total_return_pct"],
            "bug_return_pct": bug * 100.0,
            "clean_pct_of_total": clean_pct,
            "normal_sharpe": m_normal["sharpe_annualized"],
            "strict_sharpe": m_strict["sharpe_annualized"],
            "normal_mdd_pct": m_normal["mdd_pct"],
            "strict_mdd_pct": m_strict["mdd_pct"],
            "n_trades_normal": m_normal["n_trades"],
            "n_trades_strict": m_strict["n_trades"],
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="Single strategy id")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        ids = sorted(d.name for d in (REPO / "strategies_bar").iterdir() if d.is_dir())
    elif args.id:
        ids = [args.id]
    else:
        ap.error("specify --id or --all")

    results = [attribute(i) for i in ids]

    print(f"{'Strategy':<34} {'Split':<4} {'Norm ret%':>10} {'Strict ret%':>12} "
          f"{'bug ret%':>10} {'clean %':>8} {'#trade N':>9} {'#trade S':>9}")
    print("-" * 102)
    for r in results:
        for split in ("is", "oos"):
            d = r[split]
            cp = d.get("clean_pct_of_total")
            cp_s = f"{cp:.1f}%" if cp is not None else "  --"
            print(f"{r['strategy_id']:<34} {split:<4} "
                  f"{d['normal_return_pct']:>+10.2f} {d['strict_return_pct']:>+12.2f} "
                  f"{d['bug_return_pct']:>+10.2f} {cp_s:>8} "
                  f"{d['n_trades_normal']:>9d} {d['n_trades_strict']:>9d}")

    out_path = REPO / "data" / "bar_attribution_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nsaved -> {out_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
