"""THE DISCOVERY LOOP: an unseeded source carried from discovery to an outcome to a new priority.

WHY THIS EXISTS (audit ARCH-22 / ARCH-23 / DATA-51, 2026-10-07). Every stage of the data path has
an organ -- `catalog_routes`, `world_dataset_hunter` and `index_discovery` discover, the acquirer's
registry acquires, `dataset_use` records reads, the gauntlet judges cells -- and nothing joined
them per SOURCE. So the desk could not show one unseeded source going all the way round: found,
fetched correctly, its uses tested, a defensible verdict recorded, and that verdict changing what
the desk looks for next. Without the join, nothing learnt from a verdict ever reached the queue
that decides what to fetch, and "the desk improves at discovery" was a claim, not a number.

ONE RECORD PER UNSEEDED SOURCE (a host nobody wrote into any seed -- `discovery_audit`'s seed set,
the same one that decides benchmark contamination), moving through:

    DISCOVERED    a row in `intelligence/world/discoveries_*.json` (catalog routes, the crawler,
                  the deep forest), an `index_discovery` address, or a hunter provider
    ACQUIRED      a series in the acquirer's registry (`data/acquired/registry.json`), PIT-checked
                  there; a hunter dataset fetched by the hunter
    USES_TESTED   a recorded read (`libs/data/dataset_use`) or a cell the gauntlet judged whose id
                  names one of the source's series
    OUTCOME       USEFUL    at least one such cell PASSED the gauntlet
                  REJECTED  >= MIN_JUDGED_FOR_REJECT judged cells and none passed
                  LIMITED   it could not be used as found: every fetch refused (the refusal is
                            the reason), only keyed endpoints, or too little dated history
                  each with its reason in words and the time it was first reached.

THE VALIDITY GUARD. USEFUL and REJECTED come from `gate_verdict_ledger.jsonl` ONLY -- the one
gauntlet's own record, whose cells are charged to the shared standing trial count
(`gate_policy.charged_trial_count`). This organ runs no test and looks at no return: a read, a
lifecycle label or a novelty score never makes a source USEFUL. The useful rate's denominator is
gauntlet-judged sources, never all sources, so a cohort cannot look good by being untested.

THE FEEDBACK. Outcomes become a measured prior per feature a source shares with others -- host,
producer type, country, language, data type -- shrunk to the base rate (`priors.json`).
`acquire_datasets` orders its discovered-endpoint share by it and `catalog_routes` credits a
portal's staleness with it. BOTH ARE REORDERS: nothing is dropped, nothing is capped, and an
item with no evidence keeps the base rate.

THE INGESTION BALANCE (DATA-51). Discovery arrivals (new endpoints per day) against ingestion
completions (those endpoints the acquirer has processed, per day), the backlog's growth per day,
and an ALARM when arrivals outrun completions for ALARM_DAYS days running. The alarm's response
is a REORDER -- the acquirer's discovered share rises and the oldest backlog goes first -- and
never a cut to mining; the artifact says so in a field a test pins.

    python desks/mt5/research/discovery_loop.py
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

WORLD = DESK / "data" / "intelligence" / "world"
INDEX_FOUND = DESK / "data" / "intelligence" / "index_discovery"
HUNTER_CATALOG = DESK / "data" / "world_datasets" / "catalog.json"
REGISTRY = DESK / "data" / "acquired" / "registry.json"
DATASET_USE = DESK / "data" / "dataset_use"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
STATE_DIR = DESK / "data" / "discovery_loop"
LEDGER = STATE_DIR / "ledger.json"
PRIORS = STATE_DIR / "priors.json"
FLOW = STATE_DIR / "flow.json"
HISTORY = STATE_DIR / "history.jsonl"
EXTENSION = DESK / "frontier_intel" / "data" / "ontology_extension.json"
QUEUE = DESK / "data" / "task_queue.jsonl"
REPORT = DESK / "reports" / "DISCOVERY_LOOP.json"

UNMEASURED = "UNMEASURED"
OUTCOMES = ("USEFUL", "REJECTED", "LIMITED")
STAGES = ("DISCOVERED", "ACQUIRED", "USES_TESTED", "OUTCOME")
#: Judged cells before "none passed" is a REJECTED verdict rather than a test still running. One
#: failed cell is a fact about that cell; three independent ones are a fact about the source.
MIN_JUDGED_FOR_REJECT = 3
#: Prior strength (pseudo-observations at the base rate). Weak, so real evidence dominates fast.
PRIOR_STRENGTH = 4.0
#: Days arrivals must outrun completions, running, before the backlog alarm fires.
ALARM_DAYS = 3
#: Days of flow published.
FLOW_DAYS = 28
#: History rows kept (one per pass): the loop's own performance over time.
HISTORY_KEEP = 24 * 120
#: How far a mission (a promoted ontology class) lifts a matching source's prior.
MISSION_LIFT = 0.15
#: Weight of the gauntlet useful rate in a prior; the rest is acquirability. Usefulness leads,
#: so a source that is easy to fetch and judged useless (REJECTED) still ranks below the base.
W_USEFUL = 0.75
#: The features a prior is kept on, i.e. what "similar sources" means.
FEATURES = ("host", "producer_type", "country", "language", "data_type")

#: DATA TYPES -- a fixed vocabulary, matched on a source's titles, classes and keywords. A source
#: matching none is UNCLASSIFIED and its salient words become ontology CANDIDATES
#: (`frontier_intel/unknowns.promote_recurring`), never forced into the nearest type.
DATA_TYPES: dict[str, str] = {
    "weather_climate": r"weather|climat|temperatur|rainfall|precipitat|drought|meteo|wetter",
    "energy": r"energy|electric|power\b|\boil\b|petrol|\bgas\b|\blng\b|\bcoal|fuel|crude|refiner|nuclear|solar",
    "agriculture": r"agri|\bcrops?\b|harvest|grain|wheat|\bcorn\b|maize|\bsoy|\brice\b|sugar|coffee|cocoa|cattle|"
                   r"livestock|fertili",
    "shipping_trade": r"shipping|freight|port\b|ports\b|vessel|container|cargo|export|import|"
                      r"trade|customs|tariff",
    "labour": r"labou?r|employ|unemploy|payroll|wage|job|vacanc|hiring",
    "prices": r"price|inflation|cpi\b|ppi\b|consumer price|cost of living|deflator",
    "fiscal": r"fiscal|budget|tax|revenue|expenditure|treasury|public debt|deficit",
    "monetary_rates": r"interest rate|policy rate|monetary|yield|\bbonds?\b|money supply|exchange rate|"
                      r"\bfx\b|currency|central bank|\brepo\b",
    "satellite_eo": r"satellite|sentinel|landsat|modis|earth observation|imagery|ndvi|nightlight|"
                    r"stac|raster",
    "procurement": r"procure|tender|contract award|purchas",
    "payments": r"payment|card spend|transaction|remittanc",
    "production_industry": r"production|industrial|manufactur|output|pmi\b|factory|mining\b|"
                           r"steel|cement",
    "housing_construction": r"housing|house price|construction|building permit|real estate|"
                            r"dwelling|rent\b",
    "transport_mobility": r"traffic|transport|mobility|flight|airline|\brail|vehicle|\broads?\b",
    "health_population": r"health|hospital|mortality|population|census|demograph|birth",
    "environment": r"emission|pollut|air quality|co2|carbon|waste|water quality|biodivers",
    # BROADEST LAST: "index", "bank" and "fund" appear in half of all statistical titles, so
    # every specific type above gets the first claim on a source.
    "markets_finance": r"stock|equity|share price|index|futures|option|credit|loan|bank|"
                       r"financial|securit|fund",
}
_TYPE_RE = {k: re.compile(v, re.IGNORECASE) for k, v in DATA_TYPES.items()}
_STOP = frozenset("""data dataset datasets table tables series statistics statistical annual
monthly weekly daily quarterly total number national report reports value values from with that
this other various information open public index http https www html file files download csv json
xlsx table year years level levels rate rates main their about which where these those under
""".split())
#: Generic second-level labels under a ccTLD (gov.uk, com.au, ...): never a country by themselves.
_GENERIC_TLDS = frozenset({"com", "org", "net", "gov", "edu", "int", "info", "io", "ai", "co",
                           "tv", "me", "app", "dev", "eu", "world", "xyz", "site", "online"})
_TLD_FIX = {"uk": "GB"}
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{4,}")
_TOKEN = re.compile(r"[A-Za-z0-9_]+")
_URL = re.compile(r"https?://[^\s\"'<>)\]}]+")


# ---------------------------------------------------------------------------------- helpers ----
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, path)


def _when(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        got = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat(timespec="seconds") if dt else None


def _min_iso(a: str | None, b: str | None) -> str | None:
    da, db = _when(a), _when(b)
    if da is None:
        return _iso(db)
    if db is None:
        return _iso(da)
    return _iso(min(da, db))


def host_key(url_or_host: str) -> str:
    """Lower-cased host with no scheme, port or leading www."""
    s = str(url_or_host or "").strip().lower()
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s)
    s = s.split("/", 1)[0].split("?", 1)[0].split("@")[-1].split(":", 1)[0]
    return s[4:] if s.startswith("www.") else s


def country_of_host(host: str) -> str:
    """ISO2 from a country-code TLD, else UNMEASURED. `.gov.uk` -> GB; `.com` -> UNMEASURED."""
    parts = host_key(host).split(".")
    tld = parts[-1] if parts else ""
    if len(tld) != 2 or not tld.isalpha() or tld in _GENERIC_TLDS:
        return UNMEASURED
    return _TLD_FIX.get(tld, tld.upper())


def data_type_of(text: str) -> str:
    for name, rx in _TYPE_RE.items():
        if rx.search(text or ""):
            return name
    return "UNCLASSIFIED"


def candidate_words(text: str, k: int = 3) -> list[str]:
    """The salient words of an UNCLASSIFIED source: what an ontology candidate class is named by."""
    words = Counter(w.lower().strip("-") for w in _WORD.findall(text or ""))
    return [w for w, _ in words.most_common() if w not in _STOP and len(w) >= 5][:k]


def iso_week(when: datetime) -> str:
    y, w, _ = when.isocalendar()
    return f"{y}-W{w:02d}"


def _url_h(url: str) -> str:
    return hashlib.sha1(str(url).encode()).hexdigest()[:16]


# ------------------------------------------------------------------------------------ seeds ----
def load_seed_text() -> tuple[str, list[str]]:
    """Every seed the discovery path starts from, lower-cased, as `discovery_audit` reads them."""
    try:
        import discovery_audit as DA
        sources, missing = DA.seed_sources()
    except Exception as exc:  # noqa: BLE001 - an unreadable seed set is named, never read as empty
        return "", [f"discovery_audit.seed_sources: {type(exc).__name__}: {exc}"[:200]]
    return "\n".join(sources.values()).lower(), list(missing)


def seed_hosts(seed_text: str) -> set[str]:
    return {host_key(u) for u in _URL.findall(seed_text or "")}


def is_seeded(host: str, seeded_hosts: set[str], seed_text: str) -> bool:
    """A host any seed names, as a URL host or as a bare string anywhere in a seed."""
    h = host_key(host)
    return not h or h in seeded_hosts or h in (seed_text or "")


# -------------------------------------------------------------------------------- discovery ----
def _file_time(name: str) -> str | None:
    m = re.search(r"(\d{8})(?:[_T](\d{2,4}))?", name)
    if not m:
        return None
    hh = (m.group(2) or "0000").ljust(4, "0")
    try:
        return _iso(datetime.strptime(m.group(1) + hh, "%Y%m%d%H%M").replace(tzinfo=UTC))
    except ValueError:
        return None


def _blank_source(host: str) -> dict[str, Any]:
    return {"host": host, "routes": set(), "first_at": None, "rows": 0, "endpoints": set(),
            "keyed": 0, "country": Counter(), "language": Counter(), "producer_type": Counter(),
            "data_type": Counter(), "candidates": Counter(), "text": []}


def collect_discoveries(world: Path = WORLD, index_dir: Path = INDEX_FOUND,
                        hunter_catalog: Path = HUNTER_CATALOG
                        ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """(host -> what discovery saw of it, endpoint url -> first time it was discovered)."""
    out: dict[str, dict[str, Any]] = {}
    first_ep: dict[str, str] = {}

    def note(host: str, route: str, at: str | None, row: Mapping[str, Any], text: str) -> None:
        h = host_key(host)
        if not h:
            return
        s = out.setdefault(h, _blank_source(h))
        s["routes"].add(route)
        s["first_at"] = _min_iso(s["first_at"], at)
        s["rows"] += 1
        country = str(row.get("country") or "") or country_of_host(h)
        s["country"][country.upper() if len(country) == 2 else country] += 1
        s["language"][str(row.get("lang") or row.get("language") or UNMEASURED)] += 1
        s["producer_type"][str(row.get("producer_type") or UNMEASURED)] += 1
        dt = data_type_of(text)
        s["data_type"][dt] += 1
        if dt == "UNCLASSIFIED":
            s["candidates"].update(candidate_words(text))
        if len(s["text"]) < 5 and text:
            s["text"].append(text[:200])

    for f in sorted(world.glob("discoveries_*.json")):
        rows = _read_json(f, [])
        ftime = _file_time(f.name)
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            route = str(r.get("route") or r.get("source") or "world_crawler")
            at = str(r.get("first_discovered_at") or r.get("published") or ftime or "") or None
            text = " ".join(str(r.get(k) or "") for k in
                            ("title", "observable", "dataset_class", "cluster"))
            text += " " + " ".join(str(x) for x in (r.get("keywords") or [])[:10])
            eps = [str(u) for u in (r.get("endpoints") or []) if str(u).startswith("http")]
            host = str(r.get("host") or "") or host_key(eps[0] if eps else str(r.get("url") or ""))
            note(host, route, at, r, text)
            for u in eps:
                eh = host_key(u)
                if not eh:
                    continue
                if eh != host_key(host):
                    note(eh, route, at, r, text)
                out[eh]["endpoints"].add(u)
                first_ep[u] = _min_iso(first_ep.get(u), at) or first_ep.get(u) or ""
            if host_key(host) in out:
                out[host_key(host)]["keyed"] += len(r.get("keyed_endpoints") or [])
    for f in sorted(index_dir.glob("addresses_*.json")) if index_dir.is_dir() else []:
        rows = _read_json(f, [])
        at = _file_time(f.name)
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and r.get("url"):
                note(str(r["url"]), "index_discovery", at, {}, str(r["url"]))
    cat = _read_json(hunter_catalog, {})
    providers = cat.get("providers") if isinstance(cat, dict) else None
    if isinstance(providers, dict):
        names: dict[str, list[str]] = defaultdict(list)
        for row in (cat.get("datasets") or {}).values():
            if isinstance(row, dict) and len(names[str(row.get("provider"))]) < 8:
                names[str(row.get("provider"))].append(str(row.get("name") or ""))
        for code, p in providers.items():
            if isinstance(p, dict) and p.get("website"):
                note(str(p["website"]), "world_dataset_hunter", p.get("discovered_at"),
                     {"producer_type": "statistics_provider"},
                     " ".join([str(p.get("name") or code), *names.get(str(code), [])]))
    return out, first_ep


# ------------------------------------------------------------------------------ acquisition ----
def acquisition_view(registry: Mapping[str, Any] | None,
                     hunter_catalog: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """host -> what the acquirer (and the hunter) did with it."""
    out: dict[str, dict[str, Any]] = {}
    reg = registry or {}
    series_meta = reg.get("series") or {}
    for url, meta in (reg.get("by_url") or {}).items():
        meta = meta or {}
        h = host_key(str(meta.get("host") or url))
        row = out.setdefault(h, {"series": set(), "acquired_at": None, "attempted_at": None,
                                 "refusals": Counter(), "statuses": Counter(),
                                 "eligible": 0, "insufficient": 0, "access": Counter()})
        row["attempted_at"] = _min_iso(row["attempted_at"], meta.get("at"))
        status = str(meta.get("status") or ("SUCCESS" if meta.get("series") else "REFUSED"))
        row["statuses"][status] += 1
        if meta.get("refusal"):
            row["refusals"][str(meta["refusal"])[:80]] += 1
        for s in meta.get("series") or []:
            row["series"].add(str(s))
            sm = series_meta.get(s) or {}
            row["acquired_at"] = _min_iso(row["acquired_at"],
                                          sm.get("acquired_at") or meta.get("at"))
            if sm.get("research_eligible") is True:
                row["eligible"] += 1
            if sm.get("history_status") == "INSUFFICIENT_HISTORY":
                row["insufficient"] += 1
    for url, acc in (reg.get("access") or {}).items():
        if isinstance(acc, dict):
            h = host_key(url)
            row = out.setdefault(h, {"series": set(), "acquired_at": None, "attempted_at": None,
                                     "refusals": Counter(), "statuses": Counter(),
                                     "eligible": 0, "insufficient": 0, "access": Counter()})
            row["access"][str(acc.get("state") or UNMEASURED).split(":", 1)[0]] += 1
    cat = hunter_catalog or {}
    providers = cat.get("providers") if isinstance(cat, dict) else None
    if isinstance(providers, dict):
        fetched: dict[str, str | None] = {}
        for d in (cat.get("datasets") or {}).values():
            if isinstance(d, dict) and d.get("fetched_at"):
                p = str(d.get("provider"))
                fetched[p] = _min_iso(fetched.get(p), d.get("fetched_at"))
        for code, p in providers.items():
            if isinstance(p, dict) and p.get("website") and fetched.get(str(code)):
                h = host_key(str(p["website"]))
                row = out.setdefault(h, {"series": set(), "acquired_at": None,
                                         "attempted_at": None, "refusals": Counter(),
                                         "statuses": Counter(), "eligible": 0,
                                         "insufficient": 0, "access": Counter()})
                row["acquired_at"] = _min_iso(row["acquired_at"], fetched[str(code)])
                row["statuses"]["HUNTER_FETCHED"] += 1
    return out


# ----------------------------------------------------------------------------------- uses ----
def judged_cells(series_to_host: Mapping[str, str], verdicts: Path = VERDICTS
                 ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """host -> {cells: {cell: passed}, gates: Counter, first_at} from the gauntlet's own ledger.

    A cell belongs to a source when its id names one of the source's series (or `ext_<series>`,
    the primitive name `build_primitives` gives it). Streamed once; absent ledger = UNMEASURED.
    """
    src: dict[str, Any] = {"path": str(verdicts)}
    out: dict[str, dict[str, Any]] = {}
    if not series_to_host:
        return out, {**src, "status": "NO_SERIES_TO_MATCH"}
    if not verdicts.exists():
        return out, {**src, "status": UNMEASURED, "why": "gate verdict ledger absent on this host"}
    names = sorted(series_to_host, key=len, reverse=True)
    rx = re.compile(r"(?<![A-Za-z0-9])(?:ext_)?(" + "|".join(map(re.escape, names))
                    + r")(?![A-Za-z0-9])")
    rows = 0
    try:
        with verdicts.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not rx.search(line):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict) or not r.get("cell"):
                    continue
                blob = " ".join(str(r.get(k) or "") for k in
                                ("cell", "series", "series_key", "inputs", "data", "recipe"))
                hosts = {series_to_host[m.group(1)] for m in rx.finditer(blob)}
                cell = str(r["cell"])
                for h in hosts:
                    rows += 1
                    e = out.setdefault(h, {"cells": {}, "gates": Counter(), "first_at": None,
                                           "first_pass_at": None})
                    e["cells"][cell] = bool(e["cells"].get(cell)) or bool(r.get("passed"))
                    e["first_at"] = _min_iso(e["first_at"], r.get("at"))
                    if r.get("passed"):
                        e["first_pass_at"] = _min_iso(e["first_pass_at"], r.get("at"))
                    else:
                        e["gates"][str(r.get("terminal_gate") or "UNKNOWN")] += 1
    except OSError as exc:
        return out, {**src, "status": f"UNREADABLE: {type(exc).__name__}"}
    return out, {**src, "status": "READ", "matched_rows": rows}


def recorded_reads(series: Iterable[str], use_dir: Path = DATASET_USE) -> int | str:
    """Live consumer reads of these series, or UNMEASURED when no reader records exist at all."""
    if not use_dir.is_dir():
        return UNMEASURED
    try:
        from libs.data import dataset_use as U
        reads = U.census(use_dir)
    except Exception:  # noqa: BLE001
        return UNMEASURED
    return sum(int((reads.get(f"acquired:{s}") or {}).get("live_consumers", 0)) for s in series)


# --------------------------------------------------------------------------------- outcome ----
def decide(acq: Mapping[str, Any] | None, judged: Mapping[str, Any] | None,
           keyed: int = 0) -> tuple[str | None, str, str | None]:
    """(outcome or None, reason, the time the evidence for it first existed). PURE.

    USEFUL / REJECTED read ONLY gauntlet verdicts. LIMITED reads only the acquirer's own refusals
    and access states. Anything else is no outcome yet, with the stage it waits at as the reason.
    """
    cells = dict((judged or {}).get("cells") or {})
    passed = sorted(c for c, ok in cells.items() if ok)
    if passed:
        return ("USEFUL", f"{len(passed)} of {len(cells)} gauntlet-judged cell(s) passed: "
                f"{', '.join(passed[:3])}", (judged or {}).get("first_pass_at"))
    if len(cells) >= MIN_JUDGED_FOR_REJECT:
        gates = Counter((judged or {}).get("gates") or {})
        top = ", ".join(f"{g} x{n}" for g, n in gates.most_common(3)) or "no gate named"
        return ("REJECTED", f"{len(cells)} gauntlet-judged cell(s), none passed; terminal gates: "
                f"{top}", (judged or {}).get("first_at"))
    a = acq or {}
    series = a.get("series") or set()
    if not series:
        statuses = Counter(a.get("statuses") or {})
        refusals = Counter(a.get("refusals") or {})
        access = Counter(a.get("access") or {})
        if statuses and set(statuses) <= {"REFUSED"}:
            why = ", ".join(f"{r} x{n}" for r, n in refusals.most_common(3)) or "refused"
            return ("LIMITED", f"every fetch refused by the acquirer: {why}",
                    a.get("attempted_at"))
        if access or keyed:
            states = ", ".join(f"{s} x{n}" for s, n in access.most_common(3)) or "NEEDS_KEY"
            return ("LIMITED", f"only keyed or held endpoints: {states}", a.get("attempted_at"))
        return None, ("waiting for acquisition" if not statuses
                      else "acquisition in progress"), None
    if cells:
        return None, (f"{len(cells)} cell(s) judged, below the {MIN_JUDGED_FOR_REJECT} a "
                      f"rejection needs"), None
    if int(a.get("eligible") or 0) == 0 and int(a.get("insufficient") or 0) > 0:
        return ("LIMITED", f"{a['insufficient']} series acquired with too little dated history "
                "for research (INSUFFICIENT_HISTORY); accumulating forward",
                a.get("acquired_at"))
    return None, "acquired; waiting for a cell to be judged", None


def _top(c: Counter[str], default: str = UNMEASURED) -> str:
    for k, _ in c.most_common():
        if k and k != UNMEASURED:
            return k
    return default


def build_records(discovered: Mapping[str, Mapping[str, Any]], acq: Mapping[str, Mapping[str, Any]],
                  judged: Mapping[str, Mapping[str, Any]], *, seeded_hosts: set[str],
                  seed_text: str, previous: Mapping[str, Any], now: datetime,
                  use_dir: Path = DATASET_USE) -> tuple[dict[str, Any], dict[str, int]]:
    """One record per UNSEEDED discovered host. Stage stamps are kept from `previous` (first
    reached wins), and an outcome's history is appended when the verdict changes."""
    recs: dict[str, Any] = {}
    seeded = 0
    now_iso = _iso(now)
    for host, d in sorted(discovered.items()):
        if is_seeded(host, seeded_hosts, seed_text):
            seeded += 1
            continue
        old = dict(previous.get(host) or {})
        a = acq.get(host) or {}
        j = judged.get(host) or {}
        series = sorted(a.get("series") or ())
        reads = recorded_reads(series, use_dir) if series else 0
        cells = dict(j.get("cells") or {})
        outcome, reason, evidence_at = decide(a, j, int(d.get("keyed") or 0))
        stages = dict(old.get("stages") or {})
        stages["DISCOVERED"] = _min_iso(stages.get("DISCOVERED"), d.get("first_at")) or now_iso
        if series or a.get("acquired_at"):
            stages["ACQUIRED"] = stages.get("ACQUIRED") or a.get("acquired_at") or now_iso
        if cells or (isinstance(reads, int) and reads > 0):
            stages["USES_TESTED"] = stages.get("USES_TESTED") or j.get("first_at") or now_iso
        hist = list(old.get("outcome_history") or [])
        if outcome:
            if not hist or hist[-1].get("outcome") != outcome:
                hist.append({"outcome": outcome, "at": evidence_at or now_iso, "reason": reason})
            stages["OUTCOME"] = stages.get("OUTCOME") or evidence_at or now_iso
        t0, t1 = _when(stages.get("DISCOVERED")), _when(stages.get("OUTCOME"))
        recs[host] = {
            "host": host, "routes": sorted(d.get("routes") or ()),
            "country": _top(d.get("country") or Counter()),
            "language": _top(d.get("language") or Counter()),
            "producer_type": _top(d.get("producer_type") or Counter()),
            "data_type": _top(d.get("data_type") or Counter(), "UNCLASSIFIED"),
            "candidate_words": [w for w, _ in (d.get("candidates") or Counter()).most_common(3)],
            "sample": list(d.get("text") or [])[:2],
            "endpoints": len(d.get("endpoints") or ()),
            "stages": stages,
            "stage": next(s for s in reversed(STAGES) if stages.get(s)),
            "series": series[:20], "n_series": len(series),
            "recorded_reads": reads,
            "cells_judged": len(cells), "cells_passed": sum(1 for v in cells.values() if v),
            "outcome": outcome, "reason": reason, "outcome_history": hist[-10:],
            "hours_to_outcome": (round((t1 - t0).total_seconds() / 3600.0, 1)
                                 if t0 and t1 else None),
        }
    return recs, {"seeded_hosts_skipped": seeded, "unseeded_records": len(recs)}


