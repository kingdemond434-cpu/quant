"""EVENT TO SCALE -- what a supply event is WORTH: lost output, share, duration and cushion.

WHY (DATA-26). The news stream classifies "a mine, field, refinery, port, pipeline or strait
stops or restarts" as `supply_disruption` and nudges a world-state component; nothing said HOW
BIG it was. A 300 kb/d Libyan field and the 20 mb/d through Hormuz read as the same kind. This
organ turns a qualitative event into a declared scale, from a DECLARED, VERSIONED capacity table
(`data/physical/capacity_table.json`) whose every row names its public source and carries status
VERIFY until a session checks the cited edition.

PER EVENT (kinds in SCALE_KINDS, read from the news stream's event log):

    match           a facility whose alias appears in the text (most specific), else a country
                    entity x commodity keyword (country production row), else UNMATCHED
    fraction        explicit "N%" or "half"/"partially" in the text, else 1.0 for an outage
                    verb ("halted", "shut", "offline", ...); a RESTART/RESUMPTION is the same
                    capacity with the opposite sign (restored output)
    lost_output     capacity x fraction, or an explicit quantity in the text ("300,000 bpd"),
                    in the commodity's unit PER DAY (annual units divided by 365)
    share           lost_output / global supply (and of the regional supply the table holds)
    duration_days   an explicit "for N days/weeks/months" in the text, else the kind's declared
                    prior (DURATION_PRIOR_DAYS)
    cushion         spare capacity (table) plus, for crude, the US commercial inventory above
                    its five-year same-week norm (PHYSICAL_STATE.json) expressed in days of the
                    lost output; a commodity with neither is UNMEASURED, never a zero
    scale           share_pct x sqrt(min(duration_days, 180) / 30) x uncovered, where
                    uncovered = lost / (lost + spare): the part no cushion absorbs. Declared,
                    not fitted; a ranking key, not a forecast
    mapping         the MT5 CFDs of the commodity (resolved against universe.json) with the
                    SIGNED supply shock (-share for a loss, +share for a restoration). A supply
                    shock is a state; no side, size or weight is written here

OPEC+ COMPLIANCE (`data/physical/opec_quotas.json`, every row VERIFY): required production per
country from the decision in force, against a production estimate on this host
(`data/physical/production_estimates.json`, {country: [[month, kb/d], ...]}) when one exists.
No estimate -> UNMEASURED for that country with the reason. Exempt members say so.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
UNMEASURED = "UNMEASURED"
ENGINE = "supply_scale"
CAPACITY = DESK / "data" / "physical" / "capacity_table.json"
QUOTAS = DESK / "data" / "physical" / "opec_quotas.json"
PRODUCTION = DESK / "data" / "physical" / "production_estimates.json"
EVENT_LOG = DESK / "data" / "events" / "events.jsonl"
PHYSICAL_REPORT = DESK / "reports" / "PHYSICAL_STATE.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
SCALE_KINDS = ("supply_disruption", "strike", "natural_disaster", "sanctions", "war_escalation")
#: Declared priors for how long an unspecified event of each kind lasts, in days.
DURATION_PRIOR_DAYS: dict[str, float] = {"supply_disruption": 14.0, "strike": 7.0,
                                         "natural_disaster": 21.0, "sanctions": 180.0,
                                         "war_escalation": 30.0}
DURATION_CAP = 180.0
LOOKBACK_DAYS = 14
LOG_TAIL_BYTES = 8 * 1024 * 1024
OUTAGE = re.compile(r"\b(halt\w*|shut\w*|stopp\w*|offline|outage|disrupt\w*|blockad\w*|"
                    r"closed?|closure|suspend\w*|force majeure|fire|explosion|attack\w*|"
                    r"strike|cut|curtail\w*|evacuat\w*|seiz\w*)\b", re.I)
RESTORE = re.compile(r"\b(restart\w*|resum\w*|restor\w*|reopen\w*|back online|lift\w*)\b", re.I)
PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|per ?cent)", re.I)
HALF = re.compile(r"\b(half|partial\w*)\b", re.I)
QTY = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|k|m)?\s*"
                 r"(barrels? (?:per|a) day|bpd|b/d)", re.I)
DUR = re.compile(r"\bfor\s+(?:at least\s+|about\s+|up to\s+)?(\d+(?:\.\d+)?)\s*"
                 r"(day|week|month)s?\b", re.I)


def _un(why: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "why": why}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def per_day(value: float, unit: str) -> tuple[float, str]:
    """An annual figure as a daily rate; a daily one unchanged."""
    if unit.endswith("/y"):
        return value / 365.0, unit[:-2] + "/d"
    return value, unit


# ============================================================================== the table
def load_table(path: Path = CAPACITY) -> dict[str, Any]:
    doc = _read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("commodities"), dict):
        return {}
    return doc


def coverage(table: Mapping[str, Any]) -> dict[str, Any]:
    """What the declared table holds, by facility type and verification status."""
    fac = table.get("facilities") or []
    types: dict[str, int] = {}
    for f in fac:
        types[str(f.get("type"))] = types.get(str(f.get("type")), 0) + 1
    rows = [*fac, *(table.get("country_production") or []),
            *(table.get("commodities") or {}).values()]
    return {"version": table.get("version"), "commodities": len(table.get("commodities") or {}),
            "facilities": len(fac), "facility_types": dict(sorted(types.items())),
            "country_rows": len(table.get("country_production") or []),
            "verify_rows": sum(1 for r in rows if r.get("status") == "VERIFY"),
            "verified_rows": sum(1 for r in rows if r.get("status") == "VERIFIED")}


def _text(event: Mapping[str, Any]) -> str:
    return " ".join(str(event.get(k) or "") for k in ("title", "claim", "text"))


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(phrase.lower()) + r"(?![a-z])",
                     text.lower()) is not None


def match(event: Mapping[str, Any], table: Mapping[str, Any]) -> dict[str, Any] | None:
    """The facility, else the country x commodity row, the event names."""
    text = _text(event)
    best = None
    for f in table.get("facilities") or []:
        hits = [a for a in f.get("aliases") or [] if _has(text, a)]
        if hits and (best is None or max(map(len, hits)) > best[0]):
            best = (max(map(len, hits)), f)
    if best:
        f = best[1]
        return {"basis": "facility", "id": f["id"], "type": f.get("type"),
                "commodity": f["commodity"], "country": f.get("country") or "",
                "capacity": float(f["capacity"]), "source": f.get("source"),
                "status": f.get("status")}
    ents = {str(e).upper() for e in event.get("entities") or []}
    comms = table.get("commodities") or {}
    for row in table.get("country_production") or []:
        if row.get("country") not in ents:
            continue
        kws = (comms.get(row["commodity"]) or {}).get("keywords") or []
        if any(_has(text, k) for k in kws):
            return {"basis": "country", "id": f"{row['country']}:{row['commodity']}",
                    "type": "country_production", "commodity": row["commodity"],
                    "country": row["country"], "capacity": float(row["capacity"]),
                    "source": row.get("source"), "status": row.get("status")}
    return None


def fraction(text: str) -> tuple[float, str]:
    m = PCT.search(text)
    if m and 0 < float(m.group(1)) <= 100:
        return float(m.group(1)) / 100.0, f"explicit {m.group(0)}"
    h = HALF.search(text)
    if h:
        return 0.5, f"'{h.group(0)}' read as half"
    return 1.0, "full outage (no fraction stated)"


def quantity_kbd(text: str) -> float | None:
    """An explicit crude quantity in the text, in kb/d."""
    m = QTY.search(text)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    mult = (m.group(2) or "").lower()
    if mult in ("million", "m"):
        return v * 1000.0
    if mult in ("thousand", "k"):
        return v
    return v / 1000.0


def duration(text: str, kind: str) -> tuple[float, str]:
    m = DUR.search(text)
    if m:
        n = float(m.group(1)) * {"day": 1, "week": 7, "month": 30}[m.group(2).lower()]
        return min(n, DURATION_CAP), f"explicit '{m.group(0)}'"
    return DURATION_PRIOR_DAYS.get(kind, 14.0), f"declared prior for {kind}"


def inventory_excess_kbbl(report: Any) -> float | None:
    """US commercial crude above (+) or below (-) its five-year same-week norm."""
    row = ((report or {}).get("series") or {}).get("WCESTUS1") if isinstance(report, dict) \
        else None
    if not isinstance(row, dict) or row.get("status") != "MEASURED":
        return None
    v = row.get("level_vs_norm")
    return float(v) if isinstance(v, int | float) else None


def resolve(candidates: Sequence[str], universe: Mapping[str, Any] | None) -> dict[str, Any]:
    if not universe:
        return {"status": UNMEASURED, "why": "universe registry absent on this host",
                "candidates": list(candidates)}
    got = [c for c in candidates if c in universe]
    return ({"status": "RESOLVED", "symbols": got} if got else
            {"status": "NOT_TRADEABLE_HERE", "candidates": list(candidates)})


def scale_event(event: Mapping[str, Any], table: Mapping[str, Any], *,
                physical: Any = None, universe: Mapping[str, Any] | None = None
                ) -> dict[str, Any]:
    """The declared scale of one event; UNMATCHED or UNMEASURED parts say why."""
    text = _text(event)
    kind = str(event.get("kind") or "")
    base = {"event_id": event.get("id") or event.get("event_id"), "kind": kind,
            "title": str(event.get("title") or "")[:200],
            "knowable_at": event.get("knowable_at")}
    m = match(event, table)
    if m is None:
        return {**base, "status": "UNMATCHED",
                "why": "no facility alias or country x commodity row of the capacity table "
                       "is named by this event"}
    comm = (table.get("commodities") or {}).get(m["commodity"]) or {}
    unit = str(comm.get("unit") or "")
    # a restoration headline usually names the outage it ends, so the restart verb decides
    restore = bool(RESTORE.search(str(event.get("title") or "") or text))
    verb = OUTAGE.search(text)
    frac, frac_basis = fraction(text)
    cap_d, unit_d = per_day(m["capacity"], unit)
    lost = cap_d * frac
    lost_basis = f"capacity x fraction ({frac_basis})"
    if m["commodity"] == "crude_oil" and (q := quantity_kbd(text)) is not None:
        lost, lost_basis = min(q, cap_d) if m["basis"] == "facility" else q, "explicit quantity"
    days, dur_basis = duration(text, kind)
    glob_d = per_day(float(comm.get("global_supply") or 0.0), unit)[0]
    spare_d = per_day(float(comm.get("spare_capacity") or 0.0), unit)[0]
    share = lost / glob_d if glob_d > 0 else None
    region = (table.get("regions") or {}).get(m["country"])
    reg_supply = sum(per_day(float(r["capacity"]), unit)[0]
                     for r in table.get("country_production") or []
                     if r.get("commodity") == m["commodity"]
                     and (table.get("regions") or {}).get(r.get("country")) == region) \
        if region else 0.0
    cushion: dict[str, Any] = {"spare_capacity_per_day": round(spare_d, 4)}
    inv = inventory_excess_kbbl(physical) if m["commodity"] == "crude_oil" else None
    if inv is not None and lost > 0:
        cushion["us_inventory_vs_norm_kbbl"] = round(inv, 1)
        cushion["inventory_cover_days"] = round(inv / lost, 2)
    elif m["commodity"] == "crude_oil":
        cushion["inventory"] = _un("PHYSICAL_STATE.json has no MEASURED crude inventory vs norm")
    else:
        cushion["inventory"] = _un(f"no inventory state for {m['commodity']} on this host")
    if spare_d <= 0 and "inventory_cover_days" not in cushion:
        cushion["status"] = UNMEASURED
        cushion["why"] = "no declared spare capacity and no inventory state: the cushion is " \
                         "unknown, not zero"
        uncovered = 1.0
    else:
        cushion["status"] = "MEASURED"
        uncovered = lost / (lost + spare_d) if lost + spare_d > 0 else 1.0
    sign = 1.0 if restore else -1.0
    score = (share * 100.0 * math.sqrt(min(days, DURATION_CAP) / 30.0) * uncovered
             if share is not None else None)
    return {**base, "status": "SCALED", "match": m, "unit": unit_d,
            "direction": "restoration" if restore else "loss",
            "outage_verb": verb.group(0) if verb else None,
            "fraction": frac, "lost_output": round(lost, 4), "lost_output_basis": lost_basis,
            "share_global": round(share, 6) if share is not None else None,
            "region": region, "share_regional": (round(lost / reg_supply, 6)
                                                 if reg_supply > 0 else None),
            "duration_days": days, "duration_basis": dur_basis,
            "lost_volume": round(lost * days, 2), "cushion": cushion,
            "uncovered": round(uncovered, 4),
            "scale": round(score, 4) if score is not None else None,
            "table_status": m.get("status"), "commodity_status": comm.get("status"),
            "mapping": {"commodity": m["commodity"],
                        "instruments": resolve(comm.get("instruments") or [], universe),
                        "supply_shock_share": (round(sign * share, 6)
                                               if share is not None else None),
                        "rule": "a signed supply shock is STATE; no side, size or weight"}}


# ============================================================================== OPEC+
def _month(s: str) -> str:
    return str(s)[:7]


def opec_compliance(now: datetime, quotas: Any, production: Any) -> dict[str, Any]:
    if not isinstance(quotas, dict) or not quotas.get("decisions"):
        return _un("no OPEC+ quota table on this host (data/physical/opec_quotas.json)")
    day = now.date().isoformat()
    live = [d for d in quotas["decisions"]
            if str(d.get("effective_from")) <= day <= str(d.get("effective_to") or "9999")]
    if not live:
        return _un(f"no quota decision in force on {day}")
    dec = live[-1]
    prod = production if isinstance(production, dict) else {}
    out: dict[str, Any] = {"decision": dec.get("id"), "source": dec.get("source"),
                           "status_of_table": dec.get("status"), "unit": quotas.get("unit"),
                           "countries": {}}
    for cc, req in sorted((dec.get("required") or {}).items()):
        series = sorted((str(r[0]), float(r[1])) for r in prod.get(cc) or []
                        if isinstance(r, list | tuple) and len(r) >= 2)
        series = [r for r in series if _month(r[0]) >= str(dec["effective_from"])[:7]]
        if not series:
            out["countries"][cc] = {"required": req, **_un(
                "no production estimate for this country on this host "
                "(data/physical/production_estimates.json)")}
            continue
        month, actual = series[-1]
        out["countries"][cc] = {"status": "MEASURED", "required": req, "actual": actual,
                                "month": month, "over": round(actual - req, 1),
                                "compliance": round(req / actual, 4) if actual > 0 else None}
    for cc, why in sorted((dec.get("exempt") or {}).items()):
        out["countries"][cc] = {"status": "EXEMPT", "why": why}
    rows = [r for r in out["countries"].values() if r.get("status") == "MEASURED"]
    out["measured"] = len(rows)
    out["status"] = "MEASURED" if rows else UNMEASURED
    if rows:
        req = sum(float(r["required"]) for r in rows)
        act = sum(float(r["actual"]) for r in rows)
        out["aggregate"] = {"required": req, "actual": act, "over": round(act - req, 1),
                            "compliance": round(req / act, 4) if act > 0 else None}
    else:
        out["why"] = "no production estimate for any quota country on this host"
    return out


# ============================================================================== the organ
def _utc(text: Any) -> datetime:
    at = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def read_events(path: Path = EVENT_LOG, *, now: datetime,
                lookback_days: float = LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Scale-kind events knowable in the lookback, one per event id (the latest row)."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - LOG_TAIL_BYTES))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    since = now - timedelta(days=lookback_days)
    by: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("kind") not in SCALE_KINDS:
            continue
        try:
            at = _utc(row.get("knowable_at") or row.get("at"))
        except ValueError:
            continue
        if since <= at <= now:
            by[str(row.get("id") or row.get("event_id") or len(by))] = row
    return list(by.values())


def build(*, now: datetime, events: Iterable[Mapping[str, Any]] | None = None,
          table_path: Path = CAPACITY, quotas_path: Path = QUOTAS,
          production_path: Path = PRODUCTION, physical: Any = None,
          universe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    table = load_table(table_path)
    out: dict[str, Any] = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"),
                           "kinds": list(SCALE_KINDS), "lookback_days": LOOKBACK_DAYS}
    if physical is None:
        physical = _read_json(PHYSICAL_REPORT)
    if universe is None:
        u = _read_json(UNIVERSE)
        universe = u if isinstance(u, dict) else None
    if not table:
        out["events"] = _un(f"capacity table absent or unreadable: {table_path}")
    else:
        out["table"] = coverage(table)
        evs = list(read_events(now=now) if events is None else events)
        scaled = [scale_event(e, table, physical=physical, universe=universe) for e in evs]
        scaled.sort(key=lambda r: -(r.get("scale") or -1.0))
        out["events"] = {"status": "MEASURED" if evs else UNMEASURED,
                         "read": len(evs),
                         "scaled": sum(1 for r in scaled if r["status"] == "SCALED"),
                         "unmatched": sum(1 for r in scaled if r["status"] == "UNMATCHED"),
                         "rows": scaled[:50]}
        if not evs:
            out["events"]["why"] = (f"no {'/'.join(SCALE_KINDS)} event knowable in the last "
                                    f"{LOOKBACK_DAYS} days in the news stream's event log")
    out["opec"] = opec_compliance(now, _read_json(quotas_path), _read_json(production_path))
    return out


def observations(block: Mapping[str, Any], received_at: datetime) -> list[Any]:
    """Sensor-ledger rows for each scaled event (the scale and the signed supply shock)."""
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    rows = (block.get("events") or {}).get("rows") or []
    for r in rows:
        if r.get("status") != "SCALED" or r.get("scale") is None or not r.get("knowable_at"):
            continue
        for metric, v in (("event_scale", r["scale"]),
                          ("supply_shock_share", r["mapping"]["supply_shock_share"])):
            if v is None:
                continue
            out.append(sc.make(sensor_class="physical_commodity", kind="state",
                               sensor_id="physical:event_scale",
                               source_id="desk:capacity_table", metric=metric, value=float(v),
                               entity=r["match"]["commodity"], geography=r["match"]["country"],
                               asset_domain="commodity", event_time=r["knowable_at"],
                               knowable_at=r["knowable_at"], knowable_basis="declared_lag",
                               received_at=max(received_at, _utc(r["knowable_at"])),
                               parse_complete_at=max(received_at, _utc(r["knowable_at"])),
                               event_id=r.get("event_id"), facility=r["match"]["id"],
                               table_status=r.get("table_status")))
    return out
