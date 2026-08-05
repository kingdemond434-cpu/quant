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

WHAT IT CANNOT DO, stated plainly because a control that overstates itself is worse than none. The
map from artifact to 0-10 is a JUDGEMENT -- the ladders and fractions below are written down so
they can be argued with, but they are not discovered facts, and a component scoring 8 does not
mean the desk is 80% of the way to excellent at it. What the artifact does claim is narrower and
worth having: the score cannot fall without a named cause, the aspect list cannot quietly shrink,
an unmeasured aspect cannot read as a healthy one, and every reading carries the specific next
thing that would raise it.
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
    "FELL",
    "FLATLINE",
    "MEASURED",
    "NEW",
    "RAISED",
    "SCALE_MAX",
    "STALL_DAYS",
    "UNMEASURED",
    "WENT_DARK",
    "Aspect",
    "Component",
    "Marks",
    "Verdict",
    "build_artifact",
    "load_marks",
    "ratchet",
    "read_capability",
    "score_aspect",
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

#: Float comparison slack. Scores are rounded to 0.1 so that FLATLINE means something -- with raw
#: floats every reading differs in the twelfth decimal and "no movement" could never be reported.
EPS = 1e-9

#: Days with no aspect setting a new best before the ratchet itself reports a defect. The order is
#: DAILY, so a week of nothing is the order not being followed, not a quiet patch. Deliberately not
#: 1 day: nine aspects cannot each move every day, and a gate that fires every morning gets
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


def _statistical_validation(root: Path) -> list[Component]:
    return mutation_components(root, "mutation_kill_validation_stack",
                               ("libs/validation/", "libs/autodiscovery/"))


_SUITE = "docs/research/test_suite_record.json"
_GRAVEYARD = "docs/graveyard.md"
_BREADTH = "data/strategy_coverage.json"

#: A graveyard heading is an ENTRY (a killed hypothesis or a retired capability) rather than a
#: section banner when it names a thing: a backticked path or a snake_case identifier. Counting
#: every heading would score the three banners as kills; hardcoding the banner titles would rot the
#: first time somebody adds a section.
_GRAVE_HEADING = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$", re.MULTILINE)
_GRAVE_ENTRY = re.compile(r"`|[a-z0-9]+_[a-z0-9_]+")


def graveyard_kills(text: str) -> int:
    return sum(1 for m in _GRAVE_HEADING.finditer(text)
               if _GRAVE_ENTRY.search(m.group("title")) is not None)


def _research_discipline(root: Path) -> list[Component]:
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
    return out


_GATE0 = "data/gate0_readiness.json"


def _gate0_rows(root: Path) -> list[dict[str, Any]]:
    doc = _read_json(root / _GATE0)
    raw = doc.get("rows") if doc is not None else None
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _risk_rails(root: Path) -> list[Component]:
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
    return out


_LAW_GATE = "data/law_gate.json"
_AUDIT = "data/max_audit_report.json"


def _governance(root: Path) -> list[Component]:
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
    return out


_ASSETS = "data/data_assets.json"
_EXPLORATION = "data/exploration_status.json"


def _data_coverage(root: Path) -> list[Component]:
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
    return out


_COVERAGE = "docs/research/COVERAGE_RATCHET.json"


def _execution_path(root: Path) -> list[Component]:
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
    return out


_LEDGER = "docs/research/recommendation_ledger.json"
_CONVERSION = "data/conversion_status.json"

#: Terminal ledger statuses, read from scripts/check_conversion.py so the two organs cannot drift
#: into disagreeing about what "converted" means on the same file.
TERMINAL_STATUSES = frozenset({"implemented", "rejected", "retired", "done", "screened"})


def _self_improvement(root: Path) -> list[Component]:
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
    return out


_LIVENESS = "data/organ_liveness.json"
_READINESS = "data/organ_readiness.json"


def _ops_autonomy(root: Path) -> list[Component]:
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
    return out


_QUEUE = "data/promotion_queue.json"
_PROMOTION = "data/promotion_gate.json"


def _alpha_output(root: Path) -> list[Component]:
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


#: THE ASPECT LIST. Fixed, ordered, and it may only ever GROW -- an aspect removed is a capability
#: the desk stopped being graded on, which is the deletion loophole one level up from a component.
#: `ceiling` states what 10/10 would MEAN, because a score with no stated ceiling drifts into
#: meaning "as good as we currently know how to be".
ASPECTS: tuple[tuple[str, str, Callable[[Path], list[Component]]], ...] = (
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
     "evidence -- the aspect the other eight exist to serve",
     _alpha_output),
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


def read_capability(root: Path) -> tuple[Aspect, ...]:
    """Score every aspect from the artifacts on disk. Pure read -- nothing here measures."""
    return tuple(score_aspect(key, ceiling, build(root)) for key, ceiling, build in ASPECTS)


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
        if fell_aspect or causes:
            cause = "; ".join(causes)
            if not cause:
                # A fall the component marks cannot explain means the COMPONENT SET changed. It is
                # still a fall and it still needs a cause -- saying so is the check refusing to
                # accept an unexplained regression rather than quietly logging one.
                cause = (f"aspect mean {mark:.1f} -> {score:.1f} with no component below its own "
                         "mark -- the component SET changed. NAME the cause in the diff; an "
                         "unexplained fall is never accepted.")
            movement = FELL
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
    """REGRESSED > STALLED > RAISED > FLATLINE. A fall outranks everything: it is the one state
    the ratchet exists to make impossible to reach quietly."""
    if any(v.movement in (FELL, WENT_DARK) for v in verdicts):
        return "REGRESSED"
    if raised_any:
        return "RAISED"
    last = _parse_ts(marks.last_raise_at)
    if last is not None and now - last > timedelta(days=STALL_DAYS):
        return "STALLED"
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
        "unmeasured": [{"aspect": v.aspect, "why": v.cause}
                       for v in verdicts if v.movement == UNMEASURED],
        "unmeasured_components": unmeasured_components,
    }
