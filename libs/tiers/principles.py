"""THE SEVEN PRINCIPLES, MAPPED TO THEIR ORGANS AND MEASURED (ARCH-32, PM delivery check
2026-10-07).

The item: *enforce autonomously and forever -- no sacred strategy/model/source/geography;
structural change triggers relearning; cash is an allocation; research never stops; validation
never relaxes; execution teaches research; ontology stays open.* The delivery check found each
principle scattered across organs and no map from a principle to what enforces it, so nothing
noticed when an enforcing organ went away or a principle quietly stopped holding.

TWO HALVES, ONE PASS.

  * THE MAP (`docs/research/principles_map.json`) is data: each principle names the legs, fences,
    box tasks and code organs that enforce it today. `resolve_organs` proves each one still
    exists where the map says -- a leg on the hourly cycle, a fence named by the law gate, a task
    in the box manifest, a code organ still carrying its token. A principle with no resolving
    organ is UNENFORCED; an organ that no longer resolves is a MISSING_ORGAN finding.
  * THE MEASUREMENT (`MEASURES`) reads live artifacts and code and returns MET, VIOLATED or
    UNMEASURED with named findings. ABSENCE IS UNMEASURED, NEVER MET (L1.28a): a host with no
    allocator artifact has not shown that cash is scored, it has shown nothing.

WHAT THIS NEVER DOES. It caps no capital, vetoes no trade, shrinks no fraction and lowers no
heat: every finding is about research and validation discipline. The one action it adds is in
`libs/ops/queue_cycle._structural_change` (P2's missing wire), and that action is a RE-JUDGE --
a `recertify` task the validation role already owns -- never a demotion.

The ratchet (which findings are pre-existing debt and which are arrivals) lives in
`scripts/check_principles.py`; the hourly leg is `desks/mt5/research/principles_enforcement.py`.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK_REL = "desks/mt5"
MAP_REL = "docs/research/principles_map.json"

MET = "MET"
VIOLATED = "VIOLATED"
UNMEASURED = "UNMEASURED"
UNENFORCED = "UNENFORCED"
VERDICTS = (MET, VIOLATED, UNMEASURED, UNENFORCED)

#: The hourly cycle counts as RUNNING on this host when its compute ledger has a row this recent.
#: Staleness findings are only issued on a host where the cycle runs: on a cloud clone an old
#: artifact means "this machine does not run the desk", which is UNMEASURED, not a breach.
CYCLE_FRESH_S = 6 * 3600
#: A mining or judge leg silent this long, on a host whose cycle IS running, has stopped.
RESEARCH_SILENCE_S = 12 * 3600
#: How long a structural-change trigger may wait for its re-judge task (one queue_cycle pass
#: plus slack) before it counts as unanswered.
RELEARN_GRACE_S = 2 * 3600
#: A research consumer of fills may lag the newest fill by this much before it is stale.
FEEDBACK_LAG_S = 48 * 3600
#: A detector artifact older than this has said nothing about the present.
DETECTOR_FRESH_S = 48 * 3600
#: The ontology must show growth inside this window (when history reaches back that far).
ONTOLOGY_WINDOW_DAYS = 14
#: gate_spec versions read from git history for the threshold ratchet.
GATE_HISTORY_VERSIONS = 40

GATE_SPEC_REL = "desks/mt5/policy/gate_spec.yaml"
MANIFEST_REL = "desks/mt5/data/IMMUTABLE_MANIFEST.json"
HOURLY_REL = "desks/mt5/research/hourly_cycle.py"
LAW_GATE_REL = "scripts/run_law_gate.py"
BOX_TASKS_REL = "desks/mt5/ops/box_tasks.manifest"
COMPUTE_LEDGER_REL = "desks/mt5/data/compute_ledger.jsonl"
TASK_QUEUE_REL = "desks/mt5/data/task_queue.jsonl"
SLEEVES_REL = "desks/mt5/data/sleeves.json"
DIST_SHIFT_REL = "desks/mt5/reports/DIST_SHIFT.json"
DECAY_REL = "desks/mt5/data/decay_live.json"
ALLOCATION_REL = "desks/mt5/reports/pf_allocation.json"
THROUGHPUT_REL = "desks/mt5/reports/JUDGING_THROUGHPUT.json"
LIVE_LEDGER_REL = "desks/mt5/data/live_ledger.jsonl"
ROBUST_ELOG_REL = "libs/portfolio/robust_elog.py"

#: Registries whose rows are scanned for a flag that would make a row exempt from retirement.
SOURCE_REGISTRIES = ("desks/mt5/data/sleeves.json", "desks/mt5/data/deep_forest_sources.json",
                     "desks/mt5/data/free_stack_sources.json", "desks/mt5/data/asia_sources.json",
                     "desks/mt5/data/data_registry.json")
#: A row key that, set truthy, declares the row beyond retirement or beyond the gauntlet.
EXEMPTION_FLAG_KEYS = frozenset({"never_retire", "sacred", "immortal", "unretirable",
                                 "exempt_from_retirement", "exempt_from_gauntlet",
                                 "skip_gauntlet", "gauntlet_bypass", "retirement_exempt"})
#: A module-level constant NAME that declares a set of things beyond retirement or the gauntlet.
#: Deliberately specific: `EXEMPT` alone names dozens of lint allow-lists that have nothing to do
#: with retirement, and a lint that fires on them would be switched off inside a week (L1.43).
_EXEMPTION_NAME = re.compile(
    r"^_?[A-Z0-9_]*(NEVER_RETIRE|SACRED|IMMORTAL|UNRETIRABLE|RETIRE(MENT)?_EXEMPT|"
    r"EXEMPT_FROM_(RETIRE|RETIREMENT|GAUNTLET|JUDGE|JUDGING|VALIDATION)|"
    r"GAUNTLET_(EXEMPT|BYPASS)|SKIP_GAUNTLET|BYPASS_GAUNTLET|GRANDFATHER(ED)?)[A-Z0-9_]*$")
_EXEMPTION_WORDS = ("RETIRE", "SACRED", "IMMORTAL", "GAUNTLET", "GRANDFATHER")
LINT_TREES = ("desks/mt5/research", "desks/mt5/mt5desk", "desks/mt5/scripts", "libs", "scripts")
#: The lint's own definition sites: they spell the pattern, they declare no exemption.
LINT_SELF = frozenset({"libs/tiers/principles.py", "scripts/check_principles.py"})
#: A gold evidence alias folds into its canonical window at `decision_core.roster`, so the
#: canonical window's retirement (data/GOLD_RETIRED.json) retires it too.
_GOLD_ALIAS = re.compile(r"^gold_(asia|london_am|afternoon)_v\d+$", re.IGNORECASE)

_BOUND = re.compile(r"([A-Za-z_][\w.]*)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)")
_MINING_LEGS = ("mine", "search", "compile_candidates", "moat_miner", "deep_forest",
                "world_crawler", "breadth_sweep")
_JUDGE_LEGS = ("external_gauntlet",)
_TIME_KEYS = ("generated_utc", "generated_at", "at", "measured_at", "updated_utc", "checked_at",
              "built_at", "written_at", "ts")


# ------------------------------------------------------------------------------------- helpers
def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _read_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def _read_json(p: Path) -> Any:
    t = _read_text(p)
    if t is None:
        return None
    try:
        return json.loads(t)
    except ValueError:
        return None


def _parse_ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _doc_time(doc: Any) -> datetime | None:
    if not isinstance(doc, dict):
        return None
    for k in _TIME_KEYS:
        t = _parse_ts(doc.get(k))
        if t is not None:
            return t
    return None


def _tail_rows(p: Path, max_bytes: int = 2 * 1024 * 1024) -> list[dict[str, Any]]:
    """The JSONL rows in the last `max_bytes` of `p` (first partial line dropped)."""
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            raw = fh.read()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _git(root: Path, *args: str, timeout: float = 30.0) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                           timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _dig(doc: Any, dotted: str) -> Any:
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _result(findings: Sequence[str], measured: bool, evidence: Mapping[str, Any],
            why: str) -> dict[str, Any]:
    """MET only when something was actually measured and nothing was found."""
    verdict = VIOLATED if findings else (MET if measured else UNMEASURED)
    return {"verdict": verdict, "findings": sorted(set(findings)), "measured": bool(measured),
            "evidence": dict(evidence), "why": why}


def load_map(root: Path | None = None) -> dict[str, Any]:
    doc = _read_json((root or ROOT) / MAP_REL)
    if not isinstance(doc, dict) or not isinstance(doc.get("principles"), list):
        raise ValueError(f"{MAP_REL} is absent or has no `principles` list")
    return doc


def cycle_running(root: Path, now: datetime | None = None) -> tuple[bool, str]:
    """Is the hourly cycle running on THIS host? (newest compute-ledger row inside 6h)"""
    rows = _tail_rows(root / COMPUTE_LEDGER_REL, 512 * 1024)
    times = [t for t in (_parse_ts(r.get("at") or r.get("finished_at")) for r in rows) if t]
    if not times:
        return False, f"no compute-ledger rows at {COMPUTE_LEDGER_REL}"
    newest = max(times)
    age = ((now or now_utc()) - newest).total_seconds()
    if age > CYCLE_FRESH_S:
        return False, (f"newest compute-ledger row is {age / 3600:.1f}h old: the hourly cycle "
                       "does not run on this host")
    return True, f"compute ledger newest row {age / 60:.0f} min old"


# -------------------------------------------------------------------------------------- organs
def resolve_organ(root: Path, organ: Mapping[str, Any],
                  cache: dict[str, str | None] | None = None) -> dict[str, Any]:
    """{ok, why} for one organ of the map. Reads only the tree."""
    cache = cache if cache is not None else {}

    def text(rel: str) -> str | None:
        if rel not in cache:
            cache[rel] = _read_text(root / rel)
        return cache[rel]

    kind = str(organ.get("kind") or "")
    name = str(organ.get("name") or "")
    if kind == "leg":
        src = text(HOURLY_REL) or ""
        ok = f'_costed("{name}"' in src
        return {"ok": ok, "why": (f"leg `{name}` is on the hourly cycle" if ok else
                                  f"no `_costed(\"{name}\"` in {HOURLY_REL}")}
    if kind == "fence":
        exists = (root / "scripts" / name).is_file()
        wired = f'"{name}"' in (text(LAW_GATE_REL) or "")
        ok = exists and wired
        return {"ok": ok, "why": (f"fence scripts/{name} wired into the law gate" if ok else
                                  f"scripts/{name} {'exists' if exists else 'is absent'} and "
                                  f"{'is' if wired else 'is NOT'} named in {LAW_GATE_REL}")}
    if kind == "task":
        src = text(BOX_TASKS_REL) or ""
        m = re.search(rf'TASK name="{re.escape(name)}"[^\n]*runs="([^"]+)"', src)
        ok = bool(m) and (root / m.group(1)).is_file() if m else False
        return {"ok": ok, "why": (f"box task {name} runs {m.group(1)}" if ok and m else
                                  f"box task {name} absent from {BOX_TASKS_REL} or its script "
                                  "is missing")}
    if kind == "code":
        rel = str(organ.get("path") or "")
        token = str(organ.get("token") or "")
        code_src = text(rel)
        ok = code_src is not None and token in code_src
        state = "lacks" if code_src is not None else "is absent; lacks"
        return {"ok": ok, "why": (f"{rel} carries `{token}`" if ok else
                                  f"{rel} {state} `{token}`")}
    return {"ok": False, "why": f"unknown organ kind {kind!r}"}


def organ_label(organ: Mapping[str, Any]) -> str:
    kind = str(organ.get("kind") or "")
    if kind == "code":
        return f"code:{organ.get('path')}#{organ.get('token')}"
    return f"{kind}:{organ.get('name')}"


def resolve_organs(root: Path, principle: Mapping[str, Any],
                   cache: dict[str, str | None] | None = None) -> list[dict[str, Any]]:
    out = []
    for organ in principle.get("organs") or []:
        if isinstance(organ, Mapping):
            res = resolve_organ(root, organ, cache)
            out.append({"organ": organ_label(organ), "kind": organ.get("kind"),
                        "role": organ.get("role", ""), **res})
    return out


# ----------------------------------------------------------------------- P1: nothing is sacred
def sacred_constants(root: Path, trees: Iterable[str] = LINT_TREES) -> list[str]:
    """`<path>:<NAME>` for every module-level constant whose NAME declares an exemption from
    retirement or from the gauntlet. Tests and the lint's own files are out of scope."""
    out: list[str] = []
    seen: set[Path] = set()
    for tree_rel in trees:
        base = root / tree_rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if p in seen or "__pycache__" in p.parts or "tests" in p.parts \
                    or p.name.startswith("test_") or "_retired" in p.parts:
                continue
            seen.add(p)
            rel = p.relative_to(root).as_posix()
            if rel in LINT_SELF:
                continue
            src = _read_text(p)
            # cheap prefilter: a file with none of the words cannot declare such a constant
            if not src or not any(w in src for w in _EXEMPTION_WORDS):
                continue
            try:
                tree = ast.parse(src)
            except (SyntaxError, ValueError):
                continue
            for node in tree.body:
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                for t in targets:
                    if isinstance(t, ast.Name) and _EXEMPTION_NAME.match(t.id):
                        out.append(f"{rel}:{t.id}")
    return sorted(set(out))


