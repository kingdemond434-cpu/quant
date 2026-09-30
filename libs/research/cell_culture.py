"""CULTURE PROVENANCE ON EVERY CELL -- the schema, the validator and the one inference rule.

    "the payoff of cross-culture mining is not a bigger candidate count: it is a lower crowding
     prior plus DIFFERENT FAILURE MODES"                          -- the principal, 2026-09-30

WHY FOUR FIELDS AND NOT A REGION. `libs/research/attribution.py` already says WHO produced a
cell and from WHICH region. That answers "did Korea produce anything"; it does not answer the
question the orthogonality test needs, which is "why would the Korean version of this mechanism
lose money on different days from the American one". That needs the participant structure on the
other side of the trade (retail tax-year selling, T+1 settlement, a policy fixing, physical gold
buying in Dubai or Mumbai, one broker's swap table) and a stated failure-mode hypothesis the
Tier S orthogonality thread can then TEST against live return streams. If the Korean and US
versions fail together, the cultural mining was coverage theater; if they fail apart, the
compounding argument holds. Neither answer is available unless the fields exist at birth.

THE SCHEMA (final, 2026-09-30 14:35, aligned with the Asia thread; common.txt):

    source_culture          "<jurisdiction>/<language>" -- "KR/ko", "JP/ja", "CN/zh", "US/en",
                            "AE/ar" -- or "GLOBAL", or UNMEASURED
    participant_structure   retail_heavy | institutional | tax_driven | policy_driven |
                            physical_flow | broker_specific | settlement_constrained | mixed |
                            UNMEASURED
    failure_mode_hypothesis one sentence: why this culture's version should fail at different
                            times from the standard Western version; UNMEASURED when either of the
                            two fields above is
    crowding_prior          low | medium | high | UNMEASURED -- how much English-language
                            literature covers the mechanism

plus `culture_derivation`, a mapping field -> "declared" | "inferred:<rule>" | "UNMEASURED", so
every value can be checked and a reader can separate what the SOURCE said from what the symbol
merely suggests (`inferred:symbol_home` is the weakest rule and is always named).

UNMEASURED IS NEVER GUESSED (L1.28a). `infer()` fires only named rules on evidence the row
already carries -- a declared field, a ground id, a URL's country-code TLD, the script of the
claim text, the declared ground registries, the symbol's single home market, the family. A row
none of them reaches is UNMEASURED on that field, which is a verdict, not a zero.

JOINS. Tier S reads the fields by cell id and by certificate through
`desks/mt5/reports/CELL_CULTURE_INDEX.jsonl` (written by `research/cell_culture_index.py`, one
row per cell id, with `certificate` / `identity` keys on certificate rows) and by the registry
columns `libs/moat/registry.py` stamps at the two doors.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"
GLOBAL = "GLOBAL"

SOURCE_CULTURE = "source_culture"
PARTICIPANT_STRUCTURE = "participant_structure"
FAILURE_MODE = "failure_mode_hypothesis"
CROWDING_PRIOR = "crowding_prior"
#: The four fields every cell and donation row carries, in the order they are documented.
FIELDS: tuple[str, ...] = (SOURCE_CULTURE, PARTICIPANT_STRUCTURE, FAILURE_MODE, CROWDING_PRIOR)
#: How each field was reached. A mapping on rows, a JSON string in a registry column.
DERIVATION_FIELD = "culture_derivation"
DECLARED = "declared"

PARTICIPANT_STRUCTURES: tuple[str, ...] = (
    "retail_heavy", "institutional", "tax_driven", "policy_driven", "physical_flow",
    "broker_specific", "settlement_constrained", "mixed", UNMEASURED)
CROWDING_PRIORS: tuple[str, ...] = ("low", "medium", "high", UNMEASURED)

#: Jurisdictions whose finance literature is the crowded Western canon. `EA` is the euro area.
WESTERN: frozenset[str] = frozenset({
    "US", "CA", "GB", "EA", "EU", "DE", "FR", "IT", "ES", "NL", "BE", "AT", "IE", "PT", "FI",
    "CH", "SE", "NO", "DK", "IS", "LU", "AU", "NZ"})

#: The language a jurisdiction's own public writing is in, for a culture reached WITHOUT a
#: language (a pack code, a symbol's home market). `mul` is ISO 639's "multiple languages" --
#: the honest code for the euro area and Switzerland rather than a guessed one.
PRIMARY_LANGUAGE: dict[str, str] = {
    "US": "en", "GB": "en", "CA": "en", "AU": "en", "NZ": "en", "IE": "en", "SG": "en",
    "IN": "hi", "PK": "ur", "BD": "bn", "LK": "si", "NG": "en", "KE": "en", "ZA": "en",
    "GH": "en", "PH": "en", "JP": "ja", "KR": "ko", "CN": "zh", "TW": "zh", "HK": "zh",
    "MO": "zh", "RU": "ru", "UA": "uk", "BY": "ru", "KZ": "ru", "AE": "ar", "SA": "ar",
    "EG": "ar", "QA": "ar", "KW": "ar", "MA": "ar", "TR": "tr", "IL": "he", "BR": "pt",
    "PT": "pt", "MX": "es", "AR": "es", "CL": "es", "CO": "es", "PE": "es", "ES": "es",
    "DE": "de", "AT": "de", "FR": "fr", "IT": "it", "NL": "nl", "BE": "nl", "SE": "sv",
    "NO": "no", "DK": "da", "FI": "fi", "PL": "pl", "CZ": "cs", "HU": "hu", "RO": "ro",
    "TH": "th", "VN": "vi", "ID": "id", "MY": "ms", "EA": "mul", "EU": "mul", "CH": "mul",
    "MENA": "ar",
}

CULTURE_RE = re.compile(r"^[A-Z]{2,4}/[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")


def culture_tag(jurisdiction: object, language: object = None) -> str | None:
    """`KR` (+ `ko`) -> "KR/ko". None when the jurisdiction is not a code this module knows."""
    j = str(jurisdiction or "").strip().upper()
    if j in ("GLOBAL", "INSTITUTIONAL"):
        return GLOBAL
    if j == "UK":
        j = "GB"
    if not re.fullmatch(r"[A-Z]{2,4}", j):
        return None
    lang = str(language or "").strip()
    if lang:
        head, _, tail = lang.partition("-")
        lang = head.lower() + (f"-{tail}" if tail else "")
    lang = lang or PRIMARY_LANGUAGE.get(j, "")
    if not lang:
        return None
    tag = f"{j}/{lang}"
    return tag if CULTURE_RE.match(tag) else None


def jurisdiction_of(culture: object) -> str | None:
    """"KR/ko" -> "KR"; GLOBAL and UNMEASURED -> None."""
    c = str(culture or "")
    return c.split("/", 1)[0] if CULTURE_RE.match(c) else None


def language_of(culture: object) -> str | None:
    c = str(culture or "")
    return c.split("/", 1)[1].split("-", 1)[0] if CULTURE_RE.match(c) else None


def is_western(culture: object) -> bool | None:
    """True / False for a measured jurisdiction, None for GLOBAL or UNMEASURED."""
    j = jurisdiction_of(culture)
    return None if j is None else j in WESTERN


# ---------------------------------------------------------------------------------- validation
def validate(row: Mapping[str, Any]) -> list[str]:
    """Every way `row` breaks the schema, as sentences. An empty list is a valid row.

    A row that carries none of the four fields is invalid: absence must be written as UNMEASURED,
    never left for a reader to interpret (L1.28a).
    """
    problems: list[str] = []
    for f in FIELDS:
        if f not in row:
            problems.append(f"{f} is absent; write UNMEASURED when it is unknown")
    c = row.get(SOURCE_CULTURE)
    if c is not None and c not in (GLOBAL, UNMEASURED) and not CULTURE_RE.match(str(c)):
        problems.append(f"source_culture {c!r} is not '<jurisdiction>/<language>', GLOBAL or "
                        "UNMEASURED")
    p = row.get(PARTICIPANT_STRUCTURE)
    if p is not None and p not in PARTICIPANT_STRUCTURES:
        problems.append(f"participant_structure {p!r} is not one of {PARTICIPANT_STRUCTURES}")
    h = row.get(FAILURE_MODE)
    if h is not None:
        hs = str(h).strip()
        if not hs:
            problems.append("failure_mode_hypothesis is empty; write UNMEASURED")
        elif hs != UNMEASURED and (len(hs) > 480 or hs.count(". ") > 1):
            problems.append("failure_mode_hypothesis must be ONE sentence")
    k = row.get(CROWDING_PRIOR)
    if k is not None and k not in CROWDING_PRIORS:
        problems.append(f"crowding_prior {k!r} is not one of {CROWDING_PRIORS}")
    d = row.get(DERIVATION_FIELD)
    if d is not None:
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except ValueError:
                problems.append("culture_derivation is not JSON")
                d = {}
        if not isinstance(d, Mapping):
            problems.append("culture_derivation must map field -> declared | inferred:<rule>")
        else:
            for f, how in d.items():
                if f not in FIELDS:
                    problems.append(f"culture_derivation names unknown field {f!r}")
                elif not (how in (DECLARED, UNMEASURED) or str(how).startswith("inferred:")):
                    problems.append(f"culture_derivation[{f}] {how!r} is not declared, "
                                    "UNMEASURED or inferred:<rule>")
    return problems


# ------------------------------------------------------------------------------ declared ground
_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
DEEP_FOREST = _DESK / "data" / "deep_forest_sources.json"
ASIA_SOURCES = _DESK / "data" / "asia_sources.json"
COUNTRY_PACKS = _DESK / "research" / "countries"
UNIVERSE = _DESK / "data" / "universe" / "universe.json"
#: The published summary, read for the English-coverage set that decides `crowding_prior: low`.
SUMMARY = _DESK / "reports" / "CELL_CULTURE.json"

#: Multi-country pack directories and the jurisdiction their grounds mostly stand in. A pack
#: named for a sea or a basin is NOT a country and is resolved per ground by its URL instead.
_PACK_ALIASES: dict[str, str] = {"ind": "IN", "idn": "ID", "uk": "GB", "gulf": "AE"}
#: Deep-forest region keys that are not jurisdictions.
_NON_JURISDICTION_REGIONS = frozenset({"institutional", "global"})


@lru_cache(maxsize=1)
def _forest() -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]],
                       dict[str, str]]:
    """(ground name -> (jurisdiction, language), host -> (jurisdiction, language),
    region key -> primary language). Built once from `deep_forest_sources.json`."""
    by_name: dict[str, tuple[str, str]] = {}
    by_host: dict[str, tuple[str, str]] = {}
    region_lang: dict[str, str] = {}
    try:
        doc = json.loads(DEEP_FOREST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return by_name, by_host, region_lang
    for key, reg in (doc.get("regions") or {}).items():
        langs = [str(x) for x in (reg.get("languages") or []) if x]
        non_en = [x for x in langs if x != "en"]
        if langs:
            region_lang[str(key).lower()] = (non_en or langs)[0]
    for g in doc.get("grounds") or []:
        if not isinstance(g, dict):
            continue
        reg = str(g.get("region") or "").lower()
        if not reg or reg in _NON_JURISDICTION_REGIONS:
            continue
        lang = str(g.get("language") or region_lang.get(reg) or "")
        pair = (reg.upper(), lang)
        name = str(g.get("name") or "").strip().lower()
        if name:
            by_name.setdefault(name, pair)
        for url in [g.get("url"), *(g.get("alt") or [])]:
            host = _host(url)
            if host:
                by_host.setdefault(host, pair)
    return by_name, by_host, region_lang


@lru_cache(maxsize=1)
def _asia() -> dict[str, str]:
    """asia_sources.json id -> jurisdiction."""
    out: dict[str, str] = {}
    try:
        doc = json.loads(ASIA_SOURCES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    rows = doc.get("sources") if isinstance(doc, dict) else doc
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("id") and r.get("country"):
            out[str(r["id"]).lower()] = str(r["country"]).upper()
    return out


@lru_cache(maxsize=1)
def _pack_codes() -> frozenset[str]:
    try:
        return frozenset(p.name.lower() for p in COUNTRY_PACKS.iterdir()
                         if p.is_dir() and not p.name.startswith("_"))
    except OSError:
        return frozenset()


@lru_cache(maxsize=1)
def _universe_classes() -> dict[str, str]:
    """symbol (upper) -> MetaTrader's own asset class."""
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k).upper(): str((v or {}).get("asset_class") or "")
            for k, v in doc.items() if isinstance(v, dict)}


