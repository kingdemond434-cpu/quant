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

THE CLOCK. FRED dates a week by its END (Friday); the EIA publishes it the following Wednesday at
10:30 ET. Holiday weeks slip a day; the clock here is the declared Wednesday and a holiday shift
makes it at worst a day EARLY in knowledge terms -- so every pair is stamped one day later than
the schedule, which can only make a measured reaction later, never earlier.

THE CONSUMER. `store_rows` hands (actual change, seasonal expectation) pairs to `event_surprise`,
which standardises each release on its OWN history and measures the USOIL/UKOIL reaction per
bucket through the gauntlet's door. Nothing here has a direction.
"""
from __future__ import annotations

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


def knowable(week_end: str) -> datetime:
    """Wednesday after the week-ending date, 10:30 ET, plus the declared one-day holiday margin."""
    d = date.fromisoformat(week_end[:10])
    wed = d + timedelta(days=(2 - d.weekday()) % 7 or 7)
    return (datetime(wed.year, wed.month, wed.day, 10, 30, tzinfo=ET).astimezone(UTC)
            + timedelta(days=1))


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


def _week(d: str) -> tuple[int, int]:
    iso = date.fromisoformat(d).isocalendar()
    return iso[0], iso[1]


def _near_week(a: int, b: int) -> bool:
    diff = abs(a - b)
    return min(diff, 52 - diff) <= 1


def weeks(rows: Sequence[tuple[str, float]]) -> list[dict[str, Any]]:
    """Every week with its change, seasonal expectation, surprise and level vs norm."""
    changes = [(rows[i][0], rows[i][1] - rows[i - 1][1], rows[i][1], *_week(rows[i][0]))
               for i in range(1, len(rows))]
    by_year: dict[int, list[tuple[int, float, float]]] = {}
    for _d, c, lv, y, w in changes:
        by_year.setdefault(y, []).append((w, c, lv))
    out: list[dict[str, Any]] = []
    for d, chg, level, y, w in changes:
        prior = [(c, lv, yy) for yy in range(y - SEASON_YEARS, y)
                 for ww, c, lv in by_year.get(yy, []) if _near_week(ww, w)]
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
                "source_id": f"fred:{sid}", "consensus_median": UNMEASURED})
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
            knowable_basis="declared_lag",
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


def main(argv: list[str] | None = None) -> int:
    rep = build()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({k: v for k, v in rep.items() if k != "store_rows"} |
                                 {"n_store_rows": len(rep["store_rows"])},
                                 indent=1, default=str), "utf-8")
    try:
        from libs.research import sensor_contract as sc
        led = sc.SensorLedger().append(observations(rep, datetime.now(UTC)))
    except Exception as exc:                             # pragma: no cover - ledger guard
        led = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    print(f"physical_state status={rep['status']} pairs={len(rep['store_rows'])} ledger={led}")
    return 0


if __name__ == "__main__":
    for _p in (str(ROOT), str(DESK)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    raise SystemExit(main())
