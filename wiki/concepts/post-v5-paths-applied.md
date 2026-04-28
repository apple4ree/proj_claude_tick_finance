---
schema_version: 1
type: concept
created: '2026-04-28'
updated: '2026-04-28'
tags: [methodology, llm-calibration, ablation]
refs:
  code:
    - {path: ".claude/agents/chain1/signal-generator/AGENTS.md", confidence: verified}
    - {path: ".claude/agents/chain1/signal-generator/references/quick_ref.md", confidence: verified}
    - {path: ".claude/agents/chain1/signal-generator/references/prior_iterations_index.md", confidence: verified}
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/empirical_baselines.md", confidence: verified}
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/t_scaling.md", confidence: verified}
    - {path: "chain1/orchestrator.py", symbol: "append_to_prior_index", confidence: verified}
  papers: []
  concepts:
    - magnitude-axes-framework
    - reward-target-mismatch
    - duty-cycle-target
    - maker-spread-capture
  experiments:
    - exp-2026-04-28-fresh-v6-paths-A-B-C-D
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
slug: post-v5-paths-applied
---

# Post-v5 Paths Applied

v5 fresh run 의 best-of-run 4.74 bps gross 천장이 fee 23 bps 와 18 bps gap 인 상태에서, **4 개의 lever** 를 동시 적용한 v6 fresh run 의 architectural premise.

## 진단 (v5 ceiling 의 원인)

| 원인 가설 | Path | 적용 방법 |
|---|---|---|
| LLM hypothesis-magnitude 추측이 unanchored (±100% off) | A, C, D | quick_ref + empirical_baselines + t_scaling |
| AGENTS.md / prior_iterations bloat 의 attention 분산 | A | trim 872줄 → 150줄 (curated only) |
| mid-to-mid execution 의 spread 미회수 | B | maker_optimistic (entry BID, exit ASK) |
| pattern saturation (top 10 v5 가 obi_1 + opening + shape 단일) | C | bias-mitigated 15-cell partition + negative space |

## 4 paths 의 effect (smoke 데이터)

### Path A — Calibration
- `quick_ref.md` 신규 (~80 lines): targets / v5 ceiling / magnitude axes / hypothesis template
- `prior_iterations_index.md` curated (~150 lines, lessons + v5 top 10 only)
- 자동 bloat 분리: orchestrator 가 `prior_iterations_auto_log.md` 별도 파일에 append (LLM 미로드)
- AGENTS.md §3 재구조화: 5 REQUIRED + primitive whitelist + papers + history

**Smoke (1-iter, 1-sym, 1-date, 4 candidates)**: hypothesis template 완전성 4/4 (vs 0/3 v5 carry-over). Diversity 회복 — closing_burst (v5 opening monoculture 탈피), multi_family_consensus (3 distinct families), sticky_obi (T=1000 rolling), zscore z=2.5 (axis C tail).

### Path B — Maker spread capture
- `backtest_runner.py` 의 `backtest_symbol_date_regime` 와 `run_backtest` 에 `execution_mode` 인자 추가
- BID/ASK 가격 regime 별 측정 → `expectancy_maker_bps`, `avg_spread_at_entry_bps`, `avg_spread_at_exit_bps`
- Schema 확장: `PerSymbolResult.execution_mode` + `BacktestResult.aggregate_expectancy_maker_bps`
- CLI: `--execution-mode {mid_to_mid|maker_optimistic}`

**Smoke (top 5 v5 specs × 8 dates × 3 syms)**: maker gain ≈ +9.2 bps (avg measured spread 9.21 bps). Best maker gross 14.01 (iter013). Net 0/5 (fee floor 14 bps mid 임계 도달 한계).

### Path C — Empirical baselines
- `analysis/empirical_baselines.py`: 5 time × 3 vol = 15 cells 의 metric 표
- 3.78M ticks (3 syms × 8 IS dates) 집계
- Distribution (mean / median / p90), negative-space (fee-prohibitive 라벨), observation framing
- Output: `data/calibration/empirical_baselines.json` + `cheat_sheets/empirical_baselines.md`

**측정 결과**: opening (3 vol 모두) 와 closing high-vol 이 high-magnitude (mean T=50 ≥ 3 bps). lunch high-vol 과 afternoon high-vol 이 fee-prohibitive (mean < 1 bps). v5 가 opening 에 saturated 인 것 — 데이터로 정합 (그러나 v6 는 하나의 cell 에 saturate 하지 않게 framing).

### Path D — T-scaling
- `analysis/t_scaling.py`: 9 T values × 5 primitives × 4 metrics
- **Macro-drift bias 발견하고 보정**: `alpha_vs_drift_bps = mean_signed − unconditional_drift`
- Output: `data/calibration/t_scaling.json` + `cheat_sheets/t_scaling.md`

**측정 결과**: obi_1 @ T=500 의 alpha_vs_drift = +24.11 bps (drift 보정 후), WR 0.399. 즉 random-walk 기반 long-T 영역에 "+24 bps signal-only edge" 가 존재 (단 overlapping windows / tick discreteness 주의).

## v5 vs v6 ablation 디자인

동일 조건:
- 8 IS dates, 3 syms
- 25 iter × 4 candidates
- regime-state mode
- fee-bps-rt = 23.0
- calibration table 동일

차이:
- v6 references (5 REQUIRED, 19 files total ~99K chars) vs v5 (17 files ~90K chars, prior_iterations bloated)
- v6 `--execution-mode maker_optimistic` (Path B) vs v5 mid_to_mid

→ v5 vs v6 의 비교는 **clean ablation** for "post-v5 4 paths 의 결합 효과".

## Risks / 한계

1. **Cheat sheet contamination**: A/C/D 가 LLM 의 hypothesis space 를 좁힐 수 있음 — wild exploration 감소. → diversity metric 으로 monitor.
2. **Cell-picking bias 잔존**: empirical_baselines.md 의 framing 만으로는 LLM 이 "high-magnitude cell 에서 trigger" bias 가 완전 사라지지 않을 수 있음. 결과 분석 시 top spec 의 cell 분포 확인.
3. **Maker fill 비현실성**: Path B 가 항상-fill 가정. 실제는 queue + adverse selection. chain 2 영역.
4. **Drift adjustment 의 statistical 가정**: T-scaling 의 alpha_vs_drift 는 IS 의 day-trend 가 OOS 에서도 유사하다고 가정. OOS drift 가 다르면 이 보정이 반대 방향으로 bias 시킬 수 있음.

## 링크

- `path-a-llm-calibration` plan
- `path-b-maker-spread-capture` plan
- `path-c-empirical-baselines` plan
- `path-d-t-scaling` plan
- `post-v5-roadmap` master sequencing
- `exp-2026-04-28-fresh-v6-paths-A-B-C-D` first joint run
- `maker-spread-capture` concept (Path B 결과)
