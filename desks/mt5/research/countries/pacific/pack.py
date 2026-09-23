"""THE PACIFIC ISLANDS: rationed currencies, counted cargoes, and the first Monday on earth.

WHAT THIS REGION IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER AUSTRALIA. Australia's
pack next door reads an ocean of traded consensus: an interbank cash-rate future, a published
port tonnage, a regulated hedge ratio. NOTHING HERE IS TRADED. Seven sovereigns, none of whose
currencies this broker quotes, none of whose exchanges has a CFD, and whose entire executable
surface is what they SHIP and who they BORROW FROM. Five things belong to this region and to no
other in the desk's book, and each one is why a domain below exists.

  1. PAPUA NEW GUINEA RATIONS DOLLARS. The kina is a crawl-like peg with a CHRONIC FX BACKLOG:
     importers queue at the commercial banks for months to have an order filled, so the posted
     interbank rate is not a clearing price and the QUEUE is the real exchange rate. The IMF ECF
     approved in March 2023 requires a SCHEDULED crawl toward a market-clearing rate, which makes
     the depreciation a published administrative calendar rather than a market outcome. No other
     economy in this book has a rationed currency with a programme timetable attached, and PGK is
     not on the broker, so the mechanism is read outward through what PNG cannot buy.

  2. PNG LNG IS ONE PLANT AND ITS OUTAGES ARE DATED. ExxonMobil's PNG LNG runs about 8-9 mtpa
     against long-term SPAs indexed to the JAPAN CRUDE COCKTAIL with a lag of roughly three
     months, so the revenue leg is oil and the volume leg is a single train that stops for
     earthquakes, landowner blockades and states of emergency. The TotalEnergies-led Papua LNG
     FID is the next step function. One plant, one berth at Caution Bay, one loading programme:
     this is the most countable energy flow in the desk's southern hemisphere.

  3. NICKEL IS A POLITICAL VARIABLE HERE, NOT A MINING ONE. New Caledonia holds roughly a tenth
     of world nickel reserves across SLN (Doniambo), KNS (usine du Nord) and Prony (usine du Sud),
     and the riots that began on 13 May 2024 shut output, put KNS on care and maintenance and
     moved the LME. The Solomon Islands' nickel prospects sit behind the same licence politics.
     A nickel supply shock in this region arrives as a CIVIL-ORDER date, not a production report.

  4. FIJI IS A BASKET PEG BOLTED TO A CRUSHING SEASON AND AN ARRIVALS SEASON. The Reserve Bank
     of Fiji publishes a monthly policy statement and holds the FJD to a USD/AUD/NZD/JPY/EUR
     basket, so the FJD is an index of its trading partners rather than a price. Underneath it
     the Fiji Sugar Corporation crushes cane from June to December against a European reference
     price it lost, and tourism -- about two fifths of GDP, overwhelmingly Australian and New
     Zealand arrivals -- makes AUDUSD and NZDUSD the honest executable legs of a Fijian shock.

  5. THE REGION OPENS FIRST. It spans UTC+10 (Port Moresby) to UTC+13, and Samoa and Tonga sit
     ACROSS the dateline: Apia reaches 08:00 on Monday three hours before Sydney's FX week opens.
     Every weekend event this pack cares about -- a cyclone landfall, a mine shutdown, a state of
     emergency, a kina notice -- is public and being acted on by Pacific institutions BEFORE the
     first quote exists. That is a microstructure mechanism no other regional pack owns.

WHAT IS EXECUTABLE AND WHAT IS NOT. PGK, FJD, SBD, VUV, XPF, WST and TOP are absent from
`data/universe/universe.json`; so are the PNGX and SPX equity indices, the LME nickel contract's
own book, JKM, the JCC index and every tuna contract -- because no tuna contract exists anywhere.
Each is named in `TRANSMISSION_TARGETS` with the broker symbols its mechanism reaches, so an
absent instrument produces a transmission hypothesis and never a cell that can never be filled
(L1.49). The PNA Vessel Day Scheme is declared an INPUT-ONLY mechanism for exactly that reason.

THE TWO-LANE ORDER. Pacific market commentary is company-shaped -- BSP Financial, Oil Search,
Santos, Newmont, Glencore, Eramet -- and every one of those is an EVENT-lane instrument. They
enter this pack only as ACTORS, and the instruments those actors move are energy, metals, softs
and the AUD/NZD complex. No share CFD appears in any instrument tuple in this file.

MULTI-COUNTRY DISCIPLINE. This is one pack for seven jurisdictions, so every actor, domain and
dataset NAMES ITS COUNTRY in its id or its `country` field. A row that says only "the Pacific"
when it means Fiji is a regional blur, and a blur cannot be falsified.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "PACIFIC"
NAME = "the Pacific Islands (PNG, Fiji, Solomon Islands, Vanuatu, New Caledonia, Samoa, Tonga)"
REGION_COMMAND = "oceania"          # the framework's command; the sibling packs are au and nz
REGION_DESK = "OCEANIA"
FOREST = "oceania"
#: The anchor currency is PNG's, the region's largest economy; the other six are declared beside
#: it because a single `currency` field cannot describe seven sovereigns.
CURRENCY = "PGK"
CURRENCIES: dict[str, str] = {
    "PGK": "Papua New Guinea kina -- crawl-like peg, rationed, IMF-ECF scheduled crawl",
    "FJD": "Fiji dollar -- pegged to a USD/AUD/NZD/JPY/EUR basket by the Reserve Bank of Fiji",
    "SBD": "Solomon Islands dollar -- pegged to a trade-weighted basket by the CBSI",
    "VUV": "Vanuatu vatu -- basket peg, Reserve Bank of Vanuatu",
    "XPF": "CFP franc -- FIXED to the euro at 1 EUR = 119.33174 XPF; New Caledonia's currency "
           "carries euro-area monetary policy with no local transmission at all",
    "WST": "Samoan tala -- basket peg, Central Bank of Samoa",
    "TOP": "Tongan pa'anga -- basket peg, National Reserve Bank of Tonga",
}
#: PNG's fiscal year is the calendar year. Fiji's ends 31 JULY (moved from December in 2016) and
#: New Caledonia runs the French calendar year; both are declared rather than averaged away.
FISCAL_YEAR_END = "12-31"
FISCAL_YEARS: dict[str, str] = {
    "PG": "12-31 (calendar year; the Budget is handed down in late November)",
    "FJ": "07-31 (moved from 31 December in 2016; the Budget lands in late June)",
    "SB": "12-31", "NC": "12-31 (French public accounting year)", "VU": "12-31",
}
NATIVE_LANGUAGES: tuple[str, ...] = ("en", "tpi", "ho", "fj", "hif", "fr")
COT_CURRENCY = ""                  # no CFTC contract exists for any Pacific currency
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"   # BPNG and RBF exchange control forbid outward margin
MISSION = ("mine the Pacific as the rationed-currency, single-cargo, politically-interrupted "
           "region it is: PNG's FX backlog and its one LNG plant, the New Caledonia and Solomon "
           "nickel shocks, Fiji's basket peg, crushing season and arrivals, the PNA tuna cartel "
           "that has no contract, the cyclone season, and the first Monday on earth")

#: Fifteen broker-quotable instruments a Pacific mechanism actually reaches. None is an equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XNGUSD", "XBRUSD",                  # PNG LNG: the volume leg and the oil-indexed price leg
    "USDJPY",                            # the JCC-indexed SPA leg: PNG LNG is sold into Japan
    "XAUUSD", "XCUUSD",                  # Porgera, Lihir, Ok Tedi, Gold Ridge
    "XAUAUD",                            # the gold leg in the currency PNG's miners report in
    "XNIUSD",                            # New Caledonia (SLN/KNS/Prony) and Solomon nickel
    "SUGAR", "SUGARRAW",                 # the Fiji Sugar Corporation crushing season
    "COFARA", "UKCOCOA",                 # PNG highlands arabica; Solomon and Vanuatu cocoa
    "AUDUSD", "NZDUSD", "AUDNZD",        # the proxy currencies, the aid leg, the arrivals leg
    "AUS200",                            # the equity index the region's trade and aid settle into
)

#: What this region's mechanisms are ABOUT that this broker does not quote. Each row names the
#: universe symbols its mechanism reaches instead.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "PGK/USD interbank rate and the BPNG-posted kina reference",
     "venue": "BPNG / the commercial banks", "country": "PG",
     "why": "the currency PAC-PNG-A and PAC-PNG-B are about; absent from the broker, and in any "
            "case not a clearing price while the import queue exists",
     "proxies": ("AUDUSD", "XAUUSD", "XNGUSD")},
    {"name": "The BPNG foreign exchange order backlog (months of import cover queued)",
     "venue": "BPNG / bank trade-finance desks", "country": "PG",
     "why": "THE REAL EXCHANGE RATE: the queue length, not the posted rate, is what an importer "
            "faces; its collapse under the ECF crawl is the region's largest single experiment",
     "proxies": ("AUDUSD", "XAUUSD")},
    {"name": "FJD nominal effective rate against the RBF's five-currency basket",
     "venue": "Reserve Bank of Fiji", "country": "FJ",
     "why": "the FJD is an index of Fiji's trading partners; a Fijian shock is therefore read on "
            "the partners themselves, weighted the way the basket weights them",
     "proxies": ("AUDUSD", "NZDUSD", "USDJPY")},
    {"name": "Japan Crude Cocktail (JCC) customs-cleared crude price",
     "venue": "Japan METI customs statistics", "country": "PG",
     "why": "PNG LNG's long-term SPAs are indexed to JCC with roughly a quarter's lag, so the "
            "plant's revenue follows a LAGGED oil average and not the spot gas print",
     "proxies": ("XBRUSD", "USDJPY", "XNGUSD")},
    {"name": "Platts JKM and the North Asian LNG spot market",
     "venue": "Platts", "country": "PG",
     "why": "the uncontracted PNG LNG cargoes price off JKM; XNGUSD is Henry Hub and only a weak "
            "proxy, which every gas edge in this pack states on its face",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "LME nickel official settlement and the Indonesian NPI/matte complex",
     "venue": "LME / Shanghai", "country": "NC",
     "why": "XNIUSD is a broker CFD on the LME leg, not the LME book; the NPI complex is where a "
            "New Caledonia outage is absorbed or is not, and it is unquotable here",
     "proxies": ("XNIUSD", "XCUUSD")},
    {"name": "PNGX (Port Moresby) and SPX (South Pacific Stock Exchange, Suva) indices",
     "venue": "PNGX Markets / SPX", "country": "PG, FJ",
     "why": "no CFD is quoted on either; both are thin domestic boards whose largest names are "
            "banks and telcos, and under the two-lane order they are actors, never instruments",
     "proxies": ("AUS200", "AUDUSD")},
    {"name": "Ok Tedi, Porgera, Lihir and Gold Ridge quarterly production and shipments",
     "venue": "operator and State reports", "country": "PG, SB",
     "why": "a counted physical metal flow with a dated interruption history; the executable leg "
            "is the global metal, and the production report is the observable",
     "proxies": ("XAUUSD", "XCUUSD", "XAUAUD")},
    {"name": "PNA Vessel Day Scheme: days allocated, days sold, the benchmark price per day",
     "venue": "Parties to the Nauru Agreement / FFA", "country": "PG, SB, regional",
     "why": "A CARTEL WITH NO CONTRACT. The PNA auctions purse-seine fishing days and sets a "
            "floor price; it is a genuine forced-flow actor, but NO TUNA INSTRUMENT EXISTS on "
            "any venue the desk reaches, so this is declared INPUT-ONLY and reaches the market "
            "only through the members' fiscal balances and the aid/AUD channel",
     "proxies": ("AUDUSD", "NZDUSD")},
    {"name": "Fiji Sugar Corporation cane payment and the EU preferential reference price",
     "venue": "FSC / European Commission", "country": "FJ",
     "why": "Fiji's sugar was sold into a European price that no longer exists after the 2017 "
            "quota end; the residual crop is priced off the world raw market instead",
     "proxies": ("SUGARRAW", "SUGAR")},
    {"name": "PNG arabica Y-grade and Smallholder differentials to ICE arabica",
     "venue": "PNG Coffee Industry Corporation / exporters", "country": "PG",
     "why": "PNG highlands arabica is a real washed-arabica origin whose differential widens when "
            "the highlands highway closes; COFARA is the contract the differential is quoted on",
     "proxies": ("COFARA", "COFROB")},
    {"name": "Australian PALM scheme worker numbers and Pacific remittance corridors",
     "venue": "Australian DEWR / World Bank Remittance Prices", "country": "regional",
     "why": "seasonal labour mobility is a MEASURABLE remittance clock for Vanuatu, Samoa, Tonga "
            "and Fiji, and it settles in AUD and NZD, which is where it becomes executable",
     "proxies": ("AUDUSD", "NZDUSD", "AUDNZD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Papua New Guinea -- the Monetary Policy Statement and the Kina Facility Rate",
    "short": "BPNG",
    "framework": "crawling_peg",
    "committee": "the Governor under the Central Banking Act 2000 as amended in 2021-22, advised "
                 "by the Monetary Policy Committee; there is no published vote and no minutes",
    "policy_instrument": "the Kina Facility Rate (KFR), the signalling rate for the domestic "
                         "money market, alongside Central Bank Bill auctions, the Cash Reserve "
                         "Requirement and -- the instrument that actually binds -- the "
                         "administered allocation of foreign exchange to the banks",
    "mandate": "price stability and the stability of the financial system; the 2021-22 amendments "
               "added an independent board and a formal monetary policy committee",
    "decision_rule": "a MONETARY POLICY STATEMENT twice a year, required by the Central Banking "
                     "Act to be published by 31 March and by 30 September; the KFR is announced "
                     "monthly between them and is usually unchanged for long runs",
    "decision_calendar_rule": "the two statutory MPS deadlines (31 March, 30 September) are the "
                              "anchor a miner may derive; the KFR announcement day varies within "
                              "the month and must be stamped from the BPNG release, never assumed",
    "decision_dates": (
        "2024-03-28", "2024-09-30", "2025-03-31", "2025-09-30", "2026-03-31", "2026-09-30"),
    "dates_status": "THESE ARE THE STATUTORY DEADLINES, NOT CONFIRMED RELEASE MINUTES. The Act "
                    "fixes 31 March and 30 September; the actual publication can land days "
                    "earlier. A cell compiled on one of these dates is re-stamped from the BPNG "
                    "press release or reported UNMEASURED (L1.28a). The MONTHLY KFR dates are "
                    "NOT LISTED because the pack refuses to invent them.",
    "decision_time_utc": "00:00",
    "announce_local": "morning Pacific/Port_Moresby (UTC+10, no DST); the minute varies",
    "dst_rule": "Papua New Guinea keeps UTC+10 all year; the UTC minute of a Port Moresby event "
                "never moves. Bougainville keeps UTC+11.",
    "minutes_lag_days": 0,
    "publication_classes": ("monetary_policy_statement", "quarterly_economic_bulletin",
                            "kfr_announcement", "annual_report", "fx_market_notice",
                            "financial_stability_report"),
    "policy_rate_series": "BPNG:kfr",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the Central Bank Bill and Treasury Bill auction cut-offs between "
                       "statements, and the ADB/IMF Article IV projections; there is no survey "
                       "of economists for PNG and no traded curve at all",
    "consensus_proxy_trap": "the T-bill cut-off is set in a market where the banks hold excess "
                            "kina they CANNOT convert, so a falling yield is a symptom of the FX "
                            "queue rather than an easing expectation; reading it as a rate "
                            "expectation inverts the mechanism",
    "reserves_clock": "BPNG publishes gross foreign reserves in the Quarterly Economic Bulletin "
                      "and in monthly balance-sheet tables; an IMF ECF disbursement or a World "
                      "Bank budget-support loan appears as a single step",
    "programme": "IMF Extended Credit Facility approved in March 2023 (with an Extended Fund "
                 "Facility component), whose structural benchmarks include a SCHEDULED CRAWL of "
                 "the kina toward a market-clearing rate and the clearance of the FX backlog; "
                 "the reviews are the region's only hard policy calendar",
    "off_cycle": ("the June 2014 introduction of the kina trading band, which created the "
                  "backlog this pack is largely about",),
    "root": "https://www.bankpng.gov.pg",
}

#: The region's other monetary authorities. Not folded into CENTRAL_BANK: a pack with one
#: `central_bank` slot and seven sovereigns must say so rather than pretend Fiji is a PNG branch.
OTHER_CENTRAL_BANKS: tuple[dict[str, Any], ...] = (
    {"name": "Reserve Bank of Fiji", "short": "RBF", "country": "FJ", "framework": "peg",
     "instrument": "the Overnight Policy Rate, held at 0.25% since March 2020",
     "decision_rule": "a MONTHLY Monetary Policy Statement, normally released on the last "
                      "Thursday of the month after the Board meets; the two objectives the RBF "
                      "names are adequate foreign reserves and low inflation, in that order",
     "peg": "the FJD is held against a basket of the USD, AUD, NZD, JPY and EUR; the weights are "
            "reviewed and not continuously published, so the NEER is the object and the "
            "bilateral rate is not",
     "root": "https://www.rbf.gov.fj"},
    {"name": "Central Bank of Solomon Islands", "short": "CBSI", "country": "SB",
     "framework": "peg", "instrument": "Bokolo Bills and the CBSI basket peg",
     "decision_rule": "a quarterly Monetary Policy Statement and a monthly economic bulletin",
     "peg": "the SBD is held against a trade-weighted basket dominated by the USD and AUD",
     "root": "https://www.cbsi.com.sb"},
    {"name": "Institut d'emission d'Outre-Mer (IEOM) for New Caledonia",
     "short": "IEOM", "country": "NC", "framework": "peg",
     "instrument": "none of its own: the CFP franc is FIXED to the euro at 1 EUR = 119.33174 XPF",
     "decision_rule": "no local monetary policy exists; the ECB's decisions pass through "
                      "unaltered, which makes New Caledonia a euro-area monetary economy with a "
                      "nickel terms-of-trade shock and no exchange-rate valve",
     "peg": "irrevocably fixed to the euro; the parity is set by French decree",
     "root": "https://www.ieom.fr"},
)

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BPNG daily kina interbank and TT reference rates",
     "local": "posted after the Port Moresby interbank close, about 16:00 Pacific/Port_Moresby",
     "time_utc": "06:00", "time_utc_dst": "06:00", "dst_rule": "none (UTC+10 all year)",
     "instruments": ("AUDUSD", "XAUUSD"), "window_minutes": 60, "country": "PG",
     "why": "the official kina reference the customs, the mining royalties and the banks read; "
            "it is a POSTED rate and not a clearing rate while the import queue exists"},
    {"name": "RBF daily exchange rate fixing against the five-currency basket",
     "local": "published each morning, about 09:00 Pacific/Fiji", "time_utc": "21:00",
     "time_utc_dst": "21:00", "dst_rule": "none since Fiji abandoned DST in 2021",
     "instruments": ("AUDUSD", "NZDUSD", "USDJPY"), "window_minutes": 60, "country": "FJ",
     "why": "the FJD's daily basket strike; it lands 21:00 UTC the PREVIOUS calendar day, which "
            "is the single easiest alignment error in this region"},
    {"name": "LME nickel official settlement (second ring)",
     "local": "the official prices are struck around 13:15-13:25 Europe/London",
     "time_utc": "13:15", "time_utc_dst": "12:15", "dst_rule": "GMT/BST",
     "instruments": ("XNIUSD",), "window_minutes": 30, "country": "NC",
     "why": "the price a New Caledonia outage is finally expressed in; the UTC minute MOVES twice "
            "a year and a fixed-UTC window puts half the sample in the wrong bar"},
    {"name": "LBMA gold price PM auction",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAUAUD"), "window_minutes": 15,
     "country": "PG",
     "why": "the reference Lihir, Porgera and Ok Tedi doré is settled against"},
    {"name": "ICE No. 11 raw sugar settlement",
     "local": "about 13:00 America/New_York", "time_utc": "18:00", "time_utc_dst": "17:00",
     "dst_rule": "EST/EDT", "instruments": ("SUGARRAW", "SUGAR"), "window_minutes": 30,
     "country": "FJ",
     "why": "the world raw price Fiji's crop fell back onto when the EU quota ended in 2017"},
    {"name": "Japan METI customs-cleared crude (JCC) monthly publication",
     "local": "provisional customs statistics mid-month, Asia/Tokyo",
     "time_utc": "00:00", "time_utc_dst": "00:00", "dst_rule": "none (Japan keeps UTC+9)",
     "instruments": ("XBRUSD", "USDJPY"), "window_minutes": 120, "country": "PG",
     "why": "the index PNG LNG's long-term SPAs are struck on, with about a quarter's lag; the "
            "lag IS the mechanism and a contemporaneous regression destroys it"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "PNG LNG monthly cargo nomination and lifting window", "kind": "day_of_month",
     "days": (1, 2, 3, 4, 5), "roll": "next", "window_utc": ("22:00", "06:00"),
     "instruments": ("XNGUSD", "XBRUSD"), "country": "PG",
     "why": "the following month's lifting programme is fixed in the opening business days; a "
            "missed cargo is visible at Caution Bay before it is visible in any statistic"},
    {"name": "Fiji sugar crushing season (June to December)", "kind": "day_of_month",
     "days": (1, 15), "months": (6, 7, 8, 9, 10, 11, 12), "roll": "next",
     "window_utc": ("20:00", "23:00"), "instruments": ("SUGARRAW", "SUGAR"), "country": "FJ",
     "why": "the mills crush only in season; the out-of-season months are the placebo the "
            "seasonal study is measured against, not a gap in the data"},
    {"name": "PNG quarterly mine production and shipment reports", "kind": "quarter_end",
     "roll": "next", "window_utc": ("22:00", "06:00"),
     "instruments": ("XAUUSD", "XCUUSD", "XAUAUD"), "country": "PG",
     "why": "Ok Tedi, Porgera and Lihir report quarterly; an interruption already known from the "
            "press is CONFIRMED here in tonnes, which is the only PIT-safe form of it"},
    {"name": "PNG fiscal year end (31 December) and the November Budget", "kind": "fiscal_year_end",
     "roll": "previous", "window_utc": ("22:00", "06:00"), "instruments": ("AUDUSD", "XNGUSD"),
     "country": "PG",
     "why": "the Budget and the Final Budget Outcome date the State's dividend from the LNG and "
            "mining projects and the size of the next year's FX demand"},
    {"name": "PNA Vessel Day Scheme annual allocation and the December trading window",
     "kind": "month_end", "months": (12,), "roll": "previous", "window_utc": ("20:00", "23:00"),
     "instruments": ("AUDUSD", "NZDUSD"), "country": "regional",
     "why": "members trade unused days between themselves at the year end; the benchmark price "
            "set for the following year is the cartel's single administered number"},
    {"name": "Cyclone season months (November to April)", "kind": "day_of_month", "days": (1,),
     "months": (11, 12, 1, 2, 3, 4), "roll": "next", "window_utc": ("18:00", "23:00"),
     "instruments": ("SUGARRAW", "XNIUSD", "XNGUSD"), "country": "regional",
     "why": "a physically-clocked interruption window for cane, nickel ore loading and LNG "
            "berthing; the other six months are the control period"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "PNGX Markets (Port Moresby Stock Exchange)", "index_symbols": (), "country": "PG",
     "open_local": "10:00 Pacific/Port_Moresby", "close_local": "12:00",
     "open_utc": "00:00", "close_utc": "02:00", "dst_rule": "none (UTC+10)",
     "auction": "a single daily call; there is no continuous book",
     "expiry_rule": "no derivatives are listed",
     "holidays": "PNG public holidays",
     "notes": "about a dozen listings dominated by banks, telcos and the dual-listed resource "
              "names; NO CFD IS QUOTED, and under the two-lane order the listings are actors"},
    {"name": "South Pacific Stock Exchange (SPX), Suva", "index_symbols": (), "country": "FJ",
     "open_local": "09:30 Pacific/Fiji", "close_local": "12:30",
     "open_utc": "21:30", "close_utc": "00:30", "dst_rule": "none since 2021",
     "auction": "continuous within a short session, very thin",
     "expiry_rule": "no derivatives are listed",
     "holidays": "Fiji public holidays",
     "notes": "the STI index has no CFD; SPX exists in this pack as the venue Fiji's own capital "
              "cannot leave, which is part of why the basket peg is defensible at all"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "pac_dateline_first_light", "start_utc": "19:00", "end_utc": "21:00",
     "notes": "Apia and Nuku'alofa (UTC+13) are already at 08:00 on the new day and Suva "
              "(UTC+12) reaches it an hour later; the FX week has not opened yet"},
    {"name": "pac_week_open_gap", "start_utc": "21:00", "end_utc": "23:00",
     "notes": "Wellington and Sydney open the week here; this is the first bar that can price "
              "a Pacific weekend event that has been public for three hours"},
    {"name": "pac_pom_morning", "start_utc": "22:00", "end_utc": "23:59",
     "notes": "08:00-10:00 Port Moresby: BPNG notices, the banks' FX allocations and the mine "
              "and LNG announcements land here"},
    {"name": "pac_suva_noumea_morning", "start_utc": "20:00", "end_utc": "22:00",
     "notes": "08:00 Suva (UTC+12) and 07:00 Noumea (UTC+11): RBF statements and the New "
              "Caledonia nickel and civil-order news of the day"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "BPNG Monetary Policy Statement (semi-annual)", "cadence": "quarterly",
     "time_utc": "00:00", "source": "Bank of Papua New Guinea",
     "actual_series": "BPNG:kfr", "expected_series": "UNMEASURED",
     "notes": "statutory by 31 March and 30 September; carries the FX-backlog and crawl language"},
    {"name": "BPNG Quarterly Economic Bulletin (QEB)", "cadence": "quarterly", "time_utc": "00:00",
     "source": "Bank of Papua New Guinea", "actual_series": "BPNG:qeb_reserves",
     "expected_series": "UNMEASURED",
     "notes": "the reserves, the trade account and the mineral export tables; published with a "
              "lag of a quarter or more, so it CONFIRMS and never leads"},
    {"name": "PNG National Statistical Office CPI (quarterly)", "cadence": "quarterly",
     "time_utc": "00:00", "source": "PNG National Statistical Office", "actual_series": "NSO:cpi",
     "expected_series": "UNMEASURED",
     "notes": "quarterly, not monthly, and often months late; an imported-inflation print in a "
              "rationed-FX economy measures the queue as much as the world price"},
    {"name": "Reserve Bank of Fiji monthly Monetary Policy Statement and Economic Review",
     "cadence": "monthly", "time_utc": "21:00", "source": "Reserve Bank of Fiji",
     "actual_series": "RBF:opr", "expected_series": "UNMEASURED",
     "notes": "normally the last Thursday; the reserves and months-of-import-cover line is what "
              "actually moves, because the OPR has not moved since March 2020"},
    {"name": "Fiji Bureau of Statistics visitor arrivals by source market", "cadence": "monthly",
     "time_utc": "21:00", "source": "Fiji Bureau of Statistics", "actual_series": "FBOS:arrivals",
     "expected_series": "UNMEASURED",
     "notes": "the Australian and New Zealand lines are the ones that carry the mechanism; "
              "arrivals are about two fifths of GDP once indirect effects are counted"},
    {"name": "Fiji Sugar Corporation weekly crush and sugar-made report", "cadence": "weekly",
     "time_utc": "21:00", "source": "Fiji Sugar Corporation", "actual_series": "FSC:crush_weekly",
     "expected_series": "UNMEASURED",
     "notes": "in season only (June-December); a week with no crush is a MILL STOPPAGE and not a "
              "zero, and the distinction is the whole of PAC-FJ-B"},
    {"name": "ISEE and DIMENC New Caledonia monthly nickel production and exports",
     "cadence": "monthly", "time_utc": "07:00", "source": "ISEE / DIMENC (Nouvelle-Caledonie)",
     "actual_series": "DIMENC:nickel_exports", "expected_series": "UNMEASURED",
     "notes": "ore, matte and ferronickel split by plant; the 2024 collapse is visible here "
              "months before any annual statistic"},
    {"name": "Japan METI customs-cleared crude price (JCC)", "cadence": "monthly",
     "time_utc": "00:00", "source": "Japan Ministry of Economy, Trade and Industry",
     "actual_series": "METI:jcc", "expected_series": "n/a",
     "notes": "provisional then final; the SPA index for PNG LNG, applied with a lag"},
)

# --------------------------------------------------------------------------- holidays
#: FOUR STATUTORY CALENDARS, NOT ONE. PNG, Fiji, Solomon Islands and New Caledonia each legislate
#: their own closures, and Samoa and Tonga add a fifth and sixth on the other side of the
#: dateline. A single "Pacific calendar" would close Suva for PNG Independence Day and open
#: Noumea on Bastille Day, and both errors invent or delete a whole business day.
FIXED_PG: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (2, 26, "Grand Chief Sir Michael Somare Remembrance Day"),
    (7, 23, "National Remembrance Day"),
    (8, 26, "National Repentance Day"),
    (9, 16, "Independence Day"),
    (12, 25, "Christmas Day"), (12, 26, "Boxing Day"),
)
FIXED_FJ: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"), (9, 7, "Constitution Day"), (10, 10, "Fiji Day"),
    (12, 25, "Christmas Day"), (12, 26, "Boxing Day"),
)
FIXED_SB: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"), (7, 7, "Independence Day"),
    (12, 25, "Christmas Day"), (12, 26, "National Day of Thanksgiving"),
)
FIXED_VU: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"), (2, 21, "Father Walter Lini Day"), (3, 5, "Custom Chiefs' Day"),
    (5, 1, "Labour Day"), (7, 30, "Independence Day"), (10, 5, "Constitution Day"),
    (11, 29, "Unity Day"), (12, 25, "Christmas Day"),
)
FIXED_NC: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Jour de l'An"), (5, 1, "Fete du Travail"), (5, 8, "Victoire 1945"),
    (7, 14, "Fete nationale"), (8, 15, "Assomption"), (9, 24, "Fete de la Citoyennete"),
    (11, 1, "Toussaint"), (11, 11, "Armistice"), (12, 25, "Noel"),
)
FIXED_WS_TO: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"), (4, 25, "Anzac Day"), (6, 1, "Samoa Independence Day"),
    (6, 4, "Tonga Emancipation Day"), (11, 4, "Tonga Constitution Day"),
    (12, 25, "Christmas Day"), (12, 26, "Boxing Day"),
)

#: FIJI'S TWO MOVING FEASTS, DECLARED RATHER THAN COMPUTED. Diwali follows the Hindu lunisolar
#: calendar and Prophet Mohammed's Birthday the Hijri one; both are set by gazette notice, and
#: Fiji's Mondayisation rule can move the observed day again. Each row carries its status: a
#: PROJECTED row may be a day out, and a cell compiled on one is re-stamped or reported
#: UNMEASURED rather than pooled with a reported one (L1.28a).
FJ_MOVING: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 9, 16), "Prophet Mohammed's Birthday (Fiji)", "REPORTED"),
           (date(2024, 10, 31), "Diwali (Fiji)", "REPORTED")),
    2025: ((date(2025, 9, 5), "Prophet Mohammed's Birthday (Fiji)", "REPORTED"),
           (date(2025, 10, 20), "Diwali (Fiji)", "REPORTED")),
    2026: ((date(2026, 8, 25), "Prophet Mohammed's Birthday (Fiji)", "PROJECTED"),
           (date(2026, 11, 8), "Diwali (Fiji)", "PROJECTED")),
}

#: One-off closures a government declared that no rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 1, 11): "PNG: the 14-day state of emergency declared for the National Capital "
                       "District after the 10 January 2024 unrest",
    date(2024, 5, 14): "New Caledonia: the state of emergency and curfew declared after the "
                       "13 May 2024 riots; Noumea's commerce and the Doniambo plant stopped",
}


def easter_sunday(year: int) -> date:
    """Easter Sunday by the anonymous Gregorian algorithm. Four of the six calendars here hang
    off it, and Whit Monday and Ascension hang off Easter in turn."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lag = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lag) // 451
    month, day = divmod(h + lag - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of a month -- the shape PNG's King's Birthday takes."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    """The LAST `weekday` of a month -- Fiji's Ratu Sir Lala Sukuna Day."""
    day = date(year, month, 28)
    while (day + timedelta(days=7)).month == month:
        day += timedelta(days=7)
    return day - timedelta(days=(day.weekday() - weekday) % 7)


def mondayise(day: date) -> date:
    """Fiji's substitution rule: a public holiday falling on a Saturday or Sunday is observed on
    the following Monday. PNG has NO such rule, which is why the two functions differ."""
    if day.weekday() == 5:
        return day + timedelta(days=2)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def png_holidays(year: int) -> dict[date, str]:
    """Papua New Guinea's Public Holidays Act calendar. No weekend substitution."""
    easter = easter_sunday(year)
    out: dict[date, str] = {date(year, m, d): n for m, d, n in FIXED_PG}
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter - timedelta(days=1)] = "Easter Saturday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[nth_weekday(year, 6, 0, 2)] = "King's Birthday (second Monday in June)"
    return dict(sorted(out.items()))


