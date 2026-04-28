---
date: 2026-04-27 02:30
tone: milestone
title: v4 fresh run launch with Fix #1
---

## Context
Fix #1 4-stage plumbing 검증 완료(unit test + CLI smoke). v3 baseline과 동일 config로 v4 background run 시작. 25 iter × 4 candidates × 3 sym × 8 date.

## Done
- v3 archive 이동: iterations/ → iterations_v3_archive/ (2.5 GB 보존)
- 새 iterations/ 생성
- v4 background launch: `chain1.orchestrator run --max-iter 25 --n-candidates 4 --symbols 005930 000660 005380 --dates 20260316 ... 20260325 --calibration-table data/calibration/krx_v2_2026_03_3sym.json --fee-bps-rt 23.0`
- Process 정상 가동 확인 (PID 2567353, log /tmp/chain1_logs/fresh_run_v4.log)
- 첫 줄 로그 확인: "[loop] objective = net_expectancy (fee_bps_rt=23.0 bps RT)"

## Numbers
- PID: 2567353
- 시작 시각: 2026-04-27 02:31 KST
- 예상 완료: ~6시간 후
- v3 archive 크기: 2.5 GB
- fee_bps_rt: 23.0

## Next
- iter_004 진행 시점에 v3 vs v4 ablation 분석
- LabHub은 현재 500 (서버 다운), 회복 시 새 run 등록
