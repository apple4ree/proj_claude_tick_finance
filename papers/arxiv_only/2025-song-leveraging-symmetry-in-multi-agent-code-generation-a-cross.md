# Leveraging Symmetry in Multi-Agent Code Generation: A Cross-Verification Collaboration Protocol for Competitive Programming

**Authors:** A Song, A Azman
**Venue:** arxiv_only 2025
**Confidence:** low
**Links:** [arXiv](https://www.mdpi.com/2073-8994/17/10/1660)

## Abstract
roles to prevent semantic drift and ensure specification fidelity; ( checking for transformation  invariance in candidate designs.  iterations and C LLM the average cost of a single LLM call (

## TL;DR
Leveraging Symmetry in Multi-Agent Code Generation: A Cross-Verification Collaboration Protocol for Competitive Programming — abstract 기반 1줄 요약은 본 파일 Abstract 블록과 ## 왜 관련 있는가 참조.

## Method
Abstract만으로 method 세부는 부분적. 풀 논문에서 (a) pipeline, (b) evaluation 방법, (c) dataset/benchmark 확인 필요.

## Result
Abstract가 수치 claim을 제공하는 경우 그대로, 아니면 '개선 주장 + 비교 대상'만 기재. 상세 수치는 풀 논문.

## Critical Reading
- 평가 해상도 (bar/tick/order-level) 확인 필요
- Reproducibility (model version, seed, data window) 공개 여부
- 우리 C4 4 failure modes 관점에서 어느 축(spec drift / micro-domain / handoff / invariant blindspot)이 누락인지

## 왜 이 프로젝트와 관련 있는가
Multi-agent code generation에서 cross-verification으로 semantic drift를 막고 specification fidelity를 유지하는 protocol — 우리 3-agent handoff (alpha→execution→spec-writer→coder) 에서의 field propagation audit 관점에서 직접 유사. 경쟁 프로그래밍 domain이라 trading 적용은 없음 → 우리 cross-domain contribution 주장에 tie-in.

## Figures
<!-- Figure extraction 결과가 있으면 이 섹션에 자동 append됨. 빈 채로 두면 extraction 실패/paywall. -->

## BibTeX
```bibtex
@inproceedings{song2025leveraging,
  title = {Leveraging Symmetry in Multi-Agent Code Generation: A Cross-Verification Collaboration Protocol for Competitive Programming},
  author = {A Song and A Azman},
  year = {2025},
  booktitle = {Symmetry},
  url = {https://www.mdpi.com/2073-8994/17/10/1660},
}
```
