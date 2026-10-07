"""MACRO EVENT IMPLIED MOVE vs REALISED MOVE -- was the event's uncertainty over- or under-priced?

    python desks/mt5/macro/implied_move.py [--dry-run] [--days 4000]

WHY (completion audit #9, Quant Guild card QG25-06 "IV crush"): the desk measured release
surprises (event_surprise) but never what the market PRICED for the event before it, so it could
not say whether a CPI/NFP/FOMC/ECB/BoJ print moved its CFD more or less than options implied.

THE NUMBERS, per (event, CFD), all from FRED's republication of the CBOE indices (terms-admitted;
the Yahoo copy is held) and the desk's own broker closes:

    iv_pre          the 30-day index on the last trading day BEFORE the event day (the event is
                    inside its window); implied_move_pre = iv_pre / 100 / sqrt(252), the 1-day
                    sigma the index prices on the eve -- the PRE-EVENT state, knowable on the eve
    iv_post         the index on the event day (after the print); crush = iv_pre - iv_post
    implied_event   the event-day sigma backed out of the crush: with ~21 trading days in the
                    index window, event_var = (iv_pre^2 - iv_post^2) * 21/252 + iv_post^2 / 252
                    (floored at 0); the "IV crush" decomposition of the card, on an index
    realised        |log close(event day) / close(day before)| on this broker's own closes
    ratio           realised / (implied_move_pre * sqrt(2/pi)): above 1 the move beat what was
                    priced (uncertainty UNDER-priced), below 1 it fell short (OVER-priced)
    prior_ratio     the median ratio of the SAME event family's earlier events on this CFD -- the
                    desk's PIT estimate of whether this kind of event is usually over-priced

EVENTS. CPI and NFP release days are ALFRED's first-print vintages (`macro.release_vintages`),
stamped at their scheduled instant; FOMC/ECB/BOJ decisions come from
`research/forced_flow_calendar.CENTRAL_BANK_MEETINGS` (years it does not list are UNMEASURED).
BoJ has no FRED-republished yen vol index: its rows are UNMEASURED, never approximated.

POINT IN TIME. An index close of day d is held at d+1 09:00 ET (FRED's clock, market_state); a
post-event row (ratio, crush) is knowable when iv_post and the event-day close both are; the
pre-event row when iv_pre is. No row uses a later close.

THE CONTRACTS (sensor_engines):
    monotone: implied_move_pre ranks the realised event move                       QG25-06
    forecast: implied_move_pre^2 vs the trailing 20-day realised variance for the event day's
              squared return (QLIKE): does the eve's implied price the event better than RV
    gated:    ratio >= 1.5 (move beat the priced uncertainty) -> next-day reversal
    gated:    prior_ratio < 0.8 (family usually over-priced) -> event-day continuation is
              absent: the next-day trend cell is judged against ungated
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_engines as se  # noqa: E402

REPORT = DESK / "reports" / "IMPLIED_MOVE.json"
UNIVERSE_DIR = DESK / "data" / "universe"
ENGINE = "implied_move"
UNMEASURED = "UNMEASURED"
CARDS = ["QG25-06", "AUDIT-9"]
EVENT_MEAN_ABS = math.sqrt(2.0 / math.pi)
#: event family -> the ALFRED series whose first-print vintages date it (release_vintages titles)
RELEASE_FAMILIES: dict[str, str] = {"CPI": "USD CPI m/m", "NFP": "USD Non-Farm Employment Change"}
BANKS: dict[str, str] = {"FOMC": "FOMC", "ECB": "ECB", "BOJ": "BOJ"}
#: event family -> [(CFD candidates, FRED vol series)]
LEGS: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "CPI": [(("US500", "SPX500"), "VIXCLS"), (("NAS100", "USTEC"), "VXNCLS"),
            (("XAUUSD", "GOLD"), "GVZCLS"), (("EURUSD",), "EVZCLS")],
    "NFP": [(("US500", "SPX500"), "VIXCLS"), (("NAS100", "USTEC"), "VXNCLS"),
            (("XAUUSD", "GOLD"), "GVZCLS"), (("EURUSD",), "EVZCLS")],
    "FOMC": [(("US500", "SPX500"), "VIXCLS"), (("NAS100", "USTEC"), "VXNCLS"),
             (("XAUUSD", "GOLD"), "GVZCLS"), (("EURUSD",), "EVZCLS")],
    "ECB": [(("EURUSD",), "EVZCLS")],
    "BOJ": [],
}
SIGNALS = ("implied_move_pre", "prior_ratio", "ratio", "crush")


# ============================================================================== inputs
def release_events(folder: Path | None = None) -> list[tuple[str, datetime]]:
    """(family, instant) from ALFRED first prints. Absent ALFRED files give no rows."""
    from macro import release_vintages as rv
    out: list[tuple[str, datetime]] = []
    for fam, title in RELEASE_FAMILIES.items():
        spec = rv.BY_TITLE[title]
        try:
            df = rv.load_alfred(spec.series, folder or rv.ALFRED)
            prints = rv.release_vintage(df, spec) if df is not None else []
        except Exception:
            prints = []
        for p in prints:
            try:
                out.append((fam, rv.scheduled_utc(spec, date.fromisoformat(str(p["vintage"])))))
            except (KeyError, ValueError):
                continue
    return out


def bank_events(years: Sequence[int]) -> list[tuple[str, datetime]]:
    try:
        from research import forced_flow_calendar as ffc
    except Exception:
        try:
            import forced_flow_calendar as ffc  # type: ignore[no-redef]
        except Exception:
            return []
    from zoneinfo import ZoneInfo
    out: list[tuple[str, datetime]] = []
    for bank, spec in ffc.CENTRAL_BANK_MEETINGS.items():
        fam = BANKS.get(str(bank).upper())
        if fam is None:
            continue
        hh, mm = spec["at"]
        tz = ZoneInfo(str(spec["tz"]))
        for y in years:
            for month, _first, last in spec["days"].get(y) or []:
                out.append((fam, datetime(y, month, last, hh, mm, tzinfo=tz).astimezone(UTC)))
    return out


def fred_daily(series: Mapping[str, Sequence[tuple[str, float]]], sid: str) -> dict[str, float]:
    return {str(d)[:10]: float(v) for d, v in series.get(sid, [])}


def fred_series() -> dict[str, list[tuple[str, float]]]:
    try:
        from macro.market_state import load_series
        return load_series()
    except Exception:
        return {}


def fred_held_at(day: str, sid: str) -> datetime:
    from macro.market_state import knowable
    return knowable(day, sid)


def resolve(cands: Sequence[str], universe_dir: Path) -> str | None:
    from macro.vol_conditioner import resolve_symbol
    return resolve_symbol(cands, universe_dir)


def closes_for(symbol: str, universe_dir: Path) -> dict[str, float]:
    from macro.vol_conditioner import daily_closes
    return daily_closes(symbol, universe_dir)


# ============================================================================== the measurement
def measure(fam: str, at: datetime, iv: Mapping[str, float], closes: Mapping[str, float],
            iv_days: Sequence[str], close_days: Sequence[str]) -> dict[str, Any] | None:
    """One (event, CFD) row, or None when a needed close is missing."""
    import bisect
    ev_day = at.date().isoformat()
    k = bisect.bisect_left(iv_days, ev_day) - 1          # last index day strictly before
    if k < 0 or iv_days[min(k + 1, len(iv_days) - 1)] != ev_day:
        return None
    pre_day, iv_pre, iv_post = iv_days[k], iv[iv_days[k]], iv[ev_day]
    j = bisect.bisect_left(close_days, ev_day)
    if j < 21 or j >= len(close_days) - 1 or close_days[j] != ev_day:
        return None
    c_prev, c_ev, c_next = (closes[close_days[j - 1]], closes[ev_day],
                            closes[close_days[j + 1]])
    if min(c_prev, c_ev, c_next) <= 0:
        return None
    r_ev = math.log(c_ev / c_prev)
    r_next = math.log(c_next / c_ev)
    past = [math.log(closes[close_days[i]] / closes[close_days[i - 1]])
            for i in range(j - 20, j)]
    rv20 = statistics.pvariance(past) if len(past) > 2 else None
    sig_pre = iv_pre / 100.0 / math.sqrt(252.0)
    event_var = max(0.0, ((iv_pre / 100) ** 2 - (iv_post / 100) ** 2) * 21 / 252
                    + (iv_post / 100) ** 2 / 252)
    return {"family": fam, "event_at": at.isoformat(), "event_day": ev_day,
            "pre_day": pre_day, "iv_pre": iv_pre, "iv_post": iv_post,
            "implied_move_pre": sig_pre, "implied_event": math.sqrt(event_var),
            "crush": iv_pre - iv_post, "realised": abs(r_ev),
            "ratio": abs(r_ev) / (sig_pre * EVENT_MEAN_ABS) if sig_pre > 0 else None,
            "r_event": r_ev, "r_next": r_next, "rv20": rv20}


def attach_prior(rows: list[dict[str, Any]]) -> None:
    """prior_ratio: the median ratio of the same family's STRICTLY EARLIER events."""
    seen: dict[str, list[float]] = {}
    for r in sorted(rows, key=lambda r: r["event_at"]):
        hist = seen.setdefault(r["family"], [])
        r["prior_ratio"] = statistics.median(hist) if len(hist) >= 5 else None
        if r.get("ratio") is not None:
            hist.append(float(r["ratio"]))


