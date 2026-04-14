#!/usr/bin/env python3
"""Validate a spec.yaml without running the backtest.

Checks:
- YAML parses.
- load_spec() succeeds.
- All referenced signal primitives exist in SIGNAL_REGISTRY.
- entry.when / exit.when compile via safe_eval (name errors allowed,
  only syntactic/structural errors fail).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.dsl import safe_eval  # noqa: E402,F401
from engine.signals import SIGNAL_REGISTRY  # noqa: E402
from engine.spec import load_spec  # noqa: E402


def _check_expr(expr) -> str | None:
    if isinstance(expr, bool) or expr is None:
        return None
    try:
        ast.parse(str(expr), mode="eval")
    except SyntaxError as e:
        return f"syntax: {e}"
    return None


def _validate_python_strategy(spec_path: Path) -> list[str]:
    """For strategy_kind=python — ensure strategy.py loads and has Strategy."""
    import importlib.util

    strat_py = spec_path.parent / "strategy.py"
    if not strat_py.exists():
        return [f"strategy_kind=python but {strat_py} not found"]
    module_name = f"validate_strategy_{spec_path.parent.name}"
    loader_spec = importlib.util.spec_from_file_location(module_name, strat_py)
    if loader_spec is None or loader_spec.loader is None:
        return [f"failed to build loader for {strat_py}"]
    module = importlib.util.module_from_spec(loader_spec)
    sys.modules[module_name] = module
    try:
        loader_spec.loader.exec_module(module)
    except Exception as e:
        sys.modules.pop(module_name, None)
        return [f"{strat_py.name} import failed: {e}"]
    if not hasattr(module, "Strategy"):
        return [f"{strat_py.name}: top-level `Strategy` class is missing"]
    cls = module.Strategy
    if not callable(getattr(cls, "on_tick", None)):
        return [f"{strat_py.name}:Strategy must implement on_tick(snap, ctx)"]
    return []


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: validate_spec.py <path/to/spec.yaml>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    try:
        spec = load_spec(path)
    except Exception as e:
        print(f"load_spec failed: {e}", file=sys.stderr)
        sys.exit(1)

    errors: list[str] = []
    kind = str(spec.raw.get("strategy_kind") or "dsl").lower()

    if not spec.universe.symbols:
        errors.append("universe.symbols is empty")
    if not spec.universe.dates:
        errors.append("universe.dates is empty")

    if kind == "python":
        errors.extend(_validate_python_strategy(path))
    else:
        # DSL / built-in paths check signals and expressions
        for name, defn in (spec.signals or {}).items():
            if isinstance(defn, str):
                fn = defn
            elif isinstance(defn, dict):
                fn = defn.get("fn") or defn.get("primitive")
            else:
                errors.append(f"signal {name}: invalid def {defn!r}")
                continue
            if fn not in SIGNAL_REGISTRY:
                errors.append(f"signal {name}: unknown primitive {fn!r}")

        err = _check_expr(spec.entry.get("when"))
        if err:
            errors.append(f"entry.when {err}")
        err = _check_expr(spec.exit.get("when"))
        if err:
            errors.append(f"exit.when {err}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print(f"ok: {spec.name} ({kind})")


if __name__ == "__main__":
    main()
