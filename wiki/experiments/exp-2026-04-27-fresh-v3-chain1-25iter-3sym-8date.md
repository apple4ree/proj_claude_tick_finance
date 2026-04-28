---
schema_version: 1
type: experiment
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code:
  - path: chain1/orchestrator.py
    symbol: run_loop
    confidence: verified
  - path: chain1/agents/signal_generator.py
    symbol: generate_signals
    confidence: verified
  - path: chain1/agents/signal_evaluator.py
    symbol: evaluate_signal
    confidence: verified
  - path: chain1/agents/feedback_analyst.py
    symbol: analyze_feedback
    confidence: verified
  - path: chain1/agents/signal_improver.py
    symbol: improve_signals
    confidence: verified
  - path: chain1/backtest_runner.py
    symbol: run_backtest
    confidence: verified
  - path: chain1/calibration.py
    symbol: load_table
    confidence: verified
  papers: []
  concepts: []
  experiments:
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
  - krx-only-deployment-scope
  - exp-2026-04-27-regime-state-paradigm-ablation
  - regime-state-paradigm-default
  - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
git_ref: 1465dc7
run_duration: null
seed: null
experiment_id: exp-2026-04-26-fresh-v3-chain1-25iter-3sym-8date
status: completed
duration: 18h 04m
---

# fresh-v3-chain1-25iter-3sym-8date

## 가설
tickdata_krx parquet (data_type=11 trade + data_type=12 quote, 100ms snapshots) + Block E 직접 trade-event primitive(askbid_type, transaction_power) + per-symbol z-score calibration (D1) + 종목 다양화(3 sym) 조합 시, 단일 종목 실험 대비 generalization이 개선되고 KRX 23 bps RT 수수료 벽을 통과하는 spec(net_expectancy > 0)이 발견될 가능성을 측정한다. 1차 reward는 WR.

## 셋업
chain1.orchestrator run --max-iter 25 --n-candidates 4 --symbols 005930 000660 005380 --dates 20260316 20260317 20260318 20260319 20260320 20260323 20260324 20260325 --calibration-table data/calibration/krx_v2_2026_03_3sym.json. PID 2042958, wall clock 18시간 04분. Data: tickdata_krx parquet, merge_asof + 3-layer lookahead protection. Logs: /tmp/chain1_logs/fresh_run_v3.log. Artifacts: iterations_v3_archive/iter_000 ~ iter_024 (25 iter, 100 spec proposed, 80 backtested). 2.5 GB.

## 결과
25/25 iter 완료. WR trajectory iter 0 → 24: 0.879 → 0.860 → 0.938 → 0.890 → 0.903 → 0.922 → 0.921 → 0.956 → 0.928 → 0.930 → 0.915 → 0.896 → 0.704 → 0.921 → 0.963 → 0.960 → 0.929 → 0.934 → 0.929 → 0.962 → 0.767 → 0.905 → 0.919 → 0.814 → 0.758. 80 spec 측정값: WR mean 0.788 / median 0.846 / max 0.963 (iter014_bbo_divergence_low_vol). expectancy_bps mean 5.79 / median 6.73 / max 13.32 (iter005_ask_wall_reversion_low_vol). WR ≥ 0.80 인 spec 43/80 (54%). expectancy ≥ 5 bps인 spec 63/80 (79%). post-fee 시나리오: crypto maker 4 bps RT 66/80 흑자, crypto taker 8 bps 6/80, 가상 15 bps 0/80, KRX 현물 23 bps 0/80. Top spec(iter005)도 net = −9.68 bps.

## 관찰
(1) 신호 raw edge 천장이 13 bps 부근으로 수렴 — 25 iter 동안 max expectancy가 13.32 이상 올라가지 않음. (2) Family 분포: bbo_push/wall(23) consensus(15) trade_flow Block E(14) bbo_divergence(10) OBI 단독(9). 상위 평균은 OBI 단독(6.89) > consensus(6.83) > wall(6.66). Block E는 평균 4.31 bps로 OBI/OFI 대비 추가 edge를 만들지 못함. (3) Saturation 발생 지점 iter_014, 그 이후 iter_020+ 에서 best WR이 하락(0.96 → 0.76). signal-improver의 mutation random walk 패턴 — 부모 → 자식 expectancy 개선률 36/63 (57%, sample mean +0.11 bps with std 3.19). (4) Top 3 spec 모두 'low-vol regime filter' 사용 — rolling_realized_vol(mid_px, 100) < 30. (5) Hypothesis 텍스트 50% 만 정량 claim 포함, 그중 fee 명시는 한 자릿수 — LLM이 fee constraint를 hypothesis space에 넣지 않음.

## 실패 양상
KRX 23 bps RT 수수료 벽을 통과하는 spec 0개. 80 spec 모두 net_expectancy ≤ 0. 80 / 80 = 100% capped post-fee. signal-improver의 후반 mutation은 systematic improvement를 만들지 못하고 동일 family(ask_wall × low_vol) 내 jitter에 머묾.

## 관련 코드
chain1/orchestrator.py run_loop, chain1/agents/signal_generator.py generate_signals, chain1/agents/signal_evaluator.py evaluate_signal, chain1/agents/feedback_analyst.py analyze_feedback (legacy WR-keyed), chain1/agents/signal_improver.py improve_signals (legacy expectancy + WR rank), chain1/backtest_runner.py run_backtest, chain1/calibration.py load_table.

## 다음 단계
본 실험 결과가 후속 결정 dec-objective-from-wr-to-net-pnl 의 motivation으로 사용됨. 이후 v4(Fix #1: WR → net_expectancy objective) 실행.
