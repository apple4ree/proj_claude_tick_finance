# Exit Design Cheatsheet

> **Primary consumer**: `execution-designer` agent (also useful for `alpha-designer` when framing hypothesis).
> **Focus**: MFE/MAE-aware exit calibration — preventing the "peak-then-give-back" pattern that iter1 exhibited.
> **Format**: Concrete formulas + Python snippets + when-to-use decision table. Not theory.

---

## 0. 문제 (The problem this document addresses)

**Give-back pattern**: strategy가 보유 중 실제로 수익을 찍었지만 (MFE > 0) exit에서 반납하거나 심지어 손실로 끝나는 현상.

측정 지표:
- **MFE (Maximum Favorable Excursion)**: 포지션 보유 동안 peak PnL (bps)
- **MAE (Maximum Adverse Excursion)**: 보유 동안 worst PnL
- **capture_pct = realized / MFE × 100**: < 50%면 give-back, < 0%면 MFE를 찍고 반대방향으로 exit

`analysis_trace.md`의 Give-Back Summary 블록에서 자동 계산됨.

---

## 1. iter1 case study (실제 데이터)

BTC 1h `roc_168h <= -0.056` 전략. 12 roundtrips IS window.

| # | tag | realized | MFE | MAE | capture_% | 진단 |
|---|---|---|---|---|---|---|
| 0 | time_stop | -288 | **+157** | -324 | -190% | MFE 157 찍고 반납 + 실손 |
| 1 | time_stop | -63 | **+336** | -197 | -22% | MFE 336 전체 반납 |
| 4 | time_stop | +94 | **+384** | -430 | +22% | MFE 384 중 90bp만 캡처 |
| 6 | time_stop | +220 | **+548** | -146 | +38% | 피크 절반 이상 반납 |
| 8 | sl_hit | -480 | **+292** | -480 | **-164%** | 올랐다가 SL (falling knife after bounce) |
| 11 | time_stop | +47 | **+299** | -354 | +16% | 84% 반납 |

**결과**: avg MFE **+379 bps**, avg realized **-46 bps**, sum missed profit = **+4557 bps** (전체 IS 기간에서 놓친 상방).

