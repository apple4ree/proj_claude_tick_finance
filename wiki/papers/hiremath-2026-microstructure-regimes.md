---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [microstructure, regime-detection, lob, tick-level]
refs:
  code: []
  papers: []
  concepts:
    - regime-state-paradigm
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
arxiv_id: 2604.20949
authors: [Prakul Sunil Hiremath, Vruksha Arun Hiremath]
venue: preprint
year: 2026
---

# Hiremath & Hiremath (2026) — Early Detection of Latent Microstructure Regimes in LOB

**Citation**: Hiremath & Hiremath. arXiv:2604.20949, 2026-04.

## TL;DR

LOB 가 stable → **latent build-up** → stress 의 3-regime causal data-generating process 를 가진다는 이론. 표준 OFI / vol 같은 reactive signal 의 한계 명시. Latent build-up regime 의 identifiability + lead-time 보장 도출.

## 핵심 이론

```
Underlying causal DGP:
  stable regime  ─→  latent build-up  ─→  stress regime
       (low vol)      (drift, no observable signal)   (high vol, observable)
```

표준 indicator (OFI, realized vol, spread) 는 **stress regime 에 들어간 후에만 detect** = reactive. Latent build-up phase 가 진짜 actionable window.

→ Mild assumption (temporal drift + regime persistence) 하에서:
1. Latent build-up regime 이 identifiable
2. Strict positive expected lead-time 보장

## 우리 framework 와의 관계

⭐⭐⭐ **OVERLAP + COMPLEMENTARY**:

우리는 **regime-state paradigm** 을 backtest measurement framework 으로 사용 — Hiremath et al 은 같은 regime concept 의 **이론적 backbone**. 

| Dimension | Hiremath et al | 우리 framework |
|---|---|---|
| **Regime concept** | 시장의 latent state (causal DGP) | 신호의 state machine (binary indicator) |
| **Approach** | Theoretical (identifiability proof) | Empirical (LLM-generated specs) |
| **Output** | Lead-time 보장 + detection rule | Spec + measurement metrics |
| **Frequency** | LOB tick-level | LOB tick-level ✓ |

→ 그들의 framework + 우리 LLM agent measurement 결합 가능 (future work).

## 차용 가능

1. **3-regime causal DGP** 명명 — paper §Background 에서 motivation 으로 인용
2. **Lead-time 측정** — 우리 spec 의 entry timing 의 이론적 정당화 (regime build-up 시점 entry)
3. **Reactive vs proactive signal** 구분 — chain 1 v5 의 LLM 이 주로 reactive signal 짜는지 proactive 짜는지 측정 가능

## 우리 측정에서의 흥미로운 연결

v3/v4 의 high-WR but low-magnitude spec 들이 본 framework 에서는 **stress regime 에 reactive** — 이미 변동이 일어난 후 detect. 진짜 deployable 은 **latent build-up phase 에서 entry** 해야 — 이건 chain 1 의 standard primitive 로 표현 가능?

가능한 hypothesis: spec 이 OFI / depth_concentration 같은 surface-level signal 만 사용하면 reactive. **Build-up phase signal** = signed_volume_cumulative + microprice_velocity 같은 stateful primitive 의 누적. v5 가 이 axis 로 진화하는지 측정.

## 인용 우선순위

⭐⭐⭐ **§Related Work + §Method**:
- "Our regime-state backtest paradigm operationalizes the regime concept formalized by Hiremath et al. (2026), measuring spec behavior across regime transitions empirically."

⭐⭐ **§Discussion**:
- "Hiremath et al's reactive vs proactive signal distinction maps to our spec_duty_cycle profile — reactive signals tend to fire during stress regime exits (high duty in stress windows) while proactive signals fire during build-up (transient duty)."

⭐ **§Future Work**:
- "Combining Hiremath et al's latent build-up identifiability theory with our LLM-spec generation could yield specs that target proactive entry timing."

## Connection

- `regime-state-paradigm` — host paradigm (우리 측)
- 미래 추가 가능: `latent-build-up-regime` concept page

## Status

- 2026-04 preprint
- Hiremath & Hiremath 의 본문 미정독 (abstract 만 검토). Full PDF download + 정밀 분석 권장 (future work).
