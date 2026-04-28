---
schema_version: 1
type: plan
created: 2026-04-27
updated: 2026-04-27
tags: [roadmap, post-v5, master-plan]
refs:
  code: []
  papers: []
  concepts: []
  experiments:
    - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-roadmap-post-v5
status: proposed
trigger: post-v5-completion
priority: master
---

# Post-v5 Roadmap (5 path, ordered)

## 배경

v5 fresh run (regime-state + Fix #1 net-PnL) 이 진행 중. 초기 결과 (iter_000~009) 는 v3 대비 매우 약함 — best meaningful gross 3.44 bps (v3: 13.32). KRX 23 bps fee 통과 0/28+.

원인 진단 (가설):
1. **Cold-start**: regime-state paradigm 신규, LLM 미적응
2. **AGENTS.md 비대**: prompt attention 분산 (~600 lines)
3. **Calibration 부재**: LLM 의 magnitude prior 가 unanchored (실측 대비 ±100% off)
4. **Spread capture 미고려**: chain 1 이 mid-to-mid 만 → maker edge 5~7 bps 미사용
5. **Static cheat sheet 의 한계**: LLM 이 dynamic query 불가능

## 5 paths

| Path | 요지 | 노력 | 의존성 | Priority |
|---|---|---|---|---|
| **A** | LLM calibration: quick_ref + AGENTS.md trim | ~3.5h | v5 결과 | medium |
| **B** | Maker spread capture in chain 1 backtest | ~10h | v5 결과 | high |
| **C** | Empirical baselines (bias-mitigated 15 cells) | ~7h | v5 결과 | medium |
| **D** | T-scaling table (9 holding periods) | ~5h | C | medium |
| **E** | Agentic data-analysis tools (sub-agent + tool-use) | ~30h | A, C, D | high |

각 path 의 상세 spec:
- [path-a-llm-calibration](path-a-llm-calibration.md)
- [path-b-maker-spread-capture](path-b-maker-spread-capture.md)
- [path-c-empirical-baselines](path-c-empirical-baselines.md)
- [path-d-t-scaling](path-d-t-scaling.md)
- [path-e-agentic-data-tools](path-e-agentic-data-tools.md)

## 권장 실행 순서

```
Step 1: v5 완료 → 결과 분석                                    [~5h, automatic]
   ↓
Step 2: Path A — calibration (cold-start 완화)                 [~3.5h]
   ↓
Step 3: Path C — empirical_baselines.json 산출                 [~7h]
   ↓ (병렬 가능)
Step 4: Path D — t_scaling.json 산출                           [~5h]
   ↓
Step 5: Smoke test (A+C+D 결합) — 1 iter, gross 변화 측정      [~30 min]
   │
   ├─ gross 향상 > 50% 면 Path B 로 진행
   └─ 향상 < 20% 면 Path E (heavy intervention) 우선

Step 6a: Path B — maker spread capture                         [~10h]
   ↓
Step 6b: Full run (A+B+C+D 적용, regime-state + maker)         [~5h]
   │
   ├─ net > 0 spec 발견 = 프로젝트 first deployable signal
   └─ net 0 미달 → Step 7

Step 7: Path E — agentic tool-use (heavy)                      [~30h, 1주]
   ↓
Step 8: Final full run (A+B+C+D+E)                             [~5h, 단 cost ↑]
```

총 estimated effort: **~75h work + ~10h compute** = ~2주 (full-time).

## 게이트 / 분기 결정

**Gate 1 (after Step 2/A)**: smoke test 의 hypothesis quality 향상 측정
- 향상 ≥ 30% → 계속 (C/D 로)
- 향상 < 10% → Path A 가 부족하다는 신호 → E 가 critical

**Gate 2 (after Step 5)**: A+C+D smoke 의 spec quality
- gross 5+ bps spec 1+ 발견 → Path B 로 (deployable 가능성)
- 모두 < 3 bps → Path E 직행 (cheat sheet 만으론 부족)

**Gate 3 (after Step 6b)**: full run 결과
- net > 0 spec 1+ → 프로젝트 first milestone, paper writeup 준비
- net > -10 bps → near-deployable, Path E 추가
- net < -15 bps → fundamental rethink (KRX cash 가 tick 단위에서 가능한지 자체 의심)

## Paper-target 정렬

각 path 의 paper-relevance:

- **A**: 직접 paper 기여 적음 (engineering)
- **B**: §Method §Discussion — "LLM agent 가 chain 1 단계에서 execution 일부를 미리 보는 것의 가치"
- **C**: §Method — "bias-mitigated systematic partition for LLM grounding"
- **D**: §Discussion — "holding-period dimension as fee-binding lever"
- **E**: ⭐ **§Method 핵심** — "agentic data tool-use for hypothesis grounding". 차별점: alphaagent-2025 / quantagent-2025 는 single-shot LLM call 만 사용

E 가 paper 기여도 가장 큼. 단, 구현 비용 가장 큼.

## 분기 위험

- **2주짜리 effort** — v5 결과 보기 전 commit 방지. v5 완료 후 결과 분석 → 5 path 중 어떤 게 가장 critical 인지 evidence-based 선택.
- **Path E 의 cost regression** — 5x ($1 → $5/run). 학습 효과 검증 후에만.
- **Cheat sheet contamination** — A/C/D 가 LLM 의 hypothesis space 에 영향 → v3/v4/v5 와의 ablation comparison 가 깨짐. → 새 baseline 으로 v6 부터 시작.

## 미정 사항

- 단일 path 가 net > 0 를 만들면 나머지 path skip 할지 (vs 모두 적용해 robust 검증)
- Path E 의 sub-agent 가 미래 Path F (chain 2 미리보기) 로 확장 가능한지
- Paper deadline (NeurIPS 2026 May submission) 와 path 적용 순서의 정합성
