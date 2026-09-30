#!/usr/bin/env python3
"""THE CONVERSION FUNNEL -- mined -> cell -> judged -> verdict -> PASS -> certificate -> clock,
with the count lost at every step and the NAMED reason it was lost.

WHY THIS EXISTS (the 25 Sep lane "maximise conversion to certificates", rebuilt 2026-09-30). The
desk's conversion was measured in pieces that nothing put side by side: the registry counts its
candidates, the judge appends a verdict ledger, the canon holds certificates, the enrolment census
holds clocks. Each organ reported its own stage, so a row that fell BETWEEN two of them -- a PASS
the canon never received, a certificate no clock picked up, a verdict that was really a build
failure -- was visible to nobody. The noon CRO of 2026-09-30 could only say "UNKNOWN verdicts
9.55% of 29,466" and "build/data failures UNMEASURED". This organ is the drop-finder: one
artifact, every stage, every loss with its reason and the organ that owns it.

THE STAGES, AND WHERE EACH NUMBER COMES FROM (all read, nothing written but the artifact):

    mined        research_candidates rows, by status          registry (`GROUP BY status`)
    cells        the testable statuses                        registry; losses = the parked
                                                              statuses, each by failure_class
    judged       cells with a verdict in the judge's ledger   data/hypotheses/gate_verdict_ledger
    verdict      PASS / FAIL_AT_GATE / REFUSED_PRE_GATE /     the LATEST ledger row per cell
                 UNKNOWN -- and UNKNOWN split by the judge's
                 own `downstream_status` into BUILD_FAILED,
                 DATA_MISSING, MODIFIER, BUDGET_DEFERRED and NO_STATUS (the <60-observation
                 UNMEASURED verdicts, and rows written before 2026-09-13)
    certificate  PASS cells whose `external.<cell>` key       reports/UNIVERSAL_SURVIVORS.json
                 the canon holds                              and its seal; losses = retired,
                                                              evicted-unrunnable, awaiting
                                                              republication, banned family, and
                                                              UNEXPLAINED -- the drop to fix
    clock        certificates on a forward clock, accruing    reports/FORWARD_ENROLMENT.json

LATENCY (CRO duty D5, "idea-to-certificate latency UNMEASURED"): p50 / p90 / max hours and the
counts, over the last seven days, for idea -> cell, donation -> docket, docket -> first verdict,
PASS -> certificate and certificate -> forward clock -- each from two stamps an organ already
writes, named in its `basis`. A step no organ stamps is listed under `unstamped_steps` as
UNMEASURED; a stamped step nothing crossed is NO_EVENTS_IN_WINDOW, never a latency of zero.

WHAT IT NEVER DOES. It moves no gate, judges nothing, writes no certificate and no clock. The
thresholds are sealed (`external_gauntlet.py`, `gate_policy.py`); this measures where the rows
that clear them are lost afterwards, and where rows that could never clear them spent the judge.
An input it cannot read is UNMEASURED with the reason -- never zero (L1.28a).

BOUNDED. The ledger is streamed line by line under the pass budget (`--budget-s`, and never past
`QUANT_LEG_BUDGET_S`); a stream the budget cuts is published as `partial` with the bytes read,
and the artifact is checkpointed before the stream starts.

    python desks/mt5/research/conversion_funnel.py --once --budget-s 240
Clock: hourly leg `conversion_funnel` (research/hourly_cycle.py). Artifact:
desks/mt5/reports/CONVERSION_FUNNEL.json. Consumer: the CRO cycle's conversion duty, and
`conversion_maximiser`'s owners table names the organ for each loss it lists.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "conversion_funnel"
#: The artifact, bound at module level so the component registry reads it off the organ itself.
OUT = DESK / "reports" / "CONVERSION_FUNNEL.json"
UNMEASURED = "UNMEASURED"
STAGE_COMPLETE = "COMPLETE"
BUDGET_S = 240.0
WRITE_MARGIN_MIN_S = 60.0
WRITE_MARGIN_FRAC = 0.15
#: The window the CRO reads the UNKNOWN share over (its 43% was a 7-day figure).
WINDOW_DAYS = 7.0
SAMPLE = 25

#: Registry statuses that ARE a gauntlet cell -- one list, the maximiser's.
TESTABLE_STATUSES = ("queued", "claimed", "judged", "survived", "rejected", "live", "forward")
AWAITING_JUDGE = ("queued", "claimed")

#: The judge's own vocabulary for a row that got no gate verdict (external_gauntlet.py: the
#: blocked-build and deferred verdicts carry `downstream_status`; the <60-observation verdicts
#: carry `unmeasured: true` and no status, which the ledger cannot see).
UNKNOWN_CLASS: dict[str, str] = {
    "NOT_RUN_BUILD_FAILED": "BUILD_FAILED",
    "NOT_RUN_DATA_MISSING": "DATA_MISSING",
    "NOT_RUN_MODIFIER": "MODIFIER",
    "NOT_RUN_BUILD_BUDGET_DEFERRED": "BUDGET_DEFERRED",
}
#: Terminal gates that are REFUSALS BEFORE THE TEN GATES, not a gate failure.
PRE_GATE = frozenset({"symbol_eligibility", "economic_prior"})

#: WHO OWNS EACH LOSS. A loss with no address is a report nobody acts on.
OWNER: dict[str, str] = {
    "donated": "desks/mt5/research/conversion_maximiser.py (drains donated rows every hour)",
    "untestable_queued": "desks/mt5/research/conversion_maximiser.py (supplies the falsifier)",
    "retired": "the organ named in the row's failure_class (OFF_UNIVERSE / EVENT_LANE / "
               "superseded repair) -- admissible refusals",
    "study": "research governance: live-banned family, kept for study, never judged",
    "routed": "whichever organ routed it (parked_past_grace in CONVERSION_MAXIMISER.json)",
    "BUILD_FAILED": "desks/mt5/mt5desk/families.py build_cell (signal construction returned no "
                    "executable cell) -- a build defect, not evidence against the edge",
    "DATA_MISSING": "research/fetch_universe.py via the hourly `refresh_bars` leg -- the cell's "
                    "point-in-time parquet is missing or empty",
    "MODIFIER": "mt5desk/cell_modifiers.py -- a modifier the builder could not apply",
    "BUDGET_DEFERRED": "the judge's build budget (judging_throughput sizes it; the cache is "
                       "cumulative, so the next sweep resumes) -- work not yet done",
    "NO_STATUS": "the proposing search: too few daily observations (<60) to judge, or a row "
                 "written before 2026-09-13 when the ledger began recording the terminal gate",
    "RETIRED_AFTER_CERTIFICATION": "the retirer named in the seal's retired_certificates",
    "UNRUNNABLE_EVICTED": "research/certificate_hygiene.py (no runnable shadow_spec)",
    "AWAITING_REPUBLICATION": "desks/mt5/research/canon_publication.py (seals the next sweep, "
                              "or recovers it from the gate output)",
    "BANNED_FAMILY": "mt5desk/live_policy.py -- refused at both live doors",
    "UNEXPLAINED": "desks/mt5/research/canon_publication.py recovery (see its refused reasons) "
                   "-- a PASS the canon does not hold and no named reason explains",
    "CLOCKLESS": "desks/mt5/research/forward_enrolment.py (repair sweep)",
    "NOT_ACCRUING": "the blocker named per status in FORWARD_ENROLMENT.json `blocked`",
}


@dataclass(frozen=True)
class Paths:
    ledger: Path
    report: Path
    seal: Path
    enrolment: Path
    cure: Path
    canon_pub: Path
    maximiser: Path
    out: Path

    @classmethod
    def at(cls, desk: Path) -> Paths:
        return cls(ledger=desk / "data" / "hypotheses" / "gate_verdict_ledger.jsonl",
                   report=desk / "reports" / "UNIVERSAL_SURVIVORS.json",
                   seal=desk / "data" / "UNIVERSAL_SURVIVORS.canon.json",
                   enrolment=desk / "reports" / "FORWARD_ENROLMENT.json",
                   cure=desk / "reports" / "POWER_CURE_CANDIDATES.json",
                   canon_pub=desk / "reports" / "CANON_PUBLICATION.json",
                   maximiser=desk / "reports" / "CONVERSION_MAXIMISER.json",
                   out=desk / "reports" / OUT.name)


# ------------------------------------------------------------------------------ utilities
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _atomic_write(path: Path, doc: Any) -> None:
    """tempfile + os.replace; a read-only destination is made writable first (WinError 5)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    try:
        os.replace(tmp, path)
    except PermissionError:
        with contextlib.suppress(OSError):
            os.chmod(path, 0o644)
        os.replace(tmp, path)


