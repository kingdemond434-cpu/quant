"""SOURCE PROMOTION -- a verified alternative REPLACES the incumbent, and keeps replacing it.

WHAT WAS MISSING, and it is the whole point of hunting. The desk had two halves of a loop and not
the third. `source_alternatives` holds candidate replacements per information class; `paywall`
records every paid dataset walked into and demands a hunt. Neither could ever SWAP anything. So a
genuinely better free route could be found, verified, written into a registry row -- and the desk
would keep calling the old one forever, because nothing turned a finding into a change. Hunting
without replacing is cataloguing.

THIS IS NOT ONLY ABOUT PAYWALLS. The same machinery answers the general case: if a better route to
the SAME information class turns up at any point -- cheaper, cleaner licence, wider coverage,
fewer blockers, or simply alive when the incumbent has died -- it replaces the incumbent. A route
is never permanent because it was first.

WHAT "GENUINE" MEANS, because a loose bar here silently degrades every downstream number. A
candidate is promoted only when ALL of these hold:

    USABLE          it returned real rows, not HTTP 200 with an anti-bot page or an empty list
    LICENSED        its terms permit desk use. The desk has already excluded Coin Metrics on
                    licence (CC BY-NC + a ToU clause banning AI use) despite the data being
                    perfect, so this is a real gate and not a formality
    SAME CLASS      it answers the same information class -- a substitute that changes the
                    question is not a replacement, it is a different dataset
    STRICTLY BETTER on at least one axis, and WORSE ON NONE of the hard ones

The hard axes never trade off: licence and look-ahead safety. A cheaper route that cannot stamp
`known_from` is not cheaper, it is broken -- a point-in-time series without a knowability stamp
silently reintroduces look-ahead, which no downstream statistic would reveal.

INSUFFICIENT IS THE DEFAULT AND IT IS NOT A FAILURE. A candidate nobody probed does not get
promoted on optimism. The verdict is INSUFFICIENT-EVIDENCE with the specific missing field named,
so the next hunt knows exactly what to go and measure.

EVERY SWAP IS LEDGERED AND REVERSIBLE. `data/route_swaps.jsonl` records what replaced what, on
what evidence, and when -- so a promotion that turns out badly can be traced to the measurement
that justified it rather than argued about, and the incumbent it displaced is still named.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "ACTIVE_ROUTES",
    "SWAP_LEDGER",
    "RouteEvidence",
    "active_route",
    "evaluate",
    "promote",
]

_ROOT = Path(__file__).resolve().parents[2]

#: The live answer to "who does the desk actually call for this information class?"
ACTIVE_ROUTES = "data/active_routes.json"
#: Append-only history of every replacement, with the evidence that justified it.
SWAP_LEDGER = "data/route_swaps.jsonl"

PROMOTE = "PROMOTE"
KEEP = "KEEP"
INSUFFICIENT = "INSUFFICIENT-EVIDENCE"
REFUSED = "REFUSED"

#: Licence verdicts that permit desk use. Anything else -- including UNKNOWN -- blocks promotion.
#: UNKNOWN blocks deliberately: adopting a source whose terms nobody read is how a desk acquires an
#: obligation it cannot see, and the Coin Metrics exclusion (CC BY-NC plus a ToU clause banning AI
#: use) is the standing proof that reading them changes the answer.
LICENCE_OK: frozenset[str] = frozenset({"PERMISSIVE", "PUBLIC-DOMAIN", "MIT", "APACHE-2.0",
                                        "CC0", "CC-BY", "PRIMARY-SOURCE", "OWN-RECORDING"})


@dataclass
class RouteEvidence:
    """What is actually KNOWN about one route. Every field defaults to the unknown state."""

    name: str
    information_class: str
    usable_rows: int | None = None          # None = never probed, 0 = probed and empty
    licence: str = "UNKNOWN"
    is_paid: bool | None = None
    stamps_known_from: bool | None = None   # can it carry a point-in-time knowability stamp?
    coverage_note: str = ""
    probed_utc: str = ""
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "information_class": self.information_class,
                "usable_rows": self.usable_rows, "licence": self.licence,
                "is_paid": self.is_paid, "stamps_known_from": self.stamps_known_from,
                "coverage_note": self.coverage_note, "probed_utc": self.probed_utc,
                "detail": self.detail}


@dataclass
class Verdict:
    verdict: str
    why: str
    better_on: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "why": self.why,
                "better_on": self.better_on, "missing": self.missing}


def evaluate(candidate: RouteEvidence, incumbent: RouteEvidence | None) -> Verdict:
    """Should `candidate` replace `incumbent`? Pure -- all evidence is passed in.

    Ordered so the CHEAP disqualifications run first and the reason returned is the most
    fundamental one. A caller told "not licensed" learns more than one told "no better on any
    axis", even when both are true.
    """
    missing: list[str] = []
    if candidate.usable_rows is None:
        missing.append("usable_rows (never probed -- optimism is not evidence)")
    if candidate.stamps_known_from is None:
        missing.append("stamps_known_from (unknown whether it can carry a point-in-time stamp)")
    if candidate.licence == "UNKNOWN":
        missing.append("licence (terms nobody has read)")
    if missing:
        return Verdict(INSUFFICIENT, "candidate has not been measured on: " + "; ".join(missing),
                       missing=missing)

    if not candidate.usable_rows:
        return Verdict(REFUSED, "candidate was probed and returned NO usable rows -- a 200 with an "
                                "empty list or an anti-bot page is not a working source")
    if candidate.licence not in LICENCE_OK:
        return Verdict(REFUSED, f"licence {candidate.licence!r} does not permit desk use. This is "
                                "a real gate: Coin Metrics was excluded on exactly this ground "
                                "(CC BY-NC + a ToU clause banning AI use) with perfect data")
    if candidate.stamps_known_from is False:
        return Verdict(REFUSED, "candidate cannot stamp `known_from`. A point-in-time series with "
                                "no knowability stamp silently reintroduces look-ahead, which no "
                                "downstream statistic would reveal -- so this is never a trade-off "
                                "against price or coverage")
    if incumbent is None:
        return Verdict(PROMOTE, "no incumbent route for this information class -- the desk was "
                                "calling nothing, so a verified candidate is strictly better",
                       better_on=["exists"])
    if candidate.information_class != incumbent.information_class:
        return Verdict(REFUSED, f"candidate answers {candidate.information_class!r}, incumbent "
                                f"answers {incumbent.information_class!r}. A substitute that "
                                "changes the question is a different dataset, not a replacement")

    better: list[str] = []
    if incumbent.is_paid and candidate.is_paid is False:
        better.append("free vs paid")
    if (incumbent.usable_rows or 0) and candidate.usable_rows > (incumbent.usable_rows or 0):
        better.append(f"more rows ({candidate.usable_rows} vs {incumbent.usable_rows})")
    if not incumbent.usable_rows:
        better.append("incumbent returns nothing -- it has died")
    if incumbent.licence not in LICENCE_OK and candidate.licence in LICENCE_OK:
        better.append(f"licence {candidate.licence} vs {incumbent.licence}")

    # WORSE ON A HARD AXIS BLOCKS, whatever it wins on. Paying for more rows is a decision, not an
    # automatic upgrade, and it is the principal's decision rather than this function's.
    if candidate.is_paid and not incumbent.is_paid:
        return Verdict(REFUSED, "candidate is PAID and the incumbent is free. Buying is the "
                                "principal's decision, never a promotion rule -- recorded as a "
                                "paid target instead")
    if not better:
        return Verdict(KEEP, "candidate is verified and usable but beats the incumbent on no "
                             "axis. A working alternative is worth keeping as a standby, not "
                             "worth a swap -- churn costs the desk its comparability")
    return Verdict(PROMOTE, "verified, licensed, same class, and better on: " + ", ".join(better),
                   better_on=better)


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def active_route(information_class: str, root: Path | None = None) -> RouteEvidence | None:
    """The route the desk currently calls for this class, or None if it calls nothing."""
    doc = _read((root or _ROOT) / ACTIVE_ROUTES)
    row = doc.get(information_class)
    if not isinstance(row, dict):
        return None
    return RouteEvidence(
        name=str(row.get("name", "")), information_class=information_class,
        usable_rows=row.get("usable_rows"), licence=str(row.get("licence", "UNKNOWN")),
        is_paid=row.get("is_paid"), stamps_known_from=row.get("stamps_known_from"),
        coverage_note=str(row.get("coverage_note", "")), probed_utc=str(row.get("probed_utc", "")),
        detail=str(row.get("detail", "")))


def promote(candidate: RouteEvidence, *, root: Path | None = None,
            force: bool = False) -> dict[str, Any]:
    """Evaluate and, if it wins, MAKE IT THE LIVE ROUTE. Returns the decision either way.

    The swap is two writes: the active-route registry (what the desk calls now) and an append-only
    ledger row naming what was displaced and on what evidence. The second is what makes a bad
    promotion traceable to the measurement that justified it instead of arguable after the fact,
    and it keeps the displaced route named so a rollback knows where to go back to.
    """
    base = root or _ROOT
    incumbent = active_route(candidate.information_class, base)
    verdict = evaluate(candidate, incumbent)
    decision = {
        "decided_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "information_class": candidate.information_class,
        "candidate": candidate.as_dict(),
        "incumbent": incumbent.as_dict() if incumbent else None,
        **verdict.as_dict(),
    }
    if verdict.verdict != PROMOTE and not force:
        return decision
    if force and verdict.verdict != PROMOTE:
        decision["forced"] = ("promoted against the verdict by an explicit caller decision -- "
                              "recorded so the override is visible rather than indistinguishable "
                              "from a clean promotion")

    doc = _read(base / ACTIVE_ROUTES)
    doc[candidate.information_class] = {**candidate.as_dict(),
                                        "promoted_utc": decision["decided_utc"],
                                        "replaced": incumbent.name if incumbent else None,
                                        "why": verdict.why}
    try:
        (base / ACTIVE_ROUTES).parent.mkdir(parents=True, exist_ok=True)
        (base / ACTIVE_ROUTES).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", "utf-8")
        with (base / SWAP_LEDGER).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(decision, ensure_ascii=False) + "\n")
    except OSError as exc:
        decision["write_error"] = f"{type(exc).__name__}: {exc}"
    decision["swapped"] = True
    return decision
