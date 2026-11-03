"""THE WORLD DATASET HUNTER -- discover, fetch, quality-check, register and expose thousands of
free public datasets, incrementally, every hour.

WHY THIS EXISTS (measured 2026-09-30). The desk researched on FOUR datasets: `data_registry.json`
held fifteen rows, ten of them only DISCOVERED, and the collectors that do reach the network each
own a hand-picked list (twenty-two FRED ids, three ECB crosses, one BIS bulk file). Institutions
do not pick a list; they run a frontier. This organ is that frontier for the public statistical
world, with one backbone and a handful of direct doors:

    DBnomics (api.db.nomics.world/v22)   ~80 providers behind one keyless JSON API -- IMF, OECD,
                                         BIS, ECB, Eurostat, World Bank, ILO, national statistics
                                         offices and central banks. ~30k datasets. THE BACKBONE.
    BIS bulk (data.bis.org/static/bulk)  flat CSV zips (EER, policy rates, credit, property ...)
    CFTC Socrata (publicreporting)       traders-in-financial-futures -- the EURO FX positioning
                                         the legacy schema never carried
    US Treasury fiscal data              average interest rates by security
    FRED fredgraph.csv                   the desk's known ids, keyless
    direct probes                        the ten registry rows that sat DISCOVERED

ONE PASS, THREE PHASES, ONE CURSOR. Discovery lists providers (daily) and pages their dataset
catalogues (500 a request) until every provider is listed. Fetching is BREADTH-FIRST: one page of
series per dataset per visit, highest MT5 relevance first and never-fetched before refreshed, so
thousands of datasets are touched in days rather than the first big one being paged to the end.
Every dataset carries its own series offset, so a truncated pass resumes where it stopped -- the
truncated-job defect (`hourly_cycle.LEG_BUDGET_SEC`) cannot happen here by construction.

POINT-IN-TIME OR NOTHING. Every observation row carries `period_end` (what it describes),
`available_time` (period_end + the cadence's publication lag, `libs.data.pit_stamp`) and
`first_seen_utc` (when THIS box first read that value). A revised value is a NEW row with a new
`first_seen_utc`, never an overwrite. The research door (`world_series_for`) keys each value on
`available_time` for the backfilled history and on `max(available_time, first_seen_utc)` for
every value the hunter watched arrive, and always serves the FIRST vintage it saw -- a value
revised later never leaks backwards.

MAPPED TO THE MT5 UNIVERSE, NEVER A LIST. Country -> currency and commodity -> instrument are
facts about the world (tables below); the instruments are read from the broker's own registry
(`data/universe/universe.json`) and filtered by `universe_policy.may_hypothesise`, so a share CFD
is never given a statistical conditioner (two-lanes rule) and nothing here names a
crypto-exchange venue. Crypto CFDs stay in the hypothesis lane exactly as the registry says.

WHERE IT GOES. `build_exposure` publishes, per hypothesis-lane symbol, the ranked series that
inform it. `research/world_macro_proposer.py` (its own hourly leg) reads that exposure and mints
`world_macro_state` cells -- a z-score band on ONE named series x direction x hold -- through the
shared proposer screen and donation contract. The family (`mt5desk/family_world_macro.py`,
registered in `ORTHOGONAL_FAMILIES`) reloads the series from the `series_key` on the recipe, so
the sealed gauntlet's `build_cell` and the forward clock rebuild the same signals with no input
resolver, and rotation can never orphan a cell. The banned `discovered` family is never fed.

    python desks/mt5/research/world_dataset_hunter.py --once --budget-s 900
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import shutil
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STORE = DESK / "data" / "world_datasets"
OBS = STORE / "obs"
CATALOG = STORE / "catalog.json"
EXPOSURE = STORE / "exposure.json"
KEYS = STORE / "keys.json"
HISTORY = STORE / "hunt_history.jsonl"
REGISTRY = DESK / "data" / "data_registry.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
REPORT = DESK / "reports" / "DATASET_HUNT.json"
#: The country packs' liveness, in the DEPENDENCY_LIVENESS shape (RED after >2 empty attempts).
PACK_LIVENESS = DESK / "reports" / "COUNTRY_PACK_LIVENESS.json"

DBNOMICS = "https://api.db.nomics.world/v22"
UNMEASURED = "UNMEASURED"
UA = "quant-desk-world-dataset-hunter/1.0 (research; keyless public statistics)"

DEFAULT_BUDGET_S = 900.0
#: Discovery may take this share of the pass; the rest is fetching. Discovery is finite (every
#: provider listed once, then refreshed weekly) so after the first days it uses a sliver of it.
DISCOVERY_SHARE = 0.35
DATASETS_PAGE = 500
SERIES_PAGE = 50
HTTP_TIMEOUT_S = 30.0
#: Polite spacing between requests to one API. DBnomics is a public service run by a small team.
MIN_REQUEST_GAP_S = 0.25
MAX_DIRECT_BYTES = 80 * 1024 * 1024
PROVIDERS_REFRESH_H = 24.0
DATASETS_RELIST_D = 7.0
DIRECT_REFRESH_H = 24.0
LEGACY_RETRY_H = 24.0
#: Free disk kept for everything else on the box: the larger of 3 GB and 3% of the volume.
#: Below it fetching STANDS DOWN (reported, never silent) while discovery continues.
MIN_FREE_BYTES = 3 * 1024 ** 3
MIN_FREE_SHARE = 0.03
#: Rows of the DISCOVERED-only population written into data_registry.json. The catalog holds
#: every dataset; the registry is a git-tracked state file and is kept to what a reader can load.
REGISTRY_DISCOVERED_CAP = 1500
#: Per-symbol research exposure: a stable core (highest relevance) plus a rotating window that
#: walks the rest of the symbol's mapped series one day at a time.
EXPOSE_CORE = 8
EXPOSE_ROTATING = 16
EXPOSE_CANDIDATES = 240
WORLD_KEY_PREFIX = "world_"

LIFECYCLE = ("DISCOVERED", "INGESTED", "QUALITY-PASSED", "RESEARCH-USEFUL", "OOS-INCREMENTAL",
             "FORWARD-INCREMENTAL", "CORE")

# ------------------------------------------------------------------------------ world facts ----
#: ISO2, ISO3, name -> currency. A FACT TABLE ABOUT THE WORLD, not a universe boundary: which of
#: these reach an instrument is decided by the broker registry at run time.
_EURO = ("AT AUT Austria", "BE BEL Belgium", "CY CYP Cyprus", "DE DEU Germany", "EE EST Estonia",
         "ES ESP Spain", "FI FIN Finland", "FR FRA France", "GR GRC Greece", "HR HRV Croatia",
         "IE IRL Ireland", "IT ITA Italy", "LT LTU Lithuania", "LU LUX Luxembourg",
         "LV LVA Latvia", "MT MLT Malta", "NL NLD Netherlands", "PT PRT Portugal",
         "SI SVN Slovenia", "SK SVK Slovakia", "EA EMU Euro area", "U2 EUZ Eurozone",
         "I8 EA19 Euro area 19", "EA20 EA20 Euro area 20", "XM XM Euro area")
_OTHERS = ("US USA United States:USD", "GB GBR United Kingdom:GBP", "JP JPN Japan:JPY",
           "CH CHE Switzerland:CHF", "AU AUS Australia:AUD", "NZ NZL New Zealand:NZD",
           "CA CAN Canada:CAD", "NO NOR Norway:NOK", "SE SWE Sweden:SEK", "DK DNK Denmark:DKK",
           "PL POL Poland:PLN", "HU HUN Hungary:HUF", "CZ CZE Czechia:CZK",
           "TR TUR Turkey:TRY", "ZA ZAF South Africa:ZAR", "MX MEX Mexico:MXN",
           "BR BRA Brazil:BRL", "CN CHN China:CNH", "HK HKG Hong Kong:HKD",
           "SG SGP Singapore:SGD", "IL ISR Israel:ILS", "IN IND India:INR",
           "ID IDN Indonesia:IDR", "KR KOR Korea:KRW", "TH THA Thailand:THB",
           "RU RUS Russia:RUB", "CL CHL Chile:CLP", "CO COL Colombia:COP")


def _country_table() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in _EURO:
        iso2, iso3, name = row.split(" ", 2)
        out[iso2] = {"iso3": iso3, "name": name, "ccy": "EUR"}
    for row in _OTHERS:
        head, ccy = row.rsplit(":", 1)
        iso2, iso3, name = head.split(" ", 2)
        out[iso2] = {"iso3": iso3, "name": name, "ccy": ccy}
    return out


COUNTRIES = _country_table()
_ISO3 = {v["iso3"]: k for k, v in COUNTRIES.items()}
_NAME_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(v["name"]) for v in COUNTRIES.values()),
                                               key=len, reverse=True)) + r")\b", re.I)
_NAME_TO_ISO2 = {v["name"].lower(): k for k, v in COUNTRIES.items()}
_CCY_NAMES = {"us dollar": "USD", "euro": "EUR", "japanese yen": "JPY", "pound sterling": "GBP",
              "swiss franc": "CHF", "australian dollar": "AUD", "canadian dollar": "CAD",
              "new zealand dollar": "NZD", "renminbi": "CNH", "yuan": "CNH"}
_CCY_ALIASES = {"CNY": "CNH"}

#: Commodity words -> instrument-name stems. Matched against the broker's symbols, so a stem only
#: reaches an instrument the registry actually carries.
COMMODITY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"\bgold\b", ("XAU",)), (r"\bsilver\b", ("XAG",)), (r"\bplatinum\b", ("XPT",)),
    (r"\bpalladium\b", ("XPD",)), (r"\bcopper\b", ("XCU",)), (r"\balumin(?:i)?um\b", ("XAL",)),
    (r"\bnickel\b", ("XNI",)), (r"\bzinc\b", ("XZN",)),
    (r"\blead\b.{0,20}\b(?:metal|lme)\b", ("XPB",)),
    (r"\bbrent\b", ("XBR",)), (r"\b(?:crude|petroleum|wti)\b|\boil price", ("XTI", "XBR")),
    (r"\bnatural gas\b", ("XNG",)), (r"\bcoffee\b", ("COF",)), (r"\bcocoa\b", ("COCOA",)),
    (r"\bsugar\b", ("SUGAR",)), (r"\b(?:corn|maize)\b", ("CORN",)), (r"\bwheat\b", ("WHEAT",)),
    (r"\b(?:soybeans?|soya)\b", ("SOYBEAN",)), (r"\bcotton\b", ("COTTON",)),
    (r"\borange juice\b", ("OJ",)), (r"\bbitcoin\b", ("BTC",)), (r"\bether(?:eum)?\b", ("ETH",)),
)
_COMMODITY_RE = [(re.compile(p, re.I), stems) for p, stems in COMMODITY_TERMS]

#: Topic weights for ranking what to fetch first. Ranking only -- nothing here refuses a dataset.
TOPIC_WEIGHTS: tuple[tuple[str, float], ...] = (
    (r"exchange rate|\bfx\b|effective exchange", 3.0),
    (r"interest rate|policy rate|\brates?\b", 3.0),
    (r"\byields?\b|\bbonds?\b|treasur|government securit", 3.0),
    (r"inflation|consumer price|\bcpi\b|\bhicp\b|producer price|\bppi\b", 2.5),
    (r"commodit|\bgold\b|\boil\b|energy|metal|agricultur", 3.0),
    (r"money|monetary|\bm[123]\b|reserve|liquidity|central bank", 2.0),
    (r"balance of payments|current account|\btrade\b|export|import", 2.0),
    (r"industrial production|\bpmi\b|manufactur|business survey|confidence|sentiment", 2.0),
    (r"unemployment|employment|labou?r|wage|payroll", 1.5),
    (r"\bgdp\b|national accounts|growth", 1.5), (r"credit|lending|loan|debt|deficit", 1.5),
    (r"stock|equit|share price|index|volatil|futures|swap|derivativ", 2.0),
    (r"housing|house price|property|construction", 1.0), (r"retail|consumption|sales", 1.0),
    (r"shipping|freight|transport", 1.5), (r"daily|weekly", 1.0),
)
_TOPIC_RE = [(re.compile(p, re.I), w) for p, w in TOPIC_WEIGHTS]
#: Providers whose output is closest to the price-forming state variables.
PROVIDER_WEIGHT: dict[str, float] = {
    "BIS": 3.0, "ECB": 3.0, "IMF": 2.5, "OECD": 2.5, "FED": 3.0, "BOE": 3.0, "BOJ": 3.0,
    "SNB": 3.0, "RBA": 3.0, "BOC": 3.0, "NB": 2.5, "RIKSBANK": 3.0, "NORGES": 3.0,
    "BUBA": 2.5, "BDF": 2.0, "Eurostat": 2.0, "WB": 1.5, "BLS": 2.5, "BEA": 2.0,
    "CFTC": 3.0, "FRED": 3.0, "TREASURY": 2.5, "BIS_BULK": 3.0, "DIRECT": 2.0,
    "EIA": 3.0, "NOAA_CPC": 2.0, "USDA_NASS": 3.0, "USDA_FAS": 3.0, "USDA_WASDE": 3.0,
    "NYFED": 3.0,
}

#: Frequency -> (min finite observations, max staleness in days, exposure bonus).
FREQ_RULES: dict[str, tuple[int, int, float]] = {
    "daily": (250, 45, 2.0), "business": (250, 45, 2.0), "weekly": (104, 75, 1.5),
    "monthly": (36, 200, 1.0), "bi-monthly": (24, 250, 0.8), "quarterly": (20, 400, 0.5),
    "bi-annual": (12, 600, 0.2), "annual": (15, 900, 0.0),
}
#: Publication lag by cadence where pit_stamp has no default of its own.
EXTRA_LAG_DAYS = {"annual": 90, "bi-annual": 60, "bi-monthly": 30, "business": 1}


# ------------------------------------------------------------------------------- utilities ----
def _now() -> datetime:
    return datetime.now(UTC)


def _iso(when: datetime | None) -> str | None:
    return when.isoformat(timespec="seconds") if when else None


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        got = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _replace_windows_safe(tmp: Path, path: Path) -> None:
    """`os.replace` onto a READ-ONLY destination raises WinError 5 on Windows where POSIX allows
    it (the fix that passed on the VPS and would have broken the trading box). Clear the
    read-only bit and retry once; never leave the tmp file behind."""
    try:
        os.replace(tmp, path)
        return
    except OSError:
        pass
    try:
        if path.exists():
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def write_json(path: Path, payload: Any, *, indent: int | None = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=indent, default=str, ensure_ascii=False),
                   encoding="utf-8")
    _replace_windows_safe(tmp, path)


def _write_parquet(df: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    df.to_parquet(tmp, index=False)
    _replace_windows_safe(tmp, path)


def _rel(path: Path) -> str:
    """A desk-relative, forward-slash path when it lies under the desk; else the absolute one."""
    try:
        return str(path.relative_to(DESK)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")[:120] or "x"


def series_key(provider: str, dataset: str, code: str) -> str:
    """A stable identifier-safe key for one series. Hash, because DBnomics codes carry dots,
    slashes and spaces that would break `x_<a>__<b>` interaction names downstream."""
    h = hashlib.sha1(f"{provider}/{dataset}/{code}".encode()).hexdigest()[:12]
    return f"w{h}"


def dataset_path(provider: str, dataset: str) -> Path:
    return OBS / _slug(provider) / f"{_slug(dataset)}.parquet"


def meta_path(provider: str, dataset: str) -> Path:
    return OBS / _slug(provider) / f"{_slug(dataset)}.meta.json"


# ------------------------------------------------------------------------------------ HTTP ----
def url_template(text: object, key: str) -> str:
    """`text` (a URL, an error detail) with the credential `key` -- raw or percent-quoted --
    written back as `{key}`, so a stored or logged URL is the door's TEMPLATE, never the keyed
    request (BPS carries its key as a PATH segment, `/key/<key>/`). Anything else credential-shaped
    is blanked by `polite_fetch.redact_text`."""
    from libs.data import polite_fetch as _pf
    out = str(text)
    if key:
        for form in {urllib.parse.quote(key, safe=""), key}:
            out = out.replace(form, "{key}")
    return _pf.redact_text(out)


class FetchError(Exception):
    """A classified fetch failure. `reason` is the bucket the report counts."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _classify(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        code = int(exc.code)
        if code == 429:
            return "rate_limited_429"
        if code in (401, 403):
            return f"blocked_{code}"
        if code == 404:
            return "not_found_404"
        if code >= 500:
            return "server_5xx"
        return f"http_{code}"
    text = f"{type(exc).__name__}: {exc}".lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "tunnel" in text or "403" in text or "proxy" in text:
        return "blocked_proxy"
    if "certificate" in text or "ssl" in text:
        return "tls"
    return "connection"


#: (url, timeout) -> body. A country-pack door that needs a request header (the EVDS key) or a
#: POST body (SCB) passes them as `headers=` / `data=` keywords; every other door calls with two.
Fetcher = Callable[..., bytes]


