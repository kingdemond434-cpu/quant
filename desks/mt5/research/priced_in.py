#!/usr/bin/env python3
"""PRICED-IN-NESS -- event reactions scaled by the market's pre-event implied probability (QG25-26).

WHAT EXISTED (card diff_first: EXISTS_INCOMPLETE). `prediction_markets` stores forecasts BEFORE
resolution (`data/prediction_forecasts.jsonl`) and fits a per-category recalibration;
`event_surprise` measures consensus z and the tape's reaction to it. Nothing joined a pre-event
implied probability to the size of the reaction.

THE NUMBER. For a macro event with a market-implied probability p of the outcome that then
happened or did not:

    surprise_pm = outcome - p_implied            in [-1, 1]

p is RISK-NEUTRAL (measure "Q"): a market price carries a risk premium and a favourite/longshot
bias, so it is not a forecast until it is recalibrated (card QG-ADH-003). Where
`prediction_markets.fit_recalibration` is MEASURED on that category's EARLIER resolved events (only
events resolved before this one -- an expanding fit, never the whole sample), the risk-adjusted
`surprise_pm_adj = outcome - recalibrate(p)` is published beside it, labelled measure
"P_recalibrated"; otherwise that field is UNMEASURED and the raw Q number is not relabelled.

PIT. p_first is the earliest stored snapshot and p_last the latest stored STRICTLY BEFORE the event
instant; a snapshot stored at or after it is the card's named leakage ("using the post-release
market price as implied") and is refused and counted. The surprise is available at
max(event_time, outcome_known_at) (knowable_basis calendar: the release is scheduled).

THE REACTION. Daily close-to-close on the MT5 bars around the event: close of the event's UTC date
(an event at or after 20:00 UTC belongs to the next date: the broker's day closes 21:00-22:00 UTC)
over the previous close, in units of the symbol's own trailing 60-day return sd, averaged over the
event's legs (FX, indices, gold).

CONTRACTS.
  monotone_gain of |surprise_pm| against |reaction| (card falsifier: no monotone relation), raw Q
  and, where measured, recalibrated; and the INCREMENTAL test against the consensus z from
  `event_surprise`: |surprise_pm| against the rank residual of |reaction| on |z| for events where
  both exist (baseline: consensus z).

    python desks/mt5/research/priced_in.py [--days 1200] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_contract as sc  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "priced_in"
SERIES = "ws_priced_in"
REPORT = DESK / "reports" / "PRICED_IN.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
UNMEASURED = "UNMEASURED"
MEASURE = "Q"
CARDS = ["QG25-26"]
FALSIFIER = "No monotone relation between |surprise_pm| and reaction size."
#: Categories the forecast store calls macro events.
MACRO_CATEGORIES = frozenset({"macro", "rates", "fed", "fomc", "cpi", "inflation", "payrolls",
                              "nfp", "jobs", "gdp", "ecb", "boj", "boe", "central_bank"})
#: The legs a macro surprise is read on (card candidates), first listed candidate wins.
LEGS: tuple[tuple[str, ...], ...] = (("EURUSD",), ("USDJPY",), ("XAUUSD", "GOLD"),
                                     ("US500", "SPX500"), ("NAS100", "USTEC"))
#: The cell door's terms-gate key: the desk's own forecast store (prediction_markets venues are
#: read under their labels there), not a held provider.
DATA_SOURCE = "prediction_markets:forecast_store"
VOL_WINDOW = 60
LATE_HOUR_UTC = 20
#: Two stamps within this are the same release (forecast store vs consensus store).
MATCH_WINDOW = timedelta(minutes=90)


def _f(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ============================================================================== the events
def _pm() -> Any:
    from research import prediction_markets as pm
    return pm


def read_forecasts(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or _pm().FORECASTS
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _event_key(r: Mapping[str, Any]) -> str:
    return str(r.get("event_id") or r.get("forecast_id") or "")


def build_events(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """One event per key: p_first, p_last strictly before the event, outcome, category."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        k = _event_key(r)
        if k:
            groups.setdefault(k, []).append(r)
    acc = {"keys": len(groups), "not_macro": 0, "no_event_time": 0, "no_outcome": 0,
           "no_pre_event_snapshot": 0, "post_event_snapshots_refused": 0, "events": 0}
    events: list[dict[str, Any]] = []
    for key, grp in groups.items():
        cat = str(next((r.get("category") for r in grp if r.get("category")), "")).lower()
        if cat not in MACRO_CATEGORIES:
            acc["not_macro"] += 1
            continue
        at = next((t for t in (sc.parse_time(r.get("event_time") or r.get("resolves_at"))
                               for r in grp) if t is not None), None)
        if at is None:
            acc["no_event_time"] += 1
            continue
        outs = [_f(r.get("outcome")) for r in grp if r.get("outcome") is not None]
        outcome = next((o for o in outs if o is not None), None)
        if outcome is None:
            acc["no_outcome"] += 1
            continue
        known = [t for t in (sc.parse_time(r.get("outcome_known_at") or r.get("resolved_at"))
                             for r in grp) if t is not None]
        snaps: list[tuple[datetime, float]] = []
        for r in grp:
            t, p = sc.parse_time(r.get("stored_at")), _f(r.get("p"))
            if t is None or p is None or r.get("outcome") is not None:
                continue
            if t >= at:
                acc["post_event_snapshots_refused"] += 1
                continue
            snaps.append((t, min(max(p, 0.0), 1.0)))
        if not snaps:
            acc["no_pre_event_snapshot"] += 1
            continue
        snaps.sort()
        y = 1.0 if outcome > 0.5 else 0.0
        events.append({"event_id": key, "category": cat, "event_time": at,
                       "available_at": max([at, *known]),
                       "question": str(grp[0].get("question") or "")[:200],
                       "p_first": snaps[0][1], "p_first_at": snaps[0][0],
                       "p_last": snaps[-1][1], "p_last_at": snaps[-1][0], "outcome": y,
                       "surprise_pm": y - snaps[-1][1], "surprise_pm_first": y - snaps[0][1],
                       "symbols": [str(s) for s in grp[0].get("symbols") or []],
                       "measure": MEASURE})
    events.sort(key=lambda e: e["event_time"])
    acc["events"] = len(events)
    return events, acc


