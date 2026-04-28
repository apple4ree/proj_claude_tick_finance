# Hasbrouck (1991) — Measuring the Information Content of Stock Trades

**Citation**: Hasbrouck, J., "Measuring the information content of stock trades", *Journal of Finance* 46(1), 179–207 (1991).

## Why this matters to our project

Hasbrouck 1991 is the **empirical counterpart** to Kyle's theoretical model. It operationalizes "how much does each trade actually move the price?" using a Vector Autoregression (VAR) on quote revisions and trade directions. For us:

1. It is the **foundational reference for `trade_imbalance_signed`** (our Block C primitive).
2. It gives the method for cross-symbol **lead-lag analysis** — essential if we add cross-symbol primitives.
3. It separates **permanent (informational)** vs **transient (order-processing)** impact.

## 1. VAR model setup

Define two time series:
- `r_t` = midprice return at tick t (in bps)
- `x_t` = signed trade volume at tick t (Lee-Ready classified; our `trade_imbalance_signed`)

The VAR:
```
r_t = Σ_{k=1..p} (a_k · r_{t-k} + b_k · x_{t-k}) + v_{1,t}
x_t = Σ_{k=1..p} (c_k · r_{t-k} + d_k · x_{t-k}) + v_{2,t}
```

Innovations `v_{1,t}` (return shocks) and `v_{2,t}` (flow shocks) are assumed uncorrelated over time but contemporaneously correlated.

## 2. Information content measures

### 2.1 Trade impact (primary)
Impulse response of `r` to a unit shock in `x`:
```
IR_r_from_x(h) = ∂ E[r_{t+h} | v_{2,t} = 1] / ∂ v_{2,t}
```

**Long-run impact**:
```
IR_r_from_x(∞) = Σ_{h=0..∞} IR(h)  — this is the PERMANENT component
```

### 2.2 Information share (IS)
For two price series (e.g., two symbols), decompose **common factor variance**:
```
IS_i = (f_i · σ_i)² / Σ_j (f_j · σ_j)²
```
where `f_i` is the i-th column of the VAR's long-run multiplier matrix, `σ_i` is innovation variance.

**Interpretation**: IS_i = fraction of price discovery that originates in symbol i.

**For our project (cross-symbol lead-lag)**:
- If IS_005930 = 0.7 and IS_000660 = 0.3, Samsung leads Hynix.
- Primitive `cross_symbol_obi_lag1` becomes empirically justified when IS is concentrated.

## 3. Our `trade_imbalance_signed` primitive in Hasbrouck's framework

Our primitive is effectively `x_t` in the VAR. Key interpretations:

### 3.1 Why smoothing matters
Single-tick `x_t` is noisy. In Hasbrouck's VAR, the **cumulative flow** contributes most to long-run impact:
```
Permanent impact ∝ Σ x_{t-k} (cumulative signed flow)
```

Our `rolling_mean(trade_imbalance_signed, 50)` or `zscore(trade_imbalance_signed, 300)` is a crude version of this cumulative term.

### 3.2 Why zscore > raw for us
The contemporaneous VAR innovation `v_{2,t}` has zero mean and time-varying variance. Dividing by rolling std (zscore) approximates **normalized innovations**, making the threshold meaningful across regimes.

Hasbrouck's empirical finding: **z-scored trade flow** has much more consistent predictive power for mid moves than raw flow.

### 3.3 Sign of impact
For NYSE stocks (Hasbrouck's sample), `b_0` (immediate impact coefficient) is positive: signed buy → mid up.

**But we found**: iter005 `zscore(trade_imbalance_signed, 300)` with direction=**long_if_neg** (contra) worked better. Why?
- Zscore > 2 means **extreme buying spike** in the last 30s
- At 50-tick (5-second) horizon, post-extreme-spike reversion dominates
- Hasbrouck's 1-minute impact is different from our 5-second reaction

Rule of thumb: at horizons **much shorter than mean trade inter-arrival time**, reversion dominates. At **longer horizons**, permanent impact dominates.

## 4. For our framework

### 4.1 Verify direction via VAR fit
For each new primitive, we can fit Hasbrouck's VAR on historical KRX data and read off the sign of the immediate impact coefficient. This replaces empirical direction discovery with principled estimation.

```python
def fit_hasbrouck_var(returns: np.ndarray, signed_flow: np.ndarray, p: int = 5):
    """Fit p-th order VAR and return permanent impact of flow on return."""
    from statsmodels.tsa.vector_ar.var_model import VAR
    data = np.column_stack([returns, signed_flow])
    model = VAR(data)
    result = model.fit(p)
    # impulse response at ∞
    irf = result.irf(periods=200)  
    return irf.lr_effects[0, 1]  # return response to flow shock, long-run
```

### 4.2 Cross-symbol lead-lag primitive
Implementation sketch:
```python
# In primitives.py
def cross_symbol_signed_flow_lag(snap, lag_ticks: int, leader_symbol: str):
    """Look up leader_symbol's trade_imbalance_signed `lag_ticks` ago.
    
    Requires joint snapshot data (multiple symbols synchronized).
    """
    ...
```

This adds a **multi-symbol dimension** to our signal space — Chain 1 explicitly deferred to Phase D+ but Hasbrouck's VAR is the academic basis.

## 5. Empirical regularities (Hasbrouck's findings on NYSE)

1. **~25-45% of mid variance** is trade-flow-explained (symbol-dependent)
2. **~60% of permanent impact** from trades is delivered within 10 minutes
3. **Large trades have disproportionate info content** — but nonlinear; beyond top 5% they saturate

For our KRX equivalent, we'd need to fit the VAR on 005930 trade data. Expected numbers:
- Mid variance from flow: probably 20-35% (large-cap Korean stocks)
- Impact half-life: likely 1-3 minutes for 005930

## 6. Limitations

- **VAR linearity**: reality has threshold effects (small flow = no impact, big flow = square-root impact per Bouchaud).
- **Contemporaneous correlation handling**: Cholesky ordering of innovations is arbitrary; can flip interpretation. Hasbrouck uses "trade-first" ordering; some prefer "quote-first".
- **Requires clean trade-sign classification**: our Lee-Ready tick rule has ~85% accuracy; errors bias β downward.
- **Stationarity**: VAR assumes no regime shifts; 1-day fits are ok; multi-day needs more care.

## 7. For paper narrative

When citing this for our `trade_imbalance_signed` primitive:
> "Following Hasbrouck (1991), we use signed volume (Lee-Ready classification) to capture the information content of trades. The z-scored rolling aggregate approximates the innovation to cumulative signed flow, which is informationally equivalent to the VAR's permanent impact component."

## Related references

- Lee, C. M. C., & Ready, M. J. (1991). Tick rule for trade classification. `lee_ready_1991_tick_rule.md`.
- Kyle, A. S. (1985). Theoretical source. `kyle_1985_continuous_auctions.md`.
- Hasbrouck, J. (1995). "One security, many markets: Determining the contributions to price discovery." *JF* 50(4). Extends IS decomposition to multiple venues.
- Cont, R., Kukanov, A., Stoikov, S. (2014). OFI paper. Same spirit, uses quote rather than trade innovations.
