"""THE MACRO ACQUISITION LANE -- languages, institutions, datasets, the PIT stamp, four scouts.

WHY THE VOCABULARY COMES FIRST. A search in English over a German central bank finds the press
release a translator wrote a day later, and the desk reads the translation believing it read the
record. The institution says it first in its own language, in its own terms -- `Mindestkurs`,
`仲値`, `逆周期因子`, `adjudication` -- and a query built from English stems cannot reach any of
them. So this module opens with a terminology dictionary in eight languages across six topics
(policy, rates, intervention, positioning, fixings, auctions), and every query the scouts emit is
built from it rather than from a translated phrase.

WHY THE CATALOGUE IS A STRUCTURE AND NOT A LIST OF URLS. "We have FRED" is not a capability. The
questions that decide whether a series can carry a hypothesis are: what does it cover, how often
does it publish, HOW LATE, does it revise, under what licence, how far back, and can a vintage be
reconstructed. A dataset that revises and publishes no vintage cannot be used point-in-time, and
using it anyway is a lookahead that flatters every backtest it touches. So each row is a
`DatasetSpec` with those fields plus the assets and mechanism families it can serve and the
literal way to fetch it, and a row with a blank field fails the mandate's validator.

THE PIT STAMP IS ONE FUNCTION AND IT IS DELIBERATELY STRICT. `pit_stamp(row)` returns
NOT_PIT_SAFE for any observation that does not carry a publication time -- not a warning, not a
default of "probably fine". The desk has a measured history of current-vintage series being read
as history (the FRED fetcher says so in its own docstring), and the only defence that survives a
tired session is a stamp that says NO by default.

FOUR SCOUTS, EACH WIDENING A DIFFERENT PART OF THE GRAPH. The data scout registers the
institutions that publish series and says which the box can actually reach. The academic scout
registers the research estate. The native web scout registers the institutions' own
native-language publication indexes and steers the deep-forest miner at the regions it supports
(reading the miner's own region index rather than a hard-coded list) and `world_frontier` at
everything else. The code scout registers public implementations. All four write SOURCES with the
language stamped and EXPANSION EDGES into the registry's provenance DAG, so a source discovered
by a scout is distinguishable from one the desk declared for itself -- which is the only way to
answer whether the forest is still growing.

WHAT NO SCOUT DOES HERE. None of them fetches. Fetching is the crawler's job, on the crawler's
budget, through the desk's one HTTP client; a scout that fetched would be a second crawler with
no politeness budget and no raw store. The scouts publish WHERE to look and IN WHICH WORDS, and
the retrieval itself is reported UNMEASURED until the crawler has been.

NO KEY IS EVER PRINTED. The FRED key lives in `data/secrets/fred.json` on both boxes. This module
names the path and never opens it; `how_to_fetch` says "key from data/secrets/fred.json" and that
string is the whole of the desk's relationship with it here.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REGION = "macro"
TAG = f"{REGION}:"
DESK = Path(__file__).resolve().parents[2]
ROOT = DESK.parents[1]
#: The one place the FRED key lives. Named, never opened, never printed.
FRED_KEY_PATH = "data/secrets/fred.json"
#: The deep-forest miner's own region index. Read, never duplicated.
DEEP_FOREST_SOURCES = DESK / "data" / "deep_forest_sources.json"

PIT_SAFE = "PIT_SAFE"
NOT_PIT_SAFE = "NOT_PIT_SAFE"
UNMEASURED = "UNMEASURED"

LANGUAGES: tuple[str, ...] = ("en", "de", "fr", "it", "es", "pt", "ja", "zh")
TOPICS: tuple[str, ...] = ("policy", "rates", "intervention", "positioning", "fixings",
                           "auctions")


# --------------------------------------------------------------------------- the framework shim
def _framework() -> Any:
    try:
        return importlib.import_module("libs.research.region_mandate")
    except ImportError:
        return None


@dataclass(frozen=True)
class DatasetSpec:
    """One public dataset, and everything that decides whether it may be used point-in-time."""

    dataset_id: str
    institution: str
    coverage: str
    frequency: str
    publication_lag: str
    revisions: str
    licence: str
    history: str
    pit_feasible: str
    assets: tuple[str, ...]
    mechanism_families: tuple[str, ...]
    how_to_fetch: str
    language: str = "en"
    url: str = ""


def _spec(**fields: Any) -> Any:
    """A catalogue row through the framework's dataclass when it has one, else the local shape."""
    fw = _framework()
    cls = getattr(fw, "DatasetSpec", None) if fw is not None else None
    if cls is not None:
        try:
            return cls(**fields)
        except TypeError:
            pass
    return DatasetSpec(**fields)


# =============================================================================================
# The terminology. Native script where the language has one -- a romanised stem finds nothing.
# =============================================================================================
TERMS: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "policy": ("policy rate", "interest rate decision", "monetary policy statement",
                   "forward guidance", "minutes", "staff projections", "quantitative tightening"),
        "rates": ("yield curve", "term premium", "real yield", "breakeven inflation",
                  "10-year yield", "swap spread", "curve steepening"),
        "intervention": ("foreign exchange intervention", "verbal intervention",
                         "currency floor", "exchange rate band", "smoothing operations"),
        "positioning": ("commitments of traders", "net long", "speculative positioning",
                        "open interest", "crowded trade", "non-commercial"),
        "fixings": ("WMR fix", "4pm London fix", "reference rate", "benchmark fixing",
                    "month-end rebalancing"),
        "auctions": ("treasury auction", "bid-to-cover", "quarterly refunding",
                     "issuance calendar", "syndication", "tap"),
    },
    "de": {
        "policy": ("Leitzins", "Zinsentscheid", "Geldpolitik", "geldpolitische Straffung",
                   "Protokoll", "Projektionen", "Forward Guidance"),
        "rates": ("Renditekurve", "Umlaufrendite", "Realzins", "Bundesanleihe",
                  "Laufzeitprämie", "Inflationserwartung"),
        "intervention": ("Devisenmarktinterventionen", "Mindestkurs", "verbale Intervention",
                         "Wechselkursuntergrenze"),
        "positioning": ("Positionierung", "Netto-Long", "offene Kontrakte",
                        "spekulative Positionen"),
        "fixings": ("Referenzkurs", "EZB-Referenzkurs", "Fixing", "Monatsultimo"),
        "auctions": ("Bundesanleihe-Auktion", "Emissionskalender", "Zuteilung",
                     "Aufstockung", "Bietungsverhältnis"),
    },
    "fr": {
        "policy": ("taux directeur", "décision de taux", "politique monétaire",
                   "compte rendu", "projections macroéconomiques", "orientation prospective"),
        "rates": ("courbe des taux", "OAT", "taux réel", "prime de terme",
                  "point mort d'inflation"),
        "intervention": ("intervention de change", "taux plancher", "intervention verbale"),
        "positioning": ("positionnement", "positions nettes", "intérêt ouvert",
                        "positions spéculatives"),
        "fixings": ("cours de référence", "fixing", "rééquilibrage de fin de mois"),
        "auctions": ("adjudication", "calendrier d'émission", "AFT", "taux de couverture"),
    },
    "it": {
        "policy": ("tasso di riferimento", "decisione sui tassi", "politica monetaria",
                   "verbali", "proiezioni macroeconomiche"),
        "rates": ("curva dei rendimenti", "BTP", "spread", "tasso reale", "premio a termine"),
        "intervention": ("intervento sul cambio", "cambio minimo", "intervento verbale"),
        "positioning": ("posizionamento", "posizioni nette", "open interest",
                        "posizioni speculative"),
        "fixings": ("cambio di riferimento", "fixing", "ribilanciamento di fine mese"),
        "auctions": ("asta BTP", "calendario delle aste", "rapporto di copertura",
                     "collocamento"),
    },
    "es": {
        "policy": ("tipo de interés oficial", "decisión de tipos", "política monetaria",
                   "actas", "proyecciones macroeconómicas"),
        "rates": ("curva de tipos", "bono a 10 años", "tipo real", "prima de plazo",
                  "expectativa de inflación"),
        "intervention": ("intervención cambiaria", "tipo de cambio mínimo",
                         "intervención verbal"),
        "positioning": ("posicionamiento", "posiciones netas", "interés abierto",
                        "posiciones especulativas"),
        "fixings": ("tipo de cambio de referencia", "fixing", "reajuste de fin de mes"),
        "auctions": ("subasta del Tesoro", "calendario de emisiones", "ratio de cobertura",
                     "sindicación"),
    },
    "pt": {
        "policy": ("taxa básica de juros", "decisão de juros", "política monetária",
                   "ata do Copom", "relatório de inflação", "Selic"),
        "rates": ("curva de juros", "NTN-B", "juro real", "prêmio de prazo",
                  "expectativa de inflação"),
        "intervention": ("intervenção cambial", "leilão de swap cambial",
                         "intervenção verbal"),
        "positioning": ("posicionamento", "posições líquidas", "contratos em aberto",
                        "posições especulativas"),
        "fixings": ("taxa de referência", "PTAX", "fixing", "reequilíbrio de fim de mês"),
        "auctions": ("leilão do Tesouro", "calendário de leilões", "razão de cobertura"),
    },
    "ja": {
        "policy": ("政策金利", "金融政策決定会合", "金融政策", "議事要旨", "展望レポート",
                   "イールドカーブ・コントロール"),
        "rates": ("長期金利", "国債利回り", "イールドカーブ", "実質金利", "期間プレミアム"),
        "intervention": ("為替介入", "円買い介入", "口先介入", "覆面介入", "財務省 介入実績"),
        "positioning": ("建玉", "投機筋", "ネットロング", "持ち高", "取組高"),
        "fixings": ("仲値", "東京仲値", "五十日", "TTM", "月末リバランス"),
        "auctions": ("国債入札", "応札倍率", "発行計画", "流動性供給入札"),
    },
    "zh": {
        "policy": ("政策利率", "货币政策", "利率决议", "会议纪要", "中期借贷便利", "逆回购"),
        "rates": ("收益率曲线", "国债收益率", "实际利率", "期限溢价", "通胀预期"),
        "intervention": ("外汇干预", "汇率中间价", "逆周期因子", "跨境资本流动管理"),
        "positioning": ("持仓", "净多头", "投机头寸", "持仓量", "多空比"),
        "fixings": ("中间价", "定盘价", "人民币中间价", "月末调仓"),
        "auctions": ("国债招标", "认购倍数", "发行计划", "续发行"),
    },
}

