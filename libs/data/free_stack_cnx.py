"""CHINA EXCHANGE POSITIONING, INVENTORY AND CURVES -- the free stack's `cn_exchange` fetcher
(audit package P2, directive PART II.B/C; registered in `libs.data.free_stack.FETCHERS`).

WHAT IT READS, per exchange and per trading day, from the exchange's own dated publications:

    SHFE / INE  kx<date>.dat         daily quotes per contract month (OHLC, settlement, volume,
                                     OI, OI change)                                       JSON
                pm<date>.dat         member rankings per contract: top-20 volume, long OI,
                                     short OI with their day changes                      JSON
                <date>dailystock.dat warehouse receipts (warrants) per warehouse, with totals JSON
                <date>weeklystock.dat weekly warehouse inventory per warehouse (Fridays)  JSON
    DCE         day-quotes export (txt) and member-ranking export (txt, three blocks)
    CZCE        FutureDataDaily.txt and FutureDataHolding.txt (pipe-separated)
    GFEX        day-quotes and member-ranking JSON (POST loadList endpoints)
    CFFEX       rtj/<yyyymm>/<dd>/index.xml (daily) and ccpm/<yyyymm>/<dd>/<product>.xml (ranks)

The documented formats these parsers read are reproduced as fixtures under
`desks/mt5/tests/fixtures/free_stack/cnx/` (the README there says what each is based on). The
build sandbox cannot reach any exchange host, so the live yield is UNMEASURED until the box runs it.

WHAT IT PRODUCES, per mapped product and trading day (keys `<product>_<metric>`):

    curve        ret (log settle / pre-settle of the dominant contract -- no roll artefact),
                 settle, oi, vol, ts_slope (next/front - 1), roll_yield (annualised
                 log(front/next)), curv ((front - 2 mid + far) / front)
    positioning  long_c5/c10/c20, short_c5/c10/c20, vol_c20 (top-k share of the product's OI or
                 volume), net_top5, net_top20 ((top long - top short) / OI), long_hhi, short_hhi
                 (HHI of the top-20 list), conc_disp (long_c20 - short_c20), state_net (the
                 tracked state-owned brokers' net, a LOWER BOUND: a member outside a top-20
                 list adds nothing on that side), citic_net (CITIC Futures, only when it is
                 in BOTH lists)
    inventory    wr / wr_chg (warrant tonnes and the exchange's own day change), inv / inv_chg
                 (weekly inventory, SHFE / INE only)

and, from that history (`derive`, run by the hunter on the FIRST-VINTAGE store so it is
point-in-time), change (_d1) and acceleration (_d2), inventory surprise vs the same ISO week of
the two previous years (_seas_surp, _seas_z, carrying expected_value / seasonal_expected /
raw_surprise / surprise_z), and four divergence scores that are POSITIVE WHEN THE TWO LEGS
DISAGREE: inv_px_div / wr_px_div (z of the 5-obs stock change + z of the 5-obs return: stocks
building into a rally, or drawing into a sell-off), pos_px_div (z of the 5-obs change in top-20
net minus z of the return: top members buying a falling market), oi_px_div (minus the product of
the two z's: price and OI moving against each other).

POINT IN TIME. Each file is a dated archive the exchange published after its close. Every
observation carries `publication_time` = the trading day at the row's declared release hour
(Beijing time, conservative -- the exact release instant is UNMEASURED and the declared bound is
later than the exchanges' usual 15:30-17:00), which the hunter uses as `available_time` for the
first vintage; a later changed value is a revision stamped at its first sight. Every record also
carries the names of the universal sensor contract (MANDATE 2026-10-06 s2.5) so a later adapter
is a pure mapping.

TERMS, FAIL CLOSED. A row whose `terms` is not `confirmed` returns BLOCKED_ON_TERMS and makes no
request; `terms_evidence` on the roster row holds the URL and the verbatim clause read.
"""
# ruff: noqa: RUF001, RUF002 -- the exchanges' own files use full-width Chinese
# punctuation (colons and parentheses in their headers); the parsers must match them exactly.
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

UNMEASURED = "UNMEASURED"
BJT = timedelta(hours=8)
#: Release hour (Beijing) assumed when a roster row declares none: a conservative upper bound.
DEFAULT_RELEASE_BJT = "20:00"
DEFAULT_BACKFILL_DAYS = 800          # weekdays (~3 years: the seasonal surprise needs two prior)
DEFAULT_DAYS_PER_PASS = 15
DEFAULT_MAX_SECONDS = 150.0
Z_WINDOW = 60                        # observations; a z needs the FULL window (deterministic)
DIV_STEP = 5                         # observations in a divergence leg's change / return

#: Tracked state-controlled futures brokers, matched by prefix of the member's short name.
STATE_BROKERS: tuple[str, ...] = ("中信期货", "国泰君安", "海通期货", "银河期货", "中信建投",
                                  "华泰期货", "申银万国", "国投安信", "广发期货", "招商期货",
                                  "光大期货", "东证期货", "永安期货", "中金财富", "五矿期货")
CITIC = "中信期货"

#: Chinese product names -> exchange product codes (the warehouse files and DCE/GFEX quote
#: exports name products in Chinese only). A fact table about exchanges, not a universe.
CN_NAME_CODE: dict[str, str] = {
    "铜": "cu", "阴极铜": "cu", "铝": "al", "锌": "zn", "铅": "pb", "镍": "ni", "锡": "sn",
    "黄金": "au", "白银": "ag", "螺纹钢": "rb", "线材": "wr", "热轧卷板": "hc", "不锈钢": "ss",
    "原油": "sc", "中质含硫原油": "sc", "燃料油": "fu", "低硫燃料油": "lu", "天然橡胶": "ru",
    "20号胶": "nr", "石油沥青": "bu", "纸浆": "sp", "漂针浆": "sp", "国际铜": "bc", "氧化铝": "ao",
    "铁矿石": "i", "焦炭": "j", "焦煤": "jm", "豆一": "a", "豆二": "b", "豆粕": "m", "豆油": "y",
    "棕榈油": "p", "玉米": "c", "玉米淀粉": "cs", "鸡蛋": "jd", "聚乙烯": "l", "聚丙烯": "pp",
    "聚氯乙烯": "v", "乙二醇": "eg", "苯乙烯": "eb", "液化石油气": "pg", "生猪": "lh",
    "工业硅": "si", "碳酸锂": "lc", "多晶硅": "ps",
}

