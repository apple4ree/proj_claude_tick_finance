"""FeedbackOutput — output of feedback-analyst."""
from __future__ import annotations

from typing import Any, Literal, Optional

from engine.schemas.base import HandoffBase


class FeedbackOutput(HandoffBase):
    agent_name: Literal["feedback-analyst"]

    lesson_id: Optional[str]
    pattern_id: Optional[str]
    primary_finding: str
    agreement_points: list[str]
    disagreement_points: list[str]
    priority_action: Literal["alpha", "execution", "both", "neither", "meta"]
    next_idea_seed: str
    local_seed: str
    escape_seed: str
    stop_suggested: bool
    structural_concern: Optional[str]
    data_requests: list[str]
    extensions: dict[str, Any]
