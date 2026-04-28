---
schema_version: 1
type: decision
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code:
  - path: chain1/primitives.py
    symbol: is_opening_burst
    confidence: inferred
  - path: chain1/primitives.py
    symbol: is_lunch_lull
    confidence: inferred
  - path: chain1/primitives.py
    symbol: is_closing_burst
    confidence: inferred
  - path: chain1/primitives.py
    symbol: RollingRangeBps
    confidence: inferred
  - path: chain1/code_generator.py
    symbol: STATEFUL_HELPERS
    confidence: inferred
  - path: chain1/primitives.py
    symbol: PRIMITIVE_WHITELIST
    confidence: verified
  papers: []
  concepts: []
  experiments:
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
decision_id: DEC-2026-04-27-block-f-magnitude-primitives
status: proposed
supersedes: []
superseded_by: []
scope:
- chain1.primitives
- chain1.code_generator
- .claude.agents.chain1._shared.references.cheat_sheets
- .claude.agents.chain1.signal-evaluator.references
---

# block-f-magnitude-primitives-and-cheat-sheets

## 문제
Fix #1 적용 후 결정 트리가 magnitude-seeking 행동(change_horizon, extreme_quantile, add_regime_filter, drop_feature)을 추천하지만, 이들이 효과적으로 동작하려면 LLM이 '언제 |Δmid|가 큰지'를 식별할 수 있는 primitive와 reference가 필요. 현 39 primitive 중 magnitude regime을 직접 표현하는 명시적 primitive는 없음 — 시간대(opening/closing burst), Parkinson high-low range, time-of-day burst flag가 모두 부재. 또 net-PnL objective와 magnitude 추구의 연결을 설명하는 cheat sheet도 없어 LLM이 '어떤 primitive가 어느 axis에 기여하는지' 추론 비용이 큼.

## 검토한 옵션
Option A(P0+P2): 즉시 추가 — 3 boolean regime primitive(is_opening/lunch/closing) + 1 stateful helper(rolling_range_bps) + 2 cheat sheet(magnitude_primitives.md, time_of_day_regimes.md). v4 run 영향: iter_005+가 새 cheat sheet 보면서 부분 contamination. Option B(P0+P1+P2): P1까지 한 번에 — Kyle λ, AR1, tail event indicator, Garman-Klass/Andersen-Bollerslev/Amihud 3 paper 추가. 90분 작업 + v4 contamination 더 큼. Option C: v4 끝날 때까지 대기 후 P0+P1+P2 한 번에 — clean ablation 보전, 단 즉각 효과 없음. Option D: P0 primitive만 추가하고 cheat sheet은 보류 — LLM이 모르는 primitive는 안 쓸 가능성 큼.

## 선택한 접근
Option A(P0 primitive + P2 cheat sheet). 추가 항목: chain1/primitives.py에 is_opening_burst / is_lunch_lull / is_closing_burst (3 boolean primitive, KRX 09:00–09:30 / 11:30–13:00 / 14:30–15:30 KST). RollingRangeBps stateful helper class (Parkinson high-low range in bps over rolling window). PRIMITIVE_WHITELIST 확장 39개. code_generator.STATEFUL_HELPERS에 rolling_range_bps 등록. 신규 cheat sheet: _shared/references/cheat_sheets/magnitude_primitives.md (3 axis framework: A horizon × B regime × C tail), time_of_day_regimes.md (KRX 시간대별 magnitude 측정치 + 합성 recipe). signal-evaluator/references/formula_validity_rules.md whitelist 갱신. P1(Kyle λ, AR1, paper 3종)는 v4 종료 후 v5 setup으로 미룸.

## 근거
(1) v4 첫 4 iter에서 결정 트리가 add_regime_filter를 3회 추천했으나 이를 표현할 명시적 primitive 부재 — 측정 가능한 gap. (2) v3 top 3 spec(iter005, iter014, iter019) 모두 'rolling_realized_vol(mid_px, 100) < 30' 형태의 regime filter 사용 — magnitude regime의 중요성은 v3에서 이미 입증, 그런데도 LLM은 일부 spec에만 적용. cheat sheet 부재가 LLM의 발견 비용을 키우고 있음을 시사. (3) P0 primitive 코드 추가 자체는 v4 영향 없음 — LLM은 모르는 primitive 안 씀. cheat sheet 추가만 v4 iter_005+ 에 영향. 이를 'natural experiment'로 활용: iter 0–4 (Fix #1 only) vs iter 5–24 (Fix #1 + new cheat sheets)로 v4 자체가 2-segment 측정 가능. 판단 근거(P8): cheat sheet의 효과 측정은 후속 v5 ablation에서 정확히 분리 가능 — magnitude_primitives.md만 추가했을 때의 marginal contribution을 v4 후반 vs v5에서 비교.

## 트레이드오프
(1) v4 ablation의 unclean partition — iter 0–4와 iter 5+ 가 다른 reference에 노출. paper 작성 시 두 segment를 분리 분석해야 함. (2) P1을 미루면서 Kyle λ / AR1 / Amihud 3개 magnitude lever가 v4에는 부재 — 일부 magnitude-seeking 행동(특히 liquidity-aware)이 실현되지 않을 수 있음. (3) is_opening_burst와 is_closing_burst는 mutually exclusive하므로 잘못 곱하면 항상 0이 되는 anti-pattern 가능 — cheat sheet에 명시했으나 LLM이 따를지 측정 필요.

## 영향 범위
chain1/primitives.py (3 primitive + 1 helper class + WHITELIST + __all__). chain1/code_generator.py STATEFUL_HELPERS. .claude/agents/chain1/_shared/references/cheat_sheets/ 신규 2개. .claude/agents/chain1/signal-evaluator/references/formula_validity_rules.md whitelist 단락 갱신. v4 run의 iter_005+ LLM call이 새 cheat sheet 봄. 영향 없음: backtest_runner, fidelity_checker, calibration, 기존 38 primitive, v3 archive.

## 재검토 조건
(1) v4 후반(iter 5–24)에서 새 primitive(is_opening_burst 등) 사용 spec이 5개 이상 등장하면 cheat sheet의 효과 입증 — v5에 P1 추가 정당화. (2) 등장 0개라면 cheat sheet 표현이 부족하거나 LLM이 magnitude_primitives.md 의 위계를 따르지 않는 것 — 후속 cheat sheet 재작성 또는 system_prompt 강화 결정. (3) is_opening_burst × is_closing_burst 같은 anti-pattern이 발견되면 cheat sheet에 negative example 추가.
