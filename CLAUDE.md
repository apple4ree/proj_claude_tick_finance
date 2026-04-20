# Crypto Strategy Framework (Dual-Mode: OHLCV + LOB)

Binance crypto 데이터 기반 전략 자율 생성 → 백테스트 → 학습 프레임워크. **두 가지 데이터 모드**를 동시 지원:

- **Bar OHLCV** (1d / 1h / 15m / 5m): directional strategies (mean-reversion, momentum, breakout)
- **L2 Order Book (LOB)** (10-level, 100ms snapshot): LOB-aware strategies (market-making / ping-pong / spread capture)

**Scope note (2026-04-19 ~ 2026-04-20)**: KRX tick legacy + Qlib CSI500/SP500 경로 **완전 제거됨**. 크립토 전용. LOB 데이터는 `scripts/binance_lob_collector.py`가 WebSocket으로 forward-going 수집 (2026-04-19 시작, 상시 가동). **LOB end-to-end 파이프라인은 2026-04-20 활성화 완료** (α-1~α-6): engine LOB dispatch + discover_alpha_lob + lob_full_artifacts + BH/validate LOB 분기 + `/experiment --market crypto_lob` 통합 smoke 통과 (iter2 BTC+ETH +0.226 bps @ fee=0).

## Architecture

```
engine/              순수 Python 백테스트 엔진 (토큰 비용 = 0)
  schemas/           Pydantic handoff contracts (AlphaHandoff, ExecutionHandoff, FeedbackOutput)
  data_loader.py     CRYPTO_PRICE_SCALE=1e8 LOB int64 scaling + iter_events_crypto_lob
  simulator.py       Backtester (bar loop / LOB loop dispatch by universe.market)
  runner.py          capital auto-scale for crypto_lob + _resolve_time_window
scripts/             CLI 도구 (discover_alpha / discover_alpha_lob / *_full_artifacts / validate_strategy / benchmark_vs_bh / run_feedback / verify_outputs / audit / optuna 등)
  binance_lob_collector.py  상시 가동 (WebSocket depth20@100ms → hourly parquet)
references/          9 practitioner cheatsheets (agent consultation source of truth)
  exit_design.md / mean_reversion_entry.md / fee_aware_sizing.md
  microstructure_primer.md / market_making.md / trend_momentum_entry.md
  python_impl_patterns.md / portfolio_allocation.md
  signal_diagnostics.md / execution_diagnostics.md / spec_schema_guide.md
strategies/          전략 산출물 루트 (meta files: _drafts/, _trajectories/, _iterate_context.md)
knowledge/           Obsidian 호환 vault (lessons + patterns + seeds)
.claude/agents/      11 active agents (설계 7 + 비평 2 + support 2)
.claude/commands/    /experiment (canonical); /iterate & /new-strategy (deprecated)
docs/                overview.html + superpowers/specs + superpowers/plans + progress/
tests/               pytest suite + fixtures/ (pilot_s3 idea.json 등 regression 데이터)
literature/papers/   참조 논문
experiments/         _research_session + 개별 실험 아티팩트 + run_<date>/experiment_summary.md
data/
  binance_daily/     crypto_1d bars
  binance_multi/{1h,15m,5m}/  intraday bars
  binance_lob/<SYM>/<YYYY-MM-DD>/<HH>.parquet  LOB snapshots (forward-going)
  signal_briefs_v2/<market>.json  Phase 1 산출물
```

## Unified Framework (end-to-end)

데이터 기반 α 발견 + agent 기반 설계 + 자동 검증이 하나의 flow로 묶임.

```
[Phase 1] discover_alpha.py (bar) OR discover_alpha_lob.py (LOB)
             → data/signal_briefs_v2/<market>.json  (cross-symbol IC + robustness + per-signal calibration)
[Phase 2] ── design-mode=auto   ──→ scripts/gen_strategy_from_brief.py (rule-template, bar only)
          └─ design-mode=agent ──→ alpha-designer → execution-designer → spec-writer → strategy-coder
                                   (각 단계 Pydantic verify_outputs 검증 강제)
[Phase 2.5] bar_full_artifacts.py (daily) OR intraday_full_artifacts.py (1h/15m/5m) OR lob_full_artifacts.py (LOB)
             → report.json / trace.json / analysis_trace.{json,md} / report.html
[Phase 3]   validate_strategy.py           → 4 gates (invariants / OOS / IR vs BH / cross-symbol)
[Phase 3.5] benchmark_vs_bh.py              → bh_benchmark.json (bar vs LOB 분기)
[Phase 4] ── feedback-mode=programmatic ──→ run_feedback.py → feedback_auto.*, _iterate_context.md
          └─ feedback-mode=agent         ──→ alpha-critic + execution-critic + feedback-analyst
                                             → knowledge/lessons/<YYYYMMDD>_<id>_<slug>.md
```

