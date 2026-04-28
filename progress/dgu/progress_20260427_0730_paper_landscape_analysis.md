---
date: 2026-04-27 07:30
tone: design
title: Related work landscape — LLM x tick 교차점에 우리만 존재
---

## Context
paper-target framing 정확화 위해 arXiv + Google Scholar 검색 (24 query, 200+ 논문 review). 우리 framework 의 unique positioning 검증.

## Done
- 5-tier landscape 정리:
  - Tier 0: LLM-as-researcher (AlphaForgeBench 2026-02 — concurrent paradigm twin) + tick-level FM (TradeFM 2026-02 — simulator only)
  - Tier 1: LLM × HFT multi-agent (QuantAgent 2025-09, 1-4h interval)
  - Tier 2: LLM × daily factor mining (AlphaAgent / Alpha Jungle / Chain-of-Alpha / FactorMiner)
  - Tier 3: LLM × daily trading (TradingAgents / FinCon / ATLAS / StockBench / PRISM-INSIGHT)
  - Tier 4: non-LLM tick LOB (DeepLOB / Briola / T-KAN / Hiremath)
- TradeFM 정밀 분석 (29p PDF): 524M Transformer, partial observability, scale-invariant, "trading agents" = 그들의 future work (Appendix D.6)
- "LLM agent + 100ms tick + KRX fee-binding" 교차점 검색 결과 0 hit — 우리 unique positioning 확인
- analysis_vs_ours.md 작성 (papers/arxiv/01_kawawa-beaudan2026TRADEFM/)

## Numbers
- arXiv 검색: 24 query × 8-12 top = 280+ raw → 124 unique
- Google Scholar 검색: 4 query × 10 top = 40 raw
- 직접 비교 paper: 12개
- LLM × tick-level intersection: 0 prior published work

## Decisions & Rationale
- Paper-target framing 정정: "First LLM agent for tick-level KRX with fee-binding constraints"
- 5 unique contributions 확인:
  1. Reward function design ablation (Fix #1: WR → net-PnL)
  2. Capped-post-fee 정식 분석
  3. Cite-but-fail B3 (LLM reasoning failure mode)
  4. Regime-state paradigm comparison
  5. KRX sell-tax-binding agent behavior
- AlphaForgeBench 와는 paradigm twin (independent reasoning), TradeFM 와는 future work 로 직접 보완

## Next
- paper writing 시작 (deployment 결과 기다리지 않고 framework contribution 먼저)
- 또는 v5 결과 본 후 통합 paper 작성
