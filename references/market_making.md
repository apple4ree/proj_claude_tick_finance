# Market Making Cheatsheet

> **Primary consumer**: `execution-designer` when `alpha.paradigm ∈ {market_making, spread_capture}`.
> **Requires**: LOB data (`--market crypto_lob`), maker-fee access (VIP or near-rebate).

---

## 0. Economic reality check

MM edge = half-spread − adverse selection − fee_net.

**BTC/USDT Binance spot 기준**:
- half-spread ≈ 0.07 bps (spread ~0.13 bps / 2)
- adverse selection ≈ 2-5 bps (취약한 가격 움직임에 노출)
- fee_net (maker VIP 1+): 0 to −0.5 bps

→ **Expected EV per round-trip ≈ 0.07 − 3 + 0 ≈ -3 bps** (unfavorable under default assumptions!)

**MM becomes viable when**:
- Maker rebate > adverse selection (VIP 9 MM 티어 -1 bp rebate)
- OR low-volatility regime (adverse selection drops to 0.5-1 bp)
- OR wider spread coins (altcoins with 2-10 bps typical spread)

**Altcoin example** (SOL/USDT with ~1 bp spread):
- half-spread = 0.5 bp
- adverse selection ~1 bp
- fee_net −0.5 bp → EV per round-trip ≈ 0 bps (break-even, depends on regime)

---

## 1. Basic quoting patterns

### 1.1 Symmetric fixed-spread quotes

```
quote_bid = mid − half_spread
quote_ask = mid + half_spread
half_spread = k × observed_spread / 2  (k = 0.5-1.5)
```

단순 + 직관적. 모든 시간에 같은 비율로 quote.

**문제**: inventory 축적 (한쪽만 fill 되면 편향) — 다음 §1.2.

### 1.2 Avellaneda-Stoikov reservation price

**수식**:
```
r(t) = S(t) − q × γ × σ² × (T − t)

q    = current inventory (positive = long, negative = short)
γ    = risk aversion [0.01, 5.0], higher = flatter quotes
σ²   = variance per time unit
T-t  = time horizon for risk-free shutdown

quote_bid(t) = r(t) − δ_bid
quote_ask(t) = r(t) + δ_ask

optimal δ = half_spread_ref = (γ × σ² × (T-t)) / 2 + (1/γ) × ln(1 + γ/k)
```

**실용 simplification** (crypto 24/7이라 T-t = large constant):
```python
def as_reservation(mid, inventory, sigma, gamma=0.5):
    inventory_adjustment = inventory * gamma * sigma**2
    return mid - inventory_adjustment

def as_quotes(mid, inventory, sigma, spread, gamma=0.5):
    r = as_reservation(mid, inventory, sigma, gamma)
    half_offset = spread / 2 + 0.5 * gamma * sigma**2
    return r - half_offset, r + half_offset  # bid, ask
```

**효과**: long inventory 쌓이면 bid는 낮아져 새 매수 낮음, ask는 낮아져 sell-off 재촉 → inventory 0 수렴.

### 1.3 Volume-weighted reservation

Inventory + volume imbalance 둘 다 반영:
```python
reservation = microprice + inventory_adjustment
  # microprice 자체가 bid/ask volume-weighted mid
```

Avellaneda-Stoikov 보다 약간 더 reactive.

---

## 2. Queue-position-aware entry

Passive LIMIT은 queue 뒤에 있으면 체결 안 됨. **Queue position 우선 전략**:

### 2.1 Price-improve (go in front)

```python
# quote 1 tick inside best bid
quote_bid = best_bid + tick_size
```

**Pros**: queue 0, 최우선 fill.
**Cons**: 스프레드 내부에 있어 adverse selection 최대 (가격이 반대로 움직여야 fill).

### 2.2 Back-of-queue

```python
quote_bid = best_bid  # join at best
```

**Pros**: fill 되면 이익 조건 좋음 (가격 반전).
**Cons**: 기다리는 동안 mid 움직이면 stale 되고 cancel 필요.

### 2.3 Hybrid (time-in-queue tracking)

```python
# submit at best bid; if not filled in N ticks, cancel and re-submit at bid + tick
TTL_TICKS = 30
if my_queue_pos > TTL_TICKS_FILLED_ELSEWHERE:
    cancel(my_order)
    submit(best_bid + tick_size)  # re-enter price-improve
```

---

## 3. Exit (close inventory) mechanics

