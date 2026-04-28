---
date: 2026-04-27 01:00
tone: result
title: Fresh v3 25-iter 완료, fee 벽 0/80
---

## Context
어제 백그라운드로 돌렸던 chain1 fresh v3 (25 iter × 3 sym × 8 date) 18시간 4분 만에 완료. v3는 WR 기반 1차 reward, tickdata_krx parquet + Block E trade-event primitive + per-symbol calibration (D1) + 종목 다양화(005930/000660/005380) 조합의 효과 측정 목표.

## Done
- 25/25 iter 완료, 100 spec 제안 → 80 spec 백테스트 완료 (eval/fidelity gate 20% reject)
- Family 분포 분석: bbo_push/wall(23) consensus(15) trade_flow Block E(14) bbo_divergence(10) OBI 단독(9)
- Post-fee 시나리오 4종 비교 (crypto maker 4bps / crypto taker 8bps / 가상 15bps / KRX 23bps)
- Hypothesis vs result divergence 정밀 분석: direction 95% 적중, Category B3만 67% (cite-but-fail), mutation 개선력 후반 random walk

## Numbers
- WR mean 0.788 / median 0.846 / max **0.963** (iter014_bbo_divergence_low_vol)
- expectancy_bps mean 5.79 / median 6.73 / max **13.32** (iter005_ask_wall_reversion_low_vol)
- Crypto maker 4bps 시나리오: 66/80 흑자
- KRX 23bps RT 수수료 벽: **0/80 통과** (max net = -9.68 bps)
- Block E (trade events) 평균 4.31 bps — OBI/OFI 대비 추가 edge 부재

## Next
- Fix #1 결정 (objective WR → net_expectancy), 4 stage plumbing 작업
- v4 launch (동일 config + --fee-bps-rt 23.0)
- v3 결과를 LabHub run exp-te3rax success로 마감
