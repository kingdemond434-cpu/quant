"""The expression language the mathematicians invent IN, its canonicaliser, and its translator.

AN EXPRESSION IS ITS RECIPE. A tree is plain JSON -- a leaf is a variable name (a string) or a
constant (a number), a node is a list `[op, child, ...args]` -- so an object that leaves this
module can be stored, hashed, diffed, re-evaluated and executed without a deserialiser. The
representation is deliberately the same shape as `libs.research.alpha_grammar`, because a tree
that maps into that grammar can be TRADED by the `formula` family exactly as written, and one
that cannot is recorded as a discovery with the gap named rather than quietly approximated.

FORMAL SIMPLIFICATION IS ALGEBRAIC CANONICALISATION, and it is what makes dedup honest.
`simplify` folds constants, removes identities (x+0, x*1, x/1, x-x, lag(x,0)), collapses
involutions (neg(neg(x)), abs(abs(x)), sign(sign(x))), and orders the children of every
commutative operator by their own canonical string. Two scientists that invent the same law by
different routes therefore produce the SAME canonical string and charge ONE trial instead of two.
sympy would do the algebra more thoroughly and IS used when it imports (`algebraic_key`, which
turns every non-arithmetic subtree into an opaque atom and normalises the algebra around it); it
does not import on this box (measured 2026-09-17), so the canonicaliser below is the desk's own
and is what runs. Nothing REQUIRES sympy: a dedup that depended on an optional dependency would
silently double-charge trials on the machine that lacks it.

EVERY OPERATOR IS CAUSAL BY CONSTRUCTION. Windows look back only and there is no operator that
can reach a later bar, so an expression cannot leak whatever shape the search gives it. Warm-up
is NaN, never a backfilled value, and every consumer reads NaN as "no signal" -- an absent number
is not a zero.

WINDOWS ARE alpha_grammar's WINDOWS, on purpose. A lag set of our own would have made half the
inventions untranslatable and therefore untradeable, which is the expensive kind of elegance.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import warnings
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import numpy as np

Expr = Any                                        # str | float | int | list[Any]; JSON-shaped

#: Window / lag arguments. Identical to `libs.research.alpha_grammar.WINDOWS` so that every
#: windowed node this grammar can build has an exact counterpart there.
WINDOWS: tuple[int, ...] = (2, 3, 5, 8, 12, 24, 48, 120, 240)

UNARY: tuple[str, ...] = ("neg", "abs", "sign", "log", "sqrt")
#: `[op, child, window]`
WINDOWED: tuple[str, ...] = ("lag", "diff", "curv", "rmean", "rstd", "z", "rmin", "rmax")
BINARY: tuple[str, ...] = ("add", "sub", "mul", "div", "max2", "min2")
#: `[op, child, constant]` -> an indicator in {0, 1}
THRESHOLD: tuple[str, ...] = ("gt", "lt")
OPERATORS: tuple[str, ...] = UNARY + WINDOWED + BINARY + THRESHOLD

COMMUTATIVE: frozenset[str] = frozenset({"add", "mul", "max2", "min2"})
#: Deep enough for a second-order Haar scattering path (depth 10) and the ratio of two of them
#: (depth 11), and for a three-symbol event sequence. This bounds what the SEARCH may build;
#: what may be TRADED is bounded again by `alpha_grammar.MAX_DEPTH` (5) inside `tradeable`,
#: which is the door that matters.
MAX_DEPTH = 12

#: Bar terminals every panel carries, in the names `libs.research.alpha_grammar` uses for them,
#: so translation is a rename of nothing at all.
BAR_VARIABLES: tuple[str, ...] = ("close", "open", "high", "low", "ret", "range", "body",
                                  "activity", "spread", "atr", "vol", "flow")

#: How many distinct symbols the MDL code has to name per node. Used for the description length,
#: never for a screen: a bigger vocabulary makes every tree more expensive, which is correct.
_VOCAB = len(OPERATORS) + len(BAR_VARIABLES) + len(WINDOWS) + 8

try:                                                            # pragma: no cover - not on box
    import sympy as _sympy
    HAVE_SYMPY = True
except Exception:                                               # pragma: no cover
    _sympy = None
    HAVE_SYMPY = False


# ------------------------------------------------------------------------------- construction
@contextlib.contextmanager
def quiet() -> Iterator[None]:
    """Numpy's empty-slice and divide warnings, silenced WHERE THEY ARE EXPECTED.

    A rolling window that is entirely warm-up IS an empty slice, and NaN is the right answer for
    it -- but pytest runs this repo with `filterwarnings = error`, so an expected RuntimeWarning
    is a test failure. The suppression is scoped to the blocks that legitimately produce them and
    is never applied around a computation whose NaNs would be a defect.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with np.errstate(all="ignore"):
            yield


