"""Chain 1 code-generator (stage ②.5) — deterministic template renderer.

Input:  SignalSpec  (validated, post signal-evaluator)
Output: GeneratedCode  (Python module on disk with a `signal(snap) -> float` function)

This is pure Python with no LLM involvement. The SignalSpec.formula is parsed
as a Python expression using a restricted grammar; every identifier must be a
whitelisted primitive or a known helper. Emitted code always follows the
template at `.claude/agents/chain1/code-generator/references/signal_fn_template.py`.

Template version contract: v0.1.0_basic.
If a future SignalSpec needs constructs outside this template's grammar, the
remedy is to publish a new template (v0.2.0_...) and bump the template_used
field — not to introduce ad-hoc generation.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"

if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import SignalSpec, GeneratedCode  # noqa: E402
from chain1.primitives import PRIMITIVE_WHITELIST  # noqa: E402

TEMPLATE_VERSION = "v0.1.0_basic"


# ---------------------------------------------------------------------------
# Formula grammar — restricted Python expression subset
# ---------------------------------------------------------------------------
# Allowed:
#   - Primitive calls:   obi_1, obi_5(k=5), microprice_dev_bps, spread_bps, ...
#     (no-arg or with fixed-int positional args for _k-style)
#   - Numeric literals:  int, float
#   - Arithmetic:        + - * / (unary -)
#   - Comparisons:       > < >= <= == !=
#   - Boolean:           and or not
#   - abs(), sign() (mapped to np.sign)
#   - Parentheses
# Disallowed: function defs, lambda, comprehensions, attribute access, subscripts,
# assignments, any name not in PRIMITIVE_WHITELIST or the extras dict below.


ALLOWED_EXTRAS = {"abs", "sign"}
PRIMITIVE_NAMES = set(PRIMITIVE_WHITELIST.keys())

# Stateful helpers: zscore(primitive, window), rolling_mean(primitive, window),
# rolling_std(primitive, window). These instantiate a per-spec helper at module
# import time and update it each tick.
STATEFUL_HELPERS: dict[str, str] = {
    "rolling_mean":        "RollingMean",
    "rolling_std":         "RollingStd",
    "zscore":              "RollingZScore",
    "rolling_realized_vol": "RollingRealizedVol",
    "rolling_momentum":    "RollingMomentum",
}

ALLOWED_NAMES = PRIMITIVE_NAMES | ALLOWED_EXTRAS | set(STATEFUL_HELPERS.keys()) | {"True", "False"}

# Primitives that need previous snapshot (take 2 args: snap, prev)
STATEFUL_PRIMITIVES = {name for name, meta in PRIMITIVE_WHITELIST.items() if meta["stateful"]}


class FormulaParseError(ValueError):
    """Raised when spec.formula violates the restricted grammar."""


class _FormulaValidator(ast.NodeVisitor):
    """AST walker that validates a parsed formula expression."""

    def __init__(self, allowed_primitives: set[str]) -> None:
        self.allowed = allowed_primitives
        self.primitives_seen: set[str] = set()

    def generic_visit(self, node: ast.AST) -> None:
        # Whitelist node types
        allowed_types = (
            ast.Expression, ast.Expr, ast.Call, ast.Name, ast.Constant,
            ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
            ast.Add, ast.Sub, ast.Mult, ast.Div,
            ast.USub, ast.UAdd,
            ast.And, ast.Or, ast.Not,
            ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
            ast.Load,
        )
        if not isinstance(node, allowed_types):
            raise FormulaParseError(f"Disallowed AST node: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if (node.id not in self.allowed
                and node.id not in ALLOWED_EXTRAS
                and node.id not in STATEFUL_HELPERS
                and node.id not in ("True", "False")):
            raise FormulaParseError(f"Unknown identifier (not a whitelisted primitive): {node.id!r}")
        if node.id in PRIMITIVE_NAMES:
            self.primitives_seen.add(node.id)

    def visit_Call(self, node: ast.Call) -> None:
        # Function must be a Name node
        if not isinstance(node.func, ast.Name):
            raise FormulaParseError("Only direct function calls allowed (no attribute calls)")
        fname = node.func.id
        if fname not in self.allowed and fname not in ALLOWED_EXTRAS and fname not in STATEFUL_HELPERS:
            raise FormulaParseError(f"Call to unknown function: {fname!r}")
        # Helper call shape: helper(primitive_name, window_int)
        if fname in STATEFUL_HELPERS:
            if len(node.args) != 2:
                raise FormulaParseError(
                    f"{fname}() requires exactly 2 positional args (primitive, window), got {len(node.args)}"
                )
            first = node.args[0]
            second = node.args[1]
            if not (isinstance(first, ast.Name) and first.id in PRIMITIVE_NAMES):
                raise FormulaParseError(
                    f"{fname}() first arg must be a whitelisted primitive name, got {ast.dump(first)}"
                )
            if not (isinstance(second, ast.Constant) and isinstance(second.value, int) and second.value >= 2):
                raise FormulaParseError(
                    f"{fname}() second arg must be an integer window >= 2, got {ast.dump(second)}"
                )
            # Do NOT mark this primitive in primitives_seen here — the inner primitive
            # Name will be transformed later, but for the spec's `primitives_used` list
            # we DO record it so declare/used bidirectional check passes.
            self.primitives_seen.add(first.id)
            return  # skip generic_visit to avoid double-visit of inner Name
        # Primitive calls accept positional args only; no kwargs with non-literal
        for kw in node.keywords:
            if not isinstance(kw.value, ast.Constant):
                raise FormulaParseError(f"kwargs must be literal constants in {fname}")
        for arg in node.args:
            if not isinstance(arg, (ast.Constant, ast.Name)):
                raise FormulaParseError(f"Call {fname}: arg type {type(arg).__name__} not allowed")
        # Record primitive usage
        if fname in PRIMITIVE_NAMES:
            self.primitives_seen.add(fname)
        # Visit children so nested arg Names get validated
        self.generic_visit(node)


class _PrimitiveCallTransformer(ast.NodeTransformer):
    """Rewrite primitive Name references into Call(primitive, [snap, ...]).

    Also rewrites stateful-helper calls (rolling_mean / rolling_std / zscore):
        zscore(obi_proxy, 300)
           → _HELPER_zscore_obi_proxy_300.update(obi_proxy(snap))

    Unique (helper, primitive, window) tuples encountered are recorded in
    `helpers_used`, so the renderer can emit module-level helper instances.
    """

    def __init__(self) -> None:
        super().__init__()
        self._seen_call_funcs: set[int] = set()
        # Each entry: (var_name, helper_name, primitive_name, window_int)
        self.helpers_used: list[tuple[str, str, str, int]] = []
        self._helper_keys: set[tuple[str, str, int]] = set()

    def _make_primitive_call(self, prim_name: str) -> ast.Call:
        snap_arg = ast.Name(id="snap", ctx=ast.Load())
        args: list[ast.AST] = [snap_arg]
        if prim_name in STATEFUL_PRIMITIVES:
            prev_arg = ast.Call(
                func=ast.Name(id="getattr", ctx=ast.Load()),
                args=[snap_arg, ast.Constant(value="prev"), ast.Constant(value=None)],
                keywords=[],
            )
            args.append(prev_arg)
        return ast.Call(func=ast.Name(id=prim_name, ctx=ast.Load()), args=args, keywords=[])

    def visit_Call(self, node: ast.Call) -> ast.AST:
        # Mark the func child so visit_Name doesn't rewrite it
        if isinstance(node.func, ast.Name):
            self._seen_call_funcs.add(id(node.func))

            # Stateful helper — rewrite into HELPER.update(primitive(snap))
            if node.func.id in STATEFUL_HELPERS:
                prim_name = node.args[0].id  # Name node (validated earlier)
                window = int(node.args[1].value)  # Constant int
                helper_name = node.func.id
                key = (helper_name, prim_name, window)
                var_name = f"_HELPER_{helper_name}_{prim_name}_{window}"
                if key not in self._helper_keys:
                    self._helper_keys.add(key)
                    self.helpers_used.append((var_name, helper_name, prim_name, window))
                inner_call = self._make_primitive_call(prim_name)
                new_call = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=var_name, ctx=ast.Load()),
                        attr="update", ctx=ast.Load(),
                    ),
                    args=[inner_call], keywords=[],
                )
                return ast.copy_location(new_call, node)

        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if id(node) in self._seen_call_funcs:
            return node
        if node.id not in PRIMITIVE_NAMES:
            return node
        new_call = self._make_primitive_call(node.id)
        return ast.copy_location(new_call, node)


def _normalize_formula_text(formula: str) -> str:
    """Light pre-processing: accept natural-language `AND`/`OR`/`NOT` (any case)
    and convert to Python `and`/`or`/`not`. Preserves other text as-is.

    LLM outputs often use uppercase `AND` / `OR` because mathematical/English
    convention. We tolerate this so compound formulas like
    `obi_1 > 0.5 AND obi_5 > 0.3` parse as valid Python expressions.
    """
    # Word-boundary replace, case-insensitive
    import re as _re
    f = _re.sub(r"\bAND\b", "and", formula, flags=_re.IGNORECASE)
    f = _re.sub(r"\bOR\b",  "or",  f, flags=_re.IGNORECASE)
    f = _re.sub(r"\bNOT\b", "not", f, flags=_re.IGNORECASE)
    return f


def parse_formula(formula: str, allowed_primitives: set[str]) -> tuple[ast.Expression, set[str], str, list[tuple[str, str, str, int]]]:
    """Parse formula as a restricted Python expression.

    Returns (parsed_ast, primitives_referenced, canonical_expression_str, helpers_used).
    - helpers_used: list of (var_name, helper_name, primitive_name, window_int) tuples
      for each unique stateful-helper invocation (rolling_mean / rolling_std / zscore).
    Raises FormulaParseError on any violation.
    """
    formula = _normalize_formula_text(formula)
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as e:
        raise FormulaParseError(f"Syntax error: {e}") from e
    v = _FormulaValidator(allowed_primitives)
    v.visit(tree)

    # Rewrite primitive Names → Call(primitive, snap[, prev])
    transformer = _PrimitiveCallTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    canonical = ast.unparse(new_tree.body)
    return new_tree, v.primitives_seen, canonical, transformer.helpers_used


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


TEMPLATE_SRC = '''\
"""Auto-generated Chain 1 signal module.

