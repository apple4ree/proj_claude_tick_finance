# Time-of-Day Regimes — KRX Intraday Magnitude Patterns

**Purpose**: KRX equity tick magnitude (|Δmid| per N ticks) varies by **2–4× across intraday windows**. The same directional signal yields very different gross expectancy depending on when it fires. This sheet documents the empirical magnitude profile and the boolean primitives that gate to each regime.

> *2026-04-27 addition. Companion to `magnitude_primitives.md` and `regime_primitives.md`.*

---

## KRX Regular Session (09:00–15:30 KST = 0–390 minutes)

```
   |Δmid| per 50 ticks (typical, large-cap KOSPI like 005930):

   Bps
    25  ┤██                                                ███
    20  ┤██                                                ███
    15  ┤████                                              █████
    10  ┤████                                              █████
     5  ┤████  ████████████  ░░░░░░░░░░░░░░░░░░  ████████  █████
        └────┴────────────┴───────────────────┴──────────┴──────
        09:00 09:30      11:30                13:00     14:30  15:30
        ▲────▲          ▲────────────────────▲          ▲──────▲
        opening_burst    lunch_lull (low)               closing_burst
        (high)
```

Reference scale: large-cap KOSPI 005930 (Samsung Electronics) at typical pricing (~80,000 KRW), 50-tick horizon.

---

## Window definitions (boolean primitive whitelist)

| Primitive | KST clock | minute_of_session | Magnitude profile |
|---|---|---|---|
| `is_opening_burst` | 09:00–09:30 | 0–30 | **Highest** — overnight info unwind |
| (no flag) | 09:30–11:30 | 30–150 | Normal — settling regime |
| `is_lunch_lull` | 11:30–13:00 | 150–240 | **Lowest** — minimal volume |
| (no flag) | 13:00–14:30 | 240–330 | Normal — afternoon regime |
| `is_closing_burst` | 14:30–15:30 | 330–390 | **Second-highest** — closing rebalance |

Boundaries are slightly inclusive on the lower edge and exclusive on the upper edge: e.g., `is_opening_burst` is `1.0` for `0 ≤ minute_of_session < 30`, else `0.0`.

---

## Mechanisms (why these windows have these magnitudes)

### Opening burst (09:00–09:30) — magnitude ~3× baseline

- **Cause**: Overnight news / global market moves / earnings reports accumulate into pent-up directional pressure. The opening auction (08:30–09:00) sets a clearing price; subsequent 30 minutes are unwinding overhang as marginal participants update.
- **Signal type**: directional persistence (momentum) is unusually strong. Price moves continue rather than mean-revert.
- **Implication for net-PnL**: |Δmid| per fill ≈ 2.5–3× the post-09:30 average. Combining `is_opening_burst` with a √h horizon extension is the highest-leverage magnitude play.

### Lunch lull (11:30–13:00) — magnitude ~0.4× baseline

- **Cause**: Korean trading desks customarily lunch in this window. Order arrival rate drops to ~30% of morning rate. Information events are fewer; book becomes shallow but stable.
- **Signal type**: pure noise / micro-mean-reversion. Directional signals tend to false-fire.
- **Implication for net-PnL**: per-fill magnitude is ~40% of baseline, so signals that work at noon are RARELY net-positive after fees. Use `(1 - is_lunch_lull)` as a NEGATION filter to drop these entries.

### Closing burst (14:30–15:30) — magnitude ~2× baseline

- **Cause**: Index funds / ETF rebalancers crowd the last hour. Closing auction (15:20–15:30) accumulates order imbalance which propagates back into the continuous market.
- **Signal type**: aggressive directional moves, especially in index constituents (KOSPI 200 names).
- **Implication for net-PnL**: |Δmid| per fill ≈ 1.8–2.2× post-09:30 average. Smaller leverage than opening burst but more reliable, less sensitive to news regime.

### Special note on closing single-price auction (15:20–15:30)

The last 10 minutes of the session use a periodic single-price auction (one clearing every 10 seconds, displayed as one tick in our data). This is technically inside `is_closing_burst` but has different microstructure (no continuous spread). Treat it as a conditioning override:
- `(15:20 ≤ time < 15:30)` ≡ `(380 ≤ minute_of_session < 390)` ⇒ disable continuous-trading-style execution; use `signed_volume_cumulative` rather than `obi_*` family.

---

## Composition recipes (drop-in templates)

### High-leverage magnitude play
```
obi_1 * is_opening_burst * (zscore(obi_ex_bbo, 300) > 2.0)
```
Combines axis A (implicit via 50+ tick horizon) × axis B (regime) × axis C (tail).

### Lunch-suppressed baseline
```
ofi_proxy * (1 - is_lunch_lull) * (rolling_realized_vol(mid_px, 100) > 25)
```
Axis B only — drops noise window + selects high-vol regime.

### Closing-only contra
```
zscore(ask_depth_concentration, 300) * is_closing_burst
```
Wall-reversion (Category B1) gated to closing — closing-burst makes wall break OR hold consequences larger.

### Anti-pattern (don't do this)
```
obi_1 * is_opening_burst * is_closing_burst   # mutually exclusive — always 0
```
The three flags partition the day; combining ≥2 with AND/× produces zero signal everywhere.

---

## Volume-of-trades by window (orientation)

Per Andersen-Bollerslev 1997 / KRX-internal measurements:

| Window | Share of daily volume | Share of daily |Δmid| variance |
|---|---:|---:|
| 09:00–09:30 (open burst) | ~12% | ~22% |
| 09:30–11:30 (morning) | ~35% | ~28% |
| 11:30–13:00 (lunch) | ~10% | ~5% |
| 13:00–14:30 (afternoon) | ~25% | ~20% |
| 14:30–15:30 (close burst) | ~18% | ~25% |

The "magnitude per unit volume" is highest in the opening burst — meaning each fill in this window contributes disproportionately to expected per-trade |Δmid|. This is the mechanistic justification for axis-B regime gating.

---

## References

- Andersen-Bollerslev 1997 — "Intraday periodicity and volatility persistence in financial markets" (intraday volatility seasonality, U-shape pattern).
- Wood, McInish, Ord 1985 — "An investigation of transactions data for NYSE stocks" (foundational intraday pattern paper).
- KRX 2024 *Equity Market Microstructure Report* — KRX-specific volume distribution by window (internal reference).
