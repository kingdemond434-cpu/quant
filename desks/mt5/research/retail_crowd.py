"""RETAIL FX CROWD RECORDER -- hourly, point-in-time, append-only. History cannot be backfilled.

    python desks/mt5/research/retail_crowd.py --once          # fetch, append, features, hypotheses
    python desks/mt5/research/retail_crowd.py --once --no-fetch   # rebuild features from the store

WHY IT IS A RECORDER FIRST. Retail positioning (% of client accounts long / short per symbol) is
published as a NOW-snapshot by every source this module reads. None of them serves its own
history, so an hour not recorded is an hour the desk can never test on. That is why this leg runs
on the CORE hourly plan and sits in `leg_rotation.ALWAYS_RUN` beside `record_tape`: capture is
irreversible, judging is not.

SOURCES, IN ORDER (each a row in `SOURCES`, each with its access label recorded, LAWS 5e):

  myfxbook_api   Myfxbook's official JSON API (`/api/login.json` -> `/api/get-community-
                 outlook.json` -> `/api/logout.json`) with the account credentials held on the
                 box. Credentials are read only through `libs.core.secrets` (QP_SECRET_MYFXBOOK_*),
                 the env names `asia_sources.json` already declares (MYFXBOOK_SESSION, or
                 MYFXBOOK_EMAIL + MYFXBOOK_PASSWORD) or `data/secrets/myfxbook.json`, and are never
                 printed, logged, stored in a raw snapshot or written into a URL that is recorded.
                 One outlook call per hour sits far inside the free tier's 100 per day.
  myfxbook_html  The public outlook page, ONLY when the API is unconfigured or failing. Cloudflare's
                 managed challenge fronts that host (seed_miners.SOURCE_WALLS); a challenge is
                 recorded as WALLED and never solved -- solving it is crossing an access control.
  dukascopy      Dukascopy SWFX sentiment, public page, no login.
  fxblue         FX Blue live sentiment, public page, no login.
  ig             IG client sentiment, public page, no login.

A source answering with a login wall, a paywall or a bot challenge is WALLED with the evidence and
is not retried inside the pass: no logins beyond the API's own, no cookies, no proxies, no
rate-limit bypass, one request per source per hour.

THE STORE (shared layout with the copy-trade crowd recorder):
  data/lake/series/retail_crowd.csv          LONG, append-only, one row per (pass, source, symbol):
                                             captured_at, available_time, source, cohort, symbol,
                                             raw_symbol, n_accounts, n_positions, long_lots,
                                             short_lots, net_frac, long_pct, short_pct,
                                             access_label, payload_sha. Never rewritten.
  data/lake/series/retail_crowd.pit.json     the PIT sidecar: clock, stamp rule, columns, sources.
  data/crowd/retail/raw/<source>/<ts>.json.gz  every response body, immutable, one file per fetch.
  data/lake/series/retail_crowd_wide.csv     DERIVED VIEW rebuilt from the long store each pass:
                                             one row per hour, `<SYM>__net` = mean net_frac across
                                             sources, with `available_time` = the latest capture
                                             in that hour. It is what `exogenous_conditioner` and
                                             `alt_series_momentum` read; history lives in the long
                                             store, so rebuilding it overwrites nothing.

PIT. `captured_at` is the UTC instant the response arrived; a reading cannot have been known
before it, so `available_time = captured_at`. The hypotheses below carry `lag_hours = 3`, which
the families apply BEFORE aligning to the broker-clock bar index (UTC+2/+3), so no join can land
early.

FEATURES (reports/RETAIL_CROWD.json, every pass): per symbol, crowd net %, its z-score against its
own trailing history, its change over 1h and 24h, and a contrarian-extreme flag.

HYPOTHESES, PRE-REGISTERED AND CHARGED ONCE. Three per hypothesis-lane symbol (`HYPOTHESES`):
fade the crowd at an extreme level, fade a 1h shift, fade a 24h shift. A hypothesis is donated to
`data/intelligence/retail_crowd/` as an EXACT_RECIPE row exactly ONCE, the pass its symbol's
recorded history first reaches `MIN_HISTORY_OBS` observations over `MIN_HISTORY_DAYS` days --
before that the gauntlet would judge a series too short to fire and spend a trial on the
fallback, not on the mechanism. `data/crowd/retail/emitted.jsonl` is the once-ledger: a
hypothesis already in it is never donated again, so no pass ever re-charges the multiplicity
budget. Until then the artifact names every pending hypothesis and the date it becomes eligible.

SYMBOLS. Broker names are mapped onto the Fusion registry by a small private alias table
(`_ALIASES`). It should converge onto `libs/data/crowd_symbols.py` (owned by the copy-trade crowd
recorder) once that lands; nothing here edits that file. A name the registry cannot price is
counted under `unmapped`, never guessed. Single-name equities are recorded but never hypothesised
(`universe_policy.may_hypothesise`); crypto-exchange venues are not a source here at all.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SERIES_DIR = DESK / "data" / "lake" / "series"
STORE = SERIES_DIR / "retail_crowd.csv"
SIDECAR = SERIES_DIR / "retail_crowd.pit.json"
WIDE = SERIES_DIR / "retail_crowd_wide.csv"
WIDE_SOURCE = "retail_crowd_wide"            # the `source` param the families read
CROWD_DIR = DESK / "data" / "crowd" / "retail"
RAW_DIR = CROWD_DIR / "raw"
STATE = CROWD_DIR / "state.json"
EMITTED = CROWD_DIR / "emitted.jsonl"
SEAT = "retail_crowd"
INTEL = DESK / "data" / "intelligence" / SEAT
OUT = DESK / "reports" / "RETAIL_CROWD.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
SECRET_FILES = (ROOT / "data" / "secrets" / "myfxbook.json",
                DESK / "data" / "secrets" / "myfxbook.json")

USER_AGENT = "quant-desk-collector/1.0 (retail crowd recorder; hourly)"
TIMEOUT_S = 25
MAX_BODY_BYTES = 4 * 1024 * 1024

COLUMNS: tuple[str, ...] = (
    "captured_at", "available_time", "source", "cohort", "symbol", "raw_symbol", "n_accounts",
    "n_positions", "long_lots", "short_lots", "net_frac", "long_pct", "short_pct",
    "access_label", "payload_sha")

#: Hourly observations a symbol's series needs, over at least this many days, before its
#: hypotheses are donated. 60 days of hours: the z-window below is 720 observations (30 days)
#: and the gauntlet needs out-of-sample room after it.
MIN_HISTORY_OBS = 1440
MIN_HISTORY_DAYS = 60
Z_WINDOW = 720
Z_MIN_OBS = 24
EXTREME_Z = 2.0
EXTREME_NET = 0.5            # 75% / 25% one-sided
LAG_HOURS = 3                # broker clock is UTC+2/+3; held back before any join

#: Each source and its access label (LAWS 5e: labels route use and weight, they never stop
#: mining; the refused acts -- login walls, paywalls, access controls -- are refused by the
#: fetch path itself). `terms_note` says what was and was not read, honestly.
SOURCES: dict[str, dict[str, str]] = {
    "myfxbook_api": {
        "url": "https://www.myfxbook.com/api/get-community-outlook.json",
        "access_label": "LICENSED",
        "terms_note": ("official API under the desk's own Myfxbook account; free tier limit 100 "
                       "outlook requests/day, honoured at 24/day. API terms not re-read from the "
                       "build container (its proxy refuses myfxbook.com); redistribution withheld"),
    },
    "myfxbook_html": {
        "url": "https://www.myfxbook.com/community/outlook",
        "access_label": "PUBLIC_WITH_TERMS",
        "terms_note": ("fallback only. The host is fronted by a Cloudflare managed challenge "
                       "(seed_miners.SOURCE_WALLS, 2026-08-26); a challenge is WALLED, never solved"),
    },
    "dukascopy": {
        "url": "https://www.dukascopy.com/swiss/english/marketwatch/sentiment/",
        "access_label": "ACCESS_UNCLEAR",
        "terms_note": ("public page, no login. Site terms not read: unreachable from the build "
                       "container (proxy policy). Mined with the label; redistribution withheld"),
    },
    "fxblue": {
        "url": "https://www.fxblue.com/market-data/tools/sentiment",
        "access_label": "PUBLIC_WITH_TERMS",
        "terms_note": ("public page, no login. book_forensics.TERMS: fxblue robots.txt refuses "
                       "/terms from this host (2026-10-06), terms unread -> to_confirm; mined with "
                       "the label, redistribution withheld"),
    },
    "ig": {
        "url": "https://www.ig.com/uk/ig-client-sentiment",
        "access_label": "ACCESS_UNCLEAR",
        "terms_note": ("public page, no login. Site terms not read: unreachable from the build "
                       "container (proxy policy). Mined with the label; redistribution withheld"),
    },
}

#: The three pre-registered hypotheses per symbol. Contrarian on every one: the mechanism is that
#: a one-sided retail crowd is a supply of stops and of forced exits, so price tends to move
#: against it (the B-book debias prior: retail ruin is partly cost extraction, which is exactly
#: why the gauntlet, not this table, decides).
HYPOTHESES: tuple[dict[str, Any], ...] = (
    {"key": "crowd_extreme_fade", "family": "exogenous_conditioner",
     "params": {"transform": "level_z", "threshold": EXTREME_Z, "side_when_high": -1,
                "lag_hours": LAG_HOURS, "z_window": Z_WINDOW, "ttl_bars": 24},
     "mechanism": ("retail net positioning at a 2-sigma extreme of its own history: the crowd's "
                   "stops and margin exits sit on the far side, so fade it")},
    {"key": "crowd_shift_fade_1h", "family": "alt_series_momentum",
     "params": {"lookback": 1, "threshold": EXTREME_Z, "side_when_up": -1,
                "lag_hours": LAG_HOURS, "z_window": Z_WINDOW, "ttl_bars": 12},
     "mechanism": ("a 2-sigma one-hour lurch in retail net positioning is the crowd chasing a "
                   "move; fade the chase")},
    {"key": "crowd_shift_fade_24h", "family": "alt_series_momentum",
     "params": {"lookback": 24, "threshold": EXTREME_Z, "side_when_up": -1,
                "lag_hours": LAG_HOURS, "z_window": Z_WINDOW, "ttl_bars": 48},
     "mechanism": ("a 2-sigma one-day build-up of retail positioning is crowding in progress; "
                   "fade it over the following two days")},
)

#: Broker / site spellings -> Fusion registry names. Private on purpose (see module docstring).
_ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD", "SILVER": "XAGUSD", "SPOTGOLD": "XAUUSD", "SPOTSILVER": "XAGUSD",
    "XAUUSDM": "XAUUSD", "XAGUSDM": "XAGUSD",
    "US500": "US500", "SPX500": "US500", "SP500": "US500", "SPX": "US500", "USSPX500": "US500",
    "US30": "US30", "WALLSTREET": "US30", "DJ30": "US30", "DOW": "US30", "USA30": "US30",
    "NAS100": "NAS100", "USTECH100": "NAS100", "USTEC": "NAS100", "NDX100": "NAS100",
    "US100": "NAS100", "NASDAQ100": "NAS100",
    "GER40": "GER40", "GER30": "GER40", "DE40": "GER40", "DE30": "GER40", "GERMANY40": "GER40",
    "DAX": "GER40", "DAX40": "GER40",
    "UK100": "UK100", "FTSE100": "UK100", "FTSE": "UK100",
    "JPN225": "JPN225", "JP225": "JPN225", "JAPAN225": "JPN225", "NIKKEI": "JPN225",
    "NIKKEI225": "JPN225",
    "FRA40": "FRA40", "FRANCE40": "FRA40", "CAC40": "FRA40",
    "AUS200": "AUS200", "AUSTRALIA200": "AUS200", "ASX200": "AUS200",
    "HK50": "HK50", "HONGKONG50": "HK50", "HSI": "HK50",
    "EUSTX50": "EUSTX50", "EU50": "EUSTX50", "EUSTOXX50": "EUSTX50", "STOXX50": "EUSTX50",
    "US2000": "US2000", "RUSSELL2000": "US2000",
    "OIL": "XTIUSD", "USOIL": "XTIUSD", "WTI": "XTIUSD", "CRUDE": "XTIUSD", "OILUSCRUDE": "XTIUSD",
    "UKOIL": "XBRUSD", "BRENT": "XBRUSD", "OILBRENTCRUDE": "XBRUSD",
    "NATGAS": "XNGUSD", "NATURALGAS": "XNGUSD", "COPPER": "XCUUSD",
    "PLATINUM": "XPTUSD", "PALLADIUM": "XPDUSD",
}
_SUFFIX = re.compile(r"(?:\.(?:X|R|M|PRO|ECN|RAW|I)|_?(?:M|PRO|ECN|RAW|I))$")

Fetcher = Callable[[str], tuple[int, str]]


# ------------------------------------------------------------------ small IO helpers
def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _read_json(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, p)
    finally:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()


def _universe(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _read_json(path or UNIVERSE, {}) or {}
    return {k: v for k, v in doc.items() if isinstance(v, dict)}


def below_normal() -> dict[str, Any]:
    """Run beneath the release and risk tasks (the judge_prescreen mechanism): lower this
    process's own priority and SAY whether it took. Never fails the pass."""
    try:
        import psutil

        me = psutil.Process()
        want = psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10
        me.nice(want)
        got = me.nice()
        return {"applied": bool(got == want), "requested": str(want), "observed": str(got)}
    except Exception as exc:
        return {"applied": False, "why": f"{type(exc).__name__}: {exc}"[:160]}


