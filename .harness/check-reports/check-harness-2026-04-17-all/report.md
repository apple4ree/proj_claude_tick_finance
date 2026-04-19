# 🧭 Harness Maturity Report

**2026-04-17** · Scope: `all` · Project: `proj_claude_tick_finance`

---

## 🧭 Harness Score: **37 / 100** (Needs Work)

```
👤 User Scope    L0  ░░░░░░░░░░   0% → L1   (Score: 33)
📁 Project Scope L0  ▓▓░░░░░░░░  29% → L1   (Score: 29)
🔁 Compounding   L1  ░░░░░░░░░░   0% → L2   (Score: 50)
```

> User = `~/.claude/` 전역 · Project = 현재 프로젝트 · Compounding = 하네스가 자라고 있는지 (축 6, 공통)

## 🎯 한 줄 요약

> 전략 생성 파이프라인(alpha→exec→spec→critic→feedback)은 artifact로 잘 축적되고 있지만(CLAUDE.md 30일 5회·lessons 46개), 하네스의 기본기 — 민감 파일 보호·포맷 훅·dead skill 정리 — 가 비어 있어요. `.gitignore`에 네 줄 추가부터 시작하면 가장 빨리 한 단계 올라갑니다.

**잘 되고 있는 것**: User 세션의 delegation_ratio 1.0 + Agent 파이프라인이 실제로 매일 굴러감 + knowledge/lessons 46파일 90일 축적.
**개선하면 좋을 것**: `.gitignore`에 `.env`/secrets 엔트리가 전무, PostToolUse/PreToolUse 훅 부재, 전역 skill 1,007개 중 982개가 dead라 트리거 노이즈.

---

## 🔄 사이클 한눈에 보기

1. **구조** · 👤 User — ❌ 설치 1,007개 중 최근 30일 사용 25개(2.5%), dead 982, trigger collision 38, duplicate cluster 41.
2. **맥락** · 📁 Project — ⚠️ CLAUDE.md는 충실(190줄·목적/구조/명령어 포함)하나 `.gitignore`가 `strategies` 한 줄뿐, `.claude/rules/` 디렉토리 부재.
3. **계획** · 👤 User — ❌ plan_first_ratio 0.0 — specify/scaffold 스킬 한 번도 사용 안 됨 (최근 7일).
4. **실행** · 👤+📁 — ⚠️ User 100 / Project 25. 프로젝트는 Bash→Bash→Bash 3-gram이 56% (쉘 연쇄 고착).
5. **검증** · 📁 Project — ❌ completion_check 0.158, PostToolUse·PreToolUse 훅 둘 다 없음, `defaultMode: bypassPermissions`.
6. **개선** · 👤+📁 — ✅ CLAUDE.md 30일 5회 갱신, lessons 46건 축적, agents 12건 변경. 단 long-session handoff 0/5.

---

## ✅ 지금 하면 좋은 것 (제안)

### 🟢 바로 해볼 만한 것

- [ ] 📁 **`.gitignore`에 민감 파일 엔트리 추가** — 예상 효과: `.env`/`*.pem`/`secrets/`가 우발적으로 커밋되지 않게, C3 L1 복구.
  - 제안 명령: `printf '\n.env\n*.pem\nsecrets/\ncredentials*\n' >> .gitignore`
  - 근거: 현재 `.gitignore`는 `strategies` 한 줄만 존재.

- [ ] 👤 **30일 미사용 user plugin 비활성화** — 예상 효과: trigger 매칭 노이즈 감소, 엉뚱한 스킬 발동 확률↓.
  - 제안: `/update-config`로 `~/.claude/settings.json`의 `enabledPlugins`에서 `prompt-engineering`, `ml-paper-writing`, `autoresearch` 제거 (bulk_plugin_enabled_user 4건 중 3개).
  - 근거: PORTFOLIO의 low_value / bulk_plugin_enabled_user 플래그.

- [ ] 👤 **다음 큰 작업 시작 시 `/specify` 또는 `/scaffold` 한 번** — 예상 효과: plan_first_ratio 0 → 첫 카운트 기록, B2 진행률 움직임.
  - 근거: 최근 5세션 중 plan/specify/scaffold 0회.

### 🟡 한 번 정리하면 좋을 것

