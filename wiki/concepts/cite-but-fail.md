---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, microstructure, paper-target]
refs:
  code: []
  papers: []
  concepts:
    - reward-target-mismatch
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Cite-But-Fail

LLM agent 가 표준 microstructure category 에 spec 을 정확히 배정하면서도 (theoretical citation 정확) 그 카테고리의 expected behavior 를 측정 결과가 반박하는 패턴. v3 fresh run (80 spec) 분석에서 **Category B3 (depth ratio reversal)** 에서만 일관되게 발생함을 측정.

## Definition

다음 두 조건이 동시 만족:
1. Spec.hypothesis 가 표준 reference (cheat sheet 또는 paper) 의 category 를 명시 인용 ("This is Category B1 / Cat B3 / etc.")
2. Spec 의 측정 결과 (aggregate WR, expectancy) 가 해당 category 의 expected polarity / magnitude 를 만족하지 않음 (특히 WR < 0.5 이어서 directional 가설이 틀림)

## v3 측정치

| Category | n | WR > 0.5 | avg WR |
|---|---:|---:|---:|
| A (BBO 압력) | 40 | 38/40 (95%) | 0.853 |
| B1 (resistance wall) | 23 | 23/23 (100%) | 0.809 |
| B2 (flow exhaustion) | 16 | 16/16 (100%) | 0.727 |
| **B3 (depth ratio reversal)** | **6** | **4/6 (67%)** | **0.430** |
| C (spread context) | 3 | 3/3 (100%) | 0.920 |

Category A / B1 / B2 / C 에서는 LLM 의 인용이 100% 또는 95% 적중. B3 에서만 directional polarity 가 평균 WR 0.43 으로 명백히 틀림.

## Interpretation

Standard category (A, B1, B2, C) 는 paper / cheat sheet 에 명확한 implementation 예제가 있어 LLM 이 mechanical 하게 적용. B3 (변형 / 합성 카테고리) 는 reference 에 정의는 있으나 example 이 적음 — LLM 이 이름은 인용하되 실제 mechanism 을 잘못 추론.

이는 paper-target ("LLM-generated domain code 의 spec-implementation fidelity") 의 직접 motivating finding:
- LLM 은 "well-documented standard" 와 "novel composition" 사이에서 identification accuracy 가 비대칭
- Cite 능력 (이름) ≠ Implement 능력 (mechanism)
- 후자는 explicit example coverage 에 강하게 의존

## Detection rule (proposed)

`feedback-analyst` 가 fail-case 분석 시 다음 marker 를 가진 spec 을 우선 검사:
1. Hypothesis 에 "Cat[egory] " + 변형 / 합성 카테고리명 포함
2. WR < 0.5 또는 cross_symbol_consistency = "inconsistent"
3. Reference path 에 해당 category 의 명시 example 부재

해당 spec 은 `cite_but_fail` flag 를 부여, signal-improver 가 retire 또는 cat 별 directional flip 권장.

## Related

- **Category framework**: `_shared/references/cheat_sheets/direction_semantics.md`
- **Cross-category accuracy**: 본 wiki 의 free entry `notes/2026-04-27-hypothesis-vs-result-divergence-v3`
- **Reward-target mismatch**: 별도 concept

## Status

- 2026-04-27: v3 분석에서 정식 발견, paper-section §Results.B 후보
- 후속 ablation: B3 example coverage 강화 시 cite-but-fail 비율 감소 측정 — v6 candidate experiment
