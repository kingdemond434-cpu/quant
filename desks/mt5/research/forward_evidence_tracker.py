#!/usr/bin/env python3
"""FORWARD EVIDENCE, ACCUMULATED AS A TIME SERIES (Tier-1 audit item #20, 2026-09-29).

THE PRINCIPAL: "Forward evidence accumulation: track survival, degradation, live/backtest
calibration, breadth, realised cost, capacity, research hit rate over time."

WHAT EXISTED: every one of those numbers is measured somewhere -- the forward clocks' own state
files, `edge_reliability.json`, `EFFECTIVE_BREADTH.json`, `markout.json`, `CAPACITY.json`,
`EXPERIMENT_LEDGER.json`, `UNIVERSAL_SURVIVORS.json`, and since today the calibration posterior
(`LIVE_CALIBRATION_POSTERIOR.json`). `tier1_scorecard.py` puts several of them on one page. What
nothing kept is the SERIES: every one of those artifacts is overwritten each pass, so "is the
desk's forward evidence getting better or worse" had no answer beyond the last reading.

WHAT THIS DOES, hourly:
  * reads the seven dimensions from the organs that own them (never recomputing them), each with
    its source and UNMEASURED when the source is absent -- a zero would be a measurement;
  * appends ONE row per UTC hour to data/forward_evidence_history.jsonl (append-only);
  * publishes reports/FORWARD_EVIDENCE.json: the current reading plus the change against the
    reading ~24 hours and ~7 days earlier, per dimension, so drift is a number.

THE ASIAN-DERIVED SIGNAL RECORD (Asia directive XXIV, 2026-10-06). "For every Asian-derived signal
record: number of forward trades, days, effective sample size, autocorrelation adjustment,
sequential lower bound, costs, slippage, execution quality, realized expectancy, DD, decay,
correlation to book, marginal E[log W]." `asian_signals` publishes exactly those thirteen fields
per signal, each read from the organ that owns it (never recomputed by a second rule):

  lineage          RESEARCH_ROI.delayed_credit -- a forward key is Asian-derived when a source
                   whose region is china / japan / korea / south_asia / asean is credited with it
                   (the same provenance walk the research economy pays on)
  trades, days,    the forward clock's own row (shadow state: n, days_active, exp_r, max_dd_r)
  expectancy, DD
  n_eff, ACF adj., forward_verdict.effective_n / sequential_lower_bound over the FORWARD-phase
  sequential LB    trades of the clock's own ledger (reports/shadow/ledger_*.json)
  costs, slippage, data/fill_corpus.jsonl rows of the sleeve (commission_r, slip_r, filled
  execution        share, decision->send latency, spread at decision), plus the frozen cost basis
  decay            data/decay_live.json (verdict and fitted half-life)
  corr. to book,   reports/pf_allocation.json (admission.candidates[*].corr_to_book,
  marginal E[log W] marginal_delta_elog)

A field whose owner has nothing for the signal is UNMEASURED with the path it looked at -- never a
zero. No Asian-derived signal on a forward clock is itself the published answer (n_signals 0).

    python desks/mt5/research/forward_evidence_tracker.py
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
DATA = DESK / "data"
SHADOW = (REPORTS / "shadow" / "shadow_state.json", REPORTS / "shadow" / "qquant_shadow_state.json",
          REPORTS / "shadow" / "scalp_shadow_state.json",
          REPORTS / "shadow" / "external_shadow_state.json")
CALIBRATION = REPORTS / "LIVE_CALIBRATION_POSTERIOR.json"
RELIABILITY = REPORTS / "edge_reliability.json"
BREADTH = REPORTS / "EFFECTIVE_BREADTH.json"
MARKOUT = REPORTS / "markout.json"
CAPACITY = REPORTS / "CAPACITY.json"
EXPERIMENTS = REPORTS / "EXPERIMENT_LEDGER.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
HISTORY = DATA / "forward_evidence_history.jsonl"
OUT = REPORTS / "FORWARD_EVIDENCE.json"
RESEARCH_ROI = REPORTS / "RESEARCH_ROI.json"
PF_ALLOCATION = REPORTS / "pf_allocation.json"
DECAY_LIVE = DATA / "decay_live.json"
FILL_CORPUS = DATA / "fill_corpus.jsonl"
SLEEVE_REGISTRY = DATA / "sleeve_registry.json"
SHADOW_DIR = REPORTS / "shadow"
#: The research_roi regions that are Asia (directive scope: China first, Japan, Korea, South and
#: South-East Asia). Oceania is a transmission input, not an Asian origin, and is left out.
ASIAN_REGIONS = ("china", "japan", "korea", "south_asia", "asean")
#: The thirteen fields the directive names, in its order.
ASIAN_FIELDS = ("forward_trades", "days", "effective_sample_size", "autocorrelation_adjustment",
                "sequential_lower_bound", "costs", "slippage", "execution_quality",
                "realized_expectancy", "drawdown", "decay", "correlation_to_book",
                "marginal_elogw")

#: A clock started at least this long ago is old enough to count toward survival.
SURVIVAL_AGE_D = 14
ALIVE = {"ACTIVE", "PROMOTED", "LIVE", "MATURE", "ELIGIBLE"}
LOOKBACKS = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _unmeasured(path: Path) -> dict[str, Any]:
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    return {"status": "UNMEASURED", "value": None, "source": rel}


def survival(now: datetime) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    old, old_alive = 0, 0
    seen = False
    for p in SHADOW:
        d = _read(p)
        if not isinstance(d, dict):
            continue
        seen = True
        for r in d.values():
            if not isinstance(r, dict) or "status" not in r:
                continue
            st = str(r.get("status") or "").upper()
            by_status[st] = by_status.get(st, 0) + 1
            start = _ts(r.get("forward_start") or r.get("first_entry"))
            if start and now - start >= timedelta(days=SURVIVAL_AGE_D):
                old += 1
                old_alive += st in ALIVE
    if not seen:
        return _unmeasured(SHADOW[0])
    return {"status": "MEASURED" if old else "UNMEASURED",
            "value": round(old_alive / old, 4) if old else None,
            "n_clocks": sum(by_status.values()), "n_aged": old, "n_aged_alive": old_alive,
            "by_status": dict(sorted(by_status.items(), key=lambda t: -t[1])),
            "definition": f"share of clocks started >= {SURVIVAL_AGE_D}d ago still alive",
            "source": "reports/shadow/*_state.json"}


def degradation() -> dict[str, Any]:
    doc = _read(RELIABILITY)
    rows = doc.get("sleeves") if isinstance(doc, dict) else None
    vals = []
    if isinstance(rows, dict):
        rows = list(rows.values())
    for r in rows or []:
        v = _num((r or {}).get("p_works_now")) if isinstance(r, dict) else None
        if v is not None:
            vals.append(v)
    cal = _read(CALIBRATION)
    ratios = [_num(r.get("ratio")) for r in (cal.get("sleeves") or [])
              if isinstance(r, dict)] if isinstance(cal, dict) else []
    ratios = sorted(x for x in ratios if x is not None)
    if not vals and not ratios:
        return _unmeasured(RELIABILITY)
    return {"status": "MEASURED",
            "value": round(ratios[len(ratios) // 2], 4) if ratios else None,
            "definition": "median realised/claimed Sharpe per certificate-clock (1.0 = no decay)",
            "median_p_works_now": round(sorted(vals)[len(vals) // 2], 4) if vals else None,
            "n_ratio_rows": len(ratios), "n_reliability_rows": len(vals),
            "source": "reports/LIVE_CALIBRATION_POSTERIOR.json + reports/edge_reliability.json"}


def calibration() -> dict[str, Any]:
    doc = _read(CALIBRATION)
    pooled = doc.get("pooled") if isinstance(doc, dict) else None
    if not isinstance(pooled, dict) or not pooled.get("n_rows"):
        return _unmeasured(CALIBRATION)
    return {"status": "MEASURED", "value": _num(pooled.get("kappa_mean")),
            "kappa_sd": _num(pooled.get("kappa_sd")), "verdict": pooled.get("verdict"),
            "n_certificates": pooled.get("n_rows"),
            "definition": "posterior mean of realised/claimed Sharpe, pooled over certificates",
            "source": "reports/LIVE_CALIBRATION_POSTERIOR.json pooled"}


def breadth() -> dict[str, Any]:
    doc = _read(BREADTH)
    eff = doc.get("effective") if isinstance(doc, dict) else None
    v = None
    if isinstance(eff, dict):
        v = _num(eff.get("effective_breadth"))
        v = v if v is not None else _num(eff.get("n_eff"))
    if v is None:
        return _unmeasured(BREADTH)
    return {"status": "MEASURED", "value": v,
            "n_nominal": eff.get("n_nominal") if isinstance(eff, dict) else None,
            "definition": "effective independent bets (n_eff)",
            "source": "reports/EFFECTIVE_BREADTH.json effective"}


def realised_cost() -> dict[str, Any]:
    doc = _read(MARKOUT)
    # A markout with no matched fill has a mean of nothing: 0.0 there is not a measured cost.
    if (not isinstance(doc, dict) or _num(doc.get("mean_slip_r")) is None
            or not doc.get("usable") or not _num(doc.get("n_matched"))):
        return _unmeasured(MARKOUT)
    return {"status": "MEASURED", "value": _num(doc.get("mean_slip_r")),
            "n_matched": doc.get("n_matched"), "edge_share": doc.get("edge_share"),
            "definition": "mean entry slippage per matched fill, in R",
            "source": "reports/markout.json"}


def capacity() -> dict[str, Any]:
    doc = _read(CAPACITY)
    if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
        return _unmeasured(CAPACITY)
    n = int(doc.get("sleeves") or len(doc["rows"]))
    binding = int(doc.get("binding_now") or 0)
    return {"status": "MEASURED", "value": round(binding / n, 4) if n else None,
            "n_sleeves": n, "binding_now": binding,
            "over_risked": len(doc.get("over_risked") or []),
            "ceiling_status": doc.get("ceiling_status"),
            "definition": "share of live sleeves whose minimum lot binds above policy risk",
            "source": "reports/CAPACITY.json"}


def hit_rate() -> dict[str, Any]:
    exp = _read(EXPERIMENTS)
    surv = _read(SURVIVORS)
    trials = _num(exp.get("lifetime_trials")) if isinstance(exp, dict) else None
    n = None
    if isinstance(surv, dict):
        n = _num(surv.get("n"))
        if n is None and isinstance(surv.get("survivors"), dict):
            n = float(len(surv["survivors"]))
    if not trials or n is None:
        return _unmeasured(EXPERIMENTS if not trials else SURVIVORS)
    return {"status": "MEASURED", "value": round(n / trials, 8), "survivors": int(n),
            "lifetime_trials": int(trials),
            "definition": "certified survivors per lifetime trial",
            "source": "reports/UNIVERSAL_SURVIVORS.json n / reports/EXPERIMENT_LEDGER.json"}


# ---------------------------------------------------------------- the Asian-derived signal record
def _um(path: Path, why: str) -> dict[str, Any]:
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    return {"status": "UNMEASURED", "value": None, "source": rel, "why": why}


def asian_lineage(roi: Any) -> dict[str, list[str]]:
    """Forward/cell key -> the Asian source ids credited with it (RESEARCH_ROI delayed credit)."""
    if not isinstance(roi, dict):
        return {}
    regions = {str(k): str((v or {}).get("region") or "")
               for k, v in (roi.get("source_roi") or {}).items() if isinstance(v, dict)}
    by_source = (roi.get("delayed_credit") or {}).get("by_source") or {}
    out: dict[str, list[str]] = {}
    for sid, row in by_source.items():
        if regions.get(str(sid)) not in ASIAN_REGIONS or not isinstance(row, dict):
            continue
        for cell in row.get("cells") or []:
            out.setdefault(str(cell), [])
            if str(sid) not in out[str(cell)]:
                out[str(cell)].append(str(sid))
    return out


def ledger_paths(key: str, shadow_dir: Path | None = None) -> list[Path]:
    """`shadow_forward`'s ledger names a clock key can map to: `ledger_<SYM>_<window>.json` for a
    breakout (`SYM.window`) and `ledger_<SYM>_<family>_<window>.json` otherwise. A window may
    itself carry a dot (`asia.MACRO_FAV`), so both readings are offered; the chart, parameter tail
    and `.SHORT` are not in the file name."""
    stem = str(key).split("#", 1)[0].split("@", 1)[0]
    if stem.endswith(".SHORT"):
        stem = stem[: -len(".SHORT")]
    parts = stem.split(".")
    d = shadow_dir or SHADOW_DIR
    if len(parts) < 2:
        return []
    out = [d / f"ledger_{parts[0]}_{'.'.join(parts[1:])}.json"]
    if len(parts) >= 3:
        out.append(d / f"ledger_{parts[0]}_{parts[1]}_{'.'.join(parts[2:])}.json")
    return out


def _forward_rs(key: str, row: dict[str, Any]) -> tuple[list[float] | None, list[str], str]:
    """The clock's FORWARD-phase R multiples and entry days, or None with the reason. A ledger
    shared by several parameterisations is believed only when its forward count equals the
    clock's own `n` -- otherwise it is another clock's evidence and the fields stay UNMEASURED."""
    n = int(_num(row.get("n")) or 0)
    why = f"no ledger for {key}"
    for path in ledger_paths(key):
        doc = _read(path)
        if not isinstance(doc, list):
            continue
        fwd = [t for t in doc if isinstance(t, dict) and t.get("phase") == "forward"
               and _num(t.get("r_multiple")) is not None]
        if len(fwd) != n:
            why = (f"{path.name} holds {len(fwd)} forward trade(s), the clock {n}: a shared "
                   f"ledger, not this clock's alone")
            continue
        return ([float(t["r_multiple"]) for t in fwd],
                [str(t.get("entry_time") or "")[:10] for t in fwd], path.name)
    return None, [], why


def _fills(sleeve: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with FILL_CORPUS.open(encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if sleeve not in ln:
                    continue
                with contextlib.suppress(ValueError):
                    r = json.loads(ln)
                    if isinstance(r, dict) and str(r.get("sleeve") or "") == sleeve:
                        rows.append(r)
    except OSError:
        return []
    return rows


def _mean_of(rows: list[dict[str, Any]], key: str) -> tuple[float | None, int]:
    vals = [v for v in (_num(r.get(key)) for r in rows) if v is not None]
    return (round(sum(vals) / len(vals), 6) if vals else None), len(vals)


def signal_record(key: str, row: dict[str, Any], sources: list[str], alloc: Any,
                  decay: Any, registry: Any) -> dict[str, Any]:
    """The thirteen fields for one Asian-derived forward key."""
    import forward_verdict as fv
    rec: dict[str, Any] = {"key": key, "asian_sources": sorted(sources),
                           "status": str(row.get("status") or "")}
    n = _num(row.get("n"))
    rec["forward_trades"] = {"status": "MEASURED", "value": int(n)} if n is not None else \
        _um(SHADOW[0], "the clock row carries no n")
    days = _num(row.get("days_active"))
    rec["days"] = {"status": "MEASURED", "value": int(days)} if days is not None else \
        _um(SHADOW[0], "the clock row carries no days_active")
    rs, days_of, basis = _forward_rs(key, row)
    if rs is None or len(rs) < 2:
        why = basis if rs is None else f"{len(rs)} forward trade(s): no dependence estimate"
        for f in ("effective_sample_size", "autocorrelation_adjustment"):
            rec[f] = _um(SHADOW_DIR, why)
    else:
        n_eff, n_basis = fv.effective_n(rs, days_of)
        rec["effective_sample_size"] = {"status": "MEASURED", "value": round(n_eff, 3),
                                        "basis": n_basis, "source": basis}
        rec["autocorrelation_adjustment"] = {"status": "MEASURED",
                                             "value": round(len(rs) / n_eff, 4),
                                             "basis": f"n / n_eff ({n_basis})", "source": basis}
    if rs is None:
        rec["sequential_lower_bound"] = _um(SHADOW_DIR, basis)
    else:
        lb = fv.sequential_lower_bound(rs)
        rec["sequential_lower_bound"] = (
            {"status": "MEASURED", "value": round(lb, 6), "significant": lb > 0.0,
             "alpha": fv.SEQ_ALPHA, "source": basis} if math.isfinite(lb) else
            _um(SHADOW_DIR, f"{len(rs)} forward trade(s) < {fv.SEQ_MIN_TRADES}: no bound "
                "is drawn from a handful of trades"))
    fills = _fills(key)
    frozen = ((registry or {}).get("sleeves") or {}).get(key, {}) if isinstance(registry,
                                                                                   dict) else {}
    frozen_costs = frozen.get("cost_fields") if isinstance(frozen, dict) else None
    comm, n_comm = _mean_of(fills, "commission_r")
    rec["costs"] = ({"status": "MEASURED" if comm is not None else "MODELLED",
                     "value": comm, "n_fills": n_comm,
                     "frozen_cost_basis": frozen_costs or None,
                     "definition": "mean live commission per fill in R; the frozen modelled basis "
                                   "beside it"}
                    if comm is not None or frozen_costs else
                    _um(FILL_CORPUS, "no fill and no frozen cost basis for this sleeve"))
    slip, n_slip = _mean_of(fills, "slip_r")
    rec["slippage"] = ({"status": "MEASURED", "value": slip, "n_fills": n_slip,
                        "definition": "mean entry slippage per matched fill, in R"}
                       if slip is not None else
                       _um(FILL_CORPUS, "no matched fill for this sleeve (shadow clocks never "
                                        "fill)"))
    if fills:
        filled = sum(1 for r in fills if str(r.get("status") or "") == "FILLED")
        lat, _ = _mean_of(fills, "latency_decision_to_send_ms")
        spr, _ = _mean_of(fills, "spread_frac_at_decision")
        rec["execution_quality"] = {"status": "MEASURED", "value": round(filled / len(fills), 4),
                                    "n_rows": len(fills), "mean_latency_ms": lat,
                                    "mean_spread_frac": spr,
                                    "definition": "filled share of the sleeve's order rows"}
    else:
        rec["execution_quality"] = _um(FILL_CORPUS, "no order row for this sleeve")
    exp_r = _num(row.get("exp_r"))
    rec["realized_expectancy"] = ({"status": "MEASURED", "value": exp_r, "unit": "R/trade"}
                                  if exp_r is not None and n else
                                  _um(SHADOW[0], "no forward trade: an expectancy of nothing"))
    dd = _num(row.get("max_dd_r"))
    rec["drawdown"] = ({"status": "MEASURED", "value": dd, "unit": "R"} if dd is not None and n
                       else _um(SHADOW[0], "no forward trade: no drawdown measured"))
    dv = (decay or {}).get("verdicts") if isinstance(decay, dict) else None
    dm = (decay or {}).get("decay_model") if isinstance(decay, dict) else None
    v = dv.get(key) if isinstance(dv, dict) else None
    m = dm.get(key) if isinstance(dm, dict) else None
    rec["decay"] = ({"status": "MEASURED",
                     "value": (v or {}).get("verdict") if isinstance(v, dict) else None,
                     "half_life_days": (m or {}).get("half_life_days") if isinstance(m, dict)
                     else None, "source": "data/decay_live.json"}
                    if v is not None or m is not None else
                    _um(DECAY_LIVE, "the decay monitor judges LIVE sleeves; this key has no row"))
    cand = (((alloc or {}).get("admission") or {}).get("candidates") or {}).get(key) \
        if isinstance(alloc, dict) else None
    corr = _num((cand or {}).get("corr_to_book")) if isinstance(cand, dict) else None
    rec["correlation_to_book"] = ({"status": "MEASURED", "value": corr,
                                   "source": "reports/pf_allocation.json admission"}
                                  if corr is not None else
                                  _um(PF_ALLOCATION, "the allocator scored no admission row for "
                                                     "this key"))
    marg = (alloc or {}).get("marginal_delta_elog") if isinstance(alloc, dict) else None
    mv = _num(marg.get(key)) if isinstance(marg, dict) else None
    if mv is None and isinstance(cand, dict):
        mv = _num(cand.get("delta_elogw_per_day"))
    rec["marginal_elogw"] = ({"status": "MEASURED", "value": mv, "unit": "dE[log W]/day",
                              "source": "reports/pf_allocation.json"} if mv is not None else
                             _um(PF_ALLOCATION, "no marginal for this key in the allocation"))
    rec["n_measured"] = sum(1 for f in ASIAN_FIELDS
                            if (rec.get(f) or {}).get("status") != "UNMEASURED")
    return rec


def asian_signals(now: datetime) -> dict[str, Any]:
    """Every Asian-derived signal on a forward clock, with the directive's thirteen fields."""
    roi = _read(RESEARCH_ROI)
    if not isinstance(roi, dict):
        return {"status": "UNMEASURED", "n_signals": None, "signals": {},
                "fields": list(ASIAN_FIELDS),
                "why": f"no lineage: {_um(RESEARCH_ROI, '')['source']} absent or unreadable"}
    lineage = asian_lineage(roi)
    clocks: dict[str, dict[str, Any]] = {}
    for p in SHADOW:
        d = _read(p)
        if isinstance(d, dict):
            clocks.update({str(k): v for k, v in d.items() if isinstance(v, dict)
                           and "status" in v})
    alloc, decay, registry = _read(PF_ALLOCATION), _read(DECAY_LIVE), _read(SLEEVE_REGISTRY)
    signals = {key: signal_record(key, clocks[key], srcs, alloc, decay, registry)
               for key, srcs in sorted(lineage.items()) if key in clocks}
    return {"status": "MEASURED", "n_signals": len(signals),
            "n_asian_credited_cells": len(lineage),
            "signals": signals, "fields": list(ASIAN_FIELDS),
            "regions": list(ASIAN_REGIONS),
            "lineage_rule": ("a forward key whose RESEARCH_ROI delayed credit names a source in "
                             "an Asian region; the credit list is capped at 25 cells per source "
                             "by research_roi, so a heavily credited source may be under-listed"),
            "why": (None if signals else
                    "no Asian-derived signal is on a forward clock: the record is empty because "
                    "there is nothing to record, not because nothing was looked at")}


