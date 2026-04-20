# Experiment J — Crypto Horizon × LLM-Generated Strategies

**목적**: 기존 exp_g는 momentum 하나의 간단한 전략만 horizon sweep했음. 여기서는 **LLM-designed 전략**을 각 horizon에서 만들어서 "더 똑똑한 signal design으로도 저-horizon 수익 불가능한가?" 확인.

## 구성

3 paradigms × 3 symbols (3 horizons):
- **1h** (BTC/ETH/SOL): `crypto_1h_*_rsi_atr` — RSI oversold + ATR compression + BB lower + drift filter (mean_reversion)
- **15m** (BTC/ETH/SOL): `crypto_15m_*_rvol_compress` — Realized-vol percentile + vol-of-vol stability (volatility_regime)
- **5m** (BTC/ETH/SOL): `crypto_5m_*_vol_breakout` — Donchian breakout + ATR compression + volume spike + cooldown (breakout)

모두 LLM `alpha-designer` 직접 설계. 데이터: Binance 2025-07-01 ~ 2025-12-31 (6개월).

## 핵심 결과

| Horizon | Symbol | Return | Sharpe | MDD | #RT |
|---|---|---|---|---|---|
| **1h** | BTCUSDT | +4.30% | **+1.32** | -3.24% | 10 |
| **1h** | ETHUSDT | +5.59% | **+2.02** | -1.23% | 4 |
| 1h | SOLUSDT | -2.73% | -1.01 | -4.19% | 2 |
| 15m | BTCUSDT | -45.25% | -6.79 | -48.40% | 242 |
| 15m | ETHUSDT | -36.49% | -2.97 | -42.07% | 255 |
| 15m | SOLUSDT | -32.78% | -2.17 | -37.55% | 248 |
| 5m | BTCUSDT | -61.11% | -21.40 | -61.11% | 821 |
| 5m | ETHUSDT | -61.49% | -12.86 | -61.49% | 859 |
| 5m | SOLUSDT | -66.41% | -12.73 | -66.45% | 845 |

## 핵심 Finding

1. **1h에서 2/3 전략 수익** — ETH Sharpe 2.02 최고
2. **15m 전부 음수** — 평균 Sharpe -4.0, turnover 240~255 roundtrips
3. **5m 재앙 수준** — 평균 Sharpe -15.7, roundtrips 820~860
4. **Fee-saturation threshold $h^*$** 를 **15m~1h 사이로 좁힘**
5. **LLM이 design을 아무리 잘해도 저-horizon에서는 수수료가 엣지를 지운다** — 실험 1의 단순 momentum 결과와 일치

## 논문에 미치는 영향

### 이전 주장
"Tick-level에서 LLM 전략은 실패 — momentum 하나 기준"

### 업그레이드된 주장
"LLM-designed strategies (mean_reversion, volatility_regime, breakout) 모두 **1h 이상에서만 수익** 가능. 
paradigm diversity로는 구조적 fee-saturation 극복 불가. 
**이는 LLM capability가 아닌 시장 기저 제약임**을 실증."

이 결과는 **intervention prompt 개선도 15m 이하를 구원할 수 없음**을 암시 — 논문 §5.4 "Invariant taxonomy blindspot"에 "horizon blindspot"도 추가 가능.

## 업데이트 (2026-04-18) — IR vs Buy-and-Hold

LLM-designed 9개 모두를 period-matched BH와 비교:

| Horizon | pos IR vs BH | beats BH (abs ret) | 최고 IR |
|---|---|---|---|
| 1h | 2/3 | 2/3 | BTC +1.04 |
| 15m | 0/3 | 0/3 | −0.87 |
| 5m | 0/3 | 0/3 | −2.65 |

**1h도 BH를 이긴 2건은 해당 6개월 crypto 하락장에서 현금 유지만으로 이득** — 실제 alpha 아님.

### Weekly Mean-Reversion (raw-IS-EDA 기반, 비LLM)

같은 1h 데이터에서 Raw EDA로 설계한 `crypto_1h_weekly_meanrev_{btc,eth,sol}`:

| Symbol | OOS 2025-11~12 IR vs BH |
|---|---|
| BTC | **+1.73** |
| ETH | **+2.44** |
| SOL | **+3.89** |

LLM-pipeline이 못 찾은 weekly mean-reversion signal을 직접 관측으로 잡음. 논문 §5에 "raw-EDA > signal_brief pipeline"으로 추가 가능.

## 아티팩트

각 전략 `strategies/<id>/` 에:
- `spec.yaml`, `strategy.py`
- `report.json`, `report.html` (통일 한국어 dashboard)
- `trace.json`, `analysis_trace.json`, `analysis_trace.md`
