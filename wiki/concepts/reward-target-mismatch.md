---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags:
- llm-agent
- paper-target
- failure-mode
refs:
  code: []
  papers: []
  concepts:
  - net-pnl-objective
  - capped-post-fee
  - cite-but-fail
  - exp-2026-04-27-regime-state-paradigm-ablation
  experiments:
  - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
  - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
- 2026-04-27-s1
---

# Reward Target Mismatch

LLM-driven research loop 에서 **reward function 이 deployment objective 와 불일치할 때 system 이 systematically wrong direction 으로 search 하는 standard failure mode**. v3 fresh run 의 80/80 spec capped-post-fee 결과가 paradigmatic example.

본 framework 은 paper-target ("LLM-generated domain code 의 spec-implementation fidelity") 의 **§Discussion** 후보 — Fix #1 의 motivating 일반 원리.

## Definition

LLM agent loop 의 자가 개선 (improver / feedback / generator) 이 다음 reward signal 을 따른다:
- `R_loop` = loop 내부 reward (WR, gate pass count, etc.)
- `R_deploy` = 실제 deployment objective (net PnL, accuracy in target domain, etc.)

**Mismatch** 발생 조건: `R_loop` 와 `R_deploy` 의 gradient 가 두 차원 이상에서 다른 부호 / 다른 크기.

LLM 은 `R_loop` 를 climb 하면서 `R_deploy` 가 정체하거나 악화됨. v3 의 경우:
- `R_loop` = WR (correct directional prediction rate)
- `R_deploy` = net_PnL = (2·WR − 1) · |Δmid| · n_trades − fee · n_trades
- WR 차원과 |Δmid| 차원의 partial derivative 가 LLM 의 mutation step 에서 다른 부호 — WR climb 이 |Δmid| 를 자동으로 키우지 않음

## Standard symptoms

1. **Loop convergence ≠ deployment success**: stop condition (best WR plateau) 만족하나 deploy 시 음수 결과
2. **Mutation random walk**: 후반 iteration 에서 mutation 의 R_deploy 개선력이 random 에 수렴 (v3 측정: mid/late phase 에서 50% — 동전 던지기)
3. **Hypothesis drift**: LLM 이 R_loop 차원 (WR) 만 reasoning 에서 다루고 R_deploy 차원 (fee, magnitude) 은 무시 (v3 측정: 'fee' / 'expectancy' 키워드 함유율 ≤ 5%)

## Detection

Pre-launch:
- `R_loop` 와 `R_deploy` 의 정의를 명시 비교
- `R_loop` 가 `R_deploy` 의 strict monotonic transform 인지 검증 — 아니면 mismatch

Post-result:
- Top-N spec 의 deployment metric 분포가 `R_loop` 분포와 decorrelate 되면 mismatch 의증
- v3 case: top WR spec 들의 net PnL 이 모두 음수, WR ↔ net 의 cross-section correlation 약함

## Mitigation (v4 = Fix #1 의 응용)

가장 단순한 mitigation: `R_loop` 를 `R_deploy` 의 직접 proxy 로 교체.
- v3: R_loop = WR
- v4: R_loop = expectancy_bps − fee_bps_rt = direct proxy of `R_deploy`

이를 위한 4-stage plumbing 이 net-pnl-objective decision 의 내용. Generalizable pattern:
- Reward 차원 변경은 단일 ranking key 변경이 아니라 generation prompt + feedback decision tree + improver ranking + convergence detection 4 곳을 동시 수정해야 일관됨.

## Wider connection (paper §Discussion)

- **Sutton 1992** "Adapting Bias by Gradient Descent" / **Singh-Barto-Chentanez 2005** "Intrinsically Motivated Reinforcement Learning" — 일반 RL 에서 reward shaping 의 위험
- 본 framework 은 RL 이 아닌 **LLM-driven program search** 영역에서 같은 mechanism 의 발현
- Difference: LLM 은 explicit reward signal 보다 **prompt 의 framing** 으로 implicit objective 를 학습 — prompt 의 단어 선택이 reward 의 등가물 (cf. v4 의 "expectancy_bps MUST exceed {fee}" prompt 추가가 hypothesis 텍스트의 'expectancy' 키워드를 0 → 13 으로 변화시킴)

## Status

- 2026-04-27: 정식 명명, paper §Discussion 후보
- v3 ↔ v4 ablation 으로 mismatch ↔ correction 의 quantitative 효과 측정 중
- 후속 ablation 후보: R_loop 가 R_deploy 의 strict monotonic 일 때 vs partial monotonic 일 때의 search efficiency 비교