def _host(url: object) -> str:
    raw = str(url or "").strip().lower()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    host = raw.split("/", 1)[0].split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


# ------------------------------------------------------------------------------- symbol homes
#: Currency -> the jurisdiction that issues it.
CURRENCY_HOME: dict[str, str] = {
    "USD": "US", "EUR": "EA", "GBP": "GB", "JPY": "JP", "CHF": "CH", "AUD": "AU", "NZD": "NZ",
    "CAD": "CA", "CNH": "CN", "CNY": "CN", "HKD": "HK", "SGD": "SG", "KRW": "KR", "INR": "IN",
    "IDR": "ID", "THB": "TH", "TRY": "TR", "ZAR": "ZA", "MXN": "MX", "BRL": "BR", "RUB": "RU",
    "PLN": "PL", "HUF": "HU", "CZK": "CZ", "ILS": "IL", "NOK": "NO", "SEK": "SE", "DKK": "DK",
    "TWD": "TW", "PHP": "PH", "MYR": "MY", "AED": "AE", "SAR": "SA", "CLP": "CL", "COP": "CO",
}
#: Indices, bonds and the few share CFDs whose home is not the US.
SYMBOL_HOME: dict[str, str] = {
    "JPN225": "JP", "JP225": "JP", "HK50": "HK", "CHINAH": "HK", "CHINA50": "CN", "CN50": "CN",
    "US500": "US", "US30": "US", "NAS100": "US", "US2000": "US", "USDX": "US", "UK100": "GB",
    "GER40": "DE", "FRA40": "FR", "E35": "ES", "EUSTX50": "EA", "NETH25": "NL", "AUS200": "AU",
    "CA60": "CA", "UST05Y": "US", "UST10Y": "US", "UKGILT": "GB", "KOSPI200": "KR",
    "KS200": "KR", "IND50": "IN", "NIFTY50": "IN", "SA40": "ZA", "SPI200": "AU",
    "ALIBABAGROUP": "CN", "BAIDU": "CN", "NIO": "CN", "JD": "CN", "PDD": "CN",
    "SHOPIFY": "CA",
}
_METALS = ("XAU", "XAG", "XPT", "XPD")


