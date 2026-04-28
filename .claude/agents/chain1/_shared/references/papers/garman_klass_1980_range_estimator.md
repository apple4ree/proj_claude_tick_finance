# Garman & Klass (1980) — High-Low-Open-Close Range Volatility Estimator

**Citation**: Garman, M.B. and Klass, M.J., "On the Estimation of Security Price Volatilities from Historical Data", *Journal of Business* 53(1), 67–78 (1980).

## Why this matters to our project

Chain 1 의 magnitude axis (axis B — regime concentration) 에서는 "지금 이 윈도우의 |Δmid| 가 큰가?" 를 판단해야 한다. 표준 도구 두 종류 중 하나를 선택해야 하는데 — RMS-of-diffs (realized volatility) 와 high-low range — 후자가 **tail-aware** 이다. 본 논문이 range-based estimator 의 분산 효율성 (variance efficiency) 을 정식화했고, 그 결과가 우리 `RollingRangeBps` helper (Block F, 2026-04-27) 의 이론 근거이다.

## 1. Background

### Classical close-to-close estimator
시계열 `p_t` 의 분산 추정량:
```
σ̂²_CC = (1/N) · Σ (Δlog p_t)²
```
- N 개 close-to-close 수익률만 사용
- **장점**: unbiased, 모든 차분 정보 사용
- **단점**: efficiency 낮음 — 한 시점의 high/low 정보 (intraperiod 정보) 미사용. 같은 σ² 추정 정밀도를 얻으려면 N 을 키워야 함.

### Parkinson (1980) 의 high-low estimator (선행 연구)
같은 호 *Journal of Business* 에 실린 Parkinson 의 결과:
```
σ̂²_P = (1 / (4·log 2)) · (log(H/L))²
```
- H = period high, L = period low
- single-bar 추정량 (그러나 N 개 bar 에 평균해서 사용)
- **분산 efficiency** : `Var(σ̂²_CC) / Var(σ̂²_P) ≈ 5.2` — 같은 정밀도에 5× 적은 샘플로 충분
- **단점**: drift = 0 가정. 실제 가격에 trend 있으면 bias.

## 2. Garman-Klass extension

### Full formula (open + high + low + close 모두 활용)
```
σ̂²_GK = 0.5 · (log(H/L))² − (2·log 2 − 1) · (log(C/O))²
```
- O = open, C = close, H = high, L = low (period 내)
- **분산 efficiency** : Parkinson 의 약 `1.5×` (CC 대비 약 `7.4×`)
- Drift correction 내장 — `log(C/O)` 항이 trend 영향 차감

### 가정
- Brownian motion (geometric)
- Continuous trading (unrealistic — 불연속적 trading 시 |H/L| 과소추정 → estimator downward biased)
- No discrete jumps

### 실증적 거동
- Bouchaud-Potters 2001 의 측정에 따르면 실제 시장에서는 estimator 가 약 5–15% downward biased — discrete trading + 1-tick rounding 효과
- Tail-event sensitivity: range estimator 는 **single large move** 한 번으로 전체 분산 추정값이 크게 변함 (CC estimator 는 RMS 평균 효과로 둔화). 즉 magnitude tail 을 포착하기에 더 적합.

## 3. Connection to our `RollingRangeBps` helper

```python
class RollingRangeBps:
    """Parkinson-style high-low range in bps over a rolling window."""
    def update(self, x: float) -> float:
        self._buf.append(float(x))
        ...
        hi = float(arr.max())
        lo = float(arr.min())
        denom = max(abs(float(arr.mean())), EPS)
        return 1.0e4 * (hi - lo) / denom
```

우리 구현 vs Parkinson:
- Parkinson 은 단일 bar 의 H/L 사용; 우리는 rolling window 내 max/min — 사실상 **동등** (window 를 1 bar 로 보면 됨)
- 우리는 **bps** 단위로 정규화 — 비교 가능성 위해 mean 으로 나눔 (Parkinson 은 log-return 단위)
- GK 의 drift-correction 항 미포함 — chain 1 은 short horizon (≤ 200 ticks ≈ 20 sec) 에서 drift 가 무시할 만하다는 전제. Long horizon 적용 시 GK formula 로 확장 필요.

### 어디에 쓰는가
- `(rolling_range_bps(mid_px, 200) > 15)` — 최근 200 tick 의 high-low 가 15bps 초과 → high-magnitude regime gate
- `signal × (rolling_range_bps(mid_px, 200) > rolling_mean(rolling_range_bps, 1000))` — recent range > long-term average → regime concentration

## 4. Limitations / when to NOT use

1. **Discrete trading bias**: 우리 KRX tick 데이터는 100ms snapshot — 그 사이의 진짜 H/L 을 못 봄. estimator 가 systematically 5–15% under-estimate. magnitude regime "있음 / 없음" 판정에는 충분하나 점추정 시 보정 필요.
2. **Short windows**: window < 30 tick 시 H, L 추정의 noise > signal. 권장 최소 window: 50 tick.
3. **Regime change crossing**: window 가 두 regime 을 가로질러 통과하면 bias.

## 5. Direct quote (paper)

> "The high-low estimator dominates the close-to-close estimator in mean square error for any positive price drift. ... The combined open-high-low-close estimator achieves an efficiency of approximately 7.4 relative to the close-to-close benchmark."

## 6. References (chain 내 사용처)

- `chain1/primitives.py:RollingRangeBps` — implementation
- `code_generator.py:STATEFUL_HELPERS["rolling_range_bps"]` — registration
- `_shared/references/cheat_sheets/magnitude_primitives.md` §Axis B — usage guidance
