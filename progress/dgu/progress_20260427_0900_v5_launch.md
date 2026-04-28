---
date: 2026-04-27 09:00
tone: milestone
title: v5 fresh run launch — regime-state paradigm + Fix #1
---

## Context
Chain 1 의 모든 layer 정비 완료. 첫 fair test of regime-state paradigm. v3 (fixed-H legacy) / v4 (Fix #1 only) / v5 (regime-state + Fix #1) 3-way ablation 완성.

## Done
- iterations/ archive: iterations_v4_archive (18 iter from v4)
- 새 iterations/ 생성
- v5 background launch:
  - PID 2845354
  - chain1.orchestrator run --max-iter 25 --n-candidates 4
  - --symbols 005930 000660 005380
  - --dates 20260316 ~ 20260325 (8 dates)
  - --calibration-table data/calibration/krx_v2_2026_03_3sym.json
  - --fee-bps-rt 23.0
- log 첫 줄 확인: "[loop] objective = net_expectancy (fee_bps_rt=23.0 bps RT)"
- backtest mode = regime_state (default)

## Numbers
- PID: 2845354
- Expected duration: 4-6 hours
- v3/v4/v5 ablation: 3 conditions completed for paper
- Total reference docs updated this session: 12

## Decisions & Rationale
- v5 = 진정한 regime-state baseline. Prompts 가 regime-state 인지하고 spec 짜는 첫 번째 실험.
- 기존 fixed-H mode 는 opt-in 으로 보존 (mode="fixed_h") — 백워드 호환

## Next
- 모니터링 + 결과 분석 (~6시간 후)
- LabHub flow ingest (이번 세션 progress files)
- 결과에 따라 paper writing 또는 추가 실험 결정
