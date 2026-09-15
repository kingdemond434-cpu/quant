"""F2 -- POINT-IN-TIME TRUTH ON EVERY DATA PATH, not just the acquired ones.

THE PRINCIPAL, 2026-09-12, ranking this second of the remaining blueprint:

    acquire_datasets.py is already very good: it refuses undated/revision-unsafe data and creates
    PIT certificates. Extend that standard to literally every market/data path: event time,
    observation time, receive time, broker/server time, publication time, revision/vintage,
    timezone source, transformation lineage and availability timestamp.

THE STANDARD EXISTS AND IS EXCELLENT. `libs/data/pit_certificate.certify` puts seven questions to
a dataset -- leak, revision, timestamps, availability, survivorship, truncation, schema -- and
mints a certificate whose `authority` is false unless every one passes. `acquire_datasets` calls
it on everything it fetches.

WHAT IT DOES NOT COVER, which is the whole of F2: every OTHER path. The universe parquets the
gauntlet backtests on, the ingested axes (COT, BIS, ECB, FRED), the moat tape, the macro event
ledger, the tick tape. Those feed certificates, sizing and live orders, and not one of them has
ever been asked the seven questions. A standard applied to the smallest surface is a standard in
name.

YOU CANNOT EXTEND A STANDARD TO PATHS NOBODY HAS ENUMERATED, which is why this is an AUDIT before
it is a gate. It walks every data path the desk actually reads, asks which carry a certificate,
and -- for those that do not -- reports which of the nine time facts the data itself can still
answer. That turns "extend PIT everywhere" from an aspiration into a numbered list of paths with
a named missing field each.

THE TIMEZONE CLAUSE IS CHECKED DIRECTLY, because it is the one that fails silently. A naive
datetime index is not a time: it is a number that LOOKS like a time and whose meaning depends on
whichever machine last wrote it. Every path is checked for tz-awareness and the naive ones are
named, because "no implicit timezone conversion anywhere" cannot be verified by reading code.

    python desks/mt5/research/pit_audit.py [--apply]
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

OUT = DESK / "reports" / "PIT_AUDIT.json"
CERT_DIR = DESK / "data" / "pit_certificates"

#: The nine time facts F2 requires of every path. Named here so a path's gap is a FIELD, not a
#: feeling -- "macro lacks publication_time" is actionable and "macro needs better PIT" is not.
REQUIRED_FACTS: tuple[str, ...] = (
    "event_time",        # when the thing happened in the world
    "observation_time",  # when the publisher observed it
    "receive_time",      # when this desk received it
    "broker_time",       # the venue's own clock, where a venue is involved
    "publication_time",  # when it became public
    "revision_vintage",  # which vintage this is, if the source restates
    "timezone_source",   # whose timezone the stamps are in, stated not assumed
    "transform_lineage", # what produced this from what
    "available_time",    # the first instant the desk could have acted on it
)

#: Every data path the desk actually reads, and what consumes it. A path whose consumer is a
#: money-path organ is ranked above one feeding a report, because a PIT defect there prices risk.
PATHS: tuple[dict[str, Any], ...] = (
    {"id": "universe_bars", "glob": "desks/mt5/data/universe/*_H1.parquet",
     "kind": "parquet", "consumer": "gauntlet, shadow_forward, allocator", "tier": "money"},
    {"id": "axis_cot", "glob": "desks/mt5/data/axes/cot.json",
     "kind": "json", "consumer": "cot_positioning family", "tier": "research"},
    {"id": "axis_bis", "glob": "desks/mt5/data/axes/bis.json",
     "kind": "json", "consumer": "carry, macro_conditional", "tier": "research"},
    {"id": "axis_ecb", "glob": "desks/mt5/data/axes/ecb.json",
     "kind": "json", "consumer": "macro_conditional", "tier": "research"},
    {"id": "axis_fred", "glob": "desks/mt5/data/axes/fred.json",
     "kind": "json", "consumer": "macro_conditional", "tier": "research"},
    {"id": "macro_events", "glob": "desks/mt5/data/macro/event_ledger.jsonl",
     "kind": "jsonl", "consumer": "event_reaction, news lane", "tier": "money"},
    {"id": "moat_tape", "glob": "desks/mt5/data/tape/*",
     "kind": "opaque", "consumer": "moat_miner, cost_surface", "tier": "research"},
    {"id": "cost_surface", "glob": "desks/mt5/data/cost_surface.json",
     "kind": "json", "consumer": "engine cost model (once fed)", "tier": "money"},
    {"id": "carry_state", "glob": "desks/mt5/data/carry_state.json",
     "kind": "json", "consumer": "financing leg (once fed)", "tier": "money"},
    {"id": "live_ledger", "glob": "desks/mt5/data/live_ledger.jsonl",
     "kind": "jsonl", "consumer": "attribution, book_forensics", "tier": "money"},
)


def _certificates() -> dict[str, Any]:
    """Every PIT certificate on disk, by dataset name."""
    out: dict[str, Any] = {}
    if not CERT_DIR.exists():
        return out
    for p in CERT_DIR.rglob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = str(d.get("dataset") or p.stem)
        out[name] = {"authority": bool(d.get("authority")),
                     "certified_at": d.get("certified_at"),
                     "checks": {c.get("name"): c.get("passed")
                                for c in (d.get("checks") or []) if isinstance(c, dict)}}
    return out


def _probe(spec: dict[str, Any]) -> dict[str, Any]:
    """What the data itself can still answer, for a path with no certificate.

    Deliberately SHALLOW -- it reads one file and its column/key names. The point is not to
    re-implement certify(); it is to say which of the nine facts the path could supply today, so
    the repair is a named field rather than a research project.
    """
    matches = sorted(ROOT.glob(spec["glob"]))
    if not matches:
        return {"present": False, "why": "no file matches this path on this box"}
    sample = matches[0]
    facts: dict[str, bool] = dict.fromkeys(REQUIRED_FACTS, False)
    tz_aware: bool | None = None
    cols: list[str] = []
    try:
        if spec["kind"] == "parquet":
            import pandas as pd
            df = pd.read_parquet(sample)
            cols = [str(c) for c in df.columns]
            idx = df.index
            tz_aware = bool(getattr(idx, "tz", None)) if hasattr(idx, "tz") else None
            if tz_aware is None and "time" in cols:
                tz_aware = bool(getattr(pd.to_datetime(df["time"], errors="coerce").dt,
                                        "tz", None))
        elif spec["kind"] in ("json", "jsonl"):
            raw = sample.read_text(encoding="utf-8", errors="replace")
            first = raw.splitlines()[0] if spec["kind"] == "jsonl" else raw
            doc = json.loads(first)
            if isinstance(doc, dict):
                cols = list(doc)[:60]
            elif isinstance(doc, list) and doc and isinstance(doc[0], dict):
                cols = list(doc[0])[:60]
            blob = " ".join(cols).lower()
            tz_aware = ("+00:00" in raw[:4000]) or ("utc" in raw[:4000].lower())
        else:
            cols = []
    except Exception as exc:
        return {"present": True, "why": f"unreadable: {type(exc).__name__}: {exc}",
                "n_files": len(matches)}

    blob = " ".join(cols).lower()
    # A fact counts as PRESENT only when a field names it. Inference from a generic `time` column
    # is exactly the implicit assumption F2 exists to end: one timestamp cannot be event time AND
    # receive time AND availability time, and treating it as all three is how lookahead enters.
    marks = {
        "event_time": ("event_time", "time", "date", "datetime"),
        "observation_time": ("observation_time", "observed", "obs_time"),
        "receive_time": ("receive_time", "received", "ingested_time", "fetched_at"),
        "broker_time": ("broker_time", "server_time", "time_msc"),
        "publication_time": ("publication_time", "published", "release_time"),
        "revision_vintage": ("vintage", "revision", "as_of", "asof"),
        "timezone_source": ("timezone", "tz", "tz_source"),
        "transform_lineage": ("lineage", "source_hash", "pit_certificate", "derived_from",
                              "code_hash"),
        "available_time": ("available_time", "availability", "knowable_at"),
    }
    for fact, keys in marks.items():
        facts[fact] = any(k in blob for k in keys)
    return {"present": True, "n_files": len(matches), "sample": sample.name,
            "tz_aware": tz_aware, "fields": cols[:24], "facts": facts,
            "n_facts": sum(facts.values())}


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    certs = _certificates()
    rows: list[dict[str, Any]] = []
    for spec in PATHS:
        cert = certs.get(spec["id"])
        probe = _probe(spec)
        missing = [f for f, ok in (probe.get("facts") or {}).items() if not ok]
        if cert and cert.get("authority"):
            state = "CERTIFIED"
        elif cert:
            state = "CERTIFIED_NO_AUTHORITY"
        elif not probe.get("present"):
            state = "ABSENT"
        else:
            state = "UNCERTIFIED"
        rows.append({**spec, "state": state, "certificate": cert,
                     "tz_aware": probe.get("tz_aware"),
                     "n_facts_present": probe.get("n_facts"),
                     "missing_facts": missing,
                     "sample": probe.get("sample"), "why": probe.get("why")})

    present = [r for r in rows if r["state"] != "ABSENT"]
    certified = [r for r in present if r["state"] == "CERTIFIED"]
    naive = [r for r in present if r.get("tz_aware") is False]
    money = [r for r in present if r["tier"] == "money" and r["state"] != "CERTIFIED"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "n_paths": len(rows), "n_present": len(present), "n_certified": len(certified),
        "coverage_pct": round(100 * len(certified) / max(len(present), 1), 1),
        "n_money_path_uncertified": len(money),
        "money_path_uncertified": [r["id"] for r in money],
        "naive_timestamps": [r["id"] for r in naive],
        "required_facts": list(REQUIRED_FACTS),
        "paths": rows,
        "status": "ATTENTION" if (money or naive) else ("OK" if certified else "UNMEASURED"),
        "rule": ("a fact counts as present only when a FIELD names it. One `time` column cannot "
                 "be event time and receive time and availability time at once, and treating it "
                 "as all three is exactly how lookahead enters a backtest."),
        "why": ("the seven-question standard exists and is excellent; it covers the acquired "
                "datasets only. Every other path -- the bars the gauntlet certifies on, the "
                "ingested axes, the macro ledger, the live fills -- feeds certificates, sizing "
                "and orders, and has never been asked."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build()
    print(f"PIT audit: {doc['status']}   {doc['n_certified']}/{doc['n_present']} path(s) "
          f"certified ({doc['coverage_pct']}%)")
    for r in doc["paths"]:
        if r["state"] == "ABSENT":
            continue
        tz = {True: "tz-aware", False: "NAIVE", None: "tz?"}[r.get("tz_aware")]
        print(f"  {r['state']:<22} {r['id']:<15} {r['tier']:<8} {tz:<9} "
              f"{r.get('n_facts_present', 0)}/9 facts")
        if r["missing_facts"]:
            print(f"      missing: {', '.join(r['missing_facts'][:6])}")
    if doc["money_path_uncertified"]:
        print(f"\n  MONEY PATH UNCERTIFIED: {', '.join(doc['money_path_uncertified'])}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
