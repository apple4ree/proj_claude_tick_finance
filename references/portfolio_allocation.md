# Portfolio Allocation

> **Primary consumer**: portfolio-designer
> **Trigger condition**: cross-symbol 자본 배분 시 (항상)
> **Companion references**: `fee_aware_sizing.md`
> **Status**: stable

---

## 0. Core insight

**자본 배분은 심볼 간 correlation과 EV로 결정한다. Uniform 분배는 default가 아니다.**

**해결할 failure mode**: 단일 심볼 집중으로 pooled avg가 왜곡. 특정 심볼이 4-심볼 평균 EV를 단독으로 끌어올려 전략 품질 과대평가.

**실측 근거**: `knowledge/lessons/lesson_023` — 1개 심볼이 세션 전체 PnL의 87% 기여. 해당 심볼 제거 시 pooled WR 61% → 44% 하락.

---

## 1. Kelly fraction

**수식**:
```
f* = (WR × avg_win_bps - (1 - WR) × avg_loss_bps) / avg_win_bps
f_applied = f* × k        (k = 0.25 권장)
capital_i  = total_capital × f_applied
```

**Python snippet**:
```python
def kelly_fraction(wr: float, avg_win: float,
                   avg_loss: float, k: float = 0.25) -> float:
    """
    wr:       win rate [0, 1]
    avg_win:  평균 수익 bps (양수)
    avg_loss: 평균 손실 bps (양수, 절댓값)
    k:        fractional kelly 계수
    """
    if avg_win <= 0:
        return 0.0
    f_star = (wr * avg_win - (1 - wr) * avg_loss) / avg_win
    return max(0.0, min(f_star * k, 0.25))   # 25% 상한

# Example: WR=45%, avg_win=120, avg_loss=80
# f* = (0.45×120 - 0.55×80) / 120 = 10/120 = 0.083
# f_applied = 0.083 × 0.25 = 0.021  →  자본의 2.1%
```

**When to use**: IS 샘플 n ≥ 30이고 WR / avg_win / avg_loss 추정치 신뢰 시
**When NOT to use**: n < 20 — 추정 오차가 Kelly 계산을 지배
**Calibration**: k=0.25 (기본). 신뢰도 높은 IS 결과: k=0.5. 초기 탐색: k=0.10

---

## 2. Correlation-adjusted sizing

**수식**:
```
ρ_avg      = mean of all pairwise correlations (IS 기간 일일 수익률)
effective_n = n / (1 + (n - 1) × ρ_avg)
effective_capital_per_symbol = total_capital / effective_n
```

**Python snippet**:
```python
import numpy as np
import pandas as pd

def effective_n(returns_df: pd.DataFrame) -> float:
    """
    returns_df: 심볼별 일일 수익률 DataFrame, columns = symbols
    """
    n = len(returns_df.columns)
    if n < 2:
        return float(n)
    rho_mat = returns_df.corr().values
    rho_avg = (rho_mat.sum() - n) / (n * (n - 1))   # 대각선 제외 평균
    return n / (1 + (n - 1) * rho_avg)

# Example: BTC/ETH/SOL, ρ_avg=0.72
# effective_n = 3 / (1 + 2×0.72) = 3 / 2.44 ≈ 1.23
# → 3개 심볼이지만 실질적으로 1.2개 독립 베팅
```

**When to use**: 2개 이상 심볼 동시 운용 (항상)
**When NOT to use**: 없음
**Calibration**: ρ_avg > 0.7 → effective_n < 1.5 → 합산 자본 60–70%만 투입 권장

| ρ_avg | 해석 | 대응 |
|-------|------|------|
| < 0.3 | 분산 효과 충분 | 정상 배분 |
| 0.3–0.7 | 부분 중복 | effective_n 적용 |
| > 0.7 | 실질 단일 베팅 | total_capital × 0.70만 투입 |

---

## 3. EV-weighted allocation

**수식**:
```
weight_i ∝ ev_bps_after_fee_i × sqrt(n_entry_i)
weight_i  = 0  if ev_bps_after_fee_i <= 0
capital_i = total_capital × weight_i / Σweight_j
capital_i = min(capital_i, total_capital × max_single_pct)
```

**Python snippet**:
```python
def ev_weighted_alloc(total_capital: float,
                      ev_bps: dict,          # {symbol: ev_after_fee}
                      n_entries: dict,       # {symbol: n_entry}
                      max_single_pct: float = 0.40) -> dict:
    weights = {}
    for sym, ev in ev_bps.items():
        if ev <= 0:
            weights[sym] = 0.0              # 음수 EV → 자동 제외
        else:
            weights[sym] = ev * (n_entries.get(sym, 1) ** 0.5)

    total_w = sum(weights.values())
    if total_w == 0:
        return {s: 0.0 for s in ev_bps}

    result = {}
    for sym, w in weights.items():
        raw = total_capital * w / total_w
        result[sym] = min(raw, total_capital * max_single_pct)
    return result
```

