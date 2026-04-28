---
schema_version: 1
type: experiment
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code:
  - path: chain1/agents/feedback_analyst.py
    symbol: _primary_recommendation
    confidence: verified
  - path: chain1/agents/feedback_analyst.py
    symbol: analyze_feedback
    confidence: verified
  - path: chain1/agents/signal_improver.py
    symbol: _rank_triples
    confidence: verified
  - path: chain1/agents/signal_improver.py
    symbol: improve_signals
    confidence: verified
  - path: chain1/agents/signal_generator.py
    symbol: generate_signals
    confidence: verified
  - path: chain1/orchestrator.py
    symbol: run_loop
    confidence: verified
  papers: []
  concepts: []
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - block-f-magnitude-primitives-and-cheat-sheets
  - krx-only-deployment-scope
  - p1-staged-additions-for-v5
  - exp-2026-04-27-regime-state-paradigm-ablation
  - regime-state-paradigm-default
  - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
git_ref: 1465dc7
run_duration: null
seed: null
experiment_id: exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
status: in_progress
pid: 2567353
started: '2026-04-27T02:31:00+09:00'
---

# fresh-v4-fix1-net-pnl-objective

## 가설
Chain 1의 1차 reward를 WR에서 net_expectancy(= expectancy_bps − fee_bps_rt)로 전환(Fix #1)하면 (a) feedback recommendation 분포가 'tighten_threshold'에서 magnitude-seeking 행동(change_horizon, extreme_quantile, add_regime_filter)으로 이동하고, (b) signal-generator hypothesis 텍스트가 fee/expectancy/magnitude 차원을 명시적으로 다루며, (c) v3에서 0/80이었던 'net_expectancy > 0' deployable spec 수가 증가한다. v3 baseline과 동일 config로 비교 측정.

## 셋업
PYTHONPATH=. nohup python -m chain1.orchestrator run --max-iter 25 --n-candidates 4 --symbols 005930 000660 005380 --dates 20260316 20260317 20260318 20260319 20260320 20260323 20260324 20260325 --calibration-table data/calibration/krx_v2_2026_03_3sym.json --fee-bps-rt 23.0. PID 2567353, log /tmp/chain1_logs/fresh_run_v4.log. v3 archive 보존(iterations_v3_archive/), 새 iterations/ 디렉토리 생성. 시작 시각 02:31 (2026-04-27). 변경 모듈: feedback_analyst._primary_recommendation, _headline_strengths_weaknesses, _build_deterministic_feedback, analyze_feedback / signal_improver._rank_triples, _build_deterministic_proposals, _build_user_message, improve_signals / signal_generator._build_user_message, generate_signals / orchestrator._FEE_BPS_RT, stage_feedback, stage_improve, stage_generate, run_loop.

## 결과
본 entry 작성 시점(iter_004 backtest 진행 중, 5/25): WR 평균 0.755 / max 0.922 / iter_3 best_net_exp -15.5576. expectancy 평균 5.66 bps / max 12.85 bps. iter 0–3 비교 데이터(v3 vs v4, 동일 표본): tighten_threshold 8/14 (57%) → 0/10 (0%). add_regime_filter 0 → 3, change_horizon 2 → 3, extreme_quantile 0 → 1. mean horizon 26.3 → 38.4 ticks (+46%). 101–500 ticks 범위 spec 0 → 1 (iter_004_obi_shape_modulated_long_h, h=150). hypothesis 텍스트 키워드: 'fee/bps/cost' 4 → 10, 'expectancy/edge' 0 → 13. mutation axes: threshold 2 → 1, filter 0 → 6.

## 관찰
(1) 결정 트리의 capped-post-fee 분기가 의도대로 활성화 — wr ≥ 0.55 AND net_exp ≤ 0 인 spec이 모두 magnitude-seeking 행동으로 라우팅. (2) signal-generator의 user prompt 변경(fee constraint paragraph 추가)이 LLM의 hypothesis 텍스트 분포에 직접 영향 — 'expectancy' 키워드가 v3에서 0회였는데 v4 첫 4 iter에 13회 등장. (3) iter_3 → iter_4 mutation 사례: iter003_obi_shape_modulated horizon=15 → iter004_obi_shape_modulated_long_h horizon=150 (10×). v3에서는 동일 부모에 대해 tighten_threshold가 적용되었을 행동이 change_horizon으로 대체. (4) WR 평균이 살짝 하락(0.788 → 0.755)하면서 expectancy max는 +73% 상승 — 두 axis 사이의 trade-off가 측정대로 일어남. (5) prior_iterations_index.md(v3 history 공유)로 인해 iter_000의 첫 candidate가 'exact replica' reject — 의도하지 않은 diversity-forcing 효과.

## 실패 양상
본 entry 작성 시점(iter_004) 까지 net_expectancy > 0 spec 0개. v3와 동일하게 max net = -10.15 bps로 fee 벽까지 10.15 bps 남음. 표본이 작아(10 spec) 통계적 결론 불가.

## 관련 코드
chain1/agents/feedback_analyst.py _primary_recommendation _headline_strengths_weaknesses analyze_feedback. chain1/agents/signal_improver.py _rank_triples improve_signals. chain1/agents/signal_generator.py generate_signals _build_user_message. chain1/orchestrator.py run_loop stage_feedback stage_improve stage_generate.

## 다음 단계
v4 끝까지 실행(예상 06:30 완료, 총 ~4–6시간). 25 iter 완료 후 v3 vs v4 ablation 분석 — 결정 트리 변경 → recommendation 분포 변화 → spec 분포 변화 → net_expectancy 분포 변화의 인과 사슬 측정. 이후 v5 launch (P1 primitive + paper + cheat sheet 추가).
