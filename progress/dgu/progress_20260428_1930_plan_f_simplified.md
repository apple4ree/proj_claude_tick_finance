---
date: 2026-04-28 19:30
tone: design
title: Plan F 단계적 → 동시 적용으로 재구조화
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

직전에 Plan F (\"Path F — Tool-use + Raw column read\") 의 가독성 개선 + 검토 진행. 점검 중 사용자 질문: \"Phase 1 과 2 를 **동시** 적용하는 게 낫지 않을까?\"

옛 디자인 (단계적):
- Phase 1 (Level 4 only, 1주) → smoke 측정 idle (3-4일) → Phase 2 진행 결정 → Phase 2 (3-4일)
- 총 약 2.3주 + 의사결정 idle

이 단계적 디자인의 진짜 가치는 \"Phase 1 만으로 충분하면 Phase 2 작업 절약\". 그러나:
- 시간 차이 거의 없음 (2.3주 vs 2주 동시)
- 효과 분리는 ablation v7a/b/c 로 어차피 가능
- 두 lever 가 직교 → 동시 진행해도 코드 충돌 없음, `data_tools.py` 같은 파일에 자연스럽게 통합

→ **단계적 디자인 폐기**, 동시 진행으로 재구조화.

## 가설 (Hypothesis)

\"Part A (Level 4 = tool-use) + Part B (Level 2 = raw column) 동시 적용 시 작업 시간 ~2주, 결과 quality 는 단계적 진행과 같음. Ablation v7a/b/c 가 두 lever 의 분리 효과 측정 충분.\"

가설 틀리면 (어떤 측면에서 단계적 진행이 좋다면): 사용자가 진행 중 결정 변경 가능.

## 변인 통제 및 설계

옛/새 디자인 비교:

| 차원 | 옛 (단계적) | 새 (동시) |
|---|---|---|
| 작업 시간 | ~2.3주 (1주 + idle 3-4일 + 1주) | ~2주 |
| Trigger 분기 | 3-way (A=보류 / B=Phase1만 / C=Phase1+2) | 2-way (A=보류 / B,C=Part A+B 동시) |
| 효과 분리 | Phase 1 smoke 후 결정 | Ablation v7a/b/c 한 번 |
| 코드 통합 | `data_tools.py` 두 번 수정 | 한 번 |
| 의사결정 idle | 있음 (Phase 1 결과 본 후) | 없음 |

## 철학 / 선택의 근거

**\"단계적 진행\" 의 매력 vs 실질 가치**:
- 매력: \"적은 위험으로 시작\" — 그러나 두 lever 모두 위험 0 (메모리 / cost / determinism 모두 검증됨)
- 매력: \"Phase 1 만으로 충분하면 절약\" — 그러나 v6 천장 (45% 확률) 시 Phase 1 만으론 부족 가능성 ↑
- 매력: \"효과 분리 측정\" — ablation 으로 사후 분리 가능

→ 단계적 진행이 줄 수 있는 \"실질 가치\" 가 작음. 단순화 (동시 진행) 가 자연스러움.

**\"Phase\" 명명 변경**:
- 옛: Phase 1 / Phase 2 — \"순차 단계\" 라는 인상
- 새: Part A / Part B — \"병렬 부분\" 의미

## 세션 컨텍스트

### 이미 수행하고 분석한 것 (Done & Analyzed)

이 세션 안의 흐름:
- v6 fresh run 진행 중 (~21:30 KST 종료 예상, 4-5 bps 천장 saturation 신호)
- v3 의 13.32 가 fixed-H over-counting 인공물 진단 — wiki concept + flow event 등록
- 병렬화 (#109) 완료 — `--parallel` flag, iter 35분 → ~10분 예상
- Archive lessons cheat sheet (#110) 완료 — failure modes + tried area map, LLM 자동 로드
- 사용자가 E (Path E) + F (Path F) 가 superset 관계 발견 → E delete, F 만 유지
- Plan F 가독성 개선 (662 → 513 줄, §0 용어 명확화 신설, TL;DR, Architecture 단순화)
- \"sub-agent\" 의 의미 명확화 (chain 1 의 LiteLLM 기반 LLM 호출 ≠ Claude Code 의 Agent tool)
- 사용자 의문: \"Phase 1+2 동시 적용\" → 본 progress

### 지금 수행·분석 중인 것 (In Progress)

- v6 fresh run (PID 3237121, iter_019+ 진행 중)
- v5 archive retroactive report.html 생성 완료 (25/25)
- 본 progress 의 wiki/flow 기록

### 수행·분석할 예정인 것 — 추측

- v6 종료 (~21:30 KST) → 결과 분석
- 분기:
  - net > 0 (25%): F 보류, paper writeup 우선
  - net ≤ 0 (75%): F (Part A + B) 즉시 시작, ~2주
- F 시작 시 §12 점검 체크리스트 6 항목 사전 검증 (~2시간)
- v7 ablation 3-way (병렬화로 12h compute) → 시너지 측정

## 다이어그램 (Diagrams)

### 옛 vs 새 디자인 비교

```
[옛 — 단계적 진행]
  Phase 1 (Level 4)
       ↓
   smoke 측정 (3-4일 idle)
       ↓
   결과 보고 Phase 2 결정
       ↓
   Phase 2 (Level 2 추가)
       ↓
   v7 ablation
   ─────────────────
   총 ~2.3주

[새 — 동시 진행]
  Part A + Part B 병행 (~2주)
       │
       └─→ v7 ablation v7a/b/c
       ─────────────────
   총 ~2주, 의사결정 idle 없음
```

### Ablation v7 의 분리 측정

```
v7a (baseline)              v7b (Part A only)            v7c (Part A + B)
═════════════               ═══════════════               ═══════════════
옛 v6 + 병렬화만             + agentic-mode               + agentic-mode
(no agentic, no raw col)                                  + allow-raw-columns

         │                          │                            │
         └──────── 25 iter ─────────┴────────── 25 iter ─────────┘
                  (parallel mode, ~4h each)
                  
                          │
                          ▼
                   결과 비교:
                   Δ_b = v7b − v7a    (Level 4 marginal 효과)
                   Δ_c = v7c − v7a    (Level 4 + Level 2 결합 효과)
                   시너지 = Δ_c − Δ_b   (Level 2 의 추가 효과)
```

### 작업 흐름 (14 day milestone)

```
Day  Part A (Level 4)              Part B (Level 2)
────────────────────────────────────────────────────────────
1    tool_use_loop.py              ─
2    4 query tools                 spec_parser.py (AST validator)
3    data_analyst.py + AGENTS.md   safe_eval_raw_expr
4    smoke (data_analyst 단독)      5번째 tool (query_raw_column)
5    signal_generator multi-turn   code_generator transpile
6    --agentic-mode flag            --allow-raw-columns + fidelity AST
7    smoke 1 iter (Part A)          smoke 1 iter (Part B)
8-10 통합 smoke (Part A + B 결합)
11-12 Ablation smoke (각 1 iter)
13-14 본격 ablation v7a/b/c (각 25 iter, 병렬화 with #109) → 12h compute
```

## 진행 / 결과 (Progress / Results)

- Plan F 갱신 — Phase → Part 명명 변경, 단계적 폐기
- §3 \"동시 적용 + Ablation — 단계적 진행 폐기\" 신설 (5 가지 이유 명시)
- §5/6 명명 \"Part A / Part B\"
- §5.5 통합 milestone (14 day, Part A + B 병행)
- §11 Trigger 단순화 (3-way → 2-way)
- Task #108 description + subject 갱신

## 발견 / 의미 (Findings / Implications)

- 단계적 진행의 가치는 작은 cost 영역에서만 의미. 두 lever 모두 위험 0 + 직교 + 같은 파일 통합 필요 → 동시 진행이 자연스러움.
- Plan 의 단순화 자체가 implementation 흐름의 friction 감소.
- Ablation 디자인이 단계적 진행의 \"분리 측정 가치\" 를 충분히 제공.

## 다음 단계 (Next)

1. v6 종료 대기 (~21:30 KST)
2. v6 결과 분석:
   - net > 0 발견: F 보류, paper writeup
   - net ≤ 0: F (Part A + B 동시) 시작
3. F 시작 시 §12 점검 체크리스트 6 항목 사전 검증
4. v7 ablation 3-way 결과로 시너지 측정
