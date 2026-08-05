"""THE CAPABILITY RATCHET (R0104) -- every aspect of the desk carries a score, and it only rises.

THE STANDING ORDER, AND WHY IT HAD NO INSTRUMENT. The principal's order is that every aspect of
this desk is pushed toward 10/10 every day, non-exhaustively. Until now that rating existed only
in conversation: somebody said "risk rails are maybe a 7" and nothing wrote it down. A rating
nobody records cannot ratchet, cannot be diffed, and cannot fail -- so the order was enforced by
remembering to care, which is the thing this desk builds machinery to stop relying on. A score
that can silently fall is not a standard; it is a mood.

WHAT THIS IS, AND WHAT IT IS NOT. It is the aggression ratchet's idiom (libs/doctrine/ratchet.py)
pointed at CAPABILITY instead of constitutional aggression: a high-water mark per named aspect,
raised automatically and never lowered by code. It is NOT a second copy of check_ratchets.py --
that fence holds individual scalar METRICS above their own floors and deliberately refuses to say
what is "good". This one answers the different question the standing order actually asks: on the
desk's own 0-10 scale, where does each aspect stand, and WHAT IS STOPPING IT FROM BEING ONE POINT
HIGHER. The binding constraint is the whole product; the number is how the constraint gets found.

THE HONESTY RULE, which outranks every other property here. A component with no measurement
scores UNMEASURED. It is NEVER silently treated as 0 and never as 10 -- 0 would manufacture a
defect out of ignorance and 10 would manufacture a capability out of it, and the second failure is
how an all-green board hides an empty one (scripts/check_clock_provenance.py, L1.28a). UNMEASURED
is its own state, it is reported in its own list, and it is excluded from the aspect mean rather
than folded into it. A MEASURED zero is different and is allowed: the desk has promoted nothing to
a live rung, and 0.0 is the honest reading of that.

TRUNCATION IS NOT STRENGTH. data/mutation_score.json carries its own `budget_truncated` flag: a
run that stopped at a mutant budget sampled the easy end of the file and its kill rate is a
sampling artifact, not a strength measurement. Those targets are excluded from the score and
listed as UNMEASURED, because scoring them would let the desk buy points by running LESS.

DELETION IS WEAKENING, inherited unchanged from the constitution ratchet. A component that had a
high-water mark and no longer measures is not neutral -- the capability it evidenced is now
unevidenced, so the aspect is scored as having FALLEN with WENT-DARK named as the cause. Otherwise
deleting the measurement would be the trivial way around the entire mechanism.

THE TAXONOMY IS EXHAUSTIVE BY INTENT AND IT ONLY WIDENS. "Every aspect" is not the four anyone
would think to grade. It is also the pager between incidents, cost-model freshness, the tape's
clock provenance, seat credentials, dependency drift against the deployed pins, backup restore
drills, mutation BREADTH as a distinct question from kill rate, scheduler manifest drift, and
permission hygiene -- the minor surface, which is precisely where a desk rots, because nobody
grades it. Every one of them is read from an artifact another organ already writes: this module
measures NOTHING itself, since a scorer that measures is a scorer that can be gamed by rewriting
the scorer, and it re-derives no threshold another organ owns.

MEASURING MORE IS NOT REGRESSING, and getting this wrong would have destroyed the instrument.
Widening an aspect lowers its mean against a mark earned over fewer components, and reporting that
as a fall makes the gate permanently red -- the exact failure check_ratchets.py already fixed by
giving each mutation target its own floor ("a fence that fires when the desk measures MORE trains
everyone to ignore it"). So a fall whose mark the CURRENT component set could not have produced
even at every component's own best is WIDENED, not FELL: the mark is kept, the gap is printed, and
the instruction is to beat it over the wider set. It cannot launder a regression -- component marks
are per component, so anything that actually dropped names itself as a cause first.

WHAT IT CANNOT DO, stated plainly because a control that overstates itself is worse than none. The
map from artifact to 0-10 is a JUDGEMENT -- the ladders and fractions below are written down so
they can be argued with, but they are not discovered facts, and a component scoring 8 does not
mean the desk is 80% of the way to excellent at it. What the artifact does claim is narrower and
worth having: the score cannot fall without a named cause, the aspect list cannot quietly shrink,
an unmeasured aspect cannot read as a healthy one, every reading cites the artifact it came from,
and every reading carries the specific next thing that would raise it. One further limit is worth
naming: the desk-wide binding constraint ranks only MEASURED components, so a desk with large
unmeasured holes will keep pointing at a real but possibly not-worst defect. The unmeasured list
sits directly beside it for exactly that reason, and its instruction is always the same: measure
it, then the ranking means more.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "ARTIFACT_PATH",
    "ASPECT_KEYS",
    "AT_CEILING",
    "CANARY_MAX_AGE_H",
    "FELL",
    "FLATLINE",
    "MEASURED",
    "NEW",
    "RAISED",
    "SCALE_MAX",
    "STALL_DAYS",
    "UNMEASURED",
    "WENT_DARK",
    "WIDENED",
    "Aspect",
    "Component",
    "Marks",
    "Verdict",
    "age_hours",
    "attainable",
    "binary_component",
    "build_artifact",
    "desk_binding_constraint",
    "fraction_component",
    "inverse_ladder_component",
    "ladder_component",
    "liveness_component",
    "load_marks",
    "ratchet",
    "read_capability",
    "score_aspect",
    "stale_gate",
    "unmeasured_component",
]

#: Where the desk's capability record lives. data/, not docs/: it is rewritten daily by cron and a
#: daily-churning file in git is noise -- the ratchet's protection is that nothing in code lowers a
#: mark, not that a human reviews every reading.
ARTIFACT_PATH = Path("data/CAPABILITY_RATCHET.json")

#: The scale the principal's order is stated on. 10/10 is the target for every aspect, every day.
SCALE_MAX = 10.0

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: Movements. Each is a distinct fact and none may be folded into another: FLATLINE is not a
#: failure, FELL is, and WENT-DARK is a fall whose cause is the measurement disappearing.
RAISED = "RAISED"
FLATLINE = "FLATLINE"
AT_CEILING = "AT-CEILING"
FELL = "FELL"
WENT_DARK = "WENT-DARK"
NEW = "NEW"

#: WIDENED -- the aspect mean fell because the desk started grading itself on MORE, while every
#: component that already had a mark still holds it. This is not a defect and must not be reported
#: as one, for the reason check_ratchets.py:60-64 already learned the hard way: a single aggregate
#: across targets meant MEASURING A NEW FILE looked like a regression, and "a fence that fires when
#: the desk measures MORE trains everyone to ignore it -- the opposite of L1.0".
#:
#: IT CANNOT HIDE A REGRESSION, and that is why it is safe to distinguish. Component high-water
#: marks are held per component, so any pre-existing component that dropped, or went dark, or
#: stopped measuring, produces a NAMED CAUSE and the aspect is FELL regardless of what was added
#: beside it. WIDENED is reachable only when NOTHING that was already measured got worse. The
#: aspect's own high-water mark is still not lowered -- the record keeps saying 9.0 while today
#: says 4.5, and the gap is the honest statement that the old 9.0 was measured over less.
WIDENED = "WIDENED"

#: Float comparison slack. Scores are rounded to 0.1 so that FLATLINE means something -- with raw
#: floats every reading differs in the twelfth decimal and "no movement" could never be reported.
EPS = 1e-9

#: Days with no aspect setting a new best before the ratchet itself reports a defect. The order is
#: DAILY, so a week of nothing is the order not being followed, not a quiet patch. Deliberately not
#: 1 day: the aspect list cannot each move every day, and a gate that fires every morning gets
#: acknowledged into silence, which is worse than no gate.
STALL_DAYS = 7.0


@dataclass(frozen=True)
class Component:
    """One measured (or explicitly unmeasured) input to an aspect, with the artifact that fed it.

    `constraint` is the point of the whole record: the specific, quantified next thing that buys
    one more point on this component.
    """

    key: str
    state: str
    score: float | None
    artifact: str
    detail: str
    constraint: str


@dataclass(frozen=True)
class Aspect:
    """A named aspect of the desk, scored 0-10 from its components -- or UNMEASURED."""

    key: str
    ceiling: str
    state: str
    score: float | None
    components: tuple[Component, ...]
    binding_constraint: str

    @property
    def artifacts(self) -> tuple[str, ...]:
        seen: list[str] = []
        for c in self.components:
            if c.artifact not in seen:
                seen.append(c.artifact)
        return tuple(seen)

    @property
    def unmeasured(self) -> tuple[Component, ...]:
        return tuple(c for c in self.components if c.state == UNMEASURED)


@dataclass(frozen=True)
class Marks:
    """The high-water record. Aspect marks AND component marks, because a fall must be localised.

    Component marks are what make a cause NAMEABLE. With aspect marks alone the artifact could
    only say "governance fell to 6.4", which is a fact nobody can act on; with component marks it
    says which measurement regressed, by how much, and out of which file.

    They are also what keeps an aspect mark MEANINGFUL as the taxonomy grows. A mark higher than
    the mean of the current components' own bests cannot have been earned over the current set
    (see `attainable`), so the marks carry their own evidence about whether a comparison is even
    valid -- no remembered component list, and no migration for records written before the rule
    existed.
    """

    aspect_high_water: dict[str, float]
    component_high_water: dict[str, float]
    last_raise_at: str
    first_recorded: str
    n_raises: int


@dataclass(frozen=True)
class Verdict:
    """What one aspect did against its own record this run."""

    aspect: str
    movement: str
    score: float | None
    high_water: float | None
    cause: str


# --------------------------------------------------------------------------------------------
# SCORING PRIMITIVES. Every count-to-score map is written down here rather than inlined, because a
# rubric that lives inside one call site is a rubric nobody can argue with.
# --------------------------------------------------------------------------------------------

#: Ladder for "how many of these has the desk actually produced" counts. Ten rungs, each roughly
#: 1.4x the last, so points get harder to buy as the count grows -- a linear map would let a desk
#: reach 10/10 by grinding the cheap end of any counter it happens to control.
COUNT_LADDER: tuple[int, ...] = (1, 2, 3, 5, 8, 12, 18, 25, 35, 50)

#: Ladder for the test suite. Linear because suite size genuinely is linear work per module, and
#: the top rung (500 collectable modules) is a stated ambition rather than a discovered ceiling.
SUITE_LADDER: tuple[int, ...] = (50, 100, 150, 200, 250, 300, 350, 400, 450, 500)

#: INVERSE ladder for defect counts -- doubling. Cutting 46 live defects to 31 is one point; the
#: last point costs going from 1 to 0, which is correct: the final defect is the expensive one.
DEFECT_LADDER: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)


def _round(score: float) -> float:
    """Clamp into the scale and round to 0.1. Rounding is load-bearing -- see EPS."""
    return round(min(max(score, 0.0), SCALE_MAX), 1)


def _read_json(path: Path) -> dict[str, Any] | None:
    """Missing, unreadable and not-an-object all mean the same thing here: NO MEASUREMENT.

    They are not swallowed -- every caller turns this None into an UNMEASURED component that names
    the artifact it wanted, so an absent file is louder in the output than a bad number would be.
    """
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]] | None:
    """Append-only ledgers, as a list of objects. None means NO LEDGER -- same contract as
    _read_json. An unparseable LINE is skipped (a half-written tail row is normal in a file being
    appended to); an unreadable FILE is the absent case and becomes UNMEASURED at the call site."""
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _rows(doc: dict[str, Any] | None, key: str) -> list[dict[str, Any]] | None:
    """A list-of-objects field, or None for "the artifact did not carry one"."""
    raw = doc.get(key) if doc is not None else None
    if not isinstance(raw, list):
        return None
    return [r for r in raw if isinstance(r, dict)]


def _mapping(doc: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """An object-valued field, or None for "the artifact did not carry one"."""
    raw = doc.get(key) if doc is not None else None
    return raw if isinstance(raw, dict) else None


def _len_or_none(value: object) -> float | None:
    """len() of a list/dict field, or None when the field is absent or the wrong shape.

    Used wherever a defect COUNT is published as the defect LIST. An absent list must not read as
    zero defects -- that is the shape in which "nobody checked" impersonates "nothing wrong".
    """
    return float(len(value)) if isinstance(value, list | dict) else None


def _num(value: object) -> float | None:
    """A number, or None. `True` is not 1 here -- a bool arriving where a count belongs is a bug
    upstream, and silently scoring it would hide that."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _field(doc: dict[str, Any] | None, key: str) -> Any:
    """A field for the DETAIL string, or "?" -- an absent artifact must still print something that
    says so. Never used to produce a score; scores come from _num(), which returns None."""
    if doc is None:
        return "?"
    return doc.get(key, "?")


def unmeasured_component(key: str, artifact: str, why: str) -> Component:
    """The honesty rule in one constructor: no score, and the reason is carried, not dropped."""
    return Component(
        key=key, state=UNMEASURED, score=None, artifact=artifact, detail=why,
        constraint=f"MEASURE IT -- {why}. Unmeasured is neither a 0 nor a 10; it is the state "
                   "of not knowing, and it stays that until an artifact says otherwise.")


def fraction_component(key: str, artifact: str, num: float | None, den: float | None, *,
                       unit: str, detail: str) -> Component:
    """Score = 10 x (num/den). Used wherever the desk already counts a numerator and denominator.

    A ZERO DENOMINATOR IS UNMEASURED, never 10. "0 of 0 organs are stale" is not a healthy desk,
    it is an empty one, and this is the exact shape in which unmeasured most often tries to pass
    itself off as perfect.
    """
    if num is None or den is None:
        return unmeasured_component(key, artifact, f"{artifact} did not yield {unit}")
    if den <= 0:
        return unmeasured_component(
            key, artifact,
            f"{artifact} reports a zero denominator for {unit} -- a ratio over nothing is not a "
            "measurement and must never read as full marks")
    score = _round(SCALE_MAX * num / den)
    if score >= SCALE_MAX - EPS:
        constraint = f"AT CEILING ({num:g}/{den:g} {unit}) -- the work is now HOLDING it"
    else:
        # The next WHOLE point, in the numerator's own units. Whole counts are ceiled to whole
        # counts: "23.1 of 42 organs producing" is not an instruction anybody can follow.
        target = (score + 1.0) / SCALE_MAX * den
        need = (float(math.ceil(target)) if float(num).is_integer() and float(den).is_integer()
                else math.ceil(target * 1000) / 1000)
        if need > den:
            # The last fractional point costs less than a full point's worth of numerator, and
            # printing "103 of 100" would be an instruction that cannot be followed. The honest
            # constraint at this end of the scale is the whole remaining gap.
            constraint = (f"+{den - num:g} {unit} ({num:g} -> {den:g}, the whole remaining gap) "
                          f"is the last +{SCALE_MAX - score:.1f} to 10/10")
        else:
            constraint = (f"+{need - num:g} {unit} ({num:g} -> {need:g} of {den:g}) buys the next "
                          "point")
    return Component(key=key, state=MEASURED, score=score, artifact=artifact, detail=detail,
                     constraint=constraint)


