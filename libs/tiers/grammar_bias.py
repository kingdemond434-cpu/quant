"""THE LEARNED GRAMMAR, READ BACK BY THE GENERATORS (Tier S layers 22 and 44).

`tier_s.organ_grammar` measures each operator's yield on the formulas the gauntlet has judged and
mines sub-expressions that recur across independent survivors, and writes both to
`desks/mt5/data/tier_s/grammar.json`. This is the one reader the generators share:
`bias()` returns the keyword arguments `alpha_grammar.random_expr` / `mutate` accept
(`op_weights`, `primitives`), so the vocabulary the desk learned is the vocabulary it samples.

Absent, stale or unreadable -> {} and the draw is exactly the uniform one it always was.
Retired operators are drawn LESS (the grammar floors every weight at a quarter of its class
mean), never removed: breadth is never cut by a learned prior.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GRAMMAR = ROOT / "desks" / "mt5" / "data" / "tier_s" / "grammar.json"
MAX_AGE_H = 72.0

_CACHE: dict[str, Any] = {"mtime": None, "bias": {}}


def bias(path: Path | None = None, max_age_h: float = MAX_AGE_H) -> dict[str, Any]:
    # A TEST RUN SAMPLES THE UNBIASED GRAMMAR. The seeded-sampler tests pin draws, and the box
    # holds a live grammar.json the build box does not; reading it under pytest would make the
    # same test pass on one machine and fail on the other. An explicit `path` still reads.
    if path is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    p = path or GRAMMAR
    try:
        m = p.stat().st_mtime
    except OSError:
        return {}
    if path is None and _CACHE["mtime"] == m:
        return dict(_CACHE["bias"])
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        at = datetime.fromisoformat(str(doc.get("generated_utc")))
    except (OSError, ValueError, TypeError):
        return {}
    if (datetime.now(UTC) - at).total_seconds() > max_age_h * 3600:
        return {}
    from libs.research import alpha_grammar as ag
    out: dict[str, Any] = {}
    w = doc.get("operator_weights") or {}
    if isinstance(w, dict) and w:
        out["op_weights"] = {str(k): float(v) for k, v in w.items()
                             if isinstance(v, (int, float))}
    prims = []
    for r in doc.get("primitives") or []:
        text = r.get("expression") if isinstance(r, dict) else None
        if not text:
            continue
        try:
            e = ag.from_str(str(text))
        except ValueError:
            continue
        if isinstance(e, list) and ag.is_valid(e):
            prims.append(e)
    if prims:
        out["primitives"] = prims
    if path is None:
        _CACHE.update(mtime=m, bias=out)
    return dict(out)
