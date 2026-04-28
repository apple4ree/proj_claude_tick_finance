---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [foundation-model, microstructure, tick-level]
refs:
  code: []
  papers: []
  concepts:
    - paradigm-twin
    - regime-state-paradigm
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
arxiv_id: 2602.23784
authors: [Maxime Kawawa-Beaudan, Srijan Sood, Kassiani Papasotiriou, Daniel Borrajo, Manuela Veloso]
venue: preprint (J.P. Morgan AI Research)
year: 2026
---

# TradeFM (2026) — Generative Foundation Model for Trade-Flow and Market Microstructure

**Citation**: Kawawa-Beaudan, Sood, Papasotiriou, Borrajo, Veloso (J.P. Morgan AI Research). arXiv:2602.23784, 2026-02-27.

## TL;DR

524M-param decoder Transformer trained on 10.7B tokens of US equity trade events (>9K stocks). Scale-invariant tokenization + universal feature design enable zero-shot APAC generalization. Generative simulator for synthetic data + stress testing. **"Trading agents" 영역은 그들의 explicit future work**.

## 4 Contributions (자체 명시)

1. Foundation model for microstructure (paradigm)
2. **Partial observability** — trade event stream only (not full LOB) — single trader's view ⭐
3. Scale-invariant feature + universal tokenization (16,384 vocab via mixed-base encoding)
4. Closed-loop market simulator (deterministic LOB matching)

## 우리 framework 와의 관계

| Dimension | TradeFM | 우리 chain 1 |
|---|---|---|
| AI architecture | Custom 524M Transformer (scratch pretrained) | Off-the-shelf LLM (prompt) |
| Training cost | 3× A100 weeks | 0 GPU |
| Output | Trade event tokens (next event prediction) | Executable spec (formula) |
| Goal | Synthetic market | Deployable strategy |
| Eval metric | Realism (K-S, perplexity) | Profitability (net PnL) |
| Frequency | tick (100ms) | tick (100ms) ✓ |
| Trading agent? | ❌ (their future work) | ✅ |

**핵심**: paradigm 다름 (FM-from-scratch vs LLM-agent), frequency 같음, trading agent direction 은 그들의 future work = 우리 영역.

## 차용 가능한 element

1. **Scale-invariant features**: `relative_price_depth = (p_order − p_mid) / p_mid` (bps). 우리 calibration table 보다 더 systematic.
2. **EW-VWAP mid-price estimator**: volume-weighted, time-decayed. 우리 단순 (bid+ask)/2 보다 robust.
3. **Universal tokenization**: 5-tuple (Δt, δp, v, a, s) → 단일 integer. 우리 Block E primitives 와 사실상 같음.
4. **Counterfactual stress testing**: 10× anomalous flow injection. v5 spec 의 robustness benchmark 후보.

## TradeFM 의 명시 future work (Appendix D.4-D.6)

1. **Synthetic data for backtesting** — generate 다양한 market scenarios
2. **Stress testing** — counterfactual injection
3. **Trading agent training** — RL 또는 multi-agent on synthetic environment
   - "RL for optimal execution" (price impact 최소화)
   - "Multi-agent systems" (emergent behavior 연구)

→ 우리 framework 가 "trading agent training" 의 LLM-agent variant. RL 아니므로 entirely orthogonal.

## Empirical results (paper Table 2/3)

- 2-3× lower K-S distance than Compound Hawkes baselines
- Stylized facts 재현 (heavy tail, vol clustering, no autocorr)
- 9-month temporal hold-out + APAC zero-shot 안정
- Conditional generation (controllability) 작동

## Limitations (자체 acknowledged)

- "Closed-loop evaluation couples model quality with simulator fidelity. Full disentanglement remains future work."
- Spread reproduction 만 baseline 에 진 영역 — Hawkes 가 inter-arrival explicit 모델링하기 때문
- "Validating TradeFM's utility for these downstream applications remains a key priority"

## 인용 우선순위

⭐⭐⭐ **§Related Work + §Discussion**:
- "Concurrent foundation-model approach to microstructure"
- "Their future-work direction (trading agents) is our framework"

⭐⭐ **§Method**:
- "We adopt scale-invariant feature design (cf. Kawawa-Beaudan et al. 2026) for cross-symbol primitives"

⭐ **§Future Work**:
- "Integration of foundation-model simulator (TradeFM) with our LLM-agent layer for synthetic-to-real validation"

## Connection

- `paradigm-twin` — TradeFM 은 paradigm twin 이긴 하나 different direction (sim vs agent)
- `regime-state-paradigm` — TradeFM 의 closed-loop generation 도 일종의 state-machine approach
- 우리 `_shared/references/papers/` 에 더 상세한 분석 (analysis_vs_ours.md)
