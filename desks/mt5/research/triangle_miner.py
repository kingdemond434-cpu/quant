"""The triangles that EXIST, which is a fact about the quote set rather than a search.

WHY THIS FILE EXISTS AT ALL, and it is the reason `family_triangle` is not a sweep family.
`orthogonal_sweep.NOT_SOURCED_HERE` declines `lead_lag` with: "a sweep that paired every symbol
with every other would be an uncharged search over pairs." Triangles are worse -- N^3. On this
desk's 86 hypothesis-lane FX pairs that is 636,056 combinations, and enumerating them would be a
vast uncharged search whose survivors would owe a multiple-testing charge nobody levied.

But almost none of those combinations is a triangle. A triangle requires three currencies whose
three connecting pairs are ALL quoted by the broker, and that is decided by the quote set, not by
anything a search discovers. MEASURED on this registry, 2026-09-10:

    86 FX pairs, 27 currencies  ->  150 closed triangles

150, not 636,056: a factor of 4,240. The grid is therefore small, complete, and DETERMINED --
every cell is nameable in advance, the charge is 150 trials, and there is no version of this
that found its triangles by looking at returns.

ORIENTATION IS DERIVED, NOT SEARCHED. Whether a leg enters the implied price as quoted or
inverted follows from the two symbols' names: GBPUSD and USDJPY imply GBPJPY only if the second
is taken as quoted and the shared USD cancels. `orient` works that out per triangle and the
family is TOLD, because a family that tried both signs would be running two hypotheses while
reporting one.

WHAT THIS DELIBERATELY DOES NOT DO. It does not fetch bars, run backtests or score anything --
it names cells. The caller loads the three frames and hands them to `family_triangle`; keeping
enumeration separate is what lets the 150 be counted and charged before a single bar is read.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe" / "universe.json"

#: Only the classes whose edge this desk seeks statistically. `universe_policy` routes single-name
#: equities to the event lane, and a currency triangle is meaningless outside FX in any case.
FX_CLASSES = frozenset({"Forex", "Forex Exotics"})

#: A quotable FX symbol is exactly six letters: BASE then QUOTE. Anything else in the registry
#: (indices, metals spelled XAUUSD, crypto CFDs) is not a currency pair even when it looks like
#: one, and `FX_CLASSES` is what actually decides -- this is the shape check, not the test.
_PAIR = re.compile(r"^([A-Z]{3})([A-Z]{3})$")


@dataclass(frozen=True)
class Triangle:
    """One closed triangle: trade `target`, imply it from `leg_b` and `leg_c`."""

    target: str
    leg_b: str
    leg_c: str
    sign_b: int
    sign_c: int
    currencies: tuple[str, str, str]

    @property
    def cell(self) -> str:
        """The candidate's name. Stable and rebuildable: three symbols and two signs."""
        return f"{self.target}~{self.leg_b}{'+' if self.sign_b > 0 else '-'}" \
               f"{self.leg_c}{'+' if self.sign_c > 0 else '-'}"

    def to_dict(self) -> dict[str, Any]:
        return {"cell": self.cell, "target": self.target, "leg_b": self.leg_b,
                "leg_c": self.leg_c, "sign_b": self.sign_b, "sign_c": self.sign_c,
                "currencies": list(self.currencies)}


