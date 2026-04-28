# Advanced Microstructure — Block C (2026-04-21)

Primitives beyond the OBI/OFI/microprice cluster. Each one exposes an
information channel that is **structurally orthogonal** to the OBI family,
so specs built from these can yield edge in regimes where pure OBI saturates.

> **Rule**: any Chain-1 SignalSpec using a primitive listed here must cite
> this file in its `references` list. Primitives are already added to
> `chain1/primitives.PRIMITIVE_WHITELIST` and accepted by signal-evaluator.

---

## Notation (same as obi_family)

- `B_k`, `A_k` — bid/ask quantity at level k (1-indexed)
- `Pb_k`, `Pa_k` — bid/ask price at level k
- `mid_t = (Pb_1 + Pa_1) / 2` at tick t
- `total_bid` = TOTAL_BIDP_RSQN, `total_ask` = TOTAL_ASKP_RSQN
- Δ prefix indicates difference from previous tick (stateful, needs `prev`)

---

## 1. Trade-flow primitives <a name="trade_flow"></a>

OBI and OFI both reflect **book state** (who is resting where). The trade-flow
axis reflects **who actually traded** and in which direction — a fundamentally
different information channel (Lee-Ready 1991, Hasbrouck 1991).

### `trade_imbalance_signed(snap, prev)` — stateful

**Classification (Lee-Ready tick rule):**
```
ΔV = ACML_VOL_t − ACML_VOL_{t-1}   (shares traded this tick)

if mid_t > mid_{t-1}:        signed = +ΔV     (buyer-initiated, uptick)
elif mid_t < mid_{t-1}:      signed = −ΔV     (seller-initiated, downtick)
else:                        signed = 0       (unclassified; zero-change)
```

**Usage**: single-tick values are noisy. Smooth with rolling helpers:
- `rolling_mean(trade_imbalance_signed, 50)` → 5-second signed flow (50 × 100ms)
- `zscore(trade_imbalance_signed, 300)` → 30-second standardized flow

**Why it's different from OFI**:
- OFI (`ofi_cks_1`) = book-state change (queue mutations)
- Trade imbalance = **realized trades** with Lee-Ready sign. Includes only
  ticks where `ACML_VOL` actually moved. Immune to "phantom" OFI from cancel
  storms.

**Paper ref**: `../papers/lee_ready_1991_tick_rule.md`

---

## 2. Book-shape primitives <a name="book_shape"></a>

OBI captures directional imbalance but discards *shape* info — how liquidity
is distributed across depth levels. Two books with identical OBI can have
very different microstructure: one with all size at BBO (fragile), another
with smooth distribution across 5 levels (deep).

### `bid_depth_concentration(snap)` — stateless

```
bid_depth_concentration = B_1 / total_bid    ∈ [0, 1]
```
- 1.0 = all bid-side size sitting at BBO (front-loaded, aggressive)
- 0.0 = BBO empty / size spread across deeper levels
- Typical KRX regular session: 0.05 ~ 0.20

### `ask_depth_concentration(snap)` — stateless

Mirror of the bid version. Identical semantics, ask side.

### Suggested use
- **Fragility filter**: `bid_depth_concentration > 0.30` = BBO-heavy, prone to
  fast dismissal on small trade. Probably avoid long entries during these
  states.
- **Informed vs noise** (per Bouchaud 2002): deep, smooth book = more
  informed traders waiting; concentrated BBO = mostly HFT queue jockeying.
- **Combined**: `obi_1 > 0.5 AND bid_depth_concentration < 0.15` — strong
  directional imbalance WITH patient bid-side liquidity behind it.

**Paper ref**: `../papers/bouchaud_mezard_potters_2002_book_shape.md`

---

## 3. Deep-book imbalance <a name="deep_book"></a>

### `obi_ex_bbo(snap)` — stateless

```
obi_ex_bbo = (Σ_{k=2..5} B_k − Σ_{k=2..5} A_k) /
             (Σ_{k=2..5} B_k + Σ_{k=2..5} A_k)    ∈ [−1, 1]
```

