"""THE COUNTRY EQUIVALENCE ONTOLOGY -- every information class, and each country's functional
equivalent of it, as frozen data.

THE LAW IT ENCODES (ASIA_CHINA_FIRST_DIRECTIVE_2026-10-05, GLOBAL directive, CORE LAW and PART
III). "For every country and region: identify the LOCAL EQUIVALENT of every useful information
class." China has SHFE member rankings; the question elsewhere is not "does that country have
SHFE?" but "what is the closest public participant-positioning, exchange-member, broker-flow,
regulatory-position or open-interest dataset in that market?" -- and the same for the SGE
physical premium and SAFE's bank FX settlement. Every class is searched for FUNCTIONAL
equivalents, never brand names.

WHAT THIS MODULE IS. Data and pure functions. It opens no socket and no registry, and exactly one
file: the EXTENSION (`desks/mt5/data/equivalence_ontology_ext.json`), merged at import so a new
class or a new named equivalent is data, not a code change. The lists below are the directive's
FLOOR; the ontology is open above it (`load_extension`, and the candidate-class rows
`regional_parity` emits for every declaration no class matches).

  * ``CLASSES`` -- the information classes, copied VERBATIM from the directive's PART II ("FULL
    GLOBAL HARD-DATA TAXONOMY": twelve classes, 86 sub-classes, ASIA-1207..ASIA-1292 in the
    completion audit of 2026-10-06) plus the five PART III functions that have no PART II home
    (FX positioning, retail positioning, investor flows, shipping, energy; ASIA-1304/1305/1310/
    1312/1313). The other eight PART III functions are mapped onto the PART II sub-class that
    answers them in ``FUNCTIONS``; nothing is invented that the directive does not name.
  * ``KNOWN`` -- named per-country equivalents (publisher, series, cadence, url and, only where
    the endpoint is known to serve a dated file, the endpoint).
  * ``TRANSNATIONAL`` -- one public dataset that answers a class for an explicit, conservative
    list of countries (the BIS bulk files, the ECB data API, CFTC, Google Trends, IMF PortWatch).
  * ``PUBLISHERS`` -- the national central bank / statistics office / finance ministry of the
    major economies, and ``ROLE_STANDARD`` -- the few classes every one of those publishers
    publishes (CPI, GDP, policy rate ...). A class inferred this way is graded ``role``, below a
    named or transnational equivalent, and says so.
  * ``NO_EQUIVALENT_RULES`` -- the cases where the class genuinely has no local equivalent, each
    with its reason (an officially dollarized economy has no domestic policy rate; a landlocked
    economy has no seaport; a euro member has no national FX intervention).

THE FIVE DISPOSITIONS, AND THE ONE THING THIS MODULE REFUSES TO DO. A (country, class) cell is

    COVERED                 a source with PROOF of source -> measured outcome (an ingestion-ledger
                            unit that reached a measured downstream state)
    DECLARED                a country pack declares it; no such proof was found
    ABSENT_KNOWN_EQUIVALENT a public equivalent is known (named, transnational or role) and no
                            pack declares it -- the work queue's first rows
    NO_EQUIVALENT           the class has no local equivalent, with the reason
    UNMEASURED              nobody has looked -- never zero, never "absent", never "covered"

It NEVER DEFAULTS TO COVERED: ``dispose`` reaches COVERED only through a proof it was handed, and
an unreadable proof source is UNMEASURED by name rather than a clean "not fed".
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "BASE_CLASS_COUNT",
    "CLASSES",
    "CLASS_KEYS",
    "CLASS_SOURCE",
    "CORE_LAW_ANCHORS",
    "COUNTRY_NAMES",
    "DISPOSITIONS",
    "DOLLARIZED",
    "EURO_MEMBERS",
    "EXT_PATH",
    "EXT_REPORT",
    "FUNCTIONS",
    "HELD",
    "KNOWN",
    "LANDLOCKED_NO_SEAPORT",
    "MEASURED_OUTCOME_STATES",
    "PERMITTED",
    "PUBLISHERS",
    "ROLE_STANDARD",
    "SHARED_COMPETENCE",
    "TERMS_EVIDENCE",
    "TRANSNATIONAL",
    "UNMEASURED",
    "Cell",
    "DataClass",
    "Equivalent",
    "class_of",
    "dispose",
    "equivalents_for",
    "load_extension",
    "match_classes",
    "names_country",
    "no_equivalent_reason",
    "terms_for",
    "terms_verdict",
    "terms_why",
]

UNMEASURED = "UNMEASURED"

DISPOSITIONS: tuple[str, ...] = ("COVERED", "DECLARED", "ABSENT_KNOWN_EQUIVALENT",
                                 "NO_EQUIVALENT", UNMEASURED)

#: Where the class list comes from. Quoted so a reader can check it against the mandate file.
CLASS_SOURCE = ("ASIA_CHINA_FIRST_DIRECTIVE_2026-10-05.md, GLOBAL directive PART II (full global "
                "hard-data taxonomy, 12 classes / 86 sub-classes, completion-audit rows "
                "ASIA-1207..ASIA-1292) and PART III (country equivalence engine, 13 functions, "
                "ASIA-1294 and ASIA-1304..ASIA-1315)")

#: The ingestion ledger's downstream states that are a MEASURED OUTCOME. AWAITING_EXPERIMENT is
#: the one state that is not: the datum was stored and nothing has read it yet.
MEASURED_OUTCOME_STATES: frozenset[str] = frozenset({
    "WORLD_MODEL_INPUT", "CANDIDATE_INPUT", "INTERACTION_INPUT", "EXECUTION_INPUT",
    "PORTFOLIO_INPUT", "NEGATIVE_KNOWLEDGE", "RETIRED_WITH_EVIDENCE"})


# ------------------------------------------------------------------------------- the classes
@dataclass(frozen=True)
class DataClass:
    """One information class (a PART II sub-class or a homeless PART III function)."""

    key: str                       # "FX:official fixes"
    group: str                     # "FX"
    name: str                      # "official fixes"
    layer: str                     # the coverage tensor's source layer it lives in
    terms: str                     # regex matched against a pack's declarations
    cadence: str = "monthly"       # the typical cadence of the equivalent
    mandate_id: str = ""           # the completion-audit row it answers
    part: str = "II"


def _c(group: str, name: str, layer: str, terms: str, cadence: str, mid: int,
       part: str = "II") -> DataClass:
    return DataClass(key=f"{group}:{name}", group=group, name=name, layer=layer, terms=terms,
                     cadence=cadence, mandate_id=f"ASIA-{mid}", part=part)


_WAGES = (r"\bwages?\b|\bearnings\b|salar(y|ies)|labou?r cost|工资|賃金|임금|minimum wage|"
          r"compensation per employee")

#: PART II, in the directive's order, and the five homeless PART III functions after it.
CLASSES: tuple[DataClass, ...] = (
    # ---- Monetary / rates (ASIA-1207..1216)
    _c("Monetary / rates", "policy rates", "official",
       r"policy rate|\bbase rate|key rate|\bbank rate|cash rate|\bselic\b|official cash rate|"
       r"\bopr\b|monetary policy (rate|decision|statement|committee)|rate decision|alapkamat|"
       r"kamatd|ключев|基准利率|\blpr\b|政策金利|기준금리|tasa de pol[ií]tica|"
       r"national bank rate|refinancing rate|discount rate", "event", 1207),
    _c("Monetary / rates", "OMO", "official",
       r"open[- ]market|\bomo\b|公开市场|reverse repo operation|\bmlf\b", "daily", 1208),
    _c("Monetary / rates", "repo", "official",
       r"\brepo\b|repurchase|\bsofr\b|\bgc rate|回购|\bdr007\b|\br007\b|レポ", "daily", 1209),
    _c("Monetary / rates", "reserve requirements", "official",
       r"reserve requirement|required reserve|statutory reserve|\brrr\b|cash reserve ratio|"
       r"\bcrr\b|存款准备金|encaje|minimum reserve|\bsrr\b", "event", 1210),
    _c("Monetary / rates", "central-bank assets", "official",
       r"balance sheet|central[- ]bank (total )?assets|weekly statement|\bh\.4\.1\b|"
       r"monetary base|base money|資金供給|bank return|weekly financial statement|资产负债表",
       "weekly", 1211),
    _c("Monetary / rates", "liquidity operations", "official",
       r"liquidity (operation|facilit|injection|management|adjustment)|standing facilit|"
       r"deposit facilit|lending facilit|\bslf\b|\btltro|one-day and one-week deposit|流动性|"
       r"\blaf\b", "daily", 1212),
    _c("Monetary / rates", "yield curves", "official",
       r"yield curve|government bond yield|treasury (yield|rate|curve)|bond yields|"
       r"benchmark yield|(jgb|gilt|bund|ktb|ust) yields?|国债收益率|sovereign curve|"
       r"zero[- ]coupon curve|par yield", "daily", 1213),
    _c("Monetary / rates", "bank funding", "official",
       r"interbank|\blibor|\bshibor|\bhibor|\bjibor|\bklibor|\bbubor|\bwibor|\bpribor|\bestr\b|"
       r"€str|\bsonia\b|\btonar|\bcd rate|deposit rates?\b|bank funding|money market rate|"
       r"call rate|\bcorra\b|\bbbsw\b|\bnibor|\bstibor|\bcibor|\btelbor|\bmibor|\btibor|"
       r"同业拆借", "daily", 1214),
    _c("Monetary / rates", "money supply", "official",
       r"money supply|\bm[123]\b|broad money|monetary aggregate|货币供应|マネーストック|통화량|"
       r"monetary statistics|monetary survey", "monthly", 1215),
    _c("Monetary / rates", "credit", "official",
       r"credit (growth|aggregate|to the private sector)|total social financing|社会融资|"
       r"private[- ]sector credit|domestic credit|新增贷款|loan growth", "monthly", 1216),
    # ---- FX (ASIA-1217..1227)
    _c("FX", "official fixes", "official",
       r"\bfix(es|ing)?\b|reference rate|official (exchange |market )?rates?|central parity|"
       r"中间价|\bptax\b|\btrm\b|d[oó]lar observado|\bfbil\b|kurz|arfolyam|árfolyam|"
       r"indicative rate|declared exchange rate|market average rate|매매기준율|基準相場",
       "daily", 1217),
    _c("FX", "interventions", "official",
       r"intervention|外汇干预|為替介入|순거래|net fx transactions|fx (sales|purchases)|"
       r"willing-buyer|(fx|forex|dollar|currency) auction|平衡操作", "event", 1218),
    _c("FX", "reserves", "official",
       r"(fx|foreign[- ]exchange|international|official|forex|gross|currency) reserves|"
       r"外汇储备|外貨準備|외환보유|reservas internacionales|международн\w* резерв|"
       r"reserve cover|fx_reserves|\bnir\b|外匯存底", "monthly", 1219),
    _c("FX", "bank settlement/sales", "official",
       r"settlement and sales|结售汇|bank fx (settlement|flows)|fluxo cambial|fx flows|"
       r"resident fx deposits|foreign[- ]currency deposits|deposits by currency|"
       r"dollar deposits|fx turnover|interbank fx volume", "monthly", 1220),
    _c("FX", "cross-border flows", "official",
       r"balance of payments|\bbop\b|current account|capital flows|portfolio flows|\btic\b|"
       r"international transactions in securities|foreign (portfolio|investor)s? "
       r"(flows|holdings|investment)|non-?resident (share|holdings)|remittance|"
       r"対外及び対内証券|国际收支|국제수지|external sector|foreign holdings", "monthly", 1221),
    _c("FX", "forward books", "official",
       r"forward (book|position)|net forward|forward cover|outright forward|"
       r"forward points|远期结售汇", "monthly", 1222),
    _c("FX", "swaps", "official",
       r"fx swap|currency swap|swap line|swap cambial|cross-currency|swap points|"
       r"swap auction|掉期", "daily", 1223),
    _c("FX", "option activity", "institutional",
       r"fx option|currency option|option (volume|activity|open interest)|risk reversal|"
       r"implied vol", "daily", 1224),
    _c("FX", "REER/NEER", "official",
       r"\breer\b|\bneer\b|effective exchange rate|实际有效汇率|実効為替|cfets (rmb )?index|"
       r"currency basket index", "monthly", 1225),
    _c("FX", "capital controls", "official",
       r"capital control|capital account|exchange control|repatriation|surrender requirement|"
       r"\bqfii\b|parallel[- ](market|rate|exchange)|black[- ]market", "event", 1226),
    _c("FX", "carry", "official",
       r"\bcarry\b|rate differential|interest differential|forward premium|implied yield",
       "daily", 1227),
    # ---- Inflation (ASIA-1228..1233)
    _c("Inflation", "CPI", "official",
       r"\bcpi\b|consumer price|\bhicp\b|\bihpc\b|inflation (rate|print|index)|居民消费价格|"
       r"消費者物価|소비자물가|\bipca\b|\binpc\b|visitala|потребительск", "monthly", 1228),
    _c("Inflation", "PPI", "official",
       r"\bppi\b|producer price|wholesale price|\bwpi\b|生产者价格|出厂价格|企業物価|생산자물가",
       "monthly", 1229),
    _c("Inflation", "import/export prices", "official",
       r"(import|export) price|unit value index|terms of trade|輸出物価|輸入物価|수출입물가",
       "monthly", 1230),
    _c("Inflation", "wages", "official", _WAGES, "monthly", 1231),
    _c("Inflation", "commodity inflation", "official",
       r"food price|fuel price|commodity price index|energy price|petrol price|pump price|"
       r"administered price|utility (price|tariff)|electricity tariff|capped tariff|price cap",
       "monthly", 1232),
    _c("Inflation", "inflation expectations", "official",
       r"inflation expectation|expected inflation|breakeven|inflation[- ]linked|"
       r"survey of professional forecasters|\bspf\b|期待インフレ|기대인플레", "monthly", 1233),
    # ---- Growth (ASIA-1234..1240)
    _c("Growth", "GDP", "official",
       r"\bgdp\b|gross domestic product|national accounts|国内生产总值|国内総生産|국내총생산|"
       r"\bpib\b|\bbip\b|economic activity index|\bigae\b|\bibc-br\b|\bimacec\b|"
       r"monthly economic activity", "quarterly", 1234),
    _c("Growth", "industrial output", "official",
       r"industrial (production|output)|manufacturing (output|production)|工业增加值|鉱工業|"
       r"산업생산|produção industrial|producci[oó]n industrial|factory output", "monthly", 1235),
    _c("Growth", "PMIs", "official", r"\bpmi\b|purchasing managers", "monthly", 1236),
    _c("Growth", "surveys", "official",
       r"\bsurvey\b|tankan|短観|\bifo\b|\bzew\b|\bkof\b|barometer|sentiment|"
       r"business conditions|\bbsi\b|\besi\b|confidence index", "monthly", 1237),
    _c("Growth", "utilization", "official",
       r"capacity utili[sz]ation|utili[sz]ation rate|operating rate|開工率|开工率|가동률|"
       r"\bnuci\b|稼働率", "monthly", 1238),
    _c("Growth", "production", "official",
       r"(construction|services?|tertiary|all[- ]industry) (output|activity|production)|"
       r"services production|第三次産業|服务业生产|service industries", "monthly", 1239),
    _c("Growth", "consumption", "official",
       r"consumption|household spending|private consumption|household expenditure|消費支出|"
       r"社会消费品|consumer spending", "monthly", 1240),
    # ---- Labour (ASIA-1241..1246)
    _c("Labour", "employment", "official",
       r"(?<!un)employment\b|payrolls?|\bnfp\b|labou?r force|jobs report|就业|雇用|고용|"
       r"emprego|empleo\b|\blfs\b|\bcaged\b", "monthly", 1241),
    _c("Labour", "unemployment", "official",
       r"unemployment (rate|survey|statistics)|unemployment\b(?! (insurance|benefit))|"
       r"jobless rate|失业|失業|실업|desemprego|desempleo|безработ", "monthly", 1242),
    _c("Labour", "claims", "official",
       r"jobless claims|initial claims|unemployment (insurance|benefit) claims|"
       r"claimant count|benefit recipients|\bei beneficiaries|registered unemploy",
       "weekly", 1243),
    _c("Labour", "vacancies", "official",
       r"vacanc|job openings?|\bjolts\b|job adverts|job postings|job-to-applicant|求人倍率|"
       r"구인|help wanted", "monthly", 1244),
    _c("Labour", "wages", "official", _WAGES, "monthly", 1245),
    _c("Labour", "hours worked", "official",
       r"hours worked|working hours|average (weekly )?hours|労働時間|근로시간", "monthly", 1246),
    # ---- Credit (ASIA-1247..1251)
    _c("Credit", "bank lending", "official",
       r"bank lending|loans? (to|by) |lending (to|growth|survey)|credit to (households|"
       r"businesses|corporates|private)|new loans|新增贷款|貸出|대출|cr[eé]dito bancario|"
       r"loan book|lending rate", "monthly", 1247),
    _c("Credit", "mortgage growth", "official",
       r"mortgage|home loan|housing loan|个人住房贷款|住宅ローン|주택담보|hipotec", "monthly",
       1248),
    _c("Credit", "corporate credit", "official",
       r"corporate (credit|bond|debt|loan)|business (lending|credit)|credit spread|"
       r"high[- ]yield|\bsme lending|commercial paper|企业债|社債|회사채", "monthly", 1249),
    _c("Credit", "defaults", "official",
       r"\bdefaults?\b|non[- ]performing|\bnpls?\b|bankrupt|insolvenc|delinquen|不良贷款|倒産|"
       r"부도|impago|arrears", "monthly", 1250),
    _c("Credit", "household leverage", "official",
       r"household (debt|leverage|credit|indebtedness)|debt service ratio|consumer credit|"
       r"家計債務|가계부채|居民杠杆", "quarterly", 1251),
    # ---- Fiscal (ASIA-1252..1258)
    _c("Fiscal", "budgets", "official",
       r"budget|fiscal (balance|position|deficit|outturn|statement|data)|government finance|"
       r"public finance|国家预算|予算|예산|presupuesto|orçamento", "monthly", 1252),
    _c("Fiscal", "spending", "official",
       r"(government|public|fiscal|central government) (spending|expenditure|outlays)|"
       r"一般公共预算支出|歳出|재정지출", "monthly", 1253),
    _c("Fiscal", "tax receipts", "official",
       r"tax (receipts|revenue|collection)|revenue (collection|authority)|customs revenue|"
       r"royalt|\bvat (receipts|collection)|税收|税収|세수|recaudaci[oó]n|arrecada",
       "monthly", 1254),
    _c("Fiscal", "issuance", "official",
       r"issuance|bond (supply|calendar|issue)|borrowing (plan|programme|requirement)|"
       r"refunding|gross financing|发行|발행|emisi[oó]n", "event", 1255),
    _c("Fiscal", "auctions", "official",
       r"(bond|bill|treasury|t-bill|gilt|bund|sukuk|government securities|debt|ktb|jgb|bono|"
       r"cete|obligation)s? (auction|tender)|auction (calendar|results)|入札|국고채 입찰|subasta|"
       r"leil[aã]o|aukci|bid-to-cover", "event", 1256),
    _c("Fiscal", "public debt", "official",
       r"public debt|government debt|national debt|debt (stock|statistics|bulletin|"
       r"management office)|sovereign debt|\bdmo\b|政府債務|국가채무|deuda p[uú]blica|"
       r"external debt|holder structure|state debt", "monthly", 1257),
    _c("Fiscal", "fiscal calendars", "official",
       r"fiscal calendar|budget (calendar|speech|day|statement)|budget cycle|"
       r"tax (deadline|payment date|calendar)|appropriation", "event", 1258),
    # ---- Trade (ASIA-1259..1266)
    _c("Trade", "imports", "official", r"import|进口|輸入|수입|importa", "monthly", 1259),
    _c("Trade", "exports", "official", r"export|出口|輸出|수출|exporta", "monthly", 1260),
    _c("Trade", "quantities", "official",
       r"(export|import|trade|shipment)s? (volume|tonnage|quantit)|tonnage|cargo volume",
       "monthly", 1261),
    _c("Trade", "values", "official",
       r"(export|import|trade) (value|values|receipts|earnings)|trade balance|"
       r"merchandise trade|foreign trade|贸易差额|貿易収支|무역수지|balanza comercial|"
       r"balança comercial", "monthly", 1262),
    _c("Trade", "partners", "official",
       r"by (country|destination|origin|partner)|\bpartners?\b|direction of trade|国别|国・地域別",
       "monthly", 1263),
    _c("Trade", "customs ports", "official",
       r"customs|海关|税関|관세|aduana|alf[aâ]ndega|douane|border post|port of entry|"
       r"20-?day|10-?day|1st-20th|上中旬", "monthly", 1264),
    _c("Trade", "product classes", "official",
       r"\bhs ?\d|harmoni[sz]ed system|by product|commodity breakdown|by commodity|"
       r"product class|\bsitc\b|semiconductor exports|by item", "monthly", 1265),
    _c("Trade", "shipping mode", "official",
       r"by (mode|transport)|seaborne|air cargo|rail freight|road freight|by sea|by air|"
       r"shipping mode", "monthly", 1266),
    # ---- Commodities (ASIA-1267..1274)
    _c("Commodities", "physical production", "physical_economy",
       r"(crude|oil|gas|copper|gold|iron ore|coal|mine|mining|mineral|cocoa|coffee|crop|grain|"
       r"wheat|corn|rice|sugar|palm oil|cpo|lng|steel|aluminium|nickel|zinc|lithium|cotton|"
       r"methanol)\w* (production|output)|production by field|harvest|crop (estimate|report)|"
       r"产量|生産量", "monthly", 1267),
    _c("Commodities", "inventory", "physical_economy",
       r"inventor|stockpile|(oil|crude|metal|grain|cereal|coal|lng|gas|warehouse|commercial|"
       r"ending|copper|sugar|palm oil|cpo) stocks|库存|在庫|재고|existencias|estoques",
       "weekly", 1268),
    _c("Commodities", "delivery", "physical_economy",
       r"deliver|交割|受渡|entrega|liftings?\b|loadings?\b|cargo programme|nomination",
       "monthly", 1269),
    _c("Commodities", "basis", "institutional",
       r"\bbasis\b|physical premium|(gold|silver|metal|bullion|oil|crude|grain|import|local|"
       r"sge) premium|premium (to|over|vs)|discount to|升贴水|基差|\bosp\b|"
       r"official selling price|price differential|farmgate price", "daily", 1270),
    _c("Commodities", "futures curves", "institutional",
       r"futures (prices?|curves?|settlements?|settlement prices|term structure)|"
       r"futures\b.{0,20}settlement|settlement prices?|forward curve|term structure|"
       r"contango|backwardation|期货(价格|结算)|先物価格|implied path", "daily", 1271),
    _c("Commodities", "warehouse receipts", "institutional",
       r"warehouse receipt|仓单|\bwarrants?\b|cancelled warrant|registered stocks|"
       r"certified stock|倉荷証券", "daily", 1272),
    _c("Commodities", "member positions", "institutional",
       r"member (rank|position|holding)|持仓排名|positions? by (member|participant|"
       r"investor type|trader)|open interest by|commitments of traders|\bcot\b|\bcotr\b|"
       r"미결제약정|建玉|participant[- ]wise|large trader|position report|trader category",
       "daily", 1273),
    _c("Commodities", "exports/imports", "physical_economy",
       r"(crude|oil|gas|lng|copper|gold|iron ore|coal|cocoa|coffee|grain|wheat|corn|soy|sugar|"
       r"palm oil|potash|phosphate|cotton|banana|cacao|metal|mineral|diamond|uranium|methanol|"
       r"cereal)\w* (export|import|shipment|re-export)|(export|import)s? of (crude|oil|gas|lng|"
       r"copper|gold|ore|coal|cocoa|coffee|grain|soy)", "monthly", 1274),
    # ---- Housing (ASIA-1275..1280)
    _c("Housing", "permits", "official",
       r"building permit|building approval|construction permit|planning (permission|approval)|"
       r"建築確認|건축허가|licencias de construcci", "monthly", 1275),
    _c("Housing", "starts", "official",
       r"housing starts|dwelling starts|new (housing|dwelling) construction|住宅着工|新开工|"
       r"착공|housing construction", "monthly", 1276),
    _c("Housing", "sales", "official",
       r"(home|house|housing|property|residential) (sales|transactions)|"
       r"commercial housing sales|商品房销售|住宅販売|주택매매|real estate transactions",
       "monthly", 1277),
    _c("Housing", "inventories", "official",
       r"housing (inventory|stock)|unsold (homes|housing|units)|商品房待售|months of supply|"
       r"vacant (homes|dwellings)|housing vacanc", "monthly", 1278),
    _c("Housing", "prices", "official",
       r"(house|home|property|housing|residential( property)?|real estate) prices?|\bhpi\b|"
       r"房价|住宅価格|주택가격|70[- ]city|rent (index|price)", "monthly", 1279),
    _c("Housing", "mortgages", "official",
       r"mortgage|home loan|housing loan|住宅ローン|주택담보|房贷|hipotec|"
       r"financiamento imobili", "monthly", 1280),
    # ---- Consumer (ASIA-1281..1286)
    _c("Consumer", "retail sales", "official",
       r"retail (sales|trade)|社会消费品零售|商業販売|소매판매|vendas no varejo|"
       r"ventas minoristas|department store sales", "monthly", 1281),
    _c("Consumer", "card payments", "official",
       r"card (spending|payments?|transactions?)|debit card|credit card|electronic card|"
       r"\bupi\b|\bpix\b|payment (system|statistics|volume)|pos transaction|mobile money|"
       r"e-?money|\bnpci\b", "monthly", 1282),
    _c("Consumer", "tourism", "official",
       r"touris|visitor arrivals|\barrivals\b|bednight|hotel occupancy|travel receipts|入境|"
       r"訪日|관광", "monthly", 1283),
    _c("Consumer", "mobility", "official",
       r"mobility|traffic|passenger|ridership|congestion|\bmetro\b|subway|air traffic|"
       r"footfall", "daily", 1284),
    _c("Consumer", "vehicle sales", "official",
       r"(car|auto|vehicle|motor vehicle|automobile|passenger car|truck) (sales|registrations)|"
       r"new car registrations|汽车销量|新車販売|자동차 판매|\bsiam\b|\bcaam\b|\bcpca\b|"
       r"\bsmmt\b|\bkba\b|fenabrave|vfacts|anfac", "monthly", 1285),
    _c("Consumer", "search behavior", "app_ecosystem",
       r"search (trend|volume|index|interest|behaviou?r)|google trends|baidu index|百度指数|"
       r"naver datalab|네이버 데이터랩|wordstat", "daily", 1286),
    # ---- Business (ASIA-1287..1292)
    _c("Business", "confidence", "official",
       r"business (confidence|sentiment|climate|conditions|expectations)|tankan|短観|\bifo\b|"
       r"\bzew\b|\bbsi\b|business survey|\bkof\b|economic barometer|\besi\b", "monthly", 1287),
    _c("Business", "hiring", "official",
       r"hiring|\bhires\b|recruitment|job (adverts|ads|postings)|new hires|"
       r"employment intentions|foreign employment", "monthly", 1288),
    _c("Business", "capex", "official",
       r"capex|capital (expenditure|investment|spending)|business investment|"
       r"fixed[- ]asset investment|固定资产投资|設備投資|설비투자|machinery orders|機械受注|"
       r"core orders|investment intentions", "monthly", 1289),
    _c("Business", "tenders", "official",
       r"\btenders?\b|procurement|public contract|government contracts|招标|조달|licitaci|"
       r"licita[cç]", "event", 1290),
    _c("Business", "permits", "official",
       r"business (permit|licen[cs]e|registration)|company registrations|"
       r"new (business|firm|company) (registrations|formation)|business formation|"
       r"incorporations|mining licen[cs]e|exploration licen[cs]e|licensing round|concession",
       "monthly", 1291),
    _c("Business", "purchasing activity", "official",
       r"purchasing activity|new orders|orders received|machinery orders|order book|受注|"
       r"durable goods|factory orders", "monthly", 1292),
    # ---- PART III functions with no PART II home
    _c("Part III", "FX positioning", "institutional",
       r"(fx|currency|forex) (position|positioning|futures position)|traders in financial "
       r"futures|\btff\b|click ?365|くりっく|retail fx position|cot_currency", "weekly", 1304,
       part="III"),
    _c("Part III", "retail positioning", "retail_ecology",
       r"retail (position|investor|trader|leverage|flow|account|sentiment)|"
       r"margin (balance|debt|trading|financing|loan)|融资融券|信用取引|신용융자|예탁금|"
       r"investor accounts|new (investor|brokerage) accounts|individual investors|"
       r"client category", "daily", 1305, part="III"),
    _c("Part III", "investor flows", "institutional",
       r"investor (type|flows|category)|by investor|foreign (investor|net) (buying|selling|"
       r"flows|net buy)|net (buy|purchases) by|northbound|southbound|stock connect|"
       r"connect flows|\bfpi\b|\bfii\b|\bdii\b|fund flows|etf flows|by nationality|"
       r"投資部門別|투자자별|外资|foreign participation", "daily", 1310, part="III"),
    _c("Part III", "shipping", "physical_economy",
       r"\bports?\b|shipping|freight|vessel|container|\bteu\b|tanker|bulk carrier|canal|"
       r"strait|chokepoint|throughput|portwatch|\bais\b|baltic (dry|index)|港口|港湾|해운|"
       r"navigation", "daily", 1312, part="III"),
    _c("Part III", "energy", "physical_economy",
       r"electricity|power (generation|demand|load|price)|\bgrid\b|load[- ]shedding|\boil\b|"
       r"crude|natural gas|\blng\b|refiner|\bfuel\b|\bcoal\b|energy|petroleum|hydro|"
       r"reservoir|\bjodi\b|\beia\b|発電|发电|전력", "weekly", 1313, part="III"),
)

CLASS_KEYS: tuple[str, ...] = tuple(c.key for c in CLASSES)
_BY_KEY: dict[str, DataClass] = {c.key: c for c in CLASSES}
_COMPILED: dict[str, re.Pattern[str]] = {c.key: re.compile(c.terms, re.IGNORECASE)
                                         for c in CLASSES}
#: Words that VETO a class even when its terms match: a gold auction "fix" is not an FX fix, and
#: an equity closing auction is not one either.
_EXCLUDE: dict[str, re.Pattern[str]] = {
    "FX:official fixes": re.compile(r"\b(gold|silver|lbma|platinum|palladium|closing (call )?"
                                    r"auction|libor|euribor|estr|sonia)\b", re.IGNORECASE),
}

#: PART III's thirteen functions -> the class keys that answer each. The directive's own worked
#: example (central-bank liquidity) is the first row.
FUNCTIONS: dict[str, tuple[str, ...]] = {
    "central-bank liquidity": ("Monetary / rates:OMO", "Monetary / rates:liquidity operations",
                               "Monetary / rates:central-bank assets"),
    "FX positioning": ("Part III:FX positioning",),
    "retail positioning": ("Part III:retail positioning",),
    "futures positioning": ("Commodities:member positions",),
    "commodity inventories": ("Commodities:inventory", "Commodities:warehouse receipts"),
    "customs": ("Trade:customs ports",),
    "physical premia": ("Commodities:basis",),
    "investor flows": ("Part III:investor flows", "FX:cross-border flows"),
    "derivatives": ("FX:option activity", "Commodities:futures curves", "FX:swaps"),
    "shipping": ("Part III:shipping", "Trade:shipping mode"),
    "energy": ("Part III:energy",),
    "procurement": ("Business:tenders",),
    "search behavior": ("Consumer:search behavior",),
}

#: The CORE LAW's three worked questions, each pinned to the class that answers it.
CORE_LAW_ANCHORS: dict[str, str] = {
    "SHFE member rankings -> participant-positioning / exchange-member / open-interest":
        "Commodities:member positions",
    "SGE physical gold premium -> physical-vs-global premium / auction / delivery":
        "Commodities:basis",
    "SAFE FX settlement/sales -> BOP / bank FX flow / intervention / reserves":
        "FX:bank settlement/sales",
}


def class_of(key: str) -> DataClass | None:
    return _BY_KEY.get(key)


# ------------------------------------------------------------------------------- countries
#: ISO-2 -> English name and the stems a declaration uses for it ("kuwait" also reads "Kuwaiti").
#: Used ONLY to attribute a row of a MULTI-country pack to the country it names.
COUNTRY_NAMES: dict[str, tuple[str, ...]] = {
    "ae": ("United Arab Emirates", "uae", "emirat", "dubai", "abu dhabi", "fujairah"),
    "af": ("Afghanistan", "afghan"), "am": ("Armenia", "armenia"), "ao": ("Angola", "angola"),
    "ar": ("Argentina", "argentin"), "at": ("Austria", "austria"),
    "au": ("Australia", "australia"), "az": ("Azerbaijan", "azerbaijan", "azeri"),
    "bd": ("Bangladesh", "bangladesh"), "be": ("Belgium", "belgi"),
    "bf": ("Burkina Faso", "burkina"), "bg": ("Bulgaria", "bulgaria"),
    "bh": ("Bahrain", "bahrain"), "bj": ("Benin", "benin"), "bn": ("Brunei", "brunei"),
    "bo": ("Bolivia", "bolivia"), "br": ("Brazil", "brazil", "brasil"),
    "bt": ("Bhutan", "bhutan"), "bw": ("Botswana", "botswana"), "by": ("Belarus", "belarus"),
    "ca": ("Canada", "canad"), "cd": ("DR Congo", "congo", "drc"),
    "ch": ("Switzerland", "swiss", "switzerland"), "ci": ("Cote d'Ivoire", "ivoire", "ivory"),
    "cl": ("Chile", "chile"), "cn": ("China", "china", "chinese", "prc"),
    "co": ("Colombia", "colombia"), "cr": ("Costa Rica", "costa rica"),
    "cv": ("Cabo Verde", "cabo verde", "cape verde"), "cy": ("Cyprus", "cyprus", "cypriot"),
    "cz": ("Czechia", "czech"), "de": ("Germany", "german", "bundes"),
    "dj": ("Djibouti", "djibouti"), "dk": ("Denmark", "denmark", "danish"),
    "dz": ("Algeria", "algeria"), "ec": ("Ecuador", "ecuador"), "ee": ("Estonia", "estonia"),
    "eg": ("Egypt", "egypt"), "er": ("Eritrea", "eritrea"), "es": ("Spain", "spain", "spanish"),
    "et": ("Ethiopia", "ethiopia"), "fi": ("Finland", "finland", "finnish"),
    "fj": ("Fiji", "fiji"), "fr": ("France", "france", "french"),
    "gb": ("United Kingdom", "united kingdom", "britain", "british", "england"),
    "ge": ("Georgia", "georgia"), "gh": ("Ghana", "ghana"), "gm": ("Gambia", "gambia"),
    "gn": ("Guinea", "guinea"), "gr": ("Greece", "greece", "greek"),
    "gt": ("Guatemala", "guatemala"), "gw": ("Guinea-Bissau", "bissau"),
    "gy": ("Guyana", "guyana"), "hk": ("Hong Kong", "hong kong"),
    "hn": ("Honduras", "hondura"), "hr": ("Croatia", "croatia"), "hu": ("Hungary", "hungar"),
    "id": ("Indonesia", "indonesia"), "ie": ("Ireland", "ireland", "irish"),
    "il": ("Israel", "israel"), "in": ("India", "india"), "iq": ("Iraq", "iraq"),
    "ir": ("Iran", "iran"), "is": ("Iceland", "iceland"), "it": ("Italy", "ital"),
    "jo": ("Jordan", "jordan"), "jp": ("Japan", "japan"), "ke": ("Kenya", "kenya"),
    "kg": ("Kyrgyzstan", "kyrgyz"), "kh": ("Cambodia", "cambodia"),
    "kr": ("South Korea", "korea"), "kw": ("Kuwait", "kuwait"),
    "kz": ("Kazakhstan", "kazakh"), "la": ("Laos", "lao"), "lb": ("Lebanon", "leban"),
    "lk": ("Sri Lanka", "sri lanka"), "lr": ("Liberia", "liberia"),
    "lt": ("Lithuania", "lithuania"), "lu": ("Luxembourg", "luxembourg"),
    "lv": ("Latvia", "latvia"), "ly": ("Libya", "libya"), "ma": ("Morocco", "morocc"),
    "ml": ("Mali", "mali"), "mm": ("Myanmar", "myanmar", "burma"),
    "mn": ("Mongolia", "mongolia"), "mo": ("Macao", "macao", "macau"),
    "mr": ("Mauritania", "mauritania"), "mt": ("Malta", "malta", "maltese"),
    "mv": ("Maldives", "maldiv"), "mx": ("Mexico", "mexic"), "my": ("Malaysia", "malaysia"),
    "mz": ("Mozambique", "mozambi", "moçambi"), "na": ("Namibia", "namibia"),
    "nc": ("New Caledonia", "caledonia"), "ne": ("Niger", "niger"),
    "ng": ("Nigeria", "nigeria"), "ni": ("Nicaragua", "nicaragua"),
    "nl": ("Netherlands", "netherlands", "dutch"), "no": ("Norway", "norw"),
    "np": ("Nepal", "nepal"), "nz": ("New Zealand", "new zealand"), "om": ("Oman", "oman"),
    "pa": ("Panama", "panam"), "pe": ("Peru", "peru"), "pg": ("Papua New Guinea", "papua"),
    "ph": ("Philippines", "philippin"), "pk": ("Pakistan", "pakistan"),
    "pl": ("Poland", "poland", "polish"), "pt": ("Portugal", "portug"), "qa": ("Qatar", "qatar"),
    "ro": ("Romania", "romania"), "rs": ("Serbia", "serbia"), "ru": ("Russia", "russia"),
    "sa": ("Saudi Arabia", "saudi"), "sb": ("Solomon Islands", "solomon"),
    "sd": ("Sudan", "sudan"), "se": ("Sweden", "swed"), "sg": ("Singapore", "singapore"),
    "si": ("Slovenia", "slovenia"), "sk": ("Slovakia", "slovak"),
    "sl": ("Sierra Leone", "sierra leone"), "sn": ("Senegal", "senegal"),
    "so": ("Somalia", "somali"), "sr": ("Suriname", "surinam"),
    "sv": ("El Salvador", "salvador"), "sy": ("Syria", "syria"), "tg": ("Togo", "togo"),
    "th": ("Thailand", "thai"), "tj": ("Tajikistan", "tajik"), "tl": ("Timor-Leste", "timor"),
    "tm": ("Turkmenistan", "turkmen"), "tn": ("Tunisia", "tunisia"),
    "tr": ("Turkiye", "turk"), "tt": ("Trinidad and Tobago", "trinidad"),
    "tw": ("Taiwan", "taiwan"), "tz": ("Tanzania", "tanzania"), "ua": ("Ukraine", "ukrain"),
    "ug": ("Uganda", "uganda"), "us": ("United States", "united states", "u.s."),
    "uz": ("Uzbekistan", "uzbek"), "ve": ("Venezuela", "venezuela"),
    "vn": ("Vietnam", "vietnam", "viet nam"), "vu": ("Vanuatu", "vanuatu"),
    "ws_to": ("Samoa and Tonga", "samoa", "tonga"), "ye": ("Yemen", "yemen"),
    "za": ("South Africa", "south africa"), "zm": ("Zambia", "zambia"),
    "zw": ("Zimbabwe", "zimbabwe"),
}


def names_country(text: str, cc: str) -> bool:
    """True when a declaration names this country -- by a name stem, or by the country's code as
    a token of a series key (`SN_CPI`, `CCA_KG_TRADE`, `GULF_QA_TRADE`)."""
    low = str(text or "").lower()
    stems = COUNTRY_NAMES.get(cc, ())[1:]
    if any(re.search(r"\b" + re.escape(s), low) for s in stems):
        return True
    return bool(re.search(r"(^|[^A-Za-z])" + re.escape(cc.upper()) + r"_", str(text or "")))


#: The twenty euro-area members the `ea` pack declares, plus Bulgaria (euro since 2026-01-01).
EURO_MEMBERS: frozenset[str] = frozenset({
    "at", "be", "bg", "cy", "de", "ee", "es", "fi", "fr", "gr", "hr", "ie", "it", "lt", "lu",
    "lv", "mt", "nl", "pt", "si", "sk"})
#: Officially dollarized: no domestic currency, so no domestic policy rate or fix.
DOLLARIZED: frozenset[str] = frozenset({"ec", "sv", "pa"})
#: Landlocked with no seaport (the Caspian littoral -- KZ, TM, AZ -- and the Rhine/Danube
#: economies with inland ports are deliberately NOT here).
LANDLOCKED_NO_SEAPORT: frozenset[str] = frozenset({
    "af", "am", "bf", "bt", "bw", "by", "et", "kg", "la", "ml", "mn", "ne", "np", "tj", "ug",
    "uz", "zm", "zw"})

#: A MULTI-COUNTRY pack whose declaration of these classes is a SHARED COMPETENCE of every
#: jurisdiction it answers for: the ECB's rate, operations and reference rate ARE each euro
#: member's local equivalent. Every other multi-country row is credited only to the country it
#: names, never to the whole pack.
SHARED_COMPETENCE: dict[str, frozenset[str]] = {
    "ea": frozenset({"Monetary / rates:policy rates", "Monetary / rates:OMO",
                     "Monetary / rates:repo", "Monetary / rates:reserve requirements",
                     "Monetary / rates:central-bank assets",
                     "Monetary / rates:liquidity operations", "Monetary / rates:bank funding",
                     "Monetary / rates:money supply", "FX:official fixes", "FX:carry"}),
}

#: The rules under which a class has NO local equivalent, with the reason. Order matters only for
#: the message; any rule that fires makes the cell NO_EQUIVALENT unless a pack declares it.
_NO_EQ: tuple[tuple[frozenset[str], frozenset[str], str], ...] = (
    (DOLLARIZED,
     frozenset({"Monetary / rates:policy rates", "Monetary / rates:OMO", "FX:official fixes",
                "FX:interventions", "FX:carry", "FX:forward books"}),
     "officially dollarized: no domestic currency or policy rate -- the Federal Reserve's "
     "rate and the US dollar are the operative ones"),
    (EURO_MEMBERS, frozenset({"FX:interventions"}),
     "euro member: FX intervention is a euro-area competence, there is no national one"),
    (LANDLOCKED_NO_SEAPORT, frozenset({"Part III:shipping"}),
     "landlocked with no seaport: the equivalent is a neighbour's transit port, filed under "
     "that country"),
)


def no_equivalent_reason(cc: str, key: str) -> str:
    for members, keys, why in _NO_EQ:
        if cc in members and key in keys:
            return why
    return ""


# ------------------------------------------------------------------------------- equivalents
@dataclass(frozen=True)
class Equivalent:
    """One public functional equivalent of one class in one country."""

    country: str
    key: str
    source_id: str
    series: str
    cadence: str
    publisher: str
    url: str
    endpoints: tuple[str, ...] = ()
    tier: str = "named"            # named | transnational | role | pack
    #: NEVER "PUBLIC" BY DEFAULT. Whether an endpoint may be fetched is decided per URL by
    #: `TERMS_EVIDENCE` (a verbatim permitting clause from the publisher's own terms page); this
    #: label only describes a row that carries no endpoint.
    access: str = "UNVERIFIED"
    note: str = ""

    def to_json(self) -> dict[str, Any]:
        permitted = [u for u in self.endpoints if terms_verdict(u) == PERMITTED]
        held = [{"url": u, "verdict": terms_verdict(u), "why": terms_why(u)}
                for u in self.endpoints if terms_verdict(u) != PERMITTED]
        access = self.access
        if self.endpoints:
            access = PERMITTED if not held else (HELD if not permitted else "PARTIAL")
        terms: list[dict[str, str]] = []
        for u in self.endpoints:
            for t in terms_for(u):
                if dict(t) not in terms:
                    terms.append(dict(t))
        return {"source_id": self.source_id, "series": self.series, "cadence": self.cadence,
                "publisher": self.publisher, "url": self.url, "endpoints": permitted,
                "held_endpoints": held, "terms": terms[:4],
                "tier": self.tier, "access": access, "note": self.note}


# ------------------------------------------------------------------------------- terms
PERMITTED = "PERMITTED"
HELD = "HELD"

#: THE TERMS EVIDENCE. An endpoint is handed to the acquirer ONLY when every rule whose `prefix`
#: it starts with quotes, VERBATIM, a clause from the publisher's own terms page that permits the
#: use, and says PERMITTED. A URL no rule covers is HELD -- fail closed: "it is a government site"
#: or "it is a central bank" is an inference, and no inference opens a fetch. Read 2026-10-06.
TERMS_EVIDENCE: tuple[Mapping[str, str], ...] = (
    {"prefix": "https://data.bis.org/",
     "terms_url": "https://data.bis.org/help/legal",
     "terms_quote": ("The use of the statistics is unrestricted, provided that: [...] if the "
                     "statistics are reproduced, the BIS must be cited in your publication or "
                     "product as the source of the statistics [...] if the statistics will be "
                     "used in a commercial publication or product, their inclusion in the "
                     "publication or product will not result in any additional charge to "
                     "subscribers or other users"),
     "verdict": PERMITTED, "checked_at": "2026-10-06"},
    {"prefix": "https://data-api.ecb.europa.eu/",
     "terms_url": ("https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_"
                   "framework/html/usage_policy.en.html"),
     "terms_quote": ("The ESCB subscribes to a policy of free access and free reuse regarding "
                     "its publicly released statistics, subject to the conditions described "
                     "below. [...] All publicly available ESCB statistics may be reused free of "
                     "charge on the condition that the source is quoted (e.g. \"Source: ECB "
                     "statistics.\") and that the statistics (including metadata) are not "
                     "modified."),
     "verdict": PERMITTED, "checked_at": "2026-10-06"},
    # The same policy: "The right of free reuse does not apply to third-party data without a prior
    # permission from the originator." HICP is Eurostat's, so it also needs Eurostat's own clause.
    {"prefix": "https://data-api.ecb.europa.eu/service/data/ICP/",
     "terms_url": "https://ec.europa.eu/eurostat/about-us/policies/copyright",
     "terms_quote": ("Eurostat has a policy of encouraging free re-use of its data, both for "
                     "non-commercial and commercial purposes. All statistical data, metadata, "
                     "content of web pages or other dissemination tools, official publications "
                     "and other documents published on its website, with the exceptions listed "
                     "below, can be reused without any payment or written licence provided "
                     "that: - the source is indicated as Eurostat;"),
     "verdict": PERMITTED, "checked_at": "2026-10-06"},
    {"prefix": "https://www.cftc.gov/",
     "terms_url": "https://www.cftc.gov/webpolicy/index.htm",
     "terms_quote": ("Government information at the CFTC website is in the public domain. "
                     "Public domain information may be freely distributed and copied, but it is "
                     "requested that in any subsequent use the CFTC be given appropriate "
                     "acknowledgement."),
     "verdict": PERMITTED, "checked_at": "2026-10-06"},
    {"prefix": "https://www.eia.gov/",
     "terms_url": "https://www.eia.gov/about/copyrights_reuse.php",
     "terms_quote": ("U.S. government publications are in the public domain and are not subject "
                     "to copyright protection. [...] You may use and/or distribute any of our "
                     "data, files, databases, reports, graphs, charts, and other information "
                     "products that are on our website or that you receive through our email "
                     "distribution service."),
     "verdict": PERMITTED, "checked_at": "2026-10-06"},
    {"prefix": "https://home.treasury.gov/",
     "terms_url": "https://home.treasury.gov/subfooter/site-policies-and-notices",
     "terms_quote": ("(none found: the site-policies page and the linked privacy policy carry no "
                     "copyright, public-domain or reuse sentence, and /subfooter/site-policies-"
                     "and-notices/copyright-and-use-information returns 404)"),
     "verdict": HELD, "checked_at": "2026-10-06"},
)


def terms_for(url: str) -> list[Mapping[str, str]]:
    """Every terms rule that governs `url`; all of them must permit."""
    u = str(url or "")
    return [t for t in TERMS_EVIDENCE if u.startswith(t["prefix"])]


def terms_verdict(url: str) -> str:
    """PERMITTED only when at least one rule covers the URL and every covering rule permits."""
    rules = terms_for(url)
    return PERMITTED if rules and all(t["verdict"] == PERMITTED for t in rules) else HELD


def terms_why(url: str) -> str:
    rules = terms_for(url)
    if not rules:
        return "no terms evidence on file for this URL: HELD (fail closed, never inferred)"
    bad = [t for t in rules if t["verdict"] != PERMITTED]
    return ("held by " + "; ".join(f"{t['terms_url']}: {t['terms_quote']}" for t in bad)
            if bad else "permitted by " + ", ".join(t["terms_url"] for t in rules))


def _k(cc: str, key: str, sid: str, series: str, cadence: str, publisher: str, url: str,
       *endpoints: str, access: str = "UNVERIFIED", note: str = "") -> Equivalent:
    return Equivalent(country=cc, key=key, source_id=sid, series=series, cadence=cadence,
                      publisher=publisher, url=url, endpoints=tuple(endpoints), tier="named",
                      access=access, note=note)


_CFTC_TFF = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
_CFTC_DIS = "https://www.cftc.gov/dea/newcot/f_disagg.txt"
_MP = "Commodities:member positions"
_BASIS = "Commodities:basis"
_FIX = "FX:official fixes"

#: NAMED EQUIVALENTS. Every one is a public dataset its publisher actually issues; an endpoint is
#: given only where it serves a dated file the acquirer can parse, otherwise the url is the
#: publisher's data page and the row is a discovery for the scouts, not for the acquirer.
KNOWN: tuple[Equivalent, ...] = (
    # ---- the CORE LAW's first question: participant positioning (SHFE member rankings)
    _k("cn", _MP, "shfe_member_rankings", "SHFE/DCE/ZCE/INE daily member volume and open-"
       "interest rankings (成交持仓排名)", "daily", "Shanghai Futures Exchange",
       "https://www.shfe.com.cn"),
    _k("us", _MP, "cftc_cot_disaggregated", "CFTC Commitments of Traders, disaggregated "
       "futures-only", "weekly", "CFTC", "https://www.cftc.gov", _CFTC_DIS),
    _k("gb", _MP, "lme_cotr", "LME Commitments of Traders report", "weekly",
       "London Metal Exchange", "https://www.lme.com", access="PUBLIC_WITH_TERMS"),
    _k("jp", _MP, "jpx_open_interest_by_participant", "JPX open interest by trading "
       "participant (取引参加者別建玉)", "weekly", "Japan Exchange Group", "https://www.jpx.co.jp"),
    _k("kr", _MP, "krx_derivatives_positions", "KRX futures/options open interest by investor "
       "type (투자자별 미결제약정)", "daily", "Korea Exchange", "http://data.krx.co.kr"),
    _k("in", _MP, "nse_participant_wise_oi", "NSE participant-wise open interest", "daily",
       "National Stock Exchange of India", "https://www.nseindia.com"),
    _k("br", _MP, "b3_oi_by_investor_type", "B3 open interest by investor type", "daily", "B3",
       "https://www.b3.com.br"),
    _k("de", _MP, "eex_mifid_position_report", "EEX MiFID II weekly commitments of traders",
       "weekly", "European Energy Exchange", "https://www.eex.com"),
    _k("fr", _MP, "euronext_commodity_cot", "Euronext MiFID II commodity position report",
       "weekly", "Euronext", "https://live.euronext.com"),
    _k("nl", _MP, "ice_endex_cot", "ICE Endex MiFID II commitments of traders", "weekly",
       "ICE Endex", "https://www.ice.com/endex", access="PUBLIC_WITH_TERMS"),
    # ---- the CORE LAW's second question: physical-vs-global premium (SGE premium)
    _k("cn", _BASIS, "sge_premium", "SGE Au99.99 vs London gold (the SGE premium)", "daily",
       "Shanghai Gold Exchange", "https://www.sge.com.cn"),
    _k("in", _BASIS, "ibja_gold_rate", "IBJA daily gold reference rates vs international",
       "daily", "India Bullion and Jewellers Association", "https://ibjarates.com"),
    _k("tr", _BASIS, "borsa_istanbul_precious_metals", "Borsa Istanbul precious-metals market "
       "gold price vs London", "daily", "Borsa Istanbul", "https://www.borsaistanbul.com"),
    _k("gb", _BASIS, "lbma_auction_prices", "LBMA gold and silver auction prices", "daily",
       "LBMA", "https://www.lbma.org.uk", access="PUBLIC_WITH_TERMS"),
    # ---- the CORE LAW's third question: BOP / bank FX flow (SAFE settlement/sales)
    _k("cn", "FX:bank settlement/sales", "safe_bank_fx_settlement", "SAFE banks' FX settlement "
       "and sales on behalf of clients (银行结售汇)", "monthly", "State Administration of "
       "Foreign Exchange", "https://www.safe.gov.cn"),
    _k("br", "FX:bank settlement/sales", "bcb_fluxo_cambial", "BCB FX flows (fluxo cambial)",
       "weekly", "Banco Central do Brasil", "https://www.bcb.gov.br"),
    _k("kr", "FX:bank settlement/sales", "bok_resident_fx_deposits", "BoK residents' FX "
       "deposits", "monthly", "Bank of Korea", "https://ecos.bok.or.kr"),
    _k("jp", "FX:interventions", "mof_fx_intervention", "MoF foreign-exchange intervention "
       "operations (外国為替平衡操作の実施状況)", "monthly", "Ministry of Finance Japan",
       "https://www.mof.go.jp"),
    _k("ch", "FX:interventions", "snb_fx_interventions", "SNB foreign-currency purchases and "
       "sales", "quarterly", "Swiss National Bank", "https://data.snb.ch"),
    _k("in", "FX:interventions", "rbi_fx_purchases_sales", "RBI sale/purchase of foreign "
       "currency (RBI Bulletin)", "monthly", "Reserve Bank of India", "https://www.rbi.org.in"),
    _k("kr", "FX:interventions", "bok_net_fx_transactions", "MOEF/BoK net FX transactions "
       "(외환당국 순거래)", "quarterly", "Bank of Korea", "https://www.bok.or.kr"),
    _k("in", "FX:forward books", "rbi_forward_book", "RBI net forward position (RBI Bulletin)",
       "monthly", "Reserve Bank of India", "https://www.rbi.org.in"),
    _k("br", "FX:swaps", "bcb_swap_cambial", "BCB FX swap auctions and outstanding stock",
       "daily", "Banco Central do Brasil", "https://www.bcb.gov.br"),
    _k("us", "FX:cross-border flows", "treasury_tic", "Treasury International Capital (TIC)",
       "monthly", "US Treasury", "https://home.treasury.gov"),
    _k("jp", "FX:cross-border flows", "mof_weekly_securities_flows", "MoF international "
       "transactions in securities (対外及び対内証券売買契約等の状況)", "weekly",
       "Ministry of Finance Japan", "https://www.mof.go.jp"),
    # ---- official fixes
    _k("cn", _FIX, "cfets_central_parity", "USD/CNY central parity (中间价)", "daily",
       "CFETS / PBOC", "https://www.chinamoney.com.cn"),
    _k("in", _FIX, "fbil_reference_rate", "FBIL USD/INR reference rate", "daily",
       "Financial Benchmarks India", "https://www.fbil.org.in"),
    _k("ru", _FIX, "cbr_official_rate", "Bank of Russia official exchange rates", "daily",
       "Bank of Russia", "https://www.cbr.ru"),
    _k("tr", _FIX, "cbrt_indicative_rates", "CBRT indicative exchange rates", "daily",
       "Central Bank of the Republic of Turkiye", "https://www.tcmb.gov.tr"),
    _k("mx", _FIX, "banxico_fix", "Banxico FIX", "daily", "Banco de Mexico",
       "https://www.banxico.org.mx"),
    _k("br", _FIX, "bcb_ptax", "BCB PTAX", "daily", "Banco Central do Brasil",
       "https://www.bcb.gov.br"),
    _k("cl", _FIX, "bcch_dolar_observado", "Dolar observado", "daily", "Banco Central de Chile",
       "https://www.bcentral.cl"),
    _k("co", _FIX, "banrep_trm", "Tasa Representativa del Mercado (TRM)", "daily",
       "Banco de la Republica", "https://www.banrep.gov.co"),
    _k("pl", _FIX, "nbp_table_a", "NBP average exchange rates (Table A)", "daily",
       "Narodowy Bank Polski", "https://nbp.pl"),
    _k("hu", _FIX, "mnb_official_rates", "MNB official exchange rates", "daily",
       "Magyar Nemzeti Bank", "https://www.mnb.hu"),
    _k("cz", _FIX, "cnb_fixing", "CNB central bank exchange rate fixing", "daily",
       "Czech National Bank", "https://www.cnb.cz"),
    _k("ca", _FIX, "boc_daily_rates", "Bank of Canada daily exchange rates", "daily",
       "Bank of Canada", "https://www.bankofcanada.ca"),
    _k("au", _FIX, "rba_exchange_rates", "RBA 4pm AEST exchange rates", "daily",
       "Reserve Bank of Australia", "https://www.rba.gov.au"),
    _k("us", _FIX, "fed_h10", "Federal Reserve H.10 foreign exchange rates", "weekly",
       "Federal Reserve Board", "https://www.federalreserve.gov"),
    _k("kr", _FIX, "smbs_mar", "Seoul Money Brokerage market average rate (매매기준율)", "daily",
       "Seoul Money Brokerage Services", "http://www.smbs.biz"),
    # ---- commodities: inventories, warehouse receipts, futures curves
    _k("cn", "Commodities:inventory", "shfe_weekly_stocks", "SHFE weekly warehouse stocks",
       "weekly", "Shanghai Futures Exchange", "https://www.shfe.com.cn"),
    _k("us", "Commodities:inventory", "eia_weekly_crude_stocks", "EIA weekly US ending stocks "
       "of crude oil excluding SPR", "weekly", "US Energy Information Administration",
       "https://www.eia.gov", "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls"),
    _k("gb", "Commodities:inventory", "lme_warehouse_stocks", "LME daily warehouse stocks",
       "daily", "London Metal Exchange", "https://www.lme.com", access="PUBLIC_WITH_TERMS"),
    _k("cn", "Commodities:warehouse receipts", "shfe_warehouse_receipts", "SHFE/DCE/ZCE daily "
       "warehouse receipts (仓单日报)", "daily", "Shanghai Futures Exchange",
       "https://www.shfe.com.cn"),
    _k("gb", "Commodities:warehouse receipts", "lme_cancelled_warrants", "LME live and "
       "cancelled warrants", "daily", "London Metal Exchange", "https://www.lme.com",
       access="PUBLIC_WITH_TERMS"),
    _k("us", "Commodities:warehouse receipts", "comex_registered_stocks", "COMEX registered "
       "and eligible warehouse stocks", "daily", "CME Group", "https://www.cmegroup.com"),
    _k("cn", "Commodities:futures curves", "cn_commodity_futures", "SHFE/DCE/ZCE/INE/GFEX "
       "daily settlement prices by contract", "daily", "Chinese futures exchanges",
       "https://www.shfe.com.cn"),
    _k("us", "Commodities:futures curves", "cme_settlements", "CME Group daily settlements",
       "daily", "CME Group", "https://www.cmegroup.com"),
    _k("gb", "Commodities:futures curves", "lme_ice_curves", "LME and ICE Futures Europe "
       "settlement curves", "daily", "LME / ICE", "https://www.lme.com",
       access="PUBLIC_WITH_TERMS"),
    _k("jp", "Commodities:futures curves", "ose_commodity_futures", "OSE (ex-TOCOM) commodity "
       "futures settlements", "daily", "Japan Exchange Group", "https://www.jpx.co.jp"),
    _k("in", "Commodities:futures curves", "mcx_settlements", "MCX daily settlement prices",
       "daily", "Multi Commodity Exchange of India", "https://www.mcxindia.com"),
    _k("br", "Commodities:futures curves", "b3_commodity_futures", "B3 agricultural futures "
       "settlements", "daily", "B3", "https://www.b3.com.br"),
    _k("my", "Commodities:futures curves", "bursa_fcpo", "Bursa Malaysia crude palm oil "
       "futures (FCPO)", "daily", "Bursa Malaysia", "https://www.bursamalaysia.com"),
    _k("za", "Commodities:futures curves", "jse_commodity_derivatives", "JSE commodity "
       "derivatives (ex-SAFEX grains)", "daily", "Johannesburg Stock Exchange",
       "https://www.jse.co.za"),
    _k("ar", "Commodities:futures curves", "matba_rofex", "Matba Rofex grain futures", "daily",
       "A3 Mercados (Matba Rofex)", "https://www.matbarofex.com.ar"),
    _k("sg", "Commodities:futures curves", "sgx_iron_ore_rubber", "SGX iron ore and rubber "
       "futures", "daily", "Singapore Exchange", "https://www.sgx.com"),
    _k("ru", "Commodities:futures curves", "moex_commodity_futures", "MOEX commodity futures",
       "daily", "Moscow Exchange", "https://www.moex.com"),
    # ---- PART III: FX positioning, retail positioning, investor flows
    *(_k(cc, "Part III:FX positioning", "cftc_tff_currency", "CFTC Traders in Financial "
         "Futures -- the CME futures contract on this currency", "weekly", "CFTC",
         "https://www.cftc.gov", _CFTC_TFF)
      for cc in ("gb", "jp", "ch", "ca", "au", "nz", "mx", "br", "za")),
    _k("jp", "Part III:retail positioning", "tfx_click365_positions", "TFX Click 365 retail "
       "FX positions", "daily", "Tokyo Financial Exchange", "https://www.tfx.co.jp"),
    _k("kr", "Part III:retail positioning", "kofia_margin_balance", "KOFIA margin loans and "
       "investor deposits (신용융자잔고, 예탁금)", "daily", "Korea Financial Investment "
       "Association", "https://freesis.kofia.or.kr"),
    _k("cn", "Part III:retail positioning", "sse_szse_margin_balance", "SSE/SZSE margin "
       "financing and securities lending balance (融资融券)", "daily",
       "Shanghai and Shenzhen stock exchanges", "https://www.sse.com.cn"),
    _k("tw", "Part III:retail positioning", "twse_margin_balance", "TWSE margin purchase and "
       "short sale balance", "daily", "Taiwan Stock Exchange", "https://www.twse.com.tw"),
    _k("us", "Part III:retail positioning", "finra_margin_statistics", "FINRA margin "
       "statistics", "monthly", "FINRA", "https://www.finra.org"),
    _k("in", "Part III:retail positioning", "nse_client_oi", "NSE client-category open "
       "interest", "daily", "National Stock Exchange of India", "https://www.nseindia.com"),
    _k("kr", "Part III:investor flows", "krx_investor_flows", "KRX trading by investor type "
       "(투자자별 거래실적)", "daily", "Korea Exchange", "http://data.krx.co.kr"),
    _k("tw", "Part III:investor flows", "twse_foreign_flows", "TWSE trading by institutional "
       "investors (三大法人)", "daily", "Taiwan Stock Exchange", "https://www.twse.com.tw"),
    _k("in", "Part III:investor flows", "nsdl_fpi_flows", "NSDL daily FPI investment", "daily",
       "NSDL", "https://www.fpi.nsdl.co.in"),
    _k("jp", "Part III:investor flows", "jpx_investor_type", "JPX trading by type of investor "
       "(投資部門別売買状況)", "weekly", "Japan Exchange Group", "https://www.jpx.co.jp"),
    _k("th", "Part III:investor flows", "set_investor_type", "SET trading by investor type",
       "daily", "Stock Exchange of Thailand", "https://www.set.or.th"),
    _k("us", "Part III:investor flows", "ici_fund_flows", "ICI weekly estimated long-term "
       "mutual fund flows", "weekly", "Investment Company Institute", "https://www.ici.org"),
    # ---- PART III: energy
    _k("us", "Part III:energy", "eia_wti_spot", "EIA WTI spot price", "daily",
       "US Energy Information Administration", "https://www.eia.gov",
       "https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls"),
    # ---- PART II: the ABSENT rows of the completion audit, named where a publisher is known
    _k("us", "Labour:claims", "dol_initial_claims", "DOL weekly unemployment insurance claims",
       "weekly", "US Department of Labor", "https://www.dol.gov"),
    _k("gb", "Labour:claims", "ons_claimant_count", "ONS claimant count", "monthly", "ONS",
       "https://www.ons.gov.uk"),
    _k("us", "Labour:vacancies", "bls_jolts", "BLS JOLTS job openings", "monthly", "BLS",
       "https://www.bls.gov"),
    _k("gb", "Labour:vacancies", "ons_vacancies", "ONS vacancies survey", "monthly", "ONS",
       "https://www.ons.gov.uk"),
    _k("jp", "Labour:vacancies", "mhlw_jobs_to_applicants", "MHLW jobs-to-applicants ratio "
       "(有効求人倍率)", "monthly", "Ministry of Health, Labour and Welfare",
       "https://www.mhlw.go.jp"),
    _k("ca", "Labour:vacancies", "statcan_jvws", "StatCan Job Vacancy and Wage Survey",
       "quarterly", "Statistics Canada", "https://www.statcan.gc.ca"),
    _k("au", "Labour:vacancies", "abs_job_vacancies", "ABS job vacancies", "quarterly", "ABS",
       "https://www.abs.gov.au"),
    _k("us", "Labour:hours worked", "bls_ces_hours", "BLS CES average weekly hours", "monthly",
       "BLS", "https://www.bls.gov"),
    _k("jp", "Labour:hours worked", "mhlw_monthly_labour_survey", "MHLW Monthly Labour Survey "
       "hours worked (毎月勤労統計)", "monthly", "Ministry of Health, Labour and Welfare",
       "https://www.mhlw.go.jp"),
    _k("gb", "Consumer:card payments", "ons_card_spending", "ONS UK spending on debit and "
       "credit cards", "weekly", "ONS", "https://www.ons.gov.uk"),
    _k("au", "Consumer:card payments", "rba_payments_data", "RBA retail payments statistics",
       "monthly", "Reserve Bank of Australia", "https://www.rba.gov.au"),
    _k("nz", "Consumer:card payments", "statsnz_electronic_card", "Stats NZ electronic card "
       "transactions", "monthly", "Stats NZ", "https://www.stats.govt.nz"),
    _k("in", "Consumer:card payments", "npci_upi_statistics", "NPCI UPI product statistics",
       "monthly", "National Payments Corporation of India", "https://www.npci.org.in"),
    _k("br", "Consumer:card payments", "bcb_pix_statistics", "BCB Pix statistics", "monthly",
       "Banco Central do Brasil", "https://www.bcb.gov.br"),
    _k("us", "Consumer:vehicle sales", "bea_light_vehicle_sales", "BEA light vehicle sales",
       "monthly", "BEA", "https://www.bea.gov"),
    _k("cn", "Consumer:vehicle sales", "caam_vehicle_sales", "CAAM vehicle sales", "monthly",
       "China Association of Automobile Manufacturers", "http://www.caam.org.cn"),
    _k("jp", "Consumer:vehicle sales", "jada_new_vehicle_sales", "JADA new vehicle sales",
       "monthly", "Japan Automobile Dealers Association", "https://www.jada.or.jp"),
    _k("de", "Consumer:vehicle sales", "kba_registrations", "KBA new vehicle registrations",
       "monthly", "Kraftfahrt-Bundesamt", "https://www.kba.de"),
    _k("gb", "Consumer:vehicle sales", "smmt_registrations", "SMMT new car registrations",
       "monthly", "SMMT", "https://www.smmt.co.uk"),
    _k("in", "Consumer:vehicle sales", "siam_sales", "SIAM domestic sales", "monthly", "SIAM",
       "https://www.siam.in"),
    _k("br", "Consumer:vehicle sales", "fenabrave_registrations", "Fenabrave vehicle "
       "registrations", "monthly", "Fenabrave", "https://www.fenabrave.org.br"),
    _k("au", "Consumer:vehicle sales", "fcai_vfacts", "FCAI VFACTS new vehicle sales",
       "monthly", "FCAI", "https://www.fcai.com.au"),
    _k("cn", "Consumer:search behavior", "baidu_index", "Baidu Index (百度指数)", "daily",
       "Baidu", "https://index.baidu.com", access="PUBLIC_WITH_TERMS",
       note="login required; Google Trends does not cover the mainland"),
    _k("kr", "Consumer:search behavior", "naver_datalab", "Naver DataLab search trends",
       "daily", "Naver", "https://datalab.naver.com"),
    _k("ru", "Consumer:search behavior", "yandex_wordstat", "Yandex Wordstat", "daily",
       "Yandex", "https://wordstat.yandex.ru", access="PUBLIC_WITH_TERMS"),
    _k("jp", "Trade:customs ports", "mof_trade_statistics_10day", "MoF trade statistics, first "
       "ten and twenty days of the month (上中旬)", "monthly", "Ministry of Finance Japan",
       "https://www.customs.go.jp"),
    _k("kr", "Trade:customs ports", "kcs_10day_exports", "Korea Customs Service 10/20-day "
       "exports", "monthly", "Korea Customs Service", "https://www.customs.go.kr"),
    _k("cn", "Trade:customs ports", "gacc_trade_by_customs_district", "GACC trade by customs "
       "district", "monthly", "General Administration of Customs", "http://www.customs.gov.cn"),
    _k("us", "Trade:customs ports", "census_trade_by_port", "Census USA Trade by port of entry",
       "monthly", "US Census Bureau", "https://www.census.gov"),
    _k("us", "Business:tenders", "usaspending_awards", "USAspending federal awards", "daily",
       "US Treasury", "https://www.usaspending.gov"),
    _k("gb", "Business:tenders", "find_a_tender", "Find a Tender / Contracts Finder", "daily",
       "UK Cabinet Office", "https://www.find-tender.service.gov.uk"),
    _k("cn", "Business:tenders", "ccgp_procurement", "China government procurement notices",
       "daily", "Ministry of Finance PRC", "http://www.ccgp.gov.cn"),
    _k("kr", "Business:tenders", "koneps_tenders", "KONEPS public procurement", "daily",
       "Public Procurement Service", "https://www.g2b.go.kr"),
    _k("in", "Business:tenders", "cppp_tenders", "Central Public Procurement Portal", "daily",
       "Government of India", "https://eprocure.gov.in"),
    _k("br", "Business:tenders", "pncp_contracts", "Portal Nacional de Contratacoes Publicas",
       "daily", "Government of Brazil", "https://pncp.gov.br"),
    _k("us", "Inflation:inflation expectations", "umich_expectations", "University of "
       "Michigan consumer inflation expectations", "monthly", "University of Michigan",
       "https://www.sca.isr.umich.edu"),
    _k("gb", "Inflation:inflation expectations", "boe_inflation_attitudes", "BoE/Ipsos "
       "inflation attitudes survey", "quarterly", "Bank of England",
       "https://www.bankofengland.co.uk"),
    _k("jp", "Inflation:inflation expectations", "boj_tankan_price_outlook", "Tankan firms' "
       "inflation outlook", "quarterly", "Bank of Japan", "https://www.boj.or.jp"),
    _k("us", "Growth:utilization", "fed_g17_utilization", "Federal Reserve G.17 capacity "
       "utilization", "monthly", "Federal Reserve Board", "https://www.federalreserve.gov"),
    _k("jp", "Growth:utilization", "meti_operating_ratio", "METI operating ratio index "
       "(稼働率指数)", "monthly", "METI", "https://www.meti.go.jp"),
    _k("us", "Business:purchasing activity", "census_m3_orders", "Census M3 manufacturers' "
       "shipments, inventories and orders", "monthly", "US Census Bureau",
       "https://www.census.gov"),
    _k("jp", "Business:purchasing activity", "cao_machinery_orders", "Cabinet Office "
       "machinery orders (機械受注)", "monthly", "Cabinet Office", "https://www.esri.cao.go.jp"),
    _k("us", "Monetary / rates:yield curves", "treasury_daily_par_curve", "Treasury daily par "
       "yield curve rates", "daily", "US Treasury", "https://home.treasury.gov",
       "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
       "daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve"
       "&field_tdr_date_value=2026&_format=csv"),
)


@dataclass(frozen=True)
class Transnational:
    """One public dataset that answers a class for an explicit list of countries."""

    source_id: str
    keys: tuple[str, ...]
    series: str
    cadence: str
    publisher: str
    url: str
    countries: frozenset[str]
    endpoints: tuple[str, ...] = ()
    #: ISO-2 -> extra endpoints that only serve that country (the ECB's per-member HICP keys).
    per_country: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    access: str = "UNVERIFIED"


def _bis(flow: str) -> str:
    return f"https://data.bis.org/static/bulk/{flow}_csv_col.zip"


#: The BIS reporting economies this module is confident of, euro members included through the
#: euro area's own rows; deliberately conservative -- a country left out reads UNMEASURED, which
#: is honest, while a country put in wrongly would be a false "known equivalent".
_BIS_CORE: frozenset[str] = frozenset({
    "us", "gb", "jp", "ch", "ca", "au", "nz", "no", "se", "dk", "pl", "hu", "cz", "ro", "is",
    "tr", "ru", "za", "il", "sa", "in", "id", "kr", "my", "ph", "th", "cn", "hk", "mx", "br",
    "cl", "co", "pe", "ar"})
_EURO_CORE: frozenset[str] = frozenset({"de", "fr", "it", "es", "nl", "be", "at", "fi", "gr",
                                        "ie", "pt"})
_ECB_HICP = "https://data-api.ecb.europa.eu/service/data/ICP/M.{cc}.N.000000.4.ANR?format=csvdata"

TRANSNATIONAL: tuple[Transnational, ...] = (
    Transnational("bis_cbpol", ("Monetary / rates:policy rates", "FX:carry"),
                  "BIS central bank policy rates", "daily", "Bank for International Settlements",
                  "https://data.bis.org", _BIS_CORE | _EURO_CORE, (_bis("WS_CBPOL"),)),
    Transnational("bis_eer", ("FX:REER/NEER",), "BIS effective exchange rates (broad)",
                  "monthly", "Bank for International Settlements", "https://data.bis.org",
                  _BIS_CORE | _EURO_CORE | {"sg", "tw", "ae", "bg"}, (_bis("WS_EER"),)),
    Transnational("bis_spp", ("Housing:prices",), "BIS selected residential property prices",
                  "quarterly", "Bank for International Settlements", "https://data.bis.org",
                  _BIS_CORE | _EURO_CORE | {"sg"}, (_bis("WS_SPP"),)),
    Transnational("bis_tc", ("Credit:household leverage", "Credit:corporate credit",
                             "Monetary / rates:credit"),
                  "BIS total credit to the non-financial sector", "quarterly",
                  "Bank for International Settlements", "https://data.bis.org",
                  _BIS_CORE | _EURO_CORE | {"sg"}, (_bis("WS_TC"),)),
    Transnational("bis_cbta", ("Monetary / rates:central-bank assets",),
                  "BIS central bank total assets", "monthly",
                  "Bank for International Settlements", "https://data.bis.org",
                  _BIS_CORE | _EURO_CORE, (_bis("WS_CBTA"),)),
    Transnational("bis_long_cpi", ("Inflation:CPI",), "BIS consumer prices (long series)",
                  "monthly", "Bank for International Settlements", "https://data.bis.org",
                  _BIS_CORE | _EURO_CORE, (_bis("WS_LONG_CPI"),)),
    Transnational("ecb_reference_rates", ("FX:official fixes",), "ECB euro foreign exchange "
                  "reference rates", "daily", "European Central Bank",
                  "https://data.ecb.europa.eu", EURO_MEMBERS,
                  ("https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
                   "?format=csvdata",)),
    Transnational("ecb_hicp", ("Inflation:CPI",), "ECB/Eurostat HICP by member state",
                  "monthly", "European Central Bank", "https://data.ecb.europa.eu",
                  EURO_MEMBERS,
                  per_country={cc: (_ECB_HICP.format(cc=cc.upper()),)
                               for cc in sorted(EURO_MEMBERS)}),
    Transnational("ted_procurement", ("Business:tenders",), "Tenders Electronic Daily (EU/EEA "
                  "public procurement)", "daily", "Publications Office of the EU",
                  "https://ted.europa.eu",
                  EURO_MEMBERS | {"cz", "dk", "hu", "pl", "ro", "se", "is", "no"}),
    Transnational("eurostat_job_vacancies", ("Labour:vacancies",), "Eurostat job vacancy "
                  "statistics", "quarterly", "Eurostat", "https://ec.europa.eu/eurostat",
                  EURO_MEMBERS | {"cz", "dk", "hu", "pl", "ro", "se", "no"}),
    Transnational("google_trends", ("Consumer:search behavior",), "Google Trends", "daily",
                  "Google", "https://trends.google.com",
                  frozenset(c for c in COUNTRY_NAMES if c not in {"cn", "kr", "ru", "ir",
                                                                  "ws_to", "nc"}),
                  access="PUBLIC_WITH_TERMS"),
    Transnational("imf_portwatch", ("Part III:shipping",), "IMF PortWatch daily port calls and "
                  "trade-volume estimates", "daily", "IMF", "https://portwatch.imf.org",
                  frozenset(c for c in COUNTRY_NAMES if c not in LANDLOCKED_NO_SEAPORT
                            and c not in {"ch", "at", "rs", "hu", "cz", "kz", "tm", "az",
                                          "ws_to", "nc"})),
)


# --------------------------------------------------------------------- national publishers
@dataclass(frozen=True)
class Publisher:
    id: str
    name: str
    url: str


def _p(pid: str, name: str, url: str) -> Publisher:
    return Publisher(pid, name, url)


_ECB = _p("ecb", "European Central Bank (shared)", "https://www.ecb.europa.eu")

#: role -> publisher, for the major economies. A role inferred from this table is graded `role`.
PUBLISHERS: dict[str, dict[str, Publisher]] = {
    "us": {"central_bank": _p("fed", "Federal Reserve", "https://www.federalreserve.gov"),
           "statistics_office": _p("bls_bea_census", "BLS / BEA / Census Bureau",
                                   "https://www.bea.gov"),
           "finance_ministry": _p("us_treasury", "US Treasury", "https://home.treasury.gov")},
    "gb": {"central_bank": _p("boe", "Bank of England", "https://www.bankofengland.co.uk"),
           "statistics_office": _p("ons", "Office for National Statistics",
                                   "https://www.ons.gov.uk"),
           "finance_ministry": _p("uk_dmo", "UK Debt Management Office",
                                  "https://www.dmo.gov.uk")},
    "jp": {"central_bank": _p("boj", "Bank of Japan", "https://www.boj.or.jp"),
           "statistics_office": _p("stat_jp", "Statistics Bureau / Cabinet Office",
                                   "https://www.stat.go.jp"),
           "finance_ministry": _p("mof_jp", "Ministry of Finance", "https://www.mof.go.jp")},
    "ch": {"central_bank": _p("snb", "Swiss National Bank", "https://www.snb.ch"),
           "statistics_office": _p("bfs", "Federal Statistical Office",
                                   "https://www.bfs.admin.ch"),
           "finance_ministry": _p("efv", "Federal Finance Administration",
                                  "https://www.efv.admin.ch")},
    "ca": {"central_bank": _p("boc", "Bank of Canada", "https://www.bankofcanada.ca"),
           "statistics_office": _p("statcan", "Statistics Canada",
                                   "https://www.statcan.gc.ca"),
           "finance_ministry": _p("fin_ca", "Department of Finance Canada",
                                  "https://www.canada.ca/en/department-finance.html")},
    "au": {"central_bank": _p("rba", "Reserve Bank of Australia", "https://www.rba.gov.au"),
           "statistics_office": _p("abs", "Australian Bureau of Statistics",
                                   "https://www.abs.gov.au"),
           "finance_ministry": _p("aofm", "AOFM", "https://www.aofm.gov.au")},
    "nz": {"central_bank": _p("rbnz", "Reserve Bank of New Zealand", "https://www.rbnz.govt.nz"),
           "statistics_office": _p("statsnz", "Stats NZ", "https://www.stats.govt.nz"),
           "finance_ministry": _p("nz_treasury", "The Treasury", "https://www.treasury.govt.nz")},
    "no": {"central_bank": _p("norges_bank", "Norges Bank", "https://www.norges-bank.no"),
           "statistics_office": _p("ssb", "Statistics Norway", "https://www.ssb.no")},
    "se": {"central_bank": _p("riksbank", "Sveriges Riksbank", "https://www.riksbank.se"),
           "statistics_office": _p("scb", "Statistics Sweden", "https://www.scb.se"),
           "finance_ministry": _p("riksgalden", "Swedish National Debt Office",
                                  "https://www.riksgalden.se")},
    "dk": {"central_bank": _p("nationalbanken", "Danmarks Nationalbank",
                              "https://www.nationalbanken.dk"),
           "statistics_office": _p("dst", "Statistics Denmark", "https://www.dst.dk")},
    "pl": {"central_bank": _p("nbp", "Narodowy Bank Polski", "https://nbp.pl"),
           "statistics_office": _p("gus", "Statistics Poland", "https://stat.gov.pl")},
    "hu": {"central_bank": _p("mnb", "Magyar Nemzeti Bank", "https://www.mnb.hu"),
           "statistics_office": _p("ksh", "Hungarian Central Statistical Office",
                                   "https://www.ksh.hu")},
    "cz": {"central_bank": _p("cnb", "Czech National Bank", "https://www.cnb.cz"),
           "statistics_office": _p("czso", "Czech Statistical Office", "https://www.czso.cz")},
    "tr": {"central_bank": _p("cbrt", "Central Bank of the Republic of Turkiye",
                              "https://www.tcmb.gov.tr"),
           "statistics_office": _p("turkstat", "TurkStat", "https://www.tuik.gov.tr")},
    "za": {"central_bank": _p("sarb", "South African Reserve Bank", "https://www.resbank.co.za"),
           "statistics_office": _p("statssa", "Statistics South Africa",
                                   "https://www.statssa.gov.za"),
           "finance_ministry": _p("za_treasury", "National Treasury",
                                  "https://www.treasury.gov.za")},
    "mx": {"central_bank": _p("banxico", "Banco de Mexico", "https://www.banxico.org.mx"),
           "statistics_office": _p("inegi", "INEGI", "https://www.inegi.org.mx")},
    "br": {"central_bank": _p("bcb", "Banco Central do Brasil", "https://www.bcb.gov.br"),
           "statistics_office": _p("ibge", "IBGE", "https://www.ibge.gov.br"),
           "finance_ministry": _p("tesouro", "Tesouro Nacional",
                                  "https://www.tesourotransparente.gov.br")},
    "cl": {"central_bank": _p("bcch", "Banco Central de Chile", "https://www.bcentral.cl"),
           "statistics_office": _p("ine_cl", "INE Chile", "https://www.ine.gob.cl")},
    "co": {"central_bank": _p("banrep", "Banco de la Republica", "https://www.banrep.gov.co"),
           "statistics_office": _p("dane", "DANE", "https://www.dane.gov.co")},
    "pe": {"central_bank": _p("bcrp", "Banco Central de Reserva del Peru",
                              "https://www.bcrp.gob.pe"),
           "statistics_office": _p("inei", "INEI", "https://www.inei.gob.pe")},
    "ar": {"central_bank": _p("bcra", "Banco Central de la Republica Argentina",
                              "https://www.bcra.gob.ar"),
           "statistics_office": _p("indec", "INDEC", "https://www.indec.gob.ar")},
    "cn": {"central_bank": _p("pboc", "People's Bank of China", "http://www.pbc.gov.cn"),
           "statistics_office": _p("nbs", "National Bureau of Statistics",
                                   "https://www.stats.gov.cn"),
           "finance_ministry": _p("mof_cn", "Ministry of Finance", "https://www.mof.gov.cn")},
    "hk": {"central_bank": _p("hkma", "Hong Kong Monetary Authority", "https://www.hkma.gov.hk"),
           "statistics_office": _p("censtatd", "Census and Statistics Department",
                                   "https://www.censtatd.gov.hk")},
    "sg": {"central_bank": _p("mas", "Monetary Authority of Singapore",
                              "https://www.mas.gov.sg"),
           "statistics_office": _p("singstat", "Singapore Department of Statistics",
                                   "https://www.singstat.gov.sg")},
    "kr": {"central_bank": _p("bok", "Bank of Korea", "https://www.bok.or.kr"),
           "statistics_office": _p("kostat", "Statistics Korea", "https://kostat.go.kr")},
    "tw": {"central_bank": _p("cbc", "Central Bank of the Republic of China (Taiwan)",
                              "https://www.cbc.gov.tw"),
           "statistics_office": _p("dgbas", "DGBAS", "https://www.dgbas.gov.tw")},
    "in": {"central_bank": _p("rbi", "Reserve Bank of India", "https://www.rbi.org.in"),
           "statistics_office": _p("mospi", "MoSPI", "https://www.mospi.gov.in")},
    "id": {"central_bank": _p("bi", "Bank Indonesia", "https://www.bi.go.id"),
           "statistics_office": _p("bps", "Badan Pusat Statistik", "https://www.bps.go.id")},
    "my": {"central_bank": _p("bnm", "Bank Negara Malaysia", "https://www.bnm.gov.my"),
           "statistics_office": _p("dosm", "Department of Statistics Malaysia",
                                   "https://www.dosm.gov.my")},
    "th": {"central_bank": _p("bot", "Bank of Thailand", "https://www.bot.or.th"),
           "statistics_office": _p("nso_th", "National Statistical Office",
                                   "https://www.nso.go.th")},
    "ph": {"central_bank": _p("bsp", "Bangko Sentral ng Pilipinas", "https://www.bsp.gov.ph"),
           "statistics_office": _p("psa", "Philippine Statistics Authority",
                                   "https://psa.gov.ph")},
    "il": {"central_bank": _p("boi", "Bank of Israel", "https://www.boi.org.il"),
           "statistics_office": _p("cbs_il", "Central Bureau of Statistics",
                                   "https://www.cbs.gov.il")},
    "sa": {"central_bank": _p("sama", "Saudi Central Bank", "https://www.sama.gov.sa"),
           "statistics_office": _p("gastat", "General Authority for Statistics",
                                   "https://www.stats.gov.sa")},
    "ru": {"central_bank": _p("cbr", "Bank of Russia", "https://www.cbr.ru"),
           "statistics_office": _p("rosstat", "Rosstat", "https://rosstat.gov.ru")},
    "de": {"central_bank": _ECB,
           "statistics_office": _p("destatis", "Destatis", "https://www.destatis.de")},
    "fr": {"central_bank": _ECB,
           "statistics_office": _p("insee", "INSEE", "https://www.insee.fr")},
    "it": {"central_bank": _ECB,
           "statistics_office": _p("istat", "Istat", "https://www.istat.it")},
    "es": {"central_bank": _ECB,
           "statistics_office": _p("ine_es", "INE Spain", "https://www.ine.es")},
    "nl": {"central_bank": _ECB,
           "statistics_office": _p("cbs_nl", "Statistics Netherlands", "https://www.cbs.nl")},
}

#: The classes every publisher in its role publishes in EVERY economy `PUBLISHERS` lists. Kept to
#: the prints no major economy lacks: a wider list would turn a guess into a "known equivalent".
ROLE_STANDARD: dict[str, tuple[str, ...]] = {
    "central_bank": ("Monetary / rates:policy rates", "Monetary / rates:central-bank assets",
                     "Monetary / rates:money supply"),
    "central_bank_national": ("FX:reserves",),
    "statistics_office": ("Inflation:CPI", "Growth:GDP", "Labour:unemployment",
                          "Trade:imports", "Trade:exports"),
}


def equivalents_for(cc: str, key: str) -> list[Equivalent]:
    """Every known public equivalent of `key` in `cc`, best first: named, transnational, role."""
    out: list[Equivalent] = [e for e in KNOWN if e.country == cc and e.key == key]
    for t in TRANSNATIONAL:
        if key in t.keys and cc in t.countries:
            out.append(Equivalent(country=cc, key=key, source_id=t.source_id, series=t.series,
                                  cadence=t.cadence, publisher=t.publisher, url=t.url,
                                  endpoints=tuple(t.endpoints) + tuple(t.per_country.get(cc, ())),
                                  tier="transnational", access=t.access))
    pubs = PUBLISHERS.get(cc, {})
    for role, keys in ROLE_STANDARD.items():
        base_role = "central_bank" if role == "central_bank_national" else role
        pub = pubs.get(base_role)
        if pub is None or key not in keys:
            continue
        if role == "central_bank_national" and pub.id == _ECB.id:
            continue                  # a euro member's reserves are its NCB's, not the ECB's
        out.append(Equivalent(country=cc, key=key, source_id=f"{pub.id}:{_slug(key)}",
                              series=f"{_BY_KEY[key].name} ({pub.name})",
                              cadence=_BY_KEY[key].cadence, publisher=pub.name, url=pub.url,
                              tier="role"))
    return out


def _slug(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


# ------------------------------------------------------------------------------- matching
def match_classes(text: str) -> tuple[str, ...]:
    """The class keys a pack declaration's text answers, in ontology order."""
    t = str(text or "")
    if not t.strip():
        return ()
    return tuple(c.key for c in CLASSES if _COMPILED[c.key].search(t)
                 and not (c.key in _EXCLUDE and _EXCLUDE[c.key].search(t)))


