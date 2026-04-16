"""Interactive HTML backtest report renderer.

Reads `spec.yaml`, `report.json`, `trace.json` from a strategy directory
and produces `report.html` with Plotly-backed interactive charts:

- Row 1: mid-price series per symbol with BUY (^) and SELL (v) markers.
- Row 2: equity curve (cash + mark-to-mid).
- Row 3: drawdown from running peak.

Metric cards above the chart surface return, Sharpe, MDD, trades,
win rate, fees, etc. Spec YAML is shown in a collapsible footer.

Token-optimized: the renderer is a pure Python function invoked by the
runner. Agents never read the HTML — they just get its path back in the
report JSON.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import yaml
from plotly.subplots import make_subplots

_KST = timezone(timedelta(hours=9))


def _ts(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=_KST).isoformat()


def _fmt_param_val(v: object) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, int) and v > 9999:
        return f"{v:,}"
    return str(v)


def _spec_description_html(spec: dict) -> str:
    """Human-readable description block rendered inside the spec.yaml details."""
    sections: list[str] = []

    # --- Description ---
    desc = (spec.get("description") or "").strip()
    if desc:
        esc = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        para = esc.replace("\n\n", "</p><p>").replace("\n", "<br>")
        sections.append(
            '<div class="spec-section">'
            '<div class="spec-section-title">전략 설명</div>'
            f"<p>{para}</p>"
            "</div>"
        )

    # --- Parameters ---
    params = spec.get("params") or {}
    if params:
        rows = "".join(
            f'<tr><td class="pk">{k}</td><td class="pv">{_fmt_param_val(v)}</td></tr>'
            for k, v in params.items()
        )
        sections.append(
            '<div class="spec-section">'
            '<div class="spec-section-title">파라미터</div>'
            '<table class="spec-table">'
            "<thead><tr><th>파라미터</th><th>값</th></tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table></div>"
        )

    # --- Payoff & Fee Mechanics (수식) ---
    fees_cfg = spec.get("fees") or {}
    params_cfg = spec.get("params") or {}
    pt  = params_cfg.get("profit_target_bps")
    sl  = params_cfg.get("stop_loss_bps")
    lot = params_cfg.get("lot_size")
    comm = float(fees_cfg.get("commission_bps", 1.5))
    tax  = float(fees_cfg.get("tax_bps", 18.0))
    rtt  = comm + tax  # round-trip cost bps

    if pt is not None and sl is not None:
        pt_f, sl_f = float(pt), float(sl)
        be_wr = sl_f / (pt_f + sl_f) * 100 if (pt_f + sl_f) > 0 else 0.0
        payoff = pt_f / sl_f if sl_f > 0 else 0.0
        lot_str = f"  ·  lot = {lot}" if lot is not None else ""

        formula_rows = [
            ("왕복 비용",
             f"수수료 ({comm} bps) + 매도세 ({tax} bps) = <b>{rtt:.1f} bps</b>"),
            ("손익분기 승률",
             f"손절 / (익절 + 손절) = {sl_f:.0f} / ({pt_f:.0f} + {sl_f:.0f}) = <b>{be_wr:.1f}%</b>"),
            ("손익비 (P:L)",
             f"익절 / 손절 = {pt_f:.0f} / {sl_f:.0f} = <b>{payoff:.2f}</b>{lot_str}"),
            ("최소 요구 edge",
             f"실제 승률이 {be_wr:.1f}%를 초과해야 {rtt:.1f} bps 비용 후 수익 가능"),
        ]
        rows_f = "".join(
            f'<tr><td class="pk">{k}</td><td class="pv">{v}</td></tr>'
            for k, v in formula_rows
        )
        sections.append(
            '<div class="spec-section">'
            '<div class="spec-section-title">손익 구조 및 수수료</div>'
            '<table class="spec-table">'
            "<thead><tr><th>항목</th><th>값</th></tr></thead>"
            f"<tbody>{rows_f}</tbody>"
            "</table></div>"
        )

    # --- Universe & Config ---
    universe = spec.get("universe") or {}
    fees = spec.get("fees") or {}
    latency = spec.get("latency") or {}
    meta: list[tuple[str, str]] = []

    syms = universe.get("symbols", [])
    if syms:
        meta.append(("종목", ", ".join(syms)))
    dates = universe.get("dates", [])
    if dates:
        meta.append(("기간", f"{dates[0]} → {dates[-1]}  ({len(dates)}일)"))
    if spec.get("capital"):
        meta.append(("자본금", f"{spec['capital']:,} KRW"))
    if fees:
        comm = fees.get("commission_bps", 0)
        tax = fees.get("tax_bps", 0)
        meta.append(("수수료", f"수수료 {comm} bps + 매도세 {tax} bps → 왕복 {comm + tax} bps"))
    if latency:
        meta.append(("지연시간", f"제출 {latency.get('submit_ms', 0)} ms ± {latency.get('jitter_ms', 0)} ms 변동"))

    if meta:
        rows = "".join(
            f'<tr><td class="pk">{k}</td><td class="pv">{v}</td></tr>'
            for k, v in meta
        )
        sections.append(
            '<div class="spec-section">'
            '<div class="spec-section-title">유니버스 및 설정</div>'
            '<table class="spec-table">'
            "<thead><tr><th>항목</th><th>값</th></tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table></div>"
        )

    return "\n".join(sections)


def _sensitivity_panel_html(spec: dict, report: dict) -> str:
    """Interactive break-even WR and fee burden panel (pure JS, no backtest re-run)."""
    params   = spec.get("params") or {}
    fees     = spec.get("fees") or {}

    profit_target  = float(params.get("profit_target_bps", 150.0))
    stop_loss      = float(params.get("stop_loss_bps", 50.0))
    lot_size       = int(params.get("lot_size", 2))
    commission_bps = float(fees.get("commission_bps", 1.5))
    tax_bps        = float(fees.get("tax_bps", 18.0))
    round_trip_bps = commission_bps + tax_bps

    current_wr      = float(report.get("win_rate_pct", 0))
    n_roundtrips    = int(report.get("n_roundtrips", 0))
    total_fees      = float(report.get("total_fees", 0))
    avg_win_bps     = float(report.get("avg_win_bps", profit_target))
    original_lot    = lot_size  # lot_size from spec (fee baseline)

    # break-even WR at spec params
    be_wr_spec = stop_loss / (profit_target + stop_loss) * 100 if (profit_target + stop_loss) > 0 else 50.0
    edge_spec  = current_wr - be_wr_spec

    return f"""
