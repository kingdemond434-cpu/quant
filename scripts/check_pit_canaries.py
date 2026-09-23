"""PLANTED POINT-IN-TIME CANARIES -- proof, every hour, that a value cannot be read before it
was available.

THE CLOSED-LOOP ATTESTATION ASKS `truth.pit_canaries_green` and no census carried a canary
block (2026-09-16). This plants three rows into a frame the way every stamped source is
stamped (`libs.data.pit_stamp.stamp_frame`: event_time, available_time, ingested_time) -- one
whose availability is in the past, one exactly now, one in the FUTURE -- and asks the only
question that matters: does a point-in-time read at `now` return the future row? Green means
no. A canary that could not be planted, or a stamp module that cannot be imported, is UNMEASURED
and the attestation reads it as open, never as green.

    python scripts/check_pit_canaries.py     -> desks/mt5/reports/PIT_CENSUS.json
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "PIT_CENSUS.json"
LAKE = DESK / "data" / "lake"


def _sidecar_census() -> dict[str, Any]:
    """How many parser sidecars carry PIT stamps on this box: the census half."""
    try:
        side = list(LAKE.rglob("*.pit.json"))
    except OSError:
        side = []
    stamped = 0
    for p in side[:5000]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("available_time"):
                stamped += 1
        except (OSError, ValueError):
            continue
    return {"sidecars": len(side), "stamped": stamped}


def plant_and_read(now: datetime | None = None) -> dict[str, Any]:
    """Plant past/now/future rows and read them point-in-time. Pure over `now`."""
    now = now or datetime.now(tz=UTC)
    try:
        import pandas as pd

        from libs.data.pit_stamp import stamp_frame
    except Exception as exc:
        return {"green": None, "why": f"pit_stamp unavailable ({type(exc).__name__}: {exc})"}
    periods = [now - timedelta(days=3), now - timedelta(days=1), now + timedelta(days=2)]
    df = pd.DataFrame({"period_end": [p.date().isoformat() for p in periods],
                       "value": [1.0, 2.0, 3.0]})
    try:
        res = stamp_frame(df, lag_days=1, observed_at=now)
    except Exception as exc:
        return {"green": None, "why": f"stamp_frame raised ({type(exc).__name__}: {exc})"}
    stamped = next((x for x in (res if isinstance(res, tuple) else (res,))
                    if hasattr(x, "columns")), None)
    if stamped is None or "available_time" not in stamped.columns:
        return {"green": None, "why": "stamp_frame produced no available_time column"}
    avail = pd.to_datetime(stamped["available_time"], utc=True, errors="coerce")
    visible = stamped[avail <= pd.Timestamp(now)]
    future_leaked = bool((visible["value"] == 3.0).any())
    past_seen = bool((visible["value"] == 1.0).any())
    # THE ENVELOPE IS PART OF THE CANARY (blueprint item 2): a stamp that lacks the published /
    # retrieval / source / vintage fields is not the point-in-time envelope the desk declares.
    wanted = ("event_time", "published_time", "available_time", "retrieval_time", "source_id",
              "vintage_id")
    missing = [c for c in wanted if c not in stamped.columns]
    return {
        "green": (not future_leaked) and past_seen and not missing,
        "planted": 3, "visible_at_now": len(visible),
        "future_row_leaked": future_leaked, "past_row_visible": past_seen,
        "envelope_missing": missing,
        "why": (f"the stamp lacks {missing}" if missing else
                "a point-in-time read at now returned only rows whose available_time had passed"
                if (not future_leaked and past_seen) else
                "the future row was readable before its available_time" if future_leaked else
                "the past row was not readable although its available_time had passed"),
    }


#: The two series the canary keeps planted in the lake itself. They are rewritten every run with
#: a fresh stamp, they carry no values any strategy reads, and their source ids are in no
#: registry -- so the only organ that can ever be affected by them is one that reads the lake
#: WITHOUT joining on available_time, which is precisely what they exist to catch.
CANARY_FUTURE = "pit_canary_future"
CANARY_PAST = "pit_canary_past"


def plant_in_lake(now: datetime) -> dict[str, Any]:
    """Plant the two canary series, with sidecars, in the lake consumers actually read."""
    series = LAKE / "series"
    try:
        series.mkdir(parents=True, exist_ok=True)
        for sid, avail in ((CANARY_FUTURE, now + timedelta(days=30)),
                           (CANARY_PAST, now - timedelta(days=30))):
            (series / f"{sid}.json").write_text(
                json.dumps({"canary": sid, "value": 0.0,
                            "note": "planted by scripts/check_pit_canaries.py; no strategy "
                                    "reads it, and a consumer that joins on available_time "
                                    "cannot see the future one"}, indent=1), encoding="utf-8")
            (series / f"{sid}.pit.json").write_text(
                json.dumps({"source_id": sid, "event_time": now.isoformat(timespec="seconds"),
                            "available_time": avail.isoformat(timespec="seconds"),
                            "ingested_time": now.isoformat(timespec="seconds"),
                            "source_version": "canary", "revision": 0}, indent=1),
                encoding="utf-8")
    except OSError as exc:
        return {"planted": False, "why": f"could not plant into the lake ({exc})"}
    return {"planted": True, "series_dir": str(series)}


def ask_consumers(now: datetime) -> dict[str, Any]:
    """Do the lake's consumers refuse the planted FUTURE series? Green only when every consumer
    that was asked cannot see it and can see the past one.

    THE CANARY IS ONLY A CANARY WHERE SOMEONE BREATHES. A planted row that no consumer reads
    proves nothing about the desk; these two ask the join library and the organ that decides
    which sources the desk "has data for", which is the read that converts a source into cells.
    """
    rows: list[dict[str, Any]] = []
    try:
        from libs.data.lake_pit import usable_series
        view = usable_series(LAKE / "series", now)
        rows.append({"consumer": "libs.data.lake_pit.usable_series",
                     "joins_on_available_time": True,
                     "future_visible": CANARY_FUTURE in view.visible,
                     "past_visible": CANARY_PAST in view.visible,
                     "n_withheld": len(view.withheld), "n_unstamped": len(view.unstamped)})
    except Exception as exc:
        rows.append({"consumer": "libs.data.lake_pit.usable_series", "error": f"{type(exc).__name__}: {exc}"})
    try:
        sys.path.insert(0, str(DESK))
        from research.asia_plane import _have_data
        have = _have_data(now)
        rows.append({"consumer": "desks/mt5/research/asia_plane.py::_have_data",
                     "joins_on_available_time": True,
                     "future_visible": CANARY_FUTURE in have,
                     "past_visible": CANARY_PAST in have, "n_sources_visible": len(have)})
    except Exception as exc:
        rows.append({"consumer": "desks/mt5/research/asia_plane.py::_have_data",
                     "error": f"{type(exc).__name__}: {exc}"})
    asked = [r for r in rows if "error" not in r]
    leaked = [r["consumer"] for r in asked if r.get("future_visible")]
    blind = [r["consumer"] for r in asked if not r.get("past_visible")]
    return {"green": bool(asked) and not leaked and not blind,
            "n_asked": len(asked), "n_error": len(rows) - len(asked),
            "leaked_to": leaked, "past_invisible_to": blind, "consumers": rows,
            "why": (f"{len(leaked)} consumer(s) read the planted FUTURE series: {leaked}"
                    if leaked else
                    f"{len(blind)} consumer(s) could not read the planted PAST series: {blind}"
                    if blind else
                    f"{len(asked)} lake consumer(s) join on available_time: the future series is "
                    f"invisible to all of them and the past series is visible to all of them"
                    if asked else "no lake consumer could be asked: UNMEASURED")}


def main() -> int:
    now = datetime.now(tz=UTC)
    frame = plant_and_read(now)
    planted = plant_in_lake(now)
    lake = ask_consumers(now) if planted.get("planted") else {
        "green": None, "why": str(planted.get("why") or "nothing planted"), "consumers": []}
    # ONE VERDICT, AND IT IS THE CONJUNCTION. The frame canary proves the stamping library
    # refuses a future row; the lake canary proves the desk's own consumers do. Green means both,
    # and an UNMEASURED half can never make the pair green (L1.28a).
    green = (None if (frame.get("green") is None or lake.get("green") is None)
             else bool(frame.get("green")) and bool(lake.get("green")))
    canaries = {**frame, "green": green, "frame_green": frame.get("green"),
                "lake": {**planted, **lake},
                "why": f"frame: {frame.get('why')}; lake: {lake.get('why')}"}
    doc = {"at": now.isoformat(timespec="seconds"), "canaries": canaries,
           "census": _sidecar_census(),
           "rule": "green only when the planted future row is invisible at now and the past row "
                   "is visible -- in the stamping library AND in the lake's own consumers; "
                   "unmeasured is never green"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    c = doc["canaries"]
    print(f"pit canaries: green={c.get('green')} ({c.get('why')}); sidecars stamped "
          f"{doc['census']['stamped']}/{doc['census']['sidecars']} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
