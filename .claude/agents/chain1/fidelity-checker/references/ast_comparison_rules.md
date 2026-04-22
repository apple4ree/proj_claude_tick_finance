# AST-Based Fidelity Comparison Rules

Programmatic recipes implementing the 6 CLAUDE.md §②.75 checks. Used by `fidelity-checker` to issue deterministic verdicts.

---

## Check 1 — Feature formula 일치

**Normalization pipeline applied to both sides**:

1. Parse with `ast.parse(expr)`.
2. Walk and substitute all identifiers using a rename map (alphabetize).
3. Collapse commutative operators: sort operands of `ast.BinOp(op=Add|Mult)`, `ast.BoolOp(op=And|Or)`.
4. Constant-fold any trivial arithmetic (`x + 0 → x`).
5. Re-serialize via `ast.unparse` → compare strings.

Edge case: if spec.formula is written in natural Korean (e.g., "obi_1 이 0.5 이상이면"), the signal-generator is responsible for always emitting the canonical form. The fidelity-checker does not attempt natural-language parsing.

## Check 2 — Threshold / horizon 일치

Extract from generated module:
- `THRESHOLD = <float>` — module-level assignment
- `HORIZON_TICKS = <int>`
- `DIRECTION = <"long_if_pos" | "long_if_neg">`

Compare field-wise. Floats: `abs(a - b) < 1e-9`. Strings: exact. Ints: exact.

## Check 3 — Entry 조건 일치

Verify `signal()` return type contract:
- AST must find a single `ast.Return` whose value is a numeric expression (float-valued).
- NOT: `return (side, px)`, `return True`, `return Order(...)`, etc.

If generator erroneously embedded decision logic, this check catches it.

## Check 4 — Execution=1 강제

Banned identifier list (case-insensitive substring match in the source):
```
submit_buy_order, submit_sell_order, submit_order, cancel, order_id,
LIMIT, MARKET, GTC, GTX, IOC, FOK,
skew, trailing, stop_loss, profit_target, time_stop, inventory,
position, ttl,
```

Any occurrence → `passed: false` with `detail: "banned identifier found: <name> at line <n>"`.

## Check 5 — Lookahead 부재

Banned regex (case-insensitive): `_t\+|next_|fwd_|future_|post_trade|post_tick|_later`

Also banned: any indexing beyond allowed depth (Check 6 reuses this), any attribute access to `snap._next`, `snap.future`, etc.

## Check 6 — 미선언 side effect 부재

Banned imports and calls:
```
import random, import numpy.random, from numpy import random
import time, time.time, time.sleep
from datetime import datetime, datetime.now, datetime.utcnow
open(, os.write, os.remove, shutil.,
print(, sys.stdout
urllib, requests, http.client
```

Also forbidden: any assignment to a name starting with `__` (module internals), any `global` statement, any `nonlocal`.

---

## Failure protocol

If `overall_passed == false`:
- Orchestrator passes the full FidelityReport back to `code-generator` for retry.
- Retry is capped at 3 attempts per spec. After 3 failures, the spec is retired with feedback tag `code_infeasible`.

## Success evidence template

For every `FidelityCheck.passed == true`, populate `detail` like:
```
"Check 1: AST equal after normalization. LHS=`obi_1 - 0.3*obi_5`, RHS=`obi_1 - 0.3*obi_5` (post-sort)"
"Check 2: THRESHOLD=0.5 ≡ spec; HORIZON_TICKS=1 ≡ spec; DIRECTION='long_if_pos' ≡ spec"
```

This keeps the audit trail human-readable.