<div class="sens-wrap">
  <div class="sens-title">파라미터 민감도 분석</div>

  <!-- ① 수익 구조 분석 -->
  <div class="sens-section-label">① 수익 구조 — break-even WR</div>
  <div class="sens-row">
    <span class="sens-name">profit target (bps)</span>
    <input class="sens-slider" type="range" min="30" max="400" step="5"
           value="{profit_target:.0f}" id="pt-sl" oninput="sensUpdate()">
    <span class="sens-val" id="pt-val">{profit_target:.0f}</span>
  </div>
  <div class="sens-row">
    <span class="sens-name">stop loss (bps)</span>
    <input class="sens-slider" type="range" min="10" max="200" step="5"
           value="{stop_loss:.0f}" id="sl-sl" oninput="sensUpdate()">
    <span class="sens-val" id="sl-val">{stop_loss:.0f}</span>
  </div>

  <div class="sens-metrics">
    <div class="sens-card">
      <div class="sens-label">Break-even WR</div>
      <div class="sens-value" id="be-wr">—</div>
    </div>
    <div class="sens-card">
      <div class="sens-label">실제 WR (고정)</div>
      <div class="sens-value" style="color:#16a34a">{current_wr:.1f}%</div>
    </div>
    <div class="sens-card">
      <div class="sens-label">엣지 마진</div>
      <div class="sens-value" id="edge-margin">—</div>
    </div>
    <div class="sens-card">
      <div class="sens-label">손익비 (P:L)</div>
      <div class="sens-value" id="payoff-ratio">—</div>
    </div>
  </div>

  <!-- WR 비교 바 -->
  <div class="wr-bar-wrap">
    <div class="wr-bar-label">실제 WR</div>
    <div class="wr-track">
      <div class="wr-fill wr-current" id="wr-current-bar" style="width:{min(current_wr,100):.1f}%"></div>
      <div class="wr-marker" id="wr-be-marker" style="left:{min(be_wr_spec,100):.1f}%">
        <div class="wr-marker-line"></div>
        <div class="wr-marker-label" id="wr-be-label">BE {be_wr_spec:.1f}%</div>
      </div>
    </div>
    <div class="wr-bar-label" style="text-align:right">{current_wr:.1f}%</div>
  </div>

  <div class="sens-divider"></div>

  <!-- ② 수수료 부담 분석 -->
  <div class="sens-section-label">② 수수료 부담 분석</div>
  <div class="sens-row">
    <span class="sens-name">lot size</span>
    <input class="sens-slider" type="range" min="1" max="10" step="1"
           value="{lot_size}" id="lot-sl" oninput="sensUpdate()">
    <span class="sens-val" id="lot-val">{lot_size}</span>
  </div>

  <div class="sens-metrics">
    <div class="sens-card">
      <div class="sens-label">수수료 round-trip</div>
      <div class="sens-value">{round_trip_bps:.1f} bps</div>
    </div>
    <div class="sens-card">
      <div class="sens-label">수수료 / profit target</div>
      <div class="sens-value" id="fee-ratio">—</div>
    </div>
    <div class="sens-card">
      <div class="sens-label">수수료 차감 순익 (bps)</div>
      <div class="sens-value" id="net-profit">—</div>
    </div>
    <div class="sens-card">
      <div class="sens-label">lot 변경 시 총 수수료 추정</div>
      <div class="sens-value" id="fee-scaled">—</div>
    </div>
  </div>

  <!-- 수수료 부담 바 -->
  <div class="fee-bar-wrap">
    <div class="fee-bar-bg">
      <div class="fee-bar-cost" id="fee-bar-cost"></div>
      <div class="fee-bar-net"  id="fee-bar-net"></div>
    </div>
    <div class="fee-bar-legend">
      <span><span class="fee-dot fee-dot-cost"></span>수수료</span>
      <span><span class="fee-dot fee-dot-net"></span>순 수익</span>
    </div>
  </div>
</div>