def is_constant(node: Expr) -> bool:
    return isinstance(node, (int, float)) and not isinstance(node, bool)


def is_variable(node: Expr) -> bool:
    return isinstance(node, str)


def variables_in(node: Expr) -> set[str]:
    """Every variable name the tree reads."""
    if is_variable(node):
        return {str(node)}
    if isinstance(node, (list, tuple)) and node:
        out: set[str] = set()
        for child in node[1:]:
            if isinstance(child, (str, list, tuple)):
                out |= variables_in(child)
        return out
    return set()


def depth(node: Expr) -> int:
    if not isinstance(node, (list, tuple)) or not node:
        return 1
    return 1 + max((depth(c) for c in node[1:] if isinstance(c, (str, list, tuple))), default=0)


def nodes(node: Expr) -> int:
    """MDL node count: every leaf and every operator counts once."""
    if not isinstance(node, (list, tuple)) or not node:
        return 1
    return 1 + sum(nodes(c) for c in node[1:] if isinstance(c, (str, list, tuple)))


def parameters(node: Expr) -> int:
    """Free numeric parameters: constants and window/threshold arguments the search chose."""
    if is_constant(node):
        return 1
    if not isinstance(node, (list, tuple)) or not node:
        return 0
    total = 0
    for child in node[1:]:
        if isinstance(child, (list, tuple, str)):
            total += parameters(child)
        elif is_constant(child):
            total += 1
    return total


def mdl_bits(node: Expr) -> float:
    """Description length of the tree in bits: nodes at log2(vocabulary), parameters at 8 bits.

    A parameter costs more than a symbol because a parameter is a number the SEARCH picked, and
    the burden it creates is the whole reason this module exists.
    """
    return nodes(node) * math.log2(_VOCAB) + parameters(node) * 8.0


def valid(node: Expr, variables: Sequence[str] | None = None) -> bool:
    """Structural validity, and -- when `variables` is given -- that every leaf is available."""
    if is_constant(node):
        return True
    if is_variable(node):
        return variables is None or str(node) in set(variables)
    if not isinstance(node, (list, tuple)) or not node or depth(node) > MAX_DEPTH:
        return False
    op = node[0]
    if op in UNARY:
        return len(node) == 2 and valid(node[1], variables)
    if op in WINDOWED:
        return (len(node) == 3 and valid(node[1], variables)
                and isinstance(node[2], int) and node[2] in WINDOWS)
    if op in THRESHOLD:
        return len(node) == 3 and valid(node[1], variables) and is_constant(node[2])
    if op in BINARY:
        return len(node) == 3 and all(valid(c, variables) for c in node[1:3])
    return False


def to_str(node: Expr) -> str:
    """The canonical string. Equal strings are the same hypothesis and hash the same."""
    if is_variable(node):
        return str(node)
    if is_constant(node):
        value = float(node)
        return f"{value:.6g}"
    if not isinstance(node, (list, tuple)) or not node:
        return "?"
    op = str(node[0])
    args = [to_str(c) if isinstance(c, (str, list, tuple)) else f"{float(c):.6g}"
            for c in node[1:]]
    infix = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
    if op in infix and len(args) == 2:
        return f"({args[0]} {infix[op]} {args[1]})"
    return f"{op}({', '.join(args)})"


