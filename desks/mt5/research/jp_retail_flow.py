"""JAPAN RETAIL AND INVESTOR-TYPE FLOW -- two free public doors of the world dataset hunter.

    TFX "Click 365" (www.click365.jp)  為替売買動向: retail exchange-FX open interest per currency
        pair, SELL against BUY, as of each Tuesday's close (the file carries the latest four).
        Mrs Watanabe's book: contrarian and crowding features for USDJPY, AUDJPY and the crosses.
    JPX 投資部門別売買状況 (www.jpx.co.jp)  weekly trading value on the TSE by investor type --
        foreigners, individuals, trust banks, investment trusts, business companies and the rest.
        An INDEX-LEVEL aggregate (the whole Prime market), so it is flow for JPN225 and the yen,
        never a single-name equity hypothesis (CLAUDE.md, TWO LANES).
    FFAJ 店頭FX月次速報 (www.ffaj.or.jp)  the Financial Futures Association of Japan's monthly OTC
        retail FX statistics: every reporting member's customer open positions at month end,
        SELL (売建玉) against BUY (買建玉), in 100 million yen. The whole OTC retail book (an
        order of magnitude larger than Click 365), monthly: the slow leg of the same crowd.

WHERE IT RUNS. `world_dataset_hunter.run` calls `fetch_doors` on every hourly pass of the
`world_dataset_hunt` leg (hourly_cycle); a door is asked only when its `next_due` has passed. Its
series land in the hunter's one PIT store (`PACK_JP/...`), `build_exposure` hands the quality-passed
ones to world_macro_proposer, and the gauntlet judges them as `world_macro_state` cells. No new
leg, no new store, no second minting clock.

ACCESS (LAWS 5e). Licence, robots and terms are LABELS on the row, never a stop:
    robots.txt allows, or is absent      -> the terms row's label (PUBLIC_WITH_TERMS here: both
                                            publishers reserve their rights and grant no reuse)
    robots.txt Disallow for the desk     -> PUBLIC_WITH_TERMS, the Disallow carried in terms_note
    robots.txt unreadable                -> ACCESS_UNCLEAR, mined with the label attached
`redistribute_allowed` is read from `access_classifier.ROUTING` and fails closed. What DOES stop
a door is an access control: 401, 403, 429 or a WAF / CAPTCHA page is a HARD STOP, recorded on the
door and (on the desk transport) in polite_fetch's shared ledger as a person-held hold. Nothing
retries it and no clock releases it. The desk's honest DESK_UA is the only User-Agent sent; there
is no IP or agent rotation, no login, no key.

LIVE SIZING. A series may size a live position only when its register row quotes a clause that
PERMITS the use (`terms_fence.terms_verdict(row) == "confirmed"`). Neither publisher has one (TFX:
"All Rights Reserved" and no reuse clause; JPX: secondary use needs its permission), so both rows
are IDEAS_ONLY in the register and every series here is RESEARCH-ONLY: mined, stored, featured and
judged in full, with `live_sizing_allowed: false` on its dataset's `access` block and
`terms_fence.input_source(<url>)` refusing it to any live-input organ.

POINT IN TIME. Every observation is stamped at its PUBLICATION instant, never its period:
    TFX   the Tuesday close is published after the close: stamped Wednesday 09:00 UTC
          (18:00 JST), later than both readings of "毎週火曜日取引終了時のデータを提出します".
    JPX   "毎週第4営業日 ... 午後3時30分に資料を掲載します": the 4th Tokyo business day of the
          FOLLOWING week, 15:30 JST (06:30 UTC). The holiday table below is deliberately wide (both
          candidate equinox days, every bridge day), so an error only ever stamps LATER.
    FFAJ  no release rule is published; the September 2026 file carried "更新日 2026年10月15日".
          A month is stamped on the FFAJ_PUBLISH_DAY of the following month at 15:00 UTC (24:00
          JST), later than every release observed; the month the page's own 更新日 names is stamped
          at that date's end of day when it is later still.
A value the hunter first sees after its rule time is keyed on max(rule, first seen) by
`world_dataset_hunter.pit_series`, so a late release can never be stamped early.

LIVENESS. A door counts consecutive attempts that landed nothing (`empty_streak`); more than
`world_dataset_hunter.PACK_EMPTY_RED_RUNS` in a row is RED, and RED puts the door's name in the
hunter report's top-level `status`, which health_board reads as the organ's last reading.

THE PLAYER-FOOTPRINT MATRIX (PR #659, claude/global-flow-footprints) is not on this base. Its
registry carries both sources as named gaps (`tfx_click365`, `jpx_investor_type`: class retail,
region JP). `FOOTPRINT_ROWS` restates those two rows filled in, with the column names this module
publishes, and `footprint_frame(sid)` returns them in the shape #659's `collect` consumes (a
date-indexed frame plus an `available_utc` column carrying the publication stamp).
"""
from __future__ import annotations

import math
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

#: The catalog provider every series here lands under (the hunter's Japan pack provider).
PROVIDER = "PACK_JP"
PACK = "japan_retail_flow"

TFX_FILE = "https://www.click365.jp/resorces/doc/weekly_sellbuy.xls"
TFX_PAGE = "https://www.click365.jp/market.html"
JPX_INDEX = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html"
JPX_ARCHIVE = ("https://www.jpx.co.jp/markets/statistics-equities/investor-type/"
               "00-00-archives-00.html")

#: The two register rows (libs/data/terms_fence.SOURCE_POLICY).
TFX_POLICY = "jp_tfx_click365"
JPX_POLICY = "jp_jpx_investor_type"
FFAJ_POLICY = "jp_ffaj_otc_fx"
FFAJ_PAGE = "https://www.ffaj.or.jp/library/performance/fx_flash"

#: A door is asked again this many hours after a pass that landed rows (TFX updates weekly on
#: Tuesday, JPX on Thursday; six hours finds each within a quarter of a day) and after a failure.
REFRESH_OK_H = 6.0
RETRY_FAIL_H = 6.0
#: JPX files fetched per pass (newest first, then the back-fill), and older archive pages read per
#: pass. One index page + a few files every six hours is the opposite of the "high-frequency,
#: high-load automated retrieval" JPX's terms ask users to refrain from.
JPX_FILES_PER_PASS = 6
JPX_ARCHIVE_PAGES_PER_PASS = 2
MAX_BYTES = 8_000_000
#: Minimum seconds between two requests to one host (polite_fetch's shared per-host gate).
POLITE_GAP_S = 3.0
HTTP_TIMEOUT_S = 30.0

#: Rolling windows (weeks) and the minimum history before a feature is published.
Z_WINDOW_TFX = 26
Z_WINDOW_JPX = 52
Z_WINDOW_FFAJ = 36
Z_MIN = 8

#: TFX publication: the Tuesday close, stamped the next day at this UTC hour.
TFX_PUBLISH_LAG_D = 1
TFX_PUBLISH_HOUR_UTC = 9
#: JPX publication: the Nth Tokyo business day of the following week, at 15:30 JST.
JPX_PUBLISH_BUSINESS_DAY = 4
JPX_PUBLISH_UTC = (6, 30)
#: FFAJ publication: this day of the following month, at FFAJ_PUBLISH_HOUR_UTC (see the docstring).
FFAJ_PUBLISH_DAY = 20
FFAJ_PUBLISH_HOUR_UTC = 15

HARD_STOP_STATUS: frozenset[int] = frozenset({401, 403, 429})


class HardStop(Exception):
    """An access control answered (401/403/429, a WAF / CAPTCHA page, or a redirect into a login
    wall). The door holds until a person clears it; nothing retries it."""

    def __init__(self, status: int | str, url: str, why: str = "") -> None:
        super().__init__(f"{status}: {why or url}")
        self.status, self.url, self.why = status, url, why


