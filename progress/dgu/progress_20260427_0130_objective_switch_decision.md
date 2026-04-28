---
date: 2026-04-27 01:30
tone: pivot
title: Reward WR → net-PnL 전환 (Fix #1)
---

## Context
v3 80 spec 모두 KRX 23 bps RT 수수료 벽을 통과하지 못함. 신호 천장 13 bps인데 fee가 23 bps이라 산술적 gap. WR과 net-PnL이 decorrelate되는 영역에서 optimizer가 climb. Reward function 자체가 deployment 목표(net PnL)와 mismatch하는 reward hacking 표준 failure mode.

## Done
- 5개 root cause 식별 (10-topic 관점: calibration, search collapse, compositional fragility, OOS guarantee 부재, noisy ranking)
- Option A/B/C/D 4가지 옵션 검토 → Option C 채택 (4-stage plumbing)
- chain1/agents/feedback_analyst.py: `_primary_recommendation`에 capped-post-fee 분기 추가 — net_exp ≤ 0 AND wr ≥ 0.55 → magnitude-seeking 4 옵션(change_horizon / extreme_quantile / combine / regime_filter)으로 라우팅
- chain1/agents/signal_improver.py: `_rank_triples` 정렬 키를 (-net_exp, -wr, -n)로 변경
- chain1/agents/signal_generator.py: `_build_user_message`에 fee constraint paragraph 주입 — "expectancy_bps MUST exceed fee_bps_rt"
- chain1/orchestrator.py: `--fee-bps-rt` CLI 플래그 (default 0; > 0이면 새 objective 활성화), `_FEE_BPS_RT` global, `run_loop`의 convergence detection을 best_wr → best_net_exp으로 전환

## Numbers
- v3 capped post-fee spec 비율: 80/80 (100%)
- v3 신호 천장 (max gross expectancy): 13.32 bps
- KRX RT fee: 23 bps (1.5+1.5 + 20 sell tax)
- 변경 모듈 수: 4 (feedback_analyst, signal_improver, signal_generator, orchestrator)
- 새 CLI flag: 1 (--fee-bps-rt)

## Next
- Smoke test (1-iter deterministic-only) 검증
- v4 launch (background, --fee-bps-rt 23.0)
- A/B 비교를 위해 v3 archive 보존 (iterations_v3_archive/)
