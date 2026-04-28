---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, paradigm, backtest]
refs:
  code:
    - {path: "chain1/backtest_runner.py", symbol: "backtest_symbol_date_regime", confidence: inferred}
    - {path: "chain1/agents/feedback_analyst.py", symbol: "_primary_recommendation", confidence: verified}
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/regime_state_paradigm.md", symbol: null, confidence: verified}
  papers: []
  concepts:
    - net-pnl-objective
    - capped-post-fee
    - magnitude-axes-framework
  experiments:
    - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Regime-State Paradigm

Chain 1 의 backtest semantics. 2026-04-27 부터 default. 기존 fixed-H paradigm 대체.

## Core semantics

- spec.formula > threshold = STATE indicator (not trigger)
- formula True 동안 IN-position, False 즉시 EXIT
- Holding period = continuous time signal stays True (variable, not fixed)
- Fee 1 RT per regime (not per tick)
- No end-of-session force-close (incomplete regime → discarded)

## State machine

```
FLAT  + signal=True  →  ENTER  at mid[i]
LONG  + signal=True  →  HOLD
LONG  + signal=False →  EXIT   at mid[i]
FLAT  + signal=False →  STAY FLAT
```

`gross_bps_per_regime = (mid[exit] − mid[entry]) / mid[entry] × 1e4 × direction_sign`

## Target metric ranges

| Metric | Healthy | Anti-pattern |
|---|---|---|
| signal_duty_cycle | 0.05 – 0.80 | > 0.95 (buy-and-hold) |
| n_regimes / sessions | 5 – 50 | < 1.5 (too rare) |
| mean_duration_ticks | 20 – 5000 | < 5 (flickering) |
| expectancy_bps | ≥ 28 (KRX deployable) | ≤ 0 |

## Why this paradigm

### Mechanical reason
v3 fixed-H 결과: 0/80 fee 통과. 분석에서 매 tick fire = N trades = N × 23 bps fee × n_ticks = 천문학적 비용 부담 발견. 같은 mid 움직임을 N 번 카운트하면서 fee 도 N 번 부과 — statistical artifact.

### User insight (2026-04-27)
> "단위만 tick이고 충분히 buy and hold를 해도 상관없다. 검증, 진입 시점, 청산 시점, 실행이든 뭐든 결국 신호를 통해 buy하고 holding을 해야한다면 하고, 청산해야하면 하는 그런 거"

→ Tick-resolution monitoring 과 holding period 가 직교. 실제 trading 의 자연스러운 mental model.

## Implementation

- `chain1/backtest_runner.py:backtest_symbol_date_regime` — state machine
- `chain1/backtest_runner.py:run_backtest(mode="regime_state")` — default 2026-04-27
- `BacktestResult.{n_regimes, signal_duty_cycle, mean_duration_ticks}` — schema fields
- `chain1/agents/feedback_analyst.py:_primary_recommendation` — sanity checks first

## Sanity checks (auto-rejected by feedback-analyst)

```python
if duty > 0.95:                      → swap_feature  (buy-and-hold)
if n_regimes/sessions < 1.5:         → loosen_threshold (too rare)
if mean_dur < 5 and n_regimes > 100: → add_filter (flickering)
```

## Difference from fixed-H

| Dimension | Fixed-H (legacy) | Regime-state (current default) |
|---|---|---|
| Entry trigger | every tick where signal fires | signal False→True transition |
| Exit | i + H ticks (fixed) | signal True→False transition |
| Holding period | H ticks (fixed) | variable (signal-driven) |
| Fee per RT | per tick fire | per regime |
| n_trades meaning | trade fires (overlapping) | regimes (transitions) |
| Anti-patterns | N/A | duty>0.95, mean_dur<5, n<1.5/sess |

## Legacy mode

`run_backtest(..., mode="fixed_h")` 로 opt-in 가능. v3/v4 결과 비교용.

## Status

- 2026-04-27 09:00: v5 첫 fair 측정 launch
- 결과 미정 (~6h 후)
- v3/v4/v5 3-way ablation 으로 paradigm 효과 측정
