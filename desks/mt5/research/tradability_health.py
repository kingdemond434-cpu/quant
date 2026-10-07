#!/usr/bin/env python3
"""TRADABILITY HEALTH -- is each LIVE/STANDBY sleeve still forward-operationally tradable?

    python desks/mt5/research/tradability_health.py             # writes the report
    python desks/mt5/research/tradability_health.py --dry-run   # prints, writes nothing

Artifact: desks/mt5/reports/TRADABILITY_HEALTH.json, hourly (leg `tradability_health`).

WHY THIS EXISTS (Roman / Quant Guild directive item 28, completion audit 2026-10-06 repair #13).
The desk certifies HISTORICAL PROFITABILITY (the gauntlet) and watches FORWARD PERFORMANCE (the
clocks, `decay_monitor`), but it had no single artifact that says, per live sleeve, whether the
conditions the edge was certified under still hold: are the features it reads still distributed
the way they were, is it trading the spec research certified, is the venue charging what the
model charged, is execution filling the way the twin modelled, is the market in a state the
sleeve has evidence for, how much cost headroom is left, and what does the recent forward record
say. "Profitable" and "tradable" are different axes; this is the second one.

DIFF-FIRST: EVERY FIELD IS ANOTHER ORGAN'S READING, NOTHING IS RECOMPUTED HERE.

    feature_drift            reports/DRIFT.json `per_symbol[sym].hazard_max` (drift_monitor, daily),
                             mapped by `drift_monitor.feature_drift` -- that organ's own function
    parameter_drift          reports/RESEARCH_LIVE_IDENTITY.json (research_live_identity, hourly):
                             fields where the traded spec differs from the certified one; the
                             promoter's `certificate_drift` flag on the row when that is absent
    cost_drift               reports/COST_TRUTH.json `symbols[].compare` (cost_truth): the venue's
                             quoted spread against the spread the model charges
    execution_drift          reports/EXECUTION_TWIN.json `recalibration.symbols` (execution_twin,
                             hourly), mapped by `drift_monitor.cost_drift` / `fill_drift`
    regime_occupancy         reports/REGIME_ROUTER.json (regime_router, hourly): the share of the
                             sleeve's evidence taken in the state the desk is in NOW, and
                             P(alpha > 0 | that state)
    capacity_drift           reports/CAPACITY_FRONTIER.json (the cost multiple each mechanism dies
                             at against its symbol's intraday spread widening), with
                             reports/CAPACITY.json's floor reading beside it
    recent_forward_posterior reports/POSTERIOR_ALPHA.json (posterior_alpha, hourly): the NIG
                             posterior P(mu > 0) on the sleeve's own forward record, with
                             data/decay_live.json's FADE/RETIRE verdict beside it

ONE RULER. Each field is mapped onto `libs.research.perishability`'s [0, 1] pressure ruler -- the
same one `drift_monitor.hazard_by_sleeve` uses -- so "how far toward gone" means the same thing
here as in the hazard the allocator reads. A field that cannot be read is the literal UNMEASURED
with its reason (L1.28a): an absent artifact, a stale one, a sleeve the organ did not cover, too
few observations. UNMEASURED never averages in as a calm zero and never yields HEALTHY.

THE VERDICT (`verdict_of`, the rule stated once, in code):

    BROKEN      a STRUCTURAL field (parameter, cost, execution, feature drift or the forward
                posterior) is at full pressure (>= BROKEN_AT)
    DEGRADING   any field at or above DEGRADING_AT (a regime or capacity field at full pressure
                is DEGRADING, never BROKEN: both are conditions that come and go, not a defect
                in the edge)
    HEALTHY     nothing above the lines, at least MIN_MEASURED fields measured, and the forward
                posterior among them -- a sleeve whose recent forward record is unread is not
                healthy, whatever else is quiet
    UNMEASURED  otherwise: too little was readable to say

IT SIZES NOTHING AND VETOES NOTHING. GROWTH GOVERNANCE Rule 1: a reduction must first prove it
raises robust forward E[log W]; this proves nothing of the kind, so it reduces nothing. Its
reader is the lifecycle's REPLACEMENT half: `hazard_engine` attaches each live sleeve's verdict to
its card and queues a `successor_search` for every DEGRADING / BROKEN sleeve -- more independent
bets inside the same heat, started while the incumbent is still earning. The kill stays with
`decay_monitor` on its unchanged bars.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import perishability as ph  # noqa: E402
from research import decay_monitor as dm  # noqa: E402
from research import drift_monitor as dmon  # noqa: E402

REPORTS = BASE / "reports"
OUT = REPORTS / "TRADABILITY_HEALTH.json"
SLEEVES = dm.SLEEVES_FILE
DECAY_LIVE = dm.OUT
DRIFT = dmon.REPORT
EXECUTION_TWIN = dmon.EXECUTION_TWIN
#: Mirrored, not imported: these organs import heavy or terminal-side modules at import time
#: (capacity imports decision_core). Pinned equal to each organ's own constant by
#: desks/mt5/tests/test_tradability_health.py, so a moved artifact fails a test, not this report.
IDENTITY = REPORTS / "RESEARCH_LIVE_IDENTITY.json"
COST_TRUTH = REPORTS / "COST_TRUTH.json"
REGIME_ROUTER = REPORTS / "REGIME_ROUTER.json"
CAPACITY = REPORTS / "CAPACITY.json"
CAPACITY_FRONTIER = REPORTS / "CAPACITY_FRONTIER.json"
POSTERIOR = REPORTS / "POSTERIOR_ALPHA.json"

SCHEMA = "tradability-health/1"
UNMEASURED = "UNMEASURED"
HEALTHY, DEGRADING, BROKEN = "HEALTHY", "DEGRADING", "BROKEN"
VERDICTS = (HEALTHY, DEGRADING, BROKEN, UNMEASURED)
#: Report order: the sleeves a reader must act on first.
_SEVERITY = {BROKEN: 0, DEGRADING: 1, UNMEASURED: 2, HEALTHY: 3}
FIELDS: tuple[str, ...] = ("feature_drift", "parameter_drift", "cost_drift", "execution_drift",
                           "regime_occupancy", "capacity_drift", "recent_forward_posterior")
#: Fields whose full pressure is a defect in the edge itself. Regime occupancy and capacity are
#: conditions the market moves in and out of: they can say DEGRADING, never BROKEN.
STRUCTURAL: frozenset[str] = frozenset({"feature_drift", "parameter_drift", "cost_drift",
                                        "execution_drift", "recent_forward_posterior"})
#: The roster states this report judges -- the same set `hazard_engine.collect_alphas` puts on
#: lane `live`. Pinned equal by the test so the two readers cannot drift apart again.
ROSTER_STATES: tuple[str, ...] = ("LIVE", "STANDBY")
DEGRADING_AT = 0.5
BROKEN_AT = 1.0
#: The promoter's `certificate_drift` flag, read only when the identity join has no row.
CERT_DRIFT_PRESSURE = DEGRADING_AT
#: Measured fields before silence may be called HEALTHY -- the perishability hazard's own bar.
MIN_MEASURED = ph.HAZARD_MIN_CHANNELS
#: P(alpha > 0) mapped onto the ruler: at or above P_CALM there is no pressure; at or below
#: P_GONE the posterior is as sure the edge is absent as `posterior_alpha`'s credible bar (0.90)
#: is sure it is present.
P_CALM, P_GONE = 0.5, 0.1
#: How old each input may be before it is a statement about a desk that no longer exists. The
#: hourly organs get six passes; drift_monitor runs on the daily chain; the capacity frontier
#: has no clock of its own (measured 2026-10-06: no scheduler names it), so a week.
LEASE_H: dict[str, float | None] = {"sleeves": None, "decay_live": 36.0, "drift": 36.0,
                             "identity": 6.0, "cost_truth": 6.0, "execution_twin": 6.0,
                             "regime_router": 6.0, "capacity": 6.0, "capacity_frontier": 168.0,
                             "posterior": 6.0}
_TIME_KEYS = ("generated_utc", "generated_at", "at", "checked_at", "swept_at")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _ts(x: Any) -> datetime | None:
    if not x:
        return None
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


# ------------------------------------------------------------------------------------- sources
class Source:
    """One input artifact: its path, whether it was read, its own as-of time and its age."""

    def __init__(self, key: str, path: Path, now: datetime) -> None:
        self.key, self.path = key, path
        self.doc: Any = None
        self.as_of: str | None = None
        self.basis = "absent"
        self.why = ""
        try:
            self.doc = json.loads(path.read_text("utf-8-sig"))
        except FileNotFoundError:
            self.why = f"{self._rel()} is absent on this host"
        except (OSError, ValueError) as exc:
            self.why = f"{self._rel()} unreadable ({type(exc).__name__})"
        if self.doc is not None:
            stamp = next((self.doc.get(k) for k in _TIME_KEYS
                          if isinstance(self.doc, dict) and self.doc.get(k)), None)
            t = _ts(stamp)
            self.basis = "artifact" if t else "mtime"
            if t is None:
                try:
                    t = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                except OSError:
                    t = None
            self.as_of = t.isoformat(timespec="seconds") if t else None
            age = (now - t).total_seconds() / 3600.0 if t else None
            self.age_h = round(age, 3) if age is not None else None
            lease = LEASE_H.get(key, 6.0)
            if age is not None and lease is not None and age > lease:
                self.why = (f"{self._rel()} is {age:.1f}h old, past its {lease:g}h lease: a "
                            f"reading of a desk that no longer exists")
                self.doc = None
        else:
            self.age_h = None

    def _rel(self) -> str:
        try:
            return self.path.relative_to(ROOT).as_posix()
        except ValueError:
            return str(self.path)

    @property
    def ok(self) -> bool:
        return isinstance(self.doc, dict)

    def card(self) -> dict[str, Any]:
        return {"path": self._rel(), "read": self.ok, "as_of": self.as_of,
                "as_of_basis": self.basis, "age_h": self.age_h,
                "lease_h": LEASE_H.get(self.key, 6.0), "why": self.why or None}


def _field(src: Source, value: float | None, pressure: float | None, *, n: int | None = None,
           why: str = "", **detail: Any) -> dict[str, Any]:
    """A measured field, or the literal UNMEASURED with its reason -- never a silent zero."""
    if value is None:
        return {"value": UNMEASURED, "pressure": None, "source": src.card()["path"],
                "as_of": src.as_of, "why": why or src.why or "no reading", **detail}
    return {"value": round(float(value), 6), "pressure": (None if pressure is None
                                                          else round(_clip01(pressure), 6)),
            "n": n, "source": src.card()["path"], "as_of": src.as_of,
            "why": why or None, **detail}


def _from_pressure(src: Source, p: ph.Pressure, value: float | None, **detail: Any
                   ) -> dict[str, Any]:
    if p.value is None or value is None:
        return _field(src, None, None, why=p.why or src.why, n_obs=p.n, **detail)
    return _field(src, value, p.value, n=p.n, **detail)


def _p_pressure(p: float) -> float:
    return _clip01((P_CALM - p) / (P_CALM - P_GONE))


# -------------------------------------------------------------------------------------- fields
def feature_drift(sym: str, src: Source) -> dict[str, Any]:
    if not src.ok:
        return _field(src, None, None)
    per_symbol = src.doc.get("per_symbol") or {}
    row = per_symbol.get(sym) if isinstance(per_symbol, dict) else None
    if not isinstance(row, dict):
        return _field(src, None, None, why=f"drift_monitor did not measure {sym} on its last "
                                           f"pass (not in per_symbol)")
    p = dmon.feature_drift(sym, per_symbol)
    return _from_pressure(src, p, _num(row.get("hazard_max")), unit="z (hazard_max)")


def parameter_drift(name: str, row: dict[str, Any], src: Source) -> dict[str, Any]:
    ident = None
    if src.ok:
        ident = next((r for r in (src.doc.get("rows") or [])
                      if isinstance(r, dict) and r.get("name") == name), None)
    if isinstance(ident, dict) and ident.get("verdict") in ("MATCH", "MISMATCH"):
        diffs = list(ident.get("fields") or []) if ident["verdict"] == "MISMATCH" else []
        return _field(src, float(len(diffs)), 1.0 if diffs else 0.0, n=1,
                      unit="fields where the traded spec differs from the certified one",
                      identity=ident["verdict"], differing=diffs)
    if "certificate_drift" in row:
        # THE WEAKER WITNESS, SO HALF THE RULER. The promoter stamps this at promotion time,
        # "recorded, blocking nothing": the spec left today's gate-authority set, which says the
        # certificate needs re-reading -- not, as an identity MISMATCH does, that the gateway
        # trades a different strategy. It can make a sleeve DEGRADING, never BROKEN.
        drifted = bool(row.get("certificate_drift"))
        rel = SLEEVES.relative_to(ROOT).as_posix()
        return {"value": 1.0 if drifted else 0.0,
                "pressure": CERT_DRIFT_PRESSURE if drifted else 0.0, "n": 1,
                "source": f"{rel} (promoter certificate_drift)",
                "as_of": str(row.get("admit_scan") or row.get("promoted_at") or "") or None,
                "unit": "1 = the row's spec is not in the gate authority set",
                "why": ("identity join unavailable (" + (str(ident.get("why"))
                                                       if isinstance(ident, dict) else
                                                       (src.why or "no row for this sleeve"))
                        + "); the promoter's own flag is read instead")}
    why = (f"identity join UNMEASURED: {ident.get('why')}" if isinstance(ident, dict)
           else src.why if not src.ok else "research_live_identity has no row for this sleeve")
    return _field(src, None, None, why=why + "; and the row carries no certificate_drift flag")


def cost_drift(sym: str, src: Source) -> dict[str, Any]:
    if not src.ok:
        return _field(src, None, None)
    row = next((r for r in (src.doc.get("symbols") or [])
                if isinstance(r, dict) and r.get("symbol") == sym), None)
    if not isinstance(row, dict):
        return _field(src, None, None, why=f"cost_truth carries no row for {sym}")
    cmp_ = row.get("compare") or {}
    charged, ref = _num(cmp_.get("charged_pts")), _num(cmp_.get("reference_pts"))
    pooled = (((row.get("quoted") or {}).get("tape") or {}).get("pooled") or {})
    n = int(_num(pooled.get("n")) or 0)
    p = ph.ratio_pressure("cost_drift", ref, charged, n, worse_is_higher=True)
    value = (ref / charged) if ref is not None and charged else None
    return _from_pressure(src, p, value, unit="venue quoted / model charged spread",
                          cost_truth_verdict=cmp_.get("verdict"),
                          commission_total_overcharge=cmp_.get("commission_total_overcharge"))


def execution_drift(sym: str, src: Source) -> dict[str, Any]:
    if not src.ok:
        return _field(src, None, None)
    twin = dmon.twin_symbols(src.path)
    slip, fill = dmon.cost_drift(sym, twin), dmon.fill_drift(sym, twin)
    measured = [p for p in (slip, fill) if p.value is not None]
    if not measured:
        return _field(src, None, None, why=f"slip: {slip.why}; fill: {fill.why}")
    lead = max(measured, key=lambda p: float(p.value or 0.0))
    now_v, base_v = _num(lead.detail.get("now")), _num(lead.detail.get("baseline"))
    value = now_v / base_v if now_v is not None and base_v else None
    return _from_pressure(src, lead, value,
                          unit=("realised / modelled slip" if lead is slip
                                else "realised / predicted fill rate"),
                          leading="slip" if lead is slip else "fill",
                          slip_pressure=slip.value, fill_pressure=fill.value)


def regime_occupancy(name: str, src: Source) -> dict[str, Any]:
    if not src.ok:
        return _field(src, None, None)
    row = next((r for r in (src.doc.get("sleeves") or [])
                if isinstance(r, dict) and r.get("name") == name), None)
    if not isinstance(row, dict):
        return _field(src, None, None, why="regime_router published no row for this sleeve "
                                           "(no measured trade)")
    n = int(_num(row.get("n")) or 0)
    bucket = str(row.get("current_bucket") or "")
    in_state = int(_num(((row.get("by_state") or {}).get(bucket) or {}).get("n")) or 0)
    p_now = _num(row.get("p_alpha_positive_now"))
    if n < ph.HAZARD_MIN_N or p_now is None:
        return _field(src, None, None, why=(f"{n} trade(s), need {ph.HAZARD_MIN_N}" if p_now
                                            is not None else "no P(alpha>0 | now) published"))
    return _field(src, in_state / n, _p_pressure(p_now), n=n,
                  unit="share of the sleeve's trades taken in the state the desk is in now",
                  current_bucket=bucket, p_alpha_positive_now=p_now,
                  p_basis=row.get("p_alpha_positive_basis"))


def capacity_drift(name: str, sym: str, family: str, frontier: Source, floor: Source
                   ) -> dict[str, Any]:
    fl = None
    if floor.ok:
        fl = next((r for r in (floor.doc.get("rows") or [])
                   if isinstance(r, dict) and r.get("sleeve") == name), None)
    floor_detail = ({"floor_over_policy_now": fl.get("over_policy_now"),
                     "floor_binding_now": fl.get("binding_now"), "floor_source":
                     floor.card()["path"], "floor_as_of": floor.as_of}
                    if isinstance(fl, dict) else {"floor": floor.why or "no CAPACITY row"})
    if not frontier.ok or frontier.doc.get("status") != "OK":
        why = frontier.why or f"capacity_frontier status {frontier.doc.get('status')}"
        return _field(frontier, None, None, why=why, **floor_detail)
    curve = next((c for c in (frontier.doc.get("curves") or [])
                  if isinstance(c, dict) and c.get("symbol") == sym
                  and c.get("family") == family), None)
    if not isinstance(curve, dict):
        return _field(frontier, None, None, why=f"no frontier curve for ({sym}, {family}) in "
                                                f"the published top curves", **floor_detail)
    spreads = ((frontier.doc.get("spread_widening") or {}).get("by_symbol") or {}).get(sym)
    widen = _num(spreads.get("widening_multiple")) if isinstance(spreads, dict) else None
    dies = _num(curve.get("dies_at_cost_multiple"))
    status = str(curve.get("status") or "")
    n = int(_num(curve.get("n_signals")) or 0)
    if status == "SURVIVES_THE_SWEEP":
        return _field(frontier, 0.0, 0.0, n=n, unit="spread widening / death cost multiple",
                      frontier_status=status, **floor_detail)
    if status == "NO_EDGE_AT_1X":
        return _field(frontier, 1.0, 1.0, n=n, unit="spread widening / death cost multiple",
                      frontier_status=status, **floor_detail)
    if dies is None or widen is None:
        return _field(frontier, None, None, why="no death multiple or no spread widening for "
                                                f"{sym}", **floor_detail)
    pressure = 1.0 if dies <= 1.0 else (widen - 1.0) / (dies - 1.0)
    return _field(frontier, widen / dies, pressure, n=n,
                  unit="spread widening / death cost multiple", dies_at_cost_multiple=dies,
                  widening_multiple=widen, frontier_status=status, **floor_detail)


def forward_posterior(name: str, src: Source, decay: Source) -> dict[str, Any]:
    verdicts = (decay.doc.get("verdicts") or {}) if decay.ok else {}
    dv = verdicts.get(name) if isinstance(verdicts, dict) else None
    extra: dict[str, Any] = {"decay_monitor": ((dv.get("verdict") if isinstance(dv, dict) else dv)
                               if dv else (decay.why or "no decay_monitor verdict"))}
    if not src.ok:
        return _field(src, None, None, **extra)
    row = next((r for r in (src.doc.get("sleeves") or [])
                if isinstance(r, dict) and r.get("name") == name), None)
    if not isinstance(row, dict):
        return _field(src, None, None, why="posterior_alpha published no row for this sleeve",
                      **extra)
    n, p = int(_num(row.get("n")) or 0), _num(row.get("p_positive"))
    if p is None or n < ph.HAZARD_MIN_N:
        return _field(src, None, None, why=f"{n} forward observation(s), need "
                                           f"{ph.HAZARD_MIN_N}", **extra)
    return _field(src, p, _p_pressure(p), n=n, unit="P(mu > 0) on the forward record",
                  mu_mean=row.get("mu_mean"), basis=row.get("basis"),
                  edge_credible=row.get("edge_credible"), **extra)


# ------------------------------------------------------------------------------------- verdict
def verdict_of(fields: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """THE RULE. See the module docstring; this is the only place it is applied."""
    scored = {k: float(v["pressure"]) for k, v in fields.items()
              if isinstance(v.get("pressure"), (int, float))}
    broken = sorted(k for k, p in scored.items() if p >= BROKEN_AT and k in STRUCTURAL)
    if broken:
        return BROKEN, f"structural field(s) at full pressure: {', '.join(broken)}"
    degrading = sorted(k for k, p in scored.items() if p >= DEGRADING_AT)
    if degrading:
        return DEGRADING, (f"field(s) at or above {DEGRADING_AT} pressure: "
                           f"{', '.join(f'{k}={scored[k]:.2f}' for k in degrading)}")
    if len(scored) >= MIN_MEASURED and "recent_forward_posterior" in scored:
        return HEALTHY, f"{len(scored)} field(s) measured, none above {DEGRADING_AT}"
    missing = [k for k in FIELDS if k not in scored]
    return UNMEASURED, (f"{len(scored)} field(s) scored (need {MIN_MEASURED} including "
                        f"recent_forward_posterior); unscored: {', '.join(missing)}")


def live_rows(doc: Any) -> list[dict[str, Any]]:
    """Every roster row the gateway trades or is one admitting reading from trading: LIVE AND
    STANDBY (audit 2026-10-07, must-fix 1). A STANDBY row is the next thing the gateway places;
    leaving it out hid its tradability exactly when it was about to carry capital, and left
    `hazard_engine` (whose lane `live` is LIVE + STANDBY) stamping it with a false "no row".
    Each sleeve's own roster state is reported beside its verdict."""
    return [r for r in dm.roster_rows(doc).values()
            if str(r.get("status") or "").upper() in ROSTER_STATES]


