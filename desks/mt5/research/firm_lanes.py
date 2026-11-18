"""FIRM LANES, ONE PASS: every research role of a top systematic shop as an always-on lane.

    py -3 desks/mt5/research/firm_lanes.py        # argless: one pass, the only mode

What a pass does, in order (the logic lives in `libs/research/firm_lanes.py`):

  1. Measures every roster lane (LIVE / STALE / NO_ARTIFACT / NOT_ON_BRANCH / CODE_ONLY). A role
     whose code is only in an open PR shows NOT_ON_BRANCH with the PR numbers, so the gap between
     "a thread built it" and "the box runs it" is visible every hour.
  2. Seeds the shared signal library with every certified survivor (no lane re-proposes one).
  3. Queues asset x horizon grid hypotheses into the emptiest squares, then drains every lane's
     queue at QUEUE_DRAIN per pass into `data/intelligence/firm_lanes/` through the normal
     `proposer_common.donate` door, which stamps, blinds, preregisters and charges every row as a
     trial. The judge decides; nothing here decides.
  4. Replays every certificate's SPA p-value through the desk's online FDR (LORD++ / e-LOND).
  5. Pod stops (Citadel discipline), SHADOW: per-sleeve drawdown in R against a hard stop, from
     the live deal ledger. Recommendations only; nothing here is read by sizing or the gateway.
  6. Careers scout, weekly: firms' own careers pages through the robots gate and the refused-host
     list, themes diffed against the last read and written as lane topics.

Writes reports/FIRM_LANES.json, reports/FIRM_POD_STOPS.json, reports/FIRM_CAREERS.json.
Exit 1 only when the roster cannot be read.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import firm_lanes as fl  # noqa: E402

DATA = DESK / "data" / "firm_lanes"
LIBRARY = DATA / "signal_library.jsonl"
QUEUES = DATA / "queues"
CAREERS_STATE = DATA / "careers_last.json"
TOPICS = DATA / "lane_topics.jsonl"
REPORT = DESK / "reports" / "FIRM_LANES.json"
POD_REPORT = DESK / "reports" / "FIRM_POD_STOPS.json"
CAREERS_REPORT = DESK / "reports" / "FIRM_CAREERS.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"

#: Grid rows queued per pass, and rows drained per lane per pass into the judge's intake.
#: Small on purpose: every drained row is a charged trial against the shared FDR budget, and the
#: grid's job is to cover squares, not to flood one.
GRID_PER_PASS = 24
QUEUE_DRAIN = 24
#: Tightest drawdown among the prop accounts we trade (E8 8%) and the per-trade risk the plan
#: sizes at (docs/PROP_FIRM_E8.md). Used only by the shadow pod-stop report.
FIRM_DD_PCT = 8.0
RISK_PCT = 0.5
CAREERS_EVERY_H = 24 * 7


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _drain(lanes: list[str], library: fl.SignalLibrary, at: str) -> dict[str, Any]:
    from research import proposer_common as pc
    out: dict[str, Any] = {}
    for lane in lanes:
        q = fl.LaneQueue(QUEUES / f"{lane}.jsonl")
        batch = q.pending()[:QUEUE_DRAIN]
        if not batch:
            out[lane] = {"drained": 0, "pending": 0}
            continue
        rows = [fl.to_intake_row(r) for r in batch]
        path = pc.donate("firm_lanes", rows, tests_run=len(rows), suffix=lane)
        counts = pc.donation_counts()
        # ONLY WHAT THE DOOR TOOK IS SENT. A refused row (unstamped, wrong lane) stays QUEUED and
        # is retried next pass; marking it SENT would put a rule in the library the judge never
        # saw, and the grid would then never propose it again.
        refused = {str(x.get("title")) for x in (counts.get("refusals") or [])}
        refused |= {str(x.get("title")) for x in (counts.get("lane_refusals") or [])}
        sent = [] if not counts.get("donated") else [
            r for r, row in zip(batch, rows, strict=True) if row["title"] not in refused]
        q.mark_sent(sent, at)
        library.add([{"id": r["id"], "family": r["family"], "symbol": r["symbol"],
                      "params": r.get("params", {}), "lane": lane, "state": "SENT", "at": at}
                     for r in sent])
        out[lane] = {"offered": len(batch), "drained": len(sent),
                     "pending": len(q.pending()),
                     "intake": str(path) if path else None,
                     "donated": counts.get("donated"),
                     "refused_unstamped": counts.get("refused_unstamped"),
                     "refused_wrong_lane": counts.get("refused_wrong_lane")}
    return out


def _careers(roster: dict[str, Any], now: datetime) -> dict[str, Any]:
    prev = _read_json(CAREERS_STATE) or {}
    last = prev.get("at")
    if last:
        try:
            age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600.0
        except ValueError:
            age_h = CAREERS_EVERY_H
        if age_h < CAREERS_EVERY_H:
            return {"status": "NOT_DUE", "age_h": round(age_h, 1)}
    from libs.data.refused_hosts import refusal
    from research import index_discovery as idx
    themes: dict[str, dict[str, int]] = {}
    reads: list[dict[str, Any]] = []
    for page in roster.get("careers_pages", []):
        url, firm = str(page.get("url")), str(page.get("firm"))
        if not fl.terms_confirmed(page):
            reads.append({"firm": firm, "url": url,
                          "result": "BLOCKED_ON_TERMS: no confirmed terms record for this page; "
                                    "fail closed until one is added to the roster"})
            continue
        why = refusal(url)
        if why:
            reads.append({"firm": firm, "url": url, "result": f"REFUSED: {why}"})
            continue
        body, res = idx._get(url, cap=1_500_000)
        # Exception TYPE only: `_get` appends the exception's message, which can carry a host's
        # error page or a path, and the report is published.
        if not res.startswith(("HTTP", "REFUSED")):
            res = res.split(":", 1)[0]
        reads.append({"firm": firm, "url": url, "result": res})
        if body:
            themes[firm] = fl.career_themes(body.decode("utf-8", errors="replace"))
    new = fl.career_diff(prev.get("themes") or {}, themes)
    fl.append_jsonl(TOPICS, [dict(n, at=now.isoformat(), source="careers_scout")
                             for n in new])
    merged = {**(prev.get("themes") or {}), **themes}
    _write(CAREERS_STATE, {"at": now.isoformat(), "themes": merged})
    status = "READ" if themes else "NO_PAGE_READ"
    doc = {"at": now.isoformat(), "status": status, "reads": reads, "themes": themes,
           "new_or_grown": new,
           "rule": "firms' own careers pages only, robots.txt and the refused-host list obeyed; "
                   "LinkedIn and boards that ban automated reading are never contacted"}
    _write(CAREERS_REPORT, doc)
    return {"status": status, "pages": len(reads),
            "blocked_on_terms": sum(1 for r in reads
                                    if str(r["result"]).startswith("BLOCKED_ON_TERMS")),
            "fetched": sum(1 for r in reads if str(r["result"]).startswith("HTTP 2")),
            "new_or_grown": len(new)}


def run(now: datetime | None = None, *, careers: bool = True) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    at = now.isoformat()
    roster = fl.load_roster()
    lanes = fl.liveness(roster, ROOT, DESK, now)

    library = fl.SignalLibrary(LIBRARY)
    survivors = _read_json(SURVIVORS) or {}
    seeded = library.add(fl.survivors_to_library(survivors, at))

    universe = _read_json(UNIVERSE) or {}
    buckets = fl.universe_buckets(universe)
    grid_rows = fl.grid_hypotheses(buckets, library, GRID_PER_PASS, at)
    queued = fl.LaneQueue(QUEUES / "asset_horizon_grid.jsonl").push(grid_rows, library)

    queue_lanes = sorted(p.stem for p in QUEUES.glob("*.jsonl")) if QUEUES.exists() else []
    drained = _drain(queue_lanes, library, at)
    fdr = fl.fdr_summary(survivors)

    pods = fl.pod_stops(fl.read_jsonl(LIVE_LEDGER), FIRM_DD_PCT, RISK_PCT, now=now)
    pods["at"] = at
    _write(POD_REPORT, pods)

    car: dict[str, Any] = {"status": "SKIPPED"}
    if careers:
        try:
            car = _careers(roster, now)
        except Exception as exc:                                       # network is optional
            car = {"status": f"ERROR: {type(exc).__name__}"}

    verdicts: dict[str, int] = {}
    for r in lanes:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    doc = {"at": at, "template": roster.get("template"), "lanes": lanes,
           "verdicts": verdicts,
           "not_on_branch": [{"id": r["id"], "prs": r["prs"]} for r in lanes
                             if r["verdict"] == "NOT_ON_BRANCH"],
           "dark": [r["id"] for r in lanes if r["verdict"] in ("STALE", "NO_ARTIFACT")],
           "library": {**library.counts(), "seeded_this_pass": seeded},
           "grid": fl.grid_coverage(buckets, library), "grid_queued": queued,
           "queues": drained, "fdr": fdr,
           "pod_stops": {k: pods[k] for k in ("mode", "n_pods", "stop_r", "stops", "cuts")},
           "careers": car}
    _write(REPORT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    try:
        doc = run()
    except (OSError, ValueError) as exc:
        print(f"FIRM LANES: roster unreadable: {type(exc).__name__}")
        return 1
    print(f"FIRM LANES  {doc['at']}  verdicts={doc['verdicts']}")
    print(f"  not on branch {[x['id'] for x in doc['not_on_branch']]}; dark {doc['dark']}")
    print(f"  library {doc['library']['n']} ids; grid queued {doc['grid_queued']}; "
          f"drained {sum(v.get('drained', 0) for v in doc['queues'].values())}")
    f = doc["fdr"]
    print(f"  fdr {f.get('status')} certified={f.get('certified')} "
          f"over_budget_share={f.get('over_budget_share')}")
    print(f"  pods {doc['pod_stops']['n_pods']} stop={doc['pod_stops']['stop_r']}R "
          f"STOP={doc['pod_stops']['stops']} CUT={doc['pod_stops']['cuts']}")
    print(f"  careers {doc['careers']}")
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
