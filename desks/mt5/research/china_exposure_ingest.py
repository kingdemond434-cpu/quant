"""UN Comtrade -> the MEASURED weights of the China knowledge graph (GAP_MAP row 31).

For every country in `libs.research.china_graph.COUNTRIES`, one annual query to the UN Comtrade
public preview API (the endpoint `data_axis_miner` already registers for the trade_flow axis):
exports (flow X) to partners World (0) and China (156), commodity codes TOTAL plus the HS
chapters the graph's commodity nodes name. From it:

    china_share          = exports to China / exports to World            (TOTAL)
    chapter_share[hs]    = exports to World of chapter hs / total exports

Only these DERIVED RATIOS and the vintage are written (data/axes/china_exposure.json); the raw
trade values are not stored or redistributed. A country whose query fails keeps its previous
measured row (stamped with that row's own `fetched_at`), and the graph falls back to its
labelled structural prior for any country that never measured.

FETCH DISCIPLINE (the desk's rules for every new fetcher): an honest User-Agent naming this
organ; robots.txt read first with that UA and an UNREADABLE robots is a refusal, never a
permission (a 404 robots allows, as the standard says); redirects are followed only on the SAME
host -- a cross-host 3xx is refused and recorded; no retry on 429 (the server asked us to stop);
no key, no login, no paid endpoint. Annual data: the file is refreshed at most every
REFRESH_DAYS, so the hourly leg that calls `refresh()` costs nothing on most passes.

The latest complete year is tried first and the year before it on an empty answer (Comtrade
publishes a year's annual data progressively through the following year).

    python desks/mt5/research/china_exposure_ingest.py [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import china_graph  # noqa: E402

OUT = DESK / "data" / "axes" / "china_exposure.json"
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; china_exposure_ingest)"
CHINA, WORLD = 156, 0
REFRESH_DAYS = 7
TIMEOUT_S = 30.0


class Refused(Exception):
    """The fetch discipline said no (robots, cross-host redirect, rate limit)."""


class _SameHostOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> Any:
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            raise Refused(f"cross-host redirect {code} to {urllib.parse.urlsplit(newurl).netloc}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameHostOnly)


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with _OPENER.open(req, timeout=TIMEOUT_S) as r:
            return str(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise Refused("HTTP 429: the server asked us to stop") from exc
        raise


def robots_allow(url: str, get: Callable[[str], str] = http_get) -> bool:
    import urllib.robotparser
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(get(f"{p.scheme}://{p.netloc}/robots.txt").splitlines())
    except urllib.error.HTTPError as exc:
        return exc.code == 404
    except Exception:  # noqa: BLE001 -- an unread policy is never a yes
        return False
    return rp.can_fetch(UA, url)


def query_url(reporter: int, year: int) -> str:
    cmds = ",".join(["TOTAL", *china_graph.hs_chapters()])
    q = {"reporterCode": reporter, "period": year, "partnerCode": f"{WORLD},{CHINA}",
         "cmdCode": cmds, "flowCode": "X", "includeDesc": "false"}
    return f"{BASE}?{urllib.parse.urlencode(q)}"


def shares(rows: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Derived ratios from one reporter-year's rows; None when the totals are absent."""
    val: dict[tuple[int, str], float] = {}
    for r in rows:
        try:
            v = float(r.get("primaryValue") if r.get("primaryValue") is not None
                      else r.get("fobvalue"))
            p = int(r.get("partnerCode"))
        except (TypeError, ValueError):
            continue
        if str(r.get("flowCode") or "X") != "X":
            continue
        k = (p, str(r.get("cmdCode")))
        val[k] = val.get(k, 0.0) + v
    world = val.get((WORLD, "TOTAL"))
    china = val.get((CHINA, "TOTAL"))
    if not world or world <= 0 or china is None:
        return None
    return {"china_share": round(china / world, 5),
            "chapter_share": {hs: round(val[(WORLD, hs)] / world, 5)
                              for hs in china_graph.hs_chapters() if (WORLD, hs) in val}}


def fetch_country(iso: str, m49: int, now: datetime,
                  get: Callable[[str], str] = http_get) -> dict[str, Any]:
    last_err = "no year answered"
    for year in (now.year - 1, now.year - 2):
        url = query_url(m49, year)
        if not robots_allow(url, get):
            return {"status": "REFUSED_ROBOTS", "url": url}
        try:
            doc = json.loads(get(url))
        except Refused as exc:
            return {"status": "REFUSED", "why": str(exc)}
        except Exception as exc:  # noqa: BLE001 -- recorded, never a verdict on the source
            last_err = f"{type(exc).__name__}: {str(exc)[:160]}"
            continue
        rows = doc.get("data") if isinstance(doc, dict) else None
        s = shares(rows or [])
        if s is None:
            last_err = f"{year}: no World/China TOTAL rows"
            continue
        return {"status": "MEASURED", "year": year, **s,
                "fetched_at": now.isoformat(timespec="seconds")}
    return {"status": "UNMEASURED", "why": last_err}


def refresh(*, force: bool = False, now: datetime | None = None, path: Path = OUT,
            get: Callable[[str], str] = http_get) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    old = china_graph.load_measured(path)
    try:
        at = datetime.fromisoformat(str(old.get("generated_at")))
    except (TypeError, ValueError):
        at = None
    # a vintage that measured nothing is retried daily, not weekly: an outage is not a verdict
    wait = timedelta(days=REFRESH_DAYS if old.get("n_measured") else 1)
    if not force and at is not None and now - at < wait:
        return {**old, "refreshed": False}
    prev = old.get("countries") if isinstance(old.get("countries"), dict) else {}
    countries: dict[str, Any] = {}
    attempts: dict[str, str] = {}
    for iso, m49 in china_graph.country_codes().items():
        r = fetch_country(iso, m49, now, get)
        attempts[iso] = str(r.get("status"))
        if r.get("status") == "MEASURED":
            countries[iso] = {k: v for k, v in r.items() if k != "status"}
        elif isinstance(prev.get(iso), dict):
            countries[iso] = {**prev[iso], "kept_from_previous_vintage": True}
    years = [int(c["year"]) for c in countries.values() if c.get("year")]
    doc = {"generated_at": now.isoformat(timespec="seconds"),
           "organ": "desks/mt5/research/china_exposure_ingest.py",
           "source": "UN Comtrade public preview API (annual, HS, exports)",
           "stored": "derived ratios only (china_share, chapter_share); no raw trade values",
           "year": max(years) if years else None, "countries": countries,
           "attempts": attempts,
           "n_measured": sum(1 for s in attempts.values() if s == "MEASURED")}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return {**doc, "refreshed": True}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    d = refresh(force=a.force)
    print(f"china_exposure_ingest: refreshed={d.get('refreshed')} year={d.get('year')} "
          f"measured={d.get('n_measured')} attempts={d.get('attempts')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
