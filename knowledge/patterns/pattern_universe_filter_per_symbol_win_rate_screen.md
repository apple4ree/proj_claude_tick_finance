---
id: pattern_universe_filter_per_symbol_win_rate_screen
created: 2026-04-14T00:00:00
tags: [pattern, universe, krx, win-rate, symbol-heterogeneity, methodology, breakeven, declining-symbol, regime-filter]
severity: high
lessons:
  - "[[lesson_20260414_020_symbol_heterogeneity_4_of_10_krx_symbols_structurally_below_win_rate_breakeven]]"
  - "[[lesson_20260414_023_000660_concentration_masks_4_symbol_drag_pooled_avg_hides_a_2_symbol_viable_core]]"
  - "[[lesson_20260415_014_passive_bid_fills_on_declining_symbols_are_toxic_universe_quality_gate_needed]]"
---

# Pattern: Per-symbol win-rate screen required before universe inclusion

## The failure mode

Pooling results across a heterogeneous symbol universe masks per-symbol structural
losers. In strat_0022 (top10), 4 of 10 KRX symbols had win rates of 14-29% against
a 35.5% breakeven threshold, dragging the pooled rate from ~40% (viable 6 symbols)
down to 32.7% (below breakeven). The strategy appeared unprofitable by pooled metrics
but was actually profitable on the sub-universe that met the threshold.

## Why symbols diverge structurally

KRX equity symbols vary significantly in:
- **Realized spread vs tick size**: Thin-book symbols (010140 at 28,825 KRW per tick,
  35420 NAVER) have wider realized spreads that make 150 bps targets harder to reach.
- **Intraday volatility regime**: Low-volatility symbols rarely provide enough
  directional movement within a session to fill a resting SELL LIMIT at +150 bps.
- **Liquidity depth**: Symbols where the BUY LIMIT entry fills but price reverts
  immediately (book absorbs rather than continues) systematically fail the profit target.

None of these are fixable by tightening the entry gate — they are structural properties
of the instrument, not of the signal.

## Mandatory pre-run universe screen

Before including a symbol in a resting-limit strategy universe:

1. **Measure per-symbol win rate on 2-3 IS dates** with the same profit/stop params.
2. **Exclude any symbol with win rate < (breakeven_W - 5%)** as a safety margin.
   For 150/50 bps: breakeven_W = 35.5%, so exclude symbols below 30%.
3. **Document excluded symbols and their win rates** in the spec `description:` field
   so future iterations do not re-include them without a parameter change.
4. **Never pool win_rate_pct across heterogeneous symbols** without per-symbol breakdown.
   A single structural loser with many trades can sink the pooled EV.

## KRX top10 reference screen (from strat_0022, 150/50 bps params, 8 IS dates)

| Symbol | Win Rate | Status            |
|--------|----------|-------------------|
| 010140 | 14.3%    | EXCLUDE (below 30%)|
| 035420 | 16.7%    | EXCLUDE (below 30%)|
| 005380 | 20.0%    | EXCLUDE (below 30%)|
| 272210 | 28.6%    | EXCLUDE (below 30%)|
| 006800 | ~40%     | INCLUDE           |
| 042700 | ~40%     | INCLUDE           |
| 015760 | ~40%     | INCLUDE           |
| 034020 | 20.0%    | EXCLUDE (strat_0024: win_rate<30%)|
| 000660 | ~40%     | INCLUDE           |
| 005930 | 33.3%    | EXCLUDE (3x confirmed: strat_0023/24/25 all below 35.5%)|

This screen is param-specific: changing profit_target_bps or stop_loss_bps changes
the breakeven_W and may shift which symbols qualify. Re-screen if params change by
more than 25 bps on either side.

**Update (strat_0025, 2026-04-14)**: 005930 confirmed EXCLUDE — 33% win rate across strat_0023, _0024, _0025 (3 consecutive iterations). 034020 also EXCLUDE (20% win rate in strat_0024). The viable pass-through universe for 150/50 bps resting-limit is now: **006800, 042700, 015760, 000660** (4 symbols). 000660 is the primary driver (+4.78% in strat_0025); focus future iterations on it first.

## Actionable rules

- **Rule 1**: Never launch a multi-symbol strategy without a 1-iteration per-symbol
  win-rate measurement. This costs one iteration but prevents 2-3 iterations of
  diluted results from pooled losers.
- **Rule 2**: When upgrading a strategy (e.g., removing time exit), preserve the
  same symbol filter from the prior screen — do not re-expand to top10 prematurely.
- **Rule 3**: Symbol re-inclusion requires a structural explanation for why the
  symbol will now clear breakeven (e.g., wider profit target, different entry gate).
  "It might work now" is not a justification.
- **Rule 4 (strat_0016, iter 16)**: Per-symbol WR screen is necessary but not sufficient.
  Also require a positive IS buy-hold return before including a symbol. A symbol with
  -6% buy-hold return during the IS window is in a downtrend; passive BID fills will
  accumulate at successively worse levels with no recovery. The vol gate (min_entry_volume)
  does NOT screen for directional regime — a declining symbol can pass the volume check
  while delivering 0W/8L outcomes. Minimum screen: buy_hold_return > 0% over IS window.
  Preferred screen: VWAP > open by the time of first entry (intraday trend gate).

## Anti-patterns

- DO NOT use "top10" universe shorthand for resting-limit strategies without
  per-symbol pre-screening. Top10 = liquidity rank; it does not imply win-rate viability.
- DO NOT expand back to 10 symbols after narrowing to 6 unless params changed enough
  to plausibly shift the excluded symbols above the new breakeven threshold.
- DO NOT interpret a high pooled win rate as evidence all symbols contribute positively.
  Always decompose by symbol before evaluating strategy viability.

**Update (strat_0026, 2026-04-14)**: 2-symbol [000660, 006800] concentration with OBI=0.35 confirmed — avg_return=+0.0262% (4× strat_0025, best in series). 000660 generates 14× per-trade KRW vs 006800 at equal lot_size=1. New implication: **symbol inclusion is necessary but not sufficient** — once the viable universe is identified, lot_size must be asymmetric to reflect per-symbol payoff magnitude, not just win rate. See [[lesson_20260414_024_tighter_obi_4x_return_gain_000660_payoff_magnitude_dwarfs_006800_revealing_lot_scale_asymmetry]].