def symbol_home(symbol: object) -> str | None:
    """The ONE jurisdiction an instrument's price is made in, else None.

    Global instruments (metals, energy, softs, crypto CFDs) have no single home and return None:
    their culture comes from the source or not at all. For an FX pair the non-Western leg wins,
    because that is the leg whose local participants can make the pair behave differently; with
    two Western legs the non-USD leg, then the base.
    """
    s = str(symbol or "").strip().upper().replace("/", "").replace(".", "")
    if not s:
        return None
    if s in SYMBOL_HOME:
        return SYMBOL_HOME[s]
    klass = _universe_classes().get(s, "").lower()
    if len(s) == 6 and s[:3] in CURRENCY_HOME and s[3:] in CURRENCY_HOME and not s.startswith(
            _METALS):
        a, b = CURRENCY_HOME[s[:3]], CURRENCY_HOME[s[3:]]
        non_w = [x for x in (a, b) if x not in WESTERN]
        if non_w:
            return non_w[0]
        if a == "US":
            return b
        return a
    if klass == "equities":
        return "US"
    return None


# ------------------------------------------------------------------------------------ scripts
_SCRIPT_RULES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    # (rule name, pattern, jurisdiction, language) -- Kana before Han: Japanese uses both.
    ("script_kana", re.compile(r"[぀-ヿ]"), "JP", "ja"),
    ("script_hangul", re.compile(r"[ᄀ-ᇿ㄰-㆏가-힣]"), "KR", "ko"),
    ("script_han", re.compile(r"[㐀-䶿一-鿿]"), "CN", "zh"),
    ("script_cyrillic", re.compile(r"[Ѐ-ӿ]"), "RU", "ru"),
    ("script_arabic", re.compile(r"[؀-ۿݐ-ݿ]"), "MENA", "ar"),
    ("script_devanagari", re.compile(r"[ऀ-ॿ]"), "IN", "hi"),
    ("script_thai", re.compile(r"[฀-๿]"), "TH", "th"),
    ("script_hebrew", re.compile(r"[֐-׿]"), "IL", "he"),
)
#: Five or more distinct English function words in a SOURCE-authored field (a title, a verbatim
#: claim) is English. Desk-authored prose (`mechanism_note`, `why`) is English by construction
#: and is never read for this, or every row on the desk would read "English source".
_EN_WORDS = re.compile(r"\b(the|and|of|to|in|is|for|on|with|when|that|this|trading|price)\b",
                       re.IGNORECASE)
#: Fields a SOURCE wrote, as opposed to fields the desk wrote about it.
SOURCE_TEXT_FIELDS: tuple[str, ...] = ("claim", "title", "source_title", "text", "quote")
#: Every free-text field a row may carry; read for non-Latin script only.
TEXT_FIELDS: tuple[str, ...] = (*SOURCE_TEXT_FIELDS, "description", "mechanism",
                                "mechanism_note", "why", "parent", "causal_rationale", "note")


def _text(row: Mapping[str, Any], fields: Iterable[str], cap: int = 1500) -> str:
    parts: list[str] = []
    for f in fields:
        v = row.get(f)
        if isinstance(v, str) and v:
            parts.append(v[:cap])
    return " ".join(parts)


#: Every script above in one class: the common case (Latin text) is ONE search, not eight.
_ANY_SCRIPT = re.compile("[" + "".join(p.pattern[1:-1] for _r, p, _j, _l in _SCRIPT_RULES)
                         + "]")


def script_culture(text: str) -> tuple[str, str, str] | None:
    """(jurisdiction, language, rule) from the script of `text`, or None for Latin/empty."""
    if not text or not _ANY_SCRIPT.search(text):
        return None
    for rule, pat, j, lang in _SCRIPT_RULES:
        if pat.search(text):
            return j, lang, rule
    return None


def is_english(text: str) -> bool:
    return len({m.lower() for m in _EN_WORDS.findall(text or "")}) >= 5