**When to use**: per-symbol EV 추정치가 있는 경우 (항상 권장)
**When NOT to use**: EV 추정 불가 — kelly_fraction으로 fallback
**Calibration**: `max_single_pct` = 0.40 default

---

## 4. Per-symbol lot sizing

**수식**:
```
effective_price = entry_price × (1 + slippage_bps / 10000)
lot_i = floor(capital_i / (effective_price × min_lot_unit))
```

**Python snippet**:
```python
import math

BINANCE_MIN_LOT = {"BTCUSDT": 0.00001, "ETHUSDT": 0.0001, "SOLUSDT": 0.01}

def compute_lot(capital: float, entry_price: float,
                symbol: str, slippage_bps: float = 0.0) -> float:
    min_lot = BINANCE_MIN_LOT.get(symbol, 0.001)
    eff_price = entry_price * (1 + slippage_bps / 10_000)
    raw = capital / (eff_price * min_lot)
    return max(1.0, math.floor(raw)) * min_lot

# slippage_bps: fee_aware_sizing.md §3 walk-book 모델에서 조회
```

**When to use**: 진입 직전 lot 확정 시 (항상)
**When NOT to use**: 없음
**Calibration**: lot > 1 BTC 이상이면 `fee_aware_sizing.md §3` walk-book slippage 필수 반영

---

## 5. Risk limits

**수식**:
```
max_single_symbol_pct:      capital_i / total_capital <= 0.40
max_drawdown_per_symbol_bps: 심볼별 누적 DD >= 임계 → capital_i = 0
```

**Python snippet**:
```python
def apply_risk_limits(allocations: dict, realized_dd: dict,
                      total_capital: float,
                      max_dd_bps: float = 300.0) -> dict:
    result = {}
    for sym, cap in allocations.items():
        # 단일 심볼 상한
        capped = min(cap, total_capital * 0.40)
        # 낙폭 초과 심볼 제외
        if realized_dd.get(sym, 0.0) >= max_dd_bps:
            capped = 0.0
        result[sym] = capped
    return result
```

**Calibration**: `max_single_symbol_pct`=0.40, `max_drawdown_per_symbol_bps`=300

---

## 6. Rebalancing cadence

| 시점 | 대상 | 방법 |
|------|------|------|
| 매 5 iter | EV 추정치 | ev_weighted_alloc 재실행 |
| Paradigm shift | 전체 재배분 | correlation 재측정 + Kelly 재계산 |
| Drawdown cut 발동 | 해당 심볼만 | 즉시 0 배분, 복구는 다음 iter |
| OOS 테스트 실패 | 전체 | IS 기간 연장 후 재추정 |

---

## 7. Anti-patterns

1. **Equal weight without correlation check** — ρ_avg > 0.7 심볼에 균등 배분 시 실질 단일 베팅. effective_n 계산 후 배분.
2. **Full Kelly** — edge 추정 오차 시 파산 가능. k ≤ 0.5 강제.
3. **lot 10× = PnL 10× 가정** — slippage 곡선이 비선형. lot 증가 시 `fee_aware_sizing.md §3` walk-book 반영 필수.
4. **단일 심볼 > 40% 집중** — pooled avg 왜곡 + concentration risk. `max_single_symbol_pct=0.40` 하드캡.
5. **음수 EV 심볼에 소량 배분** — "혹시 반등" 심리. EV ≤ 0 → weight=0 강제 (§3).
6. **Rebalancing 없이 초기 weight 고정** — 시장 체제 변화 시 stale 배분 유지. §6 cadence 준수.
7. **realized_dd 추적 생략** — 손실 심볼이 자본 계속 소비. `apply_risk_limits` 항상 호출.

---

## 8. Parameter cheat

| 파라미터 | 권장값 | Range | 주의 |
|----------|--------|-------|------|
| `kelly_fraction_k` | 0.25 | 0.1–0.5 | 0.5 이상은 IS 신뢰도 높을 때만 |
| `max_single_symbol_pct` | 0.40 | 0.2–0.6 | 0.6 초과 금지 |
| `rho_threshold` | 0.70 | 0.5–0.85 | 초과 시 합산 자본 70%만 투입 |
| `max_drawdown_per_symbol_bps` | 300 | 200–500 | 심볼 변동성 수준에 따라 조정 |
| `rebalance_interval_iters` | 5 | 3–10 | 짧을수록 추정 노이즈 민감 |

---

## 9. References

- Kelly, J.L. (1956). "A New Interpretation of Information Rate". *Bell System Technical Journal* 35(4).
- Thorp, E.O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market". *Handbook of Asset and Liability Management*.
- `knowledge/lessons/lesson_023` — 단일 심볼 concentration 왜곡 사례
- `fee_aware_sizing.md §3` — walk-book slippage 모델
