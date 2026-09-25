#!/usr/bin/env python3
"""THE COVERAGE DRAIN -- the uncrawled set falls every hour, or the law gate says why.

    "an institution built on ALL global public information"          -- the principal

THE GAP THIS ORGAN EXISTS TO CLOSE. The desk has two different quantities and had been reading
only one of them. The first is WHAT IT HOLDS: rows in the registry's `sources` table that
something actually fetched. The second is WHAT IT COULD LAWFULLY HOLD: every root its own
country packs declare, every ground in `deep_forest_sources.json`, every source the scouts and
the evidence router registered and nothing ever went back for. On 2026-09-23 the second exceeded
the first by 148 rows, the oldest of them had been waiting 134 hours, and
`research/loop_liveness.py` called the whole `sources_ingested` stage STALLED. Nothing owned
that number. This organ owns it.

WHAT IT DOES, IN ONE PASS, AND WHY IN THIS ORDER.

  1. SEED. Every source layer every country pack declares becomes a registry row, tagged with
     its country, its language, its layer and its access label. A root a pack names and the
     registry has never heard of is the purest form of the gap: the desk KNOWS the ground exists
     and has not written it down where the crawlers look. Seeding RAISES the uncrawled count on
     purpose, which is why the ratchet below is not on that count (see THE RATCHET).
  2. RESOLVE. Sixty of the 148 pending rows carried NO URL AT ALL -- registry rows minted by
     `evidence_router` from a seat name with no root beside it. A crawler cannot fetch a name.
     Each is resolved against the source registry, the deep-forest grounds and the packs' own
     roots; what resolves gets its `url` filled and joins the drainable set, and what does not is
     registered as a PERMANENT REFUSAL (`NO_ROOT_KNOWN`) rather than sitting in the queue for
     another 134 hours pretending to be work.
  3. LABEL, AND REFUSE ONLY THE FIVE ACTS. LAWS 5e (2026-09-23) is explicit and it is newer
     than most of the code around this organ: licence, terms, robots and
     `machine_use_allowed=false` are ROUTING AND PROVENANCE LABELS on the row -- they say what the
     desk may REDISTRIBUTE, never whether it may READ. The section NAMES
     "`machine_use_allowed=false` read as registered, never scraped" as a deleted brake that no
     session may re-introduce in any form. So this organ mines those rows and carries the terms
     note with them. What is refused is the principal's five ACTS -- credential theft, bypassing
     an access control or paywall, MNPI, stolen or leaked private data, personal-data harvesting
     -- which arrive as the three refused access labels (PRIVATE, CONFIDENTIAL_MNPI,
     STOLEN_UNAUTHORIZED), a declared authenticated surface or declared MNPI. Those are stamped
     with their reason and never queued again. THE REFUSAL IS STILL KNOWLEDGE: the row is kept,
     because dropping it would lose the fact that the ground exists.
  4. DRAIN. What is left is crawled through the machinery that already exists --
     `research/moat_collectors.py`, which owns the robots probe, the media typing, the collectors,
     the point-in-time capture and the claim writer -- with the budget spent OLDEST AND HIGHEST
     ROI FIRST. This organ adds no second crawler and no second set of manners.
  5. VERIFY THE TEN LAYERS. `libs/research/coverage.py` says a country is COVERED only when every
     source layer is MAPPED or declared ABSENT WITH A REASON. Most packs' layers read
     DECLARED_UNVERIFIED -- the pack names a root and `verified` is hard-coded False, because a
     pack cannot verify itself. This organ verifies them from the OUTSIDE: a layer is MAPPED when
     a registry row whose host matches one of that layer's declared roots carries a `last_crawled`
     stamp. Declared becomes measured, and the pack never has to claim anything.
  6. PUBLISH THE SINGLE LARGEST GAP. `desks/mt5/reports/COVERAGE_DRAIN.json` names, by expected
     value, the one piece of information the desk is most missing -- so the bottleneck is a line
     somebody reads every morning instead of a number nobody computes.

THE RATCHET, AND WHY IT IS NOT ON THE HEADLINE COUNT. `scripts/check_coverage_drain.py` fails the
law gate when the backlog RISES. But this organ's own first duty is to SEED lawful ground the
registry had never heard of, which raises the uncrawled count -- and a fence that punished that
would teach the next session to stop seeding, which is the exact opposite of the order. So three
quantities are ratcheted and each is the honest one for its job:

  * `backlog_overdue` -- rows pending LONGER THAN THE LEASE. May fall, never rise. A newly seeded
    root is not overdue; a root that has waited a day is. This is the failing metric.
  * `overdue_wait_h` -- how far the oldest wait EXCEEDS the lease, `max(0, oldest - LEASE_H)`.
    May fall, never rise. NOT `oldest_wait_h` itself, and the difference cost a red gate to
    learn: the raw wait rises by 0.3 when eighteen minutes pass, so the fence failed on
    arithmetic that no amount of draining can reverse inside a pass. A wait UNDER the lease is
    the queue working as designed; only the part ABOVE it is neglect, and that part is zero
    while the drain keeps up. `oldest_wait_h` is still published, just not fenced.
  * `drained_total` -- cumulative rows moved out of the uncrawled set. May rise, never fall.

and `uncrawled_total` is published with its own ceiling, failing ONLY when it rises in a pass that
seeded nothing -- a rise with no new ground is a genuine regression and a rise with new ground is
the organ working.

BOUNDARIES, AS LAWS 5e STATES THEM TODAY. Everything reachable on the open internet without
breaking in is mined, and the label travels with the row. No access control and no paywall is
ever bypassed; no credential is ever used; no MNPI, no stolen or leaked private data and no
personal-data harvesting. Those five ACTS are the whole of the restriction and there is no sixth
-- "the absence of a rule is a permission, not a reason for caution". Nothing here classifies a
source in order to BRAKE discovery: a terms note lowers what may be republished and changes
nothing about what may be read (growth governance Rule 1). No crypto-exchange-native ground is
hunted (mandate 2026-08-18). Nothing here sizes, allocates or touches the money path.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import closing, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "side_channels"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "COVERAGE_DRAIN.json"
LEDGER = DESK / "data" / "coverage_drain_ledger.json"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"
DEEP_FOREST = DESK / "data" / "deep_forest_sources.json"
SOURCE_REGISTRY = DESK / "data" / "source_registry.json"
#: The hard-data plane: official, exchange, physical and flow grounds, one row per declared MT5
#: transmission path. The THIRD registry, and the one this organ was not reading.
PLANE_REGISTRY = DESK / "data" / "asia_sources.json"
SOURCE = "coverage_drain"

#: The bucket for a ground whose country is blank and whose host is on a generic TLD. It is a
#: NAMED bucket and never a region, because folding an unknown jurisdiction into one would make
#: that region read deeper than it is -- the exact error that hid five empty regions for a week.
UNMAPPED_REGION = "UNMAPPED"

#: How long a registered source may sit uncrawled before it is a DEFECT rather than a queue.
#: One day: the crawl clock is hourly, so a row that has survived twenty-four passes was not
#: waiting its turn, it was being skipped.
LEASE_H = 24.0
#: Refusals, as registered permanent facts. A refusal is stamped so the row leaves the pending
#: set, and it keeps its reason forever so the knowledge that the ground EXISTS is never lost.
#:
#: TWO ONLY, AND NEITHER IS A LEGAL OPINION ABOUT CONTENT. `refused-hard-boundary` carries the
#: principal's five refused ACTS (LAWS 5e), which reach this organ as the three refused access
#: labels or a declared authenticated/MNPI surface. `refused-no-root` is not a legal refusal at
#: all -- it is the factual statement that there is nothing to fetch. The statuses this organ
#: USED to carry, `refused-machine-use` and `refused-robots`, are named in `REMOVED_BRAKES` and
#: are kept in this tuple for ONE reason: rows stamped with them by an earlier build must still
#: be recognised as refusals rather than read as successful crawls.
REFUSAL_STATUSES: tuple[str, ...] = ("refused-hard-boundary", "refused-no-root",
                                     "refused-machine-use", "refused-robots",
                                     "refused-unreachable")
#: The refused access labels, read from the classifier when it is reachable so this organ can
#: never drift from the law's own list.
REFUSED_LABELS: tuple[str, ...] = ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
#: The status a resolved, drainable row is cleared to. `moat_collectors.ACTIVE_STATUSES` accepts
#: it, which is the whole point: this organ clears the path, that organ does the fetching.
CLEARED = "candidate-cleared"
#: Registry-row prefixes an ORGAN mints about the desk's own state rather than about a ground on
#: the web. They can never carry a url and must not read as a lost root.
INTERNAL_PREFIXES: frozenset[str] = frozenset({
    "world_lab", "execution_tape", "regime", "shadow", "lane", "sleeve", "forecast", "book"})
#: The layer states in which the desk has done everything it lawfully can and SAID SO: the
#: root was fetched, the layer was declared absent with a reason, or every declared host is
#: a registered legal refusal. The other two -- DECLARED_UNVERIFIED and UNMAPPED -- are work.
LAYER_SETTLED: tuple[str, ...] = ("MAPPED", "ABSENT_DECLARED", "REFUSED_HARD_BOUNDARY")
#: The ten source layers, borrowed rather than re-declared.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

RULE = ("the uncrawled set falls every hour: overdue backlog and oldest wait ratchet DOWN, "
        "drained total ratchets UP, every refusal is a permanent registered fact with its rule "
        "and its date, and the only refusals are the principal's five ACTS (LAWS 5e) -- a "
        "terms, licence, robots or machine_use_allowed label travels with the row and never "
        "stops it being read")


# --------------------------------------------------------------------------------- small tools
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _age_h(stamp: Any, now: datetime | None = None) -> float | None:
    """Hours since an ISO stamp, or None when it cannot be read. Never raises."""
    text = str(stamp or "").strip()
    if not text:
        return None
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0


def host_of(url: str) -> str:
    """The bare host of a url or a root, lowercased, `www.` kept. "" when there is none."""
    text = str(url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    with suppress(ValueError):
        return (urlparse(text).netloc or "").lower()
    return ""


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=False, ensure_ascii=False,
                              default=str), encoding="utf-8")
    os.replace(tmp, path)


def budget_seconds(requested: float) -> float:
    """The pass budget, never larger than what this machine can actually spend on it.

    DERIVED, NOT TYPED. The trading box and the build box differ by an order of magnitude in RAM
    and the desk has broken itself once already by sizing a floor off the other machine's number
    (CLAUDE.md, 2026-09-15). This organ's cost is network wait rather than memory, so the bound
    that matters is the clock -- but when the box is under memory pressure the crawl is the first
    thing that should shorten, so the budget is scaled by measured free memory when it can be
    read and left exactly as asked when it cannot.
    """
    want = max(30.0, float(requested))
    try:
        import psutil  # type: ignore[import-untyped]
        free_mb = float(psutil.virtual_memory().available) / (1024.0 * 1024.0)
    except Exception:
        return want
    if free_mb <= 0.0:
        return want
    # Below 512 MB free the box is thrashing and a long crawl makes it worse; above 2 GB the
    # clock is the only bound. Between them the budget slides, floored at a third of the ask so
    # a pass always does SOME work rather than degenerating into a no-op that still counts.
    if free_mb >= 2048.0:
        return want
    scale = max(1.0 / 3.0, free_mb / 2048.0)
    return max(30.0, want * scale)


# ------------------------------------------------------------------------------- the registry
def connect(db: Path | None = None) -> sqlite3.Connection | None:
    """The alpha registry, or None with no exception. An absent registry is UNMEASURED."""
    target = Path(db) if db is not None else REGISTRY_DB
    if not target.exists():
        return None
    try:
        conn = sqlite3.connect(str(target), timeout=30.0)
    except sqlite3.Error:
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _has_sources(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    except sqlite3.Error:
        return False
    return "sources" in {str(r[0]) for r in rows}


def pending_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every registry source nothing has ever fetched. The set this organ exists to shrink."""
    if not _has_sources(conn):
        return []
    try:
        cur = conn.execute("SELECT * FROM sources WHERE last_crawled IS NULL OR last_crawled=''")
    except sqlite3.Error:
        return []
    return [dict(r) for r in cur.fetchall()]