#: The expanding recalibration is refitted once this many new resolved events have accrued in a
#: category (each fit still sees ONLY events resolved before the one it adjusts).
REFIT_EVERY = 10


def adjust(events: list[dict[str, Any]]) -> int:
    """Expanding per-category recalibration: each event uses only EARLIER resolved events."""
    pm = _pm()
    n_adj = 0
    fits: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for i, ev in enumerate(events):
        prior = [e for e in events[:i] if e["category"] == ev["category"]
                 and e["available_at"] <= ev["p_last_at"]]
        n_prior, fit = fits.get(ev["category"], (-REFIT_EVERY, {"verdict": UNMEASURED}))
        if len(prior) - n_prior >= REFIT_EVERY or (fit.get("verdict") != "MEASURED"
                                                   and len(prior) >= pm.MIN_FORECASTS
                                                   and len(prior) != n_prior):
            fit = pm.fit_recalibration([e["p_last"] for e in prior],
                                       [e["outcome"] for e in prior])
            fits[ev["category"]] = (len(prior), fit)
        if fit.get("verdict") == "MEASURED":
            p_adj = float(pm.recalibrate(ev["p_last"], fit))
            ev.update({"p_adj": p_adj, "surprise_pm_adj": ev["outcome"] - p_adj,
                       "adj_measure": "P_recalibrated", "adj_fit_n": int(fit["n"])})
            n_adj += 1
        else:
            ev.update({"p_adj": UNMEASURED, "surprise_pm_adj": UNMEASURED,
                       "adj_why": str(fit.get("why") or "")[:120]})
    return n_adj


# ============================================================================== reactions
def reaction_day(at: datetime) -> date:
    d = at.astimezone(UTC).date()
    return d + timedelta(days=1) if at.astimezone(UTC).hour >= LATE_HOUR_UTC else d


def reaction_z(closes: Sequence[tuple[str, float]], day: date) -> float | None:
    """|log close(day) / close(prev)| over the trailing VOL_WINDOW daily-return sd."""
    rows = sorted(closes)
    idx = next((i for i, (d, _) in enumerate(rows) if d == day.isoformat()), None)
    if idx is None or idx < VOL_WINDOW + 1:
        return None
    rets = [math.log(rows[j][1] / rows[j - 1][1]) for j in range(idx - VOL_WINDOW, idx)]
    sd = float(np.std(rets, ddof=1))
    if sd <= 0:
        return None
    return abs(math.log(rows[idx][1] / rows[idx - 1][1])) / sd


def resolve_legs(registry: Mapping[str, Any]) -> list[str]:
    out = []
    for cands in LEGS:
        hit = next((c for c in cands if c.upper() in registry), None)
        if hit:
            out.append(hit)
    return out