Same structural formula as `obi_5` but **excluding level 1**. The intuition:

- **obi_1** is dominated by HFT-speed BBO churn (cancelations, re-posts,
  queue jockeying) — short-lived, noisy, but fast to react.
- **obi_ex_bbo** captures orientation of the "patient" liquidity — orders
  that survived BBO and remain 1-4 ticks away. This reflects mid-term
  directional conviction of quiet market makers and slower algos.
- They are **correlated but not redundant**: obi_1 = +0.7 while obi_ex_bbo
  = −0.2 is a stall signal; BBO says long but the deeper book is loaded for
  a reversal. A conviction filter is
  `sign(obi_1) == sign(obi_ex_bbo) AND |obi_ex_bbo| > 0.2`.

### Suggested use
- **Strong conviction entry**: `obi_1 > 0.5 AND obi_ex_bbo > 0.2` —
  front-of-book and behind-the-line both agree.
- **Reversal detector**: `obi_1 > 0.5 AND obi_ex_bbo < −0.3` → BBO overrun
  likely, bet against obi_1.

**Paper refs**: `../papers/gould_bonart_2016_queue_imbalance.md`,
`../papers/cont_kukanov_stoikov_2014_ofi.md` §6 (layer contributions).

---

## 4. Horizon guidance (new for Block C)

With the multi-horizon backtest runner (2026-04-21), every spec now produces a
full horizon curve in one pass. Typical effective horizon by primitive
family:

| family                         | effective horizon range | why |
|---|---|---|
| `trade_imbalance_signed`       | 20–200 ticks (2–20 s)   | trade-driven signal decays slowly |
| `bid/ask_depth_concentration`  | 5–50 ticks             | book shape persists few seconds |
| `obi_ex_bbo`                   | 10–100 ticks           | deeper liquidity is more persistent than obi_1 |
| `obi_1` (ref)                  | 1–20 ticks             | BBO-level info decays fast |

When designing a SignalSpec, **try a horizon matched to the primitive's
physical timescale**; the horizon_curve in `BacktestResult` confirms or
refutes empirically.

---

---

## Block D (2026-04-25) — Velocity / probability / cumulative primitives

Six new primitives added based on additional paper grounding (Hasbrouck 1991/1995, Stoikov 2018, Cartea-Jaimungal 2015, Glosten-Milgrom 1985, Avellaneda-Stoikov 2008).

### Probability-style imbalance <a name="queue_imbalance"></a>

**`queue_imbalance_best`** (stateless, [0, 1])
```
QI = B_1 / (B_1 + A_1)
```
- 0.5 = balanced
- > 0.5 = bid-heavy (probability of next mid-up)
- Linearly equivalent to `obi_1` (= 2·QI − 1)
- **Direction**: Category A (long_if_pos)
- **Use when**: LLM wants probability-style threshold, e.g., `QI > 0.7` (= obi_1 > 0.4)

Paper ref: Gould-Bonart 2016.

### Velocity primitives <a name="velocity"></a>

**`microprice_velocity`** (stateful, bps per tick)
```
mv_t = (microprice_t − microprice_{t-1}) / mid_t × 1e4
```
- Captures fair-value drift speed
- Large |velocity| = adverse-selection arrival
- **Direction**: Category A at moderate magnitude; B2 at extreme

**`book_imbalance_velocity`** (stateful, range ≈ [-2, 2])
```
biv_t = obi_1_t − obi_1_{t-1}
```
- Speed of imbalance shift
- Large positive = bid-side stacking fast
- Large negative = bid being eaten / ask stacking
- **Direction**: Category A (signed pressure-derivative)

Paper ref: Stoikov 2018 §3.4 (microprice dynamics), Cartea-Jaimungal 2015 §HF momentum.

### Spread dynamics <a name="spread_dynamics"></a>

