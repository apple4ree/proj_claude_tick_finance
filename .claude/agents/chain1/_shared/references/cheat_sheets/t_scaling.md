# T-scaling — Empirical holding-period vs magnitude (KRX cash IS)

**Source**: 3 symbols × 8 IS dates. Aggregated unconditionally + conditionally on each primitive.

## What this answers

Two questions for each (primitive, threshold) pair:
1. **Magnitude growth**: how does mean(|Δmid_T|_bps) scale with holding period T?
2. **Predictivity decay**: does the primitive's WR (direction-correctness) hold as T grows?

If magnitude grows √T but WR decays to 0.5, the conditional `mean(Δmid_signed_T)` →
the actual realized expectancy. **That's the deployable metric**.

Anchor: KRX RT fee = 23 bps. Net = `mean(abs_dmid)` × `(2·WR − 1)` − 23.

## Unconditional baseline (random-walk reference)

| T | mean |Δmid|_bps | median | p90 | mean_signed (drift) | n |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.09 | 0.00 | 0.00 | +0.01 | 3,786,172 |
| 10 | 0.64 | 0.00 | 0.00 | +0.09 | 3,786,163 |
| 50 | 2.48 | 0.00 | 9.76 | +0.46 | 3,786,123 |
| 100 | 4.34 | 0.00 | 10.33 | +0.93 | 3,786,073 |
| 500 | 15.46 | 5.17 | 21.36 | +4.66 | 3,785,673 |
| 1000 | 26.54 | 10.03 | 31.63 | +9.32 | 3,785,173 |
| 2000 | 45.89 | 15.31 | 48.19 | +18.67 | 3,784,173 |
| 5000 | 96.90 | 21.25 | 76.12 | +46.88 | 3,781,173 |
| 10000 | 174.55 | 30.60 | 117.94 | +93.87 | 3,776,173 |

**The `mean_signed (drift)` column is the IS sample's macro-drift contribution.**
If non-zero, all conditional `mean_signed` numbers below are biased by this drift.
Use the `alpha_vs_drift` column to isolate the signal's true edge.

## Per-primitive conditional metrics

For each primitive, conditional on `|signal| > threshold`. Long side stats
are reported; short side is symmetric for Category A primitives.

### `obi_1` (threshold=0.5, direction=long_if_pos)

| T | n | mean_signed | **alpha_vs_drift** | mean_abs | WR(>0) | net_signal_after_fee |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 740,389 | +0.18 | +0.17 | 0.21 | 0.018 | -22.83 |
| 10 | 740,383 | +1.13 | +1.04 | 1.40 | 0.083 | -21.96 |
| 50 | 740,383 | +4.24 | +3.77 | 5.44 | 0.208 | -19.23 |
| 100 | 740,383 | +6.61 | +5.68 | 8.93 | 0.276 | -17.32 |
| 500 | 740,372 | +28.78 | +24.11 | 39.21 | 0.399 | **+1.11** ✓ |
| 1000 | 740,347 | +53.03 | +43.71 | 74.62 | 0.434 | **+20.71** ✓ |
| 2000 | 740,347 | +101.75 | +83.08 | 137.12 | 0.464 | **+60.08** ✓ |
| 5000 | 739,930 | +238.34 | +191.47 | 300.67 | 0.482 | **+168.47** ✓ |
| 10000 | 739,912 | +417.63 | +323.75 | 503.51 | 0.491 | **+300.75** ✓ |

### `obi_3` (threshold=0.4, direction=long_if_pos)

| T | n | mean_signed | **alpha_vs_drift** | mean_abs | WR(>0) | net_signal_after_fee |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 928,480 | +0.07 | +0.06 | 0.12 | 0.007 | -22.94 |
| 10 | 928,480 | +0.54 | +0.44 | 0.97 | 0.034 | -22.56 |
| 50 | 928,480 | +2.35 | +1.88 | 4.23 | 0.099 | -21.12 |
| 100 | 928,480 | +4.42 | +3.49 | 7.92 | 0.144 | -19.51 |
| 500 | 928,480 | +21.07 | +16.40 | 32.95 | 0.256 | -6.60 |
| 1000 | 928,480 | +41.04 | +31.72 | 62.38 | 0.307 | **+8.72** ✓ |
| 2000 | 928,480 | +81.98 | +63.31 | 116.12 | 0.353 | **+40.31** ✓ |
| 5000 | 926,676 | +206.76 | +159.88 | 265.35 | 0.394 | **+136.88** ✓ |
| 10000 | 926,661 | +388.67 | +294.80 | 459.89 | 0.397 | **+271.80** ✓ |

### `microprice_dev_bps` (threshold=0.5, direction=long_if_pos)