#: Which language each domain is most likely to be said in first. Used to order the scouts'
#: queries, never to exclude a language: an institution may publish in any of them.
DOMAIN_LANGUAGES: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("en", "de", "ja", "zh", "fr", "it", "es", "pt"),
    "macro_release_surprise": ("en", "de", "fr", "it", "es", "pt", "ja", "zh"),
    "positioning": ("en", "ja", "zh"),
    "rates_complexes": ("en", "de", "fr", "it", "ja"),
    "fiscal_auction_calendars": ("en", "de", "fr", "it", "es", "ja"),
    "intervention_states": ("ja", "zh", "de", "en"),
    "cross_asset_propagation": ("en", "zh", "ja"),
    "fixing_flows": ("en", "ja", "zh", "de"),
    "commodity_fundamentals": ("en", "pt", "es", "zh"),
    "risk_regimes": ("en", "zh", "ja"),
    "calendar_mismatches": ("en", "ja", "zh"),
    "native_language_intelligence": LANGUAGES,
    "dataset_catalogue": ("en",),
    "research_and_code_provenance": ("en", "zh", "ja", "de"),
    "conversion_and_transformation": ("en",),
}

#: The topics each domain searches in. A domain with no topic would emit no query at all, which
#: is a silent omission; every domain names at least one.
DOMAIN_TOPICS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("policy", "rates"),
    "macro_release_surprise": ("policy", "rates"),
    "positioning": ("positioning",),
    "rates_complexes": ("rates", "policy"),
    "fiscal_auction_calendars": ("auctions", "rates"),
    "intervention_states": ("intervention", "fixings"),
    "cross_asset_propagation": ("rates", "positioning"),
    "fixing_flows": ("fixings", "positioning"),
    "commodity_fundamentals": ("positioning", "auctions"),
    "risk_regimes": ("rates", "positioning"),
    "calendar_mismatches": ("fixings", "auctions"),
    "native_language_intelligence": TOPICS,
    "dataset_catalogue": ("policy", "rates", "positioning"),
    "research_and_code_provenance": ("policy", "rates", "positioning", "intervention"),
    "conversion_and_transformation": ("positioning",),
}


# =============================================================================================
# The institutions. Public roots only, each with the language it publishes in.
# =============================================================================================
def _src(source_id: str, institution: str, url: str, language: str, country: str, kind: str,
         licence: str, assets: tuple[str, ...]) -> dict[str, Any]:
    return {"source_id": source_id, "institution": institution, "url": url,
            "language": language, "country": country, "kind": kind, "licence": licence,
            "asset_classes": assets}


_FX = ("forex",)
_FXRATES = ("forex", "bonds")
_ALL = ("forex", "bonds", "indices", "metals", "energy", "softs")

