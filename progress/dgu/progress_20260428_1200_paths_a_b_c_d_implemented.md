---
date: 2026-04-28 12:00
tone: design
title: 4가지 개선 묶음 구현 완료 + 사전 검증
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

직전(2026-04-27 저녁) 의 v5 fresh run 분석 결과: 25 반복 × 78개 신호 모두 KRX 23 bps 수수료 통과 못함. 신호의 한 거래당 평균 가격 변동량이 max 4.74 bps. v3 의 13.32 bps 보다 오히려 낮음.

\"왜 v5 가 v3 보다 나빴나\" 진단 결과 4가지 원인 추정:
1. LLM 의 \"이 신호로 +5 bps 잡을 것\" 같은 추측이 실측 데이터에 anchored 안 됨 (±100% 어긋남)
2. LLM 의 prompt / 과거 iteration 로그가 비대 (872 줄) — attention 분산
3. 백테스트가 \"매수도 매도도 mid 가격\" 가정 → 실제 maker 거래의 spread 회수 누락
4. 신호 패턴 saturation (top 10 중 7개가 \"obi_1 + 장 시작 + book shape\" 변형)

본 progress 는 이 4가지 원인에 대응하는 4 lever (\"Path\" A/B/C/D) 의 동시 구현. v6 fresh run 의 사전 단계.

## 가설 (Hypothesis)

\"4 lever 동시 적용 시 maker_gross 14 bps 임계 (= mid 14 + spread 9 가 fee 23 통과) 도달하는 신호가 발견된다\".

각 lever 별 sub-hypothesis:
- A (LLM 캘리브레이션): hypothesis 의 quality (template 완전성) 가 v5 의 0/3 → ≥ 75% 로 향상
- B (Maker 호가 회수): 같은 신호의 realized gross 가 mid 대비 +5~10 bps 보강
- C (시장 통계 표): LLM 이 cell-level magnitude 의 baseline 를 알게 되어 hypothesis 가 anchored
- D (보유 시간 표): LLM 이 보유 시간별 alpha (drift 보정 후) 표 참조 → 더 긴 보유 시간 신호 등장

가설이 맞다면: smoke test 의 hypothesis 4/4 template 완전, maker 효과 +5~10 bps 일관, 신호 패턴 다양화.
가설이 틀리면 (smoke 결과 약하면): LLM 의 hypothesis-result divergence 가 lever 만으로는 못 닫히는 fundamental 문제 → Path E (agentic tool-use) 또는 chain 2 통합.

## 변인 통제 및 설계 (Experimental Design)

- **독립 변수**: LLM references (Path A/C/D) + 백테스트 회계 방식 (Path B)
- **종속 변수**: hypothesis template 완전성, maker_gross 평균, mean_dur 분포, top-10 신호의 primitive family 다양성
- **통제 변수**: 종목 (005930, 000660, 005380), 날짜 (20260316~25, 8 거래일), iteration 25, candidates 4, regime-state 패러다임, fee 23 bps RT
- **비교 baseline**: v5 의 동일 setup (78 specs). v6 = (v5 + 4 lever).

## 철학 / 선택의 근거 (Why this approach)

\"한 lever 씩 검증\" 보다 \"동시 적용\" 선택. 이유:
- v5 의 4가지 원인이 서로 약간 결합 (예: \"LLM prompt 비대\" 와 \"신호 패턴 saturation\" 이 둘 다 prompt 의 문제). 분리 검증이 비효율.
- 시간 자원: lever 1개씩 5번 fresh run = 25시간. 통합 1번 = 5시간.
- v3/v4/v5 와의 ablation 은 \"v5 (4 lever 없음) vs v6 (4 lever 있음)\" 으로 충분히 clean.

대신 비용: 어느 lever 가 효과의 어느 비율 차지하는지 분리 안 됨. 추후 \"lever ablation run\" 으로 분리 측정 가능 (그러나 우선순위 낮음).

또 \"Path E (agentic tool-use)\" 는 의도적으로 보류. 이유: heavy implementation (~30h) + cost 5x. v6 결과 본 뒤에 정말 필요한지 결정.

## 세션 컨텍스트 (Session Context)

### 이미 수행하고 분석한 것 (Done & Analyzed)

본 progress 직전까지 (2026-04-27 저녁 ~ 2026-04-28 12:00) 의 작업:

- v5 fresh run 결과 집계 (78 specs, best 4.74 bps, 0/78 fee 통과)
- v5 의 4가지 원인 진단 (LLM unanchored / prompt 비대 / mid-only / saturation)
- 5개 path 의 wiki 페이지 (post-v5 roadmap + path-a~e) 작성
- 사용자와 적용 순서 합의: \"Option 1 — A → C → D → smoke → B 순\"
- Path A 구현: quick_ref.md 신규 + prior_iterations_index.md 트림 (872→150줄) + auto-bloat 분리
- Path C 구현: empirical_baselines.py 작성, 380만 tick 집계, 15 cells × 5 metrics
- Path D 구현: t_scaling.py 작성, 9 T × 5 primitives, **macro drift bias 발견하고 보정** (alpha vs drift 컬럼 추가)
- A+C+D smoke (1 iter × 1 sym × 1 date): hypothesis 4/4 template 완전, diversity 회복
- Path B 구현: schemas.py 확장 (execution_mode, expectancy_maker_bps, avg_spread_*) + backtest_runner.py 의 maker_optimistic 분기 + orchestrator CLI flag
- Path B smoke (top 5 v5 specs × 8 dates × 3 syms): 평균 +9.22 bps maker gain, 측정 spread 9.21 bps (사전 가정 5 bps 의 1.8x)

### 지금 수행·분석 중인 것 (In Progress)

본 progress 작성 시점에 동시에 돌아가는 작업:

- LabHub Flow / Wiki 정리 (오늘 ~12:00 까지 진행) — 곧 Phase 5 까지 완료 예정
- v6 fresh launch 준비 — iterations/ archive + 새 fresh dir 생성 직전

### 수행·분석할 예정인 것 — 추측 / 가능성 (Planned, speculative)

본 progress 직후의 분기:

- v6 fresh launch (PID 별도, ~5h) — 4 lever 동시 적용 첫 정식 실험
- v6 종료 후 결과별 분기:
  - **net > 0 spec ≥ 1 발견**: 프로젝트 first deployable signal. Paper §Results 시작.
  - **net 0 ~ -5 (margin)**: Path E (agentic tool-use) 로 LLM 의 cell query 정확도 향상 시도.
  - **net ≤ -10**: Fundamental rethink — chain 2 (queue model) 또는 multi-day paradigm 검토.

추측이라 확정 아님 — 결과 보고 결정.

## 다이어그램 (Diagrams)

### v5 천장의 4 원인 → 4 lever 매핑

```
v5 fresh run 결과:  best 4.74 bps gross  /  fee 23 bps  →  -18 bps gap

   ┌─ 원인 1: LLM의 magnitude 추측이 데이터에 anchored 안 됨 (±100% off)
   │           ↓
   │       Path A: quick_ref.md + AGENTS.md trim        ━━━━━━━━━┓
   │           Path C: 시장 통계 표 (15 cells)               ━━━━┫
   │           Path D: 보유시간 표 (9 T values, drift 보정)  ━━━━┫
   │                                                              ┃
   ├─ 원인 2: Prompt 비대 → attention 분산                        ┃
   │           ↓                                                  ┃
   │       Path A: 옛 iteration 로그 872줄→150줄                ━━┛
   │
   ├─ 원인 3: 백테스트가 mid-only → spread 회수 누락
   │           ↓
   │       Path B: maker_optimistic 모드 (BID/ASK 회계)
   │
   └─ 원인 4: 신호 패턴 saturation (top 10 중 7개가 같은 변형)
               ↓
           Path A + C + D 결합 (다른 영역 노출)
```

### Path B 의 회계 mechanism

```
옛 mid-to-mid:                   매수      매도
                                  ↓         ↓
                                 mid ──── mid
                                 (이론, 비용 0)

새 maker_optimistic (long):                BID  mid  ASK
                              entry  →     ●━━━━┷━━━━○
                              exit                    │   BID  mid  ASK
                                                      ↓        ●━━━┷━━━○━━ ←
                                                                              청산
                              gross_long = (ASK_exit − BID_entry) / BID_entry
                                       ≈ mid_gross + spread_entry/2 + spread_exit/2
                                       ≈ mid_gross + 평균 spread (≈ 9 bps)
```

### 각 Path 의 측정된 효과 (smoke 결과)

```
Hypothesis quality
   v5 (잔존):   ✗✗✗    (0/3 template 완전)
   v6 (smoke): ✓✓✓✓   (4/4)

Maker 효과 (top 5 v5 specs maker re-measure)
   mid_gross ━━━━━ +9.22 bps spread ━━━━━━ maker_gross
   4.74      ─────────────────────────────→  14.01  (best)
   3.85                                       13.73
   ... 평균 +9.22 bps 일관 보강

Fee floor 변화:
   mid-only :  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 23 bps (deploy 임계)
   maker mode:  ━━━━━━━━━━━━━━━━ 14 bps (= 23 − 9 spread)
                                  ↑ v5 best 4.74 와 9.3 bps gap 잔존
```

## 진행 / 결과 (Progress / Results)

- Path A: quick_ref.md (~80줄) + prior_iterations 트림 + AGENTS.md §3 재구조화
- Path B: schema 확장 + backtest_runner maker_optimistic + CLI --execution-mode
- Path C: 15 cell 표 (3.78M tick), 2 fee-prohibitive / 4 high-magnitude 셀 라벨
- Path D: 9 T × 5 primitives 표, drift 보정 컬럼 추가
- Smoke A+C+D: hypothesis 4/4, multi-family 다양성 회복
- Smoke B: maker 효과 +9.22 bps, 측정 spread 9.21 bps

## 발견 / 의미 (Findings / Implications)

- **측정 spread 9.21 bps** = 사전 가정 5 bps 의 1.8x. Tick discreteness 가 spread 하한.
- Path B 단독 = fee floor 23 → 14 bps 임계. v5 best (mid 4.74) 와 9.3 bps gap 잔존.
- Path D 의 alpha vs drift 분석에서 \"obi_1 @ T=500: alpha +24 bps\" 발견 — IS 의 drift 빼면 진짜 신호 있음.
- 4 lever 의 결합 효과는 v6 결과 봐야 정량 가능.

## 다음 단계 (Next)

1. v6 fresh launch (8 dates × 3 syms × 25 iter × 4 candidates)
2. v6 진행 모니터링
3. v6 종료 후 자동 분석 (analysis/v6_results.py)
