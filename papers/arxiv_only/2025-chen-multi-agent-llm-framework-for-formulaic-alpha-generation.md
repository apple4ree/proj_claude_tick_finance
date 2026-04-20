# Multi-Agent LLM Framework for Formulaic Alpha Generation and Selection in Quantitative Trading

**Authors:** Q Chen, H Kawashima
**Venue:** arxiv_only 2025
**Confidence:** low
**Links:** [arXiv](https://ieeexplore.ieee.org/abstract/document/11400963/)

## Abstract
excess returns beyond market benchmarks. While a single  formulaic alpha mining that  uses a dual-chain architecture of factor  decay-resistant alpha factors. By enforcing originality,

## TL;DR
Multi-Agent LLM Framework for Formulaic Alpha Generation and Selection in Quantitative Trading — abstract 기반 1줄 요약은 본 파일 Abstract 블록과 ## 왜 관련 있는가 참조.

## Method
Abstract만으로 method 세부는 부분적. 풀 논문에서 (a) pipeline, (b) evaluation 방법, (c) dataset/benchmark 확인 필요.

## Result
Abstract가 수치 claim을 제공하는 경우 그대로, 아니면 '개선 주장 + 비교 대상'만 기재. 상세 수치는 풀 논문.

## Critical Reading
- 평가 해상도 (bar/tick/order-level) 확인 필요
- Reproducibility (model version, seed, data window) 공개 여부
- 우리 C4 4 failure modes 관점에서 어느 축(spec drift / micro-domain / handoff / invariant blindspot)이 누락인지

## 왜 이 프로젝트와 관련 있는가
Multi-Agent LLM for Formulaic Alpha Generation — dual-chain architecture + decay-resistant alpha의 직접 baseline. 우리 alpha-designer → execution-designer 분리와 design philosophy가 유사. Tick-level LOB는 다루지 않으므로 우리가 '같은 multi-agent 구조에서 tick-level fidelity 이슈를 발견'한 contribution으로 positioning.

## Figures
<!-- Figure extraction 결과가 있으면 이 섹션에 자동 append됨. 빈 채로 두면 extraction 실패/paywall. -->

## BibTeX
```bibtex
@inproceedings{chen2025multi,
  title = {Multi-Agent LLM Framework for Formulaic Alpha Generation and Selection in Quantitative Trading},
  author = {Q Chen and H Kawashima},
  year = {2025},
  booktitle = {2025 IEEE International Conference …},
  url = {https://ieeexplore.ieee.org/abstract/document/11400963/},
}
```