<script>
(function() {{
  const CURRENT_WR     = {current_wr:.4f};
  const ROUND_TRIP_BPS = {round_trip_bps:.4f};
  const TOTAL_FEES     = {total_fees:.2f};
  const N_ROUNDTRIPS   = {n_roundtrips};
  const ORIG_LOT       = {original_lot};

  function fmt1(v) {{ return v.toFixed(1); }}
  function fmt0(v) {{ return v.toFixed(0); }}

  window.sensUpdate = function() {{
    const profit  = parseFloat(document.getElementById('pt-sl').value);
    const stop    = parseFloat(document.getElementById('sl-sl').value);
    const lotSize = parseInt(document.getElementById('lot-sl').value);

    document.getElementById('pt-val').textContent  = fmt0(profit);
    document.getElementById('sl-val').textContent  = fmt0(stop);
    document.getElementById('lot-val').textContent = lotSize;

    // ① break-even WR
    const beWR = stop / (profit + stop) * 100;
    document.getElementById('be-wr').textContent = fmt1(beWR) + '%';

    const edge = CURRENT_WR - beWR;
    const edgeEl = document.getElementById('edge-margin');
    edgeEl.textContent = (edge >= 0 ? '+' : '') + fmt1(edge) + 'pp';
    edgeEl.style.color = edge >= 5 ? '#16a34a' : edge >= 0 ? '#d97706' : '#dc2626';

    const payoff = profit / stop;
    document.getElementById('payoff-ratio').textContent = fmt1(payoff) + ':1';

    // WR bar
    const beClamp = Math.min(Math.max(beWR, 0), 100);
    document.getElementById('wr-be-marker').style.left = beClamp + '%';
    document.getElementById('wr-be-label').textContent  = 'BE ' + fmt1(beWR) + '%';
    document.getElementById('wr-current-bar').style.width = Math.min(CURRENT_WR, 100) + '%';

    // ② fee burden
    const feeRatio = ROUND_TRIP_BPS / profit * 100;
    document.getElementById('fee-ratio').textContent = fmt1(feeRatio) + '%';

    const netProfit = profit - ROUND_TRIP_BPS;
    const netEl = document.getElementById('net-profit');
    netEl.textContent = (netProfit >= 0 ? '+' : '') + fmt1(netProfit) + ' bps';
    netEl.style.color = netProfit >= 0 ? '#16a34a' : '#dc2626';

    // scale total fees proportional to lot change
    const feeScaled = N_ROUNDTRIPS > 0
      ? (TOTAL_FEES / ORIG_LOT * lotSize)
      : 0;
    document.getElementById('fee-scaled').textContent =
      Math.round(feeScaled).toLocaleString() + ' KRW';

    // fee bar (% breakdown of profit target)
    const costPct = Math.min(feeRatio, 100);
    const netPct  = Math.max(100 - costPct, 0);
    document.getElementById('fee-bar-cost').style.width = costPct + '%';
    document.getElementById('fee-bar-net').style.width  = netPct  + '%';
  }};

  sensUpdate();
}})();
</script>
"""


def _metric_cards(report: dict) -> str:
    cards = [
        ("수익률", f"{report.get('return_pct', 0):.3f}%"),
        ("총 손익", f"{report.get('total_pnl', 0):,.0f}"),
        ("샤프 (raw)", f"{report.get('sharpe_raw', 0):.3f}"),
        ("샤프 (연환산)", f"{report.get('sharpe_annualized', 0):.3f}"),
        ("MDD", f"{report.get('mdd_pct', 0):.3f}%"),
        ("주문 수", f"{report.get('n_trades', 0)}"),
        ("라운드트립", f"{report.get('n_roundtrips', 0)}"),
        ("승률", f"{report.get('win_rate_pct', 0):.1f}%"),
        ("Avg trade", f"{report.get('avg_trade_pnl', 0):,.0f}"),
        ("최대 수익 거래", f"{report.get('best_trade', 0):,.0f}"),
        ("최대 손실 거래", f"{report.get('worst_trade', 0):,.0f}"),
        ("총 수수료", f"{report.get('total_fees', 0):,.0f}"),
    ]
    return "".join(
        f'<div class="card"><div class="label">{label}</div><div class="value">{val}</div></div>'
        for label, val in cards
    )


def _build_figure(report: dict, trace: dict) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("가격 및 체결", "자산곡선", "낙폭 (%)"),
        vertical_spacing=0.05,
        row_heights=[0.52, 0.24, 0.24],
    )

    palette = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"]

    # Row 1 — mid series per symbol
    mid_series = trace.get("mid_series", {}) or {}
    for i, (sym, series) in enumerate(mid_series.items()):
        if not series:
            continue
        xs = [_ts(s[0]) for s in series]
        ys = [s[1] for s in series]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                name=f"{sym}",
                line=dict(color=palette[i % len(palette)], width=1.3),
                hovertemplate="%{x}<br>mid=%{y}<extra>" + sym + "</extra>",
            ),
            row=1,
            col=1,
        )

    # Buy / sell markers
    fills = trace.get("fills", []) or []
    buys = [f for f in fills if f.get("side") == "BUY"]
    sells = [f for f in fills if f.get("side") == "SELL"]

    def _marker_trace(items, name, symbol, color, edge):
        if not items:
            return None
        return go.Scatter(
            x=[_ts(f["ts_ns"]) for f in items],
            y=[f["avg_price"] for f in items],
            mode="markers",
            name=name,
            marker=dict(
                symbol=symbol,
                size=11,
                color=color,
                line=dict(color=edge, width=1.2),
            ),
            customdata=[
                [f.get("symbol", ""), f.get("qty", 0), f.get("fee", 0), f.get("tag", "")]
                for f in items
            ],
            hovertemplate=(
                name + " %{customdata[0]}<br>qty=%{customdata[1]}"
                "<br>px=%{y}<br>fee=%{customdata[2]:.2f}"
                "<br>tag=%{customdata[3]}<extra></extra>"
            ),
        )

    buy_trace = _marker_trace(buys, "BUY", "triangle-up", "#16a34a", "#052e16")
    sell_trace = _marker_trace(sells, "SELL", "triangle-down", "#dc2626", "#450a0a")
    if buy_trace is not None:
        fig.add_trace(buy_trace, row=1, col=1)
    if sell_trace is not None:
        fig.add_trace(sell_trace, row=1, col=1)

    # Row 2 — equity curve
    equity_curve = trace.get("equity_curve", []) or []
    if equity_curve:
        eq_x = [_ts(e[0]) for e in equity_curve]
        eq_y = [e[1] for e in equity_curve]
        fig.add_trace(
            go.Scatter(
                x=eq_x,
                y=eq_y,
                mode="lines",
                name="Equity",
                line=dict(color="#2563eb", width=1.6),
                hovertemplate="%{x}<br>equity=%{y:,.0f}<extra></extra>",
            ),
            row=2,
            col=1,
        )
        start_cash = report.get("starting_cash", eq_y[0])
        fig.add_trace(
            go.Scatter(
                x=[eq_x[0], eq_x[-1]],
                y=[start_cash, start_cash],
                mode="lines",
                name="Starting cash",
                line=dict(color="#94a3b8", dash="dash", width=1),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=2,
            col=1,
        )

        # Row 3 — drawdown
        equity = np.array(eq_y, dtype=np.float64)
        peak = np.maximum.accumulate(equity)
        peak_safe = np.where(peak != 0, peak, 1.0)
        dd_pct = (equity - peak) / peak_safe * 100.0
        fig.add_trace(
            go.Scatter(
                x=eq_x,
                y=dd_pct.tolist(),
                mode="lines",
                name="낙폭 %",
                line=dict(color="#dc2626", width=1),
                fill="tozeroy",
                fillcolor="rgba(220,38,38,0.18)",
                hovertemplate="%{x}<br>dd=%{y:.3f}%<extra></extra>",
            ),
            row=3,
            col=1,
        )

    fig.update_layout(
        height=820,
        margin=dict(l=60, r=20, t=60, b=40),
        hovermode="x unified",
        font=dict(
            family="system-ui, -apple-system, Pretendard, 'Noto Sans KR', sans-serif",
            size=11,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", y=-0.08, x=0),
    )
    for r in range(1, 4):
        fig.update_xaxes(showgrid=True, gridcolor="#e5e7eb", row=r, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb", row=r, col=1)
    return fig


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Noto Sans KR', system-ui, sans-serif;
    background: #fafafa;
    color: #111827;
    margin: 0;
    padding: 32px 24px 56px;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1240px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; font-weight: 800; letter-spacing: -0.015em; }}
  .sub {{ color: #6b7280; font-size: 13px; margin-bottom: 22px; }}
  .sub code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 22px;
  }}
  @media (max-width: 960px) {{ .cards {{ grid-template-columns: repeat(4, 1fr); }} }}
  @media (max-width: 560px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
  .card {{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 14px;
    min-width: 0;
  }}
  .card .label {{
    color: #6b7280;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
  }}
  .card .value {{
    font-size: 17px;
    font-weight: 700;
    color: #1a1a1a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .chart-wrap {{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 10px;
  }}
  /* ── Sensitivity panel ───────────────────────── */
  .sens-wrap {{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 18px 20px;
    margin-top: 18px;
  }}
  .sens-title {{
    font-size: 13px; font-weight: 700; color: #374151;
    margin-bottom: 14px; letter-spacing: -0.01em;
  }}
  .sens-section-label {{
    font-size: 10.5px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #9ca3af; margin: 12px 0 8px;
  }}
  .sens-row {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
  }}
  .sens-name {{
    font-size: 12px; color: #6b7280;
    min-width: 160px; font-family: 'Menlo','Consolas',monospace;
  }}
  .sens-val {{
    font-size: 12px; font-weight: 600; color: #111827;
    min-width: 38px; text-align: right; font-family: 'Menlo','Consolas',monospace;
  }}
  .sens-slider {{
    flex: 1; -webkit-appearance: none; appearance: none;
    height: 4px; border-radius: 2px; background: #e5e7eb; outline: none; cursor: pointer;
  }}
  .sens-slider::-webkit-slider-thumb {{
    -webkit-appearance: none; width: 16px; height: 16px;
    border-radius: 50%; background: #374151; cursor: pointer;
  }}
  .sens-metrics {{
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 8px; margin: 12px 0 8px;
  }}
  @media (max-width: 700px) {{ .sens-metrics {{ grid-template-columns: repeat(2, 1fr); }} }}
  .sens-card {{
    background: #f9fafb; border: 1px solid #e5e7eb;
    border-radius: 8px; padding: 10px 12px;
  }}
  .sens-label {{
    font-size: 10px; color: #9ca3af; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px;
  }}
  .sens-value {{
    font-size: 16px; font-weight: 700; color: #111827;
    font-family: 'Menlo','Consolas',monospace;
  }}
  /* WR comparison bar */
  .wr-bar-wrap {{
    display: flex; align-items: center; gap: 8px; margin: 8px 0;
  }}
  .wr-bar-label {{ font-size: 11px; color: #9ca3af; min-width: 52px; }}
  .wr-track {{
    flex: 1; height: 16px; background: #f3f4f6;
    border-radius: 8px; position: relative; overflow: visible;
  }}
  .wr-fill {{
    height: 100%; border-radius: 8px; transition: width .2s;
  }}
  .wr-current {{ background: #2563eb; }}
  .wr-marker {{
    position: absolute; top: -4px; transform: translateX(-50%);
    transition: left .2s;
  }}
  .wr-marker-line {{
    width: 2px; height: 24px; background: #ef4444; margin: 0 auto;
  }}
  .wr-marker-label {{
    font-size: 9px; color: #ef4444; font-weight: 700;
    white-space: nowrap; text-align: center; margin-top: 2px;
  }}
  /* Fee bar */
  .fee-bar-wrap {{ margin: 10px 0 4px; }}
  .fee-bar-bg {{
    display: flex; height: 14px; border-radius: 7px; overflow: hidden;
    background: #f3f4f6;
  }}
  .fee-bar-cost {{
    background: #fca5a5; height: 100%; transition: width .2s;
  }}
  .fee-bar-net {{
    background: #86efac; height: 100%; transition: width .2s;
  }}
  .fee-bar-legend {{
    display: flex; gap: 12px; font-size: 11px; color: #9ca3af; margin-top: 5px;
  }}
  .fee-dot {{
    display: inline-block; width: 8px; height: 8px;
    border-radius: 2px; margin-right: 4px; vertical-align: middle;
  }}
  .fee-dot-cost {{ background: #fca5a5; }}
  .fee-dot-net  {{ background: #86efac; }}
  .sens-divider {{
    border: none; border-top: 1px solid #e5e7eb; margin: 14px 0;
  }}
  /* ── end sensitivity panel ────────────────────── */
  /* Symbol tabs */
  .tab-bar {{
    display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;
  }}
  .tab-btn {{
    padding: 6px 16px; border: 1px solid #e5e7eb; border-radius: 8px;
    cursor: pointer; font-size: 13px; font-weight: 600; background: white;
    color: #374151; font-family: inherit; transition: all 0.12s;
  }}
  .tab-btn:hover {{ background: #f3f4f6; }}
  .tab-btn.active {{ background: #2563eb; color: white; border-color: #2563eb; }}
  .meta {{
    margin-top: 24px;
    color: #6b7280;
    font-size: 12px;
  }}
  .meta details summary {{
    cursor: pointer;
    font-weight: 600;
    color: #374151;
    padding: 6px 0;
  }}
  .meta pre {{
    background: #1e293b;
    color: #e2e8f0;
    padding: 14px;
    border-radius: 8px;
    font-size: 12px;
    overflow-x: auto;
    line-height: 1.5;
    margin-bottom: 0;
  }}
  .spec-section {{
    margin-top: 18px;
    border-top: 1px solid #334155;
    padding-top: 14px;
  }}
  .spec-section-title {{
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #94a3b8;
    margin-bottom: 8px;
  }}
  .spec-section p {{
    color: #cbd5e1;
    line-height: 1.7;
    font-size: 12.5px;
    margin: 0;
    white-space: pre-wrap;
  }}
  .spec-table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 12px;
  }}
  .spec-table th {{
    text-align: left;
    color: #64748b;
    font-weight: 600;
    padding: 3px 10px;
    border-bottom: 1px solid #334155;
  }}
  .spec-table td {{
    padding: 4px 10px;
    border-bottom: 1px solid #1e3a5f33;
    vertical-align: top;
  }}
  .pk {{
    color: #7dd3fc;
    font-family: 'Menlo', 'Consolas', monospace;
    white-space: nowrap;
    width: 34%;
  }}
  .pv {{
    color: #e2e8f0;
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="sub">
    strategy <code>{strat_id}</code> ·
    symbols {symbols} ·
    dates {dates} ·
    {events:,} ticks ·
    {duration:.2f}s
  </div>
  <div class="cards">{cards}</div>
  <div class="chart-wrap">{chart}</div>
  {sensitivity_panel}
  {per_day_section}
  {fill_context_section}
  <div class="meta">
    {spec_description}
    <details>
      <summary>spec.yaml (raw)</summary>
      <pre>{spec_escaped}</pre>
    </details>
  </div>
</div>
</body>
</html>
"""