class Missing(Exception):
    """404 / 410: the file is not there (yet). Not a refusal."""


class Transient(Exception):
    """A transport failure or a 5xx: tried again on the next due pass."""


#: url, timeout -> body. Raises HardStop / Missing / Transient.
Transport = Callable[[str, float], bytes]


# ---------------------------------------------------------------------------- the transport --
class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when the target is neither a held source nor a login wall."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> Any:
        from libs.data import terms_fence as _tf
        if _tf.login_wall(newurl):
            raise HardStop(code, newurl, "redirect into a login wall")
        if _tf.platform_of_url(newurl):
            raise HardStop(code, newurl, f"redirect into held source {_tf.platform_of_url(newurl)}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def desk_transport(url: str, timeout: float) -> bytes:
    """THE PRODUCTION TRANSPORT. One GET with the desk's honest headers (`DESK_UA`) and verified
    TLS. robots.txt is NOT asked here: it is read separately as a LABEL (`access_label`). A held
    register source or a login wall is never requested; a site a person holds is never asked; a
    401/403/429 or a challenge page records a person-held hold in the shared access ledger."""
    from libs.data import polite_fetch as _pf
    from libs.data import terms_fence as _tf
    if _tf.platform_of_url(url) or _tf.login_wall(url):
        raise HardStop("held", url, "held register source or login wall: never requested")
    held = _pf.person_hold(url)
    if held:
        raise HardStop("held", url, f"site held for a person ({held})")
    _pf.GATE.wait(_pf.hostname_of(url), at_least=POLITE_GAP_S)     # per-host spacing, shared
    req = urllib.request.Request(url, headers=_pf.honest_headers({"Accept": "*/*"}))
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_pf.ssl_context()),
                                         _Redirects())
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(MAX_BYTES + 1)
            headers, status = resp.headers, int(getattr(resp, "status", 200) or 200)
    except HardStop:
        raise
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        try:
            err_body = exc.read(16000)
        except Exception:
            err_body = b""
        marker = _pf.looks_challenged(err_body, exc.headers, code)
        if code in HARD_STOP_STATUS or marker:
            _pf.hold_site(url, code, cause=marker or f"HTTP {code}")
            raise HardStop(code, url, marker or f"HTTP {code}") from exc
        if code in (404, 410):
            raise Missing(url) from exc
        raise Transient(f"HTTP {code}") from exc
    except (OSError, ValueError) as exc:
        raise Transient(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
    marker = _pf.looks_challenged(body, headers, status)
    if marker:
        _pf.hold_site(url, "WAF", cause=marker)
        raise HardStop("WAF", url, marker)
    if len(body) > MAX_BYTES:
        raise Transient(f"body longer than {MAX_BYTES} bytes")
    return bytes(body)


def hunter_transport(fetch: Callable[..., bytes]) -> Transport:
    """Adapt a world_dataset_hunter fetcher (raises FetchError(reason)) to this door's errors."""
    def _t(url: str, timeout: float) -> bytes:
        W = _W()
        try:
            return fetch(url, timeout)
        except W.FetchError as exc:
            r = str(exc.reason)
            if r in ("blocked_401", "blocked_403", "rate_limited_429"):
                raise HardStop(int(r[-3:]), url, r) from exc
            if r in ("waf", "challenge", "captcha"):
                raise HardStop("WAF", url, r) from exc
            if r == "not_found_404":
                raise Missing(url) from exc
            raise Transient(r) from exc
    return _t


# ------------------------------------------------------------------------------ access label --
def redistribute_allowed(label: str) -> bool:
    """`redistribute` among the label's allowed uses in access_classifier.ROUTING; False when the
    classifier or the label cannot be read (the one use a label withholds is never assumed)."""
    try:
        from libs.research.access_classifier import ROUTING
    except ImportError:
        return False
    row = ROUTING.get(label)  # type: ignore[call-overload]
    return bool(row) and "redistribute" in tuple(row.get("allowed_uses") or ())


def terms_label(policy_key: str) -> str:
    """The label the register row's own terms give: OPEN_DATA for an open licence row, else
    PUBLIC_WITH_TERMS when the row carries terms (read or not), else PUBLIC."""
    from libs.data import terms_fence as _tf
    row = _tf.SOURCE_POLICY.get(policy_key) or {}
    if row.get("open_licence"):
        return "OPEN_DATA"
    return "PUBLIC_WITH_TERMS" if row.get("terms") else "PUBLIC"


def access_label(url: str, transport: Transport, policy_key: str) -> dict[str, Any]:
    """robots.txt READ AS A LABEL (LAWS 5e), never a refusal. A 401/403/429 or a challenge on
    robots.txt is an access control and raises HardStop like any other request."""
    from libs.data import polite_fetch as _pf
    parts = urllib.parse.urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    base = terms_label(policy_key)
    try:
        raw = transport(robots, HTTP_TIMEOUT_S)
    except HardStop:
        raise
    except Missing:
        return _label(base, "robots.txt absent (404): no rules; " + _terms_note(policy_key))
    except Exception as exc:
        return _label("ACCESS_UNCLEAR",
                      f"robots.txt unreadable ({str(exc)[:80]}): mined with the label attached")
    text = raw.decode("utf-8", "replace")
    if _pf.looks_like_html(text):
        return _label(base, "HTML served as robots.txt: no rules; " + _terms_note(policy_key))
    try:
        ok = _pf.parse_robots(text).can_fetch(_pf.DESK_UA_PRODUCT, url)
    except Exception as exc:
        return _label("ACCESS_UNCLEAR", f"robots.txt unparseable ({type(exc).__name__})")
    if ok:
        return _label(base, "robots.txt allows; " + _terms_note(policy_key))
    return _label("PUBLIC_WITH_TERMS",
                  f"robots.txt Disallow for {_pf.DESK_UA_PRODUCT} on {parts.path}: mined in full, "
                  "redistribution withheld (LAWS 5e); " + _terms_note(policy_key))


def _terms_note(policy_key: str) -> str:
    from libs.data import terms_fence as _tf
    row = _tf.SOURCE_POLICY.get(policy_key) or {}
    t = row.get("terms") or {}
    return (f"terms {t.get('url', 'UNREAD')} read {t.get('checked_at', 'never')}: "
            f"{row.get('why', '')}")


def _label(label: str, note: str) -> dict[str, Any]:
    return {"access_label": label, "terms_note": note[:600],
            "redistribute_allowed": redistribute_allowed(label)}


def live_sizing_allowed(policy_key: str) -> bool:
    """Only a register row that quotes a PERMITTING clause sizes live (fail closed)."""
    from libs.data import terms_fence as _tf
    try:
        return _tf.terms_verdict(policy_key) == "confirmed"
    except Exception:
        return False


# ---------------------------------------------------------------------------- the calendars --
def _nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def jp_holidays(year: int) -> frozenset[date]:
    """Tokyo exchange non-business weekdays, WIDE on purpose: both candidate equinox days, the
    year-end closure, Happy-Monday holidays, substitute days and the September bridge day. A day
    too many only stamps a JPX release later than it was; a day too few could stamp it early."""
    fixed = [(1, 1), (1, 2), (1, 3), (2, 11), (2, 23), (3, 20), (3, 21), (4, 29), (5, 3),
             (5, 4), (5, 5), (8, 11), (9, 22), (9, 23), (11, 3), (11, 23), (12, 31)]
    days = {date(year, m, d) for m, d in fixed}
    days |= {_nth_weekday(year, 1, 0, 2), _nth_weekday(year, 7, 0, 3),
             _nth_weekday(year, 9, 0, 3), _nth_weekday(year, 10, 0, 2)}
    aged = _nth_weekday(year, 9, 0, 3)
    days.add(aged + timedelta(days=1))                      # the September bridge (citizens' day)
    for d in sorted(days):
        if d.weekday() == 6:                                # a Sunday holiday moves to the next
            s = d + timedelta(days=1)                       # free weekday (substitute holiday)
            while s in days:
                s += timedelta(days=1)
            days.add(s)
    return frozenset(days)


def tokyo_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in jp_holidays(d.year)


def jpx_publication(week_end: date) -> datetime:
    """The 4th Tokyo business day of the week AFTER the week ending `week_end`, 15:30 JST."""
    d = week_end + timedelta(days=7 - week_end.weekday())   # the next Monday
    n = 0
    while True:
        if tokyo_business_day(d):
            n += 1
            if n == JPX_PUBLISH_BUSINESS_DAY:
                return datetime(d.year, d.month, d.day, *JPX_PUBLISH_UTC, tzinfo=UTC)
        d += timedelta(days=1)


def ffaj_publication(year: int, month: int, page_updated: date | None = None) -> datetime:
    """Month (year, month) is public on FFAJ_PUBLISH_DAY of the next month at 15:00 UTC, or at the
    end of the page's own 更新日 when that names a later day for this month."""
    y, m = (year + 1, 1) if month == 12 else (year, month + 1)
    at = datetime(y, m, FFAJ_PUBLISH_DAY, FFAJ_PUBLISH_HOUR_UTC, tzinfo=UTC)
    if page_updated is not None and (page_updated.year, page_updated.month) == (y, m):
        upd = datetime(page_updated.year, page_updated.month, page_updated.day,
                       FFAJ_PUBLISH_HOUR_UTC, tzinfo=UTC)
        at = max(at, upd)
    return at


def tfx_publication(obs: date) -> datetime:
    """A Tuesday-close observation, stamped the next day at TFX_PUBLISH_HOUR_UTC."""
    d = obs + timedelta(days=TFX_PUBLISH_LAG_D)
    return datetime(d.year, d.month, d.day, TFX_PUBLISH_HOUR_UTC, tzinfo=UTC)


# ---------------------------------------------------------------------------- cell helpers --
def _norm(v: Any) -> str:
    s = unicodedata.normalize("NFKC", str(v if v is not None else ""))
    return re.sub(r"\s+", "", s)


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    s = _norm(v).replace(",", "").replace("▲", "-").replace("△", "-")
    if not s or not re.fullmatch(r"[-+]?\d+(\.\d+)?", s):
        return None
    return float(s)


_DATE_TXT = re.compile(r"(\d{4})[/.\-年](\d{1,2})[/.\-月](\d{1,2})")


def _cell_date(v: Any, *, serial: bool = True) -> date | None:
    if serial and isinstance(v, (int, float)) and not isinstance(v, bool) \
            and 36000 < float(v) < 60000:
        return date(1899, 12, 30) + timedelta(days=int(float(v)))
    if isinstance(v, str):
        m = _DATE_TXT.search(_norm(v))
        if m:
            try:
                return date(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                return None
    return None


def sheets_of(raw: bytes) -> dict[str, list[list[Any]]]:
    """An .xls (BIFF8, libs.data.xls_reader) or .xlsx (the hunter's stdlib reader) -> rows."""
    if raw[:4] == b"PK\x03\x04":
        out: dict[str, list[list[Any]]] = _W().xlsx_sheets(raw)
        return out
    from libs.data.xls_reader import read_xls
    return {s.name: s.rows() for s in read_xls(raw)}


# --------------------------------------------------------------------------- TFX: the parser --
#: Click 365 pair labels (Japanese, as the exchange writes them) -> MT5 symbol.
TFX_PAIRS: dict[str, str] = {
    "米ドル/円": "USDJPY", "ユーロ/円": "EURJPY", "英ポンド/円": "GBPJPY", "ポンド/円": "GBPJPY",
    "豪ドル/円": "AUDJPY", "オーストラリアドル/円": "AUDJPY", "NZドル/円": "NZDJPY",
    "ニュージーランドドル/円": "NZDJPY", "カナダドル/円": "CADJPY", "スイスフラン/円": "CHFJPY",
    "南アフリカランド/円": "ZARJPY", "南アランド/円": "ZARJPY", "メキシコペソ/円": "MXNJPY",
    "トルコリラ/円": "TRYJPY", "ノルウェークローネ/円": "NOKJPY",
    "スウェーデンクローナ/円": "SEKJPY",
    "香港ドル/円": "HKDJPY", "シンガポールドル/円": "SGDJPY", "ポーランドズロチ/円": "PLNJPY",
    "中国人民元/円": "CNHJPY", "人民元/円": "CNHJPY", "インドルピー/円": "INRJPY",
    "ユーロ/米ドル": "EURUSD", "英ポンド/米ドル": "GBPUSD", "ポンド/米ドル": "GBPUSD",
    "豪ドル/米ドル": "AUDUSD", "NZドル/米ドル": "NZDUSD", "米ドル/カナダドル": "USDCAD",
    "米ドル/スイスフラン": "USDCHF", "ユーロ/英ポンド": "EURGBP", "ユーロ/スイスフラン": "EURCHF",
    "英ポンド/スイスフラン": "GBPCHF", "豪ドル/NZドル": "AUDNZD",
}
_TFX_KEYS = {_norm(k).upper(): v for k, v in TFX_PAIRS.items()}


def tfx_pair(v: Any) -> str | None:
    """A cell naming a Click 365 pair -> its MT5 symbol. ラージ (100k-lot) rows are a different
    contract unit and are not summed into the standard pair: they read None."""
    s = _norm(v).upper()
    if not s or "ラージ" in s or "LARGE" in s:
        return None
    s = s.replace("・", "")
    if s in _TFX_KEYS:
        return _TFX_KEYS[s]
    m = re.fullmatch(r"([A-Z]{3})/?([A-Z]{3})", s)
    if m and m[2] in ("JPY", "USD", "CHF", "GBP", "CAD", "NZD"):
        return m[1] + m[2]
    return None


def _side(v: Any) -> str | None:
    """'long' for a BUY header, 'short' for a SELL header, else None (売買 / 比 / 差 are not)."""
    s = _norm(v)
    if not s or len(s) > 12 or any(x in s for x in ("比", "差", "増減", "計")):
        return None
    sell, buy = "売" in s, "買" in s
    if sell and not buy:
        return "short"
    if buy and not sell:
        return "long"
    return None


def parse_tfx_sellbuy(raw: bytes) -> list[dict[str, Any]]:
    """TFX 為替売買動向 workbook -> [{date, symbol, long, short}].

    Read by LABELS, never by position: a currency-pair label names the row (or the column group),
    a 売 / 買 header names the side, a date header names the observation. Both orientations
    are read:
        pairs down the rows, (date x side) across the columns     (the file's latest four weeks)
        dates down the rows, (pair x side) across the columns
    A record is kept only when BOTH sides are present and non-negative."""
    out: dict[tuple[date, str], dict[str, float]] = {}
    for rows in sheets_of(raw).values():
        _tfx_sheet(rows, out)
    recs = [{"date": d, "symbol": sym, "long": v["long"], "short": v["short"]}
            for (d, sym), v in sorted(out.items()) if "long" in v and "short" in v
            and v["long"] >= 0 and v["short"] >= 0]
    return recs


def _tfx_sheet(rows: list[list[Any]], out: dict[tuple[date, str], dict[str, float]]) -> None:
    pairs = [(r, c, p) for r, row in enumerate(rows) for c, v in enumerate(row)
             if (p := tfx_pair(v))]
    if not pairs:
        return
    by_row: dict[int, list[tuple[int, str]]] = {}
    for r, c, p in pairs:
        by_row.setdefault(r, []).append((c, p))
    sheet_dates = sorted({d for row in rows for v in row if (d := _cell_date(v, serial=False))})
    header_row = next((r for r in sorted(by_row) if len(by_row[r]) >= 2), None)
    if header_row is not None:                                   # dates down the rows
        pair_cols = sorted(by_row[header_row])
        sides: dict[int, str] = {}
        for r in range(header_row, min(header_row + 3, len(rows))):
            for c, v in enumerate(rows[r]):
                if (s := _side(v)):
                    sides[c] = s
        for row in rows[header_row + 1:]:
            d = next((x for v in row[:max(1, pair_cols[0][0])] if (x := _cell_date(v))), None)
            if d is None:
                continue
            for c, s in sides.items():
                owner = [p for pc, p in pair_cols if pc <= c]
                val = _num(row[c]) if c < len(row) else None
                if owner and val is not None:
                    out.setdefault((d, owner[-1]), {})[s] = val
        return
    first = min(by_row)                                          # pairs down the rows
    sides = {}
    dates: list[tuple[int, date]] = []
    for r in range(first):
        for c, v in enumerate(rows[r]):
            if (s := _side(v)):
                sides[c] = s
            if (d := _cell_date(v)):
                dates.append((c, d))
    for r, cols in by_row.items():
        sym = cols[0][1]
        row = rows[r]
        for c, s in sides.items():
            left = [d for dc, d in sorted(dates) if dc <= c]
            d = left[-1] if left else (sheet_dates[-1] if sheet_dates else None)
            val = _num(row[c]) if c < len(row) else None
            if d is not None and val is not None:
                out.setdefault((d, sym), {})[s] = val


# --------------------------------------------------------------------------- JPX: the parser --
#: Investor-type labels (the Japanese half of JPX's bilingual row label) -> series stem.
JPX_INVESTORS: dict[str, str] = {
    "海外投資家": "foreigners", "個人": "individuals", "信託銀行": "trust_banks",
    "投資信託": "investment_trusts", "事業法人": "business_cos", "生保損保": "insurers",
    "都銀地銀等": "city_regional_banks", "その他金融機関": "other_financials",
    "その他法人等": "other_cos", "証券会社": "securities_cos", "自己計": "proprietary",
    "委託計": "brokerage", "総計": "total", "法人": "institutions",
    "金融機関": "financial_institutions",
}
_MARKETS = (("プライム", "prime"), ("第一部", "first_section"), ("二市場", "two_markets"),
            ("東証全体", "tse_all"), ("スタンダード", "standard"), ("グロース", "growth"),
            ("第二部", "second_section"), ("マザーズ", "mothers"), ("JASDAQ", "jasdaq"),
            ("ジャスダック", "jasdaq"))
#: The market whose flows the series carry, most preferred first (the index market).
MARKET_PRIORITY = ("prime", "first_section", "tse_all", "two_markets")


def jpx_investor(v: Any) -> str | None:
    s = _norm(v)
    s = re.split(r"[A-Za-z]", s, maxsplit=1)[0]
    s = s.replace("・", "").replace("･", "").replace("(", "").replace(")", "")
    return JPX_INVESTORS.get(s)


def _market_of(v: Any) -> str | None:
    s = _norm(v)
    for k, m in _MARKETS:
        if k in s:
            return m
    return None


#: Matched AFTER NFKC, which folds full-width tildes, hyphens and brackets to ASCII.
_DASH = r"[~〜\-―]"
_RANGE = (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日?" + _DASH
                     + r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日"),
          re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})" + _DASH
                     + r"(?:(\d{4})/)?(\d{1,2})/(\d{1,2})"),
          re.compile(r"(\d{4})年\d{1,2}月第\d週\((\d{1,2})/(\d{1,2})" + _DASH
                     + r"()(\d{1,2})/(\d{1,2})"))