**진입점**: `/experiment --market crypto_1h --symbols BTCUSDT,ETHUSDT,SOLUSDT --is-start ... --oos-start ... --design-mode (auto|agent) --feedback-mode (both|programmatic|agent)`

`.claude/commands/experiment.md`가 이 전체 과정을 Claude가 읽어서 실행하도록 스크립트화. 각 단계는 개별 스크립트로도 호출 가능.

## Agent Pipeline (설계/비평 담당, `/experiment`의 일부)

```
alpha-designer → execution-designer → spec-writer → [strategy-coder] → backtest-runner → [alpha-critic + execution-critic] → feedback-analyst
```

| Agent | 역할 | 산출물 |
|---|---|---|
| alpha-designer | 신호 edge (WHEN/WHY) | `_drafts/<name>_alpha.md` |
| execution-designer | 주문 메커닉 (HOW) | `_drafts/<name>_execution.md` |
| spec-writer | YAML 생성 + 교정 검증 | `strategies/<id>/spec.yaml` |
| strategy-coder | Python strategy.py 구현 (python path만) | `strategies/<id>/strategy.py` |
| backtest-runner | 백테스트 실행 | report JSON (roundtrips, per_day, fill context) |
| alpha-critic | 신호 품질 분석 (WIN/LOSS 분리, 선택성, 레짐 의존) | alpha critique JSON |
| execution-critic | 체결 메커닉 분석 (exit 분포, fee 부담, stop/target 교정) | execution critique JSON |
| feedback-analyst | 두 critique 합의 → 최종 lesson + seeds | `knowledge/lessons/`, feedback.json |

Support: `code-generator` (engine 확장), `meta-reviewer` (프레임워크 감사, 매 K회), `portfolio-designer` (capital allocation — dormant, LOB multi-symbol scale-up 시 활성화), `backtest-runner` (wrapper).

Active agent count: **11**. 2026-04-20 clean-up: 미사용 agents (`strategy-ideator` legacy + `context-quality-reviewer` / `project-automation-auditor` / `session-pattern-analyzer` / `skill-portfolio-analyzer` — check-harness plugin 전용) 삭제.

### Agent → References mapping

각 설계/비평 agent는 `references/` 실천 치트시트를 on-demand consult. 인용 필수 (critic이 미인용 설계는 flag).

| Agent | Consulted references |
|---|---|
| alpha-designer | `mean_reversion_entry.md` / `trend_momentum_entry.md` (paradigm별), `fee_aware_sizing.md`, `microstructure_primer.md` (LOB) |
| execution-designer | `exit_design.md`, `fee_aware_sizing.md`, `market_making.md` (MM 패러다임) |
| spec-writer | `spec_schema_guide.md` (항상) — market별 required-field matrix |
| strategy-coder | `python_impl_patterns.md` (항상), `exit_design.md` §2.2 / `market_making.md` §2.3,§7 |
| portfolio-designer | `portfolio_allocation.md` (항상), `fee_aware_sizing.md` §3 |
| alpha-critic | `signal_diagnostics.md` (항상 5-step 고정 진단), `mean_reversion_entry.md` / `trend_momentum_entry.md` §2 |
| execution-critic | `execution_diagnostics.md` (항상 5-step + counterfactual 의무), `exit_design.md` §1,§4, `fee_aware_sizing.md` §6, `market_making.md` §3,§4 |

**Iteration context 전파**: 매 iteration 후 `strategies/_iterate_context.md`에 결과 누적. Critics 분석은 `strategies/<id>/alpha_critique.md`, `execution_critique.md`로 저장. 다음 iteration의 agent가 이 파일들 + 부모 `analysis_trace.md` (per-RT MFE/MAE/capture_pct)를 읽어 이전 교훈을 직접 참조.

## Agent Handoff Schema (Pydantic)

