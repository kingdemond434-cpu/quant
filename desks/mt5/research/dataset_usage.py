"""THE DATASET-USAGE CENSUS -- is every dataset the desk collects actually fed to something?

THE PRINCIPAL'S ASK (2026-09-30, BACKLOG row 61): "Fix partial and unfed datasets fully,
unstarved and collected." The re-check of 2026-11-03 found no per-dataset artifact on LIVE that
said which collected datasets are consumed, so the ask was UNMEASURED. This is that artifact.

WHY IT IS NOT THE TWELVE-QUESTION AUDIT. `scripts/check_ingestion_exploitation.py` audits the
ingestion ledger's UNIT KINDS (seat rows, claims, bar files) against cell exploitation. It never
asks the three questions here: is the dataset FRESH against its own declared cadence, is it
COMPLETE against the fields / series / timeframes its registry row declares, and does a reader
ON A CLOCK exist for it. A dataset can be exploited once and then sit stale for a month with
every question there answered YES; this census is what catches that.

ONE ROW PER DATASET, enumerated from the registries the desk already keeps (nothing is invented
here, and a dataset is added by adding a row THERE):

    data_registry   desks/mt5/data/data_registry.json -- rows that declare a `path`
                    (a row with no path was DISCOVERED, never collected: listed, not judged)
    free_stack      desks/mt5/data/free_stack_sources.json -- obs/<id>.jsonl + fs_<id>.parquet
    futures_state   desks/mt5/reports/FUTURES_STATE.json -- every series that organ built,
                    with ITS OWN staleness verdict (never re-derived here)
    acquired        desks/mt5/data/acquired/registry.json -- every acquired series
    alt_platforms   desks/mt5/reports/ALT_DATA_YIELD.json -- every platform that ever yielded rows

PER DATASET:

  freshness     the newest observation (parquet column statistics, never a full read) or, when
                the file carries none, the last write; FRESH when within STALE_FACTOR x the
                declared cadence. A registry row with no cadence is judged against the fallback
                week and says `cadence_source: UNDECLARED_FALLBACK` -- the owner should declare
                one. A stamp in the future is LOOKAHEAD: it is set aside, flagged, and never
                counts as fresh.
  completeness  PARTIAL when a declared part (series, contract, timeframe, symbol count, a
                companion file, the free-stack column map) is missing, naming each one.
  consumers     every first-party module whose text references the dataset (its id, its file
                stem, or its directory joined the way this codebase joins paths), minus its
                writer, tests, and the auditors that only read to count. A reader counts as
                SCHEDULED when a clock (hourly/daily cycle, ops units and scripts, box tasks)
                names it or reaches it through imports -- an unwired reader feeds nothing (III.16).

VERDICT, never defaulted to clean (L1.28a):

    UNMEASURED  no file of the dataset on this host, or its registry unreadable
    UNFED       collected, and no scheduled reader
    STARVED     a scheduled reader exists, and the data is STALE or PARTIAL
    FED         a scheduled reader exists, and the data is fresh and complete

THE FENCE: RED when any dataset has been UNFED or STARVED for more than RED_AFTER_H hours (the
onset is the stale point when staleness is the cause, else the first pass that saw it, carried
in this artifact); UNMEASURED when nothing could be measured or any in-scope dataset is
UNMEASURED; GREEN otherwise. The census names datasets; it never fetches, revives or edits one.

    python desks/mt5/research/dataset_usage.py --once [--budget-s 240]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]

UNMEASURED = "UNMEASURED"
#: The leg's own artifact (the runtime attestation reads this binding); ARTIFACT is its
#: desk-relative name, so a test can root the whole organ at a temp desk.
OUT = DESK / "reports" / "DATASET_USAGE.json"
ARTIFACT = "reports/DATASET_USAGE.json"
#: A dataset is STALE past this many multiples of its declared cadence: one missed publication
#: is a hiccup, two is a pattern (the issue board's own tolerance).
STALE_FACTOR = 2.0
#: The cadence a registry row is judged against when it declares none. Named in the row.
FALLBACK_CADENCE_H = 168.0
#: The fence turns RED once a dataset has been UNFED or STARVED this long.
RED_AFTER_H = 24.0
#: A stamp this far past now is lookahead, not freshness.
FUTURE_TOLERANCE_H = 1.0
CADENCE_H = {"hourly": 1.0, "4h": 4.0, "daily": 24.0, "weekly": 168.0, "monthly": 744.0}
DEFAULT_BUDGET_S = 240.0

#: Readers that only COUNT a dataset: an audit is not a consumer.
AUDITORS: tuple[str, ...] = (
    "desks/mt5/research/dataset_usage.py", "desks/mt5/research/unused_information.py",
    "desks/mt5/research/ingestion_ledger.py", "desks/mt5/research/runtime_attestation.py",
    "desks/mt5/research/issue_board.py", "libs/ops/capability_graph.py",
)
#: Files whose text names the scripts a clock runs.
CLOCK_GLOBS: tuple[str, ...] = (
    "desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py",
    "ops/*.sh", "ops/**/*.sh", "ops/*.service", "desks/mt5/scripts/*.ps1",
)
#: The clocks themselves name every dataset their legs touch; naming is not reading.
CLOCKS: frozenset[str] = frozenset({"desks/mt5/research/hourly_cycle.py",
                                    "desks/mt5/research/daily_cycle.py"})
CODE_ROOTS: tuple[str, ...] = ("libs", "desks/mt5", "scripts", "ops")


@dataclass
class Spec:
    """One dataset as its registry declares it."""

    id: str
    registry: str
    paths: list[str]                         # desk-relative globs
    cadence_h: float | None = None
    cadence_source: str = "declared"
    parts: dict[str, list[str]] = field(default_factory=dict)
    min_files: int = 0
    groups: list[list[set[str]]] = field(default_factory=list)   # consumer token groups
    writers: list[str] = field(default_factory=list)
    declared_consumers: list[str] = field(default_factory=list)
    fresh_override: tuple[str, str] | None = None                # (state, why) from its owner
    last_write_override: str | None = None
    extra_partial: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ small readers
def _now() -> datetime:
    return datetime.now(UTC)


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v or v == UNMEASURED:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def dir_tokens(rel_dir: str) -> set[str]:
    """The spellings this codebase uses to join a directory: 'a/b', "a" / "b", / "b"."""
    parts = [p for p in rel_dir.strip("/").split("/") if p]
    if not parts:
        return set()
    b = parts[-1]
    out = {f'/ "{b}"', f"/ '{b}'"}
    if len(parts) >= 2:
        a = parts[-2]
        out |= {f"{a}/{b}", f'"{a}" / "{b}"', f"'{a}' / '{b}'"}
    return out


def path_groups(glob: str) -> list[list[set[str]]]:
    """Consumer token groups for one desk-relative path glob."""
    d, _, name = glob.rpartition("/")
    stem = re.sub(r"\.(parquet|jsonl|json|csv)$", "", name)
    if "*" not in stem:
        return [[{stem}]] if len(stem) >= 4 else [[dir_tokens(d), {stem}]]
    frag = max(stem.split("*"), key=len)
    toks = dir_tokens(d)
    if not toks:
        return []
    return [[toks, {frag}]] if len(frag) >= 3 else [[toks]]


# ------------------------------------------------------------------ registries
#: What every registry reader returns: its specs, the rows it saw but cannot judge, an error.
Read = tuple[list["Spec"], list[dict[str, Any]], str | None]

def from_data_registry(desk: Path) -> tuple[list[Spec], list[dict[str, Any]], str | None]:
    doc = _read_json(desk / "data" / "data_registry.json")
    rows = (doc or {}).get("datasets") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return [], [], "data/data_registry.json unreadable or has no datasets block"
    specs: list[Spec] = []
    not_collected: list[dict[str, Any]] = []
    for k, r in sorted(rows.items()):
        if not isinstance(r, dict):
            continue
        path = r.get("path")
        if not isinstance(path, str) or not path:
            not_collected.append({"id": k, "registry": "data_registry",
                                  "lifecycle": r.get("lifecycle", UNMEASURED),
                                  "why": "registry row declares no path: discovered, never "
                                         "collected"})
            continue
        cad = CADENCE_H.get(str(r.get("cadence") or ""))
        parts: dict[str, list[str]] = {}
        for key in ("series", "contracts", "timeframes"):
            v = r.get(key)
            if isinstance(v, list) and v:
                parts[key] = [str(x) for x in v]
        sym = r.get("symbols")
        prov = str(r.get("provenance") or "")
        writers = re.findall(r"[\w/]+\.py", prov) + re.findall(r"[\w/]+\.py", str(r.get("source")))
        specs.append(Spec(
            id=k, registry="data_registry", paths=[path], cadence_h=cad,
            cadence_source="declared" if cad else "UNDECLARED_FALLBACK",
            parts=parts, min_files=int(sym) if isinstance(sym, int) else 0,
            groups=[[{k}], *path_groups(path)], writers=writers,
            declared_consumers=re.findall(r"[\w/]+\.py", str(r.get("consumer") or ""))))
    return specs, not_collected, None


def from_free_stack(desk: Path) -> tuple[list[Spec], list[dict[str, Any]], str | None]:
    doc = _read_json(desk / "data" / "free_stack_sources.json")
    rows = (doc or {}).get("sources") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return [], [], "data/free_stack_sources.json unreadable or has no sources list"
    cols = _read_json(desk / "data" / "free_stack" / "columns.json")
    specs: list[Spec] = []
    lake = {'"lake" / "series"', "lake/series", "'lake' / 'series'"}
    for r in rows:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        sid = str(r["id"])
        cad = CADENCE_H.get(str(r.get("cadence") or ""))
        direct = ((r.get("uses") or {}).get("direct") or {}) if isinstance(r.get("uses"), dict) \
            else {}
        organ = str(direct.get("organ") or "")
        extra: list[str] = []
        if isinstance(cols, dict) and not cols.get(sid):
            extra.append("columns.json maps no column of this source to an instrument")
        specs.append(Spec(
            id=sid, registry="free_stack",
            paths=[f"data/free_stack/obs/{sid}.jsonl", f"data/lake/series/fs_{sid}.parquet"],
            cadence_h=cad, cadence_source="declared" if cad else "UNDECLARED_FALLBACK",
            parts={"files": [f"{sid}.jsonl", f"fs_{sid}.parquet"]},
            groups=[[{f"fs_{sid}"}], [{"fs_{"}], [lake]],
            writers=["desks/mt5/research/free_stack_hunter.py", "libs/data/free_stack.py"],
            declared_consumers=re.findall(r"[\w/]+\.py", organ), extra_partial=extra))
    return specs, [], None


def from_futures_state(desk: Path, now: datetime) -> tuple[list[Spec], list[dict[str, Any]],
                                                           str | None]:
    p = desk / "reports" / "FUTURES_STATE.json"
    doc = _read_json(p)
    if not isinstance(doc, dict) or not isinstance(doc.get("series"), dict):
        return [], [], "reports/FUTURES_STATE.json absent or carries no series block"
    at = _ts(doc.get("generated_utc") or doc.get("generated_at") or doc.get("at"))
    if at is None:
        try:
            at = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        except OSError:
            at = None
    report_stale = at is None or (now - at).total_seconds() > 2 * 3600 * STALE_FACTOR
    stale: dict[str, str] = {}
    for n in doc.get("notes") or []:
        if isinstance(n, dict) and str(n.get("why", "")).startswith("STALE"):
            stale[str(n.get("series"))] = str(n.get("why"))
    lake = {'"lake" / "series"', "lake/series", "'lake' / 'series'"}
    specs: list[Spec] = []
    for sid, meta in sorted(doc["series"].items()):
        if report_stale:
            fo = (UNMEASURED, "FUTURES_STATE.json is itself stale or unstamped: its staleness "
                              "verdicts cannot be read as current")
        elif sid in stale:
            fo = ("STALE", f"futures_state's own verdict: {stale[sid]}")
        else:
            fo = ("FRESH", "futures_state's own verdict: not stale on its last pass")
        last = meta.get("last_event") if isinstance(meta, dict) else None
        specs.append(Spec(
            id=str(sid), registry="futures_state", paths=[f"data/lake/series/{sid}.parquet"],
            cadence_h=None, cadence_source="owner_verdict", groups=[[{str(sid)}], [lake]],
            writers=["desks/mt5/research/futures_state.py"], fresh_override=fo,
            last_write_override=str(last) if last else None))
    return specs, [], None


def from_acquired(desk: Path) -> tuple[list[Spec], list[dict[str, Any]], str | None]:
    doc = _read_json(desk / "data" / "acquired" / "registry.json")
    rows = (doc or {}).get("series") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return [], [], "data/acquired/registry.json unreadable or has no series block"
    specs: list[Spec] = []
    for sid, r in sorted(rows.items()):
        if not isinstance(r, dict):
            continue
        base = Path(str(r.get("path") or f"{sid}.parquet").replace("\\", "/")).name
        specs.append(Spec(
            id=str(sid), registry="acquired", paths=[f"data/acquired/{base}"],
            cadence_h=None, cadence_source="UNDECLARED_FALLBACK",
            groups=[[{str(sid)}], [dir_tokens("data/acquired")]],
            writers=["desks/mt5/research/acquire_datasets.py"]))
    return specs, [], None


def from_alt_platforms(desk: Path) -> tuple[list[Spec], list[dict[str, Any]], str | None]:
    doc = _read_json(desk / "reports" / "ALT_DATA_YIELD.json")
    rows = ((doc or {}).get("platforms") or {}).get("rows_by_platform") \
        if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return [], [], "reports/ALT_DATA_YIELD.json unreadable or has no rows_by_platform"
    specs: list[Spec] = []
    not_collected: list[dict[str, Any]] = []
    intel = dir_tokens("data/intelligence")
    for name, r in sorted(rows.items()):
        if not isinstance(r, dict):
            continue
        best = r.get("best_rows")
        if not isinstance(best, (int, float)) or best <= 0:
            not_collected.append({"id": name, "registry": "alt_platforms",
                                  "why": f"never yielded a row (last_state "
                                         f"{r.get('last_state', UNMEASURED)})"})
            continue
        last = r.get("last_success") if _ts(r.get("last_success")) else (
            r.get("last_attempt") if r.get("last_state") == "ok" else None)
        specs.append(Spec(
            id=str(name), registry="alt_platforms", paths=[], cadence_h=None,
            cadence_source="UNDECLARED_FALLBACK", groups=[[intel]],
            writers=["desks/mt5/research/deep_forest_miner.py",
                     "desks/mt5/research/regional_survivor_hunters.py"],
            last_write_override=str(last) if last else None))
    return specs, not_collected, None


# ------------------------------------------------------------------ code corpus
def _code_files(repo: Path) -> list[str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), "ls-files", "--", *[f"{c}/*.py" for c in
                                                                       CODE_ROOTS]],
                           capture_output=True, text=True, timeout=60, check=False)
        files = [ln for ln in r.stdout.splitlines() if ln.endswith(".py")]
    except (OSError, subprocess.SubprocessError):
        files = []
    if not files:
        for c in CODE_ROOTS:
            for p in (repo / c).rglob("*.py"):
                files.append(p.relative_to(repo).as_posix())
    return sorted({f for f in files if "/tests/" not in f and not f.startswith("tests/")
                   and "/data/" not in f})


@dataclass
class Corpus:
    found: dict[str, set[str]]        # file -> tokens it contains
    scheduled: set[str]               # files a clock reaches
    n_files: int
    truncated: bool


_IMPORT = re.compile(r"^[ \t]*(?:from[ \t]+([\w.]+)[ \t]+import[ \t]+([^\n#]+)|"
                     r"import[ \t]+([\w., \t]+))", re.M)
_DOTTED = re.compile(r"[\"']((?:mt5desk|research|libs|scripts)\.[\w.]+)[\"']")


def scan_corpus(repo: Path, tokens: Iterable[str], deadline: float) -> Corpus:
    toks = sorted({t for t in tokens if t}, key=len, reverse=True)
    rx = re.compile("|".join(re.escape(t) for t in toks)) if toks else None
    files = _code_files(repo)
    found: dict[str, set[str]] = {}
    imports: dict[str, set[str]] = {}
    by_stem: dict[str, list[str]] = {}
    truncated = False
    for f in files:
        stem = Path(f).stem if Path(f).stem != "__init__" else Path(f).parent.name
        by_stem.setdefault(stem, []).append(f)
    for f in files:
        if time.monotonic() > deadline:
            truncated = True
            break
        try:
            text = (repo / f).read_text("utf-8", errors="replace")
        except OSError:
            continue
        if rx is not None:
            hit = {m.group(0) for m in rx.finditer(text)}
            if hit:
                found[f] = hit
        names: set[str] = set()
        for m in _IMPORT.finditer(text):
            if m.group(1):
                names.add(m.group(1).split(".")[-1])
                names |= {n.strip(" ()\t").split(" as ")[0].strip()
                          for n in m.group(2).split(",")}
            else:
                names |= {n.strip().split(" as ")[0].split(".")[-1]
                          for n in (m.group(3) or "").split(",")}
        names |= {m.group(1).split(".")[-1] for m in _DOTTED.finditer(text)}
        imports[f] = {n for n in names if n}
    roots = clock_roots(repo, files)
    seen = set(roots)
    stack = list(roots)
    while stack:
        f = stack.pop()
        for n in imports.get(f, ()):
            for g in by_stem.get(n, ()):
                if g not in seen:
                    seen.add(g)
                    stack.append(g)
    return Corpus(found=found, scheduled=seen, n_files=len(files), truncated=truncated)


def clock_roots(repo: Path, files: list[str]) -> set[str]:
    texts: list[str] = []
    roots: set[str] = set()
    for g in CLOCK_GLOBS:
        for p in repo.glob(g):
            try:
                texts.append(p.read_text("utf-8", errors="replace"))
            except OSError:
                continue
            rel = p.relative_to(repo).as_posix()
            if rel.endswith(".py"):
                roots.add(rel)
    blob = "\n".join(texts).replace("\\", "/")
    for f in files:
        short = f[len("desks/mt5/"):] if f.startswith("desks/mt5/") else f
        if f in blob or ("/" in short and short in blob):
            roots.add(f)
    return roots


# ------------------------------------------------------------------ measurement
def _newest_obs(p: Path, now: datetime) -> tuple[datetime | None, bool]:
    """The largest timestamp in a parquet's column statistics; (None, False) when it has none.
    The flag is True when a stamp sat in the future and was set aside (lookahead)."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(p)  # type: ignore[no-untyped-call]
    except Exception:
        return None, False
    schema = pf.schema_arrow
    idx = [i for i, f in enumerate(schema) if pa.types.is_timestamp(f.type)]
    best: datetime | None = None
    future = False
    md = pf.metadata
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        for i in idx:
            if i >= rg.num_columns:
                continue
            st = rg.column(i).statistics
            if st is None or not st.has_min_max:
                continue
            v = st.max
            if not isinstance(v, datetime):
                continue
            v = v if v.tzinfo else v.replace(tzinfo=UTC)
            if (v - now).total_seconds() > FUTURE_TOLERANCE_H * 3600:
                future = True
                continue
            best = v if best is None or v > best else best
    return best, future


