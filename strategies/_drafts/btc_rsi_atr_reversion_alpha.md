---
stage: alpha
name: btc_rsi_atr_reversion
created: 2026-04-18
---

# Alpha Design: btc_rsi_atr_reversion

## Hypothesis
When BTCUSDT is in a low-volatility compression regime (ATR/close < median) and RSI(14) is oversold below 35, short-term price displacement is statistically likely to revert within 1–4 bars — exploiting panic-driven dips that lack directional momentum.

## Market Context
- Regime: low 14-bar ATR relative to recent ATR median (compression / consolidation)
- No trending momentum: 20-bar return magnitude < 1.5%
- Time: any hour (crypto 24/7), but signal is more reliable outside weekend volatility spikes
- Volume context: entry volume spike (current bar volume > 1.2x 20-bar rolling mean) confirms genuine panic, not liquidity vacuum

## Entry Condition
Enter LONG on close of a 1h bar when ALL of the following hold:
1. RSI(14) < 35  — price is oversold on short horizon
2. ATR(14) / close < median(ATR(14)/close, 48 bars)  — regime is compressed, not trending
3. close < BB_lower(20, 2.0)  — price outside lower Bollinger Band (confirms displacement)
4. volume > 1.2 * volume.rolling(20).mean()  — volume spike confirms selling pressure, not illiquidity
5. abs(close.pct_change(20)) < 0.015  — 20-bar drift is flat (exclude persistent downtrends)

Condition (3) is a BB confirmation gate that adds selectivity without being the primary signal driver — RSI + ATR regime is the core.

## Signals Needed
- `df['rsi14']  = 100 - 100/(1 + df['close'].diff().clip(lower=0).rolling(14).mean() / (-df['close'].diff().clip(upper=0)).rolling(14).mean())`
- `df['atr14']  = df[['high','low','close']].apply(lambda x: max(x['high']-x['low'], abs(x['high']-x['close'].shift()), abs(x['low']-x['close'].shift())), axis=1).rolling(14).mean()`  (via pd.concat true_range approach)
- `df['atr_pct'] = df['atr14'] / df['close']`
- `df['atr_median48'] = df['atr_pct'].rolling(48).median()`
- `df['bb_mid'] = df['close'].rolling(20).mean()`
- `df['bb_std'] = df['close'].rolling(20).std()`
- `df['bb_lower'] = df['bb_mid'] - 2.0 * df['bb_std']`
- `df['vol_ma20'] = df['volume'].rolling(20).mean()`
- `df['drift20'] = df['close'].pct_change(20).abs()`

## Universe Rationale
BTCUSDT 1h: highest Binance liquidity, 10 bps fee is modest for 1h returns, mean reversion edge documented in compressed-ATR regimes; prior BTC strategies used BB (bar_s2, bar_s12) but NOT RSI+ATR-regime gating.

## Knowledge References
- Iteration context: KRX strategies with direction-agnostic entries in downtrend = 0% WR. Lesson: must gate on drift/trend magnitude.
- bar_s7_eth_bb_reversion: pure BB entry without regime filter — drift condition (abs drift < 1.5%) is the structural improvement.
- KRX lesson 005: mean reversion entry fires after reversal exhausted — RSI(14)<35 + volume spike combination fires at peak selling pressure, before the rebound, not after.

## Constraints Passed To Execution-Designer
- Entry is valid only on bar close; do not chase intra-bar.
- Signal is valid for the NEXT bar's open (1-bar lookahead forbidden — enter at open of bar t+1).
- Target exposure: 15–35% of capital. Avoid sizing above 35% — this signal fires ~3–8% of bars (selective).
- Paradigm is mean_reversion: profit target should be within 0.5–1.5x ATR, not a trailing stop optimized for trend continuation.

```json
{
  "name": "btc_rsi_atr_reversion",
  "target_symbol": "BTCUSDT",
  "target_horizon": "1h",
  "paradigm": "mean_reversion",
  "signals_needed": [
    "rsi14 = RSI(close, 14) via EWM gain/loss",
    "atr14 = ATR(14) via true_range.rolling(14).mean()",
    "atr_pct = atr14 / close",
    "atr_median48 = atr_pct.rolling(48).median()",
    "bb_lower = close.rolling(20).mean() - 2.0 * close.rolling(20).std()",
    "vol_ma20 = volume.rolling(20).mean()",
    "drift20 = abs(close.pct_change(20))"
  ],
  "params": {
    "rsi_threshold": 35,
    "bb_bands": 2.0,
    "bb_window": 20,
    "atr_window": 14,
    "atr_median_window": 48,
    "vol_spike_mult": 1.2,
    "vol_window": 20,
    "drift_window": 20,
    "max_drift_pct": 0.015
  },
  "entry_condition": "RSI(14) < 35 AND atr_pct < atr_median(48) AND close < BB_lower(20,2) AND volume > 1.2*vol_ma(20) AND abs(drift_20bar) < 1.5%",
  "missing_primitive": null,
  "needs_python": true,
  "multi_date": true,
  "parent_lesson": "bar_s2_btc_bb_reversion — added ATR regime filter and RSI gate to fix directionless BB entry",
  "universe_rationale": "BTCUSDT 1h: highest Binance liquidity, structurally distinct from existing bar_s2/bar_s12 BB-only BTC strategies",
  "signal_brief_rank": null,
  "deviation_from_brief": null,
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/btc_rsi_atr_reversion_alpha.md"
}
```
