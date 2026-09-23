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
  3. REFUSE, PERMANENTLY AND BY NAME. A row the source registry marks
     `machine_use_allowed=false`, a route it marks unreachable, a snippets-only search index, a
     path `robots.txt` disallows -- each is stamped, recorded with the rule that refused it and
     the date, and never queued again. THE REFUSAL IS THE KNOWLEDGE. Dropping the row would lose
     the fact that the ground exists; retrying it forever would spend the hour on a wall.
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
  * `oldest_wait_h` -- the age of the oldest uncrawled row. May fall, never rise.
  * `drained_total` -- cumulative rows moved out of the uncrawled set. May rise, never fall.

and `uncrawled_total` is published with its own ceiling, failing ONLY when it rises in a pass that
seeded nothing -- a rise with no new ground is a genuine regression and a rise with new ground is
the organ working.

BOUNDARIES. Public and licensed ground only. No access control is ever bypassed. A page
registered `machine_use_allowed=false` is NEVER fetched -- it is registered and refused. No
crypto-exchange-native ground is hunted (mandate 2026-08-18). Nothing here classifies a source
in order to BRAKE discovery: the labels route use, they never stop a hunt (LAWS, growth
governance Rule 1). Nothing here sizes, allocates or touches the money path.
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
SOURCE = "coverage_drain"

#: How long a registered source may sit uncrawled before it is a DEFECT rather than a queue.
#: One day: the crawl clock is hourly, so a row that has survived twenty-four passes was not
#: waiting its turn, it was being skipped.
LEASE_H = 24.0
#: Refusals, as registered permanent facts. A refusal is stamped so the row leaves the pending
#: set, and it keeps its reason forever so the knowledge that the ground EXISTS is never lost.
REFUSAL_STATUSES: tuple[str, ...] = ("refused-machine-use", "refused-robots", "refused-no-root",
                                     "refused-unreachable")
#: The status a resolved, drainable row is cleared to. `moat_collectors.ACTIVE_STATUSES` accepts
#: it, which is the whole point: this organ clears the path, that organ does the fetching.
CLEARED = "candidate-cleared"
#: Registry-row prefixes an ORGAN mints about the desk's own state rather than about a ground on
#: the web. They can never carry a url and must not read as a lost root.
INTERNAL_PREFIXES: frozenset[str] = frozenset({
    "world_lab", "execution_tape", "regime", "shadow", "lane", "sleeve", "forecast", "book"})
#: The ten source layers, borrowed rather than re-declared.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

RULE = ("the uncrawled set falls every hour: overdue backlog and oldest wait ratchet DOWN, "
        "drained total ratchets UP, every refusal is a permanent registered fact with its rule "
        "and its date, and a page registered machine_use_allowed=false is never fetched")


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
    """{host: newest last_crawled} over every source that was actually fetched.

    This is the measurement the ten-layer verification stands on: a pack's declared root is
    VERIFIED when a row for that host carries a stamp. Nothing here reads the pack's own
    `verified` field, which is hard-coded False by every pack and always will be -- a pack that
    could verify itself would not be evidence of anything.
    """
    out: dict[str, str] = {}
    if not _has_sources(conn):
        return out
    try:
        cur = conn.execute("SELECT url, last_crawled FROM sources "
                           "WHERE last_crawled IS NOT NULL AND last_crawled!=''")
    except sqlite3.Error:
        return out
    for row in cur.fetchall():
        host = host_of(row["url"] or "")
        if not host:
            continue
        stamp = str(row["last_crawled"] or "")
        if stamp > out.get(host, ""):
            out[host] = stamp
    return out


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


def lawful_grounds() -> list[dict[str, Any]]:
    """Every ground the desk could lawfully hold, from both of its own registries, deduplicated
    by source_id. This is the numerator of the whole organ: coverage is what fraction of THIS
    the registry has actually fetched."""
    seen: dict[str, dict[str, Any]] = {}
    for row in [*pack_sources(), *forest_grounds(), *registry_grounds()]:
        seen.setdefault(str(row["source_id"]), row)
    return list(seen.values())


