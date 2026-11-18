"""STATE CONDITIONER -- the shared door a computed market STATE takes to become testable.

WHY THIS FILE EXISTS. Two state organs (`hawkes_state`, tick-arrival self-excitation; and
`tda_state`, persistence-landscape fragility of the multi-symbol return cloud) compute a number
per hour that is not a price pattern but a description of the market's condition. A state the
judge cannot read is a report. The desk already has exactly one honest route from a series to a
gauntlet verdict and this module only uses it, it adds none:

  1. THE LAKE. The series is written as `data/lake/series/<id>.csv` in the point-in-time envelope
     (`event_time`, `available_time`, `source_id`, numeric columns). That is the file
     `mt5desk.family_exogenous_conditioner.conditioner` loads, and therefore also the file the
     `alt:<id>:<column>:<op>:<threshold>` second-axis conditioner of `mt5desk.cell_modifiers`
     loads. Neither file is edited: a series in this envelope is registered by being there.
  2. THE CELLS. A small, fixed grid of `exogenous_conditioner` cells per instrument is donated
     ONCE IN ITS LIFE through `proposer_common.donate` (stamped, lane-filtered, pre-registered),
     the `futures_state` discipline: a pass never re-mints a cell, so trials are charged when a
     rule is minted and never inflated by minting it again.

THE CLOCK, BECAUSE IT IS WHERE A STATE LEAKS. Bars and ticks are stamped on the BROKER's wall
clock under a UTC label (UTC+2 winter / UTC+3 summer; `research/bars_state.py`). A state
computed on bars up to broker instant `t` is published with `available_time` = the TRUE UTC of `t`,
converted through the server anchor `bars_state.broker_to_utc`. With the anchor unavailable the
conversion falls back to `t - 2h`, the LATER of the two possible UTC instants -- a stamp that can
only be late, never early. The donated cells then hold the value back `CELL_LAG_HOURS` on top,
which exceeds the largest broker offset plus one bar, so a broker-labelled bar can never read a
state value computed from its own future.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SERIES_DIR = DESK / "data" / "lake" / "series"
STATE_DIR = DESK / "data" / "lake" / "state"
REPORTS = DESK / "reports"

#: The PIT envelope columns written ahead of the numeric state columns.
ENVELOPE = ("event_time", "available_time", "source_id")

#: Hours a donated cell holds the state back before a bar may read it: the largest broker offset
#: (3 h, summer) plus one bar. `exogenous_conditioner` joins the UTC `available_time` onto the
#: broker-labelled bar index, which runs 2-3 h AHEAD of UTC, so any lag below 3 h could leak.
CELL_LAG_HOURS = 4

#: Fallback broker offset when the server anchor is not importable: the SMALLER offset, so the
#: UTC stamp it yields is the later of the two candidates and can only be late.
FALLBACK_OFFSET_H = 2


def _anchor() -> Any:
    try:
        from research import bars_state
        return bars_state
    except Exception:
        return None


_BS = _anchor()


def broker_to_utc(wall: datetime) -> datetime:
    """A naive broker wall time as true UTC; late-biased fallback when the anchor is absent."""
    naive = wall.replace(tzinfo=None)
    if _BS is not None:
        try:
            out = _BS.broker_to_utc(naive)
            if out is not None:
                return out.astimezone(UTC)
        except Exception:
            pass
    return (naive - timedelta(hours=FALLBACK_OFFSET_H)).replace(tzinfo=UTC)


def utc_to_broker(utc: datetime) -> datetime:
    """True UTC as a naive broker wall time; early-biased fallback (the bound it gives is safe)."""
    if _BS is not None:
        try:
            out = _BS.utc_to_broker(utc)
            if out is not None:
                return out.replace(tzinfo=None)
        except Exception:
            pass
    return (utc.astimezone(UTC) + timedelta(hours=FALLBACK_OFFSET_H)).replace(tzinfo=None)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat(timespec="seconds")
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def trailing_z(values: Sequence[float | None], window: int, min_n: int) -> list[float | None]:
    """z of each value against the `window` values STRICTLY BEFORE it; never itself or later."""
    out: list[float | None] = []
    hist: list[float] = []
    for v in values:
        prior = hist[-window:]
        z: float | None = None
        if v is not None and math.isfinite(v) and len(prior) >= min_n:
            mu = sum(prior) / len(prior)
            var = sum((x - mu) ** 2 for x in prior) / len(prior)
            sd = math.sqrt(var)
            if sd > 0:
                z = (v - mu) / sd
        out.append(z)
        if v is not None and math.isfinite(v):
            hist.append(float(v))
    return out


def read_series(sid: str, root: Path | None = None) -> list[dict[str, Any]]:
    p = (root or SERIES_DIR) / f"{sid}.csv"
    if not p.exists():
        return []
    try:
        with p.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_series(sid: str, rows: Iterable[dict[str, Any]], columns: Sequence[str],
                 root: Path | None = None) -> Path:
    """`data/lake/series/<sid>.csv` in the PIT envelope, rows in event order."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    cols = [*ENVELOPE, *columns]
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    path = (root or SERIES_DIR) / f"{sid}.csv"
    _atomic(path, buf.getvalue())
    return path


