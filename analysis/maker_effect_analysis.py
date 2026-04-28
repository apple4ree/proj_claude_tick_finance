"""Path B (maker spread capture) 효과의 메커니즘 분석.

분석 차원:
1. mid → maker amplification ratio (신호별)
2. Spread 의 신호별 분포 — \"언제 진입·청산하는가\" 의 시점이 다르면 spread 도 다름
3. v5 (mid only) vs v6 (maker mode) 의 LLM 디자인 패턴 비교
4. mean_dur 와 spread 의 상관 — 긴 보유 신호가 spread 잘 잡는지
5. Net (maker − fee) 분포 — fee floor 까지 거리
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
V5 = REPO_ROOT / "iterations_v5_archive_20260428"
V6 = REPO_ROOT / "iterations"
KRX_FEE_BPS = 23.0


def collect(root):
    rows = []
    if not root.exists():
        return rows
    for d in sorted(root.glob("iter_*/")):
        for f in d.glob("results/*.json"):
            try:
                r = json.load(open(f))
                spec_path = d / "specs" / f.name
                spec = json.load(open(spec_path)) if spec_path.exists() else {}
                rows.append({
                    "iter": int(d.name.split("_")[1]),
                    "spec_id": f.stem,
                    "mid": r.get("aggregate_expectancy_bps"),
                    "maker": r.get("aggregate_expectancy_maker_bps"),
                    "spread": r.get("aggregate_avg_spread_bps"),
                    "n": r.get("aggregate_n_trades") or 0,
                    "duty": r.get("aggregate_signal_duty_cycle") or 0,
                    "mean_dur": r.get("aggregate_mean_duration_ticks") or 0,
                    "exec_mode": r.get("execution_mode"),
                    "primitives": spec.get("primitives_used", []),
                    "formula": spec.get("formula", ""),
                    "hypothesis": spec.get("hypothesis", ""),
                })
            except Exception:
                pass
    return rows


def main():
    v5 = collect(V5)
    v6 = [r for r in collect(V6) if r["maker"] is not None]
    print(f"=== Path B (maker spread capture) 효과 분석 ===\n")
    print(f"v5: {len(v5)} specs (mid-only, no maker measurement)")
    print(f"v6: {len(v6)} specs with maker measurement\n")

    # === 1. Mid → Maker amplification 분포 (v6 only) ===
    print("=" * 78)
    print("[1] Mid → Maker amplification — Spread 회수가 어떻게 mid_gross 를 보강하는가")
    print("=" * 78)
    valid = [r for r in v6 if r["n"] >= 500 and r["mid"] is not None and r["mid"] != 0]
    if valid:
        amps = [(r["maker"] - r["mid"], r["spread"]) for r in valid]
        diff_mean = sum(a[0] for a in amps) / len(amps)
        spread_mean = sum(a[1] for a in amps) / len(amps)
        print(f"\n신호 수: {len(valid)}")
        print(f"평균 maker − mid : {diff_mean:+.2f} bps")
        print(f"평균 측정 spread  : {spread_mean:+.2f} bps")
        print(f"비율 (gain/spread): {diff_mean/spread_mean:.3f}  ← 1.0 에 가까우면 수식 일치")
        print()
        print("→ maker 모드 = mid + spread 의 수식적 일치 검증")
        print("  (long 진입 BID, 청산 ASK → 수익 측정에 spread 양쪽 합산)")

    # === 2. Spread 의 신호별 분포 — 진입 시점이 다르면 spread 도 다름 ===
    print()
    print("=" * 78)
    print("[2] Spread 의 신호별 분포 — \"언제 진입하는가\" 가 spread 에 미치는 영향")
    print("=" * 78)
    # v6 신호의 spread 분포
    if v6:
        spreads = sorted([r["spread"] for r in v6 if r["spread"] is not None and r["n"] >= 500])
        if spreads:
            n = len(spreads)
            print(f"\n신호별 측정 spread (n≥500 신호 {n}개):")
            print(f"  최소 (시장 안정 시 진입): {spreads[0]:.2f} bps")
            print(f"  25th percentile        : {spreads[int(0.25*n)]:.2f} bps")
            print(f"  중앙값                 : {spreads[n//2]:.2f} bps")
            print(f"  75th percentile        : {spreads[int(0.75*n)]:.2f} bps")
            print(f"  최대 (변동성 큰 시 진입): {spreads[-1]:.2f} bps")
            print()
            print("→ Spread 는 신호별 ±20% 변동. 신호가 활발한 시점 (high vol) 에 진입하면")
            print("  spread 도 크고 → maker capture 도 큼. 신호의 \"트리거 시점\" 이 spread 회수량을 결정.")

    # === 3. v5 (mid-only) vs v6 (maker) — LLM 의 신호 디자인 패턴 변화 ===
    print()
    print("=" * 78)
    print("[3] v5 vs v6 의 LLM 신호 디자인 패턴 차이")
    print("=" * 78)

    def compute_stats(rows, label):
        meaningful = [r for r in rows if r["n"] >= 500]
        if not meaningful:
            return None
        return {
            "label": label,
            "n_specs": len(meaningful),
            "mean_dur_avg": sum(r["mean_dur"] for r in meaningful) / len(meaningful),
            "mean_dur_max": max(r["mean_dur"] for r in meaningful),
            "duty_avg": sum(r["duty"] for r in meaningful) / len(meaningful),
            "long_horizon_specs": sum(1 for r in meaningful if r["mean_dur"] > 200),
            "short_horizon_specs": sum(1 for r in meaningful if r["mean_dur"] < 50),
        }

    v5_stats = compute_stats(v5, "v5 (mid only)")
    v6_stats = compute_stats(v6, "v6 (maker mode)")

    if v5_stats and v6_stats:
        print(f"\n{'':30} {'v5 (mid)':>15} {'v6 (maker)':>15}")
        print(f"{'n_specs (n≥500)':30} {v5_stats['n_specs']:>15} {v6_stats['n_specs']:>15}")
        print(f"{'평균 mean_dur (틱)':30} {v5_stats['mean_dur_avg']:>15.0f} {v6_stats['mean_dur_avg']:>15.0f}")
        print(f"{'최대 mean_dur (틱)':30} {v5_stats['mean_dur_max']:>15.0f} {v6_stats['mean_dur_max']:>15.0f}")
        print(f"{'평균 duty cycle':30} {v5_stats['duty_avg']:>15.3f} {v6_stats['duty_avg']:>15.3f}")
        print(f"{'mean_dur > 200 신호':30} {v5_stats['long_horizon_specs']:>15} {v6_stats['long_horizon_specs']:>15}")
        print(f"{'mean_dur < 50 신호':30} {v5_stats['short_horizon_specs']:>15} {v6_stats['short_horizon_specs']:>15}")

        ratio = (v6_stats['mean_dur_avg'] / v5_stats['mean_dur_avg']) if v5_stats['mean_dur_avg'] > 0 else 0
        print(f"\n→ v6 의 평균 mean_dur 가 v5 대비 {ratio:.2f}x")

        if v6_stats['long_horizon_specs'] > v5_stats['long_horizon_specs']:
            print(f"  v6 가 long-horizon 신호 더 많이 시도 ({v5_stats['long_horizon_specs']} → {v6_stats['long_horizon_specs']})")
            print(f"  → Path D (T-scaling 표) + Path B (maker mode) 의 결합 효과")

    # === 4. mean_dur 와 maker effect 의 상관 ===
    print()
    print("=" * 78)
    print("[4] mean_dur 와 maker effect 의 상관 — 긴 보유 신호가 spread 잘 잡는가?")
    print("=" * 78)
    if valid:
        # bucket by mean_dur
        buckets = {"<50": [], "50-200": [], "200-1000": [], ">=1000": []}
        for r in valid:
            md = r["mean_dur"]
            if md < 50: buckets["<50"].append(r)
            elif md < 200: buckets["50-200"].append(r)
            elif md < 1000: buckets["200-1000"].append(r)
            else: buckets[">=1000"].append(r)
        print(f"\n{'mean_dur bucket':18} {'n':>4} {'avg mid':>9} {'avg maker':>10} {'avg spread':>11} {'maker/mid 비':>13}")
        for b, rs in buckets.items():
            if not rs: continue
            mid_avg = sum(r["mid"] for r in rs) / len(rs)
            maker_avg = sum(r["maker"] for r in rs) / len(rs)
            spr_avg = sum(r["spread"] for r in rs) / len(rs)
            ratio = maker_avg / mid_avg if abs(mid_avg) > 0.1 else 0
            print(f"  {b:18} {len(rs):>4} {mid_avg:>9.2f} {maker_avg:>10.2f} {spr_avg:>11.2f} {ratio:>13.2f}")
        print()
        print("→ Mid_gross 의 magnitude 가 작을수록 maker/mid 비가 커짐 (spread 가 dominant 효과)")
        print("  Mid_gross 가 충분히 큰 (5+ bps) 신호에서만 maker 보강이 \"add-on\" 의미")

    # === 5. Net distribution — fee floor 까지 거리 ===
    print()
    print("=" * 78)
    print("[5] Net (maker − 23) 분포 — Fee 통과까지의 거리")
    print("=" * 78)
    if valid:
        nets = sorted([r["maker"] - KRX_FEE_BPS for r in valid], reverse=True)
        n = len(nets)
        deployable = sum(1 for x in nets if x > 0)
        marginal = sum(1 for x in nets if -5 <= x <= 0)
        print(f"\n신호 수: {n}")
        print(f"Net > 0 (deployable):       {deployable} 개")
        print(f"Net ∈ (-5, 0] (margin):     {marginal} 개")
        print(f"Top 5 net values: {[f'{x:+.2f}' for x in nets[:5]]} bps")
        print(f"Net 평균:                   {sum(nets)/len(nets):+.2f} bps")
        print(f"Net 최대 (best):            {nets[0]:+.2f} bps")
        print()
        if deployable > 0:
            print("⭐ DEPLOYABLE 신호 발견!")
        else:
            print(f"→ Best 신호도 fee floor 까지 {-nets[0]:.2f} bps 부족.")
            print(f"  Path B 단독으론 부족 — A/C/D 의 magnitude 보강 + 추가 lever 필요.")

    # === 6. Top 5 신호의 메커니즘 정성 분석 ===
    print()
    print("=" * 78)
    print("[6] Top 5 신호의 메커니즘 — Path B 가 어떻게 작용하는지")
    print("=" * 78)
    if valid:
        valid.sort(key=lambda x: -x["maker"])
        for i, r in enumerate(valid[:5], 1):
            print(f"\n#{i} {r['spec_id']}")
            print(f"   formula:   {r['formula']}")
            print(f"   mid={r['mid']:.2f} → maker={r['maker']:.2f} (+{r['maker']-r['mid']:.2f} from spread {r['spread']:.2f})")
            print(f"   n={r['n']}, duty={r['duty']:.2f}, mean_dur={r['mean_dur']:.0f} 틱")
            net = r["maker"] - KRX_FEE_BPS
            print(f"   net={net:+.2f}  ({'deployable' if net > 0 else 'capped post-fee'})")


if __name__ == "__main__":
    main()
