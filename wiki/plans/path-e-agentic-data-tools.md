---
schema_version: 1
type: plan
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, signal-generator, agentic, tool-use, litellm, post-v5]
refs:
  code:
    - {path: "chain1/llm_client.py", confidence: verified}
    - {path: ".claude/agents/chain1/signal-generator/AGENTS.md", confidence: verified}
  papers:
    - alphaagent-2025
    - quantagent-2025
  concepts:
    - reward-target-mismatch
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-E-agentic-data-tools
status: superseded
superseded_by: PLAN-F-tool-use-and-raw-column
trigger: post-v5-completion
priority: high
---

> **2026-04-28 SUPERSEDED**: 이 plan 은 [path-f-tool-use-and-raw-column.md](path-f-tool-use-and-raw-column.md) 에 흡수됨. F 의 Phase 1 = 이 plan 의 모든 작업, Phase 2 = + Level 2 (raw column read AST validator) 추가. 단계적 적용 + ablation v7a/b/c 로 효과 분리 측정.

# Path E — Agentic Data-Analysis Tools (sub-agent + LiteLLM tool-use)

## 문제

Path A/C/D 가 baseline / partition / T-scaling 을 정적 cheat sheet 로 LLM 에 주입. 그러나:
1. **Static cheat sheet 의 한계**: LLM 이 spec 작성 시점에 "이 specific feature × threshold 의 historical performance 가 어땠나?" 같은 dynamic query 불가능.
2. **Signal-generator 의 부담**: hypothesis 작성 + spec 작성 + 가설 정량화 를 모두 한 LLM call 에 — attention 분산.
3. **Data analyst 분리 효과**: 별도 agent 가 query 해석 + 데이터 lookup + 통계 요약 을 담당하면, signal-generator 는 design 에 집중.

해결: signal-generator 에게 **`consult_data_analyst(question)` tool** 을 쥐어주기. 내부적으로 data-analyst sub-agent 가 4 개의 query tool 을 사용해 답변.

## 제안 design (Hybrid Option III)

```
signal-generator (LLM, multi-turn loop via LiteLLM tool-use)
   │
   ├─ tool: consult_data_analyst(question: str) → answer: str
   │     │
   │     └─ internally invokes: data-analyst (LLM, separate AGENTS.md)
   │            │
   │            ├─ tool: query_distribution(feature, partition) → table
   │            ├─ tool: query_regime(feature, threshold) → regime stats
   │            ├─ tool: query_t_scaling(feature, T_list) → magnitude table
   │            └─ tool: query_paper(topic) → relevant paper passage
   │
   └─ tool: submit_spec(spec_dict) → end of loop
```

**E.1 LiteLLM tool-use 확장** — `chain1/llm_client.py`:
- 현재: `litellm.completion(messages, ...)` — single response
- 추가: `tool_use_loop(messages, tools, max_iter=8)` — multi-turn
  - 각 iteration: completion call → if `tool_calls` in response → execute tools → append to messages → loop
  - end condition: `submit_spec` tool 호출 OR max_iter 도달
- LiteLLM 의 OpenAI-compatible tool spec 사용 (Anthropic / OpenAI / Gemini 모두 동일 schema)

**E.2 data-analyst sub-agent** — 신규 agent:
- Path: `.claude/agents/chain1/data-analyst/AGENTS.md`
- System prompt: "You are a data analyst for KRX tick data. Answer questions about feature distributions, regime statistics, T-scaling, and microstructure literature."
- Input schema: `{question: str}`
- Output schema: `{answer: str, evidence_refs: List[str]}`
- Reasoning flow: question parse → tool selection → tool exec → synthesize answer
- Tools: 4개 (E.3 참조)

**E.3 Data query tools** (data-analyst 가 내부 사용):

```python
# Tool 1: query_distribution
{
  "name": "query_distribution",
  "description": "Get distribution stats for a feature in a partition cell",
  "parameters": {
    "feature": "obi_1 | obi_3 | ofi_1 | microprice_dev_bps | ...",
    "time_partition": "opening_30min | morning_60min | ...",
    "vol_partition": "low | mid | high"
  },
  "returns": {"mean": float, "median": float, "p90": float, "n": int}
}

# Tool 2: query_regime
{
  "name": "query_regime",
  "description": "Simulate a (feature > threshold) regime and report stats",
  "parameters": {"feature": str, "threshold": float, "long_if": "pos | neg"},
  "returns": {"duty_cycle": float, "mean_duration_ticks": float, "n_regimes_per_session": float, "expectancy_bps": float}
}

# Tool 3: query_t_scaling
{
  "name": "query_t_scaling",
  "description": "Get magnitude / WR / decay across holding periods T",
  "parameters": {"feature": str, "threshold": float},
  "returns": [{"T": int, "mean_abs_delta_bps": float, "wr": float}, ...]
}

# Tool 4: query_paper
{
  "name": "query_paper",
  "description": "Lookup relevant paper passage about a microstructure concept",
  "parameters": {"topic": str},
  "returns": {"papers": [{"slug": str, "passage": str, "page": int}, ...]}
}
```

**E.4 Tool implementation** (Python, query 백엔드):
- `query_distribution`: Path C 의 `data/calibration/empirical_baselines.json` lookup
- `query_regime`: live computation on KRX CSV (cached) — 실측 backtest 의 mini 버전
- `query_t_scaling`: Path D 의 `data/calibration/t_scaling.json` lookup
- `query_paper`: `chain1/_shared/references/papers/` markdown grep + LLM summarize

