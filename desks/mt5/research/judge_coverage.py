"""JUDGE COVERAGE -- the judge tests 100% of what this desk mines, every hour, by BACKLOG.

    "the judge should test 100 percent of what this desk ever mines, every hour, 24/7, always"
    "all families should be hunted, all mechanisms, all unknowns, for maximum breadth -- not
     fixed like these six, every time"                                -- the principal, 2026-09-23

WHAT WAS MEASURED, AND WHY ORDER IS THE WHOLE PROBLEM. From 120,000 recent gate verdicts on the
trading box, 60 families were judged -- and the judged distribution had almost nothing to do with
the mined one. The docket's five largest populations were `cross_asset_residual` 55,190,
`overnight_drift` 26,721, `discovered` 24,052, `clock_transition` 20,081 and `execution_state`
13,660; the judged counts were `discovered` 22,009 (18% of the judge's whole recent capacity, on
a family BANNED from live capital, passing 0), then `orderflow_imbalance` 5,654, `vol_transition`
4,869, `liquidity_regime` 3,785, `session_range_breakout` 3,723. So the scarce judge re-tested a
handful of families every hour while the largest mined populations waited, and spent a fifth of
itself on cells that could never reach the book.

That is not a gauntlet defect. `external_gauntlet` is SEALED and takes the docket it is handed
under a bar budget, so **the order of the docket IS the selection**: a family at the tail is not
"lower priority", it is never judged at all. This organ therefore does its whole job at INTAKE,
upstream of the sealed judge, and changes nothing about how a cell is judged once it arrives.

COVERAGE, NOT ROTATION. Rotation asks "whose turn is it"; coverage asks "what has never been
answered". The quantity this organ drives to zero is the UNJUDGED BACKLOG, per family:

    backlog(family) = docket rows of that family carrying NO verdict in the gate ledger

Every family holding backlog is given a quota of the hour -- a FLOOR first, so a family of nine
cells is reached at all, then the remainder in proportion to its own backlog, so a family of
55,190 is drained at the rate its size deserves. The docket is then emitted as a weighted
interleave of the families, which makes EVERY PREFIX of it family-balanced: whatever slice of the
docket the gauntlet's budget actually reaches this hour, that slice contains every family with
backlog, at its quota. Nothing is truncated, nothing is deleted, nothing is deferred by this
organ -- the whole corpus still ships, in an order that spends the budget on coverage.

WHAT IT NEVER DOES (GROWTH_GOVERNANCE Rule 1). It removes no cell, lowers no bar, caps no book
and shrinks no budget. Reordering is the one intervention that cannot cost throughput: the same
rows reach the same judge under the same budget, and the only thing that changes is which
question the hour answers first. Mining stays unrestricted; a family's population may grow as
fast as the miners can grow it.

THE RATCHET, AND WHY IT IS ON THE CARRIED COHORT. `data/judge_backlog_ratchet.json` records, per
family, the backlog at each reading. Raw backlog RISES whenever miners outrun the judge, which is
mining working, not intake failing -- a fence on the raw number would punish the desk for mining
and would be switched off inside a week. So the ratcheted quantity is the CARRIED cohort: rows
that were already in the backlog at the previous reading and are still unjudged now. A cell
leaves that cohort exactly one way, by being judged, so the carried count can only fall, and any
family whose carried count fails to fall while it held backlog was starved -- which is the defect
this organ exists to make impossible. `scripts/check_judge_coverage.py` is that fence.

WHAT IT PUBLISHES -- `reports/JUDGE_COVERAGE.json`, per family:
`mined`, `queued` (this hour's realised quota in the head window), `judged_window`,
`unjudged`, `oldest_unjudged_age_h`, `carried`, `drained`, `window_h`.

THE BANNED FAMILY IS ALREADY OUT, AND THIS ORGAN DOES NOT RE-DO IT. `merge_hypotheses` routes
every row of a family banned from live capital (`mt5desk.live_policy.DEFAULT_BANNED_FAMILIES`)
into `data/hypotheses/study_bank.json` with the ban as the recorded reason, before the docket is
written; `external_gauntlet` sets banned cells aside again at its own door. Those rows are kept
forever and the miners keep producing them -- what stops is the SPENDING. This organ reads the
study bank only to report `mined` honestly: a family's mined population is what the desk mined,
not what it chose to judge.

NO FIXED FAMILY SET. The family universe here is `mt5desk.families.live_family_names()` -- the
union of every registered population the forward engine can actually resolve -- unioned with
whatever the docket and the ledger name. A family invented tomorrow is queued and judged the hour
it first appears in the docket, with no edit to this file.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
STUDY_BANK = HYP / "study_bank.json"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
REPORTS = BASE / "reports"
REPORT = REPORTS / "JUDGE_COVERAGE.json"
RATCHET = BASE / "data" / "judge_backlog_ratchet.json"

#: The judging window every family is measured against: one hour, because the principal's order
#: is "every hour, 24/7". A family's OWN window widens from here by how long its own quota needs
#: to drain its own backlog -- a family of 55,190 cells is not starved for being large.
WINDOW_H = 1.0

#: The share of the hour handed out as an equal FLOOR before anything is proportional. A floor is
#: what makes a nine-cell family reachable at all; without it proportional allocation is a
#: winner-take-all rule that rediscovers the exact starvation this organ was built to end.
FLOOR_SHARE = 0.25

#: The judge's capacity is MEASURED from its own ledger (the busiest recent hour), never assumed
#: off a machine size -- CLAUDE.md's 8 GB/96 GB note is the standing lesson about inventing one.
#: The floor exists only so a cold tree with no ledger still produces a usable allocation.
CAPACITY_FLOOR = 500
CAPACITY_LOOKBACK_H = 168.0

#: Ledger rows whose downstream status begins with this were never actually judged -- the sweep's
#: build budget ran out before the cell was computed. Counting them as judged is precisely the
#: trap `external_gauntlet._stamped_but_unjudged` documents: it starved 1,544 cells forever.
NOT_JUDGED_PREFIX = "NOT_RUN"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(raw: object) -> datetime | None:
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _cell_id(row: dict[str, Any]) -> str | None:
    """The gauntlet's OWN identity function, imported, never re-implemented.

    Two implementations of an identity are two identities, and the whole measurement here turns
    on matching a docket row to the verdict the sealed judge recorded for it.
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.frontier_identity import cell_id
    except Exception:
        return None
    try:
        return str(cell_id({"sym": row.get("symbol") or row.get("sym"),
                            "family": row.get("family"),
                            "params": row.get("params") or {},
                            "timeframe": row.get("timeframe")}))
    except Exception:
        return None