def ladder_component(key: str, artifact: str, count: float | None, rungs: tuple[int, ...], *,
                     unit: str, detail: str) -> Component:
    """Score = the number of ladder rungs the count has cleared."""
    if count is None:
        return unmeasured_component(key, artifact, f"{artifact} did not yield a count of {unit}")
    cleared = sum(1 for r in rungs if count >= r)
    score = _round(float(cleared))
    nxt = next((r for r in rungs if count < r), None)
    if nxt is None:
        constraint = (f"AT CEILING ({count:g} {unit}, top rung {rungs[-1]}) -- the ladder is "
                      "exhausted and the next point needs a HARDER ladder, argued for in the diff")
    else:
        constraint = (f"+{nxt - count:g} {unit} ({count:g} -> {nxt}, the next rung) buys the "
                      "next point")
    return Component(key=key, state=MEASURED, score=score, artifact=artifact, detail=detail,
                     constraint=constraint)


def inverse_ladder_component(key: str, artifact: str, count: float | None,
                             rungs: tuple[int, ...], *, unit: str, detail: str) -> Component:
    """Score = 10 minus the rungs cleared -- for counts where LOWER is the capability."""
    if count is None:
        return unmeasured_component(key, artifact, f"{artifact} did not yield a count of {unit}")
    cleared = [r for r in rungs if count >= r]
    score = _round(SCALE_MAX - len(cleared))
    if not cleared:
        constraint = f"AT CEILING ({count:g} {unit}) -- the work is now HOLDING it"
    else:
        target = cleared[-1] - 1
        constraint = (f"-{count - target:g} {unit} ({count:g} -> {target}, back under the "
                      f"{cleared[-1]} rung) buys the next point")
    return Component(key=key, state=MEASURED, score=score, artifact=artifact, detail=detail,
                     constraint=constraint)


def binary_component(key: str, artifact: str, ok: bool | None, *, detail: str, fix: str,
                     held: str = "") -> Component:
    """A capability that is either EVIDENCED or not: 10 or a MEASURED 0, never a hedge.

    `ok is None` is the third state and it is the one that matters: it means the artifact never
    made the claim either way, so the component is UNMEASURED rather than being pushed to whichever
    end of the scale the caller finds convenient. Callers pass None deliberately -- a missing flag
    is not a False. Note the explicit `is None` / `is True` tests: a truthiness test would read an
    absent field and a False field as the same fact, which is the entire failure this guards.
    """
    if ok is None:
        return unmeasured_component(key, artifact, detail)
    return Component(
        key=key, state=MEASURED, score=SCALE_MAX if ok else 0.0, artifact=artifact, detail=detail,
        constraint=(held or "AT CEILING -- evidenced, and the work is now HOLDING it") if ok
        else fix)


def age_hours(doc: dict[str, Any] | None, field: str, now: datetime) -> float | None:
    """How old is this artifact's own stamp, in hours? None when it cannot be established.

    None covers three cases that must NOT be told apart by the caller, because they license the
    same conclusion and nothing weaker: no document, no stamp field, and a stamp that will not
    parse. The last one is the sharpest form of the fail-open this exists to close -- a timestamp
    that can never be shown to be OLD can never be shown to be old, so trusting the artifact
    beside it is trusting something that has no expiry at all.

    Negative ages (a stamp in the future, an NTP step) come back as written rather than clamped;
    callers compare against a positive bound, so a future stamp reads as fresh, which is the right
    failure direction for a clock that just moved.
    """
    stamped = _parse_ts(doc.get(field)) if doc is not None else None
    if stamped is None:
        return None
    return round((now - stamped).total_seconds() / 3600.0, 2)


def stale_gate(key: str, artifact: str, doc: dict[str, Any] | None, field: str, now: datetime, *,
               max_age_h: float, owner: str, what: str) -> Component | None:
    """THE AGE CHECK, as one call, so that skipping it is a visible omission rather than a habit.

    Returns an UNMEASURED component when the artifact is absent, unstamped, unparseable or OLDER
    than `max_age_h`; returns None when it is fresh enough to be read. A caller that wants to score
    a state artifact writes this line first, and the reviewer can see whether they did.

    WHY A GATE RATHER THAN A FRESHER `_read_json`. A silent "return None when stale" would collapse
    stale into absent, and those are different findings with different repairs: nothing was ever
    written versus something stopped writing. The gate keeps them distinguishable in the reason
    string while making the CHECK itself a single unmissable statement.

    `owner` names where the bound came from. This module owns no cadences: the number is the one
    the producing organ already declares, cited so the two cannot drift into disagreeing.
    """
    age = age_hours(doc, field, now)
    if age is None:
        return unmeasured_component(
            key, artifact,
            f"{artifact} carries no usable `{field}` stamp -- {what} cannot be shown to be "
            "current, and an artifact with no readable age can never be shown to be STALE either, "
            "which is the state in which a dead monitor reads exactly like a live one")
    if age > max_age_h:
        return unmeasured_component(
            key, artifact,
            f"{artifact} is {age:g}h old against a {max_age_h:g}h bound ({owner}) -- {what}. A "
            "stale reading is not a bad reading and not a good one: it is last week's observation "
            "wearing today's date, and scoring it either way invents information")
    return None


#: The desk's per-organ liveness roster: which scheduled organ produced, how long ago, and against
#: what tolerance. Read by many aspects below, because "is the thing that measures X still running"
#: is a precondition for believing anything X publishes.
_LIVENESS = "data/organ_liveness.json"

#: The verdict vocabulary of check_organ_liveness.py, read rather than restated. FRESH means the
#: organ produced inside ITS OWN declared cadence; the two failure words are kept apart because
#: they need different repairs -- NEVER-PRODUCED is wiring, STALE is something that stopped.
_LIVENESS_FRESH = "FRESH"
_LIVENESS_DEAD = ("STALE", "NEVER-PRODUCED")


def _liveness_row(root: Path, script: str) -> dict[str, Any] | None:
    for row in _rows(_read_json(root / _LIVENESS), "organs") or []:
        if row.get("script") == script:
            return row
    return None


def liveness_component(root: Path, key: str, script: str) -> Component:
    """Is ONE named organ producing inside its own cadence, per the organ that owns cadences?

    THE THRESHOLD IS NOT SET HERE, deliberately. check_organ_liveness.py declares every organ's
    cadence and tolerance and publishes a per-row verdict; this reads that verdict. Re-deriving
    "how old is too old" here would give the desk two disagreeing answers about one organ, and the
    one this module invented would be the one nobody maintains.

    An organ ABSENT FROM THE ROSTER is UNMEASURED, never a zero: nothing is watching it, which is
    a different (and more actionable) fact than it being late.
    """
    row = _liveness_row(root, script)
    if row is None:
        return unmeasured_component(
            key, _LIVENESS,
            f"{_LIVENESS} carries no row for {script} -- the organ is not on the liveness roster, "
            "so NOTHING measures whether it produces. Add it there; an unwatched organ reads the "
            "same as a healthy one from here")
    state = str(row.get("state") or "")
    raw = row.get("artifacts")
    evidence = ", ".join(str(a) for a in raw) if isinstance(raw, list) and raw else "?"
    age, tol = _num(row.get("age_h")), _num(row.get("tolerance_h"))
    detail = (f"{script} is {state or 'UNSTATED'} "
              f"(age {age if age is not None else 'never'}h against its own "
              f"{tol if tol is not None else '?'}h tolerance); evidence {evidence}")
    if state == _LIVENESS_FRESH:
        return Component(key=key, state=MEASURED, score=SCALE_MAX, artifact=_LIVENESS,
                         detail=detail,
                         constraint="AT CEILING -- producing inside its own declared cadence, and "
                                    "the work is now HOLDING it")
    if state in _LIVENESS_DEAD:
        fix = (f"WIRE IT -- {script} has NEVER produced {evidence}; that is a path/venv/lock "
               "fault, not a late run" if state == "NEVER-PRODUCED" else
               f"RESTART IT -- {script} last produced {age if age is not None else '?'}h ago "
               f"against a {tol if tol is not None else '?'}h tolerance; something STOPPED "
               "(auth, quota, upstream), which is a different repair from never wired")
        return Component(key=key, state=MEASURED, score=0.0, artifact=_LIVENESS, detail=detail,
                         constraint=fix)
    return unmeasured_component(
        key, _LIVENESS,
        f"{script} carries liveness state {state or 'EMPTY'!r}, which is neither FRESH nor a "
        "declared failure -- an unrecognised verdict is not scored in either direction")


# --------------------------------------------------------------------------------------------
# COMPONENT BUILDERS. Each reads ONE artifact this desk already produces. Nothing here computes a
# fresh measurement: a scorer that measures is a scorer that can be gamed by rewriting the scorer.
# --------------------------------------------------------------------------------------------

_MUTATION = "data/mutation_score.json"


def mutation_components(root: Path, key: str, prefixes: tuple[str, ...]) -> list[Component]:
    """Mutation kill rate over one slice of the tree, with TRUNCATED RUNS REFUSED.

    `budget_truncated` means the harness stopped at its mutant budget, so the kill rate describes
    the mutants it happened to reach rather than the file. Scoring it would reward a SHORTER run,
    which is the denominator trick (§34) wearing a stopwatch. Truncated targets become UNMEASURED
    components naming themselves, so the gap is visible instead of averaged away.

    The two reading rules -- skip truncated, prefer `adjusted_kill_rate` over the raw one where an
    equivalence register applies -- are lifted verbatim from scripts/check_ratchets.py:78-84 rather
    than re-derived. Two organs reading the same artifact by different rules is how a desk ends up
    with two disagreeing truths about one file.
    """
    doc = _read_json(root / _MUTATION)
    if doc is None:
        return [unmeasured_component(key, _MUTATION, f"{_MUTATION} absent or unreadable")]
    raw = doc.get("targets")
    targets = [t for t in raw if isinstance(t, dict)] if isinstance(raw, list) else []
    in_scope = [t for t in targets
                if isinstance(t.get("target"), str)
                and str(t["target"]).startswith(prefixes)]
    bar = _num(doc.get("bar"))
    out: list[Component] = []
    rates: list[float] = []
    names: list[str] = []
    for t in in_scope:
        name = str(t["target"])
        rate = _num(t.get("adjusted_kill_rate"))
        if rate is None:
            rate = _num(t.get("kill_rate"))
        if t.get("budget_truncated") is True:
            out.append(unmeasured_component(
                f"{key}::{Path(name).name}", _MUTATION,
                f"{name} ran BUDGET-TRUNCATED ({t.get('total')} of {t.get('n_sites')} sites) -- a "
                "truncated run samples the mutants it reached, so its kill rate is not a strength "
                "measurement and is refused rather than scored"))
            continue
        if rate is None:
            out.append(unmeasured_component(
                f"{key}::{Path(name).name}", _MUTATION, f"{name} carries no kill rate"))
            continue
        rates.append(rate)
        names.append(f"{Path(name).name} {rate:.2f}")
    if not rates:
        scope = ", ".join(prefixes)
        out.insert(0, unmeasured_component(
            key, _MUTATION,
            f"no completed mutation run over {scope} -- every target in scope is absent or "
            "budget-truncated"))
        return out
    mean = sum(rates) / len(rates)
    detail = (f"{len(rates)} target(s) at bar {bar if bar is not None else '?'}: "
              f"{', '.join(names)}; measured {doc.get('measured', '?')}")
    out.insert(0, fraction_component(key, _MUTATION, round(mean * 100, 2), 100.0,
                                     unit="% mutants killed", detail=detail))
    return out


_CALIBRATION = "data/calibration_status.json"


def _statistical_validation(root: Path, _now: datetime) -> list[Component]:
    out = mutation_components(root, "mutation_kill_validation_stack",
                              ("libs/validation/", "libs/autodiscovery/"))

    # A DESK THAT CANNOT SCORE ITS OWN FORECASTS CANNOT KNOW IT IS CALIBRATED. n_resolved/
    # n_forecasts is the completeness of the scoring loop, not the Brier score -- scoring the
    # Brier of zero resolved forecasts would be the 0/0 lie, and check_calibration already refuses
    # it by publishing status BLIND.
    cal = _read_json(root / _CALIBRATION)
    out.append(fraction_component(
        "forecasts_resolved", _CALIBRATION, _num(_field(cal, "n_resolved")),
        _num(_field(cal, "n_forecasts")), unit="logged forecasts scored against an outcome",
        detail=f"status {_field(cal, 'status')}: {_field(cal, 'detail')}; brier "
               f"{_field(cal, 'brier')}, {_field(cal, 'n_overdue')} overdue"))
    return out


_SUITE = "docs/research/test_suite_record.json"
_GRAVEYARD = "docs/graveyard.md"
_BREADTH = "data/strategy_coverage.json"
_CENSUS = "data/mechanism_census.json"
_SURFACES = "data/strategy_breadth.json"

#: A graveyard heading is an ENTRY (a killed hypothesis or a retired capability) rather than a
#: section banner when it names a thing: a backticked path or a snake_case identifier. Counting
#: every heading would score the three banners as kills; hardcoding the banner titles would rot the
#: first time somebody adds a section.
_GRAVE_HEADING = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$", re.MULTILINE)
_GRAVE_ENTRY = re.compile(r"`|[a-z0-9]+_[a-z0-9_]+")


def graveyard_kills(text: str) -> int:
    return sum(1 for m in _GRAVE_HEADING.finditer(text)
               if _GRAVE_ENTRY.search(m.group("title")) is not None)