def _flagged_rows(doc: Any, path: str, out: list[str], depth: int = 0) -> None:
    if depth > 6:
        return
    if isinstance(doc, dict):
        for k, v in doc.items():
            if str(k).lower() in EXEMPTION_FLAG_KEYS and bool(v):
                name = doc.get("name") or doc.get("id") or doc.get("source") or "?"
                out.append(f"{path}:{name}:{k}")
            elif isinstance(v, (dict, list)):
                _flagged_rows(v, path, out, depth + 1)
    elif isinstance(doc, list):
        for v in doc[:50_000]:
            _flagged_rows(v, path, out, depth + 1)


def retirement_path(row: Mapping[str, Any]) -> str:
    """How a LIVE row can leave the book, or "" when it cannot."""
    override = row.get("principal_override")
    name = str(row.get("name") or "")
    if not override:
        return "promoter/decay_monitor (automatic, certificate- and ledger-driven)"
    if isinstance(override, Mapping) and override.get("reverts_if"):
        return f"principal override with a named falsifier: {str(override['reverts_if'])[:80]}"
    if _GOLD_ALIAS.match(name):
        return "evidence alias of a canonical gold window, retired through data/GOLD_RETIRED.json"
    return ""


def measure_no_sacred(root: Path, spec: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    findings: list[str] = []
    lint = sacred_constants(root)
    findings += [f"P1:sacred_constant:{x}" for x in lint]
    flagged: list[str] = []
    read: list[str] = []
    for rel in SOURCE_REGISTRIES:
        doc = _read_json(root / rel)
        if doc is None:
            continue
        read.append(rel)
        _flagged_rows(doc, rel, flagged)
    findings += [f"P1:exempt_row:{x}" for x in flagged]
    sleeves = _read_json(root / SLEEVES_REL)
    rows = sleeves.get("sleeves") if isinstance(sleeves, dict) else sleeves
    live = [r for r in rows if isinstance(r, dict)
            and str(r.get("status") or "").upper() == "LIVE"] if isinstance(rows, list) else []
    no_path = [str(r.get("name")) for r in live if not retirement_path(r)]
    findings += [f"P1:live_without_retirement_path:{n}" for n in no_path]
    overrides = [str(r.get("name")) for r in live if r.get("principal_override")]
    return _result(findings, measured=isinstance(rows, list), evidence={
        "sacred_constants": lint, "exempt_rows": flagged, "registries_read": read,
        "live_sleeves": len(live), "live_principal_overrides": overrides,
        "live_without_retirement_path": no_path},
        why=("every LIVE sleeve has a retirement path (automatic, a named falsifier, or the "
             "canonical gold window it folds into), no registry row carries an exemption flag, "
             "and no research module declares an exemption constant"))


# -------------------------------------------------------------- P2: change triggers relearning
def structural_triggers(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every live structural-change signal the detectors publish, each with the dedupe key the
    queue producer files its `recertify` task under. Shared by the producer and the measure, so
    they can never disagree about what counts as a trigger."""
    triggers: list[dict[str, Any]] = []
    seen: dict[str, Any] = {}
    shift = _read_json(root / DIST_SHIFT_REL)
    if isinstance(shift, dict):
        at = _parse_ts(shift.get("at"))
        seen["dist_shift"] = {"at": shift.get("at"), "status": shift.get("status"),
                              "n_shifted": shift.get("n_shifted")}
        day = (at or now_utc()).date().isoformat()
        for row in shift.get("shifted") or []:
            if not isinstance(row, dict) or not row.get("symbol"):
                continue
            sym = str(row["symbol"])
            triggers.append({"kind": "dist_shift", "subject": sym, "at": shift.get("at"),
                             "verdict": row.get("verdict"),
                             "sleeves": list(row.get("sleeves") or []),
                             "dedupe_key": f"recertify:structural:dist_shift:{sym}:{day}"})
    decay = _read_json(root / DECAY_REL)
    if isinstance(decay, dict):
        at = _parse_ts(decay.get("checked_at"))
        seen["decay_live"] = {"at": decay.get("checked_at"),
                              "n_verdicts": len(decay.get("verdicts") or {})}
        day = (at or now_utc()).date().isoformat()
        verdicts = decay.get("verdicts") or {}
        for name, v in (verdicts.items() if isinstance(verdicts, dict) else []):
            if isinstance(v, dict) and str(v.get("verdict") or "").upper() == "FADE":
                triggers.append({"kind": "decay_fade", "subject": str(name),
                                 "at": decay.get("checked_at"), "verdict": "FADE",
                                 "sleeves": [str(name)],
                                 "dedupe_key": f"recertify:structural:decay_fade:{name}:{day}"})
    return triggers, seen


def queued_keys(root: Path) -> set[str]:
    """Every dedupe key the task journal has ever carried, any state."""
    keys: set[str] = set()
    for row in _tail_rows(root / TASK_QUEUE_REL, 16 * 1024 * 1024):
        k = row.get("dedupe_key")
        if k:
            keys.add(str(k))
    return keys


def measure_relearn_on_change(root: Path, spec: Mapping[str, Any],
                              now: datetime) -> dict[str, Any]:
    triggers, seen = structural_triggers(root)
    if not seen:
        return _result([], False, {"detectors": {}},
                       f"neither {DIST_SHIFT_REL} nor {DECAY_REL} exists on this host")
    keys = queued_keys(root)
    findings: list[str] = []
    answered, waiting = [], []
    for t in triggers:
        if t["dedupe_key"] in keys:
            answered.append(t["dedupe_key"])
            continue
        at = _parse_ts(t.get("at"))
        if at is not None and (now - at).total_seconds() <= RELEARN_GRACE_S:
            waiting.append(t["dedupe_key"])
            continue
        findings.append(f"P2:trigger_without_rejudge:{t['kind']}:{t['subject']}")
    running, why_run = cycle_running(root, now)
    stale = []
    for name, info in seen.items():
        at = _parse_ts(info.get("at"))
        if at is None or (now - at).total_seconds() > DETECTOR_FRESH_S:
            stale.append(name)
    if running:
        # a detector that stopped publishing on the host that runs it is a broken trigger
        findings += [f"P2:detector_stale:{n}" for n in stale]
    # A stale detector on a host that does not run the cycle has measured nothing about today.
    measured = bool(triggers) or len(stale) < len(seen)
    return _result(findings, measured=measured, evidence={
        "detectors": seen, "triggers": len(triggers), "answered": len(answered),
        "within_grace": waiting, "detectors_stale": stale, "cycle": why_run},
        why=("every distribution-shift or decay-FADE trigger has a `recertify` task in the "
             "queue (libs/ops/queue_cycle._structural_change), so a structural change is "
             "re-judged by the validation role rather than published and forgotten"))


# -------------------------------------------------------------------- P3: cash is an allocation
def optimiser_admits_cash(root: Path) -> tuple[bool, str]:
    src = _read_text(root / ROBUST_ELOG_REL)
    if src is None:
        return False, f"{ROBUST_ELOG_REL} absent"
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return False, f"{ROBUST_ELOG_REL} does not parse: {exc}"
    proj = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "project_capped_simplex"), None)
    if proj is None:
        return False, "project_capped_simplex is gone"
    kw = {a.arg for a in proj.args.kwonlyargs} | {a.arg for a in proj.args.args}
    body = ast.get_source_segment(src, proj) or ""
    if "exact" not in kw or "not exact" not in body:
        return False, ("project_capped_simplex has no non-exact path: the optimiser can no "
                       "longer hold capital back")
    return True, "project_capped_simplex keeps sum(h) <= cap (exact=False): cash is admissible"


def measure_cash_is_allocation(root: Path, spec: Mapping[str, Any],
                               now: datetime) -> dict[str, Any]:
    findings: list[str] = []
    ok, why_code = optimiser_admits_cash(root)
    if not ok:
        findings.append("P3:optimiser_forces_full_investment")
    alloc = _read_json(root / ALLOCATION_REL)
    heat = alloc.get("heat") if isinstance(alloc, dict) else None
    ev: dict[str, Any] = {"optimiser": why_code}
    measured = False
    if isinstance(alloc, dict):
        if not isinstance(heat, dict) or _num(heat.get("free_optimum")) is None:
            findings.append("P3:allocator_publishes_no_free_optimum")
        else:
            measured = True
            free = _num(heat.get("free_optimum")) or 0.0
            ceiling = _num(heat.get("hard_ceiling"))
            total = _num(heat.get("total"))
            ev.update({"free_optimum": free, "resolved_total": total, "hard_ceiling": ceiling,
                       "cash_heat_at_free_optimum": (round(ceiling - free, 6)
                                                     if ceiling is not None else None),
                       "allocation_at": alloc.get("generated_at") or alloc.get("at")})
    else:
        ev["allocation"] = f"{ALLOCATION_REL} absent on this host"
    return _result(findings, measured, ev,
                   "the optimiser may hold capital back (its free optimum is published beside "
                   "the resolved book), so unrisked capital is a scored choice, not a remainder")


# ---------------------------------------------------------------- P4: research never stops
def measure_research_never_stops(root: Path, spec: Mapping[str, Any],
                                 now: datetime) -> dict[str, Any]:
    running, why_run = cycle_running(root, now)
    if not running:
        return _result([], False, {"cycle": why_run},
                       "the hourly cycle does not run on this host, so research liveness is "
                       "measured where it does")
    rows = _tail_rows(root / COMPUTE_LEDGER_REL, 8 * 1024 * 1024)
    last: dict[str, datetime] = {}
    for r in rows:
        t = _parse_ts(r.get("at") or r.get("finished_at"))
        run = str(r.get("run") or "")
        if t is not None and run and (run not in last or t > last[run]):
            last[run] = t

    def age_h(legs: Sequence[str]) -> float | None:
        ts = [last[x] for x in legs if x in last]
        return round((now - max(ts)).total_seconds() / 3600, 2) if ts else None

    findings: list[str] = []
    mining_h, judge_h = age_h(_MINING_LEGS), age_h(_JUDGE_LEGS)
    if mining_h is None or mining_h * 3600 > RESEARCH_SILENCE_S:
        findings.append("P4:mining_silent")
    if judge_h is None or judge_h * 3600 > RESEARCH_SILENCE_S:
        findings.append("P4:judge_silent")
    tp = _read_json(root / THROUGHPUT_REL)
    vph = _num(tp.get("verdicts_per_hour")) if isinstance(tp, dict) else None
    if vph is not None and vph <= 0:
        findings.append("P4:zero_judging_throughput")
    return _result(findings, True, {
        "cycle": why_run, "mining_last_ran_h": mining_h, "judge_last_ran_h": judge_h,
        "verdicts_per_hour": vph if vph is not None else UNMEASURED},
        why="mining and judge legs ran inside 12h and the judge drains at a non-zero rate")


# ---------------------------------------------------------- P5: validation never relaxes
def gate_bounds(spec_text: str) -> dict[str, tuple[str, float]]:
    """`gate:field:metric` -> (operator, value) for every numeric bound in gate_spec."""
    import yaml  # local: only the gate ratchet needs it
    try:
        doc = yaml.safe_load(spec_text)
    except yaml.YAMLError:
        return {}
    out: dict[str, tuple[str, float]] = {}
    for gate in (doc or {}).get("gates") or []:
        if not isinstance(gate, dict):
            continue
        gname = str(gate.get("name") or "?")
        for field in ("threshold", "forward_cure_threshold"):
            val = gate.get(field)
            if not isinstance(val, str):
                continue
            for metric, op, num in _BOUND.findall(val):
                out[f"{gname}:{field}:{metric}"] = (op, float(num))
    return out


def _stricter(op: str, a: float, b: float) -> bool:
    """Is bound value `a` stricter than `b` under operator `op`?"""
    return a > b if op in (">", ">=") else a < b


def gate_threshold_ratchet(root: Path,
                           versions: int = GATE_HISTORY_VERSIONS) -> dict[str, Any]:
    """Every gate_spec bound against its strictest value across the file's git history.

    Direction comes from the bound's own operator: under `>`/`>=` a higher number is stricter,
    under `<`/`<=` a lower one. A bound looser at HEAD than anywhere in history is a relaxation.
    A shallow clone reads what history it has, and says how many versions that was."""
    cur_text = _read_text(root / GATE_SPEC_REL)
    if cur_text is None:
        return {"status": UNMEASURED, "why": f"{GATE_SPEC_REL} absent", "relaxed": []}
    current = gate_bounds(cur_text)
    log = _git(root, "log", f"-n{versions}", "--format=%H", "--", GATE_SPEC_REL)
    shas = [s for s in (log or "").split() if s]
    strictest: dict[str, tuple[float, str]] = {}
    for sha in shas:
        old = _git(root, "show", f"{sha}:{GATE_SPEC_REL}")
        if old is None:
            continue
        for key, (op, val) in gate_bounds(old).items():
            cur = current.get(key)
            if cur is None or cur[0][0] != op[0]:
                continue
            best = strictest.get(key)
            if best is None or _stricter(op, val, best[0]):
                strictest[key] = (val, sha[:10])
    relaxed = []
    for key, (op, val) in sorted(current.items()):
        best = strictest.get(key)
        if best is not None and _stricter(op, best[0], val):
            relaxed.append({"bound": key, "op": op, "now": val, "strictest": best[0],
                            "strictest_at": best[1]})
    return {"status": MET if shas else UNMEASURED, "versions_read": len(shas),
            "bounds": len(current), "relaxed": relaxed,
            "why": ("no git history for gate_spec on this clone" if not shas else
                    f"{len(current)} bound(s) against {len(shas)} historical version(s)")}


def gate_spec_sealed(root: Path) -> tuple[str, str]:
    """(MET|VIOLATED|UNMEASURED, why): gate_spec.yaml against its signed manifest hash, with
    the same CRLF normalisation `check_immutable_evaluator` signs with."""
    p = root / GATE_SPEC_REL
    man = _read_json(root / MANIFEST_REL)
    files = man.get("files") if isinstance(man, dict) else None
    signed = files.get(GATE_SPEC_REL) if isinstance(files, dict) else None
    if not p.is_file() or not signed:
        return UNMEASURED, "gate_spec or its manifest entry is absent"
    h = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]
    if h != signed:
        return VIOLATED, f"gate_spec hash {h} != signed {signed}"
    return MET, f"gate_spec matches its signed hash {signed}"


def floor_ratchet(root: Path, floors: Sequence[Mapping[str, Any]],
                  versions: int = GATE_HISTORY_VERSIONS) -> list[dict[str, Any]]:
    """Each declared floor key at HEAD against its best value across the file's git history."""
    out = []
    for f in floors:
        rel = str(f.get("path") or "")
        up = str(f.get("direction") or "up") == "up"
        cur = _read_json(root / rel)
        log = _git(root, "log", f"-n{versions}", "--format=%H", "--", rel)
        hist = []
        for sha in [s for s in (log or "").split() if s]:
            old = _git(root, "show", f"{sha}:{rel}")
            if old is None:
                continue
            try:
                hist.append((sha[:10], json.loads(old)))
            except ValueError:
                continue
        for key in f.get("keys") or []:
            now_v = _num(_dig(cur, key))
            best: tuple[float, str] | None = None
            for sha, doc in hist:
                v = _num(_dig(doc, key))
                if v is not None and (best is None or (v > best[0] if up else v < best[0])):
                    best = (v, sha)
            fell = (now_v is not None and best is not None
                    and (now_v < best[0] if up else now_v > best[0]))
            out.append({"path": rel, "key": key, "now": now_v,
                        "best": best[0] if best else None, "best_at": best[1] if best else None,
                        "versions_read": len(hist), "fell": bool(fell)})
    return out


def measure_validation_never_relaxes(root: Path, spec: Mapping[str, Any],
                                     now: datetime) -> dict[str, Any]:
    findings: list[str] = []
    seal, seal_why = gate_spec_sealed(root)
    if seal == VIOLATED:
        findings.append("P5:gate_spec_unsealed")
    gates = gate_threshold_ratchet(root)
    findings += [f"P5:gate_relaxed:{r['bound']}" for r in gates.get("relaxed") or []]
    floors = floor_ratchet(root, spec.get("floors") or [])
    findings += [f"P5:floor_fell:{r['path']}:{r['key']}" for r in floors if r["fell"]]
    measured = seal != UNMEASURED or gates.get("status") == MET \
        or any(r["now"] is not None for r in floors)
    return _result(findings, measured, {"gate_spec_seal": seal_why, "gate_ratchet": gates,
                                        "floors": floors},
                   "gate_spec is sealed, no gate bound is looser than its strictest value in "
                   "history, and no declared floor sits below its own high-water mark")


# ---------------------------------------------------------- P6: execution teaches research
def measure_execution_teaches_research(root: Path, spec: Mapping[str, Any],
                                       now: datetime) -> dict[str, Any]:
    findings: list[str] = []
    feeds = []
    for feed in spec.get("feeds") or []:
        art = str(feed.get("artifact") or "")
        readers = [c for c in feed.get("consumers") or []
                   if art and art in (_read_text(root / c) or "")]
        feeds.append({"artifact": art, "research_readers": readers})
        if not readers:
            findings.append(f"P6:no_research_consumer:{art}")
    fills = _tail_rows(root / LIVE_LEDGER_REL, 512 * 1024)
    fill_ts = [t for t in (_parse_ts(r.get("time") or r.get("at")) for r in fills) if t]
    last_fill = max(fill_ts) if fill_ts else None
    reports = {}
    for rel in spec.get("consumer_reports") or []:
        t = _doc_time(_read_json(root / rel))
        if t is not None:
            reports[rel] = t
    running, why_run = cycle_running(root, now)
    measured = last_fill is not None and bool(reports)
    if measured and running and last_fill is not None:
        newest = max(reports.values())
        if (last_fill - newest).total_seconds() > FEEDBACK_LAG_S:
            findings.append("P6:research_consumers_stale")
    return _result(findings, measured, {
        "feeds": feeds, "last_fill": last_fill.isoformat() if last_fill else UNMEASURED,
        "consumer_reports": {k: v.isoformat() for k, v in reports.items()}, "cycle": why_run},
        why=("the live ledger and the fill corpus each have research readers, and those "
             "readers' reports keep pace with the newest fill"))


# --------------------------------------------------------------- P7: the ontology stays open
def registry_open(root: Path, reg: Mapping[str, Any]) -> tuple[bool, str]:
    rel, sym, fn = str(reg.get("path")), str(reg.get("symbol")), str(reg.get("register"))
    src = _read_text(root / rel)
    if src is None:
        return False, f"{rel} absent"
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return False, f"{rel} does not parse: {exc}"
    has_fn = any(isinstance(n, ast.FunctionDef) and n.name == fn for n in tree.body)
    value = None
    for n in tree.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            if any(isinstance(t, ast.Name) and t.id == sym for t in targets):
                value = n.value
    if value is None:
        return False, f"{rel} no longer defines {sym}"
    closed = isinstance(value, (ast.Tuple, ast.Constant)) or (
        isinstance(value, ast.Call) and isinstance(value.func, (ast.Name, ast.Attribute))
        and (getattr(value.func, "id", None) or getattr(value.func, "attr", ""))
        in {"frozenset", "tuple", "MappingProxyType", "frozendict"})
    if closed:
        return False, f"{rel}:{sym} is a closed (immutable) container"
    if not has_fn:
        return False, f"{rel} has no `{fn}`: nothing can add to {sym}"
    return True, f"{rel}:{sym} is mutable and `{fn}` adds to it"


def registry_growth(root: Path, reg: Mapping[str, Any], now: datetime,
                    days: int = ONTOLOGY_WINDOW_DAYS) -> dict[str, Any]:
    token, tree = reg.get("growth_token"), reg.get("growth_tree")
    if not token or not tree:
        return {"status": UNMEASURED, "why": "no growth token declared"}

    def count(rev: str) -> int | None:
        out = _git(root, "grep", "-c", "-F", str(token), rev, "--", str(tree))
        if out is None:
            return 0 if _git(root, "rev-parse", "--verify", rev) else None
        return sum(int(line.rsplit(":", 1)[1]) for line in out.splitlines()
                   if line.rsplit(":", 1)[-1].isdigit())

    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    old = (_git(root, "rev-list", "-1", f"--before={cutoff}", "HEAD") or "").strip()
    head = count("HEAD")
    if not old or head is None:
        return {"status": UNMEASURED, "head": head,
                "why": f"git history on this clone does not reach {days} days back"}
    then = count(old)
    grew = then is not None and head > then
    return {"status": MET if grew else VIOLATED, "head": head, "then": then, "then_sha": old[:10],
            "why": f"{token} occurrences {then} -> {head} over {days} days"}


def measure_ontology_open(root: Path, spec: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    findings: list[str] = []
    regs = []
    growth_measured = False
    any_growth = False
    for reg in spec.get("registries") or []:
        ok, why = registry_open(root, reg)
        row: dict[str, Any] = {"registry": f"{reg.get('path')}:{reg.get('symbol')}",
                               "open": ok, "why": why}
        if not ok:
            findings.append(f"P7:registry_closed:{reg.get('path')}:{reg.get('symbol')}")
        if reg.get("growth_token"):
            g = registry_growth(root, reg, now)
            row["growth"] = g
            if g["status"] != UNMEASURED:
                growth_measured = True
                any_growth = any_growth or g["status"] == MET
        regs.append(row)
    proposals = _read_json(root / f"{DESK_REL}/reports/AXIS_PROPOSER.json")
    prop_t = _doc_time(proposals)
    recent_proposals = bool(prop_t and (now - prop_t).days <= ONTOLOGY_WINDOW_DAYS)
    if growth_measured and not any_growth and not recent_proposals:
        findings.append("P7:ontology_static")
    return _result(findings, growth_measured or recent_proposals, {
        "registries": regs, "axis_proposer_at": prop_t.isoformat() if prop_t else UNMEASURED},
        why=("the family and feature registries are mutable with a registration path, and the "
             f"family registry grew (or the axis proposer proposed) inside {ONTOLOGY_WINDOW_DAYS}"
             " days"))


MEASURES: dict[str, Callable[[Path, Mapping[str, Any], datetime], dict[str, Any]]] = {
    "no_sacred": measure_no_sacred,
    "relearn_on_change": measure_relearn_on_change,
    "cash_is_allocation": measure_cash_is_allocation,
    "research_never_stops": measure_research_never_stops,
    "validation_never_relaxes": measure_validation_never_relaxes,
    "execution_teaches_research": measure_execution_teaches_research,
    "ontology_open": measure_ontology_open,
}


# ------------------------------------------------------------------------------------ the pass
def evaluate(root: Path | None = None, *, now: datetime | None = None,
             principle_map: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One pass over every principle: organs resolved, measurement taken, verdict assigned."""
    root = Path(root or ROOT)
    now = now or now_utc()
    pmap = principle_map or load_map(root)
    cache: dict[str, str | None] = {}
    rows = []
    for p in pmap.get("principles") or []:
        organs = resolve_organs(root, p, cache)
        live = [o for o in organs if o["ok"]]
        missing = [o["organ"] for o in organs if not o["ok"]]
        fn = MEASURES.get(str(p.get("measure") or ""))
        if fn is None:
            m = _result([f"{p.get('id')}:no_measure"], False, {},
                        f"no measure named {p.get('measure')!r}")
        else:
            try:
                m = fn(root, p, now)
            except Exception as exc:  # a broken measure is a finding, never a silent pass
                m = {"verdict": UNMEASURED, "findings": [], "measured": False, "evidence": {},
                     "why": f"measure raised {type(exc).__name__}: {exc}"}
        verdict = UNENFORCED if not live else m["verdict"]
        findings = list(m.get("findings") or []) + [f"{p['id']}:missing_organ:{x}"
                                                    for x in missing]
        rows.append({"id": p["id"], "text": p.get("text", ""), "verdict": verdict,
                     "measured_verdict": m["verdict"], "findings": sorted(set(findings)),
                     "organs_enforcing": len(live), "organs_declared": len(organs),
                     "missing_organs": missing, "organs": organs,
                     "evidence": m.get("evidence", {}), "why": m.get("why", "")})
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}
    return {"schema": 1, "generated_utc": now.isoformat(timespec="seconds"),
            "map": MAP_REL, "principles": rows, "counts": counts,
            "caps_capital": False,
            "rule": ("ABSENCE IS UNMEASURED, NEVER MET. A principle with no resolving organ is "
                     "UNENFORCED. This organ measures research and validation discipline; it "
                     "caps no capital, vetoes no trade and lowers no heat.")}


def findings_of(doc: Mapping[str, Any]) -> set[str]:
    return {f for r in doc.get("principles") or [] for f in r.get("findings") or []}


def ratchet(doc: Mapping[str, Any], floor: Mapping[str, Any] | None,
            *, require_state: bool = False) -> dict[str, Any]:
    """Arrivals against the committed floor. Pre-existing findings and UNMEASURED principles
    are debt the floor names; a NEW finding, an UNENFORCED principle, or (with
    `require_state`) a principle that is UNMEASURED and not already in the floor, fails."""
    floor = floor or {}
    known = set(floor.get("findings") or [])
    known_unmeasured = set(floor.get("unmeasured") or [])
    now_findings = findings_of(doc)
    arrived = sorted(now_findings - known)
    unenforced = sorted(r["id"] for r in doc.get("principles") or []
                        if r["verdict"] == UNENFORCED)
    unmeasured = sorted(r["id"] for r in doc.get("principles") or []
                        if r["verdict"] == UNMEASURED)
    new_unmeasured = sorted(set(unmeasured) - known_unmeasured) if require_state else []
    healed = sorted(known - now_findings)
    ok = not arrived and not unenforced and not new_unmeasured
    return {"ok": ok, "arrived": arrived, "unenforced": unenforced,
            "new_unmeasured": new_unmeasured, "pre_existing": sorted(now_findings & known),
            "healed": healed, "unmeasured": unmeasured, "require_state": require_state}
