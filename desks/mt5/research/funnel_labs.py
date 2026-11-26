"""FUNNEL.json `labs`: per research lab, breadth, depth and conversion, against rising floors.

THE ORDER (principal, 2026-11-25): the math lab "must run 24/7, never be thin on conversion,
breadth or depth". The box had produced nothing from it for a day while every dashboard read the
last good artifact. This block makes the three properties a number per lab, beside the desk
funnel, with a ratcheting floor each and a freshness verdict:

  breadth     distinct generating units (tradition / generator / scenario / island x model) whose
              donated rows in the last 24 h include at least one TESTABLE recipe
  depth       testable cells donated in the last 24 h (family_spec EXECUTABLE / _VARIANT on the
              row's own family and params -- the compiler's EXACT_RECIPE door reads the same)
  conversion  testable / donated over the same rows (donated -> testable); `judged` and
              `testable_to_judged` beside it from the compiler rows the judge's seen cells name
  last_output_utc  the newest of the lab's main artifact and its donation files
  status      STALE when last_output_utc is older than STALE_AFTER_S (2 h) or absent ->
              UNMEASURED; else BELOW_FLOOR when any measured value is under its floor; else OK

An input that cannot be read is UNMEASURED, never 0. A row that is not testable is counted by
its family_spec status under `refused` -- a named refusal, never a silent drop. The floors live in
data/funnel_floors.json under `labs` and follow the funnel's own rule: a met floor lifts to
RATCHET_SHARE of the reading, it never falls, and there is no ceiling.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"
STALE_AFTER_S = 2 * 3600
WINDOW_S = 24 * 3600
#: Newest donation files read per lab per pass; a lab writes about one an hour per seat.
MAX_FILES = 240
METRICS: tuple[str, ...] = ("breadth", "depth", "conversion")

#: lab -> (main artifact under reports/, donation seat directories under data/intelligence/)
LABS: dict[str, tuple[str, tuple[str, ...]]] = {
    "mathlab": ("MATH_LAB.json", ("mathlab",)),
    "physics_lab": ("PHYSICS_LAB.json", ("physics_lab",)),
    "expression_factory": ("EXPRESSION_FACTORY.json", ("expression_factory",)),
    "world_lab": ("WORLD_LAB.json", ("world_lab",)),
    "coevolution": ("COEVOLUTION.json", ()),
}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _iso(ts: float | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, UTC).isoformat(timespec="seconds")


def _unit(row: Mapping[str, Any]) -> str:
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    return str(ev.get("tradition") or row.get("generator") or ev.get("scenario")
               or row.get("scenario") or row.get("family") or "unattributed")


def _status(row: Mapping[str, Any]) -> str:
    from research import family_spec as fs
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    try:
        return str(fs.to_executable(str(row.get("family") or ""), params)["status"])
    except Exception:
        return UNMEASURED


def donation_rows(roots: Iterable[Path], seats: tuple[str, ...], since: float
                  ) -> tuple[list[dict[str, Any]] | None, float | None, int]:
    """(rows donated since `since`, newest file mtime, files read). None when no seat directory
    exists under any root -- the lab has never donated HERE, which is UNMEASURED, not zero."""
    files: list[tuple[float, Path]] = []
    seen_dir = False
    for root in roots:
        for seat in seats:
            d = Path(root) / seat
            if not d.is_dir():
                continue
            seen_dir = True
            for f in d.glob("discoveries_*.json"):
                try:
                    files.append((f.stat().st_mtime, f))
                except OSError:
                    continue
    if not seen_dir:
        return None, None, 0
    files.sort(reverse=True)
    newest = files[0][0] if files else None
    rows: list[dict[str, Any]] = []
    read = 0
    for mtime, f in files[:MAX_FILES]:
        if mtime < since:
            break
        doc = _read(f)
        read += 1
        for r in (doc.get("discoveries") if isinstance(doc, dict) else None) or []:
            if isinstance(r, dict):
                rows.append(r)
    return rows, newest, read


def _coevolution_rows(report: Any) -> list[dict[str, Any]] | None:
    """The co-evolution lab donates to the registry, not to an intake file: its enqueued
    survivors, as rows of the conditioning family they were queued under."""
    if not isinstance(report, dict):
        return None
    out: list[dict[str, Any]] = []
    surv = {(s.get("symbol"), s.get("island")): s for s in report.get("survivors") or []
            if isinstance(s, dict)}
    for e in report.get("registry") or []:
        if not isinstance(e, dict) or not e.get("enqueued"):
            continue
        s = surv.get((e.get("symbol"), e.get("island"))) or {}
        out.append({"family": "conditioning_model",
                    "params": {"model_family": s.get("model"), "features": s.get("features")},
                    "generator": f"{e.get('island')}:{s.get('model')}",
                    "symbol": e.get("symbol")})
    return out


def judged_share(rows: list[Mapping[str, Any]] | None, seen: set[str] | None, lab: str,
                 who: Any) -> tuple[Any, Any]:
    """(testable compiler rows of this lab, of them judged) from the compiler's rows and the
    judge's seen cells; UNMEASURED when either is unreadable."""
    if rows is None or seen is None:
        return UNMEASURED, UNMEASURED
    from research import alt_catalog as ac
    from research import producer_loop as PL
    names = {who(lab), *(who(s) for s in LABS[lab][1])} if who else {lab, *LABS[lab][1]}
    testable = judged = 0
    for r in rows:
        if who(PL.row_producer(r)) not in names:
            continue
        if _status(r) not in ("EXECUTABLE", "EXECUTABLE_VARIANT"):
            continue
        testable += 1
        cid = ac._cell(r)
        if cid and cid in seen:
            judged += 1
    return testable, judged