SOURCE_CLASSES: dict[str, tuple[dict[str, Any], ...]] = {
    "central_bank": (
        _src("macro:cb:fed", "Federal Reserve Board", "https://www.federalreserve.gov/",
             "en", "US", "central_bank", "public domain (US government work)", _ALL),
        _src("macro:cb:fed_fomc", "FOMC calendars and statements",
             "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "en", "US",
             "central_bank", "public domain (US government work)", _ALL),
        _src("macro:cb:ecb", "European Central Bank",
             "https://www.ecb.europa.eu/press/pr/date/html/index.en.html", "en", "EA",
             "central_bank", "ECB terms: reuse with attribution", _ALL),
        _src("macro:cb:bundesbank", "Deutsche Bundesbank",
             "https://www.bundesbank.de/de/presse/pressenotizen", "de", "DE", "central_bank",
             "Bundesbank terms: reuse with attribution", _FXRATES),
        _src("macro:cb:bdf", "Banque de France",
             "https://www.banque-france.fr/fr/publications-et-statistiques", "fr", "FR",
             "central_bank", "Banque de France terms: reuse with attribution", _FXRATES),
        _src("macro:cb:bancaditalia", "Banca d'Italia",
             "https://www.bancaditalia.it/pubblicazioni/", "it", "IT", "central_bank",
             "Banca d'Italia terms: reuse with attribution", _FXRATES),
        _src("macro:cb:bde", "Banco de España",
             "https://www.bde.es/bde/es/secciones/informes/", "es", "ES", "central_bank",
             "Banco de España terms: reuse with attribution", _FXRATES),
        _src("macro:cb:bcb", "Banco Central do Brasil",
             "https://www.bcb.gov.br/publicacoes/atascopom", "pt", "BR", "central_bank",
             "BCB terms: public information", _FXRATES),
        _src("macro:cb:snb", "Schweizerische Nationalbank",
             "https://www.snb.ch/de/the-snb/mandates-goals/monetary-policy", "de", "CH",
             "central_bank", "SNB terms: reuse with attribution", _FX),
        _src("macro:cb:boj", "Bank of Japan", "https://www.boj.or.jp/", "ja", "JP",
             "central_bank", "BoJ terms: reuse with attribution", _ALL),
        _src("macro:cb:pboc", "People's Bank of China", "http://www.pbc.gov.cn/", "zh", "CN",
             "central_bank", "PBoC terms: public information", _FX),
        _src("macro:cb:boe", "Bank of England",
             "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes", "en", "GB",
             "central_bank", "Open Government Licence v3.0", _ALL),
        _src("macro:cb:rba", "Reserve Bank of Australia",
             "https://www.rba.gov.au/monetary-policy/", "en", "AU", "central_bank",
             "CC BY 4.0", _FXRATES),
        _src("macro:cb:rbnz", "Reserve Bank of New Zealand",
             "https://www.rbnz.govt.nz/monetary-policy", "en", "NZ", "central_bank",
             "CC BY 4.0", _FXRATES),
        _src("macro:cb:boc", "Bank of Canada",
             "https://www.bankofcanada.ca/press/press-releases/", "en", "CA", "central_bank",
             "Bank of Canada terms: reuse with attribution", _FXRATES),
        _src("macro:cb:riksbank", "Sveriges Riksbank",
             "https://www.riksbank.se/en-gb/monetary-policy/", "en", "SE", "central_bank",
             "Riksbank terms: reuse with attribution", _FX),
        _src("macro:cb:norges", "Norges Bank",
             "https://www.norges-bank.no/en/topics/Monetary-policy/", "en", "NO",
             "central_bank", "Norges Bank terms: reuse with attribution", _FX),
        _src("macro:cb:mas", "Monetary Authority of Singapore",
             "https://www.mas.gov.sg/news", "en", "SG", "central_bank",
             "MAS terms: public information", _FX),
    ),
    "statistics_office": (
        _src("macro:stat:bls", "US Bureau of Labor Statistics", "https://www.bls.gov/bls/news-release.htm",
             "en", "US", "statistics", "public domain (US government work)", _ALL),
        _src("macro:stat:bea", "US Bureau of Economic Analysis", "https://www.bea.gov/data",
             "en", "US", "statistics", "public domain (US government work)", _ALL),
        _src("macro:stat:eurostat", "Eurostat",
             "https://ec.europa.eu/eurostat/web/main/data/database", "en", "EA", "statistics",
             "Eurostat reuse policy: free with attribution", _ALL),
        _src("macro:stat:ons", "UK Office for National Statistics",
             "https://www.ons.gov.uk/economy", "en", "GB", "statistics",
             "Open Government Licence v3.0", _ALL),
        _src("macro:stat:abs", "Australian Bureau of Statistics",
             "https://www.abs.gov.au/statistics", "en", "AU", "statistics", "CC BY 4.0", _ALL),
        _src("macro:stat:statcan", "Statistics Canada", "https://www150.statcan.gc.ca/",
             "en", "CA", "statistics", "Statistics Canada Open Licence", _ALL),
    ),
    "debt_management": (
        _src("macro:dmo:ustreasury", "US Treasury auction results",
             "https://www.treasurydirect.gov/auctions/announcements-data-results/", "en", "US",
             "debt_management", "public domain (US government work)", ("bonds", "forex")),
        _src("macro:dmo:finanzagentur", "Deutsche Finanzagentur (Bund issuance)",
             "https://www.deutsche-finanzagentur.de/en/", "de", "DE", "debt_management",
             "Finanzagentur terms: public information", ("bonds", "forex")),
        _src("macro:dmo:ukdmo", "UK Debt Management Office", "https://www.dmo.gov.uk/",
             "en", "GB", "debt_management", "Open Government Licence v3.0",
             ("bonds", "forex")),
        _src("macro:dmo:aft", "Agence France Trésor", "https://www.aft.gouv.fr/",
             "fr", "FR", "debt_management", "AFT terms: public information",
             ("bonds", "forex")),
        _src("macro:dmo:mof_jp", "Japan Ministry of Finance (JGB and intervention)",
             "https://www.mof.go.jp/", "ja", "JP", "debt_management",
             "MoF terms: public information", ("bonds", "forex")),
    ),
    "regulator": (
        _src("macro:reg:cftc_cot", "CFTC Commitments of Traders",
             "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm", "en", "US",
             "regulator", "public domain (US government work)",
             ("forex", "metals", "energy", "softs", "indices")),
        _src("macro:reg:sec_edgar", "SEC EDGAR full-text search",
             "https://efts.sec.gov/LATEST/search-index?q=", "en", "US", "regulator",
             "public domain (US government work)", ("indices",)),
    ),
    "commodity_agency": (
        _src("macro:com:eia", "US Energy Information Administration",
             "https://www.eia.gov/petroleum/supply/weekly/", "en", "US", "agency",
             "public domain (US government work)", ("energy",)),
        _src("macro:com:usda", "USDA WASDE and reports",
             "https://www.usda.gov/oce/commodity/wasde", "en", "US", "agency",
             "public domain (US government work)", ("softs",)),
        _src("macro:com:opec", "OPEC Monthly Oil Market Report",
             "https://www.opec.org/opec_web/en/publications/338.htm", "en", "AT", "agency",
             "OPEC terms: reuse with attribution", ("energy",)),
        _src("macro:com:lbma", "LBMA precious metals prices",
             "https://www.lbma.org.uk/prices-and-data", "en", "GB", "market_infrastructure",
             "LBMA terms: non-commercial use with attribution", ("metals",)),
    ),
    "market_infrastructure": (
        _src("macro:mkt:cme", "CME Group public volume and open interest",
             "https://www.cmegroup.com/market-data/volume-open-interest.html", "en", "US",
             "exchange", "CME terms: delayed public data", ("energy", "metals", "indices")),
        _src("macro:mkt:ice", "ICE public report centre",
             "https://www.ice.com/marketdata/reports", "en", "US", "exchange",
             "ICE terms: delayed public data", ("energy", "softs")),
    ),
    "international_organisation": (
        _src("macro:intl:bis", "Bank for International Settlements statistics",
             "https://data.bis.org/", "en", "CH", "international",
             "BIS terms: free reuse with attribution", _ALL),
        _src("macro:intl:imf", "IMF data (COFER, IFS)", "https://data.imf.org/", "en", "US",
             "international", "IMF terms: free reuse with attribution", _ALL),
        _src("macro:intl:oecd", "OECD statistics", "https://data-explorer.oecd.org/", "en",
             "FR", "international", "OECD terms: free reuse with attribution", _ALL),
    ),
    "academic": (
        _src("macro:acad:nber", "NBER working papers", "https://www.nber.org/papers", "en",
             "US", "academic", "abstracts public; papers per NBER terms", _ALL),
        _src("macro:acad:ssrn_frn", "SSRN financial economics network",
             "https://www.ssrn.com/index.cfm/en/fen/", "en", "US", "academic",
             "abstracts public", _ALL),
        _src("macro:acad:arxiv_qfin", "arXiv q-fin", "https://arxiv.org/list/q-fin/recent",
             "en", "US", "academic", "arXiv non-exclusive licence", _ALL),
        _src("macro:acad:bis_wp", "BIS working papers",
             "https://www.bis.org/wppubl.htm", "en", "CH", "academic",
             "BIS terms: free reuse with attribution", _ALL),
        _src("macro:acad:ecb_wp", "ECB working paper series",
             "https://www.ecb.europa.eu/pub/research/working-papers/html/index.en.html", "en",
             "EA", "academic", "ECB terms: reuse with attribution", _ALL),
        _src("macro:acad:cnki_macro", "CNKI 宏观经济 (macro economics index)",
             "https://kns.cnki.net/", "zh", "CN", "academic",
             "abstracts public; full text licensed", _ALL),
    ),
    "code": (
        _src("macro:code:github_macro", "GitHub search: macro factor implementations",
             "https://github.com/search?q=macro+surprise+backtest&type=repositories", "en",
             "US", "code", "per-repository licence; check before reuse", _ALL),
        _src("macro:code:gitee_macro", "Gitee 宏观 因子 repositories",
             "https://search.gitee.com/?type=repository&q=%E5%AE%8F%E8%A7%82%E5%9B%A0%E5%AD%90",
             "zh", "CN", "code", "per-repository licence; check before reuse", _ALL),
        _src("macro:code:quantlib_rates", "QuantLib rates and curve implementations",
             "https://github.com/lballabio/QuantLib", "en", "IT", "code",
             "modified BSD", ("bonds", "forex")),
    ),
}