def fiji_holidays(year: int) -> dict[date, str]:
    """Fiji's calendar, WITH Mondayisation applied to every fixed day and to the moving feasts."""
    easter = easter_sunday(year)
    out: dict[date, str] = {}
    for m, d, n in FIXED_FJ:
        out[mondayise(date(year, m, d))] = n
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter - timedelta(days=1)] = "Easter Saturday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[last_weekday(year, 5, 0)] = "Ratu Sir Lala Sukuna Day (last Monday in May)"
    for day, name, status in FJ_MOVING.get(year, ()):
        out[mondayise(day)] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def solomon_holidays(year: int) -> dict[date, str]:
    """Solomon Islands. Whit Monday is Easter + 50 days and is a statutory closure here."""
    easter = easter_sunday(year)
    out: dict[date, str] = {date(year, m, d): n for m, d, n in FIXED_SB}
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[easter + timedelta(days=50)] = "Whit Monday"
    out[nth_weekday(year, 6, 4, 2)] = "King's Birthday (June)"
    return dict(sorted(out.items()))


def vanuatu_holidays(year: int) -> dict[date, str]:
    """Vanuatu. Father Walter Lini Day and Custom Chiefs' Day are its own; the rest is Easter."""
    easter = easter_sunday(year)
    out: dict[date, str] = {date(year, m, d): n for m, d, n in FIXED_VU}
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[easter + timedelta(days=39)] = "Ascension Day"
    return dict(sorted(out.items()))


def new_caledonia_holidays(year: int) -> dict[date, str]:
    """New Caledonia runs the FRENCH calendar plus its own Fete de la Citoyennete on 24 September.
    There is no Mondayisation in French law: a holiday on a Saturday is simply lost."""
    easter = easter_sunday(year)
    out: dict[date, str] = {date(year, m, d): n for m, d, n in FIXED_NC}
    out[easter + timedelta(days=1)] = "Lundi de Paques"
    out[easter + timedelta(days=39)] = "Ascension"
    out[easter + timedelta(days=50)] = "Lundi de Pentecote"
    return dict(sorted(out.items()))


def samoa_tonga_holidays(year: int) -> dict[date, str]:
    """Samoa and Tonga, the two jurisdictions EAST of the dateline. Their Monday begins before
    anyone else's, and their Sunday closure is close to total."""
    easter = easter_sunday(year)
    out: dict[date, str] = {date(year, m, d): n for m, d, n in FIXED_WS_TO}
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[nth_weekday(year, 10, 0, 2)] = "White Monday (Samoa)"
    return dict(sorted(out.items()))


#: The six calendars, by ISO country code, so a study can ask ONE jurisdiction rather than the
#: union. `WS_TO` carries Samoa and Tonga together because their dateline position is the fact.
JURISDICTIONS: tuple[str, ...] = ("PG", "FJ", "SB", "VU", "NC", "WS_TO")


def jurisdiction_holidays(code: str, year: int) -> dict[date, str]:
    """One jurisdiction's closures. An unknown code returns {} rather than the union."""
    if code == "PG":
        return png_holidays(year)
    if code == "FJ":
        return fiji_holidays(year)
    if code == "SB":
        return solomon_holidays(year)
    if code == "VU":
        return vanuatu_holidays(year)
    if code == "NC":
        return new_caledonia_holidays(year)
    if code == "WS_TO":
        return samoa_tonga_holidays(year)
    return {}


def national_holidays(year: int) -> dict[date, str]:
    """Every closure in the region, each TAGGED with the jurisdictions that close. A day closed
    in PNG and open in Fiji is one fact, not two, and the tag is what keeps it one."""
    tagged: dict[date, list[str]] = {}
    names: dict[date, str] = {}
    for code in JURISDICTIONS:
        for day, name in jurisdiction_holidays(code, year).items():
            tagged.setdefault(day, []).append(code)
            names.setdefault(day, name)
    for day, why in DECLARED_CLOSURES.items():
        if day.year == year:
            tagged.setdefault(day, []).append("DECLARED")
            names[day] = why
    return {day: f"{names[day]} [{'/'.join(sorted(set(tagged[day])))}]"
            for day in sorted(tagged)}


