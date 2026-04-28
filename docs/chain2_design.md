# Chain 2 Design Document — Execution Layer

**Date**: 2026-04-22 · **Author**: Claude Code + user direction · **Status**: draft v0.1

## 0. Context & Motivation

Chain 1은 `iter013_ask_conc_low_vol_h50`에서 OOS **raw expectancy +12.98 bps** 달성. 하지만 KRX 23 bps RT fee 벽에서 여전히 post-fee **−5 bps**. 이 차이는 raw edge를 더 키워 메우기보다 **execution layer에서 fee burden을 줄이고 spread를 수익화**하는 게 수학적으로 더 효율적이라고 판단됨 (이전 분석 참조).

Chain 2의 primary objective는 Chain 1 signal을 **fixed entry trigger**로 받고, 다음 execution 자유도를 최적화하여 **net PnL (post-fee)**을 최대화하는 것:
- Order type (MARKET taker vs LIMIT maker)
- Exit policy (PT / SL / time_stop / trailing)
- Inventory/sizing (추후, Phase 2.3+)

## 1. Scope — In / Out

### In (Phase 2.0 ~ 2.2)
- SignalSpec → fixed entry signal (entry rule 고정, 수정 금지)
- ExecutionSpec schema 설계 및 검증
- BacktestResult_v2 (cost_breakdown 포함) 측정
- Execution grid search (hand-crafted → systematic)
- KRX 현물 (fee_market=krx_cash) 단일

### Out (나중 Phase 혹은 기각)
- 크립토 시장 fee scenario (CLAUDE.md 2026-04-21 결정 — cross-market 비교 전엔 금지)
- Market-making paradigm (bid/ask 양측 post, inventory neutral) — paradigm 재설계 필요, Phase 2.3 이후
- Chain 2 LLM agents (execution-designer 등) — 엔진 안정화 후 Phase 2.3
- Kelly/signal-strength sizing — Phase 2.2 이후
- hftbacktest 풀스택 backtest — 첫 직접 검증은 simplified engine, 필요 시 A/B

## 2. Extensibility (D1 확장성 대응)

Chain 2 engine은 **signal-agnostic**. 다음 시나리오 모두 동일 엔진으로:

| 시나리오 | 변경 | 엔진 수정? |
|---|---|---|
| iter013 단독 (1차) | `signal_spec_id = "iter013_ask_conc_low_vol_h50"` | X |
| iter014 교체 | spec_id만 변경 | X |
| iter013 + iter014 portfolio | `signal_spec_ids: list[str]`, `aggregation_rule: "or"` | schema 확장 1줄 |
| 3개 signal weighted vote | `aggregation_rule: "weighted"`, `weights: list[float]` | schema 확장 3줄 |
| Crypto 시장 확장 | `fee_market = "crypto_binance_spot"` (별도 data adapter) | data 층만 |

Entry trigger는 신호 vs threshold 비교만 하므로 signal implementation과 독립.

## 3. Architecture Overview

```
   ┌── Chain 1 output ──┐
   │ SignalSpec.json    │   (iter013_ask_conc_low_vol_h50)
   └─────────┬──────────┘
             │ (fixed entry trigger)
             ▼
   ┌──────── Chain 2 Execution Pipeline ─────────────────┐
   │                                                     │
   │  ExecutionSpec                                      │
   │   ├─ order_type         (MARKET | LIMIT_AT_BID)    │
   │   ├─ pt_bps / sl_bps / time_stop_ticks / trailing  │
   │   ├─ regime_gate        (optional extra filter)    │
   │   ├─ sizing_rule        ("constant_1" 1차)          │
   │   ├─ fee_market         ("krx_cash" 고정)           │
   │   └─ queue_model        ("risk_adverse" 기본)       │
   │                                                     │
   │        ↓ chain2/execution_runner.py                 │
   │                                                     │
   │   per-tick loop over KRX snapshots:                 │
   │     1. compute signal_value (Chain 1 spec)         │
   │     2. if signal > threshold AND no open position: │
   │          open position with entry_price            │
   │            (MARKET: ask/bid cross)                 │
   │            (LIMIT: post + 50% fill model)          │
   │     3. for open position each tick:                │
   │          evaluate PT / SL / time_stop / trailing   │
   │          if triggered: close position, record PnL  │
   │          if not: move to next tick                 │
   │     4. accumulate cost_breakdown per trade         │
   │                                                     │
   │        ↓                                            │
   │  BacktestResult_v2                                  │
   │   ├─ (Chain 1 fields)                              │
   │   ├─ net_pnl_bps_per_trade                         │
   │   ├─ Sharpe, MDD                                   │
   │   ├─ n_maker_fills, n_taker_fills                  │
   │   └─ cost_breakdown (6 components)                 │
   └─────────────────────────────────────────────────────┘
```

