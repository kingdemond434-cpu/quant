"""THE DATASET CENSUS: every dataset the desk holds, the three uses it has, and which feed NOTHING.

THE PRINCIPAL, 2026-09-30: every alt, macro or intelligence dataset must feed three uses -- (a)
DIRECT cells through families of its own, (b) INDIRECT cells through conditioning and interactions
on existing families, (c) ALLOCATION state the allocator may read -- and a dataset that feeds no
producer is a defect to wire first. A LIBRARY, not a leg: `producer_breadth` calls `census()` and
publishes it as PRODUCER_BREADTH.json["datasets"], which the daily CRO duty (D14) reads, and
`producer_swarm` reads that section back to visit the unfed datasets' conditioned producers first.

WHAT IS A DATASET HERE, by kind (every one discovered from disk, none listed in this file):
    lake:<pack>     data/lake/series/<pack>.*, plus every pack REGISTERED in asia_sources.json
                    that has no series file yet (listed with that reason: it cannot feed anything)
    cot:<relpath>   the CFTC positioning files, data/cot*.parquet and data/cot*/*.parquet
    intel:<seat>    each seat directory under either data/intelligence root
    macro:<name>    the macro axis records, data/axes/*.json
    grounds:<name>  the grounds files miners walk, data/*sources*.json|jsonl and data/*grounds*

THE THREE USES, and how each is measured -- a count where one exists, a named organ where not:
    direct      registry cells in 7d whose source_id is the dataset (or a source name its own rows
                carry), the compiler's last per-source candidates for it, and the organs whose
                source text reads it (producers and families that turn it into a stance);
    indirect    registry cells in 7d of `dataset_conditioned` naming it, and the conditioning
                families that read it (a family whose name says it conditions);
    allocation  the state organs whose source text reads it (research/*state*, macro_*,
                regime*, libs/portfolio/*). A static wiring fact, labelled as one: a reference is
                not a measured read, and it is never counted as a cell.

A dataset FEEDS NO PRODUCER when no direct or indirect cell was minted from it in 7d. The registry
unreadable AND no compiler record = UNMEASURED, never "unfed" and never "fed" (L1.28a).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
UNMEASURED = "UNMEASURED"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"
COMPILED = DATA / "hypotheses" / "miner_candidates.json"
ASIA_SOURCES = DATA / "asia_sources.json"
SWARM_REGISTRY = DATA / "producer_swarm_registry.json"
#: Readings a series needs before `family_dataset_conditioned` will condition on it.
MIN_OBSERVATIONS = 30
#: Newest snapshot files sampled to learn an intelligence dataset's numeric fields.
FIELD_SAMPLE_FILES = 3
FIELD_SAMPLE_ROWS = 400
#: Distinct `symbol` values an intelligence field is split into, most frequent first.
MAX_MATCHES = 12
CONDITIONED_FAMILY = "dataset_conditioned"
#: History a series needs before conditioning on it is worth a trial; below it the dataset is
#: ACCUMULATING (read from the swarm registry's dataset_conditioning.min_span_days when present).
MIN_SPAN_DAYS = 28
#: Files that name datasets without reading them: this census, the declaration table.
NOT_READERS = frozenset({Path(__file__).resolve(),
                         (DESK / "mt5desk" / "family_inputs.py").resolve()})
STAMP_COLUMNS = frozenset({"event_time", "published_time", "available_time", "revision_time",
                           "retrieval_time", "ingested_time", "source_id", "vintage_id",
                           "report_date"})


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _iso(t: Any) -> str | None:
    try:
        return t.isoformat(timespec="seconds") if t is not None else None
    except (AttributeError, TypeError):
        return None


# ------------------------------------------------------------------ culture tags
def cultures(reg: dict[str, Any] | None = None) -> tuple[dict[str, str], list[str]]:
    """(seat/dataset name -> culture tag, the culture tags the swarm registry declares)."""
    reg = reg if reg is not None else (_read(SWARM_REGISTRY, {}) or {})
    named = {str(k): str(v) for k, v in (reg.get("dataset_cultures") or {}).items()
             if not str(k).startswith("_")}
    tags = [str(k) for k in (reg.get("cultures") or {}) if not str(k).startswith("_")]
    return named, tags


def culture_of(name: str, named: dict[str, str], tags: list[str]) -> str:
    """A dataset's culture from the registry's table, else a `_xx` suffix naming a declared tag."""
    if name in named:
        return named[name]
    tail = name.rsplit("_", 1)[-1].upper() if "_" in name else ""
    return tail if tail in tags else UNMEASURED


# ------------------------------------------------------------------ discovery
def _numeric_cols(df: Any) -> list[str]:
    cols = [str(c) for c in df.columns if str(c) not in STAMP_COLUMNS
            and not str(c).startswith("_")]
    out = []
    for c in cols:
        try:
            if str(df[c].dtype) != "bool" and df[c].dtype.kind in "iuf":
                out.append(c)
        except (AttributeError, KeyError):
            continue
    return out


def _series_facts(s: Any) -> dict[str, Any]:
    if s is None or len(s) == 0:
        return {"points": 0, "first": None, "last": None, "span_days": 0}
    return {"points": len(s), "first": _iso(s.index[0]), "last": _iso(s.index[-1]),
            "span_days": round((s.index[-1] - s.index[0]).total_seconds() / 86400, 1)}


def _min_span() -> float:
    reg = _read(SWARM_REGISTRY, {}) or {}
    try:
        return float((reg.get("dataset_conditioning") or {}).get("min_span_days", MIN_SPAN_DAYS))
    except (TypeError, ValueError):
        return float(MIN_SPAN_DAYS)


def _pit(usable: bool, why: str, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """The usable verdict. A series shorter than the minimum span is ACCUMULATING: stamped and
    growing, and not yet worth a trial that would raise every other cell's multiplicity bar."""
    facts = dict(facts or {})
    span = facts.get("span_days")
    need = _min_span()
    if usable and isinstance(span, (int, float)) and span < need:
        usable, why = False, (f"ACCUMULATING: {span} day(s) of stamped history, under "
                              f"{need:g}; it becomes conditionable as its miner keeps writing")
    return {"usable": bool(usable), "why": why, **facts}


