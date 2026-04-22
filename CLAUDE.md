# KRX LOB Direction Prediction — Multi-Agent Strategy System

KRX tick 데이터(10-level L2 order book)에서 **OBI / OFI 기반 next-tick direction 예측** 전략을 다중 Agent가 **지속적으로 생성·평가·개선**하는 시스템.

---

## 🎯 목표

OBI(Order Book Imbalance)와 OFI(Order Flow Imbalance)를 활용해 **매 tick 직후의 방향(up/down)을 예측**하고, win rate 상승을 통해 return을 극대화하는 전략을 **지속적으로 생성·평가·개선**하는 multi-agent 시스템을 구축한다.

---

## 📌 범위 및 고정 제약

- **예측 단위**: 매 tick 다음 시점의 direction
- **1차 최적화 지표**: win rate (→ 이를 통한 return)
- **Execution**: 본 단계에서는 **1로 상수 고정**. Execution 최적화는 추후 독립된 전략 컴포넌트로 분리 설계
- **코드화 흐름**: Signal 생성 Agent의 **산출물(SignalSpec)을 입력**으로 받아 이를 코드로 변환하는 단계를 별도 Agent로 배치

### 왜 WR을 primary로?

Execution=1 고정 조건(entry=signal, exit=next tick, size=1) 하에서는
`Expected Return ≈ (2·WR − 1) × E[|Δmid|]`
이므로 **WR이 수학적으로 expectancy를 결정**한다. Execution 자유도가 없기 때문에 흔한 "tiny PT / huge SL" 비대칭 조작이 원천 차단되어 WR을 1차 지표로 쓰는 것이 타당하다.

---

## 🔗 2-Chain 아키텍처 (프로젝트 전체 구조)

전략 개발은 **두 개의 독립 체인**으로 분리된다.

```
┌─────────────────────────────────────┐     ┌─────────────────────────────────────┐
│       Chain 1 — Signal (α)          │     │       Chain 2 — Execution (ε)       │
│                                     │     │                                     │
│   Objective: WR ↑ (→ return)        │ ──▶ │   Objective: net PnL ↑              │
│   Variable:  feature × threshold    │     │   Variable:  order type, TTL,       │
│              × horizon              │     │              stop/target, skew,     │
│   Fixed:     execution = 1          │     │              inventory, sizing, …   │
│   Output:    SignalSpec + WR 통계   │     │   Input:     SignalSpec (Chain 1)   │
│                                     │     │   Output:    ExecutionSpec          │
│   Status:    🟢 현재 활성           │     │   Status:    🔴 현재 비활성 (deferred) │
└─────────────────────────────────────┘     └─────────────────────────────────────┘
```

### Chain 1 — Signal
- **목적**: OBI/OFI 계열 feature 공간에서 next-tick direction을 예측하는 **신호 자체의 WR**을 극대화.
- **고정**: execution = 1 상수 (entry=signal, exit=next tick, size=1).
- **가변**: feature 수식, 조합, threshold, prediction horizon, standardization window, regime filter 등.
- **산출**: `SignalSpec { formula, threshold, horizon, measured_WR, measured_expectancy }`.
- **현재 상태**: 🟢 **활성 — 본 문서 §Workflow의 ①~⑤가 Chain 1의 내부 루프다.**

### Chain 2 — Execution
- **목적**: Chain 1에서 검증된 SignalSpec을 받아, 실제 거래에서 **net PnL**(수수료·스프레드·adverse selection 후)을 극대화.
- **고정**: SignalSpec (Chain 1에서 받은 것 — Chain 2는 entry 로직에 손대지 않음).
- **가변**: order type (maker vs taker), entry price, TTL, cancel rule, PT/SL/trailing, skew, inventory limit, EOD flatten, queue position model, position sizing 등.
- **산출**: `ExecutionSpec { …, measured_net_PnL, Sharpe, MDD, cost_breakdown }`.
- **현재 상태**: 🔴 **비활성.** Execution을 "= 1 상수"로 고정해서 신호 탐색 복잡도를 낮춘 상태. Chain 1이 충분히 성숙(WR 목표치 달성 + 안정성 확인)하면 Chain 2를 별도 workflow·별도 Agent 세트로 신규 설계한다. 현 시점에서 Chain 2는 본 CLAUDE.md의 policy 범위 밖이다.

