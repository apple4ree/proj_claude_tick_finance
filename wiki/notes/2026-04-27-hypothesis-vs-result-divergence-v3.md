---
schema_version: 1
type: other
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code: []
  papers: []
  concepts: []
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
---

# hypothesis-vs-result-divergence-v3

## 노트
v3 80 spec / 100 spec proposed에 대해 LLM hypothesis와 측정 결과의 divergence 정밀 분석. Paper-target(spec-implementation fidelity in LLM-generated domain code)에 직결.

## (1) Reject 단계 — LLM 자기-여과 정확도
100 spec 제안 → 20 reject (eval/fidelity gate, 20%) → 80 backtest. 주된 reject 사유: primitive whitelist 위반(microprice_velocity, velocity_momentum 등 명세에 없는 이름 사용).

## (2) Direction 예측 정확도
long_if_pos: 39 spec 중 37/39 (95%) WR > 0.5, avg WR 0.861. long_if_neg(contra): 41 spec 중 39/41 (95%) WR > 0.5, avg WR 0.718. → 95% 방향성 적중. contra가 평균 WR 더 낮은 건 reversion이 본질적으로 더 어렵기 때문.

## (3) Theoretical Category 인용 정확도
Category A(BBO 압력): n=40, WR>0.5 38/40 (95%), avg 0.853. Category B1(resistance wall): n=23, 23/23 (100%), 0.809. Category B2(flow exhaustion): n=16, 16/16 (100%), 0.727. **Category B3(depth ratio reversal): n=6, 4/6 (67%), avg 0.430**. Category C(spread context): n=3, 3/3, 0.920. → B3만 cite-but-fail 패턴 — 표준 카테고리(A/B1/B2/C)는 정확하나 변형/조합 카테고리는 부정확.

## (4) Mutation 정확도 (parent → child, n=63 pair)
mutation이 expectancy 개선: 36/63 (57%). WR 개선: 31/63 (49%). 양쪽 다 개선: 30/63 (48%). mean Δ expectancy +0.11 bps (std 3.19), mean Δ WR -0.0066. → 사실상 random walk.

Mutation type별:
- threshold tightening (n=17): WR 14/17 (82%) 개선 — mechanically valid (selection bias로 자연스러움).
- drop_feature/isolate (n=21): expectancy 12/21 (57%) 개선 — LLM 판단력 필요한 mutation은 동전 던지기.

## (5) Phase별 개선력
early(iter 0–7) 20 pair: 70% 개선, mean Δ +0.406. mid(8–15) 21: 52% 개선, -0.180. late(16–24) 22: 50% 개선, +0.129. → 초반 개선력 후 saturation 도달, late phase는 random walk에 수렴.

## (6) 정성 가설 검증 — low-vol regime
rolling_realized_vol filter 적용 spec(n=8) mean exp 9.15 / mean WR 0.934 vs 미적용(n=72) mean exp 5.42 / mean WR 0.772. Δ exp +3.73 bps. → 'low-vol → cleaner' 가설 confirm.

## (7) 정량 claim 함유율
50/100 spec hypothesis에 정량 claim('WR > N%', 'expectancy ≥ N bps') 포함. fee 명시 spec은 한 자릿수.

## Paper-grade findings
1. LLM은 표준 microstructure category를 95% 정확도로 적용하나, 합성 카테고리(B3)에서는 cite-but-fail.
2. Mutation 개선력은 초반 70% → 후반 50%로 감소 — saturation 후 random walk.
3. Mechanical mutation(threshold tighten 82%) ≠ Judgmental mutation(drop_feature 57%) — 후자는 동전 던지기.
4. 정량 claim 50% / fee 명시 거의 0 — verifiability 결함.
5. Reward function = optimization target. WR을 reward로 쓰면 expectancy는 압축 안 됨 — Fix #1의 motivation.

## 데이터 출처
iterations_v3_archive/iter_*/specs/*.json (100 spec). iterations_v3_archive/iter_*/results/*.json (80 backtest). iterations_v3_archive/iter_*/feedback/*.json (80 feedback).

## 링크
exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date (raw data 출처). dec-objective-from-wr-to-net-pnl (본 분석이 motivation 제공한 결정). exp-2026-04-27-fresh-v4-fix1-net-pnl-objective (Fix #1의 효과 측정 실험).
