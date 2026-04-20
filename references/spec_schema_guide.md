# Spec Schema Guide

> **Primary consumer**: spec-writer
> **Secondary consumers**: strategy-coder (참조), code-generator (schema 확장 시)
> **Trigger condition**: 모든 spec.yaml 작성 시 (항상)
> **Companion references**: `python_impl_patterns.md` (엔진 API), `exit_design.md`
> **Requires**: 이 문서만 consult하면 충분 — `engine/spec.py` 직접 읽기 불필요
> **Status**: stable

---

## 0. Core insight

**spec.yaml은 엔진 계약이다. market마다 요구/금지 필드가 다르며, 잘못된 필드 조합은 runtime error 또는 silent mis-dispatch를 야기한다.**

**해결할 failure mode**: spec-writer가 LOB 규칙을 몰라 `validate_spec.py`에 surgical patch 2건 자가 주입 (2026-04-20 smoke iter1: `universe.dates` emptiness skip, `strategy.py` import warning). 본 문서는 market별 필드 매트릭스를 단일 진실의 원천으로 고정한다.

---

## 1. Market → required-field 매트릭스

**이 문서의 핵심 섹션. spec 작성 전 해당 column을 반드시 확인.**

| 필드 | crypto_1d | crypto_1h/15m/5m | crypto_lob |
|------|-----------|------------------|------------|
| `name` | required | required | required |
| `description` | recommended | recommended | recommended |
| `capital` | 10_000_000.0 | 동일 | **인간단위 USD** (auto ×1e8) |
| `universe.market` | — (optional) | — | **required** = `"crypto_lob"` |
| `universe.symbols` | required (list) | required | required |
| `universe.dates` | **required** (list of YYYY-MM-DD) | **required** | **must be `[]`** |
| `universe.time_window.start` | — (unused) | — | **required** (ISO UTC datetime) |
| `universe.time_window.end` | — | — | **required** |
| `target_symbol` | required | required | **forbidden** |
| `target_horizon` | `"1d"` | `"1h"`/`"15m"`/`"5m"` | **forbidden** |
| `fees.commission_bps` | 1.5 default (`engine/simulator.py` FeeModel) | 동일 | 0.0 (maker) or 2.0 (taker half-rt) |
| `fees.tax_bps` | 0.0 | 0.0 | 0.0 (크립토 — 세금 없음) |
| `latency.submit_ms` | 5.0 | 5.0 | 5.0 |
| `strategy_kind` | `dsl`/`python` | `dsl`/`python` | `python` (실질 필수) |
| `params.*` | 전략별 | 전략별 | 전략별 (§6 표준 키 참조) |
| `handoff_metadata.*` | optional | optional | optional |

**해석 규칙**:

| 표기 | 의미 |
|------|------|
| required | 없으면 runtime `ValueError` |
| forbidden | 있으면 무시되지만 타 스크립트 오분기 유발 — 생략 필수 |
| — (unused) | 스키마 수용하지만 의미 없음 |
| must be `[]` | non-empty면 engine이 bar-path `iter_events` 호출 → LOB 경로 불일치 |

---

## 2. 필드별 의미 + 엔진 소비처

| 필드 | 타입 | 읽는 위치 | 파급 효과 |
|------|------|-----------|-----------|
| `universe.market` | str | `engine/spec.py load_spec → Universe.market → Backtester` | LOB vs bar 분기 트리거 |
| `universe.time_window.start/end` | ISO str | `engine/runner._resolve_time_window → ns 변환` | `iter_events_crypto_lob` 인자 |
| `universe.dates` | list[str] | bar path의 `iter_events(date)` | 날짜별 partition 루프 |
| `capital` | float | `engine/runner._build_config → auto-scale` | `Portfolio.starting_cash` |
| `params.time_stop_ticks` | int | `strategy.py` (직접 읽음) | primary exit 발동 시점 |
| `params.stop_loss_bps` | float | invariant checker | `sl_overshoot` 탐지 임계 |
| `params.profit_target_bps` | float | invariant checker | `pt_overshoot` 탐지 |
| `params.lot_size` | int ≥ 1 | Portfolio + invariant | max_position scaling |
| `params.max_position_per_symbol` | int | invariant checker | ×lot_size로 `max_position_exceeded` |
| `params.max_entries_per_session` | int | invariant checker | 일별 진입 제한 |
| `fees.commission_bps/tax_bps` | float | FeeModel | round-trip fee 계산 |
| `latency.submit_ms/jitter_ms` | float | LatencyModel | 주문 전송 지연 시뮬 |

---

## 3. crypto_lob 전용 규칙

