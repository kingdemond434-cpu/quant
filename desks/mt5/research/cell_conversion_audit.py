"""CELL CONVERSION AUDIT: does every idea the desk produces become a testable cell?

THE PRINCIPAL'S STANDING ORDER (2026-11-11, given three times): every research output,
producer, miner, yield and idea in the quant becomes real, testable breadth cells for the
gauntlet, at 100% capacity, with nothing missed. Scope addition the same day: every row and every
raw cell too, and every data-row source the desk collects.

This leg MEASURES that order and FLAGS every gap. Then it CONVERTS the gaps that need no
judgement, through the doors the desk already has.

WHAT IT MEASURES (every list DERIVED, never hand-listed; a source added tomorrow is audited
tomorrow):

    legs       every costed leg of `hourly_cycle.py` (`ops.components.leg_names`), resolved to its
               producer script (`components._producer_calls`) or its own module. A leg is an
               IDEA EMITTER when its code holds a door (`donate(`, a `data/intelligence` seat,
               `enqueue_candidate(` / a `research_candidates` insert) or declares an idea-shaped
               output (an OUT-like constant naming a hypotheses/claims/candidates/ideas file).
    tier1      Tier-1 items scheduled OUTSIDE the hourly cycle (a box task, a VPS timer, the
               daily cycle) whose cited code is an idea emitter.
    seats      every directory under BOTH intelligence roots the compiler reads.
    artifacts  every idea-shaped file under `data/hypotheses/`, `data/` and `reports/cro/`.
    handoff    the judge's parked cells, `data/hypotheses/conversion_handoff.json`.
    idea_queue the owner threads' IDEA_QUEUE.md (where this host holds one).
    data       every dataset the desk collects: `data/data_registry.json`, `data/axes/*.json`,
               the lake series under `data/lake/series/`, the bar timeframes and the tick/tape
               directories, each checked against the family code (`mt5desk/famil*.py`) for a
               consumer.
    stages     the raw-cell funnel: intake rows -> compiled cells -> docket -> registry -> judged,
               each read from the artifact that owns it, compared to the previous pass so a stage
               where rows stop moving reads STALLED.

HOW A SOURCE REACHES THE GAUNTLET, as the desk wires it:
    seat      -> `miner_candidate_compiler` -> `miner_candidates.json` (per_source = measured)
    registry  -> `research_candidates` -> the docket feed in `merge_hypotheses`
    docket    -> a file named in `merge_hypotheses.SOURCES` (merge_report.per_source = measured)
    handoff   -> a converter that reads `conversion_handoff.json`

VERDICTS: CONVERTING, PARTIAL (with the named loss stage), NOT_WIRED (the output reaches no
converter at all), UNMEASURED (the artifact that would say is absent here; a verdict, never a
zero -- L1.28a). Every NOT_WIRED or PARTIAL source and every STALLED stage is published as an
issue in `research/issue_board.Issue` form, and the board collects them.

WHAT IT CONVERTS, mechanically and only through the existing door (`proposer_common.donate` ->
`data/intelligence/cell_conversion_audit/discoveries_*_<family>.json`, which the compiler reads):
    * an open IDEA_QUEUE row, an unwired idea artifact's rows: through the compiler's own
      `compile_row` (exact recipe, structured hypothesis, deterministic prose vocabulary). A row
      the compiler cannot compile stays parked, counted by its reason.
    * a lake series no cell consumes: `exogenous_conditioner` cells (the family reads any lake
      series by name), on the instruments the pack declares.
EVERY CONVERTED CELL IS A NEW TRIAL, charged to its trial_family: one donation file per family,
`tests_run` = the cells the compiler will mint from it after its own axis expansion, which is what
`experiment_ledger._proposer_counts` reads. A cell already converted (the ledger) is never
re-donated, so a cell is charged once. The two-lane rule holds at this door as well as at donate:
a share CFD may only carry a `universe_policy.CROSS_SECTIONAL_FAMILIES` cell; an unclassified or
non-MT5 instrument carries none. No crypto-exchange universe is read.

    python desks/mt5/research/cell_conversion_audit.py --once [--budget-s 300] [--no-convert]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESEARCH = DESK / "research"
OUT = DESK / "reports" / "CELL_CONVERSION_AUDIT.json"
HYP = DESK / "data" / "hypotheses"
INTEL_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
MINER_CANDIDATES = HYP / "miner_candidates.json"
MERGE_REPORT = HYP / "merge_report.json"
MERGE_MODULE = RESEARCH / "merge_hypotheses.py"
HANDOFF = HYP / "conversion_handoff.json"
PRODUCER_BREADTH = DESK / "reports" / "PRODUCER_BREADTH.json"
JUDGE_COVERAGE = DESK / "reports" / "JUDGE_COVERAGE.json"
JUDGING_RATE = DESK / "reports" / "JUDGING_RATE.json"
PACK_CELLS = DESK / "reports" / "PACK_CELLS.json"
TIER1 = ROOT / "docs" / "research" / "tier1_program.json"
DATA_REGISTRY = DESK / "data" / "data_registry.json"
AXES = DESK / "data" / "axes"
LAKE_SERIES = DESK / "data" / "lake" / "series"
UNIVERSE = DESK / "data" / "universe"
FAMILY_CODE = DESK / "mt5desk"
#: Where an idea queue may live on this host. The repo's own `reports/` first; the second root is
#: the project-files mount the owner threads write to, read only where it exists.
IDEA_QUEUE_ROOTS = (ROOT / "reports", Path("/mnt/attach/project-files/reports"),
                    Path("/mnt/project-files/reports"))
IDEA_QUEUE_NAME = "IDEA_QUEUE.md"
#: Cells this leg already converted, one row per cell identity: the reason a cell is charged
#: once. Box state, gitignored; losing it re-charges (over-counts), it never under-counts.
LEDGER = HYP / "cell_conversion_ledger.jsonl"
SEAT = "cell_conversion_audit"

UNMEASURED = "UNMEASURED"
CONVERTING, PARTIAL, NOT_WIRED = "CONVERTING", "PARTIAL", "NOT_WIRED"
VERDICTS = (CONVERTING, PARTIAL, NOT_WIRED, UNMEASURED)
WINDOW_DAYS = 7
#: A converted share at or above this is CONVERTING; below it the loss stage is named.
FULL_SHARE = 0.999
#: Bounds per pass. Each cell is a trial on the shared family-wise budget, so the fan-out is
#: bounded per pass and per family; whatever is over the bound waits for the next pass, counted.
MAX_CELLS_PER_PASS = 400
MAX_CELLS_PER_FAMILY_PER_PASS = 100
MAX_ROWS_PER_ARTIFACT = 2_000
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_SEAT_SCAN = 400
#: A stage artifact older than this is STALE rather than a reading of now.
STAGE_STALE_H = 6.0

# ------------------------------------------------------------------------- code-text classifiers
#: The doors into the gauntlet's intake, as they are spelled in code.
DOOR_SEAT = re.compile(r"\bdonate\(|data[/\\\"' ,]+intelligence|INTEL\s*/|\"intelligence\"")
DOOR_REGISTRY = re.compile(
    r"\benqueue_candidate\(|INSERT\s+(?:OR\s+\w+\s+)?INTO\s+research_candidates|"
    r"_record_in_registry\(|record_candidates\(", re.I)
#: An idea-shaped file name: what a producer of hypotheses, claims or cells writes.
IDEA_FILE = re.compile(
    r"(hypothes|claim|idea|candidate|proposal|discover|lead|recipe|thesis|cells?\b|_cells|"
    r"noon_adds)", re.I)
#: An OUT-like module constant: the module's DECLARED output, not a file it merely reads.
_OUT_CONST = re.compile(
    r"^([A-Z][A-Z0-9_]*)\s*(?::[^=\n]*)?=\s*(.+)$", re.M)
_OUT_NAME = re.compile(r"(^|_)(OUT|OUTPUT|DEST|QUEUE|CANDIDATES|CLAIMS|IDEAS|HYPOTHESES|"
                       r"PROPOSALS|REPORT)(_|$)")
_FILE_LIT = re.compile(r"[\"']([A-Za-z0-9_.-]+\.jsonl?)[\"']")
_SEAT_CONST = re.compile(r'^(?:SOURCE|SEAT)\s*(?::\s*str)?\s*=\s*"([A-Za-z0-9_]+)"', re.M)
_DONATE_LIT = re.compile(r'donate\(\s*"([A-Za-z0-9_]+)"')
_INTEL_LIT = re.compile(r'INTEL\s*/\s*"([A-Za-z0-9_]+)"')

#: The converters themselves -- the doors a source is measured against -- and the cycle that
#: calls them. They are never audited AS sources: the compiler is not a producer of its own input.
DOOR_MODULES = frozenset({"hourly_cycle", "miner_candidate_compiler", "merge_hypotheses",
                          "proposer_common", "registry", "cell_conversion_audit"})

_TEXT_CACHE: dict[Path, str] = {}


def _text(p: Path) -> str:
    if p not in _TEXT_CACHE:
        try:
            _TEXT_CACHE[p] = p.read_text("utf-8", errors="replace")
        except OSError:
            _TEXT_CACHE[p] = ""
    return _TEXT_CACHE[p]


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _age_h(p: Path, now: datetime) -> float | None:
    try:
        return round((now.timestamp() - p.stat().st_mtime) / 3600.0, 2)
    except OSError:
        return None


def _tail_keys(p: Path, keys: tuple[str, ...]) -> dict[str, Any] | None:
    """Top-level keys of a LARGE json document that are written AFTER its bulk list.

    `miner_candidates.json` is ~70 MB of `hypotheses` followed by small blocks; parsing it whole
    to read `per_source` costs half a gigabyte on an 8 GB box. The text is scanned from the end
    for each key and only that value is decoded. None when the file is absent or unreadable.
    """
    try:
        if p.stat().st_size > 512 * 1024 * 1024:
            return None
        t = p.read_text("utf-8", errors="replace")
    except OSError:
        return None
    dec = json.JSONDecoder()
    out: dict[str, Any] = {}
    for k in keys:
        i = t.rfind(f'"{k}":')
        if i < 0:
            continue
        j = i + len(k) + 3
        while j < len(t) and t[j] in " \n\r\t":
            j += 1
        try:
            out[k] = dec.raw_decode(t, j)[0]
        except ValueError:
            continue
    return out


def declared_outputs(text: str) -> list[str]:
    """Idea-shaped file names the module DECLARES as an output (an OUT-like constant)."""
    found: list[str] = []
    for name, rhs in _OUT_CONST.findall(text):
        if not _OUT_NAME.search(name):
            continue
        for lit in _FILE_LIT.findall(rhs):
            stem = lit.split(".", 1)[0]
            # An ALL-CAPS stem is a report the desk reads, not an intake of ideas.
            if IDEA_FILE.search(lit) and stem != stem.upper() and lit not in found:
                found.append(lit)
    return found


def seats_of(text: str, stem: str) -> list[str]:
    """The seats a donating module writes, from its own SOURCE/SEAT constant, its literal
    `donate("seat", ...)` calls and `INTEL / "seat"` paths; its stem when none is spelled."""
    seats = list(dict.fromkeys(_SEAT_CONST.findall(text) + _DONATE_LIT.findall(text)
                               + _INTEL_LIT.findall(text)))
    return seats or [stem]


def classify(text: str, stem: str = "") -> dict[str, Any]:
    """What a module's code says about its output: the doors it holds and what it declares."""
    doors: list[str] = []
    if DOOR_SEAT.search(text):
        doors.append("seat")
    if DOOR_REGISTRY.search(text):
        doors.append("registry")
    outputs = declared_outputs(text)
    return {"doors": doors, "outputs": outputs,
            "emitter": bool(doors or outputs),
            "seats": seats_of(text, stem) if "seat" in doors else []}


