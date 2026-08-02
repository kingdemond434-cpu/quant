"""REASONING EFFORT AS DATA, NOT AS SIX HARDCODED LITERALS.

WHAT THIS REPLACES. Every reasoning organ on this desk sent `"reasoning": {"effort": "high"}` as a
literal -- six copies, none of them derived from what the seat in question can actually do. That is
the same defect shape as `seats.resolve(SEATS, n=len(SEATS))`, which this desk already found in six
organs: a constant quietly bounding something that was supposed to grow with the roster. When a
seat ships a deeper reasoning mode, six files have to be edited by someone who noticed, and nobody
notices, because "high" reads like a maximum.

IT IS NOT A MAXIMUM. It is the middle rung of a ladder whose top rung differs per model and per
month, and a middle rung applied to a flagship the desk is paying for is capability left unused --
which this constitution scores as a defect on the same footing as idle capital.

CAPABILITY IS MEASURED, NEVER GUESSED. `scripts/refresh_panel_roster.py` sees each model's declared
`supported_parameters` when it refreshes from the live catalog; this module reads what was RECORDED
there and asks for the deepest mode that seat actually advertises. Where nothing was recorded it
falls back to the previous literal and says so, because the alternative -- inventing a parameter
name and hoping -- produces a request the provider rejects, or worse, silently ignores while the
desk believes it bought deeper reasoning.

THE FALLBACK IS DELIBERATELY THE OLD BEHAVIOUR. An unknown seat must not become a broken seat. The
report distinguishes "asked for max because the seat advertises it" from "asked for high because
nothing is known", so the gap between them is visible and shrinks as the roster is refreshed rather
than sitting unmeasured forever.

Pure, dependency-free, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "DEFAULT_EFFORT",
    "EFFORT_LADDER",
    "ROSTER_CAPS",
    "coverage",
    "effort_for",
    "reasoning_payload",
]

#: Ordered weakest -> deepest. The desk always asks for the deepest rung a seat advertises: the
#: input context is the expensive half of the call and is already paid for, so a shallower rung
#: buys a cheaper answer to a question the desk has already funded.
EFFORT_LADDER: tuple[str, ...] = ("low", "medium", "high", "max")

#: Used when a seat's capabilities have never been recorded. The PREVIOUS hardcoded literal,
#: chosen so an unknown seat degrades to exactly what it did before rather than to a request the
#: provider may reject.
DEFAULT_EFFORT = "high"

#: Written by refresh_panel_roster when it can reach the catalog. model id -> declared parameters.
ROSTER_CAPS = Path("data/roster_capabilities.json")


def _recorded(path: Path | str = ROSTER_CAPS) -> dict[str, list[str]]:
    try:
        d = json.loads(Path(path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    caps = d.get("models", d)
    return {str(k): [str(x) for x in (v or [])] for k, v in caps.items()
            if isinstance(v, list | tuple)}


def effort_for(model: str, *, path: Path | str = ROSTER_CAPS) -> tuple[str, str]:
    """(effort, why). The deepest rung this seat ADVERTISES, or the old default with the reason.

    Returns the reason alongside the value so a caller can log which of the two situations it is
    in. "We asked for max because this seat advertises it" and "we asked for high because nothing
    is known about this seat" are different facts, and collapsing them hides how much of the
    roster is still running on a guess.
    """
    caps = _recorded(path).get(model)
    if not caps:
        return DEFAULT_EFFORT, (
            f"no recorded capabilities for {model} -- falling back to the previous literal "
            f"'{DEFAULT_EFFORT}'. Run refresh_panel_roster to record what this seat can do; "
            "until then the desk may be buying a shallower answer than it is paying for.")
    advertised = [rung for rung in EFFORT_LADDER if rung in caps]
    if not advertised:
        return DEFAULT_EFFORT, (
            f"{model} declares parameters but no reasoning rung among {EFFORT_LADDER} -- "
            f"'{DEFAULT_EFFORT}' retained rather than inventing one")
    best = advertised[-1]
    return best, (f"{model} advertises {advertised}; asking for the deepest rung '{best}'")


def reasoning_payload(model: str, *, path: Path | str = ROSTER_CAPS) -> dict:
    """The `reasoning` block to put in a chat/completions body.

    A dict rather than a bare string so a seat that advertises a different shape can be handled
    here, in one place, instead of in six call sites that will not all get edited.
    """
    effort, _ = effort_for(model, path=path)
    return {"effort": effort}


def coverage(models: list[str], *, path: Path | str = ROSTER_CAPS) -> dict:
    """How much of the roster is running on measured capability versus on the fallback.

    THE NUMBER THAT MATTERS is the fallback count, not the recorded one: every seat on the
    fallback is a flagship the desk is paying for and possibly under-driving, and that cost is
    invisible because the call succeeds either way.
    """
    caps = _recorded(path)
    known = [m for m in models if caps.get(m)]
    unknown = [m for m in models if not caps.get(m)]
    return {
        "models": len(models),
        "measured": len(known),
        "fallback": len(unknown),
        "fallback_seats": sorted(unknown),
        "note": ("every seat's reasoning depth is measured from the live catalog"
                 if not unknown else
                 f"{len(unknown)} of {len(models)} seats run on the '{DEFAULT_EFFORT}' fallback "
                 "-- each may be a flagship being under-driven, and the call succeeds either "
                 "way so the cost never surfaces on its own. Refresh the roster."),
    }
