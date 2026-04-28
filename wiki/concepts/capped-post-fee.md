---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags:
- chain1
- post-fee
- deployability
refs:
  code:
  - path: chain1/agents/feedback_analyst.py
    symbol: _primary_recommendation
    confidence: verified
  - path: chain1/agents/chain2_gate.py
    symbol: FEE_SCENARIOS
    confidence: verified
  papers: []
  concepts:
  - net-pnl-objective
  - magnitude-axes-framework
  - krx-only-deployment-scope
  - exp-2026-04-27-regime-state-paradigm-ablation
  - regime-state-paradigm-default
  - exp-2026-04-27-fresh-v5-regime-state-paradigm
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
---

# Capped Post-Fee

Spec 의 측정값이 **WR 은 충분히 높으나 (≥ 0.55) gross expectancy 가 RT 수수료보다 작아 net 이 음수** 인 상태. v3 fresh run (2026-04-26) 의 80/80 spec 이 모두 이 카테고리.

## Definition

```
spec.aggregate_wr ≥ 0.55  AND  spec.aggregate_n_trades ≥ 100
AND
spec.aggregate_expectancy_bps − fee_bps_rt ≤ 0
```

세 조건을 모두 만족하면 `capped_post_fee = True`. Chain 1 의 feedback-analyst 는 이 상태의 spec 을 magnitude-seeking 행동으로 라우팅 (Fix #1, 2026-04-27).

## Why this label exists

WR 만 reward 로 쓴 v3 에서 LLM 이 도달한 region:
- WR distribution: mean 0.788, max 0.963
- Expectancy distribution: mean 5.79, max 13.32 bps
- KRX 23 bps RT 후 net: 모든 80 spec ≤ 0

WR 차원에서는 진전, expectancy 차원에서는 정체. WR 과 expectancy 가 **decorrelate** 되는 영역으로 optimizer 가 climb 하면서 fee 벽을 통과하지 못함.

이 label 은 두 차원의 분리를 강제 — capped_post_fee 인 spec 은 단순 tighten 으로는 해결되지 않으며, magnitude axis 를 자극해야 한다는 것을 명시.

## Behavioral consequence

Chain 1 feedback-analyst 결정 트리에서 (`_primary_recommendation`):

```python
if fee_bps_rt > 0 and wr ≥ 0.55 and n ≥ 100 and net_exp ≤ 0:
    # Capped post-fee: rotate among magnitude-seeking actions
    options = [change_horizon, extreme_quantile,
               combine_with_other_spec, add_regime_filter]
    direction = options[hash(spec.spec_id) % len(options)]
```

v3 (legacy WR-keyed) 에서는 같은 spec 이 `tighten_threshold` 또는 `add_filter` 로 라우팅되어 WR 만 더 끌어올렸을 행동.

## Examples

| spec_id | WR | exp_bps | fee_bps | net_bps | capped? |
|---|---:|---:|---:|---:|---|
| iter005_ask_wall_reversion_low_vol | 0.94 | 13.32 | 23 | -9.68 | YES |
| iter014_bbo_divergence_low_vol | 0.96 | 9.26 | 23 | -13.74 | YES |
| iter019_consensus_low_vol | 0.96 | 9.42 | 23 | -13.58 | YES |
| (가상: same WR, exp 25 bps) | 0.94 | 25.00 | 23 | +2.00 | NO (deployable) |

Capped post-fee 는 "WR 좋다" 와 "deployable" 사이의 gap. v4 의 측정 목표는 이 gap 통과 spec 의 발견.

## Status

- 2026-04-27: Fix #1 의 결정 트리 분기로 정식 도입
- v3 capped 비율: 80/80 (100%)
- v4 (in progress, iter_008): 27/27 까지 capped 비율 100% (동일 — 아직 fee 벽 미돌파)
