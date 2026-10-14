"""Google Trends mining miner.

Scrapes Google Trends for search volume spikes on trading terms.
High search volume for "buy gold" = retail FOMO = potential top.
Low search volume = indifference = potential bottom.

Uses Google Trends RSS/CSV (no API key needed).
"""

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    from research import hard_stop
except ImportError:                                         # pragma: no cover - layout
    import hard_stop  # type: ignore[no-redef,import-not-found]

OUT = BASE / "data" / "intelligence" / "google_trends"
OUT.mkdir(parents=True, exist_ok=True)
#: THE HARD STOP (standing project rule, `research/hard_stop.py`): the persisted backoff marker
#: and the register the block is recorded in. A 401/403/429 ends the pass; later passes request
#: nothing until the backoff expires; no retry around it, no UA rotation, no other host.
BLOCK_STATE = BASE / "data" / "google_trends_block.json"
BLOCKED_REGISTER = hard_stop.BLOCKED_REGISTER
REGISTER_KEY = "google_trends"
#: What the last pass did (status, requests, block), for the caller's one-line summary.
LAST_PASS: dict = {}

#: The desk's own declared identity, never a browser impersonation (audit 2026-10-14). One fixed
#: value: on a refusal it is never rotated.
DESK_UA = "quant-desk-google-trends/1.0 (research; public trend queries only)"
HEADERS = {"User-Agent": DESK_UA}

# Search terms that move markets
SEARCH_TERMS = {
    "forex": ["buy gold", "sell euro", "forex trading", "gold price", "usd jpy"],
    "commodities": ["oil price", "silver price", "copper price", "natural gas price"],
    "crypto": ["bitcoin buy", "ethereum buy", "crypto crash"],
    "macro": ["recession", "inflation", "interest rates", "fed rate"],
    "sentiment": ["stock market crash", "bull market", "bear market", "buy stocks"],
}

# Map search terms to symbols
TERM_TO_SYMBOLS = {
    "buy gold": ["XAUUSD"], "gold price": ["XAUUSD"], "sell gold": ["XAUUSD"],
    "silver price": ["XAGUSD"], "buy silver": ["XAGUSD"],
    "oil price": ["USOIL"], "natural gas price": ["NATGAS"],
    "copper price": ["COPPER"],
    "usd jpy": ["USDJPY"], "sell euro": ["EURUSD"], "buy euro": ["EURUSD"],
    "forex trading": ["EURUSD", "GBPUSD", "USDJPY"],
    "bitcoin buy": ["BTCUSD"], "bitcoin crash": ["BTCUSD"],
    "ethereum buy": ["ETHUSD"],
    "stock market crash": ["US500", "NAS100"],
    "bull market": ["US500"], "bear market": ["US500"],
    "recession": ["USDJPY", "XAUUSD", "US500"],
    "interest rates": ["USDJPY", "EURUSD", "XAUUSD"],
}


#: Weeks the trend reading needs: four recent against the four before them.
MIN_TIMELINE = 8


def point_value(point: dict) -> float | None:
    """A timeline point's value, or None when it carries none. NEVER a 0 for a missing value
    (`t.get("value", [0])` turned an absent point into a zero, which read as a -25% trend)."""
    try:
        raw = point.get("value")
        v = raw[0] if isinstance(raw, list | tuple) else raw
        if v is None or isinstance(v, bool):
            return None
        f = float(v)
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    return f if math.isfinite(f) else None      # NaN/inf is no reading either (audit 0b66b08de)


def complete_points(timeline: list[dict]) -> list[dict]:
    """The timeline without its trailing `isPartial` point(s): an unfinished week is not a
    reading of that week."""
    pts = list(timeline)
    while pts and pts[-1].get("isPartial"):
        pts.pop()
    return pts


def trend_reading(timeline: list[dict]) -> float | None:
    """Last 4 complete weeks vs the 4 before, in percent; None (UNMEASURED) when it cannot be
    computed.

    NEVER A ZERO FOR "NO DATA". A short timeline, a zero base or a point without a value used to
    be written as a number the seat series (`alt_seat_cells`, seat_google_trends) cannot tell from
    a genuine reading -- a silent zero entering a PIT series. No reading emits no row.
    """
    pts = complete_points(timeline)
    if len(pts) < MIN_TIMELINE:
        return None
    vals = [point_value(t) for t in pts[-MIN_TIMELINE:]]
    if any(v is None for v in vals):
        return None
    nums = [float(v) for v in vals if v is not None]
    recent = sum(nums[-4:]) / 4
    prev = sum(nums[:4]) / 4
    if prev <= 0:
        return None
    return (recent - prev) / prev * 100


def timeline_from(text: str) -> list[dict]:
    """The embedded `timelineData` array, decoded whole. The old non-greedy bracket match stopped at
    the first `]`, which is inside the first point's own `"value": [n]`, so it never decoded."""
    m = re.search(r'"timelineData":\s*', text)
    if not m:
        return []
    try:
        val, _end = json.JSONDecoder().raw_decode(text, m.end())
    except ValueError:
        return []
    return [t for t in val if isinstance(t, dict)] if isinstance(val, list) else []


