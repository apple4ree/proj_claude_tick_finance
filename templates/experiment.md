<!--
  ResearchWiki 템플릿: experiment
  ---
  이 파일은 연구자가 실험 엔트리를 만들 때 `wiki-log`가 소비합니다. wiki-log는:

    1. 아래 YAML frontmatter를 파싱. `_` prefix 키 (예: `_template`) 는 템플릿 전용으로
       새 엔트리에는 복사되지 **않습니다**.
    2. 나머지 frontmatter를 새 엔트리에 복사하며, `{{중괄호}}` 플레이스홀더를 세션 값으로 치환.
    3. 마크다운 본문을 순회하며 각 `##` 헤더를 대화형 프롬프트로 변환. `[required]` 플래그가
       붙은 섹션은 비어있으면 엔트리를 쓰지 않습니다.

  wiki-log가 자동으로 채우는 플레이스홀더:
    {{DATE}}        생성 시점의 ISO 날짜 (YYYY-MM-DD)
    {{SESSION_ID}}  현재 LLM 세션 식별자
    {{GIT_REF}}     현재 HEAD의 SHA 또는 브랜치. git 저장소가 아니면 null.
    {{TITLE}}       연구자가 입력한 사람이 읽기 좋은 제목

  템플릿 전역 수정이 필요한 경우가 아니라면 아래 블록을 직접 편집하지 마세요.
  특정 엔트리만 달리 처리하고 싶으면 생성된 엔트리 파일을 편집하면 됩니다.
-->

---
# ===== Entry frontmatter (새 엔트리에 복사됨) =====

schema_version: 1
type: experiment
created: {{DATE}}
updated: {{DATE}}
tags: []

# 교차 참조 — 연구자 승인 후 wiki-log의 auto-link pass가 채움
# (P7: 모든 엔트리는 provenance를 가짐; confidence는 refs.code의 각 항목에 기록)
refs:
  code: []
  papers: []
  concepts: []
  experiments: []

# Provenance
authored_by: hybrid            # P3/P8: wiki-log는 `llm`을 금지. 구술만 한 경우 `human`.
source_sessions: [{{SESSION_ID}}]

# 실험 고유의 측정 가능 메타데이터
# 객관적이고 측정 가능한 사실만 (P8). 해석은 본문에 둡니다.
git_ref: {{GIT_REF}}           # 실험을 돌린 SHA, 브랜치, 또는 태그
run_duration: null             # 예: "2h 14m"; 기록 안 했으면 null
seed: null                     # 단일 시드는 int, 다중 시드는 list

# ===== 템플릿 전용 config (wiki-log가 소비; 엔트리에 복사 안 됨) =====

_template:
  # Auto-link 스캔 규칙. ARCHITECTURE.md §3.4 와 wiki-log/SPEC.md §Auto-link rules 참조.
  # 실험 엔트리는 코드 및 과거 실험과의 링크가 가장 가치있음.
  # 논문은 실험 본문에 잘 등장하지 않으므로 끔 — 노이즈 감소 목적. 필요시 refs.papers에
  # 직접 추가하면 됨.
  auto_link:
    code:
      enabled: true
      strategy: identifier_token   # 코드 식별자 꼴의 토큰을 본문에서 스캔
      default_confidence: verified # index/signatures.json에 있으면 verified
    experiments:
      enabled: true
      strategy: exact_id           # `exp-YYYY-MM-DD-*` 패턴만 매치
      link_bidirectional: true     # 매치된 과거 실험의 frontmatter에도 역링크 기재
    concepts:
      enabled: true
      strategy: exact_slug         # `wiki/concepts/<slug>.md` 에 정확 매치
      link_bidirectional: true
    papers:
      enabled: false
---

# {{TITLE}}

<!--
  wiki-log로 이 템플릿을 채우는 연구자를 위한 안내:
  이 템플릿을 직접 타이핑하지 않습니다. wiki-log가 아래 섹션을 대화형으로 질문하고,
  자연어로 답하면 매칭되는 섹션에 구조화해 넣습니다.
-->

## 가설  [required]

*무엇을 테스트했나요? 가설은 틀릴 수 있었던 주장 — 목표가 아닙니다.
한두 문장으로.*

<!-- 예: "batch size 256이면 lr=3e-4를 써도 불안정하지 않을 것이다" -->

## 셋업  [required]

*이전 런과 무엇이 달랐나요? 하이퍼파라미터, 데이터셋 변경, 시드 수, 하드웨어.
과거 실험을 ID로 참조 (예: `exp-2026-04-22-bs128`) — wiki-log가 자동 링크합니다.
git ref는 이미 frontmatter에 기록되어 있으니 여기 반복할 필요 없음.*

## 결과  [required]

*숫자가 무엇을 보여줬나요? **직접 관찰만.** 원인 설명은 여기에 쓰지 마세요 —
근거 있는 해석은 "관찰"로, 근거 없는 추측은 `wiki/questions.md`로
(P8 — 추측 금지 원칙).*

<!-- 예: "3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN 발생." -->

## 관찰  [required]

*로그·플롯·메트릭에서 직접 짚을 수 있는 패턴. 데이터가 뒷받침하지 않는 원인 귀인이
들어가려 하면 생략하거나 `[speculation]` 태그 (P8).*

## 실패 양상  [optional]

*런 중 무엇이 잘못됐나. **무엇이 일어났는지** 쓰고 **왜** 는 쓰지 마세요.
로그 증거 없는 원인 귀인은 추측 — 태그하거나 `wiki/questions.md`로 옮기세요.*

## 관련 코드  [required]

*런에 관련된 함수·파일·모듈. 이름만 적으세요 — wiki-log가 이 섹션을 스캔해
`index/signatures.json`의 심볼과 매칭해 verified `refs.code` 후보로 띄웁니다.*

## 다음 단계  [optional]

*구체적인 후속 실험 또는 코드 변경. 짧게 — 후속 작업이 커지면 이 엔트리에 두지 말고
자기 자신의 로그 엔트리로 분리하세요.*
