#!/usr/bin/env python3
"""EXPECTATION GAPS -- a multi-sensor latent nowcast per release, and the gaps between OUR
nowcast, the CONSENSUS and the MARKET-IMPLIED expectation, each with its uncertainty (DATA-44).

WHAT EXISTED. `macro/release_vintages` joins the calendar's consensus to ALFRED's first prints and
carries ONE declared naive nowcast (EWM of the last twelve first prints); `macro/surprise` measures
the surprise family of one print; `shadow_institutional.fuse` fuses sensors into a latent with a
dispersion band; `priced_in` reads a prediction-market probability. Nothing published OUR
expectation with a posterior uncertainty, and nothing measured the GAP between what we expect,
what the survey expects and what the market has priced, BEFORE the print -- which is the only
moment a gap can be traded.

THE NOWCAST (per release, PIT at its scheduled instant: only first prints published before it).
Four declared sensors of the next first print -- `ewm12` (release_vintages.nowcast), `last` (the
latest first print), `mean12` (the trailing twelve), `ar1` (AR(1) on the trailing 24) -- each with
the variance of ITS OWN past errors (trailing 24, at least MIN_ERRORS). The posterior mean is the
precision-weighted mean; the posterior sd is the LARGER of the independent-errors sd
sqrt(1 / sum precision) and the fused nowcast's own past rms error, because the sensors share a
history and their errors correlate (declared, never assumed away). Published with each sensor's
weight and contribution (weight x forecast), the revision against the previous release's nowcast,
its acceleration (change of the revision), and -- after the print -- the surprise and its z.

THE EXPECTATIONS, AND THEIR TERMS.
  nowcast       alfred:<series>                     admitted (FRED/ALFRED terms basis)
  consensus     ff_calendar_vintage                 HELD (Forex Factory survey median)
  market_bars   mt5:bars (+ alfred for the fit)     admitted: per leg, a PIT OLS of the first
                print on the leg's pre-release log move (PREMOVE_DAYS to MARKET_LEAD before the
                instant), fitted on EARLIER releases only, fused across legs like the nowcast.
                It is what the tape had priced about the print, measured, never assumed.
  market_pm     prediction_markets:forecast_store   HELD; read only where a stored forecast row
                carries a numeric `expected_value` for the release, stored before the instant.
A gap's data source is the union of its two sides', so `libs.data.terms_hold.gauntlet_terms`
holds a gap whenever either side is held: its rows are computed, stored in the report and
counted, its gate verdict travels with it, and it reaches no lake series and no cell.

THE GAPS. For every pair (a, b) present at a release: gap = a - b, sd = sqrt(sd_a^2 + sd_b^2)
(independence declared), the uncertainty-adjusted gap gap/sd, the magnitude |gap| / sd(the pair's
earlier gaps on this release), the trailing percentile among those earlier gaps, and the
acceleration (second difference of the gap across releases, in the same trailing units). Knowable
at max(knowable_a, knowable_b), always before the scheduled instant.

THE HYPOTHESES, SEPARATE CONTRACTS (per gap pair x leg). The sign of a response is MEASURED: every
directional forecast is an EXPANDING OLS of the leg's release-day return on the feature, fitted on
releases whose return window had closed before this one's opened, against the expanding mean
(`sensor_engines.forecast_gain`).
  sign                 sign(gap)            -> release-day return
  magnitude            |gap| / trailing sd  -> |release-day return| (size, not direction)
  percentile           trailing pct - 0.5   -> release-day return
  acceleration         acceleration z       -> release-day return
  uncertainty_adjusted gap / sd             -> release-day return
  uncertainty_gate     `gated_gain`: the sign trade taken only while |gap/sd| >= 1
The release-day return: open of the first bar at or after max(the gap's knowable instant, the
release day's 00:00 UTC) to the release day's last close. Plus one nowcast contract: does the
fused nowcast forecast the first print better than the ewm12 sensor alone (errors in the
release's own trailing units, pooled).

    python desks/mt5/research/expectation_gaps.py [--days 1200] [--dry-run]
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

ENGINE = "expectation_gaps"
REPORT = DESK / "reports" / "EXPECTATION_GAPS.json"
UNMEASURED = "UNMEASURED"
CARDS = ["DATA-44"]
FALSIFIER = ("The gap between our nowcast and the consensus or the market-implied expectation, "
             "known before the print, does not forecast the release-day return (or its size) "
             "better than the expanding mean.")
#: Where a release's gap is read: declared legs, never a direction.
LEGS: tuple[str, ...] = ("XAUUSD", "EURUSD", "USDJPY", "US500")
SOURCES: dict[str, str] = {"consensus": "ff_calendar_vintage",
                           "market_bars": "mt5:bars",
                           "market_pm": "prediction_markets:forecast_store"}
#: The gap pairs, a - b.
PAIRS: tuple[tuple[str, str], ...] = (("nowcast", "consensus"), ("nowcast", "market_bars"),
                                      ("consensus", "market_bars"), ("nowcast", "market_pm"),
                                      ("consensus", "market_pm"))
HYPOTHESES = ("sign", "magnitude", "percentile", "acceleration", "uncertainty_adjusted")
SIGNALS = ("gap_sign", "gap_magnitude", "gap_percentile", "gap_accel_z", "gap_uadj")
ERR_WINDOW = 24
MIN_ERRORS = 6
MIN_HISTORY = 10
MIN_FIT = 12
MIN_FIT_EVENTS = 30
#: Pooled events a contract needs (releases are monthly: a lower floor than daily engines').
MIN_N_EVENTS = 150
PREMOVE_DAYS = 5
MARKET_LEAD = timedelta(hours=1)
UADJ_GATE = 1.0


def _f(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _iso(t: datetime | None) -> str | None:
    return None if t is None else t.astimezone(UTC).isoformat(timespec="seconds")


def _sd(xs: Sequence[float]) -> float | None:
    return float(np.std(xs, ddof=1)) if len(xs) >= 2 and float(np.std(xs, ddof=1)) > 0 else None


# ============================================================================== the nowcast
def sensor_forecasts(firsts: Sequence[float]) -> dict[str, float]:
    """Each declared sensor's forecast of the next first print, from earlier prints only."""
    xs = [x for x in firsts if x is not None and math.isfinite(x)]
    out: dict[str, float] = {}
    if len(xs) < 3:
        return out
    from macro.release_vintages import nowcast
    ewm = nowcast(xs)
    if ewm is not None:
        out["ewm12"] = float(ewm)
    out["last"] = float(xs[-1])
    out["mean12"] = float(np.mean(xs[-12:]))
    tail = xs[-ERR_WINDOW:]
    if len(tail) >= 8:
        x0, x1 = np.asarray(tail[:-1]), np.asarray(tail[1:])
        if float(np.var(x0)) > 0:
            phi = float(np.cov(x0, x1, ddof=1)[0, 1] / np.var(x0, ddof=1))
            phi = max(-0.99, min(0.99, phi))
            c = float(x1.mean() - phi * x0.mean())
            out["ar1"] = c + phi * float(tail[-1])
    return out


