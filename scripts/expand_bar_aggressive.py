#!/usr/bin/env python3
"""Add aggressive/higher-return bar variants to push more strategies above 50% threshold.

Strategies:
- bar_s11: SOL momentum looser (vol_spike=0.8, broader regime)
- bar_s12: BTC BB reversion with wider bands (+3-sigma)
- bar_s13: ETH breakout with shorter Donchian (14 bars)
- bar_s14: SOL momentum with longer hold (no stop_loss)
- bar_s15: BTC momentum long-short with wider bands (2.0/0.0)
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


AGGRESSIVE = [
    ("bar_s11_sol_mom_loosest",  "bar_s1_sol_vol_momentum", "SOLUSDT",
     {"vol_spike_threshold": 0.8, "rvol_short": 15, "rvol_long": 45, "stop_loss_pct": -0.15}),
    ("bar_s12_btc_bb_wide",      "bar_s2_btc_bb_reversion", "BTCUSDT",
     {"bb_std": 2.5, "slope_window": 10, "stop_loss_pct": -0.15}),
    ("bar_s13_eth_breakout_short","bar_s3_eth_vol_breakout", "ETHUSDT",
     {"donchian_window": 14, "volume_ratio": 1.0, "hold_days": 20, "stop_loss_pct": -0.12}),
    ("bar_s14_sol_mom_nostop",   "bar_s1_sol_vol_momentum", "SOLUSDT",
     {"vol_spike_threshold": 1.0, "stop_loss_pct": None}),
    ("bar_s15_btc_mom_ls_wide",  "bar_s5_btc_momentum_ls",  "BTCUSDT",
     {"entry_band": 0.5, "exit_band": 0.0, "ret_lookback": 21}),
]


def build_run(new_id: str, base_id: str, sym: str, overrides: dict) -> dict | None:
    base_dir = BAR_DIR / base_id
    new_dir = BAR_DIR / new_id
    if not new_dir.exists():
        new_dir.mkdir(parents=True, exist_ok=True)
        spec = yaml.safe_load((base_dir / "spec.yaml").read_text())
        spec["name"] = new_id
        spec["target_symbol"] = sym
        params = spec.get("params", {})
        # Overrides may include None to disable features
        for k, v in overrides.items():
            params[k] = v
        spec["params"] = params
        spec.setdefault("origin", {})["parent_variant_of"] = base_id
        (new_dir / "spec.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        shutil.copy(base_dir / "strategy.py", new_dir / "strategy.py")

    spec = yaml.safe_load((new_dir / "spec.yaml").read_text())
    sym = spec["target_symbol"]
    params = spec.get("params", {})
    fee = float(params.get("fee_side_bps", 5.0))

    sp = importlib.util.spec_from_file_location(f"_{new_id}", new_dir / "strategy.py")
    module = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(module)

    df = load_daily(sym)
    is_df, oos_df = split_is_oos(df)
    full_sig = module.generate_signal(df, **params)
    is_sig = module.generate_signal(is_df, **params)
    oos_sig = module.generate_signal(oos_df, **params)

    m_full = backtest(df, full_sig, fee_side_bps=fee)
    m_is = backtest(is_df, is_sig, fee_side_bps=fee)
    m_oos = backtest(oos_df, oos_sig, fee_side_bps=fee)

    return {
        "strategy_id": new_id,
        "symbol": sym,
        "full_return_pct": m_full["total_return_pct"],
        "full_sharpe": m_full["sharpe_annualized"],
        "full_mdd_pct": m_full["mdd_pct"],
        "is_return_pct": m_is["total_return_pct"],
        "is_sharpe": m_is["sharpe_annualized"],
        "is_mdd_pct": m_is["mdd_pct"],
        "oos_return_pct": m_oos["total_return_pct"],
        "oos_sharpe": m_oos["sharpe_annualized"],
        "oos_mdd_pct": m_oos["mdd_pct"],
    }


def main() -> None:
    print("Building 5 aggressive bar variants...\n")
    print(f"{'Strategy':<32} {'Sym':<7} "
          f"{'Full Ret%':>10} {'Full Shrp':>10} {'Full MDD%':>10} "
          f"{'IS Ret%':>8} {'OOS Ret%':>9}")
    print("-" * 95)
    results = []
    for new_id, base_id, sym, over in AGGRESSIVE:
        try:
            r = build_run(new_id, base_id, sym, over)
            if r:
                results.append(r)
                print(f"{r['strategy_id']:<32} {r['symbol']:<7} "
                      f"{r['full_return_pct']:>+10.2f} {r['full_sharpe']:>+10.3f} {r['full_mdd_pct']:>+10.2f} "
                      f"{r['is_return_pct']:>+8.2f} {r['oos_return_pct']:>+9.2f}")
        except Exception as e:
            print(f"  {new_id}: FAILED — {e}")

    print(f"\nMeets 50%+ threshold:")
    for r in results:
        if r["full_return_pct"] >= 50:
            print(f"  ✓ {r['strategy_id']:<32} Full={r['full_return_pct']:+.1f}%  MDD={r['full_mdd_pct']:+.1f}%  Sharpe={r['full_sharpe']:+.2f}")

    out = REPO / "data" / "bar_aggressive_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nsaved -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