def urllib_fetch(url: str, timeout: float, headers: dict[str, str] | None = None,
                 data: bytes | None = None) -> bytes:
    """Default transport: polite_fetch's urlopen seam, the named UA (plus a country pack's
    credential header or POST body when one is set). LIVE-INPUT CHECK
    (libs/data/terms_fence.py): a URL on an IDEAS_ONLY or held source is refused before any
    request, and a 30x into a held source or a login wall is never followed. ROBOTS DECIDES
    (LAWS 5e amended 2026-10-14): the site's holds and the origin's robots.txt are checked on
    every hop before a request; a 401/403/429 holds the site and is never retried."""
    from libs.data import polite_fetch as _pf
    from libs.data import terms_fence as _tf
    if _tf.input_source(url):
        raise FetchError("terms_fenced", url)
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA,
                                                          "Accept": ("application/json, "
                                                                     "text/csv, */*"),
                                                          **(headers or {})})
    try:
        with _pf.polite_urlopen(req, timeout=timeout, live_input=True,
                                max_bytes=MAX_DIRECT_BYTES + 1, retries=0,
                                leg="world_dataset_hunter") as resp:
            raw = resp.read(MAX_DIRECT_BYTES + 1)
        if len(raw) > MAX_DIRECT_BYTES:
            raise FetchError("too_large", url)
        return raw
    except urllib.error.HTTPError as exc:
        raise FetchError(_classify(exc), str(exc)[:160]) from exc
    except FetchError:
        raise
    except _pf.PoliteRefused as exc:
        if exc.verdict:
            raise FetchError("terms_fenced" if exc.verdict == "terms_fenced"
                             else "robots_or_held", f"{exc.verdict}: {url}") from exc
        if "body longer" in exc.error:
            raise FetchError("too_large", url) from exc
        raise FetchError(_classify(exc), f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    except _tf.TermsFenced as exc:
        raise FetchError("terms_fenced", f"redirected into {exc.platform}: {url}") from exc
    except Exception as exc:
        raise FetchError(_classify(exc), f"{type(exc).__name__}: {str(exc)[:160]}") from exc


class Client:
    """Budgeted, counted, polite. Every request and every failure lands in `stats`."""

    def __init__(self, fetch: Fetcher | None, deadline: float) -> None:
        self.fetch = fetch or urllib_fetch
        self.deadline = deadline
        self.requests = 0
        self.ok = 0
        self.bytes = 0
        self.failures: Counter[str] = Counter()
        self._last = 0.0

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def get(self, url: str, headers: dict[str, str] | None = None,
            data: bytes | None = None) -> bytes:
        left = self.remaining()
        if left < 2.0:
            raise FetchError("budget_exhausted", url)
        gap = MIN_REQUEST_GAP_S - (time.monotonic() - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()
        self.requests += 1
        try:
            timeout = min(HTTP_TIMEOUT_S, max(2.0, left - 1.0))
            # a credential header or a POST body travels only when one is set, as a keyword, so
            # every two-argument fetcher (and a three-argument one taking headers) keeps working
            kw: dict[str, Any] = {}
            if headers:
                kw["headers"] = headers
            if data is not None:
                kw["data"] = data
            raw = self.fetch(url, timeout, **kw) if kw else self.fetch(url, timeout)
        except FetchError as exc:
            self.failures[exc.reason] += 1
            raise
        except Exception as exc:
            reason = _classify(exc)
            self.failures[reason] += 1
            raise FetchError(reason, str(exc)[:160]) from exc
        self.ok += 1
        self.bytes += len(raw or b"")
        return raw

    def get_json(self, url: str) -> Any:
        raw = self.get(url)
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except ValueError as exc:
            self.failures["bad_json"] += 1
            raise FetchError("bad_json", url) from exc


# ------------------------------------------------------------------------- MT5 mapping ----
@lru_cache(maxsize=4)
def _universe_at(path: str, mtime_ns: int) -> tuple[tuple[str, str, str], ...]:
    """(symbol, asset_class, currency_profit) for every HYPOTHESIS-lane instrument."""
    doc = _read_json(Path(path), {})
    if not isinstance(doc, dict):
        return ()
    try:
        from research import universe_policy as up
    except ImportError:                                                       # pragma: no cover
        import universe_policy as up  # type: ignore[no-redef]
    out = []
    for sym, row in doc.items():
        if not isinstance(row, dict):
            continue
        try:
            ok = up.may_hypothesise(sym)
        except Exception:
            ok = False
        if ok:
            out.append((str(sym), str(row.get("asset_class") or ""),
                        str(row.get("currency_profit") or "")))
    return tuple(sorted(out))


def hypothesis_universe() -> tuple[tuple[str, str, str], ...]:
    try:
        mtime = UNIVERSE.stat().st_mtime_ns
    except OSError:
        return ()
    return _universe_at(str(UNIVERSE), mtime)


def _fx_legs(sym: str, klass: str) -> tuple[str, str] | None:
    if "forex" not in klass.lower() or len(sym) != 6 or not sym.isalpha():
        return None
    return sym[:3].upper(), sym[3:].upper()


def instruments_for(currencies: Iterable[str], stems: Iterable[str],
                    universe: tuple[tuple[str, str, str], ...] | None = None,
                    cap: int = 40) -> list[str]:
    """Hypothesis-lane instruments a series about these currencies / commodities informs.

    A currency reaches every FX pair carrying it and every index/bond quoted in it; a commodity
    stem reaches the instruments whose symbol carries it. Nothing is invented: an instrument the
    registry does not hold is never returned."""
    uni = hypothesis_universe() if universe is None else universe
    ccys = {_CCY_ALIASES.get(c.upper(), c.upper()) for c in currencies if c}
    stems_u = tuple(s.upper() for s in stems if s)
    out: list[str] = []
    for sym, klass, profit in uni:
        su = sym.upper()
        legs = _fx_legs(su, klass)
        hit = False
        quoted_in = (not legs and klass.lower() in ("indices", "index", "bonds", "bond")
                     and profit.upper() in ccys)
        if (legs and (legs[0] in ccys or legs[1] in ccys)) or quoted_in:
            hit = True
        if not hit and stems_u:
            hit = any(su.startswith(s) or (len(s) >= 4 and s in su) for s in stems_u)
        if hit:
            out.append(sym)
    return sorted(out)[:cap]


_GEO_DIM = re.compile(r"area|geo|country|location|reporter|counterpart|region|ref_area|economy",
                      re.I)
_CCY_DIM = re.compile(r"curr|unit", re.I)


def map_series(text: str, dims: dict[str, Any] | None) -> dict[str, list[str]]:
    """Countries, currencies and commodity stems a series is about, from its name and dims."""
    countries: set[str] = set()
    currencies: set[str] = set()
    for key, val in (dims or {}).items():
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            s = str(v).strip().upper()
            if _GEO_DIM.search(str(key)):
                if s in COUNTRIES:
                    countries.add(s)
                elif s in _ISO3:
                    countries.add(_ISO3[s])
            if _CCY_DIM.search(str(key)) and len(s) == 3 and s.isalpha():
                currencies.add(_CCY_ALIASES.get(s, s))
    for m in _NAME_RE.finditer(text or ""):
        iso2 = _NAME_TO_ISO2.get(m.group(1).lower())
        if iso2:
            countries.add(iso2)
    low = (text or "").lower()
    for name, ccy in _CCY_NAMES.items():
        if name in low:
            currencies.add(ccy)
    currencies |= {COUNTRIES[c]["ccy"] for c in countries}
    stems: set[str] = set()
    for rx, st in _COMMODITY_RE:
        if rx.search(text or ""):
            stems.update(st)
    return {"countries": sorted(countries), "currencies": sorted(currencies),
            "stems": sorted(stems)}


def topic_score(text: str) -> float:
    return min(8.0, sum(w for rx, w in _TOPIC_RE if rx.search(text or "")))


def dataset_score(provider: str, name: str) -> float:
    pw = PROVIDER_WEIGHT.get(provider, 1.0)
    low = (name or "").lower()
    if pw == 1.0 and ("central bank" in low or "monetary" in low):
        pw = 1.5
    commodity = 3.0 if any(rx.search(name or "") for rx, _ in _COMMODITY_RE) else 0.0
    return round(pw * (1.0 + topic_score(name)) + commodity, 3)


# ----------------------------------------------------------------------- periods and PIT ----
_FREQ_ALIASES = {"a": "annual", "annually": "annual", "yearly": "annual", "q": "quarterly",
                 "m": "monthly", "w": "weekly", "d": "daily", "b": "business",
                 "s": "bi-annual", "semi-annual": "bi-annual", "semiannual": "bi-annual",
                 "h": "bi-annual", "bimonthly": "bi-monthly"}


def norm_freq(freq: Any) -> str:
    f = str(freq or "").strip().lower()
    return _FREQ_ALIASES.get(f, f)


def _month_end(y: int, m: int) -> date:
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def period_end(period: str, freq: str = "") -> tuple[date | None, str]:
    """(last day the period describes, inferred frequency). None when unparseable."""
    p = str(period or "").strip()
    f = norm_freq(freq)
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", p):
            d = date(int(m[1]), int(m[2]), int(m[3]))
            if f == "weekly":
                return d + timedelta(days=6), f
            return d, f or "daily"
        if m := re.fullmatch(r"(\d{4})-?Q([1-4])", p, re.I):
            return _month_end(int(m[1]), int(m[2]) * 3), "quarterly"
        if m := re.fullmatch(r"(\d{4})-(\d{2})", p):
            return _month_end(int(m[1]), int(m[2])), f or "monthly"
        if m := re.fullmatch(r"(\d{4})-?W(\d{2})", p, re.I):
            return date.fromisocalendar(int(m[1]), int(m[2]), 7), "weekly"
        if m := re.fullmatch(r"(\d{4})-?[SH]([12])", p, re.I):
            return _month_end(int(m[1]), int(m[2]) * 6), "bi-annual"
        if m := re.fullmatch(r"(\d{4})-?B([1-6])", p, re.I):
            return _month_end(int(m[1]), int(m[2]) * 2), "bi-monthly"
        if m := re.fullmatch(r"(\d{4})", p):
            return date(int(m[1]), 12, 31), "annual"
        if m := re.fullmatch(r"(\d{4})(\d{2})(\d{2})(?:T.*)?", p):
            return date(int(m[1]), int(m[2]), int(m[3])), f or "daily"
        if m := re.match(r"(\d{4})-(\d{2})-(\d{2})[T ]", p):
            return date(int(m[1]), int(m[2]), int(m[3])), f or "daily"
    except ValueError:
        return None, f
    return None, f


def lag_days(freq: str, declared: int | None = None) -> int:
    if declared is not None:
        return max(0, int(declared))
    f = norm_freq(freq)
    if f in EXTRA_LAG_DAYS:
        return EXTRA_LAG_DAYS[f]
    try:
        from libs.data.pit_stamp import lag_for
        return int(lag_for({"cadence": f})[0])
    except Exception:
        return 20


# -------------------------------------------------------------------------- observations ----
def observations_from_dbnomics(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """DBnomics `series.docs[]` -> [{code, name, freq, dims, points: [(period, value)]}]."""
    out = []
    for s in ((doc.get("series") or {}).get("docs") or []):
        if not isinstance(s, dict):
            continue
        code = str(s.get("series_code") or s.get("code") or "")
        periods = s.get("period") or []
        values = s.get("value") or []
        pts = []
        for per, val in zip(periods, values, strict=False):
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue                          # "NA" is an absent observation, not a failure
            if f == f and abs(f) != float("inf"):
                pts.append((str(per), f))
        out.append({"code": code, "name": str(s.get("series_name") or code),
                    "freq": norm_freq(s.get("@frequency") or s.get("frequency")),
                    "dims": s.get("dimensions") if isinstance(s.get("dimensions"), dict) else {},
                    "points": pts})
    return out


def quality(points: list[tuple[str, float]], freq: str, *, now: datetime,
            parsed: list[date | None] | None = None) -> tuple[bool, str, str]:
    """(passed, reason, inferred frequency). Every refusal names the measurement that failed."""
    if not points:
        return False, "no_observations", freq
    ends = parsed if parsed is not None else [period_end(p, freq)[0] for p, _ in points]
    if not freq:
        freq = next((period_end(p)[1] for p, _ in points if period_end(p)[1]), "")
    ok_ends = [e for e in ends if e is not None]
    if len(ok_ends) < 0.95 * len(points):
        return False, "unparseable_periods", freq
    min_obs, max_stale, _ = FREQ_RULES.get(freq, (30, 400, 0.0))
    if len(points) < min_obs:
        return False, "too_short", freq
    if len({round(v, 12) for _, v in points}) < 3:
        return False, "constant", freq
    if (now.date() - max(ok_ends)).days > max_stale:
        return False, "stale_discontinued", freq
    return True, "ok", freq


def merge_observations(existing: Any, series: list[dict[str, Any]], *, now: datetime,
                       declared_lag: int | None = None) -> tuple[Any, int]:
    """Append new and REVISED observations; never overwrite. Returns (frame, rows appended)."""
    import pandas as pd

    rows = []
    for s in series:
        freq = s.get("freq") or ""
        per_lag = s.get("lag_by_period") or {}
        # `released` (a publisher's release instant) and `available` (a door that knows each
        # value's actual release, e.g. the MoF intervention file released a quarter at a time)
        # are the same fact: period -> ISO UTC instant, never before the period ends.
        released = {**(s.get("available") or {}), **(s.get("release_at") or {}),
                    **(s.get("released") or {})}
        for per, val in s["points"]:
            end, f = period_end(per, freq)
            if end is None:
                continue
            t_end = pd.Timestamp(end, tz="UTC")
            rel = released.get(per)
            if rel:
                # THE PUBLISHER'S OWN RELEASE INSTANT (crop progress Monday 16:00 ET, WASDE
                # 12:00 ET, export sales Thursday 08:30 ET ...), never before the period ends.
                ts = pd.Timestamp(rel)
                ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
                avail = max(t_end, ts)
            else:
                # A PER-PERIOD release lag where the source gave one, else the cadence lag.
                lag = (max(0, int(per_lag[per])) if per in per_lag
                       else lag_days(f or freq, declared_lag))
                avail = t_end + pd.Timedelta(days=lag)
            rows.append((s["code"], per, t_end, float(val), avail))
    if not rows:
        return existing, 0
    new = pd.DataFrame(rows, columns=["series_code", "period", "period_end", "value",
                                      "available_time"])
    new["first_seen_utc"] = pd.Timestamp(now)
    new = new.drop_duplicates(["series_code", "period"], keep="last")
    if existing is None or len(existing) == 0:
        new["vintage"] = 1
        return new.reset_index(drop=True), len(new)
    last = (existing.sort_values("first_seen_utc")
            .drop_duplicates(["series_code", "period"], keep="last")
            [["series_code", "period", "value", "vintage"]])
    j = new.merge(last, on=["series_code", "period"], how="left", suffixes=("", "_old"))
    old = j["value_old"]
    changed = old.isna() | ((j["value"] - old).abs() > 1e-9 * (1.0 + old.abs()))
    add = j.loc[changed].copy()
    add["vintage"] = add["vintage"].fillna(0).astype(int) + 1
    add = add[["series_code", "period", "period_end", "value", "available_time",
               "first_seen_utc", "vintage"]]
    if add.empty:
        return existing, 0
    frame = pd.concat([existing, add], ignore_index=True)
    return frame, len(add)


def pit_series(frame: Any, code: str) -> Any:
    """One series, keyed on the instant the desk could have KNOWN each value, first vintage only.

    Backfilled history (first seen on the series' first fetch) is keyed on `available_time`; a
    value the hunter watched arrive later is keyed on max(available_time, first_seen_utc)."""
    import pandas as pd

    rows = frame[frame["series_code"] == code]
    if rows.empty:
        return pd.Series(dtype="float64")
    rows = rows.sort_values("first_seen_utc").drop_duplicates("period", keep="first")
    first_fetch = rows["first_seen_utc"].min()
    watched = rows["first_seen_utc"] > first_fetch + pd.Timedelta(hours=36)
    known = rows["available_time"].where(~watched,
                                         rows[["available_time", "first_seen_utc"]].max(axis=1))
    s = pd.Series(rows["value"].to_numpy(dtype="float64"), index=pd.DatetimeIndex(known))
    s = s.sort_index()
    return s[~s.index.duplicated(keep="last")]


# ------------------------------------------------------------------------ direct sources ----
def frame_from_payload(raw: bytes, mode: str, spec: dict[str, Any]) -> Any:
    """Parse one direct payload into a LONG frame [series_code, period, value, dims...]."""
    import pandas as pd

    if raw[:1] in (b"<",) or raw[:15].lower().startswith(b"<!doctype"):
        raise FetchError("served_html", spec.get("url", ""))
    if mode == "bis_flat_zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
            if name is None:
                raise FetchError("unparseable", "zip without csv")
            df = pd.read_csv(zf.open(name), low_memory=False)
        if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
            raise FetchError("unparseable", "BIS flat without TIME_PERIOD/OBS_VALUE")
        keycol = "KEY" if "KEY" in df.columns else None
        dims = [c for c in df.columns if c.isupper() and c not in ("TIME_PERIOD", "OBS_VALUE",
                                                                   "KEY", "OBS_STATUS",
                                                                   "OBS_CONF", "OBS_PRE_BREAK")
                and ":" not in c][:8]
        code = df[keycol].astype(str) if keycol else df[dims].astype(str).agg(".".join, axis=1)
        out = pd.DataFrame({"series_code": code, "period": df["TIME_PERIOD"].astype(str),
                            "value": pd.to_numeric(df["OBS_VALUE"], errors="coerce")})
        for d in dims:
            out[d] = df[d].astype(str).str.split(":").str[0]
        return out.dropna(subset=["value"])
    if mode == "gdelt_timeline":
        doc = json.loads(raw.decode("utf-8", "replace"))
        rows = []
        for tl in doc.get("timeline") or []:
            for pt in tl.get("data") or []:
                rows.append({"series_code": _slug(tl.get("series") or "volume"),
                             "period": str(pt.get("date") or "")[:8], "value": pt.get("value")})
        df = pd.DataFrame(rows)
        if df.empty:
            raise FetchError("empty", "gdelt timeline")
        df["period"] = df["period"].str.replace(r"^(\d{4})(\d{2})(\d{2})$", r"\1-\2-\3",
                                                regex=True)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"])
    if mode == "treasury_auctions":
        return _treasury_auction_frame(raw)
    if mode == "cpc_ascii":
        return _cpc_ascii_frame(raw, str(spec.get("series_code") or "index"))
    if mode == "eia_v2":
        return _eia_v2_frame(raw, str(spec.get("series_code") or "value"))
    if mode == "mof_weekly":
        return _mof_weekly_frame(raw)
    if mode == "tic_slt":
        return _tic_slt_frame(raw, str(spec.get("series_prefix") or "tic"))
    if mode == "ecb_sdmx_csv":
        return _ecb_sdmx_csv_frame(raw)
    if mode == "z1_ddp_zip":
        return _z1_ddp_frame(raw)
    if mode == "nass_quickstats":
        return _nass_frame(raw, str(spec.get("series_code") or "nass"))
    if mode == "fas_esr":
        return _fas_esr_frame(raw, str(spec.get("series_code") or "esr"),
                              spec.get("market_year"))
    if mode == "wasde_csv":
        return _wasde_frame(raw, str(spec.get("series_code") or "wasde"))
    if mode == "nowcast_vintage":
        return _nowcast_frame(raw, str(spec.get("series_code") or "nowcast"))
    if mode == "json_records":
        doc = json.loads(raw.decode("utf-8", "replace"))
        recs = doc.get(spec["data_key"]) if spec.get("data_key") else doc
        df = pd.DataFrame(recs if isinstance(recs, list) else [])
    else:                                                     # csv (wide)
        text = raw.decode("utf-8-sig", "replace")
        lines = text.splitlines()
        skip = next((i for i, ln in enumerate(lines[:40])
                     if re.match(r"\s*\"?(date|time|period)", ln, re.I)), 0)
        df = pd.read_csv(io.StringIO("\n".join(lines[skip:])), low_memory=False)
    if df.empty:
        raise FetchError("empty", spec.get("url", ""))
    dcol = spec.get("date_col")
    if not dcol or dcol not in df.columns:
        from libs.data.pit_stamp import find_period_column, period_column_by_value
        dcol = find_period_column(df.columns) or period_column_by_value(df)[0]
    if not dcol:
        raise FetchError("no_date_column", spec.get("url", ""))
    dates = pd.to_datetime(df[dcol].astype(str).str.strip(), errors="coerce", utc=True,
                           format="mixed")
    if dates.notna().mean() < 0.8:
        raise FetchError("no_date_column", f"{dcol} parses {dates.notna().mean():.0%}")
    period = dates.dt.strftime("%Y-%m-%d")
    code_col, value_col = spec.get("code_col"), spec.get("value_col")
    if code_col and value_col and code_col in df.columns and value_col in df.columns:
        out = pd.DataFrame({"series_code": df[code_col].astype(str), "period": period,
                            "value": pd.to_numeric(df[value_col], errors="coerce")})
        return out.dropna(subset=["value", "period"])
    frames = []
    for col in df.columns:
        if col == dcol:
            continue
        vals = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(),
                             errors="coerce")
        if vals.notna().mean() < 0.5:
            continue
        frames.append(pd.DataFrame({"series_code": _slug(col), "period": period,
                                    "value": vals}))
        if len(frames) >= int(spec.get("max_columns", 40)):
            break
    if not frames:
        raise FetchError("no_numeric_columns", spec.get("url", ""))
    return pd.concat(frames, ignore_index=True).dropna(subset=["value", "period"])


# ------------------------------------------------------- data-class gap doors (2026-10-29) ----
#: THREE DOORS FROM THE TIER-1 DATA-CLASS GAP LIST (research/data_class_gap.py, item 14 of the
#: hourly pass). Each lands its series in this organ's store, so `build_exposure` maps them to the
#: hypothesis-lane symbols and `world_macro_proposer` mints `world_macro_state` cells from them --
#: the form the desk's cells already consume, no second lane. Each host's terms are a row of the
#: one register (libs/data/terms_fence.SOURCE_POLICY: `us_treasury_fiscaldata`, `noaa_cpc`,
#: `eia_api`) with the publisher's own clause quoted.
_AUCTION_TERM = re.compile(r"^\s*(\d+)-(Week|Year)\b", re.I)


def _num_or_none(v: Any) -> float | None:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def _treasury_auction_frame(raw: bytes) -> Any:
    """FiscalData `auctions_query` -> one row per (security kind, original term, auction date) and
    measure: bid-to-cover, the indirect / direct / primary-dealer share of competitive awards, the
    stop-out yield (rate for bills) and the offering size. An announced auction whose results are
    still "null" yields nothing, so a result is only ever read from the record that carries it.
    Cash-management bills are skipped (irregular, off the calendar)."""
    import pandas as pd

    doc = json.loads(raw.decode("utf-8", "replace"))
    rows: list[dict[str, Any]] = []
    for r in (doc.get("data") or []) if isinstance(doc, dict) else []:
        if not isinstance(r, dict) or str(r.get("cash_management_bill_cmb")) == "Yes":
            continue
        m = _AUCTION_TERM.match(str(r.get("original_security_term") or r.get("security_term")
                                    or ""))
        day = str(r.get("auction_date") or "")[:10]
        if not m or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            continue
        bucket = f"{int(m[1])}{m[2][0].lower()}"
        kind = ("tips" if str(r.get("inflation_index_security")) == "Yes"
                else "frn" if str(r.get("floating_rate")) == "Yes"
                else str(r.get("security_type") or "x").strip().lower() or "x")
        comp = _num_or_none(r.get("comp_accepted"))
        vals: dict[str, float | None] = {
            "bid_to_cover": _num_or_none(r.get("bid_to_cover_ratio")),
            "stop_yield": (_num_or_none(r.get("high_yield"))
                           if _num_or_none(r.get("high_yield")) is not None
                           else _num_or_none(r.get("high_investment_rate"))),
            "offering_bn": (None if _num_or_none(r.get("offering_amt")) is None
                            else float(_num_or_none(r.get("offering_amt")) or 0.0) / 1e9),
        }
        for who in ("indirect_bidder", "direct_bidder", "primary_dealer"):
            took = _num_or_none(r.get(f"{who}_accepted"))
            vals[f"{who.split('_')[0]}_share"] = (took / comp if took is not None and comp
                                                  else None)
        if vals["bid_to_cover"] is None:
            vals["offering_bn"] = None            # announced, not yet auctioned: no result
        for measure, v in vals.items():
            if v is not None:
                rows.append({"series_code": f"{kind}_{bucket}_{measure}", "period": day,
                             "value": v})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("empty", "treasury auctions")
    return df


#: CPC three-month season -> the LAST calendar month it covers (offset in years for NDJ). A season
#: is only known once its last month is over, so the period is that month, never the centre.
_CPC_SEASONS = {s: (i + 2, 0) for i, s in enumerate(
    ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND"))}
_CPC_SEASONS["NDJ"] = (1, 1)


def _cpc_ascii_frame(raw: bytes, code: str) -> Any:
    """NOAA CPC whitespace tables: the ONI table (`SEAS YR TOTAL ANOM`, one row per running
    season) or a monthly index (`YYYY M value`: NAO, AO, PNA). Missing values (<= -99) are
    absent observations, never zeros."""
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        tok = line.split()
        if len(tok) >= 4 and tok[0].upper() in _CPC_SEASONS and tok[1].isdigit():
            month, carry = _CPC_SEASONS[tok[0].upper()]
            period = f"{int(tok[1]) + carry:04d}-{month:02d}"
            for name, v in (("total", tok[2]), ("anom", tok[3])):
                f = _num_or_none(v)
                if f is not None and f > -99.0:
                    rows.append({"series_code": f"{code}_{name}", "period": period, "value": f})
        elif len(tok) == 3 and tok[0].isdigit() and tok[1].isdigit() and 1 <= int(tok[1]) <= 12:
            f = _num_or_none(tok[2])
            if f is not None and f > -99.0:
                rows.append({"series_code": code,
                             "period": f"{int(tok[0]):04d}-{int(tok[1]):02d}", "value": f})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("unparseable", f"cpc table {code}")
    return df


def _eia_v2_frame(raw: bytes, code: str) -> Any:
    """EIA API v2 (`/v2/seriesid/<v1 id>`): `response.data[]` rows of `period` and `value`
    (values arrive as strings). An error document is a failure, never an empty series."""
    import pandas as pd

    doc = json.loads(raw.decode("utf-8", "replace"))
    resp = doc.get("response") if isinstance(doc, dict) else None
    if not isinstance(resp, dict):
        raise FetchError("unparseable", "eia: no response block")
    rows = []
    for r in resp.get("data") or []:
        if not isinstance(r, dict):
            continue
        f = _num_or_none(r.get("value"))
        per = str(r.get("period") or "")[:10]
        if f is not None and re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", per):
            rows.append({"series_code": code, "period": per, "value": f})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("empty", f"eia {code}")
    return df


def series_from_long(df: Any, *, freq: str = "", hint: str = "") -> list[dict[str, Any]]:
    """A long frame -> series dicts. A `release_utc` column (the instant the publisher released
    that value, ISO UTC) becomes the series' `released` map, which `merge_observations` keys the
    value's availability on instead of a cadence lag."""
    out = []
    dim_cols = [c for c in df.columns if c not in ("series_code", "period", "value", "lag_days",
                                                   "release_utc", "stem", "market_year",
                                                   "available_utc", "freq")]
    for code, g in df.groupby("series_code", sort=False):
        dims = {c: str(g[c].iloc[0]) for c in dim_cols} if dim_cols else {}
        pts = [(str(p), float(v)) for p, v in zip(g["period"], g["value"], strict=False)]
        fq = ((str(g["freq"].iloc[0]) if "freq" in g.columns else "") or freq
              or dims.get("FREQ", ""))
        row: dict[str, Any] = {"code": str(code), "name": f"{hint} {code}".strip(),
                               "freq": norm_freq(fq), "dims": dims, "points": pts}
        if "lag_days" in g.columns:
            # A PER-PERIOD release lag (a publisher whose release slips around holidays): the
            # stamp a period gets, overriding the spec's one lag for that period only.
            row["lag_by_period"] = {str(p): int(lg) for p, lg in
                                    zip(g["period"], g["lag_days"], strict=False)
                                    if lg == lg}
        if "stem" in g.columns:
            # PER-SERIES INSTRUMENT STEMS: a multi-commodity table (WASDE) maps each series to
            # its own commodity, never every series to every commodity the dataset names.
            row["stems"] = sorted({str(x) for x in g["stem"] if isinstance(x, str) and x})
        if "release_utc" in g.columns:
            row["released"] = {str(p): str(r) for p, r in zip(g["period"], g["release_utc"],
                                                              strict=False)
                               if isinstance(r, str) and r}
        if "available_utc" in g.columns:
            row["available"] = {str(p): str(a) for p, a in zip(g["period"], g["available_utc"],
                                                               strict=False) if a}
        out.append(row)
    return out


def _last_business_day(now: datetime) -> str:
    d = now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def direct_sources(now: datetime | None = None) -> list[dict[str, Any]]:
    """The direct doors beside DBnomics. DECLARED because each is a fact about a public API."""
    now = now or _now()
    bis = [("WS_EER", "BIS effective exchange rates"),
           ("WS_CBPOL", "BIS central bank policy rates"),
           ("WS_XRU", "BIS US dollar exchange rates"), ("WS_LONG_CPI", "BIS consumer prices"),
           ("WS_TC", "BIS total credit"), ("WS_CREDIT_GAP", "BIS credit-to-GDP gaps"),
           ("WS_SPP", "BIS residential property prices"), ("WS_DSR", "BIS debt service ratios")]
    out: list[dict[str, Any]] = [
        {"provider": "BIS_BULK", "dataset": code, "name": name, "mode": "bis_flat_zip",
         "url": f"https://data.bis.org/static/bulk/{code}_csv_flat.zip"} for code, name in bis]
    out += [
        {"provider": "CFTC", "dataset": "TFF_EURO_FX", "name": "CFTC TFF EURO FX positioning",
         "mode": "json_records", "date_col": "report_date_as_yyyy_mm_dd", "lag_days": 4,
         "freq": "weekly", "stems": [], "currencies": ["EUR"],
         "url": ("https://publicreporting.cftc.gov/resource/gpe5-46if.json?"
                 + urllib.parse.urlencode({"$where": "starts_with(market_and_exchange_names,"
                                                     "'EURO FX')",
                                           "$order": "report_date_as_yyyy_mm_dd",
                                           "$limit": "5000"}))},
        {"provider": "TREASURY", "dataset": "avg_interest_rates",
         "name": "US Treasury average interest rates on securities", "mode": "json_records",
         "data_key": "data", "date_col": "record_date", "code_col": "security_desc",
         "value_col": "avg_interest_rate_amt", "freq": "monthly", "currencies": ["USD"],
         "url": ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/"
                 "od/avg_interest_rates?sort=-record_date&page%5Bsize%5D=10000")},
    ]
    out += gap_doors()
    out += fund_flow_doors()
    out += agri_nowcast_doors(now)
    out += country_pack_doors()
    for sid in _fred_ids():
        out.append({"provider": "FRED", "dataset": sid, "name": f"FRED {sid}", "mode": "csv",
                    "url": ("https://fred.stlouisfed.org/graph/fredgraph.csv?"
                            + urllib.parse.urlencode({"id": sid})), "currencies": ["USD"]})
    return out


_FISCAL_AUCTIONS = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/"
                    "accounting/od/auctions_query?")
#: (dataset, URL, series code, name). Monthly CPC indices; ONI is the running season. Written as
#: whole URLs so a reader of this file (and `data_class_gap`) sees each data path in full.
_CPC_FILES = (
    ("ONI", "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", "oni",
     "NOAA CPC Oceanic Nino Index ENSO sea surface temperature anomaly"),
    ("NAO", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/"
            "norm.nao.monthly.b5001.current.ascii", "nao",
     "NOAA CPC North Atlantic Oscillation monthly index (European winter heating demand)"),
    ("AO", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/"
           "monthly.ao.index.b50.current.ascii", "ao",
     "NOAA CPC Arctic Oscillation monthly index (northern hemisphere cold outbreaks)"),
    ("PNA", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/"
            "norm.pna.monthly.b5001.current.ascii", "pna",
     "NOAA CPC Pacific North American pattern monthly index (US winter temperature)"),
)
#: EIA weekly series by APIv1 id (served by the v2 `seriesid` route). The petroleum week ends on
#: a Friday and is published the next Wednesday 10:30 ET (Thursday in holiday weeks); natural gas
#: storage the next Thursday 10:30 ET (Friday in holiday weeks).
_EIA_SERIES = (
    ("PET.WCESTUS1.W", "crude_stocks_ex_spr", "petroleum",
     "EIA weekly US commercial crude oil stocks excluding SPR"),
    ("PET.WCSSTUS1.W", "crude_stocks_spr", "petroleum",
     "EIA weekly US crude oil Strategic Petroleum Reserve stocks"),
    ("PET.WGTSTUS1.W", "gasoline_stocks", "petroleum",
     "EIA weekly US total motor gasoline stocks (crude oil product)"),
    ("PET.WDISTUS1.W", "distillate_stocks", "petroleum",
     "EIA weekly US distillate fuel oil stocks (crude oil product)"),
    ("PET.WCRFPUS2.W", "crude_production", "petroleum",
     "EIA weekly US field production of crude oil"),
    ("PET.WPULEUS3.W", "refinery_utilisation", "petroleum",
     "EIA weekly US percent utilisation of refinery operable capacity (crude oil)"),
    ("NG.NW2_EPG0_SWO_R48_BCF.W", "natgas_storage_l48", "natural_gas",
     "EIA weekly working natural gas in underground storage, lower 48"),
)
#: EIA stamps a week by its ENDING Friday, and `period_end` adds six days to a weekly period, so a
#: value lands on the Thursday after; these lags push it to Friday 00:00 UTC (petroleum) and
#: Saturday 00:00 UTC (gas), past even the holiday-week release. Late only costs edge; early
#: would invent it.
_EIA_LAG = {"petroleum": 1, "natural_gas": 2}
_SOFTS_AND_GAS = ["COF", "COCOA", "SUGAR", "CORN", "WHEAT", "SOYBEAN", "COTTON", "XNG"]


def gap_doors() -> list[dict[str, Any]]:
    """The data-class gap doors (sovereign auctions, climate indices, energy inventories) as direct
    specs. EIA rows carry `key_env`: the key is substituted at fetch time from the environment,
    never written to a spec, an artifact or a log, and its absence is the named NEEDS_KEY."""
    out: list[dict[str, Any]] = [
        {"provider": "TREASURY", "dataset": "auctions",
         "name": ("US Treasury securities auction results: bid-to-cover, indirect, direct and "
                  "primary-dealer take-up, stop-out yield, size by security and term"),
         "mode": "treasury_auctions", "freq": "event", "lag_days": 1, "currencies": ["USD"],
         "url": _FISCAL_AUCTIONS + urllib.parse.urlencode(
             {"filter": "auction_date:gte:2008-01-01", "sort": "-auction_date",
              "page[size]": "10000"})}]
    for ds, url, code, name in _CPC_FILES:
        out.append({"provider": "NOAA_CPC", "dataset": ds, "name": name, "mode": "cpc_ascii",
                    "series_code": code, "freq": "monthly", "lag_days": 15,
                    "currencies": ["AUD"] if ds == "ONI" else [], "stems": _SOFTS_AND_GAS,
                    "url": url})
    for sid, code, kind, name in _EIA_SERIES:
        out.append({"provider": "EIA", "dataset": sid, "name": name, "mode": "eia_v2",
                    "series_code": code, "freq": "weekly", "lag_days": _EIA_LAG[kind],
                    "key_env": "EIA_API_KEY",
                    "stems": ["XNG"] if kind == "natural_gas" else ["XTI", "XBR"],
                    "currencies": ["USD", "CAD"] if kind == "petroleum" else ["USD"],
                    "url": (f"https://api.eia.gov/v2/seriesid/{sid}?"
                            "api_key={api_key}&length=5000")})
    return out


# ----------------------------------------------- fund-flow gap doors (data-class gap #1) ----
#: FUND FLOWS (DATA_CLASS_GAP #1, score 7.07, no producer before this). Four official publishers
#: of cross-border and fund flows, each a direct door landing in THIS store, so `build_exposure`
#: maps the series to the hypothesis-lane symbols and `world_macro_proposer` mints
#: `world_macro_state` cells (a z-score band on one flow series) the sealed gauntlet judges as a
#: state for USDJPY, JPN225, EURUSD, US500 and the rest. Terms are rows of the ONE register:
#: `jp_mof` (PUBLIC_PAGE, PDL 1.0), `ecb_data_portal` (API_PERMITTED, ESCB reuse policy),
#: `fed_board` (PUBLIC_PAGE, public domain), `us_tic` (IDEAS_ONLY: no clause read). A door on an
#: IDEAS_ONLY row is refused at `urllib_fetch` (`terms_fenced`) and its missed-growth line is
#: published in the report (`terms_doors`); its parser is still built and pinned on fixtures.
_MOF_ITS = ("https://www.mof.go.jp/policy/international_policy/reference/"
            "itn_transactions_in_securities/")
_TIC_DOCS = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/"
_ECB_IVF = "https://data-api.ecb.europa.eu/service/data/IVF/"
_Z1_DATA = "https://www.federalreserve.gov/releases/z1/data/"

#: MoF weekly columns F2..F23 (week.csv, read 2026-10-29): per side, equity (acquisition,
#: disposition, net), long-term debt (acq, disp, net), subtotal net, short-term debt (acq, disp,
#: net), total net. Unit 100 million yen. Side 1 = portfolio investment ASSETS (residents of
#: Japan buying and selling FOREIGN securities); side 2 = LIABILITIES (non-residents buying and
#: selling JAPANESE securities). Only the NET columns are kept: the flow is the state.
_MOF_NET_COLS = {3: "jp_outward_equity_net", 6: "jp_outward_ltdebt_net",
                 7: "jp_outward_subtotal_net", 10: "jp_outward_stdebt_net",
                 11: "jp_outward_total_net", 14: "foreign_inward_equity_net",
                 17: "foreign_inward_ltdebt_net", 18: "foreign_inward_subtotal_net",
                 21: "foreign_inward_stdebt_net", 22: "foreign_inward_total_net"}
_MOF_WEEK = re.compile(r"^\s*(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*(\d{1,2})\s*[~\u301c-]\s*"
                       r"(?:(\d{4})\s*[.]\s*)?(\d{1,2})\s*[.]\s*(\d{1,2})\s*$")

#: MoF RELEASE TIME (schedule.htm, read 2026-10-29): "Release time is 8:50 AM (Japan Standard
#: Time)", normally the Thursday after the Sunday-Saturday week, but holiday weeks slip: the
#: 2026 calendar shows Friday releases (Oct 16, Nov 6, Nov 27) and Sep 13-19 + Sep 20-26 both
#: released Thu Oct 1 (12 days after the first week ended). A week's value is therefore stamped
#: Saturday + 6 days (Friday 00:00 UTC = 09:00 JST, after a Friday 08:50 release), and a week
#: ending inside a Japanese holiday cluster (Golden Week, Silver Week, year end) + 14 days. Late
#: only costs edge; early would invent it. A value the hunter watches arrive is keyed on its own
#: first_seen_utc whenever that is later (`pit_series`).
_MOF_LAG_D = 6
_MOF_HOLIDAY_LAG_D = 14
_MOF_HOLIDAY_WINDOWS = (((4, 25), (5, 10)), ((9, 13), (9, 23)), ((12, 20), (12, 31)),
                        ((1, 1), (1, 10)))


def _mof_lag(week_end: date) -> int:
    md = (week_end.month, week_end.day)
    return (_MOF_HOLIDAY_LAG_D if any(a <= md <= b for a, b in _MOF_HOLIDAY_WINDOWS)
            else _MOF_LAG_D)


def _decode_jp(raw: bytes) -> str:
    """MoF CSVs are Shift_JIS (cp932); a UTF-8 copy is accepted too."""
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", "replace")


def _mof_weekly_frame(raw: bytes) -> Any:
    """MoF `week.csv` -> one row per (net series, week). The period cell reads like
    `2005.1.2~ 1.8` or `2006.12.31~ 2007.1.6`, written with FULL-WIDTH stops and tilde
    (U+FF0E, U+FF5E) and NFKC-normalised here before the match; the
    period is stamped so `period_end` (period + 6 days for weekly) is the week's own last day,
    and `lag_days` carries the per-week release lag. Non-data rows (title, units, headers,
    blanks) have no parseable period and are skipped; a file with none is unparseable."""
    import csv
    import unicodedata

    import pandas as pd

    rows: list[dict[str, Any]] = []
    for rec in csv.reader(io.StringIO(_decode_jp(raw))):
        if not rec:
            continue
        m = _MOF_WEEK.match(unicodedata.normalize("NFKC", rec[0]))
        if not m:
            continue
        try:
            start = date(int(m[1]), int(m[2]), int(m[3]))
            end = date(int(m[4] or m[1]), int(m[5]), int(m[6]))
        except ValueError:
            continue
        if end < start:                       # `2006.12.31~ 1.6` written without the new year
            end = date(end.year + 1, end.month, end.day)
        if not 0 <= (end - start).days <= 7:
            continue
        period = (end - timedelta(days=6)).isoformat()
        for idx, code in _MOF_NET_COLS.items():
            if idx >= len(rec):
                continue
            v = _num_or_none(unicodedata.normalize("NFKC", rec[idx]).strip())
            if v is not None:
                rows.append({"series_code": code, "period": period, "value": v,
                             "lag_days": _mof_lag(end)})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "lag_days"])
    if df.empty:
        raise FetchError("unparseable", "mof weekly: no week rows")
    return df


