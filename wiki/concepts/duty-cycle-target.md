---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, regime-state, metric]
refs:
  code:
    - {path: "chain1/backtest_runner.py", symbol: "backtest_symbol_date_regime", confidence: inferred}
    - {path: ".claude/agents/chain1/_shared/schemas.py", symbol: "BacktestResult", confidence: verified}
  papers: []
  concepts:
    - regime-state-paradigm
    - signal-stickiness
    - force-close-artifact
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Duty Cycle Target

Regime-state paradigm 하에서 신호가 ON 인 비율 — `signal_duty_cycle = n_signal_on / n_ticks`. Spec design 의 핵심 메트릭, target range 0.05–0.80.

## Definition

```
signal_duty_cycle  =  Σ (signal_on_at_tick_i)  /  total_ticks
                   ≈  fraction of session in-position
                   ∈  [0, 1]
```

높은 값 = 신호가 자주 True (오래 hold), 낮은 값 = 거의 fire 안 함 (sparse selectivity).

## Target range (regime-state design)

| Range | 진단 | 행동 |
|---|---|---|
| 0.00–0.01 | extremely sparse | n_regimes 부족, statistical power X |
| **0.05–0.40** | **healthy selective signal** | 정상 spec |
| **0.40–0.80** | **regime gate or persistent state** | regime-aware spec |
| 0.80–0.95 | very persistent | borderline, careful inspection |
| **0.95–1.00** | **buy-and-hold artifact** | **auto-rejected** by feedback-analyst |

## Why the bounds matter

### Lower bound (0.05)
- Below 5% duty: signal 이 너무 rare 해서 sample 부족
- KRX 정규장 234,000 ticks/day × 0.05 = 11,700 ticks ON / day
- 적당한 mean_duration (50–200 ticks) 시 → 60–230 regimes/day
- 이 sample 에서 directional alpha 측정 가능

### Upper bound (0.80 healthy / 0.95 hard)
- Above 80% duty: signal 이 거의 always-on, 차별화 부족
- 95% 이상은 buy-and-hold artifact zone — **force-close-artifact** 와 연관

## v3/v4/v5 측정에서의 실증 분포

### v3 archive smoke (iter000_ask_wall_reversion):
- duty 0.129 (12.9%)
- mean_dur 19.8 ticks
- n_regimes 6375 over 6 sessions
- → healthy range, however expectancy 작음

### v3 archive (iter005_ask_wall_reversion_low_vol):
- duty 0.0097 (1%) ⚠️ below lower bound
- mean_dur 19.9 ticks
- n_regimes 477
- → sparse — feedback 자동으로 "loosen_threshold" 추천

### Force-close artifact 사례:
- duty 0.97+ (auto-rejected)
- mean_dur 16,000 ticks
- n_regimes 1/session

## Sanity check 연결

`feedback_analyst._primary_recommendation`:
```python
if duty > 0.95:
    return "swap_feature", "buy-and-hold artifact"
if n_regimes / n_sessions < 1.5:
    return "loosen_threshold", "signal too rare"
```

이 임계값이 duty 의 acceptable range 의 boundary.

## Spec design 시 고려

LLM 이 hypothesis 작성 시 다음 questions 에 답해야 함:
1. Expected duty cycle?  → 0.05–0.80 안에 들도록 formula 설계
2. Why this duty? — 어떤 regime/condition 이 해당 비율 정당화?
3. If too sparse: lower threshold or simpler formula
4. If too dense: tighter threshold or more compound conditions

`regime_state_paradigm.md` §3 hypothesis template 에 명시.

## Mathematical notes

신호의 expected duty 는 underlying primitive 분포 + threshold 의 함수:
```
E[duty] = P(formula(snap) > threshold) over snap distribution
```

Single primitive 의 경우 (Normal approximation):
- `obi_1 > 0.5` → P ≈ 0.31 (대략 1σ above mean)
- `zscore(X, 300) > 2.0` → P ≈ 0.0228 (top 2.3%)
- `zscore(X, 300) > 2.5` → P ≈ 0.0062 (top 0.6%)
- AND 결합 시 multiplicative (independence 가정 시)

## Related

- `signal-stickiness` — duty 가 같아도 mean_duration 다를 수 있음 (orthogonal)
- `regime-state-paradigm` — host paradigm
- `force-close-artifact` — duty=1 로의 degenerate 경계
- `fee-binding-constraint` — too-low duty → not enough sample for power; too-high duty → no toggling

## Paper relevance

- §Method 의 quantitative metric definition
- §Results 의 v5 spec 분포 분석
- §Discussion 의 LLM-as-spec-generator 의 calibration: 추정 duty vs 실측 duty 의 정확도