def fuse(forecasts: Mapping[str, float], errors: Mapping[str, Sequence[float]],
         own_errors: Sequence[float] = ()) -> dict[str, Any]:
    """Precision-weighted posterior of the sensors whose own error history is long enough."""
    var: dict[str, float] = {}
    skipped: dict[str, str] = {}
    for k, fc in forecasts.items():
        e = list(errors.get(k, ()))[-ERR_WINDOW:]
        if len(e) < MIN_ERRORS:
            skipped[k] = f"{len(e)} past error(s) < {MIN_ERRORS}"
            continue
        v = float(np.mean(np.square(e)))
        if v <= 0 or not math.isfinite(fc):
            skipped[k] = "zero error variance"
            continue
        var[k] = v
    if not var:
        return {"status": UNMEASURED, "mean": None, "sd": None, "skipped": skipped,
                "why": "no sensor has a measured error variance yet"}
    prec = {k: 1.0 / v for k, v in var.items()}
    tot = sum(prec.values())
    w = {k: p / tot for k, p in prec.items()}
    mean = sum(w[k] * forecasts[k] for k in w)
    sd_ind = math.sqrt(1.0 / tot)
    own = list(own_errors)[-ERR_WINDOW:]
    sd_own = math.sqrt(float(np.mean(np.square(own)))) if len(own) >= MIN_ERRORS else None
    return {"status": "MEASURED", "mean": mean,
            "sd": max(sd_ind, sd_own) if sd_own is not None else sd_ind,
            "sd_independent": sd_ind, "sd_calibrated": sd_own,
            "weights": {k: round(v, 6) for k, v in sorted(w.items())},
            "contribution": {k: round(w[k] * forecasts[k], 10) for k in sorted(w)},
            "forecasts": {k: round(v, 10) for k, v in sorted(forecasts.items())},
            "skipped": skipped}