def lake_datasets(series_dir: Path | None = None) -> list[dict[str, Any]]:
    import pandas as pd
    from mt5desk import dataset_series as DS
    base = series_dir or (DATA / "lake" / "series")
    reg = _read(ASIA_SOURCES, {}) or {}
    registered = {str(r.get("id")): r for r in (reg.get("sources") or [])
                  if isinstance(r, dict) and r.get("id")}
    out: list[dict[str, Any]] = []
    on_disk: set[str] = set()
    for p in sorted(base.glob("*")) if base.is_dir() else []:
        if p.suffix not in (".parquet", ".csv"):
            continue
        pack = p.stem
        on_disk.add(pack)
        try:
            df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
        except Exception as exc:
            out.append({"id": f"lake:{pack}", "kind": "lake", "path": str(p.relative_to(ROOT)),
                        "fields": [], "country": (registered.get(pack) or {}).get("country"),
                        "pit": _pit(False, f"unreadable ({type(exc).__name__})")})
            continue
        fields = [{"field": f, "match": ""} for f in _numeric_cols(df)]
        stamped = "available_time" in df.columns
        facts = {"points": len(df)}
        if stamped and fields:
            facts = _series_facts(DS.raw(f"lake:{pack}", fields[0]["field"], root=base))
        usable = stamped and bool(fields) and facts.get("points", 0) >= MIN_OBSERVATIONS
        why = ("" if usable else "no available_time stamp: no honest join" if not stamped
               else "no numeric column" if not fields
               else f"{facts.get('points', 0)} reading(s), under {MIN_OBSERVATIONS}")
        out.append({"id": f"lake:{pack}", "kind": "lake", "path": str(p.relative_to(ROOT)),
                    "fields": fields, "country": (registered.get(pack) or {}).get("country"),
                    "source_names": [pack], "pit": _pit(usable, why, facts)})
    for pack, r in sorted(registered.items()):
        if pack in on_disk:
            continue
        out.append({"id": f"lake:{pack}", "kind": "lake", "path": None, "fields": [],
                    "country": r.get("country"), "source_names": [pack],
                    "pit": _pit(False, "registered in asia_sources.json; no series file has "
                                       "been collected into data/lake/series")})
    return out