#: TIC slt_table1.txt / slt_table2.txt (read 2026-10-29): five preamble lines, then three header
#: rows (groups, display names, machine field names `country country_code date for_lt_*`), then
#: tab-separated rows per country and month (`2026-08`), newest first; "n.a." is absent, never 0.
#: Table 1 is FOREIGN holdings of US long-term securities, its `*_net` the net US sales to
#: foreigners (positive = foreign position up); table 2 is US holdings of FOREIGN securities.
#: Kept: the net-flow fields of every country the hunter's fact table names, plus total rows.
#: RELEASE (release-dates-of-tic-data, read 2026-10-29): "All data releases occur at 4 p.m.
#: Washington, D.C. time", month M in mid-month M+2; the 2026 maximum is 49 days after the
#: month ends (Feb 18 for December), so a month is stamped month end + 50 days. Pre-2026 release
#: dates were not read (the 2025 shutdown may have delayed some): UNMEASURED.
_TIC_LAG_D = 50


def _tic_slt_frame(raw: bytes, prefix: str) -> Any:
    import pandas as pd

    lines = raw.decode("utf-8-sig", "replace").splitlines()
    head = next((i for i, ln in enumerate(lines[:40])
                 if ln.split("\t")[:3] == ["country", "country_code", "date"]), None)
    if head is None:
        raise FetchError("unparseable", "tic slt: no machine field-name row")
    fields = [f.strip() for f in lines[head].split("\t")]
    keep = [(i, f) for i, f in enumerate(fields) if f.endswith("_net")]
    rows: list[dict[str, Any]] = []
    for ln in lines[head + 1:]:
        tok = ln.split("\t")
        if len(tok) < len(fields) or not re.fullmatch(r"\d{4}-\d{2}", tok[2].strip()):
            continue
        country = tok[0].strip()
        low = country.lower()
        if not (low in _NAME_TO_ISO2 or "total" in low or low.startswith("all countries")):
            continue
        for i, f in keep:
            v = _num_or_none(tok[i].strip())
            if v is not None:
                rows.append({"series_code": f"{prefix}_{_slug(country)}_{f}",
                             "period": tok[2].strip(), "value": v,
                             "country": country})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "country"])
    if df.empty:
        raise FetchError("unparseable", "tic slt: no country rows")
    return df


#: ECB SDMX `format=csvdata`: one row per observation, KEY + TIME_PERIOD + OBS_VALUE (+ TITLE
#: when the API sends it). IVF monthly; the ECB's own release lag for monthly investment fund
#: statistics was not read on 2026-10-29: stamped month end + 45 days, release time UNMEASURED.
_ECB_IVF_LAG_D = 45
_ECB_IVF_KEYS = (
    # Total investment funds, investment fund shares/units, total maturity, NET ISSUES (flows),
    # world not allocated, all currencies, euro (dimension labels read on the ECB Data Portal
    # series page 2026-10-29): euro-area fund net sales, the EPFR-class demand state in public.
    ("M.U2.N.T0.L30.A.0.Z5.0000.Z01.E", "ecb_ivf_total_funds_net_issues"),
)


def _ecb_sdmx_csv_frame(raw: bytes) -> Any:
    import pandas as pd

    df = pd.read_csv(io.StringIO(raw.decode("utf-8-sig", "replace")), low_memory=False)
    need = {"KEY", "TIME_PERIOD", "OBS_VALUE"}
    if not need <= set(df.columns):
        raise FetchError("unparseable", "ecb csvdata without KEY/TIME_PERIOD/OBS_VALUE")
    out = pd.DataFrame({"series_code": df["KEY"].astype(str),
                        "period": df["TIME_PERIOD"].astype(str).str.strip(),
                        "value": pd.to_numeric(df["OBS_VALUE"], errors="coerce")})
    out = out.dropna(subset=["value"])
    if out.empty:
        raise FetchError("empty", "ecb csvdata")
    return out


#: Fed Z.1 (releases/z1, read 2026-10-29): quarterly, "typically released during the second week
#: of March, June, September, and December", next at 12:00 noon ET. 2023-2026 releases were
#: 68-100 days after quarter end (2025:Q3 on 2026-01-09 after the shutdown, 2025:Q4 on 2026-03-19
#: at 78): stamped quarter end + 80 days, 2025:Q3 + 101. The package is the Data Download Program
#: CSV zip (`FRB_Z1_csv.zip`): DDP layout, metadata rows then `Time Period` + series ids. Kept:
#: the sector prefixes whose flows are fund flows -- rest of world (26), money market funds (63),
#: mutual funds (65), ETFs (56) -- as unadjusted flows (FU) and levels (FL). The live zip's inner
#: layout and size were not readable from the build sandbox: UNMEASURED until the box fetches it.
_Z1_LAG_D = 80
_Z1_LAG_OVERRIDE = {"2025Q3": 101}
_Z1_PREFIXES = ("FU26", "FU63", "FU65", "FU56", "FL63", "FL65", "FL56")
_Z1_MAX_SERIES = 600


