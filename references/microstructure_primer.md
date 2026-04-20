# Microstructure Primer (LOB-aware)

> **Primary consumer**: `alpha-designer` when `paradigm ∈ {market_making, spread_capture}` or `--market crypto_lob`.
> **Focus**: LOB-derived signals with formulas. Supplements `engine.signals.SIGNAL_REGISTRY`.

---

## 0. Snapshot anatomy

```
OrderBookSnapshot (10-level, from engine.data_loader):
    ask_px[0..9]   increasing prices, level 0 = best ask
    ask_qty[0..9]  volume at each level
    bid_px[0..9]   decreasing prices, level 0 = best bid
    bid_qty[0..9]
```

Spread = `ask_px[0] − bid_px[0]` (always ≥ 1 tick on Binance; BTC/USDT 1 cent = ~0.13 bps at $75k).

---

## 1. Signal formulas

### 1.1 Order Book Imbalance (OBI)

Already in `SIGNAL_REGISTRY["obi"]`:
```
OBI(n) = (Σ bid_qty[0..n-1] − Σ ask_qty[0..n-1]) / (Σ bid_qty[0..n-1] + Σ ask_qty[0..n-1])
       ∈ [−1, +1]
+1 = all demand (heavy bid)
−1 = all supply (heavy ask)
 0 = balanced
```

**Depth choice**:
- `obi(1)` — top-of-book only; very noisy, high-frequency sensitive
- `obi(5)` — balanced; standard choice for directional signal
- `obi(10)` — deep; changes slowly, better for regime detection

Empirical (iter1 BTC 26 min sample): obi(5) mean +0.235, std 0.510, range [-0.85, +1.00].

### 1.2 Microprice

Already in `SIGNAL_REGISTRY["microprice"]`:
```
microprice = (ask_px[0] × bid_qty[0] + bid_px[0] × ask_qty[0]) / (ask_qty[0] + bid_qty[0])
```

**Interpretation**: weighted mid based on top-of-book volumes. `microprice > mid` means bid side heavier → short-term upward pressure.

**Signal**: `sign(microprice − mid)` — directional indicator independent of spread.

### 1.3 Microprice-mid deviation (bps)

```
microprice_diff_bps = (microprice − mid) / mid × 10000
```

Typically |microprice_diff_bps| < 1 bp in liquid markets, but can spike to 5-10 bps during imbalance events.

### 1.4 Spread in bps

`SIGNAL_REGISTRY["spread_bps"]`:
```
spread_bps = (ask_px[0] − bid_px[0]) / mid × 10000
```

**Regime classification** (BTC/USDT typical):
- < 0.2 bps: ultra-tight (most of day)
- 0.2–1 bps: normal
- 1–5 bps: elevated (news / volume shock)
- > 5 bps: stress event

### 1.5 Total imbalance (full book)

`SIGNAL_REGISTRY["total_imbalance"]`:
```
total_imbalance = (total_bid_qty − total_ask_qty) / (total_bid_qty + total_ask_qty)
```

More stable than obi(1) or obi(5); used as regime filter (e.g., only trade when |total_imbalance| < 0.3 → market is balanced).

### 1.6 Depth slope / shape asymmetry (manual, not in registry)

```python
def depth_slope(snap, depth=5):
    # how fast does depth grow moving away from best?
    bid_cumsum = np.cumsum(snap.bid_qty[:depth])
    ask_cumsum = np.cumsum(snap.ask_qty[:depth])
    # slope = qty at level N vs level 1
    bid_slope = bid_cumsum[-1] / max(1, bid_cumsum[0])
    ask_slope = ask_cumsum[-1] / max(1, ask_cumsum[0])
    return bid_slope - ask_slope  # positive = bid side builds faster = absorption
```

### 1.7 Queue position estimate (for passive LIMIT)

Not a signal, but critical for market-making execution design:
```
queue_ahead_at_bid = sum of qty at bid_px[0] that was there BEFORE our order
```

`engine/simulator.py`의 `queue_ahead` 모델이 이걸 auto-track (우리가 submit할 때 bid_qty[0] 를 back-of-queue 로 간주).

**Fill probability** 추정:
```
P(fill in N ticks) ≈ 1 − exp(−λN / queue_ahead)
  where λ = rate of fills at that level (trades/tick)
```

---

## 2. Order Flow Imbalance (OFI) — **primitive 아님, 수동 구현 필요**

**수식** (Cont & Kukanov 2014):
```
OFI(t) = [bid_qty[0](t) − bid_qty[0](t−1)] × I(bid_px[0](t) >= bid_px[0](t−1))
       - [ask_qty[0](t) − ask_qty[0](t−1)] × I(ask_px[0](t) <= ask_px[0](t−1))
```

**Interpretation**:
- bid_px 올라가면서 bid_qty 늘면 → buyer pressure (+)
- ask_px 내려가면서 ask_qty 늘면 → seller pressure (−)

**왜 유용한가**: OBI는 "현재 상태", OFI는 "변화율". 단기 방향성 예측에 OBI보다 강함 (특히 tick 레벨).

