---
id: pattern_lob_signal_fires_after_absorption
created: 2026-04-14T00:00:00
tags: [pattern, lob, signal-timing, absorption, anti-edge, obi]
severity: high
links:
  - "[[lesson_20260414_005_mean_reversion_entry_fires_after_reversal_exhausted_ret50_confirmation_too_late]]"
---

# Pattern: LOB signal fires after absorption, not at onset

## Root cause

Every LOB-derived entry attempted so far that uses a confirmation condition (price has already moved a little, acceleration already peaked, surface-depth divergence already visible with positive return) fires **structurally late** — at the point where the order-book pressure has been absorbed into price and the market is set to revert. The confirmation requirement is intended to filter noise but instead selects post-absorption ticks.

## Evidence

| Strategy | Signal | Confirmation filter | Outcome |
|---|---|---|---|
| strat_0005 / 0006 mean_reversion | ret50 > threshold | wait for reversal sign | fires after reversal exhausted (lesson_005) |
| strat_0009 lob_pressure_acceleration | imbalance acceleration > 0.15 | mid flat | fires at peak imbalance, reversal follows (lesson_007) |
| strat_0011 obi_surface_depth_divergence | obi(3)-obi(10) > 0.10 | mid_return_bps(5) in (0,5] | fires after absorption leg is already live (lesson_009) |

Win rate = 0% and best trade is a loss in all three cases. Pre-fee PnL is negative, ruling out fees as the sole cause — the signal direction itself is wrong.

## Root mechanism

Order book imbalance and surface-depth divergence are *coincident* with, not *leading*, price movement at tick scale on 005930 (Samsung intraday). By the time the condition is observable and confirmed, queue replenishment and market-maker response have already reversed the initial pressure.

## Escape routes (in order of estimated leverage)

1. **First-cross / onset detection**: Require that the signal *just crossed* the threshold (was below it N ticks ago, above it now) rather than sustaining above it. This targets the arrival of new information, not its saturation.

2. **Fade the signal**: Enter in the direction *opposite* to the observed imbalance/divergence when it collapses from a local peak. This explicitly targets absorption-driven reversion.

3. **Price-flat entry gate**: Allow entry only when mid_return_bps(lookback) == 0 — divergence exists but price has not yet moved — so the trade targets the absorption leg itself rather than the post-absorption reversion.

4. **Longer-horizon aggregation**: Aggregate the signal over 50–100 ticks and require a sustained imbalance regime (e.g., mean obi > 0.2 for 50 consecutive ticks) before entering, targeting structural order flow rather than transient spikes.

## Anti-patterns to avoid

- Do NOT use short positive return as an entry confirmation for a momentum signal — it selects post-absorption.
- Do NOT stack imbalance conditions (e.g., acceleration + level threshold) if both require the signal to be already elevated; stacking increases selectivity but does not shift the firing time earlier.
- Do NOT assume 0% win rate is solely a fee problem — check pre-fee PnL per roundtrip first. If it is also negative, the signal direction is wrong and fee reduction alone cannot save the strategy.
