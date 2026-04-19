---
stage: execution_critique
strategy_id: crypto_1h_btc_mean_rev_168h_iter1
generated: 2026-04-17
---

# Execution Critique: crypto_1h_btc_mean_rev_168h_iter1

## Invariant Violations

None. `invariant_violations = []`, `invariant_violation_count = 0`. No execution bugs at the invariant level.

## Exit Distribution

All 12 IS roundtrips carry `exit_tag: "exit_signal"`. Zero exits are tagged `tp`, `sl`, `trailing_stop`, or `time_stop`. This is the primary execution finding: **the entire designed exit structure (PT 1312 bps, SL 450.79 bps, trailing activation 600 bps) never fired during the backtest period.**

| Exit Type | Count | Pct | Avg bps |
|---|---|---|---|
| PT (profit_target) | 0 | 0% | — |
| SL (stop_loss) | 0 | 0% | — |
| Trailing stop | 0 | 0% | — |
| Time stop (168-bar) | 0 | 0% | — |
| exit_signal (re-entry signal gate) | 12 | 100% | -46.08 |

The strategy is exiting entirely on a secondary condition (some form of exit signal), not on the designed PT/SL/trailing mechanics. The hold duration evidence partially corroborates this: 9 of 12 trades held exactly 7 days (604800 seconds = 168 bars), which matches the time stop horizon. However, the exit_tag is labeled `exit_signal` rather than `time_stop`, suggesting the engine's exit tag reporting is misclassifying time-horizon exits — or a parallel exit_signal condition is consistently firing before (or simultaneously with) the designed exits.

**SL breach audit**: 5 of 7 losing trades closed with losses exceeding the designed SL threshold of 450.79 bps:
- RT4: -510.12 bps (SL overshoot: +59 bps)
- RT6: -535.94 bps (SL overshoot: +85 bps)
- RT8: -528.98 bps (SL overshoot: +78 bps)
- RT9: -489.32 bps (SL overshoot: +38 bps)
- RT10: -551.99 bps (SL overshoot: +101 bps)

These are functional SL overshoots (bar-close mark price exceeded SL before the next-bar exit was submitted), but they are **not recorded as SL exits**. The engine did not recognize or fire the SL on these trades.

**PT phantom audit**: The two largest wins are +1007.92 bps (RT3) and +1095.43 bps (RT11). Both are below the PT of 1312 bps, meaning PT was never reached. Wins were captured at the 168-bar horizon, not at the designed profit target. PT is effectively phantom.

## Fee Burden

| Metric | Value |
|---|---|
| total_fees | 1,207.32 USD |
| gross_pnl | -5,542.45 USD |
| fee_pct | 21.8% of |gross_pnl| |
| fee_per_roundtrip | 100.61 USD |
| avg gross per roundtrip | -461.87 USD |

Fee burden is **not the primary problem** here. At 4 bps round-trip and BTC prices of ~$90k-115k, per-trade fees are ~100 USD, which is modest relative to the scale of wins and losses (ranging from -5,829 to +10,969 USD). The fee_pct of 21.8% is elevated because gross_pnl is itself negative, not because fees are disproportionate. In a profitable scenario, fee drag would be well under 10%. Fees are a second-order concern.

## PT/SL Calibration

**PT 1312 bps — Phantom.** The designed profit target was never hit across 12 trades. The two largest winners peaked at +1007 and +1095 bps at the 168-bar exit, suggesting the market did not sustain mean-reversion momentum to the full +13.12% recovery threshold during the IS window. The PT is set above the reachable range for most mean-reversion recoveries in this regime. Either the PT should be reduced to ~800-1000 bps (below observed peaks), or the signal needs a higher-momentum entry condition.

**SL 450.79 bps — Not firing (functional bug), effective level confirmed by data.** The calibration itself is supported by the data: the 5 stopping losses range from -489 to -552 bps, clustering near the 450 bps design level. The issue is not miscalibration — it is that the SL is not being executed. If it were firing correctly, it would have cut losses on 5 trades at approximately -450 bps instead of letting them run to -490-552 bps, saving roughly 200-300 bps of aggregate loss.

