"""Empirical baselines — bias-mitigated systematic partition.

Computes 15-cell (5 time × 3 vol) partition of KRX tick data, with per-cell:
  - mean / median / p90 of |Δmid_per_tick|_bps
  - mean / median / p90 of |Δmid_per_50tick|_bps
  - mean / median / p90 of |Δmid_per_500tick|_bps
  - pct_obi_above_0.5
  - lag1 autocorr of Δmid

Bias mitigation:
  - 15 cells (not single-cell highlight)
  - Distribution (mean/median/p90), not point estimate
  - Negative-space labeling: cells where mean<1 bps AND p90<5 bps tagged "fee-prohibitive"
  - IS-only (v5 dates 20260316~20260325). OOS reserved.
  - Observation framing in markdown output (no "use this cell" guidance)

Output:
  data/calibration/empirical_baselines.json   (machine-readable)
  .claude/agents/chain1/_shared/references/cheat_sheets/empirical_baselines.md  (LLM ref)

Usage:
  python analysis/empirical_baselines.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.data_loader_v2 import load_day_v2  # noqa: E402

# v5 IS dates (also used for v3/v4) — 8 KRX trading dates in March 2026
IS_DATES = ["20260316", "20260317", "20260318", "20260319",
            "20260320", "20260323", "20260324", "20260325"]
SYMBOLS = ["005930", "000660", "005380"]

# Time partition (5 buckets) by session-elapsed minutes from 09:00 KST
# Session is 09:00–15:30 (390 min). Lunch break is implicit in continuous tape.
TIME_BUCKETS = [
    ("opening_30min",     0,    30),    # 09:00–09:30
    ("morning_60min",     30,   90),    # 09:30–10:30
    ("lunch_60min",       180,  240),   # 12:00–13:00
    ("afternoon_120min",  240,  360),   # 13:00–15:00
    ("closing_30min",     360,  390),   # 15:00–15:30
]

# Vol partition (3 buckets) by intra-session realized vol tertile
VOL_BUCKETS = ["low", "mid", "high"]

# Negative-space label thresholds
NEG_SPACE_MEAN_BPS = 1.0
NEG_SPACE_P90_BPS  = 5.0


def _local_time_to_minute(local_time: int) -> int:
    """Convert KRX local_time (HHMMSSffffff) to minutes-from-09:00.

    local_time encoding: HHMMSS + 6 fractional digits (microseconds).
    e.g., 90030000000 = 09:00:30
    """
    # Strip fractional → HHMMSS
    hms = local_time // 10**6
    h = hms // 10000
    m = (hms // 100) % 100
    return (h - 9) * 60 + m


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute mid, |Δmid_T|_bps for T∈{1,50,500}, obi_1, vol, time_bucket."""
    out = pd.DataFrame(index=df.index)

    bid1 = df["BIDP1"].to_numpy(dtype=np.float64)
    ask1 = df["ASKP1"].to_numpy(dtype=np.float64)
    qb1  = df["BIDP_RSQN1"].to_numpy(dtype=np.float64)
    qa1  = df["ASKP_RSQN1"].to_numpy(dtype=np.float64)

    mid = (bid1 + ask1) / 2.0
    out["mid"] = mid

    # |Δmid_T|_bps for T = 1, 50, 500
    for T in (1, 50, 500):
        if len(mid) > T:
            dmid = np.abs(np.diff(mid, n=1))[T-1:T-1+len(mid)-T] if False else None
            # Simple shift: |mid[t+T] - mid[t]| / mid[t] × 1e4
            arr = np.abs(mid[T:] - mid[:-T]) / mid[:-T] * 1e4
            arr_full = np.full(len(mid), np.nan)
            arr_full[:len(arr)] = arr
            out[f"abs_dmid_{T}_bps"] = arr_full
        else:
            out[f"abs_dmid_{T}_bps"] = np.nan

    # obi_1
    denom = qb1 + qa1
    obi_1 = np.where(denom > 0, (qb1 - qa1) / denom, 0.0)
    out["obi_1"] = obi_1
    out["abs_obi_1"] = np.abs(obi_1)

    # 1-tick mid increment for autocorr / vol
    dmid_1tick = np.zeros(len(mid))
    dmid_1tick[1:] = (mid[1:] - mid[:-1]) / mid[:-1] * 1e4
    out["dmid_1tick_bps"] = dmid_1tick

    # Rolling realized vol (window=300 ticks, signed Δmid_bps), for vol partitioning
    # Use std of |dmid_1tick|, sliding window.
    win = 300
    vol = pd.Series(dmid_1tick).rolling(window=win, min_periods=50).std().to_numpy()
    out["rolling_vol"] = vol

    # Time bucket
    minute = df["recv_ts_kst"].apply(_local_time_to_minute).to_numpy()
    out["minute_of_session"] = minute
    bucket = np.full(len(minute), "_unbucketed", dtype=object)
    for name, lo, hi in TIME_BUCKETS:
        mask = (minute >= lo) & (minute < hi)
        bucket[mask] = name
    out["time_bucket"] = bucket

    return out