#: product -> MT5 instruments with a plausible transmission path (directive PART II: "use it as
#: an information sensor only where there is a plausible MT5 transmission path"). The hunter
#: keeps only those the broker lists AND `universe_policy.may_hypothesise` admits.
PRODUCT_TARGETS: dict[str, tuple[str, ...]] = {
    "au": ("XAUUSD", "XAUAUD"), "ag": ("XAGUSD",), "cu": ("XCUUSD", "AUDUSD"),
    "bc": ("XCUUSD",), "al": ("XALUSD",), "ao": ("XALUSD",), "zn": ("XZNUSD",),
    "ni": ("XNIUSD",), "pb": ("XPBUSD",), "rb": ("AUDUSD",), "hc": ("AUDUSD",),
    "sc": ("XBRUSD", "XTIUSD"), "fu": ("XBRUSD",), "lu": ("XBRUSD",),
    "i": ("AUDUSD",), "j": ("AUDUSD",), "jm": ("AUDUSD",), "m": ("SOYBEAN",), "a": ("SOYBEAN",),
    "c": ("CORN",), "CF": ("COTTON",), "SR": ("SUGAR",), "lc": ("AUDUSD",),
    "IF": ("CHINAH", "HK50", "USDCNH"), "IH": ("CHINAH", "HK50"), "IC": ("CHINAH", "USDCNH"),
    "IM": ("CHINAH", "USDCNH"), "T": ("USDCNH",), "TF": ("USDCNH",),
}

#: Metrics that become HYPOTHESIS columns (the rest are stored for derivation and audit only, so
#: they charge no trials). Each one names a mechanism the directive lists.
SIGNAL_METRICS: dict[str, str] = {
    "long_c5": "top-5 long concentration (crowding)",
    "short_c5": "top-5 short concentration (crowding)",
    "net_top20": "top-20 members' net position / OI",
    "state_net": "tracked state brokers' net position / OI (lower bound)",
    "conc_disp": "long minus short top-20 concentration (dispersion)",
    "long_c20_d1": "top-20 long concentration, day change",
    "net_top20_d1": "top-20 net, day change",
    "net_top20_d2": "top-20 net, acceleration",
    "wr_d1": "warehouse receipts, day change",
    "wr_d2": "warehouse receipts, acceleration",
    "inv_seas_z": "weekly inventory change surprise vs the same week of the two prior years",
    "inv_px_div": "inventory-price divergence",
    "wr_px_div": "warrant-price divergence",
    "pos_px_div": "price-position divergence",
    "oi_px_div": "OI-price divergence",
    "ts_slope": "front-next spread (contango > 0)",
    "roll_yield": "annualised roll yield (backwardation > 0)",
    "curv": "curve curvature (front - 2 mid + far)",
}
UNITS: dict[str, str] = {"ret": "log_return", "settle": "price_cny", "oi": "contracts",
                         "vol": "contracts", "wr": "exchange_unit", "wr_chg": "exchange_unit",
                         "inv": "exchange_unit", "inv_chg": "exchange_unit"}

Fetch = Callable[[str, Mapping[str, str] | None, bytes | None], bytes]


# =================================================================================== utils ===
def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "--", "null", "None"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def _decode(raw: bytes | None) -> str:
    if not raw:
        return ""
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _jload(raw: bytes | None) -> Any:
    text = _decode(raw).strip()
    if not text or text[0] not in "{[":
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _code(name: str) -> str | None:
    """A product code from a Chinese name, an English-suffixed `铜$$Copper`, or a code."""
    s = str(name or "").split("$$")[0].strip()
    if s in CN_NAME_CODE:
        return CN_NAME_CODE[s]
    m = re.match(r"^([A-Za-z]{1,2})\d*$", s)
    return m.group(1) if m else None


def _letters(inst: str) -> str:
    m = re.match(r"^\s*([A-Za-z]+)", str(inst or ""))
    return m.group(1) if m else ""


def contract_month(digits: str, trade: date) -> tuple[int, int] | None:
    """(year, month) of a delivery code: YYMM (SHFE/DCE/GFEX/CFFEX) or YMM (CZCE)."""
    d = re.sub(r"\D", "", str(digits or ""))
    if len(d) == 4:
        y, mth = 2000 + int(d[:2]), int(d[2:])
    elif len(d) == 3:
        y0 = int(d[0])
        y = trade.year - trade.year % 10 + y0
        if y < trade.year - 1:
            y += 10
        mth = int(d[1:])
    else:
        return None
    return (y, mth) if 1 <= mth <= 12 else None


def _sha(raw: bytes | None) -> str:
    return hashlib.sha256(raw or b"").hexdigest()[:16]


# ============================================================================ quotes parsers ==
#: one quote row: {"product","contract","month":(y,m),"settle","presettle","close","volume","oi",
#: "oi_chg"}
Quote = dict[str, Any]


def parse_shfe_kx(raw: bytes | None, trade: date) -> list[Quote]:
    """SHFE / INE kx<date>.dat: {"o_curinstrument": [{PRODUCTID "cu_f", PRODUCTGROUPID "cu",
    DELIVERYMONTH "2311" | "小计", PRESETTLEMENTPRICE, OPENPRICE, HIGHESTPRICE, LOWESTPRICE,
    CLOSEPRICE, SETTLEMENTPRICE, VOLUME, OPENINTEREST, OPENINTERESTCHG}], "report_date": ...}"""
    doc = _jload(raw)
    rows = (doc or {}).get("o_curinstrument") if isinstance(doc, dict) else None
    out: list[Quote] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        prod = str(r.get("PRODUCTGROUPID") or "").strip() or str(r.get("PRODUCTID") or ""
                                                                 ).split("_")[0].strip()
        ym = contract_month(str(r.get("DELIVERYMONTH") or ""), trade)
        if not prod or ym is None:
            continue
        out.append(_quote(prod.lower(), f"{prod.lower()}{str(r.get('DELIVERYMONTH')).strip()}",
                          ym, r.get("SETTLEMENTPRICE"), r.get("PRESETTLEMENTPRICE"),
                          r.get("CLOSEPRICE"), r.get("VOLUME"), r.get("OPENINTEREST"),
                          r.get("OPENINTERESTCHG")))
    return [q for q in out if q]


def _quote(prod: str, contract: str, ym: tuple[int, int], settle: Any, pre: Any, close: Any,
           vol: Any, oi: Any, oi_chg: Any) -> Quote:
    return {"product": prod, "contract": contract, "month": ym, "settle": _num(settle),
            "presettle": _num(pre), "close": _num(close), "volume": _num(vol) or 0.0,
            "oi": _num(oi) or 0.0, "oi_chg": _num(oi_chg)}


def _table_lines(text: str, sep: str | None) -> list[list[str]]:
    out: list[list[str]] = []
    for ln in text.splitlines():
        if not ln.strip():
            out.append([])
            continue
        cells = [c.strip() for c in (ln.split(sep) if sep else re.split(r"\t+|\s{2,}", ln.strip()))]
        out.append(cells)
    return out


