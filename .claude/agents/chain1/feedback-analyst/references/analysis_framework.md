# Analysis Framework — feedback-analyst

Mandatory decision tree and diagnostic recipes. All feedback outputs must trace back to entries here.

> **2026-04-27 paradigm shift**: Backtest mode = `regime_state` (default). Decision tree below has been extended with regime-state sanity checks. Read `_shared/references/cheat_sheets/regime_state_paradigm.md` first for context.

---

## Regime-state sanity checks (run FIRST, before headline triage)

When `result.backtest_mode == "regime_state"`, run these BEFORE the WR-based decision tree:

| Trigger | Recommendation | Rationale |
|---|---|---|
| `aggregate_signal_duty_cycle > 0.95` | `swap_feature` | Buy-and-hold artifact — signal almost always True, regimes degenerate to one-per-session holds. Replace primitive with one having meaningful temporal toggling. |
| `aggregate_n_regimes / n_sessions < 1.5` | `loosen_threshold` | Signal too rare to validate. Lower threshold or simplify formula. |
| `aggregate_mean_duration_ticks < 5` AND `aggregate_n_regimes > 100` | `add_filter` | Signal flickering — too noisy to support stable holding. Add regime gate or rolling smoother. |

These three checks REPLACE any other recommendation when triggered.

### Target metric ranges (regime-state, per `regime_state_paradigm.md`)

| Metric | Healthy range |
|---|---|
| `signal_duty_cycle` | 0.05 – 0.80 |
| `n_regimes / sessions` | 5 – 50 |
| `mean_duration_ticks` | 20 – 5000 |
| `WR` | ≥ 0.55 |
| `expectancy_bps` | ≥ 28 (KRX deployable) |

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

---

## Post-fee deployment sanity (NEW, 2026-04-23)

Chain 1 measures raw expectancy (mid-to-mid, no fees). Chain 2 will later apply execution costs (spread + taker fee + KRX sell_tax ≈ **30 bps RT** for KRX cash equity). A signal with raw expectancy +10 bps is still **−20 bps post-fee** — not deployable.

To make feedback useful for the downstream `signal-improver`, compute per-trade win/loss **magnitudes** (not just WR and expectancy):

```
avg_win_bps  = sum_win_bps  / n_wins
avg_loss_bps = sum_loss_bps / n_losses
```

Note: `sum_loss_bps` is stored as a positive number in our schema (absolute value).

### Fee budget reference (KRX cash equity, our deployment market)

| Component | bps |
|---|---|
| Taker fee (entry + exit) | 3 |
| Sell tax (매도 시) | 20 |
| Half-spread × 2 (taker cross both sides) | ~7 |
| **Total RT fee** | **~30** |

For `net_pnl > 0` deployment-feasibility, we need either:
- **avg_win_bps ≥ 30** (each winning trade individually covers fee), OR
- `(2·WR − 1) × avg_win − 2·(1−WR)·avg_loss > 30` (portfolio math; high-WR + small-loser payoff)

### Deployment viability tag

Add ONE of the following tags to `concerns` or `recommended_direction_reasoning`:

| Tag | Condition | Interpretation |
|---|---|---|
| `deployable_post_fee` | `avg_win_bps ≥ 30` | Single winning trade covers fee. Strong candidate for Chain 2. |
| `marginal_post_fee`   | `15 ≤ avg_win_bps < 30` | Wins partially cover fee; needs Chain 1.5 (exit policy) or Chain 2 (maker) to push post-fee positive. |
| `capped_post_fee`     | `avg_win_bps < 15` | Wins cannot cover fee even in principle. Any WR improvement cannot rescue this signal for KRX. Paradigm is wrong for this market. |

### How the tag steers `recommended_next_direction`

Override or augment the headline triage above:

- **`capped_post_fee`** → **prefer `change_horizon` over `tighten_threshold`**. Reasoning: tightening threshold raises WR but does not change avg_win (|Δmid| distribution). Only longer horizon stretches avg_|Δmid|. (Exception: retire if horizon sweep already shows no |Δmid| scaling.)
- **`marginal_post_fee`** → **prefer `add_filter` / `change_horizon`**. Tag: `signal works but magnitude insufficient — requires regime-gating to isolate high-magnitude subset`.
- **`deployable_post_fee`** → **prefer `combine_with_other_spec`**. Tag: `signal already economically strong — portfolio diversification gives Sharpe uplift`.

### Example diagnosis flow

Observed metrics for a candidate spec:
```
n_trades = 1,661, WR = 0.948, expectancy = +12.98 bps
sum_win_bps = 22,500 (over 1,575 wins)
sum_loss_bps = 1,550 (over 86 losses)

→ avg_win_bps = 22,500 / 1,575 = 14.3 bps
→ avg_loss_bps = 1,550 / 86 = 18.0 bps
→ Tag: `capped_post_fee` (avg_win < 15)
→ Recommendation: `change_horizon` to 100 ticks to test if avg_win scales
```

### Note on raw expectancy vs net expectancy

Raw expectancy `= E[signed_bps]` does not guarantee post-fee profit. It is perfectly possible (and common) to have raw expectancy +5 bps where the signal is **fundamentally capped** at 20 bps avg_win, making KRX deployment impossible regardless of further Chain 1 refinement.

This is why feedback-analyst must emit the viability tag — it tells signal-improver which axes of mutation are **worth spending iteration budget on** and which are **dead ends**.
