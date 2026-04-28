---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [microstructure, ofi, foundational]
refs:
  code:
    - {path: "chain1/primitives.py", symbol: "ofi_proxy", confidence: verified}
    - {path: "chain1/primitives.py", symbol: "ofi_cks_1", confidence: verified}
  papers: []
  concepts: []
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
authors: [Rama Cont, Arseniy Kukanov, Sasha Stoikov]
venue: Journal of Financial Econometrics
year: 2014
---

# Cont, Kukanov, Stoikov (2014) — The Price Impact of Order Book Events

**Citation**: Cont, R., Kukanov, A., Stoikov, S. (2014). "The Price Impact of Order Book Events". *Journal of Financial Econometrics*, 12(1), 47–88.

## TL;DR

**OFI (Order Flow Imbalance) 의 정식 정의** + linear mid-price regression 입증. 우리 chain 1 의 `ofi_proxy` / `ofi_cks_1` primitive 의 직접 backbone.

## 핵심 contribution

### OFI 정의
```
OFI_t = Σ ε_n^B (P_n^B Q_n^B − P_{n-1}^B Q_{n-1}^B)
       − Σ ε_n^A (P_n^A Q_n^A − P_{n-1}^A Q_{n-1}^A)
```
- bid 측 변화량 − ask 측 변화량 (sign-corrected)
- 양수면 buy pressure, 음수면 sell pressure

### Linear regression of mid-price changes
```
ΔP_t = α + β · OFI_t + ε
```
- β ≈ +1 / (depth × 2) (이론적 prediction)
- 실측 R² 0.4–0.6 (high explanatory power for tick-level)

## 우리 framework 와의 직접 사용

### chain 1 primitives
- `ofi_proxy` — book level 1 의 OFI proxy
- `ofi_cks_1` — full Cont-Kukanov-Stoikov definition (level 1)
- `ofi_depth_5` / `ofi_depth_10` — multi-level extension

### Direction semantics
- OFI 는 Category A (pressure/flow) per `direction_semantics.md`
- 양수 → long_if_pos (price 따라 올라감)
- 우리 v3 측정: `ofi_*` family 의 direction 정확도 95%

## v3 의 measured behavior

- OFI primitive 사용 spec 의 평균 expectancy: 4.3 bps (cite: family analysis)
- WR 평균: 0.78 (Category A 의 typical)
- 그러나 fee 통과 못 함 (KRX 23 bps)

## 인용 우선순위

⭐⭐⭐ **§Method**:
- Primitive whitelist 의 OFI family 직접 인용
- "We adopt the Order Flow Imbalance (OFI) formulation of Cont, Kukanov, Stoikov (2014) as a Category A pressure indicator..."

⭐⭐ **§Background**:
- "Microstructure literature (CKS 2014, Stoikov 2018) establishes OFI and microprice as theoretically grounded direction predictors..."

## Limitations of CKS in our context

- CKS 의 linear regression 은 daily / 5-min aggregated. Tick-level (100ms) 에서는 noise dominates linearly.
- 우리 chain 1 은 OFI 의 binary thresholding (ofi_proxy > 0 등) 으로 사용 — non-linear.

## Connection

- `chain1/_shared/references/papers/cont_kukanov_stoikov_2014_ofi.md` — full summary (existing)
- `direction_semantics.md` Category A 정의의 backbone
- 우리 chain 1 의 가장 자주 사용되는 reference 중 하나

## Status

- Existing reference, well-integrated since v0
- Stable (foundational paper, no recent supersession)
