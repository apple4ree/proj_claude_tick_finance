---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, multi-agent, hft, tick-level-adjacent]
refs:
  code: []
  papers: []
  concepts:
    - paradigm-twin
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
arxiv_id: 2509.09995
authors: [Fei Xiong, Xiang Zhang, Aosong Feng, Siqi Sun]
venue: preprint
year: 2025
---

# QuantAgent (2025) — Price-Driven Multi-Agent LLMs for High-Frequency Trading

**Citation**: Xiong, Zhang, Feng, Sun. arXiv:2509.09995, 2025-09-12.

## TL;DR

**"First multi-agent LLM framework explicitly designed for HFT"** 자체 주장. 4 specialized agents (Indicator / Pattern / Trend / Risk). 9 financial instruments (incl. Bitcoin, Nasdaq futures), **1-hour and 4-hour intervals**. Authors define HFT as "short-horizon" but at intraday hour-level, NOT 100ms tick.

## 핵심 design

```
Indicator Agent  →  technical features (RSI, MACD, etc.)
Pattern Agent    →  chart patterns
Trend Agent      →  trend detection
Risk Agent       →  position management
                     ↓
              Trading decision
```

→ **direct trading actions** (buy/sell/hold) per 1-4h interval. Multi-agent debate to converge on action.

## 우리와의 차별 — "First HFT" claim 의 정확한 의미

QuantAgent 의 "high-frequency" = 1-4h decision interval. 우리 frequency = 100ms tick (4× faster than their 1h, 144× faster than 4h).

| Dimension | QuantAgent | 우리 |
|---|---|---|
| **Frequency claim** | "HFT" (사실은 intraday) | **Sub-second tick** |
| **Decision interval** | 1h–4h | 100ms |
| **Output** | Direct trading action (buy/sell) | SignalSpec (formula → state machine) |
| **Market** | Bitcoin / Nasdaq futures | KRX cash equity |
| **Fee** | Implicit | **Explicit KRX 23 bps** |
| **Backtest paradigm** | Direct action sequence | Regime-state |

→ **Frequency 100× 차이** + **direct action vs spec generation** 의 architecture 차이. **Paper 작성 시 정확한 framing 필요**:

> *"QuantAgent (Xiong et al. 2025) claims to be the first multi-agent LLM framework for HFT, but operates at 1–4h interval rather than tick level. To our knowledge, no prior work targets sub-second LLM-agent trading framework with explicit fee-binding constraint."*

## 인용 우선순위

⭐⭐ **§Related Work**:
- Compare frequency: 1-4h vs 100ms (100× differential)
- Compare architecture: direct action vs spec generation

⭐ **§Discussion**:
- Different "HFT" definitions in literature — QuantAgent's coarser, ours sub-second
- Direct-action LLM agents (their direction) vs spec-generation LLM agents (our direction) — orthogonal trade-offs

## 우리 framework 가 differentiated 하는 핵심

1. **Sub-second frequency** — 그들은 1h–4h, 우리는 100ms
2. **Indirect trading** — spec → compile → execute, vs direct action
3. **Fee-binding KRX cash** — 그들 시장 (futures, crypto) 는 fee 관대
4. **Regime-state semantics** — 우리만의 design

## Connection

- `paradigm-twin` — Tier 1 (LLM × HFT 영역, frequency 만 다름)
- 더 자세한 비교: `papers/related_work_survey.md`

## Status

- 2025-09 preprint
- "First HFT LLM" claim 은 1-4h scope 에서만 성립 — 우리 sub-second 영역과 분리됨
