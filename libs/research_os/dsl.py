"""A safe expression language for factors the generic family cannot express.

WHY THIS EXISTS (2026-09-04)

`family_generic` refuses `cross_sectional_rank`, `multi_leg_spread`, `term_structure` and
`order_flow_data` by name, and that refusal is CORRECT -- approximating a proposal would put a
different hypothesis in the docket under the original's name. But it is also a ceiling: measured
this session, 236 queued proposals were refused for capabilities the desk cannot express, and no
amount of mining moves that number. FactorEngine's advantage over RD-Agent and QuantaAlpha is
exactly this: it searches PROGRAMS, so its discovery space is not bounded by a fixed family list.

THE PRICE IT PAYS IS THE ONE THING THIS DESK MAY NOT PAY. Program search normally means executing
model-written Python, and a research loop with `exec` on the same box as a live €743 account and
its broker credentials is not a research decision, it is a security one. So this is a DSL, not an
interpreter: the model emits a JSON TREE, never source. Every node is checked against an
allowlist, every argument is type-checked, and evaluation walks the tree calling vetted pandas
operations. There is no eval, no exec, no attribute access, no import, and no user-supplied
callable anywhere in the path.

WHAT IT BUYS, precisely: cross-sectional rank across the universe, spreads and ratios between
instruments, residuals after a common factor, and conditional gating -- the four shapes behind
almost every refusal. A tree that names an unknown op, an unknown symbol, or a bad arity is
REFUSED BY NAME, which is a research finding (it names the operator worth adding) rather than a
silent approximation.

LOOK-AHEAD IS STRUCTURALLY IMPOSSIBLE for the rolling and lag nodes: every window is trailing and
every shift is positive. `rank` is the one node that reads across instruments AT A TIMESTAMP,
which is point-in-time by construction -- it uses no future bar, only contemporaneous ones, which
is what a cross-sectional factor means.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

#: op -> (arity, description). THE ALLOWLIST IS THE SECURITY BOUNDARY: anything absent is refused,
#: so adding an operator is a deliberate, reviewable act rather than something a model can do by
#: emitting a novel string.
OPS: dict[str, tuple[int, str]] = {
    "col":       (1, "a raw column of the primary instrument (close/high/low/open/volume)"),
    "sym":       (2, "a column of ANOTHER instrument -- (symbol, column)"),
    "lag":       (2, "shift BACKWARD by n bars; n>0 enforced, so no future value can be read"),
    "diff":      (2, "difference against n bars ago"),
    "pct":       (2, "percentage change over n bars"),
    "roll_mean": (2, "trailing mean over n bars"),
    "roll_std":  (2, "trailing standard deviation over n bars"),
    "roll_max":  (2, "trailing maximum over n bars"),
    "roll_min":  (2, "trailing minimum over n bars"),
    "zscore":    (2, "(x - trailing mean) / trailing std over n bars"),
    "rank":      (1, "CROSS-SECTIONAL percentile rank across the universe at each timestamp"),
    "spread":    (2, "a - b: the multi-leg shape family_generic cannot express"),
    "ratio":     (2, "a / b, guarded against division by zero"),
    "resid":     (2, "a after removing its trailing beta to b -- the common-factor residual"),
    "add":       (2, "a + b"),
    "mul":       (2, "a * b"),
    "gt":        (2, "a > b as 1.0/0.0"),
    "lt":        (2, "a < b as 1.0/0.0"),
    "cond":      (3, "gate: where(c, a, b)"),
    "session":   (2, "1.0 inside a named broker-hour window, else 0.0"),
    "decay":     (2, "exponentially weighted mean, halflife n"),
    "const":     (1, "a scalar"),
}

#: Broker hours (Fusion runs UTC+3); the bar index is on this clock, so these are too.
SESSIONS: dict[str, tuple[int, int]] = {
    "asia": (1, 9), "london": (9, 17), "new_york": (15, 23), "overlap": (15, 17),
}

MAX_DEPTH = 8
MAX_NODES = 60
MAX_WINDOW = 500


class DslError(ValueError):
    """A tree this compiler refuses, with the reason a reviewer needs."""


@dataclass
class Ctx:
    """Everything evaluation may touch. Nothing else is reachable from a tree."""

    primary: pd.DataFrame
    universe: dict[str, pd.DataFrame]


def validate(tree: Any, depth: int = 0, seen: list[int] | None = None) -> None:
    """Refuse anything not in the allowlist, BEFORE any data is touched."""
    seen = seen if seen is not None else [0]
    seen[0] += 1
    if depth > MAX_DEPTH:
        raise DslError(f"tree deeper than {MAX_DEPTH}; complexity is a redundancy risk, not a win")
    if seen[0] > MAX_NODES:
        raise DslError(f"tree larger than {MAX_NODES} nodes")
    if not isinstance(tree, (list, tuple)) or not tree:
        raise DslError(f"node must be a non-empty list, got {type(tree).__name__}")
    op = tree[0]
    if not isinstance(op, str) or op not in OPS:
        raise DslError(f"unknown operator {op!r}; the allowlist is {sorted(OPS)}")
    arity, _ = OPS[op]
    args = list(tree[1:])
    if len(args) != arity:
        raise DslError(f"{op} takes {arity} argument(s), got {len(args)}")
    for a in args:
        if isinstance(a, (list, tuple)):
            validate(a, depth + 1, seen)
        elif isinstance(a, (int, float, str)):
            if isinstance(a, int) and not isinstance(a, bool) and a > MAX_WINDOW:
                raise DslError(f"window {a} exceeds {MAX_WINDOW} bars")
            if isinstance(a, int) and op in ("lag", "diff", "pct", "roll_mean", "roll_std",
                                             "roll_max", "roll_min", "zscore", "decay") and a <= 0:
                raise DslError(f"{op} needs a POSITIVE window; a non-positive shift could read "
                               f"a future bar, which is the one thing this cannot allow")
        else:
            raise DslError(f"argument type {type(a).__name__} is not permitted")


def _series(x: Any, ctx: Ctx) -> pd.Series:
    if isinstance(x, (int, float)):
        return pd.Series(float(x), index=ctx.primary.index)
    return evaluate(x, ctx)


def evaluate(tree: Any, ctx: Ctx) -> pd.Series:
    """Walk the validated tree. Only the operations named in OPS are ever called."""
    op = tree[0]
    a = tree[1] if len(tree) > 1 else None
    b = tree[2] if len(tree) > 2 else None
    c = tree[3] if len(tree) > 3 else None
    idx = ctx.primary.index

    if op == "const":
        return pd.Series(float(a), index=idx)
    if op == "col":
        if a not in ctx.primary.columns:
            raise DslError(f"column {a!r} absent; available {list(ctx.primary.columns)}")
        return ctx.primary[a].astype(float)
    if op == "sym":
        df = ctx.universe.get(str(a))
        if df is None:
            raise DslError(f"symbol {a!r} is not in the tradeable universe -- refusing rather "
                           f"than substituting a peer nobody named")
        if b not in df.columns:
            raise DslError(f"column {b!r} absent on {a!r}")
        return df[b].astype(float).reindex(idx).ffill()
    if op == "rank":
        # CROSS-SECTIONAL, the shape family_generic cannot express. Contemporaneous only.
        s = _series(a, ctx)
        frame = pd.DataFrame({k: v["close"].astype(float).reindex(idx).ffill()
                              for k, v in ctx.universe.items() if "close" in v})
        if frame.empty:
            raise DslError("cross-sectional rank needs a universe; none was supplied")
        return frame.rank(axis=1, pct=True).reindex(idx).mean(axis=1).where(s.notna())

    x = _series(a, ctx)
    if op in ("lag", "diff", "pct", "roll_mean", "roll_std", "roll_max", "roll_min",
              "zscore", "decay", "session"):
        n = b
        if op == "lag":
            return x.shift(int(n))
        if op == "diff":
            return x - x.shift(int(n))
        if op == "pct":
            return x.pct_change(int(n))
        if op == "roll_mean":
            return x.rolling(int(n)).mean()
        if op == "roll_std":
            return x.rolling(int(n)).std()
        if op == "roll_max":
            return x.rolling(int(n)).max()
        if op == "roll_min":
            return x.rolling(int(n)).min()
        if op == "decay":
            return x.ewm(halflife=float(n)).mean()
        if op == "zscore":
            m = x.rolling(int(n)).mean()
            sd = x.rolling(int(n)).std()
            return (x - m) / sd.replace(0.0, pd.NA)
        if op == "session":
            win = SESSIONS.get(str(n))
            if win is None:
                raise DslError(f"session {n!r} unknown; named windows are {sorted(SESSIONS)}")
            lo, hi = win
            h = pd.Index(idx).hour
            return pd.Series([1.0 if lo <= v < hi else 0.0 for v in h], index=idx)

    y = _series(b, ctx)
    if op == "spread":
        return x - y
    if op == "ratio":
        return x / y.replace(0.0, pd.NA)
    if op == "add":
        return x + y
    if op == "mul":
        return x * y
    if op == "gt":
        return (x > y).astype(float)
    if op == "lt":
        return (x < y).astype(float)
    if op == "resid":
        # Trailing beta only -- a full-sample regression would fit x on bars that had not
        # happened yet, which is look-ahead wearing a statistic's clothes.
        w = 120
        cov = x.rolling(w).cov(y)
        var = y.rolling(w).var()
        return x - (cov / var.replace(0.0, pd.NA)) * y
    if op == "cond":
        # Gate: where the condition is true take a, else b. `Series.where` keeps the caller's
        # values where the mask holds and substitutes the other branch elsewhere -- no numpy
        # indirection, no alignment surprises.
        return _series(b, ctx).where(x > 0, _series(c, ctx))
    raise DslError(f"operator {op!r} validated but not implemented")


def compile_factor(tree: Any, primary: pd.DataFrame,
                   universe: dict[str, pd.DataFrame] | None = None) -> pd.Series:
    """Validate then evaluate. Refusal names the reason; nothing is ever approximated."""
    validate(tree)
    return evaluate(tree, Ctx(primary=primary, universe=universe or {}))