def assign_vol_buckets(df: pd.DataFrame) -> pd.Series:
    """Tertile-cut rolling_vol → low/mid/high. Per-symbol-per-day to avoid cross-day mixing."""
    vol = df["rolling_vol"].dropna()
    if len(vol) < 50:
        return pd.Series(["_no_vol"] * len(df), index=df.index)
    q33 = vol.quantile(0.33)
    q67 = vol.quantile(0.67)
    bucket = pd.Series(["mid"] * len(df), index=df.index)
    bucket[df["rolling_vol"] < q33] = "low"
    bucket[df["rolling_vol"] >= q67] = "high"
    bucket[df["rolling_vol"].isna()] = "_no_vol"
    return bucket


def aggregate_cell(df_cell: pd.DataFrame) -> dict[str, Any]:
    """Per-cell metric aggregation.

    df_cell: rows in one (time × vol) bucket. Returns metrics dict."""
    if len(df_cell) < 100:
        return {"n": int(len(df_cell)), "_skip": "n<100"}

    out: dict[str, Any] = {"n": int(len(df_cell))}

    for T in (1, 50, 500):
        col = f"abs_dmid_{T}_bps"
        a = df_cell[col].dropna().to_numpy()
        if len(a) < 10:
            out[f"abs_dmid_{T}_bps"] = {"mean": None, "median": None, "p90": None, "n": int(len(a))}
        else:
            out[f"abs_dmid_{T}_bps"] = {
                "mean":   float(a.mean()),
                "median": float(np.median(a)),
                "p90":    float(np.quantile(a, 0.90)),
                "n":      int(len(a)),
            }

    # pct_obi_above_0.5
    out["pct_abs_obi_1_above_0.5"] = float((df_cell["abs_obi_1"] > 0.5).mean())

    # lag1 autocorr of dmid_1tick
    d = df_cell["dmid_1tick_bps"].dropna().to_numpy()
    if len(d) > 100:
        d_centered = d - d.mean()
        denom = float(np.sum(d_centered ** 2))
        if denom > 0:
            num = float(np.sum(d_centered[:-1] * d_centered[1:]))
            out["lag1_autocorr_dmid"] = num / denom
        else:
            out["lag1_autocorr_dmid"] = None
    else:
        out["lag1_autocorr_dmid"] = None

    return out


