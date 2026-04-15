---
id: lesson_20260415_019_session_drop_regime_filter_cleanly_excises_downtrend_losses
created: 2026-04-15T06:54:32
tags: [lesson, regime_filter, session_drop, entry_gate, win_rate, downtrend]
source: strat_20260415_0025_krx_resting_limit_4sym_regime_filter
metric: "return_pct=0.5969 trades=9 win_rate=66.7 avg_win_bps=108.52 avg_loss_bps=-83.70"
---

# Session-drop regime filter cleanly excises downtrend losses

Observation: Adding an 80 bps session-drop gate to strat_0014 blocked 6 trades and raised WR 53.3%→66.7% and return 0.506%→0.597%; all 6 blocked trades appear to have been losses.

Why: Passive BID resting orders in stocks already down >80 bps from today's open get filled by continued downside momentum — the very condition that generates adverse fills. Skipping entry when intraday drop exceeds threshold avoids precisely the regime where this strategy's mean-reversion assumption breaks.

How to apply next: Use session_drop_gate_bps as a first-class risk parameter. Before widening to 60 bps or adding asymmetric lot sizing, validate gate calibration on OOS dates (20260305-20260313). If 60 bps recovers blocked trades with WR ≥60%, loosen it; otherwise keep at 80. Asymmetric lot sizing (lot=3 for 000660, lot=1 for others) is the lower-variance lever to amplify return without touching gate logic.

## Update — strat_20260415_0026_oos_regime_filter (pre-IS OOS validation)

OOS on pre-IS dates 20260305-20260313: return=-0.0139%, N=4, WR=25.0%. 000660 buy-hold was -7.43% over that window — a sustained downtrend. The 80 bps session-drop gate produced only 4 entries and failed to protect: individual intraday drops were below gate threshold even as multi-day trend was deeply bearish. Gate calibration verdict: 80 bps is necessary but not sufficient; a multi-day trend condition is required to complement it.