def _ols(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float] | None:
    x, y = np.asarray(xs, float), np.asarray(ys, float)
    if x.size < 2 or float(np.var(x)) <= 0:
        return None
    b = float(np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1))
    return float(y.mean() - b * x.mean()), b


# ============================================================================== one release's rows
def release_rows(title: str, events: Sequence[Mapping[str, Any]], *,
                 series: str = "") -> list[dict[str, Any]]:
    """Every expectation and gap of one release, event by event, PIT at each scheduled instant.

    `events` (any order): {"at": scheduled instant, "actual": first print, optional
    "consensus" + "consensus_at", "premove": {leg: log move} + "premove_at",
    "pm_value" + "pm_at"}. Row i is computed from events[:i] and from event i's PRE-print fields;
    event i's actual enters only its post-print `surprise` and the histories of later rows.
    """
    evs = sorted((e for e in events if sc.parse_time(e.get("at")) is not None),
                 key=lambda e: sc.parse_time(e.get("at")))  # type: ignore[arg-type,return-value]
    firsts: list[float] = []
    first_at: datetime | None = None
    s_err: dict[str, list[float]] = {}
    nc_err: list[float] = []
    c_err: list[float] = []
    pm_err: list[float] = []
    leg_hist: dict[str, list[tuple[float, float]]] = {}
    leg_err: dict[str, list[float]] = {}
    mk_err: list[float] = []
    gap_hist: dict[str, list[float]] = {}
    prev_mean: float | None = None
    prev_rev: float | None = None
    src_now = f"alfred:{series}" if series else "alfred"
    rows: list[dict[str, Any]] = []
    for ev in evs:
        at = sc.parse_time(ev.get("at"))
        assert at is not None
        actual = _f(ev.get("actual"))
        row: dict[str, Any] = {"release": title, "series": series, "at": _iso(at)}
        exps: dict[str, dict[str, Any]] = {}
        # ---- our nowcast
        fc = sensor_forecasts(firsts)
        nc = fuse(fc, s_err, nc_err)
        if nc["status"] == "MEASURED" and first_at is not None:
            exps["nowcast"] = {"mean": nc["mean"], "sd": nc["sd"], "knowable_at": first_at,
                               "source": src_now}
            rev = None if prev_mean is None else nc["mean"] - prev_mean
            nc["revision"] = rev
            nc["acceleration"] = (None if rev is None or prev_rev is None else rev - prev_rev)
            prev_mean, prev_rev = nc["mean"], rev
        row["nowcast"] = nc
        # ---- the consensus (refused when captured at or after the instant)
        cons, cat = _f(ev.get("consensus")), sc.parse_time(ev.get("consensus_at"))
        if cons is not None and cat is not None and cat < at:
            c_e = c_err[-ERR_WINDOW:]
            exps["consensus"] = {"mean": cons, "knowable_at": cat, "source": SOURCES["consensus"],
                                 "sd": (math.sqrt(float(np.mean(np.square(c_e))))
                                        if len(c_e) >= MIN_ERRORS else None)}
        # ---- the market-implied expectation from the tape before the instant
        pm_at = sc.parse_time(ev.get("premove_at"))
        moves = {k: v for k, v in dict(ev.get("premove") or {}).items() if _f(v) is not None}
        if pm_at is not None and pm_at < at and moves:
            preds: dict[str, float] = {}
            for leg, mv in moves.items():
                lh = leg_hist.get(leg, [])
                fit = _ols([h[0] for h in lh], [h[1] for h in lh]) if len(lh) >= MIN_FIT \
                    else None
                if fit is not None:
                    preds[leg] = fit[0] + fit[1] * float(mv)
            mk = fuse(preds, leg_err, mk_err) if preds else {"status": UNMEASURED,
                                                            "why": "no leg fit yet"}
            row["market_bars"] = {k: mk.get(k) for k in ("status", "mean", "sd", "weights",
                                                         "why")}
            if mk["status"] == "MEASURED":
                exps["market_bars"] = {"mean": mk["mean"], "sd": mk["sd"], "knowable_at": pm_at,
                                       "source": f"{SOURCES['market_bars']}+{src_now}"}
        else:
            preds = {}
            row["market_bars"] = {"status": UNMEASURED, "why": "no pre-release bars"}
        pmv, pma = _f(ev.get("pm_value")), sc.parse_time(ev.get("pm_at"))
        if pmv is not None and pma is not None and pma < at:
            p_e = pm_err[-ERR_WINDOW:]
            exps["market_pm"] = {"mean": pmv, "knowable_at": pma, "source": SOURCES["market_pm"],
                                 "sd": (math.sqrt(float(np.mean(np.square(p_e))))
                                        if len(p_e) >= MIN_ERRORS else None)}
        row["expectations"] = {k: {"mean": v["mean"], "sd": v["sd"],
                                   "knowable_at": _iso(v["knowable_at"]), "source": v["source"]}
                               for k, v in exps.items()}
        # ---- the gaps
        gaps: dict[str, dict[str, Any]] = {}
        for a, b in PAIRS:
            if a not in exps or b not in exps:
                continue
            key = f"{a}-{b}"
            g = float(exps[a]["mean"] - exps[b]["mean"])
            sa, sb = exps[a]["sd"], exps[b]["sd"]
            sd = math.sqrt(sa * sa + sb * sb) if sa is not None and sb is not None else None
            hist = gap_hist.setdefault(key, [])
            scale = _sd(hist[-ERR_WINDOW:])
            pct = None
            if len(hist) >= MIN_HISTORY:
                pct = (sum(1 for h in hist if h < g) + 0.5 * sum(1 for h in hist if h == g)) \
                    / len(hist)
            accel = (g - 2 * hist[-1] + hist[-2]) if len(hist) >= 2 else None
            src = "+".join(dict.fromkeys(
                p for s in (exps[a]["source"], exps[b]["source"]) for p in s.split("+")))
            ok, why = gauntlet_terms(src)
            gaps[key] = {
                "gap": g, "sd": sd, "uadj": (g / sd if sd else None),
                "sign": float(np.sign(g)), "magnitude": (abs(g) / scale if scale else None),
                "percentile": pct,
                "accel_z": (accel / scale if accel is not None and scale else None),
                "knowable_at": _iso(max(exps[a]["knowable_at"], exps[b]["knowable_at"])),
                "data_source": src, "terms": "admitted" if ok else "HELD",
                "terms_why": why}
            hist.append(g)
        row["gaps"] = gaps
        # ---- after the print: the surprise, then every history learns the actual
        if actual is not None:
            if nc["status"] == "MEASURED":
                row["surprise"] = actual - nc["mean"]
                row["surprise_z"] = row["surprise"] / nc["sd"] if nc["sd"] else None
                nc_err.append(actual - nc["mean"])
                row["sensor_errors"] = {k: actual - v for k, v in fc.items()}
            for k, v in fc.items():
                s_err.setdefault(k, []).append(actual - v)
            if "consensus" in exps:
                c_err.append(actual - exps["consensus"]["mean"])
            if "market_pm" in exps:
                pm_err.append(actual - exps["market_pm"]["mean"])
            for leg, p in preds.items():
                leg_err.setdefault(leg, []).append(actual - p)
            if "market_bars" in exps:
                mk_err.append(actual - exps["market_bars"]["mean"])
            for leg, mv in moves.items():
                leg_hist.setdefault(leg, []).append((float(mv), actual))
            row["scale"] = _sd([b - a for a, b in zip(firsts[-ERR_WINDOW:],
                                                       firsts[-ERR_WINDOW + 1:], strict=False)])
            firsts.append(actual)
            first_at = at
        row["actual"] = actual
        rows.append(row)
    return rows