def load_registry() -> dict[str, Any]:
    try:
        doc = json.loads(UNIVERSE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k).upper(): v for k, v in doc.items()} if isinstance(doc, dict) else {}


def bars_daily(symbol: str, now: datetime) -> list[tuple[str, float]]:
    try:
        from macro import market_state as ms
        return ms.daily_closes(ms._chart(symbol), now)
    except Exception:
        return []


# ============================================================================== consensus join
def consensus_pairs(now: datetime, days: int) -> list[dict[str, Any]]:
    try:
        from research import event_surprise as es
        pairs, _ = es.store_pairs(days, now)
        cal, _ = es.calendar_pairs(days, now)
        out, _ = es.standardize([*pairs, *cal])
        return out
    except Exception:
        return []


def join_consensus(events: Sequence[dict[str, Any]], pairs: Sequence[Mapping[str, Any]]) -> int:
    stamped = [(t, _f(p.get("z"))) for p in pairs
               if (t := sc.parse_time(p.get("at"))) is not None and _f(p.get("z")) is not None]
    n = 0
    for ev in events:
        near = [(abs((t - ev["event_time"]).total_seconds()), z) for t, z in stamped
                if abs(t - ev["event_time"]) <= MATCH_WINDOW]
        if near:
            ev["consensus_z"] = min(near)[1]
            n += 1
    return n


def _rank(x: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(x, kind="mergesort"), kind="mergesort").astype(float)


# ============================================================================== the organ
def contracts_for(events: Sequence[Mapping[str, Any]], *, min_n: int = 100) -> list[dict[str, Any]]:
    have = [e for e in events if e.get("reaction_z") is not None]
    out = [se.monotone_gain([abs(e["surprise_pm"]) for e in have],
                            [e["reaction_z"] for e in have], engine=ENGINE, cards=CARDS,
                            falsifier=FALSIFIER, min_n=min_n)
           | {"label": "|surprise_pm| (Q) vs |reaction| in own-vol units", "measure": MEASURE}]
    adj = [e for e in have if isinstance(e.get("surprise_pm_adj"), float)]
    out.append(se.monotone_gain([abs(e["surprise_pm_adj"]) for e in adj],
                                [e["reaction_z"] for e in adj], engine=ENGINE,
                                cards=[*CARDS, "QG-ADH-003"], falsifier=FALSIFIER, min_n=min_n)
               | {"label": "|surprise_pm_adj| (recalibrated, P) vs |reaction|",
                  "measure": "P_recalibrated"})
    both = [e for e in have if e.get("consensus_z") is not None]
    if len(both) >= 3:
        rz = _rank(np.asarray([abs(float(e["consensus_z"])) for e in both]))
        rr = _rank(np.asarray([e["reaction_z"] for e in both]))
        X = np.column_stack([np.ones(len(both)), rz])
        beta, *_ = np.linalg.lstsq(X, rr, rcond=None)
        resid = rr - X @ beta
        inc = se.monotone_gain([abs(e["surprise_pm"]) for e in both], resid.tolist(),
                               engine=ENGINE, cards=CARDS, falsifier=FALSIFIER,
                               baseline="consensus z (event_surprise): rank residual of |reaction|"
                                        " on |z|", min_n=min_n)
    else:
        inc = se.contract(engine=ENGINE, cards=CARDS, metric="spearman_rho",
                          baseline="consensus z (event_surprise)", falsifier=FALSIFIER,
                          value=None, baseline_value=0.0, n=len(both), min_n=min_n,
                          why=f"{len(both)} event(s) carry both a pre-event probability and a "
                              "consensus z")
    out.append(inc | {"label": "incremental over consensus z", "measure": MEASURE})
    return out


