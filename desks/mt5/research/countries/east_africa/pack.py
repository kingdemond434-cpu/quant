"""EAST AFRICA -- Ethiopia, Tanzania and Uganda: a central bank that BUYS GOLD, a currency that
was cut loose in one week, and a pipeline that makes two countries one physical system.

WHY THREE JURISDICTIONS IN ONE PACK, AND WHY THESE THREE. They are not "the rest of East Africa
after Kenya". They are one physical economy with three treasuries: Ugandan crude will leave
through a Tanzanian port, Ugandan and Ethiopian coffee leave through Mombasa and Djibouti,
Congolese and Zambian copper leaves through Dar es Salaam, and gold mined or bought anywhere in
the three moves on the same lorries. Kenya (`ke`) is the financial and logistics HUB of all
three and is answered by its own pack; this one is deliberately its COMPLEMENT -- `ke` owns the
Mombasa/Northern-Corridor leg, the published CBK buy/sell spread and the two-rainy-season cycle,
and this pack owns the Central Corridor, the three currencies Kenya's pack does not carry, and
the three mechanisms below that exist nowhere else in the desk's roster.

THE THREE MECHANISMS THAT EARN THE TRIAL BUDGET. Each one is published, dated and price-relevant,
and each one is a domain of its own rather than a sentence inside a generic frontier domain:

  1. TANZANIA IS A TOP-FIFTEEN GOLD PRODUCER WHOSE CENTRAL BANK BUYS THE METAL AT HOME. Roughly
     50 tonnes a year come out of Geita, North Mara, Bulyanhulu and the artisanal sector, and
     from the 2023/24 fiscal year the Bank of Tanzania has run a FORMAL DOMESTIC GOLD PURCHASE
     PROGRAMME for its reserves -- announced in the 2023/24 budget, funded from FY2023/24, with
     a domestic refinery requirement and, from the 2024/25 and 2025/26 budget rounds, a statutory
     obligation on licensed miners, smelters and dealers to OFFER a share of output (the 2025
     Finance Act sets it at 20% of production) to the domestic market and to the Bank. That is a
     dated, published change in WHERE physical gold goes and in official-sector demand, on a
     producer big enough to matter: a direct XAUUSD observable almost no desk models, and the
     reason EA-F exists.
  2. ETHIOPIA FLOATED THE BIRR ON 2024-07-29 AFTER DECADES OF A CRAWLING PEG. The National Bank
     of Ethiopia's directive of that week ended the administered rate and the FX rationing queue
     that went with it; the birr lost more than half its value against the dollar within weeks,
     the parallel premium that had run above 100% collapsed toward the official rate, and an IMF
     Extended Credit Facility was approved the same day. It is one of the cleanest emerging-market
     regime boundaries of the decade. Ethiopia is also the BIRTHPLACE of arabica coffee and its
     fifth-largest producer, and the Ethiopian Commodity Exchange publishes DAILY coffee and
     sesame trade data, so the boundary is measurable on the export economics of COFARA at the
     margin and not only on a currency the broker does not quote.
  3. UGANDA BECOMES AN OIL PRODUCER IN 2025-2026. Tilenga and Kingfisher took FID on 2022-02-01
     and the East African Crude Oil Pipeline runs 1,443 km from Hoima to TANGA IN TANZANIA --
     which is what makes Uganda and Tanzania one physical system rather than two neighbours. A
     dated, published capacity ramp of roughly 230,000 b/d at plateau into XBRUSD, with the
     Petroleum Authority of Uganda publishing the schedule against which the ramp is measured.
     Uganda is also a top-ten coffee exporter -- robusta, so COFROB and not COFARA -- and the
     Uganda Coffee Development Authority publishes MONTHLY export volumes and values.

AND THE ONE THAT IS A WINDOW RATHER THAN A FLOW. UGANDA'S OFFICIAL GOLD EXPORTS HAVE REPEATEDLY
EXCEEDED ITS OWN MINE PRODUCTION BY AN ORDER OF MAGNITUDE, and both numbers are published -- by
the Bank of Uganda in the balance of payments and by the mirror statistics of the importing
countries in UN Comtrade. The gap is re-export, and the 2021 export levy (Finance Act 2021, in
force 2021-07-01: 5% on unprocessed and a per-kilogram charge on refined gold) made the whole
thing measurable by switching it OFF -- official gold exports collapsed within a quarter and
recovered only after the levy was amended in 2022/2023. That is a lawful, published, dated
window onto an informal regional physical flow into XAUUSD, and EA-M is built on it.

THE CURRENCIES ARE ALL ABSENT AND THE PACK SAYS SO THREE TIMES. ETB, TZS and UGX are not in
`data/universe/universe.json` and never will be. Every one is named in `TRANSMISSION_TARGETS`
with its regime, its parallel-market spread and the broker symbols its economics route into, so
an absent instrument produces a transmission hypothesis and never a cell that can never be
filled (L1.49).

THE GROUND IS BILINGUAL BY LAW AND AN ENGLISH-ONLY CRAWL READS THE WRONG HALF. English is
co-official in all three, so an English crawl returns something for every query and looks
complete. It is not: the National Bank of Ethiopia's directives, the Negarit Gazeta and the
Addis press argue in AMHARIC (Ge'ez script), the Oromia ground is in AFAAN OROMOO, and Tanzania
governs, legislates and reports in KISWAHILI -- Mwananchi, Habari Leo and the Bank of Tanzania's
own Swahili releases are the domestic tape, while The Citizen is the export edition. Uganda
works in English and Kiswahili with Luganda in the popular press. The terminology table and
every source class's queries are written in those languages for exactly that reason.

THE TWO-LANE ORDER (2026-09-06) BINDS HARD HERE. The tempting names in this region are all
single companies -- the gold miners' Tanzanian operating subsidiaries, the mobile-money
operators, the coffee exporters, the airline -- and each is a listed or state-owned single name.
Every one of them appears in this pack as an ACTOR and never as an instrument. No share CFD
appears in any instrument tuple in this file, and no crypto-exchange ground is hunted (mandate
2026-08-18).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "east_africa"
NAME = "East Africa (Ethiopia, Tanzania, Uganda)"
REGION_COMMAND = "africa"
REGION_DESK = "AFRICA"
FOREST = "africa"

#: THE THREE COUNTRIES THIS PACK ANSWERS FOR. `scripts/check_regional_parity.py::jurisdictions_of`
#: reads this tuple and nothing else, so a pack that answers three countries and declares one is
#: credited with one. Ethiopia and Tanzania are on the africa forest's roster and were UNANSWERED;
#: Uganda is claimed here for the first time.
JURISDICTIONS: tuple[str, ...] = ("et", "tz", "ug")

#: The pack-level currency is Ethiopia's, because the float of 2024-07-29 is the single largest
#: regime event in the three and because the framework carries ONE currency per pack. All three
#: are declared here and all three are absent from the broker (see TRANSMISSION_TARGETS).
CURRENCY = "ETB"
CURRENCIES: dict[str, str] = {
    "et": "ETB",   # Ethiopian birr -- crawling peg until 2024-07-28, market-determined since
    "tz": "TZS",   # Tanzanian shilling -- managed float, a measurable 2023-24 dollar shortage
    "ug": "UGX",   # Ugandan shilling -- the most freely floating of the three, IT-lite since 2011
}

#: Ethiopia and Uganda run a 7 July - 30 June fiscal year (Hamle 1 - Sene 30 in the Ethiopian
#: calendar for Ethiopia); Tanzania runs 1 July - 30 June. The framework carries one date, so the
#: pack declares the common June year-end and names Ethiopia's Ge'ez-calendar anchor beside it.
FISCAL_YEAR_END = "06-30"
FISCAL_YEAR_ENDS: dict[str, str] = {
    "et": "07-07 (Ethiopian fiscal year runs Hamle 1 to Sene 30; the Gregorian anchor is 8 July "
          "to 7 July, and the budget is tabled in Ethiopian-calendar years)",
    "tz": "06-30 (the budget is read in the National Assembly in June for a 1 July start)",
    "ug": "06-30 (the budget is read on or about 13 June for a 1 July start)",
}

NATIVE_LANGUAGES: tuple[str, ...] = ("am", "om", "sw", "lg", "ti", "en")
COT_CURRENCY = ""            # no CFTC contract exists for ETB, TZS or UGX
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
MISSION = ("mine East Africa as the three-treasury, one-physical-economy region it is: the Bank "
           "of Tanzania's domestic gold purchase programme and the mandated 20% offer, the "
           "birr's 2024-07-29 float and the ECX coffee and sesame tape, Uganda's Tilenga and "
           "Kingfisher ramp into EACOP at Tanga, the UCDA monthly robusta export print, the "
           "Ugandan gold re-export gap and the 2021 levy that made it measurable, the Dar es "
           "Salaam Central Corridor as the copper and cobalt chokepoint, the GERD filling "
           "schedule against Egypt, and the mobile-money rails that are the only high-frequency "
           "nominal series any of the three publish")

#: The instruments this pack may compile a cell against. Every one is in the broker registry,
#: none is a single-name equity, and each carries the mechanism that put it here.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XAUUSD",                         # Tanzanian production + BoT purchases + Ugandan re-export
    "XAGUSD",                         # Bulyanhulu and Buzwagi are gold-silver-copper ores
    "XCUUSD",                         # the Central Corridor's copper transit out of ZM and CD
    "XNIUSD",                         # Kabanga: one of the largest undeveloped Ni sulphide bodies
    "COFARA",                         # Ethiopian arabica: the crop's birthplace, ~5th producer
    "COFROB",                         # Ugandan and Tanzanian robusta
    "UKCOCOA", "USCOCOA",             # Ugandan and Tanzanian cocoa, and the EUDR traceability leg
    "SUGAR",                          # Kakira/Kilombero cane, the EAC sugar deficit and imports
    "COTTON",                         # Tanzanian and Ugandan lint, both EAC export crops
    "CORN", "WHEAT", "SOYBEAN",       # the import bill, the drought and the sesame-oilseed leg
    "XBRUSD",                         # Uganda's Tilenga/Kingfisher ramp; the import cost leg
    "XNGUSD",                         # Tanzanian gas: Songo Songo, Mnazi Bay and the Lindi LNG
    "USDZAR",                         # the liquid African risk carrier for three absent currencies
    "US500", "UK100",                 # the frontier risk-appetite channel and the London listings
)

#: WHAT THIS PACK CANNOT TRADE, NAMED. Three currencies, three exchanges, one commodity exchange
#: and one crop with no contract anywhere. Each row carries the broker symbols its economics
#: route into; a proxy is a CARRIER and never a substitute, and every edge that uses one says so.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "ETB -- the Ethiopian birr and its parallel-market rate",
     "venue": "National Bank of Ethiopia and the commercial banks' interbank market",
     "regime": "CRAWLING PEG WITH FX RATIONING until 2024-07-28, MARKET-DETERMINED since "
               "2024-07-29; the birr lost more than half its value within weeks of the float",
     "parallel_market": "the hawala and street rate ran at a premium above 100% to the official "
                        "rate through 2023 and into mid-2024 and collapsed toward it after the "
                        "float -- the premium itself is the rationing-stress state EA-A uses",
     "route": "the float is an EXPORT-ECONOMICS event: a birr worth half as much doubles the "
              "local-currency receipt on a dollar coffee sale, which reaches COFARA through "
              "farmgate supply response and through the exporters' willingness to deliver",
     "why": "absent from the broker and not deliverable offshore; every ETB mechanism here "
            "terminates in COFARA, XAUUSD, WHEAT or the risk carriers",
     "proxies": ("COFARA", "XAUUSD", "USDZAR", "WHEAT")},
    {"name": "TZS -- the Tanzanian shilling and the 2023-24 dollar shortage",
     "venue": "Bank of Tanzania Interbank Foreign Exchange Market (IFEM)",
     "regime": "MANAGED FLOAT; the BoT publishes a daily indicative rate and intervenes, and the "
               "shilling depreciated through 2023-2024 under a measurable dollar shortage",
     "parallel_market": "bureau de change rates diverged visibly from the IFEM rate during the "
                        "2023-24 shortage, and the BoT's own bureau survey is the published "
                        "measure of that spread",
     "route": "the shortage is an IMPORT-RATIONING state: it delays fuel and fertiliser cargoes "
              "and it is one of the reasons the central bank wants domestic gold for reserves",
     "why": "absent from the broker; TZS mechanisms terminate in XAUUSD, XBRUSD and USDZAR",
     "proxies": ("XAUUSD", "XBRUSD", "USDZAR")},
    {"name": "UGX -- the Ugandan shilling under inflation targeting",
     "venue": "Bank of Uganda interbank market",
     "regime": "FLOAT with an inflation-targeting-lite framework adopted in July 2011 -- the "
               "first in sub-Saharan Africa after South Africa and Ghana -- steered by the "
               "Central Bank Rate announced at scheduled MPC meetings",
     "parallel_market": "no material parallel market: Uganda has had an open capital account "
                        "since 1997, which is exactly what makes it the CONTROL jurisdiction "
                        "for Ethiopia's rationing and Tanzania's shortage",
     "route": "UGX is the clean float in a three-country panel of one peg, one managed float and "
              "one float, which is the natural experiment EA-N is built on",
     "why": "absent from the broker; UGX mechanisms terminate in COFROB, XBRUSD and USDZAR",
     "proxies": ("COFROB", "XBRUSD", "USDZAR")},
    {"name": "The Ethiopian Commodity Exchange (ECX) coffee and sesame contracts",
     "venue": "ECX, Addis Ababa",
     "regime": "a mandatory-through-exchange regime for export coffee and sesame with daily "
               "published trade data by grade and washing station",
     "parallel_market": "side-selling and contract default were the recurring enforcement "
                        "problem and are reported in the trade press rather than measured",
     "route": "the ECX daily print is the only high-frequency African arabica volume series the "
              "desk can read; it conditions COFARA, it is never traded",
     "why": "no CFD is quoted on any ECX contract",
     "proxies": ("COFARA", "SOYBEAN")},
    {"name": "The Dar es Salaam Stock Exchange (DSEI and TSI indices) and its bond market",
     "venue": "DSE, Dar es Salaam",
     "regime": "a small frontier exchange with a domestic-only index (TSI) beside the all-share "
               "(DSEI); foreign participation is capped in some counters",
     "parallel_market": "n/a",
     "route": "no CFD is quoted; the index level is a frontier risk STATE and the executable leg "
              "is the liquid African risk carrier and the London listings",
     "why": "absent from the broker registry",
     "proxies": ("USDZAR", "UK100")},
    {"name": "The Uganda Securities Exchange (ALSI/LSI) and the Ethiopian Securities Exchange",
     "venue": "USE, Kampala; ESX, Addis Ababa (opened 2025-01-10)",
     "regime": "USE is cross-listed with Nairobi and thin; ESX began trading in January 2025 "
               "with a handful of listings and no public machine-readable tape",
     "parallel_market": "n/a",
     "route": "registered as a STATE, never as a price; the ESX's opening is itself a dated "
              "institutional event EA-D conditions on",
     "why": "absent from the broker registry",
     "proxies": ("USDZAR", "UK100")},
    {"name": "Ethiopian sovereign eurobond (the 2024 maturity) and the restructured claim",
     "venue": "the international bond market",
     "regime": "DEFAULT: the coupon due 2023-12-11 was missed and the grace period expired on "
               "2023-12-26, making Ethiopia the third African default of the cycle after Zambia "
               "and Ghana; restructuring runs under the G20 Common Framework",
     "parallel_market": "n/a",
     "route": "the broker quotes UKGILT, UST05Y and UST10Y and no frontier credit; the default "
              "and the IMF programme reviews are read as RISK-CHANNEL events",
     "why": "absent from the broker registry",
     "proxies": ("USDZAR", "US500")},
    {"name": "TEA -- and the pack refuses to proxy it, exactly as `ke` does",
     "venue": "the Mombasa tea auction",
     "regime": "Ugandan and Tanzanian tea is sold at Mombasa alongside Kenya's",
     "parallel_market": "n/a",
     "route": "NOTHING ADEQUATE. There is no tea contract in the broker registry and coffee is a "
              "different crop with a different buyer base; tea enters this pack as a "
              "CONDITIONING OBSERVABLE for export earnings and never as a price",
     "why": "no tea contract exists anywhere in data/universe/universe.json",
     "proxies": ("COFROB",)},
    {"name": "CASHEW, SESAME and VANILLA -- three export crops with no contract",
     "venue": "the Tanzanian warehouse-receipt auction; the ECX sesame floor; the Ugandan "
              "vanilla trade",
     "regime": "cashew is sold through a state-supervised auction whose collapse in 2018 became "
               "a fiscal event; sesame is ECX-mandated and sold overwhelmingly into China",
     "parallel_market": "cross-border smuggling into Kenya and Mozambique is reported, not "
                        "measured",
     "route": "sesame competes for the same Chinese edible-oil and crush demand as soyabeans, so "
              "SOYBEAN is a WEAK carrier and the pack labels it weak; cashew and vanilla have no "
              "carrier at all and are conditioning observables only",
     "why": "no contract exists for any of the three",
     "proxies": ("SOYBEAN", "COTTON")},
)

# --------------------------------------------------------------------------- central banks
#: THE PACK CARRIES ONE `CENTRAL_BANK` BECAUSE THE FRAMEWORK DOES, and three is the truth. The
#: National Bank of Ethiopia is the primary because its 2024-07-29 float is the largest regime
#: break in the three; the Bank of Tanzania and the Bank of Uganda are declared beside it in
#: `CENTRAL_BANKS` with their own frameworks, and a study that pools the three is pooling a
#: former crawling peg, a managed float and an inflation targeter.
CENTRAL_BANK: dict[str, Any] = {
    "name": "National Bank of Ethiopia (የኢትዮጵያ ብሔራዊ ባንክ)",
    "framework": "managed_float",
    "policy_instrument": "the National Bank Rate (NBR), introduced in July 2024 as the first "
                         "policy rate Ethiopia has ever had, with a standing-facility corridor "
                         "and weekly open-market operations; before it, policy was direct credit "
                         "control, a 27% NBE-bill subscription on private banks (2011-2019) and "
                         "an administered exchange rate",
    "mandate": "price stability and the external position under the 2008 proclamation as amended "
               "by the 2024 National Bank of Ethiopia Proclamation; NO published numeric "
               "inflation target existed before 2024, so a 'surprise' in the earlier era has no "
               "benchmark and the pack says so rather than inventing one",
    "decision_rule": "the Monetary Policy Committee meets on a published schedule (roughly every "
                     "two months since the 2024 reform) and the NBR decision is published on "
                     "nbe.gov.et with a short statement",
    "decision_calendar_rule": "bi-monthly MPC meetings announced at nbe.gov.et since 2024-07; "
                              "before 2024 there was NO decision clock to mine at all, which is "
                              "the binding constraint on EA-A's event sample",
    "decision_dates": (),
    "dates_status": "NOT LISTED, deliberately. The MPC calendar is young, the statements are "
                    "posted without a pinned minute, and this pack refuses to type a date it "
                    "cannot cite (L1.28a). The dated events EA-A is built on are the FLOAT "
                    "(2024-07-29), the directive series around it and the IMF review board "
                    "dates, all of which are citable.",
    "decision_time_utc": "12:00",
    "announce_local": "Addis Ababa is UTC+3 all year with NO daylight saving anywhere in the "
                      "three countries -- East Africa Time is a fixed offset, which makes every "
                      "session window here stable in UTC and is a genuine convenience",
    "dst_rule": "none: EAT is UTC+3 year-round in ET, TZ and UG",
    "minutes_lag_days": 0,
    "publication_classes": ("mpc_statement", "nbe_directive", "quarterly_bulletin",
                            "annual_report", "interbank_fx_rate", "reserve_statistics"),
    "policy_rate_series": "NBE:national_bank_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the 28/91/182/364-day Treasury bill cut-off at the weekly auction and "
                       "the interbank rate; there is no published survey of economists",
    "consensus_proxy_trap": "the T-bill market was a captive one for most of its history -- the "
                            "banks were required to hold the paper -- so a pre-2024 cut-off is a "
                            "REGULATORY number and not an expectation",
    "reserves_clock": "gross reserves are published with a long lag in the NBE bulletin and more "
                      "promptly in the IMF programme documents; the ECF reviews are the reliable "
                      "dated stamp",
    "programme": "IMF Extended Credit Facility approved 2024-07-29, about US$3.4bn over four "
                 "years, with the float as a prior action; reviews are a DISBURSING clock, the "
                 "opposite of Morocco's precautionary line",
    "off_cycle": ("2024-07-29 the float and the accompanying directive package",
                  "2017-10-11 a 15% devaluation, the last of the old regime's step moves"),
    "root": "https://nbe.gov.et",
}

#: The other two, declared rather than folded away. Uganda is the desk's only sub-Saharan
#: inflation targeter outside South Africa and Ghana, and it is the CONTROL for the other two.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "et": {"name": "National Bank of Ethiopia", "framework": "managed_float",
           "rate": "National Bank Rate (NBR), from July 2024",
           "root": "https://nbe.gov.et",
           "why": "a crawling peg with FX rationing until 2024-07-28 and a market-determined "
                  "rate since; the only one of the three with a dated regime break"},
    "tz": {"name": "Bank of Tanzania (Benki Kuu ya Tanzania)", "framework": "managed_float",
           "rate": "the Central Bank Rate, introduced January 2024 when the BoT moved from a "
                   "monetary-aggregate framework to an interest-rate one; announced quarterly",
           "root": "https://www.bot.go.tz",
           "why": "the ONLY central bank in the desk's roster running a formal domestic gold "
                  "purchase programme for reserves -- the reason EA-F is a domain"},
    "ug": {"name": "Bank of Uganda", "framework": "inflation_targeter",
           "rate": "the Central Bank Rate, announced at scheduled MPC meetings roughly every "
                   "two months since July 2011",
           "root": "https://www.bou.or.ug",
           "why": "inflation-targeting-lite since July 2011, the first in sub-Saharan Africa "
                  "after South Africa and Ghana; an open capital account since 1997"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Tanzania IFEM indicative exchange rate",
     "local": "published each business day in the morning, Africa/Dar_es_Salaam (UTC+3)",
     "time_utc": "07:00", "time_utc_dst": "07:00",
     "dst_rule": "none: EAT is UTC+3 year-round",
     "instruments": ("XAUUSD", "USDZAR"), "window_minutes": 60,
     "why": "the rate the importers and the customs value against; its gap to the bureau survey "
            "is the dollar-shortage state EA-I conditions on"},
    {"name": "National Bank of Ethiopia daily interbank/indicative rate",
     "local": "published each business day, Africa/Addis_Ababa (UTC+3)",
     "time_utc": "07:30", "time_utc_dst": "07:30", "dst_rule": "none",
     "instruments": ("COFARA", "XAUUSD"), "window_minutes": 60,
     "why": "before 2024-07-29 this was an ADMINISTERED number and the informative price was the "
            "parallel rate; after it, the two converged, so the same series means two different "
            "things either side of the boundary"},
    {"name": "Bank of Uganda interbank mid-rate",
     "local": "published each business day, Africa/Kampala (UTC+3)",
     "time_utc": "07:30", "time_utc_dst": "07:30", "dst_rule": "none",
     "instruments": ("COFROB", "USDZAR"), "window_minutes": 60,
     "why": "the clean float of the three; the control leg for a rationing or shortage study"},
    {"name": "ECX daily coffee and sesame session close",
     "local": "the Addis trading floor closes early afternoon, Africa/Addis_Ababa",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none",
     "instruments": ("COFARA", "SOYBEAN"), "window_minutes": 90,
     "why": "the only daily African arabica volume-and-price print the desk can read; it lands "
            "BEFORE the New York coffee session opens, which is the whole reason it is useful"},
    {"name": "ICO composite indicator price (the coffee market's own daily benchmark)",
     "local": "published by the International Coffee Organization for the previous session",
     "time_utc": "16:00", "time_utc_dst": "16:00", "dst_rule": "none",
     "instruments": ("COFARA", "COFROB"), "window_minutes": 30,
     "why": "the arabica/robusta group indicators are the reference every East African exporter "
            "prices against, and they separate a CROP story from an exchange story"},
    {"name": "LBMA gold price PM auction",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "why": "the price the Bank of Tanzania's domestic purchases and Uganda's refinery exports "
            "are referenced to; the refinery gate price is a published DISCOUNT to it"},
    {"name": "Dar es Salaam Stock Exchange closing session",
     "local": "16:00 Africa/Dar_es_Salaam", "time_utc": "13:00", "time_utc_dst": "13:00",
     "dst_rule": "none", "instruments": ("USDZAR", "UK100"), "window_minutes": 30,
     "why": "the domestic close; no DSE CFD exists, so the frontier carrier takes the leg"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Tanzania and Bank of Uganda Treasury bill auctions", "kind": "weekday",
     "weekday": 2, "roll": "next", "window_utc": ("06:00", "12:00"),
     "instruments": ("USDZAR", "XAUUSD"),
     "why": "both run Wednesday bill auctions; the cut-off is the domestic rate path and the "
            "bid-to-cover is the banks' appetite for local paper over dollars"},
    {"name": "National Bank of Ethiopia weekly Treasury bill auction", "kind": "weekday",
     "weekday": 3, "roll": "next", "window_utc": ("06:00", "12:00"),
     "instruments": ("COFARA",),
     "why": "weekly, and a CAPTIVE market for most of its history -- the banks were required to "
            "hold the paper, so a pre-2024 cut-off is regulation and not expectation"},
    {"name": "UCDA monthly coffee export report and the ICO month-end", "kind": "month_end",
     "roll": "next", "window_utc": ("06:00", "14:00"), "instruments": ("COFROB", "COFARA"),
     "why": "Uganda publishes the month's export volume and value in the first fortnight of the "
            "following month; the ICO publishes its own monthly at about the same time"},
    {"name": "Month-end importer dollar demand under a rationing or shortage regime",
     "kind": "month_end", "roll": "previous", "window_utc": ("05:00", "13:00"),
     "instruments": ("XBRUSD", "WHEAT", "XAUUSD"),
     "why": "fuel, fertiliser and wheat letters of credit are settled into the last business "
            "days; under rationing this is when the queue is longest and the parallel premium "
            "widest"},
    {"name": "Fiscal year end (30 June) and the three budget speeches", "kind": "fiscal_year_end",
     "roll": "previous", "window_utc": ("06:00", "16:00"),
     "instruments": ("XAUUSD", "XBRUSD", "COFROB"),
     "why": "Tanzania and Uganda read their budgets in June for a 1 July start and Ethiopia's "
            "year turns on 8 July; the gold purchase programme, the Ugandan gold levy and the "
            "mining royalty rates are all BUDGET instruments and change on this boundary"},
    {"name": "Quarter-end IMF programme review and disbursement dates", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("13:00", "20:00"), "instruments": ("USDZAR", "US500"),
     "why": "Ethiopia's ECF reviews and the G20 Common Framework milestones are dated Board "
            "events and are the risk-channel clock of EA-D"},
    {"name": "Ethiopian coffee marketing-year boundary and the new-crop delivery window",
     "kind": "day_of_month", "days": (1,), "months": (10, 11), "roll": "next",
     "window_utc": ("06:00", "14:00"), "instruments": ("COFARA",),
     "why": "the Ethiopian crop year opens in October; the first ECX deliveries of the new crop "
            "and the export contract registrations cluster on that boundary"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Dar es Salaam Stock Exchange (DSE) -- DSEI all-share and TSI domestic index",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "16:00", "open_utc": "07:00", "close_utc": "13:00",
     "dst_rule": "none: EAT is UTC+3 year-round",
     "auction": "continuous trading with an opening and closing call; the exchange is small "
                "enough that a single block can set the day",
     "expiry_rule": "no listed derivatives of any kind; there is no expiry clock to mine",
     "holidays": "the Tanzanian national calendar including the two Eids and Maulid",
     "notes": "NO CFD IS QUOTED on the DSEI or the TSI. The TSI/DSEI SPREAD is the readable "
              "thing -- foreign participation is restricted in some counters, so the two indices "
              "diverge exactly when foreign flow turns, which is a frontier-risk state and not "
              "a price this desk trades"},
    {"name": "Uganda Securities Exchange (USE) -- ALSI and the local share index",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "12:00", "open_utc": "06:30", "close_utc": "09:00",
     "dst_rule": "none",
     "auction": "a short continuous session; several counters are cross-listed from Nairobi",
     "expiry_rule": "no listed derivatives",
     "holidays": "the Ugandan national calendar including the two Eids",
     "notes": "the cross-listings mean a USE move is often a NAIROBI move arriving late, which "
              "is the single most important thing to control for and the reason the `ke` pack "
              "is named in INTERACTIONS"},
    {"name": "Ethiopian Commodity Exchange (ECX) -- coffee, sesame, mung bean, haricot bean",
     "index_symbols": (),
     "open_local": "08:30", "close_local": "13:00", "open_utc": "05:30", "close_utc": "10:00",
     "dst_rule": "none",
     "auction": "open-outcry and electronic sessions by commodity and grade, with daily "
                "published volume, price and washing-station origin",
     "expiry_rule": "spot and warehouse-receipt trading; no futures curve exists",
     "holidays": "the Ethiopian national calendar -- the Ge'ez fixed feasts, Fasika and the Eids",
     "notes": "THE MOST USEFUL EXCHANGE IN THIS PACK and the one with no tradable instrument. "
              "Export coffee and sesame must transact through it, so its daily print is close to "
              "a census of the flow rather than a sample of it"},
    {"name": "Ethiopian Securities Exchange (ESX) -- opened 2025-01-10",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "12:00", "open_utc": "06:00", "close_utc": "09:00",
     "dst_rule": "none",
     "auction": "a young order book with a handful of listings",
     "expiry_rule": "none",
     "holidays": "the Ethiopian national calendar",
     "notes": "REGISTERED AS AN EVENT, NOT AS A TAPE: the opening is a dated institutional fact "
              "that belongs in EA-D's era table, and there is no machine-readable history to "
              "mine yet -- saying so is the measurement (L1.28a)"},
    {"name": "The three interbank FX markets and the licensed bureaux de change",
     "index_symbols": (), "open_local": "08:30", "close_local": "16:00",
     "open_utc": "05:30", "close_utc": "13:00", "dst_rule": "none",
     "auction": "BoT and BoU intervene in the interbank market; the NBE ran an allocation queue "
                "rather than a market until 2024-07-29",
     "expiry_rule": "forwards are thin and mostly bank-to-importer; there is no exchange clock",
     "holidays": "each country's banking calendar",
     "notes": "the bureau-to-interbank spread is the published stress observable in all three, "
              "and it is the only one that survives a regime change intact"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "ea_eat_morning", "start_utc": "05:30", "end_utc": "08:30",
     "notes": "the East African business morning (08:30-11:30 EAT). The fixings, the ECX open "
              "and the bank openings all sit here, and because there is NO daylight saving in "
              "any of the three the window is stable in UTC all year -- unlike Morocco's"},
    {"name": "ea_ecx_session", "start_utc": "05:30", "end_utc": "10:00",
     "notes": "the Ethiopian Commodity Exchange floor; it closes BEFORE the New York coffee "
              "session opens, which is what makes the daily print a candidate lead"},
    {"name": "ea_dse_session", "start_utc": "07:00", "end_utc": "13:00",
     "notes": "the Dar es Salaam equity session"},
    {"name": "ea_london_overlap", "start_utc": "08:00", "end_utc": "13:00",
     "notes": "the overlap with London, when the gold and the soft complexes are liquid and an "
              "East African physical observable can actually reach a price"},
    {"name": "ea_announcement_afternoon", "start_utc": "11:00", "end_utc": "15:00",
     "notes": "the MPC statements, the budget speeches and the ministerial press conferences; "
              "the budget speeches run into the evening EAT and are carried live"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Uganda MPC decision and the Central Bank Rate", "cadence": "bi-monthly",
     "time_utc": "11:00", "source": "Bank of Uganda", "actual_series": "BOU:cbr",
     "expected_series": "UNMEASURED",
     "notes": "the one scheduled, credible policy clock in the three; the statement carries the "
              "inflation forecast revision"},
    {"name": "Bank of Tanzania Central Bank Rate and the Monetary Policy Statement",
     "cadence": "quarterly", "time_utc": "11:00", "source": "Bank of Tanzania",
     "actual_series": "BOT:cbr", "expected_series": "UNMEASURED",
     "notes": "the CBR framework began in January 2024; before that the BoT steered reserve "
              "money, so a policy-surprise study cannot cross that boundary"},
    {"name": "National Bank of Ethiopia MPC statement and the National Bank Rate",
     "cadence": "bi-monthly", "time_utc": "12:00", "source": "National Bank of Ethiopia",
     "actual_series": "NBE:national_bank_rate", "expected_series": "UNMEASURED",
     "notes": "introduced July 2024; there was no policy rate at all before it"},
    {"name": "ECX daily trade data by commodity, grade and origin", "cadence": "daily",
     "time_utc": "11:00", "source": "Ethiopian Commodity Exchange", "actual_series": "ECX:trades",
     "expected_series": "n/a",
     "notes": "volume, price and washing-station origin; the page overwrites, so the vintage is "
              "the crawl somebody took"},
    {"name": "UCDA monthly coffee export volume and value", "cadence": "monthly",
     "time_utc": "09:00", "source": "Uganda Coffee Development Authority",
     "actual_series": "UCDA:exports", "expected_series": "n/a",
     "notes": "bags and dollars by type (robusta/arabica) and by destination, in the first "
              "fortnight of the following month; a genuine counted physical flow"},
    {"name": "Bank of Uganda balance of payments and the gold export line", "cadence": "monthly",
     "time_utc": "09:00", "source": "Bank of Uganda", "actual_series": "BOU:gold_exports",
     "expected_series": "n/a",
     "notes": "THE SERIES EA-M IS BUILT ON: official gold exports that have exceeded domestic "
              "mine production by an order of magnitude, published monthly"},
    {"name": "Bank of Tanzania Monthly Economic Review (reserves, gold, trade, IFEM)",
     "cadence": "monthly", "time_utc": "12:00", "source": "Bank of Tanzania",
     "actual_series": "BOT:reserves", "expected_series": "n/a",
     "notes": "the reserve line is where the domestic gold purchase programme shows up as a "
              "number rather than as a policy announcement"},
    {"name": "NBS Tanzania and UBOS Uganda consumer price index", "cadence": "monthly",
     "time_utc": "08:00", "source": "NBS Tanzania / UBOS",
     "actual_series": "NBS:cpi", "expected_series": "UNMEASURED",
     "notes": "both publish mid-month for the prior month; the food line carries the season"},
    {"name": "Ethiopian Statistical Service consumer price index", "cadence": "monthly",
     "time_utc": "08:00", "source": "Ethiopian Statistical Service",
     "actual_series": "ESS:cpi", "expected_series": "UNMEASURED",
     "notes": "the series that carried the post-float pass-through; the pre-2024 vintages were "
              "collected under an administered exchange rate and are not the same measurement"},
    {"name": "The three budget speeches (June for TZ and UG, July for ET)", "cadence": "annual",
     "time_utc": "13:00", "source": "the three ministries of finance",
     "actual_series": "MOF:budget", "expected_series": "n/a",
     "notes": "the gold purchase mandate, the Ugandan gold levy and the mining royalty rates are "
              "BUDGET instruments; the speech is the event and the Finance Act is the citation"},
    {"name": "Stanbic Uganda and Tanzania PMI", "cadence": "monthly", "time_utc": "06:30",
     "source": "S&P Global / Stanbic Bank", "actual_series": "PMI:ug",
     "expected_series": "UNMEASURED",
     "notes": "the only monthly diffusion index in the three; LICENSED headline, published "
              "summary, and the detail is behind the publisher's terms"},
    {"name": "Petroleum Authority of Uganda project and production updates", "cadence": "irregular",
     "time_utc": "UNMEASURED", "source": "PAU / petroleum.go.ug",
     "actual_series": "PAU:tilenga_kingfisher", "expected_series": "n/a",
     "notes": "the dated schedule the 2025-2026 ramp is measured against; drilling counts, well "
              "completions and the EACOP welding progress are published as milestones"},
)

# --------------------------------------------------------------------------- the Ge'ez calendar
#: ETHIOPIA KEEPS ITS OWN CALENDAR AND IT IS THE MOST DISTINCTIVE CALENDAR FACT IN THE DESK'S
#: WHOLE COUNTRY ROSTER. Thirteen months -- twelve of thirty days and Pagume of five, or six in a
#: leap year -- running about seven years and eight months behind the Gregorian. Ethiopian year N
#: is a leap year when N mod 4 == 3, which puts the extra Pagume day immediately BEFORE the
#: Gregorian leap year, so the new year alternates between 11 and 12 September. Nothing here is
#: typed: `ethiopic_to_gregorian` converts through the Julian day number, and Enkutatash, Meskel
#: and the whole fixed Ethiopian calendar fall out of it.
#:
#: The epoch constant is the Amete Mihret ("year of mercy") epoch used by the Ethiopian civil and
#: church calendars: Meskerem 1 of Ethiopian year 1 is JDN 1724221.
_ETHIOPIC_EPOCH_JDN = 1723856
#: Julian day number of Gregorian 0001-01-01, so `date.toordinal() + this` is a JDN.
_JDN_OF_ORDINAL_ZERO = 1721425
#: The thirteen Ethiopian months, transliterated and in Ge'ez script.
ETHIOPIC_MONTHS: tuple[tuple[str, str], ...] = (
    ("Meskerem", "መስከረም"), ("Tikimt", "ጥቅምት"), ("Hidar", "ኅዳር"), ("Tahsas", "ታኅሳስ"),
    ("Tir", "ጥር"), ("Yekatit", "የካቲት"), ("Megabit", "መጋቢት"), ("Miyazia", "ሚያዝያ"),
    ("Ginbot", "ግንቦት"), ("Sene", "ሰኔ"), ("Hamle", "ሐምሌ"), ("Nehase", "ነሐሴ"),
    ("Pagume", "ጳጉሜ"),
)


def is_ethiopian_leap(ethiopian_year: int) -> bool:
    """True when Pagume has SIX days. Ethiopian year N is leap when N mod 4 == 3, which is the
    year immediately before a Gregorian leap year -- the reason Enkutatash moves to 12 September
    in three-in-four... no: in exactly one year in four, the one FOLLOWING a leap year."""
    return int(ethiopian_year) % 4 == 3


def ethiopic_to_jdn(ethiopian_year: int, month: int, day: int) -> int:
    """Julian day number of an Ethiopian calendar date. Months are 1..13 (13 is Pagume)."""
    if not 1 <= int(month) <= 13:
        raise ValueError(f"Ethiopian month {month!r} is outside 1..13")
    if not 1 <= int(day) <= 30:
        raise ValueError(f"Ethiopian day {day!r} is outside 1..30")
    ey = int(ethiopian_year)
    return (_ETHIOPIC_EPOCH_JDN + 365 + 365 * (ey - 1) + ey // 4
            + 30 * int(month) + int(day) - 31)


def jdn_to_gregorian(jdn: int) -> date:
    """The proleptic Gregorian date of a Julian day number."""
    return date.fromordinal(int(jdn) - _JDN_OF_ORDINAL_ZERO)


def ethiopic_to_gregorian(ethiopian_year: int, month: int, day: int) -> date:
    """One Ethiopian calendar date as a Gregorian date. DERIVED, never typed."""
    return jdn_to_gregorian(ethiopic_to_jdn(ethiopian_year, month, day))


def ethiopian_year_starting_in(gregorian_year: int) -> int:
    """The Ethiopian year whose Meskerem 1 falls in this Gregorian year: G - 7."""
    return int(gregorian_year) - 7


def enkutatash(gregorian_year: int) -> date:
    """ETHIOPIAN NEW YEAR (Meskerem 1, እንቁጣጣሽ) in a Gregorian year: 11 September, or 12
    September when the Ethiopian year that just ended was a leap year. Computed from the Ge'ez
    rule and never typed -- the alternation is exactly what a typed table gets wrong."""
    return ethiopic_to_gregorian(ethiopian_year_starting_in(gregorian_year), 1, 1)


def meskel(gregorian_year: int) -> date:
    """MESKEL (መስቀል, Meskerem 17), the Finding of the True Cross: Enkutatash plus sixteen days,
    so 27 September in three years out of four and 28 September in the fourth."""
    return ethiopic_to_gregorian(ethiopian_year_starting_in(gregorian_year), 1, 17)


def julian_to_gregorian(year: int, month: int, day: int) -> date:
    """A JULIAN calendar date as a Gregorian one. The Ethiopian Orthodox fixed feasts are Julian
    dates -- Genna is 25 December Julian and Timkat is 6 January Julian -- which is why both land
    on a stable Gregorian day this century instead of drifting with the Ethiopian months."""
    a = (14 - int(month)) // 12
    y = int(year) + 4800 - a
    m = int(month) + 12 * a - 3
    jdn = int(day) + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jdn_to_gregorian(jdn)


def genna(gregorian_year: int) -> date:
    """ETHIOPIAN CHRISTMAS (ገና / ልደት, Lidet): 25 December in the JULIAN calendar of the previous
    year, which is 7 January Gregorian throughout 1900-2099."""
    return julian_to_gregorian(int(gregorian_year) - 1, 12, 25)


def timkat(gregorian_year: int) -> date:
    """TIMKAT (ጥምቀት), Ethiopian Epiphany: 6 January Julian, i.e. 19 January Gregorian."""
    return julian_to_gregorian(int(gregorian_year), 1, 6)


def orthodox_easter(gregorian_year: int) -> date:
    """FASIKA (ፋሲካ / ትንሣኤ), Ethiopian Orthodox Easter, by MEEUS' JULIAN ALGORITHM.

    The computus is run on the JULIAN calendar -- that is what makes Orthodox Easter fall where
    it does -- and the result is converted to Gregorian through the Julian day number rather than
    by adding a constant, so the function stays correct past 2100 when the offset changes.
    """
    year = int(gregorian_year)
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return julian_to_gregorian(year, month, day)


def western_easter(gregorian_year: int) -> date:
    """WESTERN (GREGORIAN) EASTER by the Meeus/Butcher algorithm. Tanzania and Uganda close for
    the Western Good Friday and Easter Monday; Ethiopia closes for the Orthodox one, and in most
    years the two are WEEKS apart. A regional holiday study that uses one date for all three is
    mislabelling two countries."""
    year = int(gregorian_year)
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


#: Ethiopia's two rain seasons, and they are NOT Kenya's. Kenya runs long rains (March-May) and
#: short rains (October-December); Ethiopia runs BELG (the small rains, February-May) and KIREMT
#: (the main rains, June-September), and the main crop is harvested from Meher in October-
#: December. A regional drought study that applies the Kenyan season calendar to Ethiopia is
#: measuring the wrong months, which is the single most common error in East African crop work.
ETHIOPIAN_RAIN_SEASONS: dict[str, tuple[int, int]] = {"belg": (2, 5), "kiremt": (6, 9),
                                                      "meher_harvest": (10, 12)}
#: Tanzania is itself two climates: the unimodal south and west (one wet season, November-April)
#: and the bimodal north-east (Masika March-May, Vuli October-December). The Central Corridor
#: road and rail run through the unimodal half.
TANZANIAN_RAIN_SEASONS: dict[str, tuple[int, int]] = {"unimodal_msimu": (11, 4),
                                                      "masika": (3, 5), "vuli": (10, 12)}

#: FIXED SOLAR NATIONAL HOLIDAYS, per jurisdiction. Rows are (month, day, name). None of the
#: three substitutes a weekend holiday onto the Monday as a rule, so a Saturday holiday costs no
#: session -- `market_holidays` drops them for exactly that reason.
FIXED_ET: tuple[tuple[int, int, str], ...] = (
    (3, 2, "Adwa Victory Day / የአድዋ ድል በዓል"),
    (5, 1, "International Labour Day / የሠራተኞች ቀን"),
    (5, 5, "Patriots' Victory Day / የአርበኞች ድል ቀን"),
    (5, 28, "Downfall of the Derg / ደርግ የወደቀበት ቀን"),
)
FIXED_TZ: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year / Mwaka Mpya"),
    (1, 12, "Zanzibar Revolution Day / Mapinduzi ya Zanzibar"),
    (4, 7, "Karume Day / Siku ya Karume"),
    (4, 26, "Union Day / Muungano"),
    (5, 1, "Workers' Day / Siku ya Wafanyakazi"),
    (7, 7, "Saba Saba (International Trade Fair) / Sabasaba"),
    (8, 8, "Nane Nane (Farmers' Day) / Nanenane"),
    (10, 14, "Mwalimu Nyerere Memorial Day / Siku ya Nyerere"),
    (12, 9, "Independence Day / Uhuru"),
    (12, 25, "Christmas / Krismasi"),
    (12, 26, "Boxing Day / Siku ya Kupeana Zawadi"),
)
FIXED_UG: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year / Mwaka Mpya"),
    (1, 26, "NRM Liberation Day"),
    (2, 16, "Archbishop Janani Luwum Day"),
    (3, 8, "International Women's Day"),
    (5, 1, "Labour Day"),
    (6, 3, "Uganda Martyrs' Day"),
    (6, 9, "National Heroes Day"),
    (10, 9, "Independence Day"),
    (12, 25, "Christmas"),
    (12, 26, "Boxing Day"),
)

#: THE ISLAMIC FEASTS ARE TYPED, WITH THE AUTHORITY THAT SIGHTS THEM. Three different bodies
#: announce them in three countries -- the Ethiopian Islamic Affairs Supreme Council (Majlis),
#: the Mufti of Tanzania (with Zanzibar announcing separately), and the Uganda Muslim Supreme
#: Council -- and they do not always agree with each other or with the Gulf. A rule would be a
#: wrong rule, so each row carries (date, name, status) and 2026 is PROJECTED throughout.
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 4, 10), "Eid al-Fitr / Idd el Fitr / ኢድ አል ፈጥር", "ANNOUNCED"),
           (date(2024, 6, 16), "Eid al-Adha / Idd el Hajj / አረፋ", "ANNOUNCED"),
           (date(2024, 9, 16), "Mawlid an-Nabi / Maulid / መውሊድ", "ANNOUNCED")),
    2025: ((date(2025, 3, 31), "Eid al-Fitr / Idd el Fitr / ኢድ አል ፈጥር", "ANNOUNCED"),
           (date(2025, 6, 7), "Eid al-Adha / Idd el Hajj / አረፋ", "ANNOUNCED"),
           (date(2025, 9, 5), "Mawlid an-Nabi / Maulid / መውሊድ", "PROJECTED")),
    2026: ((date(2026, 3, 20), "Eid al-Fitr / Idd el Fitr / ኢድ አል ፈጥር", "PROJECTED"),
           (date(2026, 5, 27), "Eid al-Adha / Idd el Hajj / አረፋ", "PROJECTED"),
           (date(2026, 8, 25), "Mawlid an-Nabi / Maulid / መውሊድ", "PROJECTED")),
}
#: One-off closures and dated clock facts no recurring rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 9, 11): "Enkutatash 2017 EC on 11 September -- the year AFTER a leap year lands "
                       "on the 11th, and 2016 EC landed on the 12th; the alternation is why the "
                       "table is computed",
    date(2025, 1, 10): "the Ethiopian Securities Exchange opened for trading -- not a closure, "
                       "carried here as the dated institutional fact EA-D conditions on",
}


def ethiopian_holidays(year: int) -> dict[date, str]:
    """Ethiopia's closed days in a Gregorian year, every movable one COMPUTED: Genna and Timkat
    from the Julian calendar, Fasika and Siklet from Meeus' Julian computus, Enkutatash and
    Meskel from the Ge'ez rule. Only the Islamic feasts are typed, with their status."""
    out: dict[date, str] = {
        genna(year): "Genna (Ethiopian Christmas) / ገና",
        timkat(year): "Timkat (Epiphany) / ጥምቀት",
        enkutatash(year): "Enkutatash (Ethiopian New Year) / እንቁጣጣሽ",
        meskel(year): "Meskel (Finding of the True Cross) / መስቀል",
    }
    fasika = orthodox_easter(year)
    out[fasika - timedelta(days=2)] = "Siklet (Orthodox Good Friday) / ስቅለት"
    out[fasika] = "Fasika (Ethiopian Orthodox Easter) / ፋሲካ"
    for m, d, name in FIXED_ET:
        out[date(year, m, d)] = name
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def tanzanian_holidays(year: int) -> dict[date, str]:
    """Tanzania's closed days: eleven fixed solar dates, the WESTERN Easter pair, and the three
    Islamic feasts announced by the Mufti (Zanzibar announcing separately)."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_TZ:
        out[date(year, m, d)] = name
    easter = western_easter(year)
    out[easter - timedelta(days=2)] = "Good Friday / Ijumaa Kuu"
    out[easter + timedelta(days=1)] = "Easter Monday / Jumatatu ya Pasaka"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def ugandan_holidays(year: int) -> dict[date, str]:
    """Uganda's closed days: ten fixed solar dates, the WESTERN Easter pair, and the two Eids
    announced by the Uganda Muslim Supreme Council. Uganda does not close for Maulid."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_UG:
        out[date(year, m, d)] = name
    easter = western_easter(year)
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        if "Mawlid" in name:
            continue
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