**Trailing stop — Never activated.** Activation requires 600 bps of unrealized profit. With the best win at +1095 bps (net), the activation threshold could theoretically have been reached on RT3 and RT11 intra-bar, but no trailing exit was recorded. Either the activation was never breached intra-bar (only bar-close mark is monitored), or the trailing logic has a similar non-execution bug as the SL.

## Adverse Selection

Market order entry (MARKET BUY at bar close, `ask` mode). No passive fill mechanics, no TTL, no bid-drop. Adverse selection measurement is not applicable for market taker entries. The 4 bps round-trip cost is already captured in fee_per_roundtrip. No further adverse selection data is needed.

## Execution Assessment

**Poor.** The exit structure is entirely non-functional: PT never fires (phantom), SL never fires despite 5 trades exceeding its threshold, trailing stop never activates. All exits are tagged `exit_signal`, suggesting either a parallel exit condition is overriding the designed mechanics, or the engine's strategy.py implementation does not correctly wire the PT/SL/trailing monitoring to the exit logic. The strategy is running as a pure 168-bar time-exit strategy with no downside protection and no upside capture beyond the horizon.

## Execution Improvement Direction

Fix the strategy.py implementation to correctly monitor bar.close against the SL threshold and PT resting limit each bar, ensuring SL fires before the next signal gate and PT fires when the LIMIT SELL is crossed — the designed exit mechanics must override the `exit_signal` condition.

---

## JSON Summary

```json
{
  "strategy_id": "crypto_1h_btc_mean_rev_168h_iter1",
  "execution_assessment": "poor",
  "exit_breakdown": {
    "n_tp": 0,
    "n_sl": 0,
    "n_eod": 0,
    "n_trailing": 0,
    "n_other": 12,
    "sl_tp_ratio": null,
    "avg_tp_bps": null,
    "avg_sl_bps": -426.62,
    "avg_eod_bps": null,
    "note": "all 12 exits tagged exit_signal; PT/SL/trailing/time_stop mechanics produced zero tagged exits"
  },
  "fee_analysis": {
    "total_fees": 1207.32,
    "gross_pnl": -5542.45,
    "fee_pct": 21.8,
    "fee_per_roundtrip": 100.61,
    "assessment": "fees are not dominant; 4 bps round-trip is appropriate for BTC bar-level strategy; primary leak is non-functional exit mechanics, not fees"
  },
  "stop_target_calibration": "PT 1312 bps is phantom — never reached in 12 trades; best wins were +1007 and +1095 bps at 168-bar horizon. SL 450.79 bps is well-calibrated in magnitude (5 losses cluster at -489 to -552 bps) but never executed — the SL is not firing despite being breached.",
  "adverse_selection": "Market taker entry (MARKET BUY at ask); no adverse selection applicable.",
  "critique": "The entire designed exit structure is non-functional: zero trades exited via PT, SL, or trailing stop across 12 roundtrips, despite 5 losses exceeding the SL threshold by 38-101 bps. All exits are classified as exit_signal, indicating the strategy.py implementation either lacks working PT/SL monitoring logic or an exit_signal condition overrides it unconditionally. As a result, the strategy ran as a pure 168-bar time-exit with no downside protection, amplifying losses on 5 trades that should have been cut at -450 bps. PT is additionally phantom — BTC mean-reversion during IS never reached the +1312 bps target, meaning the payoff structure is asymmetrically broken: losers run to -535 bps, winners cap at +1095 bps at the time horizon.",
  "execution_improvement": "Audit and rewrite the strategy.py exit loop to correctly check bar.close against entry_price * (1 - sl_bps/10000) each bar and submit a MARKET SELL immediately when breached, before any exit_signal condition is evaluated.",
  "data_requests": [
    "intra-bar OHLC data for each roundtrip to determine whether PT/SL thresholds were breached intra-bar but not at bar close (bar.close-only monitoring may miss intra-bar violations)",
    "strategy.py exit logic code path to confirm whether SL/PT checks are wired in the on_bar handler",
    "exit_signal condition definition — what triggers exit_signal tag and whether it fires before SL/PT evaluation"
  ],
  "pt_phantom": true,
  "sl_calibrated": true,
  "sl_firing": false,
  "fee_burden_pct": 21.8
}
```