def market_holidays(year: int) -> dict[date, str]:
    """The weekday closures only. A Saturday holiday closes no board anywhere in the region, and
    counting one is how a liquidity study invents a session that never existed."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def holidays(year: int) -> dict[str, str]:
    """The region's closure table for one year as `{"YYYY-MM-DD": name}`."""
    return {d.isoformat(): n for d, n in national_holidays(year).items()}


def is_market_holiday(day: date, code: str = "") -> bool:
    """True when the day is closed -- in one jurisdiction if `code` is given, anywhere if not."""
    if code:
        return day in jurisdiction_holidays(code, day.year)
    return day in market_holidays(day.year)


def cyclone_season(year: int) -> tuple[date, date]:
    """The South Pacific cyclone season that OPENS in `year`: 1 November to 30 April."""
    return (date(year, 11, 1), date(year + 1, 4, 30))


HOLIDAY_YEARS: tuple[int, ...] = (2024, 2025, 2026)
HOLIDAY_TABLE: dict[int, dict[str, str]] = {y: holidays(y) for y in HOLIDAY_YEARS}

HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_multi_jurisdiction",
    "rule": (
        "SIX STATUTORY CALENDARS IN ONE REGION, COMPUTED PER JURISDICTION AND THEN TAGGED. "
        "(1) PAPUA NEW GUINEA, Public Holidays Act: New Year 1 Jan, Grand Chief Sir Michael "
        "Somare Remembrance Day 26 Feb, Good Friday / Easter Saturday / Easter Monday from the "
        "Gregorian Easter, King's Birthday on the SECOND MONDAY IN JUNE, National Remembrance "
        "Day 23 Jul, National Repentance Day 26 Aug, INDEPENDENCE DAY 16 SEP, Christmas 25 Dec "
        "and Boxing Day 26 Dec. PNG HAS NO WEEKEND SUBSTITUTION: a holiday on a Saturday is "
        "lost. (2) FIJI: New Year, Good Friday / Easter Saturday / Easter Monday, Ratu Sir Lala "
        "Sukuna Day on the LAST MONDAY IN MAY, Prophet Mohammed's Birthday and Diwali by GAZETTE "
        "NOTICE (declared in the table, never computed), Constitution Day 7 Sep, FIJI DAY 10 "
        "OCT, Christmas and Boxing Day -- and Fiji DOES Mondayise: a holiday on a Saturday or "
        "Sunday is observed on the following Monday. (3) SOLOMON ISLANDS: New Year, Good Friday, "
        "Easter Monday, WHIT MONDAY at Easter+50, King's Birthday in June, Independence Day 7 "
        "Jul, Christmas and the National Day of Thanksgiving 26 Dec. (4) VANUATU: New Year, "
        "Father Walter Lini Day 21 Feb, Custom Chiefs' Day 5 Mar, Easter, Ascension at "
        "Easter+39, Labour Day 1 May, Independence Day 30 Jul, Constitution Day 5 Oct, Unity Day "
        "29 Nov, Christmas. (5) NEW CALEDONIA runs the FRENCH calendar -- 1 Jan, Lundi de "
        "Paques, 1 May, 8 May, Ascension, Lundi de Pentecote, 14 Jul, 15 Aug, 1 Nov, 11 Nov, 25 "
        "Dec -- PLUS its own Fete de la Citoyennete on 24 SEPTEMBER, and French law substitutes "
        "nothing. (6) SAMOA AND TONGA sit EAST OF THE DATELINE at UTC+13: Anzac Day 25 Apr, "
        "Samoa Independence 1 Jun, Tonga Emancipation 4 Jun, White Monday on the second Monday "
        "in October, Tonga Constitution Day 4 Nov, Christmas and Boxing Day. "
        "THE DATELINE IS PART OF THE RULE, NOT A FOOTNOTE: Samoa and Tokelau moved ACROSS the "
        "line at the end of 29 December 2011 to sit with Australia and New Zealand rather than "
        "with the United States, so Samoa and Tonga reach any given calendar date BEFORE every "
        "other market on earth. A closure in Apia is already in force while Sydney is still on "
        "the previous day, and a UTC-keyed holiday mask that ignores this marks the wrong bar."),
    "authority": "the PNG Public Holidays Act and National Gazette; the Fiji Public Holidays Act "
                 "and Government Gazette (which alone sets Diwali and the Prophet's Birthday); "
                 "the Solomon Islands Public Holidays Act; the Vanuatu Public Holidays Act; the "
                 "French Code du travail as applied in New Caledonia plus the local 24 September "
                 "holiday; the Samoan and Tongan public holidays Acts",
    "years": HOLIDAY_YEARS,
    "weekend": "Saturday and Sunday across the region; Sunday closure in Samoa, Tonga and much "
               "of the Solomons is close to total and is a social fact as well as a legal one",
    "table": HOLIDAY_TABLE,
    "status": {
        2024: "COMPUTED for the fixed and Easter-derived days; the two Fijian moving feasts are "
              "REPORTED and must be re-verified against the Fiji Government Gazette",
        2025: "COMPUTED for the fixed and Easter-derived days; the Fijian moving feasts REPORTED",
        2026: "COMPUTED for the fixed and Easter-derived days. THE FIJIAN MOVING FEASTS ARE "
              "PROJECTED: Diwali 2026 falls on a Sunday and is Mondayised here, and the "
              "Prophet's Birthday is a Hijri estimate that may move by a day in either "
              "direction. A cell landing on one is re-stamped from the gazette or UNMEASURED.",
    },
    "moving_feasts": "Easter (and Whit Monday, Ascension, Easter Saturday) is computed; Diwali "
                     "and Prophet Mohammed's Birthday in Fiji are DECLARED from FJ_MOVING and "
                     "never computed, because the gazette and not the almanac fixes the day",
    "substitution": "FIJI MONDAYISES, PNG AND NEW CALEDONIA DO NOT. The divergence is the single "
                    "calendar fact this region gets wrong most often: 10 October 2026 is a "
                    "SATURDAY, so Fiji Day is observed on Monday 12 October 2026, while PNG's "
                    "Independence Day 2026-09-16 is a Wednesday and stands on its own day.",
    "market_effect": "NOTHING PACIFIC IS QUOTED ON THIS ACCOUNT, so a Pacific closure is an "
                     "OBSERVABILITY OUTAGE and not a liquidity regime: no BPNG notice, no RBF "
                     "statement, no FSC crush report, no DIMENC export line. A missing day is "
                     "UNMEASURED by name and is never a zero. The carriers -- AUDUSD, XNIUSD, "
                     "SUGARRAW, XNGUSD -- trade through it with no Pacific information arriving.",
    "fn": market_holidays,
    "national_fn": national_holidays,
    "jurisdiction_fn": jurisdiction_holidays,
    "cyclone_fn": cyclone_season,
    "callable": "countries.pacific.pack:holidays",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "BPNG foreign exchange market data and the import-order backlog (PNG)",
     "root": "https://www.bankpng.gov.pg/statistics/",
     "fields": ("fx_turnover", "bpng_intervention", "outstanding_orders", "gross_reserves",
                "import_cover_months"),
     "frequency": "monthly / quarterly", "snapshot": "month end", "publish_utc": "00:00",
     "lag_days": 45, "licence": "free, public", "available": True,
     "why": "THE QUEUE IS THE POSITION. In a rationed-FX economy the outstanding import orders "
            "are the only measure of unmet demand for dollars, and their clearance under the "
            "ECF crawl is the largest single experiment this region offers",
     "pit_warning": "six weeks stale or worse, and the backlog figure is often a Governor's "
                    "statement rather than a table; never a same-month conditioner"},
    {"name": "Reserve Bank of Fiji foreign reserves and months of import cover",
     "root": "https://www.rbf.gov.fj/statistics/",
     "fields": ("foreign_reserves_fjd", "import_cover_months", "opr", "private_sector_credit"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "21:00", "lag_days": 20,
     "licence": "free, public", "available": True,
     "why": "the RBF's FIRST named objective is adequate reserves, ahead of inflation; the "
            "import-cover line is what its policy actually reacts to",
     "pit_warning": "the weekly reserves figure appears in press commentary before the monthly "
                    "review; only the review is a dated, citable vintage"},
    {"name": "PNA Vessel Day Scheme: days allocated, days sold, benchmark price per day",
     "root": "https://www.pnatuna.com/vds",
     "fields": ("days_allocated", "days_used", "days_traded", "benchmark_price_usd",
                "access_revenue_by_member"),
     "frequency": "annual, with a December trading window", "snapshot": "calendar year",
     "publish_utc": "20:00", "lag_days": 180, "licence": "free, public", "available": True,
     "why": "a genuine cartel inventory: the members cap the days and set a floor price, and the "
            "revenue is a third of Kiribati's and a large slice of the Solomons' budget",
     "pit_warning": "annual and very late; it is a STRUCTURAL conditioner, never an event"},
    {"name": "Australian PALM scheme worker numbers and Pacific remittance corridor prices",
     "root": "https://www.dewr.gov.au/pacific-australia-labour-mobility",
     "fields": ("workers_in_country", "by_sending_country", "by_sector",
                "remittance_cost_percent"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "22:00", "lag_days": 60,
     "licence": "free, public (Australian Government)", "available": True,
     "why": "the measurable remittance clock for Vanuatu, Samoa, Tonga and Fiji; it settles in "
            "AUD and NZD, which is the only place it becomes executable",
     "pit_warning": "quarterly and revised; the World Bank corridor prices are a separate series "
                    "with its own lag"},
    {"name": "a CFTC or exchange-traded positioning series for any Pacific currency",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "no PGK, FJD, SBD, VUV, XPF, WST or TOP future trades on any exchange the desk can "
            "read, and no bank publishes a Pacific positioning survey",
     "pit_warning": "DOES NOT EXIST: Pacific currency positioning is UNMEASURED and is never "
                    "proxied by the AUD COT report, which is a different economy's book"},
)

# --------------------------------------------------------------------------- terminology
#: SIX LANGUAGES, AND THE ENGLISH ONE IS THE THINNEST GROUND. An English-only query reaches the
#: Post-Courier, the RBF's press releases and RNZ Pacific and stops there. TOK PISIN is the
#: lingua franca of PNG's nine million people and is the language a landowner blockade, a road
#: closure and a kina complaint are actually reported in; HIRI MOTU is the second official
#: vernacular of Papua; FIJIAN and FIJI HINDI split Fiji's ground almost in half; and NEW
#: CALEDONIA'S NICKEL INDUSTRY IS ENTIRELY FRENCH -- "usine du Sud", "minerai" and "regie" have
#: no English equivalents in the local press and a nickel query in English misses the outage.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "PAC-PNG-A": ("Kina Facility Rate", "KFR", "Monetary Policy Statement", "Bank of Papua New "
                  "Guinea", "Central Bank Bill auction", "Cash Reserve Requirement",
                  "kina", "mani", "beng", "gavman", "kina i go daun", "moni", "gavamani"),
    "PAC-PNG-B": ("foreign exchange backlog", "import orders queue", "FX rationing",
                  "kina convertibility", "Extended Credit Facility", "crawling peg",
                  "market-clearing rate", "dola i sot", "hatwok long kisim dola", "bisnis",
                  "kago i no kam", "prais i go antap", "wok"),
    "PAC-PNG-C": ("PNG LNG", "Papua LNG", "Caution Bay", "Hides gas conditioning plant",
                  "Japan Crude Cocktail", "sales and purchase agreement", "force majeure",
                  "cargo lifting programme", "liquefaction train", "gas projek",
                  "ol papa graun", "wok i pinis", "rot i pas", "tano"),
    "PAC-PNG-D": ("Ok Tedi", "Porgera", "Lihir", "Panguna", "Bougainville",
                  "special mining lease", "memorandum of agreement", "state of emergency",
                  "tailings", "gol", "mainim", "papa graun", "hevi", "pait", "kampani",
                  "wara i doti", "hanua"),
    "PAC-PNG-E": ("Coffee Industry Corporation", "Y-grade arabica", "smallholder coffee",
                  "Highlands Highway", "Cocoa Board of PNG", "coffee berry borer", "parchment",
                  "kopi", "koko", "gaden", "maket", "prais bilong kopi"),
    "PAC-FJ-A": ("Reserve Bank of Fiji", "Overnight Policy Rate", "basket peg",
                 "nominal effective exchange rate", "months of import cover", "exchange control",
                 "ilavo", "baqe", "matanitu", "veivakatorocaketaki", "saumi", "paisa", "sarkar",
                 "mehngai"),
    "PAC-FJ-B": ("Fiji Sugar Corporation", "crushing season", "cane payment", "Lautoka mill",
                 "Rarawai mill", "Labasa mill", "EU preferential price", "cane growers",
                 "dovu", "suka", "vanua", "ganna", "chini", "ganna kisan"),
    "PAC-FJ-C": ("visitor arrivals", "Nadi International Airport", "Fiji Airways", "Tourism Fiji",
                 "Australian arrivals", "New Zealand arrivals", "hotel turnover tax",
                 "vulagi", "bisinisi", "bajar"),
    "PAC-NC-A": ("Societe Le Nickel", "SLN", "Doniambo", "Koniambo", "KNS", "Prony Resources",
                 "usine du Sud", "usine du Nord", "minerai de nickel", "ferronickel", "regie",
                 "rouleurs", "emeutes", "etat d'urgence", "couvre-feu", "blocages",
                 "Congres de la Nouvelle-Caledonie", "accord de Noumea", "province Nord",
                 "redevance miniere", "nickel pig iron", "Thio", "Kouaoua"),
    "PAC-SB-A": ("Gold Ridge", "Mineral Resources Authority", "export permit", "round logs",
                 "log export duty", "Central Bank of Solomon Islands", "Bokolo Bill",
                 "cocoa dryer", "copra", "gavman", "kaikai"),
    "PAC-REG-A": ("Parties to the Nauru Agreement", "Vessel Day Scheme", "purse seine",
                  "Forum Fisheries Agency", "WCPFC", "benchmark price per day", "access revenue",
                  "skipjack", "transshipment", "pis", "ika"),
    "PAC-REG-B": ("tropical cyclone", "RSMC Nadi", "Category 5", "Cyclone Winston",
                  "Cyclone Harold", "storm surge", "National Disaster Management Office",
                  "state of natural disaster", "El Nino drought", "highlands frost",
                  "bikpela win", "guria", "kaikai i sot", "sikau", "cagilaba", "waluvu",
                  "cyclone tropical", "alerte rouge"),
    "PAC-REG-C": ("International Date Line", "UTC+13", "Apia", "Nuku'alofa", "Monday open",
                  "weekend gap", "first market open", "Samoa dateline change 2011",
                  "mataka", "moning taim", "de bilong wok"),
    "PAC-REG-D": ("PALM scheme", "Pacific Australia Labour Mobility", "seasonal worker",
                  "remittances", "Recognised Seasonal Employer", "Pacific Islands Forum",
                  "Australian aid", "Pacific Step-up", "mani i kam bek", "wok long Ostrelia",
                  "wantok", "veivukei"),
}

