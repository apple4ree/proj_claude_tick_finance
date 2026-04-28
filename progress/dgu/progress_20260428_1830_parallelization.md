---
date: 2026-04-28 18:30
tone: design
title: Pipeline 병렬화 구현 — iter 시간 35분 → 10분 예상
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

v6 fresh run 의 한 iter 가 약 35-38 분 소요 → 25 iter 한 run 에 14-15 시간. 사용자 질문 \"실험 한 번이 너무 오래 걸리는데 어디서 병목이 생기나\" 에서 시작. 분석 결과:

- **iter 의 50%** = 4 specs 의 backtest sequential (4 × 5분 = 20분, 380만 tick × 24 (sym, date) pairs)
- **iter 의 30%** = LLM stage 의 spec 별 sequential (eval/codegen/feedback × 4 specs)
- **iter 의 20%** = generator + improver (1번씩)

→ 4 specs 의 같은 stage 가 서로 독립인데도 sequential 인 게 비효율.

또한 v6 의 결과가 \"4-5 bps 천장\" 으로 saturating — 천장 깨려면 더 많은 ablation 시도 (Level 2/4, paradigm shift 등) 필요. 빠른 iteration 이 critical.

## 가설 (Hypothesis)

\"4 specs 의 같은 stage 를 동시 실행하면 (LLM 은 asyncio.gather, backtest 는 thread) iter 시간이 75% 감소 (35분 → 10분), 결과의 정량 값은 거의 변화 없음 (LLM temperature=0, deterministic backtest).\"

검증할 것:
- Smoke 1 iter 의 실제 시간 측정 (목표 ≤ 12분)
- Sequential 결과와 parallel 결과의 spec quality 비교 (deterministic 함을 검증)

가설이 틀리면: race condition / OOM / LLM rate limit / 결과 비결정성.

## 변인 통제 및 설계

- **독립 변수**: pipeline 실행 방식 (sequential vs parallel)
- **종속 변수**: iter 시간, 메모리 사용량, spec 결과의 numeric 값
- **통제 변수**: 모든 LLM stage 의 prompt / temperature, 같은 데이터, 같은 신호 함수
- **사전 위험 점검**:
  - 시스템 메모리: 503GB (available 438GB). 4-spec 동시 backtest 의 메모리 4x = ~6GB → 위험 0.
  - LLM rate limit: paid tier 100K tokens/min, 우리 4 동시 ≈ 40K/min → margin 충분.
  - 결과 deterministic: temperature=0 + backtest deterministic.

## 철학 / 선택의 근거

\"기존 코드 수정\" 보다 \"새 함수 추가 + opt-in CLI flag\" 선택. 이유:
- v6 가 진행 중 (PID 3237121, iter_016+) — 코드 수정 시 영향 위험.
- `--parallel` flag 가 없으면 기존 sequential 그대로 — backward compat.
- v6 vs v7 의 ablation 비교 가능 (같은 setup, 병렬화만 차이).

\"한 spec 안의 stage 는 sequential 유지\" — eval 결과가 codegen input. 이 의존성 깨면 안 됨.

\"4 specs 동시\" 만 — 더 큰 동시성 (예: 16 specs 같은 stage 동시) 은 LLM rate limit risk + improver 의존성 충돌.

\"asyncio + to_thread 결합\":
- LLM 은 IO-bound → asyncio.acompletion (network 대기 동안 다른 spec 진행)
- Backtest 는 CPU-bound numpy → asyncio.to_thread (별도 thread, GIL 자주 release 가능)
- ProcessPoolExecutor 까지 안 가는 이유: numpy/pandas operation 이 GIL release 자주 → thread 로 충분, fork overhead 회피.

## 다이어그램 (Diagrams)

### Sequential vs Parallel 의 흐름

```
Sequential (현재):
  ① gen (1 LLM call, 4 specs)         [2분]
  for spec in specs:                   [4 × 8분 = 32분]
    ② eval        [LLM, 1분]
    ②.5 codegen   [LLM, 1분]
    ②.75 fidelity [det, <1초]
    ③ backtest    [det, 5분]
    ④ feedback    [LLM, 1-2분]
  ⑤ improve (1 LLM call)               [1분]
                                        ─────
                                        총 ~35분

Parallel:
  ① gen                                 [2분]
  asyncio.gather(spec1, spec2, spec3, spec4) {
    각 spec 의 stage 들이 자기 안에서 sequential
    그러나 4 specs 가 동시 진행
                                        [max(4 specs) ≈ 8분]
  }
  ⑤ improve                             [1분]
                                        ─────
                                        총 ~11분 (예상)
```

