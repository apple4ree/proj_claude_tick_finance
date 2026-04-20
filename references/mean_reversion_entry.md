# Mean-Reversion Entry Timing Cheatsheet

> **Primary consumer**: `alpha-designer` agent.
> **Focus**: Oversold ≠ bounce imminent — entry timing patterns that filter "falling knife" trades.
> **Companion reference**: `exit_design.md` (what to do once in a position).

---

## 0. Core insight

Mean-reversion signal이 fire된다고 바로 bounce 나오는 건 아니다. "price is oversold" 는 필요조건일 뿐 **충분조건이 아님**. Iter1의 roc_168h ≤ -5.6% 는 `8/12 trades에서 MFE가 나중에 +100 bps 이상 나왔지만 먼저 떨어지다가 SL 걸림` — 이는 **signal 타이밍이 먼저** 울렸다는 증거.

**Fix pattern (공통 구조)**:
```
oversold_condition  AND  reversal_confirmation  → enter
```

`reversal_confirmation` 이 이 문서의 핵심.

---

## 1. Confirmation pattern library

### 1.1 Price structure confirmation

**1a. Bullish reversal bar**:
```python
# current bar closed in the upper half of its range
close_in_range = (close - low) / (high - low)
confirmation = close_in_range > 0.6  # rejection candle signature
```

**1b. Lower-wick (rejection) after oversold**:
```python
lower_wick = min(open, close) - low
body = abs(open - close)
# long lower wick relative to body = sellers pushed down then rejected
confirmation = (lower_wick > 2 * body) and (close > (high + low) / 2)
```

**1c. Two consecutive higher closes after oversold trigger**:
```python
confirmation = close.iloc[-1] > close.iloc[-2] > close.iloc[-3]
```

### 1.2 Momentum oscillator confirmation

**RSI divergence / turn-up**:
```python
rsi14 = RSI(close, 14)
# entry allowed ONLY when RSI crossed back up through 30 after oversold
rsi_turnup = (rsi14.iloc[-1] > 30) and (rsi14.iloc[-2] <= 30)
confirmation = oversold_signal AND rsi_turnup
```

**Stochastic cross-up**:
```python
stoch_k = (close - lowest_low_n) / (highest_high_n - lowest_low_n) * 100
confirmation = stoch_k.iloc[-1] > 20 and stoch_k.iloc[-2] <= 20
```

### 1.3 Volume confirmation

**Capitulation then recovery**:
```python
# volume spike (panic selling) followed by slow volume on next up-move
vol_spike = volume.iloc[-2] > volume.rolling(20).mean().iloc[-2] * 2.0
price_up = close.iloc[-1] > close.iloc[-2]
confirmation = vol_spike and price_up
```

**Buy-volume ratio**:
```python
# Binance-specific: taker_buy_base / volume
buy_ratio = taker_buy_base / volume
confirmation = buy_ratio.iloc[-1] > 0.55  # bid-heavy taker flow
```

### 1.4 Micro-structure confirmation (LOB market only)

```
obi(depth=5) > 0.5   AND   microprice > mid
```
즉 5-level book이 강하게 bid-heavy + microprice가 mid 위쪽으로 skewed → 실제 매수 압력.

### 1.5 Regime gate — 안 사는 게 나을 때

**Strong downtrend filter**:
```python
# block all long entries during persistent downtrends
ema_slope = EMA(close, 50).pct_change(10)
regime_ok = ema_slope > -0.02  # slope >= -2% per 10 bars
allow_entry = oversold_signal AND regime_ok
```

이게 없으면 iter1의 Trade #6~#10 (Nov 2025 BTC 폭락 중) 같은 5회 연속 손실 방지.

---

## 2. iter1 diagnosis with this framework

Trade #8: `roc_168h ≤ -5.6% @ Nov 15` (true) → entered long → price continued down to SL -480.

체크:
- Bullish reversal bar? **No** — close was in lower range at entry bar.
- RSI turn-up? **Not required** by signal; not checked.
- Regime filter? **Not applied** — BTC was in sustained -6.6% window trend.

만약 regime gate만 있었다면: Nov 15의 EMA50 slope 는 -4%+ 였으므로 블락 → -480 회피.

---

## 3. Calibration tips

| Confirmation | 권장 threshold | 주의 |
|---|---|---|
| `close_in_range > 0.6` | conservative; 0.55 도 시도 가능 | 너무 tight하면 signal 빈도 급감 |
| RSI turn-up | 30-line cross | 40-line cross도 valid (less restrictive) |
| 2 consecutive higher closes | 엄격 | Crypto 1h에선 noise에 약함 — 3 bars 중 2 up으로 완화 |
| Volume spike × 2.0 | standard | 2.5 써도 무방 |
| EMA50 slope > -2% | 1d 전략 기준 | 1h는 EMA20 slope > -1% |

---

## 4. Anti-patterns

1. **너무 많은 confirmation 중첩** — signal이 너무 드물어 통계력 상실. 1-2 개까지만.
2. **Look-ahead in confirmation** — `close.iloc[-1]`은 현재 bar 종가이므로 entry 시점에 사용 가능. 하지만 `(close > close.iloc[-1])` 같이 **미래의 close**를 참조하면 look-ahead bias.
3. **Oversold threshold를 confirmation으로 완화** — "roc_168h > -10% (완화) AND reversal" 패턴은 사실상 새로운 signal. 기존 signal edge 검증 X 이므로 discover_alpha 재실행 필요.

---

## 5. Quick-pick decision

실험 목적 | 권장 confirmation
---|---
**첫 iter** (최소 개선) | Regime gate only (EMA slope > -2%)
**진입 품질 올리기** | Regime gate + reversal bar (close_in_range > 0.55)
**noise에 강한 방어** | Regime + reversal + RSI turn-up (3-factor, but 빈도↓)
**High-frequency (1m/5m)** | Micro-structure: OBI + microprice > mid

---

## 6. How this cheatsheet is used

`alpha-designer` agent가 entry_condition 설계 시:

1. Parent `analysis_trace.md` 확인 → MFE > 0 but realized < 0 trades 비율 계산
2. 위 비율 > 40% 면 confirmation pattern 추가 고려
3. §1에서 pattern 1-2개 선택, §3 table로 threshold 설정
4. `brief_realism.rationale` 또는 hypothesis에 사용한 pattern 이름 명시
   - 예: `"roc_168h <= -0.056 AND EMA50 slope > -0.02 (regime gate from mean_reversion_entry.md §1.5)"`
