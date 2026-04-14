---
id: lesson_20260414_010_mode_d_overtrading_loose_entry_condition_saturates_on_regime_dominated_days
created: 2026-04-14T07:40:11
tags: [lesson, overtrading, entry-saturation, regime-descriptor, mode-d, fees, microprice]
source: strat_20260414_0012_microprice_flat_onset_v1
metric: "return_pct=-42.1 trades=1805 fees=3483652"
---

# Mode D overtrading: loose entry condition saturates on regime-dominated days

Observation: When entry conditions are individually weak and the market is in a strong regime (here bid-heavy with median imbalance=+0.467), all conditions can be simultaneously true for the majority of ticks. microprice > mid is nearly always true on a bid-heavy day; abs(mid_return_bps(5)) < 1 bps is satisfied between every tick move. Result: 902 roundtrips in one session, fees (3.48M KRW) dwarfing any possible edge.

Why: Each condition looked plausible in isolation but none requires a genuine state CHANGE. Microprice > mid reflects the persistent regime, not a fresh signal. Flat-price gate is trivially satisfied at sub-tick resolution. Neither is an event; both are background conditions.

How to apply next: After verifying >=100 qualifying ticks (Mode C check), add a Mode D check: qualifying ticks must be < 20% of total ticks. If a condition qualifies on >20% of ticks it is a regime descriptor, not a signal. Prefer conditions tied to a detectable transition (e.g., imbalance crossing a threshold, not imbalance exceeding a level).