def fx_pairs(registry: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """`{symbol: (base, quote)}` for the registry's hypothesis-lane FX pairs."""
    out: dict[str, tuple[str, str]] = {}
    for sym, rec in registry.items():
        if not isinstance(rec, dict) or rec.get("asset_class") not in FX_CLASSES:
            continue
        m = _PAIR.match(str(sym))
        if m and m.group(1) != m.group(2):
            out[str(sym)] = (m.group(1), m.group(2))
    return out


def _log_price(sym: str, legs: dict[str, tuple[str, str]], num: str, den: str) -> int | None:
    """+1 if `sym` quotes num/den as-is, -1 if it quotes den/num, None if it is neither.

    log(num/den) = +log(sym) when sym IS num/den, and -log(sym) when sym is its reciprocal --
    which is the entire content of the sign the family is handed.
    """
    b, q = legs[sym]
    if (b, q) == (num, den):
        return 1
    if (b, q) == (den, num):
        return -1
    return None


def orient(target: str, leg_b: str, leg_c: str,
           legs: dict[str, tuple[str, str]]) -> Triangle | None:
    """The signs that make `leg_b` and `leg_c` imply `target`, or None if they do not.

    log(A/C) = log(A/B) + log(B/C). Each leg contributes +1 as quoted or -1 inverted, and the
    shared currency must cancel -- so a trio that does not close returns None rather than a
    plausible-looking sign pair.
    """
    if target not in legs or leg_b not in legs or leg_c not in legs:
        return None
    a, c = legs[target]
    shared = ({*legs[leg_b]} & {*legs[leg_c]}) - {a, c}
    if len(shared) != 1:
        return None
    (b,) = shared
    # WHICH LEG IS THE a->b ONE IS NOT THE CALLER'S ORDER (bug, caught 2026-09-10 by an
    # independent count: 101 triangles where a direct enumeration found 150). `a` and `c` are
    # re-derived from the TARGET's own quoting convention -- USDCAD is (USD, CAD), not
    # (CAD, USD) -- so after that line the caller's leg_b may connect `c` rather than `a`, and
    # `_log_price` correctly returned None for a leg that simply arrived in the other slot.
    # Silently, as 49 missing cells: the enumeration still looked principled and was a third
    # short. Choose the legs by which currency they actually carry.
    if a in legs[leg_b]:
        first, second = leg_b, leg_c
    elif a in legs[leg_c]:
        first, second = leg_c, leg_b
    else:
        return None
    sb = _log_price(first, legs, a, b)
    sc = _log_price(second, legs, b, c)
    if sb is None or sc is None:
        return None
    return Triangle(target=target, leg_b=first, leg_c=second, sign_b=sb, sign_c=sc,
                    currencies=(a, b, c))


def closed_triangles(registry: dict[str, Any]) -> list[Triangle]:
    """Every triangle the broker actually quotes all three sides of, once each.

    ONCE EACH, and that is a charge decision rather than tidiness: a triangle can be written
    three ways (trade the AC leg, the AB leg or the BC leg) and the three are ONE hypothesis
    about one residual. Enumerating all three would triple the trial count for no new claim, so
    the target is fixed as the pair between the two currencies that sort first.
    """
    legs = fx_pairs(registry)
    by_ccy: dict[frozenset[str], str] = {}
    for sym, (b, q) in legs.items():
        by_ccy.setdefault(frozenset((b, q)), sym)
    out: list[Triangle] = []
    for a, b, c in combinations(sorted({x for p in legs.values() for x in p}), 3):
        ab = by_ccy.get(frozenset((a, b)))
        bc = by_ccy.get(frozenset((b, c)))
        ac = by_ccy.get(frozenset((a, c)))
        if not (ab and bc and ac):
            continue
        tri = orient(ac, ab, bc, legs)
        if tri is not None:
            out.append(tri)
    return sorted(out, key=lambda t: t.cell)


def load_registry(path: Path | None = None) -> dict[str, Any]:
    """The symbol registry, or {} when it cannot be read. Never raises: an unreadable registry
    is zero triangles and a reason, not a crashed miner."""
    p = path or UNIVERSE
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def census(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the grid costs, in the terms `NOT_SOURCED_HERE` cares about.

    `naive_triples` is what a sweep over every ordered pair-of-pairs would have enumerated. It is
    reported beside the real figure so the charge this miner AVOIDS is on the record rather than
    asserted in a comment.
    """
    reg = registry if registry is not None else load_registry()
    legs = fx_pairs(reg)
    tri = closed_triangles(reg)
    n = len(legs)
    return {"fx_pairs": n,
            "currencies": len({x for p in legs.values() for x in p}),
            "closed_triangles": len(tri),
            "naive_triples": n ** 3,
            "reduction": (n ** 3 / len(tri)) if tri else None,
            "cells": [t.cell for t in tri]}
