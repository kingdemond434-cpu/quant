"""JUDGE REACH -- every producer whose ideas are emitted but never judged, named every hour.

THE ORDER (principal, 2026-11-25): "everything must always reach judge if it's meant to in the
first place." Measured the same day on the trading box: 28 sandbox generators held ~29.4k rows,
all judged, none surviving -- and the sampled row was judged on the family's DEFAULTS because its
rule was prose and its params empty. So "reached the judge" has two halves, and this guardian
checks both, for EVERY producer, not one lane:

    REACH     emitted -> received -> judged. A producer with emitted > 0 and judged == 0 after
              GRACE_H, or an emitted -> received loss above LOSS_TOL that no named reason
              explains, is LEAKING, with the stage and the reason.
    GENUINE   of the rows that WERE judged, how many carried an executable rule. A producer whose
              sampled judged rows are at least NOT_GENUINE_SHARE prose-only or defaults-only is
              PROSE_ONLY / DEFAULTS_ONLY: it occupies judge slots without its own rule reaching
              the judge (research/family_spec.py is the reading).

IT IS BUILT ON THE PRODUCER LOOP'S FUNNEL, NOT A PARALLEL CENSUS. The per-producer stages come
from `reports/PRODUCER_CONVERSION.json` (read through `producer_loop._conversion_rows`, the same
reader the loop uses: candidates, docket, judged by exact cell identity, certificates) and the
loop's own `reports/PRODUCER_LOOP.json` funnel and stage of death ride along on every row. What
this adds is the RECEIVED stage and its named losses (one grouped, read-only registry query) and
the genuineness sample. The sandbox runner's own lifetime handoff (`rows_emitted`,
`rows_enqueued`, `not_executable_by_reason`, `enqueue_errors`) names the losses before the
registry for the sandbox lane.

VERDICTS: REACHING / LEAKING (stage + reason) / PROSE_ONLY / DEFAULTS_ONLY / NOTHING_EMITTED /
UNMEASURED. A missing input is UNMEASURED, never a pass (L1.28a).

PAGING. A producer newly LEAKING / PROSE_ONLY / DEFAULTS_ONLY, and again every REPAGE_H while it
stays so, lands on the desk event log as one PLUMBING_DEFECT -- the surface the alert relay hands
to Claude (ops/alert_feed.py, invariant I5). Never the principal's phone; never a status change,
a gate, a trial count or a producer edit: this module writes only its own files and the event.

    python desks/mt5/research/judge_reach.py            # one pass (hourly leg `judge_reach`)
    python desks/mt5/research/judge_reach.py --no-page  # measure and write, page nothing
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import family_spec as FS  # noqa: E402
from research import producer_loop as PL  # noqa: E402

OUT = DESK / "reports" / "JUDGE_REACH.json"
STATE = DESK / "data" / "judge_reach_state.json"
EVENTS = DESK / "data" / "events.jsonl"
SANDBOX_STATE = DESK / "data" / "sandbox_runner_state.json"
LOOP_REPORT = PL.OUT
REGISTRY = PL.REGISTRY

UNMEASURED = "UNMEASURED"
REACHING = "REACHING"
LEAKING = "LEAKING"
NOTHING_EMITTED = "NOTHING_EMITTED"
PAGED_VERDICTS = (LEAKING, FS.PROSE_ONLY, FS.DEFAULTS_ONLY)

#: A producer that has emitted for this long with nothing judged is LEAKING, not "early".
GRACE_H = 24.0
#: The window over which emitted/received/judged deltas are reported (and a stall is read).
WINDOW_H = 72.0
#: Snapshots older than this are pruned; one is kept per SNAPSHOT_EVERY_H.
SNAPSHOT_KEEP_H = 8 * 24.0
SNAPSHOT_EVERY_H = 1.0
#: An emitted -> received loss above this share, with no named reason covering it, is a leak.
LOSS_TOL = 0.5
#: Genuineness: at least this many judged rows sampled, and this share non-genuine, to flag.
MIN_QUALITY_SAMPLE = 20
NOT_GENUINE_SHARE = 0.9
SAMPLE_PER_PRODUCER = 400
MAX_QUALITY_ROWS = 300_000
#: Re-page a producer that stays flagged after this long; never once per hourly pass.
REPAGE_H = 24.0
MAX_NAMES_PER_PAGE = 40
DEFAULT_BUDGET_S = 300.0

#: Registry statuses that mean "past the judge's door" (certificate_provenance.conversion).
DOOR = ("donated", "claimed", "judged", "retired", "survived")
#: Losses that are DEFECTS even though they have a name: they never reach a judge and nobody
#: chose that. Every other named reason is a declared disposition.
DEFECT_REASONS = frozenset({"ENQUEUE_ERROR", "UNNAMED"})


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


# ------------------------------------------------------------------------------ the registry

def received_census(db: Path | None = None, *, deadline: float | None = None
                    ) -> dict[str, Any]:
    """Per producer: rows in the registry, rows RECEIVED by the docket, and every other row by
    its named reason. Received = past the judge's door, or queued with the executable identity
    (symbol + family) that `libs/moat/docket_feed` carries into the merged docket every pass."""
    db = db or REGISTRY
    if not db.exists():
        return {"available": False, "why": f"{UNMEASURED}: no registry at {db.as_posix()}"}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        return {"available": False, "why": f"{UNMEASURED}: registry unopenable ({exc})"}
    per: dict[str, dict[str, Any]] = {}
    try:
        cols = {str(r[1]) for r in con.execute("PRAGMA table_info(research_candidates)")}
        if "producer" not in cols:
            return {"available": False,
                    "why": f"{UNMEASURED}: research_candidates has no producer stamp"}
        judged = ("coalesce(judged_at,'') != ''" if "judged_at" in cols else "0")
        q = ("SELECT lower(coalesce(nullif(producer,''),'')), lower(coalesce(status,'')), "  # noqa: S608
             "(coalesce(symbol,'') != '' AND coalesce(family,'') != ''), "
             f"({judged}), count(*) FROM research_candidates GROUP BY 1,2,3,4")
        for who, status, ident, was_judged, n in con.execute(q):
            if deadline is not None and time.monotonic() > deadline:
                return {"available": False, "why": f"{UNMEASURED}: registry budget ran out"}
            name = PL._norm(who) or "unattributable"
            p = per.setdefault(name, {"enqueued": 0, "received": 0, "lost": Counter()})
            n = int(n or 0)
            p["enqueued"] += n
            if was_judged or status in DOOR or (status == "queued" and ident):
                p["received"] += n
            elif status == "queued":
                p["lost"]["NO_SYMBOL_OR_FAMILY"] += n
            elif status:
                p["lost"][f"STATUS:{status}"] += n
            else:
                p["lost"]["UNNAMED"] += n
    except sqlite3.Error as exc:
        return {"available": False, "why": f"{UNMEASURED}: registry query failed ({exc})"}
    finally:
        con.close()
    return {"available": True, "producers": per}


def quality_sample(db: Path | None = None, *, deadline: float | None = None) -> dict[str, Any]:
    """Per producer: of its newest judged rows, how many carried an executable rule."""
    db = db or REGISTRY
    if not db.exists():
        return {"available": False, "why": f"{UNMEASURED}: no registry at {db.as_posix()}"}
    per: dict[str, Counter[str]] = {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
        try:
            cols = {str(r[1]) for r in con.execute("PRAGMA table_info(research_candidates)")}
            if "producer" not in cols:
                return {"available": False,
                        "why": f"{UNMEASURED}: research_candidates has no producer stamp"}
            prose = "exact_rules" if "exact_rules" in cols else "''"
            where = ("coalesce(judged_at,'') != '' OR lower(coalesce(status,'')) = 'judged'"
                     if "judged_at" in cols else "lower(coalesce(status,'')) = 'judged'")
            cur = con.execute(
                f"SELECT lower(coalesce(nullif(producer,''),'')), family, params_json, "  # noqa: S608
                f"{prose} FROM research_candidates WHERE {where} ORDER BY seq DESC LIMIT ?",
                (MAX_QUALITY_ROWS,))
            for n, (who, fam, pj, text) in enumerate(cur, 1):
                if deadline is not None and n % 20_000 == 0 and time.monotonic() > deadline:
                    break
                name = PL._norm(who) or "unattributable"
                c = per.setdefault(name, Counter())
                if sum(c.values()) >= SAMPLE_PER_PRODUCER:
                    continue
                c[FS.judged_quality(fam, pj, text)] += 1
        finally:
            con.close()
    except sqlite3.Error as exc:
        return {"available": False, "why": f"{UNMEASURED}: registry unreadable ({exc})"}
    return {"available": True, "producers": per}


# ------------------------------------------------------------------------- the sandbox handoff

def sandbox_handoff(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """`sandbox:<id>` -> {emitted, enqueued, lost by reason} from the runner's lifetime rows."""
    doc = PL._read(path or SANDBOX_STATE, {}) or {}
    systems = doc.get("systems") if isinstance(doc, dict) else None
    out: dict[str, dict[str, Any]] = {}
    for sid, s in (systems or {}).items():
        if not isinstance(s, dict) or "rows_emitted" not in s:
            continue
        lost = Counter({str(k): int(v or 0) for k, v in
                        (s.get("not_executable_by_reason") or {}).items() if int(v or 0)})
        if int(s.get("enqueue_errors") or 0):
            lost["ENQUEUE_ERROR"] += int(s["enqueue_errors"])
        out[PL._norm(f"sandbox:{sid}")] = {"emitted": int(s.get("rows_emitted") or 0),
                                           "enqueued": int(s.get("rows_enqueued") or 0),
                                           "lost": lost}
    return out


