# Tried failure modes — what NOT to do (auto-generated from v3-v6 archive)

*This sheet is auto-generated from cumulative experiment archives. Updated each run.*

Quick rule: when designing a new spec, **scan this list first**. If your hypothesis 
matches a known failure mode, it will likely produce the same outcome.

Total specs analyzed: 161 failures across 262 measured specs (out of 335 total).

## **No backtest result** — code generation or fidelity check failed.

Count: 73

Concrete examples (top 5):
- `zscore(obi_1 + obi_ex_bbo, 300)` (n=0, mid=0.00, dur=0, duty=0.00)
- `(obi_1 > 0.5) AND (obi_ex_bbo > 0.2) AND (bid_depth_concentration > 0.` (n=0, mid=0.00, dur=0, duty=0.00)
- `zscore(ask_depth_concentration, 300) * (rolling_realized_vol(mid_px, 1` (n=0, mid=0.00, dur=0, duty=0.00)
- `(obi_1 - obi_ex_bbo > 1.5) AND (rolling_realized_vol(mid_px, 100) > 40` (n=0, mid=0.00, dur=0, duty=0.00)
- `zscore(ask_depth_concentration, 300)` (n=0, mid=0.00, dur=0, duty=0.00)

## **Flickering** — mean_duration < 5 ticks with n > 100 regimes. Signal toggles every 1-2 ticks. fee accumulation prohibitive.

Count: 29

Concrete examples (top 5):
- `zscore(trade_imbalance_signed, 300)` (n=2738, mid=-0.07, dur=1, duty=0.02)
- `(ofi_proxy > 0.3) AND (obi_ex_bbo > 0.1) AND (rolling_mean(trade_imbal` (n=17655, mid=0.01, dur=2, duty=0.20)
- `zscore(trade_imbalance_signed, 300) > 2.0 AND obi_ex_bbo > 0.1` (n=16151, mid=0.46, dur=2, duty=0.01)
- `zscore(trade_imbalance_signed, 300) > 1.5 AND zscore(ask_depth_concent` (n=5136, mid=0.45, dur=2, duty=0.00)
- `microprice_velocity > 1.5 AND spread_change_bps < 0.5` (n=24590, mid=0.23, dur=1, duty=0.01)

## **Trigger fragility** — n < 50 trades total. Statistical noise dominates.

Count: 27

Concrete examples (top 5):
- `(zscore(trade_imbalance_signed, 300) > 2.0) AND (ask_depth_concentrati` (n=1, mid=5.13, dur=0, duty=0.00)
- `ask_depth_concentration > 0.35 AND obi_ex_bbo < -0.2` (n=44, mid=5.24, dur=0, duty=0.00)
- `(zscore(ask_depth_concentration, 300) > 2.5) AND (rolling_realized_vol` (n=6, mid=11.39, dur=0, duty=0.00)
- `zscore(ask_depth_concentration, 300) > 2.0 AND (obi_1 - obi_ex_bbo) > ` (n=0, mid=0.00, dur=0, duty=0.00)
- `(obi_1 > 0.5) AND (minute_of_session > 350)` (n=0, mid=0.00, dur=0, duty=0.00)

## **Negative alpha** — mid_gross < -1 bps. Direction wrong, or signal captures mean-reversion at wrong sign.

Count: 23

Concrete examples (top 5):
- `obi_1 - obi_ex_bbo` (n=4272, mid=-5.79, dur=0, duty=0.00)
- `obi_1 - obi_ex_bbo` (n=4272, mid=-5.79, dur=0, duty=0.00)
- `zscore(trade_imbalance_signed, 300) > 1.5 AND obi_ex_bbo > 0.1` (n=926, mid=-2.40, dur=0, duty=0.00)
- `zscore(trade_imbalance_signed, 100) > 2.0 AND rolling_momentum(mid_px,` (n=457, mid=-2.88, dur=0, duty=0.00)
- `(obi_1 > 0.6) AND (obi_ex_bbo < -0.2) AND (rolling_mean(trade_imbalanc` (n=1934, mid=-5.95, dur=0, duty=0.00)

## **Spread arbitrage (suspicious)** — mid_gross ≈ 0 but maker_gross > 8 bps. Signal triggers only when spread is unusually wide. Likely not real alpha — would not survive maker_realistic queue + adverse selection.

Count: 7

Concrete examples (top 5):
- `obi_1 * (1.1 - bid_depth_concentration)` (n=32054, mid=-0.27, dur=52, duty=0.44)
- `where(rolling_realized_vol(mid_px, 100) > 50, rolling_mean(ofi_proxy, ` (n=6850, mid=0.11, dur=87, duty=0.16)
- `rolling_mean(microprice_dev_bps, 500)` (n=3286, mid=-0.23, dur=633, duty=0.56)
- `rolling_mean(ofi_proxy, 500)` (n=13465, mid=-0.09, dur=176, duty=0.64)
- `rolling_mean(obi_1, 500) + rolling_mean(obi_ex_bbo, 500)` (n=1736, mid=0.17, dur=1335, duty=0.63)

## **Buy-and-hold artifact** — signal is True ≥ 95% of session. Effectively a buy-and-hold, not a signal. duty_cycle > 0.95.

Count: 2

Concrete examples (top 5):
- `rolling_mean(obi_ex_bbo, 2000)` (n=320, mid=-4.09, dur=9880, duty=0.97)
- `where(rolling_realized_vol(mid_px, 200) > 60, rolling_mean(microprice_` (n=3071, mid=-0.68, dur=1173, duty=0.97)

## Anti-pattern checklist (review before submitting any spec)

- [ ] If `formula` evaluates True > 95% of session → buy-and-hold artifact
- [ ] If your `threshold` makes the signal trigger only at `> 0.99` extremes → trigger fragility (n < 50)
- [ ] If your spec uses zscore < 2.0 — that's not really 'tail', try ≥ 2.5
- [ ] If your spec triggers only when spread > 15 bps → likely spread-arbitrage, not real alpha
- [ ] If `mean_duration_ticks` will be < 5 → flickering, fee will eat alpha
- [ ] Category B3 (deep book extreme contra direction) has 67% accuracy — cite-but-fail risk