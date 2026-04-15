---
id: pattern_post_fill_signal_quality_gates
tags: [pattern, methodology, krx, resting-limit, obi, volume-filter, adverse-selection, exit_management, win-rate, entry-signal, signal-edge, min-hold, settlement-period]
severity: high
created: 2026-04-15T00:00:00
links:
  - lesson_20260415_012_entry_volume_is_the_strongest_win_discriminator_1_7x_higher_volume_at_win_entries_vs_loss
  - lesson_20260415_013_exit_obi_divergence_as_early_exit_signal_for_resting_limit_stops
  - lesson_20260415_014_passive_bid_fills_on_declining_symbols_are_toxic_universe_quality_gate_needed
  - lesson_20260415_015_obi_exit_fires_during_post_fill_settlement_needs_min_hold_guard
---

# Pattern: Post-fill signal quality — two independent WR levers for resting-limit strategies

## Root cause

Strat_0013 and strat_0014 (KRX resting-limit, 4-sym, 10:30-13:00, N=26 and N=15) revealed two
independent signal-quality levers that operate at different points in the trade lifecycle:

1. **Pre-fill gate (entry volume)**: entry volume at WIN trades was 1.47M vs 0.89M at LOSS trades
   (1.7x gap). OBI at entry barely separated outcomes (WIN=0.540, LOSS=0.530, delta=0.010).
   Volume is the dominant entry discriminator; OBI alone is insufficient.

2. **Post-fill monitor (exit OBI)**: after fill, WIN trades exit with avg OBI=-0.370; LOSS trades
   that stop out show avg OBI=+0.520 at exit time. A 0.89-unit divergence in OPPOSITE directions.
   Persistently positive OBI after a long fill signals the reversal has NOT occurred — the position
   is in a momentum regime, not a mean-reversion regime.

These two findings address different loss types:
- The volume gate cuts trades that should never have been entered (thin-book false imbalances).
- The exit OBI monitor converts stop-outs into managed early exits (smaller losses, improved WR).

## Empirical evidence

| Iteration | Change applied | N trades | WR | Return |
|---|---|---|---|---|
| strat_0013 | no volume gate | 26 | 42.3% | +0.169% |
| strat_0014 | min_vol=1M added | 15 | 53.3% | +0.506% |

Adding the volume gate alone: +11pp WR improvement, +3x return, with -42% trade count.
This confirms the volume gate prunes loss trades while retaining win trades.

## Implementation rules

### Rule 1 — Minimum entry volume gate (apply before OBI check)

```yaml
params:
  min_entry_volume: 1_000_000   # total shares traded this bar before entry; tune 800K-1.2M
```

Mechanism: At entry time, check that the most recent N-second or N-tick volume window exceeds
`min_entry_volume`. The purpose is to confirm that the OBI signal reflects genuine conviction
(not a thin-book artifact from sparse overnight residual quotes).

The volume gate should be applied BEFORE the OBI gate in the entry condition chain. A high-OBI,
low-volume setup is the exact false-positive signature.

### Rule 2 — Exit OBI early-exit (monitor post-fill) — CRITICAL: min_hold guard required

**WARNING — strat_0017 failure (iter 17)**: Implementing exit OBI without a `min_hold_ticks`
guard causes the exit to fire on 14/15 positions including winners. Win rate collapsed to 6.7%.

Root cause: A passive BUY LIMIT fills on a down-move. Immediately after fill, the bid book
dominates because the price just moved adversely — OBI is **structurally elevated** in the
settlement window (first 5-10 ticks post-fill) regardless of the position's eventual outcome.
This means OBI is INVERTED as a signal immediately after fill. The threshold=0.40/ticks=3
parameters used in strat_0017 trigger within the settlement window on every fill, converting
future winners into small losses.

**Mandatory implementation with settlement guard:**

```python
# Post-fill monitor pseudocode — CORRECT version
if self._fill_confirmed:
    self._ticks_held[sym] += 1

    # GATE: suppress OBI exit during post-fill settlement window
    if self._ticks_held[sym] < MIN_HOLD_TICKS_BEFORE_OBI_EXIT:
        pass  # do not evaluate OBI exit during settlement
    elif obi_current > EXIT_OBI_THRESHOLD:
        self._obi_persist_count += 1
        if self._obi_persist_count >= EXIT_OBI_CONSECUTIVE:
            # Abort: mean reversion not happening; exit before stop
            submit_market_sell(sym)
            self.fsm_state = "IDLE"
    else:
        self._obi_persist_count = 0
```

Calibrated parameter ranges (from lesson_015):
- `min_hold_ticks_before_obi_exit`: 5-10 ticks (suppresses settlement-window OBI spike)
- `exit_obi_threshold`: 0.55-0.60 (raised from 0.40 — higher to require genuine persistence)
- `exit_obi_ticks`: 8-10 (raised from 3 — require more persistent adverse signal)

Threshold search range after guard is applied: OBI_threshold in [0.50, 0.65], consecutive ticks in [6, 12].

### Rule 3 — Interaction between the two gates

- The volume gate reduces N (fewer entries). This compounds the N=15 thin-sample problem.
  Do NOT apply both gates simultaneously on a 2-symbol universe — expand symbols first.
- The exit OBI early-exit is safe to add to any existing strategy without changing entry count.
  It only affects trades already in-position. Add it FIRST before the volume gate if N is < 30.
- Do NOT implement the exit OBI gate as a new stop-loss type that fires on a single-tick OBI
  reading. Single-tick OBI spikes are noisy. The consecutive-tick requirement is mandatory.

## Ordering recommendations for future iterations

Given the N=15 constraint on strat_0014 (pattern_sample_size_gate rule: N >= 30 before OOS):

**Priority 1**: Expand to 6-8 symbol universe with same vol-gate + time-window spec. Goal: N >= 30
roundtrips to establish statistical footing.

**Priority 2**: Once N >= 30, add exit OBI early-exit as an enhancement layer. Measure delta-WR.

**Priority 3**: After exit OBI is validated, add volume gate tightening (test min_vol=1.2M).

**Priority 4**: Only after N >= 50 on a stable spec: OOS validation on 20260326/20260327/20260330.

## Anti-patterns

- DO NOT tune min_entry_volume on IS data with N < 30. The confidence interval (±12pp at N=15)
  is wider than the WR improvement being sought. Any optimized threshold will be overfit.
- DO NOT use OBI alone as an entry gate. Lesson_012 confirms OBI delta at entry is near-zero
  (0.010 units). Volume is the discriminating variable; OBI is a necessary but not sufficient gate.
- DO NOT implement exit OBI as a stop-loss replacement. The -50 bps stop remains. Exit OBI is an
  override that fires BEFORE the stop for adverse-regime trades. Both must coexist.
- DO NOT treat the 53.3% WR in strat_0014 as confirmed edge. CI at N=15 is ±13pp, spanning
  40-66%. The breakeven is 42.4%. The WR is above breakeven but the CI overlaps — not confirmed.

## Connection to sample-size gate

This pattern does NOT override [[pattern_sample_size_gate_before_parameter_tuning]].
The N >= 30 rule applies before any parameter tuning, including vol threshold and exit OBI threshold.
The exit OBI rule can be added as a structural fix (not a parameter tune) once N >= 30 is met.