def _ddp_rows(text: str) -> list[tuple[str, str, float]]:
    """One DDP 'seriescolumn' CSV -> (series id, period, value). Metadata rows precede the
    `Time Period` row, whose cells are the series ids; ND / NA cells are absent."""
    import csv

    out: list[tuple[str, str, float]] = []
    ids: list[str] | None = None
    for rec in csv.reader(io.StringIO(text)):
        if not rec:
            continue
        first = rec[0].strip()
        if ids is None:
            if first.lower() == "time period":
                ids = [c.strip().split("/")[-1] for c in rec[1:]]
            continue
        if not re.fullmatch(r"\d{4}(?:Q[1-4]|-\d{2}(?:-\d{2})?)?", first):
            continue
        for sid, cell in zip(ids, rec[1:], strict=False):
            v = _num_or_none(cell.strip())
            if v is not None and sid:
                out.append((sid, first, v))
    return out


def _z1_ddp_frame(raw: bytes) -> Any:
    import pandas as pd

    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            text = zf.read(name).decode("utf-8-sig", "replace")
            for sid, per, v in _ddp_rows(text):
                if not sid.upper().startswith(_Z1_PREFIXES):
                    continue
                rows.append({"series_code": sid.upper(), "period": per, "value": v,
                             "lag_days": _Z1_LAG_OVERRIDE.get(per, _Z1_LAG_D)})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "lag_days"])
    if df.empty:
        raise FetchError("unparseable", "z1 ddp: no fund-flow sector series")
    keep = sorted(df["series_code"].unique())[:_Z1_MAX_SERIES]
    return df[df["series_code"].isin(keep)]


def fund_flow_doors() -> list[dict[str, Any]]:
    """The fund-flow doors as direct specs (`direct_sources` appends them)."""
    out: list[dict[str, Any]] = [
        {"provider": "JP_MOF", "dataset": "ITS_WEEKLY",
         "name": ("Japan Ministry of Finance weekly international transactions in securities: "
                  "net purchases of foreign stocks and bonds by residents of Japan and of "
                  "Japanese stocks and bonds by foreign investors (100 million yen)"),
         "mode": "mof_weekly", "freq": "weekly", "lag_days": _MOF_LAG_D,
         "currencies": ["JPY"], "url": _MOF_ITS + "week.csv"}]
    for table, side, prefix in (("slt_table1", "foreign purchases of United States long-term "
                                 "securities", "foreign_in"),
                                ("slt_table2", "United States purchases of foreign long-term "
                                 "securities", "us_out")):
        out.append({"provider": "US_TIC", "dataset": table,
                    "name": f"US Treasury TIC monthly {side} by country (net, USD millions)",
                    "mode": "tic_slt", "series_prefix": prefix, "freq": "monthly",
                    "lag_days": _TIC_LAG_D, "currencies": ["USD"],
                    "url": _TIC_DOCS + f"{table}.txt"})
    for key, code in _ECB_IVF_KEYS:
        out.append({"provider": "ECB_IVF", "dataset": code,
                    "name": ("ECB euro area investment fund statistics: investment fund shares "
                             "net issues, total funds (euro)"),
                    "mode": "ecb_sdmx_csv", "freq": "monthly", "lag_days": _ECB_IVF_LAG_D,
                    "currencies": ["EUR"], "url": _ECB_IVF + key + "?format=csvdata"})
    out.append({"provider": "FED_Z1", "dataset": "FUND_FLOWS",
                "name": ("Federal Reserve Z.1 Financial Accounts of the United States: rest of "
                         "world, money market fund, mutual fund and ETF flows and levels"),
                "mode": "z1_ddp_zip", "freq": "quarterly", "lag_days": _Z1_LAG_D,
                "currencies": ["USD"], "url": _Z1_DATA + "FRB_Z1_csv.zip"})
    return out


def terms_doors() -> list[dict[str, Any]]:
    """Every direct door's reading in the ONE register: its row, live status and terms state.
    A door the register refuses as live input carries `terms_fence.held_missed_growth` (kind
    ideas_only_refusal, delta E[log W] UNMEASURED) -- the growth governance line for the hold."""
    from libs.data import terms_fence as _tf

    out: list[dict[str, Any]] = []
    for spec in direct_sources():
        url = str(spec.get("url") or "")
        key = _tf.source_of_url(url)
        refused = _tf.input_source(url)
        row: dict[str, Any] = {"door": f"{spec['provider']}/{spec['dataset']}",
                               "policy_row": key,
                               "status": _tf.live_input_status(key) if key else "UNLISTED",
                               "terms_state": _tf.terms_state(key) if key else _tf.UNREAD,
                               "live_input": "REFUSED" if refused else "PERMITTED"}
        if refused:
            row["missed_growth"] = _tf.held_missed_growth(refused, source=row["door"],
                                                          live_input_refusal=True)
        out.append(row)
    return out


# --------------------------------------- agri supply and nowcast vintage doors (2026-10-29) ----
#: GAP #4 (agri_supply) AND #5 (macro_nowcasts_vintages) OF research/data_class_gap.py, landed in
#: this organ's store so `world_macro_proposer` mints `world_macro_state` cells from them. Each
#: value is keyed on the publisher's OWN release instant (a `release_utc` column; never a guessed
#: cadence lag): crop progress Monday 16:00 ET for the week ending the Sunday before (Tuesday
#: when Monday is a federal holiday), export sales Thursday 08:30 ET for the week ending the
#: Thursday before (Friday in a week with a weekday federal holiday), WASDE 12:00 ET on its own
#: release date, a nowcast at 18:00 ET of its publication day. Every rule errs LATE: a late stamp
#: costs edge, an early one invents it. Terms: the `usda_nass_quickstats`, `usda_fas_esr`,
#: `usda_wasde` and `nyfed_web` rows of libs/data/terms_fence.SOURCE_POLICY, clauses quoted.
#: CONAB, the Atlanta Fed (GDPNow) and the Philadelphia Fed (ADS) are IDEAS_ONLY rows: their
#: parsers below are tested on fixtures and NO door fetches them as live input.
_ET_ZONE = "America/New_York"
#: When the tz database is missing (a bare Windows Python without tzdata), EST (UTC-5) is the
#: LATE side of Eastern time all year: an EDT release stamped an hour late, never early.
_ET_FALLBACK_H = -5


def _et_utc(day: date, hh: int, mm: int) -> str:
    """ISO UTC instant of `hh:mm` Eastern time on `day`."""
    try:
        from zoneinfo import ZoneInfo
        local = datetime(day.year, day.month, day.day, hh, mm, tzinfo=ZoneInfo(_ET_ZONE))
        return local.astimezone(UTC).isoformat()
    except Exception:
        at = datetime(day.year, day.month, day.day, hh, mm, tzinfo=UTC)
        return (at - timedelta(hours=_ET_FALLBACK_H)).isoformat()


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of a month; n=-1 is the last."""
    if n < 0:
        d = _month_end(year, month)
        return d - timedelta(days=(d.weekday() - weekday) % 7)
    d = date(year, month, 1)
    return d + timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))


@lru_cache(maxsize=64)
def us_federal_holidays(year: int) -> frozenset[date]:
    """US federal holidays as observed (5 U.S.C. 6103): fixed dates shift Sat->Fri, Sun->Mon."""
    out: set[date] = set()
    fixed = [(1, 1), (7, 4), (11, 11), (12, 25)] + ([(6, 19)] if year >= 2021 else [])
    for m, d in fixed:
        day = date(year, m, d)
        out.add(day - timedelta(days=1) if day.weekday() == 5
                else day + timedelta(days=1) if day.weekday() == 6 else day)
    out |= {_nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3),
            _nth_weekday(year, 5, 0, -1), _nth_weekday(year, 9, 0, 1),
            _nth_weekday(year, 10, 0, 2), _nth_weekday(year, 11, 3, 4)}
    return frozenset(out)


def _holiday(d: date) -> bool:
    return d in us_federal_holidays(d.year)


def crop_progress_release(week_ending: date) -> str:
    """NASS Crop Progress: the Monday after the week ending (a Sunday), 16:00 ET; the next
    business day when that Monday is a federal holiday."""
    d = week_ending + timedelta(days=(0 - week_ending.weekday()) % 7 or 7)
    while d.weekday() >= 5 or _holiday(d):
        d += timedelta(days=1)
    return _et_utc(d, 16, 0)


def export_sales_release(week_ending: date) -> str:
    """FAS Export Sales: the Thursday a week after the week ending (a Thursday), 08:30 ET; the
    Friday when any weekday of that release week up to Thursday is a federal holiday."""
    thu = week_ending + timedelta(days=7)
    monday = thu - timedelta(days=thu.weekday())
    if any(_holiday(monday + timedelta(days=i)) for i in range(4)):
        thu += timedelta(days=1)
    while _holiday(thu) or thu.weekday() >= 5:
        thu += timedelta(days=1)
    return _et_utc(thu, 8, 30)


def wasde_release(day: date) -> str:
    """WASDE: 12:00 ET on the release date the report itself carries."""
    return _et_utc(day, 12, 0)


#: Commodity (as the USDA names it, lower case) -> the MT5 stem it informs. A commodity with no
#: stem is UNMAPPED and recorded so (`agri_mapping`), never dropped silently.
AGRI_STEMS: dict[str, str | None] = {
    "corn": "CORN", "soybeans": "SOYBEAN", "wheat": "WHEAT", "cotton": "COTTON",
    "sugar": "SUGAR", "cocoa": "COCOA", "orange juice": "OJ", "coffee": "COF",
    "rice": None, "sorghum": None, "barley": None, "oats": None, "soybean oil": None,
    "soybean meal": None,
}


def agri_mapping(universe: tuple[tuple[str, str, str], ...] | None = None) -> dict[str, Any]:
    """Each USDA commodity -> the hypothesis-lane MT5 symbols it reaches in the broker's own
    registry, and every commodity that reaches none (no stem, or a stem the registry lacks)."""
    mapped: dict[str, list[str]] = {}
    unmapped: dict[str, str] = {}
    for name, stem in AGRI_STEMS.items():
        if not stem:
            unmapped[name] = "no MT5 instrument class for it"
            continue
        syms = instruments_for([], [stem], universe)
        if syms:
            mapped[name] = syms
        else:
            unmapped[name] = f"stem {stem} matches no hypothesis-lane symbol in universe.json"
    return {"mapped": mapped, "unmapped": unmapped}


_NASS_NUM = re.compile(r"^-?[\d,]*\.?\d+$")


def _lslug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _nass_frame(raw: bytes, code: str) -> Any:
    """NASS Quick Stats `api_GET` JSON (`data[]`): NATIONAL weekly crop progress / condition.
    One series per `short_desc` (e.g. CORN - CONDITION, MEASURED IN PCT GOOD) plus, for
    condition, the good+excellent share per week. Suppressed values ("(D)", "(NA)") are absent
    observations, never zeros. The period is the Monday that STARTS the week (the hunter's
    weekly period), the release is the Monday-after 16:00 ET."""
    import pandas as pd

    doc = json.loads(raw.decode("utf-8", "replace"))
    if isinstance(doc, dict) and doc.get("error"):
        raise FetchError("api_error", f"nass: {str(doc.get('error'))[:120]}")
    rows: list[dict[str, Any]] = []
    ge: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in (doc.get("data") or []) if isinstance(doc, dict) else []:
        if not isinstance(r, dict):
            continue
        if str(r.get("agg_level_desc") or "NATIONAL").upper() != "NATIONAL":
            continue
        we = str(r.get("week_ending") or "")[:10]
        val = str(r.get("Value") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", we) or not _NASS_NUM.match(val):
            continue
        end = date.fromisoformat(we)
        start = (end - timedelta(days=6)).isoformat()
        short = str(r.get("short_desc") or "")
        f = float(val.replace(",", ""))
        rel = crop_progress_release(end)
        rows.append({"series_code": _lslug(short)[:120] or code, "period": start,
                     "value": f, "release_utc": rel})
        m = re.match(r"(.+?) - CONDITION, MEASURED IN PCT (GOOD|EXCELLENT)$", short, re.I)
        if m:
            ge[(_lslug(m[1]), start)][m[2].lower()] = f
            ge[(_lslug(m[1]), start)]["_end"] = float(end.toordinal())
    for (crop, start), parts in ge.items():
        if "good" in parts and "excellent" in parts:
            end = date.fromordinal(int(parts["_end"]))
            rows.append({"series_code": f"{crop}_condition_good_excellent",
                         "period": start, "value": parts["good"] + parts["excellent"],
                         "release_utc": crop_progress_release(end)})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "release_utc"])
    if df.empty:
        raise FetchError("empty", f"nass {code}")
    return df.drop_duplicates(["series_code", "period"], keep="last")


_ESR_FIELDS = (("currentMYNetSales", "net_sales"), ("weeklyExports", "exports"),
               ("outstandingSales", "outstanding"),
               ("currentMYTotalCommitment", "total_commitment"),
               ("nextMYNetSales", "next_my_net_sales"))


def _fas_esr_frame(raw: bytes, code: str, market_year: int | None = None) -> Any:
    """FAS Export Sales API (`/api/esr/exports/...allCountries/marketYear/N`): per-destination
    weekly records summed over destinations into US totals per week. The period is the Friday
    that starts the week ending on `weekEndingDate` (a Thursday); release next Thursday 08:30
    ET. `market_year` rides along so overlapping weeks keep the later market year."""
    import pandas as pd

    doc = json.loads(raw.decode("utf-8", "replace"))
    recs = doc if isinstance(doc, list) else (doc.get("data") or [] if isinstance(doc, dict)
                                              else [])
    tot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in recs:
        if not isinstance(r, dict):
            continue
        we = str(r.get("weekEndingDate") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", we):
            continue
        for src, name in _ESR_FIELDS:
            v = _num_or_none(r.get(src))
            if v is not None:
                tot[we][name] += v
    rows = []
    for we, vals in tot.items():
        end = date.fromisoformat(we)
        for name, v in vals.items():
            rows.append({"series_code": f"{code}_{name}",
                         "period": (end - timedelta(days=6)).isoformat(), "value": v,
                         "release_utc": export_sales_release(end),
                         "market_year": int(market_year or 0)})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "release_utc",
                                     "market_year"])
    if df.empty:
        raise FetchError("empty", f"fas esr {code}")
    return df


_WASDE_COLS = {"release": ("releasedate", "reportdate"), "commodity": ("commodity",),
               "region": ("region",), "my": ("marketyear",), "flag": ("projestflag",),
               "attr": ("attribute",), "value": ("value",)}
#: WASDE regions read; the World balance is the global stocks-to-use the softs price off.
WASDE_REGIONS = {"united states": "us", "world": "world"}


def _wasde_csv_tables(raw: bytes) -> list[Any]:
    import pandas as pd

    if raw[:2] == b"PK":
        out = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".csv"):
                    out.append(pd.read_csv(zf.open(name), low_memory=False, dtype=str))
        if not out:
            raise FetchError("unparseable", "wasde zip without csv")
        return out
    if raw[:1] == b"<" or raw[:15].lower().startswith(b"<!doctype"):
        raise FetchError("served_html", "wasde")
    return [pd.read_csv(io.BytesIO(raw), low_memory=False, dtype=str)]


def _wasde_frame(raw: bytes, code: str = "wasde") -> Any:
    """WASDE as-reported report data (CSV, or a zip of them): for each release, commodity and
    region (United States, World), the CURRENT projection's ending stocks, total use and
    stocks-to-use (ending stocks / total use). The current projection is the latest market
    year flagged a projection in that release. Total use is the table's own total-use line, else
    domestic use + exports. Period = the release date; release 12:00 ET that day."""
    import pandas as pd

    frames = []
    for df in _wasde_csv_tables(raw):
        cols = {re.sub(r"[^a-z]", "", str(c).lower()): c for c in df.columns}
        pick = {k: next((cols[a] for a in al if a in cols), None) for k, al in _WASDE_COLS.items()}
        if any(v is None for v in pick.values()):
            raise FetchError("unparseable", f"wasde columns {sorted(cols)[:12]}")
        sub = pd.DataFrame({k: df[v].astype(str).str.strip() for k, v in pick.items()})
        frames.append(sub)
    t = pd.concat(frames, ignore_index=True)
    t["commodity"] = t["commodity"].str.lower()
    t["region"] = t["region"].str.lower()
    t = t[t["region"].isin(WASDE_REGIONS) & t["flag"].str.lower().str.startswith("proj")]
    t = t.assign(day=pd.to_datetime(t["release"], errors="coerce", format="mixed").dt.date,
                 v=pd.to_numeric(t["value"].str.replace(",", ""), errors="coerce"),
                 attr=t["attr"].str.lower())
    t = t.dropna(subset=["day", "v"])
    rows: list[dict[str, Any]] = []
    for (day, comm, reg), g in t.groupby(["day", "commodity", "region"], sort=False):
        base = next((k for k in AGRI_STEMS if comm == k or comm.startswith(k + " ")
                     or comm.startswith(k + ",")), None)
        if base is None:
            continue
        g = g[g["my"] == max(g["my"])]                     # the current projection year
        by = {str(a): float(v) for a, v in zip(g["attr"], g["v"], strict=False)}
        ending = by.get("ending stocks")
        use = next((by[a] for a in ("use, total", "total use", "use total", "total domestic "
                                    "and exports") if a in by), None)
        if use is None:
            dom = next((by[a] for a in by if a.startswith("domestic") and "total" in a), None)
            dom = dom if dom is not None else by.get("domestic use")
            exp = by.get("exports")
            use = dom + exp if dom is not None and exp is not None else None
        sid = f"{code}_{WASDE_REGIONS[reg]}_{_lslug(base)}"
        rel = wasde_release(day)
        for name, v in (("ending_stocks", ending), ("total_use", use),
                        ("stocks_to_use", ending / use if ending is not None and use else None)):
            if v is not None:
                rows.append({"series_code": f"{sid}_{name}", "period": day.isoformat(),
                             "value": float(v), "release_utc": rel,
                             "stem": AGRI_STEMS.get(base) or ""})
    out = pd.DataFrame(rows, columns=["series_code", "period", "value", "release_utc", "stem"])
    if out.empty:
        raise FetchError("empty", "wasde: no current projection for a mapped commodity")
    return out.drop_duplicates(["series_code", "period"], keep="last")


# ------------------------------------------------------------------ xlsx without openpyxl ----
_XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref or "A")[0]:          # type: ignore[index]
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(raw: bytes) -> dict[str, list[list[Any]]]:
    """Every sheet of an .xlsx as rows of cell values (str, float or None), stdlib only (the box
    has no guarantee of openpyxl). Dates stay Excel serials: the caller knows which columns
    hold dates (`excel_date`)."""
    import xml.etree.ElementTree as ET

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise FetchError("unparseable", "not an xlsx") from exc
    with zf:
        names = set(zf.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).iter(f"{_XNS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_XNS}t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels")):
                rels[r.get("Id")] = str(r.get("Target") or "").lstrip("/")
        out: dict[str, list[list[Any]]] = {}
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        for sh in wb.iter(f"{_XNS}sheet"):
            target = rels.get(sh.get(f"{_RNS}id"), "")
            path = target if target.startswith("xl/") else f"xl/{target}"
            if path not in names:
                continue
            rows: list[list[Any]] = []
            for row in ET.fromstring(zf.read(path)).iter(f"{_XNS}row"):
                cells: list[Any] = []
                for c in row.iter(f"{_XNS}c"):
                    i = _col_index(str(c.get("r") or ""))
                    t = c.get("t")
                    v = c.find(f"{_XNS}v")
                    if t == "s" and v is not None:
                        val: Any = shared[int(v.text or 0)]
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{_XNS}t"))
                    elif t == "str":
                        val = v.text if v is not None else None
                    elif v is not None and v.text is not None:
                        val = _num_or_none(v.text)
                    else:
                        val = None
                    cells.extend([None] * (i - len(cells) + 1))
                    cells[i] = val
                rows.append(cells)
            out[str(sh.get("name"))] = rows
    return out


def excel_date(v: Any) -> date | None:
    """An Excel serial (1900 system) or a date string -> date; None when it is neither."""
    if isinstance(v, (int, float)) and 1000 < float(v) < 80000:
        return date(1899, 12, 30) + timedelta(days=int(float(v)))
    s = str(v or "").strip()
    m = re.match(r"(\d{4})[-:/](\d{1,2})[-:/](\d{1,2})", s) or None
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        try:
            return date(int(m[3]), int(m[1]), int(m[2]))
        except ValueError:
            return None
    return None


_QTR = re.compile(r"(\d{4})\s*[:\-]?\s*Q([1-4])|Q([1-4])\s*[:\-]?\s*(\d{4})", re.I)


def _quarter_of(v: Any) -> tuple[int, int] | None:
    m = _QTR.search(str(v or ""))
    if m:
        return (int(m[1]), int(m[2])) if m[1] else (int(m[4]), int(m[3]))
    d = excel_date(v)
    return (d.year, (d.month - 1) // 3 + 1) if d else None


def _tables(raw: bytes) -> list[list[list[Any]]]:
    if raw[:2] == b"PK":
        return list(xlsx_sheets(raw).values())
    import csv
    text = raw.decode("utf-8-sig", "replace")
    if text.lstrip()[:1] == "<":
        raise FetchError("served_html", "nowcast")
    return [[list(r) for r in csv.reader(io.StringIO(text))]]


def nowcast_vintages(raw: bytes) -> list[tuple[date, tuple[int, int], float]]:
    """(publication date, target quarter, nowcast) for every published vintage in a nowcast
    history table, LONG (a date column, a quarter column, a nowcast column: GDPNow's tracking
    archive) or WIDE (a date column and one column per target quarter: the NY Fed download).
    Nothing is overwritten: every publication is its own row."""
    out: list[tuple[date, tuple[int, int], float]] = []
    for rows in _tables(raw):
        for hi, head in enumerate(rows[:30]):
            hs = [str(h or "").strip().lower() for h in head]
            dcol = next((i for i, h in enumerate(hs)
                         if re.search(r"forecast date|release date|^date$|timestamp|as of", h)),
                        None)
            if dcol is None:
                continue
            qcol = next((i for i, h in enumerate(hs)
                         if re.search(r"quarter|target|reference period", h)), None)
            vcol = next((i for i, h in enumerate(hs)
                         if i not in (dcol, qcol) and re.search(r"nowcast|gdp", h)), None)
            wide = {i: q for i, h in enumerate(head) if i != dcol
                    and (q := (_quarter_of(h) if _QTR.search(str(h or "")) else None))}
            for r in rows[hi + 1:]:
                if dcol >= len(r):
                    continue
                d = excel_date(r[dcol])
                if d is None:
                    continue
                if qcol is not None and vcol is not None and max(qcol, vcol) < len(r):
                    q, v = _quarter_of(r[qcol]), _num_or_none(r[vcol])
                    if q and v is not None:
                        out.append((d, q, v))
                elif wide:
                    for i, q in wide.items():
                        v = _num_or_none(r[i]) if i < len(r) else None
                        if v is not None:
                            out.append((d, q, v))
            if out:
                return sorted(set(out))
    return sorted(set(out))


def _nowcast_frame(raw: bytes, code: str, release_hh: int = 18) -> Any:
    """Nowcast vintages -> three series on the publication clock (release `release_hh`:00 ET):
    `<code>_q0` the nowcast of the quarter containing the publication day, `<code>_q0_rev` its
    change since the previous publication for the SAME quarter (the news the vintage carried),
    and `<code>_qm1` the previous quarter's nowcast while it is still being tracked."""
    import pandas as pd

    vint = nowcast_vintages(raw)
    if not vint:
        raise FetchError("unparseable", f"nowcast {code}: no dated vintages")
    by_day: dict[date, dict[tuple[int, int], float]] = defaultdict(dict)
    for d, q, v in vint:
        by_day[d][q] = v
    rows: list[dict[str, Any]] = []
    last: dict[tuple[int, int], float] = {}
    for d in sorted(by_day):
        q0 = (d.year, (d.month - 1) // 3 + 1)
        qm1 = (q0[0] - (q0[1] == 1), 4 if q0[1] == 1 else q0[1] - 1)
        rel = _et_utc(d, release_hh, 0)
        cur = by_day[d]
        if q0 in cur:
            rows.append({"series_code": f"{code}_q0", "period": d.isoformat(),
                         "value": cur[q0], "release_utc": rel})
            if q0 in last:
                rows.append({"series_code": f"{code}_q0_rev", "period": d.isoformat(),
                             "value": cur[q0] - last[q0], "release_utc": rel})
        if qm1 in cur:
            rows.append({"series_code": f"{code}_qm1", "period": d.isoformat(),
                         "value": cur[qm1], "release_utc": rel})
        last.update(cur)
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "release_utc"])
    if df.empty:
        raise FetchError("empty", f"nowcast {code}: no current-quarter vintage")
    return df


