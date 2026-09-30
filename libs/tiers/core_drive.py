"""THE MODEL CHECKER'S COUNTEREXAMPLES, REPLAYED AGAINST THE REAL decision_core (Tier S layer 31).

`libs/tiers/formal.py` proves an abstract order protocol and prints the shortest trace that breaks
it when a knob is removed; `libs/tiers/failure_worlds.py` does the same for environment faults.
A trace about an abstract model says nothing about the desk until it is driven through the code
that actually decides. This module is that bridge: each counterexample is interpreted as a
concrete scenario, and at every step where the model's protocol makes a decision, the matching
`mt5desk/decision_core.py` function is CALLED with the scenario's inputs -- in a temp directory,
never against a live terminal, never writing anything the desk reads.

The decision points and the core function that owns each one:

    send while the allocator published zero   book_from_allocation(..., zeroed=[sleeve])
                                              -- the sleeve must come back at 0.0 heat
    send for a revoked certificate            load_sleeves_verbose(tmp sleeves.json)
                                              -- a RETIRED row must not be in the roster
                                              (control: the same row LIVE must be)
    resend of an intent after a restart       bar_already_traded(deals, tag)
                                              -- the venue's deal history must show the entry
    decision on a bar stamped after the clock family_bar_due(closed, sig_hour)
                                              -- must refuse a bar later than the decision clock

Each trace ends BLOCKED_BY_CORE (the real code refuses at the step the model broke), CORE_ADMITS
(the real code lets the violating step through -- the guard, if any, lives outside the core),
NO_CORE_DECISION (the violation is a venue act the core never sees) or UNMEASURED (the probe's
control failed, so the refusal could not be attributed). A CORE_ADMITS is an OBLIGATION to
publish, not a verdict on the live gateway, whose adapter layer may hold the missing guard.
"""
from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

SLEEVE = "tier_s_probe_sleeve"
TAG = "tsprobe"


def _probe_zero(core: Any) -> dict[str, Any]:
    book, why = core.book_from_allocation(0.2, {"OTHER": 0.2}, None, certified=True,
                                          why="tier_s core_drive probe", zeroed=[SLEEVE])
    frac = None if book is None else book.get(SLEEVE)
    blocked = frac is not None and float(frac) == 0.0
    return {"function": "book_from_allocation", "blocked": blocked,
            "observed": {"fraction": frac, "why": why}}


def _probe_cert(core: Any, symbol: str) -> dict[str, Any]:
    row = {"name": SLEEVE, "symbol": symbol, "family": "session_range_breakout",
           "timeframe": "H1"}
    with tempfile.TemporaryDirectory(prefix="tier_s_core_drive_") as d:
        p = Path(d) / "sleeves.json"
        p.write_text(json.dumps({"sleeves": [dict(row, status="LIVE")]}), encoding="utf-8")
        control = [s.get("name") for s in core.load_sleeves_verbose(p)[0]]
        p.write_text(json.dumps({"sleeves": [dict(row, status="RETIRED")]}), encoding="utf-8")
        revoked = [s.get("name") for s in core.load_sleeves_verbose(p)[0]]
    if SLEEVE not in control:
        return {"function": "load_sleeves_verbose", "blocked": None,
                "why": f"control failed: the LIVE probe row on {symbol} is not admitted either, "
                       "so a refusal could not be attributed to the revocation"}
    return {"function": "load_sleeves_verbose", "blocked": SLEEVE not in revoked,
            "observed": {"control_admitted": True, "revoked_admitted": SLEEVE in revoked}}


def _probe_resend(core: Any, deals: list[Any]) -> dict[str, Any]:
    hit = core.bar_already_traded(deals, TAG)
    out: dict[str, Any] = {"function": "bar_already_traded", "blocked": hit is not None,
                           "observed": {"deals_in_history": len(deals), "hit": hit}}
    if hit is None:
        out["why"] = ("the first order has not filled, so the venue's deal history holds no "
                      "entry for the tag: a pending order from before the restart is invisible "
                      "to this witness")
    return out


def _probe_future(core: Any) -> dict[str, Any]:
    import pandas as pd
    clock = pd.Timestamp("2026-01-05 09:00", tz="UTC")
    # three closed bars, the last stamped one hour AFTER the decision clock at the signal hour
    idx = pd.DatetimeIndex([clock - pd.Timedelta(hours=1), clock,
                            clock + pd.Timedelta(hours=1)])
    closed = pd.DataFrame({"open": [1.0, 1.0, 1.0], "high": [1.0, 1.0, 1.0],
                           "low": [1.0, 1.0, 1.0], "close": [1.0, 1.0, 1.0]}, index=idx)
    due = core.family_bar_due(closed, int(idx[-1].hour))
    blocked = due is None or pd.Timestamp(due) <= clock
    out: dict[str, Any] = {"function": "family_bar_due", "blocked": blocked,
                           "observed": {"decision_clock": clock.isoformat(),
                                        "bar_returned": None if due is None else str(due)}}
    if not blocked:
        out["why"] = ("family_bar_due takes no clock argument; excluding a bar stamped after "
                      "the decision clock is left to the caller")
    return out


