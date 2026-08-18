#!/usr/bin/env python3
"""RECOMMENDATION LEDGER (§42, principal 2026-07-26) -- nothing recommended is ever forgotten.

THE HOLE. track_findings.py governs PANEL findings only (model / summary / accepted-or-rejected).
Everything else this desk produces a recommendation from -- max_audit defects, the weekly deep cold
audit, cycle reports, the proactive battery, external reviews -- had no ledger and no forced
disposition. A deep sweep could name eight high-ROI improvements, the report gets written, the
window closes, and by the next Sunday nobody knows they existed. That is the same class as the
findings hole it was built to close, one layer up.

THE LAW. Every recommendation gets exactly one row, and every row must reach a DISPOSITION:
IMPLEMENTED (with a commit), REJECTED (with a real reason), or SCHEDULED (with a due date that is
itself enforced). "No decision" is not a state a row may rest in -- an undisposed row past its
grace window is a DEFECT, not backlog. Rejection is always available and is a legitimate answer,
because the principal's instruction is that nothing is SKIPPED, not that everything is BUILT: a
reasoned no is a decision, silence is the failure.

WHY IT CANNOT BE GAMED. Rows are never deleted and dispositions never revert to none, so the
cheap escape -- quietly dropping an inconvenient row -- is closed the same way the mining ratchet
closes shrinking the denominator. A rejection needs a substantive reason (a bare "no" is refused
at the CLI), and a SCHEDULED row that passes its due date fires exactly like an orphan, so
"scheduled" cannot become a place recommendations go to die.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
# `python3 scripts/recommendations.py` puts scripts/ on sys.path[0], NOT the repo root, so `libs`
# is unimportable however sound the code is. The L1.29 hook's refusal path caught this on its first
# live call and printed rather than swallowed -- which is the only reason it was a one-line fix and
# not a permanently silent no-op wearing a green tick.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.ops.deferral import is_chronic, record_reschedule  # noqa: E402

LEDGER = ROOT / "docs/research/recommendation_ledger.json"

# A recommendation may sit undisposed for one cycle -- long enough to be triaged in the next
# organ run, short enough that it cannot quietly become permanent.
#
# L1.48 EXEMPTION CLAIMED, AND IT IS THE NARROW ONE. `GRACE_H` is not an evidence clock and never
# was: it is the DUTY horizon -- how long a row may rest before someone owes it a decision -- and
# duty is denominated in wall-clock because the principal reads a dashboard in wall-clock. It is
# deliberately NOT the SKIP test. Elapsed hours cannot distinguish a row nobody would look at from
# a row nobody DID look at, and conflating them is what welded this fence shut (see `owed`).
GRACE_H = 24.0
SWEEPS = ROOT / "data/carryover_sweeps.jsonl"
# The §37 bar, borrowed verbatim rather than re-invented: shown to a LIVE cycle at least twice in a
# row and still open. Two organs measure this one backlog and only one of them had this discipline.
SKIP_SWEEPS = 2
_TERMINAL = ("implemented", "rejected")
_MIN_REASON = 25          # a bare "no" / "wontfix" is not a disposition


def _load() -> dict[str, Any]:
    if LEDGER.exists():
        try:
            loaded: dict[str, Any] = json.loads(LEDGER.read_text("utf-8"))
            return loaded
        except Exception as e:
            # A corrupt ledger must NEVER read as empty-healthy: `report` would print
            # "0 total, nothing overdue" and the next _save would atomically replace
            # every row with the empty dict -- the mass-deletion the ledger law forbids.
            # Observed live 2026-07-31: merge-conflict markers committed to origin read
            # here as a clean empty ledger. Refuse loudly; git history repairs it.
            raise SystemExit(
                f"REFUSING: {LEDGER} exists but cannot be parsed ({e}); repair it from "
                "git history -- an unreadable ledger must never become an empty one") from e
    return {"recommendations": []}


def _save(d: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".json.tmp")
    # ensure_ascii=False IS LOAD-BEARING, not cosmetic (R0368). ~60 of the escapes this used to
    # emit were CJK: the Chinese search operators the non-English mining rows are ABOUT. As
    # `韭菜` a reviewer cannot read the row and -- the half that costs something -- no
    # grep for 韭菜 can find it, so a term already mined returns a clean zero and reads as
    # unexplored ground. That is the false-exhaustion mode L1.11a exists to prevent, arriving
    # through the serializer. Every consumer goes through json.loads and is indifferent.
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), "utf-8")
    tmp.replace(LEDGER)          # atomic: a torn ledger would lose the very rows it protects


def _age_h(iso: str) -> float:
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 3600.0
    except Exception:
        return 0.0


def _next_id(d: dict) -> str:
    """Allocate past BOTH the local ledger and the last-fetched origin/master copy (R0152).

    Count-based allocation minted the same id on two boxes three times on 2026-07-31
    (R0135-37, R0143, R0144): each box counts its own rows, so concurrent sessions collide
    and every merge renumbers rows and repoints code comments. Max-known-id with origin
    consulted (git show reads the fetched ref -- no network) shrinks the race window from
    all-day to since-last-fetch; an unreadable origin falls back to the local max, which
    still never re-mints an id a renumber has already retired.
    """
    import re
    import subprocess
    nums = [int(m.group(1)) for r in d["recommendations"]
            if (m := re.match(r"R(\d+)$", str(r.get("id", ""))))]
    try:
        remote = subprocess.run(
            ["git", "show", "origin/master:docs/research/recommendation_ledger.json"],
            capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).resolve().parent.parent)
        if remote.returncode == 0:
            nums += [int(x) for x in re.findall(r'"id":\s*"R(\d+)"', remote.stdout)]
    except (OSError, subprocess.SubprocessError):
        pass                                   # offline clone: local max still monotonic
    return f"R{(max(nums) if nums else 0) + 1:04d}"


def _forecast_add(rid: str, rows: list) -> dict | None:
    """Pre-register the L1.29 forecast for a new row. NEVER fatal to the ledger write.

    The ledger is the organ; the calibration hook is instrumentation ON it. If the forecast log is
    unwritable, the recommendation must still be ledgered -- losing a row to a broken side-effect
    would trade the thing §42 exists to guarantee for the thing measuring it. The failure is
    printed, not swallowed (L2.4): a silent except here would make an unwritable forecast log look
    exactly like a healthy one.
    """
    try:
        from libs.research.recommendation_forecast import on_add
        return on_add(rid, rows)
    except (ImportError, OSError, ValueError, KeyError, TypeError) as e:
        print(f"  WARNING: L1.29 forecast not logged for {rid}: {type(e).__name__}: {e}")
        return None


def _settle_forecasts(rows: list) -> None:
    """Grade every past-due `rec:*` forecast. Runs on EVERY invocation of this CLI.

    Cheap (one small JSON read) and unconditional, because the alternative is a cron line that can
    silently stop -- and an ungraded forecast inflates the desk's apparent hit-rate by never
    counting its misses. This CLI is invoked constantly, so hanging the resolver off it makes the
    forecasts self-closing by construction rather than by schedule.
    """
    try:
        from libs.research.recommendation_forecast import settle
        done = settle(rows)
    except (ImportError, OSError, ValueError, KeyError, TypeError) as e:
        print(f"  WARNING: L1.29 forecasts not settled: {type(e).__name__}: {e}")
        return
    if done:
        hit = sum(1 for x in done if x["outcome"])
        print(f"  L1.29: graded {len(done)} past-due forecast(s) -- {hit} implemented, "
              f"{len(done) - hit} not")


def add(a: argparse.Namespace) -> None:
    d = _load()
    # DEDUPE on (source, summary): organs re-read the same audit report every cycle, and a ledger
    # that grows a duplicate row per read becomes noise nobody triages -- which is the failure it
    # exists to prevent, arriving by a different route.
    for r in d["recommendations"]:
        if r["source"] == a.source and r["summary"].strip() == a.summary.strip():
            print(f"{r['id']} already ledgered ({r['status']})")
            return
    # R0477 tripwire: every value ever observed in the rank-wearing-bps population was >= 7500,
    # while the largest MEASURED estimate on the ledger is 400. A four-digit "bps" is an ordinal.
    if a.roi_bps is not None and a.roi_bps >= 1000:
        raise SystemExit(
            f"--roi-bps {a.roi_bps:g} refused: bps that size are rank ordinals wearing a bps "
            "label (R0477's 9999/9000/8000 population). Use --rank for ordering; --roi-bps "
            "carries a MEASURED return estimate only.")
    rank = getattr(a, "rank", None)
    basis = "measured" if a.roi_bps is not None else ("rank" if rank is not None else None)
    rid = _next_id(d)
    d["recommendations"].append({
        "id": rid, "source": a.source, "summary": a.summary,
        "roi_bps": a.roi_bps, "rank": rank, "roi_basis": basis,
        "raised": datetime.now(tz=UTC).isoformat(),
        "status": "open", "reason": None, "commit": None, "due": None, "disposed": None})
    _save(d)
    print(f"{rid} ledgered from {a.source} -- OPEN, disposition owed within {GRACE_H:.0f}h")
    fx = _forecast_add(rid, d["recommendations"])
    if fx:
        print(f"  L1.29 forecast {fx['key']} p={fx['p']} [{fx['provenance']}] "
              f"resolve_by {fx['resolve_by'][:10]}")


def dispose(a: argparse.Namespace) -> None:
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if row["status"] in _TERMINAL:
        raise SystemExit(f"{a.id} is already {row['status']} -- dispositions do not revert. "
                         "If it was MISFILED, use `correct --id --reason`, which logs the "
                         "reversal in the row history rather than erasing it.")
    # GUARD AGAINST DISPOSING THE WRONG ROW (2026-07-26): ids are assigned by count, so a
    # concurrent writer -- the weekly sweep ledgering seven rows mid-session -- shifts the id
    # a caller assumed. --expect makes the caller name what it thinks it is deciding.
    if a.expect and a.expect.lower() not in row["summary"].lower():
        raise SystemExit(
            f"{a.id} does not match --expect {a.expect!r}. Its summary is:\n  "
            f"{row['summary'][:200]}\nAnother writer may have taken the id you assumed.")
    if a.status == "rejected" and len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(
            f"a rejection needs a real reason (>={_MIN_REASON} chars). The principal's "
            "standard is that nothing is SKIPPED, not that everything is built -- a "
            "reasoned no is a decision, a bare no is silence wearing a label.")
    if a.status == "scheduled" and not a.due:
        raise SystemExit("a scheduled recommendation needs --due YYYY-MM-DD, else 'scheduled' "
                         "becomes the place recommendations go to die")
    if a.status == "implemented" and not a.commit:
        raise SystemExit("an implemented recommendation needs --commit: the desk's standing rule "
                         "is that an artifact proves the work, never a claim")
    # RE-SCHEDULING A ROW IS A DEFERRAL, AND A DEFERRAL THAT LEAVES NO TRACE IS A SKIP (L1.60).
    # This file's docstring claims "scheduled" cannot become where rows go to die because an
    # overdue schedule fires like an orphan -- true, unless the due date moves first, which this
    # very function did in place with no history and no counter. Measured over the ledger's
    # first-parent git history 2026-08-13: 39 of 152 ever-scheduled rows (26%) were given more
    # than one distinct due date and 38 of them are STILL scheduled -- they never converted, they
    # only moved. See libs/ops/deferral.py for the census and why it had to come from git.
    #
    # DEFERRING AGAIN STAYS FULLY AVAILABLE -- a row blocked on Gate 0 or a forward clock is not
    # repair debt, and forcing it terminal would manufacture a false rejection. What is refused is
    # deferring INVISIBLY: say what changed, and the move is recorded rather than erased.
    if a.status == "scheduled" and row["status"] == "scheduled":
        if len((a.reason or "").strip()) < _MIN_REASON:
            raise SystemExit(
                f"{a.id} is already scheduled (due {row.get('due')}) -- moving that date is a "
                f"DEFERRAL and needs --reason (>={_MIN_REASON} chars) naming what changed. "
                "Re-scheduling is always available; doing it silently is not, because a row "
                "snoozed for the fourth time and a row scheduled once are otherwise identical.")
        record_reschedule(row, a.reason)
    row.update(status=a.status, reason=a.reason, commit=a.commit, due=a.due,
               disposed=datetime.now(tz=UTC).isoformat())
    _save(d)
    print(f"{a.id} -> {a.status.upper()}")


def correct(a: argparse.Namespace) -> None:
    """Reverse a MIS-ENTERED disposition, permanently logging that it happened.

    "Dispositions never revert" is the right guard against gaming and the wrong one against error:
    it made an honest mis-entry unfixable. What actually prevents laundering is not immovability
    but VISIBILITY -- a correction keeps the original disposition, its reason, and the reason it
    was wrong in the row's own history, so the record reads as "decided, then found misfiled",
    never as "never decided". Corrections are cheap to audit and impossible to hide.
    """
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if row["status"] == "open":
        raise SystemExit(f"{a.id} is already open -- nothing to correct")
    if len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(f"a correction needs a real reason (>={_MIN_REASON} chars): what was "
                         "misfiled, and why the original disposition did not apply to this row")
    row.setdefault("corrections", []).append({
        "was": row["status"], "was_reason": row.get("reason"),
        "was_commit": row.get("commit"), "was_due": row.get("due"),
        "corrected": datetime.now(tz=UTC).isoformat(), "why": a.reason})
    row.update(status="open", reason=None, commit=None, due=None, disposed=None)
    _save(d)
    print(f"{a.id} corrected -> OPEN (prior disposition kept in its history); "
          "a fresh disposition is now owed")


def repoint(a: argparse.Namespace) -> None:
    """Re-point a disposition's --commit at the commit that actually carries the work (R0369).

    WHY `correct` IS THE WRONG VERB FOR THIS. A rebase rewrites SHAs -- and this branch gets
    rebased whenever a sibling pushes to it -- so a citation written honestly this morning can
    name an orphaned object by tonight. `correct` re-OPENS the row and files the prior
    disposition as MISFILED, which is a lie about what happened: the decision was right and only
    the pointer moved. Recording it as a misfiling would corrupt the correction history that
    verb exists to protect, so the two are kept distinct.

    WHAT THIS MAY NOT BECOME. It mutates the commit field and NOTHING else -- never the status,
    never the reason. And it refuses a new citation that does not resolve to a real commit
    object, because a verb that laundered one unresolvable pointer into another would give the
    ledger a way to look repaired while proving nothing. Every repoint is appended to the row's
    `repoints` list with its reason, so the old pointer stays readable forever.
    """
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if a.expect and a.expect.lower() not in row["summary"].lower():
        raise SystemExit(
            f"{a.id} does not match --expect {a.expect!r}. Its summary is:\n  "
            f"{row['summary'][:200]}\nAnother writer may have taken the id you assumed.")
    if row["status"] != "implemented":
        raise SystemExit(f"{a.id} is {row['status']}, not implemented -- only an implemented "
                         "row cites a commit, so there is no pointer to move")
    if len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(f"a repoint needs a real reason (>={_MIN_REASON} chars): why the old "
                         "citation stopped resolving, and how the new one was identified")
    import subprocess
    try:
        p = subprocess.run(["git", "rev-parse", "--verify", f"{a.commit}^{{commit}}"],
                           capture_output=True, text=True, timeout=30, cwd=ROOT)
    except (OSError, subprocess.SubprocessError) as e:
        raise SystemExit(f"cannot verify {a.commit}: {type(e).__name__}: {e}") from e
    if p.returncode != 0:
        raise SystemExit(
            f"REFUSING: {a.commit!r} does not resolve to a commit in this clone. Re-pointing a "
            "citation at something unresolvable would make the ledger look repaired while still "
            "proving nothing -- find the real commit first.")
    row.setdefault("repoints", []).append({
        "was": row.get("commit"), "now": a.commit,
        "at": datetime.now(tz=UTC).isoformat(), "why": a.reason})
    row["commit"] = a.commit
    _save(d)
    print(f"{a.id} repointed -> {a.commit} (was {row['repoints'][-1]['was']}); "
          "status and reason untouched")


def sweeps_shown() -> dict[str, int]:
    """Row id -> how many sweeps the brain was AWAKE for have carried it.

    THE MEASUREMENT THIS FENCE WAS MISSING. `data/carryover_sweeps.jsonl` records every §37 sweep
    with an `alive` flag and the ids it carried, and the §37 brief already uses it to say "survived
    N sweeps, N with the brain awake". This fence -- looking at the SAME backlog -- had no notion of
    it and judged purely on elapsed hours.

    An unreadable or absent record returns ``{}``, which degrades toward MORE alarm, not less:
    every owed row then reports zero sweeps shown and none can claim the queued exemption.
    """
    counts: dict[str, int] = {}
    if not SWEEPS.exists():
        return counts
    try:
        lines = SWEEPS.read_text("utf-8").splitlines()
    except OSError:
        return counts
    for line in lines:
        if not line.strip():
            continue
        try:
            sweep = json.loads(line)
        except ValueError:
            continue
        if not sweep.get("alive"):          # a sweep the brain slept through shows nobody anything
            continue
        for rid in sweep.get("ids") or []:
            if isinstance(rid, str) and rid.startswith("rec-owed-"):
                counts[rid[len("rec-owed-"):]] = counts.get(rid[len("rec-owed-"):], 0) + 1
    return counts


def drain(d: dict[str, Any], window_h: float = 72.0) -> dict[str, float]:
    """Arrivals vs dispositions over a trailing window -- the property a LEVEL cannot express.

    THE DETECTOR THE DESK DID NOT HAVE. The old fence counted how many rows were open past grace,
    which on 2026-08-01 (131 raised, 48 disposed) said exactly what it had said the day before and
    what it said on a day the queue drained: RED. A backlog that is being worked down and one that
    is running away look identical to a level. Measured 2026-08-05 over the ledger's whole life,
    the level fence read RED for 226 of its 226 informative hours -- a gate that is always on
    carries no information (L1.43), and one that cries wolf gets switched off (L1.37).
    """
    arrived = disposed = unstamped = 0
    for r in d["recommendations"]:
        if _age_h(r.get("raised")) <= window_h:
            arrived += 1
        dd = r.get("disposed")
        if dd and _age_h(dd) <= window_h:
            disposed += 1
        # R0259: rows that reached a terminal state through an organ writing the JSON directly
        # carry no `disposed` stamp, so they are real dispositions this window CANNOT see. Counted
        # and published rather than silently dropped -- an undercounted numerator biases the drain
        # verdict toward RUNNING AWAY, which is the direction that manufactures a false alarm.
        elif not dd and r.get("status") not in ("open", "scheduled"):
            unstamped += 1
    return {"window_h": window_h, "arrived": arrived, "disposed": disposed,
            "net": disposed - arrived, "terminal_unstamped": unstamped,
            "ratio": (disposed / arrived) if arrived else float("inf")}


def owed(d: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """(undisposed past grace, scheduled past due OR chronically deferred) -- how a row goes stale.

    THE THIRD WAY A ROW GOES STALE WAS INVISIBLE UNTIL 2026-08-13. An overdue schedule fires here,
    so a row that keeps its date owes a decision the day it arrives -- but a row whose date is
    MOVED the day before never arrives at all, and 26% of ever-scheduled rows had exactly that
    done to them (libs/ops/deferral.py). A chronically re-scheduled row is therefore counted as
    owed whatever its due date says: it does not lose the right to be deferred again, only the
    ability to leave the desk's attention while it happens.
    """
    now = datetime.now(tz=UTC)
    orphans = [r for r in d["recommendations"]
               if r["status"] == "open" and _age_h(r["raised"]) > GRACE_H]
    overdue = []
    for r in d["recommendations"]:
        if r["status"] != "scheduled" or not r.get("due"):
            continue
        if is_chronic(r):
            overdue.append(r)
            continue
        try:
            if datetime.fromisoformat(str(r["due"])).replace(tzinfo=UTC) < now:
                overdue.append(r)
        except Exception:
            overdue.append(r)          # an unparseable due date is not a valid schedule
    return orphans, overdue


def report(_a: argparse.Namespace) -> None:
    d = _load()
    rows = d["recommendations"]
    orphans, overdue = owed(d)
    done = [r for r in rows if r["status"] == "implemented"]
    print(f"recommendations: {len(rows)} total | {len(done)} implemented | "
          f"{sum(1 for r in rows if r['status'] == 'rejected')} rejected | "
          f"{sum(1 for r in rows if r['status'] == 'scheduled')} scheduled | "
          f"{sum(1 for r in rows if r['status'] == 'open')} open")
    # THE QUEUE, NOT JUST ITS LEVEL. Printed first because it is the line that changes day to day.
    fl = drain(d)
    verdict = ("DRAINING" if fl["net"] > 0 else "FLAT" if fl["net"] == 0 else "RUNNING AWAY")
    print(f"  queue/{fl['window_h']:.0f}h: {fl['arrived']} in, {fl['disposed']} out, "
          f"net {fl['net']:+d} -- {verdict}"
          + (f" (+{fl['terminal_unstamped']} terminal but unstamped, invisible to this window)"
             if fl["terminal_unstamped"] else ""))
    shown = sweeps_shown()
    # SEPARATE "NOBODY LOOKED" FROM "NOBODY WOULD HAVE LOOKED YET". Both still owe a disposition and
    # both are still printed; only one of them is evidence that work is being walked past. Calling a
    # row raised into a quota-dead window "skipped" is a false positive, and a fence whose alarms
    # are mostly false is a fence that gets ignored -- which is how the real skips hid among them.
    for label, group in (("UNDISPOSED past grace", orphans), ("SCHEDULED past due", overdue)):
        for r in group:
            n = shown.get(r["id"], 0)
            tag = ("DEFECT" if n >= SKIP_SWEEPS else "OWED")
            note = (f"skipped, shown to {n} live sweep(s)" if n >= SKIP_SWEEPS
                    else f"queued, shown to {n} live sweep(s)")
            print(f"  {tag} [{label}] {r['id']} ({r['source']}, "
                  f"{_age_h(r['raised']) / 24:.1f}d, {note}): {r['summary'][:100]}")
    n_skip = sum(1 for r in orphans + overdue if shown.get(r["id"], 0) >= SKIP_SWEEPS)
    n_owed = len(orphans) + len(overdue)
    if not orphans and not overdue:
        print("  no orphans, nothing overdue -- every recommendation has a decision")
    else:
        print(f"  {n_owed} row(s) owe a disposition; {n_skip} of them are SKIPS "
              f"(shown to >={SKIP_SWEEPS} live sweeps and still open)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="ledger a recommendation (status opens as undisposed)")
    p.add_argument("--source", required=True,
                   help="max_audit | deep_sweep | cycle | panel | proactive_battery | principal")
    p.add_argument("--summary", required=True)
    # R0477: one field used to carry two populations -- measured bps and rank ordinals
    # (9999/9000/8000/...) -- so a guessed rank was indistinguishable from a measured return.
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--roi-bps", dest="roi_bps", type=float, default=None,
                     help="MEASURED return estimate in bps -- never an ordering ordinal")
    grp.add_argument("--rank", dest="rank", type=float, default=None,
                     help="priority ordinal, higher = sooner -- carries no return claim")
    p.set_defaults(func=add)
    p = sub.add_parser("dispose", help="record the decision -- the only way a row leaves open")
    p.add_argument("--id", required=True)
    # R0259: the CLI accepted three statuses while organs were writing `done` and `screened`
    # directly into the JSON, so 15 rows reached a terminal state through a path with no timestamp
    # and no reason check. Migrating them to `implemented` was the other option offered and it
    # DESTROYS information -- a SCREENED axis (the section-33 screen-on-discovery duty) is not an
    # implemented recommendation, and collapsing the two would make the conversion record lie about
    # which kind of work was done. Teach the CLI the vocabulary the desk actually uses instead.
    p.add_argument("--status", required=True,
                   choices=["implemented", "rejected", "scheduled", "done", "screened"])
    p.add_argument("--reason")
    p.add_argument("--commit")
    p.add_argument("--due", help="YYYY-MM-DD, required for scheduled")
    p.add_argument("--expect", help="substring the target summary must contain -- "
                                    "guards against disposing a row another writer "
                                    "took the id of")
    p.set_defaults(func=dispose)
    p = sub.add_parser("correct", help="reverse a MISFILED disposition, logged")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=correct)
    p = sub.add_parser("repoint", help="move an implemented row's --commit after a rebase, "
                                       "without touching the disposition itself")
    p.add_argument("--id", required=True)
    p.add_argument("--commit", required=True, help="the commit that carries the work TODAY")
    p.add_argument("--reason", required=True)
    p.add_argument("--expect", help="substring the target summary must contain")
    p.set_defaults(func=repoint)
    p = sub.add_parser("report", help="orphans and overdue -- both are defects, not backlog")
    p.set_defaults(func=report)
    a = ap.parse_args()
    _settle_forecasts(_load()["recommendations"])
    a.func(a)


if __name__ == "__main__":
    main()