# --------------------------------------------------------------------------- participant rules
#: Families whose participant structure is part of the mechanism's own definition.
FAMILY_STRUCTURE: dict[str, str] = {
    "retail_overlap_reversal": "retail_heavy", "cot_positioning": "institutional",
    "cot_comm_follow": "institutional", "cot_change_momentum": "institutional",
    "fx_fixing_reversal": "institutional", "hedging_demand_close": "institutional",
    "london_close_momentum": "institutional", "forced_flow": "institutional",
    "comex_settlement": "settlement_constrained", "gotobi": "settlement_constrained",
    "spread_state": "broker_specific", "execution_state": "broker_specific",
    "sge_premium": "physical_flow", "cb_tone": "policy_driven",
}
_STRUCTURE_TERMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("physical_flow", re.compile(
        r"(shanghai gold|\bsge\b|dgcx|\bmcx\b|dubai gold|mumbai|physical (gold|demand|flow)|"
        r"gold premium|jewell?ery|dhanteras|akshaya|diwali|wedding season|上海黄金|金价溢价|"
        r"沪金|金溢价|실물 금|ذهب)", re.IGNORECASE)),
    ("settlement_constrained", re.compile(
        r"(\bt\+[012]\b|settlement (date|day|cycle|constraint)|price limit|limit[- ]up|"
        r"limit[- ]down|gotobi|五十日|涨停|跌停|涨跌停|value date|상한가|하한가)", re.IGNORECASE)),
    ("tax_driven", re.compile(
        r"(tax[- ]loss|tax year|tax-year|fiscal year[- ]end|\bnisa\b|\bisa allowance|"
        r"税制|節税|年末調整|税金|양도세|세금|налог)", re.IGNORECASE)),
    ("policy_driven", re.compile(
        r"(central bank|intervention|\bpboc\b|\bboj\b|\bcbrt\b|\brbi\b|\bsnb\b|\bcbr\b|"
        r"daily fix(ing)?|midpoint fix|currency peg|capital control|央行|中间价|日銀|介入|"
        r"한국은행|외환당국|центробанк|банк россии|\bцб\b|البنك المركزي)",  # noqa: RUF001
        re.IGNORECASE)),
    ("retail_heavy", re.compile(
        r"(\bretail\b|mrs\.? watanabe|散户|个人投资者|個人投資家|ミセス・ワタナベ|fx個人|개미|"
        r"개인투자자|розничн|частн\w+ инвестор|crowd sentiment|retail positioning)",
        re.IGNORECASE)),
    ("broker_specific", re.compile(
        r"(\bbroker\b|swap (rate|table|points)|rollover|triple swap|spread widening|"
        r"quote feed|last look)", re.IGNORECASE)),
    ("institutional", re.compile(
        r"(pension|\bgpif\b|insurer|real money|index rebalanc|fund rebalanc|\bcta\b|"
        r"asset manager|sovereign fund|month[- ]end rebalanc)", re.IGNORECASE)),
)
#: The seven vocabularies as ONE alternation of named groups: a single pass over the text.
_STRUCTURE_ANY = re.compile("|".join(f"(?P<{st}>{pat.pattern})" for st, pat in _STRUCTURE_TERMS),
                            re.IGNORECASE)
#: Source / producer tokens whose participant structure is the source's own nature.
_SOURCE_STRUCTURE: tuple[tuple[str, str], ...] = (
    ("broker_swaps", "broker_specific"), ("fusion_spread", "broker_specific"),
    ("fund_playbook", "institutional"), ("miner:cot", "institutional"),
    ("fetch_sge_premium", "physical_flow"), ("sge_premium", "physical_flow"),
    ("reddit", "retail_heavy"), ("forexfactory", "retail_heavy"), ("youtube", "retail_heavy"),
    ("mql5", "retail_heavy"), ("central_bank", "policy_driven"), ("cb_tone", "policy_driven"),
)
#: Seats (data/intelligence/<seat>/) whose participants are the seat's own nature: retail
#: track-record and copy-trading platforms, positioning reports, policy speech corpora.
_SEAT_STRUCTURE: dict[str, str] = {
    **dict.fromkeys(("followme_cn", "myfxbook_outlook", "mql5", "mql5_signals", "mql5_survivors",
                     "fxblue", "share4you", "darwinex", "collective2", "duplitrade", "litefinance",
                     "forexpeacearmy", "forexfactory", "tradingview", "tradingview_scripts",
                     "reddit", "youtube", "mylivefx_br", "minfx_jp", "readitrades_africa",
                     "trading_latam", "propfirm_boards", "fbs_tape", "aaii", "fear_greed"),
                    "retail_heavy"),
    **dict.fromkeys(("cot", "sec_edgar", "fund_playbook"), "institutional"),
    **dict.fromkeys(("central_banks", "bis_speeches", "central_bank"), "policy_driven"),
    **dict.fromkeys(("broker_swaps", "amarkets", "equiti_copy_rules"), "broker_specific"),
}
#: Deep-forest ground kinds: practitioner venues are retail; papers and disclosures institutional.
_KIND_STRUCTURE: dict[str, str] = {
    "forum": "retail_heavy", "social": "retail_heavy", "community": "retail_heavy",
    "video": "retail_heavy", "blog": "retail_heavy", "column": "retail_heavy",
    "qa": "retail_heavy", "competition": "retail_heavy", "interview": "retail_heavy",
    "fund_disclosure": "institutional", "benchmark_flows": "institutional",
    "broker_execution_rules": "broker_specific", "exchange_rulebook": "settlement_constrained",
}
#: Hosts of official policy makers: a ground on one of these is policy-driven evidence.
_POLICY_HOSTS = re.compile(
    r"(\.gov(\.[a-z]{2})?$|\.gob\.|\.go\.(jp|kr|id|th)$|boj\.or\.jp|pbc\.gov\.cn|cbr\.ru|"
    r"rbi\.org\.in|tcmb\.gov\.tr|bcb\.gov\.br|bok\.or\.kr|centralbank|federalreserve|"
    r"ecb\.europa|snb\.ch|safe\.gov\.cn)")
_GOLD_PHYSICAL_HOMES = frozenset({"AE", "CN", "IN", "HK", "SG", "TR", "SA", "MENA"})

#: Standard textbook families: in English they are the most-written-about rules there are.
TEXTBOOK_FAMILIES: frozenset[str] = frozenset({
    "trend_ma_cross", "mean_reversion_rsi", "mean_reversion_bollinger", "engulfing_reversal",
    "pin_bar_reversal", "macd_cross", "opening_range", "turn_of_month", "dow_effect"})

