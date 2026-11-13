#!/usr/bin/env python3
"""EVERY PRODUCER'S FUNNEL, STAGE BY STAGE: its yield, its named bottleneck, and a RED fence.

    "Millions of hypotheses a day and 100 percent yield; fix every named bottleneck."
                                                     -- BACKLOG row 58, Breadth, 2026-09-30

WHAT WAS ALREADY HERE, AND WHAT WAS NOT. The desk counts its funnel in four places and none of
them answers the row:

    productivity_census   per producer, the lifetime COUNT at every stage -- no yield between
                          stages, no bottleneck, no movement over time.
    check_producer_yield  per producer, cells emitted / unique / sent to the judge in a 24h
                          window, and a desk-wide throughput ratchet -- no per-producer fall.
    bottleneck_law,       ONE desk-wide binding stage. A desk-wide minimum hides every
    conversion_ledger     producer whose own pipe is blocked somewhere else.
    research_productivity

So "which stage loses this producer's output, and has it stopped moving" had no answer for any
one producer. This organ READS the first two (it re-derives nothing from the registry, which the
census already scans) and adds exactly the three things missing:

  1. STAGE-TO-STAGE YIELD per producer over the lifetime funnel

        raw_items -> compiled_cells -> reached_judge -> judged -> certificates
                  -> promotable -> live

     and over the fresh 24h window (cells emitted -> cells sent to the judge). The census's
     `unique_cells` is DISTINCT `grid_cell` -- a docket coordinate such as `fx_exotic|H1|all`,
     shared by thousands of distinct hypotheses -- so it is BREADTH, not a stage: every row still
     goes to the judge. It is published beside the funnel as `distinct_grid_cells` and never
     read as a loss (a first draft did, and named `descendants` a 88% "dedup" bottleneck while
     all 175 of its cells an hour were reaching the judge).
  2. THE BOTTLENECK per producer: the ACTIONABLE transition with the lowest yield (ties broken by
     the most items lost). Two transitions are measured and published but are NEVER named a
     bottleneck, because raising them is not unblocking anything:
        judged -> certificates   the sealed judge's VERDICT. Raising it means moving a bar.
        promotable -> live       forward-clock EVIDENCE accruing; it takes weeks by design.
  3. A RED FENCE with history (`PRODUCER_FUNNEL_STATE.json`), per producer:
        STUCK            items waiting at one stage whose downstream count has not moved for
                         more than 24h (lifetime funnel), or a producer that emitted cells over
                         more than 24h of readings and sent NONE to the judge.
        THROUGHPUT_FELL  cells sent to the judge per hour fell below half of the reading ~24h
                         earlier (disjoint windows), from at least 1 cell/h.
     Every RED producer is routed onto the issue board with its named bottleneck
     (`issue_board.producer_funnel_issues`).

UNMEASURED IS A VERDICT, NEVER A ZERO (L1.28a). An absent or stale input makes every check that
needs it UNMEASURED with the reason; a check without 24h of history is UNMEASURED; the fence is
GREEN only when every check ran on fresh inputs and none fired.

IT MEASURES AND NEVER THROTTLES. Nothing here caps, defers or retires a producer and nothing it
writes is read by a sizing or gating path; it names where output is lost so the loss can be fixed.

    python desks/mt5/research/producer_funnel.py            # one pass, write the artifact
    python desks/mt5/research/producer_funnel.py --json     # and print it
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
REPORTS = BASE / "reports"
OUT = REPORTS / "PRODUCER_FUNNEL.json"
STATE = REPORTS / "PRODUCER_FUNNEL_STATE.json"
CENSUS = REPORTS / "PRODUCTIVITY_CENSUS.json"
YIELD = REPORTS / "PRODUCER_YIELD.json"

UNMEASURED = "UNMEASURED"

#: The census is an hourly leg; past this age its counts describe a desk that no longer exists,
#: so nothing about MOVEMENT may be inferred from it. Its stage counts are still published,
#: stamped with the census's own `at`, because a stale count is information and a blank is not.
CENSUS_MAX_AGE_H = 6.0
#: PRODUCER_YIELD.json is written by the law gate, every few hours on the box (measured from its
#: git history 2026-10-07..11-04: median spacing ~5h, worst ~30h). Past this age it is stale.
YIELD_MAX_AGE_H = 12.0
#: "Stuck for more than 24h" is the row's own number.
STUCK_HOURS = 24.0
#: A handful of rows that can never move (an unbuildable cell, a refused family) must not page
#: forever; the fence is about a PIPE, so it needs a backlog worth a pipe.
STUCK_MIN_ITEMS = 10
#: Throughput fell: the latest 24h window against the reading 24h earlier (a disjoint window).
THROUGHPUT_FALL_FRACTION = 0.5
THROUGHPUT_MIN_PRIOR_PER_H = 1.0
PRIOR_WINDOW_H = (18.0, 30.0)
#: How long yield readings are kept. Two days is all the checks need; a week lets a reader see
#: the trend without the state file growing past a few hundred kilobytes.
KEEP_READINGS_H = 24.0 * 8

#: The lifetime funnel: (stage, census funnel key). `raw_items` is resolved per producer below.
LIFETIME_STAGES: tuple[tuple[str, str], ...] = (
    ("raw_items", "raw_mechanism_claims"),
    ("compiled_cells", "raw_cells"),
    ("reached_judge", "cells_reached_judge"),
    ("judged", "cells_judged"),
    ("certificates", "certificates"),
    ("promotable", "forward_enrolled"),
    ("live", "live_contribution"),
)
#: The kind of each transition, keyed by its INPUT stage. Only ACTIONABLE kinds may be named a
#: bottleneck; `verdict` and `evidence` are published with their yield and why they are excluded.
TRANSITION_KIND: dict[str, str] = {
    "raw_items": "compile",
    "compiled_cells": "reach",
    "reached_judge": "judge_queue",
    "judged": "verdict",
    "certificates": "enrolment",
    "promotable": "evidence",
    # window funnel
    "emitted": "reach",
}
ACTIONABLE = frozenset({"compile", "reach", "judge_queue", "enrolment"})
#: Transitions whose lack of movement is a stuck PIPE (lifetime funnel).
STUCK_TRANSITIONS: tuple[str, ...] = ("raw_items", "compiled_cells", "reached_judge",
                                      "certificates")
EXCLUDED_WHY = {
    "verdict": "the sealed judge's verdict: raising this yield means moving a bar, never "
               "unblocking a pipe",
    "evidence": "forward-clock evidence accrues over weeks by design; a clock is not a queue",
}
WINDOW_STAGES: tuple[tuple[str, str], ...] = (
    ("emitted", "cells_emitted_per_hour"),
    ("to_judge", "cells_to_judge_per_hour"),
)
#: Read beside the window funnel as breadth (distinct grid cells per hour), never as a stage.
WINDOW_BREADTH = "unique_cells_per_hour"
#: What one yield reading stores per producer, in this order: [emitted, distinct, to_judge].
READING_FIELDS: tuple[str, ...] = ("cells_emitted_per_hour", WINDOW_BREADTH,
                                   "cells_to_judge_per_hour")


# ------------------------------------------------------------------------------------ helpers

def _now() -> datetime:
    return datetime.now(UTC)


def _parse(stamp: Any) -> datetime | None:
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _age_h(stamp: Any, now: datetime) -> float | None:
    dt = _parse(stamp)
    return None if dt is None else round((now - dt).total_seconds() / 3600.0, 3)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _key(v: Any) -> str:
    return str(v or "").strip().lower()


def _input(path: Path, stamp_field: str, max_age_h: float, now: datetime) -> dict[str, Any]:
    """One input's document and its verdict: MEASURED, STALE or UNMEASURED, always with why."""
    doc = _read(path)
    rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    if not isinstance(doc, dict):
        return {"path": rel, "status": UNMEASURED, "doc": None,
                "why": f"{rel} is absent or unreadable on this host"}
    at = doc.get(stamp_field)
    age = _age_h(at, now)
    if age is None:
        return {"path": rel, "status": UNMEASURED, "doc": doc, "at": at,
                "why": f"{rel} carries no readable `{stamp_field}` stamp"}
    if age > max_age_h:
        return {"path": rel, "status": "STALE", "doc": doc, "at": at, "age_h": age,
                "why": f"{rel} is {age:.1f}h old (stamp {at}) against a {max_age_h:g}h limit: "
                       f"its producer has stopped writing it, so no movement can be read "
                       f"from it"}
    return {"path": rel, "status": "MEASURED", "doc": doc, "at": at, "age_h": age, "why": ""}


