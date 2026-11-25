"""THE COUNTRY CENSUS: every ISO 3166-1 country and territory, counted against the forest grounds.

The principal's order (2026-11-25): the hunt is literally global, every bit of the earth. This
module turns that into a number that can only be read, never asserted. Each of the 249 ISO
3166-1 entries in `desks/mt5/data/iso3166_countries.json` is classed against
`desks/mt5/data/deep_forest_sources.json`:

    COVERED           >= 3 grounds, at least one of them an official-data ground
    PARTIAL           >= 1 ground
    SERVED_BY_PARENT  no monetary or statistics body of its own; its row names the parent and
                      the reason, and the parent must itself be PARTIAL or better
    MISSING           nothing

A territory row whose parent is MISSING counts as MISSING too: "served" by nothing is not
served. `missing` is the count the hourly pass reports until it reaches 0, and it is a FLOOR
the other way round from coverage -- it may only fall (`check_ratchet`).

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

OFFICIAL_KINDS = frozenset({"official", "macro", "dataset", "rates_credit", "regulatory_filing",
                            "exchange_rulebook", "local_market_mechanics"})
COVERED_MIN_GROUNDS = 3
STATUSES = ("COVERED", "PARTIAL", "SERVED_BY_PARENT", "MISSING")


def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def census(iso_doc: Mapping[str, Any] | None, grounds_doc: Mapping[str, Any] | None
           ) -> dict[str, Any]:
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

    def own(code: str) -> str:
        rows = per.get(code, [])
        if not rows:
            return "MISSING"
        official = any(str(r.get("kind") or "") in OFFICIAL_KINDS for r in rows)
        return "COVERED" if len(rows) >= COVERED_MIN_GROUNDS and official else "PARTIAL"

    rows_out: list[dict[str, Any]] = []
    for c in countries:
        code = str(c.get("alpha2") or "").upper()
        status = own(code)
        parent = str(c.get("served_by") or "").upper()
        if status == "MISSING" and parent:
            status = "SERVED_BY_PARENT" if own(parent) != "MISSING" else "MISSING"
        rows_out.append({"alpha2": code, "name": c.get("name"), "status": status,
                         "grounds": len(per.get(code, [])),
                         **({"served_by": parent, "why": c.get("served_by_why")}
                            if parent else {})})
    hist = Counter(r["status"] for r in rows_out)
    return {"status": "MEASURED", "total": len(rows_out),
            **{s.lower(): hist.get(s, 0) for s in STATUSES},
            "missing_list": sorted(r["alpha2"] for r in rows_out if r["status"] == "MISSING"),
            "partial_list": sorted(r["alpha2"] for r in rows_out if r["status"] == "PARTIAL"),
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
    return census(_read(ISO_FILE), _read(GROUNDS_FILE))