### 체인 간 계약 (interface)

```
Chain 1 → Chain 2 handoff = SignalSpec (Pydantic/JSON schema 예정):
  - feature_formula      : callable(book_snapshot) → float
  - entry_rule           : threshold | z_score | direction_vote 등
  - assumed_fixed_exit   : "next_tick" (Chain 1 내부 가정; Chain 2에서 재정의 가능)
  - measured_WR          : float  — Chain 1에서 측정한 next-tick WR
  - measured_expectancy  : float  — (2·WR − 1) × E[|Δmid|] in bps
  - references           : list[str]  — Chain 1 Agent가 참조한 근거 자료
```

Chain 2는 이 SignalSpec을 **entry 로직으로 고정**한 상태에서 execution 레이어만 튜닝한다. 역방향(Chain 2 → Chain 1) 수정은 금지 — 단, Chain 2가 "이 SignalSpec은 execution 관점에서 구현 불가"라고 판정하면 Chain 1에 reject 신호를 되돌릴 수 있다.

---

## 🔁 Workflow (Chain 1 내부 순환)

아래 ①~⑤는 **Chain 1 내부**의 자가 개선 루프다. Chain 2의 workflow는 별도로 정의될 예정.

```
 ① Signal 생성
      ↓
 ② Signal 평가 (SignalSpec 자체의 타당성 — static)
      ↓
 ②.5 코드화 (SignalSpec → Python signal/strategy code)
      ↓
 ②.75 Signal-코드 정합성 검사 (SignalSpec ↔ code fidelity gate)
      ↓
 ③ 백테스트 (hftbacktest 실행)
      ↓
 ④ 평가/피드백 (backtest 결과 분석)
      ↓
 ⑤ 자가 개선 ─────┐
      ↑           │
      └───────────┘ (loop back to ①)
```

### ②.75 정합성 검사의 책임

입력: `{signal_spec, generated_code}`. 검증 항목:

1. **Feature formula 일치**: spec의 신호 수식이 코드에 exactly 동일하게 구현됐는지
2. **Threshold / horizon 일치**: spec의 임계값·예측 horizon이 코드 상수와 일치하는지
3. **Entry 조건 일치**: spec의 진입 조건이 코드의 분기와 일대일 대응하는지
4. **Execution=1 강제**: size가 상수 1, exit가 next-tick, order type이 단순 MARKET 등 — execution 자유도 없음 확인
5. **Lookahead 부재**: 코드가 `mid[t+1]` 같은 미래 참조를 하지 않는지
6. **미선언 side effect 부재**: spec에 없는 skew, trailing, inventory 등 추가 로직이 없는지

출력: `pass` / `fail + mismatch list`. Fail이면 ②.5 코드화로 돌려 재작성.

---

## 🔭 Chain 2 — Execution (future workflow 스케치)

> **활성화 조건 전까지 본 섹션은 구조 참조용이며, 구현·실행되지 않는다.** 세부 agent prompt / 파라미터 탐색공간은 Chain 1 실증 결과를 입력으로 받아 추후 본 섹션을 확장하여 정의한다. `TBD` 태그된 항목은 현 시점에서 미정.

### Workflow (Chain 1과 동일 뼈대)

```
 ① Execution 생성  (ExecutionSpec 초안)
      ↓
 ② Execution 평가  (spec 자체의 타당성 — static)
      ↓
 ②.5 코드화        (ExecutionSpec → Python strategy code, SignalSpec 결합)
      ↓
 ②.75 정합성 검사  (SignalSpec + ExecutionSpec ↔ code fidelity gate)
      ↓
 ③ 백테스트        (hftbacktest 실행, 현실적 fee·latency·queue 모델 포함)
      ↓
 ④ 평가/피드백     (net PnL, Sharpe, MDD, cost breakdown 분석)
      ↓
 ⑤ 자가 개선 ─────┐
      ↑           │
      └───────────┘ (loop back to ①)
```

