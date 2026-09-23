"""WorldQuant BRAIN (public) adapter (REBUILT) -- the PUBLIC operator vocabulary measured against
the desk's own expression organs. Nothing of the platform runs here and no account is used; the
adapter reads this tree and reports which published operators the desk's DSL actually
implements, so a gap is a number instead of an impression."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "worldquant_brain_public"
CAPABILITY_FAMILY = "dsl_program_search"
LICENCE_EXPECTED = "N/A (public documentation)"
RUNS_WITHOUT_LIBRARY = True

#: Operator names published in the BRAIN documentation and the 101-alpha paper's notation.
OPERATORS: tuple[str, ...] = (
    "rank", "delta", "delay", "correlation", "covariance", "scale", "decay_linear", "ts_min",
    "ts_max", "ts_rank", "ts_argmax", "ts_argmin", "ts_sum", "product", "stddev", "signedpower",
    "abs", "log", "sign", "min", "max", "power", "winsorize", "zscore", "group_neutralize",
)
#: The desk organs that carry an expression vocabulary of their own.
DSL_FILES: tuple[str, ...] = (
    "libs/research/alpha_dsl.py", "libs/research/alpha_grammar.py",
    "libs/research/alpha_genome.py", "libs/research/adapters/hubble.py",
    "libs/research/adapters/alpha101.py",
)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    text = ""
    read: list[dict[str, Any]] = []
    for rel in DSL_FILES:
        p = root / rel
        try:
            body = p.read_text(encoding="utf-8") if p.exists() else ""
        except OSError as exc:
            read.append({"file": rel, "exists": p.exists(),
                         "why": f"{type(exc).__name__}: {exc}"[:120]})
            continue
        read.append({"file": rel, "exists": p.exists(), "bytes": len(body)})
        text += body
    if not text:
        return A.unmeasured(SYSTEM, bundle, "none of the desk's DSL organs could be read")
    present = [op for op in OPERATORS if op in text]
    missing = [op for op in OPERATORS if op not in text]
    return A.packet(
        SYSTEM, bundle, trials=len(OPERATORS),
        representations=[{
            "kind": "operator_vocabulary_coverage", "system": SYSTEM,
            "n_published": len(OPERATORS), "n_carried": len(present),
            "coverage": round(len(present) / len(OPERATORS), 4),
            "carried": present, "missing": missing, "files_read": read,
            "representation": ("which published BRAIN/101-alpha operators this desk's own "
                               "expression organs implement, measured against the tree")}],
        note=f"operator coverage {len(present)}/{len(OPERATORS)}")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
