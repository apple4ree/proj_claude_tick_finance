"""Chain 1 shared Pydantic schemas.

All 7 Chain 1 agents exchange data via these contracts. SignalSpec is the
primary artifact that flows through the workflow; the other models record
intermediate/terminal states of the iteration.

Usage from an agent-specific schema module:
    from .._shared.schemas import SignalSpec, BacktestResult, ...
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Meta / common fields
# ---------------------------------------------------------------------------

class HandoffBase(BaseModel):
    """Common metadata every inter-agent handoff carries."""

    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(..., description="Producing agent identifier")
    agent_version: str = Field("0.1.0")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    iteration_idx: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# SignalSpec — the primary artifact flowing through Chain 1
# ---------------------------------------------------------------------------

class Direction(str, Enum):
    LONG_IF_POS = "long_if_pos"  # signal > 0 → predict up (enter long)
    LONG_IF_NEG = "long_if_neg"  # signal < 0 → predict up (contrarian)


class SignalSpec(HandoffBase):
    """A concrete, implementable signal specification.

    Under Chain 1's execution=1 constraint the trading rule is fully determined
    by `formula`, `threshold`, `direction`, and `prediction_horizon_ticks`:
      1. Compute `signal_value = formula(snapshot)` each tick.
      2. If `signal_value > threshold`: predict UP (enter long if LONG_IF_POS,
         short if LONG_IF_NEG); symmetric for `< -threshold`.
      3. Exit after `prediction_horizon_ticks` (default 1, i.e. next tick).
    """

    # Identity
    spec_id: str = Field(..., description="Stable unique ID, e.g. 'iter003_obi1_gt_05'")
    name: str
    hypothesis: str = Field(..., min_length=20, description="Why this signal should work")

    # Signal formula
    formula: str = Field(
        ...,
        description=(
            "Human-readable expression of the signal, using the whitelisted "
            "primitives from cheat_sheets/obi_family_formulas.md (e.g., "
            "'obi_1 - 0.3 * obi_5' or 'microprice_dev_bps > 2 AND ofi_proxy > 0'). "
            "Must be deterministic given a book snapshot."
        ),
    )
    primitives_used: list[str] = Field(
        ...,
        min_length=1,
        description="Whitelist of primitives used: obi_k, ofi_proxy, microprice_dev_bps, vamp, spread_bps, etc.",
    )

    # Decision rule
    threshold: float = Field(..., description="Trigger value; sign handling in `direction`")
    direction: Direction = Field(Direction.LONG_IF_POS)
    prediction_horizon_ticks: int = Field(1, ge=1, le=20000)

    # References (evidence-based principle)
    references: list[str] = Field(
        default_factory=list,
        description="Relative paths to consulted reference files under _shared/ or agent-local references/",
    )

    # Lineage
    parent_spec_id: str | None = Field(None, description="If derived from a prior spec (Chain 1 iteration)")
    mutation_note: str | None = None

    # Measured (filled in by backtest-runner / feedback-analyst; None until then)
    measured_wr: float | None = Field(None, ge=0.0, le=1.0)
    measured_expectancy_bps: float | None = None
    measured_n_trades: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def _check_threshold_semantics(self) -> SignalSpec:
        if self.threshold < 0:
            raise ValueError("threshold must be non-negative; direction encodes sign")
        return self


# ---------------------------------------------------------------------------
# Evaluation of the spec itself (pre-code)
# ---------------------------------------------------------------------------

class SpecEvaluation(HandoffBase):
    """Output of signal-evaluator (stage ②)."""

    spec_id: str
    valid: bool
    concerns: list[str] = Field(default_factory=list)
    duplicate_of: str | None = Field(None, description="spec_id of a prior identical/near-identical spec, if any")
    expected_merit: Literal["high", "medium", "low", "unknown"] = "unknown"
    reasoning: str = Field(..., min_length=20)


# ---------------------------------------------------------------------------
# Code output
# ---------------------------------------------------------------------------

class GeneratedCode(HandoffBase):
    """Output of code-generator (stage ②.5)."""

    spec_id: str
    code_path: str = Field(..., description="Path to generated Python file")
    entry_function: str = Field("signal", description="Callable name inside code_path")
    template_used: str = Field(..., description="Which rendering template was used")


# ---------------------------------------------------------------------------
# Fidelity report
# ---------------------------------------------------------------------------

class FidelityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    passed: bool
    detail: str = ""


class FidelityReport(HandoffBase):
    """Output of fidelity-checker (stage ②.75)."""

    spec_id: str
    overall_passed: bool
    checks: list[FidelityCheck]

    @model_validator(mode="after")
    def _consistent(self) -> FidelityReport:
        if self.overall_passed != all(c.passed for c in self.checks):
            raise ValueError("overall_passed must equal AND of all check results")
        return self


# ---------------------------------------------------------------------------
# Backtest result
# ---------------------------------------------------------------------------

class HorizonPoint(BaseModel):
    """Per-horizon metric point — one row of a horizon sweep curve.

    Same signal/threshold/direction as the parent spec; only the exit
    horizon (ticks lookahead) differs. Populated in a single backtest
    pass when `horizon_grid` is provided to run_backtest.
    """
    model_config = ConfigDict(extra="forbid")
    horizon: int = Field(..., ge=1)
    n_trades: int = Field(..., ge=0)
    n_wins: int = Field(..., ge=0)
    n_losses: int = Field(..., ge=0)
    wr: float = Field(..., ge=0.0, le=1.0)
    sum_win_bps: float = Field(..., ge=0.0)
    sum_loss_bps: float = Field(..., ge=0.0)
    expectancy_bps: float


class PerSymbolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    date: str
    n_ticks: int
    n_trades: int
    n_wins: int
    n_losses: int
    wr: float
    sum_win_bps: float
    sum_loss_bps: float
    expectancy_bps: float
    horizon_curve: list[HorizonPoint] = Field(
        default_factory=list,
        description="Optional multi-horizon sweep at this (symbol, date). Empty unless horizon_grid is passed.",
    )
    # Regime-state mode metrics (2026-04-27, paradigm shift from fixed-H to signal-driven)
    # Only populated when backtest_mode == "regime_state". Optional to preserve back-compat.
    n_regimes: int | None = Field(None, description="Number of (entry, exit) regime trades in this session.")
    signal_duty_cycle: float | None = Field(
        None, description="Fraction of ticks within session where signal evaluated True (in_position duty)."
    )
    mean_duration_ticks: float | None = Field(
        None, description="Mean holding duration per regime, in ticks."
    )
    # Maker spread capture metrics (2026-04-27, Path B). Only populated when
    # execution_mode in {"maker_optimistic", "maker_realistic"}.
    execution_mode: str | None = Field(
        None, description="'mid_to_mid' (default) | 'maker_optimistic' | 'maker_realistic'."
    )
    expectancy_maker_bps: float | None = Field(
        None, description="Mean per-regime gross under maker_optimistic execution (entry at touch, exit at touch).",
    )
    avg_spread_at_entry_bps: float | None = Field(
        None, description="Mean (ASK - BID) / mid * 1e4 measured at regime entry tick.",
    )
    avg_spread_at_exit_bps: float | None = Field(
        None, description="Mean (ASK - BID) / mid * 1e4 measured at regime exit tick.",
    )


class BacktestResult(HandoffBase):
    """Output of backtest-runner (stage ③). Execution=1 assumed."""

    spec_id: str
    per_symbol: list[PerSymbolResult]
    aggregate_n_trades: int
    aggregate_wr: float
    aggregate_expectancy_bps: float
    trace_path: str | None = Field(None, description="Optional path to per-trade log (.parquet/.npz)")
    horizon_curve: list[HorizonPoint] = Field(
        default_factory=list,
        description="Aggregated (across symbols × dates) horizon sweep. Empty unless horizon_grid was passed.",
    )
    # Backtest paradigm mode (2026-04-27).
    # - "fixed_h"      : legacy fixed-horizon (entry every tick where signal fires; exit at i+H)
    # - "regime_state" : signal-driven (enter at signal=True transition, exit at signal=False transition)
    #                    aggregate_n_trades = total number of regime trades
    #                    aggregate_expectancy_bps = mean per-regime gross bps
    backtest_mode: str = Field("fixed_h", description="Backtest paradigm: 'fixed_h' (legacy) or 'regime_state' (default 2026-04-27).")
    # Regime-state aggregate metrics (only populated when backtest_mode == "regime_state")
    aggregate_n_regimes: int | None = Field(None, description="Sum of n_regimes across (sym, date).")
    aggregate_signal_duty_cycle: float | None = Field(
        None, description="Trade-weighted mean signal duty cycle. Near 1.0 = signal-always-on (buy-and-hold artifact)."
    )
    aggregate_mean_duration_ticks: float | None = Field(
        None, description="Mean regime holding period in ticks across all sessions."
    )
    # Maker spread capture aggregates (2026-04-27, Path B).
    execution_mode: str | None = Field(
        None, description="'mid_to_mid' (default) | 'maker_optimistic' | 'maker_realistic'."
    )
    aggregate_expectancy_maker_bps: float | None = Field(
        None, description="Mean per-regime gross under maker execution mode, aggregated across (sym, date)."
    )
    aggregate_avg_spread_bps: float | None = Field(
        None, description="Mean spread bps at entry/exit averaged across all regimes."
    )


# ---------------------------------------------------------------------------
# Chain 1.5 — Signal enhancement layer (2026-04-23)
#
# Bridges Chain 1 (pure signal discovery, execution=1) and Chain 2 (real-world
# execution mechanics: order type, fees, queue, latency).
#
# Chain 1.5 assumes mid-to-mid pricing (no fees, no spread costs) — same
# simplification as Chain 1 — and optimizes:
#   - exit policy: PT / SL / trailing (early-exit within max_hold)
#   - max_hold_ticks: may differ from Chain 1's prediction_horizon_ticks
#   - extra_regime_gate: additional filter on top of base SignalSpec
#
# Chain 2 then takes an EnhancedSignalSpec as fixed input and tunes order
# type / fees / queue / sizing. This preserves CLAUDE.md's "Chain 1 objective:
# WR × E[|Δmid|]" mathematical framework — Chain 1.5 stays fee-free.
# ---------------------------------------------------------------------------


class ExitTrailingMode(str, Enum):
    NONE      = "none"
    FIXED_BPS = "fixed_bps"


class ExitPolicy(BaseModel):
    """Early-exit rules applied before max_hold_ticks expires. Still mid-to-mid."""
    model_config = ConfigDict(extra="forbid")
    pt_bps: float = Field(0.0, ge=0.0, description="Profit target (bps). 0 = no PT.")
    sl_bps: float = Field(0.0, ge=0.0, description="Stop loss (bps). 0 = no SL.")
    trailing_mode: ExitTrailingMode = ExitTrailingMode.NONE
    trailing_distance_bps: float = Field(0.0, ge=0.0)


class EnhancedSignalSpec(HandoffBase):
    """Chain 1.5 output — wraps a Chain 1 SignalSpec with exit policy and
    optional extra regime filter. Still uses mid-to-mid pricing (pre-fee).

    Chain 2 later takes this as immutable input.
    """
    spec_id: str = Field(..., description="Stable unique ID, e.g. 'enh_iter013_pt12_sl25'")
    base_signal_spec_id: str = Field(..., description="Reference to Chain 1 SignalSpec (fixed)")

    # Override / extend base spec behavior
    max_hold_ticks: int = Field(
        ..., ge=1, le=1000,
        description="Max ticks to hold before time-exit. May differ from base SignalSpec's "
                    "prediction_horizon_ticks — Chain 1 uses H as a measurement point, Chain 1.5 "
                    "treats it as an upper bound with early-exit allowed.",
    )
    exit_policy: ExitPolicy = Field(default_factory=ExitPolicy)
    extra_regime_gate: str | None = Field(
        None,
        description="Additional regime filter expression (evaluated per tick). "
                    "If False, skip entry. e.g. 'rolling_realized_vol(mid_px, 100) < 30'.",
    )

    # Measured (filled by chain1_5 runner)
    measured_expectancy_bps: float | None = None
    measured_wr: float | None = None
    measured_n_trades: int | None = None
    measured_avg_hold_ticks: float | None = None
    measured_exit_reason_dist: dict[str, int] | None = None  # {"pt":N, "sl":N, "trail":N, "time":N}


# ---------------------------------------------------------------------------
# Chain 2 — Execution layer (2026-04-22, Phase 2.0)
# ---------------------------------------------------------------------------


class OrderType(str, Enum):
    MARKET          = "MARKET"            # cross the spread (taker)
    LIMIT_AT_BID    = "LIMIT_AT_BID"      # post maker on bid side (for long entry)
    LIMIT_AT_ASK    = "LIMIT_AT_ASK"      # post maker on ask side (for short entry)
    LIMIT_INSIDE_1  = "LIMIT_INSIDE_1"    # 1-tick aggressive limit (Phase 2.2)


class TrailingMode(str, Enum):
    NONE        = "none"
    FIXED_BPS   = "fixed_bps"
    # ATR_BASED later


class FeeMarket(str, Enum):
    KRX_CASH = "krx_cash"      # 1.5 + 1.5 + 20 (sell tax on long exit) = RT 23 bps


class ExecutionSpec(HandoffBase):
    """Execution plan applied to a fixed Chain 1 SignalSpec.

    `signal_spec_id` references the SignalSpec that provides entry triggers.
    ExecutionSpec does NOT modify the SignalSpec; it wraps it with a post-entry
    execution layer (order type, stops, fees) to measure real-world net PnL.

    See docs/chain2_design.md for full design rationale.
    """

    spec_id: str = Field(..., description="Stable unique ID, e.g. 'exec_A_S1_baseline'")
    signal_spec_id: str = Field(..., description="Chain 1 SignalSpec id (entry trigger, fixed)")

    # Entry
    order_type: OrderType = OrderType.MARKET
    entry_ttl_ticks: int = Field(
        1, ge=1, le=500,
        description="For LIMIT orders: cancel and abort if not filled within this many ticks.",
    )
    maker_fill_rate: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Phase 2.0 simplification: when a crossing event happens while our LIMIT is resting, "
                    "we only count this fraction as actual fills (queue-position approximation).",
    )

    # Exit policy
    pt_bps: float = Field(0.0, ge=0.0, description="Profit target (bps). 0 = no PT.")
    sl_bps: float = Field(0.0, ge=0.0, description="Stop loss (bps). 0 = no SL.")
    time_stop_ticks: int = Field(50, ge=1, le=500, description="Max ticks to hold before forced MARKET exit.")
    trailing_mode: TrailingMode = TrailingMode.NONE
    trailing_distance_bps: float = Field(0.0, ge=0.0)

    # Optional extra regime gate on top of SignalSpec's own filters
    extra_regime_gate: str | None = Field(
        None, description="Optional extra filter expression, e.g. 'rolling_realized_vol(mid_px, 100) < 30'.",
    )

    # Sizing — Phase 2.0 constant only
    sizing_rule: Literal["constant_1"] = "constant_1"

    # Market realism constraints
    long_only: bool = Field(
        True,
        description=(
            "If True (default for KRX cash equity), short-side signals are SKIPPED entirely "
            "since the trader has no inventory to sell. Only `direction=+1` entries are executed. "
            "Set to False only when short selling is operationally feasible (e.g., with 대차거래 "
            "agreements or on markets that support native short — crypto spot, US equities with margin)."
        ),
    )

    # Market / cost model
    fee_market: FeeMarket = FeeMarket.KRX_CASH
    queue_model: Literal["risk_adverse", "power_prob_2"] = "risk_adverse"
    latency_model: Literal["constant_5ms"] = "constant_5ms"

    # Measured (filled in by execution-runner; None until then)
    measured_net_pnl_bps: float | None = None
    measured_sharpe: float | None = None
    measured_mdd_bps: float | None = None


class CostBreakdown(BaseModel):
    """Per-trade average cost contributions (bps, taken trade-weighted over run)."""
    model_config = ConfigDict(extra="forbid")
    spread_cost_bps: float = Field(..., ge=0.0, description="Half-spread crossed on MARKET entries/exits")
    maker_fee_cost_bps: float = Field(..., ge=0.0, description="Maker fee portion of total fee")
    taker_fee_cost_bps: float = Field(..., ge=0.0, description="Taker fee portion of total fee")
    sell_tax_cost_bps: float = Field(..., ge=0.0, description="KRX 20 bps sell tax on exit side for long positions")
    adverse_selection_cost_bps: float = Field(
        0.0, description="Mid move against us in 1 tick post-fill (signed; positive = adverse).",
    )
    slippage_cost_bps: float = Field(0.0, ge=0.0, description="Multi-level walk cost when lot > top-level qty (0 in Phase 2.0).")


class PerSymbolResult_v2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    date: str
    n_ticks: int
    n_trades: int                  # = number of round-trips (entries that got filled)
    n_wins: int
    n_losses: int
    wr: float
    net_pnl_bps_sum: float         # sum of signed net pnl across all trades (bps)
    net_pnl_bps_per_trade: float   # n_trades 기준 평균
    n_maker_fills: int
    n_taker_fills: int
    cost_breakdown: CostBreakdown


class BacktestResult_v2(HandoffBase):
    """Chain 2 backtest output. Extends Chain 1 BacktestResult semantics with
    execution-layer measurements and cost decomposition.
    """
    spec_id: str
    signal_spec_id: str
    execution_spec_id: str

    per_symbol: list[PerSymbolResult_v2]

    aggregate_n_trades: int
    aggregate_wr: float
    aggregate_net_pnl_bps_per_trade: float
    aggregate_sharpe: float
    aggregate_max_drawdown_bps: float

    n_fills: int
    n_maker_fills: int
    n_taker_fills: int
    final_inventory_lots: int = 0

    cost_breakdown: CostBreakdown

    trace_path: str | None = None


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class Feedback(HandoffBase):
    """Output of feedback-analyst (stage ④)."""

    spec_id: str
    strengths: list[str]
    weaknesses: list[str]
    win_bucket_insight: str = Field(
        ..., description="What characterizes the winning ticks? (regime, book state, etc.)"
    )
    loss_bucket_insight: str
    cross_symbol_consistency: Literal["consistent", "mixed", "inconsistent", "not_applicable"] = "not_applicable"
    recommended_next_direction: Literal[
        "tighten_threshold", "loosen_threshold", "add_filter", "drop_feature",
        "swap_feature", "change_horizon", "combine_with_other_spec", "retire",
        # Block B additions — extended mutation repertoire
        "ensemble_vote", "extreme_quantile", "timevarying_threshold", "add_regime_filter",
    ]
    recommended_direction_reasoning: str


# ---------------------------------------------------------------------------
# Improvement proposal
# ---------------------------------------------------------------------------

class ImprovementProposal(HandoffBase):
    """Output of signal-improver (stage ⑤). Input to the next iteration's
    signal-generator.
    """

    parent_spec_id: str
    proposed_mutations: list[str] = Field(
        ...,
        description=(
            "Concrete spec changes to try next iteration, each referencing an "
            "observation from the Feedback. e.g., 'raise threshold 0.5→0.7 "
            "based on weak WR in mid-spread regime'"
        ),
    )
    search_axes: list[Literal["feature", "threshold", "horizon", "filter", "combine"]]
    reasoning: str


# ---------------------------------------------------------------------------
# Chain 2 gate — candidate selection for promotion to Chain 2
# ---------------------------------------------------------------------------


class Chain2Priority(str, Enum):
    MUST_INCLUDE = "must_include"
    STRONG       = "strong"
    MARGINAL     = "marginal"


class Chain2Candidate(BaseModel):
    """One SignalSpec ranked as a Chain 2 promotion candidate."""

    model_config = ConfigDict(extra="forbid")

    spec_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    priority: Chain2Priority

    # Derived metrics used by the scorer
    wr: float
    expectancy_bps: float
    expectancy_post_fee_bps: float
    fee_absorption_ratio: float
    trade_density_per_day_per_sym: float
    complexity_score: float
    has_regime_self_filter: bool

    # Dominance
    dominates: list[str] = Field(default_factory=list)
    dominated_by: str | None = None

    # Factor contributions to composite score
    factor_breakdown: dict[str, float] = Field(default_factory=dict)

    # Optional LLM-generated narrative
    rationale_kr: str | None = None
    expected_chain2_concerns: list[str] = Field(default_factory=list)


class Chain2ScenarioResult(BaseModel):
    """Candidate ranking under one fee scenario."""

    model_config = ConfigDict(extra="forbid")

    fee_scenario: str
    fee_rt_bps: float
    top_candidates: list[Chain2Candidate]
    excluded: dict[str, str] = Field(
        default_factory=dict,
        description="spec_id → reason for exclusion (gate name or 'dominated_by:<id>')",
    )


class Chain2GateOutput(HandoffBase):
    """Output of chain2-gate agent (stage 6_promotion_gate)."""

    iterations_scanned: list[int]
    total_valid_specs: int
    scenarios: list[Chain2ScenarioResult]
    cross_scenario_consensus: list[str] = Field(
        default_factory=list,
        description="spec_ids that appear in every scenario's top_candidates",
    )
    warnings: list[str] = Field(default_factory=list)
    meta_narrative_kr: str | None = None


# ---------------------------------------------------------------------------
# Iteration log (meta)
# ---------------------------------------------------------------------------

class IterationLog(BaseModel):
    """One iteration's end-to-end artifact index."""

    model_config = ConfigDict(extra="forbid")

    iteration_idx: int
    started_at: datetime
    finished_at: datetime | None = None
    signal_specs: list[str] = Field(default_factory=list, description="spec_ids generated this iteration")
    spec_evaluations: list[str] = Field(default_factory=list, description="Paths to SpecEvaluation jsons")
    generated_codes: list[str] = Field(default_factory=list)
    fidelity_reports: list[str] = Field(default_factory=list)
    backtest_results: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    improvement_proposals: list[str] = Field(default_factory=list)
    stop_reason: str | None = None


# ---------------------------------------------------------------------------
# Agent self-description (for 6-component validator)
# ---------------------------------------------------------------------------

REQUIRED_AGENT_COMPONENTS = (
    "system_prompt",
    "user_prompt",
    "reference",
    "input_schema",
    "output_schema",
    "reasoning_flow",
)


class AgentManifest(BaseModel):
    """Parsed from each agent's AGENTS.md YAML frontmatter. Used by the
    orchestrator to enforce CLAUDE.md §Agent 구성 원칙 (2) — all 6 components
    must be present.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    last_updated: str
    owner_chain: Literal["chain1", "chain2"]
    stage: str
    input_schema: str
    output_schema: str
    required_components: list[str]

    @model_validator(mode="before")
    @classmethod
    def _coerce_date(cls, data: Any) -> Any:
        if isinstance(data, dict) and "last_updated" in data:
            lu = data["last_updated"]
            if hasattr(lu, "isoformat"):
                data["last_updated"] = lu.isoformat()
        return data

    @model_validator(mode="after")
    def _must_have_6(self) -> AgentManifest:
        missing = [c for c in REQUIRED_AGENT_COMPONENTS if c not in self.required_components]
        if missing:
            raise ValueError(f"Agent {self.name} missing required components: {missing}")
        return self