def effective_budget_s(requested: float, env: Mapping[str, str] | None = None) -> float:
    """Own budget, never past the cycle's cap minus its write margin (hourly_cycle)."""
    source = os.environ if env is None else env
    try:
        cap = float(source.get("QUANT_LEG_BUDGET_S") or 0.0)
    except (TypeError, ValueError):
        cap = 0.0
    if cap <= 0.0:
        return float(requested)
    return max(10.0, min(float(requested),
                         cap - max(WRITE_MARGIN_MIN_S, WRITE_MARGIN_FRAC * float(requested))))


# ------------------------------------------------------------------------ stage 1: mined
def registry_stage(conn: sqlite3.Connection | None) -> dict[str, Any]:
    """Mined -> testable cell, from the registry's status index (one GROUP BY each)."""
    if conn is None:
        return {"status": UNMEASURED, "why": "the registry could not be opened"}
    try:
        by_status = {str(r[0] or ""): int(r[1]) for r in conn.execute(
            "SELECT status, COUNT(*) FROM research_candidates GROUP BY status")}
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    parked: dict[str, dict[str, int]] = {}
    for st in ("retired", "study", "routed"):
        if not by_status.get(st):
            continue
        try:
            parked[st] = {str(r[0] or "UNSTATED"): int(r[1]) for r in conn.execute(
                "SELECT failure_class, COUNT(*) FROM research_candidates WHERE status=? "
                "GROUP BY failure_class", (st,))}
        except sqlite3.Error as exc:
            parked[st] = {UNMEASURED: 0, f"{type(exc).__name__}": 0}
    discoveries: dict[str, int] | str
    try:
        discoveries = {str(r[0] or ""): int(r[1]) for r in conn.execute(
            "SELECT state, COUNT(*) FROM discoveries GROUP BY state")}
    except sqlite3.Error as exc:
        discoveries = f"{UNMEASURED}: {type(exc).__name__}: {exc}"
    mined = sum(by_status.values())
    testable = sum(by_status.get(s, 0) for s in TESTABLE_STATUSES)
    awaiting = sum(by_status.get(s, 0) for s in AWAITING_JUDGE)
    lost = {st: n for st, n in by_status.items() if st not in TESTABLE_STATUSES}
    return {"status": "MEASURED", "by_status": by_status, "discoveries_by_state": discoveries,
            "mined": mined, "testable_cells": testable,
            "judged_in_registry": testable - awaiting, "awaiting_judge": awaiting,
            "lost_before_cell": lost, "lost_before_cell_by_class": parked,
            "owners": {k: OWNER.get(k, "unassigned") for k in lost}}