DIMENSIONS: dict[str, Callable[[datetime], dict[str, Any]]] = {
    "survival": survival, "degradation": lambda _n: degradation(),
    "live_backtest_calibration": lambda _n: calibration(), "breadth": lambda _n: breadth(),
    "realised_cost": lambda _n: realised_cost(), "capacity": lambda _n: capacity(),
    "research_hit_rate": lambda _n: hit_rate()}


def _history(path: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = (path or HISTORY).read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict) and _ts(d.get("at")):
            out.append(d)
    return out


def trend(hist: list[dict[str, Any]], now: datetime, current: dict[str, float | None],
          ) -> dict[str, dict[str, Any]]:
    """Change of each dimension against the history row nearest each lookback. Pure."""
    out: dict[str, dict[str, Any]] = {}
    for label, lb in LOOKBACKS.items():
        target = now - lb
        best = None
        for h in hist:
            t = _ts(h.get("at"))
            if t is None or t > target:
                continue
            bt = _ts(best["at"]) if best else None
            if bt is None or t > bt:
                best = h
        for dim, v in current.items():
            row = out.setdefault(dim, {})
            prev = _num((best or {}).get("values", {}).get(dim)) if best else None
            row[label] = (None if (v is None or prev is None) else round(v - prev, 8))
            row[f"{label}_from"] = best.get("at") if best else None
    return out


