---
schema_version: 1
type: plan
created: 2026-04-28
updated: 2026-04-28
tags: [chain1, signal-generator, agentic, tool-use, raw-column, ast-validator, post-v6]
refs:
  code:
    - {path: "chain1/llm_client.py", confidence: verified}
    - {path: "chain1/agents/signal_generator.py", confidence: verified}
    - {path: "chain1/agents/signal_evaluator.py", confidence: verified}
    - {path: "chain1/code_generator.py", confidence: verified}
    - {path: "chain1/fidelity_checker.py", confidence: verified}
    - {path: "chain1/primitives.py", confidence: verified}
  papers:
    - alphaagent-2025
    - quantagent-2025
  concepts:
    - reward-target-mismatch
    - magnitude-axes-framework
    - fixed-h-overcounting-bias
  experiments:
    - exp-2026-04-28-fresh-v6-paths-A-B-C-D
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-F-tool-use-and-raw-column
status: proposed
trigger: post-v6-completion
priority: high
supersedes:
  - PLAN-E-agentic-data-tools
---

# Path F — Tool-use + Raw column read 동시 적용

> **TL;DR**: chain 1 의 mid_gross 천장 4-5 bps 를 깨려는 시도. 두 직교 lever 를 결합:
> - **Level 4 (reasoning ↑)**: signal-generator 가 데이터 분석 LLM 에게 질문 → 답 받음 → spec 작성
> - **Level 2 (표현력 ↑)**: spec.formula 안에서 raw column (BIDP1, ASKP_RSQN5 등) 직접 사용 가능
> **동시 적용** (Part A + Part B 묶음, ~2주). Ablation v7a/b/c 로 두 lever 의 분리 효과 측정.

---

## 0. 용어 명확화 (먼저 읽기)

이 plan 의 \"sub-agent\" 와 \"agent\" 가 두 개념 사이에서 헷갈릴 수 있어 명시:

