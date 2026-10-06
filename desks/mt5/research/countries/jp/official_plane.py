"""JAPAN OFFICIAL PLANE -- MOF flows and intervention, the BOJ's own series, and the refused lanes.

The series are fetched, parsed, PIT-stamped and vintaged by `research.alt_proxies` (rows
`jp_mof_securities_weekly`, `jp_mof_securities_investor_bonds`, `jp_mof_fx_intervention`,
`jp_boj_call_rate`, `jp_boj_tankan`, `jp_boj_current_account`, `jp_boj_jgb_holdings`, plus the
e-Stat / METI rows already there: every alt_proxies source whose region is JP). This module
fetches nothing. It reads them through `countries._official_plane` and adds what the directive's
PART IX asks of a Japan superplane and the factory cannot hold as a series:

  * EVENT OBJECTS with lifecycles: BOJ policy meetings (the decision day from the desk's one
    central-bank calendar, `forced_flow_calendar.CENTRAL_BANK_MEETINGS`, with the overnight call
    rate's move across it once both sides are knowable); every MOF intervention day (signed from
    the yen's side, knowable only at the quarterly disclosure); MOF's monthly intervention-total
    disclosure (SCHEDULED, last business day 19:00 JST); TANKAN prints; and the weekly MOF
    securities release.
  * A JAPAN FUNDING STATE (directive "latent state: Japan Funding State"): the latest surprise_z
    of each funding component, signed toward yen STRENGTH, and their mean. A component with no
    surprise_z is UNMEASURED and named, never a zero. It is a conditioning state, low prior, with
    no capital authority.

REFUSED or UNCONFIRMED lanes are reported with their verbatim terms and never fetched: JPX
market data (investor-type PDFs, margin, OSE options / implied volatility), the boj.or.jp HTML
releases (Rinban results, MPM statements: commercial copying excluded), J-Quants (terms not fully
readable; its parser waits on PR #218's collector output), TFX Click365 retail positions, and the
MOF JGB auction history (terms confirmed; the file is .xls and the desk has no reader).

The file is named `official_plane.py` for the same reason as Korea's: it is the plane every
department in this package now shares, and `pack.py` names it as the department module.
"""
from __future__ import annotations

import importlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def _load(name: str) -> Any:
    """A sibling module of the country packages, under whichever root this process resolves."""
    last: Exception | None = None
    for root in ("countries", "research.countries", "desks.mt5.research.countries"):
        try:
            return importlib.import_module(f"{root}.{name}")
        except ImportError as exc:
            last = exc
    raise ImportError(f"{name}: {last}")


_op: Any = _load("_official_plane")

CODE = "jp"
REGION = "JP"
REPORT: Path = _op.report_path(CODE)
REFUSED: tuple[str, ...] = ("jp_jpx_market_data", "jp_boj_site_releases",
                            "jp_jquants_investor_types", "jp_tfx_click365", "jp_mof_jgb_auctions")
LANES: tuple[str, ...] = ("alt_proxies:region=JP",)
YEN_TARGETS: list[str] = ["USDJPY", "EURJPY", "AUDJPY", "JPN225"]
#: (source id, series, sign toward YEN STRENGTH when the component's surprise is positive).
FUNDING_COMPONENTS: tuple[tuple[str, str, int], ...] = (
    ("jp_boj_call_rate", "call_rate_on", 1),
    ("jp_boj_current_account", "boj_current_account", -1),
    ("jp_boj_jgb_holdings", "boj_jgb_holdings", -1),
    ("jp_mof_securities_weekly", "assets_bonds_net", -1),
    ("jp_mof_securities_weekly", "liab_equity_net", 1),
    ("jp_mof_securities_investor_bonds", "bonds_life_insurers_net", -1),
)


def _boj_meetings() -> list[tuple[date, date]]:
    """(first day, decision day) of every BOJ meeting the desk's calendar holds."""
    try:
        ffc = importlib.import_module("research.forced_flow_calendar")
    except ImportError:
        try:
            ffc = importlib.import_module("forced_flow_calendar")
        except ImportError:
            return []
    row = (getattr(ffc, "CENTRAL_BANK_MEETINGS", {}) or {}).get("BOJ") or {}
    out = []
    for year, spans in sorted((row.get("days") or {}).items()):
        for m, d0, d1 in spans:
            out.append((date(int(year), int(m), int(d0)), date(int(year), int(m), int(d1))))
    return out