def _research_discipline(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []

    suite = _read_json(root / _SUITE)
    n_modules = _num(_field(suite, "max_collected"))
    out.append(ladder_component(
        "test_suite_size", _SUITE, n_modules, SUITE_LADDER, unit="collectable test modules",
        detail=f"high-water suite size {n_modules} as of {_field(suite, 'at')}"))

    try:
        kills: int | None = graveyard_kills((root / _GRAVEYARD).read_text("utf-8"))
    except OSError:
        kills = None
    out.append(ladder_component(
        "hypotheses_killed", _GRAVEYARD, kills, COUNT_LADDER, unit="graveyard entries",
        detail=f"{kills} permanent kill/retirement entries -- the desk's record of ideas it "
               "closed rather than left open"))

    breadth = _read_json(root / _BREADTH)
    out.append(fraction_component(
        "families_hunted", _BREADTH, _num(_field(breadth, "n_hunted")),
        _num(_field(breadth, "n_families")), unit="families genuinely hunted",
        detail=f"{_field(breadth, 'n_hunted')}/{_field(breadth, 'n_families')} distinct families "
               f"worked; thin {_field(breadth, 'n_thin')}, unhunted "
               f"{_field(breadth, 'n_unhunted')}"))

    # MECHANISM DIVERSITY, from the census that owns the taxonomy. Counting candidates would
    # reward reparameterising one idea 40 times; classes occupied cannot be bought that way.
    census = _read_json(root / _CENSUS)
    div = _mapping(census, "diversity") or {}
    out.append(fraction_component(
        "mechanism_classes_occupied", _CENSUS, _num(div.get("n_classes_occupied")),
        _num(div.get("n_classes_in_taxonomy")), unit="taxonomy classes with a live candidate",
        detail=f"{div.get('n_classes_occupied')}/{div.get('n_classes_in_taxonomy')} classes "
               f"occupied over {div.get('n_candidates')} candidates; top class "
               f"{div.get('top_class')} at {div.get('top_class_share')} share"))
    out.append(fraction_component(
        "mechanism_diversity", _CENSUS, _num(div.get("diversity")), 1.0,
        unit="of the census's own normalised diversity index",
        detail=f"diversity {div.get('diversity')} (hhi {div.get('hhi')}, effective classes "
               f"{div.get('effective_classes')}); the CAMPAIGN is narrower still at "
               f"{(_mapping(census, 'campaign_diversity') or {}).get('diversity')}"))

    # HUNTING SURFACES CARRYING THE BREADTH MANDATE. `breadth.state` is checked because the
    # organ runs in a surfaces-only mode on a clean checkout: a partial run must not be scored as
    # a complete one, so the widened count is read and the live breadth measurement is not.
    surfaces = _read_json(root / _SURFACES)
    n_surf = _num(_field(surfaces, "n_surfaces"))
    unwidened = _len_or_none(_field(surfaces, "unwidened_surfaces"))
    out.append(fraction_component(
        "surfaces_carrying_the_mandate", _SURFACES,
        None if n_surf is None or unwidened is None else n_surf - unwidened, n_surf,
        unit="hunting surfaces carrying the breadth mandate",
        detail=f"status {_field(surfaces, 'status')}; live breadth state "
               f"{(_mapping(surfaces, 'breadth') or {}).get('state')} -- the live measurement is "
               "NOT scored here when it did not run"))
    return out


_GATE0 = "data/gate0_readiness.json"


def _gate0_rows(root: Path) -> list[dict[str, Any]]:
    doc = _read_json(root / _GATE0)
    raw = doc.get("rows") if doc is not None else None
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _risk_rails(root: Path, _now: datetime) -> list[Component]:
    out = mutation_components(root, "mutation_kill_risk_stack", ("libs/risk/",))

    # THE RUIN RAIL IS BINARY AND ITS THIRD STATE IS THE INTERESTING ONE. gate0 records
    # BLOCKED-UNKNOWN when the state file cannot be read from this box -- which is neither clear
    # nor breached, and folding it into either direction would be exactly the lie this module
    # exists to prevent.
    row = next((r for r in _gate0_rows(root) if r.get("criterion") == "ruin_rail_clear"), None)
    status = str(row.get("status")) if row is not None else ""
    detail = str(row.get("detail", "")) if row is not None else f"{_GATE0} carries no ruin-rail row"
    if row is None or status.startswith("BLOCKED"):
        out.append(unmeasured_component(
            "ruin_rail_clear", _GATE0,
            f"ruin-rail state is {status or 'ABSENT'} -- {detail}"))
    else:
        clear = status == "READY"
        out.append(Component(
            key="ruin_rail_clear", state=MEASURED, score=SCALE_MAX if clear else 0.0,
            artifact=_GATE0, detail=f"ruin_rail_clear={status}: {detail}",
            constraint=("AT CEILING -- the rail is clear and the work is HOLDING it" if clear
                        else f"clear the ruin rail: {row.get('action') or detail}")))

    # EVERY NUMBER THAT MOVES MONEY CARRIES A CITED DERIVATION. Four money-path constants were
    # found defective in one session, all of them round numbers picked by analogy (L1.41/L2.4).
    sizing = _read_json(root / _SIZING)
    n_modules = _num(_field(sizing, "n_modules"))
    unjustified = _num(_field(sizing, "n_unjustified"))
    out.append(fraction_component(
        "sizing_constants_derived", _SIZING,
        None if n_modules is None or unjustified is None else n_modules - unjustified, n_modules,
        unit="money-path modules with every constant derived",
        detail=f"status {_field(sizing, 'status')}: {_field(sizing, 'detail')}"))

    # THE RAILS ARE ONLY AS GOOD AS THE LAST TIME THEY WERE FIRED IN ANGER. run_drills exercises
    # ruin re-entry, the derisk ladder and the naked-clock rail against temp-copy state.
    drills = _read_json(root / _DRILLS)
    out.append(fraction_component(
        "drills_passing", _DRILLS, _num(_field(drills, "passed")), _num(_field(drills, "n_drills")),
        unit="rail drills passing",
        detail=f"{_field(drills, 'passed')}/{_field(drills, 'n_drills')} drills passed at "
               f"{_field(drills, 'at')}; {_field(drills, 'critical_drill_failures')} CRITICAL "
               "failure(s)"))
    out.append(liveness_component(root, "drill_cadence", "scripts/run_drills.py"))
    return out


_LAW_GATE = "data/law_gate.json"
_AUDIT = "data/max_audit_report.json"
_ENFORCEMENT = "data/enforcement_matrix.json"
_LAW_FAMILIES = "data/law_families.json"
_FENCE_YIELD = "data/fence_yield.json"


def _audit_defects(root: Path, prefix: str) -> float | None:
    """Live audit defects whose id starts with `prefix`, or None when there is no audit at all.

    NO REPORT IS NOT ZERO DEFECTS. The distinction is the whole point of counting them here: an
    absent max_audit_report means nobody looked, and returning 0.0 would score that as a clean
    bill of health -- the exact inversion this module exists to prevent.
    """
    live = _rows(_read_json(root / _AUDIT), "live")
    if live is None:
        return None
    return float(sum(1 for r in live if str(r.get("id") or "").startswith(prefix)))


def _governance(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    gate = _read_json(root / _LAW_GATE)
    n_fences = _num(_field(gate, "n_fences"))
    n_failed = _num(_field(gate, "n_failed"))
    passing = None if n_fences is None or n_failed is None else n_fences - n_failed
    out.append(fraction_component(
        "law_fences_passing", _LAW_GATE, passing, n_fences, unit="law fences passing",
        detail=f"{passing}/{n_fences} fences green; failures {_field(gate, 'failures')}"))

    audit = _read_json(root / _AUDIT)
    live = _field(audit, "live")
    n_live = float(len(live)) if isinstance(live, list) else None
    out.append(inverse_ladder_component(
        "audit_defects_live", _AUDIT, n_live, DEFECT_LADDER, unit="live audit defects",
        detail=f"{n_live} unacknowledged defects at {_field(audit, 'ran')}; "
               f"by scope {_field(audit, 'by_scope')}"))

    # A PRINCIPLE WITH NO FENCE IS A WISH. The enforcement matrix is the register of which
    # constitutional principles are held up by machinery rather than by attention.
    matrix = _read_json(root / _ENFORCEMENT)
    counts = _mapping(matrix, "counts") or {}
    out.append(fraction_component(
        "principles_mechanically_enforced", _ENFORCEMENT, _num(counts.get("ENFORCED")),
        _num(_field(matrix, "n_principles")), unit="principles held up by a fence",
        detail=f"{counts.get('ENFORCED')}/{_field(matrix, 'n_principles')} enforced over "
               f"{_field(matrix, 'n_fences')} fences; counts {counts}; unenforced "
               f"{_field(matrix, 'unenforced')}"))

    families = _read_json(root / _LAW_FAMILIES)
    n_fam = _num(_field(families, "n_families"))
    failing = _len_or_none(_field(families, "failing"))
    out.append(fraction_component(
        "law_families_enforced", _LAW_FAMILIES,
        None if n_fam is None or failing is None else n_fam - failing, n_fam,
        unit="law families fully enforced",
        detail=f"status {_field(families, 'status')}: {_field(families, 'detail')} over "
               f"{_field(families, 'n_laws_governed')} governed laws"))

    # A FENCE THAT HAS NEVER CAUGHT ANYTHING IS EITHER GUARDING NOTHING OR NOT LOOKING. Both are
    # worth a point of governance; check_fence_yield is the organ that decides which.
    yield_doc = _read_json(root / _FENCE_YIELD)
    out.append(fraction_component(
        "fences_earning_their_place", _FENCE_YIELD, _num(_field(yield_doc, "n_fired")),
        _num(_field(yield_doc, "n_fences")), unit="fences that have caught something real",
        detail=f"status {_field(yield_doc, 'status')}: {_field(yield_doc, 'detail')}; never run "
               f"{_field(yield_doc, 'n_never_run')}"))
    return out


_ASSETS = "data/data_assets.json"
_EXPLORATION = "data/exploration_status.json"
_PROVENANCE = "docs/research/data_provenance.json"
_ANNOUNCE = "data/announcement_collector.json"


def _data_coverage(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    assets = _read_json(root / _ASSETS)
    raw = _field(assets, "counts")
    counts: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out.append(fraction_component(
        "assets_with_measured_span", _ASSETS, _num(counts.get("measured")),
        _num(counts.get("assets")), unit="registered assets carrying a measured span",
        detail=f"{counts.get('measured')}/{counts.get('assets')} assets have a readable span "
               f"({counts.get('absent')} absent on disk); deep={_field(assets, 'deep')}"))

    expl = _read_json(root / _EXPLORATION)
    out.append(fraction_component(
        "exploration_organs_fresh", _EXPLORATION, _num(_field(expl, "n_fresh")),
        _num(_field(expl, "n_organs")), unit="unknown-unknown organs fresh",
        detail=f"status {_field(expl, 'status')}: {_field(expl, 'n_fresh')} fresh, "
               f"{_field(expl, 'n_stale')} stale, {_field(expl, 'n_dark')} dark"))

    # PROVENANCE IS PART OF THE DATA. A series whose collection method, survivorship and
    # manipulation risk are unrecorded cannot be reasoned about, only used.
    prov = _read_json(root / _PROVENANCE)
    out.append(ladder_component(
        "datasets_with_declared_provenance", _PROVENANCE,
        _len_or_none(_field(prov, "datasets")), COUNT_LADDER,
        unit="datasets carrying source/method/survivorship",
        detail=f"{_len_or_none(_field(prov, 'datasets'))} datasets declared in the provenance "
               "register -- collection method, manipulation risk and survivorship per series"))

    # A COLLECTOR WITH A DEAD SOURCE IS A DARK CORNER WEARING A GREEN LIGHT.
    ann = _read_json(root / _ANNOUNCE)
    out.append(inverse_ladder_component(
        "announcement_sources_failing", _ANNOUNCE, _len_or_none(_field(ann, "source_errors")),
        DEFECT_LADDER, unit="announcement sources erroring",
        detail=f"status {_field(ann, 'status')}: {_field(ann, 'detail')}; median latency "
               f"{_field(ann, 'median_latency_minutes')}min"))
    return out


_COVERAGE = "docs/research/COVERAGE_RATCHET.json"
_FORENSICS = "docs/research/trade_forensics_latest.json"


def _execution_path(root: Path, _now: datetime) -> list[Component]:
    doc = _read_json(root / _GATE0)
    out: list[Component] = [fraction_component(
        "gate0_readiness", _GATE0, _num(_field(doc, "n_ready")), _num(_field(doc, "n_criteria")),
        unit="S1-entry criteria ready",
        detail=f"desk owes {_field(doc, 'desk_owes')}, principal owes "
               f"{_field(doc, 'principal_owes')}")]

    cov = _read_json(root / _COVERAGE)
    raw = _field(cov, "measured")
    measured: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out.append(fraction_component(
        "money_path_coverage", _COVERAGE, _num(measured.get("money_path_pct")), 100.0,
        unit="% money-path statement coverage",
        detail=f"{measured.get('money_path_pct')}% over "
               f"{measured.get('money_path_statements')} statements on the order path "
               f"(repo {measured.get('repo_pct')}%)"))

    out += mutation_components(root, "mutation_kill_execution_stack", ("libs/execution/",))

    # MAKER SHARE AGAINST THE DESK'S OWN TARGET, which is carried IN the forensics artifact --
    # 0.6 is trade forensics' number, not this module's, and lifting it keeps one target rather
    # than two. Fees are the dominant carry cost, so this is the live unit-economics lever.
    fore = _read_json(root / _FORENSICS)
    tape = _mapping(fore, "maker_fill") or {}
    out.append(fraction_component(
        "maker_fill_share", _FORENSICS, _num(tape.get("maker_share")), _num(tape.get("target")),
        unit="of the desk's own maker-share target",
        detail=f"maker share {tape.get('maker_share')} over {tape.get('n_legs')} legs "
               f"(spot {tape.get('spot')}, fut {tape.get('fut')}) against target "
               f"{tape.get('target')}; measured {_field(fore, 'updated')}"))

    # FEE ATTRIBUTION COMPLETENESS. An unattributed fee is money leaving the desk for a reason
    # nobody has named -- and the artifact states its own scope limit (futures only, a LOWER
    # BOUND), which is carried into the detail rather than dropped.
    fees = _mapping(fore, "fee_attribution") or {}
    out.append(fraction_component(
        "fees_attributed", _FORENSICS, _num(fees.get("attributed")),
        _num(fees.get("venue_commission")), unit="of billed commission attributed to a cause",
        detail=f"{fees.get('attributed')} of {fees.get('venue_commission')} attributed over "
               f"{fees.get('n_events')} events ({fees.get('unattributed')} unattributed); scope "
               f"{fees.get('scope')}"))
    return out


_LEDGER = "docs/research/recommendation_ledger.json"
_CONVERSION = "data/conversion_status.json"
_INSTRUMENTATION = "data/instrumentation_coverage.jsonl"
_CHASE = "data/instrumentation_chase.json"

#: Terminal ledger statuses, read from scripts/check_conversion.py so the two organs cannot drift
#: into disagreeing about what "converted" means on the same file.
TERMINAL_STATUSES = frozenset({"implemented", "rejected", "retired", "done", "screened"})


def _self_improvement(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    doc = _read_json(root / _LEDGER)
    raw = _field(doc, "recommendations")
    rows = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else None
    if rows is None:
        out.append(unmeasured_component("ledger_dispositioned", _LEDGER,
                                        f"{_LEDGER} absent or carries no recommendations array"))
    else:
        terminal = float(sum(1 for r in rows if r.get("status") in TERMINAL_STATUSES))
        open_rows = len(rows) - terminal
        out.append(fraction_component(
            "ledger_dispositioned", _LEDGER, terminal, float(len(rows)),
            unit="ledger rows reaching a terminal verdict",
            detail=f"{terminal:g} dispositioned of {len(rows)} raised ({open_rows:g} still open "
                   "or scheduled) -- a reasoned rejection counts, silence does not"))

    conv = _read_json(root / _CONVERSION)
    arrivals = _num(_field(conv, "arrivals_7d"))
    disposals = _num(_field(conv, "dispositions_7d"))
    if conv is not None and arrivals is not None and arrivals <= 0:
        # ZERO ARRIVALS IS NOT PERFECT CONVERSION. disposals/arrivals would be 0/0, and the
        # tempting reading -- "nothing arrived, so everything was converted" -- scores a desk that
        # stopped finding things as a desk that fixed everything.
        out.append(unmeasured_component(
            "conversion_flow_7d", _CONVERSION,
            "zero findings arrived in 7 days -- the conversion RATIO is undefined over an empty "
            "numerator and denominator, and an idle finder must never read as a perfect fixer"))
    else:
        out.append(fraction_component(
            "conversion_flow_7d", _CONVERSION,
            None if disposals is None or arrivals is None else min(disposals, arrivals),
            arrivals, unit="of the last 7 days' arrivals dispositioned",
            detail=f"status {_field(conv, 'status')}: {disposals} dispositioned vs {arrivals} "
                   f"raised in 7d; backlog {_field(conv, 'backlog')}, oldest "
                   f"{_field(conv, 'oldest_backlog_age_days')}d"))

    # THE DESK CANNOT IMPROVE WHAT IT CANNOT SEE ITSELF DOING. instrumentation_coverage is the
    # ledger of how much of the desk's own behaviour is instrumented at all; the chase counter
    # beside it never resets except by CLOSING a gap.
    rows = _read_jsonl(root / _INSTRUMENTATION)
    if not rows:
        out.append(unmeasured_component(
            "instrumentation_coverage", _INSTRUMENTATION,
            f"{_INSTRUMENTATION} absent or empty -- nothing records how much of the desk's own "
            "behaviour is instrumented, and an uninstrumented desk cannot tell improvement from "
            "drift"))
    else:
        last = rows[-1]
        out.append(fraction_component(
            "instrumentation_coverage", _INSTRUMENTATION, _num(last.get("coverage_pct")), 100.0,
            unit="% of declared instrumentation points wired",
            detail=f"{last.get('instrumented')} instrumented, {last.get('owed')} owed at "
                   f"{last.get('ts')} over {len(rows)} recorded sweeps"))

    chase = _read_json(root / _CHASE)
    out.append(inverse_ladder_component(
        "instrumentation_gaps_owed", _CHASE, _len_or_none(_field(chase, "cycles_owed")),
        DEFECT_LADDER, unit="instrumentation gaps standing open across cycles",
        detail=f"{_len_or_none(_field(chase, 'cycles_owed'))} gap(s) carrying a cycle counter at "
               f"{_field(chase, 'updated')} -- the counter never resets except by closing the gap"))
    return out


_READINESS = "data/organ_readiness.json"
_ORGAN_ER = "data/organ_er.json"
_KERNEL_LOG = "data/kernel_log_status.json"


def _ops_autonomy(root: Path, _now: datetime) -> list[Component]:
    live = _read_json(root / _LIVENESS)
    dark = _field(live, "never_produced")
    stale = _field(live, "stale")
    out: list[Component] = [fraction_component(
        "organs_producing", _LIVENESS, _num(_field(live, "n_fresh")),
        _num(_field(live, "n_checked")), unit="scheduled organs producing fresh output",
        detail=f"status {_field(live, 'status')}: "
               f"{len(dark) if isinstance(dark, list) else '?'} never produced, "
               f"{len(stale) if isinstance(stale, list) else '?'} stale")]

    ready = _read_json(root / _READINESS)
    n_ready = _num(_field(ready, "ready"))
    n_not = _num(_field(ready, "not_ready"))
    total = None if n_ready is None or n_not is None else n_ready + n_not
    out.append(fraction_component(
        "organs_ready", _READINESS, n_ready, total, unit="organs assembling a lawful prompt",
        detail=f"{n_ready}/{total} organs ready at {_field(ready, 'ts')} "
               f"(gate_ok={_field(ready, 'gate_ok')})"))

    # THE ER IS THE ESCALATION LAYER: an organ that stopped is SICK, one that stopped for >24h is
    # in COMA, and an UNTREATED coma is the state where autonomy has actually failed.
    er = _read_json(root / _ORGAN_ER)
    out.append(fraction_component(
        "organs_healthy", _ORGAN_ER, _num(_field(er, "n_healthy")), _num(_field(er, "n_organs")),
        unit="organs healthy under the ER's own triage",
        detail=f"status {_field(er, 'status')}: {_field(er, 'detail')}; untreated comas "
               f"{_field(er, 'untreated_comas')}"))
    out.append(inverse_ladder_component(
        "organ_comas_untreated", _ORGAN_ER, _len_or_none(_field(er, "untreated_comas")),
        DEFECT_LADDER, unit="comatose organs with no treatment applied",
        detail=f"{_len_or_none(_field(er, 'untreated_comas'))} untreated coma(s) after "
               f"{_field(er, 'coma_hours')}h; treatments {_field(er, 'treatments')}"))

    # CAN THE BOX SEE ITS OWN KILLS? A 'no OOM' conclusion is only a measurement if a kernel event
    # was provably readable first (R0350/L1.40) -- the fraction of channels that read is that
    # proof, and check_kernel_log owns the probe.
    kern = _read_json(root / _KERNEL_LOG)
    out.append(fraction_component(
        "kernel_log_channels_readable", _KERNEL_LOG,
        _len_or_none(_field(kern, "readable_channels")), _len_or_none(_field(kern, "channels")),
        unit="kernel-log channels provably readable",
        detail=f"verdict {_field(kern, 'verdict')}: {_field(kern, 'detail')}"))
    return out


_QUEUE = "data/promotion_queue.json"
_PROMOTION = "data/promotion_gate.json"


def _alpha_output(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    queue = _read_json(root / _QUEUE)
    raw = _field(queue, "slots")
    slots: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out.append(fraction_component(
        "forward_slots_occupied", _QUEUE, _num(slots.get("occupied")), _num(slots.get("cap")),
        unit="forward slots carrying a live clock",
        detail=f"{slots.get('occupied')}/{slots.get('cap')} slots running; "
               f"{_field(queue, 'n_candidates')} screened survivors queued"))

    gate = _read_json(root / _PROMOTION)
    ladder = _field(gate, "ladder")
    rungs = ([_num(r.get("rung")) for r in ladder if isinstance(r, dict)]
             if isinstance(ladder, list) else [])
    top = max((r for r in rungs if r is not None), default=None)
    out.append(fraction_component(
        "promotion_rung", _PROMOTION, _num(_field(gate, "granted_rung")), top,
        unit="promotion rungs granted",
        detail=f"granted '{_field(gate, 'granted')}' at rung {_field(gate, 'granted_rung')}, "
               f"blocked at {_field(gate, 'blocked_at_rung')} over "
               f"{_field(gate, 'n_closed')} closed trades"))
    return out


# --------------------------------------------------------------------------------------------
# THE MINOR ASPECTS. The standing order is "every aspect", not "the nine headline ones", and the
# surface below is where a desk actually rots: the pager that died between incidents, the cost
# model nobody refreshed, the seat with no credential, the backup nobody restored. None of these
# is glamorous and every one of them has taken a desk down.
# --------------------------------------------------------------------------------------------

_ALERT_LEDGER = "data/alert_delivery.jsonl"
_ALERT_SILENT = "data/ALERT_CHANNELS_SILENT"
_ALERT_CANARY = "data/alert_canary_state.json"

#: How old the canary's last run may be before its verdict stops counting. NOT a number this
#: module invented: it is the canary's OWN throttle -- `--interval-h` defaults to 6.0 in
#: scripts/run_alert_canary.py:49, which is that organ's statement of how often it intends to run
#: (its cron line is tighter still, so 6h is several missed ticks and comfortably past "the box
#: was busy"). Lifting it rather than picking one keeps the desk from holding two different
#: opinions about when the canary is late.
CANARY_MAX_AGE_H = 6.0
_CANARY_OWNER = "scripts/run_alert_canary.py --interval-h default"


def _alerting(root: Path, now: datetime) -> list[Component]:
    """Does the pager provably deliver BETWEEN incidents?

    The failure this scores is on the record twice: quota exhaustion left the pager dead five
    days, and a latin-1 header encode killed 39/39 pushes for 29h across a live dead-man fire.
    Alerts only fire on incidents, so a broken alert path looks exactly like a quiet desk -- which
    is why the DELIVERY LEDGER, not the alerting code, is the artifact that settles it.
    """
    out: list[Component] = []
    rows = _read_jsonl(root / _ALERT_LEDGER)
    if rows is None:
        out.append(unmeasured_component(
            "pager_deliveries_ok", _ALERT_LEDGER,
            f"{_ALERT_LEDGER} absent -- there is no delivery ledger, so 'the pager works' is an "
            "assumption. libs/ops/alert_channels writes one row per attempt per channel; that "
            "file is what would settle it"))
    else:
        delivered = float(sum(1 for r in rows if r.get("ok") is True))
        last = rows[-1] if rows else {}
        out.append(fraction_component(
            "pager_deliveries_ok", _ALERT_LEDGER, delivered, float(len(rows)),
            unit="logged page attempts that DELIVERED",
            detail=f"{delivered:g}/{len(rows)} ledger attempts delivered; last row channel "
                   f"{last.get('channel')} ok={last.get('ok')} -- {str(last.get('detail'))[:90]}"))

    # THE SILENCE FLAG IS THE CANARY'S OWN VERDICT, written using ITS lookback window, not one
    # invented here. But that verdict is only worth anything while the canary is ALIVE, and the
    # two directions are not symmetric:
    #
    #   FLAG PRESENT is a positive assertion of silence that only a successful delivery clears. It
    #       is scored 0 whatever the canary's age -- the last thing anyone established was that the
    #       pager was dead, and nothing since has said otherwise. Downgrading that to UNMEASURED
    #       because the canary later died would be the flattering reading of a monitor dying while
    #       reporting a fault, which is the worst moment to stop counting it.
    #   FLAG ABSENT proves nothing on its own -- an unrun canary, a dead canary and a healthy pager
    #       all leave the same empty directory. So absence is only a 10 while the canary is FRESH,
    #       and otherwise UNMEASURED.
    #
    # WITHOUT THE AGE CHECK this component read 10/10 AT CEILING forever off ONE observation
    # receding into the past: run the canary once, clear the flag, let the canary die, and a dead
    # pager scores identically to a live one while looking more confident every day. That is the
    # same shape as the five-day dead pager this whole aspect exists to catch. A monitor that
    # cannot report its own death is not a monitor.
    flag = root / _ALERT_SILENT
    note = ""
    if flag.exists():
        try:
            note = flag.read_text("utf-8").strip()
        except (OSError, UnicodeDecodeError):
            note = "(flag present, unreadable)"
    canary = _read_json(root / _ALERT_CANARY)
    age = age_hours(canary, "last_canary", now)
    stale = stale_gate("alert_channels_not_silent", _ALERT_CANARY, canary, "last_canary", now,
                       max_age_h=CANARY_MAX_AGE_H, owner=_CANARY_OWNER,
                       what="the canary's own liveness, which is what makes the silence flag's "
                            "ABSENCE mean anything")
    if flag.exists():
        out.append(Component(
            key="alert_channels_not_silent", state=MEASURED, score=0.0, artifact=_ALERT_SILENT,
            detail=f"SILENCE FLAG PRESENT: {note[:150]} (canary last ran "
                   f"{age if age is not None else '?'}h ago)",
            constraint="ARM A CHANNEL and deliver one page: the canary's own audit found no "
                       "delivery on ANY channel inside its lookback, which is the state that hid "
                       "a dead pager for five days. The flag clears itself on the next successful "
                       "delivery -- nothing else clears it"))
    elif stale is not None:
        out.append(stale)
    else:
        out.append(binary_component(
            "alert_channels_not_silent", _ALERT_SILENT, True,
            detail=f"no silence flag, and the canary ran {age}h ago (bound {CANARY_MAX_AGE_H:g}h) "
                   "-- a live canary that is not complaining",
            fix="",
            held="AT CEILING -- a page has landed inside the canary's own lookback AND the canary "
                 "is itself alive; HOLDING it means keeping the canary on its cadence, because a "
                 "silent canary and a working pager look identical from here"))
    return out


_COST_HUNT = "data/cost_hunt.json"
_ECONOMICS = "data/execution_economics.json"

#: execution_economics' own sentinel for an input it could not read on this box. Read, not
#: restated: it is that organ's vocabulary for "absent", and it deliberately never writes 0.0.
_NOT_READABLE = "NOT-READABLE-HERE"


def _cost_model(root: Path, _now: datetime) -> list[Component]:
    """Is the cost model FRESH, and is the realised-versus-modelled residual measurable at all?

    Cost is the only input that decides whether an edge survives contact with a venue, and it is
    the input most prone to silent staleness: a model fitted once and never refreshed reports the
    same confident number forever while the venue's fees, funding and depth all move.
    """
    hunt = _read_json(root / _COST_HUNT)
    out = [fraction_component(
        "funding_rates_measured", _COST_HUNT, _num(_field(hunt, "n_measured")),
        _num(_field(hunt, "n_symbols")), unit="universe symbols with a measured funding rate",
        detail=f"status {_field(hunt, 'status')}: {_field(hunt, 'detail')}")]
    out.append(liveness_component(root, "cost_hunt_freshness", "scripts/run_cost_hunt.py"))
    out.append(liveness_component(root, "cost_surface_identified",
                                  "scripts/run_cost_identification.py"))

    # INPUT READABILITY, NOT THE RESIDUAL. A residual computed over inputs that were mostly
    # unreadable is a partial measurement, and scoring it as a whole one is precisely the failure
    # the truncated-mutation rule forbids. What IS complete and scoreable is how many of the
    # model's declared inputs this box can read at all.
    econ = _read_json(root / _ECONOMICS)
    inputs = _mapping(econ, "inputs")
    if inputs is None or not inputs:
        out.append(unmeasured_component(
            "cost_inputs_readable", _ECONOMICS,
            f"{_ECONOMICS} carries no inputs map -- the cost model's own account of what it could "
            "read is what makes its residual believable, and without it the residual is a number "
            "with no denominator"))
    else:
        readable = float(sum(1 for v in inputs.values() if str(v) != _NOT_READABLE))
        out.append(fraction_component(
            "cost_inputs_readable", _ECONOMICS, readable, float(len(inputs)),
            unit="declared cost-model inputs readable from this box",
            detail=f"status {_field(econ, 'status')}: {readable:g}/{len(inputs)} inputs readable "
                   f"({', '.join(k for k, v in inputs.items() if str(v) == _NOT_READABLE)} are "
                   f"{_NOT_READABLE}); thresholds read from "
                   f"{(_mapping(econ, 'thresholds_read_not_declared') or {}).get('sources')}"))
    return out


_REPLACEMENT = "data/replacement_rate.json"


def _forward_clock(root: Path, _now: datetime) -> list[Component]:
    """Do the desk's forward clocks MEAN anything -- measured latency, countable births?

    A forward clock is the desk's only honest evidence generator, and its hygiene is separate from
    how many slots are full (that is alpha_output). What is scored here is whether the clock's own
    numbers are measurements: a promotion latency assembled from DESIGN and ESTIMATED terms is a
    plan, not an observation, and a birth rate nobody can count cannot be compared to a death rate.
    """
    out: list[Component] = []
    latency = _mapping(_read_json(root / _QUEUE), "latency") or {}
    terms = _mapping(latency, "components")
    if terms is None or not terms:
        out.append(unmeasured_component(
            "promotion_latency_measured", _QUEUE,
            f"{_QUEUE} carries no latency component breakdown -- a single total with no "
            "provenance per term cannot be told apart from a guess"))
    else:
        measured = float(sum(1 for v in terms.values()
                             if isinstance(v, dict) and v.get("provenance") == "MEASURED"))
        provenance = ", ".join(f"{k}={v.get('provenance')}"
                               for k, v in sorted(terms.items()) if isinstance(v, dict))
        out.append(fraction_component(
            "promotion_latency_measured", _QUEUE, measured, float(len(terms)),
            unit="latency terms MEASURED rather than designed or estimated",
            detail=f"total {latency.get('total_days')}d, fully_measured="
                   f"{latency.get('fully_measured')}; {provenance}"))

    rep = _read_json(root / _REPLACEMENT)
    births_flag = rep.get("births_measured") if rep is not None else None
    out.append(binary_component(
        "births_countable", _REPLACEMENT, births_flag if isinstance(births_flag, bool) else None,
        detail=f"status {_field(rep, 'status')}: {_field(rep, 'detail')}",
        fix="RECORD A DATED PROMOTION HISTORY -- births are UNCOUNTABLE, so the desk cannot say "
            "whether validated births keep pace with deaths (L1.30). Never loosen a validation "
            "bar to manufacture one: that turns a real countdown into a fake reprieve",
        held="AT CEILING -- births are counted from a dated promotion history; HOLDING it means "
             "keeping that history append-only"))

    rate = _num(_field(rep, "replacement_rate"))
    if rate is None:
        out.append(unmeasured_component(
            "replacement_rate", _REPLACEMENT,
            f"{_REPLACEMENT} publishes a null replacement rate ({_field(rep, 'status')}) -- with "
            "births uncountable the ratio is undefined, and an undefined ratio is not a 1.0"))
    else:
        out.append(fraction_component(
            "replacement_rate", _REPLACEMENT, rate, 1.0,
            unit="of one-for-one replacement over the window",
            detail=f"{_field(rep, 'births')} births vs {_field(rep, 'deaths')} deaths in "
                   f"{_field(rep, 'window_days')}d; {_field(rep, 'live_forward_clocks')} live "
                   "forward clocks"))
    return out


_CLOCK_PROVENANCE = "data/clock_provenance_status.json"
_BACKUP = "data/backup_status.json"

#: check_clock_provenance's two REFUSAL verdicts. They are not defects of the tape -- they are the
#: fence saying it had nothing to look at, and the one thing that fence may never do is report OK
#: because it found nothing. Scoring them as zero would invent a defect out of an absent corpus.
_CLOCK_REFUSALS = ("NO-DATA", "UNMEASURED")


def _recorder_tape(root: Path, _now: datetime) -> list[Component]:
    """Is the desk's OWN tape being recorded, and does its time axis mean what the schema implies?

    Three of the largest kills in the graveyard (kimchi_premium, coinbase_premium_timing, the
    leaky Upbit copies) are ONE defect class: a timestamp whose clock was never declared. Delta =
    t_recv - t_venue is structurally unbuyable and cannot be backfilled, so a day not recorded is
    a day gone permanently -- which is why tape health is scored beside the fancier aspects.
    """
    out: list[Component] = []
    doc = _read_json(root / _CLOCK_PROVENANCE)
    status = str(_field(doc, "status"))
    if doc is None:
        out.append(unmeasured_component(
            "tape_clock_declared", _CLOCK_PROVENANCE,
            f"{_CLOCK_PROVENANCE} absent -- scripts/check_clock_provenance.py has never produced "
            "it, so nothing has asked whether the tape's timestamps mean what its schema implies"))
    elif status in _CLOCK_REFUSALS:
        out.append(unmeasured_component(
            "tape_clock_declared", _CLOCK_PROVENANCE,
            f"the clock fence returned {status} -- {_field(doc, 'detail')}. That is the fence "
            "refusing to grade an absent or unclassifiable corpus, and a refusal is not a defect "
            "of the tape any more than it is a clean bill"))
    else:
        streams = _mapping(doc, "streams") or {}
        bad = ((_len_or_none(_field(doc, "mixed_clock_streams")) or 0.0)
               + (_len_or_none(_field(doc, "unknown_streams")) or 0.0))
        out.append(fraction_component(
            "tape_clock_declared", _CLOCK_PROVENANCE, float(len(streams)) - bad,
            float(len(streams)), unit="tape streams declaring the clock that stamped them",
            detail=f"status {status}: {_field(doc, 'detail')}; {_field(doc, 'rows_sampled')} rows "
                   f"sampled over {_field(doc, 'files_read')} files"))

    # THE TAPE STORE ITSELF, per the backup organ that inventories the desk's durable stores.
    stores = _mapping(_read_json(root / _BACKUP), "stores")
    tape = (stores or {}).get("execution_tape")
    tape_status = str((tape or {}).get("status") or "") if isinstance(tape, dict) else ""
    if not isinstance(tape, dict):
        out.append(unmeasured_component(
            "execution_tape_store", _BACKUP,
            f"{_BACKUP} carries no execution_tape store row -- the tape is the desk's proprietary "
            "moat and nothing is inventorying whether it exists"))
    else:
        out.append(binary_component(
            "execution_tape_store", _BACKUP, tape_status == "REPLICATED",
            detail=f"execution_tape is {tape_status} at {tape.get('path')}: "
                   f"{tape.get('note') or 'replicated'}",
            fix=f"RUN THE RECORDER -- the execution tape reads {tape_status} at "
                f"{tape.get('path')}. Delta between venue and receipt clocks cannot be "
                "backfilled, so every day it is absent is a day gone permanently",
            held="AT CEILING -- the tape exists and is replicated; HOLDING it is the recorder "
                 "staying up"))

    # THE RECORDING WINDOW ITSELF: forensics reports whether the retained buffer is squeezing the
    # analysis window, which is the early warning before a tape gap becomes a measurement gap.
    tape_stats = _mapping(_read_json(root / _FORENSICS), "execution_tape")
    squeeze = (tape_stats or {}).get("buffer_squeezing_window")
    out.append(binary_component(
        "tape_buffer_not_squeezing", _FORENSICS,
        (not squeeze) if isinstance(squeeze, bool) else None,
        detail=(f"{(tape_stats or {}).get('taped')} taped rows over "
                f"{(tape_stats or {}).get('tape_days')}d; buffer "
                f"{(tape_stats or {}).get('buffer_days')}d, window margin "
                f"{(tape_stats or {}).get('window_margin_days')}d"
                if tape_stats else
                f"{_FORENSICS} carries no execution_tape block -- retention pressure on the "
                "analysis window is not being watched"),
        fix="EXTEND RETENTION -- the retained buffer is squeezing the analysis window, so the "
            "next forensics pass will silently narrow rather than fail",
        held="AT CEILING -- the retained buffer clears the analysis window with margin"))
    return out


_RUNWAY = "data/miner_runway.json"

#: The seat verdict check_ratchets._miner_productive counts as productive. Lifted from there so
#: the ratchet floor and this score cannot disagree about what a working seat is.
_SEAT_OK = "ok"


def _llm_seats(root: Path, _now: datetime) -> list[Component]:
    """Are the desk's LLM seats WIRED, CREDENTIALLED and PRODUCING -- three different facts.

    The three are kept apart deliberately, because collapsing them is how a desk convinces itself
    it has a research bench: prompts and runners can all exist while every seat is unfunded, and
    an unreadable log directory means the productivity question cannot be answered AT ALL from
    this box. miner_runway states its own observability, and that state is honoured here.
    """
    doc = _read_json(root / _RUNWAY)
    seats = _mapping(doc, "seats")
    if seats is None or not seats:
        why = f"{_RUNWAY} carries no seat roster -- nothing enumerates the desk's LLM bench"
        return [unmeasured_component(k, _RUNWAY, why)
                for k in ("seats_wired", "seats_credentialled", "seats_productive")]

    rows = [s for s in seats.values() if isinstance(s, dict)]
    total = float(len(rows))
    wired = float(sum(1 for s in rows if s.get("prompt") and s.get("runner") and s.get("unit")))
    creds = float(sum(1 for s in rows if s.get("creds") is True))
    out = [fraction_component(
        "seats_wired", _RUNWAY, wired, total,
        unit="seats with prompt + runner + unit all present",
        detail=f"{wired:g}/{total:g} seats wired at {_field(doc, 'checked')}"),
        fraction_component(
        "seats_credentialled", _RUNWAY, creds, total, unit="seats carrying a credential",
        detail=f"{creds:g}/{total:g} seats credentialled (creds_present="
               f"{_field(doc, 'creds_present')}); a wired seat with no key is a bench that "
               "cannot sit down")]

    # OBSERVABILITY IS THE PRECONDITION, and this organ publishes it. `observable: false` means
    # the log directory could not be read, so seat productivity is UNKNOWN -- and 0 productive
    # seats out of 11 would be a fabricated defect rather than a measurement.
    if doc is not None and doc.get("observable") is not True:
        blockers = _rows(doc, "blockers") or []
        out.append(unmeasured_component(
            "seats_productive", _RUNWAY,
            f"{_RUNWAY} reports observable={_field(doc, 'observable')} -- "
            f"{(blockers[0].get('blocker') if blockers else 'run history unreadable here')}. The "
            "report says NOTHING about whether the seats ran, and an unreadable log is not an "
            "idle seat"))
    else:
        productive = float(sum(1 for s in rows if s.get("status") == _SEAT_OK))
        out.append(fraction_component(
            "seats_productive", _RUNWAY, productive, total,
            unit="seats producing inside their own max_age_h",
            detail=f"{productive:g}/{total:g} seats ok at {_field(doc, 'checked')}; by_status "
                   f"{_field(doc, 'by_status')}"))
    return out


_UTILISATION = "data/utilisation.json"


def _dependency_env(root: Path, _now: datetime) -> list[Component]:
    """Does the environment the suite runs in match the environment that runs the money?

    A green suite here is not evidence about production unless the deps match: `ruff>=0.5`
    resolving to 0.15.8 produced 36 errors production never saw, and a mypy minor-version gap
    made the same file clean on one box and red on another. max_audit owns the drift check and
    check_utilisation owns the importability ceiling; both are read, neither is re-derived.
    """
    out = [inverse_ladder_component(
        "dependency_drift_defects", _AUDIT, _audit_defects(root, "dependency-"), DEFECT_LADDER,
        unit="live dependency/pin defects raised by the audit",
        detail="max_audit's dependency checks: major-version drift vs the deployed pin set, "
               "pinned packages absent here, and pyproject floors sitting BELOW production")]

    ceiling = _ceiling_row(root, "optional_test_deps")
    if ceiling is None:
        out.append(unmeasured_component(
            "optional_test_deps_importable", _UTILISATION,
            f"{_UTILISATION} carries no optional_test_deps ceiling -- nothing measures whether "
            "declared optional dependencies import, and a test that skips on a missing dep prints "
            "one grey line and exits 0"))
    else:
        out.append(fraction_component(
            "optional_test_deps_importable", _UTILISATION, _num(ceiling.get("used")),
            _num(ceiling.get("limit")), unit="declared optional test deps importable here",
            detail=f"{ceiling.get('used')}/{ceiling.get('limit')} importable "
                   f"({ceiling.get('status')}): {ceiling.get('binding_constraint')}"))
    return out


def _ceiling_row(root: Path, name: str) -> dict[str, Any] | None:
    for row in _rows(_read_json(root / _UTILISATION), "ceilings") or []:
        if row.get("name") == name:
            return row
    return None


def _capital_utilisation(root: Path, _now: datetime) -> list[Component]:
    """Is paid-for capacity actually being USED -- capital, slots, wired capability?

    Unused headroom is not safety, it is an unbooked loss (L1.28a). The aggregate is deliberately
    computed over the MEASURED ceilings only and the unmeasured ones are listed by name: the
    utilisation organ's own convention scores an unmeasured ceiling as zero, which is right for a
    fence that must not reward ignorance but wrong for a capability score that must not invent a
    defect out of one. Both readings are published rather than merged.
    """
    doc = _read_json(root / _UTILISATION)
    rows = _rows(doc, "ceilings")
    if rows is None or not rows:
        return [unmeasured_component(
            "ceiling_utilisation", _UTILISATION,
            f"{_UTILISATION} carries no ceilings -- nothing enumerates the desk's paid-for "
            "capacity, so idle capacity cannot be told from absent capacity")]

    measured = [r for r in rows if r.get("measured") is True]
    out: list[Component] = [fraction_component(
        "ceilings_measured", _UTILISATION, float(len(measured)), float(len(rows)),
        unit="declared ceilings actually measurable here",
        detail=f"{len(measured)}/{len(rows)} ceilings measured; UNMEASURED "
               f"{_field(doc, 'unmeasured')}")]
    for row in rows:
        if row.get("measured") is not True:
            out.append(unmeasured_component(
                f"ceiling::{row.get('name')}", _UTILISATION,
                f"ceiling {row.get('name')} reports measured=false "
                f"({row.get('binding_constraint') or 'no reason given'}) -- it is excluded from "
                "the aggregate rather than folded in as a zero"))
    utilisations = [u for u in (_num(r.get("utilisation")) for r in measured) if u is not None]
    if not utilisations:
        out.append(unmeasured_component(
            "ceiling_utilisation", _UTILISATION,
            "no measured ceiling carries a utilisation figure -- the aggregate would be a mean "
            "over nothing"))
        return out
    mean = sum(utilisations) / len(utilisations)
    expect = _num(_field(doc, "expect_fraction"))
    out.append(fraction_component(
        "ceiling_utilisation", _UTILISATION, round(mean, 4), expect,
        unit="of the desk's own expected utilisation fraction",
        detail=f"mean {mean:.3f} over {len(utilisations)} MEASURED ceilings against an expected "
               f"{expect}; the organ's own headline (which counts unmeasured as zero) is "
               f"{_field(doc, 'mean_utilisation')}; idle_unexplained "
               f"{_field(doc, 'idle_unexplained')}"))
    return out


_KNOWLEDGE = "data/knowledge_engine.json"
_PLAYBOOK = "data/trading_playbook.json"
_LESSONS = "docs/desk_lessons.jsonl"


def _knowledge_currency(root: Path, _now: datetime) -> list[Component]:
    """Is what the desk has LEARNED retrievable, or does every cycle start from nothing?

    The expensive failure here is re-testing a dead hypothesis: compute spent to rediscover a
    result already in the graveyard. The knowledge engine is the retrieval layer that answers
    "has this effectively already been tested?" BEFORE the compute is spent, and the lesson
    ledgers are the desk's record of what an incident actually taught it.
    """
    doc = _read_json(root / _KNOWLEDGE)
    if doc is None:
        out = [unmeasured_component(
            "knowledge_corpus", _KNOWLEDGE,
            f"{_KNOWLEDGE} absent -- scripts/knowledge_engine.py has not produced it, so the "
            "'has this already been tested?' query has no index to run against and the graveyard "
            "is a document rather than a memory")]
    else:
        out = [ladder_component(
            "knowledge_corpus", _KNOWLEDGE, _num(doc.get("corpus_size")), COUNT_LADDER,
            unit="retrievable documents in the research memory",
            detail=f"corpus {doc.get('corpus_size')} at {doc.get('updated')}; "
                   f"{_len_or_none(doc.get('causal_edges'))} causal edges, blind-validation "
                   f"consistent={doc.get('blind_validation_consistent')}")]

    play = _read_json(root / _PLAYBOOK)
    out.append(ladder_component(
        "playbook_lessons", _PLAYBOOK, _len_or_none(_field(play, "lessons")), COUNT_LADDER,
        unit="playbook lessons distilled from closed trades",
        detail=f"{_len_or_none(_field(play, 'lessons'))} lesson(s) over "
               f"{_field(play, 'reviewed_keys')} reviewed keys, updated "
               f"{_field(play, 'updated')}"))

    lessons = _read_jsonl(root / _LESSONS)
    if lessons is None:
        out.append(unmeasured_component(
            "desk_lessons_recorded", _LESSONS,
            f"{_LESSONS} absent -- the desk's incident ledger is where a defect becomes a lesson "
            "instead of a recurrence; with no ledger, recurrence cannot even be counted"))
    else:
        out.append(ladder_component(
            "desk_lessons_recorded", _LESSONS, float(len(lessons)), COUNT_LADDER,
            unit="recorded desk lessons, each with its cost and recurrence count",
            detail=f"{len(lessons)} lesson(s); most recent "
                   f"{lessons[-1].get('id') if lessons else '?'} learned "
                   f"{lessons[-1].get('learned') if lessons else '?'}"))
    return out


_DRILLS = "data/drill_report.json"
_SIZING = "data/sizing_derivation.json"


def _backup_dr(root: Path, _now: datetime) -> list[Component]:
    """Could the desk be REBUILT -- and has anyone proved it by actually restoring?

    A backup nobody has restored from is a hypothesis, so the restore drill is scored separately
    from the replication count. The disk fuse is read from the artifact rather than restated here:
    run_moat_backup owns the percentage at which it refuses to keep writing.
    """
    doc = _read_json(root / _BACKUP)
    stores = _mapping(doc, "stores")
    if stores is None or not stores:
        out = [unmeasured_component(
            "stores_replicated", _BACKUP,
            f"{_BACKUP} carries no store inventory -- nothing enumerates what would have to "
            "survive a host loss, so 'we have backups' is untested in both directions")]
    else:
        rows = [s for s in stores.values() if isinstance(s, dict)]
        replicated = float(sum(1 for s in rows if s.get("status") == "REPLICATED"))
        absent = [k for k, s in stores.items()
                  if isinstance(s, dict) and s.get("status") != "REPLICATED"]
        out = [fraction_component(
            "stores_replicated", _BACKUP, replicated, float(len(rows)),
            unit="durable stores replicated off the host",
            detail=f"{replicated:g}/{len(rows)} stores replicated at {_field(doc, 'generated')}; "
                   f"NOT replicated: {', '.join(absent) or 'none'}")]

    drill = doc.get("restore_drill_passed") if doc is not None else None
    out.append(binary_component(
        "restore_drill_passed", _BACKUP, drill if isinstance(drill, bool) else None,
        detail=f"restore_drill_passed={drill}; status {_field(doc, 'status')}",
        fix="RESTORE FROM THE BACKUP AND PROVE IT -- an unrestored backup is a hypothesis, and "
            "the first restore attempt is not the moment to discover the archive is unreadable",
        held="AT CEILING -- a restore has actually been exercised; HOLDING it means re-running "
             "the drill, not trusting the last one"))

    free = _num(_field(doc, "disk_free_pct"))
    fuse = _num(_field(doc, "fuse_pct"))
    out.append(fraction_component(
        "disk_headroom_over_fuse", _BACKUP, free, fuse,
        unit="of the backup organ's own disk fuse",
        detail=f"disk free {free}% against a {fuse}% fuse (status {_field(doc, 'status')}); "
               f"uncovered {_field(doc, 'not_covered_note')}"))
    out.append(liveness_component(root, "backup_cadence", "scripts/run_moat_backup.py"))
    return out


def _mutation_breadth(root: Path, _now: datetime) -> list[Component]:
    """How much of the tree is mutation-tested AT ALL -- a different question from the kill rate.

    A desk can hold a 100% kill rate forever by mutation-testing one small file. Breadth is the
    denominator that stops that: how many money-path files carry a COMPLETE run, and how many
    targets exist. Truncated targets are excluded from the numerator exactly as they are from the
    kill rate -- a budget-truncated run has not covered the file, so counting it as covered would
    let the desk buy breadth by running less, which is the same trick one level up.
    """
    doc = _read_json(root / _MUTATION)
    if doc is None:
        why = f"{_MUTATION} absent -- nothing records which of the tree has been mutation-tested"
        return [unmeasured_component(k, _MUTATION, why)
                for k in ("money_path_files_mutated", "mutation_targets_complete",
                          "mutation_targets_at_bar")]

    targets = _rows(doc, "targets") or []
    complete = [t for t in targets
                if t.get("budget_truncated") is not True and isinstance(t.get("target"), str)]
    truncated = [str(t.get("target")) for t in targets if t.get("budget_truncated") is True]
    names = {str(t["target"]) for t in complete}

    # THE DENOMINATOR IS THE MONEY PATH THE COVERAGE RATCHET ALREADY DECLARES. Inventing a file
    # list here would let the breadth score be raised by editing this module.
    cov = _read_json(root / _COVERAGE)
    money = _field(cov, "money_path_files")
    money_files = [str(f) for f in money] if isinstance(money, list) else None
    if money_files is None:
        out = [unmeasured_component(
            "money_path_files_mutated", _COVERAGE,
            f"{_COVERAGE} declares no money_path_files list -- without the desk's own definition "
            "of the money path there is no honest denominator for breadth, and one invented here "
            "could be edited to raise the score")]
    else:
        hit = float(sum(1 for f in money_files if f in names))
        missing = [f for f in money_files if f not in names]
        out = [fraction_component(
            "money_path_files_mutated", _MUTATION, hit, float(len(money_files)),
            unit="money-path files carrying a COMPLETE mutation run",
            detail=f"{hit:g}/{len(money_files)} money-path files mutated; NOT mutated: "
                   f"{', '.join(missing) or 'none'}")]

    out.append(ladder_component(
        "mutation_targets_complete", _MUTATION, float(len(complete)), COUNT_LADDER,
        unit="modules with a complete (never truncated) mutation run",
        detail=f"{len(complete)} complete target(s) measured {_field(doc, 'measured')}; "
               f"{len(truncated)} truncated and excluded: {', '.join(truncated) or 'none'}"))
    for name in truncated:
        out.append(unmeasured_component(
            f"mutation_targets_complete::{Path(name).name}", _MUTATION,
            f"{name} ran BUDGET-TRUNCATED -- a truncated run has not covered the file, so it "
            "counts toward neither breadth nor strength"))

    # AT-BAR SHARE, with the bar READ from the artifact (check_ratchets holds the same rule) --
    # a scorer that owns its own bar is a scorer that can lower it.
    bar = _num(doc.get("bar"))
    rates: list[float] = []
    for t in complete:
        rate = _num(t.get("adjusted_kill_rate"))
        rate = rate if rate is not None else _num(t.get("kill_rate"))
        if rate is not None:
            rates.append(rate)
    if bar is None or not rates:
        out.append(unmeasured_component(
            "mutation_targets_at_bar", _MUTATION,
            f"{_MUTATION} carries no bar or no complete target with a kill rate -- the at-bar "
            "share is undefined and must not read as full marks"))
    else:
        at_bar = float(sum(1 for r in rates if r >= bar))
        out.append(fraction_component(
            "mutation_targets_at_bar", _MUTATION, at_bar, float(len(rates)),
            unit=f"complete targets meeting the artifact's own {bar:g} bar",
            detail=f"{at_bar:g}/{len(rates)} complete targets at bar {bar:g}"))
    return out


_SCHEDULER = "data/scheduler_manifest_report.json"


def _scheduler_integrity(root: Path, _now: datetime) -> list[Component]:
    """Does the scheduler MANIFEST describe the machine, and does the machine agree?

    A watchdog died and left the pager silent and the forward clocks frozen for 11.5 days while
    every timer looked healthy. The manifest checks are what make that detectable, and the
    live-crontab comparison is the half that actually proves the box matches the file -- which is
    why its unreadability is reported as UNMEASURED rather than folded into the passing checks.
    """
    doc = _read_json(root / _SCHEDULER)
    checks = _mapping(doc, "checks")
    if checks is None or not checks:
        return [unmeasured_component(
            "manifest_checks_passing", _SCHEDULER,
            f"{_SCHEDULER} absent or carries no checks -- nothing verifies that every scheduled "
            "line points at a script that exists, parses, and locks coherently")]

    verdicts = {k: v for k, v in checks.items() if isinstance(v, dict) and "ok" in v}
    passing = float(sum(1 for v in verdicts.values() if v.get("ok") is True))
    failing = [k for k, v in verdicts.items() if v.get("ok") is not True]
    out = [fraction_component(
        "manifest_checks_passing", _SCHEDULER, passing, float(len(verdicts)),
        unit="manifest integrity checks passing",
        detail=f"{passing:g}/{len(verdicts)} checks green over {_field(doc, 'cron_entries')} cron "
               f"and {_field(doc, 'systemd_entries')} systemd entries; failing: "
               f"{', '.join(failing) or 'none'}")]

    live = checks.get("live_crontab")
    live_map = live if isinstance(live, dict) else {}
    if live_map.get("readable") is not True:
        out.append(unmeasured_component(
            "live_crontab_matches_manifest", _SCHEDULER,
            f"the live crontab is not readable from this box ({live_map.get('note') or 'no note'})"
            " -- so manifest-versus-machine DRIFT is unmeasured. A manifest that agrees with "
            "itself is not evidence the box runs what it says"))
    else:
        drift = sum((_len_or_none(live_map.get(k)) or 0.0)
                    for k in ("missing_in_live", "extra_in_live", "duplicated_in_live"))
        out.append(inverse_ladder_component(
            "live_crontab_matches_manifest", _SCHEDULER, drift, DEFECT_LADDER,
            unit="manifest/live crontab discrepancies",
            detail=f"missing {live_map.get('missing_in_live')}, extra "
                   f"{live_map.get('extra_in_live')}, duplicated "
                   f"{live_map.get('duplicated_in_live')}"))
    return out


def _secret_permission(root: Path, _now: datetime) -> list[Component]:
    """Can the desk WRITE what it must write and READ what it must read -- and is it credentialled?

    Permission faults are the quietest class of outage on this box: an unwritable log directory
    turns every organ's evidence into nothing, and an absent credential turns a wired seat into a
    silent one. Desk code deliberately never WRITES a secret (a repo that can write its own
    secrets is a repo that can leak them), so the score here is about provisioning and access,
    never about the desk manufacturing keys for itself.
    """
    ready = _read_json(root / _READINESS)
    writable = ready.get("log_dir_writable") if ready is not None else None
    out = [binary_component(
        "log_dir_writable", _READINESS, writable if isinstance(writable, bool) else None,
        detail=f"log_dir_writable={writable}, gate_ok={_field(ready, 'gate_ok')}, doctrine "
               f"{_field(ready, 'doctrine_bytes')} bytes at {_field(ready, 'ts')}",
        fix="FIX THE LOG DIRECTORY PERMISSIONS -- an organ that cannot write its evidence "
            "produces nothing, and 'produced nothing' is indistinguishable from 'never ran'",
        held="AT CEILING -- the desk can write its own evidence")]

    runway = _read_json(root / _RUNWAY)
    creds = runway.get("creds_present") if runway is not None else None
    out.append(binary_component(
        "llm_credentials_provisioned", _RUNWAY, creds if isinstance(creds, bool) else None,
        detail=f"creds_present={creds} at {_field(runway, 'checked')}; log dir "
               f"{_field(runway, 'log_dir')}",
        fix="PROVISION THE CREDENTIAL -- it is an operator step by design (desk code must never "
            "write a secret). Until it lands, every seat is wired and unfunded",
        held="AT CEILING -- the seats are credentialled by the operator, as designed"))

    # THE AUDIT'S OWN PHANTOM-PATH CHECK is the closest thing the desk has to a filesystem-
    # hygiene fence: paths read by code that nothing writes. It names secrets explicitly as the
    # legitimately-absent class, so what remains is genuine read-without-writer.
    out.append(inverse_ladder_component(
        "phantom_path_defects", _AUDIT, _audit_defects(root, "phantom-"), DEFECT_LADDER,
        unit="read-without-writer path defects live in the audit",
        detail="paths code reads that nothing on this desk writes; operator-provisioned secrets "
               "are excluded by the audit's own allowlist, so these are real wiring faults"))
    return out


_MYPY = "data/mypy_ratchet.json"
_BUILD_STANDARD = "data/build_standard.json"
_WIRING = "data/wiring_agent.json"


def _engineering_standard(root: Path, _now: datetime) -> list[Component]:
    """Does new work enter above the standard, and is what was built actually REACHABLE?

    Two failure directions, both measured by organs that already exist: work entering below the
    build standard (no refusal path, untested, unscheduled, unmapped to a law), and work that
    entered fine and is now unreachable -- engineering already paid for that returns zero forever
    and rots into a liability.
    """
    build = _read_json(root / _BUILD_STANDARD)
    governed = _num(_field(build, "n_governed"))
    failing = _num(_field(build, "n_failing"))
    out = [fraction_component(
        "organs_meeting_build_standard", _BUILD_STANDARD,
        None if governed is None or failing is None else governed - failing, governed,
        unit="governed organs meeting the build standard",
        detail=f"status {_field(build, 'status')}: {failing} failing of {governed} governed; "
               f"unreadable inputs {_field(build, 'unreadable_inputs')}")]

    mypy = _read_json(root / _MYPY)
    out.append(fraction_component(
        "strict_typing_clean_share", _MYPY, _num(_field(mypy, "clean_fraction")), 1.0,
        unit="of scanned files carrying ZERO strict-mode errors",
        detail=f"clean fraction {_field(mypy, 'clean_fraction')} over "
               f"{_len_or_none(_field(mypy, 'per_file'))} files, {_field(mypy, 'total_errors')} "
               f"errors total, measured {_field(mypy, 'generated')}"))

    wiring = _mapping(_read_json(root / _WIRING), "counts")
    proposals = _num((wiring or {}).get("PROPOSE"))
    out.append(inverse_ladder_component(
        "unwired_proposals_open", _WIRING, proposals, DEFECT_LADDER,
        unit="open wiring proposals (built, not reachable)",
        detail=f"counts {wiring} over {_field(_read_json(root / _WIRING), 'n_scripts_scanned')} "
               "scripts scanned -- each proposal is capability already paid for and returning "
               "zero"))
    out.append(inverse_ladder_component(
        "unwired_module_defects", _AUDIT, _audit_defects(root, "unwired-"), DEFECT_LADDER,
        unit="live unwired-module defects in the audit",
        detail="library modules nothing imports, and scripts that are the only importer of a "
               "module nothing invokes -- built, tested and unreachable"))
    return out


_SOURCE_ALTERNATIVES = "data/source_alternatives_report.json"
_SOURCE_HEALTH = "data/source_health.jsonl"


def _source_resilience(root: Path, _now: datetime) -> list[Component]:
    """When a source dies, does the desk already know where else to look?

    A dead source with no registered alternative is a research seam that closes silently. The
    vantage caveat is carried, not dropped: a probe from this container says something about THIS
    egress path, and a candidate failing here may be fine on the box that collects.
    """
    doc = _read_json(root / _SOURCE_ALTERNATIVES)
    if doc is None:
        out = [unmeasured_component(
            "dead_sources_without_alternatives", _SOURCE_ALTERNATIVES,
            f"{_SOURCE_ALTERNATIVES} absent -- nothing tracks whether a dead source has a "
            "registered replacement, so a closing seam is invisible until someone notices the "
            "silence")]
    else:
        out = [inverse_ladder_component(
            "dead_sources_without_alternatives", _SOURCE_ALTERNATIVES,
            _len_or_none(doc.get("dead_without_registered_alternatives")), DEFECT_LADDER,
            unit="dead sources with NO registered alternative",
            detail=f"{_len_or_none(doc.get('dead_sources'))} dead of "
                   f"{_len_or_none(doc.get('registry'))} registered, mode {doc.get('mode')}, "
                   f"vantage {doc.get('vantage')} -- {str(doc.get('vantage_note'))[:80]}")]

    rows = _read_jsonl(root / _SOURCE_HEALTH)
    if not rows:
        out.append(unmeasured_component(
            "sources_healthy", _SOURCE_HEALTH,
            f"{_SOURCE_HEALTH} absent or empty -- no per-source verdict ledger, so 'the "
            "collectors are fine' rests on nobody having complained"))
    else:
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = row.get("source")
            if isinstance(name, str):
                latest[name] = row
        healthy = float(sum(1 for r in latest.values() if r.get("verdict") == "HEALTHY"))
        degraded = sorted(k for k, r in latest.items() if r.get("verdict") != "HEALTHY")
        out.append(fraction_component(
            "sources_healthy", _SOURCE_HEALTH, healthy, float(len(latest)),
            unit="registered sources whose latest verdict is HEALTHY",
            detail=f"{healthy:g}/{len(latest)} healthy on their most recent probe; not healthy: "
                   f"{', '.join(degraded) or 'none'}"))
    return out


_BLINDSPOT = "data/blindspot_max.json"


def _blind_spots(root: Path, _now: datetime) -> list[Component]:
    """Is the desk conditioning on the slices it KNOWS exist, and reading the fields it has?

    A blind spot is not an unknown unknown once it has been enumerated -- it is a known gap being
    left open, which is a different and much cheaper defect to close.
    """
    doc = _read_json(root / _BLINDSPOT)
    slices = _rows(doc, "slices")
    if slices is None or not slices:
        out = [unmeasured_component(
            "slices_conditioned", _BLINDSPOT,
            f"{_BLINDSPOT} carries no slice list -- nothing enumerates the conditioning axes, so "
            "'we condition on regime' is a claim rather than a measurement")]
    else:
        done = float(sum(1 for s in slices if s.get("conditioned") is True))
        out = [fraction_component(
            "slices_conditioned", _BLINDSPOT, done, float(len(slices)),
            unit="enumerated slices the desk actually conditions on",
            detail=f"{done:g}/{len(slices)} slices conditioned "
                   f"({', '.join(str(s.get('slice')) for s in slices)}) at "
                   f"{_field(doc, 'updated')}")]
    out.append(inverse_ladder_component(
        "unread_fields", _BLINDSPOT, _num(_field(doc, "unread_fields")), DEFECT_LADDER,
        unit="collected fields nothing reads",
        detail=f"{_field(doc, 'unread_fields')} unread field(s), "
               f"{_len_or_none(_field(doc, 'unmodelled_entities'))} unmodelled entities, "
               f"{_len_or_none(_field(doc, 'uncrossed_pairs'))} uncrossed pairs -- data bought "
               "and never asked a question of"))
    return out


_CONSTITUTION = "docs/research/CONSTITUTION_RATCHET.json"
_LAW_COVERAGE = "docs/research/LAW_COVERAGE.json"


def _constitutional_aggression(root: Path, _now: datetime) -> list[Component]:
    """How aggressive is the constitution the desk actually operates under, and is it enforced?

    The aggression marks are the sibling ratchet's record (libs/doctrine/ratchet.py) -- already on
    the same 0-10 scale the standing order is stated on, so they are read straight rather than
    re-scored. Institutions drift toward timidity one reasonable amendment at a time, and this is
    the number that makes each one visible.
    """
    doc = _read_json(root / _CONSTITUTION)
    marks = _mapping(doc, "high_water")
    if marks is None or not marks:
        out = [unmeasured_component(
            "principle_aggression", _CONSTITUTION,
            f"{_CONSTITUTION} carries no high-water marks -- the constitution's aggression is "
            "unrecorded, which is the state that lets it be softened without anyone noticing")]
    else:
        graded: list[tuple[float, str]] = []
        for name, raw in marks.items():
            value = _num(raw)
            if value is not None:
                graded.append((value, str(name)))
        if not graded:
            out = [unmeasured_component(
                "principle_aggression", _CONSTITUTION,
                f"{_CONSTITUTION} high_water carries no numeric marks")]
        else:
            mean = sum(v for v, _ in graded) / len(graded)
            weakest_score, weakest_name = min(graded)
            out = [fraction_component(
                "principle_aggression", _CONSTITUTION, round(mean, 3), SCALE_MAX,
                unit="of full aggression, meaned over the constitution's own marks",
                detail=f"mean {mean:.2f}/10 over {len(graded)} principles; weakest "
                       f"{weakest_name} at {weakest_score:g}, updated {_field(doc, 'updated')}")]

    live = _mapping(_read_json(root / _LAW_COVERAGE), "live")
    if live is None:
        out.append(unmeasured_component(
            "law_enforcement_coverage", _LAW_COVERAGE,
            f"{_LAW_COVERAGE} carries no live block -- the share of principles enforced both "
            "mechanically and interactionally is unrecorded"))
    else:
        out.append(fraction_component(
            "law_enforcement_coverage", _LAW_COVERAGE, _num(live.get("full_pct")), 100.0,
            unit="% of principles enforced BOTH mechanically and in every interaction",
            detail=f"{live.get('both')}/{live.get('principles')} principles fully enforced "
                   f"(mechanical {live.get('mechanical_pct')}%, interactional "
                   f"{live.get('interactional_pct')}%); {live.get('unenforced')} unenforced"))
    return out


_RETURN_TARGETING = "data/return_targeting.json"
_TIMIDITY = "data/timidity_audit.json"


def _ambition_discipline(root: Path, _now: datetime) -> list[Component]:
    """Is restraint DECLARED as evidence/risk restraint, or is it timidity wearing prudence?

    L1.28 scores timidity as a defect, and the audit that enforces it makes the distinction
    machine-checkable: every scope restraint must state its non-timid reading, and every
    evidence-or-risk restraint must be declared as such and stay strict. An UNCLASSIFIED restraint
    is the interesting one -- nobody has said which kind it is.
    """
    doc = _read_json(root / _TIMIDITY)
    rows = _rows(doc, "rows")
    unclassified = _len_or_none(_field(doc, "unclassified"))
    if rows is None or unclassified is None:
        out = [unmeasured_component(
            "restraints_classified", _TIMIDITY,
            f"{_TIMIDITY} carries no restraint rows -- nothing separates a declared evidence bar "
            "from an undeclared flinch, and the two look identical in a diff")]
    else:
        out = [fraction_component(
            "restraints_classified", _TIMIDITY, float(len(rows)) - unclassified, float(len(rows)),
            unit="restraints classified as scope, evidence or risk",
            detail=f"{len(rows)} restraint(s), {unclassified:g} unclassified; counts "
                   f"{_field(doc, 'counts')}")]
    out.append(inverse_ladder_component(
        "prompt_timidity_hits", _TIMIDITY, _len_or_none(_field(doc, "prompt_timid_hits")),
        DEFECT_LADDER, unit="timid instructions found in live prompt surfaces",
        detail=f"{_len_or_none(_field(doc, 'prompt_timid_hits'))} hit(s) across "
               f"{_field(doc, 'prompt_surfaces_scanned')} prompt surfaces; doctrine injected="
               f"{_field(doc, 'doctrine_injected')}"))

    ret = _read_json(root / _RETURN_TARGETING)
    scoped = _num(_field(ret, "n_scoped"))
    flagged = _num(_field(ret, "n_flagged"))
    out.append(fraction_component(
        "surfaces_free_of_return_targets", _RETURN_TARGETING,
        None if scoped is None or flagged is None else scoped - flagged, scoped,
        unit="governed surfaces with no return NUMBER bound to goal language",
        detail=f"status {_field(ret, 'status')}: {_field(ret, 'detail')}; unreadable "
               f"{_field(ret, 'unreadable')}"))
    return out


#: THE ASPECT LIST. Fixed, ordered, and it may only ever GROW -- an aspect removed is a capability
#: the desk stopped being graded on, which is the deletion loophole one level up from a component.
#: `ceiling` states what 10/10 would MEAN, because a score with no stated ceiling drifts into
#: meaning "as good as we currently know how to be".
#: EVERY BUILDER TAKES THE CLOCK, including the ones that do not use it (they name it `_now`).
#: THAT IS DELIBERATE. Reading a state artifact without checking its age is a fail-open in the
#: FLATTERING direction -- a stale monitor reads exactly like a healthy one, and the longer it
#: stays dead the more confident the number looks. Threading `now` in unconditionally means the
#: clock is always in reach, so age-checking is a decision each builder makes rather than a
#: capability it lacks; and taking it as an argument rather than calling datetime.now() inside
#: keeps every builder testable against a fixed instant.
ASPECTS: tuple[tuple[str, str, Callable[[Path, datetime], list[Component]]], ...] = (
    ("statistical_validation",
     "the validation stack's own tests kill every mutant of it, over complete (never truncated) "
     "runs -- the desk cannot fool itself about whether an edge is real",
     _statistical_validation),
    ("research_discipline",
     "a large, growing suite; a graveyard that keeps filling because ideas get CLOSED; and every "
     "distinct family hunted rather than one family hunted many ways",
     _research_discipline),
    ("risk_rails",
     "every rail mutation-proof and the ruin rail measurably clear from the box that owns the "
     "state -- no rail whose status is unknown",
     _risk_rails),
    ("governance",
     "every law fence green and ZERO live audit defects -- the laws are enforced by machinery "
     "rather than by attention",
     _governance),
    ("data_coverage",
     "every registered asset carrying a measured span and every unknown-unknown organ fresh -- "
     "no dark corner of the desk's own data",
     _data_coverage),
    ("execution_path",
     "Gate 0 fully ready, the money path covered like the money path, and libs/execution "
     "mutation-proof",
     _execution_path),
    ("self_improvement",
     "every ledger row reaching a terminal verdict and 7-day conversion keeping pace with 7-day "
     "arrivals -- found equals fixed",
     _self_improvement),
    ("ops_autonomy",
     "every scheduled organ producing fresh output unattended and every organ assembling a "
     "lawful prompt",
     _ops_autonomy),
    ("alpha_output",
     "the forward cohort full of live clocks and the promotion ladder climbed on closed-trade "
     "evidence -- the aspect every other one exists to serve",
     _alpha_output),
    # THE MINOR ASPECTS, which is to say the ones that actually take desks down. Everything below
    # is measured from an artifact another organ already writes; none of it was worth a headline
    # until it failed, and the standing order says EVERY aspect, not the interesting ones.
    ("alerting_pager",
     "the pager provably delivers between incidents, on more than one channel, with the canary "
     "auditing the ledger rather than the code",
     _alerting),
    ("cost_model_fidelity",
     "the cost model refreshed on its own cadence over the whole universe, with every declared "
     "input readable so the realised-versus-modelled residual is a measurement",
     _cost_model),
    ("forward_clock_hygiene",
     "promotion latency MEASURED end to end rather than designed, births countable from a dated "
     "history, and replacement keeping pace with death",
     _forward_clock),
    ("recorder_tape",
     "the desk's own tape recording continuously, every stream declaring the clock that stamped "
     "it, replicated off the host, with retention clearing the analysis window",
     _recorder_tape),
    ("llm_seat_coverage",
     "every research seat wired, credentialled AND observably producing -- three facts, none of "
     "them allowed to stand in for the others",
     _llm_seats),
    ("dependency_environment",
     "the environment that runs the tests is the environment that runs the money: no major drift "
     "from the deployed pins, no declared dependency missing",
     _dependency_env),
    ("knowledge_currency",
     "everything the desk has learned is retrievable BEFORE compute is spent -- a graveyard that "
     "is a memory rather than a document",
     _knowledge_currency),
    ("backup_dr",
     "every durable store replicated off the host and a restore actually EXERCISED, with disk "
     "headroom clear of the backup organ's own fuse",
     _backup_dr),
    ("mutation_breadth",
     "every money-path file carrying a COMPLETE mutation run -- breadth, so a perfect kill rate "
     "on one small file can never stand in for a tested tree",
     _mutation_breadth),
    ("scheduler_integrity",
     "every scheduled line pointing at a script that exists, parses and locks coherently, AND the "
     "live crontab provably matching the manifest",
     _scheduler_integrity),
    ("secret_permission_hygiene",
     "the desk can write every artifact it must write and read every credential it was given, "
     "with no path read by code that nothing writes",
     _secret_permission),
    ("engineering_standard",
     "nothing enters below the build standard, the tree is strict-clean, and nothing built is "
     "left unreachable",
     _engineering_standard),
    ("capital_utilisation",
     "every paid-for ceiling measured and saturated -- unused headroom is not safety, it is an "
     "unbooked loss",
     _capital_utilisation),
    ("source_resilience",
     "every registered source healthy on its latest probe, and every dead one already carrying a "
     "registered alternative",
     _source_resilience),
    ("blind_spot_coverage",
     "every enumerated slice conditioned on and every collected field read -- an enumerated blind "
     "spot left open is the cheapest defect on the board",
     _blind_spots),
    ("constitutional_aggression",
     "the constitution held at full aggression and every principle enforced BOTH mechanically and "
     "in every interaction",
     _constitutional_aggression),
    ("ambition_discipline",
     "every restraint declared as scope, evidence or risk; no timid instruction in a live prompt; "
     "no return NUMBER bound to goal language",
     _ambition_discipline),
)

ASPECT_KEYS: tuple[str, ...] = tuple(k for k, _, _ in ASPECTS)


def score_aspect(key: str, ceiling: str, components: list[Component]) -> Aspect:
    """Mean over MEASURED components only; UNMEASURED ones are carried, never averaged in.

    Averaging an unmeasured component as 0 would punish the desk for not knowing, and as 10 would
    reward it -- so the mean's denominator is what was actually measured, and the count of what
    was not is published beside it so nobody reads a 2-of-5 mean as a whole-aspect verdict.
    """
    scored = [c.score for c in components if c.state == MEASURED and c.score is not None]
    if not scored:
        whys = "; ".join(c.detail for c in components) or "no component produced a reading"
        return Aspect(key=key, ceiling=ceiling, state=UNMEASURED, score=None,
                      components=tuple(components),
                      binding_constraint=f"UNMEASURED -- {whys}")
    score = _round(sum(scored) / len(scored))
    weakest = min((c for c in components if c.state == MEASURED and c.score is not None),
                  key=lambda c: (c.score if c.score is not None else 0.0))
    unmeasured = [c for c in components if c.state == UNMEASURED]
    constraint = f"{weakest.key} at {weakest.score:.1f} -- {weakest.constraint}"
    if unmeasured:
        constraint += (f" [+{len(unmeasured)} UNMEASURED component(s): "
                       f"{', '.join(c.key for c in unmeasured)} -- the score above covers only "
                       f"{len(scored)} of {len(components)} components]")
    return Aspect(key=key, ceiling=ceiling, state=MEASURED, score=score,
                  components=tuple(components), binding_constraint=constraint)


def read_capability(root: Path, now: datetime | None = None) -> tuple[Aspect, ...]:
    """Score every aspect from the artifacts on disk. Pure read -- nothing here measures.

    `now` is the instant every staleness judgement is made against, threaded in rather than read
    from the system clock inside a builder: a component that calls datetime.now() itself cannot be
    tested against a fixed instant, and an age check nobody can test is an age check nobody should
    trust. Defaulting it here keeps the read-only callers (dashboards, the CRO dossier) working
    unchanged.
    """
    at = now if now is not None else datetime.now(tz=UTC)
    return tuple(score_aspect(key, ceiling, build(root, at)) for key, ceiling, build in ASPECTS)


def desk_binding_constraint(aspects: tuple[Aspect, ...]) -> dict[str, Any]:
    """THE ONE LINE A WEEKLY SWEEP ACTS ON FIRST: the lowest-scoring component on the whole desk.

    Per-aspect constraints are a queue of thirty-odd items, which is a queue nobody works. This
    picks the single desk-wide minimum and names the artifact, the reading and the specific next
    thing that raises it.

    IT IS THE MINIMUM OVER MEASURED COMPONENTS ONLY, and the count of unmeasured ones is published
    beside it rather than folded in. An unmeasured component has no score to be the minimum OF --
    treating it as a zero would make "the thing nobody measures" permanently the top priority,
    which sounds rigorous and is actually how a board full of absent measurements out-shouts a
    real defect. Unmeasured work has its own list, and its own instruction: measure it.

    The tie-break is (score, aspect key, component key) -- deterministic, so the same desk state
    always produces the same instruction and a reader can tell a real change of priority from
    dictionary ordering.
    """
    scored = [(a, c, c.score) for a in aspects for c in a.components
              if c.state == MEASURED and c.score is not None]
    unmeasured = [(a, c) for a in aspects for c in a.components if c.state == UNMEASURED]
    if not scored:
        return {
            "state": UNMEASURED,
            "aspect": None, "component": None, "score": None, "artifact": None,
            "n_unmeasured_components": len(unmeasured),
            "constraint": ("NOTHING IS MEASURED. There is no desk-wide minimum because there is "
                           "no reading -- the binding constraint is the measurement itself. Start "
                           "with the unmeasured_components list; every row names the artifact that "
                           "would settle it."),
        }
    worst_aspect, worst, score = min(scored, key=lambda t: (t[2] or 0.0, t[0].key, t[1].key))
    return {
        "state": MEASURED,
        "aspect": worst_aspect.key,
        "component": worst.key,
        "score": score,
        "artifact": worst.artifact,
        "n_unmeasured_components": len(unmeasured),
        "detail": worst.detail,
        "constraint": worst.constraint,
        "_": (f"LOWEST-SCORING COMPONENT DESK-WIDE: {worst_aspect.key}.{worst.key} at "
              f"{score:.1f}/10 out of {worst.artifact}. This is the line to work first. "
              f"{len(unmeasured)} component(s) are UNMEASURED and are NOT eligible to be this "
              "minimum -- an absent measurement has no score, and letting it win here would bury "
              "every real defect under things nobody has looked at yet."),
    }


# --------------------------------------------------------------------------------------------
# THE RATCHET ITSELF.
# --------------------------------------------------------------------------------------------


def load_marks(path: Path) -> Marks:
    """Read the high-water record. A missing file means NO HISTORY, not a clean slate at zero.

    Same reasoning as libs/doctrine/ratchet.load_baseline: with no recorded history there is
    nothing to have regressed FROM, and the first run writes today's reading as the mark. A
    DELETED record is a different fact and is caught where it belongs -- the artifact's own
    `first_recorded` stamp resetting is visible in the diff and in the printed table.
    """
    doc = _read_json(path)
    if doc is None:
        return Marks({}, {}, "", "", 0)
    aspect_raw = doc.get("high_water")
    comp_raw = doc.get("component_high_water")

    def _floats(raw: object) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            n = _num(v)
            if n is not None:
                out[str(k)] = n
        return out

    return Marks(
        aspect_high_water=_floats(aspect_raw),
        component_high_water=_floats(comp_raw),
        last_raise_at=str(doc.get("last_raise_at") or ""),
        first_recorded=str(doc.get("first_recorded") or ""),
        n_raises=int(_num(doc.get("n_raises")) or 0),
    )


def _component_marks(aspect: Aspect, marks: Marks) -> dict[str, float]:
    prefix = f"{aspect.key}."
    return {k: v for k, v in marks.component_high_water.items() if k.startswith(prefix)}


def attainable(aspect: Aspect, marks: Marks) -> float | None:
    """What this aspect would score if EVERY component it grades today stood at its own best.

    A component's best is its recorded mark, or today's reading when it has no mark yet -- a
    component measured for the first time has no history, so today IS its best-so-far. Taking the
    MAX of the two is what keeps the number safe: a component that regressed still contributes its
    old mark here, so a regression can never make an aspect look merely "wider".

    None when the aspect grades nothing measurable -- there is then nothing to compare with.
    """
    prior = _component_marks(aspect, marks)
    bests: list[float] = []
    for c in aspect.components:
        if c.state != MEASURED or c.score is None:
            continue
        bests.append(max(prior.get(f"{aspect.key}.{c.key}", c.score), c.score))
    if not bests:
        return None
    return _round(sum(bests) / len(bests))


def _widening(aspect: Aspect, marks: Marks) -> tuple[bool, list[str], str]:
    """Is the aspect's mark still COMPARABLE to today's reading, or was it earned over less?

    THE TEST IS ATTAINABILITY, and it is deliberately stateless -- derived from the marks
    themselves rather than from a remembered component list. If the aspect's mark is higher than
    the mean of the CURRENT components' own best-ever scores, then no arrangement of today's
    components could ever have produced that mark: it was earned over a different, narrower set.
    Comparing today's mean against it is therefore not a comparison at all, and reporting the gap
    as a regression asserts something the record cannot support.

    WHY NOT REMEMBER THE SET INSTEAD. A remembered basis has to be reconstructed for every record
    written before it existed, and the reconstruction is a guess. This needs no history, no
    migration, and it SELF-CORRECTS: the moment the aspect beats its old mark over the wider set,
    the mark rises, attainability catches up, and the aspect is comparable again forever after.

    IT CANNOT LAUNDER A REGRESSION. Every component mark is a high-water mark, so a component that
    dropped still sits at its old best in `prior` and does not lower attainability -- it produces a
    NAMED CAUSE in _fall_causes and the aspect is FELL before this is consulted. Deleting a strong
    component is a WENT-DARK cause for the same reason. The only way to reach this branch is for
    the current component set to be genuinely incapable of the recorded mark, which is exactly what
    "the mark was measured over less" means.
    """
    mark = marks.aspect_high_water.get(aspect.key)
    reach = attainable(aspect, marks)
    if mark is None or reach is None or reach >= mark - EPS:
        return False, [], ""
    prior = _component_marks(aspect, marks)
    added = sorted(c.key for c in aspect.components
                   if c.state == MEASURED and f"{aspect.key}.{c.key}" not in prior)
    return True, added, (
        f"with every component of today's set at its OWN best the aspect would reach {reach:.1f}, "
        f"below the recorded {mark:.1f} -- so that mark cannot have been earned over this set")


def _fall_causes(aspect: Aspect, marks: Marks) -> list[str]:
    """Localise a fall to the component(s) that caused it. A fall with no named cause is itself
    reportable -- see the caller."""
    prior = _component_marks(aspect, marks)
    now = {f"{aspect.key}.{c.key}": c for c in aspect.components}
    causes: list[str] = []
    for full, mark in sorted(prior.items()):
        cur = now.get(full)
        if cur is None:
            causes.append(
                f"{full} WENT DARK (stood at {mark:.1f}) -- a measurement that disappears is "
                "scored as the capability it evidenced disappearing, never as neutral")
        elif cur.state == UNMEASURED:
            causes.append(
                f"{full} became UNMEASURED (stood at {mark:.1f}): {cur.detail}")
        elif cur.score is not None and cur.score < mark - EPS:
            causes.append(
                f"{full} {mark:.1f} -> {cur.score:.1f} ({cur.artifact}): {cur.detail}")
    return causes


def ratchet(aspects: tuple[Aspect, ...], marks: Marks,
            now: datetime) -> tuple[Marks, list[Verdict], str]:
    """Compare today's reading against the record, then RAISE the record. Never lowers anything.

    The asymmetry is the entire design, copied from the aggression ratchet: improving is
    frictionless, and giving ground is impossible through this path -- it produces a defect with a
    named cause instead, which is a thing somebody has to answer for.
    """
    verdicts: list[Verdict] = []
    aspect_hw = dict(marks.aspect_high_water)
    comp_hw = dict(marks.component_high_water)
    raised_any = False

    for a in aspects:
        mark = marks.aspect_high_water.get(a.key)
        causes = _fall_causes(a, marks)

        if a.state == UNMEASURED:
            if mark is not None:
                movement, cause = WENT_DARK, (
                    "; ".join(causes) or
                    f"the whole aspect stopped measuring while its record stood at {mark:.1f}: "
                    f"{a.binding_constraint}")
            else:
                movement, cause = UNMEASURED, a.binding_constraint
            verdicts.append(Verdict(a.key, movement, None, mark, cause))
            continue

        score = a.score if a.score is not None else 0.0
        fell_aspect = mark is not None and score < mark - EPS
        widened, added, why_basis = _widening(a, marks)
        if causes:
            movement, cause = FELL, "; ".join(causes)
        elif fell_aspect and mark is not None and widened:
            # THE DESK IS GRADING ITSELF ON MORE, and nothing that was already graded got worse.
            # Every prior component still holds its own mark (or this branch would be unreachable
            # -- `causes` is built from exactly that comparison), so the drop is arithmetic from a
            # wider denominator, not a capability going backwards. The old mark is KEPT and printed
            # beside today's reading, because the honest statement is "9.0 was measured over less".
            # THIS PERSISTS until the aspect beats its mark over the WIDER set, which is the point:
            # a one-run amnesty would leave an unexplained fall reported every day forever after,
            # and a gate that is permanently red is a gate that is permanently ignored.
            movement = WIDENED
            first_seen = f" First graded this run: {', '.join(added)}." if added else ""
            cause = (f"aspect mean {mark:.1f} -> {score:.1f} while grading "
                     f"{len(a.components)} component(s) -- {why_basis}. NO component that already "
                     f"had a mark is below it, so nothing got worse: the mark was earned over a "
                     f"NARROWER set and is not comparable to today's reading. It STAYS at "
                     f"{mark:.1f}; beating it OVER THE WIDER SET is the work.{first_seen} Next: "
                     f"{a.binding_constraint}")
        elif fell_aspect and mark is not None:
            # A fall the component marks cannot explain, over EXACTLY the set the mark was earned
            # over. It is a fall and it needs a cause -- saying so is the check refusing to accept
            # an unexplained regression rather than quietly logging one.
            movement = FELL
            cause = (f"aspect mean {mark:.1f} -> {score:.1f} over the SAME component set the mark "
                     "was earned on, with no component below its own mark. NAME the cause in the "
                     "diff; an unexplained fall is never accepted.")
        elif mark is None:
            movement, cause = NEW, f"first reading recorded at {score:.1f}: {a.binding_constraint}"
            raised_any = True
        elif score > mark + EPS:
            movement = RAISED
            cause = f"{mark:.1f} -> {score:.1f}. Next: {a.binding_constraint}"
            raised_any = True
        elif score >= SCALE_MAX - EPS:
            movement = AT_CEILING
            cause = f"10/10 held. {a.binding_constraint}"
        else:
            movement = FLATLINE
            cause = a.binding_constraint

        verdicts.append(Verdict(a.key, movement, score, mark, cause))
        aspect_hw[a.key] = max(mark if mark is not None else score, score)
        for c in a.components:
            if c.state == MEASURED and c.score is not None:
                full = f"{a.key}.{c.key}"
                comp_hw[full] = max(comp_hw.get(full, c.score), c.score)

    status = _status(verdicts, marks, now, raised_any)
    new = Marks(
        aspect_high_water=dict(sorted(aspect_hw.items())),
        component_high_water=dict(sorted(comp_hw.items())),
        last_raise_at=now.isoformat() if raised_any else marks.last_raise_at,
        first_recorded=marks.first_recorded or now.isoformat(),
        n_raises=marks.n_raises + (1 if raised_any else 0),
    )
    return new, verdicts, status


def _status(verdicts: list[Verdict], marks: Marks, now: datetime, raised_any: bool) -> str:
    """REGRESSED > STALLED > RAISED > WIDENED > FLATLINE. A fall outranks everything: it is the one
    state the ratchet exists to make impossible to reach quietly.

    WIDENED sits BELOW stalled deliberately. Grading yourself on more is good, but it is not a
    RAISE and must never reset the stall clock -- otherwise "add another component" would be the
    cheap way to look busy for another seven days without any capability moving.
    """
    if any(v.movement in (FELL, WENT_DARK) for v in verdicts):
        return "REGRESSED"
    if raised_any:
        return "RAISED"
    last = _parse_ts(marks.last_raise_at)
    if last is not None and now - last > timedelta(days=STALL_DAYS):
        return "STALLED"
    if any(v.movement == WIDENED for v in verdicts):
        return WIDENED
    return "FLATLINE"


def days_since_raise(marks: Marks, now: datetime) -> float | None:
    last = _parse_ts(marks.last_raise_at)
    if last is None:
        return None
    return round((now - last).total_seconds() / 86400.0, 2)


def build_artifact(aspects: tuple[Aspect, ...], marks: Marks, verdicts: list[Verdict],
                   status: str, now: datetime) -> dict[str, Any]:
    """The on-disk record: the marks, the current reading, and every movement with its cause."""
    by_key = {v.aspect: v for v in verdicts}
    measured = [a for a in aspects if a.state == MEASURED and a.score is not None]
    unmeasured_components = [
        {"aspect": a.key, "component": c.key, "artifact": c.artifact, "why": c.detail}
        for a in aspects for c in a.unmeasured]
    return {
        "_": ("HIGH-WATER MARKS for desk CAPABILITY, one score per named aspect on the 0-10 scale "
              "the principal's standing order is stated on. Raised automatically; NEVER lowered "
              "by code. A FALL is a defect reported with a NAMED CAUSE, a FLATLINE is reported "
              "with the binding constraint that is holding the aspect down, and UNMEASURED is its "
              "own state -- never silently a 0 and never silently a 10."),
        "law": ("R0104 -- every aspect is pushed toward 10/10 every day, non-exhaustively. A "
                "rating nobody records cannot ratchet, and a score that can silently fall is not "
                "a standard."),
        "generated": now.isoformat(),
        "status": status,
        "scale_max": SCALE_MAX,
        "stall_days": STALL_DAYS,
        "n_aspects": len(aspects),
        "n_measured": len(measured),
        "n_unmeasured": len(aspects) - len(measured),
        # The mean over MEASURED aspects only, and it is NOT a desk score: it is published so a
        # fall in the aggregate is visible, next to the count of what it could not see.
        "measured_mean": (round(sum(a.score or 0.0 for a in measured) / len(measured), 2)
                          if measured else None),
        "first_recorded": marks.first_recorded,
        "last_raise_at": marks.last_raise_at,
        "days_since_raise": days_since_raise(marks, now),
        "n_raises": marks.n_raises,
        # THE WEEKLY SWEEP'S FIRST LINE. Everything else on this page is a list; this is an
        # instruction.
        "binding_constraint": desk_binding_constraint(aspects),
        "high_water": marks.aspect_high_water,
        "component_high_water": marks.component_high_water,
        "aspects": [
            {
                "key": a.key,
                "state": a.state,
                "score": a.score,
                "high_water": marks.aspect_high_water.get(a.key),
                "movement": by_key[a.key].movement,
                "cause": by_key[a.key].cause,
                "binding_constraint": a.binding_constraint,
                "ceiling": a.ceiling,
                "artifacts": list(a.artifacts),
                "components": [
                    {"key": c.key, "state": c.state, "score": c.score, "artifact": c.artifact,
                     "detail": c.detail, "constraint": c.constraint}
                    for c in a.components],
            }
            for a in aspects],
        "defects": [{"aspect": v.aspect, "movement": v.movement, "score": v.score,
                     "high_water": v.high_water, "cause": v.cause}
                    for v in verdicts if v.movement in (FELL, WENT_DARK)],
        "flatlined": [{"aspect": v.aspect, "score": v.score, "binding_constraint": v.cause}
                      for v in verdicts if v.movement in (FLATLINE, AT_CEILING)],
        "raised": [{"aspect": v.aspect, "score": v.score, "detail": v.cause}
                   for v in verdicts if v.movement in (RAISED, NEW)],
        # NOT a defect list. An aspect whose mean fell purely because it now grades MORE, with
        # nothing that was already graded getting worse. The old mark is kept beside it.
        "widened": [{"aspect": v.aspect, "score": v.score, "high_water": v.high_water,
                     "detail": v.cause}
                    for v in verdicts if v.movement == WIDENED],
        "unmeasured": [{"aspect": v.aspect, "why": v.cause}
                       for v in verdicts if v.movement == UNMEASURED],
        "unmeasured_components": unmeasured_components,
    }