# ------------------------------------------------------------------------------- disposition
@dataclass(frozen=True)
class Cell:
    """One (country, class) cell and the evidence for its disposition."""

    country: str
    key: str
    disposition: str
    why: str
    declared: tuple[Mapping[str, Any], ...] = ()
    equivalents: tuple[Equivalent, ...] = ()
    proof: Mapping[str, Any] | None = None
    proof_state: str = UNMEASURED      # FOUND | NOT_FOUND | UNMEASURED

    def to_json(self) -> dict[str, Any]:
        best = self.equivalents[0].to_json() if self.equivalents else None
        return {"country": self.country, "class": self.key, "disposition": self.disposition,
                "why": self.why, "declared": [dict(d) for d in self.declared[:4]],
                "n_declared": len(self.declared), "equivalent": best,
                "n_equivalents": len(self.equivalents), "proof": dict(self.proof or {}) or None,
                "proof_state": self.proof_state}


def dispose(cc: str, key: str, *, declared: Sequence[Mapping[str, Any]] = (),
            proof: Mapping[str, Any] | None = None, proof_readable: bool = False,
            equivalents: Iterable[Equivalent] | None = None) -> Cell:
    """The ONE place a cell gets its disposition. COVERED needs a proof the caller found; there is
    no other path to it, and an unreadable proof source is carried as UNMEASURED, never as a
    clean "not fed"."""
    if key not in _BY_KEY:
        raise KeyError(f"unknown information class {key!r}")
    eqs = tuple(equivalents if equivalents is not None else equivalents_for(cc, key))
    decl = tuple(declared)
    proof_state = "FOUND" if proof else ("NOT_FOUND" if proof_readable else UNMEASURED)
    if decl and proof:
        return Cell(cc, key, "COVERED",
                    f"declared ({decl[0].get('id')}) and the ingestion ledger shows "
                    f"{proof.get('state')} for {proof.get('unit')}", decl, eqs, proof, proof_state)
    if proof and not decl:
        return Cell(cc, key, "COVERED",
                    f"a known equivalent ({proof.get('key')}) reached {proof.get('state')} in the "
                    "ingestion ledger", decl, eqs, proof, proof_state)
    if decl:
        why = (f"declared by {decl[0].get('pack')} ({decl[0].get('id')}); "
               + ("no ingestion unit reached a measured outcome" if proof_readable else
                  "proof UNMEASURED: no ingestion ledger was readable on this host"))
        return Cell(cc, key, "DECLARED", why, decl, eqs, None, proof_state)
    reason = no_equivalent_reason(cc, key)
    if reason:
        return Cell(cc, key, "NO_EQUIVALENT", reason, decl, eqs, None, proof_state)
    if eqs:
        e = eqs[0]
        return Cell(cc, key, "ABSENT_KNOWN_EQUIVALENT",
                    f"{e.tier} equivalent {e.source_id} ({e.publisher}) is public and no pack "
                    "declares it", decl, eqs, None, proof_state)
    return Cell(cc, key, UNMEASURED, "no pack declares it and no equivalent is known: nobody "
                "has looked", decl, eqs, None, proof_state)