| T | n | mean_signed | **alpha_vs_drift** | mean_abs | WR(>0) | net_signal_after_fee |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,575,996 | +0.09 | +0.08 | 0.12 | 0.010 | -22.92 |
| 10 | 1,575,988 | +0.64 | +0.55 | 0.85 | 0.051 | -22.45 |
| 50 | 1,575,988 | +2.35 | +1.88 | 3.33 | 0.142 | -21.12 |
| 100 | 1,575,988 | +3.81 | +2.89 | 5.76 | 0.200 | -20.11 |
| 500 | 1,575,968 | +14.38 | +9.71 | 23.35 | 0.332 | -13.29 |
| 1000 | 1,575,943 | +25.88 | +16.56 | 42.81 | 0.376 | -6.44 |
| 2000 | 1,575,934 | +48.66 | +29.98 | 77.48 | 0.419 | **+6.98** ✓ |
| 5000 | 1,575,217 | +114.11 | +67.23 | 165.00 | 0.448 | **+44.23** ✓ |
| 10000 | 1,572,451 | +207.48 | +113.61 | 284.43 | 0.446 | **+90.61** ✓ |

### `ofi_proxy_5` (threshold=0.0, direction=long_if_pos)

| T | n | mean_signed | **alpha_vs_drift** | mean_abs | WR(>0) | net_signal_after_fee |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,921,285 | +0.03 | +0.02 | 0.10 | 0.006 | -22.98 |
| 10 | 1,921,283 | +0.12 | +0.03 | 0.72 | 0.027 | -22.97 |
| 50 | 1,921,278 | +0.56 | +0.10 | 2.80 | 0.079 | -22.90 |
| 100 | 1,921,234 | +1.19 | +0.27 | 4.88 | 0.119 | -22.73 |
| 500 | 1,920,995 | +7.00 | +2.33 | 18.45 | 0.241 | -20.67 |
| 1000 | 1,920,707 | +10.43 | +1.10 | 28.66 | 0.295 | -21.90 |
| 2000 | 1,920,177 | +21.05 | +2.37 | 48.63 | 0.342 | -20.63 |
| 5000 | 1,918,931 | +46.29 | -0.59 | 94.05 | 0.387 | -23.59 |
| 10000 | 1,916,739 | +102.18 | +8.31 | 180.12 | 0.411 | -14.69 |

### `zscore_obi1_w300` (threshold=2.0, direction=long_if_neg)

| T | n | mean_signed | **alpha_vs_drift** | mean_abs | WR(>0) | net_signal_after_fee |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 218,513 | -0.15 | -0.16 | 0.18 | 0.001 | -23.16 |
| 10 | 218,513 | -0.68 | -0.77 | 0.81 | 0.005 | -23.77 |
| 50 | 218,513 | -1.41 | -1.88 | 2.43 | 0.022 | -24.88 |
| 100 | 218,513 | +0.42 | -0.51 | 7.34 | 0.043 | -23.51 |
| 500 | 218,513 | -0.38 | -5.04 | 15.95 | 0.151 | -28.04 |
| 1000 | 218,513 | +3.72 | -5.60 | 27.17 | 0.206 | -28.60 |
| 2000 | 218,513 | +20.56 | +1.89 | 52.01 | 0.268 | -21.11 |
| 5000 | 218,432 | +51.73 | +4.85 | 103.93 | 0.336 | -18.15 |
| 10000 | 218,104 | +133.36 | +39.49 | 211.55 | 0.378 | **+16.49** ✓ |

## Reading guide — important caveats

**Caveat 1 — overlapping windows**: each `n` is dependent samples (overlapping T-tick
windows). The effective independent draws is roughly `n / T`, much smaller. Treat WR
and means as descriptive, not statistical inference.

**Caveat 2 — macro drift**: `mean_signed` includes the IS sample's day-trend.
On 8 March 2026 dates, KRX cash had a noticeable up-drift, which inflates `mean_signed`
for any long-side bucket — **regardless of signal predictivity**. Use **`alpha_vs_drift`**
(= mean_signed − unconditional_signed_drift) to isolate the signal edge.

**Caveat 3 — WR semantics**: WR counts strict `Δmid > 0` (positives). Many ticks
at small T have `Δmid = 0` due to discreteness — those are counted as losses. So WR
at T=1 may be ~0.02 even for a perfectly predictive signal. WR is meaningful only at T ≥ 100.

**Reading rules**:
- Use `alpha_vs_drift` for **signal edge** assessment (not raw `mean_signed`)
- Use `mean_abs_dmid_bps` for **magnitude reference** at horizon T
- WR < 0.5 with positive `mean_signed` typically means "few big winners offset many small losers"
- A primitive with persistent **`alpha_vs_drift` > 5 bps at T=500 with stable WR** is interesting

## How to use in hypothesis

Wrong: "my spec uses obi_1 > 0.5 with T=100, expect +5 bps gross"
(unanchored, ignores empirical T-scaling)

Right: "obi_1 > 0.5 has empirical mean_signed_dmid +X bps at T=100,
scaling to +Y bps at T=500. My spec extends T via stickiness (rolling_mean
window=200) so the regime mean_dur ≈ 200; expect mean per-regime gross
≈ Z bps. Net after 23 bps fee = Z − 23 = W."