def measure(spec: Spec, desk: Path, corpus: Corpus | None, now: datetime) -> dict[str, Any]:
    files: list[Path] = []
    for g in spec.paths:
        files.extend(sorted(desk.glob(g)))
    row: dict[str, Any] = {"id": spec.id, "registry": spec.registry,
                           "paths": spec.paths, "n_files": len(files),
                           "cadence_h": spec.cadence_h or (None if spec.fresh_override
                                                           else FALLBACK_CADENCE_H),
                           "cadence_source": spec.cadence_source}
    # ---- freshness
    obs_l: list[datetime] = []
    mt_l: list[datetime] = []
    lookahead = False
    for f in files:
        obs, fut = (_newest_obs(f, now) if f.suffix == ".parquet" else (None, False))
        lookahead = lookahead or fut
        if obs is not None:
            obs_l.append(obs)
            continue
        try:
            mt = datetime.fromtimestamp(f.stat().st_mtime, UTC)
        except OSError:
            continue
        if (mt - now).total_seconds() > FUTURE_TOLERANCE_H * 3600:
            lookahead = True
            continue
        mt_l.append(mt)
    newest: datetime | None = max(obs_l) if obs_l else (max(mt_l) if mt_l else None)
    basis = "observation" if obs_l else ("last_write" if mt_l else UNMEASURED)
    if newest is None and spec.last_write_override:
        newest = _ts(spec.last_write_override)
        basis = "registry_stamp" if newest else basis
        if newest is not None and newest > now:
            lookahead, newest = True, None
    row["newest"] = newest.isoformat(timespec="seconds") if newest else UNMEASURED
    row["freshness_basis"] = basis
    row["lookahead_stamps"] = lookahead
    age_h = round((now - newest).total_seconds() / 3600, 2) if newest else None
    row["age_h"] = age_h if age_h is not None else UNMEASURED
    if spec.fresh_override is not None:
        fresh, fwhy = spec.fresh_override
    elif newest is None:
        fresh, fwhy = UNMEASURED, ("no file of this dataset on this host" if not files
                                   else "no timestamp or write time readable")
    else:
        cad = spec.cadence_h or FALLBACK_CADENCE_H
        bound = STALE_FACTOR * cad
        fresh = "FRESH" if age_h is not None and age_h <= bound else "STALE"
        fwhy = f"age {age_h}h vs {bound}h ({STALE_FACTOR}x cadence {cad}h, {spec.cadence_source})"
    row["freshness"], row["freshness_why"] = fresh, fwhy
    # ---- completeness
    missing: list[str] = list(spec.extra_partial)
    names = " ".join(f.name for f in files).lower()
    if spec.registry == "data_registry" and files and len(files) == 1 and \
            files[0].suffix == ".json":
        try:
            names = files[0].read_text("utf-8", errors="replace").lower()
        except OSError:
            names = ""
    for key, want in (spec.parts.items() if files else ()):
        for w in want:
            if w.lower() not in names:
                missing.append(f"{key}:{w}")
    if spec.min_files and len(files) < spec.min_files:
        missing.append(f"files: {len(files)} of the {spec.min_files} declared")
    complete = UNMEASURED if not files and spec.paths else "PARTIAL" if missing else "COMPLETE"
    row["completeness"], row["missing"] = complete, missing[:40]
    row["n_missing"] = len(missing)
    # ---- consumers
    writers = set(spec.writers)
    readers: list[dict[str, Any]] = []
    if corpus is not None:
        for fp, hit in sorted(corpus.found.items()):
            if fp in writers or fp in AUDITORS or fp in CLOCKS or fp.startswith("scripts/check_"):
                continue
            if any(all(s & hit for s in grp) for grp in spec.groups):
                readers.append({"path": fp, "scheduled": fp in corpus.scheduled})
    for d in spec.declared_consumers:
        full = d if d.startswith(("desks/", "libs/", "scripts/")) else f"desks/mt5/{d}"
        if not any(r["path"] == full for r in readers):
            readers.append({"path": full, "scheduled": bool(corpus and full in corpus.scheduled),
                            "declared_only": True,
                            "exists": (REPO / full).exists() if corpus else UNMEASURED})
    sched = [r for r in readers if r["scheduled"]]
    row["consumers"] = readers[:25]
    row["n_consumers"] = len(readers)
    row["n_scheduled_consumers"] = len(sched)
    # ---- verdict
    row["verdict"], row["why"] = verdict(fresh, complete, readers, sched, corpus,
                                         bool(files) or spec.last_write_override is not None
                                         or spec.fresh_override is not None)
    return row


