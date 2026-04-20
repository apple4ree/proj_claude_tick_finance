---
stage: alpha
name: pilot_s3_034020_spread
created: 2026-04-17
signal_brief_rank: 1
---

# Alpha Design: pilot_s3_034020_spread

## Hypothesis

When 034020's spread_bps exceeds the p95 threshold (9.501 bps, the upper tail of the 1-tick spread regime) AND the depth-5 order book imbalance confirms bid-side pressure (obi_5 > 0.50), the transient liquidity gap is being met by genuine buy demand — the spread will compress upward as market-makers reprice, producing a short-horizon positive return (rank-1 from signal_brief, ev_bps=1.538 after 21 bps round-trip fee).

## Market Context

034020 (Doosan Enerbility) trades in the 100k–112k KRW range during the IS window. The effective tick is 100 KRW (implied from spread_bps ≈ 9.3 bps at median mid ~107k), yielding a 1-tick spread of ~9.3 bps and a 2-tick spread of ~18.5 bps. The spread distribution is bimodal: the 1-tick cluster (9.0–9.6 bps, ~98% of ticks) and the 2-tick cluster (18–19 bps, ~0.7%). The viable edge lives exclusively in the upper tail of the 1-tick cluster (spread 9.5–9.6 bps), where obi_5 averages 0.73 (bid-heavy) — these are micro-widening events driven by buy-side absorption, not shock events. 2-tick spread events have obi_5 ≈ 0.03 (balanced/ask-heavy) and represent adverse shock entries that must be excluded.

Entry is valid across the full KRX session (09:00–15:30 KST), with the opening 30 minutes (09:00–09:30 KST) excluded per the established KRX opening-noise lesson.

## Entry Condition

Enter long when ALL of the following hold simultaneously:

1. `spread_bps >= 9.501` — at or above the p95 threshold from the signal brief (1 is the rank)
2. `obi_5 > 0.50` — depth-5 book is bid-heavy, confirming buy-side pressure gates out the adverse 2-tick shock cluster
3. Time is after 09:30 KST (30-minute opening blackout)

The OBI gate is mandatory: without it, 2-tick shock entries (obi_5 ≈ 0.03) pollute the signal and replicate the S2 failure pattern (7/8 immediate SL on 010140 spread_bps-only entries).

## Signals Needed

- `spread_bps` — built-in snapshot primitive
- `obi(depth=5)` — built-in snapshot primitive (obi_5)

## Universe Rationale

034020 is one of only 2 symbols with viable signals (n_viable_in_top=2) in its brief. Rank-1 signal has the highest ev_bps (1.538) among all viable candidates. Mid-tier symbol with moderate liquidity — not in the top-liquid tier, but the spread_bps signal has 6,544 historical entries at threshold, sufficient for statistical significance. The 1-tick = 100 KRW tick structure (not the 500 KRW that KRX rules suggest for >100k band) is confirmed directly from the data and must be respected in execution.

## Knowledge References

- `lesson_20260417_003`: spread_bps alone is direction-agnostic; OBI was the sole separating feature (WIN OBI=0.64 vs LOSS OBI=0.43). Gate required. Also confirms 50 KRW tick for 010140 — here the implied tick is 100 KRW (verified from data).
- `lesson_20260414_004`: per-symbol tick-size floor must be computed from data, not assumed from KRX band rules. For 034020, implied spread = 100 KRW / 107k ≈ 9.3 bps, so threshold 9.501 is physically above the 1-tick floor (correct).
- Iteration 2 / S2 failure: spread_bps alone yielded WR 12.5% on 010140 downtrend. OBI gate addresses both the direction-agnostic issue and the shock-exclusion issue.

## Constraints Passed To Execution-Designer

- Tick size for 034020: **100 KRW** (verified from data — NOT 500 KRW despite KRX band suggesting otherwise). All SL/PT bps must be multiples of `100 / mid * 10000 ≈ 9.35 bps`.
- Brief's optimal_exit baseline: pt_bps=79, sl_bps=3. Note sl_bps=3 is sub-tick (3 < 9.35 bps per tick) — execution designer must round up to at minimum 1-tick SL (~9.5 bps) or the stop is physically unreachable.
- Exit mix from brief: 56% trailing stop, 33% SL, 9% PT — trailing is the primary exit mechanism.
- EV is marginal (1.538 bps); selectivity matters more than volume. The OBI gate reduces entries from ~7.4% to ~6.5% of ticks — acceptable selectivity loss given exclusion of the hostile shock cluster.
- Signal is fleeting — spread widens and tightens within seconds. Entry must execute within the spread-widening window; aggressive limit (at ask) or marketable limit required.
- Signal is stateless (pure snapshot comparison) — `needs_python: false`.

```json
{
  "name": "pilot_s3_034020_spread",
  "hypothesis": "When 034020 spread_bps exceeds p95 (9.501 bps, upper tail of 1-tick regime) and obi_5 confirms bid-side pressure (>0.50), the transient liquidity gap resolves upward as market-makers reprice — rank-1 from signal_brief, ev_bps=1.538 post-fee.",
  "entry_condition": "spread_bps >= 9.501 AND obi(depth=5) > 0.50 AND time > 09:30 KST; OBI gate excludes the 2-tick shock cluster (obi_5~0.03) that accounts for 10% of above-threshold entries and has no directional edge",
  "market_context": "034020 mid 104k-112k KRW, effective tick 100 KRW (data-derived, not KRX-band rule), 1-tick spread ~9.3 bps; entry fires in the upper tail of 1-tick spread regime (9.5-9.6 bps) where obi_5 averages 0.73 (bid-heavy); 2-tick spread events (18+ bps, obi_5~0.03) explicitly excluded; full session 09:30-15:30 KST",
  "signals_needed": ["spread_bps", "obi(depth=5)"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_003_spread_bps_threshold_is_direction_agnostic_obi_gate_required",
  "signal_brief_rank": 1,
  "universe_rationale": "034020 has 2 viable signals in top-10; rank-1 spread_bps has highest ev_bps (1.538) of the viable set; 6,544 historical entries at threshold provides adequate statistical base",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/pilot_s3_034020_spread_alpha.md"
}
```