def crawled_hosts(conn: sqlite3.Connection) -> dict[str, str]:
    """{host: newest last_crawled} over every source that was ACTUALLY FETCHED.

    This is the measurement the ten-layer verification stands on: a pack's declared root is
    VERIFIED when a row for that host carries a stamp. Nothing here reads the pack's own
    `verified` field, which is hard-coded False by every pack and always will be -- a pack that
    could verify itself would not be evidence of anything.

    A REFUSAL IS STAMPED TOO, AND IT IS EXCLUDED HERE. The stamp is what stops a refused row
    re-queueing every hour; it is not evidence that anything was read. Measured on the first live
    pass: 113 pack sources carry `machine_use_allowed=false`, every one was registered and
    stamped in the same step, and counting their hosts as fetched moved `layers_mapped` from 57
    to 184 without a single page having been read. `refused_hosts` below is where they belong.
    """
    out: dict[str, str] = {}
    for url, status, stamp, _why in _stamped_rows(conn):
        if status in REFUSAL_STATUSES or not stamp:
            continue
        host = host_of(url)
        if host and stamp > out.get(host, ""):
            out[host] = stamp
    return out


def refused_hosts(conn: sqlite3.Connection) -> dict[str, str]:
    """{host: the refusal reason} over every source refused at the five-act hard boundary.

    A layer whose only declared hosts are refused is NOT unverified work: the desk has done
    everything it lawfully can and the answer is a registered legal fact. That is a different
    state from "nobody has got round to it", and conflating the two hides the one the desk can
    actually act on. Rows stamped by an earlier build with the now-deleted `refused-machine-use`
    and `refused-robots` statuses are counted here too -- they are not evidence of a fetch, and
    re-crawling them is the drain's ordinary work once they are re-cleared.
    """
    out: dict[str, str] = {}
    for url, status, _stamp, why in _stamped_rows(conn):
        if status not in REFUSAL_STATUSES:
            continue
        host = host_of(url)
        if host:
            out.setdefault(host, why or status or "refused")
    return out