def _per_day_section_html(report: dict) -> str:
    """Per-day breakdown table: n_entries, n_roundtrips, wins, losses, stops, EOD, net_pnl."""
    per_day = report.get("per_day") or {}
    if not per_day:
        return ""

    rows_html = ""
    for date, d in sorted(per_day.items()):
        pnl = d.get("net_pnl", 0.0)
        pnl_color = "#16a34a" if pnl >= 0 else "#dc2626"
        wr = 0.0
        if d.get("n_roundtrips", 0) > 0:
            wr = d["n_wins"] / d["n_roundtrips"] * 100
        rows_html += (
            f'<tr>'
            f'<td>{date}</td>'
            f'<td>{d.get("n_entries", 0)}</td>'
            f'<td>{d.get("n_roundtrips", 0)}</td>'
            f'<td style="color:#16a34a">{d.get("n_wins", 0)}</td>'
            f'<td style="color:#dc2626">{d.get("n_losses", 0)}</td>'
            f'<td>{d.get("n_stops", 0)}</td>'
            f'<td>{d.get("n_eod", 0)}</td>'
            f'<td style="font-weight:600">{wr:.0f}%</td>'
            f'<td style="color:{pnl_color};font-weight:600">{pnl:+,.0f}</td>'
            f'</tr>'
        )

    return f"""
<div class="sens-wrap" style="margin-top:1.5rem">
  <div class="sens-title">일별 트레이딩 결과 (KST)</div>
  <div style="overflow-x:auto">
    <table class="spec-table" style="width:100%;min-width:640px">
      <thead>
        <tr>
          <th>Date</th><th>진입</th><th>체결</th>
          <th style="color:#16a34a">WIN</th><th style="color:#dc2626">LOSS</th>
          <th>SL</th><th>EOD</th><th>WR</th><th>Net PnL (KRW)</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>"""


