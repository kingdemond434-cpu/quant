"""THE COUNTRY CENSUS: every ISO 3166-1 country and territory, counted against the forest grounds.

The principal's order (2026-11-25): the hunt is literally global, every bit of the earth. This
module turns that into a number that can only be read, never asserted. Each of the 249 ISO
3166-1 entries in `desks/mt5/data/iso3166_countries.json` is classed against
`desks/mt5/data/deep_forest_sources.json`:

    COVERED           >= 3 grounds with evidence (not PROPOSED_UNREAD, or read by a box pass),
                      at least one of them an official-data ground
    PARTIAL           >= 1 ground
    SERVED_BY_PARENT  no monetary or statistics body of its own; its row names the parent and
                      the reason, and the parent must itself be PARTIAL or better
    NO_ECONOMY        no resident economy at all (Antarctica); the row says so
    MISSING           nothing

A territory row whose parent is MISSING counts as MISSING too: "served" by nothing is not
served. `missing` is the count the hourly pass reports until it reaches 0, and it is a FLOOR
the other way round from coverage -- it may only fall (`check_ratchet`).

Registered is not read: a ground added from this cloud session (which has no egress to most
official hosts) carries read_status PROPOSED_UNREAD, and the census publishes `unread` -- the
countries no box pass has reached yet, from the miner's own frontier state.

The census is a pure function of the two files; `global_coverage_tensor` publishes it in
reports/GLOBAL_COVERAGE_TENSOR.json["countries"] on its hourly leg.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ISO_FILE = ROOT / "desks" / "mt5" / "data" / "iso3166_countries.json"
GROUNDS_FILE = ROOT / "desks" / "mt5" / "data" / "deep_forest_sources.json"
#: The miner's per-ground hunt outcomes (`deep_forest_miner._record_frontier`). A ground is READ
#: once a box pass reached it (YIELDED or EMPTY); NAMED_ONLY and BLOCKED are not reads.
FRONTIER_FILE = ROOT / "desks" / "mt5" / "data" / "deep_forest_frontier.json"
READ_OUTCOMES = frozenset({"YIELDED", "EMPTY"})

OFFICIAL_KINDS = frozenset({"official", "macro", "dataset", "rates_credit", "regulatory_filing",
                            "exchange_rulebook", "local_market_mechanics"})
COVERED_MIN_GROUNDS = 3
STATUSES = ("COVERED", "PARTIAL", "SERVED_BY_PARENT", "NO_ECONOMY", "MISSING")


def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _outcomes(frontier_doc: Any) -> dict[str, str] | None:
    """ground name -> last hunt outcome, or None when the frontier was never written."""
    if not isinstance(frontier_doc, Mapping):
        return None
    vecs = frontier_doc.get("vectors")
    if isinstance(vecs, Mapping):
        items = vecs.items()
    elif isinstance(vecs, list):
        items = ((str(v.get("name") or ""), v) for v in vecs if isinstance(v, Mapping))
    else:
        return None
    return {str(k): str((v or {}).get("outcome") or "") for k, v in items
            if isinstance(v, Mapping)}


def census(iso_doc: Mapping[str, Any] | None, grounds_doc: Mapping[str, Any] | None,
           frontier_doc: Any = None) -> dict[str, Any]:
    """The per-country classification, or an UNMEASURED verdict when either file is absent."""
    if not isinstance(iso_doc, Mapping) or not isinstance(grounds_doc, Mapping):
        return {"status": "UNMEASURED",
                "why": "iso3166_countries.json or deep_forest_sources.json unreadable: the "
                       "country count is unknown, not zero"}
    countries = [c for c in iso_doc.get("countries") or [] if isinstance(c, Mapping)]
    grounds = [g for g in grounds_doc.get("grounds") or [] if isinstance(g, Mapping)]
    per: dict[str, list[Mapping[str, Any]]] = {}
    for g in grounds:
        per.setdefault(str(g.get("region") or "").upper(), []).append(g)

    outcomes = _outcomes(frontier_doc)

    def own(code: str) -> str:
        rows = per.get(code, [])
        if not rows:
            return "MISSING"
        # COVERED needs EVIDENCE: a ground proposed and never read counts toward PARTIAL only.
        firm = [r for r in rows if r.get("read_status") != "PROPOSED_UNREAD"
                or (outcomes is not None
                    and outcomes.get(str(r.get("name") or "")) in READ_OUTCOMES)]
        official = any(str(r.get("kind") or "") in OFFICIAL_KINDS for r in firm)
        return "COVERED" if len(firm) >= COVERED_MIN_GROUNDS and official else "PARTIAL"

    def read(code: str) -> int | None:
        if outcomes is None:
            return None
        return sum(1 for r in per.get(code, [])
                   if outcomes.get(str(r.get("name") or "")) in READ_OUTCOMES)

    rows_out: list[dict[str, Any]] = []
    for c in countries:
        code = str(c.get("alpha2") or "").upper()
        status = own(code)
        parent = str(c.get("served_by") or "").upper()
        if status == "MISSING" and c.get("no_economy"):
            status = "NO_ECONOMY"
        elif status == "MISSING" and parent:
            status = "SERVED_BY_PARENT" if own(parent) != "MISSING" else "MISSING"
        rows_out.append({"alpha2": code, "name": c.get("name"), "status": status,
                         "grounds": len(per.get(code, [])), "grounds_read": read(code),
                         **({"served_by": parent, "why": c.get("served_by_why")}
                            if parent else {})})
    hist = Counter(r["status"] for r in rows_out)
    return {"status": "MEASURED", "total": len(rows_out),
            **{s.lower(): hist.get(s, 0) for s in STATUSES},
            "missing_list": sorted(r["alpha2"] for r in rows_out if r["status"] == "MISSING"),
            "partial_list": sorted(r["alpha2"] for r in rows_out if r["status"] == "PARTIAL"),
            # REGISTERED IS NOT READ: a country whose grounds no box pass has reached yet.
            "unread": (None if outcomes is None else sum(
                1 for r in rows_out if r["grounds"] and not r["grounds_read"])),
            "unread_list": (None if outcomes is None else sorted(
                r["alpha2"] for r in rows_out if r["grounds"] and not r["grounds_read"])),
            "rule": (f"COVERED = >= {COVERED_MIN_GROUNDS} grounds incl. an official-data ground; "
                     "PARTIAL = >= 1 ground; SERVED_BY_PARENT = no own body and the parent has "
                     "a ground; MISSING = none. MISSING only falls."),
            "rows": rows_out}


def check_ratchet(now: Mapping[str, Any], before: Mapping[str, Any] | None) -> str | None:
    """A breach string when the MISSING count rose against the last measured census."""
    if not isinstance(before, Mapping) or before.get("status") != "MEASURED":
        return None
    if now.get("status") != "MEASURED":
        return "country census went UNMEASURED after a measured pass"
    if int(now.get("missing", 0)) > int(before.get("missing", 0)):
        return f"MISSING countries rose {before.get('missing')} -> {now.get('missing')}"
    return None


def current() -> dict[str, Any]:
    return census(_read(ISO_FILE), _read(GROUNDS_FILE), _read(FRONTIER_FILE))