**Python snippet** (rolling OFI):
```python
def compute_ofi(snaps, window=10):
    ofi_series = np.zeros(len(snaps))
    for t in range(1, len(snaps)):
        b_curr = snaps[t].bid_qty[0]; b_prev = snaps[t-1].bid_qty[0]
        a_curr = snaps[t].ask_qty[0]; a_prev = snaps[t-1].ask_qty[0]
        bpx_curr = snaps[t].bid_px[0]; bpx_prev = snaps[t-1].bid_px[0]
        apx_curr = snaps[t].ask_px[0]; apx_prev = snaps[t-1].ask_px[0]
        delta_b = (b_curr - b_prev) if bpx_curr >= bpx_prev else 0
        delta_a = (a_curr - a_prev) if apx_curr <= apx_prev else 0
        ofi_series[t] = delta_b - delta_a
    # smoothed
    return pd.Series(ofi_series).rolling(window).sum()
```

---

## 3. VPIN (Volume-synchronized Probability of Informed Trading)

Used as **toxicity gauge** — high VPIN = informed traders are around, retreat.

**Simplified**:
```python
# bucket by equal volume V; within each bucket, classify trades as buy/sell via tick rule
# VPIN = |buy_vol - sell_vol| / V, averaged over last N buckets
```

**Practical**:
- VPIN > 0.3 → "toxic" regime; pause MM / widen quotes
- VPIN < 0.1 → calm regime; tighten quotes

Binance doesn't directly expose trade direction, but `taker_buy_base / volume` is a proxy.

---

## 4. Common MM signals (for market_making paradigm)

### 4.1 Fair value estimate

```
fair_value = w × microprice + (1 − w) × mid
  w ∈ [0.5, 1.0] — higher w = more trust in microprice
```

**Use**: quote bid = fair_value − k × spread/2; quote ask = fair_value + k × spread/2.

### 4.2 Inventory skew

**문제**: MM이 한쪽에 쏠리면 market move에 노출.

**수식** (Avellaneda-Stoikov simplified):
```
reservation_price = mid − q × γ × σ² × (T − t)
  q = current inventory (signed)
  γ = risk aversion (0.1-1.0)
  σ² = volatility estimate
  T - t = time remaining in trading session

quote_bid = reservation_price − spread/2
quote_ask = reservation_price + spread/2
```

즉 long inventory 많으면 bid는 더 낮게, ask는 더 낮게 → 새 매수 줄고 매도 늘림.

### 4.3 Spread-capture regime check

```python
# only quote when half-spread > expected adverse_selection + fee_per_side
half_spread_bps = spread_bps / 2
adv_sel_bps = 2.0  # empirical estimate for BTC 1min
maker_fee_bps = 0  # assume VIP maker rebate-neutral
ok_to_quote = half_spread_bps > adv_sel_bps + maker_fee_bps
```

---

## 5. Common mistakes

1. **OBI(1) over OBI(5)** — top-of-book 는 작은 이탈로 symbol flip 이 일어나 noise가 많음. Depth 5+ 권장.
2. **Spread_bps를 absolute bps 로 비교** — 심볼 간 mid 스케일이 다르므로 (BTC vs ALTS) bps 정규화 필수.
3. **Microprice 에 depth 1만 사용** — level 2-3 까지 가중하면 더 안정적.
4. **OFI 계산 시 tick 대비 price 조건 빠뜨림** — `if bid_px[0] stayed same` 무시하면 side-step 이동이 버져됨.
5. **Queue position estimate 없이 passive LIMIT 기대값 계산** — fill rate 추정이 무의미.

---

## 6. Quick-pick table

| 목적 | Primary signal | Secondary |
|---|---|---|
| Short-term direction (seconds) | OFI rolling(10) | microprice_diff_bps |
| Medium (minutes) | obi(5) | total_imbalance |
| Regime filter | total_imbalance magnitude | spread_bps percentile |
| MM fair value | microprice | + inventory skew |
| Toxicity gauge | taker_buy_base / volume (proxy VPIN) | spread widening |

---

## 7. How to use in design

`alpha-designer` (LOB paradigm):
- Primary signal: `obi(5)` 또는 `microprice` 또는 self-implemented `OFI`
- `brief_realism.signals_needed` 에 해당 primitive 이름들 (SIGNAL_REGISTRY에 있는 건 그대로, OFI는 `missing_primitive`로 표기)
- Entry condition: `obi(5) > 0.3 AND microprice > mid`

`execution-designer` (MM paradigm):
- Queue position 기반 fill rate 추정 for `ttl_ticks` 설정
- Inventory skew 반영한 exit rule

---

## 8. References (for deeper reading)

- Cont, R. & Kukanov, A. (2014). "Optimal order placement in limit order markets"
- Avellaneda, M. & Stoikov, S. (2008). "High-frequency trading in a limit order book"
- Harris, L. (2003). "Trading and Exchanges: Market Microstructure for Practitioners"

Papers는 `literature/papers/` 에 있으면 참조. Primer는 공식 + code 위주.