# ------------------------------------------------------------------------- the derived sources
def merge_sources(path: Path | None = None) -> list[str]:
    """`merge_hypotheses.SOURCES` file names, read by AST (the docket door's own list)."""
    try:
        tree = ast.parse(_text(path or MERGE_MODULE))
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SOURCES"
                                                for t in node.targets):
            out: list[str] = []
            for elt in getattr(node.value, "elts", []):
                first = (elt.elts[0] if isinstance(elt, ast.Tuple) and elt.elts else None)
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    out.append(first.value)
            return out
    return []


def hourly_legs() -> dict[str, Path | None]:
    """Every costed hourly leg -> the code that runs it (producer script, else its own module)."""
    try:
        from ops import components
        names = components.leg_names()
        calls = components._producer_calls()
    except Exception:
        src = _text(RESEARCH / "hourly_cycle.py")
        names = sorted(set(re.findall(r'_costed\("([^"]+)"', src)))
        calls = {}
    out: dict[str, Path | None] = {}
    for leg in names:
        script = calls.get(leg, ("", ()))[0]
        cand: Path | None = None
        if script:
            for base in (DESK, ROOT):
                if (base / script).exists():
                    cand = base / script
                    break
        if cand is None and (RESEARCH / f"{leg}.py").exists():
            cand = RESEARCH / f"{leg}.py"
        out[leg] = cand
    return out


def tier1_offcycle() -> dict[str, list[Path]]:
    """Tier-1 items scheduled OUTSIDE the hourly cycle -> their cited code files."""
    doc = _read(TIER1, {}) or {}
    out: dict[str, list[Path]] = {}
    for it in doc.get("items") or []:
        sched = str(it.get("scheduled_by") or "")
        if not sched or "hourly_cycle:" in sched:
            continue
        files = [ROOT / str(e).split(":")[0] for e in (it.get("evidence") or [])
                 if str(e).endswith(".py") or ".py:" in str(e)]
        files = [f for f in files if f.exists() and "/tests/" not in f.as_posix()]
        if files:
            out[str(it.get("id"))] = files
    return out


def seat_dirs() -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for root in INTEL_ROOTS:
        try:
            for d in sorted(root.iterdir()):
                if d.is_dir() and not d.name.startswith((".", "_")):
                    out.setdefault(d.name, []).append(d)
        except OSError:
            continue
    return out


