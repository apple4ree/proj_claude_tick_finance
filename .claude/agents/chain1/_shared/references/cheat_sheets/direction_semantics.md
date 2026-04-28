# Direction Semantics — When does a signal point OPPOSITE to its magnitude?

Cheat sheet for Chain 1 signal-generator. **Read this BEFORE choosing `direction` for any new SignalSpec.**

---

## Core principle

A raw primitive value `X` with **`direction=long_if_pos`** means:
```
X > threshold  →  enter LONG (expect price UP next H ticks)
X < -threshold →  enter SHORT (expect price DOWN next H ticks)
```

A primitive with **`direction=long_if_neg`** (contra) means:
```
X > threshold  →  enter SHORT (expect price DOWN)
X < -threshold →  enter LONG (expect price UP)
```

**Decision rule**: ask the physical question — what does a **large value of X** mean inside the order book right now, and what does that imply about the NEXT move?

---

## Category A — "Pressure/flow in the predicted direction" (long_if_pos)

These primitives measure **current directional imbalance**. Large X → predicted same direction.

| Primitive | Why long_if_pos |
|---|---|
| `obi_1`, `obi_3/5/10/total` | Bid > ask depth → buying pressure → price up |
| `microprice_dev_bps` (> 0) | Microprice above mid → imbalanced toward up |
| `ofi_proxy`, `ofi_cks_1`, `ofi_depth_5/10` | Net inflow on bid side → up |
| `vol_flow` (when combined with sign) | Trade flow direction |
| Raw `trade_imbalance_signed` (unscaled) | Buyer-initiated volume dominates → price rises in short term |

**Default for this category**: `long_if_pos`.

---

## Category B — "Extreme / exhaustion" (long_if_neg = contra)

Large X means a directional move **already happened** and the market is likely to **revert**. Three sub-categories:

### B1. Resistance / support walls (shape signals)

The **accumulation of limit orders on one side creates a barrier**. When pressure hits it, the barrier holds temporarily, then often the move fails.

| Primitive | Why contra |
|---|---|
| `ask_depth_concentration` large | Giant ask wall at BBO → trading pressure exhausted at wall → price **drops** after test |
| `bid_depth_concentration` large | Symmetric: bid wall → price **bounces up** (so long_if_pos in isolation; but its z-scored spike = contra) |
| Deep-book imbalance `obi_ex_bbo` large | Levels 2-5 imbalanced same direction as BBO = already over-committed → reversal imminent → **contra** |

### B2. Z-scored extreme spikes (flow signals)

When a flow metric z-scores above ~2, it means **2-sigma frenzy** — all marginal buyers/sellers already participated. No more fuel.

| Primitive | Why contra |
|---|---|
| `zscore(trade_imbalance_signed, W) > 2` | 2σ buying frenzy → exhaustion → reversion down → **contra** |
| `zscore(ofi_proxy, W) > 2` | Same logic for OFI; extreme OFI = informed trader already sent the signal → tail drops → **contra** |
| `zscore(ofi_cks_1, W)` large | Same as above |
| `zscore(ask_depth_concentration, W) > 2` | Already covered in B1; z-scoring intensifies the wall effect |

### B3. Over-leveraged deep book

Same signed pressure on BBO + deep levels means the book is **fully committed in one direction** — high risk of reversal due to weak opposing side.

| Primitive combination | Interpretation |
|---|---|
| `obi_1 + obi_ex_bbo` high (same sign) | Full book commitment → thin opposing side → reversal soon → **contra** |
| `obi_1 > 0.5 AND obi_ex_bbo < -0.2` | BBO says buy but deep-book says sell → **stall signal**, bet against BBO → **contra** |

---

## Category C — "Regime gate only, no directional bias"

These filter **when** to enter but don't dictate direction.