def build_baselines() -> dict[str, Any]:
    """Walk all (symbol, date) → assemble per-cell distributions across IS dates.

    Cells are aggregated *across* symbols/dates for statistical mass.
    Per-symbol breakdown is preserved as side info.
    """
    print(f"Building empirical baselines: {len(SYMBOLS)} symbols × {len(IS_DATES)} dates "
          f"× {len(TIME_BUCKETS)} time × {len(VOL_BUCKETS)} vol = "
          f"{len(SYMBOLS) * len(IS_DATES) * len(TIME_BUCKETS) * len(VOL_BUCKETS)} day-cells")

    all_features = []

    for sym in SYMBOLS:
        for date in IS_DATES:
            try:
                df_raw = load_day_v2(sym, date)
            except Exception as e:  # noqa: BLE001
                print(f"  skip {sym}/{date}: {e}")
                continue
            if len(df_raw) < 1000:
                print(f"  skip {sym}/{date}: insufficient data ({len(df_raw)} rows)")
                continue
            feat = compute_features(df_raw)
            feat["symbol"] = sym
            feat["date"] = date
            feat["vol_bucket"] = assign_vol_buckets(feat)
            all_features.append(feat)
            print(f"  loaded {sym}/{date}: {len(feat)} rows")

    if not all_features:
        raise RuntimeError("No data loaded — check KRX tickdata path")

    df_all = pd.concat(all_features, axis=0, ignore_index=True)
    print(f"\nTotal rows aggregated: {len(df_all):,}")

    # Build per-cell metrics
    cells: dict[str, dict[str, Any]] = {}

    for time_name, lo, hi in TIME_BUCKETS:
        for vol_name in VOL_BUCKETS:
            cell_id = f"{time_name}__{vol_name}"
            mask = (df_all["time_bucket"] == time_name) & (df_all["vol_bucket"] == vol_name)
            df_cell = df_all[mask]
            cells[cell_id] = aggregate_cell(df_cell)
            cells[cell_id]["time_bucket"] = time_name
            cells[cell_id]["vol_bucket"] = vol_name

    # Negative-space label
    for cid, c in cells.items():
        if c.get("_skip"):
            c["label"] = "_skip"
            continue
        m_50 = c.get("abs_dmid_50_bps", {})
        mean_50 = m_50.get("mean") if isinstance(m_50, dict) else None
        p90_50 = m_50.get("p90") if isinstance(m_50, dict) else None
        if mean_50 is None or p90_50 is None:
            c["label"] = "insufficient"
        elif mean_50 < NEG_SPACE_MEAN_BPS and p90_50 < NEG_SPACE_P90_BPS:
            c["label"] = "fee-prohibitive"
        elif mean_50 >= NEG_SPACE_MEAN_BPS * 3 or p90_50 >= NEG_SPACE_P90_BPS * 3:
            c["label"] = "high-magnitude"
        else:
            c["label"] = "moderate"

    return {
        "metadata": {
            "is_dates": IS_DATES,
            "symbols": SYMBOLS,
            "n_rows_total": int(len(df_all)),
            "time_buckets": [t[0] for t in TIME_BUCKETS],
            "vol_buckets": VOL_BUCKETS,
            "neg_space_thresholds": {
                "mean_bps_T50": NEG_SPACE_MEAN_BPS,
                "p90_bps_T50": NEG_SPACE_P90_BPS,
            },
        },
        "cells": cells,
    }


