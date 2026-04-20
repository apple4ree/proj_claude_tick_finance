---
date: 2026-04-18
strategies_scope: 44 strategies (20 tick KRX + 15 bar daily + 9 crypto horizon)
signal_brief_rank: n/a (retrospective)
tags: [alpha-critic, portfolio-audit, buy-hold-benchmark, fee-saturation, horizon-threshold]
severity: high
---

# Retrospective: Every "winning" strategy has negative IR vs buy-and-hold

## Observation

Audited 44 generated strategies. Category-level summary:

| Category | n | pos/n | median return | best |
|---|---|---|---|---|
| Tick KRX (21 bps RT) | 20 | 2/20 | −0.051% | +0.008% |
| Bar daily (BTC/ETH/SOL, 3y) | 15 | 12/15 | +23.2% | +107.4% |
| Crypto intraday (1h/15m/5m, 6mo) | 9 | 2/9 | −36.5% | +5.59% |

Filtering to `Sharpe > 0.5 AND ret > 10%` yields 8 "viable" strategies — all bar-daily BTC/ETH/SOL.

## Critical finding — IR invalidates the win claim

Every viable strategy's **`information_ratio` (vs buy-hold) is negative**:

| Strategy | Return | Ann | IR vs B&H | Buy-hold ann |
|---|---|---|---|---|
| bar_s9_btc_vol_breakout | +62.8% / 3y | ~17.6%/y | **−1.10** | BTC +74.0%/y |
| bar_s8_sol_vol_mom_loose | +107.4% / 3y | ~27.5%/y | **−1.12** | SOL +131.8%/y |
| bar_s7_eth_bb_reversion | +37.6% / 3y | ~11.2%/y | — | ETH +35.2%/y |
| crypto_1h_eth_rsi_atr | +5.59% / 6mo | ~11.5%/y | **−0.69** | ETH (period) ≫ strategy |

In every case the "winning" strategy just took **smaller long exposure** during a massive 2023-2025 crypto bull run. Lower MDD is not alpha — it is reduced participation. Buy-and-hold dominates every rule-based variant on IR.

## Lessons

### L1 — Tick KRX (21 bps/RT) is structurally dead for edge discovery
n=20 tick strategies, median −0.05%, max +0.008%. The fee floor consumes any signal we can design at this horizon. No parametric sweep rescues this.

### L2 — Fee-saturation horizon threshold lies between 1h and 15m (crypto, 10 bps/RT)
- 1h: 2/3 positive, median_RT=4
- 15m: 0/3 positive, median_RT=248
- 5m: 0/3 positive, median_RT=845

Frequency is not a dial — it's a cliff. Any strategy that trades >100 RT/period in our corpus is a loser (median −53% return across n=6).

### L3 — Positive absolute return ≠ positive alpha
The bar-daily winners reported up to +107% over 3 years. Every single one **underperformed buy-hold**. Without an IR filter, "winning" is a market-beta illusion.

### L4 — Paradigm × symbol concentration in bar winners
Viable bar-daily strategies (Sharpe > 0.5):
- `trend_follow` on SOL — 4 variants (all exposure to SOL uptrend)
- `mean_reversion` on BTC — 2 variants
- `mean_reversion` on ETH — 1 variant
- `breakout` on BTC — 1 variant

All "trend_follow on SOL" wins are essentially a diluted long-SOL position. The apparent paradigm diversity collapses under IR.

### L5 — Low turnover is necessary but not sufficient
Sharpe>0 subset: 12 strategies with RT≤20 (median +5.12% return). High-turnover set: 6 strategies with RT>100 (all negative). Low turnover survives fees — but doesn't deliver alpha vs B&H.

## Official benchmark (period-matched)

Added `bar_baseline_bh_{btc,eth,sol}` — constant-1 signal, single-entry, zero exits.
For every comparable strategy (24/44; tick KRX excluded for lack of BH baseline), computed buy-and-hold return over the strategy's exact date range.

- **Beat BH on absolute return: 2/24** — both in a 6-month bear period (BH was negative), beaten by sitting in cash
- **Positive IR vs BH: 2/24** (same two)
- **In any up-period: 0/24 beat BH** — zero strategies produced alpha in a rising market

Worst-case underperformance: `bar_s4_sol_vol_compress` lost BH by **−1164.65 percentage points** (return +27% vs SOL BH +1147%).

Artifacts: `docs/bh_benchmark.json`, `docs/bh_benchmark.csv`, `docs/figures/bh_benchmark.png`.

## Practical-return verdict

**With the current corpus, practical return is not achievable.** The only profitable bucket (bar-daily) doesn't beat the underlying; the two profitable horizons (crypto 1h) traded too few times (n=4–10) for statistical confidence and still lose to B&H.

What the data suggests is required to flip the picture:
1. **Market-neutral construction** — long-short or relative-value pair trades. Current corpus is 100% directional.
2. **Regime detection** — use the strategy only when it has edge (e.g., sideways/bear phase), B&H otherwise.
3. **Move outside 1h–1d crypto / tick KRX** — possibly daily pairs, funding-rate arbitrage, or cross-exchange spreads where B&H isn't the comparable.
4. **Stop generating variants of current paradigms** — parameter sweeps on trend_follow/mean_reversion/breakout cannot produce positive IR in an up-only tape.

## Seeds for next iteration

- Spawn market-neutral alpha-designer (long best × short worst sector or pair-trade BTC/ETH).
- Add IR-vs-B&H filter to `optuna_sweep.py` objective — Sharpe alone selects closet-long variants.
- For paper: this retrospective IS a finding. "Directional LLM strategies cannot produce alpha in a persistent uptrend" is publishable when paired with the IR data above.