_FNAME_RANGE = re.compile(r"stock_1_w_(\d{8})_(\d{8})")


def jpx_week(text: str, filename: str = "") -> tuple[date, date] | None:
    """(first trading day, last trading day) of the reported week: from the file name when it
    carries the range (stock_1_w_YYYYMMDD_YYYYMMDD), else from the sheet's own period text."""
    m = _FNAME_RANGE.search(filename)
    if m:
        a, b = m[1], m[2]
        return (date(int(a[:4]), int(a[4:6]), int(a[6:])),
                date(int(b[:4]), int(b[4:6]), int(b[6:])))
    s = _norm(text)
    for i, rx in enumerate(_RANGE):
        m = rx.search(s)
        if not m:
            continue
        try:
            if i == 2:
                y = int(m[1])
                a = date(y, int(m[2]), int(m[3]))
                b = date(y + (int(m[5]) < int(m[2])), int(m[5]), int(m[6]))
            else:
                y1 = int(m[1])
                a = date(y1, int(m[2]), int(m[3]))
                y2 = int(m[4]) if m[4] else y1 + (int(m[5]) < int(m[2]))
                b = date(y2, int(m[5]), int(m[6]))
        except ValueError:
            continue
        if timedelta(0) <= b - a <= timedelta(days=7):
            return a, b
    return None