def run(*, now: datetime, days: int = 1200, forecasts: Sequence[Mapping[str, Any]] | None = None,
        registry: Mapping[str, Any] | None = None,
        closes_fn: Callable[[str, datetime], Sequence[tuple[str, float]]] | None = None,
        consensus: Sequence[Mapping[str, Any]] | None = None, ledger: Any = None,
        lake_root: Path | None = None, contracts_root: Path | None = None,
        report: Path | None = REPORT, dry_run: bool = False, emit_cells: bool = True,
        min_n: int = 100) -> dict[str, Any]:
    rows = list(forecasts) if forecasts is not None else read_forecasts()
    events, acc = build_events(rows)
    events = [e for e in events if e["available_at"] <= now
              and e["event_time"] >= now - timedelta(days=days)]
    n_adj = adjust(events)
    reg = registry if registry is not None else load_registry()
    legs = resolve_legs(reg)
    closes_of = closes_fn or bars_daily
    closes = {s: list(closes_of(s, now)) for s in legs}
    for ev in events:
        syms = [s for s in (ev["symbols"] or legs) if s in closes]
        zs = [z for s in syms if (z := reaction_z(closes[s], reaction_day(ev["event_time"])))
              is not None]
        ev["reaction_z"] = float(np.mean(zs)) if zs else None
        ev["reaction_legs"] = len(zs)
    n_cons = join_consensus(events, consensus if consensus is not None
                            else consensus_pairs(now, days))
    contracts = contracts_for(events, min_n=min_n)
    # ---- lake (one row per availability instant; same-instant events are averaged)
    by_at: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        by_at.setdefault(ev["available_at"].isoformat(), []).append(ev)
    lake_rows = [{"available_time": at, "event_time": grp[0]["event_time"].isoformat(),
                  "source_id": ENGINE,
                  "surprise_pm": float(np.mean([e["surprise_pm"] for e in grp])),
                  "abs_surprise_pm": float(max(abs(e["surprise_pm"]) for e in grp)),
                  "p_last": float(np.mean([e["p_last"] for e in grp])),
                  "p_first": float(np.mean([e["p_first"] for e in grp]))}
                 for at, grp in sorted(by_at.items())]
    lake: Any = {"rows": len(lake_rows), "status": "DRY_RUN" if dry_run else UNMEASURED}
    cells: Any = {"status": UNMEASURED, "why": "no event yet"}
    obs = []
    if lake_rows and not dry_run:
        lake = se.write_lake_series(SERIES, lake_rows, root=lake_root)
    if lake_rows and emit_cells and legs:
        from macro.option_chains import emit_gated
        cells = emit_gated(
            SERIES, ["surprise_pm", "abs_surprise_pm"], legs, data_source=DATA_SOURCE,
            mechanism=("prices move on the unexpected component of news: a macro outcome priced "
                       "at p (prediction market, measure Q) moves FX/indices/gold in proportion "
                       "to |outcome - p|"),
            falsifier=FALSIFIER, generator=ENGINE, sides=(1, -1), dry_run=dry_run)
    if events:
        last = events[-1]
        for s in legs:
            obs.append(sc.make(
                sensor_id=ENGINE, source_id="prediction_markets", metric="surprise_pm",
                entity=s, kind="state", sensor_class="prediction_market_surprise",
                asset_domain="macro_event", value=last["surprise_pm"],
                event_time=last["event_time"], knowable_at=last["available_at"],
                knowable_basis="calendar", received_at=max(now, last["available_at"]),
                attributes={"measure": MEASURE, "event_id": last["event_id"],
                            "p_first": last["p_first"], "p_last": last["p_last"],
                            "outcome": last["outcome"],
                            "surprise_pm_adj": last.get("surprise_pm_adj")}))
    ledger_out: Any = {"status": "DRY_RUN"}
    if not dry_run:
        led = ledger if ledger is not None else sc.SensorLedger()
        ledger_out = led.append(obs, now=now) if obs else {"appended": 0}
        se.publish(ENGINE, contracts, root=contracts_root, extra={"measure": MEASURE})
    doc = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"), "dry_run": dry_run,
           "accounting": acc, "events": len(events), "recalibrated": n_adj,
           "with_reaction": sum(1 for e in events if e.get("reaction_z") is not None),
           "with_consensus_z": n_cons, "legs": legs, "contracts": contracts,
           "verdicts": {v: sum(1 for c in contracts if c.get("verdict") == v)
                        for v in (se.GAIN, se.NO_GAIN, se.UNMEASURED)},
           "lake": lake, "cells": cells, "data_source": DATA_SOURCE, "ledger": ledger_out,
           "measure": MEASURE,
           "latest": [{k: (v.isoformat() if isinstance(v, datetime) else v)
                       for k, v in e.items()} for e in events[-10:]],
           "authority": "NONE"}
    if not dry_run and report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        tmp = report.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        os.replace(tmp, report)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="priced-in-ness of macro events (QG25-26)")
    ap.add_argument("--days", type=int, default=1200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(now=datetime.now(UTC), days=a.days, dry_run=a.dry_run)
    print(json.dumps({k: doc[k] for k in ("at", "events", "recalibrated", "with_reaction",
                                          "with_consensus_z", "verdicts")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
