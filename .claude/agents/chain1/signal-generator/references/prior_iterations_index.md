# Prior Iterations Index (curated, post-v5)

This file is **manually curated**. Auto-bloat from orchestrator goes to
`prior_iterations_auto_log.md` (separate file, not in required reading).

> **Read priority**: skim §1 (lessons) + §2 (top spec table) only. Do NOT read top-to-bottom.
> Use grep on `prior_iterations_auto_log.md` if you need a specific spec_id.

---

## §0. 2026-04-27 — Paradigm shift to regime-state (v5+)

**Backtest semantics**: spec.formula > threshold = STATE indicator (not trigger).
Variable holding period determined by signal. Fee charged once per regime (round-trip).
No end-of-session force-close.

v3/v4 historical data preserved in `prior_iterations_index.md.v3v4_archive` but
interpretation differs (fixed-H paradigm). Do NOT rely on those measurements.

---

## §1. Lessons across v3/v4/v5

### Carried over (still valid)

1. **Direction prediction is robust** — 95% accuracy across long_if_pos / long_if_neg
   with whitelisted Categories A/B1/B2/C primitives. B3 (`obi_ex_bbo` extreme) has
   cite-but-fail behavior at ~67%.
2. **Sell tax 20 bps is mechanical** (KRX cash) — net deployment requires
   `gross_expectancy_bps > 23`.
3. **Magnitude axes framework** (A horizon × B regime × C tail) — combine ≥ 2 axes
   per spec for fee-passing chance.
4. **Time-of-day matters** — opening 30-min has p99 |Δmid|/300 ticks ≈ 52 bps;
   lunch lull is fee-prohibitive.

### v5 specific (new lessons)

5. **regime-state effective ceiling ≈ 4.74 bps gross** — across 78 specs / 25 iter
   under regime-state + Fix #1 net-PnL prompt. Top 5 all use `rolling_mean(obi_1, ...)`
   variants with time-gate or shape filter.
6. **Saturation at iter ~13** — best of run is iter013 (4.74). Iters 14-24 produced
   no improvement. Improver mutation became random walk after iter ~13.
7. **Pattern saturation**: top 10 of v5 are dominated by `obi_1 + opening + shape`
   triplet. **Underexplored**: lunch / closing / vol-gate / true tail (zscore ≥ 2.5)
   / multi-symbol consensus / non-OBI primitive (ofi, microprice_dev_bps, trade_imb).
8. **Regime-state metrics confirm paradigm works**: duty 0.05~0.20, mean_dur 27~117
   for top specs. Within target range (target: duty 0.05~0.80, mean_dur 20~5000).
   Paradigm is operationally sound — the issue is **magnitude per regime**, not regime
   structure.

### Anti-patterns (auto-rejected by feedback-analyst)

| Pattern | Why rejected |
|---|---|
| `duty_cycle > 0.95` | buy-and-hold artifact |
| `n_regimes / sessions < 1.5` | too rare |
| `mean_duration_ticks < 5` with high `n_regimes` | flickering, fee-prohibitive |
| Hypothesis without target duty/duration/gross numbers | unverifiable |

---

## §2. v5 top 10 specs (curated)

| Rank | spec_id | gross_bps | n | duty | mean_dur | formula |
|---:|---|---:|---:|---:|---:|---|
| 1 | iter013_opening_burst_conviction | **4.74** | 6444 | 0.20 | 117 | `rolling_mean(obi_1, 50) > 0.4 AND minute_of_session < 15` |
| 1' | iter014_opening_burst_long_hold | 4.74 | 6444 | 0.20 | 117 | (same as iter013, dup) |
| 2 | iter016_stable_pressure_on_fragile_book | 4.08 | 1049 | 0.03 | 87 | `rolling_mean(obi_1, 100) > 0.4 AND bid_depth_concentration > 0.3` |
| 3 | iter009_stable_imbalance_vs_fragile_book | 3.85 | 1273 | 0.03 | 77 | `rolling_mean(obi_1, 50) > 0.4 AND bid_depth_concentration > 0.3` |
| 4 | iter000_full_book_consensus | 3.44 | 11846 | 0.11 | 34 | `obi_1 > 0.5 AND obi_ex_bbo > 0.2` |
| 4' | iter006_opening_burst_conviction (v5 dup) | 3.44 | 11846 | 0.11 | 34 | same as iter000 |
| 5 | iter020_magnitude_consensus_at_open | 3.42 | 6840 | 0.05 | 27 | `(obi_1 > 0.7 AND obi_ex_bbo > 0.4) AND minute_of_session < 15` |
| 6 | iter023_opening_burst_pressure_consensus | 3.36 | 9336 | 0.08 | 30 | (obi_1 + obi_ex_bbo + minute_of_session) |
| 6' | iter024_consensus_long_hold_at_open | 3.36 | 9336 | 0.08 | 30 | (dup) |
| 7 | iter002_conviction_in_high_vol | 3.26 | 17093 | 0.10 | 22 | (obi_1 + rolling_realized_vol) |

**Diversity gap**: rank 1-7 share `obi_1 > θ` core. **Non-saturated families**:
- `ofi_*` (only used in iter001, 0.46 bps — needs revisit)
- `microprice_dev_bps` (used iter008 standalone, low gross)
- `trade_imbalance_signed` (zscore variants tried but threshold too low)
- Multi-period composition (e.g., short + long rolling_mean cross)
- Tail (zscore ≥ 2.5) — almost untried

---

## §3. Active references

For full details:
- v5 specs: `prior_iterations_auto_log.md` (auto-bloat, grep target)
- v3 / v4 archive: `prior_iterations_index.md.v3v4_archive`
- Backtest result JSONs: `iterations/iter_NNN/results/<spec_id>.json`

---

## §4. Hypothesis prompts for v6+

For iter_000 of v6, generator should explore (in priority order):

1. **Tail-magnitude (Axis C, untried)**: `zscore(<flow>, 200~500) > 2.5` with
   `long_if_neg` (mean-reversion at extreme). Targets: gross 8-15 bps, mean_dur 20-100.
2. **Long-horizon stickiness (Axis A)**: `rolling_mean(<primitive>, 500~2000) > θ`
   for stickier regimes. Risk: low n_regimes.
3. **Non-OBI primitive families**: `ofi_depth_5/10`, `microprice_velocity`,
   `trade_imbalance_signed` raw — break the obi_1 monoculture.
4. **Time-gate diversification**: `is_closing_burst` (vs over-explored opening)
   or `is_lunch_lull` as anti-gate.
5. **Vol-conditional**: `rolling_realized_vol > p67` regime alone (not combined
   with obi_1 saturated cluster).
6. **Multi-primitive consensus** (≥ 3 distinct families): pressure × shape × time
   already tried; try pressure × velocity × vol.

Anti-pattern for v6: re-using the obi_1 + opening + shape triplet (saturated).
