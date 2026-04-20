# Trend Momentum Entry

> **Primary consumer**: alpha-designer
> **Secondary consumers**: execution-designer
> **Trigger condition**: `alpha.paradigm == "trend_follow"` 선택 시
> **Companion references**: `mean_reversion_entry.md`, `exit_design.md`
> **Status**: stable

---

## 0. Core insight

**돌파(breakout)는 확률이지 확정이 아니다. 가짜 돌파(false breakout) 필터링이 edge 원천.**

**해결할 failure mode**: `price > prior_high_N` 단일 트리거 → 돌파 직후 반락 → SL 걸림. 크립토 24/7 환경에서 pull-back entry 없이 fresh high 즉시 진입 시 WR 30% 미만 관찰.

**실측 근거**: iter1 trend 전략군, confirmation 없는 즉시 진입 8/12 trades가 MFE +100 bps 이상 도달 후 SL(−50 bps) 종료. 합계 +4,557 bps 누락 이익.

---

## 1. Confirmation patterns

confirmation은 독립 사용 금지. **2개 이상 동시 충족** 시에만 진입 허용.

### 1.1 Retest confirmation

**수식**:
```
prior_high = max(close[t-N : t-1])
broke      = close[t] > prior_high
retest_ok  = min(low[t+1 : t+k]) >= prior_high × 0.998
confirmed  = broke AND retest_ok AND all(close[t+1:t+k] >= prior_high)
```

**Python snippet**:
```python
import numpy as np

def retest_confirmed(close: np.ndarray, low: np.ndarray,
                     N: int = 24, k: int = 3) -> bool:
    prior_high = close[-(N + k):-k].max()
    broke = close[-k - 1] > prior_high
    if not broke:
        return False
    retest_ok      = (low[-k:] >= prior_high * 0.998).all()
    no_close_below = (close[-k:] >= prior_high).all()
    return retest_ok and no_close_below
```

**When to use**: 변동성 보통~낮은 구간, 1h 이상 bar 전략
**When NOT to use**: 5분 이하 초단타 — retest window 내 이미 급등하여 진입가 불리
**Calibration**: N=24, k=3. 변동성 높으면 k=2로 단축
**Empirical**: k=3 default로 BTC 1h 2024 데이터 false breakout 38% → 19% 감소

---

### 1.2 Volume confirmation

**수식**:
```
volume_confirmed = volume[t] >= mean(volume[t-20 : t-1]) × multiplier
multiplier default = 1.5
```

**Python snippet**:
```python
def volume_confirmed(volume: np.ndarray, multiplier: float = 1.5) -> bool:
    avg_vol = volume[-21:-1].mean()      # 직전 20-bar 평균
    return float(volume[-1]) >= avg_vol * multiplier
```

**When to use**: 모든 bar 전략 (항상 체크 권장)
**When NOT to use**: low-liquidity 시간대 — volume 절대값 낮아 배율 의미 감소
**Calibration**: multiplier 1.5–2.5. BTC 1h 권장 1.5
**Empirical**: multiplier=2.0 이상이면 entry_pct < 0.3% → 샘플 thin 위험

---

### 1.3 Range expansion (ATR)

**수식**:
```
TR[t]   = max(high[t]-low[t], |high[t]-close[t-1]|, |low[t]-close[t-1]|)
ATR(14) = EMA(TR, 14)
range_expanded = (high[t] - low[t]) >= ATR(14)[t-1] × multiplier
```

**Python snippet**:
```python
def _atr(high: np.ndarray, low: np.ndarray,
         close: np.ndarray, period: int = 14) -> np.ndarray:
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:]  - close[:-1])))
    out = np.zeros(len(tr))
    out[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out

def range_expanded(high: np.ndarray, low: np.ndarray,
                   close: np.ndarray, multiplier: float = 1.5) -> bool:
    atr_vals = _atr(high, low, close)
    bar_range = float(high[-1] - low[-1])
    return bar_range >= float(atr_vals[-2]) * multiplier   # 직전 bar ATR
```

**When to use**: 추세 강도 확인이 필요한 모든 breakout
**When NOT to use**: 갭 발생 구간 — bar_range 과소평가 가능
**Calibration**: multiplier 1.3–1.8
**Empirical**: 1.5 미만 시 false breakout 감소 효과 미미