def measure(now: datetime | None = None,
            paths: dict[str, Path] | None = None) -> dict[str, Any]:
    now = now or _now()
    p = {"sleeves": SLEEVES, "decay_live": DECAY_LIVE, "drift": DRIFT, "identity": IDENTITY,
         "cost_truth": COST_TRUTH, "execution_twin": EXECUTION_TWIN,
         "regime_router": REGIME_ROUTER, "capacity": CAPACITY,
         "capacity_frontier": CAPACITY_FRONTIER, "posterior": POSTERIOR, **(paths or {})}
    src = {k: Source(k, v, now) for k, v in p.items()}
    sleeves: list[dict[str, Any]] = []
    roster_ok = src["sleeves"].ok
    for row in (live_rows(src["sleeves"].doc) if roster_ok else []):
        name, sym = str(row.get("name") or ""), str(row.get("symbol") or "").upper()
        fam = str(row.get("family") or ("session_range_breakout" if row.get("window") else ""))
        fields: dict[str, dict[str, Any]] = {
            "feature_drift": feature_drift(sym, src["drift"]),
            "parameter_drift": parameter_drift(name, row, src["identity"]),
            "cost_drift": cost_drift(sym, src["cost_truth"]),
            "execution_drift": execution_drift(sym, src["execution_twin"]),
            "regime_occupancy": regime_occupancy(name, src["regime_router"]),
            "capacity_drift": capacity_drift(name, sym, fam, src["capacity_frontier"],
                                             src["capacity"]),
            "recent_forward_posterior": forward_posterior(name, src["posterior"],
                                                          src["decay_live"]),
        }
        verdict, why = verdict_of(fields)
        sleeves.append({"name": name, "symbol": sym, "family": fam or UNMEASURED,
                        "state": str(row.get("status") or "").upper(),
                        "verdict": verdict, "why": why,
                        "n_measured": sum(1 for f in fields.values()
                                          if f["value"] != UNMEASURED),
                        "fields": fields})
    sleeves.sort(key=lambda s: (_SEVERITY[s["verdict"]], s["name"]))
    counts = {v: sum(1 for s in sleeves if s["verdict"] == v) for v in VERDICTS}
    field_cover = {f: sum(1 for s in sleeves if s["fields"][f]["value"] != UNMEASURED)
                   for f in FIELDS}
    return {
        "schema": SCHEMA, "generated_utc": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if roster_ok else UNMEASURED,
        "n_live": sum(1 for s in sleeves if s["state"] == "LIVE") if roster_ok else None,
        "n_standby": (sum(1 for s in sleeves if s["state"] == "STANDBY") if roster_ok
                      else None),
        "n_sleeves": len(sleeves) if roster_ok else None,
        "states_judged": list(ROSTER_STATES),
        "roster_why": None if roster_ok else (src["sleeves"].why or "roster unreadable: the "
                                              "live set is UNKNOWN, not empty"),
        "counts": counts,
        "broken": [s["name"] for s in sleeves if s["verdict"] == BROKEN],
        "degrading": [s["name"] for s in sleeves if s["verdict"] == DEGRADING],
        "field_coverage": field_cover,
        "inputs": {k: s.card() for k, s in src.items()},
        "rule": {"ruler": "libs.research.perishability [0,1] pressure per field",
                 "broken": f"a STRUCTURAL field ({', '.join(sorted(STRUCTURAL))}) at pressure "
                           f">= {BROKEN_AT}",
                 "degrading": f"any field at pressure >= {DEGRADING_AT}",
                 "healthy": f">= {MIN_MEASURED} fields scored, recent_forward_posterior among "
                            f"them, none at or above {DEGRADING_AT}",
                 "unmeasured": "otherwise -- never read as healthy (L1.28a)",
                 "posterior_pressure": f"(P_CALM={P_CALM} - p) / (P_CALM - P_GONE={P_GONE})"},
        "consumer": ("research/hazard_engine.py: attaches each live sleeve's verdict to its card "
                     "and queues a successor_search for DEGRADING / BROKEN sleeves"),
        "boundary": ("a report: nothing here sizes, fades, retires or vetoes (GROWTH "
                     "GOVERNANCE Rule 1). The kill stays with decay_monitor."),
        "sleeves": sleeves,
    }


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, default=str)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, "utf-8")
    try:
        os.replace(tmp, path)
    except OSError:                # a read-only/locked destination is WinError 5 on the box
        path.write_text(text, "utf-8")
        tmp.unlink(missing_ok=True)


def run(write: bool = True, measure_fn: Callable[[], dict[str, Any]] = measure
        ) -> dict[str, Any]:
    doc = measure_fn()
    if write:
        _write_atomic(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-live-sleeve tradability health (report only)")
    ap.add_argument("--dry-run", action="store_true", help="print; write nothing")
    args = ap.parse_args(argv)
    doc = run(write=not args.dry_run)
    c = doc["counts"]
    print(f"tradability health: {doc['n_live']} live + {doc['n_standby']} standby -- "
          + ", ".join(f"{k}={v}" for k, v in c.items())
          + f"; field coverage {doc['field_coverage']}"
          + (" (dry run: nothing written)" if args.dry_run else f" -> {OUT}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
