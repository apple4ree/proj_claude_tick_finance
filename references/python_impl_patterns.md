# Python Implementation Patterns

> **Primary consumer**: strategy-coder
> **Secondary consumers**: execution-designer
> **Trigger condition**: python path 전략 구현 시 (항상)
> **Companion references**: `exit_design.md`, `market_making.md`
> **Status**: stable

---

## 0. Core insight

**구현 결함이 알파를 무효화한다. spec이 옳아도 코드가 틀리면 백테스트 데이터는 거짓말을 한다.**

**해결할 failure mode**: snap.mid 기반 SL 모니터링 → 실제 MARKET SELL 체결가(snap.bid_px[0])와 괴리 → SL spec 초과.

**실측 근거**: strat_0028 — spec에 SL=50 bps 설정, 실현 손실 362 bps (7.24× 초과). 원인: SL 체크를 `snap.mid` 기준(`(mid - entry_px) / entry_px * 1e4 <= -50`)으로 수행 → mid는 bid보다 ½ spread만큼 높아 판정 지연 → 체결은 `bid_px[0]` 기준이므로 이미 손실 누적. 올바른 구현은 §2 참조.

---

## 1. Engine API 요약

엔진 실체에 맞춘 정본. 모든 snippet이 이 계약을 따라야 한다.

```python
# engine/data_loader.py — OrderBookSnapshot (dataclass)
@dataclass
class OrderBookSnapshot:
    ts_ns:          int            # nanosecond timestamp
    symbol:         str            # "BTCUSDT" 등
    ask_px:         np.ndarray     # int64[10], level 0 = best ask
    ask_qty:        np.ndarray     # int64[10]
    bid_px:         np.ndarray     # int64[10], level 0 = best bid
    bid_qty:        np.ndarray     # int64[10]
    total_ask_qty:  int
    total_bid_qty:  int
    acml_vol:       int
    session_cls:    str
    antc_px:        int
    antc_qty:       int

    @property
    def mid(self)    -> float:  return (int(self.ask_px[0]) + int(self.bid_px[0])) / 2.0
    @property
    def spread(self) -> int:    return int(self.ask_px[0]) - int(self.bid_px[0])
    # ※ spread_bps 는 property 아님 — 필요 시 (self.spread / self.mid * 1e4) 수동 계산
```

```python
# engine/simulator.py — strategy protocol
from engine.simulator import Order, BUY, SELL, MARKET, LIMIT, CANCEL, Context

class Strategy(Protocol):
    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        ...

# Order dataclass
@dataclass
class Order:
    symbol: str
    side: str | None                   # BUY | SELL | None (CANCEL은 None)
    qty: int
    order_type: str = MARKET           # MARKET | LIMIT | CANCEL
    limit_price: int | None = None     # LIMIT 주문 시 price
    tag: str = ""                      # 자유형 태그 (e.g., "trailing_stop")

# Context — 엔진이 매 tick strategy에게 전달
@dataclass
class Context:
    portfolio:       Portfolio         # 아래 참조
    last_mids:       dict[str, float]  # 심볼 → 직전 mid
    current_ts_ns:   int

# Portfolio / Position 필드
@dataclass
class Position:
    qty:           int = 0
    avg_cost:      float = 0.0
    realized_pnl:  float = 0.0

# 포지션 접근 패턴
pos     = ctx.portfolio.positions.get(sym)     # 없으면 None
pos_qty = pos.qty if pos else 0
entry_px = pos.avg_cost if pos else 0.0        # 평균 진입가
```

**중요 차이** (타 시스템/문서와 혼동 금지):
- 반환값은 `list[Order]` — int (1/0/-1) 아님.
- `ctx.submit_order()` / `ctx.cancel_order()` **없음** — `Order` 인스턴스를 리스트로 반환하면 엔진이 매칭한다.
- `ctx.position`, `ctx.entry_mid`, `ctx.ticks_since_entry`, `ctx.tick_index` **없음** — 필요하면 strategy 내부 state로 수동 추적 (§2, §4 참조).
- CANCEL은 해당 symbol의 **모든 resting LIMIT을 일괄 취소** (order_id 단위 cancel 아님): `Order(sym, side=None, qty=0, order_type=CANCEL, tag="...")`.

---

## 2. SL reference price rule

### 2.1 LONG SL — bid_px[0] 기준 필수

