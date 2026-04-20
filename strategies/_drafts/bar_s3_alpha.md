---
stage: alpha
name: bar_s3_eth_vol_breakout
created: 2026-04-17
target_symbol: ETHUSDT
target_horizon: daily
paradigm: breakout
signal_brief_rank: null
deviation_from_brief: null
---

# Alpha Design: bar_s3_eth_vol_breakout

## Hypothesis

ETH daily price exhibits momentum continuation after a close above its 20-day highest high
that is simultaneously confirmed by a volume surge (>1.2x 20-day mean), with an ATR-based
volatility contraction precondition ensuring the breakout fires from a coiling range rather
than from an already-extended trend; this combination distinguishes genuine structural
breakouts from exhaustion-top false positives, generating positive expected return over the
next 3-10 days that exceeds the 10 bps round-trip fee.

## Why Breakout, Not Trend-Follow or Mean-Reversion

S1 (bar_s1_sol_vol_momentum) is trend_follow: it rides an existing trend and exits when
momentum cools. S2 (bar_s2_btc_bb_dip_reversion) is mean_reversion: it buys weakness
expecting snap-back. S3 fills the diversification gap with a breakout paradigm: it buys
strength specifically at the moment a range resolves upward, anticipating the NEW leg rather
than riding an old one (S1) or reverting from an extreme (S2).

The portfolio benefit: breakout entries are anti-correlated with dip-reversion entries —
S2 enters when price is weak (near BB lower), S3 enters when price is strong (new high).
They will rarely both be in-position simultaneously, distributing drawdown periods.

## Key Design Insight — Avoiding the Exhaustion-Top Trap

Lesson 017 (transition-based signals fire at informationally neutral points) specifically
describes a ROLLING HIGH BREAKOUT on tick data that entered at the LOCAL TOP: 132 trades,
12.1% win rate. The root cause was that a rolling-high cross fires at the tick the move is
already complete.

At daily-bar resolution this concern manifests differently. The fix at daily scale is:

1. **Volatility contraction precondition (coiling filter)**: require that ATR(14) today is
   below its own 20-day moving average. A breakout from a coiling range (falling ATR) has
   measurably higher follow-through than a breakout from an already-high-vol environment
   where the "new high" is just noise in an existing explosion. This is the structural
   difference between a genuine range-expansion breakout vs an exhaustion spike.

2. **Volume confirmation**: require volume > 1.2x 20-day mean. Without committed buying
   volume, a new daily close-high is a thin market drift, not conviction. Volume > 1.2x
   removes the lowest-commitment false breakouts without being so restrictive that it fires
   only 1-2 times per year (that was S1's 3-condition AND problem at 3% exposure).

3. **Entry at next-day open, not the breakout close**: to prevent lookahead, signal is
   evaluated on the prior day's close; entry fires at the next day's open. The trade is
   NOT capturing the original breakout bar's return — it is participating in the continuation
   that follows when a genuine range-expansion attracts momentum buyers over the next
   several days.

## Market Context

- Domain: Binance spot ETHUSDT, daily OHLCV bars
- ETH buy-hold IS Sharpe = 1.18 (given); target IS Sharpe > 0.8
- ETH buy-hold OOS Sharpe = 0.21 (given); strong motivation to time entries rather than hold
- Target exposure: 20-40% of trading days (entry selectivity ≈ 1 signal per 8-15 trading days)
- Regime: long-only with cash parking (no short); rebalance daily at close/open boundary
- ETH vs SOL/BTC rationale: ETH is the diversification slot — distinct ecosystem, distinct
  vol structure, and the breakout paradigm is a third mechanism vs S1's trend and S2's dip

## Entry Condition

Enter long at the NEXT day's open when ALL three conditions hold on the prior day's close:

1. **Donchian breakout** (primary signal):
   `close[-1] > max(high[-21:-1])`
   — Prior day's close exceeded the highest HIGH of the prior 20 trading days (20-day Donchian
   channel upper, computed over prior 20 bars EXCLUDING the current bar). This confirms
   the range has been decisively breached.

   Implementation note: `max(high[-21:-1])` means the rolling 20-bar maximum of HIGH prices,
   not just closes, over the 20 bars preceding the current signal bar. Using HIGH (not close)
   for the channel makes the breakout confirmation stronger — price closed above where even
   intraday extensions had reached previously.

2. **Volatility contraction precondition** (coiling filter):
   `ATR(14)[-1] < ATR(14).rolling(20).mean()[-1]`
   — The 14-day Average True Range on the breakout day is below its own 20-day simple
   moving average. This is the coiling-range filter: when ATR is below its recent average,
   the market has been compressing, and the breakout fires from a spring-loaded state.
   When ATR is already above its average (vol already elevated), the "new high" is likely
   an exhaustion move in an already-volatile environment.

