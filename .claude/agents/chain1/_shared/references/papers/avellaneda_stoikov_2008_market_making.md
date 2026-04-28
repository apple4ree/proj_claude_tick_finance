# Avellaneda & Stoikov (2008) — High-frequency trading in a limit order book

**Citation**: Avellaneda, M., & Stoikov, S., "High-frequency trading in a limit order book", *Quantitative Finance* 8(3), 217–224 (2008).

## Why this matters to our project

If/when Chain 2 extends beyond single-side directional execution to **market-making** paradigm (continuous two-sided quotes), Avellaneda-Stoikov (AS) is **the** reference. It provides the first closed-form solution to the MM dealer's problem under a simple (and tractable) set of assumptions:

- Mid price follows Brownian motion `dS = σ·dW`
- Market-maker quotes bid `p_b` and ask `p_a`
- Bid order arrives as Poisson with intensity `λ^b = A·exp(-k·(p_a − S))` — similar for ask
- MM has inventory q, wants to minimize variance × risk aversion

## 1. Core formulas

### Reservation price (indifference price)
```
r(s, q, t) = s − q · γ · σ² · (T − t)
```
- `s` = current mid
- `q` = current inventory (long = positive)
- `γ` = risk aversion
- `T − t` = time to horizon
- **When we're long (q>0)**: r < s, we'd like to sell (fair value shifted down)
- **When we're short (q<0)**: r > s, we'd like to buy

### Optimal half-spread
```
δ = γ · σ² · (T − t) / 2 + (1/γ) · ln(1 + γ/k)
```

Two terms:
1. **Inventory-risk term**: `γσ²(T−t)/2` — proportional to volatility × risk aversion × remaining horizon
2. **Adverse-selection term**: `(1/γ)·ln(1 + γ/k)` — depends on order-arrival sensitivity k

### Bid/ask quotes
```
p_b = r − δ     (post bid below reservation)
p_a = r + δ     (post ask above reservation)
```

**Key property**: As inventory accumulates, `r` shifts, causing asymmetric quotes:
- Inventory long → r < s → p_a < s + δ (sell faster) and p_b < s − δ (buy slower)
- Net effect: **MM uses skew to mean-revert inventory**

## 2. Dimensional analysis for our project

Typical KRX values to plug in:

| Symbol | σ (bps/sec) | k (arrival sensitivity) | γ (risk aversion) | T (horizon) | δ optimal |
|---|---|---|---|---|---|
| 005930 | ~15 bps/sec | ~1.0 (empirical fit needed) | 1e-4 to 1e-2 (user) | 60 sec | ~5-15 bps |

For γ = 1e-3, σ = 15 bps/sec, T − t = 60 sec:
- Inventory term: `1e-3 × 15² × 60 / 2 = 6.75 bps` (per unit of q)
- Adverse-selection term: `(1/1e-3) × ln(1 + 1e-3/1) ≈ 1.0 bps`
- Total δ ≈ **7.75 bps half-spread, so full quote spread ≈ 15.5 bps**

→ AS-optimal spread is **wider** than KRX observed market spread (~5-10 bps). This suggests retail MMs on KRX operate at lower γ or shorter T, OR compete aggressively below AS-optimum (thin margin).

## 3. Extensions (Cartea, Jaimungal, Penalva 2015)

Since AS 2008, many improvements:

### Ornstein-Uhlenbeck midprice
Replace `dS = σdW` with mean-reverting `dS = θ(μ−S)dt + σdW`. Closer to real HF price. Gives different optimal δ.

### Finite inventory bounds
Add `|q| ≤ q_max` constraint. δ becomes inventory-dependent with kinks.

### Fill probability model (Cont-Kukanov-Stoikov 2017)
Instead of `λ = A·exp(-kδ)`, use empirical queue-length-based fill probability.

### Alpha-signal integration (Cartea-Jaimungal 2015)
Augment reservation price with short-term predictor α:
```
r = s + c·α − q·γ·σ²·(T−t)
```
This is **the Chain 1 × Chain 2 integration point**: our SignalSpec provides α.

## 4. Connection to our Chain 2 roadmap

### Phase 2.3 (current): directional only
We have `order_type = MARKET / LIMIT_AT_BID`. AS not yet applicable (no simultaneous bid+ask).

### Phase 2.4+: MM extension (future)
If Chain 2 grows to market-making:
1. Introduce `ExecutionMode = {"directional", "market_making"}` enum
2. For MM mode, use AS-style reservation price:
   ```
   r = mid + alpha_contribution − inventory_skew_term
   ```
3. Chain 2's search space grows to include γ, quote cadence, inventory cap

### Current LIMIT_AT_BID usage
Our current LIMIT_AT_BID is **one-sided directional maker** (post bid, cross with ask when triggered). This is **not MM** — just maker-style directional. AS would inform:
- How wide to post (δ optimal given σ, γ)
- Whether to skew if any residual inventory from prior signal

## 5. Limitations

- **Homogeneous Poisson assumption**: arrivals are not actually exponential in our data (bursty).
- **Linear risk aversion**: real traders are more risk-averse at extremes (Kelly-like).
- **No adverse selection detection**: AS treats all fills equally, doesn't model informed vs uninformed.
- **Solo-trader assumption**: in practice, competing MMs react. Game-theoretic MM (He 2018) extends.

## 6. For immediate use

### Pragmatic simplification
We can use AS **just for time-to-hold calibration** without full MM:

```python
def as_inventory_half_life(sigma_bps_per_sec, gamma, inventory):
    """Time over which inventory-induced price bias decays in AS framework."""
    # Related to 1 / (γ·σ²) — the natural decay scale
    return 1.0 / (gamma * sigma_bps_per_sec ** 2)
```

This gives a **natural time scale** for how long inventory should be held before it "needs" liquidation. Can feed into Chain 2's `time_stop_ticks`.

### Full MM framework (Chain 2.4+)
Delegate to `hftbacktest`'s MM example notebook which implements AS-style quoting.

## 7. Related work

- Guéant, O., Lehalle, C.-A., Fernandez-Tapia, J. (2013). "Dealing with the Inventory Risk: A Solution to the Market-Making Problem." GLFT — better than AS for inventory constraint binding.
- Cartea, Á., Jaimungal, S., Penalva, J. (2015). *Algorithmic and High-Frequency Trading* Ch.10. Modernized AS derivation.
- Fodra, P., & Pham, H. (2015). "Semi-Markov model for market microstructure." Adds regime switching.
- Stoikov, S. (2018). *Microprice* (see existing `stoikov_2018_microprice.md`). Updates fair value model.