3개 handoff 경계(`alpha→execution`, `execution→spec-writer`, `critic→feedback`)에 pydantic 검증 레이어 적용 (2026-04-19 도입, spec `docs/superpowers/specs/2026-04-17-agent-handoff-schema-design.md`).

```
engine/schemas/base.py         HandoffBase (공통 필드: strategy_id, timestamp, agent_name, model_version, draft_md_path)
engine/schemas/alpha.py        AlphaHandoff + BriefRealismCheck (핵심 검증)
engine/schemas/execution.py    ExecutionHandoff + DeviationFromBrief + 서브 모델들
engine/schemas/feedback.py     FeedbackOutput
```

**BriefRealismCheck의 역할**: Agent가 brief의 EV를 *인용*만 하고 실행 조건(spread cross, horizon, regime)과의 불일치를 검증하지 않는 "guessing처럼 보이는 분석" 패턴을 차단. 필수 계산 필드 누락 또는 `adjusted_ev ≤ 0 + decision="proceed"` 같은 모순은 hard-fail.

**검증 강제 경로**:
```bash
python scripts/verify_outputs.py --agent alpha-designer --output '<json>'
# → {"ok": true/false, "failures": [...], "warnings": [...]}
```
`/experiment`의 `design-mode=agent` path가 각 agent 호출 직후 이 스크립트를 실행, `ok=false`면 iteration abort.

**Agent prompt 업데이트**: `.claude/agents/alpha-designer.md`, `execution-designer.md`, `feedback-analyst.md`의 `### Output` 섹션이 pydantic schema를 참조. 기존 분석 prose는 그대로 보존.

## Market Constraints (Crypto)

- **Fee (default)**: Binance taker ≈ 4 bps round-trip (`--fee-bps`로 설정). Market-making paradigm에서는 maker fee 0 bps 또는 negative (rebate) 가정 가능.
- **Order types**: MARKET, LIMIT (resting, queue-ahead model), CANCEL (per-symbol 일괄, per-order 지원 안 함)
- **Long-only**: 엔진은 현재 naked short 금지 (crypto spot 기준; perpetual futures는 별도 모드로 추가 가능)
- **Session**: 크립토는 24/7 연속 거래, 명시적 EOD 강제 청산 없음 (bar path만 EOD close 적용)
- **Bar markets**: `crypto_1d` (1일), `crypto_1h` (1시간), `crypto_15m` / `crypto_5m` — date-partitioned iterator
- **LOB market**: `crypto_lob` — 10-level order book @ 100ms cadence. `data/binance_lob/<SYM>/<YYYY-MM-DD>/<HH>.parquet`. 전용 iterator `iter_events_crypto_lob(start_ns, end_ns, symbols)`. LOB spec은 `universe.market: crypto_lob` + `universe.time_window.{start,end}` 필수, `dates: []` 필수, `target_symbol/target_horizon` 금지.
- **LOB capital 자동 스케일링**: `CRYPTO_PRICE_SCALE = 1e8` (satoshi-equivalent int64). `engine/runner._build_config`가 `market=crypto_lob` AND `capital ≤ 1e9` 이면 자동으로 ×1e8 스케일. spec에 인간 단위 USD (예: `capital: 1000000` = $1M) 권장.

## Spec-Invariant Checker

엔진이 spec.yaml 파라미터에서 runtime invariant를 **자동 추론**하여 매 fill 이벤트마다 체크합니다. Agent는 이 시스템의 존재를 몰라도 되며 (수정 0), 위반은 `report.json.invariant_violations`에 결정적으로 기록됩니다.

자동 추론되는 7개 invariant:

| 유형 | spec 파라미터 | severity | tolerance |
|------|------------|----------|-----------|
| sl_overshoot | stop_loss_bps | high | ±10 bps |
| pt_overshoot | profit_target_bps | low | ±20 bps |
| entry_gate_end_bypass | entry_end_time_seconds | high | 0 |
| entry_gate_start_bypass | entry_start_time_seconds | high | 0 |
| max_entries_exceeded | max_entries_per_session | high | 0 |
| max_position_exceeded | max_position_per_symbol × lot_size | high | 0 |
| time_stop_overshoot | time_stop_ticks | medium | ±50 ticks |

**분석 도구:**
- `python scripts/sweep_invariants.py` — 전 전략 retroactive 위반 카운트
- `python scripts/compare_detection.py` — critic 서술 vs 자동 checker 비교 (논문용)
- (KRX-legacy tools `signal_research.py`, `generate_signal_brief.py`, `optimal_params.py` are archived under `scripts/_legacy/` as of 2026-04-19 crypto pivot)