def cot_datasets(data: Path | None = None) -> list[dict[str, Any]]:
    import pandas as pd
    from mt5desk import dataset_series as DS
    base = data or DATA
    paths = sorted(set(base.glob("cot*.parquet")) | set(base.glob("cot*/*.parquet")))
    out: list[dict[str, Any]] = []
    for p in paths:
        rel = str(p.relative_to(base).with_suffix("")).replace("\\", "/")
        try:
            df = pd.read_parquet(p)
        except Exception as exc:
            out.append({"id": f"cot:{rel}", "kind": "cot", "path": str(p.relative_to(ROOT)),
                        "fields": [], "pit": _pit(False, f"unreadable ({type(exc).__name__})")})
            continue
        cols = _numeric_cols(df)
        fields = [{"field": f, "match": ""} for f in DS.pair_fields(cols) + cols]
        if "report_date" not in df.columns or not fields:
            out.append({"id": f"cot:{rel}", "kind": "cot", "path": str(p.relative_to(ROOT)),
                        "fields": fields, "pit": _pit(False, "no report_date or no numeric "
                                                             "column")})
            continue
        facts = _series_facts(DS.raw(f"cot:{rel}", fields[0]["field"], root=base))
        usable = facts["points"] >= MIN_OBSERVATIONS
        out.append({"id": f"cot:{rel}", "kind": "cot", "path": str(p.relative_to(ROOT)),
                    "fields": fields, "source_names": [p.stem, p.parent.name],
                    "pit": _pit(usable, "" if usable else
                                f"{facts['points']} reading(s), under {MIN_OBSERVATIONS}",
                                facts)})
    return out


def intel_fields(dirs: list[Path]) -> tuple[list[dict[str, str]], set[str]]:
    """Numeric fields (split by `symbol` where rows carry one) and the rows' own source names."""
    from mt5desk import dataset_series as DS
    files = DS.snapshot_files(dirs, 0)[-FIELD_SAMPLE_FILES:]
    keys: Counter[str] = Counter()
    per_symbol: Counter[str] = Counter()
    sources: set[str] = set()
    has_symbol = False
    n = 0
    for _t, p in reversed(files):
        for r in DS.rows_in(p):
            n += 1
            if n > FIELD_SAMPLE_ROWS:
                break
            if r.get("source"):
                sources.add(str(r["source"]))
            if isinstance(r.get("symbol"), str) and r["symbol"]:
                has_symbol = True
                per_symbol[r["symbol"]] += 1
            for k, v in r.items():
                if k in DS.NON_SIGNAL_KEYS or isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    keys[str(k)] += 1
    cols = [k for k, _ in keys.most_common()]
    names = DS.pair_fields(cols) + cols
    out: list[dict[str, str]] = [{"field": f, "match": ""} for f in names]
    if has_symbol:
        out = [{"field": f, "match": f"symbol={s}"} for s, _ in per_symbol.most_common(MAX_MATCHES)
               for f in names]
    return out, sources


