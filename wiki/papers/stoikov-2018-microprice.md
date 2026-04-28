---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [microstructure, microprice, foundational]
refs:
  code:
    - {path: "chain1/primitives.py", symbol: "microprice", confidence: verified}
    - {path: "chain1/primitives.py", symbol: "microprice_dev_bps", confidence: verified}
  papers: []
  concepts: []
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
authors: [Sasha Stoikov]
venue: Quantitative Finance
year: 2018
---

# Stoikov (2018) — The Micro-Price

**Citation**: Stoikov, S. (2018). "The micro-price: a high-frequency estimator of future prices". *Quantitative Finance*, 18(12), 1959–1966.

## TL;DR

Mid-price 보다 정확한 short-term price predictor — **microprice = (P_b · Q_a + P_a · Q_b) / (Q_a + Q_b)**. Order book 의 imbalance (volume-weighted) 가 다음 mid-price 의 direction 을 predict.

## 핵심 정의

```
microprice = (P_bid × Q_ask + P_ask × Q_bid) / (Q_ask + Q_bid)
            = mid_price + spread/2 × (Q_bid − Q_ask) / (Q_bid + Q_ask)
            = mid_price + spread/2 × OBI_1
```

→ Imbalance 가 양수 (bid heavy) 면 microprice > mid → 다음 tick 에 mid 가 오를 것을 예측. Imbalance 음수 면 반대.

## Theoretical justification

Random walk + queue dynamics 가정 하에서 **microprice 가 conditional expectation of next tick's mid-price**:
```
E[mid_{t+1} | book state at t] ≈ microprice_t
```

→ short-term arbitrage-free price.

## 우리 framework 와의 사용

### chain 1 primitives
- `microprice` — raw microprice value
- `microprice_dev_bps` — `(microprice − mid) / mid * 1e4` (microprice deviation from mid in bps)
- `microprice_velocity` — Δmicroprice / Δt (Block D)

### Direction semantics
- `microprice_dev_bps` 는 Category A (pressure/flow) per `direction_semantics.md`
- 양수면 microprice > mid → 다음에 mid 가 올라감 → long_if_pos

## v3 의 measured behavior

- `microprice_dev_bps` 사용 spec: WR 평균 0.78, expectancy ~3 bps
- 단독 사용시 effective horizon 1-3 ticks 만 (very short-term predictor)
- 우리 chain 1 의 Block A primitive 의 핵심 component

## OBI 와의 관계

위 식에서 `microprice = mid + spread/2 × OBI_1`. 즉 microprice 는 사실상 OBI 와 spread 의 결합. 따라서:
- spread = 0 일 때 microprice = mid (OBI 무관)
- spread 큰 시점에 OBI 의 영향 amplify

→ chain 1 spec 에서 `microprice_dev_bps` 와 `obi_1` 의 사용은 부분 redundant.

## 인용 우선순위

⭐⭐⭐ **§Method**:
- "We use Stoikov's (2018) microprice as a baseline price predictor in our primitive whitelist..."

⭐⭐ **§Background**:
- Microstructure foundational paper, near-universal in HFT literature

## Connection

- `chain1/_shared/references/papers/stoikov_2018_microprice.md` — full summary (existing)
- 우리 chain 1 의 가장 frequently-used reference 중 하나
- TradeFM (2026) 의 EW-VWAP 가 이 microprice 의 simulator-side variant

## Status

- Existing reference, stable
- Foundational, no recent supersession