## 4. Schema Design

### 4.1 ExecutionSpec (add to `_shared/schemas.py`)

```python
class OrderType(str, Enum):
    MARKET        = "MARKET"
    LIMIT_AT_BID  = "LIMIT_AT_BID"    # post maker on bid (for long entry)
    LIMIT_AT_ASK  = "LIMIT_AT_ASK"    # post maker on ask (for short entry, Phase 2.1)
    LIMIT_INSIDE_1 = "LIMIT_INSIDE_1"  # 1 tick aggressive, Phase 2.2

class TrailingMode(str, Enum):
    NONE          = "none"
    FIXED_BPS     = "fixed_bps"       # trailing stop at constant bps
    # ATR_BASED later

class FeeMarket(str, Enum):
    KRX_CASH_23BPS = "krx_cash"

class ExecutionSpec(HandoffBase):
    """Execution plan applied to a fixed Chain 1 SignalSpec."""

    spec_id: str                              # "exec001_market_pt10_sl20_h50"
    signal_spec_id: str                       # reference to Chain 1 SignalSpec
    # (future: signal_spec_ids: list[str] for portfolio)

    # Entry
    order_type: OrderType = OrderType.MARKET
    entry_ttl_ticks: int = Field(1, ge=1, le=500)  # LIMIT: cancel if not filled
    maker_fill_rate: float = Field(0.5, ge=0.0, le=1.0)  # used for LIMIT sim

    # Exit
    pt_bps: float = Field(0.0, ge=0.0)       # 0 = no PT
    sl_bps: float = Field(0.0, ge=0.0)       # 0 = no SL
    time_stop_ticks: int = Field(50, ge=1, le=500)   # hard timeout
    trailing_mode: TrailingMode = TrailingMode.NONE
    trailing_distance_bps: float = Field(0.0, ge=0.0)

    # Regime (optional extra filter on top of SignalSpec's own filters)
    extra_regime_gate: str | None = None      # e.g. "rolling_realized_vol < 30"

    # Sizing (Phase 2.0 constant)
    sizing_rule: Literal["constant_1"] = "constant_1"

    # Market / Fee
    fee_market: FeeMarket = FeeMarket.KRX_CASH_23BPS
    queue_model: Literal["risk_adverse", "power_prob_2"] = "risk_adverse"
    latency_model: Literal["constant_5ms"] = "constant_5ms"
```

### 4.2 BacktestResult_v2 (add to `_shared/schemas.py`)

```python
class CostBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spread_cost_bps: float = Field(..., ge=0.0)
    maker_fee_cost_bps: float = Field(..., ge=0.0)
    taker_fee_cost_bps: float = Field(..., ge=0.0)
    sell_tax_cost_bps: float = Field(..., ge=0.0)
    adverse_selection_cost_bps: float = 0.0  # can be negative? — signed
    slippage_cost_bps: float = Field(0.0, ge=0.0)

class BacktestResult_v2(BacktestResult):
    """Extends Chain 1 BacktestResult with execution-layer measurements."""
    execution_spec_id: str
    net_pnl_bps_per_trade: float
    sharpe_annualized: float
    max_drawdown_bps: float
    n_fills: int
    n_maker_fills: int
    n_taker_fills: int
    final_inventory_lots: int = 0
    cost_breakdown: CostBreakdown
```

## 5. Engine Design (`chain2/execution_runner.py`)

### 5.1 Hybrid approach (D2=(C))

- **Phase 2.0 ~ 2.2**: Python-only engine that extends `chain1/backtest_runner.py`. Uses 100ms KRX snapshots directly — no event-stream conversion. Queue model is a simple approximation (see 5.4).
- **Phase 2.x (optional)**: If the simple engine shows positive net PnL, rerun top 3 ExecutionSpec via `hftbacktest` for proper queue/latency validation.