# ---------------------------------------------------------------- stage 2: the verdicts
def classify_verdict(row: Mapping[str, Any]) -> tuple[str, str]:
    """(verdict class, sub-class) for one ledger row, in the judge's own vocabulary."""
    gate = str(row.get("terminal_gate") or "")
    if row.get("passed") is True or gate == "PASSED":
        return "PASS", "PASSED"
    if gate and gate != "UNKNOWN":
        return ("REFUSED_PRE_GATE" if gate in PRE_GATE else "FAIL_AT_GATE"), gate
    ds = str(row.get("downstream_status") or "")
    return "UNKNOWN", UNKNOWN_CLASS.get(ds, ds or "NO_STATUS")


def stream_ledger(path: Path, *, deadline: float,
                  since: datetime | None = None) -> dict[str, Any]:
    """The LATEST verdict per cell, streamed; bounded by `deadline` (time.monotonic)."""
    if not path.exists():
        return {"status": UNMEASURED, "why": f"{path.name} absent: no verdict has been measured "
                                              "on this checkout, which is not zero verdicts"}
    latest: dict[str, tuple[str, str, str, str, str]] = {}
    window: Counter[str] = Counter()
    window_sub: Counter[str] = Counter()
    rows = bad = 0
    size = path.stat().st_size
    read = 0
    partial = False
    cut = since.isoformat() if since else ""
    with path.open("rb") as fh:
        for raw in fh:
            read += len(raw)
            if (rows & 0x3FFF) == 0 and time.monotonic() > deadline:
                partial = True
                break
            try:
                r = json.loads(raw)
            except ValueError:
                bad += 1
                continue
            if not isinstance(r, dict) or not r.get("cell"):
                bad += 1
                continue
            rows += 1
            cls, sub = classify_verdict(r)
            at = str(r.get("at") or "")
            latest[str(r["cell"])] = (cls, sys.intern(sub), sys.intern(str(r.get("family") or "")),
                                      str(r.get("sym") or ""), at)
            if cut and at >= cut:
                window[cls] += 1
                window_sub[f"{cls}:{sub}"] += 1
    return {"status": "MEASURED", "latest": latest, "rows": rows, "unreadable_rows": bad,
            "bytes_read": read, "bytes_total": size, "partial": partial,
            "window_rows": dict(window), "window_by_sub": dict(window_sub)}