def parse_dce_daily(raw: bytes | None, trade: date) -> list[Quote]:
    """DCE day-quotes txt export: header 商品名称 交割月份 开盘价 最高价 最低价 收盘价 前结算价
    结算价 涨跌 涨跌1 成交量 持仓量 持仓量变化 成交额, tab-separated; 小计 / 总计 rows."""
    lines = _table_lines(_decode(raw), "\t")
    hdr: list[str] | None = None
    out: list[Quote] = []
    for cells in lines:
        if not cells:
            continue
        if "商品名称" in cells and "交割月份" in cells:
            hdr = cells
            continue
        if hdr is None or len(cells) < len(hdr) - 1:
            continue
        row = dict(zip(hdr, cells, strict=False))
        prod = _code(row.get("商品名称", ""))
        ym = contract_month(row.get("交割月份", ""), trade)
        if prod is None or ym is None:
            continue
        out.append(_quote(prod, f"{prod}{row['交割月份']}", ym, row.get("结算价"),
                          row.get("前结算价"), row.get("收盘价"), row.get("成交量"),
                          row.get("持仓量"), row.get("持仓量变化")))
    return out


def parse_czce_daily(raw: bytes | None, trade: date) -> list[Quote]:
    """CZCE FutureDataDaily.txt: title line, then `品种月份|昨结算|今开盘|最高价|最低价|今收盘|
    今结算|涨跌1|涨跌2|成交量(手)|持仓量|增减量|成交额(万元)|交割结算价`, pipe-separated."""
    hdr: list[str] | None = None
    out: list[Quote] = []
    for cells in _table_lines(_decode(raw), "|"):
        if not cells:
            continue
        if cells[0].startswith("品种月份") or cells[0].startswith("合约代码"):
            hdr = [re.sub(r"[（(].*", "", c) for c in cells]
            continue
        if hdr is None:
            continue
        row = dict(zip(hdr, cells, strict=False))
        inst = cells[0]
        prod = _letters(inst)
        ym = contract_month(inst[len(prod):], trade)
        if not prod or ym is None:
            continue
        out.append(_quote(prod.upper(), inst.upper(), ym, row.get("今结算"), row.get("昨结算"),
                          row.get("今收盘"), row.get("成交量"),
                          row.get("持仓量") or row.get("空盘量"), row.get("增减量")))
    return out


def parse_gfex_daily(raw: bytes | None, trade: date) -> list[Quote]:
    """GFEX loadList JSON: {"code": "0", "data": [{variety, varietyOrder "si", delivMonth "2309"
    | "小计", open, high, low, close, lastClear, clearPrice, volumn, openInterest, diffI}]}."""
    doc = _jload(raw)
    rows = (doc or {}).get("data") if isinstance(doc, dict) else None
    out: list[Quote] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        prod = str(r.get("varietyOrder") or "").strip().lower() or _code(r.get("variety", ""))
        ym = contract_month(str(r.get("delivMonth") or ""), trade)
        if not prod or ym is None:
            continue
        out.append(_quote(prod, f"{prod}{r.get('delivMonth')}", ym, r.get("clearPrice"),
                          r.get("lastClear"), r.get("close"), r.get("volumn", r.get("volume")),
                          r.get("openInterest"), r.get("diffI")))
    return out


def _xml_rows(raw: bytes | None, tag: str) -> list[dict[str, str]]:
    text = _decode(raw).strip()
    if not text.startswith("<"):
        return []
    try:
        root = ET.fromstring(text.encode("utf-8") if "encoding" not in text[:80] else
                             raw or b"")
    except ET.ParseError:
        return []
    return [{c.tag.lower(): (c.text or "").strip() for c in el} for el in root.iter(tag)]


def parse_cffex_daily(raw: bytes | None, trade: date) -> list[Quote]:
    """CFFEX rtj index.xml: <dailydatas><dailydata><instrumentid>IF2310</instrumentid>
    <openprice/>...<openinterest/><presettlementprice/><settlementprice/><volume/>
    <productid>IF</productid></dailydata>; option rows (IO2310-C-3800) are skipped."""
    out: list[Quote] = []
    for r in _xml_rows(raw, "dailydata"):
        inst = r.get("instrumentid", "")
        if "-" in inst:
            continue
        prod = (r.get("productid") or _letters(inst)).upper()
        ym = contract_month(inst[len(_letters(inst)):], trade)
        if not prod or ym is None:
            continue
        oi, pre_oi = _num(r.get("openinterest")), _num(r.get("preopeninterest"))
        out.append(_quote(prod, inst, ym, r.get("settlementprice"), r.get("presettlementprice"),
                          r.get("closeprice"), r.get("volume"), oi,
                          (oi - pre_oi) if oi is not None and pre_oi is not None else None))
    return out


# ============================================================================== rank parsers ==
#: ranks[product][side] = {member: (qty, chg)}, side in vol / long / short, summed across the
#: product's contracts (the "前20席位" convention); scope says what the denominator must be.
Ranks = dict[str, dict[str, dict[str, tuple[float, float]]]]


def _add(ranks: Ranks, prod: str, side: str, member: str, qty: Any, chg: Any) -> None:
    q = _num(qty)
    if not member or q is None:
        return
    book = ranks.setdefault(prod, {}).setdefault(side, {})
    q0, c0 = book.get(member, (0.0, 0.0))
    book[member] = (q0 + q, c0 + (_num(chg) or 0.0))


def parse_shfe_pm(raw: bytes | None) -> tuple[Ranks, dict[str, set[str]]]:
    """SHFE / INE pm<date>.dat: {"o_cursor": [{INSTRUMENTID "cu2311", RANK 1..20 (999 = total,
    0 / -1 = subtotal rows), PARTICIPANTABBR1, CJ1, CJ1_CHG (volume), PARTICIPANTABBR2, CJ2,
    CJ2_CHG (long OI), PARTICIPANTABBR3, CJ3, CJ3_CHG (short OI), PRODUCTNAME}]}.
    Returns (ranks per product, contracts seen per product)."""
    doc = _jload(raw)
    rows = (doc or {}).get("o_cursor") if isinstance(doc, dict) else None
    ranks: Ranks = {}
    seen: dict[str, set[str]] = defaultdict(set)
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        rk = _num(r.get("RANK"))
        inst = str(r.get("INSTRUMENTID") or "").strip()
        prod = _letters(inst).lower()
        if rk is None or not 1 <= rk <= 20 or not prod or not re.search(r"\d", inst):
            continue
        seen[prod].add(inst.lower())
        for i, side in ((1, "vol"), (2, "long"), (3, "short")):
            _add(ranks, prod, side, str(r.get(f"PARTICIPANTABBR{i}") or "").strip(),
                 r.get(f"CJ{i}"), r.get(f"CJ{i}_CHG"))
    return ranks, dict(seen)


_SIDE_WORDS = (("持买", "long"), ("买单", "long"), ("持卖", "short"), ("卖单", "short"),
               ("成交", "vol"))