spec_id: {spec_id}
template: {template_version}
Generated by chain1.code_generator — DO NOT EDIT by hand.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure chain1.primitives is importable regardless of how this module is loaded.
_REPO_ROOT = Path(__file__).resolve()
for _ in range(6):
    if (_REPO_ROOT / "chain1" / "primitives.py").exists():
        break
    _REPO_ROOT = _REPO_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chain1.primitives import {imports}


SPEC_ID = "{spec_id}"
THRESHOLD = {threshold}
DIRECTION = "{direction}"
HORIZON_TICKS = {horizon}

{helper_instances}

def signal(snap) -> float:
    """Compute signal scalar. Decision rule lives in backtest_runner."""
    return {expression}
'''


def render_signal_module(
    spec: SignalSpec,
    primitives_used: set[str],
    canonical_expression: str,
    helpers_used: list[tuple[str, str, str, int]] | None = None,
) -> str:
    """Produce the full module source string."""
    imports_set = set(primitives_used)
    helper_instances_lines: list[str] = []
    if helpers_used:
        # Ensure helper classes are imported
        helper_classes = sorted({STATEFUL_HELPERS[h] for (_v, h, _p, _w) in helpers_used})
        imports_set |= set(helper_classes)
        helper_instances_lines.append("# Stateful helper instances (one per unique helper × primitive × window)")
        for var_name, helper_name, _prim, window in helpers_used:
            cls = STATEFUL_HELPERS[helper_name]
            helper_instances_lines.append(f"{var_name} = {cls}({window})")
    imports = ", ".join(sorted(imports_set)) if imports_set else "obi_1"
    return TEMPLATE_SRC.format(
        spec_id=spec.spec_id,
        template_version=TEMPLATE_VERSION,
        imports=imports,
        threshold=repr(float(spec.threshold)),
        direction=spec.direction.value,
        horizon=int(spec.prediction_horizon_ticks),
        helper_instances="\n".join(helper_instances_lines),
        expression=canonical_expression,
    )


def generate_code(spec: SignalSpec, output_path: Path | str) -> GeneratedCode:
    """Render a SignalSpec to a Python module on disk.

    Steps:
      1. Parse formula under restricted grammar; verify primitives match declared list.
      2. Render template with primitives import + formula expression.
      3. Syntax-check the emitted source with ast.parse.
      4. Write to `output_path`.
      5. Return GeneratedCode.
    """
    output_path = Path(output_path)

    allowed = set(spec.primitives_used) & PRIMITIVE_NAMES
    if allowed != set(spec.primitives_used):
        unknown = set(spec.primitives_used) - PRIMITIVE_NAMES
        raise FormulaParseError(f"Declared primitives not in whitelist: {unknown}")

    tree, referenced, canonical, helpers_used = parse_formula(spec.formula, allowed)

    if referenced != allowed:
        extra_declared = allowed - referenced
        missing_declared = referenced - allowed
        msg_parts = []
        if extra_declared:
            msg_parts.append(f"declared but unused: {extra_declared}")
        if missing_declared:
            msg_parts.append(f"used but not declared: {missing_declared}")
        if msg_parts:
            raise FormulaParseError(
                "primitives_used inconsistent with formula (" + "; ".join(msg_parts) + ")"
            )

    source = render_signal_module(spec, referenced, canonical, helpers_used)

    # Syntax check: emitted module must parse
    try:
        ast.parse(source)
    except SyntaxError as e:
        raise RuntimeError(f"Internal: rendered module failed ast.parse: {e}") from e

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(source)

    return GeneratedCode(
        agent_name="code-generator",
        iteration_idx=spec.iteration_idx,
        spec_id=spec.spec_id,
        code_path=str(output_path),
        entry_function="signal",
        template_used=TEMPLATE_VERSION,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec_dict = json.loads(Path(args.spec_json).read_text())
    spec = SignalSpec(**spec_dict)
    code = generate_code(spec, args.out)
    print(code.model_dump_json(indent=2))
