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
from plotly.subplots import make_subplots

_KST = timezone(timedelta(hours=9))


def _ts(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=_KST).isoformat()


def _metric_cards(report: dict) -> str:
    cards = [
        ("Return", f"{report.get('return_pct', 0):.3f}%"),
        ("Total PnL", f"{report.get('total_pnl', 0):,.0f}"),
        ("Sharpe (raw)", f"{report.get('sharpe_raw', 0):.3f}"),
        ("Sharpe (ann.)", f"{report.get('sharpe_annualized', 0):.3f}"),
        ("MDD", f"{report.get('mdd_pct', 0):.3f}%"),
        ("Trades", f"{report.get('n_trades', 0)}"),
        ("Roundtrips", f"{report.get('n_roundtrips', 0)}"),
        ("Win rate", f"{report.get('win_rate_pct', 0):.1f}%"),
        ("Avg trade", f"{report.get('avg_trade_pnl', 0):,.0f}"),
        ("Best trade", f"{report.get('best_trade', 0):,.0f}"),
        ("Worst trade", f"{report.get('worst_trade', 0):,.0f}"),
        ("Total fees", f"{report.get('total_fees', 0):,.0f}"),
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
        subplot_titles=("Price & Trades", "Equity", "Drawdown (%)"),
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
                name="Drawdown %",
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
  <div class="meta">
    <details>
      <summary>spec.yaml</summary>
      <pre>{spec_escaped}</pre>
    </details>
  </div>
</div>
</body>
</html>
"""


def render(strategy_dir: Path) -> Path:
    report = json.loads((strategy_dir / "report.json").read_text())
    trace_path = strategy_dir / "trace.json"
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else {}
    spec_text = (strategy_dir / "spec.yaml").read_text()

    fig = _build_figure(report, trace)
    chart_html = fig.to_html(
        include_plotlyjs="cdn", full_html=False, div_id="chart-root", config={"responsive": True}
    )

    html = _HTML_TEMPLATE.format(
        title=report.get("spec_name", strategy_dir.name),
        strat_id=strategy_dir.name,
        symbols=", ".join(report.get("symbols", [])) or "—",
        dates=", ".join(report.get("dates", [])) or "—",
        events=report.get("total_events", 0),
        duration=report.get("duration_sec", 0.0),
        cards=_metric_cards(report),
        chart=chart_html,
        spec_escaped=spec_text.replace("<", "&lt;").replace(">", "&gt;"),
    )

    out = strategy_dir / "report.html"
    out.write_text(html)
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
