"""DIG ROI -- a cycle is scored by TESTABLE CANDIDATES AND CERTIFICATES, never by bytes written.

WHY THIS EXISTS (principal 2026-08-28: "big doesn't mean token wastage -- it means maximum
breadth, depth, orthogonal discovery, certificates, forwards and survivor hunts. Max ROI
testable candidates mined is success, and certificates").

The seat scorecard defines PRODUCED as a log file over 1,500 bytes. That is output VOLUME: a dig
that writes three kilobytes of reasoning and mines nothing scores exactly like one that adds
fifty judgeable cells to the docket. Optimising that number is optimising token spend, which is
the opposite of the order. Worse, it is the same class as every defect found on this desk: a
metric that moves without the thing it claims to measure moving.

WHAT IS MEASURED INSTEAD, from artifacts the desk already writes:
  * TESTABLE candidates added to the docket -- judgeable cells only. A candidate the gauntlet
    must terminal-reject at gate 1, or one that cannot reach the 60 trading days the gates
    need, is not a yield; it is compute the cycle spent on a question no gate can answer.
  * BREADTH -- distinct asset classes and families the day's candidates touch, because the
    binding constraint is orthogonality (n_eff ~5.5 across 23 certificates), not cell count.
  * CERTIFICATES minted, and FORWARD clocks started. The end of the pipeline is the only
    unambiguous ROI.
  * COST -- launches spent to get it. Yield per launch is the ratio the principal is asking for.

A day with 200 statistical-only candidates and a day with 20 named, judgeable, class-diverse
ones are NOT the same day, and this report is where that stops being invisible.

THE RESEARCH COUNTERFACTUAL (2026-09-09, inventory A5). `--survivor <cert_key>` walks the
hypothesis graph back from a certified cell and answers the question every trading
counterfactual on this desk answers for a TRADE and none answered for a DISCOVERY: what
process reached this region first, and how long before the certificate? It reports the
lineage (`hypothesis_graph.lineage`), the earliest graph row in the same parameter REGION and
the earliest in the same symbol+family, each with its source and date, and prices the delay in
days. Where the graph holds no earlier reach -- today's state for every certificate, because
the verdict rows were registered without their candidate rows -- the delay is BOUNDED by the
graph's memory and said to be, never reported as zero.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "dig_roi.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: The certificates, and the graph the counterfactual walks. `GRAPH_PATH` None means the
#: hypothesis graph's own ledger.
UNI = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
GRAPH_PATH: Path | None = None
#: One document per certificate key, merged on every `--survivor` run.
CF_OUT = ROOT / "data" / "research_counterfactual.json"


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _at(row: dict) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(row.get("at")))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _brief(row: dict) -> dict:
    return {"id": row.get("id"), "source": row.get("source"), "fate": row.get("fate"),
            "at": row.get("at"), "parent": row.get("parent") or ""}


def _earliest(rows: list[dict], pred) -> dict | None:
    best, best_at = None, None
    for r in rows:
        if not pred(r):
            continue
        t = _at(r)
        if t is None:
            continue
        if best_at is None or t < best_at:
            best, best_at = r, t
    return best


def survivor_counterfactual(cert_key: str, *, survivors: dict | None = None,
                            graph=None) -> dict:
    """What found this survivor's region first, and how long before it was certified.

    UNMEASURED with the missing input named when the key is not a certificate or its cell was
    never registered in the graph; BOUNDED when the graph's earliest reach IS the certifying
    pass, because the pre-gauntlet path (miner row -> candidate) was never recorded and the
    delay is a lower bound set by the graph's memory, not a measured zero.
    """
    from libs.research.hypothesis_graph import Graph, node_id
    if survivors is None:
        survivors = ((_read(UNI) or {}).get("survivors")
                     or (_read(CANON) or {}).get("survivors") or {})
    doc: dict = {"cert_key": cert_key,
                 "measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
    row = survivors.get(cert_key) if isinstance(survivors, dict) else None
    if not isinstance(row, dict):
        doc.update(status="UNMEASURED",
                   missing_input=(f"{cert_key!r} is not a key of {UNI.name} "
                                  f"({len(survivors or {})} certificate(s) held)"))
        return doc
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    symbol = str(spec.get("symbol") or row.get("sym") or "")
    family = str(spec.get("family") or "")
    params = dict(spec.get("params") or {})
    nid = node_id(symbol, family, params)
    g = graph if graph is not None else (Graph(GRAPH_PATH) if GRAPH_PATH else Graph())
    cur = g.current()
    doc.update(node_id=nid, symbol=symbol, family=family, params=params,
               hunt=row.get("hunt"))
    node = cur.get(nid)
    if node is None:
        doc.update(status="UNMEASURED",
                   missing_input=(f"no hypothesis_graph node for ({symbol}, {family}, "
                                  f"{json.dumps(params, sort_keys=True, default=str)}) -- the "
                                  f"certificate came from hunt {row.get('hunt')!r} by a path "
                                  f"that never registered its candidate, so its research path "
                                  f"is not in the graph"))
        return doc
    rows = g.rows()
    lineage = g.lineage(nid)
    root = lineage[-1] if lineage else node
    unresolved = root.get("parent") if root.get("parent") and root["parent"] not in cur else ""
    certified_at = _at(node) if node.get("fate") == "CERTIFIED" else None
    cert_basis = "the node's CERTIFIED row"
    if certified_at is None:
        try:
            certified_at = datetime.fromisoformat(str(row.get("gated_at")))
            certified_at = certified_at if certified_at.tzinfo else certified_at.replace(tzinfo=UTC)
            cert_basis = f"the certificate's gated_at (graph fate is {node.get('fate')})"
        except (TypeError, ValueError):
            certified_at, cert_basis = None, "UNMEASURED: no CERTIFIED row and no gated_at"
    region = str(node.get("region") or "")
    firsts = {
        "node": _earliest(rows, lambda r: r.get("id") == nid),
        "lineage_root": root,
        "region": _earliest(rows, lambda r: str(r.get("region") or "") == region),
        "family": _earliest(rows, lambda r: str(r.get("symbol") or "").upper() == symbol.upper()
                            and str(r.get("family") or "") == family),
    }
    reach: dict = {}
    for horizon, r in firsts.items():
        if r is None:
            reach[horizon] = None
            continue
        t = _at(r)
        delay = (None if certified_at is None or t is None
                 else round((certified_at - t).total_seconds() / 86400.0, 3))
        reach[horizon] = {**_brief(r), "delay_days": delay}
    earliest_h = min((h for h in reach if reach[h] and reach[h]["delay_days"] is not None),
                     key=lambda h: -reach[h]["delay_days"], default=None)
    first = reach[earliest_h] if earliest_h else None
    delay = first["delay_days"] if first else None
    doc.update(
        region=region,
        certified_at=certified_at.isoformat(timespec="seconds") if certified_at else None,
        certified_at_basis=cert_basis,
        lineage=[_brief(r) for r in lineage], lineage_depth=len(lineage),
        unresolved_parent=unresolved,
        first_reachable=reach,
        earliest_horizon=earliest_h,
    )
    if delay is None:
        doc.update(status="UNMEASURED",
                   missing_input="the certification time or the graph rows carry no parseable "
                                 "timestamp, so no delay can be priced")
    elif delay > 0:
        doc.update(status="MEASURED", delay_days=delay,
                   counterfactual=(f"the {earliest_h.replace('_', ' ')} was first reachable on "
                                   f"{first['at'][:10]} via source {first['source']!r}, "
                                   f"{delay:.1f} day(s) before certification on "
                                   f"{doc['certified_at'][:10]}"))
    else:
        doc.update(status="BOUNDED", delay_days=0.0,
                   counterfactual=(f"reached and certified in the same pass ({first['at'][:10]}"
                                   f", source {first['source']!r}); the graph holds no earlier "
                                   f"row in this region or family"
                                   + (f", and the lineage's root parent {unresolved!r} is not a "
                                      f"registered node -- the pre-gauntlet path (miner row -> "
                                      f"candidate) is unrecorded" if unresolved else
                                      "; the lineage ends at a root with no parent")
                                   + ", so the delay is bounded below by the graph's memory, "
                                     "not measured as zero"))
    return doc


def _write_counterfactual(doc: dict) -> None:
    CF_OUT.parent.mkdir(parents=True, exist_ok=True)
    all_docs = _read(CF_OUT)
    all_docs = all_docs if isinstance(all_docs, dict) else {}
    all_docs[doc["cert_key"]] = doc
    CF_OUT.write_text(json.dumps(all_docs, indent=1, default=str), "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="dig ROI, or one survivor's research counterfactual")
    ap.add_argument("--survivor", metavar="CERT_KEY",
                    help="walk the hypothesis graph back from this certificate and price the "
                         "delay between first reach and certification")
    args = ap.parse_args(argv)
    if args.survivor:
        doc = survivor_counterfactual(args.survivor)
        _write_counterfactual(doc)
        print(f"research counterfactual {doc['cert_key']}: {doc['status']}")
        if doc.get("counterfactual"):
            print(f"  {doc['counterfactual']}")
            print(f"  lineage depth {doc['lineage_depth']}; node {doc['node_id']}; "
                  f"region {doc['region']}")
        if doc.get("missing_input"):
            print(f"  missing input: {doc['missing_input']}")
        print(f"  -> {CF_OUT}")
        return 0 if doc["status"] in ("MEASURED", "BOUNDED") else 2

    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=1)
    m: dict = {"measured_at": now.isoformat(timespec="seconds"), "window": "24h"}

    # --- TESTABLE candidates in the docket (judgeable, named mechanism)
    docket = _read(DESK / "data" / "hypotheses" / "external_survivors.json") or []
    named = [r for r in docket if isinstance(r, dict)
             and r.get("mechanism_status") == "NAMED"]
    fresh = []
    for r in named:
        seen = str(r.get("first_seen") or "")
        if seen and seen >= cutoff.isoformat():
            fresh.append(r)
    m["docket_total"] = len(docket)
    m["docket_named_testable"] = len(named)
    m["added_last_24h"] = len(fresh)

    # --- BREADTH: the binding constraint is orthogonality, not volume
    sys.path.insert(0, str(DESK))
    try:
        from mt5desk.universe import asset_class
        classes = Counter(asset_class(str(r.get("symbol") or r.get("sym") or ""))
                          for r in named)
        classes.pop("unknown", None)
    except Exception:
        classes = Counter()
    families = Counter(str(r.get("family") or "?") for r in named)
    m["classes_touched"] = len(classes)
    m["families_touched"] = len(families)
    m["by_class"] = dict(classes.most_common())
    m["top_families"] = dict(families.most_common(8))

    # --- THE END OF THE PIPELINE: certificates and clocks
    uni = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    survivors = uni.get("survivors") or {}
    m["certificates"] = len(survivors)
    # distinct RUNNABLE strategies, not certificate rows: rows without params are legacy
    # duplicates of parameterized twins and double-count the book (measured 2026-08-28: 23
    # rows, 17 distinct runnable strategies).
    runnable = [k for k, v in survivors.items()
                if isinstance(v, dict) and (v.get("shadow_spec") or {}).get("params")]
    m["certificates_runnable"] = len(runnable)
    new_certs = [k for k, v in survivors.items()
                 if isinstance(v, dict) and str(v.get("gated_at") or "") >= cutoff.isoformat()]
    m["certificates_last_24h"] = len(new_certs)

    shadow = _read(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    active = [k for k, v in shadow.items()
              if isinstance(v, dict) and v.get("status") == "ACTIVE"]
    m["forward_clocks_active"] = len(active)
    m["forward_trades_total"] = sum(int(shadow[k].get("n") or 0) for k in active)

    # --- PER-PRODUCER YIELD. "The miners" is not an organ -- it is a dozen producers, and an
    # aggregate hides a dead one behind a busy one (principal 2026-08-28: the watchdogs must
    # make sure the LOCAL miners hunt too). Each row carries the producer that emitted it, so
    # contribution is attributable: a producer whose share of the testable docket collapses is
    # a specific broken thing with a name, not a vague slowdown.
    producers = Counter(str(r.get("producer") or "unattributed") for r in named)
    m["by_producer"] = dict(producers.most_common())
    m["producers_contributing"] = len([p for p, n in producers.items()
                                       if p != "unattributed" and n > 0])

    # --- COST: launches spent for that yield
    sy = _read(ROOT / "data" / "seat_launch_yield.json") or {}
    launches = int(sy.get("launches") or 0)
    m["launches_7d"] = launches
    m["testable_per_launch"] = (round(len(named) / launches, 1) if launches else None)

    # --- THE VERDICT, in the principal's terms
    m["verdict"] = (
        f"{len(named)} testable candidates across {len(classes)} asset class(es) and "
        f"{len(families)} family(ies); {len(runnable)} runnable certificates, "
        f"{len(active)} forward clocks holding {m['forward_trades_total']} trade(s). "
        f"Bytes written are not counted here on purpose."
    )
    OUT.write_text(json.dumps(m, indent=1), "utf-8")
    print(m["verdict"])
    print(f"  by class: {m['by_class']}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