**`spread_change_bps`** (stateful, signed bps)
```
sc_t = spread_bps(t) − spread_bps(t-1)
```
- Sudden widening (positive spike) → adverse-selection arrival
- Gradual widening → inventory pressure
- Narrowing → informed flow exhaustion
- **Direction**: Category C (regime/state filter, not signal)
- **Use case**: `spread_change_bps > 1.0` to exclude adverse-arrival moments

Paper ref: Glosten-Milgrom 1985 (adverse selection component), Avellaneda-Stoikov 2008 (inventory).

### Cumulative signed flow <a name="cumulative_flow"></a>

**`signed_volume_cumulative`** (stateful, alias for `trade_imbalance_signed`)

Provided under Hasbrouck 1991 / Lee-Ready 1991 nomenclature for naming clarity. Use with `rolling_sum` for the cumulative quantity:

```python
formula = "rolling_sum(signed_volume_cumulative, 100) > 50000"
# Hasbrouck cumulative signed flow over 10 seconds
```

- **Direction**: Category A (raw flow direction); B2 when z-scored at extreme

### Book-wide pressure <a name="book_pressure"></a>

**`book_pressure_asymmetry`** (stateless, [-1, 1])
```
bpa = (total_bid_qty − total_ask_qty) / (total_bid_qty + total_ask_qty)
```
- Distinct from `obi_total` which uses ICDC (KIS-published incremental). This uses raw totals.
- Less sensitive to ICDC publication latency
- **Direction**: Category A (pressure)

Paper ref: Cont-Kukanov-Stoikov 2014 §6.

### New helpers (Block D)

| Helper | Use |
|---|---|
| `rolling_max(primitive, W)` | Recent-high reference. e.g., `obi_1 > rolling_max(obi_1, 50) − 0.1` |
| `rolling_min(primitive, W)` | Mirror of above |
| `rolling_sum(primitive, W)` | Hasbrouck cumulative signed flow |

### Suggested Block D specs (iter_023+)

1. Pure velocity-based:
   ```
   formula = microprice_velocity > 5.0
   threshold = 5.0, direction = long_if_pos, horizon = 5
   ```
2. Hasbrouck-style cumulative flow:
   ```
   formula = zscore(rolling_sum(signed_volume_cumulative, 100), 300)
   threshold = 2.0, direction = long_if_neg (extreme = exhaustion), horizon = 20
   ```
3. Velocity + filter:
   ```
   formula = (book_imbalance_velocity > 0.05) AND (spread_change_bps < 1.0)
   threshold = 0.5, direction = long_if_pos, horizon = 10
   ```
4. QI extreme:
   ```
   formula = queue_imbalance_best
   threshold = 0.85, direction = long_if_pos, horizon = 1
   ```
5. Cross-asymmetry:
   ```
   formula = book_pressure_asymmetry - obi_1
   threshold = 0.3, direction = long_if_pos, horizon = 5
   ```
   (Whole-book signal stronger than BBO-only → deeper conviction)

---

## Quick starter specs (suggested for iter_010)

1. `trade_imbalance_signed` smoothed:
   ```
   formula = zscore(trade_imbalance_signed, 300)
   threshold = 2.0, horizon = 50
   ```
2. `obi_ex_bbo` deep-book only:
   ```
   formula = obi_ex_bbo
   threshold = 0.3, horizon = 20
   ```
3. Consensus (OBI × patient depth):
   ```
   formula = obi_1 > 0.5 AND obi_ex_bbo > 0.2
   threshold = 0.5, horizon = 5
   ```
4. Shape-filtered OBI:
   ```
   formula = obi_1 > 0.5 AND bid_depth_concentration < 0.15
   threshold = 0.5, horizon = 5
   ```
5. Trade-flow + book shape trifecta:
   ```
   formula = zscore(trade_imbalance_signed, 300) > 1.5 AND obi_ex_bbo > 0.1
   threshold = 1.5, horizon = 20
   ```

These are suggestions — signal-generator should treat them as inspiration,
not copy them verbatim.
