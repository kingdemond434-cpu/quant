"""Acceptance evaluators for the institutional footprint (IF01..IF06).

`global_research_acceptance.audit()` runs one of these for every requirement row that names an
`evaluator`, so the footprint's architectural claims are judged hourly with the
`global_research_os` leg and published in `reports/GLOBAL_RESEARCH_ACCEPTANCE.json`, beside the
R/MI rows.

Each evaluator reads the repository and the artifacts under `root` and returns
`{"verdict": PASS | FAIL | UNMEASURED, "violations": [...], "unmeasured": [...],
"measured": {...}}`.
A violation found is FAIL. An absent, unreadable or stale artifact is UNMEASURED, never PASS
(L1.28a: absence never resolves to a clean verdict). These evaluators check architecture only:
they say nothing about whether a footprint cell makes money.

Standard library and yaml only, so the audit never has to import the engine (pandas, the
registry) to judge it. The engine's constants are read from its source text.
"""
from __future__ import annotations

import ast
import contextlib
import csv
import importlib.util
import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK_REL = Path("desks") / "mt5"
ENGINE = DESK_REL / "research" / "institutional_footprint.py"
ONTOLOGY = DESK_REL / "research" / "countries" / "institutional" / "ontology.py"
ROSTER = DESK_REL / "data" / "source_rosters" / "institutional_footprint.yaml"
RULINGS = DESK_REL / "data" / "institutional_coverage_rulings.json"
STATE_DIR = DESK_REL / "data" / "institutional"
SEARCH_QUEUE = STATE_DIR / "search_queue.json"
EMITTED = STATE_DIR / "cells_emitted.json"
CULTURE_LOG = STATE_DIR / "cell_culture.jsonl"
SERIES = DESK_REL / "data" / "lake" / "series"
COVERAGE = DESK_REL / "reports" / "INSTITUTIONAL_COVERAGE.json"
STATE_REPORT = DESK_REL / "reports" / "INSTITUTIONAL_STATE.json"
DONATIONS = DESK_REL / "data" / "intelligence" / "moat_factory"
HOURLY = DESK_REL / "research" / "hourly_cycle.py"
ATTESTATION = Path("docs") / "research" / "runtime_state.json"

LEG = "institutional_footprint"
STATE_PREFIX = "institutional_state."
FIRST_RELEASE = "FIRST_RELEASE"
#: The same freshness bar the audit applies to runtime proofs (MAX_RUNTIME_AGE_H).
MAX_AGE_H = 26.0
#: Statuses a human or scout may DECLARE (the atlas header). ACTIVE is never one: it is measured.
DECLARABLE = frozenset({"DISCOVERED_NOT_INGESTED", "PAID_PUBLIC_PROXY", "BLOCKED_SUBSTITUTE",
                        "NOT_PUBLISHED", "WATCH", "ACTIVE_CANDIDATE", "TESTED_NO_INFORMATION",
                        "NOT_RELEVANT"})
CANONICAL = re.compile(r"institutional\.[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+")
#: Examples kept per violation class: the counts are complete, the examples are a sample.
EXAMPLES = 8
#: Newest donation files read when tracing a cell through the registry door.
DONATION_FILES = 400


# =========================================================================== plumbing
class _Verdict:
    def __init__(self) -> None:
        self.violations: list[str] = []
        self.unmeasured: list[str] = []
        self.measured: dict[str, Any] = {}

    def fail(self, what: str, items: Iterable[Any] = ()) -> None:
        got = sorted({str(i) for i in items})
        self.violations.append(f"{what} ({len(got)}): {', '.join(got[:EXAMPLES])}"
                               if got else what)

    def fail_if(self, what: str, items: Iterable[Any]) -> None:
        got = list(items)
        if got:
            self.fail(what, got)

    def done(self) -> dict[str, Any]:
        verdict = ("FAIL" if self.violations else "UNMEASURED" if self.unmeasured else "PASS")
        return {"verdict": verdict, "violations": self.violations,
                "unmeasured": self.unmeasured, "measured": self.measured}


