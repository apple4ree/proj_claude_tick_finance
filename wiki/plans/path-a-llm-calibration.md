---
schema_version: 1
type: plan
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, signal-generator, llm-calibration, post-v5]
refs:
  code:
    - {path: ".claude/agents/chain1/signal-generator/AGENTS.md", confidence: verified}
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/regime_state_paradigm.md", confidence: verified}
  papers: []
  concepts:
    - duty-cycle-target
    - regime-state-paradigm
  experiments:
    - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-A-llm-calibration
status: proposed
trigger: post-v5-completion
priority: medium
---

# Path A — LLM Calibration 강화 (quick_ref + AGENTS.md trim)

## 문제

v5 fresh run 의 초기 결과 (iter_000~009): 28+ specs 중 fee 통과 0/28. Max meaningful gross ≈ 3.44 bps (fee 23 bps 대비 22% 수준). v3 (max 13.32 bps) 대비 **현저히 낮음**.

진단 (가설):

1. **Cold-start**: regime-state paradigm 신규 도입. LLM 의 historical context (chain 1 = fixed-H tick-trigger) 와 새 spec semantic 간 mismatch.
2. **AGENTS.md 비대화**: 현재 signal-generator AGENTS.md ~600 lines. Required reading + anti-patterns + hypothesis template + decision tree 가 한 prompt 안에 들어가서 attention 분산.
3. **Cheat sheet 분산**: regime_state_paradigm.md (139 lines) + 기존 microstructure_advanced.md + block_f_cheat_sheet 등 — LLM 이 어떤 ref 부터 읽을지 불명확.

## 제안 design

**A.1 Quick-ref card (NEW)** — `.claude/agents/chain1/signal-generator/references/quick_ref.md`, ≤ 80 lines:
- duty 0.05~0.80 / mean_dur 20~5000 / n_regimes 5~50/session 의 target range 한 줄
- "fee 23 bps 통과 = expectancy_bps > 23" 한 줄
- 핵심 anti-pattern 5개 bullet
- Top 3 prior winning spec 의 (formula, threshold, gross) 한 표
- end. 다른 ref 로 redirect 만 함.

**A.2 AGENTS.md trim** — 현재 600 lines → 250~300 lines 목표:
- Required reading: 3개 → 2개로 축소 (regime_state_paradigm.md + quick_ref.md)
- Hypothesis template: 현재 inline 5 항목 → quick_ref.md 로 이관, AGENTS.md 에는 "see quick_ref.md §2" link 만
- Decision tree: 현재 inline 10+ steps → 핵심 3 step 으로 줄이고 details 는 cheat sheet 로
- Anti-patterns: 7개 → 5개 (중복 제거)
- Examples: 3개 → 1개 핵심 example 만 inline, 나머지 prior_iterations_index.md 로

**A.3 Prior iterations index 정비** — `prior_iterations_index.md`:
- v3 / v4 / v5 archive 각 best 5 spec 의 metric (gross / n / duty / mean_dur)
- 각 spec 의 "왜 통과/실패했는가" 한 줄
- LLM 이 한눈에 reference 가능

**A.4 Calibration table 갱신** — `data/calibration/krx_v2_2026_03_3sym.json`:
- v5 결과를 ingestion → 각 primitive 별 measured |Δmid_per_regime| / mean_dur 통계 갱신
- LLM 이 hypothesis 작성 시 "이 primitive 는 regime 당 평균 X bps move" 를 직접 참조

## 구현 단계

```
A.1  quick_ref.md 신규 작성             (30 min)
A.2  AGENTS.md trim 1차 (line 600→400)  (1h)
A.3  prior_iterations_index.md 갱신     (30 min)
A.4  calibration table 갱신 script      (1h, 자동화 가능)
A.5  smoke test: 1 iter × 1 sym × 1 date (30 min)
A.6  full re-run? — Path B/C/D 와 통합 결정
─────
total ~3.5h work, no full re-run included
```

## 성공 기준

1. Smoke test 1 iter (4 candidates) 의 hypothesis 텍스트에 "duty / mean_dur / expectancy_bps" 키워드가 4/4 등장 (현재 v5 iter_000 표본: 2/4 등장).
2. AGENTS.md token count ≤ 250 (현재 ~600).
3. Best spec 의 gross 가 v5 baseline (3.44 bps) 보다 ≥ 1 bps 향상 — small smoke 라 noise 가능, 신호로만.

## 의존성 / ordering

- **선행**: v5 종료 → results aggregation → calibration table 재계산
- **무관**: Path B/C/D/E 와 독립 (병렬 가능)
- **후행**: Path C/D 가 만든 empirical baseline 을 quick_ref.md 에 inline 가능 → 그 시점에 A.1 1회 추가 갱신

## 위험 / blocker

1. **Cold-start 가 calibration 문제가 아닐 가능성**: A 작업 완료 후에도 gross 개선 0 이면 Path E (agentic data tool) 가 필요한 신호.
2. **AGENTS.md trim 이 정보 손실**: anti-pattern / decision tree 줄이다가 LLM 이 anti-pattern spec 다시 만들 위험. A.5 smoke test 로 검증.
3. **Calibration table contamination**: v5 결과로 갱신 시 v6+ 가 v5 spec 을 모방하는 selection bias — 그러나 이건 기존 calibration 설계와 동일.

## 예상 영향

- v6+ run 의 first-iter quality 향상 (cold-start 완화)
- LLM token cost 감소 (~30% prompt 길이 감소)
- 디버깅 / iteration 속도 향상 (작업자가 AGENTS.md 빠르게 scan)

## 미정 사항

- A.4 calibration script 의 data window 결정 — v5 만? v3+v4+v5 통합? (v5 만 권장 — paradigm 동일)
- A.2 trim 후 reviewer agent 가 따로 검증할지 (manual review 로 충분할 듯)