JURISDICTION_HOLIDAY_FN: dict[str, Any] = {
    "et": ethiopian_holidays, "tz": tanzanian_holidays, "ug": ugandan_holidays}


def national_holidays(year: int) -> dict[date, str]:
    """EVERY closed day in the three jurisdictions, tagged with the countries that close.

    A union table, because this pack answers for three countries at once and a day that closes
    Addis is a normal session in Kampala. The tag is what keeps a study from treating a
    one-country closure as a regional one.
    """
    tagged: dict[date, list[str]] = {}
    names: dict[date, str] = {}
    for code, fn in JURISDICTION_HOLIDAY_FN.items():
        for day, name in fn(year).items():
            tagged.setdefault(day, []).append(code.upper())
            names.setdefault(day, name)
    out = {day: f"{names[day]} [{'+'.join(sorted(codes))}]" for day, codes in tagged.items()}
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = f"{out.get(day, '')} {name}".strip()
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The weekday closures only. A Saturday holiday costs no session and must not enter a
    holiday-liquidity sample as one -- and none of the three substitutes it onto the Monday."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def closed_in(code: str, day: date) -> bool:
    """True when THIS jurisdiction's cash market is closed on this day."""
    fn = JURISDICTION_HOLIDAY_FN.get(str(code).lower())
    return day in fn(day.year) if fn is not None else False


def announced_dates(year: int) -> dict[date, str]:
    """Only the Islamic feasts that were ANNOUNCED. The PROJECTED rows can be a day off in any
    of the three, and the three authorities do not always agree with each other."""
    return {d: n for d, n, st in LUNAR_HOLIDAYS.get(year, ()) if st == "ANNOUNCED"}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_three_calendars_plus_a_declared_lunar_table",
    "authority": "three national labour ministries for the solar days; the Ethiopian Orthodox "
                 "Tewahedo Church for Genna, Timkat, Siklet, Fasika and Meskel; the Ethiopian "
                 "Islamic Affairs Supreme Council, the Mufti of Tanzania (with Zanzibar "
                 "announcing separately) and the Uganda Muslim Supreme Council for the Eids",
    "rule": "ETHIOPIA RUNS THE GE'EZ CALENDAR and its dates are COMPUTED, not typed. Enkutatash "
            "is Meskerem 1, which is 11 September in the Gregorian calendar and 12 September in "
            "the year following an Ethiopian leap year (Ethiopian year N is leap when N mod 4 "
            "== 3); Meskel is Meskerem 17, sixteen days later. Genna (25 December JULIAN) and "
            "Timkat (6 January Julian) are fixed Julian feasts and therefore fall on 7 and 19 "
            "January Gregorian throughout this century. Fasika is ORTHODOX EASTER, computed by "
            "Meeus' JULIAN algorithm and converted through the Julian day number, with Siklet "
            "two days before it. Ethiopia adds four fixed solar days: 2 March (Adwa), 1 May, 5 "
            "May (Patriots') and 28 May (Downfall of the Derg). TANZANIA AND UGANDA run the "
            "Gregorian calendar with WESTERN Easter -- Good Friday and Easter Monday, usually "
            "weeks away from Fasika -- plus eleven and ten fixed solar days respectively, "
            "including Zanzibar Revolution Day (12 Jan), Union Day (26 Apr), Saba Saba (7 Jul), "
            "Nane Nane (8 Aug) and Nyerere Day (14 Oct) for Tanzania and NRM Liberation Day (26 "
            "Jan), Janani Luwum Day (16 Feb), Martyrs' Day (3 Jun) and Heroes Day (9 Jun) for "
            "Uganda. THE ISLAMIC FEASTS ARE TYPED WITH THEIR SIGHTING AUTHORITY because no rule "
            "computes them: Eid al-Fitr, Eid al-Adha and (in ET and TZ only) Mawlid. NO WEEKEND "
            "SUBSTITUTION in any of the three, and NO DAYLIGHT SAVING anywhere -- East Africa "
            "Time is UTC+3 all year, so every session window in this pack is stable in UTC.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed union and "
                     "`ethiopian_holidays`, `tanzanian_holidays` and `ugandan_holidays` are the "
                     "per-jurisdiction tables",
    "market_rule": "the union calendar on weekdays; each exchange keeps its own country's table, "
                   "which is why the union rows are TAGGED with the countries that close",
    "moon_sighting_rule": "DECLARED, not inferred: three authorities, three announcements, and a "
                         "PROJECTED row may be a day off in any of them",
    "moving_feasts": "the Islamic feasts drift about eleven days earlier each solar year; "
                     "Fasika moves on the Julian computus and is usually weeks away from the "
                     "Western Easter that closes Dar es Salaam and Kampala",
    "ethiopian_calendar_rule": "13 months (12 x 30 days + Pagume of 5 or 6); Ethiopian year N is "
                               "leap when N mod 4 == 3; Gregorian year G contains the start of "
                               "Ethiopian year G-7",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED for every Ethiopian and Western movable feast; ANNOUNCED for all "
                     "three Islamic feasts",
               2025: "COMPUTED for the movable feasts; ANNOUNCED for the two Eids and PROJECTED "
                     "for Maulid",
               2026: "COMPUTED for the movable feasts (they are arithmetic, not a sighting); "
                     "PROJECTED for every Islamic row",
               },
    "known_dates": {
        "2024-09-11": "Enkutatash 2017 EC -- 11 September because 2016 EC was not a leap year",
        "2023-09-12": "Enkutatash 2016 EC -- 12 September, because 2015 EC (2015 mod 4 == 3) "
                      "was a leap year and Pagume had six days",
        "2025-01-07": "Genna, and it is 7 January in every year of this century",
        "2025-04-20": "Fasika 2025 -- Orthodox Easter, five weeks after the Western Easter that "
                      "closed Dar es Salaam and Kampala",
        "2024-05-05": "Fasika 2024 fell on Patriots' Victory Day, so Ethiopia lost ONE session "
                      "to two holidays; a naive count double-counts it",
        "2026-09-11": "Enkutatash 2019 EC",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "et_fn": ethiopian_holidays,
    "tz_fn": tanzanian_holidays,
    "ug_fn": ugandan_holidays,
    "announced_fn": announced_dates,
    "enkutatash_fn": enkutatash,
    "fasika_fn": orthodox_easter,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Uganda monthly balance of payments and the gold export line",
     "root": "https://www.bou.or.ug/bouwebsite/Statistics/",
     "fields": ("gold_exports_usd", "gold_exports_kg", "coffee_exports_usd", "total_exports",
                "private_transfers", "reserves_months_of_imports"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "09:00",
     "lag_days": 45, "licence": "free, public", "available": True,
     "why": "the ONE published series in this pack that measures an informal physical flow: "
            "official gold exports have run an order of magnitude above domestic mine "
            "production, and both halves of that comparison are public",
     "pit_warning": "revised for several months after first publication; a cell compiled on a "
                    "first print is a different number from the same month a year later"},
    {"name": "Bank of Tanzania Monthly Economic Review: reserves, IFEM turnover, gold purchases",
     "root": "https://www.bot.go.tz/Publications/Filter/9",
     "fields": ("gross_reserves_usd", "months_of_imports", "ifem_turnover",
                "gold_purchases_domestic", "bureau_vs_ifem_spread"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 35, "licence": "free, public", "available": True,
     "why": "where the domestic gold purchase programme stops being an announcement and becomes "
            "a reserve number; the IFEM turnover is the quantity read that a managed rate hides",
     "pit_warning": "the reserve line is revised and the gold split is not always broken out; "
                    "an absent split is UNMEASURED, never a zero"},
    {"name": "UCDA monthly coffee export report (volume, value, type and destination)",
     "root": "https://ugandacoffee.go.ug/resource-centre/reports",
     "fields": ("bags_60kg", "value_usd", "robusta_share", "arabica_share",
                "destination_country", "average_unit_price"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "09:00",
     "lag_days": 14, "licence": "free, public", "available": True,
     "why": "a counted physical flow from the world's number-two robusta exporter, published in "
            "the first fortnight of the following month -- a real lead on the ICO's own monthly",
     "pit_warning": "restated when late shipments are registered; the FIRST print is what a "
                    "point-in-time cell must use"},
    {"name": "ECX daily trade data by commodity, grade and washing station",
     "root": "https://ecx.com.et/market-data/",
     "fields": ("lot_volume_kg", "price_birr_per_kg", "grade", "washing_station_origin",
                "contracts_traded"),
     "frequency": "daily", "snapshot": "trading session", "publish_utc": "11:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the only daily African arabica volume-and-price print the desk can read, from a "
            "regime in which export coffee MUST transact through the exchange -- closer to a "
            "census of the flow than to a sample of it",
     "pit_warning": "the page OVERWRITES IN PLACE and keeps no history, so the only vintage is "
                    "the crawl somebody took or the Wayback snapshot"},
    {"name": "Tanzania Ports Authority cargo and transit throughput by destination country",
     "root": "https://www.tanzaniaports.go.tz",
     "fields": ("total_tonnage", "transit_tonnage", "transit_by_country", "container_teu",
                "dwell_time_days"),
     "frequency": "monthly / quarterly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 60, "licence": "free, public", "available": True,
     "why": "the Central Corridor's own count of how much Zambian and Congolese copper and "
            "cobalt left through Dar es Salaam; the transit-by-country split is what makes it a "
            "chokepoint observable rather than a national trade statistic",
     "pit_warning": "published irregularly and sometimes only in the annual report; a missing "
                    "month is UNMEASURED and the pack refuses to interpolate it"},
    {"name": "UN Comtrade MIRROR statistics for the gold trade of all three",
     "root": "https://comtradeplus.un.org",
     "fields": ("reported_exports_hs7108", "partner_reported_imports_hs7108", "mirror_gap",
                "partner_country"),
     "frequency": "annual, with monthly for some reporters", "snapshot": "calendar year",
     "publish_utc": "12:00", "lag_days": 365, "licence": "free, public (UN terms)",
     "available": True,
     "why": "the SECOND half of EA-M: what Uganda says it exported against what the United Arab "
            "Emirates and Switzerland say they imported from it; the gap is the measurement",
     "pit_warning": "a year late and heavily revised; it can date an era and can never "
                    "condition a week"},
    {"name": "a CFTC, exchange or dealer positioning series in ETB, TZS or UGX",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no future, no option and no COT contract exists anywhere for ETB, "
            "TZS or UGX, and none of the three is deliverable offshore",
     "pit_warning": "DOES NOT EXIST: positioning in these currencies is UNMEASURED and is never "
                    "proxied by the ZAR COT leg, which is a position in South Africa"},
    {"name": "retail margin or client-flow statistics for any of the three",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Ethiopia forbids residents an offshore margin account outright; "
            "Tanzania's CMSA and Uganda's CMA license a handful of intermediaries and publish "
            "NO aggregate retail positioning, exposure or flow",
     "pit_warning": "DOES NOT EXIST: the retail ecology in EA-P is read from public communities "
                    "and never from a flow statistic, and no microstructure claim here may rest "
                    "on a retail-positioning number"},
)

# --------------------------------------------------------------------------- terminology
#: SIX LANGUAGES AND THE PACK MEANS ALL SIX. English is co-official in all three, which is the
#: trap: an English crawl returns something for every query and reads complete. AMHARIC (Ge'ez
#: script) is the language of the NBE's directives, the Negarit Gazeta and the Addis press;
#: AFAAN OROMOO is the largest first language in Ethiopia and the language of the coffee-growing
#: highlands; KISWAHILI is the language Tanzania legislates, reports and argues in -- Mwananchi
#: and Habari Leo are the domestic tape while The Citizen is the export edition; LUGANDA carries
#: the Ugandan popular press; TIGRINYA is kept for the 2020-2022 conflict era's own ground.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "EA-A": ("ብሔራዊ ባንክ", "የውጭ ምንዛሪ", "ምንዛሪ ተመን", "ጥቁር ገበያ", "ተንሳፋፊ ምንዛሪ", "የገንዘብ ፖሊሲ",
             "የዋጋ ንረት", "ብር", "የባንክ ወለድ", "ማሻሻያ", "buna gatii", "maallaqa",
             "National Bank Rate", "birr float", "parallel market premium",
             "FX rationing queue", "letter of credit backlog"),
    "EA-B": ("ቡና", "የኢትዮጵያ ምርት ገበያ", "ሰሊጥ", "ወጪ ንግድ", "የቡና ዋጋ", "አርሶ አደር", "ማጠቢያ ጣቢያ",
             "buna", "qonnaan bulaa", "Oromiyaa", "Yirgacheffe", "Sidama", "Guji", "Harar",
             "ECX daily trade", "washed arabica", "sun-dried natural", "farmgate price"),
    "EA-C": ("ታላቁ የሕዳሴ ግድብ", "ግድብ", "ውሃ", "ኤሌክትሪክ", "የኃይል ማመንጫ", "ተርባይን", "ዓባይ",
             "bishaan", "humna ibsaa", "GERD filling", "turbine commissioning",
             "power export to Sudan", "Nile water share", "reservoir level"),
    "EA-D": ("ዕዳ", "ብድር", "በጀት", "ዓለም አቀፍ የገንዘብ ድርጅት", "የአክሲዮን ገበያ", "አክሲዮን", "ጉምሩክ",
             "eurobond default", "Common Framework", "Extended Credit Facility",
             "AGOA suspension", "ESX listing", "official creditor committee"),
    "EA-E": ("የኢትዮጵያ አየር መንገድ", "ጭነት", "አበባ", "ቦሌ", "አትክልትና ፍራፍሬ",
             "xiyyaara", "Bole cargo tonnage", "perishables air freight", "cut flowers",
             "cold chain", "belly-hold capacity"),
    "EA-F": ("dhahabu", "Benki Kuu ya Tanzania", "ununuzi wa dhahabu", "akiba ya taifa",
             "Tume ya Madini", "uchimbaji mdogo", "kiwanda cha kusafisha dhahabu", "mrabaha",
             "ወርቅ", "domestic gold purchase", "mandated offer", "refinery licence",
             "royalty in kind", "Geita", "North Mara", "Bulyanhulu", "artisanal output"),
    "EA-G": ("bandari", "Bandari ya Dar es Salaam", "mizigo", "usafirishaji", "reli",
             "Shirika la Reli Tanzania", "shaba", "kobalti", "Kati Koridoo",
             "Central Corridor transit", "copper transit tonnage", "dwell time", "TAZARA",
             "Kasumbalesa", "Kapiri Mposhi"),
    "EA-H": ("korosho", "pamba", "mnada", "stakabadhi ghalani", "ghala", "bodi ya korosho",
             "bei elekezi", "msimu wa mauzo", "cashew auction", "warehouse receipt system",
             "indicative price", "lint export", "sisal"),
    "EA-I": ("shilingi", "uhaba wa dola", "fedha za kigeni", "soko la fedha za kigeni",
             "mfumuko wa bei", "riba", "benki", "maduka ya kubadilisha fedha",
             "IFEM indicative rate", "bureau spread", "dollar shortage", "import cover"),
    "EA-J": ("umeme", "bwawa la Julius Nyerere", "gesi asilia", "TANESCO", "mgao wa umeme",
             "Songo Songo", "Mnazi Bay", "Lindi LNG", "hydropower commissioning",
             "load shedding", "gas-to-power"),
    "EA-K": ("amafuta", "amafuta ga Uganda", "bomba la mafuta", "EACOP", "Tanga",
             "Tilenga", "Kingfisher", "Hoima", "Kabaale refinery",
             "first oil", "plateau production", "central processing facility",
             "Petroleum Authority of Uganda"),
    "EA-L": ("emmwanyi", "kahawa", "robusta", "UCDA", "mauzo nje ya kahawa", "magunia",
             "buna", "monthly export bags", "Elgon arabica", "Mount Rwenzori robusta",
             "coffee sub-sector", "farmgate kiboko price"),
    "EA-M": ("zaabu", "dhahabu", "kodi ya kusafirisha dhahabu", "kiwanda cha kusafisha",
             "African Gold Refinery", "Entebbe", "gold export levy", "re-export gap",
             "mirror statistics", "unprocessed gold", "refined gold per kilogram charge"),
    "EA-N": ("Bank of Uganda", "riba ya benki kuu", "mfumuko wa bei", "ssente", "bbanka",
             "Central Bank Rate", "inflation targeting lite", "core inflation",
             "MPC statement", "open capital account"),
    "EA-O": ("pesa za simu", "M-Pesa", "MTN MoMo", "Airtel Money", "ቴሌብር", "ሞባይል ገንዘብ",
             "wakala", "thamani ya miamala", "mobile money transaction value",
             "agent float", "interoperability", "mobile money tax"),
    "EA-P": ("እንቁጣጣሽ", "ገና", "ጥምቀት", "ፋሲካ", "መስቀል", "ጳጉሜ", "ዓመተ ምሕረት",
             "Idd el Fitr", "Maulid", "Sabasaba", "Nanenane", "Muungano",
             "Ge'ez calendar", "Pagume", "East Africa Time"),
    "EA-Q": ("Mombasa", "Bandari ya Mombasa", "Njia ya Kaskazini", "Nairobi",
             "Northern Corridor", "Jumuiya ya Afrika Mashariki", "East African Community",
             "transit corridor competition", "regional bank treasury", "cross-listing"),
}

