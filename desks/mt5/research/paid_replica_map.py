#!/usr/bin/env python3
"""THE PAID-REPLICA MAP, RE-RANKED EVERY HOUR -- every paid dataset rebuilt from free inputs, or
named as queued or blocked, never left unattempted.

THE PRINCIPAL (2026-11-18): reverse-engineer the paid alternative datasets tier-1 firms buy --
rebuild the SIGNAL each one sells from free public inputs, as a standing lane, at maximum ROI,
and make it CONTINUOUS: every pass adds newly catalogued paid products, re-scores ROI by edge per
instrument, and emits the top unbuilt items as build tasks. Every catalogue row ends in exactly
one state:

    BUILT    a working free proxy exists, cited by its fetcher (file:line, read live)
    QUEUED   the build task is emitted, with its named free inputs
    BLOCKED  only with a concrete legal or terms reason (host + clause) and a missed_growth line

"Unknown" and "no attempt" are not states: `row_state` returns one of the three for every row,
and the test suite fails on a row without one.

THE MAP IS DATA. `docs/research/paid_replica_map.json` holds the categories (paid alt-data and the
Bloomberg Terminal's five trading functions): the catalogue classes and keywords that route a paid
row to it, the MT5 instruments it moves, an edge / buildability / effort prior, the fetchers that
already build it, the pending branches that would, and the best free inputs. This organ never
edits it.

WHAT ONE PASS DOES (owned by the hourly leg `paid_substitute_engine`, which calls `run` with the
catalogue it just loaded -- seeds, the robots-respecting listing crawl, and the Asia table):

  1. ROUTE every catalogue row to a category: keywords over vendor/dataset/measures first (the
     specific beats the general: "oil storage" before "satellite"), then the row's class.
  2. RESOLVE each category's state LIVE: a cited alt_proxies source counts as BUILT only while it
     is in `alt_proxies.BY_ID` with terms `confirmed` and not DEAD; a cited organ only while its
     file exists. The citation is recomputed (`file:line`) every pass, so it never rots.
  3. SCORE: roi = edge x sum(instrument value over instruments `universe_policy.may_hypothesise`
     admits -- fail closed) x buildability / effort x (1 + ln(1 + paid rows routed) / 4). A
     measured gain-test verdict for a built source (reports/ALT_PROXIES.json) moves edge x1.25
     on PASS, x0.75 on FAIL; absent, the prior stands and is labelled so.
  4. EMIT the top unbuilt categories as build tasks -- deep-forest grounds in
     `data/deep_forest_queue/paid_replica_builds.json`, which deep_forest_miner reads every hour --
     and write `reports/PAID_REPLICA_MAP.json` with the ranked table, every row's state and the
     coverage figure (share of rows BUILT or QUEUED; BUILT share beside it).

Nothing here sizes, vetoes or trades. It ranks, cites and queues. It is a LIBRARY of the
`paid_substitute_engine` leg, not a separate clock: `python research/paid_substitute_engine.py
--no-fetch --dry-run` runs it, and the ranked table lands in the engine's report.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MAP = ROOT / "docs" / "research" / "paid_replica_map.json"
REPORT = DESK / "reports" / "PAID_REPLICA_MAP.json"
QUEUE = DESK / "data" / "deep_forest_queue" / "paid_replica_builds.json"
ALT_REPORT = DESK / "reports" / "ALT_PROXIES.json"
ALT_PROXIES_PY = DESK / "research" / "alt_proxies.py"

STATES = ("BUILT", "QUEUED", "BLOCKED")
#: Build tasks emitted per pass: the top unbuilt categories by ROI.
TOP_TASKS = 8
UNCLASSIFIED = "unclassified"
UNMEASURED = "UNMEASURED"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def load_map(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or MAP).read_text("utf-8"))
    except (OSError, ValueError):
        return {"categories": []}
    return doc if isinstance(doc, dict) else {"categories": []}


# ----------------------------------------------------------------------------- live citations
def _source_lines(py: Path) -> dict[str, int]:
    """`id="<source id>"` -> line number in alt_proxies.py, read now (never a stored line)."""
    out: dict[str, int] = {}
    try:
        for i, line in enumerate(py.read_text("utf-8").splitlines(), 1):
            m = re.match(r'\s+id="([a-z0-9_]+)",', line)
            if m and m[1] not in out:
                out[m[1]] = i
    except OSError:
        pass
    return out


def _alt_sources() -> dict[str, dict[str, Any]]:
    """Every alt_proxies source: its terms verdict and whether it is DEAD. Empty when the organ
    cannot be imported here, in which case no source citation counts as BUILT."""
    try:
        from research import alt_proxies as A
    except Exception:
        return {}
    return {s.id: {"terms": s.terms, "dead": bool(s.archive_until)} for s in A.SOURCES}


def resolve_built(cat: Mapping[str, Any], *, sources: Mapping[str, Mapping[str, Any]],
                  lines: Mapping[str, int], root: Path = ROOT) -> tuple[list[dict[str, Any]],
                                                                         list[dict[str, Any]]]:
    """(working fetchers, cited-but-not-working) for a category, each with a live citation."""
    ok: list[dict[str, Any]] = []
    bad: list[dict[str, Any]] = []
    rel = ALT_PROXIES_PY.relative_to(ROOT).as_posix()
    for b in cat.get("built") or []:
        if b.get("source_id"):
            sid = str(b["source_id"])
            s = sources.get(sid)
            cite = f"{rel}:{lines[sid]}" if sid in lines else rel
            row = {"fetcher": cite, "source_id": sid}
            if s is None:
                bad.append({**row, "why": "not an alt_proxies source on this checkout"})
            elif s.get("terms") != "confirmed":
                bad.append({**row, "why": f"terms {s.get('terms')}: never fetched"})
            elif s.get("dead"):
                bad.append({**row, "why": "DEAD: the publisher stopped (history only)"})
            else:
                ok.append(row)
        elif b.get("organ"):
            path = str(b["organ"])
            row = {"fetcher": path, **({"note": b["note"]} if b.get("note") else {})}
            (ok if (root / path).is_file() else bad).append(
                row if (root / path).is_file() else {**row, "why": "file absent"})
    return ok, bad


# ----------------------------------------------------------------------------- routing
def _text(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get(k) or "") for k in ("vendor", "dataset", "measures")).lower()


def _kw_hit(kw: str, text: str) -> bool:
    """A keyword is a whole word or phrase; a trailing `*` makes it a prefix (`agricultur*`)."""
    k = str(kw).lower()
    stem = k.endswith("*")
    pat = r"(?<![a-z0-9])" + re.escape(k.rstrip("*")) + ("" if stem else r"(?![a-z0-9])")
    return re.search(pat, text) is not None


def route(row: Mapping[str, Any], cats: Sequence[Mapping[str, Any]]) -> str:
    """The category a paid row is rebuilt under.

      1. a terminal product -> its parent's function group;
      2. a SUB-category (no classes of its own) whose `from_classes` holds the row's class and
         whose keyword the row's vendor/dataset/measures text carries ("oil storage" inside
         satellite) -- the specific beats the general;
      3. the category that owns the row's class;
      4. a row with no known class (a crawled listing marked UNSTATED): the first keyword hit
         over every category;
      5. UNCLASSIFIED (queued for classification, never silently dropped)."""
    cls = str(row.get("class") or "")
    if cls == "terminals":
        return "terminal:" + str(row.get("parent") or "bloomberg_terminal")
    text = _text(row)
    for c in cats:
        if c.get("classes") or cls not in (c.get("from_classes") or []):
            continue
        if any(_kw_hit(k, text) for k in c.get("keywords") or []):
            return str(c["id"])
    for c in cats:
        if cls and cls in (c.get("classes") or []):
            return str(c["id"])
    for c in cats:
        if any(_kw_hit(k, text) for k in c.get("keywords") or []):
            return str(c["id"])
    return UNCLASSIFIED


# ----------------------------------------------------------------------------- scoring
def measured_gains(path: Path | None = None) -> dict[str, str]:
    """source id -> PASS / FAIL from alt_proxies' own gain tests on the box; {} when absent."""
    try:
        doc = json.loads((path or ALT_REPORT).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    for key, g in (doc.get("gain_tests") or {}).items() if isinstance(doc, dict) else []:
        if not isinstance(g, dict):
            continue
        sid = str(g.get("source") or g.get("source_id") or str(key).split("|")[0])
        v = str(g.get("verdict") or "")
        if v == "PASS" or (v == "FAIL" and out.get(sid) != "PASS"):
            out[sid] = v
    return out


def admissible(symbols: Iterable[str], may: Callable[[str], bool]) -> list[str]:
    out = []
    for s in symbols:
        try:
            if may(s):
                out.append(s)
        except Exception:
            continue
    return out


def _default_may(sym: str) -> bool:
    from research import universe_policy
    return bool(universe_policy.may_hypothesise(sym, "exogenous_conditioner"))


def score(cat: Mapping[str, Any], *, values: Mapping[str, float], default_value: float,
          n_rows: int, gain: str | None, may: Callable[[str], bool]) -> dict[str, Any]:
    syms = admissible((cat.get("instruments") or {}).keys(), may)
    breadth = sum(float(values.get(s, default_value)) for s in syms)
    edge = float(cat.get("edge") or 0.0)
    edge_basis = "prior"
    if gain == "PASS":
        edge, edge_basis = edge * 1.25, "measured PASS (x1.25)"
    elif gain == "FAIL":
        edge, edge_basis = edge * 0.75, "measured FAIL (x0.75)"
    effort = max(0.5, float(cat.get("effort_days") or 1.0))
    roi = (edge * breadth * float(cat.get("buildability") or 0.0) / effort
           * (1.0 + math.log1p(max(0, n_rows)) / 4.0))
    return {"roi": round(roi, 4), "edge": round(edge, 4), "edge_basis": edge_basis,
            "breadth": round(breadth, 3), "instruments_admitted": syms,
            "instruments_refused": sorted(set(cat.get("instruments") or {}) - set(syms))}


def category_state(cat: Mapping[str, Any], ok: list[dict[str, Any]]) -> str:
    """BUILT with a working fetcher; else QUEUED when free inputs are named; else BLOCKED only on
    a named terms clause; a category with none of the three is a defect the test catches."""
    if ok:
        return "BUILT"
    if cat.get("free_inputs"):
        return "QUEUED"
    blk = cat.get("blocked") or {}
    if blk.get("host") and blk.get("clause") and blk.get("missed_growth"):
        return "BLOCKED"
    return "QUEUED" if cat.get("blocked_inputs") else ""


def row_state(row: Mapping[str, Any], cats_by_id: Mapping[str, Mapping[str, Any]],
              grounds_by_row: Mapping[str, list[str]] | None = None) -> dict[str, Any]:
    """Exactly one of STATES for one paid catalogue row, with what backs it."""
    cid = str(row.get("_category"))
    if cid.startswith("terminal:"):
        parent = cid.split(":", 1)[1]
        funcs = [c for c in cats_by_id.values() if c.get("parent") == parent]
        built = [c for c in funcs if c.get("_state") == "BUILT"]
        unbuilt = [c for c in funcs if c.get("_state") != "BUILT"]
        if funcs and not unbuilt:
            return {"state": "BUILT", "category": cid,
                    "fetchers": [f for c in built for f in c.get("_fetchers") or []]}
        return {"state": "QUEUED", "category": cid,
                "fetchers": [f for c in built for f in c.get("_fetchers") or []],
                "build_tasks": [str(c["id"]) for c in unbuilt],
                "inputs": [i["name"] for c in unbuilt for i in c.get("free_inputs") or []]}
    cat = cats_by_id.get(cid)
    if cat is None:
        grounds = list((grounds_by_row or {}).get(str(row.get("id")), []))
        return {"state": "QUEUED", "category": UNCLASSIFIED, "build_tasks": ["classify"],
                "inputs": grounds or [f"paidsub|vendor|{row.get('id')}|public_web"],
                "why": "no keyword or class routes it yet: the vendor-replica hunt is its task"}
    st = str(cat.get("_state") or "")
    out: dict[str, Any] = {"state": st, "category": cid}
    if st == "BUILT":
        out["fetchers"] = cat.get("_fetchers") or []
    elif st == "QUEUED":
        out["inputs"] = [i["name"] for i in cat.get("free_inputs") or []]
        out["build_tasks"] = [cid]
    elif st == "BLOCKED":
        out["blocked"] = cat.get("blocked")
    return out


# ----------------------------------------------------------------------------- build tasks
def build_grounds(tasks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Each unbuilt category as deep-forest `search` grounds over its named free inputs, in the
    shape `deep_forest_miner._queued_grounds` reads (name, route, queries)."""
    out: list[dict[str, Any]] = []
    for t in tasks:
        for i, inp in enumerate(t.get("inputs") or []):
            name = str(inp.get("name") or "")
            host = re.sub(r"^https?://([^/]+).*$", r"\1", str(inp.get("url") or ""))
            out.append({
                "name": f"paidreplica|{t['id']}|{i}",
                "cluster": "paid_replica_builds", "kind": "dataset", "route": "search",
                "site": host if "." in host else "", "language": "en", "region": "global",
                "weight": round(min(1.0, 0.6 + float(t.get("roi") or 0.0) / 50.0), 3),
                "queries": [f"{name} csv download", f"{name} api documentation",
                            f"{name} terms of use"],
                "class": str(t["id"]), "target_type": "build_task",
                "why": f"build task {t['id']} (roi {t.get('roi')}): free input {name}"})
    return out


# ----------------------------------------------------------------------------- the pass
def run(catalogue: list[Mapping[str, Any]], *, now: datetime | None = None,
        map_path: Path | None = None, report: Path | None = None, queue: Path | None = None,
        alt_report: Path | None = None, may: Callable[[str], bool] | None = None,
        sources: Mapping[str, Mapping[str, Any]] | None = None,
        grounds_by_row: Mapping[str, list[str]] | None = None,
        write: bool = True, root: Path = ROOT) -> dict[str, Any]:
    now = now or _now()
    m = load_map(map_path)
    cats = [dict(c) for c in m.get("categories") or [] if isinstance(c, dict) and c.get("id")]
    by_id = {str(c["id"]): c for c in cats}
    srcs = _alt_sources() if sources is None else dict(sources)
    lines = _source_lines(ALT_PROXIES_PY)
    gains = measured_gains(alt_report)
    may_fn = may or _default_may
    values = {str(k): float(v) for k, v in (m.get("instrument_value") or {}).items()}
    dv = float(m.get("default_instrument_value") or 0.4)

    routed: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for r in catalogue:
        row = dict(r)
        row["_category"] = route(row, cats)
        routed[row["_category"]] += 1
        rows.append(row)

    for c in cats:
        ok, bad = resolve_built(c, sources=srcs, lines=lines, root=root)
        c["_fetchers"], c["_not_working"] = ok, bad
        c["_state"] = category_state(c, ok)
        gain = next((gains[f["source_id"]] for f in ok
                     if f.get("source_id") in gains and gains[f["source_id"]] == "PASS"),
                    next((gains[f["source_id"]] for f in ok if f.get("source_id") in gains),
                         None))
        n = routed.get(str(c["id"]), 0) + (routed.get(f"terminal:{c.get('parent')}", 0)
                                            if c.get("parent") else 0)
        c["_score"] = score(c, values=values, default_value=dv, n_rows=n, gain=gain, may=may_fn)
        c["_rows"] = routed.get(str(c["id"]), 0)

    states = [row_state(r, by_id, grounds_by_row) for r in rows]
    table = []
    for c in cats:
        table.append({
            "id": c["id"], "label": c.get("label"), "kind": c.get("kind"),
            **({"parent": c["parent"]} if c.get("parent") else {}),
            "state": c["_state"], "roi": c["_score"]["roi"], "edge": c["_score"]["edge"],
            "edge_basis": c["_score"]["edge_basis"], "breadth": c["_score"]["breadth"],
            "instruments": c["_score"]["instruments_admitted"],
            "instruments_refused_by_universe_policy": c["_score"]["instruments_refused"],
            "paid_rows": c["_rows"], "fetchers": c["_fetchers"],
            "cited_not_working": c["_not_working"],
            "pending_branches": c.get("pending_branches") or [],
            "free_inputs": c.get("free_inputs") or [],
            "blocked_inputs": c.get("blocked_inputs") or [],
            **({k: c[k] for k in ("primary_source", "latency_gap", "gap") if c.get(k)})})
    table.sort(key=lambda t: (-float(t["roi"]), str(t["id"])))
    for i, t in enumerate(table, 1):
        t["rank"] = i
    parents = {}
    for pid, meta in (m.get("parents") or {}).items():
        funcs = [t for t in table if t.get("parent") == pid]
        parents[pid] = {"label": meta.get("label"), "roi": round(sum(t["roi"] for t in funcs), 4),
                        "functions": [t["id"] for t in funcs],
                        "built": [t["id"] for t in funcs if t["state"] == "BUILT"],
                        "unbuilt": [t["id"] for t in funcs if t["state"] != "BUILT"],
                        "paid_rows": routed.get(f"terminal:{pid}", 0)}
    unbuilt = [t for t in table if t["state"] == "QUEUED"]
    tasks = [{"id": t["id"], "rank": t["rank"], "roi": t["roi"], "label": t["label"],
              "instruments": t["instruments"],
              "inputs": [i for i in t["free_inputs"] if i.get("terms") != "refused"],
              "pending_branches": t["pending_branches"]}
             for t in unbuilt[:TOP_TASKS]]
    counts = Counter(s["state"] for s in states)
    n = len(states)
    doc = {
        "generated_at": _iso(now), "organ": "paid_replica_map",
        "owner_leg": "paid_substitute_engine",
        "map": str(map_path or MAP), "catalogue_rows": n,
        "row_states": {k: counts.get(k, 0) for k in STATES},
        "rows_without_state": n - sum(counts.get(k, 0) for k in STATES),
        "coverage_built_or_queued": round((counts["BUILT"] + counts["QUEUED"]) / n, 4)
        if n else UNMEASURED,
        "built_share": round(counts["BUILT"] / n, 4) if n else UNMEASURED,
        "coverage_rule": ("share of catalogue rows BUILT (a working free fetcher, cited) or "
                          "QUEUED (a build task emitted with named free inputs); BLOCKED needs a "
                          "host + clause + missed_growth. built_share is the stricter figure"),
        "categories": len(table), "ranked": table, "parents": parents,
        "build_tasks": tasks, "build_queue": str(queue or QUEUE),
        "measured_gains": gains or UNMEASURED,
        "rows": [{"id": r.get("id"), "vendor": r.get("vendor"), "dataset": r.get("dataset"),
                  "class": r.get("class"), **s} for r, s in zip(rows, states, strict=True)],
        "missed_growth": [{"category": t["id"], **b} for t in table
                          for b in t["blocked_inputs"]],
    }
    if write:
        _atomic(report or REPORT, doc)
        _atomic(queue or QUEUE, {
            "note": ("paid-replica BUILD TASKS: the top unbuilt categories' named free inputs as "
                     "search grounds. Written hourly by research/paid_replica_map.py under the "
                     "paid_substitute_engine leg; read by deep_forest_miner."),
            "generated_at": _iso(now), "grounds": build_grounds(tasks)})
    return doc


def summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    """The slice the engine's own coverage report carries."""
    return {k: doc.get(k) for k in ("catalogue_rows", "row_states", "rows_without_state",
                                    "coverage_built_or_queued", "built_share", "build_queue")} | {
        "top": [{k: t[k] for k in ("rank", "id", "state", "roi")} for t in
                (doc.get("ranked") or [])[:10]],
        "build_tasks": [t["id"] for t in doc.get("build_tasks") or []]}


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    os.replace(tmp, path)
