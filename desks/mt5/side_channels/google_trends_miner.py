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
#: THE HARD STOP (standing project rule, `research/hard_stop.py`). A 401/403/429 or a WAF
#: challenge ends the pass and places a hold on trends.google.com that a PERSON releases
#: (`python -m desks.mt5.research.hard_stop --release site:trends.google.com --by <name>`); until
#: then every pass sends zero requests. No timer releases it, no retry, no UA rotation, no other
#: host. BLOCK_STATE is this miner's own copy of its hold; ROBOTS_STATE keeps robots.txt a day.
BLOCK_STATE = BASE / "data" / "google_trends_block.json"
ROBOTS_STATE = BASE / "data" / "google_trends_robots.json"
BLOCKED_REGISTER = hard_stop.BLOCKED_REGISTER
REGISTER_KEY = "google_trends"
HOST = "trends.google.com"
#: What the last pass did (status, requests, block), for the caller's one-line summary.
LAST_PASS: dict = {}

#: The desk's one declared identity, with a contact path (`hard_stop.DESK_UA`): never a browser,
#: never rotated on a refusal.
DESK_UA = hard_stop.DESK_UA
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


def _load_json(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _load_block() -> dict | None:
    return _load_json(BLOCK_STATE)


def _hold(verdict: str, status: int | None, url: str, now: datetime) -> None:
    """Place the person-released hold: this miner's copy first, then the register. A write that
    raises costs the record, never another request: the caller has already stopped."""
    LAST_PASS.update({"status": hard_stop.pass_status({"verdict": verdict, "status": status}),
                      "http_status": status})
    try:
        record = hard_stop.hold_record(verdict, status, url, now)
        LAST_PASS["block"] = record
        BLOCK_STATE.parent.mkdir(parents=True, exist_ok=True)
        BLOCK_STATE.write_text(json.dumps(record, indent=1), encoding="utf-8")
        hard_stop.place_hold(record, BLOCKED_REGISTER, source_key=REGISTER_KEY)
    except Exception as exc:
        LAST_PASS["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]


def _robots(url: str, now: datetime) -> tuple[int, str, dict] | None:
    """robots.txt for `url`'s host: the day-old reading when there is one (None = not read now),
    else read under the SAME User-Agent the pass sends (L0221) and kept when definitive."""
    cache = _load_json(ROBOTS_STATE) or {}
    hit = hard_stop.robots_cached(cache, url, now)
    if hit is not None:
        return hit[0], hit[1], {}
    try:
        resp = requests.get(hard_stop.robots_url(url), headers=HEADERS, timeout=15)
        got = (int(getattr(resp, "status_code", 0) or 0), str(getattr(resp, "text", "") or ""),
               dict(getattr(resp, "headers", None) or {}))
    except Exception:
        got = (0, "", {})
    LAST_PASS["requests"] += 1
    LAST_PASS["robots_read"] = True
    if not hard_stop.refusal(got[0], got[2], got[1]):
        hard_stop.robots_remember(cache, url, got[0], got[1], now)
        try:
            ROBOTS_STATE.parent.mkdir(parents=True, exist_ok=True)
            ROBOTS_STATE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        except OSError:
            pass
    return got


def mine_google_trends(now: datetime | None = None) -> list[dict]:
    """Fetch Google Trends data for trading terms, under the hard stop and robots."""
    now = now or datetime.now(timezone.utc)
    discoveries: list[dict] = []
    prior = _load_block()
    LAST_PASS.clear()
    LAST_PASS.update({"requests": 0, "ok_responses": 0, "block": None, "robots_disallowed": 0})
    held = hard_stop.active_hold(BLOCKED_REGISTER, [hard_stop.host_key(HOST)], prior)
    if held is not None:
        LAST_PASS.update({"status": hard_stop.pass_status(held), "skipped": True,
                          "block": held})
        return discoveries
    if prior is not None:
        BLOCK_STATE.unlink(missing_ok=True)   # a person released it: this copy is spent

    blocked = False
    LAST_PASS["timelines_read"] = 0
    robots: tuple[int, str, dict] | None = None
    for category, terms in SEARCH_TERMS.items():
        for term in terms:
            # Use Google Trends explore page (HTML scraping)
            url = ("https://trends.google.com/trends/explore?q="
                   f"{term.replace(' ', '+')}&date=today+12-m")
            # ROBOTS (audit 0b66b08de MF5; principal's scope rule 2026-10-13): read at the host
            # at most once a day, judged per exact path. A refusal on robots.txt itself is a
            # person-held hold; an unavailable one stops this pass; a Disallow skips the URL.
            if robots is None:
                robots = _robots(url, now)
                if (verdict0 := hard_stop.refusal(robots[0], robots[2], robots[1])):
                    blocked = True
                    _hold(hard_stop.VERDICT_ROBOTS_HOLD if verdict0 == hard_stop.VERDICT_HARD_STOP
                          else verdict0, robots[0], hard_stop.robots_url(url), now)
                    break
            verdict = hard_stop.robots_verdict(url, robots[0], robots[1])
            LAST_PASS["robots"] = verdict
            if verdict["state"] == "UNAVAILABLE":
                blocked = True
                LAST_PASS.update({"status": "ROBOTS_UNAVAILABLE",
                                  "http_status": verdict.get("http_status")})
                break
            if not verdict["allowed"]:
                LAST_PASS["robots_disallowed"] += 1
                continue
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
            except Exception:
                continue
            LAST_PASS["requests"] += 1
            status = int(getattr(resp, "status_code", 0) or 0)
            body = str(getattr(resp, "text", "") or "")
            hdrs = dict(getattr(resp, "headers", None) or {})
            if (why := hard_stop.refusal(status, hdrs, body)):
                # THE HARD STOP, DECIDED BEFORE ANYTHING CAN FAIL. `blocked` is set and the loop
                # ends whatever happens while the hold is persisted: a write that raises can
                # cost the record, never another request (audit 2026-10-14, MF4a).
                blocked = True
                if (ra := hard_stop.retry_after_s(hdrs.get("Retry-After"), now)) is not None:
                    LAST_PASS["retry_after_s"] = ra          # recorded; it releases nothing
                _hold(why, status, url, now)
                break
            if status != 200:
                continue
            LAST_PASS["ok_responses"] += 1
            try:
                timeline = timeline_from(body)
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
        n_terms = sum(len(t) for t in SEARCH_TERMS.values())
        if LAST_PASS["robots_disallowed"] == n_terms:
            LAST_PASS["status"] = "ROBOTS_DISALLOWED"
            try:
                hard_stop.note_robots(LAST_PASS.get("robots") or {}, BLOCKED_REGISTER,
                                      source_key=REGISTER_KEY)
            except Exception as exc:
                LAST_PASS["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]
        else:
            LAST_PASS["status"] = "FETCHED" if LAST_PASS["timelines_read"] else "FAILED"
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
