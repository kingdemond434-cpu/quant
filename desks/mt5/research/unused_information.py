"""THE UNUSED-INFORMATION MINER -- what does this desk already own that no strategy reads?

THE PRINCIPAL'S ORDER (2026-09-17, ledger M5 #8): ask continuously "what information in our
proprietary archive is not currently consumed by any strategy?" -- and treat every answer as
research inventory with a price on it, not as a curiosity.

WHY IT IS A SEPARATE ORGAN. The desk's other hunters look OUTWARD -- the world crawler for a claim
nobody has read, the deep forest for a trader's story, the frontier map for a cell nobody has
tested. Nothing looked INWARD at the archive the desk already paid for. Measured the day this
landed: the BIS policy tape carries 464,803 rows over 33 instruments and the carry family reads a
swap differential from somewhere else; the forced-flow calendar carries 1,085 events over eleven
kinds and no family's inputs name one of those kinds; the causal lab's surviving edges are
published and nothing consumes them. That is DEPTH THIS DESK ALREADY HAS at zero utilisation, and
the only reason it sat there is that nothing asked the question on a clock.

CONSUMPTION IS MEASURED, NEVER ASSUMED. An item is USED when one of three searches finds it, and
the searches are named in the artifact next to every verdict:

  1. DECLARED -- a family in `mt5desk.families_orthogonal.FAMILY_INPUTS` names it (the needs text
     or the path pattern), or it is one of `mt5desk.family_inputs.IDENTITY_KEYS`.
  2. TESTED   -- a cell in `data/hypothesis_graph.jsonl` that got past BORN carries it in its
     params, its region, its family or its source.
  3. LIVE     -- a LIVE sleeve in `data/sleeves.json` reads it, directly or through the declared
     inputs of the family it trades.

Anything the three miss is UNUSED **with the evidence of the search attached** -- the probe
tokens, the three corpora and their sizes. That matters more than the verdict: "unused" here
means "these tokens are absent from these three places", which is falsifiable, where "nobody
could think of a use" is not. A source this box does not hold is UNMEASURED BY NAME and scores
nothing (L1.28a, WS-005): an archive we cannot read is not an archive we have exhausted.

SEVEN REGISTERS, one per kind of thing that can go unconsumed:

    UNUSED_DATA            proprietary series from `reports/MOAT_SERIES.json`
    UNUSED_FEATURE         information axes from `reports/AXIS_REGISTRY.json`, plus the organs
                           `reports/WIRING_CEO.json` finds on no clock -- unwired machinery is
                           information nobody is reading either (LAWS III.16)
    UNUSED_STATE           exogenous state series from `data/axes/*.json`
    UNUSED_EVENT           event kinds from `data/forced_flow_calendar.json`
    UNUSED_RELATIONSHIP    edges from `reports/CAUSAL_LAB.json` / the world causal graph
    UNEXPLAINED_PNL        `reports/RESIDUAL_QUEUE.json` and `reports/STANDING_QUESTIONS.json`
    UNEXPLAINED_EXECUTION  `reports/EXECUTION_ALPHA.json` and `reports/markout.json`

THE PRICE. Every unused item gets a research priority:

    priority = (breadth of instruments x depth in days x moat score when known)
               x (1 + unexplained P&L it could touch) / (1 + cost to wire)

Breadth and depth are MEASURED from the artifact; the moat score comes from the series registry
when the item has one and is 1.0 when it does not (an unmeasured moat must not multiply an item
above a measured one). `cost to wire` is DECLARED per register below -- changing it re-prices
every row, so it is a decision, not a constant.

WHAT IT DOES WITH THEM. Every UNUSED item priced ABOVE THE MEDIAN becomes one DiscoveryObject in
the canonical registry (`source_type="unused_information"`, `origin="MOAT"`, state UNPROCESSED)
carrying {register, item, evidence, suggested_family_or_axis}, so the discovery compiler decides
what cells it owes. This organ donates NO cells and judges nothing: mining maximises the
opportunity set, the gauntlet owns truth.

    python desks/mt5/research/unused_information.py              # census, price, record
    python desks/mt5/research/unused_information.py --dry-run    # census and price, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DESK = _DESK
DATA, REPORTS = DESK / "data", DESK / "reports"
AXES_DIR = DATA / "axes"
MOAT_SERIES = REPORTS / "MOAT_SERIES.json"
AXIS_REGISTRY = REPORTS / "AXIS_REGISTRY.json"
FORCED_FLOW = DATA / "forced_flow_calendar.json"
CAUSAL_LAB = REPORTS / "CAUSAL_LAB.json"
CAUSAL_GRAPH = REPORTS / "WORLD_CAUSAL_GRAPH.json"
RESIDUAL_QUEUE = REPORTS / "RESIDUAL_QUEUE.json"
STANDING_QUESTIONS = REPORTS / "STANDING_QUESTIONS.json"
EXECUTION_ALPHA = REPORTS / "EXECUTION_ALPHA.json"
MARKOUT = REPORTS / "markout.json"
WIRING_CEO = REPORTS / "WIRING_CEO.json"
HYPOTHESIS_GRAPH = DATA / "hypothesis_graph.jsonl"
SLEEVES = DATA / "sleeves.json"
OUT = REPORTS / "UNUSED_INFORMATION.json"

REGISTERS: tuple[str, ...] = ("UNUSED_DATA", "UNUSED_FEATURE", "UNUSED_STATE", "UNUSED_EVENT",
                              "UNUSED_RELATIONSHIP", "UNEXPLAINED_PNL", "UNEXPLAINED_EXECUTION")

RULE = "anything measured and unconsumed is research inventory with a priority"

#: DECLARED, and re-pricing every row is the point of changing it. A state series already parsed
#: into `data/axes/` is nearly free to feed an existing family; a relationship needs a new family
#: or a new joint test; an unexplained P&L residual needs an explanation before it needs code.
COST_TO_WIRE: dict[str, float] = {
    "UNUSED_DATA": 3.0, "UNUSED_FEATURE": 2.0, "UNUSED_STATE": 1.0, "UNUSED_EVENT": 2.0,
    "UNUSED_RELATIONSHIP": 4.0, "UNEXPLAINED_PNL": 5.0, "UNEXPLAINED_EXECUTION": 5.0,
}
#: An axis file can be 81 MB (`bis.json` is, on this box, and the trading box has 8 GB). Below
#: this it is parsed; above it only the metadata every axis writer puts FIRST is read from the
#: head, and the rows are never materialised. Sizing a reader off the small file is how a fix
#: tested on the VPS breaks the box that trades.
AXIS_PARSE_MAX_BYTES = 8_000_000
AXIS_HEAD_BYTES = 262_144
#: The graph is ~18 MB / 35k rows here. Streamed, tokenised and dropped -- never held as objects.
GRAPH_MAX_ROWS = 400_000
#: A token shorter than this matches half the desk ("us", "at", "h1") and would read as consumed.
MIN_PROBE_LEN = 4
#: The axis registry's `instrument` axis is an INSTRUMENT list, not an information axis: every
#: value would read USED off the tested cells and drown the register in 300 true negatives.
SKIP_AXES: frozenset[str] = frozenset({"instrument"})
#: Desk-wide vocabulary that would make any probe match. A probe is meant to be the NAME of the
#: thing, not the shape of the path it happens to live in.
STOPWORDS: frozenset[str] = frozenset({
    "data", "json", "jsonl", "parquet", "reports", "desks", "mt5", "file", "path", "only",
    "price", "from", "with", "this", "each", "series", "rows", "value", "values", "name",
    "symbol", "symbols", "chart", "session", "unknown", "none", "true", "false", "http",
    "https", "www", "com", "org", "resolved", "whatever", "primitive", "named", "search",
    # Directory segments and filename placeholders. `tape` is the folder every proprietary
    # series lives in, so probing it would report the whole moat as consumed the moment ONE
    # family declares any path under it -- which is exactly what `liquidity_regime` does.
    "tape", "yyyy", "yyyymmdd", "freq", "peer", "univ", "universe", "intelligence",
})
_TOKEN = re.compile(r"[a-z0-9_]{2,}")


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _tokens(*parts: Any) -> set[str]:
    """CORPUS tokens: the whole token AND its underscore parts, so `data/tape/ticks/<SYM>` is
    found by `ticks` and by `tape`. Deliberately WIDE -- a corpus that is too narrow reports a
    consumed series as inventory, and this organ's whole value is that it does not."""
    out: set[str] = set()
    for p in parts:
        if p is None:
            continue
        for t in _TOKEN.findall(str(p).lower()):
            out.add(t)
            if "_" in t:
                out.update(x for x in t.split("_") if len(x) >= MIN_PROBE_LEN)
    return out