**수식**:
```
entry_px = pos.avg_cost                                    # 평균 진입가
unrealized_bps = (snap.bid_px[0] - entry_px) / entry_px × 10000
exit if unrealized_bps <= -stop_loss_bps AND ticks_held >= 5
```

`ticks_since_entry`는 엔진이 제공하지 않으므로 **strategy 내부에서 수동 추적** (아래 state).

**Python snippet**:
```python
class MyStrategy:
    def __init__(self, spec):
        p = spec.get("params", {})
        self.stop_loss_bps = p.get("stop_loss_bps", 50.0)
        self._ticks_held: dict[str, int] = {}   # sym → 경과 tick

    def on_tick(self, snap, ctx) -> list[Order]:
        sym = snap.symbol
        pos = ctx.portfolio.positions.get(sym)
        pos_qty = pos.qty if pos else 0

        if pos_qty > 0:
            self._ticks_held[sym] = self._ticks_held.get(sym, 0) + 1
            entry_px = float(pos.avg_cost)
            bid0     = float(snap.bid_px[0])
            unrealized_bps = (bid0 - entry_px) / entry_px * 1e4
            if self._ticks_held[sym] >= 5 and unrealized_bps <= -self.stop_loss_bps:
                self._ticks_held[sym] = 0
                return [Order(sym, SELL, pos_qty, MARKET, tag="stop_loss")]
        else:
            self._ticks_held.pop(sym, None)
        return []

# BAD — strat_0028 재현 코드 (사용 금지)
# unrealized_bps = (snap.mid - entry_px) / entry_px * 1e4
# 이유: mid는 bid보다 ½ spread만큼 높아 SL 판정 지연 → 7× 초과 실측
```

**When to use**: LONG 포지션 모든 SL 체크
**When NOT to use**: 엔진이 현재 long-only — SHORT는 적용 범위 밖
**Calibration**: 5-tick latency buffer. 주문 전송→체결 latency 흡수 목적

### 2.2 SHORT SL (참고 — 엔진 확장 시)

현 엔진은 `SELL qty > position qty → rejected`로 short 금지. perpetual futures 모드 도입 시만 활성화.

```python
# if short position allowed:
#   unrealized_bps = (entry_px - snap.ask_px[0]) / entry_px * 1e4
```

---

## 3. Per-symbol spread gate

`OrderBookSnapshot`에 `spread_bps` property는 없으므로 수동 계산.

**수식**:
```
floor_bps    = tick_size / mid_price × 10000
gate_bps    >= floor_bps × 1.5
spread_bps  = snap.spread / snap.mid × 10000   (수동 계산)
skip if spread_bps > gate_bps
```

**Python snippet**:
```python
SPREAD_GATES = {
    "BTCUSDT": 0.30,   # tick_size=0.1, mid~60000 → floor~0.17 bps
    "ETHUSDT": 0.50,   # tick_size=0.01, mid~3000 → floor~0.33 bps
    "SOLUSDT": 1.00,   # tick_size=0.001, mid~150 → floor~0.67 bps
}

def _spread_bps(snap) -> float:
    mid = float(snap.mid)
    return (float(snap.spread) / mid * 1e4) if mid > 0 else 0.0

def spread_ok(sym: str, snap) -> bool:
    gate = SPREAD_GATES.get(sym, 1.0)
    return _spread_bps(snap) <= gate
```

**When to use**: 모든 심볼 진입 전 (항상)
**When NOT to use**: 없음 — skip 불가
**Calibration**: 각 심볼 tick_size / mid_price × 10000 × 1.5 로 자동 계산 권장

---

## 4. Entry gate (time + session)

**수식**:
```
ts_sec = snap.ts_ns // 1_000_000_000 % 86400   (UTC wall-second)
pos    = ctx.portfolio.positions.get(sym)
pos_qty = pos.qty if pos else 0

entry_allowed = entry_start_sec <= ts_sec <= entry_end_sec
                AND entries_today[sym] < max_entries_per_session
                AND pos_qty < max_position_per_symbol × lot_size
                AND sym not in pending_buy
```