def _ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _artifact(v: _Verdict, root: Path, rel: Path, now: datetime) -> dict[str, Any] | None:
    """A JSON artifact stamped `at`, fresh within MAX_AGE_H; else None and an UNMEASURED note."""
    path = root / rel
    if not path.exists():
        v.unmeasured.append(f"{rel.as_posix()}: absent")
        return None
    doc = _json(path)
    if not isinstance(doc, dict):
        v.unmeasured.append(f"{rel.as_posix()}: unreadable")
        return None
    at = _ts(doc.get("at"))
    if at is None:
        v.unmeasured.append(f"{rel.as_posix()}: no internal timestamp")
        return None
    age_h = (now - at).total_seconds() / 3600.0
    if age_h > MAX_AGE_H:
        v.unmeasured.append(f"{rel.as_posix()}: stale ({age_h:.1f}h > {MAX_AGE_H:g}h)")
        return None
    return doc


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with contextlib.suppress(OSError):
        for line in path.read_text("utf-8").splitlines():
            with contextlib.suppress(ValueError):
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
    return out


def _roster(root: Path) -> list[dict[str, Any]] | None:
    try:
        import yaml
        doc = yaml.safe_load((root / ROSTER).read_text("utf-8")) or {}
    except Exception:
        return None
    rows = doc.get("sources") if isinstance(doc, Mapping) else doc
    return [dict(r) for r in rows or [] if isinstance(r, Mapping)]


def _ontology(root: Path) -> Any:
    """The ontology module of THIS root (pure: `re` and `typing` only), or None."""
    path = root / ONTOLOGY
    if not path.exists():
        return None
    name = f"_if_acceptance_ontology_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        return None
    return mod


def _tree(root: Path, rel: Path) -> ast.Module | None:
    try:
        return ast.parse((root / rel).read_text("utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None


def _assigned(tree: ast.Module, name: str) -> ast.expr | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name
                                                for t in node.targets):
            return node.value
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == name):
            return node.value
    return None


def _constant(tree: ast.Module, name: str) -> Any:
    node = _assigned(tree, name)
    return node.value if isinstance(node, ast.Constant) else None


def _days(tree: ast.Module, name: str) -> float | None:
    """`X = pd.Timedelta(days=7)` / `timedelta(days=30)` -> the days."""
    node = _assigned(tree, name)
    if isinstance(node, ast.Call):
        for kw in node.keywords:
            if kw.arg == "days" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, int | float):
                return float(kw.value.value)
    return None


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _called(fn: ast.AST | None) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn) if fn is not None else ():
        if isinstance(node, ast.Call):
            f = node.func
            out.add(f.attr if isinstance(f, ast.Attribute) else f.id
                    if isinstance(f, ast.Name) else "")
    return out


def _string_set(node: ast.AST | None) -> set[str]:
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
            and isinstance(n.value, str)} if node is not None else set()


def _frame(path: Path) -> tuple[list[str], list[dict[str, str]]] | None:
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return list(reader.fieldnames or []), list(reader)
    except (OSError, csv.Error, UnicodeDecodeError):
        return None


def _vintages(rows: list[dict[str, str]], col: str) -> int:
    """Distinct available_time stamps at which `col` carries a reading (the engine's gate)."""
    return len({r.get("available_time") for r in rows
                if str(r.get(col) or "").strip() not in ("", "nan", "NaN")})


def _lag_hours(row: Mapping[str, Any]) -> float:
    """The engine's conservative lag (`institutional_footprint.lag_hours_of`)."""
    fetch = row.get("fetch") or {}
    if isinstance(fetch, Mapping) and fetch.get("available_offset_hours") is not None:
        return float(fetch["available_offset_hours"])
    return (float(row.get("publication_lag_days") or 0) + 1.0) * 24.0


def _key_source(key: str) -> str:
    return key.split("|", 1)[0]