# --------------------------------------------------------------------------------- cohorts ----
def _median(xs: Sequence[float]) -> float | None:
    v = sorted(xs)
    if not v:
        return None
    m = len(v) // 2
    return round(v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2.0, 1)


def cohort_row(recs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(recs)
    reached = {s: sum(1 for r in recs if (r.get("stages") or {}).get(s)) for s in STAGES}
    oc = Counter(str(r.get("outcome")) for r in recs if r.get("outcome"))
    judged = oc["USEFUL"] + oc["REJECTED"]
    return {
        "sources": n,
        "share_reaching": {s: round(reached[s] / n, 3) if n else None for s in STAGES},
        "outcomes": {k: oc.get(k, 0) for k in OUTCOMES},
        # THE VALIDITY GUARD IN ONE FIELD: the denominator is gauntlet-judged sources only.
        "useful_rate": round(oc["USEFUL"] / judged, 3) if judged else UNMEASURED,
        "useful_rate_basis": f"{oc['USEFUL']}/{judged} gauntlet-judged sources",
        "median_hours_to_outcome": _median([float(r["hours_to_outcome"]) for r in recs
                                            if r.get("hours_to_outcome") is not None]),
    }


def cohorts(recs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    by: dict[str, dict[str, list[Mapping[str, Any]]]] = {
        k: defaultdict(list) for k in ("country", "language", "data_type", "week", "route")}
    for r in recs.values():
        t0 = _when((r.get("stages") or {}).get("DISCOVERED"))
        by["week"][iso_week(t0) if t0 else UNMEASURED].append(r)
        by["country"][str(r.get("country"))].append(r)
        by["language"][str(r.get("language"))].append(r)
        by["data_type"][str(r.get("data_type"))].append(r)
        for route in r.get("routes") or ["UNMEASURED"]:
            by["route"][str(route)].append(r)
    return {axis: {k: cohort_row(v) for k, v in sorted(groups.items())}
            for axis, groups in by.items()}


def trend(by_week: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Cohorts compared over time: discovery weeks in order, and whether the loop is improving.

    IMPROVING needs the later half of the weeks to beat the earlier half on the share reaching
    an outcome AND not lose useful rate where both halves have one -- speed bought by worse
    verdicts is not improvement. Fewer than two weeks with sources: UNMEASURED."""
    weeks = [(w, r) for w, r in sorted(by_week.items()) if w != UNMEASURED and r["sources"]]
    series = [{"week": w, "sources": r["sources"],
               "share_outcome": r["share_reaching"]["OUTCOME"],
               "share_acquired": r["share_reaching"]["ACQUIRED"],
               "useful_rate": r["useful_rate"],
               "median_hours_to_outcome": r["median_hours_to_outcome"]} for w, r in weeks]
    if len(weeks) < 2:
        return {"weeks": series, "verdict": UNMEASURED,
                "why": f"{len(weeks)} discovery week(s) with sources; a trend needs two"}
    half = len(weeks) // 2

    def pool(rows: list[tuple[str, Mapping[str, Any]]]) -> tuple[float, Any]:
        n = sum(r["sources"] for _, r in rows)
        out = sum(r["share_reaching"]["OUTCOME"] * r["sources"] for _, r in rows) / n if n else 0
        useful = sum(r["outcomes"]["USEFUL"] for _, r in rows)
        judged = useful + sum(r["outcomes"]["REJECTED"] for _, r in rows)
        return out, (useful / judged if judged else None)

    e_out, e_use = pool(weeks[:half])
    l_out, l_use = pool(weeks[half:])
    if e_out == 0 and l_out == 0:
        return {"weeks": series, "verdict": UNMEASURED,
                "why": "no discovery week has a source with an outcome yet: nothing to compare"}
    worse_validity = e_use is not None and l_use is not None and l_use < e_use
    verdict = ("IMPROVING" if l_out > e_out and not worse_validity else
               "DECLINING" if l_out < e_out else "FLAT")
    return {"weeks": series, "verdict": verdict,
            "earlier": {"share_outcome": round(e_out, 3),
                        "useful_rate": round(e_use, 3) if e_use is not None else UNMEASURED},
            "later": {"share_outcome": round(l_out, 3),
                      "useful_rate": round(l_use, 3) if l_use is not None else UNMEASURED},
            "rule": ("later discovery weeks must reach an outcome more often WITHOUT a lower "
                     "gauntlet useful rate; faster at the cost of validity is not improvement")}


# ---------------------------------------------------------------------------------- priors ----
def _score(outcome: str | None) -> tuple[float, float] | None:
    """(useful, acquirable) evidence of one outcome; None = no outcome yet."""
    return {"USEFUL": (1.0, 1.0), "REJECTED": (0.0, 1.0), "LIMITED": (0.0, 0.0)}.get(
        str(outcome)) if outcome else None


def build_priors(recs: Mapping[str, Mapping[str, Any]], *, now: datetime,
                 missions: Sequence[Mapping[str, Any]] = (),
                 backlog_alarm: bool = False) -> dict[str, Any]:
    """Per feature value: a shrunk posterior of (useful, acquirable). The prior a similar source
    inherits is the base rate plus the mean lift of the feature values it shares."""
    scored = [(r, _score(r.get("outcome"))) for r in recs.values()]
    scored = [(r, s) for r, s in scored if s is not None]
    n = len(scored)
    base_u = sum(s[0] for _, s in scored) / n if n else 0.0
    base_a = sum(s[1] for _, s in scored) / n if n else 0.0
    base = round(W_USEFUL * base_u + (1 - W_USEFUL) * base_a, 6) if n else 0.5
    acc: dict[str, dict[str, list[float]]] = {f: defaultdict(lambda: [0.0, 0.0, 0.0])
                                              for f in FEATURES}
    for r, (u, a) in scored:
        for f in FEATURES:
            v = str(r.get(f) or UNMEASURED)
            if v == UNMEASURED:
                continue
            row = acc[f][v]
            row[0] += 1
            row[1] += u
            row[2] += a
    table: dict[str, dict[str, Any]] = {}
    for f, vals in acc.items():
        table[f] = {}
        for v, (k, u, a) in vals.items():
            pu = (u + PRIOR_STRENGTH * base_u) / (k + PRIOR_STRENGTH)
            pa = (a + PRIOR_STRENGTH * base_a) / (k + PRIOR_STRENGTH)
            score = W_USEFUL * pu + (1 - W_USEFUL) * pa
            table[f][v] = {"n": int(k), "useful": round(pu, 4), "acquirable": round(pa, 4),
                           "lift": round(score - base, 6)}
    return {"generated_at": _iso(now), "base": base, "evidence": n, "features": table,
            "missions": [{"key": m.get("key"), "terms": m.get("terms")} for m in missions
                         if m.get("terms")],
            "mission_lift": MISSION_LIFT, "backlog_alarm": bool(backlog_alarm),
            "prior_strength": PRIOR_STRENGTH,
            "rule": ("a REORDER prior: an item's priority is base + the mean lift of the feature "
                     "values it shares with sources that reached an outcome; no evidence = base. "
                     "Nothing is dropped, capped or skipped by it")}


def load_priors(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or PRIORS, {})
    return doc if isinstance(doc, dict) else {}


def features_of(host: str = "", *, country: str = "", language: str = "",
                producer_type: str = "", text: str = "") -> dict[str, str]:
    h = host_key(host)
    return {"host": h, "producer_type": producer_type or UNMEASURED,
            "country": (country or country_of_host(h) or UNMEASURED),
            "language": language or UNMEASURED,
            "data_type": data_type_of(text) if text else UNMEASURED, "_text": text}


def prior_for(feats: Mapping[str, str], priors: Mapping[str, Any]) -> float:
    """base + mean lift over the item's evidenced features (+ a mission bonus), clipped to [0,1]."""
    if not priors:
        return 0.5
    base = float(priors.get("base", 0.5))
    table = priors.get("features") or {}
    lifts = []
    for f in FEATURES:
        row = (table.get(f) or {}).get(str(feats.get(f) or UNMEASURED))
        if row:
            lifts.append(float(row.get("lift", 0.0)))
    score = base + (sum(lifts) / len(lifts) if lifts else 0.0)
    text = str(feats.get("_text") or "") + " " + str(feats.get("host") or "")
    for m in priors.get("missions") or []:
        try:
            if m.get("terms") and re.search(str(m["terms"]), text, re.IGNORECASE):
                score += float(priors.get("mission_lift", MISSION_LIFT))
                break
        except re.error:
            continue
    return max(0.0, min(1.0, score))


def order_by_prior(items: Sequence[Any], feats: Sequence[Mapping[str, str]],
                   priors: Mapping[str, Any], *, ages: Sequence[str] | None = None
                   ) -> tuple[list[Any], dict[str, Any]]:
    """`items` reordered by prior, highest first, stable. NEVER DROPS: same items, same count.

    Under the backlog alarm the OLDEST discovery goes first within equal priors, so the backlog
    drains from its tail rather than its newest arrivals."""
    if len(items) != len(feats):
        raise ValueError("one feature row per item")
    scores = [prior_for(f, priors) for f in feats]
    alarm = bool(priors.get("backlog_alarm"))
    order = sorted(range(len(items)), key=lambda i: (
        -round(scores[i], 6), (str(ages[i] or "9999") if (alarm and ages) else ""), i))
    out = [items[i] for i in order]
    moved = sum(1 for k, i in enumerate(order) if k != i)
    return out, {"applied": bool(priors), "items": len(items), "moved": moved,
                 "evidence": int(priors.get("evidence") or 0),
                 "backlog_alarm": alarm}


# ---------------------------------------------------------------------- ingestion balance ----
def ingestion_balance(first_ep: Mapping[str, str], registry: Mapping[str, Any] | None,
                      flow_state: dict[str, Any], *, now: datetime,
                      days: int = FLOW_DAYS, alarm_days: int = ALARM_DAYS) -> dict[str, Any]:
    """Discovery arrivals vs ingestion completions per day, backlog growth, and the alarm.

    Arrivals: discovered endpoint URLs by the day first discovered. Completions: those same URLs
    by the day the acquirer's registry first held a row for them (stamped here on first sight and
    kept in `flow.json`, because the registry keeps only the latest attempt). Mutates
    `flow_state` with new first-sighting stamps."""
    if registry is None:
        return {"status": UNMEASURED, "why": "acquirer registry absent on this host"}
    seen: dict[str, str] = flow_state.setdefault("processed", {})
    by_url = registry.get("by_url") or {}
    disc_h = {_url_h(u): u for u in first_ep}
    for u, meta in by_url.items():
        h = _url_h(u)
        if h in disc_h and h not in seen:
            at = _when((meta or {}).get("at")) or now
            seen[h] = at.date().isoformat()
    today = now.date()
    start = today - timedelta(days=days - 1)
    arrivals: Counter[str] = Counter()
    before_arr = 0
    for at in first_ep.values():
        d = (_when(at) or now).date()
        if d < start:
            before_arr += 1
        else:
            arrivals[d.isoformat()] += 1
    completions: Counter[str] = Counter()
    before_done = 0
    for h, day in seen.items():
        if h not in disc_h:
            continue
        try:
            d = date.fromisoformat(day)
        except ValueError:
            continue
        if d < start:
            before_done += 1
        else:
            completions[d.isoformat()] += 1
    rows = []
    backlog = before_arr - before_done
    for k in range(days):
        d = (start + timedelta(days=k)).isoformat()
        backlog += arrivals[d] - completions[d]
        rows.append({"day": d, "arrivals": arrivals[d], "completions": completions[d],
                     "backlog": backlog})
    complete_days = rows[:-1]                      # today is still running
    run = 0
    for r in reversed(complete_days):
        if r["arrivals"] > r["completions"]:
            run += 1
        else:
            break
    week = complete_days[-7:]
    growth = (round((week[-1]["backlog"] - week[0]["backlog"]) / max(1, len(week) - 1), 2)
              if len(week) >= 2 else UNMEASURED)
    alarm = run >= alarm_days
    return {
        "status": "MEASURED", "days": rows, "backlog_now": rows[-1]["backlog"] if rows else 0,
        "backlog_growth_per_day_7d": growth,
        "arrivals_outran_completions_days_running": run, "alarm_after_days": alarm_days,
        "alarm": alarm,
        "response": ({"action": "REORDER",
                      "detail": ("acquire_datasets raises the discovered-endpoint share of its "
                                 "pass from 1/4 to 1/2 and takes the oldest backlog first within "
                                 "equal priors (priors.json backlog_alarm)"),
                      "mining_cut": False}
                     if alarm else {"action": "NONE", "mining_cut": False}),
        "rule": ("the response to discovery outrunning ingestion is a reorder or a priority "
                 "change toward ingestion, NEVER a cut to mining: mining_cut is always false"),
    }


# -------------------------------------------------------------------------------- missions ----
def load_missions(path: Path = EXTENSION) -> list[dict[str, Any]]:
    """Promoted ontology classes (frontier_intel/unknowns.promote_recurring) as missions."""
    doc = _read_json(path, {})
    rows = doc.get("classes") if isinstance(doc, dict) else None
    out = []
    for r in rows or []:
        if isinstance(r, dict) and r.get("terms"):
            out.append({"key": f"{r.get('group')}:{r.get('name')}", "terms": str(r["terms"])})
    return out


def settle_missions(missions: Sequence[Mapping[str, Any]], recs: Mapping[str, Mapping[str, Any]],
                    queue_path: Path = QUEUE) -> dict[str, Any]:
    """A mission is MET when an unseeded source matching its terms reached ACQUIRED; its queue
    task (information lane, `acquire_class`) is then completed, which queues the linked strategy
    task. Missing queue: UNMEASURED, never 'no missions'."""
    met: list[dict[str, Any]] = []
    open_: list[str] = []
    for m in missions:
        try:
            rx = re.compile(str(m["terms"]), re.IGNORECASE)
        except re.error:
            continue
        hit = next((r for r in recs.values() if (r.get("stages") or {}).get("ACQUIRED")
                    and rx.search(" ".join([*r.get("sample", []), *r.get("candidate_words", []),
                                            str(r.get("host"))]))), None)
        if hit:
            met.append({"key": m["key"], "source": hit["host"]})
        else:
            open_.append(str(m["key"]))
    completed: list[str] = []
    queue_state = "READ" if queue_path.exists() else UNMEASURED
    if met and queue_path.exists():
        try:
            from libs.ops.task_queue import TaskQueue
            q = TaskQueue(queue_path)
            queue_state = "READ"
            for t in q.tasks().values():
                if t.kind != "acquire_class" or t.state not in ("READY", "LEASED"):
                    continue
                hit2 = next((x for x in met if x["key"] == t.payload.get("key")), None)
                if hit2 and q.complete(t.id, why=f"met by {hit2['source']}",
                                       produced={"source": hit2["source"]}):
                    completed.append(str(hit2["key"]))
        except Exception as exc:  # noqa: BLE001
            queue_state = f"UNREADABLE: {type(exc).__name__}"
    return {"missions": len(missions), "met": met, "open": open_,
            "queue_tasks_completed": completed, "queue": queue_state}


# ---------------------------------------------------------------------------- the guard ----
def validity_guard(recs: Mapping[str, Mapping[str, Any]], verdicts_src: Mapping[str, Any]
                   ) -> dict[str, Any]:
    """Show that the useful rate comes only from gauntlet verdicts and that the loop's cells are
    charged to the shared trial count. Raises on a USEFUL/REJECTED with no judged cell."""
    bad = [h for h, r in recs.items()
           if r.get("outcome") in ("USEFUL", "REJECTED") and not r.get("cells_judged")]
    if bad:
        raise AssertionError(f"verdict without a gauntlet-judged cell: {bad[:5]}")
    cells = sum(int(r.get("cells_judged") or 0) for r in recs.values())
    basis: Any = UNMEASURED
    with contextlib.suppress(Exception):
        import gate_policy as GP
        basis = GP.TRIAL_COUNT_BASIS
    return {
        "useful_from": "gate_verdict_ledger.jsonl passed rows only",
        "verdicts": dict(verdicts_src),
        "loop_cells_judged": cells,
        "loop_cells_outside_the_gauntlet": 0,
        "trial_count_basis": basis,
        "charged_to": ("the shared standing campaign charge (gate_policy.charged_trial_count) "
                       "every gauntlet-judged cell pays; the loop runs no test of its own"),
        "returns_looked_at_by_this_organ": 0,
    }


# --------------------------------------------------------------------------- weakness-fix ----
def weakness_fix(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """DATA-51: every organ this change added names the measured weakness it fixes and the metric
    that shows the fix, with that metric's value from THIS pass (or UNMEASURED by name)."""
    queue = _read_json(DESK / "reports" / "QUEUE.json", None)
    lanes = ((queue or {}).get("produced") or {}).get("lanes") if isinstance(queue, dict) else None
    ext = _read_json(EXTENSION, None)
    acq = _read_json(DESK / "reports" / "dataset_acquisition.json", None)
    loop = doc.get("loop") or {}
    return [
        {"organ": "research/discovery_loop.py (ledger + cohorts)",
         "weakness": ("no unseeded source could be traced from discovery through acquisition and "
                      "tested uses to a recorded outcome (audit ARCH-22)"),
         "metric": "loop.unseeded_with_outcome",
         "value": loop.get("unseeded_with_outcome", UNMEASURED)},
        {"organ": "discovery_loop priors -> acquire_datasets / catalog_routes ordering",
         "weakness": ("a source's verdict never changed what was fetched next: discovered "
                      "endpoints were ordered by file recency alone"),
         "metric": "dataset_acquisition.json loop_prior.moved / priors.evidence",
         "value": ((acq or {}).get("loop_prior") if isinstance(acq, dict) else None)
         or {"evidence": (doc.get("priors") or {}).get("evidence", UNMEASURED),
             "acquisition": UNMEASURED}},
        {"organ": "discovery_loop ingestion_balance",
         "weakness": ("nothing paired discovery arrivals with ingestion completions, so a "
                      "discovery surge could bury the acquirer unseen"),
         "metric": "ingestion_balance.backlog_growth_per_day_7d / alarm",
         "value": {k: (doc.get("ingestion_balance") or {}).get(k, UNMEASURED)
                   for k in ("backlog_growth_per_day_7d", "alarm")}},
        {"organ": "libs/ops/task_queue.py lanes + queue_cycle `lanes` producer",
         "weakness": ("one queue with no release timing, no per-host rate limit and no "
                      "targeted invalidation; a new data version re-ran nothing or everything"),
         "metric": "QUEUE.json produced.lanes (invalidated vs untouched, waiting_release)",
         "value": ({k: lanes.get(k, UNMEASURED) for k in
                    ("drained_information", "affected_total", "untouched_total", "lineage_rows",
                     "rate_limits_added", "next_eligible_at")}
                   if isinstance(lanes, dict) else UNMEASURED)},
        {"organ": "frontier_intel/unknowns.py promote_recurring + main",
         "weakness": ("the frontier_unknowns leg exited 1 every hour (relative import as a "
                      "script, measured 2026-10-07) and candidate classes never left the log"),
         "metric": "ontology_extension.json classes (auto-promoted, with provenance)",
         "value": (len(ext.get("classes") or []) if isinstance(ext, dict) else UNMEASURED)},
    ]


# --------------------------------------------------------------------------------- the pass ----
def run(*, now: datetime | None = None, write: bool = True,
        seed_text: str | None = None, world: Path = WORLD, index_dir: Path = INDEX_FOUND,
        hunter_catalog: Path = HUNTER_CATALOG, registry_path: Path = REGISTRY,
        verdicts: Path = VERDICTS, use_dir: Path = DATASET_USE, state_dir: Path = STATE_DIR,
        extension: Path = EXTENSION, queue_path: Path = QUEUE,
        report: Path = REPORT) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    missing: list[str] = []
    if seed_text is None:
        seed_text, missing = load_seed_text()
    seeded = seed_hosts(seed_text)
    discovered, first_ep = collect_discoveries(world, index_dir, hunter_catalog)
    registry = _read_json(registry_path, None)
    registry = registry if isinstance(registry, dict) else None
    hunter = _read_json(hunter_catalog, {})
    acq = acquisition_view(registry, hunter if isinstance(hunter, dict) else {})
    unseeded = {h for h in discovered if not is_seeded(h, seeded, seed_text)}
    series_to_host = {s: h for h in unseeded for s in (acq.get(h) or {}).get("series") or ()}
    judged, vsrc = judged_cells(series_to_host, verdicts)
    ledger_path = state_dir / LEDGER.name
    prev = _read_json(ledger_path, {})
    recs, counts = build_records(discovered, acq, judged, seeded_hosts=seeded,
                                 seed_text=seed_text,
                                 previous=(prev.get("records") or {}) if isinstance(prev, dict)
                                 else {}, now=now, use_dir=use_dir)
    flow_path = state_dir / FLOW.name
    flow_state = _read_json(flow_path, {})
    flow_state = flow_state if isinstance(flow_state, dict) else {}
    balance = ingestion_balance(first_ep, registry, flow_state, now=now)
    missions = load_missions(extension)
    priors = build_priors(recs, now=now, missions=missions,
                          backlog_alarm=bool(balance.get("alarm")))
    by = cohorts(recs)
    overall = cohort_row(list(recs.values()))
    loop = {
        **counts, "seeds_unreadable": missing,
        "unseeded_with_outcome": sum(1 for r in recs.values() if r.get("outcome")),
        "by_stage": dict(Counter(r["stage"] for r in recs.values())),
        "overall": overall,
        "repeats_across": {axis: sum(1 for k, row in by[axis].items()
                                     if k not in (UNMEASURED, "UNCLASSIFIED")
                                     and sum(row["outcomes"].values()) > 0)
                           for axis in ("country", "language", "data_type")},
    }
    hist_path = state_dir / HISTORY.name
    history = [json.loads(x) for x in _tail(hist_path, 400)]
    snap = {"at": _iso(now), "sources": overall["sources"],
            "share_outcome": overall["share_reaching"]["OUTCOME"],
            "useful_rate": overall["useful_rate"],
            "median_hours_to_outcome": overall["median_hours_to_outcome"]}
    doc: dict[str, Any] = {
        "generated_at": _iso(now),
        "label": "unseeded sources only: a host no seed roster, seed endpoint, pack or organ "
                 "URL literal names (discovery_audit.seed_sources)",
        "stages": list(STAGES), "outcomes": list(OUTCOMES),
        "loop": loop,
        "cohorts": by,
        "trend": trend(by["week"]),
        "pass_history": [*history[-23:], snap],
        "validity_guard": validity_guard(recs, vsrc),
        "priors": {"path": str(state_dir / PRIORS.name), "base": priors["base"],
                   "evidence": priors["evidence"], "backlog_alarm": priors["backlog_alarm"],
                   "missions": len(priors["missions"]),
                   "features_with_evidence": {f: len(v) for f, v in priors["features"].items()}},
        "ingestion_balance": balance,
        "missions": settle_missions(missions, recs, queue_path) if write else
        {"missions": len(missions), "dry_run": True},
        "records": dict(sorted(recs.items(), key=lambda kv: (
            -STAGES.index(kv[1]["stage"]), kv[0]))[:300]),
        "records_omitted": max(0, len(recs) - 300),
    }
    doc["weakness_fix"] = weakness_fix(doc)
    if write:
        _atomic(ledger_path, {"generated_at": _iso(now), "records": recs})
        _atomic(state_dir / PRIORS.name, priors)
        _atomic(flow_path, flow_state)
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [*_tail(hist_path, HISTORY_KEEP - 1), json.dumps(snap)]
        hist_path.write_text("\n".join(lines) + "\n", "utf-8")
        _atomic(report, doc)
    return doc


def _tail(path: Path, n: int) -> list[str]:
    try:
        lines = [x for x in path.read_text("utf-8").splitlines() if x.strip()]
    except OSError:
        return []
    out = []
    for x in lines[-n:]:
        try:
            json.loads(x)
        except ValueError:
            continue
        out.append(x)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="compute, print, write nothing")
    args = ap.parse_args(argv)
    doc = run(write=not args.dry_run)
    loop = doc["loop"]
    print(f"discovery loop: {loop['unseeded_records']} unseeded source(s) "
          f"({loop['seeded_hosts_skipped']} seeded skipped), stages {loop['by_stage']}, "
          f"{loop['unseeded_with_outcome']} with an outcome")
    print(f"  useful rate {loop['overall']['useful_rate']} ({loop['overall']['useful_rate_basis']})"
          f"; trend {doc['trend']['verdict']}")
    b = doc["ingestion_balance"]
    print(f"  ingestion: backlog {b.get('backlog_now', UNMEASURED)}, growth/day "
          f"{b.get('backlog_growth_per_day_7d', UNMEASURED)}, alarm {b.get('alarm', UNMEASURED)}")
    print(f"  priors: base {doc['priors']['base']}, evidence {doc['priors']['evidence']}"
          + ("" if args.dry_run else f" -> {REPORT}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