def fingerprint(node: Expr) -> str:
    """Content hash of the CANONICAL form: the identity two scientists must collide on."""
    return hashlib.sha256(algebraic_key(node).encode("utf-8")).hexdigest()[:20]


def _to_sympy(node: Expr, atoms: dict[str, Any]) -> Any:
    """The tree as a sympy expression, with every NON-ARITHMETIC subtree as an opaque atom.

    The atom trick is what makes this general: `z(close, 240)` is not algebra, so it becomes one
    symbol keyed by its own canonical string, and sympy then normalises whatever arithmetic is
    built AROUND it. Nothing is lost and no operator needs a sympy counterpart.
    """
    if is_constant(node):
        return _sympy.Float(float(node))
    if is_variable(node) or not isinstance(node, (list, tuple)) or not node:
        key = to_str(node)
        atoms.setdefault(key, _sympy.Symbol(f"a{len(atoms)}"))
        return atoms[key]
    op = str(node[0])
    if op in ("add", "sub", "mul", "div"):
        left = _to_sympy(node[1], atoms)
        right = _to_sympy(node[2], atoms)
        return {"add": left + right, "sub": left - right, "mul": left * right,
                "div": left / right}[op]
    if op == "neg":
        return -_to_sympy(node[1], atoms)
    key = to_str(node)
    atoms.setdefault(key, _sympy.Symbol(f"a{len(atoms)}"))
    return atoms[key]


def algebraic_key(node: Expr) -> str:
    """The identity string: sympy's normal form when sympy imports, the canonicaliser's otherwise.

    MEASURED 2026-09-17: sympy is not installed on this box, so `to_str(simplify(...))` is what
    actually runs and is what the tests pin. The sympy path is not decoration -- a box that gains
    sympy gets strictly better dedup (`(a + b) - b` collapses) without any other change -- but it
    is never REQUIRED, because a dedup that depends on an optional dependency would silently
    double-charge trials on the machine that lacks it.
    """
    tree = simplify(node)
    if not HAVE_SYMPY:
        return to_str(tree)
    try:
        return str(_sympy.simplify(_to_sympy(tree, {})))
    except Exception:                                            # pragma: no cover - sympy-only
        return to_str(tree)


# ------------------------------------------------------------------- formal simplification
def _fold(op: str, args: list[float]) -> float | None:
    try:
        if op == "neg":
            return -args[0]
        if op == "abs":
            return abs(args[0])
        if op == "sign":
            return float(np.sign(args[0]))
        if op == "log":
            return math.log(abs(args[0]) + 1e-12)
        if op == "sqrt":
            return math.sqrt(abs(args[0]))
        if op == "add":
            return args[0] + args[1]
        if op == "sub":
            return args[0] - args[1]
        if op == "mul":
            return args[0] * args[1]
        if op == "div":
            return args[0] / args[1] if abs(args[1]) > 1e-12 else 0.0
        if op == "max2":
            return max(args[0], args[1])
        if op == "min2":
            return min(args[0], args[1])
        if op in ("lag", "diff", "curv", "rmean", "rstd", "z", "rmin", "rmax"):
            return {"diff": 0.0, "curv": 0.0, "rstd": 0.0, "z": 0.0}.get(op, args[0])
        if op == "gt":
            return 1.0 if args[0] > args[1] else 0.0
        if op == "lt":
            return 1.0 if args[0] < args[1] else 0.0
    except (ValueError, OverflowError, ZeroDivisionError):
        return None
    return None


