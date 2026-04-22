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
    prediction_horizon_ticks: int = Field(1, ge=1, le=1000)

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
