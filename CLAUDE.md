# Tick Strategy Framework

KRX 10-level order book (H0STASP0) tick data로 전략을 자율 생성 → 백테스트 → 학습하는 프레임워크.

## Architecture

```
engine/          순수 Python 백테스트 엔진 (토큰 비용 = 0)
scripts/         CLI 도구 (audit, optuna, analyze, validate 등)
strategies/      생성된 전략 (49+), spec.yaml + strategy.py + report.json
knowledge/       Obsidian 호환 vault (45 lessons, 15 patterns)
.claude/agents/  9개 전문 agent 정의
.claude/commands/ /iterate, /new-strategy 커맨드
docs/            overview.html (전체 구조 문서)
```

## Agent Pipeline (전략 생성)

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

Support: `code-generator` (engine 확장), `meta-reviewer` (프레임워크 감사, 매 K회), `strategy-ideator` (legacy)

**Iteration context 전파**: 매 iteration 후 `strategies/_iterate_context.md`에 결과 누적. Critics 분석은 `strategies/<id>/alpha_critique.md`, `execution_critique.md`로 저장. 다음 iteration의 agent가 이 파일들을 읽어 이전 교훈을 직접 참조.

## KRX Constraints

- **Fee**: commission 1.5 bps (양측) + sell tax 18.0 bps = **21.0 bps round-trip** (엔진 실제 계산 기준)
- **Latency**: 5ms ± 1ms jitter (lookahead 없음)
- **Order types**: MARKET, LIMIT (resting, queue-ahead model), CANCEL
- **Long-only**: naked short 불가
- **EOD**: 매일 강제 청산

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
- `python scripts/signal_research.py extract --return-mode ask_bid` — spread-adjusted forward return (Type 7: microstructure cost)

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

전략 생성은 이제 데이터 기반입니다. Agent가 LLM 직감으로 signal/exit를 고르지 않고, 사전 분석된 signal brief에서 선택합니다.

### Flow

```
signal_research.py extract   (feature extraction, 1회 per symbol)
    ↓
generate_signal_brief.py     (Sharpe-ranked top 10 + optimal exits)
    ↓  data/signal_briefs/<symbol>.json
    ↓
alpha-designer               (read brief, pick from top 10)
    ↓
execution-designer           (use brief's optimal_exit as baseline)
    ↓
spec-writer / strategy-coder (build strategy from data-informed params)
    ↓
backtest + invariants + attribute_pnl (post-gen validation)
```

### 핵심 규칙

- `/new-strategy` 및 `/iterate`는 alpha-designer 호출 전에 **반드시** signal brief를 생성/갱신
- Brief의 `n_viable_in_top == 0`이면 해당 symbol 건너뜀 (iteration 낭비 방지)
- alpha-designer는 top 10 내에서만 signal 선택 (새 signal 발명 금지)
- execution-designer는 brief의 `optimal_exit`을 baseline으로 사용 (±20% 이내만 조정)

### 강제 검증

Agent 산출물에 `signal_brief_rank`, `deviation_from_brief` 필드 포함 → critic이 확인 → 규약 이탈 시 feedback-analyst가 재작업 요청.

### 사용법

```bash
# KRX symbol (fee 21 bps)
python scripts/generate_signal_brief.py --symbol 005930 --features-dir data/signal_research --fee 21.0

# Crypto symbol (fee 4 bps)
python scripts/generate_signal_brief.py --symbol BTC --features-dir data/signal_research/crypto --fee 4.0
```

## Data Universe

- **IS (In-Sample)**: 20260305 ~ 20260320 (12일) — 전략 개발용. 하락+상승 혼합 regime.
- **OOS (Out-of-Sample)**: 20260323 ~ 20260330 (6일) — 최종 검증용. 개발 중 절대 사용 금지.
- **Top-10 symbols**: 005930, 000660, 005380, 034020, 010140, 006800, 272210, 042700, 015760, 035420

## Key Commands

```bash
# 자율 루프 (N회)
/iterate 10 "seed description"

# 단일 이터레이션
/new-strategy "seed description"

# 백테스트
python -m engine.runner --spec strategies/<id>/spec.yaml --summary

# 파라미터 최적화
python scripts/optuna_sweep.py --spec strategies/<id>/spec.yaml --n-trials 50

# 감사
python scripts/audit_principles.py    # 12/12 must pass

# 지식 검색
python scripts/search_knowledge.py --query "keyword" --top 5
```

## Rules

- **구현은 Claude Code가 직접** 수행 (Edit/Write). 탐색 → 스펙 정리 → 구현 → 검증.
- **비가역 작업** (파일 삭제, git push, 대규모 refactor)은 사전 확인.
- **engine/ 수정 후** 반드시 `python scripts/audit_principles.py` 실행. regression 시 revert.
- **코드 리뷰 요청** 시 직접 리뷰하지 않고 `Skill` 도구로 `co-review` 호출.
- **OOS 날짜(20260326~30)는 전략 개발 중 절대 사용 금지.**
- **report.html 작성 시에는 반드시 한국어 위주로 작성할 것**