def _header_groups(rows: list[list[Any]], r0: int) -> dict[str, int] | None:
    """Above row r0: the VALUE (金額) group's sell / buy / net / total columns, by label."""
    for r in range(r0 - 1, max(-1, r0 - 8), -1):
        row = rows[r]
        cols: dict[str, list[int]] = {"sell": [], "buy": [], "net": [], "total": []}
        for c, v in enumerate(row):
            s = _norm(v)
            if not s or "比" in s:
                continue
            if "差引" in s or "差し引" in s:
                cols["net"].append(c)
            elif "合計" in s:
                cols["total"].append(c)
            elif _side(v) == "short":
                cols["sell"].append(c)
            elif _side(v) == "long":
                cols["buy"].append(c)
        if not (cols["sell"] and cols["buy"] and cols["net"]):
            continue
        value_from = -1
        for rr in range(max(0, r - 3), r + 1):
            for c, v in enumerate(rows[rr]):
                if any(k in _norm(v) for k in ("金額", "代金", "Value")):
                    value_from = c if value_from < 0 else min(value_from, c)
        if value_from < 0 and len(cols["sell"]) >= 2:
            value_from = cols["sell"][1]            # 株数 first, 金額 second (the documented order)
        pick = {k: next((c for c in v if c >= max(value_from, 0)), v[-1])
                for k, v in cols.items() if v}
        return pick
    return None


def parse_jpx_investor_type(raw: bytes, filename: str = "") -> dict[str, Any] | None:
    """One JPX weekly investor-type workbook -> {week_start, week_end, market, rows} where rows is
    {investor: {sell, buy, net, total}} in BILLIONS of yen (the file's 千円 / 1e6).

    Label-driven: the 金額 group's 売り / 買い / 差引き / 合計 columns are found by their headers;
    the documented 12-column layout (株数 sell, ratio, buy, ratio, net, total, then the same for
    金額) is the fallback. Every row must satisfy the file's own conservation law,
    net = buy - sell, or it is dropped: a misread column cannot pass it."""
    sheets = sheets_of(raw)
    text = " ".join(str(v) for rows in sheets.values() for row in rows for v in row
                    if isinstance(v, str))
    week = jpx_week(text, filename)
    if week is None:
        return None
    by_market: dict[str, dict[str, dict[str, float]]] = {}
    for name, rows in sheets.items():
        market = _market_of(name) or "unnamed"
        for r, row in enumerate(rows):
            for v in row:
                if isinstance(v, str) and (m := _market_of(v)) and not jpx_investor(v):
                    market = m
            label_c = next((c for c, v in enumerate(row) if isinstance(v, str) and _norm(v)), None)
            if label_c is None:
                continue
            inv = jpx_investor(row[label_c])
            if inv is None:
                continue
            vals = _jpx_row(rows, r, label_c)
            if vals is None:
                continue
            by_market.setdefault(market, {}).setdefault(inv, vals)
    market: str | None = next((m for m in MARKET_PRIORITY if m in by_market), None)
    market = market or next(iter(by_market), None)
    if market is None:
        return None
    return {"week_start": week[0], "week_end": week[1], "market": market,
            "rows": by_market[market]}