def _side_of(header: str) -> str | None:
    for word, side in _SIDE_WORDS:
        if word in header:
            return side
    return None


def parse_dce_rank(raw: bytes | None, prod: str) -> Ranks:
    """DCE member-ranking txt export (contract.contract_id=all, product scope): three blocks,
    each headed `名次 会员简称 成交量|持买单量|持卖单量 增减`, rows `rank member qty chg`,
    ended by a `总计` row or a blank line."""
    ranks: Ranks = {}
    side: str | None = None
    for cells in _table_lines(_decode(raw), None):
        if not cells:
            side = None
            continue
        if cells[0] == "名次":
            side = _side_of(" ".join(cells[2:3]))
            continue
        if side and cells[0].isdigit() and len(cells) >= 3 and int(cells[0]) <= 20:
            _add(ranks, prod, side, cells[1], cells[2], cells[3] if len(cells) > 3 else None)
        elif cells[0].startswith(("总计", "合计")):
            side = None
    return ranks


def parse_czce_rank(raw: bytes | None) -> tuple[Ranks, Ranks]:
    """CZCE FutureDataHolding.txt: blocks headed `品种：苹果AP  日期：...` (product scope) or
    `合约：AP401  日期：...` (contract scope), then `名次|会员简称|成交量（手）|增减量|会员简称|
    持买仓量|增减量|会员简称|持卖仓量|增减量`, rows to a `合计` row. Returns (product, contract)."""
    by_prod: Ranks = {}
    by_contract: Ranks = {}
    target: Ranks | None = None
    key = ""
    for cells in _table_lines(_decode(raw), "|"):
        if not cells:
            continue
        head = cells[0]
        m = re.match(r"^(品种|合约)[:：]\s*\S*?([A-Za-z]+\d*)\s", head + " ")
        if m:
            target = by_prod if m.group(1) == "品种" else by_contract
            key = m.group(2) if m.group(1) == "合约" else _letters(m.group(2))
            key = key.upper()
            continue
        if target is None or not head.isdigit() or int(head) > 20 or len(cells) < 10:
            continue
        for off, side in ((1, "vol"), (4, "long"), (7, "short")):
            _add(target, key, side, cells[off], cells[off + 1], cells[off + 2])
    return by_prod, by_contract


def parse_gfex_rank(raw: bytes | None, prod: str, side: str) -> Ranks:
    """GFEX member-ranking loadList JSON (one call per data_type 1 vol / 2 long / 3 short):
    {"data": [{rank, abbr, todayQty, qtySub}]} -- member / qty / change names vary by release,
    so each is read from its known spellings."""
    doc = _jload(raw)
    rows = (doc or {}).get("data") if isinstance(doc, dict) else None
    ranks: Ranks = {}
    for i, r in enumerate(rows or [], 1):
        if not isinstance(r, dict):
            continue
        rk = _num(r.get("rank")) or float(i)
        if rk > 20:
            continue
        mem = next((str(r[k]) for k in ("abbr", "memberAbbr", "shortname", "memberName")
                    if r.get(k)), "")
        qty = next((r[k] for k in ("todayQty", "qty", "volume") if k in r), None)
        chg = next((r[k] for k in ("qtySub", "todayQtyChg", "varQty") if k in r), None)
        _add(ranks, prod, side, mem.strip(), qty, chg)
    return ranks


def parse_cffex_rank(raw: bytes | None) -> tuple[Ranks, dict[str, set[str]]]:
    """CFFEX ccpm <product>.xml: <positionRank><data><instrumentid>IF2310</instrumentid>
    <datatypeid>0|1|2</datatypeid> (volume / long / short) <rank/> <shortname/> <volume/>
    <varvolume/> <productid>IF</productid></data>."""
    ranks: Ranks = {}
    seen: dict[str, set[str]] = defaultdict(set)
    side_of = {"0": "vol", "1": "long", "2": "short"}
    for r in _xml_rows(raw, "data"):
        side = side_of.get(r.get("datatypeid", ""))
        rk = _num(r.get("rank"))
        inst = r.get("instrumentid", "")
        prod = (r.get("productid") or _letters(inst)).upper()
        if side is None or rk is None or not 1 <= rk <= 20 or not prod:
            continue
        seen[prod].add(inst.upper())
        _add(ranks, prod, side, r.get("shortname", ""), r.get("volume"), r.get("varvolume"))
    return ranks, dict(seen)


# ========================================================================= warehouse parsers ==
def parse_shfe_stock(raw: bytes | None, field: str, chg_field: str | None
                     ) -> dict[str, tuple[float, float | None]]:
    """SHFE / INE <date>dailystock.dat (field WRTWGHTS, change WRTCHANGE) and weeklystock.dat
    (field WHSTOCKS): {"o_cursor": [{VARNAME "铜$$Copper", REGNAME, WHABBRNAME (a `总计$$Total`
    row per product), <field>, <chg>, UNIT}]}. The exchange's own 总计 row wins; without one the
    warehouse rows are summed (合计 / 小计 subtotals excluded)."""
    doc = _jload(raw)
    rows = (doc or {}).get("o_cursor") if isinstance(doc, dict) else None
    tot: dict[str, tuple[float, float | None]] = {}
    summed: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        prod = _code(str(r.get("VARNAME") or ""))
        v = _num(r.get(field))
        if prod is None or v is None:
            continue
        c = _num(r.get(chg_field)) if chg_field else None
        wh = str(r.get("WHABBRNAME") or "")
        if "总计" in wh:
            tot[prod] = (v, c)
        elif "合计" not in wh and "小计" not in wh:
            s = summed[prod]
            s[0] += v
            s[1] += c or 0.0
            s[2] += 1.0 if c is not None else 0.0
    for prod, (v, c, n) in summed.items():
        tot.setdefault(prod, (v, c if n else None))
    return tot


# ================================================================================= features ==
def dominant(quotes: Sequence[Quote]) -> Quote | None:
    q = [x for x in quotes if x.get("settle")]
    return max(q, key=lambda x: (x["oi"], x["volume"])) if q else None


def curve_features(quotes: Sequence[Quote]) -> dict[str, float]:
    """ret / settle of the dominant contract, product OI / volume, and the curve over the listed
    months that carry open interest, in delivery order."""
    out: dict[str, float] = {}
    dom = dominant(quotes)
    if dom is None:
        return out
    out["settle"] = float(dom["settle"])
    if dom.get("presettle"):
        out["ret"] = round(math.log(dom["settle"] / dom["presettle"]), 6)
    out["oi"] = float(sum(q["oi"] for q in quotes))
    out["vol"] = float(sum(q["volume"] for q in quotes))
    liquid = sorted((q for q in quotes if q.get("settle") and q["oi"] > 0),
                    key=lambda q: q["month"])
    if len(liquid) >= 2:
        f, n = liquid[0], liquid[1]
        out["ts_slope"] = round(n["settle"] / f["settle"] - 1.0, 6)
        months = (n["month"][0] - f["month"][0]) * 12 + n["month"][1] - f["month"][1]
        if months > 0:
            out["roll_yield"] = round(math.log(f["settle"] / n["settle"]) * 12.0 / months, 6)
    if len(liquid) >= 3:
        f, mid, far = liquid[0], liquid[1], liquid[2]
        out["curv"] = round((f["settle"] - 2 * mid["settle"] + far["settle"]) / f["settle"], 6)
    return out


