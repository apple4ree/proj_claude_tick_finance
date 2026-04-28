---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags:
- chain1
- magnitude
- framework
refs:
  code:
  - path: chain1/primitives.py
    symbol: is_opening_burst
    confidence: inferred
  - path: chain1/primitives.py
    symbol: RollingRangeBps
    confidence: inferred
  - path: .claude/agents/chain1/_shared/references/cheat_sheets/magnitude_primitives.md
    symbol: null
    confidence: verified
  papers:
  - garman_klass_1980_range_estimator
  - andersen_bollerslev_1997_intraday_periodicity
  concepts:
  - capped-post-fee
  - net-pnl-objective
  - p1-staged-additions-for-v5
  - exp-2026-04-27-fresh-v5-regime-state-paradigm
  experiments: []
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
---

# Magnitude Axes Framework

Net-PnL objective 하의 chain 1 spec 설계에서 **per-fill |Δmid| 를 키우는 3 개의 직교 차원** (axis A / B / C) 의 명명. 이 framework 은 `_shared/references/cheat_sheets/magnitude_primitives.md` 에서 정식화되었고, Block F (2026-04-27) 의 primitive 추가는 axis B 차원에서의 표현력을 확장하는 작업이다.

## Definition

각 axis 는 직교적 lever 를 정의한다:

- **Axis A — Horizon scaling**: 예측 horizon `h` 를 늘리면 `|Δmid|` 가 약 `√h` 로 증가 (random-walk scaling). Lever: `prediction_horizon_ticks ↑`.
- **Axis B — Regime concentration**: `|Δmid|` 가 시간 / volatility / liquidity 에 따라 2–4× 차이남. Lever: 신호에 boolean regime gate 를 곱함 (`signal × is_opening_burst`, `signal × (rolling_realized_vol > t)` 등).
- **Axis C — Tail selection**: primitive 의 z-score 분포에서 `|z| ≥ 2` (top 2.5%) 만 진입. tail 의 conditional `|Δmid|` 가 unconditional 보다 큼.

## Net-PnL connection

```
gross_expectancy_bps ≈ (2·WR − 1) × E[|Δmid|]
```

Axis A/B/C 는 모두 `E[|Δmid|]` 를 키우는 lever. WR 차원 (Direction prediction) 은 Direction Semantics framework 에서 별도로 다룸.

Net-PnL > 0 의 deployable spec 은 `gross_expectancy_bps > fee_bps_rt`. KRX 23 bps RT 에서 v3 신호 천장이 13 bps 였던 것은 axis A/B/C 활용도 부족이 원인.

## Composition

권장: 각 spec 은 **최소 2 axis 결합**.

```python
# A × B
signal × is_opening_burst   # horizon 자동 + 시간대 regime
# 단, prediction_horizon_ticks 도 함께 증가

# B × C
signal × (zscore(primary, 300) > 2.0) × (rolling_realized_vol > 30)

# A × B × C (가장 aggressive)
zscore(obi_ex_bbo, 300) > 2.5  AND  rolling_realized_vol(mid_px, 100) > 40
# (with horizon=100)
```

## Anti-pattern

- 단일 axis 만 사용: WR 만 추구 (axis 0 추가) → fee 벽 통과 불가
- Mutually exclusive regime gate 곱: `is_opening_burst × is_closing_burst` (always 0)
- Threshold tightening 만 (`zscore > 3.0`): axis C 강화이나 axis A/B 미반영시 trade count → 0

## Status

- 2026-04-27: framework 정식화, Block F primitive 로 axis B 표현력 확장
- v4 ablation 측정 중 (iter 0–8 시점에 axis B regime gate 사용 spec 증가 관찰됨)
- v5 계획: axis B 의 illiquidity 변형 (`kyle_lambda_proxy`) 추가