def _ads_frame(raw: bytes, code: str = "ads") -> Any:
    """Philadelphia Fed ADS index file (first column a date, `YYYY:MM:DD` or a serial; second
    the index). IDEAS_ONLY (row `philly_fed`): tested on fixtures, never fetched as live input.
    A re-read vintage lands as revised rows through `merge_observations`, never an overwrite."""
    import pandas as pd

    rows = []
    for table in _tables(raw):
        for r in table:
            if len(r) < 2:
                continue
            d, v = excel_date(r[0]), _num_or_none(r[1])
            if d is not None and v is not None:
                rows.append({"series_code": code, "period": d.isoformat(), "value": v})
        if rows:
            break
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("unparseable", "ads")
    return df


#: IDEAS_ONLY nowcast/vintage parsers: policy row -> (parser, what it reads). No URL of theirs
#: is held in fetching code; the hunter's report carries each one's missed-growth line.
IDEAS_ONLY_PARSERS: dict[str, tuple[str, str]] = {
    "atlanta_fed": ("_nowcast_frame", "GDPNow tracking archive (each forecast with its date)"),
    "philly_fed": ("_ads_frame", "ADS business conditions index, every vintage"),
    "conab_brazil": ("", "CONAB crop survey: no lawful machine-readable file found"),
}


def ideas_only_lines() -> list[dict[str, Any]]:
    """The missed-growth line of every IDEAS_ONLY source the gap doors name."""
    from libs.data import terms_fence as _tf
    out = []
    for key, (parser, what) in IDEAS_ONLY_PARSERS.items():
        if key in _tf.SOURCE_POLICY:
            line = _tf.held_missed_growth(key, live_input_refusal=True)
            line.update({"reads": what, "parser": parser or "none (no lawful file found)"})
            out.append(line)
    return out


_NASS_API = "https://quickstats.nass.usda.gov/api/api_GET/?"
_NASS_QUERIES = (("CORN", "CONDITION"), ("CORN", "PROGRESS"), ("SOYBEANS", "CONDITION"),
                 ("SOYBEANS", "PROGRESS"), ("WHEAT", "CONDITION"), ("WHEAT", "PROGRESS"),
                 ("COTTON", "CONDITION"))
#: FAS ESR commodity codes (the API's own `/api/esr/commodities` list; UNVERIFIED from this
#: sandbox, whose reader got client_error on the OpenData page: a wrong code reads as a named
#: empty/404 failure on the box, never as a zero).
_ESR_COMMODITIES = (("401", "corn", "CORN"), ("801", "soybeans", "SOYBEAN"),
                    ("107", "wheat", "WHEAT"), ("1404", "cotton_upland", "COTTON"))
_ESR_API = "https://apps.fas.usda.gov/OpenData/api/esr/exports/commodityCode/"
_WASDE_FILES = "https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-"
#: The NY Fed Staff Nowcast download (the page renders it client-side; the path is the one the
#: page's Download button serves, UNVERIFIED from this sandbox: a 404 on the box is reported as
#: not_found_404 by name).
_NYFED_NOWCAST = ("https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/NowCast/"
                  "Downloads/New-York-Fed-Staff-Nowcast_download_data.xlsx")


def agri_nowcast_doors(now: datetime) -> list[dict[str, Any]]:
    """The gap #4 / #5 doors as direct specs. `urls` fetches several payloads into one dataset;
    `urls_backfill` is added only while the dataset holds no rows yet."""
    out: list[dict[str, Any]] = []
    for comm, stat_ in _NASS_QUERIES:
        out.append({"provider": "USDA_NASS", "dataset": f"{comm}_{stat_}",
                    "name": f"USDA NASS crop {stat_.lower()} {comm.lower()} weekly national",
                    "mode": "nass_quickstats", "series_code": f"{comm.lower()}",
                    "freq": "weekly", "key_env": "NASS_API_KEY", "currencies": [],
                    "stems": [AGRI_STEMS[comm.lower()] or ""],
                    "url": _NASS_API + "key={api_key}&" + urllib.parse.urlencode(
                        {"commodity_desc": comm, "statisticcat_desc": stat_,
                         "agg_level_desc": "NATIONAL", "freq_desc": "WEEKLY",
                         "year__GE": "2008", "format": "JSON"})})
    y = now.year
    for ccode, name, stem in _ESR_COMMODITIES:
        urls = [{"url": f"{_ESR_API}{ccode}/allCountries/marketYear/{my}", "market_year": my}
                for my in (y - 1, y, y + 1)]
        back = [{"url": f"{_ESR_API}{ccode}/allCountries/marketYear/{my}", "market_year": my}
                for my in range(y - 10, y - 1)]
        out.append({"provider": "USDA_FAS", "dataset": f"ESR_{ccode}",
                    "name": f"USDA FAS weekly export sales {name.replace('_', ' ')}",
                    "mode": "fas_esr", "series_code": name, "freq": "weekly",
                    "currencies": [], "stems": [stem], "url": urls[-1]["url"], "urls": urls,
                    "urls_backfill": back})
    months = [(now.replace(day=1) - timedelta(days=31 * k)) for k in (2, 1, 0)]
    recent = [{"url": f"{_WASDE_FILES}{m:%Y-%m}.csv"} for m in months]
    back = ([{"url": f"{_WASDE_FILES}2010-04-to-2015-12.zip"},
             {"url": f"{_WASDE_FILES}2016-01-to-2020-12.zip"}]
            + [{"url": f"{_WASDE_FILES}{yy:04d}-{mm:02d}.csv"}
               for yy in range(2021, y + 1) for mm in range(1, 13)
               if (yy, mm) < (months[0].year, months[0].month)])
    out.append({"provider": "USDA_WASDE", "dataset": "wasde_balance",
                "name": "USDA WASDE as-reported ending stocks, total use and stocks-to-use "
                        "(corn soybeans wheat cotton sugar, US and world)",
                "mode": "wasde_csv", "series_code": "wasde", "freq": "monthly",
                "currencies": [], "stems": sorted({s for s in AGRI_STEMS.values() if s}),
                "url": recent[-1]["url"], "urls": recent, "urls_backfill": back})
    out.append({"provider": "NYFED", "dataset": "staff_nowcast",
                "name": "New York Fed Staff Nowcast of US real GDP growth, every vintage",
                "mode": "nowcast_vintage", "series_code": "nyfed_nowcast", "freq": "daily",
                "currencies": ["USD"], "stems": [], "url": _NYFED_NOWCAST})
    return out


# ------------------------------------------------------ country open-data packs (2026-11-03) ----
#: THE COUNTRY OPEN-DATA PACKS (REGION_GAP_RANK 2026-11-03: Indonesia rank 2, Singapore 7, Saudi
#: Arabia 9; Japan and China named weak). Each pack is a set of direct doors of THIS organ -- no
#: second lane: their series land in the same PIT store, `build_exposure` hands them to
#: `world_macro_proposer`, and the gauntlet sees them as `world_macro_state` cells.
#:
#: TERMS DECIDE LIVE INPUT. Every door names its row of the one register
#: (libs/data/terms_fence.SOURCE_POLICY). A door whose URL `input_source` refuses (IDEAS_ONLY or
#: held) is never requested as data: the pass records it as IDEAS_ONLY with the register's
#: missed-growth line (delta E[log W] UNMEASURED), and its parser is exercised on fixtures only.
#: A door whose key is absent reads NEEDS_KEY by name, never zero.
#:
#: LIVENESS. Each door counts its consecutive attempts that landed nothing (`empty_streak`, reset
#: by a fetch that lands rows). More than PACK_EMPTY_RED_RUNS in a row is RED, and a RED door
#: puts its name in the report's top-level `status`, which `health_board` reads as the organ's
#: own last reading (the desk's existing RED path; no new board).
#:
#: China is a pack WITHOUT a door here: its exchanges' daily warehouse receipts and member
#: rankings already have an organ (libs/data/free_stack_cnx.py under the free-stack hunter), and
#: its rows (cnx_shfe / cnx_dce / cnx_czce) hold it on terms. The pack reports that organ's
#: terms state and instrument map so the gap is visible in one place, and builds nothing twice.
PACK_EMPTY_RED_RUNS = 2
#: MoF publishes the DAILY breakdown of intervention a quarter at a time (latest read 2026-11-03:
#: "April - June 2026 (August 7, 2026)", 38 days after the quarter); the monthly totals follow
#: each month's last business day. The daily file is stamped at quarter end + this many days at
#: 10:00 UTC (19:00 JST) -- a bound later than the stated release; late only costs edge.
MOF_FEIO_RELEASE_LAG_D = 45
_MOF_FEIO_CSV = ("https://www.mof.go.jp/english/policy/international_policy/reference/feio/"
                 "foreign_exchange_intervention_operations.csv")
_MAS_GW = "https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610mssql/"
_BOJ_API = "https://www.stat-search.boj.or.jp/api/v1/getDataCode?"
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                       "sep", "oct", "nov", "dec"), start=1)}
_MONTHS.update({"mei": 5, "agu": 8, "agt": 8, "okt": 10, "des": 12, "januari": 1,
                "februari": 2, "maret": 3, "juni": 6, "juli": 7, "agustus": 8,
                "oktober": 10, "desember": 12})


