---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, alpha-mining, factor-discovery]
refs:
  code: []
  papers: []
  concepts:
    - paradigm-twin
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
arxiv_id: 2502.16789
authors: [Ziyi Tang, Zechuan Chen, Jiarui Yang]
venue: preprint
year: 2025
---

# AlphaAgent (2025) — LLM-Driven Alpha Mining with Regularized Exploration

**Citation**: Tang, Chen, Yang. arXiv:2502.16789, 2025-02.

## TL;DR

LLM 이 alpha factor (formulaic) 를 generate, **alpha decay** 대응에 **regularized exploration** 적용. 기존 LLM-driven 방식이 "exploration 부족 → homogeneous factor → crowding 악화" 한다고 비판. **Daily frequency** factor mining (formulaic alpha 표준).

## 우리와의 관계 — frequency 가 다름

| Dimension | AlphaAgent | 우리 |
|---|---|---|
| **Frequency** | **Daily** (formulaic factor mining 표준) | **100ms tick** |
| LLM agent | ✓ | ✓ |
| Iterative refinement | ✓ (decay 대응) | ✓ (Fix #1: net-PnL reward) |
| Output | Daily alpha formula | SignalSpec for tick LOB |
| Market | A-shares (China daily) | KRX cash equity tick |
| Fee constraint | Sharpe-implicit | **Explicit KRX 23 bps** |

→ **Same paradigm (LLM → formula → backtest → improve), different frequency**. AlphaAgent 가 "direct analog" 라 부르기에는 frequency 차이 큼 (daily vs 100ms).

## 핵심 contribution

- **Alpha decay 대응** — factor library 가 커지면 redundancy 증가, predictive power 감소
- **Regularized exploration** — 기존 LLM 이 popular pattern 따라가는 경향 (homogeneous factors) 을 explicit penalty 로 분산

## 우리 framework 와의 conceptual mapping

| AlphaAgent 의 문제 | 우리 framework 에서의 대응 |
|---|---|
| Alpha decay (factor 의 효력 감소) | v3 saturation iter_014 — 같은 family 에서 mutation random walk |
| Homogeneous factors | v3 family 분포: bbo_push/wall + consensus 가 60% 점유 — 같은 cluster |
| Regularized exploration | 우리는 Block C diversity rule (signal-generator AGENTS.md) 사용 |

→ Different mechanism, same diagnosis. **§Related Work 에서 같은 family 로 묶음**.

## 인용 우선순위

⭐⭐ **§Related Work**:
- "LLM-driven alpha mining frameworks (AlphaAgent, Tang et al. 2025; Alpha Jungle, Shi et al. 2025; Chain-of-Alpha, Cao 2025) operate at daily formulaic factor frequency. Our work extends LLM-driven alpha discovery to **sub-second tick-level signals** under fee-binding constraints, where formulaic factor mining frameworks do not apply directly."

⭐ **§Discussion**:
- "Both AlphaAgent and our framework observe LLM-generated factor saturation (alpha decay / mutation random walk). The mitigation differs — they regularize exploration, we redesign reward (Fix #1)."

## 차용 가능 / 미차용 element

| Element | 차용? | 이유 |
|---|---|---|
| Regularized exploration penalty | 미차용 | 우리는 exploration 을 prompt 의 diversity guidance 로 처리 |
| Alpha decay tracking metric | 차용 가능 | post-hoc 분석에 유용 |
| Factor uniqueness measure | 차용 가능 | family clustering 의 quantification |

## Connection

- `paradigm-twin` — Tier 2 (daily LLM × factor mining family)
- 더 자세한 비교: `papers/related_work_survey.md`

## Status

- 2025-02 preprint
- Direct comparison paper at daily frequency, NOT tick
