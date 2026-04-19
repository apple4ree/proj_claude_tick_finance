---
id: lesson_20260414_003_tax_heavy_korean_market_tight_spread_entry_filter_increases_turnover_fees_dominate_pnl
created: 2026-04-14T02:41:49
tags: [lesson, fees, tax, turnover, korea, tight-spread, obi, edge, failure]
source: strat_20260414_0003_tight_spread_ofi_momentum
links:
  - "[[lesson_20260414_001_absolute_spread_filter_breaks_cross_symbol]]"
  - "[[pattern_krx_fee_hurdle_dominates_tick_edge]]"
metric: "return_pct=-0.9504 trades=372 fees=71744"
---

# Tax-heavy Korean market: OBI momentum has no edge over spread cost, tight-spread filter worsens fee burn

## Core finding (strat_0002 + strat_0003)

OBI momentum at tick horizon has no edge over the KRX fee hurdle. strat_0002 applied the bps spread fix from lesson_001 and 000660 traded (7 losers vs 0 trades before), but net return was still -0.86% -- realized PnL of -20,200 KRW dwarfed by 65,405 KRW in fees across 292 trades. obi>0.5 + short positive mid return is a mean-reverting crossing signal at tick scale; the expected move is a few bps but each round-trip pays ~21 bps (2 bps commission + 18 bps sell tax). Unless entry captures >20 bps with hit-rate > 60%, net edge is negative by construction.

## Tight-spread filter amplifies the problem (strat_0003)

372 trades generated 71,744 KRW in fees vs only -23,300 KRW realized PnL -- fees are 3.08x the realized loss and 75.5% of total loss. Tightening the spread filter (spd_bps < 6) and adding a stricter OBI threshold (obi3 > 0.4) counterintuitively raised trade count to 372 from 334, inflating fee burn further. Tight-spread regimes are frequent for 005930 (liquid mega-cap), so the entry fires often without capturing enough edge to clear the 21 bps hurdle.

## Duration extension test (strat_0005)

Extending hold to 200 ticks and reducing turnover cut the loss 5x (-0.17% vs -0.95%), confirming the fee-burn diagnosis. But win_rate remains 0% and avg pre-fee PnL per roundtrip is -320 KRW -- the signal direction is wrong, not just the sizing. Entry condition "ret200 > 15 bps + obi5 > 0.15" reliably fires at the tail end of a completed move, capturing reversal rather than continuation. This is a structural anti-edge.

How to apply next: Either (a) target much longer holds (500+ ticks) with a volatility or trend filter, (b) switch to maker-side orders (resting limit), (c) enlarge lot size to amortize fixed-cost fee component, or (d) restrict to lower-tax instruments (ETFs have 0 tax). Do not tighten spread filters further without reducing trade frequency.