### Agent 역할 개략 (전원 6 구성 요소 + 근거 기반 원칙 준수)

| Agent | 책임 | 산출 |
|---|---|---|
| `execution-designer` | SignalSpec을 입력받아 ExecutionSpec 후보 설계 (order type, TTL, PT/SL, skew, 재고, EOD 정책 등) | ExecutionSpec 초안 JSON |
| `mechanics-evaluator` | spec의 내부 일관성·경계조건·fee 감당성 static 검증 | pass / fail + 사유 |
| `code-generator` (재사용) | SignalSpec + ExecutionSpec → 통합 Python strategy | strategy.py |
| `fidelity-checker` (재사용) | 생성 코드가 SignalSpec + ExecutionSpec을 그대로 구현하는지 | pass / fail + mismatch |
| `backtest-runner` (재사용) | hftbacktest로 실제 체결 시뮬, 결과 기록 | stats.npz + fill log |
| `execution-critic` | fill 품질·adverse selection·cost 기여도 분해 | critique JSON |
| `feedback-analyst` | 전체 결과를 SignalSpec vs ExecutionSpec 기여도로 분리, 다음 iteration 개선안 도출 | feedback JSON + lesson MD |

> Agent 간 prompt·schema 세부는 **TBD**.

### ExecutionSpec schema 필드 개략

```
ExecutionSpec {
  order_type       : "MARKET" | "LIMIT_AT_BID" | "LIMIT_AT_ASK" | "LIMIT_AT_MID"   # TBD 확장
  entry_ttl_ticks  : int | null
  cancel_rules     : list[CancelRule]    # TBD 정의
  exit_policy      : { pt_bps, sl_bps, time_stop_ticks, trailing? }   # TBD 세부
  inventory_cap    : float (포지션 한도, 단위 TBD)
  inventory_skew   : float (재고 기반 호가 기울기 계수)
  eod_flatten      : bool (장 마감 전 강제 청산)
  sizing_rule      : "constant" | "kelly_scaled" | "signal_strength_weighted"   # TBD
  queue_model      : "risk_adverse" | "power_prob_2" | ...   # hftbacktest 제공 모델 중
  fee_model        : { maker_fee_bps, taker_fee_bps, sell_tax_bps }
  # 측정값 (백테스트 후 채움)
  measured_net_pnl_pct : float
  measured_sharpe      : float
  measured_mdd_pct     : float
  cost_breakdown       : { spread_cost, fee_cost, adverse_sel_cost }   # TBD 계산식
}
```

> 구체 enum·수식은 **TBD**. Chain 1에서 발견되는 신호 특성(예: 평균 fill 간격, avg_win/loss 스케일)에 따라 유효 범위가 정해진다.

### 활성화 조건 (게이트)

Chain 2는 다음 **전원 충족** 시에만 실행된다:

1. Chain 1이 WR ≥ **TBD**% (초기 제안: 55%) 인 SignalSpec을 최소 1개 산출
2. 해당 SignalSpec의 `n_trades_per_day` ≥ **TBD** (초기 제안: 50) — 통계적 유의성 확보
3. 해당 SignalSpec이 서로 다른 날짜 ≥ **TBD** (초기 제안: 3) 에서 재현됨
4. Chain 1의 feedback-analyst가 "execution layer로 넘길 준비 완료" 태그 부여

위 조건 미충족 시 Chain 2는 활성화되지 않으며, Chain 1은 루프를 계속 돈다.

### Chain 1과의 분리 원칙

- Chain 2 agent는 **SignalSpec의 내용을 수정하지 않는다** (entry 로직 고정)
- Chain 2가 "이 SignalSpec은 어떤 execution으로도 수익화 불가"라고 판정하면 SignalSpec에 `execution_infeasible=true` 태그와 사유를 붙여 Chain 1에 reject — Chain 1은 다음 iteration에 이를 회피 조건으로 활용
- Chain 1과 Chain 2는 **동시 실행되지 않는다** (단일 활성 체인 원칙). Chain 2 활성 중 Chain 1 수정은 새로운 SignalSpec 배치(batch)로 분리.

---

