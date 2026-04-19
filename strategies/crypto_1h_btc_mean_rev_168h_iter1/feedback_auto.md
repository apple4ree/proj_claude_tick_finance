# Feedback — crypto_1h_btc_mean_rev_168h_iter1

        *Generated: 2026-04-19T04:12:16.792756Z* (programmatic)

        ## Spec
        - paradigm: `None`
        - symbol: `BTCUSDT`, horizon: `1h`
        - params: `{"roc_168h_threshold": -0.056226, "entry_side": "low", "entry_price_mode": "ask", "entry_ttl_ticks": 0, "cancel_on_bid_drop_ticks": 0, "profit_target_bps": 1312.07, "stop_loss_bps": 450.79, "trailing_stop": true, "trailing_activation_bps": 600.0, "trailing_distance_bps": 300.0, "lot_size": 1, "max_entries_per_session": 1}`

        ## Backtest (full period)
        - return: **-7.07%**,  Sharpe: **-0.42**,  MDD: **-22.70%**
        - IC (Pearson): +0.0012  |  ICIR: +2.397  |  IR vs BH: **+0.709**
        - roundtrips: 12,  win rate: 41.7%,  exposure: 0.344

        ## 4-Gate Validation
        | gate | pass | detail |
        |---|---|---|
        | 1_invariants | ✓ | violations=0 (allow=0) |
| 2_oos_sharpe | ✓ | OOS roundtrips=14 (min=1), Sharpe=-1.31, ret=-8.41% |
| 3_ir_vs_bh | ✓ | OOS IR=+2.35 (min=+0.00), BH=-19.620844206156203 |
| 4_cross_symbol | ✓ | standalone (no siblings), soft-pass |

        ## OOS
        - window: ['2025-11-01', '2025-12-31']
        - return: -8.41489300247893  |  Sharpe: -1.307749292213218  |  IR: 2.3538765705694984  |  RT: 14

        ## Notes
        - strong positive IR vs buy-and-hold
