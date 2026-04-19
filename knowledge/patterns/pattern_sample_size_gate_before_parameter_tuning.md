---
id: pattern_sample_size_gate_before_parameter_tuning
tags: [pattern, methodology, sample-size, lot-sizing, krx, win-rate, adverse-selection, iteration-stagnation]
severity: high
created: 2026-04-15T00:00:00
links:
  - lesson_20260415_006_widening_target_degrades_wr_faster_than_it_improves_payoff_use_lot_size_to_amortize_fees_instead
  - lesson_20260414_012_two_stage_state_machine_over_qualifies_entry_near_zero_trade_count_makes_signal_unvalidatable
---

# Pattern: Sample-size gate — expand trade count before parameter tuning

## Root cause

When a strategy has a one-entry-per-symbol-per-session structure with 2 symbols across 8 IS days,
the maximum achievable roundtrip count is 16. In practice this yields N=15, giving a 95% confidence
interval on win rate of ±12 percentage points (binomial). This is too wide to distinguish edge from
noise: a measured WR of 46.7% spans 34–60%, which straddles the breakeven WR of 53.6% for this
fee structure. No amount of parameter tuning (lot_size, OBI threshold, profit target) can collapse
this confidence interval — only more trades can.

The iteration loop stalls when agents respond to N=15 data by tuning parameters (lot_size 2→3 in
iter 8→9) rather than by expanding trade count. This is the local minimum trap.

## Observed evidence

| Iteration | Change | N trades | WR | 95% CI (±pp) | Net return |
|---|---|---|---|---|---|
| iter 8 | lot_size=2 + CANCEL | 15 | 46.7% | ±12 | +0.10% |
| iter 9 | lot_size=3 (scale only) | 15 | 46.7% | ±12 | +0.16% |

Two consecutive iterations with identical statistical profile — only nominal PnL scaled.
Parameter tuning cannot move beyond this without more observations.

## Minimum viable sample size for KRX resting-limit strategies

With KRX's 21 bps round-trip fee floor and the current 150/50 bps profit/stop ratio:
- Breakeven WR = 53.6%
- Minimum detectable edge (true WR of 55%) requires N ≥ 40 roundtrips for 80% power
- Minimum recommended for publication-grade inference: N ≥ 50 roundtrips

**Rule**: Do NOT tune lot_size, OBI threshold, profit target, or stop loss until N_roundtrips >= 30
measured on a stable strategy (same entry/exit logic, same universe). If N < 30, the next
iteration must prioritize expanding trade count — not tuning parameters.

## Paths to expand trade count (ordered by risk)

### Path 1 — More symbols (lowest risk, recommended first)
Add symbols with known positive characteristics from prior analysis. Current viable candidates:
- 000660 (confirmed: WR ~47%, avg_win ~111bps, avg_loss ~83bps across 8 IS days)
- 006800 (marginally positive — test in isolation before committing capital)
- Untested from TOP10: 272210 (HD현대, 145,650 KRW), 034020 (두산에너빌, 106,150 KRW)
  These have mid-range prices (similar fee structure to 006800) and high tick count.
  Run them with lot_size=1 in a 4-symbol universe to get 32 max roundtrips.

**Critical**: Before adding a symbol, verify it has OBI > 0.35 firing rate comparable to 000660.
Use `pattern_spec_calibration_failure_wastes_iteration` Mode C check.

### Path 2 — Multiple sessions per day (medium risk)
Allow 2 entries per symbol per day on the same OBI signal logic. Risk: adverse selection
compounds if two entries both fill on pullbacks the same day. Cap at max_position_per_symbol=2.
Only viable if first-entry WR can be measured independently from second-entry WR.

### Path 3 — Relax OBI threshold (medium risk, tested: non-productive)
Lesson_025 confirmed that loosening OBI 0.35→0.32 produced ZERO additional trades because
total_imbalance_threshold=0.20 was the binding constraint. Removing total_imbalance_threshold
entirely is the correct test — but this risks Mode D overtrading (pattern_spec_calibration_failure).

## Adverse selection: the WR ceiling problem

The current WR of 46.7% is below the breakeven of 53.6%. This gap is not random noise with N=15
(a 7pp gap is one standard deviation at N=15). The structural cause is adverse selection at entry:
passive BID fill means the price was FALLING toward our bid. The strategy is entering on pullbacks.

**Structural signature of adverse selection**: avg_win (111 bps) > avg_loss (83 bps) BUT WR < 50%.
This means we hold long through larger up-moves than down-moves (consistent with resting limit that
waits for recovery), but we enter on MORE losing than winning trades because the entry itself
selects for declining price moments.

**Fix for adverse selection** (to attempt once N >= 30):
- Entry confirmation: require OBI > threshold to persist for 3+ consecutive ticks before entry
- Entry price shift: enter at mid or mid+1tick rather than passive bid (reduces fill rate but
  selects for rising-price-crossing-our-limit rather than falling-price-hitting-our-bid)
- Time-of-day filter: exclude first 30 min and last 30 min (highest adverse selection periods)

## Pre-iteration checklist (append to pattern_spec_calibration_failure checklist)

7. **Sample size check**: If n_roundtrips < 30 in the prior iteration, the next iteration MUST
   expand trade count (more symbols, relaxed threshold, or multiple entries/day). Do NOT change
   lot_size, profit target, or stop loss until n_roundtrips >= 30.
8. **Confidence interval check**: Compute 95% CI on WR using binomial formula. If the CI spans
   the breakeven WR, the measured WR is not statistically distinct from breakeven. Report this
   in the lesson and flag the next ideation to focus on sample size, not parameter tuning.