def simplify(node: Expr) -> Expr:
    """Algebraic canonicalisation. Equivalent formulas become the SAME tree, so they dedupe.

    This is the "formal simplification" step of the principal's pipeline, and its purpose is
    economic as much as aesthetic: two traditions that invent the same law by different routes
    must charge ONE trial, not two, or the multiple-testing burden is a fiction.
    """
    if is_variable(node) or is_constant(node):
        return node
    if not isinstance(node, (list, tuple)) or not node:
        return node
    op = str(node[0])
    children = [simplify(c) if isinstance(c, (str, list, tuple)) else c for c in node[1:]]

    if all(is_constant(c) for c in children):
        folded = _fold(op, [float(c) for c in children])
        if folded is not None and math.isfinite(folded):
            return round(float(folded), 9)

    if op in ("neg", "abs", "sign") and isinstance(children[0], (list, tuple)) \
            and children[0] and str(children[0][0]) == op:
        return children[0] if op in ("abs", "sign") else children[0][1]
    if op in ("abs", "sqrt") and isinstance(children[0], (list, tuple)) and children[0] \
            and str(children[0][0]) in ("abs", "neg"):
        return simplify([op, children[0][1]])

    if op in ("add", "sub") and is_constant(children[1]) and abs(float(children[1])) < 1e-12:
        return children[0]
    if op == "add" and is_constant(children[0]) and abs(float(children[0])) < 1e-12:
        return children[1]
    if op in ("mul", "div") and is_constant(children[1]) and abs(float(children[1]) - 1.0) < 1e-12:
        return children[0]
    if op == "mul" and is_constant(children[0]) and abs(float(children[0]) - 1.0) < 1e-12:
        return children[1]
    if op == "mul" and any(is_constant(c) and abs(float(c)) < 1e-12 for c in children):
        return 0.0
    if op == "sub" and to_str(children[0]) == to_str(children[1]):
        return 0.0
    if op == "div" and to_str(children[0]) == to_str(children[1]):
        return 1.0
    if op in ("max2", "min2") and to_str(children[0]) == to_str(children[1]):
        return children[0]
    if op in ("lag", "diff", "curv") and isinstance(children[1], int) and children[1] == 0:
        return children[0] if op == "lag" else 0.0

    if op in COMMUTATIVE:
        children = sorted(children, key=lambda c: to_str(c) if isinstance(c, (str, list, tuple))
                          else f"{float(c):.6g}")
    return [op, *children]


def canonical(node: Expr) -> tuple[Expr, str]:
    """(simplified tree, canonical string). The pair every MathObject stores."""
    tree = simplify(node)
    return tree, to_str(tree)


# ------------------------------------------------------------------------------- evaluation
def _roll(values: np.ndarray, window: int, what: str) -> np.ndarray:
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    if window <= 0 or n < window:
        return out
    view = np.lib.stride_tricks.sliding_window_view(values, window)
    with quiet():
        if what == "mean":
            block = np.nanmean(view, axis=1)
        elif what == "std":
            block = np.nanstd(view, axis=1, ddof=1) if window > 1 else np.zeros(view.shape[0])
        elif what == "min":
            block = np.nanmin(view, axis=1)
        else:
            block = np.nanmax(view, axis=1)
    out[window - 1:] = block
    return out


def _shift(values: np.ndarray, k: int) -> np.ndarray:
    out = np.full(values.size, np.nan, dtype=float)
    if 0 < k < values.size:
        out[k:] = values[:-k]
    elif k == 0:
        out[:] = values
    return out


