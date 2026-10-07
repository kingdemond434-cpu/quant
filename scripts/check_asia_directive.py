#!/usr/bin/env python3
"""THE ASIA DIRECTIVE'S COMPLETION AUDIT -- every requirement on the directive's own 13-state ladder.

    python scripts/check_asia_directive.py --once          # write the audit (the hourly leg)
    python scripts/check_asia_directive.py --summary       # print the CRO/law-gate summary
    python scripts/check_asia_directive.py --fence         # portable law-gate half (schema only)

WHAT THE DIRECTIVE ASKS (PART XXXVII). "Create one canonical machine-readable audit of this entire
mandate. For every requirement classify ABSENT, CODED, WIRED, SCHEDULED, RUNNING, PRODUCING_DATA,
PRODUCING_CELLS, JUDGED, FORWARD, LIVE, PROVEN, BLOCKED, UNMEASURED. Never collapse these to
'implemented'." Each item carries owner module, scheduler, input and output artifact, freshness,
last successful run, cells emitted, cells judged, survivors, blocker and next repair.

THE REQUIREMENTS ARE DATA, AND THEY ARE THE PROJECT AUDIT'S OWN. `desks/mt5/data/
asia_directive_requirements.json` holds the ASIA-xxxx rows of the project completion audit
(`reports/completion_audit/mandate_files_<date>.json`), vendored by `--import-audit PATH` so the box
reads them without the project share. There is no parallel requirement list: each row keeps the
audit's id, text, state, modules, clock and artifacts, and the file's `overlays` (the runtime
evidence specs of the 2026-10-06 diff report, attached by regex + PART) add the artifacts that
would PROVE a row. The checker re-derives every row's state on the same ladder names the audit
uses and publishes the delta against the audit's state (same / up / down / unconfirmed / changed).

EVERY RUNG IS EARNED, AND ONLY ON TOP OF THE ONE BELOW IT. Where evidence is missing or
ambiguous the row reads the LOWER state or UNMEASURED, never the higher one.

CODE CAN ONLY GET A ROW TO SCHEDULED. The static rungs come from the tree: ABSENT (owner module or
its declared code marker missing), CODED (the module and marker exist), WIRED (every code owner is
REACHABLE from a scheduler root -- hourly_cycle, daily_cycle, a box task in box_tasks.manifest, a
VPS timer's service -- traced through imports and the paths runners execute; "some module imports
it" is not wiring), SCHEDULED (wired, and EVERY declared clock is confirmed in the tree; a partial
clock is not a schedule, and an audit-named clock is never taken on the audit's word). Every rung
above that is read from what the organs WROTE: the pack chain
(PACK_CELLS.json), the alt-proxy vintage store and its gain tests (ALT_PROXIES.json), the free
stack (FREE_STACK_YIELD.json), the collector (ASIA_COLLECTOR.json), the runtime attestation
(docs/research/runtime_state.json), and the three before/after decision ledgers that prove a
feedback loop moved something (EVIG -> collection order, ROI -> forest budget, deep-forest
language rotation).

A SHARED ARTIFACT IS NOBODY'S WHOLE COUNT. An artifact several requirements name credits each only
the rows its own language / country / region filter selects (`requirement_filter`); with no filter,
or rows that carry none of its fields, the probe is unattributed and proves nothing for that row.
Only an organ's OUTPUTS are evidence (an input it reads is not). An UNDERPOWERED gain test is an
emitted cell, not a judged one. PROVEN needs every lower rung, FORWARD and LIVE included, so a
proof whose row has no forward/live lineage stays at the rung it holds. Freshness is the
artifact's own generated_at / row stamp, never file mtime; none is UNMEASURED.

ABSENCE IS NEVER A PASS (L1.28a). A scheduled row whose evidence artifacts are all absent on this
host is UNMEASURED, with the rung the code reached carried beside it. A count the artifact does
not publish is UNMEASURED, never 0. A row whose XLIV verification (e.g. "SGE must maintain actual
daily history, not one day") fails is held at RUNNING with the reason, however much data it has.

IT MOVES NOTHING. It reads artifacts and writes one report; it sizes, gates and vetoes nothing.
The law-gate half (`--fence`) validates the requirement file and prints the last audit's summary;
it fails only on a malformed requirement file, never on a requirement's state.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import fnmatch
import json
import os
import re
import socket
import sys
import time
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.ledger_rotation import ledger_files  # noqa: E402

DESK_REL = "desks/mt5"
REQS_REL = "desks/mt5/data/asia_directive_requirements.json"
OUT_REL = "desks/mt5/reports/ASIA_COMPLETION_AUDIT.json"
RUNTIME_REL = "docs/research/runtime_state.json"
REGISTRY_REL = "desks/mt5/data/asia_sources.json"
COLLECTOR_STATE_REL = "desks/mt5/data/lake/collector_state.json"
FOREST_GROUNDS_REL = "desks/mt5/data/deep_forest_sources.json"
FOREST_RUNS_REL = "desks/mt5/data/forest_runs.jsonl"
COLLECTOR_REL = "desks/mt5/reports/ASIA_COLLECTOR.json"

UNMEASURED = "UNMEASURED"
LADDER: tuple[str, ...] = ("ABSENT", "CODED", "WIRED", "SCHEDULED", "RUNNING", "PRODUCING_DATA",
                           "PRODUCING_CELLS", "JUDGED", "FORWARD", "LIVE", "PROVEN", "BLOCKED",
                           UNMEASURED)
#: The progress order. BLOCKED and UNMEASURED are side states: each item also carries the rung it
#: reached so a blocked or unmeasured row never hides how far the code got.
PROGRESS: tuple[str, ...] = LADDER[:11]
RANK = {s: i for i, s in enumerate(PROGRESS)}

#: Freshness horizons: an hourly organ's artifact is stale after three missed passes; anything
#: else after a missed day plus slack.
HOURLY_STALE_H = 3.0
OTHER_STALE_H = 26.0
#: The files a scheduler entry is looked up in. Static facts about the tree.
SCHEDULER_FILES = {
    "hourly": "desks/mt5/research/hourly_cycle.py",
    "own_clock": "desks/mt5/research/hourly_cycle.py",
    "daily": "desks/mt5/research/daily_cycle.py",
    "battery": "desks/mt5/research/batteries.py",
    "fence": "scripts/run_law_gate.py",
}
#: "audit:<text>" is a clock the project audit names that is not an hourly_cycle leg (a box task,
#: a VPS timer, a department resident). It is NEVER taken on the audit's word: it counts as found
#: only when the text names something this tree can confirm -- a box task in BOX_TASKS_REL, a VPS
#: timer unit under ops/, an hourly_cycle leg, or a quoted daily_cycle entry. "hourly_cycle legs /
#: department residents" names nothing and is not a clock.
SCHEDULER_KINDS = frozenset(SCHEDULER_FILES) | {"audit"}
#: The box's task manifest (one `TASK name=... runs=... organ=...` line per scheduled task) and
#: the VPS's systemd units. With hourly_cycle and daily_cycle these are the scheduler ROOTS that
#: WIRED is traced from (ops/crontab.manifest is decommissioned and is not a root).
BOX_TASKS_REL = "desks/mt5/ops/box_tasks.manifest"
VPS_UNITS_REL = "ops"
CYCLE_ROOTS = ("desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py")
#: Audit clock texts that name no clock.
NO_CLOCK = re.compile(r"^\s*(none\b|n/?a\b|see dedicated rows|law\b|-+\s*$)", re.IGNORECASE)
AUDIT_ID_PREFIX = "ASIA-"
#: Text kept per imported row, so the vendored file stays small enough to read every hour.
IMPORT_TEXT_CHARS = 400
IMPORT_EVIDENCE_CHARS = 240
#: Region from the requirement's own words (first match wins); GLOBAL otherwise.
REGION_WORDS: tuple[tuple[str, str], ...] = (
    ("JP", r"\bjapan|\bjpx\b|\bboj\b|\bjgb\b|j.?quants|\btse\b|\btocom\b|\bosaka\b|\bnikkei"),
    ("KR", r"\bkorea|\bkrx\b|\bbok\b|\becos\b|\bkospi|\bnaver\b"),
    ("HK", r"\bhong kong|\bhkma\b|\bhibor\b|\bhkex\b|\bhang seng|\bcnh\b|stock connect"),
    ("SG", r"\bsingapore|\bsgx\b|\bmas\b"),
    ("TW", r"\btaiwan|\btwse\b|\btaifex\b"),
    ("CN", r"\bchin|\bpboc\b|\bsafe\b|\bcfets\b|\bsge\b|\bshanghai|\bshfe\b|\bine\b|\bdce\b"
           r"|\bczce\b|\bgfex\b|\bcffex\b|\bnbs\b|\bcny\b|\brmb\b|\byuan\b|\bbaidu\b|\bcustoms\b"
           r"|\bdr007\b|\bshibor\b|tianyancha|\bweibo\b|\bwechat\b"),
    ("ASIA", r"\basia|\basean\b|\bindia|\bindonesia|\bmalaysia|\bthai|\bvietnam|\bphilippin"),
)
#: WIRED is reachability from a scheduler root through imports and runner paths. The code files
#: the graph is built over (tests, data and vendored trees are not code that runs on a clock).
CODE_SUFFIXES = (".py", ".sh", ".ps1")
GRAPH_SKIP_PARTS = frozenset({".git", "tests", "node_modules", "__pycache__", ".venv", "venv",
                              "intelligence", "lake", "site-packages"})
GRAPH_SKIP_PREFIXES = ("desks/mt5/data/", "data/")
#: Where a bare `import x` / `from a.b import c` is resolved from: the repo root and the paths the
#: desk's modules put on sys.path themselves (desks/mt5 and its research directory), plus the
#: importing file's own directory.
IMPORT_BASES = ("", "desks/mt5/", "desks/mt5/research/")
#: A path a runner names (`_producer("x", "research/pack_cells.py")`, an ExecStart, a task's runs=).
PATH_MENTION = re.compile(r"[A-Za-z0-9_.:/\\-]*[A-Za-z0-9_-]+\.(?:py|sh|ps1)\b")
#: ROI proof: a forest's ROI is read as an adequate sample only past this many routed trials.
ROI_MIN_TRIALS = 30
#: Rotation proof thresholds, declared: across the trailing window the non-English share of
#: attempts must be at least this, at least this many non-English languages must be attempted,
#: and the window must reach more distinct grounds than its largest single run (it moved).
ROTATION_WINDOW_H = 48.0
ROTATION_MIN_NON_EN_SHARE = 0.25
ROTATION_MIN_NON_EN_LANGUAGES = 3
#: The evidence window for the EVIG and ROI decision ledgers.
DECISION_WINDOW_H = 72.0
TAIL_BYTES = 4 * 1024 * 1024
#: The in-file timestamp fields freshness is read from (first present wins). File mtime is never
#: used: a checkout, a copy or a sync rewrites it without the organ having run.
STAMP_KEYS = ("generated_at", "generated_utc", "at", "updated_at", "written_at", "as_of", "ts",
              "fetched_utc", "ingested_time")
#: Rows read when a shared artifact is filtered to one requirement's rows; above this the count is
#: UNMEASURED rather than a partial read presented as whole.
ATTRIBUTION_MAX_BYTES = 64 * 1024 * 1024
#: The per-requirement row filter. A requirement's own words pick ONE dimension, most specific
#: first: the language it names (only when the text is about language), else the countries its
#: text and its owner modules (`countries/<cc>/`) name, else its region. A row of a shared artifact
#: is that requirement's only when one of the dimension's fields carries one of its values.
LANGUAGE_CONTEXT = re.compile(r"language|native|lingu", re.IGNORECASE)
LANGUAGES = {
    "german": "de", "dutch": "nl", "french": "fr", "spanish": "es", "italian": "it",
    "portuguese": "pt", "russian": "ru", "japanese": "ja", "korean": "ko", "chinese": "zh",
    "mandarin": "zh", "cantonese": "zh", "vietnamese": "vi", "thai": "th", "indonesian": "id",
    "malay": "ms", "hindi": "hi", "arabic": "ar", "turkish": "tr", "polish": "pl",
    "swedish": "sv", "norwegian": "no", "danish": "da", "finnish": "fi", "hebrew": "he",
    "persian": "fa", "farsi": "fa", "greek": "el", "czech": "cs", "hungarian": "hu",
    "romanian": "ro", "ukrainian": "uk", "tagalog": "tl", "filipino": "tl", "bengali": "bn",
    "urdu": "ur", "swahili": "sw"}
COUNTRIES = {
    "china": "cn", "chinese": "cn", "japan": "jp", "japanese": "jp", "korea": "kr",
    "korean": "kr", "hong kong": "hk", "singapore": "sg", "taiwan": "tw", "india": "in",
    "indonesia": "id", "malaysia": "my", "thailand": "th", "vietnam": "vn", "philippines": "ph",
    "germany": "de", "german": "de", "netherlands": "nl", "dutch": "nl", "france": "fr",
    "united kingdom": "gb", "britain": "gb", "switzerland": "ch", "swiss": "ch", "italy": "it",
    "spain": "es", "australia": "au", "canada": "ca", "brazil": "br", "mexico": "mx",
    "south africa": "za", "russia": "ru", "turkey": "tr", "saudi": "sa", "norway": "no",
    "sweden": "se", "denmark": "dk", "poland": "pl", "nigeria": "ng", "chile": "cl",
    "new zealand": "nz", "pakistan": "pk", "ukraine": "ua"}
REGION_VALUES = {"CN": ("cn", "china"), "JP": ("jp", "japan"), "KR": ("kr", "korea"),
                 "HK": ("hk", "hong_kong", "hong kong"), "SG": ("sg", "singapore"),
                 "TW": ("tw", "taiwan")}
FILTER_FIELDS = {"language": ("language", "lang"),
                 "country": ("country", "country_code", "cc", "iso2", "region"),
                 "region": ("region", "forest", "country", "country_code")}

ASIA_COUNTRIES = {
    "cn": "China", "jp": "Japan", "kr": "Korea", "hk": "HK", "sg": "SG", "tw": "Taiwan"}
OTHER_ASIA = {"in", "id", "my", "th", "vn", "ph", "mo", "kh", "bd", "pk", "lk", "mn", "la", "mm"}
CATEGORY_PLANES = {
    "physical economy": ("physical", "physical_gold", "cn_hard"),
    "participant data": ("participant", "venue", "genome"),
    "supply chain": ("supply_chain", "customs_micro"),
    "logistics": ("logistics",),
    "geospatial": ("geospatial",),
    "search attention": ("search",),
}
OK_COLLECTOR = ("COLLECTED", "UNCHANGED", "NOT_MODIFIED")


# ------------------------------------------------------------------------------------ reading
class Reader:
    """Every artifact read once per pass, with its age. A miss is recorded, never raised."""

    def __init__(self, root: Path, now: float | None = None) -> None:
        self.root = root
        self.now = time.time() if now is None else float(now)
        self._json: dict[str, Any] = {}
        self._text: dict[str, str | None] = {}
        self.memo: dict[str, Any] = {}

    def path(self, rel: str) -> Path:
        return self.root / rel

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists() or bool(ledger_files(self.path(rel)))

    def stamp(self, rel: str) -> datetime | None:
        """The artifact's OWN timestamp: a JSON document's generated_at (or the first STAMP_KEYS
        field it carries), a JSON-lines ledger's newest row stamp. A table with no stamp field,
        or a document that carries none, has no measured freshness -- None, never the file's
        mtime (a checkout, a sync or a copy rewrites that without the organ having run)."""
        key = f"stamp:{rel}"
        if key in self.memo:
            got = self.memo[key]
            return got if isinstance(got, datetime) else None
        out: datetime | None = None
        suffix = self.path(rel).suffix.lower()
        if suffix == ".jsonl":
            stamps = [s for s in (_row_stamp(r) for r in self.jsonl_tail(rel, 512 * 1024)[-500:])
                      if s is not None]
            out = max(stamps) if stamps else None
        elif suffix == ".json":
            doc = self.json(rel)
            if isinstance(doc, list) and doc and isinstance(doc[-1], dict):
                doc = doc[-1]
            out = _row_stamp(doc) if isinstance(doc, dict) else None
        self.memo[key] = out
        return out

    def age_h(self, rel: str) -> float | None:
        st = self.stamp(rel)
        return None if st is None else max(0.0, (self.now - st.timestamp()) / 3600.0)

    def json(self, rel: str) -> Any:
        if rel not in self._json:
            try:
                self._json[rel] = json.loads(self.path(rel).read_text("utf-8", errors="replace"))
            except (OSError, ValueError):
                self._json[rel] = None
        return self._json[rel]

    def text(self, rel: str) -> str | None:
        if rel not in self._text:
            try:
                self._text[rel] = self.path(rel).read_text("utf-8", errors="replace")
            except OSError:
                self._text[rel] = None
        return self._text[rel]

    def jsonl_tail(self, rel: str, nbytes: int = TAIL_BYTES) -> list[dict[str, Any]]:
        """The newest `nbytes` of a JSON-lines ledger, ACROSS ITS ROTATED ARCHIVES: a ledger that
        outgrew its bound was moved whole to `<stem>.<stamp>.jsonl`, and a window straddling the
        rotation reads both. What was read is recorded in memo["tail:<rel>"] so a proof can say
        whether its read was complete."""
        files = ledger_files(self.path(rel))
        budget = nbytes
        chunks: list[list[str]] = []
        read: list[str] = []
        complete = True
        for p in reversed(files):
            if budget <= 0:
                complete = False
                break
            try:
                with p.open("rb") as fh:
                    size = fh.seek(0, os.SEEK_END)
                    fh.seek(max(0, size - budget))
                    raw = fh.read()
            except OSError:
                complete = False
                continue
            part = raw.decode("utf-8", errors="replace").splitlines()
            if size > budget and part:
                part = part[1:]                     # the first line may be cut mid-row
                complete = False
            chunks.insert(0, part)
            read.insert(0, p.name)
            budget -= len(raw)
        self.memo[f"tail:{rel}"] = {"files_read": read, "files_total": len(files),
                                    "complete": complete and len(read) == len(files)}
        lines = [line for part in chunks for line in part]
        out: list[dict[str, Any]] = []
        for line in lines:
            with contextlib.suppress(ValueError):
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
        return out


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dig(doc: Any, dotted: str) -> Any:
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (datetime.fromtimestamp(float(value), tz=UTC)
                if 1e9 <= float(value) <= 1e10 else None)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _row_stamp(row: dict[str, Any]) -> datetime | None:
    for k in STAMP_KEYS:
        if k in row:
            got = _ts(row.get(k))
            if got is not None:
                return got
    return None


def _rows_in(rd: Reader, rel: str) -> int | None:
    """Row count of a parquet / jsonl / csv artifact; None when it cannot be counted here."""
    p = rd.path(rel)
    if not p.exists():
        return None
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
            return int(pq.ParquetFile(p).metadata.num_rows)
        except Exception:
            try:
                import pandas as pd
                return len(pd.read_parquet(p))
            except Exception:
                return None
    if suffix in (".jsonl", ".csv"):
        n = 0
        try:
            for f in (ledger_files(p) if suffix == ".jsonl" else [p]):
                with f.open("rb") as fh:
                    n += sum(1 for line in fh if line.strip())
        except OSError:
            return None
        return max(0, n - (1 if suffix == ".csv" else 0))
    doc = rd.json(rel)
    return _count(doc) if doc is not None else None


# ------------------------------------------------------------------------------ static rungs
class Reach:
    """WHICH CODE A SCHEDULER ACTUALLY RUNS. Built once per pass over the tree's code files.

    Edges are what makes one file run another: a Python import (absolute, relative, or an
    `importlib.import_module("a.b")` literal), or a path to a .py/.sh/.ps1 named in a string a
    runner executes (`_producer("x", "research/pack_cells.py")`, an ExecStart, a task's runs=).
    Docstrings and comments are not edges. Roots are the clocks: hourly_cycle.py, daily_cycle.py,
    every box task's runs=/organ= in BOX_TASKS_REL, and every VPS timer's service ExecStart.
    A dynamic import built from a variable is not traceable and is NOT credited -- an owner
    reached only that way reads CODED, the lower rung, never WIRED by guess."""

    def __init__(self, rd: Reader) -> None:
        self.rd = rd
        self.files: set[str] = set()
        for suffix in CODE_SUFFIXES:
            for f in rd.root.rglob(f"*{suffix}"):
                rel = f.relative_to(rd.root).as_posix()
                if GRAPH_SKIP_PARTS.intersection(f.relative_to(rd.root).parts):
                    continue
                if rel.startswith(GRAPH_SKIP_PREFIXES):
                    continue
                self.files.add(rel)
        self.roots: dict[str, str] = {}
        self._roots()
        self.reached: dict[str, str] = self._walk()

    # -- resolution
    def _path(self, mention: str, importer: str) -> str | None:
        m = mention.replace("\\", "/").strip().lstrip("./") if mention else ""
        if not m:
            return None
        here = importer.rsplit("/", 1)[0] + "/" if "/" in importer else ""
        if "/" not in m:
            return here + m if here + m in self.files else None
        for base in ("", "desks/mt5/", here):
            if base + m in self.files:
                return base + m
        parts = m.split("/")
        for i in range(1, len(parts) - 1):            # an absolute path: the repo-relative tail
            tail = "/".join(parts[i:])
            if tail in self.files:
                return tail
        return None

    def _module(self, dotted: str, importer: str) -> list[str]:
        here = importer.rsplit("/", 1)[0] + "/" if "/" in importer else ""
        rel = dotted.replace(".", "/")
        out = []
        for base in (*IMPORT_BASES, here):
            for cand in (f"{base}{rel}.py", f"{base}{rel}/__init__.py"):
                if cand in self.files and cand not in out:
                    out.append(cand)
        return out

    # -- edges
    def edges(self, rel: str) -> set[str]:
        key = f"edges:{rel}"
        if key in self.rd.memo:
            return set(self.rd.memo[key])
        src = self.rd.text(rel) or ""
        out: set[str] = set()
        if rel.endswith(".py"):
            out |= self._py_edges(rel, src)
        else:
            for line in src.splitlines():
                if line.lstrip().startswith(("#", "<#", "REM ")):
                    continue
                for m in PATH_MENTION.findall(line):
                    hit = self._path(m, rel)
                    if hit:
                        out.add(hit)
        out.discard(rel)
        self.rd.memo[key] = sorted(out)
        return out

    def _py_edges(self, rel: str, src: str) -> set[str]:
        out: set[str] = set()
        try:
            tree = ast.parse(src)
        except (SyntaxError, ValueError):
            return out
        pkg = rel.rsplit("/", 1)[0] if "/" in rel else ""
        docstrings: set[int] = set()
        for node in ast.walk(tree):                 # breadth-first: a def precedes its body
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) \
                        and isinstance(body[0].value, ast.Constant) \
                        and isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))
                continue
            if isinstance(node, ast.Import):
                for a in node.names:
                    out.update(self._module(a.name, rel))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = pkg.split("/") if pkg else []
                    base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                    prefix = "/".join(base)
                    stem = (node.module or "").replace(".", "/")
                    mod = "/".join(x for x in (prefix, stem) if x)
                    for a in node.names:
                        for cand in (f"{mod}/{a.name}.py", f"{mod}.py", f"{mod}/__init__.py"):
                            if cand in self.files:
                                out.add(cand)
                    continue
                if not node.module:
                    continue
                out.update(self._module(node.module, rel))
                for a in node.names:
                    out.update(self._module(f"{node.module}.{a.name}", rel))
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name == "import_module" and node.args \
                        and isinstance(node.args[0], ast.Constant) \
                        and isinstance(node.args[0].value, str):
                    out.update(self._module(node.args[0].value, rel))
                elif _is_runner(node, name):
                    # A path RUN: handed to a runner (_producer, subprocess, run_path, a spec
                    # loader, a battery entry). A path a module merely READS (an auditor's list of
                    # files to scan) is not an edge -- reading a file is not running it.
                    for s in _arg_strings([*node.args, *(k.value for k in node.keywords)]):
                        for m in PATH_MENTION.findall(s):
                            hit = self._path(m, rel)
                            if hit:
                                out.add(hit)
            elif isinstance(node, ast.JoinedStr):
                # A loader that builds its target from a variable (f"research.countries.{c}.pack",
                # f"{root}/{code}/pack.py") reaches every file of that SHAPE -- the pattern's literal
                # segments must all match; a bare "{x}" names nothing and reaches nothing.
                pat = "".join(str(v.value) if isinstance(v, ast.Constant) else "*"
                              for v in node.values if isinstance(v, (ast.Constant,
                                                                     ast.FormattedValue)))
                out.update(self._glob(pat, rel))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in docstrings:
                if "*" in node.value:
                    out.update(self._glob(node.value.strip(), rel))
                elif rel in self.roots and "." in node.value:
                    # A SCHEDULER ROOT is a dispatcher: the scripts its tables name (the law
                    # gate's fence list, a cycle's leg table) are what it runs.
                    for m in PATH_MENTION.findall(node.value):
                        hit = self._path(m, rel)
                        if hit:
                            out.add(hit)
        return out

    def _glob(self, pat: str, importer: str) -> set[str]:
        """Files a wildcard path (`*/pack.py`, under the importer's directory or a base) or a
        wildcard dotted module (`research.countries.*.pack`) names."""
        if "*" not in pat or len(pat.replace("*", "")) < 4:
            return set()
        # The LAST segment must be literal: `*/pack.py` and `countries.*.pack` are loaders of one
        # named file per directory; `*.py` / `research.*` are code scanners (auditors that read
        # every file), and reading a file is not running it.
        last = re.split(r"[./\\]", pat[:-3] if pat.endswith(".py") else pat)[-1]
        if not last or "*" in last or last == "__init__":
            return set()
        here = importer.rsplit("/", 1)[0] + "/" if "/" in importer else ""
        if re.fullmatch(r"[\w*]+(\.[\w*]+)+", pat) and not pat.endswith((".py", ".*")):
            if not re.search(r"[A-Za-z_]\w*\.", pat.split("*", 1)[0]):
                return set()                       # no literal package before the wildcard
            rel = pat.replace(".", "/")
            pats = [f"{b}{rel}.py" for b in (*IMPORT_BASES, here)]
            pats += [f"{b}{rel}/__init__.py" for b in (*IMPORT_BASES, here)]
        elif pat.replace("\\", "/").endswith(".py") and re.fullmatch(r"[\w*./\\-]+", pat):
            rel = pat.replace("\\", "/").lstrip("./")
            if "/" not in rel:
                return set()                       # "*.py" alone names no shape
            pats = [f"{b}{rel}" for b in ("", "desks/mt5/", here)]
            pats += [f"{here}*/{rel}"] if rel.startswith("*/") else []
        else:
            return set()
        key = "glob:" + "|".join(pats)
        if key not in self.rd.memo:
            self.rd.memo[key] = sorted(f for f in self.files
                                       if any(fnmatch.fnmatchcase(f, q) for q in pats))
        return set(self.rd.memo[key])

    # -- roots and the walk
    def _roots(self) -> None:
        for r in CYCLE_ROOTS:
            if r in self.files:
                self.roots[r] = Path(r).stem
        for name, values in box_tasks(self.rd).items():
            for m in (m for v in values for m in PATH_MENTION.findall(v)):
                hit = self._path(m, BOX_TASKS_REL)
                if hit:
                    self.roots.setdefault(hit, f"box task {name}")
        for unit, execs in vps_timer_services(self.rd).items():
            for m in execs:
                hit = self._path(m, f"{VPS_UNITS_REL}/{unit}")
                if hit:
                    self.roots.setdefault(hit, f"VPS timer {unit}")

    def _walk(self) -> dict[str, str]:
        seen = dict(self.roots)
        todo = list(self.roots)
        while todo:
            cur = todo.pop(0)
            for nxt in self.edges(cur):
                if nxt not in seen:
                    seen[nxt] = seen[cur]
                    todo.append(nxt)
        return seen

    def root_of(self, rel: str) -> str | None:
        return self.reached.get(rel)


#: Calls that RUN the path they are handed (the hourly cycle's _producer, subprocess, runpy, the
#: spec loader, a battery entry `_e(path, ...)`, the desk's own subprocess wrappers).
RUNNER_CALLS = frozenset({
    "_producer", "run", "Popen", "call", "check_call", "check_output", "run_path",
    "spec_from_file_location", "run_cmd", "_srun", "_run", "_run_logged", "_spawn",
    "_subprocess_cap", "_load_by_path", "script_actuator", "_e", "execv", "execvp", "system"})


def _arg_strings(exprs: Iterable[ast.expr], depth: int = 0) -> list[str]:
    """The string literals a call's arguments carry: direct, in a list/tuple, in a `ROOT / "x.py"`
    join, or wrapped in str()/Path() -- not the bodies of lambdas or nested runners."""
    out: list[str] = []
    if depth > 4:
        return out
    for e in exprs:
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            out.append(e.value)
        elif isinstance(e, (ast.List, ast.Tuple)):
            out += _arg_strings(e.elts, depth + 1)
        elif isinstance(e, ast.BinOp):
            out += _arg_strings([e.left, e.right], depth + 1)
        elif isinstance(e, ast.Starred):
            out += _arg_strings([e.value], depth + 1)
        elif isinstance(e, ast.Call):
            out += _arg_strings(e.args, depth + 1)
    return out


def _is_runner(node: ast.Call, name: str) -> bool:
    if name in RUNNER_CALLS:
        return True
    for a in node.args:
        if isinstance(a, ast.Attribute) and a.attr == "executable":
            return True                                  # [sys.executable, "x.py", ...]
        if isinstance(a, (ast.List, ast.Tuple)) and any(
                (isinstance(e, ast.Attribute) and e.attr == "executable")
                or (isinstance(e, ast.Constant) and isinstance(e.value, str)
                    and re.match(r"(python|pwsh|powershell)", e.value)) for e in a.elts):
            return True
    return False


def box_tasks(rd: Reader) -> dict[str, list[str]]:
    """{task name: [runs=, organ=]} from the box's task manifest."""
    if "box_tasks" not in rd.memo:
        out: dict[str, list[str]] = {}
        for line in (rd.text(BOX_TASKS_REL) or "").splitlines():
            if not line.startswith("TASK "):
                continue
            kv = dict(re.findall(r'(\w+)="([^"]*)"', line))
            if kv.get("name"):
                out[kv["name"]] = [v for k, v in kv.items() if k in ("runs", "organ") and v]
        rd.memo["box_tasks"] = out
    return dict(rd.memo["box_tasks"])


def vps_timer_services(rd: Reader) -> dict[str, list[str]]:
    """{timer unit: [paths its service's ExecStart names]} for every ops/*.timer."""
    if "vps_timers" not in rd.memo:
        out: dict[str, list[str]] = {}
        base = rd.path(VPS_UNITS_REL)
        for timer in sorted(base.glob("*.timer")) if base.is_dir() else []:
            txt = rd.text(f"{VPS_UNITS_REL}/{timer.name}") or ""
            unit = re.search(r"^Unit\s*=\s*(\S+)", txt, re.MULTILINE)
            svc = unit.group(1) if unit else f"{timer.stem}.service"
            stxt = rd.text(f"{VPS_UNITS_REL}/{svc}") or ""
            execs = [m for line in stxt.splitlines() if line.strip().startswith("ExecStart")
                     for m in PATH_MENTION.findall(line)]
            out[timer.name] = execs
        rd.memo["vps_timers"] = out
    return dict(rd.memo["vps_timers"])


def audit_clock_found(rd: Reader, text: str) -> bool:
    """An audit-named clock is found only when it names a clock this tree can confirm."""
    if not text.strip() or NO_CLOCK.match(text):
        return False
    toks = set(re.findall(r"[A-Za-z0-9_.-]+", text))
    if toks & set(box_tasks(rd)):
        return True
    timers = {t.rsplit(".", 1)[0] for t in vps_timer_services(rd)}
    if toks & (timers | {f"{t}.timer" for t in timers}):
        return True
    if toks & hourly_legs(rd.text(SCHEDULER_FILES["hourly"]) or ""):
        return True
    if "daily_cycle" in toks:
        dsrc = rd.text(SCHEDULER_FILES["daily"]) or ""
        return any(f'"{tk}"' in dsrc or f"'{tk}'" in dsrc for tk in toks - {"daily_cycle"})
    return False


def scheduler_found(rd: Reader, entry: str) -> bool:
    kind, _, name = entry.partition(":")
    if kind == "audit":
        return audit_clock_found(rd, name)
    rel = SCHEDULER_FILES.get(kind)
    src = rd.text(rel) if rel else None
    if not src or not name:
        return False
    if kind == "hourly":
        return (f'_costed("{name}"' in src) or (f"_costed('{name}'" in src)
    if kind in ("battery", "fence"):
        return Path(name).name in src
    return f'"{name}"' in src or f"'{name}'" in src


def static_rung(rd: Reader, row: dict[str, Any], reach: Reach) -> tuple[str, list[str]]:
    """ABSENT -> CODED -> WIRED -> SCHEDULED, each rung earned on top of the one below.

    WIRED: EVERY existing code owner is reachable from a scheduler root (Reach), traced through
    imports and runner paths -- "some module imports it" is not wiring. SCHEDULED: WIRED, AND
    every declared clock is found (a partial clock is not a schedule; an audit-named clock must
    name a task, timer, leg or daily entry this tree confirms)."""
    why: list[str] = []
    if row.get("hold_absent"):
        return "ABSENT", ["the project completion audit found this ABSENT and no code marker in "
                          "the tree lifts it (a module that merely exists nearby is not the "
                          "requirement)"]
    owners = [str(o) for o in row.get("owner") or []]
    if not owners:
        return "ABSENT", ["no owner module is named: nothing in the tree claims this requirement"]
    missing = [o for o in owners if not rd.path(o).exists()]
    if len(missing) == len(owners):
        return "ABSENT", [f"owner module(s) absent: {', '.join(missing)}"]
    if missing:
        why.append(f"owner module(s) absent: {', '.join(missing)}")
    for m in row.get("code_markers") or []:
        src = rd.text(str(m.get("path"))) or ""
        if str(m.get("contains", "")).lower() not in src.lower():
            return "ABSENT", [*why, f"code marker {m.get('contains')!r} absent from {m.get('path')}"]
    code = [o for o in owners if o not in missing and o.endswith(CODE_SUFFIXES)]
    unreached = [o for o in code if reach.root_of(o) is None]
    if not code:
        return "CODED", [*why, "no owner is executable code: nothing a scheduler could run"]
    if unreached:
        return "CODED", [*why, f"not reachable from any scheduler root (hourly_cycle, daily_cycle, "
                               f"a box task, a VPS timer) through imports or runner paths: "
                               f"{', '.join(unreached)}"]
    why.append("reached from " + ", ".join(sorted({str(reach.root_of(o)) for o in code})))
    sched = [str(s) for s in row.get("scheduler") or []]
    found = [s for s in sched if scheduler_found(rd, s)]
    if sched and len(found) == len(sched):
        return "SCHEDULED", [*why, f"clock(s): {', '.join(found)}"]
    if found:
        why.append(f"PARTIAL clock: found {found}, missing {sorted(set(sched) - set(found))} -- "
                   "a partial clock is not SCHEDULED")
    else:
        why.append(f"no declared clock is confirmed ({', '.join(sched) or 'none declared'})")
    return "WIRED", why


# ----------------------------------------------------------------------------------- probes
def _blank(rel: str, rd: Reader) -> dict[str, Any]:
    age = rd.age_h(rel)
    return {"artifact": rel, "present": rd.exists(rel),
            "age_h": round(age, 3) if age is not None else None,
            "age_basis": "in-file timestamp" if age is not None else UNMEASURED,
            "data": None, "cells": None, "judged": None, "survivors": None,
            "blocked": None, "notes": []}


def probe_pack_cells(rd: Reader, p: dict[str, Any]) -> dict[str, Any]:
    out = _blank(p["artifact"], rd)
    doc = rd.json(p["artifact"])
    if not isinstance(doc, dict):
        return out
    rows = {str(r.get("id")): r for r in doc.get("rows") or [] if isinstance(r, dict)}
    seen = [rows[i] for i in p.get("ids") or [] if i in rows]
    absent = [i for i in p.get("ids") or [] if i not in rows]
    if absent:
        out["notes"].append(f"not in PACK_CELLS rows: {', '.join(absent)}")
    if not seen:
        return out
    stages = Counter(str(r.get("stage") or UNMEASURED) for r in seen)
    out["notes"].append("chain stages " + ", ".join(f"{k}={v}" for k, v in sorted(stages.items())))
    if all(str(r.get("stage")) == "unmeasured" for r in seen):
        return out
    out["data"] = sum(int(r.get("n_rows") or 0) for r in seen)
    out["cells"] = sum(int(r.get("cells_emitted") or 0) for r in seen)
    out["judged"] = sum(int(r.get("cells_judged") or 0) for r in seen)
    return out


def probe_collector(rd: Reader, p: dict[str, Any]) -> dict[str, Any]:
    out = _blank(p["artifact"], rd)
    doc = rd.json(p["artifact"])
    if not isinstance(doc, dict):
        return out
    rows = {str(r.get("id")): r for r in doc.get("rows") or [] if isinstance(r, dict)}
    st = {i: str((rows.get(i) or {}).get("status") or "NOT_ATTEMPTED") for i in p.get("ids") or []}
    out["notes"].append("collector " + ", ".join(f"{k}={v}" for k, v in sorted(st.items())))
    blocked = [f"{k}:{v}" for k, v in st.items()
               if v.startswith("BLOCKED") or v == "UNCONFIGURED"]
    if blocked and len(blocked) == len(st):
        out["blocked"] = "; ".join(blocked)
    # Bytes collected from a landing page are not data: the collector only proves the clock ran.
    return out


def probe_alt_proxies(rd: Reader, p: dict[str, Any]) -> dict[str, Any]:
    out = _blank(p["artifact"], rd)
    doc = rd.json(p["artifact"])
    if not isinstance(doc, dict):
        return out
    recs = {str(r.get("id")): r for r in doc.get("sources") or [] if isinstance(r, dict)}
    ids = list(recs) if p.get("ids") == ["*"] else list(p.get("ids") or [])
    have = [i for i in ids if i in recs]
    if not have:
        out["notes"].append(f"no ALT_PROXIES source row for {', '.join(ids)}: the code holds none")
        return out
    out["data"] = sum(int(recs[i].get("store_rows") or 0) for i in have)
    gains = _dict(doc.get("gain_tests"))
    keys = [k for k in gains if str(k).split("|", 1)[0] in set(have)]
    out["cells"] = len(keys)
    # UNDERPOWERED is the judge declining to rule for want of sample: a cell, not a judgement.
    tested = ("PASS", "FAIL")
    out["judged"] = sum(1 for k in keys if (gains[k] or {}).get("verdict") in tested)
    under = sum(1 for k in keys if (gains[k] or {}).get("verdict") == "UNDERPOWERED")
    if under:
        out["notes"].append(f"{under} gain test(s) UNDERPOWERED: emitted, not judged")
    out["survivors"] = sum(1 for k in keys if (gains[k] or {}).get("verdict") == "PASS")
    statuses = {i: str(recs[i].get("status") or "") for i in have}
    out["notes"].append("alt_proxies " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
    blocked = [f"{k}:{v}" for k, v in statuses.items()
               if v.startswith(("BLOCKED", "UNCONFIGURED", "DEAD"))]
    if blocked and len(blocked) == len(have) and not out["data"]:
        out["blocked"] = "; ".join(blocked)
    return out


def probe_free_stack(rd: Reader, p: dict[str, Any]) -> dict[str, Any]:
    out = _blank(p["artifact"], rd)
    doc = rd.json(p["artifact"])
    if not isinstance(doc, dict):
        return out
    per = _dict(doc.get("per_source"))
    have = [i for i in p.get("ids") or [] if i in per]
    if not have:
        out["notes"].append(f"no free-stack roster row for {', '.join(p.get('ids') or [])}")
        return out
    obs = [per[i].get("obs_total") for i in have]
    known = [int(v) for v in obs if isinstance(v, int)]
    out["data"] = sum(known) if known else None
    statuses = {i: str(per[i].get("status") or UNMEASURED) for i in have}
    out["notes"].append("free_stack " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
    blocked = [f"{k}:{v}" for k, v in statuses.items()
               if any(w in v for w in ("BLOCKED", "UNCONFIGURED", "REFUSED"))]
    if blocked and len(blocked) == len(have) and not out["data"]:
        out["blocked"] = "; ".join(blocked)
    # Cells are minted by the proposer at SEAT level; credited here only when this row's sources
    # carry columns the proposer reads, and labelled as seat attribution.
    prop = rd.json("desks/mt5/reports/FREE_STACK_PROPOSER.json")
    cols = sum(int(per[i].get("columns") or 0) for i in have)
    if isinstance(prop, dict) and cols > 0 and isinstance(prop.get("minted"), int):
        out["cells"] = int(prop["minted"])
        out["notes"].append("cells are the free_stack_proposer seat's minted count (seat attribution)")
    return out


def probe_asia_plane(rd: Reader, p: dict[str, Any]) -> dict[str, Any]:
    out = _blank(p["artifact"], rd)
    doc = rd.json(p["artifact"])
    if not isinstance(doc, dict):
        return out
    per = _dict(doc.get("cells_per_source"))
    ids = list(per) if p.get("ids") == ["*"] else list(p.get("ids") or [])
    out["cells"] = sum(int(per.get(i) or 0) for i in ids)
    out["notes"].append("price-only expression cells under hard-source names (proxy)")
    return out


def requirement_filter(row: dict[str, Any]) -> dict[str, Any] | None:
    """The row filter that makes a shared artifact's rows THIS requirement's (see FILTER_FIELDS).
    None when the requirement's text, modules and region name no language, country or region."""
    text = f"{row.get('title') or ''} {row.get('source') or ''}"
    low = text.lower()
    if LANGUAGE_CONTEXT.search(text):
        langs = sorted({c for w, c in LANGUAGES.items() if re.search(rf"\b{w}\b", low)})
        if langs:
            return {"dimension": "language", "values": langs,
                    "basis": "the language the requirement names"}
    ccs = {c for w, c in COUNTRIES.items() if re.search(rf"\b{w}\b", low)}
    for o in row.get("owner") or []:
        m = re.search(r"/countries/([a-z]{2})/", str(o))
        if m:
            ccs.add(m.group(1))
    if ccs:
        return {"dimension": "country", "values": sorted(ccs),
                "basis": "the countries the requirement's text and owner modules name"}
    region = str(row.get("region") or "")
    if region in REGION_VALUES:
        return {"dimension": "region", "values": list(REGION_VALUES[region]),
                "basis": f"the requirement's region {region}"}
    return None


def _records(rd: Reader, rel: str, rows_key: str | None) -> list[dict[str, Any]] | None:
    """An artifact's rows as dicts, or None when it cannot be read whole as rows here."""
    p = rd.path(rel)
    suffix = p.suffix.lower()
    try:
        if suffix == ".jsonl":
            files = ledger_files(p)
            if sum(f.stat().st_size for f in files) > ATTRIBUTION_MAX_BYTES:
                return None
            out: list[dict[str, Any]] = []
            for f in files:
                for line in f.read_text("utf-8", errors="replace").splitlines():
                    with contextlib.suppress(ValueError):
                        row = json.loads(line)
                        if isinstance(row, dict):
                            out.append(row)
            return out
        if suffix == ".csv":
            if p.stat().st_size > ATTRIBUTION_MAX_BYTES:
                return None
            with p.open(encoding="utf-8", errors="replace", newline="") as fh:
                return [dict(r) for r in csv.DictReader(fh)]
        if suffix == ".parquet":
            try:
                import pyarrow.parquet as pq
                pf = pq.ParquetFile(p)
                cols = [c for fields in FILTER_FIELDS.values() for c in fields
                        if c in pf.schema_arrow.names]
                if not cols:
                    return [{} for _ in range(pf.metadata.num_rows)]
                return list(pf.read(columns=sorted(set(cols))).to_pylist())
            except Exception:
                return None
    except OSError:
        return None
    doc = rd.json(rel)
    if rows_key:
        doc = _dig(doc, rows_key)
    if isinstance(doc, list) and all(isinstance(r, dict) for r in doc):
        return list(doc)
    return None


def _matches(rec: dict[str, Any], flt: dict[str, Any]) -> bool:
    want = [str(v).lower() for v in flt["values"]]
    for f in FILTER_FIELDS[flt["dimension"]]:
        v = rec.get(f)
        if v is None:
            continue
        got = str(v).lower()
        if flt["dimension"] == "language":
            if any(got == w or got.startswith(w + "-") for w in want):
                return True
        elif got in want:
            return True
    return False


def attribute(rd: Reader, out: dict[str, Any], p: dict[str, Any], flt: dict[str, Any] | None,
              claimants: list[str]) -> dict[str, Any]:
    """A SHARED artifact's counts belong to a requirement only through its own filter.

    The artifact is named by several requirements (`claimants`). Its whole row count is no single
    one's evidence; only the rows the requirement's filter selects are. No filter, or rows that
    carry none of the filter's fields, and the probe is UNATTRIBUTED: it proves nothing for this
    row (UNMEASURED), never the whole artifact's count."""
    out = dict(out, notes=list(out["notes"]), shared_by=len(claimants))
    whole = out.get("data")
    out["cells"] = None                 # a shared cell count has no per-row filter at all
    if not out["present"]:
        return out
    if flt is None:
        out.update(data=None, unattributed=True)
        out["notes"].append(f"shared by {len(claimants)} requirements and no per-requirement "
                            "filter can be built from this row's text, modules or region: "
                            "UNMEASURED, not the artifact's whole count")
        return out
    recs = _records(rd, str(p["artifact"]), p.get("rows_key"))
    fields = FILTER_FIELDS[flt["dimension"]]
    if recs is None or not any(any(f in r for f in fields) for r in recs):
        out.update(data=None, unattributed=True)
        out["notes"].append(f"shared by {len(claimants)} requirements; its rows carry none of "
                            f"{list(fields)}, so the {flt['dimension']} filter "
                            f"{flt['values']} cannot be applied: UNMEASURED")
        return out
    n = sum(1 for r in recs if _matches(r, flt))
    out["data"] = n
    out["attribution"] = {"dimension": flt["dimension"], "values": flt["values"],
                          "basis": flt["basis"], "rows_matched": n, "rows_total": len(recs),
                          "whole_artifact_count": whole}
    out["notes"].append(f"{n} of {len(recs)} rows match {flt['dimension']} {flt['values']}")
    return out


def probe_artifact(rd: Reader, p: dict[str, Any]) -> dict[str, Any]:
    rel = str(p["artifact"])
    out = _blank(rel, rd)
    if not out["present"]:
        return out
    if rel.endswith((".parquet", ".jsonl", ".csv")):
        out["data"] = _rows_in(rd, rel)
        return out
    doc = rd.json(rel)
    if doc is None:
        out["notes"].append(f"{rel} is unreadable")
        return out
    if p.get("rows_key"):
        out["data"] = _count(_dig(doc, str(p["rows_key"])))
        if out["data"] is None:
            out["notes"].append(f"{rel} publishes no {p['rows_key']!r}")
    if p.get("cells_key"):
        out["cells"] = _count(_dig(doc, str(p["cells_key"])))
    return out


# ----------------------------------------------------------------------------------- proofs
def _within(rows: Iterable[dict[str, Any]], now: datetime, hours: float) -> list[dict[str, Any]]:
    since = now - timedelta(hours=hours)
    return [r for r in rows if (_ts(r.get("at")) or datetime.min.replace(tzinfo=UTC)) >= since]


def proof_evig_order(rd: Reader, rel: str, now: datetime) -> dict[str, Any]:
    """EVIG CHANGED WHAT WAS FETCHED, not only the order of a list.

    `source_evig.fetch_order` records every decision it makes for the collector: the due list in
    the order it arrived (`before`) and the order it handed back (`after`). The collector's own
    report then says which ids it reached and which it DEFERRED when the pass budget ran out. The
    counterfactual is the same budget spent in the `before` order: the ids fetched under EVIG that
    the registry order would have deferred are the position change attributable to EVIG. A pass
    whose budget never bound moved positions but changed no fetch, and is reported as such.
    """
    recs = _within(rd.jsonl_tail(rel), now, DECISION_WINDOW_H)
    if not recs:
        return {"proof": "evig_order", "verdict": UNMEASURED,
                "why": f"no EVIG order decision in {rel} within {DECISION_WINDOW_H:g}h on this host"}
    moved = [r for r in recs if int(r.get("moved") or 0) > 0]
    coll = rd.json(COLLECTOR_REL)
    measures: dict[str, Any] = {"decisions": len(recs), "decisions_that_moved_a_source": len(moved),
                                "positions_moved_total": sum(int(r.get("moved") or 0) for r in recs)}
    if not isinstance(coll, dict):
        return {"proof": "evig_order", "verdict": "NOT_PROVEN", "measures": measures,
                "why": f"decisions recorded but {COLLECTOR_REL} is absent: what the collector did "
                       "with the order is UNMEASURED"}
    c_at = _ts(coll.get("generated_utc"))
    prior = [r for r in recs if c_at is None or (_ts(r.get("at")) or c_at) <= c_at]
    last = prior[-1] if prior else recs[-1]
    rows = [r for r in coll.get("rows") or [] if isinstance(r, dict)]
    order = [str(r.get("id")) for r in rows]
    after = [str(i) for i in last.get("after") or [] if str(i) in set(order)]
    followed = order == after
    deferred = {str(r.get("id")) for r in rows if r.get("status") == "DEFERRED"}
    reached = [i for i in order if i not in deferred]
    before = [str(i) for i in last.get("before") or [] if str(i) in set(order)]
    cf_reached = set(before[:len(reached)])
    promoted = sorted(set(reached) - cf_reached)
    demoted = sorted(cf_reached - set(reached))
    measures.update({"collector_at": coll.get("generated_utc"), "decision_at": last.get("at"),
                     "collector_followed_evig_order": followed, "deferred": len(deferred),
                     "fetched_because_of_evig": promoted[:40],
                     "deferred_because_of_evig": demoted[:40],
                     "n_fetched_because_of_evig": len(promoted)})
    if not followed:
        return {"proof": "evig_order", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "the collector's realised order does not match the EVIG decision it was "
                       "handed: the consumer did not follow the ranking on its last pass"}
    if not deferred:
        return {"proof": "evig_order", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "EVIG moved positions but the pass budget never bound (0 DEFERRED), so no "
                       "fetch differed from registry order on the last pass"}
    if not promoted:
        return {"proof": "evig_order", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "the budget bound but the same ids were reached as registry order would reach"}
    return {"proof": "evig_order", "verdict": "PROVEN", "measures": measures,
            "why": f"{len(promoted)} source(s) were fetched only because EVIG ranked them ahead; "
                   f"{len(demoted)} that registry order would have fetched were deferred instead"}


def proof_roi_budget(rd: Reader, rel: str, now: datetime) -> dict[str, Any]:
    """ROI MOVED A FOREST'S BUDGET, AND THE FOREST RAN ON IT.

    `research_roi` records each allocation it writes beside the allocation a FLAT ROI would have
    produced (every region at the declared default) and the one it replaced. A forest whose
    ROI-only workers or seconds differ from the flat counterfactual, on a region with at least
    ROI_MIN_TRIALS routed trials (the adequate-sample clause of XLIV), is a budget ROI changed;
    `data/forest_runs.jsonl` then says whether that forest's next run used it.
    """
    recs = _within(rd.jsonl_tail(rel), now, DECISION_WINDOW_H)
    if not recs:
        return {"proof": "roi_budget", "verdict": UNMEASURED,
                "why": f"no ROI budget decision in {rel} within {DECISION_WINDOW_H:g}h on this host"}
    last = recs[-1]
    forests = _dict(last.get("forests"))
    changed = {f: r for f, r in forests.items() if isinstance(r, dict)
               and r.get("roi_only") is not None and r.get("roi_only") != r.get("flat")}
    adequate = {f: r for f, r in changed.items() if int(r.get("trials") or 0) >= ROI_MIN_TRIALS}
    measures: dict[str, Any] = {"decisions": len(recs), "decision_at": last.get("at"),
                                "forests_moved_by_roi": sorted(changed),
                                "forests_moved_with_adequate_sample": sorted(adequate),
                                "min_trials": ROI_MIN_TRIALS}
    if not changed:
        return {"proof": "roi_budget", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "every forest's allocation equals the flat-ROI counterfactual: ROI moved "
                       "no budget in the last decision"}
    if not adequate:
        return {"proof": "roi_budget", "verdict": "NOT_PROVEN", "measures": measures,
                "why": f"ROI moved {len(changed)} forest(s) but none has {ROI_MIN_TRIALS} routed "
                       "trials: the sample is not adequate yet (XLIV)"}
    d_at = _ts(last.get("at")) or now
    used: list[str] = []
    for run in rd.jsonl_tail(FOREST_RUNS_REL):
        fid = str(run.get("forest") or "")
        if fid not in adequate or (_ts(run.get("at")) or d_at) < d_at:
            continue
        alloc = _dict(run.get("allocation"))
        want = adequate[fid].get("after") or {}
        if alloc.get("workers") == want.get("workers"):
            used.append(fid)
    measures["forests_that_ran_on_the_roi_budget"] = sorted(set(used))
    if not used:
        return {"proof": "roi_budget", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "ROI moved an adequately-sampled forest's budget, but no forest run since "
                       f"the decision used it ({FOREST_RUNS_REL})"}
    return {"proof": "roi_budget", "verdict": "PROVEN", "measures": measures,
            "why": f"{len(set(used))} forest(s) ran on a budget their measured ROI moved away "
                   "from the flat default, on an adequate sample"}


def proof_forest_rotation(rd: Reader, rel: str, now: datetime) -> dict[str, Any]:
    """NATIVE-LANGUAGE SEARCH IS STILL ROTATING (XLIV), from the miner's own per-run ledger."""
    recs = _within(rd.jsonl_tail(rel), now, ROTATION_WINDOW_H)
    if not recs:
        return {"proof": "forest_rotation", "verdict": UNMEASURED,
                "why": f"no deep-forest run record in {rel} within {ROTATION_WINDOW_H:g}h"}
    by_lang: Counter[str] = Counter()
    grounds: set[str] = set()
    widest = 0
    for r in recs:
        for lang, n in (r.get("attempts_by_language") or {}).items():
            by_lang[str(lang or "unknown")] += int(n or 0)
        g = [str(x) for x in r.get("grounds") or []]
        grounds.update(g)
        widest = max(widest, len(g))
    total = sum(by_lang.values())
    non_en = {k: v for k, v in by_lang.items() if k != "en" and v > 0}
    share = (sum(non_en.values()) / total) if total else None
    measures = {"runs": len(recs), "attempts": total, "by_language": dict(by_lang.most_common()),
                "non_en_share": round(share, 4) if share is not None else None,
                "non_en_languages": sorted(non_en), "distinct_grounds": len(grounds),
                "widest_single_run": widest, "window_h": ROTATION_WINDOW_H,
                "thresholds": {"non_en_share": ROTATION_MIN_NON_EN_SHARE,
                               "non_en_languages": ROTATION_MIN_NON_EN_LANGUAGES}}
    if not total:
        return {"proof": "forest_rotation", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "runs were recorded but attempted no ground"}
    fails = []
    if (share or 0.0) < ROTATION_MIN_NON_EN_SHARE:
        fails.append(f"non-English share {share:.2f} < {ROTATION_MIN_NON_EN_SHARE}")
    if len(non_en) < ROTATION_MIN_NON_EN_LANGUAGES:
        fails.append(f"{len(non_en)} non-English language(s) < {ROTATION_MIN_NON_EN_LANGUAGES}")
    if len(recs) > 1 and len(grounds) <= widest:
        fails.append("the window reached no ground beyond its widest single run: not rotating")
    if fails:
        return {"proof": "forest_rotation", "verdict": "NOT_PROVEN", "measures": measures,
                "why": "; ".join(fails)}
    return {"proof": "forest_rotation", "verdict": "PROVEN", "measures": measures,
            "why": f"{len(non_en)} non-English languages carry {share:.0%} of {total} attempts "
                   f"over {len(recs)} runs and {len(grounds)} distinct grounds"}


PROOFS = {"evig_order": proof_evig_order, "roi_budget": proof_roi_budget,
          "forest_rotation": proof_forest_rotation}


def probe_proof(rd: Reader, p: dict[str, Any], now: datetime,
                cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = _blank(p["artifact"], rd)
    name = str(p.get("proof"))
    if name not in cache:
        fn = PROOFS.get(name)
        cache[name] = (fn(rd, str(p["artifact"]), now) if fn else
                       {"proof": name, "verdict": UNMEASURED, "why": f"unknown proof {name!r}"})
        tail = rd.memo.get(f"tail:{p['artifact']}")
        if tail:
            # The ledger rotates whole to dated archives; the proof read them too, and says so.
            cache[name]["ledger_read"] = dict(tail)
            if not tail.get("complete"):
                cache[name]["why"] = (f"{cache[name].get('why', '')} [read the newest "
                                      f"{TAIL_BYTES // (1024 * 1024)} MB across "
                                      f"{len(tail.get('files_read') or [])} of "
                                      f"{tail.get('files_total')} ledger file(s); older rows were "
                                      "not read]")
    res = cache[name]
    out["proof"] = res
    if out["present"]:
        out["data"] = _rows_in(rd, str(p["artifact"]))
    out["notes"].append(f"proof {name}: {res['verdict']} -- {res.get('why', '')}")
    return out


PROBES = {"pack_cells": probe_pack_cells, "collector": probe_collector,
          "alt_proxies": probe_alt_proxies, "free_stack": probe_free_stack,
          "asia_plane": probe_asia_plane, "artifact": probe_artifact}


# ------------------------------------------------------------------------------------ verdict
def _runtime_rows(rd: Reader) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    doc = rd.json(RUNTIME_REL)
    if not isinstance(doc, dict):
        return {}, {}
    rows = {str(r.get("organ")): r for r in doc.get("organs") or [] if isinstance(r, dict)}
    return rows, {"attests_to_host": doc.get("attests_to_host"),
                  "role": (doc.get("host") or {}).get("role"),
                  "generated_at": doc.get("generated_at")}


def _sum(vals: Iterable[int | None]) -> int | None:
    known = [int(v) for v in vals if v is not None]
    return sum(known) if known else None


def probe_ceiling(probes: list[dict[str, Any]]) -> str:
    """The highest rung a row's declared probes CAN measure. A generic JSON artifact proves the
    organ ran; a table proves data; only the pack chain and the gain tests see a judge; only a
    decision ledger proves a loop. Above its ceiling a row is never measured down, only
    left unconfirmed."""
    best = "SCHEDULED"
    for p in probes:
        kind = str(p.get("kind"))
        if kind == "proof":
            rung = "PROVEN"
        elif kind in ("pack_cells", "alt_proxies"):
            rung = "JUDGED"
        elif kind in ("free_stack", "asia_plane"):
            rung = "PRODUCING_CELLS"
        elif kind == "collector":
            rung = "RUNNING"
        elif p.get("cells_key"):
            rung = "PRODUCING_CELLS"
        elif p.get("rows_key") or str(p.get("artifact", "")).endswith((".parquet", ".jsonl",
                                                                          ".csv")):
            rung = "PRODUCING_DATA"
        else:
            rung = "RUNNING"
        if RANK[rung] > RANK[best]:
            best = rung
    return best


def delta(audit_state: str | None, state: str, reached: str, ceiling: str) -> tuple[str, str]:
    """This pass's state against the project audit's, on the same ladder names."""
    if not audit_state:
        return "unaudited", "the row carries no audit state"
    if state == audit_state:
        return "same", ""
    if state == UNMEASURED:
        return "unconfirmed", (f"the audit says {audit_state}; no evidence artifact is present on "
                               f"this host (the code reached {reached})")
    if state == "BLOCKED":
        return "down", f"measured BLOCKED; the audit says {audit_state}"
    if audit_state in ("BLOCKED", UNMEASURED) or audit_state not in RANK:
        return "changed", f"the audit says {audit_state}; measured {state} here"
    if RANK[state] > RANK[audit_state]:
        return "up", f"measured {state}; the audit says {audit_state}"
    if RANK[state] >= RANK[ceiling] and (RANK[state] >= RANK["RUNNING"] or ceiling == "WIRED"):
        return "unconfirmed", (f"measured {state}, the most this row's declared clock and "
                               f"artifacts can show; the audit's {audit_state} rests on evidence "
                               "the row does not declare")
    return "down", f"measured {state}; the audit says {audit_state}"


def _probe_key(p: dict[str, Any]) -> str:
    return json.dumps(p, sort_keys=True, default=str)


def claimants_by_probe(reqs: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Which requirement rows name each generic artifact probe. Every audit row is its own
    claimant: an overlay's probe attached by regex to several audit rows is shared by all of them,
    so each is credited only the rows its own filter selects (the overlay's region reaches the
    filter through the row's `region`)."""
    out: dict[str, set[str]] = {}
    for r in reqs:
        for p in r.get("probes") or []:
            if p.get("kind") == "artifact":
                out.setdefault(_probe_key(p), set()).add(f"row:{r.get('id')}")
    return out


#: Every rung above RUNNING, in order: a row holds a rung only when it holds every rung below.
RUNTIME_RUNGS = ("PRODUCING_DATA", "PRODUCING_CELLS", "JUDGED", "FORWARD", "LIVE", "PROVEN")


def judge(rd: Reader, row: dict[str, Any], reach: Reach,
          runtime: dict[str, dict[str, Any]], now: datetime,
          proof_cache: dict[str, dict[str, Any]],
          claimants: dict[str, set[str]] | None = None) -> dict[str, Any]:
    rung, why = static_rung(rd, row, reach)
    claimants = claimants or {}
    inputs_only = {str(x) for x in row.get("inputs") or []} - {str(x) for x in
                                                               row.get("outputs") or []}
    flt = requirement_filter(row)
    probes: list[dict[str, Any]] = []
    for p in row.get("probes") or []:
        kind = str(p.get("kind"))
        if kind == "artifact" and len(p) == 2 and str(p.get("artifact")) in inputs_only:
            continue                        # an INPUT the organ reads is not evidence it ran
        if kind == "proof":
            probes.append(probe_proof(rd, p, now, proof_cache))
        elif kind in PROBES:
            key = "probe:" + _probe_key(p)
            if key not in rd.memo:
                rd.memo[key] = PROBES[kind](rd, p)
            got = dict(rd.memo[key])
            who = sorted(claimants.get(_probe_key(p), set()))
            if kind == "artifact" and len(who) > 1:
                got = attribute(rd, got, p, flt, who)
            probes.append(got)
    present = [p for p in probes if p["present"] and not p.get("unattributed")]
    unattributed = [p for p in probes if p["present"] and p.get("unattributed")]
    sched = [str(s) for s in row.get("scheduler") or []]
    legs = [s.split(":", 1)[1] for s in sched if s.startswith(("hourly:", "own_clock:"))]
    rt = {leg: runtime.get(f"leg:{leg}") for leg in legs}
    # A STALE leg has not run within its horizon: it does not earn RUNNING.
    rt_live = [leg for leg, r in rt.items() if r and r.get("state") == "LIVE"]
    ok_runs = sorted(str(r.get("last_run_at")) for r in rt.values()
                     if r and r.get("last_run_outcome") == "ok" and r.get("last_run_at"))
    counted = [p for p in probes if not p.get("unattributed")]
    data = _sum(p["data"] for p in counted)
    cells = _sum(p["cells"] for p in counted)
    judged = _sum(p["judged"] for p in counted)
    survivors = _sum(p["survivors"] for p in counted)
    blocked = [p["blocked"] for p in probes if p["blocked"]]
    proofs = [p["proof"] for p in probes if p.get("proof")]
    horizon = HOURLY_STALE_H if any(s.startswith("hourly:") for s in sched) else OTHER_STALE_H
    ages = [p["age_h"] for p in present if p["age_h"] is not None]
    newest = min(ages) if ages else None
    freshness = (UNMEASURED if newest is None else ("FRESH" if newest <= horizon else "STALE"))

    reached = rung
    held: dict[str, bool] = {}
    verify = row.get("verify") if isinstance(row.get("verify"), dict) else None
    verify_out: dict[str, Any] | None = None
    if (not row.get("owner") and not row.get("hold_absent")
            and row.get("audit_state") not in (None, "ABSENT")):
        state = UNMEASURED
        why[:] = [f"the audit grades this {row.get('audit_state')} but names no module, clock or "
                  "artifact for it (a law, a negative constraint or a roll-up of other rows): "
                  "nothing here can re-derive it, so it is UNMEASURED, not ABSENT"]
    elif RANK[rung] < RANK["SCHEDULED"]:
        state = rung
    elif not present and not rt_live:
        state = UNMEASURED
        if unattributed:
            why.append("its only evidence is an artifact shared with other requirements whose "
                       "rows cannot be attributed to this one: UNMEASURED, never the shared count")
        else:
            why.append("no evidence artifact is present on this host: UNMEASURED, never a pass")
    else:
        # EVERY RUNG IS EARNED ON TOP OF THE ONE BELOW. A proof without judged cells, cells without
        # data, or anything without FORWARD/LIVE lineage stops at the last rung actually held.
        held = {"PRODUCING_DATA": bool(data), "PRODUCING_CELLS": bool(cells),
                "JUDGED": bool(judged),
                "FORWARD": False, "LIVE": False,          # no per-requirement lineage published
                "PROVEN": bool(proofs) and all(pr.get("verdict") == "PROVEN" for pr in proofs)}
        reached = "RUNNING"
        for r_ in RUNTIME_RUNGS:
            if not held[r_]:
                break
            reached = r_
        above = [r_ for r_ in RUNTIME_RUNGS if held[r_] and RANK[r_] > RANK[reached]]
        if above:
            gap = next(r_ for r_ in RUNTIME_RUNGS if not held[r_])
            why.append(f"evidence for {', '.join(above)} exists but {gap} does not hold: held at "
                       f"{reached} (every lower rung must hold)")
        if verify and verify.get("kind") == "min_rows":
            need = int(verify.get("min_rows") or 1)
            ok = data is not None and data >= need
            verify_out = {"ok": ok, "need_rows": need, "have_rows": data,
                          "why": verify.get("why", "")}
            if not ok and RANK[reached] > RANK["RUNNING"]:
                why.append(f"XLIV verification failed ({data} < {need} rows: "
                           f"{verify.get('why', '')}); held at RUNNING")
                reached = "RUNNING"
        state = reached
        if blocked and RANK[reached] <= RANK["RUNNING"]:
            state = "BLOCKED"
    keys = {k: bool(os.environ.get(k)) for k in row.get("key_env") or []}
    ceiling = probe_ceiling(list(row.get("probes") or []))
    if not row.get("probes") and not sched:
        ceiling = "WIRED"                   # no clock and no artifact: code is all it can show
    audit_state = row.get("audit_state")
    d_kind, d_why = delta(str(audit_state) if audit_state else None, state, reached, ceiling)
    last_ok = ok_runs[-1] if ok_runs else None
    if last_ok is None and newest is not None:
        last_ok = (datetime.fromtimestamp(rd.now, tz=UTC)
                   - timedelta(hours=newest)).isoformat(timespec="seconds")
        last_basis = "newest evidence artifact's in-file timestamp"
    else:
        last_basis = "runtime_state last_run_at (outcome ok)" if last_ok else UNMEASURED
    return {
        "id": row["id"], "report_row": row.get("report_row"), "title": row.get("title"),
        "source": row.get("source") or "", "part": row.get("part"),
        "owner_thread": row.get("owner_thread") or "", "overlays": row.get("overlays") or [],
        "audit_state": audit_state or UNMEASURED, "delta": d_kind, "delta_why": d_why,
        "probe_ceiling": ceiling,
        "parts": row.get("parts") or [], "xliv": bool(row.get("xliv")),
        "region": row.get("region"), "package": row.get("package") or "",
        "state": state, "rung_reached": reached, "static_rung": rung,
        "baseline_2026_10_06": row.get("baseline"),
        "proxy": bool(row.get("proxy")),
        "owner": row.get("owner") or [], "scheduler": sched,
        "input_artifacts": row.get("inputs") or [], "output_artifacts": row.get("outputs") or [],
        "freshness": {"status": freshness, "newest_age_h": round(newest, 3) if newest is not None
                      else None, "horizon_h": horizon,
                      "basis": ("the evidence artifact's own generated_at / row stamp"
                                if newest is not None else
                                "no in-file timestamp on any evidence artifact (mtime is never "
                                "read)")},
        "rungs_held": held,
        "last_successful_run": last_ok or UNMEASURED, "last_successful_run_basis": last_basis,
        "runtime": {leg: (r or {}).get("state", UNMEASURED) for leg, r in rt.items()},
        "observations": data if data is not None else UNMEASURED,
        "cells_emitted": cells if cells is not None else UNMEASURED,
        "cells_judged": judged if judged is not None else UNMEASURED,
        "survivors": survivors if survivors is not None else UNMEASURED,
        "forward": UNMEASURED, "live": UNMEASURED,
        "proofs": proofs,
        "verify": verify_out,
        "blocker": "; ".join(blocked) if blocked else (row.get("blocker") or ""),
        "blocker_measured": bool(blocked),
        "keys_present": keys,
        "next_repair": row.get("next_repair") or "",
        "consumer": row.get("consumer") or "",
        "why": why,
        "evidence": [{k: v for k, v in p.items() if k != "proof"} for p in probes],
        "box": bool(row.get("box")),
    }


# ------------------------------------------------------------------------- the Asia sources
def asia_sources(rd: Reader) -> dict[str, Any]:
    """Registered / active / blocked / fresh / stale, per country group and per category."""
    reg = rd.json(REGISTRY_REL)
    rows = [r for r in (reg.get("sources") if isinstance(reg, dict) else None) or []
            if isinstance(r, dict) and r.get("id")]
    coll = rd.json(COLLECTOR_REL)
    cstat = {str(r.get("id")): str(r.get("status") or "")
             for r in ((coll or {}).get("rows") if isinstance(coll, dict) else None) or []
             if isinstance(r, dict)}
    state = rd.json(COLLECTOR_STATE_REL)
    state = state if isinstance(state, dict) else {}
    have_runtime = bool(cstat) or bool(state)

    def group(r: dict[str, Any]) -> str | None:
        c = str(r.get("country") or "").lower()
        if c in ASIA_COUNTRIES:
            return ASIA_COUNTRIES[c]
        if c in OTHER_ASIA:
            return "other Asia"
        return None

    def bucket(sel: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {"registered": len(sel)}
        if not have_runtime:
            for k in ("active", "blocked", "fresh_series", "stale_series"):
                out[k] = UNMEASURED
            return out
        active = blocked = fresh = stale = 0
        for r in sel:
            sid = str(r["id"])
            st = cstat.get(sid) or str((state.get(sid) or {}).get("last_status") or "")
            if st in OK_COLLECTOR:
                active += 1
            if st.startswith("BLOCKED") or st == "UNCONFIGURED":
                blocked += 1
            epoch = (state.get(sid) or {}).get("last_attempt_epoch")
            if st in OK_COLLECTOR and isinstance(epoch, (int, float)):
                if rd.now - float(epoch) <= 48 * 3600:
                    fresh += 1
                else:
                    stale += 1
        out.update({"active": active, "blocked": blocked, "fresh_series": fresh,
                    "stale_series": stale})
        return out

    asia = [r for r in rows if group(r)]
    by_group = {g: bucket([r for r in asia if group(r) == g])
                for g in (*ASIA_COUNTRIES.values(), "other Asia")}
    by_cat = {cat: bucket([r for r in asia if str(r.get("plane") or "") in planes])
              for cat, planes in CATEGORY_PLANES.items()}
    grounds = rd.json(FOREST_GROUNDS_REL)
    glist = grounds if isinstance(grounds, list) else []
    asian_lang = ("zh", "zh-Hant", "ja", "ko", "vi", "th", "id", "ms", "hi", "tl")
    by_cat["practitioner forest"] = {
        "registered": sum(1 for g in glist if isinstance(g, dict)
                          and str(g.get("language")) in asian_lang),
        "basis": "deep_forest_sources.json grounds in an Asian language"}
    return {"registered": len(asia), "totals": bucket(asia), "by_group": by_group,
            "by_category": by_cat,
            "basis": (f"{REGISTRY_REL} rows by country; activity from {COLLECTOR_REL} and "
                      f"{COLLECTOR_STATE_REL} (fresh = collected within 48h)")}


# ---------------------------------------------------------------------------------- the audit
def load_requirements(rd: Reader) -> tuple[list[dict[str, Any]], list[str]]:
    doc = rd.json(REQS_REL)
    errors: list[str] = []
    if not isinstance(doc, dict):
        return [], [f"{REQS_REL} is absent or unreadable"]
    rows = [r for r in doc.get("requirements") or [] if isinstance(r, dict)]
    if tuple(doc.get("ladder") or ()) != LADDER:
        errors.append("the requirement file's ladder is not the directive's 13 states in order")
    seen: set[str] = set()
    for r in rows:
        rid = str(r.get("id") or "")
        if not rid:
            errors.append("a requirement has no id")
            continue
        if rid in seen:
            errors.append(f"{rid}: duplicate id")
        seen.add(rid)
        if r.get("audit_state") and r["audit_state"] not in LADDER:
            errors.append(f"{rid}: audit state {r['audit_state']!r} is not on the ladder")
        for p in r.get("probes") or []:
            k = str(p.get("kind"))
            if k not in PROBES and k != "proof":
                errors.append(f"{rid}: unknown probe kind {k!r}")
            if not p.get("artifact"):
                errors.append(f"{rid}: a probe names no artifact")
            if k == "proof" and p.get("proof") not in PROOFS:
                errors.append(f"{rid}: unknown proof {p.get('proof')!r}")
        for s in r.get("scheduler") or []:
            if str(s).partition(":")[0] not in SCHEDULER_KINDS:
                errors.append(f"{rid}: scheduler {s!r} names no known clock kind")
    for o in doc.get("overlays") or []:
        try:
            re.compile(str(o.get("match") or ""))
        except re.error as exc:
            errors.append(f"overlay {o.get('key')}: bad match regex ({exc})")
    if not rows:
        errors.append("no requirements (run --import-audit on the project completion audit)")
    return rows, errors


# ------------------------------------------------------------------ importing the project audit
def audit_part(source: str) -> str | None:
    m = re.search(r"\bPART ([IVXL]+)\b", source or "")
    return m.group(1) if m else None


def region_of(text: str) -> str:
    for code, words in REGION_WORDS:
        if re.search(words, text or "", re.IGNORECASE):
            return code
    return "GLOBAL"


def hourly_legs(src: str) -> set[str]:
    return set(re.findall(r"""_costed\(\s*["'](\w+)["']""", src or ""))


def parse_clock(text: str, legs: set[str]) -> list[str]:
    """The audit's clock text as scheduler entries: every hourly_cycle leg it names (checked
    against the tree), else the text itself as an audit-named clock, else nothing."""
    text = str(text or "").strip()
    if not text or NO_CLOCK.match(text):
        return []
    named = []
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        if tok in legs and f"hourly:{tok}" not in named:
            named.append(f"hourly:{tok}")
    return named or [f"audit:{text[:160]}"]


def _evidence_probe(path: str) -> dict[str, Any] | None:
    path = str(path or "").strip()
    if not path or any(c in path for c in "<>*{}") or path.endswith("/") or not Path(path).suffix:
        return None
    return {"kind": "artifact", "artifact": path}


def _clip(text: Any, n: int) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 3] + "..."


def overlay_hits(overlays: list[dict[str, Any]], text: str, part: str | None) -> list[dict[str, Any]]:
    out = []
    for o in overlays:
        parts = o.get("match_parts") or []
        if parts and part not in parts:
            continue
        if o.get("match") and re.search(str(o["match"]), text, re.IGNORECASE):
            out.append(o)
    return out


def import_audit(audit_doc: dict[str, Any], req_doc: dict[str, Any],
                 hourly_src: str) -> dict[str, Any]:
    """Vendor the audit's ASIA rows as the requirement set, with the overlays attached."""
    overlays = [o for o in req_doc.get("overlays") or [] if isinstance(o, dict)]
    legs = hourly_legs(hourly_src)
    rows: list[dict[str, Any]] = []
    for a in audit_doc.get("requirements") or []:
        if not isinstance(a, dict) or not str(a.get("id", "")).startswith(AUDIT_ID_PREFIX):
            continue
        text = f"{a.get('requirement', '')} {a.get('source', '')}"
        part = audit_part(str(a.get("source") or ""))
        hits = overlay_hits(overlays, text, part)
        owner: list[str] = []
        for m in [*(str(x).rsplit(":", 1)[0] if re.search(r":\d+$", str(x)) else str(x)
                    for x in a.get("module") or []),
                  *(str(x) for o in hits for x in o.get("owner") or [])]:
            if m and m not in owner:
                owner.append(m)
        sched = parse_clock(str(a.get("scheduler") or ""), legs)
        for o in hits:
            sched += [str(x) for x in o.get("scheduler") or [] if str(x) not in sched]
        probes: list[dict[str, Any]] = []
        seen: set[str] = set()
        # Only what the organ WRITES is evidence it ran; an input it reads proves nothing.
        declared = list(a.get("output_artifacts") or [])
        for p in [*(p for o in hits for p in o.get("probes") or []),
                  *filter(None, (_evidence_probe(x) for x in declared))]:
            k = json.dumps(p, sort_keys=True)
            bare = p.get("kind") == "artifact" and len(p) == 2
            if k not in seen and not (bare and str(p.get("artifact")) in {
                    str(q.get("artifact")) for q in probes}):
                seen.add(k)
                probes.append(dict(p))
        markers = [m for o in hits for m in o.get("code_markers") or []]
        first = hits[0] if hits else {}
        region = region_of(str(a.get("requirement") or ""))
        if region == "GLOBAL" and first.get("region") not in (None, "", "GLOBAL"):
            region = str(first["region"])
        row: dict[str, Any] = {
            "id": a["id"], "source": _clip(a.get("source"), 160), "part": part,
            "title": _clip(a.get("requirement"), IMPORT_TEXT_CHARS),
            "audit_state": a.get("state"), "owner_thread": _clip(a.get("owner_thread"), 80),
            "region": region, "overlays": [str(o.get("key")) for o in hits],
            "report_row": first.get("report_row"), "package": first.get("package") or "",
            "xliv": any(o.get("xliv") for o in hits) or part == "XLIV",
            "owner": owner, "scheduler": sched,
            "scheduler_text": _clip(a.get("scheduler"), 200),
            "inputs": list(a.get("input_artifacts") or []),
            "outputs": list(a.get("output_artifacts") or []),
            "probes": probes,
            "blocker": _clip(a.get("blocker"), IMPORT_EVIDENCE_CHARS),
            "next_repair": _clip(a.get("next_repair"), IMPORT_EVIDENCE_CHARS),
            "audit_evidence": _clip(a.get("evidence"), IMPORT_EVIDENCE_CHARS),
        }
        for k in ("verify", "proxy", "key_env", "consumer", "box", "baseline"):
            if k in first:
                row[k] = first[k]
        if markers:
            row["code_markers"] = markers
        if a.get("state") == "ABSENT" and not markers:
            row["hold_absent"] = True
        rows.append(row)
    out = {k: v for k, v in req_doc.items() if k != "requirements"}
    out["audit_source"] = {"path": str(audit_doc.get("_path") or ""),
                           "generated_at": audit_doc.get("generated_at"),
                           "live_sha": audit_doc.get("live_sha"),
                           "rows": len(rows)}
    out["requirements"] = rows
    return out


def _write_requirements(doc: dict[str, Any], root: Path) -> Path:
    out = root / REQS_REL
    lines = [f" {json.dumps(r, ensure_ascii=True, sort_keys=False)}" for r in doc["requirements"]]
    head = {k: v for k, v in doc.items() if k != "requirements"}
    body = json.dumps(head, indent=1, ensure_ascii=True)
    text = body[:-2] + ',\n "requirements": [\n' + ",\n".join(lines) + "\n ]\n}\n"
    json.loads(text)                                    # never write a file the checker can't read
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, out)
    return out


def summary_lines(doc: dict[str, Any]) -> list[str]:
    c = doc.get("census") or {}
    lines = [f"ASIA DIRECTIVE COMPLETION AUDIT {doc.get('at')} on {doc.get('host')}: "
             f"{doc.get('n_items')} requirements -- "
             + ", ".join(f"{s} {c[s]}" for s in LADDER if c.get(s))]
    dc = doc.get("delta_census") or {}
    src = _dict(doc.get("audit_source")).get("path") or "?"
    lines.append(f"against the project audit ({src}): "
                 + ", ".join(f"{k} {v}" for k, v in sorted(dc.items())))
    proofs = doc.get("proofs") or {}
    lines.append("XLIV proofs: " + ", ".join(f"{k}={v.get('verdict')}"
                                             for k, v in sorted(proofs.items())))
    xl = Counter(i["state"] for i in doc.get("items") or [] if i.get("xliv"))
    lines.append("XLIV rows: " + ", ".join(f"{s} {xl[s]}" for s in LADDER if xl.get(s)))
    down = [i["id"] for i in doc.get("items") or [] if i.get("delta") == "down"]
    if down:
        lines.append(f"measured BELOW the audit ({len(down)}): {', '.join(down[:15])}"
                     + (" ..." if len(down) > 15 else ""))
    um = [i["id"] for i in doc.get("items") or [] if i.get("state") == UNMEASURED]
    if um:
        lines.append(f"UNMEASURED on this host ({len(um)}): {', '.join(um[:15])}"
                     + (" ..." if len(um) > 15 else "") + " -- read them on the box")
    return lines


def audit(root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    nowdt = now or datetime.now(tz=UTC)
    rd = Reader(root, nowdt.timestamp())
    reqs, errors = load_requirements(rd)
    meta = _dict(rd.json(REQS_REL))
    audit_census = Counter(str(r.get("audit_state")) for r in reqs if r.get("audit_state"))
    reach = Reach(rd)
    runtime, rt_meta = _runtime_rows(rd)
    cache: dict[str, dict[str, Any]] = {}
    claimants = claimants_by_probe(reqs)
    items = [judge(rd, r, reach, runtime, nowdt, cache, claimants) for r in reqs]
    census = Counter(i["state"] for i in items)
    by_region: dict[str, dict[str, Any]] = {}
    for i in items:
        reg = by_region.setdefault(str(i.get("region") or "?"),
                                   {"items": 0, "states": Counter(), "observations": None,
                                    "cells_emitted": None, "cells_judged": None,
                                    "survivors": None, "delta": Counter()})
        reg["items"] += 1
        reg["delta"][i["delta"]] += 1
        reg["states"][i["state"]] += 1
        for k in ("observations", "cells_emitted", "cells_judged", "survivors"):
            v = i[k]
            if isinstance(v, int):
                reg[k] = (reg[k] or 0) + v
    for reg in by_region.values():
        reg["states"] = dict(reg["states"])
        reg["delta"] = dict(reg["delta"])
        for k in ("observations", "cells_emitted", "cells_judged", "survivors"):
            if reg[k] is None:
                reg[k] = UNMEASURED
    by_package: dict[str, dict[str, int]] = {}
    for i in items:
        pk = by_package.setdefault(i["package"] or "unowned", {})
        pk[i["state"]] = pk.get(i["state"], 0) + 1
    doc: dict[str, Any] = {
        "schema": "asia_completion_audit/1",
        "at": nowdt.isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "runtime_attestation": rt_meta or {"status": UNMEASURED, "why": f"{RUNTIME_REL} absent"},
        "requirements_file": REQS_REL,
        "requirement_errors": errors,
        "ladder": list(LADDER),
        "n_items": len(items),
        "census": {s: census.get(s, 0) for s in LADDER},
        "audit_source": meta.get("audit_source"),
        "audit_census": {s: audit_census.get(s, 0) for s in LADDER},
        "delta_census": dict(sorted(Counter(i["delta"] for i in items).items())),
        "by_region": by_region,
        "by_package": by_package,
        "proofs": cache,
        "asia_sources": asia_sources(rd),
        "items": items,
        "rule": ("the requirement set is the project completion audit's ASIA rows; every rung "
                 "holds only on top of every rung below it; WIRED is reachability from a scheduler "
                 "root and SCHEDULED needs every declared clock confirmed; code lifts a row at "
                 "most to SCHEDULED; every higher rung is read from a runtime artifact's OUTPUT, "
                 "attributed per requirement when shared; an absent or unattributable artifact is "
                 "UNMEASURED; freshness is the in-file timestamp; a failed XLIV verification "
                 "holds a row at RUNNING; forward/live per requirement are UNMEASURED until "
                 "lineage from a source to a clock is published, so no row is PROVEN before it"),
        "scheduler_roots": {"roots": len(reach.roots),
                            "code_files_reached": len(reach.reached),
                            "code_files": len(reach.files)},
        "consumers": ["desks/mt5/research/desk_dashboard_state.py (ASIA INTELLIGENCE section)",
                      "scripts/run_law_gate.py (--fence summary)"],
        "seconds": round(time.monotonic() - t0, 3),
    }
    doc["summary"] = summary_lines(doc)
    return doc


def write(doc: dict[str, Any], root: Path = ROOT) -> Path:
    out = root / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=True, default=str) + "\n", "utf-8")
    os.replace(tmp, out)
    return out


def _name_safe_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]


def main(argv: list[str] | None = None) -> int:
    _name_safe_stdout()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="write the audit (the hourly leg)")
    ap.add_argument("--summary", action="store_true", help="print the last audit's summary")
    ap.add_argument("--fence", action="store_true",
                    help="validate the requirement file and print the last summary (law gate)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--import-audit", metavar="PATH",
                    help="vendor the ASIA-xxxx rows of a project completion audit JSON as the "
                         "requirement set (keeps the file's overlays)")
    a = ap.parse_args(argv)
    if a.import_audit:
        src = Path(a.import_audit)
        audit_doc = json.loads(src.read_text("utf-8"))
        audit_doc["_path"] = src.name
        req_doc = _dict(json.loads((ROOT / REQS_REL).read_text("utf-8")))
        doc = import_audit(audit_doc, req_doc, Reader(ROOT).text(SCHEDULER_FILES["hourly"]) or "")
        out = _write_requirements(doc, ROOT)
        n = len(doc["requirements"])
        lifted = sum(1 for r in doc["requirements"] if r.get("overlays"))
        print(f"imported {n} {AUDIT_ID_PREFIX}xxxx rows from {src.name} ({lifted} carry an "
              f"overlay) -> {out}")
        return 0 if n else 1
    if a.fence or a.summary:
        rd = Reader(ROOT)
        _rows, errors = load_requirements(rd)
        last = rd.json(OUT_REL)
        if isinstance(last, dict):
            for line in last.get("summary") or []:
                print(line)
        else:
            print(f"asia directive audit: {UNMEASURED} -- {OUT_REL} absent on this host; the "
                  "hourly leg asia_completion_audit writes it")
        for e in errors:
            print(f"FAIL requirement file: {e}")
        return 1 if (a.fence and errors) else 0
    doc = audit()
    if not a.json:
        write(doc)
    if a.json:
        print(json.dumps(doc, indent=1, ensure_ascii=True, default=str))
    else:
        for line in doc["summary"]:
            print(line)
        print(f"-> {ROOT / OUT_REL}")
    return 1 if doc["requirement_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
