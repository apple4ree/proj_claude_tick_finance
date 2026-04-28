---
schema_version: 1
type: experiment
created: '2026-04-28'
updated: '2026-04-28'
tags: [chain1, regime-state, maker, calibration, post-v5, ablation]
refs:
  code:
    - {path: "chain1/backtest_runner.py", symbol: "backtest_symbol_date_regime", confidence: verified}
    - {path: "chain1/orchestrator.py", symbol: "stage_backtest", confidence: verified}
    - {path: ".claude/agents/chain1/signal-generator/references/quick_ref.md", confidence: verified}
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/empirical_baselines.md", confidence: verified}
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/t_scaling.md", confidence: verified}
    - {path: "analysis/empirical_baselines.py", confidence: verified}
    - {path: "analysis/t_scaling.py", confidence: verified}
    - {path: "analysis/maker_smoke.py", confidence: verified}
  papers:
    - stoikov-2018-microprice
    - cont-kukanov-stoikov-2014
  concepts:
    - regime-state-paradigm
    - magnitude-axes-framework
    - fee-binding-constraint
    - duty-cycle-target
    - maker-spread-capture
    - post-v5-paths-applied
  experiments:
    - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
git_ref: feat/agent-handoff-schema
experiment_id: exp-2026-04-28-fresh-v6-paths-A-B-C-D
status: in_progress
launched_at: '2026-04-28T12:30:00Z'
target_completion_estimated: '2026-04-28T17:30:00Z'
runner_pid: 3166341
seed: null
---

# Fresh v6 — Paths A+B+C+D 통합 (regime-state + maker_optimistic + LLM calibration + empirical anchoring)

## 가설 (hypothesis)