def idea_artifacts() -> list[Path]:
    """Idea-shaped files the desk holds: hypotheses, claims, candidates, ideas, NOON adds."""
    found: list[Path] = []
    for base, pat in ((HYP, "*.json*"), (DESK / "data", "*.json*"),
                      (DESK / "reports" / "cro", "*.json*")):
        try:
            for p in sorted(base.glob(pat)):
                if p.is_file() and IDEA_FILE.search(p.name) and p != LEDGER:
                    found.append(p)
        except OSError:
            continue
    return found


def idea_queue_path() -> Path | None:
    env = os.environ.get("QUANT_IDEA_QUEUE", "").strip()
    if env:
        p = Path(env)
        return p if p.exists() else None
    for root in IDEA_QUEUE_ROOTS:
        try:
            for p in sorted(root.rglob(IDEA_QUEUE_NAME)):
                return p
        except OSError:
            continue
    return None


def module_corpus() -> dict[str, str]:
    """Every research / libs module's text, by repo-relative path, for reader lookups."""
    out: dict[str, str] = {}
    for base in (RESEARCH, ROOT / "libs" / "research", ROOT / "libs" / "ops", ROOT / "scripts"):
        for p in sorted(base.glob("*.py")):
            if p.name == Path(__file__).name:
                continue
            out[p.relative_to(ROOT).as_posix()] = _text(p)
    return out


def door_readers(name: str, corpus: dict[str, str], exclude: str = "") -> list[str]:
    """Modules that mention `name` AND hold a door: the reader that carries it to the gauntlet."""
    readers = []
    for rel, txt in corpus.items():
        if rel == exclude or name not in txt:
            continue
        if DOOR_SEAT.search(txt) or DOOR_REGISTRY.search(txt):
            # the mention must not be the module's own declared output (that is its writer)
            if name in declared_outputs(txt):
                continue
            readers.append(rel)
    return readers


# ------------------------------------------------------------------------- measurement
def _row(source: str, klass: str, verdict: str, **kw: Any) -> dict[str, Any]:
    base = {"source": source, "class": klass, "verdict": verdict,
            "emitted": UNMEASURED, "converted": UNMEASURED, "cells": UNMEASURED,
            "parked": {}, "dropped": UNMEASURED, "unconverted": UNMEASURED,
            "share_converted": UNMEASURED, "loss_stage": None, "why": ""}
    base.update(kw)
    return base


def seat_measure(seat: str, per_source: dict[str, Any] | None, dirs: list[Path] | None,
                 now: datetime, compiled_at: datetime | None = None) -> dict[str, Any]:
    """One seat's conversion, from the compiler's own per_source block."""
    if per_source is None:
        return _row(f"seat:{seat}", "seat", UNMEASURED,
                    why="miner_candidates.json absent or unreadable here: the compiler's "
                        "per_source block is the measurement")
    st = per_source.get(seat)
    if not isinstance(st, dict):
        if compiled_at is None or (now - compiled_at).total_seconds() > STAGE_STALE_H * 3600:
            return _row(f"seat:{seat}", "seat", UNMEASURED,
                        why=f"the compiler's artifact is older than {STAGE_STALE_H}h (compiled "
                            f"{compiled_at.isoformat() if compiled_at else 'never'}): a seat "
                            "it did not account cannot be judged against it")
        recent = _recent_files(dirs or [], now)
        if recent:
            return _row(f"seat:{seat}", "seat", PARTIAL, emitted=UNMEASURED,
                        loss_stage="compiler_intake",
                        why=f"{recent} seat file(s) written inside {WINDOW_DAYS}d and the "
                            "compiler accounted no row from this seat")
        return _row(f"seat:{seat}", "seat", UNMEASURED,
                    why=f"no seat file inside the {WINDOW_DAYS}d window and no compiler row")
    rows = int(st.get("rows") or 0)
    cells = int(st.get("candidates") or 0)
    deepening = int(st.get("deepening") or 0)
    refused = int(st.get("valid_refusals") or 0) + int(st.get("invalid_cells") or 0)
    if "converted_rows" in st:
        converted = int(st.get("converted_rows") or 0)
        basis = "per_source.converted_rows"
    else:
        converted = max(0, rows - deepening - refused) if cells else 0
        basis = "rows - deepening - refusals (old artifact carries no converted_rows)"
    if rows == 0:
        return _row(f"seat:{seat}", "seat", UNMEASURED, emitted=0, converted=0, cells=0,
                    why="the seat donated no row inside the compiler's window: nothing to "
                        "measure conversion on (the zero is the compiler's measurement)")
    unconverted = max(0, rows - converted - deepening - refused)
    denom = max(1, rows - refused)
    share = round(converted / denom, 6)
    verdict = CONVERTING if share >= FULL_SHARE else PARTIAL
    loss = None
    if verdict == PARTIAL:
        loss = ("deepening (NEEDS_*_EXTRACTION: the row lacks an exact rule or instrument)"
                if deepening >= unconverted else "compile (unresolved rows)")
    return _row(f"seat:{seat}", "seat", verdict, emitted=rows, converted=converted, cells=cells,
                parked={"deepening": deepening} if deepening else {}, dropped=refused,
                unconverted=unconverted, share_converted=share, loss_stage=loss,
                measured_from=basis,
                measured_at=compiled_at.isoformat() if compiled_at else UNMEASURED)


def _recent_files(dirs: list[Path], now: datetime) -> int:
    cut = now.timestamp() - WINDOW_DAYS * 86400
    n = seen = 0
    for d in dirs:
        try:
            with os.scandir(d) as it:
                for e in it:
                    seen += 1
                    if seen > MAX_SEAT_SCAN:
                        return n
                    try:
                        if e.is_file() and e.stat().st_mtime >= cut:
                            n += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return n


