---
schema_version: 1
type: free
created: 2026-04-27
updated: 2026-04-27
tags: [llm-agent, reward-shaping, paper-target, finding]
refs:
  code:
    - {path: "chain1/agents/signal_generator.py", symbol: "_build_user_message", confidence: verified}
    - {path: "chain1/agents/feedback_analyst.py", symbol: "_primary_recommendation", confidence: verified}
  papers: []
  concepts:
    - net-pnl-objective
    - reward-target-mismatch
  experiments:
    - exp-2026-04-27-fresh-v3-chain1-25iter-3sym-8date
    - exp-2026-04-27-fresh-v4-fix1-net-pnl-objective
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Reward Shaping → LLM Hypothesis Distribution Shift

## 노트

Paper-grade finding: **prompt-level reward function 변경 만으로 LLM 의 hypothesis text 분포가 systematic 하게 이동**. RL reward shaping 의 LLM-context 등가물.

### v3 (legacy WR-keyed) → v4 (Fix #1 net-PnL) 전환의 측정

같은 config (3 sym × 8 dates × 4 candidates), iter 0–3 동일 표본:

| Metric | v3 (legacy) | v4 (Fix #1) | Δ |
|---|---:|---:|---|
| **Recommendation 분포** |
| `tighten_threshold` 사용 | 8/14 (57%) | **0/10 (0%)** | ⭐ 완전히 사라짐 |
| `add_regime_filter` | 0 | 3 (30%) | 신규 |
| `change_horizon` | 2 | 3 (30%) | ↑ |
| `extreme_quantile` | 0 | 1 (10%) | 신규 |
| **Spec 특성** |
| Mean horizon | 26.3 ticks | 38.4 ticks | +46% |
| Max gross expectancy | 7.44 bps | 12.85 bps | +73% |
| **Hypothesis 텍스트** |
| 'fee/bps/cost' 키워드 | 4 | 10 | 2.5× |
| **'expectancy/edge' 키워드** | **0** | **13** | **신규 등장** |
| WR 키워드 | 4 | 6 | +50% |

→ "expectancy" 키워드가 v3 에서 0 회 → v4 에서 13 회. **명백한 paradigm shift** in LLM reasoning.

## Paper-grade interpretation

### Mechanism

LLM 은 generation prompt 의 framing 을 **implicit objective** 로 internalize. v4 의 prompt:
```
"Deployment fee (round-trip): 23 bps. expectancy_bps MUST exceed fee_bps_rt."
```

이 한 문장이 LLM 의 hypothesis space 을 **fee-aware reasoning** 영역으로 이동시킴. 1주 전에 0 회 등장한 'expectancy' 가 13회 등장.

### Theoretical position

- **Prompt-level intervention = soft reward shaping** for instruction-tuned LLM
- Effect 측정 가능 (hypothesis text distribution)
- Behavior 변화 측정 가능 (mutation choice distribution, spec 특성)
- → **LLM agent 의 reward shaping 이 quantitatively measurable**

### Paper § structure 후보

§Results.A — "Reward function design ablation":
- v3 baseline (WR-keyed): 0/80 fee 통과, 'expectancy' 0 회
- v4 (Fix #1): same config, 동일 표본 iter 0–3 비교
- Result: tighten 8→0, expectancy keyword 0→13, max gross +73%

§Discussion — "Implications for LLM agent design":
- "Reward shaping at prompt level is sufficient to shift LLM agent's exploration distribution"
- "Implies that current LLM-driven research frameworks under-specify their reward signal in agent prompts"

## Generalizability

이 mechanism 은 trading domain 외에도 적용:
- 어떤 LLM-driven research framework 에서 deployment objective 를 prompt 에 명시 안 하면 LLM 은 suboptimal local objective (e.g., academic Sharpe, paper-style framing) 로 drift
- 우리 result 는 KRX trading 의 specific 사례지만 paradigm 은 일반

## 링크

- `net-pnl-objective` — 본 finding 의 implementation
- `reward-target-mismatch` — generalized failure mode
- v3/v4 experiments 의 직접 evidence
