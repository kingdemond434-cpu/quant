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

# --------------------------------------------------------------------------- holidays
#: THE FIXED NATIONAL DAYS, PER JURISDICTION, DERIVED BY `national_holidays(j, year)`. Four of
#: the five keep NOWRUZ on 21 March and the two Islamic feasts; ARMENIA KEEPS NEITHER. That is
#: not an omission and it is the single most important calendar fact in this pack: Armenia is a
#: Christian country whose Christmas is 6 JANUARY (Surb Tsnund, the unsplit Nativity-Epiphany of
#: the Armenian Apostolic Church), and a regional holiday model that gives Armenia a Nowruz or
#: an Eid closure is wrong on about a dozen days a year -- exactly the days a liquidity study
#: would be conditioning on.
FIXED_NATIONAL: dict[str, tuple[tuple[int, int, str], ...]] = {
    "am": ((1, 1, "Nor tari (New Year)"), (1, 2, "Nor tari (second day)"),
           (1, 6, "Surb Tsnund -- ARMENIAN CHRISTMAS, 6 January, not 25 December"),
           (1, 28, "Banaki or (Army Day)"), (3, 8, "Kanants ton (Women's Day)"),
           (4, 24, "Mets Egherni zoheri hishataki or (Genocide Remembrance Day)"),
           (5, 1, "Ashkhatanki or (Labour Day)"), (5, 9, "Hahtanaki ev khaghaghutyan or"),
           (5, 28, "Arajin Hanrapetutyan or (First Republic Day)"),
           (7, 5, "Sahmanadrutyan or (Constitution Day)"),
           (9, 21, "Ankakhutyan or (Independence Day)"),
           (12, 31, "Nor tarva nakhoreak (New Year's Eve)")),
    "uz": ((1, 1, "Yangi yil (New Year)"),
           (1, 14, "Vatan himoyachilari kuni (Defenders of the Motherland Day)"),
           (3, 8, "Xotin-qizlar kuni (Women's Day)"), (3, 21, "Navro'z -- NOWRUZ"),
           (5, 9, "Xotira va qadrlash kuni (Day of Remembrance and Honour)"),
           (9, 1, "Mustaqillik kuni (Independence Day)"),
           (10, 1, "O'qituvchi va murabbiylar kuni (Teachers' Day)"),
           (12, 8, "Konstitutsiya kuni (Constitution Day)")),
    "kg": ((1, 1, "Jany jyl (New Year)"), (1, 7, "Orthodox Christmas"),
           (2, 23, "Ata Mekendi korgoochular kunu (Defender of the Fatherland Day)"),
           (3, 8, "Ayaldar kunu (Women's Day)"), (3, 21, "Nooruz -- NOWRUZ"),
           (4, 7, "El Aprel revolyutsiyasynyn kunu (Day of the April Revolution)"),
           (5, 1, "Emgek kunu (Labour Day)"), (5, 5, "Konstitutsiya kunu (Constitution Day)"),
           (5, 9, "Jenish kunu (Victory Day)"),
           (8, 31, "Kozkarandysyzdyk kunu (Independence Day)"),
           (11, 7, "Tarykh jana ata-babalardy eskeruu kunu"),
           (11, 8, "Tarykh jana ata-babalardy eskeruu kunu (second day)")),
    "tj": ((1, 1, "Soli nav (New Year)"), (3, 8, "Ruzi modaron (Mother's Day)"),
           (3, 21, "Navruz -- NOWRUZ day 1"), (3, 22, "Navruz day 2"),
           (3, 23, "Navruz day 3"), (3, 24, "Navruz day 4"),
           (5, 1, "Ruzi mehnat (Labour Day)"), (5, 9, "Ruzi ghalaba (Victory Day)"),
           (6, 27, "Ruzi vahdati milli (National Unity Day)"),
           (9, 9, "Ruzi istiqloliyat (Independence Day)"),
           (11, 6, "Ruzi Konstitutsiya (Constitution Day)")),
    "tm": ((1, 1, "Taze yyl (New Year)"), (1, 12, "Hatyra guni (Memorial Day)"),
           (3, 8, "Ayallar guni (Women's Day)"), (3, 21, "Novruz bayramy day 1 -- NOWRUZ"),
           (3, 22, "Novruz bayramy day 2"), (5, 9, "Yenis guni (Victory Day)"),
           (5, 18, "Konstitusiya we Magtymguly Pyragynyn sahyrcylyk guni"),
           (9, 27, "Garassyzlyk guni (Independence Day)"),
           (10, 6, "Hatyra guni (1948 Ashgabat earthquake remembrance)"),
           (12, 12, "Bitaraplyk guni (Neutrality Day)")),
}

#: WHICH JURISDICTIONS KEEP NOWRUZ, AND ON WHICH DAYS. Armenia is absent from this mapping ON
#: PURPOSE, and `nowruz_jurisdictions()` is what a miner asks rather than assuming five.
NOWRUZ_DAYS: dict[str, tuple[int, ...]] = {"uz": (21,), "kg": (21,), "tj": (21, 22, 23, 24),
                                           "tm": (21, 22)}
NOWRUZ_ABSENT: dict[str, str] = {
    "am": "Armenia does not observe Nowruz in any form. It is a Christian country whose church "
          "calendar has no Iranian new year in it, its labour code does not list 21 March, and "
          "a regional closure model that assumes otherwise mislabels an ordinary Armenian "
          "trading day as a holiday every single year",
}

#: THE TWO ISLAMIC FEASTS, TYPED BECAUSE NO RULE IN THIS FILE COMPUTES THEM. The four Muslim-
#: majority jurisdictions here follow the CALCULATED calendar announced by decree rather than a
#: local sighting, which is why their dates usually agree with each other and with the Gulf --
#: but "usually" is not "always", and a national decree can still move a date by a day. Every
#: row therefore carries its STATUS and the authority that sets it. Armenia is absent from all
#: of them.
ISLAMIC_FEASTS: dict[int, tuple[tuple[date, str, str, tuple[str, ...]], ...]] = {
    2024: ((date(2024, 4, 10), "Eid al-Fitr (Ramazon/Orozo/Idi Ramazon/Oraza bayramy)",
            "ANNOUNCED_BY_DECREE", ("uz", "kg", "tj", "tm")),
           (date(2024, 6, 16), "Eid al-Adha (Qurbon/Kurman/Idi Qurbon/Gurban bayramy)",
            "ANNOUNCED_BY_DECREE", ("uz", "kg", "tj", "tm"))),
    2025: ((date(2025, 3, 30), "Eid al-Fitr (Ramazon/Orozo/Idi Ramazon/Oraza bayramy)",
            "ANNOUNCED_BY_DECREE", ("uz", "kg", "tj", "tm")),
           (date(2025, 6, 6), "Eid al-Adha (Qurbon/Kurman/Idi Qurbon/Gurban bayramy)",
            "ANNOUNCED_BY_DECREE", ("uz", "kg", "tj", "tm"))),
    2026: ((date(2026, 3, 20), "Eid al-Fitr (Ramazon/Orozo/Idi Ramazon/Oraza bayramy)",
            "PROJECTED", ("uz", "kg", "tj", "tm")),
           (date(2026, 5, 27), "Eid al-Adha (Qurbon/Kurman/Idi Qurbon/Gurban bayramy)",
            "PROJECTED", ("uz", "kg", "tj", "tm"))),
}

#: THE AUTHORITY THAT SETS EACH ONE, named rather than implied. A typed date with a named
#: authority is honest; a computed date from a rule this file does not have would be a lie with
#: a function wrapped round it.
FEAST_AUTHORITY: dict[str, str] = {
    "uz": "the Cabinet of Ministers of Uzbekistan announces the non-working days by decision; "
          "the Muslim Board of Uzbekistan announces the feast itself",
    "kg": "the Cabinet of Ministers of the Kyrgyz Republic; the Muftiate announces the feast",
    "tj": "the Government of Tajikistan; the Islamic Centre announces the feast",
    "tm": "a decree of the President of Turkmenistan, published in the state press only",
    "am": "NOT OBSERVED -- Armenia keeps no Islamic feast",
}

#: DECREED ONE-OFFS AND MOVED DAYS. These exist because these calendars ARE decreed rather than
#: statutory, and a moved national day is a regime break a pooled study silently absorbs. The
#: Turkmen Neutrality Day is the standing example: it was 12 December, was moved to 27 November
#: by decree in 2018, and was moved back to 12 December in 2023.
DECREED_MOVES: tuple[tuple[str, str, str, str], ...] = (
    ("tm", "Neutrality Day", "2018: moved from 12 December to 27 November by presidential "
                             "decree", "PRESS_REPORTED"),
    ("tm", "Neutrality Day", "2023: moved back to 12 December by presidential decree",
     "PRESS_REPORTED"),
    ("tm", "Independence Day", "2018: moved from 27 October to 27 September by decree",
     "PRESS_REPORTED"),
    ("am", "January 3-5 and 7", "non-working in several years by amendment to the labour code; "
                                "carried as UNCERTAIN rather than typed into the table",
     "UNCERTAIN"),
)


def nowruz_jurisdictions() -> tuple[str, ...]:
    """Which of the five keep Nowruz. FOUR, not five -- Armenia is not one of them."""
    return tuple(sorted(NOWRUZ_DAYS))


def national_holidays(jurisdiction: str, year: int) -> dict[date, str]:
    """One jurisdiction's closed days in one year: its fixed statutory dates plus the two
    Islamic feasts where that jurisdiction keeps them. NO WEEKEND SUBSTITUTION is applied: the
    transfer of a weekend holiday to a Monday is DECREED per year in Uzbekistan and Kyrgyzstan
    and is not computable from a rule, so the pack carries the statutory day and says so.
    """
    key = str(jurisdiction).lower()
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL.get(key, ()):
        out[date(year, m, d)] = name
    for day, name, status, where in ISLAMIC_FEASTS.get(year, ()):
        if key in where:
            out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def regional_holidays(year: int) -> dict[date, tuple[str, ...]]:
    """Every closed day anywhere in the five, with WHICH jurisdictions close on it. A day that
    closes one of five is a different liquidity object from a day that closes four."""
    out: dict[date, list[str]] = {}
    for key in JURISDICTIONS:
        for day in national_holidays(key, year):
            out.setdefault(day, []).append(key)
    return {d: tuple(sorted(v)) for d, v in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The regional closure table for one year, weekdays only -- a Saturday closure costs no
    session and must not enter a holiday-liquidity sample as one."""
    out: dict[date, str] = {}
    for day, where in regional_holidays(year).items():
        if day.weekday() >= 5:
            continue
        names = {national_holidays(k, year)[day] for k in where}
        out[day] = f"{'/'.join(where)}: {sorted(names)[0]}"
    return out


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def closure_breadth(day: date) -> int:
    """How many of the five jurisdictions are closed on a date. THE STATE VARIABLE of CCA-N:
    one closed of five is noise, four closed of five is the region's liquidity leaving."""
    return len(regional_holidays(day.year).get(day, ()))


def nowruz_block(year: int) -> tuple[date, ...]:
    """The contiguous regional Nowruz closure, 21 March to the last day any of the four keeps.
    Tajikistan's four days make the block longer than the 21st every year."""
    days = sorted({d for row in NOWRUZ_DAYS.values() for d in row})
    return tuple(date(year, 3, d) for d in days)


def eid_navruz_collision(year: int) -> int | None:
    """Days between Eid al-Fitr and 21 March in a year, or None when the year is not declared.

    THE 2026 CASE IS WHY THIS FUNCTION EXISTS. Eid al-Fitr drifts about eleven days earlier each
    solar year, so it walks INTO Nowruz roughly once a generation. In 2026 the projected Eid
    (20 March) lands the day before Nowruz (21 March), which merges two separate closures into
    ONE multi-day regional block across four jurisdictions -- while Armenia trades through it.
    A study that treats the two as independent closures double-counts that year, and a study
    that conditions on "a Nowruz week" pools a one-day closure with a five-day one.
    """
    rows = ISLAMIC_FEASTS.get(year, ())
    for day, name, _status, _where in rows:
        if "Fitr" in name:
            return (day - date(year, 3, 21)).days
    return None


def collision_years(window: int = 4) -> tuple[int, ...]:
    """The declared years in which Eid al-Fitr falls within `window` days of Nowruz."""
    out = []
    for year in sorted(ISLAMIC_FEASTS):
        gap = eid_navruz_collision(year)
        if gap is not None and abs(gap) <= window:
            out.append(year)
    return tuple(out)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_plus_declared_table",
    "authority": "five national labour codes and five governments; the Islamic feasts are fixed "
                 "by government decision in Uzbekistan, Kyrgyzstan and Tajikistan and by "
                 "presidential decree in Turkmenistan. ARMENIA KEEPS NEITHER NOWRUZ NOR AN EID",
    "rule": "PER JURISDICTION, derived by `national_holidays(jurisdiction, year)`. Armenia: "
            "twelve fixed Christian and civic days -- 1 and 2 January, 6 JANUARY (Armenian "
            "Christmas, NOT 25 December), 28 January, 8 March, 24 April, 1 May, 9 May, 28 May, "
            "5 July, 21 September and 31 December. Uzbekistan: 1 and 14 January, 8 March, "
            "21 March (Navro'z), 9 May, 1 September, 1 October and 8 December. Kyrgyzstan: "
            "1 and 7 January, 23 February, 8 March, 21 March (Nooruz), 7 April, 1, 5 and 9 May, "
            "31 August and 7-8 November. Tajikistan: 1 January, 8 March, 21-24 March (Navruz, "
            "FOUR days), 1 and 9 May, 27 June, 9 September and 6 November. Turkmenistan: 1 and "
            "12 January, 8 March, 21-22 March (Novruz), 9 and 18 May, 27 September, 6 October "
            "and 12 December. PLUS the two Islamic feasts in the four Muslim-majority states, "
            "TYPED in ISLAMIC_FEASTS with a status and a named authority because no rule in "
            "this file computes them. NO WEEKEND SUBSTITUTION is applied: the transfer of a "
            "weekend holiday is decreed per year and is not derivable. The Turkmen calendar is "
            "DECREED and has been moved twice in living memory (DECREED_MOVES), which is a "
            "regime break a pooled closure study absorbs silently.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday in all five",
    "national_rule": "see `rule`; `national_holidays(jurisdiction, year)` is the computed form",
    "market_rule": "the union across the five, weekdays only; `closure_breadth(day)` says how "
                   "many of the five are actually shut, which is the state a liquidity study "
                   "must condition on rather than a binary holiday flag",
    "moon_sighting_rule": "CALCULATED AND DECREED, not sighted: these four states announce the "
                          "feast by government decision on a calculated calendar, which is why "
                          "their dates usually agree with the Gulf -- but a decree can still "
                          "move a date by a day and the status field says which rows are firm",
    "moving_feasts": "the two Eids drift about eleven days earlier each solar year; in 2026 "
                     "Eid al-Fitr lands the day before Nowruz, merging two closures into one",
    "armenia_exception": "Armenia observes NO Nowruz and NO Eid, and its Christmas is 6 January",
    "table": {y: {d.isoformat(): (f"{'/'.join(w)}: "
                                  f"{sorted({national_holidays(k, y)[d] for k in w})[0]}")
                  for d, w in regional_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "ANNOUNCED for every fixed day and for both Eids (decreed and past)",
               2025: "ANNOUNCED for every fixed day and for both Eids (decreed and past)",
               2026: "ANNOUNCED for the fixed days; PROJECTED for both Eids -- a 2026 decree "
                     "has not been issued and a date can still move by a day"},
    "known_dates": {
        "2024-01-06": "Armenian Christmas -- the date a Gregorian calendar gets wrong",
        "2024-03-21": "Nowruz in four of the five; an ordinary trading day in Armenia",
        "2025-03-30": "Eid al-Fitr, nine days after Nowruz -- two separate closures",
        "2026-03-20": "PROJECTED Eid al-Fitr, ONE DAY BEFORE Nowruz: the collision year",
        "2026-04-24": "Armenian Genocide Remembrance Day, fixed and certain in every year",
        "2026-12-12": "Turkmen Neutrality Day, back on 12 December after the 2018-2023 move",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "regional_fn": regional_holidays,
    "breadth_fn": closure_breadth,
    "nowruz_fn": nowruz_block,
    "collision_fn": eid_navruz_collision,
}

# --------------------------------------------------------------------------- the mechanisms
#: THE CORRIDOR'S OWN ERA BOUNDARIES, as dated public decisions rather than as change points an
#: algorithm found. Both are events with a document behind them, which is the only kind of
#: boundary a preregistered study may condition on.
CORRIDOR_START = date(2022, 2, 24)      # the invasion; the corridor's demand appears at once
CORRIDOR_ENFORCEMENT = date(2023, 12, 22)   # US EO 14114: foreign financial institutions exposed
CORRIDOR_ERAS: tuple[str, ...] = ("PRE_CORRIDOR", "SURGE", "ENFORCEMENT")


def corridor_era(day: date) -> str:
    """Which corridor regime a date is in. THREE, and the boundaries are documents.

    PRE_CORRIDOR before 2022-02-24; SURGE from the invasion to 2023-12-21, when re-export and
    transfer volumes rose by multiples with essentially no enforcement friction; ENFORCEMENT
    from 2023-12-22, the date the United States exposed FOREIGN FINANCIAL INSTITUTIONS to
    secondary sanctions for facilitating the trade, after which regional banks began refusing
    Russian-linked payments and the flow re-routed rather than stopping. A study that pools the
    second and third eras is measuring the average of a boom and a de-risking wave.
    """
    if day < CORRIDOR_START:
        return "PRE_CORRIDOR"
    if day < CORRIDOR_ENFORCEMENT:
        return "SURGE"
    return "ENFORCEMENT"


def corridor_era_days(start: date, end: date, era_name: str) -> list[date]:
    """Every weekday inside [start, end] that belongs to one corridor era -- the sample and its
    own control period, built from the same function so neither can drift from the other."""
    out: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5 and corridor_era(day) == era_name:
            out.append(day)
        day += timedelta(days=1)
    return out


def transfer_release_days(start: date, end: date) -> list[date]:
    """The CBA monthly transfer-release window: the 28th, 29th and 30th of each month, rolled
    forward off a weekend. The exact day moves within that window, so the pack carries the
    WINDOW and the miner stamps the true day from the release before any cell is compiled."""
    out: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        for dom in (28, 29, 30):
            try:
                day = date(year, month, dom)
            except ValueError:                      # February in a non-leap year
                continue
            while day.weekday() >= 5:
                day += timedelta(days=1)
            if start <= day <= end and day not in out:
                out.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return sorted(out)


def remittance_window(year: int, month: int) -> tuple[date, date]:
    """The month-end remittance payout window: the last weekday of `month` through the second
    weekday of the next. Russian wages are paid around the month end and the transfer rail
    carries its largest volume across that boundary, which is a SCHEDULED FX demand in four of
    the five jurisdictions and the reason CCA-B is a calendar domain and not a macro one."""
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    while last.weekday() >= 5:
        last -= timedelta(days=1)
    day, seen = nxt, 0
    while seen < 2:
        if day.weekday() < 5:
            seen += 1
        if seen < 2:
            day += timedelta(days=1)
    return last, day


def parallel_premium(official: float, parallel: float) -> float:
    """The parallel-market premium as a fraction of the official rate.

    THE STATE VARIABLE OF CCA-TM-B AND CCA-TJ-B. Where a rate is administered -- Turkmenistan's
    fix at 3.50 since 2015-01-01, Tajikistan's guided rate -- the official price is a constant
    or near-constant and carries no information at all. What carries information is how far the
    second price has moved away from it: a premium is the market's estimate of the fix's cost,
    and it widens before a devaluation, an import-licence squeeze or a fuel shortage. Returns
    0.0 for an unusable official rate rather than raising, because an unreadable input is
    UNMEASURED and must not look like a zero premium to the caller -- `premium_state` is what a
    miner reads, and it says UNMEASURED by name.
    """
    if official <= 0 or parallel <= 0:
        return 0.0
    return parallel / official - 1.0


#: The premium buckets CCA-TM-B and CCA-TJ-B condition on. Chosen as ROUND NUMBERS and declared
#: here rather than fitted, so the bucketing cannot be tuned to the outcome.
PREMIUM_BUCKETS: tuple[tuple[str, float], ...] = (
    ("TIGHT", 0.05), ("STRESSED", 0.25), ("BROKEN", 1.00), ("PARALLEL_IS_THE_MARKET", 1e9))


def premium_state(official: float, parallel: float) -> str:
    """The declared bucket for a parallel premium, or UNMEASURED when either leg is unusable."""
    if official <= 0 or parallel <= 0:
        return "UNMEASURED"
    prem = parallel_premium(official, parallel)
    for name, top in PREMIUM_BUCKETS:
        if prem < top:
            return name
    return "PARALLEL_IS_THE_MARKET"

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CBA monthly non-commercial money transfers by source country (Armenia)",
     "root": "https://www.cba.am/en/SitePages/statmonetaryfinancial.aspx",
     "fields": ("inflow_by_country", "outflow_by_country", "net", "currency_split",
                "russia_share"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 30, "licence": "free, public", "available": True, "jurisdiction": "am",
     "why": "THE CLEANEST HOUSEHOLD-FLOW SERIES IN THE REGION and the input to the pack's "
            "central mechanism: a cross-border transfer series BY ORIGIN, monthly, free, from "
            "a central bank, in an economy where the flow is a large share of GDP",
     "pit_warning": "a month stale and revised once; never a same-month conditioner, and the "
                    "2022 level shift is so large that any window spanning it must be split"},
    {"name": "NBKR FX auction results (Kyrgyzstan) -- volume and rate, same day",
     "root": "https://www.nbkr.kg/index1.jsp?item=1806&lang=ENG",
     "fields": ("auction_date", "direction", "volume_usd", "weighted_rate"),
     "frequency": "per auction (irregular, often several a month)", "snapshot": "auction day",
     "publish_utc": "05:00", "lag_days": 0, "licence": "free, public", "available": True,
     "jurisdiction": "kg",
     "why": "the only SAME-DAY published intervention series in this pack; the size is the "
            "corridor's dollar demand made visible before any customs table catches up",
     "pit_warning": "the auction is announced and published the same day, so it IS point-in-"
                    "time -- but the DECISION to auction is endogenous to the flow being "
                    "measured, which is a selection problem the control arm must carry"},
    {"name": "CBU monthly international reserves and the gold share (Uzbekistan)",
     "root": "https://cbu.uz/en/statistics/gold-and-foreign-exchange-reserves/",
     "fields": ("total_reserves", "gold_tonnes", "gold_value", "fx_value", "monthly_change"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "06:00", "lag_days": 7,
     "licence": "free, public", "available": True, "jurisdiction": "uz",
     "why": "a sovereign gold position published monthly in BOTH tonnes and value, which is "
            "what lets an operation be separated from a price move -- most countries publish "
            "only the value and the two are then inseparable",
     "pit_warning": "the tonnage is occasionally restated; a month whose tonnage moved AND "
                    "whose price moved is UNMEASURED unless both vintages are held"},
    {"name": "UN Comtrade mirror positioning: what the world says it shipped to the five",
     "root": "https://comtradeplus.un.org",
     "fields": ("reporter", "partner", "hs_code", "value_usd", "quantity", "period"),
     "frequency": "monthly as reporters file", "snapshot": "calendar month",
     "publish_utc": "UNMEASURED", "lag_days": 60, "licence": "free with an API key; rate caps",
     "available": True, "jurisdiction": "regional",
     "why": "THE MIRROR. The corridor's size is the gap between what the EU, Turkey and China "
            "say they exported to these five and what the five say they imported and re-"
            "exported; both halves are public and neither alone is the measurement",
     "pit_warning": "reporters file on their own clocks and BACKFILL, so a mirror gap computed "
                    "from today's database is not the gap that was visible at the time -- the "
                    "single largest point-in-time trap in this pack, and the reason every "
                    "mirror cell is NOT_PIT_SAFE until a stamped vintage is held"},
    {"name": "A CFTC or exchange-traded positioning series for AMD, UZS, KGS, TJS or TMT",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False, "jurisdiction": "regional",
     "why": "DECLARED ABSENT: no future, no option and no COT contract exists for any of the "
            "five currencies on any exchange the desk can read",
     "pit_warning": "DOES NOT EXIST. Regional currency positioning is UNMEASURED and is never "
                    "proxied by the RUB or CNH legs -- those are positions in the corridor's "
                    "counterparties, not in the corridor"},
    {"name": "A Turkmen reserve, positioning or balance-of-payments series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False, "jurisdiction": "tm",
     "why": "DECLARED ABSENT: Turkmenistan publishes no auditable reserve series, no balance of "
            "payments and no machine-readable national accounts",
     "pit_warning": "DOES NOT EXIST DOMESTICALLY. The substitute is CHINESE CUSTOMS, which "
                    "gives volumes and values but not reserves -- so Turkmen external position "
                    "stays UNMEASURED and every Turkmen cell says so on its face"},
)

# --------------------------------------------------------------------------- terminology
#: SIX WRITING SYSTEMS FOR FIVE COUNTRIES, AND THE PACK MEANS ALL OF THEM.
#:
#:   * ARMENIAN (Հայերեն) has an alphabet of its own that shares nothing with Latin or Cyrillic.
#:     A crawler that does not carry it reads the English-language corner of Armenia and reports
#:     the corner as the country.
#:   * UZBEK IS WRITTEN IN BOTH LATIN AND CYRILLIC, AND THE SPLIT IS ITSELF A CRAWLING FACT.
#:     The Latin alphabet is official and is what lex.uz, the ministries and the younger press
#:     use; Cyrillic is what a very large part of the population still reads and writes, and it
#:     is what much of the older archive, the regional press and the comment sections are in. A
#:     query in one script MISSES the other half of the ground -- this is not a stylistic
#:     preference, it is two disjoint corpora with the same meaning, and both are carried here.
#:   * KYRGYZ and TAJIK are Cyrillic (Tajik with its own ӣ ҳ ҷ қ ғ ӯ), TURKMEN is Latin with
#:     ä ň ö ü ý ş ç ž, and RUSSIAN is the shared regional working language of all five -- the
#:     language the customs forms, the bank circulars and the freight contracts are actually in.
#:   * CHINESE is carried too, because the Turkmen gas volumes exist in Chinese customs data and
#:     nowhere else, and a Chinese-language query is the only way to reach the detailed tables.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "CCA-A": ("վերաարտահանում", "մաքսային վիճակագրություն", "արտահանում", "ներմուծում",
              "qayta eksport", "bojxona statistikasi", "қайта экспорт", "божхона статистикаси",
              "реэкспорт", "параллельный импорт", "зеркальная статистика",
              "таможенная статистика", "реэкспорт товаров", "обход санкций",
              "вторичные санкции", "подсанкционные товары", "土库曼斯坦", "海关总署",
              "进口来源国"),
    "CCA-B": ("դրամական փոխանցումներ", "ոչ առևտրային փոխանցումներ", "տրանսֆերտներ",
              "pul o'tkazmalari", "пул ўтказмалари", "акча которуулар", "интиқоли пул",
              "денежные переводы", "трудовые мигранты", "переводы физических лиц",
              "системы денежных переводов", "мигрантлар", "эмгек мигранттары"),
    "CCA-C": ("ոսկի", "ոսկու արտահանում", "թանկարժեք մետաղներ", "oltin", "олтин",
              "oltin zaxiralari", "олтин захиралари", "алтын", "алтын экспорту", "Кумтөр",
              "тилла", "золото", "золотовалютные резервы", "аффинаж золота",
              "монетарное золото", "Мурунтау", "Навоий кон-металлургия комбинати"),
    "CCA-AM-A": ("Կենտրոնական բանկ", "վերաֆինանսավորման տոկոսադրույք", "գնաճ", "փոխարժեք",
                 "արժութային միջամտություն", "աճուրդ", "միջազգային պահուստներ",
                 "դրամի արժևորում", "ՀՆԱ", "տնտեսական աճ", "ՏՏ ընկերություններ",
                 "վերաբնակեցում", "ռելոկացիա"),
    "CCA-AM-B": ("պղինձ", "մոլիբդեն", "խտանյութ", "Զանգեզուր", "Քաջարան", "հանքարդյունաբերություն",
                 "պղնձի խտանյութ", "արտահանման ծավալ", "медный концентрат", "молибден",
                 "Зангезурский медно-молибденовый комбинат"),
    "CCA-UZ-A": ("markaziy bank", "asosiy stavka", "inflyatsiya", "valyuta kursi",
                 "xalqaro zaxiralar", "марказий банк", "асосий ставка", "инфляция",
                 "валюта курси", "халқаро захиралар", "so'm", "сўм", "so'm kursi",
                 "devalvatsiya", "девальвация", "erkinlashtirish", "эркинлаштириш"),
    "CCA-UZ-B": ("paxta tolasi", "пахта толаси", "paxta klasteri", "пахта кластери",
                 "davlat xaridi", "давлат хариди", "birja savdolari", "биржа савдолари",
                 "хлопковое волокно", "госзаказ на хлопок", "UzEX", "хлопковый кластер"),
    "CCA-KG-A": ("Улуттук банк", "эсептик чен", "валюта интервенциясы", "валюта аукциону",
                 "алтын-валюта кору", "сом курсу", "инфляция", "Национальный банк",
                 "валютный аукцион", "интервенция", "учетная ставка"),
    "CCA-KG-B": ("Кумтөр", "алтын өндүрүш", "Кыргызалтын", "тышкы соода", "бажы статистикасы",
                 "реэкспорт", "Дордой", "Кара-Суу базары", "Кумтор", "внешняя торговля",
                 "таможенная служба"),
    "CCA-TJ-A": ("Бонки миллии Тоҷикистон", "қурби асъор", "содирот", "воридот", "сомонӣ",
                 "нархи асъор", "бозори сиёҳи асъор", "интиқоли пул", "муҳоҷирони меҳнатӣ",
                 "Национальный банк Таджикистана", "курс сомони", "черный курс"),
    "CCA-TJ-B": ("алюминий", "ТАЛКО", "Роғун", "неругоҳи барқии обӣ", "Норак", "Вахш",
                 "гидроэнергетика", "Рогунская ГЭС", "алюминиевый завод", "энергетика",
                 "барқ"),
    "CCA-TM-A": ("tebigy gaz", "gaz geçirijisi", "Türkmengaz", "Galkynyş", "eksport",
                 "Merkezi bank", "manat", "hümmet", "nebit", "природный газ",
                 "Туркменгаз", "газопровод Центральная Азия - Китай", "天然气进口",
                 "中亚天然气管道", "土库曼斯坦天然气"),
    "CCA-TM-B": ("manadyň hümmeti", "gara bazar", "walyuta", "resmi hümmet", "nyrh",
                 "чёрный курс маната", "параллельный курс", "официальный курс", "дефицит валюты",
                 "обменный пункт"),
    "CCA-N": ("Նավասարդ", "Սուրբ Ծնունդ", "տոն", "ոչ աշխատանքային օր", "Navro'z", "Наврўз",
              "Ramazon hayit", "Рамазон ҳайит", "Qurbon hayit", "Нооруз", "Орозо айт",
              "Курман айт", "Навруз", "Иди Рамазон", "Иди Қурбон", "Novruz baýramy",
              "Oraza baýramy", "Gurban baýramy", "нерабочий день", "праздничные дни"),
    "CCA-E": ("պատժամիջոցներ", "Լաչինի միջանցք", "sanksiyalar", "санксиялар", "санкциялар",
              "таҳримҳо", "sanksiýalar", "санкции", "вторичные санкции", "комплаенс",
              "отказ в платеже", "корреспондентский счёт"),
    "CCA-F": ("էներգետիկա", "գազ", "tabiiy gaz", "табиий газ", "газ импорти", "газ экспорту",
              "барқ", "электроэнергия", "газопровод", "энергетический кризис", "лимит газа"),
}