def measure(lab: str, *, reports: Path, roots: Iterable[Path], now: datetime,
            compiler_rows: list[Mapping[str, Any]] | None = None,
            seen: set[str] | None = None, who: Any = None) -> dict[str, Any]:
    artifact_name, seats = LABS[lab]
    artifact = reports / artifact_name
    try:
        art_mtime: float | None = artifact.stat().st_mtime
    except OSError:
        art_mtime = None
    since = now.timestamp() - WINDOW_S
    if seats:
        rows, newest, files = donation_rows(roots, seats, since)
        basis = f"data/intelligence/{{{','.join(seats)}}}/discoveries_*.json, last 24 h"
    else:
        report = _read(artifact)
        rows = _coevolution_rows(report)
        if rows is not None and art_mtime is not None and art_mtime < since:
            rows = []
        newest, files = None, 0
        basis = f"reports/{artifact_name} registry (enqueued survivors)"
    last = max((t for t in (art_mtime, newest) if t is not None), default=None)
    out: dict[str, Any] = {"artifact": f"reports/{artifact_name}", "basis": basis,
                           "files_read": files, "last_output_utc": _iso(last)}
    if rows is None:
        out.update(breadth=UNMEASURED, depth=UNMEASURED, conversion=UNMEASURED,
                   donated=UNMEASURED, testable=UNMEASURED, refused={})
    else:
        refused: dict[str, int] = {}
        units: set[str] = set()
        testable = 0
        for r in rows:
            st = _status(r)
            if st in ("EXECUTABLE", "EXECUTABLE_VARIANT"):
                testable += 1
                units.add(_unit(r))
            else:
                refused[st] = refused.get(st, 0) + 1
        out.update(breadth=len(units), depth=testable, donated=len(rows), testable=testable,
                   conversion=(round(testable / len(rows), 6) if rows else UNMEASURED),
                   refused=refused)
    t, j = judged_share(compiler_rows, seen, lab, who)
    out["compiler_testable"] = t
    out["judged"] = j
    out["testable_to_judged"] = (round(j / t, 6) if isinstance(t, int) and isinstance(j, int)
                                 and t else UNMEASURED)
    return out