#: Local holidays and calendar institutions -> the jurisdiction whose calendar they are.
_HOLIDAYS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(golden[_ ]week|obon|gotobi|五十日|ゴールデンウィーク)", re.I), "JP"),
    (re.compile(r"(chuseok|seollal|추석|설날)", re.I), "KR"),
    (re.compile(r"(lunar[_ ]new[_ ]year|chinese[_ ]new[_ ]year|spring[_ ]festival|春节|"
                r"国庆|golden_week_cn)", re.I), "CN"),
    (re.compile(r"(diwali|dhanteras|akshaya|muhurat)", re.I), "IN"),
    (re.compile(r"(ramadan|eid[_ ]al|رمضان)", re.I), "MENA"),
    (re.compile(r"(carnaval|carnival_br)", re.I), "BR"),
)
_CALENDAR_FAMILIES = frozenset({"calendar_month", "turn_of_month", "dow_effect", "monday_gap",
                                "session_handoff", "asia_momentum", "overnight_gap_decay",
                                "clock_transition", "lvc_asia_london", "opening_range",
                                "session_range_breakout", "holiday", "holiday_effect"})

_CULTURE_NAMES: dict[str, str] = {
    "JP": "Japanese", "KR": "Korean", "CN": "Chinese", "HK": "Hong Kong", "TW": "Taiwanese",
    "RU": "Russian", "IN": "Indian", "AE": "Emirati", "SA": "Saudi", "TR": "Turkish",
    "BR": "Brazilian", "MX": "Mexican", "ZA": "South African", "US": "US", "GB": "UK",
    "EA": "euro-area", "DE": "German", "FR": "French", "AU": "Australian", "CA": "Canadian",
    "CH": "Swiss", "SG": "Singaporean", "ID": "Indonesian", "TH": "Thai", "IL": "Israeli",
    "MENA": "Gulf and Arab", "PL": "Polish", "HU": "Hungarian", "CZ": "Czech", "NO": "Norwegian",
    "SE": "Swedish", "NZ": "New Zealand", "VN": "Vietnamese", "MY": "Malaysian",
}

#: One sentence per participant structure. `{c}` is the culture's name. Each names a failure
#: trigger LOCAL to that structure, which is exactly what the Tier S orthogonality test checks.
FAILURE_TEMPLATES: dict[str, str] = {
    "retail_heavy": ("{c} retail flow sets this price, so it should fail when {c} households "
                     "de-lever or local leverage and sentiment turn, not when Western "
                     "institutional risk appetite does."),
    "tax_driven": ("The edge is anchored to the {c} tax calendar and rules, so it should fail "
                   "around {c} tax-rule changes and fiscal year-end rather than the US tax-loss "
                   "season."),
    "policy_driven": ("The edge rides the {c} policy reaction function (central bank, fixing, "
                      "capital controls), so it should fail on a {c} policy regime change, not "
                      "on a Fed-driven or Western liquidity shock."),
    "settlement_constrained": ("The edge exists because {c} settlement and trading limits "
                               "block arbitrage, so it should fail when those rules change, "
                               "independent of Western market stress."),
    "physical_flow": ("The edge follows {c} physical buying and import flow, so it should fail "
                      "when {c} physical demand, premiums or import policy shift, not when "
                      "Western paper positioning unwinds."),
    "broker_specific": ("The edge lives in {c} broker and venue mechanics, so it should fail "
                        "when that venue changes its swap, spread or quote terms, uncorrelated "
                        "with market-wide factor drawdowns."),
    "institutional": ("{c} institutional mandates and rebalancing calendars drive this, so it "
                      "should fail when those mandates change or the trade crowds, which for a "
                      "Western culture is the standard failure mode itself."),
    "mixed": ("Several {c} participant groups drive this at once, so it should fail only when "
              "their local drivers break together, which need not coincide with Western "
              "drawdowns."),
}


#: A GLOBAL (English-venue) cell is the crowded standard version itself: its failure mode is the
#: reference the other cultures are tested against, and the sentence says so instead of
#: inventing a local trigger it does not have.
GLOBAL_BASELINE = ("This is the global English-venue version of the mechanism, the crowded "
                   "baseline, so it should fail exactly when the standard Western version does "
                   "and is the reference the other cultures' versions are tested against.")


def failure_mode(culture: str, structure: str) -> str:
    """The template sentence for (culture, structure), or UNMEASURED when either is unknown."""
    if structure in (UNMEASURED, "") or structure not in FAILURE_TEMPLATES:
        return UNMEASURED
    if culture == GLOBAL:
        return GLOBAL_BASELINE
    else:
        j = jurisdiction_of(culture)
        if j is None:
            return UNMEASURED
        name = _CULTURE_NAMES.get(j, j)
    sentence = FAILURE_TEMPLATES[structure].format(c=name)
    return sentence[0].upper() + sentence[1:]


