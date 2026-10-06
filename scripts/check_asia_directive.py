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

THE REQUIREMENTS ARE DATA. `desks/mt5/data/asia_directive_requirements.json` holds one row per
requirement (the 55 rows of the 2026-10-06 diff report), each naming the RUNTIME artifacts that
would prove its state. Adding a requirement is a data edit; this file never hard-codes one.

CODE CAN ONLY GET A ROW TO SCHEDULED. The static rungs come from the tree: ABSENT (owner module or
its declared code marker missing), CODED (the module and marker exist), WIRED (another module
imports it), SCHEDULED (a clock names it: an hourly_cycle leg, a daily_cycle proposer, the organ
battery, the law gate). Every rung above that is read from what the organs WROTE: the pack chain
(PACK_CELLS.json), the alt-proxy vintage store and its gain tests (ALT_PROXIES.json), the free
stack (FREE_STACK_YIELD.json), the collector (ASIA_COLLECTOR.json), the runtime attestation
(docs/research/runtime_state.json), and the three before/after decision ledgers that prove a
feedback loop moved something (EVIG -> collection order, ROI -> forest budget, deep-forest
language rotation).

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
import contextlib
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
#: Where an importer of an owner module is looked for (WIRED). Bounded so the hourly pass is cheap.
WIRING_DIRS = ("desks/mt5/research", "desks/mt5/scripts", "desks/mt5/mt5desk", "libs", "scripts")
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

    def path(self, rel: str) -> Path:
        return self.root / rel

    def age_h(self, rel: str) -> float | None:
        try:
            return max(0.0, (self.now - self.path(rel).stat().st_mtime) / 3600.0)
        except OSError:
            return None

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
        p = self.path(rel)
        try:
            with p.open("rb") as fh:
                size = fh.seek(0, os.SEEK_END)
                fh.seek(max(0, size - nbytes))
                raw = fh.read()
        except OSError:
            return []
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if len(raw) >= nbytes and lines:
            lines = lines[1:]                       # the first line may be cut mid-row
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
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


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
        try:
            with p.open("rb") as fh:
                n = sum(1 for line in fh if line.strip())
        except OSError:
            return None
        return max(0, n - (1 if suffix == ".csv" else 0))
    doc = rd.json(rel)
    return _count(doc) if doc is not None else None


# ------------------------------------------------------------------------------ static rungs
def _wiring_corpus(rd: Reader) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for d in WIRING_DIRS:
        base = rd.path(d)
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if "tests" in p.parts:
                continue
            with contextlib.suppress(OSError):
                out.append((p.relative_to(rd.root).as_posix(), p.read_text("utf-8", "replace")))
    return out


def scheduler_found(rd: Reader, entry: str) -> bool:
    kind, _, name = entry.partition(":")
    rel = SCHEDULER_FILES.get(kind)
    src = rd.text(rel) if rel else None
    if not src or not name:
        return False
    if kind == "hourly":
        return (f'_costed("{name}"' in src) or (f"_costed('{name}'" in src)
    if kind in ("battery", "fence"):
        return Path(name).name in src
    return f'"{name}"' in src or f"'{name}'" in src


def static_rung(rd: Reader, row: dict[str, Any],
                corpus: list[tuple[str, str]]) -> tuple[str, list[str]]:
    why: list[str] = []
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
    sched = [str(s) for s in row.get("scheduler") or []]
    found = [s for s in sched if scheduler_found(rd, s)]
    if sched and len(found) == len(sched):
        return "SCHEDULED", [*why, f"clock(s): {', '.join(found)}"]
    if found:
        why.append(f"clock(s) found {found}, missing {sorted(set(sched) - set(found))}")
        return "SCHEDULED", why
    stems = {Path(o).stem for o in owners if rd.path(o).exists() and o.endswith(".py")}
    # An IMPORT or a path handed to a runner, never a mention in prose: a docstring naming a
    # module does not connect it to anything.
    importers = sorted({rel for rel, txt in corpus for s in stems
                        if rel not in owners and re.search(
                            rf"(^\s*from\s+[\w.]+\s+import\s+[^\n]*\b{re.escape(s)}\b)"
                            rf"|(^\s*(from|import)\s+[\w.]*\b{re.escape(s)}\b)"
                            rf"|([\w/]+/{re.escape(s)}\.py)",
                            txt, re.MULTILINE)})
    if importers:
        return "WIRED", [*why, f"imported by {', '.join(importers[:3])} but no declared clock "
                               f"runs it ({', '.join(sched) or 'none declared'})"]
    return "CODED", [*why, "code exists; nothing imports or schedules it"]