def intel_datasets(roots: tuple[Path, ...] | None = None) -> list[dict[str, Any]]:
    from mt5desk import dataset_series as DS
    roots = roots or DS.INTEL_ROOTS
    seats = sorted({d.name for r in roots if r.is_dir() for d in r.iterdir()
                    if d.is_dir() and not d.name.startswith((".", "_"))})
    out: list[dict[str, Any]] = []
    for seat in seats:
        dirs = [r / seat for r in roots if (r / seat).is_dir()]
        stamped = DS.snapshot_files(dirs, 0)
        fields, sources = intel_fields(dirs) if stamped else ([], set())
        facts: dict[str, Any] = {"snapshot_files": len(stamped)}
        if not stamped:
            why = "no snapshot file carries a time in its name: no availability stamp"
        elif not fields:
            why = "its rows carry no numeric reading (text/claims only): a direct-cell source"
        else:
            f0 = fields[0]
            facts.update(_series_facts(DS.intel_raw(seat, f0["field"], match=f0["match"],
                                                    roots=roots)))
            why = ("" if facts.get("points", 0) >= MIN_OBSERVATIONS else
                   f"{facts.get('points', 0)} stamped reading(s) of {f0['field']}, under "
                   f"{MIN_OBSERVATIONS}")
        usable = not why
        out.append({"id": f"intel:{seat}", "kind": "intel",
                    "path": [str(d.relative_to(ROOT)) for d in dirs], "fields": fields,
                    "source_names": sorted({seat, *sources}),
                    "pit": _pit(usable, why, facts)})
    return out


def file_datasets(data: Path | None = None) -> list[dict[str, Any]]:
    """Macro axis records and grounds files: listed, never conditioned on (no series inside)."""
    base = data or DATA
    out: list[dict[str, Any]] = []
    for p in sorted((base / "axes").glob("*.json")) if (base / "axes").is_dir() else []:
        doc = _read(p, {}) or {}
        n = doc.get("n_series") if isinstance(doc, dict) else None
        out.append({"id": f"macro:{p.stem}", "kind": "macro", "path": str(p.relative_to(ROOT)),
                    "fields": [], "source_names": [p.stem, str(doc.get("id") or p.stem)],
                    "pit": _pit(False, f"an axis probe record (n_series={n}), not a stored "
                                       "series: the series it names must land in the lake "
                                       "first")})
    grounds = sorted({*base.glob("*sources*.json"), *base.glob("*sources*.jsonl"),
                      *base.glob("*grounds*.json")})
    for p in grounds:
        out.append({"id": f"grounds:{p.stem}", "kind": "grounds",
                    "path": str(p.relative_to(ROOT)), "fields": [],
                    "source_names": [p.stem],
                    "pit": _pit(False, "a list of grounds a miner walks, not a series: its use "
                                       "is the cells its miners' claims compile into")})
    return out


def discover() -> list[dict[str, Any]]:
    named, tags = cultures()
    out = lake_datasets() + cot_datasets() + intel_datasets() + file_datasets()
    for d in out:
        name = d["id"].split(":", 1)[1]
        if d["kind"] == "lake" and d.get("country"):
            d["source_culture"] = str(d["country"]).upper()
        elif d["kind"] == "cot":
            d["source_culture"] = named.get("cot", "US")
        else:
            d["source_culture"] = culture_of(name.split("/")[-1], named, tags)
    return out


# ------------------------------------------------------------------ who reads what
def _corpus() -> dict[str, dict[str, str]]:
    """{role: {repo-relative path: text}} -- the organs a dataset can be wired into."""
    def grab(paths: list[Path]) -> dict[str, str]:
        got: dict[str, str] = {}
        for p in paths:
            try:
                got[str(p.relative_to(ROOT)).replace("\\", "/")] = p.read_text("utf-8", "replace")
            except OSError:
                continue
        return got
    res = DESK / "research"
    # The sealed gauntlet is READ, never edited: its build_cell branches are where the CFTC and
    # other data inputs are loaded for the families that take them as arguments.
    fams = sorted({*(DESK / "mt5desk").glob("famil*.py"),
                   DESK / "scripts" / "external_gauntlet.py"} - NOT_READERS)
    producers = [p for p in sorted(res.glob("*.py")) if p not in NOT_READERS
                 and "enqueue_candidate" in p.read_text("utf-8", "replace")]
    state = sorted({*res.glob("*state*.py"), *res.glob("macro_*.py"), *res.glob("regime*.py"),
                    *(ROOT / "libs" / "portfolio").glob("*.py")})
    return {"producers": grab(producers), "families": grab(fams), "state": grab(state)}