def verdict(fresh: str, complete: str, readers: list[dict[str, Any]],
            sched: list[dict[str, Any]], corpus: Corpus | None,
            present: bool) -> tuple[str, str]:
    """FED / UNFED / STARVED / UNMEASURED. Absence is never read as clean."""
    if not present:
        return UNMEASURED, "no file of this dataset on this host"
    if corpus is None:
        return UNMEASURED, "the reader scan did not run: consumers unmeasured"
    if not sched:
        if corpus.truncated:
            return UNMEASURED, "the reader scan was cut short by the budget and found none"
        return "UNFED", ("collected, and no reader at all" if not readers else
                         f"{len(readers)} reader(s), none reached by any clock (III.16)")
    if fresh == "STALE" or complete == "PARTIAL":
        bits = [b for b, on in (("stale", fresh == "STALE"), ("partial", complete == "PARTIAL"))
                if on]
        return "STARVED", f"{len(sched)} scheduled reader(s), data is {' and '.join(bits)}"
    if fresh == UNMEASURED or complete == UNMEASURED:
        return UNMEASURED, f"freshness {fresh}, completeness {complete}"
    return "FED", f"{len(sched)} scheduled reader(s), fresh and complete"


def _onset(row: Mapping[str, Any], prev: Mapping[str, Any], now: datetime) -> datetime:
    """When this dataset became UNFED/STARVED: the stale point when staleness is the cause,
    else the onset the previous pass recorded, else now."""
    cands = [now]
    p = _ts(prev.get("bad_since")) if prev.get("verdict") in ("UNFED", "STARVED") else None
    if p is not None:
        cands.append(p)
    newest = _ts(row.get("newest"))
    cad = row.get("cadence_h")
    if row.get("verdict") == "STARVED" and row.get("freshness") == "STALE" and newest and \
            isinstance(cad, (int, float)):
        cands.append(newest + timedelta(hours=STALE_FACTOR * float(cad)))
    return min(cands)


