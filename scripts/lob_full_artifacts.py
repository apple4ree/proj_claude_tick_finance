#!/usr/bin/env python3
"""α-2: LOB strategy post-processor.

Parallel to scripts/intraday_full_artifacts.py (bar) and bar_full_artifacts.py
(daily) for the crypto_lob market. Wraps engine.runner.run() and augments the
resulting roundtrips with Maximum Favorable/Adverse Excursion + capture_pct
so critics and designer agents can see give-back patterns.

engine.runner already produces:
    report.json   — metrics + roundtrips (entry_ts_ns, exit_ts_ns, pnl_bps, …)
    trace.json    — equity_curve, mid_series, fills
    report.html   — interactive Plotly dashboard

This script additionally writes:
    analysis_trace.json  — summary + enriched per-roundtrip MFE/MAE/capture_pct
    analysis_trace.md    — human-readable give-back summary for critics

Usage:
    python scripts/lob_full_artifacts.py --id <strategy_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow direct `python3 scripts/lob_full_artifacts.py ...` invocation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from engine.runner import run as run_engine

STRATEGIES_DIR = Path("strategies")


def _enrich_roundtrips_lob(
    roundtrips: list[dict],
    mid_series_per_sym: dict[str, list],
) -> None:
    """In-place MFE / MAE / capture_pct enrichment for LOB roundtrips.

    engine.runner schema (from engine.runner._compute_roundtrips_with_context):
        entry_ts_ns, exit_ts_ns, entry_price, exit_price, pnl_bps, outcome
    All trades are long-only (framework constraint).
    """
    if not roundtrips or not mid_series_per_sym:
        return

    sym_arrs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for sym, series in mid_series_per_sym.items():
        if not series:
            continue
        ts_arr = np.fromiter((int(s[0]) for s in series), dtype=np.int64, count=len(series))
        px_arr = np.fromiter((float(s[1]) for s in series), dtype=np.float64, count=len(series))
        sym_arrs[sym] = (ts_arr, px_arr)

    for r in roundtrips:
        sym = r.get("symbol")
        if sym not in sym_arrs:
            r["mfe_bps"] = r["mae_bps"] = r["capture_pct"] = None
            continue
        ts_arr, px_arr = sym_arrs[sym]
        try:
            b_ts = int(r["entry_ts_ns"])
            s_ts = int(r["exit_ts_ns"])
        except (KeyError, TypeError):
            r["mfe_bps"] = r["mae_bps"] = r["capture_pct"] = None
            continue
        lo = int(np.searchsorted(ts_arr, b_ts, side="left"))
        hi = int(np.searchsorted(ts_arr, s_ts, side="right"))
        if lo >= hi:
            r["mfe_bps"] = r["mae_bps"] = r["capture_pct"] = None
            continue
        window = px_arr[lo:hi]
        entry_px = float(r.get("entry_price") or 0.0)
        if entry_px <= 0:
            r["mfe_bps"] = r["mae_bps"] = r["capture_pct"] = None
            continue
        mfe = (float(window.max()) - entry_px) / entry_px * 1e4
        mae = (float(window.min()) - entry_px) / entry_px * 1e4
        r["mfe_bps"] = round(mfe, 2)
        r["mae_bps"] = round(mae, 2)
        r["capture_pct"] = (
            round(float(r.get("pnl_bps", 0.0)) / mfe * 100, 1) if mfe > 1e-6 else None
        )


def _compute_summary_lob(roundtrips: list[dict]) -> dict:
    if not roundtrips:
        return {"total_roundtrips": 0}
    wins = [r for r in roundtrips if r.get("outcome") == "WIN"]
    losses = [r for r in roundtrips if r.get("outcome") == "LOSS"]
    mfes = [r["mfe_bps"] for r in roundtrips if r.get("mfe_bps") is not None]
    maes = [r["mae_bps"] for r in roundtrips if r.get("mae_bps") is not None]
    caps = [r["capture_pct"] for r in roundtrips if r.get("capture_pct") is not None]
    give_back = [
        r for r in roundtrips
        if r.get("outcome") == "LOSS" and (r.get("mfe_bps") or 0) > 100
    ]
    pnl_bps_vals = [float(r.get("pnl_bps", 0.0)) for r in roundtrips]
    return {
        "total_roundtrips": len(roundtrips),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate_pct": round(100.0 * len(wins) / len(roundtrips), 2),
        "avg_pnl_bps": round(float(np.mean(pnl_bps_vals)), 2),
        "avg_mfe_bps": round(float(np.mean(mfes)), 2) if mfes else None,
        "avg_mae_bps": round(float(np.mean(maes)), 2) if maes else None,
        "avg_capture_pct": round(float(np.mean(caps)), 1) if caps else None,
        "n_give_back_trades": len(give_back),
        "sum_missed_profit_bps": (
            round(sum(float(r["mfe_bps"]) for r in give_back), 2) if give_back else 0.0
        ),
    }


def _write_md_lob(strat_id: str, roundtrips: list[dict], summary: dict, out: Path) -> None:
    lines: list[str] = [f"# {strat_id} — LOB analysis trace", ""]
    lines.append("## Give-Back Summary")
    if summary.get("total_roundtrips", 0) == 0:
        lines.append("No completed roundtrips.")
    else:
        lines += [
            f"- total_roundtrips: **{summary['total_roundtrips']}**",
            f"- win_rate_pct: {summary['win_rate_pct']}%",
            f"- avg_pnl_bps: {summary['avg_pnl_bps']}",
            f"- avg_mfe_bps: {summary.get('avg_mfe_bps')}",
            f"- avg_mae_bps: {summary.get('avg_mae_bps')}",
            f"- avg_capture_pct: {summary.get('avg_capture_pct')}%"
            + (" — **give-back risk**" if (summary.get("avg_capture_pct") or 100) < 50 else ""),
            f"- n_give_back_trades (LOSS with MFE > 100 bps): **{summary['n_give_back_trades']}**",
            f"- sum_missed_profit_bps: {summary['sum_missed_profit_bps']}",
        ]
    lines.append("")
    lines.append("## Per-Roundtrip")
    lines.append("| # | symbol | outcome | pnl_bps | mfe_bps | mae_bps | capture_pct | exit_tag |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(roundtrips):
        lines.append(
            f"| {i} | {r.get('symbol','?')} | {r.get('outcome','?')} | "
            f"{r.get('pnl_bps','?')} | {r.get('mfe_bps','?')} | "
            f"{r.get('mae_bps','?')} | {r.get('capture_pct','?')} | "
            f"{r.get('exit_tag','?')} |"
        )
    out.write_text("\n".join(lines) + "\n")


def run(strat_dir: Path) -> dict:
    spec_path = strat_dir / "spec.yaml"
    if not spec_path.exists():
        raise FileNotFoundError(f"spec.yaml missing at {spec_path}")

    payload = run_engine(spec_path, write_trace=True, write_html=True)

    trace_path = strat_dir / "trace.json"
    mid_series: dict[str, list] = {}
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text())
            mid_series = trace.get("mid_series") or {}
        except Exception:
            mid_series = {}

    roundtrips = payload.get("roundtrips") or []
    _enrich_roundtrips_lob(roundtrips, mid_series)
    summary = _compute_summary_lob(roundtrips)

    (strat_dir / "analysis_trace.json").write_text(json.dumps({
        "strategy_id": strat_dir.name,
        "trace_mode": "crypto_lob",
        "summary": summary,
        "roundtrips": roundtrips,
    }, indent=2, default=str))
    _write_md_lob(strat_dir.name, roundtrips, summary, strat_dir / "analysis_trace.md")

    # Refresh report.json so its roundtrips include the MFE/MAE/capture_pct
    payload["roundtrips"] = roundtrips
    (strat_dir / "report.json").write_text(json.dumps(payload, indent=2, default=str))

    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    args = ap.parse_args()
    d = STRATEGIES_DIR / args.id
    r = run(d)
    print(
        f"{args.id}: ret={r.get('return_pct', 0.0):+.2f}% "
        f"sharpe={r.get('sharpe_annualized', 0.0):+.2f} "
        f"MDD={r.get('mdd_pct', 0.0):+.2f}% "
        f"RT={r.get('n_roundtrips', 0)} fills={r.get('n_trades', 0)}"
    )


if __name__ == "__main__":
    main()