## 🔧 Chain 2 Backtest Engine — 정식 설계

Chain 2 구현 시점의 ambiguity 제거를 위해 엔진 구성 요소는 사전 확정. 파라미터 값(threshold 등)은 Chain 1 실증 결과에 따라 결정되지만, **무엇을 모델링할지**는 아래로 고정이다.

### (1) 프레임워크 — 확정

- **`hftbacktest` (nkaz001/hftbacktest)** 를 Chain 2 엔진의 유일한 백엔드로 사용. 자체 Rust 엔진 재구현 금지.
- Python 호출 경로: `py-hftbacktest` (PyPI `hftbacktest==2.3.0+`).
- Chain 2가 직접 하는 것: SignalSpec + ExecutionSpec → 이벤트 재생 → 체결 시뮬 → cost-breakdown 집계. 모두 Python wrapper 수준.
- 수정이 필요한 경우 **Python wrapper 레벨에서만 우회**; Rust 코어는 건드리지 않는다.

### (2) 데이터 경로 — 확정

```
/home/dgu/tick/open-trading-api/data/realtime/H0STASP0/<YYYYMMDD>/<symbol>.csv  (KRX 원본)
                              ↓
           adapters/krx_to_hftbacktest.py  (DiffOrderBookSnapshot 기반)
                              ↓
           data/hftb_events/<symbol>_<YYYYMMDD>.npz  (hftbacktest event 포맷)
                              ↓
           hftbacktest Python API 로 소비
```

모든 변환은 **`adapters/` 디렉토리**에서만 관리. Chain 2 agent는 어댑터 내부 수정 금지.

### (3) Chain 1 vs Chain 2 엔진 차이 — 구체화

| 항목 | Chain 1 엔진 (`chain1/backtest_runner.py`) | Chain 2 엔진 (`chain2/backtest_runner.py`, 미구현) |
|---|---|---|
| Entry 가격 | `mid[t]` (이론적) | order_type별 — MARKET은 ask(매수)/bid(매도) 크로스, LIMIT은 post 후 대기 |
| Exit 가격 | `mid[t+H]` | ExecutionSpec의 PT/SL/trailing/time_stop 발동 시점 실제 체결가 |
| Spread 비용 | 0 | 실측 (LOB 스냅샷 bid-ask) |
| Fee | 0 | market/order_type별 (§5 테이블 참조) |
| Sell tax (KRX) | 0 | 0.20% (현물 매도측에만) |
| Slippage | 0 | Lot 크기 > 레벨 잔량 시 multi-level walk (hftbacktest 자동) |
| Queue position | N/A | hftbacktest `RiskAdverseQueueModel` 기본, `PowerProbQueueModel(2)` 옵션 |
| Latency | 0 | `ConstantLatency(entry=5ms, response=5ms)` 기본; 실측 latency 데이터 확보 시 `IntpOrderLatency` |
| EOD 청산 | N/A | optional `eod_flatten` 플래그 (장 마감 30분 전 강제 unwind) |
| Inventory | N/A | `inventory_cap_lots`, `inventory_skew_krw` (MM 스타일) |

### (4) Fee 테이블 — 고정

Chain 2 cost model이 참조하는 정식 수수료:

| Market | Maker fee (bps) | Taker fee (bps) | Sell tax (bps) | 비고 |
|---|---|---|---|---|
| KRX 현물 소매 | 1.5 | 1.5 | 20 (매도에만) | **실제 배포 목표 시장** — RT ≈ 23 bps |
| `hypothetical_low_fee_5bps` | 2.5 | 2.5 | 0 | 가상 저수수료 시나리오 (리베이트 도입 등). 연구 참조만. |

(선물 / ETF 는 수수료 표에서 제외 — 2026-04-20 결정 반영.
**Crypto 시나리오는 KRX 데이터 run 시 사용 금지** — cross-market 비교는
크립토 LOB 데이터로 Chain 1 을 **별도 재측정** 한 후에만 의미 있음. 2026-04-21 결정.)

### (5) ExecutionSpec — 필드 + enum 값 고정