1. **`universe.market: crypto_lob` 명시 필수** — 없으면 bar 경로로 분기.
2. **`universe.dates: []`** — non-empty면 Backtester가 bar-path `iter_events` 호출 → 크립토 데이터 경로 불일치.
3. **`universe.time_window.start/end`**: ISO datetime 문자열 (예: `"2026-04-19T06:00:00"`). timezone 생략 시 UTC 가정.
4. **`target_symbol` / `target_horizon` 완전 생략** — 잔여 필드가 있으면 `benchmark_vs_bh` 등이 잘못 dispatch.
5. **`capital`**: 인간 단위 USD 권장 (예: `1_000_000.0` = $1M). `runner._build_config`가 `CRYPTO_PRICE_SCALE=1e8` 자동 곱함.
   - `capital ≤ 1e9`이면 auto-scale 대상. 사전 스케일값(예: `1e14`) 허용하지만 가독성 저하.
6. **`fees.tax_bps: 0.0`** — 크립토에는 sell tax 없음.
7. **`strategy_kind: python` 필수** — DSL은 OHLCV close-based signal만 지원, LOB primitives 미지원.
8. **`handoff_metadata.brief_realism.entry_order_type`**: `MARKET | LIMIT_AT_BID | LIMIT_AT_ASK | LIMIT_MID` 중 하나.
9. **`universe.symbols`**: 표준 `[BTCUSDT, ETHUSDT, SOLUSDT]` 또는 preset `[top3]`.

**YAML snippet (LOB spec canonical)**:
```yaml
name: <strategy_id>
description: |
  [crypto_lob / <paradigm>] ...
capital: 1000000.0   # $1M USD — runner auto-scales × CRYPTO_PRICE_SCALE

universe:
  market: crypto_lob
  symbols: [BTCUSDT, ETHUSDT, SOLUSDT]
  time_window:
    start: "2026-04-19T06:00:00"
    end:   "2026-04-19T22:00:00"
  dates: []

fees:
  commission_bps: 0.0
  tax_bps: 0.0

latency:
  submit_ms: 5.0
  jitter_ms: 1.0
  seed: 42

strategy_kind: python

params:
  # alpha
  obi_thresholds: {BTCUSDT: 0.91, ETHUSDT: 0.94, SOLUSDT: 0.75}
  spread_gate: true
  # execution
  entry_price_mode: ask
  profit_target_bps: 1.09
  stop_loss_bps: 1.78
  time_stop_ticks: 10
  lot_size: 1
  max_entries_per_session: 500
  max_position_per_symbol: 1

signals: {}
entry:  { when: false, size: 1 }
exit:   { when: false }
risk:   { max_position_per_symbol: 1 }

handoff_metadata:
  signal_brief_rank: 1   # 1-indexed (1 = top_robust[0])
  brief_realism: {...}
  deviation_from_brief: {...}
```

---

## 4. crypto bar 전용 규칙

1. **`universe.dates`**: `["YYYY-MM-DD", ...]` 리스트 필수. 단일 날짜면 `["2025-07-01"]`.
2. **`target_symbol`**: 단일 문자열 (예: `"BTCUSDT"`).
3. **`target_horizon`**: `"1d"` | `"1h"` | `"15m"` | `"5m"` 중 하나.
4. **`universe.market`**: 생략 가능 (bar가 default).
5. **`universe.time_window`**: **없어야 함** — 있으면 LOB path 오분기 risk.

**YAML snippet (bar spec canonical — crypto_1h)**:
```yaml
name: <strategy_id>
description: ...
capital: 10000000.0
target_symbol: BTCUSDT
target_horizon: "1h"

universe:
  symbols: [BTCUSDT]
  dates: ["2025-07-01", "2025-07-02"]

fees:
  commission_bps: 2.0
  tax_bps: 0.0

latency:
  submit_ms: 5.0
  jitter_ms: 1.0

strategy_kind: python

params: { ... }
```

---

## 5. Handoff metadata 블록

감사/재현성을 위해 alpha-designer + execution-designer 산출물의 메타를 spec.yaml에 inline 보존.

| 필드 | 출처 | 용도 |
|------|------|------|
| `handoff_metadata.signal_brief_rank` | alpha-designer | 1-indexed; `scripts/audit_handoff.py`가 감사 |
| `handoff_metadata.brief_realism` | alpha-designer (전체 블록 복사) | spec vs 실제 EV 후행 검증 |
| `handoff_metadata.deviation_from_brief` | execution-designer (전체 블록) | PT/SL 편차 ±20% 검증 |
| `handoff_metadata.parent_lesson` | feedback-analyst (iterate 시 주입) | 다음 iter alpha-designer가 읽음 |
| `handoff_metadata.draft_notes.alpha_draft_path` | alpha-designer | critic이 원본 rationale 참조 |
| `handoff_metadata.draft_notes.execution_draft_path` | execution-designer | 동일 |

**규약**: 이 필드들은 읽기 전용 audit 정보. `strategy.py` / engine이 소비하지 않음.

---

## 6. Params 네이밍 규약 (표준 키)

strategy.py 구현자와 critic이 spec.yaml 해석에 혼선이 없도록 표준 키 고정.