def verdict_stage(stream: Mapping[str, Any]) -> dict[str, Any]:
    if stream.get("status") != "MEASURED":
        return dict(stream)
    latest: Mapping[str, tuple[str, str, str, str, str]] = stream["latest"]
    by_class: Counter[str] = Counter()
    by_sub: dict[str, Counter[str]] = {}
    unknown_by_family: Counter[str] = Counter()
    for cls, sub, fam, _sym, _at in latest.values():
        by_class[cls] += 1
        by_sub.setdefault(cls, Counter())[sub] += 1
        if cls == "UNKNOWN":
            unknown_by_family[f"{sub}:{fam or 'unknown'}"] += 1
    judged = sum(by_class.values())
    unknown = by_class.get("UNKNOWN", 0)
    fixable = sum(by_sub.get("UNKNOWN", Counter()).get(k, 0)
                  for k in ("BUILD_FAILED", "DATA_MISSING", "MODIFIER"))
    win = dict(stream.get("window_rows") or {})
    win_total = sum(win.values())
    return {
        "status": "MEASURED", "partial": bool(stream.get("partial")),
        "ledger_rows_read": stream.get("rows"), "bytes_read": stream.get("bytes_read"),
        "bytes_total": stream.get("bytes_total"),
        "cells_judged": judged, "by_class": dict(by_class.most_common()),
        "by_subclass": {k: dict(v.most_common()) for k, v in by_sub.items()},
        "unknown_share": round(unknown / judged, 4) if judged else None,
        "unknown_build_or_data": fixable,
        "unknown_build_or_data_share": round(fixable / unknown, 4) if unknown else None,
        "unknown_top": dict(unknown_by_family.most_common(SAMPLE)),
        "window_days": WINDOW_DAYS, "window_rows": win,
        "window_unknown_share": (round(win.get("UNKNOWN", 0) / win_total, 4)
                                 if win_total else None),
        "window_by_subclass": dict(sorted((stream.get("window_by_sub") or {}).items(),
                                          key=lambda kv: -kv[1])),
        "owners": {k: OWNER[k] for k in (*UNKNOWN_CLASS.values(), "NO_STATUS")},
        "basis": "latest ledger row per cell (the ledger appends on CHANGE, so the last row is "
                 "the cell's standing verdict); the window counts verdict CHANGES in it",
    }


# ----------------------------------------------------------- stage 3: PASS -> certificate
def _canon(paths: Paths) -> dict[str, Any]:
    keys: set[str] = set()
    retired: set[str] = set()
    evicted: set[str] = set()
    swept: list[datetime] = []
    readable = 0
    for p in (paths.report, paths.seal):
        doc = _read(p)
        if not isinstance(doc, Mapping):
            continue
        readable += 1
        surv = doc.get("survivors")
        if isinstance(surv, Mapping):
            keys |= {str(k) for k in surv}
        ret = doc.get("retired_certificates")
        if isinstance(ret, (Mapping, list)):
            retired |= {str(k) for k in ret}
        ev = doc.get("unrunnable_evicted")
        if isinstance(ev, list):
            evicted |= {str(k) for k in ev}
        ts = _parse_ts(doc.get("swept_at") or doc.get("generated_at"))
        if ts:
            swept.append(ts)
    return {"readable": readable, "keys": keys, "retired": retired, "evicted": evicted,
            "swept_at": max(swept) if swept else None}


def _banned() -> frozenset[str]:
    try:
        from research.merge_hypotheses import live_banned_families
        return frozenset(live_banned_families())
    except Exception:                                                    # pragma: no cover
        return frozenset({"discovered"})


