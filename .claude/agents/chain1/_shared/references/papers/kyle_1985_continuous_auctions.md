# Kyle (1985) — Continuous Auctions and Insider Trading

**Citation**: Kyle, A. S., "Continuous auctions and insider trading", *Econometrica* 53(6), 1315–1335 (1985).

## Why this matters to our project

Kyle's model is the **canonical formalization of adverse selection in markets**. It proves that when informed traders interact with market makers through a continuous auction, prices move linearly with net order flow — this linearity is Kyle's lambda (λ). Our Chain 2 `execution_runner.py` measures `adverse_selection_cost_bps` empirically; Kyle gives the theoretical ground truth of what this cost is *supposed* to be.

## 1. Model setup

Three agents:
- **Insider** (informed): knows terminal liquidation value `v ~ N(p₀, Σ₀)`
- **Noise traders** (uninformed): random order flow `u ~ N(0, σ_u²)`
- **Market maker** (rational, zero profit): sets price based on aggregated order flow

### One-period setup
- Insider submits order `x` (strategic)
- Noise traders submit `u` (exogenous)
- MM observes **total flow** `y = x + u` (cannot distinguish insider from noise)
- MM sets price `p = E[v | y]`

### Insider's problem
Maximize `E[(v − p) · x]` — expected profit.

### Equilibrium solution
```
x* = β·(v − p₀)   where β = √(σ_u² / Σ₀)
p = p₀ + λ·y      where λ = √(Σ₀ / σ_u²) / 2
```

**Kyle's lambda**: `λ = √(Σ₀ / σ_u²) / 2`
- `Σ₀`: variance of asset value (terminal uncertainty)
- `σ_u²`: variance of noise order flow

**λ has units of price per unit order flow** — e.g., "price moves X bps per 1,000 shares of net flow".

## 2. Continuous-time extension (Kyle 1985 §3)

Over continuous time, insider reveals info gradually. Key result:
```
dp_t = λ·(dX_t + dU_t) = λ·dy_t
```

Price moves linearly with cumulative order flow. **Adverse selection is permanent**.

## 3. Connection to our project

### 3.1 Our adverse_selection_cost_bps
```python
# In execution_runner.py
adv_bps = -(mid[i_fill+1] − mid_fill) / mid_fill * 1e4 * direction
```
This measures: after we fill, does mid move against us in 1 tick?

Under Kyle's framework:
- If we are a noise trader (random timing), `E[adv_bps] = 0` (symmetric)
- If we are an informed-ish trader (Chain 1 signal provides prediction), `E[adv_bps] < 0` (mid moves WITH us)
- If market is efficient and others know more, `E[adv_bps] > 0` (we lose to others' info)

### 3.2 Empirical check from our data
Chain 2 Stage A S1 baseline on iter013 reported:
```
adverse_sel (signed) = -0.94 bps
```
→ Slight **negative adverse selection** (mid moves slightly with us 1 tick after fill). Consistent with our signal having marginal predictive value at 1 tick.

### 3.3 Kyle's λ for KRX 005930

Rough order-of-magnitude estimate:
- Daily σ of mid (intraday) ≈ 50 bps
- Daily volume ≈ 1M shares (200B KRW at price 200K)
- If noise flow σ_u ≈ 60% of daily volume = 600K shares
- Σ₀ (daily value variance) ≈ (0.005 × 200K)² = 1e6 KRW²
- λ ≈ √(1e6 / 600K²) / 2 ≈ 4e-4 KRW per share traded

→ For 1000-share order: price moves ~0.4 KRW = 0.2 bps. Seems small because KRX 005930 is extremely liquid.

### 3.4 For market-making extension (Chain 2.4+)
AS spread formula includes adverse-selection term. Kyle's λ calibrates it:
```
AS half-spread = (Kyle's λ) · E[expected_signed_flow] + inventory_term
```

## 4. Extensions and refinements

### 4.1 Glosten-Milgrom (1985)
Concurrent paper, **binary** version: each trade is either buy or sell, traders can be I (informed) with probability π or U (uninformed). See `glosten_milgrom_1985_bid_ask_spread.md`.

### 4.2 Multi-period (Back 1992, Back-Baruch 2004)
Insider accumulates position optimally. Price discovery path smooth, monotone in cumulative flow.

### 4.3 Stoikov-Saglam (2009)
Kyle extended with **limit orders** (not just market orders). Relevant for our LIMIT_AT_BID decisions.

### 4.4 High-frequency Kyle (Cartea-Jaimungal 2015 §11)
Microstructure version: instead of single insider, ∞ HFT traders competing. Price impact becomes:
```
λ_HFT = λ_Kyle · (1 + competition_factor)
```
In heavily HFT'd markets, λ is smaller (competition drives impact toward zero but volatility higher).

## 5. Implementation priorities

### Near-term (Chain 2.1)
Add to `chain2/cost_model.py`:
```python
def estimate_kyle_lambda(
    mid_variance_bps: float,
    noise_flow_std_shares: float,
    horizon_seconds: float = 1.0,
) -> float:
    """Kyle's λ estimate — price impact per share of order flow, bps/share."""
    import math
    return 0.5 * math.sqrt(mid_variance_bps ** 2 * horizon_seconds) / noise_flow_std_shares
```

### Longer-term
- Fit Kyle's λ empirically from our KRX LOB data (pre-compute per-symbol)
- Use λ as ex-ante expected adverse-selection cost in ExecutionSpec validation

## 6. Limitations

- **Rational MM assumption**: real MMs are often inventory-constrained / myopic.
- **Normal distribution of v**: tail risks underestimated.
- **Single informed trader**: HFT-era markets have many competing informed.
- **Static**: Kyle's one-shot equilibrium doesn't capture regime shifts.

## 7. Why this paper is foundational

Kyle 1985 + Glosten-Milgrom 1985 together created the modern microstructure literature. Every subsequent HFT/MM paper cites one of these. The two papers are **complementary**:

- **Kyle**: continuous-flow model, adverse selection as a function of total flow
- **Glosten-Milgrom**: discrete-event model, binary bid-ask spread = pure adverse selection

For us, **Kyle gives the impact mechanism** (λ), **Glosten-Milgrom gives the spread consequence** (how bid-ask widens).

## Related references

- Glosten, L. R., & Milgrom, P. R. (1985). Companion. `glosten_milgrom_1985_bid_ask_spread.md`.
- Back, K. (1992). "Insider trading in continuous time." *RFS*. Extends to continuous time rigorously.
- Hasbrouck, J. (1991). Measures information content per trade. `hasbrouck_1991_information_content.md`.
- Cartea, Á., Jaimungal, S., Penalva, J. (2015). *Algorithmic and High-Frequency Trading* Ch.5 for modern exposition.
