# Feedback — lob_run20260420_iter1_obi1_maker

        *Generated: 2026-04-20T13:04:00.652450Z* (programmatic)

        ## Spec
        - paradigm: `—`
        - symbol: `BTCUSDT,ETHUSDT,SOLUSDT`, horizon: `crypto_lob`
        - params: `{"obi_thresholds": {"BTCUSDT": 0.918997, "ETHUSDT": 0.942049, "SOLUSDT": 0.749589}, "spread_gate": true, "entry_price_mode": "bid", "entry_ttl_ticks": 10, "cancel_on_bid_drop_ticks": 1, "profit_target_bps": 1.21, "stop_loss_bps": 1.64, "trailing_stop": false, "trailing_activation_bps": 0.0, "trailing_distance_bps": 0.0, "lot_size": 1, "max_entries_per_session": 5, "max_position_per_symbol": 1}`

        ## Backtest (full period)
        - return: **-0.01%**,  Sharpe: **-0.36**,  MDD: **-0.01%**
        - IC (Pearson): +0.0000  |  ICIR: +0.000  |  IR vs BH: **+0.000**
        - roundtrips: 11,  win rate: 0.0%,  exposure: 0.000

        ## 4-Gate Validation
        | gate | pass | detail |
        |---|---|---|
        | 1_invariants | ✗ | violations=4 (allow=0) |
| 2_oos_sharpe | ✓ | OOS roundtrips=27 (min=1), Sharpe=-0.64, ret=-0.01% |
| 3_ir_vs_bh | ✓ | OOS IR=+0.98 (min=+0.00), BH=-0.485801209694004 |
| 4_cross_symbol | ✓ | standalone (no siblings), soft-pass |

        ## OOS
        - window: ['2026-04-19T22:00:00', '2026-04-20T06:00:00']
        - return: -0.0114  |  Sharpe: -0.6425  |  IR: 0.9765336113362487  |  RT: 27

        ## Notes
        - invariant violations: 4 (['max_position_exceeded'])
