<!--
  ResearchWiki 템플릿: paper_reading
  ---
  이 파일은 연구자가 논문 엔트리를 만들 때 `wiki-log`가 소비합니다. wiki-log는:

    1. 아래 YAML frontmatter를 파싱. `_` prefix 키 (예: `_template`) 는 템플릿 전용으로
       새 엔트리에는 복사되지 **않습니다**.
    2. 나머지 frontmatter를 새 엔트리에 복사하며, `{{중괄호}}` 플레이스홀더를 세션 값으로 치환.
    3. 마크다운 본문을 순회하며 각 `##` 헤더를 대화형 프롬프트로 변환. `[required]` 플래그가
       붙은 섹션은 비어있으면 엔트리를 쓰지 않습니다.

  wiki-log가 자동으로 채우는 플레이스홀더:
    {{DATE}}        생성 시점의 ISO 날짜 (YYYY-MM-DD)
    {{SESSION_ID}}  현재 LLM 세션 식별자
    {{PAPER_ID}}    연구자가 지정한 짧은 slug; 파일명 어간으로도 사용
    {{TITLE}}       연구자가 입력한 사람이 읽기 좋은 제목

  템플릿 전역 수정이 필요한 경우가 아니라면 아래 블록을 직접 편집하지 마세요.
  특정 엔트리만 달리 처리하고 싶으면 생성된 엔트리 파일을 편집하면 됩니다.
-->

---
# ===== Entry frontmatter (새 엔트리에 복사됨) =====

schema_version: 1
type: paper
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

# 논문 고유 메타데이터 (객관적 서지 정보만)
paper_id: {{PAPER_ID}}           # 짧은 slug; 파일명 어간으로도 사용
authors: []                      # 예: ["Vaswani", "Shazeer", ...]
year: null
venue: null                      # 예: "NeurIPS 2017"
source_url: null                 # DOI, arXiv URL, 또는 로컬 PDF 경로

# ===== 템플릿 전용 config (wiki-log가 소비; 엔트리에 복사 안 됨) =====

_template:
  auto_link:
    code:
      enabled: false             # 논문 엔트리는 연구자 코드베이스를 직접 참조하는 경우가 드묾
    papers:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    concepts:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    experiments:
      enabled: false
---

# {{TITLE}}

## 핵심 주장  [required]

*이 논문이 한두 문장으로 주장하는 바는 무엇인가요? 가능하면 논문의 어법을 그대로 사용하세요.
주장이 여러 개면 내 연구에 가장 관련있는 것만 여기 적고, 나머지는 "기타 주장"으로.*

## 방법 요약  [required]

*논문은 어떻게 주장을 뒷받침하나요? 본인의 말로 옮긴 요약 — 원문 복제가 아닌 요약입니다.
논문이 명시한 내용만 쓰고, 암시되었다고 추정한 단계는 채우지 마세요 (P8).*

## 내 연구와의 연관성  [required]

*이 논문을 내 위키에 남기는 이유는? 내 연구의 특정 개념, 실험, 설계 결정과 연결하세요.
이미 존재하는 항목은 slug로 참조 — wiki-log가 자동 링크 후보로 띄웁니다.*

## 기타 주장  [optional]

*논문이 제시한 부차적 주장들을 한 줄씩 나열.*

## 미해결 질문  [optional]

*논문이 남긴 미해결 질문 중 내 연구에 의미있는 것. 논문 자체에 대한 질문 —
불명확한 정의, 빠진 세부 — 도 포함. 이 섹션 내용은 `wiki/questions.md`에 덧붙여집니다.*

## 관련 개념  [optional]

*내 위키와 겹치는 논문의 개념들. 가능하면 slug 사용 — wiki-log가 정확 매치로 스캔합니다.*

## 주목할 인용  [optional]

*이 논문이 인용한 논문 중 후속으로 읽고 싶은 것. `- paper-slug — 왜 주목할 가치가 있는지`
형태로 한 줄씩.*
