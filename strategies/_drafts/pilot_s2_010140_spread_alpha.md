---
stage: alpha
name: pilot_s2_010140_spread_alpha
created: 2026-04-17
signal_brief_rank: 1
---

# Alpha Design: pilot_s2_010140_spread_alpha

## Hypothesis

When 010140's bid-ask spread widens to the 95th-percentile level (≥17.498 bps), the market is in a temporarily illiquid state that reverts toward tighter spreads over the next ~3000 ticks, generating a positive mid-price drift exploitable long.

## Market Context

- Symbol: 010140 (Samsung Electro-Mechanics, KRX)
- Regime: no explicit regime filter; spread itself is the regime proxy — only trade when spread is wide
- Time: avoid KRX opening noise (09:00–09:30); rest of session valid
- Volume: no additional volume filter required; spread threshold is sufficient selectivity (entry_pct=5.72%)

## Entry Condition

Enter LONG when:
  `spread_bps >= 17.498`

This is a pure threshold cross on a snapshot primitive. No lookback, no slope. Signal fires when current tick's spread_bps is at or above the 95th-percentile historical level. Entry is directional (long), betting that the liquidity vacuum that widens the spread coincides with temporary ask-side softness that reverts.

## Signals Needed

- `spread_bps` (snapshot primitive — available natively)

## Universe Rationale

010140 is in the top-10 KRX liquid universe. Its rank-1 signal has the highest EV (12.47 bps after 21 bps round-trip fee) and highest Sharpe (0.41) among all viable signals in the brief. The wide-spread edge is not present in other pilot symbols at comparable EV, making 010140 the natural single-symbol testbed for this hypothesis.

## Knowledge References

- Iteration 0 (strat_20260417_0001): max_position_exceeded bug on 010140 specifically; execution must cap position carefully.
- Iteration 2 (strat_20260417_0003): bug_pnl artifact from strict force_sell; sl_guard_ticks needed.
- Brief rank-1 exit_mix shows 59% trailing stops — execution-designer must enable trailing.

## Constraints Passed To Execution-Designer

1. Use brief's optimal_exit baseline: pt_bps=79, sl_bps=3; trailing stop is dominant exit (59% of fills) — do NOT omit.
2. sl_bps=3 is very tight; sl_guard_ticks must be set to avoid sl_overshoot invariant violations (lesson from iter 1).
3. Signal is a snapshot condition — entry valid on the tick it fires; no multi-tick confirmation needed.
4. Max 1 position per session on 010140 to avoid max_position_exceeded repeating from iter 0.
5. Entry gate: block 09:00–09:30 (KRX opening noise per knowledge lesson).

```json
{
  "name": "pilot_s2_010140_spread_alpha",
  "hypothesis": "When 010140 spread_bps crosses above its 95th-percentile threshold (17.498 bps), a temporary liquidity vacuum creates a mean-reverting mid-price drift exploitable long over a ~3000-tick horizon — rank-1 from signal_brief.",
  "entry_condition": "Enter LONG when spread_bps >= 17.498 (95th-percentile threshold, rank-1 from signal_brief for 010140)",
  "market_context": "010140 (KRX), any session regime; spread_bps itself proxies the regime — entry only when spread is at 95th-percentile width; block first 30 min (09:00–09:30) per KRX opening noise lesson",
  "signals_needed": ["spread_bps"],
  "missing_primitive": null,
  "needs_python": false,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "strat_20260417_0001_trajectory_multi_3sym: max_position_exceeded on 010140; strat_20260417_0003: sl_guard_ticks needed + trailing stop mandatory",
  "universe_rationale": "010140 rank-1 signal has EV=12.47 bps and Sharpe=0.41 — highest in brief with n=7 viable signals; single-symbol pilot to isolate spread-reversion edge",
  "signal_brief_rank": 1,
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/pilot_s2_010140_spread_alpha.md"
}
```