def docket_measure(name: str, merge: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not isinstance(merge, dict):
        return UNMEASURED, {"why": "merge_report.json absent here"}
    per = merge.get("per_source") or {}
    state = (merge.get("source_state") or {}).get(name)
    if name not in per:
        return PARTIAL, {"loss_stage": "merge", "why": f"{name} is a docket source and the "
                                                       "last merge reported no row from it"}
    n = int(per.get(name) or 0)
    if n == 0:
        return UNMEASURED, {"converted": 0, "cells": 0,
                            "why": f"the last merge read {name} and took 0 rows: nothing to "
                                   "measure conversion on"}
    if state and state != "FRESH" and state != "MEASURED":
        return PARTIAL, {"converted": n, "cells": n, "loss_stage": f"merge ({state})",
                         "why": f"the last merge read {name} as {state}"}
    return CONVERTING, {"converted": n, "cells": n,
                        "why": f"merged {n} row(s) at {merge.get('merged_at')}"}


def producer_measure(stem: str, breadth: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not isinstance(breadth, dict):
        return UNMEASURED, {"why": "PRODUCER_BREADTH.json absent here"}
    row = (breadth.get("producers") or {}).get(stem)
    if not isinstance(row, dict) or not isinstance(row.get("cells_7d"), int):
        return UNMEASURED, {"why": f"PRODUCER_BREADTH carries no measured row for {stem}"}
    n = int(row["cells_7d"])
    if n == 0:
        return UNMEASURED, {"emitted": 0, "converted": 0, "cells": 0,
                            "why": "registry door held; no cell in 7d to measure on"}
    return CONVERTING, {"emitted": n, "converted": n, "cells": n,
                        "share_converted": 1.0, "why": "registry rows are cells at birth"}


def emitter_row(source: str, klass: str, code: Path, info: dict[str, Any], *,
                per_source: dict[str, Any] | None, merge: dict[str, Any] | None,
                breadth: dict[str, Any] | None, docket_names: list[str],
                corpus: dict[str, str], now: datetime,
                seat_dir_map: dict[str, list[Path]] | None = None,
                compiled_at: datetime | None = None) -> dict[str, Any]:
    """Verdict for one emitting module (an hourly leg or an off-cycle Tier-1 organ)."""
    rel = code.relative_to(ROOT).as_posix() if code.is_relative_to(ROOT) else str(code)
    common = {"code": rel, "doors": info["doors"], "outputs": info["outputs"]}
    if "seat" in info["doors"]:
        parts = [seat_measure(s, per_source, (seat_dir_map or {}).get(s, []), now, compiled_at)
                 for s in info["seats"]]
        measured = [p for p in parts if isinstance(p["emitted"], int) and p["emitted"] > 0]
        if not measured:
            v = PARTIAL if any(p["verdict"] == PARTIAL for p in parts) else UNMEASURED
            return _row(source, klass, v, seats=info["seats"], **common,
                        loss_stage=next((p["loss_stage"] for p in parts if p["loss_stage"]),
                                        None),
                        why="; ".join(sorted({p["why"] for p in parts}))[:400])
        emitted = sum(p["emitted"] for p in measured)
        converted = sum(int(p["converted"]) for p in measured)
        cells = sum(int(p["cells"]) for p in measured)
        dropped = sum(int(p["dropped"]) for p in measured)
        parked = sum(int((p["parked"] or {}).get("deepening", 0)) for p in measured)
        share = round(converted / max(1, emitted - dropped), 6)
        v = CONVERTING if share >= FULL_SHARE else PARTIAL
        return _row(source, klass, v, seats=info["seats"], **common, emitted=emitted,
                    converted=converted, cells=cells, dropped=dropped,
                    parked={"deepening": parked} if parked else {},
                    unconverted=max(0, emitted - converted - parked - dropped),
                    share_converted=share,
                    loss_stage=None if v == CONVERTING else next(
                        (p["loss_stage"] for p in measured if p["loss_stage"]), "compile"))
    if "registry" in info["doors"]:
        v, kw = producer_measure(code.stem, breadth)
        return _row(source, klass, v, **common, **kw)
    # output-only emitter: wired iff the docket door lists its file or a door module reads it
    for out in info["outputs"]:
        if out in docket_names:
            v, kw = docket_measure(out, merge)
            return _row(source, klass, v, **common, **kw)
    readers = sorted({r for out in info["outputs"] for r in door_readers(out, corpus, rel)})
    if readers:
        return _row(source, klass, UNMEASURED, **common, readers=readers[:6],
                    why="wired through a door-holding reader; that reader publishes no "
                        "per-artifact conversion count")
    return _row(source, klass, NOT_WIRED, **common, loss_stage="no converter",
                why=f"declares {', '.join(info['outputs'][:3])} and no seat, registry, docket "
                    "or door-holding reader takes it")


def artifact_row(p: Path, docket_names: list[str], merge: dict[str, Any] | None,
                 corpus: dict[str, str], now: datetime) -> dict[str, Any]:
    name = p.name
    rel = p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)
    if name in docket_names:
        v, kw = docket_measure(name, merge)
        return _row(f"artifact:{name}", "artifact", v, path=rel, **kw)
    readers = door_readers(name, corpus)
    if readers:
        return _row(f"artifact:{name}", "artifact", UNMEASURED, path=rel, readers=readers[:6],
                    why="read by a door-holding module; no per-artifact conversion published")
    return _row(f"artifact:{name}", "artifact", NOT_WIRED, path=rel, loss_stage="no converter",
                age_h=_age_h(p, now),
                why="no seat, registry, docket source or door-holding reader names this file")


# ------------------------------------------------------------------------- the parked stock
_HANDOFF_CLASS = re.compile(rb'"class":\s*"([a-z_]+)"')
_HANDOFF_AT = re.compile(rb'"first_parked_utc":\s*"([0-9T:+\-.Z ]+)"')


def handoff_stock(path: Path | None = None) -> dict[str, Any]:
    """The judge's parked cells, streamed: count by class and the oldest park time."""
    p = path or HANDOFF
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent here"}
    by: dict[str, int] = {}
    oldest = ""
    tail = b""
    try:
        with p.open("rb") as fh:
            while True:
                chunk = fh.read(8 * 1024 * 1024)
                if not chunk:
                    break
                buf = tail + chunk
                cut = buf.rfind(b"\n")
                if cut < 0:
                    tail = buf
                    continue
                body, tail = buf[:cut], buf[cut:]
                for m in _HANDOFF_CLASS.finditer(body):
                    k = m.group(1).decode()
                    by[k] = by.get(k, 0) + 1
                for m in _HANDOFF_AT.finditer(body):
                    t = m.group(1).decode()
                    if not oldest or t < oldest:
                        oldest = t
            for m in _HANDOFF_CLASS.finditer(tail):
                by[m.group(1).decode()] = by.get(m.group(1).decode(), 0) + 1
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"unreadable: {type(exc).__name__}"}
    return {"status": "MEASURED", "rows": sum(by.values()), "by_class": by,
            "oldest_parked_utc": oldest or None}


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


# ------------------------------------------------------------------------- the idea queue
_CLOSED = re.compile(r"\b(done|landed|merged|closed|rejected|archived|implemented|superseded|"
                     r"converted)\b", re.I)


def idea_rows(path: Path) -> list[dict[str, Any]]:
    """The queue's markdown table rows: rank, date, owner, item, evidence, score, status."""
    out: list[dict[str, Any]] = []
    header: list[str] | None = None
    for line in _text(path).splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None and cells and cells[0].lower() == "rank":
            header = [c.lower() for c in cells]
            continue
        if header is None or len(cells) < len(header):
            continue
        row = dict(zip(header, [*cells[:len(header) - 1], " | ".join(cells[len(header) - 1:])],
                       strict=True))
        row["idea_id"] = f"IQ-{row.get('rank', '?')}"
        row["open"] = not _CLOSED.search(str(row.get("status") or ""))
        out.append(row)
    return out


# ------------------------------------------------------------------------- data-row sources
def _family_corpus() -> str:
    """The code that turns a dataset into a cell's input: every family module and the sealed
    judge's build step (read, never written)."""
    files = [*sorted(FAMILY_CODE.glob("*famil*.py")), DESK / "scripts" / "external_gauntlet.py"]
    return "\n".join(_text(p) for p in files)