def queries(domain: str, language: str) -> list[str]:
    """The native queries this domain asks in this language, built from the dictionary.

    A language with no dictionary entry returns [] -- which the caller reports as an UNMEASURED
    language rather than silently searching in English and believing it searched natively.
    """
    lang = str(language or "").lower()
    terms = TERMS.get(lang)
    if not terms:
        return []
    topics = DOMAIN_TOPICS.get(domain, TOPICS)
    stems: list[str] = []
    for topic in topics:
        stems.extend(terms.get(topic, ()))
    anchors = {
        "en": ("announcement", "calendar", "reaction"),
        "de": ("Ankündigung", "Kalender", "Marktreaktion"),
        "fr": ("annonce", "calendrier", "réaction"),
        "it": ("annuncio", "calendario", "reazione"),
        "es": ("anuncio", "calendario", "reacción"),
        "pt": ("anúncio", "calendário", "reação"),
        "ja": ("発表", "日程", "市場反応"),
        "zh": ("公告", "日历", "市场反应"),
    }[lang]
    out: list[str] = list(dict.fromkeys(stems))
    out.extend(f"{stem} {anchor}" for stem in stems[:6] for anchor in anchors)
    return list(dict.fromkeys(out))


# =============================================================================================
# The dataset catalogue
# =============================================================================================
CATALOGUE: tuple[Any, ...] = (
    _spec(dataset_id="fred", institution="Federal Reserve Bank of St. Louis (FRED)",
          coverage="US and international macro, rates, FX, commodities, equities: ~800k series",
          frequency="daily to annual, per series",
          publication_lag="market series same day; survey and national accounts days to months",
          revisions="CURRENT VINTAGE ONLY through the public CSV endpoint; market series barely "
                    "revise, national accounts revise heavily",
          licence="free; most series carry the originating agency's terms",
          history="1950s onward for the core series",
          pit_feasible="NO through FRED itself -- use ALFRED for vintages",
          assets=("forex", "bonds", "indices", "metals", "energy"),
          mechanism_families=("rates_transmission", "macro_surprise", "risk_regime"),
          how_to_fetch="fredgraph CSV, or the API with the key at data/secrets/fred.json; the "
                       "desk's captured copy is desks/mt5/data/axes/fred.json",
          url="https://fred.stlouisfed.org/"),
    _spec(dataset_id="alfred", institution="FRED archival vintages (ALFRED)",
          coverage="the same series as FRED, by vintage date",
          frequency="per release, one vintage per revision",
          publication_lag="identical to the underlying series",
          revisions="every vintage retained -- this is the point of the archive",
          licence="free with an API key",
          history="varies by series; core macro back to the 1990s",
          pit_feasible="YES -- the only PIT route for a revised US macro series",
          assets=("forex", "bonds", "indices"),
          mechanism_families=("macro_surprise", "revision_response"),
          how_to_fetch="ALFRED API with realtime_start/realtime_end; key at "
                       "data/secrets/fred.json (named, never printed)",
          url="https://alfred.stlouisfed.org/"),
    _spec(dataset_id="ecb_sdw", institution="ECB Data Portal (SDMX)",
          coverage="euro area rates, reference exchange rates, AAA yield curve, monetary "
                   "aggregates",
          frequency="daily to monthly",
          publication_lag="reference rates ~16:00 CET same day; statistics days to weeks",
          revisions="SDMX carries the vintage; the published reference rates are not revised",
          licence="ECB terms: free reuse with attribution",
          history="1999 onward; the desk's capture starts 2011",
          pit_feasible="YES for reference rates and yield curves",
          assets=("forex", "bonds"),
          mechanism_families=("fixing_flow", "rates_transmission", "policy_surprise"),
          how_to_fetch="data-api.ecb.europa.eu SDMX; captured at desks/mt5/data/axes/ecb.json",
          url="https://data.ecb.europa.eu/"),
    _spec(dataset_id="boe_database", institution="Bank of England statistical database",
          coverage="Bank Rate, gilt yields, effective rates, money and credit",
          frequency="daily to monthly",
          publication_lag="daily series next business day; statistics ~1 month",
          revisions="monetary statistics revise; Bank Rate does not",
          licence="Open Government Licence v3.0",
          history="1975 onward for Bank Rate",
          pit_feasible="PARTIAL -- no vintage service; Bank Rate is safe, aggregates are not",
          assets=("forex", "bonds"),
          mechanism_families=("policy_surprise", "rates_transmission"),
          how_to_fetch="BoE IADB CSV endpoint by series code",
          url="https://www.bankofengland.co.uk/boeapps/database/"),
    _spec(dataset_id="ons", institution="UK Office for National Statistics",
          coverage="UK CPI, labour market, GDP, retail sales, trade",
          frequency="monthly and quarterly",
          publication_lag="CPI ~2 weeks, GDP ~6 weeks",
          revisions="GDP and trade revise substantially; CPI does not",
          licence="Open Government Licence v3.0",
          history="long, by series",
          pit_feasible="PARTIAL -- superseded editions are archived but not as a clean vintage "
                       "API",
          assets=("forex", "bonds", "indices"),
          mechanism_families=("macro_surprise", "revision_response"),
          how_to_fetch="ONS API / time series CSV by series id",
          url="https://www.ons.gov.uk/"),
    _spec(dataset_id="eurostat", institution="Eurostat",
          coverage="euro area and member state CPI/HICP, GDP, unemployment, trade",
          frequency="monthly and quarterly",
          publication_lag="HICP flash ~1 day after month end, final ~2 weeks",
          revisions="flash to final is a revision and must be treated as one",
          licence="free reuse with attribution",
          history="1996 onward for HICP",
          pit_feasible="PARTIAL -- flash and final are separate observations, which is the "
                       "honest PIT construction",
          assets=("forex", "bonds", "indices"),
          mechanism_families=("macro_surprise", "revision_response"),
          how_to_fetch="Eurostat SDMX REST by dataset code",
          url="https://ec.europa.eu/eurostat/"),
    _spec(dataset_id="bls_bea", institution="US BLS and BEA",
          coverage="CPI, PPI, payrolls, unemployment, GDP, PCE",
          frequency="monthly and quarterly",
          publication_lag="payrolls first Friday 08:30 ET; CPI mid-month 08:30 ET",
          revisions="payrolls revise for two months; GDP has three estimates",
          licence="public domain (US government work)",
          history="long",
          pit_feasible="YES through ALFRED vintages; NO from the agency's current table",
          assets=("forex", "bonds", "indices", "metals"),
          mechanism_families=("macro_surprise", "revision_response"),
          how_to_fetch="BLS public API v2 / BEA API; vintages through ALFRED",
          url="https://www.bls.gov/"),
    _spec(dataset_id="abs", institution="Australian Bureau of Statistics",
          coverage="Australian CPI, labour force, retail trade, GDP",
          frequency="monthly and quarterly",
          publication_lag="labour force ~2 weeks, CPI quarterly ~4 weeks",
          revisions="seasonally adjusted series revise",
          licence="CC BY 4.0",
          history="long",
          pit_feasible="PARTIAL -- superseded releases are archived as documents",
          assets=("forex", "bonds"),
          mechanism_families=("macro_surprise",),
          how_to_fetch="ABS Data API (SDMX)",
          url="https://www.abs.gov.au/"),
    _spec(dataset_id="statcan", institution="Statistics Canada",
          coverage="Canadian CPI, labour force survey, GDP, trade",
          frequency="monthly and quarterly",
          publication_lag="LFS ~1 week after reference week, CPI ~3 weeks",
          revisions="LFS and GDP revise",
          licence="Statistics Canada Open Licence",
          history="long",
          pit_feasible="PARTIAL -- no vintage API; archived releases only",
          assets=("forex", "bonds", "energy"),
          mechanism_families=("macro_surprise",),
          how_to_fetch="StatCan Web Data Service by vector id",
          url="https://www150.statcan.gc.ca/"),
    _spec(dataset_id="rba_statistics", institution="Reserve Bank of Australia statistics",
          coverage="cash rate, statistical tables, FX rates",
          frequency="daily to monthly",
          publication_lag="cash rate same day; tables monthly",
          revisions="rare",
          licence="CC BY 4.0",
          history="1990 onward for the cash rate",
          pit_feasible="YES for the cash rate and published FX rates",
          assets=("forex", "bonds"),
          mechanism_families=("policy_surprise", "carry"),
          how_to_fetch="RBA statistical tables CSV",
          url="https://www.rba.gov.au/statistics/"),
    _spec(dataset_id="rbnz_statistics", institution="Reserve Bank of New Zealand statistics",
          coverage="OCR, wholesale rates, exchange rates",
          frequency="daily to monthly",
          publication_lag="OCR same day",
          revisions="rare",
          licence="CC BY 4.0",
          history="1999 onward for the OCR",
          pit_feasible="YES for the OCR",
          assets=("forex", "bonds"),
          mechanism_families=("policy_surprise", "carry"),
          how_to_fetch="RBNZ statistics CSV by table",
          url="https://www.rbnz.govt.nz/statistics"),
    _spec(dataset_id="boc_statistics", institution="Bank of Canada Valet API",
          coverage="policy rate, bond yields, daily exchange rates (incl. the historic noon "
                   "rate)",
          frequency="daily",
          publication_lag="same day, ~16:30 ET for the daily rates",
          revisions="none for published rates",
          licence="Bank of Canada terms: reuse with attribution",
          history="1990s onward; the noon rate ends 2017 and the successor is a 16:30 rate",
          pit_feasible="YES",
          assets=("forex", "bonds"),
          mechanism_families=("fixing_flow", "policy_surprise", "carry"),
          how_to_fetch="Valet API observations endpoint by series",
          url="https://www.bankofcanada.ca/valet/docs"),
    _spec(dataset_id="snb_statistics", institution="Swiss National Bank data portal",
          coverage="policy rate, sight deposits (the intervention tell), FX reserves",
          frequency="weekly and monthly",
          publication_lag="sight deposits Monday for the prior week",
          revisions="rare",
          licence="SNB terms: reuse with attribution",
          history="2000s onward",
          pit_feasible="YES -- sight deposits carry a publication date",
          assets=("forex",),
          mechanism_families=("intervention", "policy_surprise"),
          how_to_fetch="SNB data portal CSV by table id",
          url="https://data.snb.ch/"),
    _spec(dataset_id="cftc_cot", institution="CFTC Commitments of Traders",
          coverage="futures positioning by category for FX, metals, energy, softs, indices",
          frequency="weekly (Tuesday snapshot)",
          publication_lag="published Friday 15:30 ET -- KNOWABLE 4 DAYS AFTER THE SNAPSHOT",
          revisions="occasional reclassification; the desk stores the as-of and the knowable-at "
                    "separately",
          licence="public domain (US government work)",
          history="1986 onward legacy, 2006 onward disaggregated",
          pit_feasible="YES when the 4-day lag is applied; NO if the as-of date is used",
          assets=("forex", "metals", "energy", "softs", "indices"),
          mechanism_families=("positioning_crowding", "forced_flow"),
          how_to_fetch="cftc.gov/dea/newcot/deafut.txt; captured at "
                       "desks/mt5/data/axes/cot.json with knowable_lag_days=4",
          url="https://www.cftc.gov/MarketReports/CommitmentsofTraders/"),
    _spec(dataset_id="eia", institution="US Energy Information Administration",
          coverage="weekly petroleum status, natural gas storage, production",
          frequency="weekly",
          publication_lag="crude stocks Wednesday 10:30 ET; gas storage Thursday 10:30 ET",
          revisions="weekly series revise into the monthly series",
          licence="public domain (US government work)",
          history="1980s onward",
          pit_feasible="YES -- the release time is published to the minute",
          assets=("energy",),
          mechanism_families=("inventory_surprise", "forced_flow"),
          how_to_fetch="EIA open data API v2 by series id",
          url="https://www.eia.gov/opendata/"),
    _spec(dataset_id="usda", institution="USDA WASDE and NASS reports",
          coverage="world supply and demand estimates for grains, oilseeds, cotton, sugar",
          frequency="monthly (WASDE) plus quarterly stocks",
          publication_lag="WASDE 12:00 ET on the release day",
          revisions="each WASDE revises the prior estimate by construction",
          licence="public domain (US government work)",
          history="1973 onward",
          pit_feasible="YES -- release times are fixed and published",
          assets=("softs",),
          mechanism_families=("inventory_surprise", "seasonality"),
          how_to_fetch="USDA ESMIS / NASS Quick Stats API",
          url="https://www.usda.gov/oce/commodity/wasde"),
    _spec(dataset_id="opec_momr", institution="OPEC Monthly Oil Market Report",
          coverage="OPEC production, demand forecasts, stock levels",
          frequency="monthly",
          publication_lag="mid-month, announced in advance",
          revisions="each report revises the prior month's estimates",
          licence="OPEC terms: reuse with attribution",
          history="2001 onward",
          pit_feasible="PARTIAL -- PDF publication date is the stamp; tables need parsing",
          assets=("energy",),
          mechanism_families=("inventory_surprise", "policy_surprise"),
          how_to_fetch="monthly PDF/Excel from the OPEC publications index",
          url="https://www.opec.org/opec_web/en/publications/338.htm"),
    _spec(dataset_id="us_treasury_auctions", institution="US Treasury / TreasuryDirect",
          coverage="auction announcements, results, bid-to-cover, quarterly refunding",
          frequency="weekly to quarterly",
          publication_lag="announcement ~1 week ahead; results ~13:00 ET on the day",
          revisions="none",
          licence="public domain (US government work)",
          history="1980s onward",
          pit_feasible="YES -- announcement and result carry separate timestamps",
          assets=("bonds", "forex"),
          mechanism_families=("forced_flow", "issuance_concession"),
          how_to_fetch="TreasuryDirect auction announcements/results API",
          url="https://www.treasurydirect.gov/auctions/announcements-data-results/"),
    _spec(dataset_id="lbma", institution="LBMA precious metals price",
          coverage="gold and silver LBMA auction prices (AM/PM)",
          frequency="daily",
          publication_lag="within the hour of the auction",
          revisions="none",
          licence="LBMA terms: non-commercial use with attribution",
          history="1968 onward for gold",
          pit_feasible="YES",
          assets=("metals",),
          mechanism_families=("fixing_flow", "forced_flow"),
          how_to_fetch="LBMA prices and data page (JSON/CSV)",
          url="https://www.lbma.org.uk/prices-and-data"),
    _spec(dataset_id="cme_ice_volumes", institution="CME Group and ICE public volume/OI",
          coverage="daily volume and open interest by contract; expiry calendars",
          frequency="daily",
          publication_lag="next business day for final OI",
          revisions="preliminary to final OI is a revision",
          licence="exchange terms: delayed public data, non-redistribution",
          history="several years of public files",
          pit_feasible="PARTIAL -- use the final figure with its own publication date",
          assets=("energy", "metals", "indices"),
          mechanism_families=("roll_cycle", "dealer_gamma", "forced_flow"),
          how_to_fetch="CME volume/OI report files; ICE report centre",
          url="https://www.cmegroup.com/market-data/volume-open-interest.html"),
    _spec(dataset_id="lme", institution="London Metal Exchange",
          coverage="base metal official prices, warehouse stocks, warrant cancellations",
          frequency="daily",
          publication_lag="official prices same day; stocks 09:00 London next day",
          revisions="stock figures are restated when a warehouse reports late",
          licence="LME terms: delayed public data, non-redistribution",
          history="recent years public; deep history is licensed",
          pit_feasible="PARTIAL -- the daily stock file carries its own date; restatements do "
                       "not",
          assets=("metals",),
          mechanism_families=("inventory_surprise", "forced_flow", "roll_cycle"),
          how_to_fetch="LME public data pages (daily stock and price files)",
          url="https://www.lme.com/en/Market-data"),
    _spec(dataset_id="bis_cbpol", institution="Bank for International Settlements",
          coverage="policy rates for 38 jurisdictions, daily and monthly",
          frequency="daily and monthly",
          publication_lag="days after a change",
          revisions="rare",
          licence="BIS terms: free reuse with attribution",
          history="1946 onward for some, 1999 onward for most",
          pit_feasible="PARTIAL -- the rate change date is exact, the BIS publication date is "
                       "not carried in the flat file",
          assets=("forex", "bonds"),
          mechanism_families=("carry", "policy_surprise"),
          how_to_fetch="WS_CBPOL_csv_flat.zip; captured at desks/mt5/data/axes/bis.json",
          url="https://data.bis.org/"),
    _spec(dataset_id="bis_statistics", institution="BIS statistics and working papers",
          coverage="FX turnover, banking statistics, credit to the non-financial sector, "
                   "research",
          frequency="quarterly and triennial",
          publication_lag="quarterly statistics ~3 months",
          revisions="banking statistics revise",
          licence="BIS terms: free reuse with attribution",
          history="1970s onward",
          pit_feasible="PARTIAL -- release dates are published, vintages are not",
          assets=("forex", "bonds", "indices"),
          mechanism_families=("dealer_balance_sheet", "carry"),
          how_to_fetch="data.bis.org bulk files; www.bis.org/wppubl.htm for research",
          url="https://data.bis.org/"),
    _spec(dataset_id="cb_publications",
          institution="central bank publication indexes (Fed, ECB, BoE, SNB, BoJ, PBoC, ...)",
          coverage="statements, minutes, projections, speeches, intervention notices",
          frequency="per meeting plus ad hoc speeches",
          publication_lag="statement at the decision minute; minutes weeks later",
          revisions="none -- a statement is not revised, it is superseded",
          licence="per institution; recorded on each source row",
          history="1990s onward for most",
          pit_feasible="YES -- the publication timestamp is the record",
          assets=("forex", "bonds", "indices", "metals"),
          mechanism_families=("policy_surprise", "language_change", "intervention"),
          how_to_fetch="each institution's own index page (see SOURCE_CLASSES['central_bank'])",
          url="https://www.bis.org/cbanks.htm"),
    _spec(dataset_id="mof_intervention",
          institution="Japan Ministry of Finance intervention records",
          coverage="monthly and daily FX intervention amounts",
          frequency="monthly, with daily detail published quarterly",
          publication_lag="month-end totals ~1 month; daily detail ~1 quarter",
          revisions="none",
          licence="MoF terms: public information",
          history="1991 onward",
          pit_feasible="YES when the DISCLOSURE date is used, never the intervention date",
          assets=("forex",),
          mechanism_families=("intervention",),
          how_to_fetch="MoF FX intervention page (CSV)",
          url="https://www.mof.go.jp/english/policy/international_policy/reference/"
              "feio/index.htm",
          language="ja"),
    _spec(dataset_id="forced_flow_calendar",
          institution="desk-derived (desks/mt5/research/forced_flow_calendar.py)",
          coverage="month-end, index rebalance, futures roll, option expiry, fixings, bond "
                   "auctions, inventories, holidays",
          frequency="rule-derived, dense, years ahead",
          publication_lag="none -- every row is computed from a rule",
          revisions="central bank meeting dates are a TABLE labelled VERIFY_BANK; auctions are "
                    "a PATTERN labelled VERIFY_SCHEDULE",
          licence="desk-owned",
          history="whatever range the generator is asked for",
          pit_feasible="YES -- a rule-derived date is knowable years in advance",
          assets=("forex", "bonds", "indices", "metals", "energy", "softs"),
          mechanism_families=("forced_flow", "fixing_flow", "roll_cycle", "issuance_concession"),
          how_to_fetch="desks/mt5/data/forced_flow_calendar.json",
          url=""),
    _spec(dataset_id="desk_universe_bars",
          institution="desk-owned MT5 capture (desks/mt5/data/universe)",
          coverage="every Fusion-executable symbol at M15/H1/H4/D1",
          frequency="per bar",
          publication_lag="none -- the desk records its own broker's tape",
          revisions="none; the broker's clock is +2 winter / +3 summer and is measured, not "
                    "assumed",
          licence="desk-owned",
          history="2018 onward for the majors",
          pit_feasible="YES",
          assets=("forex", "bonds", "indices", "metals", "energy", "softs"),
          mechanism_families=("event_reaction", "propagation", "regime"),
          how_to_fetch="desks/mt5/data/universe/<SYMBOL>_<TF>.parquet",
          url=""),
    _spec(dataset_id="alpha_registry",
          institution="desk-owned canonical research registry (libs/moat/registry.py)",
          coverage="discoveries, candidates, trials, verdicts, sources, provenance",
          frequency="continuous",
          publication_lag="none",
          revisions="trials, events, audit log, returns and provenance are IMMUTABLE by trigger",
          licence="desk-owned",
          history="the whole research record",
          pit_feasible="YES -- every row carries created_at",
          assets=("forex", "bonds", "indices", "metals", "energy", "softs"),
          mechanism_families=("failure_resurrection", "residual", "transformation"),
          how_to_fetch="libs.moat.registry.connect()",
          url=""),
)

