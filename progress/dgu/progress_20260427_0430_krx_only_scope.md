---
date: 2026-04-27 04:30
tone: pivot
title: KRX-only scope, crypto pivot 폐기
---

## Context
v4 진행 중 chain 1 / chain 2 의 의도된 분리, raw edge 측정의 의미, KRX cash equity 의 fee economics 를 정밀 분해. v3 max gross 13 bps + chain 2 spread capture 5 bps = 18 bps 이지만 KRX 23 bps fee 통과 못함. Crypto maker 4 bps 시나리오에서는 deployable 하나, 사용자가 crypto 로 끌고 갈 의사 없음을 명시 — 본 프로젝트 deployment scope 가 KRX cash equity 한정으로 좁혀짐.

## Done
- chain 1 vs chain 2 의 design 분리 정밀 검토 — chain 2 는 설계됐으나 미구현
- KRX cash 의 unit economics 분해: 3 bps maker fee + 20 bps sell tax = 23 bps RT (sell tax 가 mechanical dominant constraint)
- Crypto maker 시나리오 (4 bps RT) 와의 비교 — 같은 13 bps gross 가 시장에 따라 deployable / not 으로 양분
- Memory 업데이트: project_krx_only_scope.md 추가, project_crypto_pivot.md SUPERSEDED 표시

## Numbers
- KRX RT fee floor: 23 bps (3 fee + 20 tax)
- v3 max gross: 13.32 bps
- chain 2 spread capture est: 5 bps (양쪽 maker 가정)
- Net (현 시점 추정): -5 bps
- Gap to break: ~5 bps gross edge 추가 필요

## Decisions & Rationale
- Crypto deploy 옵션 폐기 — 사용자 의사
- "낙관적 측정" framing 부정확함을 인정 — KRX 한정으로 13 bps 천장은 deployment 불가능 의미
- Paper-target 측면(LLM agent research framework)은 유효하나 KRX deploy claim 은 보류

## Next
- 모든 후속 분석은 KRX 23 bps fee 를 hard constraint 로 둠
- v4 결과의 framing 도 KRX 한정으로 재해석 필요
