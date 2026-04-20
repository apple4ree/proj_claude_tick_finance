# No Tick-Size Too Small: A General Method for Modelling Small Tick Limit Order Books

**Authors:** Konark Jain, Jean-François Muzy, Jonathan Kochems, Emmanuel Bacry
**Venue:** None 2024
**Links:** [arXiv](https://arxiv.org/abs/2410.08744v3) · [PDF](https://arxiv.org/pdf/2410.08744v3)

## Abstract
Tick-sizes not only influence the granularity of the price formation process but also affect market agents' behavior. We investigate the disparity in the microstructural properties of the Limit Order Book (LOB) across a basket of assets with different relative tick-sizes. A key contribution of this study is the identification of several stylized facts, which are used to differentiate between large, medium, and small-tick assets, along with clear metrics for their measurement. We provide cross-asset visualizations to illustrate how these attributes vary with relative tick-size. Further, we propose a Hawkes Process model that {\color{black}not only fits well for large-tick assets, but also accounts for }sparsity, multi-tick level price moves, and the shape of the LOB in small-tick assets. Through simulation studies, we demonstrate the {\color{black} versatility} of the model and identify key variables that determine whether a simulated LOB resembles a large-tick or small-tick asset. Our tests show that stylized facts like sparsity, shape, and relative returns distribution can be smoothly transitioned from a large-tick to a small-tick asset using our model. We test this model's assumptions, showcase its challenges and propose questions for further directions in this area of research.

## 한줄 요약
No Tick-Size Too Small: A General Method for Modelling Small Tick Limit Order Books — 2024년 Jain의 작업.

## 왜 이 프로젝트와 관련 있는가
Small tick LOB 모델링 — 우리 spec-invariant 중 `sl_overshoot` 같은 tick-size-sensitive invariant의 이론적 배경. BTC 1h는 tick 문제가 적지만, KRX archival + HFTBacktest 언급 시 필요.

## BibTeX
```bibtex
@article{jain2024,
  title = { No Tick-Size Too Small: A General Method for Modelling Small Tick Limit Order Books },
  author = { Konark Jain and Jean-François Muzy and Jonathan Kochems and Emmanuel Bacry },
  year = {2024},
  journal = {None}
}
```
