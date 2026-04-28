<!--
  ResearchWiki 템플릿: design_decision
  ---
  이 파일은 연구자가 결정 엔트리를 만들 때 `wiki-log`가 소비합니다. wiki-log는:

    1. 아래 YAML frontmatter를 파싱. `_` prefix 키 (예: `_template`) 는 템플릿 전용으로
       새 엔트리에는 복사되지 **않습니다**.
    2. 나머지 frontmatter를 새 엔트리에 복사하며, `{{중괄호}}` 플레이스홀더를 세션 값으로 치환.
    3. 마크다운 본문을 순회하며 각 `##` 헤더를 대화형 프롬프트로 변환. `[required]` 플래그가
       붙은 섹션은 비어있으면 엔트리를 쓰지 않습니다.

  wiki-log가 자동으로 채우는 플레이스홀더:
    {{DATE}}         생성 시점의 ISO 날짜 (YYYY-MM-DD)
    {{SESSION_ID}}   현재 LLM 세션 식별자
    {{DECISION_ID}}  연구자가 지정한 짧은 slug; 파일명 어간으로도 사용
    {{TITLE}}        연구자가 입력한 사람이 읽기 좋은 제목

  템플릿 전역 수정이 필요한 경우가 아니라면 아래 블록을 직접 편집하지 마세요.
  특정 엔트리만 달리 처리하고 싶으면 생성된 엔트리 파일을 편집하면 됩니다.
-->

---
# ===== Entry frontmatter (새 엔트리에 복사됨) =====

schema_version: 1
type: decision
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

# 결정 수명주기 메타데이터 (상태이지 해석이 아님)
decision_id: {{DECISION_ID}}
status: proposed                 # proposed | accepted | superseded | rejected | deprecated
supersedes: []                   # 이 결정이 대체하는 과거 결정의 decision_id 목록
superseded_by: []                # 나중에 이 결정을 대체하는 후속 결정이 생기면 채워짐
scope: []                        # 영향받는 경로, 도메인, 컴포넌트

# ===== 템플릿 전용 config (wiki-log가 소비; 엔트리에 복사 안 됨) =====

_template:
  # 설계 결정은 대개 코드를 직접 건드리고, 개념을 참조하고, 실험 결과에 응답합니다.
  # 4개 링크 타입 모두 활성화. 코드 스캔이 가장 공격적 — 결정은 보통 특정 파일이나
  # 심볼을 수반하기 때문.
  auto_link:
    code:
      enabled: true
      strategy: identifier_token
      default_confidence: verified
    papers:
      enabled: true
      strategy: exact_slug
    concepts:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    experiments:
      enabled: true
      strategy: exact_id
      link_bidirectional: true
---

# {{TITLE}}

## 문제  [required]

*이 결정이 해결하는 문제는 무엇인가요? 해결책이 아닌 문제를 기술하세요. 한두 문장.*

## 검토한 옵션  [required]

*어떤 대안을 평가했나요? 최소 둘 이상. 각각: 한 줄 설명. 순위는 여기서 매기지 말고
"근거" 섹션에서.*

## 선택한 접근  [required]

*어느 옵션을 선택했나, 어떤 형태로? "검토한 옵션"의 이름으로 참조. 관찰 가능한 결정만
적고, 구현 세부는 연결된 코드로 미루세요.*

## 근거  [required]

*왜 이 옵션을 대안 대신 선택했나요? 각 근거를 증거에 연결 — 실험 결과, 논문, 알려진
제약. 증거가 아닌 판단 근거는 그렇다고 명시적으로 밝히세요 (P8).*

## 트레이드오프  [optional]

*선택한 접근이 치르는 비용은? 이 결정이 쉽게 만드는 것뿐 아니라 어렵게 만드는 것도
나열.*

## 영향 범위  [required]

*어떤 코드 경로, 모듈, 연구 방향이 영향받나요? 경로나 개념 slug로 참조 — wiki-log가
자동 링크합니다.*

## 재검토 조건  [optional]

*어떤 조건에서 이 결정을 재오픈해야 하나요? 구체적 트리거가 있으면 미래의 자신이 이
결정을 대체할 시점을 알아차리기 쉽습니다.*