3. **Volume confirmation** (participation gate):
   `volume[-1] > 1.2 * volume.rolling(20).mean()[-1]`
   — Prior day's volume exceeded 1.2x the 20-day trailing mean. The multiplier of 1.2
   (vs S1's 1.5) is intentionally lower because ETH breakouts are generally accompanied
   by less dramatic volume surges than SOL. At 1.5x, ETH breakouts would fire <5 times
   per year; at 1.2x, expected frequency is 8-15 times per year, putting IS exposure in
   the 20-40% target window (assuming ~5-day average hold).

Exit to cash when the execution-designer determines (see Constraints below); the alpha
signal rationale is that the breakout continuation period is 3-10 days, targeting at
minimum the prior range width as a price target.

## Signals Needed

- `donchian_high_20`: `high.shift(1).rolling(20).max()`
  — Rolling 20-bar maximum of HIGH prices, shifted by 1 to exclude the current bar (no lookahead)
- `atr_14`: standard ATR(14) from OHLC — `mean(abs(high-low), abs(high-prev_close), abs(low-prev_close))` over 14 bars
- `atr_14_ma20`: `atr_14.rolling(20).mean()` — 20-bar MA of ATR(14)
- `vol_ratio_20`: `volume / volume.rolling(20).mean()` — volume vs 20-day mean
- Composite entry signal: `(close > donchian_high_20) & (atr_14 < atr_14_ma20) & (vol_ratio_20 > 1.2)`

All inputs are standard OHLCV pandas operations. ATR requires a small helper (~5 lines);
no custom primitives beyond standard pandas/numpy.

## Exposure Estimate

ETH daily data with 2-year IS (~500 bars):
- Donchian 20-bar breakouts (close > 20-bar high): ~30-50 per year under typical conditions
- After coiling filter (ATR < ATR_MA20): filters ~50% → ~15-25 per year  
- After volume filter (vol > 1.2x): filters ~30-40% of remaining → ~10-18 signals per year
- Expected 10-18 signals over 2-year IS = 20-36 total entry events
- At average hold 5-7 days: 100-250 held days out of 500 = 20-50% exposure
- This meets the 20-40% target (with execution-designer able to tune via hold duration)

## Why Donchian Channel (Not ATH, Not MA Cross)

- All-time high breakout: too rare at daily scale (fires 1-3x per year in a bull, never in a bear)
- MA cross (e.g., 50/200): fires too slowly — the breakout is already old news by the time
  the 50-day MA crosses above the 200-day MA; this is the Lesson 017 exhaustion problem
  scaled to daily bars
- Donchian 20-bar (1-month range): a 20-bar new high is concrete, measurable, and fires
  early enough in a new move that continuation is likely, while being far enough above
  recent price that it represents genuine new territory, not noise

## Why ETH Specifically (Not BTC Again or SOL Again)

- S1 = SOLUSDT (trend_follow); S2 = BTCUSDT (mean_reversion); S3 = ETHUSDT (breakout)
- ETH has a distinct ecosystem cycle: DeFi/staking catalysts create ETH-specific breakouts
  that are not just BTC beta; this reduces correlation between S3's entries and S2's
- ETH buy-hold OOS Sharpe = 0.21 vs IS = 1.18 means buy-hold degrades severely out-of-sample;
  a breakout-timing strategy that sits in cash during non-breakout periods specifically
  avoids the periods that likely drove this OOS degradation (sustained decline / choppy range)
- ETH vol is intermediate between BTC (low) and SOL (high), making the coiling ATR filter
  more informative than it would be on BTC (too smooth) or SOL (too noisy)

## Portfolio Diversification Rationale

| Strategy | Symbol | Paradigm | Entry Trigger | Entry Context |
|----------|--------|----------|---------------|---------------|
| S1 | SOLUSDT | trend_follow | sustained momentum + low vol | ongoing uptrend |
| S2 | BTCUSDT | mean_reversion | BB lower touch + uptrend intact | weakness within uptrend |
| S3 | ETHUSDT | breakout | new 20-day high + coiling + volume | range resolution |

S3 entries (new high breakout) are structurally orthogonal to S2 entries (near-lows dip).
Combined, S1+S2+S3 cover: trend continuation, dip recovery, and range expansion breakout
— three uncorrelated entry mechanisms across three different tokens.

## Knowledge References

- Lesson 017 (transition-based signals fire at exhaustion): directly addressed via the
  coiling ATR precondition, which ensures the "new high" fires from a compressed state,
  not from an already-extended move. A breakout from below-average ATR is NOT an exhaustion
  signal — it is a range-expansion onset.
- Lesson 005 (mean-reversion entry too late after absorption): avoided by design — breakout
  is explicitly a momentum continuation design, not a reversion
- bar_s1 (trend_follow): the 3-condition AND at S1 over-filtered to ~3% exposure; S3
  uses 3 conditions but with a lower volume threshold (1.2x vs 1.5x) to target 20-40%
  exposure instead
- bar_s2 (mean_reversion): deliberately contrasted — S2 buys weakness (close <= BB_lower),
  S3 buys strength (close > Donchian_high_20); they anti-correlate on entry timing

## Constraints Passed To Execution-Designer

- Signal computed at prior day's close; entry must execute at next day's OPEN (no lookahead)
- Warmup: minimum 50 bars required before first signal (need ATR_MA20 = ATR(14) + 20-day MA)
- Primary exit rationale: the breakout continuation typically spans 3-10 days; a time-based
  exit shorter than 3 days will systematically truncate winners (same lesson as S1)
- Natural profit target anchor: the prior 20-day range width projected above the breakout
  level (i.e., entry price + Donchian range width), which is the classic measured-move
  target for a channel breakout
- Do NOT use a stop-loss tighter than 1x ATR(14) at entry: sub-ATR stops on a
  volatility-contraction breakout will trigger on the normal post-breakout retest before
  continuation begins
- Fee is 10 bps round-trip; typical ETH breakout continuation is 3-8%, making fee cost
  ~1-3% of expected profit — fee is not a binding constraint at daily horizon
- Position sizing: binary (full-long or cash) for v1; execution-designer may explore
  scaling with distance above Donchian channel
- Short extension (short on Donchian lower channel break) is DEFERRED — long-only first

```json
{
  "name": "bar_s3_eth_vol_breakout",
  "hypothesis": "ETH daily price exhibits momentum continuation after closing above its 20-day Donchian high when ATR(14) is below its 20-day mean (coiling precondition) and volume exceeds 1.2x the 20-day mean; rank-N/A from signal_brief (daily-bar domain, no LOB brief applicable), this genuine range-expansion breakout — distinguished from exhaustion by the coiling filter — generates positive EV over the following 3-10 days well above the 10 bps round-trip fee, targeting IS Sharpe > 0.8 with 20-40% exposure.",
  "entry_condition": "Enter long at next-day open when ALL hold at prior close: (1) close > max(high over prior 20 bars) — Donchian 20-bar upper breakout; (2) ATR(14) < 20-day MA of ATR(14) — coiling precondition, volatility was contracting before the breakout; (3) volume > 1.2x 20-day volume mean — participation confirmation. All three must be true simultaneously.",
  "market_context": "Binance ETHUSDT daily OHLCV; IS period (2023-2024 or equivalent); ETH buy-hold IS Sharpe 1.18, OOS 0.21 — strong motivation to time entries; long-only with cash parking; daily rebalance at open. Strategy is agnostic to broader regime — the coiling+volume filter implicitly avoids entering during low-conviction periods.",
  "signals_needed": [
    "donchian_high_20: high.shift(1).rolling(20).max() (20-bar rolling max of HIGH, excluding current bar)",
    "atr_14: ATR(14) = EMA or SMA of true-range over 14 bars (standard OHLC calculation)",
    "atr_14_ma20: atr_14.rolling(20).mean()",
    "vol_ratio_20: volume / volume.rolling(20).mean()"
  ],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "breakout",
  "multi_date": true,
  "parent_lesson": "bar_s1_sol_vol_momentum (S1: trend_follow SOL; S2: mean_reversion BTC; S3: breakout ETH — portfolio diversification across paradigm and asset)",
  "universe_rationale": "ETHUSDT: intermediate vol between BTC and SOL makes coiling ATR filter most informative; DeFi/staking catalysts generate ETH-specific breakouts uncorrelated with pure BTC beta; OOS Sharpe degradation from 1.18 to 0.21 shows buy-hold weakness that timed breakout entry specifically avoids by sitting in cash during non-breakout periods; completes S1+S2+S3 three-paradigm diversified portfolio.",
  "signal_brief_rank": null,
  "deviation_from_brief": "N/A — signal_brief protocol applies to tick-level LOB signals only; this strategy operates on daily OHLCV bars in the Binance crypto domain where no LOB signal brief is generated.",
  "target_symbol": "ETHUSDT",
  "target_horizon": "daily",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/bar_s3_alpha.md"
}
```