def _jpx_row(rows: list[list[Any]], r: int, label_c: int) -> dict[str, float] | None:
    row = rows[r]
    hdr = _header_groups(rows, r)
    cand: dict[str, float | None] = {}
    if hdr:
        cand = {k: (_num(row[c]) if c < len(row) else None) for k, c in hdr.items()}
    if not _conserves(cand):
        nums = [x for v in row[label_c + 1:] if (x := _num(v)) is not None]
        cand = ({"sell": nums[6], "buy": nums[8], "net": nums[10], "total": nums[11]}
                if len(nums) >= 12 else {})
        if not _conserves(cand):
            return None
    return {k: float(v) / 1e6 for k, v in cand.items() if v is not None}


def _conserves(c: Mapping[str, float | None]) -> bool:
    s, b, n = c.get("sell"), c.get("buy"), c.get("net")
    if s is None or b is None or n is None:
        return False
    return abs((b - s) - n) <= 1.0 + 1e-9 * max(abs(b), abs(s))


_JPX_LINK = re.compile(r"""href\s*=\s*["']([^"']*?(stock_1_w_\d{8}_\d{8}\.xlsx|"""
                       r"""stock_val_1_\d{6}\.xls))["']""", re.I)
_ARCHIVE_LINK = re.compile(r"""href\s*=\s*["']([^"']*?00-00-archives-\d+\.html)["']""", re.I)


def jpx_links(html: str, base: str) -> tuple[dict[str, str], list[str]]:
    """An index / archive page -> ({file name: absolute URL} of the VALUE files, archive pages).
    Share-count files (stock_vol_*) are skipped: the value file carries the money."""
    files = {m[2]: urllib.parse.urljoin(base, m[1]) for m in _JPX_LINK.finditer(html)}
    pages = sorted({urllib.parse.urljoin(base, m[1]) for m in _ARCHIVE_LINK.finditer(html)})
    return files, pages


# -------------------------------------------------------------------------- FFAJ: the parser --
_FFAJ_XLS = re.compile(r"""href\s*=\s*["']([^"']*?trading_vol_and_position\.xlsx?)["']""", re.I)
_FFAJ_UPDATED = re.compile(r"更新日[:：]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日")  # noqa: RUF001
_ERAS = {"令和": 2018, "平成": 1988, "R": 2018, "H": 1988}


def ffaj_links(html: str, base: str) -> tuple[str | None, date | None]:
    """The fx_flash page -> (the 取引状況 workbook URL, the page's own 更新日). The workbook moves
    to a new /wp-content/uploads/YYYY/MM/ folder every month, so it is found, never typed."""
    links = [urllib.parse.urljoin(base, m[1]) for m in _FFAJ_XLS.finditer(html)]
    m = _FFAJ_UPDATED.search(unicodedata.normalize("NFKC", html).replace(" ", ""))
    upd = None
    if m:
        try:
            upd = date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            upd = None
    return (sorted(links)[-1] if links else None), upd


