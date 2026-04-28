---
date: 2026-04-28 14:30
tone: incident
title: v6 가 iter_007 에서 schema 위반으로 중단 후 재시작
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

v6 fresh run (PID 3166341, 12:30 KST 시작) 이 약 2시간 39분 후 (~15:09) iter_007 진입 직후 **Pydantic validation error** 로 중단. 프로세스는 zombie 상태. 사용자가 \"실험 어디까지 수행됬는 지 점검\" 요청해 진단 시작.

직전 progress (12:30) 의 \"시나리오 D\" 에 명시한 \"진행 중 crash 가능성 (확률 10%)\" 의 실제 발생.

## 가설 (Hypothesis)

Crash 의 원인 가설:
\"Path D 로 LLM 에게 노출된 t_scaling 표가 보유 시간 (T) 을 2000~10000 까지 보여주므로, LLM 이 그 영역을 시도해 prediction_horizon_ticks=2000 같은 큰 값을 생성. 그런데 schema (`prediction_horizon_ticks: ge=1, le=1000`) 가 ≤ 1000 제약이라 reject. 즉 Path D 의 의도된 행동이 schema 의 옛 제약과 충돌\".

가설이 맞다면: error 메시지에 \"prediction_horizon_ticks ≤ 1000\" 위반 명시 + 거부된 신호의 hypothesis 에 \"긴 보유 시간\" 명시.

가설이 틀리면 (다른 원인): error 메시지가 다른 필드 위반 / 데이터 로딩 / 메모리 등. 더 깊은 진단 필요.

## 변인 통제 및 설계 (Experimental Design)

진단 작업이라 정식 \"실험\" 보다는 디버깅이지만 통제 정신은 유지:

- **확인 변수**: log 의 정확한 error stack trace, 거부된 신호의 hypothesis 텍스트, schema 의 현재 제약
- **수정 변수**: schema 의 prediction_horizon_ticks 제약 (le=1000 → le=20000)
- **통제 변수**: backtest_runner 자체 (regime-state 에서 prediction_horizon_ticks 는 deprecated, 백테스트가 무시)
- **검증**: schema 수정 후 iter_007 부터 resume — start-iter 옵션 활용해 iter_000~006 결과 보존

## 철학 / 선택의 근거 (Why this approach)

\"전체 v6 재시작\" vs \"iter_007 부터 resume\" 중 후자 선택. 이유:
- iter_000~006 의 23 specs 결과가 보존되어 있고 의미 있음 (특히 iter_004 의 maker 14.12)
- 통제 변수 \"같은 setup\" 깨짐 risk 미미 — orchestrator 의 start-iter 가 idempotent
- 시간 자원 절약 (이미 2.5h 진행됨)

\"Schema 제약 le=1000 → le=20000\" 의 선택:
- 원래 fixed-H 패러다임에서 H 가 1000 이상이면 한 세션 (약 23000 tick) 중 작은 부분 — 의미 있는 제약
- regime-state 패러다임으로 전환 후 prediction_horizon_ticks 는 \"deprecated\" — 백테스트가 사용 안 함 (mean_dur 가 자체 측정됨)
- 그러나 schema 자체에 옛 제약이 잔존 → 사용자 (LLM) 의 의도 (긴 horizon 시도) 와 충돌
- 완전 제거 (le 없음) 도 가능하지만 sanity 차원에서 le=20000 (한 세션 분량 정도) 으로 약간만 완화

이 선택의 트레이드오프:
- LLM 이 정말 무의미하게 큰 값 (예: 100000) 을 생성할 가능성 — 그래도 backtest 가 무시하니 무관
- 옛 fixed-H mode (legacy) 와의 호환 — fixed-H 에서는 H 가 큰 값이면 좋지 않으나 현재 fixed-H 사용 안 함

## 세션 컨텍스트 (Session Context)

### 이미 수행하고 분석한 것 (Done & Analyzed)

본 progress 직전까지의 작업 (2026-04-28 12:30 ~ 14:30):

- v6 launch (PID 3166341, 12:30) 후 iter_000 ~ iter_006 정상 진행
- 23 specs backtest 완료
- 의미 있는 신호 발견:
  - iter004_durable_book_consensus: maker 14.12 / mid 4.46 / spread 9.64 / mean_dur 519 ticks (52초)
  - 이는 v5 best (mean_dur 117) 의 4.4x — Path D 효과 시작
- LabHub Flow / Wiki 전면 평이화 작업 (사용자 요청: 누구나 이해 가능하도록)
- Wiki entity 40 개 모두 rewrite 또는 신규 작성
- Flow event 14 개 모두 평이화 (overwrite=true)
- Path B 효과 분석 스크립트 (analysis/maker_effect_analysis.py) 작성 + 실행
- 분석 결과: maker = mid + spread 수식 일치 (1.000), v6 평균 mean_dur 가 v5 대비 5x

직전 세션 (2026-04-27) 의 요점은 progress_20260428_1200 참조.

### 지금 수행·분석 중인 것 (In Progress)

- v6 resume (PID 3237121, 14:30 KST 재시작)
  - start-iter 7 — iter_000~006 보존
  - 같은 CLI 인자 (--execution-mode maker_optimistic, --fee-bps-rt 23.0)
  - log: /tmp/chain1_logs/fresh_run_v6_resume.log
  - 첫 줄: \"start_iter=7 max_iter=25\"