#: THE LOAD-BEARING VERNACULAR, GLOSSED. A terminology table that a reader cannot check is a
#: table nobody will correct. Each entry is (language, gloss, why the desk needs it).
NATIVE_GLOSSARY: dict[str, tuple[str, str, str]] = {
    "mani": ("tpi", "money", "the general noun; a kina story is a 'mani' story in Tok Pisin"),
    "kina": ("tpi", "the currency, and the pearl shell it is named after",
             "the token every PNG FX report turns on"),
    "beng": ("tpi", "bank", "how a BPNG or commercial-bank notice is reported vernacularly"),
    "gavman": ("tpi", "government", "the actor in every licence, levy and emergency story"),
    "bisnis": ("tpi", "business, a commercial enterprise",
               "the importers queuing for dollars call themselves this"),
    "wok": ("tpi", "work, a job, an operation",
            "'wok i pinis' is how a mine or plant stoppage is reported"),
    "kaikai": ("tpi", "food; to eat",
               "the food-security vocabulary of a drought, frost or cyclone report"),
    "sikau": ("tpi", "wallaby", "bush-meat noun that appears in highlands drought and frost "
                                "food-security reporting alongside 'kaikai i sot'"),
    "graun": ("tpi", "ground, land", "'papa graun' is THE landowner, the actor in PAC-PNG-D"),
    "guria": ("tpi", "earthquake", "the 2018 Highlands event that shut PNG LNG is a 'guria'"),
    "rot i pas": ("tpi", "the road is blocked",
                  "the Highlands Highway closure that strands coffee and mine supply"),
    "moni": ("ho", "money", "the Hiri Motu cognate; Papua's second official vernacular"),
    "gavamani": ("ho", "government", "Hiri Motu, used across the Papuan coast"),
    "tano": ("ho", "ground, land", "the Hiri Motu land term in Papuan landowner reporting"),
    "hanua": ("ho", "village, place", "the unit a mining agreement is negotiated with"),
    "ilavo": ("fj", "money, funds", "the Fijian noun in RBF and budget reporting"),
    "baqe": ("fj", "bank", "Fijian borrowing; how the RBF is named in iTaukei media"),
    "matanitu": ("fj", "the state, government", "the actor in Fijian policy reporting"),
    "veivakatorocaketaki": ("fj", "development", "the word Fijian budget coverage is built on"),
    "vanua": ("fj", "land, and the people and chiefdom bound to it",
              "the unit that owns cane land and tourism leases alike"),
    "dovu": ("fj", "sugar cane", "the crop of PAC-FJ-B in the growers' own language"),
    "suka": ("fj", "sugar", "the processed product, as distinct from 'dovu' the cane"),
    "cagilaba": ("fj", "hurricane, tropical cyclone", "the Fijian cyclone term"),
    "waluvu": ("fj", "flood", "what follows a cyclone and closes the mills"),
    "vulagi": ("fj", "visitor, guest", "the tourism arrivals that are two fifths of Fiji's GDP"),
    "ganna": ("hif", "sugar cane", "Fiji Hindi; most cane growers are Indo-Fijian"),
    "chini": ("hif", "sugar", "Fiji Hindi for the milled product"),
    "paisa": ("hif", "money", "Fiji Hindi; the vernacular of half of Fiji's commerce"),
    "usine du Sud": ("fr", "the southern plant -- Prony Resources' Goro operation",
                     "one of the three New Caledonian nickel plants, named this way locally"),
    "usine du Nord": ("fr", "the northern plant -- Koniambo Nickel (KNS) at Vavouto",
                      "the Province Nord plant placed on care and maintenance in 2024"),
    "minerai de nickel": ("fr", "nickel ore",
                          "the exported saprolite and laterite, as distinct from ferronickel"),
    "regie": ("fr", "mining carried out directly by the operator rather than by subcontract",
              "the NC distinction between operator-run and 'rouleur' subcontracted extraction"),
    "rouleurs": ("fr", "the ore-truck subcontractors",
                 "the actors whose roadblocks halt ore movement before any plant stops"),
    "emeutes": ("fr", "riots", "the 13 May 2024 events that shut New Caledonian nickel"),
}

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
    labels. `queries` are native-language terms, never translations. `machine_use_allowed=False`
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
        "pac_bpng_png_state", "PNG: Bank of Papua New Guinea, Treasury and the National "
                              "Statistical Office", layer="official",
        roots=("https://www.bankpng.gov.pg/monetary-policy/",
               "https://www.bankpng.gov.pg/statistics/",
               "https://www.treasury.gov.pg/html/budget_documents/",
               "https://www.nso.gov.pg"),
        queries=("Monetary Policy Statement", "Kina Facility Rate", "foreign exchange backlog",
                 "Quarterly Economic Bulletin", "gross foreign reserves", "Final Budget Outcome",
                 "kina i go daun", "gavman", "mani"),
        languages=("en", "tpi", "ho"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (BPNG and PNG Government terms)",
        notes="the MPS is statutory twice a year; the QEB tables are the reserve and mineral "
              "export series; NSO output is quarterly and often months late, which is a "
              "measurement about PNG's statistical capacity and not a gap in the pack"),
    source_class(
        "pac_rbf_fiji_state", "Fiji: Reserve Bank of Fiji, Bureau of Statistics and the Ministry "
                              "of Finance", layer="official",
        roots=("https://www.rbf.gov.fj/monetary-policy/", "https://www.rbf.gov.fj/statistics/",
               "https://www.statsfiji.gov.fj/statistics/tourism-and-migration-statistics/",
               "https://www.economy.gov.fj/budget/"),
        queries=("Monetary Policy Statement", "Overnight Policy Rate", "foreign reserves",
                 "months of import cover", "visitor arrivals", "ilavo", "baqe", "matanitu",
                 "veivakatorocaketaki", "sarkar", "mehngai"),
        languages=("en", "fj", "hif"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the RBF names adequate reserves as its FIRST objective, so the import-cover line "
              "is the policy variable and the unchanged OPR is not; arrivals by source market "
              "are what PAC-FJ-C reads"),
    source_class(
        "pac_nc_official", "New Caledonia: ISEE, DIMENC, the Gouvernement and the Congres",
        layer="official",
        roots=("https://www.isee.nc/economie/entreprises/mines-et-energie",
               "https://dimenc.gouv.nc/mines-carrieres", "https://gouv.nc",
               "https://www.congres.nc"),
        queries=("production de nickel", "exportations de minerai", "usine du Sud",
                 "usine du Nord", "ferronickel", "redevance miniere", "etat d'urgence",
                 "couvre-feu", "emeutes", "accord de Noumea"),
        languages=("fr",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (Licence Ouverte / Etalab)",
        notes="DIMENC publishes the monthly ore, matte and ferronickel split BY PLANT, which is "
              "the only place the 2024 collapse is visible at monthly frequency; everything is "
              "in French and an English query reaches none of it"),
    source_class(
        "pac_sb_vu_ws_to_official", "Solomon Islands, Vanuatu, Samoa and Tonga: the mineral "
                                    "authority, the central banks and the statistics offices",
        layer="official",
        roots=("https://www.mra.gov.sb", "https://www.cbsi.com.sb/publications/",
               "https://www.statistics.gov.sb", "https://www.rbv.gov.vu",
               "https://www.cbs.gov.ws", "https://www.reservebank.to"),
        queries=("export permit", "round log exports", "Gold Ridge", "Bokolo Bill",
                 "Monetary Policy Statement", "remittances", "gavman", "kaikai"),
        languages=("en", "tpi", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="thin and irregular by comparison with PNG and Fiji; the MRA export permits are "
              "the dated object and the CBSI quarterly review is the confirmation"),
    source_class(
        "pac_imf_adb_worldbank", "IMF Article IV and ECF reviews, ADB Pacific and World Bank "
                                 "Pacific country pages", layer="official",
        roots=("https://www.imf.org/en/Countries/PNG", "https://www.imf.org/en/Countries/FJI",
               "https://www.adb.org/countries/papua-new-guinea/main",
               "https://www.worldbank.org/en/country/png"),
        queries=("Extended Credit Facility review", "structural benchmarks", "exchange rate "
                 "crawl", "foreign exchange backlog", "Article IV consultation",
                 "Pacific Economic Monitor", "debt sustainability analysis"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ECF staff reports DATE the crawl schedule and the backlog-clearance "
              "benchmarks; this is the only hard policy calendar the region has, and the ADB "
              "Pacific Economic Monitor is the twice-yearly cross-country table"),
    # ---- institutional
    source_class(
        "pac_regional_bodies", "Regional institutions: the Pacific Islands Forum, the Forum "
                               "Fisheries Agency, the PNA office and the Pacific Community",
        layer="institutional",
        roots=("https://www.forumsec.org", "https://www.ffa.int", "https://www.pnatuna.com",
               "https://www.spc.int"),
        queries=("Vessel Day Scheme", "benchmark price per day", "purse seine days",
                 "Forum Leaders communique", "tuna access revenue", "WCPFC measure",
                 "pis", "ika"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the PNA is the cartel of PAC-REG-A; the Forum communique is where an aid or "
              "climate-finance commitment is dated, and those land in AUD and NZD"),
    source_class(
        "pac_industry_bodies", "Industry bodies and operators' public reporting: the Fiji Sugar "
                               "Corporation, the PNG Chamber of Resources and Energy, the PNG "
                               "Coffee Industry Corporation and Cocoa Board",
        layer="institutional",
        roots=("https://www.fijisugar.com", "https://pngchamberminpet.com.pg",
               "https://www.coffee.gov.pg", "https://www.cocoaboard.gov.pg"),
        queries=("crushing season", "cane payment", "sugar made", "tonnes crushed",
                 "coffee exports", "Y-grade", "cocoa exports", "dovu", "suka", "kopi", "koko"),
        languages=("en", "fj", "hif", "tpi"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="FSC's weekly in-season crush table is the closest thing this region has to a "
              "high-frequency physical count; a week with no crush is a STOPPAGE, not a zero"),
    source_class(
        "pac_remittance_rails", "The Pacific's payment rails as an institution: Send Money "
                                "Pacific, the World Bank remittance-price corridors, and the "
                                "mobile-money schemes (M-PAiSA, CellMoni, BSP mobile)",
        layer="institutional",
        roots=("https://www.sendmoneypacific.org",
               "https://remittanceprices.worldbank.org/corridor",
               "https://www.dewr.gov.au/pacific-australia-labour-mobility"),
        queries=("remittance cost", "Australia to Tonga corridor", "New Zealand to Samoa",
                 "M-PAiSA", "CellMoni", "seasonal worker remittances", "mani i kam bek",
                 "wantok"),
        languages=("en", "tpi", "fj"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (World Bank and Australian Govt)",
        notes="REGISTERED HERE AND NOT AS AN APP ECOLOGY: these are PAYMENT rails, not venues "
              "where a price is discovered, and the distinction is why app_ecosystem below is "
              "declared absent rather than filled with them"),
    # ---- academic
    source_class(
        "pac_academic", "ANU Development Policy Centre (Devpolicy), the University of the South "
                        "Pacific, UPNG and the Lowy Institute Pacific programme",
        layer="academic",
        roots=("https://devpolicy.org/tag/papua-new-guinea/", "https://devpolicy.org/tag/fiji/",
               "https://www.usp.ac.fj/research/", "https://www.lowyinstitute.org/the-interpreter",
               "https://ideas.repec.org/"),
        queries=("PNG foreign exchange rationing", "kina exchange rate regime",
                 "Fiji sugar industry decline", "Pacific labour mobility remittances",
                 "resource curse Papua New Guinea", "nickel New Caledonia economy",
                 "Vessel Day Scheme rent"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="DEVPOLICY IS THE REAL ACADEMIC GROUND FOR THIS REGION: it publishes dated, "
              "quantitative posts on the PNG FX backlog, PALM worker numbers and Pacific budget "
              "outcomes faster than any official series, and its authors are the people who "
              "assemble those series; every claim here is a hypothesis until the desk reproduces "
              "it"),
    # ---- practitioner
    source_class(
        "pac_practitioner_press", "The region's thin practitioner ground: Business Advantage PNG, "
                                  "PNG Business News, Islands Business and PNG Resources",
        layer="practitioner",
        roots=("https://www.businessadvantagepng.com", "https://www.pngbusinessnews.com",
               "https://islandsbusiness.com/category/business/"),
        queries=("foreign exchange backlog", "kina devaluation", "LNG cargo", "mining licence",
                 "Papua LNG FID", "nickel curtailment", "bisnis", "wok i pinis"),
        languages=("en", "tpi"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="DECLARED THIN, AND WHY: there is NO domestic sell-side research industry in this "
              "region -- no broker publishes an MPS preview, no house runs an expectations "
              "survey, and the PNGX and SPX have no analysts. What exists is trade journalism "
              "written for investors, which is kept as a narrative feature and never as an "
              "expectation series; PAC-PNG-A therefore has NO consensus to measure against and "
              "says so on its face"),
    source_class(
        "pac_licensed_commodity", "Licensed commodity assessments the mechanism actually prices "
                                  "against: Fastmarkets and Argus nickel, Platts JKM and LNG "
                                  "freight, ICE softs", layer="practitioner",
        roots=("https://www.fastmarkets.com/metals-and-mining/base-metals/",
               "https://www.argusmedia.com/en/metals"),
        queries=("nickel ore assessment", "ferronickel price", "JKM assessment",
                 "LNG spot cargo Asia"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. These are the assessments a New Caledonian ore "
              "shipment and a PNG LNG spot cargo are actually priced off; the desk reads only "
              "their public headlines and treats the underlying level as UNMEASURED"),
    # ---- retail ecology
    source_class(
        "pac_retail_scam_ecology", "The Pacific's retail ecology as it actually is: BPNG and RBF "
                                   "public warnings on unlicensed foreign-exchange and "
                                   "investment schemes, and the Facebook and TikTok 'forex' "
                                   "ground in PNG and Fiji", layer="retail_ecology",
        roots=("https://www.bankpng.gov.pg/media-releases/",
               "https://www.rbf.gov.fj/press-releases/",
               "https://www.facebook.com/groups/pngbusinessforum"),
        queries=("unlicensed foreign exchange dealer", "pyramid scheme warning",
                 "fast money scheme", "forex trading PNG", "forex trading Fiji", "mani",
                 "bisnis", "gavman i tok lukaut"),
        languages=("en", "tpi", "fj"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts and releases only",
        notes="KEPT AT LOW WEIGHT AND KEPT DELIBERATELY. There is no licensed retail CFD "
              "brokerage in this region and exchange control forbids the outward margin "
              "transfer one would need, so what looks like a retail trading ecology is mostly "
              "a fraud ecology -- and the CENTRAL BANKS' OWN WARNINGS date the stress episodes, "
              "because fast-money schemes surface when the kina queue is longest. Nothing here "
              "is a source of edge; it is a dated stress observable"),
    # ---- app ecosystem
    absent_layer(
        "app_ecosystem",
        "there is no Pacific-native market-data or trading app ecology to map. No licensed "
        "retail CFD or securities broker operates in PNG, Fiji, Solomon Islands or Vanuatu; "
        "BPNG and RBF exchange control forbid the outward remittance a margin account requires; "
        "the PNGX and SPX have no retail app and publish a daily PDF; and what DOES exist -- BSP "
        "mobile banking, Vodafone Fiji's M-PAiSA, Digicel's CellMoni and Send Money Pacific -- "
        "is a PAYMENTS rail, registered under `pac_remittance_rails` in the institutional layer "
        "where it belongs. Filling this layer with mobile-money apps would misdescribe a "
        "remittance corridor as a price-discovery venue and make the coverage number a "
        "description of this pack's optimism instead of of the region"),
    # ---- media
    source_class(
        "pac_png_press", "PNG media: the Post-Courier, The National, EMTV and NBC",
        layer="media",
        roots=("https://www.postcourier.com.pg/category/business/",
               "https://www.thenational.com.pg/category/business/", "https://emtv.com.pg"),
        queries=("foreign exchange", "kina", "LNG shipment", "landowner", "state of emergency",
                 "Highlands Highway", "papa graun", "rot i pas", "wok i pinis", "guria"),
        languages=("en", "tpi", "ho"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the Post-Courier and The National carry the dated landowner, blockade and "
              "shutdown reporting that PAC-PNG-C and PAC-PNG-D are built on, usually days "
              "before any operator statement and weeks before any statistic"),
    source_class(
        "pac_fiji_press", "Fiji media: the Fiji Times, Fijivillage, FBC News and the Fiji Sun",
        layer="media",
        roots=("https://www.fijitimes.com.fj/category/business/",
               "https://www.fijivillage.com/news/", "https://www.fbcnews.com.fj/business/"),
        queries=("crushing season", "cane payment", "visitor arrivals", "Reserve Bank of Fiji",
                 "foreign reserves", "dovu", "suka", "ganna kisan", "ilavo", "vulagi"),
        languages=("en", "fj", "hif"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Fijivillage carries the RBF release and the weekly crush number within the hour; "
              "the iTaukei and Fiji Hindi segments of FBC reach the growers rather than the "
              "hotels, which is where a cane-payment dispute is reported first"),
    source_class(
        "pac_regional_media", "Regional and French-territory media: RNZ Pacific, ABC Pacific, "
                              "Islands Business, and Les Nouvelles Caledoniennes / NC la 1ere",
        layer="media",
        roots=("https://www.rnz.co.nz/international/pacific-news",
               "https://www.abc.net.au/pacific", "https://www.lnc.nc",
               "https://la1ere.francetvinfo.fr/nouvellecaledonie/"),
        queries=("Pacific Islands Forum", "nickel", "emeutes", "couvre-feu", "usine du Sud",
                 "cyclone", "state of emergency", "Vessel Day Scheme", "cagilaba"),
        languages=("en", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="RNZ Pacific is the region's de facto wire and is often the FIRST English stamp on "
              "a Melanesian event; LNC and NC la 1ere are the only continuous French-language "
              "record of the nickel plants' operating state"),
    # ---- archive
    source_class(
        "pac_archive", "The back-run: BPNG annual reports and QEB archives, RBF annual reports, "
                       "Fiji Bureau of Statistics historical series, ISEE long nickel series, "
                       "the PNG National Gazette and the Journal officiel de la "
                       "Nouvelle-Caledonie, all mirrored at the Internet Archive",
        layer="archive",
        roots=("https://www.bankpng.gov.pg/publications/", "https://www.rbf.gov.fj/publications/",
               "https://www.isee.nc/component/phocadownload/", "https://web.archive.org"),
        queries=("annual report", "Quarterly Economic Bulletin archive", "historical nickel "
                 "production", "national gazette", "journal officiel",
                 "sugar production history"),
        languages=("en", "fr"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PACIFIC WEBSITES VANISH. BPNG and several statistics offices have rebuilt their "
              "sites and dropped the back-run more than once, so the Internet Archive is not a "
              "convenience here but the only vintage record; a PIT-safe series for this region "
              "is assembled from snapshots or it is not PIT-safe"),
    # ---- physical economy
    source_class(
        "pac_ports_shipping", "Port calls and berths: the PNG LNG marine terminal at Caution "
                              "Bay, Port Moresby and Lae (PNG Ports), Suva's Kings Wharf and "
                              "Lautoka (Fiji Ports), and Noumea's Grande Rade and the Doniambo "
                              "wharf", layer="physical_economy",
        roots=("https://www.pngports.com.pg", "https://www.fijiports.com.fj",
               "https://www.portdenoumea.nc", "https://www.marinetraffic.com"),
        queries=("LNG carrier Caution Bay", "berth occupancy", "vessel arrival", "bulk carrier "
                 "nickel ore", "sugar shipment Lautoka", "port de Noumea", "minerai"),
        languages=("en", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="port authority terms; AIS aggregator terms",
        notes="ONE BERTH IS THE WHOLE MECHANISM: PNG LNG loads at a single marine terminal, so "
              "an absent carrier is an outage days before a force-majeure notice; the Doniambo "
              "wharf is the same for SLN, and Lautoka is the same for Fijian raw sugar"),
    source_class(
        "pac_hazard_weather", "The physical clock: RSMC Nadi (Fiji Meteorological Service), the "
                              "Australian Bureau of Meteorology, NIWA seasonal outlooks, the "
                              "national disaster offices, USGS and the Pacific Tsunami Warning "
                              "Center", layer="physical_economy",
        roots=("https://www.met.gov.fj/index.php?page=cyclone",
               "http://www.bom.gov.au/cyclone/", "https://www.tsunami.gov",
               "https://earthquake.usgs.gov/earthquakes/map/"),
        queries=("tropical cyclone warning", "Category 5", "storm surge", "state of natural "
                 "disaster", "tsunami warning", "magnitude earthquake Papua New Guinea",
                 "cagilaba", "guria", "alerte rouge", "cyclone tropical"),
        languages=("en", "fj", "fr", "tpi"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED",
        licence="free, public (national meteorological and geological services)",
        notes="RSMC NADI IS THE REGIONAL AUTHORITY for South Pacific cyclone warnings, so its "
              "bulletin TIME is the PIT stamp for an interruption event -- earlier than any "
              "company statement and earlier than the damage; the USGS feed does the same job "
              "for the guria that shut PNG LNG in 2018"),
    # ---- source graph
    source_class(
        "pac_source_graph", "Who cites whom: BPNG and RBF releases into the Post-Courier, The "
                            "National and Fijivillage, then into RNZ Pacific and the wires; "
                            "DIMENC and ISEE into LNC and NC la 1ere, then into the metals "
                            "wires; the PNA and FFA into Islands Business and Devpolicy",
        layer="source_graph",
        roots=("https://www.rnz.co.nz/international/pacific-news",
               "https://devpolicy.org", "https://www.postcourier.com.pg", "https://www.lnc.nc"),
        queries=("according to the Bank of Papua New Guinea", "the Reserve Bank of Fiji said",
                 "selon la DIMENC", "RNZ Pacific reports", "Devpolicy Blog analysis",
                 "sources close to the operator", "ol sos i tok"),
        languages=("en", "fr", "tpi"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="THE GRAPH IS HOW A LEAK IS TOLD FROM A REPOST. In a region where one wire (RNZ "
              "Pacific) is re-published by everyone, the same sentence appearing in six outlets "
              "is ONE observation, and counting it six times is how a Pacific event study "
              "manufactures confirmation it never had"),
)

#: The one layer this region genuinely does not have, with the reason, so the coverage number is
#: a measurement of the Pacific rather than of this pack's optimism.
LAYER_ABSENCES: dict[str, str] = {
    "app_ecosystem": "no Pacific-native market-data or trading app ecology exists: no licensed "
                     "retail CFD or securities broker operates in PNG, Fiji, Solomon Islands or "
                     "Vanuatu, exchange control forbids the outward margin transfer one would "
                     "need, and the mobile-money rails (M-PAiSA, CellMoni, BSP mobile, Send "
                     "Money Pacific) are PAYMENT infrastructure registered in the institutional "
                     "layer, not venues where a price is discovered",
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
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; fringe "
                    "and contradicted PUBLIC material is kept as a low-weight evidence object "
                    "and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}

# --------------------------------------------------------------------------- datasets
#: EVERY DATASET NAMES ITS COUNTRY IN ITS NAME. One pack, seven sovereigns: a row that says only
#: "the Pacific" cannot be joined to a jurisdiction's calendar and cannot be falsified.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "PNG -- BPNG Kina Facility Rate and Monetary Policy Statements", "source": "BPNG",
     "coverage": "2001 onward (the KFR was introduced in 2001)", "frequency": "monthly KFR, "
     "semi-annual statement", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "free, public", "history_from": "2001-02", "pit_feasible": True,
     "assets": ("AUDUSD", "XAUUSD", "XNGUSD"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "bankpng.gov.pg monetary policy page; the MPS PDF carries its own date and "
                     "the KFR announcement day is stamped from the release, never assumed"},
    {"name": "PNG -- BPNG Quarterly Economic Bulletin reserve and mineral export tables",
     "source": "BPNG", "coverage": "1998 onward", "frequency": "quarterly",
     "publication_lag_days": 100.0, "revisions": "restated without notice in later bulletins",
     "licence": "free, public", "history_from": "1998-03", "pit_feasible": False,
     "assets": ("AUDUSD", "XNGUSD", "XAUUSD"),
     "mechanism_families": ("reserves_clock", "terms_of_trade"),
     "how_to_fetch": "bankpng.gov.pg publications; PIT IS NOT FEASIBLE because later bulletins "
                     "silently restate earlier quarters -- keep every PDF as its own vintage or "
                     "declare the series UNMEASURED for the quarter in question"},
    {"name": "PNG -- the BPNG foreign exchange order backlog and import-cover statements",
     "source": "BPNG statements, IMF ECF staff reports", "coverage": "2014 onward (the backlog "
     "begins with the June 2014 trading band)", "frequency": "irregular, dated",
     "publication_lag_days": 30.0, "revisions": "never; each figure is a point statement",
     "licence": "free, public", "history_from": "2014-06", "pit_feasible": True,
     "assets": ("AUDUSD", "XAUUSD"),
     "mechanism_families": ("rationing", "stress_indicator", "programme_clock"),
     "how_to_fetch": "the Governor's statements and the IMF ECF review tables; the backlog is "
                     "quoted in months of import cover or in kina, and the two are not the same "
                     "series -- never splice them"},
    {"name": "PNG -- LNG plant production, shipments and force-majeure notices",
     "source": "ExxonMobil PNG, Santos, MRDC and the PNG Treasury",
     "coverage": "2014 onward (first cargo May 2014)", "frequency": "quarterly with dated "
     "interruptions", "publication_lag_days": 30.0, "revisions": "rarely",
     "licence": "free, public", "history_from": "2014-05", "pit_feasible": False,
     "assets": ("XNGUSD", "XBRUSD", "USDJPY"),
     "mechanism_families": ("supply_interruption", "tender_event", "forced_flow_calendar"),
     "how_to_fetch": "operator quarterlies and the PNG press; PIT IS PARTIAL because a force "
                     "majeure is usually reported before it is confirmed, so the PRESS stamp is "
                     "the event and the operator statement is the confirmation"},
    {"name": "PNG -- Ok Tedi, Porgera and Lihir quarterly production and shipment reports",
     "source": "Ok Tedi Mining Ltd, New Porgera Ltd / Barrick, Newmont",
     "coverage": "2010 onward for all three", "frequency": "quarterly",
     "publication_lag_days": 25.0, "revisions": "restated at year end", "licence": "free, public",
     "history_from": "2010-03", "pit_feasible": True, "assets": ("XAUUSD", "XCUUSD", "XAUAUD"),
     "mechanism_families": ("supply_count", "supply_interruption"),
     "how_to_fetch": "operator quarterly reports; the 2015-16 Ok Tedi drought suspension and the "
                     "2020-23 Porgera closure are the two large natural experiments in the series"},
    {"name": "PNG -- National Statistical Office CPI and the Coffee Industry Corporation export "
             "series", "source": "PNG NSO and the PNG Coffee Industry Corporation",
     "coverage": "CPI 2005 onward; coffee exports 2000 onward", "frequency": "quarterly / monthly",
     "publication_lag_days": 90.0, "revisions": "rebasing only", "licence": "free, public",
     "history_from": "2005-03", "pit_feasible": False, "assets": ("COFARA", "UKCOCOA"),
     "mechanism_families": ("release_surprise", "export_count"),
     "how_to_fetch": "nso.gov.pg and coffee.gov.pg; the publication lag is months and sometimes "
                     "quarters, which makes the series a CONDITIONER and never an event"},
    {"name": "Fiji -- RBF monthly Economic Review: reserves, import cover and the OPR",
     "source": "Reserve Bank of Fiji", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 20.0, "revisions": "minor, next month", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True, "assets": ("AUDUSD", "NZDUSD", "USDJPY"),
     "mechanism_families": ("policy_surprise", "reserves_clock"),
     "how_to_fetch": "rbf.gov.fj publications; the OPR has been 0.25% since March 2020, so the "
                     "reserves line and not the rate is what a surprise study measures"},
    {"name": "Fiji -- Bureau of Statistics visitor arrivals by source market",
     "source": "Fiji Bureau of Statistics", "coverage": "1995 onward",
     "frequency": "monthly", "publication_lag_days": 30.0, "revisions": "minor",
     "licence": "free, public", "history_from": "1995-01", "pit_feasible": True,
     "assets": ("AUDUSD", "NZDUSD", "AUDNZD"),
     "mechanism_families": ("seasonal_flow", "services_export"),
     "how_to_fetch": "statsfiji.gov.fj tourism and migration tables; the Australian and New "
                     "Zealand lines carry the mechanism and the 2020-21 border closure is a "
                     "structural break that must never be smoothed across"},
    {"name": "Fiji -- Fiji Sugar Corporation weekly crush, sugar made and cane payment",
     "source": "Fiji Sugar Corporation", "coverage": "2010 onward",
     "frequency": "weekly in season (June-December)", "publication_lag_days": 3.0,
     "revisions": "cumulative; never restated", "licence": "free, public",
     "history_from": "2010-06", "pit_feasible": True, "assets": ("SUGARRAW", "SUGAR"),
     "mechanism_families": ("supply_count", "seasonal_flow"),
     "how_to_fetch": "fijisugar.com and the Fiji press; a week with NO crush is a mill stoppage "
                     "and must be carried as such, never interpolated to zero"},
    {"name": "New Caledonia -- ISEE and DIMENC monthly nickel ore, matte and ferronickel exports",
     "source": "ISEE / DIMENC (Nouvelle-Caledonie)", "coverage": "2000 onward",
     "frequency": "monthly", "publication_lag_days": 45.0, "revisions": "minor",
     "licence": "free, public (Licence Ouverte)", "history_from": "2000-01",
     "assets": ("XNIUSD", "XCUUSD"), "pit_feasible": True,
     "mechanism_families": ("supply_count", "supply_interruption"),
     "how_to_fetch": "isee.nc and dimenc.gouv.nc monthly tables, split BY PLANT; the May 2024 "
                     "collapse and the KNS care-and-maintenance decision are visible here "
                     "months before any annual statistic"},
    {"name": "Solomon Islands -- MRA export permits and CBSI quarterly review (logs, gold, cocoa)",
     "source": "Solomon Islands Mineral Resources Authority and CBSI",
     "coverage": "2012 onward", "frequency": "irregular permits, quarterly review",
     "publication_lag_days": 60.0, "revisions": "rarely", "licence": "free, public",
     "history_from": "2012-01", "pit_feasible": False, "assets": ("XAUUSD", "UKCOCOA"),
     "mechanism_families": ("trade_decision", "export_count"),
     "how_to_fetch": "mra.gov.sb permit notices and cbsi.com.sb reviews; the permit is the dated "
                     "object and the review is the confirmation, and neither is timely"},
    {"name": "Regional -- PNA Vessel Day Scheme allocations, days sold and benchmark day price",
     "source": "Parties to the Nauru Agreement / Forum Fisheries Agency",
     "coverage": "2012 onward (the VDS benchmark price begins in 2012)", "frequency": "annual",
     "publication_lag_days": 180.0, "revisions": "never", "licence": "free, public",
     "history_from": "2012-01", "pit_feasible": True, "assets": ("AUDUSD", "NZDUSD"),
     "mechanism_families": ("cartel_quota", "fiscal_flow"),
     "how_to_fetch": "pnatuna.com and ffa.int annual reports; INPUT-ONLY -- no tuna instrument "
                     "exists on any venue the desk reaches, so this series conditions the "
                     "members' fiscal balances and never compiles a cell of its own"},
    {"name": "Regional -- PALM worker numbers, Pacific remittances and cyclone track archive",
     "source": "Australian DEWR, World Bank remittance data, RSMC Nadi and the Australian BoM",
     "coverage": "PALM 2012 onward; cyclone tracks 1970 onward", "frequency": "quarterly / "
     "per event", "publication_lag_days": 60.0, "revisions": "PALM revised; tracks final",
     "licence": "free, public", "history_from": "2012-07", "pit_feasible": True,
     "assets": ("AUDUSD", "NZDUSD", "SUGARRAW"),
     "mechanism_families": ("seasonal_flow", "physical_interruption"),
     "how_to_fetch": "dewr.gov.au PALM statistics, remittanceprices.worldbank.org, and the RSMC "
                     "Nadi / BoM best-track archives; the BULLETIN TIME, not the landfall time, "
                     "is the PIT stamp for a cyclone event"},
)

# --------------------------------------------------------------------------- actors
#: FOURTEEN ACTORS, EACH NAMING ITS JURISDICTION. The `country` field is not decoration: a
#: forced flow in New Caledonia settles in euros under French law and a forced flow in PNG
#: settles in a currency nobody can get, and pooling them destroys both mechanisms.
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Papua New Guinea (BPNG) as the kina's rate-setter and rationer",
     "country": "PG",
     "holds": "the Kina Facility Rate, the Central Bank Bill book, the Cash Reserve Requirement "
              "and -- the instrument that actually binds -- the administered allocation of "
              "foreign exchange to the commercial banks",
     "forced_to": ("publish a Monetary Policy Statement by 31 March and by 30 September under "
                   "the Central Banking Act",
                   "meet the IMF ECF's structural benchmarks, which include a SCHEDULED crawl "
                   "of the kina toward a market-clearing rate and the clearance of the backlog",
                   "decide every week which importers' orders the banks may fill"),
     "when": "the two statutory statement deadlines; the KFR monthly on a day that varies; the "
             "FX allocation continuously and without publication",
     "information": ("the true size of the outstanding import-order backlog",
                     "the mineral and LNG export receipts before anyone else",
                     "the IMF mission's numbers", "the banks' own FX books it supervises"),
     "constraints": ("the ECF's crawl schedule and reserve floor",
                     "a fiscal deficit the State funds partly through the domestic bank system",
                     "an export base of three commodities and a food import bill",
                     "the political cost of a visible devaluation"),
     "instruments": ("AUDUSD", "XAUUSD", "XNGUSD"),
     "counterparties": ("the commercial banks holding unconvertible kina",
                        "the IMF and the World Bank", "the importers in the queue",
                        "the resource projects that earn the dollars"),
     "observables": ("the Monetary Policy Statement and its backlog language",
                     "gross reserves and months of import cover in the QEB",
                     "the posted kina reference against the parallel discussion in the press",
                     "the Central Bank Bill auction cut-offs"),
     "impact": "a crawl step reprices every import contract in the country at once; the "
               "executable effect is NOT on PGK, which is unquoted, but on the AUD leg the "
               "trade and aid settle through and on the gold and gas legs PNG sells",
     "persistence": "the crawl is a programme-length regime, not an event; the queue's length "
                    "moves in months",
     "falsifier": "a widening FX backlog that is NOT followed within two quarters by a slower "
                  "import volume, a wider parallel discount in the press or a visible step in "
                  "the posted rate refutes the rationing mechanism the whole PNG half of this "
                  "pack is built on, and a crawl step with no measurable move on the AUD leg "
                  "says the transmission is to the domestic price level only",
     "notes": "the June 2014 trading band created the backlog; everything since is its history"},
    {"name": "PNG importers and the commercial banks' foreign exchange order queue",
     "country": "PG",
     "holds": "months of unfilled import orders and the trade-finance books that carry them",
     "forced_to": ("queue for dollars at the banks rather than buy them at a price",
                   "hold kina balances they cannot convert while the queue clears",
                   "ration fuel, rice, spare parts and medicine downstream when it does not"),
     "when": "continuously; the queue lengthens fastest when mineral receipts fall",
     "information": ("their own unfilled order book", "the banks' allocation signals",
                     "which sectors the BPNG has prioritised this month"),
     "constraints": ("exchange control and the allocation priority list",
                     "letters of credit that expire while the order waits",
                     "shipping schedules that do not wait for the queue"),
     "instruments": ("AUDUSD", "XAUUSD"),
     "counterparties": ("Australian, Singaporean and Chinese suppliers",
                        "the banks allocating", "BPNG"),
     "observables": ("the backlog figure in BPNG and IMF statements",
                     "import volume and the fuel and rice supply reports in the PNG press",
                     "the gap between the posted rate and what is discussed as obtainable"),
     "impact": "PNG's import compression is invisible in FX -- there is no rate to move -- and "
               "shows up instead as suppressed import VOLUME, which is a small but real "
               "subtraction from Australian and Asian export demand",
     "persistence": "years; this has been the regime since 2014",
     "falsifier": "if import volumes and the fuel and food supply reports show no relation to "
                  "the stated backlog once mineral receipts are controlled, then the queue is a "
                  "presentational number rather than a binding constraint, and PAC-PNG-B has no "
                  "mechanism at all",
     "notes": "the actor that makes PNG a RATIONED economy rather than a cheap-currency one"},
    {"name": "ExxonMobil PNG as the PNG LNG operator", "country": "PG",
     "holds": "about 8-9 mtpa of liquefaction at Caution Bay, the Hides conditioning plant, the "
              "292km pipeline, and long-term SPAs with Japanese, Chinese and Taiwanese buyers",
     "forced_to": ("lift to a nominated monthly cargo programme agreed in advance",
                   "declare force majeure when an earthquake, a landowner blockade or a state "
                   "of emergency stops the plant or the pipeline",
                   "price the contracted volume off a LAGGED Japan Crude Cocktail average "
                   "rather than off the spot gas market"),
     "when": "the following month's lifting programme is fixed in the opening business days; "
             "cargoes load at a single marine terminal roughly twice a week",
     "information": ("plant availability and the maintenance schedule before the market",
                     "landowner sentiment along the pipeline",
                     "the buyers' nomination behaviour"),
     "constraints": ("one train complex and one loading berth",
                     "landowner benefit agreements the State has repeatedly failed to pay out",
                     "the seismic and civil-order exposure of the highlands infrastructure"),
     "instruments": ("XNGUSD", "XBRUSD", "USDJPY"),
     "counterparties": ("Japanese and Chinese utility buyers", "Santos and the other JV owners",
                        "MRDC and the landowner umbrella companies", "the PNG State"),
     "observables": ("force-majeure notices and the PNG press reporting that precedes them",
                     "carrier calls at Caution Bay on AIS",
                     "the quarterly production number", "the JCC print with its lag"),
     "impact": "8-9 mtpa is about two per cent of world LNG trade; an outage is a real Asian "
               "supply subtraction, but the leg the desk can quote is Henry Hub gas, which is "
               "a WEAK proxy for it, and every gas edge in this pack says so on its face",
     "persistence": "an outage lasts weeks; the 2018 earthquake shut the plant for about two "
                    "months and that is the reference episode",
     "falsifier": "if the declared outage windows show no abnormal move on XNGUSD or XBRUSD "
                  "against the matched-weekday control and the no-outage placebo, the honest "
                  "conclusion is that Atlantic-basin gas does not read a Pacific outage, which "
                  "the pack records as the expected result rather than hiding",
     "notes": "one plant, one berth: the most countable energy flow in the southern hemisphere"},
    {"name": "TotalEnergies and the Papua LNG joint venture as the next step function",
     "country": "PG",
     "holds": "the Elk-Antelope resource and the Papua LNG project awaiting final investment "
              "decision, with Santos and ExxonMobil as partners",
     "forced_to": ("reach or defer FID on a dated timetable the State negotiates against",
                   "agree a gas agreement and a landowner benefit-sharing arrangement first",
                   "commit to downstream domestic-market obligations the State demands"),
     "when": "FID is a single dated announcement, repeatedly deferred; the gas agreement and the "
             "front-end engineering awards are dated milestones before it",
     "information": ("the partners' own cost estimates and the buyers' term interest",
                     "the State's negotiating position"),
     "constraints": ("PNG's fiscal and landowner politics",
                     "a global LNG cost environment and competing Qatari and US supply",
                     "the same seismic and civil-order exposure as PNG LNG"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the PNG State and MRDC", "Santos and ExxonMobil",
                        "the Asian term buyers"),
     "observables": ("the FID announcement or its deferral", "the gas agreement signing",
                     "the EPC awards", "the partners' capital-markets days"),
     "impact": "an FID adds several mtpa to the 2028-plus supply curve, which is a FORWARD "
               "curve event and not a prompt one; the desk expects little prompt effect and "
               "measures it anyway",
     "persistence": "a single step; the effect, if any, is on the deferred contract months",
     "falsifier": "an FID or a deferral that moves prompt XNGUSD more than it moves the deferred "
                  "structure would refute the forward-supply reading of this actor entirely, "
                  "and no measurable move on either is the outcome the pack expects and records",
     "notes": "carried because the deferral history is itself the observable, not for strength"},
    {"name": "Ok Tedi Mining Ltd and the PNG State as its sole owner", "country": "PG",
     "holds": "the Ok Tedi copper-gold mine in Western Province, wholly State-owned since 2013, "
              "and the Fly River barge route that is its only way out",
     "forced_to": ("suspend when the Fly River is too low to barge, as in the 2015-16 El Nino "
                   "drought", "pay dividends to a State that needs them for the budget",
                   "carry the environmental and compensation legacy of the tailings discharge"),
     "when": "quarterly production reports; interruptions are weather- and river-clocked",
     "information": ("river levels and barge availability weeks ahead",
                     "its own ore grade and stockpile position"),
     "constraints": ("a single river route with a hard low-water threshold",
                     "an ageing orebody", "the State's cash needs as owner"),
     "instruments": ("XCUUSD", "XAUUSD", "XAUAUD"),
     "counterparties": ("Asian smelters buying the concentrate", "the PNG State as shareholder",
                        "the Western Province landowners and the CMCA communities"),
     "observables": ("the quarterly production and shipment report",
                     "Fly River level and drought bulletins", "suspension announcements"),
     "impact": "roughly 100-150kt of copper in concentrate a year: small against world supply "
               "but a genuine, weather-clocked interruption with a public trigger variable",
     "persistence": "a drought suspension lasts months; the 2015-16 episode ran about seven",
     "falsifier": "if the drought-suspension windows carry no abnormal move on XCUUSD against "
                  "the matched control and against other concentrate interruptions of similar "
                  "size in the same years, then Ok Tedi is too small to read and the pack "
                  "records that rather than promoting a story",
     "notes": "the only mine in the book whose binding constraint is a river level"},
    {"name": "PNG's hard-rock gold operators: New Porgera Ltd and Newmont Lihir",
     "country": "PG",
     "holds": "Porgera, shut from April 2020 when the special mining lease was not extended and "
              "restarted in December 2023 under a renegotiated ownership split, and Lihir, one "
              "of the largest gold orebodies in the world",
     "forced_to": ("renegotiate leases and landowner memoranda on the State's timetable",
                   "suspend for tribal violence, landslides and highway closures in Enga",
                   "report production quarterly to their listed parents"),
     "when": "quarterly reports; interruptions arrive as dated security and landslide events",
     "information": ("their own grade, stockpile and autoclave availability",
                     "local security conditions before any public report"),
     "constraints": ("the Enga security environment and the Highlands Highway",
                     "lease and benefit-sharing politics with the State and landowners",
                     "power and fuel supply in a rationed-FX economy"),
     "instruments": ("XAUUSD", "XAUAUD", "XCUUSD"),
     "counterparties": ("Barrick and Zijin as Porgera's partners", "Newmont as Lihir's owner",
                        "the PNG State and the Porgera landowners", "the refiners"),
     "observables": ("the quarterly production report", "lease and MOA announcements",
                     "the PNG press on Enga security and Highlands Highway closures"),
     "impact": "Porgera plus Lihir is roughly 1.0-1.3 Moz a year, under one per cent of world "
               "supply; the three-and-a-half-year Porgera closure is nonetheless one of the "
               "cleanest single-mine natural experiments available anywhere",
     "persistence": "the Porgera closure lasted from April 2020 to December 2023; highway and "
                    "security interruptions last days to weeks",
     "falsifier": "if neither the April 2020 closure nor the December 2023 restart shows any "
                  "abnormal move on XAUUSD or XAUAUD against the matched control, then a mine "
                  "of this size does not reach the gold price and the pack demotes the whole "
                  "PNG mining channel to an observability story",
     "notes": "the two operators are ACTORS; no share CFD appears in any instrument tuple here"},
    {"name": "Reserve Bank of Fiji (RBF) as the basket peg's keeper", "country": "FJ",
     "holds": "the Overnight Policy Rate, held at 0.25% since March 2020, exchange control over "
              "outward payments, and the reserves that defend the basket peg",
     "forced_to": ("publish a Monetary Policy Statement monthly after the Board meets",
                   "hold the FJD to a USD/AUD/NZD/JPY/EUR basket",
                   "name adequate foreign reserves as its FIRST objective, ahead of inflation"),
     "when": "normally the last Thursday of the month, released in the Suva morning (about "
             "21:00 UTC the previous calendar day, which is the easiest alignment error here)",
     "information": ("weekly reserves before the market", "the arrivals and remittance flows "
                     "through the banking system", "the commercial banks' FX positions"),
     "constraints": ("a peg that must be defended out of reserves",
                     "an economy whose foreign earnings are tourism, remittances, water and "
                     "sugar, three of which are seasonal",
                     "exchange control that keeps domestic capital at home"),
     "instruments": ("AUDUSD", "NZDUSD", "USDJPY"),
     "counterparties": ("the commercial banks", "the tourism operators earning AUD and NZD",
                        "the IMF at Article IV"),
     "observables": ("the monthly statement and its reserves line",
                     "months of import cover", "the arrivals print it reacts to"),
     "impact": "an FJD that is an index of its partners means a Fijian shock is priced in the "
               "PARTNERS, weighted the way the basket weights them; the executable legs are "
               "AUDUSD and NZDUSD and never a Fijian instrument",
     "persistence": "the peg is structural; the reserves cycle is seasonal with arrivals",
     "falsifier": "if the reserves and import-cover line carries no information about the "
                  "subsequent AUDUSD or NZDUSD path once Australian and New Zealand arrivals "
                  "are controlled, then the RBF is a follower of its partners and not a "
                  "transmitter, which is the null this actor is measured against",
     "notes": "the OPR has not moved since March 2020; the RATE is not the policy variable"},
    {"name": "Fiji Sugar Corporation and the cane growers of Viti Levu and Vanua Levu",
     "country": "FJ",
     "holds": "the Lautoka, Rarawai and Labasa mills, the cane railway, and the crushing "
              "contract with roughly twelve thousand growers",
     "forced_to": ("crush only between June and December, when the cane is ripe",
                   "pay growers a cane price derived from the realised sugar price",
                   "sell into the world raw market since the EU preferential price ended"),
     "when": "the season opens in June and closes in December; the weekly crush and sugar-made "
             "figures are published through it",
     "information": ("the standing crop estimate before the season",
                     "mill availability and breakdown risk", "the cane quality by district"),
     "constraints": ("ageing mills with a real breakdown rate",
                     "cyclone exposure in the November-April window that overlaps the season's "
                     "tail", "expiring land leases that shrink the cane area each year"),
     "instruments": ("SUGARRAW", "SUGAR"),
     "counterparties": ("the growers", "world raw sugar buyers", "the Fijian State as funder"),
     "observables": ("the weekly crush and sugar-made table",
                     "mill stoppage reports in the Fiji press", "the cane payment announcement",
                     "the seasonal forecast of tonnes crushed"),
     "impact": "Fiji makes roughly 150-200kt of sugar, a fraction of a per cent of world trade; "
               "the mechanism is SEASONAL TIMING rather than size, and a seasonal study whose "
               "out-of-season months are the placebo is the honest form of it",
     "persistence": "one season a year, every year, on a physical clock",
     "falsifier": "if the in-season windows on SUGARRAW match the out-of-season placebo months "
                  "and the matched-weekday control, then Fiji's crush is invisible in the world "
                  "raw price -- the expected result for a producer this size, and the one the "
                  "pack will record rather than dress up",
     "notes": "the out-of-season months are the placebo, not a gap in the sample"},
    {"name": "Fiji's inbound tourism: Fiji Airways, the hotel operators and the arrivals flow",
     "country": "FJ",
     "holds": "the Nadi gateway, the aircraft that feed it, and the room stock the arrivals fill",
     "forced_to": ("sell in AUD and NZD and settle in FJD",
                   "fly to Australian and New Zealand school-holiday and winter calendars",
                   "shut when a cyclone closes Nadi or a border closes"),
     "when": "arrivals are monthly and strongly seasonal; the Australian and New Zealand winter "
             "and school holidays are the peaks",
     "information": ("forward bookings months ahead of any statistic",
                     "the airline's own load factors and capacity plans"),
     "constraints": ("Australian and New Zealand household discretionary income",
                     "aircraft capacity into one runway",
                     "the cyclone season, which is also the low season"),
     "instruments": ("AUDUSD", "NZDUSD", "AUDNZD"),
     "counterparties": ("Australian and New Zealand households",
                        "Qantas, Air New Zealand and Jetstar as competing capacity",
                        "the RBF, which receives the foreign exchange"),
     "observables": ("monthly arrivals by source market", "airline capacity announcements",
                     "hotel turnover tax receipts", "cyclone closures of Nadi"),
     "impact": "tourism is about two fifths of Fijian GDP once indirect effects are counted, so "
               "a shock to the AUD household is a shock to Fiji; the direction of causation runs "
               "INTO Fiji, which makes AUDUSD an input for Fiji and Fiji an output for AUDUSD",
     "persistence": "seasonal, with a structural break at the 2020-21 border closure",
     "falsifier": "if the arrivals series carries no relation to the prior quarter's AUDUSD and "
                  "Australian consumption once seasonality is removed, then the tourism channel "
                  "is not an AUD channel at all and PAC-FJ-C loses its conditioning variable",
     "notes": "an INPUT-direction mechanism, stated as such; the outward edge is not expected"},
    {"name": "Societe Le Nickel, Koniambo Nickel and Prony Resources as New Caledonia's "
             "nickel producers", "country": "NC",
     "holds": "the Doniambo smelter (SLN), the usine du Nord at Vavouto (KNS) and the usine du "
              "Sud at Goro (Prony), plus the mining titles over roughly a tenth of world "
              "nickel reserves",
     "forced_to": ("run plants whose energy cost is among the highest in the industry",
                   "stop when roadblocks cut the ore trucks -- the rouleurs -- from the mines",
                   "negotiate with the provinces and the Congres over export licences for ore"),
     "when": "monthly production and export statistics; interruptions arrive as dated civil "
             "order events, of which 13 May 2024 is the reference",
     "information": ("their own plant availability and ore stocks",
                     "the local security situation before any wire reports it"),
     "constraints": ("Indonesian NPI supply that sets the marginal cost of world nickel",
                     "New Caledonian politics over independence, the Accord de Noumea and the "
                     "provincial balance", "an energy cost no restructuring has yet solved"),
     "instruments": ("XNIUSD", "XCUUSD"),
     "counterparties": ("Eramet as SLN's parent and Glencore as KNS's former funder",
                        "the French State as repeated rescuer", "European stainless buyers"),
     "observables": ("the DIMENC monthly production and export split by plant",
                     "the LNC and NC la 1ere reporting on roadblocks and curfews",
                     "care-and-maintenance and administration announcements",
                     "ore carrier calls at Noumea"),
     "impact": "New Caledonia is a single-digit percentage of world nickel; in a market already "
               "in surplus from Indonesian supply, a shock here is absorbed rather than priced, "
               "which is precisely the hypothesis the nickel miner exists to test",
     "persistence": "the 2024 disruption is structural, not episodic: KNS went to care and "
                    "maintenance and SLN has run at reduced rates since",
     "falsifier": "if the declared New Caledonian disruption dates show no abnormal move on "
                  "XNIUSD against the matched-weekday control AND against the no-disruption "
                  "placebo, then Indonesian supply has made this producer price-irrelevant, "
                  "which is a finding about the nickel market and not a failure of the pack",
     "notes": "the only actor in the book whose binding constraint is a roadblock"},
    {"name": "Solomon Islands Mineral Resources Authority and the log, gold and cocoa exporters",
     "country": "SB",
     "holds": "the export permit power over round logs, gold from Gold Ridge, and the cocoa and "
              "copra trade that the smallholder economy runs on",
     "forced_to": ("issue or refuse dated export permits",
                   "collect a log export duty that is a large share of government revenue",
                   "manage a logging resource that is being cut faster than it grows"),
     "when": "permits are irregular and dated; the CBSI quarterly review confirms the flows",
     "information": ("the permit pipeline and the shipments due",
                     "the state of the Gold Ridge operation"),
     "constraints": ("a depleting log resource", "Gold Ridge's tailings-dam and ownership "
                     "history", "a very small statistical capacity"),
     "instruments": ("UKCOCOA", "XAUUSD", "XNIUSD"),
     "counterparties": ("Malaysian and Chinese logging companies",
                        "the Gold Ridge operator", "European and Asian cocoa buyers"),
     "observables": ("MRA export permit notices", "the CBSI quarterly review's export tables",
                     "shipping calls at Honiara and the outer ports"),
     "impact": "tiny in every commodity it touches; the Solomons enter this pack as a COCOA "
               "ORIGIN of real quality and as a nickel prospect whose licence politics mirror "
               "New Caledonia's, and both edges are recorded as weak on their face",
     "persistence": "a permit cycle; the logging decline is a decade-long trend",
     "falsifier": "if the export-permit windows carry no abnormal move on UKCOCOA against the "
                  "matched control and against West African origin news in the same weeks, the "
                  "Solomon cocoa edge is an origin story rather than a price mechanism, which "
                  "is what the pack expects and will record",
     "notes": "carried for completeness of the Melanesian actor map, not for executable strength"},
    {"name": "The Parties to the Nauru Agreement (PNA) and the Vessel Day Scheme",
     "country": "PG, SB, regional",
     "holds": "the purse-seine fishing days in the waters of eight members plus Tokelau -- "
              "roughly a quarter to a third of the world's skipjack catch -- and a benchmark "
              "minimum price per day",
     "forced_to": ("cap the total allowable effort in days each year",
                   "set and enforce a benchmark minimum day price",
                   "allocate days between members and allow them to trade the unused ones"),
     "when": "the annual allocation and the benchmark price are set for the following year; "
             "members trade unused days in a December window",
     "information": ("the real-time catch and effort data from the vessel day register",
                     "each member's unused days before the trading window"),
     "constraints": ("distant-water fleets from Taiwan, Korea, China, Japan, the US and the EU "
                     "that can fish elsewhere", "El Nino and La Nina, which move the skipjack "
                     "biomass east and west across member boundaries",
                     "the WCPFC conservation framework"),
     "instruments": ("AUDUSD", "NZDUSD"),
     "counterparties": ("the distant-water fishing nations and their vessel operators",
                        "the canneries in Bangkok and General Santos",
                        "the member treasuries the access revenue funds"),
     "observables": ("the annual benchmark day price", "days allocated, used and traded",
                     "access revenue in each member's budget", "the ENSO state"),
     "impact": "A CARTEL WITH NO CONTRACT. The VDS raised member access revenue several-fold "
               "and is a genuine forced-flow institution, but NO TUNA INSTRUMENT EXISTS on any "
               "venue this desk reaches, so its only executable reach is through the members' "
               "fiscal balances and the AUD-denominated aid and trade that follow",
     "persistence": "annual, and structural since 2012",
     "falsifier": "there is nothing to falsify on a price leg, which is the point: this actor is "
                  "declared INPUT-ONLY, and the falsifiable claim is the FISCAL one -- if access "
                  "revenue shows no relation to member budget outcomes and the aid flows that "
                  "follow them, then even the indirect channel is absent and the actor is "
                  "carried as structure only",
     "notes": "declared INPUT-ONLY on purpose; L1.49 forbids a cell that can never be filled"},
    {"name": "The Australian PALM scheme and the Pacific seasonal workers who remit through it",
     "country": "regional (AU/PG/FJ/VU/WS/TO)",
     "holds": "tens of thousands of Pacific workers in Australian horticulture, meat processing "
              "and aged care, plus New Zealand's Recognised Seasonal Employer equivalent",
     "forced_to": ("remit to households on a pay cycle",
                   "convert AUD and NZD into the home currency through a corridor whose price "
                   "is published", "return home at the end of a fixed visa term"),
     "when": "quarterly worker-number statistics; the remittance flow is fortnightly and "
             "peaks into Christmas and the start of the school year",
     "information": ("their own employment and pay cycle", "the corridor's exchange rate"),
     "constraints": ("Australian and New Zealand labour demand",
                     "visa caps and employer approvals",
                     "corridor costs that are among the highest in the world"),
     "instruments": ("AUDUSD", "NZDUSD", "AUDNZD"),
     "counterparties": ("Australian and New Zealand employers",
                        "the money-transfer operators and the mobile-money rails",
                        "the home central banks receiving the foreign exchange"),
     "observables": ("PALM worker numbers by sending country",
                     "World Bank corridor prices", "remittance receipts in the home central "
                     "banks' statistics", "the RSE cap announcements"),
     "impact": "remittances are a double-digit share of GDP for Tonga and Samoa and a rising one "
               "for Vanuatu; the flow is small in FX terms but it is the ONLY mechanism in this "
               "pack whose two legs -- AUD and NZD -- are both quotable",
     "persistence": "seasonal within the year and structurally growing since 2012",
     "falsifier": "if remittance receipts show no relation to PALM worker numbers and the AUDNZD "
                  "cross once Australian and New Zealand agricultural employment is controlled, "
                  "then the labour-mobility channel is a development story and not a flow "
                  "mechanism, and PAC-REG-D is demoted to structure",
     "notes": "the one mechanism here whose both legs are on the broker; small, but clean"},
    {"name": "RSMC Nadi, the Australian Bureau of Meteorology and the Pacific disaster offices",
     "country": "regional (FJ/PG/VU/SB/NC)",
     "holds": "the regional cyclone warning authority for the South Pacific basin and the "
              "national declarations of a state of natural disaster",
     "forced_to": ("issue a numbered bulletin at fixed intervals as a system develops",
                   "name and categorise the system on an agreed scale",
                   "trigger the national disaster declaration that closes ports and airports"),
     "when": "the season runs 1 November to 30 April; bulletins are issued every six hours and "
             "more often at landfall",
     "information": ("the forecast track and intensity hours to days before landfall"),
     "constraints": ("the physical predictability limit of a track forecast",
                     "the ENSO state, which shifts the basin's activity east or west"),
     "instruments": ("SUGARRAW", "XNIUSD", "XNGUSD", "AUDUSD"),
     "counterparties": ("the mills, ports, mines and airports that shut on a warning",
                        "the insurers and the reinsurance market",
                        "Australia and New Zealand as the disaster responders"),
     "observables": ("the numbered bulletin and its TIME, which is the PIT stamp",
                     "the category at landfall", "the national disaster declaration",
                     "port and airport closure notices"),
     "impact": "a severe landfall stops cane crushing, ore loading and LNG berthing at once, "
               "and does it on a clock that is public hours to days ahead -- the only "
               "forecastable supply interruption anywhere in this pack",
     "persistence": "days for the interruption, a season for the crop damage; Cyclone Winston "
                    "in February 2016 is the reference event",
     "falsifier": "if bulletin-time windows for severe systems making landfall on Fiji or "
                  "Vanuatu carry no abnormal move on SUGARRAW against the matched control and "
                  "against the non-landfall systems of the same category, then the region's "
                  "physical interruptions are too small to price and the pack says so",
     "notes": "the BULLETIN time and never the landfall time is the point-in-time stamp"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "PAC-PNG-A", "country": "PG",
     "title": "BPNG's statutory statement calendar in an economy with no traded consensus",
     "objects": ("the two statutory Monetary Policy Statements (by 31 March, by 30 September)",
                 "the monthly Kina Facility Rate announcement",
                 "the Central Bank Bill and Treasury Bill auction cut-offs between them",
                 "the statement's own backlog and crawl language"),
     "conditions": ("the era: the trading band (2014-16), the rationing years, the ECF crawl",
                    "whether the statement fell inside an IMF ECF review window",
                    "the direction of gross reserves over the prior quarter"),
     "instruments": ("AUDUSD", "XAUUSD", "XNGUSD"),
     "controls": ("the same window on the eight nearest non-statement weekdays",
                  "the same window on RBA decision days, separating 'an Oceania bank decided' "
                  "from 'BPNG decided'",
                  "the T-bill cut-off drift on non-statement weeks as a placebo"),
     "notes": "THERE IS NO CONSENSUS TO SURPRISE. No broker publishes a preview and no survey "
              "exists, so a 'surprise' here is measured against the PRIOR only, and every "
              "reading says which of the two quantities it is"},
    {"id": "PAC-PNG-B", "country": "PG",
     "title": "The kina's FX rationing: the import queue, the parallel discount and the ECF crawl",
     "objects": ("the outstanding import-order backlog in months of cover",
                 "the posted BPNG reference rate against what the press says is obtainable",
                 "the ECF's dated crawl steps and backlog-clearance benchmarks",
                 "import volumes of fuel, rice and spare parts as the rationing shows through"),
     "conditions": ("the backlog bucket (under one month, one to three, above three)",
                    "whether mineral and LNG receipts rose or fell over the prior quarter",
                    "whether an ECF review was pending"),
     "instruments": ("AUDUSD", "XAUUSD"),
     "controls": ("the same windows in quarters when the backlog was shrinking",
                  "Nigeria's and Egypt's FX-backlog episodes on the same instruments, "
                  "separating 'a rationed frontier currency' from 'PNG'",
                  "a randomised-date null on the crawl-step dates"),
     "notes": "the mechanism is a QUANTITY, not a price: PGK is unquoted and its posted rate is "
              "not a clearing rate, so everything terminates in import volume and the AUD leg"},
    {"id": "PAC-PNG-C", "country": "PG",
     "title": "PNG LNG: one plant, one berth, a lagged oil index and a dated outage history",
     "objects": ("the monthly cargo nomination and lifting programme",
                 "force-majeure notices and the press reporting that precedes them",
                 "carrier calls at the Caution Bay marine terminal",
                 "the JCC print and the roughly one-quarter lag the SPAs apply to it",
                 "the Papua LNG final investment decision and its repeated deferral"),
     "conditions": ("whether the interruption was seismic, civil-order or maintenance",
                    "the season, since Asian term demand is winter-weighted",
                    "whether the outage was declared force majeure or merely reported"),
     "instruments": ("XNGUSD", "XBRUSD", "USDJPY"),
     "controls": ("the same windows on the no-outage months of the same years",
                  "Australian North West Shelf and Gorgon outage windows on the same "
                  "instruments, separating 'a Pacific LNG outage' from 'PNG LNG'",
                  "the matched weekday-and-hour control on XNGUSD"),
     "notes": "JKM is absent from this box, so every gas reading here is declared a WEAK-PROXY "
              "reading on its face and is never promoted above HYPOTHESIS on that leg alone"},
    {"id": "PAC-PNG-D", "country": "PG",
     "title": "PNG mining: Ok Tedi's river, Porgera's lease and Lihir's highway",
     "objects": ("the quarterly production and shipment reports of the three operations",
                 "the 2015-16 Ok Tedi drought suspension and the Fly River level that caused it",
                 "the April 2020 Porgera closure and the December 2023 restart",
                 "landowner memoranda, special mining leases and the Panguna legacy"),
     "conditions": ("the interruption's cause: drought, lease politics, security, landslide",
                    "the ENSO state, which sets the Fly River risk",
                    "whether the metal was gold, copper concentrate or both"),
     "instruments": ("XAUUSD", "XCUUSD", "XAUAUD"),
     "controls": ("the same windows on quarters with no interruption",
                  "other single-mine outages of comparable size in the same years, separating "
                  "'a mine stopped' from 'a PNG mine stopped'",
                  "a randomised-date null over the interruption dates"),
     "notes": "the Porgera closure is three and a half years long, which makes it the cleanest "
              "single-mine natural experiment in the desk's book"},
    {"id": "PAC-PNG-E", "country": "PG",
     "title": "PNG highlands arabica, the Highlands Highway and the Melanesian cocoa origins",
     "objects": ("Coffee Industry Corporation export volumes and the Y-grade differential",
                 "Highlands Highway closures from landslides, tribal conflict and rain",
                 "the harvest window, which peaks around the middle of the year",
                 "Solomon Islands and Vanuatu cocoa export permits and shipments"),
     "conditions": ("whether the highway was open through the harvest",
                    "the differential's level relative to the ICE arabica price",
                    "the crop year's rainfall and frost history"),
     "instruments": ("COFARA", "UKCOCOA"),
     "controls": ("the same harvest windows in years with no highway closure",
                  "Colombian and Ethiopian washed-arabica origin news in the same weeks, "
                  "separating 'a washed origin' from 'PNG'",
                  "the out-of-harvest months as the seasonal placebo"),
     "notes": "PNG is a real washed-arabica origin but a small one; the differential and not the "
              "flat price is where a highway closure is expected to appear at all"},
    {"id": "PAC-FJ-A", "country": "FJ",
     "title": "The Reserve Bank of Fiji's monthly statement and the five-currency basket peg",
     "objects": ("the monthly Monetary Policy Statement and its reserves line",
                 "months of import cover", "the OPR, unchanged at 0.25% since March 2020",
                 "the basket's implied weights on the USD, AUD, NZD, JPY and EUR"),
     "conditions": ("the arrivals season", "the reserves trend over the prior quarter",
                    "whether an exchange-control change was announced alongside"),
     "instruments": ("AUDUSD", "NZDUSD", "USDJPY"),
     "controls": ("the same window on the four nearest non-statement Thursdays",
                  "RBNZ and RBA decision days on the same instruments, separating 'an Oceania "
                  "policy day' from 'an RBF statement day'",
                  "the months when the OPR was last actually changed, as the only non-null era"),
     "notes": "the RATE is not the policy variable here; reserves and import cover are, and a "
              "study that measures OPR surprises in this country measures a constant"},
    {"id": "PAC-FJ-B", "country": "FJ",
     "title": "The Fiji crushing season as a physically-clocked seasonal supply event",
     "objects": ("the June-December season boundaries",
                 "the weekly crush and sugar-made table",
                 "mill stoppages at Lautoka, Rarawai and Labasa",
                 "the cane payment and what remains of the European reference price"),
     "conditions": ("in season or out, which is the design",
                    "whether a cyclone crossed the cane belt in the season's tail",
                    "the standing crop estimate relative to the prior year"),
     "instruments": ("SUGARRAW", "SUGAR"),
     "controls": ("THE OUT-OF-SEASON MONTHS (January to May) as the explicit placebo",
                  "the Australian Queensland crush season on the same instruments, separating "
                  "'a southern-hemisphere crush' from 'Fiji'",
                  "the matched weekday-and-hour control on SUGARRAW"),
     "notes": "Fiji makes a fraction of a per cent of world sugar; the honest expectation is no "
              "outward effect, and the out-of-season placebo is what makes that answer readable"},
    {"id": "PAC-FJ-C", "country": "FJ",
     "title": "Fiji tourism as an AUD and NZD household-demand channel running inward",
     "objects": ("monthly visitor arrivals by source market",
                 "Fiji Airways and competitor capacity into Nadi",
                 "the 2020-21 border closure as a structural break",
                 "hotel turnover tax receipts as the domestic counterpart"),
     "conditions": ("the Australian and New Zealand school-holiday calendar",
                    "the cyclone season, which is also the low season",
                    "the level of Australian household discretionary income"),
     "instruments": ("AUDUSD", "NZDUSD", "AUDNZD"),
     "controls": ("the same months in the 2020-21 closed-border years, where arrivals are zero "
                  "by construction and any 'effect' is therefore spurious",
                  "New Zealand and Australian outbound travel to Bali and Thailand in the same "
                  "months, separating 'Australians travelled' from 'Australians went to Fiji'",
                  "a randomised-date null on the arrivals release days"),
     "notes": "an INPUT-direction mechanism: AUDUSD drives Fiji and not the reverse, and the "
              "pack measures the outward leg honestly rather than assuming it away"},
    {"id": "PAC-NC-A", "country": "NC",
     "title": "New Caledonia nickel: a civil-order supply shock into an Indonesian surplus",
     "objects": ("the 13 May 2024 riots, the state of emergency and the curfew",
                 "KNS entering care and maintenance and SLN's reduced rates",
                 "the DIMENC monthly ore, matte and ferronickel split by plant",
                 "roadblocks and the rouleurs who move the ore"),
     "conditions": ("whether Indonesian NPI supply was in surplus at the time",
                    "the LME nickel price level and the cash-to-3M structure",
                    "whether the interruption hit mining, haulage or smelting"),
     "instruments": ("XNIUSD", "XCUUSD"),
     "controls": ("MATCHED NON-DISRUPTION DAYS drawn from the same months in the same years",
                  "Indonesian and Philippine nickel policy dates on XNIUSD, separating 'nickel "
                  "supply news' from 'New Caledonian nickel supply news'",
                  "the matched weekday-and-hour control around the LME official window"),
     "notes": "the whole domain exists to test whether an Indonesian surplus has made a "
              "tenth-of-world-reserves producer price-irrelevant; either answer is a finding"},
    {"id": "PAC-SB-A", "country": "SB",
     "title": "Solomon Islands: export permits over logs, gold and cocoa in a tiny state",
     "objects": ("MRA export permit notices and their dates",
                 "Gold Ridge's operating state and ownership history",
                 "round log export volumes and the duty that funds the budget",
                 "cocoa and copra shipments from the outer provinces"),
     "conditions": ("the commodity the permit covers",
                    "whether the CBSI quarterly review later confirmed the flow",
                    "the logging resource trend, which is a decade-long decline"),
     "instruments": ("UKCOCOA", "XAUUSD"),
     "controls": ("the same windows on weeks with no permit issued",
                  "West African cocoa origin news in the same weeks, which is where the world "
                  "cocoa price is actually made",
                  "a randomised-date null over the permit dates"),
     "notes": "declared weak on its face; the Solomons are an ORIGIN and a licence-politics "
              "case study, and the pack expects to record an absent effect"},
    {"id": "PAC-REG-A", "country": "PG, SB, regional",
     "title": "The PNA Vessel Day Scheme: a real cartel with no instrument, declared INPUT-ONLY",
     "objects": ("the annual benchmark minimum price per fishing day",
                 "days allocated, days used and the December trading window",
                 "access revenue as a share of each member's budget",
                 "the ENSO state, which moves the skipjack biomass across member boundaries"),
     "conditions": ("the ENSO phase", "the world skipjack price at the Bangkok landed level",
                    "whether the distant-water fleets were bidding or standing off"),
     "instruments": ("AUDUSD", "NZDUSD"),
     "controls": ("member budget outcomes in years with a flat benchmark price",
                  "OPEC quota announcements as a reference cartel on unrelated instruments, "
                  "to check that a 'cartel announcement' effect is not a generic calendar effect",
                  "the matched weekday control on the AUD leg"),
     "notes": "NO TUNA CONTRACT EXISTS anywhere the desk can reach, so this domain compiles NO "
              "price cell and is declared INPUT-ONLY: its falsifiable claim is the fiscal one"},
    {"id": "PAC-REG-B", "country": "regional (FJ/VU/PG/SB/NC)",
     "title": "The cyclone season as the only forecastable supply interruption in the book",
     "objects": ("RSMC Nadi numbered bulletins and their TIMES",
                 "the category at landfall and the track",
                 "national declarations of a state of natural disaster",
                 "port, airport, mill and berth closures that follow"),
     "conditions": ("the category and whether the system made landfall at all",
                    "which economy it crossed: cane, nickel, LNG or none",
                    "the ENSO phase, which shifts the basin's activity"),
     "instruments": ("SUGARRAW", "XNIUSD", "XNGUSD", "AUDUSD"),
     "controls": ("SEVERE SYSTEMS OF THE SAME CATEGORY THAT DID NOT MAKE LANDFALL, which is the "
                  "cleanest placebo in this pack: the warning was issued and nothing stopped",
                  "the same calendar windows in the six non-season months",
                  "Australian east-coast cyclone landfalls on the same instruments"),
     "notes": "the BULLETIN time and not the landfall time is the point-in-time stamp; using "
              "landfall leaks hours of public forecast into the pre-event window"},
    {"id": "PAC-REG-C", "country": "regional (WS/TO/FJ)",
     "title": "The dateline: the earliest opening ground on earth and the Monday-open gap",
     "objects": ("the Sunday 19:00-21:00 UTC window in which Apia and Nuku'alofa are already at "
                 "08:00 Monday while no FX market has opened",
                 "the first bars of the trading week at the Wellington and Sydney open",
                 "Pacific weekend events -- cyclone landfall, a shutdown, an emergency -- that "
                 "were public for hours before any quote existed",
                 "Samoa's and Tokelau's move across the line at the end of 29 December 2011"),
     "conditions": ("whether a declared Pacific weekend event landed in that window",
                    "the size of the preceding Friday close to Monday open gap",
                    "the southern-hemisphere summer, when cyclone weekends cluster"),
     "instruments": ("AUDUSD", "NZDUSD", "AUDNZD"),
     "controls": ("THE TUESDAY OPEN in the same UTC hours, a mid-week open with no weekend gap",
                  "the same window on weekends with no declared Pacific event",
                  "the matched weekday-and-hour control across the whole sample"),
     "notes": "the region's own microstructure mechanism, and the only one in this pack that "
              "does not depend on a Pacific statistic existing at all"},
    {"id": "PAC-REG-D", "country": "regional (AU/NZ/PG/FJ/VU/WS/TO)",
     "title": "Australia and New Zealand as the Pacific's currency, aid and labour-mobility proxy",
     "objects": ("PALM and RSE worker numbers by sending country",
                 "Pacific remittance receipts and the published corridor costs",
                 "Australian and New Zealand aid commitments and the Forum communique",
                 "the share of Pacific trade invoiced and settled in AUD and NZD"),
     "conditions": ("the Australian and New Zealand agricultural labour cycle",
                    "the visa cap and employer-approval state",
                    "whether a Forum or bilateral aid commitment had just been dated"),
     "instruments": ("AUDUSD", "NZDUSD", "AUDNZD", "AUS200"),
     "controls": ("the same windows in years before the PALM scheme was consolidated",
                  "Philippine and Indonesian labour remittance seasonality on other crosses, "
                  "separating 'seasonal remittances' from 'Pacific remittances'",
                  "a block-permutation null on the worker-number series"),
     "notes": "THE ONLY MECHANISM IN THIS PACK WITH BOTH LEGS ON THE BROKER; small in size, "
              "which is stated, but clean in construction, which is why it is here"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "pacific_png_lng_loading_clock", "domain_ids": ("PAC-PNG-C",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pacific.miners:png_lng_loading_clock",
     "needs": ("the monthly nomination window and the declared outage rows",
               "XNGUSD, XBRUSD H1 bars"),
     "notes": "the nomination window with a mid-month placebo, plus the declared outage dates "
              "as their own study; JKM is absent so every reading is declared weak-proxy"},
    {"name": "pacific_nickel_supply_shock", "domain_ids": ("PAC-NC-A", "PAC-SB-A"),
     "kind": "event", "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.pacific.miners:nickel_supply_shock",
     "needs": ("the New Caledonia and Solomon disruption rows", "XNIUSD, XCUUSD H1 bars"),
     "notes": "matched-weekday control from the framework plus an explicit no-disruption placebo "
              "drawn from the same months of the same years"},
    {"name": "pacific_fiji_crush_season", "domain_ids": ("PAC-FJ-B",), "kind": "calendar",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.pacific.miners:fiji_crush_season",
     "needs": ("the June-December season definition", "SUGARRAW, SUGAR H1 bars"),
     "notes": "the out-of-season months are the explicit placebo, not a gap in the sample"},
    {"name": "pacific_dateline_monday_open", "domain_ids": ("PAC-REG-C",),
     "kind": "microstructure", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pacific.miners:dateline_monday_open",
     "needs": ("nothing Pacific at all: the tape's own weekly boundary",
               "AUDUSD, NZDUSD, AUDNZD H1 bars"),
     "notes": "the week-open bars against the Tuesday-open placebo in the same UTC hours"},
    {"name": "pacific_transmission_seeds",
     "domain_ids": ("PAC-PNG-A", "PAC-PNG-B", "PAC-PNG-D", "PAC-PNG-E", "PAC-FJ-A", "PAC-FJ-C",
                    "PAC-REG-A", "PAC-REG-B", "PAC-REG-D"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.pacific.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("PAC-PNG-A", "PAC-FJ-A"),
    "release_surprise": ("PAC-FJ-A", "PAC-FJ-C"),
    "calendar_settlement": ("PAC-PNG-C", "PAC-FJ-B"),
    "holiday_liquidity": ("PAC-REG-C",),
    "session_microstructure": ("PAC-REG-C",),
    "positioning": ("PAC-REG-A",),
    "carry_funding": ("PAC-PNG-B",),
    "corporate_flow": ("PAC-PNG-D", "PAC-NC-A"),
    "institutional_flow": ("PAC-REG-D", "PAC-REG-A"),
    "equity_mechanics": ("PAC-REG-D",),
    "derivatives_expiry": ("PAC-NC-A",),
    "failure": ("PAC-SB-A", "PAC-PNG-E"),
    "residual": ("PAC-PNG-B", "PAC-REG-B"),
    "transfer": ("PAC-PNG-C", "PAC-FJ-B"),
    "scouts": ("PAC-SB-A", "PAC-REG-B"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "PAC-E1", "country": "PG",
     "source": "PNG LNG unplanned outage (earthquake, landowner blockade, state of emergency)",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "about 8-9 mtpa of Asian LNG supply stops at a single plant with a single "
                  "loading berth; the term buyers must replace the cargo from the spot market",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "ExxonMobil PNG as the PNG LNG operator",
     "constraint": "one train complex, one berth, and highlands infrastructure exposed to "
                   "earthquakes and roadblocks",
     "flow": "spot replacement demand",
     "condition": "an outage declared force majeure rather than a scheduled turnaround",
     "control": "Australian North West Shelf and Gorgon outage windows; the no-outage months",
     "falsifier": "the outage windows match the matched-weekday control and the no-outage "
                  "placebo -- the expected result if Atlantic-basin gas does not read a "
                  "Pacific outage, which the pack records rather than hides",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E2", "country": "PG",
     "source": "The PNG LNG monthly cargo nomination and lifting programme",
     "target": "XBRUSD", "targets": ("XBRUSD", "XNGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the lifting programme fixes the month's physical flow in the opening "
                  "business days; a short programme is a forward signal a term buyer acts on",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "ExxonMobil PNG and the Japanese and Chinese term buyers",
     "constraint": "the programme is agreed in advance and cannot be revised freely",
     "flow": "contracted cargo scheduling",
     "condition": "the opening five business days of the month only",
     "control": "the mid-month days (12th to 16th), which carry no nomination",
     "falsifier": "the nomination window matches the mid-month placebo, which is the honest "
                  "expectation for a scheduling event that is not publicly disclosed",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E3", "country": "PG",
     "source": "The Japan Crude Cocktail print, applied to PNG LNG's SPAs with about a "
               "quarter's lag", "target": "USDJPY", "targets": ("USDJPY", "XBRUSD"),
     "to_country": "jp", "sign": "+",
     "mechanism": "the contracted PNG LNG volume is invoiced off a LAGGED crude average into "
                  "Japan, so the revenue and the yen leg move with oil on a delay the spot "
                  "gas market does not share",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the Japanese utility term buyers and Japan METI as the index publisher",
     "constraint": "the SPA index formula and its lag",
     "flow": "contracted import invoicing",
     "condition": "conditioned on the crude average of the quarter before, not on spot crude",
     "control": "a contemporaneous rather than lagged crude regression, which should be WEAKER "
                "if the lag is the mechanism; Australian LNG's own oil-linked contracts",
     "falsifier": "the contemporaneous specification fits at least as well as the lagged one, "
                  "in which case there is no lag mechanism and the edge is a generic oil-yen edge",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E4", "country": "NC",
     "source": "New Caledonia nickel disruption (the 2024 riots, SLN curtailment, KNS care and "
               "maintenance)", "target": "XNIUSD", "targets": ("XNIUSD", "XCUUSD"),
     "to_country": "global", "sign": "+",
     "mechanism": "a producer sitting on roughly a tenth of world reserves loses haulage and "
                  "smelting at once when the roadblocks go up; whether that reaches the price "
                  "depends entirely on the Indonesian surplus",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Societe Le Nickel, Koniambo Nickel and Prony Resources",
     "constraint": "the rouleurs move every tonne of ore and a roadblock stops them first",
     "flow": "physical supply interruption",
     "condition": "conditioned on the Indonesian NPI supply state: surplus or not",
     "control": "matched non-disruption days in the same months; Indonesian and Philippine "
                "nickel policy dates on the same instrument",
     "falsifier": "the disruption dates match the matched-weekday control and the no-disruption "
                  "placebo, which would say the Indonesian surplus has made this producer "
                  "price-irrelevant -- a finding about nickel, not a failure of the pack",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E5", "country": "PG",
     "source": "Porgera, Lihir and Ok Tedi production interruptions",
     "target": "XAUUSD", "targets": ("XAUUSD", "XCUUSD", "XAUAUD"), "to_country": "global",
     "sign": "+",
     "mechanism": "roughly 1.0-1.3 Moz of gold and 100-150kt of copper in concentrate stop or "
                  "restart on dated lease, drought and security events",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "New Porgera Ltd, Newmont Lihir and Ok Tedi Mining Ltd",
     "constraint": "a single river route at Ok Tedi, a lease at Porgera, a highway at both",
     "flow": "mine supply interruption",
     "condition": "an interruption lasting more than a quarter, not a one-week stoppage",
     "control": "quarters with no interruption; other single-mine outages of comparable size",
     "falsifier": "neither the April 2020 Porgera closure nor the December 2023 restart shows an "
                  "abnormal move against the matched control, in which case a mine of this size "
                  "does not reach the gold price and the channel is demoted to observability",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E6", "country": "FJ",
     "source": "The Fiji Sugar Corporation crushing season and its weekly crush table",
     "target": "SUGARRAW", "targets": ("SUGARRAW", "SUGAR"), "to_country": "global", "sign": "-",
     "mechanism": "150-200kt of raw sugar reaches the world market between June and December "
                  "and none at all outside that window; the timing is physical and public",
     "horizon": "the season", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "the Fiji Sugar Corporation and the cane growers",
     "constraint": "cane ripens on a calendar and the mills cannot crush outside it",
     "flow": "seasonal export supply",
     "condition": "in-season months (June-December) only",
     "control": "the out-of-season months (January-May) as the explicit placebo; the Queensland "
                "crush season on the same instrument",
     "falsifier": "the in-season windows match the out-of-season placebo, which is the expected "
                  "result for a producer this size and is recorded as such",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E7", "country": "PG",
     "source": "PNG highlands arabica harvest volumes and Highlands Highway closures",
     "target": "COFARA", "targets": ("COFARA",), "to_country": "global", "sign": "+",
     "mechanism": "a closed highway strands the harvest inland; the PNG washed-arabica "
                  "differential widens before any export statistic records the shortfall",
     "horizon": "2 to 12 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the PNG Coffee Industry Corporation and the smallholder growers",
     "constraint": "one road connects the highlands to Lae",
     "flow": "origin export shortfall",
     "condition": "a closure lasting more than a week inside the harvest window",
     "control": "harvest windows in years with no closure; Colombian and Ethiopian origin news",
     "falsifier": "highway closures inside the harvest carry no information for COFARA or for "
                  "the PNG differential once Colombian origin news is controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E8", "country": "SB",
     "source": "Solomon Islands and Vanuatu cocoa export permits and shipments",
     "target": "UKCOCOA", "targets": ("UKCOCOA",), "to_country": "global", "sign": "+",
     "mechanism": "a small but real Melanesian cocoa origin whose shipments are dated by permit; "
                  "the London contract is where fine-flavour origin differentials are quoted",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the Solomon Islands Mineral Resources Authority and the cocoa exporters",
     "constraint": "shipping from outer provinces is infrequent and permit-gated",
     "flow": "origin export supply",
     "condition": "permit weeks only",
     "control": "non-permit weeks; West African origin news in the same weeks",
     "falsifier": "no measurable move on UKCOCOA around permit dates once West African news is "
                  "controlled -- the expected result, which the pack records rather than hides",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E9", "country": "regional",
     "source": "Fiji visitor arrivals and PALM/RSE remittance flows from Australia and NZ",
     "target": "AUDUSD", "targets": ("AUDUSD", "NZDUSD", "AUDNZD"), "to_country": "au",
     "sign": "+",
     "mechanism": "Pacific trade, tourism and remittances settle through AUD and NZD; the "
                  "labour-mobility leg is the only flow in this pack whose two legs are both "
                  "quotable on this box",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Australian PALM scheme, the NZ RSE scheme and the Pacific remitters",
     "constraint": "visa caps, employer approvals and a fixed seasonal labour calendar",
     "flow": "remittance and services flow",
     "condition": "conditioned on Australian and New Zealand agricultural employment",
     "control": "years before the PALM consolidation; Philippine and Indonesian remittance "
                "seasonality on other crosses",
     "falsifier": "remittance receipts and arrivals carry no information about AUDNZD once "
                  "Australian and New Zealand agricultural employment is controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "PAC-E10", "country": "regional",
     "source": "A severe tropical cyclone making landfall on the Fijian cane belt, the New "
               "Caledonian ore ports or the PNG LNG loading window",
     "target": "SUGARRAW", "targets": ("SUGARRAW", "SUGAR", "XNIUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "one bulletin closes mills, ore berths and the LNG terminal at once; it is "
                  "the only supply interruption in this pack that is PUBLICLY FORECAST hours "
                  "to days before it happens",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "RSMC Nadi and the national disaster offices whose declarations close the ports",
     "constraint": "the physical track, and a cane and nickel infrastructure with no redundancy",
     "flow": "physical supply interruption",
     "condition": "severe systems that actually made landfall on a producing economy",
     "control": "SEVERE SYSTEMS OF THE SAME CATEGORY THAT DID NOT MAKE LANDFALL -- the warning "
                "was issued and nothing stopped; plus the six non-season months",
     "falsifier": "landfall bulletin windows match the no-landfall systems of the same category, "
                  "in which case the region's physical interruptions are too small to price",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the LNG boom and the birth of the kina backlog", "start": "2014-05-01",
     "end": "2016-12-31",
     "regime": "PNG LNG's first cargo in May 2014, then BPNG's June 2014 trading band, which "
               "created the import-order queue this pack is largely about; Ok Tedi suspended "
               "for the El Nino drought from August 2015",
     "markers": ("2014-05 first PNG LNG cargo", "2014-06 the kina trading band",
                 "2015-08 Ok Tedi drought suspension"),
     "why_it_matters": "the rationing regime begins here; nothing before it is exchangeable "
                       "with anything after it",
     "status": "SETTLED"},
    {"name": "the rationing years and the 2018 earthquake", "start": "2017-01-01",
     "end": "2020-03-15",
     "regime": "a persistent FX backlog with no programme attached, the February 2018 Highlands "
               "earthquake that shut PNG LNG for about two months, and the 2018 APEC year",
     "markers": ("2018-02-26 the M7.5 Highlands earthquake and the PNG LNG force majeure",
                 "2018-11 the APEC leaders' meeting in Port Moresby"),
     "why_it_matters": "the cleanest pre-programme seismic interruption of the LNG plant, with "
                       "no confounding policy event in the same window",
     "status": "SETTLED"},
    {"name": "the pandemic, the Porgera closure and the closed border", "start": "2020-03-16",
     "end": "2022-12-31",
     "regime": "PNG's special mining lease decision shut Porgera from April 2020; Fiji's border "
               "was closed to visitors until December 2021, taking arrivals to zero; New "
               "Caledonia saw blockades around the Goro plant's sale",
     "markers": ("2020-04 Porgera suspended", "2021-12-01 Fiji reopens to tourism",
                 "2020-12 the Goro blockades during the Vale sale"),
     "why_it_matters": "a STRUCTURAL BREAK in every arrivals and mine-production series here; "
                       "smoothing across it invents a recovery that was a reopening",
     "status": "SETTLED"},
    {"name": "the IMF ECF, the scheduled crawl and the reopening", "start": "2023-01-01",
     "end": "2024-05-12",
     "regime": "the PNG Extended Credit Facility approved in March 2023 with a scheduled crawl "
               "and backlog-clearance benchmarks; Porgera restarted in December 2023; Fijian "
               "arrivals returned to pre-pandemic levels",
     "markers": ("2023-03 the ECF approval", "2023-12 the Porgera restart",
                 "2024-01-10 the Port Moresby unrest and the state of emergency"),
     "why_it_matters": "the first time PNG's currency path has a PUBLISHED timetable, which is "
                       "what makes the crawl steps datable events at all",
     "status": "SETTLED"},
    {"name": "the New Caledonia nickel shock and the deferred Papua LNG", "start": "2024-05-13",
     "end": "2026-12-31",
     "regime": "the riots from 13 May 2024 shut New Caledonian nickel haulage and smelting, KNS "
               "went to care and maintenance, SLN has run reduced ever since, and Papua LNG's "
               "FID slipped again while the ECF crawl continued",
     "markers": ("2024-05-13 the riots begin", "2024-05-15 the state of emergency",
                 "2024-08 KNS care and maintenance", "2024-05-24 the Mulitaka landslide"),
     "why_it_matters": "the current regime, and the one the nickel miner is actually about",
     "status": "OPEN"},
)

# --------------------------------------------------------------------------- dated disruptions
#: THE DATED INTERRUPTION ROWS THE MINERS RUN ON, each carrying its STATUS. `RECORDED` means the
#: day is hard and public; `REPORTED` means the month is certain and the day comes from press
#: reporting and must be re-stamped before a cell is compiled on it. Pooling the two silently is
#: the failure this column exists to prevent (L1.28a).
LNG_DISRUPTIONS: tuple[tuple[str, str, str], ...] = (
    ("2018-02-26", "PNG: the M7.5 Highlands earthquake; PNG LNG and the Hides plant stopped and "
                   "force majeure was declared", "RECORDED"),
    ("2020-03-24", "PNG: the first national COVID-19 state of emergency restricted crew rotation "
                   "and movement to the highlands facilities", "REPORTED"),
    ("2024-01-10", "PNG: the Port Moresby unrest and the 14-day state of emergency", "RECORDED"),
    ("2024-05-24", "PNG: the Mulitaka landslide in Enga closed the highlands road corridor",
     "RECORDED"),
)
NICKEL_DISRUPTIONS: tuple[tuple[str, str, str], ...] = (
    ("2020-12-10", "New Caledonia: blockades and arson around the Goro plant during the Vale "
                   "sale process", "REPORTED"),
    ("2024-02-12", "New Caledonia: Glencore announced it would stop funding Koniambo Nickel and "
                   "seek a buyer", "REPORTED"),
    ("2024-05-13", "New Caledonia: the riots begin; roadblocks cut the rouleurs from the mines "
                   "and Doniambo stopped", "RECORDED"),
    ("2024-05-15", "New Caledonia: the state of emergency and curfew were declared", "RECORDED"),
    ("2024-08-30", "New Caledonia: Koniambo Nickel entered care and maintenance", "REPORTED"),
)
MINE_DISRUPTIONS: tuple[tuple[str, str, str], ...] = (
    ("2015-08-20", "PNG: Ok Tedi suspended on El Nino low water in the Fly River", "REPORTED"),
    ("2016-03-15", "PNG: Ok Tedi resumed as the river rose", "REPORTED"),
    ("2020-04-24", "PNG: Porgera suspended after the special mining lease was not extended",
     "REPORTED"),
    ("2023-12-22", "PNG: Porgera restarted as New Porgera Ltd", "REPORTED"),
    ("2024-05-24", "PNG: the Mulitaka landslide cut the Enga corridor serving Porgera",
     "RECORDED"),
)
#: The opening business days in which the following month's PNG LNG lifting programme is fixed,
#: and the mid-month days that carry no nomination and are therefore the placebo.
LNG_NOMINATION_DAYS: tuple[int, ...] = (1, 2, 3, 4, 5)
LNG_PLACEBO_DAYS: tuple[int, ...] = (12, 13, 14, 15, 16)
#: Fiji's crushing season and its complement. The out-of-season months are the DESIGN.
CRUSH_MONTHS: tuple[int, ...] = (6, 7, 8, 9, 10, 11, 12)
OUT_OF_SEASON_MONTHS: tuple[int, ...] = (1, 2, 3, 4, 5)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no Pacific currency is quoted by this broker",
     "measured": "data/universe/universe.json holds no PGK, FJD, SBD, VUV, XPF, WST or TOP",
     "consequence": "every domestic mechanism terminates in energy, metals, softs or the "
                    "AUD/NZD complex; the Pacific currencies are INPUTS, never cells"},
    {"constraint": "no Pacific equity index has a CFD and no Pacific derivative exists",
     "measured": "PNGX and SPX are absent from the universe; neither lists derivatives",
     "consequence": "the boards enter only as transmission targets, and the region has NO "
                    "traded consensus of any kind against which a policy surprise could be "
                    "measured -- which PAC-PNG-A and PAC-FJ-A both state on their face"},
    {"constraint": "no tuna instrument exists on any venue the desk can reach",
     "measured": "no tuna, skipjack or fish contract is in the universe or in any feed here",
     "consequence": "the PNA Vessel Day Scheme, a genuine cartel, is declared INPUT-ONLY and "
                    "compiles no price cell (L1.49); its falsifiable claim is fiscal"},
    {"constraint": "JKM and the JCC index are both absent",
     "measured": "the universe holds XNGUSD (Henry Hub) and XBRUSD, and no Asian gas leg",
     "consequence": "every PNG LNG reading is declared a WEAK-PROXY reading and is never "
                    "promoted above HYPOTHESIS on the gas leg alone"},
    {"constraint": "PNG and several Pacific statistics offices publish with a lag of quarters "
                   "and rebuild their websites without keeping the back-run",
     "measured": "BPNG QEB lag is around 100 days and earlier quarters are silently restated",
     "consequence": "PIT-safe Pacific series are assembled from archive snapshots or they are "
                    "declared UNMEASURED; a restated quarter is never spliced to a live one"},
    {"constraint": "Fastmarkets, Argus and Platts forbid machine extraction",
     "measured": "their subscription terms; registered machine_use_allowed=false",
     "consequence": "the nickel ore assessment and the JKM level are UNMEASURED here; the "
                    "DIMENC monthly export split and the LME official print are what the desk "
                    "actually reads"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "the BPNG foreign exchange order backlog and allocation statements",
    "RBF monthly foreign reserves and months of import cover",
    "PNA Vessel Day Scheme days allocated, sold and traded",
    "Australian DEWR PALM worker numbers and the World Bank Pacific corridor prices",
    "Fiji Bureau of Statistics visitor arrivals by source market")
SERIES: dict[str, str] = {
    "PAC_PNG_KFR": "BPNG:kfr", "PAC_PNG_RESERVES": "BPNG:qeb_reserves",
    "PAC_PNG_BACKLOG": "BPNG:fx_backlog_months", "PAC_FJ_OPR": "RBF:opr",
    "PAC_FJ_RESERVES": "RBF:import_cover_months", "PAC_FJ_ARRIVALS": "FBOS:arrivals",
    "PAC_FJ_CRUSH": "FSC:crush_weekly", "PAC_NC_NICKEL": "DIMENC:nickel_exports",
    "PAC_JCC": "METI:jcc", "PAC_PALM": "DEWR:palm_workers",
}

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
        "mission": MISSION, "currencies": CURRENCIES, "fiscal_years": FISCAL_YEARS,
        "other_central_banks": OTHER_CENTRAL_BANKS, "native_glossary": NATIVE_GLOSSARY,
        "jurisdictions": JURISDICTIONS, "lng_disruptions": LNG_DISRUPTIONS,
        "nickel_disruptions": NICKEL_DISRUPTIONS, "mine_disruptions": MINE_DISRUPTIONS,
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
    """The framework's HolidayRule shape: every WEEKDAY closure the six calendars produce for
    2024-2026, plus the fixed month-days of the two largest jurisdictions."""
    dates = sorted({d.isoformat() for y in HOLIDAY_YEARS for d in market_holidays(y)})
    fixed = tuple(f"{m:02d}-{d:02d}" for m, d, _ in (*FIXED_PG, *FIXED_FJ))
    return {"dates": tuple(dates), "fixed_md": fixed, "weekly_closed": (5, 6),
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