**원인 분해**:
- PT 1312 bps → **phantom** (12회 중 단 2회만 근접). MFE p75 ≈ +550 bps이므로 1312는 distribution 바깥.
- Trailing activation 600 bps → **너무 높음**. MFE 평균 379 < 600 → 거의 활성화 안 됨.
- Time stop 168h → 중간에 피크 나왔어도 끝까지 버티다 반납.
- SL 450 bps → **MFE +292 → SL -480** (trade #8) 같은 "먼저 올랐다가 나중에 하락해서 SL"에 무방비.

---

## 2. Exit pattern library

### 2.1 Scale-out (partial exits)

**수식**:
```
PT1 = entry × (1 + k1 × σ_window)
PT2 = entry × (1 + k2 × σ_window)  where k2 > k1

at PT1:  close 50% of position
at PT2:  close remaining 50%
```

**캘리브레이션 rule of thumb**:
- k1 = **MFE p50** (50% winners가 도달하는 수준) — 실현율 높음
- k2 = **MFE p75** (우상향 tail capture)
- σ_window = IS 기간 hourly std (bps 기준)

**Python snippet**:
```python
# In strategy.py generate_signal loop, after entering:
# Track MFE p50 / p75 from brief's entry_stats OR set conservatively
PT1_BPS = 300    # 50% exit (easy target, high hit rate)
PT2_BPS = 800    # 50% exit (stretch target)

if in_position:
    gain_bps = (px - entry_price) / entry_price * 1e4
    if not pt1_hit and gain_bps >= PT1_BPS:
        qty_to_close = position_qty // 2
        signal[i] = 0 if qty_to_close == position_qty else partial_flag
        pt1_hit = True
    elif pt1_hit and not pt2_hit and gain_bps >= PT2_BPS:
        signal[i] = 0  # close remaining
```

**언제 쓰면 좋은가**: MFE 분포가 넓고 peak가 중간에 자주 나오는 상황. Iter1의 Trade #4, #6, #11은 PT1=300 만 있었어도 의미 있는 capture.

**언제 쓰지 말 것**: Signal이 강한 모멘텀성 (PT1에서 50% 떼는 건 상승 추세를 prematurely 끊음). trend-follow paradigm엔 부적합.

### 2.2 ATR-based dynamic trailing

**수식**:
```
ATR(n) = rolling mean of |high - low| over n bars
trailing_activation = entry + α × ATR(n)
trailing_distance   = β × ATR(n)
```

**캘리브레이션**:
- α = 0.5~1.0 (낮을수록 일찍 활성화)
- β = 1.5~2.5 (노이즈 회피 vs 반납 방지 trade-off)
- n = signal의 고유 주기에 맞춤 (1h bar 전략 → n=24 (1일) or n=168 (1주))

**Python snippet**:
```python
def compute_atr(df, n=24):
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low']  - df['close'].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()

atr = compute_atr(df, n=24)
# in strategy loop:
atr_at_entry = atr.iloc[entry_idx]
act_threshold = entry_price + 0.7 * atr_at_entry
trail_dist    = 2.0 * atr_at_entry / entry_price * 1e4   # in bps
```

**언제 쓰면 좋은가**: 변동성이 regime-dependent하고 fixed-bps trailing이 일부 기간에만 맞을 때. 자동 adapt.

**언제 쓰지 말 것**: 데이터 자체가 적어 ATR이 noisy할 때 (예: 100 bars 미만). Fixed 사용.

### 2.3 Time-weighted SL tightening

**수식**:
```
SL(t) = SL_initial × (1 - 0.5 × (t / horizon))
# t = elapsed bars since entry
# horizon = time_stop_ticks
```

**의도**: 보유 시간이 길어질수록 SL을 조여서 "evening stop" — 장시간 buy-and-hold의 drawdown 제한.

**Python snippet**:
```python
elapsed_frac = bars_held / time_stop_ticks
sl_current = sl_initial * (1 - 0.5 * elapsed_frac)
if loss_bps >= sl_current:
    exit_now = True
    exit_reason = "sl_time_tightened"
```

**언제 쓰면 좋은가**: Iter1처럼 time_stop까지 버티다가 MAE에 당하는 패턴. 시간에 비례한 risk budget 축소.

**언제 쓰지 말 것**: 단기 horizon (< 20 bars) 전략. SL tightening 효과 거의 없음.

### 2.4 Break-even shift (BE stop)

**수식**:
```
if gain_bps >= BE_THRESHOLD:
    sl_price = entry_price  # SL moved to entry
```

**캘리브레이션**:
- BE_THRESHOLD = 2 × fee (2 × 4 bps = 8 bps on Binance taker) + small buffer
- 예: threshold 20 bps → "20 bps 이익 본 후에는 최소 무손실 보장"

**언제 쓰면 좋은가**: "Trade #8처럼 MFE +292 찍고 SL -480"의 직접 해독제. MFE가 20 bps만 찍어도 이후 최악의 경우 break-even.

**Python snippet**:
```python
BE_THRESHOLD = 20  # bps
be_armed = False
# in loop:
if not be_armed and gain_bps >= BE_THRESHOLD:
    be_armed = True
if be_armed and px <= entry_price:  # hit break-even shift
    exit_now = True
    exit_reason = "be_stop"
```

### 2.5 Re-entry after stop-out (cooldown logic)

**수식**:
```
if last_exit_tag == "sl_hit" and elapsed_since_sl > cooldown_bars:
    allow_re_entry if signal_reactivates
```

**캘리브레이션**:
- cooldown_bars = 2-5 (초단기) 또는 horizon/4 (장기)
- 목적: SL로 인한 "shook out" 후 signal이 재발하면 다시 진입

**Python snippet** (간단):
```python
# current code has max_entries_per_session blocking re-entry
# replace with cooldown-based logic:
COOLDOWN = 5  # bars
last_sl_bar = -np.inf

if exit_reason == "sl_hit":
    last_sl_bar = i

# at entry check:
if (i - last_sl_bar) < COOLDOWN:
    continue  # skip re-entry
```

**언제 쓰면 좋은가**: iter1 trade #8/9/10 처럼 연속 SL이 발생했는데 사실 signal은 여전히 oversold였던 경우. 현 max_entries_per_session=1 은 이 기회를 전부 차단.

### 2.6 Partial hedge on time stop

**수식**:
```
at t = 0.7 × horizon:
    if gain_bps > 0:
        close 50%  # lock partial profit
    else:
        hold all
```

**의도**: Time stop 만기 전에 현재 상태에 따라 partial close. Trade #6처럼 "MFE 548 → final 220"을 막을 수 있음 (70% 지점에서 반이라도 lock).

---

## 3. Decision table — 어떤 pattern을 언제 쓸까

| iter1-style failure | 권장 pattern | 보조 |
|---|---|---|
| PT too far (phantom) | **Scale-out** + lower PT based on MFE p50/p75 | Dynamic trailing |
| Early-mover MFE then SL | **Break-even shift** (20 bps 임계) | Scale-out @ PT1 |
| Time stop에서 반납 | **Time-weighted SL** + partial hedge | Dynamic trailing |
| 연속 SL (oversold 계속) | **Cooldown re-entry** (remove session lockout) | — |
| Trailing 활성화 안 됨 | Lower α to 0.5 × ATR or use **MFE p50 quantile** | — |

---

## 4. iter1 counterfactual — 이 reference를 썼다면?

**수정된 execution spec** (for BTC 1h roc_168h strategy):

```yaml
params:
  # BEFORE
  profit_target_bps: 1312.07      # phantom
  stop_loss_bps: 450.79
  trailing_stop: true
  trailing_activation_bps: 600.0
  trailing_distance_bps: 300.0

  # AFTER (using this reference)
  pt1_bps: 300                    # scale-out level 1 (MFE p50)
  pt2_bps: 800                    # scale-out level 2 (MFE p75)
  stop_loss_bps: 450
  break_even_threshold_bps: 20    # new: BE shift
  trailing_activation_bps: 200    # lowered from 600 (to MFE avg)
  trailing_distance_bps: 150      # tightened
  time_weighted_sl: true          # new
  cooldown_after_sl_bars: 5       # new: replace session lockout
  max_entries_per_session: 5      # loosen (with cooldown)
```

**예상 개선** (근사 계산, 실제로는 iter2에서 검증):

| Trade # | 기존 realized | 개선된 realized (추정) | 개선 |
|---|---|---|---|
| 0 | -288 | BE stop ≈ 0 | +288 |
| 1 | -63 | PT1 caught at +300 (partial +150 avg) | +213 |
| 4 | +94 | PT1 caught = +150 | +56 |
| 6 | +220 | PT1 + PT2 mix ≈ +400 | +180 |
| 8 | -480 | BE stop ≈ 0 (MFE 292 triggered BE) | +480 |
| 11 | +47 | PT1 at +150 | +103 |

**Total ≈ +1320 bps 개선** (부분 추정). 전부 현실화되지는 않지만 방향성은 명확.

---

## 5. Formula reference — 빠른 참조

```
capture_pct       = realized_bps / mfe_bps × 100
give-back_bps     = mfe_bps - realized_bps  (양수면 반납)
break-even thr    = 2 × fee_round_trip + 5 bps buffer
ATR(n)            = mean(|H-L|, |H-C_prev|, |L-C_prev|) rolled over n bars
trailing_activation_bps  ≈ MFE.avg or MFE.p50 (NOT p90)
pt1_bps  (scale-out 1)   ≈ MFE.p50  (realistic, high hit rate)
pt2_bps  (scale-out 2)   ≈ MFE.p75 OR MFE.p90  (aggressive)
```

---

## 6. Anti-patterns (하지 말 것)

1. **PT를 MFE.p99+ 로 설정** — 거의 도달 안 하는 "phantom PT". (iter1 PT 1312의 근본 문제)
2. **Trailing activation을 PT 의 50%+로 설정** — 대부분 trade 가 활성화 조차 못 됨.
3. **SL을 MAE.p95 로 widest 설정** — 겉보기 WR은 오르지만 per-trade 손실 규모가 커져 total risk 폭증.
4. **Scale-out을 momentum 전략에 쓰기** — trend를 조기에 끊음. trend-follow paradigm에서는 단일 trailing이 나음.
5. **Break-even shift를 fee 덜 고려하고 설정** — BE threshold가 fee × 2 미만이면 BE 발동해도 fee로 실손.

---

## 7. How this cheatsheet is used

`execution-designer` agent가 exit_execution 블록 설계할 때:

1. `analysis_trace.md`에서 **Give-Back Summary** 읽기 (parent strategy가 있으면)
2. Pattern library (§2)에서 문제에 맞는 pattern 1-2개 선택
3. 캘리브레이션 수식으로 bps 값 계산 (§3 decision table 참조)
4. `deviation_from_brief.rationale`에 **참조한 pattern 이름 + 사용한 수식**을 명시
   - 예: `"PT1/PT2 scale-out from exit_design.md §2.1, PT1=MFE_p50 (300), PT2=MFE_p75 (800)"`

**Agent가 이 파일을 읽지 않고 exit을 설계한 경우** critic이 `execution_critique.md`에서 give-back score를 보고 이 reference 참조를 **권고** (hard-fail 아님).