def write_json(path: Path, doc: dict[str, Any]) -> None:
    _atomic(path, json.dumps(doc, indent=1, sort_keys=False, default=str) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def conditioner_specs(sid: str, column: str, threshold: float = 2.0) -> list[str]:
    """The `alt:` second-axis specs `mt5desk.cell_modifiers` applies to any family's cell."""
    return [f"alt:{sid}:{column}:gt:{threshold:g}", f"alt:{sid}:{column}:lt:{-threshold:g}"]


def cell_rows(seat: str, sid: str, symbol: str, signals: Sequence[str], mechanism: str,
              thresholds: Sequence[float] = (1.5,), charts: Sequence[str] = ("H1",)
              ) -> list[dict[str, Any]]:
    """The fixed `exogenous_conditioner` grid for one (series, instrument): both stances, so the
    judge decides the sign and the state is not pre-signed by this organ."""
    from proposer_common import candidate
    out: list[dict[str, Any]] = []
    for sig in signals:
        for thr in thresholds:
            for side in (1, -1):
                for chart in charts:
                    params = {"source": sid, "signal": sig, "transform": "level_z",
                              "threshold": float(thr), "side_when_high": side,
                              "lag_hours": CELL_LAG_HOURS, "timeframe": chart}
                    c = candidate(seat, symbol, "exogenous_conditioner", params, mechanism,
                                  f"exogenous_conditioner on {sid}.{sig} -> {symbol} {chart} "
                                  f"[{'follow' if side > 0 else 'fade'} {thr:g}]",
                                  {"state_series": sid, "column": sig})
                    c["chart"] = chart
                    c["required_data"] = [f"desks/mt5/data/lake/series/{sid}.csv"]
                    c["falsifier"] = (f"{sid}.{sig} at |z|>{thr:g} has no measurable relation "
                                      f"to {symbol} {chart} returns out of sample")
                    c["cell"] = (f"{symbol}.exogenous_conditioner.{sid}.{sig}.{thr:g}."
                                 f"{side}.{chart}")
                    out.append(c)
    return out


def mint_once(seat: str, rows: list[dict[str, Any]], state_path: Path,
              *, dry_run: bool = False) -> dict[str, Any]:
    """Donate the rows whose `cell` id has never been donated; remember them. Never re-mints."""
    state = load_json(state_path)
    done = set(state.get("minted") or [])
    fresh = [r for r in rows if r.get("cell") not in done]
    out: dict[str, Any] = {"grid": len(rows), "already_minted": len(rows) - len(fresh),
                           "new": len(fresh), "donated": 0, "dry_run": dry_run}
    if not fresh or dry_run:
        return out
    try:
        import proposer_common as pc
        path = pc.donate(seat, fresh, tests_run=len(fresh))
        counts = pc.donation_counts()
    except Exception as exc:  # the donation door failing is a named outcome, not a crash
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
        return out
    out["donated"] = int(counts.get("donated") or 0)
    out["refused_wrong_lane"] = int(counts.get("refused_wrong_lane") or 0)
    out["refused_unstamped"] = int(counts.get("refused_unstamped") or 0)
    out["path"] = str(path) if path else None
    # A row the lane door refused is remembered too: re-offering it every pass would charge
    # nothing but would make `new` a permanent lie about what is left to mint.
    done.update(str(r.get("cell")) for r in fresh)
    state["minted"] = sorted(done)
    state["updated_utc"] = iso(datetime.now(UTC))
    write_json(state_path, state)
    return out
