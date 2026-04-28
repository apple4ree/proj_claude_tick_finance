---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags:
- chain1
- objective
- fix-1
refs:
  code:
  - path: chain1/agents/feedback_analyst.py
    symbol: _primary_recommendation
    confidence: verified
  - path: chain1/agents/signal_improver.py
    symbol: _rank_triples
    confidence: verified
  - path: chain1/orchestrator.py
    symbol: run_loop
    confidence: verified
  papers: []
  concepts:
  - capped-post-fee
  - reward-target-mismatch
  - magnitude-axes-framework
  - krx-only-deployment-scope
  - p1-staged-additions-for-v5
  - exp-2026-04-27-regime-state-paradigm-ablation
  - regime-state-paradigm-default
  - exp-2026-04-27-fresh-v5-regime-state-paradigm
  experiments:
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
---

# Net-PnL Objective

Chain 1 의 1차 reward 를 WR 에서 **net_expectancy = expectancy_bps − fee_bps_rt** 로 전환한 design decision (Fix #1, 2026-04-27). dec-objective-from-wr-to-net-pnl 의 정식 명명.

## Definition

Pipeline 의 4 stage 에서 사용되는 ranking / decision key 가 net_expectancy 로 통일:

```
net_exp = aggregate_expectancy_bps − fee_bps_rt
```

`fee_bps_rt` 는 round-trip fee in bps; CLI flag `--fee-bps-rt` 로 주입. KRX 23 bps / crypto maker 4 bps / hypothetical 다양한 시나리오 가능. `fee_bps_rt = 0` 일 때는 legacy WR-keyed 행동으로 fallback.

## Where the key is used

| Stage | Component | Action |
|---|---|---|
| ① generation | signal_generator._build_user_message | "expectancy_bps MUST exceed {fee_bps_rt}" 단락 주입 |
| ④ feedback | feedback_analyst._primary_recommendation | net_exp ≤ 0 AND wr ≥ 0.55 → magnitude-seeking 라우팅 |
| ⑤ improvement | signal_improver._rank_triples | sort key = (-net_exp, -wr, -n_trades) |
| loop | orchestrator.run_loop | best_metric trajectory = best_net_exp (legacy: best_wr) |

## Why this objective

v3 fresh run (2026-04-26) 결과: 80/80 spec 모두 KRX 23 bps RT 수수료 벽 미통과. WR mean 0.788, max 0.963 으로 WR 차원에서는 진전, expectancy 천장이 13 bps 에서 정체. WR 만 reward 로 주면 optimizer 가 WR 을 1 까지 끌어올리면서도 expectancy 는 안 키움 — 두 차원이 decorrelate 되는 영역으로 climb. capped-post-fee 의 standard failure mode.

Net-PnL 을 reward 로 주면:
- Capped-post-fee spec 이 magnitude-seeking 행동으로 라우팅됨 (cf. capped-post-fee, magnitude-axes-framework)
- LLM hypothesis 텍스트에 fee / expectancy / magnitude 차원이 명시 (v4 측정: 'expectancy' 키워드 빈도 0 → 13)
- Mean horizon 이 +46% 증가 (longer h → larger |Δmid|)

## Backwards compatibility

`fee_bps_rt = 0` (default) 일 때 모든 결정 분기가 v3 의 WR-only 행동과 정확히 동일. Existing CLI / test suite 무영향.

## Empirical evidence (v4 in progress)

Iter 0–8 측정 (2026-04-27 02:31 ~ 05:18, 9/25 iter):

- v3 (legacy) iter 0–3 vs v4 (Fix #1) iter 0–3 동일 표본:
  - tighten_threshold 사용: 8/14 → 0/10
  - mean horizon: 26.3 → 38.4 ticks (+46%)
  - max expectancy: 7.44 → 12.85 bps (+73%)
  - hypothesis 'expectancy' 키워드: 0 → 13 회

- iter_008 spec 사례: `(obi_1 > 0.6) AND (bid_depth_concentration > 0.3) AND (rolling_realized_vol(mid_px, 100) > 40)` — high-vol regime gate 능동 사용

## Limitations

1. WR 이 약간 하락 (mean 0.788 → 0.755) — 일부 high-WR / low-magnitude spec 이 reward 못 받음. trade-off.
2. `fee_bps_rt` 가 hyperparameter — 시장별 / scenario 별 다른 값 ablation 추가 부담.
3. v3 prior_iterations_index.md 가 WR-keyed reasoning 담고 있어 LLM 혼란 가능.

## Status

- 2026-04-27 02:31: v4 launch with `--fee-bps-rt 23.0`
- 2026-04-27 05:30 시점: 9/25 iter 완료, net_exp ≤ 0 spec 100%, max net = -10.15 bps (fee 벽까지 10 bps)
- 재검토 시점: v4 종료 후 net_exp > 0 spec 발견 여부