# =========================================================================== IF01 atlas
def if01_atlas(root: Path, now: datetime) -> dict[str, Any]:
    v = _Verdict()
    rows = _roster(root)
    if not rows:
        v.unmeasured.append(f"{ROSTER.as_posix()}: absent, unreadable or empty")
        return v.done()
    ids = [str(r.get("id") or "") for r in rows]
    v.measured["rows"] = len(rows)
    v.fail_if("row without an id", [i for i, x in enumerate(ids) if not x])
    seen: dict[str, int] = {}
    for i in ids:
        seen[i] = seen.get(i, 0) + 1
    v.fail_if("duplicate atlas id", [i for i, n in seen.items() if n > 1 and i])
    names: dict[str, list[str]] = {}
    bad_form, no_lane_id, no_note, bad_status, lane_ids = [], [], [], [], 0
    for r in rows:
        rid = str(r.get("id") or "")
        canon = str(r.get("atlas_id") or rid)
        parts = canon.split(".")
        others = {str(x) for x in r.get("atlas_ids") or []}
        if (not CANONICAL.fullmatch(canon) or parts[1] != str(r.get("jurisdiction"))
                or parts[2] != str(r.get("publisher"))
                or (parts[3] != str(r.get("dataset")) and canon not in others)):
            bad_form.append(rid)
        names.setdefault(canon, []).append(rid)
        if not rid.startswith("institutional."):
            # Another lane registered the dataset first: its id stands, the atlas name rides
            # as `atlas_id`, and `aliases` names every other lane id for it.
            lane_ids += 1
            if not r.get("atlas_id") or not isinstance(r.get("aliases"), list):
                no_lane_id.append(rid)
        if not str(r.get("pit_note") or "").strip():
            no_note.append(rid)
        if str(r.get("declared_status") or "") not in DECLARABLE:
            bad_status.append(f"{rid}={r.get('declared_status')!r}")
    v.measured.update({"lane_registered_first": lane_ids,
                       "with_pit_note": len(rows) - len(no_note)})
    v.fail_if("id not institutional.<jurisdiction>.<publisher>.<dataset>", bad_form)
    v.fail_if("one atlas name claimed by two rows",
              [f"{k}<-{'/'.join(x)}" for k, x in names.items() if len(x) > 1])
    id_set = set(ids)
    v.fail_if("an alias that is another row's id", [
        f"{r.get('id')}:{a}" for r in rows for a in r.get("aliases") or []
        if str(a) in id_set and str(a) != r.get("id")])
    v.fail_if("lane-registered row without atlas_id/aliases", no_lane_id)
    v.fail_if("row without a pit_note", no_note)
    v.fail_if("row without a declarable status (ACTIVE is measured, never declared)", bad_status)
    return v.done()


# =========================================================================== IF02 PIT
def _revised_frames(root: Path, cov: Mapping[str, Any] | None,
                    atlas_ids: Iterable[str]) -> tuple[set[str], int]:
    """Every footprint frame that is not FIRST_RELEASE: the coverage report's list plus any
    atlas or state frame in the lake whose pit_grade column says otherwise (other lanes' series
    share the lake and are not read). Returns (ids, frames read)."""
    out = {str(x) for x in ((cov or {}).get("pit") or {}).get("latest_revised_frames") or []}
    n = 0
    series = root / SERIES
    paths = [series / f"{i}.csv" for i in sorted(set(atlas_ids))]
    paths += sorted(series.glob(f"{STATE_PREFIX}*.csv"))
    for p in paths:
        if not p.exists():
            continue
        got = _frame(p)
        if got is None:
            continue
        cols, rows = got
        n += 1
        if "pit_grade" in cols and any(r.get("pit_grade") != FIRST_RELEASE for r in rows):
            out.add(p.stem)
    return out, n