def _stamped_rows(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    """(url, status, last_crawled, route_reason) for every source row, partitioned in PYTHON.

    The refusal statuses are a module constant, so the SQL would be a safe parameterised `IN`
    -- but it would be BUILT by string formatting, and a fence that flags that pattern is right
    to, because the next person to edit the line will not be formatting a row of `?` marks. The
    table is a few thousand rows; the filter is free here and the pattern stays out of the tree.
    """
    if not _has_sources(conn):
        return []
    try:
        cur = conn.execute("SELECT url, status, last_crawled, route_reason FROM sources")
    except sqlite3.Error:
        return []
    return [(str(r["url"] or ""), str(r["status"] or ""), str(r["last_crawled"] or ""),
             str(r["route_reason"] or "")) for r in cur.fetchall()]


# ------------------------------------------------------------------------- the lawful grounds
def _countries() -> Any:
    """The `countries` package, or None. Imported by NAME rather than statically: the package
    lives under `desks/mt5/research` and is reachable as `countries` or as `research.countries`
    depending on which root a caller put on the path, and an organ that only works from one of
    them is an organ that silently measures nothing from the other."""
    import importlib
    for name in ("countries", "research.countries"):
        with suppress(Exception):
            return importlib.import_module(name)
    return None


def _pack_module(code: str) -> Any:
    """One country pack module, or None. One failing pack never costs the other forty."""
    import importlib
    for prefix in ("countries", "research.countries"):
        with suppress(Exception):
            return importlib.import_module(f"{prefix}.{code}.pack")
    return None


def pack_sources() -> list[dict[str, Any]]:
    """Every root every country pack declares, one row per (pack, layer, source).

    THE PACKS ARE THE DESK'S OWN STATEMENT OF WHAT GROUND EXISTS. Forty-odd departments each
    name ten layers of sources in their own language, and until this organ ran none of those
    roots was a registry row -- so the crawlers could not reach them and `coverage.covered()`
    could never move a single layer off DECLARED_UNVERIFIED. Read defensively: one pack that
    fails to import must not cost the other forty.
    """
    out: list[dict[str, Any]] = []
    pkg = _countries()
    if pkg is None:
        return out
    for code in pkg.codes():
        mod = _pack_module(code)
        if mod is None:
            continue
        classes = getattr(mod, "SOURCE_CLASSES", ()) or ()
        iso = tuple(str(c).lower() for c in (getattr(mod, "JURISDICTIONS", None) or (code,)))
        langs = tuple(str(x) for x in (getattr(mod, "NATIVE_LANGUAGES", ()) or ()))
        for sc in classes:
            if not isinstance(sc, Mapping):
                continue
            sid = str(sc.get("id") or "")
            layer = str(sc.get("layer") or "")
            if not sid or sid.startswith("absent_") or layer not in SOURCE_LAYERS:
                continue
            roots = [str(r) for r in (sc.get("roots") or ()) if str(r).strip()]
            if not roots:
                continue
            out.append({
                "source_id": f"pack:{code}:{layer}:{sid}",
                "url": roots[0], "alt": tuple(roots[1:]), "kind": layer, "pack": code,
                "country": iso[0] if iso else code,
                "language": (str(sc.get("languages") or (langs[0] if langs else ""))
                             if not isinstance(sc.get("languages"), (list, tuple))
                             else ",".join(str(x) for x in sc["languages"])),
                "access_label": str(sc.get("access_label") or ""),
                "credibility": str(sc.get("credibility") or ""),
                "machine_use_allowed": bool(sc.get("machine_use_allowed", True)),
                "licence": str(sc.get("licence") or ""),
                "label": str(sc.get("label") or sid),
            })
    return out


def forest_grounds(path: Path | None = None) -> list[dict[str, Any]]:
    """The registered deep-forest grounds, as candidate registry rows.

    `desks/mt5/data/deep_forest_sources.json` is where new grounds are ADDED rather than
    hard-coded (CLAUDE.md, deep-forest mining order). Five hundred of them, each with a region,
    a language and a url -- and a ground that is not in the registry is a ground the ROI
    scheduler cannot spend an hour on.
    """
    doc = _read_json(path or DEEP_FOREST, {})
    rows = doc.get("grounds") if isinstance(doc, Mapping) else None
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        name = str(row.get("name") or url)
        region = str(row.get("region") or "")
        out.append({
            "source_id": f"forest:{region or 'world'}:{host_of(url) or name}",
            "url": url, "alt": tuple(str(a) for a in (row.get("alt") or ())),
            "kind": str(row.get("kind") or "practitioner"), "pack": "",
            "country": region, "language": str(row.get("language") or ""),
            "access_label": "PUBLIC", "credibility": "UNKNOWN",
            "machine_use_allowed": True, "licence": "public web",
            "label": name,
        })
    return out


def registry_grounds(path: Path | None = None) -> list[dict[str, Any]]:
    """The source registry's own 639 rows, as candidate registry rows.

    READ DIRECTLY, NOT THROUGH `source_shares.load()`. That loader refuses a report older than
    its staleness window and returns NOTHING -- correctly, because a stale SHARE is not a budget.
    But a stale ROOT is still a root: `desks/mt5/data/source_registry.json` is a registered fact
    file, and refusing to read a ground's url because last week's ROI numbers went stale is how
    sixty rootless rows sat in the queue for 134 hours with their roots already written down two
    directories away.
    """
    doc = _read_json(path or SOURCE_REGISTRY, {})
    rows = doc.get("sources") if isinstance(doc, Mapping) else None
    out: list[dict[str, Any]] = []
    for sid, row in dict(rows or {}).items():
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        allowed = (row.get("machine_use_allowed") is not False
                   and str(row.get("route") or "") != "unreachable"
                   and not row.get("snippets_only"))
        out.append({
            "source_id": str(sid), "url": url,
            "alt": tuple(str(a) for a in (row.get("aliases") or ())),
            "kind": str(row.get("kind") or "practitioner"), "pack": "",
            "country": str(row.get("region") or ""), "language": str(row.get("language") or ""),
            "access_label": "PUBLIC", "credibility": "UNKNOWN",
            "machine_use_allowed": bool(allowed),
            "licence": str(row.get("licence_note") or "")[:900],
            "label": str(row.get("name") or row.get("ground") or sid)})
    return out


def plane_grounds(path: Path | None = None) -> list[dict[str, Any]]:
    """The HARD-DATA plane's own grounds, as candidate registry rows.

    `desks/mt5/data/asia_sources.json` is the third registry and it was not being read here. It
    is the half of the desk's ground that carries OFFICIAL, EXCHANGE, PHYSICAL AND FLOW data --
    where the number itself is the observation and a hypothesis can be SETTLED rather than only
    minted -- while `deep_forest_sources.json` holds the practitioner forest. `source_drain.py`
    collects from it, but nothing seeded it into the `sources` table, so these grounds never
    entered the uncrawled census, never appeared in the backlog, and never took a slot in an
    hourly drain pass. A registry the coverage organ cannot see is a registry whose coverage is
    unmeasured, which is how a region could read 0 with sixteen declared grounds behind it.

    The file's `country` is the ground's declared jurisdiction and the region vocabulary is
    `libs/research/attribution`'s, so a ground seeded here lands in the same region the
    attribution census will later file its cells under.
    """
    doc = _read_json(path or PLANE_REGISTRY, {})
    rows = doc.get("sources") if isinstance(doc, Mapping) else None
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        sid = str(row.get("id") or "")
        if not sid:
            continue
        out.append({
            "source_id": f"plane:{sid}", "url": url, "alt": (),
            "kind": str(row.get("plane") or "official"), "pack": "",
            "country": str(row.get("country") or ""),
            "language": str(row.get("language") or ""),
            "access_label": "PUBLIC", "credibility": "UNKNOWN",
            "machine_use_allowed": True,
            "licence": str(row.get("access") or "public"),
            "label": str(row.get("name") or sid)})
    return out


def lawful_grounds() -> list[dict[str, Any]]:
    """Every ground the desk could lawfully hold, from all THREE of its own registries,
    deduplicated by source_id. This is the numerator of the whole organ: coverage is what
    fraction of THIS the registry has actually fetched."""
    seen: dict[str, dict[str, Any]] = {}
    for row in [*pack_sources(), *forest_grounds(), *registry_grounds(), *plane_grounds()]:
        seen.setdefault(str(row["source_id"]), row)
    return list(seen.values())


# ------------------------------------------------------------------------------ the refusals
def refusal_for(row: Mapping[str, Any], shares: dict[str, Any] | None) -> tuple[str, str]:
    """(status, reason) when this row must never be fetched, else ("", "").

    EXACTLY TWO WALLS, AND THIS IS THE PART OF THE ORGAN MOST LIKELY TO BE GOT WRONG BY THE NEXT
    SESSION. The first is the principal's five refused ACTS (LAWS 5e), which reach a registry row
    as one of the three refused access labels or as a declared authenticated / MNPI surface; the
    judgement is delegated to `source_shares.machine_use_allowed`, which is the desk's one reader
    of that law, so this organ can never drift from it. The second is not a legal refusal at all:
    a row with no url anywhere has nothing to fetch.

    WHAT IS DELIBERATELY NOT A WALL HERE: a terms page, a licence note, a robots Disallow, a
    paywalled domain, `machine_use_allowed=false`, `route=unreachable`, snippets-only, an
    ACCESS_UNCLEAR label, a social or user-submitted ground. Every one of those is a ROUTING
    LABEL: it withholds redistribution and changes nothing about reading. LAWS 5e names each as a
    deleted brake that "no session may re-introduce, in any form, under any name", so a future
    edit that adds one back to this function is a violation of the section and of growth
    governance, not a tightening.
    """
    url = str(row.get("url") or "").strip()
    if not url:
        sid = str(row.get("source_id") or "")
        # A DESK-INTERNAL OBSERVABLE IS NOT A FAILED CRAWL. `world_lab:oil_supply_shock` and
        # `execution_tape:XAUUSD:...` are rows an organ minted about the desk's own state; they
        # have no url because they have no web ground and never will. Refusing them with the same
        # sentence as a real source whose root was lost would make the backlog unreadable.
        if ":" in sid and sid.split(":", 1)[0] in INTERNAL_PREFIXES:
            return "refused-no-root", (
                f"INTERNAL_OBSERVABLE: `{sid.split(':', 1)[0]}` mints this row about the desk's "
                "own state, not about a web ground; registered so its existence is known, never "
                "queued for a crawler")
        return "refused-no-root", ("NO_ROOT_KNOWN: the registry row names a ground but carries "
                                   "no url, and no root resolved from the source registry, the "
                                   "deep-forest grounds or any country pack")
    label = str(row.get("access_label") or "").strip().upper()
    if label in _refused_labels():
        return "refused-hard-boundary", (
            f"HARD_BOUNDARY: access_label={label} carries one of the principal's five refused "
            "ACTS (LAWS 5e); the row is kept so the ground is known and is never fetched")
    if shares is not None:
        with suppress(Exception):
            from research import source_shares
            hit = source_shares.resolve(shares, row.get("source_id"), url, host_of(url))
            reg_row = (shares.get("rows") or {}).get(hit) if hit else None
            allowed, why = source_shares.machine_use_allowed(reg_row)
            if not allowed:
                return "refused-hard-boundary", f"HARD_BOUNDARY: {why}"
    return "", ""


def _refused_labels() -> tuple[str, ...]:
    """The law's own refused-label list when the classifier is reachable, else the local copy."""
    with suppress(Exception):
        from libs.research.access_classifier import REFUSED_LABELS as LIVE
        return tuple(str(x) for x in LIVE)
    return REFUSED_LABELS


def terms_note(row: Mapping[str, Any], shares: dict[str, Any] | None = None) -> str:
    """The provenance label that TRAVELS WITH a row, or "".

    This is the half of the access law that replaced the brakes. A ground whose terms, robots
    file or registry row says `machine_use_allowed=false` is mined exactly as hard as any other
    and carries this sentence, which is what the desk consults before it REPUBLISHES anything
    derived from it. Recording the note is the obligation; refusing the fetch never was.
    """
    notes: list[str] = []
    if row.get("machine_use_allowed") is False:
        notes.append("the ground declares machine_use_allowed=false")
    if str(row.get("route") or "") == "unreachable":
        notes.append("registry route=unreachable")
    licence = str(row.get("licence") or row.get("licence_note") or "")
    if "NOT FETCHABLE" in licence.upper() or "SNIPPETS ONLY" in licence.upper():
        notes.append(f"licence note: {licence[:120]}")
    if shares is not None:
        with suppress(Exception):
            from research import source_shares
            hit = source_shares.resolve(shares, row.get("source_id"), row.get("url"))
            reg_row = (shares.get("rows") or {}).get(hit) if hit else None
            allowed, why = source_shares.machine_use_allowed(reg_row)
            if allowed and "mined with its label" in why:
                notes.append(why)
    if not notes:
        return ""
    return ("MINED WITH ITS LABEL ATTACHED; REDISTRIBUTION WITHHELD BY ITS TERMS -- "
            + "; ".join(notes) + " (LAWS 5e: a terms label routes USE, it never gates mining)")


def register_refusal(conn: sqlite3.Connection, source_id: str, status: str, reason: str,
                     *, at: str | None = None) -> None:
    """Stamp a refusal so it leaves the pending set AND keeps its reason forever.

    The stamp is what stops the row being re-queued every hour; the reason is what stops the
    knowledge being lost. Both halves are the point -- a refusal that is only a stamp reads
    identically to a successful crawl a week later.
    """
    stamp = at or _now()
    with suppress(sqlite3.Error):
        conn.execute("UPDATE sources SET last_crawled=?, status=?, route_reason=?, routed_at=? "
                     "WHERE source_id=?",
                     (stamp, status, f"{reason} [registered {stamp} by {SOURCE}]", stamp,
                      str(source_id)))


# ------------------------------------------------------------------------------ resolving roots
def host_keys(host: str) -> list[str]:
    """The host, the host without `www.`, and its registrable stem.

    NOT A GUESS -- every key here is DERIVED FROM THE REGISTERED ROW'S OWN HOST, which is why a
    pending row whose only identity is the token `aaii` can be matched to the registered ground
    `https://www.aaii.com/sentimentsurvey` without inventing anything. The failure this fixes was
    measured: sixty pending rows carried a bare seat token and no url, the root was already in
    `deep_forest_sources.json`, and nothing connected the two -- so they read as NO_ROOT_KNOWN
    and would have been refused forever.
    """
    low = str(host or "").strip().lower()
    if not low:
        return []
    keys = [low]
    bare = low[4:] if low.startswith("www.") else low
    if bare != low:
        keys.append(bare)
    parts = [p for p in bare.split(".") if p]
    if len(parts) >= 2 and parts[0] not in ("com", "org", "net", "gov", "edu"):
        keys.append(parts[0])
    return keys


def build_root_index(grounds: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Every name that can identify a ground -> a url. Used to give a rootless row a root.

    `setdefault` throughout: the FIRST ground to claim a key keeps it. A later collision is
    reported by nothing and resolved by nobody, so the rule is fixed rather than last-writer-wins,
    and the pack roots are indexed before the forest grounds because a department that studied a
    country is a better authority on its roots than a crawl frontier.
    """
    idx: dict[str, str] = {}
    for row in grounds:
        url = str(row.get("url") or "")
        if not url:
            continue
        sid = str(row.get("source_id") or "")
        label = str(row.get("label") or "")
        keys: list[str] = [sid.strip().lower(), label.strip().lower(),
                           label.strip().lower().replace(" ", "_"),
                           sid.rsplit(":", 1)[-1].strip().lower(),
                           *host_keys(host_of(url))]
        for key in keys:
            if key:
                idx.setdefault(key, url)
    return idx


def resolve_root(row: Mapping[str, Any], index: Mapping[str, str],
                 shares: dict[str, Any] | None) -> str:
    """A url for a registry row that has none, or "".

    Tried in one order and never guessed: the row's own id, the seat name its `meta_json`
    carries, then the source registry's index. A guess here would put the crawler on a host
    nobody chose, which is worse than an honest refusal.
    """
    sid = str(row.get("source_id") or "").strip().lower()
    keys: list[str] = [sid, sid.rsplit(":", 1)[-1]]
    meta = row.get("meta_json")
    if isinstance(meta, str) and meta.strip():
        blob = _read_json_text(meta)
        if isinstance(blob, Mapping):
            for field in ("seat", "url", "root", "ground", "source"):
                val = blob.get(field)
                if val:
                    keys.append(str(val).strip().lower())
    for key in keys:
        if key and key in index:
            return index[key]
    if shares is not None:
        with suppress(Exception):
            from research import source_shares
            hit = source_shares.resolve(shares, *keys)
            reg_row = (shares.get("rows") or {}).get(hit) if hit else None
            if isinstance(reg_row, Mapping):
                url = str(reg_row.get("url") or "")
                if url.startswith(("http://", "https://")):
                    return url
    return ""


def _read_json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


# ------------------------------------------------------------------------------------ seeding
#: Refusal statuses whose RULE NO LONGER EXISTS. LAWS 5e deleted the brakes that wrote them, so
#: a row still carrying one is not a refusal -- it is a ground the desk stopped reading because
#: of a law that was repealed, and leaving it stamped would make the repeal cosmetic.
DELETED_BRAKE_STATUSES: tuple[str, ...] = ("refused-machine-use", "refused-robots")


def reopen_deleted_brakes(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return to the queue every row refused under a rule that has since been deleted.

    WHY THIS RUNS EVERY PASS AND NOT ONCE. A repealed brake leaves its damage in the DATA, not in
    the code: the stamp on the row is indistinguishable from a successful crawl to anything that
    only reads `last_crawled`, so the ground stays unread forever and the backlog looks healthy.
    Measured on this tree the morning the law changed: 113 pack sources had been stamped
    `refused-machine-use` by this organ's own first build, inside an hour of LAWS 5e deleting
    that exact brake. Reopening is idempotent -- a reopened row that is genuinely at the
    five-act hard boundary is refused again on the same pass, with the reason the law actually
    gives, and a row that is not is simply crawled.

    THE ORIGINAL REASON IS KEPT, prefixed, never overwritten: the fact that the desk once refused
    this ground is part of its history, and a ledger that quietly rewrites its own past is worth
    less than one that says what it changed and when.
    """
    out: dict[str, Any] = {"reopened": 0, "statuses": {}}
    rows = [r for r in _stamped_rows(conn) if r[1] in DELETED_BRAKE_STATUSES]
    if not rows:
        return out
    stamp = _now()
    for url, status, _crawled, why in rows:
        out["statuses"][status] = int(out["statuses"].get(status, 0)) + 1
        with suppress(sqlite3.Error):
            conn.execute(
                "UPDATE sources SET last_crawled=NULL, status=?, route_reason=? "
                "WHERE url=? AND status=?",
                (CLEARED,
                 (f"REOPENED {stamp} by {SOURCE}: the rule that refused this row was DELETED by "
                  f"LAWS 5e (2026-09-23) and the ground returns to the queue. Original: {why}"
                  )[:900], url, status))
            out["reopened"] += 1
    with suppress(sqlite3.Error):
        conn.commit()
    return out


def seed_grounds(conn: sqlite3.Connection, grounds: Sequence[Mapping[str, Any]],
                 *, limit: int = 4000) -> dict[str, Any]:
    """Write every lawful ground the registry has never heard of into `sources`.

    It RAISES the uncrawled count and that is correct: the count was low because the desk had
    not written down what it knew, not because the ground had been covered. The ratchet that
    fails the law gate is on the OVERDUE backlog for exactly this reason.
    """
    out: dict[str, Any] = {"considered": len(grounds), "inserted": 0, "already": 0,
                           "refused_hard_boundary": 0, "terms_labelled": 0, "errors": 0}
    if not _has_sources(conn):
        out["errors"] = len(grounds)
        return out
    try:
        have = {str(r[0]) for r in conn.execute("SELECT source_id FROM sources").fetchall()}
    except sqlite3.Error:
        out["errors"] = len(grounds)
        return out
    stamp = _now()
    for row in list(grounds)[:max(0, int(limit))]:
        sid = str(row.get("source_id") or "")
        if not sid:
            continue
        if sid in have:
            out["already"] += 1
            continue
        # A GROUND WHOSE TERMS WITHHOLD REDISTRIBUTION IS STILL MINED (LAWS 5e). It is seeded
        # like any other and its terms note is written onto the row, where the republication
        # decision will read it. An earlier build of this organ stamped such rows as refused in
        # the same step it registered them -- 113 of them on the first live pass, every one a
        # discovery brake the law names as deleted.
        note = terms_note(row)
        refused = str(row.get("access_label") or "").strip().upper() in _refused_labels()
        meta = {"seeded_by": SOURCE, "pack": row.get("pack") or "",
                "label": row.get("label") or "", "alt": list(row.get("alt") or ()),
                "layer": row.get("kind") or "", "terms_note": note}
        try:
            conn.execute(
                "INSERT INTO sources(source_id, url, kind, language, country, "
                "asset_classes_json, discovered_from, discovered_via, first_seen, last_crawled, "
                "status, licence_note, meta_json, access_label, credibility, predictive_state, "
                "quarantine, routed_at, route_reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, str(row.get("url") or ""), str(row.get("kind") or ""),
                 str(row.get("language") or ""), str(row.get("country") or ""),
                 json.dumps([]), SOURCE, "coverage_drain seed", stamp,
                 stamp if refused else None,
                 "refused-hard-boundary" if refused else CLEARED,
                 "; ".join(x for x in (str(row.get("licence") or ""), note) if x)[:900],
                 json.dumps(meta, sort_keys=True, default=str),
                 str(row.get("access_label") or "") or None,
                 str(row.get("credibility") or "") or None, "UNTESTED", 0,
                 stamp if refused else None,
                 (f"HARD_BOUNDARY: access_label={row.get('access_label')} carries one of the "
                  f"five refused ACTS (LAWS 5e); registered so the ground is known, never "
                  f"fetched [registered {stamp} by {SOURCE}]")
                 if refused else (note or None)))
        except sqlite3.Error:
            out["errors"] += 1
            continue
        have.add(sid)
        out["inserted"] += 1
        if refused:
            out["refused_hard_boundary"] += 1
        elif note:
            out["terms_labelled"] += 1
    with suppress(sqlite3.Error):
        conn.commit()
    return out


# ------------------------------------------------------------------------------- the drain pass
def region_of_row(row: Mapping[str, Any]) -> str:
    """The region a pending source stands in, from its own declared jurisdiction.

    `libs/research/attribution` owns the vocabulary and this module only READS it, so the drain
    and the attribution census can never disagree about what "North America" means. A row whose
    country is blank and whose host is on a generic TLD is UNMAPPED -- a named bucket, never a
    guess and never silently folded into a region that would then read as deeper than it is.
    """
    with suppress(Exception):
        from libs.research import attribution as _A
        where = (_A.region_of(row.get("country")) or _A.region_of_command(row.get("region"))
                 or _A.region_of_url(row.get("url")))
        if where:
            return str(where)
    return UNMAPPED_REGION


def drain_order(rows: Sequence[Mapping[str, Any]], shares: dict[str, Any] | None,
                now: datetime | None = None,
                held: Mapping[str, int] | None = None) -> list[dict[str, Any]]:
    """The pending set, oldest-and-highest-ROI first, DEALT ROUND-ROBIN ACROSS THE REGIONS.

    LEXICOGRAPHIC, not a weighted sum, for the reason `moat_collectors.source_roi` gives: any
    single number lets a prolific ground buy rank with volume. Within one region the first key is
    the published crawl share (the registry's own measured intel ROI, absent = 0.0, which puts an
    unmeasured ground behind a measured payer but AHEAD of a measured dud) and the second is
    age descending, so the 134-hour row at the front of the queue leaves it first.

    WHY THE REGION KEY EXISTS (measured 2026-09-24 on the build box). 1,593 of 2,214 registered
    grounds had never been fetched, and the never-fetched set was not a random sample of them: it
    was every ground in five whole regions. `us` 69 grounds, `institutional` 72, `cn` 41, `ru` 41,
    `sg` 26 -- ZERO crawled between them, while `cz`, `az` and `kz` were fully drained. The cause
    was here. Every one of those rows was seeded in a single batch with one `first_seen` stamp
    and no measured share, so both sort keys tied for all 1,593 and the order collapsed to
    whatever order SQLite returned rows in. The pass took the first 70 of that, every hour, and
    the same regions lost every hour. A region cannot contribute an edge from a ground nothing
    ever fetched, however deep the mining downstream of it goes.

    THIS CAPS NOTHING AND THROTTLES NOTHING. The pass size, the budget and the set of drainable
    rows are exactly what they were; only the ORDER changes, so no region is ever drained less
    than it is today and the regions that were being starved advance with the rest. `held` is the
    count of grounds each region has ALREADY had crawled -- the region holding the fewest takes
    the next slot, which is a floor that can only be satisfied by raising the weakest region and
    never by lowering a strong one.
    """
    scored: dict[str, list[tuple[float, float, dict[str, Any]]]] = {}
    for row in rows:
        share = 0.0
        if shares is not None:
            with suppress(Exception):
                from research import source_shares
                got = source_shares.share_for(shares, row.get("source_id"), row.get("url"),
                                              host_of(str(row.get("url") or "")))
                share = float(got or 0.0)
        age = _age_h(row.get("first_seen"), now) or 0.0
        scored.setdefault(region_of_row(row), []).append((share, age, dict(row)))
    for bucket in scored.values():
        bucket.sort(key=lambda t: (-t[0], -t[1]))

    taken: dict[str, int] = {r: int((held or {}).get(r, 0)) for r in scored}
    out: list[dict[str, Any]] = []
    while True:
        live = [r for r, b in scored.items() if b]
        if not live:
            return out
        # The hungriest region first; ties broken by the head row's own (share, age) rank, so
        # the existing order is preserved exactly wherever the regions are already level.
        live.sort(key=lambda r: (taken[r], -scored[r][0][0], -scored[r][0][1], r))
        pick = live[0]
        out.append(scored[pick].pop(0)[2])
        taken[pick] += 1


def crawled_by_region(conn: sqlite3.Connection) -> dict[str, int]:
    """How many grounds each region has ALREADY had fetched -- the drain's fairness basis.

    UNMEASURED (an empty mapping) is a real answer: the round-robin still deals one slot per
    region per turn, which is fair, just not starvation-weighted.
    """
    out: dict[str, int] = {}
    with suppress(sqlite3.Error):
        for row in conn.execute(
                "SELECT country, url FROM sources WHERE last_crawled IS NOT NULL "
                "AND last_crawled <> ''").fetchall():
            where = region_of_row({"country": row[0], "url": row[1]})
            out[where] = 1 + out.get(where, 0)
    return out


def drain(conn: sqlite3.Connection, *, budget_s: float, max_sources: int,
          dry_run: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """One drain pass. Returns what it drained, what it refused and why, and never raises."""
    started = time.monotonic()
    out: dict[str, Any] = {
        "planned": 0, "resolved_roots": 0, "refused": [], "cleared": 0, "crawled": 0,
        "collector": {"status": "not_run", "why": "no drainable row survived the refusals"},
        "budget_s": round(float(budget_s), 1), "budget_stopped": False, "dry_run": bool(dry_run)}
    shares = _shares_state()
    grounds = lawful_grounds()
    index = build_root_index(grounds)
    pending = pending_rows(conn)
    out["planned"] = len(pending)
    held = crawled_by_region(conn)
    out["held_by_region"] = dict(sorted(held.items(), key=lambda kv: -kv[1]))
    ordered = drain_order(pending, shares, now, held=held)[:max(0, int(max_sources))]
    take: dict[str, int] = {}
    for row in ordered:
        where = region_of_row(row)
        take[where] = 1 + take.get(where, 0)
    out["pass_by_region"] = dict(sorted(take.items(), key=lambda kv: -kv[1]))

    drainable: list[str] = []
    for row in ordered:
        if time.monotonic() - started > budget_s:
            out["budget_stopped"] = True
            break
        sid = str(row.get("source_id") or "")
        url = str(row.get("url") or "").strip()
        if not url:
            found = resolve_root(row, index, shares)
            if found:
                url = found
                row = {**row, "url": found}
                out["resolved_roots"] += 1
                if not dry_run:
                    with suppress(sqlite3.Error):
                        conn.execute("UPDATE sources SET url=? WHERE source_id=?", (found, sid))
        status, reason = refusal_for(row, shares)
        if status:
            out["refused"].append({"source_id": sid, "url": url, "status": status,
                                   "why": reason})
            if not dry_run:
                register_refusal(conn, sid, status, reason)
            continue
        drainable.append(sid)
        if not dry_run:
            with suppress(sqlite3.Error):
                conn.execute("UPDATE sources SET status=? WHERE source_id=? AND "
                             "(status IS NULL OR status NOT IN "
                             "('active','candidate-cleared','candidate_cleared'))",
                             (CLEARED, sid))
    out["cleared"] = len(drainable)
    if not dry_run:
        with suppress(sqlite3.Error):
            conn.commit()

    left = budget_s - (time.monotonic() - started)
    if drainable and left > 5.0 and not dry_run:
        out["collector"] = _run_collectors(conn, budget_s=left, max_sources=len(drainable),
                                           source_ids=drainable)
        out["crawled"] = int(out["collector"].get("sources_visited") or 0)
    elif drainable and dry_run:
        out["collector"] = {"status": "dry_run",
                            "why": f"{len(drainable)} row(s) would be crawled"}
    elif drainable:
        out["collector"] = {"status": "no_budget",
                            "why": f"{left:.1f}s left after the refusal pass; the frontier "
                                   "resumes next hour rather than restarting"}
    return out


def _run_collectors(conn: sqlite3.Connection, *, budget_s: float, max_sources: int,
                    source_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """The existing capture machinery, driven on the rows this organ just cleared.

    `research/moat_collectors.py` owns the robots probe, the media typing, the point-in-time
    capture, the normaliser and the claim writer. Writing a second crawler here would be a second
    set of manners against the same hosts, which is how a desk gets blocked.

    THE ROWS ARE NAMED, NOT COUNTED (2026-09-24). This used to pass only `max_sources`, so the
    collector re-chose the pass by pure ROI and the region-fair order above was discarded before
    a single byte was fetched. The drain cleared 35 Global/institutional grounds in one pass and
    that region's crawled count stayed at 0 -- twice -- because the choice never reached the
    crawler. The ROI order still decides rank WITHIN the named set.
    """
    try:
        from research import moat_collectors
    except Exception as exc:
        return {"status": "unavailable", "why": f"{type(exc).__name__}: {exc}"}
    try:
        report = moat_collectors.run(budget_s=float(budget_s), max_sources=int(max_sources),
                                     conn=conn, source_ids=source_ids)
    except Exception as exc:
        return {"status": "failed", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return {"status": "ran", "why": f"{report.get('sources_visited')} ground(s) visited",
            "sources_visited": report.get("sources_visited"),
            "captures_new": report.get("captures_new"),
            "claims_written": report.get("claims_written"),
            "refused": list(report.get("refused") or ())[:20],
            "budget_stopped": bool(report.get("budget_stopped"))}


def _shares_state() -> dict[str, Any] | None:
    try:
        from research import source_shares
        return dict(source_shares.load())
    except Exception:
        return None


# ------------------------------------------------------------------ the ten-layer verification
def verify_layers(conn: sqlite3.Connection | None) -> dict[str, Any]:
    """Which of every pack's ten layers is MAPPED, ABSENT or still only DECLARED -- MEASURED.

    THE CLAIM A PACK CANNOT MAKE ABOUT ITSELF. Every pack writes `verified: False` into its own
    source rows because a pack has no way of knowing whether anything ever fetched the root it
    named -- so `coverage.covered()` reads DECLARED_UNVERIFIED for almost every layer on the
    desk, and the ten-layer depth claim is an assertion rather than a measurement. Here the
    answer comes from the OUTSIDE: a layer is MAPPED when the registry holds a fetched row whose
    host matches one of that layer's declared roots; ABSENT_DECLARED when the pack named the
    layer absent with a reason; DECLARED_UNVERIFIED when roots exist and none has been fetched;
    UNMAPPED when the pack said nothing at all. Four states and no quiet zero (L1.28a).
    """
    stamped = crawled_hosts(conn) if conn is not None else {}
    walled = refused_hosts(conn) if conn is not None else {}
    out: dict[str, Any] = {"measured": conn is not None, "packs": {}, "totals": {},
                           "why": ("layers verified against registry rows carrying a "
                                   "last_crawled stamp" if conn is not None else
                                   "UNMEASURED: the alpha registry is not readable on this host, "
                                   "so no layer has been checked against anything")}
    pkg = _countries()
    if pkg is None:
        out["why"] = "UNMEASURED: the countries package is not importable"
        out["measured"] = False
        return out
    tot = dict.fromkeys(("mapped", "absent_declared", "refused_hard_boundary",
                         "declared_unverified", "unmapped"), 0)
    mods: dict[str, Any] = {}
    for code in pkg.codes():
        mod = _pack_module(code)
        if mod is not None:
            mods[code] = mod
    vocabs = {c: _domain_vocab(m) for c, m in mods.items()}
    for code in pkg.codes():
        mod = _pack_module(code)
        if mod is None:
            continue
        classes = [sc for sc in (getattr(mod, "SOURCE_CLASSES", ()) or ())
                   if isinstance(sc, Mapping)]
        if not classes:
            continue
        rows: dict[str, dict[str, Any]] = {}
        for layer in SOURCE_LAYERS:
            here = [sc for sc in classes if str(sc.get("layer") or "") == layer]
            declared = [sc for sc in here if not str(sc.get("id") or "").startswith("absent_")]
            absent = [sc for sc in here if str(sc.get("id") or "").startswith("absent_")]
            roots = [str(r) for sc in declared for r in (sc.get("roots") or ())]
            hosts = {host_of(r) for r in roots} - {""}
            hit = sorted(h for h in hosts if h in stamped)
            barred = sorted(h for h in hosts if h in walled and h not in stamped)
            if hit:
                state = "MAPPED"
                why = f"{len(hit)}/{len(hosts)} declared host(s) carry a last_crawled stamp"
            elif absent:
                state = "ABSENT_DECLARED"
                why = str(absent[0].get("notes") or "declared absent with a reason")[:220]
            elif barred and len(barred) == len(hosts):
                state = "REFUSED_HARD_BOUNDARY"
                why = (f"every declared host in this layer sits behind one of the five refused "
                       f"ACTS ({walled[barred[0]][:140]}); the desk has done what it lawfully "
                       f"can and the answer is a registered legal fact, not undone work")
            elif declared:
                state = "DECLARED_UNVERIFIED"
                why = (f"{len(declared)} source(s) over {len(hosts)} host(s) declared and none "
                       f"fetched; this is drainable work, not an absence")
            else:
                state = "UNMAPPED"
                why = "the pack names neither a source nor a declared absence for this layer"
            rows[layer] = {"state": state, "declared": len(declared), "absent": len(absent),
                           "hosts": sorted(hosts), "verified_hosts": hit,
                           "refused_hosts": barred, "why": why}
            tot[state.lower()] = tot.get(state.lower(), 0) + 1
        mapped = sum(1 for v in rows.values() if v["state"] in LAYER_SETTLED)
        out["packs"][code] = {
            "layers": rows, "layers_mapped": mapped, "layers_total": len(SOURCE_LAYERS),
            "unverified": [k for k, v in rows.items() if v["state"] == "DECLARED_UNVERIFIED"],
            "unmapped": [k for k, v in rows.items() if v["state"] == "UNMAPPED"],
            "cells": pack_cells(mod), "no_lawful_ground": no_lawful_ground(mod),
            "jurisdictions": [str(c).lower()
                              for c in (getattr(mod, "JURISDICTIONS", None) or (code,))]}
        out["packs"][code]["depth"] = depth_score(code, mod, out["packs"][code], vocabs)
        out["packs"][code]["breadth"] = breadth_score(mod, out["packs"][code])
        out["packs"][code]["ingestion"] = ingestion_score(mod, stamped)
    out["totals"] = tot
    out["packs_full_depth"] = sorted(c for c, v in out["packs"].items()
                                     if v["layers_mapped"] == len(SOURCE_LAYERS))
    counted = [v["cells"] for v in out["packs"].values() if isinstance(v["cells"], int)]
    out["cells_total"] = sum(counted)
    out["cells_unmeasured"] = sorted(c for c, v in out["packs"].items()
                                     if not isinstance(v["cells"], int))
    out["no_lawful_ground_total"] = sum(len(v["no_lawful_ground"])
                                        for v in out["packs"].values())
    out["jurisdictions_total"] = len({j for v in out["packs"].values()
                                      for j in v["jurisdictions"]})
    for axis in ("depth", "breadth", "ingestion"):
        scores = {c: float(v[axis]["score"]) for c, v in out["packs"].items()}
        vals = sorted(scores.values())
        out[axis] = {
            "scores": dict(sorted(scores.items())),
            "min": round(vals[0], 4) if vals else None,
            "median": round(vals[len(vals) // 2], 4) if vals else None,
            "max": round(vals[-1], 4) if vals else None,
            "reference": {c: round(scores[c], 4) for c in DEPTH_REFERENCE if c in scores},
            "worst": [c for c, _ in sorted(scores.items(), key=lambda kv: kv[1])[:10]],
            "rule": ("every department is scored on the same components, each measured from "
                     "OUTSIDE the pack; the floor is the LOWEST score once every pack clears "
                     "it, and it ratchets UP only, so parity can improve and never regress"),
        }
    out["depth"]["weights"] = dict(DEPTH_WEIGHTS)
    out["breadth"]["weights"] = dict(BREADTH_WEIGHTS)
    out["breadth"]["targets"] = dict(BREADTH_TARGETS)
    out["ingestion"]["publisher_classes"] = list(PUBLISHER_CLASSES)
    # THE ONE NUMBER THAT ORDERS THE WORK: distance from the complete pack on all three axes.
    # The principal asked for "the worst five packs by distance", and a pack deep on one axis
    # and empty on another must not be able to hide behind its good axis, so it is the SUM of
    # the three shortfalls rather than their mean.
    dist = {c: round((1.0 - float(v["depth"]["score"])) + (1.0 - float(v["breadth"]["score"]))
                     + (1.0 - float(v["ingestion"]["score"])), 4)
            for c, v in out["packs"].items()}
    out["parity"] = {
        "distance_from_maximum": dict(sorted(dist.items(), key=lambda kv: -kv[1])),
        "worst_by_distance": [c for c, _ in sorted(dist.items(), key=lambda kv: -kv[1])[:10]],
        "floors_measured": {"depth_min": out["depth"]["min"],
                            "breadth_min": out["breadth"]["min"],
                            "ingestion_min": out["ingestion"]["min"]},
        "rule": ("depth, breadth and ingestion each carry their own floor and each floor rises "
                 "to the weakest pack's score once every pack clears it; distance is the SUM of "
                 "the three shortfalls so a pack cannot hide a hollow axis behind a strong one"),
    }
    return out


#: THE SEVEN THINGS A DEPARTMENT MUST PROVE, and what each is worth. The principal's words
#: (2026-09-23): "all region and country packs have equal maximum depth ... like it's their
#: native country's own quant desk." Presence was never the question; these are.
#:
#: WHY THIS LIVES HERE AND NOT IN THE PARITY FENCE. `regional_parity.pack_depth` scores what a
#: pack DECLARES, and a declaration is exactly what this is meant to stop being sufficient: a
#: pack cannot verify its own source layers, cannot know whether its mechanisms duplicate a
#: sibling's, and cannot count what reached the gauntlet. Every component below is measured from
#: OUTSIDE the pack -- the registry's crawl stamps, the other packs' domain sets, the cells the
#: pack actually mints -- which is the whole difference between a score and a claim.
DEPTH_WEIGHTS: dict[str, float] = {
    "layers_verified": 0.30,      # ten layers MAPPED, ABSENT_DECLARED or hard-boundary refused
    "cells_emitted": 0.20,        # what actually reaches the one gauntlet
    "own_mechanisms": 0.15,       # its domains are its own, not a sibling's ontology renamed
    "native_language": 0.10,      # terminology and queries in the country's own languages
    "data_plane": 0.10,           # a dataset catalogue deep enough to evaluate its own cells
    "transmission": 0.10,         # candidates against symbols the broker actually quotes
    "interactions": 0.05,         # it knows which sibling departments it shares a mechanism with
}
#: The reference depth the packs are measured against: `au` and `ma`, the two the mandate names.
DEPTH_REFERENCE: tuple[str, ...] = ("au", "ma")
#: Component targets, taken from the reference packs rather than invented.
DEPTH_TARGETS: dict[str, int] = {"cells": 100, "datasets": 14, "edges": 8, "interactions": 4,
                                 "terms": 100}
#: Two packs whose domain vocabularies overlap more than this are one ontology wearing two names.
DUPLICATE_JACCARD = 0.60


def _domain_vocab(mod: Any) -> frozenset[str]:
    """The word set of a pack's domain titles and objects -- its mechanism fingerprint."""
    words: set[str] = set()
    for dom in (getattr(mod, "DOMAINS", ()) or ()):
        if not isinstance(dom, Mapping):
            continue
        blob = " ".join([str(dom.get("title") or ""), *(str(o) for o in dom.get("objects") or ())])
        words.update(w for w in blob.lower().replace("/", " ").split() if len(w) > 3)
    return frozenset(words)


def depth_score(code: str, mod: Any, layer_row: Mapping[str, Any],
                vocabs: Mapping[str, frozenset[str]]) -> dict[str, Any]:
    """This department's depth, 0..1, with every component and its arithmetic.

    Each component is a RATIO against the reference packs' own numbers, clipped at 1.0, so a
    pack that matches `au` and `ma` scores 1.0 and one that exceeds them is not rewarded for
    padding. A component the pack cannot answer is 0.0 and is NAMED -- never silently dropped,
    because a mean over the components a pack happens to have is a score of its own omissions.
    """
    def ratio(n: Any, target: int) -> float:
        try:
            return max(0.0, min(1.0, float(n) / float(target)))
        except (TypeError, ValueError):
            return 0.0

    cells = pack_cells(mod)
    terms = getattr(mod, "TERMINOLOGY", {}) or {}
    n_terms = len({t for v in dict(terms).values() for t in (v or ())})
    langs = tuple(getattr(mod, "NATIVE_LANGUAGES", ()) or ())
    non_english = any(str(x).lower() not in ("en", "english") for x in langs)
    queries = sum(len(sc.get("queries") or ()) for sc in (getattr(mod, "SOURCE_CLASSES", ()) or ())
                  if isinstance(sc, Mapping))
    mine = _domain_vocab(mod)
    worst, twin = 0.0, ""
    for other, vocab in vocabs.items():
        if other == code or not mine or not vocab:
            continue
        j = len(mine & vocab) / float(len(mine | vocab))
        if j > worst:
            worst, twin = j, other
    comp = {
        "layers_verified": float(layer_row.get("layers_mapped") or 0) / len(SOURCE_LAYERS),
        "cells_emitted": ratio(cells if isinstance(cells, int) else 0, DEPTH_TARGETS["cells"]),
        "own_mechanisms": 1.0 if worst <= DUPLICATE_JACCARD else max(
            0.0, 1.0 - (worst - DUPLICATE_JACCARD) / (1.0 - DUPLICATE_JACCARD)),
        "native_language": (0.5 * (1.0 if non_english else 0.0)
                            + 0.3 * ratio(n_terms, DEPTH_TARGETS["terms"])
                            + 0.2 * (1.0 if queries else 0.0)),
        "data_plane": ratio(len(getattr(mod, "DATASETS", ()) or ()), DEPTH_TARGETS["datasets"]),
        "transmission": ratio(len(getattr(mod, "TRANSMISSION_EDGES_SEED", ()) or ()),
                              DEPTH_TARGETS["edges"]),
        "interactions": ratio(len(getattr(mod, "INTERACTIONS", ())
                                  or getattr(mod, "CUSTOM_MINERS", ()) or ()),
                              DEPTH_TARGETS["interactions"]),
    }
    score = sum(DEPTH_WEIGHTS[k] * v for k, v in comp.items())
    weakest = sorted(comp.items(), key=lambda kv: kv[1])[:3]
    return {
        "score": round(score, 4), "components": {k: round(v, 4) for k, v in comp.items()},
        "weakest": [k for k, _ in weakest],
        "nearest_twin": twin, "twin_overlap": round(worst, 3),
        "why": (f"{score:.3f} = " + " + ".join(
            f"{DEPTH_WEIGHTS[k]:.2f}x{v:.2f} {k}" for k, v in comp.items())),
        "reference": list(DEPTH_REFERENCE),
    }


#: THE COMPLETE PACK, DEFINED SO "MAXIMUM" IS A NUMBER AND NOT A FEELING (principal 2026-09-23:
#: "depth AND breadth both maximum for all and equal"). Every target below is what a COMPLETE
#: department for any jurisdiction looks like, taken from the `au`/`ma` reference rather than
#: invented, so a pack's distance from the maximum is publishable and its floor can ratchet.
BREADTH_TARGETS: dict[str, int] = {
    "mechanisms": 14,        # distinct domains -- a pack on one mechanism is not a desk
    "instruments": 18,       # executable symbols it can actually transmit into
    "sectors": 5,            # broker asset classes those symbols span
    "source_classes": 25,    # named grounds across the ten layers
    "languages": 2,          # the jurisdiction's own languages, not English alone
    "partners": 4,           # sibling packs it mines jointly
}
BREADTH_WEIGHTS: dict[str, float] = {
    "mechanisms": 0.25, "instruments": 0.20, "sectors": 0.15,
    "source_classes": 0.20, "languages": 0.10, "partners": 0.10,
}
#: THE PUBLISHER CLASSES EVERY JURISDICTION HAS. A complete data plane enumerates one dataset
#: from each; a dataset the jurisdiction genuinely does not publish is a NO_LAWFUL_GROUND row,
#: which counts as answered. Anything else is NOT_REACHED and is named with what was tried.
PUBLISHER_CLASSES: tuple[str, ...] = (
    "statistics_office", "central_bank", "customs_trade", "exchange_clearing", "regulator",
    "ministry_budget", "port_logistics", "energy_commodity", "labour", "credit_registry")
#: Words that map a dataset row onto a publisher class. Matched against the row's own `source`
#: and `name`, never guessed from the country.
_PUBLISHER_WORDS: dict[str, tuple[str, ...]] = {
    "statistics_office": ("statistic", "census", "instat", "nso", "cso", "bureau"),
    "central_bank": ("central bank", "reserve bank", "monetary", "banco central", "banque",
                     "bank of", "pboc", "ecb", "fed"),
    "customs_trade": ("customs", "trade", "comtrade", "export", "import", "douane", "aduana"),
    "exchange_clearing": ("exchange", "bourse", "clearing", "depositor", "settlement", "stock"),
    "regulator": ("regulat", "supervis", "authority", "commission", "superint"),
    "ministry_budget": ("ministry", "treasury", "budget", "finance", "fisc", "gazette"),
    "port_logistics": ("port", "shipping", "freight", "rail", "logistic", "airport", "vessel",
                       "corridor"),
    "energy_commodity": ("energy", "oil", "gas", "power", "grid", "mine", "mining", "crop",
                         "agri", "commodity", "coffee", "cocoa", "metal"),
    "labour": ("labour", "labor", "employment", "wage", "payroll", "unemploy"),
    "credit_registry": ("credit", "loan", "lending", "registry", "deposit"),
}


def asset_class_of(symbol: str) -> str:
    """The broker's own class for a symbol. Borrowed from the countries package, never guessed."""
    pkg = _countries()
    if pkg is None:
        return ""
    try:
        return str(pkg.asset_class(symbol))
    except Exception:
        return ""


def breadth_score(mod: Any, layer_row: Mapping[str, Any]) -> dict[str, Any]:
    """How WIDE this department is, 0..1, against an explicit maximum.

    A pack can have ten verified source layers and still cover one mechanism on one instrument;
    depth would score it well and the desk would still understand the country badly. This is the
    other axis the principal named, and every component is COUNTED from the pack's own declared
    objects rather than asserted anywhere.
    """
    execs = tuple(getattr(mod, "EXECUTABLE_INSTRUMENTS", ()) or ())
    targets = {str(x) for e in (getattr(mod, "TRANSMISSION_EDGES_SEED", ()) or ())
               if isinstance(e, Mapping) for x in (e.get("targets") or ())}
    instruments = {str(x) for x in execs} | targets
    sectors = {asset_class_of(s) for s in instruments} - {"ABSENT", ""}
    classes = [sc for sc in (getattr(mod, "SOURCE_CLASSES", ()) or ()) if isinstance(sc, Mapping)]
    langs = {str(x).lower() for x in (getattr(mod, "NATIVE_LANGUAGES", ()) or ())}
    partners = {str(r.get("with") or r.get("pack") or "")
                for r in (getattr(mod, "INTERACTIONS", ()) or ()) if isinstance(r, Mapping)}
    raw = {"mechanisms": len(getattr(mod, "DOMAINS", ()) or ()),
           "instruments": len(instruments), "sectors": len(sectors),
           "source_classes": len([c for c in classes
                                  if not str(c.get("id") or "").startswith("absent_")]),
           "languages": len(langs - {"en", "english", ""}),
           "partners": len(partners - {""})}
    comp = {k: max(0.0, min(1.0, v / float(BREADTH_TARGETS[k]))) for k, v in raw.items()}
    score = sum(BREADTH_WEIGHTS[k] * v for k, v in comp.items())
    return {"score": round(score, 4), "raw": raw,
            "components": {k: round(v, 4) for k, v in comp.items()},
            "targets": dict(BREADTH_TARGETS),
            "distance_from_max": {k: max(0, BREADTH_TARGETS[k] - v) for k, v in raw.items()},
            "weakest": [k for k, _ in sorted(comp.items(), key=lambda kv: kv[1])[:3]],
            "layers_used": int(layer_row.get("layers_mapped") or 0)}


def ingestion_score(mod: Any, stamped: Mapping[str, str]) -> dict[str, Any]:
    """Which of the ten publisher classes this jurisdiction's data plane actually reaches.

    ENUMERATED, THEN INGESTED OR NAMED. For each publisher class the pack either carries a
    dataset row mapped to it -- INGESTED when one of the pack's declared hosts carries a crawl
    stamp, else ENUMERATED_NOT_REACHED with exactly what is missing -- or the class is answered
    by a NO_LAWFUL_GROUND row, or it is MISSING. MISSING is the only state that is neither
    coverage nor a measurement, and driving it out is what the floor is for.
    """
    rows = [d for d in (getattr(mod, "DATASETS", ()) or ()) if isinstance(d, Mapping)]
    hosts = {host_of(str(r)) for sc in (getattr(mod, "SOURCE_CLASSES", ()) or ())
             if isinstance(sc, Mapping) for r in (sc.get("roots") or ())} - {""}
    reached = any(h in stamped for h in hosts)
    absent_layers = sorted({r["layer"] for r in no_lawful_ground(mod) if r.get("layer")})
    by_class: dict[str, dict[str, Any]] = {}
    for cls in PUBLISHER_CLASSES:
        words = _PUBLISHER_WORDS[cls]
        hit = [r for r in rows
               if any(w in f"{r.get('source', '')} {r.get('name', '')}".lower() for w in words)]
        if hit and reached:
            state, why = "INGESTED", f"{len(hit)} dataset row(s); a declared host carries a stamp"
        elif hit:
            state, why = "ENUMERATED_NOT_REACHED", (
                f"{len(hit)} dataset row(s) enumerated with how_to_fetch; no declared host of "
                f"this pack has been crawled yet, so there is no vintage or availability stamp")
        elif absent_layers:
            state, why = "NO_LAWFUL_GROUND", (
                f"the pack declares {absent_layers[:3]} absent with a reason; this publisher "
                f"class is answered by that measured refusal")
        else:
            state, why = "MISSING", "no dataset row and no declared absence for this publisher"
        by_class[cls] = {"state": state, "rows": len(hit), "why": why}
    answered = sum(1 for v in by_class.values()
                   if v["state"] in ("INGESTED", "NO_LAWFUL_GROUND"))
    enumerated = sum(1 for v in by_class.values() if v["state"] != "MISSING")
    n = float(len(PUBLISHER_CLASSES))
    return {"score": round(0.65 * (answered / n) + 0.35 * (enumerated / n), 4),
            "by_class": by_class, "datasets": len(rows),
            "ingested": sum(1 for v in by_class.values() if v["state"] == "INGESTED"),
            "not_reached": [c for c, v in by_class.items()
                            if v["state"] == "ENUMERATED_NOT_REACHED"],
            "missing": [c for c, v in by_class.items() if v["state"] == "MISSING"],
            "maximum": list(PUBLISHER_CLASSES),
            "rule": ("every publisher class a jurisdiction has is enumerated, then INGESTED with "
                     "a vintage stamp or NAMED not-reached with what was tried; a class the "
                     "jurisdiction genuinely does not publish is a NO_LAWFUL_GROUND row and "
                     "counts as answered")}


def pack_cells(mod: Any) -> int | str:
    """How many testable cells this pack mints, or UNMEASURED naming why.

    THE NUMBER THE PRINCIPAL ASKED TO BE MAXIMISED (2026-09-23): "the point of every pack is
    cells reaching the ONE gauntlet 24/7 ... report cells emitted per pack and make that number
    the thing you maximise." A pack that does not expose `cells()` is not counted as zero -- it
    is named in `cells_unmeasured`, because a pack written before the convention landed has not
    minted nothing, it has simply not been asked.
    """
    fn = getattr(mod, "cells", None)
    if not callable(fn):
        return "UNMEASURED: the pack exposes no cells() function"
    try:
        return len(tuple(fn()))
    except Exception as exc:                                        # pragma: no cover
        return f"UNMEASURED: cells() raised {type(exc).__name__}"


def no_lawful_ground(mod: Any) -> list[dict[str, str]]:
    """Every layer this pack declares the jurisdiction genuinely does not have, with its reason.

    Read from whichever of the three shapes the pack used -- `NO_LAWFUL_GROUND` rows, the
    per-jurisdiction `JURISDICTION_LAYER_GAPS` map, or the pack-wide `LAYER_ABSENCES` mapping --
    because the packs were written by many hands and a reader that only understood one of them
    would report the other two as silence. THIS IS THE MANDATE'S OTHER ANSWER: a country pack
    either covers a layer or records a MEASURED refusal naming the layer that does not exist for
    that jurisdiction, and both are coverage. Only a blank layer is work.
    """
    out: list[dict[str, str]] = []
    rows = getattr(mod, "NO_LAWFUL_GROUND", None)
    if isinstance(rows, (list, tuple)):
        for row in rows:
            if isinstance(row, Mapping):
                out.append({"jurisdiction": str(row.get("jurisdiction") or row.get("code") or ""),
                            "layer": str(row.get("layer") or ""),
                            "why": str(row.get("why") or row.get("reason") or "")[:400],
                            "substitute": str(row.get("substitute") or "")[:300]})
    gaps = getattr(mod, "JURISDICTION_LAYER_GAPS", None)
    if isinstance(gaps, Mapping):
        for key, why in gaps.items():
            code, _, layer = str(key).partition("/")
            out.append({"jurisdiction": code, "layer": layer or str(key),
                        "why": str(why)[:400], "substitute": ""})
    absences = getattr(mod, "LAYER_ABSENCES", None)
    if isinstance(absences, Mapping):
        for layer, why in absences.items():
            out.append({"jurisdiction": "", "layer": str(layer), "why": str(why)[:400],
                        "substitute": ""})
    return out


# ----------------------------------------------------------------------------- the daily verdict
#: Words that identify a refusal raised under a rule LAWS 5e DELETED. Matched against the
#: reasons other organs hand back, never against anything this organ decides itself.
_DELETED_BRAKE_WORDS: tuple[str, ...] = ("robots", "machine_use", "machine use", "disallow",
                                         "snippets", "unreachable")


def deleted_brake_refusals(collector: Mapping[str, Any]) -> list[dict[str, str]]:
    """Refusals handed back by ANOTHER organ under a rule this desk repealed on 2026-09-23.

    This organ cannot fix `moat_collectors.robots_barred` -- that file has its own owner and a
    drain that edited every organ it touched would be a second desk. What it CAN do is refuse to
    let the loss go unnamed: a ground the collector declined on a robots Disallow is ground the
    desk is lawfully entitled to read and is not reading, and the only reason it stays invisible
    is that nobody counts it. So it is counted, named with the organ that raised it, and offered
    as a gap family in its own right.
    """
    out: list[dict[str, str]] = []
    for row in list(collector.get("refused") or ()):
        if not isinstance(row, Mapping):
            continue
        why = str(row.get("why") or "").lower()
        if any(word in why for word in _DELETED_BRAKE_WORDS):
            out.append({"source": str(row.get("source") or ""), "why": str(row.get("why") or ""),
                        "organ": "research/moat_collectors.py"})
    return out


def largest_gap(backlog: Mapping[str, Any], layers: Mapping[str, Any],
                grounds: Sequence[Mapping[str, Any]],
                collector: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """THE ONE LARGEST INFORMATION GAP, by expected value, named so a person reads it at 08:00.

    EV is the desk's own priority form (LAWS 5n): value x reach / cost. Five candidate families
    compete on one scale and the winner is printed with its arithmetic, because a bottleneck
    nobody can check is a bottleneck nobody fixes:

      * OVERDUE BACKLOG -- registered ground the desk owns and has not read. Reach is the number
        of rows, value is 1.0 (it is already known to be lawful and relevant), cost is one crawl
        each. The cheapest information on the board by construction.
      * UNVERIFIED LAYERS -- a pack's declared root that nothing has fetched. Reach is the number
        of layers, value 0.8 (declared by a department that studied the country), cost one crawl.
      * UNMAPPED LAYERS -- a layer with no source AND no declared absence. Reach is the count,
        value 1.0 (it is the only family where the desk does not even know what it is missing),
        cost is a human-scale research act, charged at ten crawls.
      * DELETED BRAKE STILL ENFORCED -- ground another organ declined under a rule LAWS 5e
        repealed. Reach is the count, value 1.0, and the cost is 0.5 because the fix is one
        edit in one function rather than a crawl each: this is the CHEAPEST family on the board
        and it should win the morning whenever it is non-empty, which is the point of listing it.
      * PACKS MINTING NO CELLS -- a department with ten mapped source layers that hands the
        gauntlet nothing. Reach is the count, value 1.0, cost 5 (a `cells()` function is real
        work). This family exists because the principal named the number to maximise: "the point
        of every pack is cells reaching the ONE gauntlet 24/7". Depth that never becomes a cell
        is depth the desk paid for and cannot test.
    """
    cands: list[dict[str, Any]] = []
    overdue = int(backlog.get("backlog_overdue") or 0)
    if overdue:
        cands.append({
            "gap": "OVERDUE_UNCRAWLED_SOURCES", "reach": overdue, "value": 1.0, "cost": 1.0,
            "ev": round(overdue * 1.0 / 1.0, 3),
            "what": (f"{overdue} registered source(s) the desk owns have been uncrawled for more "
                     f"than {LEASE_H:.0f}h; the oldest has waited "
                     f"{backlog.get('oldest_wait_h')}h"),
            "fix": "this organ's own drain pass, with a larger --budget-s or more passes"})
    unver = sum(len(v.get("unverified") or ()) for v in (layers.get("packs") or {}).values())
    if unver:
        top = sorted(((len(v.get("unverified") or ()), c)
                      for c, v in (layers.get("packs") or {}).items()), reverse=True)[:5]
        cands.append({
            "gap": "DECLARED_BUT_UNVERIFIED_LAYERS", "reach": unver, "value": 0.8, "cost": 1.0,
            "ev": round(unver * 0.8, 3),
            "what": (f"{unver} pack layer(s) name a root that nothing has ever fetched; worst "
                     f"packs {[f'{c}:{n}' for n, c in top]}"),
            "fix": "seed the pack roots into the registry and drain them (this organ, step 1)"})
    unmapped = sum(len(v.get("unmapped") or ()) for v in (layers.get("packs") or {}).values())
    if unmapped:
        top = sorted(((len(v.get("unmapped") or ()), c)
                      for c, v in (layers.get("packs") or {}).items()), reverse=True)[:5]
        cands.append({
            "gap": "UNMAPPED_LAYERS", "reach": unmapped, "value": 1.0, "cost": 10.0,
            "ev": round(unmapped * 1.0 / 10.0, 3),
            "what": (f"{unmapped} pack layer(s) carry neither a source nor a declared absence -- "
                     f"the desk does not know what it is missing; worst packs "
                     f"{[f'{c}:{n}' for n, c in top]}"),
            "fix": ("the pack's author names a source in that layer or declares it ABSENT with "
                    "the reason (a measured NO_LAWFUL_GROUND row)")})
    silent = list(layers.get("cells_unmeasured") or ())
    if silent:
        cands.append({
            "gap": "PACKS_MINTING_NO_CELLS", "reach": len(silent), "value": 1.0, "cost": 5.0,
            "ev": round(len(silent) / 5.0, 3),
            "what": (f"{len(silent)} pack(s) expose no `cells()` and therefore mint nothing the "
                     f"gauntlet can be handed, however deep their source layers are; the desk "
                     f"has measured {layers.get('cells_total')} cells from the rest. "
                     f"First: {silent[:8]}"),
            "fix": ("each pack's author adds `cells()` -- its domains x its executable "
                    "instruments x its named conditions -- so the department's depth reaches "
                    "the one gauntlet instead of sitting in a data structure")})
    stale_brakes = deleted_brake_refusals(collector or {})
    if stale_brakes:
        organs = sorted({r["organ"] for r in stale_brakes})
        cands.append({
            "gap": "DELETED_BRAKE_STILL_ENFORCED", "reach": len(stale_brakes), "value": 1.0,
            "cost": 0.5, "ev": round(len(stale_brakes) / 0.5, 3),
            "what": (f"{len(stale_brakes)} ground(s) declined this pass under a rule LAWS 5e "
                     f"REPEALED on 2026-09-23 (robots Disallow, machine_use_allowed=false, "
                     f"snippets-only, route=unreachable). Raised by {organs}. The desk is "
                     f"lawfully entitled to read every one of them."),
            "fix": (f"the owner of {organs} makes those labels travel with the row instead of "
                    "refusing the fetch, as `coverage_drain.refusal_for` does"),
            "named": stale_brakes[:12]})
    known = {str(g.get("source_id")) for g in grounds}
    if not cands:
        return {"gap": "NONE_MEASURED", "ev": 0.0,
                "what": ("no overdue backlog, no unverified layer and no unmapped layer was "
                         "measured this pass"),
                "fix": "widen the ground: add rows to deep_forest_sources.json or a new pack",
                "candidates": [], "lawful_grounds_known": len(known)}
    cands.sort(key=lambda c: -float(c["ev"]))
    best = dict(cands[0])
    best["candidates"] = cands
    best["lawful_grounds_known"] = len(known)
    best["rule"] = ("expected value = reach x value / cost, on one scale across every gap "
                    "family, printed with its arithmetic so the verdict can be checked")
    return best


# ---------------------------------------------------------------------------------- the ledger
def ratchet(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> dict[str, Any]:
    """The three ratchets, each in the direction that is honest for its own quantity.

    `backlog_overdue` and `overdue_wait_h` may FALL and never rise; `drained_total` may RISE and
    never fall. A quantity with no previous reading ENTERS at its measured value rather than at
    zero -- the desk has broken this exact rule before by inventing a floor it had not measured
    (L1.50, and the 8 GB/96 GB memory floor in CLAUDE.md).
    """
    prev = dict(previous or {})
    out: dict[str, Any] = {"ceilings": {}, "floors": {}, "over": {}, "under": {}, "first": []}
    for key in ("backlog_overdue", "overdue_wait_h", "uncrawled_total"):
        cur = current.get(key)
        if cur is None:
            continue
        cur = float(cur)
        old = prev.get(key)
        if old is None:
            out["ceilings"][key] = cur
            out["first"].append(key)
            continue
        old = float(old)
        out["ceilings"][key] = min(old, cur)
        if cur > old:
            out["over"][key] = {"ceiling": old, "current": cur}
    for key in ("drained_total", "depth_min", "breadth_min", "ingestion_min"):
        cur_f = current.get(key)
        if cur_f is None:
            continue
        cur_f = float(cur_f)
        old = prev.get(key)
        if old is None:
            out["floors"][key] = cur_f
            out["first"].append(key)
            continue
        out["floors"][key] = max(float(old), cur_f)
        if cur_f < float(old):
            out["under"][key] = {"floor": float(old), "current": cur_f}
    out["rule"] = ("backlog and wait ratchet DOWN, drained total and the three PARITY floors "
                   "(depth/breadth/ingestion, each the weakest department's score) ratchet UP; "
                   "a quantity with no "
                   "previous reading enters at what was measured, never at an invented zero")
    return out


def load_ledger(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or LEDGER, {})
    return doc if isinstance(doc, dict) else {}


def save_ledger(doc: Mapping[str, Any], path: Path | None = None) -> None:
    _write_json(path or LEDGER, doc)


# ----------------------------------------------------------------------------------- the pass
def measure_backlog(conn: sqlite3.Connection | None,
                    now: datetime | None = None) -> dict[str, Any]:
    """The uncrawled set, its oldest wait and how much of it is past the lease."""
    if conn is None:
        return {"measured": False, "uncrawled_total": None, "backlog_overdue": None,
                "oldest_wait_h": None, "overdue_wait_h": None,
                "total_sources": None, "by_kind": {},
                "why": "UNMEASURED: data/alpha_registry.sqlite is absent or unreadable"}
    rows = pending_rows(conn)
    ages = [(_age_h(r.get("first_seen"), now) or 0.0) for r in rows]
    overdue = sum(1 for a in ages if a > LEASE_H)
    by_kind: dict[str, int] = {}
    for r in rows:
        key = str(r.get("kind") or "unknown")
        by_kind[key] = by_kind.get(key, 0) + 1
    total = 0
    with suppress(sqlite3.Error):
        total = int(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
    oldest = round(max(ages), 1) if ages else 0.0
    return {"measured": True, "uncrawled_total": len(rows), "backlog_overdue": overdue,
            "oldest_wait_h": oldest,
            # THE FENCED HALF OF THE WAIT. `oldest_wait_h` rises with the clock whatever the
            # drain does -- eighteen minutes of wall time moved it 6.0 -> 6.3 and failed the law
            # gate on the third live pass, for a queue that was entirely inside its own lease.
            # Only the part ABOVE the lease is neglect, and that part is zero while the drain
            # keeps up. Both numbers are published; this is the one the ratchet reads.
            "overdue_wait_h": round(max(0.0, oldest - LEASE_H), 1),
            "total_sources": total, "by_kind": dict(sorted(by_kind.items())),
            "no_url": sum(1 for r in rows
                          if not str(r.get("url") or "").startswith(("http://", "https://"))),
            "lease_h": LEASE_H,
            "why": (f"{len(rows)} of {total} registered source(s) have never been fetched; "
                    f"{overdue} past the {LEASE_H:.0f}h lease")}


def pass_size(backlog: Mapping[str, Any], *, floor: int = 60, ceiling: int = 400) -> int:
    """How many rows THIS pass must take to clear the backlog inside the organ's own lease.

    DERIVED FROM THE OBLIGATION, NOT TYPED. The lease says a registered source may wait at most
    `LEASE_H` hours; the leg runs hourly; so a backlog of N rows obliges N / LEASE_H rows per
    pass, and anything less is a fence the organ cannot satisfy no matter how long it runs. The
    first live seed made this concrete: 1,594 rows registered in one pass against a typed cap of
    60 would have drained 1,440 a day and fallen behind by 154 every day, failing its own ratchet
    forever while doing exactly what it was built to do.

    THE STEADY-STATE SHARE ALONE CANNOT CATCH UP, AND THAT IS MEASURED (2026-09-23, trading box).
    `uncrawled_total / LEASE_H` is the rate that keeps a backlog ALREADY INSIDE its lease inside
    it. It says nothing about rows that are already PAST the lease, and those rows are owed NOW,
    not spread over another lease. On the box the pass read 3,569 uncrawled -> took 149, while
    1,726 rows were already overdue; `overdue_wait_h` rose 128.0 -> 139.5 and breached its own
    ratchet, and `check_coverage_drain.py` failed the law gate with "fix: this organ's own drain
    pass, with a larger --budget-s or more passes". The budget was NOT the binding constraint --
    the pass spent 124.1 s of a 900 s budget and stopped because `take` ran out, not the clock.
    So the derived cap was the fence the organ could not satisfy no matter how long it ran, which
    is the exact defect the paragraph above it was written about, one population over.

    The overdue count is therefore ADDED to the steady-state share: the pass owes the catch-up
    plus the rate that stops the queue growing while it catches up. This can only ever make a
    pass take MORE rows; there is no path here that takes fewer than the old formula did.

    The FLOOR keeps a small backlog from shrinking the pass to nothing (a drain that takes three
    rows an hour is not a drain); the CEILING is politeness, not memory -- these are other
    people's servers and `moat_collectors` spaces its own requests per host, so a pass that
    planned two thousand fetches would simply spend its whole clock on the first few hundred.
    """
    rows = backlog.get("uncrawled_total")
    if not isinstance(rows, (int, float)) or rows <= 0:
        return int(floor)
    steady = int(float(rows) / max(1.0, LEASE_H)) + 1
    overdue = backlog.get("backlog_overdue")
    owed_now = int(overdue) if isinstance(overdue, (int, float)) and overdue > 0 else 0
    return max(int(floor), min(int(ceiling), steady + owed_now))


def run(*, budget_s: float = 900.0, max_sources: int | None = None, dry_run: bool = False,
        seed: bool = True, db: Path | None = None, ledger: Path | None = None,
        now: datetime | None = None) -> dict[str, Any]:
    """One coverage-drain pass. Returns the report it writes; never raises."""
    started = time.monotonic()
    budget = budget_seconds(budget_s)
    conn = connect(db)
    grounds = lawful_grounds()
    report: dict[str, Any] = {
        "at": _now(), "organ": SOURCE, "budget_s": round(budget, 1), "dry_run": bool(dry_run),
        "rule": RULE, "lawful_grounds_known": len(grounds)}
    if conn is None:
        report.update({
            "backlog": measure_backlog(None, now), "seed": {"status": "skipped"},
            "drain": {"status": "skipped"}, "layers": verify_layers(None),
            "verdict": {"gap": "UNMEASURED",
                        "what": "the alpha registry is not readable on this host",
                        "fix": "run this organ where data/alpha_registry.sqlite lives"},
            "ratchet": {"ceilings": {}, "floors": {}, "over": {}, "under": {},
                        "rule": "no reading, so no ratchet was moved"},
            "status": "UNMEASURED", "elapsed_s": round(time.monotonic() - started, 1)})
        return report
    with closing(conn):
        before = measure_backlog(conn, now)
        report["before"] = before
        report["reopened"] = ({"reopened": 0, "statuses": {}, "why": "dry run"} if dry_run
                              else reopen_deleted_brakes(conn))
        if seed and not dry_run:
            report["seed"] = seed_grounds(conn, grounds)
        else:
            known = 0
            with suppress(sqlite3.Error):
                have = {str(r[0]) for r in
                        conn.execute("SELECT source_id FROM sources").fetchall()}
                known = sum(1 for g in grounds if str(g["source_id"]) in have)
            report["seed"] = {"status": "skipped" if not seed else "dry_run",
                              "considered": len(grounds), "already": known, "inserted": 0}
        spent = time.monotonic() - started
        # SIZE THE PASS AFTER SEEDING, not before: the rows this pass just registered are part
        # of the obligation the lease puts on it, and a pass sized off the pre-seed backlog would
        # be systematically too small on exactly the passes that widened the ground.
        mid = measure_backlog(conn, now)
        take = int(max_sources) if max_sources is not None else pass_size(mid)
        report["pass_size"] = {"took": take, "derived": max_sources is None,
                               "backlog": mid.get("uncrawled_total"),
                               "overdue": mid.get("backlog_overdue"), "lease_h": LEASE_H,
                               "why": (f"{mid.get('backlog_overdue')} overdue (owed now) + "
                                       f"{mid.get('uncrawled_total')} uncrawled / "
                                       f"{LEASE_H:.0f}h lease = {take} per hourly pass"
                                       if max_sources is None
                                       else f"--max-sources {take} given on the command line")}
        report["drain"] = drain(conn, budget_s=max(5.0, budget - spent),
                                max_sources=take, dry_run=dry_run, now=now)
        after = measure_backlog(conn, now)
        report["backlog"] = after
        report["layers"] = verify_layers(conn)

    prev_doc = load_ledger(ledger)
    prev = prev_doc.get("ceilings") or {}
    prev_floors = prev_doc.get("floors") or {}
    drained_before = float(prev_floors.get("drained_total") or 0.0)
    drained_now = drained_before + float(report["drain"].get("crawled") or 0.0) \
        + float(len(report["drain"].get("refused") or ()))
    current = {"backlog_overdue": after.get("backlog_overdue"),
               "overdue_wait_h": after.get("overdue_wait_h"),
               "oldest_wait_h": after.get("oldest_wait_h"),
               "uncrawled_total": after.get("uncrawled_total"),
               "drained_total": drained_now,
               "depth_min": (report["layers"].get("depth") or {}).get("min"),
               "breadth_min": (report["layers"].get("breadth") or {}).get("min"),
               "ingestion_min": (report["layers"].get("ingestion") or {}).get("min")}
    report["measured"] = current
    report["ratchet"] = ratchet({**prev, **prev_floors}, current)
    report["verdict"] = largest_gap(after, report["layers"], grounds,
                                    (report["drain"] or {}).get("collector") or {})
    report["seeded_this_pass"] = int((report["seed"] or {}).get("inserted") or 0)
    report["status"] = "MEASURED"
    report["elapsed_s"] = round(time.monotonic() - started, 1)
    report["summary"] = _summary(report)
    if not dry_run:
        hist = list(prev_doc.get("history") or ())[-49:]
        hist.append({"at": report["at"], **current,
                     "seeded": report["seeded_this_pass"],
                     "crawled": report["drain"].get("crawled"),
                     "refused": len(report["drain"].get("refused") or ())})
        save_ledger({"at": report["at"], "ceilings": report["ratchet"]["ceilings"],
                     "floors": report["ratchet"]["floors"], "lease_h": LEASE_H,
                     "rule": report["ratchet"]["rule"], "history": hist}, ledger)
    return report


def _summary(report: Mapping[str, Any]) -> list[str]:
    before = report.get("before") or {}
    after = report.get("backlog") or {}
    drain_r = report.get("drain") or {}
    layers = report.get("layers") or {}
    verdict = report.get("verdict") or {}
    tot = layers.get("totals") or {}
    return [
        f"uncrawled {before.get('uncrawled_total')} -> {after.get('uncrawled_total')} "
        f"(overdue {before.get('backlog_overdue')} -> {after.get('backlog_overdue')}, "
        f"oldest {after.get('oldest_wait_h')}h)",
        f"seeded {report.get('seeded_this_pass')} lawful ground(s) of "
        f"{report.get('lawful_grounds_known')} known; resolved "
        f"{drain_r.get('resolved_roots')} rootless row(s); reopened "
        f"{(report.get('reopened') or {}).get('reopened')} refused under a DELETED brake",
        f"crawled {drain_r.get('crawled')}, refused "
        f"{len(drain_r.get('refused') or ())} permanently "
        f"({drain_r.get('collector', {}).get('status')})",
        f"layers mapped {tot.get('mapped', 0)} / absent {tot.get('absent_declared', 0)} / "
        f"refused {tot.get('refused_hard_boundary', 0)} / "
        f"declared-unverified {tot.get('declared_unverified', 0)} / "
        f"unmapped {tot.get('unmapped', 0)} over {len(layers.get('packs') or {})} pack(s)",
        f"depth {(layers.get('depth') or {}).get('min')}/"
        f"{(layers.get('depth') or {}).get('median')}/"
        f"{(layers.get('depth') or {}).get('max')} | breadth "
        f"{(layers.get('breadth') or {}).get('min')}/"
        f"{(layers.get('breadth') or {}).get('median')}/"
        f"{(layers.get('breadth') or {}).get('max')} | ingestion "
        f"{(layers.get('ingestion') or {}).get('min')}/"
        f"{(layers.get('ingestion') or {}).get('median')}/"
        f"{(layers.get('ingestion') or {}).get('max')} (min/median/max)",
        f"worst by distance from the complete pack: "
        f"{((layers.get('parity') or {}).get('worst_by_distance') or [])[:5]}",
        f"cells {layers.get('cells_total')} over "
        f"{layers.get('jurisdictions_total')} jurisdiction(s); "
        f"{layers.get('no_lawful_ground_total')} measured NO_LAWFUL_GROUND row(s); "
        f"{len(layers.get('cells_unmeasured') or ())} pack(s) expose no cells()",
        f"LARGEST GAP: {verdict.get('gap')} (EV {verdict.get('ev')}) -- {verdict.get('what')}",
    ]


# ------------------------------------------------------------------------------------- the CLI
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--once", action="store_true",
                    help="one pass and exit; the hourly leg always passes this")
    ap.add_argument("--budget-s", type=float, default=900.0,
                    help="wall budget; scaled down when the box is short of memory")
    ap.add_argument("--max-sources", type=int, default=None,
                    help="how many pending rows this pass may take; DERIVED from the backlog "
                         "and the lease when omitted, which is what the hourly leg does")
    ap.add_argument("--no-seed", action="store_true",
                    help="measure and drain without registering new lawful ground")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write nothing, fetch nothing, stamp nothing")
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args(list(argv) if argv is not None else None)

    report = run(budget_s=float(args.budget_s),
                 max_sources=None if args.max_sources is None else int(args.max_sources),
                 dry_run=bool(args.dry_run), seed=not bool(args.no_seed))
    for line in report.get("summary") or [f"status {report.get('status')}"]:
        print(f"  {line}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    _write_json(Path(args.out), report)
    print(f"  -> {args.out}")
    with suppress(Exception):
        from libs.ops import events as ev
        ev.emit("LEG_DONE", leg=SOURCE, outcome="ok",
                uncrawled=(report.get("backlog") or {}).get("uncrawled_total"),
                overdue=(report.get("backlog") or {}).get("backlog_overdue"),
                seeded=report.get("seeded_this_pass"),
                gap=(report.get("verdict") or {}).get("gap"))
    return 0


__all__ = [
    "CLEARED",
    "DELETED_BRAKE_STATUSES",
    "DEPTH_REFERENCE",
    "DEPTH_TARGETS",
    "DEPTH_WEIGHTS",
    "INTERNAL_PREFIXES",
    "LAYER_SETTLED",
    "LEASE_H",
    "REFUSAL_STATUSES",
    "REFUSED_LABELS",
    "REPORT",
    "RULE",
    "SOURCE_LAYERS",
    "budget_seconds",
    "build_root_index",
    "connect",
    "crawled_hosts",
    "deleted_brake_refusals",
    "depth_score",
    "drain",
    "drain_order",
    "forest_grounds",
    "host_keys",
    "host_of",
    "largest_gap",
    "lawful_grounds",
    "load_ledger",
    "main",
    "measure_backlog",
    "no_lawful_ground",
    "pack_cells",
    "pack_sources",
    "pass_size",
    "pending_rows",
    "ratchet",
    "refusal_for",
    "refused_hosts",
    "register_refusal",
    "registry_grounds",
    "reopen_deleted_brakes",
    "resolve_root",
    "run",
    "save_ledger",
    "seed_grounds",
    "terms_note",
    "verify_layers",
]


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