def _decode_any(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp932", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _quarter_of_date(d: date) -> tuple[int, int]:
    return d.year, (d.month - 1) // 3 + 1


def mof_feio_release(year: int, quarter: int) -> datetime:
    """The instant a quarter's daily intervention breakdown is treated as public (see
    MOF_FEIO_RELEASE_LAG_D)."""
    end = _month_end(year, quarter * 3)
    return datetime(end.year, end.month, end.day, 10, tzinfo=UTC) + timedelta(
        days=MOF_FEIO_RELEASE_LAG_D)


def _mof_feio_frame(raw: bytes) -> Any:
    """MoF `foreign_exchange_intervention_operations.csv`: nine columns (Japanese era year, month,
    day, then the Western year, month and day, the amount in 100 million yen, the currency pair in
    Japanese and in English). Year and month are blank on rows that continue them; quarterly
    `期計` rows carry the period in English ("July - September 2022") and the quarter's total.

    Produces `yen_bought_100m_jpy` (each operation, + when the yen was bought, - when sold) and
    `qtr_net_yen_bought_100m_jpy` (every quarter the file lists, 0 when nothing was done), both
    stamped at the quarter's release, never at the operation date."""
    import csv

    import pandas as pd

    text = _decode_any(raw)
    if text.lstrip()[:1] == "<":
        raise FetchError("served_html", "mof feio")
    year = month = None
    ops: list[tuple[date, float]] = []
    quarters: set[tuple[int, int]] = set()
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row] + [""] * 9
        head = cells[0]
        if "期計" in head or re.search(r"[A-Za-z]+\s*-\s*[A-Za-z]+\s+\d{4}", cells[3]):
            m = re.search(r"([A-Za-z]+)\s*-\s*([A-Za-z]+)\s+(\d{4})", cells[3])
            mon = _MONTHS.get((m[2] if m else "")[:3].lower())
            if m and mon:
                quarters.add((int(m[3]), (mon - 1) // 3 + 1))
            continue
        if cells[3].isdigit() and len(cells[3]) == 4:
            year = int(cells[3])
        if cells[4][:3].lower() in _MONTHS:
            month = _MONTHS[cells[4][:3].lower()]
        amount = _num_or_none(cells[6])
        if not cells[5].isdigit() or amount is None or year is None or month is None:
            continue
        pair = cells[8].lower()
        if "japanese yen (bought)" in pair:
            sign = 1.0
        elif "japanese yen (sold)" in pair:
            sign = -1.0
        else:
            continue                      # a non-yen operation: not this series' quantity
        try:
            ops.append((date(year, month, int(cells[5])), sign * amount))
        except ValueError:
            continue
    rows: list[dict[str, Any]] = []
    by_q: dict[tuple[int, int], float] = defaultdict(float)
    for d, v in ops:
        q = _quarter_of_date(d)
        by_q[q] += v
        quarters.add(q)
        rows.append({"series_code": "yen_bought_100m_jpy", "period": d.isoformat(),
                     "value": v, "freq": "event",
                     "available_utc": mof_feio_release(*q).isoformat()})
    for (y, qn) in sorted(quarters):
        rows.append({"series_code": "qtr_net_yen_bought_100m_jpy", "period": f"{y}-Q{qn}",
                     "value": by_q.get((y, qn), 0.0), "freq": "quarterly",
                     "available_utc": mof_feio_release(y, qn).isoformat()})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value", "freq", "available_utc"])
    if df.empty:
        raise FetchError("empty", "mof feio")
    return df


_RECORD_WRAPPERS = ("elements", "records", "data", "result", "results", "items", "rows",
                    "value", "observations")
_DATE_FIELDS = ("end_of_day", "end_of_week", "end_of_month", "end_of_period", "date", "Date",
                "period", "periode", "obs_date", "as_of", "month", "week")


def _record_lists(doc: Any, depth: int = 0) -> list[list[dict[str, Any]]]:
    """Every list of row dicts inside a JSON document, outermost first (wrappers vary)."""
    out: list[list[dict[str, Any]]] = []
    if depth > 4:
        return out
    if isinstance(doc, list):
        rows = [r for r in doc if isinstance(r, dict)]
        if rows:
            out.append(rows)
        for x in doc:
            if isinstance(x, (list, dict)):
                out += _record_lists(x, depth + 1)
    elif isinstance(doc, dict):
        for k in _RECORD_WRAPPERS:
            if k in doc:
                out += _record_lists(doc[k], depth + 1)
    return out


def _records_of(doc: Any, date_fields: Iterable[str] = _DATE_FIELDS) -> list[dict[str, Any]]:
    """The first row list whose rows carry a date field (BPS puts a paging dict beside its rows),
    else the first row list found."""
    lists = _record_lists(doc)
    fields = tuple(date_fields)
    return next((rows for rows in lists if any(f in rows[0] for f in fields)),
                lists[0] if lists else [])


def _records_frame(raw: bytes, spec: dict[str, Any]) -> Any:
    """JSON rows (MAS API gateway, SAMA open data, BPS indicators): one date field per row and
    one series per numeric field (`value_fields` when the spec names them). A row's text values
    are never read as numbers."""
    import pandas as pd

    doc = json.loads(raw.decode("utf-8-sig", "replace"))
    dfields = tuple(spec.get("date_fields") or _DATE_FIELDS)
    recs = _records_of(doc, dfields)
    if not recs:
        raise FetchError("empty", spec.get("url", ""))
    dfield = next((f for f in dfields if f in recs[0]), None)
    if dfield is None:
        raise FetchError("no_date_column", spec.get("url", ""))
    want = spec.get("value_fields")
    code_field = spec.get("code_field")
    rows: list[dict[str, Any]] = []
    for r in recs:
        stamp = pd.to_datetime(str(r.get(dfield) or "").strip(), errors="coerce", utc=True,
                               format="mixed")
        if pd.isna(stamp):
            continue
        per = stamp.strftime("%Y-%m-%d") if spec.get("freq") != "monthly" else stamp.strftime(
            "%Y-%m")
        fields = want or [k for k in r if k != dfield and k != code_field]
        for f in fields:
            v = _num_or_none(r.get(f))
            if v is None:
                continue
            code = _slug(f"{r.get(code_field)}_{f}") if code_field else _slug(f)
            rows.append({"series_code": code, "period": per, "value": v})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("empty", spec.get("url", ""))
    return df


def _boj_survey_period(s: str) -> str | None:
    s = str(s or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if re.fullmatch(r"\d{6}", s):
        return f"{s[:4]}-{s[4:]}"
    if m := re.fullmatch(r"(\d{4})0?([1-4])", s):
        return f"{m[1]}-Q{m[2]}"
    return None


def _boj_api_frame(raw: bytes) -> Any:
    """BOJ Time-Series Data Search API `getDataCode` (format=json): per series SERIES_CODE,
    FREQUENCY, SURVEY_DATES and VALUES; a missing value is null and is absent, never zero."""
    import pandas as pd

    doc = json.loads(raw.decode("utf-8-sig", "replace"))
    found: list[dict[str, Any]] = []

    def walk(x: Any, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(x, dict):
            if "SERIES_CODE" in x and "VALUES" in x:
                found.append(x)
                return
            for v in x.values():
                walk(v, depth + 1)
        elif isinstance(x, list):
            for v in x:
                walk(v, depth + 1)

    walk(doc)
    rows: list[dict[str, Any]] = []
    for s in found:
        vals = s.get("VALUES")
        if isinstance(vals, dict):                         # {SURVEY_DATES: [...], VALUES: [...]}
            dates, values = vals.get("SURVEY_DATES") or [], vals.get("VALUES") or []
        else:
            dates, values = s.get("SURVEY_DATES") or [], vals or []
        for d, v in zip(dates, values, strict=False):
            per, f = _boj_survey_period(str(d)), _num_or_none(v)
            if per and f is not None:
                rows.append({"series_code": _slug(str(s["SERIES_CODE"])), "period": per,
                             "value": f})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("empty", "boj api")
    return df


_TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
_TD = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.I | re.S)


def _table_date(text: str) -> str | None:
    t = re.sub(r"\s+", " ", text).strip()
    if m := re.fullmatch(r"(\d{1,2})[ -]([A-Za-z]+)[ -](\d{4})", t):
        mon = _MONTHS.get(m[2].lower()) or _MONTHS.get(m[2][:3].lower())
        if mon:
            return f"{int(m[3]):04d}-{mon:02d}-{int(m[1]):02d}"
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t):
        return t
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t):          # BI prints d/m/yyyy
        return f"{int(m[3]):04d}-{int(m[2]):02d}-{int(m[1]):02d}"
    return None


def _bi_table_frame(raw: bytes, spec: dict[str, Any]) -> Any:
    """Bank Indonesia statistic tables (JISDOR, BI-Rate, reserve assets): an HTML table whose
    rows carry a date cell and a number cell ("16,250.00", "4.75 %"). The first date cell and the
    first separator-marked number make an observation."""
    import pandas as pd

    html = _decode_any(raw)
    rows: list[dict[str, Any]] = []
    for tr in _TR.findall(html):
        cells = [re.sub(r"<[^>]+>", " ", c) for c in _TD.findall(tr)]
        per = next((p for p in (_table_date(c) for c in cells) if p), None)
        if not per:
            continue
        # a bare integer cell is the table's row counter ("No"); a published value carries a
        # decimal or thousands separator or a % sign, so it wins when the row has one
        texts = [c.strip() for c in cells if not _table_date(c)]
        marked = [c for c in texts if re.search(r"[.,%]", c)]
        nums = [_num_or_none(c.replace("%", "").strip()) for c in (marked or texts)]
        v = next((x for x in nums if x is not None), None)
        if v is not None:
            rows.append({"series_code": str(spec.get("series_code") or "value"),
                         "period": per, "value": v})
    df = pd.DataFrame(rows, columns=["series_code", "period", "value"])
    if df.empty:
        raise FetchError("empty", spec.get("url", ""))
    return df.drop_duplicates(["series_code", "period"], keep="first")


#: mode -> parser(raw, spec). The pack doors dispatch here before `frame_from_payload`, whose
#: HTML refusal would otherwise reject the Bank Indonesia tables.
PACK_PARSERS: dict[str, Callable[[bytes, dict[str, Any]], Any]] = {
    "mof_feio_csv": lambda raw, spec: _mof_feio_frame(raw),
    "records_json": _records_frame,
    "boj_api_json": lambda raw, spec: _boj_api_frame(raw),
    "bi_table_html": _bi_table_frame,
}


def _sama_doors() -> list[dict[str, Any]]:
    """SAMA's doors are read from the Saudi data plane's own catalogue (one declaration of each
    URL, never restated). Unreadable -> no door, and the pack says so."""
    try:
        try:
            from research.countries.sa.data_plane import SamaLane
        except ImportError:
            from countries.sa.data_plane import (  # type: ignore[import-not-found,no-redef]
                SamaLane,
            )
    except Exception:
        return []
    want = {"saibor_daily": "daily", "sama_net_foreign_assets": "monthly",
            "sama_money_weekly": "weekly", "sama_monetary_monthly": "monthly"}
    out = []
    for row in SamaLane.CATALOGUE:
        if row.dataset_id in want and row.url:
            out.append({"dataset": row.dataset_id, "name": f"SAMA {row.coverage}",
                        "mode": "records_json", "freq": want[row.dataset_id],
                        "lag_days": max(1, math.ceil(row.publication_lag_days)),
                        "url": row.url})
    return out


#: pack -> country, the instruments it is FOR (named by the brief; checked against the broker's
#: registry each pass, so an absent one is reported unmapped, never invented), the register rows,
#: and its doors. `pin` = the door informs exactly the named instruments the registry holds.
COUNTRY_PACKS: dict[str, dict[str, Any]] = {
    "indonesia": {
        "country": "ID", "instruments": ["USDIDR"], "currencies": ["IDR"],
        "policy_rows": ["id_bank_indonesia", "id_bps_webapi"],
        "doors": [
            {"dataset": "BI_JISDOR", "name": "Bank Indonesia JISDOR USD/IDR reference rate",
             "mode": "bi_table_html", "series_code": "jisdor_idr_per_usd", "freq": "daily",
             "lag_days": 1,
             "url": "https://www.bi.go.id/en/statistik/informasi-kurs/jisdor/default.aspx"},
            {"dataset": "BI_RATE", "name": "Bank Indonesia BI-Rate policy rate decisions",
             "mode": "bi_table_html", "series_code": "bi_rate_pct", "freq": "monthly",
             "lag_days": 1,
             "url": "https://www.bi.go.id/en/fungsi-utama/moneter/bi-rate/default.aspx"},
            {"dataset": "BI_RESERVES", "name": "Bank Indonesia official reserve assets",
             "mode": "bi_table_html", "series_code": "reserve_assets_usd_bn", "freq": "monthly",
             "lag_days": 10, "url": "https://www.bi.go.id/en/statistik/indikator/default.aspx"},
            {"dataset": "BPS_INDICATORS", "name": "BPS Indonesia strategic indicators",
             "mode": "records_json", "freq": "monthly", "lag_days": 2,
             "date_fields": ["periode", "period"], "code_field": "title",
             "value_fields": ["value"], "key_env": "BPS_API_KEY",
             "url": ("https://webapi.bps.go.id/v1/api/list/model/indicators/lang/eng/domain/"
                     "0000/key/{api_key}/")}]},
    "singapore": {
        "country": "SG", "instruments": ["USDSGD"], "currencies": ["SGD"],
        "policy_rows": ["sg_mas_api"],
        "doors": [
            {"dataset": "MAS_DOMESTIC_RATES_DAILY",
             "name": "MAS SORA and domestic interest rates (daily)", "mode": "records_json",
             "freq": "daily", "lag_days": 1, "date_fields": ["end_of_day"],
             "key_env": "MAS_API_KEY", "key_header": "KeyId",
             "url": _MAS_GW + "domestic_interest_rates_daily/views/domestic_interest_rates_daily"},
            {"dataset": "MAS_FX_DAILY",
             "name": "MAS SGD exchange rates, end of period (the S$NEER basket's legs)",
             "mode": "records_json", "freq": "daily", "lag_days": 1,
             "date_fields": ["end_of_day"], "key_env": "MAS_API_KEY", "key_header": "KeyId",
             "url": (_MAS_GW + "exchange_rates_end_of_period_daily/views/"
                     "exchange_rates_end_of_period_daily")},
            {"dataset": "MAS_RESERVES_MONTHLY", "name": "MAS official foreign reserves",
             "mode": "records_json", "freq": "monthly", "lag_days": 8,
             "date_fields": ["end_of_month"], "key_env": "MAS_API_KEY", "key_header": "KeyId",
             "url": _MAS_GW + "official_foreign_reserves/views/official_foreign_reserves"}]},
    "saudi_arabia": {
        "country": "SA", "instruments": ["USDSAR", "XBRUSD", "XTIUSD"], "currencies": [],
        "pin": True, "policy_rows": ["sa_sama"], "doors": "sama_data_plane"},
    "japan": {
        "country": "JP", "instruments": ["USDJPY", "JPN225"], "currencies": ["JPY"],
        "pin": True, "policy_rows": ["jp_mof_feio", "jp_boj_stat_search", "jp_jquants"],
        "doors": [
            {"dataset": "MOF_FEIO", "name": "Japan MoF foreign exchange intervention operations",
             "mode": "mof_feio_csv", "url": _MOF_FEIO_CSV},
            {"dataset": "BOJ_FM01_CALL", "name": "BOJ uncollateralized overnight call rate",
             "mode": "boj_api_json", "freq": "daily", "lag_days": 1,
             "url": _BOJ_API + "format=json&lang=en&db=FM01&code=STRDCLUCON"},
            {"dataset": "BOJ_MD01_BASE", "name": "BOJ monetary base (average outstanding)",
             "mode": "boj_api_json", "freq": "monthly", "lag_days": 3,
             "url": _BOJ_API + "format=json&lang=en&db=MD01&code=MABS1AN11"}]},
    "china": {
        "country": "CN", "instruments": ["XAUUSD", "XAGUSD", "XCUUSD", "XALUSD", "XZNUSD",
                                         "XNIUSD", "XPBUSD", "XBRUSD", "XTIUSD", "SOYBEAN",
                                         "CORN", "COTTON", "SUGAR", "AUDUSD", "USDCNH"],
        "currencies": [], "policy_rows": ["cnx_shfe", "cnx_dce", "cnx_czce"],
        "organ": "libs/data/free_stack_cnx.py (free_stack_hunter, roster rows cnx_*)",
        "doors": []},
}


def _pack_doors(pack: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    doors = _sama_doors() if p.get("doors") == "sama_data_plane" else list(p.get("doors") or [])
    out = []
    for d in doors:
        out.append({**d, "provider": f"PACK_{p['country']}", "pack": pack,
                    "currencies": list(p.get("currencies") or []),
                    "pin": list(p["instruments"]) if p.get("pin") else None})
    return out


def country_pack_doors() -> list[dict[str, Any]]:
    return [d for pack, p in COUNTRY_PACKS.items() for d in _pack_doors(pack, p)]


def pack_terms_hold(spec: dict[str, Any]) -> str | None:
    """The register row that refuses this door as LIVE INPUT (IDEAS_ONLY or held), else None.
    The URL is judged with its placeholders in, so no key is ever handed to the check."""
    from libs.data import terms_fence as _tf
    return _tf.input_source(spec["url"])


def _pack_empty_run(row: dict[str, Any], reason: str) -> None:
    """An attempt that landed nothing. A missing key is its own state (NEEDS_KEY), not an empty
    run: the door was never asked."""
    if reason == "needs_key":
        row["pack_state"] = "NEEDS_KEY"
        return
    row["pack_state"] = "EMPTY"
    row["empty_streak"] = int(row.get("empty_streak") or 0) + 1


def _door_state(row: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any]:
    from libs.data import terms_fence as _tf
    held = pack_terms_hold(spec)
    key_env = str(spec.get("key_env") or "")
    out: dict[str, Any] = {"dataset": spec["dataset"], "url": spec["url"],
                           "policy_row": held or _tf.source_of_url(spec["url"]),
                           "empty_streak": int((row or {}).get("empty_streak") or 0),
                           "last_attempt_at": (row or {}).get("last_attempt_at") or UNMEASURED,
                           "fetched_at": (row or {}).get("fetched_at") or UNMEASURED,
                           "fail_reason": (row or {}).get("fail_reason")}
    if key_env:
        out["key"] = key_env if os.environ.get(key_env) else f"NEEDS_KEY:{key_env}"
    if held:
        out["state"] = "IDEAS_ONLY"
        out["missed_growth"] = _tf.held_missed_growth(
            held, source=f"{spec['provider']}/{spec['dataset']}", live_input_refusal=True)
    elif key_env and not os.environ.get(key_env):
        out["state"] = "NEEDS_KEY"
    elif out["empty_streak"] > PACK_EMPTY_RED_RUNS:
        out["state"] = "RED"
        out["why"] = (f"{out['empty_streak']} consecutive attempts landed nothing "
                      f"(last: {out['fail_reason']}); RED above {PACK_EMPTY_RED_RUNS}")
    elif (row or {}).get("pack_state") == "FETCHED":
        out["state"] = "GREEN"
    elif out["empty_streak"]:
        out["state"] = "AMBER"
    else:
        out["state"] = UNMEASURED                       # never attempted on this host
    return out


def country_pack_report(cat: dict[str, Any]) -> dict[str, Any]:
    """Per pack: each door's liveness and terms state, the named instruments the registry holds
    (and those it does not: unmapped, recorded), the series that reach research, and a verdict.
    RED > GREEN (every live door landing) > AMBER > HELD (no live door: ideas only / no key) >
    UNMEASURED (nothing attempted here)."""
    from libs.data import terms_fence as _tf
    uni = {sym for sym, _, _ in hypothesis_universe()}
    rows_by_key = cat.get("datasets") or {}
    packs: dict[str, Any] = {}
    for pack, p in COUNTRY_PACKS.items():
        doors = [_door_state(rows_by_key.get(f"{d['provider']}/{d['dataset']}"), d)
                 for d in _pack_doors(pack, p)]
        states = Counter(d["state"] for d in doors)
        live = [d for d in doors if d["state"] not in ("IDEAS_ONLY", "NEEDS_KEY")]
        if states.get("RED"):
            verdict = "RED"
        elif live and all(d["state"] == "GREEN" for d in live):
            verdict = "GREEN"
        elif any(d["state"] in ("GREEN", "AMBER") for d in live):
            verdict = "AMBER"
        elif not live and doors:
            verdict = "HELD"
        else:
            verdict = UNMEASURED
        series: list[str] = []
        declared = p.get("doors")
        for d in declared if isinstance(declared, list) else []:
            meta = _read_json(meta_path(f"PACK_{p['country']}", d["dataset"]), {}) or {}
            series += [s["key"] for s in (meta.get("series") or {}).values()
                       if s.get("quality") == "PASS" and s.get("instruments")]
        policy = {}
        for k in p.get("policy_rows") or []:
            row = _tf.SOURCE_POLICY.get(k) or {}
            policy[k] = {"status": _tf.live_input_status(k) if row else UNMEASURED,
                         "terms": _tf.terms_state(k) if row else UNMEASURED,
                         "terms_url": (row.get("terms") or {}).get("url")}
            if row and (row.get("status") == _tf.IDEAS_ONLY or row.get("held_route")):
                policy[k]["missed_growth"] = _tf.held_missed_growth(
                    k, source=f"country_pack:{pack}", live_input_refusal=True)
        entry: dict[str, Any] = {
            "country": p["country"], "verdict": verdict, "doors": doors,
            "door_states": dict(states), "policy": policy,
            "instruments_named": list(p["instruments"]),
            "instruments_mapped": sorted(s for s in p["instruments"] if s in uni),
            "unmapped": sorted(s for s in p["instruments"] if s not in uni),
            "series_to_research": series if series else UNMEASURED}
        if p.get("organ"):
            entry["organ"] = p["organ"]
            entry["verdict"] = ("HELD" if all(v["status"] == _tf.IDEAS_ONLY
                                              for v in policy.values()) else UNMEASURED)
        if p.get("doors") == "sama_data_plane" and not doors:
            entry["verdict"] = UNMEASURED
            entry["why"] = "the Saudi data plane's catalogue could not be read on this host"
        packs[pack] = entry
    red = [f"{pk}/{d['dataset']}" for pk, e in packs.items() for d in e["doors"]
           if d["state"] == "RED"]
    return {"packs": packs, "red_doors": red, "red_after_empty_runs": PACK_EMPTY_RED_RUNS,
            "status": (f"RED: country-pack doors empty > {PACK_EMPTY_RED_RUNS} runs: "
                       + ", ".join(red)) if red else "OK"}


def _fred_ids() -> list[str]:
    ids: set[str] = set()
    reg = _read_json(REGISTRY, {})
    row = ((reg or {}).get("datasets") or {}).get("fred_macro") or {}
    ids.update(str(s) for s in (row.get("series") or []) if s)
    try:
        from research.free_data import FRED_FIELDS
        ids.update(FRED_FIELDS)
    except Exception:
        pass
    return sorted(i for i in ids if re.fullmatch(r"[A-Za-z0-9_]+", i))


#: The ten registry rows that sat DISCOVERED, each with the door this organ tries every day.
#: `search` seeds the DBnomics frontier with datasets that answer the same need.
LEGACY_PROBES: dict[str, dict[str, Any]] = {
    "bis_eer": {"direct": "WS_EER", "search": "effective exchange rate"},
    "spdr_gld_holdings": {"url": "https://www.spdrgoldshares.com/assets/dynamic/GLD/"
                                 "GLD_US_archive_EN.csv", "mode": "csv", "stems": ["XAU"],
                          "freq": "daily", "search": "gold reserves"},
    "sge_benchmark": {"url": "https://en.sge.com.cn/data_BenchmarkPrice", "mode": "csv",
                      "stems": ["XAU"], "search": "gold price"},
    "shfe_gold": {"url": "https://www.shfe.com.cn/data/dailydata/kx/kx{bday}.dat",
                  "mode": "json_records", "stems": ["XAU"], "search": "China gold"},
    "lbma_vaults": {"url": "https://prices.lbma.org.uk/json/gold_pm.json", "mode": "lbma_json",
                    "stems": ["XAU"], "freq": "daily", "search": "gold holdings"},
    "swiss_customs_gold": {"search": "Switzerland exports gold"},
    "wgc_goldhub": {"url": "https://www.gold.org/goldhub/data/gold-prices", "mode": "csv",
                    "stems": ["XAU"], "search": "gold demand"},
    "cme_gc": {"url": "https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/437/G", "mode": "csv",
               "stems": ["XAU"], "search": "gold futures"},
    "eur_cot_blocked": {"direct": "TFF_EURO_FX", "search": "euro exchange rate"},
    "gdelt": {"url": ("https://api.gdeltproject.org/api/v2/doc/doc?query=%22gold%20price%22"
                      "&mode=timelinevol&format=json&timespan=12m"),
              "mode": "gdelt_timeline", "stems": ["XAU"], "freq": "daily",
              "search": "news media"},
}


def _lbma_frame(raw: bytes) -> Any:
    import pandas as pd
    doc = json.loads(raw.decode("utf-8", "replace"))
    rows = [{"series_code": "gold_pm_usd", "period": r.get("d"),
             "value": (r.get("v") or [None])[0]} for r in doc if isinstance(r, dict)]
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value", "period"])


# ------------------------------------------------------------------------------- the pass ----
def _blank_catalog() -> dict[str, Any]:
    return {"schema": 1, "providers": {}, "datasets": {}, "legacy": {}, "providers_listed_at": None}


def load_catalog() -> dict[str, Any]:
    cat = _read_json(CATALOG, None)
    if not isinstance(cat, dict):
        return _blank_catalog()
    for k, v in _blank_catalog().items():
        cat.setdefault(k, v)
    return cat


def _rank(lifecycle: str) -> int:
    return LIFECYCLE.index(lifecycle) if lifecycle in LIFECYCLE else 0


def _promote(row: dict[str, Any], to: str) -> None:
    if _rank(to) > _rank(str(row.get("lifecycle") or "DISCOVERED")):
        row["lifecycle"] = to


def discover(client: Client, cat: dict[str, Any], *, now: datetime, until: float,
             stats: Counter[str]) -> None:
    """Providers daily; each provider's dataset catalogue paged to the end, relisted weekly."""
    listed = _parse_iso(cat.get("providers_listed_at"))
    if listed is None or (now - listed).total_seconds() > PROVIDERS_REFRESH_H * 3600:
        try:
            doc = client.get_json(f"{DBNOMICS}/providers?limit=1000")
            for p in ((doc.get("providers") or {}).get("docs") or []):
                code = str(p.get("code") or "")
                if not code:
                    continue
                row = cat["providers"].setdefault(code, {"datasets_offset": 0,
                                                         "discovered_at": _iso(now)})
                row.update({"name": p.get("name"), "region": p.get("region"),
                            "website": p.get("website")})
            cat["providers_listed_at"] = _iso(now)
            stats["provider_list_ok"] += 1
        except FetchError as exc:
            stats[f"providers:{exc.reason}"] += 1
    order = sorted(cat["providers"].items(),
                   key=lambda kv: (-PROVIDER_WEIGHT.get(kv[0], 1.0), kv[0]))
    for code, prow in order:
        if time.monotonic() >= until:
            break
        total = prow.get("datasets_total")
        done_at = _parse_iso(prow.get("listed_at"))
        complete = total is not None and int(prow.get("datasets_offset") or 0) >= int(total)
        if complete and done_at and (now - done_at).days < DATASETS_RELIST_D:
            continue
        if complete:
            prow["datasets_offset"] = 0
        while time.monotonic() < until:
            off = int(prow.get("datasets_offset") or 0)
            url = (f"{DBNOMICS}/datasets/{urllib.parse.quote(code)}?"
                   f"limit={DATASETS_PAGE}&offset={off}")
            try:
                doc = client.get_json(url)
            except FetchError as exc:
                prow["last_error"] = exc.reason
                stats[f"datasets:{exc.reason}"] += 1
                break
            block = doc.get("datasets") or {}
            docs = block.get("docs") or []
            prow["datasets_total"] = int(block.get("num_found") or len(docs) + off)
            for d in docs:
                dcode = str(d.get("code") or "")
                if not dcode:
                    continue
                key = f"{code}/{dcode}"
                row = cat["datasets"].get(key)
                if row is None:
                    row = cat["datasets"][key] = {"provider": code, "code": dcode,
                                                  "lifecycle": "DISCOVERED",
                                                  "discovered_at": _iso(now),
                                                  "series_offset": 0, "source": "dbnomics"}
                    stats["datasets_new"] += 1
                row["name"] = str(d.get("name") or dcode)[:200]
                row["nb_series"] = d.get("nb_series")
                row["score"] = dataset_score(code, row["name"])
            prow["datasets_offset"] = off + len(docs)
            if not docs or prow["datasets_offset"] >= prow["datasets_total"]:
                prow["listed_at"] = _iso(now)
                break


def _due(row: dict[str, Any], now: datetime) -> bool:
    nxt = _parse_iso(row.get("next_due"))
    return nxt is None or nxt <= now


#: One seat in this many of the never-fetched tier goes to a dataset that could answer an
#: UNMEASURED regional-parity cell (`regional_parity_pass` writes the targets). A SHARE, not a
#: queue jump: the pass fetches exactly as many datasets as before, the refresh tier is untouched,
#: and an unused share flows straight back to the relevance order.
PARITY_EVERY = 4


def _parity_matchers() -> list[tuple[re.Pattern[str], tuple[str, ...]]]:
    """(class terms, country names) for every class with UNMEASURED cells; [] when absent."""
    doc = _read_json(DESK / "data" / "parity_hunt_targets.json", None)
    out: list[tuple[re.Pattern[str], tuple[str, ...]]] = []
    for spec in dict((doc or {}).get("classes") or {}).values() if isinstance(doc, dict) else ():
        try:
            rx = re.compile(str(spec.get("terms") or ""), re.IGNORECASE)
        except (re.error, AttributeError):
            continue
        names = tuple(str(n).lower() for n in spec.get("country_names") or () if str(n).strip())
        if rx.pattern and names:
            out.append((rx, names))
    return out


def _parity_match(name: str, where: str, matchers: list[tuple[re.Pattern[str], tuple[str, ...]]]
                  ) -> bool:
    """A dataset answers a parity target when its NAME matches the class and its name, provider
    or provider region names a country still unmeasured on that class."""
    low = f"{name} {where}".lower()
    return any(rx.search(name) and any(n in low for n in names) for rx, names in matchers)


def _fetch_order(cat: dict[str, Any], now: datetime) -> list[str]:
    """Never-fetched first, then due-for-refresh; within each, highest MT5 relevance first --
    with one seat in PARITY_EVERY of the never-fetched tier reserved for regional parity."""
    rows = []
    for key, row in cat["datasets"].items():
        if row.get("source") != "dbnomics" or not _due(row, now):
            continue
        fails = int(row.get("fail_count") or 0)
        rows.append((0 if not row.get("fetched_at") else 1, fails,
                     -float(row.get("score") or 0.0), key))
    rows.sort()
    order = [r[-1] for r in rows]
    matchers = _parity_matchers()
    if not matchers:
        return order
    fresh = [k for k in order if not cat["datasets"][k].get("fetched_at")]
    rest = order[len(fresh):]
    providers = cat.get("providers") or {}

    def where(k: str) -> str:
        p = providers.get(str(cat["datasets"][k].get("provider") or "")) or {}
        return f"{p.get('name') or ''} {p.get('region') or ''}"

    lane = [k for k in fresh
            if _parity_match(str(cat["datasets"][k].get("name") or ""), where(k), matchers)]
    if not lane:
        return order
    picked = set(lane)
    others = deque(k for k in fresh if k not in picked)
    queue = deque(lane)
    merged: list[str] = []
    while queue or others:
        if queue and (len(merged) % PARITY_EVERY == PARITY_EVERY - 1 or not others):
            merged.append(queue.popleft())
        else:
            merged.append(others.popleft())
    return merged + rest


def _load_frame(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        import pandas as pd
        return pd.read_parquet(path)
    except Exception:
        return None


def ingest_series(provider: str, dataset: str, dname: str, series: list[dict[str, Any]], *,
                  now: datetime, base_score: float, declared_lag: int | None = None,
                  hint_ccys: Iterable[str] = (), hint_stems: Iterable[str] = (),
                  qstats: Counter[str],
                  pin_instruments: Iterable[str] | None = None) -> dict[str, Any]:
    """Quality-check, PIT-merge and describe one batch of series from one dataset.

    `pin_instruments` (a country pack's named instruments) replaces the inferred mapping: only
    the named symbols the broker registry holds in the hypothesis lane are informed."""
    pinned = None if pin_instruments is None else {str(x) for x in pin_instruments}
    path = dataset_path(provider, dataset)
    frame, added = merge_observations(_load_frame(path), series, now=now,
                                      declared_lag=declared_lag)
    if added:
        _write_parquet(frame, path)
    mpath = meta_path(provider, dataset)
    meta = _read_json(mpath, {}) or {}
    meta.setdefault("series", {})
    meta.update({"provider": provider, "dataset": dataset, "name": dname,
                 "path": _rel(path), "updated_at": _iso(now)})
    passed = 0
    for s in series:
        ok, reason, freq = quality(s["points"], s.get("freq") or "", now=now)
        qstats[reason] += 1
        if "stems" in s:
            # the parser named this series' instruments itself: nothing else is inferred
            ccys = sorted({c.upper() for c in hint_ccys})
            stems = sorted({x.upper() for x in s["stems"] if x})
        else:
            mapping = map_series(f"{s.get('name', '')} {dname}", s.get("dims"))
            ccys = sorted(set(mapping["currencies"]) | {c.upper() for c in hint_ccys})
            stems = sorted(set(mapping["stems"]) | {x.upper() for x in hint_stems if x})
        insts = instruments_for(ccys, stems) if (ccys or stems) else []
        if pinned is not None:
            insts = sorted(sym for sym, _, _ in hypothesis_universe() if sym in pinned)
        fb = FREQ_RULES.get(freq, (0, 0, 0.0))[2]
        score = round(base_score + fb + (2.0 if ccys else 0.0) + (3.0 if stems else 0.0), 3)
        ends = [period_end(p, freq)[0] for p, _ in s["points"]]
        ends = [e for e in ends if e]
        meta["series"][s["code"]] = {
            "key": series_key(provider, dataset, s["code"]), "name": str(s.get("name"))[:160],
            "freq": freq, "n": len(s["points"]), "first": str(min(ends)) if ends else None,
            "last": str(max(ends)) if ends else None, "quality": "PASS" if ok else reason,
            "currencies": ccys, "stems": stems, "instruments": insts, "score": score,
            "checked_at": _iso(now)}
        passed += int(ok)
    write_json(mpath, meta, indent=None)
    return {"rows_added": added, "series": len(series), "passed": passed,
            "rows_total": 0 if frame is None else len(frame)}


def fetch_dbnomics(client: Client, cat: dict[str, Any], *, now: datetime, until: float,
                   stats: Counter[str], qstats: Counter[str],
                   by_provider: dict[str, Counter[str]]) -> None:
    for key in _fetch_order(cat, now):
        if time.monotonic() >= until or client.remaining() < 5:
            break
        row = cat["datasets"][key]
        prov, code = row["provider"], row["code"]
        off = int(row.get("series_offset") or 0)
        url = (f"{DBNOMICS}/series/{urllib.parse.quote(prov)}/{urllib.parse.quote(code)}?"
               f"observations=1&limit={SERIES_PAGE}&offset={off}")
        row["attempted_at"] = _iso(now)
        try:
            doc = client.get_json(url)
        except FetchError as exc:
            if exc.reason == "budget_exhausted":
                break
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = exc.reason
            row["next_due"] = _iso(now + timedelta(hours=6 * row["fail_count"]))
            stats[f"series:{exc.reason}"] += 1
            by_provider[prov]["failed"] += 1
            continue
        block = doc.get("series") or {}
        total = int(block.get("num_found") or 0)
        series = observations_from_dbnomics(doc)
        if not series:
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = "empty"
            row["next_due"] = _iso(now + timedelta(days=7))
            stats["series:empty"] += 1
            continue
        res = ingest_series(prov, code, str(row.get("name") or code), series, now=now,
                            base_score=float(row.get("score") or 0.0), qstats=qstats)
        row.update({"fetched_at": _iso(now), "fail_count": 0, "fail_reason": None,
                    "series_total": total,
                    "series_seen": int(row.get("series_seen") or 0) + len(series),
                    "series_passed": int(row.get("series_passed") or 0) + res["passed"],
                    "rows": res["rows_total"],
                    "path": _rel(dataset_path(prov, code))})
        _promote(row, "INGESTED")
        if res["passed"]:
            _promote(row, "QUALITY-PASSED")
        nxt = off + len(series)
        if nxt >= total:
            # A FULL SWEEP OF THE DATASET CLOSED: publish its counts, restart the cursor.
            row["last_sweep"] = {"at": _iso(now), "series": row["series_seen"],
                                 "passed": row["series_passed"]}
            row["series_offset"] = 0
            row["series_seen"] = 0
            row["series_passed"] = 0
            freq = series[0].get("freq") or ""
            row["next_due"] = _iso(now + (timedelta(days=1) if freq in ("daily", "business")
                                          else timedelta(days=7)))
        else:
            row["series_offset"] = nxt
            row["next_due"] = None
        stats["datasets_fetched"] += 1
        stats["rows_appended"] += res["rows_added"]
        by_provider[prov]["fetched"] += 1
        by_provider[prov]["rows"] += res["rows_added"]


def _fetch_direct(client: Client, spec: dict[str, Any], now: datetime, *,
                  backfill: bool = False, misses: Counter[str] | None = None
                  ) -> list[dict[str, Any]]:
    """One direct door. A spec with `urls` reads several payloads into ONE dataset (export sales
    by market year, WASDE by month), adding `urls_backfill` while `backfill` is set; a payload
    that fails is counted in `misses` by reason and the others still land, and only when every
    payload fails does the door fail (with the first reason)."""
    key_env = str(spec.get("key_env") or "")
    key = ""
    headers: dict[str, str] | None = None
    if key_env:
        key = os.environ.get(key_env) or ""
        if not key:
            raise FetchError("needs_key", key_env)        # named, never a silent skip or a zero
        # THE KEY IS REGISTERED WITH THE ACCESS LEDGER'S REDACTOR before any request: a 401/403
        # on a keyed door (BPS puts it in the PATH, `/key/<key>/`) holds the site with the
        # URL redacted, never with the key (audit HOLD on 4ac92d8316).
        from libs.data import polite_fetch as _pf
        _pf.register_secret(key)
        if spec.get("key_header"):
            headers = {str(spec["key_header"]): key}      # travels in the header, never the URL
    parts = list(spec.get("urls") or [{"url": spec["url"]}])
    if backfill:
        parts = list(spec.get("urls_backfill") or []) + parts
    mode = spec.get("mode", "csv")
    frames = []
    first: FetchError | None = None
    for part in parts:
        url = str(part["url"]).replace("{bday}", _last_business_day(now))
        if key_env:
            url = url.replace("{api_key}", urllib.parse.quote(key, safe=""))
        try:
            raw = client.get(url, headers) if headers else client.get(url)
            # the parser sees the TEMPLATE url: a key never rides into an error's detail
            sub = {**spec, **part, "url": str(part["url"])}
            if mode in PACK_PARSERS:
                df = PACK_PARSERS[mode](raw, sub)
            elif mode == "lbma_json":
                df = _lbma_frame(raw)
            else:
                df = frame_from_payload(raw, mode, sub)
        except FetchError as exc:
            if key:
                # a stored or logged failure names the door's TEMPLATE (`{key}`), never the key
                exc = FetchError(exc.reason, url_template(exc.detail, key))
            if exc.reason == "budget_exhausted" or len(parts) == 1:
                raise exc from None
            first = first or exc
            if misses is not None:
                misses[exc.reason] += 1
            continue
        if df is not None and len(df):
            frames.append(df)
    if not frames:
        if first is not None:
            raise first
        raise FetchError("empty", spec["url"])
    import pandas as pd
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    if "market_year" in df.columns:
        # a week reported under two market years keeps the LATER market year's record
        df = (df.sort_values("market_year")
              .drop_duplicates(["series_code", "period"], keep="last"))
    elif len(frames) > 1:
        df = df.drop_duplicates(["series_code", "period"], keep="last")
    return series_from_long(df, freq=spec.get("freq", ""), hint=spec.get("name", ""))


def fetch_direct(client: Client, cat: dict[str, Any], *, now: datetime, until: float,
                 stats: Counter[str], qstats: Counter[str],
                 by_provider: dict[str, Counter[str]]) -> None:
    for spec in direct_sources(now):
        if time.monotonic() >= until:
            break
        key = f"{spec['provider']}/{spec['dataset']}"
        row = cat["datasets"].setdefault(key, {"provider": spec["provider"],
                                               "code": spec["dataset"], "lifecycle": "DISCOVERED",
                                               "discovered_at": _iso(now), "source": "direct"})
        row["name"] = spec.get("name")
        row["score"] = dataset_score(spec["provider"], spec.get("name", ""))
        if not _due(row, now):
            continue
        misses: Counter[str] = Counter()
        pack = spec.get("pack")
        if pack:
            row["pack"] = pack
            held = pack_terms_hold(spec)
            if held:
                # IDEAS_ONLY / held on the register: never requested as data. Not a failure and
                # not an empty run -- the hold is the state, and its missed growth is reported.
                row.update({"pack_state": "IDEAS_ONLY", "policy_row": held,
                            "fail_reason": "terms_ideas_only",
                            "next_due": _iso(now + timedelta(hours=DIRECT_REFRESH_H))})
                stats["direct:terms_ideas_only"] += 1
                continue
            row["last_attempt_at"] = _iso(now)
        try:
            series = _fetch_direct(client, spec, now, misses=misses,
                                   backfill=not int(row.get("rows") or 0))
        except FetchError as exc:
            if exc.reason == "budget_exhausted":
                break
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = exc.reason
            row["next_due"] = _iso(now + timedelta(hours=DIRECT_REFRESH_H))
            if pack:
                _pack_empty_run(row, exc.reason)
            stats[f"direct:{exc.reason}"] += 1
            by_provider[spec["provider"]]["failed"] += 1
            continue
        except Exception as exc:
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = f"parse:{type(exc).__name__}"
            row["next_due"] = _iso(now + timedelta(hours=DIRECT_REFRESH_H))
            if pack:
                _pack_empty_run(row, row["fail_reason"])
            stats[f"direct:parse:{type(exc).__name__}"] += 1
            continue
        res = ingest_series(spec["provider"], spec["dataset"], spec.get("name", ""), series,
                            now=now, base_score=row["score"], declared_lag=spec.get("lag_days"),
                            hint_ccys=spec.get("currencies", ()),
                            hint_stems=spec.get("stems", ()), qstats=qstats,
                            pin_instruments=spec.get("pin"))
        row["partial_misses"] = dict(misses) or None
        if pack:
            row.update({"pack_state": "FETCHED", "empty_streak": 0, "needs_key": None})
        row.update({"fetched_at": _iso(now), "fail_count": 0, "fail_reason": None,
                    "series_total": len(series), "series_passed": res["passed"],
                    "rows": res["rows_total"],
                    "next_due": _iso(now + timedelta(hours=DIRECT_REFRESH_H)),
                    "path": _rel(dataset_path(spec["provider"], spec["dataset"]))})
        _promote(row, "INGESTED")
        if res["passed"]:
            _promote(row, "QUALITY-PASSED")
        stats["datasets_fetched"] += 1
        stats["rows_appended"] += res["rows_added"]
        by_provider[spec["provider"]]["fetched"] += 1
        by_provider[spec["provider"]]["rows"] += res["rows_added"]


def _packs() -> Any:
    try:
        from research import country_packs as cp
    except ImportError:                                                       # pragma: no cover
        import country_packs as cp  # type: ignore[no-redef]
    return cp


def fetch_country_packs(client: Client, cat: dict[str, Any], *, now: datetime, until: float,
                        stats: Counter[str], qstats: Counter[str],
                        by_provider: dict[str, Counter[str]]) -> None:
    """THE COUNTRY OPEN-DATA PACKS (research/country_packs.py) as direct doors of this organ.

    Each door is gated on its terms_fence row BEFORE any request (HELD / NEEDS_KEY /
    NEEDS_CONFIG are recorded with their cause and never counted as a failure), fetched through
    this client (budgeted, terms-fenced, robots-checked by guarded_urlopen), PIT-stamped by its
    publisher's release instant and ingested like every other direct door. `empty_streak`
    counts consecutive attempts that delivered nothing; the pack liveness reads it."""
    cp = _packs()
    for door in cp.DOORS:
        if time.monotonic() >= until:
            break
        key = f"{door.provider}/{door.id}"
        row = cat["datasets"].setdefault(key, {"provider": door.provider, "code": door.id,
                                               "lifecycle": "DISCOVERED",
                                               "discovered_at": _iso(now), "source": "direct"})
        row.update({"name": door.name, "pack": door.pack, "policy": door.policy,
                    "score": dataset_score(door.provider, door.name) + 4.0})
        if not _due(row, now):
            continue
        held = cp.login_hold(row) or cp.gate(door)
        if held:
            row.update({"pack_state": held[0],
                        "fail_reason": ("login_required" if row.get("login_held_at")
                                        and not row.get("login_released_by") else held[1]),
                        "next_due": _iso(now + timedelta(hours=DIRECT_REFRESH_H))})
            stats[f"pack:{held[0]}"] += 1
            continue
        row["pack_state"] = "LIVE"
        first = not row.get("fetched_at")

        def _get(req: Any) -> bytes:
            return client.get(req.url, headers=req.headers or None, data=req.data)

        reason = None
        series: list[dict[str, Any]] = []
        try:
            series = cp.fetch_door(door, _get, now, first=first)
            if not series:
                reason = "empty"
        except cp.LoginRequired:
            reason = "login_required"
        except FetchError as exc:
            if exc.reason == "budget_exhausted":
                break
            reason = exc.reason
            if reason == "terms_fenced" and "login_wall" in str(exc.detail):
                reason = "login_required"                 # a redirect into a login wall
        except Exception as exc:
            reason = f"parse:{type(exc).__name__}"
        if reason == "login_required":
            # A LOGIN WALL IS A HARD STOP, HELD FOR A PERSON: never logged into, never retried
            # by a clock, never an empty run (so never RED). A person releases it by writing
            # `login_released_by` on this catalog row.
            from libs.data import polite_fetch as _pf
            row.update({"pack_state": "HELD", "fail_reason": "login_required",
                        "login_held_at": _iso(now), "login_released_by": None,
                        "missed_growth": _pf.hold_missed_growth(
                            door.provider, "LOGIN_REQUIRED", "login",
                            f"{door.id}: its page answered with a login wall"),
                        "next_due": _iso(now + timedelta(hours=DIRECT_REFRESH_H))})
            stats["pack:login_required"] += 1
            continue
        if reason:
            row["empty_streak"] = int(row.get("empty_streak") or 0) + 1
            row.setdefault("first_empty_at", _iso(now))
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = reason
            row["next_due"] = _iso(now + timedelta(hours=cp.RETRY_FAIL_H))
            stats[f"pack:{reason}"] += 1
            by_provider[door.provider]["failed"] += 1
            continue
        res = ingest_series(door.provider, door.id, door.name, series, now=now,
                            base_score=row["score"], hint_ccys=door.currencies,
                            hint_stems=door.stems, qstats=qstats)
        row.update({"fetched_at": _iso(now), "fail_count": 0, "fail_reason": None,
                    "empty_streak": 0, "first_empty_at": None,
                    "series_total": len(series), "series_passed": res["passed"],
                    "rows": res["rows_total"],
                    "next_due": _iso(now + timedelta(hours=cp.REFRESH_OK_H)),
                    "path": _rel(dataset_path(door.provider, door.id))})
        _promote(row, "INGESTED")
        if res["passed"]:
            _promote(row, "QUALITY-PASSED")
        stats["datasets_fetched"] += 1
        stats["pack:delivered"] += 1
        stats["rows_appended"] += res["rows_added"]
        by_provider[door.provider]["fetched"] += 1
        by_provider[door.provider]["rows"] += res["rows_added"]


def country_packs_eu_report(cat: dict[str, Any], now: datetime) -> dict[str, Any]:
    """research/country_packs.py's packs (tr / pl / se / za). Per pack: each door's state and
    mapped instruments, the unmapped local indices, the
    held rows' missed-growth lines and the liveness verdict (also written to its own file)."""
    cp = _packs()
    rows = {d.id: cat["datasets"].get(f"{d.provider}/{d.id}") or {} for d in cp.DOORS}
    uni = {sym for sym, _, _ in hypothesis_universe()}
    live = cp.liveness(rows, now)
    packs: dict[str, Any] = {}
    for k, p in cp.PACKS.items():
        doors = {}
        for d in (d for d in cp.DOORS if d.pack == k):
            r = rows[d.id]
            meta = _read_json(meta_path(d.provider, d.id), {}) or {}
            ser = meta.get("series") or {}
            doors[d.id] = {
                "verdict": live["dependencies"][d.id]["verdict"], "policy": d.policy,
                "state": r.get("pack_state") or UNMEASURED, "why": r.get("fail_reason"),
                "rows": r.get("rows") if r.get("fetched_at") else UNMEASURED,
                **({"missed_growth": r["missed_growth"]} if r.get("missed_growth")
                   and r.get("pack_state") == "HELD" else {}),
                **({"access": acc} if (acc := cp.access_of(d)) else {}),
                "series": {c: {"quality": v.get("quality"), "instruments": v.get("instruments"),
                               "key": v.get("key")} for c, v in ser.items()} or UNMEASURED,
                "instruments": (sorted({i for v in ser.values() for i in v.get("instruments")
                                        or ()}) if ser else instruments_for(d.currencies,
                                                                            d.stems)),
                "release_rule": d.what}
        packs[k] = {"country": p.country, "currency": p.currency, "publishers": p.publishers,
                    "verdict": live["sources"][k], "doors": doors,
                    "local_indices_mapped": cp.mapped_indices(uni)[k],
                    "local_indices_unmapped": cp.unmapped_indices(uni)[k],
                    "not_built": [{"series": a, "why": b} for a, b in p.not_built]}
    write_json(PACK_LIVENESS, live)
    return {"verdict": live["verdict"], "red": live["red"], "packs": packs,
            "missed_growth": cp.missed_growth_lines(),
            "liveness_artifact": _rel(PACK_LIVENESS)}


def attempt_legacy(client: Client, cat: dict[str, Any], *, now: datetime, until: float,
                   stats: Counter[str], qstats: Counter[str]) -> None:
    """Try every DISCOVERED registry row once a day, by its own door and by a frontier search."""
    reg = _read_json(REGISTRY, {}) or {}
    rows = (reg.get("datasets") or {})
    for rid, probe in LEGACY_PROBES.items():
        if time.monotonic() >= until:
            break
        hand = rows.get(rid)
        if isinstance(hand, dict) and _rank(str(hand.get("lifecycle"))) >= _rank("CORE"):
            continue
        rec = cat["legacy"].setdefault(rid, {})
        last = _parse_iso(rec.get("at"))
        if last and (now - last).total_seconds() < LEGACY_RETRY_H * 3600:
            continue
        rec.update({"at": _iso(now), "status": "FAILED", "reason": None, "seeded": 0})
        if probe.get("search"):
            try:
                doc = client.get_json(f"{DBNOMICS}/search?"
                                      + urllib.parse.urlencode({"q": probe["search"],
                                                                "limit": 20}))
                for d in ((doc.get("results") or {}).get("docs") or []):
                    prov, dcode = str(d.get("provider_code") or ""), str(d.get("code") or "")
                    if not prov or not dcode:
                        continue
                    key = f"{prov}/{dcode}"
                    row = cat["datasets"].setdefault(key, {"provider": prov, "code": dcode,
                                                           "lifecycle": "DISCOVERED",
                                                           "discovered_at": _iso(now),
                                                           "series_offset": 0,
                                                           "source": "dbnomics"})
                    row["name"] = str(d.get("name") or dcode)[:200]
                    row["score"] = dataset_score(prov, row["name"]) + 5.0
                    row["seeded_by"] = rid
                    rec["seeded"] += 1
            except FetchError as exc:
                rec["search_error"] = exc.reason
        if probe.get("direct"):
            key = next((k for k in cat["datasets"] if k.endswith("/" + probe["direct"])), None)
            drow = cat["datasets"].get(key or "", {})
            rec["via"] = key
            rec["status"] = "INGESTED" if _rank(drow.get("lifecycle", "")) >= 1 else "PENDING"
            rec["reason"] = drow.get("fail_reason") or ("via the direct door" if key else
                                                        "direct door not yet reached")
            if _rank(drow.get("lifecycle", "")) >= 2:
                rec["status"] = "QUALITY-PASSED"
            stats[f"legacy:{rec['status']}"] += 1
            continue
        if not probe.get("url"):
            rec["reason"] = "no keyless endpoint known; frontier seeded by search"
            rec["status"] = "SEARCH_ONLY"
            stats["legacy:SEARCH_ONLY"] += 1
            continue
        spec = {"provider": "DIRECT", "dataset": rid, "name": rid, **probe}
        try:
            series = _fetch_direct(client, spec, now)
            res = ingest_series("DIRECT", rid, rid, series, now=now,
                                base_score=dataset_score("DIRECT", rid),
                                hint_stems=probe.get("stems", ()), qstats=qstats)
            rec.update({"status": "QUALITY-PASSED" if res["passed"] else "INGESTED",
                        "series": len(series), "passed": res["passed"],
                        "path": _rel(dataset_path("DIRECT", rid))})
        except FetchError as exc:
            rec["reason"] = exc.reason
        except Exception as exc:
            rec["reason"] = f"parse:{type(exc).__name__}"
        stats[f"legacy:{rec['status']}"] += 1


# ----------------------------------------------------------------------------- exposure ----
def build_exposure(now: datetime) -> dict[str, Any]:
    """symbol -> ranked quality-passed series that inform it; plus the key -> location index."""
    per_symbol: dict[str, list[tuple[float, str]]] = defaultdict(list)
    keys = _read_json(KEYS, {}) or {}
    datasets_used: dict[str, set[str]] = defaultdict(set)
    for mp in OBS.glob("*/*.meta.json"):
        meta = _read_json(mp, {}) or {}
        prov, ds = meta.get("provider"), meta.get("dataset")
        if not prov or not ds:
            continue
        for code, s in (meta.get("series") or {}).items():
            if s.get("quality") != "PASS" or not s.get("instruments"):
                continue
            key = s["key"]
            keys[key] = [prov, ds, code]
            for sym in s["instruments"]:
                per_symbol[sym].append((float(s.get("score") or 0.0), key))
                datasets_used[f"{prov}/{ds}"].add(sym)
    symbols = {sym: [k for _, k in sorted(v, key=lambda t: (-t[0], t[1]))[:EXPOSE_CANDIDATES]]
               for sym, v in sorted(per_symbol.items())}
    # KEYS ARE APPEND-ONLY: a cell found on a series that has since dropped out of the ranking
    # must still rebuild by name, so a key is never removed once handed to research.
    write_json(KEYS, keys, indent=None)
    doc = {"generated_at": _iso(now), "core": EXPOSE_CORE, "rotating": EXPOSE_ROTATING,
           "symbols": symbols}
    write_json(EXPOSURE, doc, indent=None)
    return {"symbols": len(symbols), "series_exposable": len({k for v in symbols.values()
                                                              for k in v}),
            "datasets_in_research_use": sorted(datasets_used)}


def exposed_keys(symbol: str, *, now: datetime | None = None,
                 doc: dict[str, Any] | None = None) -> list[str]:
    """The keys a search on `symbol` sees this UTC day: the stable core plus a daily window."""
    doc = doc if doc is not None else _exposure_doc()
    cands = list((doc.get("symbols") or {}).get(symbol) or [])
    core_n, rot_n = int(doc.get("core", EXPOSE_CORE)), int(doc.get("rotating", EXPOSE_ROTATING))
    core, rest = cands[:core_n], cands[core_n:]
    if not rest:
        return core
    day = (now or _now()).date().toordinal()
    start = (day * rot_n) % len(rest)
    window = [rest[(start + i) % len(rest)] for i in range(min(rot_n, len(rest)))]
    return core + window


def _exposure_doc() -> dict[str, Any]:
    try:
        mtime = EXPOSURE.stat().st_mtime_ns
    except OSError:
        return {}
    return _exposure_at(str(EXPOSURE), mtime)


@lru_cache(maxsize=2)
def _exposure_at(path: str, mtime_ns: int) -> dict[str, Any]:
    doc = _read_json(Path(path), {})
    return doc if isinstance(doc, dict) else {}


@lru_cache(maxsize=2)
def _keys_at(path: str, mtime_ns: int) -> dict[str, Any]:
    doc = _read_json(Path(path), {})
    return doc if isinstance(doc, dict) else {}


def _key_location(key: str) -> tuple[str, str, str] | None:
    try:
        mtime = KEYS.stat().st_mtime_ns
    except OSError:
        return None
    loc = _keys_at(str(KEYS), mtime).get(key)
    return tuple(loc) if isinstance(loc, list) and len(loc) == 3 else None  # type: ignore[return-value]


@lru_cache(maxsize=16)
def _frame_at(path: str, mtime_ns: int) -> Any:
    return _load_frame(Path(path))


def raw_world_series(key: str) -> Any:
    """The PIT series behind one key, on its own knowable-at clock, or None."""
    loc = _key_location(key)
    if loc is None:
        return None
    path = dataset_path(loc[0], loc[1])
    try:
        frame = _frame_at(str(path), path.stat().st_mtime_ns)
    except OSError:
        return None
    if frame is None:
        return None
    s = pit_series(frame, loc[2])
    return s if len(s) else None


def _align(series: Any, index: Any) -> Any:
    """Causal: each bar sees the last value knowable at or before it; tz follows the bars."""
    want = getattr(index, "tz", None)
    s = series if series.index.tz is not None else series.tz_localize("UTC")
    s = s.tz_convert("UTC").tz_localize(None) if want is None else s.tz_convert(want)
    return s.reindex(s.index.union(index)).ffill().reindex(index)


def world_series_for(symbol: str, index: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """`{world_<key>: series on index}` for the research door. Equities get nothing."""
    try:
        from research import universe_policy as up
    except ImportError:                                                       # pragma: no cover
        import universe_policy as up  # type: ignore[no-redef]
    if not up.may_hypothesise(symbol):
        return {}
    out: dict[str, Any] = {}
    for key in exposed_keys(symbol, now=now):
        s = raw_world_series(key)
        if s is None:
            continue
        aligned = _align(s, index)
        if aligned.notna().sum() >= 200:
            out[f"{WORLD_KEY_PREFIX}{key}"] = aligned
    return out



# ------------------------------------------------------------------------------ registry ----
def update_registry(cat: dict[str, Any], exposure: dict[str, Any], now: datetime) -> dict:
    """Write the lifecycle of every hunted dataset into data_registry.json -- by THIS organ, on
    the box, never by an edit on origin. Hand rows are never demoted and never rewritten; the
    ten DISCOVERED rows get a `hunter_attempt` block and move UP when a door ingests them."""
    reg = _read_json(REGISTRY, None)
    if not isinstance(reg, dict):
        return {"status": "REGISTRY_UNREADABLE"}
    ds = reg.setdefault("datasets", {})
    used = set(exposure.get("datasets_in_research_use") or [])
    # UPSERT, NEVER REMOVE. A row once registered stays; one that falls out of the capped
    # DISCOVERED set keeps its last written state (nothing is retired on an absence, LAWS 7).
    fetched = [(k, r) for k, r in cat["datasets"].items() if _rank(r.get("lifecycle", "")) >= 1]
    discovered = sorted(((k, r) for k, r in cat["datasets"].items()
                         if _rank(r.get("lifecycle", "")) == 0),
                        key=lambda kv: -float(kv[1].get("score") or 0.0))
    withheld = max(0, len(discovered) - REGISTRY_DISCOVERED_CAP)
    for key, r in fetched + discovered[:REGISTRY_DISCOVERED_CAP]:
        prior = ds.get(f"world:{key}") if isinstance(ds.get(f"world:{key}"), dict) else {}
        lifecycle = r.get("lifecycle", "DISCOVERED")
        if _rank(str(prior.get("lifecycle"))) > _rank(lifecycle):
            lifecycle = str(prior["lifecycle"])      # a later stage set by another organ stands
        ds[f"world:{key}"] = {
            **prior, "lifecycle": lifecycle,
            "source": f"{r.get('source', 'dbnomics')}:{r.get('provider')}",
            "name": r.get("name"), "path": r.get("path"),
            "discovered": (r.get("discovered_at") or "")[:10] or None,
            "ingested": (r.get("fetched_at") or "")[:10] or None,
            "series_total": r.get("series_total"), "rows": r.get("rows"),
            "research_exposed": key in used, "pit": "first_seen_utc+available_time",
            "owner": "world_dataset_hunter"}
    for rid, rec in (cat.get("legacy") or {}).items():
        hand = ds.get(rid)
        if not isinstance(hand, dict):
            continue
        hand["hunter_attempt"] = {k: rec.get(k) for k in ("at", "status", "reason", "via",
                                                          "path", "seeded")}
        if rec.get("status") in ("INGESTED", "QUALITY-PASSED"):
            _promote(hand, rec["status"])
    reg["world_dataset_hunter"] = {"updated_at": _iso(now),
                                   "registered": sum(1 for k in ds if k.startswith("world:")),
                                   "discovered_withheld_from_registry": withheld,
                                   "catalog": _rel(CATALOG)}
    write_json(REGISTRY, reg)
    return {"status": "OK", "withheld": withheld}


# ------------------------------------------------------------------------------- report ----
def _history_rates(now: datetime) -> dict[str, Any]:
    rows = []
    try:
        for line in HISTORY.read_text("utf-8").splitlines()[-2000:]:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    ats = [(_parse_iso(r.get("at")), r) for r in rows]
    ats = [(a, r) for a, r in ats if a]
    if not ats:
        return {"rows_per_day": UNMEASURED, "datasets_fetched_per_day": UNMEASURED,
                "why": "no pass history yet"}
    span_h = (now - min(a for a, _ in ats)).total_seconds() / 3600
    last = [r for a, r in ats if (now - a).total_seconds() <= 86400]
    rows_24 = sum(int(r.get("rows_appended") or 0) for r in last)
    fetched_24 = sum(int(r.get("datasets_fetched") or 0) for r in last)
    if span_h < 23:
        return {"rows_per_day": UNMEASURED, "datasets_fetched_per_day": UNMEASURED,
                "why": f"history spans {span_h:.1f}h of the 24h a daily rate needs",
                "rows_so_far": rows_24, "datasets_fetched_so_far": fetched_24,
                "passes_so_far": len(last)}
    return {"rows_per_day": rows_24, "datasets_fetched_per_day": fetched_24,
            "passes_last_24h": len(last)}


def _free_disk_ok() -> tuple[bool, dict[str, Any]]:
    try:
        STORE.mkdir(parents=True, exist_ok=True)
        du = shutil.disk_usage(STORE)
    except OSError as exc:
        return True, {"disk": UNMEASURED, "why": str(exc)}
    need = max(MIN_FREE_BYTES, int(du.total * MIN_FREE_SHARE))
    return du.free >= need, {"free_gb": round(du.free / 1024 ** 3, 2),
                             "floor_gb": round(need / 1024 ** 3, 2)}


def run(*, budget_s: float = DEFAULT_BUDGET_S, fetch: Fetcher | None = None,
        now: datetime | None = None, dry_run: bool = False) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    deadline = t0 + max(10.0, float(budget_s))
    client = Client(fetch, deadline)
    cat = load_catalog()
    stats: Counter[str] = Counter()
    qstats: Counter[str] = Counter()
    by_provider: dict[str, Counter[str]] = defaultdict(Counter)
    stood_down = None
    disk_ok, disk = _free_disk_ok()

    discovery_until = t0 + (deadline - t0) * DISCOVERY_SHARE
    discover(client, cat, now=now, until=discovery_until, stats=stats)
    if not dry_run:
        if not disk_ok:
            stood_down = "free disk below floor: fetching stood down, discovery continued"
        else:
            attempt_legacy(client, cat, now=now, until=deadline, stats=stats, qstats=qstats)
            fetch_direct(client, cat, now=now, until=t0 + (deadline - t0) * 0.55, stats=stats,
                         qstats=qstats, by_provider=by_provider)
            fetch_country_packs(client, cat, now=now, until=t0 + (deadline - t0) * 0.65,
                                stats=stats, qstats=qstats, by_provider=by_provider)
            fetch_dbnomics(client, cat, now=now, until=deadline, stats=stats, qstats=qstats,
                           by_provider=by_provider)
    cat["updated_at"] = _iso(now)
    write_json(CATALOG, cat, indent=None)
    exposure = build_exposure(now)
    reg_res = update_registry(cat, exposure, now) if not dry_run else {"status": "DRY_RUN"}

    elapsed = time.monotonic() - t0
    hist_row = {"at": _iso(now), "elapsed_s": round(elapsed, 1), "requests": client.requests,
                "ok": client.ok, "bytes": client.bytes,
                "datasets_fetched": stats["datasets_fetched"],
                "rows_appended": stats["rows_appended"]}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(hist_row) + "\n")

    report = build_report(cat, exposure, stats=stats, qstats=qstats, client=client,
                          by_provider_pass=by_provider, now=now, elapsed=elapsed,
                          budget_s=budget_s, stood_down=stood_down, disk=disk,
                          registry=reg_res)
    # TWO PACK SETS, ONE REPORT KEY: the hunter's own COUNTRY_PACKS (id / sg / sa / jp / cn,
    # `build_report`) and research/country_packs.py's (tr / pl / se / za). Pack names never
    # overlap; the liveness verdict and its artifact are the latter's (COUNTRY_PACK_LIVENESS.json),
    # whose RED process_health reads from that file (the organ's `status` stays the former's).
    eu = country_packs_eu_report(cat, now)
    own = report.get("country_packs") or {}
    report["country_packs"] = {**own, **eu,
                               "packs": {**(own.get("packs") or {}), **(eu.get("packs") or {})}}
    write_json(REPORT, report)
    return report


def build_report(cat: dict[str, Any], exposure: dict[str, Any], *, stats: Counter[str],
                 qstats: Counter[str], client: Client, by_provider_pass: dict[str, Counter[str]],
                 now: datetime, elapsed: float, budget_s: float, stood_down: str | None,
                 disk: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    used = set(exposure.get("datasets_in_research_use") or [])
    prov: dict[str, Counter[str]] = defaultdict(Counter)
    series_ingested = series_passed = obs = 0
    life = Counter()
    for key, r in cat["datasets"].items():
        p = str(r.get("provider"))
        lc = str(r.get("lifecycle") or "DISCOVERED")
        life[lc] += 1
        prov[p]["discovered"] += 1
        if _rank(lc) >= 1:
            prov[p]["fetched"] += 1
            obs += int(r.get("rows") or 0)
        if _rank(lc) >= 2:
            prov[p]["quality_passed"] += 1
        if key in used:
            prov[p]["research_use"] += 1
    for mp in OBS.glob("*/*.meta.json"):
        meta = _read_json(mp, {}) or {}
        for s in (meta.get("series") or {}).values():
            series_ingested += 1
            series_passed += int(s.get("quality") == "PASS")
    fail = Counter({k: v for k, v in stats.items() if ":" in k and not k.startswith("legacy:")})
    network = "OK" if client.ok else (UNMEASURED if not client.requests else "BLOCKED")
    blocked_why = None
    if network == "BLOCKED":
        blocked_why = ", ".join(f"{k} x{v}" for k, v in client.failures.most_common(3))
    fetched = sum(1 for r in cat["datasets"].values() if _rank(r.get("lifecycle", "")) >= 1)
    qp = sum(1 for r in cat["datasets"].values() if _rank(r.get("lifecycle", "")) >= 2)

    def _or_unmeasured(n: int, measured: bool) -> Any:
        return n if measured else UNMEASURED

    measured = bool(cat["datasets"]) or client.ok > 0
    rates = _history_rates(now)
    packs = country_pack_report(cat)
    return {
        # the organ's own last reading (health_board reads it): a RED country-pack door names
        # itself here, so the desk's board turns the organ from GREEN without a second board
        "status": packs["status"],
        "generated_at": _iso(now),
        "organ": "desks/mt5/research/world_dataset_hunter.py",
        "leg": "hourly_cycle:world_dataset_hunt",
        "pass": {"budget_s": budget_s, "elapsed_s": round(elapsed, 1),
                 "requests": client.requests, "ok": client.ok, "bytes": client.bytes,
                 "stood_down": stood_down, "network": network, "network_blocked_by": blocked_why,
                 "disk": disk, "datasets_fetched": stats["datasets_fetched"],
                 "rows_appended": stats["rows_appended"], "new_datasets": stats["datasets_new"]},
        "totals": {
            "providers_discovered": _or_unmeasured(len(cat["providers"]),
                                                   bool(cat["providers"]) or client.ok > 0),
            "datasets_discovered": _or_unmeasured(len(cat["datasets"]), measured),
            "datasets_fetched": _or_unmeasured(fetched, measured),
            "datasets_quality_passed": _or_unmeasured(qp, measured),
            "datasets_in_research_use": _or_unmeasured(len(used), measured),
            "series_ingested": _or_unmeasured(series_ingested, measured),
            "series_quality_passed": _or_unmeasured(series_passed, measured),
            "series_exposable_to_research": _or_unmeasured(exposure.get("series_exposable", 0),
                                                           measured),
            "symbols_with_world_series": _or_unmeasured(exposure.get("symbols", 0), measured),
            "observations_stored": _or_unmeasured(obs, measured),
            **rates,
        },
        "lifecycle": dict(life) or UNMEASURED,
        "by_provider": {p: dict(c) for p, c in sorted(prov.items())} or UNMEASURED,
        "by_provider_this_pass": {p: dict(c) for p, c in sorted(by_provider_pass.items())},
        "failures_by_reason": dict(fail),
        "http_failures_by_reason": dict(client.failures),
        "quality_by_reason": dict(qstats),
        "legacy_discovered": cat.get("legacy") or UNMEASURED,
        # every direct door's row in the one terms register; a refused door's missed growth
        "terms_doors": _terms_doors_or_unmeasured(),
        # GAP #4 / #5 (2026-10-29): which USDA commodities reach an MT5 symbol and which do not,
        # and the IDEAS_ONLY nowcast/crop sources with their missed-growth lines.
        "agri_supply_map": agri_mapping(),
        "ideas_only": ideas_only_lines(),
        "registry": registry,
        "country_packs": packs,
        "research_door": ("reports/WORLD_MACRO_PROPOSER.json <- world_macro_proposer reads "
                          "exposure.json and mints world_macro_state cells; the family reloads "
                          "each series by series_key"),
        "rule": ("absence is UNMEASURED, never 0; every observation carries available_time and "
                 "first_seen_utc; a revision is a new row, never an overwrite"),
    }


def _terms_doors_or_unmeasured() -> Any:
    try:
        return terms_doors()
    except Exception as exc:                       # the register unreadable is a reading too
        return {"state": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:200]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="discover only; write nothing to "
                                                           "the registry")
    args = ap.parse_args(argv)
    rep = run(budget_s=args.budget_s, dry_run=args.dry_run)
    t, p = rep["totals"], rep["pass"]
    print(f"world_dataset_hunt: network={p['network']} requests={p['requests']} ok={p['ok']} "
          f"providers={t['providers_discovered']} datasets={t['datasets_discovered']} "
          f"fetched={t['datasets_fetched']} quality_passed={t['datasets_quality_passed']} "
          f"series={t['series_ingested']} research_use={t['datasets_in_research_use']} "
          f"rows_this_pass={p['rows_appended']}", flush=True)
    if p.get("network_blocked_by"):
        print(f"   blocked by: {p['network_blocked_by']}", flush=True)
    cpk = rep.get("country_packs") or {}
    print(f"   country packs: {cpk.get('verdict')} "
          + " ".join(f"{k}={v.get('verdict')}" for k, v in (cpk.get("packs") or {}).items())
          + (f" RED: {', '.join(cpk['red'])}" if cpk.get("red") else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
