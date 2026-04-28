---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, benchmark, paradigm-twin]
refs:
  code: []
  papers: []
  concepts:
    - paradigm-twin
    - reward-target-mismatch
    - net-pnl-objective
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
arxiv_id: 2602.18481
authors: [Wentao Zhang, Mingxuan Zhao, Jincheng Gao, Jieshun You]
venue: preprint
year: 2026
---

# AlphaForgeBench (2026) — Benchmarking End-to-End Trading Strategy Design with LLMs

**Citation**: Zhang, Zhao, Gao, You. arXiv:2602.18481, 2026-02-10.

## TL;DR

LLM-based trading agent 의 **behavioral instability** (run-to-run variance, action flipping) 비판하며 **LLMs as quantitative researchers** (NOT execution agents) paradigm 제안. 우리 chain 1 / chain 2 분리 철학과 **independent convergence** — paradigm twin.

## Core argument

```
"LLM-based trading agents exhibit:
  - extreme run-to-run variance
  - inconsistent action sequences even under deterministic decoding
  - irrational action flipping across adjacent time steps

These issues stem from stateless autoregressive architectures lacking 
persistent action memory, as well as sensitivity to continuous-to-discrete 
action mappings in portfolio allocation."

Solution: "Reframe LLMs as quantitative researchers... 
LLMs generate executable alpha factors and factor-based strategies 
grounded in financial reasoning. This design decouples reasoning from 
execution, enabling fully deterministic and reproducible evaluation."
```

→ 우리 framework 의 chain 1 (signal/strategy generation) ≠ chain 2 (execution) 분리와 정확히 일치.

## 우리와 비교 — paradigm twin 의 정밀 차별

| Dimension | AlphaForgeBench | 우리 framework |
|---|---|---|
| Frequency | Daily portfolio allocation | **100ms tick LOB** |
| Output | Alpha factors (formulas) | SignalSpec (state-machine) |
| Backtest paradigm | Standard daily | **Regime-state (variable holding)** |
| Fee constraint | Implicit (Sharpe / IC) | **Explicit KRX 23 bps RT, sell tax 20 bps** |
| Failure mode focus | Behavioral instability | **Capped-post-fee, cite-but-fail B3, force-close artifact** |
| Reward design | Industry standard (IC) | **Net-PnL with fee plumbing (Fix #1)** |

## Independent convergence — implication

같은 design philosophy 에 independent 도달 = design pressure 가 inevitable. Paper §Discussion 의 의미 있는 contribution:

> *"Independent emergence of reasoning/execution decoupling design (this work, AlphaForgeBench) suggests this is an inevitable response to LLM stochastic behavior in trading domain. Future LLM-driven trading frameworks should explicitly aim for this split."*

## 인용 우선순위

⭐⭐⭐ **§Related Work — concurrent paradigm twin**:
- "Concurrent work AlphaForgeBench (Zhang et al. 2026) advocates the same reasoning/execution decoupling philosophy at daily portfolio allocation frequency. We extend this paradigm to sub-second tick-level signal discovery under fee-binding constraints."

⭐⭐ **§Discussion**:
- "Independent convergence to LLM-as-researcher (vs. LLM-as-trader) suggests this is the inevitable design choice."

⭐ **§Limitations**:
- AlphaForgeBench addresses `behavioral instability` (run-to-run variance) which is orthogonal to our `capped-post-fee` finding. Both are real failure modes of LLM-trading.

## Risk to manage in paper

**Avoid overclaiming "first to propose" reasoning/execution split**. AlphaForgeBench does it at portfolio level concurrently. Accurate framing:
- "We extend the LLM-as-researcher paradigm (concurrently advocated by AlphaForgeBench) to sub-second tick-level..."
- "Our novel contribution: regime-state backtest paradigm + reward function design ablation under sell tax constraint"

## Connection

- `paradigm-twin` — primary instance
- `reward-target-mismatch` — failure mode generalization
- `net-pnl-objective` — Fix #1 의 일반 원리

## Status

- 2026-02-10 preprint
- 우리는 2026-04-27 시점에서 발견 — 우리 framework 의 reasoning/execution split 은 independent design choice 였음을 확인