def contracts(symbol: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda r: r["event_at"])
    rev = [-math.copysign(1.0, r["r_event"]) * r["r_next"] if r["r_event"] else 0.0
           for r in rows]
    trend = [math.copysign(1.0, r["r_event"]) * r["r_next"] if r["r_event"] else 0.0
             for r in rows]
    common = {"engine": ENGINE, "cards": CARDS}
    out = [
        se.monotone_gain([r["implied_move_pre"] for r in rows], [r["realised"] for r in rows],
                         **common, min_n=60,
                         falsifier="the eve's implied move does not rank the event's move"),
        se.forecast_gain([r["r_event"] ** 2 for r in rows],
                         [r["implied_move_pre"] ** 2 for r in rows],
                         [r["rv20"] if r["rv20"] else float("nan") for r in rows], **common,
                         loss="qlike", block=4, min_n=60,
                         baseline="trailing 20-day realised variance",
                         falsifier="the eve's implied variance forecasts the event day no "
                                   "better than trailing realised variance"),
        se.gated_gain(rev, [r["ratio"] is not None and r["ratio"] >= 1.5 for r in rows],
                      **common, min_n=60, min_active=10,
                      baseline="next-day reversal after every event",
                      falsifier="after a move beyond the priced uncertainty, the next day "
                                "reverts no more than after any event"),
        se.gated_gain(trend, [r["prior_ratio"] is not None and r["prior_ratio"] < 0.8
                              for r in rows], **common, min_n=60, min_active=10,
                      baseline="next-day continuation after every event",
                      falsifier="continuation after usually over-priced families is no "
                                "different from after any event"),
    ]
    for c, lbl in zip(out, ("implied_pre->|move|", "implied_pre^2->event_var",
                            "underpriced->reversal", "overpriced_family->trend"), strict=True):
        c.update({"label": lbl, "symbol": symbol})
    return out


