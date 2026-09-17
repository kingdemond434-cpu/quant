"""THE WEEKLY SIMPLIFIER -- capability up while complexity is controlled.

    "Capability up while complexity is controlled; the simplifier proposes, a session decides."

WHY A SEPARATE ORGAN FROM module_rent. Rent asks one question per module -- what did this buy for
what it cost -- and that question is blind to the cheapest waste a growing desk accumulates: two
organs doing one job, six copies of `_read_json`, four JSON stores holding the same keys under
different names, and two legs that have never once run apart. None of those shows up as a bad
ROI. They show up as a tree that is twice the size it needs to be, where every change has to be
made in two places and one of them gets forgotten.

FIVE DETECTORS, each with a declared threshold, each reporting PAIRS AND GROUPS BY NAME so the
proposal can be checked rather than believed:

    overlaps      two organs whose artifact keys, inputs or function-name token sets overlap by
                  more than OVERLAP_JACCARD. The one that sounds like a duplicate usually is.
    unify         one function NAME implemented in several organs with the SAME normalised
                  structure (the AST's node sequence, so `p`/`path` and `d`/`doc` hash alike).
                  Six atomic writers is five too many.
    duplicate     two JSON stores whose top-level keys overlap by more than REGISTRY_OVERLAP.
    registries    Two registries of the same thing is two answers to one question.
    services      two legs that have never run apart (ADJACENCY_SHARE of A's runs are immediately
                  followed by B, MIN_ADJACENT times) and that share an input. Two processes, two
                  start-up costs, two failure modes, one job.
    dead          on no clock, zero MEASURED downstream research in MODULE_RENT_RESEARCH.json,
                  no commit in 30 days, and not EXEMPT. Everything else is alive until measured
                  otherwise: an UNMEASURED module is never proposed for deletion.

WHAT IT REFUSES TO DO. It does not delete, merge, unify or disable anything, and it does not put
a number on the saving from a merge -- a redesign's saving is UNMEASURED until the redesign
exists, and inflating `loc_removable` with a guess would make the one number here that has to be
trustworthy the one number here that is not. `loc_removable` counts exactly two things: the LOC
of the modules proposed for deletion, and the duplicated copies of unified helpers.

AND IT NAMES WHAT THE PROPOSAL WOULD COST. `capability_at_risk` lists, for every module proposed
for deletion, the organs that import it or read the artifacts it writes. A deletion with a
consumer is not a cleanup, it is an outage, and the list is there so the session deciding can
see the difference before it decides.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import module_rent as rent  # noqa: E402  (sys.path is set above; the desk imports by bare name)

OUT = DESK / "reports" / "SIMPLIFIER.json"
DATA = DESK / "data"

OVERLAP_JACCARD = 0.50
REGISTRY_OVERLAP = 0.60
#: A Jaccard over two-element sets is noise; both sides must carry weight.
MIN_KEYS = 3
MIN_FUNCS = 4
#: A helper worth unifying has a body. Two-statement wrappers hash alike everywhere and unifying
#: them buys nothing but an import.
MIN_BODY_STATEMENTS = 3
MIN_COPIES = 2
#: "Always run consecutively": B immediately follows A in at least this share of A's runs.
ADJACENCY_SHARE = 0.80
MIN_ADJACENT = 3
ADJACENCY_GAP_S = 3600.0
#: The 74 MB research_queue_archive.json is a registry nobody compares; reading it to find out
#: would cost more than the finding. Skipped BY NAME in the report, never silently.
MAX_REGISTRY_BYTES = 8_000_000
#: A key that half the desk names (universe.json, compute_ledger.jsonl) is not evidence that one
#: module CONSUMES another. Measured on this tree: without this bound `daily_research_os.py` read
#: 42 consumers, all of them strangers that happen to open the same bars file, and an at-risk
#: list that cries wolf 42 times is a list nobody reads on the one deletion that matters.
CONSUMER_KEY_MAX_SHARERS = 5


def _atomic(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def paths_for(rt: Path) -> dict[str, Path]:
    if Path(rt) == ROOT:
        return {"rent": rent.OUT, "compute": rent.COMPUTE, "data": DATA, "out": OUT}
    d = Path(rt) / "desks" / "mt5"
    return {"rent": d / "reports" / "MODULE_RENT_RESEARCH.json",
            "compute": d / "data" / "compute_ledger.jsonl", "data": d / "data",
            "out": d / "reports" / "SIMPLIFIER.json"}


# --------------------------------------------------------------------------- source facts
def _structure(node: ast.AST) -> str:
    """The node-class sequence of a body: identical logic under different variable names hashes
    the same, and two functions that merely share a name do not."""
    seq = [type(n).__name__ for n in ast.walk(node)]
    return hashlib.sha256("|".join(seq).encode()).hexdigest()[:16]


def module_facts(path: Path) -> dict[str, Any]:
    """Artifact keys, function names, and one structural hash per top-level function."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"keys": set(), "funcs": {}, "names": set(), "loc": 0, "imports": set()}
    keys = rent.artifact_keys(text)
    funcs: dict[str, tuple[str, int]] = {}
    names: set[str] = set()
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        tree = None
    if tree is not None:
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names.add(node.name)
            if len(node.body) < MIN_BODY_STATEMENTS:
                continue
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            funcs[node.name] = (_structure(ast.Module(body=node.body, type_ignores=[])),
                                max(1, int(end) - int(node.lineno) + 1))
    bare, _ = rent._imports(path)
    return {"keys": keys, "funcs": funcs, "names": names,
            "loc": len(text.splitlines()), "imports": bare}