def certificate_stage(stream: Mapping[str, Any], paths: Paths,
                      banned: Iterable[str] | None = None) -> dict[str, Any]:
    if stream.get("status") != "MEASURED":
        return {"status": UNMEASURED, "why": "no verdicts to follow into the canon"}
    canon = _canon(paths)
    if not canon["readable"]:
        return {"status": UNMEASURED,
                "why": f"neither {paths.report.name} nor {paths.seal.name} is readable, so no "
                       "PASS can be followed to a certificate"}
    ban = frozenset(banned if banned is not None else _banned())
    swept = canon["swept_at"]
    lost: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}
    certified = passes = 0
    for cell, (cls, _sub, fam, _sym, at) in stream["latest"].items():
        if cls != "PASS":
            continue
        passes += 1
        key = f"external.{cell}"
        if key in canon["keys"]:
            certified += 1
            continue
        if key in canon["retired"]:
            why = "RETIRED_AFTER_CERTIFICATION"
        elif key in canon["evicted"]:
            why = "UNRUNNABLE_EVICTED"
        elif fam in ban:
            why = "BANNED_FAMILY"
        elif swept is None or ((_parse_ts(at) or swept) > swept):
            why = "AWAITING_REPUBLICATION"
        else:
            why = "UNEXPLAINED"
        lost[why] += 1
        bucket = samples.setdefault(why, [])
        if len(bucket) < SAMPLE:
            bucket.append(key)
    pub = _read(paths.canon_pub)
    recovery = (pub.get("recovery") if isinstance(pub, Mapping) else None) or {}
    return {"status": "MEASURED", "passes": passes, "certified": certified,
            "certificates_in_canon": len(canon["keys"]),
            "canon_swept_at": swept.isoformat() if swept else None,
            "lost": dict(lost.most_common()), "lost_samples": samples,
            "owners": {k: OWNER[k] for k in lost},
            "canon_publication_refused": {
                "recovery": recovery.get("refused") if isinstance(recovery, Mapping) else None,
                "publish": pub.get("refused_rows") if isinstance(pub, Mapping) else None,
                "why": "the publisher's own refusal counts: the likeliest names for an "
                       "UNEXPLAINED loss above"},
            "rule": "every PASS is a certificate or carries a named reason it is not; "
                    "UNEXPLAINED is the drop this funnel exists to find"}


# ---------------------------------------------------------- stage 4: certificate -> clock
def clock_stage(paths: Paths, now: datetime) -> dict[str, Any]:
    doc = _read(paths.enrolment)
    if not isinstance(doc, Mapping):
        return {"status": UNMEASURED,
                "why": f"{paths.enrolment.name} absent or unreadable: whether certificates reach "
                       "a forward clock is UNMEASURED here, never a clean verdict"}
    at = _parse_ts(doc.get("at"))
    raw_missing = doc.get("missing")
    missing: list[Any] = raw_missing if isinstance(raw_missing, list) else []
    return {"status": "MEASURED", "at": doc.get("at"),
            "age_h": round((now - at).total_seconds() / 3600.0, 2) if at else None,
            "certificates": doc.get("n_certificates"), "on_clock": doc.get("n_enrolled"),
            "accruing": doc.get("n_accruing"),
            "lost": {"CLOCKLESS": doc.get("n_missing"), "NOT_ACCRUING": doc.get("n_blocked")},
            "not_accruing_by_status": doc.get("blocked_by_status"),
            "clockless_samples": [str(r.get("key")) for r in missing[:SAMPLE]
                                  if isinstance(r, Mapping)],
            "owners": {k: OWNER[k] for k in ("CLOCKLESS", "NOT_ACCRUING")}}


def near_miss_stage(paths: Paths) -> dict[str, Any]:
    """The near-misses the judge already routes: validity-pass, power-deficient cells on the
    forward cure (POWER_CURE_CANDIDATES.json). Counted, never promoted from here."""
    doc = _read(paths.cure)
    if not isinstance(doc, Mapping):
        return {"status": UNMEASURED, "why": f"{paths.cure.name} absent or unreadable"}
    return {"status": "MEASURED", "power_cure_candidates": doc.get("n"),
            "swept_at": doc.get("swept_at"),
            "route": "forward clock under gate_spec power_cure_via_forward; the promoter applies "
                     "the cure thresholds -- no gate moves"}


# ------------------------------------------------------------- D5: the latency of each step
def _hours(a: Any, b: Any) -> float | None:
    ta, tb = _parse_ts(a), _parse_ts(b)
    if ta is None or tb is None:
        return None
    return (tb - ta).total_seconds() / 3600.0