def if02_pit(root: Path, now: datetime) -> dict[str, Any]:
    v = _Verdict()
    tree = _tree(root, ENGINE)
    if tree is None:
        v.unmeasured.append(f"{ENGINE.as_posix()}: absent or unparsable")
        return v.done()
    if "cftc_available" not in _called(_function(tree, "cot_release_times")):
        v.fail("cot_release_times does not stamp by futures_state.cftc_available")
    if "cot_release_times" not in _called(_function(tree, "cot_features")):
        v.fail("cot_features does not take available_time from cot_release_times")
    for fn in ("macro_features", "planned_cells"):
        if "pit_ok" not in _called(_function(tree, fn)):
            v.fail(f"{fn} reads frames without the pit_ok FIRST_RELEASE gate")
    cov = _artifact(v, root, COVERAGE, now)
    rows = {str(r.get("id")): r for r in _roster(root) or []}
    revised, n_frames = _revised_frames(root, cov, rows)
    early: list[str] = []
    for sid, row in rows.items():
        got = _frame(root / SERIES / f"{sid}.csv")
        if got is None:
            continue
        lag = timedelta(hours=_lag_hours(row)) - timedelta(minutes=1)
        for r in got[1]:
            ev, av = _ts(r.get("event_time")), _ts(r.get("available_time"))
            if ev is None or av is None or av < ev + lag:
                early.append(f"{sid}@{r.get('event_time')}")
                break
    v.fail_if("frame row stamped before its release lag", early)
    states = sorted((root / SERIES).glob(f"{STATE_PREFIX}*.csv"))
    v.fail_if("state frame not FIRST_RELEASE", [p.stem for p in states if p.stem in revised])
    culture = _jsonl(root / CULTURE_LOG)
    reached = {f"{c.get('cell_id')}<-{s}" for c in culture
               for s in [c.get("source_id"), *(c.get("source_ids") or [])]
               if s and str(s) in revised}
    v.fail_if("LATEST_REVISED frame reached a state or cell", reached)
    emitted = _json(root / EMITTED)
    keys = [str(k) for k in (emitted or {}).get("keys") or []] if isinstance(emitted, dict) else []
    v.fail_if("cell key minted from a LATEST_REVISED frame",
              [k for k in keys if _key_source(k) in revised])
    v.measured.update({"frames_read": n_frames, "latest_revised_frames": len(revised),
                       "state_frames": len(states), "culture_rows": len(culture),
                       "cell_keys": len(keys)})
    if not n_frames and not culture and not keys:
        v.unmeasured.append("no frame, cell or culture row on this host: nothing reached a state")
    return v.done()


# =========================================================================== IF03 states
def _frame_refreshed(root: Path, row: Mapping[str, Any]) -> datetime | None:
    f = row.get("fetch") or {}
    if isinstance(f, Mapping) and f.get("kind") == "lake_parquet":
        paths = [q for g in (f.get("globs") or [f.get("glob")]) if g for q in root.glob(str(g))]
    else:
        paths = [root / SERIES / f"{row.get('id')}.csv"]
    times = []
    for q in paths:
        with contextlib.suppress(OSError):
            times.append(q.stat().st_mtime)
    return datetime.fromtimestamp(max(times), tz=UTC) if times else None


