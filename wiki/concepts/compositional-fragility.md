---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, paper-target, multi-stage, failure-mode]
refs:
  code: []
  papers: []
  concepts:
    - reward-target-mismatch
    - cite-but-fail
    - force-close-artifact
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Compositional Fragility

Multi-stage agent pipeline 에서 **각 stage 의 local reliability 가 100% 라도 final outcome 의 reliability 가 보장되지 않는 mode**. Compositional reasoning 이 implicit 한 system 의 standard failure pattern.

## Definition

7-stage pipeline (chain 1):
```
generator → evaluator → code-gen → fidelity → backtest → feedback → improver
   (LLM)     (정적)     (compile)  (정적)    (numeric)   (LLM+규칙)  (LLM+rule)
```

Each stage 의 local check:
- ✓ Primitive whitelisted? (evaluator)
- ✓ Code compiles? (code-gen)
- ✓ Code matches spec? (fidelity-checker)
- ✓ Numeric result obtained? (backtest)
- ✓ Cross-symbol consistency? (feedback)

**모든 stage 통과해도 final outcome (deployable spec) 의 reliability 는 0%** — v3 의 0/80 결과가 직접 evidence.

## Failure mechanism

각 stage 의 check 가 **local property** 만 검증, **global outcome** 은 검증 안 함.
- evaluator: spec 의 syntactic validity (✓), but semantic deployability (✗)
- code-gen: compile success (✓), but matching the LLM's intended semantics (?)
- fidelity: code ↔ spec 1:1 mapping (✓), but spec ↔ deployment goal (✗)
- backtest: numeric result (✓), but measurement assumption validity (e.g., force-close-artifact, ✗)
- feedback: rule-based (✓), but rule's appropriateness for new paradigm (?)

→ 각 stage 가 **closed under its own scope**, composition 이 **open ended**.

## v3/v4 의 직접 evidence

v3:
- 100 spec proposed, 80 stage-pass (eval reject 20%, code-gen 100%, fidelity 100%, backtest 100%)
- → "stage-pass rate" 는 80%
- 그러나 **deployment 성공률 0%** (0/80 fee 통과)

이는 이미 잘 알려진 현상의 microstructure 도메인 instance:
- "Compositional generalization" failure (Lake & Baroni 2018)
- "Specification gaming" (Krakovna 2020)
- "Multi-step reasoning hallucination" (Press 2022)

## Detection — pipeline-level diagnosis

각 spec 의 trajectory 를 분석:
1. Generator 의 hypothesis text 가 deployment 목표 (net PnL > 0) 에 명시 align 됐나?
2. Evaluator 가 deployment 가능성을 평가했나? (현재 syntactic 만)
3. Backtest 가 measurement 의 assumption 을 표시하나? (force-close 등)
4. Feedback 가 deployment 측면에서 spec 을 평가하나? (Fix #1 이 이걸 해결)

## Mitigation strategy (우리 framework 의 design choices)

| Stage | 추가된 check |
|---|---|
| Generator | Hypothesis template (duty/duration/gross 명시) |
| Evaluator | Soft check for regime-state metrics absence |
| Backtest | Sanity metrics (n_regimes/duty/mean_dur) |
| Feedback | Buy-and-hold artifact / flickering / rare 자동 detect |
| Improver | Mutation 의 deployment effect 추정 |
| chain2-gate | G1-G5 (G5 = duty/duration sanity) |

→ **Compositional fragility 를 깨기 위해 각 stage 가 final outcome 측면의 check 를 추가**해야 함. v5 가 이 design 의 첫 fair 측정.

## Generalized lesson

Multi-stage LLM agent pipeline 의 design principle:
1. **Make global objective explicit at each stage** — 우리 Fix #1 (net-PnL 을 모든 stage 의 reward 로)
2. **Add deployment-aware sanity at every stage** — local check 로는 부족
3. **Measure stage-wise vs end-to-end success** — 격차가 fragility 의 정량 지표

## Paper relevance — strong contribution

- §Method 의 "pipeline reliability decomposition" — stage-wise pass rate 측정
- §Results 의 핵심 evidence — 80% stage pass × 0% deployment success = compositional gap
- §Discussion 의 main thesis — "LLM agent pipelines need explicit global objective propagation"

## Connection to other research

- **Compositional NLP**: Lake-Baroni 2018, Hupkes 2020 (different domain, same mechanism)
- **Specification gaming**: Krakovna et al. 2020 (RL adjacent)
- **Multi-step reasoning**: Wei et al. 2022 (chain-of-thought related)
- **Our contribution**: 첫 microstructure 도메인 instance + 정량 측정 framework

## Status

- 2026-04-27 정식 명명
- v3 → v4 → v5 ablation 으로 mitigation 효과 측정 중
