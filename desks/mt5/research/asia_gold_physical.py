"""ASIAN PHYSICAL-GOLD DEMAND STATES FOR THE gold_asia XAUUSD WINDOW (IDEA_QUEUE 245/237/228/215).

Four slow states, each a separate physical-demand axis the Western tape does not see:

  hk_gold_reexports   (row 245) Hong Kong C&SD monthly trade, HKHS4 7108 (gold), with the
                      Chinese Mainland: total exports TO the Mainland minus imports consigned FROM
                      it, in HK$ thousand -- the net HK-to-mainland gold flow -- and its z against
                      its own trailing history. PIT by the release instant (the page's own stamp
                      when it prints one, else the release rule pushed LATE), never month end.
  vn_sjc_premium      (row 237) SJC 1-tael bar buy/sell in VND per tael (37.5 g), converted at
                      the SBV central rate, premium to XAUUSD; premium z and the buy-sell gap.
  th_gold_premium     (row 228) Gold Traders Association 96.5% bar buy/sell in THB per
                      baht-weight (15.244 g x 0.965 fine), converted at the BoT reference rate,
                      premium to XAUUSD; premium z and the number of price announcements per
                      day (the association's own revision count, a local volatility tell).
  cn_sge_deferral     (row 215) SGE Au(T+D) deferral-fee payment direction (交收方向): +1 when the
                      shorts pay the longs (空支付给多: delivery demand exceeds supply, physical
                      tightness), -1 when the longs pay the shorts, its signed streak, and the fee
                      rate when a page prints it (the daily table does not: UNMEASURED).

Beside them, the TURKISH household gold demand state (row 257) for the Europe AND Asia XAUUSD
windows: the CBRT EVDS TRY gold price's premium over XAUUSD x USDTRY, the monthly gold
import-surge z and CBRT gold reserves (terms_fence row tr_evds_gold, LIVE on EVDS's own terms
with EVDS_API_KEY), and Borsa Istanbul's metal-price table on fixtures only (IDEAS_ONLY).

WHO OWNS WHAT -- NO SECOND LANE. Fetching, vintages, PIT stamps, the axis files, the lake series
and the conditioned gold_asia children all belong to `research/alt_proxies.py` (an hourly leg):
each state is one `Source` row there, its parser lives HERE as a pure function, and the SGE
quotation parser lives in `research/fetch_sge_premium.py`, the organ that owns SGE. This module
adds only the arithmetic (unit conversion, premium, PIT z, streak, revision count) and the state
artifact `reports/asia_gold_physical_state.json`, which alt_proxies writes on every pass.

TERMS, ONE REGISTER. Each source is a row of `libs/data/terms_fence.SOURCE_POLICY`. Only a row
whose own terms page was read and quotes a clause is LIVE; the C&SD row quotes DATA.GOV.HK's
terms. The SJC, Gold Traders Association and SGE terms pages could not be read (client error,
JS-only body, no terms page), so those rows are IDEAS_ONLY: never fetched as live input, a
missed-growth line each, and the parsers here are built and tested on fixtures so a flipped row
runs the same day. A source unreachable from the authoring container is UNMEASURED, never zero.

    python desks/mt5/research/asia_gold_physical.py --once [--fixtures DIR] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
TROY_OZ_G = 31.1034768
BAHT_WEIGHT_G = 15.244
TH_BAR_PURITY = 0.965
TAEL_G = 37.5
SJC_PURITY = 0.9999
#: PIT z: the trailing window and the fewest prior points a z is computed from.
Z_WINDOW = {"daily": 60, "monthly": 24}
Z_MIN_N = {"daily": 20, "monthly": 12}

#: The four source ids (alt_proxies Source rows and SOURCE_POLICY rows share them).
HK_ID = "hk_gold_reexports"
VN_ID = "vn_sjc_premium"
TH_ID = "th_gold_premium"
SGE_ID = "cn_sge_deferral"
STATE_IDS = (HK_ID, VN_ID, TH_ID, SGE_ID)
IDEA_ROW = {HK_ID: 245, VN_ID: 237, TH_ID: 228, SGE_ID: 215}
STATE_FILE = "asia_gold_physical_state.json"
#: XAUUSD H1 bar (UTC hour) each local board is compared against: the bar holding the board's
#: last print of the day (SJC ~16:00 ICT, the association ~17:30 ICT).
XAU_HOUR = {VN_ID: 9, TH_ID: 10}


# ============================================================================ arithmetic
def usd_per_oz(local_price: float, grams: float, purity: float, local_per_usd: float) -> float:
    """A local price per unit weight as USD per FINE troy ounce."""
    if grams <= 0 or purity <= 0 or local_per_usd <= 0:
        raise ValueError("grams, purity and the FX rate must be positive")
    return local_price / local_per_usd / (grams * purity) * TROY_OZ_G


def premium_pct(local_usd_oz: float, xau_usd_oz: float) -> float:
    """The local bar's premium over the international price, percent."""
    if xau_usd_oz <= 0:
        raise ValueError("XAUUSD must be positive")
    return (local_usd_oz / xau_usd_oz - 1.0) * 100.0


def pit_z(values: Sequence[float | None], window: int, min_n: int) -> list[float | None]:
    """z of each value against the STRICTLY PRIOR `window` values (never itself, never later).
    Fewer than `min_n` prior values, or a zero spread, is None -- never a 0 that reads as calm."""
    out: list[float | None] = []
    hist: list[float] = []
    for v in values:
        z: float | None = None
        if v is not None and len(hist) >= min_n:
            base = hist[-window:]
            mu = sum(base) / len(base)
            sd = math.sqrt(sum((x - mu) ** 2 for x in base) / (len(base) - 1))
            z = (v - mu) / sd if sd > 0 else None
        out.append(z)
        if v is not None:
            hist.append(float(v))
    return out


def streak(dirs: Sequence[int]) -> list[int]:
    """Signed run length of the direction: +3 = third shorts-pay day in a row; 0 resets."""
    out: list[int] = []
    run = 0
    for d in dirs:
        run = (run + d if run * d > 0 else d) if d else 0
        out.append(run)
    return out


# ============================================================================ row 245: C&SD
#: Trade-IDDS trade-type codes (API Enquiry resource on DATA.GOV.HK, read 2026-10-29):
#: 1 imports, 2 domestic exports, 3 re-exports, 4 total exports, 5 total trade.
_TTYPE_NAME = {"1": "imports", "2": "domestic_exports", "3": "re_exports", "4": "total_exports"}
_PERIOD_KEYS = ("period", "refperiod", "ref_period", "yyyymm", "month")
_TTYPE_KEYS = ("ttype", "trade_type", "tradetype", "tt")
_VALUE_KEYS = ("vcm", "figure", "value", "obs_value", "val")
_RELEASE_KEYS = ("releasedate", "release_date", "lastupdate", "last_update", "released")
_YM = re.compile(r"^(\d{4})-?(\d{2})$")