def data_sources() -> list[dict[str, Any]]:
    """Every dataset the desk collects, with the tokens a consuming family would name it by."""
    out: list[dict[str, Any]] = []
    reg = _read(DATA_REGISTRY, {}) or {}
    for did, row in sorted((reg.get("datasets") or {}).items()):
        path = str((row or {}).get("path") or "")
        toks = [did]
        parts = [x for x in Path(path).parts if x not in ("data", "")] if path else []
        for x in parts:
            x = x.split("*", 1)[0].split(".", 1)[0].strip("_")
            if len(x) >= 3 and x not in toks:
                toks.append(x)
        out.append({"id": f"dataset:{did}", "tokens": toks, "kind": "registry",
                    "path_declared": path,
                    "lifecycle": str((row or {}).get("lifecycle") or ""),
                    "symbols": (row or {}).get("symbols") if isinstance(
                        (row or {}).get("symbols"), list) else []})
    for p in sorted(AXES.glob("*.json")):
        doc = _read(p, {}) or {}
        toks = [str(doc.get("id") or p.stem), p.stem]
        out.append({"id": f"axis:{p.stem}", "tokens": toks, "kind": "axis",
                    "axis": doc.get("axis"), "symbols": doc.get("symbols") or []})
    try:
        for p in sorted(LAKE_SERIES.iterdir()):
            if p.suffix in (".parquet", ".csv"):
                out.append({"id": f"lake:{p.stem}", "tokens": [p.stem], "kind": "lake",
                            "path": p})
    except OSError:
        pass
    tfs = sorted({p.stem.rsplit("_", 1)[-1] for p in UNIVERSE.glob("*_*.parquet")})
    for tf in tfs:
        out.append({"id": f"bars:{tf}", "tokens": [tf], "kind": "bars"})
    for d in sorted((DESK / "data").iterdir()) if (DESK / "data").exists() else []:
        if d.is_dir() and re.search(r"tick|tape", d.name, re.I):
            out.append({"id": f"ticks:{d.name}", "tokens": [d.name], "kind": "ticks"})
    return out


def _consumers(tokens: list[str], corpus: str) -> bool:
    for t in tokens:
        if len(t) < 2:
            continue
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", corpus):
            return True
    return False


def _pack_names(doc: Any) -> set[str]:
    names: set[str] = set()
    stack = [doc]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            stack.extend(x.values())
            names.update(str(k) for k in x)
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str):
            names.add(x)
    return names


def data_row(ds: dict[str, Any], fam_corpus: str, pack_doc: Any) -> dict[str, Any]:
    if ds["kind"] == "registry" and not ds.get("path_declared"):
        return _row(ds["id"], "data", UNMEASURED,
                    why=f"registered {ds.get('lifecycle') or 'without a lifecycle'} with no "
                        "collected path: no rows exist here to convert")
    if ds["kind"] in ("bars",) or str(ds.get("path_declared") or "").startswith("data/universe/"):
        return _row(ds["id"], "data", CONVERTING, consumer="every price family (bars are the "
                    "input build_cell loads for each cell's symbol and chart)",
                    why="bars are consumed by construction")
    if ds["kind"] == "lake":
        if pack_doc is None:
            return _row(ds["id"], "data", UNMEASURED,
                        why="lake series are read by name (exogenous_conditioner); "
                            "PACK_CELLS.json, which names the consumed ones, is absent here")
        if ds["tokens"][0] in _pack_names(pack_doc):
            return _row(ds["id"], "data", CONVERTING, consumer="exogenous_conditioner "
                        "(pack_cells)", why="PACK_CELLS names this series")
        return _row(ds["id"], "data", NOT_WIRED, loss_stage="no consuming cell",
                    why="no pack cell names this lake series; the converter mints "
                        "exogenous_conditioner cells where the pack declares targets")
    if _consumers(ds["tokens"], fam_corpus):
        return _row(ds["id"], "data", CONVERTING, consumer="a registered family names it",
                    why="consumer present in mt5desk family code; per-dataset cell count "
                        "is not published")
    return _row(ds["id"], "data", NOT_WIRED, loss_stage="no consuming family",
                why=f"no family module names {', '.join(ds['tokens'][:3])}")