| Primitive | Use |
|---|---|
| `spread_bps` | Filter: enter only when tight spread |
| `rolling_realized_vol` | Filter: enter only in low-vol (trend signals) or high-vol (mean-reversion) regime |
| `minute_of_session` | Filter: enter only in certain windows (opening/closing auction zones) |
| `book_thickness` | Filter: enter only in deep books |
| `mid_px` | Generally a reference, not a direction signal |

---

## Decision tree for new primitives

When proposing a new SignalSpec with a primitive you haven't used before:

```
Is X a pressure/flow metric (directional imbalance)?
├── YES → default `direction = long_if_pos` (Category A)
│         e.g., obi_k, microprice_dev_bps, ofi_*
│
└── NO → Is X a shape / concentration / extremeness metric?
        ├── YES → default `direction = long_if_neg` (Category B)
        │         e.g., *_depth_concentration, obi_ex_bbo, zscore(flow, W)
        │
        └── NO → Is X a regime / filter metric?
                ├── YES → use as gate (Category C), direction irrelevant for this term
                │
                └── NO → uncertain. Test BOTH directions in separate specs (Category ?)
```

---

## Compound formulas — inherit semantics of dominant term

When building compounds like `A * B` or `A + c*B`:

1. Identify the **dominant** term (usually largest magnitude contributor).
2. Apply its direction category.
3. The **filter** term (Boolean multiplier like `(rvol < 30)`) does NOT change direction.

### Examples
```
zscore(ask_depth_concentration, 300) * (rvol < 30)
  → dominant: zscore(ask_conc) → Category B1/B2 → CONTRA
  → direction = long_if_neg ✓ (this is iter013)

obi_1 > 0.5 AND microprice_dev_bps > 1.0
  → both Category A → long_if_pos ✓

(obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration
  → First two Category A (pos); last Category B1 (contra, so -2× → positive contribution to long)
  → overall long_if_pos ✓ (this is iter003)

zscore(trade_imbalance_signed, 300) + 3*obi_1
  → zscore(trade_flow) Category B2 (contra when > 2)
  → 3*obi_1 Category A (pos)
  → These PARTIALLY CANCEL. Resolve by threshold choice:
     - if threshold is low (~1), obi_1 dominates → long_if_pos
     - if threshold is high (~3+), zscore dominates → long_if_neg
```

When uncertain for compounds, **submit two SignalSpecs** — one with each direction. Chain 1 backtest reveals which is actually profitable.

---

## Hard-earned cases (prior iterations)

### Confirmed CONTRA specs (long_if_neg)
| spec_id | formula | WR | exp |
|---|---|---|---|
| iter013_ask_conc_low_vol_h50 | `zscore(ask_depth_concentration, 300) * (rvol < 30)` | 0.95 | +11.3 |
| iter014_wall_break_filter | `iter013 * (zscore(trade_imb_signed, 300) < 1.0)` | 0.96 | +11.3 |
| iter012_ask_conc_low_vol | similar to iter013, H=20 | 0.94 | +11.0 |

### Confirmed LONG_IF_POS specs
| spec_id | formula | WR | exp |
|---|---|---|---|
| iter003_full_consensus_tight | `(obi_1 + obi_ex_bbo) - 2 * ask_depth_concentration` | 0.96 | +7.0 |
| iter021_bbo_divergence_low_vol | `(obi_1 - obi_ex_bbo) * (rvol < 30)` | 1.00 | +7.4 |

### Tried WRONG direction, corrected
| Primitive | Tried first | Correct (final) |
|---|---|---|
| `obi_ex_bbo` (solo) | long_if_pos | **long_if_neg** — verified B3 |
| `zscore(trade_imbalance_signed, 300)` solo | long_if_pos | **long_if_neg** — verified B2 |
| `ask_depth_concentration` | long_if_pos | **long_if_neg** — verified B1 |

---

## D4 — Multiplicative interaction patterns (NEW 2026-04-26)