def evaluate(node: Expr, frames: Mapping[str, np.ndarray], length: int | None = None
             ) -> np.ndarray:
    """Pure arithmetic on aligned columns. RAISES NOTHING.

    An expression that cannot be computed on the frames it is given -- a variable the panel does
    not carry, a window longer than the history -- returns all-NaN, which every consumer reads as
    "no signal". That is the only safe behaviour for a search that invents its own trees.
    """
    n = length if length is not None else (len(next(iter(frames.values()))) if frames else 0)
    if is_constant(node):
        return np.full(n, float(node), dtype=float)
    if is_variable(node):
        series = frames.get(str(node))
        if series is None:
            return np.full(n, np.nan, dtype=float)
        return np.asarray(series, dtype=float)
    if not isinstance(node, (list, tuple)) or not node:
        return np.full(n, np.nan, dtype=float)

    op = str(node[0])
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        if op in UNARY:
            x = evaluate(node[1], frames, n)
            if op == "neg":
                return -x
            if op == "abs":
                return np.abs(x)
            if op == "sign":
                return np.sign(x)
            if op == "log":
                return np.log(np.abs(x) + 1e-12)
            return np.sqrt(np.abs(x))
        if op in WINDOWED:
            x = evaluate(node[1], frames, n)
            w = int(node[2])
            if op == "lag":
                return _shift(x, w)
            if op == "diff":
                return x - _shift(x, w)
            if op == "curv":
                return x - 2.0 * _shift(x, w) + _shift(x, 2 * w)
            if op == "rmean":
                return _roll(x, w, "mean")
            if op == "rstd":
                return _roll(x, w, "std")
            if op == "rmin":
                return _roll(x, w, "min")
            if op == "rmax":
                return _roll(x, w, "max")
            sd = _roll(x, w, "std")
            return np.where(np.abs(sd) > 1e-12, (x - _roll(x, w, "mean")) / sd, np.nan)
        if op in THRESHOLD:
            x = evaluate(node[1], frames, n)
            c = float(node[2])
            hit = (x > c) if op == "gt" else (x < c)
            return np.where(np.isfinite(x), hit.astype(float), np.nan)
        if op in BINARY:
            a = evaluate(node[1], frames, n)
            b = evaluate(node[2], frames, n)
            if op == "add":
                return a + b
            if op == "sub":
                return a - b
            if op == "mul":
                return a * b
            if op == "div":
                return np.where(np.abs(b) > 1e-12, a / np.where(np.abs(b) > 1e-12, b, 1.0),
                                np.nan)
            if op == "max2":
                return np.maximum(a, b)
            return np.minimum(a, b)
    return np.full(n, np.nan, dtype=float)


# --------------------------------------------------------------------------- random programs
def random_expr(rng: np.random.Generator, variables: Sequence[str], max_depth: int = 3,
                tries: int = 30) -> Expr:
    """A random tree this grammar accepts. A bare variable is the floor after `tries`."""
    pool = list(variables) or list(BAR_VARIABLES)
    for _ in range(max(1, tries)):
        tree = _draw(rng, pool, max_depth)
        if valid(tree, pool):
            return simplify(tree)
    return pool[int(rng.integers(len(pool)))]


def _draw(rng: np.random.Generator, pool: Sequence[str], budget: int) -> Expr:
    if budget <= 1 or rng.random() < 0.25:
        if rng.random() < 0.12:
            return round(float(rng.normal(0.0, 1.0)), 3)
        return str(pool[int(rng.integers(len(pool)))])
    op = str(OPERATORS[int(rng.integers(len(OPERATORS)))])
    if op in UNARY:
        return [op, _draw(rng, pool, budget - 1)]
    if op in WINDOWED:
        return [op, _draw(rng, pool, budget - 1), int(WINDOWS[int(rng.integers(len(WINDOWS)))])]
    if op in THRESHOLD:
        return [op, _draw(rng, pool, budget - 1), round(float(rng.normal(0.0, 1.0)), 3)]
    return [op, _draw(rng, pool, budget - 1), _draw(rng, pool, budget - 1)]


def mutate(node: Expr, rng: np.random.Generator, variables: Sequence[str]) -> Expr:
    """Replace one uniformly chosen subtree with a fresh draw of the same depth budget."""
    sites = _sites(node)
    if not sites:
        return random_expr(rng, variables, 2)
    target = int(rng.integers(len(sites)))
    replacement = random_expr(rng, variables, max(1, min(3, depth(sites[target]))))
    return simplify(_replace(node, target, replacement, [0]))


def crossover(left: Expr, right: Expr, rng: np.random.Generator) -> Expr:
    """Swap a random subtree of `left` for a random subtree of `right`."""
    donors = _sites(right)
    sites = _sites(left)
    if not donors or not sites:
        return left
    graft = donors[int(rng.integers(len(donors)))]
    target = int(rng.integers(len(sites)))
    return simplify(_replace(left, target, graft, [0]))


def _sites(node: Expr) -> list[Expr]:
    out: list[Expr] = [node]
    if isinstance(node, (list, tuple)) and node:
        for child in node[1:]:
            if isinstance(child, (str, list, tuple)):
                out.extend(_sites(child))
    return out