# ------------------------------------------------------------------------------- the extension
#: THE ONTOLOGY IS OPEN. The classes above are the directive's floor, never its ceiling: a class
#: the directive did not name (or a named equivalent nobody wrote into this file) is added as DATA
#: in this JSON file and merged at import, with no code change. A declaration no class matches is
#: never dropped either -- `regional_parity` reports it as a CANDIDATE CLASS, and promoting a
#: candidate means adding it here. Path override: QUANT_EQUIVALENCE_EXT (the tests use it).
EXT_PATH = Path(os.environ.get("QUANT_EQUIVALENCE_EXT") or (
    Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" /
    "equivalence_ontology_ext.json"))
BASE_CLASS_COUNT = len(CLASSES)
#: What the last load did: the file read, the rows merged, and every row REFUSED with its reason.
EXT_REPORT: dict[str, Any] = {}


def _ext_class(row: Mapping[str, Any]) -> DataClass:
    group, name = str(row.get("group") or "").strip(), str(row.get("name") or "").strip()
    terms = str(row.get("terms") or "").strip()
    if not group or not name or not terms:
        raise ValueError("a class needs group, name and terms")
    re.compile(terms, re.IGNORECASE)
    return DataClass(key=f"{group}:{name}", group=group, name=name,
                     layer=str(row.get("layer") or "official"), terms=terms,
                     cadence=str(row.get("cadence") or "monthly"),
                     mandate_id=str(row.get("mandate_id") or "EXT"),
                     part=str(row.get("part") or "ext"))