**E.5 signal-generator 통합**:
- AGENTS.md 에 tool-use 기반 prompt 추가: "You can ask the data analyst questions before writing your spec. Limit to 3 questions."
- 기존 single-shot `_build_user_message` 를 multi-turn loop 으로 변경
- max 3 questions to keep cost bounded

**E.6 LiteLLM 호환성 검증**:
- Anthropic Claude (현재 default): tool-use native support ✓
- OpenAI GPT: native ✓
- Gemini: function calling ✓ (LiteLLM 변환)
- 모든 provider 에서 tool spec 동일하게 작동 검증

**E.7 Cost analysis** (predicted):
- Per-spec normal: 1 LLM call × $0.01 = $0.01
- Per-spec with tools: 1 signal-gen call + 3 data-analyst calls (each with 1~2 tool exec) = ~5~7 LLM calls × $0.01 = $0.05~0.07
- Per iter: 4 specs × $0.05 = $0.20
- Per run: 25 iter × $0.20 = $5 (vs current ~$1) — 5x cost
- Acceptable if performance gain > 30%

## 구현 단계

```
E.1  litellm tool_use_loop() 함수 작성              (4h)
E.2  data-analyst AGENTS.md + Pydantic schema       (3h)
E.3  4 query tool 의 Python 백엔드                  (8h)
     - query_distribution: lookup (Path C 의존)      (1h)
     - query_regime: live compute (cache)             (3h)
     - query_t_scaling: lookup (Path D 의존)          (1h)
     - query_paper: grep + summarize                  (3h)
E.4  signal-generator multi-turn 통합               (4h)
E.5  cost / latency monitoring (telemetry)          (2h)
E.6  smoke test: 1 iter × 1 sym, hypothesis quality  (2h)
E.7  full run comparison (E vs no-E baseline)       (8h)
─────
total ~30h, 약 1주 작업
```

## 성공 기준

1. **Tool usage rate**: smoke test 4 specs 중 ≥ 3 specs 가 ≥ 1 tool query 사용.
2. **Hypothesis quality**: hypothesis 텍스트의 numerical claim 이 query 결과 ±20% 범위 내 (현재 v5 는 ±100% 이상 어긋남).
3. **Spec quality**: full run (25 iter) 의 best gross 가 baseline (Path A 만 적용) 대비 ≥ 30% 향상.
4. **Cost**: per-run cost ≤ $10 (5x 이내).
5. **Latency**: per-iter wall-time 증가 < 50% (현재 17 min → 25 min 이내).
6. **LiteLLM 호환**: 3 provider (Anthropic / OpenAI / Gemini) 에서 동일하게 작동.

## 의존성 / ordering

- **선행**: v5 종료 + Path C (empirical_baselines.json) + Path D (t_scaling.json) 데이터 산출물
- **선행 강력 권장**: Path A (calibration / AGENTS.md trim) 후에 — 그렇지 않으면 trim 안 된 prompt 위에 tool 까지 더해져 too heavy
- **권장 순서**: A → C → D → B → E (E 가 가장 마지막)
- **충돌 가능**: B 의 maker_spread 측정 결과를 E 의 5번째 tool (query_spread_capture) 로 추가 가능 — extension

## 위험 / blocker

1. **LiteLLM tool-use bug / inconsistency**: provider 별 tool_calls schema 미세 차이. — Mitigation: smoke test 에서 3 provider 검증.
2. **Tool-call infinite loop**: LLM 이 같은 question 반복 → cost 폭증. — Mitigation: max_iter=8 hard cap + dedupe question hash.
3. **data-analyst 의 hallucination**: tool 결과 안 보고 임의 답변. — Mitigation: AGENTS.md 에 "answer must cite tool result", 검증 evaluator 추가.
4. **Cost regression**: 5x 가 not OK 면 single-shot fallback 도 유지 (config flag).
5. **Latency regression**: 25 min/iter 가 50 min/iter 되면 불편. — Mitigation: tool query parallelization.
6. **Cheat sheet vs tool 의 redundancy**: A/C/D 의 cheat sheet 가 이미 정보 제공 → tool 이 incremental value 가 적을 수도. → smoke test 결과로 결정.
7. **Sub-agent 가 inconsistent answer**: 같은 question 에 다른 답변. — Mitigation: temperature=0 for data-analyst.

## 예상 영향

- Hypothesis-result divergence 감소 (Path A 만으로는 부족했던 부분)
- LLM 이 "이 spec 의 expected gross 는 X bps" 같은 quantified claim 가능 — 현재는 unanchored
- Future: Path B (maker spread) tool 추가, Path C/D refresh 시 tool 자동 활용
- Paper-target framing: "agentic tool-use for hypothesis grounding" — alphaagent-2025 / quantagent-2025 와의 차별점

## 미정 사항

- E.3 query_regime 의 live compute vs precompute (live = 정확하나 느림)
- E.5 max_questions 의 적정 — 3 vs 5 (cost 와 latency trade-off)
- data-analyst 가 추가로 data-validator agent 호출할지 (chain depth → 무한)
- LiteLLM 가 tool-use 미지원 provider (legacy LLaMA 등) 사용 시 fallback