**Python snippet** (날짜 경계에서 counter 리셋 포함):
```python
from datetime import datetime, timezone

class MyStrategy:
    def __init__(self, spec):
        p = spec.get("params", {})
        self.entry_start_sec  = p.get("entry_start_time_seconds", 0)
        self.entry_end_sec    = p.get("entry_end_time_seconds", 86_400)
        self.max_entries      = p.get("max_entries_per_session", 3)
        self.max_position     = p.get("max_position_per_symbol", 1)
        self.lot_size         = p.get("lot_size", 1)
        self._entries_today:  dict[str, int] = {}
        self._last_date:      dict[str, str] = {}

    def _entry_allowed(self, snap, ctx) -> bool:
        sym = snap.symbol
        # date-change reset (UTC 기준)
        dt = datetime.fromtimestamp(snap.ts_ns / 1e9, tz=timezone.utc)
        date_str = dt.strftime("%Y%m%d")
        if self._last_date.get(sym) != date_str:
            self._last_date[sym] = date_str
            self._entries_today[sym] = 0

        ts_sec = int((snap.ts_ns // 1_000_000_000) % 86_400)
        if not (self.entry_start_sec <= ts_sec <= self.entry_end_sec):
            return False
        if self._entries_today.get(sym, 0) >= self.max_entries:
            return False
        pos = ctx.portfolio.positions.get(sym)
        pos_qty = pos.qty if pos else 0
        if pos_qty >= self.max_position * self.lot_size:
            return False
        return True
```

**When to use**: 진입 주문 생성 전 항상 호출
**When NOT to use**: 없음
**Calibration**: 크립토는 24/7이지만 시간대별 edge 차이 있음. spec `entry_start_time_seconds` / `entry_end_time_seconds` 파라미터와 연결. **`datetime.now()` 사용 절대 금지** — `snap.ts_ns` 기반만 허용.

---

## 5. Trailing stop state machine

entry price 기준값은 `pos.avg_cost` (엔진이 fill 기반으로 자동 갱신).
`ctx.entry_mid` 같은 필드 **없음** — `avg_cost` 사용.

**수식**:
```
entry_px = pos.avg_cost
mfe_bps  = (snap.mid - entry_px) / entry_px × 10000

INACTIVE → ACTIVE 전환: mfe_bps >= trailing_activation_bps
INACTIVE: fixed SL 적용. peak_mid 갱신 안 함.
ACTIVE:   peak_mid = max(peak_mid, snap.mid)
          drop_bps = (peak_mid - snap.bid_px[0]) / peak_mid × 10000
          exit if drop_bps >= trailing_distance_bps
```

**Python snippet** (sym별 독립 state):
```python
class MyStrategy:
    def __init__(self, spec):
        p = spec.get("params", {})
        self.activation_bps = p.get("trailing_activation_bps", 75.0)
        self.distance_bps   = p.get("trailing_distance_bps", 30.0)
        self.sl_bps         = p.get("stop_loss_bps", 50.0)
        self._trailing_active: dict[str, bool]  = {}
        self._peak_mid:        dict[str, float] = {}
        self._ticks_held:      dict[str, int]   = {}

    def _check_exit(self, snap, ctx) -> list[Order]:
        sym = snap.symbol
        pos = ctx.portfolio.positions.get(sym)
        if pos is None or pos.qty <= 0:
            # reset on flat
            self._trailing_active.pop(sym, None)
            self._peak_mid.pop(sym, None)
            self._ticks_held.pop(sym, None)
            return []

        pos_qty  = pos.qty
        entry_px = float(pos.avg_cost)
        mid      = float(snap.mid)
        bid0     = float(snap.bid_px[0])
        held     = self._ticks_held.get(sym, 0) + 1
        self._ticks_held[sym] = held

        mfe_bps = (mid - entry_px) / entry_px * 1e4 if entry_px > 0 else 0.0
        active  = self._trailing_active.get(sym, False)

        if not active:
            if mfe_bps >= self.activation_bps:
                self._trailing_active[sym] = True
                self._peak_mid[sym]        = mid      # 활성화 시점부터 추적
                return []
            # fixed SL (activation 이전)
            unrealized_bps = (bid0 - entry_px) / entry_px * 1e4 if entry_px > 0 else 0.0
            if held >= 5 and unrealized_bps <= -self.sl_bps:
                return [Order(sym, SELL, pos_qty, MARKET, tag="stop_loss")]
            return []

        # ACTIVE
        peak = max(self._peak_mid.get(sym, mid), mid)
        self._peak_mid[sym] = peak
        drop_bps = (peak - bid0) / peak * 1e4 if peak > 0 else 0.0
        if drop_bps >= self.distance_bps:
            return [Order(sym, SELL, pos_qty, MARKET, tag="trailing_stop")]
        return []
```

