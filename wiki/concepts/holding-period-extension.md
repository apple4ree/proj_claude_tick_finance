---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [paradigm, fee-economics, deployment]
refs:
  code: []
  papers: []
  concepts:
    - signal-stickiness
    - fee-binding-constraint
    - capped-post-fee
    - regime-state-paradigm
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Holding Period Extension

Trading strategy 의 holding period 를 길게 잡으면 fee/magnitude 비율이 개선된다는 원칙. KRX cash equity 처럼 high-fee-floor 환경에서의 deployable strategy 설계의 first lever.

## Mechanism

```
gross_bps_per_round_trip  ∝  √(holding_period)        (random-walk scaling)
fee_per_round_trip         =  constant (23 bps for KRX)

→ 짧을수록 fee/gross 비율 악화, 길수록 개선
```

## 정량 예시 (KRX 005930 large cap)

| Holding period | Avg gross / RT | Net @23bps fee | Deployable? |
|---|---|---|---|
| 1 tick (100ms) | ~0.5 bps | -22.5 bps | ❌ |
| 50 ticks (5 sec) | ~3 bps | -20 bps | ❌ |
| 500 ticks (50 sec) | ~10 bps | -13 bps | ❌ |
| 5000 ticks (~8 min) | ~30 bps | +7 bps | ✅ marginal |
| 1 hour (~36000 ticks) | ~80 bps | +57 bps | ✅ |
| 1 day | ~280 bps | +257 bps | ✅✅ |

→ KRX cash equity 의 **fee-binding constraint** 하에서 holding period extension 이 deployment 가능성의 가장 큰 lever.

## Empirical evidence (this project)

### v3 (fixed-H tick-trigger)
- max gross expectancy 13 bps over avg 30-50 tick horizon
- 0/80 spec fee 통과
- Mean trade interval = ~tick, fee 누적 천문학적

### Standalone regime-state ablation (force-close artifact)
- `iter000_ask_wall_reversion`: force-close 로 4.5시간 보유 → mean +102 bps
- 그러나 이건 random-walk 의 일중 변동 측정 (alpha 아님)

### PRISM-INSIGHT (daily holding, KOSPI)
- +2.84% per trade × 86 trades = +244% / 6 months
- **Holding period = ~1 day**, magnitude / fee 비율 매우 우호적
- KRX cash 에서 LLM-driven trading agent 가 실제 수익 입증한 사례

## Path to KRX deployment

### 단계별 path
1. **Tick-trigger** (v3): 0% deployable
2. **Regime-state** (v5): variable holding 가능, 그러나 신호 stickiness 가 mean_duration 결정
3. **Multi-hour holding**: regime-state 의 long stickiness 또는 explicit time-stop
4. **Multi-day**: PRISM-INSIGHT 류 paradigm shift

### Trade-offs
| Holding period 늘릴 때 | Pro | Con |
|---|---|---|
| 5000 ticks 까지 | fee 분담 가능 | overnight gap exposure 없음 (intraday) |
| 1 hour+ | meaningful magnitude | regime change 위험 |
| 1 day+ | KRX 친화적 | tick-level edge 손실, 다른 alpha source 필요 |

## Mathematical detail

random-walk scaling:
```
σ(Δmid over T ticks) ≈ σ_per_tick × √T   (i.i.d. assumption)
```

But signal-conditional magnitude grows differently:
```
E[|Δmid_T| | direction predicted correctly] ≈ (σ_per_tick × √T) × correction_factor
```

For T → ∞, correction_factor → 1, mean → σ × √T (Brownian limit). For small T, signal predictivity dominates, magnitude < √T scaling.

## Connection to other concepts

- `signal-stickiness` — regime-state 에서 holding period 를 결정하는 mechanism
- `fee-binding-constraint` — extension 이 필요한 이유
- `capped-post-fee` — extension 부족 시 결과
- `paradigm-twin` — TradeFM 같은 simulator 도 holding period 를 다루지만 우리는 deployment 기준으로

## Paper relevance

- §Discussion 의 "deployment economics" 절
- §Future Work 에서 multi-day extension 가능성
- 우리 chain 1 의 inherent limitation — tick-trigger schema 가 holding period 를 표현 못 함
