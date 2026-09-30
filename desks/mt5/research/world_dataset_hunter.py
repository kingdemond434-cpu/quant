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
from collections import Counter, defaultdict
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


Fetcher = Callable[[str, float], bytes]


def urllib_fetch(url: str, timeout: float) -> bytes:
    """Default transport: urllib, a named UA, one polite retry on 429."""
    for attempt in (0, 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json, text/csv, */*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(MAX_DIRECT_BYTES + 1)
            if len(raw) > MAX_DIRECT_BYTES:
                raise FetchError("too_large", url)
            return raw
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                try:
                    wait = min(30.0, float(exc.headers.get("Retry-After") or 10))
                except (TypeError, ValueError):
                    wait = 10.0
                time.sleep(wait)
                continue
            raise FetchError(_classify(exc), str(exc)[:160]) from exc
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(_classify(exc), f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    raise FetchError("rate_limited_429", url)


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

    def get(self, url: str) -> bytes:
        left = self.remaining()
        if left < 2.0:
            raise FetchError("budget_exhausted", url)
        gap = MIN_REQUEST_GAP_S - (time.monotonic() - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()
        self.requests += 1
        try:
            raw = self.fetch(url, min(HTTP_TIMEOUT_S, max(2.0, left - 1.0)))
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
        for per, val in s["points"]:
            end, f = period_end(per, freq)
            if end is None:
                continue
            lag = lag_days(f or freq, declared_lag)
            rows.append((s["code"], per, pd.Timestamp(end, tz="UTC"), float(val),
                         pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=lag)))
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


def series_from_long(df: Any, *, freq: str = "", hint: str = "") -> list[dict[str, Any]]:
    out = []
    dim_cols = [c for c in df.columns if c not in ("series_code", "period", "value")]
    for code, g in df.groupby("series_code", sort=False):
        dims = {c: str(g[c].iloc[0]) for c in dim_cols} if dim_cols else {}
        pts = [(str(p), float(v)) for p, v in zip(g["period"], g["value"], strict=False)]
        fq = freq or dims.get("FREQ", "")
        out.append({"code": str(code), "name": f"{hint} {code}".strip(), "freq": norm_freq(fq),
                    "dims": dims, "points": pts})
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
    for sid in _fred_ids():
        out.append({"provider": "FRED", "dataset": sid, "name": f"FRED {sid}", "mode": "csv",
                    "url": ("https://fred.stlouisfed.org/graph/fredgraph.csv?"
                            + urllib.parse.urlencode({"id": sid})), "currencies": ["USD"]})
    return out


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


def _fetch_order(cat: dict[str, Any], now: datetime) -> list[str]:
    """Never-fetched first, then due-for-refresh; within each, highest MT5 relevance first."""
    rows = []
    for key, row in cat["datasets"].items():
        if row.get("source") != "dbnomics" or not _due(row, now):
            continue
        fails = int(row.get("fail_count") or 0)
        rows.append((0 if not row.get("fetched_at") else 1, fails,
                     -float(row.get("score") or 0.0), key))
    rows.sort()
    return [r[-1] for r in rows]


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
                  qstats: Counter[str]) -> dict[str, Any]:
    """Quality-check, PIT-merge and describe one batch of series from one dataset."""
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
        mapping = map_series(f"{s.get('name', '')} {dname}", s.get("dims"))
        ccys = sorted(set(mapping["currencies"]) | {c.upper() for c in hint_ccys})
        stems = sorted(set(mapping["stems"]) | {x.upper() for x in hint_stems})
        insts = instruments_for(ccys, stems) if (ccys or stems) else []
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


def _fetch_direct(client: Client, spec: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    url = spec["url"].replace("{bday}", _last_business_day(now))
    raw = client.get(url)
    mode = spec.get("mode", "csv")
    df = _lbma_frame(raw) if mode == "lbma_json" else frame_from_payload(raw, mode, {**spec,
                                                                                     "url": url})
    if df is None or len(df) == 0:
        raise FetchError("empty", url)
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
        try:
            series = _fetch_direct(client, spec, now)
        except FetchError as exc:
            if exc.reason == "budget_exhausted":
                break
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = exc.reason
            row["next_due"] = _iso(now + timedelta(hours=DIRECT_REFRESH_H))
            stats[f"direct:{exc.reason}"] += 1
            by_provider[spec["provider"]]["failed"] += 1
            continue
        except Exception as exc:
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = f"parse:{type(exc).__name__}"
            row["next_due"] = _iso(now + timedelta(hours=DIRECT_REFRESH_H))
            stats[f"direct:parse:{type(exc).__name__}"] += 1
            continue
        res = ingest_series(spec["provider"], spec["dataset"], spec.get("name", ""), series,
                            now=now, base_score=row["score"], declared_lag=spec.get("lag_days"),
                            hint_ccys=spec.get("currencies", ()),
                            hint_stems=spec.get("stems", ()), qstats=qstats)
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
    return {
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
        "registry": registry,
        "research_door": ("reports/WORLD_MACRO_PROPOSER.json <- world_macro_proposer reads "
                          "exposure.json and mints world_macro_state cells; the family reloads "
                          "each series by series_key"),
        "rule": ("absence is UNMEASURED, never 0; every observation carries available_time and "
                 "first_seen_utc; a revision is a new row, never an overwrite"),
    }


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
