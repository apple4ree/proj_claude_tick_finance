# Bar Trace Analysis: crypto_1h_btc_mean_rev_168h_iter1

Generated: 2026-04-19 06:28 | total_roundtrips: 12

## Summary

| Metric | Value |
|---|---|
| Total roundtrips | 12 |
| WIN / LOSS | 5 / 7 (41.7%) |
| Avg net bps | -45.95 |
| Avg net bps (WIN) | +486.99 |
| Avg net bps (LOSS) | -426.62 |
| Avg hold WIN | 7d 0h |
| Avg hold LOSS | 3d 23h |

## Exit Tag Breakdown

| tag | total | WIN | LOSS | avg_net_bps |
|---|---|---|---|---|
| sl_hit | 5 | 0 | 5 | -523.27 |
| time_stop | 7 | 5 | 2 | +294.99 |
## Give-Back Summary (MFE / MAE)

| Metric | Value | 해석 |
|---|---|---|
| Avg MFE (peak profit during hold) | +379.40 bps | — |
| Avg MAE (worst drawdown during hold) | -347.89 bps | — |
| Avg capture_pct | -523.2% | 100% = 피크 완전 캡처; < 50% = give-back 패턴 |
| Sum of missed profit | +4556.88 bps | MFE − realized 합계. 크면 exit 재설계 신호. |
| n_give_back_trades | 8 / 12 | MFE > 100 bps 였으나 LOSS or capture < 50% |

## Roundtrips

| # | sym | buy_time | sell_time | hold | tag | net_bps | mfe_bps | mae_bps | capture% | result |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BTCUSDT | 2025-08-18 16:00:00 | 2025-08-25 16:00:00 | 7d 0h | time_stop | -297.56 | +156.8 | -324.0 | -190% | LOSS |
| 2 | BTCUSDT | 2025-08-26 06:00:00 | 2025-09-02 06:00:00 | 7d 0h | time_stop | -72.45 | +335.6 | -196.5 | -22% | LOSS |
| 3 | BTCUSDT | 2025-09-26 03:00:00 | 2025-10-03 03:00:00 | 7d 0h | time_stop | +1007.92 | +1072.5 | +0.2 | +94% | WIN |
| 4 | BTCUSDT | 2025-10-11 06:00:00 | 2025-10-17 01:00:00 | 5d 19h | sl_hit | -510.12 | +133.6 | -500.4 | -382% | LOSS |
| 5 | BTCUSDT | 2025-10-17 02:00:00 | 2025-10-24 02:00:00 | 7d 0h | time_stop | +84.37 | +383.6 | -430.4 | +22% | WIN |
| 6 | BTCUSDT | 2025-11-03 13:00:00 | 2025-11-05 02:00:00 | 1d 13h | sl_hit | -535.94 | +11.3 | -632.1 | -4721% | LOSS |
| 7 | BTCUSDT | 2025-11-05 03:00:00 | 2025-11-12 03:00:00 | 7d 0h | time_stop | +209.85 | +547.9 | -146.0 | +38% | WIN |
| 8 | BTCUSDT | 2025-11-15 03:00:00 | 2025-11-18 12:00:00 | 3d 9h | sl_hit | -528.98 | +82.1 | -521.7 | -644% | LOSS |
| 9 | BTCUSDT | 2025-11-18 13:00:00 | 2025-11-21 04:00:00 | 2d 15h | sl_hit | -489.32 | +292.4 | -479.6 | -167% | LOSS |
| 10 | BTCUSDT | 2025-11-21 05:00:00 | 2025-11-21 19:00:00 | 14h | sl_hit | -551.99 | +131.7 | -542.3 | -419% | LOSS |
| 11 | BTCUSDT | 2025-11-21 20:00:00 | 2025-11-28 20:00:00 | 7d 0h | time_stop | +1095.43 | +1106.0 | -47.6 | +99% | WIN |
| 12 | BTCUSDT | 2025-12-17 02:00:00 | 2025-12-24 02:00:00 | 7d 0h | time_stop | +37.40 | +299.1 | -354.4 | +12% | WIN |