def _patterns(d: dict[str, Any]) -> list[re.Pattern[str]]:
    kind = d["kind"]
    name = d["id"].split(":", 1)[1]
    leaf = name.split("/")[-1]
    q = r"[\"'/]"
    if kind == "intel":
        return [re.compile(r"intelligence[\"']?\s*[/,]\s*[\"']?" + re.escape(leaf) + r"\b"),
                re.compile(r"INTEL\w*\s*/\s*[\"']" + re.escape(leaf) + r"[\"']")]
    if kind == "cot":
        top = name.split("/")[0]
        return [re.compile(q + re.escape(top) + r"(?:\.parquet)?" + q)]
    if kind == "lake":
        return [re.compile(r"lake[\"']?\s*[/,]\s*[\"']?series"),
                re.compile(q + re.escape(leaf) + q)]
    if kind == "macro":
        return [re.compile(r"axes[\"']?\s*[/,]\s*[\"']?" + re.escape(leaf) + r"\b"),
                re.compile(q + re.escape(leaf) + r"\.json" + q)]
    return [re.compile(re.escape(leaf) + r"\.json")]


def _readers(d: dict[str, Any], texts: dict[str, str]) -> list[str]:
    pats = _patterns(d)
    return sorted(path for path, t in texts.items() if any(p.search(t) for p in pats))


def _indirect_family(path: str) -> bool:
    stem = path.rsplit("/", 1)[-1]
    return "condition" in stem or "regime" in stem


# ------------------------------------------------------------------ what was minted
def registry_counts(now: datetime, db: Path | None = None) -> tuple[
        Counter[str], Counter[str], Counter[str], str]:
    """(cells by source_id, cells by trial family, conditioned cells by dataset, note), 7d."""
    db = db if db is not None else REGISTRY_DB
    by_src: Counter[str] = Counter()
    by_fam: Counter[str] = Counter()
    cond: Counter[str] = Counter()
    if not db.exists():
        return by_src, by_fam, cond, f"{UNMEASURED}: no registry at {db}"
    cut = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    ts = "replace(substr(created_at,1,19),' ','T')"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        return by_src, by_fam, cond, f"{UNMEASURED}: registry unopenable ({exc})"
    try:
        for sid, fam, n in con.execute(
                f"select source_id, family, count(*) from research_candidates "  # noqa: S608
                f"where {ts} >= ? group by source_id, family", (cut,)):
            by_src[str(sid or "")] += int(n)
            by_fam[str(fam or "")] += int(n)
        for (pj,) in con.execute(
                f"select params_json from research_candidates where family = ? "  # noqa: S608
                f"and {ts} >= ?", (CONDITIONED_FAMILY, cut)):
            try:
                cond[str((json.loads(pj or "{}") or {}).get("dataset") or "")] += 1
            except ValueError:
                continue
    except sqlite3.Error as exc:
        return Counter(), Counter(), Counter(), f"{UNMEASURED}: registry query failed ({exc})"
    finally:
        con.close()
    return by_src, by_fam, cond, f"registry {db.name}: {sum(by_src.values())} cell(s) in 7d"


def compiler_counts() -> tuple[dict[str, int], str]:
    doc = _read(COMPILED, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("per_source"), dict):
        return {}, f"{UNMEASURED}: {COMPILED.name} unreadable or has no per_source"
    return ({str(k): int((v or {}).get("candidates") or 0)
             for k, v in doc["per_source"].items() if isinstance(v, dict)},
            f"{COMPILED.name} compiled_at {doc.get('compiled_at')}")


