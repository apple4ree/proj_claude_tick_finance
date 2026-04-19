#!/usr/bin/env python3
"""Full 30-corpus summary table with Return + Sharpe + MDD.

Produces:
  - stdout human-readable table
  - data/full_corpus_table.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.bar_baselines import load_daily, split_is_oos, backtest


def tick_rows() -> list[dict]:
    out = []
    for d in sorted((REPO / "strategies").iterdir()):
        if not d.is_dir() or not d.name.startswith("strat_"):
            continue
        report_path = d / "report.json"
        if not report_path.exists():
            continue
        try:
            r = json.loads(report_path.read_text())
        except Exception:
            continue
        out.append({
            "segment": "tick",
            "strategy_id": d.name,
            "return_pct": r.get("return_pct", 0.0),
            "sharpe": r.get("sharpe_annualized", 0.0),
            "mdd_pct": r.get("mdd_pct", 0.0),
            "n_roundtrips": r.get("n_roundtrips", 0),
            "win_rate_pct": r.get("win_rate_pct", 0.0),
            "violations": r.get("invariant_violation_count", 0),
            "window": f"KRX IS {len(r.get('dates', []))} days",
        })
    return out


def bar_rows() -> list[dict]:
    out = []
    bar_dir = REPO / "strategies_bar"
    for d in sorted(bar_dir.iterdir()):
        if not d.is_dir():
            continue
        spec = yaml.safe_load((d / "spec.yaml").read_text())
        symbol = spec["target_symbol"]
        params = spec.get("params", {})
        fee = float(params.get("fee_side_bps", 5.0))

        sp = importlib.util.spec_from_file_location(f"_{d.name}", d / "strategy.py")
        module = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(module)

        df = load_daily(symbol)
        is_df, oos_df = split_is_oos(df)

        is_sig = module.generate_signal(is_df, **params)
        oos_sig = module.generate_signal(oos_df, **params)
        m_is = backtest(is_df, is_sig, fee_side_bps=fee)
        m_oos = backtest(oos_df, oos_sig, fee_side_bps=fee)

        # Combined (IS + OOS) — append together conceptually
        full_df = df.copy()
        full_sig = module.generate_signal(full_df, **params)
        m_full = backtest(full_df, full_sig, fee_side_bps=fee)

        out.append({
            "segment": "bar",
            "strategy_id": d.name,
            "symbol": symbol,
            "is_return_pct": m_is["total_return_pct"],
            "is_sharpe": m_is["sharpe_annualized"],
            "is_mdd_pct": m_is["mdd_pct"],
            "oos_return_pct": m_oos["total_return_pct"],
            "oos_sharpe": m_oos["sharpe_annualized"],
            "oos_mdd_pct": m_oos["mdd_pct"],
            "full_return_pct": m_full["total_return_pct"],
            "full_sharpe": m_full["sharpe_annualized"],
            "full_mdd_pct": m_full["mdd_pct"],
            "is_n_trades": m_is["n_trades"],
            "oos_n_trades": m_oos["n_trades"],
            "exposure": m_is["avg_exposure"],
        })
    return out


def main() -> None:
    print("=" * 100)
    print("TICK CORPUS (KRX, n=20) — IS only")
    print("=" * 100)
    print(f"{'Strategy':<45} {'Ret%':>7} {'Sharpe':>8} {'MDD%':>7} {'#RT':>5} {'WR%':>6} {'Viol':>5}")
    print("-" * 100)
    tick = tick_rows()
    for r in tick:
        sid = r["strategy_id"].replace("strat_20260417_", "17_").replace("strat_20260418_", "18_")
        print(f"{sid:<45} {r['return_pct']:>+7.3f} {r['sharpe']:>+8.3f} "
              f"{r['mdd_pct']:>+7.3f} {r['n_roundtrips']:>5d} {r['win_rate_pct']:>6.1f} "
              f"{r['violations']:>5d}")

    print()
    print("=" * 115)
    print("BAR CORPUS (Binance, n=10) — IS + OOS + Full 3y (2023-01-01 .. 2025-12-31)")
    print("=" * 115)
    print(f"{'Strategy':<32} {'Sym':<7} "
          f"{'IS Ret%':>8} {'IS Shrp':>8} {'IS MDD%':>8} "
          f"{'OOS Ret%':>9} {'OOS Shrp':>9} {'OOS MDD%':>9} "
          f"{'Full Ret%':>10} {'Full MDD%':>10}")
    print("-" * 115)
    bar = bar_rows()
    for r in bar:
        sid = r["strategy_id"]
        print(f"{sid:<32} {r['symbol']:<7} "
              f"{r['is_return_pct']:>+8.2f} {r['is_sharpe']:>+8.3f} {r['is_mdd_pct']:>+8.2f} "
              f"{r['oos_return_pct']:>+9.2f} {r['oos_sharpe']:>+9.3f} {r['oos_mdd_pct']:>+9.2f} "
              f"{r['full_return_pct']:>+10.2f} {r['full_mdd_pct']:>+10.2f}")

    print()
    print("BAR CORPUS — meets 50%+ total-return threshold:")
    for r in bar:
        if r["full_return_pct"] >= 50.0:
            print(f"  ✓ {r['strategy_id']:<32} Full ret={r['full_return_pct']:+.1f}%  MDD={r['full_mdd_pct']:+.1f}%")
        elif r["is_return_pct"] >= 50.0:
            print(f"  ~ {r['strategy_id']:<32} (IS only) IS ret={r['is_return_pct']:+.1f}%  IS MDD={r['is_mdd_pct']:+.1f}%")

    out = {"tick": tick, "bar": bar}
    (REPO / "data" / "full_corpus_table.json").write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> data/full_corpus_table.json")


if __name__ == "__main__":
    main()
