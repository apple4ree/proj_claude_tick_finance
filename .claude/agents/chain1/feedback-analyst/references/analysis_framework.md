# Analysis Framework — feedback-analyst

Mandatory decision tree and diagnostic recipes. All feedback outputs must trace back to entries here.

---

## Step-by-step diagnosis

### (a) Headline triage

| Pattern | Interpretation |
|---|---|
| `n_trades < 30` | Under-powered; recommend `loosen_threshold` |
| `n_trades ≥ 30, WR ∈ [48%, 52%]` | No signal; recommend `swap_feature` or `retire` |
| `n_trades ≥ 30, WR > 55%, expectancy > 0` | Candidate edge; recommend `tighten_threshold` to confirm, or `combine_with_other_spec` |
| `WR > 80%, n_trades < 100` | Probably selection/overfit; recommend `tighten_threshold` at different symbol |
| `WR > 60%, expectancy < 0` | Asymmetric payoff problem; flag but note: under execution=1 exit=1tick, this is unusual. Investigate delta_mid distribution |

### (b) Per-symbol split

Compute `std(per_symbol.wr)`. Let `σ = std_pct`.

| `σ` | `cross_symbol_consistency` | Interpretation |
|---|---|---|
| `σ < 2` | `consistent` | True cross-symbol edge |
| `2 ≤ σ ≤ 10` | `mixed` | Symbol-dependent; consider filter by regime or symbol-specific threshold |
| `σ > 10` OR sign-flip across symbols | `inconsistent` | Probably symbol-specific noise; recommend `drop_feature` or restrict universe |

### (c) Win/loss bucket insight (requires trace data)

If trace parquet available, bucket wins and losses by:
- Spread regime (narrow vs wide half of sample)
- Signal magnitude (near-threshold vs deep-threshold)
- Time-of-day (open, mid, close thirds)
- Volatility regime (realized vol past 100 ticks)

Identify the strongest "asymmetry" — a bucket where wins concentrate disproportionately. Cite in `win_bucket_insight`.

If trace data unavailable: set insight to `"trace not available"` and do not fabricate patterns.

### (d) Trend detection

If `recent_feedback` has ≥ 2 entries for the same lineage (same `parent_spec_id` chain), compute WR delta per iteration. A declining trajectory across 3+ iterations → recommend `retire`.

## Decision tree for `recommended_next_direction`

Branch on (n_trades, WR, cross_symbol_consistency):

```
IF n_trades < 30:
    → loosen_threshold
ELIF WR ∈ [48%, 52%] AND n_trades ≥ 300:
    → swap_feature (if first attempt at this family) OR retire (if ≥3 retries)
ELIF cross_symbol_consistency == "inconsistent":
    → drop_feature   (restrict universe or retire — see reasoning)
ELIF WR ≥ 55% AND n_trades ≥ 100 AND expectancy_bps > 0:
    IF we have ≥ 2 other co-eligible specs in this iteration:
        → combine_with_other_spec
    ELSE:
        → tighten_threshold
ELIF WR ≥ 60%:
    → add_filter  (narrow to higher-confidence tick set)
ELSE:
    → change_horizon  (try horizon 2..5 ticks if current = 1)
```

## Recommendation semantics

- `tighten_threshold`: raise threshold by 20-50% to improve WR at cost of trade count
- `loosen_threshold`: lower by 20-50% to raise trade count (when n_trades < 30)
- `add_filter`: introduce AND-clause with spread_bps or volatility
- `drop_feature`: remove one primitive from a compound formula
- `swap_feature`: replace primary primitive with a different whitelisted one
- `change_horizon`: increase prediction_horizon_ticks (typically 1 → 5 → 20)
- `combine_with_other_spec`: propose Chain 1 ensemble in next iteration (orchestrator will coordinate)
- `retire`: do not mutate further; mark RETIRED in prior_iterations_index.md

## Output quality rules

- `strengths` list: empty if none (do not fabricate). Maximum 3 entries.
- `weaknesses` list: minimum 1 entry (if the spec were perfect it wouldn't be in iteration). Maximum 4.
- `recommended_direction_reasoning`: must name the primary driving number (e.g., "WR=52.3% over 412 trades is indistinguishable from random walk, so swap_feature").
- `win_bucket_insight` / `loss_bucket_insight`: always required. Use `"trace not available"` if data missing.