- [ ] 📁 **PostToolUse 포맷 훅 추가** — 예상 효과: Edit/Write 후 자동 포맷, 포맷 지시 반복 비용 제거 (D2).
  - 참고: `.claude/settings.json` — `hooks.PostToolUse` 블록에 `ruff format` 또는 `black` 등록.

- [ ] 👤 **ai-research-skills 10개 플러그인 중 1–2개만 유지** — 예상 효과: duplicate_clusters 41→~5, trigger_collisions 38→0.
  - 근거: 같은 SKILL.md 세트가 `autoresearch / ideation / rag / mlops / evaluation / data-processing / emerging-techniques / observability / prompt-engineering / ml-paper-writing` 10개 플러그인에 중복 노출됨.

- [ ] 📁 **session-wrap 스킬 또는 세션 종료시 MEMORY.md 갱신 워크플로우** — 예상 효과: handoff_ratio 0 → >0, 다음 세션 재설명 제거 (B4/E2).
  - 참고: 이미 `/home/dgu/.claude/projects/-home-dgu-tick-proj-claude-tick-finance/memory/MEMORY.md` 인프라는 있음 — 호출만 습관화하면 됨.

### 🔴 시간 내서 다뤄볼 것

- [ ] 📁 **CLAUDE.md → `.claude/rules/{architecture,agents,data-universe,workflow}.md` 분리 + progressive disclosure** — 예상 효과: 관련 맥락만 선택적 로드, 컨텍스트 효율↑, C4/C6 복구.
  - 근거: `.claude/rules/` 미존재, 190줄 모놀리식, 조건부 로드 증거 0.

- [ ] 📁 **PreToolUse 위험 작업 차단 훅** — 예상 효과: `rm -rf`, `git push --force`, `.env` write 사전 차단 (D3). 현재 `permissions.deny`는 정적이고 `defaultMode=bypassPermissions`로 약화됨.

---

## 📊 축별 스코어카드 (6축)

| Axis | Scope | Score | Level | 다음 레벨까지 |
|------|-------|------:|:-----:|:-------------|
| 1. 구조 (Scaffolding)      | 👤 User     |  0 | L0 |   0% → L1 |
| 2. 맥락 (Context)          | 📁 Project  | 32 | L0 |  29% → L1 |
| 3. 계획 (Planning)         | 👤 User     |  0 | L1* |   0% → L2 |
| 4. 실행 (Execution)        | 👤+📁        | 25 | L1* | min=Project fail |
| 5. 검증 (Verification)     | 📁 Project  | 30 | L0 |  10% → L1 |
| 6. 개선 (Compounding)      | 👤+📁        | 50 | L1 |   0% → L2 |

Sessions analyzed: User 5 (7일) / Project 307 (30일) · Scanned: 2026-04-17

(*) L1 vacuous — 해당 축에 L1 항목이 없음.

---

## 🔌 현재 활성 상태 (Runtime Inventory)

**📦 플러그인** (3/15 enabled in this project)

| Plugin | Scope | Skills | 최근 30일 활용 |
|--------|:-----:|------:|:--------------|
| ouroboros | 📁+👤 | ~20 | `ouroboros:interview` 1회 |
| superpowers | 📁+👤 | ~15 | 0회 (스킬 직접 invoke 없음) |
| data-processing | 📁 | 95 | 0회 (enabled_unused_30d) |
| ideation | 👤 | 95 | 저활용 |
| prompt-engineering | 👤 | 95 | 0회 (bulk_plugin) |
| ml-paper-writing | 👤 | 95 | 0회 (bulk_plugin) |
| autoresearch | 👤 | 95 | 0회 (bulk_plugin) |

**🔗 MCP 서버** (1 총 · 1 미사용)

| Server | Scope | 최근 호출 30일 |
|--------|:-----:|:--------:|
| ouroboros | 👤 | 0회 |

**🧩 스킬 출처**

- user standalone: 1개
- 플러그인 경유: 993개
- 프로젝트 로컬: 13개 (agent-orchestrate, check-harness, deep-interview, doc-drift, graph-query, new-strategy, qa, run-backtest, scaffold, search-lessons, specify, validate-spec, write-lesson)

---

## 🧭 2×3 분석 매트릭스

