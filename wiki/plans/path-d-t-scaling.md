---
schema_version: 1
type: plan
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, signal-generator, holding-period, empirical-data, post-v5]
refs:
  code: []
  papers: []
  concepts:
    - holding-period-extension
    - fee-binding-constraint
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-D-t-scaling
status: proposed
trigger: post-v5-completion
priority: medium
---

# Path D — Empirical T-scaling (holding vs magnitude trade-off)

## 문제

Random-walk 가정 하에서 σ(Δmid_T) ≈ σ_per_tick × √T. 즉 holding 길게 = magnitude ↑. 그러나:
- T → ∞ 면 fee 1회 가 amortize 되지만 signal predictivity → 0
- T → 1 이면 predictivity 보존되나 magnitude 작아 fee 못 깸

**최적 T 의 sweet spot 이 어디?**: KRX 005930 의 경우 T ≈ 5000 ticks (~8 min) 부터 mean magnitude ≈ 30 bps 도달 — fee 23 bps 통과 가능. 그러나 그 T 에서 signal predictivity 가 살아있는지는 별개 문제.

LLM 이 horizon (regime-state 의 mean_dur) 을 정할 때 이 trade-off 를 **empirical 로** 보고 결정하게 만들기.

## 제안 design

**D.1 Holding period grid (9 values)**:
```
T_ticks ∈ {1, 10, 50, 100, 500, 1000, 2000, 5000, 10000}
         (100ms~17min)
```

**D.2 Per-T metric (4)**:
- `mean_|Δmid_T|_bps` — unconditional magnitude (random-walk baseline)
- `mean_|Δmid_T| | OBI_t > 0.5_bps` — OBI-conditioned magnitude (signal correct case)
- `WR(direction(Δmid_T) == sign(OBI_t))` — direction WR
- `signal_decay_T` = WR / WR_T=1 — signal predictivity 의 T-decay ratio

**D.3 Per-symbol × per-vol-regime decomposition** — Path C 의 vol partition 재사용:
- 9 T × 3 vol = 27 cells × 4 metrics = 108 data points
- low vol 에서는 T 길수록 √T 효과 약함, high vol 에서는 √T 가 잘 보임 등의 차이가 나타남

**D.4 Sweet-spot 시각화** — cheat sheet 안에 표 + ASCII chart:
```
T_ticks      mean_|Δ|  WR    signal_decay   net (after 23bps fee)
     1        0.5      0.78    1.00          -22.5
    50        3.0      0.74    0.95          -20.0
   500       10.0      0.65    0.83          -13.0
  5000       30.0      0.58    0.74           +7.0   ⭐
 10000       42.0      0.55    0.71          +19.0
```

**D.5 Decay vs magnitude 곡선** — 같은 데이터를 (T, expectancy_per_RT_bps) 로 plot 한 ASCII chart 도 cheat sheet 에 inline.

**D.6 LLM 가이드**: "regime-state 에서 mean_dur 을 design 할 때 이 표 참조. duty × magnitude × predictivity 의 trade-off 를 직접 결정."

**D.7 Implementation** — `analysis/t_scaling.py` (NEW):
- 입력: KRX CSV
- 출력: `chain1/_shared/references/cheat_sheets/t_scaling.md`
- bonus: `data/calibration/t_scaling.json` (Path E tool 이 query 가능)

## 구현 단계

```
D.1  T grid + per-T metric 계산 코드             (2h)
D.2  vol partition 결합 (Path C 재사용)          (1h)
D.3  per-symbol aggregation                      (1h)
D.4  cheat sheet markdown + ASCII chart          (1h)
D.5  signal-generator AGENTS.md 에 reference    (15 min)
D.6  smoke test: 1 iter, mean_dur distribution   (30 min)
─────
total ~5h
```

## 성공 기준

1. **Diversity**: smoke test 4 candidates 의 mean_dur 분포가 single value 가 아닌 다양함 (예: 50 / 200 / 1000 / 5000 ticks).
2. **Predictivity-aware**: hypothesis 에 "T 길수록 magnitude ↑ 그러나 signal decay" 키워드 등장 ≥ 2/4.
3. **Anchored**: spec 의 expected gross 가 D.4 표의 해당 T-cell 값 ±30% 범위 내.

## 의존성 / ordering

- **선행**: v5 종료 + Path C (vol partition 공통)
- **권장 순서**: A → C → D → B → E
- **무관**: Path B 와 직교

## 위험 / blocker

1. **OBI != signal**: D.2 의 conditional magnitude 가 OBI 기반인데, LLM 의 spec 은 다른 primitive 일 수 있음. — Mitigation: 5~10 개 primitive (OBI, OFI, microprice, trade_imb 등) 를 모두 측정해서 multi-primitive 표.
2. **signal_decay 의 noise**: T=10000 에서는 한 day 에 표본 수가 적음 → WR 추정 noise 큼. — Mitigation: 8 dates 통합 + bootstrap CI.
3. **regime-state 와 fixed-H 의 mismatch**: 우리 backtest 는 regime-state, T-scaling 은 fixed-T. → "이 표는 baseline reference, 실제 backtest 는 regime-state" 라고 cheat sheet 에 명시.

## 예상 영향

- LLM 의 mean_dur design 이 evidence-based 로 — 현재 무작위 (LLM 이 임의로 50 vs 500 vs 5000 선택)
- "fee 통과를 위해서는 T ≥ 5000 ticks 필요" 같은 mechanical insight 를 LLM 이 internalize
- Path B 의 maker spread capture 와 결합 시 net = (T-scaled magnitude) + spread - fee 의 직접 expectation 가능

## 미정 사항

- T grid: log-spaced (1,10,100,1000,10000) vs linear (1,1000,2000,...,10000) — log 권장
- WR base 가 매우 어려운 메트릭 (regime-state 는 WR 정의 다름) — fixed-T 가정으로만 표시할지 결정
- KRX 매도세 0.20% 가 long position 의 net 을 한쪽에 cap → "+19 bps" 같은 큰 net 은 short side 만 가능 — 표에 반영 필요
