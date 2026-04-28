# Easley, López de Prado, & O'Hara (2012) — Flow Toxicity and Liquidity in a High-Frequency World

**Citation**: Easley, D., López de Prado, M. M., & O'Hara, M., "Flow Toxicity and Liquidity in a High-Frequency World", *Review of Financial Studies* 25(5), 1457–1493 (2012).

## Why this matters to our project

This paper introduces **VPIN (Volume-synchronized Probability of Informed Trading)** — the modern, HF-friendly proxy for adverse-selection (Glosten-Milgrom 1985's π parameter). It is the **direct theoretical bridge** between trade-tick data and our framework's adverse-selection cost component.

Specifically for us:
1. Justifies adding a `vpin` primitive to Chain 1 once trade tick (H0STCNT0) feed is integrated.
2. Provides a quantitative way to flag "toxic" market regimes — periods where informed traders dominate, making naive signal-based execution money-losing.
3. Explains why our `trade_imbalance_signed` primitive is informative: it is a one-tick approximation to one ingredient of VPIN's volume-bucketed flow toxicity.

## 1. The original PIN problem

Easley-Kiefer-O'Hara-Paperman (1996) PIN model estimated probability of informed trading via daily buy/sell trade counts. Issues at HF:
- Daily aggregation loses HF dynamics
- MLE estimation is fragile (numerical issues with rare events)
- Cannot react in real time

VPIN addresses all three.

## 2. VPIN definition

### Step 1: Time bars → Volume bars
Instead of fixed-time intervals, partition the day into **volume buckets** of equal volume V (e.g., 1/50 of average daily volume per bucket).

### Step 2: Trade direction in each bucket
Within bucket τ, classify each trade as buy or sell (e.g., via Lee-Ready tick rule). Compute:
```
V_τ_B = total buy volume in bucket τ
V_τ_S = total sell volume in bucket τ
V = V_τ_B + V_τ_S = constant (by construction of volume bucket)
```

### Step 3: Toxicity per bucket
```
toxicity_τ = |V_τ_B − V_τ_S| / V
            = imbalance fraction
```

### Step 4: VPIN smoothed
Average over a window of n buckets (typically n=50):
```
VPIN(t) = (1/n) · Σ_{τ=t-n+1..t} toxicity_τ
        = avg buy/sell imbalance over recent volume window
```

### Properties
- VPIN ∈ [0, 1]
- VPIN ≈ 0: balanced flow (uninformed dominant)
- VPIN ≈ 1: extreme imbalance (informed flow concentrated)

## 3. Volume bars vs time bars — why this matters

Time bars (e.g., 1-minute) are inhomogeneous in information content:
- Quiet minute = mostly noise trades, little info
- Active minute = potentially informed trades

Volume bars **synchronize on information arrival**: each bucket has equal trade activity, so across buckets one can compare "information per unit activity". This is the **Bayesian-natural sampling**.

For us: at 100ms snapshot cadence, time bars dominate. But ACML_VOL increments give us a way to define volume buckets retrospectively from the snapshots.

## 4. Empirical findings

Easley-LdP-O'Hara test on SPY ETF (2010 Flash Crash):
- VPIN spiked from 0.4 (typical) to 0.7 (extreme) in the **30 minutes BEFORE** the May 6, 2010 Flash Crash.
- Strong predictive power for **liquidity-driven crashes**.

For our KRX project — analogous insights:
- VPIN spike before large price moves likely
- Useful as **regime gate**: avoid entering during high-VPIN periods (informed dominate, you're the uninformed counter-party)

## 5. Our proxy: trade_imbalance_signed already approximates VPIN

Our existing primitive:
```python
trade_imbalance_signed(snap, prev) = sign(Δmid) · ΔACML_VOL
```

Compare to VPIN's bucket toxicity:
```
toxicity_τ = |V_τ_B − V_τ_S| / V
```

If we aggregate `trade_imbalance_signed` over a rolling volume window (instead of rolling time window), we get the **signed version** of VPIN-like toxicity:
```
signed_VPIN_τ ≈ Σ trade_imbalance_signed in bucket τ / V
```

→ Our `zscore(trade_imbalance_signed, W)` with large W is a **proxy for VPIN volatility**. Block C primitive `B2 zscore-extreme` is essentially "high-VPIN regime detection".

## 6. Implementation plan for Chain 1

### Phase A (low cost) — direct VPIN approximation from snapshots
```python
def vpin_proxy(snaps_buffer, V_per_bucket=10000):
    """Approximate VPIN from snapshot ACML_VOL deltas.
    
    Buckets snapshots until cumulative ΔACML_VOL ≥ V_per_bucket,
    classifies each delta by mid-move direction (Lee-Ready tick rule),
    computes toxicity per bucket.
    """
    # Iterate snaps; accumulate volumes; emit toxicity_per_bucket
```

### Phase B (full) — once H0STCNT0 trade feed is available
- Use proper trade prints + Lee-Ready quote rule
- Per-trade direction is unambiguous (price relative to mid at trade time)
- Stronger VPIN estimate

### Phase C — VPIN as regime filter
```python
# In a Chain 1 spec:
formula = "obi_1 > 0.5 AND vpin_proxy(50) < 0.45"
# Direction: long_if_pos
# Rationale: enter only when toxic flow is below typical level (informed
# participation low) — our naive signal has best chance.
```

## 7. Connection to our project's findings

We observed:
- iter013 OOS +12.98 bps but post-fee -10 bps (Stage 2)
- Hypothesis: **fee absorbs naive signal value because we're being adversely selected**
- VPIN toxicity provides **a direct measure**: is the trade flow informationally driven?
- If VPIN is high during our entry → we're likely the uninformed party → expect adverse selection
- If VPIN is low → noise-dominated → our signal has fair shot

This is the **theoretical complement** to our empirical fee-vs-edge analysis. VPIN-gated entries should reduce "we entered against informed flow" cases.

## 8. Caveats

- **Bucket size V**: arbitrary parameter. Easley-LdP recommend V = 1/50 of daily vol. Different V → different VPIN scale.
- **Trade classification accuracy**: Lee-Ready tick rule has ~85% accuracy at NYSE; Korean retail-driven KRX may differ.
- **VPIN as predictor vs filter**: paper shows it predicts crashes; for our use case, it's primarily a regime gate (avoid bad regimes), not a directional signal.
- **Critique (Andersen-Bondarenko 2014)**: "VPIN: A Skeptical Look" — argues VPIN's predictive power is overstated. Reasonable rebuttal: VPIN is one of many regime indicators, not a silver bullet.

## 9. Implementation priority

- ⭐⭐⭐ For Chain 1 expansion: add `vpin_proxy(snap, prev, V)` primitive. Useful immediately.
- ⭐⭐ For Chain 2: VPIN-based dynamic spread/cancel decisions.
- ⭐ For chain2-gate: include VPIN in scoring (specs that perform under high-VPIN have stronger evidence of true edge vs noise).

## 10. Paper narrative

When citing for our `trade_imbalance_signed` and future `vpin_proxy`:
> "We integrate the volume-synchronized adverse-selection measure VPIN (Easley, López de Prado, & O'Hara, 2012) as both a signal primitive and a regime gate. Our `trade_imbalance_signed` is a per-tick approximation; the rolling z-scored variant approaches VPIN's toxicity in the limit of large window size. This provides a theoretical bridge between our naive signal-based execution and informed-trader-aware deployment."

## Related references

- Easley, Kiefer, O'Hara, Paperman (1996). Original PIN model.
- Glosten, Milgrom (1985). Theoretical π. (Already in refs.)
- Lee, Ready (1991). Trade direction. (Already in refs.)
- Hasbrouck (1991). VAR signed-volume. (Already in refs.)
- Andersen, Bondarenko (2014). Critical view of VPIN.
- López de Prado (2018). AFML Ch.19 — VPIN application to ML strategies.