- Schema 변경 사항: prediction_horizon_ticks ≤ 20000 (regime-state 에서 무시되는 필드라 backtest 영향 없음)
- AGENTS.md 의 안내 동기화 (\"≤ 20000\" 으로 텍스트 갱신)

### 수행·분석할 예정인 것 — 추측 / 가능성 (Planned, speculative)

v6 resume ~3.5h 후 종료 (예상 18:00 KST). 시나리오 분기 (직전 progress 와 동일하나 약간 갱신):

- **시나리오 A — net > 0 신호 ≥ 1 발견 (확률 30%)**: 변경 없음 — paper §Results 시작.
- **시나리오 B — margin (확률 35%)**: 약간 상향. iter_007 이후 Path D 효과 더 강하게 나올 가능성 (schema 풀린 후 LLM 이 진짜 긴 horizon 시도). Path E 시작.
- **시나리오 C — net ≤ -10 (확률 25%)**: 약간 하향.
- **시나리오 D — 또 다른 crash (확률 10%)**: 다른 schema 제약 / 데이터 로딩 등의 원인 가능.

또한 본 progress 작성 후 사용자가 새 progress.md template (계기/가설/변인/철학/세션컨텍스트) 도입 요청 — 이 template 으로 v6 종료 후 \"v6 results\" progress 작성.

## 다이어그램 (Diagrams)

### Crash mechanism

```
   Path D (t_scaling 표) 가 LLM 에게 노출:
   ┌──────────────────────────────────────────┐
   │  T = 1, 10, 50, 100, 500, 1000, 2000,    │
   │      5000, 10000  ← 큰 보유 시간 영역    │
   │  alpha (drift 보정 후) = +24, +44, ...   │
   └──────────────────────────────────────────┘
                        ↓
   LLM (iter_007) 이 \"axis A: 긴 보유 시도\":
   spec.prediction_horizon_ticks = 2000
                        ↓
   schemas.py:
   prediction_horizon_ticks: int = Field(1, ge=1, le=1000)
                                                   ↑
                                            옛 fixed-H 시절 제약
                                            (regime-state 에서는 deprecated)
                        ↓
   Pydantic ValidationError:
   \"Input should be less than or equal to 1000, input_value=2000\"
                        ↓
   v6 PID 3166341  →  zombie
```

### 수정 + Resume 의 흐름

```
   schemas.py 수정: le=1000 → le=20000
   AGENTS.md 동기화: \"[1, 1000]\" → \"[1, 20000]\"
                        ↓
   iterations/iter_007/ 의 incomplete 결과 정리
                        ↓
   v6 resume (PID 3237121, --start-iter 7)
                        ↓
   ┌─────────────────────────────────────────┐
   │ iter_000 ~ 006: 23 specs 결과 보존  ✓  │
   │ iter_007 ~ 024: 18 iter 신규 진행 중   │
   │ 종료 예상: ~18:00 KST                   │
   └─────────────────────────────────────────┘
```

### iter_004 의 Path D 효과 — \"긴 보유\" 신호의 등장

```
   v5 의 best 신호 (rolling_mean(obi_1, 50)):
       mean_dur = 117 ticks (≈ 12초)
       ▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 117

   v6 의 iter_004 (rolling_mean(obi_1, 500) AND rolling_mean(obi_ex_bbo, 500)):
       mean_dur = 519 ticks (≈ 52초)  ← 4.4x v5
       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 519

   v6 의 iter_007 (시도, 거부됨):
       의도된 prediction_horizon_ticks = 2000  ← schema 막음
       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ schema cap

   → 패러다임 전환 후 schema cleanup 부재의 cost
```

## 진행 / 결과 (Progress / Results)

- Crash 진단 — error message: \"prediction_horizon_ticks Input should be less than or equal to 1000, input_value=2000\"
- 거부된 신호: iter007 의 \"smoothed_trade_flow_reversal\" — \"axis A stickiness via rolling_mean ... 2-sigma trade flow burst\" hypothesis
- 가설 검증 ✓ — Path D 가 LLM 에게 긴 T 노출 → LLM 이 시도 → 옛 schema 제약과 충돌
- Schema 수정: schemas.py 의 `prediction_horizon_ticks` ge=1 le=1000 → ge=1 le=20000
- AGENTS.md 동기화: \"[1, 1000]\" → \"[1, 20000]\"
- iter_007 폴더 정리 (incomplete 결과 삭제)
- v6 resume — PID 3237121, start-iter 7
- iter_007 정상 진입 확인

## 발견 / 의미 (Findings / Implications)

- **Path D 의 효과는 schema 수정 전에도 작동 시작** — iter_004 의 mean_dur 519 ticks 가 Path D 의 표 효과의 직접 증거
- Schema 의 \"deprecated 필드\" 가 LLM 의 새 행동을 막을 수 있음 — 패러다임 전환 시 schema cleanup 필요
- v5 → v6 의 첫 비교 가능 데이터 (23 specs):
  - 평균 mean_dur 195 ticks (v5: 39) — **5x 증가**
  - 최대 mean_dur 1042 ticks (v5: 286) — 3.6x 증가
  - mean_dur > 200 신호 5개 (v5: 1) — 5x 증가
  - 그러나 best maker_gross 14.12 (v5 maker re-measure best 14.01) — 거의 동일
  - 즉 \"긴 horizon 시도는 했으나 magnitude 천장은 아직 비슷\"
- Schema cleanup 의 중요성: 패러다임 전환 시 \"옛 제약\" 이 \"새 행동\" 막을 위험

## 다음 단계 (Next)

1. v6 resume 진행 모니터링 (PID 3237121, ~3.5h)
2. v6 종료 후 새 template 으로 \"v6 results\" progress 작성
3. v6 결과 분석 (analysis/v6_results.py)
4. 결과별 분기 (시나리오 A/B/C/D)
