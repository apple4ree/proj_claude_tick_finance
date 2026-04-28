---
date: 2026-04-27 05:00
tone: design
title: Chain 1 의 OHLCV-bar 스타일 한계 진단
---

## Context
사용자 제기 — 현재 chain 1 의 SignalSpec 형식이 OHLCV-bar 처럼 묶인 paradigm 이 아닌가? 분석 결과 정확히 그러함을 확인. Tick 단위 데이터를 사용하나 spec language 자체가 binary trigger + fixed horizon 으로 제한.

## Done
- 진짜 tick-level / HFT 전략의 4가지 차원 정리: order-driven, spread capture, inventory & skew, asymmetric exit
- 우리 chain 1 의 한계 명시:
  - Action space: binary fire/not (continuous quote 불가능)
  - State: (snap, prev) 만 (자기 주문 / 재고 / 큐 위치 부재)
  - Reward: mid drift only (spread capture / fee rebate / inventory cost 모두 부재)
  - Exit: fixed H (PT/SL/time/event 조합 불가능)
- KRX MM 의 unit economics 시뮬: spread 12.5 bps × sell tax 20 bps 가 mechanical 한 적자 구조 — 현실적으로 -8 bps net

## Numbers
- KRX 005930 평균 spread: 12.5 bps (1 tick)
- 순수 MM (signal 없음) net: -10.5 bps
- MM + v3 13 bps signal naive net: +2.5 bps
- MM + 13 bps signal realistic net: -8 bps (fill rate 60% + adverse selection 보정)
- MM 만으로는 KRX cash equity sell tax 못 깸 — KRX HFT 가 derivatives (선물/옵션) 위주인 mechanical 이유

## Decisions & Rationale
- Chain 1 spec language 자체가 진짜 tick-level 표현력 부족 — 이건 한계가 아니라 의도된 design (raw edge 측정 분리)
- 진짜 MM 으로 가려면 PolicySpec schema 신설 + 4-agent set 추가 필요 (대규모 작업)
- KRX cash 한정으로는 MM 도 mechanical 적자 — sell tax 가 너무 큼

## Discarded
- Chain 1 의 SignalSpec 으로 quote-streaming MM 표현 시도: 불가능 — schema 자체가 binary trigger 기반
- Crypto maker 로 우회: 사용자 결정상 폐기

## Next
- 사용자 제안 "regime-state model" 으로 paradigm 변경 검증 — 매 tick trade 가 아니라 state machine 으로 보면 fee economics 가 어떻게 바뀌는지 측정