CATALOGUE_BY_ID: dict[str, Any] = {row.dataset_id: row for row in CATALOGUE}


# =============================================================================================
# The PIT stamp
# =============================================================================================
_TIME_KEYS = ("publication_time", "published_at", "knowable_at", "release_time")
_ASOF_KEYS = ("as_of", "reference_date", "period", "observation_date", "date")


def pit_stamp(row: Any) -> dict[str, Any]:
    """PIT_SAFE only when the row says WHEN IT BECAME KNOWABLE. Everything else is NOT_PIT_SAFE.

    The default is NO on purpose. A macro observation without a publication time is indexed by
    its reference period, and a backtest that reads it at the period's timestamp trades on a
    number nobody had -- which is the single most flattering bug available to a macro desk.
    """
    if not isinstance(row, dict):
        return {"pit_status": NOT_PIT_SAFE, "reason": "row is not a mapping",
                "publication_time": None, "as_of": None}
    published = next((row[k] for k in _TIME_KEYS if row.get(k)), None)
    as_of = next((row[k] for k in _ASOF_KEYS if row.get(k)), None)
    dataset = str(row.get("dataset_id") or row.get("dataset") or "")
    spec = CATALOGUE_BY_ID.get(dataset)
    out: dict[str, Any] = {"publication_time": published, "as_of": as_of,
                           "dataset_id": dataset or None,
                           "dataset_pit_feasible": getattr(spec, "pit_feasible", None)}
    if published is None:
        out["pit_status"] = NOT_PIT_SAFE
        out["reason"] = ("no publication_time/published_at/knowable_at: the row is indexed by "
                         "its reference period only, so reading it at that stamp is a lookahead")
        return out
    if as_of is not None and str(published) < str(as_of):
        out["pit_status"] = NOT_PIT_SAFE
        out["reason"] = (f"publication_time {published!r} precedes as_of {as_of!r}: a value "
                         "cannot be published before the period it measures")
        return out
    if spec is not None and str(getattr(spec, "pit_feasible", "")).upper().startswith("NO"):
        out["pit_status"] = NOT_PIT_SAFE
        out["reason"] = (f"dataset {dataset!r} publishes the current vintage only "
                         f"({spec.pit_feasible}); the stamp on this row is the crawl, not a "
                         "vintage")
        return out
    out["pit_status"] = PIT_SAFE
    out["reason"] = "publication_time present and consistent with the reference period"
    return out