# --------------------------------------------------------------------------- detectors
def overlaps(facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Two organs that name the same artifacts or expose the same surface."""
    inv: dict[str, list[str]] = defaultdict(list)
    for rel, f in facts.items():
        for k in f["keys"]:
            inv["k:" + k].append(rel)
        for n in f["names"]:
            inv["f:" + n].append(rel)
    pairs: set[tuple[str, str]] = set()
    for members in inv.values():
        if len(members) > 40:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                pairs.add((a, b) if a < b else (b, a))
    out: list[dict[str, Any]] = []
    for a, b in sorted(pairs):
        fa, fb = facts[a], facts[b]
        jk = rent.jaccard(fa["keys"], fb["keys"]) if (
            len(fa["keys"]) >= MIN_KEYS and len(fb["keys"]) >= MIN_KEYS) else 0.0
        jn = rent.jaccard(fa["names"], fb["names"]) if (
            len(fa["names"]) >= MIN_FUNCS and len(fb["names"]) >= MIN_FUNCS) else 0.0
        best = max(jk, jn)
        if best <= OVERLAP_JACCARD:
            continue
        out.append({"a": a, "b": b, "artifact_jaccard": round(jk, 3),
                    "surface_jaccard": round(jn, 3),
                    "shared_artifacts": sorted(fa["keys"] & fb["keys"])[:6],
                    "loc": [fa["loc"], fb["loc"]],
                    "why": (f"artifact keys overlap {jk:.0%}, function surface {jn:.0%} "
                            f"(> {OVERLAP_JACCARD:.0%})")})
    out.sort(key=lambda d: -max(float(d["artifact_jaccard"]), float(d["surface_jaccard"])))
    return out


def unify(facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One function name, one structure, many files: the copies are the finding."""
    groups: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for rel, f in facts.items():
        for name, (h, loc) in f["funcs"].items():
            groups[(name, h)].append((rel, loc))
    out: list[dict[str, Any]] = []
    for (name, h), members in groups.items():
        if len(members) < MIN_COPIES + 1:
            continue
        locs = np.array([m[1] for m in members], dtype=float)
        med = float(np.median(locs))
        out.append({"function": name, "structure": h, "copies": len(members),
                    "modules": sorted(m[0] for m in members)[:12],
                    "median_body_loc": round(med, 1),
                    "loc_removable": round((len(members) - 1) * med),
                    "why": (f"{len(members)} structurally identical `{name}` bodies; one shared "
                            f"helper removes {len(members) - 1} copies")})
    out.sort(key=lambda d: -int(d["loc_removable"]))
    return out


def duplicate_registries(data_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """JSON stores whose top-level keys overlap by more than REGISTRY_OVERLAP."""
    keys: dict[str, set[str]] = {}
    skipped: list[str] = []
    if not data_dir.is_dir():
        return [], [f"{data_dir} is not a directory"]
    for p in sorted(data_dir.glob("*.json")):
        try:
            if p.stat().st_size > MAX_REGISTRY_BYTES:
                skipped.append(f"{p.name} ({p.stat().st_size // 1_000_000} MB > cap)")
                continue
            d = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            skipped.append(f"{p.name} unreadable ({type(exc).__name__})")
            continue
        if isinstance(d, dict) and len(d) >= MIN_KEYS:
            keys[p.name] = set(map(str, d))
    out: list[dict[str, Any]] = []
    names = sorted(keys)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            jk = rent.jaccard(keys[a], keys[b])
            if jk <= REGISTRY_OVERLAP:
                continue
            out.append({"a": a, "b": b, "key_overlap": round(jk, 3),
                        "n_keys": [len(keys[a]), len(keys[b])],
                        "shared": sorted(keys[a] & keys[b])[:8],
                        "why": f"top-level keys overlap {jk:.0%} (> {REGISTRY_OVERLAP:.0%}): "
                               f"two stores, one question"})
    out.sort(key=lambda d: -float(d["key_overlap"]))
    return out, skipped


def services(ledger: list[dict[str, Any]], facts: dict[str, dict[str, Any]],
             stem_to_rel: dict[str, str]) -> list[dict[str, Any]]:
    """Legs that have never run apart AND share an input: one process, not two."""
    rows = [r for r in ledger if r.get("run") and r.get("at")]
    rows.sort(key=lambda r: str(r["at"]))
    runs: dict[str, int] = defaultdict(int)
    adj: dict[tuple[str, str], int] = defaultdict(int)
    for i, r in enumerate(rows):
        runs[str(r["run"])] += 1
        if i == 0:
            continue
        prev = rows[i - 1]
        ta, tb = rent._at(prev.get("at")), rent._at(r.get("at"))
        if ta is None or tb is None or (tb - ta).total_seconds() > ADJACENCY_GAP_S:
            continue
        if str(prev.get("kind")) != str(r.get("kind")) or prev["run"] == r["run"]:
            continue
        adj[(str(prev["run"]), str(r["run"]))] += 1
    out: list[dict[str, Any]] = []
    for (a, b), n in adj.items():
        if n < MIN_ADJACENT or runs.get(a, 0) == 0 or n / runs[a] < ADJACENCY_SHARE:
            continue
        ra, rb = stem_to_rel.get(a), stem_to_rel.get(b)
        shared = (facts[ra]["keys"] & facts[rb]["keys"]) if (ra in facts and rb in facts) else set()
        if not shared:
            continue
        out.append({"legs": [a, b], "modules": [ra, rb], "adjacent_runs": n,
                    "share_of_first": round(n / runs[a], 3),
                    "shared_inputs": sorted(shared)[:6],
                    "why": (f"`{b}` immediately follows `{a}` in {n / runs[a]:.0%} of {runs[a]} "
                            f"runs and they share {len(shared)} input(s): one service")})
    out.sort(key=lambda d: -int(d["adjacent_runs"]))
    return out


def dead(rent_doc: dict[str, Any], facts: dict[str, dict[str, Any]],
         stems: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Unwired, zero MEASURED downstream, untouched for 30 days, not EXEMPT -- and who would
    notice. An UNMEASURED module is never here: it has not been shown to be dead, only unread."""
    extra, never = rent._wiring_exempt()
    sharers: dict[str, int] = defaultdict(int)
    for f in facts.values():
        for k in f["keys"]:
            sharers[k] += 1
    out: list[dict[str, Any]] = []
    at_risk: list[dict[str, Any]] = []
    for r in rent_doc.get("rows") or []:
        if not isinstance(r, dict):
            continue
        mod = str(r.get("module") or "")
        if r.get("clock") not in (None, "none"):
            continue
        down = r.get("candidates_30d")
        if down is None:
            continue                       # UNMEASURED is not dead
        if int(down) + int(r.get("admissions_30d") or 0) + int(r.get("survivors_30d") or 0) > 0:
            continue
        commits = r.get("maintenance_commits_30d")
        if commits is None or int(commits) > 0:
            continue
        why_exempt = rent.exempt_reason(mod, extra, never)
        if why_exempt:
            continue
        f = facts.get(mod, {})
        stem = Path(mod).stem
        own = {k for k in f.get("keys", ()) if sharers.get(k, 0) <= CONSUMER_KEY_MAX_SHARERS}
        consumers = sorted({other for other, fo in facts.items()
                            if other != mod and (stem in fo["imports"]
                                                 or (own and fo["keys"] & own))})
        out.append({"module": mod, "loc": int(r.get("loc") or 0),
                    "why": ("on no clock, zero measured candidates/admissions/survivors in 30 "
                            "days, no commit in 30 days, not exempt"),
                    "n_consumers": len(consumers)})
        if consumers:
            at_risk.append({"module": mod, "consumers": consumers[:10],
                            "why": ("deleting it breaks these importers, or these readers of an "
                                    "artifact only it and they name")})
    out.sort(key=lambda d: -int(d["loc"]))
    _ = stems
    return out, at_risk


# --------------------------------------------------------------------------- the build
def build(root: Path | None = None, *, budget_s: float = 300.0,
          now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    rt = Path(root) if root is not None else ROOT
    pp = paths_for(rt)
    at = now or datetime.now(tz=UTC)
    unmeasured: list[str] = []

    cen = rent.census(rt)
    facts = {rel: module_facts(c["path"]) for rel, c in cen.items()}
    stems = {Path(rel).stem: rel for rel in facts}

    rent_doc = rent._read_json(pp["rent"])
    if not rent_doc:
        unmeasured.append(f"module rent: {pp['rent']} absent; DEAD machinery is UNMEASURED "
                          f"(nothing is proposed for deletion without a measured zero)")

    ov = overlaps(facts) if time.monotonic() - t0 < budget_s else []
    un = unify(facts) if time.monotonic() - t0 < budget_s else []
    dup, skipped = duplicate_registries(pp["data"]) if time.monotonic() - t0 < budget_s \
        else ([], ["budget exhausted before the registry scan"])
    if skipped:
        unmeasured.append("registries not compared: " + ", ".join(skipped[:8]))
    led = rent._jsonl(pp["compute"])
    if not led:
        unmeasured.append(f"compute ledger: {pp['compute']} absent; no service candidate "
                          f"(consecutive-run evidence is UNMEASURED)")
    svc = services(led, facts, stems)
    dd, risk = dead(rent_doc, facts, stems) if rent_doc else ([], [])

    loc_dead = sum(int(d["loc"]) for d in dd)
    loc_unify = sum(int(g["loc_removable"]) for g in un)
    doc = {
        "at": at.isoformat(timespec="seconds"),
        "n_modules": len(facts),
        "elapsed_s": round(time.monotonic() - t0, 2),
        "thresholds": {"overlap_jaccard": OVERLAP_JACCARD, "registry_overlap": REGISTRY_OVERLAP,
                       "min_copies": MIN_COPIES + 1, "adjacency_share": ADJACENCY_SHARE,
                       "min_adjacent_runs": MIN_ADJACENT},
        "overlaps": ov[:60],
        "unify": un[:60],
        "duplicate_registries": dup[:40],
        "services": svc[:40],
        "dead": dd[:60],
        "loc_removable": loc_dead + loc_unify,
        "loc_removable_basis": (f"{loc_dead} LOC of {len(dd)} dead module(s) + {loc_unify} LOC of "
                                f"duplicated helper copies in {len(un)} unify group(s); the "
                                f"saving from a MERGE is UNMEASURED until the merge exists and "
                                f"is deliberately NOT counted here"),
        "capability_at_risk": risk[:40],
        "consolidation_plan": _plan(ov, un, dup, svc, dd),
        "counts": {"overlaps": len(ov), "unify": len(un), "duplicate_registries": len(dup),
                   "services": len(svc), "dead": len(dd)},
        "unmeasured": unmeasured,
        "rule": ("capability up while complexity is controlled; the simplifier proposes, a "
                 "session decides"),
    }
    return doc


def _plan(ov: list[dict[str, Any]], un: list[dict[str, Any]], dup: list[dict[str, Any]],
          svc: list[dict[str, Any]], dd: list[dict[str, Any]]) -> list[str]:
    plan: list[str] = []
    for g in un[:5]:
        plan.append(f"UNIFY `{g['function']}` -- {g['copies']} identical copies "
                    f"({g['loc_removable']} LOC) into one shared helper; first callers: "
                    + ", ".join(g["modules"][:3]))
    for p in ov[:5]:
        plan.append(f"MERGE {p['a']} with {p['b']} -- {p['why']}")
    for p in dup[:3]:
        plan.append(f"ONE REGISTRY for {p['a']} and {p['b']} -- {p['why']}")
    for s in svc[:3]:
        plan.append(f"ONE SERVICE for legs {s['legs'][0]} + {s['legs'][1]} -- {s['why']}")
    for d in dd[:5]:
        risk = "" if not d["n_consumers"] else f" (WARNING: {d['n_consumers']} consumer(s))"
        plan.append(f"DELETE {d['module']} ({d['loc']} LOC) -- {d['why']}{risk}")
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--top", type=int, default=6)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    print(f"simplifier: {doc['n_modules']} module(s) in {doc['elapsed_s']}s; "
          + ", ".join(f"{k}={v}" for k, v in doc["counts"].items())
          + f"; {doc['loc_removable']} LOC removable")
    for line in doc["consolidation_plan"][:a.top * 3]:
        print(f"  {line[:118]}")
    for u in doc["unmeasured"]:
        print(f"  UNMEASURED: {u[:112]}")
    if a.dry_run:
        return 0
    _atomic(OUT, doc)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
