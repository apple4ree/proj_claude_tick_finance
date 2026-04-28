---
date: 2026-04-27 07:00
tone: result
title: Regime-state ablation 결과 + force-close artifact 진단
---

## Context
80 spec standalone regime-state 측정 완료 (PID 2754133, 1h43m). 첫 인상은 17/80 deployable (mean > 28 bps) 였으나, 정밀 분석 결과 대부분 force-close artifact 였음을 발견.

## Done
- 80/80 spec 완료, mean(mean_gross) +13.68 bps, max +102.57 bps
- 17 spec mean > 28 bps, 그러나 14/17 이 동일한 패턴: n=6 regimes × 6 sessions × 평균 4시간 30분 보유
- 원인 분석: standalone script 의 end-of-session force-close 가 "거의 항상 ON 인 신호" 를 강제 청산해 가짜 regime 생성
- iter000_ask_wall_reversion: 사실 매우 자주 토글하는 signal (n=6375 regimes, duty 12.9%, mean -0.25 bps), force-close 없으면 정상 측정

## Numbers
- 80 spec n=6 + mean +102.57 bps 패턴: 14개 (모두 artifact)
- 진짜 의미 있는 deployable 후보 (force-close 없을 때): 0개
- iter000 force-close 시 n=6 → 실측 n=6375 (1000× 차이)

## Decisions & Rationale
- Standalone ablation 의 17/80 deployable 결과 폐기 — force-close artifact
- 정식 chain 1 backtest_runner 에 regime-state mode 통합 + force-close 제거 결정
- Sanity check 추가: signal_duty_cycle > 0.95 → swap_feature, n_regimes/sessions < 1.5 → loosen, mean_dur < 5 → add_filter

## Discarded
- "Regime-state paradigm 만으로 KRX 통과 가능" 가설 폐기 — v3 spec 들은 fixed-H interpretation 으로 짜여져 regime-state 에서도 천장 13 bps 수준
- standalone analysis/regime_state_ablation.py 결과는 reference only

## Next
- 정식 chain 1 backtest_runner 에 regime-state mode 통합
- All agent prompts 재정비 (regime-state paradigm 에 맞게)
- 기존 80 spec 정식 backtest 통해 재측정 (deprecated — v5 launch 가 더 가치)
