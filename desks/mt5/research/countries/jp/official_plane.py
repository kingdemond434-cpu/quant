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
releases (Rinban results, MPM statements: commercial copying excluded), TFX Click365 retail
positions, and the MOF JGB auction history (terms confirmed; the file is .xls and the desk has no
reader).

J-QUANTS IS A PRIVATE-USE LANE (`jquants_cells`). Its terms are `confirmed_private_use`
(libs.ops.token_refresh.TERMS, the principal's answer of 2026-10-06) and the repository is PUBLIC.
The asia collector stores it under data/lake/private_use/ (gitignored); this module builds the
investor-type flow cells from it -- net buy, change, acceleration and surprise per investor type
-- through the desk's one door (proposer_common.screen -> deflate -> donate, every look charged)
and donates them to data/intelligence_private/jquants/ (gitignored), which only
`miner_candidate_compiler.compile_private` reads. This report, and every other tracked or shared
artifact, carries the lane's COUNTS AND STATUS ONLY: no value, no date, no derived statistic, no
cell.

The file is named `official_plane.py` for the same reason as Korea's: it is the plane every
department in this package now shares, and `pack.py` names it as the department module.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
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
                            "jp_tfx_click365", "jp_mof_jgb_auctions")
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


# ============================================================== J-Quants: the private-use lane
JQ_LANE = "jp_jquants_investor_types"
#: The seat name, and the directory under the gitignored private root it donates to.
JQ_SOURCE = "jquants"
JQ_DATA_SOURCE = "jquants:investor_types"
JQ_FAMILY = "exogenous_conditioner"
JQ_FEATURES: tuple[str, ...] = ("net", "change", "acceleration", "surprise")
#: The instruments investor-type flow bears on: the yen (a foreign purchase of Japanese equity is
#: a yen purchase first) and the index itself. Routed by `alt_proxies.may_mint` (asset class).
JQ_TARGETS: tuple[str, ...] = ("USDJPY", "EURJPY", "JPN225")
JQ_DIRECTIONS: tuple[int, ...] = (1, -1)
JQ_HOLDS: tuple[int, ...] = (24, 120)
#: Each feature is judged against its own trailing prints only (never the future): at least
#: JQ_MIN_OBS of the last JQ_Z_OBS weeks, and a print fires when |z| >= JQ_Z_THRESHOLD.
JQ_Z_OBS = 26
JQ_MIN_OBS = 8
JQ_Z_THRESHOLD = 0.5
#: The only fields of the lane that may appear in a tracked or shared artifact.
JQ_PUBLIC_KEYS = ("dataset", "status", "terms", "private_use", "private_ref", "investor_types",
                  "observations", "features", "looks", "tests_run", "proposed", "donated",
                  "trials_charged", "why")


def _private_root() -> Path:
    from research import proposer_common as pc
    return pc.PRIVATE_INTEL / JQ_SOURCE


def _jq_features(obs: list[Any]) -> dict[tuple[str, str], list[tuple[datetime, float]]]:
    """(investor series, feature) -> [(knowable_at, z)] where z is the feature against its OWN
    trailing JQ_Z_OBS prints. A print without its published instant is never used: a weekly flow
    is knowable only from its publication, and inventing one would be look-ahead."""
    by_series: dict[str, list[Any]] = {}
    for o in obs:
        if getattr(o, "published_at", None) is not None:
            by_series.setdefault(str(o.series), []).append(o)
    out: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
    for series, rows in by_series.items():
        rows.sort(key=lambda o: o.period)
        v = [float(o.value) for o in rows]
        feats: dict[str, list[float | None]] = {"net": list(v), "change": [None] * len(v),
                                                "acceleration": [None] * len(v),
                                                "surprise": [None] * len(v)}
        for i in range(len(v)):
            if i >= 1:
                feats["change"][i] = v[i] - v[i - 1]
            if i >= 2:
                feats["acceleration"][i] = (v[i] - v[i - 1]) - (v[i - 1] - v[i - 2])
            prev = v[max(0, i - JQ_Z_OBS):i]
            if len(prev) >= JQ_MIN_OBS:
                mu = sum(prev) / len(prev)
                sd = math.sqrt(sum((x - mu) ** 2 for x in prev) / (len(prev) - 1))
                if sd > 0:
                    feats["surprise"][i] = (v[i] - mu) / sd
        for name, xs in feats.items():
            pts: list[tuple[datetime, float]] = []
            for i, x in enumerate(xs):
                if x is None:
                    continue
                hist = [h for h in xs[max(0, i - JQ_Z_OBS):i] if h is not None]
                if len(hist) < JQ_MIN_OBS:
                    continue
                mu = sum(hist) / len(hist)
                sd = math.sqrt(sum((h - mu) ** 2 for h in hist) / (len(hist) - 1))
                if sd > 0:
                    pts.append((rows[i].published_at, (float(x) - mu) / sd))
            if pts:
                out[(series, name)] = pts
    return out