```
ExecutionSpec {
  order_type              ∈ {"MARKET", "LIMIT_AT_BID", "LIMIT_AT_ASK", "LIMIT_INSIDE_1"}
  entry_ttl_ticks         int ∈ [1, 500]
  cancel_on_bid_drop      int ∈ [0, 10]       # 0 = never cancel
  pt_bps                  float ≥ 0           # 0 = no profit target
  sl_bps                  float ≥ 0           # 0 = no stop loss
  time_stop_ticks         int ≥ 0
  trailing                ∈ {"none", "fixed_bps", "atr_based"}
  trailing_distance_bps   float ≥ 0
  inventory_cap_lots      int ∈ [1, 100]
  inventory_skew_krw      float ≥ 0           # 재고 1 lot당 호가 skew (KRW)
  eod_flatten             bool
  sizing_rule             ∈ {"constant_1", "kelly_scaled", "signal_strength_weighted"}
  fee_market              ∈ {"krx_cash", "crypto_binance_spot"}   # (5)의 테이블 row 선택
  queue_model             ∈ {"risk_adverse", "power_prob_2"}
  latency_model           ∈ {"constant_5ms", "intp_historical"}
}
```

미구현 enum 값 (표에 없는 값)이 섞인 ExecutionSpec은 ②.75 fidelity gate가 hard-reject.

### (6) BacktestResult_v2 — Chain 2 결과 스키마

Chain 1의 `BacktestResult`를 확장. `_shared/schemas.py`에 추가 정의 예정.

```
BacktestResult_v2 {
  (Chain 1 BacktestResult 모든 필드 그대로 상속)

  # Chain 2 고유 measured values
  net_pnl_bps_per_trade     float     # fee + spread + tax 반영 후
  sharpe_annualized         float
  max_drawdown_bps          float
  n_fills                   int
  n_maker_fills             int
  n_taker_fills             int
  final_inventory_lots      int

  cost_breakdown {
    spread_cost_bps                 float  # ≥ 0
    maker_fee_cost_bps              float
    taker_fee_cost_bps              float
    sell_tax_cost_bps               float
    adverse_selection_cost_bps      float  # 체결 시점 vs 직후 mid 차이
    slippage_cost_bps               float  # multi-level walk 발생 시
  }
}
```

### (7) PnL 산출 공식 — 정식

Round-trip당 net PnL:

```
net_pnl_per_rt  =  signal_edge_bps                # Chain 1에서 측정한 raw 예측 edge
                −  spread_cross_entry_bps          # order_type별 (MARKET=spread/2, LIMIT=0)
                −  spread_cross_exit_bps
                −  entry_fee_bps                   # (4) 테이블 + order_type (maker vs taker)
                −  exit_fee_bps
                −  sell_tax_bps                    # SELL 쪽에만, KRX 현물
                ±  adverse_selection_drift_bps     # hftbacktest 큐 모델이 자동
                ±  slippage_bps                    # lot > 레벨 잔량 시
```

Chain 2 feedback-analyst는 이 `net_pnl_per_rt` 분포를 primary metric으로 쓰며, WR은 보조 지표로만 참조.

### (8) 절대 규칙 (Chain 2 엔진 관련, 기존 §🚫 에 추가될 내용)

- Chain 2 engine 은 `hftbacktest` binary 를 호출·wrap만 한다. Rust 코어 수정 금지.
- 데이터 변환은 `adapters/` 디렉토리에서만 관리.
- `ExecutionSpec` / `BacktestResult_v2` 는 `_shared/schemas.py` 에 추가해 Chain 1과 schema 공유.
- 미구현 enum 값을 포함한 ExecutionSpec 은 ②.75 fidelity gate가 hard-reject.
- Chain 2 결과 리포트는 반드시 `cost_breakdown` 필드를 채운다 — 비어 있으면 리포트 무효.

---

## 🧩 Agent 구성 원칙

### (1) 역할 분리

- 전체 파이프라인을 **단일 Agent가 아닌 단계별 복수 Agent**로 분할하여 병목을 줄이고 정확도를 향상시킨다.
- 특정 단계가 단일 Agent로 감당 어려운 경우, **해당 단계 내부에서 sub-agent로 추가 분할 가능**.

