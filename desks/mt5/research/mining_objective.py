"""THE MINING OBJECTIVE -- the one thing the mining layer is judged on, measured every run.

Ledger items M17/M18 (principal, 2026-09-17). Every organ under `desks/mt5/research` that mints,
compiles, recombines or donates a hypothesis has been scored on whatever number its own artifact
happened to print -- rows donated, cells compiled, leads crawled. Those are activity counters, and
an activity counter is exactly the thing a search process learns to maximise. There is ONE binding
objective, it is written here, and it is measured from the canonical registry rather than asserted.

    FIVE SOVEREIGN KPIs, in order

    1. ORTHOGONAL CANDIDATE THROUGHPUT -- novel, economically distinct candidates per day: rows
       whose grid cell is new to the breadth grid OR whose mechanism is new to the registry, after
       content-hash duplicates are removed. The same rule enqueued twice is ONE candidate.
    2. FRONTIER COVERAGE GAIN -- cells of the breadth grid (`registry.GRID_AXES`) that were
       previously unmeasured and were opened on the day. Coverage may only ratchet up (L1.50).
    3. CANDIDATE INDEPENDENCE -- 1 - mean max similarity of the day's candidates against
       everything the desk already holds: other candidates, survivors, live sleeves, the
       graveyard, the common factors and the mechanism ancestry.
    4. GAUNTLET-WORTHY CONVERSION -- implementation-ready discoveries / raw discoveries. A
       discovery nobody compiled is a lead, not an opportunity.
    5. DOWNSTREAM SURVIVOR YIELD PER GENERATOR -- independent survivors / valid candidates. It is
       the FEEDBACK SIGNAL and NEVER THE TARGET: a miner that optimises survivor rate stops
       mining the frontier and starts mining the gauntlet's known tastes, which is the one way to
       make the opportunity set smaller while every dashboard goes green.

THE ANTI-GAMING LAW, and it is the reason the five are ordered the way they are:

    CANDIDATE QUANTITY HAS ZERO INTRINSIC VALUE. A generator emitting 100,000 parameter mutations
    of one mechanism scores BELOW one emitting 10 candidates in 10 new mechanism cells.

That is not a slogan here -- it is arithmetic, and `test_mining_objective.py` asserts it against
synthetic rows. The reward multiplies novelty by orthogonality, so a flood of near-duplicates
multiplies a small number by a small number and loses to ten distinct cells at any volume.

    THE MINER REWARD, per generator

    Reward = NovelMechanism x ExpectedOrthogonality x EconomicPlausibility x GauntletReadiness
             + LAMBDA x SurvivorOutcome + GAMMA x delta_n_eff          (LAMBDA=1.0, GAMMA=2.0)

Each of the four product terms is in [0, 1] and is read off the generator's own registry rows; an
unmeasured term takes the registry's PRIOR (0.5) and never 1.0, so an unmeasured generator cannot
outrank a measured one by absence. The attributed delta E[log W] is written back to the registry
with `generator_yield_update`, and every KPI lands in `kpis(day, name, value)` so the series
survives this process.

THE MOAT KPIs ride alongside and are the same measurement at a different grain: novel mechanisms
per day, high-value candidates (above the 90th percentile of every scored row), independent
candidates per 1000 leads, survivors per source, delta n_eff per 1000 candidates, delta E[log W]
per research compute hour, and the unseen mechanism mass per language, source and asset class.
Each is UNMEASURED BY NAME where the artifact that owns it is absent, never zero.

THE ORGANISATIONAL LAW is a constant in this module and a check, not a comment. Mining maximises
the OPPORTUNITY SET; the gauntlet owns TRUTH; the forward lane owns REALITY; the allocator owns
GROWTH. `separation_of_powers()` greps every mining organ -- the declared list plus whatever
generators the registry is paying -- for writes to `data/sleeves.json`, the sleeve registry, the
survivor ledger or the promoter's other inputs, and names any organ that has started grading its
own homework.

    python desks/mt5/research/mining_objective.py             # measure, write, record
    python desks/mt5/research/mining_objective.py --dry-run   # measure, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DESK, ROOT = _DESK, _ROOT
DATA, REPORTS = DESK / "data", DESK / "reports"
RESEARCH = DESK / "research"
EXPOSURE = REPORTS / "EXPOSURE_DECOMPOSITION.json"
ALLOCATION = REPORTS / "pf_allocation.json"
EFFECTIVE_BREADTH = DATA / "effective_breadth.jsonl"
COMPUTE_LEDGER = DATA / "compute_ledger.jsonl"
UNSEEN_FRONTIER = REPORTS / "UNSEEN_FRONTIER.json"
SLEEVES = DATA / "sleeves.json"
OUT = REPORTS / "MINING_OBJECTIVE.json"

#: DECLARED weights of the reward's two additive terms. They are the price the desk puts on a
#: survivor and on a unit of effective breadth relative to one unit of novel, orthogonal,
#: plausible, ready opportunity. Changing either re-prices every generator, so it is a decision.
LAMBDA = 1.0
GAMMA = 2.0
#: A discovery is IMPLEMENTATION-READY once it has been compiled into cells or queued for them.
#: TESTED is beyond ready and is reported separately rather than folded in -- a conversion rate
#: that counts the already-judged flatters a generator whose queue has simply drained.
READY_STATES: tuple[str, ...] = ("COMPILED", "QUEUED")
#: Unmeasured factors take the registry's prior, never 1.0 (see `registry.score_candidate`).
PRIOR = 0.5
TRAILING_DAYS = 7

SOVEREIGN: tuple[str, ...] = ("orthogonal_candidate_throughput", "frontier_coverage_gain",
                              "candidate_independence", "gauntlet_worthy_conversion",
                              "downstream_survivor_yield")

LAW = (
    "MINING MAXIMISES THE OPPORTUNITY SET. The gauntlet owns truth, the forward lane owns "
    "reality, and the allocator owns growth. The four jobs stay separate: a mining organ that "
    "writes a sleeve, edits the sleeve registry or feeds the promoter has stopped enlarging the "
    "set of things that can be judged and started judging them, and a search process that grades "
    "its own homework converges on its own tastes. Candidate quantity has zero intrinsic value: "
    "100,000 parameter mutations of one mechanism are worth less than 10 candidates in 10 new "
    "mechanism cells, and the reward is built so that is arithmetic rather than exhortation."
)

#: THE MINING ORGANS, declared. `separation_of_powers` greps these plus every generator the
#: registry is paying. A new miner belongs here the day it lands; an organ absent from this list
#: and absent from `generator_yield` is unchecked, and the report says how many that is.
MINING_ORGANS: tuple[str, ...] = (
    "anomaly_factory", "axis_proposer", "breadth_frontier", "causal_discovery", "crowding_miner",
    "data_axis_miner", "deep_forest_miner", "descendants", "edge_search", "empty_cluster_forcer",
    "frontier_map", "microstructure_miner", "miner_candidate_compiler", "moat_miner",
    "moat_series", "proposer_common", "qd_frontier", "regime_discovery",
    "representation_discovery", "research_tree", "residual_queue", "source_registry",
    "standing_questions", "unseen_frontier", "unused_information", "mining_objective",
)
#: The promoter's own state and inputs. A mining organ may READ any of these; writing one is the
#: separation breach. `promoter` as an import is listed too: calling into it is writing by proxy.
PROTECTED_WRITES: tuple[str, ...] = ("sleeves.json", "sleeve_registry.json",
                                     "UNIVERSAL_SURVIVORS.json", "GOLD_RETIRED.json")
_WRITE_CALL = re.compile(r"\.write_text\(|\.write_bytes\(|json\.dump\(|os\.replace\(|"
                         r"\bopen\([^)]*[\"']w|shutil\.(copy|move)")
_PROMOTER_IMPORT = re.compile(r"^\s*(from\s+(?:research\s+import\s+promoter|research\.promoter)"
                              r"|import\s+promoter|from\s+promoter\s+import)", re.M)

#: Similarity, DECLARED. The same rule is the same candidate; the same family on the same symbol
#: and chart is a parameter mutation; the same family is a style; the same mechanism is a story.
SIM_SAME_HASH = 1.0
SIM_SAME_FAMILY_SYMBOL_CHART = 0.8
SIM_SAME_FAMILY = 0.5
SIM_SAME_MECHANISM = 0.4


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def _day_of(stamp: Any) -> str:
    s = str(stamp or "")[:10]
    return s if len(s) == 10 and s[4] == "-" else ""


def _window(day: str, days: int) -> set[str]:
    try:
        end = date.fromisoformat(day)
    except ValueError:
        end = datetime.now(tz=UTC).date()
    return {(end - timedelta(days=i)).isoformat() for i in range(days)}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _f(v: Any, default: float) -> float:
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


# ------------------------------------------------------------------------------ similarity --

def _key(row: Any) -> dict[str, str]:
    """A candidate-shaped row reduced to the four fields similarity is defined on."""
    get = row.get if hasattr(row, "get") else (lambda k, d=None: d)
    return {"hash": str(get("content_hash") or ""), "family": str(get("family") or "").lower(),
            "symbol": str(get("symbol") or "").lower(), "chart": str(get("chart") or "").lower(),
            "mechanism": str(get("mechanism") or "").lower()}


def similarity(a: Any, b: Any) -> float:
    """Same content hash 1.0; same family+symbol+chart 0.8; same family 0.5; same mechanism 0.4."""
    x, y = _key(a), _key(b)
    if x["hash"] and x["hash"] == y["hash"]:
        return SIM_SAME_HASH
    if x["family"] and x["family"] == y["family"]:
        if x["symbol"] == y["symbol"] and x["chart"] == y["chart"]:
            return SIM_SAME_FAMILY_SYMBOL_CHART
        return SIM_SAME_FAMILY
    if x["mechanism"] and x["mechanism"] == y["mechanism"]:
        return SIM_SAME_MECHANISM
    return 0.0


def factor_similarity(path: Path | None = None) -> tuple[dict[str, float], str | None]:
    """Per-cell factor overlap from `EXPOSURE_DECOMPOSITION.json`'s measured duplicate heat: the
    largest cosine each named cell shares with any other. Absent means it contributes NOTHING and
    is named in `unmeasured` -- a factor overlap nobody measured is not a factor overlap of zero."""
    doc = _read_json(path or EXPOSURE)
    pairs = doc.get("duplicate_heat") if isinstance(doc, dict) else None
    if not isinstance(pairs, list):
        return {}, f"{(path or EXPOSURE).name} absent -- factor similarity UNMEASURED"
    out: dict[str, float] = {}
    for p in pairs:
        if not isinstance(p, dict):
            continue
        cos = _f(p.get("cosine"), 0.0)
        for side in ("a", "b"):
            name = str(p.get(side) or "").lower()
            if name:
                out[name] = max(out.get(name, 0.0), cos)
    return out, None


def corpus(cands: list[dict[str, Any]], *, sleeves: Path | None = None
           ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Everything a new candidate has to be different FROM: the registry's other candidates, its
    survivors, its graveyard, its mechanism ancestry, and the live sleeves the desk is trading."""
    rows: list[dict[str, Any]] = []
    counts = {"candidates": 0, "survivors": 0, "graveyard": 0, "live_sleeves": 0,
              "mechanism_ancestry": 0}
    mechanisms: set[str] = set()
    for c in cands:
        rows.append({**c, "kind": "candidate"})
        counts["candidates"] += 1
        status = str(c.get("status") or "").lower()
        if status == "survived" or c.get("survived"):
            counts["survivors"] += 1
        elif status in ("judged", "rejected", "failed") or c.get("rejection_reason"):
            counts["graveyard"] += 1
        mech = str(c.get("mechanism") or "").lower()
        if mech:
            mechanisms.add(mech)
    counts["mechanism_ancestry"] = len(mechanisms)
    doc = _read_json(sleeves or SLEEVES)
    srows = doc.get("sleeves") if isinstance(doc, dict) else doc
    for s in (list(srows.values()) if isinstance(srows, dict) else list(srows or [])):
        if not isinstance(s, dict) or str(s.get("status") or "").upper() != "LIVE":
            continue
        rows.append({"kind": "live_sleeve", "content_hash": "", "family": s.get("family"),
                     "symbol": s.get("symbol"), "chart": s.get("timeframe"),
                     "mechanism": s.get("family"), "id": s.get("name")})
        counts["live_sleeves"] += 1
    return rows, counts