def _pts(points: dict[str, dict[str, list[dict[str, Any]]]], sid: str, series: str
         ) -> list[dict[str, Any]]:
    return list((points.get(sid) or {}).get(series) or [])


def _last_business_day(y: int, m: int) -> date:
    d = (date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1))
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def boj_meeting_events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
                       ) -> list[dict[str, Any]]:
    """Each BOJ meeting: SCHEDULED until its decision day, then RELEASED with the call rate's move
    from the last print before the decision to the first print on or after it (UNMEASURED until
    both are knowable). The statement text itself is a refused lane (boj.or.jp terms)."""
    call = _pts(points, "jp_boj_call_rate", "call_rate_on")
    out: list[dict[str, Any]] = []
    for first, decision in _boj_meetings():
        t = datetime(decision.year, decision.month, decision.day, 3, tzinfo=UTC)
        base = {"event": "jp_boj_mpm", "event_time": decision.isoformat(),
                "meeting_first_day": first.isoformat(), "nominal_time_utc": t.isoformat(),
                "time_basis": "nominal 12:00 JST; the decision lands when the board finishes",
                "targets": YEN_TARGETS, "data_source": "desk:forced_flow_calendar.BOJ"}
        if t > now:
            out.append({**base, "lifecycle": "SCHEDULED", "knowable_at": None, "value": None})
            continue
        before = [p for p in call if str(p["d"]) < decision.isoformat()]
        after = [p for p in call if str(p["d"]) >= decision.isoformat()
                 and str(p.get("knowable_at") or "") <= now.isoformat()]
        if before and after:
            v = round(float(after[0]["value"]) - float(before[-1]["value"]), 6)
            out.append({**base, "lifecycle": "RELEASED", "value": v,
                        "series": "jp_boj_call_rate:call_rate_on (first print on/after minus "
                                  "last print before the decision)",
                        "knowable_at": after[0].get("knowable_at")})
        else:
            out.append({**base, "lifecycle": "RELEASED", "value": None,
                        "knowable_at": None, "verdict": "UNMEASURED",
                        "why": "no call-rate print on both sides of the decision in the store"})
    return out


def intervention_events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
                        ) -> list[dict[str, Any]]:
    """Every MOF intervention day (RELEASED at its quarterly disclosure), then the next monthly
    total disclosures (SCHEDULED: last business day, 19:00 JST = 10:00 UTC)."""
    out: list[dict[str, Any]] = []
    for e in _op.released_events(_pts(points, "jp_mof_fx_intervention", "yen_bought_100m"),
                                 event="jp_mof_intervention",
                                 extra={"series": "jp_mof_fx_intervention:yen_bought_100m",
                                        "unit": "100 million yen", "targets": YEN_TARGETS,
                                        "data_source": "mof:fx_intervention"}):
        v = e.get("value")
        if v is None or float(v) == 0.0:
            continue
        side = "YEN_BUYING" if float(v) > 0 else "YEN_SELLING"
        out.append({**e, "side": side,
                    "mechanism": ("MOF sold dollars for yen: an official seller capped the "
                                  "weak-yen trend" if side == "YEN_BUYING" else
                                  "MOF sold yen: an official buyer capped yen strength")})
    y, m = now.year, now.month
    for _ in range(2):
        d = _last_business_day(y, m)
        t = datetime(d.year, d.month, d.day, 10, tzinfo=UTC)
        if t > now:
            out.append({"event": "jp_mof_intervention_monthly_total", "lifecycle": "SCHEDULED",
                        "scheduled_time": t.isoformat(timespec="seconds"),
                        "event_time": d.isoformat(), "knowable_at": None, "value": None,
                        "targets": YEN_TARGETS, "data_source": "mof:fx_intervention",
                        "why": "MOF discloses the month's intervention total on its last "
                               "business day; zero is a disclosed value, not an absence"})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def tankan_events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
                  ) -> list[dict[str, Any]]:
    """TANKAN prints (RELEASED, with the factory's expected value and surprise) and the next
    quarterly print (SCHEDULED: first business day of Apr/Jul/Oct, mid-December for Q4;
    approximate, verify against the BOJ release calendar)."""
    per = points.get("jp_boj_tankan") or {}
    out: list[dict[str, Any]] = []
    for series, pts in sorted(per.items()):
        out.extend(_op.released_events(pts, event="jp_boj_tankan",
                                       extra={"series": f"jp_boj_tankan:{series}",
                                              "targets": YEN_TARGETS,
                                              "data_source": "boj:tankan"}))
    for y in (now.year, now.year + 1):
        for m, d in ((4, 1), (7, 1), (10, 1), (12, 15)):
            t = datetime(y, m, d, 0, tzinfo=UTC)
            while t.weekday() >= 5:
                t += timedelta(days=1)
            if now < t and sum(1 for e in out if e["lifecycle"] == "SCHEDULED") < 1:
                out.append({"event": "jp_boj_tankan", "lifecycle": "SCHEDULED",
                            "scheduled_time": t.isoformat(timespec="seconds"),
                            "event_time": t.date().isoformat(), "knowable_at": None,
                            "value": None, "targets": YEN_TARGETS, "data_source": "boj:tankan",
                            "why": "approximate quarterly calendar; nothing is known until "
                                   "release"})
    return out


