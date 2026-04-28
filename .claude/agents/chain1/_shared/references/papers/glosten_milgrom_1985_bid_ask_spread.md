# Glosten & Milgrom (1985) — Bid, Ask and Transaction Prices in a Specialist Market with Heterogeneously Informed Traders

**Citation**: Glosten, L. R., & Milgrom, P. R., "Bid, ask and transaction prices in a specialist market with heterogeneously informed traders", *Journal of Financial Economics* 14(1), 71–100 (1985).

## Why this matters to our project

Glosten-Milgrom (GM) is the **theoretical anchor for bid-ask spread**. While Kyle's continuous-flow model shows price impact linear in aggregate flow, GM's discrete-event model shows **why the spread exists in the first place**. For our Chain 2:

1. Explains why `spread_cost_bps ≈ 5-10 bps` on KRX 005930 isn't arbitrary — it's the equilibrium compensation for adverse selection.
2. Decomposes spread into **adverse-selection component** vs **order-processing component** — directly relevant to Chain 2 cost_breakdown.
3. Provides theoretical basis for **zero-profit market maker** pricing used in `hftbacktest`.

## 1. Model setup

### Players
- **Specialist (MM)**: quotes bid p_b and ask p_a. Zero-profit (competitive).
- **Trader** arrives one at a time, picks buy (at p_a) or sell (at p_b).
- Trader is **Informed (I)** with probability π, **Uninformed (U)** with probability 1−π.
- Value `V` is uncertain, currently with posterior distribution.
- Informed knows actual V. Uninformed trades for liquidity (random).

### Sequence
1. MM posts p_b, p_a
2. Trader type is realized (I or U)
3. Trader picks action (buy, sell, or no trade) based on type + V
4. Spread is updated using Bayesian inference on observed action

### Key equilibrium condition
```
p_a = E[V | buy]   (expected value conditional on observing a buy order)
p_b = E[V | sell]
```

Zero-profit ⟹ MM sets quotes = expected values conditional on trade direction.

## 2. Spread formula

After Bayesian updating, with 2-state value V ∈ {H, L} (prior prob each = 0.5):

```
p_a − V̄ = (π / (1 + π)) · (H − V̄)
V̄ − p_b = (π / (1 + π)) · (V̄ − L)
```

**Spread half-width**:
```
δ = (π / (1 + π)) · (H − L) / 2
```

### Adverse-selection component (bps)
```
AS_spread = π · volatility_bps_per_trade
```

Direct interpretation: **spread is proportional to probability of informed trader × value uncertainty per trade**.

## 3. Three-component spread decomposition

Extension of GM (Stoll 1989, Huang-Stoll 1997) decomposes spread:

```
spread_total_bps = order_processing_bps + inventory_bps + adverse_selection_bps
```

| Component | Size (typical HFT) | Driver |
|---|---|---|
| Order processing | ~0.5 bps | Fixed infrastructure |
| Inventory | 0 ~ 3 bps | Depends on MM's inventory position |
| **Adverse selection** | 2 ~ 10 bps | Proportional to π × σ (GM formula) |

**For KRX 005930**:
- Typical spread ≈ 5-7 bps (from our data)
- Our `spread_cost_bps` in cost_breakdown averages ~9.5 bps (= spread entry half + exit half, taker route)
- → Implies one-way spread ≈ 4.75 bps
- → GM decomposition would attribute ~0.5 processing + ~1 inventory + ~3.3 adverse-selection

## 4. Connection to our Chain 2 cost_breakdown

Currently `CostBreakdown`:
```python
spread_cost_bps: float     # = entry_half + exit_half if taker
maker_fee_cost_bps: float  # fixed 1.5 bps
taker_fee_cost_bps: float  # fixed 1.5 bps
sell_tax_cost_bps: float   # fixed 20 bps (KRX)
adverse_selection_cost_bps: float  # measured
```

### Gap: `spread_cost_bps` lumps all 3 GM components together
- Our measurement: we pay half-spread crossing at taker entry/exit
- Implicit attribution: **100% order-processing** (no inventory consideration, no adverse-selection-in-spread separation)

Ideally (per GM):
```python
adverse_selection_from_spread_bps = pi_informed_estimate * σ_bps_per_trade
order_processing_from_spread_bps = spread_cost_bps - adverse_selection_from_spread_bps
```

This would let us separate "cost we pay because MM charges AS" vs "cost we pay as AS-victim" (our current `adverse_selection_cost_bps` is the latter).

### When this matters
- If we ever act as MM (Chain 2.4+), we need to know which component of spread we can **earn** vs **lose**.
- For directional entry (current Chain 2), the combined spread_cost suffices.

## 5. Our project's key insight from GM

### iter013 contra-directional explanation
Our iter013 signal is `zscore(ask_depth_concentration, 300) * (rvol < 30)` with direction=long_if_neg.

**GM interpretation**:
- Large ask_depth_concentration = many traders posting sell limits near BBO
- **Why would many traders sell simultaneously?** Probably because they see bad news (informed sellers).
- GM predicts: **MM should widen spread** defensively when sell-side depth builds.
- Aggressive taker buyer (us going long) = adversely selected.
- ∴ Selling (going short) when we see the signal is correct — we are not the adversely-selected trader, **we are trading with the informed side**.

This is a **rigorous rationale** for the direction=long_if_neg convention on shape primitives — it aligns us with informed flow.

## 6. Empirical calibration

GM's π (probability of informed trader) is **unobservable**. Empirical proxies:

### PIN (Probability of Informed Trading) — Easley, Kiefer, O'Hara, Paperman (1996)
Fit EKOP model: joint distribution of buy/sell trade counts in a day. Recover π_informed.

For KRX 005930, PIN estimates typically in **π ∈ [0.10, 0.25]** range (large caps have lower π).

### Simpler: VPIN (Easley, López de Prado, O'Hara 2012)
Volume-bucketed signed flow; toxicity metric. Could be added as a future Block D primitive.

## 7. Limitations

- **Binary value**: actual value distribution continuous; GM's 2-state is simplification.
- **Single-unit trades**: trade size is 1; real trades have variable sizes → interactions with inventory.
- **Static π**: in reality π varies intraday and across regimes.
- **Zero-profit MM assumption**: real MMs are capacity-constrained, reverse-engineered GM strategies.

## 8. Implementation thoughts

### Near-term (Phase 2.2+)
Add to cost_model.py:
```python
def gm_spread_decomposition(spread_cost_bps: float, pi: float, sigma_bps: float) -> dict:
    """Rough GM-style decomposition of observed spread cost."""
    as_component = pi * sigma_bps
    op_component = max(0.0, spread_cost_bps - as_component)
    return {
        "adverse_selection_spread_bps": as_component,
        "order_processing_bps": op_component,
    }
```

### Long-term
Fit VPIN per symbol / per regime to get data-driven π. Use in Chain 2 ExecutionSpec validation ("this signal is unrealistic in high-π regime").

## Related references

- Kyle, A. S. (1985). Continuous-flow counterpart. See `kyle_1985_continuous_auctions.md`.
- Easley, D., & O'Hara, M. (1987). "Price, trade size, and information in securities markets." Extends GM to variable size.
- Stoll, H. R. (1989). "Inferring the components of the bid-ask spread: Theory and empirical tests." Three-component decomposition.
- Huang, R. D., & Stoll, H. R. (1997). "The components of the bid-ask spread: A general approach." Unified model.
- Easley, López de Prado, O'Hara (2012). "Flow toxicity and liquidity in a high-frequency world." VPIN. Modern GM-π estimator.