# ------------------------------------------------------------------------------ the refusals
def refusal_for(row: Mapping[str, Any], shares: dict[str, Any] | None) -> tuple[str, str]:
    """(status, reason) when this row must never be fetched, else ("", "").

    THREE INDEPENDENT WALLS, each read from the party entitled to raise it: the source registry's
    own `machine_use_allowed` declaration, the host's `robots.txt`, and the absence of any root
    at all. None of them is a judgement about the ground's VALUE -- a refused ground stays in the
    registry at full weight, because the desk knowing that a ground exists and may not be
    machine-read is strictly more information than the desk never having heard of it.
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
    if shares is not None:
        try:
            from research import source_shares
            hit = source_shares.resolve(shares, row.get("source_id"), url, host_of(url))
            reg_row = (shares.get("rows") or {}).get(hit) if hit else None
            allowed, why = source_shares.machine_use_allowed(reg_row)
            if not allowed:
                return "refused-machine-use", f"MACHINE_USE_REFUSED: {why}"
        except Exception:
            pass
    try:
        from research import moat_collectors
        barred = moat_collectors.robots_barred(url)
    except Exception:
        barred = ""
    if barred:
        return "refused-robots", f"ROBOTS_DISALLOW: {barred}"
    return "", ""


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
def seed_grounds(conn: sqlite3.Connection, grounds: Sequence[Mapping[str, Any]],
                 *, limit: int = 4000) -> dict[str, Any]:
    """Write every lawful ground the registry has never heard of into `sources`.

    It RAISES the uncrawled count and that is correct: the count was low because the desk had
    not written down what it knew, not because the ground had been covered. The ratchet that
    fails the law gate is on the OVERDUE backlog for exactly this reason.
    """
    out: dict[str, Any] = {"considered": len(grounds), "inserted": 0, "already": 0,
                           "refused_machine_use": 0, "errors": 0}
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
        # A ground the pack itself declares unfetchable is REGISTERED AND REFUSED IN ONE STEP --
        # written down so the desk holds the fact that it exists, stamped so it never queues.
        refused = not bool(row.get("machine_use_allowed", True))
        meta = {"seeded_by": SOURCE, "pack": row.get("pack") or "",
                "label": row.get("label") or "", "alt": list(row.get("alt") or ()),
                "layer": row.get("kind") or ""}
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
                 "refused-machine-use" if refused else CLEARED,
                 str(row.get("licence") or "")[:900],
                 json.dumps(meta, sort_keys=True, default=str),
                 str(row.get("access_label") or "") or None,
                 str(row.get("credibility") or "") or None, "UNTESTED", 0,
                 stamp if refused else None,
                 ("MACHINE_USE_REFUSED: the pack declares machine_use_allowed=false; registered "
                  f"so the ground is known, never fetched [registered {stamp} by {SOURCE}]")
                 if refused else None))
        except sqlite3.Error:
            out["errors"] += 1
            continue
        have.add(sid)
        out["inserted"] += 1
        if refused:
            out["refused_machine_use"] += 1
    with suppress(sqlite3.Error):
        conn.commit()
    return out


# ------------------------------------------------------------------------------- the drain pass
def drain_order(rows: Sequence[Mapping[str, Any]], shares: dict[str, Any] | None,
                now: datetime | None = None) -> list[dict[str, Any]]:
    """The pending set, oldest-and-highest-ROI first.

    LEXICOGRAPHIC, not a weighted sum, for the reason `moat_collectors.source_roi` gives: any
    single number lets a prolific ground buy rank with volume. Here the first key is the
    published crawl share (the registry's own measured intel ROI, absent = 0.0, which puts an
    unmeasured ground behind a measured payer but AHEAD of a measured dud) and the second is
    age descending, so the 134-hour row at the front of the queue leaves it first.
    """
    scored: list[tuple[float, float, dict[str, Any]]] = []
    for row in rows:
        share = 0.0
        if shares is not None:
            with suppress(Exception):
                from research import source_shares
                got = source_shares.share_for(shares, row.get("source_id"), row.get("url"),
                                              host_of(str(row.get("url") or "")))
                share = float(got or 0.0)
        age = _age_h(row.get("first_seen"), now) or 0.0
        scored.append((share, age, dict(row)))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [r for _, _, r in scored]


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
    ordered = drain_order(pending, shares, now)[:max(0, int(max_sources))]

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
        out["collector"] = _run_collectors(conn, budget_s=left, max_sources=len(drainable))
        out["crawled"] = int(out["collector"].get("sources_visited") or 0)
    elif drainable and dry_run:
        out["collector"] = {"status": "dry_run",
                            "why": f"{len(drainable)} row(s) would be crawled"}
    elif drainable:
        out["collector"] = {"status": "no_budget",
                            "why": f"{left:.1f}s left after the refusal pass; the frontier "
                                   "resumes next hour rather than restarting"}
    return out


def _run_collectors(conn: sqlite3.Connection, *, budget_s: float,
                    max_sources: int) -> dict[str, Any]:
    """The existing capture machinery, driven on the rows this organ just cleared.

    `research/moat_collectors.py` owns the robots probe, the media typing, the point-in-time
    capture, the normaliser and the claim writer. Writing a second crawler here would be a second
    set of manners against the same hosts, which is how a desk gets blocked.
    """
    try:
        from research import moat_collectors
    except Exception as exc:
        return {"status": "unavailable", "why": f"{type(exc).__name__}: {exc}"}
    try:
        report = moat_collectors.run(budget_s=float(budget_s), max_sources=int(max_sources),
                                     conn=conn)
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
    tot = dict.fromkeys(("mapped", "absent_declared", "declared_unverified", "unmapped"), 0)
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
            if hit:
                state = "MAPPED"
                why = f"{len(hit)}/{len(hosts)} declared host(s) carry a last_crawled stamp"
            elif absent:
                state = "ABSENT_DECLARED"
                why = str(absent[0].get("notes") or "declared absent with a reason")[:220]
            elif declared:
                state = "DECLARED_UNVERIFIED"
                why = (f"{len(declared)} source(s) over {len(hosts)} host(s) declared and none "
                       f"fetched; this is drainable work, not an absence")
            else:
                state = "UNMAPPED"
                why = "the pack names neither a source nor a declared absence for this layer"
            rows[layer] = {"state": state, "declared": len(declared), "absent": len(absent),
                           "hosts": sorted(hosts), "verified_hosts": hit, "why": why}
            tot[state.lower()] = tot.get(state.lower(), 0) + 1
        mapped = sum(1 for v in rows.values()
                     if v["state"] in ("MAPPED", "ABSENT_DECLARED"))
        out["packs"][code] = {
            "layers": rows, "layers_mapped": mapped, "layers_total": len(SOURCE_LAYERS),
            "unverified": [k for k, v in rows.items() if v["state"] == "DECLARED_UNVERIFIED"],
            "unmapped": [k for k, v in rows.items() if v["state"] == "UNMAPPED"],
            "jurisdictions": [str(c).lower()
                              for c in (getattr(mod, "JURISDICTIONS", None) or (code,))]}
    out["totals"] = tot
    out["packs_full_depth"] = sorted(c for c, v in out["packs"].items()
                                     if v["layers_mapped"] == len(SOURCE_LAYERS))
    return out


# ----------------------------------------------------------------------------- the daily verdict
def largest_gap(backlog: Mapping[str, Any], layers: Mapping[str, Any],
                grounds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """THE ONE LARGEST INFORMATION GAP, by expected value, named so a person reads it at 08:00.

    EV is the desk's own priority form (LAWS 5n): value x reach / cost. Three candidate families
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

    `backlog_overdue` and `oldest_wait_h` may FALL and never rise; `drained_total` may RISE and
    never fall. A quantity with no previous reading ENTERS at its measured value rather than at
    zero -- the desk has broken this exact rule before by inventing a floor it had not measured
    (L1.50, and the 8 GB/96 GB memory floor in CLAUDE.md).
    """
    prev = dict(previous or {})
    out: dict[str, Any] = {"ceilings": {}, "floors": {}, "over": {}, "under": {}, "first": []}
    for key in ("backlog_overdue", "oldest_wait_h", "uncrawled_total"):
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
    cur_drained = current.get("drained_total")
    if cur_drained is not None:
        cur_drained = float(cur_drained)
        old = prev.get("drained_total")
        if old is None:
            out["floors"]["drained_total"] = cur_drained
            out["first"].append("drained_total")
        else:
            out["floors"]["drained_total"] = max(float(old), cur_drained)
            if cur_drained < float(old):
                out["under"]["drained_total"] = {"floor": float(old), "current": cur_drained}
    out["rule"] = ("backlog and wait ratchet DOWN, drained total ratchets UP; a quantity with no "
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
                "oldest_wait_h": None, "total_sources": None, "by_kind": {},
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
    return {"measured": True, "uncrawled_total": len(rows), "backlog_overdue": overdue,
            "oldest_wait_h": round(max(ages), 1) if ages else 0.0,
            "total_sources": total, "by_kind": dict(sorted(by_kind.items())),
            "no_url": sum(1 for r in rows
                          if not str(r.get("url") or "").startswith(("http://", "https://"))),
            "lease_h": LEASE_H,
            "why": (f"{len(rows)} of {total} registered source(s) have never been fetched; "
                    f"{overdue} past the {LEASE_H:.0f}h lease")}


def run(*, budget_s: float = 900.0, max_sources: int = 60, dry_run: bool = False,
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
        report["drain"] = drain(conn, budget_s=max(5.0, budget - spent),
                                max_sources=max_sources, dry_run=dry_run, now=now)
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
               "oldest_wait_h": after.get("oldest_wait_h"),
               "uncrawled_total": after.get("uncrawled_total"),
               "drained_total": drained_now}
    report["measured"] = current
    report["ratchet"] = ratchet({**prev, **prev_floors}, current)
    report["verdict"] = largest_gap(after, report["layers"], grounds)
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
        f"{drain_r.get('resolved_roots')} rootless row(s)",
        f"crawled {drain_r.get('crawled')}, refused "
        f"{len(drain_r.get('refused') or ())} permanently "
        f"({drain_r.get('collector', {}).get('status')})",
        f"layers mapped {tot.get('mapped', 0)} / absent {tot.get('absent_declared', 0)} / "
        f"declared-unverified {tot.get('declared_unverified', 0)} / "
        f"unmapped {tot.get('unmapped', 0)} over {len(layers.get('packs') or {})} pack(s)",
        f"LARGEST GAP: {verdict.get('gap')} (EV {verdict.get('ev')}) -- {verdict.get('what')}",
    ]


# ------------------------------------------------------------------------------------- the CLI
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--once", action="store_true",
                    help="one pass and exit; the hourly leg always passes this")
    ap.add_argument("--budget-s", type=float, default=900.0,
                    help="wall budget; scaled down when the box is short of memory")
    ap.add_argument("--max-sources", type=int, default=60,
                    help="how many pending rows this pass may take")
    ap.add_argument("--no-seed", action="store_true",
                    help="measure and drain without registering new lawful ground")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write nothing, fetch nothing, stamp nothing")
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args(list(argv) if argv is not None else None)

    report = run(budget_s=float(args.budget_s), max_sources=int(args.max_sources),
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


__all__ = ["LEASE_H", "REPORT", "RULE", "SOURCE_LAYERS", "budget_seconds", "build_root_index",
           "connect", "crawled_hosts", "drain", "drain_order", "forest_grounds", "host_keys",
           "host_of", "largest_gap", "lawful_grounds", "load_ledger", "main", "measure_backlog",
           "pack_sources", "pending_rows", "ratchet", "refusal_for", "register_refusal",
           "registry_grounds", "resolve_root", "run", "save_ledger", "seed_grounds",
           "verify_layers"]


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