def _asian_block(now: datetime) -> dict[str, Any]:
    try:
        return asian_signals(now)
    except Exception as exc:                    # a diagnostic never takes the tracker down
        return {"status": "UNMEASURED", "n_signals": None, "signals": {},
                "fields": list(ASIAN_FIELDS), "why": f"{type(exc).__name__}: {exc}"}


def build(now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    now = now or datetime.now(tz=UTC)
    dims = {}
    for name, fn in DIMENSIONS.items():
        try:
            dims[name] = fn(now)
        except Exception as exc:
            dims[name] = {"status": "UNMEASURED", "value": None,
                          "why": f"{type(exc).__name__}: {exc}"}
    values = {k: _num(v.get("value")) for k, v in dims.items()}
    hist = _history()
    last = _ts(hist[-1]["at"]) if hist else None
    new_row = None
    if last is None or last.strftime("%Y%m%d%H") != now.strftime("%Y%m%d%H"):
        new_row = {"at": now.isoformat(timespec="seconds"), "values": values}
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "status": ("UNMEASURED" if all(v is None for v in values.values()) else "MEASURED"),
        "n_measured": sum(1 for v in values.values() if v is not None),
        "n_dimensions": len(values),
        "dimensions": dims,
        "trend": trend(hist, now, values),
        "asian_signals": _asian_block(now),
        "history": {"path": str(HISTORY.relative_to(ROOT)), "rows": len(hist) + bool(new_row),
                    "first": hist[0]["at"] if hist else (new_row or {}).get("at"),
                    "rule": "append-only, one row per UTC hour"},
    }
    return doc, new_row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc, row = build()
    if not args.dry_run:
        if row is not None:
            HISTORY.parent.mkdir(parents=True, exist_ok=True)
            with HISTORY.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    print(f"forward_evidence_tracker: {doc['status']} -- {doc['n_measured']}/"
          f"{doc['n_dimensions']} dimension(s) measured; history {doc['history']['rows']} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