def _probes(*parts: Any) -> list[str]:
    """PROBE tokens: whole tokens only, no underscore split, no desk-wide vocabulary. `clock` is
    a family name and `clock_hour_01` is a standing question's feature -- splitting the second
    into the first is how an unexplained residual reads as consumed."""
    out: set[str] = set()
    for p in parts:
        if p is None:
            continue
        for t in _TOKEN.findall(str(p).lower()):
            if len(t) >= MIN_PROBE_LEN and t not in STOPWORDS and not t.isdigit():
                out.add(t)
    return sorted(out)


def _days_between(a: Any, b: Any) -> int | None:
    """Depth in days between two stamps written by two different organs' conventions."""
    def parse(v: Any) -> datetime | None:
        s = str(v or "").strip()
        if not s:
            return None
        s = s.replace("Z", "+00:00")
        for cut in (len(s), 19, 10, 7):
            try:
                d = datetime.fromisoformat(s[:cut])
            except ValueError:
                continue
            return d if d.tzinfo else d.replace(tzinfo=UTC)
        return None
    lo, hi = parse(a), parse(b)
    if lo is None or hi is None:
        return None
    return max(1, int(abs((hi - lo).days)))


def _axis_meta(path: Path) -> dict[str, Any]:
    """An axis file's declared metadata. Parsed when the file is small; read from its head when
    it is not, so an 81 MB policy tape costs 256 KB instead of a gigabyte of python objects."""
    try:
        size = path.stat().st_size
    except OSError:
        return {}
    if size <= AXIS_PARSE_MAX_BYTES:
        doc = _read_json(path)
        if isinstance(doc, dict):
            out = {k: doc[k] for k in ("axis", "id", "source", "at", "shape", "n_rows", "n_series",
                                       "n_symbols", "n_failed", "knowable_lag_days") if k in doc}
            out["symbols"] = [str(s) for s in (doc.get("symbols") or [])]
            out["series_names"] = sorted(doc["series"]) if isinstance(doc.get("series"),
                                                                     dict) else []
            rows = doc.get("rows")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                out["first_knowable_at"] = str(rows[0].get("knowable_at") or "")
            elif isinstance(doc.get("series"), dict):
                out["first_knowable_at"] = _first_point(doc["series"])
            return out
    try:
        with path.open("rb") as f:
            head = f.read(AXIS_HEAD_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return {}
    out = {}
    for key in ("axis", "id", "source", "at", "shape"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', head)
        if m:
            out[key] = m.group(1)
    for key in ("n_rows", "n_series", "n_symbols", "n_failed", "knowable_lag_days"):
        m = re.search(rf'"{key}"\s*:\s*(-?\d+)', head)
        if m:
            out[key] = int(m.group(1))
    m = re.search(r'"symbols"\s*:\s*\[([^\]]*)\]', head)
    out["symbols"] = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    out["series_names"] = []
    m = re.search(r'"knowable_at"\s*:\s*"([^"]*)"', head)
    if m:
        out["first_knowable_at"] = m.group(1)
    return out


def _first_point(series: dict[str, Any]) -> str:
    stamps = []
    for v in series.values():
        pts = v.get("points") if isinstance(v, dict) else None
        if isinstance(pts, list) and pts:
            first = pts[0]
            stamps.append(str(first[0] if isinstance(first, (list, tuple)) else
                              (first.get("date") or first.get("at") or "")
                              if isinstance(first, dict) else first))
    return min((s for s in stamps if s), default="")


# ------------------------------------------------------------------- what is being consumed --

class Consumption:
    """The three searches, their corpora and their sizes -- the evidence behind every verdict."""

    def __init__(self, declared: set[str], tested: set[str], live: set[str],
                 sizes: dict[str, Any]) -> None:
        self.corpora = {"declared": declared, "tested": tested, "live": live}
        self.sizes = sizes

    def searched(self) -> list[str]:
        return [f"{k} ({self.sizes.get(k)})" for k in ("declared", "tested", "live")]

    def find(self, probes: list[str]) -> list[dict[str, str]]:
        hits = []
        for probe in probes:
            p = probe.lower()
            if len(p) < MIN_PROBE_LEN:
                continue
            for where, corpus in self.corpora.items():
                if p in corpus:
                    hits.append({"probe": probe, "where": where})
                    break
        return hits


def _family_inputs() -> tuple[dict[str, Any], set[str]]:
    """FAMILY_INPUTS plus the identity keys, as a token corpus. Never the module source: a
    100k-line families file tokenised whole would report the entire archive as consumed."""
    try:
        from mt5desk.families_orthogonal import FAMILY_INPUTS
    except Exception:
        FAMILY_INPUTS = {}
    toks: set[str] = set()
    for fam, needs in dict(FAMILY_INPUTS).items():
        toks |= _tokens(fam)
        toks |= _tokens(*(needs if isinstance(needs, (list, tuple)) else (needs,)))
    try:
        from mt5desk.family_inputs import IDENTITY_KEYS
        toks |= _tokens(*IDENTITY_KEYS)
    except Exception:
        pass
    return dict(FAMILY_INPUTS), toks


def _graph_tokens(path: Path, deadline: float) -> tuple[set[str], int, int]:
    """Tokens of every cell that got past BORN. Streamed: the graph is 18 MB on this box."""
    toks: set[str] = set()
    rows = tested = 0
    if not path.exists():
        return toks, 0, 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                rows += 1
                if rows > GRAPH_MAX_ROWS or (rows % 2000 == 0 and time.monotonic() > deadline):
                    break
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("fate") or "BORN").upper() == "BORN" and not row.get("gates"):
                    continue
                tested += 1
                params = row.get("params") if isinstance(row.get("params"), dict) else {}
                toks |= _tokens(row.get("family"), row.get("symbol"), row.get("source"),
                                row.get("region"), *params.keys(), *params.values())
    except OSError:
        return toks, rows, tested
    return toks, rows, tested


def _live_tokens(path: Path, family_inputs: dict[str, Any]) -> tuple[set[str], int]:
    doc = _read_json(path)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    items = list(rows.values()) if isinstance(rows, dict) else list(rows or [])
    toks: set[str] = set()
    n = 0
    for s in items:
        if not isinstance(s, dict) or str(s.get("status") or "").upper() != "LIVE":
            continue
        n += 1
        toks |= _tokens(s.get("name"), s.get("symbol"), s.get("family"), s.get("timeframe"),
                        s.get("session"), s.get("exec"))
        needs = family_inputs.get(str(s.get("family") or ""))
        if needs is not None:
            toks |= _tokens(*(needs if isinstance(needs, (list, tuple)) else (needs,)))
    return toks, n


def consumption(*, deadline: float) -> tuple[Consumption, dict[str, Any]]:
    fam, declared = _family_inputs()
    tested_toks, rows, tested = _graph_tokens(HYPOTHESIS_GRAPH, deadline)
    live_toks, n_live = _live_tokens(SLEEVES, fam)
    sizes = {"declared": f"{len(fam)} families, {len(declared)} tokens",
             "tested": f"{tested} tested cells of {rows} graph rows",
             "live": f"{n_live} LIVE sleeves"}
    return Consumption(declared, tested_toks, live_toks, sizes), {"n_families": len(fam),
                                                                  "graph_rows": rows,
                                                                  "tested_cells": tested,
                                                                  "live_sleeves": n_live}


# ----------------------------------------------------------------------------- the census --

def _item(register: str, name: str, *, source: str, probes: list[str], breadth: int = 1,
          depth: int | None = None, moat: float | None = None, suggested: str = "",
          instruments: list[str] | None = None, detail: Any = None) -> dict[str, Any]:
    return {"register": register, "item": name, "source": source,
            "probes": sorted({p for p in probes if len(p) >= MIN_PROBE_LEN}),
            "breadth_instruments": max(1, int(breadth)), "depth_days": depth,
            "moat_score": moat, "instruments": sorted(set(instruments or []))[:40],
            "suggested_family_or_axis": suggested, "detail": detail}


def _census_series(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    doc = _read_json(MOAT_SERIES)
    if not isinstance(doc, dict) or not isinstance(doc.get("series"), list):
        unmeasured.append({"what": "UNUSED_DATA", "why": f"{MOAT_SERIES.name} absent or unreadable"
                                                         " -- the proprietary series registry has"
                                                         " not run on this box"})
        return []
    out = []
    for r in doc["series"]:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        name = str(r["name"])
        pattern = str(r.get("path_pattern") or "")
        out.append(_item("UNUSED_DATA", name, source="MOAT_SERIES.json",
                         probes=[name, *_probes(pattern)],
                         breadth=int(r.get("instruments") or 1),
                         depth=int(r["days"]) if isinstance(r.get("days"), int) else None,
                         moat=float(r["moat_score"]) if isinstance(
                             r.get("moat_score"), (int, float)) else None,
                         suggested=f"a FAMILY_INPUTS entry reading {pattern or name}",
                         detail={"kind": r.get("kind"), "moat_class": r.get("moat_class"),
                                 "owner": r.get("owner")}))
    return out


def _census_axes(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not AXES_DIR.is_dir():
        unmeasured.append({"what": "UNUSED_STATE",
                           "why": f"{AXES_DIR} absent -- no exogenous axis has been fetched here"})
        return []
    out = []
    for p in sorted(AXES_DIR.glob("*.json")):
        meta = _axis_meta(p)
        if not meta:
            unmeasured.append({"what": f"UNUSED_STATE:{p.stem}",
                               "why": f"{p.name} unreadable -- its depth scores nothing"})
            continue
        symbols = [str(s) for s in meta.get("symbols") or []]
        depth = _days_between(meta.get("first_knowable_at"), meta.get("at"))
        names = [str(s) for s in meta.get("series_names") or []] or [str(meta.get("id") or p.stem)]
        for series in names:
            out.append(_item("UNUSED_STATE", f"{p.stem}.{series}", source=f"data/axes/{p.name}",
                             probes=[series, *_probes(meta.get("id"), meta.get("axis"), p.stem)],
                             breadth=max(1, len(symbols) or int(meta.get("n_symbols") or 1)),
                             depth=depth, instruments=symbols,
                             suggested=f"a macro_conditional / cot_positioning axis on "
                                       f"data/axes/{p.name} ({meta.get('axis') or 'state'})",
                             detail={"n_rows": meta.get("n_rows"), "axis": meta.get("axis"),
                                     "knowable_lag_days": meta.get("knowable_lag_days"),
                                     "bytes": p.stat().st_size}))
    return out


def _census_axis_registry(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    doc = _read_json(AXIS_REGISTRY)
    axes = doc.get("axes") if isinstance(doc, dict) else None
    if not isinstance(axes, dict):
        unmeasured.append({"what": "UNUSED_FEATURE:axes",
                           "why": f"{AXIS_REGISTRY.name} absent or carries no axes block"})
        return []
    out = []
    for axis, values in axes.items():
        if axis in SKIP_AXES:
            continue
        seq = list(values) if isinstance(values, (dict, list)) else []
        for value in seq:
            v = str(value)
            if v.upper() == "UNKNOWN":
                continue
            n = int(values[value]) if isinstance(values, dict) and isinstance(
                values.get(value), int) else None
            out.append(_item("UNUSED_FEATURE", f"{axis}={v}", source="AXIS_REGISTRY.json",
                             probes=_probes(v) or [v],
                             breadth=1, depth=None,
                             suggested=f"a cell on the {axis} axis at {v}",
                             detail={"axis": axis, "n_cells": n}))
    return out


def _census_wiring(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    doc = _read_json(WIRING_CEO)
    rows = doc.get("unwired") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        unmeasured.append({"what": "UNUSED_FEATURE:organs",
                           "why": f"{WIRING_CEO.name} absent -- the wiring hunter has not run "
                                  "here, so unwired machinery is UNMEASURED, not zero"})
        return []
    out = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("organ"):
            continue
        organ = str(r["organ"])
        out.append(_item("UNUSED_FEATURE", f"organ:{organ}", source="WIRING_CEO.json",
                         probes=[Path(organ).stem],
                         breadth=1, depth=None,
                         suggested=str(r.get("suggested_clock") or "give it a clock and an "
                                                                   "artifact (LAWS III.16)"),
                         detail={"lines": r.get("lines"), "has_tests": r.get("has_tests")}))
    return out


def _census_events(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    doc = _read_json(FORCED_FLOW)
    events = doc.get("events") if isinstance(doc, dict) else None
    if not isinstance(events, list):
        unmeasured.append({"what": "UNUSED_EVENT",
                           "why": f"{FORCED_FLOW.name} absent or carries no events"})
        return []
    by_kind: dict[str, dict[str, Any]] = {}
    for e in events:
        if not isinstance(e, dict):
            continue
        kind = str(e.get("kind") or "unknown")
        slot = by_kind.setdefault(kind, {"n": 0, "instruments": set(), "first": None, "last": None,
                                         "names": set()})
        slot["n"] += 1
        slot["instruments"].update(str(s) for s in (e.get("instruments") or []))
        slot["names"].add(str(e.get("name") or "").rsplit("_", 1)[0])
        day = str(e.get("date") or "")
        if day and (slot["first"] is None or day < slot["first"]):
            slot["first"] = day
        if day and (slot["last"] is None or day > slot["last"]):
            slot["last"] = day
    out = []
    for kind, slot in sorted(by_kind.items()):
        out.append(_item("UNUSED_EVENT", kind, source="forced_flow_calendar.json",
                         probes=[kind, *_probes(*sorted(slot["names"])[:6])],
                         breadth=len(slot["instruments"]) or 1,
                         depth=_days_between(slot["first"], slot["last"]),
                         instruments=sorted(slot["instruments"]),
                         suggested=f"event_reaction / family_forced_flow on the {kind} window",
                         detail={"n_events": slot["n"], "first": slot["first"],
                                 "last": slot["last"],
                                 "file_declared_by": "FAMILY_INPUTS['forced_flow'] names the "
                                                     "calendar FILE; this kind is the question"}))
    return out


def _census_edges(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = 0
    for path, key in ((CAUSAL_LAB, "edges"), (CAUSAL_GRAPH, "admitted_edges")):
        doc = _read_json(path)
        rows = doc.get(key) if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            unmeasured.append({"what": f"UNUSED_RELATIONSHIP:{path.name}",
                               "why": f"{path.name} absent or carries no {key}"})
            continue
        seen += 1
        for e in rows:
            if not isinstance(e, dict):
                continue
            src, dst = str(e.get("from") or ""), str(e.get("to") or "")
            if not src or not dst:
                continue
            lag = e.get("lag")
            name = f"{src}->{dst}@lag{lag}"
            a, b = src.split(".")[-1].lower(), dst.split(".")[-1].lower()
            # The PAIR is the relationship. Probing the endpoints alone would read "USDJPY is
            # traded" as "this edge is consumed", which is how an unread graph looks used.
            out.append(_item("UNUSED_RELATIONSHIP", name, source=path.name,
                             probes=[f"{a}_{b}", f"{b}_{a}", src.lower(), dst.lower()],
                             breadth=2, depth=int(e["n"]) if isinstance(e.get("n"), int) else None,
                             instruments=[src.split(".")[-1], dst.split(".")[-1]],
                             suggested=f"lead_lag / cross_asset_residual driving "
                                       f"{dst.split('.')[-1]} off {src.split('.')[-1]}",
                             detail={"klass": e.get("klass"), "lag": lag, "q": e.get("q"),
                                     "r": e.get("r")}))
    if seen and not out:
        unmeasured.append({"what": "UNUSED_RELATIONSHIP",
                           "why": "the causal artifacts hold no admitted edge -- zero edges is a "
                                  "measurement, and it is not the same as an unread archive"})
    return out


def _census_unexplained_pnl(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    doc = _read_json(RESIDUAL_QUEUE)
    rows = doc.get("top") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        unmeasured.append({"what": "UNEXPLAINED_PNL:residual_queue",
                           "why": f"{RESIDUAL_QUEUE.name} absent -- residual P&L is UNMEASURED "
                                  "here, which is a verdict and not a clean book"})
    else:
        for r in rows:
            if not isinstance(r, dict):
                continue
            key = str(r.get("key") or r.get("name") or r.get("cell") or "")
            if not key:
                continue
            out.append(_item("UNEXPLAINED_PNL", key, source="RESIDUAL_QUEUE.json",
                             probes=[key, *_probes(r.get("key"), r.get("name"), r.get("cell"))],
                             breadth=1, depth=None,
                             instruments=[str(r.get("symbol") or "")] if r.get("symbol") else [],
                             suggested="a family or axis that explains the residual",
                             detail={k: r.get(k) for k in ("value", "n", "why") if k in r}))
    doc = _read_json(STANDING_QUESTIONS)
    questions = doc.get("questions") if isinstance(doc, dict) else None
    if not isinstance(questions, dict):
        unmeasured.append({"what": "UNEXPLAINED_PNL:standing_questions",
                           "why": f"{STANDING_QUESTIONS.name} absent or carries no questions"})
        return out
    no_family = {str(r.get("why") or "")[:80] for r in (doc.get("no_family") or [])
                 if isinstance(r, dict)}
    for qid, q in questions.items():
        if not isinstance(q, dict):
            continue
        for f in (q.get("findings") or [])[:40]:
            if not isinstance(f, dict):
                continue
            feature = str(f.get("feature") or f.get("what") or "")
            target = str(f.get("target") or f.get("symbol") or "")
            if not feature:
                continue
            out.append(_item("UNEXPLAINED_PNL", f"{qid}:{target}.{feature}",
                             source="STANDING_QUESTIONS.json",
                             probes=[feature, *_probes(feature)],
                             breadth=1, depth=int(f["n_bars"]) // 24 if isinstance(
                                 f.get("n_bars"), int) else None,
                             instruments=[target] if target else [],
                             suggested=str(f.get("proposed_family") or "")
                                       or f"no registered family reads {feature}",
                             detail={"lift": f.get("lift"), "p_perm": f.get("p_perm"),
                                     "category": f.get("category"),
                                     "no_family": any(feature in s for s in no_family)}))
    return out


def _census_execution(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    doc = _read_json(EXECUTION_ALPHA)
    if not isinstance(doc, dict):
        unmeasured.append({"what": "UNEXPLAINED_EXECUTION:execution_alpha",
                           "why": f"{EXECUTION_ALPHA.name} absent -- execution alpha is "
                                  "UNMEASURED, never zero"})
    else:
        for arm, v in (doc.get("arms") or doc.get("by_arm") or {}).items():
            out.append(_item("UNEXPLAINED_EXECUTION", f"arm:{arm}", source="EXECUTION_ALPHA.json",
                             probes=[str(arm), *_probes(arm)], breadth=1,
                             suggested="an execution_state family or an exec-arm A/B",
                             detail=v if isinstance(v, (int, float, str)) else None))
    doc = _read_json(MARKOUT)
    if not isinstance(doc, dict):
        unmeasured.append({"what": "UNEXPLAINED_EXECUTION:markout",
                           "why": f"{MARKOUT.name} absent -- post-fill markout is UNMEASURED"})
        return out
    if not doc.get("usable") or doc.get("edge_share") is None:
        out.append(_item("UNEXPLAINED_EXECUTION", "markout.edge_share", source="markout.json",
                         probes=["markout", "edge_share"], breadth=1,
                         suggested="match intents to deals, then an execution_state family",
                         detail={"why": str(doc.get("why") or "")[:200],
                                 "n_matched": doc.get("n_matched"),
                                 "n_unfilled_intents": doc.get("n_unfilled_intents")}))
    return out


def census(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Every source, read tolerantly; an absent one is named in `unmeasured` and scores nothing."""
    items: list[dict[str, Any]] = []
    items += _census_series(unmeasured)
    items += _census_axes(unmeasured)
    items += _census_axis_registry(unmeasured)
    items += _census_wiring(unmeasured)
    items += _census_events(unmeasured)
    items += _census_edges(unmeasured)
    items += _census_unexplained_pnl(unmeasured)
    items += _census_execution(unmeasured)
    return items


# ------------------------------------------------------------------------------ the price --

def price(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """priority = breadth x depth x moat x (1 + unexplained P&L it could touch) / (1 + cost).

    Depth and moat DEFAULT TO 1.0 when unmeasured, never to a flattering number: an item nobody
    has measured must not outrank one that has been.
    """
    residual_syms: dict[str, int] = {}
    for it in items:
        if it["register"] in ("UNEXPLAINED_PNL", "UNEXPLAINED_EXECUTION"):
            for s in it["instruments"]:
                residual_syms[s] = residual_syms.get(s, 0) + 1
    for it in items:
        breadth = float(max(1, it["breadth_instruments"]))
        depth = float(it["depth_days"]) if isinstance(it["depth_days"], (int, float)) else 1.0
        moat = float(it["moat_score"]) if isinstance(it["moat_score"], (int, float)) else 1.0
        touch = (sum(residual_syms.get(s, 0) for s in it["instruments"])
                 if it["register"] not in ("UNEXPLAINED_PNL", "UNEXPLAINED_EXECUTION") else 1)
        cost = COST_TO_WIRE.get(it["register"], 3.0)
        it["information_value"] = round(breadth * max(depth, 1.0) * max(moat, 0.0), 3)
        it["unexplained_touch"] = int(touch)
        it["cost_to_wire"] = cost
        it["priority"] = round(it["information_value"] * (1.0 + touch) / (1.0 + cost), 4)
    return items


def judge(items: list[dict[str, Any]], seen: Consumption) -> list[dict[str, Any]]:
    """USED when one of the three searches finds a probe; UNUSED with the search attached."""
    for it in items:
        hits = seen.find(it["probes"])
        it["used"] = bool(hits)
        it["evidence"] = {"searched": seen.searched(), "probes": it["probes"],
                          "matched": hits,
                          "why": ("consumed: " + ", ".join(f"{h['probe']}@{h['where']}"
                                                           for h in hits)) if hits else
                                 ("none of these probes appears in the declared family inputs, "
                                  "the tested cells or the live sleeves")}
    return items


def _median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float))) if values else 0.0


# -------------------------------------------------------------------------- the discoveries --

def record(items: list[dict[str, Any]], *, threshold: float) -> tuple[int, str | None]:
    """Every UNUSED item above the median becomes ONE DiscoveryObject, UNPROCESSED. No cells."""
    due = [it for it in items if not it["used"] and it["priority"] > threshold]
    if not due:
        return 0, None
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"
    n = 0
    try:
        conn = reg.connect()
        try:
            for it in due:
                did, _created = reg.record_discovery(
                    source_id=f"unused_information:{it['source']}",
                    source_type="unused_information", origin="MOAT",
                    generator="unused_information",
                    mechanism=f"{it['register']}: {it['item']} is measured and unconsumed",
                    information=it["register"],
                    economic_rationale=it["suggested_family_or_axis"][:300],
                    assets=it["instruments"], novelty=1.0,
                    falsifier="a family, axis or live sleeve that already reads it -- then the "
                              "census marks it USED and this discovery is closed",
                    payload={"register": it["register"], "item": it["item"],
                             "evidence": it["evidence"],
                             "suggested_family_or_axis": it["suggested_family_or_axis"],
                             "priority": it["priority"], "source": it["source"],
                             "breadth_instruments": it["breadth_instruments"],
                             "depth_days": it["depth_days"], "moat_score": it["moat_score"]},
                    conn=conn)
                it["discovery_id"] = did
                n += 1
        finally:
            conn.close()
    except Exception as exc:
        return n, f"{type(exc).__name__}: {exc}"
    return n, None


def write_report(report: dict[str, Any], out: Path) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only destination is legal
    on POSIX and WinError 5 here -- the way a VPS-tested fix once broke the box that trades."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    try:
        os.replace(tmp, out)
        return
    except PermissionError:
        try:
            os.chmod(out, 0o666)
            os.replace(tmp, out)
            return
        except OSError:
            pass
    except OSError:
        pass
    out.write_bytes(tmp.read_bytes())


def run(*, budget_s: float = 120.0, dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    unmeasured: list[dict[str, str]] = []
    seen, sizes = consumption(deadline=t0 + budget_s * 0.5)
    items = judge(price(census(unmeasured)), seen)
    unused = [it for it in items if not it["used"]]
    threshold = _median([it["priority"] for it in unused])
    recorded, err = (0, None) if dry_run else record(items, threshold=threshold)
    if err:
        unmeasured.append({"what": "discoveries", "why": f"registry unreachable: {err}"})
    registers = {name: sorted((it for it in items if it["register"] == name),
                              key=lambda r: -r["priority"]) for name in REGISTERS}
    top = sorted(unused, key=lambda r: -r["priority"])[:40]
    return {
        "at": now(), "registers": registers,
        "n_items": len(items), "n_used": len(items) - len(unused), "n_unused": len(unused),
        "by_register": {k: {"n": len(v), "unused": sum(1 for r in v if not r["used"])}
                        for k, v in registers.items()},
        "priority_median_unused": round(threshold, 4),
        "top_priorities": [{k: it[k] for k in ("register", "item", "priority", "source",
                                               "suggested_family_or_axis", "evidence")}
                           for it in top],
        "discoveries_recorded": recorded, "consumption": sizes,
        "cost_to_wire": COST_TO_WIRE, "unmeasured": unmeasured,
        "budget_s": budget_s, "dry_run": dry_run,
        "elapsed_s": round(time.monotonic() - t0, 2), "rule": RULE,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="census the archive nothing reads, and price it")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--dry-run", action="store_true", help="census and price, write nothing")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = run(budget_s=args.budget_s, dry_run=args.dry_run)
    for name in REGISTERS:
        row = rep["by_register"][name]
        print(f"  {name:<24}{row['n']:>6} item(s), {row['unused']:>6} UNUSED")
    print(f"\n{rep['n_items']} item(s): {rep['n_used']} used, {rep['n_unused']} unused, "
          f"median unused priority {rep['priority_median_unused']}, "
          f"{len(rep['unmeasured'])} unmeasured source(s), {rep['elapsed_s']}s")
    for it in rep["top_priorities"][:10]:
        print(f"    {it['priority']:>12.2f}  {it['register']:<22}{it['item'][:54]}")
    if args.dry_run:
        print("--dry-run: nothing recorded, nothing written")
        return 0
    write_report(rep, args.out or OUT)
    print(f"  -> {args.out or OUT}\nYIELD unused={rep['n_unused']} "
          f"discoveries={rep['discoveries_recorded']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
