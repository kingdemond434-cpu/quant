"""THE FUNCTION MAP: every essential function, its nine facts, and how far up the ladder it is.

    python libs/ops/function_registry.py              # derive and publish FUNCTION_MAP.json
    python scripts/check_function_registry.py         # the law fence: fail on a false rung

WHY A PER-FUNCTION MAP, when `capability_graph` and `runtime_state.json` already cover organs
(ARCH-09). Those two answer "does this ORGAN have an artifact, a clock, a reader". Nobody could
answer the question one level up: for the desk's ESSENTIAL FUNCTIONS -- research, forecasting,
validation, the allocator, the controls, execution, accounting, data and ops -- who owns each
one, what it reads and writes, which process runs it, who consumes it, what it is allowed to
decide, what it does when it fails, and how anyone would know it works. ARCH-12 states the
separation of powers (research proposes, forecasting publishes beliefs, validation decides
eligibility, the allocator proposes, controls enforce, execution manages orders, accounting
reconciles). This file is where each power is pinned to a file and checked.

THE REGISTRY IS DATA (`docs/research/function_registry.json`); THE LADDER IS DERIVED, NEVER
ASSERTED. A row declares nine facts. No row may carry a rung, a status or a "verified" flag --
`check_function_registry.py` fails if one does, because a rung somebody typed is exactly the
claim this desk keeps being unable to cash. Every rung is computed here from the tree and the
artifacts:

    declared            all nine facts present, the domain and the authority from the enums
    implemented         the owner file exists; every input and output it names is in the
                        owner's source (a filename literal, `api:<def>` or `exit:status`); the
                        failure behaviour's marker is in the owner's source; every contract file
                        exists
    connected           every named consumer exists and reads an output (names the filename, or
                        imports the owner, or -- for `exit:status` -- invokes it); every clock is
                        one the repo knows (a cycle leg, a box task, a law fence, a VPS timer)
                        and that clock reaches the owner, directly or through the declared `via`
                        chain, each hop of which must name the next
    running             an output artifact on THIS host is inside its clock's silence window. A
                        tracked file unchanged from HEAD is a git copy, not a run, and reads
                        UNMEASURED; so does an absent one (L1.28a). A stale one is FALSE.
    behaviour_verified  running, AND every verification test exists and names the owner

The rung is the highest one with every rung below it TRUE. The first three are STATIC: if one is
FALSE the registry says something the repository contradicts, and that is a false rung the fence
fails on. The last two are runtime facts; on a host with no artifacts they are UNMEASURED, which
is the honest verdict and not a failure (L1.43: a fence that is red in CI gets switched off).

Artifact: `desks/mt5/reports/FUNCTION_MAP.json` (hourly leg `function_registry`). Its consumer is
`scripts/check_function_registry.py`, which re-derives every published rung and fails when the
published map claims a static rung the tree no longer supports.
"""
from __future__ import annotations

import argparse
import ast
import itertools
import json
import re
import socket
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REGISTRY = ROOT / "docs" / "research" / "function_registry.json"
OUT = DESK / "reports" / "FUNCTION_MAP.json"

TRUE, FALSE, UNMEASURED = "TRUE", "FALSE", "UNMEASURED"
RUNGS: tuple[str, ...] = ("declared", "implemented", "connected", "running",
                          "behaviour_verified")
STATIC_RUNGS: tuple[str, ...] = RUNGS[:3]
#: The nine essential domains (ARCH-09). Every one must be covered by at least one function.
DOMAINS: tuple[str, ...] = ("research", "forecasting", "validation", "allocator", "controls",
                            "execution", "accounting", "data", "ops")
#: The nine facts every function publishes.
FIELDS: tuple[str, ...] = ("owner", "inputs", "outputs", "contracts", "runtime_process",
                           "consumers", "decision_authority", "failure_behaviour",
                           "verification")
#: What a function may decide, in ARCH-12's own vocabulary.
AUTHORITY: tuple[str, ...] = ("proposes", "publishes", "decides", "enforces", "executes",
                              "reconciles", "observes", "schedules")
FAILURE_MODES: tuple[str, ...] = ("fail_closed", "stand_down", "hold", "unmeasured",
                                  "fail_loud")
