---
date: 2026-04-27 06:30
tone: design
title: Regime-state paradigm 검증 ablation 시작
---

## Context
사용자 제안: signal 을 binary state indicator 로 보고, 1 인 동안 보유 / 0 으로 전환 시 청산. 이러면 fee 가 매 tick 이 아니라 매 regime 마다 1번 부과 — fee economics 가 근본적으로 바뀜. Tick-trigger model 의 cumulative fee 는 사실 statistical artifact.

## Done
- Standalone analysis script 작성: analysis/regime_state_ablation.py
- v3 archive 의 80 spec 모두를 regime-state interpretation 으로 재측정하는 ablation
- Smoke test 통과 (3 spec × 1 sym × 1 date)
  - iter000_full_book_consensus 가 첫 시도에서 mean +10.81 bps, 34% regime 이 fee 통과 — interesting signal
- 본 측정 launch (PID 2754133, 80 spec × 3 sym × 2 date = 480 backtests, 예상 ~30분)

## Numbers
- 기존 chain 1 model: N_trades = O(thousands), 누적 fee 천문학적
- Regime-state model: N_trades = O(transitions) ~5–50/day, fee 1 RT/regime
- Smoke test 1번 spec: 123 regimes, mean +10.81 bps, fee_pass 34.1%
- 측정 대상: KRX 23 bps fee 통과 spec 비율 (목표: >0/80)

## Decisions & Rationale
- v4 fresh run 종료 대기 안 하고 paradigm 자체부터 검증 — 방법론적 우선순위 더 큼
- Standalone script 로 시작 (chain 1 backtest_runner 직접 수정 안 함) — 결과 보고 통합 결정
- 정규 chain 1 결과 (aggregate_expectancy_bps) 와 regime-state 결과 (mean_regime_gross_bps) 의 distribution 비교

## Next
- 결과 나오면 (~07:00) 두 model 의 spec-level 비교
- mean_regime_gross > 28 bps (fee 23 + spread 5) spec 발견 시 → KRX deployable signal 존재 확인
- 발견 0 이면 → chain 1 backtest 의 fee accounting 자체가 문제 아니라 진짜 신호 천장 낮은 것
