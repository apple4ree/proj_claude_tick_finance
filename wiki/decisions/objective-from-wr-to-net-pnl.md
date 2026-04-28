---
schema_version: 1
type: decision
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
  - path: chain1/primitives.py
    symbol: is_opening_burst
    confidence: inferred
  - path: chain1/primitives.py
    symbol: is_lunch_lull
    confidence: inferred
  - path: chain1/primitives.py
    symbol: is_closing_burst
    confidence: inferred
  - path: chain1/primitives.py
    symbol: RollingRangeBps
    confidence: inferred
  papers: []
  concepts: []
  experiments: []
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
decision_id: DEC-2026-04-27-objective-from-wr-to-net-pnl
status: proposed
supersedes: []
superseded_by: []
scope:
- chain1.feedback_analyst
- chain1.signal_improver
- chain1.signal_generator
- chain1.orchestrator
---

# objective-from-wr-to-net-pnl

## 문제
Chain 1의 자가-개선 루프가 WR을 1차 reward로 사용해 spec을 ranking하고 mutation을 추천하는데, 실제 deployment 목표는 net_PnL = expectancy_bps − fee_bps_rt이다. v3 fresh run(80 spec, 25 iter, 3 sym × 8 date)에서 모든 spec이 KRX 23 bps RT 수수료 벽을 통과하지 못함(0/80 deployable). 신호 천장 13.32 bps인데, optimizer는 WR을 0.96까지 끌어올리는 데에 budget을 쓰면서도 expectancy 절대값을 키우는 방향으로는 가지 못함. WR과 net PnL이 decorrelate되는 영역에서 climb이 일어남.

## 검토한 옵션
Option A: WR-based 그대로 두고 chain 2에서 execution으로 fee 보전 시도 — 신호 자체에 magnitude 부재면 execution도 한계. Option B: feedback_analyst의 결정 트리만 net_exp keyed로 변경, ranking은 그대로 — 부분적 일관성. Option C(채택): 결정 트리 + signal_improver ranking + signal_generator prompt + orchestrator convergence detection 모두 net_expectancy 기반으로 통합. Option D: WR과 net_exp을 multi-objective Pareto로 — 구현 복잡, 단일 axis가 아님.

## 선택한 접근
Option C 채택. 4개 stage에 fee_bps_rt 파라미터 plumbing: (1) feedback_analyst._primary_recommendation 결정 트리에 capped-post-fee 분기 추가 — wr ≥ 0.55 AND net_exp ≤ 0이면 magnitude-seeking 4 옵션(change_horizon / extreme_quantile / combine / regime_filter)으로 라우팅. (2) signal_improver._rank_triples 정렬 키를 (-net_exp, -wr, -n)로 변경. (3) signal_generator._build_user_message에 fee constraint 단락 주입 — 'expectancy_bps MUST exceed fee_bps_rt'. (4) orchestrator run_loop convergence detection을 best_wr → best_net_exp으로 전환. CLI 플래그 --fee-bps-rt (default 0; > 0이면 새 objective 활성화).

## 근거
v3 데이터 기반 정량 evidence: (i) feedback recommendation 분포 — v3 14건 중 8건(57%)이 tighten_threshold; v4 첫 4 iter(10건) 중 0건. tighten_threshold가 WR 키우기 위한 행동인데, 같은 spec군이 net_exp을 못 넘는 상태에서는 systematically wasted budget이었음을 의미. (ii) v3 80 spec의 WR mean 0.788, expectancy mean 5.79 bps — WR은 안정적인데 expectancy는 fee의 1/4 수준. WR 차원과 expectancy 차원이 사실상 독립적으로 분포함을 시사. (iii) v4 iter 0–3 mean horizon 26.3 → 38.4 ticks(+46%), max expectancy 7.44 → 12.85 bps(+73%) — 결정 트리 변경 후 LLM이 magnitude 차원으로 search redirect됨. (iv) v4 hypothesis 텍스트에서 'expectancy' 키워드 0 → 13회 등장 — generator prompt 변경의 직접 효과. 판단 근거(P8): 5번째 axis의 'reward function = optimization target'은 standard ML 원칙 적용; deployment 목표(net PnL)와 reward(WR)의 mismatch는 reward hacking의 표준적 failure mode.

## 트레이드오프
(1) Convergence가 더 어려워짐 — magnitude-seeking 행동(특히 change_horizon, extreme_quantile)은 trade count를 줄이고 variance를 키워 statistical power 확보가 어려움. (2) v4 측정상 WR 평균이 살짝 하락(0.788 → 0.755); 일부 'WR 좋은데 fee 못넘는' spec이 reward를 못 받게 되어 LLM이 그 family를 일찍 포기할 수 있음 — short-term WR 손실. (3) 기존 v3 iteration_index(prior_iterations_index.md)가 WR 기반 reasoning을 담고 있어 LLM이 메시지 혼란을 겪을 가능성. (4) fee_bps_rt가 hyperparameter — 시장별/시나리오별 다른 값을 시험해야 하는 추가 ablation 부담.

## 영향 범위
chain1 내부 의사결정 루프 전체. 영향 받는 모듈: feedback_analyst.py, signal_improver.py, signal_generator.py, orchestrator.py. 영향 없는 모듈: backtest_runner, code_generator, fidelity_checker, primitives — 신호 정의/측정 자체는 그대로. Chain 2(execution)는 본 결정과 직교. 외부 데이터/calibration table은 변경 없음. v3 archive(iterations_v3_archive/)는 보존 — A/B 비교 기준선.

## 재검토 조건
(1) v4 또는 v5에서 net_exp > 0 인 spec이 5개 이상 발견되면, fee 벽 통과의 안정성을 추가 측정 — sample 충분하면 net-PnL keyed objective의 효과 확정. (2) 반대로 v4가 끝까지 net_exp > 0 spec을 0개 산출하면 신호 천장 자체가 13bps 부근이라는 가설 강화 — 그 경우 chain 1 layer만으로는 KRX deployment 불가능, chain 2 또는 시장 pivot(crypto) 결정 필요. (3) magnitude-seeking 행동이 noise만 만들어 net_exp 분포가 v3보다 악화되면, ranking key를 (-net_exp, -wr, ...)에서 두 axis 가중 조합(α·net_exp + (1-α)·wr)으로 soft-blend 하는 후속 결정.
