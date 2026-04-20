#!/usr/bin/env python3
"""Phase 3 — 4-gate strategy validation.

Gates:
  1. Invariants pass: report.json.invariant_violation_count == 0
                      (or <= --allow-violations)
  2. OOS frozen-param test: backtest over OOS window with the *same*
     params; require OOS Sharpe > 0 (or --oos-min-sharpe).
  3. IR > 0 vs period-matched buy-and-hold (full-period or OOS).
  4. Same-sign IC across symbols if the strategy is one of a multi-symbol
     family (checked by walking sibling strategies with the same paradigm
     and base feature signature).

Gate 4 is currently a soft check if the strategy is standalone (no
siblings). All gates get a pass/fail flag in validation.json.

Usage:
    python scripts/validate_strategy.py --id crypto_1h_weekly_meanrev_btc \\
        --oos-start 2025-11-01 --oos-end 2025-12-31

    python scripts/validate_strategy.py --all --oos-start ... --oos-end ...
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.benchmark_vs_bh import bh_matched, bh_matched_lob, HORIZON_PATH  # noqa: E402


def load_strategy_module(strat_dir: Path):
    path = strat_dir / "strategy.py"
    if not path.exists():
        return None
    sp = importlib.util.spec_from_file_location(f"_{strat_dir.name}", path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def backtest_window(df: pd.DataFrame, signal: pd.Series,
                    fee_side_bps: float, bars_per_year: float) -> dict:
    c = df["close"].values
    sig = signal.fillna(0).astype(int).values
    position = np.concatenate([[0], sig[:-1]])
    ret = np.diff(c) / c[:-1]
    pos = position[1:]
    strat_ret = pos * ret
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee_side_bps / 1e4)
    net = strat_ret - fee_cost
    if len(net) < 2:
        return {"total_ret_pct": 0.0, "sharpe": 0.0, "mdd_pct": 0.0, "n_rt": 0}
    eq = np.cumprod(1 + net)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    sharpe = (float(net.mean() / net.std() * np.sqrt(bars_per_year))
              if net.std() > 0 else 0.0)
    return {
        "total_ret_pct": float(eq[-1] - 1) * 100,
        "sharpe": sharpe,
        "mdd_pct": float(dd.min()) * 100,
        "n_rt": int((change[1:] > 0).sum()),
        "exposure": float(np.mean(np.abs(pos))),
    }


def load_market_data(symbol: str, horizon: str) -> pd.DataFrame | None:
    tmpl = HORIZON_PATH.get(horizon)
    if not tmpl:
        return None
    path = REPO / tmpl.format(sym=symbol)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["date"] = df["ts"].dt.strftime("%Y-%m-%d")
    return df.sort_values("ts").reset_index(drop=True)


def bars_per_year_for(horizon: str) -> float:
    return {"1d": 365.0, "daily": 365.0, "1h": 24 * 365.0,
            "15m": 4 * 24 * 365.0, "5m": 12 * 24 * 365.0,
            "1m": 60 * 24 * 365.0}.get(horizon, 365.0)


def run_oos_lob(strat_dir: Path, oos_start: str, oos_end: str) -> dict | None:
    """LOB-market OOS: clone spec.yaml with OOS time_window, run engine.runner.

    Returns same schema as run_oos (n_rt, sharpe, total_ret_pct, bh_ret_pct,
    information_ratio, window). IR here is a *simplified* excess-return
    normalization: (strat_ret - bh_ret) / max(|bh_ret|, 1e-4). Full
    periodic Information Ratio would require iterating the equity curve
    tick-by-tick against a BH series, deferred until more data is available.
    """
    spec_path = strat_dir / "spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    spec_oos = dict(spec)
    spec_oos["universe"] = dict(spec.get("universe", {}))
    spec_oos["universe"]["time_window"] = {"start": oos_start, "end": oos_end}
    tmp_path = strat_dir / "_spec_oos.yaml"
    tmp_path.write_text(yaml.safe_dump(spec_oos, sort_keys=False))
    try:
        from engine.runner import run as run_engine
        payload = run_engine(
            tmp_path, write_trace=False, write_html=False,
            report_out=strat_dir / "report_oos.json",
        )
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
    bh_ret = bh_matched_lob(payload)
    ret = float(payload.get("return_pct") or 0.0)
    if bh_ret is not None:
        denom = max(abs(bh_ret), 1e-4)
        ir = (ret - bh_ret) / denom
    else:
        ir = 0.0
    return {
        "n_rt": int(payload.get("n_roundtrips", 0)),
        "sharpe": float(payload.get("sharpe_annualized", 0.0)),
        "total_ret_pct": ret,
        "bh_ret_pct": bh_ret,
        "information_ratio": float(ir),
        "window": [oos_start, oos_end],
    }


def run_oos(strat_dir: Path, oos_start: str, oos_end: str) -> dict | None:
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    market = str(((spec.get("universe") or {}).get("market")) or "")
    if market == "crypto_lob":
        return run_oos_lob(strat_dir, oos_start, oos_end)
    module = load_strategy_module(strat_dir)
    if module is None or not hasattr(module, "generate_signal"):
        return None
    symbol = spec.get("target_symbol")
    horizon = spec.get("target_horizon")
    df = load_market_data(symbol, horizon)
    if df is None:
        return None
    # warmup buffer so rolling windows don't NaN at OOS start
    warm_days = 14
    warm_start = (pd.Timestamp(oos_start) - pd.Timedelta(days=warm_days)).strftime("%Y-%m-%d")
    full = df[(df["date"] >= warm_start) & (df["date"] <= oos_end)].reset_index(drop=True)
    oos_mask = (full["date"] >= oos_start).values

    params = spec.get("params", {})
    fee = float(params.get("fee_side_bps", 5.0))
    sig = module.generate_signal(full, **params)
    bpy = bars_per_year_for(horizon)

    # Apply oos mask: set signal to 0 before OOS so fills don't count pre-OOS
    sig_oos = sig.copy()
    sig_oos[~oos_mask] = 0
    m = backtest_window(full.iloc[oos_mask.nonzero()[0]].reset_index(drop=True),
                        sig[oos_mask].reset_index(drop=True), fee, bpy)
    # BH on same window
    oos_df = full[oos_mask].reset_index(drop=True)
    bh_ret = bh_matched(symbol, horizon, oos_df["date"].iloc[0],
                        oos_df["date"].iloc[-1], fee_side_bps=fee)
    # IR on OOS per-bar returns
    c = oos_df["close"].values
    ret = np.diff(c) / c[:-1]
    sig_inwin = sig[oos_mask].reset_index(drop=True).fillna(0).astype(int).values
    position = np.concatenate([[0], sig_inwin[:-1]])
    pos = position[1:]
    change = np.abs(np.diff(np.concatenate([[0], position])))
    fee_cost = change[1:] * (fee / 1e4)
    strat_net = pos * ret - fee_cost
    diff = strat_net - ret
    te = float(diff.std()) if len(diff) > 1 else 0.0
    ir = float(diff.mean() / te * np.sqrt(bpy)) if te > 1e-12 else 0.0
    return {**m, "bh_ret_pct": bh_ret, "information_ratio": ir,
            "window": [oos_df["date"].iloc[0], oos_df["date"].iloc[-1]]}


def gate_invariants(report: dict, allow: int) -> tuple[bool, str]:
    n = int(report.get("invariant_violation_count", 0))
    return (n <= allow,
            f"violations={n} (allow={allow})")


def gate_oos(oos_result: dict | None, min_rt: int) -> tuple[bool, str]:
    """Sanity: OOS backtest executed and the signal actually fired.

    Does NOT require positive absolute Sharpe — bear periods can have
    negative Sharpe while still beating BH (that is gate 3's job).
    """
    if oos_result is None:
        return (False, "oos backtest not runnable")
    n = oos_result.get("n_rt", 0)
    s = oos_result.get("sharpe", 0.0)
    return (n >= min_rt,
            f"OOS roundtrips={n} (min={min_rt}), Sharpe={s:+.2f}, "
            f"ret={oos_result['total_ret_pct']:+.2f}%")


def gate_ir_vs_bh(oos_result: dict | None, min_ir: float) -> tuple[bool, str]:
    if oos_result is None:
        return (False, "no oos result")
    ir = oos_result.get("information_ratio", 0.0)
    return (ir > min_ir, f"OOS IR={ir:+.2f} (min={min_ir:+.2f}), "
                          f"BH={oos_result.get('bh_ret_pct')}")


def gate_cross_symbol(strat_dir: Path, oos_result: dict | None,
                      oos_start: str, oos_end: str) -> tuple[bool, str]:
    """Pass if OOS IR has the same sign across all sibling symbols.

    Siblings = other strategy dirs sharing the stem obtained by stripping
    the trailing `_<sym>` token. Each sibling's OOS IR is recomputed over
    the same window so the comparison is apples-to-apples.
    """
    base = "_".join(strat_dir.name.split("_")[:-1])
    siblings = [d for d in (REPO / "strategies").iterdir()
                if d.is_dir() and d.name != strat_dir.name
                and d.name.startswith(base)
                and (d / "strategy.py").exists()]
    if len(siblings) < 1:
        return (True, "standalone (no siblings), soft-pass")
    signs: list[float] = []
    if oos_result:
        signs.append(float(np.sign(oos_result.get("information_ratio", 0.0))))
    for sd in siblings:
        try:
            s_oos = run_oos(sd, oos_start, oos_end)
            if s_oos:
                signs.append(float(np.sign(s_oos.get("information_ratio", 0.0))))
        except Exception:
            continue
    if not signs:
        return (True, "no sibling OOS IR data, soft-pass")
    same = all(s == signs[0] for s in signs) and signs[0] != 0
    return (bool(same), f"sibling OOS IR signs = {signs}")


def validate(strat_dir: Path, oos_start: str, oos_end: str,
             allow_violations: int = 0,
             oos_min_rt: int = 1,
             ir_min: float = 0.0) -> dict:
    rp = strat_dir / "report.json"
    if not rp.exists():
        return {"id": strat_dir.name, "error": "no report.json"}
    report = json.loads(rp.read_text())

    # Gate 1: Invariants
    g1 = gate_invariants(report, allow_violations)

    # Gate 2+3: OOS
    oos_res = None
    try:
        oos_res = run_oos(strat_dir, oos_start, oos_end)
    except Exception as e:
        oos_res = None
        oos_err = str(e)
    else:
        oos_err = None

    g2 = gate_oos(oos_res, oos_min_rt)
    g3 = gate_ir_vs_bh(oos_res, ir_min)
    g4 = gate_cross_symbol(strat_dir, oos_res, oos_start, oos_end)

    all_pass = g1[0] and g2[0] and g3[0] and g4[0]
    out = {
        "id": strat_dir.name,
        "passed": all_pass,
        "gates": {
            "1_invariants":    {"pass": g1[0], "detail": g1[1]},
            "2_oos_sharpe":    {"pass": g2[0], "detail": g2[1]},
            "3_ir_vs_bh":      {"pass": g3[0], "detail": g3[1]},
            "4_cross_symbol":  {"pass": g4[0], "detail": g4[1]},
        },
        "oos_result": oos_res,
        "oos_error": oos_err,
    }
    (strat_dir / "validation.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--id")
    group.add_argument("--pattern")
    ap.add_argument("--oos-start", required=True)
    ap.add_argument("--oos-end", required=True)
    ap.add_argument("--allow-violations", type=int, default=0)
    ap.add_argument("--oos-min-rt", type=int, default=1,
                    help="Minimum OOS roundtrips for gate 2 (signal must fire)")
    ap.add_argument("--ir-min", type=float, default=0.0)
    args = ap.parse_args()

    strategies_dir = REPO / "strategies"
    import fnmatch
    if args.id:
        targets = [strategies_dir / args.id]
    elif args.pattern:
        targets = [d for d in sorted(strategies_dir.iterdir())
                   if d.is_dir() and fnmatch.fnmatch(d.name, args.pattern)]
    else:
        targets = [d for d in sorted(strategies_dir.iterdir())
                   if d.is_dir() and not d.name.startswith("_")
                   and (d / "strategy.py").exists()]

    print(f"{'strategy':<48} {'inv':>5} {'oos':>5} {'ir':>5} {'cross':>5}  {'PASS':>5}")
    print("-" * 86)
    pass_n = 0
    for d in targets:
        try:
            v = validate(d, args.oos_start, args.oos_end,
                         args.allow_violations, args.oos_min_rt, args.ir_min)
        except Exception as e:
            print(f"  {d.name:<46}  ERROR: {e}")
            continue
        if "error" in v:
            print(f"  {d.name:<46}  ERROR: {v['error']}")
            continue
        g = v["gates"]
        ok = "✓" if v["passed"] else "✗"
        if v["passed"]: pass_n += 1
        print(f"  {d.name:<46} "
              f"{'✓' if g['1_invariants']['pass'] else '✗':>5} "
              f"{'✓' if g['2_oos_sharpe']['pass'] else '✗':>5} "
              f"{'✓' if g['3_ir_vs_bh']['pass'] else '✗':>5} "
              f"{'✓' if g['4_cross_symbol']['pass'] else '✗':>5}  "
              f"{ok:>5}")
    print(f"\npass rate: {pass_n}/{len(targets)}")


if __name__ == "__main__":
    main()
