"""HONG KONG OFFICIAL PLANE -- the HKMA currency board as parsed series, and the refused HKEX lane.

The series are fetched, parsed and PIT-stamped by `research.alt_proxies` (rows
`hk_hkma_interbank_liquidity`, `hk_hkma_hibor_fixing`, `hk_hkma_monetary_base`,
`hk_immd_passenger`: every alt_proxies source whose region is HK). This module reads them through
`countries._official_plane` and adds the CURRENCY-BOARD EVENT SYSTEM (PART XI): every non-zero
Convertibility Undertaking FX leg the HKMA books (`forex_trans_t1`) is an event object --
WEAK_SIDE when the HKMA bought HKD (an outflow it defended, which drains the aggregate balance and
lifts HIBOR), STRONG_SIDE when it sold HKD -- with its knowable-at instant and size.

HKEX Stock Connect (Northbound / Southbound) is a REFUSED lane: HKEX's terms of use forbid
systematic retrieval into databases and any data mining of the site, so no fetcher is built and
the lane is reported BLOCKED_ON_TERMS with the verbatim clause.
"""
from __future__ import annotations

import importlib
from datetime import datetime
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

CODE = "hk"
REGION = "HK"
REPORT: Path = _op.report_path(CODE)
REFUSED: tuple[str, ...] = ("hk_hkex_stock_connect",)
LANES: tuple[str, ...] = ("alt_proxies:region=HK",)
CU_SERIES = "cu_forex_trans_t1_hkd_mn"


def cu_events(points: dict[str, dict[str, list[dict[str, Any]]]], now: datetime
              ) -> list[dict[str, Any]]:
    """Each non-zero CU FX leg as a RELEASED event, signed by the side of the band it defends."""
    del now
    pts = (points.get("hk_hkma_interbank_liquidity") or {}).get(CU_SERIES) or []
    out: list[dict[str, Any]] = []
    for e in _op.released_events(pts, event="hk_cu_fx_leg",
                                 extra={"series": f"hk_hkma_interbank_liquidity:{CU_SERIES}",
                                        "targets": ["USDHKD", "HK50", "USDCNH", "AUDUSD"]}):
        v = e.get("value")
        if v is None or float(v) == 0.0:
            continue
        side = "WEAK_SIDE" if float(v) < 0 else "STRONG_SIDE"
        out.append({**e, "event": f"hk_cu_{side.lower()}", "side": side,
                    "mechanism": ("HKMA bought HKD at 7.85: aggregate balance drains, HIBOR "
                                  "rises toward SOFR" if side == "WEAK_SIDE" else
                                  "HKMA sold HKD at 7.75: aggregate balance swells, HIBOR "
                                  "falls")})
    return out


def run(**kwargs: Any) -> dict[str, Any]:
    """The HK lanes from the factory's stores, plus the currency-board event system."""
    kwargs.pop("code", None)
    kwargs.setdefault("report_default", REPORT)
    return dict(_op.run(code=CODE, region=REGION, refused=REFUSED, events=cu_events, **kwargs))


__all__ = ["CODE", "CU_SERIES", "LANES", "REFUSED", "REPORT", "cu_events", "run"]
