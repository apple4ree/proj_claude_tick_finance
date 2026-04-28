---
schema_version: 1
type: decision
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code: []
  papers: []
  concepts:
  - capped-post-fee
  - net-pnl-objective
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
decision_id: DEC-2026-04-27-krx-only-deployment-scope
status: accepted
supersedes:
- project_crypto_pivot
superseded_by: []
scope:
- deployment
- framing
- paper-target
---

# krx-only-deployment-scope

## 문제
v3 fresh run 결과가 0/80 fee 통과로 나온 후, 우리 framework 이 'crypto maker (4 bps RT) 시나리오에서는 66/80 흑자' 같은 framing 으로 결과를 낙관적으로 해석하고 있었음. 그러나 실제 deployment 의도가 KRX cash equity 인지 crypto 인지 명시되지 않아 분석 방향 혼란. 또한 chain 2 의 spread capture 가능성을 가정한 '낙관적 lower bound' 해석이 KRX cash 의 mechanical 한 fee 구조와 맞지 않음을 발견.

## 검토한 옵션
Option A: Crypto pivot 정당화 — 같은 13 bps 신호가 4 bps fee 시장에서 deployable, framework 자체는 valid. Option B: KRX cash 한정 — 23 bps fee floor (3 bps maker fee + 20 bps sell tax) 하에서 deploy 가능 신호 발견이 유일 목표. Option C: Multi-market support — KRX + crypto 양쪽 모두 deployable 추구.

## 선택한 접근
Option B 채택 — KRX cash equity 한정. Crypto pivot decision 은 폐기 (memory 의 project_crypto_pivot.md 를 SUPERSEDED 마킹). 모든 후속 분석은 KRX 23 bps RT fee 를 hard constraint 로 둠. Spread capture 가능성 (~5 bps) + chain 1 raw edge (현재 13 bps max) = 18 bps 이지만 fee 23 bps 못 통과 — gap ~5 bps 가 실측 결과. memory 에 project_krx_only_scope.md 추가하여 정책 명시.

## 근거
사용자 명시 의사 (2026-04-27 세션) — '크립토에는 끌고 갈지 않을 거니까 이 부분은 앞으로 고려하지 말아줘, 일단 KRX에서 수익을 내야하는 게 중요한 거니까'. Mechanical economics 도 본 결정을 뒷받침: KRX cash 의 sell tax 20 bps 는 정부세이므로 회피 불가, maker rebate 도 retail 에 일반적으로 미적용. 즉 fee 23 bps 는 floor 이지 ceiling 의 기댓값이 아님 — 어떤 sophisticated execution 으로도 못 깸. 판단 근거 (P8): KRX HFT 가 historically derivatives (선물/옵션, fee floor 1-5 bps) 위주인 사실은 문헌상으로 인정되며 cash equity HFT 의 어려움은 시장 구조의 수학적 결과.

## 트레이드오프
(1) Cross-market 일반화의 paper-grade evidence 잃음 — '같은 framework 가 crypto 에서도 작동' 류 framing 불가. (2) v3/v4 결과의 '낙관적 lower bound' framing 사용 금지 — 솔직하게 'KRX 한정 신호 information content 측정' 이라고 명시해야 함. (3) Deployment 가능성이 시장 구조상 mechanical 하게 제약 — 발견 가능한 gross edge 가 < 23 bps 면 KRX deploy 자체가 불가능.

## 영향 범위
프로젝트 전체의 deployment-target framing. 영향 받는 문서: memory/MEMORY.md (index), memory/project_crypto_pivot.md (SUPERSEDED 표시), 새 memory/project_krx_only_scope.md. 후속 분석/wiki entry 의 framing. 영향 없는 모듈: chain 1 코드 (그대로), data (KRX 데이터 그대로 사용), agent 정의 (chain 1 그대로).

## 재검토 조건
(1) v4/v5 에서 net_expectancy > 0 인 spec 발견 — 시나리오 unit economics 재검토. (2) Regime-state paradigm 측정에서 mean_regime_gross > 28 bps spec 발견 시 — chain 1 backtest 의 fee accounting 정의가 핵심 결함이었다는 결론으로 방향 전환. (3) 규제 환경 변화 — KRX sell tax 가 변경되면 (예: 인하) fee floor 재계산.
