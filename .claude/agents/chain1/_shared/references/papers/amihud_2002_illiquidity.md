# Amihud (2002) — Illiquidity and Stock Returns

**Citation**: Amihud, Y., "Illiquidity and Stock Returns: Cross-Section and Time-Series Effects", *Journal of Financial Markets* 5(1), 31–56 (2002).

## Why this matters to our project

우리 v3 분석의 핵심 발견: **신호 천장 13 bps × KRX RT fee 23 bps = net negative**. 이 천장을 깨려면 **per-fill |Δmid| 를 키워야** 한다. 본 논문은 직관적 illiquidity 측정량 **`|return| / volume`** (Amihud ratio) 을 제안하고, 이것이 cross-section 에서 expected return premium 을 예측한다는 것을 보였다 — 즉 "illiquid 한 시점에 매매하면 더 큰 magnitude 가 발생". 우리 chain 1 v5 에서 도입할 `kyle_lambda_proxy` 와 직접 동치.

## 1. Background

### "Liquidity" 의 정의 (논문 §2)
> *"the ability to buy or sell large quantities of an asset quickly, at low cost, with little price impact"*

이 정의에는 4 차원이 섞여 있음:
1. Tightness — bid-ask spread
2. Depth — book volume
3. Resiliency — price impact decay 후 회복 속도
4. Immediacy — order-to-fill latency

Amihud ratio 는 이 중 (1)+(2)+(3) 의 종합 (price impact per volume).

### Kyle 1985 의 λ (이론적 근거)
Kyle 모형에서 informed trader 의 order flow x 가 mid-price 를 `Δp = λ·x` 만큼 움직임. 여기 `λ` 는 market maker 의 inverse-depth (informed flow 를 detect 하는 능력의 reciprocal). Amihud ratio 는 `λ` 의 **empirical proxy**.

## 2. Amihud Ratio — 정의

### 단일 일자 (daily)
```
ILLIQ_t = |R_t| / DVOL_t
```
- `R_t` = 일중 수익률 (daily return)
- `DVOL_t` = 일중 거래대금 (dollar volume)

### Period-level (월간 또는 연간)
```
ILLIQ_{i,T} = (1/D_T) · Σ_{t∈T} |R_{i,t}| / DVOL_{i,t}
```
- 종목 i, 기간 T 의 평균
- 단위: 거래대금 1 단위당 가격 충격 (예: 1억원 매매당 bps)

### Tick-level 변형 (우리 chain 1 적용)
```
λ_tick = |Δmid_t| / Δvolume_t  (단일 tick)
λ_window = (1/W) · Σ_{i=t-W+1}^{t} |Δmid_i| / Δvolume_i  (rolling window 평균)
```

## 3. 실증 결과 (본 논문)

### Cross-section premium
NYSE 1963–1997, monthly cross-sectional regression:
```
R_{i,t+1} = β_0 + β_1 · ILLIQ_{i,t} + β_2 · controls + ε
```
- `β_1 > 0`, t-stat ≈ 6.4 — illiquid 종목이 다음 달에 더 큰 expected return
- "illiquidity premium" — investor 가 illiquidity risk 에 대한 보상을 요구

### Time-series effect
- 일중 ILLIQ 가 클 때 시장의 expected risk premium 도 큼
- VIX 류 변동성 지수와 0.6+ 상관

## 4. 우리 chain 1 적용 — `kyle_lambda_proxy`

### Primitive 설계 (P1, v5 도입 예정)
```python
def kyle_lambda_proxy(snap: Any, prev: Any | None) -> float:
    """Single-tick Kyle λ proxy: |Δmid| / Δvolume."""
    if prev is None:
        return 0.0
    d_mid = abs(mid_px(snap) - mid_px(prev))
    d_vol = max(abs(snap.acml_vol - prev.acml_vol), 1.0)  # avoid /0
    return d_mid / d_vol
```

### Smoothing
single-tick `λ_tick` 은 noise 큼. Rolling 평균으로 사용:
```
rolling_mean(kyle_lambda_proxy, 200)   # 최근 200 ticks 평균 impact
zscore(kyle_lambda_proxy, 1000) > 2.0   # 현재 tick 의 impact 가 1000-tick 분포의 tail
```

### Magnitude 추구의 직접 도구
- `(rolling_mean(kyle_lambda_proxy, 200) > threshold) → high-λ regime` — 매 trade 가 더 크게 가격을 움직이는 시점
- `signal × (rolling_mean(kyle_lambda_proxy, 200) > threshold)` — 같은 신호도 high-λ window 에 발사하면 |Δmid| 가 더 큼 → net expectancy ↑

## 5. Connection to fee-vs-magnitude trade-off

핵심 함의 (chain 1 v5 motivation):

```
gross_expectancy_bps ≈ direction_correctness × E[|Δmid|]
                     = (2·WR − 1) × λ_avg × E[|Δvolume|]
```

- WR 은 LLM 이 잘 키울 수 있는 차원 (95% direction accuracy 측정됨)
- λ 는 거의 손대지 않은 차원 — illiquid window 에서 매매하면 같은 거래 사이즈에 더 큰 |Δmid|
- v3 천장 13 bps 는 LLM 이 high-λ regime 을 선택하지 못해서 — λ 평균값에서의 expectancy

→ 결론: **`kyle_lambda_proxy` + cheat sheet 추가가 chain 1 의 다음 가장 큰 leverage**.

## 6. Limitations / KRX 적용 시 주의

1. **거래대금 vs 거래량**: 본 논문은 daily DVOL (KRW 단위 또는 USD 단위). 우리 tick 데이터는 ACML_VOL (누적 주식 수) 만 직접 접근 가능 — 근사적으로 `DVOL ≈ ACML_VOL · mid_px`. 약간의 noise 추가.
2. **Tick 단위 vs daily**: 본 논문은 daily aggregation. tick 단위로 직접 적용시 noise 비율이 크게 증가 — rolling 평균 윈도우 ≥ 50 tick 필수.
3. **Bid-ask bounce 오염**: tick 단위 |Δmid| 의 일부는 bid-ask bounce. mid 사용 시 영향 작으나 bounce 가 0 이라 가정 못함. 보정: `Δmid` 보다 `Δmicroprice` 사용 가능 (Stoikov 2018).
4. **Volume = 0 tick**: 100ms snapshot 중 거래 없는 tick 다수. 그 시점 ILLIQ = ∞ 또는 정의 불가. 우리 구현에서는 floor `max(Δvolume, 1)` 적용.

## 7. Direct quote

> "Illiquidity affects asset prices: illiquid assets must offer higher returns to compensate for the difficulty of trading. ... Most importantly, our measure ILLIQ has the merit of simplicity: it does not require detailed transaction data."

## 8. Related (chain 내 사용처 — 예정)

- `chain1/primitives.py:kyle_lambda_proxy` — 단일 tick implementation (v5)
- `_shared/references/cheat_sheets/magnitude_primitives.md` §Axis B — illiquidity-aware regime gate (v5 갱신 예정)
- `_shared/references/papers/kyle_1985_continuous_auctions.md` — 이론적 모형 (이미 보유)