### Counterfactual PnL Attribution

엔진은 `--strict` 모드를 지원합니다. 이 모드에서는 invariant 위반이 발생하려는 순간 엔진이 개입해서 spec대로 강제합니다 (REJECT 또는 FORCE SELL 주입).

```bash
# 단일 전략의 clean_pnl vs bug_pnl 계산
python scripts/attribute_pnl.py --strategy <strategy_id>

# 전 전략 일괄
python scripts/attribute_pnl.py --all
```

출력:
- `normal_pnl` — 현행 backtest 결과
- `strict_pnl_clean` — spec 완전 준수 시 기대 수익 (true counterfactual)
- `bug_pnl` — 둘의 차이, 즉 invariant 위반에 의한 기여 (양수면 버그가 수익에 도움, 음수면 해)
- `clean_pct_of_total` — 전체 수익 중 진짜 edge 비중

Iterate 루프의 feedback-analyst는 clean_pnl을 기준으로 진짜 edge 여부를 판단해야 함.

## Data-Driven Generation Pipeline (Phase A → Generation)

전략 생성은 데이터 기반입니다. Agent가 LLM 직감으로 signal/exit를 고르지 않고, `discover_alpha.py`가 산출한 brief에서 선택합니다.

### Flow

```
discover_alpha.py                 (cross-symbol IC + robustness + per-signal calibration, 1회 per run)
    ↓  data/signal_briefs_v2/<market>.json
    ↓
alpha-designer                    (read brief, pick from top_robust with viable==true)
    ↓
execution-designer                (use brief's optimal_exit as baseline, ±20% 조정 범위)
    ↓
spec-writer / strategy-coder      (build strategy from data-informed params)
    ↓
backtest + invariants + attribute_pnl (post-gen validation)
```

### 핵심 규칙

- `/experiment --design-mode agent`는 alpha-designer 호출 전에 **반드시** signal brief(v2)를 생성/갱신
- `top_robust`가 비어 있거나 어떤 엔트리도 `viable==true`가 아니면 STOP → escape_route 제안
- alpha-designer는 `top_robust` 내에서만 signal 선택 (새 signal 발명 금지)
- execution-designer는 brief의 `optimal_exit`을 baseline으로 사용 (±20% 이내만 조정, Pydantic `DeviationFromBrief.within_band`로 강제)

### 강제 검증

1. **필드 의무** — Agent 산출물에 `signal_brief_rank`, `deviation_from_brief`, `brief_realism` 포함. Pydantic 모델이 누락 시 hard-fail.
2. **계산 일관성** — `adjusted_ev_bps = brief_ev * horizon_scale − spread_cross − regime_adj`가 `max(0.5, 5%)` 허용오차 내. 불일치 시 reject.
3. **의사결정 일관성** — `adjusted_ev_bps ≤ 0`일 때 `decision="proceed"` 금지. Regime mismatch는 adverse adjustment 동반 필수.

### 사용법

```bash
# Crypto 1h universe (Binance, fee 4 bps)
python scripts/discover_alpha.py \
  --market crypto_1h --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --is-start 2025-07-01 --is-end 2025-10-31 \
  --fee-bps 4.0 --threshold-percentile 90 \
  --output data/signal_briefs_v2/crypto_1h.json
```

## 3-Axis Trajectory System

전략 생성을 3개 독립 축으로 분리하고, 각 축에서 최적 trajectory를 선택/mutation/crossover합니다.

### 3개 축
| 축 | 질문 | Agent | Pool 저장 |
|---|---|---|---|
| Alpha | "어떤 종목의 어떤 signal?" | alpha-designer | strategies/_trajectories/alpha_pool.json |
| Execution | "PT/SL/trailing 어떻게?" | execution-designer | strategies/_trajectories/exec_pool.json |
| Portfolio | "종목 배분 얼마나?" | portfolio-designer (NEW) | strategies/_trajectories/port_pool.json |

### 핵심 연산
- **Selection**: pool에서 score 상위 trajectory 선택
- **Mutation**: 기존 trajectory의 파라미터를 ±10~20% 변형
- **Crossover**: 서로 다른 iteration의 best α × ε × π 조합
- **Localization**: 실패 시 어느 축이 원인인지 진단 → 그 축만 교체

