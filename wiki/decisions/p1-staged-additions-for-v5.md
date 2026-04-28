---
schema_version: 1
type: decision
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code:
  - path: chain1/primitives.py
    symbol: kyle_lambda_proxy
    confidence: inferred
  - path: chain1/primitives.py
    symbol: RollingAutocorrLag1
    confidence: inferred
  - path: chain1/primitives.py
    symbol: PRIMITIVE_WHITELIST
    confidence: verified
  - path: chain1/code_generator.py
    symbol: STATEFUL_HELPERS
    confidence: inferred
  papers: []
  concepts:
  - magnitude-axes-framework
  - net-pnl-objective
  experiments:
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
decision_id: DEC-2026-04-27-p1-staged-additions-for-v5
status: accepted
supersedes: []
superseded_by: []
scope:
- chain1.primitives
- _shared.references.papers
- wiki.concepts
---

# p1-staged-additions-for-v5

## 문제
v4 fresh run 진행 중 (5+ 시간 소요 중) — 그 사이 시간을 활용할 작업 필요. 동시에 v5 launch 가속을 위한 P1 (Block G primitive + 추가 paper) 의 사전 작업 가능. 그러나 LLM 가 cheat sheet / paper / WHITELIST 갱신을 보면 v4 ablation 의 clean partition 이 깨짐. v4 종료 대기와 P1 사전 준비 사이의 trade-off.

## 검토한 옵션
Option A: P1 primitive 코드만 추가 (whitelist 미등록), paper / cheat sheet 보류. v4 영향 0. Option B: P1 전체 (primitive + paper + cheat sheet) 즉시 추가. v4 iter_005+ 가 새 ref 봄, ablation 오염. Option C: v4 종료까지 대기, 이후 한 번에. 시간 효율 낮음.

## 선택한 접근
Option A 채택 — '코드 dormant 추가' 패턴. 작업 내용: (1) Block G primitive 코드 추가: kyle_lambda_proxy(snap, prev) + RollingAutocorrLag1(window) helper class. PRIMITIVE_WHITELIST / STATEFUL_HELPERS 등록 보류 (v5 launch 시 추가). (2) P1 paper summary 3개 작성 (이미 _shared/references/papers/ 에 직접 — cheat sheet 와 마찬가지로 v4 후반 부분 contamination, 그러나 paper 는 referenced 되지 않으면 LLM 이 안 봄). (3) Wiki concept page 5개 작성: magnitude-axes-framework, capped-post-fee, cite-but-fail, net-pnl-objective, reward-target-mismatch.

## 근거
(i) Block G primitive 코드 자체가 v4 LLM 에 영향 0 임 — LLM 은 모르는 primitive 안 씀. WHITELIST 만 미등록하면 evaluator 가 reject 함. 즉 코드만 두는 건 zero-overhead prep. (ii) P1 paper 는 _shared/references/papers/ 에 추가됐으나 signal-generator AGENTS.md 의 'required reading' 리스트에 없음 — LLM 이 명시 인용 시에만 영향. v4 후반 LLM 이 발견할 가능성은 낮음. (iii) Wiki concept page 는 chain 1 파이프라인이 안 보는 위치 (wiki/) — 영향 0. (iv) v5 launch 의 작업량을 5분 으로 단축 — 단순 WHITELIST + STATEFUL_HELPERS 등록 + cheat sheet 갱신.

## 트레이드오프
(1) P1 paper 가 _shared/references/papers/ 에 들어가서 LLM 이 직접 읽을 수도 있음 — 일종의 mild contamination. AGENTS.md 의 required reading 에 명시 안 했으니 미미하나 zero 보장은 어려움. (2) Block G code 가 unused 상태로 codebase 에 추가됨 — 미래에 wiki-sync stale link 발생 가능. (3) 문서 inconsistency 위험 — papers 는 추가됐는데 cheat sheet 와 cross-link 없음. v5 launch 시 동기화 필요.

## 영향 범위
chain1/primitives.py (kyle_lambda_proxy + RollingAutocorrLag1 추가, WHITELIST 미등록). _shared/references/papers/ (3개 신규 paper md). wiki/concepts/ (5개 신규 concept page). 영향 받지 않음: code_generator (STATEFUL_HELPERS 미등록), feedback_analyst, signal_generator, orchestrator. v4 ablation: 거의 zero, but not strictly zero (paper file 존재).

## 재검토 조건
(1) v4 후반 (iter 5–24) 에서 LLM 이 P1 paper 의 명시적 인용을 시작하면 — full WHITELIST 등록 시점 앞당김. (2) wiki-lint 에서 unused primitive flag 가 발생하면 — Block G 가 사용 가능한 상태로 promote. (3) v5 launch 시: WHITELIST 등록 + cheat sheet 갱신 + signal-generator AGENTS.md required reading 에 P1 paper 추가.
