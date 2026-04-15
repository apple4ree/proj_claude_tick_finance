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

## KRX Constraints

- **Fee**: commission 1.5 bps + sell tax 18.0 bps = **19.5 bps round-trip**
- **Latency**: 5ms ± 1ms jitter (lookahead 없음)
- **Order types**: MARKET, LIMIT (resting, queue-ahead model), CANCEL
- **Long-only**: naked short 불가
- **EOD**: 매일 강제 청산

## Data Universe

- **IS (In-Sample)**: 20260316 ~ 20260325 (8일) — 전략 개발용
- **OOS (Out-of-Sample)**: 20260326 ~ 20260330 (3일) — 최종 검증용. 개발 중 절대 사용 금지.
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