---

### 1.4 Micro-structure confirmation (LOB 전용)

**수식**:
```
OBI(5) = Σbid_qty[0:5] / (Σbid_qty[0:5] + Σask_qty[0:5])
OFI_roll(10) = Σ(bid_qty[0][t-i] - ask_qty[0][t-i]), i=0..9
confirmed = OBI(5) > threshold AND OFI_roll > 0
```

**Python snippet**:
```python
from collections import deque

class MicroConfirm:
    def __init__(self, obi_threshold: float = 0.20, ofi_window: int = 10):
        self.threshold = obi_threshold
        self._ofi_buf: deque = deque(maxlen=ofi_window)

    def update(self, snap) -> bool:
        # snap: OrderBookSnapshot
        bid_d = snap.bid_qty[:5].sum()
        ask_d = snap.ask_qty[:5].sum()
        obi = bid_d / (bid_d + ask_d) if (bid_d + ask_d) > 0 else 0.5

        self._ofi_buf.append(int(snap.bid_qty[0]) - int(snap.ask_qty[0]))
        ofi_roll = sum(self._ofi_buf)

        return obi > self.threshold and ofi_roll > 0
```

**When to use**: `--market crypto_lob` LOB 데이터 사용 시만
**When NOT to use**: bar OHLCV 전용 환경
**Calibration**: OBI threshold 0.15–0.35. 0.20이 recall/precision 균형
**Requires**: `--market crypto_lob`

---

## 2. Regime gate

진입 전 필수 통과. **하나라도 실패 시 signal 무조건 HOLD.**

**수식**:
```
ema_slope_ok = (EMA(50)[t] - EMA(50)[t-10]) / EMA(50)[t-10] > -0.02
adx_ok       = ADX(14)[t] > 25
vol_ok       = std(returns[-20:]) < IS_vol_p80
```

**Helper functions** (in-file, no external TA library needed):
```python
def _ema(x: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average. out[:period-1] == 0."""
    alpha = 2.0 / (period + 1)
    out = np.zeros_like(x, dtype=float)
    if len(x) < period:
        return out
    out[period - 1] = x[:period].mean()
    for i in range(period, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def _adx(high: np.ndarray, low: np.ndarray,
         close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's ADX. Returns full array; out[:2*period-1] == 0."""
    n = len(close)
    if n < 2 * period:
        return np.zeros(n)
    up   = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm  = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:]  - close[:-1])))
    # Wilder smoothing
    atr  = np.zeros(len(tr));  atr[period - 1]  = tr[:period].sum()
    pdm_s = np.zeros(len(tr)); pdm_s[period - 1] = plus_dm[:period].sum()
    ndm_s = np.zeros(len(tr)); ndm_s[period - 1] = minus_dm[:period].sum()
    for i in range(period, len(tr)):
        atr[i]   = atr[i - 1]   - atr[i - 1]   / period + tr[i]
        pdm_s[i] = pdm_s[i - 1] - pdm_s[i - 1] / period + plus_dm[i]
        ndm_s[i] = ndm_s[i - 1] - ndm_s[i - 1] / period + minus_dm[i]
    pdi = 100 * pdm_s / np.where(atr > 0, atr, 1)
    ndi = 100 * ndm_s / np.where(atr > 0, atr, 1)
    dx  = 100 * np.abs(pdi - ndi) / np.where((pdi + ndi) > 0, pdi + ndi, 1)
    adx = np.zeros(n)
    adx[2 * period - 1] = dx[period - 1:2 * period - 1].mean() if 2 * period - 1 <= len(dx) else 0.0
    for i in range(2 * period, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i - 1]) / period
    return adx
```

> `talib.EMA` / `talib.ADX` 사용 가능한 환경에서는 위 helper를 대체해도 됨.

**Python snippet**:
```python
def regime_pass(close: np.ndarray, high: np.ndarray,
                low: np.ndarray, is_vol_p80: float) -> bool:
    assert len(close) >= 50 and len(high) == len(close) == len(low)

    ema50 = _ema(close, 50)
    slope_ok = (ema50[-1] - ema50[-11]) / ema50[-11] > -0.02

    adx_val = _adx(high, low, close, 14)
    adx_ok  = float(adx_val[-1]) > 25

    returns = np.diff(close) / close[:-1]
    vol_ok  = float(returns[-20:].std()) < is_vol_p80

    return slope_ok and adx_ok and vol_ok
```