### 사용법
```bash
python scripts/trajectory_pool.py seed --briefs-dir data/signal_briefs
python scripts/trajectory_pool.py summary
python scripts/trajectory_pool.py top --axis alpha --n 5
```

## Data Universe (Crypto)

- **Standard universe**: `BTCUSDT, ETHUSDT, SOLUSDT` (Binance spot, multi-symbol robustness check 기준)
- **Data sources**:
  - `data/binance_daily/<SYM>.csv` — daily bars
  - `data/binance_multi/{1h,15m,5m}/<SYM>.csv` — intraday bars
  - `data/binance_lob/<SYM>/<YYYY-MM-DD>/<HH>.parquet` — LOB 20-level snapshots @ 100ms (top-10 level을 engine이 소비). `scripts/binance_lob_collector.py` 상시 가동.
- **IS / OOS split**:
  - Bar: `--is-start`/`--is-end`를 `YYYY-MM-DD`로. 관례 crypto_1h IS ≈ 4 months, OOS ≈ 1-2 months (예: IS 2025-07-01~2025-10-31, OOS 2025-11-01~2025-12-31)
  - LOB: ISO datetime (UTC), 예: IS `2026-04-19T06:00:00 ~ 2026-04-19T22:00:00` (16h), OOS `2026-04-19T22:00:00 ~ 2026-04-20T00:00:00` (2h). 장기 실험은 LOB 축적 분량 성장에 따라 창 확장.
- **Archived (KRX legacy)**: `data/_archive/krx_legacy/` — 이전 KRX top-10 tick 데이터 + v1 briefs. unified flow에서 참조되지 않음.

## Backtest Mode (2026-04-19 변경)

**Default = 포트폴리오 모드**: 단일 자본 풀을 multi-symbol 전체에 공유, 하나의 `engine.runner` 실행.

```bash
# 기본 (portfolio mode)
python -m engine.runner --spec strategies/<id>/spec.yaml --summary

# 분석 opt-in: 심볼별 독립 실행, fresh capital, 집계 리포트
python -m engine.runner --spec strategies/<id>/spec.yaml --per-symbol --summary
```

Primary metric: 포트폴리오 `return_pct` (shared-pool realized). `--per-symbol`은 디버깅/분석 용도로만 사용. 2026-04-19 이전 per-symbol baseline은 포트폴리오 모드와 직접 비교 불가 — 재평가 필요.

## Key Commands

```bash
# 통합 진입점 (canonical) — bar
/experiment --market crypto_1h --symbols BTCUSDT,ETHUSDT,SOLUSDT \
            --is-start 2025-07-01 --is-end 2025-10-31 \
            --oos-start 2025-11-01 --oos-end 2025-12-31 \
            --design-mode agent --feedback-mode both --n-iterations 10

# 통합 진입점 — LOB (datetime UTC, 보통 smoke-test에만)
/experiment --market crypto_lob --symbols BTCUSDT,ETHUSDT,SOLUSDT \
            --is-start '2026-04-19T06:00:00' --is-end '2026-04-19T22:00:00' \
            --oos-start '2026-04-19T22:00:00' --oos-end '2026-04-20T00:00:00' \
            --design-mode agent --feedback-mode both --n-iterations 2 --smoke-test
#   --design-mode: auto (rule template, bar only) | agent (LLM chain) | skip
#   --feedback-mode: programmatic | agent | both

# Phase 1 standalone
python scripts/discover_alpha.py      --market crypto_1h --symbols ... --is-start ... --output ...   # bar
python scripts/discover_alpha_lob.py  --symbols ... --is-start '...' --is-end '...' --output ...    # LOB

# 백테스트
python -m engine.runner --spec strategies/<id>/spec.yaml --summary          # portfolio mode
python -m engine.runner --spec strategies/<id>/spec.yaml --per-symbol       # 분석 opt-in

# Phase 2.5 post-processor (artifact 생성 + MFE/MAE 계산)
python scripts/lob_full_artifacts.py     --id <id>   # LOB
python scripts/intraday_full_artifacts.py --id <id>  # 1h/15m/5m
python scripts/bar_full_artifacts.py      --id <id>  # daily

# Agent 산출물 스키마 검증
python scripts/verify_outputs.py --agent alpha-designer --output '<json>'

# LOB 수집기 상태 확인
pgrep -af binance_lob_collector
ls -la data/binance_lob/BTCUSDT/ | tail

# 감사
python scripts/audit_principles.py    # 12/12 must pass

# 지식 검색
python scripts/search_knowledge.py --query "keyword" --top 5

# 테스트
python3 -m pytest tests/ -q                                               # 전체 (~45s)
python3 -m pytest tests/test_handoff_*.py tests/test_verify_outputs_schema.py -v  # schema만

# Legacy (deprecated — /experiment로 대체)
/iterate 10 "seed description"
/new-strategy "seed description"
```