**중심 가설**: v5 (regime-state + Fix #1 net-PnL) 의 best-of-run 4.74 bps gross 천장은 **LLM hypothesis-magnitude 추측이 unanchored** + **mid-to-mid execution 의 spread 미회수** + **prior_iterations bloat 의 attention 분산** 의 결합 효과. 이 4 lever 를 동시에 보정하면 **maker-realized gross 가 14 bps 임계** (= mid 14 + spread 9 가 fee 23 통과) 에 도달하는 spec 이 발견될 수 있다.

**Sub-hypotheses (개별 path 별)**:

- **A — calibration**: quick_ref.md (post-v5 ceiling, target ranges, hypothesis template) + AGENTS.md REQUIRED 5개 정비 → hypothesis quality 가 v5 0/3 (template 완전성) 에서 ≥ 75% 로 회복.
- **B — maker spread capture**: backtest 가 mid-to-mid 가 아닌 (entry at touch BID, exit at touch ASK) 로 회계 → 실측 KRX 005930/000660/005380 spread ~9 bps 가 gross 에 직접 더해짐. 동일 spec 의 maker gross = mid + 9 bps 검증 (5/5, 사전 smoke 결과).
- **C — empirical baselines**: 15-cell partition (5 time × 3 vol) 의 magnitude / WR / lag-autocorr 표 + bias-mitigation framing → LLM 의 cell-level magnitude prior 가 anchored (v5: ±100% off, target: ±30% within).
- **D — T-scaling**: 9 holding period × 5 primitive 의 magnitude / WR / drift-adjusted alpha 표 → LLM 이 mean_dur design 시 √T 와 signal-decay trade-off 직접 reference.

## 셋업 (setup)

| 항목 | 값 |
|---|---|
| 모드 | regime-state (state machine: True 동안 hold, False 시 exit) |
| Execution mode | **maker_optimistic** (long: enter BID, exit ASK; short reversed) |
| Fee | 23.0 bps RT (KRX cash, sell tax 20 + maker 1.5×2) |
| Calibration | `data/calibration/krx_v2_2026_03_3sym.json` (per-symbol z-score) |
| Symbols | 005930, 000660, 005380 |
| Dates | 20260316~20260325 (8 KRX 거래일) |
| Iterations | 25 |
| Candidates / iter | 4 |
| 총 specs | ≤ 100 |
| LLM | sonnet (default per chain1 config) |

## 실험 디자인

```
Cold start (no prior iterations)
   ↓
Iter 0: signal-generator 가 4 candidates 생성
        → references auto-loaded:
            quick_ref.md (post-v5 ceiling)
            empirical_baselines.md (15 cells)
            t_scaling.md (9 T values × 5 primitives)
            regime_state_paradigm.md
            direction_semantics.md
   ↓
Per spec: evaluate → codegen → fidelity → backtest (regime-state, maker_optimistic)
   ↓
Aggregate: aggregate_expectancy_bps = maker gross (Path B primary)
           aggregate_expectancy_maker_bps = same (back-compat)
           aggregate_avg_spread_bps = measured (~9 bps for IS)
   ↓
Feedback: net_expectancy = maker_gross − 23 ; rank by net
   ↓
Improver: top-3 의 mutation
   ↓
prior_iterations_auto_log.md (NOT in required reading) 에 압축 로그
   ↓
Iter 1, 2, ..., 24
```

## 측정할 metric (success criteria)

1. **Hypothesis template 완전성** ≥ 75% (v5: 0/3 of carry-over). Smoke 1-iter pre-launch 에서 4/4 검증됨.
2. **Best maker gross**: ≥ 14 bps (= fee 23 - measured spread 9). v5 best maker = 14.01 (단 하나).
3. **Net deployable spec**: ≥ 1 spec 의 (aggregate_expectancy_bps − 23) > 0. **본 실험의 핵심 질문**.
4. **Diversity (anti-saturation)**: top 10 spec 의 primitive_used 가 OBI/OFI/microprice/trade_imb 의 ≥ 3 family 분산. v5 는 OBI 단일 family 가 dominant.
5. **Anti-pattern occurrence**: mean_dur < 5 (flickering) spec 비율 ≤ 10% (v5: 25-40%).
6. **Saturation iter**: best-of-run iter 가 ≥ iter_15 (v5: iter_13 saturated, 12 iter 추가 random walk).

## 비교 prior

| Run | mid_gross best | n | duty | mean_dur | net (mid - 23) |
|---|---:|---:|---:|---:|---:|
| v3 | 13.32 | (n=80) | — | (fixed-H) | -9.7 |
| v4 (Fix #1) | ~10 | (n=?) | — | (fixed-H) | -13 |
| v5 (regime-state) | 4.74 | 6444 | 0.20 | 117 | -18.3 |
| v5 (maker re-measure, sample 5 specs) | 14.01 | 6444 | 0.20 | 117 | -8.99 |
| **v6 (target)** | **≥ 14** | varies | varies | varies | **≥ 0** ⭐ |

## 위험 요소

1. **Hypothesis 안 통하면 backtest 안 돌리는 것 같은 효과**: A+C+D 가 LLM 을 "안전" 영역으로 좁혀 v5 같은 wild exploration 이 줄어 best gross 가 오히려 떨어질 수 있음. (smoke 결과 일부 signal 있음 — sticky_obi mean_dur 486 등 새로운 영역.)
2. **Spread bias by date**: IS 가 8 dates 만이라 measured spread 가 실제 deploy 시점과 다를 수 있음. 그러나 측정 기반이라 적어도 IS 에 대해서는 정확.
3. **LLM 이 cheat sheet 의 cell 을 "선택" 하는 bias**: empirical_baselines.md 에 framing 으로 방지 시도하나, observation framing 만으로는 부족할 수 있음.
4. **Maker fill 비현실성**: maker_optimistic 은 항상 fill 가정. 현실은 queue position + adverse selection. 추후 maker_realistic 으로 검증 필요 (현 단계 미구현).

## 사용 references (LLM 에게 노출되는 cheat sheet)

총 19 files, 약 99 K chars. 핵심 5 (REQUIRED):
1. `regime_state_paradigm.md` — paradigm semantics
2. `quick_ref.md` — post-v5 ceiling, magnitude axes, hypothesis template
3. `empirical_baselines.md` — 15-cell partition (3.78M ticks 집계)
4. `t_scaling.md` — 9 T × 5 primitive (drift-adjusted alpha)
5. `direction_semantics.md` — Category A/B1/B2/B3/C decision tree

비교 v5: 17 files, 약 90K chars. v6 는 quick_ref + empirical_baselines + t_scaling 추가, prior_iterations_index.md 트림 (872줄 → 150줄).

## 후속 분기 (v6 결과별)

- **net > 0 spec 발견**: 프로젝트 first deployable spec. paper §Results 핵심. Path E 를 통해 추가 generalization 가능.
- **net 0 ~ -5 bps 도달 (margin)**: Path E (agentic tool-use) 로 LLM 의 cell-level query 정확도 향상 → margin 돌파 시도.
- **net ≤ -10 bps**: Path E 로도 부족할 가능성. fundamental rethink — chain 2 (maker_realistic + queue) 또는 multi-day paradigm 검토.

## 링크

- Plan documents: `wiki/plans/post-v5-roadmap.md`, `wiki/plans/path-a-llm-calibration.md`, `path-b-maker-spread-capture.md`, `path-c-empirical-baselines.md`, `path-d-t-scaling.md`
- Pre-launch smoke: `analysis/maker_smoke_results.json` (mid 4.74 → maker 14.01 검증)
- Predecessor: `exp-2026-04-27-fresh-v5-regime-state-paradigm.md`
- Successor (v7+): TBD