# =============================================================================================
# The registry doors -- lazily, so a missing sibling never stops the module importing
# =============================================================================================
def _registry() -> Any:
    try:
        return importlib.import_module("libs.moat.registry")
    except ImportError:
        return None


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def register_source(conn: Any, source_id: str, *, url: str = "", kind: str = "",
                    language: str = "", country: str = "", asset_classes: tuple[str, ...] = (),
                    discovered_from: str = "", discovered_via: str = "macro_scout",
                    licence_note: str = "", meta: Any = None) -> bool:
    """One source into the graph, language stamped. True when the row is new.

    `source_frontier.register_source` is the desk's door and is used when it imports; the direct
    INSERT is the fallback for a box where the research tree is not on the path, and it writes
    the SAME columns so the two are indistinguishable downstream.

    NO CONNECTION MEANS NOTHING IS WRITTEN. The desk's door opens its own connection when it is
    handed None, which would make a scout run with no context write into the canonical registry
    -- exactly what a test or a dry run must never do. The caller's connection is the authority
    here, and its absence is reported rather than worked around.
    """
    if conn is None:
        return False
    try:
        sf = importlib.import_module("source_frontier")
    except ImportError:
        sf = None
    if sf is not None and hasattr(sf, "register_source"):
        return bool(sf.register_source(
            source_id, url=url, kind=kind, language=language, country=country,
            asset_classes=list(asset_classes), discovered_from=discovered_from,
            discovered_via=discovered_via, licence_note=licence_note, meta=meta, conn=conn))
    if conn is None:
        return False
    row = conn.execute("SELECT source_id FROM sources WHERE source_id=?", (source_id,)).fetchone()
    if row is not None:
        return False
    conn.execute("INSERT INTO sources(source_id, url, kind, language, country, "
                 "asset_classes_json, discovered_from, discovered_via, first_seen, last_crawled, "
                 "status, licence_note, meta_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (source_id, url, kind, language, country,
                  json.dumps(sorted(asset_classes), ensure_ascii=False), discovered_from,
                  discovered_via, _now(), None, "active", licence_note,
                  json.dumps(meta or {}, ensure_ascii=False, default=str)))
    conn.commit()
    return True