def _fill_context_section_html(report: dict) -> str:
    """WIN vs LOSS average fill-time LOB context comparison."""
    roundtrips = report.get("roundtrips") or []
    if not roundtrips:
        return ""

    wins = [rt for rt in roundtrips if rt.get("outcome") == "WIN" and rt.get("entry_context")]
    losses = [rt for rt in roundtrips if rt.get("outcome") == "LOSS" and rt.get("entry_context")]

    if not wins and not losses:
        return ""

    def _avg(rts: list, key: str) -> str:
        vals = [rt["entry_context"].get(key) for rt in rts if key in (rt.get("entry_context") or {})]
        if not vals:
            return "—"
        return f"{sum(vals) / len(vals):.4f}"

    def _avg_bps(rts: list, key: str) -> str:
        vals = [rt["entry_context"].get(key) for rt in rts if key in (rt.get("entry_context") or {})]
        if not vals:
            return "—"
        return f"{sum(vals) / len(vals):.2f}"

    metrics = [
        ("OBI (order book imbalance)", "obi", _avg),
        ("Spread (bps)", "spread_bps", _avg_bps),
        ("Mid price (KRW)", "mid", lambda rts, k: f"{sum(rt['entry_context'].get(k, 0) for rt in rts if rt.get('entry_context')) / max(len(rts), 1):,.0f}"),
        ("Acml vol", "acml_vol", lambda rts, k: f"{int(sum(rt['entry_context'].get(k, 0) for rt in rts if rt.get('entry_context')) / max(len(rts), 1)):,}"),
    ]

    rows_html = ""
    for label, key, fmt_fn in metrics:
        w_val = fmt_fn(wins, key) if wins else "—"
        l_val = fmt_fn(losses, key) if losses else "—"
        rows_html += (
            f'<tr><td>{label}</td>'
            f'<td style="color:#16a34a;font-weight:600">{w_val}</td>'
            f'<td style="color:#dc2626;font-weight:600">{l_val}</td></tr>'
        )

    # avg pnl_bps per outcome
    if wins:
        avg_win_bps = sum(rt.get("pnl_bps", 0) for rt in wins) / len(wins)
        rows_html += f'<tr><td>Avg PnL (bps)</td><td style="color:#16a34a;font-weight:600">{avg_win_bps:+.2f}</td><td>—</td></tr>'
    if losses:
        avg_loss_bps = sum(rt.get("pnl_bps", 0) for rt in losses) / len(losses)
        rows_html += f'<tr><td>Avg PnL (bps)</td><td>—</td><td style="color:#dc2626;font-weight:600">{avg_loss_bps:+.2f}</td></tr>'

    return f"""
<div class="sens-wrap" style="margin-top:1.5rem">
  <div class="sens-title">WIN vs LOSS — 진입 시점 LOB 컨텍스트 비교</div>
  <p style="font-size:0.8rem;color:#6b7280;margin:0 0 0.75rem">
    N: {len(wins)} WIN, {len(losses)} LOSS &nbsp;·&nbsp; entry_context = 체결 직전 스냅샷 기준
  </p>
  <div style="overflow-x:auto">
    <table class="spec-table" style="width:100%">
      <thead>
        <tr>
          <th>Metric</th>
          <th style="color:#16a34a">WIN avg</th>
          <th style="color:#dc2626">LOSS avg</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>"""