def _jq_signals(d: Any, pts: list[tuple[datetime, float]], direction: int, hold: int
                ) -> list[Any]:
    """One signal per print whose |z| clears the threshold, on the first bar at or after its
    publication + the broker-clock pad (bars carry broker time under a UTC tzinfo)."""
    import pandas as pd
    from libs.research.release_gain import CLOCK_PAD_H
    from mt5desk.engine import Signal
    idx = d.index
    close = d["close"].to_numpy(dtype=float)
    out: list[Any] = []
    for when, z in pts:
        if abs(z) < JQ_Z_THRESHOLD:
            continue
        pos = int(idx.searchsorted(pd.Timestamp(when) + pd.Timedelta(hours=CLOCK_PAD_H)))
        if pos >= len(idx) - 1:
            continue
        side = int(direction) * (1 if z > 0 else -1)
        px = float(close[pos])
        out.append(Signal(time=idx[pos], side=side, stop=px * (1 - 0.05 * side),
                          target=px * (1 + 0.05 * side), ttl_bars=int(hold),
                          tag=f"{JQ_SOURCE}:{direction}"))
    return out


def _jq_public(lane: dict[str, Any]) -> dict[str, Any]:
    """The lane as a tracked artifact may carry it: counts and status, never a value."""
    return {k: lane[k] for k in JQ_PUBLIC_KEYS if k in lane}


def _charge(paths: Any, now: datetime, looks: int) -> int:
    """EVERY LOOK IS A TRIAL. The private discovery file is not read by experiment_ledger, so a
    J-Quants pass is charged on the tracked side ledger as a BARE COUNT (source, family, n)."""
    if looks <= 0:
        return 0
    row = {"at": now.isoformat(timespec="seconds"), "source": f"{JQ_SOURCE}_private",
           "tests_run": int(looks), "by_family": {JQ_FAMILY: int(looks)},
           "why": "private-use lane: looks charged here as a count; the cells stay private"}
    paths.null_trials.parent.mkdir(parents=True, exist_ok=True)
    with paths.null_trials.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return int(looks)


