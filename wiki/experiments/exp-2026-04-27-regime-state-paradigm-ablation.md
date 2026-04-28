---
schema_version: 1
type: experiment
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code: []
  papers: []
  concepts:
  - capped-post-fee
  - net-pnl-objective
  - reward-target-mismatch
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
  - regime-state-paradigm-default
  - exp-2026-04-27-fresh-v5-regime-state-paradigm
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
git_ref: 1465dc7
run_duration: null
seed: null
experiment_id: exp-2026-04-27-regime-state-paradigm-ablation
status: in_progress
pid: 2754133
started: '2026-04-27T06:46:00+09:00'
---

# regime-state-paradigm-ablation

## 가설
사용자 제안: chain 1 의 'tick-trigger + fixed horizon' paradigm 이 fee accounting 측면에서 잘못된 측정을 하고 있다는 가설. 매 tick 마다 신호 fire 시 독립 trade 로 카운트하면 같은 mid 움직임이 N 번 계수되어 statistical artifact 발생. 대신 binary state machine (signal=1 → 보유, signal=0 → 청산) 으로 보면 fee 가 매 regime 마다 1 RT 만 부과 — fee economics 가 근본적으로 다름. 만약 80 spec 중 mean_regime_gross > 28 bps (KRX 23 bps fee + 5 bps spread) 인 spec 이 발견되면 v3 의 0/80 결과는 paradigm artifact 였다는 결론.

## 셋업
Standalone analysis script: analysis/regime_state_ablation.py. 80 spec 모두를 v3 archive (iterations_v3_archive/iter_*/code/) 에서 import, 같은 KRX 데이터 (3 sym × 2 dates: 005930, 000660, 005380 × 20260319, 20260323) 로 regime-state interpretation 재측정. State machine 구현: FLAT + signal=True → ENTER; LONG + signal=True → HOLD; LONG + signal=False → EXIT; FLAT + signal=False → STAY. End-of-session force-close. PID 2754133, 06:46 launch, 예상 ~80분.

## 결과
현재 진행 중 (~13/80 spec 완료). 일부 early observations: (1) iter000_full_book_consensus n=4998 regimes mean +3.84 bps fee_pass 1.0% — signal 자주 토글하여 사실상 tick-trigger 회귀 패턴. (2) iter000_ask_wall_reversion / iter001_ask_wall_reversion_tight / iter001_trade_flow_obi_inverted_h100 / iter002_deep_book_divergence — 4 spec 이 동일하게 n=6 regimes mean +102.57 bps fee_pass 50%. 표본 6 개라 통계적 의미 약하나 흥미로운 magnitude. (3) iter002_spread_discounted_obi / iter003_obi1_baseline / iter003_obi_shape_modulated — n=67 mean -9.12 bps 동일 결과 — 같은 primitive 조합으로 동일 regime 구조. (4) iter003_ask_wall_neutral_bbo n=1678 mean +0.17 bps — toggling 빠른 spec.

## 관찰
Regime 분포가 spec 별로 매우 다름 (n=6 ~ n=4998). 빈번한 toggling 이 있는 spec 은 tick-trigger paradigm 과 효과적으로 동등 (같은 mid 움직임을 여러 regime 으로 잘게 나눔). 드문 toggling 의 spec 은 큰 magnitude per regime 이지만 표본이 작음 — closing auction artifact 가능성 큼 (이전 oracle 분석에서 mos=379–380 의 단일가매매 호가가 |Δmid|=149 bps 같은 비현실적 값 generate 함을 확인). n=6 + mean=+102.57 bps 패턴은 6 개 regime 이 모두 closing auction 에서 발생했을 가능성 — ablation 종료 후 regime entry/exit timestamp 분석으로 검증 필요.

## 실패 양상
현재까지 mean_regime_gross > 28 bps 인 spec 0 개 (단, 표본 13/80 으로 결론 이르름). 통과한 4 spec (mean +102.57 bps) 도 closing auction artifact 위험으로 결과 의심.

## 관련 코드
analysis/regime_state_ablation.py (신규), chain1/backtest_runner.py:iter_snaps (재사용), engine/data_loader_v2.py:load_day_v2 (데이터 로더), iterations_v3_archive/iter_*/code/*.py (80 spec 의 generated 코드 import 대상).

## 다음 단계
Ablation 종료 후 (~08:30 예상): (1) closing auction artifact 검증 — n=6 + 큰 mean 패턴의 spec 들의 regime timestamp 가 mos > 375 인지 확인. (2) Closing auction 제외 후 재측정 (가능하면). (3) mean_regime_gross > 28 bps spec 발견 여부 — 발견 시 chain 1 backtest_runner 를 regime-state 모드 옵션으로 통합. 발견 0 이면 chain 1 의 진짜 신호 천장이 낮은 것 — paradigm 이 문제 아님.