| 용어 | 의미 |
|---|---|
| **chain 1 의 agent** | chain1/agents/*.py 의 한 함수. 한 가지 \"역할\" 의 LLM 호출 (특정 system prompt + tools). 예: signal-generator, signal-evaluator |
| **chain 1 의 sub-agent** | 한 agent 안에서 \"추가\" 로 호출되는 또 다른 LLM (다른 system prompt + 다른 tools). 본 plan 의 \"data_analyst\" 가 그것. 같은 모델 (sonnet) 재호출, 다른 역할 |
| **Claude Code 의 sub-agent** | ❌ 본 plan 과 무관. 사용자 인터랙티브 세션 (Claude Code CLI / Cursor) 의 Agent tool 기능. chain 1 은 standalone Python 이라 사용 불가 |

**전부 LiteLLM acompletion 기반 LLM 호출**. \"sub-agent\" 는 architectural metaphor 일 뿐.

---

## 1. 문제 진단

v6 의 결과 (예상): 4-5 bps mid_gross 영역에 saturating. fee 23 bps 와 18 bps gap.

천장 추정 원인 두 차원:

```
표현력 (Level 2): LLM 이 spec.formula 안에서 raw column 못 씀
                   → \"BIDP_RSQN5 / BIDP_RSQN1 > 3\" 같은 호가 패턴 표현 불가능
                   → whitelist 39 primitive 의 변형만 가능

Reasoning (Level 4): LLM 이 hypothesis 작성 시 magnitude 추측이 데이터에 anchored 안 됨
                      → static cheat sheet (Path A/C/D) 만 봄, dynamic query 불가능
                      → \"이 specific spec 의 결과가 어땠나?\" 못 물어봄
```

두 차원이 **직교** 라 결합 시 시너지 가능.

---

## 2. 가설 + 측정 metric

\"두 lever 결합 시 mid_gross 천장 4-5 → 6-8 bps 영역 진입.\"

| Metric | 현재 (v6) | 목표 (v7) |
|---|---:|---:|
| best mid_gross (regime-state) | ~4.5 | ≥ 5.5 |
| hypothesis-result divergence | ±100% | ≤ ±50% |
| 새 영역 spec 비율 (book_shape, ofi+time-gate 등) | ~5% | ≥ 30% |
| LLM tool call 횟수 / spec | 0 | 1-3 (Phase 1) |
| Raw column 사용 spec 수 | 0 | ≥ 5 (Phase 2) |

가설 틀리면: 천장이 microstructure mechanical 한계 → paradigm shift (multi-day, chain 2).

---

## 3. 동시 적용 + Ablation — 단계적 진행 폐기

**옛 디자인** (단계적): Phase 1 → 효과 측정 → Phase 2 결정. **폐기 사유**:

1. **시간 차이 거의 없음**: 단계적 (1주 + 의사결정 idle 3-4일 + 1주 = ~2.3주) vs 동시 (~2주)
2. **효과 분리는 ablation 으로 가능**: v7a (baseline) / v7b (Level 4 만) / v7c (Level 4 + Level 2) 한 번 ablation 으로 분리 측정
3. **두 lever 가 직교** — 동시 진행해도 코드 충돌 없음, 같은 파일 (`data_tools.py`) 의 자연스러운 통합

**새 디자인** (동시):

```
                                   [Part A + Part B 동시]
                                  ╱
                                 ╱
[현재 v6] ────────────────────→ Level 4 + Level 2 결합
                                 │
                                 ↓
                          v7 fresh run (ablation v7a/b/c)
                                 │
                                 ↓
                          시너지 측정 (Δ 분리)
```

**Part A** = Level 4 (tool-use multi-turn, ~1주 작업 분량)
**Part B** = Level 2 (raw column read, ~3-4일 작업 분량)

**작업 흐름**: Part A + Part B 가 같은 ~2주 동안 병행 진행. 각 \"Day\" 에 두 part 의 작업 섞임 가능.

> 이전 \"Phase 1 / Phase 2\" 라는 표현 → 이 plan 안에서는 **\"Part A\" / \"Part B\"** (동시 진행) 로 변경.

---

## 4. Architecture (한눈에)

```
┌─────────────────────────────────────────────────────────────────┐
│  signal-generator (LLM, multi-turn loop)                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  cheat sheet (REQUIRED 7 files) + prior feedback     │     │
│  └───────────────────────────────────────────────────────┘     │
│            │                                                    │
│            ↓ thinking → tool call → thinking → submit          │
│                          │                                      │
│                          ▼                                      │
│           ┌──────────────────────────────┐                     │
│           │  consult_data_analyst tool   │                     │
│           │  (단일 entry point)          │                     │
│           └──────────────────────────────┘                     │
│                          │                                      │
│                          ▼                                      │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  data-analyst (별도 LLM call, 다른 system prompt)    │     │
│  │                                                       │     │
│  │  ┌─────────┬─────────┬─────────┬─────────┬─────┐    │     │
│  │  ▼         ▼         ▼         ▼         ▼     │    │     │
│  │  query_   query_    query_   query_   query_   │    │     │
│  │  distri   regime    tscale   paper    raw_col  │    │     │
│  │  bution   (live)    (lookup) (grep)   (P2 ★)   │    │     │
│  │  (lookup)                                       │    │     │
│  └───────────────────────────────────────────────────────┘     │
│            ↓ answer string                                      │
│                                                                 │
│  signal-generator 가 답 받고 → spec 작성 (formula = primitive   │
│      OR raw column [Phase 2 만], 사칙 + 비교 + AND/OR)         │
│            ↓                                                    │
│       ② signal-evaluator (single-shot, 그대로)                  │
│       ②.5 code-generator (raw column transpile [P2])           │
│       ②.75 fidelity-checker + AST validator [P2 ★]             │
│       ③ backtest-runner (그대로)                                │
│       ④ feedback-analyst (그대로)                               │
│       ⑤ signal-improver (그대로)                                │
└─────────────────────────────────────────────────────────────────┘
```

★ = Phase 2 에서 추가.

---

## 5. Part A — Tool-use multi-turn (Level 4, ~1주 분량)

### 5.1 새 파일 4개

| 파일 | 줄수 | 핵심 |
|---|---:|---|
| `chain1/tool_use_loop.py` | ~150 | LiteLLM acompletion + `submit_final` 메타-tool |
| `chain1/data_tools.py` | ~250 | 4 query tools (Phase 1) |
| `chain1/agents/data_analyst.py` | ~80 | sub-agent (LLM call wrapper) |
| `.claude/agents/chain1/data-analyst/AGENTS.md` | ~150 | sub-agent system prompt + reasoning flow |

### 5.2 변경 파일 2개

| 파일 | 변경 | 줄수 |
|---|---|---:|
| `chain1/agents/signal_generator.py` | multi-turn 통합 (consult_data_analyst tool) | +50 |
| `chain1/orchestrator.py` | `--agentic-mode` flag + global `_AGENTIC_MODE` | +10 |

### 5.3 핵심 코드 — `tool_use_loop.py`

```python
async def tool_use_loop(*, model, system_prompt, user_prompt, tools,
                         final_response_schema, max_iterations=8, max_tool_calls=12):
    \"\"\"Multi-turn LLM with tool-use until 'submit_final' is called.\"\"\"
    submit_tool = ToolDefinition(
        name=\"submit_final\",
        description=\"Call when ready with final answer.\",
        parameters=final_response_schema,
        fn=lambda args: args,  # identity
    )
    all_tools = tools + [submit_tool]
    messages = [
        {\"role\": \"system\", \"content\": system_prompt},
        {\"role\": \"user\", \"content\": user_prompt},
    ]
    n_tool_calls = 0
    for iteration in range(max_iterations):
        resp = await litellm.acompletion(
            model=model, messages=messages,
            tools=[t.to_openai_spec() for t in all_tools],
            temperature=0.0, max_tokens=4096,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            raise RuntimeError(\"LLM ended without submit_final\")
        for tc in msg.tool_calls:
            n_tool_calls += 1
            if n_tool_calls > max_tool_calls:
                raise RuntimeError(f\"max_tool_calls={max_tool_calls} exceeded\")
            if tc.function.name == \"submit_final\":
                return json.loads(tc.function.arguments)
            # ... execute other tool, append result to messages ...
    raise RuntimeError(\"max_iterations reached\")
```

핵심 디자인:
- **`submit_final` 메타-tool** = 명시적 loop 종료 신호 (무한 loop 방지)
- **`max_tool_calls=12` hard cap** = cost 폭발 방지 (LLM 이 같은 question 반복 시)
- **`temperature=0`** = 결정적 결과 (sequential 과 비교 가능)
- **Provider 무관** (LiteLLM 의 OpenAI-compatible schema, Anthropic/OpenAI/Gemini)

### 5.4 4 query tools (Phase 1)

| Tool | 입력 | 출력 | Backend |
|---|---|---|---|
| `query_distribution` | feature, time/vol partition | mean/median/p90/n | Path C lookup (`empirical_baselines.json`) |
| `query_regime` | formula, long_if, sample size | duty_cycle, mean_dur, expectancy | Live mini-backtest (1 sym × 1 day) |
| `query_t_scaling` | primitive, threshold | T 별 alpha vs drift, WR | Path D lookup (`t_scaling.json`) |
| `query_paper` | topic | papers + passage | Grep `_shared/references/papers/` |

### 5.5 통합 milestone — Part A + B 병행 (~2주)

Part A (Level 4) 와 Part B (Level 2) 가 같은 기간 안에 병행. 다른 색깔로 표시:

| Day | Part A (Level 4) | Part B (Level 2) |
|---|---|---|
| 1 | `tool_use_loop.py` + 단위 테스트 | — |
| 2 | 4 query tools (3 lookup + 1 live) | `spec_parser.py` AST validator (10+ corner case 테스트) |
| 3 | `data_analyst.py` + AGENTS.md | `safe_eval_raw_expr` 구현 (data_tools.py 의 5번째 tool 의 backend) |
| 4 | smoke: data_analyst 단독 호출 | 5번째 tool (`query_raw_column`) 통합 |
| 5 | signal-generator multi-turn 통합 | `code_generator.py` 의 transpile (BIDP_RSQN5 → snap.bid_qty[4]) |
| 6 | orchestrator `--agentic-mode` flag | orchestrator `--allow-raw-columns` flag + `fidelity_checker` AST 통합 |
| 7 | smoke 1 iter (Part A only) | smoke 1 iter (Part B only) |
| 8-10 | 통합 smoke (Part A + B) | (병행) |
| 11-12 | Ablation v7a/b/c smoke (각 1 iter) — 시너지 사전 측정 |
| 13-14 | 본격 v7 ablation 3-way (각 25 iter, 병렬화 with #109) → 12h compute |

---

## 6. Part B — Raw column read (Level 2, ~3-4일 분량)

Part A 와 병행 진행 (단계적 진행 폐기 — §3 참조).

### 6.1 새 파일 1개 + 변경 파일 4개

| 파일 | 변경 | 줄수 |
|---|---|---:|
| `chain1/spec_parser.py` (신규) | AST validator (raw column + 사칙, lookahead 방지) | ~200 |
| `chain1/data_tools.py` | 5번째 tool 추가 (`query_raw_column`) | +50 |
| `chain1/code_generator.py` | raw column transpile (BIDP_RSQN5 → snap.bid_qty[4]) | +50 |
| `chain1/fidelity_checker.py` | AST validator 통합 (whitelist + raw column 사칙만) | +20 |
| `chain1/orchestrator.py` | `--allow-raw-columns` flag | +5 |

### 6.2 핵심 — AST validator 의 정책

**허용**:
- Whitelist primitive callable (`obi_1`, `microprice_dev_bps`, ...) ← 그대로
- Stateful helper callable (`rolling_mean`, `zscore`, ...) ← 그대로
- **Raw column read** (`BIDP1`, `ASKP_RSQN5`, ...) ← 신규
- **Helper nesting** (`rolling_mean(zscore(trade_imbalance_signed, 300), 50)`) ← 신규 (현재 evaluator 가 reject — Phase 2 에서 풀어야)
- 산술: `+ - * / // %`
- 비교: `> < >= <= == !=`
- Boolean: `and or not`
- 함수: `abs(), min(), max(), sqrt()`
- 숫자 literal, `True/False/None`

**거부**:
- For/While/FunctionDef/ClassDef/Lambda
- Import/ImportFrom
- ListComp/DictComp
- **Subscript on raw column** (`BIDP1[t+1]` 류 — lookahead 방지)
- 알 수 없는 함수/변수 이름
- Conditional expression (`x if y else z` — 단순화 위해 reject, 필요시 추후 완화)
- f-string

**Phase 2 의 \"제약 완화\" 한 가지**: 현재 v6 의 evaluator 가 \"rolling_mean() 의 first arg must be primitive name\" 으로 nested helper reject. iter_007 crash 한 원인. AST validator 가 이걸 허용 (기존 evaluator 의 이 제약 풀어야).

### 6.3 4-day milestone

| Day | 작업 |
|---|---|
| 1 | `spec_parser.py` + 단위 테스트 (10+ corner case) |
| 2 | `data_tools.py` 의 5번째 tool (raw_column) + safe_eval_raw_expr |
| 3 | `code_generator.py` 의 raw column transpile + smoke test |
| 4 | fidelity_checker AST 통합 + ablation v7a/b/c smoke |

### 6.4 Code generator 의 raw column transpile

```python
def transpile_raw_column(name: str) -> str:
    if name.startswith(\"BIDP_RSQN\"):
        k = int(name.replace(\"BIDP_RSQN\", \"\")) - 1
        return f\"snap.bid_qty[{k}]\"
    if name.startswith(\"ASKP_RSQN\"):
        k = int(name.replace(\"ASKP_RSQN\", \"\")) - 1
        return f\"snap.ask_qty[{k}]\"
    if name.startswith(\"BIDP\"):
        k = int(name.replace(\"BIDP\", \"\")) - 1
        return f\"snap.bid_px[{k}]\"
    if name.startswith(\"ASKP\"):
        k = int(name.replace(\"ASKP\", \"\")) - 1
        return f\"snap.ask_px[{k}]\"
    if name in {\"TOTAL_BID_RSQN\"}: return \"snap.total_bid_qty\"
    if name in {\"TOTAL_ASK_RSQN\"}: return \"snap.total_ask_qty\"
    if name == \"ACML_VOL\": return \"snap.acml_vol\"
    # ... trade_volume, askbid_type, transaction_power, last_trade_price ...
```

Snap attribute 이름 검증됨 (engine/data_loader.py 의 `Snap` dataclass).

---

## 7. CLI flag + 사용 예시

```bash
# v7a (baseline = 옛 v6, 비교용)
python -m chain1.orchestrator run \\
  --max-iter 25 --n-candidates 4 \\
  --execution-mode maker_optimistic --fee-bps-rt 23.0 \\
  --parallel \\                              # G (#109)
  --symbols 005930 000660 005380 \\
  --dates 20260316 ... 20260325

# v7b (Phase 1 only — Level 4)
python -m chain1.orchestrator run ... --agentic-mode

# v7c (Phase 1 + 2 — Level 4 + Level 2)
python -m chain1.orchestrator run ... --agentic-mode --allow-raw-columns \\
  --max-tool-calls-per-spec 3
```

→ 같은 setup, lever 만 다르므로 **clean ablation**.

---

## 8. Risk mitigation

### 8.1 Lookahead 방지

```python
# spec_parser.py 에서 raw column 의 subscript 자동 reject
def visit_Subscript(self, node):
    if isinstance(node.value, ast.Name) and node.value.id in ALLOWED_RAW_COLUMNS:
        self.errors.append(\"subscript on raw column = lookahead\")
```

### 8.2 Data snooping 방지

```python
data_context = {
    \"is_dates\": IS_DATES,  # 8 dates only
    \"oos_dates\": None,     # ← tool 이 access 불가능
    ...
}
# Final 평가는 별도 OOS dates (orchestrator 에서)
```

### 8.3 Cost 폭발 방지

```python
max_tool_calls_per_spec = 3  # CLI flag

class QueryCache:
    \"\"\"같은 query 반복 호출 시 cache hit\"\"\"
    def get_or_compute(self, key, fn): ...
```

### 8.4 LLM hallucination 방지

```python
DATA_ANALYST_SYSTEM = \"\"\"...
Cite tool result for every numerical claim. 
If can't find data, say so — don't fabricate.\"\"\"

def verify_grounded(answer, tool_results) -> bool:
    \"\"\"answer 가 tool 결과의 수치 인용하는지 정규식 체크\"\"\"
```

---

## 9. Ablation 디자인 — 시너지 측정

```
v7a (baseline)    : 옛 v6 + 병렬화만 (#109)
v7b (Phase 1)     : v7a + agentic-mode
v7c (Phase 1+2)   : v7b + allow-raw-columns

각 25 iter, 같은 setup. 측정:
  - best mid_gross / maker_gross
  - hypothesis-result divergence
  - LLM tool call 빈도, raw column 사용 빈도
  - 새 영역 spec 비율 (book_shape, ofi+time-gate)
  
시너지 검증:
  Δ(v7c - v7a) > Δ(v7b - v7a) + Δ(v7c - v7b) 면 진짜 시너지
```

병렬화 (#109) 적용 후 한 run 4시간 → ablation 12시간에 완료.

---

## 10. 작업 시간 + 비용

| Phase | 시간 | LLM cost / run |
|---|---|---:|
| Phase 1 (Level 4) | ~1주 (35h) | 5x baseline |
| Phase 2 (Level 2 추가) | ~3-4일 (28h) | 같은 5x |
| **F 전체** | **~2주 (63h)** | **5x** |

병렬화 적용 후 시간:
- v6 한 run = 14h (sequential) → 4h (parallel)
- v7 ablation 3개 = 12h (parallel) ✓

---

## 11. Trigger 조건 (v6 결과별)

```
v6 종료 (~21:30 KST)
  │
  ├─[A] net > 0 spec 발견 (확률 25%)
  │     → F 보류, paper writeup 우선 (OOS 검증 + DSR + paper §Results)
  │
  └─[B/C] net ≤ 0 (확률 75%, margin 또는 천장)
        → F (Part A + B 동시) 진행, ~2주
        → v7 ablation 3-way (v7a/b/c) 로 시너지 측정
        → 시너지 효과 따라 paper §Method 핵심 이거나 paradigm shift 다음 단계
```

→ v6 결과 net ≤ 0 이면 **margin / 천장 무관 둘 다 동시 진행**. 단계적 의사결정 idle 없음.

---

## 12. 점검 체크리스트 (구현 시작 전)

다음 사항 사전 검증:

- [ ] **LiteLLM acompletion + tools 가 sonnet 에서 정상 작동** — 작은 sanity test (10분)
- [ ] **iter_007 crash 의 원인** — `rolling_mean(zscore(...), 50)` 이 evaluator 에서 reject 되는 이유 식별 + AST validator 에서 풀어야 할 곳 명시
- [ ] **Snap attribute mapping** — engine/data_loader.py 의 `Snap` dataclass 의 attribute 이름과 raw column 매핑 검증
- [ ] **AST validator corner case** — ternary, f-string, list comprehension 등 reject 정책
- [ ] **Cost monitoring** — per-run token usage 추적 (orchestrator 에 telemetry 추가)
- [ ] **OOS protocol** — Phase 1+2 의 final spec 을 별도 OOS dates 에서 검증 (data snooping 방지)

---

## 13. 신규 / 변경 파일 summary

```
신규 (Phase 1 — 4 파일):
  chain1/tool_use_loop.py            ~150 lines
  chain1/data_tools.py               ~250 lines (4 tools)
  chain1/agents/data_analyst.py      ~80 lines
  .claude/agents/chain1/data-analyst/AGENTS.md  ~150 lines

신규 (Phase 2 — 1 파일):
  chain1/spec_parser.py              ~200 lines
  analysis/v7_ablation.py            ~100 lines

변경 (Phase 1 — 2 파일):
  chain1/agents/signal_generator.py  +50 lines (multi-turn)
  chain1/orchestrator.py             +10 lines (--agentic-mode flag)

변경 (Phase 2 — 4 파일):
  chain1/data_tools.py               +50 lines (5번째 tool)
  chain1/code_generator.py           +50 lines (raw column transpile)
  chain1/fidelity_checker.py         +20 lines (AST validator 통합)
  chain1/orchestrator.py             +5 lines (--allow-raw-columns flag)

총 ~1100 lines 신규/변경
```

---

## 14. 관련 plan / concept

- [path-e-agentic-data-tools.md](path-e-agentic-data-tools.md) — superseded
- [post-v5-roadmap.md](post-v5-roadmap.md) — master sequencing
- [fixed-h-overcounting-bias](../concepts/fixed-h-overcounting-bias.md) — v3 의 13 bps 가 인공물인 이유
- 신호 framework: `magnitude-axes-framework`, `regime-state-paradigm`
- Failure modes: `reward-target-mismatch`, `cite-but-fail`
- 비교: `paradigm-twin` (alphaagent / quantagent / tradefm)

---

## 15. 의문점 / 결정 미정

- [ ] LLM `temperature=0` 가 충분한가? `temperature=0.1~0.3` 이 더 다양한 spec 만들 가능?
- [ ] Phase 1 의 `max_tool_calls_per_spec=3` 이 적정? 처음에는 5 로 시작 → 줄이기?
- [ ] data_analyst 의 model = sonnet 그대로 vs haiku (cheaper)?
- [ ] 5번째 tool (query_raw_column) 의 cache strategy — file 기반 vs in-memory?
- [ ] Phase 2 의 \"helper nesting 허용\" 시 evaluator 의 기존 reject logic 어떻게 풀지

위 의문점은 v6 결과 + Phase 1 smoke test 보고 결정.
