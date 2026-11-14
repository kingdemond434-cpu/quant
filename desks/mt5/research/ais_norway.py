#!/usr/bin/env python3
"""NORWAY'S OPEN AIS STREAM -> TANKER PORT CALLS, TRANSITS AND STATIONARY TANKERS, PER DAY.

THE FREE ALTERNATIVE TO A PAID TANKER-TRACKING TERMINAL (2026-11-13). Kpler, Vortexa and the
Bloomberg tanker screens sell ship positions turned into flows. The Norwegian Coastal
Administration (Kystverket) publishes its open AIS stream under NLOD 2.0. NLOD allows use "for
any purpose and in all contexts", with attribution, and needs no registration. Norway's coast
watches three things a crude and gas book prices:

    hammerfest_lng      Melkoya LNG, Europe's northern LNG export train         -> XNGUSD
    mongstad_sture      the Bergen crude terminals (Troll, Oseberg, Grane)       -> XBRUSD, NOK
    karsto              Karsto gas processing and NGL export                     -> XNGUSD
    north_cape          the lane Russian Arctic crude and LNG take west          -> XBRUSD, XTIUSD

WHY NOT aisstream.io. Its site publishes no terms of service (read 2026-11-13), and unread
terms fail closed. The closed Kystverket component and the Danish AIS archive (robots-refused)
are not used either.

THE STREAM IS SAMPLED, NEVER HELD OPEN. Each pass reads the TCP socket for a bounded window
(`--window-s`, default 240 s). Class A tankers send a position every 2-10 s and their static
report every 6 minutes, so a 4-minute window sees every tanker in coverage at least once.
Coverage is the Norwegian economic zone plus the Svalbard and Jan Mayen protection zones.
Positions of non-tankers are discarded once the window closes. The tanker registry (ship type
80-89, from type-5 static reports) persists between passes.

THE DAILY SERIES IS A MEAN OVER WINDOWS, NOT A SUM. A day's value for a zone is the mean count
of distinct tankers per window that day, so a pass that failed lowers no count. A day with
fewer than MIN_WINDOWS windows publishes nothing for that day; the gap is never a zero. The
value is known at the end of its UTC day, and the alt_proxies rule stamps it at D+1.

    python desks/mt5/research/ais_norway.py [--window-s 240] [--no-collect]

Attribution, NLOD 2.0: "Contains data under the Norwegian licence for Open Government data
(NLOD) distributed by the Norwegian Coastal Administration."
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import socket
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LAKE = DESK / "data" / "lake" / "ais" / "norway"
SERIES = DESK / "data" / "lake" / "series" / "ais_norway.parquet"
REPORT = DESK / "reports" / "AIS_NORWAY.json"

HOST, PORT = "153.44.253.27", 5631
TERMS_URL = "https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/"
LICENCE_URL = "https://data.norge.no/nlod/en/2.0/"
CREDIT = ("Contains data under the Norwegian licence for Open Government data (NLOD) "
          "distributed by the Norwegian Coastal Administration.")

#: (south, west, north, east) in decimal degrees.
ZONES: dict[str, tuple[float, float, float, float]] = {
    "hammerfest_lng": (70.60, 23.40, 70.75, 23.80),
    "mongstad_sture": (60.50, 4.70, 60.90, 5.30),
    "karsto": (59.20, 5.40, 59.35, 5.60),
    "north_cape": (71.00, 25.00, 72.50, 31.00),
}
TANKER_TYPES = range(80, 90)
#: Below this speed over ground (knots) a tanker counts as stationary.
STATIONARY_KN = 0.5
MIN_WINDOWS = 6
KEEP_DAYS = 120
MAX_BYTES = 64 * 1024 * 1024


# ============================================================================ NMEA / AIVDM
_SENTENCE = re.compile(r"![A-Z]{2}VD[MO],(\d),(\d),(\d?),([AB12]?),([^,]*),"
                       r"(\d)\*[0-9A-Fa-f]{2}")
_TAG_TIME = re.compile(r"(?:^|[,\\])c:(\d{9,10})")


def _sixbit(payload: str, fill: int) -> str:
    bits = []
    for ch in payload:
        v = ord(ch) - 48
        if v > 40:
            v -= 8
        if not 0 <= v < 64:
            raise ValueError("bad payload char")
        bits.append(format(v, "06b"))
    s = "".join(bits)
    return s[: len(s) - fill] if fill else s


def _u(bits: str, start: int, n: int) -> int:
    return int(bits[start:start + n], 2)


def _s(bits: str, start: int, n: int) -> int:
    v = _u(bits, start, n)
    return v - (1 << n) if v & (1 << (n - 1)) else v


def _text(bits: str, start: int, nchars: int) -> str:
    out = []
    for i in range(nchars):
        v = _u(bits, start + 6 * i, 6)
        out.append(chr(v + 64) if v < 32 else chr(v))
    return "".join(out).split("@")[0].strip()


def decode(bits: str) -> dict[str, Any] | None:
    """Types 1-3 (Class A position) and 5 (static and voyage). Anything else is None."""
    if len(bits) < 38:
        return None
    mt = _u(bits, 0, 6)
    mmsi = _u(bits, 8, 30)
    if mt in (1, 2, 3) and len(bits) >= 149:
        lon = _s(bits, 61, 28) / 600000.0
        lat = _s(bits, 89, 27) / 600000.0
        sog = _u(bits, 50, 10)
        if abs(lon) > 180 or abs(lat) > 90:
            return None
        return {"type": mt, "mmsi": mmsi, "lat": lat, "lon": lon,
                "sog": None if sog == 1023 else sog / 10.0,
                "nav_status": _u(bits, 38, 4)}
    if mt == 5 and len(bits) >= 422:
        return {"type": 5, "mmsi": mmsi, "imo": _u(bits, 40, 30),
                "name": _text(bits, 112, 20), "ship_type": _u(bits, 232, 8),
                "draught": _u(bits, 294, 8) / 10.0, "destination": _text(bits, 302, 20)}
    return None


class Assembler:
    """Joins multi-sentence messages (type 5 spans two) and decodes complete ones."""

    def __init__(self) -> None:
        self._parts: dict[tuple[str, str, str], dict[int, str]] = {}

    def feed(self, line: str) -> tuple[dict[str, Any] | None, int | None]:
        m = _SENTENCE.search(line)
        if not m:
            return None, None
        total, num, seq, chan, payload, fill = m.groups()
        tm = _TAG_TIME.search(line)
        ts = int(tm.group(1)) if tm else None
        try:
            if total == "1":
                return decode(_sixbit(payload, int(fill))), ts
            key = (total, seq, chan)
            parts = self._parts.setdefault(key, {})
            parts[int(num)] = payload
            if int(num) != int(total) or len(parts) != int(total):
                if len(self._parts) > 4096:
                    self._parts.clear()
                return None, ts
            del self._parts[key]
            joined = "".join(parts[i] for i in range(1, int(total) + 1))
            return decode(_sixbit(joined, int(fill))), ts
        except (ValueError, KeyError):
            return None, ts


# ============================================================================ the window
def stream_lines(window_s: float, host: str = HOST, port: int = PORT) -> Iterator[str]:
    """Lines from the open stream for `window_s` seconds. Raises OSError when unreachable."""
    deadline = time.monotonic() + window_s
    got = 0
    with socket.create_connection((host, port), timeout=20) as sock:
        sock.settimeout(10)
        buf = b""
        while time.monotonic() < deadline and got < MAX_BYTES:
            try:
                chunk = sock.recv(65536)
            except TimeoutError:
                continue
            if not chunk:
                break
            got += len(chunk)
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                yield ln.decode("ascii", "replace").strip()


@dataclass
class Window:
    started: datetime
    lines: int = 0
    positions: int = 0
    statics: int = 0


def collect(lines: Iterable[str], registry: dict[str, dict[str, Any]],
            started: datetime) -> tuple[Window, list[dict[str, Any]]]:
    """Decode a window: update the registry in place, return the tankers' positions."""
    asm = Assembler()
    w = Window(started=started)
    last: dict[int, dict[str, Any]] = {}
    for ln in lines:
        w.lines += 1
        msg, _ts = asm.feed(ln)
        if msg is None:
            continue
        if msg["type"] == 5:
            w.statics += 1
            key = str(msg["mmsi"])
            prev = registry.get(key, {})
            registry[key] = {**prev, "ship_type": msg["ship_type"], "name": msg["name"],
                             "draught": msg["draught"], "destination": msg["destination"],
                             "imo": msg["imo"], "seen": started.date().isoformat()}
            continue
        w.positions += 1
        last[msg["mmsi"]] = msg
    tankers = []
    for mmsi, pos in last.items():
        row = registry.get(str(mmsi))
        if row and int(row.get("ship_type", 0)) in TANKER_TYPES:
            tankers.append({"mmsi": mmsi, "lat": pos["lat"], "lon": pos["lon"],
                            "sog": pos["sog"], "draught": row.get("draught"),
                            "ship_type": row.get("ship_type")})
    return w, tankers


