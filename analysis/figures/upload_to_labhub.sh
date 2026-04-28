#!/bin/bash
# 모든 figure 를 적합한 wiki entity / flow event 에 첨부.
# 매핑: figure → (entity_id 또는 event_id, title)
set -e

TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.config/labhub/token.json'))['token'])")
URL="https://labhub.damilab.cc"
SLUG="tick-agent"
FIG_DIR="/home/dgu/tick/proj_claude_tick_finance/analysis/figures"

upload_wiki() {
  local entity_id="$1"
  local figure="$2"
  local title="$3"
  echo "  WIKI $entity_id ← $figure"
  curl -fsS -X POST "$URL/api/projects/$SLUG/wiki-entities/$entity_id/attachments" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$FIG_DIR/$figure" \
    -F "title=$title" > /dev/null
}

upload_flow() {
  local event_id="$1"
  local figure="$2"
  local title="$3"
  echo "  FLOW event $event_id ← $figure"
  curl -fsS -X POST "$URL/api/flow-events/$event_id/attachments" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$FIG_DIR/$figure" \
    -F "title=$title" > /dev/null
}

echo "=== Wiki concept entities ==="

# project-overview: chain 1 architecture
upload_wiki project-overview fig_chain1_architecture.png "Chain 1 multi-agent pipeline"
upload_wiki project-overview fig_market_fee_comparison.png "RT fee by market"

# regime-state-paradigm: state machine + magnitude axes context
upload_wiki regime-state-paradigm fig_regime_state_machine.png "Regime-state state machine (FLAT ↔ LONG)"

# fee-binding-constraint: market fee comparison + holding period
upload_wiki fee-binding-constraint fig_market_fee_comparison.png "RT fee by market — KRX 23 bps stands out"
upload_wiki fee-binding-constraint fig_holding_period_economics.png "Holding period vs deployability under 23 bps fee"

# magnitude-axes-framework
upload_wiki magnitude-axes-framework fig_magnitude_axes.png "Magnitude 3-axis framework"

# holding-period-extension: √T scaling
upload_wiki holding-period-extension fig_sqrt_t_scaling.png "Random-walk √T scaling — KRX 005930"

# capped-post-fee: gross distribution
upload_wiki capped-post-fee fig_capped_post_fee.png "v3 specs gross distribution (capped vs deployable)"

# net-pnl-objective: keyword shift
upload_wiki net-pnl-objective fig_v3_v4_keyword_shift.png "v3 → v4 hypothesis keyword shift"

# reward-target-mismatch: shares same v3→v4 evidence
upload_wiki reward-target-mismatch fig_v3_v4_keyword_shift.png "Reward shaping → LLM hypothesis distribution shift"

# cite-but-fail
upload_wiki cite-but-fail fig_cite_but_fail.png "Category B3 (deep book extreme) only 67%"

# compositional-fragility
upload_wiki compositional-fragility fig_chain1_architecture.png "6-stage chain 1 pipeline (noise accumulation source)"
upload_wiki compositional-fragility fig_mutation_phases.png "Mutation random walk after iter 13 saturation"

# paradigm-twin
upload_wiki paradigm-twin fig_paradigm_twin_matrix.png "Paradigm twin comparison matrix"

# duty-cycle-target — partly covered by regime state machine
upload_wiki duty-cycle-target fig_regime_state_machine.png "Regime-state machine context for duty/mean_dur"

echo
echo "=== Wiki experiment entities ==="

# fresh-v3
upload_wiki fresh-v3-chain1-25iter-3sym-8date fig_v3_results.png "v3 fresh run gross distribution (n=80)"
upload_wiki fresh-v3-chain1-25iter-3sym-8date fig_capped_post_fee.png "v3 capped post-fee distribution"
upload_wiki fresh-v3-chain1-25iter-3sym-8date fig_mutation_phases.png "v3 mutation phases — saturation after iter 13"

# fresh-v4
upload_wiki fresh-v4-fix1-net-pnl-objective fig_v3_v4_keyword_shift.png "v3 → v4 hypothesis keyword shift"

# fresh-v5
upload_wiki fresh-v5-regime-state-paradigm fig_version_trajectory.png "Best gross trajectory v3 → v6"

