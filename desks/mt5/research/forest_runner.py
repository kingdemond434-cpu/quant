"""THE FOREST RUNNER -- one regional research civilization, eleven agents, all at once.

    python forest_runner.py --forest korea --once --budget-s 3000
    python forest_runner.py --forest north_america --once --dry-run --workers 2

WHAT IT IS. `libs/research/forests.py` says which civilizations exist, what they cover and what
compute each is entitled to this hour. This is the organ that RUNS one of them: the eleven roles
of `forests.ROLES` in a thread pool sized by the allocator, each with its own budget slice and
its own try/except, so one role's failure costs the other ten nothing and a forest is never idle.

IT REUSES THE DESK'S ORGANS; IT REIMPLEMENTS NONE. Source scouts ask `country_lab`'s own native
query seeds (and `polyglot`'s native terminology where a pack has not landed) and register
through `source_frontier`; official-data agents run the country data planes (`countries/kr/
data_plane.py` is the pattern) or record the dataset as a NEED; practitioner agents read the
deep forest's grounds and claims for this region's languages; academic and code agents use
`knowledge_graph` and `source_civilizations`; archive agents use `archaeology`; failure miners
use `graveyard_resurrection.classify_failure` on this region's dead cells; mechanism extractors
use `transformation_miners`; data agents write PIT-safe series into `data/axes/`; candidate
compilers donate through `proposer_common`; source-ROI agents read the registry's `source_yield`.

THREE PROPERTIES IT HOLDS ON PURPOSE.

**EVERY WRITE GOES THROUGH THE DEDUP CHAIN FIRST.** Nothing in this file writes a discovery
without `dedup_chain.dedup` deciding NEW / DUPLICATE_OF / DESCENDANT_OF, and a duplicate adds a
PROVENANCE EDGE rather than a row. Ten agents finding one strategy on ten repost sites therefore
produce one mechanism and nine edges -- across roles and across forests, because the view is
seeded from the registry the whole federation shares.

**A FOREST WITH NO PACK STILL RUNS.** `north_america` has no country pack on this box today. Its
source scout works from the mandate's own terms, and the other ten roles report UNMEASURED
NAMING THE PACK AND THE PATH that would measure them. An idle forest and an unmeasured one look
identical in a count and are opposite findings (L1.28a), so they are never rendered the same.

**NETWORK CALLS ONLY THROUGH THE DESK'S EXISTING FETCHERS.** This file opens no socket; the data
planes and the deep-forest miner own every fetch. A ground whose terms, robots or licence note
says something is REGISTERED WITH THAT NOTE AS A LABEL AND MINED (LAWS 5e, 2026-09-23) -- the
label routes REDISTRIBUTION, never discovery. The five acts of
`libs.research.access_classifier.HARD_BOUNDARY` are the only refusals left. No secret is read or
printed here.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from libs.research import dedup_chain as dc  # noqa: E402
from libs.research import forests as F  # noqa: E402

REPORTS = DESK / "reports"
DATA = DESK / "data"
AXES = DATA / "axes"
RUNS_JSONL = DATA / "forest_runs.jsonl"
GROUNDS_JSON = DATA / "deep_forest_sources.json"
CLAIMS_JSONL = DATA / "deep_forest_claims.jsonl"
UNIVERSE_JSON = DATA / "universe" / "universe.json"
COUNTRIES = DESK / "research" / "countries"

UNMEASURED = F.UNMEASURED
GENERATOR = "forest_runner"

#: Rows any one role carries forward per pass. A cap is a compute budget and it SAYS SO: what it
#: leaves behind is reported as owed, never dropped silently.
MAX_PER_ROLE = 60
#: Lines read from an append-only ledger per pass. The claims file is tens of MB on the box.
MAX_LEDGER_BYTES = 24 * 1024 * 1024
MAX_LEDGER_ROWS = 4000
#: Discoveries pulled from the registry to SEED the dedup view, so a mechanism another forest
#: already recorded is recognised as a duplicate rather than minted twice.
VIEW_SEED_ROWS = 1500
#: A dependent role (data agents, candidate compilers) waits at most this share of its own budget
#: for the role that feeds it, then reports what it got. It never blocks the pass.
DEPENDENCY_WAIT_SHARE = 0.6

#: The ten source layers, the vocabulary every scout and pack tags a source with.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: Ground `kind` (deep_forest_sources.json) -> the role that owns it. A kind absent here belongs
#: to the practitioner role, which is the desk's broadest reader.
KIND_ROLE: dict[str, str] = {
    "dataset": "official_data", "macro": "official_data",
    "research": "academic", "academic": "academic",
    "code": "code", "notebook": "code",
    "archive": "archive",
    "column": "practitioner", "blog": "practitioner", "interview": "practitioner",
    "forum": "practitioner", "community": "practitioner", "qa": "practitioner",
    "social": "practitioner", "video": "practitioner", "competition": "practitioner",
}


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl_tail(path: Path, max_rows: int = MAX_LEDGER_ROWS) -> list[dict[str, Any]]:
    """The last rows of an append-only ledger, bounded by BYTES as well as rows."""
    try:
        size = path.stat().st_size
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open("rb") as fh:
            if size > MAX_LEDGER_BYTES:
                fh.seek(size - MAX_LEDGER_BYTES)
                fh.readline()
            for raw in fh:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return out
    return out[-max_rows:]


# --------------------------------------------------------------------------- packs, lazily
_PACK_CACHE: dict[str, Any] = {}
_PACK_LOCK = threading.Lock()


def pack_module(code: str) -> Any:
    """One country pack, or None. LAZY AND TOLERANT BY CONSTRUCTION: the packs are being written
    concurrently by other builders, so an import error is an absence to report, not a crash."""
    code = str(code).strip().lower()
    with _PACK_LOCK:
        if code in _PACK_CACHE:
            return _PACK_CACHE[code]
    mod: Any = None
    path = COUNTRIES / code / "pack.py"
    if path.exists():
        for name in (f"research.countries.{code}.pack",
                     f"desks.mt5.research.countries.{code}.pack"):
            try:
                mod = importlib.import_module(name)
                break
            except Exception:
                mod = None
        if mod is None:
            try:
                spec = importlib.util.spec_from_file_location(f"forest_pack_{code}", path)
                if spec is not None and spec.loader is not None:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
            except Exception:
                mod = None
    with _PACK_LOCK:
        _PACK_CACHE[code] = mod
    return mod


def data_plane_module(code: str) -> Any:
    """One country's official DATA PLANE (`countries/<cc>/data_plane.py`), or None."""
    path = COUNTRIES / str(code).lower() / "data_plane.py"
    if not path.exists():
        return None
    for name in (f"research.countries.{code}.data_plane",
                 f"desks.mt5.research.countries.{code}.data_plane"):
        with contextlib.suppress(Exception):
            return importlib.import_module(name)
    try:
        spec = importlib.util.spec_from_file_location(f"forest_plane_{code}", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _attr(mod: Any, name: str, default: Any = ()) -> Any:
    return getattr(mod, name, default) if mod is not None else default


def region_package(fid: str) -> Any:
    """A dedicated region package's mandate (japan, macro_region), or None."""
    pkg = F.forest(fid).package
    if not pkg:
        return None
    name = pkg.replace("desks/mt5/research/", "research.").replace("/", ".")
    for candidate in (f"{name}.mandate", name):
        with contextlib.suppress(Exception):
            return importlib.import_module(candidate)
    return None


# --------------------------------------------------------------------------- the run
@dataclass
class RoleResult:
    """One agent's pass: what it did, or what it could not measure and why."""

    role: str
    ran: bool = False
    seconds: float = 0.0
    new: int = 0
    duplicates: int = 0
    descendants: int = 0
    unmeasured: list[dict[str, str]] = field(default_factory=list)
    why: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return {"role": self.role, "ran": self.ran, "seconds": round(self.seconds, 2),
                "new": self.new, "duplicates": self.duplicates, "descendants": self.descendants,
                "unmeasured": self.unmeasured, "why": self.why, **self.detail}

    def note(self, what: str, why: str) -> None:
        self.unmeasured.append({"what": what, "why": why})


@dataclass
class Run:
    """One forest's pass: the allocation, the shared dedup view, and everything it recorded."""

    forest: str
    allocation: F.Allocation
    dry_run: bool = False
    started: float = field(default_factory=time.monotonic)
    view: dc.RegistryView = field(default_factory=dc.RegistryView)
    lock: threading.Lock = field(default_factory=threading.Lock)
    results: dict[str, RoleResult] = field(default_factory=dict)
    verdicts: list[dc.Verdict] = field(default_factory=list)
    edges: int = 0
    techniques: list[dict[str, Any]] = field(default_factory=list)
    sources_seen: set[str] = field(default_factory=set)
    #: Cross-role hand-offs. A dependent role waits on the event with a timeout and reports what
    #: it got; it never blocks the pass, and the other nine roles never wait at all.
    observations: list[dict[str, Any]] = field(default_factory=list)
    official_done: threading.Event = field(default_factory=threading.Event)
    mechanisms: list[dict[str, Any]] = field(default_factory=list)
    mechanisms_done: threading.Event = field(default_factory=threading.Event)

    @property
    def spec(self) -> F.Forest:
        return F.forest(self.forest)

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def conn(self) -> Any:
        """A connection PER CALLER. sqlite3 refuses a connection across threads, and the roles
        are threads; WAL plus the registry's own 30 s timeout makes concurrent writers safe."""
        if self.dry_run:
            return None
        try:
            return reg.connect()
        except Exception:
            return None


def _instruments(run: Run) -> tuple[list[str], list[dict[str, str]]]:
    """The forest's executable instruments, from its packs or its region package. Absence is
    NAMED: a role that needs instruments and has none says which pack would have carried them."""
    syms: list[str] = []
    missing: list[dict[str, str]] = []
    for code in run.spec.packs:
        mod = pack_module(code)
        if mod is None:
            missing.append({"what": f"pack:{code}",
                            "why": f"{UNMEASURED}: {COUNTRIES / code / 'pack.py'} is not on this "
                                   f"box; another builder owns it"})
            continue
        for s in _attr(mod, "EXECUTABLE_INSTRUMENTS", ()):
            if str(s) not in syms:
                syms.append(str(s))
    mandate = region_package(run.forest)
    if mandate is not None:
        for s in _attr(mandate, "INSTRUMENTS", ()) or _attr(mandate, "JPY_CROSSES", ()):
            if str(s) not in syms:
                syms.append(str(s))
    if not syms and not run.spec.packs and not run.spec.package:
        missing.append({"what": "instruments",
                        "why": f"{UNMEASURED}: this forest declares no country pack and no "
                               f"region package; its instruments are whatever its transmission "
                               f"edges name, and nothing has named them yet"})
    return syms, missing


def _grounds(run: Run) -> list[dict[str, Any]]:
    """The deep forest's declared grounds that belong to THIS forest, by region code."""
    doc = _read_json(GROUNDS_JSON)
    rows = (doc or {}).get("grounds") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return []
    want = {str(c).lower() for c in run.spec.grounds}
    want |= {str(c).lower() for c in run.spec.countries}
    return [g for g in rows if isinstance(g, dict) and str(g.get("region") or "").lower() in want]


# --------------------------------------------------------------------------- the one door
def _provisional_id(payload: Mapping[str, Any]) -> str:
    return "prov_" + dc.content_hash(json.dumps(payload, sort_keys=True, default=str))[:24]


def record(run: Run, res: RoleResult, *, source_id: str, source_type: str, mechanism: str,
           url: str = "", title: str = "", text: str = "", family: str = "",
           instruments: Sequence[str] = (), condition: str = "", horizon: str = "",
           kind: str = "discovery", parents: Sequence[str] = (), conn: Any = None,
           **fields: Any) -> str:
    """THE ONLY WAY A ROLE WRITES ANYTHING. Dedup first, then the registry.

    NEW -> one discovery plus its provenance edges. DESCENDANT_OF -> one discovery carrying its
    ancestor, so it is tested on its own and its lineage is walkable. DUPLICATE_OF -> NO ROW, one
    `retold` edge from this source to the canonical discovery, which is what makes "five grounds
    agree" countable instead of looking like one ground scraped five times.
    """
    item = dc.Item(item_id="", url=url, title=title[:400], text=str(text or "")[:4000],
                   family=family, instruments=tuple(str(s) for s in instruments),
                   condition=condition[:400], horizon=horizon, source_id=source_id,
                   forest=run.forest, role=res.role, kind=kind,
                   parent_ids=tuple(str(p) for p in parents))
    item = dc.Item(**{**item.__dict__, "item_id": _provisional_id({
        "u": item.url, "t": item.title, "x": item.text[:600], "f": item.family,
        "i": list(item.instruments), "c": item.condition})})
    with run.lock:
        verdict = dc.dedup(item, run.view)
        run.verdicts.append(verdict)
    if verdict.is_duplicate:
        res.duplicates += 1
        if not run.dry_run:
            with contextlib.suppress(Exception):
                reg.link("source", source_id, "discovery", verdict.of, "retold", conn=conn)
            with run.lock:
                run.edges += 1
        return verdict.of
    if run.dry_run:
        with run.lock:
            run.view.add(item, mech=verdict.mechanism_key)
        if verdict.is_descendant:
            res.descendants += 1
        else:
            res.new += 1
        return item.item_id
    payload = {"kind": kind, "forest": run.forest, "role": res.role,
               "dedup": verdict.as_row(), **{k: v for k, v in fields.items() if k != "payload"}}
    extra = fields.get("payload")
    if isinstance(extra, Mapping):
        payload.update(dict(extra))
    ancestors = [verdict.of] if verdict.is_descendant else list(parents)
    try:
        did, created = reg.record_discovery(
            source_id=source_id, source_type=source_type, mechanism=str(mechanism)[:400],
            origin="EXTERNAL", generator=f"{GENERATOR}:{run.forest}:{res.role}",
            assets=list(item.instruments), horizons=[horizon or "UNKNOWN"],
            exact_rule_if_known=condition[:400],
            economic_rationale=str(fields.get("why") or title or "")[:800],
            required_data=list(fields.get("required_data") or []),
            falsifier=str(fields.get("falsifier") or ""),
            parent_discovery_ids=ancestors, payload=payload, conn=conn)
    except Exception as exc:
        res.note("registry_write", f"{type(exc).__name__}: {str(exc)[:160]}")
        return ""
    with run.lock:
        run.view.add(item, did, mech=verdict.mechanism_key)
        run.sources_seen.add(source_id)
    if verdict.is_descendant:
        res.descendants += 1
    elif created:
        res.new += 1
    else:
        res.duplicates += 1
    for kind_, src, _dst, relation in verdict.edges:
        if relation == "produced" and kind_ == "source":
            continue                        # record_discovery already wrote source -> discovery
        with contextlib.suppress(Exception):
            reg.link(kind_, src, "discovery", did, relation, conn=conn)
            with run.lock:
                run.edges += 1
    return did


def record_technique(run: Run, res: RoleResult, *, name: str, source_class: str,
                     procedure: str, representation: str, conn: Any = None) -> str:
    """A RESEARCH TECHNIQUE, recorded as a discovery of kind `technique` with a method spec.

    A new way to identify trader crowding is not a hypothesis about a market; it is a METHOD, and
    a method found in one forest is testable against every other forest's equivalent local
    sources. The technique exchange (a later builder) reads these rows; recording them costs one
    row and NOT recording them loses the transferable half of what an agent learned.
    """
    spec = {"technique": name, "source_class": source_class, "extraction_procedure": procedure,
            "representation": representation, "region": run.forest,
            "languages": list(run.spec.languages)}
    with run.lock:
        run.techniques.append(spec)
    return record(run, res, source_id=f"forest:{run.forest}", source_type="technique",
                  mechanism=f"TECHNIQUE {name}: {procedure}"[:400], title=name,
                  text=f"{source_class} | {procedure} | {representation}", kind="technique",
                  conn=conn, payload={"method": spec},
                  why="a method, transferable to every forest with an equivalent local source")


# --------------------------------------------------------------------------- the eleven roles
def role_source_scouts(run: Run, res: RoleResult, budget_s: float) -> None:
    """Discover new local sites, apps and APIs -- in the forest's OWN language, always.

    THE ORDER IS THE POINT: native queries -> native sources -> native terminology. An English
    query against an English index reaches the already-translated corpus, which is the one
    everybody has read. Seeds come from the country pack's own terminology where a pack exists,
    from `polyglot`'s native tables where it does not, and from the MANDATE's terms as the floor
    -- so this role runs for every forest, funded or not, packed or not.
    """
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        seeds: list[dict[str, Any]] = []
        used: list[str] = []
        try:
            from libs.research import country_lab as cl
            for code in run.spec.packs:
                if pack_module(code) is None:
                    continue
                for layer in LAYERS:
                    with contextlib.suppress(Exception):
                        got = cl.native_query_seeds(code, layer)
                        if got:
                            seeds.extend(got[:8])
                            used.append(f"country_lab:{code}:{layer}")
        except Exception as exc:
            res.note("country_lab", f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:120]}")
        try:
            from libs.research import polyglot as pg
            for lang in run.spec.languages:
                for layer in LAYERS:
                    with contextlib.suppress(Exception):
                        got = pg.native_queries(lang, layer, limit=6)
                        seeds.extend({"country": run.forest, "layer": layer, "query": q,
                                      "languages": [lang], "domain": "polyglot"} for q in got)
                        if got:
                            used.append(f"polyglot:{lang}")
                missing = []
                with contextlib.suppress(Exception):
                    missing = pg.layers_unmeasured(lang)
                if missing:
                    res.note(f"native_terms:{lang}",
                             f"{UNMEASURED}: polyglot has no native vocabulary for "
                             f"{lang!r} at layers {sorted(missing)}; a translated phrase would "
                             f"hide the gap instead of naming it")
        except Exception as exc:
            res.note("polyglot", f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:120]}")
        if not seeds:
            for layer, terms in F.MANDATE_SEEDS.items():
                seeds.extend({"country": run.forest, "layer": layer, "query": t,
                              "languages": list(run.spec.languages), "domain": "mandate"}
                             for t in terms)
            used.append("mandate_seeds")
            res.note("native_seeds", f"{UNMEASURED}: no pack and no native vocabulary for "
                                     f"{list(run.spec.languages)}; the scout is working from the "
                                     f"mandate's own terms, which is the floor, not coverage")
        # THE PROPOSER SEAT, OPTIONAL: more NATIVE-SCRIPT search terms for this forest.
        # This is the additive kind, and the rule that makes it safe is in the seat: a term is a
        # SEARCH STRING and never a ground, so anything shaped like a URL, a host or a path is
        # discarded before it gets here and no crawler can be routed by a model naming an
        # address. Everything a term surfaces still enters through `source_frontier` as a
        # CANDIDATE and is fetched by the organ that owns the fetch, which mines it. No panel,
        # no call, and the scout works from exactly the seeds it has today.
        try:
            from libs.research import proposer_seat as _ps
            _reply = _ps.ask(
                "forest_runner", "terms",
                task=(f"Propose additional native-script search terms a {run.spec.name} retail "
                      f"or professional trader would actually type when discussing market "
                      f"mechanics. Native script only -- a translated English phrase reaches the "
                      f"corpus everybody has already read."),
                context=[f"languages: {list(run.spec.languages)}",
                         f"layers: {list(LAYERS)}"],
                n=8)
            for _t in _reply.terms[:8]:
                seeds.append({"country": run.forest, "layer": "all", "query": _t,
                              "languages": list(run.spec.languages), "domain": "proposer_seat"})
            if _reply.terms:
                used.append(f"proposer_seat:{len(_reply.terms)}")
            if _reply.verdict != "RAN":
                res.note("proposer_seat", f"{UNMEASURED}: {_reply.why[:160]}")
        except Exception as _exc:                          # pragma: no cover - optional seat
            res.note("proposer_seat",
                     f"{UNMEASURED}: {type(_exc).__name__}: {str(_exc)[:120]}")

        registered = 0
        try:
            from research import source_frontier as sf
        except Exception:
            sf = None                                              # type: ignore[assignment]
            res.note("source_frontier", f"{UNMEASURED}: source_frontier is not importable here")
        for ground in _grounds(run)[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                break
            sid = f"forest:{run.forest}:{str(ground.get('name') or '')[:80]}"
            if sf is not None and not run.dry_run:
                with contextlib.suppress(Exception):
                    registered += int(bool(sf.register_source(
                        sid, url=str(ground.get("url") or ""), kind=str(ground.get("kind") or ""),
                        language=str(ground.get("language") or ""),
                        country=str(ground.get("region") or ""),
                        discovered_from=f"{GENERATOR}:{run.forest}",
                        discovered_via="forest_source_scout", status="candidate",
                        licence_note="declared ground; MINED by the organ that owns the fetch, "
                                     "with any terms/robots note carried as a routing label "
                                     "(LAWS 5e) rather than as a refusal", conn=conn)))
        by_layer: dict[str, list[str]] = {}
        for s in seeds:
            by_layer.setdefault(str(s.get("layer") or "all"), []).append(str(s.get("query") or ""))
        for layer, queries in list(by_layer.items())[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                res.note("layers", f"budget {budget_s:.0f}s: layers after {layer!r} are owed")
                break
            record(run, res, source_id=f"forest:{run.forest}:{layer}",
                   source_type="source_seed", kind="source_seed",
                   mechanism=f"{run.spec.name} {layer} layer: native search territory "
                             f"({len(queries)} queries in {list(run.spec.languages)})",
                   title=f"{run.forest}:{layer}", text=" | ".join(queries[:24]),
                   condition=f"layer={layer}", conn=conn,
                   payload={"layer": layer, "queries": queries[:24],
                            "languages": list(run.spec.languages), "seeded_by": used[:8]},
                   why="a source layer nobody has mapped is UNMAPPED, which is a third state and "
                       "never a quiet zero")
        if "country_lab" in " ".join(used):
            record_technique(run, res, name="native_query_seeding_from_pack_terminology",
                             source_class="country pack terminology x source layer",
                             procedure="pair each layer's declared roots with the country's own "
                                       "terms, site-scoped, translated only AFTER retrieval",
                             representation="query list per (country, layer, language)", conn=conn)
        res.detail.update({"n_seeds": len(seeds), "n_layers": len(by_layer),
                           "sources_registered": registered, "seeded_by": sorted(set(used))[:12]})
        res.why = (f"{len(seeds)} native seed(s) over {len(by_layer)} layer(s); "
                   f"{registered} ground(s) registered")
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_official_data(run: Run, res: RoleResult, budget_s: float) -> None:
    """Government, exchange and central-bank ground: the country data planes, or the NEED."""
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    planes: list[str] = []
    try:
        for code in run.spec.packs:
            if time.monotonic() > deadline:
                break
            pack = pack_module(code)
            plane = data_plane_module(code)
            if pack is None:
                res.note(f"pack:{code}", f"{UNMEASURED}: {COUNTRIES / code / 'pack.py'} is not "
                                         f"on this box; another builder owns it")
                continue
            if plane is not None and hasattr(plane, "run"):
                planes.append(code)
                try:
                    doc = plane.run(budget_s=max(5.0, (deadline - time.monotonic()) / 2),
                                    no_fetch=True, dry_run=True)
                except Exception as exc:
                    res.note(f"data_plane:{code}",
                             f"{type(exc).__name__}: {str(exc)[:160]}")
                    doc = None
                for lane in (doc or {}).get("lanes", []) if isinstance(doc, dict) else []:
                    if not isinstance(lane, dict):
                        continue
                    for row in lane.get("unmeasured") or []:
                        if isinstance(row, dict):
                            res.note(f"{code}:{row.get('dataset')}",
                                     str(row.get("why") or "")[:240])
                    with run.lock:
                        run.observations.append({"country": code, "lane": lane.get("lane"),
                                                 "series": lane.get("series_written") or [],
                                                 "stored": lane.get("stored"),
                                                 "would_store": lane.get("would_store")})
            for ds in list(_attr(pack, "DATASETS", ()))[:MAX_PER_ROLE]:
                if time.monotonic() > deadline:
                    res.note("datasets", f"budget {budget_s:.0f}s: the rest of {code} is owed")
                    break
                row = dict(ds) if isinstance(ds, Mapping) else {}
                name = str(row.get("name") or "")
                if not name:
                    continue
                record(run, res, source_id=f"{code}:official:{str(row.get('source') or '')[:60]}",
                       source_type="official_dataset", kind="dataset",
                       mechanism=f"{name}: {row.get('coverage') or ''} at "
                                 f"{row.get('frequency') or ''}"[:400],
                       title=name, text=str(row.get("how_to_fetch") or "")[:800],
                       instruments=[str(s) for s in (row.get("assets") or [])],
                       condition=f"lag_days={row.get('publication_lag_days')}",
                       horizon=str(row.get("frequency") or ""), conn=conn,
                       required_data=[name],
                       payload={"pit_feasible": bool(row.get("pit_feasible")),
                                "licence": row.get("licence"), "country": code,
                                "revisions": row.get("revisions"),
                                "has_data_plane": plane is not None},
                       why=("a dataset whose vintage cannot be reconstructed can only ever "
                            "produce NOT_PIT_SAFE cells; that is recorded, not hidden"))
        if not run.spec.packs:
            res.note("official_plane",
                     f"{UNMEASURED}: {run.forest} declares no country pack, so it has no official "
                     f"catalogue on this box; the pack directory that would carry one is "
                     f"{COUNTRIES}")
        res.detail.update({"data_planes": planes, "packs": list(run.spec.packs)})
        res.why = (f"{len(planes)} data plane(s), {res.new} dataset discovery(ies)"
                   if planes or res.new else "no official plane on this box: named, not zero")
    finally:
        run.official_done.set()
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def _region_claims(run: Run, limit: int = MAX_PER_ROLE * 4) -> list[dict[str, Any]]:
    """Deep-forest claims already mined for THIS forest's regions and languages."""
    want_r = {str(c).lower() for c in (*run.spec.grounds, *run.spec.countries)}
    want_l = {str(x).lower() for x in run.spec.languages}
    out: list[dict[str, Any]] = []
    for row in _jsonl_tail(CLAIMS_JSONL):
        region = str(row.get("region") or "").lower()
        lang = str(row.get("language") or row.get("lang") or "").lower()
        if region in want_r or (lang and lang in want_l):
            out.append(row)
        if len(out) >= limit:
            break
    return out


def role_practitioner(run: Run, res: RoleResult, budget_s: float) -> None:
    """Traders, forums, broker research and public communities -- the deep forest's own ground.

    A DUBIOUS TRADER STORY IS STILL A TESTABLE MECHANISM (the principal's standing order), and
    fringe or contradictory material is a CROWDING measurement rather than noise. Nothing is
    dropped here for being unreliable; reliability rides on the row.
    """
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        grounds = [g for g in _grounds(run)
                   if KIND_ROLE.get(str(g.get("kind") or ""), "practitioner") == "practitioner"]
        claims = _region_claims(run)
        if not grounds and not claims:
            res.note("practitioner_ground",
                     f"{UNMEASURED}: no deep-forest ground and no mined claim carries region "
                     f"{sorted(run.spec.grounds)} or language {list(run.spec.languages)}; "
                     f"{GROUNDS_JSON.name} is where a ground is added, never hard-coded here")
        for row in claims[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                res.note("claims", f"budget {budget_s:.0f}s: {len(claims) - res.new} claim(s) owed")
                break
            inst = row.get("instruments") if isinstance(row.get("instruments"), dict) else {}
            syms = [str(s) for s in (inst.get("analogues") or inst.get("indirect") or [])]
            record(run, res, source_id=f"deep_forest:{row.get('ground') or row.get('source')}",
                   source_type="practitioner_claim", kind="story_mechanism",
                   mechanism=str(row.get("mechanism_class") or "")[:200] or "practitioner claim",
                   url=str(row.get("url") or ""), title=str(row.get("title") or "")[:200],
                   text=str(row.get("claim") or ""), instruments=syms,
                   condition=str(row.get("claim") or "")[:400],
                   horizon=" ".join(str(h) for h in (row.get("horizon") or [])), conn=conn,
                   payload={"evidence_grade": row.get("evidence_grade"),
                            "language": row.get("language"), "region": row.get("region"),
                            "published_time": row.get("published_time"),
                            "available_time": row.get("available_time"),
                            "claimed_performance": row.get("claimed_performance")},
                   why="a claim a crowd believes is a crowding feature whether or not it is true")
        for g in grounds[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                break
            record(run, res, source_id=f"forest:{run.forest}:{str(g.get('name') or '')[:80]}",
                   source_type="practitioner_ground", kind="ground",
                   mechanism=f"{g.get('name')}: {str(g.get('why') or '')[:200]}",
                   url=str(g.get("url") or ""), title=str(g.get("name") or ""),
                   text=str(g.get("why") or ""), conn=conn,
                   payload={"route": g.get("route"), "kind": g.get("kind"),
                            "language": g.get("language"), "weight": g.get("weight")},
                   why="the ground is registered here; deep_forest_miner MINES it, carrying any "
                       "terms or robots note as a routing label (LAWS 5e)")
        res.detail.update({"n_grounds": len(grounds), "n_claims": len(claims)})
        res.why = f"{len(claims)} mined claim(s), {len(grounds)} ground(s) for this region"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_academic(run: Run, res: RoleResult, budget_s: float) -> None:
    """Local papers, dissertations and conferences -- through the desk's own knowledge graph."""
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        leads: list[dict[str, Any]] = []
        try:
            from research import knowledge_graph as kg
            leads = [row for row in kg.unconverted_leads(kind="paper", limit=400)
                     if _in_region(run, row)][:MAX_PER_ROLE]
        except Exception as exc:
            res.note("knowledge_graph",
                     f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:140]}; the academic layer "
                     f"of this forest is unread until the graph is readable")
        for row in leads:
            if time.monotonic() > deadline:
                break
            record(run, res, source_id=f"academic:{(row.get('sources') or ['unknown'])[0]}",
                   source_type="academic_lead", kind="paper",
                   mechanism=" ".join(str(m) for m in (row.get("mechanisms") or []))[:400]
                             or "academic claim",
                   title=str(row.get("claim") or "")[:200], text=str(row.get("claim") or ""),
                   instruments=[str(s) for s in (row.get("instruments") or [])], conn=conn,
                   payload={"priority": row.get("priority"), "n_mentions": row.get("n_mentions")},
                   why="an unconverted testable lead is the intake backlog, named not estimated")
        for code in run.spec.packs:
            mod = pack_module(code)
            if mod is None:
                continue
            for row in list(_attr(mod, "SOURCE_CLASSES", ()))[:MAX_PER_ROLE]:
                text = row if isinstance(row, str) else json.dumps(row, default=str,
                                                                   ensure_ascii=False)
                if "academic" not in text.lower():
                    continue
                if time.monotonic() > deadline:
                    break
                record(run, res, source_id=f"{code}:academic", source_type="academic_source",
                       kind="source_seed", mechanism=text[:400], title=f"{code}:academic",
                       text=text, conn=conn,
                       why="the academic layer of this country, from its own pack")
        if not leads and not run.spec.packs:
            res.note("academic_layer",
                     f"{UNMEASURED}: no pack declares an academic layer for {run.forest} and the "
                     f"graph holds no paper lead in {list(run.spec.languages)}")
        res.detail["n_leads"] = len(leads)
        res.why = f"{len(leads)} unconverted paper lead(s) in this forest's languages"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def _in_region(run: Run, row: Mapping[str, Any]) -> bool:
    langs = {str(x).lower() for x in run.spec.languages}
    text = " ".join(str(row.get(k) or "") for k in ("claim", "language", "region", "id")).lower()
    if any(str(c).lower() in text for c in run.spec.grounds):
        return True
    return str(row.get("language") or "").lower() in langs


def role_code(run: Run, res: RoleResult, budget_s: float) -> None:
    """GitHub, Gitee and the local package ecosystems: where the PARAMETERS are the claim."""
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        grounds = [g for g in _grounds(run)
                   if KIND_ROLE.get(str(g.get("kind") or "")) == "code"]
        for g in grounds[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                break
            record(run, res, source_id=f"code:{str(g.get('name') or '')[:80]}",
                   source_type="code_ground", kind="code",
                   mechanism=f"code ecosystem {g.get('name')}: {str(g.get('why') or '')[:200]}",
                   url=str(g.get("url") or ""), title=str(g.get("name") or ""),
                   text=str(g.get("why") or ""), conn=conn,
                   payload={"language": g.get("language"), "route": g.get("route")},
                   why="a repository states its rule in parameters, which is the only form of a "
                       "practitioner claim that needs no interpretation")
        seeded = 0
        for code in run.spec.packs:
            mod = pack_module(code)
            for row in list(_attr(mod, "SOURCE_CLASSES", ()))[:MAX_PER_ROLE]:
                text = row if isinstance(row, str) else json.dumps(row, default=str,
                                                                   ensure_ascii=False)
                if "app_ecosystem" not in text.lower() and "code" not in text.lower():
                    continue
                if time.monotonic() > deadline:
                    break
                seeded += 1
                record(run, res, source_id=f"{code}:code", source_type="code_source",
                       kind="source_seed", mechanism=text[:400], title=f"{code}:code", text=text,
                       conn=conn, why="the local package ecosystem this country actually uses")
        if not grounds and not seeded:
            res.note("code_layer",
                     f"{UNMEASURED}: no code ground for regions {sorted(run.spec.grounds)} in "
                     f"{GROUNDS_JSON.name} and no pack declares an app_ecosystem layer")
        res.detail.update({"n_code_grounds": len(grounds), "n_pack_code_sources": seeded})
        res.why = f"{len(grounds)} code ground(s), {seeded} pack-declared code source(s)"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_archive(run: Run, res: RoleResult, budget_s: float) -> None:
    """Old forums, vanished strategies, historical pages -- and the NAMED ABSENCES between them.

    The absences are the product. A coverage table with holes reads as completeness to anybody
    who skims; a table where every hole says which ground is missing can be worked down.
    """
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        cells: list[dict[str, Any]] = []
        try:
            from research.archaeology import snapshots as snap
            regions = {str(c).lower() for c in (*run.spec.grounds, *run.spec.countries)}
            layer = snap.archive_layer()
            cells = [c for c in layer.get("cells", [])
                     if str(c.get("region") or "").lower() in regions]
        except Exception as exc:
            res.note("archaeology",
                     f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:140]}; the archive layer of "
                     f"this forest is unmapped until archaeology is importable")
        for cell in cells[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                break
            state = str(cell.get("state") or "")
            if state != "GROUND":
                res.note(f"archive:{cell.get('region')}:{cell.get('archive_kind')}",
                         str(cell.get("note") or "named absence"))
                continue
            record(run, res, source_id=f"archive:{cell.get('name')}", source_type="archive_ground",
                   kind="archive",
                   mechanism=f"archive ground {cell.get('name')} "
                             f"({cell.get('archive_kind')}): {str(cell.get('note') or '')[:200]}",
                   url=str(cell.get("url") or ""), title=str(cell.get("name") or ""),
                   text=str(cell.get("note") or ""), conn=conn,
                   payload={"access_label": cell.get("access_label"),
                            "credibility": cell.get("credibility"),
                            "terms_note": cell.get("terms_note") or cell.get("note"),
                            "archive_kind": cell.get("archive_kind")},
                   why="a ground whose terms are unread is MINED with the unread-terms label "
                       "attached (LAWS 5e): the quarantine was deleted on 2026-09-23")
        if not cells:
            res.note("archive_cells",
                     f"{UNMEASURED}: the archive layer names no region x kind cell for "
                     f"{sorted(run.spec.grounds)}; the cell is owed, not empty")
        res.detail.update({"n_cells": len(cells),
                           "n_absences": sum(1 for c in cells if c.get("state") != "GROUND")})
        res.why = f"{len(cells)} archive cell(s) for this region"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_failure_miners(run: Run, res: RoleResult, budget_s: float) -> None:
    """Strategies that stopped working, and WHY -- this region's dead cells, classified.

    Negative knowledge is the cheapest evidence the desk owns: a mechanism that died of
    `cost_killed` on this region's instruments is a different finding from one that died of
    `no_edge`, and only the first one is worth a second expression.
    """
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        syms, missing = _instruments(run)
        for m in missing:
            res.note(m["what"], m["why"])
        if not syms:
            res.note("dead_population",
                     f"{UNMEASURED}: this forest names no instrument on this box, so its dead "
                     f"population cannot be separated from every other forest's")
            res.why = "no instrument to attribute a death to: UNMEASURED, not zero"
            return
        want = {s.upper() for s in syms}
        try:
            from research import graveyard_resurrection as gr
        except Exception as exc:
            res.note("graveyard_resurrection", f"{UNMEASURED}: {type(exc).__name__}: "
                                               f"{str(exc)[:140]}")
            res.why = "the graveyard is unreadable on this box"
            return
        try:
            dead = [d for d in gr.dead_cells(gr.read_graph(limit=20000), limit=20000)
                    if str(d.symbol).upper() in want]
        except Exception as exc:
            res.note("dead_cells", f"{type(exc).__name__}: {str(exc)[:160]}")
            dead = []
        classes: dict[str, int] = {}
        for d in dead[:MAX_PER_ROLE * 4]:
            if time.monotonic() > deadline:
                res.note("classify", f"budget {budget_s:.0f}s: the rest of the dead are owed")
                break
            try:
                cls = gr.classify_failure(d.terminal_gate, d.evidence)
            except Exception:
                cls = UNMEASURED
            classes[cls] = classes.get(cls, 0) + 1
        for cls, n in sorted(classes.items(), key=lambda kv: -kv[1])[:12]:
            record(run, res, source_id=f"forest:{run.forest}:graveyard",
                   source_type="failure_cluster", kind="failure",
                   mechanism=f"{run.spec.name}: {n} dead cell(s) classified {cls}",
                   title=f"{run.forest}:{cls}", text=f"failure class {cls} over {n} dead cells "
                                                     f"on {sorted(want)[:12]}",
                   instruments=sorted(want)[:12], condition=f"failure_class={cls}", conn=conn,
                   payload={"failure_class": cls, "n": n, "symbols": sorted(want)[:24]},
                   why="a repair is only worth building for a death whose cause was diagnosed")
        res.detail.update({"n_dead": len(dead), "by_failure_class": classes,
                           "n_instruments": len(want)})
        res.why = f"{len(dead)} dead cell(s) on this forest's instruments, {len(classes)} class(es)"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_mechanism_extractors(run: Run, res: RoleResult, budget_s: float) -> None:
    """Material -> economic hypotheses: the twelve transformation miners on this forest's rows."""
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        try:
            from research import discovery_compiler as dcomp
            from research import transformation_miners as tm
        except Exception as exc:
            res.note("transformation_miners",
                     f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:140]}")
            res.why = "the mechanism miners are not importable on this box"
            return
        try:
            ctx = dcomp.build_context(max_per_miner=3)
        except Exception as exc:
            res.note("context", f"{type(exc).__name__}: {str(exc)[:140]}")
            res.why = "no miner context on this box"
            return
        syms, missing = _instruments(run)
        for m in missing:
            res.note(m["what"], m["why"])
        parents: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        if not run.dry_run:
            with contextlib.suppress(Exception):
                rows = reg.discoveries(state="UNPROCESSED", origin="EXTERNAL", limit=400,
                                       conn=conn)
        for row in rows:
            gen = str(row.get("generator") or "")
            if f":{run.forest}:" not in gen:
                continue
            assets = row.get("assets_json")
            with contextlib.suppress(Exception):
                assets = json.loads(assets) if isinstance(assets, str) else assets
            sym = str((assets or [""])[0] if isinstance(assets, list) else "").upper()
            if not sym and syms:
                sym = syms[0]
            if not sym:
                continue
            parents.append({"discovery_id": str(row.get("discovery_id")), "symbol": sym,
                            "assets": [sym], "family": "", "params": {},
                            "chart": "H1", "session": "all", "regime": "unconditional",
                            "information": "price_only",
                            "mechanism_id": str(row.get("mechanism") or "")[:60],
                            "why": str(row.get("mechanism") or "")[:200]})
            if len(parents) >= 12:
                break
        if not parents:
            res.note("parents", f"{UNMEASURED}: this forest has recorded no UNPROCESSED "
                                f"discovery naming an instrument yet; the extractor has nothing "
                                f"to transform, which is a measurement of the intake, not of the "
                                f"miners")
        made = 0
        for parent in parents:
            if time.monotonic() > deadline:
                res.note("miners", f"budget {budget_s:.0f}s: {len(parents) - made} parent(s) owed")
                break
            try:
                closure = tm.run_all(parent, ctx)
            except Exception as exc:
                res.note("run_all", f"{type(exc).__name__}: {str(exc)[:140]}")
                continue
            made += 1
            for miner, children in closure.items():
                for child in children[:3]:
                    did = record(
                        run, res, source_id=f"forest:{run.forest}:mechanism",
                        source_type="mechanism", kind="mechanism",
                        mechanism=f"{parent['mechanism_id']} via {miner}: "
                                  f"{str(child.get('why') or '')[:200]}",
                        title=f"{child.get('symbol')}:{miner}",
                        text=str(child.get("why") or ""),
                        instruments=[str(child.get("symbol") or "")],
                        family=str(child.get("family") or ""),
                        condition=f"{miner}:{child.get('axis')}",
                        horizon=str(child.get("chart") or ""),
                        parents=[parent["discovery_id"]], conn=conn,
                        payload={"transformation": miner, "axis": child.get("axis"),
                                 "session": child.get("session"), "regime": child.get("regime")},
                        why="a transformation of a parent is a DESCENDANT, tested on its own")
                    with run.lock:
                        run.mechanisms.append({"discovery_id": did, "miner": miner,
                                               "symbol": str(child.get("symbol") or ""),
                                               "family": str(child.get("family") or ""),
                                               "params": dict(child.get("params") or {}),
                                               "chart": str(child.get("chart") or ""),
                                               "why": str(child.get("why") or "")[:200]})
        if made:
            record_technique(run, res, name="closure_expansion_of_a_regional_claim",
                             source_class="one regional discovery x the twelve transformations",
                             procedure="expand every admitted regional claim across asset, "
                                       "horizon, session, regime, residual, inverse and "
                                       "cross-asset axes before testing any of them",
                             representation="child specs with a named axis and a named parent",
                             conn=conn)
        res.detail.update({"n_parents": len(parents), "n_expanded": made,
                           "n_children": len(run.mechanisms)})
        res.why = f"{made} parent(s) expanded into {len(run.mechanisms)} child spec(s)"
    finally:
        run.mechanisms_done.set()
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def _pit_point(value: float, period: str, publication: str, available: str,
               vintage: str, revision: str | None = None) -> dict[str, Any]:
    """One PIT-safe observation, with all six stamps. `revision_time` is None for a first print,
    which is a fact about the series, never a missing field."""
    return {"value": float(value), "period_time": period, "publication_time": publication,
            "available_time": available, "revision_time": revision, "vintage_id": vintage}


def role_data_agents(run: Run, res: RoleResult, budget_s: float) -> None:
    """Raw sources -> PIT-safe structured series under `data/axes/`.

    IT WAITS FOR THE OFFICIAL LANE, BOUNDED, AND NEVER BLOCKS THE PASS. The other nine roles run
    regardless; this one needs what the official agents read, so it waits at most a share of its
    own budget and then reports what it got. A series it cannot build is UNMEASURED naming the
    dataset that would build it -- it never writes an invented number into an axis.
    """
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        run.official_done.wait(timeout=max(1.0, budget_s * DEPENDENCY_WAIT_SHARE))
        with run.lock:
            obs = list(run.observations)
        if not obs:
            res.note("series", f"{UNMEASURED}: the official-data agents produced no observation "
                               f"this pass, so there is nothing to stamp; the datasets they "
                               f"named are this forest's data debt")
            res.why = "no observation to stamp: UNMEASURED, not an empty series"
            return
        stamp = now()
        written: list[str] = []
        for row in obs[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                res.note("write", f"budget {budget_s:.0f}s: the rest of the series are owed")
                break
            names = [str(s) for s in (row.get("series") or [])]
            if not names:
                res.note(f"lane:{row.get('country')}:{row.get('lane')}",
                         f"{UNMEASURED}: the lane read no payload this pass (no-fetch mode reads "
                         f"fixtures); its catalogue is recorded and its series are owed")
                continue
            for name in names[:12]:
                sid = f"forest_{run.forest}_{row.get('country')}_{row.get('lane')}_{name}"
                path = AXES / f"{sid}.json"
                doc = {"axis": "forest_state", "id": sid, "forest": run.forest,
                       "country": row.get("country"), "lane": row.get("lane"),
                       "series_name": name, "at": stamp,
                       "pit_fields": ["value", "period_time", "publication_time",
                                      "available_time", "revision_time", "vintage_id"],
                       "shape": "points[] -- one observation per (period, vintage)",
                       "vintage_note": ("APPEND-ONLY. A flash and its final are two observations "
                                        "of one period; the reader asks what was knowable at an "
                                        "instant, never what is true now."),
                       "source": f"{row.get('country')}:{row.get('lane')}",
                       "points": []}
                existing = _read_json(path)
                if isinstance(existing, dict) and isinstance(existing.get("points"), list):
                    doc["points"] = existing["points"]
                doc["n"] = len(doc["points"])
                if not run.dry_run:
                    _atomic(path, doc)
                written.append(sid)
                record(run, res, source_id=f"{row.get('country')}:{row.get('lane')}",
                       source_type="pit_series", kind="series",
                       mechanism=f"PIT series {sid}: the lane's own observations, stamped with "
                                 f"period/publication/available/revision/vintage",
                       title=sid, text=f"axis series {name} from "
                                       f"{row.get('country')}:{row.get('lane')}",
                       condition=f"series={name}", conn=conn,
                       required_data=[name],
                       payload={"axis_file": str(path), "country": row.get("country"),
                                "lane": row.get("lane"), "series": name},
                       why="every series carries the six PIT stamps or it is not admitted")
        res.detail.update({"n_observations": len(obs), "series_written": written[:24],
                           "n_series": len(written)})
        res.why = f"{len(written)} PIT-stamped series from {len(obs)} lane reading(s)"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_candidate_compilers(run: Run, res: RoleResult, budget_s: float) -> None:
    """Mechanisms -> implementation-ready hypothesis cards, donated through the desk's own door.

    It donates through `proposer_common.donate`, which is the ONE intake that stamps a candidate
    point-in-time, refuses an unstamped row, refuses a single-name equity under the two-lane
    order and records the candidate in the canonical registry. Compiling a second way would mean
    a second set of those fences, which is how a fence stops being one.
    """
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        run.mechanisms_done.wait(timeout=max(1.0, budget_s * DEPENDENCY_WAIT_SHARE))
        with run.lock:
            children = list(run.mechanisms)
        runnable = [c for c in children if c.get("family") and c.get("symbol")]
        if not runnable:
            res.note("candidates",
                     f"{UNMEASURED}: {len(children)} mechanism child(ren) and none names both a "
                     f"family and a symbol, so none is executable yet; the gap is the compiler's "
                     f"debt, not an empty forest")
            res.why = "no executable child this pass"
            return
        try:
            from research import proposer_common as pc
        except Exception as exc:
            res.note("proposer_common", f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:140]}")
            res.why = "the donation door is not importable on this box"
            return
        cands: list[dict[str, Any]] = []
        for c in runnable[:MAX_PER_ROLE]:
            if time.monotonic() > deadline:
                res.note("compile", f"budget {budget_s:.0f}s: the rest of the children are owed")
                break
            cands.append(pc.candidate(
                source=f"forest_{run.forest}", symbol=str(c["symbol"]), family=str(c["family"]),
                params=dict(c.get("params") or {}),
                mechanism=str(c.get("why") or "")[:200],
                title=f"{run.spec.name} {c.get('miner')} {c.get('symbol')}",
                evidence={"forest": run.forest, "transformation": c.get("miner"),
                          "discovery_id": c.get("discovery_id"), "chart": c.get("chart")}))
        path = None
        if cands and not run.dry_run:
            with contextlib.suppress(Exception):
                path = pc.donate(f"forest_{run.forest}", cands, len(children))
        counts: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            counts = pc.donation_counts()
        res.detail.update({"n_children": len(children), "n_executable": len(runnable),
                           "n_donated": int(counts.get("donated") or 0),
                           "refused_unstamped": int(counts.get("refused_unstamped") or 0),
                           "refused_wrong_lane": int(counts.get("refused_wrong_lane") or 0),
                           "contract": str(path) if path else None})
        for row in (counts.get("lane_refusals") or [])[:6]:
            if isinstance(row, Mapping):
                res.note(f"lane:{row.get('symbol')}", str(row.get("why") or "")[:240])
        res.why = (f"{len(cands)} candidate(s) offered, "
                   f"{int(counts.get('donated') or 0)} admitted at the intake door")
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def role_source_roi(run: Run, res: RoleResult, budget_s: float) -> None:
    """Which of THIS region's ecosystems actually produce survivors -- from the registry, not
    from a feeling. A source with no measurement is UNMEASURED and keeps its floor; a source
    with a measured zero is a finding."""
    deadline = time.monotonic() + budget_s
    conn = run.conn()
    try:
        try:
            from research import source_frontier as sf
        except Exception as exc:
            res.note("source_frontier", f"{UNMEASURED}: {type(exc).__name__}: {str(exc)[:140]}")
            res.why = "no ROI table on this box"
            return
        want = {str(c).lower() for c in (*run.spec.grounds, *run.spec.countries)}
        rows: list[dict[str, Any]] = []
        try:
            known = sf.sources(conn=conn) if not run.dry_run else {}
            for sid, row in known.items():
                if time.monotonic() > deadline:
                    break
                country = str(row.get("country") or "").lower()
                language = str(row.get("language") or "").lower()
                if country not in want and language not in {x.lower()
                                                            for x in run.spec.languages} \
                        and f"forest:{run.forest}" not in str(sid):
                    continue
                with contextlib.suppress(Exception):
                    rows.append(sf.source_roi(str(sid), conn=conn))
        except Exception as exc:
            res.note("roi", f"{type(exc).__name__}: {str(exc)[:160]}")
        measured = [r for r in rows if r.get("measured")]
        rows.sort(key=lambda r: -float(r.get("roi_score") or 0.0))
        payload = {"forest": run.forest, "at": now(), "n_sources": len(rows),
                   "n_measured": len(measured),
                   "top": [{k: r.get(k) for k in ("source_id", "roi_score", "leads", "judged")}
                           for r in rows[:20]],
                   "rule": ("novel and testable per LEAD, survival per JUDGED cell; a source "
                            "with no measurement keeps its exploration floor rather than being "
                            "defunded for never having been tried")}
        if not rows:
            res.note("source_yield",
                     f"{UNMEASURED}: no source in the registry carries this forest's country or "
                     f"language yet; its ecosystems have produced nothing to price, which is a "
                     f"measurement of the scouts' age, not of the region")
        if not run.dry_run:
            with contextlib.suppress(Exception):
                reg.remember("forest_source_roi", json.dumps(payload["top"], default=str)[:2000],
                             kind="source_roi", memory_key=f"forest_source_roi:{run.forest}",
                             payload=payload, conn=conn)
        res.detail.update({"n_sources": len(rows), "n_measured": len(measured),
                           "top": payload["top"][:10]})
        res.why = f"{len(measured)} measured of {len(rows)} source(s) in this forest"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


RoleFn = Callable[[Run, RoleResult, float], None]
ROLE_FUNCS: dict[str, RoleFn] = {
    "source_scouts": role_source_scouts,
    "official_data": role_official_data,
    "practitioner": role_practitioner,
    "academic": role_academic,
    "code": role_code,
    "archive": role_archive,
    "failure_miners": role_failure_miners,
    "mechanism_extractors": role_mechanism_extractors,
    "data_agents": role_data_agents,
    "candidate_compilers": role_candidate_compilers,
    "source_roi": role_source_roi,
}


# --------------------------------------------------------------------------- the pass
def _seed_view(run: Run) -> int:
    """Seed the dedup view from the registry, so a mechanism ANOTHER forest already recorded is
    recognised as a duplicate rather than minted again. This is where the federation stops being
    seventeen private notebooks."""
    if run.dry_run:
        return 0
    try:
        rows = reg.discoveries(limit=VIEW_SEED_ROWS)
    except Exception:
        return 0
    view = dc.RegistryView.from_rows(
        {"discovery_id": r.get("discovery_id"), "mechanism": r.get("mechanism"),
         "exact_rule": r.get("exact_rule"), "assets": _loads(r.get("assets_json")),
         "source_id": r.get("source_id"), "title": r.get("economic_rationale")}
        for r in rows)
    with run.lock:
        run.view = view
    return len(view)


def _loads(raw: Any) -> Any:
    if isinstance(raw, str):
        with contextlib.suppress(ValueError):
            return json.loads(raw)
    return raw


def _heartbeat(run: Run, status: str, note: str = "") -> None:
    if run.dry_run:
        return
    with contextlib.suppress(Exception):
        reg.worker_heartbeat(f"forest:{run.forest}", kind="forest_runner",
                             department=run.spec.department, status=status,
                             beat=note or run.forest, generator=GENERATOR, pid=os.getpid())


def run_pass(forest_id: str, *, budget_s: float | None = None, workers: int | None = None,
             dry_run: bool = False, allocation: F.Allocation | None = None,
             roles: Iterable[str] | None = None) -> dict[str, Any]:
    """One full pass of one forest: all eleven roles, in parallel, each isolated.

    A ROLE THAT RAISES COSTS THE OTHER TEN NOTHING. Every role body is wrapped here, its failure
    is recorded as that role's result with the exception named, and the pool keeps going -- the
    fifty-five-leg lesson applied to eleven agents: a civilization whose reliability is the
    product of eleven things all going right is not a civilization.
    """
    spec = F.forest(forest_id)
    alloc = allocation or F.allocation_for(spec.id)
    if budget_s is not None:
        alloc = F.Allocation(**{**alloc.__dict__, "budget_s": int(max(1.0, budget_s))})
    if workers is not None:
        alloc = F.Allocation(**{**alloc.__dict__, "workers": max(1, int(workers))})
    run = Run(forest=spec.id, allocation=alloc, dry_run=bool(dry_run))
    seeded = _seed_view(run)
    _heartbeat(run, "running", f"pass start ({alloc.workers} worker(s))")
    plan = [(r, s) for r, s in F.role_plan(spec.id, alloc)
            if roles is None or r in set(roles)]
    if F.SCOUT_ROLE not in {r for r, _ in plan}:
        plan.insert(0, (F.SCOUT_ROLE, F.MIN_ROLE_S))     # the floor is a law, not a knob

    def _one(role: str, slice_s: float) -> RoleResult:
        res = RoleResult(role=role)
        started = time.monotonic()
        fn = ROLE_FUNCS.get(role)
        if fn is None:
            res.why = f"{UNMEASURED}: no agent is wired for role {role!r}"
            res.note("agent", res.why)
            return res
        try:
            fn(run, res, slice_s)
            res.ran = True
        except Exception as exc:
            res.ran = False
            res.why = f"ROLE FAILED {type(exc).__name__}: {str(exc)[:200]}"
            res.note("role", res.why)
        finally:
            res.seconds = time.monotonic() - started
            if role == "official_data":
                run.official_done.set()
            if role == "mechanism_extractors":
                run.mechanisms_done.set()
        return res

    with ThreadPoolExecutor(max_workers=max(1, alloc.workers),
                            thread_name_prefix=f"forest-{spec.id}") as pool:
        futures = {pool.submit(_one, role, slice_s): role for role, slice_s in plan}
        for fut in futures:
            role = futures[fut]
            try:
                run.results[role] = fut.result()
            except Exception as exc:                        # pragma: no cover -- belt and braces
                res = RoleResult(role=role, ran=False,
                                 why=f"ROLE FAILED {type(exc).__name__}: {str(exc)[:200]}")
                res.note("role", res.why)
                run.results[role] = res
    doc = _report(run, seeded, plan)
    if not dry_run:
        _atomic(REPORTS / spec.report_name, doc)
        _append_run(doc)
    _heartbeat(run, "running", "pass done")
    return doc


def _report(run: Run, seeded: int, plan: Sequence[tuple[str, float]]) -> dict[str, Any]:
    spec = run.spec
    rows = [run.results[r].as_row() for r, _s in plan if r in run.results]
    unmeasured = [{"role": r["role"], **u} for r in rows for u in r.get("unmeasured") or []]
    return {
        "at": now(), "forest": spec.id, "name": spec.name, "kind": spec.kind,
        "task": spec.task, "department": spec.department, "leg": spec.leg,
        "countries": list(spec.countries), "languages": list(spec.languages),
        "packs": list(spec.packs), "package": spec.package,
        "seconds": round(run.elapsed(), 2), "dry_run": run.dry_run,
        "allocation": run.allocation.as_row(),
        "plan": [{"role": r, "budget_s": s} for r, s in plan],
        "roles": rows,
        "n_roles_ran": sum(1 for r in rows if r["ran"]),
        "n_roles_failed": sum(1 for r in rows if not r["ran"]),
        "totals": {"new": sum(r["new"] for r in rows),
                   "duplicates": sum(r["duplicates"] for r in rows),
                   "descendants": sum(r["descendants"] for r in rows),
                   "provenance_edges": run.edges, "techniques": len(run.techniques),
                   "sources": len(run.sources_seen)},
        "dedup": dc.census(run.verdicts) | {"view_seeded_from_registry": seeded},
        "techniques": run.techniques[:24],
        "unmeasured": unmeasured,
        "unmeasured_packs": F.unmeasured_packs(spec.id),
        "boundary": ("this organ opens no socket: every fetch belongs to the organ that owns it, "
                     "every registered ground is MINED with its terms/robots note carried as a "
                     "routing label (LAWS 5e, 2026-09-23), the only refusals are the five acts "
                     "of access_classifier.HARD_BOUNDARY, and no secret is read or printed here"),
        "rule": ("eleven agents in parallel, every write through the dedup chain first, one "
                 "registry; a role with no ground reports UNMEASURED by name and the forest is "
                 "never idle"),
    }


def _append_run(doc: Mapping[str, Any]) -> None:
    row = {"at": doc.get("at"), "forest": doc.get("forest"), "seconds": doc.get("seconds"),
           "allocation": doc.get("allocation"), "totals": doc.get("totals"),
           "n_roles_ran": doc.get("n_roles_ran"), "n_roles_failed": doc.get("n_roles_failed"),
           "n_unmeasured": len(doc.get("unmeasured") or [])}
    RUNS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")


def summary(doc: Mapping[str, Any]) -> list[str]:
    t = doc.get("totals") or {}
    out = [f"forest {doc.get('forest')} ({doc.get('name')}): {doc.get('n_roles_ran')}/"
           f"{len(doc.get('roles') or [])} role(s) ran in {doc.get('seconds')}s -- "
           f"new {t.get('new')}, duplicates {t.get('duplicates')}, "
           f"descendants {t.get('descendants')}, edges {t.get('provenance_edges')}"]
    for row in doc.get("roles") or []:
        mark = "ok " if row.get("ran") else "FAIL"
        out.append(f"  {mark} {row['role']:<22} {row['seconds']:>6.1f}s  "
                   f"new={row['new']:<4} dup={row['duplicates']:<4} "
                   f"desc={row['descendants']:<4} {str(row.get('why') or '')[:70]}")
    for row in (doc.get("unmeasured") or [])[:6]:
        out.append(f"  UNMEASURED {row.get('role')}/{row.get('what')}: "
                   f"{str(row.get('why') or '')[:90]}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").splitlines()[0])
    ap.add_argument("--forest", help="forest id (see --list)")
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="measure and write nothing")
    ap.add_argument("--role", action="append", help="run only these roles (repeatable)")
    ap.add_argument("--list", action="store_true", help="print the federation and exit")
    a = ap.parse_args(argv)
    if a.list or not a.forest:
        print(json.dumps(F.census(), indent=1, ensure_ascii=False))
        return 0 if a.list else 2
    fid = str(a.forest).strip().lower()
    if fid not in F.FORESTS:
        print(f"unknown forest {fid!r}; known: {sorted(F.FORESTS)}")
        return 2
    doc = run_pass(fid, budget_s=a.budget_s, workers=a.workers, dry_run=a.dry_run,
                   roles=a.role or None)
    for line in summary(doc):
        print(line, flush=True)
    if not a.once:
        print("note: --once is the only mode this organ has; the RESIDENT loop is the box task "
              f"{doc.get('task')}, which restarts it", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
