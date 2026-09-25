"""THE LAKE'S POINT-IN-TIME DOOR: a series is visible to a decision only once it was available.

Tier-1 B2. `libs/data/pit.py` defines the five stamps and `usable_at`; `libs/data/pit_stamp.py`
puts them on a frame; `desks/mt5/research/asia_parser.py` writes a `<source>.pit.json` sidecar
beside every series file it lands in `desks/mt5/data/lake/series`. What did not exist was the
JOIN: every consumer of that lake asked whether a FILE was on disk, so a series whose
`available_time` has not arrived counted as data the desk holds. A planted future row that
nothing refuses is a lookahead the canary cannot see, which is why the canary and this join land
together.

THE RULE IS ONE-SIDED ON PURPOSE. A series is withheld only when its sidecar carries an
`available_time` LATER than the decision time. A series with no sidecar, an unparseable stamp or
no time at all is VISIBLE and counted as unstamped -- never withheld. Withholding the unstamped
would shrink the desk's data on the strength of a missing file, which is a reduction bought with
no evidence; naming it as unstamped puts the same fact in the census where it can be fixed at the
producer.

    from libs.data.lake_pit import usable_series
    view = usable_series(lake / "series", as_of=datetime.now(UTC))
    view.visible      # source ids a decision at as_of may read
    view.withheld     # source id -> the available_time that has not arrived
    view.unstamped    # source ids carrying no readable available_time
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Every key `libs.data.pit` accepts as "when the desk could have known it", in its own order.
AVAILABLE_KEYS = ("available_time", "published_at", "captured_at", "found_at")

#: Sidecar suffix `asia_parser` writes beside each series file.
SIDECAR = ".pit.json"


@dataclass
class SeriesView:
    """What a decision at `as_of` may read out of a lake series directory."""

    as_of: datetime
    visible: set[str] = field(default_factory=set)
    withheld: dict[str, str] = field(default_factory=dict)
    unstamped: set[str] = field(default_factory=set)
    stamped: dict[str, str] = field(default_factory=dict)

    def census(self) -> dict[str, Any]:
        return {"as_of": self.as_of.isoformat(timespec="seconds"),
                "n_visible": len(self.visible), "n_withheld": len(self.withheld),
                "n_unstamped": len(self.unstamped),
                "withheld": dict(sorted(self.withheld.items())[:20]),
                "rule": ("a series is withheld only when its sidecar's available_time is later "
                         "than as_of; unstamped is visible and counted, never withheld")}


def _parse(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        dt = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def available_time_of(sidecar: Path) -> datetime | None:
    """The sidecar's available_time, or None when it carries no readable one."""
    try:
        doc = json.loads(sidecar.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    for key in AVAILABLE_KEYS:
        dt = _parse(doc.get(key))
        if dt is not None:
            return dt
    return None


def usable_series(series_dir: Path, as_of: datetime | None = None) -> SeriesView:
    """Join every series file in `series_dir` onto its sidecar's available_time."""
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    view = SeriesView(as_of=now)
    if not series_dir.is_dir():
        return view
    for f in series_dir.iterdir():
        if not f.is_file() or f.name.endswith(SIDECAR):
            continue
        # `abs_trade__t0.parquet` and `abs_trade.parquet` are the same source; the sidecar is
        # written against the source id, so the stem before the parser's `__t<n>` suffix is the
        # identity both sides share.
        sid = f.stem.split("__", 1)[0]
        avail = available_time_of(f.with_suffix(f.suffix + SIDECAR))
        if avail is None:
            avail = available_time_of(series_dir / f"{sid}{SIDECAR}")
        if avail is None:
            view.unstamped.add(sid)
            view.visible.add(sid)
            continue
        view.stamped[sid] = avail.isoformat(timespec="seconds")
        if avail > now:
            view.withheld[sid] = avail.isoformat(timespec="seconds")
            view.visible.discard(sid)
        else:
            view.visible.add(sid)
    # A source with one visible file and one future file is WITHHELD for the future one only;
    # the visible file keeps it in the readable set, which is what a row-level join would do.
    for sid in list(view.withheld):
        if sid in view.visible:
            view.withheld.pop(sid, None)
    return view


def rows_as_of(rows: list[dict[str, Any]], as_of: datetime | None = None
               ) -> tuple[list[dict[str, Any]], int]:
    """Rows a decision at `as_of` may read, and how many were withheld. Row-level twin of
    `usable_series` for consumers that hold parsed rows rather than files."""
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    out, withheld = [], 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        avail = None
        for key in AVAILABLE_KEYS:
            avail = _parse(r.get(key))
            if avail is not None:
                break
        if avail is not None and avail > now:
            withheld += 1
            continue
        out.append(r)
    return out, withheld
