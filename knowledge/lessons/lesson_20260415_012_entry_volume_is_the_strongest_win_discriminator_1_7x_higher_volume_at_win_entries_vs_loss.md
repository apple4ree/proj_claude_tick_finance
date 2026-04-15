---
id: lesson_20260415_012_entry_volume_is_the_strongest_win_discriminator_1_7x_higher_volume_at_win_entries_vs_loss
created: 2026-04-15T05:48:40
tags: [lesson, volume-filter, entry-signal, time-filter, obi, krx-resting-limit]
source: strat_20260415_0013_krx_resting_limit_4sym_window_10_13
metric: "return_pct=0.1694 trades=26 win_rate=42.31 avg_win_bps=107.99 avg_loss_bps=-72.72"
---

# Entry volume is the strongest win discriminator: 1.7x higher volume at WIN entries vs LOSS

Observation: In strat_0013 (KRX resting limit, 26 roundtrips), WIN entries had avg volume 1,473,287 vs LOSS entries 885,490 — a 1.7x gap — making entry volume the single strongest discriminator found so far. OBI at entry (WIN=0.540 vs LOSS=0.530) barely separated outcomes. By contrast, entry hour was a meaningful secondary filter: 11:xx delivered 75% WR while 10:xx delivered only 30% WR across the same strategy.\nWhy: High entry volume reflects genuine buyer/seller conviction behind the OBI signal, reducing the chance of a thin-book false imbalance. Low-volume imbalances invert faster (avg hold=8 ticks before reversal was observed in prior iterations), triggering stops before the limit exit fires. The 10:xx weakness is consistent with early-session spread noise before the book fully populates.\nHow to apply next: Add a minimum_entry_volume threshold (e.g., 1,000,000 shares) as a gate before the OBI check; this should prune ~half of LOSS trades while retaining most WIN trades. Alternatively or additionally, shift entry_start to 10:30 to cut the worst WR hour without sacrificing the strong 11:xx–12:xx band.