# ----------------------------------------------------------------------------- English coverage
@lru_cache(maxsize=1)
def _english_families_cached(mtime_ns: int) -> frozenset[str] | None:
    try:
        doc = json.loads(SUMMARY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    fams = doc.get("english_covered_families")
    return frozenset(str(f) for f in fams) if isinstance(fams, list) else None


def english_covered_families() -> frozenset[str] | None:
    """Families the registry already holds from an ENGLISH source (last published pass), or
    None when unmeasured -- in which case `crowding_prior` can never be `low` by inference."""
    try:
        m = SUMMARY.stat().st_mtime_ns
    except OSError:
        return None
    return _english_families_cached(m)


# ---------------------------------------------------------------------------------- inference
def _declared(row: Mapping[str, Any], field: str, valid: Iterable[str] | None = None) -> str | None:
    v = row.get(field)
    if v is None:
        return None
    s = str(v).strip()
    if not s or s == UNMEASURED:
        return None
    if field == SOURCE_CULTURE:
        if s == GLOBAL or CULTURE_RE.match(s):
            return s
        # the pre-schema plain form ("JP") is accepted and normalised, never dropped
        return culture_tag(s)
    if valid is not None and s not in valid:
        return None
    return s


def _ground_tokens(row: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    for v in (row.get("source"), row.get("source_id"), row.get("producer"), row.get("generator"),
              row.get("ground"), row.get("source_seat"),
              params.get("source") if params else None):
        if isinstance(v, str) and v.strip():
            out.append(v.strip().lower())
    return out


#: Country names a seat may be named by (`korea`, `china`, `japan_scout`). Only whole countries:
#: a bloc name (`europe`, `latam`, `mena`) names no jurisdiction and is never read as one.
_SEAT_COUNTRY: dict[str, str] = {
    "japan": "JP", "japanese": "JP", "korea": "KR", "korean": "KR", "china": "CN",
    "chinese": "CN", "taiwan": "TW", "hongkong": "HK", "russia": "RU", "russian": "RU",
    "india": "IN", "indian": "IN", "brazil": "BR", "mexico": "MX", "turkey": "TR",
    "vietnam": "VN", "thailand": "TH", "indonesia": "ID", "nigeria": "NG", "kenya": "KE",
    "southafrica": "ZA", "saudi": "SA", "uae": "AE", "dubai": "AE", "israel": "IL",
    "poland": "PL", "germany": "DE", "france": "FR", "australia": "AU", "canada": "CA",
}
_SEAT_NS = ("miner:", "seat:", "src:", "ground:", "intel:", "exe:")


def seat_names(row: Mapping[str, Any]) -> list[str]:
    """The seats a row names: its source/producer tokens with their filing namespace peeled,
    `intel:<seat>:<file>` source ids, `source_seat`, and `contributing_sources`."""
    raw = list(_ground_tokens(row))
    contrib = row.get("contributing_sources")
    if isinstance(contrib, (list, tuple)):
        raw += [str(x).strip().lower() for x in contrib if x]
    out: list[str] = []
    for tok in raw:
        base = tok
        changed = True
        while changed:
            changed = False
            for ns in _SEAT_NS:
                if base.startswith(ns):
                    base, changed = base[len(ns):], True
        seat = base.split(":", 1)[0].strip()
        if seat and seat not in out:
            out.append(seat)
        # `ext_<seat>_<SYMBOL>_<family>`: the external lane files the seat in position one
        if seat.startswith("ext_"):
            inner = seat[4:].split("_", 1)[0]
            if inner and inner not in out:
                out.append(inner)
    return out


#: GLOBAL ENGLISH-LANGUAGE VENUES. A claim from one of these is the crowded, standard version the
#: principal's cross-culture test compares against: its culture is GLOBAL (not a guess about the
#: poster's country) and its source language is English.
GLOBAL_VENUE_SEATS: frozenset[str] = frozenset({
    "forexfactory", "reddit", "youtube", "github", "github_topics", "tradingview",
    "tradingview_scripts", "mql5", "mql5_signals", "mql5_survivors", "mql5_catalog",
    "babypips", "quantconnect", "quant_se", "arxiv_qfin", "ssrn", "myfxbook_outlook",
    "investing", "seekingalpha", "collective2", "fxblue", "forexpeacearmy", "literature"})
GLOBAL_VENUE_HOSTS = re.compile(
    r"(^|\.)(youtube\.com|youtu\.be|reddit\.com|forexfactory\.com|github\.com|"
    r"tradingview\.com|mql5\.com|babypips\.com|quantconnect\.com|arxiv\.org|ssrn\.com|"
    r"myfxbook\.com|investing\.com|seekingalpha\.com|stackexchange\.com)$")


def seat_culture(seat: str) -> str | None:
    """A jurisdiction a SEAT's own name declares: `minfx_jp`, `followme_cn`, `mylivefx_br`
    (a country-code suffix naming a country pack) or `korea`, `china` (a country name)."""
    s = str(seat or "").lower()
    if not s:
        return None
    parts = [p for p in s.replace("-", "_").split("_") if p]
    if s in _SEAT_COUNTRY:
        return _SEAT_COUNTRY[s]
    if parts and parts[0] in _SEAT_COUNTRY:
        return _SEAT_COUNTRY[parts[0]]
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1] in _pack_codes():
        return parts[-1].upper()
    return None


def _culture_from_row(row: Mapping[str, Any], text: str | None = None
                      ) -> tuple[str | None, str, str | None]:
    """(culture, rule, source_language). The culture is None when no rule fires. The language
    is what the SOURCE is written in when that is measurable, for the crowding prior."""
    by_name, by_host, region_lang = _forest()
    lang_hint = str(row.get("language") or row.get("lang") or "").strip() or None
    # 1. A GROUND ID THAT DECLARES ITS COUNTRY IN POSITION: pack:<cc>:..., forest:<cc>:...
    packs = _pack_codes()
    for tok in _ground_tokens(row):
        for ns in ("pack:", "forest:", "miner:pack:", "ground:pack:"):
            if tok.startswith(ns):
                seg = tok[len(ns):].split(":", 1)[0]
                code = _PACK_ALIASES.get(seg, seg.upper() if len(seg) == 2 else "")
                if code and (seg in packs or len(seg) == 2):
                    tag = culture_tag(code, lang_hint or region_lang.get(seg))
                    if tag:
                        return tag, "inferred:ground_position", language_of(tag)
    # 2. A DECLARED COUNTRY OR REGION CODE ON THE ROW (pack_cells world rows, deep-forest tasks).
    for key in ("country", "region", "market"):
        v = str(row.get(key) or "").strip()
        if len(v) == 2 and v.isalpha() and (v.lower() in region_lang or v.lower() in packs):
            tag = culture_tag(v, lang_hint or region_lang.get(v.lower()))
            if tag:
                return tag, f"inferred:declared_{key}", language_of(tag)
    # 3. A DECLARED GROUND: deep_forest_sources.json by name, asia_sources.json by id.
    asia = _asia()
    for tok in _ground_tokens(row):
        base = tok
        for ns in ("miner:", "seat:", "src:", "ground:", "asia:"):
            if base.startswith(ns):
                base = base[len(ns):]
        if base.startswith("asia:"):
            base = base[5:]
        if base in asia:
            tag = culture_tag(asia[base], lang_hint)
            if tag:
                return tag, "inferred:asia_sources", None
        if tok in by_name:
            j, lang = by_name[tok]
            tag = culture_tag(j, lang_hint or lang)
            if tag:
                return tag, "inferred:deep_forest_ground", language_of(tag)
    g = str(row.get("ground") or "").strip().lower()
    if g in by_name:
        j, lang = by_name[g]
        tag = culture_tag(j, lang_hint or lang)
        if tag:
            return tag, "inferred:deep_forest_ground", language_of(tag)
    # 4. THE SOURCE URL: a declared deep-forest host, else a country-code TLD.
    for key in ("source_url", "url", "link"):
        host = _host(row.get(key))
        if not host:
            continue
        if host in by_host:
            j, lang = by_host[host]
            tag = culture_tag(j, lang_hint or lang)
            if tag:
                return tag, "inferred:deep_forest_host", language_of(tag)
        label = host.rsplit(".", 1)[-1] if "." in host else ""
        if len(label) == 2 and label.isalpha() and label not in ("io", "co", "ai", "me", "tv",
                                                                   "fm", "ly", "gg", "cc"):
            code = "GB" if label == "uk" else ("EA" if label == "eu" else label.upper())
            tag = culture_tag(code, lang_hint)
            if tag:
                return tag, "inferred:url_tld", None
    # 5. THE SCRIPT OF THE TEXT. Any non-Latin script anywhere on the row is source evidence:
    #    the desk writes English, so Hangul in a claim came from the source.
    sc = script_culture(_text(row, TEXT_FIELDS) if text is None else text)
    if sc is not None:
        j, lang, rule = sc
        tag = culture_tag(j, lang)
        if tag:
            return tag, f"inferred:{rule}", lang
    # 5b. A SEAT WHOSE OWN NAME IS A COUNTRY (`followme_cn`, `korea`): the seat mined that
    #     country's ground. Read after the URL and the script, which are the source speaking.
    for seat in seat_names(row):
        scode = seat_culture(seat)
        if scode:
            tag = culture_tag(scode, lang_hint)
            if tag:
                return tag, "inferred:seat_name", language_of(tag)
    # 5c. A GLOBAL ENGLISH VENUE (ForexFactory, Reddit, YouTube, GitHub, arXiv ...): GLOBAL, en.
    for key in ("source_url", "url", "link"):
        host = _host(row.get(key))
        if host and GLOBAL_VENUE_HOSTS.search(host):
            return GLOBAL, "inferred:global_english_venue", "en"
    for seat in seat_names(row):
        if seat in GLOBAL_VENUE_SEATS:
            return GLOBAL, "inferred:global_english_venue", "en"
    # 6. A LOCAL HOLIDAY named in the family or params of a calendar family.
    fam = str(row.get("family") or "").lower()
    if fam in _CALENDAR_FAMILIES or any(w in fam for w in ("holiday", "calendar", "season",
                                                           "festival", "gotobi")):
        params = row.get("params")
        hay = fam + " " + (json.dumps(params, default=str, ensure_ascii=False)
                           if isinstance(params, Mapping) else "")
        for pat, code in _HOLIDAYS:
            if pat.search(hay):
                tag = culture_tag(code)
                if tag:
                    return tag, "inferred:holiday_calendar", None
    # 7. A FUND'S OWN DOMICILE (fund_playbook:<fund>).
    for tok in _ground_tokens(row):
        if tok.startswith("fund_playbook:") or tok.startswith("miner:fund_playbook"):
            fund = tok.split(":", 2)[1] if tok.startswith("fund_playbook:") else ""
            home = _FUND_HOME.get(fund)
            if home:
                return culture_tag(home), "inferred:fund_domicile", "en"
    en = is_english(_text(row, SOURCE_TEXT_FIELDS))
    # 8. THE SYMBOL'S SINGLE HOME MARKET -- the weakest rule, always named as such.
    home = symbol_home(row.get("symbol"))
    if home:
        tag = culture_tag(home)
        if tag:
            return tag, "inferred:symbol_home", "en" if en else None
    return None, "", "en" if en else None


_FUND_HOME: dict[str, str] = {
    "aqr": "US", "bridgewater": "US", "renaissance": "US", "two sigma": "US", "citadel": "US",
    "cubist": "US", "de shaw": "US", "millennium": "US", "man ahl": "GB", "winton": "GB",
    "brevan howard": "GB", "capula": "GB", "gpif": "JP",
}


def _structure_from_row(row: Mapping[str, Any], culture: str | None,
                        text: str | None = None) -> tuple[str | None, str]:
    """(participant_structure, rule). None when no rule fires."""
    hits: dict[str, str] = {}
    fam = str(row.get("family") or "").lower()
    if fam in FAMILY_STRUCTURE:
        hits.setdefault(FAMILY_STRUCTURE[fam], "family")
    for tok in _ground_tokens(row):
        for needle, st in _SOURCE_STRUCTURE:
            if needle in tok:
                hits.setdefault(st, "source")
        if ":official:" in tok:
            hits.setdefault("policy_driven", "ground_layer_official")
    for seat in seat_names(row):
        seat_st = _SEAT_STRUCTURE.get(seat)
        if seat_st is None and any(w in seat for w in ("copy", "pamm", "masters", "signals")):
            seat_st = "retail_heavy"
        if seat_st:
            hits.setdefault(seat_st, "seat")
    kind = str(row.get("kind") or row.get("ground_kind") or "").lower()
    if kind in _KIND_STRUCTURE:
        hits.setdefault(_KIND_STRUCTURE[kind], "ground_kind")
    for key in ("source_url", "url"):
        host = _host(row.get(key))
        if host and _POLICY_HOSTS.search(host):
            hits.setdefault("policy_driven", "policy_host")
    text = _text(row, TEXT_FIELDS) if text is None else text
    if text:
        for m in _STRUCTURE_ANY.finditer(text):
            st = str(m.lastgroup)
            hits.setdefault(st, f"text_{st}")
    sym = str(row.get("symbol") or "").upper()
    j = jurisdiction_of(culture) if culture else None
    if sym.startswith(("XAU", "XAG")) and j in _GOLD_PHYSICAL_HOMES and (
            "physical_flow" not in hits):
        hits["physical_flow"] = "gold_physical_home"
    if not hits:
        return None, ""
    if len(hits) == 1:
        st, how = next(iter(hits.items()))
        return st, f"inferred:{how}"
    return "mixed", "inferred:mixed(" + "+".join(sorted(hits)) + ")"


def _crowding(row: Mapping[str, Any], culture: str | None, culture_rule: str,
              source_lang: str | None, english: frozenset[str] | None) -> tuple[str | None, str]:
    fam = str(row.get("family") or "").lower()
    source_based = bool(culture) and culture_rule not in ("", "inferred:symbol_home")
    lang = source_lang or (language_of(culture) if source_based else None)
    if lang == "en" and fam in TEXTBOOK_FAMILIES:
        return "high", "inferred:textbook_family_in_english"
    if lang and lang != "en" and source_based and english is not None and fam and (
            fam not in english):
        return "low", "inferred:non_english_no_english_equivalent"
    return None, ""


def infer(cell_or_row: Mapping[str, Any], *,
          english_families: frozenset[str] | bool | None = True) -> dict[str, Any]:
    """The four culture fields and how each was derived (see `infer_with_language`)."""
    return infer_with_language(cell_or_row, english_families=english_families)[0]


def infer_with_language(cell_or_row: Mapping[str, Any], *,
                        english_families: frozenset[str] | bool | None = True
                        ) -> tuple[dict[str, Any], str | None]:
    """The four culture fields and how each was derived, from what the row already carries.

    Declared values win and are marked `declared`; every other value names the rule that fired;
    a field no rule reaches is UNMEASURED. `english_families` is the set of families the registry
    holds from an English source (True: read the last published summary; None: unmeasured, so
    `crowding_prior: low` cannot be inferred).
    """
    row = cell_or_row if isinstance(cell_or_row, Mapping) else {}
    if english_families is True:
        english = english_covered_families()
    elif english_families is False or english_families is None:
        english = None
    else:
        english = frozenset(english_families)
    how: dict[str, str] = {}
    culture = _declared(row, SOURCE_CULTURE)
    source_lang: str | None = None
    rule = DECLARED if culture else ""
    text = _text(row, TEXT_FIELDS)
    if culture:
        how[SOURCE_CULTURE] = DECLARED
        source_lang = language_of(culture)
    else:
        culture, rule, source_lang = _culture_from_row(row, text)
        how[SOURCE_CULTURE] = rule if culture else UNMEASURED
    structure = _declared(row, PARTICIPANT_STRUCTURE, PARTICIPANT_STRUCTURES)
    if structure:
        how[PARTICIPANT_STRUCTURE] = DECLARED
    else:
        structure, srule = _structure_from_row(row, culture, text)
        how[PARTICIPANT_STRUCTURE] = srule if structure else UNMEASURED
    hyp = _declared(row, FAILURE_MODE)
    if hyp:
        how[FAILURE_MODE] = DECLARED
    else:
        hyp = failure_mode(culture or UNMEASURED, structure or UNMEASURED)
        how[FAILURE_MODE] = (f"inferred:template:{structure}" if hyp != UNMEASURED
                             else UNMEASURED)
    crowd = _declared(row, CROWDING_PRIOR, CROWDING_PRIORS)
    if crowd:
        how[CROWDING_PRIOR] = DECLARED
    else:
        crowd, crule = _crowding(row, culture, rule, source_lang, english)
        how[CROWDING_PRIOR] = crule if crowd else UNMEASURED
    # A value CARRIED from an earlier hop keeps the rule that first reached it: a cell the
    # discovery compiler emits from a seat donation says `inferred:seat_name`, not `declared`.
    prior = row.get(DERIVATION_FIELD)
    if isinstance(prior, str):
        try:
            prior = json.loads(prior)
        except ValueError:
            prior = None
    if isinstance(prior, Mapping):
        for f in FIELDS:
            was = str(prior.get(f) or "")
            if how.get(f) == DECLARED and was.startswith("inferred:"):
                how[f] = was
    return ({SOURCE_CULTURE: culture or UNMEASURED,
             PARTICIPANT_STRUCTURE: structure or UNMEASURED,
             FAILURE_MODE: hyp or UNMEASURED,
             CROWDING_PRIOR: crowd or UNMEASURED,
             DERIVATION_FIELD: how}, source_lang)


def stamp(row: Mapping[str, Any], **declared: Any) -> dict[str, Any]:
    """`infer()` over the row with `declared` values laid on top -- the call a producer makes
    when it KNOWS some of the answer (a pack knows its country) and wants the rest inferred."""
    merged = {**row, **{k: v for k, v in declared.items() if v not in (None, "")}}
    return infer(merged)


def carry(row: dict[str, Any], source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Write the four fields (and their derivation) onto `row` in place and return it.

    Values `row` already declares are kept; everything else is inferred from `source` (the
    evidence row the cell was compiled from) merged under `row`. Never raises: a malformed row
    is stamped UNMEASURED, because a producer must never lose a cell to its provenance.
    """
    try:
        basis = {**(source or {}), **row}
        fields = infer(basis)
    except Exception:  # provenance can never cost a cell
        fields = dict.fromkeys(FIELDS, UNMEASURED)
        fields[DERIVATION_FIELD] = dict.fromkeys(FIELDS, UNMEASURED)
    for f in (*FIELDS, DERIVATION_FIELD):
        row[f] = fields[f]
    return row


def normalise(row: Mapping[str, Any]) -> dict[str, Any]:
    """A LEGACY or partial culture stamp brought up to the final schema, nothing re-guessed.

    Producers that emitted the plain keys before this module landed (`specialist_cell.culture`,
    `residual_search.CULTURE`) wrote a bare jurisdiction ("US") and no crowding prior. A bare code
    becomes "<code>/<primary language>" ("US" -> "US/en"); an unknown code, a malformed structure
    or crowding value, and every absent field become UNMEASURED. The derivation says `declared`
    for a value that survived and UNMEASURED for one that did not.
    """
    out: dict[str, Any] = {}
    how: dict[str, str] = {}
    culture = _declared(row, SOURCE_CULTURE)
    structure = _declared(row, PARTICIPANT_STRUCTURE, PARTICIPANT_STRUCTURES)
    hyp = _declared(row, FAILURE_MODE)
    crowd = _declared(row, CROWDING_PRIOR, CROWDING_PRIORS)
    for f, v in ((SOURCE_CULTURE, culture), (PARTICIPANT_STRUCTURE, structure),
                 (FAILURE_MODE, hyp), (CROWDING_PRIOR, crowd)):
        out[f] = v or UNMEASURED
        how[f] = DECLARED if v else UNMEASURED
    prior = row.get(DERIVATION_FIELD)
    if isinstance(prior, Mapping):
        for f in FIELDS:
            if out[f] != UNMEASURED and str(prior.get(f) or "").startswith("inferred:"):
                how[f] = str(prior[f])
    out[DERIVATION_FIELD] = how
    return out


def is_source_derived(derivation: Mapping[str, Any] | str | None) -> bool:
    """True when source_culture came from the source itself rather than the symbol's home."""
    d = derivation
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except ValueError:
            return False
    if not isinstance(d, Mapping):
        return False
    how = str(d.get(SOURCE_CULTURE) or "")
    return how == DECLARED or (how.startswith("inferred:") and how != "inferred:symbol_home")
