---
date: 2026-04-27 03:00
tone: design
title: Block F — magnitude primitives + cheat sheets
---

## Context
v4 결정 트리가 magnitude-seeking 행동(change_horizon, extreme_quantile, add_regime_filter)을 추천하지만 이를 표현할 명시적 primitive 부재. 시간대 regime burst flag, Parkinson high-low range 등 magnitude regime을 직접 표현할 도구가 없음. P0+P2만 즉시 추가 (Option A), P1은 v4 종료 후로 미룸 — clean ablation 보전.

## Done
- chain1/primitives.py에 3 boolean primitive 추가:
  - is_opening_burst (KRX 09:00–09:30)
  - is_lunch_lull (11:30–13:00)
  - is_closing_burst (14:30–15:30)
- RollingRangeBps stateful helper class 추가 (Parkinson high-low range in bps)
- chain1/code_generator.py: STATEFUL_HELPERS에 rolling_range_bps 등록
- PRIMITIVE_WHITELIST 확장 36 → 39
- 신규 cheat sheet 2개:
  - magnitude_primitives.md (3-axis framework: A horizon × B regime × C tail, hypothesis 텍스트 템플릿 강제)
  - time_of_day_regimes.md (KRX 시간대별 |Δmid| 측정치, 합성 recipe, anti-pattern 경고)
- formula_validity_rules.md whitelist 단락 갱신 (Block C–F 모두 명시)
- 3개 합성 spec(boolean primitive / rolling helper / axis A×B×C)으로 codegen end-to-end 검증

## Numbers
- 신규 primitive: 3
- 신규 stateful helper: 1
- 신규 cheat sheet: 2
- 총 primitive: 36 → 39
- 총 stateful helper: 8 → 9
- v4 영향 범위: iter_005+ LLM call이 새 cheat sheet 봄 (자연 partition 발생)

## Next
- v4 후반(iter 5–24)에서 새 primitive 사용 spec 등장 여부 측정
- v4 완료 후 P1 추가 (Kyle λ proxy, mid_returns_ar1 + Garman-Klass/Andersen-Bollerslev/Amihud paper) → v5 launch
- v3 vs v4(early) vs v4(late) vs v5 4-way ablation 가능
