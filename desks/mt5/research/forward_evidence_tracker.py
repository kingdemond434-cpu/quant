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

    python desks/mt5/research/forward_evidence_tracker.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from collections.abc import Callable
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS, DATA = DESK / "reports", DESK / "data"
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
