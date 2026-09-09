#!/usr/bin/env python3
"""THE PORTFOLIO GAP -- every unfilled point of heat becomes a research request.

    "Make every unused percentage point generate a research emergency ... the purpose of
     research becomes: make high-quality 20% utilisation possible in more states of the world."
                                                            -- the principal, 2026-09-02

WHAT THIS IS FOR. `pf_allocator.py` answers "what should the book be". This answers the question
that follows: WHERE THE LIBRARY IS EMPTY. A heat gap that says "4% unfilled" is a number nobody
can act on; one that says "4% unfilled, and the desk owns nothing that trades the 00-04 UTC band
outside JPY" is a search. The gap is the bridge between the allocator and the hunt: the allocator
discovers what it cannot fund, and the hunt goes and finds it.

NOTHING IS ENUMERATED HERE. The mechanism axis is READ OUT OF THE CERTIFICATES -- every family
name that has ever cleared the ten gates appears, and one that appears tomorrow appears
tomorrow. There is no list of families in this file and there must never be one: a hardcoded axis
turns "we have not looked there" into "that cell does not exist", which is the failure mode this
whole artifact exists to prevent. The session axis is likewise read from the windows the desk
actually trades.

WHAT IT IS NOT. Not a gate, not a promoter, not a sizer. It writes `reports/portfolio_gap.json`
and ranks cells. Nothing here can admit or reject a candidate.

THE GAP BECOMES A MISSION (acceptance property AP4, "the portfolio creates research missions";
audit P17, 2026-09-08). `research_requests` named the gap and `pf_allocator`'s `opportunity`
block named the unfunded heat by session and family, and neither reached the organ that does
research: the deepening queue. `missions` turns them into queue rows of kind "mission" -- each
with a stable `mission_id`, the exposure that is missing (session / family / state), the heat
gap, and the allocator's own opportunity reading -- written through the same shared writer
alpha_breadth uses, under source `portfolio_gap`. `reports/RESEARCH_MISSIONS.json` lists the
open missions and every candidate that carries a `mission_id` back to one.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "portfolio_gap.json"
ALLOC = BASE / "reports" / "pf_allocation.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
MISSIONS_OUT = BASE / "reports" / "RESEARCH_MISSIONS.json"
#: Where a candidate born from a mission would carry its `mission_id`: the deepening worker's
#: recovered candidates and the miner compiler's store. Read for the report, never written.
CANDIDATE_STORES = (BASE / "data" / "hypotheses" / "deepened_candidates.json",
                    BASE / "data" / "hypotheses" / "miner_candidates.json")
#: Empty cells are numerous and cheap to name; the queue is worked in VOI order, so the first
#: dozen (already ranked by band then family) are missions and the rest stay requests.
MAX_EMPTY_CELL_MISSIONS = 12

#: UTC hour bands. Coarse on purpose: the desk's sleeves are session-bracketed, so a finer grid
#: would report structure the evidence cannot support.
BANDS = ((0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24))

#: Signal hour per known window, read from the gateway when it can be imported. This is the ONLY
#: place a window name is turned into a clock, and it defers to the gateway's own definition.
_FALLBACK_WINDOW_HOUR = {"asia": 7, "london_am": 13, "afternoon": 17, "ny_open": 20}


def window_hours() -> dict[str, int]:
    """Window -> signal hour, from the gateway if importable, else the last known mapping."""
    try:
        from mt5desk.gateway import GOLD_WINDOWS
        got = {str(w[0]): int(w[1]) for w in GOLD_WINDOWS}
        return {**_FALLBACK_WINDOW_HOUR, **got}
    except Exception:
        return dict(_FALLBACK_WINDOW_HOUR)


def band_of(hour: int) -> str:
    for lo, hi in BANDS:
        if lo <= hour < hi:
            return f"{lo:02d}-{hi:02d}"
    return "??"


def parse_cell(cell: str) -> dict[str, str]:
    """Split a survivor cell into its axes WITHOUT assuming a fixed shape.

    Two shapes exist in the live ledger and more have existed:
        `AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY`   (hunt cells)
        `XAUUSD.session_range_breakout`                            (external discoveries)

    Tokens are therefore CLASSIFIED rather than positioned -- a side is LONG/SHORT, a state ends
    in _DAY, a window is one the desk trades, the symbol is the first token, and whatever is left
    is the mechanism. A hunt inventing a new token order is parsed, not dropped.
    """
    raw = str(cell).strip()
    if not raw:
        return {}
    toks = raw.split()
    if len(toks) == 1 and "." in toks[0]:
        sym, _, fam = toks[0].partition(".")
        return {"symbol": sym, "side": "", "window": "", "state": "",
                "family": fam or "unspecified"}
    wins = set(window_hours())
    out = {"symbol": toks[0], "side": "", "window": "", "state": "", "family": ""}
    rest: list[str] = []
    for t in toks[1:]:
        if t in ("LONG", "SHORT") and not out["side"]:
            out["side"] = t
        elif t in wins and not out["window"]:
            out["window"] = t
        elif t.endswith("_DAY") and not out["state"]:
            out["state"] = t
        else:
            rest.append(t)
    out["family"] = "_".join(rest) if rest else "unspecified"
    return out


def load_survivors() -> list[dict[str, Any]]:
    """Every universal 10-gate survivor, as parsed axes. UNMEASURED, never zero, on absence.

    `shadow_spec` WINS OVER THE CELL STRING when a row carries one. The external-discovery rows
    carry `{symbol, selector, family, condition}` -- the spec the forward engine actually enrols
    -- while their cell collapses all of it into `SYMBOL.family`. Measured 2026-09-02: parsing
    the cell alone put 62 of 63 certificates into an unspecified family with no window, so the
    coverage matrix showed ONE certificate and read like a desk that had certified almost
    nothing. Reading the spec recovers the real axes.
    """
    if not SURVIVORS.exists():
        return []
    try:
        doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("survivors") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = list(rows.values())
    out: list[dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        axes = parse_cell(str(r.get("cell") or ""))
        spec = r.get("shadow_spec")
        if isinstance(spec, dict):
            axes = {
                "symbol": str(spec.get("symbol") or axes.get("symbol") or "?"),
                "window": str(spec.get("selector") or axes.get("window") or ""),
                "family": str(spec.get("family") or axes.get("family") or "unspecified"),
                "state": str(spec.get("condition") or axes.get("state") or ""),
                "side": axes.get("side", ""),
            }
        if not axes:
            continue
        axes["hunt"] = str(r.get("hunt") or "")
        axes["days"] = str(r.get("days") or "")
        out.append(axes)
    return out


def sleeve_axes(name: str) -> dict[str, str]:
    """Axes for an allocator book entry, whose names are `symbol_window_state` or `gold_window`."""
    if name.startswith("gold_"):
        return {"symbol": "XAUUSD", "window": name[len("gold_"):], "state": "",
                "family": "session_bracket", "side": ""}
    m = re.match(r"^([A-Za-z0-9]+)_(.+?)_([A-Z]+_DAY)$", name)
    if m:
        return {"symbol": m.group(1), "window": m.group(2), "state": m.group(3),
                "family": "session_bracket", "side": ""}
    parts = name.split("_")
    return {"symbol": parts[0], "window": parts[-1] if len(parts) > 1 else "",
            "state": "", "family": "_".join(parts[1:-1]) or "unspecified", "side": ""}


def build(alloc: dict[str, Any], survivors: list[dict[str, Any]]) -> dict[str, Any]:
    """The coverage matrix, the gap, and the ranked research requests."""
    hours = window_hours()
    book = {str(k): float(v) for k, v in (alloc.get("book") or {}).items()}
    marginal = {str(k): float(v) for k, v in (alloc.get("marginal_delta_elog") or {}).items()}
    heat = alloc.get("heat") or {}
    target = float(heat.get("target") or 0.0)
    held = float(heat.get("total") or 0.0)

    cells: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"certificates": 0, "funded_sleeves": 0, "funded_heat": 0.0,
                 "positive_marginal": 0.0, "symbols": set(), "windows": set()})

    for s in survivors:
        band = band_of(hours.get(s.get("window", ""), -1))
        c = cells[(band, s.get("family") or "unspecified")]
        c["certificates"] += 1
        c["symbols"].add(s.get("symbol", "?"))
        c["windows"].add(s.get("window", "?"))

    for name, h in book.items():
        ax = sleeve_axes(name)
        band = band_of(hours.get(ax["window"], -1))
        c = cells[(band, ax["family"])]
        c["funded_sleeves"] += 1
        c["funded_heat"] += h
        c["windows"].add(ax["window"])
        c["symbols"].add(ax["symbol"])
    for name, mv in marginal.items():
        if mv <= 0:
            continue
        ax = sleeve_axes(name)
        cells[(band_of(hours.get(ax["window"], -1)), ax["family"])]["positive_marginal"] += mv

    bands = [f"{lo:02d}-{hi:02d}" for lo, hi in BANDS]
    # "??" IS A REAL ROW, NOT A DROPPED ONE. A certificate whose window the desk cannot place on
    # a clock is unschedulable evidence, and letting it fall out of the matrix would report a
    # library smaller than the one that exists -- the same silent zero this file exists to catch.
    if any(b == "??" for b, _f in cells):
        bands = [*bands, "??"]
    families = sorted({f for _b, f in cells})
    matrix = [
        {"band": b, "family": f,
         **{k: (sorted(v) if isinstance(v, set) else round(v, 6) if isinstance(v, float) else v)
            for k, v in cells[(b, f)].items()}}
        for b in bands for f in families if (b, f) in cells
    ]

    # EMPTY CELLS ARE THE POINT. A band/family the desk has never certified anything in is not a
    # zero to be reported once -- it is the search target that would let the heat target be
    # filled in a state of the world it currently cannot be.
    real = [b for b in bands if b != "??"]
    empty = [{"band": b, "family": f} for b in real for f in families if (b, f) not in cells]
    dark_bands = [b for b in real
                  if not any(cells[(b, f)]["funded_heat"] > 0 for f in families if (b, f) in cells)]
    unplaced = sum(int(v["certificates"]) for (b, _f), v in cells.items() if b == "??")

    gap = max(target - held, 0.0)
    requests: list[dict[str, Any]] = []
    if gap > 1e-9:
        requests.append({
            "kind": "heat_gap", "priority": 1,
            "detail": f"{gap:.2%} of the {target:.0%} heat target is unfunded by the current "
                      f"library at its per-sleeve bounds",
        })
    for b in dark_bands:
        requests.append({
            "kind": "dark_band", "priority": 2, "band": b,
            "detail": f"no funded sleeve trades the {b} UTC band -- the book is flat there "
                      f"whatever the opportunity set offers",
        })
    if unplaced:
        requests.append({
            "kind": "unplaced_certificates", "priority": 2, "count": str(unplaced),
            "detail": f"{unplaced} certificate(s) carry a window this desk cannot place on a "
                      f"clock, so they can be neither scheduled nor counted toward coverage",
        })
    for e in empty[:40]:
        requests.append({
            "kind": "empty_cell", "priority": 3, **e,
            "detail": f"no certificate has ever come from {e['family']} in the {e['band']} "
                      f"UTC band",
        })

    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "target_heat": target, "held_heat": held, "heat_gap": round(gap, 6),
        "bands": bands, "families": families,
        "n_certificates": len(survivors), "n_funded": len(book),
        "certificates_unplaced_on_a_clock": unplaced,
        "matrix": matrix,
        "dark_bands": dark_bands,
        "empty_cells": empty,
        "research_requests": requests,
        "note": ("Mechanism axis is read from the certificates, never enumerated here: a family "
                 "that clears the gates tomorrow appears in this matrix tomorrow."),
    }


def mission_id(kind: str, session: str = "any", family: str = "any") -> str:
    """Stable across reruns and readable: the queue worker keys a task on its title and bills it
    once, and a candidate is tagged with this id, so it must not carry a timestamp or a hash."""
    return f"mission:{kind}:{session or 'any'}:{family or 'any'}"


def missions(doc: dict[str, Any], alloc: dict[str, Any],
             now: datetime | None = None) -> list[dict[str, Any]]:
    """The queue rows: one per heat gap, per dark band, per (capped) empty cell.

    Every mission carries the SAME allocator reading (`opportunity`: positive marginal dE[log W]
    by session and by family, opportunity density, the allocator's own gap sentence) so the
    crawler working any one of them can see where the library already has unfunded opportunity
    and where it has none -- a gap that says "4% unfilled" is a number, one that says "4%
    unfilled, nothing positive in the 00-04 band, most of it in overnight_gap_decay" is a search.
    """
    at = (now or datetime.now(UTC)).isoformat()
    gap = float(doc.get("heat_gap") or 0.0)
    opp = alloc.get("opportunity") if isinstance(alloc.get("opportunity"), dict) else {}
    by_session = dict(opp.get("positive_marginal_by_session") or {})
    by_family = dict(opp.get("positive_marginal_by_family") or {})
    context = {
        "opportunity_density": opp.get("opportunity_density"),
        "n_positive_marginal": opp.get("n_positive_marginal"),
        "positive_marginal_by_session": by_session,
        "positive_marginal_by_family": by_family,
        "allocator_heat_gap": opp.get("heat_gap"),
        "allocator_request": list(opp.get("research_request") or []),
        "basis": ("reports/pf_allocation.json opportunity block" if opp
                  else "no opportunity block in the allocation artifact on this host"),
    }
    out: list[dict[str, Any]] = []

    def _mission(kind: str, session: str, family: str, state: str, priority: int,
                 title: str, description: str) -> None:
        out.append({
            "source": "portfolio_gap", "kind": "mission", "mission_kind": kind,
            "mission_id": mission_id(kind, session, family),
            "title": title, "description": description,
            "exposure_missing": {"session": session or "any", "family": family or "any",
                                 "state": state or "any"},
            "heat_gap": round(gap, 6), "target_heat": doc.get("target_heat"),
            "held_heat": doc.get("held_heat"), "issued_at": at, "priority": priority,
            "opportunity": context, "status": None,
            "consumer": "deepening_worker / proposers / research brains",
            "rule": ("a mission funds nothing and gates nothing: it is the portfolio asking "
                     "research for the exposure it cannot buy, on the MT5/Fusion universe, and "
                     "a candidate that answers it carries this mission_id back"),
        })

    sessions_txt = (", ".join(f"{k} {v:+.2e}" for k, v in list(by_session.items())[:6])
                    or "no session carries positive unfunded marginal")
    families_txt = (", ".join(f"{k} {v:+.2e}" for k, v in list(by_family.items())[:6])
                    or "no family carries positive unfunded marginal")
    for r in doc.get("research_requests") or []:
        if r.get("kind") == "heat_gap" and gap > 1e-9:
            _mission("heat_gap", "any", "any", "any", 1,
                     f"Mission: fill {gap:.2%} of unfunded heat",
                     f"{r.get('detail')}. The allocator's own reading of where unfunded "
                     f"opportunity sits -- by session: {sessions_txt}; by family: "
                     f"{families_txt}. What to hunt: a mechanism whose marginal dE[log W] is "
                     f"positive against the HELD book, in a session or family the library is "
                     f"thin in, on the MT5/Fusion universe -- not a re-parameterisation of what "
                     f"the book already holds.")
    for b in doc.get("dark_bands") or []:
        _mission("dark_band", str(b), "any", "any", 2,
                 f"Mission: a funded sleeve in the {b} UTC band",
                 f"No funded sleeve trades the {b} UTC band -- the book is flat there whatever "
                 f"the opportunity set offers. Unfunded positive marginal by session today: "
                 f"{sessions_txt}. What to hunt: a mechanism that fires inside {b} UTC on the "
                 f"MT5/Fusion universe, with the payer named.")
    for e in (doc.get("empty_cells") or [])[:MAX_EMPTY_CELL_MISSIONS]:
        _mission("empty_cell", str(e.get("band")), str(e.get("family")), "any", 3,
                 f"Mission: {e.get('family')} in the {e.get('band')} UTC band",
                 f"No certificate has ever come from {e.get('family')} in the {e.get('band')} "
                 f"UTC band. What to hunt: whether the mechanism {e.get('family')} monetises "
                 f"anything inside {e.get('band')} UTC on the MT5/Fusion universe.")
    return out


def tagged_candidates(ids: list[str]) -> dict[str, Any]:
    """Every candidate in the stores that carries a `mission_id` naming an open mission.

    THE TAG DOES NOT SURVIVE THE COMPILER TODAY, and the report says so rather than showing an
    empty list as if nothing had been hunted: `miner_candidate_compiler._candidate` copies url
    and title from the task row and nothing else, so a mission's id is on the queue row and not
    on the candidate it produces. The note names the one line that would carry it.
    """
    wanted = set(ids)
    by_mission: dict[str, list[dict[str, Any]]] = {m: [] for m in ids}
    stores: dict[str, Any] = {}
    for p in CANDIDATE_STORES:
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            stores[p.name] = {"present": False, "candidates": 0, "with_mission_id": 0}
            continue
        rows = doc.get("candidates") if isinstance(doc, dict) else doc
        rows = [r for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict)]
        n_tagged = 0
        for r in rows:
            mid = r.get("mission_id")
            if not isinstance(mid, str):
                continue
            n_tagged += 1
            if mid in wanted:
                by_mission[mid].append({"symbol": r.get("symbol"), "family": r.get("family"),
                                        "source": r.get("source"), "store": p.name,
                                        "params": r.get("params")})
        stores[p.name] = {"present": True, "candidates": len(rows), "with_mission_id": n_tagged}
    n_tagged_total = sum(len(v) for v in by_mission.values())
    note = None
    if not any(s.get("with_mission_id") for s in stores.values()):
        note = ("no candidate store carries mission_id: miner_candidate_compiler._candidate "
                "copies url and title from the task row and nothing else, so the tag stays on "
                "the queue row and does not reach the candidate. Coordinator: copy "
                "row.get('mission_id') onto the candidate there (one line) and this report "
                "fills itself")
    return {"by_mission": by_mission, "n_candidates_tagged": n_tagged_total, "stores": stores,
            "note": note}


def write_missions(doc: dict[str, Any], alloc: dict[str, Any], *, write_queue: bool = True,
                   now: datetime | None = None) -> dict[str, Any]:
    """Write RESEARCH_MISSIONS.json and, when there are missions, this source's queue rows."""
    rows = missions(doc, alloc, now=now)
    tagged = tagged_candidates([m["mission_id"] for m in rows])
    queue: dict[str, Any] = {"source": "portfolio_gap", "n_tasks": len(rows), "written": False,
                             "why": "no mission this pass"}
    if rows and write_queue:
        try:
            try:
                from research.regime_coverage import _merge_into_queue
            except ImportError:
                from regime_coverage import _merge_into_queue
            _merge_into_queue(rows, source="portfolio_gap")
            queue.update(written=True, why=f"{len(rows)} mission(s) written under source "
                                            f"portfolio_gap, replacing that source's rows only")
        except Exception as exc:
            queue["why"] = f"queue write failed: {type(exc).__name__}: {exc}"
    elif rows:
        queue["why"] = "queue write disabled for this pass"
    report = {
        "generated_utc": (now or datetime.now(UTC)).isoformat(),
        "n_open": len(rows), "heat_gap": doc.get("heat_gap"),
        "target_heat": doc.get("target_heat"), "held_heat": doc.get("held_heat"),
        "by_kind": {k: sum(1 for m in rows if m["mission_kind"] == k)
                    for k in ("heat_gap", "dark_band", "empty_cell")},
        "missions": rows,
        "candidates_by_mission": tagged["by_mission"],
        "n_candidates_tagged": tagged["n_candidates_tagged"],
        "candidate_stores": tagged["stores"], "tagging_note": tagged["note"],
        "queue": queue,
        "rule": ("open missions are the portfolio's standing research asks, re-derived from "
                 "reports/portfolio_gap.json and the allocator's opportunity block every pass; "
                 "a mission funds nothing and gates nothing"),
    }
    MISSIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    MISSIONS_OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    if not ALLOC.exists():
        print("no pf_allocation.json -- the gap is UNMEASURED, not zero. Run pf_allocator first.")
        return 2
    alloc = json.loads(ALLOC.read_text(encoding="utf-8"))
    survivors = load_survivors()
    doc = build(alloc, survivors)

    print(f"heat {doc['held_heat']:.2%} / target {doc['target_heat']:.2%}  "
          f"gap {doc['heat_gap']:.2%}   certificates {doc['n_certificates']}  "
          f"funded {doc['n_funded']}")
    fams = doc["families"]
    print(f"\n{'band':>7} " + " ".join(f"{f[:14]:>14}" for f in fams))
    lookup = {(m["band"], m["family"]): m for m in doc["matrix"]}
    for b in doc["bands"]:
        row = []
        for f in fams:
            m = lookup.get((b, f))
            row.append("             ." if m is None
                       else f"{m['certificates']:>6}c{m['funded_heat'] * 100:>6.2f}%")
        print(f"{b:>7} " + " ".join(row))
    print(f"\ndark bands (no funded sleeve): {doc['dark_bands'] or 'none'}")
    for r in doc["research_requests"][:12]:
        print(f"  [{r['priority']}] {r['kind']}: {r['detail']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"-> {_rel(OUT)}")
    rep = write_missions(doc, alloc)
    print(f"missions: {rep['n_open']} open ({rep['by_kind']}), "
          f"{rep['n_candidates_tagged']} candidate(s) tagged -- {rep['queue']['why']}")
    print(f"-> {_rel(MISSIONS_OUT)}")
    return 0


def _rel(p: Path) -> str:
    """Repository-relative when the path is inside the repository, absolute otherwise -- a
    test that points OUT at tmp_path must not fail the pass on the print line."""
    try:
        return str(p.relative_to(BASE.parent.parent))
    except ValueError:
        return str(p)


if __name__ == "__main__":
    raise SystemExit(main())
