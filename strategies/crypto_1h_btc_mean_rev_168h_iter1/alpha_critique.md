# Alpha Critique: crypto_1h_btc_mean_rev_168h_iter1

Generated: 2026-04-17 | Critic: alpha-critic

---

## Observation

The roc_168h mean-reversion signal produced 12 IS entries with a 41.7% win rate and -7.07% total IS return, failing to realize the brief's projected +441 bps adjusted EV. The OOS result (-8.41%) nonetheless outperformed buy-and-hold (-19.62%) by +11.2 percentage points (IR +2.35), indicating the signal does carry some regime-conditioned edge — it loses less than passive holding during a declining market — but cannot produce absolute positive returns in the tested IS window.

---

## Signal Quality Analysis

### Invariant Check

No invariant violations (0 of 0). `clean_pct_of_total` is not applicable here (no bug PnL). All returns are attributed to signal edge (or lack thereof).

### WIN vs LOSS Entry Context Comparison

This is a 1h bar crypto strategy — roundtrip `buy_context` contains only `bar_close` (no OBI, spread_bps, or acml_vol from tick LOB). Separation is analyzed via absolute entry price level and temporal regime:

| Metric | WIN (n=5) | LOSS (n=7) | Delta |
|---|---|---|---|
| Avg entry price (USD) | 97,894.55 | 102,945.48 | -5,050.93 |
| Avg net_bps | +486.99 | -426.62 | +913.61 |
| Avg hold (hours) | 168.0 | 95.7 | +72.3 |

The price-level separation reveals a meaningful pattern: WIN entries occurred at lower absolute BTC price levels (avg $97.9k) vs LOSS entries ($102.9k). This is partially tautological — wins happened later in the IS window when BTC had already declined further — but it also implies the signal fires more reliably when the entry price itself is at a deeper discount relative to the 168h lookback.

The hold-time difference is structurally important: WIN trades all ran the full 168h time stop (7 days), while LOSS trades averaged only 95.7h — meaning losses were cut by stop-loss exits while wins required the full window. This is an execution-critic issue (SL at 450 bps cutting too early on volatile days), but it reveals that signal quality alone cannot be separated from the SL trigger — the BTC-specific weak raw mean_fwd warned of this.

### Selectivity

- Total IS events: 4,393 bars (184 days × ~24 bars/day)
- Actual entries fired: 12 roundtrips
- Entry rate: 0.27% of total events; 6.5% of trading days

The alpha design cited "~10% of bars fire the entry condition (n_entry=262)." In practice only 12 trades executed — because `max_entries_per_session=1` collapsed the 262 signal bars into 12 discrete trade days. The signal itself (262 fires / ~4,416 bars) fires at 5.9% rate, which is within the expected 10% range but significantly more selective at the trade level due to the session cap. **Assessment: selective** — the signal does not fire indiscriminately, but the session cap means most signal fires are wasted.

### Regime Dependency

Entries by month:
- August 2025: 2 entries (2 LOSS) — BTC ranging high ~109-115k
- September 2025: 1 entry (1 WIN) — BTC dip to 108k then rally to 119k
- October 2025: 2 entries (1 WIN, 1 LOSS) — BTC volatile 108-114k
- November 2025: 6 entries (3 WIN, 3 LOSS) — BTC declining from 107k to 82k
- December 2025: 1 entry (1 WIN) — BTC recovering ~87k