def gauntlet_terms(source_id: str) -> tuple[bool, str]:
    from libs.data.terms_hold import gauntlet_terms as held
    return held(source_id)


# ============================================================================== returns
def release_return(frame: Any, minutes: int, entry_after: datetime, day: date
                   ) -> float | None:
    """log(last close of `day`) - log(open of the first bar opening at/after `entry_after`)."""
    if frame is None or len(frame) == 0:
        return None
    import pandas as pd
    start = max(entry_after, datetime(day.year, day.month, day.day, tzinfo=UTC))
    end = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
    f = frame[(frame.index >= pd.Timestamp(start)) & (frame.index < pd.Timestamp(end))]
    if len(f) == 0:
        return None
    o, c = float(f["open"].iloc[0]), float(f["close"].iloc[-1])
    return math.log(c / o) if o > 0 and c > 0 else None


def premove(frame: Any, minutes: int, cut: datetime, days: int = PREMOVE_DAYS) -> float | None:
    """Log move of the last close BEFORE `cut` against the last close `days` days earlier."""
    if frame is None or len(frame) == 0:
        return None
    import pandas as pd
    closes = frame.index + pd.Timedelta(minutes=minutes)
    now_m = closes <= pd.Timestamp(cut)
    then_m = closes <= pd.Timestamp(cut - timedelta(days=days))
    if not now_m.any() or not then_m.any():
        return None
    c1 = float(frame["close"][now_m].iloc[-1])
    c0 = float(frame["close"][then_m].iloc[-1])
    return math.log(c1 / c0) if c0 > 0 and c1 > 0 else None