def in_zone(lat: float, lon: float, box: tuple[float, float, float, float]) -> bool:
    s, w, n, e = box
    return s <= lat <= n and w <= lon <= e


def summarise(tankers: list[dict[str, Any]]) -> dict[str, float]:
    """One window's counts: distinct tankers per zone, laden draught, stationary outside ports."""
    out: dict[str, float] = {}
    ports = ("hammerfest_lng", "mongstad_sture", "karsto")
    for z, box in ZONES.items():
        inside = [t for t in tankers if in_zone(t["lat"], t["lon"], box)]
        out[f"{z}_tankers"] = float(len(inside))
        dr = [float(t["draught"]) for t in inside if t.get("draught")]
        if dr:
            out[f"{z}_mean_draught"] = sum(dr) / len(dr)
    out["stationary_offport_tankers"] = float(sum(
        1 for t in tankers
        if t["sog"] is not None and t["sog"] < STATIONARY_KN
        and not any(in_zone(t["lat"], t["lon"], ZONES[p]) for p in ports)))
    out["coverage_tankers"] = float(len(tankers))
    return out


# ============================================================================ daily series
def daily(windows: list[dict[str, Any]]) -> dict[date, dict[str, float]]:
    """Mean of each count over the day's windows; days under MIN_WINDOWS publish nothing."""
    by_day: dict[date, list[dict[str, float]]] = defaultdict(list)
    for w in windows:
        with contextlib.suppress(KeyError, ValueError, TypeError):
            by_day[datetime.fromisoformat(w["started"]).date()].append(w["counts"])
    out: dict[date, dict[str, float]] = {}
    for d, rows in by_day.items():
        if len(rows) < MIN_WINDOWS:
            continue
        keys = {k for r in rows for k in r}
        out[d] = {k: sum(r[k] for r in rows if k in r) / max(1, sum(k in r for r in rows))
                  for k in keys}
        out[d]["windows"] = float(len(rows))
    return out


