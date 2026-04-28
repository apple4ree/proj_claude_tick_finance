---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [deployment, krx, fee-economics, paper-target]
refs:
  code:
    - {path: "chain1/agents/chain2_gate.py", symbol: "FEE_SCENARIOS", confidence: verified}
  papers: []
  concepts:
    - capped-post-fee
    - net-pnl-objective
    - holding-period-extension
    - krx-only-deployment-scope
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Fee-Binding Constraint

Trading agent system 의 **deployment objective 가 mechanical 한 fee floor 에 의해 hard-bound** 되는 상황. 구체적으로 KRX cash equity 의 RT 23 bps fee 가 chain 1 의 raw signal edge 와 비교 시 binding constraint.

## Definition

```
deployable iff  net_PnL > 0
              ↔  gross_edge > fee_floor + execution_costs
              ↔  gross_edge > 23 bps (KRX) + 5 bps (avg cross-spread)
              ↔  gross_edge > 28 bps
```

Constraint 가 **binding** = 모든 candidate 가 fee floor 와 비교될 때 결과가 결정됨.

## KRX cash equity 의 fee 구성

```
Total RT fee = 1.5 (maker fee) × 2 + 20 (sell tax)
             = 3 + 20
             = 23 bps
```

각 component:
- **Maker fee 1.5 bps**: 증권사 수수료 (retail). taker 는 약간 낮으나 retail rebate 거의 없음
- **Sell tax 20 bps** (0.20%): 정부세 (증권거래세 0.05% + 농어촌특별세 0.15%)
  - **Variable 불가 — 모든 cash equity 매도에 부과**
  - HFT 든 swing trade 든 동일 적용
  - 시장 구조의 hard ceiling

## v3 의 binding 발견

- Chain 1 max gross expectancy: 13.32 bps
- KRX fee floor: 23 bps
- Gap: ~10 bps
- 결과: 0/80 spec fee 통과
- → Chain 1 의 spec language 자체로는 KRX cash 에서 deployment 불가

## Cross-market 비교

| 시장 | RT fee | Constraint 종류 |
|---|---|---|
| **KRX cash equity** | **23 bps** | **binding (sell tax dominant)** |
| KRX 선물 (KOSPI 200) | ~1 bps | non-binding |
| KRX 옵션 | ~5 bps | weakly binding |
| US Nasdaq retail | ~3 bps | non-binding (maker rebate 가능시 negative) |
| Crypto Binance taker | ~8 bps | non-binding for 13 bps signals |
| Crypto maker rebate | ~−2 bps (역리베이트) | non-binding |

→ **KRX cash 가 cash equity 시장 중에서도 가장 fee-binding constraint 가 강함**.

## 시사점 — 우리 framework 의 design pressure

1. **High-magnitude target**: 모든 spec 이 average gross > 28 bps 를 목표로 해야 deployable. v3 13 bps 와 비교 시 ~2× 격차.
2. **Holding period extension**: per-RT fee 가 fixed 이므로 길게 holding 할수록 magnitude/fee 비율 개선.
3. **Schema selection bias**: binary trigger schema (chain 1) 는 이 constraint 를 깨기 어려움. PolicySpec / MM / multi-day schema 가 필요할 수도.

## Related framework

- **Optimal execution literature** (Almgren-Chriss 2001) — minimize execution cost 가 핵심. 우리 framework 에서 cost = fee floor.
- **Algorithmic trading economics** (Cartea-Jaimungal 2015, Ch. 1–3) — net PnL 이 deployment criterion. fee 는 hard 가정.
- **Kyle 1985 / Amihud 2002** — price impact + illiquidity 이 우리 fee 의 secondary cost (chain 1 에선 무시).

## Why "binding" 이 paper-grade observation

대부분의 academic finance / quant trading paper 는 fee 를 light footnote 로 다루거나 0 으로 가정. Real deployment 에서는 fee 가 binding constraint 인 시장이 많음 (KRX, ASIA emerging markets, retail US options 등).

→ **"LLM agent 가 fee-binding 시장에서 어떻게 행동하는가" 는 paper-grade research question**. v3/v4/v5 측정이 직접 evidence.

## Paper relevance

- §Introduction 의 motivation: "fee-binding markets are pervasive yet underexplored"
- §Method 의 setup: KRX fee structure 명시
- §Results 의 핵심 finding: Chain 1 raw edge < fee floor, deployment 불가
- §Discussion 의 implication: schema 또는 holding period 의 paradigm shift 필요

## Status

- 2026-04-27 정식 명명
- Memory 의 `project_krx_only_scope.md` 와 일관
