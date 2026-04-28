---
date: 2026-04-27 08:30
tone: pivot
title: Chain 1 paradigm shift — fixed-H to regime-state (v5)
---

## Context
사용자 통찰: "단위만 tick이고, 신호에 따라 진입/청산하는 메커니즘이면 충분하다." Chain 1 의 fixed-H paradigm 이 자연스럽지 않다는 점 명확. 매 tick fire = N trades = N × fee 부과로 mechanically 자기-패배. v3/v4 의 0/80 fee 통과는 paradigm artifact 일 가능성.

## Done
- backtest_runner.py 에 regime_state mode 추가 (default 변경)
- BacktestResult schema 확장: n_regimes, signal_duty_cycle, mean_duration_ticks
- End-of-session force-close 제거 (사용자 요청, buy-and-hold artifact 자동 제거)
- feedback_analyst 에 sanity check 추가 (duty>0.95 swap, n_regimes<1.5 loosen, mean_dur<5 add_filter)
- Master cheat sheet regime_state_paradigm.md 작성 (3 axis framework, target ranges, anti-patterns, hypothesis template)
- All agent prompts 재정비:
  - signal-generator: regime-state semantics + 새 reasoning flow + hypothesis template
  - signal-evaluator: prediction_horizon_ticks deprecate, soft check 추가
  - feedback-analyst: regime metrics decision tree
  - signal-improver: tighten/loosen 재해석, change_horizon deprecated → "extend hold"
  - chain2-gate: G1-G5 재정의 (G5=duty/duration sanity)
- prior_iterations_index.md reset (v3/v4 archive 보존)
- iterations/ → iterations_v4_archive 보관
- v5 fresh launch (PID 2845354)

## Numbers
- 변경 모듈 수: 8 (4 agents + backtest_runner + schemas + orchestrator + 1 master cheat sheet)
- 변경 prompt: 5 AGENTS.md / reference docs
- v3 archive: 100 spec 보존, prior_index.md.v3v4_archive 로 backup
- v5 config: 25 iter × 4 candidates × 3 sym × 8 dates × fee 23 bps RT
- 예상 소요: 4-6시간

## Decisions & Rationale
- Force-close 제거 사용자 결정 — buy-and-hold artifact (이전 14 spec n=6 + 102bps) 자동 제거
- regime-state 이 default (legacy fixed-H 는 opt-in 으로 보존)
- prediction_horizon_ticks 명시적으로 deprecated 표시 — v5+ LLM 에 혼란 방지
- v3 spec 들 정식 backtest 재측정은 skip — fixed-H 시대에 짜여져서 fair eval 어렵다는 게 smoke test 에서 확인. v5 가 첫 fair 측정.

## Discarded
- "v3 archive 80 spec 정식 chain1 backtest_runner 통과 재측정" task — sample 결과 (iter000_ask_wall_reversion: n=6375 mean=-0.25bps) 가 paradigm 효과 없음을 충분히 보임
- Standalone ablation 의 17/80 deployable 결과 — force-close artifact

## Next
- v5 진행 모니터링 (~30분 / iter)
- 결과 분석 후 paper writing 시작 결정
