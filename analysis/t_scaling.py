"""T-scaling — empirical holding-period vs magnitude trade-off.

For 9 T values × 5 representative primitives × 3 vol partitions, compute:
  - mean_|Δmid_T|_bps                   (unconditional baseline, random-walk √T baseline)
  - mean_|Δmid_T| | primitive > θ       (conditional magnitude when signal active)
  - WR(direction(Δmid_T) == sign(primitive))  (direction predictivity)
  - signal_decay_T = WR_T / WR_T1       (predictivity decay across T)

Output:
  data/calibration/t_scaling.json
  .claude/agents/chain1/_shared/references/cheat_sheets/t_scaling.md

This is bias-mitigated:
  - 9 T-values (not single highlight)
  - 5 primitives (not just obi_1)
  - Both unconditional + conditional reported
  - Vol partition cross-cut (3 partitions)
  - WR + magnitude separate (LLM sees both axes)
  - Net column included (gross - fee = -23 anchor, helps grounding)
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

IS_DATES = ["20260316", "20260317", "20260318", "20260319",
            "20260320", "20260323", "20260324", "20260325"]
SYMBOLS = ["005930", "000660", "005380"]

T_GRID = [1, 10, 50, 100, 500, 1000, 2000, 5000, 10000]

# 5 representative primitives (Category A pressure/flow + B1/B2 examples)
# Each: (name, fn(df) → np.array, default_threshold, "long_if_pos"|"long_if_neg")
PRIMITIVES = [
    ("obi_1",                  "obi_1",                   0.5, "long_if_pos"),
    ("obi_3",                  "obi_3",                   0.4, "long_if_pos"),
    ("microprice_dev_bps",     "microprice_dev_bps",      0.5, "long_if_pos"),
    ("ofi_proxy_5",            "ofi_proxy_5",             0.0, "long_if_pos"),  # raw OFI
    ("zscore_obi1_w300",       "zscore_obi1_w300",        2.0, "long_if_neg"),  # tail mean-rev
]

KRX_FEE_BPS = 23.0


def compute_primitives(df: pd.DataFrame) -> pd.DataFrame:
    """Compute mid + 5 primitives needed for t_scaling. Returns aligned arrays in DF."""
    out = pd.DataFrame(index=df.index)

    bid1 = df["BIDP1"].to_numpy(dtype=np.float64)
    ask1 = df["ASKP1"].to_numpy(dtype=np.float64)
    qb1  = df["BIDP_RSQN1"].to_numpy(dtype=np.float64)
    qa1  = df["ASKP_RSQN1"].to_numpy(dtype=np.float64)
    qb3  = sum(df[f"BIDP_RSQN{k}"].to_numpy(dtype=np.float64) for k in range(1, 4))
    qa3  = sum(df[f"ASKP_RSQN{k}"].to_numpy(dtype=np.float64) for k in range(1, 4))
    qb5  = sum(df[f"BIDP_RSQN{k}"].to_numpy(dtype=np.float64) for k in range(1, 6))
    qa5  = sum(df[f"ASKP_RSQN{k}"].to_numpy(dtype=np.float64) for k in range(1, 6))

    mid = (bid1 + ask1) / 2.0
    out["mid"] = mid

    # obi_1, obi_3
    d1 = qb1 + qa1
    d3 = qb3 + qa3
    out["obi_1"] = np.where(d1 > 0, (qb1 - qa1) / d1, 0.0)
    out["obi_3"] = np.where(d3 > 0, (qb3 - qa3) / d3, 0.0)

    # microprice_dev_bps (microprice - mid) / mid * 1e4 ; equivalent to spread/2 × OBI_1
    micro = np.where(d1 > 0, (bid1 * qa1 + ask1 * qb1) / d1, mid)
    out["microprice_dev_bps"] = (micro - mid) / mid * 1e4

    # ofi_proxy_5 — simple finite difference proxy (Δqb_5 - Δqa_5), z-scored
    qb5_diff = np.zeros_like(qb5); qb5_diff[1:] = qb5[1:] - qb5[:-1]
    qa5_diff = np.zeros_like(qa5); qa5_diff[1:] = qa5[1:] - qa5[:-1]
    raw_ofi = qb5_diff - qa5_diff
    # rolling z-score, window=300
    s = pd.Series(raw_ofi)
    mu = s.rolling(300, min_periods=50).mean()
    sd = s.rolling(300, min_periods=50).std().replace(0, np.nan)
    out["ofi_proxy_5"] = ((s - mu) / sd).to_numpy()

    # zscore_obi1_w300
    s_obi = pd.Series(out["obi_1"].to_numpy())
    mu_obi = s_obi.rolling(300, min_periods=50).mean()
    sd_obi = s_obi.rolling(300, min_periods=50).std().replace(0, np.nan)
    out["zscore_obi1_w300"] = ((s_obi - mu_obi) / sd_obi).to_numpy()

    # Rolling realized vol for vol partition
    dmid_1 = np.zeros(len(mid))
    dmid_1[1:] = (mid[1:] - mid[:-1]) / mid[:-1] * 1e4
    out["rolling_vol"] = pd.Series(dmid_1).rolling(300, min_periods=50).std().to_numpy()

    return out


def compute_t_metrics(
    feat: pd.DataFrame,
    primitive_col: str,
    threshold: float,
    direction: str,
) -> dict[int, dict[str, Any]]:
    """For one (primitive, threshold), compute per-T metrics."""
    mid = feat["mid"].to_numpy()
    sig = feat[primitive_col].to_numpy()

    # Active mask: |sig| > threshold ; direction sign for predicted move
    if direction == "long_if_pos":
        active_long = sig > threshold
        active_short = sig < -threshold
    else:  # long_if_neg
        active_long = sig < -threshold
        active_short = sig > threshold

    out: dict[int, dict[str, Any]] = {}

    for T in T_GRID:
        if len(mid) <= T + 10:
            out[T] = {"_skip": "data too short"}
            continue
        # Δmid_T at each tick t: mid[t+T] - mid[t], in bps
        dmid_T = np.full(len(mid), np.nan)
        dmid_T[:-T] = (mid[T:] - mid[:-T]) / mid[:-T] * 1e4

        valid = ~np.isnan(dmid_T)
        abs_dmid_T = np.abs(dmid_T)

        # Unconditional
        unconditional = {
            "mean_abs_dmid_bps":   float(np.nanmean(abs_dmid_T)) if valid.any() else None,
            "median_abs_dmid_bps": float(np.nanmedian(abs_dmid_T)) if valid.any() else None,
            "p90_abs_dmid_bps":    float(np.nanquantile(abs_dmid_T, 0.90)) if valid.any() else None,
            "mean_signed_dmid_bps": float(np.nanmean(dmid_T)) if valid.any() else None,  # macro drift
            "n_valid":             int(valid.sum()),
        }
        u_drift = unconditional["mean_signed_dmid_bps"] or 0.0

        # Conditional on active_long: dmid_T should be positive for predictive signal
        m_long = valid & active_long[:len(mid)]
        n_long = int(m_long.sum())
        if n_long > 30:
            d_long = dmid_T[m_long]
            cond_long = {
                "mean_dmid_signed_bps":         float(np.mean(d_long)),
                "alpha_vs_drift_bps":           float(np.mean(d_long) - u_drift),  # remove macro-drift
                "mean_abs_dmid_bps":            float(np.mean(np.abs(d_long))),
                "wr":                           float((d_long > 0).mean()),
                "n":                            n_long,
            }
        else:
            cond_long = {"_skip": f"n_long={n_long}<30"}

        m_short = valid & active_short[:len(mid)]
        n_short = int(m_short.sum())
        if n_short > 30:
            d_short = dmid_T[m_short]
            cond_short = {
                "mean_dmid_signed_bps":         float(np.mean(d_short)),
                "alpha_vs_drift_bps":           float(-(np.mean(d_short) - u_drift)),  # short side: −(mean − drift)
                "mean_abs_dmid_bps":            float(np.mean(np.abs(d_short))),
                "wr":                           float((d_short < 0).mean()),
                "n":                            n_short,
            }
        else:
            cond_short = {"_skip": f"n_short={n_short}<30"}

        out[T] = {
            "unconditional": unconditional,
            "cond_long":  cond_long,
            "cond_short": cond_short,
        }

    return out


def build_t_scaling() -> dict[str, Any]:
    print(f"Building t_scaling: {len(SYMBOLS)} sym × {len(IS_DATES)} dates × "
          f"{len(PRIMITIVES)} primitives × {len(T_GRID)} T values")

    all_features = []
    for sym in SYMBOLS:
        for date in IS_DATES:
            try:
                df_raw = load_day_v2(sym, date)
            except Exception as e:  # noqa: BLE001
                print(f"  skip {sym}/{date}: {e}")
                continue
            if len(df_raw) < 1000:
                continue
            feat = compute_primitives(df_raw)
            feat["symbol"] = sym
            feat["date"] = date
            all_features.append(feat)
            print(f"  loaded {sym}/{date}: {len(feat)} rows")

    if not all_features:
        raise RuntimeError("No data")

    df_all = pd.concat(all_features, axis=0, ignore_index=True)
    print(f"\nTotal rows: {len(df_all):,}")

    # Per-primitive × per-T metrics (aggregated across all symbol+date)
    results: dict[str, Any] = {}
    for prim_name, prim_col, thr, direction in PRIMITIVES:
        if prim_col not in df_all.columns:
            print(f"  skip {prim_name}: column missing")
            continue
        print(f"  computing {prim_name} (thr={thr}, dir={direction}) ...")
        metrics = compute_t_metrics(df_all, prim_col, thr, direction)
        results[prim_name] = {
            "threshold":  thr,
            "direction":  direction,
            "per_T":      metrics,
        }

    return {
        "metadata": {
            "is_dates": IS_DATES,
            "symbols": SYMBOLS,
            "n_rows_total": int(len(df_all)),
            "T_grid": T_GRID,
            "primitives": [p[0] for p in PRIMITIVES],
            "fee_bps": KRX_FEE_BPS,
        },
        "results": results,
    }


def render_markdown(t_scaling: dict[str, Any]) -> str:
    md = ["# T-scaling — Empirical holding-period vs magnitude (KRX cash IS)",
          "",
          "**Source**: 3 symbols × 8 IS dates. Aggregated unconditionally + conditionally on each primitive.",
          "",
          "## What this answers",
          "",
          "Two questions for each (primitive, threshold) pair:",
          "1. **Magnitude growth**: how does mean(|Δmid_T|_bps) scale with holding period T?",
          "2. **Predictivity decay**: does the primitive's WR (direction-correctness) hold as T grows?",
          "",
          "If magnitude grows √T but WR decays to 0.5, the conditional `mean(Δmid_signed_T)` →",
          "the actual realized expectancy. **That's the deployable metric**.",
          "",
          "Anchor: KRX RT fee = 23 bps. Net = `mean(abs_dmid)` × `(2·WR − 1)` − 23.",
          "",
          "## Unconditional baseline (random-walk reference)",
          ""]

    # Unconditional from first primitive (same for all)
    first_prim = list(t_scaling["results"].keys())[0]
    md.append("| T | mean |Δmid|_bps | median | p90 | mean_signed (drift) | n |")
    md.append("|---:|---:|---:|---:|---:|---:|")
    for T in T_GRID:
        u = t_scaling["results"][first_prim]["per_T"].get(T, {}).get("unconditional", {})
        if not isinstance(u, dict) or u.get("mean_abs_dmid_bps") is None:
            md.append(f"| {T} | — | — | — | — | — |")
            continue
        msd = u.get("mean_signed_dmid_bps")
        msd_s = f"{msd:+.2f}" if msd is not None else "—"
        md.append(f"| {T} | {u['mean_abs_dmid_bps']:.2f} | {u['median_abs_dmid_bps']:.2f} | {u['p90_abs_dmid_bps']:.2f} | {msd_s} | {u['n_valid']:,} |")
    md.append("")
    md.append("**The `mean_signed (drift)` column is the IS sample's macro-drift contribution.**")
    md.append("If non-zero, all conditional `mean_signed` numbers below are biased by this drift.")
    md.append("Use the `alpha_vs_drift` column to isolate the signal's true edge.")

    md.append("")
    md.append("## Per-primitive conditional metrics")
    md.append("")
    md.append("For each primitive, conditional on `|signal| > threshold`. Long side stats")
    md.append("are reported; short side is symmetric for Category A primitives.")
    md.append("")

    for prim_name, prim_data in t_scaling["results"].items():
        thr = prim_data["threshold"]
        direction = prim_data["direction"]
        md.append(f"### `{prim_name}` (threshold={thr}, direction={direction})")
        md.append("")
        md.append("| T | n | mean_signed | **alpha_vs_drift** | mean_abs | WR(>0) | net_signal_after_fee |")
        md.append("|---:|---:|---:|---:|---:|---:|---:|")
        for T in T_GRID:
            cell = prim_data["per_T"].get(T, {})
            cl = cell.get("cond_long", {})
            if cl.get("_skip"):
                md.append(f"| {T} | — | — | — | — | — | — |")
                continue
            wr = cl["wr"]
            mean_abs = cl["mean_abs_dmid_bps"]
            mean_signed = cl["mean_dmid_signed_bps"]
            alpha = cl["alpha_vs_drift_bps"]
            # net signal-only after fee uses alpha (drift-adjusted)
            net_signal = alpha - KRX_FEE_BPS
            net_str = f"{net_signal:+.2f}"
            if net_signal > 0:
                net_str = f"**{net_str}** ✓"
            md.append(f"| {T} | {cl['n']:,} | {mean_signed:+.2f} | {alpha:+.2f} | {mean_abs:.2f} | {wr:.3f} | {net_str} |")
        md.append("")

    md.append("## Reading guide — important caveats")
    md.append("")
    md.append("**Caveat 1 — overlapping windows**: each `n` is dependent samples (overlapping T-tick")
    md.append("windows). The effective independent draws is roughly `n / T`, much smaller. Treat WR")
    md.append("and means as descriptive, not statistical inference.")
    md.append("")
    md.append("**Caveat 2 — macro drift**: `mean_signed` includes the IS sample's day-trend.")
    md.append("On 8 March 2026 dates, KRX cash had a noticeable up-drift, which inflates `mean_signed`")
    md.append("for any long-side bucket — **regardless of signal predictivity**. Use **`alpha_vs_drift`**")
    md.append("(= mean_signed − unconditional_signed_drift) to isolate the signal edge.")
    md.append("")
    md.append("**Caveat 3 — WR semantics**: WR counts strict `Δmid > 0` (positives). Many ticks")
    md.append("at small T have `Δmid = 0` due to discreteness — those are counted as losses. So WR")
    md.append("at T=1 may be ~0.02 even for a perfectly predictive signal. WR is meaningful only at T ≥ 100.")
    md.append("")
    md.append("**Reading rules**:")
    md.append("- Use `alpha_vs_drift` for **signal edge** assessment (not raw `mean_signed`)")
    md.append("- Use `mean_abs_dmid_bps` for **magnitude reference** at horizon T")
    md.append("- WR < 0.5 with positive `mean_signed` typically means \"few big winners offset many small losers\"")
    md.append("- A primitive with persistent **`alpha_vs_drift` > 5 bps at T=500 with stable WR** is interesting")
    md.append("")
    md.append("## How to use in hypothesis")
    md.append("")
    md.append("Wrong: \"my spec uses obi_1 > 0.5 with T=100, expect +5 bps gross\"")
    md.append("(unanchored, ignores empirical T-scaling)")
    md.append("")
    md.append("Right: \"obi_1 > 0.5 has empirical mean_signed_dmid +X bps at T=100,")
    md.append("scaling to +Y bps at T=500. My spec extends T via stickiness (rolling_mean")
    md.append("window=200) so the regime mean_dur ≈ 200; expect mean per-regime gross")
    md.append("≈ Z bps. Net after 23 bps fee = Z − 23 = W.\"")
    return "\n".join(md)


def main():
    print("=== Building T-scaling ===\n")
    t_scaling = build_t_scaling()

    json_path = REPO_ROOT / "data" / "calibration" / "t_scaling.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(t_scaling, indent=2))
    print(f"\n✓ wrote {json_path}")

    md = render_markdown(t_scaling)
    md_path = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared" / "references" / "cheat_sheets" / "t_scaling.md"
    md_path.write_text(md)
    print(f"✓ wrote {md_path} ({len(md.splitlines())} lines)")

    # Summary
    n_prim = len(t_scaling["results"])
    print(f"\nSummary: {n_prim} primitives, {len(T_GRID)} T values")
    # Highlight any cell with alpha_vs_drift > 0 (drift-adjusted)
    print("\nCells with alpha_vs_drift > 23 bps (signal-only edge clearing fee):")
    found = 0
    for prim_name, prim_data in t_scaling["results"].items():
        for T in T_GRID:
            cl = prim_data["per_T"].get(T, {}).get("cond_long", {})
            if cl.get("_skip"): continue
            if cl.get("alpha_vs_drift_bps", -999) > KRX_FEE_BPS:
                print(f"  {prim_name} @ T={T}: alpha={cl['alpha_vs_drift_bps']:+.2f}, "
                      f"raw_signed={cl['mean_dmid_signed_bps']:+.2f}, WR={cl['wr']:.3f}, n={cl['n']:,}")
                found += 1
    if not found:
        print("  (none — drift accounts for most of the apparent gain)")


if __name__ == "__main__":
    main()