# ------------------------------------------------------------------ symbols
def map_symbol(raw: str, universe: Iterable[str]) -> str | None:
    """A site's instrument name -> the registry's own spelling, or None (never a guess)."""
    names = {u.upper(): u for u in universe}
    t = re.sub(r"[^A-Za-z0-9.]", "", str(raw or "")).upper()
    if not t:
        return None
    for cand in (t, _SUFFIX.sub("", t), t.replace(".", "")):
        c = cand.replace(".", "")
        hit = _ALIASES.get(c, c)
        if hit.upper() in names:
            return names[hit.upper()]
    return None


def _hypothesis_lane(symbol: str) -> bool:
    try:
        import universe_policy as up
        return bool(up.lane(symbol) == up.HYPOTHESIS)
    except Exception:
        return False


# ------------------------------------------------------------------ credentials (never printed)
def _credentials(env: dict[str, str] | None = None) -> dict[str, str]:
    """{'session'} or {'email','password'} or {}. Values are returned to the caller only."""
    e = os.environ if env is None else env
    out: dict[str, str] = {}
    with contextlib.suppress(Exception):
        from libs.core import secrets as _sec
        prov = _sec.get_default_provider()
        if env is None:
            for name, key in (("MYFXBOOK_SESSION", "session"), ("MYFXBOOK_EMAIL", "email"),
                              ("MYFXBOOK_PASSWORD", "password")):
                if prov.has_secret(name):
                    out[key] = prov.get_secret(name)
    for name, key in (("MYFXBOOK_SESSION", "session"), ("MYFXBOOK_EMAIL", "email"),
                      ("MYFXBOOK_PASSWORD", "password")):
        if not out.get(key) and e.get(name):
            out[key] = str(e[name])
    if not out.get("session") and not (out.get("email") and out.get("password")) and env is None:
        for p in SECRET_FILES:
            doc = _read_json(p, {}) or {}
            if isinstance(doc, dict):
                for key in ("session", "email", "password"):
                    if not out.get(key) and doc.get(key):
                        out[key] = str(doc[key])
    if out.get("session"):
        return {"session": out["session"]}
    if out.get("email") and out.get("password"):
        return {"email": out["email"], "password": out["password"]}
    return {}


