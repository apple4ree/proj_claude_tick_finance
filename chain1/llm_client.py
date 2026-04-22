"""Chain 1 LLM client — LiteLLM-backed, multi-provider (Anthropic / OpenAI / Gemini).

Design:
  - Single entry point `LLMClient.call_agent(agent_name, user_message, response_model)`.
  - Model string alone selects the provider (LiteLLM convention).
  - Provider-specific reasoning controls (Anthropic `thinking`, OpenAI
    `reasoning_effort`, Gemini thinking) are applied automatically based on the
    detected model family.
  - Structured output: OpenAI → JSON schema mode; Gemini → response_mime_type;
    Anthropic → instruction + parse (Anthropic JSON-schema mode is not exposed
    in all SDKs; instruction-based extraction is reliable with Opus).
  - AGENTS.md prompts + references auto-loaded for each agent, so the call site
    only supplies the dynamic user message and a Pydantic response model.
  - `.env` loaded via python-dotenv at import time.

Phase A-C note: offline-safe. Construction + prompt loading + config inspection
do NOT require any network or API key. Only `call_agent()` needs credentials.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_ROOT = REPO_ROOT / ".claude" / "agents" / "chain1"

load_dotenv(REPO_ROOT / ".env", override=False)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def detect_provider(model: str) -> str:
    """Classify a model string into {'anthropic', 'openai', 'gemini', 'other'}."""
    m = model.lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if m.startswith("gemini") or m.startswith("gemini/"):
        return "gemini"
    if "/" in m:
        prefix = m.split("/", 1)[0]
        if prefix in {"anthropic", "openai", "azure", "vertex", "bedrock"}:
            return prefix
    return "other"


def canonicalize_model(model: str) -> str:
    """Normalize a model string so LiteLLM routes to the intended provider endpoint.

    Specifically: bare `gemini-*` must be prefixed with `gemini/` so LiteLLM
    uses Google AI Studio (GEMINI_API_KEY) rather than defaulting to Vertex AI
    (which requires Google Cloud SDK + gcloud auth).
    """
    m = model.strip()
    if m.startswith("gemini-") and not m.startswith("gemini/"):
        return "gemini/" + m
    return m


_OPENAI_REASONING_PATTERNS = re.compile(r"^(o[1-9]|gpt-5)", re.IGNORECASE)


def supports_anthropic_thinking(model: str) -> bool:
    # Anthropic Opus 4.x + Sonnet 4.x (thinking-capable).
    m = model.lower()
    return m.startswith("claude") and any(tok in m for tok in ("opus-4", "sonnet-4"))


def supports_openai_reasoning(model: str) -> bool:
    return bool(_OPENAI_REASONING_PATTERNS.match(model))


def supports_gemini_thinking(model: str) -> bool:
    m = model.lower()
    return m.startswith("gemini") and "2.5" in m


def budget_to_effort(budget_tokens: int) -> str:
    """Map Anthropic-style budget (tokens) to OpenAI-style effort (low/medium/high)."""
    if budget_tokens <= 0:
        return "minimal"
    if budget_tokens <= 2000:
        return "low"
    if budget_tokens <= 8000:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    default_model: str = field(default_factory=lambda: os.getenv("CHAIN1_DEFAULT_MODEL", "claude-opus-4-7"))
    max_output_tokens: int = field(default_factory=lambda: int(os.getenv("CHAIN1_MAX_OUTPUT_TOKENS", "8000")))
    thinking_budget: int = field(default_factory=lambda: int(os.getenv("CHAIN1_THINKING_BUDGET", "8000")))
    request_timeout_sec: int = field(default_factory=lambda: int(os.getenv("CHAIN1_REQUEST_TIMEOUT_SEC", "300")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("CHAIN1_MAX_RETRIES", "2")))

    per_agent_overrides: dict[str, str] = field(default_factory=lambda: {
        "signal-generator":  os.getenv("CHAIN1_MODEL_SIGNAL_GENERATOR") or "",
        "signal-evaluator":  os.getenv("CHAIN1_MODEL_SIGNAL_EVALUATOR") or "",
        "feedback-analyst":  os.getenv("CHAIN1_MODEL_FEEDBACK_ANALYST") or "",
        "signal-improver":   os.getenv("CHAIN1_MODEL_SIGNAL_IMPROVER") or "",
    })

    def model_for(self, agent_name: str) -> str:
        return self.per_agent_overrides.get(agent_name) or self.default_model


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    """LiteLLM-backed client with AGENTS.md prompt loading and Pydantic-validated output."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()

    # ---- Liveness (no network) -------------------------------------------

    def is_live(self, model: str | None = None) -> bool:
        """Return True iff a plausible API key is present for the target model's provider."""
        target_model = model or self.config.default_model
        provider = detect_provider(target_model)
        key_map = {
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
            "openai":    os.getenv("OPENAI_API_KEY", ""),
            "gemini":    os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
        }
        k = key_map.get(provider, "")
        if not k:
            return False
        if provider == "anthropic":
            return k.startswith("sk-ant-") and len(k) > 30
        if provider == "openai":
            return k.startswith("sk-") and len(k) > 20
        if provider == "gemini":
            return len(k) > 20
        return False

    # ---- AGENTS.md loading -----------------------------------------------

    @staticmethod
    def load_prompts(agent_name: str) -> dict[str, str]:
        ad = AGENTS_ROOT / agent_name / "AGENTS.md"
        if not ad.exists():
            raise FileNotFoundError(ad)
        text = ad.read_text()
        _, _, body = text.split("---", 2) if text.startswith("---") else ("", "", text)
        section_markers = [
            ("system_prompt",    "## 1. System Prompt"),
            ("user_prompt",      "## 2. User Prompt"),
            ("reference",        "## 3. Reference"),
            ("input_schema",     "## 4. Input Schema"),
            ("output_schema",    "## 5. Output Schema"),
            ("reasoning_flow",   "## 6. Reasoning Flow"),
        ]
        positions = []
        for key, marker in section_markers:
            idx = body.find(marker)
            if idx < 0:
                raise ValueError(f"{agent_name}: missing section {marker!r} in AGENTS.md")
            positions.append((key, idx))
        positions.append(("__end__", len(body)))

        sections: dict[str, str] = {}
        for i in range(len(section_markers)):
            key, start = positions[i]
            _, end = positions[i + 1]
            chunk = body[start:end].split("\n", 1)[1] if "\n" in body[start:end] else ""
            sections[key] = chunk.strip()
        return sections

    @staticmethod
    def load_reference_files(agent_name: str) -> dict[str, str]:
        prompts = LLMClient.load_prompts(agent_name)
        ref_body = prompts["reference"]
        paths = re.findall(r"[`\"]*((?:\.\./)?[\w\-/_.]+\.(?:md|py))[`\"]*", ref_body)
        out: dict[str, str] = {}
        agent_dir = AGENTS_ROOT / agent_name
        for p in paths:
            candidate = (agent_dir / p).resolve()
            if candidate.exists() and candidate.is_file():
                try:
                    out[str(candidate.relative_to(REPO_ROOT))] = candidate.read_text()
                except Exception:  # noqa: BLE001
                    pass
        return out

    # ---- Provider-aware parameter assembly -------------------------------

    def _build_completion_params(self, model: str, response_model: Type[T]) -> dict[str, Any]:
        provider = detect_provider(model)
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": self.config.max_output_tokens,
            "timeout": self.config.request_timeout_sec,
            "num_retries": self.config.max_retries,
        }

        # Reasoning / thinking controls
        budget = self.config.thinking_budget
        if budget > 0:
            if provider == "anthropic" and supports_anthropic_thinking(model):
                params["thinking"] = {"type": "enabled", "budget_tokens": budget}
            elif provider == "openai" and supports_openai_reasoning(model):
                params["reasoning_effort"] = budget_to_effort(budget)
            elif provider == "gemini" and supports_gemini_thinking(model):
                params["reasoning_effort"] = budget_to_effort(budget)

        # Structured output (provider-specific best effort)
        schema = response_model.model_json_schema()
        if provider == "openai":
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": schema,
                    "strict": False,   # pydantic schemas often use 'extra="forbid"' equivalents; strict mode is too rigid
                },
            }
        elif provider == "gemini":
            # Gemini accepts `response_mime_type=application/json` but its
            # `response_schema` parser rejects OpenAPI v3.1 constructs Pydantic
            # emits (`$defs`, `$ref`, `additionalProperties`). Don't send the
            # schema to the API — our system prompt already embeds it via
            # _augment_system(), and Pydantic validates the response client-side.
            params["response_mime_type"] = "application/json"
        # Anthropic: handled via system-prompt instructions (see _augment_system)

        return params

    def _augment_system(self, base_system: str, response_model: Type[T]) -> str:
        schema = response_model.model_json_schema()
        instructions = (
            "\n\n---\n## Output format\n"
            "Respond with a single JSON object matching the following Pydantic schema. "
            "Return ONLY the JSON object — no prose, no markdown fences.\n\n"
            f"Schema name: {response_model.__name__}\n"
            f"Schema JSON:\n{json.dumps(schema, indent=2)}\n"
        )
        return base_system + instructions

    # ---- Call ------------------------------------------------------------

    def call_agent(
        self,
        agent_name: str,
        user_message: str,
        response_model: Type[T],
        extra_system: str = "",
        include_references: bool = True,
        model_override: str | None = None,
    ) -> T:
        """Invoke an agent's LLM with its AGENTS.md system prompt + user message.

        Raises RuntimeError if no valid API key is present for the selected model's provider.
        """
        model = canonicalize_model(model_override or self.config.model_for(agent_name))

        if not self.is_live(model):
            provider = detect_provider(model)
            raise RuntimeError(
                f"LLM call requested but no live API key for provider={provider!r} "
                f"(model={model!r}). Populate .env from .env.example."
            )

        # Assemble system prompt from AGENTS.md + references
        prompts = self.load_prompts(agent_name)
        system_prompt = prompts["system_prompt"]
        if include_references:
            refs = self.load_reference_files(agent_name)
            if refs:
                system_prompt += "\n\n---\n## Loaded reference materials\n"
                for path, content in refs.items():
                    system_prompt += f"\n### {path}\n\n{content}\n"
        if extra_system:
            system_prompt += "\n\n" + extra_system

        system_prompt = self._augment_system(system_prompt, response_model)

        # Deferred import — litellm pulls large transitive deps
        import litellm  # noqa: F401 (imported for side-effect of .completion())

        params = self._build_completion_params(model, response_model)
        params["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        resp = litellm.completion(**params)

        # LiteLLM normalizes the response shape (OpenAI-style)
        try:
            text_out = resp["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            text_out = getattr(resp.choices[0].message, "content", "")
        text_out = (text_out or "").strip()

        # Some providers wrap JSON in ```json fences despite instruction; strip defensively.
        text_out = _strip_code_fences(text_out)

        try:
            data = json.loads(text_out)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{agent_name} returned non-JSON response (model={model}).\n"
                f"First 500 chars: {text_out[:500]}\nError: {e}"
            ) from e
        # Tolerate common LLM deviations from the response schema:
        # 1) Bare list at top level when the schema expects an object with one
        #    list field (e.g. `{"specs": [...]}` expected but `[...]` returned).
        # 2) Object with singular-key variants (`spec`, `items`, `results`)
        #    when the canonical field is plural.
        if isinstance(data, list):
            # Find the unique list-typed field on the response_model and wrap.
            list_fields = [
                name for name, info in response_model.model_fields.items()
                if getattr(info.annotation, "__origin__", None) is list
                or str(info.annotation).startswith("list[")
            ]
            if len(list_fields) == 1:
                data = {list_fields[0]: data}

        # Additional sanitization for signal-generator output:
        # LLMs sometimes emit negative thresholds to encode contra direction.
        # Our schema requires threshold ≥ 0 (direction field carries the sign).
        # Auto-correct: flip sign into direction.
        if isinstance(data, dict) and "specs" in data and isinstance(data["specs"], list):
            for spec in data["specs"]:
                if not isinstance(spec, dict):
                    continue
                thr = spec.get("threshold")
                if isinstance(thr, (int, float)) and thr < 0:
                    spec["threshold"] = float(abs(thr))
                    cur_dir = spec.get("direction", "long_if_pos")
                    spec["direction"] = (
                        "long_if_neg" if cur_dir == "long_if_pos" else "long_if_pos"
                    )

        try:
            return response_model(**data)
        except ValidationError as e:
            raise ValueError(
                f"{agent_name} output failed Pydantic validation for {response_model.__name__}.\n"
                f"Data snippet: {json.dumps(data, indent=2)[:1000]}\n{e}"
            ) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    m = _CODE_FENCE_RE.match(text.strip())
    if m:
        return m.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# CLI — diagnostic only (does not call LLM unless --live)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("config")
    p_prompts = sub.add_parser("show-prompts"); p_prompts.add_argument("agent_name")
    p_ref = sub.add_parser("show-references");  p_ref.add_argument("agent_name")
    sub.add_parser("check-live")
    p_detect = sub.add_parser("detect-provider"); p_detect.add_argument("model")

    args = ap.parse_args()

    client = LLMClient()

    if args.cmd == "config":
        cfg = client.config
        print(json.dumps({
            "default_model": cfg.default_model,
            "default_provider": detect_provider(cfg.default_model),
            "per_agent_overrides": cfg.per_agent_overrides,
            "max_output_tokens": cfg.max_output_tokens,
            "thinking_budget": cfg.thinking_budget,
            "request_timeout_sec": cfg.request_timeout_sec,
            "max_retries": cfg.max_retries,
            "live_for_default": client.is_live(),
            "api_keys_present": {
                "anthropic": bool(os.getenv("ANTHROPIC_API_KEY", "")),
                "openai":    bool(os.getenv("OPENAI_API_KEY", "")),
                "gemini":    bool(os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")),
            },
        }, indent=2))
    elif args.cmd == "show-prompts":
        for k, v in client.load_prompts(args.agent_name).items():
            print(f"\n{'='*60}\n{k}\n{'='*60}\n{v[:500]}")
    elif args.cmd == "show-references":
        refs = client.load_reference_files(args.agent_name)
        for p in refs:
            print(f"  {p}")
        print(f"\n({len(refs)} files)")
    elif args.cmd == "check-live":
        models = [client.config.default_model] + [m for m in client.config.per_agent_overrides.values() if m]
        for m in dict.fromkeys(models):  # dedupe preserving order
            print(f"{m:<40} provider={detect_provider(m):<10} live={client.is_live(m)}")
    elif args.cmd == "detect-provider":
        print(detect_provider(args.model))
