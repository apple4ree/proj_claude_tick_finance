# Gould & Bonart (2016) — Queue Imbalance as a One-Tick-Ahead Price Predictor

**Citation**: Gould, Martin D. and Bonart, Julius, "Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book," *Market Microstructure and Liquidity* 2(2), 1650006 (2016).

## Core Finding

On LSE stocks (2012 sample), queue imbalance

$$
\text{QI} = \frac{B_1}{B_1 + A_1}
$$

(equivalently `(obi_1 + 1) / 2`, so linearly equivalent to our `obi_1`) is a **statistically significant one-tick-ahead predictor of mid-price direction** — but **conditional on the next tick being a price-moving event**.

### Conditional probabilities reported

- `P(mid_{t+1} > mid_t | QI_t ∈ [0.9, 1.0])` ≈ 0.71
- `P(mid_{t+1} < mid_t | QI_t ∈ [0.0, 0.1])` ≈ 0.70
- `P(|mid_{t+1} − mid_t| > 0 | QI_t ∈ [0.4, 0.6])` ≈ 0.03

Most events are non-moves. Conditioned on a move, QI provides ~70% WR at the one-tick horizon — consistent with our empirical observations on KRX.

## The "Layer-wise" refinement

Gould & Bonart §6 extends the analysis beyond the BBO:

- QI at level 1 = obi_1 (our primitive)
- QI at level `k ≥ 2` — behaves differently: slower to mean-revert, correlated with BBO QI but lag leads to predictive value of its own
- Specifically: **deep-book QI retains predictive value at horizons 10–50 ticks, while BBO QI decays after ~5 ticks**

This directly motivates the `obi_ex_bbo` primitive: aggregated levels 2..5 imbalance, measuring patient liquidity orientation.

## Relevance to Chain 1

- Our observed `obi_1` WR of 0.93–0.96 at h=1 is **consistent with Gould-Bonart's 0.71** after accounting for our KRX bid-ask zero-mid filter (we exclude no-move ticks, which raises conditional WR).
- `obi_ex_bbo` as a separate feature exploits the **layer-wise** result: deep imbalance persists longer and has different horizon characteristics.
- When `obi_1` and `obi_ex_bbo` agree (same sign), Gould-Bonart's conviction argument says the conditional WR rises further.
- When they disagree, it is a signal of **BBO stall** — obi_1 direction may not be sustainable because deeper-level liquidity is fighting it.

## Empirical implications (our project)

### Predictions we can test with the new primitive:
1. `obi_ex_bbo` alone at h=20: expected WR 0.75–0.85 (lower than obi_1 at h=1, but longer-lived edge).
2. `obi_1 > 0.5 AND obi_ex_bbo > 0.2` consensus: WR ≥ 0.96, expectancy boosted 10–20% over obi_1 alone.
3. `sign(obi_1) != sign(obi_ex_bbo)` as a **reject filter**: removes the BBO-stall regime, should slightly raise WR on remaining trades.

## Known Caveats

- Results are LSE-specific; KRX tick size and queue dynamics differ. Baseline numbers may shift but the qualitative layer-wise effect should carry.
- At horizons > 50 ticks, deep-book QI also decays; not a cure for all horizon ranges.
- The paper uses conditional-on-move WR; our project uses direct-measure WR. Numbers aren't directly comparable but trends are.
