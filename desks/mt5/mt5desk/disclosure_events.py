"""THE DATED-DISCLOSURE READER the event families load their own events through.

WHY A FAMILY LOADS ITS OWN EVENTS. The sealed gauntlet (`scripts/external_gauntlet.build_cell`)
hands every `event_reaction` cell ONE event index -- the Forex Factory calendar vintages -- and has
no branch that could hand a cell a corporate disclosure stream. A cell that names its stream in
its own params and loads it here reaches the judge through the ordinary `fn(h1, **params)` call,
exactly as `family_exogenous_conditioner` loads its own lake series and the cross-sectional class
books load their own peer panel. Nothing sealed changes.

WHERE THE EVENTS COME FROM. `research/corporate_disclosure.py` (hourly leg `corporate_disclosure`)
writes one JSON row per primary-source disclosure -- TDnet, EDINET, J-Quants, DART, cninfo, SSE,
SZSE, EDGAR 8-K/6-K -- under `data/lake/events/corporate_disclosure/<source>.jsonl`. Each row
carries `at`, the moment the market could FIRST know (the exchange or regulator's own publication
stamp, or the END of the publication day when the source dates to the day only), and three
instrument lists resolved against the broker's registry at write time:

    symbols    the issuer's own MT5 share CFD (Toyota, TSMC, AlibabaGroup, Baidu, NIO ...)
    peers      declared supply-chain / sector peers the broker quotes
    transmits  the country's index and USD-leg currency pair (JPN225, USDJPY, USDKRW, HK50,
               CHINAH, USDCNH ...) derived from the registry's own asset class and currency

THE STREAM SPEC is one string so it survives every params filter on the way to the judge:

    corporate_disclosure:<country|*>:<scope>:<category|*>:<direction>:<min_count>

    scope      self | peers | transmits
    direction  any | up | down        (a guidance revision's sign, a pre-announcement's sign)
    min_count  events of the class needed on one local publication day before the day is an
               event -- 1 for an issuer's own filing, a burst threshold for an index

A malformed spec loads nothing: no events is UNMEASURED and the family emits no signals.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

#: The organ's event store, named from this file's own location so a test tree and the box agree.
EVENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "lake" / "events" / "corporate_disclosure"
STREAM = "corporate_disclosure"
SCOPES = ("self", "peers", "transmits")
#: The event row's field each scope reads.
SCOPE_FIELD = {"self": "symbols", "peers": "peers", "transmits": "transmits"}
DIRECTIONS = ("any", "up", "down")

#: A publication DAY is the issuer's own local day. Fixed offsets are enough for grouping: none of
#: JP/KR/CN observes summer time, and a US day boundary one hour off moves no filing across it
#: (EDGAR accepts 06:00-22:00 ET).
LOCAL_OFFSET_H: dict[str, int] = {"jp": 9, "kr": 9, "cn": 8, "hk": 8, "tw": 8, "us": -5}

_MEMO: dict[tuple[str, int, int], list[dict[str, Any]]] = {}


def parse_spec(spec: str) -> dict[str, Any] | None:
    """The six fields of a stream spec, or None when it is not one this reader can honour."""
    parts = str(spec or "").split(":")
    if len(parts) != 6 or parts[0] != STREAM:
        return None
    _s, country, scope, category, direction, n = parts
    if scope not in SCOPES or direction not in DIRECTIONS:
        return None
    try:
        min_count = max(1, int(n))
    except ValueError:
        return None
    return {"country": country.lower() or "*", "scope": scope, "category": category or "*",
            "direction": direction, "min_count": min_count}


def make_spec(country: str, scope: str, category: str, direction: str = "any",
              min_count: int = 1) -> str:
    return f"{STREAM}:{country}:{scope}:{category}:{direction}:{int(min_count)}"


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = (str(path), int(st.st_mtime_ns), int(st.st_size))
    hit = _MEMO.get(key)
    if hit is not None:
        return hit
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    for stale in [k for k in _MEMO if k[0] == str(path)]:
        _MEMO.pop(stale, None)
    _MEMO[key] = out
    return out


def _at(row: dict[str, Any]) -> datetime | None:
    raw = row.get("at")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _matches(row: dict[str, Any], spec: dict[str, Any], symbol: str) -> bool:
    if spec["country"] != "*" and str(row.get("country") or "").lower() != spec["country"]:
        return False
    if spec["category"] != "*" and str(row.get("category") or "") != spec["category"]:
        return False
    d = int(row.get("direction") or 0)
    if spec["direction"] == "up" and d <= 0:
        return False
    if spec["direction"] == "down" and d >= 0:
        return False
    names = row.get(SCOPE_FIELD[spec["scope"]]) or []
    return isinstance(names, list) and symbol.upper() in {str(s).upper() for s in names}


def load_events(spec: str, symbol: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    """`[{symbol, at}]` for `symbol` under `spec`, in the contract `family_event_reaction` reads.

    One event per local publication day on which at least `min_count` qualifying disclosures
    landed, stamped at the moment the `min_count`-th became knowable -- never earlier, so a burst
    cannot be traded before it has happened.
    """
    parsed = parse_spec(spec)
    if parsed is None or not symbol:
        return []
    base = root or EVENTS_DIR
    if not base.is_dir():
        return []
    by_day: dict[tuple[str, str], list[tuple[datetime, int]]] = defaultdict(list)
    seen: set[str] = set()
    for path in sorted(base.glob("*.jsonl")):
        for row in _rows(path):
            if not _matches(row, parsed, symbol):
                continue
            rid = str(row.get("id") or "")
            if rid and rid in seen:
                continue
            seen.add(rid)
            ts = _at(row)
            if ts is None:
                continue
            cc = str(row.get("country") or "").lower()
            # A day-precision row is stamped at the END of its day (00:00 local of the next);
            # one second back files it under the day it was published on.
            local = ts + timedelta(hours=LOCAL_OFFSET_H.get(cc, 0)) - timedelta(seconds=1)
            try:
                weight = max(1, int(row.get("n") or 1))       # a per-day COUNT row
            except (TypeError, ValueError):
                weight = 1
            by_day[(cc, local.date().isoformat())].append((ts, weight))
    out: list[dict[str, Any]] = []
    need = int(parsed["min_count"])
    for _key, stamps in sorted(by_day.items()):
        stamps.sort()
        total = 0
        for ts, weight in stamps:
            total += weight
            if total >= need:
                out.append({"symbol": symbol, "at": ts.astimezone(UTC).isoformat()})
                break
    out.sort(key=lambda e: e["at"])
    return out
