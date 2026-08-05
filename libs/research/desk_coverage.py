"""WHOLE-DESK GRADE -- 100% coverage PROVEN, scored harshly, every aspect pushed at once.

THE DEFECT THIS CLOSES. `capability_ratchet.ASPECTS` is a hardcoded tuple of 26. It is a good list
and it is ASSERTED COMPLETE, never proven -- so an aspect of this desk that nobody wrote into that
tuple is invisible, scores nothing, and drags no number down. That is the same fail-open shape the
desk keeps finding in itself: an unmeasured thing reading as a healthy one. A weekly grade claiming
to cover the desk has to DERIVE its surface and prove every part of it is claimed, or "100%
coverage" is a sentence rather than a measurement.

WHAT "THE DESK" IS, enumerated rather than declared. Four surfaces, each read from the repo:

    SCHEDULED ORGANS   every cron line in ops/crontab.manifest -- what the desk actually DOES
    SUBSYSTEMS         every package under libs/ -- what the desk is BUILT from
    DECISION ARTIFACTS every data/*.json|jsonl a rated aspect could rest on -- what it KNOWS
    LAWS               every L1.x in docs/CONSTITUTION.md -- what it has PROMISED

Anything in those four that no aspect claims is an UNRATED SURFACE: a real part of the desk with
no grade, no owner and no way to fall. Coverage is then a measured fraction, and it is scored on
the same 0-10 scale as everything else so it cannot be quietly excluded from the headline.

THE AGGREGATE IS HARSH ON PURPOSE, AND THE ARITHMETIC MEAN IS THE REASON. Measured 2026-08-05 the
desk's 26 aspects averaged 5.82 while `alerting_pager` sat at 0.0 -- a desk whose pager has never
delivered a page. An average lets two 10s pay for a zero, which is precisely backwards: capability
is a CHAIN, and a chain with a broken link does not score 5.8. The headline grade is therefore the
HARMONIC mean, which is dominated by the weakest members and collapses toward zero when any aspect
is near zero. The arithmetic mean is still reported, because hiding it would be its own dishonesty
-- but it is not the number.

PUSH EVERY ASPECT AT ONCE, NOT JUST THE MINIMUM. The daily ratchet names ONE binding constraint,
which is correct for a daily cadence: fix the worst thing. A weekly grade has a different job --
emit the FULL worklist, every aspect below 10 with its own next action and the distance to 10, so
a week's work is chosen against the whole surface rather than against one number. Ranked by
distance-to-ceiling times how cheap the next rung is, so the week's plan is not simply "the worst
one" repeated seven times.

Pure logic. Reading is passed in; the organ is scripts/run_weekly_desk_grade.py.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "CEILING",
    "SurfaceItem",
    "desk_grade",
    "enumerate_surface",
    "harmonic",
    "unclaimed",
    "worklist",
]

CEILING = 10.0

#: Added to every score before the harmonic mean so a single 0.0 yields a very low grade rather
#: than an undefined one. Small enough that a zero still dominates: with one aspect at 0.0 and 25
#: at 10.0 the grade is ~1.3, which is the intended verdict on a desk whose pager is dead.
_EPS = 0.05

#: Surfaces a grade must cover. Each is (label, how it is enumerated) -- the enumeration is code
#: below, and this table exists so a reader can see at a glance what "the whole desk" was taken to
#: mean and argue with it.
SURFACES: tuple[tuple[str, str], ...] = (
    ("organ", "every cron line in ops/crontab.manifest -- what the desk DOES"),
    ("subsystem", "every package under libs/ -- what the desk is BUILT from"),
    ("artifact", "every data/ decision artifact -- what the desk KNOWS"),
    ("law", "every L1.x in docs/CONSTITUTION.md -- what the desk has PROMISED"),
)

#: Surfaces that legitimately need no aspect of their own. Each needs a REASON, and the list is
#: deliberately tiny: an exemption is how a coverage number gets to 100% without covering anything.
EXEMPT: dict[str, str] = {
    "libs/__init__": "namespace package, no behaviour to grade",
    "libs/py.typed": "typing marker, not a subsystem",
}


@dataclass
class SurfaceItem:
    """One part of the desk, and the aspect that claims it (or none)."""

    kind: str
    name: str
    claimed_by: str = ""
    why_unclaimed: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "claimed_by": self.claimed_by,
                "why_unclaimed": self.why_unclaimed}


def _cron_organs(manifest: str) -> set[str]:
    """Script names on real cron lines. Comments are excluded -- a documented organ is not a
    scheduled one, and counting prose as coverage is how a manifest starts lying."""
    out: set[str] = set()
    for line in manifest.splitlines():
        if line.lstrip().startswith("#") or not line.strip():
            continue
        if not re.match(r"^[\d*/,\- ]+ [\d*/,\- ]+ ", line):
            continue
        for hit in re.findall(r"scripts/([a-z0-9_]+)\.py", line):
            out.add(hit)
    return out


def enumerate_surface(root: Path, *, constitution: str = "",
                      manifest: str = "") -> list[SurfaceItem]:
    """Every part of the desk a weekly grade must account for. DERIVED, never listed."""
    items: list[SurfaceItem] = []

    man = manifest or _safe_read(root / "ops/crontab.manifest")
    for organ in sorted(_cron_organs(man)):
        items.append(SurfaceItem("organ", organ))

    libs = root / "libs"
    if libs.is_dir():
        for pkg in sorted(p.name for p in libs.iterdir() if p.is_dir() and p.name != "__pycache__"):
            items.append(SurfaceItem("subsystem", f"libs/{pkg}"))

    data = root / "data"
    if data.is_dir():
        for p in sorted(data.iterdir()):
            if p.is_dir() or p.suffix not in (".json", ".jsonl"):
                continue
            items.append(SurfaceItem("artifact", f"data/{p.name}"))

    con = constitution or _safe_read(root / "docs/CONSTITUTION.md")
    for law in sorted(set(re.findall(r"^##\s+(L1\.\d+[a-z]?)\b", con, flags=re.M))):
        items.append(SurfaceItem("law", law))

    return [i for i in items if i.name not in EXEMPT]


def _safe_read(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", str(text).lower()) if t not in
            {"data", "json", "jsonl", "libs", "run", "check", "the", "and", "for", "scripts"}}


def unclaimed(surface: list[SurfaceItem], aspects: list[dict[str, Any]]) -> list[SurfaceItem]:
    """Attach each surface item to a rated aspect, or mark it UNRATED.

    A claim is made by the aspect's OWN declared artifacts first -- that is an explicit statement
    by whoever wrote the aspect, and it is worth more than any inference. Token overlap with the
    aspect key and description is the fallback, deliberately requiring a real word in common
    rather than a substring, because `data/alpha.json` and `alpha_output` sharing "alpha" is a
    claim while `run.py` and `research_discipline` sharing "r" is not.

    UNCLAIMED IS THE DEFAULT. Anything the loop cannot attach stays unrated and drags the coverage
    score down, which is the whole point -- an aspect list that quietly stopped covering a third of
    the desk would otherwise keep reporting the same 26 numbers.
    """
    claims: list[tuple[str, set[str], set[str]]] = []
    for a in aspects:
        key = str(a.get("key", ""))
        arts = {str(x) for x in (a.get("artifacts") or []) if x}
        toks = _tokens(key) | _tokens(a.get("ceiling", "")) | _tokens(a.get("cause", ""))
        for comp in a.get("components") or []:
            if isinstance(comp, dict):
                arts |= {str(comp.get("artifact") or "")} - {""}
                toks |= _tokens(comp.get("name", ""))
        claims.append((key, arts, toks))

    for item in surface:
        name = item.name
        base = name.split("/")[-1].rsplit(".", 1)[0]
        hit = ""
        for key, arts, _toks in claims:                     # explicit artifact claim wins
            if name in arts or any(name in str(a) or str(a).endswith(name) for a in arts):
                hit = key
                break
        if not hit:
            item_toks = _tokens(base)
            best, best_n = "", 0
            for key, _arts, toks in claims:
                n = len(item_toks & toks)
                if n > best_n:
                    best, best_n = key, n
            if best_n >= 2:                                 # two real words in common, not one
                hit = best
        if hit:
            item.claimed_by = hit
        else:
            item.why_unclaimed = (
                f"UNRATED SURFACE: no aspect declares {name} and no aspect shares two words with "
                "it. It is a real part of this desk with no grade, no owner and no way to fall.")
    return [i for i in surface if not i.claimed_by]


def harmonic(scores: list[float]) -> float:
    """The harshest defensible aggregate: dominated by the weakest member.

    An ARITHMETIC mean lets two 10s pay for a 0, which is backwards -- capability is a chain, and a
    chain with a broken link is not 5.8/10. Measured on the desk's own 2026-08-05 scores the
    arithmetic mean is 5.82 with `alerting_pager` at 0.0; the harmonic mean is ~1.0. The second
    number is the true verdict on a desk whose pager has never delivered a page.
    """
    vals = [max(0.0, float(s)) + _EPS for s in scores if isinstance(s, (int, float))]
    if not vals:
        return 0.0
    return round(len(vals) / sum(1.0 / v for v in vals) - _EPS, 2)


@dataclass
class Grade:
    grade: float = 0.0
    arithmetic: float = 0.0
    coverage_score: float = 0.0
    n_surface: int = 0
    n_unrated: int = 0
    weakest: list[dict[str, Any]] = field(default_factory=list)
    at_ceiling: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"grade_harmonic": self.grade, "grade_arithmetic": self.arithmetic,
                "coverage_score": self.coverage_score, "n_surface": self.n_surface,
                "n_unrated": self.n_unrated, "weakest": self.weakest,
                "at_ceiling": self.at_ceiling}


def desk_grade(aspects: list[dict[str, Any]], surface: list[SurfaceItem],
               unrated: list[SurfaceItem]) -> Grade:
    """The whole-desk grade: harmonic(aspects) SCALED BY the fraction of the desk actually rated.

    COVERAGE IS A MULTIPLIER, NOT A TERM, and the first version got this wrong. Adding coverage as
    one more member of the harmonic mean diluted it: five aspects at 10.0 with NINE OF TEN surfaces
    unrated still graded 4.09, which says a desk measured on a tenth of itself is a middling desk.
    It is not -- it is a desk nobody has measured. A score computed over 18% of the surface
    describes 18% of the desk, so it is worth 18% of its face value, and multiplying says exactly
    that. Full coverage leaves the aspect grade untouched; no coverage sends it to zero.

    The harmonic mean handles the other half of the problem: capability is a CHAIN, so two 10s must
    not pay for a 0. Measured on the desk's own 2026-08-05 numbers the arithmetic mean is 5.82 and
    the harmonic mean is 0.98, with `alerting_pager` at 0.0 -- a desk whose pager has never
    delivered a page. The second number is the true one.
    """
    scores = [float(a["score"]) for a in aspects if isinstance(a.get("score"), (int, float))]
    n_sur = len(surface)
    cov = CEILING * (1.0 - (len(unrated) / n_sur)) if n_sur else 0.0
    ranked = sorted(
        (a for a in aspects if isinstance(a.get("score"), (int, float))),
        key=lambda a: float(a["score"]))
    covered = (1.0 - (len(unrated) / n_sur)) if n_sur else 0.0
    return Grade(
        grade=round(harmonic(scores) * covered, 2),
        arithmetic=round(sum(scores) / len(scores), 2) if scores else 0.0,
        coverage_score=round(cov, 2),
        n_surface=n_sur, n_unrated=len(unrated),
        weakest=[{"aspect": a["key"], "score": round(float(a["score"]), 1),
                  "binding_constraint":
                      str(a.get("binding_constraint") or a.get("cause") or "")[:200]}
                 for a in ranked[:8]],
        at_ceiling=[a["key"] for a in aspects
                    if isinstance(a.get("score"), (int, float)) and float(a["score"]) >= CEILING])


def worklist(aspects: list[dict[str, Any]], unrated: list[SurfaceItem]) -> list[dict[str, Any]]:
    """EVERY aspect below 10 with its next action -- not just the binding constraint.

    The daily ratchet names one thing to fix, which is right for a daily cadence. A weekly grade
    has a different job: put the WHOLE surface in front of the desk so a week is planned against
    all of it. Ranked by distance-to-ceiling, because a 0.8 aspect has nine points of headroom and
    a 9.7 aspect has three tenths -- and an unrated surface outranks both, since an aspect nobody
    grades cannot even be known to be broken.
    """
    rows: list[dict[str, Any]] = []
    for item in unrated:
        rows.append({"rank_key": CEILING + 1.0, "kind": item.kind, "target": item.name,
                     "score": None, "distance": CEILING,
                     "action": ("RATE IT -- add an aspect (or a component of one) that grades "
                                f"{item.name}, or record why it needs none. An ungraded surface "
                                "cannot fall, so it never appears in any weekly plan."),
                     "why": item.why_unclaimed})
    for a in aspects:
        s = a.get("score")
        if not isinstance(s, (int, float)) or float(s) >= CEILING:
            continue
        rows.append({"rank_key": CEILING - float(s), "kind": "aspect", "target": a["key"],
                     "score": round(float(s), 1), "distance": round(CEILING - float(s), 1),
                     "action": str(a.get("binding_constraint") or a.get("cause") or
                                   "no binding constraint recorded -- the aspect scores below "
                                   "ceiling and nothing says why, which is its own defect")[:300],
                     "why": str(a.get("ceiling") or "")[:200]})
    return sorted(rows, key=lambda r: (-float(r["rank_key"]), str(r["target"])))


def json_default(obj: Any) -> Any:                          # pragma: no cover - serialiser shim
    if isinstance(obj, SurfaceItem):
        return obj.as_dict()
    return json.JSONEncoder().default(obj)


def n_effective_aspects(aspects: list[dict[str, Any]]) -> float:
    """How many INDEPENDENT aspects the grade really rests on.

    Twenty-six aspects that all read the same three artifacts is not twenty-six measurements. This
    is the participation ratio over how many distinct artifacts each aspect touches -- a blunt
    proxy, reported so a reader can see whether breadth is real or nominal, and never used to
    adjust a score.
    """
    counts = [len({str(c.get("artifact") or "") for c in (a.get("components") or [])
                   if isinstance(c, dict)} - {""}) for a in aspects]
    sizes = [float(c) for c in counts if c]
    if not sizes:
        return 0.0
    total = sum(sizes)
    return round((total * total) / sum(s * s for s in sizes) if total else 0.0, 1) \
        if not math.isclose(total, 0.0) else 0.0
