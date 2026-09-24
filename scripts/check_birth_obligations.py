#!/usr/bin/env python3
"""EVERY OBLIGATION IS INHERITED, NOT REMEMBERED (LAWS 7, principal's order 2026-09-23).

    python scripts/check_birth_obligations.py [--json] [--with-fences] [--update]

THE DEFECT CLASS. The desk keeps acquiring obligations -- an executable needs a clock, a source
needs a position in the collection chain, a family needs to be inside the judge's coverage, a
region arrives at the current depth and breadth floors, a destructive path must be guarded
against acting on an absence -- and every one of them was, until now, satisfied by a SESSION
REMEMBERING IT. A thing created next month inherits nothing from a habit: the session that
creates it has never read the cycle where the obligation was learned. `scripts/learn.py` keeps
the lesson reachable; only a fence makes it INHERITED.

THE SHAPE, GENERALISED FROM THE ONE THE DESK ALREADY GOT RIGHT. `check_component_registry.py`
fails when a new executable arrives without a clock: it derives the SET of objects from the tree,
derives the SET that satisfies the obligation, and ratchets the difference. This runs that same
shape on five axes at once, so there is ONE place that answers "did anything arrive incomplete"
rather than five more checkers -- and where another fence already owns an axis, `--with-fences`
CALLS it instead of reimplementing its judgement.

WHY NAMES AND NOT COUNTS. A count that may only fall tells you something regressed; it does not
tell you what. The floor here stores the NAMES of the objects known to be incomplete, so the
failure can say *this* executable, *this* source, *this* region arrived without its obligation --
and an object that later acquires its obligation drops out of the floor automatically, which is
the ratchet falling without a human editing a number.

PRE-EXISTING DEBT IS THE FLOOR, NOT A FAILURE. A fence that is red on the day it is built gets
switched off (L1.43). Today's incomplete set is recorded as the baseline; only an ARRIVAL fails.
Each axis publishes its debt so the number is visible and can be driven down on purpose.

UNMEASURED IS AN AXIS VERDICT (L1.28a). An axis whose declaring artifact is absent reads
UNMEASURED and says so; it never reads as zero incomplete, and it never reads as a pass.

Artifact: `docs/research/birth_obligations.json` (the floors, committed).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
UNMEASURED = "UNMEASURED"
FLOORS = ROOT / "docs" / "research" / "birth_obligations.json"


def _name_safe_stdout() -> None:
    """THIS FENCE MUST BE ABLE TO NAME A CHINESE SOURCE (measured on the trading box 2026-09-23).

    WHY NAMES AND NOT COUNTS is this fence's own design rule (see the module docstring), and on
    Windows it could not honour it. The law gate spawns every fence with a PIPE for stdout, so
    the child's encoding is the locale's -- `cp1252` on the trading box, not utf-8. The DEEP-FOREST
    mandate (principal 2026-09-04) makes this desk mine the Chinese, Japanese, Korean and Russian
    webs by standing order, so the `source` axis is GUARANTEED to hold names outside cp1252. The
    first one it reached, U+548C in a source name, raised UnicodeEncodeError inside `print` at the
    `FAILED` loop -- which killed the process BEFORE the remaining failures printed and before the
    fence returned its own exit code. The 2 the law gate recorded was the traceback's, not the
    fence's verdict: the gate could not tell "93 executables arrived incomplete" from "this fence
    crashed", which is exactly the false reading L1.49 forbids.

    `backslashreplace` is chosen over `replace` deliberately: it never loses information -- the
    exact codepoint stays recoverable from the output -- so a name the console cannot render is
    still a name the next session can look up, not a row of question marks. Nothing here changes
    WHAT is judged; it changes only whether the verdict can be uttered. Best-effort by
    construction: a stream that cannot be reconfigured leaves the fence exactly as it was.
    """
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if enc in {"utf8", "utf8mb4"}:
            continue
        # not a reconfigurable stream -- judge anyway, never refuse to speak
        with contextlib.suppress(AttributeError, OSError, ValueError):
            stream.reconfigure(errors="backslashreplace")   # type: ignore[union-attr]

#: At most this many names per axis in the committed floor. The file must hold the WHOLE
#: incomplete set or the names it dropped would read as arrivals on the next pass, so the bound is
#: generous; when it does bite, the axis says so and stops judging arrivals rather than inventing
#: them -- a truncated floor is UNMEASURED, never a pass and never a false alarm (L1.28a).
MAX_NAMES = 20_000

#: Where an executable of this desk lives. Outside these areas a .py file is not ours to clock.
EXEC_AREAS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts", "desks/mt5/ops",
                               "desks/mt5/moat", "scripts")

#: The files that DECLARE a clock. A stem named in any of them has one.
CLOCK_DECLARATIONS: tuple[str, ...] = (
    "desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py",
    "desks/mt5/ops/box_tasks.manifest", "desks/mt5/research/department_resident.py",
    "desks/mt5/research/moat_swarms.py", "scripts/run_law_gate.py",
)

#: A call that removes, overwrites or retires something.
DESTRUCTIVE = re.compile(r"\b(?:shutil\.rmtree|os\.remove|os\.unlink|\.unlink\(|_retire|"
                         r"retire_\w+|DELETE\s+FROM)\b")

#: A guard that proves the destructive path looked before it acted. `UNMEASURED` counts because
#: recording "I could not see it" IS the guard this desk asks for (L1.28a).
#: NO TRAILING \b: `exists()` is followed by `:` or `)`, both non-word, so a closing boundary
#: never matches and every guarded path would read as unguarded. Measured 2026-09-23.
ABSENCE_GUARD = re.compile(r"\b(?:exists\(\)|is_file\(\)|is_dir\(\)|missing_ok|FileNotFoundError|"
                           r"UNMEASURED|no_retirement_on_absence)")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ the five axes, derived
def _executables(root: Path) -> tuple[set[str], set[str], str]:
    """An executable must have a clock AND a row in the runtime attestation.

    The artifact and named-consumer halves of the same obligation are owned by
    `check_component_registry.py`, which `--with-fences` calls: this axis does not re-judge them.
    """
    objects: set[str] = set()
    for area in EXEC_AREAS:
        d = root / area
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts or p.name.startswith("_"):
                continue
            if "__main__" in _read(p):
                objects.add(p.relative_to(root).as_posix())
    if not objects:
        return set(), set(), f"{UNMEASURED}: no executable areas in this tree"
    clocks = "\n".join(_read(root / c) for c in CLOCK_DECLARATIONS)
    attested = _read(root / "docs" / "research" / "runtime_state.json")
    if not attested.strip():
        return objects, set(), (f"{UNMEASURED}: docs/research/runtime_state.json is absent, so "
                                f"no executable can be shown to have a row in it")
    registry_clocked = _registry_clocked(root)
    ok = {rel for rel in objects
          if (Path(rel).stem in clocks or rel in clocks or rel in registry_clocked)
          and (Path(rel).stem in attested or f'"{rel}"' in attested)}
    return objects, ok, f"{len(ok)}/{len(objects)} executables carry a clock and an attested row"


def _registry_clocked(root: Path) -> set[str]:
    """Every file the component registry puts on a clock -- the fence that OWNS this half.

    WHY NOT ONLY THE GREP ABOVE (2026-09-29). CLOCK_DECLARATIONS is six files; the registry reads
    every clock the desk has -- the two standing batteries, the VPS crontab and systemd units, the
    law gate, the git hooks, and the organs a clocked organ imports or invokes. So an organ rostered
    on a battery, or a launcher its supervisor runs, read "no clock" here while
    `check_component_registry.py` (this axis's own fence) counted it clocked: 14 of the 43
    executables this fence named on 2026-09-29 were that disagreement, not a missing clock. The
    grep stays; the registry's verdict is added to it. An unbuildable registry adds nothing.
    """
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from desks.mt5.ops.components import registry
        return {p for s in registry(root).all() if s.scheduled for p in s.code_paths}
    except Exception:                                   # pragma: no cover - import guard
        return set()


def _sources(root: Path) -> tuple[set[str], set[str], str]:
    """A source must appear in the collection chain, not merely in the grounds registry."""
    grounds = _json(root / "desks" / "mt5" / "data" / "deep_forest_sources.json")
    objects: set[str] = set()
    if isinstance(grounds, dict):
        for k, v in grounds.items():
            if isinstance(v, list):
                objects.update(str(r.get("id") or r.get("name") or "") for r in v
                               if isinstance(r, dict))
            elif isinstance(v, dict):
                objects.add(str(k))
    elif isinstance(grounds, list):
        objects.update(str(r.get("id") or r.get("name") or "") for r in grounds
                       if isinstance(r, dict))
    objects.discard("")
    if not objects:
        return set(), set(), f"{UNMEASURED}: no source grounds registry in this tree"
    chain = "\n".join(_read(root / "desks" / "mt5" / "reports" / n)
                      for n in ("SOURCE_DRAIN.json", "SOURCE_REGISTRY.json",
                                "INGESTION_EXPLOITATION.json"))
    if not chain.strip():
        return objects, set(), (f"{UNMEASURED}: no chain report (SOURCE_DRAIN / SOURCE_REGISTRY "
                                f"/ INGESTION_EXPLOITATION) exists to place a source in")
    ok = {s for s in objects if s in chain}
    return objects, ok, f"{len(ok)}/{len(objects)} sources hold a position in the chain"


def _families(root: Path) -> tuple[set[str], set[str], str]:
    """A family must be REACHED by the judge, not merely listed beside it."""
    doc = _json(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json")
    if not isinstance(doc, dict):
        return set(), set(), f"{UNMEASURED}: desks/mt5/reports/JUDGE_COVERAGE.json is absent"
    rows = doc.get("families")
    items: list[tuple[str, Any]] = []
    if isinstance(rows, dict):
        items = list(rows.items())
    elif isinstance(rows, list):
        items = [(str(r.get("family") or r.get("name") or ""), r) for r in rows
                 if isinstance(r, dict)]
    objects = {k for k, _ in items if k}
    if not objects:
        return set(), set(), f"{UNMEASURED}: the judge's coverage report declares no families"
    ok = set()
    for k, row in items:
        if not k or not isinstance(row, dict):
            continue
        # THE KEYS ARE THE WRITER'S, NOT A GUESS (measured 2026-09-24). This read was
        # `row.get("judged", row.get("n_judged"))` and `row.get("reached", row.get("judge"))`.
        # `judge_coverage.py` has never emitted any of those four names -- its row schema is
        # mined/queued/judged_window/judged_total/unjudged/quota/window_h/... -- so `ok` was
        # EMPTY on every run since the fence was written and the axis reported
        # "0/168 families are reached by the judge" whatever the judge actually did.
        # It was not measuring a defect, it was measuring a typo: `htf_anchor_trend`, one of the
        # two names this fence was failing on, carries `judged_total: 63`. The legacy names are
        # kept as fallbacks so an older artifact still reads, but the writer's names win.
        judged = next((row[key] for key in ("judged_total", "judged_window", "judged", "n_judged")
                       if isinstance(row.get(key), (int, float))), None)
        reached = row.get("reached", row.get("judge"))
        if (isinstance(judged, (int, float)) and judged > 0) or bool(reached):
            ok.add(k)
    return objects, ok, f"{len(ok)}/{len(objects)} families are reached by the judge"


def _regions(root: Path) -> tuple[set[str], set[str], str]:
    """A region arrives at the CURRENT depth and breadth floors, never at zero."""
    doc = _json(root / "desks" / "mt5" / "reports" / "regional_parity.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("regions"), dict):
        return set(), set(), f"{UNMEASURED}: desks/mt5/reports/regional_parity.json is absent"
    objects = {str(k) for k in doc["regions"]}
    flagged = doc.get("flagged")
    if isinstance(flagged, dict):
        below = {str(k) for k in flagged}
    elif isinstance(flagged, list):
        below = {str(r.get("region") if isinstance(r, dict) else r) for r in flagged}
    else:
        below = set()
    return objects, objects - below, f"{len(objects) - len(below)}/{len(objects)} regions at floor"


def _destructive(root: Path) -> tuple[set[str], set[str], str]:
    """A destructive path must look before it acts: acting on an absence is how records die."""
    objects: set[str] = set()
    ok: set[str] = set()
    for area in (*EXEC_AREAS, "libs"):
        d = root / area
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            text = _read(p)
            if not DESTRUCTIVE.search(text):
                continue
            rel = p.relative_to(root).as_posix()
            objects.add(rel)
            if ABSENCE_GUARD.search(text):
                ok.add(rel)
    if not objects:
        return set(), set(), f"{UNMEASURED}: no destructive path in this tree"
    return objects, ok, f"{len(ok)}/{len(objects)} destructive paths guard against an absence"


def _attribution(root: Path) -> tuple[set[str], set[str], str]:
    """THE SIXTH AXIS: a cell or discovery born carrying WHO produced it and from WHICH region.

    The obligation is satisfied at BIRTH by `libs/moat/registry.enqueue_candidate` and
    `record_discovery`, both of which call the one helper `libs/research/attribution.attribute()`.
    A row created after the obligation date with an empty `producer` column was written by a path
    that bypassed those doors -- that is the arrival this axis catches, and the remedy is to route
    the writer through the registry, never to sweep the column afterwards.

    `UNATTRIBUTABLE` SATISFIES THE OBLIGATION. It is a DECLARED verdict with its reason recorded,
    which is the honest answer when lineage reaches no producer; silence is the defect, not the
    admission (L1.28a). Only rows created after the cut are judged: everything older is the
    one-time backfill `desks/mt5/research/attribution_census.py` performs, not a standing breach.
    """
    db = root / "data" / "alpha_registry.sqlite"
    if not db.exists():
        return set(), set(), f"{UNMEASURED}: no registry at {db.as_posix()}"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from libs.research.attribution import BIRTH_OBLIGATION_FROM, PRODUCER_FIELD
    except Exception as exc:                                       # pragma: no cover - guard
        return set(), set(), f"{UNMEASURED}: attribution helper unreadable ({exc})"
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return set(), set(), f"{UNMEASURED}: registry unopenable ({exc})"
    objects: set[str] = set()
    ok: set[str] = set()
    cut = BIRTH_OBLIGATION_FROM[:19]
    # THE UPPER CUT, AND IT IS A DENOMINATOR AND NOT A TOLERANCE. `attribution_census` is the
    # organ that measures this axis; a row created AFTER its last pass has not been measured yet,
    # and calling it incomplete would be reporting an absence of measurement as a breach (L1.28a).
    # A row still unstamped after the next census pass fails, which is the whole point -- the
    # window is one hourly leg wide and closes by itself.
    measured_to = "9999"
    cov = _json(root / "desks" / "mt5" / "reports" / "ATTRIBUTION_COVERAGE.json")
    at = cov.get("at") if isinstance(cov, dict) else None
    if isinstance(at, str) and len(at) >= 19:
        measured_to = at[:19]
    try:
        for table, idcol, prefix in (("research_candidates", "id", "cell"),
                                     ("discoveries", "discovery_id", "discovery")):
            cols = {str(r[1]) for r in conn.execute(f"pragma table_info({table})")}
            if PRODUCER_FIELD not in cols:
                return set(), set(), (f"{UNMEASURED}: {table} carries no {PRODUCER_FIELD} column "
                                      f"yet (libs/moat/registry.EXTENSIONS adds it on connect)")
            rows = conn.execute(
                f"select {idcol}, coalesce({PRODUCER_FIELD},'') from {table} "  # noqa: S608
                f"where replace(substr(created_at,1,19),' ','T') >= ? "
                f"and replace(substr(created_at,1,19),' ','T') <= ?",
                (cut, measured_to)).fetchall()
            for rid, who in rows:
                name = f"{prefix}:{rid}"
                objects.add(name)
                if str(who or "").strip():
                    ok.add(name)
    except sqlite3.Error as exc:
        return set(), set(), f"{UNMEASURED}: registry unreadable ({exc})"
    finally:
        conn.close()
    if not objects:
        return set(), set(), f"{UNMEASURED}: no cell or discovery born since {cut}"
    return objects, ok, (f"{len(ok)}/{len(objects)} cells and discoveries born since {cut} and "
                         f"measured by {measured_to} carry their producer stamp")


def _certificate_birth(root: Path) -> tuple[set[str], set[str], str]:
    """THE SEVENTH AXIS: every certificate names the producer that earned it, or says why not.

    THE BOUNDARY THIS GUARDS. The sixth axis stamps the CELL at the registry's two doors. A
    certificate is minted from a cell by `scripts/external_gauntlet.py`, which is SEALED and knows
    nothing about producers -- so `UNIVERSAL_SURVIVORS.canon.json` carries `hunt`, `cell`, `sym`,
    `days`, the ten gate results and `gated_at`, and nothing about who found it. The stamp cannot
    ride across that boundary by itself, which is exactly the shape of failure this desk keeps
    repeating: a fact that exists in one place and is silently lost by the next organ.

    `desks/mt5/research/certificate_provenance.py` rebuilds the link by EXACT cell identity on the
    hourly census leg. This clause fails when a certificate the canon holds has no row there at
    all. A row reading UNMEASURED with its reason SATISFIES the obligation -- the same discipline
    the attribution axis uses, and the reason this fence can never be passed by guessing.
    """
    canon = root / "desks" / "mt5" / "data" / "UNIVERSAL_SURVIVORS.canon.json"
    if not canon.exists():
        canon = root / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
    doc = _json(canon)
    surv = doc.get("survivors") if isinstance(doc, dict) else None
    if not isinstance(surv, dict) or not surv:
        return set(), set(), f"{UNMEASURED}: no certificate store readable at {canon.as_posix()}"
    rec_doc = _json(root / "desks" / "mt5" / "data" / "certificate_provenance.json")
    records = rec_doc.get("records") if isinstance(rec_doc, dict) else None
    if not isinstance(records, dict):
        return ({f"certificate:{k}" for k in surv}, set(),
                f"{UNMEASURED}: no birth record at desks/mt5/data/certificate_provenance.json -- "
                f"{len(surv)} certificate(s) with nothing naming their producer. Run "
                f"`python desks/mt5/research/certificate_provenance.py --once`, which the hourly "
                f"leg attribution_census also calls")
    objects: set[str] = set()
    ok: set[str] = set()
    named = 0
    for key, row in surv.items():
        row = row if isinstance(row, dict) else {}
        cell = str(row.get("cell") or "").strip()
        if not cell:
            hunt = str(row.get("hunt") or "").strip()
            cell = (str(key)[len(hunt) + 1:]
                    if hunt and str(key).startswith(hunt + ".") else str(key))
        name = f"certificate:{key}"
        objects.add(name)
        rec = records.get(cell)
        if not isinstance(rec, dict) or not str(rec.get("verdict") or "").strip():
            continue
        # A RECORD WITHOUT A REASON IS SILENCE WEARING A VERDICT'S CLOTHES. UNMEASURED and
        # AMBIGUOUS satisfy the obligation only when they say WHY; a named producer speaks for
        # itself.
        if not rec.get("producer") and not str(rec.get("why") or "").strip():
            continue
        ok.add(name)
        if rec.get("producer"):
            named += 1
    return objects, ok, (f"{len(ok)}/{len(objects)} certificates carry a birth record "
                         f"({named} name a producer by exact identity, "
                         f"{len(ok) - named} record why none could be reached)")


#: A gateway pass this recent means the clocks on this machine are actually turning. The SAME
#: instrument and the SAME window as `check_self_repair` and `check_productivity_census`: three
#: fences asking "is this the host that runs the legs?" must not answer it three different ways.
_TRADING_WINDOW_H = 3.0
#: How old an axis's source report may be before it stops describing today. One hour of margin on
#: the hourly legs that write them.
_SOURCE_STALE_H = 6.0


def _is_trading_host(base: Path) -> bool:
    """Measured from the gateway's own heartbeat, never from a hostname that would rot."""
    try:
        age = time.time() - (base / "desks" / "mt5" / "data" / "gateway_state.json").stat().st_mtime
    except OSError:
        return False
    return age < _TRADING_WINDOW_H * 3600


def _source_age_h(base: Path, rel: str | None) -> float | None:
    if not rel:
        return None
    try:
        return (time.time() - (base / rel).stat().st_mtime) / 3600.0
    except OSError:
        return None


@dataclass(frozen=True)
class Axis:
    name: str
    obligation: str
    derive: Callable[[Path], tuple[set[str], set[str], str]]
    fence: tuple[str, tuple[str, ...]] | None
    #: The report this axis READS. An axis is only as current as the artifact it is derived from,
    #: and on a host that regenerates none of them the age of that file is the whole verdict.
    source: str | None = None


AXES: tuple[Axis, ...] = (
    Axis("executable", "a clock, an artifact, a named consumer and a row in the runtime "
                       "attestation", _executables, ("check_component_registry.py", ()),
         "docs/research/runtime_state.json"),
    Axis("source", "a collection obligation and a position in the chain from collected through "
                   "ingested, represented, cells emitted, cells judged", _sources,
         ("check_source_drain.py", ()), "desks/mt5/reports/SOURCE_DRAIN.json"),
    Axis("family", "membership of the judge's coverage, derived from the registry rather than "
                   "typed", _families, ("check_judge_coverage.py", ()),
         "desks/mt5/reports/JUDGE_COVERAGE.json"),
    Axis("region", "arrival at the CURRENT depth, breadth and ingestion floors, never at zero",
         _regions, ("check_regional_parity.py", ()), "desks/mt5/reports/regional_parity.json"),
    Axis("destructive", "a guard against acting on an absence", _destructive,
         ("check_no_retirement_on_absence.py", ())),
    # SIXTH AXIS (2026-09-23): attribution. Measured that day, 3,663 of 3,862 unique cells and 33
    # of 58 certificates could not be traced to a producer or a region, and the regional board
    # therefore read `Europe: 1,973 sources, 0 cells`. The stamp is now written at birth through
    # ONE helper; this clause is what stops the next writer from re-opening the gap silently.
    Axis("attribution", "the producer that made it and, where the producer belongs to one, its "
                        "region -- stamped at birth by libs/research/attribution.attribute() "
                        "through the two registry doors, never by a later sweep",
         _attribution, ("check_producer_yield.py", ()),
         "desks/mt5/reports/ATTRIBUTION_COVERAGE.json"),
    # SEVENTH AXIS (2026-09-24): the certificate's own birth record. The sixth axis stamps the
    # CELL; a certificate is minted from one by a sealed writer that knows nothing about
    # producers, so the stamp does not ride across that boundary on its own. Measured that day:
    # 174 certificates, provenance-shaped fields on none of them, and the census publishing
    # `coverage 1.0` from a symbol|family fallback that several hundred candidates share. A
    # certificate with no row in the record is the arrival this clause catches.
    Axis("certificate_birth", "a row in desks/mt5/data/certificate_provenance.json naming the "
                              "producer that earned it by EXACT cell identity, or UNMEASURED "
                              "with its reason -- silence is the defect, not the admission",
         _certificate_birth, None,
         "desks/mt5/data/certificate_provenance.json"),
)


def measure(root: Path | None = None, *, floors: Path | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    stored = _json(floors or (base / "docs" / "research" / "birth_obligations.json"))
    known: dict[str, Any] = stored.get("axes", {}) if isinstance(stored, dict) else {}
    axes: dict[str, Any] = {}
    failures: list[str] = []
    trading = _is_trading_host(base)
    for ax in AXES:
        objects, ok, why = ax.derive(base)
        # AN AXIS IS ONLY AS CURRENT AS THE REPORT IT READS, AND ONLY SOME HOSTS WRITE THOSE.
        #
        # MEASURED 2026-09-24, one checker, one commit, two boxes, twelve minutes apart:
        #
        #   vmi3571445 (trading)  JUDGE_COVERAGE.json written 22:46  ->  96 families, 62 reached,
        #                                                                the family axis PASSES
        #   vmi3500897 (build)    the same path, written 02:17       -> 168 families, 28 reached,
        #                                                                "88 arrived without its
        #                                                                 obligation"
        #
        # Nothing arrived. The build box runs ONE enabled MT5 task (`MT5-AdoptRelease`) out of
        # twenty-seven -- every other clock is disabled there BY DESIGN, because that machine
        # authors code and does not trade -- so no leg on it will EVER refresh these reports. The
        # fence was reading a twenty-hour-old file and calling the gap an arrival, which sends an
        # operator to a judge that is working and leaves a gate nobody on that machine can satisfy
        # red every hour (L1.43 -- a permanent red trains the desk to stop reading the fence).
        #
        # SO IT IS UNMEASURED THERE, AND UNMEASURED IS A VERDICT AND NOT A PASS (L1.28a): the age
        # and the artifact are named on the row and printed. THE TEETH ARE UNTOUCHED WHERE THEY
        # BITE: on the trading host `trading` is True and every axis is judged exactly as before,
        # and the same axes on that box still fail today (executable 125, source 6) -- which is
        # the point. This clause narrows WHERE a verdict may be given, never WHAT it is.
        age_h = _source_age_h(base, ax.source)
        # AN ABSENT REPORT IS NOT THIS CLAUSE'S BUSINESS: each `derive` already returns
        # UNMEASURED with its own reason when its input is missing, and a fresh tree that simply
        # has not written a report yet must keep reading exactly as it did. Only a report that
        # EXISTS and has stopped describing today is a staleness question.
        if (not trading and ax.source is not None and not why.startswith(UNMEASURED)
                and age_h is not None and age_h > _SOURCE_STALE_H):
            why = (f"{UNMEASURED}: this host runs no clocks (no gateway pass within "
                   f"{_TRADING_WINDOW_H:g}h) and {ax.source} is {age_h:.1f}h old"
                   + f", past the {_SOURCE_STALE_H:g}h window -- so an incomplete row here is a "
                     f"fact about this machine, not an arrival. Judge this axis on the host that "
                     f"writes the report. Last read: {why}")
        incomplete = sorted(objects - ok)
        _prev = known.get(ax.name)
        prev: dict[str, Any] = _prev if isinstance(_prev, dict) else {}
        baseline = set(prev.get("incomplete") or [])
        arrived = sorted(set(incomplete) - baseline)
        healed = sorted(baseline - set(incomplete))
        axes[ax.name] = {
            "obligation": ax.obligation,
            "objects": len(objects),
            "incomplete": len(incomplete),
            "verdict": UNMEASURED if why.startswith(UNMEASURED) else "measured",
            "why": why,
            "arrived_without_obligation": arrived[:20],
            "healed": len(healed),
            "names": incomplete[:MAX_NAMES],
            "names_dropped": max(0, len(incomplete) - MAX_NAMES),
            "fence": (ax.fence[0] if ax.fence else UNMEASURED),
        }
        if prev.get("names_dropped"):
            axes[ax.name]["verdict"] = UNMEASURED
            axes[ax.name]["why"] = (f"{UNMEASURED}: the floor dropped "
                                    f"{prev['names_dropped']} name(s), so an arrival here cannot "
                                    f"be told from a name the floor could not hold -- {why}")
            arrived = []
            axes[ax.name]["arrived_without_obligation"] = []
        if arrived and not why.startswith(UNMEASURED):
            failures.append(
                f"{ax.name}: {len(arrived)} arrived without its obligation ({ax.obligation}) -- "
                + ", ".join(arrived[:5]) + ("..." if len(arrived) > 5 else "")
                + ". Give it the obligation, or RETIRE it with a reason in "
                  "docs/research/retirements.jsonl.")
    return {"schema": "birth_obligations/1",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "root": str(base), "axes": axes, "failures": failures}


def run_fences(argv_root: Path) -> dict[str, Any]:
    """CALL the fence that already owns an axis rather than re-judging it."""
    out: dict[str, Any] = {}
    for ax in AXES:
        if not ax.fence:
            continue
        script = argv_root / "scripts" / ax.fence[0]
        if not script.is_file():
            out[ax.name] = {"fence": ax.fence[0], "rc": UNMEASURED, "why": "not in this tree"}
            continue
        try:
            r = subprocess.run([sys.executable, "-W", "ignore", str(script), *ax.fence[1]],
                               capture_output=True, text=True, timeout=600, cwd=str(argv_root))
            out[ax.name] = {"fence": ax.fence[0], "rc": r.returncode,
                            "tail": (r.stdout or r.stderr or "").strip().splitlines()[-1:][:1]}
        except (OSError, subprocess.SubprocessError) as exc:
            out[ax.name] = {"fence": ax.fence[0], "rc": UNMEASURED, "why": type(exc).__name__}
    return out


def write_floor(doc: dict[str, Any], path: Path | None = None) -> None:
    out = path or FLOORS
    body = {
        "schema": "birth_obligations_floor/1",
        "at": doc["at"],
        "note": ("The names known to be incomplete on each axis. An object that ACQUIRES its "
                 "obligation drops out of this file automatically (the ratchet falling); an "
                 "object that ARRIVES incomplete fails scripts/check_birth_obligations.py. "
                 "Pre-existing debt is the floor, not a pass -- drive it down on purpose."),
        "axes": {k: {"incomplete": v["names"], "count": v["incomplete"],
                     "names_dropped": v["names_dropped"],
                     "obligation": v["obligation"], "verdict": v["verdict"]}
                 for k, v in doc["axes"].items()},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--with-fences", action="store_true",
                    help="also run the fence that already owns each axis")
    ap.add_argument("--update", action="store_true",
                    help="record today's incomplete set as the floor (a first install, or after "
                         "an arrival has been given its obligation)")
    a = ap.parse_args(argv)
    _name_safe_stdout()             # before the first print: this fence's job is to NAME things
    root = Path(a.root or ROOT)
    doc = measure(root)
    if a.with_fences:
        doc["fences"] = run_fences(root)
        for name, r in doc["fences"].items():
            if isinstance(r.get("rc"), int) and r["rc"] != 0:
                doc["failures"].append(f"{name}: its own fence {r['fence']} exits {r['rc']}")
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for name, ax in doc["axes"].items():
            print(f"birth {name:12s} {ax['objects']:5d} object(s), "
                  f"{ax['incomplete']:4d} incomplete, {ax['healed']:3d} healed -- {ax['why']}")
    if a.update:
        write_floor(doc, (root / "docs" / "research" / "birth_obligations.json"))
        print(f"   floor written: {len(doc['axes'])} axes")
        return 0
    for f in doc["failures"]:
        print(f"   FAILED {f}")
    return 2 if doc["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