| 범주 | 표준 키 | 타입 | 의미 |
|------|---------|------|------|
| Sizing | `lot_size` | int ≥ 1 | 주문당 수량 |
| Sizing | `max_position_per_symbol` | int | 심볼당 최대 동시 포지션 (× lot_size) |
| Session | `max_entries_per_session` | int | 일별 최대 진입 횟수 |
| Session | `entry_start_time_seconds` | int (0..86399) | 일 진입 시작 (UTC sec-of-day) |
| Session | `entry_end_time_seconds` | int | 일 진입 마감 |
| Entry | `entry_price_mode` | enum | `ask | bid | mid | bid_minus_1tick` |
| Entry | `entry_ttl_ticks` | int ≥ 0 | LIMIT 진입 TTL (0=비활성) |
| Entry | `cancel_on_bid_drop_ticks` | int ≥ 0 | bid 낙폭 취소 (0=비활성) |
| Exit | `profit_target_bps` | float > 0 | PT 임계 |
| Exit | `stop_loss_bps` | float > 0 | SL 임계 |
| Exit | `time_stop_ticks` | int ≥ 0 | time-based exit (0=비활성) |
| Exit | `trailing_stop` | bool | trailing 활성화 |
| Exit | `trailing_activation_bps` | float or null | 활성화 임계 (`trailing_stop=true`면 필수) |
| Exit | `trailing_distance_bps` | float or null | peak 대비 거리 |
| LOB | `obi_thresholds` | dict[str→float] | per-symbol OBI 임계 |
| LOB | `spread_gate` | bool | 진입 시 spread > PT면 reject |

**금지 alias**: `stop_bps`, `pt_pips`, `profit_target` (단위 모호), `lot`, `max_entries`

---

## 7. strategy_kind 선택 가이드

| strategy_kind | 언제 사용 | 제약 |
|---------------|-----------|------|
| `dsl` | bar 전략, 단순 signal (SMA cross 등) | `engine/dsl.py` 제한된 primitive만 |
| `python` | 대부분 실전 전략 (LOB, stateful entry) | `strategies/<id>/strategy.py` 필수 |
| `buyhold` | 베이스라인 비교 | 인자 없음, 첫 snap에 BUY |
| `alternating` | engine smoke test | 디버깅 전용 |

**규칙**: LOB은 `python` 실질적 필수. DSL이 LOB primitives 미지원.

---

## 8. Validation 절차

spec.yaml 작성 후 반드시 아래 순서로 실행:

```bash
# Step 1: 필드 구조 검증
python scripts/validate_spec.py strategies/<id>/spec.yaml
# → 통과: 녹색 "OK"
# → 실패: 누락/불일치 필드 구체 출력

# Step 2: Pydantic 출력 검증
python scripts/verify_outputs.py --agent spec-writer --output '<json>'
# → draft_md_path 존재 확인 등
```

**흔한 실패 패턴**:

| 증상 | 원인 | 수정 |
|------|------|------|
| `ValueError: time_window required` | LOB spec에 `dates: ["2026-04-19"]` | `dates: []`로 변경 |
| `runner._resolve_time_window → None` | bar spec에 `universe.market: crypto_lob` 오타 | market 필드 제거 또는 수정 |
| `FileNotFoundError: strategy.py` | `strategy_kind: python`인데 파일 없음 | `strategies/<id>/strategy.py` 생성 |
| `benchmark_vs_bh` 오분기 | LOB spec에 `target_symbol` 잔존 | 해당 필드 완전 삭제 |

---

## 9. Anti-patterns

1. **LOB spec에 `dates: ["..."]` 넣기** — engine이 bar-path `iter_events` 호출 → 크립토 CSV 경로 불일치. `dates: []` 필수.
2. **LOB spec에 `target_symbol: BTCUSDT` 유지** — `benchmark_vs_bh`가 이 값을 읽어 잘못된 bar BH 계산 경로로 분기.
3. **bar spec에 `universe.market: crypto_lob` 오타 삽입** — `time_window` 없음으로 runner `ValueError`.
4. **LOB fees.commission_bps를 taker 4로 설정하되 paradigm이 market_making** — maker fee(0 bps) 기준 전략에 taker fee 적용 → EV 왜곡.
5. **`capital: 1e14` 직접 지정** — auto-scale 우회이나 가독성 저하. 인간단위 권장 (`1_000_000.0`).
6. **`handoff_metadata.signal_brief_rank: 0` (0-indexed)** — Pydantic `ge=1` 위반. 1-indexed 필수.
7. **`params.obi_thresholds`를 float 단일값으로** — multi-symbol에서 symbol 매핑 실패. `dict[str→float]` 필수.
8. **`strategy_kind: dsl`로 LOB 시도** — DSL primitive가 LOB에 없어 모든 signal이 0.

---

## 10. References

- `engine/spec.py` — `load_spec`, `Universe` 데이터클래스 정의 (직접 소비처)
- `engine/runner.py` — `_build_config`, `_resolve_time_window` (필드 해석)
- `engine/simulator.py` — `Backtester` (market별 분기)
- `scripts/validate_spec.py` — 로컬 검증 도구
- `tests/fixtures/pilot_s3_idea.json` — bar spec regression 예시
- `references/python_impl_patterns.md §1` — 엔진 API 계약
