#!/usr/bin/env python3
"""Auto-generate strategy.py + spec.yaml from a signal_brief_v2 entry.

Supports a small library of rule templates keyed on the feature name.
If the template does not cover a given feature, the script prints the
placeholder so a caller (Claude, an agent, or a human) can fill it in.

Usage:
    python scripts/gen_strategy_from_brief.py \\
        --brief data/signal_briefs_v2/crypto_1h.json \\
        --rank 0 --symbols BTCUSDT,ETHUSDT,SOLUSDT \\
        --market crypto_1h
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

import yaml

REPO = Path(__file__).resolve().parent.parent
STRAT_DIR = REPO / "strategies"

# Very small rule library keyed on feature-name prefix.
# Each returns (strategy_py_template, params_dict, paradigm, signals_list).
TEMPLATES = {
    "roc":              ("mean_reversion_on_roc",   "mean_reversion", "{feature}"),
    "zscore":           ("trend_follow_on_zscore",  "trend_follow",   "{feature}"),
    "taker_buy":        ("order_flow_persistence",  "order_flow",     "{feature}"),
    "hl_range":         ("range_filter",            "volatility",     "{feature}"),
    "lower_wick_rel":   ("wick_reversal",           "microstructure", "{feature}"),
    "upper_wick_rel":   ("wick_reversal",           "microstructure", "{feature}"),
    "rv":               ("realized_vol_filter",     "volatility",     "{feature}"),
    "bb_pos":           ("bb_extreme",              "mean_reversion", "{feature}"),
}


def _template(rule: str, feature: str, horizon: str) -> tuple[str, dict]:
    """Return (strategy_py_body, default_params_dict)."""
    if rule == "mean_reversion_on_roc":
        window = int(feature.split("_")[1].rstrip("h"))
        return dedent(f'''
            """Auto-generated: mean-reversion on {feature} (negative IC at {horizon}).

            Go long when past-{window}-bar return is below −roc_threshold.
            """
            from __future__ import annotations
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                roc_window: int = {window},
                                roc_threshold: float = 0.05,
                                **kwargs) -> pd.Series:
                roc = df["close"].pct_change(roc_window)
                return (roc < -roc_threshold).astype(int)
        ''').lstrip(), {"roc_window": window, "roc_threshold": 0.05}

    if rule == "trend_follow_on_zscore":
        window = int(feature.split("_")[1].rstrip("h"))
        return dedent(f'''
            """Auto-generated: trend-follow on {feature} (positive IC at {horizon})."""
            from __future__ import annotations
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                zscore_window: int = {window},
                                z_threshold: float = 1.0,
                                **kwargs) -> pd.Series:
                c = df["close"]
                m = c.rolling(zscore_window).mean()
                s = c.rolling(zscore_window).std()
                return ((c - m) / s > z_threshold).astype(int)
        ''').lstrip(), {"zscore_window": window, "z_threshold": 1.0}

    if rule == "order_flow_persistence":
        return dedent(f'''
            """Auto-generated: long when {feature} > threshold (positive IC at {horizon})."""
            from __future__ import annotations
            import numpy as np
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                short_window: int = 6,
                                long_window: int = 168,
                                persistence_threshold: float = 0.02,
                                **kwargs) -> pd.Series:
                v = df["volume"].values
                tb = df["taker_buy_base"].values
                tbr = pd.Series(tb / np.where(v > 0, v, 1))
                p = tbr.rolling(short_window).mean() - tbr.rolling(long_window).mean()
                return (p > persistence_threshold).astype(int)
        ''').lstrip(), {"short_window": 6, "long_window": 168,
                       "persistence_threshold": 0.02}

    if rule == "range_filter":
        # negative IC → small range predicts low returns, so long when range LARGE
        window = int(feature.split("_")[-1].rstrip("h"))
        return dedent(f'''
            """Auto-generated: long when {feature} above its 168h median (negative IC at {horizon})."""
            from __future__ import annotations
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                window: int = {window},
                                lookback_median: int = 168,
                                **kwargs) -> pd.Series:
                hl = (df["high"] - df["low"]) / df["close"]
                rng = hl.rolling(window).mean()
                med = rng.rolling(lookback_median).median()
                return (rng > med).astype(int)
        ''').lstrip(), {"window": window, "lookback_median": 168}

    if rule == "wick_reversal":
        return dedent(f'''
            """Auto-generated: long when {feature} is small (negative IC at {horizon})."""
            from __future__ import annotations
            import numpy as np
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                wick_quantile: float = 0.25,
                                lookback: int = 168,
                                **kwargs) -> pd.Series:
                o, c, h, l = df["open"], df["close"], df["high"], df["low"]
                cmax = c.clip(lower=1e-9)
                lower_wick = (pd.concat([o, c], axis=1).min(axis=1) - l) / cmax
                thresh = lower_wick.rolling(lookback).quantile(wick_quantile)
                return (lower_wick < thresh).astype(int)
        ''').lstrip(), {"wick_quantile": 0.25, "lookback": 168}

    if rule == "realized_vol_filter":
        return dedent(f'''
            """Auto-generated: long when realized vol is low (negative IC at {horizon})."""
            from __future__ import annotations
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                rv_window: int = 24,
                                pct_threshold: float = 0.25,
                                **kwargs) -> pd.Series:
                ret = df["close"].pct_change()
                rv = ret.rolling(rv_window).std()
                rank = rv.rolling(168).rank(pct=True)
                return (rank < pct_threshold).astype(int)
        ''').lstrip(), {"rv_window": 24, "pct_threshold": 0.25}

    if rule == "bb_extreme":
        return dedent(f'''
            """Auto-generated: long when price is at lower Bollinger (mean-revert)."""
            from __future__ import annotations
            import pandas as pd


            def generate_signal(df: pd.DataFrame,
                                window: int = 24,
                                k: float = 2.0,
                                **kwargs) -> pd.Series:
                c = df["close"]
                m = c.rolling(window).mean()
                s = c.rolling(window).std()
                lower = m - k * s
                return (c < lower).astype(int)
        ''').lstrip(), {"window": 24, "k": 2.0}

    raise ValueError(f"Unknown rule template: {rule}")


def pick_template(feature: str) -> tuple[str, str, str]:
    """Return (rule_name, paradigm, signals_label)."""
    for prefix, (rule, paradigm, sig_tmpl) in TEMPLATES.items():
        if feature.startswith(prefix):
            return rule, paradigm, sig_tmpl.format(feature=feature)
    raise ValueError(f"No template covers feature '{feature}'. Add to TEMPLATES.")


def emit(brief_path: Path, rank: int, symbols: list[str], market: str,
         fee_bps: float = 5.0, lot_size: int = 1,
         family_suffix: str | None = None) -> list[Path]:
    brief = json.loads(brief_path.read_text())
    if rank >= len(brief["top_robust"]):
        raise ValueError(f"rank {rank} out of range (top_robust has {len(brief['top_robust'])})")
    entry = brief["top_robust"][rank]
    feature = entry["feature"]
    horizon = entry["horizon"]
    rule, paradigm, sig_label = pick_template(feature)

    py_body, params = _template(rule, feature, horizon)
    params.update({"fee_side_bps": fee_bps, "lot_size": lot_size})

    family_name = family_suffix or rule
    out_paths = []
    for sym in symbols:
        sym_lo = sym.replace("USDT", "").lower()
        strat_id = f"{market}_{family_name}_{sym_lo}"
        d = STRAT_DIR / strat_id
        d.mkdir(parents=True, exist_ok=True)
        spec = {
            "name": strat_id,
            "kind": "python_bar_intraday",
            "target_horizon": market.split("_")[1],
            "target_symbol": sym,
            "paradigm": paradigm,
            "signals_needed": [sig_label],
            "params": dict(params),
            "origin": {
                "alpha_designer": "gen_strategy_from_brief.py",
                "signal_brief_v2_rank": rank,
                "signal_brief_v2_feature": feature,
                "signal_brief_v2_horizon": horizon,
                "signal_brief_v2_avg_ic": entry["avg_ic"],
                "rule_template": rule,
                "note": f"Auto-generated from signal_brief_v2 rank {rank} "
                        f"({feature} → {horizon}, avg IC={entry['avg_ic']:+.4f})",
            },
        }
        (d / "spec.yaml").write_text(yaml.dump(spec, sort_keys=False))
        (d / "strategy.py").write_text(py_body)
        out_paths.append(d)
        print(f"  wrote {d.relative_to(REPO)}/ (spec.yaml + strategy.py)")
    return out_paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--rank", type=int, default=0,
                    help="Which top_robust entry to turn into a strategy (0 = best)")
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--market", required=True,
                    help="e.g. crypto_1h — used for strategy-id prefix")
    ap.add_argument("--fee-bps", type=float, default=5.0)
    ap.add_argument("--lot", type=int, default=1)
    ap.add_argument("--family-name", default=None,
                    help="Override auto family name (default: rule template name)")
    args = ap.parse_args()

    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
    emit(Path(args.brief), args.rank, syms, args.market,
         fee_bps=args.fee_bps, lot_size=args.lot,
         family_suffix=args.family_name)


if __name__ == "__main__":
    main()