def drive(trace: Iterable[str], core: Any, *, symbol: str = "XAUUSD") -> dict[str, Any]:
    """Replay one counterexample trace through decision_core; stop at the first core refusal."""
    alloc, cert, fills = 1, True, 0
    sends = 0
    snapshot: tuple[int, bool] | None = None
    deals: list[Any] = []
    late = False
    steps: list[dict[str, Any]] = []
    acts = [a for a in trace if a != "init"]
    for i, act in enumerate(acts):
        probes: list[dict[str, Any]] = []
        if act.startswith("publish("):
            alloc = int(act[len("publish("):-1])
        elif act == "revoke_cert":
            cert = False
        elif act in ("feed_late", "feed_skewed"):
            late = True
        elif act == "recheck_ok":
            snapshot = (alloc, cert)
        elif act in ("send", "transmit"):
            a_seen, c_seen = snapshot if (act == "transmit" and snapshot) else (alloc, cert)
            snapshot = None
            if a_seen == 0:
                probes.append(_probe_zero(core))
            elif alloc == 0:
                probes.append({"function": "book_from_allocation", "blocked": False,
                               "why": "the core was consulted before the allocator published "
                                      "zero; the send used that earlier answer"})
            if not c_seen:
                probes.append(_probe_cert(core, symbol))
            elif not cert:
                probes.append({"function": "load_sleeves_verbose", "blocked": False,
                               "why": "the roster was read before the revocation; the send "
                                      "used that earlier roster"})
            if sends > 0:
                probes.append(_probe_resend(core, deals))
            sends += 1
        elif act in ("fill", "late_fill_after_reject", "broker_fills_duplicate"):
            fills += 1
            deals.append(SimpleNamespace(entry=0, comment=TAG, time=1_767_600_000 + i,
                                         ticket=1000 + fills))
        elif act == "reject":
            sends = max(0, sends - 1)
        if late and act in ("decide", "feed_late", "feed_skewed") and not any(
                s.get("function") == "family_bar_due" for st in steps for s in st["probes"]):
            probes.append(_probe_future(core))
        if probes:
            steps.append({"step": i + 1, "action": act, "probes": probes})
            if any(p.get("blocked") is True for p in probes):
                return {"trace": list(trace), "verdict": "BLOCKED_BY_CORE",
                        "blocked_at": {"step": i + 1, "action": act,
                                       "function": next(p["function"] for p in probes
                                                        if p.get("blocked") is True)},
                        "steps": steps}
    probes_all = [p for st in steps for p in st["probes"]]
    if not probes_all:
        verdict = "NO_CORE_DECISION"
    elif any(p.get("blocked") is False for p in probes_all):
        verdict = "CORE_ADMITS"
    else:
        verdict = "UNMEASURED"
    return {"trace": list(trace), "verdict": verdict, "steps": steps}


def drive_all(counterexamples: Iterable[Mapping[str, Any]], core: Any, *,
              symbol: str = "XAUUSD") -> dict[str, Any]:
    """counterexamples: {source, invariant, trace}. Each distinct trace is driven once."""
    rows: list[dict[str, Any]] = []
    seen: dict[tuple[str, ...], dict[str, Any]] = {}
    for c in counterexamples:
        tr = tuple(c.get("trace") or ())
        if not tr:
            continue
        if tr not in seen:
            seen[tr] = drive(tr, core, symbol=symbol)
        r = seen[tr]
        rows.append({"source": c.get("source"), "invariant": c.get("invariant"),
                     "verdict": r["verdict"], "blocked_at": r.get("blocked_at"),
                     "trace": list(tr), "steps": r["steps"]})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    gaps: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r["verdict"] != "CORE_ADMITS":
            continue
        for st in r["steps"]:
            for p in st["probes"]:
                if p.get("blocked") is False:
                    g = gaps.setdefault(p["function"], {"function": p["function"],
                                                       "why": p.get("why"), "invariants": set(),
                                                       "sources": set()})
                    g["invariants"].add(str(r["invariant"]))
                    g["sources"].add(str(r["source"]))
    gap_rows = [{**g, "invariants": sorted(g["invariants"]), "sources": sorted(g["sources"])}
                for g in gaps.values()]
    decided = counts.get("BLOCKED_BY_CORE", 0) + counts.get("CORE_ADMITS", 0)
    return {"traces_driven": len(rows), "distinct_traces": len(seen), "verdicts": counts,
            "blocked_share": (counts.get("BLOCKED_BY_CORE", 0) / decided) if decided else None,
            "core_gaps": sorted(gap_rows, key=lambda g: g["function"]), "rows": rows}


def counterexamples(ablations: Mapping[str, Any],
                    worlds: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every VIOLATED trace of the knob ablations and the minimal failure worlds."""
    out: list[dict[str, Any]] = []
    for label, res in (ablations.get("runs") or {}).items():
        for inv, v in (res.get("invariants") or {}).items():
            if v.get("verdict") == "VIOLATED":
                out.append({"source": f"ablation:{label}", "invariant": inv,
                            "trace": v.get("trace")})
    for m in (worlds or {}).get("minimal_failing_worlds") or []:
        out.append({"source": "world:" + "+".join(m["faults"]), "invariant": m["invariant"],
                    "trace": m["trace"]})
    return out
