"""ONE rendering of a structured hypothesis into the (statement, features) the novelty gate reads.

WHY THIS IS ITS OWN MODULE. The gate compares a candidate against a compiled corpus of past
failures. That comparison is only meaningful if BOTH sides were rendered the same way -- the
corpus builder and the live generator must agree token-for-token on how a hypothesis becomes
text and a feature set. They started in `scripts/build_graveyard_priors.py`, which the live
generation path cannot import (a lib importing a script is backwards), so wiring the gate meant
either that inversion or a second copy of the renderer.

A second copy is the worse option and it is not hypothetical: this desk already measured the
novelty gate at 0% recall once. A renderer that drifts does not fail loudly -- similarity simply
decays toward zero, every candidate looks novel, and the gate reports a clean bill of health
while catching nothing. Sharing one implementation is what makes the measured recall a property
of the SYSTEM rather than of the replay script that measured it.

`params` accepts a dict or a JSON string because the two callers hold different shapes: the
builder reads `params_json` out of sqlite, the generator holds `Hypothesis.params`. Both render
identically -- that equivalence is asserted in the tests, since it is exactly the seam where a
silent drift would enter.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

Params = dict[str, object] | str | None


def _as_dict(params: Params) -> dict[str, object]:
    if isinstance(params, dict):
        return params
    try:
        loaded = json.loads(params or "{}")
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def params_keys(params: Params) -> tuple[str, ...]:
    """Sorted param NAMES. Values are deliberately excluded -- see candidate_features."""
    return tuple(sorted(str(k) for k in _as_dict(params)))


def params_text(params: Params) -> str:
    """`fast=10 slow=30` -- sorted so the same params always render to the same string."""
    p = _as_dict(params)
    return " ".join(
        f"{k}={p[k]:g}" if isinstance(p[k], (int, float)) and not isinstance(p[k], bool)
        else f"{k}={p[k]}"
        for k in sorted(p, key=str)
    )


def candidate_features(
    family: str, subtype: str, mechanism: str, params: Params
) -> tuple[str, ...]:
    """The MECHANISM SIGNATURE of a structured candidate -- symbol and param VALUES excluded.

    Excluding both is the point of the gate. The desk's content-hash dedupe already catches an
    exact re-run; what it misses is the same dead mechanism re-proposed on a different symbol or
    with a nudged window, which is how 195 redundant backtests got paid for in one campaign.
    """
    feats = [f"family:{family}", f"subtype:{subtype}"]
    if mechanism:
        feats.append(f"mech:{mechanism}")
    feats.extend(f"param:{k}" for k in params_keys(params))
    return tuple(feats)


def candidate_statement(
    family: str, subtype: str, mechanism: str, params: Params, symbols: Sequence[str]
) -> str:
    """Human/text form of a collapsed mechanism -- carries the detail the signature drops."""
    sym = ", ".join(sorted(symbols)[:12])
    more = f" and {len(symbols) - 12} more" if len(symbols) > 12 else ""
    ptxt = params_text(params)
    return (
        f"{family} {subtype} rule ({mechanism} mechanism)"
        + (f" with {ptxt}" if ptxt else "")
        + f", backtested and rejected on {len(symbols)} instrument-instances: {sym}{more}"
    )[:4000]