#: Keys a row may NEVER carry: each would be a rung asserted instead of derived.
ASSERTED_KEYS: frozenset[str] = frozenset({"rung", "rungs", "ladder", "status", "state",
                                           "verified", "running", "connected", "implemented"})
CLOCK_KINDS: tuple[str, ...] = ("leg", "task", "fence", "timer")
#: The output token whose product is the owner's exit code (a fence's verdict).
EXIT_TOKEN = "exit:" + "status"

#: Where an output artifact may live on a host. Filenames are the join key, as in
#: `check_dead_architecture`: this repository builds every path from parts.
ARTIFACT_DIRS: tuple[Path, ...] = (
    DESK / "reports", DESK / "data", DESK / "data" / "universe", DESK / "data" / "hypotheses",
    DESK / "data" / "intelligence", ROOT / "data", ROOT / "reports", ROOT / "docs" / "research",
)
#: Silence windows by clock kind, in seconds, when the clock does not say more. A leg runs
#: hourly and is late after two; a box task's own trigger is parsed when it names minutes/hours.
DEFAULT_SILENCE_S: dict[str, int] = {"leg": 7_200, "task": 7_200, "timer": 7_200,
                                     "fence": 0}
DAILY_SILENCE_S = 172_800


def _read(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


def load_registry(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path or REGISTRY).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _stem(path: str) -> str:
    return Path(path).stem


def _defs(src: str) -> set[str]:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set()
    return {n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)}


def _names_module(src: str, owner: str) -> bool:
    """Does `src` reach the owner: by its stem as an import, a path literal or a call."""
    return re.search(rf"\b{re.escape(_stem(owner))}\b", src) is not None


# ------------------------------------------------------------------------------------------
# the clocks
# ------------------------------------------------------------------------------------------

def clock_target(clock: str, root: Path = ROOT) -> tuple[str | None, int | None, str]:
    """(file the clock runs, its silence window in seconds, why) -- or (None, None, why) when the
    repository does not know the clock. Exact: each kind is read from the file that owns it."""
    kind, _, name = clock.partition(":")
    if kind not in CLOCK_KINDS or not name:
        return None, None, f"clock kind {kind!r} is not one of {CLOCK_KINDS}"
    if kind == "leg":
        src = _read(root / "desks" / "mt5" / "research" / "hourly_cycle.py")
        m = re.search(rf'_producer(?:_impl)?\(\s*"{re.escape(name)}",\s*"([^"]+)"', src)
        if not m:
            return None, None, f"no hourly_cycle leg named {name!r}"
        rel = m.group(1)
        for cand in (f"desks/mt5/{rel}", rel):
            if (root / cand).is_file():
                return cand, DEFAULT_SILENCE_S["leg"], f"hourly_cycle leg {name} runs {cand}"
        return None, None, f"leg {name} runs {rel}, which is not in the tree"
    if kind == "task":
        man = _read(root / "desks" / "mt5" / "ops" / "box_tasks.manifest")
        m = re.search(rf'^TASK name="{re.escape(name)}"(.*)$', man, re.M)
        if not m:
            return None, None, f"box_tasks.manifest declares no task {name!r}"
        line = m.group(1)
        runs = re.search(r'runs="([^"]+)"', line)
        trig = (re.search(r'trigger="([^"]+)"', line) or [None, ""])[1]
        silence = DEFAULT_SILENCE_S["task"]
        if re.search(r"\bdaily\b", trig or ""):
            silence = DAILY_SILENCE_S
        target = runs.group(1) if runs else None
        organ = re.search(r'organ="([^"]+)"', line)
        if organ and (root / organ.group(1)).is_file():
            target = organ.group(1)
        if not target or not (root / target).is_file():
            return None, None, f"task {name} runs {target!r}, which is not in the tree"
        return target, silence, f"box task {name} ({trig}) runs {target}"
    if kind == "fence":
        gate = _read(root / "scripts" / "run_law_gate.py")
        script = name if name.endswith(".py") else f"{name}.py"
        if f'"{script}"' not in gate or not (root / "scripts" / script).is_file():
            return None, None, f"run_law_gate.py runs no fence {script!r}"
        return f"scripts/{script}", DEFAULT_SILENCE_S["fence"], f"law fence {script}"
    unit = root / "ops" / f"{name}.timer"
    if not unit.is_file():
        return None, None, f"no VPS timer ops/{name}.timer"
    svc = _read(root / "ops" / f"{name}.service")
    m = re.search(r"ExecStart=.*?\b((?:scripts|desks|libs|ops)/[\w/.-]+\.(?:py|sh))", svc)
    return (m.group(1) if m else None), DEFAULT_SILENCE_S["timer"], f"VPS timer {name}"


