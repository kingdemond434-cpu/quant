"""DISCOVERY AUDIT: how much of a WITHHELD benchmark of real datasets the discovery path found.

WHY A WITHHELD BENCHMARK. Every discovery organ reports what it found; none can report what it
missed, because the denominator -- the world's datasets -- is unknowable. A fixed, independent
benchmark of real, publicly accessible datasets is the closest honest denominator: ~60 direct
data URLs and API endpoints across languages, regions and observation types (weather, shipping,
energy, agriculture, labour, prices, trade, satellite-derived numerics, payments, procurement).
What this measures is BENCHMARK COVERAGE, NOT WORLD COVERAGE, and the report says so in its
first field.

WITHHELD MEANS WITHHELD, TWICE. The committed benchmark is SEALED: salted hashes of each URL and
dataset id plus its type/region/language, nothing a reader could copy (`--seal`); the plaintext
is kept off the repository. And a benchmark the seeds can read measures the seeds, not discovery: copy
one URL into a roster and recall rises without discovering anything. So the audit first checks
every seed the discovery path starts from -- the catalog-routes roster, the deep-forest, free-
stack, Asia and event rosters, the acquirer's `_SEED_ENDPOINTS`, every country pack's declared
URLs, and the URL literals in the discovery organs' own code -- and if any benchmark URL or its
exact dataset id appears in any of them the verdict is CONTAMINATED and no recall is published.

ROTATION. A weekly subset (deterministic by ISO week, so every run in a week measures the same
items and the next week a different mix) is measured in full; the whole benchmark's recall is
published beside it so a lucky week is visible as one.

PER ITEM: discovered (a row in any `intelligence/world/discoveries_*.json`, or the acquirer's
registry `by_url`), via which route, endpoint resolved (the row carries a data URL, not only a
landing page), ingested (series in the registry), field coverage (series acquired / numeric
columns the item declares), first-discovery delay (hours from the item's entry to the benchmark
to the first row naming it), and downstream use (series named in `data/dataset_use` or registry
consumers when either exists, else UNMEASURED -- an absent ledger is not a zero).

No network. Cheap: one read of the discoveries files and the registry per pass.

    python desks/mt5/research/discovery_audit.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: THE SEALED BENCHMARK. Only salted hashes of each item's URL and dataset id are committed, with
#: its type/region/language; the plaintext lives off the repo (/mnt/project-files/withheld/), so no
#: seat, miner or session reading the tree can copy a benchmark item into a seed.
BENCHMARK = DESK / "data" / "discovery_audit" / "benchmark.sealed.json"
SEALED_KEEP = ("type", "region", "country", "language", "columns", "benchmark_since")
REPORT = DESK / "reports" / "DISCOVERY_AUDIT.json"
WORLD = DESK / "data" / "intelligence" / "world"
REGISTRY = DESK / "data" / "acquired" / "registry.json"
DATASET_USE = DESK / "data" / "dataset_use"
LABEL = "benchmark coverage, not world coverage"
UNMEASURED = "UNMEASURED"
DEFAULT_WEEKLY_SHARE = 0.34

#: Data rosters the discovery path seeds from. A benchmark URL or id in any of them is
#: contamination. Missing files are skipped (and listed), never read as clean.
SEED_ROSTERS: tuple[Path, ...] = (
    DESK / "data" / "catalog_routes" / "roster.json",
    DESK / "data" / "deep_forest_sources.json",
    DESK / "data" / "free_stack_sources.json",
    DESK / "data" / "asia_sources.json",
    DESK / "data" / "event_consensus_sources.json",
    DESK / "data" / "blog_social_feeds.json",
    DESK / "data" / "prospector_targets.json",
)
#: Discovery organs whose source code carries seed URLs as literals.
SEED_CODE: tuple[Path, ...] = (
    DESK / "side_channels" / "world_crawler.py",
    DESK / "research" / "deep_forest_miner.py",
    DESK / "research" / "index_discovery.py",
    DESK / "research" / "world_dataset_hunter.py",
    DESK / "research" / "catalog_routes.py",
    DESK / "research" / "acquire_datasets.py",
)
_URL = re.compile(r"https?://[^\s\"'<>)\]}]+")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def norm_url(url: str) -> str:
    """Scheme dropped, host lower-cased, trailing slash and fragment removed: the identity two
    spellings of one URL share."""
    u = str(url or "").strip().split("#", 1)[0]
    u = re.sub(r"^https?://", "", u, flags=re.IGNORECASE)
    host, _, rest = u.partition("/")
    out = host.lower() + ("/" + rest if rest else "")
    return out.rstrip("/")


def id_pattern(dataset_id: str) -> re.Pattern[str]:
    """The exact id as a token: not preceded or followed by a letter or digit."""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(dataset_id) + r"(?![A-Za-z0-9])",
                      re.IGNORECASE)


# ------------------------------------------------------------------------------- sealing ----
def _h(salt: str, text: str) -> str:
    return hashlib.sha256(f"{salt}|{text}".encode()).hexdigest()[:32]


def _sealed(item: Mapping[str, Any]) -> bool:
    return "url_h" in item or "id_h" in item


_ALNUM = re.compile(r"[A-Za-z0-9]+")


def id_candidates(text: str, *, max_runs: int = 6, max_len: int = 64) -> set[str]:
    """Every substring `id_pattern` could match: bounded by non-alphanumerics at both ends,
    spanning at most `max_runs` alphanumeric runs. Lower-cased, so the match is case-blind."""
    runs = [(m.start(), m.end()) for m in _ALNUM.finditer(text)]
    out: set[str] = set()
    for i, (a, _) in enumerate(runs):
        for j in range(i, min(i + max_runs, len(runs))):
            b = runs[j][1]
            if b - a > max_len:
                break
            out.add(text[a:b].lower())
    return out


def seal(benchmark: Mapping[str, Any], salt: str) -> dict[str, Any]:
    """The committed form of a plaintext benchmark: opaque ids, salted hashes, no URL or title."""
    items = []
    for k, it in enumerate(benchmark.get("items") or []):
        row: dict[str, Any] = {"id": f"b{k:03d}"}
        row.update({f: it[f] for f in SEALED_KEEP if f in it})
        if it.get("url"):
            row["url_h"] = _h(salt, norm_url(str(it["url"])).lower())
        if it.get("dataset_id"):
            row["id_h"] = _h(salt, str(it["dataset_id"]).lower())
        items.append(row)
    return {k: v for k, v in benchmark.items() if k != "items"} | {
        "salt": salt, "sealed": True, "items": items}


def _row_hashes(row: dict[str, Any], salt: str) -> tuple[set[str], set[str], set[str]]:
    """(all-url hashes, endpoint hashes, id-candidate hashes) of a discovery row, cached on it."""
    key = f"_h:{salt}"
    if key not in row:
        row[key] = ({_h(salt, u) for u in row["all_urls"]},
                    {_h(salt, u) for u in row["endpoints"]},
                    {_h(salt, c) for c in id_candidates(row["blob"])})
    return row[key]


# ------------------------------------------------------------------------ contamination ----
def _pack_urls() -> list[str]:
    """Every URL the country packs declare -- the same collection `acquire_datasets` walks."""
    try:
        from libs.research import country_lab
    except Exception:  # noqa: BLE001 - an unimportable lab is reported, not read as clean
        return []
    urls: list[str] = []
    for pack_py in sorted((DESK / "research" / "countries").glob("*/pack.py")):
        code = pack_py.parent.name
        if code.startswith("_"):
            continue
        try:
            pack = country_lab.resolve_pack(code)
        except Exception:  # noqa: BLE001, S112 - one unresolvable pack never hides the rest
            continue
        if pack is None:
            continue
        for dataset in pack.datasets:
            urls.extend(str(v) for v in (dataset.how_to_fetch, dataset.source)
                        if str(v).startswith(("http://", "https://")))
        for source in country_lab.source_rows(pack):
            urls.extend(str(v) for v in source.roots if str(v).startswith(("http://", "https://")))
    return urls


def _seed_endpoints() -> list[str]:
    try:
        from acquire_datasets import _SEED_ENDPOINTS
    except Exception:  # noqa: BLE001
        return []
    return [str(u) for u in _SEED_ENDPOINTS]


def seed_sources() -> tuple[dict[str, str], list[str]]:
    """(label -> text the seeds consist of, labels that could not be read)."""
    out: dict[str, str] = {}
    missing: list[str] = []
    for p in SEED_ROSTERS:
        try:
            out[str(p.relative_to(DESK))] = p.read_text("utf-8")
        except OSError:
            missing.append(str(p.relative_to(DESK)))
    for p in SEED_CODE:
        try:
            out[str(p.relative_to(DESK)) + " (url literals)"] = "\n".join(
                _URL.findall(p.read_text("utf-8")))
        except OSError:
            missing.append(str(p.relative_to(DESK)))
    seeds = _seed_endpoints()
    if seeds:
        out["acquire_datasets._SEED_ENDPOINTS"] = "\n".join(seeds)
    else:
        missing.append("acquire_datasets._SEED_ENDPOINTS")
    packs = _pack_urls()
    if packs:
        out["country packs"] = "\n".join(packs)
    else:
        missing.append("country packs")
    return out, missing


def contamination(items: Iterable[Mapping[str, Any]],
                  sources: Mapping[str, str], salt: str = "") -> list[dict[str, Any]]:
    """Every benchmark item whose URL or exact dataset id a seed source contains. Pure."""
    lowered = {k: v.lower() for k, v in sources.items()}
    hits: list[dict[str, Any]] = []
    hashed: dict[str, tuple[set[str], set[str]]] = {}
    for it in items:
        if _sealed(it):
            for label, text in sources.items():
                if label not in hashed:
                    hashed[label] = ({_h(salt, norm_url(u).lower()) for u in _URL.findall(text)},
                                     {_h(salt, c) for c in id_candidates(text)})
                urls, ids = hashed[label]
                if it.get("url_h") and it["url_h"] in urls:
                    hits.append({"id": it.get("id"), "by": "url", "in": label})
                elif it.get("id_h") and it["id_h"] in ids:
                    hits.append({"id": it.get("id"), "by": "dataset_id", "in": label})
            continue
        url = str(it.get("url") or "")
        core = norm_url(url).lower()
        did = str(it.get("dataset_id") or "")
        pat = id_pattern(did) if did else None
        for label, text in sources.items():
            if core and core in lowered[label]:
                hits.append({"id": it.get("id"), "by": "url", "in": label})
            elif pat is not None and pat.search(text):
                hits.append({"id": it.get("id"), "by": "dataset_id", "value": did, "in": label})
    return hits


# ----------------------------------------------------------------------------- rotation ----
def iso_week(when: datetime) -> str:
    y, w, _ = when.isocalendar()
    return f"{y}-W{w:02d}"


def weekly_subset(items: list[dict[str, Any]], when: datetime,
                  share: float = DEFAULT_WEEKLY_SHARE) -> list[dict[str, Any]]:
    """A deterministic subset for the ISO week: same week, same items; next week, a new mix."""
    if not items:
        return []
    key = iso_week(when)
    k = max(1, min(len(items), round(len(items) * float(share))))
    return sorted(items, key=lambda it: hashlib.sha1(
        f"{key}|{it.get('id')}".encode()).hexdigest())[:k]


# ---------------------------------------------------------------------------- discovery ----
def _row_route(row: Mapping[str, Any], fname: str) -> str:
    if row.get("route"):
        return str(row["route"])
    if "deepforest" in fname:
        return "deep_forest"
    return str(row.get("source") or "world_crawler")


def _file_time(fname: str) -> str | None:
    m = re.search(r"(\d{8})(?:_(\d{4}))?", fname)
    if not m:
        return None
    hhmm = m.group(2) or "0000"
    try:
        dt = datetime.strptime(m.group(1) + hhmm, "%Y%m%d%H%M").replace(tzinfo=UTC)
    except ValueError:
        return None
    return dt.isoformat(timespec="seconds")


def load_discoveries(world: Path) -> list[dict[str, Any]]:
    """Every discovery row with its route, first-seen time and a searchable URL blob."""
    out: list[dict[str, Any]] = []
    for f in sorted(world.glob("discoveries_*.json")):
        rows = _read_json(f, [])
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            eps = [str(u) for u in (r.get("endpoints") or []) + (r.get("mirror_endpoints") or [])]
            other = [str(u) for u in (r.get("keyed_endpoints") or [])
                     + (r.get("unparsed_endpoints") or [])
                     + [r.get("url") or "", r.get("landing_page") or ""] if u]
            out.append({
                "route": _row_route(r, f.name), "file": f.name,
                "at": str(r.get("first_discovered_at") or r.get("published")
                          or _file_time(f.name) or ""),
                "endpoints": {norm_url(u).lower() for u in eps},
                "all_urls": {norm_url(u).lower() for u in eps + other},
                "blob": "\n".join([str(r.get("dataset_id") or ""), *eps, *other]),
                "observation_class": bool(r.get("observation_class")),
            })
    return out


def match(item: Mapping[str, Any], rows: Iterable[dict[str, Any]],
          salt: str = "") -> list[dict[str, Any]]:
    """Rows naming the item, by exact URL or by its exact dataset id as a token."""
    if _sealed(item):
        out = []
        for r in rows:
            urls, eps, ids = _row_hashes(r, salt)
            by = ("url" if item.get("url_h") in urls else
                  "dataset_id" if item.get("id_h") in ids else None)
            if by:
                out.append({"route": r["route"], "at": r["at"], "by": by,
                            "endpoint": bool(r["endpoints"]),
                            "endpoint_urls": sorted(r["endpoints"]),
                            "observation_class": r.get("observation_class", False)})
        return sorted(out, key=lambda h: h["at"] or "9999")
    core = norm_url(str(item.get("url") or "")).lower()
    did = str(item.get("dataset_id") or "")
    pat = id_pattern(did) if did else None
    hits = []
    for r in rows:
        if core and core in r["all_urls"]:
            hits.append({"route": r["route"], "at": r["at"], "by": "url",
                         "endpoint": core in r["endpoints"] or bool(r["endpoints"]),
                         "observation_class": r.get("observation_class", False)})
        elif pat is not None and pat.search(r["blob"]):
            hits.append({"route": r["route"], "at": r["at"], "by": "dataset_id",
                         "endpoint": bool(r["endpoints"]),
                         "endpoint_urls": sorted(r["endpoints"]),
                         "observation_class": r.get("observation_class", False)})
    return sorted(hits, key=lambda h: h["at"] or "9999")


def _registry_view(reg: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if reg is None:
        return None
    by_url = {norm_url(u).lower(): (m or {}) for u, m in (reg.get("by_url") or {}).items()}
    return {"by_url": by_url, "series": reg.get("series") or {},
            "consumers": reg.get("consumers")}


def downstream_use(series: list[str], reg: Mapping[str, Any] | None,
                   use_dir: Path) -> bool | str:
    if use_dir.is_dir():
        # A LIVE recorded read (libs/data/dataset_use) is the evidence; a stale one is not use.
        from libs.data import dataset_use as U
        reads = U.census(use_dir)
        return any((reads.get(f"acquired:{s}") or {}).get("live_consumers", 0) > 0
                   for s in series)
    consumers = (reg or {}).get("consumers")
    if isinstance(consumers, dict):
        return any(consumers.get(s) for s in series)
    return UNMEASURED


def measure_item(item: Mapping[str, Any], rows: list[dict[str, Any]],
                 reg: Mapping[str, Any] | None, use_dir: Path, salt: str = "") -> dict[str, Any]:
    hits = match(item, rows, salt)
    core = norm_url(str(item.get("url") or "")).lower()
    view = _registry_view(reg)
    candidate_urls = {u for h in hits for u in h.get("endpoint_urls", [])}
    if core:
        candidate_urls.add(core)
    reg_meta = [view["by_url"][u] for u in candidate_urls if view and u in view["by_url"]]
    if view and item.get("url_h"):
        reg_meta += [m for u, m in view["by_url"].items()
                     if _h(salt, u) == item["url_h"] and u not in candidate_urls]
    routes = sorted({h["route"] for h in hits})
    if not hits and reg_meta:
        routes = ["acquire_registry"]
    discovered = bool(hits or reg_meta)
    series = sorted({s for m in reg_meta for s in (m.get("series") or [])})
    ingested: bool | str = UNMEASURED if view is None else bool(series)
    cols = item.get("columns")
    coverage: float | str
    if view is None or not isinstance(cols, int) or cols <= 0:
        coverage = UNMEASURED
    else:
        coverage = round(min(1.0, len(series) / cols), 3)
    first_at = hits[0]["at"] if hits else None
    delay: float | None = None
    before = False
    if first_at:
        try:
            t0 = datetime.fromisoformat(str(item.get("benchmark_since"))).replace(tzinfo=UTC)
            t1 = datetime.fromisoformat(first_at)
            t1 = t1 if t1.tzinfo else t1.replace(tzinfo=UTC)
            h = (t1 - t0).total_seconds() / 3600.0
            before, delay = h < 0, round(max(0.0, h), 1)
        except (TypeError, ValueError):
            delay = None
    return {
        "id": item.get("id"), "type": item.get("type"), "region": item.get("region"),
        "country": item.get("country"), "language": item.get("language"),
        "discovered": discovered, "routes": routes,
        "first_route": hits[0]["route"] if hits else (routes[0] if routes else None),
        "matched_by": sorted({h["by"] for h in hits}),
        "first_discovered_at": first_at,
        "first_discovery_delay_h": delay if first_at else None,
        "discovered_before_benchmark_entry": before,
        "endpoint_resolved": any(h["endpoint"] for h in hits) or bool(reg_meta),
        "ingested": ingested, "series": series, "field_coverage": coverage,
        "downstream_use": downstream_use(series, reg, use_dir) if series else (
            UNMEASURED if view is None else False),
    }


def recall_by(measured: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in measured:
        if key == "first_route":
            groups[str(m.get("first_route") or "MISSED")].append(m)
        else:
            groups[str(m.get(key) or UNMEASURED)].append(m)
    n = len(measured)
    out: dict[str, dict[str, Any]] = {}
    for g, ms in sorted(groups.items()):
        found = sum(1 for m in ms if m["discovered"])
        out[g] = {"items": len(ms), "discovered": found,
                  # by route the denominator is the whole rotation: a route's share of it
                  "recall": round(found / (n if key == "first_route" else len(ms)), 3)
                  if (n if key == "first_route" else len(ms)) else None}
    return out


def audit(benchmark: Mapping[str, Any], *, now: datetime, rows: list[dict[str, Any]],
          registry: Mapping[str, Any] | None, sources: Mapping[str, str],
          missing_sources: list[str], use_dir: Path) -> dict[str, Any]:
    """The whole audit, from its inputs. Pure apart from reading `use_dir` when it exists."""
    items = [it for it in benchmark.get("items") or [] if isinstance(it, dict) and it.get("id")]
    base: dict[str, Any] = {"label": LABEL, "generated_at": now.isoformat(timespec="seconds"),
                            "iso_week": iso_week(now), "benchmark_items": len(items),
                            "seed_sources_checked": sorted(sources),
                            "seed_sources_unreadable": sorted(missing_sources)}
    if not items:
        return {**base, "verdict": UNMEASURED, "why": "benchmark missing or empty"}
    salt = str(benchmark.get("salt") or "")
    hits = contamination(items, sources, salt)
    if hits:
        return {**base, "verdict": "CONTAMINATED", "contamination": hits, "recall": None,
                "why": ("a benchmark URL or dataset id is readable by the discovery seeds, so "
                        "recall would measure the seeds; replace the item or the seed")}
    rotation = weekly_subset(items, now, float(benchmark.get("weekly_share")
                                               or DEFAULT_WEEKLY_SHARE))
    measured = [measure_item(it, rows, registry, use_dir, salt) for it in rotation]
    every = [measure_item(it, rows, registry, use_dir, salt) for it in items]
    n = len(measured)
    found = sum(1 for m in measured if m["discovered"])
    return {
        **base,
        "verdict": "OK",
        "rotation": [m["id"] for m in measured],
        "recall": round(found / n, 3) if n else None,
        "discovered": found, "measured": n,
        "endpoint_resolved": sum(1 for m in measured if m["endpoint_resolved"]),
        "ingested": (UNMEASURED if registry is None
                     else sum(1 for m in measured if m["ingested"] is True)),
        "recall_by_route": recall_by(measured, "first_route"),
        "recall_by_region": recall_by(measured, "region"),
        "recall_by_type": recall_by(measured, "type"),
        "recall_by_language": recall_by(measured, "language"),
        "full_benchmark_recall": round(sum(1 for m in every if m["discovered"]) / len(every), 3),
        "missed": [{"id": m["id"], "type": m["type"], "region": m["region"]}
                   for m in measured if not m["discovered"]],
        "items": measured,
    }


def run() -> dict[str, Any]:
    now = datetime.now(UTC)
    bench = _read_json(BENCHMARK, {})
    reg = _read_json(REGISTRY, None)
    sources, missing = seed_sources()
    rep = audit(bench if isinstance(bench, dict) else {}, now=now, rows=load_discoveries(WORLD),
                registry=reg if isinstance(reg, dict) else None, sources=sources,
                missing_sources=missing, use_dir=DATASET_USE)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_name(REPORT.name + ".tmp")
    tmp.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    tmp.replace(REPORT)
    rep["stages_measured"] = int(rep.get("measured") or 0)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--seal", nargs=2, metavar=("PLAINTEXT", "SEALED"),
                    help="seal a plaintext benchmark (kept off the repo) into the committed form")
    a = ap.parse_args(argv)
    if a.seal:
        import secrets
        plain = json.loads(Path(a.seal[0]).read_text("utf-8"))
        Path(a.seal[1]).write_text(json.dumps(seal(plain, secrets.token_hex(16)), indent=1),
                                   "utf-8")
        return 0
    r = run()
    print(f"discovery audit ({LABEL}): verdict={r['verdict']} week={r['iso_week']} "
          f"recall={r.get('recall')} ({r.get('discovered')}/{r.get('measured')}) "
          f"full={r.get('full_benchmark_recall')} -> {REPORT}")
    for h in r.get("contamination") or []:
        print(f"   CONTAMINATED {h['id']} by {h['by']} in {h['in']}")
    for m in r.get("missed") or []:
        print(f"   missed {m['id']} ({m['type']}, {m['region']})")
    return 0 if r["verdict"] != "CONTAMINATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