def _records(doc: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(doc, Mapping):
        yield doc
        for v in doc.values():
            yield from _records(v)
    elif isinstance(doc, list):
        for v in doc:
            yield from _records(v)


def _pick(rec: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    low = {str(k).lower(): v for k, v in rec.items()}
    for k in keys:
        if k in low and low[k] not in (None, ""):
            return low[k]
    return None


def _num(v: Any) -> float | None:
    try:
        x = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _when(v: Any) -> datetime | None:
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d/%m/%Y"):
        try:
            t = datetime.strptime(s, fmt)  # noqa: DTZ007 -- a naive stamp is read as UTC below
        except ValueError:
            continue
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    return None


def parse_csd_trade(body: bytes) -> list[dict[str, Any]]:
    """Trade-IDDS JSON -> [{period: 'YYYY-MM', ttype, value_hkd_k, released}] for HKHS4 7108.

    The API's response field names were not readable from the authoring container (the spec PDF
    is robots-refused there), so this reads ANY record that carries a monthly period, a trade
    type and a value under the names the enquiry page and its sibling C&SD tables use. A record
    missing any of the three is skipped, never guessed; a body with none parses to nothing."""
    try:
        doc = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rec in _records(doc):
        per, tt, val = (_pick(rec, _PERIOD_KEYS), _pick(rec, _TTYPE_KEYS),
                        _num(_pick(rec, _VALUE_KEYS)))
        m = _YM.match(str(per or "").strip())
        if m is None or val is None or str(tt) not in _TTYPE_NAME:
            continue
        key = (f"{m.group(1)}-{m.group(2)}", str(tt))
        if key in seen:
            continue
        seen.add(key)
        out.append({"period": key[0], "ttype": _TTYPE_NAME[key[1]], "value_hkd_k": val,
                    "released": _when(_pick(rec, _RELEASE_KEYS))})
    return out


def hk_net_flow(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Per month: exports TO the Mainland minus imports consigned FROM it (HK$ thousand).
    Total exports when printed, else domestic exports + re-exports; a month missing either leg
    has no net flow (never a one-legged number)."""
    by: dict[str, dict[str, float]] = {}
    for r in rows:
        by.setdefault(str(r["period"]), {})[str(r["ttype"])] = float(r["value_hkd_k"])
    out: dict[str, float] = {}
    for per, legs in by.items():
        exp = legs.get("total_exports")
        if exp is None and {"domestic_exports", "re_exports"} <= set(legs):
            exp = legs["domestic_exports"] + legs["re_exports"]
        if exp is not None and "imports" in legs:
            out[per] = exp - legs["imports"]
    return dict(sorted(out.items()))


# ============================================================================ row 237: SJC + SBV
_SBV_RATE = re.compile(r"T[ỷy]\s*gi[áa]\s*trung\s*t[âa]m[\s\S]{0,160}?"
                       r"(?<![\d.,])(\d{2}[.,]\d{3})(?![\d.,])", re.I)
_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def parse_sjc_prices(body: bytes, branch: str = "Hồ Chí Minh") -> list[dict[str, Any]]:
    """SJC price service JSON -> [{date, buy, sell}] in VND per tael for the 1-tael SJC bar.

    Shape (the public price-board service): {"success": true, "latestDate": "HH:MM dd/mm/yyyy",
    "data": [{"TypeName": "Vàng SJC 1L, 10L, 1KG", "BranchName": ..., "BuyValue": 84500000.0,
    "SellValue": 86500000.0}, ...]}. Only the 1L bar row of `branch` is read; a board quoted in
    thousand VND (values below 1e6) is scaled, a value outside a gold-shaped band is refused."""
    try:
        doc = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(doc, Mapping) or not isinstance(doc.get("data"), list):
        return []
    m = _DMY.search(str(doc.get("latestDate") or ""))
    if m is None:
        return []
    d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    for row in doc["data"]:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("TypeName") or "")
        if "SJC" not in name or "1L" not in name or str(row.get("BranchName") or "") != branch:
            continue
        buy, sell = _num(row.get("BuyValue")), _num(row.get("SellValue"))
        if buy is None or sell is None:
            continue
        if buy < 1e6:                                   # thousand VND per tael
            buy, sell = buy * 1000.0, sell * 1000.0
        if not (1e6 < buy <= sell < 1e9):
            return []
        return [{"date": d.isoformat(), "buy": buy, "sell": sell}]
    return []


def parse_sbv_central_rate(body: bytes) -> list[dict[str, Any]]:
    """SBV page -> [{date, vnd_per_usd}] from its 'Tỷ giá trung tâm' line (VND per USD)."""
    text = body.decode("utf-8", "replace")
    m = _SBV_RATE.search(text)
    dm = _DMY.search(text[m.start(): m.start() + 400] if m else "") or _DMY.search(text)
    if m is None or dm is None:
        return []
    rate = float(m.group(1).replace(".", "").replace(",", ""))
    if not 10_000 < rate < 50_000:
        return []
    d = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
    return [{"date": d.isoformat(), "vnd_per_usd": rate}]


# ============================================================================ the research lane
#: THE ASIAN RETAIL GOLD-DEMAND RESEARCH DOORS (2026-11-04). Two local-premium states for the
#: gold_asia XAUUSD window, MINED AND TESTED IN FULL under LAWS 5e although neither publisher's
#: terms carry a clause permitting live use: their register rows are IDEAS_ONLY + research_only,
#: so `alt_proxies` fetches them on its RESEARCH lane (`research_collect`: polite_fetch.get with
#: robots read as an access LABEL, never `live_input`), keeps them in their own vintage store,
#: and never lets them reach allocation_intel, the conditioned live children or any sizing.
#:
#:   vn_sjc_premium   SJC 1-tael bar (VND per tael, 37.5 g, 99.99%) at Vietcombank's public
#:                    USD transfer rate (portal XML) -> USD per fine oz, premium over XAUUSD in
#:                    USD/oz and %, and the buy-sell gap. SJC reprices INTRADAY: each print is
#:                    stamped at the board's own "HH:MM dd/mm/yyyy" (Vietnam time, UTC+7), and the
#:                    XAUUSD bar it is compared with is the last H1 bar CLOSED before that print.
#:   in_ibja_premium  IBJA 999 gold (INR per 10 g, ex-GST) at the RBI-published FBIL USD/INR
#:                    reference rate -> premium/discount over London in USD/oz and %, for the
#:                    PM (closing) and AM (opening) polls. IBJA polls ~12:00 and ~17:00 IST; the
#:                    reference rate prints ~13:30 IST. NOTE: IBJA's price carries India's import
#:                    duty, so the level sits a duty above London and a duty change is a break;
#:                    the conditioner reads it as a z against its own history.
IN_ID = "in_ibja_premium"
RESEARCH_IDS = (VN_ID, IN_ID)
#: The register rows each research door reads (the price board's row, then its FX leg's row).
RESEARCH_POLICY = {VN_ID: (VN_ID, "vn_vcb_fx"), IN_ID: (IN_ID, "in_rbi_reference_rate")}
ICT = timezone(timedelta(hours=7))
IST = timezone(timedelta(hours=5, minutes=30))
IBJA_GRAMS = 10.0
IBJA_999_PURITY = 0.999
#: IBJA publication, pushed LATE so a stamp is never early: the PM poll (~17:00 IST) and the
#: reference rate (~13:30 IST) are both public by 18:00 IST = 12:30 UTC, the stamp every IBJA
#: and RBI leg of a date carries (the AM poll, public ~12:40 IST, is stamped at it too: late).
IN_PUBLISH_UTC = (12, 30)
#: XAUUSD H1 bar (UTC hour label) the IBJA polls are compared with: the bar closed before each
#: poll (AM ~06:30-07:10 UTC; PM ~11:30 UTC). A broker-time index labels an EARLIER UTC hour, so
#: either reading of the bar clock stays before the poll.
IN_XAU_HOUR = {"am": 6, "pm": 10}
#: Liveness: more than this many consecutive fetch passes that land nothing is RED (the same
#: rule as world_dataset_hunter.PACK_EMPTY_RED_RUNS).
RESEARCH_EMPTY_RED_RUNS = 2

_SJC_STAMP = re.compile(r"(\d{1,2}):(\d{2})\s+(\d{1,2})/(\d{1,2})/(\d{4})")
_VCB_TIME = re.compile(r"<DateTime>\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?"
                       r"\s*([AP]M)?\s*</DateTime>", re.I)
_VCB_USD = re.compile(r"<Exrate\b[^>]*\bCurrencyCode=\"USD\"[^>]*/?>", re.I)
_ATTR = re.compile(r"(\w+)=\"([^\"]*)\"")


def sjc_print_instant(body: bytes) -> datetime | None:
    """The SJC board's own print stamp ("latestDate": "HH:MM dd/mm/yyyy", Vietnam time) in UTC."""
    try:
        doc = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    m = _SJC_STAMP.search(str(doc.get("latestDate") or "")) if isinstance(doc, Mapping) else None
    if m is None:
        return None
    hh, mm, d, mo, y = (int(g) for g in m.groups())
    return datetime(y, mo, d, hh, mm, tzinfo=ICT).astimezone(UTC)


def parse_vcb_rates(body: bytes) -> list[dict[str, Any]]:
    """Vietcombank's public exchange-rate XML -> [{date, vnd_per_usd, vnd_per_usd_sell,
    published_utc}]. <ExrateList><DateTime>M/D/YYYY h:mm:ss AM</DateTime> (Vietnam time) and
    <Exrate CurrencyCode="USD" Buy="25,560.00" Transfer="25,590.00" Sell="25,970.00"/>; the
    TRANSFER rate is the conversion (the bank's own wire rate), Sell is kept beside it."""
    text = body.decode("utf-8-sig", "replace")
    t, u = _VCB_TIME.search(text), _VCB_USD.search(text)
    if t is None or u is None:
        return []
    mo, d, y, hh, mi = (int(t.group(i)) for i in range(1, 6))
    ss = int(t.group(6) or 0)
    ap = (t.group(7) or "").upper()
    if ap == "PM" and hh < 12:
        hh += 12
    elif ap == "AM" and hh == 12:
        hh = 0
    at = datetime(y, mo, d, hh, mi, ss, tzinfo=ICT).astimezone(UTC)
    attrs = dict(_ATTR.findall(u.group(0)))
    mid, sell = _num(attrs.get("Transfer")), _num(attrs.get("Sell"))
    if mid is None or not 10_000 < mid < 50_000:
        return []
    return [{"date": date(y, mo, d).isoformat(), "vnd_per_usd": mid,
             "vnd_per_usd_sell": sell, "published_utc": at}]


_IBJA_TAB = re.compile(r"id=[\"']tab-(am|pm)[\"']", re.I)
_IBJA_ROW = re.compile(r"<tr[^>]*>\s*<td[^>]*>\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*</td>(.*?)</tr>",
                       re.I | re.S)
_TD_NUM = re.compile(r"<td[^>]*>\s*([\d,]+(?:\.\d+)?)\s*</td>", re.I)


def parse_ibja_rates(body: bytes) -> list[dict[str, Any]]:
    """IBJA's rate page (ibjarates.com) -> [{date, session, gold_999, gold_995}] in INR per 10 g.

    The page's "Previous Dates Rate" tables run Date | 999 | 995 | 916 | 750 | 585 | Silver 999 |
    Platinum 999 (dd/mm/yyyy), one table under the `tab-am` panel and one under `tab-pm`. A row
    is read inside the panel it sits in; without panel ids the first table is AM and the second
    PM (the page's own tab order). A 999 value outside a gold-shaped band, or below the 995, is
    refused, never guessed."""
    text = body.decode("utf-8", "replace")
    marks = [(m.start(), m.group(1).lower()) for m in _IBJA_TAB.finditer(text)]
    tables = [m.start() for m in re.finditer(r"<table\b", text, re.I)]
    rows = list(_IBJA_ROW.finditer(text))
    # without panel ids: the dated tables in page order (today's Purity table has no date row)
    dated = sorted({max((t for t in tables if t <= m.start()), default=0) for m in rows})
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for m in rows:
        sess = None
        for pos, name in marks:
            if pos <= m.start():
                sess = name
        if sess is None:
            own = max((t for t in tables if t <= m.start()), default=0)
            sess = "am" if dated.index(own) == 0 else "pm"
        nums = [_num(x) for x in _TD_NUM.findall(m.group(4))]
        if len(nums) < 2 or nums[0] is None or nums[1] is None:
            continue
        g999, g995 = float(nums[0]), float(nums[1])
        if not (20_000 < g999 < 1_000_000) or g995 > g999:
            continue
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        out.setdefault((d, sess), {"date": d, "session": sess, "gold_999": g999,
                                   "gold_995": g995})
    return [out[k] for k in sorted(out)]


_RBI_USD = re.compile(r"INR\s*/\s*1\s*USD\W{0,40}?(\d{2,3}\.\d{2,4})", re.I | re.S)
_RBI_ASAT = re.compile(r"As\s+at\s+[\d.:]+\s*[ap]\.?m\.?\s+of\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
                       re.I)
_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"), start=1)}


def parse_rbi_reference_rate(body: bytes) -> list[dict[str, Any]]:
    """RBI home page 'Current Rates' block -> [{date, inr_per_usd}]: the FBIL USD/INR reference
    rate RBI republishes ("INR / 1 USD : 94.8606", "(As at 1.00pm of November 03, 2026)",
    "(Source : FBIL)"). The date is the block's own; a rate outside 40..200 is refused."""
    text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace"))
    r, a = _RBI_USD.search(text), _RBI_ASAT.search(text)
    if r is None or a is None or a.group(1).lower() not in _MONTHS:
        return []
    rate = float(r.group(1))
    if not 40.0 < rate < 200.0:
        return []
    d = date(int(a.group(3)), _MONTHS[a.group(1).lower()], int(a.group(2)))
    return [{"date": d.isoformat(), "inr_per_usd": rate}]


def in_publication(period: date) -> datetime:
    """When an IBJA poll or the RBI reference rate dated `period` is first knowable (UTC): 18:00
    IST the same day, after the PM poll and the reference rate, so no leg is stamped early."""
    return datetime(period.year, period.month, period.day, *IN_PUBLISH_UTC, tzinfo=UTC)


def xau_hourly_close(paths_universe: Path, symbol: str = "XAUUSD") -> dict[str, float]:
    """{'YYYY-MM-DDTHH': close} of every H1 bar on this box (hour label as the index carries it);
    absent file -> {} (a premium is then UNMEASURED, never 0)."""
    p = paths_universe / f"{symbol}_H1.parquet"
    if not p.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_parquet(p)
        return {pd.Timestamp(i).strftime("%Y-%m-%dT%H"): float(v)
                for i, v in df["close"].items()}
    except Exception:
        return {}


def bar_before(xau_h: Mapping[str, float], at: datetime) -> tuple[float, datetime] | None:
    """The close of the last H1 bar that CLOSED at or before `at`, and that close instant (the
    bar labelled h closes at h+1). Up to six hours back; older is no comparison, never a carry."""
    end = at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    for k in range(1, 7):
        lab = end - timedelta(hours=k)
        v = xau_h.get(lab.strftime("%Y-%m-%dT%H"))
        if v is not None:
            return v, lab + timedelta(hours=1)
    return None


def premium_usd_oz(local_usd_oz: float, xau_usd_oz: float) -> float:
    """The local bar's premium over the international price, USD per fine troy ounce."""
    return local_usd_oz - xau_usd_oz


# ============================================================================ row 228: GTA + BoT
_GTA_ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*</td>\s*"      # date (Gregorian)
    r"<td[^>]*>\s*(\d{1,2})[:.](\d{2})\s*</td>\s*"                          # time
    r"<td[^>]*>\s*(\d{1,3})\s*</td>\s*"                                     # announcement no.
    r"<td[^>]*>\s*([\d,]+(?:\.\d+)?)\s*</td>\s*<td[^>]*>\s*([\d,]+(?:\.\d+)?)\s*</td>",
    re.S)


def parse_gta_history(body: bytes) -> list[dict[str, Any]]:
    """Gold Traders Association price history table -> one row per announcement:
    {date, time, seq, bar_buy, bar_sell} (96.5% bar, THB per baht-weight). The rows the
    association prints are date | time | ครั้งที่ (announcement number) | bar buy | bar sell |
    ...; a Buddhist-era year (> 2400) is converted to the Gregorian year."""
    text = body.decode("utf-8", "replace")
    out: list[dict[str, Any]] = []
    for m in _GTA_ROW.finditer(text):
        y = int(m.group(3))
        y = y - 543 if y > 2400 else y
        buy, sell = _num(m.group(7)), _num(m.group(8))
        if buy is None or sell is None or not (1_000 < buy <= sell < 1_000_000):
            continue
        out.append({"date": date(y, int(m.group(2)), int(m.group(1))).isoformat(),
                    "time": f"{int(m.group(4)):02d}:{m.group(5)}", "seq": int(m.group(6)),
                    "bar_buy": buy, "bar_sell": sell})
    return out


def gta_daily(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """Per day: the LAST announcement's bar buy/sell and the day's announcement count (the
    highest ครั้งที่ printed, or the rows seen when no number is larger)."""
    by: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        by.setdefault(str(r["date"]), []).append(r)
    out: dict[str, dict[str, float]] = {}
    for d, rs in sorted(by.items()):
        last = max(rs, key=lambda r: (int(r["seq"]), str(r["time"])))
        out[d] = {"bar_buy": float(last["bar_buy"]), "bar_sell": float(last["bar_sell"]),
                  "revisions": float(max(len(rs), max(int(r["seq"]) for r in rs)))}
    return out


def parse_bot_reference_rate(body: bytes) -> list[dict[str, Any]]:
    """Bank of Thailand statistics API JSON -> [{date, thb_per_usd}]. Reads any record with a
    `period` date and a `rate` / `mid_rate` (THB per USD), wherever the envelope nests it."""
    try:
        doc = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    out: dict[str, float] = {}
    for rec in _records(doc):
        per = str(_pick(rec, ("period",)) or "")
        rate = _num(_pick(rec, ("rate", "mid_rate", "reference_rate")))
        if re.match(r"^\d{4}-\d{2}-\d{2}$", per) and rate is not None and 10 < rate < 100:
            cur = str(_pick(rec, ("currency_id", "currency")) or "USD").upper()
            if cur == "USD":
                out[per] = rate
    return [{"date": d, "thb_per_usd": r} for d, r in sorted(out.items())]


# ============================================================================ row 215: SGE
def deferral_direction(text: str) -> int:
    """交收方向 -> +1 shorts pay longs (空支付给多: physical tightness), -1 longs pay shorts,
    0 for no payment / an unrecognised cell (never guessed)."""
    t = str(text or "").replace(" ", "")
    if t.startswith("空支付") or t.startswith("空付"):
        return 1
    if t.startswith("多支付") or t.startswith("多付"):
        return -1
    return 0


def sge_deferral_state(rows: Iterable[Mapping[str, Any]],
                       contract: str = "Au(T+D)") -> list[dict[str, Any]]:
    """Daily rows from `fetch_sge_premium.parse_daily_quotation` -> one state row per date for
    `contract`: direction, signed streak, delivery volume, and fee_rate when printed."""
    by = {str(r["date"]): r for r in rows if r.get("contract") == contract}
    days = sorted(by)
    dirs = [deferral_direction(str(by[d].get("direction") or "")) for d in days]
    runs = streak(dirs)
    out = []
    for d, dr, run in zip(days, dirs, runs, strict=True):
        fee = by[d].get("fee_rate")
        out.append({"date": d, "direction": dr, "streak": run,
                    "delivery_lots": by[d].get("delivery_lots"),
                    "fee_rate": fee if fee is not None else UNMEASURED})
    return out


# ============================================================================ row 257: Turkey
#: THE TURKISH HOUSEHOLD GOLD DEMAND STATE (IDEA_QUEUE 257). Turkish households hold gold as the
#: lira's alternative; a domestic TRY gold price running above XAUUSD x USDTRY is local demand
#: and capital flight the London tape sees only later, and a monthly import surge is the same
#: demand crossing the border. Sources: CBRT EVDS (terms_fence row tr_evds_gold, LIVE with the
#: key) for the TRY gold price, monthly gold imports and CBRT gold reserves; Borsa Istanbul's
#: precious-metals table (row tr_bist_gold, IDEAS_ONLY: its notice forbids storing without
#: written consent) parsed on fixtures only; Istanbul Gold Refinery (row tr_iar_gold, UNREAD).
TR_PRICE_ID = "tr_gold_try_price"
TR_IMPORT_ID = "tr_gold_imports"
TR_RESERVE_ID = "tr_gold_reserves"
TR_BIST_ID = "tr_bist_gold"
TR_IDS = (TR_PRICE_ID, TR_IMPORT_ID, TR_RESERVE_ID, TR_BIST_ID)
TR_EVDS_POLICY = "tr_evds_gold"
TR_IAR_POLICY = "tr_iar_gold"
#: The terms_fence row each state reads its policy from (the three EVDS series share one row).
POLICY_OF = {TR_PRICE_ID: TR_EVDS_POLICY, TR_IMPORT_ID: TR_EVDS_POLICY,
             TR_RESERVE_ID: TR_EVDS_POLICY}
#: Policy rows with no state of their own (no readable page shape) that still owe a line.
POLICY_ONLY = (TR_IAR_POLICY,)
ALL_STATE_IDS = (*STATE_IDS, *TR_IDS)
IDEA_ROW.update(dict.fromkeys(TR_IDS, 257))
#: Turkish bullion ("kulce altin") is 995 fine; the offset is a constant inside a level_dev state.
TR_BAR_PURITY = 0.995
#: The XAUUSD and USDTRY H1 bar the TRY price is compared against: 12:00 UTC (15:00 TR), the bar
#: holding the CBRT's afternoon announcement. The bar's time of day is an assumption (the EVDS
#: series does not print one): UNMEASURED until the box compares first_seen_at to it.
TR_XAU_HOUR = 12
#: The EVDS web service takes the key in this request header (the parameter moved out of the URL
#: in 2024); the key is never put in a URL, a log or a vault file.
EVDS_KEY_HEADER = "key"
_EVDS_CODE = re.compile(r"^TP\.[A-Z0-9_.]{2,60}$")
_TARIH_DMY = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
_TARIH_YM = re.compile(r"^(\d{4})-(\d{1,2})$")


#: PIT BY RELEASE. EVDS prints no release stamp, so each series is stamped by its publisher's
#: release clock, pushed LATE: the CBRT's daily gold price for day d is first read the next
#: weekday 06:00 UTC; monthly imports (TÜİK's foreign-trade release, ~the last working day of
#: the next month, 10:00 TR) at month end + 31 days 08:00 UTC; weekly reserves (the CBRT's
#: Thursday 14:30 TR release for the prior Friday) at the reading's date + 6 days 12:00 UTC.
#: The alt_proxies rules ARE these functions; a vintage first seen later keeps its later stamp.
TR_SERIES = {TR_PRICE_ID: "try_per_gram", TR_IMPORT_ID: "gold_imports",
             TR_RESERVE_ID: "gold_reserves"}


def tr_release_at(sid: str, period: date) -> datetime:
    """The instant a Turkish reading for `period` is first knowable (UTC), per the rules above."""
    if sid == TR_IMPORT_ID:
        t = datetime(period.year, period.month, period.day, 8, tzinfo=UTC) + timedelta(days=31)
    elif sid == TR_RESERVE_ID:
        # +6 days from the Friday reading is the Thursday release; a reading dated any other
        # day must still land on a weekday, so this branch takes the same weekend roll.
        t = datetime(period.year, period.month, period.day, 12, tzinfo=UTC) + timedelta(days=6)
    else:
        t = datetime(period.year, period.month, period.day, 6, tzinfo=UTC) + timedelta(days=1)
    while t.weekday() >= 5:
        t += timedelta(days=1)
    return t


def tr_release(sid: str, period: str) -> str:
    """`tr_release_at` for a 'YYYY-MM' (month, dated to its end) or 'YYYY-MM-DD' period."""
    if len(period) == 7:
        d = _month_end(int(period[:4]), int(period[5:7]))
    else:
        d = date.fromisoformat(period[:10])
    return tr_release_at(sid, d).isoformat(timespec="seconds")


def evds_code_ok(code: str) -> bool:
    """A series code is TP.<letters/digits/dots>; anything else never reaches a URL."""
    return bool(_EVDS_CODE.match(str(code or "").strip()))


def evds_url(base: str, code: str, start: date, end: date) -> str:
    """The EVDS series request (the key travels in the `key` header, never here)."""
    if not evds_code_ok(code):
        raise ValueError(f"not an EVDS series code: {code!r}")
    root = base if base.endswith("/") else base + "/"
    return (f"{root}series={code.strip()}&startDate={start:%d-%m-%Y}&endDate={end:%d-%m-%Y}"
            "&type=json")


def _month_end(y: int, m: int) -> date:
    import calendar
    return date(y, m, calendar.monthrange(y, m)[1])


def parse_evds(body: bytes, code: str) -> list[dict[str, Any]]:
    """EVDS series JSON -> [{date, value, freq}]. `items[]` carry `Tarih` and the series column
    named as the code with dots as underscores. Tarih `dd-mm-yyyy` is a day (daily and weekly
    series); `yyyy-m` is a month, dated to its month END. A null or empty cell is absent, never 0;
    a body without the requested column (a wrong code, an error envelope) parses to []."""
    try:
        doc = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    items = doc.get("items") if isinstance(doc, Mapping) else None
    if not isinstance(items, list):
        return []
    col = str(code).strip().replace(".", "_")
    if not col:
        # no code named: read the body's ONE series column, and nothing when there are several
        cols = {str(k) for it in items if isinstance(it, Mapping) for k in it
                if str(k).startswith("TP_")}
        if len(cols) != 1:
            return []
        col = cols.pop()
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, Mapping):
            continue
        v = _num(it.get(col))
        t = str(it.get("Tarih") or "").strip()
        if v is None:
            continue
        m = _TARIH_DMY.match(t)
        if m:
            d, freq = date(int(m.group(3)), int(m.group(2)), int(m.group(1))), "D"
        elif (m := _TARIH_YM.match(t)):
            d, freq = _month_end(int(m.group(1)), int(m.group(2))), "M"
        else:
            continue
        out[d.isoformat()] = {"date": d.isoformat(), "value": v, "freq": freq}
    return [out[k] for k in sorted(out)]


_BIST_ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>\s*(\d{1,2})[./](\d{1,2})[./](\d{4})\s*</td>\s*"
    r"<td[^>]*>\s*([\d.,]+)\s*</td>\s*<td[^>]*>\s*([\d.,]+)\s*</td>", re.I)


def _tr_num(s: str) -> float | None:
    """Turkish number format: '.' groups thousands, ',' is the decimal mark."""
    t = s.strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return _num(t)


def parse_bist_metal_prices(body: bytes) -> list[dict[str, Any]]:
    """Borsa Istanbul precious-metals price history table (Date | Fiyat(TL/Kg) | Fiyat(USD/Ons)
    | Fiyat(EUR/Ons)) -> [{date, try_per_kg, usd_per_oz}]. Built on a fixture: the row is
    IDEAS_ONLY, so these bytes are never fetched as live input."""
    html = body.decode("utf-8", "replace")
    out: dict[str, dict[str, Any]] = {}
    for m in _BIST_ROW.finditer(html):
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        kg, oz = _tr_num(m.group(4)), _tr_num(m.group(5))
        if kg and oz and kg > 0 and oz > 0:
            out[d] = {"date": d, "try_per_kg": kg, "usd_per_oz": oz}
    return [out[k] for k in sorted(out)]


def tr_premium_series(try_per_gram: Mapping[str, float], usdtry: Mapping[str, float],
                      xau: Mapping[str, float], *, purity: float = TR_BAR_PURITY
                      ) -> list[dict[str, Any]]:
    """The domestic TRY gold price over XAUUSD x USDTRY, INNER-joined on date (a day missing a
    leg has no premium, never a carried one), with a PIT z of the premium."""
    rows: list[dict[str, Any]] = []
    for d in sorted(set(try_per_gram) & set(usdtry) & set(xau)):
        px, fx, x = float(try_per_gram[d]), float(usdtry[d]), float(xau[d])
        rows.append({"date": d, "try_per_gram": px, "usdtry": fx, "xau_usd_oz": x,
                     "premium_pct": premium_pct(usd_per_oz(px, 1.0, purity, fx), x)})
    zs = pit_z([r["premium_pct"] for r in rows], Z_WINDOW["daily"], Z_MIN_N["daily"])
    for r, z in zip(rows, zs, strict=True):
        r["premium_z"] = z
    return rows


def tr_import_surge(monthly: Mapping[str, float], published: Mapping[str, str]
                    ) -> list[dict[str, Any]]:
    """Monthly gold imports with the import-surge z against the strictly prior months, each row
    stamped with the instant it was first knowable (the release, never the month end)."""
    pers = sorted(monthly)
    zs = pit_z([monthly[p] for p in pers], Z_WINDOW["monthly"], Z_MIN_N["monthly"])
    return [{"period": p, "imports": monthly[p], "import_surge_z": z,
             "available_time": published.get(p, UNMEASURED)}
            for p, z in zip(pers, zs, strict=True)]


def tr_reserves(weekly: Mapping[str, float], published: Mapping[str, str]
                ) -> list[dict[str, Any]]:
    """CBRT gold reserves per reading and the change on the previous reading (None first)."""
    rows: list[dict[str, Any]] = []
    prev: float | None = None
    for d in sorted(weekly):
        v = float(weekly[d])
        rows.append({"date": d, "gold_reserves": v,
                     "change": None if prev is None else v - prev,
                     "available_time": published.get(d, UNMEASURED)})
        prev = v
    return rows


# ============================================================================ premium series
def premium_series(local: Mapping[str, Mapping[str, float]], fx: Mapping[str, float],
                   xau: Mapping[str, float], *, grams: float, purity: float,
                   fx_key: str) -> list[dict[str, Any]]:
    """Join local bar prices, the FX rate and XAUUSD on date (INNER: a day missing a leg has no
    premium, never a carried one) -> premium on the sell and buy sides, the buy-sell gap, and a
    PIT z of the mid premium."""
    rows: list[dict[str, Any]] = []
    for d in sorted(set(local) & set(fx) & set(xau)):
        px, rate, x = local[d], float(fx[d]), float(xau[d])
        buy = premium_pct(usd_per_oz(float(px["buy"]), grams, purity, rate), x)
        sell = premium_pct(usd_per_oz(float(px["sell"]), grams, purity, rate), x)
        rows.append({"date": d, "premium_buy_pct": buy, "premium_sell_pct": sell,
                     "premium_pct": (buy + sell) / 2.0, "buy_sell_gap_pct": sell - buy,
                     "fx": rate, "fx_key": fx_key, "xau_usd_oz": x,
                     **({"revisions": px["revisions"]} if "revisions" in px else {})})
    zs = pit_z([r["premium_pct"] for r in rows], Z_WINDOW["daily"], Z_MIN_N["daily"])
    for r, z in zip(rows, zs, strict=True):
        r["premium_z"] = z
    return rows


def xau_daily_close(paths_universe: Path, hour_utc: int = 7,
                    symbol: str = "XAUUSD") -> dict[str, float]:
    """XAUUSD close of the `hour_utc` H1 bar per date from the desk's own feed (the gold_asia
    window places at 04:00 UTC in summer; the 07:00 bar is the one the SGE premium uses, so the
    Asian premiums share its clock). Absent file -> {} (the premium is then UNMEASURED)."""
    p = paths_universe / f"{symbol}_H1.parquet"
    if not p.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_parquet(p)
        s = df[df.index.hour == hour_utc]["close"]
        return {str(pd.Timestamp(i).date()): float(v) for i, v in s.items()}
    except Exception:
        return {}


# ============================================================================ the state artifact
def _latest(rows: Sequence[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    if not rows:
        return {}
    r = rows[-1]
    return {k: r.get(k) for k in ("date", *keys) if k in r}


def hk_state(net: Mapping[str, float], published: Mapping[str, str]) -> dict[str, Any]:
    """Monthly net flow rows with a PIT z (strictly prior months) and each month's release
    instant -- the time the state is first knowable, never the month end."""
    pers = sorted(net)
    zs = pit_z([net[p] for p in pers], Z_WINDOW["monthly"], Z_MIN_N["monthly"])
    rows = [{"period": p, "net_flow_hkd_k": net[p], "net_flow_z": z,
             "available_time": published.get(p, UNMEASURED)} for p, z in zip(pers, zs, strict=True)]
    return {"rows": rows, "latest": _latest(rows, ("period", "net_flow_hkd_k", "net_flow_z",
                                                   "available_time"))}


def build_state(*, records: Mapping[str, Mapping[str, Any]],
                hk: Mapping[str, Any] | None = None,
                vn: Sequence[Mapping[str, Any]] | None = None,
                th: Sequence[Mapping[str, Any]] | None = None,
                sge: Sequence[Mapping[str, Any]] | None = None,
                tr: Mapping[str, Sequence[Mapping[str, Any]] | None] | None = None,
                missed_growth: Sequence[Mapping[str, Any]] = (),
                mode: str, now: datetime) -> dict[str, Any]:
    """The artifact: one block per state, each MEASURED (rows and the latest reading) or
    UNMEASURED with its reason. Nothing absent is ever written as zero."""
    from libs.data import terms_fence as tf
    blocks: dict[str, Any] = {}
    data: dict[str, Any] = {HK_ID: hk, VN_ID: vn, TH_ID: th, SGE_ID: sge, **dict(tr or {})}
    for sid in ALL_STATE_IDS:
        rec = dict(records.get(sid) or {})
        got = data.get(sid)
        rows = (got or {}).get("rows") if isinstance(got, Mapping) else got
        pk = POLICY_OF.get(sid, sid)
        blk: dict[str, Any] = {
            "idea_queue_row": IDEA_ROW[sid], "policy_row": pk, "policy_status": tf.status(pk),
            "terms": tf.terms_verdict(pk), "live_input": tf.input_source(sid) is None,
            "collector_status": rec.get("status", UNMEASURED)}
        if rows:
            blk.update({"verdict": "MEASURED", "n": len(rows),
                        "latest": (got or {}).get("latest") if isinstance(got, Mapping)
                        else dict(rows[-1]),
                        "rows": list(rows)[-60:]})
        else:
            blk.update({"verdict": UNMEASURED,
                        "why": rec.get("why") or (
                            "NEEDS_KEY: " + ",".join(tf.SOURCE_POLICY[pk].get("key_env") or ())
                            + " is not set on this host" if tf.status(pk) == tf.NEEDS_KEY
                            else f"{tf.SOURCE_POLICY[pk]['why']}" if tf.input_source(sid)
                            else "no observation on this machine yet (the authoring container "
                                 "cannot reach the host; live yield is the trading box's)")})
        blocks[sid] = blk
    return {"at": now.isoformat(timespec="seconds"), "organ": "asia_gold_physical",
            "producer": "research/alt_proxies.py (hourly leg alt_proxies)", "mode": mode,
            "window": "gold_asia (XAUUSD.asia): conditioned children carry "
                      "params.conditioner = alt:<series>:pace:<op>:0 on the asia selector; "
                      "the Turkish states (row 257) condition the Europe AND Asia windows",
            "states": blocks, "missed_growth_lines": list(missed_growth),
            "n_measured": sum(1 for b in blocks.values() if b["verdict"] == "MEASURED"),
            "rule": ("PIT: monthly HK points are knowable from their release instant, daily "
                     "premiums from the day's last print; z uses strictly prior points only; a "
                     "missing leg is UNMEASURED, never zero")}


def missed_growth_lines() -> list[dict[str, Any]]:
    """GROWTH GOVERNANCE: each IDEAS_ONLY state refused as live input carries its line."""
    from libs.data import terms_fence as tf
    keys = [POLICY_OF.get(sid, sid) for sid in ALL_STATE_IDS if tf.input_source(sid)]
    keys += [k for k in POLICY_ONLY if tf.input_source(k)]
    # a keyed row with its key absent is NEEDS_KEY (a named state), not a terms refusal
    keys = [k for k in keys if tf.SOURCE_POLICY[k]["status"] == tf.IDEAS_ONLY]
    return [tf.held_missed_growth(k, None, live_input_refusal=True)
            for k in dict.fromkeys(keys)]


def write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def fixture_state(fixtures: Path, now: datetime) -> dict[str, Any]:
    """The dry run: every parser and every state computed from fixture bytes, labelled FIXTURE.
    No network. XAUUSD comes from the fixture too, so nothing here is a market reading."""
    def _b(name: str) -> bytes:
        p = fixtures / name
        return p.read_bytes() if p.exists() else b""

    csd = parse_csd_trade(_b(f"{HK_ID}.json"))
    net = hk_net_flow(csd)
    pub = {r["period"]: r["released"].isoformat() for r in csd if r.get("released")}
    xau = {str(k): float(v) for k, v in
           json.loads(_b("asia_gold_xauusd.json") or b"{}").items()}
    sjc = {r["date"]: r for r in parse_sjc_prices(_b(f"{VN_ID}.json"))}
    sbv = {r["date"]: r["vnd_per_usd"] for r in parse_sbv_central_rate(_b(f"{VN_ID}.1.html"))}
    vn = premium_series(sjc, sbv, xau, grams=TAEL_G, purity=SJC_PURITY, fx_key="sbv_central")
    gta = {d: {"buy": v["bar_buy"], "sell": v["bar_sell"], "revisions": v["revisions"]}
           for d, v in gta_daily(parse_gta_history(_b(f"{TH_ID}.html"))).items()}
    bot = {r["date"]: r["thb_per_usd"] for r in parse_bot_reference_rate(_b(f"{TH_ID}.1.json"))}
    th = premium_series(gta, bot, xau, grams=BAHT_WEIGHT_G, purity=TH_BAR_PURITY,
                        fx_key="bot_reference")
    from research import fetch_sge_premium as fsp
    sge = sge_deferral_state(fsp.parse_daily_quotation(_b(f"{SGE_ID}.html")
                                                       .decode("utf-8", "replace")))
    tr = fixture_tr(fixtures, _b, xau)
    recs = {sid: {"status": "FIXTURE"} for sid in ALL_STATE_IDS}
    return build_state(records=recs, hk=hk_state(net, pub), vn=vn, th=th, sge=sge, tr=tr,
                       missed_growth=missed_growth_lines(), mode="fixtures", now=now)


def fixture_tr(fixtures: Path, _b: Any, xau: Mapping[str, float]
               ) -> dict[str, list[dict[str, Any]] | None]:
    """The Turkish states from fixtures: EVDS bodies, the USDTRY H1 close per day as JSON, and
    the Borsa Istanbul table. The release instants are the rules alt_proxies stamps with."""
    codes = json.loads(_b("tr_gold_evds_codes.json") or b"{}")
    usdtry = {str(k): float(v) for k, v in json.loads(_b("tr_gold_usdtry.json") or b"{}").items()}
    price = {r["date"]: r["value"] for r in parse_evds(_b(f"{TR_PRICE_ID}.json"),
                                                       codes.get("price", ""))}
    imp = {r["date"][:7]: r["value"] for r in parse_evds(_b(f"{TR_IMPORT_ID}.json"),
                                                         codes.get("imports", ""))}
    res = {r["date"]: r["value"] for r in parse_evds(_b(f"{TR_RESERVE_ID}.json"),
                                                     codes.get("reserves", ""))}
    bist = {r["date"]: r["try_per_kg"] / 1000.0
            for r in parse_bist_metal_prices(_b(f"{TR_BIST_ID}.html"))}
    return {TR_PRICE_ID: tr_premium_series(price, usdtry, xau) or None,
            TR_IMPORT_ID: tr_import_surge(imp, {p: tr_release(TR_IMPORT_ID, p) for p in imp})
            or None,
            TR_RESERVE_ID: tr_reserves(res, {d: tr_release(TR_RESERVE_ID, d) for d in res})
            or None,
            TR_BIST_ID: tr_premium_series(bist, usdtry, xau) or None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=DESK / "reports" / STATE_FILE)
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    if a.fixtures is not None:
        doc = fixture_state(a.fixtures, now)
    else:
        # The live states are written by the alt_proxies leg; standalone, report what it left.
        from research import alt_proxies
        doc = state_from_alt(alt_proxies.DEFAULT_PATHS, {}, now)
    write(a.out, doc)
    print(json.dumps({sid: b["verdict"] for sid, b in doc["states"].items()}))
    return 0


def state_from_alt(paths: Any, records: Mapping[str, Mapping[str, Any]],
                   now: datetime) -> dict[str, Any]:
    """The live state from the alt_proxies vintage stores (called by its run). Only a LIVE row
    is read; an IDEAS_ONLY row's store is never read as input (it stays UNMEASURED)."""
    from libs.data import terms_fence as tf

    def _store(sid: str) -> dict[str, Any]:
        if tf.input_source(sid):
            return {}
        p = Path(paths.obs_dir) / f"{sid}.json"
        try:
            doc = json.loads(p.read_text("utf-8")) if p.exists() else {}
        except (OSError, json.JSONDecodeError):
            doc = {}
        return doc if isinstance(doc, dict) else {}

    def _series(store: Mapping[str, Any], name: str) -> dict[str, tuple[float, str]]:
        return {str(r["period"]): (float(r["value_first"]), str(r["published_time"]))
                for r in store.values()
                if isinstance(r, Mapping) and r.get("series") == name}

    hk_raw = _series(_store(HK_ID), "net_flow_hkd_k")
    hk = hk_state({p[:7]: v for p, (v, _) in hk_raw.items()},
                  {p[:7]: t for p, (_, t) in hk_raw.items()}) if hk_raw else None
    uni = Path(paths.universe)
    vn_store, th_store = _store(VN_ID), _store(TH_ID)
    vn = th = None
    if vn_store:
        buy, sell = _series(vn_store, "sjc_buy_vnd"), _series(vn_store, "sjc_sell_vnd")
        local = {d: {"buy": buy[d][0], "sell": sell[d][0]} for d in set(buy) & set(sell)}
        fx = {d: v for d, (v, _) in _series(vn_store, "sbv_vnd_per_usd").items()}
        vn = premium_series(local, fx, xau_daily_close(uni, XAU_HOUR[VN_ID]), grams=TAEL_G,
                            purity=SJC_PURITY,
                            fx_key="sbv_central") or None
    if th_store:
        buy, sell = _series(th_store, "bar_buy_thb"), _series(th_store, "bar_sell_thb")
        rev = _series(th_store, "revisions")
        local = {d: {"buy": buy[d][0], "sell": sell[d][0],
                     **({"revisions": rev[d][0]} if d in rev else {})}
                 for d in set(buy) & set(sell)}
        fx = {d: v for d, (v, _) in _series(th_store, "bot_thb_per_usd").items()}
        th = premium_series(local, fx, xau_daily_close(uni, XAU_HOUR[TH_ID]),
                            grams=BAHT_WEIGHT_G, purity=TH_BAR_PURITY,
                            fx_key="bot_reference") or None
    sge_store = _store(SGE_ID)
    sge = None
    if sge_store:
        dirs = _series(sge_store, "pay_direction")
        days = sorted(dirs)
        runs = streak([int(dirs[d][0]) for d in days])
        sge = [{"date": d, "direction": int(dirs[d][0]), "streak": r, "fee_rate": UNMEASURED}
               for d, r in zip(days, runs, strict=True)] or None
    return build_state(records=records, hk=hk, vn=vn, th=th, sge=sge,
                       tr=tr_from_stores(_store, _series, uni),
                       missed_growth=missed_growth_lines(), mode="live", now=now)


def tr_from_stores(_store: Any, _series: Any, uni: Path
                   ) -> dict[str, list[dict[str, Any]] | None]:
    """The Turkish states from the alt_proxies vintage stores. A store of a row refused as live
    input reads empty (UNMEASURED); a missing USDTRY or XAUUSD bar leaves no premium, never 0."""
    xau = xau_daily_close(uni, TR_XAU_HOUR)
    usdtry = xau_daily_close(uni, TR_XAU_HOUR, "USDTRY")
    price = {d: v for d, (v, _) in _series(_store(TR_PRICE_ID), "try_per_gram").items()}
    imp_raw = _series(_store(TR_IMPORT_ID), "gold_imports")
    res_raw = _series(_store(TR_RESERVE_ID), "gold_reserves")
    bist = {d: v / 1000.0 for d, (v, _) in _series(_store(TR_BIST_ID), "try_per_kg").items()}
    return {TR_PRICE_ID: tr_premium_series(price, usdtry, xau) or None,
            TR_IMPORT_ID: tr_import_surge({p[:7]: v for p, (v, _) in imp_raw.items()},
                                          {p[:7]: t for p, (_, t) in imp_raw.items()}) or None,
            TR_RESERVE_ID: tr_reserves({d: v for d, (v, _) in res_raw.items()},
                                       {d: t for d, (_, t) in res_raw.items()}) or None,
            TR_BIST_ID: tr_premium_series(bist, usdtry, xau) or None}


# ============================================================================ player footprint
#: The retail rows of the player-footprint matrix (PR #659's registry schema: `class`, `region`,
#: `targets`, `why`), in the same shape as jp_retail_flow.FOOTPRINT_ROWS: `adapter` names this
#: module's frame reader and `columns` the exact columns `footprint_frame` returns.
RESEARCH_SERIES: dict[str, tuple[str, ...]] = {
    VN_ID: ("premium_pct", "premium_usd_oz", "buy_sell_gap_pct"),
    IN_ID: ("premium_pct", "premium_usd_oz", "premium_am_pct"),
}
FOOTPRINT_ROWS: list[dict[str, Any]] = [
    {"id": VN_ID, "class": "retail", "region": "VN", "adapter": "asia_gold_physical",
     "store": f"lake/series/alt_{VN_ID}__<column>.csv (alt_proxies research lane)",
     "columns": list(RESEARCH_SERIES[VN_ID]), "units": "% and USD per fine oz over XAUUSD",
     "freq": "intraday prints, one per date (the first print seen)",
     "targets": ["XAUUSD"], "session": "asia", "policy_row": VN_ID,
     "live_sizing_allowed": False,
     "why": ("Vietnamese households buy the SJC bar as savings and capital flight; its premium "
             "over London at Vietcombank's dollar is the local retail bid the Western tape "
             "prices only later (SBV bar auctions cap it: a policy clock beside the demand).")},
    {"id": IN_ID, "class": "retail", "region": "IN", "adapter": "asia_gold_physical",
     "store": f"lake/series/alt_{IN_ID}__<column>.csv (alt_proxies research lane)",
     "columns": list(RESEARCH_SERIES[IN_ID]), "units": "% and USD per fine oz over XAUUSD",
     "freq": "daily (IBJA AM and PM polls, business days)",
     "targets": ["XAUUSD"], "session": "asia", "policy_row": IN_ID,
     "live_sizing_allowed": False,
     "why": ("India's jewellers and households are the world's second retail gold buyer; IBJA's "
             "polled 999 price over London at the RBI reference rate is their premium or "
             "discount -- a discount is retail selling into the rally, a premium is the bid.")},
]


def footprint_frame(sid: str, series_dir: Path | None = None) -> Any:
    """One footprint row's series as #659's `collect` consumes them: indexed by the observation
    date (DatetimeIndex, ascending), one column per feature, plus `available_utc` (the instant the
    row was first knowable: the latest of its legs, tz-aware UTC). Empty when nothing is held."""
    import pandas as pd
    if sid not in RESEARCH_SERIES:
        raise KeyError(sid)
    base = series_dir or (DESK / "data" / "lake" / "series")
    cols, stamps = [], []
    for name in RESEARCH_SERIES[sid]:
        p = base / f"alt_{sid}__{name}.csv"
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if df.empty or "value" not in df.columns:
            continue
        idx = pd.DatetimeIndex(pd.to_datetime(df["event_time"]))
        cols.append(pd.Series(df["value"].to_numpy(dtype=float), index=idx, name=name))
        stamps.append(pd.Series(pd.to_datetime(df["available_time"], utc=True).to_numpy(),
                                index=idx, name=name))
    if not cols:
        return pd.DataFrame()
    out = pd.concat(cols, axis=1)
    out["available_utc"] = pd.to_datetime(pd.concat(stamps, axis=1).max(axis=1), utc=True)
    return out.sort_index()


def research_door_state(row: Mapping[str, Any] | None) -> str:
    """HARD_STOP > RED (more than RESEARCH_EMPTY_RED_RUNS empty fetch passes in a row) > GREEN
    (the last fetch pass landed rows) > AMBER (an empty pass, not yet RED) > UNMEASURED."""
    r = row or {}
    if r.get("hard_stop") and not (r["hard_stop"] or {}).get("released_by"):
        return "HARD_STOP"
    streak = int(r.get("empty_streak") or 0)
    if streak > RESEARCH_EMPTY_RED_RUNS:
        return "RED"
    if r.get("last_landed_at") and not streak:
        return "GREEN"
    if streak:
        return "AMBER"
    return UNMEASURED


def research_missed_growth() -> list[dict[str, Any]]:
    """GROWTH GOVERNANCE: each research door's register rows are refused as LIVE input (no quoted
    permitting clause), so each carries its missed-growth line (delta E[log W] UNMEASURED)."""
    from libs.data import terms_fence as tf
    keys = [k for sid in RESEARCH_IDS for k in RESEARCH_POLICY[sid] if tf.input_source(k)]
    return [tf.held_missed_growth(k, None, live_input_refusal=True)
            for k in dict.fromkeys(keys)]

if __name__ == "__main__":
    raise SystemExit(main())