def distribution(values: Iterable[float | None], *, basis: str) -> dict[str, Any]:
    """p50 / p90 / max in hours, with the counts behind them. No samples is NOT zero latency."""
    vals = sorted(v for v in values if v is not None)
    neg = sum(1 for v in vals if v < 0)
    vals = [v for v in vals if v >= 0]
    if not vals:
        return {"status": "NO_EVENTS_IN_WINDOW", "n": 0, "negative_excluded": neg,
                "basis": basis,
                "why": "the stage is stamped but nothing crossed it in the window -- a count of "
                       "zero events, never a latency of zero"}

    def q(p: float) -> float:
        i = min(len(vals) - 1, max(0, round(p * (len(vals) - 1))))
        return round(vals[i], 3)

    return {"status": "MEASURED", "n": len(vals), "p50_h": q(0.5), "p90_h": q(0.9),
            "p95_h": q(0.95), "max_h": round(vals[-1], 3), "negative_excluded": neg,
            "basis": basis}


def _sql_pairs(conn: sqlite3.Connection | None, sql: str, args: tuple[Any, ...],
               basis: str) -> dict[str, Any]:
    if conn is None:
        return {"status": UNMEASURED, "why": "the registry could not be opened", "basis": basis}
    try:
        rows = conn.execute(sql, args).fetchall()
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}", "basis": basis}
    return distribution((_hours(a, b) for a, b in rows), basis=basis)


def latency_stage(conn: sqlite3.Connection | None, stream: Mapping[str, Any], paths: Paths,
                  now: datetime) -> dict[str, Any]:
    """CRO duty D5: how long each step of the funnel takes, from stamps the organs already
    write. Every stage names its two stamps; a step no organ stamps is UNMEASURED by name."""
    cut = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    out: dict[str, Any] = {"window_days": WINDOW_DAYS, "unit": "hours"}
    out["idea_to_cell"] = _sql_pairs(
        conn,
        "SELECT d.created_at, MIN(c.created_at) FROM discoveries d "
        "JOIN research_candidates c ON c.discovery_id = d.discovery_id "
        "WHERE d.created_at >= ? GROUP BY d.discovery_id", (cut,),
        "discoveries.created_at -> the first research_candidates.created_at minted from it "
        "(discovery_id), for discoveries in the window")
    out["donation_to_docket"] = _sql_pairs(
        conn,
        "SELECT a.created_at, p.created_at FROM provenance p "
        "JOIN research_candidates a ON a.id = p.from_id "
        "WHERE p.relation = 'conversion_repair' AND p.created_at >= ?", (cut,),
        "a donated/untestable row's created_at -> the provenance edge `conversion_repair` "
        "that put its repaired cell on the queue (conversion_maximiser)")
    out["docket_to_first_verdict"] = _sql_pairs(
        conn,
        "SELECT created_at, judged_at FROM research_candidates "
        "WHERE judged_at IS NOT NULL AND judged_at >= ?", (cut,),
        "research_candidates.created_at (on the queue) -> judged_at (the verdict's `at`, synced "
        "from the judge's ledger by libs/moat/registry)")
    if stream.get("status") == "MEASURED":
        canon: dict[str, Any] = {}
        for p in (paths.seal, paths.report):
            doc = _read(p)
            surv = doc.get("survivors") if isinstance(doc, Mapping) else None
            if isinstance(surv, Mapping):
                for k, v in surv.items():
                    # A row that carries its stamp wins over one that does not.
                    if isinstance(v, Mapping) and (v.get("gated_at")
                                                   or str(k) not in canon):
                        canon[str(k)] = v
        pairs = []
        for cell, (cls, _sub, _fam, _sym, at) in stream["latest"].items():
            row = canon.get(f"external.{cell}")
            if cls == "PASS" and row is not None and at >= cut:
                pairs.append(_hours(at, row.get("gated_at")))
        out["pass_to_certificate"] = distribution(
            pairs, basis="the ledger row that turned the cell PASS (`at`) -> the canon row's "
                         "`gated_at`; gated_at is re-stamped when a later sweep re-passes the "
                         "cell, so this is an upper bound; a certificate sealed before its "
                         "ledger row is excluded and counted as negative_excluded")
    else:
        out["pass_to_certificate"] = {"status": UNMEASURED,
                                      "why": "no verdict ledger read this pass"}
    enrol = _read(paths.enrolment)
    certs = enrol.get("certificates") if isinstance(enrol, Mapping) else None
    if isinstance(certs, list):
        out["certificate_to_clock"] = distribution(
            (float(c["latency_h"]) for c in certs
             if isinstance(c, Mapping) and isinstance(c.get("latency_h"), (int, float))),
            basis="FORWARD_ENROLMENT.json certificates[].latency_h: certified_at (the canon's "
                  "gated_at) -> the clock's first stamp, per certificate on a clock")
        out["certificate_to_clock"]["unstamped"] = sum(
            1 for c in certs if isinstance(c, Mapping)
            and not isinstance(c.get("latency_h"), (int, float)))
    else:
        out["certificate_to_clock"] = {"status": UNMEASURED,
                                       "why": f"{paths.enrolment.name} absent or carries no "
                                              "per-certificate rows"}
    out["unstamped_steps"] = {
        "idea_to_docket_file": (
            f"{UNMEASURED}: the judge's docket file (data/hypotheses/external_survivors.json) "
            "stamps each row `first_seen`, but it is ~440 MB on the box and is not streamed by "
            "an hourly leg; the registry queue (`docket_to_first_verdict`) is measured instead"),
        "first_verdict_of_a_cell_never_synced": (
            f"{UNMEASURED}: a ledger verdict whose cell the registry never synced has no "
            "`judged_at`, so its queue wait is invisible here"),
    }
    return out


