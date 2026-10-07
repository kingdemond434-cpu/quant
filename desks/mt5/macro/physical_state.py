"""PHYSICAL COMMODITY STATES -- US petroleum inventories against their own seasonal norm, as states
for the sensor ledger and as SURPRISES for the event-reaction gauntlet.

WHY (principal 2026-10-05, "PHYSICAL COMMODITY STATES"): the desk trades USOIL and UKOIL and read
no physical inventory at all. The EIA's Weekly Petroleum Status Report is public, weekly and
point-in-time by its release, and FRED carries its headline stocks. China and Asia physical
states are the Asia thread's; this is the US balance.

WHAT A WEEK CARRIES, per series (crude ex SPR, SPR, gasoline, distillate; refinery utilisation as
a level):
    level, weekly change
    seasonal_expected   mean change in the same ISO week (+/-1) over the five PRIOR years: a
                        declared naive expectation that needs no survey, so it has history today
    surprise            change - seasonal_expected
    level_vs_norm       level - mean same-week level over the five prior years, and the level's
                        percentile inside that five-year same-week range
A licensed analyst consensus for the weekly print is not free; it is UNMEASURED and the
seasonal expectation is written under its own release id so the two can never be mixed.

THE CLOCK (audit #211 item 1). FRED dates a week by its END (Friday); the EIA publishes it the
following Wednesday at 10:30 ET. A federal holiday on the Monday, Tuesday or Wednesday of the
release week moves the report to Thursday 11:00 ET; a Christmas-week Wednesday holiday has moved it
to Friday, stamped Friday 12:00 ET. Holidays are computed by rule (`us_federal_holidays`), and a
publication the EIA made earlier than this stamp only makes a measured reaction later, never
earlier. `RELEASE_OVERRIDES` records any irregular week the EIA announces, by week-end date.

THE CONSUMER. `store_rows` hands (actual change, seasonal expectation) pairs to `event_surprise`,
which standardises each release on its OWN history and measures the USOIL/UKOIL reaction per
bucket through the gauntlet's door. Nothing here has a direction.

EVENT TO SCALE (DATA-26). `main` also runs `macro/supply_scale.py`: each supply-type event in the
news stream's log is translated into lost output, share of global and regional supply, expected
duration and cushion (spare capacity, and this report's crude inventory vs norm) from the
declared capacity table, with the OPEC+ quota/compliance state; PHYSICAL_STATE.json carries both
as `event_scale` and `opec`.
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
ARCHIVE = ROOT / "data" / "fred_market_state.json"
REPORT = DESK / "reports" / "PHYSICAL_STATE.json"
UNMEASURED = "UNMEASURED"
ET = ZoneInfo("America/New_York")
SEASON_YEARS = 5
OIL = ["USOIL", "UKOIL"]

#: FRED id -> (release name, unit, instruments, is_stock)
SERIES: dict[str, tuple[str, str, list[str], bool]] = {
    "WCESTUS1": ("EIA crude oil stocks ex SPR", "kbbl", OIL, True),
    "WCSSTUS1": ("EIA SPR crude stocks", "kbbl", OIL, True),
    "WGTSTUS1": ("EIA gasoline stocks", "kbbl", OIL, True),
    "WDISTUS1": ("EIA distillate stocks", "kbbl", OIL, True),
    "WPULEUS3": ("EIA refinery utilisation", "%", OIL, False),
}


#: week-end date -> the EIA's announced release instant in ET ("YYYY-MM-DDTHH:MM"), for weeks the
#: rule below does not describe. Empty until the EIA announces one.
RELEASE_OVERRIDES: dict[str, str] = {}
#: Stamped on every store row. Rows written under an earlier clock (the +1 day stamp, the ISO-week
#: norm) are superseded: `event_surprise.store_pairs` reads only this clock's inventory rows, and
#: every week is regenerated from FRED on each pass, so nothing is lost.
CLOCK = "eia_wpsr_calendar_v3"


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_monday(year: int, month: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return nxt - timedelta(days=nxt.weekday())


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else (
        d + timedelta(days=1) if d.weekday() == 6 else d)


def us_federal_holidays(year: int) -> dict[date, str]:
    """The eleven US federal holidays (5 U.S.C. 6103), observed Fri/Mon when on a weekend."""
    out = {
        _observed(date(year, 1, 1)): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        _last_monday(year, 5): "Memorial Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 10, 0, 2): "Columbus Day",
        _observed(date(year, 11, 11)): "Veterans Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
        _observed(date(year, 12, 25)): "Christmas Day",
    }
    if year >= 2021:
        out[_observed(date(year, 6, 19))] = "Juneteenth"
    # New Year's Day of next year observed on Friday 31 December belongs to this year
    nxt = date(year + 1, 1, 1)
    if nxt.weekday() == 5:
        out[date(year, 12, 31)] = "New Year's Day (observed)"
    return out


def release_at(week_end: str) -> tuple[datetime, str]:
    """(the EIA WPSR release instant for the week ending `week_end`, why)."""
    d = date.fromisoformat(week_end[:10])
    wed = d + timedelta(days=(2 - d.weekday()) % 7 or 7)
    if week_end[:10] in RELEASE_OVERRIDES:
        at = datetime.fromisoformat(RELEASE_OVERRIDES[week_end[:10]]).replace(tzinfo=ET)
        return at.astimezone(UTC), "announced override"
    mon = wed - timedelta(days=2)
    hol = {**us_federal_holidays(mon.year), **us_federal_holidays(wed.year)}
    hit = [(day, hol[day]) for day in (mon, mon + timedelta(days=1), wed) if day in hol]
    if not hit:
        xmas = date(wed.year, 12, 25)
        if wed < xmas <= wed + timedelta(days=2):
            # CHRISTMAS ON THE THURSDAY OR FRIDAY (audit #211, 2026-10-07): the 2025 release came
            # 126.5 h after the Wednesday stamp, with the executive-order closures either side. No
            # rule describes those, so the stamp is a CONSERVATIVE BOUND -- the Tuesday after,
            # 12:00 ET -- which can only arrive late, never early, until the announced date is
            # recorded in RELEASE_OVERRIDES.
            tue = wed + timedelta(days=6)
            return datetime(tue.year, tue.month, tue.day, 12, 0, tzinfo=ET).astimezone(UTC), \
                "Christmas on Thursday/Friday: conservative bound, Tuesday after 12:00 ET"
        return datetime(wed.year, wed.month, wed.day, 10, 30, tzinfo=ET).astimezone(UTC), \
            "Wednesday 10:30 ET"
    day, name = hit[-1]
    if day == wed and name.startswith("Christmas"):
        fri = wed + timedelta(days=2)
        return datetime(fri.year, fri.month, fri.day, 12, 0, tzinfo=ET).astimezone(UTC), \
            f"{name} on Wednesday: Friday 12:00 ET"
    # a Mon-Wed holiday moves the release to Thursday NOON ET (audit #211: 11:00 stamped an
    # hour before the print on every holiday week)
    thu = wed + timedelta(days=1)
    return datetime(thu.year, thu.month, thu.day, 12, 0, tzinfo=ET).astimezone(UTC), \
        f"{name} ({day.isoformat()}): Thursday 12:00 ET"


def knowable(week_end: str) -> datetime:
    """The instant the week ending `week_end` is public: the EIA release calendar."""
    return release_at(week_end)[0]


def load(path: Path = ARCHIVE) -> dict[str, list[tuple[str, float]]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, list[tuple[str, float]]] = {}
    for sid in SERIES:
        rows = ((doc or {}).get("series") or {}).get(sid) or []
        clean = []
        for r in rows:
            try:
                v = float(r[1])
            except (TypeError, ValueError, IndexError):
                continue
            if math.isfinite(v):
                clean.append((str(r[0])[:10], v))
        if clean:
            out[sid] = sorted(clean)
    return out


#: a prior year's "same week" is every weekly print within this many days of the same calendar
#: date that year: +/-1 week, by date, so week 1 neighbours week 52 and ISO week 53 has a norm
NEAR_DAYS = 10


def _same_date(d: date, back: int) -> date:
    try:
        return d.replace(year=d.year - back)
    except ValueError:                                   # 29 February
        return d.replace(year=d.year - back, day=28)


def weeks(rows: Sequence[tuple[str, float]]) -> list[dict[str, Any]]:
    """Every week with its change, seasonal expectation, surprise and level vs norm."""
    changes = [(date.fromisoformat(rows[i][0][:10]), rows[i][1] - rows[i - 1][1], rows[i][1])
               for i in range(1, len(rows))]
    days = [c[0] for c in changes]
    out: list[dict[str, Any]] = []
    for day, chg, level in changes:
        d = day.isoformat()
        prior: list[tuple[float, float, int]] = []
        for back in range(1, SEASON_YEARS + 1):
            target = _same_date(day, back)
            lo = bisect.bisect_left(days, target - timedelta(days=NEAR_DAYS))
            hi = bisect.bisect_right(days, target + timedelta(days=NEAR_DAYS))
            prior += [(changes[j][1], changes[j][2], back) for j in range(lo, hi)]
        row: dict[str, Any] = {"week_end": d, "level": level, "change": chg,
                               "knowable_at": knowable(d).isoformat()}
        if len({yy for _c, _lv, yy in prior}) < SEASON_YEARS:
            row["seasonal_expected"] = None
            row["why"] = f"fewer than {SEASON_YEARS} prior years of the same week"
        else:
            exp = sum(c for c, _lv, _y in prior) / len(prior)
            levels = [lv for _c, lv, _y in prior]
            norm = sum(levels) / len(levels)
            row.update({"seasonal_expected": exp, "surprise": chg - exp,
                        "level_vs_norm": level - norm,
                        "level_percentile_5y": round(
                            (sum(1 for v in levels if v < level)
                             + 0.5 * sum(1 for v in levels if v == level)) / len(levels), 4)})
        out.append(row)
    return out


def build(*, now: datetime | None = None,
          series: Mapping[str, list[tuple[str, float]]] | None = None) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    ser = load() if series is None else series
    report: dict[str, Any] = {"at": when.isoformat(timespec="seconds"), "source": "physical_state",
                              "series": {}, "store_rows": []}
    for sid, (name, unit, instruments, is_stock) in SERIES.items():
        rows = [r for r in ser.get(sid, []) if knowable(r[0]) <= when]
        if len(rows) < 2:
            report["series"][sid] = {"name": name, "status": UNMEASURED,
                                     "why": "absent from fred_market_state.json as of now"}
            continue
        wk = weeks(rows)
        last = wk[-1]
        surprises = [w["surprise"] for w in wk[:-1] if w.get("surprise") is not None]
        z = None
        if last.get("surprise") is not None and len(surprises) >= 20:
            m = sum(surprises) / len(surprises)
            sd = math.sqrt(sum((s - m) ** 2 for s in surprises) / (len(surprises) - 1))
            z = round((last["surprise"] - m) / sd, 4) if sd > 0 else None
        report["series"][sid] = {"name": name, "unit": unit, "status": "MEASURED",
                                 "kind": "stock" if is_stock else "rate", **last,
                                 "surprise_z": z, "weeks": len(wk)}
        if not is_stock:
            continue
        for w in wk:
            if w.get("seasonal_expected") is None:
                continue
            rel = date.fromisoformat(w["knowable_at"][:10])
            report["store_rows"].append({
                "release": f"{name} w/w|seasonal{SEASON_YEARS}y", "period": rel.isoformat(),
                "reference_period": w["week_end"], "at": w["knowable_at"],
                "actual": round(w["change"] / 1000.0, 4),
                "consensus": round(w["seasonal_expected"] / 1000.0, 4),
                "provides": "both", "kind": "inventory_surprise", "instruments": instruments,
                "expectation_kind": f"seasonal_{SEASON_YEARS}y", "unit": "mbbl",
                "source_id": f"fred:{sid}", "consensus_median": UNMEASURED,
                "clock": CLOCK, "clock_why": release_at(w["week_end"])[1]})
    measured = [s for s in report["series"].values() if s.get("status") == "MEASURED"]
    report["status"] = "present" if measured else UNMEASURED
    return report


def store_rows(now: datetime | None = None) -> dict[str, Any]:
    """For `event_surprise`: the pairs plus a census, never raising."""
    try:
        rep = build(now=now)
    except Exception as exc:                             # pragma: no cover - guarded organ
        return {"rows": [], "census": {"status": UNMEASURED,
                                       "why": f"{type(exc).__name__}: {str(exc)[:120]}"}}
    return {"rows": rep["store_rows"],
            "census": {"status": rep["status"], "rows": len(rep["store_rows"]),
                       "series": {k: v.get("status") for k, v in rep["series"].items()}}}


def observations(report: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    out = []
    for sid, row in (report.get("series") or {}).items():
        if row.get("status") != "MEASURED":
            continue
        exp = row.get("seasonal_expected")
        out.append(sc.make(
            sensor_id="physical:eia_wpsr", source_id=f"fred:{sid}", dataset_id="eia_wpsr",
            metric=row["name"], entity="US", geography="US", asset_domain="energy",
            sensor_class="physical_commodity", kind="state", value=row["level"],
            unit=row["unit"], event_time=row["week_end"], scheduled_time=row["knowable_at"],
            publication_time=row["knowable_at"], knowable_at=row["knowable_at"],
            knowable_basis="calendar",
            received_at=max(received_at, datetime.fromisoformat(row["knowable_at"])),
            parse_complete_at=max(received_at, datetime.fromisoformat(row["knowable_at"])),
            delta=row["change"], seasonal_expected=exp,
            expected_value=exp, surprise_z=row.get("surprise_z"),
            percentile=row.get("level_percentile_5y"),
            licence="EIA: US government public domain (via FRED)",
            commercial_rights="public domain", attributes={"surprise": row.get("surprise"),
                                                           "level_vs_norm": row.get(
                                                               "level_vs_norm")}))
    return out


def scale_block(rep: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """DATA-26: the event-to-scale estimator and OPEC+ compliance (`macro/supply_scale.py`),
    with this report's own crude inventory vs norm as the cushion. UNMEASURED if it raises."""
    try:
        from macro import supply_scale as ss
        return ss.build(now=now, physical=rep)
    except Exception as exc:                             # pragma: no cover - organ guard
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:160]}"}


def main(argv: list[str] | None = None) -> int:
    now = datetime.now(UTC)
    rep = build(now=now)
    scale = scale_block(rep, now)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({k: v for k, v in rep.items() if k != "store_rows"} |
                                 {"n_store_rows": len(rep["store_rows"]),
                                  "event_scale": {k: v for k, v in scale.items()
                                                  if k != "opec"},
                                  "opec": scale.get("opec")},
                                 indent=1, default=str), "utf-8")
    try:
        from libs.research import sensor_contract as sc
        rows = observations(rep, now)
        try:
            from macro import supply_scale as ss
            rows += ss.observations(scale, now)
        except Exception:                                # pragma: no cover - ledger guard
            pass
        led = sc.SensorLedger().append(rows)
    except Exception as exc:                             # pragma: no cover - ledger guard
        led = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    print(f"physical_state status={rep['status']} pairs={len(rep['store_rows'])} ledger={led}")
    return 0


if __name__ == "__main__":
    for _p in (str(ROOT), str(DESK)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    raise SystemExit(main())