# ============================================================================== contracts
def _expanding(x: Sequence[float], y: Sequence[float], start: Sequence[datetime],
               end: Sequence[datetime]) -> tuple[list[float], list[float], list[int]]:
    """For each event, an OLS forecast and the mean, fitted on events whose window ended before
    this one's opened. Returns (model, base, index) for the events that had MIN_FIT_EVENTS.
    Running sums in end order keep it linear; the fit never sees an unfinished window."""
    by_end = sorted(range(len(y)), key=lambda j: end[j])
    model: list[float] = []
    base: list[float] = []
    idx: list[int] = []
    n = sx = sy = sxx = sxy = 0.0
    k = 0
    for i in sorted(range(len(y)), key=lambda j: start[j]):
        while k < len(by_end) and end[by_end[k]] <= start[i]:
            j = by_end[k]
            n += 1
            sx += x[j]
            sy += y[j]
            sxx += x[j] * x[j]
            sxy += x[j] * y[j]
            k += 1
        if n < MIN_FIT_EVENTS:
            continue
        mx, mu = sx / n, sy / n
        vx = sxx / n - mx * mx
        b = (sxy / n - mx * mu) / vx if vx > 1e-15 else 0.0
        model.append(mu + b * (x[i] - mx))
        base.append(mu)
        idx.append(i)
    return model, base, idx


