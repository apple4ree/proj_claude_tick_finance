"""Chain 1 fidelity-checker (stage ②.75) — deterministic AST comparison.

Implements the 6 mandatory checks defined in CLAUDE.md §Workflow ②.75 and
detailed in `.claude/agents/chain1/fidelity-checker/references/ast_comparison_rules.md`:

  1. Feature formula 일치
  2. Threshold / horizon 일치
  3. Entry 조건 일치 (signal returns scalar, not order)
  4. Execution=1 강제 (no banned identifiers)
  5. Lookahead 부재
  6. 미선언 side effect 부재

Pure Python, no LLM. Input: (SignalSpec, GeneratedCode). Output: FidelityReport.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"

if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import SignalSpec, GeneratedCode, FidelityReport, FidelityCheck  # noqa: E402
from chain1.code_generator import parse_formula, PRIMITIVE_NAMES  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — locate signal() inside the generated module
# ---------------------------------------------------------------------------


def _parse_module(path: str | Path) -> ast.Module:
    src = Path(path).read_text()
    return ast.parse(src)


def _get_signal_fn(mod: ast.Module) -> ast.FunctionDef | None:
    for node in mod.body:
        if isinstance(node, ast.FunctionDef) and node.name == "signal":
            return node
    return None


def _get_return_expr(fn: ast.FunctionDef) -> ast.AST | None:
    # docstring optional
    body = [n for n in fn.body if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Constant)]
    # Find the single Return
    returns = [n for n in body if isinstance(n, ast.Return)]
    if len(returns) != 1:
        return None
    return returns[0].value


def _module_assign_value(mod: ast.Module, name: str) -> Any | None:
    for node in mod.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
            if isinstance(node.value, ast.Constant):
                return node.value.value
            if isinstance(node.value, ast.UnaryOp) and isinstance(node.value.op, ast.USub) and isinstance(node.value.operand, ast.Constant):
                return -node.value.operand.value
    return None


def _normalize_ast(node: ast.AST) -> str:
    """Canonicalize AST to a string for structural comparison.

    Sorts commutative operands (Add, Mult, And, Or) so `a + b` ≡ `b + a`.
    """

    class _Sorter(ast.NodeTransformer):
        def visit_BinOp(self, n: ast.BinOp) -> ast.AST:
            self.generic_visit(n)
            if isinstance(n.op, (ast.Add, ast.Mult)):
                left = ast.unparse(n.left)
                right = ast.unparse(n.right)
                if left > right:
                    n.left, n.right = n.right, n.left
            return n

        def visit_BoolOp(self, n: ast.BoolOp) -> ast.AST:
            self.generic_visit(n)
            n.values = sorted(n.values, key=ast.unparse)
            return n

    cloned = ast.parse(ast.unparse(node), mode="eval").body
    sorted_ast = _Sorter().visit(cloned)
    ast.fix_missing_locations(sorted_ast)
    return ast.unparse(sorted_ast)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_1_formula_match(spec: SignalSpec, mod: ast.Module) -> FidelityCheck:
    fn = _get_signal_fn(mod)
    if fn is None:
        return FidelityCheck(name="1_formula_match", passed=False, detail="no `signal` function in module")
    ret = _get_return_expr(fn)
    if ret is None:
        return FidelityCheck(name="1_formula_match", passed=False, detail="signal() must have exactly one `return` statement")

    # Reparse spec.formula through the same transformer to get canonical form
    try:
        _, _, canonical_spec, _ = parse_formula(spec.formula, set(spec.primitives_used))
    except Exception as e:  # noqa: BLE001
        return FidelityCheck(name="1_formula_match", passed=False, detail=f"spec.formula re-parse failed: {e}")

    rhs_str = _normalize_ast(ret)
    spec_ast = ast.parse(canonical_spec, mode="eval").body
    spec_str = _normalize_ast(spec_ast)

    if rhs_str == spec_str:
        return FidelityCheck(name="1_formula_match", passed=True, detail=f"canonical match: `{rhs_str}`")
    return FidelityCheck(
        name="1_formula_match", passed=False,
        detail=f"mismatch — generated: `{rhs_str}`  spec: `{spec_str}`",
    )


def check_2_threshold_horizon(spec: SignalSpec, mod: ast.Module) -> FidelityCheck:
    threshold_val = _module_assign_value(mod, "THRESHOLD")
    horizon_val = _module_assign_value(mod, "HORIZON_TICKS")
    direction_val = _module_assign_value(mod, "DIRECTION")

    errors = []
    if threshold_val is None or abs(float(threshold_val) - float(spec.threshold)) > 1e-9:
        errors.append(f"THRESHOLD {threshold_val!r} ≠ spec {spec.threshold}")
    if horizon_val is None or int(horizon_val) != int(spec.prediction_horizon_ticks):
        errors.append(f"HORIZON_TICKS {horizon_val!r} ≠ spec {spec.prediction_horizon_ticks}")
    if direction_val is None or str(direction_val) != spec.direction.value:
        errors.append(f"DIRECTION {direction_val!r} ≠ spec {spec.direction.value}")

    if not errors:
        return FidelityCheck(
            name="2_threshold_horizon", passed=True,
            detail=f"THRESHOLD={threshold_val} HORIZON={horizon_val} DIRECTION={direction_val!r}",
        )
    return FidelityCheck(name="2_threshold_horizon", passed=False, detail="; ".join(errors))


def check_3_signal_returns_scalar(spec: SignalSpec, mod: ast.Module) -> FidelityCheck:
    fn = _get_signal_fn(mod)
    if fn is None:
        return FidelityCheck(name="3_signal_returns_scalar", passed=False, detail="no signal() fn")
    ret = _get_return_expr(fn)
    if ret is None:
        return FidelityCheck(name="3_signal_returns_scalar", passed=False, detail="no return")
    # Forbid Tuple, List, Dict, Set, Constant True/False
    if isinstance(ret, (ast.Tuple, ast.List, ast.Dict, ast.Set)):
        return FidelityCheck(
            name="3_signal_returns_scalar", passed=False,
            detail=f"return type is {type(ret).__name__}, expected scalar expression",
        )
    if isinstance(ret, ast.Constant) and isinstance(ret.value, bool):
        return FidelityCheck(
            name="3_signal_returns_scalar", passed=False,
            detail="return is a boolean literal (decision logic must live outside signal())",
        )
    return FidelityCheck(
        name="3_signal_returns_scalar", passed=True,
        detail=f"return expression node: {type(ret).__name__}",
    )


BANNED_EXECUTION_IDENTIFIERS = {
    "submit_buy_order", "submit_sell_order", "submit_order",
    "cancel", "order_id", "Order", "LIMIT", "MARKET", "GTC", "GTX", "IOC", "FOK",
    "skew", "trailing", "stop_loss", "profit_target", "time_stop", "inventory",
    "position", "ttl", "hbt",
}


def check_4_execution_equal_1(spec: SignalSpec, mod: ast.Module, source: str) -> FidelityCheck:
    hits = []
    # Scan module AST for Name nodes matching banned identifiers
    for node in ast.walk(mod):
        if isinstance(node, ast.Name) and node.id in BANNED_EXECUTION_IDENTIFIERS:
            # Ignore "position" if it only appears in docstrings/names; but we also scan source text.
            hits.append(f"Name `{node.id}`")
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_EXECUTION_IDENTIFIERS:
            hits.append(f"Attribute .{node.attr}")
        elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            mod_name = (getattr(node, "module", "") or "") + " " + " ".join(a.name for a in node.names)
            for bad in BANNED_EXECUTION_IDENTIFIERS:
                if re.search(rf"\b{re.escape(bad)}\b", mod_name):
                    hits.append(f"import exposes `{bad}`")

    if hits:
        return FidelityCheck(
            name="4_execution_equal_1", passed=False,
            detail="banned execution identifiers: " + ", ".join(hits),
        )
    return FidelityCheck(name="4_execution_equal_1", passed=True, detail="no banned execution identifiers")


LOOKAHEAD_PATTERNS = [r"\bnext_\w*", r"\bfwd_\w*", r"\bfuture_\w*", r"_t\+", r"post_trade", r"post_tick", r"_later\b"]


def check_5_no_lookahead(spec: SignalSpec, mod: ast.Module, source: str) -> FidelityCheck:
    # Text-based check (regex). Allow comments-only occurrences via AST dump.
    body_only = ast.unparse(mod)
    hits = []
    for pat in LOOKAHEAD_PATTERNS:
        m = re.search(pat, body_only)
        if m:
            hits.append(f"pattern {pat!r} matched `{m.group(0)}`")
    if hits:
        return FidelityCheck(name="5_no_lookahead", passed=False, detail="; ".join(hits))
    return FidelityCheck(name="5_no_lookahead", passed=True, detail="no lookahead patterns found")


FORBIDDEN_IMPORTS = {"random", "time", "datetime", "os", "shutil", "urllib", "requests", "http"}
FORBIDDEN_CALLS = {"print", "open", "input", "exec", "eval", "compile", "__import__"}


def check_6_no_side_effects(spec: SignalSpec, mod: ast.Module, source: str) -> FidelityCheck:
    hits = []
    for node in ast.walk(mod):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            else:
                mods = [(node.module or "").split(".")[0]]
            for m in mods:
                if m in FORBIDDEN_IMPORTS:
                    hits.append(f"forbidden import: {m}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                hits.append(f"forbidden call: {node.func.id}()")
        elif isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
            hits.append(f"forbidden stmt: {type(node).__name__}")
    if hits:
        # One allowed exception: generator-emitted `sys.path.insert(...)` bootstrap block
        # which lives outside any function. Filter those out.
        hits = [h for h in hits if h != "forbidden import: sys"]  # sys is allowed for path bootstrap
    if hits:
        return FidelityCheck(name="6_no_side_effects", passed=False, detail="; ".join(hits))
    return FidelityCheck(name="6_no_side_effects", passed=True, detail="no banned imports/calls/mutations")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_fidelity(spec: SignalSpec, code: GeneratedCode) -> FidelityReport:
    source = Path(code.code_path).read_text()
    mod = ast.parse(source)

    checks = [
        check_1_formula_match(spec, mod),
        check_2_threshold_horizon(spec, mod),
        check_3_signal_returns_scalar(spec, mod),
        check_4_execution_equal_1(spec, mod, source),
        check_5_no_lookahead(spec, mod, source),
        check_6_no_side_effects(spec, mod, source),
    ]

    overall = all(c.passed for c in checks)
    return FidelityReport(
        agent_name="fidelity-checker",
        iteration_idx=spec.iteration_idx,
        spec_id=spec.spec_id,
        overall_passed=overall,
        checks=checks,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True)
    ap.add_argument("--code-path", required=True)
    args = ap.parse_args()

    spec_dict = json.loads(Path(args.spec_json).read_text())
    spec = SignalSpec(**spec_dict)
    code = GeneratedCode(
        agent_name="manual", iteration_idx=spec.iteration_idx,
        spec_id=spec.spec_id, code_path=args.code_path,
        entry_function="signal", template_used="manual",
    )
    report = run_fidelity(spec, code)
    print(report.model_dump_json(indent=2))