def _top(book: Mapping[str, tuple[float, float]], k: int) -> float:
    return float(sum(sorted((q for q, _ in book.values()), reverse=True)[:k]))


def _hhi(book: Mapping[str, tuple[float, float]]) -> float | None:
    qs = sorted((q for q, _ in book.values()), reverse=True)[:20]
    tot = sum(qs)
    return round(sum((q / tot) ** 2 for q in qs) * 10000.0, 2) if tot > 0 else None


def rank_features(book: Mapping[str, Mapping[str, tuple[float, float]]], oi: float | None,
                  vol: float | None, brokers: Sequence[str] = STATE_BROKERS
                  ) -> dict[str, float]:
    """Concentration needs the scope's own OI; without it only the HHI and the citic flag remain
    (a share of an unknown total would be a made-up number)."""
    out: dict[str, float] = {}
    lo, sh, vb = book.get("long") or {}, book.get("short") or {}, book.get("vol") or {}
    if oi and oi > 0 and lo and sh:
        for k in (5, 10, 20):
            out[f"long_c{k}"] = round(_top(lo, k) / oi, 6)
            out[f"short_c{k}"] = round(_top(sh, k) / oi, 6)
        out["net_top5"] = round((_top(lo, 5) - _top(sh, 5)) / oi, 6)
        out["net_top20"] = round((_top(lo, 20) - _top(sh, 20)) / oi, 6)
        out["conc_disp"] = round(out["long_c20"] - out["short_c20"], 6)

        def tracked(b: Mapping[str, tuple[float, float]]) -> float:
            return sum(q for m, (q, _) in b.items() if m.startswith(tuple(brokers)))
        out["state_net"] = round((tracked(lo) - tracked(sh)) / oi, 6)
        if CITIC in lo and CITIC in sh:
            out["citic_net"] = round((lo[CITIC][0] - sh[CITIC][0]) / oi, 6)
    if vol and vol > 0 and vb:
        # member volume is counted on BOTH sides of a trade (the members' column sums to twice
        # the exchange's volume), so the share is of 2 x volume; a constant factor either way
        out["vol_c20"] = round(_top(vb, 20) / (2.0 * vol), 6)
    for side, b in (("long", lo), ("short", sh)):
        h = _hhi(b)
        if h is not None:
            out[f"{side}_hhi"] = h
    return out