def _edge(conn: Any, parent: str, child: str, relation: str) -> bool:
    """One expansion edge of the source graph. Absent registry: reported, never pretended."""
    reg = _registry()
    if reg is None or conn is None:
        return False
    reg.link("source", parent, "source", child, relation, conn=conn)
    return True


def _scout_result(name: str, *, sources: list[str], new: int, edges: int,
                  languages: list[str], unmeasured: list[dict[str, str]],
                  notes: list[dict[str, str]], extra: dict[str, Any] | None = None
                  ) -> dict[str, Any]:
    out: dict[str, Any] = {
        "miner": name, "generator": f"{TAG}{name}", "region": REGION, "ok": True,
        "sources": sources, "n_sources": len(sources), "n_new": new, "n_edges": edges,
        "languages": sorted(set(languages)), "unmeasured": unmeasured, "notes": notes,
        "rule": "a scout publishes WHERE to look and IN WHICH WORDS; the fetch is the crawler's "
                "job and is UNMEASURED here",
    }
    out.update(extra or {})
    return out


def _register_classes(ctx: Any, classes: tuple[str, ...], name: str,
                      root_id: str) -> tuple[list[str], int, int, list[str]]:
    conn = getattr(ctx, "conn", None)
    ids: list[str] = []
    new = 0
    edges = 0
    langs: list[str] = []
    if conn is None and hasattr(ctx, "note"):
        ctx.note("register_source", "no registry connection: the sources are reported and "
                                    "nothing is written")
    register_source(conn, root_id, url="", kind="scout_root", language="en",
                    discovered_via="macro_mandate", licence_note="desk-declared root",
                    meta={"scout": name, "region": REGION})
    for cls in classes:
        for row in SOURCE_CLASSES.get(cls, ()):
            created = register_source(
                conn, str(row["source_id"]), url=str(row["url"]), kind=str(row["kind"]),
                language=str(row["language"]), country=str(row["country"]),
                asset_classes=tuple(row["asset_classes"]), discovered_from=root_id,
                discovered_via=f"{TAG}{name}", licence_note=str(row["licence"]),
                meta={"institution": row["institution"], "source_class": cls,
                      "region": REGION})
            ids.append(str(row["source_id"]))
            langs.append(str(row["language"]))
            new += int(created)
            edges += int(_edge(conn, root_id, str(row["source_id"]), "expands"))
    return ids, new, edges, langs


# =============================================================================================
# The four scouts
# =============================================================================================
def mine_data_scout(ctx: Any) -> dict[str, Any]:
    """The dataset estate: who publishes the series, under what licence, reachable from here?"""
    root = f"{TAG}data_scout"
    ids, new, edges, langs = _register_classes(
        ctx, ("statistics_office", "debt_management", "regulator", "commodity_agency",
              "market_infrastructure", "international_organisation"), "data_scout", root)
    reachable: list[str] = []
    gaps: list[dict[str, str]] = []
    for spec in CATALOGUE:
        fetch = str(spec.how_to_fetch)
        local = "desks/mt5/data" in fetch or "libs.moat" in fetch
        if local:
            reachable.append(spec.dataset_id)
        else:
            gaps.append({"dataset_id": spec.dataset_id,
                         "why": "no captured copy on this box; the fetch is the crawler's job"})
    pit_no = [s.dataset_id for s in CATALOGUE
              if str(s.pit_feasible).upper().startswith(("NO", "PARTIAL"))]
    return _scout_result(
        "data_scout", sources=ids, new=new, edges=edges, languages=langs,
        unmeasured=[{"what": "dataset reachability", "why": f"{len(gaps)} catalogue rows have no "
                     "captured copy on this box and no fetch was attempted here"}],
        notes=[{"what": "pit", "why": f"{len(pit_no)} datasets are NOT or only PARTIALLY "
                "point-in-time feasible and every read of them is stamped"}],
        extra={"catalogue_size": len(CATALOGUE), "reachable_here": sorted(set(reachable)),
               "gaps": gaps, "pit_limited": pit_no,
               "secret_policy": f"the FRED key is named as {FRED_KEY_PATH} and never opened "
                                "here"})