# fresh-v6
upload_wiki fresh-v6-paths-a-b-c-d fig_version_trajectory.png "Best gross trajectory v3 → v6"
upload_wiki fresh-v6-paths-a-b-c-d fig_v5_v6_mean_dur.png "v5 vs v6 mean_dur distribution (Path D effect)"
upload_wiki fresh-v6-paths-a-b-c-d fig_fee_floor_reduction.png "Fee floor 23 → 14 in maker mode (Path B)"

# regime-state-paradigm-ablation
upload_wiki regime-state-paradigm-ablation fig_regime_state_machine.png "Regime-state machine"

echo
echo "=== Wiki note entities ==="

# hypothesis-vs-result-divergence-v3
upload_wiki hypothesis-vs-result-divergence-v3 fig_hypothesis_divergence.png "LLM estimated vs measured expectancy"

# mutation-random-walk-after-saturation
upload_wiki mutation-random-walk-after-saturation fig_mutation_phases.png "Mutation phases — early/mid/late"

# reward-shaping-llm-hypothesis-distribution
upload_wiki reward-shaping-llm-hypothesis-distribution fig_v3_v4_keyword_shift.png "Reward shaping effect on LLM keywords"

# tick-vs-daily-fee-economics
upload_wiki tick-vs-daily-fee-economics fig_holding_period_economics.png "Holding period vs deployability"
upload_wiki tick-vs-daily-fee-economics fig_sqrt_t_scaling.png "√T scaling reference"

# krx-spread-9bps-measured already has fig_fee_floor + fig_maker_effect via earlier uploads (but rerun)
upload_wiki krx-spread-9bps-measured fig_fee_floor_reduction.png "Fee floor change with measured 9 bps spread"

echo
echo "=== Wiki paper entities ==="

# stoikov-2018-microprice — no direct figure, skip
# cont-kukanov-stoikov-2014 — schematic of OFI not generated, skip
# lopez-de-prado-2014-deflated-sharpe — no fig
# alphaagent-2025 — paradigm twin matrix
upload_wiki alphaagent-2025 fig_paradigm_twin_matrix.png "Comparison vs other LLM-trading systems"
upload_wiki quantagent-2025 fig_paradigm_twin_matrix.png "Comparison vs other LLM-trading systems"
upload_wiki tradefm-2026 fig_paradigm_twin_matrix.png "Comparison vs other LLM-trading systems"
upload_wiki alphaforgebench-2026 fig_paradigm_twin_matrix.png "Comparison vs other LLM-trading systems"
upload_wiki hiremath-2026-microstructure-regimes fig_regime_state_machine.png "Our regime-state usage of latent regimes"

echo
echo "=== Flow events ==="

# event 199 (v3 results)
upload_flow 199 fig_v3_results.png "v3 fresh run gross distribution (n=80)"
upload_flow 199 fig_capped_post_fee.png "v3 capped post-fee distribution"

# event 208 (v4 early findings)
upload_flow 208 fig_v3_v4_keyword_shift.png "v3 → v4 hypothesis keyword shift"

# event 209 (v4 launch) — schematic
upload_flow 209 fig_chain1_architecture.png "Chain 1 multi-agent pipeline"

# event 210 (objective switch decision)
upload_flow 210 fig_v3_v4_keyword_shift.png "Effect of reward switch on hypothesis distribution"

# event 200 (v5 launch)
upload_flow 200 fig_regime_state_machine.png "New regime-state machine adopted"

# event 201 (paradigm redesign)
upload_flow 201 fig_regime_state_machine.png "Regime-state machine"

# event 202 (paper landscape)
upload_flow 202 fig_paradigm_twin_matrix.png "Paradigm twin comparison"

# event 203 (regime ablation results)
upload_flow 203 fig_regime_state_machine.png "Regime-state machine"

# event 204 (regime ablation start)
upload_flow 204 fig_regime_state_machine.png "Regime-state machine"

# event 205 (paradigm critique)
upload_flow 205 fig_holding_period_economics.png "Holding period vs deployability"

# event 206 (KRX-only scope)
upload_flow 206 fig_market_fee_comparison.png "Why KRX 23 bps is special"

# event 207 (Block F)
upload_flow 207 fig_magnitude_axes.png "Magnitude 3-axis framework"

# event 211/212/213 already had figures uploaded earlier

echo
echo "=== DONE ==="