def _replace(node: Expr, index: int, graft: Expr, counter: list[int]) -> Expr:
    here = counter[0] - 1
    if here == index:
        return graft
    if not isinstance(node, (list, tuple)) or not node:
        return node
    out: list[Any] = [node[0]]
    for child in node[1:]:
        if isinstance(child, (str, list, tuple)):
            counter[0] += 1
            out.append(_replace(child, index, graft, counter))
        else:
            out.append(child)
    return out


# ------------------------------------------------------------ translation to the trade grammar
#: mathlab operator -> `libs.research.alpha_grammar` operator, where the semantics are identical.
_ALPHA_OPS: dict[str, str] = {
    "neg": "neg", "abs": "abs", "sign": "sign",
    "lag": "delay", "diff": "delta", "rmean": "mean", "rstd": "std", "z": "zscore",
    "rmin": "min", "rmax": "max",
    "add": "add", "sub": "sub", "mul": "mul", "div": "div", "max2": "max2", "min2": "min2",
}
#: Operators with NO counterpart there. An object using one is registered as a discovery and
#: NEVER donated as an executable recipe -- an approximation donated as an exact rule is a lie.
UNTRANSLATABLE: tuple[str, ...] = ("log", "sqrt", "gt", "lt")


def to_alpha_grammar(node: Expr) -> Expr | None:
    """The same law in `libs.research.alpha_grammar`, or None when it cannot be said there.

    `curv(x, k)` has no single counterpart and is rewritten EXACTLY as
    `delta(x, k) - delay(delta(x, k), k)` = x_t - 2 x_{t-k} + x_{t-2k}, which is the curvature the
    principal's example names. Every other windowed operator is a rename. A constant leaf, a
    threshold, a log or a square root cannot be said there at all, and None is the honest answer.
    """
    if is_constant(node):
        return None
    if is_variable(node):
        return str(node) if str(node) in BAR_VARIABLES else None
    if not isinstance(node, (list, tuple)) or not node:
        return None
    op = str(node[0])
    if op in UNTRANSLATABLE:
        return None
    if op == "curv":
        inner = to_alpha_grammar(node[1])
        k = int(node[2])
        if inner is None or k not in WINDOWS:
            return None
        delta = ["delta", inner, k]
        return ["sub", delta, ["delay", delta, k]]
    mapped = _ALPHA_OPS.get(op)
    if mapped is None:
        return None
    if op in WINDOWED:
        inner = to_alpha_grammar(node[1])
        return None if inner is None else [mapped, inner, int(node[2])]
    if op in UNARY:
        inner = to_alpha_grammar(node[1])
        return None if inner is None else [mapped, inner]
    left = to_alpha_grammar(node[1])
    right = to_alpha_grammar(node[2])
    if left is None or right is None:
        return None
    return [mapped, left, right]


def tradeable(node: Expr) -> tuple[Expr | None, str]:
    """(alpha_grammar expression, why not) -- the door between invention and execution.

    The expression must translate AND pass `alpha_grammar.is_valid`, which is structure plus the
    unit algebra: a tree that adds a price to a tick count is refused there and must be refused
    here too, or the desk would donate a recipe the family declines to trade.
    """
    translated = to_alpha_grammar(node)
    if translated is None:
        used = sorted({o for o in UNTRANSLATABLE if f"{o}(" in to_str(node)})
        why = (f"uses {', '.join(used)}, which libs/research/alpha_grammar has no operator for"
               if used else "a leaf is a constant or a non-bar variable the formula family "
                            "cannot supply as a frame")
        return None, why
    try:
        from libs.research.alpha_grammar import is_valid
    except Exception as exc:                                     # pragma: no cover - desk-only
        return None, f"alpha_grammar unimportable: {type(exc).__name__}"
    if not is_valid(translated, allow_drivers=False, terminals=BAR_VARIABLES):
        return None, ("alpha_grammar.is_valid refuses it: structure, type or the unit algebra "
                      "(a price added to a tick count is not constructible there)")
    return translated, ""


def to_json(node: Expr) -> str:
    return json.dumps(node, default=str)
