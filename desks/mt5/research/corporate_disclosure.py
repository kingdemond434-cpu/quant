#!/usr/bin/env python3
"""THE PRIMARY-DISCLOSURE MOAT: every listed company's own filings, in its own language, dated.

WHAT WAS MISSING (reports/asia_quant_gap_2026-09-30.md, row 6). The desk reads Japanese, Korean
and Chinese RESEARCH TEXT -- Qiita, Zenn, DCInside, Juejin -- and not one primary disclosure: no
TDnet, no EDINET, no DART, no cninfo/SSE/SZSE. EventVestor-style corporate event data was bought
by the institutions this desk competes with; the regulators publish the same facts free, first
and in the native language, and nothing here fetched them.

THE SOURCES, and what each one needs (the rows are DATA in `SOURCES` and are upserted into the
existing grounds file `data/asia_sources.json` every pass, with licence and machine_use_allowed):

    tdnet_yanoshin   JP timely disclosure (TDnet) via the keyless yanoshin webapi mirror
    edinet_v2        JP statutory filings, EDINET API v2          -- free Subscription-Key
    jquants_free     JP statements with the company's own forecast -- free J-Quants account
    dart_openapi     KR filings, DART OpenAPI                      -- free crtfc_key
    cninfo           CN announcements, the CSRC-designated site   -- keyless
    sse_bulletin     CN Shanghai exchange bulletins                -- keyless (Referer declared)
    szse_annlist     CN Shenzhen exchange announcements           -- keyless
    sec_edgar_8k     US 8-K items and foreign issuers' 6-K         -- no key; SEC fair-access
                                                                     policy needs a contact UA

A keyed source with no key is BLOCKED_NO_KEY, its yield is UNMEASURED, and the key's name and
registration URL are in the report. A key is read from `data/secrets/disclosure_apis.json` (or
the environment) and never printed, logged, vaulted or written to a report: every URL that
carried one is redacted before it is recorded anywhere.

WHAT EVERY ROW BECOMES. One disclosure -> one EVENT ROW, classified from its native-language
title (決算短信, 業績予想の修正, 영업(잠정)실적, 业绩预告, 8-K Item 2.02 ...) into a category, a sign
where the title carries one (上方修正 / 下方修正, 预增 / 预减), and SCHEDULED or not; stamped with
`at`, the moment the market could first know; and resolved to MT5 instruments THROUGH THE
BROKER'S REGISTRY, never a typed symbol list:

    symbols    the issuer's own share CFD, matched by name against the registry's keys
    peers      declared supply-chain / sector peers (Samsung -> TSMC, BYD -> NIO) the broker quotes
    transmits  the country's index and USD-leg pair, derived from the registry's asset class and
               profit currency (JPN225/USDJPY, USDKRW, HK50/CHINAH/USDCNH, the US indices)

and then flows three ways, which is the principal's order for every source (`uses` on each row):

  (a) DIRECT -- event cells. `event_reaction` (scheduled categories) and `news_reaction`
      (unscheduled) cells whose params NAME the stream, so the family loads its own dated events
      (`mt5desk.disclosure_events`) through the sealed gauntlet's ordinary call. Donated as
      EXACT_RECIPE rows to `data/intelligence/corporate_disclosure/`.
  (b) INDIRECT -- regime conditions. A daily point-in-time disclosure-flow series per source and
      per country (`data/lake/series/`, with its `.pit.json`), which `pack_cells` already turns
      into `exogenous_conditioner` cells, and which this organ donates as `exogenous_gate` cells:
      an existing price family on the mapped instrument, taken only while the flow is extreme.
  (c) ALLOCATION STATE. `data/corporate_disclosure_state.json`: per instrument, today's flow z,
      the revision balance and the burst flag, and the news lane reads the event rows
      (`news_event_stream`), which nudges `world_state.json` and lodges the allocator's re-solve
      request. The allocator itself reads neither; wiring it is money-path and is NOT done here.

NOTHING HERE SIZES, VETOES OR JUDGES. It fetches, classifies, maps, stamps and donates; the one
gauntlet decides. Every trial the donations cause is charged where every other trial is.

    python desks/mt5/research/corporate_disclosure.py --once --budget-s 600
    python desks/mt5/research/corporate_disclosure.py --once --fixtures desks/mt5/tests/fixtures/corporate_disclosure
    python desks/mt5/research/corporate_disclosure.py --keys        # PRESENT/ABSENT, never a value
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
UNIVERSE = DATA / "universe" / "universe.json"
GROUNDS = DATA / "asia_sources.json"
SECRETS = DATA / "secrets" / "disclosure_apis.json"
EVENTS = DATA / "lake" / "events" / "corporate_disclosure"
SERIES = DATA / "lake" / "series"
VAULT = DATA / "lake" / "vault"
CURSOR = DATA / "corporate_disclosure_cursor.json"
STATE = DATA / "corporate_disclosure_state.json"
SEAT = DATA / "intelligence" / "corporate_disclosure"
REPORT = DESK / "reports" / "CORPORATE_DISCLOSURE.json"
ROSTER = ROOT / "libs" / "mining" / "sources.yaml"

SOURCE = "corporate_disclosure"
UNMEASURED = "UNMEASURED"
BLOCKED_NO_KEY = "BLOCKED_NO_KEY"

#: Requests one source may spend in one pass, and the pause between two requests to one host.
#: Not a cap on what a source may yield: the cursor resumes where the pass stopped.
MAX_REQUESTS_PER_SOURCE = int(os.environ.get("DISCLOSURE_MAX_REQUESTS", "40"))
HOST_DELAY_S = float(os.environ.get("DISCLOSURE_HOST_DELAY_S", "1.5"))
MAX_BYTES = 12 * 1024 * 1024
TIMEOUT_S = 25.0
#: Days re-fetched every pass because the day is still being published (today, yesterday).
LIVE_DAYS = 2
#: Keep this many days of per-date bookkeeping for the live window; older dates are final.
RECENT_ID_DAYS = 4
#: Minimum event-days before a spec is donated, and minimum series rows for a conditioner. Below
#: either, the spec is UNMEASURED with its count -- never donated on thin history.
MIN_EVENT_DAYS = 12
MIN_SERIES_ROWS = 30
#: Specs donated per pass. The cursor carries the rest to the next pass; nothing is dropped.
DONATE_PER_PASS = int(os.environ.get("DISCLOSURE_DONATE_PER_PASS", "400"))
#: Price-only base families an `exogenous_gate` cell conditions (the compiler's own price-only
#: vocabulary, every one wrappable from bars and params alone).
GATE_BASES: tuple[str, ...] = ("session_range_breakout", "overnight_gap_decay", "trend_ma_cross",
                               "mean_reversion_bollinger", "volatility_squeeze")
#: Bands of `family_exogenous_gate.BANDS` minted per (series, base): the one-sided extremes.
GATE_BANDS: tuple[str, ...] = ("high", "low")

#: Local offset of each country's publication day. None of JP/KR/CN keeps summer time; the US
#: figure is EST, which makes an end-of-day stamp an hour LATE in summer -- conservative.
TZ_H: dict[str, int] = {"jp": 9, "kr": 9, "cn": 8, "us": -5}
#: Which currencies a country's transmission instruments are quoted in: its index (by profit
#: currency) and its USD-leg pair. A declaration about COUNTRIES; the symbols come from the
#: registry.
COUNTRY_CCY: dict[str, dict[str, tuple[str, ...]]] = {
    "jp": {"index": ("JPY",), "fx": ("JPY",)},
    "kr": {"index": ("KRW",), "fx": ("KRW",)},
    "cn": {"index": ("HKD", "CNH", "CNY"), "fx": ("CNH", "CNY")},
    "us": {"index": ("USD",), "fx": ()},
}

#: CULTURE PROVENANCE ON EVERY DONATED ROW (principal, 2026-09-30 14:18). Field names exactly as
#: `libs/research/cell_culture.py` declares them; plain keys until that module lands.
CULTURE: dict[str, dict[str, str]] = {
    "jp": {"source_culture": "JP", "participant_structure": "retail_heavy",
           "failure_mode_hypothesis": (
               "TDnet releases cluster at 15:00 JST after the Tokyo close and Japanese retail "
               "margin traders fade disclosure moves, so the reaction lands in the next Tokyo "
               "session and in USDJPY overnight, failing when the Western reading of the same "
               "news is already priced")},
    "kr": {"source_culture": "KR", "participant_structure": "retail_heavy",
           "failure_mode_hypothesis": (
               "Korean retail dominates turnover and DART filings land after the 15:30 KST close, "
               "so the reaction arrives at the next Seoul open through foreign flow and USDKRW, "
               "failing on days foreign investors are net sellers regardless of the filing")},
    "cn": {"source_culture": "CN", "participant_structure": "settlement_constrained",
           "failure_mode_hypothesis": (
               "A-share T+1 settlement and daily price limits delay and truncate the reaction to "
               "a cninfo announcement, so it spills into HK50/CHINAH and USDCNH and fails when "
               "policy (PBoC, CSRC) rather than the filing drives mainland prices")},
    "us": {"source_culture": "US", "participant_structure": "institutional",
           "failure_mode_hypothesis": (
               "8-K items are absorbed by institutional algorithms within minutes of EDGAR "
               "acceptance, so the residual drift is the fastest-decaying version and fails "
               "first when that liquidity is present")},
}

LICENCE_NOTE = ("routing and provenance label (LAWS 5e): says what may be REDISTRIBUTED, never "
                "whether the published facts may be read and tested")

#: THE SOURCE ROWS. Roster-ready (id, cadence, auth, licence, machine_use_allowed, cursor) for
#: `libs/mining/sources.yaml`, and upserted into `data/asia_sources.json` every pass.
SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "tdnet_yanoshin", "name": "TDnet timely disclosure (yanoshin webapi mirror)",
     "country": "jp", "plane": "jp", "language": "ja", "cadence": "hourly",
     "url": "https://webapi.yanoshin.jp/webapi/tdnet/list/{yyyymmdd}.json?limit=1000",
     "auth": "none", "access": "public", "key_names": [],
     "licence": "TDnet content (c) JPX; mirror by yanoshin, free API, attribution requested",
     "machine_use_allowed": True, "backfill_days": 30,
     "pit": {"event_time": "TDnet publication time (JST, minute)", "precision": "minute"}},
    {"id": "edinet_v2", "name": "EDINET API v2 (FSA statutory filings)",
     "country": "jp", "plane": "jp", "language": "ja", "cadence": "hourly",
     "url": "https://api.edinet-fsa.go.jp/api/v2/documents.json?date={yyyy-mm-dd}&type=2",
     "auth": "key", "access": "key", "key_names": ["EDINET_API_KEY"], "key_param": "Subscription-Key",
     "registration_url": "https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1",
     "licence": "FSA EDINET terms of use; public-sector information, reuse permitted",
     "machine_use_allowed": True, "backfill_days": 400,
     "pit": {"event_time": "submitDateTime (JST, minute)", "precision": "minute"}},
    {"id": "jquants_free", "name": "J-Quants free plan: financial statements with forecasts",
     "country": "jp", "plane": "jp", "language": "ja", "cadence": "daily",
     "url": "https://api.jquants.com/v1/fins/statements?date={yyyy-mm-dd}",
     "auth": "account", "access": "key", "key_names": ["JQUANTS_REFRESH_TOKEN"],
     "registration_url": "https://jpx-jquants.com/",
     "licence": "J-Quants API terms (JPX); free plan, personal-use licence, data delayed 12 weeks",
     "machine_use_allowed": True, "backfill_days": 400, "lag_days": 84,
     "pit": {"event_time": "DisclosedDate + DisclosedTime (JST)", "precision": "minute",
             "live_usable": False,
             "note": "free plan serves each statement 12 weeks late: the EVENT time is exact and "
                     "backtests are point-in-time; the desk cannot trade it live"}},
    {"id": "dart_openapi", "name": "DART OpenAPI (FSS Korea filings)",
     "country": "kr", "plane": "kr", "language": "ko", "cadence": "hourly",
     "url": ("https://opendart.fss.or.kr/api/list.json?bgn_de={yyyymmdd}&end_de={yyyymmdd}"
             "&page_no={page}&page_count=100"),
     "auth": "key", "access": "key", "key_names": ["DART_API_KEY"], "key_param": "crtfc_key",
     "registration_url": "https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do",
     "licence": "OpenDART terms; public information, free API, 20,000 calls/day",
     "machine_use_allowed": True, "backfill_days": 400,
     "pit": {"event_time": "rcept_dt (KST, day) -- stamped at the END of the day",
             "precision": "day"}},
    {"id": "cninfo", "name": "cninfo 巨潮资讯 announcements (CSRC-designated)",
     "country": "cn", "plane": "cn_hard", "language": "zh", "cadence": "hourly",
     "url": "http://www.cninfo.com.cn/new/hisAnnouncement/query",
     "auth": "none", "access": "public", "key_names": [], "columns": ["szse", "sse"],
     "licence": "cninfo terms; public statutory disclosure, redistribution restricted",
     "machine_use_allowed": True, "backfill_days": 120,
     "pit": {"event_time": "announcementTime (CST, day) -- stamped at the END of the day",
             "precision": "day"}},
    {"id": "sse_bulletin", "name": "SSE 上交所 company bulletins",
     "country": "cn", "plane": "cn_hard", "language": "zh", "cadence": "hourly",
     "url": ("https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?isPagination=true"
             "&pageHelp.pageSize=100&pageHelp.pageNo={page}&pageHelp.beginPage={page}"
             "&START_DATE={yyyy-mm-dd}&END_DATE={yyyy-mm-dd}"),
     "auth": "none", "access": "public", "key_names": [],
     "request_headers": {"Referer": "https://www.sse.com.cn/"},
     "licence": "SSE website terms; public exchange disclosure",
     "machine_use_allowed": True, "backfill_days": 0,
     "pit": {"event_time": "ADDDATE/SSEDATE (CST)", "precision": "day"}},
    {"id": "szse_annlist", "name": "SZSE 深交所 announcements",
     "country": "cn", "plane": "cn_hard", "language": "zh", "cadence": "hourly",
     "url": "https://www.szse.cn/api/disc/announcement/annList",
     "auth": "none", "access": "public", "key_names": [],
     "licence": "SZSE website terms; public exchange disclosure",
     "machine_use_allowed": True, "backfill_days": 0,
     "pit": {"event_time": "publishTime (CST, minute)", "precision": "minute"}},
    {"id": "sec_edgar_8k", "name": "SEC EDGAR full-text search: 8-K items and 6-K",
     "country": "us", "plane": "north_america", "language": "en", "cadence": "hourly",
     "url": ("https://efts.sec.gov/LATEST/search-index?q=&forms=8-K,6-K&dateRange=custom"
             "&startdt={yyyy-mm-dd}&enddt={yyyy-mm-dd}&from={offset}"),
     "auth": "user_agent", "access": "public", "key_names": ["SEC_EDGAR_UA"],
     "registration_url": "https://www.sec.gov/os/accessing-edgar-data (no registration: a "
                         "User-Agent naming a contact, e.g. 'Desk Name admin@domain')",
     "licence": "US government work, public domain; SEC fair-access policy (<=10 req/s, UA)",
     "machine_use_allowed": True, "backfill_days": 120,
     "pit": {"event_time": "file_date (ET, day) -- stamped at the END of the day",
             "precision": "day"}},
)

#: Where each source's rows go, so the coordinator's roster can read `uses` off the row.
USES: dict[str, Any] = {
    "direct": {"families": ["event_reaction", "news_reaction"],
               "consumer": "desks/mt5/research/corporate_disclosure.py -> "
                           "data/intelligence/corporate_disclosure/ -> miner_candidate_compiler "
                           "(EXACT_RECIPE) -> merge_docket -> external_gauntlet",
               "loader": "desks/mt5/mt5desk/disclosure_events.py"},
    "indirect": {"families": ["exogenous_conditioner", "exogenous_gate"],
                 "consumer": "data/lake/series/<id>.csv -> research/pack_cells.py; and "
                             "exogenous_gate donations through the same seat"},
    "allocation": {"artifact": "desks/mt5/data/corporate_disclosure_state.json",
                   "consumer": "desks/mt5/research/news_event_stream.py (event rows -> "
                               "world_state.json -> allocator_resolve_request.json); the "
                               "allocator does not read it directly (money path, not wired)"},
}

#: Issuers whose disclosures are named individually: their names in the filings' own languages,
#: their native codes, the SHORT names the broker's registry might quote them under, and declared
#: peers (by short name). The MT5 symbol is RESOLVED against the registry at run time; an issuer
#: the broker does not quote simply resolves to nothing.
ISSUERS: tuple[dict[str, Any], ...] = (
    {"short": ["Toyota"], "names": ["Toyota Motor", "トヨタ自動車"], "jp": "7203",
     "peers": ["Honda", "Tesla"]},
    {"short": ["Honda"], "names": ["Honda Motor", "本田技研工業"], "jp": "7267", "peers": ["Toyota"]},
    {"short": ["Sony"], "names": ["Sony Group", "ソニーグループ"], "jp": "6758", "peers": ["Apple"]},
    {"short": ["Nintendo"], "names": ["Nintendo", "任天堂"], "jp": "7974", "peers": []},
    {"short": ["SoftBank"], "names": ["SoftBank Group", "ソフトバンクグループ"], "jp": "9984",
     "peers": ["NVIDIA", "AlibabaGroup"]},
    {"short": ["TokyoElectron"], "names": ["Tokyo Electron", "東京エレクトロン"], "jp": "8035",
     "peers": ["TSMC", "AppliedMaterials"]},
    {"short": ["Advantest"], "names": ["Advantest", "アドバンテスト"], "jp": "6857",
     "peers": ["NVIDIA", "TSMC"]},
    {"short": ["FastRetailing"], "names": ["Fast Retailing", "ファーストリテイリング"], "jp": "9983",
     "peers": []},
    {"short": ["Samsung"], "names": ["Samsung Electronics", "삼성전자"], "kr": "005930",
     "peers": ["TSMC", "Micron", "Apple"]},
    {"short": ["SKHynix"], "names": ["SK hynix", "SK하이닉스"], "kr": "000660",
     "peers": ["NVIDIA", "Micron", "TSMC"]},
    {"short": ["Hyundai"], "names": ["Hyundai Motor", "현대자동차"], "kr": "005380",
     "peers": ["Toyota"]},
    {"short": ["LGEnergySolution"], "names": ["LG Energy Solution", "LG에너지솔루션"],
     "kr": "373220", "peers": ["Tesla", "NIO"]},
    {"short": ["BYD"], "names": ["BYD", "比亚迪"], "cn": "002594", "peers": ["NIO", "Tesla"]},
    {"short": ["CATL"], "names": ["Contemporary Amperex", "宁德时代"], "cn": "300750",
     "peers": ["NIO", "Tesla"]},
    {"short": ["SMIC"], "names": ["Semiconductor Manufacturing International", "中芯国际"],
     "cn": "688981", "peers": ["TSMC", "AppliedMaterials"]},
    {"short": ["Moutai"], "names": ["Kweichow Moutai", "贵州茅台"], "cn": "600519", "peers": []},
    {"short": ["TSMC"], "names": ["Taiwan Semiconductor Manufacturing", "台積電"],
     "peers": ["NVIDIA", "AppliedMaterials"]},
    {"short": ["AlibabaGroup", "Alibaba"], "names": ["Alibaba Group Holding", "阿里巴巴"],
     "peers": ["Baidu"]},
    {"short": ["Baidu"], "names": ["Baidu", "百度"], "peers": ["AlibabaGroup"]},
    {"short": ["NIO"], "names": ["NIO Inc", "蔚来"], "peers": ["Tesla"]},
)

#: ------------------------------------------------------------------ classification tables
#: (category, direction, pattern) checked in order; the first hit wins. Native-language first.
SCHEDULED = frozenset({"earnings", "periodic_report", "monthly_sales", "dividend"})
_JA: tuple[tuple[str, int, str], ...] = (
    ("guidance_revision", 1, r"上方修正"), ("guidance_revision", -1, r"下方修正"),
    ("guidance_revision", 0, r"業績予想の修正|業績予想修正|予想値と実績値との差異"),
    ("tender_offer", 0, r"公開買付|TOB"), ("mna", 0, r"合併|買収|株式交換|株式移転|子会社化|事業譲渡"),
    ("buyback", 1, r"自己株式の取得|自己株式取得|自社株買い|自己株券買付"),
    ("equity_issuance", -1, r"新株式発行|第三者割当|公募|新株予約権の発行"),
    ("dividend", 1, r"増配"), ("dividend", -1, r"減配|無配"), ("dividend", 0, r"配当"),
    ("earnings", 0, r"決算短信|決算説明|四半期決算"),
    ("periodic_report", 0, r"有価証券報告書|四半期報告書|半期報告書"),
    ("monthly_sales", 0, r"月次|月度"), ("impairment", -1, r"特別損失|減損"),
    ("halt_resume", 0, r"上場廃止|監理銘柄|整理銘柄"), ("control_change", 0, r"大量保有|主要株主"),
    ("split", 0, r"株式分割|株式併合"), ("correction", 0, r"訂正"),
    ("personnel", 0, r"人事|役員|代表取締役"),
)
_KO: tuple[tuple[str, int, str], ...] = (
    ("earnings", 0, r"영업\(잠정\)실적|영업실적|잠정실적"),
    ("guidance_revision", 0, r"매출액또는손익구조|손익구조"),
    ("tender_offer", 0, r"공개매수"), ("mna", 0, r"합병|분할합병|주식교환|영업양수|타법인주식및출자증권취득"),
    ("buyback", 1, r"자기주식취득|자기주식 취득"), ("buyback", -1, r"자기주식처분"),
    ("equity_issuance", -1, r"유상증자|전환사채|신주인수권부사채|교환사채"),
    ("dividend", 0, r"현금ㆍ현물배당|현금·현물배당|배당"),
    ("contract", 0, r"단일판매ㆍ공급계약|단일판매·공급계약|공급계약"),
    ("control_change", 0, r"최대주주변경|최대주주 변경|대량보유"),
    ("insider_trade", 0, r"임원ㆍ주요주주|임원·주요주주|소유상황보고"),
    ("halt_resume", 0, r"거래정지|매매거래정지|상장폐지"), ("regulatory", -1, r"불성실공시|조회공시"),
    ("periodic_report", 0, r"사업보고서|분기보고서|반기보고서"), ("correction", 0, r"정정"),
    ("personnel", 0, r"대표이사변경|임원"),
)
_ZH: tuple[tuple[str, int, str], ...] = (
    ("guidance_revision", 1, r"预增|扭亏|略增"), ("guidance_revision", -1, r"预减|首亏|续亏|预亏|略减"),
    ("guidance_revision", 0, r"业绩预告|业绩快报"),
    ("tender_offer", 0, r"要约收购"), ("mna", 0, r"重大资产重组|收购|并购|吸收合并|资产置换"),
    ("buyback", 1, r"回购"), ("insider_trade", 1, r"增持"), ("insider_trade", -1, r"减持"),
    ("equity_issuance", -1, r"非公开发行|定向增发|向特定对象发行|配股|可转换公司债券|可转债"),
    ("dividend", 0, r"利润分配|权益分派|分红"),
    ("earnings", 0, r"年度报告|半年度报告|季度报告|年报|季报"),
    ("halt_resume", 0, r"停牌|复牌|退市|风险警示"),
    ("regulatory", -1, r"问询函|关注函|立案|行政处罚|监管函|警示函"),
    ("contract", 0, r"中标|重大合同|签订.*合同"), ("litigation", -1, r"诉讼|仲裁"),
    ("control_change", 0, r"控股股东|实际控制人变更|权益变动"), ("correction", 0, r"更正"),
    ("personnel", 0, r"董事会决议|辞职|聘任"),
)
#: 8-K items -> category. 6-K carries no item list and is classified from its title.
EDGAR_ITEMS: dict[str, tuple[str, int]] = {
    "1.01": ("contract", 0), "1.02": ("contract", -1), "1.03": ("distress", -1),
    "1.05": ("cyber", -1), "2.01": ("mna", 0), "2.02": ("earnings", 0), "2.03": ("financing", 0),
    "2.04": ("distress", -1), "2.05": ("impairment", -1), "2.06": ("impairment", -1),
    "3.01": ("halt_resume", -1), "3.02": ("equity_issuance", -1), "4.01": ("governance", 0),
    "4.02": ("restatement", -1), "5.01": ("control_change", 0), "5.02": ("personnel", 0),
    "5.03": ("governance", 0), "5.07": ("governance", 0), "7.01": ("other", 0),
    "8.01": ("other", 0), "9.01": ("other", 0),
}
#: Rows kept as full event rows regardless of mapping: the unscheduled classes a headline lane is
#: for. Everything else unmapped is kept as one per-day COUNT row, which is what an index burst
#: needs and one-thousandth of the bytes.
NOTABLE = frozenset({"guidance_revision", "tender_offer", "mna", "buyback", "equity_issuance",
                     "impairment", "halt_resume", "regulatory", "restatement", "distress",
                     "control_change", "contract", "cyber", "litigation", "insider_trade"})


def classify(country: str, title: str, items: Iterable[str] = ()) -> tuple[str, int, bool]:
    """(category, direction, scheduled) from the NATIVE title. No model, no translation."""
    cc = (country or "").lower()
    item_list = [str(i).strip() for i in items if str(i).strip()]
    if item_list:
        ranked = [EDGAR_ITEMS[i] for i in item_list if i in EDGAR_ITEMS]
        ranked = [r for r in ranked if r[0] != "other"] or ranked
        if ranked:
            cat, d = ranked[0]
            return cat, d, cat in SCHEDULED
    table = {"jp": _JA, "kr": _KO, "cn": _ZH}.get(cc, ())
    for cat, d, pat in table:
        if re.search(pat, title or ""):
            return cat, d, cat in SCHEDULED
    low = (title or "").lower()
    for cat, d, pat in (("earnings", 0, r"results|earnings|quarterly report"),
                        ("mna", 0, r"merger|acquisition|tender offer"),
                        ("buyback", 1, r"repurchase|buyback"),
                        ("guidance_revision", 0, r"guidance|outlook"),
                        ("dividend", 0, r"dividend")):
        if re.search(pat, low):
            return cat, d, cat in SCHEDULED
    return "other", 0, False


# ============================================================================ small utilities
def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(p)


def _norm(text: Any) -> str:
    return re.sub(r"[^0-9a-z]", "", str(text or "").lower())


_SUFFIXES = frozenset({"inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
                       "limited", "plc", "holdings", "holding", "group", "sa", "nv", "ag", "se",
                       "the", "adr", "de", "llc", "lp", "class", "com"})


def _name_forms(name: str) -> set[str]:
    """The normalised forms of an issuer name a registry key may equal: whole, and suffix-stripped."""
    toks = [t for t in re.split(r"[^0-9a-z]+", str(name or "").lower()) if t]
    if not toks:
        return set()
    core = [t for t in toks if t not in _SUFFIXES] or toks
    return {"".join(toks), "".join(core)}


# ============================================================================ the registry
def registry() -> dict[str, dict[str, Any]]:
    doc = _read(UNIVERSE, {})
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)} if isinstance(doc, dict) \
        else {}


def _asset_class(meta: Mapping[str, Any]) -> str:
    return str(meta.get("asset_class") or "").strip().lower()


def equity_index(reg: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """normalised registry key -> registry key, for share CFDs only (the broker's own class)."""
    out: dict[str, str] = {}
    for sym, meta in reg.items():
        if "equit" in _asset_class(meta) or "share" in _asset_class(meta) \
                or "stock" in _asset_class(meta):
            n = _norm(sym.split(".")[0])
            if len(n) >= 2:
                out.setdefault(n, sym)
    return out


def transmission_targets(country: str, reg: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The country's index CFDs and USD-leg pairs, DERIVED from the registry's class and currency.

    Indices first (the disclosure flow is an equity fact before it is a currency one), then the
    USD pair. Empty when the registry is unreadable -- which is reported, never guessed around.
    """
    spec = COUNTRY_CCY.get(country.lower())
    if not spec:
        return []
    # A CURRENCY INDEX (USDX) quotes in its own currency and is not the country's equity index.
    idx = sorted(s for s, m in reg.items()
                 if _asset_class(m) in ("indices", "index")
                 and str(m.get("currency_profit") or "").upper() in spec["index"]
                 and not s.upper().startswith(str(m.get("currency_profit") or "").upper()))
    fx = sorted(s for s, m in reg.items()
                if "forex" in _asset_class(m) and len(s) == 6 and s.isalpha()
                and s[:3].upper() == "USD" and s[3:].upper() in spec["fx"])
    return idx + fx


class Resolver:
    """Issuer -> MT5 instruments, through the registry. Built once per pass."""

    def __init__(self, reg: Mapping[str, Mapping[str, Any]]) -> None:
        self.reg = dict(reg)
        self.eq = equity_index(self.reg)
        self.targets = {cc: transmission_targets(cc, self.reg) for cc in COUNTRY_CCY}
        self.by_code: dict[tuple[str, str], dict[str, Any]] = {}
        self.names: list[tuple[str, dict[str, Any]]] = []
        for iss in ISSUERS:
            for cc in ("jp", "kr", "cn"):
                if iss.get(cc):
                    self.by_code[(cc, str(iss[cc]))] = iss
            for nm in iss.get("names") or ():
                self.names.append((str(nm), iss))

    def _registry_symbol(self, shorts: Iterable[str], names: Iterable[str] = ()) -> str | None:
        for s in [*shorts, *names]:
            for form in ({_norm(s)} | _name_forms(s)):
                if form in self.eq:
                    return self.eq[form]
        return None

    def issuer_for(self, country: str, code: str, name: str) -> dict[str, Any] | None:
        code = re.sub(r"\D", "", str(code or ""))
        if country == "jp" and len(code) == 5 and code.endswith("0"):
            code = code[:4]                        # TDnet/EDINET write the 4-digit code + check 0
        hit = self.by_code.get((country, code))
        if hit is not None:
            return hit
        low = str(name or "")
        for nm, iss in self.names:
            if nm and (nm in low or _norm(nm) and _norm(nm) in _norm(low)):
                return iss
        return None

    def resolve(self, country: str, code: str, name: str) -> dict[str, list[str]]:
        iss = self.issuer_for(country, code, name)
        own: list[str] = []
        peers: list[str] = []
        if iss is not None:
            sym = self._registry_symbol(iss.get("short") or (), iss.get("names") or ())
            if sym:
                own.append(sym)
            for p in iss.get("peers") or ():
                ps = self._registry_symbol([p])
                if ps and ps not in own and ps not in peers:
                    peers.append(ps)
        elif country == "us":
            # A US filer is matched by NAME ONLY against the broker's own share keys: the whole
            # name or the name with its corporate suffixes removed must EQUAL a key, so
            # "META MATERIALS" can never become Meta. A miss is a miss, never a guess.
            for form in _name_forms(name):
                if form in self.eq:
                    own.append(self.eq[form])
                    break
        return {"symbols": own, "peers": peers, "transmits": list(self.targets.get(country, []))}


# ============================================================================ secrets
def read_keys(path: Path | None = None) -> dict[str, str]:
    """Key name -> value from the box's secrets file, then the environment. NEVER printed."""
    out: dict[str, str] = {}
    doc = _read(path or SECRETS, {})
    if isinstance(doc, dict):
        for k, v in doc.items():
            got = v.get("key") if isinstance(v, dict) else v
            if isinstance(got, str) and got.strip():
                out[str(k)] = got.strip()
    env_alias = {"EDINET_API_KEY": ("EDINET_API_KEY",), "DART_API_KEY": ("DART_API_KEY",),
                 "JQUANTS_REFRESH_TOKEN": ("JQUANTS_REFRESH_TOKEN", "JQUANTS_TOKEN"),
                 "SEC_EDGAR_UA": ("SEC_EDGAR_UA", "QUANT_EDGAR_UA"),
                 "JQUANTS_MAIL": ("JQUANTS_MAIL",), "JQUANTS_PASSWORD": ("JQUANTS_PASSWORD",)}
    for name, envs in env_alias.items():
        if name not in out:
            for e in envs:
                if os.environ.get(e, "").strip():
                    out[name] = os.environ[e].strip()
                    break
    return out


def key_status(keys: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Per source: PRESENT / ABSENT per declared key name. Never a value, prefix or length."""
    held = dict(keys) if keys is not None else read_keys()
    out: dict[str, dict[str, Any]] = {}
    for src in SOURCES:
        names = list(src.get("key_names") or [])
        out[src["id"]] = {"auth": src["auth"], "keys": {n: ("PRESENT" if held.get(n) else "ABSENT")
                                                        for n in names},
                          "registration_url": src.get("registration_url", "")}
    return out


def redact(text: Any, secrets: Iterable[str]) -> str:
    out = str(text)
    for s in sorted({str(x) for x in secrets if x}, key=len, reverse=True):
        out = out.replace(s, "***").replace(urllib.parse.quote(s, safe=""), "***")
    return out


# ============================================================================ transport
class Http:
    """One polite fetcher: per-host spacing, a byte cap, the collector's verified TLS context."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self.last: dict[str, float] = {}
        self.secrets = [s for s in secrets if s]
        try:
            from research.asia_collector import _tls_context
            self.tls = _tls_context()
        except Exception:
            self.tls = None

    def __call__(self, url: str, *, data: bytes | None = None,
                 headers: Mapping[str, str] | None = None) -> tuple[int, str, bytes, str]:
        host = urllib.parse.urlsplit(url).netloc
        wait = HOST_DELAY_S - (time.monotonic() - self.last.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        self.last[host] = time.monotonic()
        hdr = {"User-Agent": "quant-desk-disclosure/1.0 (+public disclosure research)",
               "Accept": "application/json, text/plain, */*"}
        hdr.update(dict(headers or {}))
        req = urllib.request.Request(url, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=self.tls) as r:
                return (int(getattr(r, "status", 200) or 200),
                        str(r.headers.get("Content-Type") or ""), r.read(MAX_BYTES), "")
        except urllib.error.HTTPError as e:
            return int(e.code or 0), "", b"", redact(f"HTTP {e.code}", self.secrets)
        except Exception as e:                                   # noqa: BLE001
            return 0, "", b"", redact(f"{type(e).__name__}: {str(e)[:120]}", self.secrets)


def _json_body(body: bytes) -> Any:
    text = body.decode("utf-8-sig", errors="replace").strip()
    m = re.match(r"^[\w$.]+\((.*)\)\s*;?\s*$", text, re.S)     # JSONP (SSE answers either)
    if m:
        text = m.group(1)
    return json.loads(text)


def _vault(sid: str, body: bytes, url: str) -> str:
    """The raw bytes under their content hash, as asia_collector vaults them. URL pre-redacted."""
    digest = hashlib.sha256(body).hexdigest()
    d = VAULT / sid
    try:
        d.mkdir(parents=True, exist_ok=True)
        blob = d / f"{digest[:16]}.gz"
        if not blob.exists():
            blob.write_bytes(gzip.compress(body))
            blob.with_suffix(".meta.json").write_text(json.dumps(
                {"source_id": sid, "url": url, "sha256": digest, "bytes": len(body),
                 "fetched_utc": _now().isoformat(timespec="seconds")}), encoding="utf-8")
    except OSError:
        pass
    return digest


# ============================================================================ time
def _local_date(country: str, when: datetime | None = None) -> date:
    return ((when or _now()) + timedelta(hours=TZ_H.get(country, 0))).date()


def _stamp_local(country: str, text: str) -> str | None:
    """A local wall-clock 'YYYY-MM-DD HH:MM[:SS]' -> UTC ISO. None when unparseable."""
    t = str(text or "").strip().replace("T", " ").replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d%H%M%S"):
        try:
            loc = datetime.strptime(t[:19] if "%S" in fmt else t[:16], fmt)
        except ValueError:
            continue
        return (loc - timedelta(hours=TZ_H.get(country, 0))).replace(tzinfo=UTC).isoformat()
    return None


def _end_of_day(country: str, day: str) -> str | None:
    """A day-precision publication -> the END of that local day, in UTC. Late, never early."""
    d = re.sub(r"\D", "", str(day or ""))[:8]
    try:
        loc = datetime.strptime(d, "%Y%m%d") + timedelta(days=1)
    except ValueError:
        return None
    return (loc - timedelta(hours=TZ_H.get(country, 0))).replace(tzinfo=UTC).isoformat()


# ============================================================================ parsers
#: Every parser: (provider document) -> (raw rows as dicts, has_more). A raw row carries
#: native_id, code, name, title, at, precision, url, and optionally items / surprise.
def parse_tdnet(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    items = (doc or {}).get("items") if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    for it in items or []:
        t = it.get("Tdnet") if isinstance(it, dict) else None
        if not isinstance(t, dict):
            continue
        out.append({"native_id": str(t.get("id") or ""), "code": str(t.get("company_code") or ""),
                    "name": str(t.get("company_name") or ""), "title": str(t.get("title") or ""),
                    "at": _stamp_local("jp", str(t.get("pubdate") or "")), "precision": "minute",
                    "url": str(t.get("document_url") or "")})
    total = (doc or {}).get("total_count") if isinstance(doc, dict) else None
    try:
        more = int(total or 0) > len(out) and len(out) >= 1000
    except (TypeError, ValueError):
        more = False
    return out, more


def parse_edinet(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    res = (doc or {}).get("results") if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    for r in res or []:
        if not isinstance(r, dict) or str(r.get("withdrawalStatus") or "0") != "0":
            continue
        out.append({"native_id": str(r.get("docID") or ""), "code": str(r.get("secCode") or ""),
                    "name": str(r.get("filerName") or ""),
                    "title": str(r.get("docDescription") or ""),
                    "at": _stamp_local("jp", str(r.get("submitDateTime") or "")),
                    "precision": "minute", "doc_type": str(r.get("docTypeCode") or ""),
                    "url": f"https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?{r.get('docID')}"})
    return out, False


def parse_jquants(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    rows = (doc or {}).get("statements") if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        when = f"{r.get('DisclosedDate') or ''} {r.get('DisclosedTime') or '00:00:00'}"
        doc_type = str(r.get("TypeOfDocument") or "")
        surprise = None
        try:
            op, fop = float(r.get("OperatingProfit")), float(r.get("ForecastOperatingProfit"))
            if fop:
                surprise = (op - fop) / abs(fop)
        except (TypeError, ValueError):
            surprise = None
        out.append({"native_id": str(r.get("DisclosureNumber") or ""),
                    "code": str(r.get("LocalCode") or ""), "name": "",
                    "title": ("決算短信 " + doc_type) if "FinancialStatements" in doc_type
                    else ("業績予想の修正 " + doc_type) if "Forecast" in doc_type else doc_type,
                    "at": _stamp_local("jp", when), "precision": "minute", "url": "",
                    "surprise": surprise})
    return out, bool(isinstance(doc, dict) and doc.get("pagination_key"))


def parse_dart(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(doc, dict) or str(doc.get("status") or "") not in ("000", "013"):
        raise ValueError(f"DART status {doc.get('status') if isinstance(doc, dict) else '?'}: "
                         f"{(doc or {}).get('message') if isinstance(doc, dict) else ''}")
    out: list[dict[str, Any]] = []
    for r in doc.get("list") or []:
        if not isinstance(r, dict):
            continue
        out.append({"native_id": str(r.get("rcept_no") or ""), "code": str(r.get("stock_code") or ""),
                    "name": str(r.get("corp_name") or ""), "title": str(r.get("report_nm") or ""),
                    "at": _end_of_day("kr", str(r.get("rcept_dt") or "")), "precision": "day",
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.get('rcept_no')}"})
    try:
        more = int(doc.get("page_no") or page) < int(doc.get("total_page") or 0)
    except (TypeError, ValueError):
        more = False
    return out, more


def parse_cninfo(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    anns = (doc or {}).get("announcements") if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    for a in anns or []:
        if not isinstance(a, dict):
            continue
        try:
            day = datetime.fromtimestamp(int(a.get("announcementTime")) / 1000,
                                         tz=UTC) + timedelta(hours=8)
            at = _end_of_day("cn", day.strftime("%Y%m%d"))
        except (TypeError, ValueError, OSError):
            at = None
        title = re.sub(r"<[^>]+>", "", str(a.get("announcementTitle") or ""))
        out.append({"native_id": str(a.get("announcementId") or ""),
                    "code": str(a.get("secCode") or ""), "name": str(a.get("secName") or ""),
                    "title": title, "at": at, "precision": "day",
                    "url": ("http://static.cninfo.com.cn/" + str(a.get("adjunctUrl")))
                    if a.get("adjunctUrl") else ""})
    return out, bool(isinstance(doc, dict) and doc.get("hasMore"))


def parse_sse(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    ph = (doc or {}).get("pageHelp") if isinstance(doc, dict) else None
    data = (ph or {}).get("data") if isinstance(ph, dict) else None
    if data is None and isinstance(doc, dict):
        data = doc.get("result")
    flat: list[dict[str, Any]] = []
    for r in data or []:
        if isinstance(r, list):
            flat.extend(x for x in r if isinstance(x, dict))
        elif isinstance(r, dict):
            flat.append(r)
    out: list[dict[str, Any]] = []
    for r in flat:
        when = str(r.get("ADDDATE") or "")
        at = _stamp_local("cn", when) if len(when) >= 16 else None
        out.append({"native_id": str(r.get("URL") or r.get("TITLE") or ""),
                    "code": str(r.get("SECURITY_CODE") or ""),
                    "name": str(r.get("SECURITY_NAME") or ""), "title": str(r.get("TITLE") or ""),
                    "at": at or _end_of_day("cn", str(r.get("SSEDATE") or when)),
                    "precision": "minute" if at else "day",
                    "url": ("https://www.sse.com.cn" + str(r.get("URL"))) if r.get("URL") else ""})
    try:
        more = int((ph or {}).get("pageNo") or page) < int((ph or {}).get("pageCount") or 0)
    except (TypeError, ValueError, AttributeError):
        more = False
    return out, more


def parse_szse(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    data = (doc or {}).get("data") if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    for r in data or []:
        if not isinstance(r, dict):
            continue
        codes = r.get("secCode") or []
        names = r.get("secName") or []
        out.append({"native_id": str(r.get("id") or r.get("annId") or ""),
                    "code": str(codes[0] if isinstance(codes, list) and codes else codes or ""),
                    "name": str(names[0] if isinstance(names, list) and names else names or ""),
                    "title": str(r.get("title") or ""),
                    "at": _stamp_local("cn", str(r.get("publishTime") or "")), "precision": "minute",
                    "url": ("https://disc.static.szse.cn/download" + str(r.get("attachPath")))
                    if r.get("attachPath") else ""})
    try:
        more = page * 50 < int((doc or {}).get("announceCount") or 0)
    except (TypeError, ValueError, AttributeError):
        more = False
    return out, more


def parse_edgar(doc: Any, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    hits = ((doc or {}).get("hits") or {}) if isinstance(doc, dict) else {}
    out: list[dict[str, Any]] = []
    for h in hits.get("hits") or []:
        src = h.get("_source") if isinstance(h, dict) else None
        if not isinstance(src, dict):
            continue
        names = src.get("display_names") or []
        raw = str(names[0] if names else "")
        name = re.sub(r"\s*\((?:CIK|[A-Z.\-, ]+)[^)]*\)", "", raw).strip()
        form = str(src.get("form") or src.get("root_form") or "")
        items = [str(i) for i in (src.get("items") or [])]
        out.append({"native_id": str(src.get("adsh") or h.get("_id") or ""),
                    "code": ",".join(str(c) for c in (src.get("ciks") or [])), "name": name,
                    "title": f"{form} " + (" ".join(f"Item {i}" for i in items) or name),
                    "items": items, "at": _end_of_day("us", str(src.get("file_date") or "")),
                    "precision": "day", "url": ""})
    total = ((hits.get("total") or {}).get("value") if isinstance(hits.get("total"), dict)
             else hits.get("total"))
    try:
        more = page * 100 < int(total or 0)
    except (TypeError, ValueError):
        more = False
    return out, more


PARSERS: dict[str, Callable[[Any, int], tuple[list[dict[str, Any]], bool]]] = {
    "tdnet_yanoshin": parse_tdnet, "edinet_v2": parse_edinet, "jquants_free": parse_jquants,
    "dart_openapi": parse_dart, "cninfo": parse_cninfo, "sse_bulletin": parse_sse,
    "szse_annlist": parse_szse, "sec_edgar_8k": parse_edgar,
}


# ============================================================================ request plans
def request_for(src: Mapping[str, Any], day: date, page: int, keys: Mapping[str, str],
                unit: str = "") -> tuple[str, bytes | None, dict[str, str]]:
    """(url, body, headers) for one page of one date. Keys go in exactly where the provider
    documents them and nowhere else."""
    sid = src["id"]
    iso, compact = day.isoformat(), day.strftime("%Y%m%d")
    url = (str(src["url"]).replace("{yyyy-mm-dd}", iso).replace("{yyyymmdd}", compact)
           .replace("{page}", str(page)).replace("{offset}", str((page - 1) * 100)))
    headers = dict(src.get("request_headers") or {})
    body: bytes | None = None
    if sid == "edinet_v2":
        url += "&Subscription-Key=" + urllib.parse.quote(keys.get("EDINET_API_KEY", ""))
    elif sid == "dart_openapi":
        url += "&crtfc_key=" + urllib.parse.quote(keys.get("DART_API_KEY", ""))
    elif sid == "sec_edgar_8k":
        headers["User-Agent"] = keys.get("SEC_EDGAR_UA", "")
    elif sid == "jquants_free":
        headers["Authorization"] = "Bearer " + keys.get("_JQUANTS_ID_TOKEN", "")
        if unit:
            url += "&pagination_key=" + urllib.parse.quote(unit)
    elif sid == "cninfo":
        body = urllib.parse.urlencode({
            "pageNum": page, "pageSize": 30, "column": unit or "szse", "tabName": "fulltext",
            "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "", "trade": "",
            "seDate": f"{iso}~{iso}", "sortName": "", "sortType": "", "isHLtitle": "true"}).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    elif sid == "szse_annlist":
        body = json.dumps({"seDate": [iso, iso], "channelCode": ["listedNotice_disc"],
                           "pageSize": 50, "pageNum": page}).encode()
        headers["Content-Type"] = "application/json"
    return url, body, headers


def _jquants_id_token(http: Http, keys: dict[str, str]) -> str:
    """Refresh token -> ID token (J-Quants v1). The token is held in memory for the pass only."""
    rt = keys.get("JQUANTS_REFRESH_TOKEN", "")
    # A refresh token lives one week; the account's mail and password mint a fresh one each pass,
    # so a box holding those never goes BLOCKED on an expired token.
    if keys.get("JQUANTS_MAIL") and keys.get("JQUANTS_PASSWORD"):
        body = json.dumps({"mailaddress": keys["JQUANTS_MAIL"],
                           "password": keys["JQUANTS_PASSWORD"]}).encode()
        status, _ct, raw, _err = http("https://api.jquants.com/v1/token/auth_user", data=body,
                                      headers={"Content-Type": "application/json"})
        if status == 200:
            try:
                rt = str(_json_body(raw).get("refreshToken") or "") or rt
            except (ValueError, AttributeError):
                pass
    if not rt:
        return ""
    http.secrets.append(rt)
    url = "https://api.jquants.com/v1/token/auth_refresh?refreshtoken=" + urllib.parse.quote(rt)
    status, _ct, body, _err = http(url, data=b"")
    if status != 200:
        return ""
    try:
        return str(_json_body(body).get("idToken") or "")
    except (ValueError, AttributeError):
        return ""


# ============================================================================ the pass
def _blocked(src: Mapping[str, Any], keys: Mapping[str, str]) -> str:
    missing = [k for k in (src.get("key_names") or []) if not keys.get(k)]
    if not missing:
        return ""
    return (f"{BLOCKED_NO_KEY}: {', '.join(missing)} absent from {SECRETS.relative_to(ROOT)} and "
            f"the environment; register at {src.get('registration_url') or '(see row)'}")


def event_row(src: Mapping[str, Any], raw: Mapping[str, Any], res: Resolver,
              fixture: bool = False) -> dict[str, Any] | None:
    cc = str(src["country"])
    if not raw.get("at"):
        return None
    cat, d, sched = classify(cc, str(raw.get("title") or ""), raw.get("items") or ())
    mapped = res.resolve(cc, str(raw.get("code") or ""), str(raw.get("name") or ""))
    row = {"id": f"{src['id']}:{raw.get('native_id') or hashlib.sha1(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:16]}",
           "source": src["id"], "country": cc, "language": src.get("language"),
           "issuer_code": str(raw.get("code") or ""), "issuer_name": str(raw.get("name") or "")[:80],
           "title": str(raw.get("title") or "")[:160], "category": cat, "direction": d,
           "scheduled": sched, "at": raw["at"], "at_precision": raw.get("precision"),
           "url": str(raw.get("url") or "")[:240], **mapped,
           "fetched_at": _now().isoformat(timespec="seconds")}
    if raw.get("surprise") is not None:
        row["surprise"] = round(float(raw["surprise"]), 6)
    if fixture:
        row["fixture"] = True
    return row


def _keep_full(row: Mapping[str, Any]) -> bool:
    return bool(row.get("symbols") or row.get("peers")) or row.get("category") in NOTABLE


def _count_rows(src: Mapping[str, Any], day: date, rows: list[dict[str, Any]],
                transmits: list[str]) -> list[dict[str, Any]]:
    """One per-(day, category, direction) COUNT row for everything not kept in full."""
    groups: Counter[tuple[str, int, bool]] = Counter()
    for r in rows:
        if not _keep_full(r):
            groups[(str(r["category"]), int(r["direction"]), bool(r["scheduled"]))] += 1
    out: list[dict[str, Any]] = []
    at = _end_of_day(str(src["country"]), day.strftime("%Y%m%d"))
    for (cat, d, sched), n in sorted(groups.items()):
        out.append({"id": f"{src['id']}:count:{day.isoformat()}:{cat}:{d}", "source": src["id"],
                    "country": src["country"], "kind": "count", "n": n, "category": cat,
                    "direction": d, "scheduled": sched, "at": at, "at_precision": "day",
                    "symbols": [], "peers": [], "transmits": transmits})
    return out


def _append(path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return len(rows)


def run_source(src: Mapping[str, Any], *, cursor: dict[str, Any], keys: dict[str, str],
               res: Resolver, http: Http | None, fixtures: Path | None, deadline: float,
               today: date | None = None) -> dict[str, Any]:
    """One source, one pass: the live days re-fetched, then the backfill walked backwards.

    A DAY IS FINAL ONLY WHEN EVERY PAGE OF IT WAS READ AND THE DAY IS OVER. Its counts are then
    written once and never again; a live day's full rows are deduplicated by id so the fast lane
    sees each headline once.
    """
    sid = str(src["id"])
    cc = str(src["country"])
    rec: dict[str, Any] = {"id": sid, "country": cc, "auth": src["auth"], "requests": 0,
                           "rows_seen": 0, "rows_kept": 0, "count_rows": 0, "mapped_rows": 0,
                           "days_finalised": 0, "errors": []}
    why = "" if fixtures else _blocked(src, keys)
    if why:
        rec.update({"status": BLOCKED_NO_KEY, "why": why, "yield": UNMEASURED})
        return rec
    cur = cursor.setdefault(sid, {})
    done: set[str] = set(cur.get("done_dates") or [])
    recent: dict[str, list[str]] = {k: list(v) for k, v in (cur.get("recent_ids") or {}).items()}
    today = today or _local_date(cc)
    lag = int(src.get("lag_days") or 0)
    live = [today - timedelta(days=lag + i) for i in range(LIVE_DAYS)]
    back = [today - timedelta(days=lag + i)
            for i in range(LIVE_DAYS, LIVE_DAYS + int(src.get("backfill_days") or 0))]
    plan = live + [d for d in back if d.isoformat() not in done]
    transmits = res.targets.get(cc, [])
    units = [str(u) for u in (src.get("columns") or [""])]
    store = EVENTS / f"{sid}.jsonl"
    parser = PARSERS[sid]
    for day in plan:
        if time.monotonic() > deadline or rec["requests"] >= MAX_REQUESTS_PER_SOURCE:
            rec["deferred_from"] = day.isoformat()
            break
        day_rows: list[dict[str, Any]] = []
        complete = True
        for unit in units:
            page, token = 1, unit
            while True:
                if time.monotonic() > deadline or rec["requests"] >= MAX_REQUESTS_PER_SOURCE:
                    complete = False
                    break
                try:
                    if fixtures is not None:
                        doc = _read(fixtures / f"{sid}.json")
                        if doc is None:
                            raise ValueError(f"no fixture {sid}.json")
                    else:
                        assert http is not None
                        url, body, hdr = request_for(src, day, page, keys, token)
                        status, _ctype, raw, err = http(url, data=body, headers=hdr)
                        if status != 200:
                            raise ValueError(err or f"HTTP {status}")
                        _vault(sid, raw, redact(url, keys.values()))
                        doc = _json_body(raw)
                    rows, more = parser(doc, page)
                except Exception as exc:                          # noqa: BLE001
                    rec["errors"].append(redact(f"{day}: {type(exc).__name__}: {exc}"[:200],
                                                keys.values()))
                    complete = False
                    rows, more = [], False
                rec["requests"] += 1
                for raw_row in rows:
                    ev = event_row(src, raw_row, res, fixture=fixtures is not None)
                    if ev is not None:
                        day_rows.append(ev)
                if fixtures is not None or not more:
                    break
                page += 1
                if sid == "jquants_free":
                    token = str((doc or {}).get("pagination_key") or "") if isinstance(doc, dict) \
                        else ""
            if not complete:
                break
        # One row per id: a source read by several columns (cninfo szse/sse) can list the same
        # announcement twice, and a duplicate would count twice in every burst.
        uniq: dict[str, dict[str, Any]] = {}
        for r in day_rows:
            uniq.setdefault(str(r["id"]), r)
        day_rows = list(uniq.values())
        rec["rows_seen"] += len(day_rows)
        key = day.isoformat()
        seen = set(recent.get(key) or [])
        full = [r for r in day_rows if _keep_full(r) and r["id"] not in seen]
        rec["rows_kept"] += _append(store, full)
        rec["mapped_rows"] += sum(1 for r in full if r.get("symbols") or r.get("peers"))
        recent[key] = sorted(seen | {r["id"] for r in full})
        is_live = day in live
        if complete and not is_live:
            rec["count_rows"] += _append(store, _count_rows(src, day, day_rows, transmits))
            done.add(key)
            rec["days_finalised"] += 1
            recent.pop(key, None)
        if fixtures is not None:
            break                                   # a fixture is one document, read once
    keep_after = (today - timedelta(days=lag + RECENT_ID_DAYS)).isoformat()
    cur["recent_ids"] = {k: v for k, v in recent.items() if k >= keep_after}
    cur["done_dates"] = sorted(done)[-1200:]
    cur["last_run"] = _now().isoformat(timespec="seconds")
    rec["status"] = "FETCHED" if rec["requests"] and not rec["errors"] else \
        ("PARTIAL" if rec["rows_seen"] else ("ERROR" if rec["errors"] else "IDLE"))
    rec["yield"] = rec["rows_seen"]
    return rec


# ============================================================================ series (b)
def _events(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


SIGNAL_CATS: tuple[str, ...] = ("earnings", "guidance_revision", "buyback", "mna",
                                "equity_issuance", "regulatory", "insider_trade", "contract")


def daily_frame(rows: Iterable[Mapping[str, Any]], country: str) -> dict[str, dict[str, float]]:
    """local day -> the day's signal columns. Full rows count 1, count rows count their n."""
    days: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    seen: set[str] = set()
    for r in rows:
        rid = str(r.get("id") or "")
        if rid in seen:
            continue
        seen.add(rid)
        try:
            at = datetime.fromisoformat(str(r.get("at")).replace("Z", "+00:00"))
        except ValueError:
            continue
        # A day-precision row is stamped at the END of its day; step back a second so it counts
        # on the day it was published, not the next one.
        day = (at + timedelta(hours=TZ_H.get(country, 0)) - timedelta(seconds=1)).date().isoformat()
        n = float(r.get("n") or 1)
        cat = str(r.get("category") or "other")
        d = int(r.get("direction") or 0)
        row = days[day]
        row["n_total"] += n
        if cat in SIGNAL_CATS:
            row[f"n_{cat}"] += n
        if not r.get("scheduled"):
            row["n_unscheduled"] += n
        row["net_direction"] += d * n
        if r.get("surprise") is not None:
            row["surprise_sum"] += float(r["surprise"])
            row["surprise_n"] += 1
    out: dict[str, dict[str, float]] = {}
    for day, row in days.items():
        o = dict(row)
        if o.get("surprise_n"):
            o["surprise_mean"] = o["surprise_sum"] / o["surprise_n"]
        o.pop("surprise_sum", None)
        out[day] = o
    return out


def write_series(series_id: str, frame: Mapping[str, Mapping[str, float]], country: str) -> int:
    """`data/lake/series/<id>.csv` plus its `.pit.json`, in the envelope pack_cells reads.

    `available_time` is the END of the local publication day -- a day's count is not knowable
    until the day is over -- and `exogenous_conditioner` lags it a further publication day.
    """
    if not frame:
        return 0
    cols = sorted({c for r in frame.values() for c in r})
    SERIES.mkdir(parents=True, exist_ok=True)
    lines = [",".join(["event_time", "available_time", "source_id", *cols])]
    for day in sorted(frame):
        avail = _end_of_day(country, day)
        lines.append(",".join([day, str(avail), series_id,
                               *(f"{float(frame[day].get(c, 0.0)):.6g}" for c in cols)]))
    path = SERIES / f"{series_id}.csv"
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
    _write_atomic(SERIES / f"{series_id}.pit.json", {
        "source_id": series_id, "n_rows": len(frame), "writer": "research/corporate_disclosure.py",
        "frames": [{"status": "STAMPED", "path": path.name,
                    "why": "available_time = end of the local publication day, UTC"}],
        "generated_at": _now().isoformat(timespec="seconds")})
    return len(frame)


def build_series() -> dict[str, int]:
    """Per source and per country. Returns series id -> rows."""
    out: dict[str, int] = {}
    by_country: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for src in SOURCES:
        rows = list(_events(EVENTS / f"{src['id']}.jsonl"))
        if not rows:
            continue
        cc = str(src["country"])
        out[src["id"]] = write_series(src["id"], daily_frame(rows, cc), cc)
        by_country[cc].extend(rows)
    for cc, rows in by_country.items():
        sid = f"{SOURCE}_{cc}"
        out[sid] = write_series(sid, daily_frame(rows, cc), cc)
    return out


# ============================================================================ state (c)
def _z(values: list[float]) -> float | None:
    if len(values) < 10:
        return None
    hist, last = values[:-1], values[-1]
    mu = sum(hist) / len(hist)
    sd = (sum((v - mu) ** 2 for v in hist) / len(hist)) ** 0.5
    return None if sd <= 0 else (last - mu) / sd


def build_state(res: Resolver) -> dict[str, Any]:
    """Per instrument: the disclosure-flow regime today. ADVISORY STATE, never a size."""
    inst: dict[str, dict[str, Any]] = {}
    for cc in COUNTRY_CCY:
        path = SERIES / f"{SOURCE}_{cc}.csv"
        if not path.exists():
            continue
        try:
            import pandas as pd
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        flow = [float(x) for x in df.get("n_total", pd.Series(dtype=float)).fillna(0)]
        net = [float(x) for x in df.get("net_direction", pd.Series(dtype=float)).fillna(0)]
        zf, zn = _z(flow[-250:]), _z(net[-250:])
        row = {"country": cc, "as_of_day": str(df["event_time"].iloc[-1]),
               "available_time": str(df["available_time"].iloc[-1]),
               "flow_z": None if zf is None else round(zf, 3),
               "revision_balance_z": None if zn is None else round(zn, 3),
               "burst": bool(zf is not None and zf >= 2.0),
               "regime": (UNMEASURED if zf is None else
                          "burst" if zf >= 2.0 else "quiet" if zf <= -1.0 else "normal")}
        for sym in res.targets.get(cc, []):
            inst[sym] = dict(row)
    doc = {"generated_at": _now().isoformat(timespec="seconds"), "writer": SOURCE,
           "rule": ("advisory state: the disclosure flow per mapped instrument. Nothing here sizes, "
                    "caps or vetoes; an instrument absent from this map is UNMEASURED, not quiet"),
           "instruments": inst}
    _write_atomic(STATE, doc)
    return doc


# ============================================================================ donations (a, b)
def _event_days(spec: str, symbol: str) -> int:
    try:
        from mt5desk.disclosure_events import load_events
    except Exception:
        return 0
    return len(load_events(spec, symbol, root=EVENTS))


def enumerate_specs(res: Resolver, frames: Mapping[str, int]) -> list[dict[str, Any]]:
    """Every hypothesis the stream now has the history to support, as compiler EXACT_RECIPE rows."""
    from mt5desk.disclosure_events import make_spec
    from mt5desk.family_exogenous_gate import gateable
    rows: list[dict[str, Any]] = []
    stats: dict[tuple[str, str, str, int], set[str]] = defaultdict(set)
    for src in SOURCES:
        for r in _events(EVENTS / f"{src['id']}.jsonl"):
            for scope in ("symbols", "peers", "transmits"):
                for sym in r.get(scope) or []:
                    d = int(r.get("direction") or 0)
                    for dirn in {"any", ("up" if d > 0 else "down" if d < 0 else "any")}:
                        stats[(str(r.get("country")), scope, str(sym),
                               ("up", "down", "any").index(dirn))].add(
                            f"{r.get('category')}|{str(r.get('at'))[:10]}")
    scope_name = {"symbols": "self", "peers": "peers", "transmits": "transmits"}
    for (cc, scope, sym, di), keys in sorted(stats.items()):
        dirn = ("up", "down", "any")[di]
        by_cat: dict[str, set[str]] = defaultdict(set)
        for k in keys:
            cat, day = k.split("|", 1)
            by_cat[cat].add(day)
        for cat, days in sorted(by_cat.items()):
            if cat in ("other", "correction", "personnel") or len(days) < MIN_EVENT_DAYS:
                continue
            fam = "event_reaction" if cat in SCHEDULED else "news_reaction"
            min_count = 1 if scope != "transmits" else _burst_threshold(cc, cat)
            spec = make_spec(cc, scope_name[scope], cat, dirn, min_count)
            side = -1 if dirn == "down" else 1
            for mode in ("drift", "fade"):
                rows.append({"kind": "hypothesis", "family": fam, "symbols": [sym], "country": cc,
                             "params": {"event_stream": spec, "symbol": sym, "mode": mode,
                                        "side": side},
                             "uses": "direct", "spec_key": f"{fam}|{sym}|{spec}|{mode}",
                             "mechanism": (f"{cc.upper()} primary disclosures of class {cat} "
                                           f"({scope_name[scope]} of {sym}, direction {dirn}): the "
                                           f"{'scheduled release' if fam == 'event_reaction' else 'unscheduled headline'} "
                                           f"reprices {sym} and the {mode} is the claim; the "
                                           f"stream is read in the issuer's own language")})
    for sid, n in sorted(frames.items()):
        if n < MIN_SERIES_ROWS or not sid.startswith(f"{SOURCE}_"):
            continue
        cc = sid.rsplit("_", 1)[-1]
        for sym in res.targets.get(cc, []):
            for sig in ("n_total", "n_unscheduled", "net_direction", "n_guidance_revision",
                        "surprise_mean"):
                rows.append({"kind": "hypothesis", "family": "exogenous_conditioner",
                             "symbols": [sym], "uses": "indirect", "country": cc,
                             "params": {"source": sid, "signal": sig, "transform": "level_z"},
                             "spec_key": f"exogenous_conditioner|{sym}|{sid}|{sig}",
                             "mechanism": (f"the {cc.upper()} disclosure-flow statistic {sig} at "
                                           f"an extreme conditions {sym}")})
                for base in GATE_BASES:
                    if not gateable(base):
                        continue
                    for band in GATE_BANDS:
                        rows.append({"kind": "hypothesis", "family": "exogenous_gate",
                                     "symbols": [sym], "uses": "indirect", "country": cc,
                                     "params": {"base_family": base, "base_params": {},
                                                "source": sid, "signal": sig,
                                                "transform": "level_z", "band": band},
                                     "spec_key": f"exogenous_gate|{sym}|{sid}|{sig}|{base}|{band}",
                                     "mechanism": (f"{base} on {sym} taken only while the "
                                                   f"{cc.upper()} disclosure flow {sig} is "
                                                   f"{band}: the same price mechanism under a "
                                                   f"different information regime")})
    return rows


def culture_of(country: str) -> dict[str, str]:
    """The three culture fields for a donated row; UNMEASURED when the country is unknown."""
    return dict(CULTURE.get(country.lower(), {"source_culture": UNMEASURED,
                                              "participant_structure": UNMEASURED,
                                              "failure_mode_hypothesis": UNMEASURED}))


_BURST: dict[tuple[str, str], int] = {}


def _burst_threshold(country: str, category: str) -> int:
    """The class's own 75th-percentile daily count, so a 'burst' is measured, not declared."""
    return max(1, _BURST.get((country, category), 1))


def _learn_bursts() -> None:
    _BURST.clear()
    per: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for src in SOURCES:
        cc = str(src["country"])
        for r in _events(EVENTS / f"{src['id']}.jsonl"):
            per[(cc, str(r.get("category")))][str(r.get("at"))[:10]] += int(r.get("n") or 1)
    for key, days in per.items():
        vals = sorted(days.values())
        if vals:
            _BURST[key] = int(vals[int(0.75 * (len(vals) - 1))])


def donate(rows: list[dict[str, Any]], cursor: dict[str, Any], *, dry_run: bool = False
           ) -> dict[str, Any]:
    """The next DONATE_PER_PASS not-yet-donated specs, one file, the seat the compiler reads."""
    done = set(cursor.get("donated") or [])
    fresh = [r for r in rows if hashlib.sha1(r["spec_key"].encode()).hexdigest()[:16] not in done]
    take = fresh[:DONATE_PER_PASS]
    out = {"specs_total": len(rows), "specs_new": len(fresh), "donated_this_pass": len(take),
           "carried_to_next_pass": max(0, len(fresh) - len(take)),
           "by_use": dict(Counter(str(r.get("uses")) for r in take)),
           "by_family": dict(Counter(str(r.get("family")) for r in take))}
    if dry_run or not take:
        return out
    stamp = _now().strftime("%Y%m%d_%H%M%S")
    for r in take:
        r.update({"source": SOURCE, "generator": f"{SOURCE}:{r['uses']}",
                  "found_at": _now().isoformat(timespec="seconds")})
        r.update(culture_of(str(r.get("country") or "")))
    _write_atomic(SEAT / f"hypotheses_{stamp}.json", {"discoveries": take, "writer": SOURCE})
    done |= {hashlib.sha1(r["spec_key"].encode()).hexdigest()[:16] for r in take}
    cursor["donated"] = sorted(done)
    out["path"] = str((SEAT / f"hypotheses_{stamp}.json").relative_to(ROOT))
    return out


# ============================================================================ grounds rows
def source_rows(res: Resolver | None = None) -> list[dict[str, Any]]:
    """The registry rows, with transmission targets filled from the broker's registry."""
    out: list[dict[str, Any]] = []
    for src in SOURCES:
        row = {k: v for k, v in src.items() if k not in ("url",)}
        row["url"] = src["url"]
        row["collector"] = SOURCE
        row["expect"] = "json"
        row["cursor"] = {"kind": "date+page", "path": str(CURSOR.relative_to(ROOT)),
                         "live_days": LIVE_DAYS, "backfill_days": src.get("backfill_days", 0)}
        row["uses"] = USES
        row["licence_note"] = LICENCE_NOTE
        if src.get("key_names"):
            row["key_env"] = src["key_names"][0]
        if res is not None:
            row["targets"] = res.targets.get(str(src["country"]), [])
        row["mechanism"] = ("a listed company's own primary disclosure, dated at publication and "
                            "read in its native language, is information the tape has not yet "
                            "absorbed at that moment")
        out.append(row)
    return out


def upsert_grounds(rows: list[dict[str, Any]], *, dry_run: bool = False) -> dict[str, Any]:
    """Add or refresh OUR rows in the existing grounds file; never touch anyone else's row."""
    doc = _read(GROUNDS, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("sources"), list):
        return {"status": UNMEASURED, "why": f"{GROUNDS.name} unreadable; nothing written"}
    ours = {r["id"]: r for r in rows}
    changed = 0
    kept: list[Any] = []
    for r in doc["sources"]:
        if isinstance(r, dict) and r.get("id") in ours:
            new = {**r, **ours.pop(r["id"])}
            changed += int(new != r)
            kept.append(new)
        else:
            kept.append(r)
    added = list(ours.values())
    kept.extend(added)
    if (changed or added) and not dry_run:
        doc["sources"] = kept
        _write_atomic(GROUNDS, doc)
    roster = "absent (libs/mining/sources.yaml not on this tree); rows are roster-shaped"
    if ROSTER.exists():
        roster = "present: register these rows there (roster format owned by libs/mining)"
    return {"status": "OK", "added": len(added), "refreshed": changed, "roster": roster}


# ============================================================================ main
def run(*, budget_s: float = 600.0, fixtures: Path | None = None, dry_run: bool = False,
        only: Iterable[str] = ()) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(10.0, budget_s * 0.75)
    reg = registry()
    res = Resolver(reg)
    keys = read_keys()
    http = None if fixtures is not None else Http(keys.values())
    if fixtures is None and http is not None and (
            keys.get("JQUANTS_REFRESH_TOKEN") or keys.get("JQUANTS_MAIL")):
        tok = _jquants_id_token(http, keys)
        if tok:
            keys["_JQUANTS_ID_TOKEN"] = tok
            http.secrets.append(tok)
    cursor = _read(CURSOR, {}) or {}
    per_source: list[dict[str, Any]] = []
    want = set(only)
    if keys.get("_JQUANTS_ID_TOKEN"):
        keys.setdefault("JQUANTS_REFRESH_TOKEN", "(minted from the account this pass)")
    for src in SOURCES:
        if want and src["id"] not in want:
            continue
        if dry_run:
            why = _blocked(src, keys)
            per_source.append({"id": src["id"], "status": BLOCKED_NO_KEY if why else "DUE",
                               "why": why, "yield": UNMEASURED})
            continue
        per_source.append(run_source(src, cursor=cursor.setdefault("sources", {}), keys=keys,
                                     res=res, http=http, fixtures=fixtures, deadline=deadline))
    frames = {} if dry_run else build_series()
    state = {} if dry_run else build_state(res)
    _learn_bursts()
    specs = enumerate_specs(res, frames)
    donation = donate(specs, cursor, dry_run=dry_run)
    grounds = upsert_grounds(source_rows(res), dry_run=dry_run)
    if not dry_run:
        _write_atomic(CURSOR, cursor)
    report = {
        "generated_at": _now().isoformat(timespec="seconds"), "organ": SOURCE,
        "mode": "fixtures" if fixtures is not None else ("dry_run" if dry_run else "live"),
        "registry_symbols": len(reg),
        "transmission_targets": res.targets,
        "issuer_resolution": {("/".join(i["short"])): res._registry_symbol(i["short"], i["names"])
                              or UNMEASURED for i in ISSUERS},
        "sources": per_source,
        "yield_by_source": {r["id"]: r.get("yield", UNMEASURED) for r in per_source},
        "keys": key_status(keys),
        "series": frames,
        "state_instruments": len((state or {}).get("instruments") or {}),
        "donation": donation, "grounds": grounds, "uses": USES,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rule": ("fetch, classify, map, stamp, donate. Nothing sizes or judges; a keyed source "
                 "with no key is BLOCKED_NO_KEY and its yield UNMEASURED, never zero"),
    }
    if not dry_run:
        _write_atomic(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixtures", type=Path, default=None,
                    help="read <source>.json documents from this directory instead of the network")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--keys", action="store_true", help="PRESENT/ABSENT per key; never a value")
    args = ap.parse_args(argv)
    if args.keys:
        print(json.dumps(key_status(), indent=1))
        return 0
    rep = run(budget_s=args.budget_s, fixtures=args.fixtures, dry_run=args.dry_run,
              only=args.source)
    for r in rep["sources"]:
        print(f"  {r['id']:16} {r.get('status')!s:15} yield={r.get('yield')!s:>6} "
              f"req={r.get('requests', 0)} kept={r.get('rows_kept', 0)} "
              f"mapped={r.get('mapped_rows', 0)} {str(r.get('why') or '')[:70]}")
    d = rep["donation"]
    print(f"corporate_disclosure: {d['donated_this_pass']} donated of {d['specs_new']} new specs; "
          f"series {len(rep['series'])}; state {rep['state_instruments']} instrument(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