def hypothesis_contracts(events: Sequence[Mapping[str, Any]], *, pair: str, leg: str,
                         terms: str = "admitted", min_n: int = MIN_N_EVENTS
                         ) -> list[dict[str, Any]]:
    """The separate hypotheses of one gap pair on one leg. `events`: {"gap": {...the gap row},
    "ret": release-day log return, "start"/"end": its window}, any order."""
    evs = sorted((e for e in events if _f(e.get("ret")) is not None),
                 key=lambda e: e["start"])
    feat = {"sign": "sign", "magnitude": "magnitude", "percentile": "percentile",
            "acceleration": "accel_z", "uncertainty_adjusted": "uadj"}
    out: list[dict[str, Any]] = []
    tag = {"pair": pair, "leg": leg, "terms": terms}
    sign_pos: dict[int, float] = {}
    for hyp in HYPOTHESES:
        have = [e for e in evs if _f(e["gap"].get(feat[hyp])) is not None]
        x = [float(e["gap"][feat[hyp]]) - (0.5 if hyp == "percentile" else 0.0) for e in have]
        y = [abs(float(e["ret"])) if hyp == "magnitude" else float(e["ret"]) for e in have]
        model, base, idx = _expanding(x, y, [e["start"] for e in have],
                                      [e["end"] for e in have])
        yy = [y[i] for i in idx]
        c = se.forecast_gain(yy, model, base, engine=ENGINE, cards=CARDS, falsifier=FALSIFIER,
                             baseline="expanding mean of the release-day return"
                                      + (" size" if hyp == "magnitude" else ""),
                             block=5, min_n=min_n)
        out.append(c | tag | {"hypothesis": hyp, "label": f"{pair} {hyp} -> {leg}"})
        if hyp == "sign":
            for k, i in enumerate(idx):
                sign_pos[id(have[i])] = float(np.sign(model[k] - base[k]) or np.sign(model[k]))
    traded = [e for e in evs if id(e) in sign_pos]
    pay = [sign_pos[id(e)] * float(e["ret"]) for e in traded]
    gate = [(_f(e["gap"].get("uadj")) is not None and abs(float(e["gap"]["uadj"])) >= UADJ_GATE)
            for e in traded]
    g = se.gated_gain(pay, gate, engine=ENGINE, cards=CARDS, falsifier=FALSIFIER,
                      baseline="the measured-sign trade on every release", min_n=min_n,
                      min_active=max(10, min_n // 10))
    out.append(g | tag | {"hypothesis": "uncertainty_gate",
                          "label": f"{pair} sign trade only while |gap/sd| >= {UADJ_GATE}"})
    return out


def nowcast_contract(rows: Sequence[Mapping[str, Any]], *, min_n: int = MIN_N_EVENTS
                     ) -> dict[str, Any]:
    """Does the fused nowcast beat the ewm12 sensor alone? Errors in the release's own units."""
    y, m, b = [], [], []
    for r in rows:
        nc, a, sc_ = r.get("nowcast") or {}, _f(r.get("actual")), _f(r.get("scale"))
        ewm = (nc.get("forecasts") or {}).get("ewm12")
        if nc.get("status") != "MEASURED" or a is None or not sc_ or ewm is None:
            continue
        y.append((a - ewm) / sc_)
        m.append((nc["mean"] - ewm) / sc_)
        b.append(0.0)
    return se.forecast_gain(y, m, b, engine=ENGINE, cards=CARDS,
                            falsifier="The fused multi-sensor nowcast forecasts the first print "
                                      "no better than the ewm12 sensor alone.",
                            baseline="ewm12 single-sensor nowcast", block=5, min_n=min_n) \
        | {"hypothesis": "multi_sensor_nowcast", "label": "fused nowcast vs ewm12"}


# ============================================================================== inputs on the box
def _alfred_events(now: datetime, days: int) -> tuple[dict[str, tuple[str, list[dict[str, Any]]]],
                                                      dict[str, Any]]:
    from macro import release_vintages as rv
    cons = rv.consensus_vintages()
    out: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    acc: dict[str, Any] = {"releases": 0, "first_prints": 0, "with_consensus": 0,
                           "alfred_missing": []}
    frames: dict[str, Any] = {}
    for spec in rv.RELEASES:
        if spec.series not in frames:
            frames[spec.series] = rv.load_alfred(spec.series)
        df = frames[spec.series]
        if df is None:
            acc["alfred_missing"].append(spec.series)
            continue
        evs = []
        for p in rv.release_vintage(df, spec):
            at = rv.scheduled_utc(spec, date.fromisoformat(p["vintage"]))
            if at > now:
                break
            c = cons.get((spec.title, p["vintage"])) or {}
            evs.append({"at": at, "actual": p["actual"], "consensus": c.get("consensus"),
                        "consensus_at": c.get("captured_at")})
            acc["with_consensus"] += int(c.get("consensus") is not None)
        acc["first_prints"] += len(evs)
        if evs:
            acc["releases"] += 1
            out[spec.title] = (spec.series, evs)
    acc["alfred_missing"] = sorted(set(acc["alfred_missing"]))
    return out, acc


def _pm_values() -> dict[str, list[tuple[datetime, float]]]:
    """Stored forecasts that carry a numeric expected value for a release title."""
    try:
        from research import priced_in as pi
        rows = pi.read_forecasts()
    except Exception:
        return {}
    out: dict[str, list[tuple[datetime, float]]] = {}
    for r in rows:
        v, t = _f(r.get("expected_value")), sc.parse_time(r.get("stored_at"))
        title = str(r.get("release") or "")
        if v is not None and t is not None and title:
            out.setdefault(title, []).append((t, v))
    return out


def _bars(symbol: str) -> tuple[Any, int] | None:
    try:
        import event_response_atlas as atlas  # type: ignore[import-not-found]
        got = atlas.chart(symbol)
    except Exception:
        return None
    return None if got is None else (got[0], int(got[2]))


def attach_market(events: list[dict[str, Any]], bars: Mapping[str, tuple[Any, int] | None],
                  pm: Sequence[tuple[datetime, float]] = ()) -> None:
    for ev in events:
        at = sc.parse_time(ev["at"])
        assert at is not None
        cut = at - MARKET_LEAD
        mv = {leg: m for leg, fb in bars.items() if fb is not None
              and (m := premove(fb[0], fb[1], cut)) is not None}
        if mv:
            ev["premove"], ev["premove_at"] = mv, cut
        before = [(t, v) for t, v in pm if t < at]
        if before:
            ev["pm_at"], ev["pm_value"] = max(before)


def run(*, now: datetime, days: int = 1200,
        releases: Mapping[str, tuple[str, list[dict[str, Any]]]] | None = None,
        bars_fn: Callable[[str], tuple[Any, int] | None] | None = None,
        pm_values: Mapping[str, Sequence[tuple[datetime, float]]] | None = None,
        legs: Sequence[str] = LEGS, ledger: Any = None, lake_root: Path | None = None,
        contracts_root: Path | None = None, report: Path | None = REPORT,
        dry_run: bool = False, emit_cells: bool = True, min_n: int = MIN_N_EVENTS
        ) -> dict[str, Any]:
    acc: dict[str, Any] = {}
    if releases is None:
        releases, acc = _alfred_events(now, days)
    pm_all = dict(pm_values) if pm_values is not None else _pm_values()
    bars = {leg: (bars_fn or _bars)(leg) for leg in legs}
    horizon = now - timedelta(days=days)
    all_rows: list[dict[str, Any]] = []
    for title, (series, evs) in releases.items():
        evs = [dict(e) for e in evs]
        attach_market(evs, bars, pm_all.get(title, ()))
        rows = release_rows(title, evs, series=series)
        all_rows += [r for r in rows if (sc.parse_time(r["at"]) or now) >= horizon
                     and (sc.parse_time(r["at"]) or now) <= now]
    all_rows.sort(key=lambda r: str(r["at"]))
    # ---- per pair: events joined to each leg's release-day return
    contracts: list[dict[str, Any]] = [nowcast_contract(all_rows, min_n=min_n)]
    pairs: dict[str, Any] = {}
    lake_out: dict[str, Any] = {}
    cells_out: dict[str, Any] = {}
    for a, b in PAIRS:
        key = f"{a}-{b}"
        grows = [(r, r["gaps"][key]) for r in all_rows if key in r["gaps"]]
        srcs = sorted({p for _, g in grows for p in g["data_source"].split("+")})
        ds = "+".join(srcs)
        ok, why = gauntlet_terms(ds) if ds else (False, "no rows")
        pairs[key] = {"rows": len(grows), "data_source": ds or UNMEASURED,
                      "terms": "admitted" if ok else "HELD", "terms_why": why}
        if not grows:
            pairs[key]["why"] = "no release carried both expectations"
        for leg in legs:
            fb = bars.get(leg)
            jevs: list[dict[str, Any]] = []
            for r, g in grows:
                at, k_at = sc.parse_time(r["at"]), sc.parse_time(g["knowable_at"])
                if at is None or k_at is None or fb is None:
                    continue
                ret = release_return(fb[0], fb[1], k_at, at.date())
                if ret is not None:
                    start = max(k_at, datetime(at.year, at.month, at.day, tzinfo=UTC))
                    jevs.append({"gap": g, "ret": ret, "start": start,
                                 "end": datetime(at.year, at.month, at.day, tzinfo=UTC)
                                 + timedelta(days=1)})
            contracts += hypothesis_contracts(jevs, pair=key, leg=leg,
                                              terms=pairs[key]["terms"], min_n=min_n)
        # ---- lake and cells: admitted pairs only; a held pair is stored in the report
        series_id = f"ws_expgap_{a}_{b}"
        by_at: dict[str, list[dict[str, Any]]] = {}
        for _, g in grows:
            by_at.setdefault(str(g["knowable_at"]), []).append(g)
        lake_rows = []
        for t, gs in sorted(by_at.items()):
            row: dict[str, Any] = {"available_time": t, "source_id": series_id}
            for sig, fld in zip(SIGNALS, ("sign", "magnitude", "percentile", "accel_z", "uadj"),
                                strict=True):
                vals = [float(g[fld]) for g in gs if _f(g.get(fld)) is not None]
                row[sig] = float(np.mean(vals)) if vals else None
            lake_rows.append(row)
        if not ok:
            lake_out[series_id] = {"status": "HELD_TERMS", "rows_kept_in_report": len(lake_rows),
                                   "why": why}
            cells_out[series_id] = {"status": "HELD_TERMS", "emitted": 0, "why": why}
            continue
        if lake_rows and not dry_run:
            lake_out[series_id] = se.write_lake_series(series_id, lake_rows, root=lake_root)
        else:
            lake_out[series_id] = {"rows": len(lake_rows),
                                   "status": "DRY_RUN" if dry_run else UNMEASURED}
        if lake_rows and emit_cells:
            cells_out[series_id] = se.emit_conditioner_cells(
                series_id, list(SIGNALS), list(legs), data_source=ds,
                mechanism=("prices move on the part of a print the market had not priced: the "
                           f"pre-release gap {a} - {b}, scaled by its uncertainty, carries that "
                           "part; its sign of transmission is measured per leg"),
                falsifier=FALSIFIER, generator=ENGINE, sides=(1, -1), dry_run=dry_run)
        else:
            cells_out[series_id] = {"status": UNMEASURED, "why": "no admitted gap rows"}
    # ---- the sensor ledger: each release's latest nowcast as state
    obs = []
    latest: dict[str, dict[str, Any]] = {}
    for r in all_rows:
        latest[r["release"]] = r
    for title, r in latest.items():
        nc = r["nowcast"]
        if nc.get("status") != "MEASURED":
            continue
        at = sc.parse_time(r["at"])
        obs.append(sc.make(
            sensor_id=ENGINE, source_id=f"alfred:{r['series']}", metric=f"{title}|nowcast",
            entity="US", kind="state", sensor_class="macro_nowcast", asset_domain="macro",
            value=nc["mean"], expected_value=nc["mean"], measurement_uncertainty=nc["sd"],
            acceleration=nc.get("acceleration"), delta=nc.get("revision"),
            event_time=at, knowable_at=at, knowable_basis="calendar",
            received_at=max(now, at) if at else now,
            attributes={"weights": nc.get("weights"), "contribution": nc.get("contribution"),
                        "gaps": {k: {f: g.get(f) for f in ("gap", "sd", "uadj", "terms")}
                                 for k, g in r["gaps"].items()}}))
    ledger_out: Any = {"status": "DRY_RUN"}
    if not dry_run:
        led = ledger if ledger is not None else sc.SensorLedger()
        ledger_out = led.append(obs, now=now) if obs else {"appended": 0}
        se.publish(ENGINE, contracts, root=contracts_root)
    doc = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"), "dry_run": dry_run,
           "accounting": acc, "rows": len(all_rows),
           "releases": sorted({r["release"] for r in all_rows}),
           "nowcasts_measured": sum(1 for r in all_rows
                                    if r["nowcast"].get("status") == "MEASURED"),
           "pairs": pairs, "legs": list(legs),
           "legs_without_bars": [leg for leg in legs if bars.get(leg) is None],
           "contracts": contracts,
           "verdicts": {v: sum(1 for c in contracts if c.get("verdict") == v)
                        for v in (se.GAIN, se.NO_GAIN, se.UNMEASURED)},
           "lake": lake_out, "cells": cells_out, "ledger": ledger_out,
           "latest": [{k: v for k, v in r.items() if k != "sensor_errors"}
                      for r in latest.values()],
           "authority": "NONE"}
    if not all_rows:
        doc["status"] = UNMEASURED
        doc["why"] = ("no release carried a first-print history on this host (ALFRED files "
                      f"missing: {len(acc.get('alfred_missing') or [])})")
    if not dry_run and report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        tmp = report.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        os.replace(tmp, report)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="multi-sensor nowcasts and expectation gaps")
    ap.add_argument("--days", type=int, default=1200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(now=datetime.now(UTC), days=a.days, dry_run=a.dry_run)
    print(json.dumps({k: doc.get(k) for k in ("at", "rows", "nowcasts_measured", "pairs",
                                              "verdicts", "status")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