# ------------------------------------------------------------------------- the raw-cell funnel
def stage_flow(now: datetime, previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Raw -> compiled -> docket -> registry -> judged, each from its own artifact."""
    mc = _tail_keys(MINER_CANDIDATES, ("rows_accounted", "executable_candidates",
                                       "deepening_tasks", "compiled_at"))
    merge = _read(MERGE_REPORT)
    jc = _tail_keys(JUDGE_COVERAGE, ("totals", "at", "unrunnable_filtered_from_docket"))
    jr = _read(JUDGING_RATE)
    totals = (jc or {}).get("totals") or {}
    reg = (merge or {}).get("alpha_registry") or {}
    rate_v = ((jr or {}).get("verdicts") or {}) if isinstance(jr, dict) else {}

    def stage(name: str, n: Any, src: Path, basis: str) -> dict[str, Any]:
        return {"stage": name, "count": n if isinstance(n, int) else UNMEASURED,
                "artifact": src.name, "age_h": _age_h(src, now), "basis": basis}

    docket = totals.get("docket_rows")
    unjudged = totals.get("unjudged_total")
    rows = [
        stage("raw_intake_rows", (mc or {}).get("rows_accounted"), MINER_CANDIDATES,
              "miner_candidates.rows_accounted"),
        stage("compiled_cells", (mc or {}).get("executable_candidates"), MINER_CANDIDATES,
              "miner_candidates.executable_candidates"),
        stage("registry_candidates", reg.get("candidates"), MERGE_REPORT,
              "merge_report.alpha_registry.candidates"),
        stage("docket_cells", docket, JUDGE_COVERAGE, "JUDGE_COVERAGE.totals.docket_rows"),
        stage("built_and_judged",
              (docket - unjudged) if isinstance(docket, int) and isinstance(unjudged, int)
              else None, JUDGE_COVERAGE, "docket_rows - unjudged_total"),
        stage("first_terminal_cells", rate_v.get("first_terminal_cells"), JUDGING_RATE,
              "JUDGING_RATE.verdicts.first_terminal_cells"),
    ]
    prev = {s.get("stage"): s for s in (previous or {}).get("stages") or []
            if isinstance(s, dict)}
    upstream_backlog: Any = None
    for i, s in enumerate(rows):
        p = prev.get(s["stage"]) or {}
        if not isinstance(s["count"], int):
            s["state"] = UNMEASURED
        elif s["age_h"] is not None and s["age_h"] > STAGE_STALE_H:
            s["state"] = "STALE"
        elif isinstance(p.get("count"), int) and s["count"] == p["count"] and i > 0 \
                and isinstance(upstream_backlog, int) and upstream_backlog > 0:
            s["state"] = "STALLED"
        else:
            s["state"] = "MOVING" if isinstance(p.get("count"), int) else "FIRST_READING"
        s["delta_since_last_pass"] = (s["count"] - p["count"]
                                      if isinstance(s["count"], int)
                                      and isinstance(p.get("count"), int) else None)
        upstream_backlog = s["count"] if isinstance(s["count"], int) else None
    if isinstance(unjudged, int):
        rows[4]["backlog_unjudged"] = unjudged
    return rows


# ------------------------------------------------------------------------- the converter
def _ledger() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        with LEDGER.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("cell_id"):
                    out[str(r["cell_id"])] = r
    except OSError:
        pass
    return out


def lane_ok(symbol: str, family: str) -> tuple[bool, str]:
    """The two-lane rule at this door. A share CFD carries ONLY a cross-sectional class book;
    an instrument the broker registry does not classify carries nothing (absence is no
    permission); every other family is hypothesis-lane only."""
    try:
        from research import universe_policy as up
    except Exception as exc:
        return False, f"universe_policy unimportable ({type(exc).__name__})"
    lane = up.lane(symbol)
    if lane == up.HYPOTHESIS:
        return True, ""
    if up.is_equity(symbol):
        if family in up.CROSS_SECTIONAL_FAMILIES:
            return True, ""
        return False, "share CFD outside CROSS_SECTIONAL_FAMILIES (two-lane rule)"
    return False, f"instrument lane {lane}: not a hypothesis-lane MT5 instrument"


def compile_cells(source: str, rows: list[dict[str, Any]]
                  ) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], dict[str, int]]:
    """Rows -> (row, cell) pairs through the compiler's own `compile_row`; reasons for the rest."""
    from research import miner_candidate_compiler as mcc
    universe = mcc.known_symbols()
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    reasons: dict[str, int] = {}
    for row in rows:
        try:
            cands, disp = mcc.compile_row(source, row, universe)
        except Exception as exc:
            cands, disp = [], f"COMPILE_RAISED:{type(exc).__name__}"
        if not cands:
            reasons[disp] = reasons.get(disp, 0) + 1
            continue
        reasons[disp] = reasons.get(disp, 0) + 1
        pairs.extend((row, c) for c in cands)
    return pairs, reasons


def lake_cells(ds: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """exogenous_conditioner cells for one unconsumed lake series, on its declared targets."""
    try:
        from research import pack_cells as pc
    except Exception as exc:
        return [], f"pack_cells unimportable ({type(exc).__name__})"
    sid = ds["tokens"][0]
    pack = next((p for p in pc.packs() if str(p.get("id")) == sid), None)
    targets = pc.targets_of(pack) if pack else []
    if not targets:
        return [], "NEEDS_TARGET: no registered pack declares the instruments this series bears on"
    cols, _n, why = pc.signals_of(ds["path"])
    if not cols:
        return [], f"NO_SIGNAL: {why}"
    out = []
    for sig in cols[:3]:
        for sym in targets[:4]:
            out.append({"symbol": sym, "family": "exogenous_conditioner",
                        "params": {"source": sid, "signal": sig, "transform": "level_z",
                                   "threshold": 1.0, "side_when_high": 1},
                        "mechanism": f"the lake series {sid}.{sig} at a 1-sigma extreme of its "
                                     f"own history conditions {sym}; the pack declares {sym} "
                                     "as a target"})
    return out, ""


def convert(candidates: list[dict[str, Any]], now: datetime, *, dry_run: bool = False
            ) -> dict[str, Any]:
    """Donate NEW cells through `proposer_common.donate`, one file per trial_family.

    `candidates` rows carry symbol, family, params, origin (the idea / artifact / series id) and
    the source row's mechanism. A cell the ledger already holds is not re-donated (charged once);
    a lane refusal is counted and never donated; the pass and family bounds defer the rest.
    """
    from research import proposer_common as pcm
    try:
        from research import miner_candidate_compiler as mcc
        expand = mcc.expand_axes
    except Exception:
        def expand(cells: list[dict]) -> list[dict]:
            return cells
    held = _ledger()
    by_family: dict[str, list[dict[str, Any]]] = {}
    refused: dict[str, int] = {}
    deferred = already = 0
    seen: set[str] = set()
    n = 0
    for c in candidates:
        sym, fam = str(c.get("symbol") or ""), str(c.get("family") or "")
        params = dict(c.get("params") or {})
        if not sym or not fam:
            refused["incomplete"] = refused.get("incomplete", 0) + 1
            continue
        cid = pcm.identity(sym, fam, params)
        if cid in held or cid in seen:
            already += 1
            continue
        ok, why = lane_ok(sym, fam)
        if not ok:
            refused[why] = refused.get(why, 0) + 1
            continue
        if n >= MAX_CELLS_PER_PASS or len(by_family.get(fam, [])) >= \
                MAX_CELLS_PER_FAMILY_PER_PASS:
            deferred += 1
            continue
        seen.add(cid)
        n += 1
        by_family.setdefault(fam, []).append({**c, "cell_id": cid})
    charged: dict[str, int] = {}
    files: list[str] = []
    ledger_rows: list[dict[str, Any]] = []
    at = now.isoformat(timespec="seconds")
    for fam, cells in sorted(by_family.items()):
        rows = [{**pcm.candidate(SEAT, c["symbol"], fam, dict(c["params"]),
                                str(c.get("mechanism") or "mechanically converted idea"),
                                str(c.get("title") or c.get("origin") or "")[:300],
                                {"origin": c.get("origin"), "origin_class": c.get("origin_class"),
                                 "converted_by": SEAT}),
                 "trial_family": fam, "cell_id": c["cell_id"], "origin": c.get("origin")}
                for c in cells]
        # THE CHARGE: the cells the compiler will mint from these rows after its own axis
        # expansion (charts x sessions). Charging the pre-expansion count would under-count.
        try:
            tests = max(len(rows), len(expand([dict(r) for r in rows])))
        except Exception:
            tests = len(rows)
        charged[fam] = tests
        if not dry_run:
            path = pcm.donate(SEAT, rows, tests, suffix=f"cca_{fam}")
            files.append(str(path) if path else "")
        for c in cells:
            ledger_rows.append({"cell_id": c["cell_id"], "family": fam, "trial_family": fam,
                                "symbol": c["symbol"], "params": c["params"],
                                "origin": c.get("origin"), "origin_class": c.get("origin_class"),
                                "converted_at": at, "tests_charged_with_family": tests})
    if ledger_rows and not dry_run:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for r in ledger_rows:
                fh.write(json.dumps(r, default=str) + "\n")
    return {"donated": sum(len(v) for v in by_family.values()), "tests_run_by_family": charged,
            "tests_run_total": sum(charged.values()), "already_converted": already,
            "deferred_over_bound": deferred, "lane_refused": refused, "files": files,
            "new": ledger_rows, "dry_run": dry_run}


# ------------------------------------------------------------------------- issues
def issues_for(sources: list[dict[str, Any]], stages: list[dict[str, Any]]
               ) -> list[dict[str, Any]]:
    try:
        from research.issue_board import Issue
    except Exception:
        Issue = None
    out: list[dict[str, Any]] = []
    for s in sources:
        if s["verdict"] not in (NOT_WIRED, PARTIAL):
            continue
        sev = "BLIND" if s["verdict"] == NOT_WIRED else "DEGRADED"
        what = (f"{s['source']} produces output no converter takes"
                if s["verdict"] == NOT_WIRED else
                f"{s['source']} converts {s['share_converted']} of its rows; loss at "
                f"{s['loss_stage']}")
        repair = ("route it through proposer_common.donate / a merge_hypotheses SOURCE, or let "
                  "research/cell_conversion_audit.py convert it if its rows compile")
        args = (f"cell_conversion:{s['source']}", sev, what, str(s.get("why") or "")[:400],
                repair, False)
        out.append(Issue(*args).as_dict() if Issue else
                   dict(zip(("key", "severity", "what", "detail", "repair", "auto_repairable"),
                            args, strict=True)))
    for st in stages:
        if st.get("state") != "STALLED":
            continue
        args = (f"cell_conversion:stage:{st['stage']}", "STALLED",
                f"stage {st['stage']} did not move since the last pass while upstream holds rows",
                f"{st['basis']} = {st['count']} (artifact {st['artifact']}, {st['age_h']}h old)",
                None, False)
        out.append(Issue(*args).as_dict() if Issue else
                   dict(zip(("key", "severity", "what", "detail", "repair", "auto_repairable"),
                            args, strict=True)))
    return out


# ------------------------------------------------------------------------- the pass
def _artifact_rows(p: Path, limit: int) -> list[dict[str, Any]]:
    try:
        if p.stat().st_size > MAX_ARTIFACT_BYTES:
            return []
    except OSError:
        return []
    from research import miner_candidate_compiler as mcc
    out = []
    for r in mcc._iter_file_rows(p):
        out.append(r)
        if len(out) >= limit:
            break
    return out


def build(now: datetime | None = None, *, do_convert: bool = True,
          budget_s: float = 300.0) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    previous = _read(OUT)
    mc = _tail_keys(MINER_CANDIDATES, ("per_source", "compiled_at"))
    per_source = (mc or {}).get("per_source") if mc else None
    compiled_at = _parse_ts((mc or {}).get("compiled_at"))
    sdirs = seat_dirs()
    merge = _read(MERGE_REPORT)
    breadth = _tail_keys(PRODUCER_BREADTH, ("producers",))
    docket_names = merge_sources()
    corpus = module_corpus()
    sources: list[dict[str, Any]] = []
    legs = hourly_legs()
    non_emitters: list[str] = []
    unresolved: list[str] = []
    for leg, code in sorted(legs.items()):
        if code is not None and code.stem in DOOR_MODULES:
            non_emitters.append(leg)
            continue
        if code is None:
            unresolved.append(leg)
            if IDEA_FILE.search(leg):
                sources.append(_row(f"leg:{leg}", "leg", UNMEASURED,
                                    why="idea-named leg with no resolvable module"))
            continue
        info = classify(_text(code), code.stem)
        if not info["emitter"]:
            non_emitters.append(leg)
            continue
        sources.append(emitter_row(f"leg:{leg}", "leg", code, info, per_source=per_source,
                                   merge=merge, breadth=breadth, docket_names=docket_names,
                                   corpus=corpus, now=now, seat_dir_map=sdirs,
                                   compiled_at=compiled_at))
    leg_codes = {c for c in legs.values() if c is not None}
    seen_t1: set[Path] = set()
    for tid, files in sorted(tier1_offcycle().items()):
        for f in files:
            if f in leg_codes or f in seen_t1 or f.stem in DOOR_MODULES:
                continue
            seen_t1.add(f)
            info = classify(_text(f), f.stem)
            if info["emitter"]:
                sources.append(emitter_row(f"tier1:{tid}:{f.stem}", "tier1", f, info,
                                           per_source=per_source, merge=merge, breadth=breadth,
                                           docket_names=docket_names, corpus=corpus, now=now,
                                           seat_dir_map=sdirs, compiled_at=compiled_at))
    for seat, dirs in sorted(sdirs.items()):
        sources.append(seat_measure(seat, per_source, dirs, now, compiled_at))
    unwired_artifacts: list[Path] = []
    for p in idea_artifacts():
        row = artifact_row(p, docket_names, merge, corpus, now)
        sources.append(row)
        if row["verdict"] == NOT_WIRED:
            unwired_artifacts.append(p)
    # the judge's parked cells
    stock = handoff_stock()
    readers = door_readers(HANDOFF.name, corpus, "desks/mt5/research/judge_coverage.py")
    if stock.get("status") != "MEASURED":
        sources.append(_row("handoff:conversion_handoff", "handoff",
                            NOT_WIRED if not readers else UNMEASURED,
                            readers=readers, loss_stage=None if readers else "no converter",
                            why=stock.get("why", "") + ("" if readers else
                                                         "; no door-holding module reads it")))
    else:
        sources.append(_row("handoff:conversion_handoff", "handoff",
                            PARTIAL if readers else NOT_WIRED, emitted=stock["rows"],
                            parked=stock["by_class"], readers=readers,
                            loss_stage="parked in the judge's handoff" if readers
                            else "no converter",
                            why="the converter reads it; the rows still in the file are parked"
                            if readers else "no door-holding module reads the handoff"))
    # data-row sources
    fam_corpus = _family_corpus()
    pack_doc = _read(PACK_CELLS)
    data = data_sources()
    data_rows = [data_row(ds, fam_corpus, pack_doc) for ds in data]
    sources.extend(data_rows)

    # ---- the converter
    candidates: list[dict[str, Any]] = []
    parked_reasons: dict[str, dict[str, int]] = {}
    idea_path = idea_queue_path()
    ideas = idea_rows(idea_path) if idea_path else []
    open_ideas = [r for r in ideas if r["open"]]
    idea_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if open_ideas:
        prose = [{"title": r.get("item", "")[:300],
                  "text": f"{r.get('item', '')} {r.get('evidence', '')}",
                  "source": "idea_queue", "idea_id": r["idea_id"]} for r in open_ideas]
        try:
            idea_pairs, reasons = compile_cells("idea_queue", prose)
        except Exception as exc:
            idea_pairs, reasons = [], {f"COMPILER_UNAVAILABLE:{type(exc).__name__}": len(prose)}
        parked_reasons["idea_queue"] = reasons
        for row, c in idea_pairs:
            candidates.append({**c, "origin": row["idea_id"], "origin_class": "idea_queue",
                               "title": row["title"]})
    for p in unwired_artifacts:
        if time.monotonic() - t0 > 0.6 * budget_s:
            parked_reasons.setdefault("_budget", {})[p.name] = 1
            continue
        rows = _artifact_rows(p, MAX_ROWS_PER_ARTIFACT)
        if not rows:
            continue
        try:
            pairs, reasons = compile_cells(p.stem, rows)
        except Exception as exc:
            pairs, reasons = [], {f"COMPILER_UNAVAILABLE:{type(exc).__name__}": len(rows)}
        parked_reasons[f"artifact:{p.name}"] = reasons
        for _, c in pairs:
            candidates.append({**c, "origin": f"artifact:{p.name}", "origin_class": "artifact"})
    for ds, row in zip(data, data_rows, strict=True):
        if ds["kind"] == "lake" and row["verdict"] == NOT_WIRED:
            cells, why = lake_cells(ds)
            if why:
                parked_reasons[ds["id"]] = {why.split(":")[0]: 1}
                row["why"] += f"; converter: {why}"
            for c in cells:
                candidates.append({**c, "origin": ds["id"], "origin_class": "data"})
    conversion = convert(candidates, now, dry_run=not do_convert)
    new = conversion.pop("new")

    # ---- the idea queue's source row and the converted_ideas list
    held = _ledger() if do_convert else {r["cell_id"]: r for r in new}
    if do_convert:
        for r in new:
            held.setdefault(r["cell_id"], r)
    converted_ideas = sorted(
        ({"idea_id": r.get("origin"), "cell_id": r["cell_id"], "family": r.get("family"),
          "trial_family": r.get("trial_family"), "symbol": r.get("symbol"),
          "converted_at": r.get("converted_at")}
         for r in held.values() if r.get("origin_class") == "idea_queue"),
        key=lambda x: (str(x["converted_at"]), str(x["idea_id"])))
    ideas_converted = {c["idea_id"] for c in converted_ideas}
    if idea_path is None:
        sources.append(_row("idea_queue", "idea_queue", UNMEASURED,
                            why="no IDEA_QUEUE.md on this host (it lives in the owner threads' "
                                "project files, not the repository)"))
    else:
        n_open = len(open_ideas)
        conv = sum(1 for r in open_ideas if r["idea_id"] in ideas_converted)
        sources.append(_row("idea_queue", "idea_queue",
                            CONVERTING if n_open and conv >= n_open else PARTIAL,
                            path=str(idea_path), emitted=n_open, converted=conv,
                            cells=sum(1 for c in converted_ideas),
                            parked=parked_reasons.get("idea_queue", {}),
                            unconverted=n_open - conv,
                            share_converted=round(conv / n_open, 6) if n_open else UNMEASURED,
                            loss_stage=None if n_open and conv >= n_open else
                            "compile (no registered family or no priced instrument in the row)",
                            why="open rows run through the compiler's own compile_row; a row it "
                                "cannot compile stays parked with its reason"))

    stages = stage_flow(now, previous if isinstance(previous, dict) else None)

    # ---- totals
    by_verdict: dict[str, int] = dict.fromkeys(VERDICTS, 0)
    by_class: dict[str, dict[str, int]] = {}
    for s in sources:
        by_verdict[s["verdict"]] = by_verdict.get(s["verdict"], 0) + 1
        c = by_class.setdefault(s["class"], dict.fromkeys(VERDICTS, 0))
        c[s["verdict"]] += 1

    def _sum(key: str) -> int:
        # Legs and Tier-1 organs are VIEWS onto the seats and artifacts they write; counting them
        # beside those would count one row twice. Their verdicts are in by_verdict.
        return sum(int(s[key]) for s in sources
                   if s["class"] not in ("leg", "tier1") and isinstance(s.get(key), int))
    parked_now = sum(int(v) for s in sources for v in (s.get("parked") or {}).values()
                     if isinstance(v, int))
    converted_from_parking = len([r for r in held.values()
                                  if r.get("origin_class") in ("idea_queue", "artifact",
                                                               "data")])
    oldest: list[datetime] = []
    if stock.get("oldest_parked_utc"):
        t = _parse_ts(stock["oldest_parked_utc"])
        if t:
            oldest.append(t)
    for r in open_ideas:
        if r["idea_id"] in ideas_converted:
            continue
        t = _parse_ts(r.get("date"))
        if t:
            oldest.append(t)
    oldest_h = (round((now - min(oldest)).total_seconds() / 3600.0, 1) if oldest
                else UNMEASURED)
    sources.sort(key=lambda s: (VERDICTS.index(s["verdict"]), s["class"], s["source"]))
    issues = issues_for(sources, stages)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "rule": ("every producer, miner, seat, idea artifact, idea-queue row, parked cell and "
                 "data source the desk holds, DERIVED, each with how its output reaches the "
                 "gauntlet and a verdict: CONVERTING, PARTIAL (loss stage named), NOT_WIRED, "
                 "UNMEASURED (absent artifact; never a zero). Mechanical gaps are converted "
                 "through proposer_common.donate, one file per trial_family, tests_run charged "
                 "per family."),
        "parked_basis": ("still_parked = parked units measured now (handoff rows by class, "
                         "compiler deepening tasks, open idea rows the compiler could not "
                         "compile); converted = cells this leg has converted out of parking "
                         "(its ledger); parked = the two together"),
        "parked": parked_now + converted_from_parking,
        "converted": converted_from_parking,
        "still_parked": parked_now,
        "oldest_parked_age_h": oldest_h,
        "totals": {
            "sources": len(sources), "by_verdict": by_verdict, "by_class": by_class,
            "emitted": _sum("emitted"), "converted": _sum("converted"), "cells": _sum("cells"),
            "dropped_with_reason": _sum("dropped"), "unconverted": _sum("unconverted"),
            "parked": parked_now,
            "share_converted": _share(sources),
            "basis": "sums over seats, artifacts, the handoff, the idea queue and data sources "
                     "whose counts are MEASURED (legs and Tier-1 organs are views onto those and "
                     "are not summed twice); UNMEASURED rows add nothing and are counted in "
                     "by_verdict",
        },
        "coverage": {"hourly_legs": len(legs), "emitting_legs": sum(
            1 for s in sources if s["class"] == "leg"), "non_emitting_legs": len(non_emitters),
            "legs_unresolved": unresolved, "docket_sources": docket_names,
            "seat_roots": [str(r) for r in INTEL_ROOTS]},
        "stages": stages,
        "stalled_stages": [s["stage"] for s in stages if s.get("state") == "STALLED"],
        "handoff": stock,
        "conversion": {**conversion, "parked_by_reason": parked_reasons,
                       "seat": SEAT, "ledger": LEDGER.relative_to(ROOT).as_posix(),
                       "charge_rule": "one donation file per trial_family; tests_run = cells "
                                      "after the compiler's axis expansion; a ledgered cell is "
                                      "never donated (or charged) twice"},
        "converted_ideas": converted_ideas,
        "idea_queue": {"path": str(idea_path) if idea_path else None, "rows": len(ideas),
                       "open": len(open_ideas),
                       "status_column_written": False,
                       "why_not_written": "the queue is the owner threads' file, outside this "
                                          "repository; the mapping is published here instead"},
        "issues": issues,
        "sources": sources,
        "wall_s": round(time.monotonic() - t0, 2),
    }


def _share(sources: list[dict[str, Any]]) -> float | str:
    """Converted over emitted (net of named refusals), over sources that measured BOTH."""
    em = cv = 0
    for s in sources:
        if s["class"] in ("leg", "tier1"):
            continue
        if isinstance(s.get("emitted"), int) and isinstance(s.get("converted"), int):
            em += s["emitted"] - (s["dropped"] if isinstance(s.get("dropped"), int) else 0)
            cv += s["converted"]
    return round(cv / em, 6) if em > 0 else UNMEASURED


def write(doc: dict[str, Any], out: Path | None = None) -> Path:
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, target)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's form)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-convert", action="store_true",
                    help="measure only; donate nothing and write no ledger row")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = build(do_convert=not a.no_convert, budget_s=a.budget_s)
    path = write(doc)
    t = doc["totals"]
    print(f"cell conversion audit: {t['sources']} source(s) {t['by_verdict']}; "
          f"converted this pass {doc['conversion']['donated']} cell(s), tests_run "
          f"{doc['conversion']['tests_run_total']}; stalled stages {doc['stalled_stages']}; "
          f"-> {path}")
    if a.json:
        print(json.dumps(doc, indent=1, default=str)[:20000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
