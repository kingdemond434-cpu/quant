#!/usr/bin/env python3
"""EVERY LIVE SLEEVE'S MARGINAL ADMISSION, MEASURED EVERY HOUR (blueprint rows CS5 and D7).

    "No LIVE sleeve with UNMEASURED marginal indefinitely."          -- blueprint row CS5
    "31 LIVE with UNMEASURED marginal admission."                    -- blueprint row D7

`promoter.capital_verdict` returns UNMEASURED for a LIVE row the allocator never priced, and
`reconcile_capital` deliberately leaves such a row holding its risk ("removing risk on a compute
limit is an outage wearing a risk decision"). That is right for one pass and wrong forever: nothing
counted how long a LIVE row had sat UNMEASURED, so "indefinitely" was unobservable.

This organ is the measurement. Each pass it asks the promoter's own door -- the SAME
`allocation_view` + `capital_verdict` the promoter decides on, never a second reading -- for every
LIVE row's current marginal, and keeps per-sleeve the first time that row was seen UNMEASURED
(data/marginal_census_state.json). A row whose run of UNMEASURED readings exceeds
`UNMEASURED_BOUND_H` is listed as OVER_BOUND, with what a quarantine would do.

REPORT-ONLY (`ENFORCE = False`). It moves no row and no risk: a quarantine removes exposure, so
under the growth governance (Rule 1) it may bind only with a missed-growth line proving it raises
robust forward E[log W]. What it publishes is the input such a line needs: the held heat on each
over-bound row. Two-sided by construction -- a row that gets a measured ADMITTING reading leaves
the over-bound list on the same pass and its clock resets, so the bound can never hold risk down
after the allocator has priced it.

An absent or stale allocation is reported as the allocator's own `why`, and every LIVE row is then
UNMEASURED with that reason -- never a count of zero.

    python desks/mt5/research/marginal_census.py      -> reports/MARGINAL_CENSUS.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

OUT = DESK / "reports" / "MARGINAL_CENSUS.json"
STATE = DESK / "data" / "marginal_census_state.json"
#: How long a LIVE row may read UNMEASURED before it is listed OVER_BOUND. One heavy admission
#: scan is due every 2 h and the promoter accepts a scan up to `ADMISSION_MAX_AGE_H` (26 h); three
#: days is three missed days of scans, not a compute hiccup.
UNMEASURED_BOUND_H = 72.0
#: Report-only. Flipping it is a Rule-1 decision that needs the missed-growth line first.
ENFORCE = False


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def _hours(a: str, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(a)
    except (TypeError, ValueError):
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return round((now - t).total_seconds() / 3600.0, 2)


def census(sleeves: list[dict], view: dict, state: dict, now: datetime,
           bound_h: float = UNMEASURED_BOUND_H) -> tuple[dict, dict]:
    """(report, new_state). Pure over its inputs: the verdicts come from `capital_verdict`."""
    stamp = now.isoformat(timespec="seconds")
    first_seen = dict((state or {}).get("first_unmeasured_at") or {})
    new_first: dict[str, str] = {}
    rows: list[dict] = []
    for s in sleeves:
        if str(s.get("status") or "").upper() != "LIVE":
            continue
        name = str(s.get("name") or "")
        cap = promoter.capital_verdict(
            view, name, symbol=str(s.get("symbol") or ""), family=str(s.get("family") or ""),
            selector=str(s.get("selector") or s.get("window") or ""),
            streak=int(s.get("admit_streak") or 0), first_promotion=True)
        status = str(cap.get("status") or "UNMEASURED")
        row = {"name": name, "symbol": s.get("symbol"), "family": s.get("family"),
               "marginal": status, "delta_elogw_per_day": cap.get("delta_elogw_per_day"),
               "heat_earned": cap.get("heat_earned"),
               "held_risk_frac": float(s.get("risk_frac") or 0.0),
               "principal_override": bool(s.get("principal_override")),
               "joined": cap.get("joined"), "why": cap.get("why")}
        if status == "UNMEASURED":
            since = first_seen.get(name) or stamp
            new_first[name] = since
            age = _hours(since, now) or 0.0
            row.update({"unmeasured_since": since, "unmeasured_h": age,
                        "over_bound": age > bound_h})
            if row["over_bound"]:
                row["would_quarantine"] = (
                    f"UNMEASURED for {age:.1f} h > {bound_h:g} h: a binding quarantine would move "
                    f"this row to STANDBY through promoter.reconcile_capital, releasing "
                    f"{row['held_risk_frac']:.2%} held risk. REPORT-ONLY (ENFORCE=False) until a "
                    f"missed-growth line proves it raises robust forward E[log W]")
        else:
            row.update({"unmeasured_since": None, "unmeasured_h": 0.0, "over_bound": False})
        rows.append(row)
    counts = {k: sum(1 for r in rows if r["marginal"] == k)
              for k in ("LIVE", "STANDBY", "UNMEASURED")}
    over = [r["name"] for r in rows if r["over_bound"]]
    report = {
        "generated_at": stamp, "rows": rows, "n_live": len(rows),
        "counts": {"admitting": counts["LIVE"], "refusing": counts["STANDBY"],
                   "unmeasured": counts["UNMEASURED"]},
        "measured_share": (round((counts["LIVE"] + counts["STANDBY"]) / len(rows), 4)
                           if rows else None),
        "over_bound": over, "over_bound_held_risk": round(sum(
            r["held_risk_frac"] for r in rows if r["over_bound"]), 6),
        "bound_h": bound_h, "enforce": ENFORCE,
        "allocation": {"fresh": bool(view.get("fresh")), "why": view.get("why"),
                       "admission_at": view.get("at"),
                       "scan_age_h": view.get("age_h")},
        "verdict": ("UNMEASURED" if not rows else
                    "OVER_BOUND" if over else
                    "ALL_MEASURED" if not counts["UNMEASURED"] else "WITHIN_BOUND"),
        "rule": ("every LIVE row's marginal comes from promoter.capital_verdict over the same "
                 "allocation_view the promoter reads; a run of UNMEASURED readings longer than "
                 "bound_h is OVER_BOUND; report-only; a measured reading resets the clock"),
    }
    return report, {"first_unmeasured_at": new_first, "at": stamp}


def main(argv: list[str] | None = None) -> int:
    now = datetime.now(tz=UTC)
    doc = _read(promoter.SLEEVES_FILE)
    sleeves = (doc or {}).get("sleeves") if isinstance(doc, dict) else doc
    if not isinstance(sleeves, list):
        _write(OUT, {"generated_at": now.isoformat(timespec="seconds"), "verdict": "UNMEASURED",
                     "why": f"{promoter.SLEEVES_FILE.name} absent or unreadable"})
        print("marginal census UNMEASURED: sleeves.json unreadable")
        return 0
    report, state = census(sleeves, promoter.allocation_view(now), _read(STATE) or {}, now)
    _write(OUT, report)
    _write(STATE, state)
    print(f"marginal census {report['verdict']}: {report['n_live']} LIVE, {report['counts']}, "
          f"over bound {len(report['over_bound'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
