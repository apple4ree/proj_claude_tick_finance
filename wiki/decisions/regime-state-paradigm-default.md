---
schema_version: 1
type: decision
created: '2026-04-27'
updated: '2026-04-27'
tags: []
refs:
  code:
  - path: chain1/backtest_runner.py
    symbol: backtest_symbol_date_regime
    confidence: inferred
  - path: chain1/backtest_runner.py
    symbol: run_backtest
    confidence: verified
  - path: chain1/agents/feedback_analyst.py
    symbol: _primary_recommendation
    confidence: verified
  - path: .claude/agents/chain1/_shared/schemas.py
    symbol: BacktestResult
    confidence: verified
  papers: []
  concepts:
  - capped-post-fee
  - net-pnl-objective
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
  - exp-2026-04-27-regime-state-paradigm-ablation
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
decision_id: DEC-2026-04-27-regime-state-paradigm-default
status: accepted
supersedes:
- fixed-h-paradigm-implicit
superseded_by: []
scope:
- chain1.backtest_runner
- chain1.feedback_analyst
- chain1.orchestrator
- _shared.schemas
- all-5-agents
---

# regime-state-paradigm-default

## 문제
v3 (legacy fixed-H) 의 0/80 fee 통과 결과 + v4 (Fix #1 only, fixed-H) 의 0/18 fee 통과 결과 분석에서 chain 1 의 'tick-trigger + fixed horizon' paradigm 자체의 mechanical 한계 발견. 매 tick fire 시 N trades 가 같은 mid 움직임을 N 번 카운트하면서 fee 도 N 번 부과 — KRX 23 bps RT × 1000+ trades = 천문학적 부담. 사용자 지적: tick 단위는 결정 frequency, holding period 는 신호가 결정해야 함.

## 검토한 옵션
Option A: 그대로 두고 Fix #2 (search algorithm 개선) — paradigm 자체 문제 해결 못 함. Option B: 별도 standalone regime-state ablation 만 — chain 1 정식 통합 안 됨. Option C: 정식 backtest_runner 에 regime-state mode 통합 + force-close 제거 + agent prompts 모두 재정비. Option D: Multi-day holding paradigm 으로 (PRISM-INSIGHT 처럼) — daily 시장으로 frequency 변경, 본 프로젝트 KRX cash tick scope 와 다름.

## 선택한 접근
Option C 채택. backtest_runner.run_backtest 에 mode='regime_state' 옵션 (default 변경), schema 에 n_regimes/signal_duty_cycle/mean_duration_ticks 추가, end-of-session force-close 제거 (사용자 결정 — buy-and-hold artifact 자동 제거). 5 agent prompts 모두 재정비: signal-generator (regime-state semantics + hypothesis template + reasoning flow), signal-evaluator (horizon check deprecate + regime soft check), feedback-analyst (sanity checks: duty>0.95 / n_regimes/sessions<1.5 / mean_dur<5), signal-improver (mutation 재해석 — tighten 은 duty cycle 좁히기), chain2-gate (G1-G5, G5: duty/duration sanity). Master cheat sheet regime_state_paradigm.md 신규.

## 근거
v3 standalone regime-state ablation 결과 (2026-04-27 07:00) 가 결정적 evidence: 80 spec 중 17 이 mean > 28 bps deployable 처럼 보였으나, 14 가 force-close artifact (n=6 + 102 bps + 4시간 보유 = session 당 1 regime). force-close 제거 후 iter000 spec 의 진짜 메트릭은 n=6375 / mean -0.25 bps / duty 12.9%. 즉 force-close 가 'always-on' 신호를 강제 청산해 false deployable 만들었음. Sanity check 의 정량 임계값 (0.95 / 1.5×sessions / 5 ticks) 은 regime_state_paradigm.md §2.3 에서 target range (0.05–0.80 / 5–50 / 20–5000) 의 boundary 로 도출. 판단 근거 (P8): 사용자의 trader 직관 (tick-resolution monitoring + variable holding) 이 chain 1 의 design choice 의 부자연성을 정확히 짚음.

## 트레이드오프
(1) v3/v4 spec 들이 fixed-H interpretation 으로 짜여져 regime-state 에서 fair 평가 어려움 — v5 가 첫 fair 측정. (2) Schema migration: 기존 BacktestResult 사용자가 backtest_mode 필드 새로 처리 필요 (Optional 이라 backward compat). (3) prior_iterations_index 가 reset 되어 LLM 이 v3/v4 spec 의 lessons 를 다시 학습해야 함 (그러나 핵심 lesson 은 새 prior index 에 명시). (4) 일부 mutation direction (`change_horizon`) 의 의미 변화 — 이전 사용자/agent 가 기대한 것과 다름.

## 영향 범위
chain 1 전체. 변경 모듈: chain1/backtest_runner.py (regime mode + force-close 제거), .claude/agents/chain1/_shared/schemas.py (3 new fields), chain1/orchestrator.py (mode pass-through), chain1/agents/feedback_analyst.py (sanity checks), 5 agent AGENTS.md / reference docs, 신규 _shared/references/cheat_sheets/regime_state_paradigm.md. iterations/ → iterations_v4_archive 보관, v5 fresh launch (PID 2845354). 영향 없음: chain 2 (미구현), data layer.

## 재검토 조건
(1) v5 결과 (~6 hours): mean(expectancy_bps) > 0 spec 비율 측정. v3/v4 (0/total) 대비 개선 정량. (2) 만약 v5 도 0/total 이면 chain 1 spec language 자체 한계 — schema 확장 (PolicySpec, MM-aware) 또는 multi-day paradigm 으로 escalation. (3) v5 의 sanity check trigger 비율 — duty>0.95 / mean_dur<5 / n_regimes<1.5×sessions 가 50%+ 면 LLM 이 새 prompt 를 internalize 못 한 것 — generator prompt 강화 필요.
