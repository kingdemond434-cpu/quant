"""CAUCASUS AND CENTRAL ASIA -- the five states that became the world's routing layer in 2022.

WHAT THIS PACK IS AND WHY IT IS ONE PACK AND NOT FIVE. Armenia, Uzbekistan, Kyrgyzstan,
Tajikistan and Turkmenistan share ONE dominant, dated, published mechanism, and it is a strong
one: THE POST-2022 RE-EXPORT AND REMITTANCE CORRIDOR. After 2022-02-24 these five economies
stopped being small open economies at the edge of the CIS and became the layer through which
Russia buys from the rest of the world and through which Russian wages return to Central Asian
households. The corridor is not an inference. It is visible in four independent places at once:

  1. THEIR OWN CUSTOMS STATISTICS. Armenian and Kyrgyz exports to Russia rose by multiples --
     not percentages -- in 2022 and 2023, in categories neither country produces. A landlocked
     state of 2.8 million people does not begin exporting telephone handsets, semiconductors and
     luxury cars; it re-exports them. The statistics offices publish the tables.
  2. THE MIRROR STATISTICS. The EU's, Turkey's and China's export series to these five states
     rose in the SAME categories in the SAME months. A mirror gap is the oldest trade-statistics
     instrument there is, and it is exactly the right one here: when the origin says it shipped
     and the destination says it did not receive, the difference left in a third country.
  3. THE REMITTANCE SERIES. The Central Bank of Armenia publishes MONTHLY NON-COMMERCIAL MONEY
     TRANSFERS BY SOURCE COUNTRY, free, on a fixed calendar -- the cleanest household-flow
     series in the region and one of the cleanest anywhere. Transfers from Russia multiplied in
     2022. Tajikistan has run the highest remittance-to-GDP ratio ON EARTH in several years;
     Kyrgyzstan is above a quarter of GDP.
  4. THE PRICE. The Armenian dram APPRECIATED about 20% against the US dollar in 2022 -- one of
     the largest single-year appreciations any emerging-market currency has recorded -- while
     Armenian GDP grew at a double-digit rate. That is not a monetary-policy story. It is a flow
     story with a published monthly flow series beside it, which is rare enough to be the
     backbone of a research pack.

Almost nobody trades this. The corridor's transmission is into USDRUB, EURRUB, USDTRY, EURTRY,
USDCNH, XAUUSD, XCUUSD, XALUSD and the softs complex, and every one of those is a broker symbol.
The five local currencies are not.

WHAT EACH STATE CONTRIBUTES THAT THE OTHER FOUR DO NOT.

  * ARMENIA (am) -- THE CLEANEST FLOW SERIES IN THE REGION. Monthly non-commercial transfers by
    source country; the 2022 relocation shock (tens of thousands of people and several hundred
    IT companies arriving inside two quarters); a managed float the CBA intervenes in by
    published auction; copper-molybdenum concentrate out of Zangezur, which is a genuine XCUUSD
    supply observable; a GOLD RE-EXPORT spike that shows up in the customs tables as a jump of
    orders of magnitude in an economy with no gold mine of that size; and the Lachin corridor
    blockade and the 2023 population movement as dated political-risk events. Armenia's calendar
    is CHRISTIAN and its Christmas is 6 January, not 25 December, and it keeps no Nowruz -- the
    one place in this pack where a regional rule genuinely does not apply, and it is declared
    rather than averaged away.

  * UZBEKISTAN (uz) -- A SOVEREIGN WHOSE GOLD SALES ARE VISIBLE. Uzbekistan holds one of the
    largest gold-mining operations on the planet (Navoi's Muruntau open pit) and the Central
    Bank of Uzbekistan BUYS THE DOMESTIC OUTPUT AND SELLS GOLD, reporting monthly. A sovereign
    whose bullion operations are published on a monthly calendar is a rare and real XAUUSD
    supply observable -- the opposite of the usual case, where official gold flows are inferred
    from quarterly estimates. Uzbekistan also carries the single hardest regime boundary in this
    pack: on 2017-09-05 the som was floated and lost roughly half its value against the dollar
    IN ONE DAY. Any study that pools across that date is measuring two countries. Plus cotton
    after the end of the state procurement order, and a gas position that reversed from export
    to import.

  * KYRGYZSTAN (kg) -- KUMTOR AND THE GOLD CONDUIT. Kumtor, the country's one large mine, was
    taken under state external management in 2021 -- a dated ownership break in a producing gold
    asset. Separately and much larger, Kyrgyz customs recorded extraordinary GOLD RE-EXPORT
    volumes in 2022-2023 that bear no relation to domestic production, and they are published.
    The National Bank runs FX auctions and publishes the result the SAME DAY, which makes its
    intervention a dated, sized, public event rather than a reserve inference.

  * TAJIKISTAN (tj) -- ALUMINIUM ON STRANDED HYDROPOWER, AND THE WORLD'S HIGHEST REMITTANCE
    SHARE. TALCO smelts aluminium with power that cannot be exported any other way, which makes
    Tajik output a function of the Vakhsh cascade and of the Rogun filling schedule rather than
    of the LME price. The National Bank runs a managed rate whose spread to the licensed-bureau
    rate is the country's stress observable.

  * TURKMENISTAN (tm) -- THE MIRROR-STATISTICS CASE, AND THE PACK'S HONEST REFUSAL. Fourth
    largest proven gas reserves on earth and effectively ONE customer. Turkmen official
    statistics are not published in any form a desk can use: there is no machine-readable
    national accounts release, no monthly trade table, no auditable reserve series, and the
    official manat rate has been administratively fixed while a parallel rate trades at a large
    multiple. THE VOLUMES ARE STILL KNOWABLE, because CHINESE CUSTOMS PUBLISHES THEM: the
    Central Asia-China pipeline's throughput appears in China's own monthly gas-import-by-origin
    tables. Where a layer genuinely has no lawful Turkmen ground, this pack declares it ABSENT
    with the reason AND names the mirror source that substitutes (`NO_LAWFUL_GROUND`). That
    measured refusal plus its substitute is worth more than a padded row, and it is the model
    for every opaque state the desk will meet later.

WHAT IS EXECUTABLE AND WHAT IS NOT. None of AMD, UZS, KGS, TJS or TMT is quoted by this broker,
and neither is the Armenia Securities Exchange, the Uzbek Republican Commodity Exchange, the
Kumtor production series or the Turkmen border gas price. Every one is named in
`TRANSMISSION_TARGETS` with the broker symbols its economics reaches, so an absent instrument
mints a transmission hypothesis and never a cell that can never be filled (L1.49).

THE TWO-LANE ORDER (2026-09-06). Zangezur Copper-Molybdenum, Navoi Mining and Metallurgical,
Kyrgyzaltyn, TALCO and Turkmengaz are the loudest names in this region and NOT ONE of them is
listed anywhere a desk could trade it. They appear here as ACTORS only, and the instruments
their behaviour reaches are metals, energy, softs and the rouble/lira/renminbi legs.

THE COMPLEMENT RULE. Four sibling packs already answer for this command -- `ru` (the demand side
of the corridor and the desk's hardest access problem), `kz` (the largest single Central Asian
pipe and a transmission-only tenge), `az` (the pegged oil half of the Caucasus) and `ge` (the
remittance observatory next door). This pack does not restate any of them: it is their
COMPLEMENT, and `INTERACTIONS` names all four by code with the observable that joins them.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "CAUCASUS_CENTRAL_ASIA"
NAME = "Caucasus and Central Asia"
REGION_COMMAND = "russia_cis"       # the framework's command; the forest is russia_cis
REGION_DESK = "RUSSIA_CIS"
FOREST = "russia_cis"
CURRENCY = "UZS"                    # the pack's lead currency; see CURRENCIES for all five
FISCAL_YEAR_END = "12-31"           # all five run calendar-year state budgets
NATIVE_LANGUAGES: tuple[str, ...] = ("hy", "uz", "ky", "tg", "tk", "ru", "en")
COT_CURRENCY = ""                   # no CFTC contract exists for any of the five currencies
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"

#: THE PARITY FENCE COUNTS THIS TUPLE (`scripts/check_regional_parity.py::jurisdictions_of`).
#: Five ISO-2 codes, lowercase, and the pack owes each of them actors, domains and sources of
#: its own -- a multi-jurisdiction pack that credits itself with a country it did not write is
#: worse than a missing pack, because the fence then reads the gap as closed.
JURISDICTIONS: tuple[str, ...] = ("am", "uz", "kg", "tj", "tm")

#: THREE OF THE FIVE ARE ON THE DESK'S OWN ROSTER (`libs/research/forests.py`, russia_cis:
#: RU UA KZ BY AZ GE AM UZ KG) and TWO ARE NOT. Declared as two tables rather than one, because
#: "answers a roster country" and "answers a country nobody has claimed" are different claims
#: and the fence measures only the first. Tajikistan and Turkmenistan are written here because
#: the corridor does not stop at the roster's edge: Tajik remittances and Turkmen gas are legs
#: of the same mechanism, and a pack that covered three of five would leave the mechanism's two
#: largest physical legs unmined. Adding them to the forest roster is the forest owner's call,
#: not this pack's -- so the pack answers them and says so.
ROSTER_JURISDICTIONS: tuple[str, ...] = ("am", "uz", "kg")
BEYOND_ROSTER: dict[str, str] = {
    "tj": "Tajikistan is not on any forest's country list as of 2026-09-23; it is written here "
          "because it carries the highest remittance-to-GDP share on earth and the region's "
          "only primary aluminium smelter, both of which are legs of the corridor mechanism",
    "tm": "Turkmenistan is not on any forest's country list as of 2026-09-23; it is written "
          "here because the Central Asia-China pipeline is the single largest physical flow in "
          "the region and is READABLE ONLY IN CHINESE MIRROR STATISTICS, which is the pack's "
          "clearest worked example of lawful ground substituting for an absent one",
}

#: All five local currencies, with the regime each one actually runs. NOT ONE is a broker
#: symbol: every row here is a `TRANSMISSION_TARGETS` entry as well, and the regime is what
#: decides whether the currency's PRICE carries information (a float) or whether only its
#: DEFENCE does (a fix, where the information is in the parallel spread and the reserve cost).
CURRENCIES: dict[str, dict[str, str]] = {
    "am": {"iso": "AMD", "name": "Armenian dram",
           "regime": "managed float with a formal inflation target; the CBA intervenes by "
                     "published auction and does not defend a level",
           "state": "appreciated about 20% against the USD in 2022 on the transfer and "
                    "relocation inflow -- a FLOW appreciation, not a rate-differential one",
           "broker": "ABSENT from data/universe/universe.json"},
    "uz": {"iso": "UZS", "name": "Uzbek som",
           "regime": "managed float since the 2017-09-05 liberalisation; the CBU runs an "
                     "inflation-targeting framework and sells FX (and gold proceeds) into the "
                     "domestic market",
           "state": "a controlled downward crawl since 2017 with the gold sale as the largest "
                    "single supply of dollars to the market",
           "broker": "ABSENT from data/universe/universe.json"},
    "kg": {"iso": "KGS", "name": "Kyrgyz som",
           "regime": "de jure managed float, de facto a narrow quasi-peg held by NBKR FX "
                     "auctions whose results are published the same day",
           "state": "held in a very narrow band against the USD since 2022 while the corridor "
                    "flows ran through the banking system",
           "broker": "ABSENT from data/universe/universe.json"},
    "tj": {"iso": "TJS", "name": "Tajik somoni",
           "regime": "heavily managed rate set with NBT administrative guidance; licensed "
                     "bureaux quote a second price",
           "state": "the spread between the official rate and the licensed-bureau rate is the "
                    "country's FX-stress observable, and it widens with the remittance cycle",
           "broker": "ABSENT from data/universe/universe.json"},
    "tm": {"iso": "TMT", "name": "Turkmen manat",
           "regime": "ADMINISTRATIVELY FIXED at 3.50 to the US dollar since 2015-01-01; there "
                     "is no market in it at that price",
           "state": "a parallel rate has traded at a large multiple of the official one for "
                    "years; the official rate carries no information and the SPREAD carries all "
                    "of it",
           "broker": "ABSENT from data/universe/universe.json"},
}

MISSION = ("mine the five states of the Caucasus and Central Asia as ONE mechanism -- the "
           "post-2022 re-export and remittance corridor -- through the four places it is "
           "published: their own customs tables, the EU/Turkey/China mirror statistics, the "
           "monthly transfer series Armenia and Kyrgyzstan publish by source country, and the "
           "prices of the metals, gas and cotton these economies physically ship; plus the "
           "sovereign gold supply of Uzbekistan and Kyrgyzstan, the Turkmen gas volumes that "
           "exist only in Chinese customs data, and the Nowruz/Eid calendar block that closes "
           "four of the five at once")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDRUB", "EURRUB",          # the corridor's demand side and its settlement leg
    "USDTRY", "EURTRY",          # Turkey as the corridor's other end and a mirror-statistics twin
    "USDCNH",                    # China as the gas monopsonist and the re-export origin
    "XAUUSD",                    # Muruntau, Kumtor, the CBU's sales and the gold re-export spike
    "XCUUSD",                    # Zangezur concentrate out of the Caucasus
    "XALUSD",                    # TALCO on stranded hydropower
    "XNGUSD", "XBRUSD",          # the Central Asia-China pipeline and the region's energy bill
    "COTTON", "WHEAT",           # Uzbek cotton after the state order; the region's grain import
    "USDINR",                    # the third EM re-export twin and the INSTC leg
)

#: EVERY LOCAL INSTRUMENT THIS PACK IS ABOUT, NAMED ABSENT WITH WHAT CARRIES IT INSTEAD. An
#: absent instrument is a transmission hypothesis; it is never a cell that can never be filled.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "AMD (Armenian dram) -- USD/AMD and EUR/AMD",
     "venue": "the interbank market and the CBA's published FX auctions",
     "jurisdiction": "am",
     "why": "the 2022 appreciation is the pack's single largest identified flow event and the "
            "dram is not quoted here; the transfer series is the input and the rouble, lira and "
            "gold legs are the readable output",
     "proxies": ("USDRUB", "EURRUB", "USDTRY", "XAUUSD")},
    {"name": "UZS (Uzbek som) -- USD/UZS",
     "venue": "the CBU fixing and the domestic interbank market",
     "jurisdiction": "uz",
     "why": "the som's controlled crawl is funded by the central bank's own GOLD SALES, so the "
            "dollar leg of that operation is read on XAUUSD and not on a som quote",
     "proxies": ("XAUUSD", "USDRUB", "USDCNH")},
    {"name": "KGS (Kyrgyz som) -- USD/KGS",
     "venue": "the NBKR FX auction and the commercial-bank market",
     "jurisdiction": "kg",
     "why": "a quasi-peg carries no information in its price; the information is in the auction "
            "SIZE and in the customs tables the auction is financing",
     "proxies": ("USDRUB", "XAUUSD", "USDCNH")},
    {"name": "TJS (Tajik somoni) -- the official rate and the licensed-bureau rate",
     "venue": "the NBT official rate and the licensed exchange bureaux",
     "jurisdiction": "tj",
     "why": "TWO prices, and the SPREAD is the observable; the somoni itself is absent and the "
            "aluminium and rouble legs carry the economics",
     "proxies": ("XALUSD", "USDRUB")},
    {"name": "TMT (Turkmen manat) -- the fixed official rate and the parallel rate",
     "venue": "the Central Bank of Turkmenistan (fixed) and the informal market",
     "jurisdiction": "tm",
     "why": "a rate fixed at 3.50 since 2015-01-01 is a constant, and a constant has no "
            "information; the parallel multiple is the state variable and the gas volumes are "
            "read from Chinese customs",
     "proxies": ("XNGUSD", "USDCNH", "XBRUSD")},
    {"name": "The Armenia Securities Exchange (AMX) equity and bond boards",
     "venue": "AMX, Yerevan", "jurisdiction": "am",
     "why": "no CFD is quoted on any Armenian index and the free float is negligible; the "
            "corridor's equity expression is elsewhere",
     "proxies": ("USDRUB", "USDTRY")},
    {"name": "The Uzbek Republican Commodity Exchange (UzEX) cotton and commodity auctions",
     "venue": "UzEX, Tashkent", "jurisdiction": "uz",
     "why": "a real, dated, public auction for a physical commodity the broker quotes as a "
            "global price; the auction is the observable and COTTON is the instrument",
     "proxies": ("COTTON", "WHEAT")},
    {"name": "Kumtor mine production and the Kyrgyzaltyn refining series",
     "venue": "Kyrgyzaltyn and the state's periodic disclosure", "jurisdiction": "kg",
     "why": "a producing gold asset whose ownership broke on a date; production is an XAUUSD "
            "supply observable and the company is not listed anywhere the desk trades",
     "proxies": ("XAUUSD",)},
    {"name": "TALCO primary aluminium output and the Vakhsh cascade power balance",
     "venue": "TALCO and Barqi Tojik", "jurisdiction": "tj",
     "why": "output is a function of stranded hydropower and of the Rogun filling schedule, "
            "which makes it a supply observable independent of the exchange price",
     "proxies": ("XALUSD",)},
    {"name": "The Central Asia-China pipeline border gas price and throughput",
     "venue": "Turkmengaz and CNPC, read through China's customs releases",
     "jurisdiction": "tm",
     "why": "THE MIRROR CASE: Turkmenistan publishes nothing usable and China publishes the "
            "volumes and values by origin every month; the price is derived, not quoted",
     "proxies": ("XNGUSD", "USDCNH")},
    {"name": "The Zangezur copper-molybdenum concentrate export programme",
     "venue": "ZCMC, Kajaran", "jurisdiction": "am",
     "why": "concentrate, not refined metal, so the transmission is into the treatment-charge "
            "and concentrate-availability side of XCUUSD rather than into the cathode price",
     "proxies": ("XCUUSD",)},
    {"name": "The five central banks' policy rates and reserve series",
     "venue": "CBA, CBU, NBKR, NBT, CBT", "jurisdiction": "regional",
     "why": "none is a tradeable rate anywhere the desk can reach; they are conditioning "
            "variables on the corridor's flow, never instruments",
     "proxies": ("USDRUB", "XAUUSD")},
)

# --------------------------------------------------------------------------- the central banks
#: THE FRAMEWORK HAS ONE CENTRAL-BANK SLOT AND THIS PACK HAS FIVE BANKS. The slot carries the
#: CBU, because UZS is the pack's declared currency and because the CBU is the one bank in the
#: five whose operations are themselves a tradeable observable (it sells gold). The other four
#: are in `CENTRAL_BANKS` with the same field names, and every miner that needs one reads THAT
#: table by jurisdiction rather than pretending the CBU speaks for Yerevan or Ashgabat.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of the Republic of Uzbekistan -- the Board (Markaziy bank)",
    "short": "CBU",
    "jurisdiction": "uz",
    "framework": "inflation_targeter",
    "committee": "the Board of the Central Bank, chaired by the Chairman; the decision is "
                 "published with a press release and a quarterly monetary policy review",
    "policy_instrument": "the main (refinancing) rate, with an interest-rate corridor of "
                         "overnight deposit and overnight loan facilities around it",
    "mandate": "price stability under the 2019 law on the Central Bank, with a stated medium-"
               "term inflation target adopted as part of the transition to inflation targeting "
               "announced in 2019 and operational from 2020",
    "decision_rule": "scheduled Board meetings published in advance on cbu.uz, roughly seven to "
                     "eight a year, with an announcement in the afternoon Tashkent time",
    "decision_calendar_rule": "the CBU publishes the next calendar year's meeting dates on "
                              "cbu.uz in the fourth quarter; the announcement minute must be "
                              "stamped from the press release and never assumed",
    "decision_dates": (),
    "dates_status": "UNMEASURED ON THIS BOX (L1.28a). The CBU publishes its Board calendar and "
                    "this pack refuses to type dates it has not fetched: a wrong decision date "
                    "does not produce a weak study, it produces a confidently wrong one. The "
                    "collector fills this from cbu.uz monetary-policy; until it does, every "
                    "CCA-UZ-A event arm reports UNMEASURED by name",
    "decision_time_utc": "11:00",
    "announce_local": "afternoon Asia/Tashkent (UTC+5 all year, no daylight saving)",
    "dst_rule": "NONE. Uzbekistan is UTC+5 year round; Armenia is UTC+4, Kyrgyzstan UTC+6, "
                "Tajikistan UTC+5 and Turkmenistan UTC+5. NOT ONE of the five observes daylight "
                "saving, so every UTC window in this pack is stable across the year -- the "
                "opposite of the European packs, and the reason a shared session grid is safe",
    "minutes_lag_days": 0,
    "publication_classes": ("board_decision_press_release", "monetary_policy_review",
                            "monthly_monetary_statistics", "international_reserves_monthly",
                            "gold_operations_monthly", "balance_of_payments_quarterly"),
    "policy_rate_series": "CBU:main_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the domestic deposit-auction rate and the government bond cut-off "
                       "between meetings; there is no published survey consensus",
    "consensus_proxy_trap": "the deposit-auction rate is pinned to the corridor by construction, "
                            "so a move there is a liquidity fact before it is an expectation",
    "reserves_clock": "international reserves are published monthly and the GOLD SHARE of them "
                      "is the series that matters here: Uzbekistan's reserves are majority gold "
                      "by value, so a reserve move is a gold-price move plus an operation, and "
                      "the two must be separated before either is read",
    "programme": "no IMF adjustment programme; Article IV consultations only",
    "off_cycle": ("2020 pandemic-era easing outside the published calendar",),
    "root": "https://cbu.uz",
}

#: THE OTHER FOUR BANKS, in the same shape. Each carries its OWN announcement clock, its own
#: instrument and its own reason for existing in this pack.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "am": {"name": "Central Bank of Armenia -- the Board", "short": "CBA", "jurisdiction": "am",
           "framework": "inflation_targeter",
           "policy_instrument": "the refinancing rate inside a corridor; FX intervention by "
                                "auction on the Yerevan exchange platform",
           "decision_rule": "eight scheduled Board meetings a year, announced the same day, on "
                            "a calendar published in advance at cba.am",
           "decision_time_utc": "10:30", "tz": "Asia/Yerevan (UTC+4, no DST)",
           "decision_dates": (),
           "dates_status": "UNMEASURED ON THIS BOX: cba.am publishes the eight-meeting calendar "
                           "and the collector fills it; not typed here",
           "why_it_matters": "the CBA publishes MONTHLY NON-COMMERCIAL MONEY TRANSFERS BY "
                             "SOURCE COUNTRY -- the cleanest household-flow series in the "
                             "region, and the input to the pack's central mechanism",
           "root": "https://www.cba.am"},
    "kg": {"name": "National Bank of the Kyrgyz Republic", "short": "NBKR", "jurisdiction": "kg",
           "framework": "managed_float",
           "policy_instrument": "the policy rate, and FX AUCTIONS whose volume and rate are "
                                "published the same day",
           "decision_rule": "scheduled Board meetings on the policy rate; the FX auction is an "
                            "operational event and is announced on the day it happens",
           "decision_time_utc": "06:00", "tz": "Asia/Bishkek (UTC+6, no DST)",
           "decision_dates": (),
           "dates_status": "UNMEASURED ON THIS BOX: nbkr.kg publishes both the rate calendar "
                           "and the same-day auction results; the collector fills them",
           "why_it_matters": "SAME-DAY PUBLISHED INTERVENTION. A central bank whose defence of "
                             "a quasi-peg is a dated, sized, public sale is a research object "
                             "even though the rate it defends barely moves",
           "root": "https://www.nbkr.kg"},
    "tj": {"name": "National Bank of Tajikistan", "short": "NBT", "jurisdiction": "tj",
           "framework": "managed_float",
           "policy_instrument": "the refinancing rate and administrative guidance to the "
                                "licensed bureaux on the rate they may quote",
           "decision_rule": "periodic Board decisions announced on nbt.tj; the official rate is "
                            "published every business day",
           "decision_time_utc": "05:00", "tz": "Asia/Dushanbe (UTC+5, no DST)",
           "decision_dates": (),
           "dates_status": "UNMEASURED ON THIS BOX; nbt.tj carries the decisions",
           "why_it_matters": "TWO PRICES. The official rate and the licensed-bureau rate diverge "
                             "under stress, and the spread is the observable -- the rate itself "
                             "is administered and carries little",
           "root": "https://nbt.tj"},
    "tm": {"name": "Central Bank of Turkmenistan", "short": "CBT", "jurisdiction": "tm",
           "framework": "peg",
           "policy_instrument": "an administratively FIXED rate of 3.50 manat to the US dollar, "
                                "in force since 2015-01-01, plus exchange controls on who may "
                                "convert and how much",
           "decision_rule": "none that is published; there is no announced meeting calendar and "
                            "no minutes",
           "decision_time_utc": "", "tz": "Asia/Ashgabat (UTC+5, no DST)",
           "decision_dates": (),
           "dates_status": "NO LAWFUL GROUND: the CBT publishes no decision calendar, no "
                           "minutes and no auditable reserve series. This is a MEASURED "
                           "ABSENCE, not an unread page -- see NO_LAWFUL_GROUND",
           "why_it_matters": "the fixed rate is a constant and constants carry no information; "
                             "everything Turkmen that a desk can measure is measured somewhere "
                             "else, and this pack names where",
           "root": "https://www.cbt.tm"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CBA official exchange rate (Armenia, published each business day)",
     "local": "published in the afternoon Asia/Yerevan (UTC+4, no DST)",
     "time_utc": "12:00", "dst_rule": "none -- Armenia has kept UTC+4 with no DST since 2012",
     "instruments": ("USDRUB", "USDTRY"), "window_minutes": 30, "jurisdiction": "am",
     "why": "the dram fixing the corridor's transfer flows are converted at; AMD is absent, so "
            "the fixing is an INPUT and the rouble and lira legs are the readable output"},
    {"name": "CBU official rate and the monthly gold-operations release (Uzbekistan)",
     "local": "the rate each business day; the gold and reserve tables monthly",
     "time_utc": "06:00", "dst_rule": "none -- Uzbekistan is UTC+5 year round",
     "instruments": ("XAUUSD",), "window_minutes": 60, "jurisdiction": "uz",
     "why": "the ONE place in this pack where a sovereign's bullion operation is on a published "
            "monthly clock; the release is the event and XAUUSD is the instrument"},
    {"name": "NBKR FX auction (Kyrgyzstan) -- announced, sized and published the same day",
     "local": "intraday Asia/Bishkek (UTC+6, no DST)",
     "time_utc": "05:00", "dst_rule": "none", "instruments": ("USDRUB", "XAUUSD"),
     "window_minutes": 60, "jurisdiction": "kg",
     "why": "a dated, sized, public intervention; its size is the corridor's dollar demand made "
            "visible, and it is published before the customs tables catch up"},
    {"name": "NBT official rate and the licensed-bureau quote (Tajikistan)",
     "local": "the official rate each business day Asia/Dushanbe (UTC+5, no DST)",
     "time_utc": "05:00", "dst_rule": "none", "instruments": ("XALUSD", "USDRUB"),
     "window_minutes": 60, "jurisdiction": "tj",
     "why": "two prices for one currency; the SPREAD is the stress state, and the aluminium and "
            "rouble legs carry it into something tradeable"},
    {"name": "LBMA gold price PM auction -- the dollar leg of every regional gold flow",
     "local": "15:00 Europe/London", "time_utc": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("XAUUSD",), "window_minutes": 15, "jurisdiction": "regional",
     "why": "Muruntau's output, Kumtor's output, the CBU's sales and the Armenian and Kyrgyz "
            "gold re-export lines are all valued against this print"},
    {"name": "The Moscow close and the rouble reference the corridor settles against",
     "local": "late afternoon Europe/Moscow", "time_utc": "13:30",
     "dst_rule": "none -- Russia abolished daylight saving in 2014",
     "instruments": ("USDRUB", "EURRUB"), "window_minutes": 60, "jurisdiction": "regional",
     "why": "corridor invoices are increasingly rouble-denominated, so the rouble reference is "
            "the price at which the re-export margin is struck"},
    {"name": "China customs monthly release -- the Turkmen gas mirror",
     "local": "published by the General Administration of Customs, monthly",
     "time_utc": "03:00", "dst_rule": "none -- China is UTC+8 year round",
     "instruments": ("XNGUSD", "USDCNH"), "window_minutes": 120, "jurisdiction": "tm",
     "why": "THE MIRROR FIXING: the only lawful, dated, quantified read on Turkmen gas exports "
            "anywhere, and it is a foreign government's release rather than a Turkmen one"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Armenian monthly transfer release (CBA, prior month)", "kind": "day_of_month",
     "days": (28, 29, 30), "roll": "next", "window_utc": ("08:00", "14:00"),
     "instruments": ("USDRUB", "USDTRY"), "jurisdiction": "am",
     "why": "the non-commercial transfers by source country land near the end of the following "
            "month; the release is the corridor's cleanest scheduled information event"},
    {"name": "Remittance month-end payout cycle across the four labour exporters",
     "kind": "month_end", "roll": "previous", "window_utc": ("06:00", "14:00"),
     "instruments": ("USDRUB", "XAUUSD"), "jurisdiction": "regional",
     "why": "Russian wages are paid around the month end, so the transfer rail carries its "
            "largest volume in the last and first business days -- a scheduled FX demand"},
    {"name": "CBU monthly reserves and gold-operations publication", "kind": "day_of_month",
     "days": (5, 6, 7), "roll": "next", "window_utc": ("05:00", "11:00"),
     "instruments": ("XAUUSD",), "jurisdiction": "uz",
     "why": "the gold share of reserves and the month's operation appear together; a reserve "
            "move must be split into a price move and an operation before it is read"},
    {"name": "China customs monthly detailed trade tables (gas by origin)",
     "kind": "day_of_month", "days": (18, 19, 20), "roll": "next",
     "window_utc": ("02:00", "08:00"), "instruments": ("XNGUSD", "USDCNH"),
     "jurisdiction": "tm",
     "why": "the detailed by-origin tables follow the headline release by about a fortnight; "
            "the Turkmen volume is only in the detailed one"},
    {"name": "Quarter-end concentrate and aluminium shipment programmes", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("06:00", "14:00"), "instruments": ("XCUUSD", "XALUSD"),
     "jurisdiction": "regional",
     "why": "Zangezur concentrate and TALCO metal move on quarterly contract cycles, so the "
            "physical flow clusters at the quarter boundary"},
    {"name": "Fiscal year end (31 December) and the five state budgets",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("06:00", "14:00"),
     "instruments": ("USDRUB", "XAUUSD"), "jurisdiction": "regional",
     "why": "all five run calendar-year budgets; the Uzbek gold sale, the Tajik power tariff "
            "and the Kyrgyz customs target are all dated to it"},
    {"name": "The cotton marketing year and the UzEX auction season", "kind": "day_of_month",
     "days": (1, 15), "roll": "next", "window_utc": ("05:00", "11:00"),
     "instruments": ("COTTON",), "jurisdiction": "uz",
     "why": "the Uzbek crop is picked September to November and auctioned through the winter; "
            "the auction dates are the physical supply reaching the market"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Armenia Securities Exchange (AMX, Yerevan) and the CBA FX auction platform",
     "index_symbols": (), "open_local": "10:00", "close_local": "16:00",
     "open_utc": "06:00", "close_utc": "12:00",
     "dst_rule": "none -- Asia/Yerevan is UTC+4 all year",
     "auction": "the FX auction on the exchange platform is where the CBA's intervention is "
                "executed and where the day's reference is formed",
     "expiry_rule": "no listed derivatives of any kind",
     "holidays": "the Armenian national calendar (Christian; 6 January is Christmas)",
     "notes": "NO CFD IS QUOTED on anything listed here; the exchange enters as a transmission "
              "target only. The FX auction, not the equity board, is the object worth mining"},
    {"name": "Uzbek Republican Commodity Exchange (UzEX) and the Tashkent currency exchange",
     "index_symbols": (), "open_local": "09:00", "close_local": "17:00",
     "open_utc": "04:00", "close_utc": "12:00",
     "dst_rule": "none -- Asia/Tashkent is UTC+5 all year",
     "auction": "UzEX runs dated public auctions for cotton fibre, metals, petroleum products "
                "and state property; results are published per lot",
     "expiry_rule": "spot and forward physical lots; no financial futures",
     "holidays": "the Uzbek national calendar including Navruz and the two Hayits",
     "notes": "THE AUCTION IS THE OBSERVABLE and COTTON is the instrument; UzEX itself is not "
              "quoted by the broker and never will be"},
    {"name": "The Kyrgyz interbank market and the NBKR auction platform",
     "index_symbols": (), "open_local": "09:00", "close_local": "17:00",
     "open_utc": "03:00", "close_utc": "11:00",
     "dst_rule": "none -- Asia/Bishkek is UTC+6 all year",
     "auction": "the NBKR announces its FX auctions and publishes the volume and rate the same "
                "day; there is no continuous public tape",
     "expiry_rule": "none",
     "holidays": "the Kyrgyz national calendar including Nooruz, Orozo Ait and Kurman Ait",
     "notes": "the only same-day published intervention series in this pack"},
    {"name": "Turkmenistan: the State Commodity and Raw Materials Exchange (Ashgabat)",
     "index_symbols": (), "open_local": "unpublished", "close_local": "unpublished",
     "open_utc": "05:00", "close_utc": "11:00",
     "dst_rule": "none -- Asia/Ashgabat is UTC+5 all year",
     "auction": "the exchange reports weekly deal summaries in the state press; there is no "
                "tape, no order book and no machine-readable archive",
     "expiry_rule": "none",
     "holidays": "a calendar set by presidential decree and revised without notice",
     "notes": "DECLARED THIN ON PURPOSE. The exchange exists and reports, but what it reports "
              "is a press summary, not data; the Chinese customs mirror is the substitute and "
              "NO_LAWFUL_GROUND says so by name"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "cca_central_asia_morning", "start_utc": "03:00", "end_utc": "07:00",
     "notes": "the Tashkent, Bishkek and Dushanbe business morning; the region's own fixings, "
              "auctions and releases land here, hours before London opens"},
    {"name": "cca_yerevan_session", "start_utc": "06:00", "end_utc": "12:00",
     "notes": "the Armenian business day (UTC+4, no DST); the CBA rate and the AMX board"},
    {"name": "cca_moscow_overlap", "start_utc": "06:00", "end_utc": "14:00",
     "notes": "the window in which the corridor's two ends are open at once -- Central Asian "
              "afternoon and Moscow morning; where a rouble-settled re-export is priced"},
    {"name": "cca_china_customs_release", "start_utc": "02:00", "end_utc": "05:00",
     "notes": "the Beijing morning in which China's customs releases land; the ONLY window in "
              "which a Turkmen gas number becomes public anywhere"},
    {"name": "cca_london_gold_pm", "start_utc": "14:45", "end_utc": "15:30",
     "notes": "the LBMA PM auction every regional gold flow is valued against"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "CBA monthly non-commercial money transfers by source country (Armenia)",
     "cadence": "monthly", "time_utc": "12:00", "source": "Central Bank of Armenia",
     "actual_series": "CBA:transfers_by_country", "expected_series": "UNMEASURED",
     "notes": "THE PACK'S CENTRAL SERIES. Monthly, free, by origin, with a Russia line that "
              "multiplied in 2022 -- a household flow published by a central bank"},
    {"name": "Armstat monthly external trade by partner and commodity chapter (Armenia)",
     "cadence": "monthly", "time_utc": "10:00", "source": "Statistical Committee of Armenia",
     "actual_series": "ARMSTAT:trade_by_partner", "expected_series": "n/a",
     "notes": "where the re-export and the gold line are visible; the commodity chapter split "
              "is what separates a re-export from a real export"},
    {"name": "CBU monthly international reserves and gold operations (Uzbekistan)",
     "cadence": "monthly", "time_utc": "06:00", "source": "Central Bank of Uzbekistan",
     "actual_series": "CBU:reserves_gold", "expected_series": "n/a",
     "notes": "the sovereign gold observable; the operation must be separated from the price"},
    {"name": "Stat.uz monthly trade, industrial output and cotton statistics (Uzbekistan)",
     "cadence": "monthly", "time_utc": "06:00", "source": "Statistics Agency of Uzbekistan",
     "actual_series": "STATUZ:trade", "expected_series": "n/a",
     "notes": "the cotton and gold export lines; Uzbekistan has reported gold exports inside a "
              "residual category in some vintages, which is a point-in-time trap and is flagged"},
    {"name": "NBKR FX auction result and weekly reserve statement (Kyrgyzstan)",
     "cadence": "daily", "time_utc": "05:00", "source": "National Bank of the Kyrgyz Republic",
     "actual_series": "NBKR:fx_auction", "expected_series": "n/a",
     "notes": "same-day publication; the size is the corridor's dollar demand made visible"},
    {"name": "Stat.kg monthly foreign trade including the gold re-export line (Kyrgyzstan)",
     "cadence": "monthly", "time_utc": "05:00", "source": "National Statistical Committee",
     "actual_series": "STATKG:trade", "expected_series": "n/a",
     "notes": "the extraordinary 2022-2023 gold re-export volumes appear here and in the mirror"},
    {"name": "NBT official rate and quarterly remittance statistics (Tajikistan)",
     "cadence": "daily and quarterly", "time_utc": "05:00",
     "source": "National Bank of Tajikistan", "actual_series": "NBT:official_rate",
     "expected_series": "n/a",
     "notes": "the official leg of the two-price state; the bureau leg is press-reported only"},
    {"name": "China customs monthly natural gas imports by origin (the Turkmen mirror)",
     "cadence": "monthly", "time_utc": "03:00",
     "source": "General Administration of Customs of the People's Republic of China",
     "actual_series": "CHINACUSTOMS:gas_imports_tm", "expected_series": "n/a",
     "notes": "the ONLY lawful quantified read on Turkmen gas; a foreign release standing in "
              "for an absent domestic one, which is the pack's worked mirror case"},
    {"name": "UN Comtrade mirror pulls: EU, Turkey and China exports to the five",
     "cadence": "monthly as reporters file", "time_utc": "UNMEASURED", "source": "UN Comtrade",
     "actual_series": "COMTRADE:mirror", "expected_series": "n/a",
     "notes": "the reporters file on their own clocks, so a mirror comparison is only PIT-safe "
              "when both vintages are stamped; this is the single largest PIT trap in the pack"},
    {"name": "EAEU statistical portal: intra-union trade for Armenia and Kyrgyzstan",
     "cadence": "monthly", "time_utc": "UNMEASURED",
     "source": "Eurasian Economic Commission", "actual_series": "EAEU:intra_trade",
     "expected_series": "n/a",
     "notes": "Armenia and Kyrgyzstan are inside the customs union, so their trade with Russia "
              "is INTRA-UNION and is not customs-declared the same way -- a structural reason "
              "the two are the corridor's preferred routes and a measurement caveat at once"},
)
