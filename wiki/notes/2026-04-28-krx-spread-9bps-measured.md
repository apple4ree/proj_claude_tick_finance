---
schema_version: 1
type: free
created: '2026-04-28'
updated: '2026-04-28'
tags: [microstructure, spread, krx, finding]
refs:
  code:
    - {path: "analysis/maker_smoke.py", confidence: verified}
  papers: []
  concepts:
    - maker-spread-capture
    - fee-binding-constraint
  experiments:
    - exp-2026-04-28-fresh-v6-paths-A-B-C-D
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# KRX cash 의 평균 spread = 9.2 bps (예상 5-7 bps 보다 큼)

## 노트

Path B (maker spread capture) smoke 에서 발견한 empirical 사실.

### 측정

3 syms (005930, 000660, 005380) × 8 IS dates (2026-03-16~25), regime-state backtest 의 entry/exit tick 시점 (ASK − BID) / mid × 1e4:

| spec (regime entry/exit 시점) | avg_spread_bps |
|---|---:|
| iter013_opening_burst_conviction | 9.25 |
| iter016_stable_pressure_on_fragile_book | 9.84 |
| iter009_stable_imbalance_vs_fragile_book | 9.87 |
| iter000_full_book_consensus | 8.70 |
| iter020_magnitude_consensus_at_open | 8.38 |

→ 평균 **9.21 bps**, 표준편차 ~0.7 bps.

### 가정 vs 실측

- **가정 (CLAUDE.md, plan-b-maker-spread-capture)**: KRX cash 평균 spread ~5 bps
- **실측**: 9.2 bps (1.8x 큼)

### 가능한 원인

1. **종목 구성**: 005930 (대형, ~9-10만원), 000660 (~10만원), 005380 (~25만원) — 가격대가 spread/price 비율을 키움.
2. **Tick size 기여**: 005930 / 000660 가격대에서 tick size = 100원 → bps 환산 spread ≈ (100/100000) × 1e4 = 10 bps. 5380 가격대 250원 / 250000 ≈ 10 bps. 즉 **tick discreteness 가 spread 의 lower bound**.
3. **Regime 시점 bias**: regime entry/exit 가 활발한 (high vol) 시점에 모이면, 그 시점의 spread 가 일평균보다 클 수 있음. 그러나 spec 별 차이가 작아 (8.4 ~ 9.9), big 차이는 아님.

### 함의

1. **Maker capture 가 9 bps 만큼 mid-gross 를 보강** — 이전 가정 (5 bps) 의 약 2배.
2. **Fee floor in maker mode = 23 - 9 = 14 bps mid-gross**. v5 best (4.74) 와 9.3 bps 거리.
3. **Spread 는 magnitude axis C 의 source 로도 작동**: spread 큰 시점이 곧 magnitude 큰 시점 (book thinning).
4. **Tick discreteness 가 spread 하한** → KRX 005930 등 대형주에서는 spread 가 (다른 maker ECN 대비) 비교적 안정.

### Future check

- 작은 종목 (예: 가격 < 5만원) 에서는 spread 가 더 클 수 있음 — top-10 univ 확장 시 측정 필요.
- OOS dates (2026-04-01~) 에서 spread 분포 변동 측정 — drift 가 v6 의 Path D alpha_vs_drift 보정에도 영향.

## 링크

- `maker-spread-capture` — concept
- `analysis/maker_smoke.py` — measurement code
- `analysis/maker_smoke_results.json` — raw data