def _ext_known(row: Mapping[str, Any], keys: set[str]) -> Equivalent:
    key = str(row.get("key") or "")
    if key not in keys:
        raise ValueError(f"unknown class {key!r}")
    url = str(row.get("url") or "")
    eps = tuple(str(u) for u in row.get("endpoints") or ())
    if not url.startswith(("http://", "https://")) or not all(
            u.startswith("https://") for u in eps):
        raise ValueError("url must be http(s) and every endpoint https")
    cc, sid = str(row.get("country") or "").lower(), str(row.get("source_id") or "")
    if not cc or not sid:
        raise ValueError("a known equivalent needs country and source_id")
    return Equivalent(country=cc, key=key, source_id=sid, series=str(row.get("series") or sid),
                      cadence=str(row.get("cadence") or "monthly"),
                      publisher=str(row.get("publisher") or ""), url=url, endpoints=eps,
                      tier="named", note=str(row.get("note") or "ext"))


def load_extension(path: Path | None = None) -> dict[str, Any]:
    """Merge the extension file into CLASSES / KNOWN. Idempotent; a bad row is refused BY NAME
    (never silently skipped) and the base ontology always survives an unreadable file."""
    global CLASSES, CLASS_KEYS, _BY_KEY, _COMPILED, KNOWN
    p = Path(path) if path is not None else EXT_PATH
    base_classes, base_known = CLASSES[:BASE_CLASS_COUNT], _BASE_KNOWN
    report: dict[str, Any] = {"path": str(p), "classes_added": [], "known_added": 0,
                              "refused": [], "state": "ABSENT"}
    doc: Any = None
    if p.exists():
        try:
            doc = json.loads(p.read_text(encoding="utf-8-sig"))
            report["state"] = "READ"
        except (OSError, ValueError) as exc:
            report["state"] = f"{UNMEASURED}: {type(exc).__name__}: {exc}"
    classes, known = list(base_classes), list(base_known)
    if isinstance(doc, Mapping):
        keys = {c.key for c in classes}
        for i, row in enumerate(doc.get("classes") or ()):
            try:
                dc = _ext_class(row)
                if dc.key in keys:
                    raise ValueError(f"duplicate class {dc.key!r}")
            except (ValueError, re.error, AttributeError) as exc:
                report["refused"].append({"row": f"classes[{i}]", "why": str(exc)})
                continue
            classes.append(dc)
            keys.add(dc.key)
            report["classes_added"].append(dc.key)
        for i, row in enumerate(doc.get("known") or ()):
            try:
                known.append(_ext_known(row, keys))
                report["known_added"] += 1
            except (ValueError, AttributeError) as exc:
                report["refused"].append({"row": f"known[{i}]", "why": str(exc)})
    CLASSES = tuple(classes)
    CLASS_KEYS = tuple(c.key for c in CLASSES)
    _BY_KEY = {c.key: c for c in CLASSES}
    _COMPILED = {c.key: re.compile(c.terms, re.IGNORECASE) for c in CLASSES}
    KNOWN = tuple(known)
    EXT_REPORT.clear()
    EXT_REPORT.update(report)
    return report


_BASE_KNOWN: tuple[Equivalent, ...] = KNOWN
load_extension()
