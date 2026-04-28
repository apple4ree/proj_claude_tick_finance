---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, signal-design, regime-state]
refs:
  code:
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/regime_state_paradigm.md", symbol: null, confidence: verified}
  papers: []
  concepts:
    - regime-state-paradigm
    - magnitude-axes-framework
    - holding-period-extension
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Signal Stickiness

Regime-state paradigm 하에서 신호가 True 상태로 머무는 지속성 — `mean_duration_ticks` 로 측정. **Magnitude axis A (horizon scaling) 의 regime-state 표현**.

## Definition

```
signal_stickiness = mean across regimes of (exit_tick − entry_tick)
                  = mean_duration_ticks
                  ≈ 시간 단위로: × 100ms / 1000 = sec
```

높은 stickiness = 한 번 fire 하면 길게 유지 = longer holding per regime.

## Why it matters

Fixed-H paradigm 에서는 H 가 고정. Regime-state 에서는 stickiness 가 holding 을 결정 → magnitude × √h scaling 의 직접 lever.

```
gross_bps_per_regime ≈ direction_correctness × E[|Δmid| during regime]
                      ≈ (2·WR − 1) × σ_per_tick × √(mean_duration)
```

`mean_duration` 가 100 → 1000 ticks 으로 늘면 magnitude `× √10 ≈ 3.16` 배.

## Healthy vs pathological stickiness

| mean_duration | duty cycle | 진단 |
|---|---|---|
| < 5 ticks | 어떤 값이든 | **flickering** — fee 천문학적, 자동 reject |
| 5–20 ticks | 모든 값 | short-bursts — fee 분담 어려움 |
| **20–500 ticks** (target) | **0.05–0.80** | healthy regime, magnitude 충분 |
| 500–5000 ticks | 적당 (< 0.95) | long hold, deeper alpha 가능 |
| > 5000 ticks | > 0.95 | **buy-and-hold artifact** zone |

## Stickiness 를 만드는 mechanism

### (1) Compound regime gate
```
signal = obi_1 > 0.5  (raw)              → flickers, mean_dur ~3
signal = obi_1 > 0.5  AND  vol > 30      → stickier, mean_dur ~50
signal = obi_1 > 0.5  AND  is_opening_burst → very sticky in window, mean_dur ~500
```
Composite condition 의 모든 term 이 동시에 변해야 toggle → 자동 stickier.

### (2) Rolling smoother
```
signal = obi_1 > 0.5                         → tick-level noisy
signal = rolling_mean(obi_1, 30) > 0.5       → smoothed, mean_dur ~50
signal = zscore(obi_1, 100) > 1.5            → quantile-stable
```

### (3) Hysteresis (advanced)
```
enter: signal > 0.7
exit:  signal < 0.3
```
Different enter/exit thresholds → 일반 transition 보다 stickier. (Chain 1 schema 미지원, future work)

### (4) Time-of-day gate (axis B + stickiness)
```
signal = (obi_1 > 0.5) AND is_opening_burst
        → opening 30분 동안 high duty, 외에는 0
        → window 내에서 매우 sticky
```

## Anti-pattern: noise-driven flickering

```
signal = obi_1 > 0  (no smoothing, no gate)
        → 매 tick 거의 random True/False
        → mean_dur < 3 ticks
        → fee 천문학적 부담, 자동 reject
```

## Paper relevance

- §Method 의 "spec language design choices" — formula composition rules
- §Discussion 의 "axis A under regime-state" 절 (magnitude_primitives.md 의 regime-state 적응)
- 우리 framework 의 unique design choice — signal stickiness 를 explicit metric 으로 측정

## Related

- `regime-state-paradigm` — host paradigm
- `magnitude-axes-framework` — axis A theoretical basis
- `holding-period-extension` — generalized principle
- `force-close-artifact` — opposite extreme (excess stickiness)