# ------------------------------------------------------------------------------ yield + bottleneck

def stage_yields(stages: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Every adjacent transition: in, out, yield, items lost, kind. UNMEASURED where a side is."""
    out: list[dict[str, Any]] = []
    for (a, va), (b, vb) in zip(stages, stages[1:], strict=False):
        kind = TRANSITION_KIND.get(a, "compile")
        row: dict[str, Any] = {"from": a, "to": b, "kind": kind, "in": va, "out": vb}
        na, nb = _num(va), _num(vb)
        if na is None or nb is None:
            row["yield"] = UNMEASURED
            row["why"] = f"{a if na is None else b} is UNMEASURED"
        elif na <= 0:
            row["yield"] = UNMEASURED
            row["why"] = f"nothing arrived at {a}, so its yield is undefined (not zero)"
        else:
            row["yield"] = round(nb / na, 6)
            row["lost"] = round(max(0.0, na - nb), 4)
        if kind not in ACTIONABLE:
            row["excluded_from_bottleneck"] = EXCLUDED_WHY.get(kind, kind)
        out.append(row)
    return out


def bottleneck(transitions: list[dict[str, Any]], first: tuple[str, Any]) -> dict[str, Any]:
    """The single worst ACTIONABLE stage, or why there is none.

    Rule: among actionable transitions whose yield is measured, the lowest yield wins and the
    tie-break is the most items lost. A producer with nothing at its first stage has no pipe to
    be blocked -- it is NO_OUTPUT, the producer-yield fence's DEAD, named here so it is not
    mistaken for a clean pass.
    """
    name, v = first
    n = _num(v)
    if n is None:
        return {"stage": UNMEASURED, "why": f"{name} is UNMEASURED"}
    if n <= 0:
        return {"stage": name, "verdict": "NO_OUTPUT",
                "why": f"nothing at {name}: the producer emits nothing, so no later stage can "
                       f"bind (scripts/check_producer_yield.py owns DEAD/owing)"}
    cand = [t for t in transitions if t["kind"] in ACTIONABLE and isinstance(t["yield"], float)]
    if not cand:
        return {"stage": UNMEASURED,
                "why": "no actionable transition has a measured yield"}
    worst = min(cand, key=lambda t: (t["yield"], -float(t.get("lost") or 0.0)))
    return {"stage": worst["from"], "to": worst["to"], "kind": worst["kind"],
            "yield": worst["yield"], "lost": worst.get("lost"),
            "why": (f"{worst['from']} -> {worst['to']} converts {worst['yield']:.4g} "
                    f"({worst.get('lost')} lost): the lowest actionable yield in this "
                    f"producer's funnel")}


def lifetime_stages(funnel: dict[str, Any]) -> tuple[list[tuple[str, Any]], str]:
    """The seven lifetime stages from a census funnel, and how `raw_items` was resolved."""
    vals: list[tuple[str, Any]] = []
    for stage, key in LIFETIME_STAGES:
        v = funnel.get(key, UNMEASURED)
        if isinstance(v, dict):          # the census nests an UNMEASURED verdict with its why
            v = UNMEASURED
        vals.append((stage, v))
    claims = _num(vals[0][1])
    if claims is None or claims <= 0:
        # A generator mints cells directly: it has no claims stage, and reading its zero claims
        # as a 0% compile yield would accuse every generator on the desk of a stage it lacks.
        vals[0] = ("raw_items", vals[1][1])
        basis = "raw_cells (the producer mints cells directly; no claims stage)"
    else:
        basis = "raw_mechanism_claims"
    return vals, basis


# ----------------------------------------------------------------------------------- the fence

def _readings_update(state: dict[str, Any], yinp: dict[str, Any],
                     now: datetime) -> list[dict[str, Any]]:
    readings = [r for r in state.get("yield_readings") or [] if isinstance(r, dict)]
    if yinp["status"] == "MEASURED":
        doc = yinp["doc"]
        rows = ((doc.get("cells_owed") or {}).get("producers") or [])
        rates: dict[str, list[float]] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            vals = [_num(r.get(k)) or 0.0 for k in READING_FIELDS]
            if any(vals):
                rates[_key(r.get("key") or r.get("producer"))] = vals
        at = str(yinp["at"])
        if not any(r.get("at") == at for r in readings):
            readings.append({"at": at, "rates": rates})
    cutoff = now - timedelta(hours=KEEP_READINGS_H)
    readings = [r for r in readings if (_parse(r.get("at")) or cutoff) > cutoff]
    readings.sort(key=lambda r: str(r.get("at")))
    return readings


def _census_update(state: dict[str, Any], cinp: dict[str, Any],
                   rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per producer per stage: [count, since], where `since` is the census stamp at which the
    count was first seen at its current value. Advanced only by a NEW census reading."""
    prev = state.get("census") if isinstance(state.get("census"), dict) else {}
    if cinp["status"] not in ("MEASURED", "STALE") or prev.get("at") == cinp.get("at"):
        return prev or {}
    at = str(cinp["at"])
    old = prev.get("producers") if isinstance(prev.get("producers"), dict) else {}
    cur: dict[str, dict[str, list[Any]]] = {}
    for row in rows:
        stages = {s: v for s, v in row["_lifetime"] if _num(v) is not None}
        if not any(_num(v) for v in stages.values()):
            continue
        k = row["key"]
        o = old.get(k) or {}
        entry: dict[str, list[Any]] = {}
        for s, v in stages.items():
            was = o.get(s)
            if isinstance(was, list) and len(was) == 2 and _num(was[0]) == _num(v):
                entry[s] = [v, was[1]]
            else:
                entry[s] = [v, at]
        cur[k] = entry
    return {"at": at, "producers": cur}


def _prior_reading(readings: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    lo, hi = PRIOR_WINDOW_H
    best: tuple[float, dict[str, Any]] | None = None
    for r in readings:
        age = _age_h(r.get("at"), now)
        if age is None or not lo <= age <= hi:
            continue
        d = abs(age - 24.0)
        if best is None or d < best[0]:
            best = (d, r)
    return None if best is None else best[1]


def _window_streak(readings: list[dict[str, Any]], key: str, pred: Any) -> float | None:
    """Hours the predicate has held over consecutive readings ending at the latest one."""
    if not readings:
        return None
    run: list[dict[str, Any]] = []
    for r in reversed(readings):
        vals = (r.get("rates") or {}).get(key)
        if vals is None or not pred(vals):
            break
        run.append(r)
    if not run:
        return 0.0
    a, b = _parse(run[-1].get("at")), _parse(run[0].get("at"))
    return None if a is None or b is None else (b - a).total_seconds() / 3600.0


def build(now: datetime | None = None, state: dict[str, Any] | None = None) -> tuple[
        dict[str, Any], dict[str, Any]]:
    """The whole pass: (artifact, new state). Pure apart from reading the two inputs."""
    now = now or _now()
    state = state if isinstance(state, dict) else (_read(STATE) or {})
    cinp = _input(CENSUS, "at", CENSUS_MAX_AGE_H, now)
    yinp = _input(YIELD, "generated_utc", YIELD_MAX_AGE_H, now)

    # ---------------------------------------------------------------- per-producer funnels
    rows: dict[str, dict[str, Any]] = {}
    cdoc = cinp.get("doc") or {}
    for p in cdoc.get("producers") or []:
        if not isinstance(p, dict):
            continue
        k = _key(p.get("key") or p.get("producer"))
        if not k:
            continue
        stages, basis = lifetime_stages(p.get("funnel") or {})
        ub = (p.get("funnel") or {}).get("unique_cells", UNMEASURED)
        rows[k] = {"producer": p.get("producer") or k, "key": k, "kind": p.get("kind"),
                   "clock": p.get("clock"), "_lifetime": stages, "raw_items_basis": basis,
                   "_breadth": ub if _num(ub) is not None else UNMEASURED}
    ydoc = yinp.get("doc") or {}
    for p in ((ydoc.get("cells_owed") or {}).get("producers") or []):
        if not isinstance(p, dict):
            continue
        k = _key(p.get("key") or p.get("producer"))
        if not k:
            continue
        row = rows.setdefault(k, {"producer": p.get("producer") or k, "key": k,
                                  "kind": None, "clock": p.get("clock"),
                                  "_lifetime": None, "raw_items_basis": None})
        row["_window"] = [(s, p.get(f, UNMEASURED)) for s, f in WINDOW_STAGES]
        row["_window_breadth"] = p.get(WINDOW_BREADTH, UNMEASURED)

    readings = _readings_update(state, yinp, now)
    census_state = _census_update(state, cinp, list(r for r in rows.values()
                                                    if r.get("_lifetime")))
    prior = _prior_reading(readings, now) if yinp["status"] == "MEASURED" else None
    window_hist_h = None
    if readings:
        a, b = _parse(readings[0].get("at")), _parse(readings[-1].get("at"))
        window_hist_h = None if a is None or b is None else (b - a).total_seconds() / 3600.0

    # ------------------------------------------------------------------ the checks' verdicts
    checks: dict[str, dict[str, Any]] = {}
    if cinp["status"] != "MEASURED":
        checks["stuck_lifetime"] = {"status": UNMEASURED, "why": cinp["why"]}
    else:
        span = _age_h(min((v[1] for e in (census_state.get("producers") or {}).values()
                           for v in e.values()), default=None), now)
        if span is None or span < STUCK_HOURS:
            checks["stuck_lifetime"] = {
                "status": UNMEASURED,
                "why": f"census history spans {span or 0:.1f}h; {STUCK_HOURS:g}h are needed "
                       f"before a count can be said not to have moved"}
        else:
            checks["stuck_lifetime"] = {"status": "MEASURED", "history_h": span}
    if yinp["status"] != "MEASURED":
        why = yinp["why"]
        checks["stuck_window"] = {"status": UNMEASURED, "why": why}
        checks["throughput_fell"] = {"status": UNMEASURED, "why": why}
    else:
        if window_hist_h is None or window_hist_h < STUCK_HOURS:
            checks["stuck_window"] = {
                "status": UNMEASURED,
                "why": f"{len(readings)} yield reading(s) spanning {window_hist_h or 0:.1f}h; "
                       f"{STUCK_HOURS:g}h are needed"}
        else:
            checks["stuck_window"] = {"status": "MEASURED", "history_h": round(window_hist_h, 2)}
        if prior is None:
            checks["throughput_fell"] = {
                "status": UNMEASURED,
                "why": f"no yield reading {PRIOR_WINDOW_H[0]:g}-{PRIOR_WINDOW_H[1]:g}h old to "
                       f"compare the current window against"}
        else:
            checks["throughput_fell"] = {"status": "MEASURED", "prior_at": prior.get("at")}

    # ------------------------------------------------------------------- per-producer verdicts
    published: list[dict[str, Any]] = []
    red: list[dict[str, Any]] = []
    by_stage: dict[str, int] = {}
    n_silent = 0
    cprod = census_state.get("producers") or {}
    for k, row in sorted(rows.items()):
        out: dict[str, Any] = {"producer": row["producer"], "key": k, "kind": row.get("kind"),
                               "clock": row.get("clock")}
        life = row.get("_lifetime")
        anything = False
        if life:
            tr = stage_yields(life)
            out["lifetime"] = {"as_of": cinp.get("at"), "census_status": cinp["status"],
                               "raw_items_basis": row.get("raw_items_basis"),
                               "stages": dict(life),
                               "distinct_grid_cells": row.get("_breadth", UNMEASURED),
                               "transitions": tr,
                               "bottleneck": bottleneck(tr, life[0])}
            anything = anything or any(_num(v) for _, v in life)
        win = row.get("_window")
        if win:
            tr = stage_yields(win)
            out["window_24h"] = {"as_of": yinp.get("at"), "per_hour": dict(win),
                                 "distinct_grid_cells_per_hour": row.get("_window_breadth"),
                                 "transitions": tr, "bottleneck": bottleneck(tr, win[0])}
            anything = anything or any(_num(v) for _, v in win)
        # THE HEADLINE BOTTLENECK: the fresh window's when it has output (it describes the hour),
        # else the lifetime funnel's. Its basis is always named.
        wb = (out.get("window_24h") or {}).get("bottleneck") or {}
        lb = (out.get("lifetime") or {}).get("bottleneck") or {}
        if wb and wb.get("stage") not in (UNMEASURED,) and wb.get("verdict") != "NO_OUTPUT":
            out["bottleneck"] = {**wb, "basis": "window_24h"}
        elif lb:
            out["bottleneck"] = {**lb, "basis": "lifetime"}
        elif wb:
            out["bottleneck"] = {**wb, "basis": "window_24h"}
        else:
            out["bottleneck"] = {"stage": UNMEASURED, "why": "no input names this producer",
                                 "basis": None}

        reasons: list[dict[str, Any]] = []
        # STUCK on the lifetime funnel: items waiting, downstream count unmoved for > 24h.
        if checks["stuck_lifetime"]["status"] == "MEASURED" and life:
            ent = cprod.get(k) or {}
            vals = dict(life)
            for frm in STUCK_TRANSITIONS:
                idx = [s for s, _ in life].index(frm)
                to = life[idx + 1][0]
                a, b = _num(vals.get(frm)), _num(vals.get(to))
                if a is None or b is None or a - b < STUCK_MIN_ITEMS:
                    continue
                since = (ent.get(to) or [None, None])[1]
                h = _age_h(since, now)
                if h is not None and h > STUCK_HOURS:
                    reasons.append({"check": "STUCK", "stage": frm, "to": to,
                                    "waiting": int(a - b), "hours_unmoved": round(h, 1),
                                    "why": f"{int(a - b)} item(s) at {frm} and {to} has not "
                                           f"moved for {h:.1f}h"})
        # STUCK on the window: cells emitted for > 24h and none unique / none sent to the judge.
        if checks["stuck_window"]["status"] == "MEASURED" and win:
            h = _window_streak(readings, k, lambda v: v[0] > 0 and v[2] <= 0)
            if h is not None and h > STUCK_HOURS:
                reasons.append({"check": "STUCK", "stage": "emitted", "to": "to_judge",
                                "hours_unmoved": round(h, 1),
                                "why": f"cells emitted across {h:.1f}h of consecutive readings "
                                       f"and none sent to the judge"})
        # THROUGHPUT FELL against the disjoint window 24h earlier.
        if checks["throughput_fell"]["status"] == "MEASURED" and prior is not None:
            pv = (prior.get("rates") or {}).get(k)
            cur = _num(dict(win or []).get("to_judge")) if win else 0.0
            before = float(pv[2]) if isinstance(pv, list) and len(pv) == 3 else 0.0
            cur = cur or 0.0
            if (before >= THROUGHPUT_MIN_PRIOR_PER_H
                    and cur < before * THROUGHPUT_FALL_FRACTION):
                reasons.append({"check": "THROUGHPUT_FELL", "stage": "to_judge",
                                "per_hour_now": round(cur, 4),
                                "per_hour_prior": round(before, 4),
                                "prior_at": prior.get("at"),
                                "why": f"cells sent to the judge fell to {cur:.4g}/h from "
                                       f"{before:.4g}/h at {prior.get('at')} (floor "
                                       f"{THROUGHPUT_FALL_FRACTION:g}x)"})
        if reasons:
            out["verdict"] = "RED"
            out["red"] = reasons
            red.append(out)
        if anything or reasons:
            stage = str(out["bottleneck"].get("stage"))
            by_stage[stage] = by_stage.get(stage, 0) + 1
            published.append(out)
        else:
            n_silent += 1

    def _lost(r: dict[str, Any]) -> float:
        return float(r["bottleneck"].get("lost") or 0.0) if r["bottleneck"].get(
            "basis") == "window_24h" else 0.0

    ranking = sorted((r for r in published if _lost(r) > 0), key=lambda r: -_lost(r))
    falls = sorted((x | {"producer": r["producer"], "key": r["key"]}
                    for r in red for x in r["red"] if x["check"] == "THROUGHPUT_FELL"),
                   key=lambda x: -(x["per_hour_prior"] - x["per_hour_now"]))
    biggest: dict[str, Any] | None = None
    if falls and (not ranking or falls[0]["per_hour_prior"] - falls[0]["per_hour_now"]
                  >= _lost(ranking[0])):
        f = falls[0]
        biggest = {"producer": f["producer"], "key": f["key"], "check": "THROUGHPUT_FELL",
                   "stage": "to_judge", "cells_per_hour_lost":
                       round(f["per_hour_prior"] - f["per_hour_now"], 4), "why": f["why"]}
    elif ranking:
        r = ranking[0]
        biggest = {"producer": r["producer"], "key": r["key"], "check": "BOTTLENECK",
                   "stage": r["bottleneck"]["stage"], "to": r["bottleneck"].get("to"),
                   "cells_per_hour_lost": _lost(r), "why": r["bottleneck"].get("why")}

    unmeasured = {c: v["why"] for c, v in checks.items() if v["status"] != "MEASURED"}
    status = "RED" if red else (UNMEASURED if unmeasured else "GREEN")
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "status": status,
        "law": ("EVERY PRODUCER'S FUNNEL IS MEASURED STAGE BY STAGE, ITS WORST ACTIONABLE STAGE "
                "IS NAMED, AND A PRODUCER STUCK AT ONE STAGE FOR MORE THAN 24H OR WHOSE "
                "THROUGHPUT HALVED IS RED ON THE ISSUE BOARD. A missing stage is UNMEASURED, "
                "never zero. This organ measures and unblocks; it throttles nothing."),
        "host": os.environ.get("COMPUTERNAME") or platform.node(),
        "inputs": {"census": {k: v for k, v in cinp.items() if k != "doc"},
                   "producer_yield": {k: v for k, v in yinp.items() if k != "doc"}},
        "checks": checks,
        "unmeasured": unmeasured,
        "thresholds": {"stuck_hours": STUCK_HOURS, "stuck_min_items": STUCK_MIN_ITEMS,
                       "throughput_fall_fraction": THROUGHPUT_FALL_FRACTION,
                       "throughput_min_prior_per_h": THROUGHPUT_MIN_PRIOR_PER_H,
                       "census_max_age_h": CENSUS_MAX_AGE_H,
                       "yield_max_age_h": YIELD_MAX_AGE_H},
        "n_producers": len(rows),
        "n_published": len(published),
        "n_no_output_anywhere": n_silent,
        "n_red": len(red),
        "bottleneck_by_stage": dict(sorted(by_stage.items(), key=lambda kv: -kv[1])),
        "biggest_bottleneck": biggest or {"stage": UNMEASURED,
                                          "why": "no producer has a measured window loss or a "
                                                 "measured throughput fall"},
        "bottleneck_ranking": [
            {"producer": r["producer"], "key": r["key"], "stage": r["bottleneck"]["stage"],
             "to": r["bottleneck"].get("to"), "yield": r["bottleneck"].get("yield"),
             "cells_per_hour_lost": _lost(r)} for r in ranking[:40]],
        "throughput_falls": falls[:40],
        "red": [{"producer": r["producer"], "key": r["key"], "bottleneck": r["bottleneck"],
                 "red": r["red"]} for r in red],
        "producers": published,
        "sources": {
            "lifetime": "desks/mt5/reports/PRODUCTIVITY_CENSUS.json producers[].funnel "
                        "(read, never re-derived from the registry)",
            "window_24h": "desks/mt5/reports/PRODUCER_YIELD.json cells_owed.producers[] "
                          "(per-hour rates over the law gate's 24h registry window)",
            "history": "desks/mt5/reports/PRODUCER_FUNNEL_STATE.json (this organ's own)",
        },
    }
    new_state = {"at": doc["at"], "yield_readings": readings, "census": census_state}
    return doc, new_state


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc, state = build()
    if not a.no_write:
        _write(STATE, state)
        _write(OUT, doc)
        try:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from libs.ops.events import emit
            emit("producer_funnel", status=doc["status"], n_red=doc["n_red"],
                 n_published=doc["n_published"],
                 biggest=str(doc["biggest_bottleneck"].get("producer")))
        except Exception:
            pass  # the events log is a convenience; the artifact is the record
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        b = doc["biggest_bottleneck"]
        print(f"producer_funnel: {doc['status']} -- {doc['n_red']} RED of "
              f"{doc['n_published']} producers with output; biggest bottleneck "
              f"{b.get('producer')} at {b.get('stage')} ({b.get('cells_per_hour_lost')}/h) -> "
              f"{OUT}")
        for c, why in doc["unmeasured"].items():
            print(f"  UNMEASURED {c}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