**When to use**: MFE 구간이 충분히 있는 전략 (activation_bps 설정 가능)
**When NOT to use**: scalping — MFE 구간 없어 activation 미도달
**Calibration**: activation_bps = stop_loss_bps × 1.5 권장 (SL보다 큰 이익 확보 후 활성화)

---

## 6. TTL + bid-drop cancel

엔진은 per-order cancel 없음 — CANCEL order가 **해당 symbol의 모든 resting LIMIT을 일괄 취소**한다.
절대 tick index도 엔진이 제공하지 않으므로 strategy 내부에서 `self._tick_count[sym]` 수동 추적.

**수식**:
```
tc = self._tick_count[sym]                               # 매 on_tick마다 ++
elapsed = tc - submit_tick
cancel if elapsed >= ttl_ticks
cancel if submit_bid_px - snap.bid_px[0] >= cancel_drop_ticks × tick_size
```

**Python snippet**:
```python
class MyStrategy:
    def __init__(self, spec):
        p = spec.get("params", {})
        self.ttl_ticks         = p.get("entry_ttl_ticks", 20)
        self.cancel_drop_ticks = p.get("cancel_on_bid_drop_ticks", 2)
        self._tick_count:   dict[str, int] = {}
        self._pending_buy:  dict[str, int] = {}    # sym → submit_tick
        self._submit_bid:   dict[str, int] = {}    # sym → bid_px at submit

    def _submit_limit_buy(self, sym, snap, tc, price, qty) -> list[Order]:
        self._pending_buy[sym] = tc
        self._submit_bid[sym]  = int(snap.bid_px[0])
        return [Order(sym, BUY, qty, LIMIT, limit_price=int(price), tag="entry")]

    def _check_cancel(self, snap, tc, tick_size: int) -> list[Order]:
        sym = snap.symbol
        if sym not in self._pending_buy:
            return []
        elapsed  = tc - self._pending_buy[sym]
        bid_drop = self._submit_bid[sym] - int(snap.bid_px[0])

        if elapsed >= self.ttl_ticks:
            del self._pending_buy[sym]
            del self._submit_bid[sym]
            return [Order(sym, None, 0, order_type=CANCEL, tag="ttl_cancel")]
        if bid_drop >= self.cancel_drop_ticks * tick_size:
            del self._pending_buy[sym]
            del self._submit_bid[sym]
            return [Order(sym, None, 0, order_type=CANCEL, tag="bid_drop_cancel")]
        return []

    def on_tick(self, snap, ctx) -> list[Order]:
        sym = snap.symbol
        tc  = self._tick_count.get(sym, 0) + 1
        self._tick_count[sym] = tc
        # ... cancel check → latency guard → entry/exit
```

**When to use**: LIMIT 주문 사용하는 모든 전략
**When NOT to use**: MARKET-only 전략 (즉시 체결)
**Calibration**: `ttl_ticks` = 10–30, `cancel_drop_ticks` = 2–5. `tick_size`는 §10 안내대로 bid_px diff에서 추정하거나 spec에서 상수로 주입.

---

## 7. Max-entries + position cap

엔진은 fill이 완료된 시점에 `Portfolio.positions[sym].qty`를 자동 갱신.
`entries_today` 카운터는 **BUY 주문을 submit하는 시점**에 증분 (fill 확정 전).
나중에 cancel되면 감소시키지 말 것 (중복 counting보다 안전).

```python
def _submit_entry_and_count(self, snap, tc, qty: int, limit_price: int) -> list[Order]:
    sym = snap.symbol
    self._entries_today[sym] = self._entries_today.get(sym, 0) + 1
    self._pending_buy[sym]   = tc
    self._submit_bid[sym]    = int(snap.bid_px[0])
    return [Order(sym, BUY, qty, LIMIT, limit_price=limit_price, tag="entry")]

def _position_cap_ok(self, sym, ctx) -> bool:
    pos = ctx.portfolio.positions.get(sym)
    pos_qty = pos.qty if pos else 0
    # pending BUY가 아직 체결 전이어도 double-fill 방지 위해 block
    if sym in self._pending_buy:
        return False
    return pos_qty < self.max_position * self.lot_size
```

**Calibration**: `max_entries_per_session` default 10, `max_position_per_symbol` default 1.
`ctx.portfolio.positions[sym].qty`는 **read** 용도로만 사용 — **쓰기 금지** (엔진 상태 불일치 유발).

---

## 8. Anti-patterns