def build(desk: Path = DESK, repo: Path = REPO, *, budget_s: float = DEFAULT_BUDGET_S,
          now: datetime | None = None, corpus: Corpus | None = None,
          scan: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or _now()
    specs: list[Spec] = []
    not_collected: list[dict[str, Any]] = []
    registries: dict[str, str] = {}
    readers_of: tuple[tuple[str, Callable[[], Read]], ...] = (
        ("data_registry", lambda: from_data_registry(desk)),
        ("free_stack", lambda: from_free_stack(desk)),
        ("futures_state", lambda: from_futures_state(desk, now)),
        ("acquired", lambda: from_acquired(desk)),
        ("alt_platforms", lambda: from_alt_platforms(desk)))
    for name, fn in readers_of:
        try:
            got, nc, err = fn()
        except Exception as exc:
            got, nc, err = [], [], f"{type(exc).__name__}: {exc}"
        registries[name] = f"{UNMEASURED}: {err}" if err else f"read {len(got)} dataset(s)"
        specs.extend(got)
        not_collected.extend(nc)
    if corpus is None and scan:
        toks: set[str] = set()
        for sp in specs:
            for grp in sp.groups:
                for alts in grp:
                    toks |= alts
        corpus = scan_corpus(repo, toks, t0 + budget_s * 0.7)
    prev_doc = _read_json(desk / ARTIFACT)
    prev = {(r.get("registry"), r.get("id")): r for r in (prev_doc or {}).get("datasets") or []
            if isinstance(r, dict)} if isinstance(prev_doc, dict) else {}
    rows: list[dict[str, Any]] = []
    for sp in specs:
        if time.monotonic() - t0 > budget_s:
            rows.append({"id": sp.id, "registry": sp.registry, "verdict": UNMEASURED,
                         "why": "budget exhausted before this dataset was measured"})
            continue
        r = measure(sp, desk, corpus, now)
        if r["verdict"] in ("UNFED", "STARVED"):
            since = _onset(r, prev.get((sp.registry, sp.id), {}), now)
            r["bad_since"] = since.isoformat(timespec="seconds")
            r["bad_for_h"] = round((now - since).total_seconds() / 3600, 2)
        rows.append(r)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    red = [r for r in rows if r["verdict"] in ("UNFED", "STARVED")
           and float(r.get("bad_for_h") or 0) > RED_AFTER_H]
    pending = [r for r in rows if r["verdict"] in ("UNFED", "STARVED") and r not in red]
    unmeasured = [r for r in rows if r["verdict"] == UNMEASURED]
    measured = [r for r in rows if r["verdict"] != UNMEASURED]
    if red:
        fence, fwhy = "RED", f"{len(red)} dataset(s) UNFED or STARVED for more than {RED_AFTER_H}h"
    elif not measured:
        fence, fwhy = UNMEASURED, "no dataset could be measured on this host"
    elif unmeasured:
        fence, fwhy = UNMEASURED, f"{len(unmeasured)} dataset(s) unmeasured on this host"
    elif pending:
        fence, fwhy = "GREEN", (f"{len(pending)} dataset(s) UNFED or STARVED for under "
                                f"{RED_AFTER_H}h (pending_red); none past the line")
    else:
        fence, fwhy = "GREEN", "every collected dataset has a scheduled reader and is fresh"

    def _top(verd: str) -> list[dict[str, Any]]:
        sel = [r for r in rows if r["verdict"] == verd]
        sel.sort(key=lambda r: -float(r.get("bad_for_h") or 0))
        return [{"registry": r["registry"], "id": r["id"], "why": r.get("why"),
                 "bad_for_h": r.get("bad_for_h"), "missing": r.get("missing", [])[:5]}
                for r in sel[:15]]
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "organ": "desks/mt5/research/dataset_usage.py",
        "ask": "BACKLOG row 61 (principal 2026-09-30): fix partial and unfed datasets fully, "
               "unstarved and collected",
        "fence": fence, "fence_why": fwhy,
        "rule": f"RED when any dataset is UNFED or STARVED for more than {RED_AFTER_H}h; "
                "UNMEASURED when nothing or any in-scope dataset is unmeasured; GREEN otherwise",
        "counts": counts, "n_datasets": len(rows),
        "red": [{"registry": r["registry"], "id": r["id"], "verdict": r["verdict"],
                 "bad_for_h": r.get("bad_for_h"), "why": r.get("why")} for r in red],
        "pending_red": [{"registry": r["registry"], "id": r["id"], "verdict": r["verdict"],
                         "bad_for_h": r.get("bad_for_h")} for r in pending],
        "top_unfed": _top("UNFED"), "top_starved": _top("STARVED"),
        "registries": registries,
        "not_collected": not_collected,
        "cadence_undeclared": sorted(f"{r['registry']}:{r['id']}" for r in rows
                                     if r.get("cadence_source") == "UNDECLARED_FALLBACK"),
        "reader_scan": ({"files": corpus.n_files, "files_with_hits": len(corpus.found),
                         "scheduled_files": len(corpus.scheduled),
                         "truncated": corpus.truncated} if corpus else UNMEASURED),
        "datasets": rows,
        "elapsed_s": round(time.monotonic() - t0, 2),
    }


def write(doc: Mapping[str, Any], desk: Path = DESK) -> Path:
    out = desk / ARTIFACT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one census pass (the leg's mode)")
    ap.add_argument("--budget-s", type=float,
                    default=float(os.environ.get("QUANT_LEG_BUDGET_S") or DEFAULT_BUDGET_S) * 0.8)
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    if not a.dry_run:
        write(doc)
    print(json.dumps({k: doc[k] for k in ("fence", "fence_why", "counts", "n_datasets",
                                          "elapsed_s")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