The critical regime dependency is the **November 2025 BTC drawdown**: 4 of the 7 losses (57%) occurred in November, concentrated in a persistent downtrend where BTC dropped from ~107k to ~82k. During this period, the signal fired 4 consecutive times (trades 6, 8, 9, 10) as each new 168h low triggered entry — only to see further decline. This is the core failure mode: roc_168h fires into ongoing trending moves, not just oversold mean-reversion setups. The eventual WIN (trade #11, Nov-21 20:00) came only after BTC bottomed near $82k.

**Assessment: strong regime dependency** — strategy performs when BTC is in a ranging/recovering regime (Aug-Oct, Dec entries) but suffers consecutive cascade losses during persistent weekly downtrends (Nov). 4 of 7 losses and 57% of total loss magnitude concentrated in one trending-down month.

---

## Hypothesis Validation

### Was the brief's +441 bps EV realized?

No. The brief projected +414 bps adjusted EV (after 30 bps haircut for BTC's weaker raw entry stats). Observed avg net_bps across all 12 IS trades was -45.95 bps. The brief's pooled EV of +445 bps reflected ETH (+613 bps) and SOL (+733 bps) heavily — the BTC-specific raw entry mean_fwd of -10 bps was the dominant factor, as warned in the alpha design. PT/SL filtering (intended to carve out the profitable 61.96% pooled win rate) achieved only 41.7% win rate on BTC alone.

### Was BTC's weak mean_fwd (-10 bps) the dominant factor?

Yes. The alpha design explicitly flagged "BTC-specific entry-stats show mean_fwd_bps = -10 at the raw unfiltered entry horizon, which is weaker than ETHUSDT (+613 bps) and SOLUSDT (+733 bps)." The realized WR of 41.7% (vs brief's projected 61.96% pooled) and negative total return confirm that BTC-specific mean reversion at the 168h horizon is structurally weaker — the pooled cross-symbol EV does not translate to BTC in isolation.

### Does IR +2.35 OOS validate the hypothesis?

Partially. The OOS window (Nov-Dec 2025) saw BTC decline -19.6% buy-and-hold while the strategy lost only -8.4% — a 11.2pp outperformance. This confirms the signal has genuine downside protection properties: by holding only when roc_168h is deeply oversold, the strategy avoids most of the trend exposure and exits when further decline continues (SL protection). However, this is not the mean-reversion alpha claimed in the hypothesis — it is closer to a momentum filter that reduces net long exposure during drawdowns. The OOS "pass" on IR vs BH is a soft validation that doesn't confirm positive absolute returns are achievable with this signal on BTC.

---

## Alpha Improvement Direction

Restrict BTC entries to periods where short-term momentum shows early reversal confirmation — e.g., add a secondary filter requiring roc_24h >= 0 (BTC up in the past 24 bars) before allowing entry on the roc_168h oversold signal, to avoid firing into still-falling momentum.

---

## JSON Summary

```json
{
  "signal_edge_assessment": "weak",
  "win_loss_separation_observed": true,
  "selectivity_assessment": "Signal fires at ~6% of bars (262 of ~4416 IS bars meet threshold), collapsed to 12 actual trades by max_entries_per_session=1 — selective at the trade level but wastes most signal fires; entry selectivity is adequate but not the limiting factor.",
  "regime_dependency_assessment": "Strong regime dependency: 4 of 7 losses (57%) clustered in November 2025 BTC persistent downtrend (107k to 82k), where the signal fired 4 consecutive times into a trending decline; strategy has edge only in ranging-to-recovering BTC regimes.",
  "hypothesis_supported": false,
  "critique": "The roc_168h mean-reversion signal has no reliable discriminative power on BTC in isolation — the alpha design acknowledged mean_fwd of -10 bps for BTC vs +613/+733 bps for ETH/SOL, and the realized 41.7% WR confirms BTC's 168h momentum reversal does not produce the pooled cross-symbol EV. The signal correctly avoids large portions of trend exposure (evidenced by IR +2.35 vs BH on OOS), but fires indiscriminately into both genuine mean-reversion setups and ongoing cascade drawdowns, as seen in the 4-consecutive-loss November cluster. WIN entries show lower avg entry price ($97.9k vs $102.9k for losses), suggesting the depth of the decline — not merely crossing the -5.6% threshold — is what matters.",
  "alpha_improvement": "Add a short-term reversal confirmation filter (e.g., roc_24h >= 0 or last-bar return positive) as a secondary gate on top of the roc_168h oversold signal to prevent entry into still-declining momentum, targeting only genuine exhaustion bounces."
}
```
