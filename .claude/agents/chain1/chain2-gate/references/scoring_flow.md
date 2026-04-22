# Chain 2 후보 Scoring Flow — 결정론 정의

이 파일이 유일한 권위. 가중치·임계값 변경은 여기서 이루어지며, 코드는 이 값을 상수로 참조한다.

---

## Gates (hard-fail → excluded)

| 게이트 | 조건 | 설명 |
|---|---|---|
| G1 | `trade_density_per_day_per_sym ≥ 300` | 통계적 안정성 하한. 300 미만이면 WR 추정오차 커져 의미 없음 |
| G2 | `WR ≥ 0.55` | 방향 예측력 최소 |
| G3 | `expectancy_post_fee_bps > 0` | 해당 fee scenario 하에서 **양수 기대값** (필수) |
| G4 | `cross_symbol_consistency ∈ {consistent, mixed, not_applicable}` | `inconsistent` 는 제외 |

G1-G4 중 하나라도 실패 → excluded dict 에 `gate_failed:<gate_name>:<detail>` 로 기록.

단, `not_applicable` 은 single symbol 시나리오에서 불가피 → G4 통과로 간주.

---

## Dominance

A가 B를 dominate 하는 조건 (전부 만족):

1. `set(A.primitives_used) ⊇ set(B.primitives_used)` (A가 B의 primitive 를 모두 포함)
2. `A.formula` 가 `B.formula` 를 텍스트 substring 혹은 AST 상 extension 으로 포함 (AND 절 추가 등)
3. `A.direction == B.direction` AND `A.prediction_horizon_ticks == B.prediction_horizon_ticks`
4. `A.expectancy_bps ≥ B.expectancy_bps`
5. `A.trade_density ≥ 0.5 × B.trade_density` (A가 너무 selective 하면 dominance 안 성립)

B → excluded with `reason = "dominated_by:<A.spec_id>"`.

---

## Composite score (0.0 ~ 1.0)

```
score =
  0.35 × s_edge     (expectancy_post_fee_bps 기반)
+ 0.20 × s_density  (log trade_density 기반)
+ 0.15 × s_filter   (regime self-filter 보너스)
+ 0.15 × s_simple   (complexity 역수)
+ 0.15 × s_multi    (multi-day 재현성 보너스)
```

각 sub-score 는 [0, 1] 로 normalize. 정의:

### s_edge
```
s_edge = clamp((expectancy_post_fee_bps - 0) / (10 - 0), 0, 1)
```
- 0 bps 는 break-even (기여 0)
- 10 bps 는 soft cap (1.0)

### s_density
```
s_density = clamp((log10(trade_density) - log10(300)) / (log10(10000) - log10(300)), 0, 1)
```
- 300 / day / sym 이 gate 하한 (기여 0)
- 10,000 이 cap (1.0)

### s_filter
```
s_filter = 1.0 if has_regime_self_filter else 0.0
```
- 공식에 `spread_bps` 등 regime gate 가 있으면 True
- Chain 2 에서 fee-burn regime 자동 회피 → 가점

### s_simple
```
complexity_score = len(primitives_used) + (1 if stateful_helper else 0) + (1 if compound else 0)
s_simple = clamp((6 - complexity_score) / (6 - 1), 0, 1)
```
- 1 (단일 primitive, stateless, non-compound) → 1.0
- 6+ (compound, stateful, many primitives) → 0.0
- 이유: Chain 2 에서 debug / tune 이 단순할수록 쉬움

### s_multi
```
if n_dates >= 3:   s_multi = 1.0
elif n_dates == 2: s_multi = 0.5
else:              s_multi = 0.2
```
- single-day 측정은 overfit 위험 → 강한 패널티

---

## Priority bucketing

```
priority =
  MUST_INCLUDE  if score ≥ 0.75
  STRONG        if 0.55 ≤ score < 0.75
  MARGINAL      otherwise  (탈락은 아니지만 주의 필요)
```

---

## 가중치 변경 로그

- v0.1.0 (2026-04-21): 초기값. edge 0.35, density 0.20, filter/simple/multi 0.15 각각.
- 이후 multi-day 실증 결과 보고 재보정 예정.