### 5.2 Entry pricing

| order_type | entry_price calc | entry_cost_bps |
|---|---|---|
| MARKET | long: `ask_px[0]`, short: `bid_px[0]` | = spread/2 (half-spread crossed) |
| LIMIT_AT_BID (long) | `bid_px[0]` at signal tick | 0 if filled; else unfilled |
| LIMIT_AT_ASK (short) | `ask_px[0]` at signal tick | 0 if filled |

### 5.3 Exit pricing

매 tick마다 open position의 `unrealized_pnl_bps = (mid_now − mid_entry) / mid_entry * 1e4 * direction`. 다음 조건 중 첫 번째 발생에 exit:

- `unrealized_pnl_bps >= pt_bps` and `pt_bps > 0` → **hit PT** (exit at MARKET cross)
- `unrealized_pnl_bps <= −sl_bps` and `sl_bps > 0` → **hit SL** (exit at MARKET cross)
- Trailing (if enabled): track `max_pnl`, exit if `max_pnl − current_pnl >= trailing_distance_bps`
- `ticks_held >= time_stop_ticks` → **time stop** (exit at MARKET cross)

Exit은 기본 MARKET (즉 maker entry + taker exit = mixed fill). Phase 2.1에서 `exit_order_type` 분리 고려.

### 5.4 Fee model (fee_market=krx_cash)

```
Per round-trip:
  entry_fee_bps  = 1.5 (maker) or 1.5 (taker)   # KRX has no maker rebate
  exit_fee_bps   = 1.5 (taker, always — exits are MARKET in Phase 2.0)
  sell_tax_bps   = 20 (long position exit only; short has no KRX cash)
  spread_entry_bps = 0 (maker) or spread/2 (taker)
  spread_exit_bps  = spread/2 (taker exit)
  slippage_bps   = 0 (assume lot size fits in top level; Phase 2.1 multi-level walk)
```

### 5.5 Maker fill simulation (Phase 2.0 simplified)

LIMIT_AT_BID at signal tick `t`:
- Assume posted at `bid_px[t]`, depth = `bid_qty[0][t]`
- Fill if any of next `entry_ttl_ticks` ticks has `mid_{t+k} <= bid_px[t] - tick_size/2` (price crossed)
- Conservative: apply `maker_fill_rate` multiplier to expected fills (e.g. 0.5 = simulate only half of filled events actually fill our order, reflecting queue position)
- Unfilled entries discarded (no trade, no fee)

### 5.6 adverse_selection_cost_bps

체결 후 1 tick (100ms) 뒤 mid 움직임이 entry 방향과 **반대**이면 adverse selection. Phase 2.0에선 별도 측정만 하고 PnL에 이미 포함된 상태로 기록:
```
adverse_sel_bps = −(mid_{t_fill+1} − mid_fill) / mid_fill * 1e4 * direction
  # positive if mid moved against us
```

## 6. Search Strategy

### 6.1 Stage A — Direction test (5 specs, ~10 min 컴퓨트)

Signal: `iter013_ask_conc_low_vol_h50` (고정)
Universe: 005930, 000660 × IS 3 + OOS 18 = 21 dates

| spec_id | order | pt | sl | time | trailing |
|---|---|---|---|---|---|
| exec_A_S1_baseline     | MARKET | 0 | 0 | 50 | none |
| exec_A_S2_market_ptsl  | MARKET | 10 | 20 | 50 | none |
| exec_A_S3_market_wide  | MARKET | 15 | 30 | 100 | none |
| exec_A_S4_maker_flat   | LIMIT_AT_BID | 0 | 0 | 50 | none |
| exec_A_S5_maker_ptsl   | LIMIT_AT_BID | 10 | 20 | 50 | none |

**검증 포인트**:
- S1 net_pnl = `raw_exp − spread − 2×taker_fee − sell_tax`. 이게 이론치와 맞는지 (sanity check).
- S2 vs S3: PT/SL 넓히기가 도움되나?
- S4 vs S1: maker 50% fill로 spread 회피 효과?
- S5 vs S2: maker 전환으로 진짜 net positive에 도달?

### 6.2 Stage B — Grid narrow (~36 specs, Stage A 후 판단)