def live_families() -> frozenset[str]:
    """Every family the desk can actually resolve -- the registry's live set, never a literal.

    An unreadable registry returns EMPTY and the caller then falls back to the docket's own
    families: losing this import must never narrow what gets judged (L1.28a).
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from mt5desk.families import live_family_names
        return frozenset(live_family_names())
    except Exception:
        return frozenset()


def banned_from_capital() -> frozenset[str]:
    """Families the desk has forbidden from live capital, read from the policy that enforces it.

    `merge_hypotheses` already routes these rows OUT of the judging docket and into the study
    bank, and `external_gauntlet` sets them aside again at its own door. This is the same answer
    at the allocator: a family that cannot reach the book is given no quota, so no hour of the
    scarce judge is allocated to an outcome the desk has already refused. The rows are still
    counted as MINED -- mining is unrestricted and stays so -- and they still ship in the docket,
    behind every family that can actually repay a gate-second.
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.merge_hypotheses import live_banned_families
        return frozenset(live_banned_families())
    except Exception:
        return frozenset()


def judged_index(path: Path | None = None, *, now: datetime | None = None,
                 window_h: float = WINDOW_H) -> tuple[set[str], dict[str, int], dict[str, int]]:
    """(cells carrying a real verdict, judged-per-family all-time, judged-per-family in window).

    A row is JUDGED when the ledger recorded a terminal gate or a pass/fail for it. A row whose
    downstream status is a `NOT_RUN_*` deferral is NOT judged: the budget never reached the cell,
    and calling that a verdict is what made deferral mean "never" for a third of the docket.
    """
    seen: set[str] = set()
    total: dict[str, int] = {}
    in_window: dict[str, int] = {}
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - window_h * 3600.0
    try:
        with (path or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return seen, total, in_window
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
            continue
        if row.get("passed") in (None, "None") and not row.get("terminal_gate"):
            continue
        fam = str(row.get("family") or "")
        cell = str(row.get("cell") or "")
        if cell:
            seen.add(cell)
        if not fam:
            continue
        total[fam] = total.get(fam, 0) + 1
        at = _ts(row.get("at"))
        if at is not None and at.timestamp() >= cutoff:
            in_window[fam] = in_window.get(fam, 0) + 1
    return seen, total, in_window


def measured_capacity(judged_total: dict[str, int], ledger: Path | None = None,
                      *, now: datetime | None = None) -> int:
    """Cells the judge demonstrably rules on in ONE hour -- its busiest recent hour, measured.

    Measured and never assumed: the allocation below divides THIS number, so inventing it off a
    machine size would size the hour for a machine the code is not on.
    """
    best = 0
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - CAPACITY_LOOKBACK_H * 3600.0
    per_hour: dict[str, int] = {}
    try:
        with (ledger or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    at = _ts(json.loads(line).get("at"))
                except ValueError:
                    continue
                if at is None or at.timestamp() < cutoff:
                    continue
                key = at.strftime("%Y-%m-%dT%H")
                per_hour[key] = per_hour.get(key, 0) + 1
    except OSError:
        per_hour = {}
    if per_hour:
        best = max(per_hour.values())
    return max(best, CAPACITY_FLOOR, sum(judged_total.values()) // 24)


def allocate(backlog: dict[str, int], capacity: int,
             floor_share: float = FLOOR_SHARE) -> dict[str, int]:
    """Quota per family: an equal FLOOR for every family holding backlog, then proportional.

    Two properties are load-bearing and both are tested. EVERY family with backlog gets at least
    one cell of the hour (coverage, not rotation), and no family is given more than its own
    backlog (a quota is a promise to drain, not a licence to re-judge).
    """
    live = {f: n for f, n in backlog.items() if n > 0}
    if not live or capacity <= 0:
        return {}
    floor_pool = int(capacity * max(0.0, min(1.0, floor_share)))
    per_family_floor = max(1, floor_pool // len(live))
    quota = {f: min(n, per_family_floor) for f, n in live.items()}
    spare = capacity - sum(quota.values())
    if spare > 0:
        room = {f: live[f] - quota[f] for f in live if live[f] > quota[f]}
        weight = sum(room.values())
        if weight > 0:
            for fam, r in sorted(room.items(), key=lambda kv: (-kv[1], kv[0])):
                take = min(r, int(spare * r / weight))
                quota[fam] += take
    return quota


def coverage_order(rows: list[dict[str, Any]], quota: dict[str, int],
                   unjudged_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Weighted interleave of the families, so EVERY PREFIX of the docket is family-balanced.

    Each family is emitted on its own virtual clock ticking at 1/quota, and the family whose next
    tick is earliest goes next -- classic weighted fair queueing. The result: in any first N rows
    the gauntlet's budget reaches, family f holds about N * quota[f] / sum(quota) of them. Within
    a family, NEVER-JUDGED rows go first and the oldest of those first, so the head of a family's
    stream is exactly the backlog the ratchet measures.

    No row is dropped. A family with no quota still ships, after the quota'd stream, because the
    docket this returns is the whole docket and the judge's budget -- not this order -- decides
    where the hour stops.
    """
    if not rows:
        return []
    ids = unjudged_ids or set()

    def rank(row: dict[str, Any]) -> tuple[int, str]:
        cid = str(row.get("_cell") or "")
        fresh = 0 if (not ids or cid in ids) else 1
        return (fresh, str(row.get("first_seen") or "9999"))

    streams: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        streams.setdefault(str(row.get("family") or ""), []).append(row)
    for fam in streams:
        streams[fam].sort(key=rank)

    # Virtual finish time of each family's next row; a family with no quota rides at weight 1 so
    # it is still interleaved rather than appended in a block.
    import heapq
    heap: list[tuple[float, str, int]] = []
    for fam, stream in streams.items():
        w = float(max(quota.get(fam, 0), 1))
        heapq.heappush(heap, (1.0 / w, fam, 0))
    out: list[dict[str, Any]] = []
    while heap:
        vtime, fam, idx = heapq.heappop(heap)
        out.append(streams[fam][idx])
        nxt = idx + 1
        if nxt < len(streams[fam]):
            w = float(max(quota.get(fam, 0), 1))
            heapq.heappush(heap, (vtime + 1.0 / w, fam, nxt))
    return out


def _mined(docket: list[dict[str, Any]]) -> dict[str, int]:
    """Mined population per family: the docket PLUS the study bank.

    The study bank holds families banned from live capital. They are not judged -- a gate-second
    there buys an outcome the desk has already forbidden -- but they were mined, and a coverage
    report that hid them would be reporting the desk's choices as if they were its output.
    """
    mined: dict[str, int] = {}
    for row in docket:
        fam = str(row.get("family") or "")
        mined[fam] = mined.get(fam, 0) + 1
    bank = _read(STUDY_BANK)
    if isinstance(bank, list):
        for row in bank:
            if isinstance(row, dict):
                fam = str(row.get("family") or "")
                mined[fam] = mined.get(fam, 0) + 1
    return mined


def build(docket: list[dict[str, Any]] | None = None, *, ledger: Path | None = None,
          ratchet: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """The per-family coverage table, the quotas, and the carried-cohort ratchet."""
    at = now or datetime.now(tz=UTC)
    rows = docket if docket is not None else (_read(DOCKET) or [])
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return {"at": at.isoformat(timespec="seconds"), "verdict": "UNMEASURED",
                "why": "the judging docket is absent or empty -- nothing mined to cover",
                "families": {}, "totals": {}, "quota": {}}

    judged_cells, judged_total, judged_window = judged_index(ledger, now=at)
    for row in rows:
        row["_cell"] = _cell_id(row)

    mined = _mined(rows)
    banned = banned_from_capital()
    study_only: dict[str, int] = {}
    backlog: dict[str, int] = {}
    oldest: dict[str, float | None] = {}
    unjudged_ids: set[str] = set()
    for row in rows:
        fam = str(row.get("family") or "")
        cid = row.get("_cell")
        if cid and cid in judged_cells:
            continue
        if fam in banned:
            # NOT backlog: a cell that cannot reach the book is not work the judge owes. It is
            # counted, named and kept -- it is simply not something the hour is allocated to.
            study_only[fam] = study_only.get(fam, 0) + 1
            continue
        backlog[fam] = backlog.get(fam, 0) + 1
        if cid:
            unjudged_ids.add(str(cid))
        seen = _ts(row.get("first_seen"))
        if seen is not None:
            age = max(0.0, (at.timestamp() - seen.timestamp()) / 3600.0)
            prev = oldest.get(fam)
            oldest[fam] = age if prev is None else max(prev, age)
        else:
            oldest.setdefault(fam, None)

    capacity = measured_capacity(judged_total, ledger, now=at)
    quota = allocate(backlog, capacity)
    judgeable = [r for r in rows if str(r.get("family") or "") not in banned]
    study_rows = [r for r in rows if str(r.get("family") or "") in banned]
    ordered = coverage_order(judgeable, quota, unjudged_ids) + study_rows
    head = ordered[:capacity]
    queued: dict[str, int] = {}
    for row in head:
        fam = str(row.get("family") or "")
        queued[fam] = queued.get(fam, 0) + 1

    prior = _read(ratchet or RATCHET) or {}
    prior_fams = prior.get("families") if isinstance(prior, dict) else {}
    prior_fams = prior_fams if isinstance(prior_fams, dict) else {}
    prior_at = _ts(prior.get("at") if isinstance(prior, dict) else None)
    # THE CARRIED COHORT: rows already in the backlog at the previous reading and STILL unjudged.
    # It can only fall, because a cell leaves it exactly one way -- by being judged.
    carried: dict[str, int] = {}
    if prior_at is not None:
        for row in rows:
            cid = row.get("_cell")
            if cid and cid in judged_cells:
                continue
            seen = _ts(row.get("first_seen"))
            if seen is not None and seen.timestamp() <= prior_at.timestamp():
                fam = str(row.get("family") or "")
                carried[fam] = carried.get(fam, 0) + 1

    fams = sorted(set(mined) | set(backlog) | set(judged_window) | live_families())
    table: dict[str, dict[str, Any]] = {}
    for fam in fams:
        if not fam:
            continue
        back = backlog.get(fam, 0)
        q = quota.get(fam, 0)
        # A FAMILY'S OWN WINDOW: the hours its own quota needs to drain its own backlog. A family
        # of 55,190 cells is not starved for being large, and a family of nine is not excused for
        # being small -- each is held to the clock its own size implies, floored at the hour.
        window = WINDOW_H if q <= 0 else max(WINDOW_H, back / max(q, 1) * WINDOW_H)
        was = int(prior_fams.get(fam, {}).get("unjudged", 0)) if isinstance(
            prior_fams.get(fam), dict) else 0
        table[fam] = {
            "mined": mined.get(fam, 0),
            "queued": queued.get(fam, 0),
            "judged_window": judged_window.get(fam, 0),
            "judged_total": judged_total.get(fam, 0),
            "unjudged": back,
            "oldest_unjudged_age_h": (round(oldest[fam], 2)
                                      if oldest.get(fam) is not None else None),
            "quota": q,
            "window_h": round(window, 2),
            "carried": carried.get(fam, 0) if prior_at is not None else None,
            "prior_unjudged": was if prior_at is not None else None,
            "drained": (was - carried.get(fam, 0)) if (prior_at is not None and was) else None,
        }

    covered = sum(1 for f, r in table.items() if r["unjudged"] > 0 and r["queued"] > 0)
    starved = sorted((f for f, r in table.items() if r["unjudged"] > 0 and r["queued"] == 0),
                     key=lambda f: -table[f]["unjudged"])
    totals = {
        "docket_rows": len(rows),
        "mined": sum(mined.values()),
        "families_mined": sum(1 for r in table.values() if r["mined"] > 0),
        "families_with_backlog": sum(1 for r in table.values() if r["unjudged"] > 0),
        "families_queued": covered,
        "families_starved": len(starved),
        "unjudged_total": sum(backlog.values()),
        "carried_total": sum(carried.values()) if prior_at is not None else None,
        "prior_unjudged_total": (sum(int(v.get("unjudged", 0)) for v in prior_fams.values()
                                     if isinstance(v, dict)) if prior_at is not None else None),
        "capacity_measured": capacity,
        "oldest_unjudged_age_h": (round(max(v for v in oldest.values() if v is not None), 2)
                                  if any(v is not None for v in oldest.values()) else None),
    }
    return {
        "at": at.isoformat(timespec="seconds"),
        "verdict": "COVERED" if not starved else "STARVED",
        "why": ("every family holding unjudged cells is in this hour's queue at its own quota"
                if not starved else
                f"{len(starved)} family(ies) hold unjudged cells and are absent from the queue: "
                f"{', '.join(starved[:5])}"),
        "rule": ("floor first (an equal share of "
                 f"{FLOOR_SHARE:.0%} of measured capacity to every family holding backlog), then "
                 "the remainder in proportion to backlog; the docket ships whole, interleaved, "
                 "so every prefix the judge's budget reaches is family-balanced"),
        "families": table,
        "totals": totals,
        "quota": quota,
        "starved": starved[:20],
        "worst_backlog": [
            {"family": f, "unjudged": table[f]["unjudged"], "queued": table[f]["queued"],
             "oldest_unjudged_age_h": table[f]["oldest_unjudged_age_h"],
             "mined": table[f]["mined"]}
            for f in sorted(table, key=lambda f: -table[f]["unjudged"])[:10]
            if table[f]["unjudged"] > 0],
        "banned_routed_out": {
            "where": str(STUDY_BANK),
            "by": "research/merge_hypotheses.py (live_banned_families -> study bank)",
            "why": ("a family banned from live capital cannot reach the book even if it passes, "
                    "so the scarce judge is not spent on it; mining stays unrestricted and the "
                    "rows are kept, never deleted"),
        },
    }


def write(doc: dict[str, Any], *, report: Path | None = None,
          ratchet: Path | None = None) -> None:
    """Publish the table and advance the ratchet. A ratchet write is the NEXT reading's baseline."""
    target = report or REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    fams = doc.get("families") or {}
    state = {
        "at": doc.get("at"),
        "families": {f: {"unjudged": int(r.get("unjudged") or 0),
                         "queued": int(r.get("queued") or 0)} for f, r in fams.items()},
        "unjudged_total": (doc.get("totals") or {}).get("unjudged_total"),
        "why": ("the baseline the carried-cohort ratchet is measured against: rows already in "
                "this backlog and still unjudged at the next reading were STARVED, because a "
                "cell leaves a cohort exactly one way -- by being judged"),
    }
    rt = ratchet or RATCHET
    rt.parent.mkdir(parents=True, exist_ok=True)
    rt.write_text(json.dumps(state, indent=1, default=str), "utf-8")


def render(doc: dict[str, Any]) -> list[str]:
    t = doc.get("totals") or {}
    lines = [f"judge coverage: {doc.get('verdict')} -- {doc.get('why')}",
             f"  families mined {t.get('families_mined')} / with backlog "
             f"{t.get('families_with_backlog')} / queued this hour {t.get('families_queued')}; "
             f"unjudged {t.get('unjudged_total')} on capacity {t.get('capacity_measured')}"]
    for row in (doc.get("worst_backlog") or [])[:5]:
        lines.append(f"  {row['family']}: mined {row['mined']} unjudged {row['unjudged']} "
                     f"queued {row['queued']} oldest {row['oldest_unjudged_age_h']}h")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="judge coverage by unjudged backlog, per family")
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's mode)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="measure without advancing the ratchet")
    args = ap.parse_args(argv)
    t0 = time.time()
    doc = build()
    doc["elapsed_s"] = round(time.time() - t0, 2)
    doc["budget_s"] = args.budget_s
    if not args.no_write:
        write(doc)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for line in render(doc):
            print(line)
    return 0


__all__ = ["allocate", "build", "coverage_order", "judged_index", "live_families",
           "measured_capacity", "main", "render", "write"]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