# ----------------------------------------------------------------------------------- probes
def _blank(rel: str, rd: Reader) -> dict[str, Any]:
    age = rd.age_h(rel)
    return {"artifact": rel, "present": age is not None,
            "age_h": round(age, 3) if age is not None else None,
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
    tested = ("PASS", "FAIL", "UNDERPOWERED")
    out["judged"] = sum(1 for k in keys if (gains[k] or {}).get("verdict") in tested)
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


def judge(rd: Reader, row: dict[str, Any], corpus: list[tuple[str, str]],
          runtime: dict[str, dict[str, Any]], now: datetime,
          proof_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rung, why = static_rung(rd, row, corpus)
    probes: list[dict[str, Any]] = []
    for p in row.get("probes") or []:
        kind = str(p.get("kind"))
        if kind == "proof":
            probes.append(probe_proof(rd, p, now, proof_cache))
        elif kind in PROBES:
            probes.append(PROBES[kind](rd, p))
    present = [p for p in probes if p["present"]]
    sched = [str(s) for s in row.get("scheduler") or []]
    legs = [s.split(":", 1)[1] for s in sched if s.startswith(("hourly:", "own_clock:"))]
    rt = {leg: runtime.get(f"leg:{leg}") for leg in legs}
    rt_live = [leg for leg, r in rt.items() if r and r.get("state") in ("LIVE", "STALE")]
    ok_runs = sorted(str(r.get("last_run_at")) for r in rt.values()
                     if r and r.get("last_run_outcome") == "ok" and r.get("last_run_at"))
    data = _sum(p["data"] for p in probes)
    cells = _sum(p["cells"] for p in probes)
    judged = _sum(p["judged"] for p in probes)
    survivors = _sum(p["survivors"] for p in probes)
    blocked = [p["blocked"] for p in probes if p["blocked"]]
    proofs = [p["proof"] for p in probes if p.get("proof")]
    horizon = HOURLY_STALE_H if any(s.startswith("hourly:") for s in sched) else OTHER_STALE_H
    ages = [p["age_h"] for p in present if p["age_h"] is not None]
    newest = min(ages) if ages else None
    freshness = (UNMEASURED if newest is None else ("FRESH" if newest <= horizon else "STALE"))

    reached = rung
    verify = row.get("verify") if isinstance(row.get("verify"), dict) else None
    verify_out: dict[str, Any] | None = None
    if RANK[rung] < RANK["SCHEDULED"]:
        state = rung
    elif not present and not rt_live:
        state = UNMEASURED
        why.append("no evidence artifact is present on this host: UNMEASURED, never a pass")
    else:
        reached = "RUNNING"
        if data:
            reached = "PRODUCING_DATA"
        if cells:
            reached = "PRODUCING_CELLS"
        if judged:
            reached = "JUDGED"
        if proofs and all(pr.get("verdict") == "PROVEN" for pr in proofs):
            reached = "PROVEN"
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
    last_ok = ok_runs[-1] if ok_runs else None
    if last_ok is None and newest is not None:
        last_ok = (datetime.fromtimestamp(rd.now, tz=UTC)
                   - timedelta(hours=newest)).isoformat(timespec="seconds")
        last_basis = "newest evidence artifact mtime"
    else:
        last_basis = "runtime_state last_run_at (outcome ok)" if last_ok else UNMEASURED
    return {
        "id": row["id"], "report_row": row.get("report_row"), "title": row.get("title"),
        "parts": row.get("parts") or [], "xliv": bool(row.get("xliv")),
        "region": row.get("region"), "package": row.get("package") or "",
        "state": state, "rung_reached": reached, "static_rung": rung,
        "baseline_2026_10_06": row.get("baseline"),
        "proxy": bool(row.get("proxy")),
        "owner": row.get("owner") or [], "scheduler": sched,
        "input_artifacts": row.get("inputs") or [], "output_artifacts": row.get("outputs") or [],
        "freshness": {"status": freshness, "newest_age_h": round(newest, 3) if newest is not None
                      else None, "horizon_h": horizon},
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
        if not r.get("probes"):
            errors.append(f"{rid}: names no evidence artifact (probes)")
        for p in r.get("probes") or []:
            k = str(p.get("kind"))
            if k not in PROBES and k != "proof":
                errors.append(f"{rid}: unknown probe kind {k!r}")
            if not p.get("artifact"):
                errors.append(f"{rid}: a probe names no artifact")
            if k == "proof" and p.get("proof") not in PROOFS:
                errors.append(f"{rid}: unknown proof {p.get('proof')!r}")
        for s in r.get("scheduler") or []:
            if str(s).partition(":")[0] not in SCHEDULER_FILES:
                errors.append(f"{rid}: scheduler {s!r} names no known clock kind")
    if not rows:
        errors.append("no requirements")
    return rows, errors


def summary_lines(doc: dict[str, Any]) -> list[str]:
    c = doc.get("census") or {}
    lines = [f"ASIA DIRECTIVE COMPLETION AUDIT {doc.get('at')} on {doc.get('host')}: "
             f"{doc.get('n_items')} requirements -- "
             + ", ".join(f"{s} {c[s]}" for s in LADDER if c.get(s))]
    proofs = doc.get("proofs") or {}
    lines.append("XLIV proofs: " + ", ".join(f"{k}={v.get('verdict')}"
                                             for k, v in sorted(proofs.items())))
    xl = [i for i in doc.get("items") or [] if i.get("xliv")]
    lines.append("XLIV items: " + ", ".join(f"{i['id']} {i['state']}" for i in xl))
    um = [i["id"] for i in doc.get("items") or [] if i.get("state") == UNMEASURED]
    if um:
        lines.append(f"UNMEASURED on this host ({len(um)}): {', '.join(um)} -- read them on the box")
    return lines


def audit(root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    nowdt = now or datetime.now(tz=UTC)
    rd = Reader(root, nowdt.timestamp())
    reqs, errors = load_requirements(rd)
    corpus = _wiring_corpus(rd)
    runtime, rt_meta = _runtime_rows(rd)
    cache: dict[str, dict[str, Any]] = {}
    items = [judge(rd, r, corpus, runtime, nowdt, cache) for r in reqs]
    census = Counter(i["state"] for i in items)
    by_region: dict[str, dict[str, Any]] = {}
    for i in items:
        reg = by_region.setdefault(str(i.get("region") or "?"),
                                   {"items": 0, "states": Counter(), "observations": None,
                                    "cells_emitted": None, "cells_judged": None,
                                    "survivors": None})
        reg["items"] += 1
        reg["states"][i["state"]] += 1
        for k in ("observations", "cells_emitted", "cells_judged", "survivors"):
            v = i[k]
            if isinstance(v, int):
                reg[k] = (reg[k] or 0) + v
    for reg in by_region.values():
        reg["states"] = dict(reg["states"])
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
        "by_region": by_region,
        "by_package": by_package,
        "proofs": cache,
        "asia_sources": asia_sources(rd),
        "items": items,
        "rule": ("code lifts a row at most to SCHEDULED; every higher rung is read from a runtime "
                 "artifact; an absent artifact is UNMEASURED; a failed XLIV verification holds a "
                 "row at RUNNING; forward/live per requirement are UNMEASURED until lineage from "
                 "a source to a clock is published"),
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
    a = ap.parse_args(argv)
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