|  | Static (갖춘 것) | Behavioral (하는 것) | Growth (축적) |
|---|---|---|---|
| 👤 User    | 축 1 — Score 0 (1007개 설치 / 25개만 사용) | 축 3 — 0 · 축 4-User — 100 | 축 6-User — 50 |
| 📁 Project | 축 2 — 32 (CLAUDE.md 충실, 민감 파일 노출) | 축 4-Project — 25 · 축 5 — 30 | 축 6-Project — 50 |

**교차에서 나온 gap 요약**

- **Static vs Behavioral (User)**: 1,007개 설치했지만 최근 7일에 스킬 호출은 6회(`new-strategy`×2, `update-config`×2, `ouroboros:interview`×1, `co-review`×1)뿐. 포트폴리오-실사용 gap 98%.
- **Static vs Behavioral (Project)**: 13개 프로젝트 스킬 등록 / 실제 호출은 `new-strategy`×2만 확인. `specify`/`scaffold`/`qa`/`doc-drift` 등은 미사용.
- **Growth**: CLAUDE.md 5 commits + lessons 46건 + agents 12건 = 축적은 활발. 다만 rules·hooks 축적은 0건 — "알고리즘 문서화는 잘 되지만 자동화로 굳히지는 않는다"는 신호.

---

## 📋 상세 체크리스트

### 축 1 — 구조 (👤 User × Static)

| ID | L | Item | Status | Evidence |
|----|---|------|--------|----------|
| A1 | L1 | 70%+ skills used last 30d | FAIL | used_last_30d=25 / total=1007 (2.5%) |
| A2 | L2 | Dead count == 0 | FAIL | dead_count=982 |
| A3 | L2 | Ghost count == 0 | FAIL | ghost_count=8 (update-config, co-implement, iterate, statusline, ouroboros:openclaw, superpowers:brainstorm/write-plan/execute-plan) |
| A4 | L2 | Duplicate clusters == 0 | FAIL | 41 clusters (주로 ai-research-skills 마켓 중복) |
| A5 | L3 | Prefix dup + trigger collisions == 0 | FAIL | prefix=1 (creative-thinking-for-research), collisions=38 |

### 축 2 — 맥락 (📁 Project × Static)

| ID | L | Item | Status | Evidence |
|----|---|------|--------|----------|
| C1 | L1 | CLAUDE.md 존재 & 목적/구조 설명 | PASS | 190줄, has_project_purpose + has_structure + has_dev_commands 모두 true |
| C2 | L1 | 품질 — 모순/ambiguity/placeholder 없음 | WEAK_PASS | contradictions=0, placeholders=0, ambiguities=2 ("대규모 refactor" 기준, "한국어 위주" 비율) |
| C3 | L1 | 민감 파일 보호 | FAIL | `.gitignore`는 `strategies` 한 줄뿐, `.env`/`*.pem`/secrets 엔트리 없음. PreToolUse 훅 없음. |
| C4 | L2 | Rules 분리 ≥2 파일 | FAIL | `.claude/rules/` 디렉토리 미존재, 규칙이 CLAUDE.md Rules 섹션에 인라인 |
| C5 | L2 | MCP 서버 설정 | FAIL | `.mcp.json` 없음, settings.json에 mcpServers 블록 없음 (플러그인과는 별개) |
| C6 | L3 | Progressive disclosure | FAIL | @import / additionalDirectories / 조건부 로드 증거 0 |

### 축 3 — 계획 (👤 User × Behavioral)

| ID | L | Item | Status | Evidence |
|----|---|------|--------|----------|
| B2 | L2 | plan_first_ratio ≥ 0.3 | FAIL | 0.0 (최근 7일 specify/scaffold/plan 호출 0회) |

### 축 4 — 실행 (👤+📁 × Behavioral)

| ID | L | Item | 👤 User | 📁 Project | 판정(min) | Evidence |
|----|---|------|-----|--------|----------|----------|
| B3 | L2 | delegation_ratio ≥ 0.4 | 1.0 PASS | 0.016 FAIL | FAIL | 프로젝트 307 세션 중 Agent 사용 세션 극소 (단 Agent 총 306 호출은 소수 파이프라인 세션에 집중) |
| B5 | L3 | parallel_count ≥ 1 | 9 PASS | 6 PASS | PASS | run_in_background 사용 있음 |
| B6 | L3 | top_3gram_share < 0.3 | 0.28 PASS | 0.56 FAIL | FAIL | Project에서 Bash→Bash→Bash 2,538회 = 56% |

### 축 5 — 검증 (📁 Project)