#: The Swahili and Amharic working vocabulary the pack must carry, asserted by the tests so this
#: file cannot quietly become an English glossary of three non-English-speaking grounds.
SWAHILI_MARKERS: tuple[str, ...] = (
    "dhahabu", "kahawa", "bandari", "korosho", "pamba", "shilingi", "umeme", "mnada",
    "mizigo", "mfumuko wa bei", "pesa za simu", "uhaba wa dola", "Tume ya Madini",
    "stakabadhi ghalani", "bwawa la Julius Nyerere")
OROMO_MARKERS: tuple[str, ...] = ("buna", "qonnaan bulaa", "Oromiyaa", "bishaan", "maallaqa")

#: Ethiopic (Ge'ez) covers the main block plus the supplements the web actually serves.
_ETHIOPIC_RANGES = ((0x1200, 0x137F), (0x1380, 0x139F), (0x2D80, 0x2DDF), (0xAB00, 0xAB2F))

SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


#: SWAHILI AND LUGANDA ARE WRITTEN IN LATIN SCRIPT, so a codepoint test cannot find them and a
#: WORD test is the only honest one. These are closed-class and high-frequency tokens of the two
#: languages -- grammatical particles and the trade vocabulary this pack actually queries in --
#: matched as whole words so that "Kenya" does not read as the Swahili genitive "ya".
_SWAHILI_WORDS: frozenset[str] = frozenset({
    "ya", "wa", "za", "la", "na", "kwa", "cha", "kwenye", "bei", "soko", "sokoni", "benki",
    "kuu", "dhahabu", "kahawa", "mizigo", "madini", "pesa", "mauzo", "taarifa", "uchumi",
    "fedha", "riba", "bandari", "mnada", "uzalishaji", "umeme", "kodi", "sheria", "biashara",
    "bomba", "mafuta", "gesi", "reli", "wakala", "miamala", "utafiti", "programu", "mvua",
    "ukame", "korosho", "pamba", "jinsi", "leo", "nje", "hisa", "serikali", "tume", "uhaba",
    "dola", "simu", "ripoti", "bajeti", "mfumuko", "watumiaji", "thamani", "mrabaha", "masoko",
    "mikoa", "kiwanda", "kusafisha", "leseni", "takwimu", "mwezi", "nchi", "jirani", "bwawa",
    "mgao", "maendeleo", "vyanzo", "wanasema", "wachambuzi", "inasema", "yatangaza", "imepanda",
    "umeanza", "mujibu", "tathmini", "sera", "mwenendo", "uchambuzi", "kuwekeza", "kubadilisha",
    "maduka", "elekezi", "uwazi", "utabiri", "kisasa", "asilia", "mazao", "zamani", "kumbukumbu",
    "mdogo", "uchimbaji", "akiba", "kigeni", "ununuzi", "hali", "mwaka", "uliolipwa", "tangazo",
    "gazeti", "stakabadhi", "ghalani", "kupeana"})
_LUGANDA_WORDS: frozenset[str] = frozenset({
    "emmwanyi", "bbeeyi", "zaabu", "ssente", "bbanka", "nkola", "gavumenti", "ebika",
    "enkyukakyuka", "ng'eragirwa", "amafuta"})


def _words(text: str) -> list[str]:
    return ["".join(ch for ch in w if ch.isalpha() or ch == "'").lower()
            for w in str(text).split()]


def has_ethiopic(text: str) -> bool:
    """True when the text carries at least one Ge'ez (Ethiopic) codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _ETHIOPIC_RANGES) for ch in str(text))


def has_swahili(text: str) -> bool:
    """True when the text carries at least one Swahili word. A WORD test, not a substring one:
    'Kenya' must not read as the genitive particle 'ya'."""
    return any(w in _SWAHILI_WORDS for w in _words(text))


def has_luganda(text: str) -> bool:
    """True when the text carries at least one Luganda word. Uganda's popular press and its
    farmgate coffee reporting run in Luganda and an English-only crawl never sees them."""
    return any(w in _LUGANDA_WORDS for w in _words(text))


def has_native(text: str) -> bool:
    """True when a query is written in ANY of this pack's native grounds rather than in English.
    The Oromo markers are Latin-script too and are checked as words for the same reason."""
    return (has_ethiopic(text) or has_swahili(text) or has_luganda(text)
            or any(w in {m.lower() for m in OROMO_MARKERS} for w in _words(text)))


def ethiopic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_ethiopic(t)]


def swahili_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared Swahili marker actually present in the terminology table."""
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in SWAHILI_MARKERS if any(m in t for t in flat)]