# ------------------------------------------------------------------ the census
def census(now: datetime | None = None, db: Path | None = None,
           datasets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    ds = datasets if datasets is not None else discover()
    texts = _corpus()
    by_src, by_fam, cond, reg_note = registry_counts(now, db)
    comp, comp_note = compiler_counts()
    reg_ok = not reg_note.startswith(UNMEASURED)
    comp_ok = not comp_note.startswith(UNMEASURED)
    rows: dict[str, Any] = {}
    for d in ds:
        names = [str(x) for x in d.get("source_names") or []]
        prod = _readers(d, texts["producers"])
        fams = _readers(d, texts["families"])
        state = _readers(d, texts["state"])
        direct_fams = [f for f in fams if not _indirect_family(f)]
        indirect_fams = [f for f in fams if _indirect_family(f)]
        direct_cells: Any = sum(by_src.get(n, 0) for n in names) if reg_ok else UNMEASURED
        if d["kind"] == "cot" and reg_ok:
            # The CFTC families read every cot file; their cells are credited to the kind.
            direct_cells = int(direct_cells) + sum(n for f, n in by_fam.items()
                                                   if f.startswith("cot_"))
        compiled: Any = sum(comp.get(n, 0) for n in names) if comp_ok else UNMEASURED
        indirect_cells: Any = cond.get(d["id"], 0) if reg_ok else UNMEASURED
        counts = [x for x in (direct_cells, compiled, indirect_cells) if isinstance(x, int)]
        fed: Any = (any(counts) if counts else UNMEASURED)
        if fed is True:
            why = ""
        elif fed == UNMEASURED:
            why = "UNMEASURED: neither the registry nor the compiler record is readable"
        else:
            wired = ("WIRED_NOT_PRODUCING: organs read it and no cell was minted from it in 7d"
                     if prod or fams else "UNWIRED: no producer or family reads it")
            why = (f"{wired}; CONDITIONABLE: producer_swarm's {CONDITIONED_FAMILY} producers "
                   "visit it first" if d["pit"]["usable"]
                   else f"{wired}; NO_PIT_SERIES: {d['pit']['why']}")
        rows[d["id"]] = {
            "kind": d["kind"], "path": d.get("path"),
            "source_culture": d.get("source_culture", UNMEASURED),
            "pit_series": d["pit"],
            "fields": len(d.get("fields") or []),
            "uses": {
                "direct": {"cells_7d": direct_cells, "compiler_candidates_last_pass": compiled,
                           "organs": prod + direct_fams},
                "indirect": {"cells_7d": indirect_cells, "organs": indirect_fams,
                             "conditionable": bool(d["pit"]["usable"]),
                             "by": (f"{CONDITIONED_FAMILY} via producer_swarm"
                                    if d["pit"]["usable"] else None)},
                "allocation": {"organs": state, "measured_by": "source reference"},
            },
            "feeds_producer": fed, "why": why,
        }
    unfed = sorted(k for k, r in rows.items() if r["feeds_producer"] is False)
    kinds = Counter(r["kind"] for r in rows.values())
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "rule": ("every dataset on disk (lake packs and registered packs, CFTC files, "
                 "intelligence seats, macro axis records, grounds files) with its three uses -- "
                 "direct cells, indirect conditioned cells, allocation-state readers -- and the "
                 "organs behind each; feeds_producer is False when no direct or indirect cell "
                 "was minted from it in 7d, UNMEASURED when nothing can tell"),
        "registry": reg_note, "compiler": comp_note,
        "totals": {"datasets": len(rows), "by_kind": dict(sorted(kinds.items())),
                   "feeding": sum(1 for r in rows.values() if r["feeds_producer"] is True),
                   "unfed": len(unfed),
                   "unmeasured": sum(1 for r in rows.values()
                                     if r["feeds_producer"] == UNMEASURED),
                   "conditionable": sum(1 for r in rows.values()
                                        if r["pit_series"]["usable"]),
                   "unfed_conditionable": sum(1 for k in unfed
                                              if rows[k]["pit_series"]["usable"]),
                   "with_allocation_reader": sum(1 for r in rows.values()
                                                 if r["uses"]["allocation"]["organs"])},
        "unfed": unfed,
        "unfed_conditionable": [k for k in unfed if rows[k]["pit_series"]["usable"]],
        "datasets": rows,
    }