def _build_symbol_tabs_html(report: dict, trace: dict) -> str:
    """Tab bar + per-symbol Plotly charts for report.html.

    Each tab shows: that symbol's mid-price + BUY/SELL markers (row 1)
    + global equity curve (row 2) + global drawdown (row 3).

    The first tab's figure includes the Plotly CDN script; subsequent
    tabs use include_plotlyjs=False so the script is only loaded once.
    """
    mid_series = trace.get("mid_series", {}) or {}
    fills = trace.get("fills", []) or []
    equity_curve = trace.get("equity_curve", [])
    symbols = list(mid_series.keys())

    if not symbols:
        # Fallback: single figure with whatever is in trace
        fig = _build_figure(report, trace)
        return fig.to_html(
            include_plotlyjs="cdn", full_html=False,
            div_id="chart-root", config={"responsive": True},
        )

    tab_buttons: list[str] = []
    tab_panels: list[str] = []

    for i, sym in enumerate(symbols):
        is_first = i == 0
        active_cls = "active" if is_first else ""

        # Slice trace to this symbol only (equity/drawdown stay global)
        sym_trace = {
            "mid_series": {sym: mid_series[sym]},
            "fills": [f for f in fills if f.get("symbol") == sym],
            "equity_curve": equity_curve,
        }

        fig = _build_figure(report, sym_trace)
        chart_html = fig.to_html(
            include_plotlyjs="cdn" if is_first else False,
            full_html=False,
            div_id=f"chart-{sym}",
            config={"responsive": True},
        )

        tab_buttons.append(
            f'<button class="tab-btn {active_cls}"'
            f' onclick="showSymTab(\'{sym}\', this)">{sym}</button>'
        )
        tab_panels.append(
            f'<div id="sym-tab-{sym}" class="sym-tab-panel"'
            f' style="display:{"block" if is_first else "none"}">'
            f'{chart_html}'
            f'</div>'
        )

    tab_js = """<script>
function showSymTab(sym, btn) {
  document.querySelectorAll('.sym-tab-panel').forEach(function(p) { p.style.display = 'none'; });
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.getElementById('sym-tab-' + sym).style.display = 'block';
  btn.classList.add('active');
}
</script>"""

    return (
        f'<div class="tab-bar">{"".join(tab_buttons)}</div>\n'
        + "\n".join(tab_panels)
        + "\n" + tab_js
    )


def render(strategy_dir: Path) -> Path:
    report = json.loads((strategy_dir / "report.json").read_text())
    trace_path = strategy_dir / "trace.json"
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else {}
    spec_text = (strategy_dir / "spec.yaml").read_text()
    spec = yaml.safe_load(spec_text) or {}

    chart_html = _build_symbol_tabs_html(report, trace)

    html = _HTML_TEMPLATE.format(
        title=report.get("spec_name", strategy_dir.name),
        strat_id=strategy_dir.name,
        symbols=", ".join(report.get("symbols", [])) or "—",
        dates=", ".join(report.get("dates", [])) or "—",
        events=report.get("total_events", 0),
        duration=report.get("duration_sec", 0.0),
        cards=_metric_cards(report),
        chart=chart_html,
        sensitivity_panel=_sensitivity_panel_html(spec, report),
        per_day_section=_per_day_section_html(report),
        fill_context_section=_fill_context_section_html(report),
        spec_escaped=spec_text.replace("<", "&lt;").replace(">", "&gt;"),
        spec_description=_spec_description_html(spec),
    )

    out = strategy_dir / "report.html"
    out.write_text(html)
    return out


def _sym_metric_cards(sym_data: dict) -> str:
    ret = sym_data.get("return_pct", 0)
    ret_color = "#16a34a" if ret >= 0 else "#dc2626"
    wr = sym_data.get("win_rate_pct", 0)
    wr_color = "#16a34a" if wr >= 35.5 else "#dc2626"
    cards = [
        ("수익률", f'<span style="color:{ret_color}">{ret:+.4f}%</span>'),
        ("라운드트립", str(sym_data.get("n_roundtrips", 0))),
        ("승률", f'<span style="color:{wr_color}">{wr:.1f}%</span>'),
        ("최대 수익", f'{sym_data.get("best_trade", 0):,.0f}'),
        ("최대 손실", f'{sym_data.get("worst_trade", 0):,.0f}'),
        ("총 수수료", f'{sym_data.get("total_fees", 0):,.0f}'),
    ]
    return "".join(
        f'<div class="card"><div class="label">{label}</div>'
        f'<div class="value" style="font-size:15px">{val}</div></div>'
        for label, val in cards
    )