def oromo_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in OROMO_MARKERS if any(m in t for t in flat)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=True`
    registers ground whose terms forbid extraction: never scraped, never omitted."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r}")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r}")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this region has nothing in, declared BY NAME with the reason (L1.28a)."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "ea_nbe", "National Bank of Ethiopia: directives, the MPC statement and the National "
                  "Bank Rate, daily indicative FX rates, the quarterly bulletin and reserves",
        layer="official",
        roots=("https://nbe.gov.et", "https://nbe.gov.et/directives/",
               "https://nbe.gov.et/monetary-policy/", "https://nbe.gov.et/publications/"),
        queries=("የኢትዮጵያ ብሔራዊ ባንክ መመሪያ", "የምንዛሪ ተመን", "የገንዘብ ፖሊሲ ኮሚቴ", "ተንሳፋፊ ምንዛሪ",
                 "የውጭ ምንዛሪ ክምችት", "የባንክ ወለድ ምጣኔ", "National Bank Rate directive",
                 "foreign exchange directive 2024", "interbank foreign exchange market"),
        languages=("am", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (nbe.gov.et terms)",
        notes="THE DIRECTIVE IS THE EVENT of EA-A: the July 2024 package that floated the birr "
              "is a numbered directive with a date on it, and the Amharic and English texts are "
              "posted together, which is the cheapest place to learn this ground's vocabulary"),
    source_class(
        "ea_et_state", "Ethiopian Statistical Service (CPI, national accounts), Ministry of "
                       "Finance (budget, debt, the ECF programme), the Customs Commission and "
                       "the Ministry of Mines", layer="official",
        roots=("https://www.statsethiopia.gov.et", "https://www.mofed.gov.et",
               "https://www.customs.gov.et", "https://www.mom.gov.et"),
        queries=("የዋጋ ንረት መጠን", "የሸማቾች ዋጋ መረጃ ጠቋሚ", "ዓመታዊ በጀት", "የውጭ ዕዳ", "ጉምሩክ ታሪፍ",
                 "የማዕድን ወጪ ንግድ", "Ethiopian fiscal year budget proclamation",
                 "external debt bulletin", "customs tariff schedule"),
        languages=("am", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CPI vintages before 2024-07 were collected under an administered exchange "
              "rate and a rationed import regime; the same series after the float is measuring "
              "a different economy, which is why EA-A's era boundary is not optional"),
    source_class(
        "ea_bot", "Bank of Tanzania: the Monthly Economic Review, the Monetary Policy "
                  "Statement and the Central Bank Rate, IFEM rates, reserves, the National "
                  "Payment Systems report and the DOMESTIC GOLD PURCHASE disclosures",
        layer="official",
        roots=("https://www.bot.go.tz", "https://www.bot.go.tz/Publications/Filter/9",
               "https://www.bot.go.tz/FinancialMarkets/InterbankForeignExchangeMarket",
               "https://www.bot.go.tz/Publications/Filter/4"),
        queries=("Benki Kuu ya Tanzania taarifa", "ununuzi wa dhahabu benki kuu",
                 "akiba ya fedha za kigeni", "riba ya benki kuu", "soko la fedha za kigeni",
                 "uhaba wa dola", "taarifa ya hali ya uchumi", "monetary policy statement",
                 "gold purchase programme reserves"),
        languages=("sw", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY CENTRAL BANK IN THE DESK'S ROSTER THAT BUYS DOMESTIC GOLD FOR RESERVES. "
              "The BoT publishes in Swahili and English side by side and the Swahili release is "
              "often the earlier one, so an English-only crawl of Tanzania is late as well as "
              "partial"),
    source_class(
        "ea_tz_state", "National Bureau of Statistics (CPI, trade), the MINING COMMISSION "
                       "(production, royalties, licences, mineral markets), the Tanzania "
                       "Revenue Authority and the Ministry of Finance budget documents",
        layer="official",
        roots=("https://www.nbs.go.tz", "https://www.madini.go.tz", "https://www.tra.go.tz",
               "https://www.mof.go.tz"),
        queries=("Tume ya Madini takwimu", "uzalishaji wa dhahabu", "mrabaha wa madini",
                 "masoko ya madini", "mfumuko wa bei Tanzania", "biashara ya nje",
                 "bajeti ya serikali", "Finance Act mining royalty", "mineral market centres"),
        languages=("sw", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Mining Commission's regional MINERAL MARKET CENTRES are where artisanal gold "
              "is bought and taxed, so its statistics are the artisanal half of the 50-tonne "
              "number that the listed miners' reports do not contain"),
    source_class(
        "ea_bou", "Bank of Uganda: the MPC statement and Central Bank Rate, the balance of "
                  "payments with its GOLD EXPORT line, the interbank rate, reserves and the "
                  "mobile-money statistics", layer="official",
        roots=("https://www.bou.or.ug", "https://www.bou.or.ug/bouwebsite/Statistics/",
               "https://www.bou.or.ug/bouwebsite/MonetaryPolicy/"),
        queries=("riba ya benki kuu Uganda", "mauzo ya dhahabu nje", "mfumuko wa bei",
                 "Central Bank Rate statement", "balance of payments gold exports",
                 "mobile money transaction value", "private sector credit", "reserve adequacy"),
        languages=("en", "sw", "lg"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE GOLD EXPORT LINE IS THE POINT: published monthly, it has run an order of "
              "magnitude above Uganda's own mine production, and the 2021 levy switched it off "
              "and then back on again -- a natural experiment with a public series on both sides"),
    source_class(
        "ea_ug_state", "UBOS (CPI, trade, GDP), the Uganda Revenue Authority (the gold export "
                       "levy and customs), the UCDA coffee reports, the Petroleum Authority of "
                       "Uganda and the Ministry of Finance budget", layer="official",
        roots=("https://www.ubos.org", "https://ura.go.ug", "https://ugandacoffee.go.ug",
               "https://www.petroleum.go.ug", "https://www.finance.go.ug"),
        queries=("mauzo ya kahawa nje", "bei ya kahawa", "kodi ya dhahabu",
                 "UCDA monthly report bags", "Tilenga project status",
                 "Kingfisher development", "EACOP progress", "budget speech Uganda",
                 "emmwanyi ebika"),
        languages=("en", "sw", "lg"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="UCDA publishes BAGS AND DOLLARS BY TYPE AND DESTINATION within a fortnight of "
              "the month end, which is a counted physical flow from the world's number-two "
              "robusta exporter and a genuine lead on the ICO's own monthly"),
    # ---- institutional
    source_class(
        "ea_exchanges", "The four exchanges and their regulators: the Dar es Salaam Stock "
                        "Exchange and CMSA, the Uganda Securities Exchange and CMA, the "
                        "Ethiopian Commodity Exchange, and the Ethiopian Securities Exchange "
                        "with the Ethiopian Capital Market Authority", layer="institutional",
        roots=("https://www.dse.co.tz", "https://www.cmsa.go.tz", "https://www.use.or.ug",
               "https://cmauganda.co.ug", "https://ecx.com.et", "https://ecma.gov.et"),
        queries=("soko la hisa Dar es Salaam", "taarifa ya soko la hisa", "hisa za kigeni",
                 "የኢትዮጵያ ምርት ገበያ ዕለታዊ", "የአክሲዮን ገበያ", "daily market report DSE",
                 "USE all share index", "ECX daily trade data", "ESX listing rules"),
        languages=("sw", "en", "am"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ECX IS THE VALUABLE ONE and it has no tradable instrument: export coffee and "
              "sesame must transact through it, so its daily print is close to a census. The "
              "DSE's TSI/DSEI spread is the foreign-participation state; the ESX has no history"),
    source_class(
        "ea_industry_bodies", "The trade bodies and the transparency initiatives: the Tanzania "
                              "Chamber of Minerals and Energy, the Cashewnut Board, the "
                              "Tanzania Coffee Board, the Ethiopian Coffee and Tea Authority, "
                              "the Uganda Manufacturers Association, TEITI and Uganda EITI",
        layer="institutional",
        roots=("https://www.teiti.go.tz", "https://www.ueiti.go.ug",
               "https://www.coffeeboard.or.tz", "https://www.cashew.go.tz",
               "https://www.tcme.or.tz"),
        queries=("bodi ya korosho taarifa", "mnada wa korosho", "bei elekezi ya korosho",
                 "ripoti ya uwazi wa madini", "የቡና እና ሻይ ባለስልጣን",
                 "EITI reconciliation report", "coffee board auction results",
                 "chamber of minerals budget submission"),
        languages=("sw", "en", "am"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the EITI reconciliations are the one place where company-declared mineral "
              "payments and government-declared receipts are put side by side, which is the "
              "only independent read on the artisanal and smuggled share of production"),
    source_class(
        "ea_imf_wb", "IMF country pages for all three (Article IV, the Ethiopian ECF reviews, "
                     "the Common Framework documents), the World Bank economic updates and the "
                     "African Development Bank outlooks", layer="institutional",
        roots=("https://www.imf.org/en/Countries/ETH", "https://www.imf.org/en/Countries/TZA",
               "https://www.imf.org/en/Countries/UGA",
               "https://www.worldbank.org/en/country/ethiopia"),
        queries=("Ethiopia Extended Credit Facility review", "Ethiopia Article IV exchange rate",
                 "Tanzania Article IV reserves", "Uganda Article IV inflation targeting",
                 "Common Framework debt treatment Ethiopia", "arrears to bondholders"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ECF staff reports carry the ONLY public reconstruction of Ethiopia's parallel "
              "premium and its FX backlog, which are the two series EA-A needs and the NBE does "
              "not publish; the review dates are a DISBURSING clock, unlike Morocco's"),
    # ---- academic
    source_class(
        "ea_academic_et", "Addis Ababa University, the Policy Studies Institute (formerly EDRI), "
                          "the Ethiopian Economics Association, Jimma and Haramaya (coffee "
                          "agronomy) and the Ethiopian Journal of Economics",
        layer="academic",
        roots=("https://www.aau.edu.et", "https://psi.gov.et", "https://eea-et.org",
               "https://www.ju.edu.et"),
        queries=("የምንዛሪ ተመን ማሻሻያ ጥናት", "የቡና ምርታማነት", "የዋጋ ንረት መንስኤ",
                 "exchange rate pass-through Ethiopia", "coffee value chain Ethiopia",
                 "parallel market premium Ethiopia", "buna qorannoo"),
        languages=("am", "en", "om"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the Jimma and Haramaya agronomy is what turns 'Ethiopia grows coffee' into a "
              "mechanism: altitude, shade and washing-station capacity decide how much of a "
              "farmgate price move can reach an exportable grade at all"),
    source_class(
        "ea_academic_tzug", "University of Dar es Salaam, ESRF and REPOA in Tanzania; Makerere "
                            "and the Economic Policy Research Centre in Uganda; the African "
                            "Economic Research Consortium; and the open indexes (OpenAlex, "
                            "CORE, AJOL)", layer="academic",
        roots=("https://www.udsm.ac.tz", "https://www.repoa.or.tz", "https://eprcug.org",
               "https://openalex.org", "https://www.ajol.info"),
        queries=("utafiti wa uchumi Tanzania", "sera ya fedha", "biashara ya madini utafiti",
                 "artisanal gold mining Tanzania study", "coffee smallholder Uganda",
                 "oil revenue management Uganda", "corridor transport costs East Africa"),
        languages=("sw", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="REPOA and EPRC publish the corridor-cost and artisanal-mining fieldwork that no "
              "official series contains; every paper is a HYPOTHESIS until the desk reproduces "
              "it, and the ones that matter here are the ones with a number in them"),
    # ---- practitioner
    source_class(
        "ea_bank_research", "The regional bank and broker research that is published openly: "
                            "Stanbic and Absa Africa research, NCBA and CRDB market notes, "
                            "Renaissance Capital and Frontier-desk East Africa notes, and the "
                            "Stanbic PMI releases", layer="practitioner",
        roots=("https://www.stanbicbank.co.ug", "https://www.crdbbank.co.tz",
               "https://www.absa.africa/absaafrica/insights/",
               "https://www.pmi.spglobal.com"),
        queries=("taarifa ya soko la fedha", "utabiri wa riba", "market commentary shilling",
                 "PMI Uganda output", "Tanzania fixed income weekly",
                 "Ethiopia birr outlook note"),
        languages=("en", "sw"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="there is no published consensus for any of the three policy rates, so these notes "
              "are the closest thing to an expectation the region has; they are kept as the "
              "EXPECTATION source EA-N measures a surprise against, never as a view adopted"),
    source_class(
        "ea_commodity_trade_press", "The commodity trade desks' own press: Global Coffee Report "
                                    "and the Coffee Barometer, Mining Review Africa and "
                                    "MiningWeekly, African Energy and the Africa Oil+Gas "
                                    "Report, Public Ledger and the cashew trade letters",
        layer="practitioner",
        roots=("https://www.globalcoffeereport.com", "https://www.miningreview.com",
               "https://africa-oilgas.com", "https://www.publicledger.com"),
        queries=("Uganda robusta crop estimate", "Ethiopia coffee export season",
                 "Tanzania gold refinery licence", "EACOP line pipe delivery",
                 "cashew auction Tanzania season", "Central Corridor copper volumes"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms; some titles paywalled",
        notes="the trade letters date a refinery licence, a crop estimate or a pipeline delivery "
              "WEEKS before the official page updates, and they are where an EA-F or EA-K "
              "milestone first becomes citable at all"),
    # ---- retail ecology
    source_class(
        "ea_retail_communities", "Public retail communities: r/Ethiopia, r/Tanzania, r/Uganda, "
                                 "the Facebook investment and diaspora-remittance groups, the "
                                 "Amharic and Swahili personal-finance YouTube channels, and "
                                 "the DSE/USE shareholder forums", layer="retail_ecology",
        roots=("https://www.reddit.com/r/Ethiopia/", "https://www.reddit.com/r/Uganda/",
               "https://www.youtube.com/results?search_query=%E1%8B%B5%E1%88%AD%E1%88%B5"),
        queries=("ጥቁር ገበያ ዶላር ዋጋ", "ወርቅ ዋጋ ዛሬ", "እንዴት ብር ማዳን", "bei ya dhahabu leo",
                 "jinsi ya kuwekeza hisa", "dola sokoni leo", "remittance rate Ethiopia"),
        languages=("am", "sw", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT and never a source of edge. It earns its place for ONE thing: "
              "the diaspora and street vocabulary around the dollar premium DATES the Ethiopian "
              "rationing episodes to the week, which no official series does"),
    source_class(
        "ea_forex_sellers", "Amharic and Swahili 'forex' signal sellers and prop-firm affiliates "
                            "on Telegram, WhatsApp, TikTok and YouTube targeting East African "
                            "retail", layer="retail_ecology",
        roots=("https://t.me/s/forexethiopia",
               "https://www.youtube.com/results?search_query=forex+swahili"),
        queries=("ፎሬክስ ትሬዲንግ", "የወርቅ ትሬዲንግ", "forex kwa kiswahili", "biashara ya dhahabu mtandao",
                 "prop firm challenge Uganda", "signals za forex bure"),
        languages=("am", "sw", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="ILLEGAL IN ETHIOPIA AND ADVERTISED ANYWAY: residents may not fund an offshore "
              "margin account, so this ground measures an unlicensed retail base and never a "
              "regulated flow. Kept because the XAUUSD stop clusters it advertises are a real "
              "microstructure observable, and because NO regulator in the three publishes a "
              "retail flow statistic to compare it with"),
    # ---- app ecosystem
    source_class(
        "ea_mobile_money", "MOBILE MONEY IS THE APP ECOSYSTEM HERE: M-Pesa and Mixx by Yas in "
                           "Tanzania, MTN MoMo and Airtel Money in Uganda, telebirr in "
                           "Ethiopia -- and their statistics are PUBLISHED by the central banks "
                           "and the regulators, monthly", layer="app_ecosystem",
        roots=("https://www.bou.or.ug/bouwebsite/Statistics/",
               "https://www.bot.go.tz/Publications/Filter/13", "https://www.tcra.go.tz",
               "https://www.ethiotelecom.et"),
        queries=("thamani ya miamala ya pesa za simu", "watumiaji wa pesa za simu",
                 "wakala wa pesa za simu", "ቴሌብር ተጠቃሚ", "ሞባይል ገንዘብ ዝውውር",
                 "mobile money transaction value monthly", "agent banking statistics",
                 "interoperability mobile money"),
        languages=("sw", "am", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONE HIGH-FREQUENCY NOMINAL SERIES ANY OF THE THREE PUBLISH. Transaction value "
              "and agent float are a monthly nominal-demand read with a two-to-six week lag, "
              "against national accounts that arrive annually -- which is why declaring this "
              "layer absent, as a desk that only knows app stores would, is simply wrong"),
    source_class(
        "ea_app_rails_and_prices", "The rest of the app layer: bank and brokerage apps (CRDB "
                                   "SimBanking, Stanbic FlexiPay, CBE Birr), the DSE and USE "
                                   "mobile market feeds, the agricultural price apps and SMS "
                                   "services, and PUBLIC COMMENTARY on the peer-to-peer "
                                   "stablecoin premium as a capital-control observable",
        layer="app_ecosystem",
        roots=("https://play.google.com/store/search?q=CRDB%20SimBanking",
               "https://www.dse.co.tz/mobile", "https://www.esoko.com"),
        queries=("programu ya benki", "bei za mazao kwa simu", "የባንክ መተግበሪያ",
                 "USSD banking code", "agri price SMS service", "P2P premium commentary"),
        languages=("sw", "am", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform and publisher terms",
        notes="PUBLIC COMMENTARY ONLY on the P2P premium: no venue feed, no order book and no "
              "exchange named as a source (mandate 2026-08-18). The premium is carried at low "
              "weight beside the bureau-de-change spread and never instead of it"),
    # ---- media
    source_class(
        "ea_media_am", "The Ethiopian press: Fana Broadcasting, EBC, Addis Fortune, Addis "
                       "Standard, The Reporter (Amharic and English editions), Capital Ethiopia "
                       "and Ethiopian News Agency", layer="media",
        roots=("https://www.fanabc.com", "https://addisfortune.news",
               "https://addisstandard.com", "https://www.ena.et"),
        queries=("ብሔራዊ ባንክ አስታወቀ", "የዶላር ምንዛሪ ተመን", "የቡና ወጪ ንግድ", "ታላቁ የሕዳሴ ግድብ",
                 "የዋጋ ንረት", "birr devaluation reaction", "coffee export earnings Ethiopia",
                 "GERD turbine"),
        languages=("am", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Addis Fortune is the business paper of record and carries the directive's effect "
              "on the banks days before the NBE's own page explains it; Fana is the fastest "
              "stamp for a ministerial statement and the Amharic edition is the earlier one"),
    source_class(
        "ea_media_sw", "The Tanzanian press: Mwananchi and Habari Leo in Swahili, The Citizen "
                       "and Daily News in English, Nipashe, and the TBC/ITV business bulletins",
        layer="media",
        roots=("https://www.mwananchi.co.tz", "https://www.habarileo.co.tz",
               "https://www.thecitizen.co.tz", "https://dailynews.co.tz"),
        queries=("benki kuu yatangaza", "bei ya dhahabu", "mnada wa korosho", "uhaba wa dola",
                 "bandari ya Dar es Salaam", "bomba la mafuta", "bajeti ya serikali",
                 "mrabaha wa madini"),
        languages=("sw", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="AN ENGLISH-ONLY CRAWL OF TANZANIA MISSES THE ENTIRE DOMESTIC GROUND. Mwananchi "
              "and Habari Leo carry the cashew indicative price, the mineral market centre "
              "disputes and the fuel queue as they happen; The Citizen is the export edition "
              "and reports a subset, later"),
    source_class(
        "ea_media_ug", "The Ugandan press: Daily Monitor, New Vision, Bukedde (Luganda), The "
                       "Independent, The Observer and NBS/NTV business bulletins", layer="media",
        roots=("https://www.monitor.co.ug", "https://www.newvision.co.ug",
               "https://www.independent.co.ug", "https://observer.ug"),
        queries=("emmwanyi bbeeyi", "zaabu Uganda", "bei ya kahawa Uganda",
                 "gold export levy", "Tilenga drilling", "EACOP compensation",
                 "coffee farmers price", "Bank of Uganda rate"),
        languages=("en", "lg", "sw"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the Ugandan press reported the gold refineries' response to the 2021 levy in real "
              "time, months before the balance-of-payments series showed the collapse; Bukedge "
              "and the Luganda bulletins carry the farmgate coffee price the English papers "
              "round off"),
    source_class(
        "ea_licensed_assessments", "Licensed terminals and price reporting agencies: Bloomberg "
                                   "and LSEG for the three currencies' offshore quotes, the "
                                   "S&P Global PMI detail, Public Ledger for cashew and sesame, "
                                   "and Fastmarkets for cobalt and copper concentrate",
        layer="media",
        roots=("https://www.publicledger.com", "https://www.fastmarkets.com"),
        queries=("Tanzania cashew kernel assessment", "sesame seed cfr China assessment",
                 "cobalt hydroxide payable", "copper concentrate TC RC"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED. The cashew and sesame assessments are the actual "
              "prices of two of this region's largest export crops and both are paywalled, "
              "which is exactly why EA-H is measured on COTTON and the state auction's own "
              "published indicative price instead -- the absence is named rather than worked "
              "around, and the same is true of the cobalt payable behind EA-G"),
    # ---- archive
    source_class(
        "ea_gazettes", "The three official gazettes and the parliamentary records: the Federal "
                       "Negarit Gazeta, the Tanzania Government Gazette and the Uganda Gazette, "
                       "plus the Finance Acts, the mining and petroleum statutes and the "
                       "Hansards", layer="archive",
        roots=("https://www.fdregazette.gov.et", "https://www.parliament.go.tz",
               "https://www.parliament.go.ug", "https://ulii.org", "https://tanzlii.org"),
        queries=("ነጋሪት ጋዜጣ አዋጅ", "የገንዘብ አዋጅ", "sheria ya fedha", "sheria ya madini",
                 "Finance Act gold export levy", "Mining Act amendment 2017",
                 "Petroleum Act Uganda", "gazette notice mineral royalty"),
        languages=("am", "sw", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE GAZETTE IS WHERE A LEVY OR A MANDATED OFFER BECOMES CITABLE. Every dated "
              "claim in EA-F and EA-M -- the 2021 Ugandan gold levy, the Tanzanian 20% domestic "
              "offer, the 2017 concentrate export ban -- has a Finance Act or a gazette notice "
              "behind it, and a press date without one stays PRESS_REPORTED"),
    source_class(
        "ea_wayback", "web.archive.org snapshots of the pages that overwrite in place: the ECX "
                      "market-data table, the BoT IFEM rate page, the UCDA report index, the TPA "
                      "throughput page and the NBE daily rate table", layer="archive",
        roots=("https://web.archive.org/web/*/ecx.com.et*",
               "https://web.archive.org/web/*/bot.go.tz*",
               "https://web.archive.org/web/*/ugandacoffee.go.ug*"),
        queries=("ecx market data archive", "bot exchange rate archive",
                 "ucda monthly report archive", "tanzaniaports throughput archive",
                 "takwimu za zamani za bandari", "kumbukumbu ya bei ya dhahabu",
                 "የቀድሞ የምንዛሪ ተመን መረጃ"),
        languages=("en", "am", "sw"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="EVERY HIGH-FREQUENCY SERIES IN THIS PACK LIVES ON A PAGE THAT SHOWS TODAY AND "
              "KEEPS NO HISTORY. Without this layer the ECX daily print, the IFEM rate and the "
              "TPA throughput are reconstructible only from press quotes, and a cell compiled on "
              "an un-archived month is UNMEASURED rather than assumed"),
    # ---- physical economy
    source_class(
        "ea_ports_corridor", "The physical trade routes: Tanzania Ports Authority (Dar es "
                             "Salaam, Tanga, Mtwara), the Central Corridor Transit Transport "
                             "Facilitation Agency, TAZARA and the Tanzanian SGR, and the "
                             "Ethiopian corridor to Djibouti", layer="physical_economy",
        roots=("https://www.tanzaniaports.go.tz", "https://centralcorridor-ttfa.org",
               "https://www.tazarasite.com", "https://www.trc.co.tz"),
        queries=("mizigo ya bandari", "mizigo ya nchi jirani", "Kati Koridoo takwimu",
                 "reli ya kisasa mizigo", "transit cargo DRC Zambia",
                 "Dar es Salaam port dwell time", "Djibouti corridor Ethiopia"),
        languages=("sw", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="DAR ES SALAAM IS THE CHOKEPOINT THAT MAKES THIS PACK A COPPER PACK. The transit "
              "split by destination country is the Zambian and Congolese metal leaving through "
              "Tanzania, and the corridor agency publishes the transit times that say whether "
              "the route is working -- the physical counterpart of EA-G"),
    source_class(
        "ea_energy_water", "The power and hydrocarbon plane: TANESCO and the Julius Nyerere "
                           "hydropower project, Ethiopian Electric Power and the GERD, UETCL "
                           "and the Uganda Electricity Regulatory Authority, the Petroleum "
                           "Authority of Uganda and EACOP", layer="physical_economy",
        roots=("https://www.tanesco.co.tz", "https://www.eep.gov.et", "https://www.uetcl.go.ug",
               "https://www.petroleum.go.ug", "https://eacop.com"),
        queries=("mgao wa umeme", "bwawa la Julius Nyerere uzalishaji", "gesi asilia Tanzania",
                 "የኃይል ማመንጫ", "ታላቁ የሕዳሴ ግድብ ተርባይን", "power export to Kenya Ethiopia",
                 "EACOP welding progress", "Tilenga central processing facility"),
        languages=("sw", "am", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the GERD's turbine commissionings and the Julius Nyerere units are DATED physical "
              "capacity additions that displace diesel and gas generation across the region; "
              "EACOP's welding and station milestones are the schedule EA-K's ramp is measured "
              "against"),
    source_class(
        "ea_agri_remote", "The crop and climate plane: USDA FAS GAIN reports for all three, FAO "
                          "GIEWS country briefs, FEWS NET East Africa, IGAD ICPAC seasonal "
                          "forecasts, the International Coffee Organization and UN Comtrade",
        layer="physical_economy",
        roots=("https://fas.usda.gov/data", "https://www.fao.org/giews/countrybrief/",
               "https://fews.net/east-africa", "https://www.icocoffee.org",
               "https://comtradeplus.un.org"),
        queries=("Ethiopia coffee annual GAIN", "Uganda coffee annual", "Tanzania grain and feed",
                 "GIEWS Ethiopia brief", "FEWS NET belg kiremt outlook",
                 "ICO composite indicator", "comtrade HS0901 Uganda", "comtrade HS7108 gap"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work) / UN terms",
        notes="FEWS NET is the only source that forecasts BELG and KIREMT rather than the Kenyan "
              "long and short rains, which is the distinction EA-B and EA-H depend on; the "
              "Comtrade mirror gap is the second half of EA-M's gold measurement"),
    source_class(
        "ea_mining_physical", "The mining plane: the Mining Commission's production and royalty "
                              "statistics and its regional mineral market centres, the licensed "
                              "refineries in Tanzania and Uganda, the TEITI and UEITI "
                              "reconciliations, and the operators' public quarterly reports",
        layer="physical_economy",
        roots=("https://www.madini.go.tz", "https://www.teiti.go.tz",
               "https://www.ueiti.go.ug"),
        queries=("uzalishaji wa dhahabu kwa mwezi", "masoko ya madini mikoa",
                 "leseni ya kiwanda cha kusafisha dhahabu", "mrabaha uliolipwa",
                 "gold doré export", "refinery throughput Uganda", "smelter licence Tanzania"),
        languages=("sw", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE OPERATORS ARE ACTORS AND NEVER INSTRUMENTS (two-lane order, 2026-09-06): "
              "their quarterly reports are read for TONNES AND GRADES and their shares are never "
              "hunted. The artisanal half of the 50-tonne number exists only in the Mining "
              "Commission's market-centre statistics and the EITI reconciliations"),
    # ---- source graph
    source_class(
        "ea_source_graph", "Who cites whom: NBE directive -> Addis Fortune -> the diaspora "
                           "groups; the Finance Act -> the Mining Commission circular -> "
                           "Mwananchi; UCDA -> the ICO monthly -> the coffee trade letters; "
                           "PAU -> African Energy -> the wires", layer="source_graph",
        roots=("https://nbe.gov.et/directives/", "https://www.mwananchi.co.tz",
               "https://addisfortune.news", "https://www.monitor.co.ug"),
        queries=("kwa mujibu wa vyanzo", "taarifa ya benki kuu inasema", "ምንጮች እንደገለጹት",
                 "according to the gazette notice", "citing the Finance Act",
                 "wachambuzi wa uchumi wanasema"),
        languages=("sw", "am", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'kwa mujibu wa vyanzo' and 'ምንጮች እንደገለጹት' mark the unattributed leak that "
              "precedes a directive or a Finance Act clause by a day or two in all three "
              "countries; the graph is how a leak is told from a repost, and it is the only way "
              "to date an EA-F or EA-M measure before the gazette prints it"),
)

#: NO LAYER IS BLANK FOR THE REGION AS A WHOLE, and that is the measurement rather than a claim
#: of completeness. The refusals that ARE real here are per-jurisdiction and per-layer, and they
#: are declared by name below rather than hidden inside a layer that another country fills.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSALS (L1.28a). Each row names the jurisdiction, the layer, what does not
#: exist and why the pack will not manufacture it. A layer that one of the three fills and
#: another does not is a real asymmetry, and pooling the three without it is how a pack claims
#: coverage of a ground it has never read.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "et", "layer": "retail_ecology",
     "reason": "NO LAWFUL RETAIL MARGIN MARKET EXISTS. Ethiopian residents may not fund an "
               "offshore margin account under the NBE's exchange-control directives, no "
               "domestic broker is licensed to offer leverage, and no regulator publishes a "
               "retail flow, exposure or margin statistic. The unlicensed Telegram and YouTube "
               "ground IS sourced above at FRINGE credibility, and it is all there is."},
    {"jurisdiction": "tz", "layer": "retail_ecology",
     "reason": "CMSA licenses a handful of dealing members and publishes NO aggregate retail "
               "positioning, client exposure or margin statistic. The DSE reports turnover by "
               "investor category only in its annual report, which cannot condition a week."},
    {"jurisdiction": "ug", "layer": "retail_ecology",
     "reason": "the CMA publishes no aggregate retail positioning; the USE's investor split is "
               "annual. No microstructure claim in this pack may rest on a retail flow number."},
    {"jurisdiction": "et", "layer": "institutional",
     "reason": "NO SECURITIES TAPE EXISTS TO READ. The Ethiopian Securities Exchange opened on "
               "2025-01-10 with a handful of listings and publishes no machine-readable history; "
               "there is no public bond curve and no interbank yield series. The ECX fills this "
               "layer for commodities and nothing fills it for securities."},
    {"jurisdiction": "tz", "layer": "app_ecosystem",
     "reason": "THERE IS NO DOMESTIC TRADING-APP ECOSYSTEM. No Tanzanian brokerage publishes an "
               "API, no retail platform reports flow, and the app layer here is the PAYMENT "
               "rail -- M-Pesa, Mixx and Airtel Money -- whose statistics the BoT and TCRA do "
               "publish and which are sourced above. Declaring the layer absent because there "
               "is no MetaTrader ecology would be reading the wrong country."},
    {"jurisdiction": "ug", "layer": "app_ecosystem",
     "reason": "the same: MTN MoMo and Airtel Money ARE the app layer and the Bank of Uganda "
               "publishes their transaction value monthly; there is no domestic trading-app "
               "ecosystem and no brokerage API to read."},
)

#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer. At least
#: three per layer and every one in Amharic, Swahili, Luganda or Oromo unless the ground itself
#: is anglophone (the IMF, USDA and Comtrade layers genuinely are).
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("የኢትዮጵያ ብሔራዊ ባንክ መመሪያ", "የውጭ ምንዛሪ ተመን ማሻሻያ", "Benki Kuu ya Tanzania taarifa",
                 "ununuzi wa dhahabu na benki kuu", "Tume ya Madini takwimu za uzalishaji",
                 "mauzo ya dhahabu nje Uganda", "riba ya benki kuu imepanda",
                 "የዋጋ ንረት መረጃ"),
    "institutional": ("soko la hisa la Dar es Salaam taarifa ya siku", "የኢትዮጵያ ምርት ገበያ ዕለታዊ ግብይት",
                      "bodi ya korosho bei elekezi", "ripoti ya uwazi wa rasilimali madini",
                      "የአክሲዮን ገበያ ኢትዮጵያ", "hisa za kampuni zilizoorodheshwa"),
    "academic": ("የምንዛሪ ተመን ማሻሻያ ጥናት", "buna qorannoo Oromiyaa", "utafiti wa uchumi wa madini",
                 "tathmini ya sera ya fedha", "የቡና ምርታማነት ጥናት"),
    "practitioner": ("taarifa ya kila wiki ya soko la fedha", "utabiri wa shilingi",
                     "የብር ምንዛሪ ትንበያ", "mwenendo wa bei ya kahawa dunia",
                     "uchambuzi wa bajeti ya madini"),
    "retail_ecology": ("ጥቁር ገበያ ዶላር ዋጋ ዛሬ", "ወርቅ ዋጋ ዛሬ አዲስ አበባ", "bei ya dhahabu leo Tanzania",
                       "jinsi ya kuwekeza kwenye hisa", "dola sokoni leo Kampala",
                       "ፎሬክስ ትሬዲንግ ኢትዮጵያ"),
    "app_ecosystem": ("thamani ya miamala ya pesa za simu", "wakala wa M-Pesa takwimu",
                      "ቴሌብር ተጠቃሚዎች ቁጥር", "MTN MoMo miamala kwa mwezi",
                      "programu ya benki ya CRDB"),
    "media": ("ብሔራዊ ባንክ አስታወቀ", "የቡና ወጪ ንግድ ገቢ", "benki kuu yatangaza riba",
              "mnada wa korosho umeanza", "emmwanyi bbeeyi enkyukakyuka",
              "ታላቁ የሕዳሴ ግድብ ዜና"),
    "archive": ("ነጋሪት ጋዜጣ አዋጅ ቁጥር", "sheria ya fedha ya mwaka", "gazeti la serikali tangazo",
                "የማዕድን አዋጅ", "sheria ya madini marekebisho"),
    "physical_economy": ("mizigo ya bandari ya Dar es Salaam", "mizigo ya nchi jirani takwimu",
                         "mgao wa umeme Tanzania", "bwawa la Julius Nyerere uzalishaji",
                         "ታላቁ የሕዳሴ ግድብ ተርባይን", "bomba la mafuta EACOP maendeleo",
                         "uzalishaji wa dhahabu kwa mwezi"),
    "source_graph": ("kwa mujibu wa vyanzo vya serikali", "ምንጮች እንደገለጹት",
                     "wachambuzi wa uchumi wanasema", "taarifa ya benki kuu inasema",
                     "nkola ya gavumenti ng'eragirwa"),
}


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def layer_terms() -> dict[str, tuple[str, ...]]:
    """Every query this pack declares, by layer: the source classes' own queries plus the
    deep-forest territories, deduplicated and order-preserving."""
    out: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    for sc in SOURCE_CLASSES:
        layer = str(sc.get("layer") or "")
        if layer not in out:
            continue
        for q in sc.get("queries", ()):
            if q not in out[layer]:
                out[layer].append(q)
    for layer, terms in QUERY_TERRITORIES.items():
        if layer not in out:
            continue
        for q in terms:
            if q not in out[layer]:
                out[layer].append(q)
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    return {"code": CODE, "jurisdictions": JURISDICTIONS, "layer_counts": counts,
            "n_layers_covered": sum(1 for n in counts.values() if n),
            "n_sources": len([s for s in SOURCE_CLASSES
                              if not str(s["id"]).startswith("absent_")]),
            "missing": missing,
            "unexplained_missing": sorted(k for k, why in missing.items() if not why.strip()),
            "machine_use_forbidden": [str(s["id"]) for s in SOURCE_CLASSES
                                      if not s.get("machine_use_allowed", True)],
            "low_weight_kept": [str(s["id"]) for s in SOURCE_CLASSES
                                if s.get("credibility") in ("FRINGE", "UNRELIABLE",
                                                            "CONTRADICTED")],
            "no_lawful_ground": tuple(dict(r) for r in NO_LAWFUL_GROUND),
            "query_territory_counts": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; a layer "
                    "one jurisdiction fills and another does not is declared per jurisdiction in "
                    "NO_LAWFUL_GROUND rather than hidden behind the one that fills it; fringe "
                    "and unreliable PUBLIC material is kept at low weight and never dropped; a "
                    "page whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted"}


# --------------------------------------------------------------------------- datasets
#: TWENTY ROWS, SPREAD ACROSS THE TEN LAYERS, each with a `how_to_fetch` a collector can act on.
#: Only the twelve DATASET_FIELDS appear here: the framework's `DatasetRow` has no notes slot, so
#: a thirteenth key would arrive as a coercion note rather than as information.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "NBE daily indicative exchange rates and the FX directive series", "source": "NBE",
     "coverage": "daily rates from the 1990s; the directive series from 2008 onward",
     "frequency": "daily (business days), directives irregular", "publication_lag_days": 0.0,
     "revisions": "never revised; the pre-2024 rate was ADMINISTERED and is not a market price",
     "licence": "free, public", "history_from": "2008-01", "pit_feasible": False,
     "assets": ("COFARA", "XAUUSD", "USDZAR"),
     "mechanism_families": ("regime_break", "administered_price", "fixing"),
     "how_to_fetch": "nbe.gov.et exchange-rate table and nbe.gov.et/directives/; the rate page "
                     "OVERWRITES IN PLACE, so the only point-in-time vintage is a daily crawl or "
                     "the Wayback snapshot -- pit_feasible is False for exactly that reason"},
    {"name": "Ethiopia's parallel-market premium as reconstructed in the IMF programme documents",
     "source": "IMF ECF staff reports and Article IV annexes",
     "coverage": "2019 onward in the programme documents; press quotes before that",
     "frequency": "per review (roughly semi-annual)", "publication_lag_days": 45.0,
     "revisions": "restated between reviews", "licence": "free, public",
     "history_from": "2019-06", "pit_feasible": True, "assets": ("COFARA", "XAUUSD"),
     "mechanism_families": ("regime_break", "capital_control_stress"),
     "how_to_fetch": "imf.org/en/Countries/ETH: each ECF review PDF carries the staff's own "
                     "parallel-premium and FX-backlog estimates, which the NBE does not publish"},
    {"name": "ECX daily trade data: coffee and sesame by grade, volume, price and origin",
     "source": "Ethiopian Commodity Exchange",
     "coverage": "2008 onward on the exchange; the public daily table is a rolling window",
     "frequency": "daily (trading sessions)", "publication_lag_days": 0.0,
     "revisions": "none", "licence": "free, public", "history_from": "2008-04",
     "pit_feasible": False, "assets": ("COFARA", "SOYBEAN"),
     "mechanism_families": ("physical_flow", "auction", "seasonal_flow"),
     "how_to_fetch": "ecx.com.et/market-data/ daily table; it shows the session and keeps no "
                     "archive, so a daily crawl is the only vintage and the Wayback snapshots "
                     "are the fallback"},
    {"name": "Ethiopian Statistical Service consumer price index", "source": "ESS",
     "coverage": "2011 base onward", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "rebasing only", "licence": "free, public", "history_from": "2011-01",
     "pit_feasible": True, "assets": ("COFARA", "WHEAT"),
     "mechanism_families": ("release_surprise", "pass_through"),
     "how_to_fetch": "statsethiopia.gov.et CPI bulletin; the post-float vintages carry the "
                     "pass-through of a 50%+ depreciation and are not comparable to the "
                     "administered-rate era"},
    {"name": "Ethiopian coffee and sesame export volumes and values by destination",
     "source": "Ethiopian Customs Commission and the Coffee and Tea Authority",
     "coverage": "2010 onward", "frequency": "monthly and per crop year",
     "publication_lag_days": 45.0, "revisions": "restated at the crop-year close",
     "licence": "free, public", "history_from": "2010-07", "pit_feasible": True,
     "assets": ("COFARA", "SOYBEAN"),
     "mechanism_families": ("physical_flow", "external_balance"),
     "how_to_fetch": "customs.gov.et trade statistics plus the Coffee and Tea Authority's "
                     "crop-year report; cross-check against ICO country exports and Comtrade"},
    {"name": "GERD filling and turbine commissioning milestones with Ethiopian power exports",
     "source": "Ethiopian Electric Power, the Ministry of Water, and the Nile basin reporting",
     "coverage": "2020 onward (first filling July 2020)", "frequency": "irregular, dated events",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2020-07", "pit_feasible": True, "assets": ("XBRUSD", "WHEAT", "CORN"),
     "mechanism_families": ("capacity_ramp", "regime_break", "transfer"),
     "how_to_fetch": "eep.gov.et announcements and the Ministry of Water statements, stamped "
                     "against ENA and Fana; the filling SEASONS are July-September in each year "
                     "and the turbine commissionings are single dated events"},
    {"name": "Bank of Tanzania Monthly Economic Review: reserves, IFEM, gold and trade",
     "source": "Bank of Tanzania", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 35.0, "revisions": "reserves and trade restated",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XAUUSD", "XBRUSD", "USDZAR"),
     "mechanism_families": ("official_demand", "external_balance", "liquidity"),
     "how_to_fetch": "bot.go.tz/Publications/Filter/9 monthly PDFs; the gold and reserve lines "
                     "are the number the domestic purchase programme shows up in"},
    {"name": "Bank of Tanzania domestic gold purchase programme announcements and allocations",
     "source": "Bank of Tanzania, the Ministry of Finance budget speeches and the Finance Acts",
     "coverage": "FY2023/24 onward", "frequency": "per budget round, with monthly reserve prints",
     "publication_lag_days": 30.0, "revisions": "the reserve split is not always broken out",
     "licence": "free, public", "history_from": "2023-07", "pit_feasible": True,
     "assets": ("XAUUSD", "XAGUSD"),
     "mechanism_families": ("official_demand", "administered_price", "physical_flow"),
     "how_to_fetch": "the June budget speech and the Finance Act of each year on mof.go.tz, "
                     "plus bot.go.tz monthly reviews for the realised purchases; the MANDATED "
                     "DOMESTIC OFFER share is a statutory number and belongs to the Finance Act"},
    {"name": "Tanzania Mining Commission production, royalty and mineral-market-centre statistics",
     "source": "Mining Commission (madini.go.tz) and TEITI",
     "coverage": "2018 onward for the market centres; longer for royalties",
     "frequency": "monthly and annual", "publication_lag_days": 60.0,
     "revisions": "annual reconciliation in the EITI report", "licence": "free, public",
     "history_from": "2018-01", "pit_feasible": True, "assets": ("XAUUSD", "XAGUSD", "XCUUSD"),
     "mechanism_families": ("physical_flow", "administered_price"),
     "how_to_fetch": "madini.go.tz statistics pages and the annual TEITI reconciliation; the "
                     "market-centre series is the ARTISANAL half of national production and the "
                     "operators' quarterly reports are the industrial half"},
    {"name": "Tanzania Ports Authority throughput and Central Corridor transit by country",
     "source": "Tanzania Ports Authority and the Central Corridor TTFA",
     "coverage": "2010 onward, irregularly published", "frequency": "monthly to annual",
     "publication_lag_days": 60.0, "revisions": "restated in the annual report",
     "licence": "free, public", "history_from": "2010-07", "pit_feasible": False,
     "assets": ("XCUUSD", "XNIUSD", "XBRUSD"),
     "mechanism_families": ("chokepoint", "physical_flow"),
     "how_to_fetch": "tanzaniaports.go.tz statistics and the Central Corridor TTFA's transit "
                     "time observatory; the TRANSIT-BY-DESTINATION split is the copper and "
                     "cobalt leaving Zambia and the DRC and is the only part that matters here"},
    {"name": "NBS Tanzania consumer price index and foreign trade statistics", "source": "NBS",
     "coverage": "2010 base onward", "frequency": "monthly", "publication_lag_days": 12.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("SUGAR", "CORN", "XBRUSD"),
     "mechanism_families": ("release_surprise", "external_balance"),
     "how_to_fetch": "nbs.go.tz monthly CPI and the quarterly foreign-trade bulletin"},
    {"name": "Tanzanian cashew auction results and the indicative price",
     "source": "Cashewnut Board of Tanzania and the co-operative unions",
     "coverage": "2015 onward", "frequency": "weekly through the October-January season",
     "publication_lag_days": 3.0, "revisions": "none", "licence": "free, public",
     "history_from": "2015-10", "pit_feasible": False, "assets": ("COTTON", "SUGAR"),
     "mechanism_families": ("auction", "administered_price", "seasonal_flow"),
     "how_to_fetch": "cashew.go.tz auction notices and the Mwananchi reporting of each week's "
                     "indicative price; there is NO cashew contract, so this series conditions "
                     "the Tanzanian export-earnings state and is never a price the desk trades"},
    {"name": "Bank of Uganda Central Bank Rate decisions and MPC statements", "source": "BoU",
     "coverage": "July 2011 onward (the start of inflation targeting lite)",
     "frequency": "roughly bi-monthly", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2011-07", "pit_feasible": True,
     "assets": ("COFROB", "USDZAR", "XAUUSD"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "bou.or.ug monetary policy statements; the announcement time is stamped in "
                     "the release and the statement carries the inflation forecast revision"},
    {"name": "Bank of Uganda monthly balance of payments with the GOLD EXPORT line",
     "source": "Bank of Uganda", "coverage": "2005 onward", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "heavily revised for several months",
     "licence": "free, public", "history_from": "2005-01", "pit_feasible": True,
     "assets": ("XAUUSD",),
     "mechanism_families": ("physical_flow", "administered_price", "regime_break"),
     "how_to_fetch": "bou.or.ug Statistics -> External Sector; the gold line against Uganda's "
                     "own mine production is the measurement, and the 2021 levy is the "
                     "switch that turned it off and on again"},
    {"name": "UCDA monthly coffee export report: bags, value, type and destination",
     "source": "Uganda Coffee Development Authority", "coverage": "1990s onward",
     "frequency": "monthly", "publication_lag_days": 14.0,
     "revisions": "restated when late shipments register", "licence": "free, public",
     "history_from": "2000-10", "pit_feasible": True, "assets": ("COFROB", "COFARA"),
     "mechanism_families": ("physical_flow", "seasonal_flow", "release_surprise"),
     "how_to_fetch": "ugandacoffee.go.ug/resource-centre/reports monthly PDF; the FIRST print is "
                     "what a point-in-time cell must use, because the restatements are material"},
    {"name": "Uganda gold export levy: the Finance Act clauses and the URA collections",
     "source": "Uganda Gazette, the Finance Acts and the Uganda Revenue Authority",
     "coverage": "2021 onward", "frequency": "per Act, with monthly collections",
     "publication_lag_days": 30.0, "revisions": "none for the statute",
     "licence": "free, public", "history_from": "2021-07", "pit_feasible": True,
     "assets": ("XAUUSD",),
     "mechanism_families": ("administered_price", "regime_break", "event_reaction"),
     "how_to_fetch": "ulii.org and the Uganda Gazette for the Finance Act text with its "
                     "commencement date; ura.go.ug for the collections; the Daily Monitor and "
                     "New Vision for the refineries' dated response"},
    {"name": "Petroleum Authority of Uganda project milestones and the EACOP schedule",
     "source": "PAU, the Ministry of Energy and EACOP Ltd", "coverage": "2017 onward",
     "frequency": "irregular, dated milestones", "publication_lag_days": 7.0,
     "revisions": "schedules slip and the slips are themselves the events",
     "licence": "free, public", "history_from": "2017-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XNGUSD"),
     "mechanism_families": ("capacity_ramp", "event_reaction"),
     "how_to_fetch": "petroleum.go.ug project updates and eacop.com progress releases, stamped "
                     "against African Energy and the Ugandan press; FID was 2022-02-01 and the "
                     "plateau target is about 230,000 b/d"},
    {"name": "UBOS Uganda consumer price index and external trade statistics", "source": "UBOS",
     "coverage": "2009 base onward", "frequency": "monthly", "publication_lag_days": 1.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2009-10",
     "pit_feasible": True, "assets": ("COFROB", "CORN", "USDZAR"),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "ubos.org publishes the CPI on the last working day of the reference month "
                     "itself, which is one of the fastest CPI prints on the continent"},
    {"name": "Mobile-money transaction value, agents and float for all three",
     "source": "Bank of Uganda, Bank of Tanzania National Payment Systems reports, TCRA and "
               "Ethio Telecom's telebirr disclosures",
     "coverage": "2012 onward for UG and TZ; 2021 onward for telebirr",
     "frequency": "monthly (UG, TZ) and quarterly (ET)", "publication_lag_days": 45.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2012-01",
     "pit_feasible": True, "assets": ("SUGAR", "CORN", "USDZAR"),
     "mechanism_families": ("nominal_demand", "liquidity", "seasonal_flow"),
     "how_to_fetch": "bou.or.ug Statistics -> Payment Systems; bot.go.tz National Payment "
                     "Systems reports; TCRA quarterly communications statistics; the telebirr "
                     "user and value numbers come from Ethio Telecom's own releases"},
    {"name": "ICO composite indicator prices and country export statistics",
     "source": "International Coffee Organization", "coverage": "1990 onward",
     "frequency": "daily indicator, monthly country exports", "publication_lag_days": 30.0,
     "revisions": "country exports restated", "licence": "free, public (ICO terms)",
     "history_from": "1990-01", "pit_feasible": True, "assets": ("COFARA", "COFROB"),
     "mechanism_families": ("benchmark_price", "physical_flow"),
     "how_to_fetch": "icocoffee.org statistics: the group indicators separate a CROP story from "
                     "an exchange story, and the country export table is the independent check "
                     "on UCDA and the Ethiopian customs print"},
    {"name": "FEWS NET and IGAD ICPAC seasonal outlooks for BELG, KIREMT and the Tanzanian "
             "unimodal season",
     "source": "FEWS NET, IGAD ICPAC and FAO GIEWS", "coverage": "2010 onward",
     "frequency": "monthly outlooks and per-season forecasts", "publication_lag_days": 5.0,
     "revisions": "each outlook supersedes the last and the revision is the signal",
     "licence": "free, public (US government work / IGAD terms)", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("CORN", "WHEAT", "COFARA", "COFROB"),
     "mechanism_families": ("weather", "supply_shock"),
     "how_to_fetch": "fews.net/east-africa monthly outlooks and the ICPAC GHACOF statements; "
                     "these forecast BELG and KIREMT rather than the Kenyan long and short "
                     "rains, which is the distinction every regional crop study gets wrong"},
    {"name": "UN Comtrade mirror statistics for gold, coffee and sesame",
     "source": "UN Comtrade", "coverage": "2000 onward", "frequency": "annual, some monthly",
     "publication_lag_days": 365.0, "revisions": "heavily revised", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False, "assets": ("XAUUSD", "COFARA", "COFROB"),
     "mechanism_families": ("physical_flow", "transfer"),
     "how_to_fetch": "comtradeplus.un.org: HS7108 exports reported BY Uganda against HS7108 "
                     "imports reported FROM Uganda by the UAE and Switzerland; the gap is the "
                     "re-export measurement and it can date an era, never condition a week"},
)


# --------------------------------------------------------------------------- actors
#: TWENTY ACTORS, AT LEAST SIX PER JURISDICTION. The floor is twelve for a single country and a
#: three-country pack that stops at twelve has read one country and guessed twice. Every row
#: carries all eleven fields, and the FALSIFIER is the one that decides whether the row is a
#: research object or a story.
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- Ethiopia
    {"name": "The National Bank of Ethiopia FX desk and the allocation queue it used to run",
     "holds": "the exchange regime itself, the banks' FX surrender requirement, and reserves "
              "that fell to roughly two weeks of imports before the 2024 programme",
     "forced_to": ("allocate scarce dollars by priority list until 2024-07-28, and stop doing so "
                   "on 2024-07-29 when the float directive took effect",
                   "publish a daily indicative rate that was administered before the float and "
                   "market-determined after it",
                   "meet the IMF programme's reserve and arrears targets at each review"),
     "when": "daily for the rate; the regime change itself is a single dated directive package "
             "issued in the last week of July 2024",
     "information": ("the true size of the letter-of-credit backlog, which the market could only "
                     "infer from the parallel premium",
                     "the surrender proceeds arriving from coffee and gold exporters",
                     "the programme's disbursement calendar before it is public"),
     "constraints": ("a reserve position too thin to defend any rate at all by mid-2024",
                     "an IMF prior action that made the float a condition of disbursement",
                     "a pass-through into a CPI already running above 20%",
                     "state-owned enterprise debt that the same reform had to restructure"),
     "instruments": ("COFARA", "XAUUSD", "USDZAR"),
     "counterparties": ("the commercial banks and their importer clients",
                        "the coffee and sesame exporters who surrender proceeds",
                        "the diaspora remitters who chose between the official and street rates",
                        "the IMF and the Official Creditor Committee"),
     "observables": ("the daily indicative rate and its gap to the street rate",
                     "the directive series and its commencement dates",
                     "the IMF review documents' own backlog and premium estimates",
                     "the remittance line in the balance of payments"),
     "impact": "the float halved the dollar value of a birr and therefore DOUBLED the local "
               "receipt on a dollar coffee sale; the executable consequence is on the supply "
               "side of COFARA over quarters, and on the frontier risk carriers on the day",
     "persistence": "a regime, not an event: the boundary of 2024-07-29 partitions every "
                    "Ethiopian series in this pack and does not decay",
     "falsifier": "Ethiopian arabica export volumes and the ECX's own delivered tonnage show no "
                  "change in level or seasonality across the 2024-07-29 boundary once the crop "
                  "year and the global arabica price are controlled for -- in which case the "
                  "float was a monetary event with no physical consequence and EA-B's edge dies",
     "notes": "THE CLEANEST EM REGIME BOUNDARY IN THE PACK, and the reason the pre-float CPI, "
              "exchange-rate and trade vintages are a different measurement from the post-float "
              "ones rather than a longer sample of the same one"},
    {"name": "The Ethiopian Commodity Exchange and its mandatory coffee and sesame floor",
     "holds": "a legal monopoly on the first sale of export coffee and sesame, the warehouses "
              "that grade and store it, and the only daily price and volume print in the country",
     "forced_to": ("publish the session's lots, grades, prices and washing-station origins the "
                   "same day",
                   "grade and warehouse every lot before it can be sold for export",
                   "clear and settle in birr, which makes the exchange the first place a "
                   "currency move reaches the farmgate"),
     "when": "each trading session, roughly 08:30-13:00 Africa/Addis_Ababa, closing BEFORE the "
             "New York coffee session opens",
     "information": ("the day's delivered tonnage by origin before any exporter or importer sees "
                     "the aggregate",
                     "the grade mix, which says how much of the crop can reach a specialty buyer",
                     "the side-selling pressure the enforcement reports describe"),
     "constraints": ("a mandatory regime that has been relaxed for vertically integrated "
                     "specialty exporters, so the census is not quite complete",
                     "warehouse and transport capacity at the crop-year opening",
                     "a price in birr against an export price in dollars"),
     "instruments": ("COFARA", "SOYBEAN"),
     "counterparties": ("the cooperatives and the private washing stations",
                        "the licensed exporters", "the importers and roasters abroad",
                        "the banks financing the export contracts"),
     "observables": ("the daily lot volume, price and grade table",
                     "the crop-year opening's first-delivery week",
                     "the sesame floor's Chinese-demand season"),
     "impact": "a census-like daily supply print from the world's fifth-largest arabica producer, "
               "arriving hours before the New York session -- a candidate lead on COFARA that "
               "almost no desk reads",
     "persistence": "daily and seasonal; the crop-year opening in October is the structural "
                    "break inside each year",
     "falsifier": "ECX daily delivered tonnage carries no information about the following "
                  "session's COFARA return beyond what the previous New York session and the ICO "
                  "indicator already carry, measured against a matched-weekday control",
     "notes": "THE MOST USEFUL EXCHANGE IN THIS PACK AND IT HAS NO TRADABLE INSTRUMENT. It is an "
              "observable, it is declared in TRANSMISSION_TARGETS, and the page that publishes "
              "it overwrites in place"},
    {"name": "The Ethiopian coffee exporters, the cooperatives and the washing stations",
     "holds": "the physical crop between the farmgate and the port, and the export contracts "
              "registered against it",
     "forced_to": ("surrender export proceeds to the banking system at the prevailing rate",
                   "deliver against registered contracts within the crop year or default",
                   "buy cherry in birr and sell green in dollars, which is the whole of their "
                   "exposure to the float"),
     "when": "the crop year opens in October; the export peak runs December to April",
     "information": ("the cherry price being paid in Sidama, Guji, Yirgacheffe and Harar before "
                     "any aggregate exists",
                     "the washing-station throughput, which caps the washed-grade share",
                     "their own contract book against the delivered tonnage"),
     "constraints": ("working capital in a banking system that was rationing dollars",
                     "a minimum-price and contract-registration regime",
                     "the EU Deforestation Regulation's traceability requirement on smallholder "
                     "plots, which is a compliance cost per kilogram and not per farm"),
     "instruments": ("COFARA", "UKCOCOA"),
     "counterparties": ("the smallholders and cooperative unions", "the ECX floor",
                        "the European and Japanese specialty importers",
                        "the banks financing pre-shipment"),
     "observables": ("the ECX daily print", "the customs export volumes by destination",
                     "the ICO country export table as the independent check",
                     "the farmgate cherry price reported in the Amharic press"),
     "impact": "the supply side of the specialty arabica market; a delivery failure or a hoarding "
               "episode shows up first as a WIDENING of the specialty differential rather than as "
               "a move in the flat price",
     "persistence": "one crop year; the EUDR compliance state is multi-year",
     "falsifier": "crop years in which Ethiopian export registrations ran well below the delivered "
                  "ECX tonnage show no abnormal COFARA behaviour against matched crop years "
                  "elsewhere, which would put the mechanism entirely in the differential and "
                  "outside anything this broker quotes",
     "notes": "the differentials themselves are LICENSED ground; the pack measures the flat price "
              "and says what it cannot see"},
    {"name": "Ethiopian Airlines Cargo and the Bole perishables hub",
     "holds": "the largest air-freight operation in Africa, with dedicated freighters and a "
              "cold chain built for flowers, vegetables and specialty coffee",
     "forced_to": ("fly perishables to a European auction clock that does not move",
                   "buy jet fuel in dollars while selling a service partly in birr",
                   "fill belly-hold capacity that its own passenger network creates"),
     "when": "daily, with a Valentine's and Mother's Day flower peak and a Northern-Hemisphere "
             "winter vegetable season",
     "information": ("the tonnage booked out of Bole before any statistic is published",
                     "the cold-chain and capacity constraints at the airport",
                     "the horticulture exporters' own volumes"),
     "constraints": ("jet fuel cost and the dollar price of it",
                     "European phytosanitary and freight-rate conditions",
                     "conflict-era airspace and route restrictions"),
     "instruments": ("XBRUSD", "UK100"),
     "counterparties": ("the horticulture and coffee exporters", "the European auctions and "
                        "supermarkets", "the fuel suppliers at Bole"),
     "observables": ("Ethiopian Civil Aviation and airline cargo tonnage statistics",
                     "the horticulture export line in the customs data",
                     "European fresh-produce auction volumes"),
     "impact": "a PHYSICAL-ECONOMY observable for the continent's perishables trade and a "
               "jet-fuel demand line; the claim here is about DIRECTION and is small, and the "
               "pack says so rather than pretending an airline moves Brent",
     "persistence": "seasonal, with a multi-year capacity trend",
     "falsifier": "Bole cargo tonnage carries no information about European fresh-produce supply "
                  "or about jet-fuel cracks beyond what global air-freight rates already carry",
     "notes": "the airline is a SINGLE NAME and appears here as an actor only; the two-lane order "
              "forbids hunting it, and no instrument tuple in this file contains it"},
    {"name": "The Ethiopian Ministry of Finance debt office and the Official Creditor Committee",
     "holds": "the defaulted 2024 eurobond, the bilateral claims under the G20 Common Framework "
              "and the state-enterprise debt the reform had to restructure",
     "forced_to": ("miss the coupon due 2023-12-11 and let the grace period expire 2023-12-26",
                   "negotiate a treatment under the Common Framework with a Chinese and Western "
                   "creditor committee that must agree with each other",
                   "meet the ECF's arrears and financing-assurance milestones on a review clock"),
     "when": "the default dates are fixed; the reviews are quarter-end Board events",
     "information": ("the bilateral creditors' positions before the committee publishes",
                     "the financing gap the programme is built on"),
     "constraints": ("comparability of treatment between bondholders and bilaterals",
                     "an IMF programme that cannot disburse without financing assurances",
                     "a domestic banking system holding the state's own paper"),
     "instruments": ("USDZAR", "US500", "UK100"),
     "counterparties": ("the bondholder committee", "China Exim and the Paris Club members",
                        "the IMF and the World Bank"),
     "observables": ("the missed-coupon and grace-period dates",
                     "the ECF review Board dates and the disbursement amounts",
                     "the Common Framework communiques"),
     "impact": "a FRONTIER RISK-CHANNEL event: the third African default of the cycle after "
               "Zambia and Ghana, read by the same investors who hold the rand and the frontier "
               "credit complex",
     "persistence": "years; the restructuring clock is still open",
     "falsifier": "Ethiopian default and review dates show no abnormal behaviour in USDZAR or in "
                  "the frontier risk complex against matched non-event days, which would make "
                  "this a local credit event with no measurable spillover at all",
     "notes": "a genuine test of whether 'frontier risk' is one thing or a label; Ghana's and "
              "Zambia's dates are the natural placebo and both are on the desk's roster"},
    {"name": "Ethiopian Electric Power and the Grand Ethiopian Renaissance Dam",
     "holds": "the largest hydroelectric project in Africa, about 5 GW installed at full "
              "commissioning, and the export interconnectors to Sudan, Djibouti and Kenya",
     "forced_to": ("fill the reservoir during the KIREMT rains of July to September, which is "
                   "the only season with enough water to do it",
                   "commission turbines on a schedule that is announced as it happens",
                   "sell power across borders under contracts denominated in dollars"),
     "when": "the filling seasons are July-September in each year from 2020; the turbine "
             "commissionings are single dated events",
     "information": ("the reservoir level and the release schedule before Egypt or Sudan see it",
                     "the export contract pipeline with Kenya and Tanzania"),
     "constraints": ("an unresolved dispute with Egypt and Sudan over the filling rate",
                     "transmission capacity to the export markets",
                     "domestic demand that grows faster than the interconnectors"),
     "instruments": ("XBRUSD", "WHEAT", "CORN"),
     "counterparties": ("the Egyptian and Sudanese water ministries",
                        "Kenya Power and the Djiboutian utility",
                        "the domestic industrial users and the smelters"),
     "observables": ("the filling-season announcements and the turbine commissioning dates",
                     "Ethiopian power export volumes in the trade data",
                     "Egyptian water-stress and import-demand reporting"),
     "impact": "TWO CHANNELS, and they run in opposite directions. Cheap Ethiopian hydro "
               "DISPLACES diesel and heavy-fuel generation in the region, which is a small "
               "negative for distillate demand; a filling season that tightens Egyptian water "
               "raises Egyptian agricultural import demand, which is a small positive for WHEAT "
               "and CORN. Both are weak and both are declared weak",
     "persistence": "a filling season is months; a commissioned turbine is permanent",
     "falsifier": "GERD filling seasons and turbine commissioning dates show no abnormal "
                  "behaviour in Egyptian wheat tender volumes or in regional distillate demand "
                  "against matched seasons in the years before 2020",
     "notes": "THE DIRECT INTERACTION WITH THE `eg` PACK, and the one edge in this file where "
              "two country packs must be tested against each other or neither claim is testable"},
    # ---------------------------------------------------------------- Tanzania
    {"name": "The Bank of Tanzania's domestic gold purchase desk",
     "holds": "the national reserves and, since FY2023/24, a budget line for buying gold INSIDE "
              "Tanzania rather than on the international market",
     "forced_to": ("buy from licensed domestic refiners and dealers at a published reference to "
                   "the LBMA price, in shillings",
                   "hold the metal as reserve assets and report it in the monthly review",
                   "operate the programme within an annual budget allocation that the Finance "
                   "Act and the June budget speech set"),
     "when": "continuously within each fiscal year from July; the mandate and the allocation are "
             "set at the June budget and in each year's Finance Act",
     "information": ("the domestic refiners' throughput and the artisanal deliveries into the "
                     "mineral market centres",
                     "its own reserve adequacy against the import bill",
                     "the dollar shortage's severity before the trade data shows it"),
     "constraints": ("a shilling budget against a dollar-priced metal",
                     "domestic refining capacity, which is the binding physical limit",
                     "a statutory offer obligation on miners that has to be enforced, not just "
                     "legislated"),
     "instruments": ("XAUUSD", "XAGUSD"),
     "counterparties": ("the licensed domestic refineries", "the large mine operators subject to "
                        "the offer requirement", "the artisanal miners at the market centres",
                        "the Mining Commission as the licensing authority"),
     "observables": ("the reserve line and its gold component in the monthly economic review",
                     "the budget speech and Finance Act clauses that set the offer share",
                     "the Mining Commission's market-centre volumes",
                     "the refineries' licensed capacity"),
     "impact": "OFFICIAL-SECTOR DEMAND AND A SUPPLY DIVERSION AT ONCE: tonnes that would have "
               "been exported as dore are bought and held domestically instead. On a 50-tonne "
               "producer this is a real, dated, published change in physical routing -- the "
               "single most under-modelled XAUUSD observable in this pack",
     "persistence": "a standing programme renewed each fiscal year; the offer share is statutory",
     "falsifier": "budget rounds that raised the mandated domestic offer share show no change in "
                  "Tanzanian gold EXPORT tonnage in the customs data against matched years, and "
                  "no abnormal XAUUSD behaviour in the announcement window against a "
                  "matched-weekday control -- in which case the programme is an accounting "
                  "transfer and not a supply event",
     "notes": "THE HEADLINE MECHANISM OF THIS PACK. The two halves are separately falsifiable: "
              "the diversion is measurable in the customs data whether or not the price responds"},
    {"name": "The Tanzanian Mining Commission and its regional mineral market centres",
     "holds": "the licensing of miners, dealers, smelters and refineries, and the regional "
              "market centres where artisanal gold is legally bought, assayed and taxed",
     "forced_to": ("publish production and royalty statistics by mineral and region",
                   "collect the royalty and the inspection fee at the point of sale",
                   "license the refineries the central bank's programme depends on"),
     "when": "continuously; the royalty rates and the offer obligations change at the budget",
     "information": ("the artisanal deliveries that no company report contains",
                     "the licensed refinery throughput",
                     "the smuggling pressure the border seizures imply"),
     "constraints": ("an artisanal sector that can sell across a border instead",
                     "assay and refining capacity",
                     "a royalty rate that is itself a fiscal instrument and changes"),
     "instruments": ("XAUUSD", "XAGUSD", "XCUUSD"),
     "counterparties": ("the artisanal and small-scale miners",
                        "the licensed dealers and refiners", "the large mine operators",
                        "the Bank of Tanzania as the buyer of last resort"),
     "observables": ("monthly production and royalty statistics by region",
                     "market-centre turnover", "refinery and smelter licence grants",
                     "the TEITI reconciliation of payments against receipts"),
     "impact": "the market centres formalised a flow that used to leave the country informally, "
               "which is what made a central-bank purchase programme possible at all; the "
               "centre turnover is the earliest read on the artisanal half of supply",
     "persistence": "structural since the 2017-2019 reform package",
     "falsifier": "market-centre turnover carries no information about Tanzanian gold export "
                  "tonnage or about the BoT's realised purchases once the LBMA price and the "
                  "season are controlled for",
     "notes": "the ARTISANAL half of the 50-tonne number lives only here and in the EITI "
              "reconciliations; the industrial half is in the operators' quarterlies"},
    {"name": "The Tanzanian gold mine operating companies (Geita, North Mara, Bulyanhulu)",
     "holds": "the three large producing mines and the concentrate and dore they ship",
     "forced_to": ("report quarterly production, grade and cost per mine",
                   "pay royalty and clearing fees at a statutory rate, with a government free-"
                   "carried interest under the 2017 framework and the 2019-2020 settlement",
                   "offer a share of production to the domestic market under the current "
                   "Finance Act"),
     "when": "quarterly for the reports; continuously for the physical shipments",
     "information": ("grade and recovery before the quarterly print",
                     "the shipment schedule out of Dar es Salaam",
                     "the negotiation state with the Mining Commission"),
     "constraints": ("the 2017 concentrate export ban and its 2019-2020 resolution",
                     "a statutory domestic offer obligation",
                     "power supply from a grid with a load-shedding history"),
     "instruments": ("XAUUSD", "XAGUSD", "XCUUSD"),
     "counterparties": ("the Tanzanian state as a free-carried partner and royalty taker",
                        "the domestic refiners and the BoT",
                        "the international dore and concentrate buyers"),
     "observables": ("quarterly production and grade by mine",
                     "the customs export tonnage of dore and concentrate",
                     "the royalty receipts in the Mining Commission statistics"),
     "impact": "roughly two thirds of a 50-tonne national supply, published quarterly with "
               "grades -- a real, dated physical supply series for a top-fifteen producer",
     "persistence": "mine lives are decades; the policy regime changes at the budget",
     "falsifier": "Tanzanian quarterly mine production carries no information about XAUUSD "
                  "beyond what global mine supply already carries, which would make EA-F a "
                  "POLICY edge only and not a supply edge",
     "notes": "THE OPERATORS ARE LISTED SINGLE NAMES AND APPEAR HERE AS ACTORS ONLY. The "
              "two-lane order (2026-09-06) forbids hunting them statistically; their reports are "
              "read for TONNES AND GRADES and their shares never enter an instrument tuple"},
    {"name": "Tanzania Ports Authority and the Central Corridor transit operators",
     "holds": "Dar es Salaam, Tanga and Mtwara, the Central Corridor road and rail, TAZARA and "
              "the new standard-gauge railway",
     "forced_to": ("clear transit cargo for Zambia, the DRC, Burundi, Rwanda and Uganda through "
                   "a single port whose berths and dwell time are finite",
                   "publish throughput and transit statistics",
                   "compete with Mombasa, Beira, Walvis Bay and Lobito for the same metal"),
     "when": "continuously; the copper and cobalt season follows the Congolese and Zambian "
             "production and the southern African rainy season's road conditions",
     "information": ("the transit queue and the dwell time before any statistic publishes",
                     "the berth allocation between transit and domestic cargo",
                     "the corridor's own transit-time observatory"),
     "constraints": ("berth, crane and rail capacity", "road conditions in the rainy season",
                     "Zambian and Congolese border processing at Kasumbalesa and Tunduma",
                     "the Lobito corridor's re-opening as a competitor"),
     "instruments": ("XCUUSD", "XNIUSD", "XBRUSD"),
     "counterparties": ("the Zambian and Congolese miners and their traders",
                        "the Ugandan, Rwandan and Burundian importers",
                        "the shipping lines calling Dar es Salaam"),
     "observables": ("monthly and annual throughput with the TRANSIT-BY-COUNTRY split",
                     "the corridor observatory's transit times",
                     "port dwell time and container turnaround"),
     "impact": "A GENUINE CHOKEPOINT ON A METAL THIS BROKER QUOTES. A blockage at Dar es Salaam "
               "or on the corridor delays Congolese and Zambian copper and cobalt reaching the "
               "sea, which is a supply-timing effect on XCUUSD with a physical, published count "
               "behind it",
     "persistence": "an episode lasts weeks; the corridor's share is a multi-year trend",
     "falsifier": "months in which Central Corridor transit tonnage fell more than its own "
                  "interquartile range show no abnormal XCUUSD behaviour against matched months, "
                  "once Chinese demand and the LME stock cycle are controlled for -- which would "
                  "mean the metal simply left through Mombasa, Beira or Lobito instead",
     "notes": "THE CONTROL IS THE OTHER CORRIDOR, which is why the `ke` pack is named in "
              "INTERACTIONS: a Dar es Salaam blockage that diverts cargo to Mombasa is a "
              "ROUTING event and not a supply event, and only the two packs together can tell "
              "them apart"},
    {"name": "The Cashewnut Board of Tanzania and the warehouse-receipt auction",
     "holds": "the state-supervised auction through which the raw cashew crop is sold, the "
              "warehouse-receipt system behind it and the indicative price it announces",
     "forced_to": ("run weekly auctions through the October-to-January season",
                   "announce an indicative price that the cooperative unions will accept",
                   "clear the crop before it deteriorates in store"),
     "when": "weekly through the southern season; the collapse of the 2018 auction became a "
             "fiscal and political event when the state bought the crop itself",
     "information": ("the delivered tonnage at the warehouses before the auction",
                     "the Indian and Vietnamese buyers' bids",
                     "the co-operative unions' reserve prices"),
     "constraints": ("a buyer base concentrated in India and Vietnam",
                     "an indicative price that can be set above what buyers will pay, which is "
                     "exactly what broke the 2018 season",
                     "warehouse and shipping capacity at Mtwara"),
     "instruments": ("COTTON", "SUGAR"),
     "counterparties": ("the smallholder growers and the cooperative unions",
                        "the Indian and Vietnamese processors", "the Bank of Tanzania when the "
                        "state financed the crop directly"),
     "observables": ("weekly auction volumes and the indicative price",
                     "the Mwananchi reporting of each week's clearing",
                     "the export line in the NBS trade data"),
     "impact": "an ADMINISTERED-PRICE mechanism on a crop with no contract: the auction's success "
               "or failure moves Tanzanian export earnings and therefore the dollar supply that "
               "EA-I conditions on; it reaches a broker symbol only through COTTON as the "
               "sibling smallholder export crop and the pack labels that leg WEAK",
     "persistence": "one season; the institutional design persists between them",
     "falsifier": "seasons in which the cashew auction cleared badly show no abnormal Tanzanian "
                  "export-earnings shortfall relative to matched seasons once the world cashew "
                  "price is controlled for, which would make the auction a distributional "
                  "mechanism with no macro consequence",
     "notes": "the actual cashew price assessment is LICENSED and registered "
              "machine_use_allowed=false; what is public is the auction's own indicative price"},
    {"name": "TANESCO and the Julius Nyerere hydropower project",
     "holds": "the national grid, a load-shedding history and about 2.1 GW of new hydro capacity "
              "commissioning from 2024",
     "forced_to": ("balance a grid that has been short of firm capacity for years",
                   "burn gas from Songo Songo and Mnazi Bay when the hydrology is poor",
                   "commission the Julius Nyerere units as they come"),
     "when": "continuously; the hydrology follows the unimodal November-to-April season and the "
             "commissioning dates are announced events",
     "information": ("reservoir levels and the dispatch stack before any public statement",
                     "the industrial load, including the mines"),
     "constraints": ("hydrology", "gas supply and transmission",
                     "a tariff the regulator sets below the cost of the marginal unit"),
     "instruments": ("XNGUSD", "XAUUSD", "XCUUSD"),
     "counterparties": ("the mines and the industrial users", "the gas producers at Songo Songo "
                        "and Mnazi Bay", "the regional grid through the interconnectors"),
     "observables": ("load-shedding announcements", "the commissioning dates of each unit",
                     "gas offtake from the two fields", "the regulator's tariff decisions"),
     "impact": "load shedding raises mining costs and can cut milled tonnage, which is a supply "
               "effect on a gold and copper producer; new hydro DISPLACES gas-fired generation, "
               "which is a small negative for domestic gas demand",
     "persistence": "an episode is weeks; a commissioned unit is permanent",
     "falsifier": "Tanzanian load-shedding episodes show no measurable change in the mines' "
                  "reported quarterly tonnage against matched quarters, which would put the "
                  "whole mechanism inside the mines' own backup generation",
     "notes": "the honest version of an 'energy affects mining' claim: it is testable on "
              "PRODUCTION, which is published, before it is ever claimed on a price"},
    # ---------------------------------------------------------------- Uganda
    {"name": "The Bank of Uganda Monetary Policy Committee",
     "holds": "the Central Bank Rate, an open capital account since 1997 and the most credible "
              "inflation-targeting framework in the three",
     "forced_to": ("meet on a published schedule roughly every two months and announce the CBR "
                   "with a statement the same day",
                   "publish an inflation forecast it can be held to",
                   "let the shilling float, having no exchange-rate target to defend"),
     "when": "the scheduled MPC days, announced in advance, with the statement in the late "
             "morning UTC",
     "information": ("the private-credit and mobile-money aggregates before publication",
                     "the coffee and gold export receipts arriving in the banking system",
                     "the oil-sector import surge ahead of first oil"),
     "constraints": ("an open capital account, which means the rate is the only instrument",
                     "an oil-driven import boom that widens the current account before the "
                     "exports start",
                     "a food-heavy CPI basket that a drought dominates"),
     "instruments": ("COFROB", "USDZAR", "XAUUSD"),
     "counterparties": ("the commercial banks", "the offshore holders of Ugandan local paper",
                        "the Treasury at the weekly bill auction"),
     "observables": ("the CBR decision and the statement's forecast revision",
                     "the interbank rate and the bill auction cut-off",
                     "the monthly CPI, published on the last working day of the month itself"),
     "impact": "the one scheduled, credible policy clock in the three; it is the CONTROL "
               "jurisdiction that makes Ethiopia's rationing and Tanzania's shortage measurable "
               "as deviations rather than as stories",
     "persistence": "a decision holds for about two months by construction",
     "falsifier": "CBR decision windows show no abnormal behaviour in COFROB or in the frontier "
                  "risk carriers against matched non-meeting days, which would make Uganda a "
                  "clean control and nothing more -- a USEFUL result, not a failure",
     "notes": "UBOS publishes the CPI on the last working day of the reference month, which is "
              "one of the fastest prints on the continent and a real scheduling advantage"},
    {"name": "The Uganda Coffee Development Authority and the robusta exporters",
     "holds": "the registration of exporters, the quality regime and the monthly export census",
     "forced_to": ("publish bags, value, type and destination within a fortnight of each "
                   "month's end",
                   "certify quality before shipment",
                   "administer the sector through a statutory framework that was being merged "
                   "into the agriculture ministry"),
     "when": "monthly, in the first fortnight; the crop peaks twice a year across the two "
             "growing belts",
     "information": ("the month's registered shipments before the ICO aggregates them",
                     "the farmgate kiboko price across the Rwenzori and Elgon belts",
                     "the exporters' stock positions"),
     "constraints": ("two growing belts with different seasons, which smooths the annual profile",
                     "EUDR traceability on smallholder plots",
                     "a world robusta price set in London and not in Kampala"),
     "instruments": ("COFROB", "COFARA"),
     "counterparties": ("the smallholder growers and the hullers",
                        "the international robusta traders", "the banks financing shipments"),
     "observables": ("the monthly export report: bags, dollars, type and destination",
                     "the ICO country export table as the check",
                     "the farmgate kiboko price in the Ugandan press"),
     "impact": "a counted monthly physical flow from the world's number-two robusta exporter, "
               "published ahead of the ICO's own monthly -- the cleanest supply nowcast for "
               "COFROB that exists outside Vietnam",
     "persistence": "monthly, with a two-peak annual seasonality",
     "falsifier": "the UCDA monthly export surprise carries no information about COFROB returns "
                  "over the following week beyond what the Vietnamese export estimate and the "
                  "ICO indicator already carry, measured against a matched-weekday control",
     "notes": "the SECOND-LARGEST robusta exporter publishing a monthly census a fortnight after "
              "the month end is an unusually good data situation for a frontier economy"},
    {"name": "The Ugandan gold refiners and the re-export trade",
     "holds": "licensed refining capacity at and around Entebbe that is far larger than Uganda's "
              "own mine production, and the trade that fills it",
     "forced_to": ("declare exports to customs and pay whatever levy is in force",
                   "source feedstock from a region rather than from Uganda alone",
                   "respond within weeks when a levy makes the declared route uneconomic"),
     "when": "continuously; the 2021 levy took effect 2021-07-01 and the response was visible "
             "within a quarter",
     "information": ("the true origin mix of the feedstock",
                     "the refinery throughput before any statistic publishes",
                     "the alternative routes' cost"),
     "constraints": ("a levy that can price the declared route out of the market",
                     "importing-country due diligence in the UAE and Switzerland",
                     "a regional supply that is mobile by construction"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the regional artisanal and trader networks",
                        "the UAE and Swiss importers", "the Uganda Revenue Authority"),
     "observables": ("the Bank of Uganda's monthly gold export line",
                     "Uganda's own mine production, which is an order of magnitude smaller",
                     "the Comtrade mirror gap against the UAE and Switzerland",
                     "the Finance Act text and its commencement date"),
     "impact": "THE CLEAREST LAWFUL WINDOW ONTO INFORMAL REGIONAL GOLD FLOWS THAT EXISTS. The "
               "2021 levy is a natural experiment: it switched the declared route OFF and the "
               "published series collapsed, then the amendment switched it back on",
     "persistence": "the levy episode is dated and bounded; the structural re-export is a "
                    "multi-year feature",
     "falsifier": "the collapse in Uganda's declared gold exports after 2021-07-01 is matched by "
                  "an equal fall in the UAE's and Switzerland's reported imports FROM Uganda in "
                  "the mirror statistics -- in which case the flow stopped rather than "
                  "re-routing, and the series measures a trade and not a window",
     "notes": "the pack makes NO claim about who mined the metal and needs none: both halves of "
              "the comparison are published by governments, and the gap is the measurement"},
    {"name": "The Tilenga and Kingfisher joint-venture operators and EACOP Ltd",
     "holds": "the Lake Albert development -- about 1.4bn barrels of recoverable oil -- and the "
              "1,443 km heated crude pipeline from Hoima to TANGA in Tanzania",
     "forced_to": ("drill and complete several hundred wells before first oil",
                   "build and heat a pipeline for a waxy crude that will not flow cold",
                   "reach a plateau of roughly 230,000 b/d against a schedule that has already "
                   "slipped more than once"),
     "when": "FID 2022-02-01; first oil targeted 2025-2026 with the ramp following",
     "information": ("well completion counts and facility commissioning before the milestones "
                     "are announced", "the pipeline's welding and pump-station progress",
                     "the financing syndicate's drawdown"),
     "constraints": ("financing, after a sustained campaign against the project's lenders",
                     "a waxy crude that needs a heated line and therefore power along its route",
                     "a landlocked resource whose only export route crosses another country"),
     "instruments": ("XBRUSD", "XNGUSD"),
     "counterparties": ("the Uganda National Oil Company and the Tanzanian state as equity "
                        "partners", "the EPC contractors and the financing syndicate",
                        "the crude buyers who will lift at Tanga"),
     "observables": ("the PAU's project updates and well counts",
                     "EACOP's own welding and station progress releases",
                     "the customs import surge of capital equipment into both countries"),
     "impact": "A DATED CAPACITY RAMP INTO XBRUSD of roughly 230,000 b/d at plateau -- small "
               "against world supply and large against East African trade, and the pack claims "
               "the second and not the first. The pipeline is what makes Uganda and Tanzania ONE "
               "physical system rather than two neighbours",
     "persistence": "decades once producing; the ramp itself is a two-to-three year event",
     "falsifier": "the announced first-oil and ramp milestones show no abnormal behaviour in "
                  "XBRUSD against matched non-event days, and no measurable change in the two "
                  "countries' own trade balances -- the second half is what makes this testable "
                  "at all, because the price half is expected to be small",
     "notes": "the pack tests the TRADE-BALANCE consequence first because it is large and "
              "published, and the price consequence second because it is small and contested"},
    {"name": "The Uganda Revenue Authority as the administrator of the gold export levy",
     "holds": "customs at Entebbe and the border posts, and the collection of whatever export "
              "levy the current Finance Act imposes",
     "forced_to": ("apply the levy from its commencement date whatever the trade's response",
                   "publish collections and trade statistics",
                   "police a border a mobile commodity can cross"),
     "when": "the Finance Act commences on 1 July of each fiscal year; the 2021 levy took effect "
             "2021-07-01 and was amended in the following rounds",
     "information": ("declared consignments in real time",
                     "the seizure and undervaluation cases before they are reported"),
     "constraints": ("a levy set by parliament and not by the authority",
                     "a commodity with a high value-to-weight ratio and a short border"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the refiners and exporters", "the Ministry of Finance",
                        "the neighbouring customs administrations"),
     "observables": ("the Finance Act clause and its commencement date",
                     "URA collections by head", "the declared export tonnage"),
     "impact": "the ADMINISTRATIVE half of EA-M: the levy is the treatment and the declared "
               "export series is the outcome, with a clean commencement date in a gazette",
     "persistence": "each Finance Act lasts a fiscal year and several have amended the levy",
     "falsifier": "the declared-export response to the 2021 commencement date is matched by the "
                  "same move in a neighbouring country's declared gold exports in the same "
                  "quarter, which would make it a regional shock and not a Ugandan policy effect",
     "notes": "the placebo is the OTHER Finance Act clauses that commenced on the same day and "
              "touched nothing to do with gold"},
    {"name": "The Lake Victoria fish exporters and the Entebbe air-freight shippers",
     "holds": "the Nile perch fillet trade to the European Union and the Middle East, and the "
              "cold chain and freighter capacity that carries it",
     "forced_to": ("fly a perishable product to a fixed European clock",
                   "meet EU sanitary approval, which has been suspended and restored before",
                   "buy fuel and freight in dollars while paying for fish in shillings"),
     "when": "continuously, with a Lenten demand peak in Europe and a lake-season supply cycle",
     "information": ("landings and processing throughput before any statistic exists",
                     "the freight-rate and capacity position out of Entebbe"),
     "constraints": ("the lake's own stock and the enforcement of size limits",
                     "EU sanitary approval", "air-freight capacity and jet fuel cost"),
     "instruments": ("XBRUSD", "UK100"),
     "counterparties": ("the fishing communities and the processors",
                        "the European and Middle Eastern importers", "the freight operators"),
     "observables": ("the fish export line in the UBOS trade data",
                     "EU sanitary decisions and their dates",
                     "Entebbe air cargo tonnage"),
     "impact": "a SECOND perishables air-freight leg beside Ethiopia's, which is what makes the "
               "channel testable at all: one country's flower and vegetable trade is a story, "
               "two independent countries' perishable exports moving together is a mechanism",
     "persistence": "seasonal; a sanitary suspension is a dated multi-month event",
     "falsifier": "Ugandan fish and Ethiopian horticulture export tonnages show no common "
                  "component once European demand and global air-freight rates are controlled "
                  "for, which would collapse the whole perishables channel into freight cost",
     "notes": "kept SMALL and honest: this is a physical-economy observable that conditions "
              "other domains, not an edge of its own"},
    # ---------------------------------------------------------------- regional
    {"name": "The mobile-money operators' agent networks across the three",
     "holds": "the payment rail that most households and small traders actually use -- M-Pesa "
              "and Mixx in Tanzania, MTN MoMo and Airtel Money in Uganda, telebirr in Ethiopia "
              "-- and the agent float behind it",
     "forced_to": ("report transaction volumes and values to the central banks, which publish "
                   "them monthly",
                   "hold trust accounts against the float",
                   "absorb a mobile-money tax when one is imposed, as Uganda's was in 2018"),
     "when": "continuously; the statistics publish monthly with a two-to-six week lag",
     "information": ("the real-time transaction value before the central bank aggregates it",
                     "the agent float distribution across regions",
                     "the remittance corridor volumes"),
     "constraints": ("a levy that can push users back to cash, which Uganda measured in 2018",
                     "interoperability rules the regulators set",
                     "agent liquidity in the rural network"),
     "instruments": ("SUGAR", "CORN", "USDZAR"),
     "counterparties": ("the households and small traders", "the banks holding the trust "
                        "accounts", "the central banks and the telecoms regulators",
                        "the diaspora remitters"),
     "observables": ("monthly transaction value and volume",
                     "registered and active agents",
                     "the trust-account balances in the payment-systems reports"),
     "impact": "THE ONLY HIGH-FREQUENCY NOMINAL DEMAND SERIES ANY OF THE THREE PUBLISH. Against "
               "national accounts that arrive annually, a monthly transaction-value series is a "
               "real nowcast of the domestic consumption that drives the region's SUGAR and "
               "CORN import demand",
     "persistence": "structural and growing; a tax change is a dated step",
     "falsifier": "mobile-money transaction value carries no information about the three "
                  "countries' food and sugar IMPORT volumes over the following quarter beyond "
                  "what the CPI and the exchange rate already carry",
     "notes": "THE OPERATORS ARE SINGLE NAMES AND APPEAR ONLY HERE. The brief's warning is the "
              "right one: a desk that declares the app layer absent because there is no domestic "
              "trading-app ecology has missed the macro series the region does publish"},
    {"name": "The Nairobi regional bank treasuries and the corridor freight forwarders",
     "holds": "the regional treasury books, the correspondent dollar lines and the forwarding "
              "contracts that choose between Mombasa and Dar es Salaam for the same cargo",
     "forced_to": ("price and fund three currencies none of which is deliverable offshore",
                   "route a client's cargo through whichever corridor is cheaper and faster "
                   "THIS month",
                   "hold dollar liquidity for subsidiaries in a shortage"),
     "when": "continuously; the routing decision is made per shipment and shows up in the two "
             "ports' statistics a month later",
     "information": ("the corridor cost and transit time before either port publishes",
                     "the group's internal dollar position across the subsidiaries",
                     "the client import pipeline"),
     "constraints": ("capital controls that differ in each of the three",
                     "correspondent-banking risk appetite",
                     "corridor capacity at both ends"),
     "instruments": ("XCUUSD", "USDZAR", "XBRUSD"),
     "counterparties": ("the importers and exporters across the five EAC economies",
                        "the two port authorities and the two rail operators",
                        "the correspondent banks in London and New York"),
     "observables": ("the Mombasa and Dar es Salaam throughput series side by side",
                     "the corridor observatories' transit times",
                     "the regional banking groups' segment disclosures"),
     "impact": "THE INTERACTION THAT MAKES THE `ke` PACK NECESSARY: the same cargo appearing in "
               "one port's statistics and not the other's is a ROUTING event, and only the two "
               "packs together can tell it from a supply event",
     "persistence": "a routing shift can persist for quarters once contracts move",
     "falsifier": "Mombasa and Dar es Salaam transit tonnages move together rather than as "
                  "substitutes once regional import demand is controlled for, which would mean "
                  "the corridors are complements and the routing control is unnecessary",
     "notes": "the regional banking groups are LISTED SINGLE NAMES and appear as actors only"},
)


# --------------------------------------------------------------------------- domains
#: SEVENTEEN DOMAINS: five for Ethiopia, five for Tanzania, four for Uganda and three regional.
#: Each jurisdiction owes at least three of its own, and a domain with fewer than two negative
#: controls is refused by the validator because an effect with no control cannot be told from
#: the desk's own selection.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "EA-A", "title": "ETHIOPIA: the birr float of 2024-07-29 and the two-rate era",
     "objects": ("the NBE directive package that ended the crawling peg and its commencement "
                 "date", "the daily indicative rate before and after the boundary",
                 "the parallel premium as reconstructed in the IMF programme documents",
                 "the letter-of-credit backlog and its clearance",
                 "the CPI pass-through of a depreciation of more than 50%"),
     "conditions": ("the era: administered-rate rationing to 2024-07-28, market-determined after",
                    "the premium bucket in the rationing era (below 50%, 50-100%, above 100%)",
                    "whether an IMF review disbursed in the same quarter"),
     "instruments": ("COFARA", "XAUUSD", "USDZAR"),
     "controls": ("Uganda over the same months -- an open capital account with no rationing at "
                  "all, which is what separates 'East Africa' from 'Ethiopia'",
                  "the Ghanaian and Zambian post-default adjustments as matched frontier cases",
                  "the same windows in the 2017-10 step devaluation, when the regime did NOT "
                  "change and only the level did"),
     "notes": "ETB is absent from the broker and the pack never pretends otherwise: the float is "
              "tested on the EXPORT PHYSICS it changes and on the risk carriers, never on a "
              "currency nobody can quote"},
    {"id": "EA-B", "title": "ETHIOPIA: the ECX floor, arabica supply and the specialty grade mix",
     "objects": ("the ECX daily lot volume, price and grade table",
                 "the crop-year opening in October and the first-delivery week",
                 "the customs export volumes by destination against the ICO country table",
                 "the farmgate cherry price across Sidama, Guji, Yirgacheffe and Harar",
                 "the EUDR traceability requirement on smallholder plots"),
     "conditions": ("the crop-year phase (opening, peak, tail)",
                    "the washed versus natural grade mix of the session",
                    "the era boundary of the float, which changes the birr receipt per dollar",
                    "whether the BELG rains failed in the preceding season"),
     "instruments": ("COFARA", "COFROB", "UKCOCOA"),
     "controls": ("the matched session-and-weekday control on COFARA, because an ECX session is "
                  "a weekday like any other until it is shown not to be",
                  "Brazilian and Colombian export registrations over the same weeks, which "
                  "separates 'arabica supply' from 'Ethiopian supply'",
                  "a block-permuted ECX volume series as the null for a daily-lead claim"),
     "notes": "the ECX print lands BEFORE the New York session, which is the entire reason it is "
              "a candidate lead rather than a coincident observable"},
    {"id": "EA-C", "title": "ETHIOPIA: the GERD filling schedule, Nile water and power exports",
     "objects": ("the filling seasons of July-September from 2020 and the volumes impounded",
                 "the turbine commissioning dates and the installed capacity after each",
                 "Ethiopian power export volumes to Sudan, Djibouti and Kenya",
                 "the Egyptian and Sudanese water-stress reporting in the same seasons"),
     "conditions": ("the filling season versus the rest of the year",
                    "the KIREMT rainfall outcome, which decides how much can be impounded",
                    "whether a trilateral negotiation round was live in the same window"),
     "instruments": ("WHEAT", "CORN", "XBRUSD"),
     "controls": ("the same July-September windows in 2015-2019, before any filling began",
                  "Egyptian wheat tender volumes in non-filling years as the matched control, "
                  "which is the `eg` pack's own series and not this one's",
                  "regional distillate demand in years with no new hydro commissioning"),
     "notes": "THE DIRECT INTERACTION WITH `eg`. Two weak channels running in opposite "
              "directions -- displaced diesel and raised Egyptian import demand -- and the pack "
              "declares both weak rather than choosing the one that sounds better"},
    {"id": "EA-D", "title": "ETHIOPIA: default, the IMF programme and the external adjustment",
     "objects": ("the missed coupon of 2023-12-11 and the grace expiry of 2023-12-26",
                 "the ECF approval of 2024-07-29 and each review Board date",
                 "the Common Framework creditor-committee milestones",
                 "the AGOA suspension effective 2022-01-01 and the garment sector's response",
                 "the Ethiopian Securities Exchange's opening on 2025-01-10"),
     "conditions": ("the programme phase (pre-approval, review passed, review delayed)",
                    "whether a Ghanaian or Zambian milestone fell in the same window",
                    "the risk regime measured on the carriers themselves"),
     "instruments": ("USDZAR", "US500", "UK100"),
     "controls": ("Ghana's and Zambia's own default and restructuring dates as matched frontier "
                  "events, both on the desk's roster",
                  "the same windows on days with a US CPI or FOMC print, which separates 'the "
                  "frontier repriced' from 'the dollar repriced'",
                  "a randomised-date null drawn from the same quarters"),
     "notes": "the honest prior is that a single frontier default has no measurable global "
              "spillover; the point of the domain is to MEASURE that rather than assume it"},
    {"id": "EA-E", "title": "ETHIOPIA: Bole, air freight and the perishables plane",
     "objects": ("Ethiopian air cargo tonnage and the horticulture export line",
                 "the flower season peaks against the European auction clock",
                 "jet fuel offtake at Bole", "conflict-era route and airspace restrictions"),
     "conditions": ("the European demand season (Valentine's, Mother's Day, winter vegetables)",
                    "the air-freight rate regime",
                    "whether the Ugandan fish channel moved in the same month"),
     "instruments": ("XBRUSD", "UK100"),
     "controls": ("the Ugandan Nile perch export series as the INDEPENDENT second perishables "
                  "leg -- one country is a story, two moving together is a mechanism",
                  "global air-freight rate indices, which separate 'African perishables' from "
                  "'freight cost'",
                  "the same months in the pre-2020 years"),
     "notes": "kept small and declared small; the airline is a single name and an actor only"},
    {"id": "EA-F", "title": "TANZANIA: the central bank's domestic gold purchase and the "
                            "mandated offer",
     "objects": ("the FY2023/24 launch of the purchase programme and each year's allocation",
                 "the statutory domestic offer obligation on miners, smelters and dealers, set "
                 "at 20% of production by the 2025 Finance Act",
                 "the licensed refinery capacity that the programme physically depends on",
                 "the gold component of reserves in the monthly economic review",
                 "national production of roughly 50 tonnes split between the three large mines "
                 "and the artisanal market centres"),
     "conditions": ("the budget round that set the offer share and the allocation",
                    "the domestic refining capacity actually licensed in that year",
                    "the dollar-shortage state, which is why the programme exists",
                    "the LBMA price level, since the shilling budget buys fewer ounces when "
                    "gold is dear"),
     "instruments": ("XAUUSD", "XAGUSD"),
     "controls": ("Tanzanian gold EXPORT tonnage in the customs data as the diversion test, "
                  "which is measurable whether or not the price responds",
                  "Ghana's own gold-purchase-for-reserves programme over the same years, the "
                  "sibling African case and a pack on this desk",
                  "the matched-weekday control on XAUUSD around each budget-speech date",
                  "budget rounds that changed OTHER royalty clauses and not the gold offer"),
     "notes": "THE HEADLINE MECHANISM. Two separately falsifiable halves: a PHYSICAL diversion "
              "measurable in the customs data, and a PRICE response measurable on the "
              "announcement dates. The first can be true while the second is not, and that is a "
              "result rather than a failure"},
    {"id": "EA-G", "title": "TANZANIA: Dar es Salaam and the Central Corridor as the copper and "
                            "cobalt chokepoint",
     "objects": ("Tanzania Ports Authority throughput with the transit-by-destination split",
                 "the Central Corridor transit-time observatory",
                 "TAZARA and the standard-gauge railway's tonnage",
                 "the Kasumbalesa and Tunduma border processing times",
                 "the competing corridors: Mombasa, Beira, Walvis Bay and Lobito"),
     "conditions": ("the southern-African rainy season, which decides the road condition",
                    "the Congolese and Zambian production season",
                    "whether the Lobito corridor was taking volume in the same months",
                    "port dwell time above or below its own interquartile range"),
     "instruments": ("XCUUSD", "XNIUSD", "XBRUSD"),
     "controls": ("MOMBASA's throughput over the same months, from the `ke` pack -- a cargo that "
                  "moved between corridors is a routing event and not a supply event, and only "
                  "the two series together can tell them apart",
                  "Chinese refined-copper import volumes, which separate 'supply timing' from "
                  "'demand'",
                  "months in which transit fell for a declared strike or maintenance reason, as "
                  "the exogenous subset"),
     "notes": "the cobalt payable itself is LICENSED and registered machine_use_allowed=false, "
              "so the domain is measured on COPPER, which this broker quotes"},
    {"id": "EA-H", "title": "TANZANIA: the cashew auction, cotton and the crop-board regime",
     "objects": ("weekly cashew auction volumes and the indicative price through the season",
                 "the 2018 auction collapse and the state's direct purchase of the crop",
                 "the warehouse-receipt system and the cooperative unions' reserve prices",
                 "cotton lint and sisal export volumes as the sibling smallholder crops"),
     "conditions": ("the season phase (October opening, December peak, January tail)",
                    "whether the indicative price was set above the clearing bid",
                    "the Indian and Vietnamese buying season"),
     "instruments": ("COTTON", "SUGAR"),
     "controls": ("the same weeks in seasons that cleared normally",
                  "the world cashew price as reported in the trade letters, which separates "
                  "'Tanzania's auction failed' from 'the crop is cheap everywhere'",
                  "Mozambique's and Ivory Coast's cashew seasons as the matched producers"),
     "notes": "there is NO cashew contract and the pack refuses to invent one: the auction "
              "conditions the export-earnings state of EA-I and reaches a price only through "
              "COTTON as the sibling crop, labelled WEAK on its face"},
    {"id": "EA-I", "title": "TANZANIA: the managed float and the 2023-24 dollar shortage",
     "objects": ("the daily IFEM indicative rate and the BoT's interventions",
                 "the bureau-de-change survey and its spread to the IFEM rate",
                 "IFEM turnover, which is the QUANTITY read a managed rate hides",
                 "reserves in months of imports and the fuel import queue"),
     "conditions": ("the spread bucket between the bureau and the IFEM rate",
                    "reserve cover above or below four months of imports",
                    "whether a fuel or fertiliser cargo was publicly delayed in the same month"),
     "instruments": ("XAUUSD", "XBRUSD", "USDZAR"),
     "controls": ("Uganda's freely floating shilling over the same months, the clean control",
                  "the same spread state in 2019-2021, before the shortage",
                  "a block-permuted spread series as the null for a state-variable claim"),
     "notes": "the quantity read matters more than the price read under a managed rate, which is "
              "the same insight that makes Nigeria's turnover print and Kenya's published "
              "buy/sell spread valuable -- arriving here in a third form"},
    {"id": "EA-J", "title": "TANZANIA: power, gas and the Julius Nyerere commissioning",
     "objects": ("load-shedding episodes and their dates",
                 "the Julius Nyerere units' commissioning schedule, about 2.1 GW in total",
                 "gas offtake from Songo Songo and Mnazi Bay",
                 "the Lindi LNG project's negotiation and FID milestones"),
     "conditions": ("the unimodal hydrology season of November to April",
                    "whether a Julius Nyerere unit commissioned in the same quarter",
                    "the mines' own reported quarterly tonnage"),
     "instruments": ("XNGUSD", "XAUUSD", "XCUUSD"),
     "controls": ("the mines' quarterly tonnage in quarters with no load shedding",
                  "Zambian and Ghanaian load-shedding episodes as matched African cases",
                  "the same quarters before the first Julius Nyerere unit"),
     "notes": "tested on PRODUCTION first, because production is published and the price claim "
              "is small; an energy-to-mining claim that cannot be seen in tonnage is not a "
              "mechanism"},
    {"id": "EA-K", "title": "UGANDA AND TANZANIA: the Lake Albert ramp and the EACOP pipeline",
     "objects": ("FID on 2022-02-01 and the first-oil target of 2025-2026",
                 "the PAU's well completion and facility commissioning milestones",
                 "EACOP's welding, pump-station and Tanga terminal progress",
                 "the capital-equipment import surge in both countries' trade data",
                 "the plateau target of roughly 230,000 b/d"),
     "conditions": ("the project phase (pre-FID, construction, first oil, ramp)",
                    "whether a financing or schedule slip was announced in the same window",
                    "the Brent level, since the project's own economics move with it"),
     "instruments": ("XBRUSD", "XNGUSD"),
     "controls": ("the two countries' own trade balances, which is where a ramp of this size IS "
                  "large and is the half the pack tests first",
                  "matched non-event days for the milestone announcements",
                  "Ghana's and Senegal's first-oil ramps as the sibling African cases"),
     "notes": "230,000 b/d is small against world supply and large against East African trade; "
              "the pack claims the second, measures the first, and says which is which"},
    {"id": "EA-L", "title": "UGANDA: robusta, the UCDA monthly census and the two growing belts",
     "objects": ("the monthly export report: bags, value, type and destination",
                 "the farmgate kiboko price across the Rwenzori and Elgon belts",
                 "the two-peak annual seasonality the two belts create",
                 "the EUDR traceability requirement on smallholder plots"),
     "conditions": ("the month's position in the two-peak cycle",
                    "the surprise against the trailing twelve-month seasonal norm",
                    "the Vietnamese export estimate in the same month"),
     "instruments": ("COFROB", "COFARA"),
     "controls": ("the Vietnamese monthly export estimate, which separates 'robusta supply' from "
                  "'Ugandan supply'",
                  "the matched-weekday control on COFROB around each publication date",
                  "months in which the UCDA print matched its own seasonal norm, as the null"),
     "notes": "a monthly census from the world's number-two robusta exporter, published a "
              "fortnight after the month end -- an unusually good data situation, and the reason "
              "this domain has a real event clock while several others do not"},
    {"id": "EA-M", "title": "UGANDA: the gold re-export gap and the 2021 levy as a natural "
                            "experiment",
     "objects": ("the Bank of Uganda's monthly gold export line",
                 "Uganda's own mine production, an order of magnitude smaller",
                 "the Comtrade mirror gap against the UAE and Switzerland",
                 "the Finance Act 2021 levy, in force 2021-07-01, and its later amendment",
                 "the licensed refinery capacity at and around Entebbe"),
     "conditions": ("the levy regime (none, in force, amended)",
                    "the declared-to-produced ratio bucket",
                    "the LBMA price level and the regional artisanal season"),
     "instruments": ("XAUUSD",),
     "controls": ("the UAE's and Switzerland's reported imports FROM Uganda over the same "
                  "quarters -- if they fell too, the flow stopped rather than re-routing",
                  "Rwanda's and Kenya's declared gold exports in the same quarters, the "
                  "neighbouring routes",
                  "the OTHER Finance Act clauses that commenced on the same day and touched "
                  "nothing to do with gold, as the placebo"),
     "notes": "THE CLEANEST LAWFUL WINDOW ONTO AN INFORMAL PHYSICAL FLOW IN THIS PACK. The pack "
              "makes no claim about who mined the metal and needs none: both halves of the "
              "comparison are published by governments"},
    {"id": "EA-N", "title": "UGANDA: inflation targeting, the CBR and the regional control",
     "objects": ("the CBR decisions since July 2011 and the MPC statements",
                 "the UBOS CPI, published on the last working day of the reference month",
                 "the weekly bill auction cut-off and the interbank rate",
                 "the oil-driven import surge ahead of first oil"),
     "conditions": ("the cycle phase (hiking, holding, easing)",
                    "whether the food line drove the CPI surprise",
                    "the pre-first-oil import surge"),
     "instruments": ("COFROB", "USDZAR", "XAUUSD"),
     "controls": ("the same windows on non-meeting days, matched by weekday",
                  "South African and Ghanaian MPC days, the other two sub-Saharan inflation "
                  "targeters, both on the desk's roster",
                  "the same windows on days carrying a US CPI or FOMC print"),
     "notes": "Uganda is the CONTROL JURISDICTION of this pack: a clean float with an open "
              "capital account beside a former peg and a managed float. A null here is a useful "
              "result and not a failure"},
    {"id": "EA-O", "title": "REGIONAL: mobile money as the only high-frequency nominal series",
     "objects": ("monthly transaction value and volume in all three",
                 "registered and active agents, and the trust-account float",
                 "Uganda's 2018 mobile-money tax as a dated step in the series",
                 "telebirr's user and value growth from 2021"),
     "conditions": ("the tax regime in force",
                    "the harvest and remittance seasons",
                    "the interoperability rules in force"),
     "instruments": ("SUGAR", "CORN", "USDZAR"),
     "controls": ("the CPI and the exchange rate, which a nominal series must beat to carry any "
                  "information at all",
                  "the same months before the 2018 Ugandan tax, as the pre-treatment sample",
                  "Kenya's own M-Pesa series from the `ke` ground, the regional original"),
     "notes": "the brief's warning is the right one and the pack acts on it: the app layer here "
              "is the PAYMENT rail, its statistics are published monthly by central banks, and "
              "declaring the layer absent because there is no trading-app ecology would be "
              "reading the wrong country"},
    {"id": "EA-P", "title": "REGIONAL: three calendars, three sighting authorities and one clock",
     "objects": ("the Ge'ez calendar's Enkutatash and Meskel, which alternate by one day",
                 "Genna and Timkat as fixed Julian feasts",
                 "Fasika by the Julian computus against the Western Easter that closes Dar es "
                 "Salaam and Kampala",
                 "the Eids announced by three different authorities that need not agree",
                 "East Africa Time as a fixed UTC+3 with no daylight saving anywhere"),
     "conditions": ("which of the three is closed and which is open",
                    "whether an Ethiopian and a Western movable feast coincided",
                    "the ANNOUNCED versus PROJECTED status of a lunar row"),
     "instruments": ("XAUUSD", "COFARA", "COFROB"),
     "controls": ("the matched weekday twenty-six weeks away, the standard holiday-liquidity "
                  "control",
                  "days on which only ONE of the three closed, which separates a regional effect "
                  "from a national one",
                  "the same dates in years when the feast fell on a weekend and cost no session"),
     "notes": "the one calendar plane on this desk where three national calendars, two Easters "
              "and three sighting authorities overlap -- and where NO daylight saving means the "
              "UTC windows are stable all year, unlike Morocco's"},
    {"id": "EA-Q", "title": "REGIONAL: corridor competition and Kenya as the financial hub",
     "objects": ("Mombasa and Dar es Salaam throughput side by side",
                 "the Northern and Central Corridor transit-time observatories",
                 "the Nairobi cross-listings on the Uganda Securities Exchange",
                 "the regional banking groups' dollar liquidity across subsidiaries",
                 "the EAC common external tariff and its exemptions"),
     "conditions": ("which corridor was cheaper and faster in the month",
                    "whether a strike, flood or border closure hit one route only",
                    "the regional dollar-liquidity state"),
     "instruments": ("XCUUSD", "USDZAR", "XBRUSD", "COFROB"),
     "controls": ("the `ke` pack's own Mombasa and Northern Corridor series, which is the whole "
                  "point of running the two packs as complements",
                  "total EAC import volumes, which separate 'the region imported less' from "
                  "'the cargo used the other port'",
                  "months with no declared disruption on either corridor"),
     "notes": "THE COMPLEMENT RULE, stated as a domain: `ke` owns Mombasa, the Northern Corridor, "
              "the published CBK buy/sell spread and the Kenyan two-season cycle; this pack owns "
              "the Central Corridor, the three other currencies and the Ethiopian BELG/KIREMT "
              "seasons. Neither can tell routing from supply alone"},
)

# --------------------------------------------------------------------------- custom miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ea_gold_offer_regime", "domain_ids": ("EA-F", "EA-M"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_gold_offer_regime",
     "needs": ("GOLD_POLICY_EVENTS", "XAUUSD and XAGUSD H1 bars",
               "Tanzanian customs gold export tonnage", "BoU monthly gold export line"),
     "notes": "the Tanzanian mandated-offer and the Ugandan levy dates in one clock, because "
              "they are the same mechanism -- an administered change in where physical gold may "
              "lawfully go -- pointed in opposite directions"},
    {"name": "ea_birr_float_boundary", "domain_ids": ("EA-A", "EA-B"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_birr_float_boundary",
     "needs": ("POLICY_ERAS", "COFARA D1 bars", "ECX daily prints", "IMF review dates"),
     "notes": "the 2024-07-29 boundary as a regime break on the export physics, with Uganda over "
              "the same months as the no-rationing control"},
    {"name": "ea_coffee_export_census", "domain_ids": ("EA-L", "EA-B"), "kind": "release",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_coffee_export_census",
     "needs": ("UCDA monthly report dates", "ECX session calendar", "COFROB and COFARA H1 bars"),
     "notes": "the UCDA monthly surprise against its own trailing seasonal norm, with the "
               "Vietnamese export estimate as the separating control"},
    {"name": "ea_corridor_chokepoint", "domain_ids": ("EA-G", "EA-Q"), "kind": "physical",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_corridor_chokepoint",
     "needs": ("TPA throughput with the transit split", "Mombasa throughput from the ke ground",
               "XCUUSD and XNIUSD D1 bars"),
     "notes": "a transit fall is a ROUTING event until Mombasa's series says it is not, which is "
              "why this miner cannot run without the sibling pack's ground"},
    {"name": "ea_oil_ramp_milestones", "domain_ids": ("EA-K", "EA-J"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_oil_ramp_milestones",
     "needs": ("OIL_RAMP_EVENTS", "XBRUSD H1 bars", "the two countries' trade balances"),
     "notes": "the trade-balance half is tested first because it is large and published; the "
              "price half is tested second because it is small and contested"},
    {"name": "ea_calendar_plane", "domain_ids": ("EA-P",),
     "kind": "calendar", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_calendar_plane",
     "needs": ("HOLIDAYS_RULE", "XAUUSD, COFARA and COFROB H1 bars"),
     "notes": "three national calendars, two Easters and three sighting authorities, with the "
              "one-country-closed days as the separating control"},
    {"name": "ea_transmission_seeds",
     "domain_ids": ("EA-C", "EA-D", "EA-E", "EA-H", "EA-I", "EA-N", "EA-O"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.east_africa.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("EA-N", "EA-A"), "release_surprise": ("EA-L", "EA-B", "EA-N"),
    "calendar_settlement": ("EA-P", "EA-H"), "holiday_liquidity": ("EA-P",),
    "positioning": ("EA-D",), "carry_funding": ("EA-I", "EA-N"),
    "corporate_flow": ("EA-F", "EA-K"), "institutional_flow": ("EA-D", "EA-O"),
    "equity_mechanics": ("EA-D",), "derivatives_expiry": ("EA-D",),
    "failure": ("EA-I", "EA-J"), "residual": ("EA-A", "EA-C"),
    "transfer": ("EA-G", "EA-Q"), "scouts": ("EA-E", "EA-M"),
    "session_microstructure": ("EA-P", "EA-B"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "EA-E1", "source": "Bank of Tanzania domestic gold purchase allocation and the "
                              "statutory domestic offer share",
     "target": "XAUUSD", "targets": ("XAUUSD", "XAGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a top-fifteen producer's central bank buys domestically and the state "
                  "requires miners, smelters and dealers to OFFER a share of output at home; "
                  "tonnes that would have been exported as dore are bought and held instead, "
                  "which is official-sector demand and a supply diversion at once",
     "horizon": "1 to 4 quarters for the diversion; 0 to 3 sessions for the announcement",
     "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Bank of Tanzania's purchase desk and the Mining Commission",
     "constraint": "licensed domestic refining capacity, which is the binding physical limit",
     "flow": "domestic purchase and reserve accumulation instead of dore export",
     "condition": "a budget round that raised the mandated offer share or the allocation",
     "control": "Ghana's own gold-purchase-for-reserves programme over the same years; the "
                "matched-weekday control on XAUUSD around each budget-speech date; budget "
                "rounds that changed other royalty clauses and not the gold offer",
     "falsifier": "budget rounds that raised the mandated offer show no fall in Tanzanian gold "
                  "EXPORT tonnage in the customs data against matched years, which would make "
                  "the programme an accounting transfer and not a supply event",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E2", "source": "Uganda's gold export levy (Finance Act 2021, in force 2021-07-01) "
                              "and its later amendment",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "-",
     "mechanism": "an export levy on a commodity with a very high value-to-weight ratio "
                  "switches a declared re-export route off; Uganda's published gold exports "
                  "collapsed within a quarter of commencement and recovered after the amendment, "
                  "which makes the levy a dated treatment on a published physical series",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the licensed Ugandan refiners and the Uganda Revenue Authority",
     "constraint": "a mobile regional supply that can cross a border instead",
     "flow": "declared re-export through Entebbe, on or off",
     "condition": "a Finance Act commencement or amendment date touching the gold levy",
     "control": "the UAE's and Switzerland's reported imports FROM Uganda over the same "
                "quarters; Rwanda's and Kenya's declared gold exports; the other Finance Act "
                "clauses that commenced the same day",
     "falsifier": "the collapse in Uganda's declared exports is matched by an equal fall in the "
                  "importers' mirror statistics, which would mean the flow stopped rather than "
                  "re-routed and the series measures a trade, not a window",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "EA-E3", "source": "The Ethiopian birr float of 2024-07-29 and the export receipt it "
                              "doubled",
     "target": "COFARA", "targets": ("COFARA", "COFROB"), "to_country": "global", "sign": "+",
     "mechanism": "a currency that halves in dollar terms doubles the local-currency receipt on "
                  "a dollar coffee sale; at the margin that pulls held stock to market and "
                  "raises the delivered share of the crop, which is a SUPPLY effect on arabica "
                  "from the world's fifth-largest producer",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the Ethiopian exporters, cooperatives and washing stations",
     "constraint": "washing-station throughput and the registered-contract regime",
     "flow": "farmgate supply response and export delivery",
     "condition": "the crop years either side of the 2024-07-29 boundary",
     "control": "Uganda over the same months, which had no regime change at all; Brazilian and "
                "Colombian registrations, which separate 'arabica' from 'Ethiopia'; the 2017-10 "
                "step devaluation, when the level moved and the regime did not",
     "falsifier": "Ethiopian arabica export volumes and delivered ECX tonnage show no change in "
                  "level or seasonality across the boundary once the crop year and the global "
                  "arabica price are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E4", "source": "ECX daily delivered tonnage and grade mix, published before the "
                              "New York coffee session opens",
     "target": "COFARA", "targets": ("COFARA",), "to_country": "global", "sign": "-",
     "mechanism": "a mandatory exchange produces something close to a daily CENSUS of Ethiopian "
                  "export supply; a delivered tonnage well above its own seasonal norm is "
                  "arabica arriving, and the print lands hours before New York opens",
     "horizon": "0 to 3 sessions", "horizon_class": "intraday", "lag_days": 1.0,
     "actor": "the Ethiopian Commodity Exchange and the licensed exporters",
     "constraint": "warehouse and transport capacity at the crop-year opening",
     "flow": "graded physical supply reaching the export channel",
     "condition": "a session whose delivered tonnage sits outside its trailing seasonal band",
     "control": "the matched session-and-weekday control on COFARA; a block-permuted ECX volume "
                "series as the null; Brazilian registrations over the same weeks",
     "falsifier": "ECX delivered tonnage carries no information about the following session's "
                  "COFARA return beyond what the previous New York session and the ICO indicator "
                  "already carry",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E5", "source": "UCDA monthly robusta export volume against its trailing seasonal "
                              "norm",
     "target": "COFROB", "targets": ("COFROB", "COFARA"), "to_country": "global", "sign": "-",
     "mechanism": "the world's number-two robusta exporter publishes a monthly census of bags "
                  "and dollars a fortnight after the month end, ahead of the ICO's own monthly; "
                  "a surprise against the seasonal norm is supply news on a market whose other "
                  "big number comes from Vietnam",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the UCDA and the registered Ugandan exporters",
     "constraint": "two growing belts with different seasons, which smooths the annual profile",
     "flow": "registered export shipments",
     "condition": "a monthly print outside its trailing twelve-month seasonal band",
     "control": "the Vietnamese monthly export estimate; the matched-weekday control on COFROB; "
                "months in which the print matched its own norm",
     "falsifier": "the UCDA monthly surprise carries no information about COFROB over the "
                  "following week beyond what the Vietnamese estimate and the ICO indicator "
                  "already carry",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E6", "source": "Central Corridor transit tonnage and Dar es Salaam dwell time",
     "target": "XCUUSD", "targets": ("XCUUSD", "XNIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "Zambian and Congolese copper and cobalt leave through Dar es Salaam; a "
                  "blockage on the corridor or at the port delays metal reaching the sea, which "
                  "is a supply-timing effect with a published physical count behind it",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 21.0,
     "actor": "Tanzania Ports Authority, TAZARA and the corridor forwarders",
     "constraint": "berth, crane and rail capacity, and the rainy-season road condition",
     "flow": "transit metal to the sea",
     "condition": "a month in which transit tonnage fell more than its own interquartile range",
     "control": "MOMBASA's throughput over the same months from the `ke` pack -- a diversion is "
                "a routing event, not a supply event; Chinese refined-copper imports; months "
                "with a declared strike or maintenance cause as the exogenous subset",
     "falsifier": "months of large transit falls show no abnormal XCUUSD behaviour against "
                  "matched months once Chinese demand and LME stocks are controlled for, which "
                  "would mean the metal simply used another corridor",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E7", "source": "Tilenga, Kingfisher and EACOP milestones on the way to first oil",
     "target": "XBRUSD", "targets": ("XBRUSD",), "to_country": "global", "sign": "-",
     "mechanism": "a dated capacity ramp toward roughly 230,000 b/d at plateau, from a "
                  "landlocked resource whose only export route is a heated pipeline across "
                  "Tanzania; the milestones are published and the slips are themselves events",
     "horizon": "1 to 8 quarters", "horizon_class": "multi_day", "lag_days": 120.0,
     "actor": "the Tilenga and Kingfisher operators, UNOC and EACOP Ltd",
     "constraint": "financing, a waxy crude that needs a heated line, and a schedule that has "
                   "slipped more than once",
     "flow": "new crude supply reaching the sea at Tanga",
     "condition": "an announced first-oil, commissioning or slip milestone",
     "control": "the two countries' own trade balances, where a ramp of this size IS large; "
                "matched non-event days; Ghana's and Senegal's first-oil ramps",
     "falsifier": "the announced milestones show no abnormal XBRUSD behaviour against matched "
                  "non-event days AND no measurable change in either country's trade balance, "
                  "which would mean the schedule is not informative at all",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E8", "source": "Tanzanian gas: Songo Songo and Mnazi Bay offtake, the Julius "
                              "Nyerere commissioning and the Lindi LNG milestones",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "-",
     "mechanism": "new hydro DISPLACES gas-fired generation in the domestic stack, and an LNG "
                  "FID at Lindi would be a dated multi-year supply addition to the seaborne "
                  "market; both are small and both are published",
     "horizon": "1 to 8 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "TANESCO, the Songo Songo and Mnazi Bay operators and the LNG partners",
     "constraint": "transmission capacity and a tariff set below the marginal unit's cost",
     "flow": "domestic gas offtake and, prospectively, seaborne LNG",
     "condition": "a commissioning or FID milestone quarter",
     "control": "the same quarters before the first Julius Nyerere unit; Mozambican LNG "
                "milestones as the neighbouring case; quarters with no commissioning",
     "falsifier": "commissioning quarters show no change in domestic gas offtake, which would "
                  "put the displacement entirely inside industrial demand growth",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E9", "source": "GERD filling seasons and turbine commissioning dates",
     "target": "WHEAT", "targets": ("WHEAT", "CORN", "XBRUSD"), "to_country": "eg", "sign": "+",
     "mechanism": "TWO WEAK CHANNELS IN OPPOSITE DIRECTIONS, declared as such: a filling season "
                  "that tightens Egyptian water raises Egyptian agricultural import demand "
                  "(positive for WHEAT and CORN), while commissioned hydro displaces regional "
                  "diesel and heavy-fuel generation (negative for distillate)",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "Ethiopian Electric Power and the Egyptian and Sudanese water ministries",
     "constraint": "the KIREMT rains, which are the only season with enough water to impound",
     "flow": "impounded water and commissioned capacity",
     "condition": "a July-September filling season or a commissioning date",
     "control": "the same July-September windows in 2015-2019, before any filling; Egyptian "
                "wheat tender volumes in non-filling years, which is the `eg` pack's series; "
                "regional distillate demand in years with no commissioning",
     "falsifier": "filling seasons and commissioning dates show no abnormal behaviour in "
                  "Egyptian wheat tender volumes or regional distillate demand against matched "
                  "pre-2020 seasons",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E10", "source": "The EU Deforestation Regulation's traceability requirement on "
                               "East African smallholder coffee and cocoa",
     "target": "COFROB", "targets": ("COFROB", "UKCOCOA", "USCOCOA"), "to_country": "europe",
     "sign": "+",
     "mechanism": "a per-plot traceability requirement is a fixed compliance cost spread over a "
                  "smallholder's very small output, which is why it bites hardest exactly where "
                  "East Africa sells; the predicted signature is a WIDENING of the EU-facing "
                  "against the non-EU-facing price, i.e. the London-New York cocoa spread and "
                  "the EU share of robusta destinations",
     "horizon": "1 to 4 quarters around each application date",
     "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the Ugandan and Ethiopian smallholders, the exporters and the EU importers",
     "constraint": "plot-level geolocation on farms of under a hectare",
     "flow": "destination re-routing of compliant and non-compliant lots",
     "condition": "the quarters around each announced EUDR application or delay date",
     "control": "the same spread in the quarters before the regulation was adopted; Brazilian "
                "and Vietnamese destination shares, which are far less smallholder-dominated; "
                "the delay announcements as their own placebo, since a delay should REVERSE the "
                "sign if the mechanism is real",
     "falsifier": "the EU share of Ugandan and Ethiopian coffee destinations does not move "
                  "across the application and delay dates, and the London-New York cocoa spread "
                  "shows nothing at those dates either",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E11", "source": "The Tanzanian dollar shortage: the bureau-to-IFEM spread and "
                               "reserve cover",
     "target": "XBRUSD", "targets": ("XBRUSD", "XAUUSD", "USDZAR"), "to_country": "global",
     "sign": "-",
     "mechanism": "a dollar shortage rations imports before it moves any published rate: fuel "
                  "and fertiliser cargoes are delayed, the physical demand is deferred rather "
                  "than destroyed, and the deferral shows up as a lumpy catch-up later",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Bank of Tanzania and the importers' banks",
     "constraint": "reserve cover in months of imports",
     "flow": "rationed import settlement",
     "condition": "a month in the widest quartile of the bureau-to-IFEM spread",
     "control": "Uganda's freely floating shilling over the same months; the same spread state "
                "in 2019-2021 before the shortage; a block-permuted spread series as the null",
     "falsifier": "wide-spread months show no subsequent catch-up in Tanzanian fuel import "
                  "volumes against matched months, which would mean the demand was destroyed "
                  "and not deferred",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E12", "source": "Ethiopian default, Common Framework and IMF review milestones",
     "target": "USDZAR", "targets": ("USDZAR", "US500", "UK100"), "to_country": "global",
     "sign": "+",
     "mechanism": "the third African default of the cycle after Zambia and Ghana, read by the "
                  "same investors who hold the rand and the frontier credit complex; the honest "
                  "prior is that a single frontier default has NO measurable global spillover, "
                  "and the point of the edge is to measure that rather than assume it",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Ethiopian debt office, the bondholder committee and the IMF Board",
     "constraint": "comparability of treatment between bondholders and bilaterals",
     "flow": "a repricing of frontier credit risk, if any",
     "condition": "a dated default, committee or Board event",
     "control": "Ghana's and Zambia's own restructuring dates as matched frontier events; the "
                "same windows on US CPI and FOMC days; a randomised-date null from the same "
                "quarters",
     "falsifier": "Ethiopian milestone days show no abnormal behaviour in USDZAR or the frontier "
                  "complex against matched non-event days -- a NULL that is worth having, "
                  "because it prices how much 'frontier risk' is one thing",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E13", "source": "Mobile-money transaction value across the three as a monthly "
                               "nominal-demand nowcast",
     "target": "SUGAR", "targets": ("SUGAR", "CORN", "USDZAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "the only high-frequency nominal series any of the three publish; against "
                  "national accounts that arrive annually, a monthly transaction-value print "
                  "nowcasts the domestic consumption that drives the region's sugar and maize "
                  "import demand",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the mobile-money operators' agent networks and the central banks that publish",
     "constraint": "a mobile-money tax can push users back to cash, as Uganda's did in 2018",
     "flow": "household nominal spending through the payment rail",
     "condition": "a quarter in which transaction value grew outside its own trailing band",
     "control": "the CPI and the exchange rate, which the series must beat to carry anything; "
                "the months before the 2018 Ugandan tax as the pre-treatment sample; Kenya's "
                "own M-Pesa series from the `ke` ground",
     "falsifier": "transaction value carries no information about the three countries' food and "
                  "sugar import volumes over the following quarter beyond what the CPI and the "
                  "exchange rate already carry",
     "evidence": "HYPOTHESIS"},
    {"id": "EA-E14", "source": "The Tanzanian cashew auction's indicative price and clearing, "
                               "and the sibling smallholder crops",
     "target": "COTTON", "targets": ("COTTON", "SUGAR"), "to_country": "global", "sign": "+",
     "mechanism": "a state auction that sets an indicative price above the clearing bid stops "
                  "the crop moving, which removes export earnings from an economy already short "
                  "of dollars; the price leg reaches a broker symbol only through COTTON as the "
                  "sibling smallholder export crop, and the pack labels that leg WEAK on its face",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the Cashewnut Board, the cooperative unions and the Indian and Vietnamese buyers",
     "constraint": "a buyer base concentrated in two countries",
     "flow": "auction clearing and export shipment",
     "condition": "a season in which the indicative price sat above the clearing bid",
     "control": "seasons that cleared normally; the world cashew price from the trade letters, "
                "which separates 'the auction failed' from 'the crop is cheap everywhere'; "
                "Mozambique's and Ivory Coast's seasons",
     "falsifier": "badly clearing seasons show no Tanzanian export-earnings shortfall against "
                  "matched seasons once the world cashew price is controlled for",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "ETHIOPIA: the crawling peg and the rationing queue", "start": "2017-10-11",
     "end": "2024-07-28",
     "regime": "a 15% step devaluation in October 2017 followed by a crawl, an FX surrender "
               "requirement on exporters and an allocation queue for importers; the parallel "
               "premium ran above 100% by 2023 and reserves fell toward two weeks of imports",
     "markers": ("2017-10-11 the 15% devaluation", "2019 the NBE-bill subscription ends",
                 "2023 the parallel premium passes 100%"),
     "why_it_matters": "every Ethiopian price, CPI and trade vintage from this era was collected "
                       "under an ADMINISTERED rate and a rationed import regime; pooling it with "
                       "the post-float data measures two different economies and calls it one",
     "status": "SETTLED"},
    {"name": "ETHIOPIA: the Tigray conflict and the AGOA suspension", "start": "2020-11-04",
     "end": "2022-11-02",
     "regime": "armed conflict in the north from November 2020 to the Pretoria cessation of "
               "hostilities agreement of 2022-11-02; the United States terminated Ethiopia's "
               "AGOA eligibility with effect from 2022-01-01, which removed duty-free access "
               "for the garment sector built around the industrial parks",
     "markers": ("2020-11-04 the conflict begins", "2022-01-01 AGOA eligibility terminated",
                 "2022-11-02 the Pretoria agreement"),
     "why_it_matters": "trade, freight and coffee-logistics series from this window carry a "
                       "conflict and a trade-preference shock at once; a study that pools it "
                       "with normal years is attributing a war to a season",
     "status": "SETTLED"},
    {"name": "ETHIOPIA: default and the Common Framework", "start": "2023-12-11",
     "end": "2026-12-31",
     "regime": "the coupon due 2023-12-11 was missed and the grace period expired on 2023-12-26, "
               "making Ethiopia the third African default of the cycle; restructuring runs under "
               "the G20 Common Framework with a bondholder committee and an official creditor "
               "committee that must reach comparability",
     "markers": ("2023-12-11 the missed coupon", "2023-12-26 the grace period expires",
                 "2025-01-10 the Ethiopian Securities Exchange opens"),
     "why_it_matters": "the sovereign's external financing is in negotiation, so an Ethiopian "
                       "risk event in this era is a RESTRUCTURING event and not a market one",
     "status": "OPEN"},
    {"name": "ETHIOPIA: the float and the IMF programme", "start": "2024-07-29",
     "end": "2026-12-31",
     "regime": "the NBE's directive package of 2024-07-29 ended the administered rate; the birr "
               "lost more than half its value within weeks, the parallel premium collapsed "
               "toward the official rate, an IMF Extended Credit Facility of about US$3.4bn was "
               "approved the same day, and a National Bank Rate was introduced as the country's "
               "first policy rate",
     "markers": ("2024-07-29 the float directive and the ECF approval",
                 "2024-07 the National Bank Rate is introduced",
                 "2025-01-10 the ESX opens for trading"),
     "why_it_matters": "THE BOUNDARY THAT PARTITIONS EVERY ETHIOPIAN SERIES IN THIS PACK. One of "
                       "the cleanest emerging-market regime breaks of the decade, and the reason "
                       "EA-A exists as a domain rather than as a paragraph",
     "status": "OPEN"},
    {"name": "TANZANIA: the resource-nationalism reset", "start": "2017-03-03",
     "end": "2020-01-24",
     "regime": "a ban on the export of unprocessed mineral concentrates from March 2017, the "
               "Mining (Amendment) and sovereignty Acts of 2017, a multi-billion-dollar tax "
               "dispute with the largest operator, and a settlement in 2019-2020 that created a "
               "joint venture with a 16% free-carried government interest",
     "markers": ("2017-03-03 the concentrate export ban",
                 "2017-07 the Mining (Amendment) Act and the sovereignty legislation",
                 "2020-01-24 the joint-venture settlement completes"),
     "why_it_matters": "Tanzanian export tonnage, royalty receipts and company disclosures all "
                       "change definition inside this window; it is also the era that built the "
                       "institutions -- the market centres and the domestic refining requirement "
                       "-- that the gold purchase programme later depended on",
     "status": "SETTLED"},
    {"name": "TANZANIA: the central bank buys gold at home", "start": "2023-07-01",
     "end": "2026-12-31",
     "regime": "a formal domestic gold purchase programme for reserves funded from FY2023/24, a "
               "domestic refining requirement, and a statutory obligation on licensed miners, "
               "smelters and dealers to offer a share of output to the domestic market -- set at "
               "20% of production by the 2025 Finance Act",
     "markers": ("2023-06 the budget speech announcing the programme",
                 "2023-07-01 FY2023/24 begins and the allocation takes effect",
                 "2025-07-01 the 20% domestic offer obligation commences"),
     "why_it_matters": "a dated, published change in where physical gold from a top-fifteen "
                       "producer may lawfully go; every EA-F cell is conditioned on which budget "
                       "round it sits in, because the share and the allocation change annually",
     "status": "OPEN"},
    {"name": "TANZANIA: the dollar shortage and the move to an interest-rate framework",
     "start": "2023-01-01", "end": "2025-12-31",
     "regime": "a visible foreign-exchange shortage through 2023 and 2024 with a widening "
               "bureau-to-IFEM spread and delayed fuel cargoes, alongside the Bank of Tanzania's "
               "move from a monetary-aggregate framework to a Central Bank Rate in January 2024",
     "markers": ("2023 the bureau spread widens and fuel cargoes are publicly delayed",
                 "2024-01 the Central Bank Rate framework begins"),
     "why_it_matters": "the policy instrument itself changed in the middle of the shortage, so a "
                       "policy-surprise study cannot cross January 2024 and a shortage study "
                       "must control for the framework change",
     "status": "OPEN"},
    {"name": "UGANDA: inflation targeting lite", "start": "2011-07-01", "end": "2026-12-31",
     "regime": "the Bank of Uganda adopted an inflation-targeting-lite framework in July 2011 "
               "with the Central Bank Rate as the instrument and scheduled MPC announcements -- "
               "the first in sub-Saharan Africa after South Africa and Ghana -- on top of an "
               "open capital account that has been in place since 1997",
     "markers": ("2011-07 the CBR framework begins",
                 "2011-2012 the disinflation that established its credibility"),
     "why_it_matters": "this is the CONTROL REGIME of the pack: a clean float with a scheduled "
                       "policy clock, beside a former peg and a managed float, which is what "
                       "makes Ethiopia's rationing and Tanzania's shortage measurable as "
                       "deviations rather than as stories",
     "status": "OPEN"},
    {"name": "UGANDA: the gold export levy and the re-export collapse", "start": "2021-07-01",
     "end": "2023-06-30",
     "regime": "the Finance Act 2021 imposed an export levy on gold with effect from 2021-07-01; "
               "declared gold exports -- which had been running an order of magnitude above "
               "domestic mine production -- collapsed within a quarter, and the levy was amended "
               "in the following budget rounds before the declared flow recovered",
     "markers": ("2021-07-01 the levy commences",
                 "2021-Q4 declared gold exports collapse in the balance of payments",
                 "2022-2023 the levy is amended and the declared flow recovers"),
     "why_it_matters": "A NATURAL EXPERIMENT WITH A PUBLISHED SERIES ON BOTH SIDES. Any EA-M "
                       "cell must know which side of the commencement date it sits on, and the "
                       "mirror statistics decide whether the flow stopped or re-routed",
     "status": "SETTLED"},
    {"name": "UGANDA AND TANZANIA: the oil era begins", "start": "2022-02-01",
     "end": "2026-12-31",
     "regime": "final investment decision on Tilenga, Kingfisher and the East African Crude Oil "
               "Pipeline on 2022-02-01; construction of a 1,443 km heated line from Hoima to "
               "Tanga, first oil targeted for 2025-2026 and a plateau of roughly 230,000 b/d",
     "markers": ("2022-02-01 FID", "2023-2025 EACOP construction and well completions",
                 "2025-2026 first oil and the start of the ramp"),
     "why_it_matters": "it turns Uganda from a pure oil importer into an exporter and binds its "
                       "external accounts to Tanzania's port; any pre-2022 Ugandan external "
                       "series is from a different economy",
     "status": "OPEN"},
    {"name": "REGIONAL: the EU Deforestation Regulation's compliance clock", "start": "2023-06-29",
     "end": "2026-12-31",
     "regime": "the EUDR entered into force on 2023-06-29 covering coffee and cocoa among other "
               "commodities, with the application date for large operators set for the end of "
               "2024 and then delayed; East African supply is overwhelmingly smallholder, so the "
               "per-plot traceability cost falls hardest exactly here",
     "markers": ("2023-06-29 entry into force", "the announced application date and its delays"),
     "why_it_matters": "the predicted signature is a DESTINATION re-routing rather than a flat "
                       "price move, so a study that looks only at the flat price will find "
                       "nothing and conclude wrongly",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "none of the three currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no ETB, TZS or UGX symbol",
     "consequence": "every domestic mechanism terminates in gold, the softs, the metals, the "
                    "energy legs or the risk carriers; the three currencies are INPUTS, never "
                    "cells, and each is named in TRANSMISSION_TARGETS with its route"},
    {"constraint": "the ECX daily table, the BoT IFEM page and the TPA throughput page overwrite "
                   "in place",
     "measured": "each publishes TODAY and keeps no history",
     "consequence": "their point-in-time history exists only in the archive layer's crawls; a "
                    "cell compiled on an un-archived session is UNMEASURED rather than assumed, "
                    "and the three datasets carry pit_feasible=False for exactly that reason"},
    {"constraint": "the cashew, sesame and cobalt price assessments forbid machine extraction",
     "measured": "Public Ledger and Fastmarkets terms; registered machine_use_allowed=false",
     "consequence": "EA-H is measured on COTTON and on the auction's own published indicative "
                    "price, and EA-G is measured on COPPER rather than on the cobalt payable"},
    {"constraint": "no retail margin or client-flow statistic exists in any of the three",
     "measured": "Ethiopia forbids residents an offshore margin account; CMSA and CMA publish no "
                 "aggregate retail positioning",
     "consequence": "no microstructure claim in this pack may rest on a retail-flow number; the "
                    "retail ecology is read from public communities at FRINGE credibility and is "
                    "declared per jurisdiction in NO_LAWFUL_GROUND"},
    {"constraint": "Ethiopia has no policy-rate history before July 2024",
     "measured": "the National Bank Rate was introduced in July 2024 and there is no earlier "
                 "instrument to measure a surprise against",
     "consequence": "EA-A carries NO central-bank decision dates and says so; the dated events "
                    "it is built on are the float directive, the IMF review Board dates and the "
                    "default milestones, every one of which is citable"},
    {"constraint": "Tanzania Ports Authority publishes throughput irregularly",
     "measured": "monthly in some years, only in the annual report in others",
     "consequence": "a missing month in EA-G is UNMEASURED and the pack refuses to interpolate "
                    "it; a chokepoint claim on an interpolated month is a claim about the "
                    "interpolation"},
    {"constraint": "the Ethiopian Securities Exchange has no machine-readable history",
     "measured": "it opened on 2025-01-10 with a handful of listings",
     "consequence": "the opening is an ERA MARKER in EA-D and never a tape; the institutional "
                    "layer is declared absent for Ethiopian SECURITIES in NO_LAWFUL_GROUND while "
                    "the ECX fills it for commodities"},
)

#: INTERACTION MINERS -- the other country packs this one has a MEASURABLE interaction with. The
#: point is to stop the desk testing each country in isolation: half the controls in this file
#: are another pack's series, and an edge whose control lives in a pack nobody runs is an edge
#: nobody can falsify.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "ke",
     "mechanism": "KENYA IS THE REGIONAL FINANCIAL AND LOGISTICS HUB OF ALL THREE, and this pack "
                  "is deliberately its COMPLEMENT. Mombasa and the Northern Corridor compete "
                  "with Dar es Salaam and the Central Corridor for the same Ugandan, Congolese, "
                  "Rwandan and Burundian cargo; Nairobi's banking groups run the treasury books "
                  "and the USE's counters are cross-listed from the NSE; and `ke` carries the "
                  "two-season rainfall cycle that Ethiopia's BELG and KIREMT are NOT",
     "observable": "Mombasa throughput and Northern Corridor transit times beside Dar es Salaam "
                   "throughput and Central Corridor transit times, month by month; the NSE-USE "
                   "cross-listed counters; the CBK published buy/sell spread beside the BoT's "
                   "bureau-to-IFEM spread",
     "targets": ("XCUUSD", "XNIUSD", "COFROB", "USDZAR", "XBRUSD"),
     "control": "total EAC import volumes, which separate 'the region imported less' from 'the "
                "cargo used the other port'. A transit fall at Dar es Salaam that appears as a "
                "rise at Mombasa is a ROUTING event and carries no supply information at all -- "
                "and NEITHER PACK CAN ESTABLISH THAT ALONE, which is the strongest interaction "
                "in this file"},
    {"with": "eg",
     "mechanism": "the Grand Ethiopian Renaissance Dam sits on the Blue Nile above Egypt. Its "
                  "filling seasons and turbine commissionings are Ethiopian decisions with "
                  "Egyptian consequences, and Egypt's agricultural import demand is the `eg` "
                  "pack's own object",
     "observable": "GERD filling volumes and commissioning dates against Egyptian wheat tender "
                   "volumes, Nile flow reporting and Egyptian water-stress statements",
     "targets": ("WHEAT", "CORN", "XBRUSD"),
     "control": "the same July-September windows in 2015-2019, before any filling began; "
                "Egyptian tender volumes in non-filling years. The Egyptian half of this edge "
                "belongs to `eg` and this pack must not measure it alone"},
    {"with": "za",
     "mechanism": "USDZAR is the liquid African risk carrier that three unquotable currencies "
                  "route through, and South Africa is one of only three sub-Saharan inflation "
                  "targeters -- the other two being Uganda and Ghana",
     "observable": "USDZAR and the South African MPC calendar as the risk-channel leg for every "
                   "Ethiopian default and review milestone, and SARB decision days as the "
                   "separating control for Ugandan CBR days",
     "targets": ("USDZAR", "US500", "XAUUSD"),
     "control": "a carrier is not a substitute: the rand contains South African idiosyncratic "
                "risk that none of these three economies has, and every edge that routes through "
                "it says so on its face"},
    {"with": "gh",
     "mechanism": "GHANA IS THE SIBLING CASE TWICE OVER: it defaulted in the same cycle and "
                  "restructured under the same Common Framework, and its central bank runs its "
                  "OWN domestic gold purchase programme for reserves. Both of this pack's "
                  "headline mechanisms have a Ghanaian placebo",
     "observable": "Ghana's default and restructuring milestone dates against Ethiopia's; the "
                   "Bank of Ghana's gold purchase and gold-for-oil programmes against the Bank "
                   "of Tanzania's",
     "targets": ("XAUUSD", "USDZAR", "US500"),
     "control": "Ghana is the placebo that decides whether EA-F is about TANZANIA or about "
                "African central banks buying gold in general, and whether EA-D is about "
                "Ethiopia or about frontier default as a class"},
    {"with": "ng",
     "mechanism": "Nigeria is the other large African economy that unified a multiple-rate "
                  "exchange regime in the same window -- its own float came in June 2023, "
                  "thirteen months before Ethiopia's -- and it is an oil EXPORTER where all "
                  "three of these are importers until Uganda's first oil",
     "observable": "the Nigerian rate unification of June 2023 against the Ethiopian float of "
                   "2024-07-29: two administered regimes ending in the same cycle, with "
                   "published parallel premia on both sides",
     "targets": ("XBRUSD", "USDZAR", "COFARA"),
     "control": "Nigeria's float is the matched TREATMENT, not a control: if the export-supply "
                "response to a float is real it should appear in both, and if it appears only in "
                "Ethiopia the mechanism is Ethiopian and not monetary"},
    {"with": "cn",
     "mechanism": "China is the marginal buyer of Ethiopian sesame, of Tanzanian and Congolese "
                  "copper and cobalt leaving through Dar es Salaam, and the principal financier "
                  "and contractor of the corridor infrastructure itself",
     "observable": "Chinese refined-copper and concentrate imports against Central Corridor "
                   "transit tonnage; Chinese sesame import volumes against the ECX sesame floor",
     "targets": ("XCUUSD", "XNIUSD", "SOYBEAN"),
     "control": "Chinese demand is the confound in EA-G and must be controlled from the `cn` "
                "pack's own series: a transit fall during a Chinese demand slump is not a "
                "chokepoint"},
)


INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Bank of Uganda monthly balance of payments and the gold export line",
    "Bank of Tanzania Monthly Economic Review: reserves, IFEM turnover and gold purchases",
    "UCDA monthly coffee export report (bags, value, type, destination)",
    "ECX daily trade data by commodity, grade and washing-station origin",
    "Tanzania Ports Authority transit throughput by destination country",
    "Mining Commission monthly production and mineral-market-centre turnover",
    "Mobile-money transaction value and agent float in all three (BoU, BoT, TCRA)",
    "UN Comtrade mirror statistics for gold, coffee and sesame",
)
SERIES: dict[str, str] = {
    "ET_FX": "NBE:indicative_rate", "ET_PREMIUM": "IMF:parallel_premium",
    "ET_CPI": "ESS:cpi", "ET_COFFEE": "ECX:coffee_trades", "ET_SESAME": "ECX:sesame_trades",
    "ET_POWER": "EEP:exports", "ET_GERD": "EEP:gerd_milestones",
    "TZ_FX": "BOT:ifem_rate", "TZ_SPREAD": "BOT:bureau_minus_ifem",
    "TZ_RESERVES": "BOT:gross_reserves", "TZ_GOLD_BUY": "BOT:domestic_gold_purchases",
    "TZ_GOLD_PROD": "MADINI:gold_production", "TZ_TRANSIT": "TPA:transit_by_country",
    "TZ_CASHEW": "CBT:auction_indicative_price", "TZ_POWER": "TANESCO:load_shedding",
    "UG_CBR": "BOU:cbr", "UG_GOLD": "BOU:gold_exports", "UG_COFFEE": "UCDA:exports",
    "UG_CPI": "UBOS:cpi", "UG_OIL": "PAU:ramp_milestones",
    "EA_MOBILE_MONEY": "BOU_BOT:mobile_money_value", "EA_MIRROR": "COMTRADE:hs7108_gap",
}

# --------------------------------------------------------------------------- mechanisms
#: THE DATED GOLD-POLICY EVENTS of both jurisdictions in one table, because they are the same
#: mechanism pointed in opposite directions: an administered change in where physical gold may
#: lawfully go. Rows are (date, jurisdiction, what, status). PRESS_REPORTED means exactly that --
#: a date carried by the trade press or the budget speech, to be confirmed against the Finance
#: Act or gazette number before any cell is promoted on it.
GOLD_POLICY_EVENTS: tuple[tuple[date, str, str, str], ...] = (
    (date(2021, 7, 1), "ug", "the Finance Act 2021 gold export levy commences", "GAZETTED"),
    (date(2022, 7, 1), "ug", "the levy is amended in the following budget round",
     "PRESS_REPORTED"),
    (date(2023, 7, 1), "ug", "the declared re-export flow recovers under the amended levy",
     "PRESS_REPORTED"),
    (date(2023, 7, 1), "tz", "FY2023/24 begins and the Bank of Tanzania's domestic gold "
                             "purchase allocation takes effect", "GAZETTED"),
    (date(2024, 7, 1), "tz", "FY2024/25 renews the purchase allocation and the domestic "
                             "refining requirement", "PRESS_REPORTED"),
    (date(2025, 7, 1), "tz", "the 20% domestic offer obligation on licensed miners, smelters "
                             "and dealers commences with the 2025 Finance Act", "GAZETTED"),
)
#: The mandated domestic OFFER share, as a fraction of production, in force from each date. A
#: cell in EA-F is conditioned on which of these it sits in.
GOLD_OFFER_SHARE: tuple[tuple[date, float], ...] = (
    (date(2023, 7, 1), 0.0),      # the purchase programme exists; no statutory offer yet
    (date(2025, 7, 1), 0.20),     # the 2025 Finance Act sets the domestic offer at 20%
)
#: The Ugandan oil ramp's dated milestones. Rows are (date, what, status).
OIL_RAMP_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2022, 2, 1), "final investment decision on Tilenga, Kingfisher and EACOP", "ANNOUNCED"),
    (date(2023, 1, 1), "EACOP line-pipe delivery and pump-station construction begin",
     "PRESS_REPORTED"),
    (date(2025, 1, 1), "first-oil window opens on the published schedule", "PROJECTED"),
    (date(2026, 1, 1), "ramp toward the plateau of roughly 230,000 b/d", "PROJECTED"),
)
#: The Ethiopian float: one boundary, and it partitions every Ethiopian series in this pack.
BIRR_FLOAT_DATE = date(2024, 7, 29)
#: The Ugandan levy window, for the natural experiment.
UG_LEVY_START = date(2021, 7, 1)
UG_LEVY_AMENDED = date(2022, 7, 1)


def birr_regime(day: date) -> str:
    """Ethiopia's exchange regime on a date: the boundary is 2024-07-29 and nothing else.

    A study that pools across it is pooling an administered rate with a market one, which is the
    single most consequential mislabelling available in this pack.
    """
    return "MARKET_DETERMINED" if day >= BIRR_FLOAT_DATE else "CRAWLING_PEG_RATIONED"


def gold_offer_share(day: date) -> float:
    """The mandated domestic gold OFFER share in force in Tanzania on a date, as a fraction of
    production. Zero before the purchase programme existed at all."""
    share = 0.0
    for start, value in GOLD_OFFER_SHARE:
        if day >= start:
            share = value
    return share


def uganda_gold_levy(day: date) -> str:
    """Uganda's gold export levy state on a date: NONE, IN_FORCE or AMENDED. The natural
    experiment of EA-M is the transition, so a cell must know which side it is on."""
    if day < UG_LEVY_START:
        return "NONE"
    if day < UG_LEVY_AMENDED:
        return "IN_FORCE"
    return "AMENDED"


def oil_ramp_phase(day: date) -> str:
    """Uganda's Lake Albert phase on a date: PRE_FID, CONSTRUCTION, FIRST_OIL_WINDOW or RAMP."""
    phases = ("CONSTRUCTION", "CONSTRUCTION", "FIRST_OIL_WINDOW", "RAMP")
    phase = "PRE_FID"
    for (start, _what, _status), name in zip(OIL_RAMP_EVENTS, phases, strict=True):
        if day >= start:
            phase = name
    return phase


def coffee_crop_year(day: date) -> tuple[int, str]:
    """The Ethiopian coffee crop year a date sits in and its phase.

    The crop year opens in OCTOBER, the export peak runs December to April, and the tail runs to
    September. Returning the opening YEAR rather than the calendar year is the whole point: a
    January session belongs to the crop year that opened the previous October, and a study that
    buckets by calendar year splits every crop in half.
    """
    year = day.year if day.month >= 10 else day.year - 1
    if day.month in (10, 11):
        phase = "OPENING"
    elif day.month in (12, 1, 2, 3, 4):
        phase = "PEAK"
    else:
        phase = "TAIL"
    return year, phase


def rain_season(day: date, jurisdiction: str = "et") -> str:
    """Which rain season a date sits in, PER JURISDICTION -- and they are not the same seasons.

    Ethiopia runs BELG (February-May) and KIREMT (June-September) with the MEHER harvest from
    October; Tanzania's unimodal half runs one wet season from November to April. Kenya's long
    and short rains, which the `ke` pack owns, are a THIRD calendar, and applying them to
    Ethiopia is the most common error in East African crop work.
    """
    code = str(jurisdiction).lower()
    month = day.month
    if code == "et":
        if 2 <= month <= 5:
            return "BELG"
        if 6 <= month <= 9:
            return "KIREMT"
        return "MEHER_HARVEST"
    if code == "tz":
        if month >= 11 or month <= 4:
            return "MSIMU"
        if 3 <= month <= 5:
            return "MASIKA"
        return "DRY"
    return "BIMODAL" if month in (3, 4, 5, 9, 10, 11) else "DRY"


def gerd_filling_window(year: int) -> tuple[date, date]:
    """The KIREMT filling season for a year: 1 July to 30 September. It is the only season with
    enough water to impound, which is why the GERD's decisions are seasonal and dated."""
    return date(year, 7, 1), date(year, 9, 30)


def jurisdiction_of_domain(domain_id: str) -> tuple[str, ...]:
    """Which of the three countries a domain belongs to. A regional domain names all three."""
    return DOMAIN_JURISDICTION.get(str(domain_id), JURISDICTIONS)


#: Which jurisdiction owns each domain, so a test can prove the pack owes each of the three at
#: least three domains of its own rather than three countries' worth of one country's mechanisms.
DOMAIN_JURISDICTION: dict[str, tuple[str, ...]] = {
    "EA-A": ("et",), "EA-B": ("et",), "EA-C": ("et",), "EA-D": ("et",), "EA-E": ("et",),
    "EA-F": ("tz",), "EA-G": ("tz",), "EA-H": ("tz",), "EA-I": ("tz",), "EA-J": ("tz",),
    "EA-K": ("ug", "tz"), "EA-L": ("ug",), "EA-M": ("ug",), "EA-N": ("ug",),
    "EA-O": ("et", "tz", "ug"), "EA-P": ("et", "tz", "ug"), "EA-Q": ("et", "tz", "ug"),
}
#: Which jurisdiction each actor belongs to, by position in ACTORS. Six Ethiopian, six Tanzanian,
#: six Ugandan and two regional -- the floor the brief sets is five per jurisdiction.
ACTOR_JURISDICTION: tuple[str, ...] = (
    "et", "et", "et", "et", "et", "et",
    "tz", "tz", "tz", "tz", "tz", "tz",
    "ug", "ug", "ug", "ug", "ug", "ug",
    "regional", "regional",
)
#: The mechanism family and the horizon each domain mints its cells under.
DOMAIN_MECHANISM: dict[str, str] = {
    "EA-A": "regime_break", "EA-B": "physical_flow", "EA-C": "capacity_ramp",
    "EA-D": "event_reaction", "EA-E": "physical_flow", "EA-F": "official_demand",
    "EA-G": "chokepoint", "EA-H": "administered_price", "EA-I": "capital_control_stress",
    "EA-J": "supply_shock", "EA-K": "capacity_ramp", "EA-L": "release_surprise",
    "EA-M": "administered_price", "EA-N": "policy_surprise", "EA-O": "nominal_demand",
    "EA-P": "holiday_liquidity", "EA-Q": "transfer",
}
DOMAIN_HORIZON: dict[str, str] = {
    "EA-A": "1 to 3 quarters", "EA-B": "0 to 3 sessions", "EA-C": "1 to 2 quarters",
    "EA-D": "0 to 5 sessions", "EA-E": "1 to 2 quarters", "EA-F": "0 to 3 sessions and "
                                                                  "1 to 4 quarters",
    "EA-G": "2 to 8 weeks", "EA-H": "1 to 2 quarters", "EA-I": "1 to 2 quarters",
    "EA-J": "1 to 2 quarters", "EA-K": "1 to 8 quarters", "EA-L": "0 to 10 sessions",
    "EA-M": "1 to 3 quarters", "EA-N": "0 to 5 sessions", "EA-O": "1 to 2 quarters",
    "EA-P": "0 to 2 sessions", "EA-Q": "2 to 8 weeks",
}


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS: every domain crossed with its own instruments and its
    own named conditions, and nothing else.

    This is deliberately NOT a cartesian product of every domain against every executable
    instrument. A cell is only worth a trial if the pack's own data plane can evaluate its
    CONDITION on that SYMBOL, so the cross product is taken inside each domain, where the
    instruments were chosen for the mechanism and the conditions are states the pack's own
    series can resolve. That is the difference between maximising cells and maximising noise:
    a blown-up grid spends the program's shared family-wise error budget on cells nobody can
    fill, and every FX and metals cell on the desk pays for it (two-lane order, 2026-09-06).
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        controls = tuple(dom["controls"])
        for symbol in dom["instruments"]:
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE}:{did}:{symbol}:c{i}",
                    "domain": did,
                    "jurisdictions": DOMAIN_JURISDICTION.get(did, JURISDICTIONS),
                    "symbol": str(symbol),
                    "condition": str(condition),
                    "mechanism_family": DOMAIN_MECHANISM.get(did, "residual"),
                    "horizon": DOMAIN_HORIZON.get(did, "1 to 2 quarters"),
                    "control": controls[i % len(controls)] if controls else "",
                    "why": f"{dom['title']} -- conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()


# --------------------------------------------------------------------------- the department
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _emit(ctx: Any, rows: list[dict[str, Any]]) -> int:
    """Hand rows to the department Ctx when one is given, and count what was taken.

    `mine()` must work with NO context at all -- that is how a test calls it, and how a fresh
    session checks the pack without wiring anything -- so an absent ctx is a normal return and
    never an error.
    """
    if ctx is None:
        return 0
    record = getattr(ctx, "record", None)
    if not callable(record):
        return 0
    taken = 0
    for row in rows:
        try:
            record(row)
        except Exception:                      # a ctx that refuses a row is the ctx's business
            continue
        taken += 1
    return taken


def mine_gold_offer_regime(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EA-F and EA-M: the two administered gold regimes as ONE clock.

    Tanzania's mandated domestic offer and Uganda's export levy are the same mechanism pointed
    in opposite directions -- a dated change in where physical gold may lawfully go -- so they
    are mined together and each is the other's natural placebo.
    """
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "EA-F" if juris == "tz" else "EA-M",
             "jurisdiction": juris, "at": day.isoformat(), "what": what, "status": status,
             "symbols": ["XAUUSD", "XAGUSD"] if juris == "tz" else ["XAUUSD"],
             "offer_share": gold_offer_share(day) if juris == "tz" else None,
             "levy_state": uganda_gold_levy(day) if juris == "ug" else None,
             "family": "official_demand" if juris == "tz" else "administered_price",
             "control": "Ghana's own gold-purchase programme; the importers' mirror statistics"}
            for day, juris, what, status in GOLD_POLICY_EVENTS]
    return {"miner": "ea_gold_offer_regime", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the realised purchase tonnage is not always broken out of the "
                           "reserve line; an absent split is UNMEASURED, never a zero"]}


def mine_birr_float_boundary(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EA-A and EA-B: the 2024-07-29 boundary as a regime break on the export physics."""
    rows: list[dict[str, Any]] = [
            {"kind": "hypothesis", "pack": CODE, "domain": "EA-A", "jurisdiction": "et",
             "at": BIRR_FLOAT_DATE.isoformat(),
             "what": "the NBE directive package ends the administered rate",
             "regime_before": birr_regime(BIRR_FLOAT_DATE - timedelta(days=1)),
             "regime_after": birr_regime(BIRR_FLOAT_DATE),
             "symbols": ["COFARA", "XAUUSD", "USDZAR"], "family": "regime_break",
             "control": "Uganda over the same months, which had no regime change at all"},
            {"kind": "hypothesis", "pack": CODE, "domain": "EA-B", "jurisdiction": "et",
             "at": BIRR_FLOAT_DATE.isoformat(),
             "what": "the birr receipt per dollar of coffee roughly doubles, which is a "
                     "farmgate supply-response claim and not a currency claim",
             "symbols": ["COFARA"], "family": "physical_flow",
             "crop_year": coffee_crop_year(BIRR_FLOAT_DATE),
             "control": "Brazilian and Colombian registrations over the same weeks"}]
    return {"miner": "ea_birr_float_boundary", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the parallel premium itself is reconstructed only in the IMF "
                           "programme documents and exists at review frequency, not weekly"]}


def mine_coffee_export_census(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EA-L and EA-B: the two published coffee censuses -- UCDA monthly and ECX daily."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "EA-L", "jurisdiction": "ug",
             "at": _now(), "what": "the UCDA monthly export print against its own trailing "
                                   "twelve-month seasonal norm", "symbols": ["COFROB", "COFARA"],
             "family": "release_surprise", "horizon": "0 to 10 sessions",
             "control": "the Vietnamese monthly export estimate, which separates 'robusta "
                        "supply' from 'Ugandan supply'"},
            {"kind": "hypothesis", "pack": CODE, "domain": "EA-B", "jurisdiction": "et",
             "at": _now(), "what": "ECX delivered tonnage against its trailing seasonal band, "
                                   "printed before the New York session opens",
             "symbols": ["COFARA"], "family": "physical_flow", "horizon": "0 to 3 sessions",
             "control": "a block-permuted ECX volume series as the null for a daily-lead claim"}]
    return {"miner": "ea_coffee_export_census", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the ECX page overwrites in place, so any session the archive layer "
                           "did not crawl is UNMEASURED and is never interpolated"]}


def mine_corridor_chokepoint(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EA-G and EA-Q: the Central Corridor as a copper chokepoint, WITH the routing control."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "EA-G", "jurisdiction": "tz",
             "at": _now(), "what": "a month in which Central Corridor transit tonnage fell more "
                                   "than its own interquartile range",
             "symbols": ["XCUUSD", "XNIUSD"], "family": "chokepoint", "horizon": "2 to 8 weeks",
             "needs_sibling_pack": "ke",
             "control": "Mombasa throughput over the same months: a fall here that appears as a "
                        "rise there is a ROUTING event and carries no supply information"}]
    return {"miner": "ea_corridor_chokepoint", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["Tanzania Ports Authority publishes throughput irregularly; a missing "
                           "month is UNMEASURED and this miner refuses to interpolate it"]}


def mine_oil_ramp_milestones(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EA-K: the Lake Albert ramp, tested on the trade balance first and the price second."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "EA-K", "jurisdiction": "ug",
             "at": day.isoformat(), "what": what, "status": status,
             "phase": oil_ramp_phase(day), "symbols": ["XBRUSD"], "family": "capacity_ramp",
             "control": "the two countries' own trade balances, where a ramp of this size IS "
                        "large; matched non-event days for the price half"}
            for day, what, status in OIL_RAMP_EVENTS]
    return {"miner": "ea_oil_ramp_milestones", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["two of the four milestones are PROJECTED; a projected date may not "
                           "arrive at all and no cell is promoted on one"]}


def mine_calendar_plane(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EA-P: three national calendars, two Easters and three sighting authorities."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        closures = {code: fn(year) for code, fn in JURISDICTION_HOLIDAY_FN.items()}
        for day in sorted(set().union(*(set(c) for c in closures.values()))):
            closed = tuple(sorted(c for c, tbl in closures.items() if day in tbl))
            if day.weekday() >= 5:
                continue
            rows.append({"kind": "hypothesis", "pack": CODE, "domain": "EA-P",
                         "at": day.isoformat(), "closed": closed,
                         "regional": len(closed) == len(JURISDICTIONS),
                         "symbols": ["XAUUSD", "COFARA", "COFROB"],
                         "family": "holiday_liquidity", "horizon": "0 to 2 sessions",
                         "control": "the matched weekday twenty-six weeks away; days on which "
                                    "only ONE of the three closed"})
    return {"miner": "ea_calendar_plane", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["every Islamic row for 2026 is PROJECTED and three authorities "
                           "announce independently, so a projected date may be a day off"]}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, as HYPOTHESIS discoveries the registry deduplicates."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "transmission", "at": _now(),
             "edge": str(seed["id"]), "what": str(seed["mechanism"]),
             "symbols": list(seed["targets"]), "family": "transfer",
             "horizon": str(seed["horizon"]), "evidence": str(seed["evidence"]),
             "control": str(seed["control"]), "falsifier": str(seed["falsifier"])}
            for seed in TRANSMISSION_EDGES_SEED]
    return {"miner": "ea_transmission_seeds", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows), "unmeasured": []}


MINERS: dict[str, Any] = {
    "mine_gold_offer_regime": mine_gold_offer_regime,
    "mine_birr_float_boundary": mine_birr_float_boundary,
    "mine_coffee_export_census": mine_coffee_export_census,
    "mine_corridor_chokepoint": mine_corridor_chokepoint,
    "mine_oil_ramp_milestones": mine_oil_ramp_milestones,
    "mine_calendar_plane": mine_calendar_plane,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python, no network, no LLM and no heavy import.

    It runs the pack's own seven miners over the pack's own tables, emits through the department
    Ctx when one is given, and returns a plain report when one is not -- which is how a test
    calls it and how a fresh session checks the pack with nothing wired.
    """
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    emitted = 0
    for name, fn in MINERS.items():
        try:
            got = fn(None, ctx)
        except Exception as exc:               # a broken miner is NAMED, never silently skipped
            unmeasured.append(f"{name}: raised {type(exc).__name__}: {exc}")
            continue
        rows.extend(got.get("rows", ()))
        unmeasured.extend(got.get("unmeasured", ()))
        emitted += int(got.get("emitted", 0))
    coverage = source_layer_coverage()
    return {"code": CODE, "jurisdictions": JURISDICTIONS, "at": _now(), "emitted": emitted,
            "rows": rows, "unmeasured": unmeasured,
            "cells_emitted": len(cells()),
            "miners": tuple(MINERS),
            "layers_covered": coverage["n_layers_covered"],
            "sources": coverage["n_sources"],
            "datasets": len(DATASETS), "actors": len(ACTORS), "domains": len(DOMAINS),
            "edges": len(TRANSMISSION_EDGES_SEED), "eras": len(POLICY_ERAS),
            "interactions": tuple(str(r["with"]) for r in INTERACTIONS),
            "no_lawful_ground": tuple(f"{r['jurisdiction']}:{r['layer']}"
                                      for r in NO_LAWFUL_GROUND)}


# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping: the framework fields plus everything the framework has no
    slot for, carried beside them so nothing is silently dropped."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "currencies": CURRENCIES, "jurisdictions": JURISDICTIONS,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "central_banks": CENTRAL_BANKS,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "fiscal_year_ends": FISCAL_YEAR_ENDS,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "no_lawful_ground": NO_LAWFUL_GROUND, "query_territories": QUERY_TERRITORIES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "interactions": INTERACTIONS, "cells": CELLS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "gold_policy_events": GOLD_POLICY_EVENTS,
        "oil_ramp_events": OIL_RAMP_EVENTS, "domain_jurisdiction": DOMAIN_JURISDICTION,
    }


def _source_line(sc: Mapping[str, Any]) -> str:
    return (f"{sc['id']} :: layer={sc['layer']} :: {sc['label']} :: "
            f"roots={'; '.join(sc['roots']) or 'NONE'} :: "
            f"queries={'; '.join(sc['queries']) or 'NONE'} :: "
            f"languages={','.join(sc['languages']) or 'NONE'} :: access={sc['access_label']} :: "
            f"credibility={sc['credibility']} :: predictive={sc['predictive_state']} :: "
            f"machine_use_allowed={sc['machine_use_allowed']} :: licence={sc['licence']}")


def _source_row(sc: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": sc["id"], "layer": sc["layer"], "label": sc["label"], "roots": sc["roots"],
            "languages": sc["languages"], "licence": sc["licence"], "verified": False,
            "query_terms": sc["queries"],
            "notes": (f"access_label={sc['access_label']} | credibility={sc['credibility']} | "
                      f"predictive_state={sc['predictive_state']} | "
                      f"machine_use_allowed={sc['machine_use_allowed']} | {sc['notes']}")}


def _holiday_rule_row() -> dict[str, Any]:
    """The framework's HolidayRule shape: every closed weekday the three calendars produce."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in (FIXED_ET, FIXED_TZ, FIXED_UG) for m, d, _ in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": (5, 6),
            "notes": HOLIDAYS_RULE["authority"]}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion reads
    best: sources as rows AND as tagged lines, positioning and miners as strings, the holiday
    rule as dates, absent layers as a mapping."""
    data = as_dict()
    real = [s for s in SOURCE_CLASSES if not str(s["id"]).startswith("absent_")]
    data.update({
        "code": CODE.lower(),
        "positioning_sources": tuple(str(p["name"]) for p in POSITIONING_SOURCES),
        "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
        "source_classes": tuple(_source_line(s) for s in real),
        "sources": tuple(_source_row(s) for s in real),
        "absent_layers": dict(LAYER_ABSENCES),
        "holidays_rule": _holiday_rule_row(),
    })
    return data


def pack() -> Any:
    """`country_lab.CountryPack` when the framework is present, else the mapping. Imported
    lazily so this department stays importable on a tree where the framework is not."""
    data = lab_kwargs()
    try:
        from libs.research import country_lab
    except ImportError:
        return data
    cls = getattr(country_lab, "CountryPack", None)
    if cls is None:
        return data
    try:
        import dataclasses
        names = {f.name for f in dataclasses.fields(cls)}
    except Exception:
        names = set(_PACK_FIELDS)
    try:
        return cls(**{k: v for k, v in data.items() if k in names})
    except (TypeError, ValueError):
        return data
