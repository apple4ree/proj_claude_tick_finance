---
schema_version: 1
type: free
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, mutation, paper-target, finding]
refs:
  code:
    - {path: "chain1/agents/signal_improver.py", symbol: "_rank_triples", confidence: verified}
  papers:
    - lopez-de-prado-2014-deflated-sharpe
  concepts:
    - reward-target-mismatch
    - compositional-fragility
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Mutation Random Walk After Saturation

## 노트

v3 fresh run (25 iter, 80 spec, 63 parent-child mutation pair) 분석에서 발견한 **paper-grade quantitative finding**:

LLM agent 의 mutation 개선력이 **iteration phase 에 따라 systematic 하게 감소**, late phase 에서 random walk (50/50) 로 수렴.

### Phase별 측정

| Phase | n pairs | 개선률 (Δexp > 0) | mean Δexp_bps |
|---|---:|---:|---:|
| early (iter 0–7) | 20 | **70%** | **+0.41** |
| mid (iter 8–15) | 21 | 52% | -0.18 |
| late (iter 16–24) | 22 | 50% | +0.13 |

### Mutation 종류별 분해

| Type | n | 개선률 | 의미 |
|---|---|---|---|
| `tighten_threshold` (mechanical) | 17 | **WR 14/17 (82%)** | mechanically valid (selection bias 자연스러움) |
| `drop_feature/isolate` (judgmental) | 21 | **exp 12/21 (57%)** | judgment 동전 던지기 |

**Mechanical mutation 은 일관 개선, judgmental mutation 은 random walk** 패턴.

### Saturation 시점

Best WR trajectory:
```
iter 0–7:   0.88 → 0.96 (rapid climb)
iter 8–19:  0.92–0.96 (plateau)
iter 20–24: 0.77 → 0.76 (degradation)
```

Iter_014 부근에서 saturation, 이후 mutation 이 noise generator 로 작동.

## Paper relevance

이 finding 은 paper §Results 의 핵심 quantitative observation:

> *"LLM agent의 자가-개선 능력은 saturation 후 random walk 로 수렴 — 50/50 개선률은 mutation 이 directionally informative 가 아니라 noise generator 로 작동함을 의미. **Stopping rule** 또는 **diversity preservation** mechanism 이 부재한 LLM agent loop 의 systematic failure mode."*

### Related theoretical literature

- **Sequential analysis** (Wald 1947) — saturation detection 의 stopping rule
- **Multi-armed bandit** — exploration-exploitation balance
- **Genetic algorithm** literature — diversity preservation (stagnation prevention)

→ LLM agent loop 가 **이 표준 통계학 / RL 영역의 lessons 를 internalize 안 한 상태** = paper §Discussion 의 strong claim.

## Mitigation candidates (v5+ design)

1. **Early-stop rule**: 3 consecutive iter without improvement > ε → halt (이미 v4 의 convergence_window 가 이걸 함)
2. **Diversity bonus** in signal-improver ranking — 같은 family 의 spec 이 N+ 차지하면 penalty
3. **Forced exploration**: 매 K iter 마다 1 spec 은 unrelated family 로 강제

## 링크

- `compositional-fragility` — pipeline-level failure mode
- `reward-target-mismatch` — saturation 의 deeper cause (잘못된 reward 가 saturation 을 만듦)
- `lopez-de-prado-2014-deflated-sharpe` — multiple-testing correction (this finding 과 함께 적용 시 의미 있는 statistical claim)