def if03_states(root: Path, now: datetime) -> dict[str, Any]:
    v = _Verdict()
    tree = _tree(root, ENGINE)
    if tree is None:
        v.unmeasured.append(f"{ENGINE.as_posix()}: absent or unparsable")
        return v.done()
    if _days(tree, "STATE_MAX_AGE") != 7:
        v.fail("STATE_MAX_AGE is not 7 days")
    if _days(tree, "ACTIVE_WINDOW") != 30:
        v.fail("ACTIVE_WINDOW is not 30 days")
    rows = _roster(root) or []
    v.fail_if("ACTIVE declared in the atlas", [r.get("id") for r in rows
                                               if r.get("declared_status") == "ACTIVE"])
    doc = _artifact(v, root, STATE_REPORT, now)
    if doc is not None:
        no_interval, stale_live, measured_n, unmeasured_n = [], [], 0, 0
        for asset, states in (doc.get("states") or {}).items():
            for sid, s in (states or {}).items():
                name = f"{asset}.{sid}"
                age = s.get("age_hours")
                p, lo, hi = s.get("p"), s.get("lo"), s.get("hi")
                if s.get("status") == "MEASURED":
                    measured_n += 1
                    if not all(isinstance(x, int | float) for x in (p, lo, hi)) or not (
                            lo <= p <= hi):
                        no_interval.append(name)
                    if not isinstance(age, int | float) or age > 7 * 24:
                        stale_live.append(name)
                else:
                    unmeasured_n += 1
                    if p is not None:
                        stale_live.append(name)
        v.fail_if("MEASURED state without a 95% interval around p", no_interval)
        v.fail_if("state older than 7 days published as live", stale_live)
        reg = doc.get("regimes") or {}
        v.fail_if("UNMEASURED state given a regime", [
            f"{a}.{sid}" for a, states in (doc.get("states") or {}).items()
            for sid, s in (states or {}).items()
            if s.get("p") is None and sid in (reg.get(a) or {})
            and (reg.get(a) or {}).get(sid) != "UNMEASURED"])
        v.measured.update({"states_measured": measured_n, "states_unmeasured": unmeasured_n})
    cov = _artifact(v, root, COVERAGE, now)
    if cov is not None:
        at = _ts(cov.get("at")) or now
        emitted = _json(root / EMITTED)
        credited = (emitted or {}).get("credited") if isinstance(emitted, dict) else None
        credited = credited if isinstance(credited, dict) else {}
        by_id = {str(r.get("id")): r for r in rows}
        window = timedelta(days=30)
        unproven = []
        active = [k for k, s in (cov.get("row_status") or {}).items() if s == "ACTIVE"]
        for sid in active:
            refreshed = _frame_refreshed(root, by_id.get(sid) or {"id": sid})
            fed = _ts(credited.get(sid))
            if refreshed is None or at - refreshed > window or fed is None or at - fed > window:
                unproven.append(sid)
        v.fail_if("ACTIVE without a frame refreshed AND a cell fed within 30 days", unproven)
        v.measured["active_sources"] = len(active)
    return v.done()


# =========================================================================== IF04 cells
def _donated(root: Path) -> list[dict[str, Any]]:
    files = sorted((root / DONATIONS).glob("*.json"), key=lambda p: p.name)[-DONATION_FILES:]
    out: list[dict[str, Any]] = []
    for p in files:
        doc = _json(p)
        rows = (doc.get("candidates") or doc.get("discoveries") or []
                if isinstance(doc, dict) else doc if isinstance(doc, list) else [])
        out.extend(r for r in rows if isinstance(r, dict))
    return out


