---
date: 2026-04-27 02:45
tone: result
title: v4 iter 0–3 — tighten 8→0, expectancy 키워드 0→13
---

## Context
v4 진행 1시간 33분 시점(iter_004 backtest 단계, 5/25 iter 완료). v3와 동일 표본(iter 0–3, 16 spec 제안 / 10 백테스트)으로 ablation 분석.

## Done
- Recommendation 분포 비교 (v3 14건 vs v4 10건)
- Spec horizon 분포 비교
- Hypothesis text 키워드 빈도 분석 (fee/expectancy/magnitude/WR)
- Result distribution (mean/max expectancy_bps, WR, net@23bps)
- Mutation axes 사용 빈도 비교

## Numbers
- tighten_threshold: v3 8/14 (57%) → v4 **0/10 (0%)** ⭐ 가장 큰 단일 변화
- add_regime_filter: 0 → 3, change_horizon: 2 → 3, extreme_quantile: 0 → 1
- mean horizon: 26.3 → **38.4 ticks (+46%)**
- 101–500 ticks 범위 spec: 0 → 1 (iter004_obi_shape_modulated_long_h, h=150)
- hypothesis 키워드 'fee/bps/cost': 4 → 10 (2.5×)
- hypothesis 키워드 'expectancy/edge': 0 → **13** (신규 등장)
- mean expectancy_bps: 4.13 → 5.66 (+37%)
- max expectancy_bps: 7.44 → **12.85 (+73%)**
- max net @23bps: -15.56 → **-10.15 (+5.4 bps, fee 벽에 더 근접)**
- WR mean: 0.730 → 0.755 (+0.025)
- WR max: 0.938 → 0.922 (-0.016) — magnitude 추구 trade-off

## Next
- v4 끝까지 실행 대기 (예상 ~6시간)
- 완료 시 v3 vs v4 정량 ablation 마무리
- Block F primitive + cheat sheet 추가 결정