### 한 spec 안의 의존성 (sequential 필수)

```
spec 1:  eval ─→ codegen ─→ fidelity ─→ backtest ─→ feedback
                  ↑ eval 결과가 input

spec 2:  eval ─→ codegen ─→ fidelity ─→ backtest ─→ feedback   (spec 1 과 동시)
spec 3:  eval ─→ codegen ─→ fidelity ─→ backtest ─→ feedback   (spec 1 과 동시)
spec 4:  eval ─→ codegen ─→ fidelity ─→ backtest ─→ feedback   (spec 1 과 동시)
```

### 시간 단축 추정

```
                  Sequential   Parallel
iter 1번          35-38분       ~10분         (75% 감소)
25-iter run       14-15시간      ~4시간        (75% 감소)

→ 하루 1 run (현재) → 하루 5-6 run (병렬화)
→ ablation 다수 시도 가능 (Level 2/4, paradigm 변형, OOS 검증, ...)
```

## 세션 컨텍스트

### 이미 수행하고 분석한 것 (Done & Analyzed)

이 세션 안에서 직전까지의 흐름:
- v6 fresh run 진행 중 (4-5 bps 천장 saturation 신호)
- v3 의 13.32 가 fixed-H over-counting 인공물 진단 (별도 progress)
- 사용자 질문 \"왜 실험이 오래 걸리나\" → log timing 분석 → backtest + LLM sequential 가 dominant
- 사용자 질문 \"병렬화 부정적 영향?\" → 검토: 메모리 OOM (위험 0, 503GB), determinism 미세 차이 (mitigation 가능)
- Phase 1 + Phase 2 동시 진행 결정

### 지금 수행·분석 중인 것 (In Progress)

- v6 fresh run (PID 3237121, iter_016+ 진행 중)
- 본 progress 의 wiki/flow 기록

### 수행·분석할 예정인 것 — 추측

- v6 종료 (~21:00 KST 예상) → 최종 결과 분석
- v6 결과별 분기:
  - net > 0: paper writeup, 병렬화 불긴급
  - margin: Path E (Task #107) 또는 Level 2+4 (Task #108) → 병렬화 critical
  - 천장: Level 2+4 + 추가 ablation → 병렬화 매우 critical
- v7 launch (병렬화 적용, 같은 setup) → ~4 시간 후 결과
- v7 vs v6 비교: 병렬화의 결과 영향 측정

## 진행 / 결과 (Progress / Results)

### Phase 1 + Phase 2 동시 구현 완료 (~3 시간 작업)

변경 파일:
- `chain1/llm_client.py` — `call_agent_async()` 신규 + helper 분리
- `chain1/agents/signal_evaluator.py` — `evaluate_signal_async()` 신규
- `chain1/agents/feedback_analyst.py` — `analyze_feedback_async()` 신규
- `chain1/orchestrator.py` — `_run_one_spec_async()`, `run_iteration_parallel()`, `_PARALLEL` global, `--parallel` CLI flag

검증:
- 모든 import 정상 ✓
- async 함수가 coroutine 으로 인식 ✓
- v6 (sequential) 진행 중 영향 없음 (기존 `run_iteration` 그대로 유지) ✓

### 디자인 결정 요약

1. 한 spec 의 stage 는 sequential (의존성 보존)
2. 4 specs 동시 (asyncio.gather)
3. LLM = acompletion, sync 함수 = to_thread
4. Improver / Generator 는 sync 유지 (1 LLM call 씩)
5. 기존 sequential 함수 그대로 유지, opt-in CLI flag

## 발견 / 의미 (Findings / Implications)

- 작업 시간 ~3 시간 (예상 3.5h 보다 약간 빠름)
- 코드 추가 ~250 lines, 기존 코드 변경 없음 (호환성 보장)
- v6 진행 중에도 안전하게 작업 가능 — 새 함수 추가만
- 시스템 메모리 503GB 라 OOM 위험 0 (Phase 2 backtest 병렬도 안전)

## 다음 단계 (Next)

1. v6 종료 대기 (~21:00 KST)
2. v7 launch (`--parallel`) — 같은 setup, 병렬화만 차이
3. Smoke 측정: 1 iter 시간 비교 (sequential ~35min vs parallel ~10min 검증)
4. v7 종료 후 v6 vs v7 결과 비교 (결과 deterministic 가설 검증)
5. 결과별: 천장 깨면 Level 2+4 (Task #108) 즉시 적용