# ------------------------------------------------------------------------------------------
# the rungs
# ------------------------------------------------------------------------------------------

def _rung(state: str, why: str) -> dict[str, str]:
    return {"state": state, "why": why}


def judge_declared(row: dict[str, Any]) -> dict[str, str]:
    bad: list[str] = []
    asserted = sorted(ASSERTED_KEYS & set(row))
    if asserted:
        bad.append(f"asserts a rung instead of deriving it: {asserted}")
    for f in FIELDS:
        if not row.get(f):
            bad.append(f"no {f}")
    if row.get("domain") not in DOMAINS:
        bad.append(f"domain {row.get('domain')!r} not in {DOMAINS}")
    auth = row.get("decision_authority") or {}
    if not isinstance(auth, dict) or auth.get("level") not in AUTHORITY or not auth.get("scope"):
        bad.append(f"decision_authority needs level in {AUTHORITY} and a scope")
    fail = row.get("failure_behaviour") or {}
    if (not isinstance(fail, dict) or fail.get("mode") not in FAILURE_MODES
            or not fail.get("marker") or not fail.get("says")):
        bad.append(f"failure_behaviour needs mode in {FAILURE_MODES}, a marker and what it says")
    for key in ("inputs", "outputs", "contracts", "runtime_process", "consumers",
                "verification"):
        if key in row and not isinstance(row[key], list):
            bad.append(f"{key} must be a list")
    if bad:
        return _rung(FALSE, "; ".join(bad))
    return _rung(TRUE, "nine facts declared")


def judge_implemented(row: dict[str, Any], root: Path = ROOT) -> dict[str, str]:
    owner = str(row.get("owner") or "")
    if not (root / owner).is_file():
        return _rung(FALSE, f"owner {owner} is not in the tree")
    src = _read(root / owner)
    defs = _defs(src)
    bad: list[str] = []
    for kind in ("inputs", "outputs"):
        for token in row.get(kind) or ():
            token = str(token)
            if token.startswith("api:"):
                if token[4:] not in defs:
                    bad.append(f"{kind} {token}: no def {token[4:]} in {owner}")
            elif token == EXIT_TOKEN:
                if "SystemExit" not in src and "sys.exit" not in src:
                    bad.append(f"{kind} exit:status: {owner} never exits with a status")
            elif token not in src:
                bad.append(f"{kind} {token}: not named in {owner}")
    marker = str((row.get("failure_behaviour") or {}).get("marker") or "")
    if marker and marker not in src:
        bad.append(f"failure marker {marker!r} is not in {owner}")
    for c in row.get("contracts") or ():
        if not (root / str(c)).is_file():
            bad.append(f"contract {c} is not in the tree")
    if bad:
        return _rung(FALSE, "; ".join(bad))
    return _rung(TRUE, f"{owner} names every input, output and its failure marker")


def _consumer_reads(consumer_src: str, row: dict[str, Any], consumer: str) -> bool:
    owner = str(row.get("owner") or "")
    if consumer == owner:
        return False
    for token in row.get("outputs") or ():
        token = str(token)
        if token.startswith("api:") or token == EXIT_TOKEN:
            if _names_module(consumer_src, owner) and (
                    token == EXIT_TOKEN or token[4:] in consumer_src):
                return True
        elif token in consumer_src:
            return True
    return False