def _load_windows(lake: Path, since: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(lake.glob("windows_*.jsonl")):
        with contextlib.suppress(ValueError):
            if date.fromisoformat(p.stem[8:]) < since:
                continue
        with contextlib.suppress(OSError):
            for ln in p.read_text("utf-8").splitlines():
                with contextlib.suppress(ValueError):
                    out.append(json.loads(ln))
    return out


def write_series(lake: Path, series: Path, today: date) -> int:
    days = daily(_load_windows(lake, today - timedelta(days=KEEP_DAYS)))
    done = {d: v for d, v in days.items() if d < today}      # a day is complete at its end
    if not done:
        return 0
    import pandas as pd
    df = pd.DataFrame.from_dict(done, orient="index").sort_index()
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    if series.exists():
        try:
            old = pd.read_parquet(series)
        except Exception:     # an unreadable series is never overwritten by a 120-day window
            return 0
        df = pd.concat([old[~old.index.isin(df.index)], df]).sort_index()
    series.parent.mkdir(parents=True, exist_ok=True)
    tmp = series.with_suffix(".tmp")
    df.to_parquet(tmp)
    tmp.replace(series)
    return len(df)


def _prune(lake: Path, today: date) -> None:
    for p in lake.glob("*_????-??-??.*"):
        with contextlib.suppress(ValueError, OSError):
            if date.fromisoformat(p.stem[-10:]) < today - timedelta(days=KEEP_DAYS):
                p.unlink()


# ============================================================================ the pass
def run(window_s: float, *, lake: Path = LAKE, series: Path = SERIES, collect_live: bool = True,
        lines: Iterable[str] | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    lake.mkdir(parents=True, exist_ok=True)
    reg_path = lake / "registry.json"
    registry: dict[str, dict[str, Any]] = {}
    with contextlib.suppress(OSError, ValueError):
        registry = json.loads(reg_path.read_text("utf-8"))
    rep: dict[str, Any] = {"generated_at": now.isoformat(), "source": f"{HOST}:{PORT}",
                           "terms": "confirmed", "licence": "NLOD 2.0", "terms_url": TERMS_URL,
                           "licence_url": LICENCE_URL, "credit": CREDIT}
    if collect_live or lines is not None:
        try:
            src = lines if lines is not None else stream_lines(window_s)
            w, tankers = collect(src, registry, now)
        except OSError as exc:
            rep.update(status="UNREACHABLE", error=type(exc).__name__,
                       missed_growth=("no Norway tanker window this pass: the day's mean is "
                                      "taken over the windows that did land, so the series "
                                      "loses resolution, not level"))
        else:
            counts = summarise(tankers)
            day = now.date().isoformat()
            with (lake / f"windows_{day}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"started": now.isoformat(), "lines": w.lines,
                                     "positions": w.positions, "statics": w.statics,
                                     "counts": counts}) + "\n")
            with (lake / f"tankers_{day}.jsonl").open("a", encoding="utf-8") as fh:
                for t in tankers:
                    fh.write(json.dumps({"t": now.isoformat(), **t}) + "\n")
            tmp = reg_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(registry), "utf-8")
            tmp.replace(reg_path)
            status = "OK" if w.positions else "EMPTY_WINDOW"
            rep.update(status=status, lines=w.lines, positions=w.positions, statics=w.statics,
                       registry=len(registry), tankers=len(tankers), counts=counts)
    else:
        rep["status"] = "SERIES_ONLY"
    rep["series_rows"] = write_series(lake, series, now.date())
    _prune(lake, now.date())
    with contextlib.suppress(OSError):
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(rep, indent=1), "utf-8")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window-s", type=float, default=240.0)
    ap.add_argument("--no-collect", action="store_true", help="rebuild the series only")
    a = ap.parse_args(argv)
    rep = run(a.window_s, collect_live=not a.no_collect)
    print(json.dumps({k: rep.get(k) for k in ("status", "positions", "statics", "tankers",
                                               "series_rows")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
