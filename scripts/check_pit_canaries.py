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


def main() -> int:
    now = datetime.now(tz=UTC)
    doc = {"at": now.isoformat(timespec="seconds"), "canaries": plant_and_read(now),
           "census": _sidecar_census(),
           "rule": "green only when the planted future row is invisible at now and the past row "
                   "is visible; unmeasured is never green"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    c = doc["canaries"]
    print(f"pit canaries: green={c.get('green')} ({c.get('why')}); sidecars stamped "
          f"{doc['census']['stamped']}/{doc['census']['sidecars']} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