def if04_cells(root: Path, now: datetime) -> dict[str, Any]:
    v = _Verdict()
    tree = _tree(root, ENGINE)
    if tree is None:
        v.unmeasured.append(f"{ENGINE.as_posix()}: absent or unparsable")
        return v.done()
    for name, want in (("TRAIN_FRACTION", 0.5), ("MIN_VINTAGES", 60),
                       ("SIDE_SELECTION_TRIALS", 2)):
        if _constant(tree, name) != want:
            v.fail(f"{name} is not {want}")
    if "MIN_VINTAGES" not in {n.id for n in ast.walk(_function(tree, "planned_cells") or tree)
                              if isinstance(n, ast.Name)}:
        v.fail("planned_cells does not gate on MIN_VINTAGES")
    if "enqueue_candidate" not in _called(_function(tree, "emit_cells")):
        v.fail("emit_cells does not mint through the registry door (enqueue_candidate)")
    emitted = _json(root / EMITTED)
    if not isinstance(emitted, dict):
        v.unmeasured.append(f"{EMITTED.as_posix()}: absent or unreadable (no cell minted here)")
        return v.done()
    keys = [str(k) for k in emitted.get("keys") or []]
    v.fail_if("cell key that is not source|signal|transform|symbol|chart",
              [k for k in keys if len(k.split("|")) != 5])
    if emitted.get("spec") != "purged_trade_from/1":
        v.fail(f"emitted ledger spec {emitted.get('spec')!r} is not the purged rule")
    thin = []
    frames: dict[str, list[dict[str, str]] | None] = {}
    for k in keys:
        src, sig = k.split("|")[:2] if "|" in k else (k, "")
        if src not in frames:
            got = _frame(root / SERIES / f"{src}.csv")
            frames[src] = got[1] if got else None
        if frames[src] is not None and _vintages(frames[src] or [], sig) < 60:
            thin.append(k)
    v.fail_if("cell minted from a column with fewer than 60 vintages", thin)
    culture = _jsonl(root / CULTURE_LOG)
    sides: dict[str, set[Any]] = {}
    ids: dict[str, int] = {}
    unfit = []
    for c in culture:
        fit = c.get("side_fit") or {}
        ids[str(c.get("cell_id"))] = ids.get(str(c.get("cell_id")), 0) + 1
        if (fit.get("side") not in (1, -1) or not fit.get("train_end")
                or fit.get("selection_trials") != 2 or not c.get("claim_family")):
            unfit.append(c.get("cell_id"))
        sides.setdefault(str(c.get("claim_family")), set()).add(fit.get("side"))
    v.fail_if("cell without one side learned on the train span and its 2 trials", unfit)
    v.fail_if("claim family carrying both sides", [f for f, s in sides.items() if len(s) > 1])
    v.fail_if("cell enqueued more than once", [i for i, n in ids.items() if n > 1])
    by_cell = {str(c.get("cell_id")): c for c in culture}
    door = [d for d in _donated(root)
            if str((d.get("evidence") or {}).get("candidate_id")) in by_cell]
    v.fail_if("donated cell lost its claim family or its 2 selection trials", [
        (d.get("evidence") or {}).get("candidate_id") for d in door
        if d.get("claim_selection_trials") != 2 or d.get("claim_family") != by_cell[
            str((d.get("evidence") or {}).get("candidate_id"))].get("claim_family")])
    v.measured.update({"cell_keys": len(keys), "culture_rows": len(culture),
                       "claim_families": len(sides), "donated_through_door": len(door)})
    if not culture:
        v.unmeasured.append(f"{CULTURE_LOG.as_posix()}: no cell minted on this host")
    elif not door:
        v.unmeasured.append("no footprint cell found in data/intelligence/moat_factory yet: the "
                            "registry door's donation is unmeasured")
    return v.done()


