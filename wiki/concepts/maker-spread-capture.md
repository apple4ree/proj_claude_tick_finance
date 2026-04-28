---
schema_version: 1
type: concept
created: '2026-04-28'
updated: '2026-04-28'
tags: [execution, maker, spread, fee-economics]
refs:
  code:
    - {path: "chain1/backtest_runner.py", symbol: "backtest_symbol_date_regime", confidence: verified}
    - {path: "chain1/backtest_runner.py", symbol: "run_backtest", confidence: verified}
  papers:
    - stoikov-2018-microprice
  concepts:
    - fee-binding-constraint
    - capped-post-fee
  experiments:
    - exp-2026-04-28-fresh-v6-paths-A-B-C-D
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
slug: maker-spread-capture
---

# Maker Spread Capture

## 정의

체결 회계를 mid-to-mid 가 아닌 **touch-side maker** 로 변경:
- Long: enter at BID, exit at ASK
- Short: enter at ASK, exit at BID

Effect: realized gross = mid_to_mid_gross + (avg measured spread bps).

## Mathematical accounting

```
mid_to_mid:    gross_bps = (mid_exit − mid_entry) / mid_entry × 1e4 × dir
maker_optimistic:
  (long)       gross_bps = (ask_exit − bid_entry) / bid_entry × 1e4
  (short)      gross_bps = (ask_entry − bid_exit) / ask_entry × 1e4

마이너스 부호 무시 시:
  maker_gross ≈ mid_gross + (spread_entry/2 + spread_exit/2)
              ≈ mid_gross + avg_spread
```

KRX 005930 / 000660 / 005380 (8 IS dates 측정): **avg_spread ≈ 9.2 bps**.

## KRX RT fee 와의 관계

KRX cash 의 fee 구조:
- Maker: 1.5 bps (taker 도 같음, 양쪽 1.5×2 = 3 bps)
- Sell tax: **20 bps (sell-side 만, maker/taker 무관 — 직접세)**
- Total RT: 23 bps (long 포지션 기준)

→ **maker mode 가 fee 자체를 줄이지 않음**. 단지 realized gross 가 mid_gross + spread 가 됨으로써 require된 mid-gross 임계가 23 → 14 bps 로 낮아짐.

## v5 → v6 적용 효과 (smoke, top 5 specs × 8 dates × 3 syms)

| spec | mid_gross | maker_gross | spread | net (maker − 23) |
|---|---:|---:|---:|---:|
| iter013_opening_burst_conviction | 4.74 | 14.01 | 9.25 | -8.99 |
| iter016_stable_pressure_on_fragile_book | 4.08 | 13.93 | 9.84 | -9.07 |
| iter009_stable_imbalance_vs_fragile_book | 3.85 | 13.73 | 9.87 | -9.27 |
| iter000_full_book_consensus | 3.44 | 12.15 | 8.70 | -10.85 |
| iter020_magnitude_consensus_at_open | 3.42 | 11.81 | 8.38 | -11.19 |

→ 평균 +9.2 bps gain, 그러나 net 통과 0/5. **Path B 단독으로는 부족, A+C+D 결합이 필수**.

## 한계 / 미구현 사항

1. **maker_optimistic 은 항상 fill 가정**: 현실은 queue position + adverse selection. 신호 반대 방향으로 갈 때 잘 fill, 찬성 방향에서 안 fill — bias.
2. **Sell tax 의 mechanical 성**: 매도세 0.20% 는 maker 분류 무관. KRX 시장 구조 자체 이슈.
3. **Spread 측정의 sampling bias**: regime entry/exit 시점만 측정. 신호가 조용한 시점 (낮은 spread) 만 활성화하는 spec 은 측정치보다 더 큰 spread capture 가능 (drift).
4. **maker_realistic** (queue model + adverse selection 반영) 은 chain 2 영역으로 이전 예정.

## Paper 인용 후보

§Method:
- "We extend the chain 1 backtest to record both mid-to-mid and maker_optimistic gross
   per regime, allowing the LLM agent to design specs against the realized fee floor of
   23 bps instead of the artificial mid-floor of 28 bps (= 23 + 5 spread)."

§Discussion:
- "Our maker_optimistic mode is upper-bound for spread capture; production deployment
   requires a queue + adverse selection model (chain 2)."

## 링크

- `fee-binding-constraint` — 23 bps mechanical floor (sell tax)
- `capped-post-fee` — measurement label for "gross 통과 했지만 fee 후 음수" 패턴
- `path-b-maker-spread-capture` — implementation plan
- `exp-2026-04-28-fresh-v6-paths-A-B-C-D` — 첫 적용 실험