### (2) 모든 Agent의 필수 구성 요소 — **예외 없음**

모든 Agent는 반드시 다음 6개 항목을 갖춘다.

1. **System Prompt** — 역할·목표·제약
2. **User Prompt** — 실행 지시 템플릿
3. **Reference** — 참조 자료/근거 소스
4. **Input Schema** — 입력 구조 명세
5. **Output Schema** — 출력 구조 명세
6. **Reasoning Flow** — 단계별 추론 절차

---

## 🚫 절대 위반 금지 규칙

1. **구조 규칙**: 어떤 Agent도 위 6개 구성 요소 중 하나라도 누락하지 않는다.
2. **근거 기반 원칙**: 각 체인의 `생성` · `평가` · `평가/피드백` · `자가 개선` 4개 Agent (Chain 1의 `Signal 생성` / `Signal 평가` / … , Chain 2의 `Execution 생성` / `Execution 평가` / …) 는 **본인의 추측이 아닌, 검증 가능한 근거(Reference·Input·백테스트 결과 등)에 기반**하여 분석·판단을 수행한다.
3. **범위 규칙**: Execution 관련 최적화는 현재 파이프라인에서 다루지 않는다 (상수 1 고정).
4. **정합성 규칙**: ②.75 fidelity gate를 통과하지 못한 코드는 ③ 백테스트로 진입할 수 없다.
5. **비가역 작업 규칙**: 파일 삭제, git 조작, 대규모 refactor 등 비가역 작업은 **사전 사용자 확인** 후 수행한다.

---

## 🗂 Repo 현황 (ground truth)

### 디렉토리 구조

```
proj_claude_tick_finance/
├── CLAUDE.md                       # 본 문서
├── engine/
│   ├── __init__.py
│   └── data_loader.py              # KRX CSV → OrderBookSnapshot 어댑터 (12KB)
├── adapters/
│   └── krx_to_hftbacktest.py       # KRX CSV → hftbacktest event stream 변환기
├── scripts/
│   ├── run_obi_mm_krx.py           # (예시) OBI MM 전략 포팅 실행
│   └── oracle_max_pnl.py           # 오라클 상한 (perfect foresight) 계산기
├── data/
│   ├── binance_lob/                # (보존) crypto LOB parquet — 현재 파이프라인 미사용
│   ├── binance_daily/, binance_multi/  # (보존) crypto bars — 현재 파이프라인 미사용
│   ├── hftb_events/                # KRX → hftbacktest 변환 결과 .npz
│   └── hftb_stats/                 # 백테스트 stats .npz
└── .venv/                          # Python 환경
```

### 외부 데이터 원본 (**읽기 전용, 수정·삭제 금지**)

- **KRX LOB 원본 CSV**: `/home/dgu/tick/open-trading-api/data/realtime/H0STASP0/<YYYYMMDD>/<SYMBOL>.csv`
  - 현재 누적: 2026-03-05 ~ 2026-04-20 (약 20 거래일), 총 7.0 GB
  - 1행 = 100ms 주기 호가 스냅샷
  - 컬럼 62개 (가격 10단계 × 2, 잔량 10단계 × 2, 총잔량, ACML_VOL, 예상체결, 시간코드 등 — 상세: `engine/data_loader.py` 주석)

- **hftbacktest 원본 프레임워크**: `/home/dgu/tick/hftbacktest/` (nkaz001/hftbacktest 클론, 1038 commits, 27 contributors)
  - 실사용: `py-hftbacktest` Python 바인딩 (PyPI `hftbacktest==2.3.0`)
  - 참조 예제: `examples/Market Making with Alpha - Order Book Imbalance.ipynb` 등

---

## 🔧 기술 규칙 (operational)

### 프레임워크 선택

- **백테스트 엔진**: `hftbacktest` (nkaz001) 사용. 자체 구현 금지.
  - 이유: Queue position (5종), Latency (Constant/IntpOrder), Fee (TradingValue/Qty/PerTrade), Exchange matcher (4종), Market depth (4종) 모두 학술·업계 수준 구현.
  - 수정이 필요하면 Python 래퍼 레벨에서 우회하고, Rust 코어는 건드리지 않는다.

