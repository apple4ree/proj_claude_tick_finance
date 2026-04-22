"""Chain 1 iteration report generator — Plotly HTML.

Given an iteration directory at `iterations/iter_<NNN>/`, produces
`report.html`: self-contained single-file document summarising every
SignalSpec in the iteration.

Contents:
  1. 요약 KPI 테이블 — 각 spec의 WR, expectancy, n_trades, 등
  2. WR 비교 바 차트
  3. 누적 PnL 곡선 (trace 기반)
  4. Win/Loss 시간축 히스토그램 (하루 중 언제 이기는지)
  5. Signal value 분포 히스토그램
  6. 각 spec에 대한 한국어 해석 (feedback + mutation_note + rec direction)

Reads:
  specs/*.json               — SignalSpec
  evaluations/*.json         — SpecEvaluation (optional)
  fidelity/*.json            — FidelityReport (optional)
  results/*.json             — BacktestResult
  feedback/*.json            — Feedback (for 한국어 해석)
  traces/*.trace.json        — per-trade log (enables charts)
  improvements/*.json        — ImprovementProposal (optional)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

REPO_ROOT = Path(__file__).resolve().parent.parent
ITERATIONS_ROOT = REPO_ROOT / "iterations"


# ---------------------------------------------------------------------------
# Artifact readers
# ---------------------------------------------------------------------------


def _read_json_dir(d: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        stem = p.stem.replace(".trace", "")
        try:
            out[stem] = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            out[stem] = {"__read_error__": True, "path": str(p)}
    return out


def load_iteration(iter_idx: int) -> dict[str, Any]:
    iter_dir = ITERATIONS_ROOT / f"iter_{iter_idx:03d}"
    if not iter_dir.is_dir():
        raise FileNotFoundError(iter_dir)
    chain2_gate = None
    gate_path = iter_dir / "chain2_gate.json"
    if gate_path.exists():
        try:
            chain2_gate = json.loads(gate_path.read_text())
        except Exception:  # noqa: BLE001
            chain2_gate = None
    return {
        "iter_idx": iter_idx,
        "iter_dir": iter_dir,
        "specs": _read_json_dir(iter_dir / "specs"),
        "evaluations": _read_json_dir(iter_dir / "evaluations"),
        "fidelity": _read_json_dir(iter_dir / "fidelity"),
        "results": _read_json_dir(iter_dir / "results"),
        "feedback": _read_json_dir(iter_dir / "feedback"),
        "traces": _read_json_dir(iter_dir / "traces"),
        "improvements": _read_json_dir(iter_dir / "improvements"),
        "chain2_gate": chain2_gate,
    }


# ---------------------------------------------------------------------------
# Korean interpretation synthesizer
# ---------------------------------------------------------------------------


DIRECTION_NAMES_KR = {
    "tighten_threshold":       "임계값 강화",
    "loosen_threshold":         "임계값 완화",
    "add_filter":              "필터 추가",
    "drop_feature":            "특성 제거",
    "swap_feature":            "특성 교체",
    "change_horizon":          "예측 horizon 변경",
    "combine_with_other_spec": "다른 spec과 결합",
    "retire":                  "퇴역",
}


def interpret_spec_korean(
    spec: dict, result: dict | None, feedback: dict | None, fidelity: dict | None
) -> str:
    """Compose a 한국어 narrative summary for one spec."""
    lines: list[str] = []

    # 공식 해석
    formula = spec.get("formula", "(?)")
    threshold = spec.get("threshold", "?")
    horizon = spec.get("prediction_horizon_ticks", "?")
    direction = spec.get("direction", "long_if_pos")
    dir_kr = "양수일 때 매수 (상승 예측)" if direction == "long_if_pos" else "음수일 때 매수 (역발상)"
    lines.append(
        f"**공식**: `{formula}` — 이 값이 임계값 **{threshold}** 을 넘으면 {dir_kr}, "
        f"**{horizon} tick** 뒤까지의 mid 이동 방향을 예측."
    )

    # 가설
    hyp = spec.get("hypothesis", "(없음)")
    lines.append(f"**가설**: {hyp}")

    # 결과
    if result is not None:
        wr = result.get("aggregate_wr")
        exp = result.get("aggregate_expectancy_bps")
        n = result.get("aggregate_n_trades")
        if wr is not None:
            wr_pct = wr * 100
            judgement = (
                "통계적으로 방향 예측력이 매우 강함" if wr >= 0.90
                else "방향 예측력 있음" if wr >= 0.55
                else "noise 범위" if 0.45 <= wr <= 0.55
                else "역방향 예측 (부호 반전 고려)"
            )
            lines.append(
                f"**실측**: {n}회 거래에서 승률 **{wr_pct:.2f}%**, 평균 기대 수익 **{exp:+.3f} bps**. "
                f"해석: {judgement}."
            )

    # Feedback
    if feedback is not None:
        rec = feedback.get("recommended_next_direction")
        rec_reason = feedback.get("recommended_direction_reasoning", "")
        cross = feedback.get("cross_symbol_consistency", "not_applicable")
        cross_kr = {
            "consistent": "여러 심볼 간 일관",
            "mixed": "심볼별 편차 있음",
            "inconsistent": "심볼별 모순",
            "not_applicable": "단일 심볼 (비교 불가)",
        }.get(cross, cross)
        lines.append(f"**Cross-symbol**: {cross_kr}")
        if rec:
            rec_kr = DIRECTION_NAMES_KR.get(rec, rec)
            lines.append(f"**다음 개선 방향**: {rec_kr} — {rec_reason}")

    # Fidelity
    if fidelity is not None:
        passed = fidelity.get("overall_passed", False)
        status = "통과" if passed else "실패"
        lines.append(f"**Fidelity gate**: {status}")

    # Strengths / Weaknesses
    if feedback is not None:
        strengths = feedback.get("strengths", [])
        weaknesses = feedback.get("weaknesses", [])
        if strengths:
            lines.append("**강점**:\n" + "\n".join(f"- {s}" for s in strengths))
        if weaknesses:
            lines.append("**약점**:\n" + "\n".join(f"- {w}" for w in weaknesses))

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Plotly figures
# ---------------------------------------------------------------------------


def fig_wr_comparison(results: dict[str, dict]) -> go.Figure:
    spec_ids = list(results.keys())
    wrs = [r.get("aggregate_wr", 0.0) * 100 for r in results.values()]
    exps = [r.get("aggregate_expectancy_bps", 0.0) for r in results.values()]
    ns = [r.get("aggregate_n_trades", 0) for r in results.values()]

    fig = make_subplots(
        rows=1, cols=3, subplot_titles=("승률 (%)", "기대수익 (bps/trade)", "거래 수 (n)"),
    )
    fig.add_trace(go.Bar(x=spec_ids, y=wrs, marker_color="#2ecc71", name="WR (%)"), row=1, col=1)
    fig.add_trace(go.Bar(x=spec_ids, y=exps, marker_color="#3498db", name="exp (bps)"), row=1, col=2)
    fig.add_trace(go.Bar(x=spec_ids, y=ns, marker_color="#f39c12", name="n_trades"), row=1, col=3)
    fig.update_layout(height=400, showlegend=False, title_text="Spec별 성과 비교")
    fig.update_xaxes(tickangle=-30)
    fig.add_hline(y=50, line_dash="dash", line_color="red", row=1, col=1)
    return fig


def fig_cumulative_pnl(traces: dict[str, dict]) -> go.Figure | None:
    """Plot cumulative PnL over time for each spec (sorted by tick_idx)."""
    fig = go.Figure()
    any_data = False
    for spec_id, trace in traces.items():
        records = trace.get("records", [])
        if not records:
            continue
        records_sorted = sorted(records, key=lambda r: (r.get("ts_ns") or 0))
        xs = list(range(len(records_sorted)))
        cum = 0.0
        cums = []
        for r in records_sorted:
            cum += float(r.get("signed_bps", 0.0))
            cums.append(cum)
        fig.add_trace(go.Scatter(x=xs, y=cums, mode="lines", name=spec_id))
        any_data = True
    if not any_data:
        return None
    fig.update_layout(
        title_text="누적 PnL (bps) — 거래 순서 기준",
        xaxis_title="거래 인덱스",
        yaxis_title="누적 수익 (bps)",
        height=400,
    )
    return fig


def fig_winloss_timeline(traces: dict[str, dict]) -> go.Figure | None:
    """Scatter of (tick_idx, signed_bps) colored by win/loss, one subplot per spec."""
    if not traces:
        return None
    ids = list(traces.keys())
    rows = len(ids)
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        subplot_titles=[f"{sid}" for sid in ids],
        vertical_spacing=0.05,
    )
    for i, sid in enumerate(ids):
        records = traces[sid].get("records", [])
        if not records:
            continue
        ts = [r.get("ts_ns", 0) for r in records]
        signed = [float(r.get("signed_bps", 0.0)) for r in records]
        colors = ["#27ae60" if s > 0 else "#c0392b" for s in signed]
        fig.add_trace(
            go.Scatter(
                x=ts, y=signed, mode="markers",
                marker=dict(size=4, color=colors),
                name=sid, showlegend=False,
            ),
            row=i + 1, col=1,
        )
    fig.update_layout(
        title_text="거래별 손익 — 시간축 (녹색=승, 적색=패)",
        height=200 + 150 * rows,
    )
    fig.update_xaxes(title_text="ts_ns", row=rows, col=1)
    return fig


def _load_mid_series(symbol: str, date: str, downsample: int = 20) -> tuple[list[int], list[float]]:
    """Load mid timeseries for (symbol, date) from KRX CSV, optionally downsampled.

    Returns (ts_ns_list, mid_list). Empty lists on failure.
    """
    try:
        from chain1.backtest_runner import load_day  # noqa: WPS433
    except Exception:  # noqa: BLE001
        return [], []
    try:
        df = load_day(symbol, date)
    except Exception:  # noqa: BLE001
        return [], []
    if df.empty:
        return [], []
    import pandas as _pd
    ts = _pd.to_datetime(df["recv_ts_kst"], utc=False).astype("int64").to_numpy()
    mid = (df["BIDP1"].to_numpy(dtype="float64") + df["ASKP1"].to_numpy(dtype="float64")) / 2.0
    if downsample > 1:
        ts = ts[::downsample]
        mid = mid[::downsample]
    return ts.tolist(), mid.tolist()


def fig_price_with_trades(traces: dict[str, dict]) -> go.Figure | None:
    """Baseline mid timeseries + entry markers colored by win/loss per spec.

    For each unique (symbol, date) combination seen in the traces, loads the
    mid series from KRX CSV (downsampled ~20×) and overlays each spec's
    entry points. Hovering shows full context (signal_value, delta_bps, etc.).
    """
    if not traces:
        return None

    # Collect unique (symbol, date) pairs across all specs
    pairs: set[tuple[str, str]] = set()
    for trace in traces.values():
        for r in trace.get("records", []):
            sym = r.get("symbol")
            date = r.get("date")
            if sym and date:
                pairs.add((sym, date))
    if not pairs:
        return None

    # One subplot per (symbol, date); shared x for same symbol simplifies
    # but different dates can have very different ranges — give each its own row
    pairs_sorted = sorted(pairs)
    fig = make_subplots(
        rows=len(pairs_sorted), cols=1,
        subplot_titles=[f"{sym} {date}" for sym, date in pairs_sorted],
        vertical_spacing=0.08,
    )

    # Color palette for specs (cycles if many)
    palette = [
        "#2980b9", "#8e44ad", "#d35400", "#16a085", "#c0392b",
        "#2c3e50", "#7f8c8d", "#27ae60", "#e67e22", "#9b59b6",
    ]
    spec_colors = {sid: palette[i % len(palette)] for i, sid in enumerate(traces.keys())}

    for row_idx, (sym, date) in enumerate(pairs_sorted, start=1):
        # Baseline mid
        ts, mid = _load_mid_series(sym, date)
        if ts:
            fig.add_trace(
                go.Scattergl(
                    x=ts, y=mid, mode="lines",
                    line=dict(color="rgba(100,100,100,0.8)", width=1),
                    name=f"mid {sym}",
                    legendgroup=f"mid_{sym}_{date}",
                    hovertemplate="ts=%{x}<br>mid=%{y:,.0f}<extra></extra>",
                ),
                row=row_idx, col=1,
            )

        # Trade markers per spec
        for spec_id, trace in traces.items():
            records = [r for r in trace.get("records", [])
                       if r.get("symbol") == sym and r.get("date") == date]
            if not records:
                continue
            wins = [r for r in records if float(r.get("signed_bps", 0)) > 0]
            losses = [r for r in records if float(r.get("signed_bps", 0)) < 0]

            base_color = spec_colors[spec_id]

            def _pack(recs, win_flag: bool):
                xs, ys, texts = [], [], []
                for r in recs:
                    xs.append(r.get("ts_ns"))
                    ys.append(r.get("mid_t"))
                    texts.append(
                        f"spec: {spec_id}<br>"
                        f"tick: {r.get('tick_idx')}<br>"
                        f"signal: {r.get('signal_value'):.4f}<br>"
                        f"dir: {'+1 (long)' if r.get('predicted_dir')==1 else '-1 (short)'}<br>"
                        f"mid_entry: {r.get('mid_t'):,.0f}<br>"
                        f"mid_exit: {r.get('mid_th'):,.0f}<br>"
                        f"Δmid: {r.get('delta_bps'):+.2f} bps<br>"
                        f"signed: {r.get('signed_bps'):+.2f} bps"
                    )
                return xs, ys, texts

            wx, wy, wt = _pack(wins, True)
            if wx:
                fig.add_trace(
                    go.Scattergl(
                        x=wx, y=wy, mode="markers",
                        marker=dict(color="#27ae60", size=7, symbol="triangle-up",
                                    line=dict(color=base_color, width=1)),
                        name=f"{spec_id} win ({len(wx)})",
                        legendgroup=spec_id,
                        text=wt, hoverinfo="text",
                    ),
                    row=row_idx, col=1,
                )
            lx, ly, lt = _pack(losses, False)
            if lx:
                fig.add_trace(
                    go.Scattergl(
                        x=lx, y=ly, mode="markers",
                        marker=dict(color="#c0392b", size=7, symbol="triangle-down",
                                    line=dict(color=base_color, width=1)),
                        name=f"{spec_id} loss ({len(lx)})",
                        legendgroup=spec_id,
                        text=lt, hoverinfo="text",
                    ),
                    row=row_idx, col=1,
                )

    fig.update_layout(
        title_text="실제 주가 + Spec별 진입/청산 (interactive — legend 클릭해서 spec 토글)",
        height=350 + 400 * len(pairs_sorted),
        hovermode="closest",
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
    )
    for i in range(1, len(pairs_sorted) + 1):
        fig.update_xaxes(title_text="ts_ns", row=i, col=1)
        fig.update_yaxes(title_text="mid (KRW)", row=i, col=1)
    return fig


def fig_signal_distribution(traces: dict[str, dict]) -> go.Figure | None:
    fig = go.Figure()
    any_data = False
    for spec_id, trace in traces.items():
        records = trace.get("records", [])
        if not records:
            continue
        sigs = [float(r.get("signal_value", 0.0)) for r in records if r.get("signal_value") is not None]
        if not sigs:
            continue
        fig.add_trace(go.Histogram(x=sigs, name=spec_id, opacity=0.55, nbinsx=50))
        any_data = True
    if not any_data:
        return None
    fig.update_layout(
        barmode="overlay",
        title_text="Signal value 분포 (거래 시점)",
        xaxis_title="signal_value",
        yaxis_title="거래 건수",
        height=350,
    )
    return fig


# ---------------------------------------------------------------------------
# HTML composition
# ---------------------------------------------------------------------------


_HTML_SHELL = """<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8" />
<title>Chain 1 Iteration {iter_idx:03d} — Report</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  body {{ font-family: -apple-system, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
         max-width: 1200px; margin: 2em auto; padding: 1em; background: #fafafa; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ border-bottom: 2px solid #0b6623; padding-bottom: 0.3em; }}
  h2 {{ color: #0b6623; border-bottom: 1px solid #d0d0d0; margin-top: 2em; }}
  h3 {{ margin-top: 1.5em; }}
  .kpi {{ background: #fff; border: 1px solid #d0d0d0; padding: 1em; margin: 1em 0; border-radius: 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.93em; }}
  th, td {{ border: 1px solid #d0d0d0; padding: 0.4em 0.7em; text-align: left; }}
  th {{ background: #ececec; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .spec-block {{ background: #fff; border-left: 4px solid #0b6623; margin: 1em 0; padding: 1em 1.3em; border-radius: 4px; }}
  code {{ background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; }}
  .muted {{ color: #6b6b6b; font-size: 0.88em; }}
  .plot-container {{ margin: 1em 0; }}
  hr {{ border: none; border-top: 1px dashed #d0d0d0; margin: 2em 0; }}
</style>
</head><body>

<h1>Chain 1 — Iteration {iter_idx:03d} 리포트</h1>
<p class="muted">생성 시각: {generated_at}</p>

<h2>📊 KPI 요약</h2>
<div class="kpi">
{kpi_table}
</div>

<h2>📈 Spec 비교 차트</h2>
<div class="plot-container">{fig_wr_html}</div>

<h2>💹 실제 주가 + 진입/청산 시각화</h2>
<p class="muted">각 spec 의 진입 시점을 실제 mid 가격 그래프 위에 overlay.
  녹색 ▲ = Win (예측 방향 맞음), 적색 ▼ = Loss. 마커에 마우스 올리면 signal value / Δmid 등 상세 확인.
  범례(legend) 에서 spec 이름 클릭으로 on/off 토글.
</p>
<div class="plot-container">{fig_price_html}</div>

<h2>📉 누적 PnL (거래 순서 기준)</h2>
<div class="plot-container">{fig_cumpnl_html}</div>

<h2>⏱ 거래별 손익 — 시간축</h2>
<div class="plot-container">{fig_timeline_html}</div>

<h2>📊 Signal value 분포</h2>
<div class="plot-container">{fig_dist_html}</div>

<h2>🚀 Chain 2 후보 게이트</h2>
{chain2_gate_html}

<h2>🔍 Spec별 한국어 해석</h2>
{per_spec_blocks}

<hr />
<p class="muted">Chain 1 Signal 체인 iteration 리포트.
실제 수익 측정은 Chain 2 (execution 레이어) 에서 수수료·스프레드 반영 후 재계산됩니다.</p>

</body></html>
"""


def _kpi_table(iter_data: dict) -> str:
    rows = []
    rows.append(
        "<tr><th>Spec ID</th><th>Formula</th><th>Threshold</th><th>Horizon</th>"
        "<th>WR (%)</th><th>Exp (bps)</th><th>n_trades</th><th>Fidelity</th>"
        "<th>Next 추천</th></tr>"
    )
    for sid, spec in iter_data["specs"].items():
        result = iter_data["results"].get(sid, {})
        fidelity = iter_data["fidelity"].get(sid, {})
        feedback = iter_data["feedback"].get(sid, {})
        wr = result.get("aggregate_wr")
        exp = result.get("aggregate_expectancy_bps")
        n = result.get("aggregate_n_trades")
        fid_ok = fidelity.get("overall_passed", False)
        rec = feedback.get("recommended_next_direction", "—")
        rec_kr = DIRECTION_NAMES_KR.get(rec, rec)
        wr_cell = f"{wr*100:.2f}" if wr is not None else "—"
        exp_cell = f"{exp:+.3f}" if exp is not None else "—"
        n_cell = str(n) if n is not None else "—"
        rows.append(
            f"<tr><td><code>{sid}</code></td>"
            f"<td><code>{spec.get('formula', '?')}</code></td>"
            f"<td class='num'>{spec.get('threshold', '?')}</td>"
            f"<td class='num'>{spec.get('prediction_horizon_ticks', '?')}</td>"
            f"<td class='num'>{wr_cell}</td>"
            f"<td class='num'>{exp_cell}</td>"
            f"<td class='num'>{n_cell}</td>"
            f"<td>{'✅' if fid_ok else '—'}</td>"
            f"<td>{rec_kr}</td></tr>"
        )
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def _chain2_gate_html(iter_data: dict) -> str:
    """Render the Chain 2 promotion gate section."""
    g = iter_data.get("chain2_gate")
    if not g:
        return "<p class='muted'>(chain2-gate 실행 기록 없음)</p>"

    parts: list[str] = []
    parts.append(
        f"<p>총 valid spec <strong>{g.get('total_valid_specs', 0)}</strong>개 "
        f"· 스캔된 iteration {g.get('iterations_scanned', [])} · "
        f"Cross-scenario consensus: "
        f"{', '.join(g.get('cross_scenario_consensus') or ['(없음)'])}</p>"
    )

    for sc in g.get("scenarios", []):
        sid = sc.get("fee_scenario")
        rt = sc.get("fee_rt_bps")
        top = sc.get("top_candidates", [])
        parts.append(f"<h3>시나리오: <code>{sid}</code> (RT fee {rt} bps)</h3>")
        if not top:
            parts.append("<p class='muted'>이 시나리오에서 통과한 후보 없음.</p>")
        else:
            rows = [
                "<tr><th>우선순위</th><th>Score</th><th>Spec ID</th>"
                "<th>WR</th><th>Post-fee exp (bps)</th><th>Density/day/sym</th>"
                "<th>Filter?</th><th>Complexity</th></tr>"
            ]
            for c in top:
                pr = c.get("priority", "?")
                pr_kr = {"must_include": "🟢 필수", "strong": "🟡 강추", "marginal": "🟠 경계"}.get(pr, pr)
                rows.append(
                    f"<tr><td>{pr_kr}</td>"
                    f"<td class='num'>{c.get('score', 0):.4f}</td>"
                    f"<td><code>{c.get('spec_id','?')}</code></td>"
                    f"<td class='num'>{c.get('wr', 0):.4f}</td>"
                    f"<td class='num'>{c.get('expectancy_post_fee_bps', 0):+.3f}</td>"
                    f"<td class='num'>{c.get('trade_density_per_day_per_sym', 0):.0f}</td>"
                    f"<td>{'✅' if c.get('has_regime_self_filter') else '—'}</td>"
                    f"<td class='num'>{c.get('complexity_score', 0):.0f}</td></tr>"
                )
            parts.append("<table>" + "\n".join(rows) + "</table>")
            # Rationale + concerns per candidate
            for c in top:
                rat = (c.get("rationale_kr") or "").replace("\n", " ")
                concerns = c.get("expected_chain2_concerns", [])
                bullets = "".join(f"<li>{cc}</li>" for cc in concerns)
                parts.append(
                    f"<div class='spec-block'>"
                    f"<strong><code>{c.get('spec_id')}</code></strong>"
                    f"<p>{rat}</p>"
                    f"{'<p><em>Chain 2 우려 사항:</em></p><ul>' + bullets + '</ul>' if bullets else ''}"
                    f"</div>"
                )
        excl = sc.get("excluded", {})
        if excl:
            ex_items = "".join(
                f"<li><code>{sid}</code>: <span class='muted'>{reason[:120]}</span></li>"
                for sid, reason in excl.items()
            )
            parts.append(f"<details><summary>제외된 spec ({len(excl)}개)</summary><ul>{ex_items}</ul></details>")
    # Meta narrative
    meta = g.get("meta_narrative_kr")
    if meta:
        parts.append(
            "<h3>메타 요약</h3>"
            f"<div class='kpi'>{meta.replace(chr(10), '<br>')}</div>"
        )
    # Warnings
    warns = g.get("warnings", [])
    if warns:
        parts.append(
            "<h3>⚠️ 경고</h3><ul>"
            + "".join(f"<li>{w}</li>" for w in warns)
            + "</ul>"
        )

    return "\n".join(parts)


def _per_spec_html(iter_data: dict) -> str:
    blocks = []
    for sid, spec in iter_data["specs"].items():
        result = iter_data["results"].get(sid)
        feedback = iter_data["feedback"].get(sid)
        fidelity = iter_data["fidelity"].get(sid)
        text_md = interpret_spec_korean(spec, result, feedback, fidelity)
        # Naive markdown-to-html
        html_body = text_md.replace("\n\n", "</p><p>").replace("\n- ", "</p><p>• ")
        html_body = html_body.replace("**", "")
        html_body = f"<p>{html_body}</p>"
        blocks.append(f"<div class='spec-block'><h3>{sid}</h3>{html_body}</div>")
    return "\n".join(blocks)


def generate_iteration_report(iter_idx: int, output_path: Path | str | None = None) -> Path:
    iter_data = load_iteration(iter_idx)
    output_path = Path(output_path) if output_path else iter_data["iter_dir"] / "report.html"

    # Charts
    fig_wr = fig_wr_comparison(iter_data["results"])
    fig_price = fig_price_with_trades(iter_data["traces"])
    fig_cumpnl = fig_cumulative_pnl(iter_data["traces"])
    fig_timeline = fig_winloss_timeline(iter_data["traces"])
    fig_dist = fig_signal_distribution(iter_data["traces"])

    def _render(fig: go.Figure | None) -> str:
        if fig is None:
            return "<p class='muted'>(trace 데이터 없음)</p>"
        return fig.to_html(full_html=False, include_plotlyjs=False)

    html = _HTML_SHELL.format(
        iter_idx=iter_idx,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        kpi_table=_kpi_table(iter_data),
        fig_wr_html=_render(fig_wr),
        fig_price_html=_render(fig_price),
        fig_cumpnl_html=_render(fig_cumpnl),
        fig_timeline_html=_render(fig_timeline),
        fig_dist_html=_render(fig_dist),
        chain2_gate_html=_chain2_gate_html(iter_data),
        per_spec_blocks=_per_spec_html(iter_data),
    )

    output_path.write_text(html)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration-idx", type=int, required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = generate_iteration_report(args.iteration_idx, args.out)
    print(f"report → {out}")