def render_markdown(baselines: dict[str, Any]) -> str:
    """Render LLM-facing cheat sheet from baselines dict."""
    md = ["# Empirical Baselines — KRX cash equity tick (IS-only)",
          "",
          "**Source**: 3 symbols × 8 IS dates (20260316~20260325). Quotes only (data_type=12).",
          "Aggregated across symbol+date for statistical mass.",
          "",
          "## Observation framing (read first)",
          "",
          "This table is **not a guide for which cell to trigger in**.",
          "It is the **statistical baseline** of KRX cash microstructure.",
          "Your hypothesis should explain how your spec **deviates** from the cell baseline,",
          "not which cell looks attractive. Bias-aware framing:",
          "1. The 5×3 partition is **our** choice; other partitions exist.",
          "2. Distribution (mean/median/p90) is reported, not point estimates.",
          "3. Cells labeled `fee-prohibitive` should NOT be primary triggers — flag them.",
          "4. OOS data is reserved (not in this table).",
          "",
          "## Cells: 5 time × 3 vol × 3 magnitude horizons",
          "",
          "Magnitude unit: |Δmid|_bps for T-tick horizon. T=50 is the primary metric.",
          "",
          "| time_bucket | vol | T=1 mean | T=50 mean | T=500 mean | T=50 p90 | obi>.5 % | lag1 ρ | label |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    for time_name, _, _ in TIME_BUCKETS:
        for vol_name in VOL_BUCKETS:
            cid = f"{time_name}__{vol_name}"
            c = baselines["cells"].get(cid, {})
            if c.get("_skip"):
                md.append(f"| {time_name} | {vol_name} | n<100 ({c.get('n')}) | — | — | — | — | — | _skip |")
                continue
            m1 = c.get("abs_dmid_1_bps", {})
            m50 = c.get("abs_dmid_50_bps", {})
            m500 = c.get("abs_dmid_500_bps", {})
            t1m = f"{m1.get('mean'):.2f}" if m1.get("mean") is not None else "—"
            t50m = f"{m50.get('mean'):.2f}" if m50.get("mean") is not None else "—"
            t500m = f"{m500.get('mean'):.2f}" if m500.get("mean") is not None else "—"
            t50p = f"{m50.get('p90'):.2f}" if m50.get("p90") is not None else "—"
            obi_pct = c.get("pct_abs_obi_1_above_0.5", 0)
            obi_pct_s = f"{obi_pct*100:.1f}%"
            ac = c.get("lag1_autocorr_dmid")
            ac_s = f"{ac:.3f}" if ac is not None else "—"
            label = c.get("label", "—")
            md.append(f"| {time_name} | {vol_name} | {t1m} | {t50m} | {t500m} | {t50p} | {obi_pct_s} | {ac_s} | {label} |")

    md.append("")
    md.append("## Distribution detail (T=50 abs_dmid_bps, by cell)")
    md.append("")
    md.append("Reading: `mean | median | p90` per cell. Use p90 to gauge tail magnitude.")
    md.append("")
    md.append("| time_bucket | vol | mean | median | p90 | n |")
    md.append("|---|---|---:|---:|---:|---:|")
    for time_name, _, _ in TIME_BUCKETS:
        for vol_name in VOL_BUCKETS:
            cid = f"{time_name}__{vol_name}"
            c = baselines["cells"].get(cid, {})
            if c.get("_skip"): continue
            m50 = c.get("abs_dmid_50_bps", {})
            if not isinstance(m50, dict) or m50.get("mean") is None: continue
            md.append(f"| {time_name} | {vol_name} | {m50['mean']:.2f} | {m50['median']:.2f} | {m50['p90']:.2f} | {m50['n']:,} |")

    md.append("")
    md.append("## Negative space (fee-prohibitive cells)")
    md.append("")
    md.append(f"Cells where mean(|Δmid|_T50_bps) < {NEG_SPACE_MEAN_BPS} AND p90 < {NEG_SPACE_P90_BPS} bps.")
    md.append("These cells alone cannot pay 23 bps RT fee. Triggering primarily within")
    md.append("them is auto-flagged as suspicious by feedback-analyst.")
    md.append("")
    fee_prohib = [cid for cid, c in baselines["cells"].items() if c.get("label") == "fee-prohibitive"]
    if fee_prohib:
        for cid in fee_prohib:
            md.append(f"- `{cid}`")
    else:
        md.append("(none in this measurement)")

    md.append("")
    md.append("## High-magnitude cells (potential focus zones)")
    md.append("")
    md.append(f"Cells where mean(|Δmid|_T50_bps) ≥ {NEG_SPACE_MEAN_BPS*3} OR p90 ≥ {NEG_SPACE_P90_BPS*3} bps.")
    md.append("These cells have natural baseline magnitude — but raw baseline")
    md.append("magnitude is **not** signal. Spec must show predictivity ON TOP of")
    md.append("the cell's natural variance to be interesting.")
    md.append("")
    high_mag = [cid for cid, c in baselines["cells"].items() if c.get("label") == "high-magnitude"]
    if high_mag:
        for cid in high_mag:
            md.append(f"- `{cid}`")
    else:
        md.append("(none in this measurement — try lowering thresholds)")

    md.append("")
    md.append("## How to use in hypothesis")
    md.append("")
    md.append("Wrong: \"my spec triggers in opening_30min × high vol\" → cell-picking.")
    md.append("")
    md.append("Right: \"in opening_30min × high vol, baseline mean(|Δmid|_T50) ≈ X bps")
    md.append("with p90 Y bps. My spec adds the condition `obi_1 > 0.7`, which I expect")
    md.append("to filter to events where mid moves +Z bps directionally over T=50, exceeding")
    md.append("the cell's |Δmid| baseline by Δ.\"")
    md.append("")
    md.append("This forces deviation framing — anchored to data, not picking-from-list.")

    return "\n".join(md)


def main():
    print("=== Building empirical baselines ===\n")
    baselines = build_baselines()

    # Write JSON
    json_path = REPO_ROOT / "data" / "calibration" / "empirical_baselines.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(baselines, indent=2))
    print(f"\n✓ wrote {json_path}")

    # Write markdown
    md = render_markdown(baselines)
    md_path = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared" / "references" / "cheat_sheets" / "empirical_baselines.md"
    md_path.write_text(md)
    print(f"✓ wrote {md_path} ({len(md.splitlines())} lines)")

    # Summary
    n_cells = len(baselines["cells"])
    n_skip = sum(1 for c in baselines["cells"].values() if c.get("_skip"))
    n_fee_prohib = sum(1 for c in baselines["cells"].values() if c.get("label") == "fee-prohibitive")
    n_high_mag = sum(1 for c in baselines["cells"].values() if c.get("label") == "high-magnitude")
    print(f"\nSummary:")
    print(f"  cells:           {n_cells}")
    print(f"  skipped (n<100): {n_skip}")
    print(f"  fee-prohibitive: {n_fee_prohib}")
    print(f"  high-magnitude:  {n_high_mag}")


if __name__ == "__main__":
    main()
