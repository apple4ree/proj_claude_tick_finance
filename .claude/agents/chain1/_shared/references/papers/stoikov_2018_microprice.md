# Stoikov (2018) — *The Micro-Price: A High-Frequency Estimator of Future Prices*

**Canonical reference for Microprice** — Chain 1 signal-generator must cite this paper when using `microprice` or `microprice_dev_bps` primitives.

Citation: Stoikov, S. (2018). *The Micro-Price: A High-Frequency Estimator of Future Prices.* Quantitative Finance, 18(12), 1959–1966. [SSRN 2970694]

---

## Definition (top-of-book form)

$$
P^{\text{micro}} = \frac{Q^a \cdot P^b + Q^b \cdot P^a}{Q^a + Q^b}
$$

where $Q^b, Q^a$ are bid/ask sizes at the best and $P^b, P^a$ are best bid/ask prices. Observation: quantities and prices are **cross-multiplied** between sides.

**Interpretation**: the bigger the bid queue, the more "inertia" pulls expected future price toward the ask (since bid imbalance → imminent up-move).

## Relation to OBI (exact algebra)

$$
P^{\text{micro}} - P^{\text{mid}} = \frac{\text{spread}}{2} \cdot \text{obi}_1
$$

Therefore, `microprice_dev_bps = (spread_bps / 2) * obi_1`. The two primitives differ **only by the spread scaling**. In thin-spread books they are near-identical; in wide-spread books, microprice's magnitude scales with uncertainty.

## Empirical claim

Stoikov shows that over 1s–60s horizons, $E[\text{mid}_{t+h} \mid \mathcal{F}_t] \approx P^{\text{micro}}_t$ with R² comparable to OBI but slightly better in wide-spread regimes. The "best linear predictor of future mid" property is the paper's main contribution.

## Extension: multi-level VAMP

$$
P^{\text{VAMP}}_N = \frac{\sum_{i=1}^N Q^a_i \cdot P^b_i + \sum_{i=1}^N Q^b_i \cdot P^a_i}{\sum_{i=1}^N Q^b_i + \sum_{i=1}^N Q^a_i}
$$

where N is usually chosen as a fixed percentage of mid (e.g., 1% → sum all levels within mid × (1 ± 0.01)).

---

## Practical recipe for Chain 1

### `microprice` (primitive)
```
microprice = (ASKP_RSQN1 * BIDP1 + BIDP_RSQN1 * ASKP1) / (ASKP_RSQN1 + BIDP_RSQN1)
```

### `microprice_dev_bps` (primitive — recommended)
```
mid = (BIDP1 + ASKP1) / 2
microprice_dev_bps = (microprice − mid) / mid * 1e4
```

Unitful (bps), symmetric in sign (positive → microprice above mid → up-pressure expected).

### `vamp_k` (depth-extended)
Chain 1 may propose depth-k extension using k=1 (= microprice), k=5, or k=10. Reference: CLAUDE.md §참조 자료.

---

## Key lessons for signal design

1. **Microprice vs OBI equivalence**: Don't waste iteration budget training both separately — they carry the same rank-ordering information in a single-level setup. Chain 1 evaluator should flag a spec that uses both as primary signals.
2. **Spread-dependent magnitude**: microprice_dev_bps amplifies the signal in wide-spread regimes. Useful for execution-time gating (Chain 2 concern) but worth noting in Chain 1 for bucketed WR analysis.
3. **Multi-level extension matters** when Book Slope differs on bid vs ask side (asymmetric liquidity). VAMP_5 / VAMP_10 can differ from VAMP_1 (= microprice).

---

## Citation for SignalSpec

When a SignalSpec uses microprice, its `references` field should include:
- `_shared/references/papers/stoikov_2018_microprice.md`
- `_shared/references/cheat_sheets/obi_family_formulas.md`