def _redact(text: str, secrets: Iterable[str]) -> str:
    s = str(text)
    for v in secrets:
        if v:
            s = s.replace(v, "<redacted>")
            s = s.replace(urllib.parse.quote(v, safe=""), "<redacted>")
    return s


# ------------------------------------------------------------------ HTTP
def http_get(url: str) -> tuple[int, str]:
    """One plain GET: our own UA, no cookies, no proxy tricks, one attempt."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json,text/html;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 -- fixed https URLs
            body = r.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
            return int(getattr(r, "status", 200) or 200), body
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(200_000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return int(exc.code), body


_WALL_MARKERS = ("just a moment", "cf-challenge", "challenge-platform", "ctype: 'managed'",
                 "cf_chl_", "attention required! | cloudflare", "captcha",
                 "please log in", "please login", "sign in to continue", "subscribe to continue")


def is_walled(status: int, body: str) -> str | None:
    """The reason a response is an access control rather than content, or None."""
    low = (body or "")[:20000].lower()
    for m in _WALL_MARKERS:
        if m in low:
            return f"access control on the page ({m!r}); not bypassed"
    if status in (401, 402, 403, 407, 429, 451):
        return f"HTTP {status}: refused by the server; not retried this pass"
    return None


# ------------------------------------------------------------------ parsers
def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(str(v).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def normalise(raw_symbol: str, long_pct: Any, short_pct: Any, **extra: Any) -> dict[str, Any] | None:
    """One observation with long/short in percent summing to 100, or None when unreadable."""
    lp, sp = _num(long_pct), _num(short_pct)
    if lp is None and sp is None:
        return None
    if lp is not None and sp is not None and lp + sp > 0 and lp + sp <= 1.0001:
        lp, sp = lp * 100.0, sp * 100.0           # fractions
    if lp is None:
        lp = 100.0 - float(sp or 0.0)
    if sp is None:
        sp = 100.0 - lp
    tot = lp + sp
    if tot <= 0 or lp < 0 or sp < 0 or lp > 100.0001 or sp > 100.0001:
        return None
    lp, sp = 100.0 * lp / tot, 100.0 * sp / tot
    obs = {"raw_symbol": str(raw_symbol), "long_pct": round(lp, 4), "short_pct": round(sp, 4),
           "net_frac": round((lp - sp) / 100.0, 6)}
    for k in ("n_accounts", "n_positions", "long_lots", "short_lots"):
        v = _num(extra.get(k))
        obs[k] = v
    return obs


def parse_myfxbook_api(doc: Any) -> list[dict[str, Any]]:
    """`get-community-outlook.json`: {"error": false, "symbols": [{name, longPercentage, ...}]}."""
    if not isinstance(doc, dict) or doc.get("error") is True:
        return []
    out = []
    for s in doc.get("symbols") or []:
        if not isinstance(s, dict):
            continue
        lpos, spos = _num(s.get("longPositions")), _num(s.get("shortPositions"))
        o = normalise(str(s.get("name") or ""), s.get("longPercentage"),
                      s.get("shortPercentage"),
                      n_positions=(_num(s.get("totalPositions"))
                                   or ((lpos or 0) + (spos or 0)) or None),
                      long_lots=s.get("longVolume"), short_lots=s.get("shortVolume"))
        if o and o["raw_symbol"]:
            out.append(o)
    return out


_SYM_KEYS = ("symbol", "name", "instrument", "instrumentname", "pair", "market", "marketname",
             "ticker", "epic", "title", "currencypair", "asset")
_LONG_KEYS = ("longpercentage", "long_pct", "longpct", "long", "longpercent", "buy",
              "buypercentage", "buypct", "clientslong", "longposition", "longpositionpercentage",
              "percentlong", "long_percentage", "bulls", "bullish")
_SHORT_KEYS = ("shortpercentage", "short_pct", "shortpct", "short", "shortpercent", "sell",
               "sellpercentage", "sellpct", "clientsshort", "shortposition",
               "shortpositionpercentage", "percentshort", "short_percentage", "bears", "bearish")


def _walk(obj: Any, out: list[dict[str, Any]], depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(obj, dict):
        low = {str(k).lower().replace("-", "").replace(" ", ""): v for k, v in obj.items()}
        sym = next((low[k] for k in _SYM_KEYS if isinstance(low.get(k), str) and low[k]), None)
        lv = next((low[k] for k in _LONG_KEYS if _num(low.get(k)) is not None), None)
        sv = next((low[k] for k in _SHORT_KEYS if _num(low.get(k)) is not None), None)
        if sym and (lv is not None or sv is not None):
            o = normalise(sym, lv, sv, n_accounts=low.get("traders") or low.get("accounts"),
                          n_positions=low.get("positions") or low.get("totalpositions"),
                          long_lots=low.get("longvolume"), short_lots=low.get("shortvolume"))
            if o:
                out.append(o)
        for v in obj.values():
            _walk(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, out, depth + 1)


def parse_generic_json(text_or_doc: Any) -> list[dict[str, Any]]:
    """Any JSON / JSONP document: every object naming an instrument and a long or short share."""
    doc = text_or_doc
    if isinstance(doc, str):
        s = doc.strip()
        m = re.match(r"^[\w.$]+\s*\((.*)\)\s*;?\s*$", s, re.DOTALL)   # JSONP
        if m:
            s = m.group(1)
        try:
            doc = json.loads(s)
        except ValueError:
            return []
    out: list[dict[str, Any]] = []
    _walk(doc, out)
    return _dedupe(out)


_JSON_BLOB = re.compile(r"(\{[^<>]{20,}?\}|\[[^<>]{20,}?\])", re.DOTALL)
_LABELLED_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of [a-z ]{0,30}?)?\b(long|short)\b",
                           re.IGNORECASE)
_NAME_TAIL = re.compile(r"([A-Z][A-Za-z0-9/&.\-]*(?: [A-Z0-9][A-Za-z0-9/&.\-]*){0,2})\s*$")


def _text_pairs(text: str) -> list[dict[str, Any]]:
    """'N% long' / 'M% short' pairs, each named by the instrument written just before it."""
    hits = list(_LABELLED_PCT.finditer(text))
    out: list[dict[str, Any]] = []
    i, prev_end = 0, 0
    while i + 1 < len(hits):
        a, b = hits[i], hits[i + 1]
        la, lb = a.group(2).lower(), b.group(2).lower()
        if la == lb or b.start() - a.end() > 120:
            i += 1
            continue
        name = _NAME_TAIL.search(text[prev_end:a.start()].strip())
        if name:
            lv = a.group(1) if la == "long" else b.group(1)
            sv = b.group(1) if lb == "short" else a.group(1)
            o = normalise(name.group(1).strip(), lv, sv)
            if o:
                out.append(o)
        prev_end = b.end()
        tail = re.match(r"[a-z ,.]{0,40}", text[prev_end:])     # "... on this market"
        prev_end += tail.end() if tail else 0
        i += 2
    return out


def _strip_tags(html: str) -> str:
    t = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", html, flags=re.DOTALL | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def parse_html(html: str) -> list[dict[str, Any]]:
    """A public sentiment page: embedded JSON first, then labelled 'N% long / M% short' text.

    Never reads an unlabelled pair of percentages -- which number is long is exactly what a
    contrarian signal must not guess."""
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", html or "", re.DOTALL | re.I):
        body = m.group(1)
        for blob in _JSON_BLOB.findall(body):
            with contextlib.suppress(ValueError, RecursionError):
                _walk(json.loads(blob), out)
    for m in re.finditer(r"data-(?:symbol|instrument|market)=\"([^\"]+)\"[^>]*?"
                         r"data-long=\"([\d.]+)\"(?:[^>]*?data-short=\"([\d.]+)\")?",
                         html or "", re.I):
        o = normalise(m.group(1), m.group(2), m.group(3))
        if o:
            out.append(o)
    if not out:
        out.extend(_text_pairs(_strip_tags(html or "")))
    return _dedupe(out)


def parse_myfxbook_html(html: str) -> list[dict[str, Any]]:
    """The outlook page's per-symbol popover tables: rows labelled Short / Long with a percent.

    The fallback only; the labelled-row reading replaces seed_miners' old pct_a/pct_b capture,
    which never knew which number was long."""
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"id=\"outlookSymbolPopover(?:Table)?([A-Z0-9.]{3,12})\"(.*?)</table>",
                         html or "", re.DOTALL | re.I):
        sym, block = m.group(1), m.group(2)
        sv = re.search(r"Short\s*</td>\s*<td[^>]*>\s*([\d.]+)\s*%", block, re.I)
        lv = re.search(r"Long\s*</td>\s*<td[^>]*>\s*([\d.]+)\s*%", block, re.I)
        if sv or lv:
            o = normalise(sym, lv.group(1) if lv else None, sv.group(1) if sv else None)
            if o:
                out.append(o)
    return out or parse_html(html)


def _dedupe(obs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for o in obs:
        seen.setdefault(o["raw_symbol"].upper(), o)
    return list(seen.values())


PARSERS: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "myfxbook_html": parse_myfxbook_html,
    "dukascopy": lambda body: parse_generic_json(body) or parse_html(body),
    "fxblue": lambda body: parse_generic_json(body) or parse_html(body),
    "ig": lambda body: parse_generic_json(body) or parse_html(body),
}


# ------------------------------------------------------------------ fetching
def _raw_snapshot(source: str, at: datetime, url: str, status: int, body: str,
                  raw_dir: Path) -> str:
    sha = hashlib.sha256((body or "").encode("utf-8", errors="replace")).hexdigest()
    d = raw_dir / source
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{at.strftime('%Y%m%dT%H%M%SZ')}.json.gz"
    if not p.exists():                     # immutable: one file per fetch, never rewritten
        payload = {"source": source, "fetched_at": _iso(at), "url": url, "status": status,
                   "sha256": sha, "body": body}
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    return sha


def fetch_myfxbook_api(fetch: Fetcher = http_get, creds: dict[str, str] | None = None
                       ) -> dict[str, Any]:
    """{'status', 'why', 'body', 'url', 'obs'}. Logs in only when no session is held, and logs
    out of a session it opened. No credential reaches the returned dict."""
    c = _credentials() if creds is None else creds
    secrets = [v for v in c.values() if v]
    base = "https://www.myfxbook.com/api"
    url_public = f"{base}/get-community-outlook.json"
    if not c:
        return {"status": "UNCONFIGURED", "url": url_public, "obs": [],
                "why": ("no Myfxbook credentials on this host (QP_SECRET_MYFXBOOK_*, "
                        "MYFXBOOK_SESSION / MYFXBOOK_EMAIL+MYFXBOOK_PASSWORD, or "
                        "data/secrets/myfxbook.json)")}
    opened = False
    session = c.get("session", "")
    try:
        if not session:
            q = urllib.parse.urlencode({"email": c["email"], "password": c["password"]})
            st, body = fetch(f"{base}/login.json?{q}")
            wall = is_walled(st, body)
            if wall:
                return {"status": "WALLED", "why": _redact(wall, secrets), "url": url_public,
                        "obs": []}
            try:
                doc = json.loads(body)
            except ValueError:
                return {"status": "API_ERROR", "why": f"login answered non-JSON (HTTP {st})",
                        "url": url_public, "obs": []}
            if not isinstance(doc, dict) or doc.get("error") or not doc.get("session"):
                msg = str((doc or {}).get("message") or "no session") if isinstance(doc, dict) \
                    else "no session"
                return {"status": "API_ERROR", "why": _redact(f"login refused: {msg}"[:200],
                                                               secrets),
                        "url": url_public, "obs": []}
            session = urllib.parse.unquote(str(doc["session"]))
            secrets.append(session)
            opened = True
        st, body = fetch(f"{url_public}?{urllib.parse.urlencode({'session': session})}")
        wall = is_walled(st, body)
        if wall:
            return {"status": "WALLED", "why": _redact(wall, secrets), "url": url_public,
                    "obs": []}
        try:
            doc = json.loads(body)
        except ValueError:
            return {"status": "API_ERROR", "why": f"outlook answered non-JSON (HTTP {st})",
                    "url": url_public, "obs": []}
        if isinstance(doc, dict) and doc.get("error"):
            return {"status": "API_ERROR",
                    "why": _redact(str(doc.get("message") or "error")[:200], secrets),
                    "url": url_public, "obs": []}
        obs = parse_myfxbook_api(doc)
        return {"status": "OK" if obs else "PARSE_EMPTY", "url": url_public, "obs": obs,
                "http": st, "body": _redact(body, secrets),
                "why": "" if obs else "outlook JSON carried no readable symbols"}
    except Exception as exc:  # a transport failure is UNREACHABLE, never a crash of the leg
        return {"status": "UNREACHABLE", "url": url_public, "obs": [],
                "why": _redact(f"{type(exc).__name__}: {exc}", secrets)[:240]}
    finally:
        if opened and session:
            with contextlib.suppress(Exception):
                fetch(f"{base}/logout.json?{urllib.parse.urlencode({'session': session})}")


def fetch_page(source: str, fetch: Fetcher = http_get) -> dict[str, Any]:
    url = SOURCES[source]["url"]
    try:
        st, body = fetch(url)
    except Exception as exc:
        return {"status": "UNREACHABLE", "url": url, "obs": [],
                "why": f"{type(exc).__name__}: {exc}"[:240]}
    wall = is_walled(st, body)
    if wall:
        return {"status": "WALLED", "url": url, "obs": [], "why": wall, "http": st,
                "body": body}
    if st >= 400:
        return {"status": "UNREACHABLE", "url": url, "obs": [], "why": f"HTTP {st}", "http": st,
                "body": body}
    obs = PARSERS[source](body)
    return {"status": "OK" if obs else "PARSE_EMPTY", "url": url, "obs": obs, "http": st,
            "body": body, "why": "" if obs else ("fetched and matched no labelled long/short "
                                                 "reading; needs a parser, not a retry")}


# ------------------------------------------------------------------ the append-only store
def append_rows(rows: list[dict[str, Any]], store: Path = STORE) -> int:
    """Append, never rewrite. A missing file gets its header; an existing one only grows."""
    if not rows:
        return 0
    store.parent.mkdir(parents=True, exist_ok=True)
    new = not store.exists() or store.stat().st_size == 0
    with store.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNS), extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in COLUMNS})
    return len(rows)


def write_sidecar(path: Path = SIDECAR) -> None:
    doc = {"series": "retail_crowd", "layout": "long", "clock": "utc",
           "available_time_rule": "available_time = captured_at (the instant the response "
                                  "arrived); nothing is known before it",
           "append_only": True, "cohort": "all", "columns": list(COLUMNS),
           "derived_view": {"path": WIDE.name, "source_param": WIDE_SOURCE,
                            "rule": "mean net_frac across sources per UTC hour; available_time "
                                    "= latest capture in the hour; rebuilt each pass"},
           "lag_hours_in_hypotheses": LAG_HOURS,
           "sources": {k: {"access_label": v["access_label"], "terms_note": v["terms_note"]}
                       for k, v in SOURCES.items()},
           "writer": "desks/mt5/research/retail_crowd.py"}
    _write_atomic(path, json.dumps(doc, indent=1) + "\n")


def record_pass(results: dict[str, dict[str, Any]], at: datetime, universe: Iterable[str],
                *, store: Path = STORE, raw_dir: Path = RAW_DIR, state_path: Path = STATE
                ) -> dict[str, Any]:
    """Raw snapshots + mapped rows appended. One pass per (source, UTC hour), never twice."""
    names = list(universe)
    state = _read_json(state_path, {}) or {}
    last = state.setdefault("last_hour", {})
    hour = at.strftime("%Y-%m-%dT%H")
    rows: list[dict[str, Any]] = []
    unmapped: dict[str, list[str]] = {}
    per: dict[str, dict[str, Any]] = {}
    for source, res in results.items():
        body = res.get("body")
        sha = ""
        if body is not None:
            sha = _raw_snapshot(source, at, str(res.get("url") or ""), int(res.get("http") or 0),
                                str(body), raw_dir)
        rec = {"status": res.get("status"), "why": res.get("why", ""), "n_parsed": 0,
               "n_mapped": 0, "appended": 0}
        if res.get("status") == "OK":
            rec["n_parsed"] = len(res.get("obs") or [])
            if last.get(source) == hour:
                rec["why"] = f"already recorded hour {hour}; nothing appended (append-only)"
            else:
                src_rows = []
                for o in res.get("obs") or []:
                    sym = map_symbol(o["raw_symbol"], names)
                    if not sym:
                        unmapped.setdefault(source, []).append(o["raw_symbol"])
                        continue
                    src_rows.append({**o, "symbol": sym, "source": source, "cohort": "all",
                                     "captured_at": _iso(at), "available_time": _iso(at),
                                     "access_label": SOURCES[source]["access_label"],
                                     "payload_sha": sha})
                rec["n_mapped"] = len(src_rows)
                rows.extend(src_rows)
                last[source] = hour
        per[source] = rec
    n = append_rows(rows, store)
    for source in per:
        per[source]["appended"] = sum(1 for r in rows if r["source"] == source)
    state["updated"] = _iso(at)
    _write_atomic(state_path, json.dumps(state, indent=1) + "\n")
    return {"appended": n, "sources": per,
            "unmapped": {k: sorted(set(v))[:60] for k, v in unmapped.items()}}


# ------------------------------------------------------------------ derived view and features
def build_wide(store: Path = STORE, wide: Path = WIDE) -> Any:
    """The hourly consensus frame the families read, or None when the store is empty."""
    import pandas as pd
    if not store.exists():
        return None
    try:
        df = pd.read_csv(store, usecols=["captured_at", "symbol", "net_frac"])
    except (ValueError, OSError):
        return None
    if df.empty:
        return None
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    df["net_frac"] = pd.to_numeric(df["net_frac"], errors="coerce")
    df = df.dropna()
    if df.empty:
        return None
    df["hour"] = df["captured_at"].dt.floor("h")
    avail = df.groupby("hour")["captured_at"].max()
    w = df.pivot_table(index="hour", columns="symbol", values="net_frac", aggfunc="mean")
    w.columns = [f"{c}__net" for c in w.columns]
    w = w.sort_index()
    w.insert(0, "available_time", avail.reindex(w.index).map(lambda t: t.isoformat()))
    out = w.reset_index(drop=True)
    _write_atomic(wide, out.to_csv(index=False))
    return out


def features(wide: Any, now: datetime) -> dict[str, dict[str, Any]]:
    """Per symbol: net %, z vs its own trailing history, change 1h / 24h, contrarian extreme."""
    import numpy as np
    import pandas as pd
    out: dict[str, dict[str, Any]] = {}
    if wide is None or len(wide) == 0:
        return out
    t = pd.to_datetime(wide["available_time"], utc=True, errors="coerce")
    for col in [c for c in wide.columns if c.endswith("__net")]:
        s = pd.Series(pd.to_numeric(wide[col], errors="coerce").to_numpy(), index=t).dropna()
        if s.empty:
            continue
        sym = col[: -len("__net")]
        mu = s.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).mean()
        sd = s.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).std(ddof=0)
        z = (s - mu) / sd.replace(0.0, np.nan)
        last_t = s.index[-1]

        def _chg(hours: int, s: Any = s, last_t: Any = last_t) -> float | None:
            prior = s[s.index <= last_t - pd.Timedelta(hours=hours) + pd.Timedelta(minutes=30)]
            return None if prior.empty else round(float(s.iloc[-1] - prior.iloc[-1]), 6)

        zl = z.iloc[-1]
        zf = None if not np.isfinite(zl) else round(float(zl), 4)
        net = float(s.iloc[-1])
        extreme = bool((zf is not None and abs(zf) >= EXTREME_Z) or abs(net) >= EXTREME_NET)
        span_d = (s.index[-1] - s.index[0]).total_seconds() / 86400.0
        out[sym] = {
            "net_pct": round(100.0 * net, 3), "net_z": zf, "chg_1h": _chg(1),
            "chg_24h": _chg(24), "contrarian_extreme": extreme,
            "contrarian_side": (-1 if net > 0 else 1) if extreme else 0,
            "n_obs": len(s), "first": s.index[0].isoformat(), "last": last_t.isoformat(),
            "span_days": round(span_d, 2),
            "stale": bool((now - last_t.to_pydatetime()).total_seconds() > 3 * 3600),
        }
    return out


# ------------------------------------------------------------------ hypotheses, charged once
def hypothesis_id(symbol: str, family: str, params: dict[str, Any]) -> str:
    blob = json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def _emitted(path: Path = EMITTED) -> set[str]:
    ids: set[str] = set()
    with contextlib.suppress(OSError), path.open("r", encoding="utf-8") as fh:
        for line in fh:
            with contextlib.suppress(ValueError):
                ids.add(str(json.loads(line).get("id") or ""))
    ids.discard("")
    return ids


def specs_for(symbol: str) -> list[dict[str, Any]]:
    out = []
    for h in HYPOTHESES:
        params = {"source": WIDE_SOURCE, "signal": f"{symbol}__net", **h["params"]}
        out.append({"id": hypothesis_id(symbol, h["family"], params), "key": h["key"],
                    "symbol": symbol, "family": h["family"], "params": params,
                    "mechanism": h["mechanism"]})
    return out


def hypotheses(feats: dict[str, dict[str, Any]], now: datetime, *,
               emitted_path: Path = EMITTED, intel_dir: Path = INTEL,
               lane: Callable[[str], bool] = _hypothesis_lane) -> dict[str, Any]:
    """Donate every newly eligible hypothesis exactly once; name the rest with their ETA."""
    done = _emitted(emitted_path)
    new: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    already = 0
    set_aside: list[str] = []
    for sym, f in sorted(feats.items()):
        if not lane(sym):
            set_aside.append(sym)
            continue
        ready = f["n_obs"] >= MIN_HISTORY_OBS and f["span_days"] >= MIN_HISTORY_DAYS
        for sp in specs_for(sym):
            if sp["id"] in done:
                already += 1
            elif ready:
                new.append(sp)
            else:
                first = datetime.fromisoformat(f["first"])
                eta = max(first + timedelta(days=MIN_HISTORY_DAYS),
                          now + timedelta(hours=max(0, MIN_HISTORY_OBS - f["n_obs"])))
                pending.append({"id": sp["id"], "key": sp["key"], "symbol": sym,
                                "n_obs": f["n_obs"], "eligible_from": _iso(eta)})
    donated_file = None
    if new:
        rows = [{"source": SEAT, "kind": "hypothesis", "family": sp["family"],
                 "params": sp["params"], "symbols": [sp["symbol"]],
                 "title": f"{sp['symbol']} {sp['key']} (retail crowd, pre-registered)",
                 "text": sp["mechanism"], "mechanism": sp["mechanism"],
                 "url": "desks/mt5/data/lake/series/retail_crowd.csv",
                 "hypothesis_id": sp["id"], "found_at": _iso(now),
                 "available_time": _iso(now)} for sp in new]
        donated_file = _donate(rows, now, intel_dir)
        emitted_path.parent.mkdir(parents=True, exist_ok=True)
        with emitted_path.open("a", encoding="utf-8") as fh:
            for sp in new:
                fh.write(json.dumps({"id": sp["id"], "symbol": sp["symbol"], "key": sp["key"],
                                     "family": sp["family"], "params": sp["params"],
                                     "emitted_at": _iso(now)}) + "\n")
    return {"donated": len(new), "donated_file": donated_file, "already_emitted": already,
            "pending": len(pending), "pending_rows": pending[:200],
            "set_aside_not_hypothesis_lane": set_aside,
            "charge_rule": ("one trial per hypothesis id, donated once; emitted.jsonl is the "
                            "ledger and no pass re-donates an id in it")}


def _donate(rows: list[dict[str, Any]], now: datetime, intel_dir: Path) -> str:
    sc = str(DESK / "side_channels")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from discovery_io import write_discoveries
    p = intel_dir / f"discoveries_{now.strftime('%Y%m%d_%H%M%S')}.json"
    write_discoveries(p, rows)
    return str(p.relative_to(DESK)) if p.is_relative_to(DESK) else str(p)


# ------------------------------------------------------------------ the pass
def fetch_all(fetch: Fetcher = http_get, creds: dict[str, str] | None = None
              ) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    api = fetch_myfxbook_api(fetch, creds)
    out["myfxbook_api"] = api
    if api["status"] != "OK":
        out["myfxbook_html"] = fetch_page("myfxbook_html", fetch)
    for source in ("dukascopy", "fxblue", "ig"):
        out[source] = fetch_page(source, fetch)
    return out


def run(*, do_fetch: bool = True, fetch: Fetcher = http_get, now: datetime | None = None,
        out_path: Path = OUT) -> dict[str, Any]:
    t0 = time.time()
    at = now or _now()
    uni = _universe()
    doc: dict[str, Any] = {"generated_at": _iso(at), "writer": "research/retail_crowd.py",
                           "store": str(STORE.relative_to(DESK)),
                           "wide_view": str(WIDE.relative_to(DESK))}
    if do_fetch:
        results = fetch_all(fetch)
        doc["record"] = record_pass(results, at, uni.keys())
    else:
        doc["record"] = {"status": "NOT_FETCHED", "why": "--no-fetch"}
    write_sidecar()
    wide = build_wide()
    feats = features(wide, at)
    doc["features"] = feats
    doc["n_symbols"] = len(feats)
    doc["extremes"] = sorted(s for s, f in feats.items() if f["contrarian_extreme"])
    doc["hypotheses"] = hypotheses(feats, at)
    doc["sources"] = {k: {"access_label": v["access_label"], "terms_note": v["terms_note"]}
                      for k, v in SOURCES.items()}
    ok = [s for s, r in (doc["record"].get("sources") or {}).items() if r.get("status") == "OK"]
    doc["status"] = ("OK" if ok else ("UNMEASURED" if do_fetch else "REBUILT"))
    doc["sources_ok"] = ok
    doc["elapsed_s"] = round(time.time() - t0, 2)
    _write_atomic(out_path, json.dumps(doc, indent=1, default=str) + "\n")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--no-fetch", action="store_true", help="rebuild features from the store")
    a = ap.parse_args(argv)
    prio = below_normal()
    doc = run(do_fetch=not a.no_fetch)
    print(f"  priority: {prio}")
    rec = doc.get("record") or {}
    print(f"retail_crowd: status={doc['status']} appended={rec.get('appended', 0)} "
          f"symbols={doc['n_symbols']} extremes={len(doc['extremes'])} "
          f"donated={doc['hypotheses']['donated']} pending={doc['hypotheses']['pending']}")
    for s, r in (rec.get("sources") or {}).items():
        print(f"  {s:14s} {r.get('status')}: parsed={r.get('n_parsed')} "
              f"appended={r.get('appended')} {str(r.get('why') or '')[:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
