# Cont, Kukanov, Stoikov (2014) — *The Price Impact of Order Book Events*

**Canonical reference for Order Flow Imbalance (OFI)** — Chain 1 signal-generator must cite this paper when proposing any `ofi_*` primitive.

Citation: Cont, R., Kukanov, A., & Stoikov, S. (2014). *The Price Impact of Order Book Events.* Journal of Financial Econometrics, 12(1), 47–88.

---

## Core finding

At short horizons (seconds), price moves are **linearly driven by net order flow at the best quote**, not by realized trades alone. The authors define OFI as a single scalar per tick and show it explains >65% of 10-second mid-price variance (their NYSE data).

## Formal definition (eq. 6–8 in paper)

Let $t_n$ denote the n-th event on the order book (bid or ask side price/qty change). Define the individual event contribution:

$$
e_n = \underbrace{\mathbb{1}_{\{P^b_n \ge P^b_{n-1}\}} \cdot q^b_n}_\text{bid price up/same, +qty} - \underbrace{\mathbb{1}_{\{P^b_n \le P^b_{n-1}\}} \cdot q^b_{n-1}}_\text{bid price down/same, −prev qty} - \underbrace{\mathbb{1}_{\{P^a_n \le P^a_{n-1}\}} \cdot q^a_n}_\text{ask price down/same, +qty} + \underbrace{\mathbb{1}_{\{P^a_n \ge P^a_{n-1}\}} \cdot q^a_{n-1}}_\text{ask price up/same, −prev qty}
$$

OFI over an interval $[t_{k-1}, t_k]$ is $\text{OFI}_k = \sum_{n: t_n \in (t_{k-1}, t_k]} e_n$.

## Linear impact model (eq. 10)

$$\Delta P_k = \alpha + \beta \cdot \frac{\text{OFI}_k}{\text{ADV}} + \epsilon_k$$

Coefficient $\beta$ is stable across stocks once OFI is normalized by average daily depth. R² for 10-second bars: 0.65 (median).

---

## Practical recipe for Chain 1

### Primitive: `ofi_cks_1` (formal)

Stateful: needs previous tick's `BIDP1, BIDP_RSQN1, ASKP1, ASKP_RSQN1`. For each tick t:

```
bid_contrib = 0
if BIDP1_t >  BIDP1_{t-1}: bid_contrib =  BIDP_RSQN1_t         # new higher bid level
if BIDP1_t == BIDP1_{t-1}: bid_contrib =  BIDP_RSQN1_t − BIDP_RSQN1_{t-1}   # size change at same level
if BIDP1_t <  BIDP1_{t-1}: bid_contrib = -BIDP_RSQN1_{t-1}     # level abandoned

ask_contrib = 0
if ASKP1_t <  ASKP1_{t-1}: ask_contrib =  ASKP_RSQN1_t
if ASKP1_t == ASKP1_{t-1}: ask_contrib =  ASKP_RSQN1_t − ASKP_RSQN1_{t-1}
if ASKP1_t >  ASKP1_{t-1}: ask_contrib = -ASKP_RSQN1_{t-1}

ofi_cks_1 = bid_contrib − ask_contrib
```

### Primitive: `ofi_proxy` (simplified, using KIS pre-computed deltas)

```
ofi_proxy = (TOTAL_BIDP_RSQN_ICDC − TOTAL_ASKP_RSQN_ICDC)
          / (|TOTAL_BIDP_RSQN_ICDC| + |TOTAL_ASKP_RSQN_ICDC| + 1e-9)
```

This is **not the formal CKS OFI**. It's a bounded [-1, 1] proxy using pre-computed aggregate delta fields from KIS. Correlation with formal OFI over KRX data empirically: TBD (needs measurement in Chain 1 baseline).

---

## Key lessons for signal design

1. **OFI > OBI for prediction**: the CKS paper shows flow (changes) explains returns better than level (state). Chain 1 should always consider OFI variants in parallel with OBI.
2. **Linear scaling with ADV**: raw OFI magnitude is not directly comparable across symbols; **normalize** before thresholding. In Chain 1, either standardize per-symbol z-score (`zscore(ofi_proxy, W)`) or use `ofi_proxy`'s bounded [-1, 1] form.
3. **Interval matters**: OFI aggregated over longer windows (1s+) predicts better than single-tick OFI because high-frequency noise cancels. Chain 1 generator may propose `rolling_mean(ofi_proxy, W)`.
4. **Non-best levels matter less** (per Huang & Polak 2011 and Cartea 2018): top-of-book OFI captures most of the information. Deeper levels (obi_5, obi_10) are supplementary.

---

## Citation for SignalSpec

When a SignalSpec uses OFI, its `references` field should include:
- `_shared/references/papers/cont_kukanov_stoikov_2014_ofi.md`
- `_shared/references/cheat_sheets/obi_family_formulas.md`