Stage A 최고 spec 기준으로:
- PT: {5, 10, 15, 20, 25}
- SL: {10, 20, 30, 40}
- time_stop: {20, 50, 100, 200}
- trailing: {none, fixed_bps 15}
- order_type: Stage A winner 고정

→ 5×4×4×2 = 160 combos. 너무 많으면 Latin hypercube sampling으로 20~36개 선택.

### 6.3 Stage C — LLM Agent framework (Phase 2.3)

`.claude/agents/chain2/` 구조 (Chain 1 대칭):
- `execution-designer` (LLM) — Chain 1 feedback + Stage A/B 결과 보고 ExecutionSpec 제안
- `mechanics-evaluator` — spec static validity (fee sanity, boundary)
- `code-generator` / `fidelity-checker` — 재사용
- `execution-critic` (LLM) — fill 품질, adverse selection, cost 기여도 분해
- `feedback-analyst` (LLM) — Chain 1 vs Chain 2 기여도 분리, 다음 iter 개선안

## 7. Phase Roadmap

| Phase | 산출물 | ETA |
|---|---|---|
| 2.0 | ExecutionSpec + BacktestResult_v2 schemas, `chain2/execution_runner.py` skeleton, S1 only smoke (sanity) | Day 1 |
| 2.0.1 | S1~S5 (Stage A) 실행, cost_breakdown 첫 수치 | Day 2 |
| 2.1 | Maker fill model 세밀화, LIMIT_AT_ASK 지원, Stage A 결과 보고서 | Day 3~4 |
| 2.2 | Stage B grid search, 최적 ExecutionSpec 확정, (optional) hftbacktest 재검증 | Day 5~7 |
| 2.3 | Chain 2 agents 구현 시작 (execution-designer + critic 먼저) | Week 2 |
| 2.4+ | Multi-signal portfolio, Kelly sizing 등 | Week 3+ |

## 8. 성공 기준

| 기준 | 성공선 |
|---|---|
| Stage A S1 (baseline) | 이론치 (-5~-10 bps net) 와 ±1 bps 이내 일치 — sanity |
| Stage A S5 (maker + ptsl) | **net_pnl > 0** 이면 Chain 2 가치 확정 |
| Stage B 최적 | net_pnl > +1 bps robust across OOS dates |
| 최종 | iter013 고정 + best ExecutionSpec → **post-fee Sharpe > 1.5** |

## 9. Open Questions (추후 해결)

1. Short position: KRX 현물 공매도는 대차거래 수수료 별도, 일부 종목 제한. 1차는 **long-only**만?
2. LIMIT 체결 확률 0.5가 현실적인가? hftbacktest로 Phase 2.2 말에 재검증.
3. Adverse selection을 별도 측정할지, PnL에 포함할지 — **측정 + 이미 PnL 포함** (이중 계산 방지).
4. Multi-day aggregation 시 Sharpe 계산의 per-trade vs per-day 기준 — per-day 선호.

## 10. File Layout (새로 생성할 파일)

```
chain2/
├── __init__.py
├── execution_runner.py          # 엔진 핵심 (Phase 2.0)
├── cost_model.py                # fee / spread / slippage 계산 유틸
├── report.py                    # Chain 2용 plotly report (Phase 2.1)
└── tests/
    └── test_execution_runner.py

.claude/agents/chain2/           # Phase 2.3 이후
(not created yet)

.claude/agents/chain1/_shared/schemas.py
    + ExecutionSpec
    + BacktestResult_v2
    + CostBreakdown
    + OrderType / FeeMarket / TrailingMode enums

docs/
└── chain2_design.md   ← 본 문서
```

---

## Appendix A — `iter013_ask_conc_low_vol_h50` 요약 (Chain 2 고정 입력)

- **Formula**: `zscore(ask_depth_concentration, 300) * (rolling_realized_vol(mid_px, 100) < 30)`
- **Threshold**: 5.0 · **Direction**: `long_if_neg` · **Horizon**: 50
- **OOS performance** (18 dates × 4 sym, pre-fee):
  - WR 0.948 · expectancy +12.98 bps · n 1,661
- **Already has regime filter** (`rolling_realized_vol < 30`) built in → Chain 2의 `extra_regime_gate`는 기본 `None`.