Boolean compound (`A AND B`) is one form of interaction; **continuous multiplication / non-linear combinations** are another with distinct properties. The framework now allows these via expanded operator set: `sqrt`, `exp`, `log`, `log10`, `sign`, `abs`, `min`, `max`, `floor`, `ceil`, `where`.

### Pattern types

#### P1. Sign-modulated combinations
Use one primitive for direction sign, another for magnitude.
```
formula: obi_1 * sign(ofi_proxy)
```
Direction depends on **OBI strength * OFI direction agreement**. Strong OBI in same direction as OFI → strong signal. Strong OBI but opposite OFI → muted (or contra).
Direction: long_if_pos (Category A) — but only when both terms align.

#### P2. Magnitude / mismatch combinations  
```
formula: sqrt(obi_1**2 + obi_ex_bbo**2)
```
Total imbalance vector length. **Direction-agnostic magnitude**. Use with `direction = long_if_pos` and high threshold (>0.7) to detect "any large imbalance" regardless of side. Less directional but more frequent.

#### P3. Rational expressions (saturation / discount)
```
formula: obi_1 / (1 + spread_bps / 5)
```
"OBI discounted by spread width." Wide spread reduces signal magnitude. Captures the intuition: OBI in tight-spread regime is more reliable than in wide-spread regime.

```
formula: (B_total - A_total) / (B_total + A_total + 1)
```
Saturation prevented (denominator never zero). Range bounded.

#### P4. Exponential decay weighting
```
formula: obi_1 * exp(-spread_bps / 3)
```
OBI down-weighted exponentially as spread widens. Essentially a smooth version of `obi_1 * (spread_bps < threshold)`. Smoother → more trade samples (less binary cut).

#### P5. Threshold-style with where()
```
formula: where(rolling_realized_vol(mid_px, 100) > 50, obi_1, 0)
```
Same as `obi_1 * (rvol > 50)` but more readable. `where(cond, a, b)` returns `a` if cond else `b`.

### When to propose multiplicative interaction

- **Two correlated primitives** (e.g., obi_1, obi_ex_bbo): multiplication highlights agreement/disagreement.
- **Filter that varies smoothly** (vs binary cut): multiplication preserves info gradient.
- **Capacity / saturation constraint**: rational form (numerator/denominator).
- **Asymmetry concern**: sign(X)·|Y| keeps direction info from X but magnitude from Y.

### When NOT to use

- **Both primitives strong on their own**: simple AND-compound is interpretable.
- **No physical justification** for non-linearity: don't add complexity for its own sake.
- **Single-primitive sufficient** (per smoke result): multiplicative wrapper adds noise.

### Direction inheritance for multiplicative compounds

For `formula = f(A, B, ...)`, identify the **dominant-magnitude term**:
1. If formula is `A * (B<thr)` (Boolean filter) → A's category determines direction
2. If formula is `A * B` with both Category A (pressure/flow) → likely Category A (long_if_pos), but check via small backtest
3. If formula involves `abs()`, `sqrt()`, `**2` → magnitude-only → use with high threshold + Category dependence on outermost operator
4. If formula uses `sign(X)` → X's category determines direction

### Hypothesis template for multiplicative spec

```
hypothesis: "Spec multiplies obi_1 (Category A pressure) by sign(ofi_proxy) 
to require directional agreement. The product is non-zero only when both 
primitives align — capturing 'consensus pressure' more strictly than naive 
AND. Direction = long_if_pos (Category A inherited from obi_1, modulated by 
sign indicator)."
```

---

## When in doubt

If you're unsure about direction, **your spec's `hypothesis` field should state the mechanism explicitly**. Example:

```
hypothesis: "zscore(ask_depth_concentration, 300) > 5 in low-vol regime is an 
exhaustion signal (Category B1): the accumulated ask wall has absorbed all 
short-term buying pressure and the market will revert downward. Therefore 
direction = long_if_neg."
```

This forces you to justify the direction choice BEFORE measurement, making the result interpretable either way.