# ------------------------------------------------------------------------------- the verdict

def _window(snaps: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """The snapshot closest to WINDOW_H ago (at least that old), or None."""
    cut = now - timedelta(hours=WINDOW_H)
    old = [s for s in snaps if (PL._parse(s.get("at")) or now) <= cut]
    return old[-1] if old else None


def verdict(row: dict[str, Any], *, first_seen: datetime | None, now: datetime,
            base: dict[str, Any] | None) -> dict[str, Any]:
    """REACH and GENUINE for one producer row (mutates and returns it)."""
    emitted, received, judged = row["emitted"], row["received"], row["judged"]
    if not isinstance(judged, int) or not isinstance(emitted, int):
        row.update(verdict=UNMEASURED, stage=None,
                   reason="the conversion table does not measure this producer's judged stage")
        return row
    if emitted <= 0:
        row.update(verdict=NOTHING_EMITTED, stage=None,
                   reason="no row meant for the judge was emitted; liveness is producer_loop's")
        return row
    aged = first_seen is not None and now - first_seen >= timedelta(hours=GRACE_H)
    lost = row.get("lost_by_reason") or {}
    defects = sum(v for k, v in lost.items() if k in DEFECT_REASONS)
    named = sum(v for k, v in lost.items() if k not in DEFECT_REASONS)
    rec = received if isinstance(received, int) else None
    unexplained = max(0, emitted - (rec or 0) - named) if rec is not None else None
    if judged == 0 and aged:
        row.update(verdict=LEAKING, stage="JUDGE",
                   reason=(f"{emitted} row(s) emitted for {GRACE_H:g}h+ and none judged "
                           f"({rec if rec is not None else UNMEASURED} received)"))
        return row
    if aged and unexplained is not None and (defects + unexplained) > LOSS_TOL * emitted:
        top = ", ".join(f"{k} {v}" for k, v in sorted(lost.items(), key=lambda kv: -kv[1])[:4]
                        if k in DEFECT_REASONS)
        row.update(verdict=LEAKING, stage="RECEIVE",
                   reason=(f"{defects + unexplained} of {emitted} emitted row(s) lost before the "
                           f"docket without a declared reason"
                           + (f" ({top})" if top else "")))
        return row
    if base is not None and isinstance(base.get("judged"), int) and isinstance(
            base.get("emitted"), int):
        d_emit, d_judged = emitted - base["emitted"], judged - base["judged"]
        row["window"] = {"since": base.get("at"), "emitted": d_emit, "judged": d_judged,
                         "received": (received - base["received"]
                                      if isinstance(received, int)
                                      and isinstance(base.get("received"), int) else UNMEASURED)}
        if d_emit > 0 and d_judged <= 0 and judged > 0:
            row.update(verdict=LEAKING, stage="JUDGE",
                       reason=(f"{d_emit} row(s) emitted since {base.get('at')} and none judged: "
                               f"the producer's rows stopped reaching the judge"))
            return row
    q = row.get("judged_quality") or {}
    sampled = sum(int(v) for k, v in q.items() if k != UNMEASURED)
    bad = {k: int(q.get(k) or 0) for k in (FS.PROSE_ONLY, FS.DEFAULTS_ONLY)}
    if sampled >= MIN_QUALITY_SAMPLE and sum(bad.values()) >= NOT_GENUINE_SHARE * sampled:
        which = max(bad, key=lambda k: (bad[k], k))
        row.update(verdict=which, stage="JUDGE",
                   reason=(f"{sum(bad.values())} of {sampled} sampled judged row(s) carry no "
                           f"executable rule ({bad[FS.PROSE_ONLY]} prose-only, "
                           f"{bad[FS.DEFAULTS_ONLY]} defaults-only): the judge scored the "
                           f"family's defaults, not this producer's rule"))
        return row
    if judged == 0:
        row.update(verdict=REACHING, stage=None,
                   reason=f"inside the {GRACE_H:g}h grace: emitted, not yet judged")
        return row
    row.update(verdict=REACHING, stage=None, reason="")
    return row


def build(*, now: datetime | None = None, budget_s: float | None = None,
          db: Path | None = None) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    budget = float(budget_s if budget_s is not None
                   else os.environ.get("QUANT_LEG_BUDGET_S") or DEFAULT_BUDGET_S)
    deadline = t0 + budget * 0.85
    conv = PL._conversion_rows()
    loop = PL._read(LOOP_REPORT, {}) or {}
    loop_rows = {PL._norm(r.get("producer")): r for r in (loop.get("producers") or [])
                 if isinstance(r, dict) and r.get("producer")}
    rec = received_census(db, deadline=deadline)
    qual = quality_sample(db, deadline=deadline)
    sbx = sandbox_handoff()
    state = PL._read(STATE, {}) or {}
    first_seen: dict[str, str] = dict(state.get("first_emitting") or {})
    snaps: dict[str, list[dict[str, Any]]] = {k: list(v) for k, v in
                                              (state.get("snapshots") or {}).items()}
    rec_p = rec.get("producers") or {} if rec.get("available") else {}
    q_p = qual.get("producers") or {} if qual.get("available") else {}
    names = sorted((set(conv) | set(rec_p) | set(sbx)) - {""})
    rows: list[dict[str, Any]] = []
    for name in names:
        c = conv.get(name) or {}
        r = rec_p.get(name)
        s = sbx.get(name)
        enq = PL._int(c.get("candidates")) if c else (r or {}).get("enqueued")
        emitted = max(enq or 0, s["emitted"] if s else 0) if (c or r or s) else None
        lost: Counter[str] = Counter()
        if r:
            lost.update(r["lost"])
        if s:
            lost.update(s["lost"])
            # emitted by the system but neither enqueued nor named: an unnamed pre-registry loss
            gap = s["emitted"] - s["enqueued"] - sum(s["lost"].values())
            if gap > 0:
                lost["UNNAMED"] += gap
        received: int | str = UNMEASURED
        if r is not None:
            received = int(r["received"])
            if c and isinstance(PL._int(c.get("docket")), int):
                received = max(received, int(PL._int(c.get("docket")) or 0))
        elif c and isinstance(PL._int(c.get("docket")), int):
            received = int(PL._int(c.get("docket")) or 0)
        judged = PL._int(c.get("judged")) if c else None
        lp = loop_rows.get(name) or {}
        row: dict[str, Any] = {
            "producer": name,
            "emitted": emitted if emitted is not None else UNMEASURED,
            "received": received,
            "judged": judged if judged is not None else UNMEASURED,
            "discoveries": PL._int(c.get("discoveries")) if c else UNMEASURED,
            "certificates": PL._int(c.get("certificates")) if c else UNMEASURED,
            "lost_by_reason": dict(lost),
            "judged_quality": dict(q_p.get(name) or {}) if qual.get("available") else UNMEASURED,
            "producer_loop": {"status": lp.get("status") or UNMEASURED,
                              "stage_of_death": lp.get("stage_of_death"),
                              "funnel": lp.get("funnel") or UNMEASURED},
        }
        if s:
            row["sandbox_handoff"] = {"emitted": s["emitted"], "enqueued": s["enqueued"]}
        if isinstance(emitted, int) and emitted > 0 and name not in first_seen:
            first_seen[name] = _iso(now)
        hist = snaps.get(name, [])
        verdict(row, first_seen=PL._parse(first_seen.get(name)), now=now,
                base=_window(hist, now))
        row["first_emitting_seen"] = first_seen.get(name)
        last = PL._parse(hist[-1].get("at")) if hist else None
        if last is None or now - last >= timedelta(hours=SNAPSHOT_EVERY_H):
            hist.append({"at": _iso(now), "emitted": row["emitted"], "received": received,
                         "judged": row["judged"]})
        cut = now - timedelta(hours=SNAPSHOT_KEEP_H)
        snaps[name] = [x for x in hist if (PL._parse(x.get("at")) or now) >= cut]
        rows.append(row)
    order = {LEAKING: 0, FS.PROSE_ONLY: 1, FS.DEFAULTS_ONLY: 2, UNMEASURED: 3, REACHING: 4,
             NOTHING_EMITTED: 5}
    rows.sort(key=lambda x: (order.get(x["verdict"], 9), x["producer"]))
    census = Counter(x["verdict"] for x in rows)
    doc = {
        "generated_at": _iso(now),
        "law": ("Everything meant for the judge reaches it, as the rule its producer proposed: "
                "per producer, emitted > received > judged with every loss named, and the "
                "judged rows sampled for an executable rule. A missing input is UNMEASURED."),
        "inputs": {"conversion": "READ" if conv else f"{UNMEASURED}: {PL.CONVERSION.name}",
                   "producer_loop": "READ" if loop_rows else f"{UNMEASURED}: {LOOP_REPORT.name}",
                   "registry_received": "READ" if rec.get("available") else rec.get("why"),
                   "registry_quality": "READ" if qual.get("available") else qual.get("why"),
                   "sandbox_handoff": "READ" if sbx else f"{UNMEASURED}: {SANDBOX_STATE.name}"},
        "thresholds": {"grace_h": GRACE_H, "window_h": WINDOW_H, "loss_tol": LOSS_TOL,
                       "min_quality_sample": MIN_QUALITY_SAMPLE,
                       "not_genuine_share": NOT_GENUINE_SHARE, "repage_h": REPAGE_H},
        "census": dict(census),
        "summary": {"n_producers": len(rows), "n_reaching": census.get(REACHING, 0),
                    "n_leaking": census.get(LEAKING, 0),
                    "n_not_genuine": census.get(FS.PROSE_ONLY, 0)
                    + census.get(FS.DEFAULTS_ONLY, 0),
                    "n_unmeasured": census.get(UNMEASURED, 0)},
        "flagged": [{"producer": x["producer"], "verdict": x["verdict"], "stage": x["stage"],
                     "reason": x["reason"]} for x in rows if x["verdict"] in PAGED_VERDICTS],
        "producers": rows,
        "budget_s": budget, "elapsed_s": round(time.monotonic() - t0, 2),
    }
    doc["_state"] = {"first_emitting": first_seen, "snapshots": snaps,
                     "paged": dict(state.get("paged") or {})}
    return doc


def due_pages(doc: dict[str, Any], paged: dict[str, str], now: datetime
              ) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """(flags due a page now, the new paged memory). Page on change, re-page every REPAGE_H."""
    keep: dict[str, str] = {}
    due: list[dict[str, Any]] = []
    for f in doc.get("flagged") or []:
        key = f"{f['producer']}|{f['verdict']}|{f.get('stage')}"
        last = PL._parse(paged.get(key))
        if last is None or now - last >= timedelta(hours=REPAGE_H):
            due.append(f)
            keep[key] = _iso(now)
        else:
            keep[key] = paged[key]
    return due, keep


def write(doc: dict[str, Any], *, page: bool = True, out: Path | None = None,
          now: datetime | None = None, events: Path | None = None) -> dict[str, Any]:
    now = now or PL._parse(doc.get("generated_at")) or _now()
    st = doc.pop("_state", {})
    due, paged = due_pages(doc, dict(st.get("paged") or {}), now)
    doc["paged_this_pass"] = [f["producer"] for f in due] if page else []
    if page and due:
        try:
            from libs.ops import events as _ev
            names = ", ".join(f"{f['producer']} ({f['verdict']}"
                              + (f"@{f['stage']}" if f.get("stage") else "") + ")"
                              for f in due[:MAX_NAMES_PER_PAGE])
            _ev.emit("PLUMBING_DEFECT", events or EVENTS, organ="judge_reach",
                     defect="JUDGE_REACH", artifact=(out or OUT).relative_to(ROOT).as_posix()
                     if (out or OUT).is_relative_to(ROOT) else str(out or OUT),
                     detail=(f"{len(due)} producer(s) not genuinely reaching the judge: "
                             f"{names}")[:600],
                     producer="judge_reach", priority=2)
        except Exception as exc:          # the report still names every flag
            doc["page_error"] = f"{type(exc).__name__}: {exc}"
    PL._atomic(out or OUT, doc)
    if page:
        st["paged"] = paged
    PL._atomic(STATE, {**st, "at": doc["generated_at"]})
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--no-page", action="store_true", help="measure and write; page nothing")
    a = ap.parse_args(argv)
    doc = write(build(budget_s=a.budget_s), page=not a.no_page)
    print(f"judge_reach: {doc['summary']['n_producers']} producer(s) {doc['census']}; "
          f"paged {len(doc['paged_this_pass'])} -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