def _load_block() -> dict | None:
    try:
        doc = json.loads(BLOCK_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _persist_hold(marker: dict) -> None:
    """Persist a hold (hard stop or robots) and record it in the register. A write that raises
    costs the record, never another request: the caller has already decided to stop."""
    LAST_PASS["block"] = marker
    try:
        BLOCK_STATE.parent.mkdir(parents=True, exist_ok=True)
        BLOCK_STATE.write_text(json.dumps(marker, indent=1), encoding="utf-8")
        hard_stop.record_block(marker, BLOCKED_REGISTER, key=REGISTER_KEY,
                               host="trends.google.com")
    except Exception as exc:
        LAST_PASS["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]


def _read_robots(url: str) -> tuple[int, str, dict]:
    """robots.txt at `url`'s own host, under the SAME User-Agent the pass sends (L0221):
    (status, body, response headers -- read only for Retry-After)."""
    try:
        resp = requests.get(hard_stop.robots_url(url), headers=HEADERS, timeout=15)
    except Exception:
        return 0, "", {}
    return (int(getattr(resp, "status_code", 0) or 0), str(getattr(resp, "text", "") or ""),
            dict(getattr(resp, "headers", None) or {}))


def mine_google_trends(now: datetime | None = None) -> list[dict]:
    """Fetch Google Trends data for trading terms, under the hard stop."""
    now = now or datetime.now(timezone.utc)
    discoveries: list[dict] = []
    prior = _load_block()
    LAST_PASS.clear()
    LAST_PASS.update({"requests": 0, "ok_responses": 0, "block": None})
    if hard_stop.active(prior, now):
        assert prior is not None
        LAST_PASS.update({"status": prior.get("status"), "skipped": True, "block": prior})
        return discoveries

    blocked = False
    LAST_PASS["timelines_read"] = 0
    robots: tuple[int, str, dict] | None = None
    for category, terms in SEARCH_TERMS.items():
        for term in terms:
            # Use Google Trends explore page (HTML scraping)
            url = f"https://trends.google.com/trends/explore?q={term.replace(' ', '+')}&date=today+12-m"
            # ROBOTS (audit 0b66b08de MF5; principal's scope rule 2026-10-13). Read once a pass at
            # the host, judged per exact path; a path it does not allow is not fetched and the
            # pass is held exactly as a 401/403/429 holds it.
            if robots is None:
                robots = _read_robots(url)
                LAST_PASS["requests"] += 1
                if robots[0] in hard_stop.HARD_STOP:
                    blocked = True
                    LAST_PASS.update({"status": hard_stop.HARD_STOP[robots[0]],
                                      "http_status": robots[0]})
                    try:
                        marker = hard_stop.block_marker(robots[0], "robots.txt", robots[2],
                                                        now, prior)
                    except Exception as exc:
                        LAST_PASS["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]
                    else:
                        _persist_hold(marker)
                    break
            verdict = hard_stop.robots_verdict(url, DESK_UA, robots[0], robots[1])
            LAST_PASS["robots"] = verdict
            if not verdict["allowed"]:
                blocked = True
                LAST_PASS.update({"status": hard_stop.ROBOTS_HOLD,
                                  "http_status": verdict.get("http_status")})
                try:
                    marker = hard_stop.robots_marker(verdict, "explore", now, prior)
                except Exception as exc:
                    LAST_PASS["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]
                else:
                    _persist_hold(marker)
                break
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
            except Exception:
                continue
            LAST_PASS["requests"] += 1
            status = int(getattr(resp, "status_code", 0) or 0)
            if status in hard_stop.HARD_STOP:
                # THE HARD STOP, DECIDED BEFORE ANYTHING CAN FAIL. `blocked` is set and the loop
                # ends whatever happens while the marker is persisted: a write that raises can
                # cost the record, never another request (audit 2026-10-14, MF4a).
                blocked = True
                LAST_PASS.update({"status": hard_stop.HARD_STOP[status],
                                  "http_status": status})
                try:
                    marker = hard_stop.block_marker(
                        status, "explore", dict(getattr(resp, "headers", None) or {}), now,
                        prior)
                except Exception as exc:
                    LAST_PASS["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]
                else:
                    _persist_hold(marker)
                break
            if status != 200:
                continue
            LAST_PASS["ok_responses"] += 1
            try:
                timeline = timeline_from(resp.text)
            except Exception:
                timeline = []
            if not timeline:
                continue                     # a 200 with no decodable timeline read nothing
            LAST_PASS["timelines_read"] += 1
            pts = complete_points(timeline)
            latest = point_value(pts[-1]) if pts else None
            # last 4 complete weeks vs previous 4; unmeasurable emits nothing rather than a zero
            trend_pct = trend_reading(timeline)
            syms = TERM_TO_SYMBOLS.get(term, [])
            if syms and latest is not None and latest > 0 and trend_pct is not None:
                discoveries.append({
                    "source": "google_trends",
                    "type": "search_volume",
                    "term": term,
                    "category": category,
                    "current_value": latest,
                    "trend_pct": round(trend_pct, 1),
                    "symbols": syms,
                    "confidence": min(0.7, abs(trend_pct) / 50),
                    "description": f"'{term}' search volume {trend_pct:+.1f}% vs 4-week avg",
                })
        if blocked:
            break

    if not blocked:
        # FETCHED only when a timeline was actually read: a 200 that carried none is not data
        LAST_PASS["status"] = "FETCHED" if LAST_PASS["timelines_read"] else "FAILED"
        if LAST_PASS["timelines_read"] and prior is not None:
            BLOCK_STATE.unlink(missing_ok=True)   # an answered, unrefused pass ends the ladder
    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_google_trends()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"google_trends: {len(discoveries)} discoveries saved "
          f"(pass {LAST_PASS.get('status')}, {LAST_PASS.get('requests')} requests)")
    return discoveries


if __name__ == "__main__":
    run_and_save()