def _build_comparison_chart(per_symbol: dict, starting_cash: float) -> str:
    syms = list(per_symbol.keys())
    returns = [per_symbol[s]["return_pct"] for s in syms]
    win_rates = [per_symbol[s]["win_rate_pct"] for s in syms]
    roundtrips = [per_symbol[s]["n_roundtrips"] for s in syms]

    bar_colors = ["#16a34a" if r >= 0 else "#dc2626" for r in returns]
    wr_colors = ["#16a34a" if w >= 35.5 else "#dc2626" for w in win_rates]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("종목별 수익률 (%)", "종목별 승률 (%)"),
        horizontal_spacing=0.12,
    )

    fig.add_trace(
        go.Bar(
            y=syms,
            x=returns,
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{r:+.4f}%" for r in returns],
            textposition="outside",
            hovertemplate="%{y}: %{x:+.4f}%<extra></extra>",
            name="수익률 %",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            y=syms,
            x=win_rates,
            orientation="h",
            marker=dict(color=wr_colors),
            text=[f"{w:.1f}% ({r}rt)" for w, r in zip(win_rates, roundtrips)],
            textposition="outside",
            hovertemplate="%{y}: %{x:.1f}% win rate<extra></extra>",
            name="승률 %",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    # Breakeven line at 35.5%
    fig.add_vline(
        x=35.5,
        line=dict(color="#f59e0b", dash="dash", width=1.5),
        row=1,
        col=2,
        annotation_text="breakeven 35.5%",
        annotation_position="top right",
        annotation_font=dict(size=10, color="#f59e0b"),
    )

    fig.update_layout(
        height=max(220, 50 * len(syms) + 100),
        margin=dict(l=20, r=100, t=50, b=20),
        font=dict(
            family="system-ui, -apple-system, Pretendard, 'Noto Sans KR', sans-serif",
            size=11,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
    fig.update_yaxes(showgrid=False)

    return fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        div_id="chart-comparison",
        config={"responsive": True},
    )


def _build_sym_figure(sym_data: dict, sym_trace: dict, sym: str, starting_cash: float) -> go.Figure:
    """3-row chart (price+trades, equity, drawdown) for a single symbol."""
    report_proxy = {
        "starting_cash": starting_cash,
        "return_pct": sym_data.get("return_pct", 0),
        "total_pnl": sym_data.get("return_pct", 0) / 100 * starting_cash,
    }
    return _build_figure(report_proxy, sym_trace)


_PER_SYMBOL_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Noto Sans KR', system-ui, sans-serif;
    background: #fafafa;
    color: #111827;
    margin: 0;
    padding: 32px 24px 56px;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1280px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin: 0 0 6px; font-weight: 800; letter-spacing: -0.015em; }}
  .sub {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
  .sub code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
  .section-title {{
    font-size: 13px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #6b7280; margin: 24px 0 10px;
  }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 16px;
  }}
  .cards-agg {{
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }}
  @media (max-width: 900px) {{ .cards {{ grid-template-columns: repeat(3, 1fr); }} }}
  .card {{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 11px 14px;
    min-width: 0;
  }}
  .card .label {{
    color: #6b7280; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px;
  }}
  .card .value {{
    font-size: 16px; font-weight: 700; color: #1a1a1a;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .chart-wrap {{
    background: white; border: 1px solid #e5e7eb;
    border-radius: 12px; padding: 10px; margin-bottom: 16px;
  }}
  /* Tabs */
  .tab-bar {{
    display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px;
  }}
  .tab-btn {{
    padding: 7px 18px; border: 1px solid #e5e7eb; border-radius: 8px;
    cursor: pointer; font-size: 13px; font-weight: 600; background: white;
    color: #374151; font-family: inherit; transition: all 0.12s;
  }}
  .tab-btn:hover {{ background: #f3f4f6; }}
  .tab-btn.active {{ background: #2563eb; color: white; border-color: #2563eb; }}
  .tab-panel {{ }}
  /* Spec footer */
  .meta {{ margin-top: 24px; color: #6b7280; font-size: 12px; }}
  .meta details summary {{
    cursor: pointer; font-weight: 600; color: #374151; padding: 6px 0;
  }}
  .meta pre {{
    background: #1e293b; color: #e2e8f0; padding: 14px;
    border-radius: 8px; font-size: 12px; overflow-x: auto; line-height: 1.5;
    margin-bottom: 0;
  }}
  .spec-section {{ margin-top: 18px; border-top: 1px solid #334155; padding-top: 14px; }}
  .spec-section-title {{
    font-size: 10.5px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: #94a3b8; margin-bottom: 8px;
  }}
  .spec-section p {{
    color: #cbd5e1; line-height: 1.7; font-size: 12.5px; margin: 0; white-space: pre-wrap;
  }}
  .spec-table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  .spec-table th {{
    text-align: left; color: #64748b; font-weight: 600;
    padding: 3px 10px; border-bottom: 1px solid #334155;
  }}
  .spec-table td {{ padding: 4px 10px; border-bottom: 1px solid #1e3a5f33; vertical-align: top; }}
  .pk {{ color: #7dd3fc; font-family: 'Menlo','Consolas',monospace; white-space: nowrap; width: 34%; }}
  .pv {{ color: #e2e8f0; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="sub">
    strategy <code>{strat_id}</code> ·
    {n_traded} symbols traded · {n_skipped} skipped ·
    {total_roundtrips} total roundtrips
  </div>

  <div class="section-title">Aggregate</div>
  <div class="cards cards-agg">{agg_cards}</div>
  <div class="chart-wrap">{comparison_chart}</div>

  <div class="section-title">Per-symbol detail</div>
  <div class="tab-bar">{tab_buttons}</div>
  {tab_panels}

  <div class="meta">
    <details>
      <summary>spec.yaml</summary>
      <pre>{spec_escaped}</pre>
      {spec_description}
    </details>
  </div>
</div>
<script>
  // Render all tab panels visible so Plotly initialises correctly,
  // then hide non-active ones after page load.
  window.addEventListener('load', function () {{
    document.querySelectorAll('.tab-panel').forEach(function (p) {{
      if (!p.classList.contains('active')) p.style.display = 'none';
    }});
  }});
  function showTab(sym, btn) {{
    document.querySelectorAll('.tab-panel').forEach(function (p) {{
      p.style.display = 'none';
    }});
    document.querySelectorAll('.tab-btn').forEach(function (b) {{
      b.classList.remove('active');
    }});
    document.getElementById('tab-' + sym).style.display = 'block';
    btn.classList.add('active');
    window.dispatchEvent(new Event('resize'));
  }}
</script>
</body>
</html>
"""


def render_per_symbol(strategy_dir: Path) -> Path:
    """Render a tabbed multi-symbol HTML report from report_per_symbol.json.

    Reads:
        report_per_symbol.json  — aggregate + per-symbol metrics
        trace_per_symbol.json   — equity curves, mid series, fills per symbol
        spec.yaml               — strategy spec (shown in footer)

    Writes:
        report_per_symbol.html

    Layout:
        - Aggregate metric cards + comparison bar chart (return % and win rate per symbol)
        - Tab per symbol: metric cards + 3-row Plotly chart (price, equity, drawdown)
    """
    agg = json.loads((strategy_dir / "report_per_symbol.json").read_text())
    trace_path = strategy_dir / "trace_per_symbol.json"
    per_traces = json.loads(trace_path.read_text()) if trace_path.exists() else {}
    spec_text = (strategy_dir / "spec.yaml").read_text()
    spec = yaml.safe_load(spec_text) or {}

    per_symbol = agg.get("per_symbol", {})
    starting_cash = float(agg.get("starting_cash", 10_000_000))

    # --- Aggregate cards ---
    avg_ret = agg.get("avg_return_pct", 0)
    avg_ret_color = "#16a34a" if avg_ret >= 0 else "#dc2626"
    agg_card_data = [
        ("평균 수익률", f'<span style="color:{avg_ret_color}">{avg_ret:+.4f}%</span>'),
        ("통합 승률", f'{agg.get("pooled_win_rate_pct", 0):.1f}%'),
        ("총 라운드트립", str(agg.get("total_roundtrips", 0))),
        ("총 수수료", f'{agg.get("total_fees", 0):,.0f}'),
        ("거래 종목", f'{agg.get("n_symbols_traded", 0)} / {agg.get("n_symbols_traded", 0) + agg.get("n_symbols_skipped", 0)}'),
    ]
    agg_cards_html = "".join(
        f'<div class="card"><div class="label">{label}</div>'
        f'<div class="value" style="font-size:15px">{val}</div></div>'
        for label, val in agg_card_data
    )

    # --- Comparison chart (Plotly CDN already included in <head>) ---
    comparison_html = _build_comparison_chart(per_symbol, starting_cash)

    # --- Per-symbol tabs ---
    symbols = list(per_symbol.keys())
    tab_buttons_parts: list[str] = []
    tab_panels_parts: list[str] = []

    for i, sym in enumerate(symbols):
        is_first = i == 0
        active_cls = "active" if is_first else ""

        tab_buttons_parts.append(
            f'<button class="tab-btn {active_cls}" onclick="showTab(\'{sym}\', this)">{sym}</button>'
        )

        sym_data = per_symbol[sym]
        sym_trace = per_traces.get(sym, {})
        cards_html = _sym_metric_cards(sym_data)

        fig = _build_sym_figure(sym_data, sym_trace, sym, starting_cash)
        chart_html = fig.to_html(
            include_plotlyjs=False,
            full_html=False,
            div_id=f"chart-{sym}",
            config={"responsive": True},
        )

        ret = sym_data.get("return_pct", 0)
        ret_color = "#16a34a" if ret >= 0 else "#dc2626"
        tab_panels_parts.append(
            f'<div id="tab-{sym}" class="tab-panel {active_cls}">'
            f'<div style="font-size:14px;font-weight:700;color:{ret_color};margin-bottom:10px;">'
            f'{sym} &nbsp; {ret:+.4f}%</div>'
            f'<div class="cards">{cards_html}</div>'
            f'<div class="chart-wrap">{chart_html}</div>'
            f'</div>'
        )

    out = strategy_dir / "report_per_symbol.html"
    out.write_text(
        _PER_SYMBOL_HTML.format(
            title=agg.get("spec_name", strategy_dir.name),
            strat_id=strategy_dir.name,
            n_traded=agg.get("n_symbols_traded", 0),
            n_skipped=agg.get("n_symbols_skipped", 0),
            total_roundtrips=agg.get("total_roundtrips", 0),
            agg_cards=agg_cards_html,
            comparison_chart=comparison_html,
            tab_buttons="".join(tab_buttons_parts),
            tab_panels="\n".join(tab_panels_parts),
            spec_escaped=spec_text.replace("<", "&lt;").replace(">", "&gt;"),
            spec_description=_spec_description_html(spec),
        )
    )
    return out


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m engine.report_html <strategy_id>", file=sys.stderr)
        sys.exit(2)
    root = Path(__file__).resolve().parent.parent
    strategy_dir = root / "strategies" / sys.argv[1]
    if not strategy_dir.exists():
        print(f"not found: {strategy_dir}", file=sys.stderr)
        sys.exit(1)
    out = render(strategy_dir)
    print(str(out.relative_to(root)))


if __name__ == "__main__":
    main()
