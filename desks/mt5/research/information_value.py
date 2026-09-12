"""F14 -- WHICH MISSING OBSERVATION IS WORTH BUYING, decided from the desk's own blind spots.

THE PRINCIPAL, 2026-09-12:

    Decide which MISSING observation is worth obtaining, estimate a dataset's EVIG BEFORE
    acquisition, find legal/public/licensed sources, compare competing providers, infer
    publication lags, build parsers, retire datasets that never contribute information.

THE GAP, AS THE LEDGER STATES IT: endpoint discovery, fetch, PIT-check and conversion to
primitives all exist -- the DECIDING half does not. `acquire_datasets` will fetch, date-check and
certify anything the crawler finds. Nothing says which thing is worth finding.

THE ANSWER IS ALREADY WRITTEN DOWN, IN THE DESK'S OWN REPORTS. Every organ that cannot answer a
question publishes UNMEASURED and says why -- and the why almost always names a dataset. Today the
desk holds sentences like "the COT and macro axes are empty, so there is nothing to read a crowd
off", "the event ledger parses to zero rows, so every extreme move is unexplained by
construction", "the live book holds 16 deals across 3 days". Each is a purchase order nobody has
read. So this organ HARVESTS every UNMEASURED verdict across every report, maps it to the dataset
that would close it, and ranks the datasets by how many blind spots each one opens.

THE EVIG UNIT IS STATED AND IT IS NOT dE[log W]. A dataset's value here is the number of
currently-unanswerable verdicts it would make answerable, weighted by whether those verdicts sit
on the money path. Converting that to expected log wealth would need the value of each verdict,
which the desk does not have -- and inventing a conversion would make a purchase decision look
like a portfolio calculation. The unit is BLIND SPOTS CLOSED, and it is labelled as such
everywhere it appears.

PROVIDERS ARE COMPARED ON THIS DESK'S OWN RECORD, never on a claim about the world. The
acquisition registry holds every URL fetched, its host and when. That supports a real comparison
-- which hosts have produced usable dated series and which have produced nothing -- and it does not
support a licence audit, so none is asserted.

RETIREMENT IS THE HALF EVERYONE FORGETS. A dataset that has been acquired and never referenced by
a single candidate is costing storage, PIT surface and attention for nothing. They are NAMED, not
deleted: the principal's storage rule is that data leaves the box deliberately, and an organ that
quietly deleted a series would be the wrong kind of tidy.

    python desks/mt5/research/information_value.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
STORE = DESK / "data" / "acquired"
REGISTRY = STORE / "registry.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
OUT = REPORTS / "INFORMATION_VALUE.json"

#: The dataset NEEDS this desk can recognise, and the phrases that name them. Each entry is a
#: thing that could actually be obtained, not a research aspiration -- "better data" is not a
#: purchase order and does not appear here.
NEEDS: tuple[dict[str, Any], ...] = (
    {"id": "cot_positioning", "tier": "research",
     "what": "CFTC Commitments of Traders, commercial and non-commercial net positioning",
     "marks": ("cot", "positioning data", "commercial positioning", "read a crowd off",
               "axes directory", "ingested axes"),
     "public_source": "CFTC publishes COT weekly, free, no key",
     "lag_note": "released Friday for the prior Tuesday -- a 3-day publication lag that MUST be "
                 "modelled, or every COT backtest is three days ahead of the world"},
    {"id": "macro_event_calendar", "tier": "money",
     "what": "a parseable macro event calendar: release time, actual, consensus, revision",
     "marks": ("event ledger", "macro event", "no macro events", "event calendar",
               "unexplained by construction"),
     "public_source": "central bank and statistics-office release calendars are public",
     "lag_note": "the release TIME is the whole point; a calendar without it cannot separate a "
                 "move from its cause"},
    {"id": "live_fill_history", "tier": "money",
     "what": "enough realised deals to measure the book rather than describe it",
     "marks": ("16 deals", "live ledger holds", "live book holds", "closed deal",
               "fills carry", "0 fills", "no fill", "realised r", "matched_fills",
               "realised deals"),
     "public_source": "NOT purchasable -- it accrues by trading, and only by trading",
     "lag_note": "none; it is produced here"},
    {"id": "compute_history", "tier": "research",
     "what": "seven days of compute ledger, so survivors per compute-hour can be fitted",
     "marks": ("scaling_laws", "compute ledger", "survivors per compute hour"),
     "public_source": "NOT purchasable -- it accrues by running, and the ledger is already wired",
     "lag_note": "none; it is produced here"},
    {"id": "depth_and_ticks", "tier": "research",
     "what": "order-book depth and tick tape, for impact and microstructure",
     "marks": ("depth", "tick tape", "microstructure", "fills at different sizes",
               "impact curve"),
     "public_source": "the broker's own feed, already recorded by the tape organs",
     "lag_note": "real time, but retention is the constraint rather than the lag"},
    {"id": "cost_surface_by_hour", "tier": "money",
     "what": "spread as a symbol x HOUR surface rather than one scalar per symbol",
     "marks": ("cost_surface", "one flat spread", "spread is a symbol", "cost model"),
     "public_source": "derivable from the desk's own bar and tick record",
     "lag_note": "none"},
    {"id": "financing_terms", "tier": "money",
     "what": "overnight swap and financing by symbol and side",
     "marks": ("carry_state", "financing", "swap", "overnight"),
     "public_source": "published by the broker in the contract specification",
     "lag_note": "changes without notice, so it must be re-read rather than cached forever"},
)

#: Weight on a blind spot that sits on the money path. Three, because a wrong number that prices
#: risk costs more than a wrong number in a research report -- and stated rather than tuned.
MONEY_WEIGHT = 3.0


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _walk_unmeasured(node: Any, report: str, path: str = "") -> list[dict[str, Any]]:
    """Every UNMEASURED verdict anywhere in a report, with the sentence that explains it.

    Recursive on purpose: the desk's organs nest their verdicts -- a symbol's axis, a lane's
    sub-block -- and a scan that only read the top-level `status` would find perhaps a fifth of
    them and report a desk that mostly knows what it is doing.
    """
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        st = str(node.get("status") or "")
        if st == "UNMEASURED":
            why = node.get("why") or node.get("value_why") or node.get("caveat") or ""
            out.append({"report": report, "at": path or "(root)", "why": str(why)[:600]})
        for k, v in node.items():
            if k in ("why", "status"):
                continue
            out.extend(_walk_unmeasured(v, report, f"{path}.{k}" if path else str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node[:200]):
            out.extend(_walk_unmeasured(v, report, f"{path}[{i}]"))
    return out


def _classify(why: str) -> str | None:
    low = why.lower()
    for need in NEEDS:
        if any(m in low for m in need["marks"]):
            return str(need["id"])
    return None


def _providers() -> dict[str, Any]:
    """Which hosts this desk has actually fetched from, and what came back. Its own record only."""
    reg = _read(REGISTRY)
    if not isinstance(reg, dict):
        return {"status": "UNMEASURED",
                "why": f"no acquisition registry at {REGISTRY.relative_to(ROOT)}"}
    by_url = reg.get("by_url") or {}
    series = reg.get("series") or {}
    hosts: dict[str, dict[str, Any]] = {}
    for url, row in by_url.items():
        if not isinstance(row, dict):
            continue
        h = str(row.get("host") or "unknown")
        e = hosts.setdefault(h, {"host": h, "n_urls": 0, "n_series": 0, "last_fetch": ""})
        e["n_urls"] += 1
        e["n_series"] += len(row.get("series") or [])
        at = str(row.get("at") or "")
        if at > str(e["last_fetch"]):
            e["last_fetch"] = at
        e.setdefault("urls", []).append(url[:120])
    rows = sorted(hosts.values(), key=lambda r: -int(r["n_series"]))
    return {"status": "OK", "n_hosts": len(rows), "n_urls": len(by_url),
            "n_series": len(series), "hosts": rows,
            "basis": ("this desk's own fetch record -- which hosts returned a usable dated "
                      "series and which did not. It supports no claim about licensing, so none "
                      "is made; a licence audit needs a document this box does not hold.")}


def _never_referenced(providers: dict[str, Any]) -> dict[str, Any]:
    """Acquired series no candidate has ever cited. Named, never deleted."""
    reg = _read(REGISTRY)
    if not isinstance(reg, dict):
        return {"status": "UNMEASURED", "why": "no acquisition registry"}
    series = list(reg.get("series") or {})
    if not series:
        return {"status": "UNMEASURED", "why": "the registry lists no acquired series"}
    rows = _read(DOCKET)
    blob = ""
    if isinstance(rows, list):
        blob = " ".join(f"{r.get('source')} {r.get('producer')} {r.get('family')} "
                        f"{json.dumps(r.get('params'))}"
                        for r in rows[:6000] if isinstance(r, dict)).lower()
    sv = _read(SURVIVORS) or {}
    blob += " " + json.dumps(sv.get("survivors") or {})[:200000].lower()
    unused = [s for s in series if s.lower() not in blob]
    return {"status": "OK", "n_series": len(series), "n_never_referenced": len(unused),
            "never_referenced": unused[:40],
            "action": ("NAMED, NEVER DELETED. The principal's storage rule is that data leaves "
                       "this box deliberately; an organ that quietly removed a series would be "
                       "the wrong kind of tidy. These are the candidates for a retirement "
                       "decision, which is a decision and not a side effect."),
            "caveat": ("a series counts as referenced if its NAME appears anywhere in the "
                       "docket's sources, producers, families or params. That over-counts: a "
                       "coincidental substring reads as a reference. It errs toward keeping "
                       "data, which is the right direction for a retirement list.")}


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    if not REPORTS.exists():
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "no reports directory -- nothing has published a verdict to harvest"}

    blind: list[dict[str, Any]] = []
    n_reports = 0
    for p in sorted(REPORTS.glob("*.json")):
        doc = _read(p)
        if doc is None:
            continue
        n_reports += 1
        blind.extend(_walk_unmeasured(doc, p.name))

    for b in blind:
        b["need"] = _classify(str(b.get("why") or ""))

    # DISTINCT REASONS, NOT RAW ROWS. A report that publishes the same UNMEASURED verdict across
    # ten sleeves and six sessions contributes ONE blind spot, not sixteen. The first run ranked
    # `live_fill_history` off ALPHA_CAPTURE's fan-out and would have made a dataset's value a
    # measure of how nested the report that wanted it happened to be.
    seen_reason: set[tuple[str, str]] = set()
    by_need: dict[str, list[dict[str, Any]]] = {}
    unclassified: list[dict[str, Any]] = []
    no_reason: list[dict[str, Any]] = []
    for b in blind:
        why = str(b.get("why") or "").strip()
        if not why:
            # AN UNMEASURED WITH NO EXPLANATION IS ITS OWN DEFECT. L1.28a says absence never
            # resolves to a clean verdict; a verdict that says "unmeasured" and nothing else
            # tells a reader there is a hole and not what would fill it, which is the half of
            # the law that does the work. Counted separately rather than silently dropped.
            no_reason.append(b)
            continue
        key = (str(b["report"]), why[:180])
        if key in seen_reason:
            continue
        seen_reason.add(key)
        if b["need"]:
            by_need.setdefault(str(b["need"]), []).append(b)
        else:
            unclassified.append(b)

    ranked: list[dict[str, Any]] = []
    for need in NEEDS:
        rows = by_need.get(str(need["id"]), [])
        w = MONEY_WEIGHT if need["tier"] == "money" else 1.0
        ranked.append({
            "dataset": need["id"], "tier": need["tier"], "what": need["what"],
            "blind_spots_closed": len(rows),
            "evig_weighted": round(len(rows) * w, 3),
            "evig_unit": "blind spots closed, money-path verdicts weighted x3",
            "public_source": need["public_source"],
            "publication_lag": need["lag_note"],
            "obtainable": not str(need["public_source"]).startswith("NOT purchasable"),
            "examples": [{"report": r["report"], "at": r["at"], "why": r["why"][:200]}
                         for r in rows[:4]],
        })
    ranked.sort(key=lambda r: -float(r["evig_weighted"]))

    providers = _providers()
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_reports_scanned": n_reports,
        "n_unmeasured_verdicts": len(blind),
        "n_distinct_blind_spots": len(seen_reason),
        "n_classified": len(seen_reason) - len(unclassified),
        "unexplained_unmeasured": {
            "n": len(no_reason),
            "rows": [{"report": b["report"], "at": b["at"]} for b in no_reason[:25]],
            "why_it_matters": (
                "an UNMEASURED verdict that carries no `why` is its own defect. L1.28a's force "
                "is not the word UNMEASURED -- it is that absence must say WHAT is absent. A "
                "verdict without that tells a reader there is a hole and not what would fill it, "
                "and it can never become a purchase order."),
        },
        "ranked_datasets": ranked,
        "top_purchase_order": next((r for r in ranked
                                    if r["blind_spots_closed"] > 0 and r["obtainable"]), None),
        "unclassified_blind_spots": {
            "n": len(unclassified),
            "rows": [{"report": b["report"], "at": b["at"], "why": b["why"][:180]}
                     for b in unclassified[:20]],
            "why": ("an UNMEASURED verdict whose explanation names no obtainable dataset. Listed "
                    "rather than forced into a need: mapping it to the nearest entry would "
                    "inflate that dataset's value with a blind spot it cannot actually close."),
        },
        "providers": providers,
        "retirement_candidates": _never_referenced(providers),
        "evig_unit_note": (
            "A DATASET'S VALUE HERE IS BLIND SPOTS CLOSED, NOT dE[log W]. Converting would need "
            "the value of each verdict, which this desk does not have; inventing a conversion "
            "would make a purchase decision look like a portfolio calculation. Money-path "
            "verdicts are weighted x3 because a wrong number that prices risk costs more than a "
            "wrong number in a research report -- stated, not tuned."),
        "boundary": (
            "IT DECIDES NOTHING AND FETCHES NOTHING. acquire_datasets remains the only thing that "
            "reaches the network; this ranks what would be worth reaching for."),
        "why": (
            "every organ that cannot answer a question already publishes UNMEASURED and says why, "
            "and the why almost always names a dataset. Those sentences are purchase orders "
            "nobody had read."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"information value: {doc.get('status')} -- {doc.get('why')}")
        return 0
    print(f"information value: OK   {doc['n_unmeasured_verdicts']} UNMEASURED verdict(s) across "
          f"{doc['n_reports_scanned']} report(s)")
    print(f"  {doc['n_distinct_blind_spots']} DISTINCT blind spot(s) after de-duplication; "
          f"{doc['n_classified']} name an obtainable dataset")
    ue = doc["unexplained_unmeasured"]
    print(f"  {ue['n']} UNMEASURED verdict(s) carry NO explanation at all -- their own defect")
    for r in doc["ranked_datasets"]:
        if not r["blind_spots_closed"]:
            continue
        flag = "" if r["obtainable"] else "  (NOT PURCHASABLE -- it accrues)"
        print(f"  {r['evig_weighted']:>6.1f}  {r['dataset']:<22} {r['tier']:<9} "
              f"closes {r['blind_spots_closed']} blind spot(s){flag}")
        print(f"          {r['what']}")
        print(f"          lag: {r['publication_lag'][:100]}")
    top = doc.get("top_purchase_order")
    if top:
        print(f"  -> the next dataset worth obtaining is {top['dataset']}: "
              f"{top['public_source']}")
    pv = doc["providers"]
    if pv.get("status") == "OK":
        print(f"  providers on this desk's own record: {pv['n_hosts']} host(s), "
              f"{pv['n_urls']} url(s), {pv['n_series']} series")
        for h in pv["hosts"][:5]:
            print(f"    {h['host']:<34} {h['n_series']:>3} series  last {h['last_fetch'][:10]}")
    rc = doc["retirement_candidates"]
    if rc.get("status") == "OK":
        print(f"  retirement candidates: {rc['n_never_referenced']} of {rc['n_series']} acquired "
              f"series have never been referenced by any candidate")
    print(f"  {doc['unclassified_blind_spots']['n']} blind spot(s) name no obtainable dataset")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