1. **Look-ahead** — `snap`을 t+1 기준으로 entry 판단. 엔진은 현재 tick snap만 전달, 미래 snap 접근 시 KeyError 또는 stale 데이터.
2. **Cancel 후 pending state 미삭제** — CANCEL Order 반환 후 `self._pending_buy[sym]` 삭제 누락 → 다음 tick에 중복 CANCEL 시도, entries_today 이중 카운팅.
3. **Trailing activation 전 peak 갱신** — INACTIVE 상태에서 `peak_mid` 갱신 시 소폭 상승에 trailing 발동 → 조기 청산.
4. **snap.mid 기반 SL** — strat_0028 재현. `snap.bid_px[0]` 사용 필수 (§2).
5. **Entry gate에 `datetime.now()`** — 엔진 시계(`snap.ts_ns`)와 wall-clock 불일치로 backtest 비결정성. **절대 금지.**
6. **Multi-symbol 전략에서 state 공유** — `self._trailing_active`, `self._peak_mid`, `self._pending_buy` 등을 **반드시 `dict[str, ...]`** 으로 symbol별 분리.
7. **`ctx.portfolio.positions[sym].qty` 직접 수정** — read-only 규약. 수정 시 엔진 fill 적용과 충돌해 equity 계산 불일치.
8. **`OrderBookSnapshot.spread_bps` 직접 접근** — property 없음. `snap.spread / snap.mid * 1e4` 수동 계산 (§3).
9. **Order list에 int/tuple 넣기** — `on_tick`은 `list[Order]` 반환. int 1/0/-1 또는 (side, qty) tuple 사용 시 runtime type error.
10. **CANCEL에 side/qty 지정** — CANCEL은 `Order(sym, side=None, qty=0, order_type=CANCEL)` 형태. side를 BUY/SELL로 주면 엔진이 무시하거나 오동작 가능.

---

## 9. Testing checklist

| Invariant | 검증 방법 |
|-----------|-----------|
| SL 실현 손실 ≤ spec × 1.1 | `report.json` → `invariant_violations` 필드 |
| `ticks_since_entry < 5` 구간 SL 미발동 | entry tick 기준 첫 5 tick 슬라이스 필터링 |
| trailing peak는 ACTIVE 전환 이후 tick부터 기록 | activation tick 이전 `peak_mid` == 0.0 확인 |
| cancel 후 `pending == None` | cancel 다음 tick에 `check_cancel` 재진입 확인 |
| per-symbol spread gate ≥ floor × 1.5 | tick_size 테이블과 대조 |
| `entries_this_session` ≤ `max_entries_per_session` | 일 단위 집계 |
| `ctx.position` 직접 수정 없음 | `grep "ctx.position ="` — 할당문 없어야 함 |

---

## 10. Tick size estimation

엔진은 tick_size를 직접 제공하지 않음. bid_px diff에서 추정하거나 spec.params에 상수로 주입.

```python
from collections import deque

class MyStrategy:
    def __init__(self, spec):
        self._bid_buf: dict[str, deque] = {}          # sym → recent bid_px[0]

    def _update_bid_buf(self, snap):
        sym = snap.symbol
        buf = self._bid_buf.setdefault(sym, deque(maxlen=20))
        buf.append(int(snap.bid_px[0]))

    def _tick_size(self, sym: str, fallback: int = 1) -> int:
        buf = self._bid_buf.get(sym)
        if not buf or len(buf) < 2:
            return fallback
        diffs = [abs(buf[i] - buf[i - 1]) for i in range(1, len(buf))]
        nonzero = [d for d in diffs if d > 0]
        return min(nonzero) if nonzero else fallback
```

권장: spec.yaml `params.tick_size_by_symbol: {BTCUSDT: 1, ETHUSDT: 1, ...}`를 상수로 주입하는 쪽이 간단하고 결정적.

---

## 11. References

- `engine/data_loader.py` — `OrderBookSnapshot` 정확한 필드 시그니처
- `engine/signals.py` — `SIGNAL_REGISTRY` primitive 목록 (`obi`, `microprice` 등)
- `engine/simulator.py` — `Order` / `Context` / `Portfolio` 구조, `walk_book`, latency 모델
- `engine/spec.py` — spec.yaml 파라미터 네이밍 convention
- `.claude/agents/strategy-coder.md` — 동일 계약의 프롬프트-레벨 지시 (latency guard, invariant checklist)
- `knowledge/lessons/lesson_20260415_024_sl_triggers_on_mid_but_exits_at_bid_*` — strat_0028 SL 7× 초과 사례 상세