def mine_academic_scout(ctx: Any) -> dict[str, Any]:
    """The research estate. A published result is a hypothesis here, never a privileged prior."""
    root = f"{TAG}academic_scout"
    ids, new, edges, langs = _register_classes(ctx, ("academic",), "academic_scout", root)
    plan = {d: {lang: queries(d, lang)[:8] for lang in DOMAIN_LANGUAGES.get(d, ("en",))}
            for d in ("central_bank_surprise", "macro_release_surprise", "positioning",
                      "rates_complexes", "fiscal_auction_calendars", "intervention_states",
                      "cross_asset_propagation", "fixing_flows")}
    return _scout_result(
        "academic_scout", sources=ids, new=new, edges=edges, languages=langs,
        unmeasured=[{"what": "retrieval", "why": "no fetch budget in this pass; the queries are "
                     "registered and the papers themselves are UNMEASURED until the crawler "
                     "runs"}],
        notes=[{"what": "anti-timid", "why": "a weak public claim is a hypothesis; it is "
                "re-measured on the desk's own data before it is worth anything"}],
        extra={"query_plan": plan,
               "n_queries": sum(len(q) for by_lang in plan.values() for q in by_lang.values())})


def mine_native_web_scout(ctx: Any) -> dict[str, Any]:
    """The institutions in their own words, and the steering for the crawlers that go there."""
    root = f"{TAG}native_web_scout"
    ids, new, edges, langs = _register_classes(ctx, ("central_bank",), "native_web_scout", root)
    steer = steer_deep_forest()
    plan = {lang: queries("native_language_intelligence", lang)[:12] for lang in LANGUAGES}
    empty = [lang for lang, q in plan.items() if not q]
    return _scout_result(
        "native_web_scout", sources=ids, new=new, edges=edges, languages=langs,
        unmeasured=([{"what": f"language:{lang}", "why": "no terminology dictionary entry"}
                     for lang in empty]
                    or [{"what": "fetch", "why": "the deep-forest miner and world_frontier do "
                         "the fetching on their own budget; nothing was crawled here"}]),
        notes=[{"what": "steering", "why": f"{len(steer['deep_forest'])} regions are handled by "
                f"deep_forest_miner and {len(steer['world_frontier'])} by world_frontier"}],
        extra={"query_plan": plan, "steering": steer})


def mine_code_scout(ctx: Any) -> dict[str, Any]:
    """Public implementations. Somebody's assumptions are readable; the desk still re-measures."""
    root = f"{TAG}code_scout"
    ids, new, edges, langs = _register_classes(ctx, ("code",), "code_scout", root)
    return _scout_result(
        "code_scout", sources=ids, new=new, edges=edges, languages=langs,
        unmeasured=[{"what": "repository contents", "why": "no clone or fetch in this pass"}],
        notes=[{"what": "licence", "why": "a repository's licence is checked before any reuse; "
                "an unlicensed repository is a reading, never a dependency"}],
        extra={"query_plan": {"en": queries("research_and_code_provenance", "en")[:10],
                              "zh": queries("research_and_code_provenance", "zh")[:10]}})


SCOUTS: dict[str, Any] = {
    "data_scout": mine_data_scout,
    "academic_scout": mine_academic_scout,
    "native_web_scout": mine_native_web_scout,
    "code_scout": mine_code_scout,
}


# =============================================================================================
# Steering the crawlers this desk already has
# =============================================================================================
#: The macro estate mapped onto the crawlers' own region vocabulary. The deep-forest miner owns
#: whichever of these its region index actually declares; everything else goes to the world
#: frontier, which crawls by URL and needs no region at all.
REGION_FOR_LANGUAGE: dict[str, tuple[str, ...]] = {
    "en": ("us", "gb", "au", "nz", "ca", "global", "institutional"),
    "de": ("de",),
    "fr": ("fr",),
    "it": ("it",),
    "es": ("es", "mx", "cl", "co", "pe", "ar"),
    "pt": ("br",),
    "ja": ("jp",),
    "zh": ("cn", "hk", "tw"),
}


def deep_forest_regions() -> tuple[str, ...]:
    """The regions the deep-forest miner actually supports, read from ITS OWN index."""
    try:
        doc = json.loads(DEEP_FOREST_SOURCES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    regions = doc.get("regions") if isinstance(doc, dict) else None
    if isinstance(regions, dict):
        return tuple(sorted(str(k) for k in regions))
    if isinstance(regions, list):
        return tuple(sorted(str(r.get("cluster") or r.get("name") or "") for r in regions
                            if isinstance(r, dict)))
    return ()


def steer_deep_forest(languages: tuple[str, ...] = LANGUAGES,
                      domains: tuple[str, ...] = ("native_language_intelligence",)
                      ) -> dict[str, Any]:
    """Which regions go to `deep_forest_miner --region`, and which go to `world_frontier`.

    The split is MEASURED against the miner's own region index rather than declared here: a
    hard-coded region list is right on the day it is written and silently wrong afterwards, and
    the miner would simply schedule nothing for a region it has never heard of.
    """
    supported = set(deep_forest_regions())
    forest: dict[str, dict[str, Any]] = {}
    frontier: list[dict[str, Any]] = []
    for lang in languages:
        wanted = REGION_FOR_LANGUAGE.get(lang, ())
        terms: list[str] = []
        for domain in domains:
            terms.extend(queries(domain, lang)[:10])
        for region in wanted:
            row = {"region": region, "language": lang, "queries": terms[:10],
                   "entry": "desks/mt5/research/deep_forest_miner.py --region " + region}
            if region in supported:
                forest[f"{lang}:{region}"] = row
            else:
                frontier.append({**row, "entry": "desks/mt5/side_channels/world_frontier.py",
                                 "why": "the deep-forest region index does not declare this "
                                        "region"})
    roots = [{"url": str(r["url"]), "lang": str(r["language"]),
              "via": f"{TAG}native_web_scout"}
             for cls in ("central_bank", "debt_management", "statistics_office")
             for r in SOURCE_CLASSES.get(cls, ())]
    return {"deep_forest": forest, "world_frontier": frontier,
            "world_frontier_roots": roots,
            "supported_regions": sorted(supported),
            "unmeasured": ([] if supported else
                           [{"what": "deep_forest_regions",
                             "why": f"{DEEP_FOREST_SOURCES} is absent or unreadable on this box; "
                                    "every region is routed to the world frontier"}])}


def summary() -> dict[str, Any]:
    """What the acquisition lane holds, in checkable numbers."""
    return {
        "region": REGION,
        "languages": list(LANGUAGES),
        "topics": list(TOPICS),
        "terms_per_language": {lang: sum(len(v) for v in TERMS[lang].values())
                               for lang in TERMS},
        "n_source_classes": len(SOURCE_CLASSES),
        "n_sources": sum(len(v) for v in SOURCE_CLASSES.values()),
        "catalogue_size": len(CATALOGUE),
        "pit_feasible_yes": [s.dataset_id for s in CATALOGUE
                             if str(s.pit_feasible).upper().startswith("YES")],
        "scouts": sorted(SCOUTS),
    }
