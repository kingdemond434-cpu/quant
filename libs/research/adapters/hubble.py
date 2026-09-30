"""Hubble adapter (REBUILT, numpy only) -- the DSL/AST-constrained factor search rebuilt without
its LLM: expressions are ENUMERATED deterministically from a closed grammar (four primitives,
four unary and three binary operators, depth two) over the desk's own lagged design, every
expression evaluated on the same data, every one charged as a trial. The grammar is the
constraint; the ten gates are the judge."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "hubble"
CAPABILITY_FAMILY = "dsl_program_search"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True


def _rank(v: Any) -> Any:
    """Ranks in [0, 1] -- the transform every formulaic-alpha family is written in."""
    import numpy as np
    x = np.asarray(v, dtype=float)
    return np.argsort(np.argsort(x)).astype(float) / max(x.shape[0] - 1, 1)


def _ic(a: Any, b: Any) -> float:
    """Rank correlation of two aligned series, non-finite rows dropped. A MEASUREMENT of
    association, never a verdict: the sign picks the family and the gauntlet judges it."""
    import numpy as np
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    if int(m.sum()) < 30 or float(np.std(x[m])) <= 0.0 or float(np.std(y[m])) <= 0.0:
        return float("nan")
    return float(np.corrcoef(_rank(x[m]), _rank(y[m]))[0, 1])


def _fwd(frame: A.BarFrame) -> Any:
    """Next-bar log return, aligned to the bar the signal is known at (NaN in the last slot)."""
    import numpy as np
    return np.concatenate([frame.log_returns(), [np.nan]])


def _family(ic: float) -> str:
    """The SIGN chooses: a positive association is momentum, a negative one reversion. Never a
    strength threshold -- a weak association is donated exactly like a strong one."""
    return "trend_ma_cross" if ic > 0 else "mean_reversion_rsi"


UNARY: tuple[str, ...] = ("id", "sign", "abs", "square")
BINARY: tuple[str, ...] = ("mul", "add", "sub")


def _u(op: str, x: Any) -> Any:
    import numpy as np
    if op == "sign":
        return np.sign(x)
    if op == "abs":
        return np.abs(x)
    if op == "square":
        return x * x
    return x


def _b(op: str, x: Any, y: Any) -> Any:
    if op == "add":
        return x + y
    if op == "sub":
        return x - y
    return x * y


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 200 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    names = A.LAGGED_FEATURE_NAMES
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        X, y, _ = A.lagged_design(f)
        if X.shape[0] < 60:
            continue
        scored: list[tuple[str, float]] = []
        for i, ni in enumerate(names):
            for u in UNARY:
                if deadline.expired():
                    break
                trials += 1
                scored.append((f"{u}({ni})", _ic(_u(u, X[:, i]), y)))
            for j, nj in enumerate(names):
                if j <= i:
                    continue
                for op in BINARY:
                    if deadline.expired():
                        break
                    trials += 1
                    scored.append((f"{op}({ni},{nj})", _ic(_b(op, X[:, i], X[:, j]), y)))
        finite = [(e, v) for e, v in scored if not np.isnan(v)]
        reps.append({"kind": "expression_grammar", "symbol": f.symbol,
                     "primitives": list(names), "unary": list(UNARY), "binary": list(BINARY),
                     "n_expressions": len(scored), "n_measured": len(finite),
                     "expressions": [{"expr": e, "ic_rank": v} for e, v in finite],
                     "representation": "a closed AST grammar enumerated in full on one frame"})
        for expr, ic in sorted(finite, key=lambda kv: -abs(kv[1]))[:3]:
            cands.append(A.candidate(
                _family(ic), [f.symbol],
                f"{f.symbol} H1: the grammar expression {expr} over lagged returns and trailing "
                f"vol scores a rank IC of {ic:+.4f} against the next bar's return",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"expression": expr, "ic_rank": ic, "grammar_size": len(scored),
                          "method": "deterministic AST enumeration, depth two"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame produced a usable design matrix")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} expressions evaluated over {len(reps)} frames")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
