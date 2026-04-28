# Quick Reference Card — Signal Generator

**MUST be read before drafting any spec.** Concise actionable reference, post-v5.

---

## 1. Targets (regime-state)

| Metric | Target range | Anti-pattern |
|---|---|---|
| `signal_duty_cycle` | 0.05 ~ 0.80 | > 0.95 = buy-and-hold artifact |
| `mean_duration_ticks` | 20 ~ 5000 | < 5 with `n_regimes` > 100 = flickering |
| `n_regimes / session` | 5 ~ 50 | < 1.5 = too rare |
| `gross_expectancy_bps` | **≥ 23** to pass KRX RT fee | < 23 = not deployable |

KRX RT fee = 20 bps sell tax + 3 bps maker fee = **23 bps mechanical floor**.

---

## 2. v5 measured ceiling — read carefully

**78 specs across 25 iterations, 0/78 passed fee.** Best:

| spec_id | gross_bps | n | duty | mean_dur | formula |
|---|---:|---:|---:|---:|---|
| iter013_opening_burst_conviction | **4.74** | 6444 | 0.20 | 117 | `rolling_mean(obi_1, 50) > 0.4 AND minute_of_session < 15` |
| iter016_stable_pressure_on_fragile_book | 4.08 | 1049 | 0.03 | 87 | `rolling_mean(obi_1, 100) > 0.4 AND bid_depth_concentration > 0.3` |
| iter009_stable_imbalance_vs_fragile_book | 3.85 | 1273 | 0.03 | 77 | `rolling_mean(obi_1, 50) > 0.4 AND bid_depth_concentration > 0.3` |
| iter020_magnitude_consensus_at_open | 3.42 | 6840 | 0.05 | 27 | `(obi_1 > 0.7 AND obi_ex_bbo > 0.4) AND minute_of_session < 15` |
| iter000_full_book_consensus | 3.44 | 11846 | 0.11 | 34 | `obi_1 > 0.5 AND obi_ex_bbo > 0.2` |

**Ceiling diagnosis**: mean per-regime magnitude ≈ 3-5 bps. Fee 23 bps → all specs net ≤ -18 bps.

**Pattern saturation observed**:
- Top 10 of 78 specs all use `rolling_mean(obi_1, ...)` or `obi_1 > θ` as core
- Time-gate (`minute_of_session < 15`) appears in 5/10 top
- Shape filter (`bid_depth_concentration > 0.3`) appears in 3/10

→ **Iterations exhausted obi_1 + opening + shape filter combinations.** v6+ must explore beyond this saturated cluster.

---

## 2.5. Maker spread capture (Path B, post-v5)

Backtest now supports `execution_mode="maker_optimistic"`:
- Long: enter at BID, exit at ASK
- Short: enter at ASK, exit at BID
- Effect: realized gross = mid_to_mid_gross + (avg spread bps) ≈ +5 bps for KRX 005930

KRX RT fee remains 23 bps (sell tax 20 bps mechanical, unaffected by maker class).
Net = `(mid_gross + spread) - 23`. v5 best (4.74 + 5 = 9.74) still fails fee.

**Implication for spec design**: maker mode reduces required mid-gross from 23 → 18 bps.
Specs with mid-to-mid gross 15+ bps may now become deployable. Path A/C/D primitives
that achieve this (e.g., long-T sticky obi or true-tail extreme) are the right targets.

## 3. Why fee floor fails — magnitude axes

To reach gross ≥ 23 bps, at least one mechanism must amplify per-regime magnitude:

**Axis A — Horizon extension (random-walk √T scaling)**
- σ(Δmid_T) ≈ σ_per_tick × √T
- KRX 005930 σ_per_tick ≈ 0.5 bps → T=5000 ticks (8 min) ≈ 35 bps
- Mechanism: signal stickiness via `rolling_mean(...)` window size or stronger gate
- v5 best mean_dur 117 (iter013) — still 10x short of √T-required

**Axis B — Regime gate (concentrated time / vol)**
- Opening 30-min has mean |Δmid_per_tick| ≈ 1.5 bps (vs 0.4 bps lunch)
- High-vol regime (rolling_realized_vol p67+) has 2.5-3x baseline magnitude
- v5 explored opening_burst extensively, but **lunch / closing / vol-gate underexplored**

**Axis C — Tail selection (zscore at p99+)**
- Conditional E[|Δmid|] | OBI z-score > 2.5 ≈ 12-15 bps for 100-tick horizon
- Trade-off: rare events → low n_regimes → high statistical noise
- v5 attempted with `zscore(...)` but threshold often too low (z=2.0 instead of z=2.5+)

**Combine ≥ 2 axes per spec for fee-passing chance.**

---

## 4. Direction rule (concise)

Run this decision tree for every primitive (full version: `direction_semantics.md`):

| Primitive type | Default direction |
|---|---|
| Pressure / flow (obi_k, ofi_*, microprice_dev_bps, trade_imbalance_signed raw) | `long_if_pos` (Category A) |
| Shape concentration (bid/ask_depth_concentration, obi_ex_bbo at extreme) | `long_if_neg` (Category B1/B3) |
| Tail extreme via zscore (zscore(flow, w) > 2.5) | `long_if_neg` (Category B2) |
| Regime gate (minute_of_session, rolling_realized_vol, is_opening_burst) | filter only — no direction |
| Uncertain | submit BOTH directions |

**Cite `Category X` in hypothesis text** — explicit anchor for downstream review.

---

## 5. Hypothesis template (copy/paste, fill blanks)

```
Enter when <state>, exit when <inverse>.
Regime characterization: <where/when this state occurs in the data>.
Expected duty=<D>, mean_duration=<M> ticks, target gross=<G> bps (vs 23 fee).
Direction <dir> per Category <A|B1|B2|B3|C>.
Magnitude mechanism: axis <A|B|C> via <stickiness|gate|tail>.
```

**Self-check before emit**:
- Does target gross G ≥ 23? If not, why is this spec interesting (diagnostic / building block)?
- Does mean_duration target reflect √T scaling? (M=20 → ~2 bps; M=500 → ~11 bps; M=5000 → ~35 bps)
- Did I cite a Category letter and a magnitude axis?

---

## 6. Reading priority (3 files)

1. `_shared/references/cheat_sheets/regime_state_paradigm.md` — paradigm semantics (REQUIRED)
2. `_shared/references/cheat_sheets/direction_semantics.md` — for new primitive or contra direction (REQUIRED if applicable)
3. **This file** (quick_ref.md)

Optional / when needed:
- Primitive whitelist: `obi_family_formulas.md`, `ofi_family_formulas.md`, `regime_primitives.md`, `microstructure_advanced.md`
- Block F: `block_f_time_gates.md` (if using opening / closing / lunch primitives)
- Papers: `cont_kukanov_stoikov_2014_ofi.md`, `stoikov_2018_microprice.md` (foundational, cite when using OFI/microprice)

`prior_iterations_index.md` is now **iteration log only** — do NOT read top-to-bottom; grep specific spec_id if needed.
