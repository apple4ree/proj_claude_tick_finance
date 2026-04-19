#!/usr/bin/env python3
"""Expand bar-level corpus from 5 to 10 by applying existing strategies to
different symbols and parameter variants.

Base: bar_s1..s5 in strategies_bar/

New additions (5):
- bar_s6 = S2's BB reversion applied to SOLUSDT (symbol transfer)
- bar_s7 = S2's BB reversion applied to ETHUSDT (symbol transfer)
- bar_s8 = S1's trend+regime with looser vol_spike threshold (param sweep)
- bar_s9 = S3's breakout applied to BTCUSDT (symbol transfer)
- bar_s10 = S4's vol-compress applied to ETHUSDT (symbol transfer)
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BAR_DIR = REPO / "strategies_bar"

sys.path.insert(0, str(REPO))
from scripts.bar_baselines import load_daily, split_is_oos, backtest


# (new_id, base_id, target_symbol, param_overrides)
NEW_STRATEGIES = [
    ("bar_s6_sol_bb_reversion",    "bar_s2_btc_bb_reversion",      "SOLUSDT", {}),
    ("bar_s7_eth_bb_reversion",    "bar_s2_btc_bb_reversion",      "ETHUSDT", {}),
    ("bar_s8_sol_vol_mom_loose",   "bar_s1_sol_vol_momentum",      "SOLUSDT",
                                                                   {"vol_spike_threshold": 1.0}),
    ("bar_s9_btc_vol_breakout",    "bar_s3_eth_vol_breakout",      "BTCUSDT", {}),
    ("bar_s10_eth_vol_compress",   "bar_s4_sol_vol_compress",      "ETHUSDT", {}),
]


def build(new_id: str, base_id: str, target_symbol: str, overrides: dict) -> str:
    base_dir = BAR_DIR / base_id
    new_dir = BAR_DIR / new_id
    if new_dir.exists():
        print(f"  already exists: {new_id}")
        return new_id
    new_dir.mkdir(parents=True, exist_ok=True)

    spec = yaml.safe_load((base_dir / "spec.yaml").read_text())
    spec["name"] = new_id
    spec["target_symbol"] = target_symbol
    spec["params"] = {**spec.get("params", {}), **overrides}
    spec.setdefault("origin", {})["parent_variant_of"] = base_id
    (new_dir / "spec.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
    shutil.copy(base_dir / "strategy.py", new_dir / "strategy.py")
    print(f"  built: {new_id} (base={base_id}, symbol={target_symbol}, overrides={overrides})")
    return new_id


def run(strat_id: str) -> dict:
    strat_dir = BAR_DIR / strat_id
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    symbol = spec["target_symbol"]
    params = spec.get("params", {})
    fee = float(params.get("fee_side_bps", 5.0))

    sp = importlib.util.spec_from_file_location("ls", strat_dir / "strategy.py")
    module = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(module)

    df = load_daily(symbol)
    is_df, oos_df = split_is_oos(df)

    is_sig = module.generate_signal(is_df, **params)
    oos_sig = module.generate_signal(oos_df, **params)
    m_is = backtest(is_df, is_sig, fee_side_bps=fee)
    m_oos = backtest(oos_df, oos_sig, fee_side_bps=fee)

    return {
        "strategy_id": strat_id,
        "symbol": symbol,
        "is_sharpe": m_is["sharpe_annualized"],
        "is_return_pct": m_is["total_return_pct"],
        "is_n_trades": m_is["n_trades"],
        "oos_sharpe": m_oos["sharpe_annualized"],
        "oos_return_pct": m_oos["total_return_pct"],
        "oos_n_trades": m_oos["n_trades"],
    }


def main() -> None:
    print(f"Building {len(NEW_STRATEGIES)} bar variants...\n")
    built = []
    for new_id, base_id, sym, over in NEW_STRATEGIES:
        nid = build(new_id, base_id, sym, over)
        if nid:
            built.append(nid)

    print(f"\n=== Running backtests ===")
    print(f"{'Strategy':<34} {'Symbol':<9} {'IS Shrp':>8} {'IS Ret%':>9} "
          f"{'OOS Shrp':>9} {'OOS Ret%':>10}")
    print("-" * 80)
    results = []
    for sid in built:
        r = run(sid)
        print(f"{r['strategy_id']:<34} {r['symbol']:<9} "
              f"{r['is_sharpe']:>+8.3f} {r['is_return_pct']:>+9.2f} "
              f"{r['oos_sharpe']:>+9.3f} {r['oos_return_pct']:>+10.2f}")
        results.append(r)

    out = REPO / "data" / "bar_corpus_expansion_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nsaved -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