def judge_connected(row: dict[str, Any], root: Path = ROOT) -> dict[str, str]:
    owner = str(row.get("owner") or "")
    bad: list[str] = []
    for c in row.get("consumers") or ():
        c = str(c)
        if not (root / c).is_file():
            bad.append(f"consumer {c} is not in the tree")
        elif not _consumer_reads(_read(root / c), row, c):
            bad.append(f"consumer {c} reads none of {owner}'s outputs")
    via = [str(v) for v in row.get("via") or ()]
    for clock in row.get("runtime_process") or ():
        target, _silence, why = clock_target(str(clock), root)
        if target is None:
            bad.append(f"{clock}: {why}")
            continue
        chain = [target, *via] if target != owner else [owner]
        if chain[-1] != owner:
            chain.append(owner)
        for here, nxt in itertools.pairwise(chain):
            if here == nxt:
                continue
            if not (root / here).is_file() or not _names_module(_read(root / here), nxt):
                bad.append(f"{clock}: {here} does not reach {nxt}")
                break
    if bad:
        return _rung(FALSE, "; ".join(bad))
    return _rung(TRUE, f"{len(row.get('consumers') or ())} consumer(s) read it; "
                       f"{len(row.get('runtime_process') or ())} clock(s) reach it")


def _tracked_unchanged(paths: list[Path], root: Path) -> set[Path]:
    """Files that are a git checkout's copy, not a run's output: tracked and equal to HEAD."""
    rels = []
    for p in paths:
        try:
            rels.append(p.relative_to(root).as_posix())
        except ValueError:
            continue
    if not rels:
        return set()
    try:
        tracked = subprocess.run(["git", "ls-files", "--", *rels], cwd=root, capture_output=True,
                                 text=True, timeout=30).stdout.split()
        dirty = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *rels], cwd=root,
                               capture_output=True, text=True, timeout=30).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return set(paths)          # cannot tell: treat as a copy, never as evidence
    return {root / t for t in tracked if t not in set(dirty)}


def locate(name: str, dirs: tuple[Path, ...] = ARTIFACT_DIRS) -> Path | None:
    for d in dirs:
        p = d / name
        if p.is_file():
            return p
    return None


def judge_running(row: dict[str, Any], root: Path = ROOT, *, now: float | None = None,
                  dirs: tuple[Path, ...] | None = None) -> dict[str, str]:
    now = time.time() if now is None else now
    silences = [clock_target(str(c), root)[1] for c in row.get("runtime_process") or ()]
    windows = [s for s in silences if s]
    if row.get("max_silence_s"):
        windows = [int(row["max_silence_s"])]
    window = max(windows) if windows else None
    files = [str(t) for t in row.get("outputs") or ()
             if not str(t).startswith("api:") and str(t) != EXIT_TOKEN]
    if window is None or not files:
        return _rung(UNMEASURED, "no file output with a silence window: running is read off "
                                 "the host process, not this map")
    if dirs is None:
        dirs = tuple(root / p.relative_to(ROOT) for p in ARTIFACT_DIRS)
    found = {f: locate(f, dirs) for f in files}
    present = [p for p in found.values() if p is not None]
    copies = _tracked_unchanged(present, root)
    evidence = [p for p in present if p not in copies]
    if not evidence:
        return _rung(UNMEASURED, f"none of {files} was written on this host "
                                 f"({len(present)} present only as a git copy)")
    ages = {p.name: now - p.stat().st_mtime for p in evidence}
    fresh = {n: a for n, a in ages.items() if a <= window}
    if fresh:
        n, a = min(fresh.items(), key=lambda kv: kv[1])
        return _rung(TRUE, f"{n} is {a / 3600:.1f}h old, inside its {window / 3600:.0f}h window")
    n, a = min(ages.items(), key=lambda kv: kv[1])
    return _rung(FALSE, f"freshest output {n} is {a / 3600:.1f}h old, past its "
                        f"{window / 3600:.0f}h window")


def judge_tests(row: dict[str, Any], root: Path = ROOT) -> dict[str, str]:
    """The static half of behaviour_verified: each verification test exists and names the owner."""
    owner = str(row.get("owner") or "")
    bad = []
    for t in row.get("verification") or ():
        t = str(t)
        if not (root / t).is_file():
            bad.append(f"test {t} is not in the tree")
        elif not _names_module(_read(root / t), owner):
            bad.append(f"test {t} never names {_stem(owner)}")
    if bad:
        return _rung(FALSE, "; ".join(bad))
    return _rung(TRUE, f"{len(row.get('verification') or ())} test(s) exercise {_stem(owner)}")