- **데이터 어댑터**: `adapters/krx_to_hftbacktest.py` 단일 경로. KRX CSV → `DiffOrderBookSnapshot` → `DEPTH_EVENT` stream → `correct_local_timestamp` + `correct_event_order` → `.npz`.

### 실행 환경

- Python 3.10, venv at `.venv/`
- 핵심 의존성: `hftbacktest, numpy, pandas, pyarrow, numba, polars, matplotlib`
- 모든 스크립트는 `source .venv/bin/activate` 선행 후 실행

### KRX 데이터 주의사항

- `HOUR_CLS_CODE == "0"` 이어도 장 시작 전 (08:30~09:00) 호가가 전부 0인 행 존재 → `(BIDP1 > 0) & (ASKP1 > 0) & (ASKP1 > BIDP1)` 필터 필수
- tick_size 가변: 가격대별 달라짐 (2000원 이하 1원 ~ 50만원 이상 1000원). `adapters/krx_to_hftbacktest.py:krx_tick_size()` 참고.
- 매도세 0.20% 는 직거래 세금 — execution 확장 단계에서 `DirectionalFees`로 모델링 필요 (현 단계 execution=1 고정이므로 미고려)

### 수수료 현실

현재 파이프라인은 execution=1 상수이므로 수수료 무고려. 그러나 향후 execution 확장 시 다음을 참고:

| 시장 | RT fee | 상대 |
|---|---|---|
| KRX 현물 소매 | ~23 bps | 사실상 불가능 |
| Crypto Binance taker | 8 bps | 경계 |

---

## 🧪 알려진 baseline 숫자 (2026-04-20 측정)

파이프라인 재설계 전 참고:

- **오라클 상한 (perfect foresight, 005930 2026-03-26, 20M book)**:
  - 스프레드·수수료 없음: +138.8%/day (절대 상한)
  - Taker 1-tick RT (spread 반영): +5.12%/day
  - DP 최적 (multi-tick hold, spread 반영): +42.35%/day
  - Break-even fee: 5.56 bps/fill

- **OBI MM 포팅 결과 (fee=0, 005930 2026-03-26)**:
  - 356 trades / day
  - Round-trip WR 71.1% (32W / 13L / 1tie)
  - Avg win/loss = 5,225 / 12,015 KRW (비율 1:2.3)
  - 실현 PnL +11K / 미청산 -3.96M → **net +16.5K KRW (+0.08%)** — 오라클의 0.2%

이 수치들은 "신호 자체엔 edge 존재, 현 execution 수준은 낮음"을 의미. 본 프로젝트의 Chain 1(신호)은 이 baseline을 상회하는 걸 목표로 한다.

---

## 📚 참조 자료

### 논문 (우선순위 순)

- **Cont, Kukanov, Stoikov (2014)** — "The Price Impact of Order Book Events" — OFI의 정식 정의와 linear mid-price regression
- **Stoikov (2018)** — "The Micro-Price" — microprice 수식과 fair value 해석
- **Gueant, Lehalle, Fernandez-Tapia (2013)** — "Dealing with the Inventory Risk" — GLFT market making 모형
- **Cartea, Jaimungal (2015~)** — "Algorithmic and High-Frequency Trading" — OBI/OFI 기반 MM 교과서

### hftbacktest 공식 예제 (참고 필수)

- `/home/dgu/tick/hftbacktest/examples/Market Making with Alpha - Order Book Imbalance.ipynb`
- `/home/dgu/tick/hftbacktest/examples/GLFT Market Making Model and Grid Trading.ipynb`
- `/home/dgu/tick/hftbacktest/examples/Probability Queue Models.ipynb`

---

## ✍️ 문서 규칙

- 본 CLAUDE.md는 **프로젝트 상위 정책**. Agent 설계·구현은 모두 이 문서를 preceding constraint로 삼는다.
- 수정 시 변경 근거를 commit message에 명시 (예: "CLAUDE.md: Chain 1 objective 변경 + 관련 규칙 추가").
- 한국어 primary, 기술 용어·코드는 영어 혼용.
