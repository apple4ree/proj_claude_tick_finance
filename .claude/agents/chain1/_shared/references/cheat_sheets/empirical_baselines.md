# Empirical Baselines — KRX cash equity tick (IS-only)

**Source**: 3 symbols × 8 IS dates (20260316~20260325). Quotes only (data_type=12).
Aggregated across symbol+date for statistical mass.

## Observation framing (read first)

This table is **not a guide for which cell to trigger in**.
It is the **statistical baseline** of KRX cash microstructure.
Your hypothesis should explain how your spec **deviates** from the cell baseline,
not which cell looks attractive. Bias-aware framing:
1. The 5×3 partition is **our** choice; other partitions exist.
2. Distribution (mean/median/p90) is reported, not point estimates.
3. Cells labeled `fee-prohibitive` should NOT be primary triggers — flag them.
4. OOS data is reserved (not in this table).

## Cells: 5 time × 3 vol × 3 magnitude horizons

Magnitude unit: |Δmid|_bps for T-tick horizon. T=50 is the primary metric.

| time_bucket | vol | T=1 mean | T=50 mean | T=500 mean | T=50 p90 | obi>.5 % | lag1 ρ | label |
|---|---|---:|---:|---:|---:|---:|---:|---|
| opening_30min | low | 0.09 | 4.17 | 13.95 | 14.99 | 30.7% | 0.036 | high-magnitude |
| opening_30min | mid | 0.12 | 3.85 | 17.49 | 10.55 | 38.7% | 0.007 | high-magnitude |
| opening_30min | high | 0.32 | 5.35 | 21.32 | 19.14 | 42.9% | -0.137 | high-magnitude |
| morning_60min | low | 0.06 | 2.32 | 11.25 | 10.12 | 41.3% | -0.007 | moderate |
| morning_60min | mid | 0.07 | 2.24 | 11.16 | 10.05 | 43.2% | -0.013 | moderate |
| morning_60min | high | 0.11 | 2.14 | 9.88 | 10.08 | 41.8% | -0.088 | moderate |
| lunch_60min | low | 0.04 | 1.67 | 9.53 | 9.63 | 40.4% | -0.001 | moderate |
| lunch_60min | mid | 0.05 | 1.38 | 7.14 | 5.37 | 41.4% | -0.010 | moderate |
| lunch_60min | high | 0.05 | 0.92 | 5.03 | 0.00 | 36.9% | -0.073 | fee-prohibitive |
| afternoon_120min | low | 0.04 | 1.63 | 8.92 | 9.83 | 35.7% | 0.031 | moderate |
| afternoon_120min | mid | 0.04 | 1.35 | 7.33 | 5.33 | 35.8% | -0.005 | moderate |
| afternoon_120min | high | 0.05 | 0.97 | 4.85 | 0.00 | 33.9% | -0.058 | fee-prohibitive |
| closing_30min | low | 0.03 | 1.06 | 7.74 | 5.26 | 43.2% | -0.036 | moderate |
| closing_30min | mid | 0.06 | 1.78 | 13.19 | 9.47 | 50.8% | -0.041 | moderate |
| closing_30min | high | 0.14 | 3.11 | 13.17 | 10.23 | 59.3% | -0.006 | high-magnitude |

## Distribution detail (T=50 abs_dmid_bps, by cell)

Reading: `mean | median | p90` per cell. Use p90 to gauge tail magnitude.

| time_bucket | vol | mean | median | p90 | n |
|---|---|---:|---:|---:|---:|
| opening_30min | low | 4.17 | 0.00 | 14.99 | 6,196 |
| opening_30min | mid | 3.85 | 0.00 | 10.55 | 20,558 |
| opening_30min | high | 5.35 | 0.00 | 19.14 | 180,220 |
| morning_60min | low | 2.32 | 0.00 | 10.12 | 47,496 |
| morning_60min | mid | 2.24 | 0.00 | 10.05 | 165,805 |
| morning_60min | high | 2.14 | 0.00 | 10.08 | 371,999 |
| lunch_60min | low | 1.67 | 0.00 | 9.63 | 90,542 |
| lunch_60min | mid | 1.38 | 0.00 | 5.37 | 213,164 |
| lunch_60min | high | 0.92 | 0.00 | 0.00 | 261,011 |
| afternoon_120min | low | 1.63 | 0.00 | 9.83 | 190,843 |
| afternoon_120min | mid | 1.35 | 0.00 | 5.33 | 440,351 |
| afternoon_120min | high | 0.97 | 0.00 | 0.00 | 564,296 |
| closing_30min | low | 1.06 | 0.00 | 5.26 | 84,436 |
| closing_30min | mid | 1.78 | 0.00 | 9.47 | 69,834 |
| closing_30min | high | 3.11 | 0.00 | 10.23 | 192,187 |

## Negative space (fee-prohibitive cells)

Cells where mean(|Δmid|_T50_bps) < 1.0 AND p90 < 5.0 bps.
These cells alone cannot pay 23 bps RT fee. Triggering primarily within
them is auto-flagged as suspicious by feedback-analyst.

- `lunch_60min__high`
- `afternoon_120min__high`

## High-magnitude cells (potential focus zones)

Cells where mean(|Δmid|_T50_bps) ≥ 3.0 OR p90 ≥ 15.0 bps.
These cells have natural baseline magnitude — but raw baseline
magnitude is **not** signal. Spec must show predictivity ON TOP of
the cell's natural variance to be interesting.

- `opening_30min__low`
- `opening_30min__mid`
- `opening_30min__high`
- `closing_30min__high`

## How to use in hypothesis

Wrong: "my spec triggers in opening_30min × high vol" → cell-picking.

Right: "in opening_30min × high vol, baseline mean(|Δmid|_T50) ≈ X bps
with p90 Y bps. My spec adds the condition `obi_1 > 0.7`, which I expect
to filter to events where mid moves +Z bps directionally over T=50, exceeding
the cell's |Δmid| baseline by Δ."

This forces deviation framing — anchored to data, not picking-from-list.