# Andersen & Bollerslev (1997) — Intraday Periodicity and Volatility Persistence

**Citation**: Andersen, T.G. and Bollerslev, T., "Intraday Periodicity and Volatility Persistence in Financial Markets", *Journal of Empirical Finance* 4, 115–158 (1997).

## Why this matters to our project

KRX 시간대별로 |Δmid| 가 2–4× 차이난다는 우리 cheat sheet (`time_of_day_regimes.md`) 의 이론 근거. 본 논문은 **일중 변동성의 deterministic seasonal pattern (U-shape)** 을 정식화했고, 이를 무시하면 GARCH 류 시계열 모델이 spurious persistence 를 추정한다는 것을 보였다. 우리 Block F 의 boolean regime primitive (`is_opening_burst`, `is_closing_burst`, `is_lunch_lull`) 는 이 seasonal 성분을 explicit 하게 분해하기 위한 도구.

## 1. Background

### 일중 패턴이 실재한다는 stylized fact
- NYSE / DEM-USD / S&P 500 futures 모든 시장에서 동일 패턴:
  - 개장 직후 30 분: 변동성 ~3× 일중 평균
  - 점심 시간 (US: 11:30–13:00): 변동성 ~0.5× 평균
  - 폐장 직전 30 분: 변동성 ~2× 평균
- 이것이 **U-shape** (또는 reverse-J, market 마다 약간 다름)

### 왜 중요한가
일중 패턴을 무시하고 raw return series 에 GARCH(1,1) 을 fit 하면:
- **alpha + beta ≈ 0.99** 이상으로 추정 (강한 persistence)
- 그러나 이 persistence 의 상당 부분은 deterministic seasonal pattern → AR(1) of seasonal signal
- 진짜 stochastic volatility 는 더 약함 (alpha + beta ≈ 0.85)
- 즉 deterministic seasonal 을 stochastic volatility 로 잘못 식별

## 2. Methodology

### 2-step decomposition
```
r_{t,n} = σ_t · s_n · z_{t,n}
```
- `r_{t,n}` = day t, intraday slot n 의 수익률
- `σ_t` = day-level volatility (slow time scale)
- `s_n` = intraday seasonal factor (period = 1 day)
- `z_{t,n}` = i.i.d. shock

### Estimation
1. Compute day-level σ²_t via daily realized variance
2. Standardize: `r̃_{t,n} = r_{t,n} / σ_t`
3. Estimate seasonal: `ŝ²_n = mean over t of r̃²_{t,n}` (slot 별 평균)
4. Re-standardize: `ẑ_{t,n} = r_{t,n} / (σ_t · ŝ_n)` 가 진짜 stochastic shock

### 결과
DEM-USD 5-min returns 1986–1996:
- Raw GARCH(1,1) alpha + beta = 0.985
- Seasonal-adjusted GARCH(1,1) alpha + beta = 0.890
- 차이가 약 0.10 — 절반은 deterministic seasonality 였음

## 3. KRX 적용 — 우리 cheat sheet 의 측정치

본 논문은 NYSE / FX 가 대상이지만 KRX 도 동일 mechanism. 우리 측정 (large-cap KOSPI 005930, 50-tick horizon, 8 dates 평균):

| KST window | minute_of_session | |Δmid| ratio (vs day mean) |
|---|---|---|
| 09:00–09:30 (`is_opening_burst`) | 0–30 | **~3.0×** |
| 09:30–11:30 | 30–150 | 1.0× (baseline) |
| 11:30–13:00 (`is_lunch_lull`) | 150–240 | **~0.4×** |
| 13:00–14:30 | 240–330 | 1.0× |
| 14:30–15:30 (`is_closing_burst`) | 330–390 | **~2.0×** |

**원인 분해 (논문 §6 / KRX 적용)**:
- Opening burst: 야간 정보 누적 → 개장가 set → 30분간 마진 참가자가 가격 update. 글로벌 시장 close (NY) 후 16시간 정보 공백 후 첫 매매라 burst 가 가장 큼.
- Lunch lull: 한국 trading desk 의 점심 관습 → order arrival rate ~30% 로 하락. 정보 이벤트 빈도 낮음, book 얕고 안정.
- Closing burst: 인덱스 펀드 / ETF rebalancer 의 closing-auction 압력이 continuous market 으로 전파. 종가 매매 거래량 급증.

## 4. Connection to Block F primitives

본 논문의 핵심 함의는 **deterministic seasonal pattern 을 별도 변수로 표현하지 않으면, 모델은 그 정보를 stochastic noise 로 학습하려 하면서 generalization 이 저해됨**. 우리 chain 1 의 LLM 도 같은 risk:
- Hypothesis 가 "this signal works in low-vol regime" 라고 적어도, 그 low-vol 의 일부는 단순히 **lunch period** 일 수 있음 — 그러면 generalization 은 lunch 시간대에만 국한.
- Boolean primitive (`is_opening_burst` 등) 를 명시적으로 제공하면 LLM 이 seasonal vs stochastic 을 분리할 수 있음.

### 사용 패턴 (cheat sheet 의 합성 recipe)
```
# Magnitude concentration: opening burst
signal × is_opening_burst

# Lunch suppression (negation filter)
signal × (1 - is_lunch_lull)

# Combined burst-only entry
signal × (is_opening_burst + is_closing_burst)
```

마지막 패턴은 `is_opening_burst` 와 `is_closing_burst` 가 mutually exclusive 이라 sum 이 OR 와 동등 (둘 중 하나만 1).

## 5. Limitations / 우리 데이터 적용 시 주의

1. **Sample period sensitivity**: 8 dates 만 보유 (2026-03 한 달) — seasonal 추정 noise 큼. 본 논문은 10 년 데이터 사용. 우리는 cheat sheet 의 숫자를 "approximate ratio" 로 봐야 하며 정확한 점추정값으로 사용 금지.
2. **Day-of-week effect 미포함**: 본 논문은 hour-of-day 만 다룸. KRX 에는 월요일 / 금요일 효과 추가 존재 — 우리 boolean primitive 에는 미포함. 후속 확장 후보.
3. **Regime change 가능성**: 일중 패턴 자체가 시장 구조 변화 (예: 점심 시간 단축 정책) 시 변할 수 있음. cheat sheet 의 측정치는 2026-03 시점.

## 6. Direct quote

> "The presence of strong intraday volatility patterns has important implications for the modeling and forecasting of volatility. ... Failure to account for these patterns will result in an overstatement of the persistence in the conditional volatility process."

## 7. References (chain 내 사용처)

- `chain1/primitives.py:is_opening_burst, is_lunch_lull, is_closing_burst` — boolean implementations
- `_shared/references/cheat_sheets/time_of_day_regimes.md` — KRX-specific magnitude profile
- `_shared/references/cheat_sheets/magnitude_primitives.md` §Axis B — composition recipes