def weekly_flow_events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime,
                       keep: int = 8) -> list[dict[str, Any]]:
    """The last `keep` weekly MOF prints (RELEASED) and the next Thursday's print (SCHEDULED)."""
    out: list[dict[str, Any]] = []
    for series in ("assets_bonds_net", "liab_equity_net"):
        pts = _pts(points, "jp_mof_securities_weekly", series)[-keep:]
        out.extend(_op.released_events(pts, event="jp_mof_weekly_securities",
                                       extra={"series": f"jp_mof_securities_weekly:{series}",
                                              "targets": YEN_TARGETS,
                                              "data_source": "mof:intl_securities_weekly"}))
    d = now.date() + timedelta(days=1)
    while d.weekday() != 3:
        d += timedelta(days=1)
    out.append({"event": "jp_mof_weekly_securities", "lifecycle": "SCHEDULED",
                "scheduled_time": datetime(d.year, d.month, d.day, tzinfo=UTC)
                .isoformat(timespec="seconds"),
                "event_time": (d - timedelta(days=5)).isoformat(), "knowable_at": None,
                "value": None, "targets": YEN_TARGETS, "data_source": "mof:intl_securities_weekly",
                "why": "Thursday 08:50 JST print for the week to the prior Saturday"})
    return out


def events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
           ) -> list[dict[str, Any]]:
    out = [*boj_meeting_events(points, now), *intervention_events(points, now),
           *tankan_events(points, now), *weekly_flow_events(points, now)]
    return sorted(out, key=lambda e: (str(e.get("event_time")), str(e.get("event"))))


def funding_state(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
                  ) -> dict[str, Any]:
    """JAPAN FUNDING STATE: each component's latest knowable surprise_z, signed toward yen
    strength, and their mean. UNMEASURED components are named; with none measured the state is
    UNMEASURED, never 0."""
    comps: list[dict[str, Any]] = []
    for sid, series, sign in FUNDING_COMPONENTS:
        pts = [p for p in _pts(points, sid, series)
               if str(p.get("knowable_at") or "") <= now.isoformat()]
        z = next((p.get("surprise_z") for p in reversed(pts) if p.get("surprise_z") is not None),
                 None)
        comps.append({"source_id": sid, "series": series, "sign_to_yen_strength": sign,
                      "latest_d": pts[-1]["d"] if pts else None,
                      "surprise_z": z,
                      "signed_z": None if z is None else round(sign * float(z), 4),
                      "verdict": "MEASURED" if z is not None else "UNMEASURED"})
    got = [c["signed_z"] for c in comps if c["signed_z"] is not None]
    return {"japan_funding_state": {
        "at": now.isoformat(timespec="seconds"),
        "yen_strength_z": round(sum(got) / len(got), 4) if got else "UNMEASURED",
        "measured_components": len(got), "components": comps,
        "rule": ("mean of signed surprise_z over the measured components; a conditioning "
                 "state for the funding/carry lane, low prior until validated; no capital "
                 "authority")}}


def run(**kwargs: Any) -> dict[str, Any]:
    """The JP lanes from the factory's stores, the event system and the funding state."""
    kwargs.pop("code", None)
    kwargs.setdefault("report_default", REPORT)
    return dict(_op.run(code=CODE, region=REGION, refused=REFUSED, events=events,
                        states=funding_state, **kwargs))


__all__ = ["CODE", "FUNDING_COMPONENTS", "LANES", "REFUSED", "REPORT", "boj_meeting_events",
           "events", "funding_state", "intervention_events", "run", "tankan_events",
           "weekly_flow_events"]