def _month_of(v: Any) -> tuple[int, int] | None:
    """A month cell: an Excel serial, '2026年9月', '2026/09', '2026.9', '令和8年9月', 'R8.9'."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 36000 < float(v) < 60000:
        d = date(1899, 12, 30) + timedelta(days=int(float(v)))
        return d.year, d.month
    s = _norm(v)
    if not s:
        return None
    m = re.match(r"(令和|平成|R|H)(\d{1,2}|元)[年.](\d{1,2})月?$", s)
    if m:
        y = _ERAS[m[1]] + (1 if m[2] == "元" else int(m[2]))
        mo = int(m[3])
    else:
        m = re.match(r"(\d{4})[年/.\-](\d{1,2})(?:月|[/.\-]\d{1,2}日?)?$", s)
        if not m:
            return None
        y, mo = int(m[1]), int(m[2])
    return (y, mo) if 1 <= mo <= 12 and 2000 <= y <= 2100 else None


def parse_ffaj_positions(raw: bytes) -> list[dict[str, Any]]:
    """FFAJ 取引状況 workbook -> [{year, month, long, short}] (100 million yen, month end).

    Read by LABELS: the header row naming 売建玉 and 買建玉 (any cell with 売 / 買 that is
    not a ratio, a change or a total) gives the side columns; a month cell starts each data row.
    When a sheet carries several 売 / 買 groups (positions by member type, say) the first group
    -- the all-member total, the file's leading table -- is read. A month is kept only when both
    sides are present and non-negative; its LATEST sheet wins (a revision supersedes)."""
    out: dict[tuple[int, int], dict[str, float]] = {}
    for rows in sheets_of(raw).values():
        hdr = None
        for r, row in enumerate(rows):
            cols = {c: s for c, v in enumerate(row)
                    if (s := _side(v)) and "建玉" in _norm(v)}
            if any(s == "long" for s in cols.values()) and any(s == "short" for s in cols.values()):
                hdr = (r, cols)
                break
        if hdr is None:
            continue
        r0, cols = hdr
        sell = min(c for c, s in cols.items() if s == "short")
        buy = min(c for c, s in cols.items() if s == "long")
        for row in rows[r0 + 1:]:
            mo = next((x for v in row[:min(sell, buy)] if (x := _month_of(v))), None)
            if mo is None:
                continue
            s_v = _num(row[sell]) if sell < len(row) else None
            b_v = _num(row[buy]) if buy < len(row) else None
            if s_v is None or b_v is None or s_v < 0 or b_v < 0:
                continue
            out[mo] = {"short": s_v, "long": b_v}
    return [{"year": y, "month": m, **v} for (y, m), v in sorted(out.items())]


# ------------------------------------------------------------------------------- features ----
def _z(s: Any, window: int) -> Any:
    m = s.rolling(window, min_periods=Z_MIN).mean()
    sd = s.rolling(window, min_periods=Z_MIN).std()
    return (s - m) / sd.where(sd > 0)


def tfx_features(wide: Any) -> Any:
    return book_features(wide, Z_WINDOW_TFX)


def ffaj_features(wide: Any) -> Any:
    return book_features(wide, Z_WINDOW_FFAJ)


def book_features(wide: Any, window: int) -> Any:
    """Per pair (columns long, short; index the observation date, ascending): the retail book.

        net_ratio      (long - short) / (long + short): +1 all long. Mrs Watanabe's tilt
        net_chg        its period-on-period change
        contrarian_z   -z(net_ratio) over `window` periods: + when retail is unusually SHORT
        crowding       |z(net_ratio)|: how far the crowd sits from its own normal, either way
        oi_logchg      log change of total open interest: leverage building or unwinding
    Every value at period t reads only periods <= t, so it is known at t's publication. Used
    for Click 365 per pair (weekly, Z_WINDOW_TFX) and the FFAJ whole book (monthly)."""
    import numpy as np
    tot = wide["long"] + wide["short"]
    out = wide[["long", "short"]].copy()
    out["net_ratio"] = (wide["long"] - wide["short"]) / tot.where(tot > 0)
    out["net_chg"] = out["net_ratio"].diff()
    z = _z(out["net_ratio"], window)
    out["contrarian_z"] = -z
    out["crowding"] = z.abs()
    out["oi_logchg"] = np.log(tot.where(tot > 0)).diff()
    return out


def jpx_features(wide: Any) -> Any:
    """Weekly net value by investor type (bn JPY, index the week's start) -> the flow features.

        foreign_net_z            z(foreigners net) over Z_WINDOW_JPX weeks
        individual_net_z         z(individuals net): the retail contrarian leg
        foreign_minus_individual_bn  foreigners net - individuals net (who is taking the other side)
        foreign_net_4w_bn        four-week sum of foreign net buying (persistence of the flow)
        trust_bank_net_z         z(trust banks net): the pension-rebalancing footprint
        foreign_net_share        foreigners net / total turnover"""
    out = wide.copy()
    f = wide.get("foreigners_net_bn")
    i = wide.get("individuals_net_bn")
    if f is not None:
        out["foreign_net_z"] = _z(f, Z_WINDOW_JPX)
        out["foreign_net_4w_bn"] = f.rolling(4, min_periods=4).sum()
        tot = wide.get("total_turnover_bn")
        if tot is not None:
            out["foreign_net_share"] = f / tot.where(tot > 0)
    if i is not None:
        out["individual_net_z"] = _z(i, Z_WINDOW_JPX)
    if f is not None and i is not None:
        out["foreign_minus_individual_bn"] = f - i
    t = wide.get("trust_banks_net_bn")
    if t is not None:
        out["trust_bank_net_z"] = _z(t, Z_WINDOW_JPX)
    return out


# ------------------------------------------------------------------ store (the hunter's PIT) --
def _W() -> Any:
    try:
        from research import world_dataset_hunter as W
    except ImportError:                                                   # pragma: no cover
        import world_dataset_hunter as W  # type: ignore[import-not-found,no-redef]
    return W


def _held_first_vintage(dataset: str) -> Any:
    """The stored frame's first vintage per (series, period): what the desk knew first."""
    W = _W()
    frame = W._load_frame(W.dataset_path(PROVIDER, dataset))
    if frame is None or len(frame) == 0:
        return None
    return frame.sort_values("first_seen_utc").drop_duplicates(["series_code", "period"],
                                                               keep="first")


def _store(dataset: str, name: str, raw_codes: Iterable[str], new_raw: list[dict[str, Any]],
           features: Callable[[Any], Any], *, now: datetime, pin: list[str],
           access: dict[str, Any], policy_key: str, qstats: Any,
           freq: str = "weekly") -> dict[str, Any]:
    """Merge newly parsed raw points [{period, code, value, available_utc}] with the held first
    vintage, compute the features over the union, and ingest raw + features (one PIT merge).
    A feature's stamp is its week's raw publication stamp."""
    import pandas as pd
    W = _W()
    held = _held_first_vintage(dataset)
    rows: dict[tuple[str, str], tuple[float, str]] = {}
    if held is not None:
        for code, per, val, av in zip(held["series_code"], held["period"], held["value"],
                                      held["available_time"], strict=True):
            if code in raw_codes:
                rows[(str(code), str(per))] = (float(val), pd.Timestamp(av).isoformat())
    for p in new_raw:
        rows.setdefault((p["code"], p["period"]), (float(p["value"]), p["available_utc"]))
    if not rows:
        return {"rows_added": 0, "series": 0, "passed": 0, "rows_total": 0}
    long = pd.DataFrame([(c, per, v, a) for (c, per), (v, a) in rows.items()],
                        columns=["series_code", "period", "value", "available_utc"])
    wide = long.pivot_table(index="period", columns="series_code", values="value",
                            aggfunc="last").sort_index()
    avail = long.groupby("period")["available_utc"].max()
    feat = features(wide)
    extra = []
    for col in feat.columns:
        if col in wide.columns:
            continue
        for per, v in feat[col].items():
            if v == v and v is not None and math.isfinite(float(v)):
                extra.append((col, per, float(v), avail[per]))
    allrows = pd.concat([long, pd.DataFrame(extra, columns=long.columns)], ignore_index=True)
    allrows["freq"] = freq
    series = W.series_from_long(allrows, freq=freq, hint=name)
    res = W.ingest_series(PROVIDER, dataset, name, series, now=now, base_score=6.0,
                          qstats=qstats, pin_instruments=pin)
    mp = W.meta_path(PROVIDER, dataset)
    meta = W._read_json(mp, {}) or {}
    meta["access"] = {**access, "policy_row": policy_key,
                      "live_sizing_allowed": live_sizing_allowed(policy_key),
                      "use": ("live sizing permitted by a quoted clause"
                              if live_sizing_allowed(policy_key) else
                              "RESEARCH-ONLY: no clause permits live sizing; mined, featured and "
                              "judged in full, never sized")}
    meta["pack"] = PACK
    W.write_json(mp, meta, indent=None)
    return dict(res)


# ----------------------------------------------------------------------------------- doors ----
def tfx_dataset(symbol: str) -> str:
    return f"TFX_C365_{symbol}"


TFX_DATASET_PREFIX = "TFX_C365_"
JPX_DATASET = "JPX_INVESTOR_TYPE"
FFAJ_DATASET = "FFAJ_OTC_FX_POSITIONS"
DOORS: dict[str, dict[str, Any]] = {
    "TFX_CLICK365": {"url": TFX_FILE, "policy": TFX_POLICY, "source_id": "tfx_click365",
                     "name": "TFX Click 365 retail FX open interest, sell vs buy, per pair"},
    "JPX_INVESTOR_TYPE": {"url": JPX_INDEX, "policy": JPX_POLICY,
                          "source_id": "jpx_investor_type",
                          "name": "JPX weekly trading value by investor type (TSE Prime)"},
    "FFAJ_OTC_FX": {"url": FFAJ_PAGE, "policy": FFAJ_POLICY, "source_id": "ffaj_otc_fx",
                    "name": "FFAJ monthly OTC retail FX open positions, sell vs buy"},
}


def _door_row(cat: dict[str, Any], door: str, now: datetime) -> dict[str, Any]:
    W = _W()
    d = DOORS[door]
    row: dict[str, Any] = cat["datasets"].setdefault(
        f"{PROVIDER}/{door}", {"provider": PROVIDER, "code": door, "lifecycle": "DISCOVERED",
                               "discovered_at": W._iso(now), "source": "direct"})
    row.update({"name": d["name"], "pack": PACK, "policy_row": d["policy"], "url": d["url"]})
    return row


def _due(row: Mapping[str, Any], now: datetime) -> bool:
    W = _W()
    nd = W._parse_iso(row.get("next_due"))
    return nd is None or nd <= now


def _tfx_pass(row: dict[str, Any], transport: Transport, now: datetime, qstats: Any,
              access: dict[str, Any]) -> int:
    recs = parse_tfx_sellbuy(transport(TFX_FILE, HTTP_TIMEOUT_S))
    if not recs:
        raise Transient("parser read zero pair rows")
    W = _W()
    universe = {s for s, _, _ in W.hypothesis_universe()}
    by_sym: dict[str, list[dict[str, Any]]] = {}
    for r in recs:
        per = (r["date"] - timedelta(days=6)).isoformat()      # weekly period ending on the obs
        av = tfx_publication(r["date"]).isoformat()
        for side in ("long", "short"):
            by_sym.setdefault(r["symbol"], []).append(
                {"code": side, "period": per, "value": r[side], "available_utc": av})
    added = 0
    pairs = []
    for sym, pts in sorted(by_sym.items()):
        res = _store(tfx_dataset(sym), f"TFX Click 365 {sym} retail open interest",
                     ("long", "short"), pts, tfx_features, now=now, pin=[sym], access=access,
                     policy_key=TFX_POLICY, qstats=qstats)
        added += int(res["rows_added"])
        pairs.append(sym)
    row["pairs"] = pairs
    row["pairs_in_universe"] = sorted(p for p in pairs if p in universe)
    row["last_obs"] = max(r["date"] for r in recs).isoformat()
    return len(recs)


def _jpx_pass(row: dict[str, Any], transport: Transport, now: datetime, qstats: Any,
              access: dict[str, Any]) -> int:
    pages = [JPX_INDEX, JPX_ARCHIVE]
    links: dict[str, str] = {}
    done_pages = set(row.get("archive_pages_done") or [])
    found_pages: list[str] = []
    for url in pages:
        html = transport(url, HTTP_TIMEOUT_S).decode("utf-8", "replace")
        f, p = jpx_links(html, url)
        links.update(f)
        found_pages += p
    older = [p for p in sorted(set(found_pages)) if p not in pages and p not in done_pages]
    for url in older[:JPX_ARCHIVE_PAGES_PER_PASS]:
        try:
            f, _ = jpx_links(transport(url, HTTP_TIMEOUT_S).decode("utf-8", "replace"), url)
        except Missing:
            f = {}
        links.update(f)
        done_pages.add(url)
    row["archive_pages_done"] = sorted(done_pages)
    done = set(row.get("files_done") or [])
    bad = set(row.get("files_unparsed") or [])
    todo = sorted((n for n in links if n not in done and n not in bad), key=_jpx_sort, reverse=True)
    pts: list[dict[str, Any]] = []
    for fname in todo[:JPX_FILES_PER_PASS]:
        try:
            got = parse_jpx_investor_type(transport(links[fname], HTTP_TIMEOUT_S), fname)
        except Missing:
            continue
        except HardStop:
            raise
        except Exception:
            got = None
        if not got:
            bad.add(fname)
            continue
        done.add(fname)
        per = (got["week_end"] - timedelta(days=got["week_end"].weekday())).isoformat()
        av = jpx_publication(got["week_end"]).isoformat()
        for inv, v in got["rows"].items():
            if "net" in v:
                pts.append({"code": f"{inv}_net_bn", "period": per, "value": v["net"],
                            "available_utc": av})
            if inv == "total" and "total" in v:
                pts.append({"code": "total_turnover_bn", "period": per, "value": v["total"],
                            "available_utc": av})
        row["market"] = got["market"]
    row["files_done"] = sorted(done)
    row["files_unparsed"] = sorted(bad)
    row["files_listed"] = len(links)
    row["backfill_remaining"] = max(0, len(links) - len(done) - len(bad))
    if not pts:
        if links and not todo:
            return -1                                   # nothing new published: not an empty run
        raise Transient("no investor-type file parsed this pass" if links else
                        "index pages listed no investor-type files")
    raw_codes = {p["code"] for p in pts} | {f"{s}_net_bn" for s in JPX_INVESTORS.values()} | \
        {"total_turnover_bn"}
    _store(JPX_DATASET, "JPX weekly trading value by investor type", raw_codes, pts,
           jpx_features, now=now, pin=["JPN225", "USDJPY"], access=access,
           policy_key=JPX_POLICY, qstats=qstats)
    return len(pts)


def _jpx_sort(fname: str) -> str:
    m = _FNAME_RANGE.search(fname)
    if m:
        return m[2]
    m2 = re.search(r"stock_val_1_(\d{2})(\d{2})(\d{2})", fname)
    return f"20{m2[1]}{m2[2]}{m2[3]}" if m2 else fname


def _ffaj_pass(row: dict[str, Any], transport: Transport, now: datetime, qstats: Any,
               access: dict[str, Any]) -> int:
    html = transport(FFAJ_PAGE, HTTP_TIMEOUT_S).decode("utf-8", "replace")
    url, updated = ffaj_links(html, FFAJ_PAGE)
    if url is None:
        raise Transient("fx_flash page listed no trading_vol_and_position.xls")
    recs = parse_ffaj_positions(transport(url, HTTP_TIMEOUT_S))
    if not recs:
        raise Transient("parser read zero month rows")
    pts = []
    for r in recs:
        per = f"{r['year']:04d}-{r['month']:02d}"
        av = ffaj_publication(r["year"], r["month"], updated).isoformat()
        for side in ("long", "short"):
            pts.append({"code": side, "period": per, "value": r[side], "available_utc": av})
    _store(FFAJ_DATASET, "FFAJ OTC retail FX open positions (100m JPY)", ("long", "short"), pts,
           ffaj_features, now=now, pin=["USDJPY", "AUDJPY"], access=access,
           policy_key=FFAJ_POLICY, qstats=qstats, freq="monthly")
    row["file_url"] = url
    row["page_updated"] = updated.isoformat() if updated else None
    row["last_obs"] = max(f"{r['year']:04d}-{r['month']:02d}" for r in recs)
    return len(recs)


_PASSES: dict[str, Callable[..., int]] = {}


def fetch_doors(cat: dict[str, Any], *, now: datetime, transport: Transport | None = None,
                stats: Any = None, qstats: Any = None,
                until: float | None = None) -> dict[str, Any]:
    """Every due door, once. Updates its catalog row: access label, liveness, the hard stop."""
    import time
    from collections import Counter
    W = _W()
    t = transport or desk_transport
    stats = stats if stats is not None else Counter()
    qstats = qstats if qstats is not None else Counter()
    for door, spec in DOORS.items():
        if until is not None and time.monotonic() >= until:
            break
        row = _door_row(cat, door, now)
        if row.get("hard_stop") and not (row["hard_stop"] or {}).get("released_by"):
            row["pack_state"] = "HARD_STOP"
            stats[f"{PACK}:hard_stop_standing"] += 1
            continue
        if not _due(row, now):
            continue
        row["last_attempt_at"] = W._iso(now)
        try:
            access = access_label(spec["url"], t, spec["policy"])
            row["access"] = access
            n = _PASSES[door](row, t, now, qstats, access)
        except HardStop as hs:
            row["hard_stop"] = {"status": hs.status, "url": hs.url, "why": hs.why,
                                "at": W._iso(now), "waits_for": "a person",
                                "released_by": None}
            row["pack_state"] = "HARD_STOP"
            stats[f"{PACK}:hard_stop"] += 1
            continue
        except (Missing, Transient, W.FetchError, ValueError, KeyError) as exc:
            reason = type(exc).__name__ if not str(exc) else str(exc)[:160]
            row["empty_streak"] = int(row.get("empty_streak") or 0) + 1
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
            row["fail_reason"] = reason
            row["pack_state"] = "EMPTY"
            row["next_due"] = W._iso(now + timedelta(hours=RETRY_FAIL_H))
            stats[f"{PACK}:empty"] += 1
            continue
        row.update({"pack_state": "FETCHED", "empty_streak": 0, "fail_reason": None,
                    "next_due": W._iso(now + timedelta(hours=REFRESH_OK_H))})
        if n >= 0:
            row["fetched_at"] = W._iso(now)
            row["rows_this_pass"] = n
            W._promote(row, "INGESTED")
        stats[f"{PACK}:delivered"] += 1
    return {k: cat["datasets"].get(f"{PROVIDER}/{k}") for k in DOORS}


_PASSES.update({"TFX_CLICK365": _tfx_pass, "JPX_INVESTOR_TYPE": _jpx_pass,
                "FFAJ_OTC_FX": _ffaj_pass})


def door_state(row: Mapping[str, Any] | None) -> str:
    """HARD_STOP > RED (more than PACK_EMPTY_RED_RUNS empty runs) > GREEN > AMBER > UNMEASURED."""
    W = _W()
    r = row or {}
    if r.get("hard_stop") and not (r["hard_stop"] or {}).get("released_by"):
        return "HARD_STOP"
    streak = int(r.get("empty_streak") or 0)
    if streak > W.PACK_EMPTY_RED_RUNS:
        return "RED"
    if r.get("pack_state") == "FETCHED":
        return "GREEN"
    if streak:
        return "AMBER"
    return "UNMEASURED"


def report(cat: dict[str, Any]) -> dict[str, Any]:
    """The pack entry for DATASET_HUNT.json: per door its liveness, access label, terms basis and
    live-sizing verdict, and the series that reach research."""
    from libs.data import terms_fence as _tf
    W = _W()
    doors = []
    for door, spec in DOORS.items():
        row = cat["datasets"].get(f"{PROVIDER}/{door}") or {}
        st = door_state(row)
        pol = _tf.SOURCE_POLICY.get(spec["policy"]) or {}
        d: dict[str, Any] = {
            "dataset": door, "url": spec["url"], "state": st, "policy_row": spec["policy"],
            "empty_streak": int(row.get("empty_streak") or 0),
            "last_attempt_at": row.get("last_attempt_at") or W.UNMEASURED,
            "fetched_at": row.get("fetched_at") or W.UNMEASURED,
            "fail_reason": row.get("fail_reason"),
            "access": row.get("access") or W.UNMEASURED,
            "terms": {"url": (pol.get("terms") or {}).get("url"),
                      "checked_at": (pol.get("terms") or {}).get("checked_at"),
                      "verdict": _tf.terms_verdict(spec["policy"]) if pol else "to_confirm"},
            "live_sizing_allowed": live_sizing_allowed(spec["policy"])}
        if st == "RED":
            d["why"] = (f"{d['empty_streak']} consecutive attempts landed nothing (last: "
                        f"{d['fail_reason']}); RED above {W.PACK_EMPTY_RED_RUNS}")
        if st == "HARD_STOP":
            d["hard_stop"] = row.get("hard_stop")
        if pol and not d["live_sizing_allowed"]:
            d["missed_growth"] = _tf.held_missed_growth(
                spec["policy"], source=f"{PACK}/{door}", live_input_refusal=True)
        doors.append(d)
    series: list[str] = []
    for mp in sorted(W.OBS.glob(f"{PROVIDER}/*.meta.json")) if W.OBS.exists() else []:
        meta = W._read_json(mp, {}) or {}
        if meta.get("pack") != PACK:
            continue
        series += [s["key"] for s in (meta.get("series") or {}).values()
                   if s.get("quality") == "PASS" and s.get("instruments")]
    states = [d["state"] for d in doors]
    verdict = ("RED" if "RED" in states else "HARD_STOP" if "HARD_STOP" in states
               else "GREEN" if all(s == "GREEN" for s in states)
               else "AMBER" if any(s in ("GREEN", "AMBER") for s in states) else W.UNMEASURED)
    red = [f"{PACK}/{d['dataset']}" for d in doors if d["state"] in ("RED", "HARD_STOP")]
    return {"country": "JP", "verdict": verdict, "doors": doors, "red_doors": red,
            "instruments_named": ["USDJPY", "AUDJPY", "JPN225"],
            "sources": {k: v["source_id"] for k, v in DOORS.items()},
            "series_to_research": series or W.UNMEASURED,
            "schedule": "hourly_cycle:world_dataset_hunt (door due every "
                        f"{REFRESH_OK_H:g}h after a landing, {RETRY_FAIL_H:g}h after a failure)",
            "player_footprint": FOOTPRINT_ROWS}


# -------------------------------------------------------------- the player-footprint matrix --
#: PR #659's registry rows for these two sources, filled in. Schema = global_flow_sources.json
#: (`class`, `region`, `targets`, `why`); `adapter` names this module's frame reader and
#: `columns` the exact columns `footprint_frame` returns, so #659 needs no parser of its own.
FOOTPRINT_ROWS: list[dict[str, Any]] = [
    {"id": "tfx_click365", "class": "retail", "region": "JP", "adapter": "jp_retail_flow",
     "store": f"world_datasets/obs/{PROVIDER}/{TFX_DATASET_PREFIX}<SYMBOL>.parquet",
     "columns": ["<sym>_long", "<sym>_short", "<sym>_net_ratio", "<sym>_net_chg",
                 "<sym>_contrarian_z", "<sym>_crowding", "<sym>_oi_logchg"],
     "targets": ["USDJPY", "AUDJPY", "EURJPY", "GBPJPY", "NZDJPY", "ZARJPY", "MXNJPY"],
     "policy_row": TFX_POLICY, "live_sizing_allowed": False,
     "why": ("Click 365 open interest split sell/buy per pair is the Japanese retail FX book "
             "(Mrs Watanabe): a crowded long is the carry trade's unwind fuel, read contrarian.")},
    {"id": "jpx_investor_type", "class": "retail", "region": "JP", "adapter": "jp_retail_flow",
     "also_class": ["institutional", "cross_border"],
     "store": f"world_datasets/obs/{PROVIDER}/{JPX_DATASET}.parquet",
     "columns": [*(f"{s}_net_bn" for s in JPX_INVESTORS.values()), "total_turnover_bn",
                 "foreign_net_z", "individual_net_z", "foreign_minus_individual_bn",
                 "foreign_net_4w_bn", "trust_bank_net_z", "foreign_net_share"],
     "targets": ["JPN225", "USDJPY"],
     "policy_row": JPX_POLICY, "live_sizing_allowed": False,
     "why": ("Weekly TSE Prime value by investor type: foreigners against individuals is the "
             "index's marginal buyer and its contrarian retail leg; trust banks carry the "
             "pension rebalance; foreign equity buying is a yen flow.")},
    {"id": "ffaj_otc_fx", "class": "retail", "region": "JP", "adapter": "jp_retail_flow",
     "store": f"world_datasets/obs/{PROVIDER}/{FFAJ_DATASET}.parquet",
     "columns": ["long", "short", "net_ratio", "net_chg", "contrarian_z", "crowding",
                 "oi_logchg"],
     "units": "100 million JPY, month end", "freq": "monthly",
     "targets": ["USDJPY", "AUDJPY"],
     "policy_row": FFAJ_POLICY, "live_sizing_allowed": False,
     "why": ("FFAJ's monthly OTC retail FX book (every reporting member's customer positions, "
             "sell vs buy): the whole Japanese retail FX crowd, monthly; Click 365 is its weekly, "
             "exchange-traded slice.")},
]


def footprint_frame(sid: str) -> Any:
    """One footprint row's series as #659's `collect` consumes them: indexed by the observation's
    period end (DatetimeIndex, ascending), one column per series, plus `available_utc` (the
    publication instant, the latest of the row's series; tz-aware UTC). Empty when nothing is held.
    TFX columns are prefixed with the lower-case symbol (`usdjpy_net_ratio`)."""
    import pandas as pd
    W = _W()
    if sid == "tfx_click365":
        dsets = sorted(p.name[:-len(".parquet")] for p in (W.OBS / PROVIDER).glob(
            f"{TFX_DATASET_PREFIX}*.parquet")) if (W.OBS / PROVIDER).exists() else []
    elif sid == "jpx_investor_type":
        dsets = [JPX_DATASET]
    elif sid == "ffaj_otc_fx":
        dsets = [FFAJ_DATASET]
    else:
        raise KeyError(sid)
    parts = []
    for ds in dsets:
        held = _held_first_vintage(ds)
        if held is None:
            continue
        prefix = (ds[len(TFX_DATASET_PREFIX):].lower() + "_") if sid == "tfx_click365" else ""
        # the hunter's own PIT rule (`pit_series`): a value watched arriving after the first
        # fetch is known at max(publication, first seen); the back-fill keeps its publication
        first = held["first_seen_utc"].min()
        watched = held["first_seen_utc"] > first + pd.Timedelta(hours=36)
        known = held["available_time"].where(
            ~watched, held[["available_time", "first_seen_utc"]].max(axis=1))
        h = held.assign(col=prefix + held["series_code"].astype(str), known=known)
        wide = h.pivot_table(index="period_end", columns="col", values="value", aggfunc="last")
        wide["available_utc"] = h.groupby("period_end")["known"].max()
        parts.append(wide)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, axis=1)
    if "available_utc" in out.columns:
        av = out["available_utc"]
        out = out.drop(columns="available_utc")
        av = av.max(axis=1) if hasattr(av, "columns") else av
        out["available_utc"] = pd.to_datetime(av, utc=True)
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index))
    return out.sort_index()