#: The Uzbek LATIN vocabulary the pack must carry alongside its Cyrillic twin. Declared as a
#: marker set so a test can prove the Latin half did not quietly disappear into the Cyrillic
#: one -- which is exactly what happens when one person writes the terminology.
UZBEK_LATIN_MARKERS: tuple[str, ...] = (
    "qayta eksport", "bojxona statistikasi", "pul o'tkazmalari", "oltin", "oltin zaxiralari",
    "markaziy bank", "asosiy stavka", "inflyatsiya", "valyuta kursi", "xalqaro zaxiralar",
    "so'm", "so'm kursi", "devalvatsiya", "erkinlashtirish", "paxta tolasi", "paxta klasteri",
    "davlat xaridi", "birja savdolari")
#: The Turkmen LATIN vocabulary, which shares no script with any other jurisdiction here.
TURKMEN_LATIN_MARKERS: tuple[str, ...] = (
    "tebigy gaz", "gaz geçirijisi", "Türkmengaz", "Galkynyş", "Merkezi bank", "manat",
    "hümmet", "nebit", "manadyň hümmeti", "gara bazar", "resmi hümmet", "nyrh",
    "Novruz baýramy", "Oraza baýramy", "Gurban baýramy", "walyuta")

_ARMENIAN = (0x0530, 0x058F)
_CYRILLIC = ((0x0400, 0x04FF), (0x0500, 0x052F))
_HAN = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))


def has_armenian(text: str) -> bool:
    """True when `text` contains at least one Armenian letter (U+0530..U+058F)."""
    lo, hi = _ARMENIAN
    return any(lo <= ord(ch) <= hi for ch in str(text))


def has_cyrillic(text: str) -> bool:
    """True when `text` contains at least one Cyrillic letter -- Uzbek, Kyrgyz, Tajik or
    Russian; the four of them share the block and are told apart by vocabulary, not codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _CYRILLIC) for ch in str(text))


def has_han(text: str) -> bool:
    """True when `text` contains a Han character -- the Chinese mirror ground's own script."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _HAN) for ch in str(text))


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms]


def armenian_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return sorted({t for t in _flat_terms(terminology) if has_armenian(t)})


def cyrillic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return sorted({t for t in _flat_terms(terminology) if has_cyrillic(t)})


def han_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return sorted({t for t in _flat_terms(terminology) if has_han(t)})


def uzbek_latin_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = set(_flat_terms(terminology))
    return sorted(t for t in UZBEK_LATIN_MARKERS if t in flat)


def turkmen_latin_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = set(_flat_terms(terminology))
    return sorted(t for t in TURKMEN_LATIN_MARKERS if t in flat)


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    """Distinct terms across every domain key of a terminology table."""
    return len(set(_flat_terms(terminology)))