def lake_rows(rows: list[dict[str, Any]], sid: str) -> list[dict[str, Any]]:
    """Two rows per event: the eve's state (implied, prior) and the post-event measurement."""
    out = []
    for r in rows:
        out.append({"available_time": fred_held_at(r["pre_day"], sid).isoformat(),
                    "event_time": r["pre_day"], "implied_move_pre": r["implied_move_pre"],
                    "prior_ratio": r["prior_ratio"], "family": r["family"]})
        post = max(fred_held_at(r["event_day"], sid),
                   datetime.fromisoformat(r["event_day"]).replace(tzinfo=UTC)
                   + timedelta(hours=25))
        out.append({"available_time": post.isoformat(), "event_time": r["event_day"],
                    "ratio": r["ratio"], "crush": r["crush"],
                    "implied_event": r["implied_event"], "family": r["family"]})
    return out


def run(*, dry_run: bool = False, universe_dir: Path = UNIVERSE_DIR, days: int = 4000,
        now: datetime | None = None, series: Mapping[str, Sequence[tuple[str, float]]] | None
        = None, events: Sequence[tuple[str, datetime]] | None = None) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    fred = fred_series() if series is None else series
    if events is None:
        years = list(range((when - timedelta(days=days)).year, when.year + 1))
        events = [*release_events(), *bank_events(years)]
    events = sorted({(f, a) for f, a in events if when - timedelta(days=days) <= a <= when},
                    key=lambda e: e[1])
    per_symbol: dict[str, dict[str, Any]] = {}
    unmeasured: dict[str, str] = {}
    for fam, legs in LEGS.items():
        if not legs:
            unmeasured[fam] = "no FRED-republished implied-vol index for this event's market"
        if not any(f == fam for f, _ in events):
            unmeasured.setdefault(fam, "no dated event of this family on this host")
        for cands, vol_sid in legs:
            iv = fred_daily(fred, vol_sid)
            sym = resolve(cands, universe_dir)
            if not iv or sym is None:
                continue
            closes = closes_for(sym, universe_dir)
            if not closes:
                continue
            ivd, cld = sorted(iv), sorted(closes)
            slot = per_symbol.setdefault(sym, {"rows": [], "vol": vol_sid})
            for f, at in events:
                if f != fam:
                    continue
                m = measure(f, at, iv, closes, ivd, cld)
                if m is not None:
                    post = fred_held_at(m["event_day"], vol_sid)
                    if post <= when:
                        slot["rows"].append(m)
    report: dict[str, Any] = {"at": when.isoformat(timespec="seconds"), "engine": ENGINE,
                              "cards": CARDS, "n_events": len(events), "unmeasured": unmeasured,
                              "symbols": {}, "contracts": [], "authority": "NONE",
                              "measure": "Q (index-implied) against P (broker realised)"}
    obs: list[Any] = []
    for sym, slot in per_symbol.items():
        rows = slot["rows"]
        attach_prior(rows)
        cs = contracts(sym, rows)
        report["contracts"].extend(cs)
        sid = f"ws_event_implied_move_{sym.lower()}"
        data_source = f"fred:{slot['vol']}"
        by_fam: dict[str, list[float]] = {}
        for r in rows:
            if r["ratio"] is not None:
                by_fam.setdefault(r["family"], []).append(float(r["ratio"]))
        info: dict[str, Any] = {
            "events": len(rows), "data_source": data_source, "series_id": sid,
            "median_ratio_by_family": {f: round(statistics.median(v), 4)
                                       for f, v in by_fam.items()},
            "verdict_by_family": {f: ("UNDER_PRICED" if statistics.median(v) > 1.1 else
                                      "OVER_PRICED" if statistics.median(v) < 0.9 else
                                      "FAIRLY_PRICED") if len(v) >= 12 else UNMEASURED
                                  for f, v in by_fam.items()},
            "last": rows[-1] if rows else None}
        if not dry_run and rows:
            info["lake"] = se.write_lake_series(sid, lake_rows(rows, slot["vol"]))
            info["cells"] = se.emit_conditioner_cells(
                sid, list(SIGNALS), [sym],
                mechanism=(f"{sym}: what the eve's implied vol priced for a scheduled macro event "
                           f"against what the event delivered; under-priced uncertainty "
                           f"overshoots, over-priced event families under-deliver"),
                falsifier="gate effect indistinguishable from the shuffled-state gate across "
                          "the judged cells", generator=ENGINE, sides=(1, -1),
                data_source=data_source)
            obs.extend(observations(sym, rows[-1], data_source, when))
        report["symbols"][sym] = info
    if not per_symbol:
        report["status"] = UNMEASURED
        report["why"] = ("no (event, CFD) pair with a FRED vol index, broker closes and a dated "
                         "event on this host")
    if not dry_run:
        se.publish(ENGINE, report["contracts"])
        if obs:
            try:
                from libs.research import sensor_contract as sc
                report["ledger"] = sc.SensorLedger().append(obs)
            except Exception as exc:
                report["ledger"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return report


def observations(sym: str, last: Mapping[str, Any], data_source: str, now: datetime
                 ) -> list[Any]:
    from libs.research import sensor_contract as sc
    sid = data_source.split(":", 1)[1]
    know = fred_held_at(str(last["event_day"]), sid)
    rx = max(now, know)
    out = []
    for metric in ("implied_move_pre", "implied_event", "realised", "ratio", "crush"):
        v = last.get(metric)
        if not isinstance(v, int | float):
            continue
        out.append(sc.make(sensor_id="market:event_implied_move", source_id=data_source,
                           metric=f"{last['family']}_{metric}", entity=sym, kind="state",
                           sensor_class="market_state", asset_domain="vol", value=float(v),
                           event_time=last["event_at"], knowable_at=know.isoformat(),
                           knowable_basis="declared_lag", received_at=rx,
                           parse_complete_at=rx, licence="CBOE index values republished by FRED",
                           commercial_rights=UNMEASURED,
                           attributes={"measure": "Q vs P", "prior_ratio": last.get(
                               "prior_ratio")}))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="macro event implied vs realised move (audit #9)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=4000)
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run, days=args.days)
    text = json.dumps(rep, indent=1, sort_keys=True, default=str)
    if args.dry_run:
        print(text[:4000])
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(text + "\n", "utf-8")
    tmp.replace(REPORT)
    v = [c.get("verdict") for c in rep["contracts"]]
    print(f"implied_move: symbols={len(rep['symbols'])} contracts={len(v)} "
          f"GAIN={v.count('GAIN')} NO_GAIN={v.count('NO_GAIN')} UNMEASURED={v.count('UNMEASURED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
