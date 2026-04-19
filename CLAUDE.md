# Crypto Strategy Framework

Binance OHLCV bar 데이터(1d / 1h / 15m / 5m) 기반으로 전략을 자율 생성 → 백테스트 → 학습하는 프레임워크.

**Scope note (2026-04-19)**: 이 프로젝트는 2026-04-15 crypto pivot 이후 크립토 bar 데이터 전용으로 정리되었습니다. KRX tick(H0STASP0) 관련 legacy 자산은 `data/_archive/krx_legacy/` 및 `scripts/_legacy/`로 이동됐으며, unified `/experiment` 프레임워크는 KRX를 지원하지 않습니다. (이유: KRX 21 bps round-trip fee가 tick horizon edge를 잠식, lessons 반복 확인.)

## Architecture

```
engine/              순수 Python 백테스트 엔진 (토큰 비용 = 0)
  schemas/           Pydantic handoff contracts (AlphaHandoff, ExecutionHandoff, FeedbackOutput)
scripts/             CLI 도구 (verify_outputs, audit, optuna, analyze, validate 등)
strategies/          전략 산출물 루트 (현재 meta only: _drafts/, _trajectories/, _examples/, _iterate_context.md)
                     — 2026-04-19 archival 이후 모든 구체 전략은 re-generate 필요
knowledge/           Obsidian 호환 vault (49 lessons + patterns + seeds, README.md 포함)
.claude/agents/      16 전문 agent 정의 (alpha/execution designer, critics, writer, coder, 기타)
.claude/commands/    /experiment (canonical), /iterate & /new-strategy (deprecated)
docs/                overview.html + superpowers/specs + superpowers/plans + progress/
tests/               pytest suite + fixtures/ (pilot_s3 idea.json 등 regression 데이터)
literature/papers/   참조 논문
experiments/         _research_session + 개별 실험 아티팩트
```

## Unified Framework (end-to-end)

데이터 기반 α 발견 + agent 기반 설계 + 자동 검증이 하나의 flow로 묶임.

```
[Phase 1] scripts/discover_alpha.py        → signal_brief_v2.json  (IC ranking across symbols)
[Phase 2] ── design-mode=auto   ──→ scripts/gen_strategy_from_brief.py (rule-template)
          └─ design-mode=agent ──→ alpha-designer → execution-designer → spec-writer → strategy-coder
[Phase 2.5] scripts/intraday_full_artifacts.py / bar_full_artifacts.py  → report/trace/HTML
[Phase 3]   scripts/validate_strategy.py   → 4 gates (invariants / OOS / IR vs BH / cross-symbol)
[Phase 3.5] scripts/benchmark_vs_bh.py     → bh_benchmark.json
[Phase 4] ── feedback-mode=programmatic ──→ scripts/run_feedback.py → feedback_auto.*, _iterate_context.md
          └─ feedback-mode=agent         ──→ alpha-critic + execution-critic + feedback-analyst → knowledge/lessons/
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

Support: `code-generator` (engine 확장), `meta-reviewer` (프레임워크 감사, 매 K회), `portfolio-designer` (capital allocation), `strategy-ideator` (legacy)

**Iteration context 전파**: 매 iteration 후 `strategies/_iterate_context.md`에 결과 누적. Critics 분석은 `strategies/<id>/alpha_critique.md`, `execution_critique.md`로 저장. 다음 iteration의 agent가 이 파일들을 읽어 이전 교훈을 직접 참조.

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

- **Fee (default)**: Binance taker ≈ 4 bps round-trip (`--fee-bps` 로 설정; maker/네트워크/대체 거래소별 조정 가능)
- **Order types**: MARKET, LIMIT (resting, queue-ahead model), CANCEL
- **Long-only**: 엔진은 현재 naked short 금지 (crypto spot 기준)
- **Session**: 크립토는 24/7 연속 거래, 명시적 EOD 강제 청산 없음 (bar 프레임워크 특성상 bar 경계가 실질적 evaluation 포인트)
- **Bar units**: `crypto_1d` (1일), `crypto_1h` (1시간), `crypto_15m` / `crypto_5m`

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

- **Standard universe**: `BTCUSDT, ETHUSDT, SOLUSDT` (Binance perpetual/spot, multi-symbol robustness check 기준)
- **Data sources**:
  - `data/binance_daily/<SYM>.csv` — daily bars
  - `data/binance_multi/{1h,15m,5m}/<SYM>.csv` — intraday bars
- **IS / OOS split**: 실험별로 `--is-start`, `--is-end`, `--oos-start`, `--oos-end`로 명시. 관례: crypto_1h에서 IS ≈ 4 months, OOS ≈ 1-2 months (예: IS 2025-07-01~2025-10-31, OOS 2025-11-01~2025-12-31)
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
# 통합 진입점 (canonical) — 단일/다중 iteration + 디자인 모드 + 피드백 모드 통합
/experiment --market crypto_1h --symbols BTCUSDT,ETHUSDT,SOLUSDT \
            --is-start 2025-07-01 --is-end 2025-10-31 \
            --oos-start 2025-11-01 --oos-end 2025-12-31 \
            --design-mode agent --feedback-mode programmatic --n-iterations 1
#   --design-mode: auto (rule template) | agent (LLM chain) | skip
#   --feedback-mode: programmatic | agent | both

# 백테스트 (default: portfolio mode)
python -m engine.runner --spec strategies/<id>/spec.yaml --summary

# Agent 산출물 스키마 검증 (subprocess)
python scripts/verify_outputs.py --agent alpha-designer --output '<json>'

# 파라미터 최적화
python scripts/optuna_sweep.py --spec strategies/<id>/spec.yaml --n-trials 50

# 감사
python scripts/audit_principles.py    # 12/12 must pass

# 지식 검색
python scripts/search_knowledge.py --query "keyword" --top 5

# 테스트 (handoff schema 포함)
python3 -m pytest tests/test_handoff_*.py tests/test_verify_outputs_schema.py -v

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
- **KRX 복원 금지 (2026-04-19 결정)**. KRX tick 자산은 `data/_archive/krx_legacy/`, `scripts/_legacy/`로 이동. 복원이 필요하면 별도 설계 task로 올릴 것.
