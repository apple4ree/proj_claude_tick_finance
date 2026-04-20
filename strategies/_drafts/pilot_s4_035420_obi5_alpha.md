---
stage: alpha
name: pilot_s4_035420_obi5
created: 2026-04-17
signal_brief_rank: 1
symbol: 035420
---

# Alpha Design: pilot_s4_035420_obi5

## Hypothesis

rank-1 from signal_brief: when 5-level order book imbalance (obi_5) on NAVER (035420) exceeds 0.644 at the 95th percentile, sustained buy-side pressure at depth predicts a directional price move over the next 3000 ticks with EV 6.2 bps after 21 bps round-trip fee.

## Market Context

- Symbol: 035420 (NAVER Corp), mid-tier liquidity (rank 3/10 viable in IS universe)
- Session: 09:30 KST onward (block pre-open noise per lesson_20260415_009)
- Regime gate (mandatory, from S3 lesson): 50-tick rolling mid return > 0 before any entry; 035420 must not be in a sustained downtrend — obi_5 long-only entry in downtrend was the primary failure mode in strat_0005 (034020, -6.6% downtrend, 0% WR)
- Volume confirmation (from pattern_post_fill_signal_quality_gates): minimum entry volume gate applied before OBI check; high-OBI / low-volume is the false-positive signature
- Horizon: 3000 ticks forward (brief-optimal); the signal is long-duration, not fleeting

## Entry Condition

1. Time gate: tick timestamp >= 09:30:00 KST (1800 seconds from 09:00:00 open)
2. Trend filter: 50-tick rolling mid_return_bps > 0 (flat or upward bias; blocks downtrend entry)
3. Volume gate: krw_turnover(lookback=50) above session median (confirms genuine conviction behind imbalance, not thin-book artifact)
4. Signal: obi(depth=5) >= 0.644 (brief threshold, no deviation; 95th percentile selectivity, ~5.3% entry rate, n=4942 historical entries)
5. No open position in 035420

All four conditions must hold simultaneously at the same tick. Entry is on the ask side (aggressive limit or marketable).

## Signals Needed

- `obi(depth=5)` — primary entry signal, threshold 0.644
- `mid_return_bps(lookback=50)` — trend filter gate
- `krw_turnover(lookback=50)` — volume conviction gate
- `mid` — reference price tracking

## Universe Rationale

035420 (NAVER) is rank 3/10 in the IS viable symbol set. Targeted here as micro-pilot S4 of 5 to test obi_5 on a mid-tier liquidity symbol distinct from S1-S3 (042700, 010140, 034020). S3 (034020) established the downtrend-failure mode; 035420's obi_5 has the highest EV in the brief (6.2 bps) among viable signals, making it the correct rank-1 pick.

## Knowledge References

- lesson_20260417_004: gate enforcement bugs nullify OBI filters; SIGNAL_REGISTRY evaluation-order must call update_state() before gate check; LIMIT entry preferred to avoid 5ms OBI flip at MARKET fill
- lesson_20260417_003 (S3): spread_bps entry in downtrend = 0% WR; trend filter is non-negotiable for long-only LOB strategies
- pattern_post_fill_signal_quality_gates: volume gate raises WR +11pp; apply before OBI check; thin-book false-positive signature is high-OBI + low-volume
- lesson_20260415_009: block entries before 09:30 KST; opening auction imbalances are noise

## Constraints Passed To Execution-Designer

- Entry valid only while obi_5 >= 0.644 at fill time (signal must hold at actual fill, not just at signal fire — use LIMIT at ask with short TTL so OBI is re-evaluated)
- Brief optimal_exit baseline: pt_bps=79, sl_bps=3, trailing stop dominant (85% of exits in brief are trailing stops — do NOT omit trailing)
- Trend filter (rolling 50-tick mid_return_bps > 0) must be enforced in strategy.py state update BEFORE gate evaluation, not after
- Volume gate must precede OBI gate in the condition chain
- No entry before 09:30 KST (entry_start_time_seconds >= 1800 from midnight = 34200)
- sl_guard_ticks must be included in spec to prevent 5-tick immunity window that inflated S2/S3 SL overshoot
- Entry selectivity is ~5.3% of ticks; do not lower threshold below 0.579 (rank-7, which has EV < 0)

```json
{
  "name": "pilot_s4_035420_obi5",
  "hypothesis": "rank-1 from signal_brief: obi_5 >= 0.644 on 035420 captures sustained 5-level buy-side conviction that predicts a 3000-tick directional move with EV 6.2 bps after 21 bps round-trip fee",
  "entry_condition": "time >= 09:30 KST AND 50-tick mid_return_bps > 0 (trend filter) AND krw_turnover(50) above session median (volume gate) AND obi(depth=5) >= 0.644 AND no open position",
  "market_context": "035420 (NAVER), mid-tier liquidity, flat-to-upward intraday regime only, post-09:30 session, volume-confirmed order book pressure",
  "signals_needed": ["obi(depth=5)", "mid_return_bps(lookback=50)", "krw_turnover(lookback=50)", "mid"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_004_strategy_py_gate_enforcement_bugs_nullify_obi_spread_filters",
  "universe_rationale": "035420 rank-1 brief signal has highest EV (6.2 bps) among 3 viable symbols; S4 of 5 micro-pilot isolating obi_5 on mid-tier liquidity after S3 downtrend failure on 034020",
  "signal_brief_rank": 1,
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/pilot_s4_035420_obi5_alpha.md"
}
```