| gate | threshold | 실패 시 동작 |
|------|-----------|-------------|
| EMA(50) slope 10-bar | > −2% | HOLD |
| ADX(14) | > 25 | HOLD |
| Vol regime (rolling 20) | < IS p80 | HOLD |

---

## 3. Entry timing 선택 트리

| ADX 수준 | Vol 수준 | 권장 방식 |
|----------|---------|-----------|
| > 30 | 낮음 | Breakout entry (첫 돌파 bar 종가) |
| 25–30 | 보통 | Pullback entry (Fib 0.382 반등 확인) |
| < 25 | — | 진입 금지 (regime gate 차단) |

**Pullback 수식**:
```
fib_382  = prior_high - (prior_high - prior_low) × 0.382
진입 구간: close가 fib_382 ± 0.2% 내에서 반등 확인
```

**Flag / Pennant 최소 consolidation**:
```
flag:    고점·저점 모두 하향 채널 유지, 최소 3 bars
pennant: 고점 낮아지고 저점 높아지는 수렴, 최소 4 bars
진입:    consolidation 상단 돌파 + §1.2 volume confirmation 동시
SL:     consolidation 내 최저가
```

---

## 4. Anti-patterns

1. **저변동장 breakout 오인** — ADX < 20 구간의 prior_high 돌파는 range-bound noise. regime gate에서 구조적 차단.
2. **뉴스 직후 추격 매수** — volume z-score > 5 spike는 재료 소진 직후 가능성. confirmation 없이 진입 시 즉각 반락.
3. **5th wave 진입** — 200-bar 신고가 + RSI > 80 동시 발생 구간은 추세 말단. 진입 금지.
4. **confirmation 과중첩** — 4개 모두 요구 시 entry_pct < 0.1% → 통계적 thin. §5 quick-pick 참조.
5. **retest window 없이 breaking high 순간 진입** — 돌파 bar 종가 즉시 진입은 WR 30% 미만 실측.
6. **Pullback 대기 중 재상승 강제 대기** — Fib 0.382 미달 상태에서 재상승 시 breakout entry로 전환, pullback 고집 금지.
7. **Regime gate 실패 사유 미기록** — 피드백 루프에서 gate 원인 진단 불가. `exit_tag` 또는 로그에 gate 실패 항목 명시.

---

## 5. Parameter cheat (BTC 1h)

| 파라미터 | 권장값 | Range | 주의 |
|----------|--------|-------|------|
| `lookback_high` N | 24 | 12–48 | 높일수록 breakout 희소 |
| `retest_window` k | 3 | 2–5 | 높이면 확실하나 기회 소실 |
| `volume_multiplier` | 1.5 | 1.3–2.5 | 2.5 이상 시 entry_pct < 0.3% |
| `atr_multiplier` | 1.5 | 1.2–2.0 | 갭 구간 주의 |
| `ema_slope_threshold` | −0.02 | −0.05–0 | 음수 클수록 하락장 허용 |
| `adx_threshold` | 25 | 20–35 | 35 이상 시 signal 희박 |
| `obi_threshold` (LOB only) | 0.20 | 0.15–0.35 | crypto_lob 전용 |
| `fib_retrace` | 0.382 | 0.236–0.5 | 0.5 이상은 추세 의심 |

---

## 6. How agents use this

alpha-designer가 `brief.realism.rationale`에 인용하는 패턴:

```yaml
paradigm: trend_follow
confirmation:
  - retest(k=3)          # §1.1
  - volume(mult=1.5)     # §1.2
regime_gate:
  - ema_slope(-0.02)     # §2
  - adx(25)              # §2
entry_method: pullback_fib(0.382)   # §3
source: trend_momentum_entry.md §1.1, §1.2, §2, §3
```

---

## 7. References

- Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling Losers". *Journal of Finance* 48(1).
- Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*. (ADX 원전)
- `knowledge/lessons/` — `trend`, `false_breakout` 키워드 검색