def apply_floors(labs: dict[str, dict[str, Any]], floors: Mapping[str, Any], now: datetime,
                 ratchet_one: Any) -> dict[str, Any]:
    """Stamp each lab with its floors and status; return the new `labs` floors block."""
    old_block = floors.get("labs") if isinstance(floors.get("labs"), dict) else {}
    new_block: dict[str, Any] = {}
    for lab, row in labs.items():
        old = old_block.get(lab) if isinstance(old_block.get(lab), dict) else {}
        new: dict[str, Any] = {}
        violated = False
        for m in METRICS:
            f_old = old.get(f"{m}_floor")
            f_new, verdict = ratchet_one(f_old, row.get(m), integer=(m != "conversion"))
            row[f"{m}_floor"] = f_old if f_old is not None else UNMEASURED
            row[f"{m}_status"] = verdict
            violated = violated or verdict == "VIOLATED"
            new[f"{m}_floor"] = f_new
        new["raised_at"] = (now.isoformat(timespec="seconds")
                            if any(new[f"{m}_floor"] != old.get(f"{m}_floor") for m in METRICS)
                            else old.get("raised_at"))
        new_block[lab] = new
        last = row.get("last_output_utc")
        age = (now - datetime.fromisoformat(last)).total_seconds() if last else None
        row["age_s"] = round(age, 1) if age is not None else UNMEASURED
        if age is None:
            row["status"] = UNMEASURED
        elif age > STALE_AFTER_S:
            row["status"] = "STALE"
        elif violated:
            row["status"] = "BELOW_FLOOR"
        elif all(row.get(m) == UNMEASURED for m in METRICS):
            row["status"] = UNMEASURED
        else:
            row["status"] = "OK"
    return new_block


def merge_up(disk: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    """The `labs` floors to write: every floor the max of disk and the new reading."""
    out: dict[str, Any] = {k: dict(v) for k, v in (new or {}).items() if isinstance(v, dict)}
    for lab, v in (disk or {}).items():
        if not isinstance(v, dict):
            continue
        row = out.setdefault(lab, {})
        for m in METRICS:
            old, cur = v.get(f"{m}_floor"), row.get(f"{m}_floor")
            if isinstance(old, int | float) and not isinstance(old, bool) and (
                    not isinstance(cur, int | float) or old > cur):
                row[f"{m}_floor"] = old
                row["raised_at"] = v.get("raised_at")
    return out


def block(*, reports: Path, roots: Iterable[Path], now: datetime, floors: Mapping[str, Any],
          ratchet_one: Any, compiler_rows: list[Mapping[str, Any]] | None = None,
          seen: set[str] | None = None, who: Any = None
          ) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the `labs` block, the new `labs` floors). Never raises for one lab: a lab whose
    measurement fails is UNMEASURED with the exception's type named."""
    roots = list(roots)
    t0 = time.monotonic()
    labs: dict[str, dict[str, Any]] = {}
    for lab in LABS:
        try:
            labs[lab] = measure(lab, reports=reports, roots=roots, now=now,
                                compiler_rows=compiler_rows, seen=seen, who=who)
        except Exception as exc:                      # one lab never costs the block
            labs[lab] = dict.fromkeys(METRICS, UNMEASURED) | {
                "last_output_utc": None, "why": f"{type(exc).__name__}: {exc}"[:200]}
    new_floors = apply_floors(labs, floors, now, ratchet_one)
    for row in labs.values():
        row["measured_in_s"] = round(time.monotonic() - t0, 3)
    return labs, {"labs": new_floors}


def unmeasured_block(why: str) -> dict[str, Any]:
    """The same shape when the block itself could not be built: every lab UNMEASURED."""
    return {lab: {**dict.fromkeys(METRICS, UNMEASURED),
                  **{f"{m}_floor": UNMEASURED for m in METRICS},
                  "last_output_utc": None, "status": UNMEASURED, "why": why[:200]}
            for lab in LABS}
