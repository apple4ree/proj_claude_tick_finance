# Bouchaud, Mézard & Potters (2002) — Statistical Properties of Stock Order Books

**Citation**: Bouchaud, J.-P., Mézard, M., and Potters, M., "Statistical properties of stock order books: empirical results and models," *Quantitative Finance* 2(4), 251–256 (2002).

## Core Empirical Findings

The paper measures the **time-averaged shape** of the limit order book using high-frequency data from Paris Bourse (CAC 40 stocks) and NASDAQ. Three main results:

### 1. Depth profile is NOT uniform

The average resting volume at relative price offset `Δ` (ticks away from BBO) follows

$$
\rho(\Delta) \sim \Delta^{\alpha} \quad \text{with } \alpha \in [0.6, 1.2]
$$

This is a **hump-shaped** profile: peak volume sits a few ticks **behind** the BBO, not at the BBO itself. The BBO is typically thin because HFT queue-jockeying constantly displaces it.

### 2. Shape parameter varies by stock

- Thick-book, low-volatility names: `α ≈ 1.0` (smooth distribution)
- Thin-book, fast-moving names: `α ≈ 0.6` (front-loaded BBO, fragile)

### 3. Shape is information-bearing

Conditional on informed flow arriving (e.g., ahead of earnings), the shape becomes **more front-loaded** — BBO fills, hump flattens. This is a detectable regime change.

## Relevance to Chain 1

The `bid_depth_concentration` and `ask_depth_concentration` primitives directly exploit this shape axis:

- `B_1 / total_bid` = BBO-concentration ratio on bid side
- High values (> 0.30 on KRX large caps) indicate **front-loaded state** → informed trader likely, expect faster directional move
- Low values (< 0.10) indicate **classic hump-shaped book** → patient liquidity dominant, expect mean reversion

### Difference from OBI

OBI (obi_1) is a **cross-sectional** measure between sides at level 1. Book shape (`depth_concentration`) is a **per-side** measure of distribution across depth levels. They are mathematically independent — you can have OBI = 0 with bid_depth_concentration = 0.8 (front-loaded on both sides) or OBI = 0.8 with bid_depth_concentration = 0.1 (directionally imbalanced but liquidity deep on both sides).

## KRX adaptation notes

- KRX tick size varies with price band (1 KRW for <2,000, up to 1,000 KRW for ≥500,000) → concentration is slightly scale-dependent. Works well for 005930 (tick ≈ 100 KRW, ~5.5 bps) and similar large caps.
- Opening-auction period produces extreme concentration values (total_bid near zero). Filter with `total_bid_qty > 1000`.

## Known Caveats

- **Hidden iceberg orders**: shape measure only sees visible queue. Large icebergs dilute the signal.
- **Shape changes slowly**: do not expect tick-to-tick prediction. Useful at horizons ≥ 20 ticks.
- **Cross-symbol**: α is symbol-specific. Thresholds like "> 0.30" need per-symbol tuning or z-scoring.
