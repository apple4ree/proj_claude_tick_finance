---
id: lesson_20260414_024_tighter_obi_4x_return_gain_000660_payoff_magnitude_dwarfs_006800_revealing_lot_scale_asymmetry
created: 2026-04-14T12:40:31
tags: [lesson, 000660, 006800, lot-size, position-sizing, obi-threshold, universe-concentration, payoff-asymmetry, resting-limit, krx]
source: strat_20260414_0026_krx_resting_limit_2sym_obi35
metric: "return_pct=0.0262 trades=15 win_rate_pct=46.67 n_symbols=2"
---

# tighter OBI 4x return gain: 000660 payoff magnitude dwarfs 006800 revealing lot-scale asymmetry

Observation: Tightening OBI 0.30→0.35 and concentrating on 2 symbols halved roundtrips (30→15) but quadrupled avg_return_pct (+0.0069%→+0.0262%). 000660 best-trade=12,999 KRW vs 006800 best-trade=893 KRW — a 14× payoff magnitude gap. 000660's 7 trades at 42.86% WR produced 0.048% return; 006800's 8 trades at 50% WR produced only 0.0044% return.
Why: The two symbols are not equivalent even after universe filtering. 000660 (SK Hynix) has sufficient intraday tick-range to generate large absolute moves; 006800 (Mirae Asset) is a lower-priced, lower-volatility security where even a 150 bps profit target fills at a small KRW amount. Equal lot_size=1 massively under-allocates to the higher-EV symbol. Additionally, OBI tightening improves entry conviction: fewer but larger winners emerge when only the strongest imbalance signals fire.
How to apply next: Scale lot_size proportionally to expected per-trade KRW magnitude — test lot_size=2 or 3 on 000660 while keeping 006800 at lot_size=1. Alternatively, drop 006800 entirely and concentrate all capital on 000660 with OBI 0.32–0.33 to recover some trade frequency without reverting to low-conviction entries.
