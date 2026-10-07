"""KOREA OFFICIAL PLANE -- BOK ECOS, the customs 10-/20-day export prints, and the refused KRX lane.

The series are fetched, parsed and PIT-stamped by `research.alt_proxies` (rows `kr_ecos_*`,
`kr_exports_early`, `kr_mof_container_teu`, `kr_bok_card_spend`, ...: every alt_proxies source
whose region is KR). This module reads them through `countries._official_plane` and adds the
directive's explicit EVENT SYSTEM for the two Korean export prints (PART X): each 1-10 and 1-20
day release is an event object with its lifecycle (SCHEDULED -> RELEASED), its knowable-at
instant, the expected value the factory derived from prior prints only, and the surprise.

KRX (investor-type net buying, program trading, short selling, KOSPI200 OI) is a REFUSED lane:
KRX's Open API terms allow non-commercial use only and forbid passing the data to third parties,
so no fetcher is built and the lane is reported BLOCKED_ON_TERMS with the verbatim clause.

The file is deliberately NOT named `data_plane.py`: Tier-1 rows K1/K2 record that a
`data_plane.py`, `agents.py`, `lattice.py`, `moat.py` and `nowcast.py` were built on the trading
box and never committed. A tracked file at one of those paths would collide with an untracked
copy when the box adopts this tree, so this plane writes `KR_OFFICIAL_PLANE.json` and leaves
`KR_DATA_PLANE.json` to that module if it still exists there.
"""
from __future__ import annotations

import importlib
from datetime import date, datetime
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

CODE = "kr"
REGION = "KR"
REPORT: Path = _op.report_path(CODE)
#: Hosts whose terms refuse the use; reported, never fetched.
REFUSED: tuple[str, ...] = ("kr_krx_market_data",)
#: The registry the shared miner adapter hands back to `run` (the factory owns the real one).
LANES: tuple[str, ...] = ("alt_proxies:region=KR",)
#: Korea Customs Service prints: 1-10 day on the 11th, 1-20 day on the 21st (09:00 KST = 00:00
#: UTC), rolled past weekends. A holiday shift lands later, never earlier.
EXPORT_PRINT_DAYS: tuple[int, ...] = (11, 21)


def export_events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
                  ) -> list[dict[str, Any]]:
    """The 10-day and 20-day export prints as event objects: RELEASED from the factory's PIT
    points (headline daily-average YoY carries the surprise), then the next two SCHEDULED."""
    pts = (points.get("kr_exports_early") or {}).get("daily_avg_yoy") or []
    out: list[dict[str, Any]] = []
    for window in (10, 20):
        out.extend(_op.released_events(
            pts, event=f"kr_exports_{window}d", period_filter=lambda d, w=window: d.day == w,
            extra={"series": "kr_exports_early:daily_avg_yoy", "window_days": window,
                   "targets": ["USDKRW", "AUDUSD", "XCUUSD", "JPN225"]}))
    for t in _op.scheduled_after(now, EXPORT_PRINT_DAYS):
        window = 10 if t.day < 21 else 20
        out.append({"event": f"kr_exports_{window}d", "lifecycle": "SCHEDULED",
                    "scheduled_time": t.isoformat(timespec="seconds"),
                    "event_time": date(t.year, t.month, window).isoformat(),
                    "knowable_at": None, "value": None,
                    "why": "scheduled by the customs calendar; nothing is known until release"})
    return sorted(out, key=lambda e: str(e.get("event_time")))


def run(**kwargs: Any) -> dict[str, Any]:
    """The KR lanes from the factory's stores, plus the export-print event system."""
    kwargs.pop("code", None)
    kwargs.setdefault("report_default", REPORT)
    return dict(_op.run(code=CODE, region=REGION, refused=REFUSED, events=export_events, **kwargs))


__all__ = ["CODE", "EXPORT_PRINT_DAYS", "LANES", "REFUSED", "REPORT", "export_events", "run"]