## Rules

- **구현은 Claude Code가 직접** 수행 (Edit/Write). 탐색 → 스펙 정리 → 구현 → 검증.
- **비가역 작업** (파일 삭제, git push, 대규모 refactor)은 사전 확인.
- **engine/ 수정 후** 반드시 `python scripts/audit_principles.py` 실행. regression 시 revert.
- **engine/schemas/ 수정 후** 반드시 `python3 -m pytest tests/test_handoff_*.py` 통과 확인.
- **Agent prompt (`.claude/agents/*.md`) 수정 시** `### Output` 섹션은 Pydantic schema 참조 형태 유지, 기타 workflow/rationale prose는 보존 (narrative regression 방지).
- **코드 리뷰 요청** 시 직접 리뷰하지 않고 `Skill` 도구로 `co-review` 호출.
- **코드 생성/수정 후** 반드시 `Skill` 도구로 `co-review`를 호출하여 Codex 코드 리뷰를 받는다. 리뷰 결과의 지적 사항을 수정/보완한 뒤 다시 `co-review`를 호출하여 통과할 때까지 반복.
- **OOS window는 전략 개발 중 절대 사용 금지.** 실험별로 `--oos-start`, `--oos-end`로 명시하고 `scripts/validate_strategy.py`에서만 평가.
- **report.html 작성 시에는 반드시 한국어 위주로 작성할 것**
- **평가는 multi-symbol (크립토 standard universe BTC/ETH/SOL) portfolio mode 기본**. 단일 심볼 / per-symbol은 debugging/analysis opt-in.
- **Iteration budget**: `/experiment --n-iterations`는 **반드시 ≥ 10** (2026-04-19 policy). 1-shot 실행 금지. `--smoke-test` 플래그는 예외 (인프라 검증 전용, 성과 평가 금지).
- **KRX / 非-crypto 시장 복원 금지** (2026-04-19 결정). 크립토 전용 프레임워크로 확정.
- **`signal_brief_rank`는 1-indexed** (2026-04-20). `1 = top_robust[0]` (최상위). execution-designer는 `top_robust[signal_brief_rank - 1]`로 인덱싱. Pydantic `ge=1, le=10` 강제.
- **LOB spec 필수 필드**: `universe.market: crypto_lob` + `universe.time_window.{start,end}` (ISO UTC) + `universe.dates: []`. `target_symbol`/`target_horizon`는 LOB spec에 **절대 포함 금지**. 상세: `references/spec_schema_guide.md §1, §3`.
- **LOB capital**: 인간 단위 USD로 기입 (예: `capital: 1000000` = $1M). runner가 `CRYPTO_PRICE_SCALE=1e8` 자동 적용. 사전 스케일된 값(`1e14`)도 허용하지만 가독성 저하.
- **References 인용 의무**: designer/critic agents는 `references/*.md` §번호 형태로 인용. 미인용 설계는 critic이 flag. `references/README.md`에 각 agent의 injection path 명시.
- **`/experiment` 중간 선택지 제시 금지** (2026-04-20). orchestrator가 "몇 iter로 할까요?", "어떤 rank만?", "foreground vs background?", "scope 좁힐까요?" 등의 질문으로 실행을 차단해선 안 됨. launch 시 CLI 인자가 최종 contract. 변경 필요 시 사용자가 `Ctrl+C` abort 후 재실행. 상세 규칙은 `.claude/commands/experiment.md` "Execution discipline" 섹션.
- **`/experiment` 1 iter = 1 portfolio strategy** (2026-04-20). `universe.symbols`에 target 심볼을 모두 unified해 **하나의 spec.yaml**을 만든다. `--ranks 1,2,3`은 iter 단위로 cycle (iter 1 → rank 1, iter 2 → rank 2 …) — 한 iter 내에서 다중 rank/심볼 spawn 금지. n_iterations=10 → 정확히 10 strategies.