def jquants_cells(paths: Any = None, now: datetime | None = None, *, donate: bool = True,
                  private_root: Path | None = None) -> dict[str, Any]:
    """J-Quants investor-type flow cells, PRIVATE end to end. Returns the lane in its PUBLIC form
    (`JQ_PUBLIC_KEYS`: counts and status); everything else is written under `private_root`."""
    A = _op.alt()
    paths = paths or A.DEFAULT_PATHS
    now = now or datetime.now(UTC)
    lane: dict[str, Any] = {"dataset": JQ_LANE, "terms": "confirmed_private_use",
                            "private_use": True}
    try:
        from libs.ops import token_refresh as T
        prov = T.PROVIDERS.get("JQUANTS_TOKEN")
        allowed = bool(prov is not None and T.TERMS.get(prov.name, ("", ""))[0] == T.PRIVATE_USE
                       and T.terms_ok(prov))
    except Exception as exc:                        # fail closed: no verdict, no lane
        allowed = False
        lane["why"] = f"token_refresh unreadable ({type(exc).__name__}); fail closed"
    if not allowed:
        lane.update({"status": "BLOCKED_ON_TERMS:to_confirm", "terms": "to_confirm"})
        lane.setdefault("why", "the private-use verdict or its recorded condition is absent")
        return _jq_public(lane)
    obs = A.read_jquants_investor_types(paths)
    feats = _jq_features(obs)
    lane.update({"investor_types": len({k[0] for k in feats}), "observations": len(obs),
                 "features": len(feats)})
    if not obs:
        lane.update({"status": "PRIVATE_USE:UNMEASURED_LIVE_YIELD", "looks": 0, "tests_run": 0,
                     "why": "no J-Quants document in the private store on this host yet"})
        return _jq_public(lane)
    from research import proposer_common as pc
    meta = pc.universe_meta()
    rows: list[dict[str, Any]] = []
    looks = 0
    for sym in JQ_TARGETS:
        if not A.may_mint(sym, JQ_FAMILY):
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 500:
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            continue
        unf = pc.artifact_hours(d)
        for (series, feat), pts in sorted(feats.items()):
            for direction in JQ_DIRECTIONS:
                for hold in JQ_HOLDS:
                    looks += 1                       # a look is charged whatever it returns
                    sc = pc.screen(d, _jq_signals(d, pts, direction, hold), cost, unf)
                    if sc is None:
                        continue
                    ref = f"private:{JQ_SOURCE}/{series}/{feat}"
                    params = {"source": ref, "signal": feat, "transform": "level_z",
                              "threshold": JQ_Z_THRESHOLD, "z_obs": JQ_Z_OBS,
                              "side_when_high": direction, "lag_hours": 0,
                              "ttl_bars": hold, "timeframe": "H1"}
                    rows.append({"cell": f"{sym}.{JQ_FAMILY}.{ref}", "symbol": sym,
                                 "series": series, "feature": feat, "params": params, **sc})
    rows = pc.deflate(rows)
    # Every look is charged in the sweep's own deflation, null screens included.
    from research.multiplicity import deflate_t
    for r in rows:
        r["n_tests_sweep"] = looks
        r["t_deflated_sweep"] = round(deflate_t(float(r["t_gross"]), max(1, looks)), 3)
        r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > pc.PROPOSE_T
                             and int(r.get("n_independent", 0)) >= pc.MIN_TRADES)
    proposals = pc.best_per_cell(rows)
    stamp = now.isoformat(timespec="seconds")
    cands = []
    for r in proposals:
        c = pc.candidate(
            JQ_SOURCE, r["symbol"], JQ_FAMILY, dict(r["params"]),
            mechanism=(f"J-Quants investor-type flow: {r['series']} {r['feature']} against its "
                       f"own last {JQ_Z_OBS} weekly prints leans "
                       f"{'with' if r['params']['side_when_high'] > 0 else 'against'} the flow "
                       f"on {r['symbol']} for {r['params']['ttl_bars']} bars"),
            title=r["cell"][:120],
            evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                            "cost_frac", "t_gross", "t_deflated_sweep",
                                            "n_tests_sweep")})
        c.update({"kind": "hypothesis", "symbols": [r["symbol"]], "cell": r["cell"],
                  "data_source": JQ_DATA_SOURCE, "private_use": True,
                  "available_time": stamp, "event_time": stamp})
        cands.append(c)
    root = private_root or _private_root()
    donated = None
    if donate and cands:
        donated = pc.donate(JQ_SOURCE, cands, looks, private_root=root)
    charged = _charge(paths, now, looks) if donate else 0
    ref_basis = str(donated or "") + stamp
    lane.update({"status": "PRIVATE_USE:CELLS_BUILT", "looks": looks, "tests_run": looks,
                 "proposed": len(proposals), "donated": len(cands) if donated else 0,
                 "trials_charged": charged,
                 "private_ref": (hashlib.sha256(ref_basis.encode()).hexdigest()[:16]
                                 if donated else None)})
    if looks == 0:
        lane["why"] = "no target instrument with H1 bars and contract terms on this host"
    return _jq_public(lane)


def run(**kwargs: Any) -> dict[str, Any]:
    """The JP lanes from the factory's stores, the event system and the funding state; then the
    J-Quants private-use lane, whose cells stay private and whose row here is counts only."""
    kwargs.pop("code", None)
    target = kwargs.pop("report_default", None) or REPORT
    dry = bool(kwargs.pop("dry_run", False))
    doc = dict(_op.run(code=CODE, region=REGION, refused=REFUSED, events=events,
                       states=funding_state, dry_run=True, **kwargs))
    jq = jquants_cells(kwargs.get("paths"), kwargs.get("now"), donate=not dry)
    doc["lanes"].append(jq)
    doc["declared"] = len(doc["lanes"])
    doc["private_use_lanes"] = [jq["dataset"]]
    if not dry:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
        tmp.replace(target)
    return doc


__all__ = ["CODE", "FUNDING_COMPONENTS", "JQ_PUBLIC_KEYS", "LANES", "REFUSED", "REPORT",
           "boj_meeting_events", "events", "funding_state", "intervention_events",
           "jquants_cells", "run", "tankan_events", "weekly_flow_events"]
