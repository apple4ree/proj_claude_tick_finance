# wiki/log.md

Append-only research journal. wiki-log writes here.

## [2026-04-27] init | ResearchWiki initialized

- mode: adopt
- language: ko
- deepscan-tool: understand-anything
- seed-from: research-diary

## [2026-04-27 04:21] log | decision | objective-from-wr-to-net-pnl

Chain 1의 1차 reward를 WR에서 net_expectancy(= expectancy_bps − fee_bps_rt)로 전환 — 4개 stage(feedback_analyst, signal_improver, signal_generator, orchestrator)에 fee_bps_rt parameter plumbing.

→ wiki/decisions/objective-from-wr-to-net-pnl.md

## [2026-04-27 04:24] log | experiment | fresh-v3-chain1-25iter-3sym-8date

Fresh v3 — chain1 25-iter × 3-sym × 8-date 완료, 80 spec 백테스트, KRX 23 bps RT 수수료 벽 0/80 통과 (max gross 13.32 bps).

→ wiki/experiments/exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date.md

## [2026-04-27 04:24] log | experiment | fresh-v4-fix1-net-pnl-objective

Fresh v4 — Fix #1 (WR → net-PnL objective) 적용한 chain1 25-iter run, 진행 중(iter_004); 첫 4 iter에서 tighten_threshold 사용 8→0회, mean horizon +46%, hypothesis 키워드 expectancy 0→13.

→ wiki/experiments/exp-2026-04-27-fresh-v4-fix1-net-pnl-objective.md

## [2026-04-27 04:25] log | decision | block-f-magnitude-primitives-and-cheat-sheets

Block F 추가 — 3 time-of-day boolean primitive(is_opening/lunch/closing_burst) + RollingRangeBps helper + 2 cheat sheet(magnitude_primitives, time_of_day_regimes), Fix #1 결정 트리의 magnitude-seeking 행동을 표현 가능하게 함.

→ wiki/decisions/block-f-magnitude-primitives-and-cheat-sheets.md

## [2026-04-27 04:26] log | free | hypothesis-vs-result-divergence-v3

v3 hypothesis vs result divergence 정밀 분석 — direction 95% 정확 / B3 67% cite-but-fail / mutation random walk 후반 / 정량 claim 50%, fee 명시 거의 부재.

→ wiki/notes/2026-04-27-hypothesis-vs-result-divergence-v3.md

## [2026-04-27 07:09] log | decision | krx-only-deployment-scope

Deployment scope 를 KRX cash equity 한정으로 좁힘 — crypto pivot decision 폐기, sell tax 20 bps 가 mechanical constraint 로 chain 1 13 bps 신호로는 통과 불가 인정.

→ wiki/decisions/krx-only-deployment-scope.md

## [2026-04-27 07:10] log | decision | p1-staged-additions-for-v5

P1 (Kyle λ proxy + autocorr helper + 3 paper summaries + 5 concept pages) 를 dormant 상태로 사전 추가 — v5 launch 가속, v4 ablation 영향 최소화.

→ wiki/decisions/p1-staged-additions-for-v5.md

## [2026-04-27 07:11] log | experiment | regime-state-paradigm-ablation

Regime-state paradigm 검증 ablation 진행 중 — chain 1 의 fee accounting 이 statistical artifact 인지 진짜 신호 천장 측정인지 80 spec × 3 sym × 2 date 로 결정.

→ wiki/experiments/exp-2026-04-27-regime-state-paradigm-ablation.md

## [2026-04-27 10:07] log | decision | regime-state-paradigm-default

Chain 1 의 default backtest paradigm 을 fixed-H tick-trigger 에서 regime-state (signal-driven entry/exit + force-close 제거) 로 전환 — v5 가 첫 fair 측정.

→ wiki/decisions/regime-state-paradigm-default.md

## [2026-04-27 10:07] log | experiment | fresh-v5-regime-state-paradigm

Fresh v5 — chain 1 의 paradigm shift (regime-state + Fix #1 + 5 agent prompt 재정비) 후 첫 fair 측정. v3/v4 의 0/total fee 통과를 깨는지 검증.

→ wiki/experiments/exp-2026-04-27-fresh-v5-regime-state-paradigm.md