| ID | L | Item | Status | Evidence |
|----|---|------|--------|----------|
| B1 | L1 | completion_check_ratio ≥ 0.5 | FAIL | 0.158 (project) |
| D1 | L1 | Test runner configured | WEAK_PASS | pytest tests 3개 + .pytest_cache는 있으나 pytest.ini/pyproject.toml/conftest/Makefile 등 명시적 러너 설정 없음 |
| D2 | L1 | PostToolUse format hook | FAIL | `.claude/settings.json`에 hooks 블록 없음 |
| D3 | L1 | PreToolUse block hook | FAIL | PreToolUse hook 없음. `permissions.deny`는 정적 + `defaultMode=bypassPermissions`로 약화 |
| D4 | L2 | project_skills_used ≥ 1 | PASS | SESSION_PROJECT.skills_invoked에 new-strategy×2 기록 |
| D5 | L3 | Verifier agent exists | PASS | alpha-critic, execution-critic, meta-reviewer, context-quality-reviewer, project-automation-auditor, session-pattern-analyzer, skill-portfolio-analyzer + scripts/audit_principles.py |

### 축 6 — 개선 (👤+📁 × Growth)

| ID | L | Item | Status | Evidence |
|----|---|------|--------|----------|
| E1 | L1 | CLAUDE.md/rules/docs 30일 갱신 | PASS | CLAUDE.md 30일 5 commits + lessons 46건 90일 |
| B4 | L2 | Handoff ratio ≥ 0.5 | FAIL | 0/5 (project long sessions), 0/3 (user long sessions) |
| E2 | L2 | wrap/compound/memory 호출 ≥1 | FAIL | skills_invoked에 session-wrap/compound/memory-write 계열 없음 |
| E3 | L3 | 최근 90일 skill/hook/rule 추가 | PASS | skills_modified_90d=6, agents_touched_90d=12 |

---

## ⚡ Execution 상세 (최근 세션 습관)

|                          | 👤 User (7d) | 📁 Project (30d) |
|--------------------------|-------:|-----------:|
| plan_first_ratio         | 0.0    | 0.0        |
| delegation_ratio         | 1.0    | 0.016      |
| parallel_count           | 9      | 6          |
| handoff_ratio            | 0.0    | 0.0        |
| completion_check_ratio   | 0.40   | 0.158      |
| top 3-gram share         | 0.28   | 0.56       |

**자동화 후보 (반복 패턴)**

- Project: `Bash→Bash→Bash` ×2,538회 — `date` 903회, `python3 -c` 226, `grep -n` 159, `python scripts/search_knowledge.py` 280 → knowledge-query 스킬로 묶을 만함.
- Project: `python scripts/audit_principles.py` 79회 — engine 수정 후 필수 단계 → PostToolUse hook 후보.
- User: `Edit→Edit→Edit` ×109 — bulk edit skill 후보.
- User: `Agent→Agent→Agent` ×83 / `Agent→Agent→Bash` ×51 — alpha→exec→spec→backtest 파이프라인은 이미 CLAUDE.md에 정의됨 → formal skill로 굳히면 재현성↑.

---

## 🔁 Compounding 상세 (축 6)

- CLAUDE.md 최근 30일 갱신: **Yes** (5 commits — 3-axis trajectory, co-review rule, data-driven pipeline, counterfactual PnL)
- `.claude/rules/` 최근 90일 추가: **0개** (디렉토리 미존재)
- `skills/` 최근 90일 변경: **6개** (graph-query, new-strategy, run-backtest, search-lessons, validate-spec, write-lesson)
- `agents/` 최근 90일 변경: **12개** (portfolio-designer, meta-reviewer, feedback-analyst 등)
- `knowledge/lessons/` 최근 90일 변경: **46개** ← 매우 강한 축적 신호
- `hooks/` 최근 90일 변경: **0건** (디렉토리 미존재)
- 세션에서 session-wrap/compound/memory-write 호출: **0회**

**관찰**: 학습이 "지식 파일"과 "에이전트 프롬프트"로는 축적되는데, "자동화 artifact(hook, rule)"로는 한 번도 굳지 않음. → 개선 축 L2 이상으로 가려면 학습의 한 비율을 hook/rule로 옮겨야 함.

---

📁 Saved: `.harness/check-reports/check-harness-2026-04-17-all/` · 🌐 Opened: `report.html`
