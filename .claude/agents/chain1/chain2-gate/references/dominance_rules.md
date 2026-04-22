# Dominance Rules — pairwise spec comparison

여러 spec 이 비슷하되 한 쪽이 "확장판" 일 때, 단순한 쪽을 제외한다. Chain 2 로
전파될 후보의 중복성을 줄이고, 실제로 의미 있는 변형만 남긴다.

---

## 정의 — A dominates B ⇔ 아래 5개 전부 만족

1. `set(B.primitives_used) ⊆ set(A.primitives_used)`
2. A.formula 가 B.formula 를 **구조적으로 포함** (AST 혹은 텍스트 substring).
   실용상: B.formula 가 A.formula 의 연속 substring 이거나, A 가 B에 AND 절을 추가한 형태.
3. `A.direction == B.direction` AND `A.prediction_horizon_ticks == B.prediction_horizon_ticks`
4. `A.expectancy_bps ≥ B.expectancy_bps`  (tie 허용, 단 A 가 strictly 확장이면 OK)
5. `A.trade_density ≥ 0.5 × B.trade_density`
   - 확장으로 trade count 가 너무 줄면 dominance 성립 안 함
   - 예: B는 1000 trades, A는 300 trades → ratio 0.3 → A는 B를 dominate 안 함
   - 이유: A가 너무 selective 해서 통계적 힘이 B보다 약함

---

## 제외 기록 포맷

`excluded[B.spec_id] = "dominated_by:A.spec_id"`

---

## 역방향 dominance 방지

만약 A→B, B→A 모두 성립 (이론적으로 불가능하지만 방어) → 더 높은 score 인 쪽만 유지.

---

## 실전 예

이번 run 기준:

| 후보 | dominance 관계 |
|---|---|
| `iter000_microprice_dev_gt_2` (h=1, exp 6.14, n 1352) | dominated by `iter001_microprice_dev_h5` (h=5, exp 6.73, n 3734). 단, horizon 이 다르므로 규칙 3 실패 → 실제로는 dominance **성립 안 함**. |
| `iter001_obi1_and_ofiproxy_gt_0` (exp 6.30, n 482) | dominated by `iter002_obiofi_spread_filtered` (exp 5.19, n 327)? 규칙 5 실패 (327/482 < 0.5 아님 → 통과). 규칙 4 (5.19 ≥ 6.30) 실패 → dominance **성립 안 함**. |

즉 dominance 는 엄격하게 정의돼 있어서 실제로는 매우 드물게 성립. 이는 의도된 보수성.

---

## 코드 참조

구현: `chain1/agents/chain2_gate.py:_check_dominance(spec_a, spec_b, result_a, result_b)`.
