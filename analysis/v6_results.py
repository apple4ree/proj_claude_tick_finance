"""v6 result aggregation + v5 comparison.

Run after v6 completion. Produces:
1. Per-iter best (mid + maker) trajectory
2. Top 10 specs (by maker gross) with diversity check
3. Anti-pattern occurrence (mean_dur < 5)
4. Hypothesis-vs-result divergence sample
5. v5 vs v6 head-to-head ablation
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
V5 = REPO_ROOT / "iterations_v5_archive_20260428"
V6 = REPO_ROOT / "iterations"
KRX_FEE_BPS = 23.0

KEYWORDS = {
    "duty":     re.compile(r"duty[\s_-]?(cycle)?", re.I),
    "mean_dur": re.compile(r"mean[\s_-]?(regime)?[\s_-]?duration|mean[\s_-]?dur", re.I),
    "category": re.compile(r"Category\s+(A|B1|B2|B3|C)", re.I),
    "axis":     re.compile(r"axis\s+(A|B|C)|magnitude\s+mechanism", re.I),
    "fee":      re.compile(r"\bfee\b|23\s?bps", re.I),
}


def collect(root: Path) -> list[dict]:
    rows = []
    if not root.exists():
        return rows
    for d in sorted(root.glob("iter_*/")):
        for r_path in d.glob("results/*.json"):
            try:
                r = json.load(open(r_path))
                spec_path = d / "specs" / r_path.name
                spec = json.load(open(spec_path)) if spec_path.exists() else {}
                iter_num = int(d.name.split("_")[1])
                rows.append({
                    "iter": iter_num,
                    "spec_id": r_path.stem,
                    "gross": r.get("aggregate_expectancy_bps"),
                    "maker": r.get("aggregate_expectancy_maker_bps"),
                    "spread": r.get("aggregate_avg_spread_bps"),
                    "n": r.get("aggregate_n_trades"),
                    "duty": r.get("aggregate_signal_duty_cycle"),
                    "mean_dur": r.get("aggregate_mean_duration_ticks"),
                    "exec_mode": r.get("execution_mode"),
                    "primitives": spec.get("primitives_used", []),
                    "formula": spec.get("formula", ""),
                    "hypothesis": spec.get("hypothesis", ""),
                    "references": spec.get("references", []),
                })
            except Exception as e:  # noqa: BLE001
                pass
    return rows


def family(prims: list[str]) -> str:
    p = set(prims)
    if any("ofi" in x for x in p): return "ofi"
    if any("microprice" in x for x in p): return "microprice"
    if any("trade_imb" in x for x in p): return "trade_imb"
    if any("zscore" in x or "extreme" in x for x in p): return "tail"
    if any("obi" in x for x in p): return "obi"
    return "other"


def per_iter_best(rows: list[dict], key: str) -> dict[int, float]:
    out = {}
    for r in rows:
        v = r.get(key)
        if v is None or (r.get("n") or 0) < 500: continue
        out[r["iter"]] = max(out.get(r["iter"], -99.0), v)
    return out


def main():
    v5 = collect(V5)
    v6 = collect(V6)
    print(f"=== v5 vs v6 ablation ===\n")
    print(f"v5: {len(v5)} specs across {len({r['iter'] for r in v5})} iterations")
    print(f"v6: {len(v6)} specs across {len({r['iter'] for r in v6})} iterations\n")

    # Per-iter best (mid_gross primary, maker if v6)
    print("=== Per-iter best (n≥500) ===")
    v5_best = per_iter_best(v5, "gross")
    # v6's primary aggregate_expectancy_bps == maker (since execution_mode=maker_optimistic)
    v6_best = per_iter_best(v6, "gross")
    v6_mid = per_iter_best(v6, "maker")  # placeholder if available
    iters = sorted(set(v5_best) | set(v6_best))
    print(f"{'iter':>4}  {'v5 mid':>7}  {'v6 maker':>9}")
    for i in iters:
        v5b = f"{v5_best.get(i, ''):.2f}" if i in v5_best else "—"
        v6b = f"{v6_best.get(i, ''):.2f}" if i in v6_best else "—"
        print(f"{i:>4}  {v5b:>7}  {v6b:>9}")

    # Overall best
    v5_max = max(v5_best.values()) if v5_best else 0
    v6_max = max(v6_best.values()) if v6_best else 0
    print(f"\nv5 best (mid):    {v5_max:.2f} bps")
    print(f"v6 best (maker):  {v6_max:.2f} bps  (fee floor 23 bps)")
    print(f"v6 net best:      {v6_max - KRX_FEE_BPS:+.2f} bps")

    # Top 10 v6
    print("\n=== Top 10 v6 specs (by maker gross, n≥500) ===")
    v6_meaningful = [r for r in v6 if (r.get("n") or 0) >= 500 and r.get("gross") is not None]
    v6_meaningful.sort(key=lambda x: -x["gross"])
    print(f"{'iter':>4} {'spec':35} {'maker':>7} {'mid?':>6} {'spread':>7} {'n':>6} {'duty':>5} {'mdur':>6} {'family':>10}")
    for r in v6_meaningful[:10]:
        net = r["gross"] - KRX_FEE_BPS
        marker = " ✓" if net > 0 else ""
        print(f"  {r['iter']:>2} {r['spec_id'][:35]:35} {r['gross']:>7.2f} "
              f"{(r.get('maker') or 0):>6.2f} {(r.get('spread') or 0):>7.2f} "
              f"{r['n']:>6} {(r.get('duty') or 0):>5.2f} {(r.get('mean_dur') or 0):>6.0f} "
              f"{family(r['primitives']):>10}{marker}")

    # Diversity (top 10 v6 family distribution)
    print("\n=== Top 10 v6 primitive family distribution ===")
    fams = Counter(family(r["primitives"]) for r in v6_meaningful[:10])
    for f, c in fams.most_common():
        print(f"  {f:>12}: {c}")
    print(f"  unique families: {len(fams)} (target ≥ 3)")

    # Anti-pattern: flickering (mean_dur < 5)
    flickers = [r for r in v6 if (r.get("mean_dur") or 0) > 0 and r.get("mean_dur", 999) < 5]
    print(f"\n=== Anti-patterns ===")
    print(f"  Flickering (mean_dur < 5):  {len(flickers)}/{len(v6)} ({100*len(flickers)/max(1,len(v6)):.1f}%)")
    print(f"  v5 baseline:                  ~25-40%, v6 target ≤ 10%")

    # Hypothesis template completeness
    def template_score(h: str) -> int:
        return sum(1 for rx in KEYWORDS.values() if rx.search(h or ""))
    template_complete = sum(1 for r in v6 if template_score(r["hypothesis"]) >= 4)
    print(f"\n=== Hypothesis template completeness ===")
    print(f"  v6 ≥4/5 keywords:     {template_complete}/{len(v6)} ({100*template_complete/max(1,len(v6)):.1f}%)")
    print(f"  target ≥ 75%")

    # Fee passing
    n_pass = sum(1 for r in v6 if (r.get("gross") or -999) > KRX_FEE_BPS)
    print(f"\n=== KEY METRIC ===")
    print(f"  v6 specs net > 0 (gross > 23 bps after maker capture): {n_pass}/{len(v6)}")
    if n_pass > 0:
        print("  ⭐ DEPLOYABLE SPEC FOUND ⭐")
    else:
        print("  (no deployable spec yet)")

    # Saturation iter (best-of-run)
    if v6_best:
        max_v = max(v6_best.values())
        sat_iter = min(i for i, v in v6_best.items() if v == max_v)
        print(f"\n=== Saturation ===")
        print(f"  v6 best-of-run reached at iter {sat_iter} (target ≥ 15)")
        print(f"  v5 saturated at iter 13")

    # Save raw data
    out = {
        "v5_n_specs": len(v5), "v6_n_specs": len(v6),
        "v5_best_per_iter": v5_best, "v6_best_per_iter": v6_best,
        "v5_max_mid": v5_max, "v6_max_maker": v6_max,
        "v6_net_best": v6_max - KRX_FEE_BPS,
        "v6_top10": [{"iter": r["iter"], "spec_id": r["spec_id"],
                      "maker": r["gross"], "n": r["n"], "duty": r["duty"],
                      "mean_dur": r["mean_dur"], "family": family(r["primitives"])}
                     for r in v6_meaningful[:10]],
        "v6_flicker_pct": 100*len(flickers)/max(1,len(v6)),
        "v6_template_pct": 100*template_complete/max(1,len(v6)),
        "v6_n_deployable": n_pass,
    }
    out_path = REPO_ROOT / "analysis" / "v6_results_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n✓ summary saved to {out_path}")


if __name__ == "__main__":
    main()