# ------------------------------------------------------------------------------- the pass
def _ratio(num: Any, den: Any) -> float | None:
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)) or den <= 0:
        return None
    return round(float(num) / float(den), 4)


def cro_duties(reg: Mapping[str, Any], verdicts: Mapping[str, Any],
               certs: Mapping[str, Any], clocks: Mapping[str, Any],
               latency: Mapping[str, Any]) -> dict[str, Any]:
    """The CRO cycle's D5 and D6 metrics under the names docs/cro/CRO_CYCLE.md gives them, so the
    pass reads one block instead of re-deriving them. None is UNMEASURED, never zero."""
    v2c = latency.get("pass_to_certificate") or {}
    c2k = latency.get("certificate_to_clock") or {}
    lost_c = certs.get("lost") if isinstance(certs.get("lost"), Mapping) else None
    lost_k = clocks.get("lost") if isinstance(clocks.get("lost"), Mapping) else None
    pass_n = (verdicts.get("by_class") or {}).get("PASS")
    return {
        "D5": {"verdict_to_cert_hours": {"median": v2c.get("p50_h"), "p95": v2c.get("p95_h"),
                                         "n": v2c.get("n"), "status": v2c.get("status")},
               "cert_to_clock_hours": {"median": c2k.get("p50_h"), "p95": c2k.get("p95_h"),
                                       "n": c2k.get("n"), "status": c2k.get("status")},
               "passing_cells_without_cert": (sum(lost_c.values()) if lost_c is not None
                                              else None),
               "passing_cells_without_cert_unexplained": (lost_c or {}).get("UNEXPLAINED")
               if lost_c is not None else None,
               "certs_without_clock": (lost_k or {}).get("CLOCKLESS") if lost_k else None,
               "certs_not_accruing": (lost_k or {}).get("NOT_ACCRUING") if lost_k else None},
        "D6": {"conv_mined_to_judged": _ratio(reg.get("judged_in_registry"), reg.get("mined")),
               "conv_judged_to_cert": _ratio(certs.get("certified"),
                                             verdicts.get("cells_judged")),
               "conv_pass_to_cert": _ratio(certs.get("certified"), pass_n),
               "conv_cert_to_forward": _ratio(clocks.get("on_clock"),
                                              clocks.get("certificates")),
               "conv_ingested_to_mined": None, "conv_forward_to_live": None,
               "unmeasured_here": "ingested->mined is the ingestion ledger's; forward->live is "
                                  "the promoter's -- this funnel does not re-derive them"},
        "source": "docs/cro/CRO_CYCLE.md duties D5 and D6",
    }


