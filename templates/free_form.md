<!--
  ResearchWiki 템플릿: free_form
  ---
  이 파일은 연구자가 자유 형식 엔트리를 만들 때 `wiki-log`가 소비합니다. wiki-log는:

    1. 아래 YAML frontmatter를 파싱. `_` prefix 키 (예: `_template`) 는 템플릿 전용으로
       새 엔트리에는 복사되지 **않습니다**.
    2. 나머지 frontmatter를 새 엔트리에 복사하며, `{{중괄호}}` 플레이스홀더를 세션 값으로 치환.
    3. 마크다운 본문을 순회하며 각 `##` 헤더를 대화형 프롬프트로 변환. `[required]` 플래그가
       붙은 섹션은 비어있으면 엔트리를 쓰지 않습니다.

  free_form은 의도적으로 가장 가벼운 템플릿 — 다른 세 타입에 맞지 않는 내용을 위한 비상구입니다.
  free_form 엔트리를 같은 형태로 반복해 쓰고 있다면 새 템플릿 타입 추가를 고려하세요.

  wiki-log가 자동으로 채우는 플레이스홀더:
    {{DATE}}        생성 시점의 ISO 날짜 (YYYY-MM-DD)
    {{SESSION_ID}}  현재 LLM 세션 식별자
    {{TITLE}}       연구자가 입력한 사람이 읽기 좋은 제목
-->

---
# ===== Entry frontmatter (새 엔트리에 복사됨) =====

schema_version: 1
type: other
created: {{DATE}}
updated: {{DATE}}
tags: []

refs:
  code: []
  papers: []
  concepts: []
  experiments: []

authored_by: hybrid              # P3/P8: wiki-log는 `llm`을 금지. 구술만 한 경우 `human`.
source_sessions: [{{SESSION_ID}}]

# ===== 템플릿 전용 config (wiki-log가 소비; 엔트리에 복사 안 됨) =====

_template:
  # free_form 엔트리는 의도적으로 구조를 최소화. Auto-link은 기본 비활성 —
  # 비정형 본문에서의 false positive 방지. 링크가 실제로 필요하면 아래 "링크"
  # 섹션에 연구자가 직접 추가합니다.
  auto_link:
    code:
      enabled: false
    papers:
      enabled: false
    concepts:
      enabled: false
    experiments:
      enabled: false
---

# {{TITLE}}

## 노트  [required]

*원하는 무엇이든 기록하세요. 구조 강제 없음. 한 문단도, 열 문단도 좋습니다.
free_form에서 같은 형태의 내용을 반복해 쓰고 있다면 새 템플릿 타입 추가를
고려해보세요 — 반복되는 구조는 노이즈가 아니라 시그널입니다.*

## 링크  [optional]

*수동 refs. `- <kind>: <slug> — 맥락` 형태로 한 줄씩. `<kind>`는 `code`, `paper`,
`concept`, `experiment` 중 하나. wiki-log가 쓰는 시점에 이 섹션을 읽어 확인된
항목을 frontmatter의 `refs:`로 승격시킵니다.*

<!--
  예시 (실제 엔트리에서는 삭제):
  - paper: transformer-2017 — attention 비용을 고민하며 참고
  - concept: temperature — temperature gap 이슈 관련
-->