def derive(row: dict[str, Any], root: Path = ROOT, *, now: float | None = None,
           dirs: tuple[Path, ...] | None = None) -> dict[str, Any]:
    """One function's ladder, every rung derived. Rungs above a non-TRUE one are not judged."""
    rungs: dict[str, dict[str, str]] = {}
    rungs["declared"] = judge_declared(row)
    rungs["implemented"] = judge_implemented(row, root)
    rungs["connected"] = judge_connected(row, root)
    rungs["running"] = judge_running(row, root, now=now, dirs=dirs)
    tests = judge_tests(row, root)
    if tests["state"] == FALSE:
        rungs["behaviour_verified"] = tests
    elif rungs["running"]["state"] != TRUE:
        rungs["behaviour_verified"] = _rung(UNMEASURED, f"tests ready ({tests['why']}); "
                                                        f"running is {rungs['running']['state']}")
    else:
        rungs["behaviour_verified"] = _rung(TRUE, f"running and {tests['why']}")
    rung = "none"
    for name in RUNGS:
        if rungs[name]["state"] != TRUE:
            break
        rung = name
    false_static = [n for n in (*STATIC_RUNGS,) if rungs[n]["state"] == FALSE]
    if tests["state"] == FALSE:
        false_static.append("behaviour_verified")
    return {"id": row.get("id"), "domain": row.get("domain"), "owner": row.get("owner"),
            "authority": (row.get("decision_authority") or {}).get("level"),
            "rung": rung, "rungs": rungs, "false_static": false_static}


def build(root: Path = ROOT, registry: dict[str, Any] | None = None, *,
          now: float | None = None, dirs: tuple[Path, ...] | None = None) -> dict[str, Any]:
    reg = load_registry(root / REGISTRY.relative_to(ROOT)) if registry is None else registry
    rows = [r for r in reg.get("functions") or () if isinstance(r, dict)]
    problems: list[str] = []
    ids = Counter(str(r.get("id")) for r in rows)
    problems += [f"function id {i!r} is declared {n} times" for i, n in ids.items() if n > 1]
    covered = {r.get("domain") for r in rows}
    problems += [f"domain {d!r} has no essential function in the registry"
                 for d in DOMAINS if d not in covered]
    functions = [derive(r, root, now=now, dirs=dirs) for r in rows]
    for f in functions:
        for n in f["false_static"]:
            problems.append(f"{f['id']}: FALSE rung {n} -- {f['rungs'][n]['why']}")
    by_rung = Counter(f["rung"] for f in functions)
    return {
        "schema": "function_map/1",
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "registry": REGISTRY.relative_to(ROOT).as_posix(),
        "ladder": list(RUNGS),
        "n_functions": len(functions),
        "by_rung": {r: by_rung.get(r, 0) for r in ("none", *RUNGS)},
        "by_domain": dict(sorted(Counter(str(f["domain"]) for f in functions).items())),
        "functions": functions,
        "problems": problems,
        "ok": not problems,
        "basis": ("every rung derived from the tree and this host's artifacts; the registry "
                  "declares facts and may not assert a rung. running and behaviour_verified "
                  "are UNMEASURED on a host that wrote none of the outputs"),
    }


def published_false_rungs(published: dict[str, Any], fresh: dict[str, Any]) -> list[str]:
    """Rungs the PUBLISHED map claims that a re-derivation no longer supports.

    Only the static rungs are compared: running is a fact about the hour the map was written,
    and a map an hour old may honestly disagree with now on it."""
    now = {f.get("id"): f for f in fresh.get("functions") or ()}
    out: list[str] = []
    for f in published.get("functions") or ():
        cur = now.get(f.get("id"))
        if cur is None:
            out.append(f"{f.get('id')}: published, but the registry no longer declares it")
            continue
        for r in STATIC_RUNGS:
            was = ((f.get("rungs") or {}).get(r) or {}).get("state")
            if was == TRUE and cur["rungs"][r]["state"] != TRUE:
                out.append(f"{f.get('id')}: published {r}=TRUE, re-derived "
                           f"{cur['rungs'][r]['state']} ({cur['rungs'][r]['why']})")
    return out


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path or OUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    tmp.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    if not args.no_write:
        write(doc)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
        return 0
    print(f"function map: {doc['n_functions']} functions; by rung {doc['by_rung']}")
    for f in doc["functions"]:
        print(f"  {f['id']:<34} {f['rung']:<19} {f['owner']}")
    for p in doc["problems"]:
        print(f"  PROBLEM: {p}")
    # The publisher never fails the cycle: the law fence is where a false rung is judged.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
