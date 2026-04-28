---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [paper-target, related-work]
refs:
  code: []
  papers: []
  concepts:
    - net-pnl-objective
    - regime-state-paradigm
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Paradigm Twin

Concurrent published work 가 우리 framework 와 **independent 하게 같은 design philosophy** 에 도달한 case. Paper writing 시 §Related Work / §Discussion 에서 careful 한 differentiation 필요.

## Primary instance — AlphaForgeBench (2026-02)

**Zhang, Zhao, Gao, You (2026)** — *"AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models"* (arXiv 2602.18481)

> *"... LLM-based trading agents exhibit extreme run-to-run variance, inconsistent action sequences even under deterministic decoding, and irrational action flipping across adjacent time steps. ... AlphaForgeBench [reframes] LLMs as quantitative researchers rather than execution agents. Instead of emitting trading actions, LLMs generate executable alpha factors and factor-based strategies grounded in financial reasoning. This design decouples reasoning from execution, enabling fully deterministic and reproducible evaluation."*

→ **이건 정확히 우리 chain 1 / chain 2 분리 철학** (reasoning ≠ execution).

## 차별점 (positioning matrix)

| Dimension | AlphaForgeBench | 우리 framework |
|---|---|---|
| **Frequency** | Daily portfolio allocation | **100ms tick LOB** |
| **Output** | Alpha factors (formulas) | SignalSpec (state-machine spec) |
| **Backtest model** | Standard daily returns | **Regime-state (variable holding)** |
| **Fee constraint** | Implicit / handled by Sharpe | **Explicit KRX 23 bps RT, sell tax 20 bps** |
| **Failure modes studied** | run-to-run variance, action flipping | **capped-post-fee, cite-but-fail B3, force-close artifact** |
| **Reward design** | IC / Sharpe (industry standard) | **Net-PnL with explicit fee plumbing (Fix #1)** |

## Other adjacent twins

### TradeFM (2026-02)
**Foundation model + microstructure** at tick level. Same frequency as us. **다른 direction**: simulator (시장 자체 representation), 우리는 agent (시장에서의 정책). 그들의 §10 "training learning-based trading agents" = 우리 영역의 future work.

### QuantAgent (2025-09)
**Multi-agent LLM at HFT-ish frequency** (1-4h). Same general direction as us. **다른 frequency**: 1-4h interval ≠ 100ms tick. They claim "first multi-agent LLM for HFT" but with different definition of HFT.

## 왜 paradigm twin 이 paper-grade observation 인가

**Independent convergence** = 우리 design 의 validity evidence:
- 둘 다 fee-binding constraint 또는 LLM behavioral instability 가 주요 motivation
- 둘 다 reasoning ≠ execution 의 분리 철학
- Independent reasoning 으로 도달 → 우연이 아닌 design pressure 에 의한 inevitable conclusion

이 observation 자체가 paper §Discussion 의 의미 있는 contribution.

## Paper writing 함의

### §Related Work 단락 구조 권장
```
"Concurrent work has explored...
 - AlphaForgeBench (concurrent paradigm twin) — reasoning/execution split, daily frequency
 - TradeFM (foundation model approach) — same frequency, simulator direction
 - QuantAgent (LLM-multi-agent HFT) — sub-tick but coarser than ours
Our contribution operates at the intersection: LLM-agent reasoning at sub-second tick under fee-binding constraints."
```

### §Discussion 의 paradigm twin 단락
"Independent emergence of reasoning/execution decoupling design (us, AlphaForgeBench) suggests this is an **inevitable** response to LLM stochastic behavior. Future framework should explicitly aim for this split."

## Risk in paper writing — overclaiming

**Note carefully**: AlphaForgeBench 가 our chain 1/2 분리 와 같은 design 에 *concurrent* 도달. **"first to propose" 같은 강한 claim 자제**. 정확한 framing:
- "We extend the LLM-as-researcher paradigm (concurrently advocated by AlphaForgeBench) to **sub-second tick-level signal discovery under fee-binding constraints**"
- "Our novel contribution: regime-state backtest paradigm + reward function design ablation under sell tax constraint"

## Detection criteria — paradigm twin 인지 알아보기

Concurrent work 가 paradigm twin 일 조건:
1. Submission / preprint date 이 우리 작업 시점과 ±6 개월
2. 같은 motivation (우리 case: LLM stochastic instability, fee constraint, agent reliability)
3. 같은 design philosophy (reasoning/execution split, multi-stage pipeline)
4. **Different specific implementation** — frequency / market / mechanism 등 한 dimension 이상 다름

## Status

- 2026-04-27 정식 명명
- 검색 범위 (arXiv + Google Scholar + OpenReview까지 일부) 에서 이 외 추가 paradigm twin 발견 안 됨
- Paper §Related Work 의 직접 인용 대상
