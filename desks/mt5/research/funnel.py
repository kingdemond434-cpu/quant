#!/usr/bin/env python3
"""THE END-TO-END FUNNEL -- raw info to live profit, every conversion, its depth, and its floor.

THE ORDER (principal, 2026-11-25): every conversion must be strong AND deep, not thin -- raw info
-> rows -> testable rows with real settings -> judged -> certified -> non-exotic -> promoted ->
fill-proven -> live -> live profit. Each organ already measures its own slice (the producer loop
the producer funnel, judge reach the handoff and its genuineness, live_yield the certificate's
road to a fill, conversion_funnel the registry-to-clock losses). Nothing put the WHOLE road side
by side, per producer, per asset class and per family, so nobody could say which conversion is
the thin one. This organ JOINS their outputs; it opens no new heavy scan and judges nothing.

THE STAGES, AND WHERE EACH COUNT COMES FROM

    RAW                   raw items a producer read: the compiler's intake rows per source
                          (miner_candidates.json `per_source[*].rows`) + the registry's
                          `discoveries` (PRODUCER_CONVERSION.json). No instrument exists yet, so
                          the class and family cuts read RAW as UNMEASURED by construction.
    ROWS                  hypothesis / candidate rows emitted: compiler `per_source[*].candidates`
                          + registry `candidates`; by class / family from the compiler's rows.
    TESTABLE              rows whose params are a REAL executable family spec
                          (research/family_spec.to_executable == EXECUTABLE). DEFAULTS_ONLY and
                          PROSE_ONLY rows are counted as WASTE, never as testable. Compiler rows
                          are read one by one; registry-lane rows are estimated from judge
                          reach's judged-row quality sample (basis says so). A row whose family
                          the spec cannot read is `quality_unmeasured`, outside the rate's
                          denominator -- neither testable nor waste.
    JUDGED                has a gate verdict: PRODUCER_CONVERSION `judged` (the verdict ledger by
                          exact cell identity); by class / family the judge's own seen-cell set
                          (data/hypotheses/gauntlet_seen_cells.json).
    CERTIFIED             data/certificate_provenance.json records in the canon.
    NON_EXOTIC_CERTIFIED  ... whose symbol research/universe_policy does not call exotic
                          (fail CLOSED: an unreadable policy calls every symbol exotic).
    FORWARD_CLOCKED       ... with a forward / shadow clock (reports/shadow/*_state.json).
    PROMOTED              ... with a promoter-written sleeve (data/sleeves.json LIVE / STANDBY).
    FILL_PROVEN           ... whose sleeve has a fill (data/fill_corpus.jsonl `filled_at`).
    LIVE                  ... whose sleeve is LIVE, non-exotic and fill-proven
                          (libs/research/live_yield.read_live_sleeves).
    LIVE_PROFIT           ... whose realised net E[log W] > 0 (live_yield.realised_elog).

From CERTIFIED on, each stage is a SUBSET of the one before (a strict chain over certificates,
joined on (symbol, family) as live_yield joins them), so every rate there is a true conversion.
Before CERTIFIED the stages come from different stores and a rate can exceed 1 (`exceeds_one`
flags it -- a fan-out, or a basis seam, never a silent cap).

DEPTH (declared, per cut): `testable_cells_per_family` = distinct testable cells / distinct
families with a testable cell; `breadth_units` per stage = independent units, not raw counts --
claim_selection.breadth_unit over rows at ROWS / TESTABLE, distinct (symbol, family) at JUDGED,
and k_eff (producer_loop.k_eff, the trial-ledger census) from CERTIFIED on.

WEAKEST STAGE per cut: the transition with the lowest rate relative to that transition's median
across the cut's dimension, among transitions with at least MIN_N in their source stage.

ATTACK ORDER (desk): every transition, floor violations first, then measured by rate ascending,
then UNMEASURED ones -- each with the organ that owns it and the remedy pointer.

FLOORS (data/funnel_floors.json): a count floor per stage and a rate floor per transition. A
measured value at or above its floor MEETS it and lifts the floor to RATCHET_SHARE of itself if
that is higher; below it is VIOLATED and the floor stays. Floors never fall (the writer merges
with the file on disk by max), and there are NO CEILINGS. UNMEASURED never moves a floor.

WHAT IT NEVER DOES. It moves no gate, DSR, FDR or trial count, writes no certificate, clock or
sleeve. An input it cannot read is UNMEASURED with the reason -- never zero (L1.28a).

    python desks/mt5/research/funnel.py --once [--budget-s 240] [--json]
Clock: hourly leg `funnel` (research/hourly_cycle.py). Artifact: desks/mt5/reports/FUNNEL.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import family_spec as FS  # noqa: E402
from research import producer_loop as PL  # noqa: E402

SEAT = "funnel"
OUT = DESK / "reports" / "FUNNEL.json"
FLOORS = DESK / "data" / "funnel_floors.json"
UNMEASURED = "UNMEASURED"
NO_INFLOW = "NO_INFLOW"
BUDGET_S = 240.0

STAGES = ("RAW", "ROWS", "TESTABLE", "JUDGED", "CERTIFIED", "NON_EXOTIC_CERTIFIED",
          "FORWARD_CLOCKED", "PROMOTED", "FILL_PROVEN", "LIVE", "LIVE_PROFIT")
TRANSITIONS = tuple(pairwise(STAGES))
CERT_STAGES = STAGES[4:]

#: A transition is ranked for a cut only when its source stage holds at least this many.
MIN_N = 20
#: A met floor rises to this share of the measured value (never above it: no ceiling, no
#: floor set at the noise edge of a single reading).
RATCHET_SHARE = 0.9
#: Sleeve statuses the promoter writes for a promoted row (LIVE, or admitted-but-unfunded).
PROMOTED_STATUSES = frozenset({"LIVE", "STANDBY"})
MAX_ROWS = 2_000_000
SHADOW_FILES = ("shadow_state.json", "external_shadow_state.json", "qquant_shadow_state.json",
                "scalp_shadow_state.json")

#: THE OWNER AND THE REMEDY POINTER of each transition (attack_order). Pointers only: this
#: module applies none of them.
OWNERS: dict[str, dict[str, str]] = {
    "RAW->ROWS": {
        "organ": "research/miner_candidate_compiler.py + research/cell_conversion_audit.py",
        "remedy": "cell_conversion_audit converts unwired rows through the compiler's door; "
                  "producer_loop FETCH_PARSE_FIX for a producer whose rows compile to nothing"},
    "ROWS->TESTABLE": {
        "organ": "research/family_spec.py + research/judge_reach.py",
        "remedy": "emit the family's own keywords (family_spec.ALIASES); judge_reach names "
                  "every DEFAULTS_ONLY / PROSE_ONLY producer"},
    "TESTABLE->JUDGED": {
        "organ": "research/judge_reach.py + the sealed judge's throughput",
        "remedy": "judge_reach LEAKING stage and reason; conversion_funnel UNKNOWN causes; "
                  "judging throughput (never a lower bar)"},
    "JUDGED->CERTIFIED": {
        "organ": "research/producer_loop.py (CERTIFY stage)",
        "remedy": "producer_loop remedy menu (GRID_WIDEN / GRID_NARROW / successors) on the "
                  "dominant kill class; the gates, DSR, FDR and the 597 never move"},
    "CERTIFIED->NON_EXOTIC_CERTIFIED": {
        "organ": "research/universe_policy.py + research/producer_loop.py",
        "remedy": "producer_loop INSTRUMENT_REMAP / NON_EXOTIC_REMAP successors"},
    "NON_EXOTIC_CERTIFIED->FORWARD_CLOCKED": {
        "organ": "research/forward_enrolment.py",
        "remedy": "conversion_funnel clock-stage losses; enrol every certificate on a clock"},
    "FORWARD_CLOCKED->PROMOTED": {
        "organ": "research/promoter.py",
        "remedy": "the promoter writes a matured certified clock LIVE on the same cycle"},
    "PROMOTED->FILL_PROVEN": {
        "organ": "the gateway + admission (research/shadow_admission.py, allocator)",
        "remedy": "admission scan and allocator fraction; a STANDBY row is the allocator's "
                  "zero, named in the sleeve's admission block"},
    "FILL_PROVEN->LIVE": {
        "organ": "research/promoter.py + admission",
        "remedy": "two admitting promoter readings for a STANDBY row (heavy admission scan)"},
    "LIVE->LIVE_PROFIT": {
        "organ": "research/decay_monitor.py + the allocator",
        "remedy": "decay verdicts and producer_loop yield weights steer compute to "
                  "producers whose live edges earn"},
}


def _key(a: str, b: str) -> str:
    return f"{a}->{b}"


# ------------------------------------------------------------------------------------ io helpers

def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=False, default=str)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _int(v: Any) -> int | None:
    return int(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def who(name: Any) -> str:
    """One producer key for every store: namespaces peeled (`miner:x` -> `x`), then normalised."""
    raw = str(name or "").strip()
    if not raw:
        return ""
    try:
        from libs.research.attribution import strip_namespace
        peeled = strip_namespace(raw)
        raw = peeled[-1] if peeled else raw
    except Exception:
        pass
    return PL._norm(raw)


@lru_cache(maxsize=4096)
def klass_of(symbol: str) -> str:
    return PL.asset_class(symbol) if symbol else "unclassified"


def iter_list(path: Path, key: str, *, deadline: float | None = None,
              max_rows: int = MAX_ROWS) -> Iterator[dict[str, Any]]:
    """The elements of the top-level list `key` in a large JSON document, decoded one at a
    time (the 70 MB compiler file is never held as one object tree). Stops at the deadline or
    `max_rows`; the caller learns it was cut from `iter_list.cut`."""
    iter_list.cut = False  # type: ignore[attr-defined]
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return
    i = text.find(f'"{key}":')
    if i < 0:
        return
    j = text.find("[", i)
    if j < 0:
        return
    dec = json.JSONDecoder()
    pos, n, ws = j + 1, 0, " \n\r\t,"
    while True:
        while pos < len(text) and text[pos] in ws:
            pos += 1
        if pos >= len(text) or text[pos] == "]":
            return
        try:
            obj, pos = dec.raw_decode(text, pos)
        except ValueError:
            return
        n += 1
        if isinstance(obj, dict):
            yield obj
        if n >= max_rows or (deadline is not None and n % 5000 == 0
                             and time.monotonic() > deadline):
            iter_list.cut = True  # type: ignore[attr-defined]
            return


def tail_keys(path: Path, keys: tuple[str, ...]) -> dict[str, Any] | None:
    """Top-level keys written after a large list (cell_conversion_audit._tail_keys's reading)."""
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return None
    dec = json.JSONDecoder()
    out: dict[str, Any] = {}
    for k in keys:
        i = text.rfind(f'"{k}":')
        if i < 0:
            continue
        j = i + len(k) + 3
        while j < len(text) and text[j] in " \n\r\t":
            j += 1
        try:
            out[k] = dec.raw_decode(text, j)[0]
        except ValueError:
            continue
    return out


# ------------------------------------------------------------------------------------ the inputs

@dataclass(frozen=True)
class Paths:
    conversion: Path
    loop: Path
    reach: Path
    compiler: Path
    seen: Path
    provenance: Path
    shadow_dir: Path
    sleeves: Path
    fills: Path
    source_registry: Path
    floors: Path
    out: Path
    lake: Path | None = None
    alt_exposure: Path | None = None

    @classmethod
    def at(cls, desk: Path) -> Paths:
        return cls(conversion=desk / "reports" / "PRODUCER_CONVERSION.json",
                   loop=desk / "reports" / "PRODUCER_LOOP.json",
                   reach=desk / "reports" / "JUDGE_REACH.json",
                   compiler=desk / "data" / "hypotheses" / "miner_candidates.json",
                   seen=desk / "data" / "hypotheses" / "gauntlet_seen_cells.json",
                   provenance=desk / "data" / "certificate_provenance.json",
                   shadow_dir=desk / "reports" / "shadow",
                   sleeves=desk / "data" / "sleeves.json",
                   fills=desk / "data" / "fill_corpus.jsonl",
                   source_registry=desk / "data" / "source_registry.json",
                   floors=desk / "data" / "funnel_floors.json",
                   out=desk / "reports" / "FUNNEL.json",
                   lake=desk / "data" / "lake" / "series",
                   alt_exposure=desk / "data" / "alt_catalog" / "exposure.json")


def _blank() -> dict[str, Any]:
    return dict.fromkeys(STAGES)


class Cut:
    """One row of the funnel: stage counts (None = UNMEASURED), their basis, waste and depth."""

    def __init__(self) -> None:
        self.n: dict[str, int | None] = _blank()
        self.basis: dict[str, list[str]] = {s: [] for s in STAGES}
        self.waste: dict[str, int] = {}
        self.quality_unmeasured = 0
        self.quality_measured_rows = 0
        self.testable_cells: set[tuple[str, str, str]] = set()
        self.units: dict[str, set[str]] = {"ROWS": set(), "TESTABLE": set(), "JUDGED": set()}
        self.cert_cells: dict[str, list[str]] = {s: [] for s in CERT_STAGES}

    def add(self, stage: str, n: int | None, basis: str) -> None:
        if n is None:
            return
        self.n[stage] = (self.n[stage] or 0) + int(n)
        if basis not in self.basis[stage]:
            self.basis[stage].append(basis)


def compiler_lane(paths: Paths, *, deadline: float | None) -> dict[str, Any]:
    """Per-source intake rows / candidates, and every compiled row's executable verdict."""
    tail = tail_keys(paths.compiler, ("per_source",))
    if tail is None:
        return {"available": False, "why": f"{UNMEASURED}: {paths.compiler.name} unreadable"}
    per = tail.get("per_source") if isinstance(tail.get("per_source"), dict) else {}
    rows = list(iter_list(paths.compiler, "hypotheses", deadline=deadline))
    return {"available": True, "per_source": per, "rows": rows,
            "partial": bool(getattr(iter_list, "cut", False))}


def row_quality(row: Mapping[str, Any]) -> str:
    prose = str(row.get("exact_rules") or row.get("rule") or row.get("mechanism_note") or "")
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    return str(FS.to_executable(str(row.get("family") or ""), params, prose=prose)["status"])


def breadth_unit(row: Mapping[str, Any]) -> str:
    try:
        from libs.research.claim_selection import breadth_unit as bu
        return bu(row)
    except Exception:
        params = json.dumps(row.get("params"), sort_keys=True, default=str)
        return f"{row.get('symbol')}|{row.get('family')}|{params}"


def read_clocks(shadow_dir: Path) -> dict[tuple[str, str], str] | None:
    """(symbol, family) -> KEPT / KILLED over every forward lane; None when the main clock
    file is unreadable."""
    from libs.research import live_yield as lv
    out: dict[tuple[str, str], str] = {}
    main = None
    for name in SHADOW_FILES:
        got = lv.read_forward(path=shadow_dir / name)
        if name == SHADOW_FILES[0]:
            main = got
        for k, v in (got or {}).items():
            if v == "KEPT" or k not in out:
                out[k] = v
    return None if main is None else out


def read_fills(path: Path) -> set[str] | None:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return None
    out: set[str] = set()
    for ln in lines:
        try:
            f = json.loads(ln) if ln.strip() else None
        except ValueError:
            continue
        if isinstance(f, dict) and f.get("filled_at"):
            out.add(str(f.get("sleeve") or f.get("strategy_id") or ""))
    return out


def cert_chain(paths: Paths, *, is_exotic: Callable[[str], bool] | None = None,
               trades_of: Callable[[str], list[dict[str, Any]]] | None = None
               ) -> dict[str, Any]:
    """Every certificate walked down CERTIFIED .. LIVE_PROFIT. Each stage is None (UNMEASURED)
    when its input is unreadable, and every later stage with it."""
    from libs.research import live_yield as lv
    ex = is_exotic or PL._is_exotic
    certs = lv.read_certificates(path=paths.provenance)
    clocks = read_clocks(paths.shadow_dir)
    sdoc = _read(paths.sleeves)
    srows = sdoc.get("sleeves") if isinstance(sdoc, dict) else sdoc
    sleeves = srows if isinstance(srows, list) else None
    fills = read_fills(paths.fills)
    live = (lv.read_live_sleeves(sdoc, None, fills_path=paths.fills, is_exotic=ex)
            if sleeves is not None and fills is not None else None)
    inputs = {"certificate_provenance": "READ" if certs is not None else UNMEASURED,
              "forward_clocks": "READ" if clocks is not None else UNMEASURED,
              "sleeves": "READ" if sleeves is not None else UNMEASURED,
              "fills": "READ" if fills is not None else UNMEASURED}
    promoted: dict[tuple[str, str], list[str]] = {}
    for r in sleeves or []:
        if isinstance(r, dict) and str(r.get("status") or "").upper() in PROMOTED_STATUSES:
            promoted.setdefault((str(r.get("symbol") or ""), str(r.get("family") or "")),
                                []).append(str(r.get("name") or ""))
    live_by: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for name, v in (live or {}).items():
        live_by.setdefault((v["symbol"], v["family"]), {})[name] = v
    out: list[dict[str, Any]] = []
    for rec in certs or []:
        if rec.get("in_canon") is False:
            continue
        cell = str(rec["cell"])
        sym, fam = lv.symbol_of(cell), lv.family_of(cell)
        st: dict[str, bool | None] = dict.fromkeys(CERT_STAGES)
        st["CERTIFIED"] = True
        st["NON_EXOTIC_CERTIFIED"] = not ex(sym)
        prev = st["NON_EXOTIC_CERTIFIED"]
        st["FORWARD_CLOCKED"] = (bool(prev and (sym, fam) in clocks)
                                 if clocks is not None else None)
        prev = st["FORWARD_CLOCKED"]
        st["PROMOTED"] = (bool(prev and (sym, fam) in promoted)
                          if prev is not None and sleeves is not None else None)
        prev = st["PROMOTED"]
        names = promoted.get((sym, fam), [])
        st["FILL_PROVEN"] = (bool(prev and any(n in (fills or set()) for n in names))
                             if prev is not None and fills is not None else None)
        prev = st["FILL_PROVEN"]
        mine = live_by.get((sym, fam), {})
        st["LIVE"] = (bool(prev and mine) if prev is not None and live is not None else None)
        if st["LIVE"] is None:
            st["LIVE_PROFIT"] = None
        elif not st["LIVE"]:
            st["LIVE_PROFIT"] = False
        else:
            el = lv.realised_elog(mine, half_life_d=lv.DEFAULT_HALF_LIFE_D, trades_of=trades_of)
            e = el.get("elog")
            st["LIVE_PROFIT"] = (bool(e > 0 and el.get("n_trades"))
                                 if isinstance(e, float) else None)
        out.append({"cell": cell, "producer": who(rec.get("producer")) or "unattributable",
                    "symbol": sym, "family": fam, "klass": klass_of(sym), "stages": st})
    return {"certs": out if certs is not None else None, "inputs": inputs}


# ------------------------------------------------------------------------------- the arithmetic

def transitions(n: Mapping[str, int | None], *, testable_den: int | None = None
                ) -> list[dict[str, Any]]:
    out = []
    for a, b in TRANSITIONS:
        na, nb = n.get(a), n.get(b)
        den = testable_den if (b == "TESTABLE" and testable_den is not None) else na
        rate: float | str = UNMEASURED
        if isinstance(den, int) and isinstance(nb, int):
            # Nothing reached the source stage: a measured starvation, not an unreadable input.
            rate = round(nb / den, 6) if den > 0 else NO_INFLOW
        out.append({"transition": _key(a, b), "n_from": na if na is not None else UNMEASURED,
                    "n_to": nb if nb is not None else UNMEASURED,
                    "denominator": den if den is not None else UNMEASURED, "rate": rate,
                    "exceeds_one": isinstance(rate, float) and rate > 1.0})
    return out


def medians(rows: list[dict[str, Any]], min_n: int = MIN_N) -> dict[str, float | None]:
    """Per transition, the median rate over the cuts with at least `min_n` in the denominator."""
    by: dict[str, list[float]] = {}
    for r in rows:
        for t in r["transitions"]:
            d = t["denominator"]
            if isinstance(t["rate"], float) and isinstance(d, int) and d >= min_n:
                by.setdefault(t["transition"], []).append(t["rate"])
    return {k: (median(v) if v else None) for k, v in by.items()}


def weakest(row: Mapping[str, Any], med: Mapping[str, float | None],
            min_n: int = MIN_N) -> dict[str, Any]:
    """The transition with the lowest rate relative to its median across the dimension."""
    best: tuple[float, int, dict[str, Any]] | None = None
    for i, t in enumerate(row["transitions"]):
        d, rate, m = t["denominator"], t["rate"], med.get(t["transition"])
        if not (isinstance(rate, float) and isinstance(d, int) and d >= min_n
                and m is not None):
            continue
        rel = rate / m if m > 0 else 1.0
        if best is None or (rel, i) < (best[0], best[1]):
            best = (rel, i, {"transition": t["transition"], "rate": rate,
                             "median": round(m, 6), "relative_to_median": round(rel, 6),
                             "n_from": d})
    if best is None:
        return {"status": "INSUFFICIENT_N", "min_n": min_n,
                "why": f"no transition has >= {min_n} in its source stage and a median"}
    return {"status": "MEASURED", **best[2]}


def k_eff(cells: list[str]) -> float:
    return round(PL.k_eff(cells), 4) if cells else 0.0


def finish(c: Cut, *, cert_measured: bool) -> dict[str, Any]:
    n = c.n
    q_den = c.quality_measured_rows if c.quality_measured_rows else None
    fams = {f for _, f, _ in c.testable_cells}
    units: dict[str, Any] = {s: (len(v) if (v or n.get(s) is not None) else UNMEASURED)
                             for s, v in c.units.items()}
    for s in CERT_STAGES:
        units[s] = k_eff(c.cert_cells[s]) if cert_measured and n.get(s) is not None \
            else UNMEASURED
    return {
        "stages": {s: (n[s] if n[s] is not None else UNMEASURED) for s in STAGES},
        "basis": {s: (c.basis[s] or [UNMEASURED]) for s in STAGES},
        "transitions": transitions(n, testable_den=q_den),
        "waste": {"defaults_only": c.waste.get(FS.DEFAULTS_ONLY, 0),
                  "prose_only": c.waste.get(FS.PROSE_ONLY, 0),
                  "other_not_executable": {k: v for k, v in sorted(c.waste.items())
                                           if k not in (FS.DEFAULTS_ONLY, FS.PROSE_ONLY)},
                  "quality_unmeasured": c.quality_unmeasured},
        "depth": {"testable_cells": len(c.testable_cells),
                  "families_with_testable": len(fams),
                  "testable_cells_per_family": (round(len(c.testable_cells) / len(fams), 3)
                                                if fams else UNMEASURED),
                  "breadth_units": units},
    }


# ------------------------------------------------------------------------------------ the floors

def read_floors(path: Path) -> dict[str, Any]:
    doc = _read(path)
    if not isinstance(doc, dict):
        doc = {}
    doc.setdefault("stages", {})
    doc.setdefault("transitions", {})
    return doc


def ratchet_one(floor: Any, value: Any, *, integer: bool) -> tuple[Any, str]:
    """(new floor, MET / VIOLATED / UNMEASURED). The floor never falls; no ceiling."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return floor, UNMEASURED
    f = floor if isinstance(floor, int | float) and not isinstance(floor, bool) else None
    if f is not None and value < f:
        return f, "VIOLATED"
    lifted = math.floor(value * RATCHET_SHARE) if integer else round(value * RATCHET_SHARE, 6)
    return (max(f, lifted) if f is not None else lifted), "MET"


def apply_floors(floors: Mapping[str, Any], desk: Mapping[str, Any],
                 now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """(new floors document, per-stage verdicts) for the desk row."""
    st_old = dict(floors.get("stages") or {})
    tr_old = dict(floors.get("transitions") or {})
    st_new: dict[str, Any] = {}
    tr_new: dict[str, Any] = {}
    verdicts: dict[str, Any] = {}
    for s in STAGES:
        old = (st_old.get(s) or {}).get("count_floor")
        new, v = ratchet_one(old, desk["stages"].get(s), integer=True)
        st_new[s] = {"count_floor": new,
                     "raised_at": (now.isoformat(timespec="seconds") if new != old
                                   else (st_old.get(s) or {}).get("raised_at"))}
        verdicts[s] = {"count": desk["stages"].get(s), "count_floor": old, "count_status": v}
    for t in desk["transitions"]:
        k = t["transition"]
        old = (tr_old.get(k) or {}).get("rate_floor")
        new, v = ratchet_one(old, t["rate"], integer=False)
        tr_new[k] = {"rate_floor": new,
                     "raised_at": (now.isoformat(timespec="seconds") if new != old
                                   else (tr_old.get(k) or {}).get("raised_at"))}
        verdicts[k] = {"rate": t["rate"], "rate_floor": old, "rate_status": v}
    doc = {"law": ("Per-stage count floors and per-transition rate floors of the end-to-end "
                   "funnel. A floor met lifts to RATCHET_SHARE of the measured value when that "
                   "is higher; it never falls, and there are no ceilings. Written by "
                   "research/funnel.py; never edited by hand downward."),
           "ratchet_share": RATCHET_SHARE, "updated_at": now.isoformat(timespec="seconds"),
           "stages": st_new, "transitions": tr_new}
    return doc, verdicts


def merge_up(disk: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    """The floors to write: every floor the max of the file on disk and the new reading, so no
    writer -- this one included -- can lower a floor."""
    out = dict(new)
    for block, field in (("stages", "count_floor"), ("transitions", "rate_floor")):
        merged = dict(new.get(block) or {})
        for k, v in (disk.get(block) or {}).items():
            old = (v or {}).get(field) if isinstance(v, dict) else None
            cur = (merged.get(k) or {}).get(field)
            if isinstance(old, int | float) and (not isinstance(cur, int | float) or old > cur):
                merged[k] = {**(merged.get(k) or {}), field: old,
                             "raised_at": (v or {}).get("raised_at")}
        out[block] = merged
    return out


# ------------------------------------------------------------------------------------- the build

def alt_block(paths: Paths, rows: list[Mapping[str, Any]] | None,
              seen: list[Any] | None) -> dict[str, Any]:
    """`by_alt_source`: per executable lake series, which generators were shown it, how many
    compiled rows carry it as an `alt:` conditioner, how many are testable, judged and certified;
    and the series and sources with no testable row (producer_loop's alt gap targets). Every
    count whose input is unreadable is UNMEASURED, never 0."""
    from research import alt_catalog as ac

    cat = ac.catalog(paths.lake or ac.LAKE)
    exposure = ac.read_exposure(paths.alt_exposure) if paths.alt_exposure \
        and paths.alt_exposure.exists() else None
    cov = ac.coverage(cat, rows if rows is not None else [],
                      judged={str(c) for c in seen} if seen is not None else None,
                      certified=ac.read_certified(paths.provenance), exposure=exposure)
    if rows is None:
        for e in cov["series"].values():
            e["rows"] = e["testable_rows"] = UNMEASURED
        cov["n_series_with_testable_rows"] = UNMEASURED
        cov["zero_coverage_series"] = cov["zero_coverage_sources"] = UNMEASURED
        cov["why_rows"] = f"{UNMEASURED}: compiler rows unreadable"
    if exposure is None:
        for e in cov["series"].values():
            e["generators_seeing"] = UNMEASURED
        cov["why_generators"] = (f"{UNMEASURED}: no exposure log yet (research/alt_catalog "
                                 "record_exposure writes it when a generator is shown a slice)")
    cov["refused_series"] = cat.get("refused") or {}
    return cov


def build(paths: Paths | None = None, *, now: datetime | None = None,
          budget_s: float | None = None, is_exotic: Callable[[str], bool] | None = None,
          trades_of: Callable[[str], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    paths = paths or Paths.at(DESK)
    now = now or _now()
    t0 = time.monotonic()
    budget = float(budget_s if budget_s is not None
                   else os.environ.get("QUANT_LEG_BUDGET_S") or BUDGET_S)
    deadline = t0 + budget * 0.8
    notes: list[str] = []

    conv_doc = _read(paths.conversion)
    conv = {who(r.get("producer")): r for r in (conv_doc or {}).get("producers") or []
            if isinstance(r, dict) and r.get("producer")} if isinstance(conv_doc, dict) else {}
    reach_doc = _read(paths.reach)
    reach = ({who(r.get("producer")): r for r in reach_doc.get("producers") or []
              if isinstance(r, dict) and r.get("producer")}
             if isinstance(reach_doc, dict) else {})
    loop_doc = _read(paths.loop)
    loop = ({who(r.get("producer")): r for r in loop_doc.get("producers") or []
             if isinstance(r, dict) and r.get("producer")} if isinstance(loop_doc, dict) else {})
    comp = compiler_lane(paths, deadline=deadline)
    seen_doc = _read(paths.seen)
    seen = list(seen_doc) if isinstance(seen_doc, dict | list) else None
    chain = cert_chain(paths, is_exotic=is_exotic, trades_of=trades_of)

    producers: dict[str, Cut] = {}
    classes: dict[str, Cut] = {}
    families: dict[str, Cut] = {}
    desk = Cut()

    def cut(table: dict[str, Cut], k: str) -> Cut:
        return table.setdefault(k or "unattributable", Cut())

    # ---- the compiler lane: RAW / ROWS per source, TESTABLE per row
    if comp.get("available"):
        for src, v in (comp.get("per_source") or {}).items():
            if not isinstance(v, dict):
                continue
            p = cut(producers, who(src))
            p.add("RAW", _int(v.get("rows")), "compiler:per_source.rows")
            p.add("ROWS", _int(v.get("candidates")), "compiler:per_source.candidates")
        for row in comp.get("rows") or []:
            name = who(PL.row_producer(row))
            sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
            q = row_quality(row)
            unit = breadth_unit(row)
            targets = (cut(producers, name), cut(classes, klass_of(sym)), cut(families, fam),
                       desk)
            for i, c in enumerate(targets):
                if i:          # producers take ROWS from per_source; the instrument cuts count rows
                    c.add("ROWS", 1, "compiler:rows")
                c.units["ROWS"].add(unit)
                if q == FS.EXECUTABLE:
                    c.add("TESTABLE", 1, "compiler:family_spec")
                    c.units["TESTABLE"].add(unit)
                    c.testable_cells.add((sym, fam, json.dumps(row.get("params"), sort_keys=True,
                                                               default=str)))
                    c.quality_measured_rows += 1
                elif q in (FS.DEFAULTS_ONLY, FS.PROSE_ONLY, FS.NO_SYMBOLS):
                    c.waste[q] = c.waste.get(q, 0) + 1
                    c.quality_measured_rows += 1
                    c.n["TESTABLE"] = c.n["TESTABLE"] or 0
                else:
                    c.quality_unmeasured += 1
        if comp.get("partial"):
            notes.append("compiler rows cut by the budget: ROWS/TESTABLE by class and family "
                         "are partial")
    else:
        notes.append(str(comp.get("why")))

    # ---- the registry lane: discoveries / candidates / judged per producer
    for name, r in conv.items():
        p = cut(producers, name)
        p.add("RAW", _int(r.get("discoveries")), "registry:discoveries")
        cand = _int(r.get("candidates"))
        p.add("ROWS", cand, "registry:candidates")
        p.add("JUDGED", _int(r.get("judged")), "registry:verdict_ledger_by_identity")
        q = (reach.get(name) or {}).get("judged_quality")
        if cand and isinstance(q, dict):
            ex_, d_, pr_ = (int(q.get(FS.EXECUTABLE) or 0), int(q.get(FS.DEFAULTS_ONLY) or 0),
                            int(q.get(FS.PROSE_ONLY) or 0))
            meas = ex_ + d_ + pr_
            if meas:
                est = round(cand * ex_ / meas)
                p.add("TESTABLE", est, "registry:estimated_from_judge_reach_sample")
                p.waste[FS.DEFAULTS_ONLY] = p.waste.get(FS.DEFAULTS_ONLY, 0) \
                    + round(cand * d_ / meas)
                p.waste[FS.PROSE_ONLY] = p.waste.get(FS.PROSE_ONLY, 0) + round(cand * pr_ / meas)
                p.quality_measured_rows += cand
    # The desk's RAW / ROWS are the producers' sums (both lanes); its TESTABLE / waste likewise.
    desk.n["RAW"] = desk.n["ROWS"] = None
    desk.basis["RAW"], desk.basis["ROWS"] = [], []
    desk.waste, desk.quality_measured_rows = {}, 0
    for p in producers.values():
        desk.add("RAW", p.n["RAW"], "sum:producers")
        desk.add("ROWS", p.n["ROWS"], "sum:producers")
        for k, v in p.waste.items():
            desk.waste[k] = desk.waste.get(k, 0) + v
        desk.quality_measured_rows += p.quality_measured_rows
    desk.n["TESTABLE"] = None
    desk.basis["TESTABLE"] = []
    for p in producers.values():
        desk.add("TESTABLE", p.n["TESTABLE"], "sum:producers")

    # ---- JUDGED by instrument (the judge's seen cells) and at the desk
    if seen is not None:
        for cell in seen:
            cell = str(cell)
            sym = cell.split(".", 1)[0].split("@", 1)[0]
            fam = PL.family_of(cell)
            for c in (cut(classes, klass_of(sym)), cut(families, fam)):
                c.add("JUDGED", 1, "judge:gauntlet_seen_cells")
                c.units["JUDGED"].add(f"{sym}|{fam}")
    tot = (conv_doc or {}).get("totals") if isinstance(conv_doc, dict) else None
    if isinstance(tot, dict) and _int(tot.get("judged")) is not None:
        desk.add("JUDGED", _int(tot.get("judged")), "registry:totals.judged")
    elif seen is not None:
        desk.add("JUDGED", len(seen), "judge:gauntlet_seen_cells")
        desk.units["JUDGED"] = {f"{str(c).split('.', 1)[0]}|{PL.family_of(str(c))}"
                                for c in seen}

    # ---- the certificate chain, CERTIFIED .. LIVE_PROFIT
    certs = chain["certs"]
    if certs is not None:
        # A None stage comes from an unreadable input, so it is UNMEASURED for every cut alike;
        # every other cert stage is a measured count (0 where nothing reached it).
        blind = {s for rec in certs for s in CERT_STAGES if rec["stages"][s] is None}
        for rec in certs:
            cut(producers, rec["producer"])
            cut(classes, rec["klass"])
            cut(families, rec["family"])
        for c in (*producers.values(), *classes.values(), *families.values(), desk):
            for s in CERT_STAGES:
                c.n[s] = None if s in blind else 0
                if s not in blind:
                    c.basis[s].append(f"chain:{s.lower()}")
        for rec in certs:
            targets = (producers[rec["producer"]], classes[rec["klass"]],
                       families[rec["family"]], desk)
            for s in CERT_STAGES:
                if s in blind or not rec["stages"][s]:
                    continue
                for c in targets:
                    c.n[s] = int(c.n[s] or 0) + 1
                    c.cert_cells[s].append(rec["cell"])
    else:
        notes.append(f"{UNMEASURED}: certificate_provenance unreadable; CERTIFIED onward")

    # A class or family the compiler / the judge never named is a MEASURED zero there once the
    # input was read (an equity class with no compiled row, a family the judge never saw).
    for c in (*classes.values(), *families.values()):
        for s, ok, basis in (("ROWS", comp.get("available"), "compiler:rows"),
                             ("TESTABLE", comp.get("available"), "compiler:family_spec"),
                             ("JUDGED", seen is not None, "judge:gauntlet_seen_cells")):
            if ok and c.n[s] is None:
                c.add(s, 0, basis)

    cert_ok = certs is not None
    rows_p = [{"producer": k, **finish(v, cert_measured=cert_ok)}
              for k, v in sorted(producers.items())]
    rows_c = [{"asset_class": k, **finish(v, cert_measured=cert_ok)}
              for k, v in sorted(classes.items())]
    rows_f = [{"family": k, **finish(v, cert_measured=cert_ok)}
              for k, v in sorted(families.items())]
    for r in (*rows_c, *rows_f):
        r["basis"]["RAW"] = [f"{UNMEASURED}: raw items carry no instrument"]
    for rows in (rows_p, rows_c, rows_f):
        med = medians(rows)
        for r in rows:
            r["weakest_stage"] = weakest(r, med)
    for r in rows_p:
        lp = loop.get(r["producer"]) or {}
        jr = reach.get(r["producer"]) or {}
        r["producer_loop"] = {"stage_of_death": lp.get("stage_of_death"),
                              "remedy": lp.get("remedy"),
                              "status": lp.get("status") or UNMEASURED}
        r["judge_reach"] = {"verdict": jr.get("verdict") or UNMEASURED,
                            "stage": jr.get("stage")}

    d = finish(desk, cert_measured=cert_ok)
    med_p = medians(rows_p)
    floors_old = read_floors(paths.floors)
    floors_new, verdicts = apply_floors(floors_old, d, now)
    attack: list[dict[str, Any]] = []
    for t in d["transitions"]:
        k = t["transition"]
        tv = verdicts.get(k) or {}
        cv = verdicts.get(k.split("->", 1)[1]) or {}
        violated = "VIOLATED" in (tv.get("rate_status"), cv.get("count_status"))
        attack.append({"transition": k, "rate": t["rate"], "n_from": t["n_from"],
                       "n_to": t["n_to"], "producer_median": med_p.get(k),
                       "floor_status": ("VIOLATED" if violated else
                                        tv.get("rate_status") or UNMEASURED),
                       "rate_floor": tv.get("rate_floor"),
                       "sample": ("OK" if isinstance(t["denominator"], int)
                                  and t["denominator"] >= MIN_N else "BELOW_MIN_N"),
                       **OWNERS[k]})
    # Floor violations first; then measured rates on at least MIN_N, weakest first; then
    # measured rates on a thinner sample; then NO_INFLOW (starved by an upstream stage); then
    # UNMEASURED. Within a group, the earlier stage first.
    def _group(a: dict[str, Any]) -> int:
        if a["floor_status"] == "VIOLATED":
            return 0
        if isinstance(a["rate"], float):
            return 1 if a["sample"] == "OK" else 2
        return 3 if a["rate"] == NO_INFLOW else 4

    attack.sort(key=lambda a: (_group(a), a["rate"] if isinstance(a["rate"], float) else 0.0,
                               TRANSITIONS.index(tuple(a["transition"].split("->")))))
    for i, a in enumerate(attack, 1):
        a["rank"] = i
    d["weakest_stage"] = ({"status": "MEASURED", **{k: attack[0][k] for k in
                                                    ("transition", "rate", "n_from")}}
                          if attack and isinstance(attack[0]["rate"], float)
                          else {"status": UNMEASURED})
    violated = sorted(k for k, v in verdicts.items()
                      if "VIOLATED" in (v.get("count_status"), v.get("rate_status")))
    try:
        by_alt = alt_block(paths, comp.get("rows") if comp.get("available") else None, seen)
    except Exception as exc:                       # a report section never costs the funnel
        by_alt = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:300]}
    src_reg = _read(paths.source_registry)
    src_rows = (src_reg or {}).get("sources") if isinstance(src_reg, dict) else None
    raw_sources = ({"n_sources": len(src_rows),
                    "n_leads": sum(int(_int((v or {}).get("n_leads")) or 0)
                                   for v in (src_rows.values() if isinstance(src_rows, dict)
                                             else src_rows))}
                   if isinstance(src_rows, dict | list) else UNMEASURED)
    return {
        "generated_utc": now.isoformat(timespec="seconds"), "organ": SEAT,
        "law": ("Every conversion from raw info to live profit is measured per producer, asset "
                "class and family, with its depth in independent units, the weakest stage "
                "named against the median and a ratcheting floor; DEFAULTS_ONLY and PROSE_ONLY "
                "rows are waste, never testable; an unreadable input is UNMEASURED, never 0."),
        "stages": list(STAGES),
        "stage_definitions": STAGE_DEFINITIONS,
        "depth_definition": DEPTH_DEFINITION,
        "inputs": {"producer_conversion": "READ" if conv else UNMEASURED,
                   "judge_reach": "READ" if reach else UNMEASURED,
                   "producer_loop": "READ" if loop else UNMEASURED,
                   "compiler": ("READ" if comp.get("available") else UNMEASURED)
                   + (" (partial)" if comp.get("partial") else ""),
                   "gauntlet_seen_cells": "READ" if seen is not None else UNMEASURED,
                   **chain["inputs"]},
        "desk": {**d, "floors": verdicts, "violated": violated, "attack_order": attack,
                 "raw_sources": raw_sources},
        "summary": {"n_producers": len(rows_p), "n_classes": len(rows_c),
                    "n_families": len(rows_f), "n_violated": len(violated),
                    "weakest_transition": d["weakest_stage"].get("transition"),
                    "live_profit": d["stages"]["LIVE_PROFIT"]},
        "producers": rows_p, "asset_classes": rows_c, "families": rows_f,
        "by_alt_source": by_alt,
        "notes": notes, "min_n": MIN_N,
        "budget_s": budget, "elapsed_s": round(time.monotonic() - t0, 2),
        "_floors": floors_new,
    }


STAGE_DEFINITIONS = {
    "RAW": "compiler intake rows per source + registry discoveries; UNMEASURED by class/family",
    "ROWS": "compiler candidates per source + registry candidates; compiler rows by instrument",
    "TESTABLE": "family_spec EXECUTABLE (compiler rows exact; registry lane estimated from the "
                "judge_reach judged-row sample); DEFAULTS_ONLY / PROSE_ONLY are waste",
    "JUDGED": "registry judged by exact cell identity; the judge's seen cells by instrument",
    "CERTIFIED": "certificate_provenance records in the canon",
    "NON_EXOTIC_CERTIFIED": "... not universe_policy.is_exotic_symbol (fail closed)",
    "FORWARD_CLOCKED": "... with a forward clock in reports/shadow/*_state.json",
    "PROMOTED": "... with a sleeves.json row LIVE or STANDBY (the promoter's output)",
    "FILL_PROVEN": "... whose sleeve has a fill_corpus row with filled_at",
    "LIVE": "... LIVE, non-exotic, fill-proven (live_yield.read_live_sleeves)",
    "LIVE_PROFIT": "... realised net E[log W] > 0 (live_yield.realised_elog)",
}
DEPTH_DEFINITION = ("testable_cells_per_family = distinct testable (symbol, family, params) / "
                    "families with one; breadth_units = claim_selection.breadth_unit at ROWS and "
                    "TESTABLE, distinct (symbol, family) at JUDGED, k_eff (trial-ledger census) "
                    "from CERTIFIED on")


def write(doc: dict[str, Any], paths: Paths | None = None) -> dict[str, Any]:
    paths = paths or Paths.at(DESK)
    floors = doc.pop("_floors", None)
    if isinstance(floors, dict):
        _atomic(paths.floors, merge_up(read_floors(paths.floors), floors))
    _atomic(paths.out, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = write(build(budget_s=a.budget_s))
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    st = doc["desk"]["stages"]
    print("funnel: " + " -> ".join(f"{s} {st[s]}" for s in STAGES))
    print(f"  weakest {doc['summary']['weakest_transition']}; violated "
          f"{doc['summary']['n_violated']}; {doc['elapsed_s']}s -> {OUT}")
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