# =========================================================================== IF05 coverage
def if05_coverage(root: Path, now: datetime) -> dict[str, Any]:
    v = _Verdict()
    onto = _ontology(root)
    if onto is None:
        v.unmeasured.append(f"{ONTOLOGY.as_posix()}: absent or not importable")
        return v.done()
    rulings = _json(root / RULINGS)
    if not isinstance(rulings, dict):
        v.unmeasured.append(f"{RULINGS.as_posix()}: absent or unreadable")
        rulings = {}
    cell_rul = dict(rulings.get("cells") or {}) if ("cells" in rulings or "roles" in rulings) \
        else dict(rulings)
    v.measured["rulings_uncited"] = sum(1 for r in cell_rul.values()
                                        if onto.ruled_status(r) == onto.UNMEASURED)
    cov = _artifact(v, root, COVERAGE, now)
    queue_doc = _artifact(v, root, SEARCH_QUEUE, now)
    if cov is None or queue_doc is None:
        return v.done()
    grid = cov.get("grid") or {}
    sources = cov.get("grid_sources") or {}
    unsearched = [f"{j}|{c}" for j, cells in grid.items() for c, s in cells.items()
                  if s == onto.UNSEARCHED]
    v.fail_if("UNSEARCHED cell (the sweep is not done)", unsearched)
    queue = [q for q in queue_doc.get("queue") or [] if isinstance(q, dict)]
    asked_cells = {f"{q.get('jurisdiction')}|{q.get('source_class')}" for q in queue
                   if q.get("source_class")}
    asked_roles = {f"{q.get('jurisdiction')}|{q.get('role')}" for q in queue if q.get("role")}
    v.fail_if("UNMEASURED cell missing from search_queue.json", [
        f"{j}|{c}" for j, cells in grid.items() for c, s in cells.items()
        if s == onto.UNMEASURED and not (sources.get(j) or {}).get(c)
        and f"{j}|{c}" not in asked_cells])
    skip = {"global", *getattr(onto, "REGION_PACKS", ())}
    v.fail_if("role gap missing from search_queue.json", [
        f"{j}|{r}" for j, roles in (cov.get("role_gaps") or {}).items() if j not in skip
        for r in roles or [] if f"{j}|{r}" not in asked_roles])
    v.fail_if("cell closed by a ruling that cites no evidence", [
        k for k, r in cell_rul.items() if "|" in k
        and (grid.get(k.split("|", 1)[0]) or {}).get(k.split("|", 1)[1]) in onto.CLOSED_STATUSES
        and not (sources.get(k.split("|", 1)[0]) or {}).get(k.split("|", 1)[1])
        and onto.ruling_defect(r)])
    v.measured.update({"cells": sum(len(c) for c in grid.values()),
                       "unsearched": len(unsearched), "queue": len(queue)})
    return v.done()


# =========================================================================== IF06 wiring
def if06_wiring(root: Path, now: datetime) -> dict[str, Any]:
    v = _Verdict()
    tree = _tree(root, HOURLY)
    if tree is None:
        v.unmeasured.append(f"{HOURLY.as_posix()}: absent or unparsable")
        return v.done()
    if LEG not in _string_set(_assigned(tree, "CORE_LEGS")):
        v.fail("institutional_footprint is not in hourly_cycle CORE_LEGS")
    producers = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "_producer"
                 and len(n.args) >= 2 and all(isinstance(a, ast.Constant) for a in n.args[:2])
                 and n.args[0].value == LEG]  # type: ignore[attr-defined]
    if not any(p.args[1].value == "research/institutional_footprint.py"  # type: ignore[attr-defined]
               for p in producers):
        v.fail("hourly_cycle has no _producer clock for research/institutional_footprint.py")
    att = _json(root / ATTESTATION)
    organ = next((o for o in (att or {}).get("organs") or [] if isinstance(o, dict)
                  and o.get("organ") == f"leg:{LEG}"), None) if isinstance(att, dict) else None
    if organ is None:
        v.fail(f"no attestation row leg:{LEG} in {ATTESTATION.as_posix()}")
    else:
        if organ.get("clock") != f"hourly_cycle:{LEG}":
            v.fail(f"attestation clock is {organ.get('clock')!r}")
        if organ.get("artifact_declared") != COVERAGE.as_posix():
            v.fail(f"attestation artifact is {organ.get('artifact_declared')!r}")
        state = str(organ.get("state") or "")
        v.measured["attestation_state"] = state
        if state == "MISSING":
            v.fail("attestation MISSING: the host recorded the leg running and no artifact")
        elif state != "LIVE":
            v.unmeasured.append(f"attestation state {state or 'absent'}: "
                                f"{str(organ.get('why') or '')[:120]}")
    for rel in (COVERAGE, STATE_REPORT, SEARCH_QUEUE):
        _artifact(v, root, rel, now)
    return v.done()


EVALUATORS: dict[str, Callable[[Path, datetime], dict[str, Any]]] = {
    "institutional_footprint.atlas": if01_atlas,
    "institutional_footprint.pit": if02_pit,
    "institutional_footprint.states": if03_states,
    "institutional_footprint.cells": if04_cells,
    "institutional_footprint.coverage": if05_coverage,
    "institutional_footprint.wiring": if06_wiring,
}
