# Feedback — lob_iter2_obi1_spread_gate

        *Generated: 2026-04-20T05:47:07.363276Z* (programmatic)

        ## Spec
        - paradigm: `—`
        - symbol: `BTCUSDT,ETHUSDT,SOLUSDT`, horizon: `crypto_lob`
        - params: `{"obi_thresholds": {"BTCUSDT": 0.91469, "ETHUSDT": 0.942049, "SOLUSDT": 0.749589}, "spread_gate": true, "entry_price_mode": "ask", "entry_ttl_ticks": 0, "cancel_on_bid_drop_ticks": 0, "profit_target_bps": 1.09, "stop_loss_bps": 1.78, "trailing_stop": false, "trailing_activation_bps": 0.0, "trailing_distance_bps": 0.0, "time_stop_ticks": 10, "lot_size": 1, "max_entries_per_session": 500, "max_position_per_symbol": 1}`

        ## Backtest (full period)
        - return: **+0.10%**,  Sharpe: **+2.11**,  MDD: **-0.00%**
        - IC (Pearson): +0.0000  |  ICIR: +0.000  |  IR vs BH: **+0.000**
        - roundtrips: 1000,  win rate: 37.5%,  exposure: 0.000

        ## 4-Gate Validation
        | gate | pass | detail |
        |---|---|---|
        | 1_invariants | ✓ | violations=0 (allow=0) |
| 2_oos_sharpe | ✓ | OOS roundtrips=1000 (min=5), Sharpe=+1.95, ret=+0.07% |
| 3_ir_vs_bh | ✓ | OOS IR=+1.07 (min=+0.00), BH=-0.9570531689632331 |
| 4_cross_symbol | ✓ | standalone (no siblings), soft-pass |

        ## OOS
        - window: ['2026-04-19T22:00:00', '2026-04-20T00:00:00']
        - return: 0.0664  |  Sharpe: 1.9523  |  IR: 1.0693796354824576  |  RT: 1000

        ## Notes
        - (none)
