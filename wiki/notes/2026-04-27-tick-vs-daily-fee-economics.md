---
schema_version: 1
type: free
created: 2026-04-27
updated: 2026-04-27
tags: [fee-economics, paradigm, paper-target, finding]
refs:
  code: []
  papers:
    - alphaagent-2025
    - quantagent-2025
  concepts:
    - fee-binding-constraint
    - holding-period-extension
    - capped-post-fee
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Tick vs Daily Fee Economics

## 노트

Holding period (tick / hour / day) 와 fee floor 의 비율이 KRX cash equity 시장에서의 deployment 가능성을 결정. **본 프로젝트 (tick) vs PRISM-INSIGHT (daily) 의 비교가 직접 evidence**.

### KRX cash 의 fee 와 holding period 비율

| Holding period | Avg gross / RT | KRX 23 bps fee / RT | Net | Deployable? |
|---|---:|---:|---:|---|
| 1 tick (100ms) | ~0.5 bps | 23 bps | -22.5 | ❌ |
| 50 ticks (5 sec) | ~3 bps | 23 | -20 | ❌ |
| 500 ticks (50 sec) | ~10 bps | 23 | -13 | ❌ |
| **5000 ticks (~8 min)** | **~30 bps** | 23 | **+7** | ✅ marginal |
| **1 hour** | **~80 bps** | 23 | **+57** | ✅ |
| **1 day (PRISM)** | **~280 bps** | 23 | **+257** | ✅✅ |

→ KRX cash 에서 fee 통과를 위해 **holding period extension 이 first lever**.

### 실증 — 본 프로젝트 vs PRISM-INSIGHT

**우리 (tick)**:
- v3 fresh run (chain 1, 25 iter, 80 spec, fixed-H paradigm)
- max gross 13.32 bps
- 0/80 fee 통과
- conclusion: tick-trigger 로 KRX deploy 불가능

**PRISM-INSIGHT (daily, KOSPI)**:
- 13+ LLM agent multi-agent system
- 86 trades / 6 months (~14 trades/month → daily holding)
- +2.84% per trade × 86 = **+244% cumulative return**
- LLM-driven trading 이 KRX cash 에서 deployable 입증

→ **같은 LLM-agent paradigm 이 frequency 만 다르면 KRX deploy 결과가 정반대**.

## Mathematical framework

random-walk scaling:
```
σ(Δmid over T ticks) ≈ σ_per_tick × √T   (i.i.d. assumption)
```

Signal-conditional magnitude growth:
```
E[|Δmid_T| | signal correct] ≈ (σ_per_tick × √T) × correction_factor
```

For T → ∞, correction → 1; for small T, signal predictivity dominates → magnitude < √T scaling.

KRX 005930 (large cap):
- σ_per_tick ≈ 0.5 bps
- σ_daily ≈ 100-150 bps
- 상호 √T scaling 실측에 부합

→ **KRX cash 시장에서 fee 통과의 가장 단순한 path = T 키우기 (longer holding)**.

## 우리 framework 의 inherent limitation

Chain 1 의 SignalSpec schema 는 binary trigger:
- `formula > threshold` → fire
- 매 tick 평가
- holding period:
  - fixed-H (legacy): 항상 H (예: 30 ticks)
  - regime-state (v5): 변수 — signal 이 True 인 동안

→ **regime-state 라도 mean_duration 이 보통 20-200 ticks 범위** (이 범위에서 평균 gross 3-10 bps). 23 bps fee 통과 어려움.

## 함의 — paper §Discussion / §Conclusion

### Strong claim
> *"Tick-level signal-driven trading at KRX cash equity is mechanically constrained by 23 bps RT fee floor. Our chain 1 framework, even with regime-state holding extension, hits this constraint at ~13 bps gross. **Multi-hour or multi-day holding paradigms (e.g., PRISM-INSIGHT) escape this constraint by ratio (gross/fee) improvement, not by improving signal quality**."*

### Weak claim (more cautious)
> *"Our findings suggest that for fee-binding markets, the holding period dimension may be a more impactful design lever than tick-level signal sophistication."*

## 시사점 — chain 1 spec language 의 limit

Chain 1 의 binary trigger schema 는 본질적으로 short holding (regime-state 라도 mean_dur 20-200) 영역. KRX cash deploy 를 위해서는:

1. **Schema 확장**: PolicySpec 으로 explicit holding period control
2. **Multi-day paradigm shift**: chain 1 자체를 daily/intraday agent 로 전환
3. **Spread capture (chain 2 maker)**: 추가 5-7 bps gross 가산 — 그러나 sell tax 20 bps 못 깸

## 링크

- `fee-binding-constraint` — generalized framework
- `holding-period-extension` — specific lever
- `capped-post-fee` — measurement label
- `alphaagent-2025`, `quantagent-2025` — daily / intraday LLM agents (KRX 친화적)
