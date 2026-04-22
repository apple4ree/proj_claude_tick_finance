# OFI Family — Flow-Based Primitives

> Separate cheatsheet because OFI primitives are **stateful** (require previous tick) and warrant distinct handling in signal-generator's Reasoning Flow.

---

## Whitelist

| Primitive | Statefulness | Bounded | Primary ref |
|---|---|---|---|
| `ofi_cks_1` | 1-tick lookback (needs `BIDP1_{t-1}, BIDP_RSQN1_{t-1}, ASKP1_{t-1}, ASKP_RSQN1_{t-1}`) | unbounded (shares) | CKS 2014 §3 |
| `ofi_depth_5` | 1-tick lookback, top-5 levels | unbounded | CKS 2014 §3.2 — depth-k extension |
| `ofi_depth_10` | 1-tick lookback, top-10 levels | unbounded | CKS 2014 §3.2 |
| `ofi_proxy` | 0 lookback (uses pre-computed KIS delta) | [-1, 1] | cheap approximation |
| `vol_flow` | 1-tick lookback (`ΔACML_VOL`) | ≥ 0 (shares) | trade-flow proxy |
| `rolling_mean(ofi_*, W)` | W-tick lookback | unbounded | smooth / aggregate |
| `zscore(ofi_*, W)` | W-tick lookback | ≈ [-3, 3] | standardize per-symbol |

## Why OFI > OBI at short horizon (repeated from CKS paper)

- OBI (state): biased by non-trading idle book state — lots of OBI shifts don't forecast returns
- OFI (flow): directly captures the **information arrival event** — change in book level
- Empirical: CKS 2014 fig. 6, OFI explains 65% of 10s mid variance, OBI explains ~30%

## Common pitfalls

1. **Single-tick OFI is noisy**. Always aggregate (rolling_mean with W ≥ 10 ticks) or use z-score.
2. **Boundary effects at session open**: first ~30 seconds of session have anomalous book activity. Filter or discard.
3. **Large queue drops without trades**: CKS OFI treats level abandonment (price move) separately from size change. `ofi_proxy` conflates them — higher variance.
4. **Symbol scaling**: Raw ofi_cks_1 in shares is not comparable across stocks. Normalize by ADV or use z-score within symbol.

## Recommended Chain 1 first candidates

- `ofi_proxy > 0.5` — simple, bounded, likely-strong per-tick directional proxy
- `zscore(ofi_proxy, 300) > 1.5` — z-normalized over 30s window (300 × 100ms)
- `rolling_mean(ofi_cks_1, 50) > 0 AND rolling_mean(ofi_cks_1, 50) > rolling_std(..., 50)` — trend confirmation

---

## References

- [`../papers/cont_kukanov_stoikov_2014_ofi.md`] — formal definition
- [`../papers/stoikov_2018_microprice.md`] — shows microprice as a continuous counterpart
- [`./obi_family_formulas.md`] — level-based counterpart
