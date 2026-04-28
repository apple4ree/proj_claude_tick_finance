---
schema_version: 1
type: experiment
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code:
  - path: chain1/backtest_runner.py
    symbol: run_backtest
    confidence: verified
  - path: chain1/orchestrator.py
    symbol: stage_backtest
    confidence: verified
  papers: []
  concepts:
  - capped-post-fee
  - net-pnl-objective
  - magnitude-axes-framework
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
  - exp-2026-04-27-regime-state-paradigm-ablation
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
git_ref: 1465dc7
run_duration: null
seed: null
experiment_id: exp-2026-04-27-fresh-v5-regime-state-paradigm
status: in_progress
pid: 2845354
started: '2026-04-27T09:00:00+09:00'
---

# fresh-v5-regime-state-paradigm

## 가설
Chain 1 의 fixed-H paradigm 이 fee economics 측면에서 자기-패배적 (매 tick fire = N trades = N × 23 bps fee)이라는 진단 하에, regime-state paradigm (signal True 동안 hold, False 시 exit) + Fix #1 (net-PnL reward) + 모든 agent prompt 재정비 후 fair 측정. 가설: regime-state 에서 LLM 이 적절한 duty cycle (5–80%) 과 mean duration (50–500 ticks) 을 가진 spec 을 짜면 net_expectancy_bps > 0 인 spec 발견 가능. v3/v4 의 0/total 결과를 깰 수 있는지가 핵심.

## 셋업
PID 2845354. chain1.orchestrator run --max-iter 25 --n-candidates 4 --symbols 005930 000660 005380 --dates 20260316~20260325 (8 dates) --calibration-table data/calibration/krx_v2_2026_03_3sym.json --fee-bps-rt 23.0. backtest mode = regime_state (default), force-close 없음. log /tmp/chain1_logs/fresh_run_v5.log. v3 archive iterations_v3_archive/ + v4 archive iterations_v4_archive/ 보존. 모든 agent prompt 재정비됨: signal-generator (regime semantics), feedback (sanity checks), improver (mutation 재해석), chain2-gate (G5 추가), 신규 cheat sheet regime_state_paradigm.md 추가, prior_iterations_index reset.

## 결과
본 entry 작성 시점 launch 직후. iter_000 진행 중. 결과 측정 시 비교 baseline: v3 (0/80 fee 통과, mean exp 5.79 bps), v4 (0/total fee 통과 — net_exp -10 ~ -17 bps 범위). v5 의 핵심 측정량: aggregate_n_regimes 분포, signal_duty_cycle 분포 (target 0.05–0.80), mean_duration_ticks 분포 (target 20–5000), expectancy_bps 분포, mean(expectancy_bps) > 0 spec 비율, expectancy_bps > 23 (fee 통과) spec 비율, expectancy_bps > 28 (deployable) spec 비율, sanity check trigger 비율 (artifact 감지율).

## 관찰
Launch 직후. 별도 결과 entry 추가 예정.

## 관련 코드
chain1/backtest_runner.py:run_backtest mode='regime_state' / chain1/backtest_runner.py:backtest_symbol_date_regime / chain1/agents/feedback_analyst.py:_primary_recommendation / .claude/agents/chain1/_shared/schemas.py:BacktestResult / .claude/agents/chain1/_shared/references/cheat_sheets/regime_state_paradigm.md / chain1/orchestrator.py:stage_backtest.

## 다음 단계
v5 진행 모니터링 (~6h). 완료 후 v3/v4/v5 3-way ablation 분석. mean(expectancy_bps) > 0 spec 발견 시 paper-grade evidence (regime-state paradigm 의 효과 입증). 0 spec 이면 chain 1 spec language 자체 한계 결론 (schema 확장 또는 multi-day paradigm 으로 escalation 필요).