def build(paths: Paths, conn: sqlite3.Connection | None, *, budget_s: float,
          now: datetime | None = None, banned: Iterable[str] | None = None) -> dict[str, Any]:
    t = now or _now()
    t0 = time.monotonic()
    reg = registry_stage(conn)
    # The stream gets what the budget leaves after a 10% write reserve.
    deadline = t0 + max(1.0, budget_s * 0.9 - (time.monotonic() - t0))
    stream = stream_ledger(paths.ledger, deadline=deadline,
                           since=t - timedelta(days=WINDOW_DAYS))
    verdicts = verdict_stage(stream)
    certs = certificate_stage(stream, paths, banned)
    clocks = clock_stage(paths, t)
    latency = latency_stage(conn, stream, paths, t)
    maxi = _read(paths.maximiser)
    debt = ((maxi.get("debt_after") or maxi.get("debt_before") or {})
            if isinstance(maxi, Mapping) else {})
    funnel = [
        {"stage": "mined", "n": reg.get("mined"), "source": "registry research_candidates"},
        {"stage": "testable_cell", "n": reg.get("testable_cells"),
         "lost": reg.get("lost_before_cell"),
         "lost_debt": (debt.get("components") if isinstance(debt, Mapping) else None)},
        {"stage": "judged", "n": verdicts.get("cells_judged"),
         "awaiting_judge_in_registry": reg.get("awaiting_judge"),
         "note": "ledger cells and registry candidates are different ids; both are published "
                 "and neither is subtracted from the other"},
        {"stage": "verdict", "by_class": verdicts.get("by_class"),
         "unknown_by_cause": (verdicts.get("by_subclass") or {}).get("UNKNOWN")},
        {"stage": "pass", "n": (verdicts.get("by_class") or {}).get("PASS")},
        {"stage": "certificate", "n": certs.get("certified"), "lost": certs.get("lost")},
        {"stage": "forward_clock", "n": clocks.get("on_clock"),
         "accruing": clocks.get("accruing"), "lost": clocks.get("lost")},
    ]
    return {"generated_utc": t.isoformat(timespec="seconds"), "organ": SEAT,
            "cro_duties": cro_duties(reg, verdicts, certs, clocks, latency),
            "pass_status": "PARTIAL" if stream.get("partial") else STAGE_COMPLETE,
            "budget_s": budget_s, "spent_s": round(time.monotonic() - t0, 2),
            "funnel": funnel, "registry": reg, "verdicts": verdicts,
            "certificates": certs, "clocks": clocks, "near_miss": near_miss_stage(paths),
            "latency": latency,
            "rule": "every row lost between two stages is counted with a named reason and an "
                    "owner; an unreadable stage is UNMEASURED, never zero; no gate moves"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--desk", type=Path, default=DESK)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    paths = Paths.at(a.desk)
    budget = effective_budget_s(a.budget_s)
    _atomic_write(paths.out, {"generated_utc": _now().isoformat(timespec="seconds"),
                              "organ": SEAT, "pass_status": "RUNNING", "budget_s": budget,
                              "note": "checkpoint written before the ledger stream; replaced "
                                      "when the pass completes"})
    conn: sqlite3.Connection | None = None
    try:
        from libs.moat import registry as R
        conn = R.connect()
        stop = time.monotonic() + budget * 0.4

        def _past_share() -> int:
            return 1 if time.monotonic() > stop else 0

        # The registry's reads may take 40% of the pass; past that they are
        # interrupted and the stage reads UNMEASURED with the reason, never a kill.
        conn.set_progress_handler(_past_share, 20_000)
    except Exception:
        conn = None
    try:
        doc = build(paths, conn, budget_s=budget)
    finally:
        if conn is not None:
            with contextlib.suppress(sqlite3.Error):
                conn.close()
    _atomic_write(paths.out, doc)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    v, c, k = doc["verdicts"], doc["certificates"], doc["clocks"]
    print(f"conversion funnel: mined {doc['registry'].get('mined')} -> cells "
          f"{doc['registry'].get('testable_cells')} -> judged {v.get('cells_judged')} "
          f"{v.get('by_class')} -> certified {c.get('certified')} of {c.get('passes')} PASS "
          f"(lost {c.get('lost')}) -> on clock {k.get('on_clock')}, accruing {k.get('accruing')}")
    print(f"  UNKNOWN share {v.get('unknown_share')} (7d {v.get('window_unknown_share')}); "
          f"build/data {v.get('unknown_build_or_data')} = {v.get('unknown_build_or_data_share')} "
          f"of UNKNOWN; pass {doc['pass_status']} in {doc['spent_s']}s -> {paths.out}")
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
