# FactorMAD: A Multi-Agent Debate Framework Based on Large Language Models for Interpretable Stock Alpha Factor Mining

**Authors:** Y Duan, chuheng zhang, J Li
**Venue:** arxiv_only 2025
**Confidence:** low
**Links:** [arXiv](https://dl.acm.org/doi/abs/10.1145/3768292.3770377) · [PDF](https://dl.acm.org/doi/full/10.1145/3768292.3770377)

## Abstract
LLM-driven multi-agent debate as a powerful paradigm for mining high-quality alpha factors   some common benchmark tasks. Building upon this foundation, Chan et al. [2] introduce a

## TL;DR
FactorMAD: A Multi-Agent Debate Framework Based on Large Language Models for Interpretable Stock Alpha Factor Mining — abstract 기반 1줄 요약은 본 파일 Abstract 블록과 ## 왜 관련 있는가 참조.

## Method
Abstract만으로 method 세부는 부분적. 풀 논문에서 (a) pipeline, (b) evaluation 방법, (c) dataset/benchmark 확인 필요.

## Result
Abstract가 수치 claim을 제공하는 경우 그대로, 아니면 '개선 주장 + 비교 대상'만 기재. 상세 수치는 풀 논문.

## Critical Reading
- 평가 해상도 (bar/tick/order-level) 확인 필요
- Reproducibility (model version, seed, data window) 공개 여부
- 우리 C4 4 failure modes 관점에서 어느 축(spec drift / micro-domain / handoff / invariant blindspot)이 누락인지

## 왜 이 프로젝트와 관련 있는가
FactorMAD (2025): multi-agent debate 기반 alpha factor mining, interpretable stock alpha — LLM multi-agent trading의 debate paradigm 대표. 우리 pipeline은 debate가 아닌 sequential handoff(designer → coder)이라는 점을 differentiator로 명시.

## Figures
<!-- Figure extraction 결과가 있으면 이 섹션에 자동 append됨. 빈 채로 두면 extraction 실패/paywall. -->

## BibTeX
```bibtex
@inproceedings{duan2025factormad,
  title = {FactorMAD: A Multi-Agent Debate Framework Based on Large Language Models for Interpretable Stock Alpha Factor Mining},
  author = {Y Duan and chuheng zhang and J Li},
  year = {2025},
  booktitle = {Proceedings of the 6th ACM International …},
  url = {https://dl.acm.org/doi/abs/10.1145/3768292.3770377},
}
```