# --------------------------------------------------------------------------- the ten layers
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


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=False`
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


def jurisdiction_absence(jurisdiction: str, layer: str, *, reason: str,
                         substitute: str, substitute_root: str) -> dict[str, Any]:
    """A layer ONE jurisdiction has no lawful ground in, with the substitute that stands in.

    THIS IS THE ROW THE PACK EXISTS TO DEMONSTRATE. A regional pack can be fully sourced in all
    ten layers and still be blind in one country -- Turkmenistan publishes essentially nothing,
    and averaging it into a regional coverage number would hide that. So the absence is declared
    PER JURISDICTION, with a REASON that names the missing publication and a SUBSTITUTE that
    names the lawful ground read instead. An absence with a substitute is a measurement and a
    plan; an absence with neither is work nobody did.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    if jurisdiction not in JURISDICTIONS:
        raise ValueError(f"jurisdiction {jurisdiction!r} is not one of {list(JURISDICTIONS)}")
    return {"id": f"no_ground_{jurisdiction}_{layer}", "jurisdiction": jurisdiction,
            "layer": layer, "reason": reason, "substitute": substitute,
            "substitute_root": substitute_root,
            "rule": "DECLARED ABSENT WITH A SUBSTITUTE: the layer is not blank, it is empty for "
                    "a named reason and the named ground is read in its place"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "cca_am_official", "Armenia: the Central Bank, the Statistical Committee, the State "
                           "Revenue Committee (customs) and the legal gazette", layer="official",
        roots=("https://www.cba.am", "https://armstat.am", "https://www.src.am",
               "https://www.arlis.am"),
        queries=("դրամական փոխանցումներ", "ոչ առևտրային փոխանցումներ", "մաքսային վիճակագրություն",
                 "վերաարտահանում", "վերաֆինանսավորման տոկոսադրույք", "միջազգային պահուստներ",
                 "արտաքին առևտուր", "ոսկու արտահանում", "գնաճ", "արժութային միջամտություն"),
        languages=("hy", "en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE CBA's MONTHLY TRANSFERS BY SOURCE COUNTRY is the single most valuable series "
              "in this pack; armstat's trade-by-partner tables are where a re-export becomes "
              "visible, and arlis.am carries the legal acts that date every policy change"),
    source_class(
        "cca_uz_official", "Uzbekistan: the Central Bank, the Statistics Agency, the customs "
                           "committee and lex.uz, the national legal database", layer="official",
        roots=("https://cbu.uz", "https://stat.uz", "https://customs.uz", "https://lex.uz"),
        queries=("oltin zaxiralari", "олтин захиралари", "asosiy stavka", "асосий ставка",
                 "valyuta kursi", "валюта курси", "paxta tolasi", "пахта толаси",
                 "bojxona statistikasi", "божхона статистикаси", "xalqaro zaxiralar",
                 "qayta eksport", "қайта экспорт", "erkinlashtirish"),
        languages=("uz", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="CRAWLED IN BOTH SCRIPTS ON PURPOSE. lex.uz publishes in Latin and Cyrillic and "
              "the two are not mirror images -- the Cyrillic side carries the older acts and "
              "much of the regional coverage, so a Latin-only crawl loses the archive"),
    source_class(
        "cca_kg_official", "Kyrgyzstan: the National Bank, the National Statistical Committee "
                           "and the customs service", layer="official",
        roots=("https://www.nbkr.kg", "http://www.stat.kg", "https://customs.gov.kg"),
        queries=("валюта аукциону", "эсептик чен", "алтын-валюта кору", "тышкы соода",
                 "бажы статистикасы", "реэкспорт", "алтын экспорту", "валютный аукцион",
                 "внешняя торговля", "золото экспорт"),
        languages=("ky", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the NBKR publishes its FX auction result the SAME DAY, which is the only same-"
              "day intervention series in this pack; stat.kg carries the gold re-export line "
              "that made Kyrgyzstan a named conduit"),
    source_class(
        "cca_tj_official", "Tajikistan: the National Bank and the Agency on Statistics",
        layer="official",
        roots=("https://nbt.tj", "https://www.stat.tj"),
        queries=("қурби асъор", "интиқоли пул", "содирот", "воридот", "алюминий",
                 "Роғун", "нархи асъор", "муҳоҷирони меҳнатӣ", "курс сомони"),
        languages=("tg", "ru", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the official rate is daily and the remittance statistics are quarterly; the "
              "LICENSED-BUREAU rate -- the second price, and the one that carries the stress -- "
              "is NOT published here and is press-reported only, which the pack says on its face"),
    source_class(
        "cca_tm_official", "Turkmenistan: the Central Bank, the State Statistics Committee and "
                           "the state news agency, such as they are", layer="official",
        roots=("https://www.cbt.tm", "https://stat.gov.tm", "https://tdh.gov.tm"),
        queries=("manadyň hümmeti", "resmi hümmet", "tebigy gaz", "Türkmengaz", "eksport",
                 "Galkynyş", "Merkezi bank"),
        languages=("tk", "ru", "en"), access_label="PUBLIC", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="REGISTERED, AND ITS LIMITS DECLARED. These sites exist and are lawful ground, "
              "but they publish a fixed rate, percentage growth claims with no levels, and no "
              "machine-readable trade or reserve tables. Credibility is UNRELIABLE not as an "
              "insult but as a measurement: the numbers cannot be reconciled against any mirror "
              "and the pack never compiles a cell on them alone. See NO_LAWFUL_GROUND"),
    source_class(
        "cca_mirror_customs", "THE MIRROR: China's General Administration of Customs and UN "
                              "Comtrade -- what the world says it shipped to these five",
        layer="official",
        roots=("http://www.customs.gov.cn", "http://stats.customs.gov.cn",
               "https://comtradeplus.un.org", "https://ec.europa.eu/eurostat/web/international-"
                                              "trade-in-goods/database"),
        queries=("土库曼斯坦天然气", "海关总署 进口来源国", "中亚天然气管道", "天然气进口 分国别",
                 "зеркальная статистика", "реэкспорт в Россию", "Comtrade mirror statistics",
                 "EU exports to Armenia Kyrgyzstan"),
        languages=("zh", "en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free; Comtrade needs an API key and rate-caps",
        notes="THE PACK'S LOAD-BEARING SOURCE. Turkmen gas volumes exist here and nowhere else, "
              "and the corridor's size is the GAP between these tables and the five states' own. "
              "Both halves must be vintage-stamped or the comparison is not point-in-time"),
    source_class(
        "cca_eaeu_official", "The Eurasian Economic Commission and the Eurasian Development "
                             "Bank: intra-union trade, tariffs and macro reviews",
        layer="official",
        roots=("http://www.eurasiancommission.org", "https://eec.eaeunion.org",
               "https://eabr.org/analytics/"),
        queries=("взаимная торговля ЕАЭС", "единый таможенный тариф", "реэкспорт",
                 "денежные переводы в страны ЕАЭС", "макроэкономический обзор",
                 "таможенная статистика ЕАЭС"),
        languages=("ru", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ARMENIA AND KYRGYZSTAN ARE INSIDE THE CUSTOMS UNION and Russia-bound goods "
              "therefore cross no customs border -- which is WHY they are the corridor's "
              "preferred routes and also why their Russia trade is measured differently from "
              "everyone else's; a study that ignores this compares two different instruments"),
    # ---- institutional
    source_class(
        "cca_exchanges", "The regional venues: the Armenia Securities Exchange, the Uzbek "
                         "Republican Commodity Exchange, the Tashkent currency exchange and the "
                         "NBKR auction platform", layer="institutional",
        roots=("https://amx.am", "https://uzex.uz", "https://www.nbkr.kg/index1.jsp?item=1806"),
        queries=("birja savdolari", "биржа савдолари", "paxta tolasi auksioni", "валюта аукциону",
                 "աճուրդ", "արժութային շուկա", "лот", "торги на бирже"),
        languages=("hy", "uz", "ky", "ru", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="NOT ONE of these venues is quoted by the broker; they are registered because the "
              "AUCTION RESULT is a dated public physical-flow observable and because UzEX's "
              "cotton lots are the Uzbek crop reaching the market"),
    source_class(
        "cca_ifis", "The development banks and the Fund: IMF Article IV and country pages, "
                    "World Bank, ADB, EBRD, AIIB and the Eurasian Development Bank",
        layer="institutional",
        roots=("https://www.imf.org/en/Countries/ARM", "https://www.imf.org/en/Countries/UZB",
               "https://www.adb.org/countries", "https://www.ebrd.com/where-we-are.html",
               "https://data.worldbank.org/country"),
        queries=("Armenia Article IV remittances", "Uzbekistan gold exports Article IV",
                 "Kyrgyz Republic re-exports", "Tajikistan remittances GDP share",
                 "Turkmenistan Article IV data provision", "отчёт МВФ",
                 "migration and remittances brief"),
        languages=("en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE IMF's DATA-PROVISION ANNEX for Turkmenistan is itself the citation for this "
              "pack's absence declarations: when the Fund records that a member does not "
              "provide the data, the absence is documented rather than assumed"),
    source_class(
        "cca_soe_issuers", "The state enterprises and sovereign issuers that must disclose: "
                           "Uzbekistan's eurobond programme and its SOE issuers, Zangezur, "
                           "Navoi, Kyrgyzaltyn, TALCO and Turkmengaz", layer="institutional",
        roots=("https://uzbekistan-ir.uz", "https://www.zangezurcmc.am", "https://www.ngmk.uz",
               "https://www.kyrgyzaltyn.kg", "http://www.talco.com.tj"),
        queries=("պղնձի խտանյութ", "Զանգեզուր արտադրություն", "oltin ishlab chiqarish",
                 "Навоий кон-металлургия комбинати", "Кумтөр өндүрүш", "ТАЛКО истеҳсолот",
                 "eurobond prospectus Uzbekistan", "производство алюминия"),
        languages=("hy", "uz", "ky", "tg", "ru", "en"), access_label="PUBLIC",
        credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public (issuer disclosure)",
        notes="A BOND PROSPECTUS IS THE BEST DATA THESE ECONOMIES PRODUCE: Uzbekistan's "
              "sovereign and SOE issuance forces audited volumes, costs and reserve detail into "
              "the open. Every name here is an ACTOR and never an instrument (two-lane order)"),
    # ---- academic
    source_class(
        "cca_academic", "The open scholarly record: OpenAlex, CORE, SSRN and the regional "
                        "universities -- ASUE and YSU in Yerevan, WIUT and the University of "
                        "World Economy in Tashkent, AUCA and UCA", layer="academic",
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.ysu.am",
               "https://wiut.uz", "https://www.auca.kg", "https://ucentralasia.org/research"),
        queries=("remittances exchange rate Armenia", "sanctions circumvention Central Asia",
                 "re-export trade diversion Russia", "Dutch disease remittances Tajikistan",
                 "gold mining Uzbekistan economy", "денежные переводы и обменный курс",
                 "миграция и экономика Центральной Азии"),
        languages=("en", "ru", "hy"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the remittance-and-real-exchange-rate literature written in the region is the "
              "mechanism source for CCA-B; every paper is a hypothesis until the desk "
              "reproduces it on its own tape"),
    source_class(
        "cca_area_studies", "The area-studies and policy-research ground: CABAR.asia, the "
                            "Caucasus Analytical Digest, Central Asian Survey, the Carnegie and "
                            "Chatham House regional programmes, KSE Institute's trade work",
        layer="academic",
        roots=("https://cabar.asia", "https://css.ethz.ch/en/publications/cad.html",
               "https://kse.ua/kse-institute/", "https://carnegieendowment.org"),
        queries=("санкции обход Центральная Азия", "реэкспорт подсанкционных товаров",
                 "миграция и денежные переводы", "Кыргызстан реэкспорт золота",
                 "Armenia relocation shock 2022", "parallel imports Russia Central Asia"),
        languages=("ru", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms; mostly open",
        notes="KSE Institute and the EU's own circumvention reporting publish COMMODITY-LEVEL "
              "mirror gaps, which is the closest thing to a ready-made measurement of this "
              "pack's central mechanism -- and therefore exactly the claim the desk must "
              "reproduce rather than adopt"),
    # ---- practitioner
    source_class(
        "cca_bank_research", "Bank and brokerage research published openly: Ameriabank and "
                             "Ardshinbank macro notes, Uzbek bank and capital-market research, "
                             "the EDB's macro reviews and the regional consultancies",
        layer="practitioner",
        roots=("https://ameriabank.am/en/research", "https://www.ardshinbank.am",
               "https://eabr.org/analytics/", "https://www.uzdaily.uz"),
        queries=("տոկոսադրույքի կանխատեսում", "դրամի փոխարժեքի կանխատեսում",
                 "so'm kursi prognozi", "прогноз курса сома", "макрообзор ЦА",
                 "инфляция прогноз", "ставка рефинансирования прогноз"),
        languages=("hy", "uz", "ru", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free notes; some behind registration",
        notes="the only stated pre-decision expectation in any of the five; kept as the "
              "EXPECTATION a surprise is measured against and never as a view the desk adopts"),
    source_class(
        "cca_logistics_practitioners", "The corridor's actual practitioners: customs brokers, "
                                       "freight forwarders, the Middle Corridor operators and "
                                       "the trucking and rail trade press", layer="practitioner",
        roots=("https://www.middlecorridor.com", "https://logirus.ru",
               "https://www.railfreight.com", "https://kazlogistics.kz"),
        queries=("транзит через Верхний Ларс", "очередь на границе", "Средний коридор",
                 "тарифы на перевозку", "таможенное оформление реэкспорт",
                 "контейнерные перевозки Китай Центральная Азия"),
        languages=("ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THE CHEAPEST LEADING INDICATOR IN THIS PACK. A border queue, a rate change or a "
              "refused consignment is reported by the people it happens to WEEKS before it "
              "appears in a customs table"),
    source_class(
        "cca_licensed_assessments", "The price-reporting agencies: gas border-price and LNG "
                                    "assessments, copper concentrate treatment charges and "
                                    "aluminium premia (Argus, ICIS, Fastmarkets, CRU)",
        layer="practitioner",
        roots=("https://www.argusmedia.com", "https://www.icis.com",
               "https://www.fastmarkets.com"),
        queries=("Central Asia gas border price assessment", "copper concentrate TC RC",
                 "aluminium P1020 premium CIS", "оценка цены газа на границе"),
        languages=("en", "ru"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="LICENSED -- terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED AND NEVER SCRAPED. The Turkmen border gas price and the concentrate "
              "treatment charge both live behind these terms, so the pack measures the CHINESE "
              "CUSTOMS unit value and the exchange-quoted metal instead and says that the "
              "assessment leg is UNMEASURED -- omitting the source would lose the knowledge "
              "that the ground exists"),
    # ---- retail ecology
    source_class(
        "cca_retail_forums", "The regional retail ground: Armenian and Central Asian Facebook "
                             "and Telegram rate groups, forum.uz, diesel.elcat.kg, the "
                             "country subreddits and the YouTube gold-and-dollar channels",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/armenia/", "https://www.reddit.com/r/Uzbekistan/",
               "https://diesel.elcat.kg/index.php?showforum=87",
               "https://t.me/s/kurs_valyut_uzbekistan"),
        queries=("դոլարի փոխարժեք այսօր", "ոսկու գին Երևանում", "dollar kursi bugun",
                 "доллар курси бугун", "доллар курсу бүгүн", "нархи доллар имрӯз",
                 "где поменять доллары", "чёрный курс"),
        languages=("hy", "uz", "ky", "tg", "ru"), access_label="PUBLIC_SOCIAL",
        credibility="FRINGE", predictive_state="UNTESTED",
        licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE, but it is the ONLY place the "
              "TAJIK AND TURKMEN PARALLEL RATES are quoted at all -- a number that exists in no "
              "official series anywhere, and the state variable of CCA-TJ-B and CCA-TM-B"),
    source_class(
        "cca_forex_sellers", "Russian-, Uzbek- and Armenian-language 'forex' signal sellers, "
                             "prop-firm affiliates and gold-trading channels targeting the "
                             "region on Telegram and YouTube", layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=форекс+Узбекистан",
               "https://t.me/s/forex_uzbekistan"),
        queries=("форекс Узбекистан", "trading signallari", "олтин савдоси", "форекс Кыргызстан",
                 "signal guruh", "бесплатные сигналы форекс", "пропфирма"),
        languages=("ru", "uz", "hy"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="LARGELY UNLICENSED and advertised anyway: none of the five has a retail CFD "
              "regime worth the name, so this measures an offshore retail base rather than a "
              "regulated flow. Kept because the XAUUSD stop clusters it advertises are a real "
              "microstructure observable and because it dates the region's retail gold manias"),
    # ---- app ecosystem
    source_class(
        "cca_transfer_rails", "THE CORRIDOR'S PLUMBING: the money-transfer systems and wallets "
                              "the flow physically moves through -- Korona Pay, Unistream, "
                              "Idram and Telcell in Armenia, Click, Payme, Humo and Uzcard in "
                              "Uzbekistan, Elsom and MBank in Kyrgyzstan, Alif in Tajikistan",
        layer="app_ecosystem",
        roots=("https://koronapay.com", "https://idram.am", "https://telcell.am",
               "https://click.uz", "https://payme.uz", "https://mbank.kg", "https://alif.tj"),
        queries=("pul o'tkazmasi komissiya", "пул ўтказма комиссия", "акча которуу комиссия",
                 "интиқоли пул аз Русия", "փոխանցում Ռուսաստանից", "перевод из России комиссия",
                 "лимит перевода", "курс перевода"),
        languages=("hy", "uz", "ky", "tg", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public app stores and operator pages",
        notes="THE RAIL IS THE MECHANISM. A transfer operator's published fee, limit and "
              "corridor list changes BEFORE the central bank's monthly series does, and a "
              "corridor being switched off (a system losing its Russian leg) is a dated, public "
              "event visible on the operator's own page the day it happens"),
    source_class(
        "cca_rate_aggregators", "The rate-aggregator apps and sites that publish the SECOND "
                                "price: rate.am, kurs.kg, the Uzbek bank-rate aggregators and "
                                "the Tajik and Turkmen informal-rate trackers",
        layer="app_ecosystem",
        roots=("https://rate.am", "https://www.kurs.kg", "https://bank.uz/uz/currency",
               "https://banki.tj"),
        queries=("դոլար գնում վաճառք բանկեր", "banklar valyuta kurslari",
                 "банклар валюта курслари", "банктардын курсу", "қурби бонкҳо",
                 "курсы валют банки", "обменный пункт курс"),
        languages=("hy", "uz", "ky", "tg", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public; some pages overwrite in place",
        notes="rate.am publishes every Armenian bank's cash bid and offer intraday, which is a "
              "near-real-time read on dram demand that leads the CBA's monthly series; the "
              "pages OVERWRITE IN PLACE, so the only vintage is a daily crawl"),
    # ---- media
    source_class(
        "cca_media_am", "The Armenian press: Civilnet, Hetq, Armenpress, News.am, Ampop and "
                        "the Armenian-language business pages", layer="media",
        roots=("https://www.civilnet.am", "https://hetq.am", "https://armenpress.am",
               "https://ampop.am"),
        queries=("դրամի արժևորում", "ՌԴ-ից փոխանցումներ", "վերաարտահանում", "ոսկու արտահանում",
                 "տնտեսական աճ", "Կենտրոնական բանկի որոշում", "Լաչինի միջանցք",
                 "ռելոկացիա ընկերություններ"),
        languages=("hy", "en", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Hetq is an investigative outlet that has published customs-level re-export "
              "reporting the official tables aggregate away; Civilnet carries the dated policy "
              "events hours before the CBA's own page updates"),
    source_class(
        "cca_media_ca", "The Central Asian press: Gazeta.uz, Kun.uz, Spot.uz, AKIpress, Kabar, "
                        "24.kg, Asia-Plus and Avesta", layer="media",
        roots=("https://www.gazeta.uz", "https://kun.uz", "https://akipress.com",
               "https://kabar.kg", "https://asiaplustj.info", "https://24.kg"),
        queries=("so'm kursi", "сўм курси", "oltin eksporti", "олтин экспорти", "реэкспорт",
                 "акча которуулар", "интиқоли пул аз муҳоҷират", "курс доллара",
                 "хлопковый кластер", "газ импорт"),
        languages=("uz", "ky", "tg", "ru", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Gazeta.uz and Asia-Plus report the SUBSIDISED and administered prices -- gas "
              "limits, power cuts, flour and fuel -- that the official statistics smooth; they "
              "are also where a decree is reported on the day it is signed"),
    source_class(
        "cca_media_regional", "The regional and exile press: Eurasianet, the RFE/RL services "
                              "(Azatutyun, Ozodlik, Azattyk, Ozodi, Azatlyk) and the Turkmen "
                              "exile outlets turkmen.news and Chronicles of Turkmenistan",
        layer="media",
        roots=("https://eurasianet.org", "https://www.azatutyun.am", "https://rus.ozodi.org",
               "https://www.azattyk.org", "https://turkmen.news", "https://www.hronikatm.com"),
        queries=("реэкспорт санкционных товаров", "чёрный курс маната", "дефицит валюты",
                 "очереди за наличными", "газ Китаю Туркменистан", "gara bazar",
                 "манат курсы", "нархи асъор дар бозори сиёҳ"),
        languages=("ru", "tk", "tg", "ky", "hy", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THE ONLY GROUND THAT QUOTES THE TURKMEN PARALLEL RATE. turkmen.news and the "
              "Chronicles publish informal-market rates and cash-queue reporting for a country "
              "whose central bank publishes a constant -- kept as the substitute named in "
              "NO_LAWFUL_GROUND, and never treated as a statistical series"),
    # ---- archive
    source_class(
        "cca_archive_web", "The web archive as the only vintage: Wayback and archive.today "
                           "crawls of cbt.tm, stat.gov.tm, nbt.tj, rate.am and the statistics "
                           "portals that overwrite in place", layer="archive",
        roots=("https://web.archive.org/web/*/cbt.tm*", "https://web.archive.org/web/*/nbt.tj*",
               "https://web.archive.org/web/*/rate.am*", "https://archive.ph"),
        queries=("cbt.tm archive", "stat.gov.tm snapshot", "rate.am historical",
                 "архив курса валют", "снимок страницы"),
        languages=("en", "ru", "tk", "tg"), access_label="PUBLIC_ARCHIVE",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="archive terms",
        notes="HALF THE REGION'S PAGES PUBLISH TODAY AND KEEP NO HISTORY. Where that is true "
              "the point-in-time vintage exists only in an archive crawl, and a cell compiled "
              "on an un-archived month is UNMEASURED rather than assumed"),
    source_class(
        "cca_archive_documentary", "The documentary archive: the national libraries of Armenia "
                                   "and Uzbekistan, the Soviet-era statistical yearbooks, the "
                                   "lex.uz historical legal corpus and arlis.am's act history",
        layer="archive",
        roots=("https://nla.am", "https://natlib.uz", "https://lex.uz", "https://www.arlis.am"),
        queries=("статистический ежегодник", "архив нормативных актов", "նախկին խմբագրություն",
                 "qonun hujjatlari arxivi", "қонун ҳужжатлари архиви", "таърихи қонунгузорӣ"),
        languages=("hy", "uz", "tg", "ru"), access_label="PUBLIC_ARCHIVE",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="lex.uz keeps the SUPERSEDED versions of an act with their effective dates, which "
              "is how the 2017 liberalisation and the end of the cotton state order are dated "
              "to a document rather than to a newspaper"),
    # ---- physical economy
    source_class(
        "cca_pipelines_power", "The physical energy plane: the Central Asia-China pipeline, "
                               "CASA-1000, the Vakhsh cascade and Rogun, the Uzbek gas balance "
                               "and the regional power system", layer="physical_economy",
        roots=("https://www.carecprogram.org", "https://www.casa-1000.org",
               "https://www.uzbekneftegaz.uz", "http://www.barqitojik.tj"),
        queries=("газопровод Центральная Азия Китай", "Рогунская ГЭС наполнение",
                 "лимит газа", "отключения электроэнергии", "gaz geçirijisi",
                 "неругоҳи барқии обӣ", "энергетический кризис зима"),
        languages=("ru", "tg", "tk", "uz", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ROGUN FILLING SCHEDULE IS A SUPPLY EVENT FOR ALUMINIUM: impounding water "
              "takes it away from generation, and TALCO's smelter is the load that gets cut "
              "first. The winter power deficit is a dated, reported, physical constraint"),
    source_class(
        "cca_freight_borders", "The physical trade plane: the Middle Corridor, Verkhniy Lars "
                               "and the Georgian-Russian crossing, the Dordoi and Kara-Suu "
                               "bazaars, Khorgos and the Kazakh-Chinese crossings",
        layer="physical_economy",
        roots=("https://www.middlecorridor.com", "https://kaztransport.kz",
               "https://www.railfreight.com/corridors/"),
        queries=("Верхний Ларс очередь", "Дордой оборот", "Кара-Суу базар",
                 "Хоргос контейнеры", "транзитные перевозки", "Средний коридор объёмы"),
        languages=("ru", "ky", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A BAZAAR IS A TRADE STATISTIC. Dordoi and Kara-Suu are where Chinese goods are "
              "broken down and re-exported; their throughput and the Verkhniy Lars queue are "
              "physical counterparts to the customs tables and lead them by weeks"),
    source_class(
        "cca_mining_physical", "The physical mining plane: Muruntau and the Navoi complex, "
                               "Kumtor, Zangezur and Kajaran, TALCO's potlines, plus the USGS "
                               "Minerals Yearbook country chapters and the WGC's official "
                               "holdings tables", layer="physical_economy",
        roots=("https://www.usgs.gov/centers/national-minerals-information-center",
               "https://www.gold.org/goldhub/data/gold-reserves-by-country",
               "https://www.ngmk.uz", "https://www.kyrgyzaltyn.kg"),
        queries=("oltin ishlab chiqarish hajmi", "олтин ишлаб чиқариш", "Кумтөр өндүрүш көлөмү",
                 "պղնձի խտանյութի արտահանում", "истеҳсоли алюминий", "добыча золота",
                 "Muruntau production", "gold reserves by country"),
        languages=("uz", "ky", "hy", "tg", "ru", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="the USGS country chapters are the only INDEPENDENT estimate of Central Asian "
              "mine output, and the WGC's official-holdings table is the cross-check on the "
              "CBU's own gold reporting -- two sources disagreeing is a measurement"),
    # ---- source graph
    source_class(
        "cca_source_graph", "What the other nine cite: the OpenAlex citation graph, Comtrade's "
                            "reporter/partner pairs, the EU sanctions-envoy and KSE "
                            "circumvention reports and their reference lists, and the outbound "
                            "links of Eurasianet, CABAR and the exile press", layer="source_graph",
        roots=("https://api.openalex.org/works?filter=title.search:sanctions%20circumvention",
               "https://comtradeplus.un.org", "https://cabar.asia", "https://eurasianet.org"),
        queries=("цитируется по", "источник данных", "по данным таможни", "according to customs "
                 "data", "mirror statistics methodology", "հղում կատարելով", "manbaga ko'ra"),
        languages=("ru", "en", "hy", "uz"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public; OpenAlex CC0",
        notes="THE EXPANSION EDGE. Every circumvention report cites a customs table, a company "
              "register or a shipping record the desk has not read yet; following the citations "
              "is how this pack's source list grows without anybody guessing a new hostname"),
)

#: NO PACK-LEVEL LAYER IS BLANK. All ten are sourced REGIONALLY, which is the honest regional
#: statement -- and it is NOT the same as saying every jurisdiction is covered in every layer.
#: The per-jurisdiction holes are in `NO_LAWFUL_GROUND` below, with their substitutes.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSAL, PER JURISDICTION. Turkmenistan carries most of it and Tajikistan
#: carries some. Each row names the missing publication AND the lawful ground read instead, so
#: the absence is a plan rather than a shrug (L1.28a).
NO_LAWFUL_GROUND: tuple[dict[str, Any], ...] = (
    jurisdiction_absence(
        "tm", "official",
        reason="the State Statistics Committee publishes no machine-readable trade table, no "
               "monthly series and no levels -- growth percentages against an unpublished base "
               "are not data; the Central Bank publishes a rate fixed at 3.50 since 2015-01-01 "
               "and no auditable reserve series; the IMF's own Article IV data-provision annex "
               "records the gap",
        substitute="China's General Administration of Customs monthly natural-gas imports BY "
                   "ORIGIN, which give the Turkmen volume and value every month, plus UN "
                   "Comtrade mirror pulls from every partner that does report",
        substitute_root="http://stats.customs.gov.cn"),
    jurisdiction_absence(
        "tm", "institutional",
        reason="there is no exchange with a public tape, no clearer, no listed issuer, no "
               "industry association that publishes and no bank that discloses; the State "
               "Commodity and Raw Materials Exchange reports weekly summaries in the state "
               "press rather than data",
        substitute="CNPC's own project disclosures, the ADB/EBRD country assessments and the "
                   "IMF Article IV, all of which discuss Turkmen volumes from the outside",
        substitute_root="https://www.imf.org/en/Countries/TKM"),
    jurisdiction_absence(
        "tm", "academic",
        reason="there is no independent domestic academic economics literature and no "
               "university repository a crawler can reach; what exists is state-published",
        substitute="the external area-studies literature (Central Asian Survey, CABAR, the "
                   "Carnegie and Chatham House regional programmes) and the energy-market "
                   "literature on the Central Asia-China pipeline",
        substitute_root="https://cabar.asia"),
    jurisdiction_absence(
        "tm", "retail_ecology",
        reason="there is no domestic retail investment ecology at all: no brokerage, no margin "
               "product, no domestic forum that discusses prices, and the internet is filtered "
               "hard enough that a local retail conversation does not take place in the open",
        substitute="the EXILE ground -- turkmen.news and Chronicles of Turkmenistan -- which "
                   "carries informal-market rates and cash-queue reporting from correspondents; "
                   "registered as reporting, never as a statistical series",
        substitute_root="https://turkmen.news"),
    jurisdiction_absence(
        "tj", "institutional",
        reason="there is no securities exchange with a public tape, no listed domestic issuer "
               "and no published bank research; the one sovereign eurobond is the whole of the "
               "country's market-facing disclosure",
        substitute="the 2017 sovereign eurobond documentation and its subsequent IMF and World "
                   "Bank debt-sustainability analyses, plus the ADB country programme",
        substitute_root="https://www.imf.org/en/Countries/TJK"),
    jurisdiction_absence(
        "tj", "app_ecosystem",
        reason="the licensed-bureau (second) exchange rate that CCA-TJ-B is built on is NOT "
               "published by the NBT, by any aggregator with an API, or by any app -- it is "
               "quoted verbally at the bureau window",
        substitute="the media and retail layers: Asia-Plus and the Telegram rate channels "
                   "report the bureau rate, and the pack labels every such reading "
                   "PRESS_REPORTED and never promotes a cell compiled on one",
        substitute_root="https://asiaplustj.info"),
)


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def layer_terms() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    for sc in SOURCE_CLASSES:
        layer = str(sc.get("layer") or "")
        if layer not in out:
            continue
        for q in sc.get("queries", ()):
            if q not in out[layer]:
                out[layer].append(q)
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    holes: dict[str, list[str]] = {}
    for row in NO_LAWFUL_GROUND:
        holes.setdefault(str(row["jurisdiction"]), []).append(str(row["layer"]))
    return {"code": CODE, "layer_counts": counts,
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
            "jurisdiction_holes": {k: sorted(v) for k, v in sorted(holes.items())},
            "jurisdictions_with_full_ground": sorted(set(JURISDICTIONS) - set(holes)),
            "rule": "ten layers, each carrying a regional source or named ABSENT with a reason; "
                    "PER-JURISDICTION holes are declared separately in NO_LAWFUL_GROUND with "
                    "the lawful substitute that is read instead, because a regional coverage "
                    "number that averages Turkmenistan into Armenia hides the one country the "
                    "desk cannot see; fringe and unreliable PUBLIC material is kept at low "
                    "weight and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer. Every
#: layer carries at least three, and no layer is English-only: an English query on a native
#: ground reads the English corner of it and reports the corner as the ground.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("դրամական փոխանցումներ ըստ երկրների", "մաքսային վիճակագրություն արտահանում",
                 "oltin zaxiralari oylik", "олтин захиралари ойлик", "валюта аукциону жыйынтыгы",
                 "қурби расмии асъор", "manadyň resmi hümmeti", "土库曼斯坦 天然气 进口 海关",
                 "таможенная статистика реэкспорт"),
    "institutional": ("birja savdolari paxta tolasi", "биржа савдолари пахта толаси",
                      "աճուրդի արդյունքներ", "Кумтөр өндүрүш отчёт", "eurobond prospectus "
                      "Uzbekistan SOE", "истеҳсоли алюминий ТАЛКО"),
    "academic": ("remittances real exchange rate Armenia", "денежные переводы и курс",
                 "sanctions circumvention Central Asia trade", "миграция Центральная Азия "
                 "экономика", "oltin qazib olish iqtisodiyot", "Dutch disease Tajikistan"),
    "practitioner": ("прогноз курса сома", "տոկոսադրույքի կանխատեսում", "очередь Верхний Ларс",
                     "тарифы перевозка Китай ЦА", "Средний коридор объёмы",
                     "so'm kursi prognozi"),
    "retail_ecology": ("դոլարի փոխարժեք այսօր", "dollar kursi bugun", "доллар курсу бүгүн",
                       "нархи доллар дар бозор", "gara bazarda dollar", "чёрный курс маната",
                       "ոսկու գին Երևանում"),
    "app_ecosystem": ("перевод из России комиссия", "pul o'tkazmasi limiti",
                      "пул ўтказма лимити", "акча которуу комиссия", "интиқоли пул аз Русия",
                      "փոխանցում Ռուսաստանից միջնորդավճար", "banklar valyuta kurslari"),
    "media": ("դրամի արժևորում պատճառները", "реэкспорт в Россию рост", "oltin eksporti o'sdi",
              "олтин экспорти ўсди", "алтын реэкспорт өстү", "интиқоли пул афзоиш ёфт",
              "газ Туркменистана Китаю объёмы"),
    "archive": ("статистический ежегодник Узбекистан", "архив курса валют Таджикистан",
                "qonun hujjatlari eski tahriri", "նախկին խմբագրություն որոշում",
                "cbt.tm archived snapshot", "архив stat.gov.tm"),
    "physical_economy": ("Рогунская ГЭС наполнение водохранилища", "лимит газа зима",
                         "Дордой оборот товаров", "Кара-Суу базар реэкспорт",
                         "gaz geçirijisiniň kuwwaty", "oltin qazib olish hajmi Muruntov",
                         "պղնձի խտանյութի բեռնափոխադրում"),
    "source_graph": ("по данным таможенной статистики", "источник: Comtrade",
                     "հղում կատարելով մաքսային տվյալներին", "manbaga ko'ra bojxona",
                     "mirror statistics methodology customs", "цитируется по отчёту KSE"),
}


# --------------------------------------------------------------------------- datasets
#: EVERY ROW CARRIES THE TWELVE FIELDS AND NOTHING ELSE -- `DatasetRow` has no `notes` slot, so
#: a thirteenth key would be DROPPED by the framework's coercion rather than folded away. What a
#: row has to say about itself lives in `how_to_fetch`, which is also the only field a collector
#: can act on: a portal name, a series, a path, and where the vintage comes from.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CBA monthly non-commercial money transfers by source country (Armenia)",
     "source": "Central Bank of Armenia", "coverage": "1998 onward, monthly, by country",
     "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "one routine revision the following month; the 2022 level shift is not a "
                  "revision and must not be smoothed",
     "licence": "free, public", "history_from": "1998-01", "pit_feasible": True,
     "assets": ("USDRUB", "EURRUB", "USDTRY", "XAUUSD"),
     "mechanism_families": ("seasonal_flow", "external_balance", "release_surprise"),
     "how_to_fetch": "cba.am statistics -> external sector -> non-commercial money transfers by "
                     "country; the Excel workbook carries inflow and outflow by origin and by "
                     "currency, and the Russia column is the corridor's own series"},
    {"name": "Armstat monthly external trade by partner and commodity chapter (Armenia)",
     "source": "Statistical Committee of the Republic of Armenia",
     "coverage": "2000 onward; HS chapter detail from 2010",
     "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "cumulative restatement within the year", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("USDRUB", "USDTRY", "XAUUSD", "XCUUSD"),
     "mechanism_families": ("trade_cycle", "transfer", "regime_break"),
     "how_to_fetch": "armstat.am external trade bulletins, monthly PDF plus the Excel annexes; "
                     "the chapter split (85 electrical machinery, 87 vehicles, 71 precious "
                     "metals) is where a re-export is separated from a real export, and the "
                     "within-year restatements are why this is NOT_PIT_SAFE without a crawl"},
    {"name": "CBA daily official exchange rate and the published FX interventions (Armenia)",
     "source": "Central Bank of Armenia", "coverage": "1993 onward daily",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1993-01", "pit_feasible": True,
     "assets": ("USDRUB", "USDTRY", "XAUUSD"),
     "mechanism_families": ("fixing", "intervention", "regime_break"),
     "how_to_fetch": "cba.am exchange rates API and the intervention statistics page; the 2022 "
                     "appreciation is a ~20% move visible in this one series and is the pack's "
                     "largest single identified flow event"},
    {"name": "Armenian precious-metal trade line: the gold re-export spike (Armenia)",
     "source": "Armstat and the State Revenue Committee customs tables",
     "coverage": "2015 onward at HS chapter 71 detail", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "restated within the year",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("XAUUSD", "USDRUB"),
     "mechanism_families": ("transfer", "trade_cycle", "regime_break"),
     "how_to_fetch": "armstat external trade, HS chapter 71, by partner; a country with no gold "
                     "mine of that size showing a chapter-71 export line of that size IS the "
                     "measurement -- cross-check against the UAE and Russia mirror legs before "
                     "any cell is compiled"},
    {"name": "Armenian copper and molybdenum concentrate export volumes (Zangezur)",
     "source": "Armstat trade tables and the ZCMC/Armenian mining disclosures",
     "coverage": "2010 onward", "frequency": "monthly (volumes) / annual (company)",
     "publication_lag_days": 45.0, "revisions": "annual reconciliation",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XCUUSD",),
     "mechanism_families": ("corporate_flow", "physical_supply"),
     "how_to_fetch": "armstat HS chapter 26 (ores, slag and ash) by partner, cross-read against "
                     "the company's own production statements; CONCENTRATE not cathode, so the "
                     "transmission is into treatment charges and concentrate availability"},
    {"name": "CBU monthly international reserves with the gold holding in tonnes and value",
     "source": "Central Bank of Uzbekistan", "coverage": "2005 onward, monthly",
     "frequency": "monthly", "publication_lag_days": 7.0,
     "revisions": "tonnage occasionally restated", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("XAUUSD",),
     "mechanism_families": ("official_flow", "physical_supply", "release_surprise"),
     "how_to_fetch": "cbu.uz statistics -> gold and foreign exchange reserves; BOTH the tonnage "
                     "and the value are published, which is what lets an OPERATION be separated "
                     "from a PRICE move -- most sovereigns publish only the value and the two "
                     "are then inseparable"},
    {"name": "CBU policy rate decisions and the quarterly monetary policy review (Uzbekistan)",
     "source": "Central Bank of Uzbekistan",
     "coverage": "2017 onward under the post-liberalisation framework",
     "frequency": "7-8 per year", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2017-09", "pit_feasible": True,
     "assets": ("XAUUSD", "USDRUB"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "cbu.uz monetary policy -> decisions; the calendar is published a year "
                     "ahead and the DATES ARE NOT TYPED INTO THIS PACK -- the collector stamps "
                     "them from the press release, and until it does the event arm is UNMEASURED"},
    {"name": "Stat.uz monthly foreign trade by partner and commodity (Uzbekistan)",
     "source": "Statistics Agency of the Republic of Uzbekistan", "coverage": "2010 onward",
     "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "restated within the year; the gold line has been reclassified between "
                  "vintages, which is a trap and not a revision",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XAUUSD", "COTTON", "USDCNH", "USDRUB"),
     "mechanism_families": ("trade_cycle", "transfer", "regime_break"),
     "how_to_fetch": "stat.uz open data -> foreign trade; read in BOTH scripts, because the "
                     "Cyrillic pages carry series the Latin ones do not, and hold the vintage: "
                     "Uzbekistan has reported gold inside and outside the headline export total "
                     "in different years"},
    {"name": "UzEX cotton fibre auction results (Uzbekistan)",
     "source": "Uzbek Republican Commodity Exchange", "coverage": "2019 onward",
     "frequency": "per auction, clustered October to March", "publication_lag_days": 1.0,
     "revisions": "never", "licence": "free, public", "history_from": "2019-10",
     "pit_feasible": True, "assets": ("COTTON",),
     "mechanism_families": ("auction", "physical_supply", "calendar_settlement"),
     "how_to_fetch": "uzex.uz exchange trades -> cotton fibre; lot volume, grade and clearing "
                     "price per session. THE AUCTION IS THE CROP REACHING THE MARKET and its "
                     "season is the marketing year, which is the calendar CCA-UZ-B conditions on"},
    {"name": "Uzbek natural gas balance: production, export to China, import from Russia",
     "source": "Uzbekneftegaz, stat.uz and the Chinese customs mirror",
     "coverage": "2010 onward", "frequency": "monthly / quarterly",
     "publication_lag_days": 45.0, "revisions": "frequent and large",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XNGUSD", "USDCNH"),
     "mechanism_families": ("physical_supply", "regime_break", "trade_cycle"),
     "how_to_fetch": "stat.uz and Uzbekneftegaz for the domestic side, China customs for the "
                     "export leg, and the Russian side for the import leg; THE SIGN OF THIS "
                     "BALANCE FLIPPED -- Uzbekistan went from exporting gas to importing it, "
                     "and a series that pools across that is measuring two different countries"},
    {"name": "NBKR FX auction results: date, direction, volume and weighted rate (Kyrgyzstan)",
     "source": "National Bank of the Kyrgyz Republic", "coverage": "2010 onward",
     "frequency": "per auction, irregular", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("USDRUB", "XAUUSD"),
     "mechanism_families": ("intervention", "official_flow", "event_reaction"),
     "how_to_fetch": "nbkr.kg -> monetary policy operations -> FX interventions; published the "
                     "SAME DAY with the size, which makes it the only point-in-time "
                     "intervention series in this pack"},
    {"name": "Stat.kg monthly foreign trade including the gold export line (Kyrgyzstan)",
     "source": "National Statistical Committee of the Kyrgyz Republic",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "restated within the year", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": False,
     "assets": ("XAUUSD", "USDRUB", "USDCNH"),
     "mechanism_families": ("trade_cycle", "transfer", "physical_supply"),
     "how_to_fetch": "stat.kg foreign trade bulletins plus the customs service tables; the "
                     "2022-2023 chapter-71 volumes are far larger than Kumtor's output, which "
                     "is the arithmetic that makes the re-export visible without any inference"},
    {"name": "Kumtor mine production and the Kyrgyzaltyn refining series (Kyrgyzstan)",
     "source": "Kyrgyzaltyn and the state's periodic production disclosures",
     "coverage": "1997 onward; the disclosure format BREAKS at the 2021 state takeover",
     "frequency": "quarterly / annual", "publication_lag_days": 60.0,
     "revisions": "the pre-2021 operator series and the post-2021 state series are not the "
                  "same measurement and must not be spliced",
     "licence": "free, public", "history_from": "1997-01", "pit_feasible": False,
     "assets": ("XAUUSD",),
     "mechanism_families": ("physical_supply", "regime_break", "corporate_flow"),
     "how_to_fetch": "kyrgyzaltyn.kg and the government's releases after 2021; for the pre-2021 "
                     "half, the former operator's audited quarterly production reports -- "
                     "WHICH IS WHY THE SPLICE IS THE PROBLEM: one half is audited and the other "
                     "is announced"},
    {"name": "NBT daily official rate and quarterly remittance statistics (Tajikistan)",
     "source": "National Bank of Tajikistan", "coverage": "2000 onward",
     "frequency": "daily / quarterly", "publication_lag_days": 60.0,
     "revisions": "quarterly remittance series revised", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XALUSD", "USDRUB"),
     "mechanism_families": ("fixing", "seasonal_flow", "external_balance"),
     "how_to_fetch": "nbt.tj statistical bulletin; the official rate is daily and the "
                     "remittance series is quarterly, so the two cannot be joined at a monthly "
                     "frequency without an interpolation the pack refuses to make"},
    {"name": "TALCO primary aluminium production (Tajikistan)",
     "source": "TALCO, the Agency on Statistics and the USGS Minerals Yearbook",
     "coverage": "1995 onward, annual with partial monthly industrial output",
     "frequency": "annual / monthly industrial index", "publication_lag_days": 90.0,
     "revisions": "USGS and domestic figures diverge in several years",
     "licence": "free, public", "history_from": "1995-01", "pit_feasible": False,
     "assets": ("XALUSD",),
     "mechanism_families": ("physical_supply", "corporate_flow"),
     "how_to_fetch": "talco.com.tj plus stat.tj industrial output plus the USGS Tajikistan "
                     "chapter; TWO SOURCES DISAGREEING IS A MEASUREMENT -- the divergence "
                     "itself dates the years the domestic figure was managed"},
    {"name": "Rogun filling schedule and the Vakhsh cascade winter power balance (Tajikistan)",
     "source": "Barqi Tojik, the Rogun project office, the World Bank assessments and CASA-1000",
     "coverage": "2016 onward", "frequency": "irregular, dated announcements",
     "publication_lag_days": 30.0, "revisions": "schedules slip and are re-announced",
     "licence": "free, public", "history_from": "2016-01", "pit_feasible": False,
     "assets": ("XALUSD",),
     "mechanism_families": ("physical_supply", "administered_price", "regime_break"),
     "how_to_fetch": "the project office and Barqi Tojik announcements plus the winter "
                     "load-shedding reports in Asia-Plus; IMPOUNDING WATER IS TAKING IT AWAY "
                     "FROM GENERATION, and the smelter is the load that is cut first, so a "
                     "filling campaign is an aluminium supply event with a date on it"},
    {"name": "China customs monthly natural gas imports by origin (the Turkmen mirror)",
     "source": "General Administration of Customs of the People's Republic of China",
     "coverage": "2010 onward, monthly, by origin, in volume and value",
     "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "minor; the detailed tables follow the headline by about a fortnight",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XNGUSD", "USDCNH"),
     "mechanism_families": ("mirror_statistics", "physical_supply", "trade_cycle"),
     "how_to_fetch": "stats.customs.gov.cn monthly detailed tables, HS 2711 by origin country; "
                     "query in Chinese. THIS IS THE ONLY LAWFUL QUANTIFIED READ ON TURKMEN GAS "
                     "ANYWHERE, and the implied unit value is the border price nobody publishes"},
    {"name": "UN Comtrade mirror pulls: EU, Turkey and China exports to the five",
     "source": "UN Comtrade, Eurostat Comext and the Turkish statistical institute",
     "coverage": "2000 onward, monthly and annual", "frequency": "monthly as reporters file",
     "publication_lag_days": 60.0,
     "revisions": "REPORTERS BACKFILL; today's database is not the database that existed then",
     "licence": "free with an API key; rate-capped", "history_from": "2000-01",
     "pit_feasible": False,
     "assets": ("USDRUB", "USDTRY", "USDCNH", "USDINR"),
     "mechanism_families": ("mirror_statistics", "transfer", "regime_break"),
     "how_to_fetch": "comtradeplus.un.org API by reporter/partner/HS, plus Eurostat Comext for "
                     "the EU leg; THE LARGEST PIT TRAP IN THIS PACK -- every mirror cell stays "
                     "NOT_PIT_SAFE until a stamped vintage of BOTH halves is held"},
    {"name": "Turkmen parallel-market exchange rate as reported by the exile press",
     "source": "turkmen.news and Chronicles of Turkmenistan correspondent reporting",
     "coverage": "2016 onward, irregular", "frequency": "irregular, several times a month",
     "publication_lag_days": 3.0, "revisions": "none; each reading is a separate observation",
     "licence": "publisher terms; public reporting", "history_from": "2016-01",
     "pit_feasible": False,
     "assets": ("XNGUSD", "USDCNH"),
     "mechanism_families": ("parallel_market", "administered_price"),
     "how_to_fetch": "the outlets' own currency tags, read as PRESS_REPORTED observations with "
                     "the reporting date stamped; this is NOT a statistical series and no cell "
                     "compiled on it may ever be promoted -- it is the substitute named in "
                     "NO_LAWFUL_GROUND and it is labelled as such on every row"},
    {"name": "EAEU and EDB intra-union trade and remittance corridor statistics",
     "source": "Eurasian Economic Commission and the Eurasian Development Bank",
     "coverage": "2015 onward for Armenia and Kyrgyzstan", "frequency": "monthly / quarterly",
     "publication_lag_days": 60.0, "revisions": "quarterly restatement",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("USDRUB", "EURRUB"),
     "mechanism_families": ("trade_cycle", "transfer", "external_balance"),
     "how_to_fetch": "eec.eaeunion.org statistics and eabr.org analytics; ARMENIA AND "
                     "KYRGYZSTAN TRADE WITH RUSSIA ACROSS NO CUSTOMS BORDER, so their Russia "
                     "trade is measured here rather than in a customs declaration -- which is "
                     "both why they are the corridor's preferred routes and why their numbers "
                     "are not comparable with Uzbekistan's"},
    {"name": "World Gold Council official gold holdings by country (the sovereign cross-check)",
     "source": "World Gold Council, from IMF IFS reporting",
     "coverage": "2000 onward, monthly by country", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "restated as countries report late",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XAUUSD",),
     "mechanism_families": ("official_flow", "mirror_statistics"),
     "how_to_fetch": "gold.org goldhub gold-reserves-by-country; read AGAINST the CBU's own "
                     "monthly tonnage -- when the two disagree the disagreement is the finding, "
                     "and neither is automatically the right one"},
    {"name": "USGS Minerals Yearbook country chapters for the five",
     "source": "United States Geological Survey",
     "coverage": "1994 onward, annual, by commodity and country",
     "frequency": "annual", "publication_lag_days": 540.0,
     "revisions": "chapters are revised years later", "licence": "free, public (US government)",
     "history_from": "1994-01", "pit_feasible": False,
     "assets": ("XAUUSD", "XCUUSD", "XALUSD"),
     "mechanism_families": ("physical_supply", "mirror_statistics"),
     "how_to_fetch": "usgs.gov national minerals information center, country chapters for "
                     "Armenia, Kyrgyzstan, Tajikistan, Turkmenistan and Uzbekistan; the ONLY "
                     "independent estimate of Central Asian mine output, and eighteen months "
                     "late, so it conditions an era and never a month"},
)


# --------------------------------------------------------------------------- actors
#: TWENTY-FIVE ACTORS, AND EVERY JURISDICTION OWES AT LEAST THREE OF ITS OWN. An actor is only
#: a research object when all eleven fields can be said about it: what it holds, what it is
#: FORCED to do, when, what it knows, what binds it, which instruments it reaches, who it faces,
#: what it leaves visible, how large the impact is, how long it lasts, and WHAT WOULD PROVE THE
#: WHOLE STORY WRONG. An actor with a blank falsifier is a story with a flag on it.
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- Armenia
    {"name": "The Central Bank of Armenia Board and its FX desk",
     "holds": "the refinancing rate, the daily official rate and the reserves that back a "
              "managed float in an economy where cross-border transfers are a large share of GDP",
     "forced_to": ("decide at eight scheduled Board meetings a year and publish the same day",
                   "publish an official exchange rate every business day",
                   "absorb or resist a transfer inflow it did not choose and cannot refuse"),
     "when": "the Board decision in the Yerevan morning (about 10:30 UTC); the rate each "
             "business day; interventions by auction when the inflow overwhelms the market",
     "information": ("the monthly transfer series before it is published",
                     "the banks' end-of-day FX positions",
                     "the deposit-dollarisation ratio in real time",
                     "the relocated companies' payroll conversion demand"),
     "constraints": ("an inflation target it must hit while a flow appreciates the currency",
                     "reserves that are small against a flow of this size",
                     "a political economy in which a strong dram hurts every exporter",
                     "no capital controls to lean on"),
     "instruments": ("USDRUB", "USDTRY", "XAUUSD"),
     "counterparties": ("the commercial banks at the auction", "the Ministry of Finance",
                        "the IMF under Article IV", "the transfer operators' settlement banks"),
     "observables": ("the Board decision and its statement", "the daily official rate",
                     "the published intervention volumes", "the monthly transfer release"),
     "impact": "the dram's 2022 move was about 20% and the Board did not stop it; the "
               "executable expression is the rouble leg the transfers arrive in and the lira "
               "leg the region's stress is priced in",
     "persistence": "the appreciation held for years rather than reverting, which is what "
                    "distinguishes a flow regime from an overshoot",
     "falsifier": "the transfer series carries no information about the rouble or lira legs "
                  "beyond what the rouble tape already carries, measured with the same state "
                  "built on a block-shuffled transfer series",
     "notes": "the one central bank in this pack whose decisions and whose central flow series "
              "are BOTH public and monthly"},
    {"name": "The Russian-origin remitter and the Armenian receiving household",
     "holds": "a Russian wage or a relocated savings balance, converted into dram at a bank "
              "window or inside a transfer app",
     "forced_to": ("send around the Russian pay cycle, which clusters at the month end",
                   "convert at whatever rate the receiving bank quotes that day",
                   "use whichever corridor is still open after each round of de-risking"),
     "when": "the last and first business days of each month; and in bursts on the announcement "
             "of any measure that threatens the corridor",
     "information": ("which operators are still working, before any statistic says so",
                     "the cash bid-offer at the Yerevan bank windows, intraday"),
     "constraints": ("transfer limits and fees set by the operator",
                     "a receiving bank's compliance appetite",
                     "the sending bank's exposure to secondary sanctions since 2023-12-22"),
     "instruments": ("USDRUB", "EURRUB", "XAUUSD"),
     "counterparties": ("Korona Pay, Unistream and the card rails", "the Armenian banks",
                        "the informal cash couriers when a rail closes"),
     "observables": ("the CBA monthly transfers by origin",
                     "the operators' published fees, limits and corridor lists",
                     "the aggregator cash spreads at rate.am", "the deposit-dollarisation ratio"),
     "impact": "the aggregate is large enough to appreciate a currency by a fifth in a year; "
               "the marginal month is a scheduled, dated FX demand",
     "persistence": "the seasonal shape repeats every month; the 2022 level shift did not "
                    "revert",
     "falsifier": "month-end windows in the four remittance jurisdictions behave no differently "
                  "from mid-month windows on the same instruments, matched by weekday and hour",
     "notes": "THE PACK'S CENTRAL HOUSEHOLD ACTOR; the flow is published by origin, which is "
              "rare enough that the identification problem is unusually small here"},
    {"name": "The Armenian re-export declarant -- the corridor's trading company",
     "holds": "inventory bought in the EU, Turkey, China or the UAE and sold onward to a "
              "Russian buyer, financed on short credit and thin margin",
     "forced_to": ("move inventory before a rule change strands it",
                   "re-route the moment a bank refuses the payment",
                   "declare something, because Armenia is inside the EAEU customs union and the "
                   "onward leg crosses no customs border"),
     "when": "continuously, with bursts in the weeks after each sanctions package and each "
             "correspondent-bank withdrawal",
     "information": ("which HS codes are being refused this week",
                     "which correspondent banks still clear the payment",
                     "the border queue at Verkhniy Lars before it is reported"),
     "constraints": ("secondary-sanctions exposure of its banks since 2023-12-22",
                     "working capital and the cost of holding stranded inventory",
                     "a route that depends on one road and one tunnel"),
     "instruments": ("USDRUB", "EURRUB", "USDTRY", "USDCNH"),
     "counterparties": ("EU, Turkish, Chinese and Emirati suppliers", "Russian buyers",
                        "the freight forwarders and customs brokers", "the correspondent banks"),
     "observables": ("Armstat trade by partner and HS chapter",
                     "the EU/Turkey/China mirror export series",
                     "the freight press and the border-queue reports",
                     "company registrations in the trade codes"),
     "impact": "the aggregate re-export line moved by multiples and is a visible share of a "
               "small economy's trade account; the price effect is on the rouble legs and on "
               "the freight and lira complex rather than on any Armenian instrument",
     "persistence": "the SURGE era ran about 22 months; the ENFORCEMENT era re-routed it rather "
                    "than ending it, which is a different regime and not a smaller one",
     "falsifier": "the mirror gap between partner exports and Armenian imports shows no step at "
                  "2022-02-24 once the commodity mix and the base effect are controlled for",
     "notes": "the two-lane order forbids hunting any single trading company; this actor is the "
              "CLASS, and the instruments are the corridor's currency legs"},
    {"name": "Zangezur Copper-Molybdenum Combine as a concentrate shipper",
     "holds": "the Kajaran deposit and the country's dominant mining export, shipped as "
              "concentrate rather than refined metal",
     "forced_to": ("ship on a quarterly contract cycle to smelters abroad",
                   "accept the treatment and refining charge the smelters set",
                   "route through Georgia, because Armenia's other borders are closed"),
     "when": "quarterly contract settlement; shipment clusters at the quarter boundary",
     "information": ("its own grade and throughput before any statistic",
                     "the smelters' appetite for concentrate a quarter ahead"),
     "constraints": ("a single viable export route through Georgia",
                     "a treatment charge set by a smelter market it does not control",
                     "domestic political attention on the mine's ownership and its water use"),
     "instruments": ("XCUUSD",),
     "counterparties": ("Chinese and European smelters", "the Georgian rail and port operators",
                        "the Armenian state as tax and licence authority"),
     "observables": ("Armstat HS chapter 26 exports by partner",
                     "company production statements", "Georgian port throughput",
                     "the published treatment-charge benchmarks, which are LICENSED"),
     "impact": "small in world copper terms and material in CONCENTRATE terms; the honest claim "
               "is about concentrate availability and treatment charges, not about the cathode "
               "price, and the pack says so rather than overselling it",
     "persistence": "a mine's output is a multi-year object; a route interruption is weeks",
     "falsifier": "quarters with a large Armenian concentrate shipment change show no move in "
                  "the treatment-charge benchmark or in XCUUSD beyond the matched control",
     "notes": "AN ACTOR AND NEVER AN INSTRUMENT: the combine is unlisted and the two-lane order "
              "forbids hunting a single name in any case"},
    {"name": "The relocated technology company and its Armenian dram payroll",
     "holds": "a foreign-currency revenue stream and a local cost base created almost overnight "
              "in 2022, when several hundred companies and tens of thousands of people arrived",
     "forced_to": ("convert foreign revenue into dram every month to pay salaries and rent",
                   "hold local deposits it did not previously hold",
                   "decide each year whether to stay, which makes the flow reversible"),
     "when": "monthly payroll conversion; the arrival was concentrated in two quarters of 2022",
     "information": ("its own staying intention before any statistic",
                     "the bank account opening pipeline"),
     "constraints": ("residency and banking rules", "the political risk of the host",
                     "a client base that may require a different domicile"),
     "instruments": ("USDRUB", "XAUUSD"),
     "counterparties": ("Armenian banks", "landlords and the domestic services economy",
                        "foreign clients paying in dollars and euros"),
     "observables": ("company registrations and tax registrations",
                     "the services export line in the balance of payments",
                     "rents and the services CPI", "resident deposit growth"),
     "impact": "a structural, monthly dollar-selling flow layered on top of the household "
               "transfers, which is why the appreciation was persistent rather than a spike",
     "persistence": "reversible by construction -- this is the leg that can leave, and that "
                    "makes it the pack's clearest two-sided risk",
     "falsifier": "the services export line shows no step change coincident with the 2022 "
                  "registrations, which would mean the relocation was a headcount and not a flow",
     "notes": "the relocation and the household transfer are SEPARATE flows into the same "
              "currency, and a study that treats them as one cannot tell a reversible flow from "
              "a persistent one"},
    # ---------------------------------------------------------------- Uzbekistan
    {"name": "The Central Bank of Uzbekistan as a seller of monetary gold",
     "holds": "reserves that are majority gold by value, bought from the domestic producer in "
              "som and sold into the world market for dollars",
     "forced_to": ("publish the gold holding monthly in BOTH tonnes and value",
                   "buy the domestic mine output it has contracted for",
                   "supply the domestic FX market when the som comes under pressure"),
     "when": "the monthly reserve publication in the first week; sales through the year with a "
             "visible tonnage change month to month",
     "information": ("the mine's delivery schedule",
                     "its own intended sales before the market sees the tonnage move",
                     "the domestic FX market's demand daily"),
     "constraints": ("an inflation target and a managed crawl at the same time",
                     "a reserve position whose value swings with the gold price it is selling",
                     "a fiscal need for the dollars the sale produces"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the bullion market and its intermediaries",
                        "Navoi and the domestic producers", "the domestic banks"),
     "observables": ("the monthly tonnage AND value", "the World Gold Council's cross-check",
                     "the som's crawl against the dollar",
                     "the trade statistics' gold export line"),
     "impact": "a sovereign selling tens of tonnes in a year is a real, visible supply leg in a "
               "market where most official flows are inferred rather than published",
     "persistence": "the buy-and-sell cycle is structural and has run for years; an individual "
                    "month's operation is a one-month object",
     "falsifier": "months in which the published tonnage FELL show no measurable XAUUSD effect "
                  "in the following weeks once the price-driven valuation change is removed and "
                  "the matched-month control is applied",
     "notes": "THE RARE CASE: a sovereign gold operation on a published monthly clock. The "
              "tonnage must be separated from the valuation before anything is read"},
    {"name": "Navoi Mining and Metallurgical Combinat as a world-scale gold producer",
     "holds": "the Muruntau open pit and the surrounding complex -- one of the largest gold "
              "operations on the planet, state-owned and now a bond issuer",
     "forced_to": ("deliver contracted output to the central bank",
                   "disclose production and costs because it issues debt",
                   "mine a declining grade with a rising strip ratio"),
     "when": "continuous production; disclosure on the issuer's reporting calendar",
     "information": ("grade, throughput and the pit schedule years ahead of any outsider",),
     "constraints": ("an ore body with a falling grade",
                     "energy supply in a country with a winter gas deficit",
                     "a state owner that takes the output"),
     "instruments": ("XAUUSD", "XNGUSD"),
     "counterparties": ("the Central Bank of Uzbekistan", "the bond market",
                        "equipment and energy suppliers"),
     "observables": ("issuer disclosures and prospectuses", "the USGS country chapter",
                     "stat.uz industrial output", "the central bank's purchase side"),
     "impact": "the physical supply behind the sovereign's sales; a production interruption "
               "would remove the supply the sales depend on",
     "persistence": "mine-life scale -- decades, with annual steps",
     "falsifier": "years with a disclosed production step show no corresponding step in the "
                  "central bank's purchased tonnage, which would mean the two are not linked "
                  "and the sovereign-supply story is wrong",
     "notes": "AN ACTOR ONLY. The combine issues bonds and is still not an instrument any desk "
              "here may hunt (two-lane order)"},
    {"name": "The Uzbek cotton cluster after the end of the state procurement order",
     "holds": "land, gin capacity and an obligation to buy the crop that used to be delivered "
              "to the state at an administered price",
     "forced_to": ("buy the crop at a market price for the first time in its institutional life",
                   "sell fibre through UzEX auctions or contract it directly",
                   "meet the labour standards that lifted the international boycott"),
     "when": "the harvest September to November; the auction season through the winter",
     "information": ("the yield in its own districts before any national figure",
                     "the fibre quality mix that decides the price"),
     "constraints": ("water allocation from the Amu Darya and Syr Darya",
                     "a domestic textile industry the state wants supplied first",
                     "an export price it does not set"),
     "instruments": ("COTTON", "WHEAT"),
     "counterparties": ("the growers", "domestic spinners", "UzEX buyers",
                        "international textile buyers after the boycott ended"),
     "observables": ("UzEX lot volumes, grades and clearing prices",
                     "stat.uz cotton output and fibre exports",
                     "the water-allocation announcements", "the area planted to cotton"),
     "impact": "Uzbekistan is a top-ten producer and the SWITCH from state procurement to "
               "cluster purchase changed who decides how much is planted -- which is a supply "
               "mechanism, not a price correlation",
     "persistence": "the institutional change is permanent; the seasonal cycle repeats annually",
     "falsifier": "the auction season's clearing prices carry no information about COTTON "
                  "beyond the global price already in the market, measured against the same "
                  "weeks in the pre-2020 state-order years",
     "notes": "THE ERA BOUNDARY IS THE POINT: a study pooling the state-order years with the "
              "cluster years is measuring two different supply functions"},
    {"name": "Uzbekneftegaz and a gas balance whose sign reversed",
     "holds": "declining domestic gas production against a rising domestic demand, plus the "
              "legacy export commitments that used to be the point",
     "forced_to": ("supply the domestic winter first, by presidential instruction",
                   "cut export volumes to do it", "import from Russia once the balance flipped"),
     "when": "the winter deficit each December to February; contract renegotiations annually",
     "information": ("field decline rates and the winter balance before any announcement",),
     "constraints": ("an ageing field base", "a subsidised domestic price",
                     "a smelter and power fleet that cannot be cut without visible cost"),
     "instruments": ("XNGUSD", "USDCNH", "XAUUSD"),
     "counterparties": ("CNPC on the export leg", "Gazprom on the import leg",
                        "the domestic power and industrial load"),
     "observables": ("China customs gas imports by origin", "stat.uz production and trade",
                     "the winter load-shedding reports in the press",
                     "the announced import arrangements"),
     "impact": "a producer becoming an importer is a structural sign change in a regional gas "
               "balance, and it changes who is bidding for molecules in winter",
     "persistence": "structural; the decline does not reverse on an announcement",
     "falsifier": "the winters after the balance flipped show no difference in the region's "
                  "gas-linked observables from the winters before it, which would mean the "
                  "reversal was accounting rather than physical",
     "notes": "the sign change is a REGIME BREAK and is in POLICY_ERAS for exactly that reason"},
    {"name": "The Uzbek labour migrant in Russia",
     "holds": "a Russian wage, a migration status that can be revoked, and a family at home "
              "that depends on the monthly transfer",
     "forced_to": ("send around the Russian pay cycle",
                   "convert roubles at whatever the corridor charges",
                   "leave or stay on terms set by Russian migration policy, not Uzbek"),
     "when": "month-end; and in step changes when Russian migration rules or the rouble move",
     "information": ("the corridor's real cost before any published fee schedule",
                     "whether the work is still there"),
     "constraints": ("Russian migration enforcement", "the rouble's own value",
                     "the fee and limit structure of the transfer operators"),
     "instruments": ("USDRUB", "EURRUB", "XAUUSD"),
     "counterparties": ("the transfer operators", "Uzbek banks and card issuers",
                        "Russian employers"),
     "observables": ("the transfer operators' corridor statistics",
                     "the central bank's cross-border transfer series",
                     "Russian migration statistics", "the som's seasonal pattern"),
     "impact": "the largest single migrant stock in the corridor; the aggregate is a standing "
               "monthly rouble-selling and dollar-buying flow",
     "persistence": "structural and seasonal at once: a monthly cycle inside a multi-year stock",
     "falsifier": "the month-end window shows no excess move on the rouble legs relative to the "
                  "matched mid-month control across the four remittance jurisdictions",
     "notes": "the same actor class as the Armenian and Tajik remitters, and the three must be "
              "measured SEPARATELY -- their corridors, their currencies and their seasonalities "
              "are not the same"},
    # ---------------------------------------------------------------- Kyrgyzstan
    {"name": "Kyrgyzaltyn and the state as Kumtor's operator since 2021",
     "holds": "the country's one large gold mine, taken under state external management in 2021 "
              "after two decades of foreign operation",
     "forced_to": ("keep producing, because the mine is a large share of the state's revenue",
                   "report production in a format it chose rather than one an auditor set",
                   "manage a high-altitude glacier-adjacent pit with the previous operator gone"),
     "when": "quarterly and annual disclosure; the ownership break is dated to 2021",
     "information": ("actual grade and throughput before anyone outside the state",),
     "constraints": ("technical capacity after an operator change",
                     "a deposit with a finite and declining reserve",
                     "an environmental and political record that constrains reporting"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the refiners that take the dore", "the state budget",
                        "the former operator through the settlement"),
     "observables": ("state production announcements", "stat.kg export line",
                     "the USGS country chapter", "the NBKR's gold purchases"),
     "impact": "material for Kyrgyz exports and small in world gold; the RESEARCH object is the "
               "2021 break, because a producing asset changing hands on a date is a natural "
               "experiment on disclosure quality and on output",
     "persistence": "the ownership change is permanent; the disclosure break is permanent too",
     "falsifier": "the post-2021 production series is statistically indistinguishable from a "
                  "continuation of the audited pre-2021 series, which would mean the break "
                  "changed the owner and not the measurement",
     "notes": "DO NOT SPLICE THE TWO HALVES. One is audited by an operator with a listing "
              "obligation and one is announced by a state; they are different measurements"},
    {"name": "The National Bank of the Kyrgyz Republic FX auction desk",
     "holds": "reserves it spends to hold the som in a band so narrow it reads as a peg, and "
              "the only same-day published intervention record in this pack",
     "forced_to": ("announce each auction and publish its volume and rate the same day",
                   "sell dollars when the corridor's import demand overwhelms the market",
                   "buy the domestic gold output the state wants monetised"),
     "when": "auctions intraday, irregular but clustered; publication the same day",
     "information": ("the banks' FX orders before they reach the market",
                     "the customs receipts weeks before stat.kg publishes"),
     "constraints": ("reserves that are small relative to the corridor's gross flows",
                     "a quasi-peg it has chosen to defend",
                     "a banking system under correspondent pressure since 2023-12-22"),
     "instruments": ("USDRUB", "XAUUSD", "USDCNH"),
     "counterparties": ("the commercial banks", "the state as gold seller",
                        "the importers financing the re-export trade"),
     "observables": ("the same-day auction result -- date, direction, volume, rate",
                     "weekly reserve statements", "the som's realised volatility, near zero"),
     "impact": "the auction SIZE is the corridor's dollar demand made visible before any trade "
               "statistic exists; the som's price is nearly constant and carries nothing",
     "persistence": "the quasi-peg has held for years; an individual auction is a one-day event",
     "falsifier": "auction days show no excess move on USDRUB or XAUUSD relative to matched "
                  "non-auction days -- and the control must handle the SELECTION problem, "
                  "because the bank auctions precisely when the flow is large",
     "notes": "the endogeneity is the hard part and is stated up front rather than discovered "
              "in review: the decision to intervene is caused by the thing being measured"},
    {"name": "The Dordoi and Kara-Suu bazaar re-exporter",
     "holds": "container lots of Chinese goods broken down for onward sale into Russia, "
              "Kazakhstan and the Fergana valley",
     "forced_to": ("clear containers quickly because storage is the whole margin",
                   "pay in cash or through informal settlement when banks refuse",
                   "switch route and product mix the week a rule changes"),
     "when": "continuously; container arrivals follow the Chinese shipping calendar and drop "
             "around the Lunar New Year",
     "information": ("container arrival volumes and the clearing price of a lot, daily",
                     "which goods have become undeclarable this month"),
     "constraints": ("customs valuation practice and the EAEU common tariff",
                     "cash logistics when the banking leg closes",
                     "the Chinese supplier's own credit terms"),
     "instruments": ("USDCNH", "USDRUB", "XAUUSD"),
     "counterparties": ("Chinese suppliers and freight forwarders", "Russian and Kazakh buyers",
                        "the cash changers"),
     "observables": ("bazaar throughput reporting", "Chinese customs exports to Kyrgyzstan",
                     "stat.kg imports from China", "the Khorgos and Torugart crossing volumes"),
     "impact": "the CHINESE MIRROR against Kyrgyz imports is one of the largest and oldest "
               "mirror gaps in world trade statistics, and it predates the corridor -- which is "
               "why the 2022 step must be measured against that pre-existing gap and not "
               "against zero",
     "persistence": "structural and decades old; the corridor added a level shift on top",
     "falsifier": "the China-Kyrgyzstan mirror gap shows no step at 2022-02-24 once the "
                  "long-standing pre-2022 gap and the commodity mix are controlled for",
     "notes": "the pre-existing gap is the reason this actor is in the pack: it is the built-in "
              "placebo for every mirror-statistics claim the pack makes"},
    {"name": "The Kyrgyz and Armenian bank compliance officer after December 2023",
     "holds": "correspondent relationships that can be withdrawn by a foreign bank at any time, "
              "and a book of corridor payments that is the reason they might be",
     "forced_to": ("refuse payments that were routine a month earlier",
                   "re-paper client relationships under pressure from a correspondent",
                   "act before a rule is tested, because the penalty is the relationship itself"),
     "when": "step changes on designation days and on correspondent notices; the era boundary "
             "is 2023-12-22, when foreign financial institutions were exposed to secondary "
             "sanctions for facilitating the trade",
     "information": ("which correspondents are about to withdraw, before the market knows",
                     "the refused-payment rate inside its own book"),
     "constraints": ("secondary-sanctions exposure", "a domestic client base that needs the "
                     "corridor", "a regulator that wants both outcomes at once"),
     "instruments": ("USDRUB", "EURRUB", "USDTRY"),
     "counterparties": ("US and European correspondent banks", "the domestic exporters",
                        "the central bank"),
     "observables": ("designation lists and their dates", "press reporting of refused payments",
                     "the transfer operators' corridor withdrawals",
                     "the step changes in the trade series afterwards"),
     "impact": "the ENFORCEMENT era's re-routing is this actor's decision aggregated; the flow "
               "did not stop, it changed address, and that is visible as a partner-mix shift",
     "persistence": "each designation's effect decays over weeks as routes re-form; the "
                    "regime change itself is permanent",
     "falsifier": "designation dates show no measurable change in the partner mix of the five "
                  "states' trade within the following quarter, which would mean enforcement "
                  "announcements are noise",
     "notes": "a cross-jurisdiction actor filed under Kyrgyzstan and Armenia because those two "
              "banking systems took the visible share of the pressure"},
    # ---------------------------------------------------------------- Tajikistan
    {"name": "TALCO as a smelter whose real input is stranded electricity",
     "holds": "the region's only primary aluminium smelter, running on hydropower that has "
              "almost no other route to market",
     "forced_to": ("run its potlines continuously or lose them, which makes the load inflexible",
                   "take whatever power the cascade has after the domestic winter demand",
                   "import every tonne of alumina it smelts"),
     "when": "continuous; the binding constraint arrives each winter and each time Rogun "
             "impounds water",
     "information": ("the reservoir level and the dispatch plan before any public statement",),
     "constraints": ("a winter power deficit the country cannot import its way out of",
                     "alumina imported over long distances",
                     "an output series that domestic statistics and the USGS disagree about"),
     "instruments": ("XALUSD",),
     "counterparties": ("Barqi Tojik as the power supplier", "alumina suppliers",
                        "metal traders", "the state as owner"),
     "observables": ("TALCO and stat.tj output", "the USGS country chapter",
                     "the Rogun filling announcements",
                     "the winter load-shedding reports in Asia-Plus"),
     "impact": "small in world aluminium and large as a CLEAN IDENTIFICATION: a smelter whose "
               "output is set by water rather than by the metal price is a supply shock that is "
               "exogenous to the price, which is rare",
     "persistence": "a potline restart takes months, so an interruption persists well past the "
                    "power event that caused it",
     "falsifier": "years with a declared Rogun filling campaign show no reduction in Tajik "
                  "aluminium output relative to the non-filling years, which would mean the "
                  "water and the smelter are not competing for the same resource",
     "notes": "THE POINT IS EXOGENEITY. Most metal-supply stories are contaminated by the price; "
              "this one is driven by a reservoir schedule"},
    {"name": "The Rogun project office and Barqi Tojik as the winter power rationer",
     "holds": "the Vakhsh cascade, a part-built dam that is the largest construction project in "
              "the region, and the authority to decide who is cut first in winter",
     "forced_to": ("impound water on a schedule set by construction, not by demand",
                   "ration the winter deficit between households and the smelter",
                   "finance the project out of a budget that cannot carry it alone"),
     "when": "the filling campaigns are announced and dated; the deficit is every winter",
     "information": ("the reservoir level, the inflow forecast and the dispatch order",),
     "constraints": ("a snowmelt-driven inflow it does not control",
                     "international lenders' conditions",
                     "an export ambition through CASA-1000 that competes with domestic demand"),
     "instruments": ("XALUSD",),
     "counterparties": ("TALCO as the interruptible load", "households",
                        "the World Bank and other financiers", "the CASA-1000 buyers"),
     "observables": ("filling announcements and commissioning dates",
                     "load-shedding reports", "CASA-1000 progress statements",
                     "the industrial output index in the deficit months"),
     "impact": "the single largest dated, physical, exogenous supply event a Central Asian metal "
               "has; the transmission is into XALUSD through the smelter's load",
     "persistence": "the filling schedule runs for years and its steps are announced",
     "falsifier": "announced filling or commissioning dates show no effect on the industrial "
                  "output index or on the aluminium output series in the following quarters",
     "notes": "a state actor whose decisions are about WATER and whose market footprint is in "
              "METAL -- which is why it belongs in a quant pack at all"},
    {"name": "The National Bank of Tajikistan and the licensed exchange bureau",
     "holds": "an official rate it guides and a licensed-bureau network that quotes a second "
              "price the bank does not publish",
     "forced_to": ("publish an official rate every business day",
                   "keep the two prices close enough to be defensible",
                   "supply the bureaux when the remittance season turns"),
     "when": "daily for the official rate; the spread widens seasonally and in stress episodes",
     "information": ("the true bureau rate across the country in real time",
                     "the remittance inflow before the quarterly statistic"),
     "constraints": ("reserves that are small against the remittance cycle",
                     "an administered rate it has chosen to defend",
                     "a cash economy where the bureau window is the real market"),
     "instruments": ("XALUSD", "USDRUB"),
     "counterparties": ("the licensed bureaux", "the commercial banks",
                        "the migrant households converting roubles"),
     "observables": ("the daily official rate", "press-reported bureau rates",
                     "the quarterly remittance series", "cash-shortage reporting"),
     "impact": "the SPREAD is the country's FX-stress state; the official rate on its own is an "
               "administered number and carries almost nothing",
     "persistence": "stress episodes run weeks to months and resolve with a step in the "
                    "official rate",
     "falsifier": "periods of a wide reported bureau spread are indistinguishable, on the "
                  "rouble and aluminium legs, from periods of a tight one",
     "notes": "the bureau rate is PRESS_REPORTED and is declared unpublishable in "
              "NO_LAWFUL_GROUND; no cell compiled on it may ever be promoted"},
    {"name": "The Tajik migrant household",
     "holds": "the highest dependence on remittances of any country on earth in several years, "
              "and almost no domestic alternative to it",
     "forced_to": ("send every month because the household has no other income",
                   "accept the rouble's value, whatever it is",
                   "convert at the bureau window when the bank rate is unavailable"),
     "when": "monthly, with a strong seasonal shape as construction work in Russia starts in "
             "spring and stops in late autumn",
     "information": ("the real bureau rate and the real cost of the corridor",),
     "constraints": ("Russian migration policy and enforcement",
                     "a rouble it does not control", "no domestic labour market to return to"),
     "instruments": ("USDRUB", "XALUSD"),
     "counterparties": ("the transfer operators", "the licensed bureaux",
                        "Russian employers in construction and services"),
     "observables": ("the NBT quarterly remittance series",
                     "the operators' corridor volumes", "the bureau spread",
                     "Russian migration statistics"),
     "impact": "the largest single item in the country's external accounts; its seasonality is "
               "the seasonality of the currency and of the import bill",
     "persistence": "structural, with a pronounced annual cycle that repeats",
     "falsifier": "the spring-to-autumn seasonal in the remittance series carries no "
                  "information about the rouble legs beyond the Russian construction cycle "
                  "already visible in Russian data",
     "notes": "the third remittance actor in this pack, and the one with the least buffer -- "
              "which is why Tajikistan is where a corridor closure would show up first"},
    # ---------------------------------------------------------------- Turkmenistan
    {"name": "Turkmengaz as a single-customer gas exporter",
     "holds": "the world's fourth-largest proven gas reserves and effectively one pipeline "
              "customer for them",
     "forced_to": ("sell to the customer it has, on terms it does not set",
                   "deliver on a contract whose volumes appear in the buyer's statistics",
                   "keep Galkynysh producing to service the credit it was built on"),
     "when": "continuous delivery; contract and volume news arrives through the buyer, not the "
             "seller",
     "information": ("its own deliverability and field performance, published to nobody",),
     "constraints": ("one pipeline system with one dominant customer",
                     "alternative routes that have been announced for decades and not built",
                     "a state that publishes no data about any of it"),
     "instruments": ("XNGUSD", "USDCNH"),
     "counterparties": ("CNPC as the dominant buyer", "the TAPI project participants",
                        "the occasional swap counterparties to the north and west"),
     "observables": ("CHINESE CUSTOMS gas imports by origin, in volume and value -- and "
                     "essentially nothing else that is quantified",
                     "pipeline operator statements on the Chinese side",
                     "the exile press's reporting of domestic conditions"),
     "impact": "one of the largest single physical energy flows in Asia, and it is observable "
               "ONLY from the buyer's side",
     "persistence": "contract-scale: years, with seasonal delivery variation",
     "falsifier": "the Chinese customs Turkmen volume series carries no information about the "
                  "region's gas-linked observables beyond China's total import series",
     "notes": "THE PACK'S WORKED MIRROR CASE. The seller publishes nothing; the buyer publishes "
              "monthly; the measurement exists because a third country keeps records"},
    {"name": "CNPC as the monopsonist at the Turkmen border",
     "holds": "the buying side of the Central Asia-China pipeline and the pricing power that "
              "comes with being the only real customer",
     "forced_to": ("take contracted volumes",
                   "report the imports to Chinese customs, which publishes them",
                   "balance Turkmen supply against LNG and Russian pipeline alternatives"),
     "when": "monthly delivery; the published record follows on the customs calendar",
     "information": ("the delivered price and volume before they are published",
                     "its own substitution options between suppliers"),
     "constraints": ("Chinese demand and the domestic gas price",
                     "competing supply from Russia and from LNG",
                     "a pipeline whose capacity is fixed"),
     "instruments": ("XNGUSD", "USDCNH"),
     "counterparties": ("Turkmengaz", "the Chinese domestic distributors",
                        "the LNG and Russian pipeline alternatives"),
     "observables": ("China customs imports by origin, volume and value",
                     "Chinese domestic gas demand and LNG import series",
                     "the implied unit value at the border"),
     "impact": "the buyer's substitution decision sets the Turkmen volume, so the SUPPLY series "
               "is really a demand series -- a distinction any causal claim here must carry",
     "persistence": "contract-scale with seasonal variation",
     "falsifier": "Turkmen volume changes are fully explained by Chinese total gas demand and "
                  "LNG prices, leaving nothing Turkmen-specific to measure",
     "notes": "THE IDENTIFICATION WARNING, written into the pack rather than left for a "
              "reviewer: a monopsonist's purchases look like the seller's supply and are not"},
    {"name": "The Central Bank of Turkmenistan as the administrator of a fixed rate",
     "holds": "a rate fixed at 3.50 manat to the dollar since 2015-01-01 and the exchange "
              "controls that are the only reason it holds",
     "forced_to": ("keep the number unchanged, because changing it is a political act",
                   "ration access to conversion through licences and limits",
                   "publish essentially nothing about any of it"),
     "when": "continuously; the rate has not moved in a decade",
     "information": ("the true external position, published to nobody",),
     "constraints": ("gas revenue it does not control",
                     "a parallel market it cannot close",
                     "no published reserve series to defend the fix with"),
     "instruments": ("XNGUSD", "USDCNH"),
     "counterparties": ("the state gas companies as the source of dollars",
                        "importers rationed at the window",
                        "the informal market it does not acknowledge"),
     "observables": ("the fixed rate itself, which is a constant",
                     "PRESS-REPORTED parallel rates from the exile outlets",
                     "cash-queue and import-shortage reporting",
                     "the Chinese customs value side as a revenue proxy"),
     "impact": "a constant carries no information; the PREMIUM does, and the premium is where "
               "an import squeeze and a devaluation risk become visible",
     "persistence": "a decade and counting, which is itself the finding",
     "falsifier": "periods of a wide reported parallel premium are indistinguishable from "
                  "periods of a narrow one on every gas- and China-linked instrument",
     "notes": "the pack's cleanest example of an official series with a value and no "
              "information, and of why a second price must be sought when the first is fixed"},
    {"name": "The Turkmen informal money changer",
     "holds": "the only real exchange market in the country, at a price the state does not "
              "acknowledge",
     "forced_to": ("quote a price that clears an actual market",
                   "operate under legal risk, which is why the price carries a risk premium",
                   "react to every rationing decision within days"),
     "when": "continuously; the reported rate moves in steps around import and cash episodes",
     "information": ("the real scarcity of dollars in the country, daily",),
     "constraints": ("enforcement risk", "cash logistics",
                     "a supply of dollars that comes from one export"),
     "instruments": ("XNGUSD", "USDCNH"),
     "counterparties": ("households and traders needing hard currency",
                        "importers rationed out of the official window"),
     "observables": ("PRESS_REPORTED rates from turkmen.news and the Chronicles",
                     "queue and shortage reporting", "import price reporting"),
     "impact": "the premium is the country's only continuous stress reading and the state "
               "variable of CCA-TM-B",
     "persistence": "episodes last weeks to months; the multiple has been large for years",
     "falsifier": "the reported premium is uncorrelated with every independently measured "
                  "Turkmen observable -- gas export value, import volumes, the cash-queue "
                  "reporting -- which would mean the reported numbers are noise",
     "notes": "REGISTERED AS REPORTING AND NEVER AS A SERIES. This actor exists in the pack so "
              "that the absence of an official market is a measurement rather than a silence"},
    # ---------------------------------------------------------------- cross-jurisdiction
    {"name": "The sanctions-enforcement authority (OFAC, the EU sanctions envoy, DG TRADE)",
     "holds": "the designation list, the export-control rules and the threat of secondary "
              "exposure for a foreign bank",
     "forced_to": ("publish each designation with a date",
                   "act visibly enough to change behaviour, which means announcing",
                   "choose between closing a route and driving it somewhere less visible"),
     "when": "designations and packages on announced dates; the era boundary is 2023-12-22",
     "information": ("the mirror data before anyone else, and its own next move",),
     "constraints": ("a jurisdiction that ends at its own border",
                     "allies with different appetites",
                     "the fact that enforcement re-routes flows rather than ending them"),
     "instruments": ("USDRUB", "EURRUB", "USDTRY", "USDCNH"),
     "counterparties": ("the regional banks and their correspondents",
                        "the trading companies", "the five governments"),
     "observables": ("the designation lists and their dates",
                     "the EU packages and the common high-priority item list",
                     "the subsequent partner-mix shift in the mirror data"),
     "impact": "the ENFORCEMENT era boundary is this actor's decision; the measurable effect is "
               "a re-routing -- a partner-mix change -- rather than a volume collapse",
     "persistence": "each announcement's behavioural effect decays over weeks; the regime "
                    "change is permanent",
     "falsifier": "designation dates show no partner-mix change in the five states' trade in "
                  "the following quarter once the seasonal and commodity mix is controlled",
     "notes": "the pack's one FOREIGN actor, and the reason it is here is that it sets the era "
              "boundaries every domestic mechanism is conditioned on"},
    {"name": "The Russian importer and the parallel-import regime",
     "holds": "the demand that the whole corridor exists to serve, plus a legal regime that "
              "made importing without the brand owner's consent lawful at home",
     "forced_to": ("source somewhere, because the direct route closed",
                   "pay the corridor's markup and the freight",
                   "re-route whenever a supplier's bank refuses"),
     "when": "continuously; step changes on each package and on each rouble move",
     "information": ("its own order book and the real landed cost",),
     "constraints": ("the rouble's value", "domestic demand",
                     "a supply chain with more hops than it had"),
     "instruments": ("USDRUB", "EURRUB", "USDCNH", "USDTRY"),
     "counterparties": ("the Armenian, Kyrgyz, Uzbek, Turkish, Emirati and Chinese "
                        "intermediaries", "the Russian customs authority"),
     "observables": ("the mirror gap's Russian side where it is published",
                     "the five states' export lines to Russia",
                     "Russian import price and volume reporting"),
     "impact": "the demand side of the corridor; without it the re-export series would not "
               "exist, and its strength is what makes the flow persistent under enforcement",
     "persistence": "as persistent as the demand itself",
     "falsifier": "the five states' Russia-bound export lines do not move with independently "
                  "measured Russian import demand, which would mean the corridor is not serving "
                  "that demand at all",
     "notes": "the actor that makes the corridor a DEMAND-PULL mechanism rather than an "
              "arbitrage; that distinction decides which direction the causality runs"},
    {"name": "The third-country correspondent bank as the payment chokepoint",
     "holds": "the dollar and euro clearing every leg of the corridor ultimately needs, and the "
              "unilateral right to withdraw it",
     "forced_to": ("price its own regulatory risk above its client revenue",
                   "withdraw first and investigate later when exposure rises",
                   "answer to a regulator in a jurisdiction none of the five is in"),
     "when": "step changes after designations and after enforcement announcements",
     "information": ("its own withdrawal plans before any client knows",),
     "constraints": ("secondary-sanctions exposure",
                     "a compliance cost that exceeds the corridor's revenue",
                     "no obligation to explain a withdrawal"),
     "instruments": ("USDRUB", "EURRUB", "USDTRY", "USDCNH"),
     "counterparties": ("the Armenian, Kyrgyz, Uzbek and Tajik banks",
                        "the transfer operators", "the regulators"),
     "observables": ("press-reported correspondent withdrawals",
                     "the transfer operators' corridor list changes",
                     "the step changes in the transfer and trade series"),
     "impact": "THE BINDING CONSTRAINT ON THE WHOLE MECHANISM. A corridor with demand, supply "
               "and a route still fails if nobody will clear the payment",
     "persistence": "a withdrawal is permanent for that relationship; the flow re-forms "
                    "elsewhere over weeks to months",
     "falsifier": "reported correspondent withdrawals are followed by no measurable change in "
                  "the transfer series or in the partner mix of the trade series",
     "notes": "this actor is why the ENFORCEMENT era is a RE-ROUTING and not a shutdown, and it "
              "is the reason the pack's edges are about partner mix rather than volume"},
)


# --------------------------------------------------------------------------- domains
#: SIXTEEN DOMAINS: three regional, TWO PER JURISDICTION, and three that belong to the calendar,
#: the enforcement clock and the energy balance. Every one carries at least two negative
#: controls, because without a control an effect cannot be told apart from the desk's own
#: sampling -- and in a region this correlated with Russia, "the rouble moved" is the null that
#: eats most apparent findings.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CCA-A", "title": "The post-2022 re-export corridor and its mirror statistics",
     "objects": ("the five states' own monthly export and import tables by partner and HS "
                 "chapter", "the EU, Turkish and Chinese mirror export series to the five",
                 "the MIRROR GAP between the two, by commodity chapter and month",
                 "the partner-mix shift after each enforcement step"),
     "conditions": ("the corridor era -- PRE_CORRIDOR, SURGE, ENFORCEMENT",
                    "whether the jurisdiction is inside the EAEU customs union (am, kg) or "
                    "outside it (uz, tj, tm)",
                    "the commodity chapter: dual-use and high-priority items against the rest"),
     "instruments": ("USDRUB", "EURRUB", "USDTRY", "USDCNH"),
     "controls": ("THE PRE-EXISTING MIRROR GAP. China-Kyrgyzstan has had one of the world's "
                  "largest mirror gaps for two decades; the 2022 step must be measured against "
                  "that gap and never against zero",
                  "the same chapters for a matched non-corridor state (Georgia and Mongolia "
                  "share the geography and not the mechanism)",
                  "a randomised-date null on the same monthly series, which is what a trend "
                  "with a base effect looks like"),
     "notes": "THE PACK'S CENTRAL DOMAIN. Both halves are published and neither alone is the "
              "measurement; every cell here is NOT_PIT_SAFE until a stamped vintage of BOTH "
              "reporter and partner is held, because Comtrade backfills"},
    {"id": "CCA-B", "title": "The remittance corridor: monthly transfers by origin and the "
                             "month-end payout clock",
     "objects": ("the CBA's monthly non-commercial transfers by source country",
                 "the NBT's quarterly remittance series and the Kyrgyz transfer statistics",
                 "the transfer operators' published corridors, fees and limits",
                 "the month-end payout window in each of the four labour exporters"),
     "conditions": ("the month-end window against mid-month",
                    "the corridor era and the correspondent-withdrawal episodes",
                    "the Russian construction season (spring start, late-autumn stop)"),
     "instruments": ("USDRUB", "EURRUB", "XAUUSD"),
     "controls": ("the matched weekday-and-hour control on the same instruments mid-month",
                  "Georgia's own published transfer series, the sibling observatory next door, "
                  "separating 'the CIS remittance cycle' from 'this jurisdiction'",
                  "the same windows in the PRE_CORRIDOR era, when the level was a fraction of "
                  "what it became"),
     "notes": "the identification here is unusually good for a flow study, because the flow "
              "itself is published monthly BY ORIGIN rather than inferred from prices"},
    {"id": "CCA-C", "title": "Sovereign and conduit gold out of Central Asia",
     "objects": ("the CBU's monthly gold tonnage and value",
                 "the Kyrgyz chapter-71 export line against Kumtor's actual production",
                 "the Armenian chapter-71 line against an economy with no mine of that size",
                 "the World Gold Council's official-holdings cross-check"),
     "conditions": ("whether the month's tonnage change is an OPERATION or a valuation",
                    "the corridor era", "the gold price regime the sale is executed into"),
     "instruments": ("XAUUSD",),
     "controls": ("the valuation-only null: reprice last month's tonnage at this month's price "
                  "and see how much of the reported change survives",
                  "the same months for a sovereign that buys rather than sells, so 'official "
                  "gold flow' is separated from 'this sovereign'",
                  "matched-month windows in years with no reported tonnage change"),
     "notes": "THE OPERATION MUST BE SEPARATED FROM THE PRICE. Uzbekistan publishes both "
              "tonnage and value, which is the only reason this domain can exist at all"},
    {"id": "CCA-AM-A", "title": "Armenia: the dram's flow appreciation and the CBA's transfer "
                                "series",
     "objects": ("the 2022 appreciation of roughly 20% against the dollar",
                 "the monthly transfer series by origin that ran beside it",
                 "the relocation of companies and people as a separate, reversible flow",
                 "the CBA's published interventions and its eight Board decisions a year"),
     "conditions": ("the corridor era", "the transfer level relative to its pre-2022 trend",
                    "whether the month carried a published intervention"),
     "instruments": ("USDRUB", "USDTRY", "XAUUSD"),
     "controls": ("the same state built on a BLOCK-SHUFFLED transfer series, which is the "
                  "correct null for a state variable built from a flow",
                  "Georgia over the same months: the same shock, a different currency regime "
                  "and a different banking system",
                  "the same windows on non-release days, so the release is told from the month"),
     "notes": "TWO FLOWS, NOT ONE: the household transfer is persistent and the corporate "
              "relocation is reversible, and a study that pools them cannot tell which is which"},
    {"id": "CCA-AM-B", "title": "Armenia: copper-molybdenum concentrate into the copper complex",
     "objects": ("Armstat chapter-26 export volumes by partner",
                 "the Zangezur production and shipment cycle",
                 "the single Georgian export route and its interruptions",
                 "the treatment-charge benchmark the concentrate is sold against"),
     "conditions": ("the quarter boundary, where contract shipments cluster",
                    "whether the Georgian route was interrupted",
                    "the smelter market's concentrate appetite"),
     "instruments": ("XCUUSD",),
     "controls": ("the same quarters for a comparable small concentrate exporter, separating "
                  "'concentrate' from 'Armenia'",
                  "quarters with no shipment change, as the null",
                  "the refined-metal price move on the same days, which is the channel this "
                  "domain explicitly does NOT claim"),
     "notes": "HONEST DIRECTION DECLARED: the claim is about concentrate availability and "
              "treatment charges, not about Armenia moving the copper price"},
    {"id": "CCA-UZ-A", "title": "Uzbekistan: the central bank's monthly gold operation",
     "objects": ("the published monthly tonnage and value",
                 "the purchase side from Navoi and the sale side into the market",
                 "the som's managed crawl the sales are financing",
                 "the CBU's seven-to-eight rate decisions a year"),
     "conditions": ("the direction and size of the tonnage change",
                    "whether the som was under pressure that month",
                    "the era: before or after the 2017-09-05 liberalisation"),
     "instruments": ("XAUUSD",),
     "controls": ("the valuation-only reconstruction of the reported change",
                  "the World Gold Council series for the same months, which is an independent "
                  "read on the same holding",
                  "matched months with no tonnage change"),
     "notes": "THE 2017-09-05 BOUNDARY IS ABSOLUTE. Before it the som had two prices and the "
              "reserve accounting means something different; no sample may cross it"},
    {"id": "CCA-UZ-B", "title": "Uzbekistan: cotton after the state order, and the UzEX auction",
     "objects": ("the UzEX fibre auction lots, grades and clearing prices",
                 "the cluster system that replaced state procurement",
                 "the area planted and the water allocation",
                 "the export line after the international boycott was lifted"),
     "conditions": ("the marketing year and the auction season (October to March)",
                    "the era: state order against cluster purchase",
                    "the water-allocation year"),
     "instruments": ("COTTON", "WHEAT"),
     "controls": ("the same calendar weeks in the pre-2020 state-order years, when the price "
                  "was administered and the auction did not set it",
                  "a matched producer's own auction calendar, separating 'the cotton season' "
                  "from 'Uzbekistan'",
                  "the wheat line over the same seasons, the rotation crop, which controls for "
                  "the water year"),
     "notes": "the institutional change is the research object; the price correlation on its "
              "own would be a coincidence with a season attached"},
    {"id": "CCA-KG-A", "title": "Kyrgyzstan: the same-day published FX intervention",
     "objects": ("the NBKR auction records -- date, direction, volume, weighted rate",
                 "the som's near-zero realised volatility under the quasi-peg",
                 "the reserve statement each week",
                 "the import demand the auctions are financing"),
     "conditions": ("auction direction and size",
                    "the corridor era",
                    "whether the auction followed a customs or transfer release"),
     "instruments": ("USDRUB", "XAUUSD", "USDCNH"),
     "controls": ("matched non-auction days by weekday and hour -- and the control must be "
                  "chosen to address SELECTION, because the bank auctions precisely when the "
                  "flow is large",
                  "the same days in the PRE_CORRIDOR era, when auction sizes were smaller",
                  "a randomised-date null over the same span"),
     "notes": "THE ENDOGENEITY IS STATED UP FRONT: the decision to intervene is caused by the "
              "thing being measured, so an uncorrected event study here will find an effect "
              "whether or not one exists"},
    {"id": "CCA-KG-B", "title": "Kyrgyzstan: Kumtor's 2021 break and the gold conduit",
     "objects": ("the production series before and after the 2021 external management",
                 "the chapter-71 export line, which is far larger than production",
                 "the arithmetic gap between the two, which IS the conduit",
                 "the refining and transit partners in the customs tables"),
     "conditions": ("before or after the 2021 ownership break",
                    "the corridor era",
                    "whether the month's export line exceeds plausible domestic production"),
     "instruments": ("XAUUSD", "USDCNH"),
     "controls": ("the USGS country chapter as an independent production estimate, so 'the "
                  "state says' and 'the mine produced' are separate quantities",
                  "the same months for Armenia's chapter-71 line, the sibling conduit",
                  "the pre-2021 audited operator series as the measurement-quality control"),
     "notes": "DO NOT SPLICE the audited and announced halves of the production series; the "
              "break is in the MEASUREMENT as well as in the ownership"},
    {"id": "CCA-TJ-A", "title": "Tajikistan: the two-price somoni and the remittance season",
     "objects": ("the NBT daily official rate",
                 "the PRESS_REPORTED licensed-bureau rate beside it",
                 "the spread between them as the stress state",
                 "the quarterly remittance series and its spring-to-autumn seasonal"),
     "conditions": ("the premium bucket -- TIGHT, STRESSED, BROKEN",
                    "the remittance season", "the corridor era"),
     "instruments": ("USDRUB", "XALUSD"),
     "controls": ("the same months in years with a tight spread, as the null",
                  "the Kyrgyz som over the same months, the neighbouring managed rate with a "
                  "published second price, separating 'Central Asia' from 'Tajikistan'",
                  "a randomised-date null on the reported bureau observations, which are "
                  "irregular and must not be treated as a regular series"),
     "notes": "the bureau rate is PRESS_REPORTED and unpublished; a cell compiled on it may "
              "generate a hypothesis and may never be promoted"},
    {"id": "CCA-TJ-B", "title": "Tajikistan: TALCO, Rogun and aluminium made of stranded water",
     "objects": ("the TALCO output series and the USGS estimate that disagrees with it",
                 "the Rogun filling campaigns and commissioning dates",
                 "the winter load-shedding episodes",
                 "the alumina import line that bounds what can be smelted"),
     "conditions": ("whether a filling campaign was under way",
                    "the winter deficit months against the rest of the year",
                    "the reservoir's inflow year (snowmelt-driven)"),
     "instruments": ("XALUSD",),
     "controls": ("the same winters with no filling campaign, as the null",
                  "the global aluminium price path over the same quarters, which is the channel "
                  "this domain claims to be INDEPENDENT of",
                  "a matched hydropower-fed smelter elsewhere, separating 'hydro aluminium' "
                  "from 'Tajikistan'"),
     "notes": "THE EXOGENEITY IS THE WHOLE POINT: output set by a reservoir schedule is a "
              "supply shock uncontaminated by the metal price, which almost no metal story is"},
    {"id": "CCA-TM-A", "title": "Turkmenistan: gas volumes read from Chinese customs",
     "objects": ("China's monthly gas imports from Turkmenistan in volume and value",
                 "the implied border unit value, which is the price nobody publishes",
                 "the pipeline's seasonal delivery pattern",
                 "the Chinese substitution between Turkmen pipeline gas, Russian gas and LNG"),
     "conditions": ("the Chinese heating season",
                    "the LNG price relative to the implied pipeline price",
                    "whether the month carried a reported outage or contract event"),
     "instruments": ("XNGUSD", "USDCNH", "XBRUSD"),
     "controls": ("China's TOTAL gas import series, which is the demand-side null this "
                  "monopsony case absolutely requires",
                  "the Russian pipeline and LNG origin lines in the same tables, separating "
                  "'Turkmen supply' from 'Chinese demand'",
                  "the same months in years with no reported contract event"),
     "notes": "A MONOPSONIST'S PURCHASES LOOK LIKE THE SELLER'S SUPPLY AND ARE NOT. That "
              "warning is written into the domain rather than left for a reviewer to find"},
    {"id": "CCA-TM-B", "title": "Turkmenistan: a fixed rate with no information and a parallel "
                                "premium with all of it",
     "objects": ("the official rate, constant at 3.50 since 2015-01-01",
                 "the PRESS_REPORTED parallel rate from the exile outlets",
                 "the premium between them and its episodes",
                 "the cash-queue and import-shortage reporting that accompanies each episode"),
     "conditions": ("the premium bucket", "the gas export VALUE in the Chinese mirror",
                    "whether an import-licence or cash-rationing episode was reported"),
     "instruments": ("XNGUSD", "USDCNH"),
     "controls": ("periods of a narrow reported premium, as the null",
                  "the Chinese gas import VALUE series, which is the independent revenue read "
                  "the premium should respond to if the mechanism is real",
                  "a randomised-date null on the irregular reported observations"),
     "notes": "NO LAWFUL DOMESTIC GROUND EXISTS FOR THIS DOMAIN and the pack says so "
              "(NO_LAWFUL_GROUND); it runs on reported observations and a foreign mirror, and "
              "no cell here is promotable"},
    {"id": "CCA-N", "title": "The regional closure calendar: Nowruz, the Eids, and the year "
                             "they collide",
     "objects": ("the per-jurisdiction closure tables for 2024-2026",
                 "the CLOSURE BREADTH -- how many of the five are shut on a date",
                 "the 2026 collision, when Eid al-Fitr lands the day before Nowruz",
                 "Armenia's exception: no Nowruz, no Eid, and Christmas on 6 January"),
     "conditions": ("closure breadth (one of five against four of five)",
                    "whether the closure is a single day or a multi-day block",
                    "whether the year is a collision year"),
     "instruments": ("USDRUB", "XAUUSD", "USDTRY"),
     "controls": ("THE ARMENIAN CONTROL, which is the best one in this pack: on every Nowruz "
                  "and every Eid, four of the five are shut and Armenia is open, so the same "
                  "day is simultaneously a treatment and a control inside one region",
                  "the matched weekday 26 weeks away on the same instruments",
                  "the same dates in a non-collision year, for the 2026 arm"),
     "notes": "a binary holiday flag would throw away the whole mechanism here; BREADTH is the "
              "state, and Armenia's calendar is what makes it identifiable"},
    {"id": "CCA-E", "title": "The enforcement clock: designations, de-risking and re-routing",
     "objects": ("designation and package dates from 2022 onward",
                 "the 2023-12-22 exposure of foreign financial institutions",
                 "reported correspondent withdrawals and transfer-corridor closures",
                 "the partner-mix shift in the trade series afterwards"),
     "conditions": ("the corridor era",
                    "whether the announcement named a bank, a company or a commodity class",
                    "the jurisdiction's banking-system exposure"),
     "instruments": ("USDRUB", "EURRUB", "USDTRY", "USDCNH"),
     "controls": ("the same windows on the four nearest non-announcement weekdays",
                  "a matched non-corridor emerging market on the same dates, separating 'risk "
                  "off' from 'this announcement'",
                  "the VOLUME null: the claim is about partner MIX, so a volume-only test is "
                  "the wrong test and is run explicitly to show it finds nothing"),
     "notes": "THE MEASURABLE EFFECT IS A RE-ROUTING, NOT A SHUTDOWN, and the domain is written "
              "to test that rather than the headline claim that the flow stops"},
    {"id": "CCA-F", "title": "The regional energy balance: a gas exporter that became an "
                             "importer, and the winter deficit",
     "objects": ("the Uzbek gas balance and the year its sign flipped",
                 "the winter load-shedding episodes across Uzbekistan and Tajikistan",
                 "the Central Asia-China pipeline's seasonal deliveries",
                 "the power available to the region's two large metal loads"),
     "conditions": ("the winter months against the rest of the year",
                    "before or after the Uzbek balance reversed",
                    "whether a filling campaign or an outage was reported"),
     "instruments": ("XNGUSD", "XBRUSD", "XALUSD"),
     "controls": ("the same winters before the balance reversed, as the era control",
                  "the Chinese total gas import series, so a regional shortage is separated "
                  "from Chinese demand",
                  "summer months as the seasonal null"),
     "notes": "the domain that joins Uzbekistan's gas, Tajikistan's power and Turkmenistan's "
              "exports into one physical balance -- which is how the region actually works and "
              "is invisible to a single-country pack"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "cca_corridor_era_breaks", "domain_ids": ("CCA-A", "CCA-E"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.caucasus_central_asia.miners:corridor_era_breaks",
     "needs": ("CORRIDOR_START and CORRIDOR_ENFORCEMENT", "USDRUB, USDTRY, USDCNH H1 bars"),
     "notes": "two dated documents, three eras, and each era is the other's control"},
    {"name": "cca_remittance_month_end", "domain_ids": ("CCA-B",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.caucasus_central_asia.miners:remittance_month_end",
     "needs": ("remittance_window", "USDRUB, EURRUB, XAUUSD H1 bars"),
     "notes": "the mid-month placebo is built in, because a month-end effect is a calendar "
              "effect until it is told apart from one"},
    {"name": "cca_regional_closure_breadth", "domain_ids": ("CCA-N",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.caucasus_central_asia.miners:regional_closure_breadth",
     "needs": ("regional_holidays", "USDRUB, XAUUSD, USDTRY H1 bars"),
     "notes": "ARMENIA IS THE CONTROL ARM: four of five shut and one open on the same date"},
    {"name": "cca_sovereign_gold_supply", "domain_ids": ("CCA-C", "CCA-UZ-A", "CCA-KG-B"),
     "kind": "macro", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.caucasus_central_asia.miners:sovereign_gold_supply",
     "needs": ("CBU:reserves_gold", "STATKG:trade chapter 71", "XAUUSD H1/D1 bars"),
     "notes": "the valuation-only null is the first arm, because most of a reported reserve "
              "change is the price"},
    {"name": "cca_transmission_seeds",
     "domain_ids": ("CCA-A", "CCA-B", "CCA-C", "CCA-AM-B", "CCA-UZ-B", "CCA-KG-A", "CCA-TJ-B",
                    "CCA-TM-A", "CCA-TM-B", "CCA-F"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.caucasus_central_asia.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
    {"name": "cca_cells", "domain_ids": tuple(),
     "kind": "scouts", "cadence_s": 3600.0, "steerable": True, "wired": False,
     "entry": "countries.caucasus_central_asia.miners:emit_cells",
     "needs": ("CELLS",),
     "notes": "the pack's own cell mint: domains x executable instruments x named conditions, "
              "emitted to the gauntlet on the hour"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("CCA-AM-A", "CCA-UZ-A", "CCA-KG-A"),
    "release_surprise": ("CCA-A", "CCA-B", "CCA-C"),
    "calendar_settlement": ("CCA-B", "CCA-UZ-B"),
    "holiday_liquidity": ("CCA-N",),
    "positioning": ("CCA-KG-A",),
    "carry_funding": ("CCA-TJ-A", "CCA-TM-B"),
    "corporate_flow": ("CCA-AM-B", "CCA-TJ-B", "CCA-KG-B"),
    "institutional_flow": ("CCA-B", "CCA-C"),
    "equity_mechanics": ("CCA-AM-A",),
    "derivatives_expiry": ("CCA-A",),
    "failure": ("CCA-TM-B", "CCA-TJ-A"),
    "residual": ("CCA-E", "CCA-F"),
    "transfer": ("CCA-A", "CCA-E"),
    "scouts": ("CCA-TM-A", "CCA-F"),
    "session_microstructure": ("CCA-N", "CCA-KG-A"),
}


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "CCA-T1", "source": "CBA monthly non-commercial transfers by source country",
     "target": "USDRUB", "targets": ("USDRUB", "EURRUB"), "to_country": "regional", "sign": "-",
     "mechanism": "a published monthly household flow from Russia into a small open economy is "
                  "a rouble-selling order of known size arriving on a known date; the receiving "
                  "banks convert it, and the corridor's cost decides how much arrives at all",
     "horizon": "0 to 5 sessions after the release", "horizon_class": "multi_day",
     "lag_days": 1.0, "actor": "the Russian-origin remitter and the Armenian receiving bank",
     "constraint": "the corridor's fee, limit and correspondent availability",
     "flow": "cross-border household transfer converted into local currency",
     "condition": "a release whose Russia line deviates from its trailing trend by more than "
                  "its historical interquartile range",
     "control": "the same windows on non-release days; Georgia's own transfer release as the "
                "sibling shock with a different banking system",
     "falsifier": "release-day windows match the matched weekday-and-hour control on USDRUB and "
                  "EURRUB once the Russian domestic calendar is conditioned on",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CCA-T2", "source": "The EU/Turkey/China mirror gap against the five states' own "
                               "import and export tables",
     "target": "USDRUB", "targets": ("USDRUB", "USDTRY", "USDCNH"), "to_country": "regional",
     "sign": "+",
     "mechanism": "a widening mirror gap is physical trade being re-routed through the region; "
                  "the re-exporter must buy the origin currency and sell the destination one, "
                  "which is a standing directional FX demand at the corridor's two ends",
     "horizon": "1 to 2 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the re-export declarant and the Russian importer",
     "constraint": "the correspondent bank's willingness to clear the payment",
     "flow": "goods re-routed and the currency legs that pay for them",
     "condition": "a monthly mirror gap above its own pre-2022 distribution, by HS chapter",
     "control": "THE PRE-EXISTING CHINA-KYRGYZSTAN GAP, which is decades old and is the built-"
                "in placebo; plus a matched non-corridor state over the same months",
     "falsifier": "the mirror gap shows no step at 2022-02-24 once the pre-existing gap, the "
                  "commodity mix and the base effect are controlled for",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CCA-T3", "source": "CBU monthly gold tonnage change, separated from valuation",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "-",
     "mechanism": "a sovereign that buys domestic mine output in local currency and sells "
                  "bullion for dollars is a visible, recurring SUPPLY leg; the published "
                  "tonnage is the operation and the published value is the price",
     "horizon": "0 to 20 sessions after the reserve release", "horizon_class": "multi_day",
     "lag_days": 7.0, "actor": "the Central Bank of Uzbekistan as a seller of monetary gold",
     "constraint": "a fiscal need for dollars and a reserve position that is majority gold",
     "flow": "official bullion sale into the market",
     "condition": "a month whose tonnage fell by more than the valuation-only reconstruction "
                  "can explain",
     "control": "the valuation-only null; the World Gold Council series as an independent read; "
                "matched months with no tonnage change",
     "falsifier": "months of a genuine tonnage fall show no XAUUSD effect beyond the matched "
                  "control once the price-driven valuation change is removed",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T4", "source": "The Kyrgyz chapter-71 export line against Kumtor's production",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDCNH"), "to_country": "global", "sign": "+",
     "mechanism": "an export line far larger than domestic production is metal transiting "
                  "rather than being mined; the arithmetic gap is a conduit whose size is "
                  "published, and a conduit that large is a real change in where bullion moves",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Kyrgyz re-export declarant and the refining counterparties",
     "constraint": "refining capacity and the willingness of a counterparty to take the metal",
     "flow": "bullion transiting a jurisdiction that did not mine it",
     "condition": "a month whose chapter-71 export exceeds plausible domestic production by "
                  "more than the USGS estimate allows",
     "control": "the USGS production estimate as the independent denominator; Armenia's own "
                "chapter-71 line as the sibling conduit; pre-2022 months as the null",
     "falsifier": "months with an implausible export line show no difference in gold's "
                  "observable flows or price behaviour from months without one",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T5", "source": "NBKR same-day published FX auction (date, direction, volume)",
     "target": "USDRUB", "targets": ("USDRUB", "XAUUSD"), "to_country": "regional", "sign": "+",
     "mechanism": "a central bank selling dollars to hold a quasi-peg is meeting an import "
                  "demand it cannot refuse; the auction SIZE is the corridor's dollar demand "
                  "made visible weeks before any customs table",
     "horizon": "0 to 3 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the NBKR FX auction desk",
     "constraint": "reserves that are small relative to the corridor's gross flows",
     "flow": "official dollar sale into the domestic market",
     "condition": "an auction whose size is in the top quintile of its trailing distribution",
     "control": "matched non-auction days -- AND an explicit selection control, because the "
                "bank auctions precisely when the flow is large; pre-2022 auctions as the null",
     "falsifier": "large-auction days are indistinguishable from matched non-auction days once "
                  "the selection into auctioning is modelled",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T6", "source": "Armenian copper-molybdenum concentrate shipment quarters",
     "target": "XCUUSD", "targets": ("XCUUSD",), "to_country": "global", "sign": "-",
     "mechanism": "a concentrate shipper's quarterly programme changes the concentrate "
                  "available to smelters, which moves the treatment charge before it moves the "
                  "metal; the honest claim is about availability, not about the cathode price",
     "horizon": "1 quarter", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "Zangezur Copper-Molybdenum Combine as a concentrate shipper",
     "constraint": "a single export route through Georgia and a smelter-set treatment charge",
     "flow": "concentrate shipment into the smelter market",
     "condition": "a quarter whose shipped volume moves more than its trailing interquartile "
                  "range, or a quarter with a reported route interruption",
     "control": "a comparable small concentrate exporter over the same quarters; quarters with "
                "no shipment change; the refined-metal channel this edge does NOT claim",
     "falsifier": "quarters with a large Armenian shipment change show no move in the treatment-"
                  "charge benchmark or in XCUUSD beyond the matched control",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T7", "source": "Rogun filling campaigns and Vakhsh cascade winter rationing",
     "target": "XALUSD", "targets": ("XALUSD",), "to_country": "global", "sign": "+",
     "mechanism": "impounding a reservoir takes water away from generation; the smelter is the "
                  "interruptible load and is cut first, so a dam's construction schedule is an "
                  "aluminium supply event that is EXOGENOUS to the metal price",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the Rogun project office and Barqi Tojik as the winter power rationer",
     "constraint": "a snowmelt-driven inflow and a domestic demand that is served first",
     "flow": "electricity withheld from a smelter, and metal not produced",
     "condition": "an announced filling or commissioning campaign overlapping the winter "
                  "deficit months",
     "control": "the same winters with no filling campaign; the global aluminium price path, "
                "which this edge claims to be independent of; a matched hydro smelter elsewhere",
     "falsifier": "filling-campaign winters show no reduction in Tajik aluminium output or in "
                  "the industrial output index relative to non-campaign winters",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T8", "source": "China customs monthly gas imports from Turkmenistan by volume "
                               "and value",
     "target": "XNGUSD", "targets": ("XNGUSD", "USDCNH"), "to_country": "global", "sign": "-",
     "mechanism": "the pipeline is one of Asia's largest physical gas flows and is observable "
                  "only from the buyer's side; a delivered volume that falls short of the "
                  "seasonal norm is supply China must replace, and its replacement is LNG",
     "horizon": "0 to 20 sessions after the detailed customs tables",
     "horizon_class": "multi_day", "lag_days": 25.0,
     "actor": "Turkmengaz as seller and CNPC as monopsonist buyer",
     "constraint": "one pipeline, one customer, and a Chinese substitution decision",
     "flow": "pipeline gas delivered or not delivered, and the LNG that replaces it",
     "condition": "a month whose Turkmen volume deviates from its own seasonal norm by more "
                  "than its trailing interquartile range",
     "control": "CHINA'S TOTAL GAS IMPORT SERIES, which is the demand-side null this monopsony "
                "case requires; the Russian pipeline and LNG origin lines in the same tables",
     "falsifier": "Turkmen volume deviations are fully explained by Chinese total demand and "
                  "the LNG price, leaving nothing Turkmen-specific",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T9", "source": "The Turkmen parallel-market premium as reported by the exile "
                               "press",
     "target": "XNGUSD", "targets": ("XNGUSD", "USDCNH"), "to_country": "regional", "sign": "-",
     "mechanism": "where the official rate is a constant, the premium is the only continuous "
                  "reading of the state's hard-currency position; a widening premium says gas "
                  "revenue is not reaching the domestic economy, which precedes export and "
                  "import policy changes",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Turkmen informal money changer and the Central Bank's rationing window",
     "constraint": "an export revenue that comes from one customer and a fixed rate that "
                   "cannot absorb a shock",
     "flow": "hard currency rationed at the official window and cleared in the parallel market",
     "condition": "a reported premium crossing from one declared PREMIUM_BUCKET into a wider "
                  "one",
     "control": "narrow-premium periods as the null; the Chinese gas import VALUE series as the "
                "independent revenue read; a randomised-date null on the irregular observations",
     "falsifier": "the reported premium is uncorrelated with the independently measured gas "
                  "export value and with every gas-linked instrument",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T10", "source": "UzEX cotton fibre auction season and clearing prices",
     "target": "COTTON", "targets": ("COTTON",), "to_country": "global", "sign": "-",
     "mechanism": "the auction season IS the Uzbek crop reaching the market; after the state "
                  "order ended, the clearing price is set by buyers rather than administered, "
                  "which makes the season a real supply event for the first time",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Uzbek cotton cluster after the end of state procurement",
     "constraint": "water allocation and a domestic textile industry served first",
     "flow": "fibre auctioned and shipped",
     "condition": "an auction session in the October-to-March window whose cleared volume is in "
                  "the top quintile",
     "control": "the same calendar weeks in the pre-2020 state-order years, when the price was "
                "administered; a matched producer's auction calendar; the wheat rotation line",
     "falsifier": "auction-season weeks match the matched-week control on COTTON once the "
                  "global price path is conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T11", "source": "The Uzbek gas balance sign reversal and the winter deficit",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "regional", "sign": "+",
     "mechanism": "a regional exporter becoming an importer removes supply AND adds demand to "
                  "the same balance; the winter deficit then competes directly with the "
                  "region's industrial loads for the same molecules",
     "horizon": "the winter quarter", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "Uzbekneftegaz and the domestic winter load",
     "constraint": "an ageing field base and a subsidised domestic price",
     "flow": "gas imported rather than exported, and industrial load shed",
     "condition": "a winter month after the reversal, with reported load-shedding",
     "control": "the same winters before the reversal; the Chinese total import series; summer "
                "months as the seasonal null",
     "falsifier": "post-reversal winters show no difference in the region's gas-linked "
                  "observables from pre-reversal winters",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T12", "source": "Sanctions designation and enforcement announcement dates",
     "target": "USDRUB", "targets": ("USDRUB", "EURRUB", "USDTRY"), "to_country": "regional",
     "sign": "+",
     "mechanism": "an announcement does not stop the corridor, it moves it: correspondent banks "
                  "withdraw, transfer operators close a corridor, and the trade re-forms "
                  "through a different partner within a quarter -- so the measurable object is "
                  "the PARTNER MIX and not the volume",
     "horizon": "0 to 5 sessions for the price, 1 quarter for the mix",
     "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the sanctions-enforcement authority and the third-country correspondent bank",
     "constraint": "a jurisdiction that ends at its own border and a demand that does not",
     "flow": "payments refused and routes re-formed",
     "condition": "an announcement naming a bank or a financial-facilitation measure, as "
                  "opposed to one naming a single company",
     "control": "the four nearest non-announcement weekdays; a matched non-corridor emerging "
                "market on the same dates; THE VOLUME NULL, run explicitly to show it fails",
     "falsifier": "designation dates are followed by no partner-mix change in the five states' "
                  "trade within the quarter, once seasonality and commodity mix are controlled",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CCA-T13", "source": "Regional closure breadth: Nowruz, the two Eids and the 2026 "
                                "collision",
     "target": "USDRUB", "targets": ("USDRUB", "XAUUSD", "USDTRY"), "to_country": "regional",
     "sign": "-",
     "mechanism": "when four of five jurisdictions close at once the region's transfer, "
                  "conversion and customs plumbing stops for a multi-day block; the flow does "
                  "not vanish, it QUEUES and arrives afterwards, which is a displacement rather "
                  "than a disappearance",
     "horizon": "the closure block plus 3 sessions", "horizon_class": "multi_day",
     "lag_days": 0.0,
     "actor": "the transfer operators, the banks and the customs posts of four jurisdictions",
     "constraint": "a book that cannot be funded during the block is funded before or after it",
     "flow": "conversion and settlement displaced across a closure",
     "condition": "a date whose closure breadth is 3 or more of 5, and separately the 2026 "
                  "collision block",
     "control": "ARMENIA, WHICH IS OPEN ON EVERY ONE OF THOSE DAYS -- a treatment and a control "
                "inside the same region on the same date; the matched weekday 26 weeks away; "
                "the same dates in a non-collision year",
     "falsifier": "high-breadth closure blocks behave no differently from matched ordinary "
                  "weeks on the target instruments",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T14", "source": "The month-end remittance payout window across four labour "
                                "exporters",
     "target": "USDRUB", "targets": ("USDRUB", "EURRUB"), "to_country": "regional", "sign": "-",
     "mechanism": "Russian wages are paid around the month end and four Central Asian and "
                  "Caucasus economies convert them within days; the aggregate is a scheduled, "
                  "repeating, same-direction FX demand",
     "horizon": "the last weekday of the month to the second weekday of the next",
     "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Uzbek, Tajik, Kyrgyz and Armenian migrant households",
     "constraint": "the pay cycle, which is set by Russian employers and not by the migrants",
     "flow": "rouble sold and local currency bought, every month",
     "condition": "the declared month-end window, excluding months whose window overlaps a "
                  "high-breadth regional closure",
     "control": "the mid-month matched weekday-and-hour window; the PRE_CORRIDOR era, when the "
                "level was a fraction of today's; Georgia's own cycle",
     "falsifier": "month-end windows match the mid-month control on the rouble legs across all "
                  "four jurisdictions",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T15", "source": "The Tajik official-to-bureau spread as an FX stress state",
     "target": "USDRUB", "targets": ("USDRUB", "XALUSD"), "to_country": "regional", "sign": "+",
     "mechanism": "where a rate is administered the second price is the market; a widening "
                  "bureau spread says the remittance inflow has fallen short of the import "
                  "bill, which is a real-economy signal with a metal export on the other side",
     "horizon": "1 to 2 months", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the National Bank of Tajikistan and the licensed exchange bureau",
     "constraint": "reserves that are small against the remittance cycle",
     "flow": "hard currency rationed at the official rate and cleared at the bureau",
     "condition": "a reported spread crossing into a wider PREMIUM_BUCKET",
     "control": "tight-spread months as the null; the Kyrgyz som over the same months; a "
                "randomised-date null on the irregular PRESS_REPORTED observations",
     "falsifier": "wide-spread periods are indistinguishable from tight ones on the rouble and "
                  "aluminium legs",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T16", "source": "The region's grain import bill and the re-routed freight plane",
     "target": "WHEAT", "targets": ("WHEAT",), "to_country": "regional", "sign": "+",
     "mechanism": "all five are net grain importers supplied overwhelmingly from the Black Sea "
                  "and Kazakhstan; when the corridor's freight and payment plumbing is "
                  "disrupted the import cost rises without the world price moving, which is a "
                  "basis story and is declared as one",
     "horizon": "1 to 2 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the state grain buyers and the millers of the five",
     "constraint": "landlocked geography and a single rail plane",
     "flow": "grain imported over a constrained route",
     "condition": "a month with a reported rail, border or payment disruption on the grain route",
     "control": "the same months with no reported disruption; the Black Sea export price path, "
                "which this edge claims to be separate from; a matched landlocked importer",
     "falsifier": "disruption months show no change in the region's import unit values relative "
                  "to the world price, which would mean there is no basis effect to trade",
     "evidence": "HYPOTHESIS"},
    {"id": "CCA-T17", "source": "The INSTC and the southern leg: India, Iran and the five",
     "target": "USDINR", "targets": ("USDINR",), "to_country": "regional", "sign": "+",
     "mechanism": "the corridor has a southern branch through the International North-South "
                  "Transport Corridor; when the northern route tightens, volume and freight "
                  "attention shift south, which is a dated, reported re-routing with an Indian "
                  "counterparty at the end of it",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the freight forwarders and the Indian and Iranian route operators",
     "constraint": "port and rail capacity, and the payment problem the southern route shares",
     "flow": "cargo re-routed south when the northern leg tightens",
     "condition": "a quarter following a northern-route enforcement step",
     "control": "quarters with no enforcement step; the Indian trade series' own trend; the "
                "northern-route volume over the same quarters",
     "falsifier": "southern-route volumes show no response to northern-route enforcement steps",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the Uzbek dual-rate era", "start": "2005-01-01", "end": "2017-09-04",
     "regime": "the som had an official rate and a parallel rate that traded at a large "
               "multiple; conversion was rationed by licence, and every price, reserve figure "
               "and trade statistic in Uzbekistan depended on which rate it was struck at",
     "markers": ("a persistent parallel premium reported throughout",
                 "exchange-control rationing of conversion for enterprises"),
     "why_it_matters": "NO UZBEK SERIES MAY CROSS THIS BOUNDARY. A som value, a reserve figure "
                       "or a trade number before 2017-09-05 is not the same measurement as one "
                       "after it, and pooling them measures the accounting and not the economy",
     "status": "SETTLED"},
    {"name": "the Uzbek liberalisation", "start": "2017-09-05", "end": "2019-12-31",
     "regime": "on 2017-09-05 the som was freed and lost roughly half its value against the "
               "dollar IN ONE DAY, the dual rate was abolished and conversion was opened; the "
               "opening of the economy that followed is the reason Uzbekistan is mineable at all",
     "markers": ("2017-09-05 the float and the ~50% one-day devaluation",
                 "the progressive opening of trade and travel that followed"),
     "why_it_matters": "the single hardest regime break in this pack and the reason CCA-UZ-A "
                       "declares its sample start explicitly rather than taking whatever "
                       "history exists",
     "status": "SETTLED"},
    {"name": "the EAEU accession of Armenia and Kyrgyzstan", "start": "2015-01-02",
     "end": "2026-12-31",
     "regime": "Armenia acceded to the Eurasian Economic Union on 2015-01-02 and Kyrgyzstan on "
               "2015-08-12; from then their trade with Russia crosses NO CUSTOMS BORDER and is "
               "recorded through the union's own statistics rather than through customs "
               "declarations",
     "markers": ("2015-01-02 Armenia accedes", "2015-08-12 Kyrgyzstan accedes"),
     "why_it_matters": "this is WHY those two became the corridor's preferred routes, and it is "
                       "also why their Russia trade is not measured the same way as Uzbekistan's "
                       "-- a cross-jurisdiction comparison that ignores it compares two "
                       "different instruments",
     "status": "OPEN"},
    {"name": "the Turkmen fixed rate", "start": "2015-01-01", "end": "2026-12-31",
     "regime": "the manat was set at 3.50 to the US dollar on 2015-01-01 and has not moved "
               "since; exchange controls ration conversion and a parallel market has traded at "
               "a large multiple for most of the period",
     "markers": ("2015-01-01 the devaluation to 3.50 and the fix that followed",
                 "the progressive tightening of conversion access"),
     "why_it_matters": "a constant has no information; every Turkmen mechanism in this pack is "
                       "therefore built on the PREMIUM and on the Chinese mirror, never on the "
                       "official rate",
     "status": "OPEN"},
    {"name": "the end of the Uzbek cotton state order", "start": "2020-01-01",
     "end": "2026-12-31",
     "regime": "the state procurement quota for cotton was wound down and replaced by the "
               "cluster system, in which private clusters buy the crop at a negotiated price; "
               "the international boycott over forced labour was lifted in the same period",
     "markers": ("the abolition of the state order for the cotton crop",
                 "the lifting of the international cotton boycott"),
     "why_it_matters": "before this the Uzbek cotton price was administered and the auction did "
                       "not set it, so a study pooling the two eras is measuring two different "
                       "supply functions with the same name",
     "status": "OPEN"},
    {"name": "Kumtor under state external management", "start": "2021-05-17",
     "end": "2026-12-31",
     "regime": "the Kyrgyz state placed Kumtor under external management in May 2021 and the "
               "dispute with the former operator was settled the following year; production "
               "reporting moved from an audited listed-company disclosure to a state "
               "announcement",
     "markers": ("2021-05 the external-management law and the takeover [PRESS_REPORTED, "
                 "RE-VERIFY the exact date before any cell is compiled on it]",
                 "2022 the settlement with the former operator"),
     "why_it_matters": "the break is in the MEASUREMENT as much as in the ownership; the two "
                       "halves of the production series are not the same quantity and must "
                       "never be spliced",
     "status": "OPEN"},
    {"name": "the corridor SURGE", "start": "2022-02-24", "end": "2023-12-21",
     "regime": "from the invasion, re-exports to Russia rose by multiples, transfers from "
               "Russia multiplied, the dram appreciated about 20% in a year, Armenian and "
               "Tajik growth spiked, and enforcement friction was close to zero",
     "markers": ("2022-02-24 the invasion", "2022 the Armenian dram's ~20% appreciation",
                 "2022-2023 the Armenian and Kyrgyz gold and electronics re-export lines",
                 "2022-12 the Lachin corridor blockade begins",
                 "2023-09 the Nagorno-Karabakh population movement"),
     "why_it_matters": "this is the era every corridor statistic is measured in, and it is a "
                       "BOOM era; pooling it with what came after averages a boom with a "
                       "de-risking wave",
     "status": "SETTLED"},
    {"name": "the ENFORCEMENT era", "start": "2023-12-22", "end": "2026-12-31",
     "regime": "from 2023-12-22 foreign financial institutions were exposed to secondary "
               "sanctions for facilitating the trade; regional banks began refusing Russian-"
               "linked payments, correspondents withdrew, transfer corridors closed and "
               "re-opened elsewhere, and the flow RE-ROUTED rather than stopping",
     "markers": ("2023-12-22 the executive order exposing foreign financial institutions",
                 "2024 the wave of correspondent withdrawals and payment refusals across "
                 "Armenian, Kyrgyz, Uzbek and Turkish banks"),
     "why_it_matters": "the measurable object changes here: in the SURGE era it was VOLUME, and "
                       "in this era it is PARTNER MIX. A volume-only test of the enforcement "
                       "era finds nothing and concludes wrongly",
     "status": "OPEN"},
)

# --------------------------------------------------------------------------- constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "none of the five currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no UZS, KGS, TJS or TMT symbol and no "
                 "USD/AMD, USD/UZS, USD/KGS or USD/TJS cross",
     "consequence": "every domestic mechanism terminates in the rouble, lira, renminbi, metals, "
                    "energy or softs legs; the five currencies are INPUTS and never cells"},
    {"constraint": "THE ARMENIAN DRAM'S ISO CODE IS A SHARE CFD TICKER ON THIS BROKER",
     "measured": "the registry DOES hold a symbol called `AMD`, and its asset_class is "
                 "`Equities` -- it is Advanced Micro Devices, not the dram (measured on this "
                 "box 2026-09-23)",
     "consequence": "A TRAP WITH TWO SEPARATE FAILURE MODES, and a pack that wrote `AMD` into "
                    "its executable list would hit BOTH: it would put a single-name equity on "
                    "the docket against the two-lane order (2026-09-06), and it would believe "
                    "it was trading the currency this pack is about. The dram is ABSENT; `AMD` "
                    "is refused by name here and appears in no instrument tuple in this file"},
    {"constraint": "EURRUB's tape stops and USDRUB's is expensive and partly frozen",
     "measured": "the desk's own `ru` pack measured EURRUB's H1 bars ending 2022-02-28 and "
                 "USDRUB's recent spread at roughly 164 basis points with about a third of "
                 "hourly bars frozen",
     "consequence": "EURRUB and USDRUB are DECLARED EXECUTABLE HERE BECAUSE THEY ARE IN THE "
                    "BROKER REGISTRY, and every cell compiled on them must carry the `ru` "
                    "pack's measurement in its cost model; a corridor finding that does not "
                    "survive a 164bp cost is not a finding"},
    {"constraint": "Turkmenistan publishes no usable official statistics",
     "measured": "no machine-readable trade table, no monthly levels, no auditable reserve "
                 "series, and an exchange rate fixed since 2015-01-01",
     "consequence": "four source layers are DECLARED ABSENT for Turkmenistan with their "
                    "substitutes named (NO_LAWFUL_GROUND); every Turkmen quantity in this pack "
                    "comes from Chinese customs or is PRESS_REPORTED, and no Turkmen cell is "
                    "promotable"},
    {"constraint": "the Tajik licensed-bureau rate is not published anywhere",
     "measured": "the NBT publishes only the official rate; the bureau rate exists in press "
                 "reporting and in retail channels",
     "consequence": "CCA-TJ-A's state variable is PRESS_REPORTED; it may generate hypotheses "
                    "and may never promote a cell"},
    {"constraint": "UN Comtrade and the national trade tables BACKFILL",
     "measured": "reporters file on their own clocks and restate within the year; today's "
                 "database is not the database that existed at the time",
     "consequence": "every mirror-statistics cell is NOT_PIT_SAFE until a stamped vintage of "
                    "BOTH reporter and partner is held; this is the largest PIT trap in the "
                    "pack and is declared rather than discovered"},
    {"constraint": "the gas border price and the concentrate treatment charge are LICENSED",
     "measured": "Argus, ICIS, Fastmarkets and CRU terms forbid machine extraction; registered "
                 "machine_use_allowed=false",
     "consequence": "the price legs of CCA-TM-A and CCA-AM-B are UNMEASURED; the pack uses the "
                    "Chinese customs implied unit value and the exchange-quoted metal instead "
                    "and says so"},
    {"constraint": "the NBKR auctions precisely when the flow it reveals is large",
     "measured": "the auction is a discretionary response to market conditions, not a scheduled "
                 "event",
     "consequence": "CCA-KG-A's event study is CONTAMINATED BY SELECTION by construction; the "
                    "control must model the decision to auction, and an uncorrected study here "
                    "will find an effect whether or not one exists"},
    {"constraint": "no COT or exchange positioning exists for any of the five currencies",
     "measured": "no future, option or COT contract on any exchange the desk can read",
     "consequence": "regional currency positioning is UNMEASURED and is never proxied by the "
                    "RUB or CNH legs, which are positions in the corridor's counterparties"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "CBA monthly non-commercial money transfers by source country",
    "NBKR same-day FX auction results", "CBU monthly gold tonnage and value",
    "China customs monthly gas imports by origin",
    "UN Comtrade and Eurostat mirror export series to the five",
    "the transfer operators' published corridor, fee and limit changes")
SERIES: dict[str, str] = {
    "CCA_AM_TRANSFERS": "CBA:transfers_by_country", "CCA_AM_RATE": "CBA:official_rate",
    "CCA_AM_TRADE": "ARMSTAT:trade_by_partner", "CCA_AM_COPPER": "ARMSTAT:hs26_exports",
    "CCA_UZ_GOLD": "CBU:reserves_gold", "CCA_UZ_RATE": "CBU:main_rate",
    "CCA_UZ_TRADE": "STATUZ:trade", "CCA_UZ_COTTON": "UZEX:cotton_auction",
    "CCA_KG_AUCTION": "NBKR:fx_auction", "CCA_KG_TRADE": "STATKG:trade",
    "CCA_KG_GOLD": "KYRGYZALTYN:production",
    "CCA_TJ_RATE": "NBT:official_rate", "CCA_TJ_REMIT": "NBT:remittances",
    "CCA_TJ_ALU": "TALCO:production",
    "CCA_TM_GAS": "CHINACUSTOMS:gas_imports_tm",
    "CCA_TM_PREMIUM": "PRESS:tm_parallel_premium",
    "CCA_MIRROR": "COMTRADE:mirror", "CCA_EAEU": "EAEU:intra_trade",
    "CCA_WGC": "WGC:official_holdings",
}

# --------------------------------------------------------------------------- interactions
#: HOW THIS PACK MEETS ITS NEIGHBOURS. The desk stops testing each country in isolation here:
#: every row names another pack, the shared mechanism, the observable that joins them and the
#: control that keeps the two apart. THE FOUR SIBLING PACKS OF THIS COMMAND ARE ALL NAMED --
#: `ru`, `kz`, `az` and `ge` -- because this pack is their complement and not their repeat.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "ru",
     "mechanism": "RUSSIA IS THE DEMAND SIDE OF THIS PACK'S CENTRAL MECHANISM. The corridor "
                  "exists because Russian buyers need goods and Russian employers pay migrant "
                  "wages; the `ru` pack holds the demand and the rouble, this pack holds the "
                  "route and the recipients",
     "observable": "the five states' Russia-bound export lines and their transfer inflows from "
                   "Russia, read against Russia's own import and migration series",
     "targets": ("USDRUB", "EURRUB"),
     "control": "a matched non-corridor emerging market on the same dates, so 'Russia risk' is "
                "separated from 'the corridor'; and the `ru` pack's own measured USDRUB cost "
                "and frozen-bar share, which bound what any corridor cell can claim"},
    {"with": "kz",
     "mechanism": "KAZAKHSTAN IS THE SAME CORRIDOR'S LARGEST PIPE AND IS ALREADY WRITTEN. This "
                  "pack deliberately does NOT restate it: Kazakh re-export, the National Fund's "
                  "announced FX sales and the CPC crude route belong to `kz`. What joins them "
                  "is that a Kazakh tightening displaces volume into Kyrgyzstan and Uzbekistan "
                  "and vice versa, which makes each the other's substitution control",
     "observable": "the partner-mix split of EU/China exports between Kazakhstan and the five, "
                   "month by month and chapter by chapter",
     "targets": ("USDRUB", "USDCNH", "XAUUSD"),
     "control": "the pre-2022 split between the same partners, which is the substitution "
                "pattern that existed before the corridor and is the placebo for it"},
    {"with": "az",
     "mechanism": "AZERBAIJAN IS THE PEGGED HALF OF THE CAUCASUS AND ARMENIA IS THE FLOATING "
                  "HALF. Two neighbours, one shared shock in 2022, and opposite currency "
                  "regimes: the dram appreciated about 20% on the flow while the manat sat at "
                  "1.7000 and the State Oil Fund's auctions absorbed the adjustment instead",
     "observable": "the AMD's realised move against the AZN's zero, and the SOFAZ auction "
                   "volumes against the CBA's published interventions, over the same months",
     "targets": ("USDRUB", "USDTRY", "XBRUSD"),
     "control": "THE NATURAL EXPERIMENT IS THE PAIR: same region, same shock, different regime "
                "-- so each country is the other's counterfactual, and neither alone identifies "
                "the regime's effect"},
    {"with": "ge",
     "mechanism": "GEORGIA IS THE SIBLING REMITTANCE OBSERVATORY AND THE ONLY EXPORT ROUTE "
                  "ARMENIA HAS. Two published monthly transfer series by origin, two small open "
                  "economies, one shared 2022 shock -- and every tonne of Armenian concentrate "
                  "leaves through Georgian rail and port",
     "observable": "the two monthly transfer-by-country releases side by side, and Georgian "
                   "port and rail throughput against Armenian chapter-26 exports",
     "targets": ("USDRUB", "USDTRY", "XCUUSD"),
     "control": "Georgia's series is the control for every Armenian transfer claim and vice "
                "versa; a move present in both is a CIS remittance-cycle fact and belongs to "
                "neither country"},
    {"with": "tr",
     "mechanism": "TURKEY IS THE CORRIDOR'S OTHER END AND ITS MIRROR TWIN. Turkish exports to "
                  "these five rose in the same chapters in the same months, Turkish banks took "
                  "the same correspondent pressure, and the lira is the region's stress leg",
     "observable": "Turkish export series to the five by chapter against the five's import "
                   "tables, and the dates of Turkish bank payment refusals",
     "targets": ("USDTRY", "EURTRY"),
     "control": "Turkey's own trade trend with the rest of the world over the same months, "
                "separating 'Turkish exports grew' from 'Turkish exports to the corridor grew'"},
    {"with": "cn",
     "mechanism": "CHINA IS BOTH THE MONOPSONIST AT THE TURKMEN BORDER AND THE ORIGIN OF THE "
                  "GOODS THE BAZAARS RE-EXPORT -- and, decisively for this pack, IT IS THE "
                  "PUBLISHER OF THE ONLY LAWFUL TURKMEN GAS NUMBERS ANYWHERE",
     "observable": "China customs imports by origin (gas from Turkmenistan) and exports by "
                   "destination (goods to Kyrgyzstan and Uzbekistan), monthly",
     "targets": ("XNGUSD", "USDCNH"),
     "control": "China's total gas import and total export series, which is the demand-side "
                "null every monopsony and mirror claim in this pack has to clear first"},
)


# --------------------------------------------------------------------------- the cells
#: WHAT EACH DOMAIN MINTS. A cell is a domain x an executable instrument x a NAMED CONDITION
#: this pack's own data plane can actually evaluate -- never a cartesian blow-up of nothing.
#: Every domain therefore declares the mechanism family its cells belong to, the horizon they
#: are judged at, and the one control that must run beside every one of them; the conditions
#: come from the domain's own `conditions` tuple, so a condition nobody wrote does not exist.
DOMAIN_CELL_SPEC: dict[str, dict[str, str]] = {
    "CCA-A": {"family": "mirror_statistics", "horizon": "multi_day",
              "control": "the pre-existing mirror gap plus a matched non-corridor state"},
    "CCA-B": {"family": "seasonal_flow", "horizon": "multi_day",
              "control": "the mid-month matched weekday-and-hour window"},
    "CCA-C": {"family": "official_flow", "horizon": "multi_day",
              "control": "the valuation-only reconstruction of the reported change"},
    "CCA-AM-A": {"family": "external_balance", "horizon": "multi_day",
                 "control": "the block-shuffled transfer series, plus Georgia over the same "
                            "months"},
    "CCA-AM-B": {"family": "physical_supply", "horizon": "multi_day",
                 "control": "quarters with no shipment change, plus a comparable concentrate "
                            "exporter"},
    "CCA-UZ-A": {"family": "official_flow", "horizon": "multi_day",
                 "control": "the valuation-only null plus the World Gold Council cross-check"},
    "CCA-UZ-B": {"family": "auction", "horizon": "multi_day",
                 "control": "the same weeks in the pre-2020 state-order years"},
    "CCA-KG-A": {"family": "intervention", "horizon": "intraday",
                 "control": "matched non-auction days WITH an explicit selection correction"},
    "CCA-KG-B": {"family": "physical_supply", "horizon": "multi_day",
                 "control": "the USGS production estimate as the independent denominator"},
    "CCA-TJ-A": {"family": "parallel_market", "horizon": "multi_day",
                 "control": "tight-spread months plus the Kyrgyz som over the same months"},
    "CCA-TJ-B": {"family": "physical_supply", "horizon": "multi_day",
                 "control": "winters with no filling campaign, plus the global metal price path"},
    "CCA-TM-A": {"family": "mirror_statistics", "horizon": "multi_day",
                 "control": "China's TOTAL gas import series as the demand-side null"},
    "CCA-TM-B": {"family": "parallel_market", "horizon": "multi_day",
                 "control": "narrow-premium periods plus the Chinese gas import value series"},
    "CCA-N": {"family": "holiday_liquidity", "horizon": "multi_day",
              "control": "ARMENIA, open on every Nowruz and Eid, plus the weekday 26 weeks away"},
    "CCA-E": {"family": "event_reaction", "horizon": "multi_day",
              "control": "the four nearest non-announcement weekdays plus the volume null"},
    "CCA-F": {"family": "physical_supply", "horizon": "multi_day",
              "control": "the same winters before the balance reversed, plus the summer null"},
}


def _slug(text: str) -> str:
    """A short, stable token for a condition, so a cell id is readable and reproducible."""
    keep = [ch.lower() if ch.isalnum() else "_" for ch in str(text)]
    tok = "".join(keep).strip("_")
    while "__" in tok:
        tok = tok.replace("__", "_")
    return tok[:44].strip("_")


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints, as the cross product of its domains, its EXECUTABLE
    instruments and its own named conditions.

    THE POINT OF A PACK IS CELLS REACHING THE ONE GAUNTLET. This function is where that number
    comes from, and it is maximised HONESTLY: a domain contributes only the instruments it
    actually names AND that are in `EXECUTABLE_INSTRUMENTS`, and only the conditions it wrote
    down, so every cell here names a real state the pack's own data plane can evaluate. A cell
    whose condition nobody can compute is not breadth, it is a bill the shared multiple-testing
    budget pays for nothing.
    """
    execset = set(EXECUTABLE_INSTRUMENTS)
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        spec = DOMAIN_CELL_SPEC.get(did, {})
        for sym in dom["instruments"]:
            if sym not in execset:
                continue
            for cond in dom["conditions"]:
                out.append({
                    "cell_id": f"{CODE.lower()}:{did}:{sym}:{_slug(cond)}",
                    "domain": did, "symbol": sym, "condition": str(cond),
                    "mechanism_family": spec.get("family", "residual"),
                    "horizon": spec.get("horizon", "multi_day"),
                    "control": spec.get("control", "the matched weekday-and-hour window"),
                    "why": f"{dom['title']} -- conditioned on {cond}",
                })
    return tuple(out)


#: The minted cells, computed once at import so a caller never pays for the cross product twice.
CELLS: tuple[dict[str, Any], ...] = cells()

#: WHAT THIS PACK CLAIMS ABOUT ITS OWN DEPTH, so a test can measure the claim rather than take
#: it. The framework's `regional_parity.DEPTH_TARGETS` are the FLOOR (12 actors, 10 domains,
#: 8 edges, 10 layers, 40 terms, 8 datasets, 4 eras, 6 instruments); a five-jurisdiction pack
#: written to the floor would be five countries at a fifth of the depth each, which is why the
#: numbers below are the ones the tests assert and they sit well above it.
DECLARED_DEPTH: dict[str, int] = {
    "actors": 20, "domains": 14, "edges": 12, "layers": 10, "terms": 120, "datasets": 18,
    "eras": 6, "instruments": 10, "sources": 24, "cells": 60, "interactions": 4,
    "jurisdictions": 5,
}


def declared_depth() -> dict[str, int]:
    """What the pack actually has, in the same keys `DECLARED_DEPTH` promises."""
    return {"actors": len(ACTORS), "domains": len(DOMAINS),
            "edges": len(TRANSMISSION_EDGES_SEED),
            "layers": source_layer_coverage()["n_layers_covered"], "terms": term_count(),
            "datasets": len(DATASETS), "eras": len(POLICY_ERAS),
            "instruments": len(EXECUTABLE_INSTRUMENTS),
            "sources": len([s for s in SOURCE_CLASSES
                            if not str(s["id"]).startswith("absent_")]),
            "cells": len(CELLS), "interactions": len(INTERACTIONS),
            "jurisdictions": len(JURISDICTIONS)}


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
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "jurisdictions": JURISDICTIONS, "currencies": CURRENCIES,
        "roster_jurisdictions": ROSTER_JURISDICTIONS, "beyond_roster": BEYOND_ROSTER,
        "central_banks": CENTRAL_BANKS, "no_lawful_ground": NO_LAWFUL_GROUND,
        "query_territories": QUERY_TERRITORIES, "interactions": INTERACTIONS,
        "cells": CELLS, "corridor_eras": CORRIDOR_ERAS, "nowruz_days": NOWRUZ_DAYS,
        "nowruz_absent": NOWRUZ_ABSENT, "islamic_feasts": ISLAMIC_FEASTS,
        "decreed_moves": DECREED_MOVES, "premium_buckets": PREMIUM_BUCKETS,
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
    """The framework's HolidayRule shape: every closed weekday the rule produces for 2024-2026,
    across all five jurisdictions, plus the fixed month-days every one of them keeps."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in FIXED_NATIONAL.values() for m, d, _ in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": (5, 6),
            "notes": HOLIDAYS_RULE["authority"]}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion
    reads best: sources as rows AND as tagged lines, positioning and miners as strings, the
    holiday rule as dates, absent layers as a mapping."""
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


# --------------------------------------------------------------------------- the department
def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure python, no network, no LLM, no heavy import.

    It reads this pack's own tables and emits one row per transmission edge and one per minted
    cell through the department Ctx when a Ctx is given; with no Ctx it emits nothing and simply
    returns the report, which is what makes it safe to call from a test. Everything the pack
    knows it CANNOT measure on this box is returned by name in `unmeasured`, because an absence
    that is not named reads as a zero (L1.28a).
    """
    at = date.today().isoformat()
    rows: list[dict[str, Any]] = []
    for e in TRANSMISSION_EDGES_SEED:
        rows.append({"kind": "transmission_seed", "id": str(e["id"]),
                     "targets": tuple(e["targets"]), "sign": str(e["sign"]),
                     "horizon_class": str(e["horizon_class"]),
                     "evidence": str(e["evidence"]), "mechanism": str(e["mechanism"])[:240],
                     "control": str(e["control"])[:240], "falsifier": str(e["falsifier"])[:240]})
    for c in CELLS:
        rows.append({"kind": "cell", "id": str(c["cell_id"]), "domain": str(c["domain"]),
                     "symbol": str(c["symbol"]), "condition": str(c["condition"])[:160],
                     "mechanism_family": str(c["mechanism_family"]),
                     "horizon": str(c["horizon"]), "control": str(c["control"])[:160]})

    unmeasured: list[str] = []
    for row in NO_LAWFUL_GROUND:
        unmeasured.append(f"{row['jurisdiction']}:{row['layer']}: NO LAWFUL GROUND -- "
                          f"{row['reason'][:160]} || substitute: {row['substitute'][:120]}")
    if not CENTRAL_BANK["decision_dates"]:
        unmeasured.append("uz:central_bank.decision_dates: UNMEASURED -- the CBU publishes its "
                          "Board calendar and this pack refuses to type dates it has not "
                          "fetched; every CCA-UZ-A event arm is UNMEASURED until the collector "
                          "stamps them")
    for key, bank in CENTRAL_BANKS.items():
        if not bank.get("decision_dates"):
            unmeasured.append(f"{key}:central_bank.decision_dates: UNMEASURED -- "
                              f"{str(bank.get('dates_status') or '')[:140]}")
    unmeasured.append("regional:mirror_vintages: every mirror-statistics cell is NOT_PIT_SAFE "
                      "until a stamped vintage of BOTH reporter and partner is held; Comtrade "
                      "and the national tables backfill")
    unmeasured.append("tj:bureau_rate and tm:parallel_rate: PRESS_REPORTED only -- hypotheses "
                      "may be generated and no cell compiled on them may be promoted")

    emitted = 0
    if ctx is not None:
        emit = getattr(ctx, "record", None) or getattr(ctx, "emit", None)
        note = getattr(ctx, "note", None)
        if callable(emit):
            for row in rows:
                try:
                    emit(source_id=f"{CODE.lower()}:pack", mechanism=row["id"], payload=row)
                except TypeError:
                    emit(row)
                emitted += 1
        if callable(note):
            for why in unmeasured:
                note(f"{CODE.lower()}:unmeasured", why)
    return {"code": CODE.lower(), "name": NAME, "at": at,
            "jurisdictions": tuple(JURISDICTIONS),
            "roster_jurisdictions": tuple(ROSTER_JURISDICTIONS),
            "beyond_roster": tuple(sorted(BEYOND_ROSTER)),
            "emitted": emitted, "rows": rows,
            "cells_emitted": len(CELLS), "edges": len(TRANSMISSION_EDGES_SEED),
            "datasets": len(DATASETS), "actors": len(ACTORS), "domains": len(DOMAINS),
            "sources": len([s for s in SOURCE_CLASSES
                            if not str(s["id"]).startswith("absent_")]),
            "layers_covered": source_layer_coverage()["n_layers_covered"],
            "terms": term_count(), "interactions": len(INTERACTIONS),
            "unmeasured": unmeasured,
            "dry_run": ctx is None}