# ================================================================================= derive =====
def _pairs(hist: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted(hist.items())


def _z_full(vals: Sequence[float], i: int) -> float | None:
    """z of vals[i] against the Z_WINDOW values BEFORE it; None until the window is full, so a
    value never changes once it exists (backfill cannot rewrite it)."""
    if i < Z_WINDOW:
        return None
    w = vals[i - Z_WINDOW:i]
    mu = sum(w) / len(w)
    sd = math.sqrt(sum((x - mu) ** 2 for x in w) / (len(w) - 1))
    return (vals[i] - mu) / sd if sd > 0 else None


def _steps(vals: Sequence[float], k: int) -> list[float | None]:
    return [None if i < k else vals[i] - vals[i - k] for i in range(len(vals))]


def _z_series(vals: Sequence[float | None]) -> list[float | None]:
    clean = [(i, v) for i, v in enumerate(vals) if v is not None]
    zs: list[float | None] = [None] * len(vals)
    xs = [v for _, v in clean]
    for j, (i, _) in enumerate(clean):
        zs[i] = _z_full(xs, j)
    return zs


DERIVE_BASES = ("_long_c20", "_short_c20", "_net_top20", "_long_c5", "_short_c5",
                "_state_net", "_wr", "_inv", "_oi")
_DERIVED_TAGS = ("_d1", "_d2", "_seas_surp", "_seas_z", "_px_div")


def is_derived(key: str) -> bool:
    return key.endswith(_DERIVED_TAGS)


def derive(series: Mapping[str, Mapping[str, float]], pub: Mapping[str, str]
           ) -> list[dict[str, Any]]:
    """Change, acceleration, seasonal surprise and divergence from the first-vintage history.

    `series[key][period_end] = value` (keys `<product>_<metric>`); `pub[period_end]` is that
    day's publication_time. Every derived row carries its contract fields; nothing is emitted
    where its inputs are short (UNMEASURED is an absent row, never a zero)."""
    series = {k: v for k, v in series.items() if not is_derived(k)}
    out: list[dict[str, Any]] = []
    prods = sorted({k.rsplit("_", 1)[0] if k.endswith(("_ret", "_oi", "_wr", "_inv"))
                    else "" for k in series} - {""})

    def emit(key: str, d: str, v: float, extra: dict[str, Any] | None = None) -> None:
        if v is None or not math.isfinite(v):
            return
        row = {"key": key, "period_end": d, "value": round(float(v), 6), "derived": True}
        if d in pub:
            row["publication_time"] = pub[d]
        row.update(extra or {})
        out.append(row)

    for base in [k for k in series if k.endswith(DERIVE_BASES)]:
        pts = _pairs(series[base])
        vals = [v for _, v in pts]
        d1 = _steps(vals, 1)
        for i, (d, _) in enumerate(pts):
            cur = d1[i]
            if cur is None:
                continue
            emit(f"{base}_d1", d, cur, {"delta": round(cur, 6)})
            prev = d1[i - 1] if i >= 1 else None
            if prev is not None:
                emit(f"{base}_d2", d, cur - prev, {"delta": round(cur, 6),
                                                   "acceleration": round(cur - prev, 6)})
    for p in prods:
        ret = series.get(f"{p}_ret") or {}
        # seasonal surprise of the weekly inventory change (and the daily warrant 5-obs change)
        for stock, step in (("inv", 1), ("wr", DIV_STEP)):
            s = series.get(f"{p}_{stock}") or {}
            pts = _pairs(s)
            chg = _steps([v for _, v in pts], step)
            by_week: dict[tuple[int, int], float] = {}
            for (d, _), c in zip(pts, chg, strict=True):
                if c is not None:
                    iso = date.fromisoformat(d[:10]).isocalendar()
                    by_week[(iso[0], iso[1])] = c
            hist_surp: list[float] = []
            for (d, _), c in zip(pts, chg, strict=True):
                if c is None:
                    continue
                iso = date.fromisoformat(d[:10]).isocalendar()
                prior = [by_week.get((iso[0] - k, iso[1])) for k in (1, 2)]
                if any(x is None for x in prior):
                    continue
                seas = sum(x for x in prior if x is not None) / 2.0
                surp = c - seas
                z = None
                if len(hist_surp) >= 8:
                    w = hist_surp[-52:]
                    mu = sum(w) / len(w)
                    sd = math.sqrt(sum((x - mu) ** 2 for x in w) / (len(w) - 1))
                    z = surp / sd if sd > 0 else None
                hist_surp.append(surp)
                extra = {"expected_value": round(seas, 6), "seasonal_expected": round(seas, 6),
                         "raw_surprise": round(surp, 6)}
                emit(f"{p}_{stock}_seas_surp", d, surp, extra)
                if z is not None:
                    emit(f"{p}_{stock}_seas_z", d, z, {**extra, "surprise_z": round(z, 6)})
        # divergences: both legs on the dates they share, each z'd over its own full window
        if not ret:
            continue
        rd = sorted(ret)

        def cum_ret(dates: Sequence[str], ret: Mapping[str, float] = ret
                    ) -> list[float | None]:
            r = [ret[d] for d in dates]
            return [None if i < DIV_STEP - 1 else sum(r[i - DIV_STEP + 1:i + 1])
                    for i in range(len(r))]

        legs = {"inv_px_div": f"{p}_inv", "wr_px_div": f"{p}_wr",
                "pos_px_div": f"{p}_net_top20", "oi_px_div": f"{p}_oi"}
        for name, leg in legs.items():
            s = series.get(leg) or {}
            dates = [d for d in rd if d in s]
            if len(dates) < Z_WINDOW + DIV_STEP:
                continue
            lv = [s[d] for d in dates]
            if name == "oi_px_div":
                lv = [math.log(v) if v > 0 else float("nan") for v in lv]
            zl = _z_series(_steps(lv, DIV_STEP))
            zr = _z_series(cum_ret(dates))
            for i, d in enumerate(dates):
                a, b = zl[i], zr[i]
                if a is None or b is None:
                    continue
                v = (a + b if name in ("inv_px_div", "wr_px_div") else
                     a - b if name == "pos_px_div" else -(a * b))
                emit(f"{p}_{name}", d, v)
    return out


# ============================================================================== the fetcher ==
def _weekdays_back(end: date, n: int) -> list[date]:
    out: list[date] = []
    d = end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out


def release_utc(d: date, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=UTC) - BJT


def plan_days(cursor: Mapping[str, Any], now: datetime, row: Mapping[str, Any]
              ) -> list[date]:
    """Newest unfetched trading days first (forward), then retries, then the backfill walk
    back from the oldest day held, to `backfill_days` weekdays. Today only after its release."""
    hhmm = str(row.get("release_bjt") or DEFAULT_RELEASE_BJT)
    per = int(row.get("days_per_pass") or DEFAULT_DAYS_PER_PASS)
    floor_n = int(row.get("backfill_days") or DEFAULT_BACKFILL_DAYS)
    today = now.date()
    last = today if now >= release_utc(today, hhmm) else today - timedelta(days=1)
    newest = cursor.get("newest")
    oldest = cursor.get("oldest")
    out: list[date] = []
    if newest:
        # FORWARD, OLDEST GAP FIRST: a pass that cannot reach today still closes the gap behind
        # it, so the held range stays contiguous and `newest` never skips a day
        d = date.fromisoformat(newest) + timedelta(days=1)
        while d <= last and len(out) < per:
            if d.weekday() < 5:
                out.append(d)
            d += timedelta(days=1)
    else:
        out = _weekdays_back(last, per)
    for r in cursor.get("retry") or []:
        if len(out) >= per:
            break
        rd = date.fromisoformat(r)
        if rd not in out:
            out.append(rd)
    floor = _weekdays_back(last, floor_n)[-1]
    start = date.fromisoformat(oldest) if oldest else (out[-1] if out else last)
    d = start - timedelta(days=1)
    while len(out) < per and d >= floor:
        if d.weekday() < 5 and d not in out:
            out.append(d)
        d -= timedelta(days=1)
    return out


def _fmt(tpl: str, d: date, **kw: str) -> str:
    return tpl.format(ymd=d.strftime("%Y%m%d"), y=d.strftime("%Y"), ym=d.strftime("%Y%m"),
                      dd=d.strftime("%d"), m0=str(d.month - 1), d=str(d.day), **kw)


#: Default URL templates per exchange and surface; a roster row's `urls` overrides any of them.
#: Several templates are tried in order (the exchanges moved paths in 2024-25; the box measures
#: which one answers). POST bodies are form-encoded.
URLS: dict[str, dict[str, list[str]]] = {
    "shfe": {
        "daily": ["https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{ymd}.dat",
                  "https://www.shfe.com.cn/data/dailydata/kx/kx{ymd}.dat"],
        "rank": ["https://www.shfe.com.cn/data/tradedata/future/dailydata/pm{ymd}.dat",
                 "https://www.shfe.com.cn/data/dailydata/kx/pm{ymd}.dat"],
        "wr": ["https://www.shfe.com.cn/data/dailydata/{ymd}dailystock.dat"],
        "inv": ["https://www.shfe.com.cn/data/dailydata/{ymd}weeklystock.dat"]},
    "ine": {
        "daily": ["https://www.ine.cn/data/tradedata/future/dailydata/kx{ymd}.dat",
                  "https://www.ine.cn/data/dailydata/kx/kx{ymd}.dat"],
        "rank": ["https://www.ine.cn/data/tradedata/future/dailydata/pm{ymd}.dat",
                 "https://www.ine.cn/data/dailydata/kx/pm{ymd}.dat"],
        "wr": ["https://www.ine.cn/data/dailydata/{ymd}dailystock.dat"],
        "inv": ["https://www.ine.cn/data/dailydata/{ymd}weeklystock.dat"]},
    "dce": {
        "daily": ["http://www.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html?"
                  "dayQuotes.variety=all&dayQuotes.trade_type=0&year={y}&month={m0}&day={d}"
                  "&exportFlag=txt"],
        "rank": ["http://www.dce.com.cn/publicweb/quotesdata/exportMemberDealPosiQuotesData.html"
                 "?memberDealPosiQuotes.variety={variety}&memberDealPosiQuotes.trade_type=0"
                 "&contract.contract_id=all&contract.variety_id={variety}&year={y}&month={m0}"
                 "&day={d}&exportFlag=txt"]},
    "czce": {
        "daily": ["http://www.czce.com.cn/cn/DFSStaticFiles/Future/{y}/{ymd}/FutureDataDaily.txt"],
        "rank": ["http://www.czce.com.cn/cn/DFSStaticFiles/Future/{y}/{ymd}/"
                 "FutureDataHolding.txt"]},
    "gfex": {
        "daily": ["POST http://www.gfex.com.cn/u/interfacesWebTiDayQuotes/loadList "
                  "trade_date={ymd}&trade_type=0"],
        "rank": ["POST http://www.gfex.com.cn/u/interfacesWebTiMemberDealPosiQuotes/loadList "
                 "trade_date={ymd}&trade_type=0&variety={variety}&contract_id={contract}"
                 "&data_type={data_type}"]},
    "cffex": {
        "daily": ["http://www.cffex.com.cn/sj/hqsj/rtj/{ym}/{dd}/index.xml"],
        "rank": ["http://www.cffex.com.cn/sj/ccpm/{ym}/{dd}/{variety}.xml"]},
}
#: What a real answer looks like per exchange: an HTML error page served with a 200 is NOT the
#: file, so the next template is tried instead of parsing a shell.
EXPECT: dict[str, str] = {"shfe": "json", "ine": "json", "dce": "txt", "czce": "txt",
                          "gfex": "json", "cffex": "xml"}


def looks_like(raw: bytes | None, kind: str) -> bool:
    head = _decode(raw[:512] if raw else b"").lstrip()
    if not head:
        return False
    if kind == "json":
        return head[0] in "{["
    if kind == "xml":
        return head.startswith("<?xml") or (head.startswith("<") and
                                            not head[:15].lower().startswith(("<!doctype",
                                                                              "<html")))
    return not head.startswith("<")


DEFAULT_VARIETIES: dict[str, tuple[str, ...]] = {
    "dce": ("i", "j", "jm", "m", "a", "c"), "gfex": ("lc", "si", "ps"),
    "cffex": ("IF", "IH", "IC", "IM", "T", "TF"),
}


class _Day:
    """What one exchange-day produced, plus why a surface is missing (never a zero)."""

    def __init__(self) -> None:
        self.quotes: list[Quote] = []
        self.ranks: Ranks = {}
        self.wr: dict[str, tuple[float, float | None]] = {}
        self.inv: dict[str, tuple[float, float | None]] = {}
        self.hashes: dict[str, str] = {}
        #: contracts a per-contract ranking covered, so the denominator is THEIR open interest
        self.rank_contracts: dict[str, set[str]] = {}
        self.missing: list[str] = []
        self.errors: list[str] = []


def _try(get: Callable[[str, bytes | None], bytes | None], templates: Sequence[str], d: date,
         expect: str = "json", **kw: str) -> bytes | None:
    for tpl in templates:
        spec = _fmt(tpl, d, **kw)
        if spec.startswith("POST "):
            _, url, body = spec.split(" ", 2)
            raw = get(url, body.encode())
        else:
            raw = get(spec, None)
        if looks_like(raw, expect):
            return raw
    return None


def fetch_day(exch: str, d: date, get: Callable[[str, bytes | None], bytes | None],
              urls: Mapping[str, Sequence[str]], varieties: Sequence[str]) -> _Day:
    day = _Day()

    def load(surface: str, **kw: str) -> bytes | None:
        raw = _try(get, urls.get(surface) or [], d, EXPECT.get(exch, "json"), **kw)
        if raw is None:
            day.missing.append(surface + (f":{kw.get('variety')}" if kw.get("variety") else ""))
        else:
            day.hashes[surface + (f":{kw['variety']}" if kw.get("variety") else "")] = _sha(raw)
        return raw

    if exch in ("shfe", "ine"):
        day.quotes = parse_shfe_kx(load("daily"), d)
        day.ranks, day.rank_contracts = parse_shfe_pm(load("rank"))
        day.wr = parse_shfe_stock(load("wr"), "WRTWGHTS", "WRTCHANGE")
        if d.weekday() == 4:
            day.inv = parse_shfe_stock(load("inv"), "WHSTOCKS", None)
    elif exch == "dce":
        day.quotes = parse_dce_daily(load("daily"), d)
        for v in varieties:
            day.ranks.update(parse_dce_rank(load("rank", variety=v), v))
    elif exch == "czce":
        day.quotes = parse_czce_daily(load("daily"), d)
        by_prod, _ = parse_czce_rank(load("rank"))
        day.ranks = by_prod
    elif exch == "gfex":
        day.quotes = parse_gfex_daily(load("daily"), d)
        for v in varieties:
            dom = dominant([q for q in day.quotes if q["product"] == v])
            if dom is None:
                continue
            book: dict[str, dict[str, tuple[float, float]]] = {}
            for dt, side in (("1", "vol"), ("2", "long"), ("3", "short")):
                r = parse_gfex_rank(load("rank", variety=v, contract=dom["contract"],
                                         data_type=dt), v, side)
                book.update(r.get(v) or {})
            # GFEX ranks one contract: its scope is that contract, so the denominators are its
            day.ranks[v] = book
            day.ranks[v]["__scope__"] = {"oi": (dom["oi"], 0.0), "vol": (dom["volume"], 0.0)}
    elif exch == "cffex":
        day.quotes = parse_cffex_daily(load("daily"), d)
        for v in varieties:
            ranks, seen = parse_cffex_rank(load("rank", variety=v))
            day.ranks.update(ranks)
            day.rank_contracts.update(seen)
    return day


def day_features(exch: str, day: _Day, brokers: Sequence[str]) -> dict[str, dict[str, float]]:
    """{product: {metric: value}} for one exchange-day."""
    by_prod: dict[str, list[Quote]] = defaultdict(list)
    for q in day.quotes:
        by_prod[q["product"]].append(q)
    feats: dict[str, dict[str, float]] = defaultdict(dict)
    for prod, qs in by_prod.items():
        feats[prod].update(curve_features(qs))
    for prod, book in day.ranks.items():
        scope = book.get("__scope__") if isinstance(book, dict) else None
        oi: float | None
        vol: float | None
        covered = [q for q in by_prod.get(prod, [])
                   if str(q["contract"]).lower() in {c.lower() for c in
                                                     day.rank_contracts.get(prod, set())}]
        if scope:
            oi, vol = scope["oi"][0], scope["vol"][0]
        elif covered:
            oi = float(sum(q["oi"] for q in covered))
            vol = float(sum(q["volume"] for q in covered))
        else:
            oi, vol = feats.get(prod, {}).get("oi"), feats.get(prod, {}).get("vol")
        clean = {k: v for k, v in book.items() if k != "__scope__"}
        feats[prod].update(rank_features(clean, oi, vol, brokers))
    for prod, (v, c) in day.wr.items():
        feats[prod]["wr"] = v
        if c is not None:
            feats[prod]["wr_chg"] = c
    for prod, (v, _) in day.inv.items():
        feats[prod]["inv"] = v
    return {p: f for p, f in feats.items() if f}


def dataset_of(metric: str) -> str:
    if metric.startswith(("wr", "inv")):
        return "warrants" if metric.startswith("wr") else "inventory"
    if metric in ("ret", "settle", "oi", "vol", "ts_slope", "roll_yield", "curv"):
        return "daily"
    return "rank"


def contract_fields(row: Mapping[str, Any], exch: str, prod: str, metric: str, d: date,
                    pub: datetime, received: datetime, h: str, raw_pointer: str
                    ) -> dict[str, Any]:
    """The universal sensor contract's names (MANDATE 2026-10-06 s2.5) for one observation."""
    sid = str(row["id"])
    return {"source_id": sid, "dataset_id": f"{exch}.{dataset_of(metric)}",
            "observation_id": hashlib.sha1(f"{sid}|{prod}_{metric}|{d}".encode()
                                           ).hexdigest()[:16],
            "entity": f"{exch.upper()}:{prod}", "geography": "CN", "asset_domain": "futures",
            "metric": metric, "unit": UNITS.get(metric, "ratio"),
            "event_time": d.isoformat(), "publication_time": pub.isoformat(),
            "received_at": received.isoformat(), "licence": str(row.get("licence") or ""),
            "commercial_rights": str(row.get("terms") or UNMEASURED),
            "provenance_hash": h, "raw_pointer": raw_pointer}


def fetch_cn_exchange(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                      now: datetime) -> Any:
    """The `cn_exchange` kind: one roster row per exchange (`exchange`: shfe | ine | dce | czce
    | gfex | cffex)."""
    from libs.data.free_stack import Harvest
    h = Harvest(str(row["id"]))
    exch = str(row.get("exchange") or "").lower()
    if exch not in URLS:
        h.status, h.detail = "NO_ROUTE", f"unknown exchange {exch!r}"
        return h
    if str(row.get("terms") or "") != "confirmed":
        ev = row.get("terms_evidence") or {}
        h.status = "BLOCKED_ON_TERMS"
        h.detail = (f"terms={row.get('terms') or 'to_confirm'}; evidence "
                    f"{ev.get('terms_url') or 'none recorded'} -- no request made")
        return h
    urls = {**URLS[exch], **(row.get("urls") or {})}
    varieties = tuple(row.get("varieties") or DEFAULT_VARIETIES.get(exch, ()))
    brokers = tuple(row.get("tracked_brokers") or STATE_BROKERS)
    hhmm = str(row.get("release_bjt") or DEFAULT_RELEASE_BJT)
    budget = float(row.get("max_seconds") or DEFAULT_MAX_SECONDS)
    t0 = time.monotonic()

    def get(url: str, body: bytes | None) -> bytes | None:
        h.requests += 1
        try:
            return fetch(url, {"Referer": url.split("/", 3)[0] + "//" + url.split("/", 3)[2]
                               + "/"}, body)
        except Exception as exc:
            from libs.data.free_stack import classify
            h.failures[classify(exc)] += 1
            h.notes.append(f"{classify(exc)}: {url[:120]}")
            return None

    days = plan_days(cursor, now, row)
    done: list[date] = []
    retry: list[str] = []
    for d in days:
        if time.monotonic() - t0 > budget:
            h.notes.append(f"budget {budget:.0f}s spent; {len(days) - len(done)} days deferred")
            break
        f0 = Counter(h.failures)
        day = fetch_day(exch, d, get, urls, varieties)
        feats = day_features(exch, day, brokers)
        if not feats:
            # A weekday with no file. Only a 404 / empty answer is a holiday, and only once the
            # day is two days old; any other failure (proxy, timeout, 5xx) is a RETRY whatever
            # the day's age -- an outage must never be recorded as a market closure.
            new = Counter(h.failures) - f0
            hard = {k: v for k, v in new.items() if k != "http_404"}
            if hard or (now.date() - d).days <= 2:
                retry.append(d.isoformat())
            done.append(d)
            continue
        done.append(d)
        pub = release_utc(d, hhmm)
        if d.weekday() == 4 and day.inv:
            pub = max(pub, release_utc(d, str(row.get("weekly_release_bjt") or hhmm)))
        ptr = f"raw/{row['id']}/{now.date().isoformat()}.jsonl#{exch}:{d.isoformat()}"
        hsh = _sha(json.dumps(day.hashes, sort_keys=True).encode())
        h.raw.append({"exchange": exch, "event_time": d.isoformat(),
                      "publication_time": pub.isoformat(), "received_at": now.isoformat(),
                      "provenance_hash": hsh, "file_hashes": day.hashes,
                      "missing_surfaces": day.missing,
                      "ranks": {p: {s: [[m, q, c] for m, (q, c) in
                                        sorted(b.items(), key=lambda kv: -kv[1][0])[:20]]
                                    for s, b in bk.items() if s != "__scope__"}
                                for p, bk in day.ranks.items()},
                      "features": feats})
        for prod, fm in feats.items():
            for metric, v in fm.items():
                key = f"{prod}_{metric}"
                h.obs.append({"key": key, "period_end": d.isoformat(), "value": v,
                              **contract_fields(row, exch, prod, metric, d, pub, now, hsh,
                                                ptr)})
    held = [x for x in done if x.isoformat() not in retry]
    if held:
        nd, od = max(held), min(held)
        cur_new = cursor.get("newest")
        cur_old = cursor.get("oldest")
        h.cursor["newest"] = max(nd.isoformat(), cur_new) if cur_new else nd.isoformat()
        h.cursor["oldest"] = min(od.isoformat(), cur_old) if cur_old else od.isoformat()
    h.cursor["retry"] = sorted(set(retry))[-60:]
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no exchange files"
    return h


def axis_of(key: str) -> str | None:
    """Which PART II axis a column belongs to (the proposer reports cells per axis)."""
    if key.endswith("_px_div"):
        return "divergence"
    if re.search(r"_(wr|inv)(_|$)", key):
        return "inventory"
    if re.search(r"_(ts_slope|roll_yield|curv)$", key):
        return "curve"
    if re.search(r"_(long|short|net|state|citic|conc|vol_c)", key):
        return "positioning"
    return None


def signal_columns(keys: Sequence[str], exch: str) -> dict[str, dict[str, Any]]:
    """columns.json entries for the hypothesis-grade keys present, mapped by product."""
    out: dict[str, dict[str, Any]] = {}
    for k in keys:
        for metric, why in SIGNAL_METRICS.items():
            if k.endswith("_" + metric):
                prod = k[: -len(metric) - 1]
                tgt = PRODUCT_TARGETS.get(prod) or PRODUCT_TARGETS.get(prod.upper())
                if tgt and "_" not in prod:
                    out[k] = {"hypothesis": list(tgt), "event": [],
                              "why": f"{exch.upper()} {prod} {why}"}
                break
    return out