MM 의 exit은 **opposite-side passive LIMIT**:
```
entered long at bid → exit by passive sell at ask
entered short at ask → exit by passive buy at bid
```

**Exit urgency escalation**:
```
t = 0:       passive LIMIT at opposite best (patient)
t = 5 ticks: LIMIT 1-tick inside (aggressive maker)
t = 20 ticks: marketable LIMIT 2-tick inside (near-taker)
t = 30 ticks: MARKET (forced exit, taker fee, maximum urgency)
```

**Inventory cap**:
```python
MAX_INVENTORY_USD = 10_000
if abs(position_value) > MAX_INVENTORY_USD:
    pause_new_quotes_same_side()  # stop accumulating
```

---

## 4. Adverse selection mitigation

**Observation**: MM fill이 mid move 직후에 집중 — informed traders pick off stale quotes.

**방어 patterns**:

### 4.1 Volatility pause

```python
recent_returns = mid.pct_change().tail(20)
if recent_returns.std() > threshold:
    # pause quoting; wait for volatility cluster to end
    continue
```

### 4.2 OBI-skew guard

```python
# cancel quotes when book is heavily skewed against you
if my_side == "bid" and obi(5) < -0.4:
    cancel_all()  # downward pressure; don't buy
```

### 4.3 Spread regime check (from fee_aware_sizing.md §5)

```python
if spread_bps < minimum_viable:  # e.g. 1 bp
    pause()  # insufficient edge
```

---

## 5. Typical parameters (BTC/USDT, Binance VIP 1+ maker)

```yaml
params:
  # Entry
  quote_offset_bps: 0.15       # half-spread quote from fair value
  min_spread_to_quote_bps: 0.3  # pause if spread too tight
  gamma_risk_aversion: 0.5     # AS gamma
  inventory_window_sec: 300    # for volatility σ² estimate
  max_inventory_usd: 5000

  # Exit
  exit_ttl_ticks: 30           # re-submit if not filled
  exit_urgency_ticks: [10, 20, 30]  # escalation schedule
  force_market_exit_ticks: 50  # absolute max hold

  # Risk gates
  pause_on_vol_std_threshold: 5e-4  # 1-min std
  pause_on_obi_abs: 0.4
```

---

## 6. Anti-patterns

1. **Taker fee 가정으로 MM 설계** — 대부분 MM은 maker 이므로 fee 가정 잘못하면 EV 양수 위장.
2. **Spread 작아도 무조건 quoting** — 1 bp 미만 spread면 대부분 loss. 최소 spread gate 필수.
3. **Inventory 추적 없이 대칭 quoting** — 한쪽 체결 지속 시 큰 방향 노출.
4. **ATR / σ 데이터 없이 Avellaneda-Stoikov 적용** — 파라미터 튜닝 임의성만 증가.
5. **Binance taker_buy_base를 order direction 직접 추정으로 사용** — aggregated metric, tick-level 아님.

---

## 7. Empirical prototype (iter candidate)

```python
# Pseudo-code for first MM strategy
class SimpleMM:
    def __init__(self, max_inventory=5000):
        self.inventory = 0
        self.max_inventory = max_inventory
        self.sigma_est = EWMStd(half_life_sec=300)
        
    def on_tick(self, snap, ctx):
        spread = snap.spread_bps
        if spread < 0.3:
            return []  # too tight
        
        obi5 = obi(snap, depth=5)
        if abs(obi5) > 0.4:
            return [cancel_all()]  # skewed, wait
        
        sigma = self.sigma_est.value
        mid = snap.mid
        gamma = 0.5
        res_price = mid - self.inventory * gamma * sigma**2
        half = spread / 2 + 0.5 * gamma * sigma**2
        
        orders = []
        if abs(self.inventory) < self.max_inventory:
            orders.append(LIMIT_BUY(price=res_price - half, ttl_ticks=30))
        if abs(self.inventory) < self.max_inventory:
            orders.append(LIMIT_SELL(price=res_price + half, ttl_ticks=30))
        return orders
```

---

## 8. References

- Avellaneda, M. & Stoikov, S. (2008). "High-frequency trading in a limit order book." Quantitative Finance 8(3).
- Cartea, Á., Jaimungal, S., Penalva, J. (2015). "Algorithmic and High-Frequency Trading." Cambridge.
- Guéant, O. (2016). "The Financial Mathematics of Market Liquidity."

Binance-specific:
- Fee schedule: https://www.binance.com/en/fee/schedule
- Market maker program: VIP 9+ requires $25B/mo volume (not achievable for retail)