def max_similarity(cand: dict[str, Any], against: list[dict[str, Any]],
                   factors: dict[str, float] | None = None) -> float:
    """The largest similarity against anything the desk already holds, including the measured
    factor overlap of the cell when the exposure decomposition names it."""
    cid = str(cand.get("id") or "")
    best = 0.0
    for other in against:
        if cid and str(other.get("id") or "") == cid:
            continue
        best = max(best, similarity(cand, other))
        if best >= 1.0:
            return 1.0
    for name in (cid, str(cand.get("donated_cell") or ""),
                 f"{cand.get('symbol')}.{cand.get('family')}"):
        if name and factors:
            best = max(best, _clip01(factors.get(name.lower(), 0.0)))
    return _clip01(best)


# ------------------------------------------------------------------------ the five sovereign --

def _dedupe(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Content-hash duplicates are ONE candidate -- the registry already enforces it on write,
    and this repeats it on read so a hand-seeded row cannot inflate the throughput."""
    seen: set[str] = set()
    out = []
    for c in sorted(cands, key=lambda r: str(r.get("created_at") or "")):
        h = str(c.get("content_hash") or "")
        if h and h in seen:
            continue
        if h:
            seen.add(h)
        out.append(c)
    return out


def sovereign(cands: list[dict[str, Any]], discs: list[dict[str, Any]],
              yields: list[dict[str, Any]], *, day: str, factors: dict[str, float],
              against: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The five, each per day and per trailing 7 days, each from the registry's own rows."""
    rows = _dedupe(cands)
    win = _window(day, TRAILING_DAYS)
    first_cell: dict[str, str] = {}
    first_mech: dict[str, str] = {}
    for c in rows:
        d = _day_of(c.get("created_at"))
        cell, mech = str(c.get("grid_cell") or ""), str(c.get("mechanism") or "").lower()
        if cell and (cell not in first_cell or d < first_cell[cell]):
            first_cell[cell] = d
        if mech and (mech not in first_mech or d < first_mech[mech]):
            first_mech[mech] = d

    def novel(c: dict[str, Any]) -> bool:
        d = _day_of(c.get("created_at"))
        cell, mech = str(c.get("grid_cell") or ""), str(c.get("mechanism") or "").lower()
        return (bool(cell) and first_cell.get(cell) == d) or (bool(mech)
                                                              and first_mech.get(mech) == d)

    by_day: dict[str, int] = defaultdict(int)
    for c in rows:
        if novel(c):
            by_day[_day_of(c.get("created_at"))] += 1
    opened: dict[str, int] = defaultdict(int)
    for cell, d in first_cell.items():
        if cell:
            opened[d] += 1

    day_rows = [c for c in rows if _day_of(c.get("created_at")) == day]
    win_rows = [c for c in rows if _day_of(c.get("created_at")) in win]
    sims_day = [max_similarity(c, against, factors) for c in day_rows]
    sims_win = [max_similarity(c, against, factors) for c in win_rows]

    ready = sum(1 for d in discs if str(d.get("state") or "") in READY_STATES)
    tested = sum(1 for d in discs if str(d.get("state") or "") == "TESTED")
    raw = len(discs)
    ready_win = sum(1 for d in discs if _day_of(d.get("created_at")) in win
                    and str(d.get("state") or "") in READY_STATES)
    raw_win = sum(1 for d in discs if _day_of(d.get("created_at")) in win)

    per_gen = []
    for y in yields:
        valid = int(y.get("judged") or 0) or int(y.get("generated") or 0)
        per_gen.append({"generator": y.get("generator"),
                        "independent_survivors": int(y.get("independent_survivors") or 0),
                        "valid_candidates": valid,
                        "yield": None if valid == 0 else round(
                            float(y.get("independent_survivors") or 0) / valid, 6)})
    measured = [g["yield"] for g in per_gen if g["yield"] is not None]

    def kpi(name: str, dayv: float | None, trail: float | None, basis: str,
            **detail: Any) -> dict[str, Any]:
        return {"name": name, "day": dayv, "trailing_7d": trail, "basis": basis,
                "unmeasured": None if dayv is not None or trail is not None else
                              "no registry rows in the window -- UNMEASURED, not zero",
                **detail}

    # An EMPTY registry is UNMEASURED, not a zero throughput: nothing has told this organ
    # whether the miners produced nothing or whether nothing wrote their rows down (L1.28a).
    any_rows = bool(rows)
    return {
        "orthogonal_candidate_throughput": kpi(
            "orthogonal_candidate_throughput",
            float(by_day.get(day, 0)) if any_rows else None,
            round(sum(by_day.get(d, 0) for d in win) / TRAILING_DAYS, 4) if any_rows else None,
            "candidates created whose grid cell or mechanism is new to the registry, after "
            "content-hash dedupe; per day",
            n_candidates_total=len(rows), n_duplicates_removed=len(cands) - len(rows)),
        "frontier_coverage_gain": kpi(
            "frontier_coverage_gain",
            float(opened.get(day, 0)) if any_rows else None,
            round(sum(opened.get(d, 0) for d in win) / TRAILING_DAYS, 4) if any_rows else None,
            "previously unmeasured cells of the breadth grid opened per day",
            n_cells_occupied=len(first_cell), axes=list(_grid_axes())),
        "candidate_independence": kpi(
            "candidate_independence",
            None if not sims_day else round(1.0 - float(np.mean(sims_day)), 6),
            None if not sims_win else round(1.0 - float(np.mean(sims_win)), 6),
            "1 - mean max similarity against candidates, survivors, live sleeves, the graveyard, "
            "the common factors and the mechanism ancestry",
            n_day=len(day_rows), n_trailing=len(win_rows), corpus_size=len(against)),
        "gauntlet_worthy_conversion": kpi(
            "gauntlet_worthy_conversion",
            None if raw == 0 else round(ready / raw, 6),
            None if raw_win == 0 else round(ready_win / raw_win, 6),
            f"discoveries in {'/'.join(READY_STATES)} / raw discoveries",
            ready=ready, raw=raw, tested_beyond_ready=tested),
        "downstream_survivor_yield": kpi(
            "downstream_survivor_yield",
            None if not measured else round(float(np.mean(measured)), 6),
            None if not measured else round(float(np.mean(measured)), 6),
            "independent survivors / valid candidates, per generator",
            per_generator=per_gen, feedback_only=True,
            why_not_a_target="a miner that optimises survivor rate mines the gauntlet's known "
                             "tastes instead of the frontier, and the opportunity set shrinks "
                             "while every dashboard goes green"),
    }


def _grid_axes() -> tuple[str, ...]:
    try:
        from libs.moat.registry import GRID_AXES
    except ImportError:
        return ()
    return tuple(GRID_AXES)


# -------------------------------------------------------------------------- the moat KPIs --

def moat_kpis(cands: list[dict[str, Any]], discs: list[dict[str, Any]],
              yields: list[dict[str, Any]], sources: list[dict[str, Any]], *, day: str,
              factors: dict[str, float], against: list[dict[str, Any]],
              unmeasured: list[dict[str, str]]) -> dict[str, Any]:
    rows = _dedupe(cands)
    win = _window(day, TRAILING_DAYS)
    day_rows = [c for c in rows if _day_of(c.get("created_at")) == day]
    win_rows = [c for c in rows if _day_of(c.get("created_at")) in win]

    seen_mech: set[str] = set()
    novel_by_day: dict[str, int] = defaultdict(int)
    for c in sorted(rows, key=lambda r: str(r.get("created_at") or "")):
        mech = str(c.get("mechanism") or "").lower()
        if mech and mech not in seen_mech:
            seen_mech.add(mech)
            novel_by_day[_day_of(c.get("created_at"))] += 1

    scores = [_f(c.get("score"), 0.0) for c in rows if c.get("score") is not None]
    p90 = float(np.percentile(np.asarray(scores, dtype=float), 90)) if scores else None
    high_day = sum(1 for c in day_rows if p90 is not None and _f(c.get("score"), 0.0) > p90)

    leads = sum(int(s.get("leads") or 0) for s in sources)
    leads_basis = "registry source_yield.leads"
    if leads == 0:
        leads, leads_basis = len(rows), "no source_yield rows -- candidates stand in for leads"
    indep = sum(1.0 - max_similarity(c, against, factors) for c in win_rows)

    n_eff, n_eff_why = _delta_n_eff(win)
    per_1000 = (None if leads == 0 else round(indep / leads * 1000.0, 4))
    if n_eff is None:
        unmeasured.append({"what": "delta_n_eff_per_1000_candidates", "why": n_eff_why or ""})
    elogw, elogw_why = _delta_elogw_per_compute_hour(win)
    if elogw is None:
        unmeasured.append({"what": "delta_elogw_per_research_compute_hour", "why": elogw_why or ""})
    unseen, unseen_why = _unseen_mass()
    if unseen is None:
        unmeasured.append({"what": "unseen_mechanism_mass", "why": unseen_why or ""})

    return {
        "novel_mechanisms_per_day": {"day": float(novel_by_day.get(day, 0)),
                                     "trailing_7d": round(sum(novel_by_day.get(d, 0)
                                                              for d in win) / TRAILING_DAYS, 4),
                                     "n_distinct_mechanisms": len(seen_mech)},
        "high_value_candidates_per_day": {"day": float(high_day), "p90_score": p90,
                                          "basis": "candidates scoring above the 90th percentile "
                                                   "of every scored candidate in the registry"},
        "independent_candidates_per_1000_leads": {"value": per_1000, "leads": leads,
                                                  "basis": leads_basis,
                                                  "independent_mass": round(indep, 4)},
        "survivors_per_source": [{"source_id": s.get("source_id"), "leads": s.get("leads"),
                                  "survivors": s.get("survivors"),
                                  "independent_survivors": s.get("independent_survivors")}
                                 for s in sources[:50]],
        "delta_n_eff_per_1000_candidates": {"value": (None if n_eff is None or not win_rows else
                                                      round(n_eff / len(win_rows) * 1000.0, 6)),
                                            "delta_n_eff": n_eff, "n_candidates": len(win_rows),
                                            "why": n_eff_why},
        "delta_elogw_per_research_compute_hour": {"value": elogw, "why": elogw_why},
        "unseen_mechanism_mass": unseen if unseen is not None else {"status": "UNMEASURED",
                                                                    "why": unseen_why},
        "yield_per_generator": [{"generator": y.get("generator"), "yield": y.get("yield"),
                                 "generated": y.get("generated"), "judged": y.get("judged"),
                                 "independent_survivors": y.get("independent_survivors"),
                                 "delta_n_eff": y.get("delta_n_eff")} for y in yields],
    }


def _delta_n_eff(win: set[str]) -> tuple[float | None, str | None]:
    rows = []
    try:
        with EFFECTIVE_BREADTH.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and _day_of(r.get("at")) in win:
                    rows.append(r)
    except OSError:
        return None, f"{EFFECTIVE_BREADTH.name} absent -- effective breadth UNMEASURED"
    if len(rows) < 2:
        return None, (f"{EFFECTIVE_BREADTH.name} holds {len(rows)} reading(s) in the window; a "
                      "delta needs two")
    rows.sort(key=lambda r: str(r.get("at") or ""))
    a = _f(rows[0].get("effective_breadth"), float("nan"))
    b = _f(rows[-1].get("effective_breadth"), float("nan"))
    if not np.isfinite(a) or not np.isfinite(b):
        return None, "effective_breadth unreadable in the window"
    return round(b - a, 6), f"{rows[0]['at'][:10]} -> {rows[-1]['at'][:10]}"


def _delta_elogw_per_compute_hour(win: set[str]) -> tuple[float | None, str | None]:
    doc = _read_json(ALLOCATION)
    if not isinstance(doc, dict):
        return None, f"{ALLOCATION.name} absent -- delta E[log W] UNMEASURED"
    post = doc.get("posterior_growth") if isinstance(doc.get("posterior_growth"), dict) else {}
    cert = post.get("certificate") if isinstance(post.get("certificate"), dict) else {}
    elogw = cert.get("elogw_per_day")
    if elogw is None:
        growth = doc.get("growth") if isinstance(doc.get("growth"), dict) else {}
        elogw = growth.get("mean_log_per_day")
    if elogw is None:
        return None, f"{ALLOCATION.name} carries no elogw_per_day -- UNMEASURED"
    hours = 0.0
    try:
        with COMPUTE_LEDGER.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and _day_of(r.get("at")) in win:
                    hours += _f(r.get("wall_s"), 0.0) / 3600.0
    except OSError:
        return None, f"{COMPUTE_LEDGER.name} absent -- research compute hours UNMEASURED"
    if hours <= 0:
        return None, f"{COMPUTE_LEDGER.name} records no compute in the window"
    return round(_f(elogw, 0.0) / hours, 8), (f"pf_allocation elogw_per_day {elogw} over "
                                              f"{round(hours, 3)} research compute hour(s)")


def _unseen_mass() -> tuple[dict[str, Any] | None, str | None]:
    doc = _read_json(UNSEEN_FRONTIER)
    if not isinstance(doc, dict):
        return None, f"{UNSEEN_FRONTIER.name} absent -- unseen mechanism mass UNMEASURED"
    out = {k: doc[k] for k in ("by_language", "by_source_type", "by_asset_class", "by_source",
                               "total_unseen", "chao1_unseen") if k in doc}
    return (out or None), (None if out else
                           f"{UNSEEN_FRONTIER.name} carries no per-axis unseen estimate")


# ------------------------------------------------------------------------------ the reward --

def rewards(cands: list[dict[str, Any]], discs: list[dict[str, Any]],
            yields: list[dict[str, Any]], *, factors: dict[str, float],
            against: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reward = NovelMechanism x ExpectedOrthogonality x EconomicPlausibility x GauntletReadiness
    + LAMBDA x SurvivorOutcome + GAMMA x delta_n_eff, per generator, every term from its rows."""
    rows = _dedupe(cands)
    by_gen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in rows:
        by_gen[str(c.get("generator") or c.get("origin") or "unknown")].append(c)
    disc_by_gen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in discs:
        disc_by_gen[str(d.get("generator") or d.get("origin") or "unknown")].append(d)
    yield_by_gen = {str(y.get("generator") or ""): y for y in yields}
    seen_mech: set[str] = set()
    first_mech: dict[str, str] = {}
    for c in sorted(rows, key=lambda r: str(r.get("created_at") or "")):
        mech = str(c.get("mechanism") or "").lower()
        if mech and mech not in seen_mech:
            seen_mech.add(mech)
            first_mech[mech] = str(c.get("generator") or c.get("origin") or "unknown")

    out = []
    for gen in sorted(set(by_gen) | set(disc_by_gen) | set(yield_by_gen)):
        mine = by_gen.get(gen, [])
        n = len(mine)
        mechs = {str(c.get("mechanism") or "").lower() for c in mine if c.get("mechanism")}
        novel = sum(1 for m in mechs if first_mech.get(m) == gen)
        novel_mechanism = _clip01(novel / n) if n else PRIOR
        orth = (_clip01(float(np.mean([1.0 - max_similarity(c, against, factors) for c in mine])))
                if mine else PRIOR)
        named = sum(1 for c in mine if str(c.get("mechanism") or "").strip())
        strength = float(np.mean([_f(c.get("mechanism_strength"), PRIOR) for c in mine])
                         ) if mine else PRIOR
        plausibility = _clip01(strength * (named / n if n else PRIOR))
        mydiscs = disc_by_gen.get(gen, [])
        if mydiscs:
            readiness = _clip01(sum(1 for d in mydiscs
                                    if str(d.get("state") or "") in READY_STATES) / len(mydiscs))
            readiness_basis = f"{len(mydiscs)} discovery(ies) in {'/'.join(READY_STATES)}"
        elif mine:
            ok = ("queued", "claimed", "judged", "survived", "donated")
            readiness = _clip01(sum(1 for c in mine
                                    if str(c.get("status") or "").lower() in ok) / n)
            readiness_basis = "no discoveries: candidate statuses that reached the docket"
        else:
            readiness, readiness_basis = PRIOR, "UNMEASURED -- the registry's prior, never 1.0"
        y = yield_by_gen.get(gen, {})
        valid = int(y.get("judged") or 0) or int(y.get("generated") or 0)
        survivor = (_clip01(float(y.get("independent_survivors") or 0) / valid) if valid
                    else 0.0)
        d_n_eff = _f(y.get("delta_n_eff"), 0.0)
        product = novel_mechanism * orth * plausibility * readiness
        reward = product + LAMBDA * survivor + GAMMA * d_n_eff
        out.append({
            "generator": gen, "reward": round(float(reward), 6),
            "n_candidates": n, "n_discoveries": len(mydiscs),
            "terms": {"NovelMechanism": round(novel_mechanism, 6),
                      "ExpectedOrthogonality": round(orth, 6),
                      "EconomicPlausibility": round(plausibility, 6),
                      "GauntletReadiness": round(readiness, 6),
                      "product": round(float(product), 6),
                      "SurvivorOutcome": round(survivor, 6), "delta_n_eff": d_n_eff,
                      "LAMBDA": LAMBDA, "GAMMA": GAMMA},
            "basis": {"novel_mechanisms": novel, "distinct_mechanisms": len(mechs),
                      "readiness": readiness_basis, "valid_candidates": valid},
        })
    return sorted(out, key=lambda r: -r["reward"])


def anti_gaming(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The law as a REPORT FIELD: whether the noisiest generator is also the best-rewarded one."""
    if not rows:
        return {"law": "candidate quantity has zero intrinsic value",
                "status": "UNMEASURED -- no generator has rows in the registry"}
    loudest = max(rows, key=lambda r: r["n_candidates"])
    best = max(rows, key=lambda r: r["reward"])
    # THE GAMING SIGNATURE: the noisiest generator takes the top reward while some quieter one
    # scores strictly better on the PRODUCT -- it won on volume-driven additive terms, not merit.
    outscored = max((r["terms"]["product"] for r in rows if r is not loudest), default=0.0)
    return {"law": "candidate quantity has zero intrinsic value: 100,000 parameter mutations of "
                   "one mechanism score below 10 candidates in 10 new mechanism cells",
            "loudest_generator": loudest["generator"],
            "loudest_n_candidates": loudest["n_candidates"],
            "loudest_reward": loudest["reward"],
            "loudest_product": loudest["terms"]["product"],
            "best_generator": best["generator"], "best_reward": best["reward"],
            "quantity_wins": bool(len(rows) > 1
                                  and loudest["generator"] == best["generator"]
                                  and outscored > loudest["terms"]["product"]),
            "ranking": [{"generator": r["generator"], "n_candidates": r["n_candidates"],
                         "reward": r["reward"], "product": r["terms"]["product"]}
                        for r in rows[:20]]}


# ----------------------------------------------------------------- separation of powers --

def separation_of_powers(organs: list[str] | None = None, *, research: Path | None = None,
                         yields: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """No mining organ writes the promoter's state. Greps the declared MINING_ORGANS plus every
    generator the registry is paying, and names the violators rather than counting them."""
    base = research or RESEARCH
    names: list[str] = list(organs if organs is not None else MINING_ORGANS)
    for y in (yields or []):
        raw = str(y.get("generator") or "")
        for part in (raw, raw.split(":")[-1], raw.split(":")[0]):
            stem = Path(part).stem
            if stem and stem not in names and (base / f"{stem}.py").exists():
                names.append(stem)
    violations: list[dict[str, Any]] = []
    checked, missing = [], []
    for name in names:
        path = base / f"{name}.py"
        if not path.exists():
            missing.append(name)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            missing.append(name)
            continue
        checked.append(name)
        # A module-level name BOUND to a protected path IS that path: `SLEEVES_FILE.write_text`
        # is a write to sleeves.json, and the breach is reported under the path, not the alias.
        targets = {k: k for k in PROTECTED_WRITES}
        for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.+)$", text, re.M):
            for protected in PROTECTED_WRITES:
                if protected in m.group(2):
                    targets[m.group(1)] = protected
                    break
        for i, line in enumerate(text.splitlines(), 1):
            if not _WRITE_CALL.search(line):
                continue
            for alias, protected in sorted(targets.items()):
                if re.search(rf"(?<![\w.]){re.escape(alias)}\b", line):
                    violations.append({"organ": f"desks/mt5/research/{name}.py", "line": i,
                                       "writes": protected, "alias": alias,
                                       "text": line.strip()[:140]})
                    break
        m = _PROMOTER_IMPORT.search(text)
        if m:
            violations.append({"organ": f"desks/mt5/research/{name}.py",
                               "line": text[:m.start()].count("\n") + 1, "writes": "promoter",
                               "text": m.group(0).strip()[:140]})
    return {"ok": not violations, "violations": violations, "n_checked": len(checked),
            "checked": checked, "not_found": missing, "protected": list(PROTECTED_WRITES),
            "rule": "mining may READ the promoter's state and may never write it"}


# ----------------------------------------------------------------------------------- the leg --

def _registry_rows() -> tuple[list, list, list, list, str | None]:
    try:
        from libs.moat import registry as reg
    except ImportError as exc:
        return [], [], [], [], f"registry unimportable: {exc}"
    try:
        conn = reg.connect()
        try:
            cands = reg.candidates(limit=200_000, conn=conn)
            discs = reg.discoveries(limit=200_000, conn=conn)
            ylds = reg.generator_yields(conn=conn)
            srcs = [dict(r) for r in conn.execute("SELECT * FROM source_yield").fetchall()]
        finally:
            conn.close()
    except Exception as exc:  # the objective is a measurement, never a blocker
        return [], [], [], [], f"{type(exc).__name__}: {exc}"
    return cands, discs, ylds, srcs, None


def _publish(day: str, report: dict[str, Any]) -> tuple[int, str | None]:
    """Every KPI and every reward into `kpis(day, name, value)`; the attributed delta E[log W]
    back onto the generator's row. The series has to survive this process to be a series."""
    try:
        from libs.moat import registry as reg
    except ImportError as exc:
        return 0, f"registry unimportable: {exc}"
    n = 0
    try:
        conn = reg.connect()
        try:
            for name, row in report["sovereign"].items():
                reg.kpi(day, f"sovereign.{name}", row.get("day"),
                        {"trailing_7d": row.get("trailing_7d"), "basis": row.get("basis")},
                        conn=conn)
                n += 1
            for name, row in report["moat_kpis"].items():
                value = (row.get("day") if isinstance(row, dict) and "day" in row else
                         row.get("value") if isinstance(row, dict) else None)
                reg.kpi(day, f"moat.{name}", value if isinstance(value, (int, float)) else None,
                        row if isinstance(row, dict) else {"rows": row}, conn=conn)
                n += 1
            total = sum(r["terms"]["SurvivorOutcome"] for r in report["rewards"]) or 0.0
            elogw = report["moat_kpis"]["delta_elogw_per_research_compute_hour"].get("value")
            for r in report["rewards"]:
                reg.kpi(day, f"reward.{r['generator']}", r["reward"], r["terms"], conn=conn)
                n += 1
                share = (r["terms"]["SurvivorOutcome"] / total) if total else 0.0
                reg.generator_yield_update(str(r["generator"]),
                                           delta_elogw=float(_f(elogw, 0.0) * share), conn=conn)
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


def run(*, day: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    d = day or today()
    unmeasured: list[dict[str, str]] = []
    cands, discs, ylds, srcs, err = _registry_rows()
    if err:
        unmeasured.append({"what": "registry", "why": err})
    factors, fwhy = factor_similarity()
    if fwhy:
        unmeasured.append({"what": "factor_similarity", "why": fwhy})
    # The corpus is DEDUPED: a second row carrying the same content hash is the same rule, and
    # leaving it in would make the candidate it clones look like its own perfect duplicate.
    against, corpus_counts = corpus(_dedupe(cands))
    sov = sovereign(cands, discs, ylds, day=d, factors=factors, against=against)
    moat = moat_kpis(cands, discs, ylds, srcs, day=d, factors=factors, against=against,
                     unmeasured=unmeasured)
    rew = rewards(cands, discs, ylds, factors=factors, against=against)
    sep = separation_of_powers(yields=ylds)
    report = {
        "at": now(), "day": d, "sovereign": sov, "moat_kpis": moat, "rewards": rew,
        "anti_gaming": anti_gaming(rew), "separation_of_powers": sep,
        "corpus": corpus_counts, "n_candidates": len(cands), "n_discoveries": len(discs),
        "n_generators": len(rew), "lambda": LAMBDA, "gamma": GAMMA,
        "ready_states": list(READY_STATES), "unmeasured": unmeasured,
        "dry_run": dry_run, "elapsed_s": round(time.monotonic() - t0, 2), "law": LAW,
    }
    if not dry_run:
        written, perr = _publish(d, report)
        report["kpi_rows_written"] = written
        if perr:
            unmeasured.append({"what": "kpi_rows", "why": perr})
    else:
        report["kpi_rows_written"] = 0
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the mining layer's one binding objective, measured")
    ap.add_argument("--day", type=str, default=None, help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--dry-run", action="store_true", help="measure, write nothing, record nothing")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = run(day=args.day, dry_run=args.dry_run)
    for name in SOVEREIGN:
        row = rep["sovereign"][name]
        val = "UNMEASURED" if row["day"] is None else f"{row['day']:>12.4f}"
        trail = "UNMEASURED" if row["trailing_7d"] is None else f"{row['trailing_7d']:.4f}"
        print(f"  {name:<34}{val}   7d={trail}")
    print(f"\n{rep['n_candidates']} candidate(s), {rep['n_discoveries']} discovery(ies), "
          f"{rep['n_generators']} generator(s), {len(rep['unmeasured'])} unmeasured, "
          f"{rep['elapsed_s']}s")
    for r in rep["rewards"][:10]:
        print(f"    reward {r['reward']:>10.4f}  {r['generator'][:40]:<42}"
              f"n={r['n_candidates']}")
    sep = rep["separation_of_powers"]
    print(f"  separation of powers: {'OK' if sep['ok'] else 'VIOLATED'} "
          f"({sep['n_checked']} organ(s) checked, {len(sep['violations'])} violation(s))")
    for v in sep["violations"][:10]:
        print(f"    {v['organ']}:{v['line']} writes {v['writes']}")
    if args.dry_run:
        print("--dry-run: nothing written, nothing recorded")
        return 0
    write_report(rep, args.out or OUT)
    print(f"  -> {args.out or OUT}\nYIELD generators={rep['n_generators']} "
          f"kpi_rows={rep['kpi_rows_written']} separation_ok={sep['ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
