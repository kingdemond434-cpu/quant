"""MOROCCO: a BASKET-PEGGED economy inside a widening band, sitting on the world's phosphate.

WHAT MOROCCO IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER FRANCE OR A SECOND EGYPT. Six
things belong to this economy and to no other in the desk's book, and each one is why a domain
below exists rather than a row in a generic emerging-market domain:

  1. THE DIRHAM IS A BASKET AND THE BASKET IS READABLE. Since 2015-04-13 the dirham is fixed
     against 60% EUR / 40% USD, and Bank Al-Maghrib publishes a reference rate ("cours de
     reference") every business day. The fluctuation band was widened from +/-0.3% to +/-2.5%
     on 2018-01-15 and to +/-5.0% on 2020-03-09, with a stated path to a float that has not
     been taken. MAD is NOT quoted by this broker -- and it does not need to be: the basket's
     own arithmetic makes EURUSD the leg that moves the dirham's two sides against each other,
     and the DISTANCE TO THE BAND EDGE is a measurable state, not a story. When the rate sits
     at the strong or weak edge, Bank Al-Maghrib's auction is the counterparty and the
     authorities' reaction function is known in advance.

  2. THE COUNTRY SITS ON ABOUT 70% OF THE WORLD'S PHOSPHATE ROCK RESERVES. OCP is a state-owned
     swing supplier of DAP/TSP fertiliser and its export pricing enters the NORTHERN-HEMISPHERE
     PLANTING DECISION: a farmer who cannot afford phosphate plants fewer acres, or switches to
     the crop that needs less of it. That reaches CORN, WHEAT and SOYBEAN as an INPUT-direction
     mechanism -- the pack declares the direction honestly rather than claiming Morocco moves
     Chicago -- and the fertiliser price assessments themselves (CRU, Argus, Profercy) are
     LICENSED ground registered here and never scraped.

  3. THE CEREAL IMPORT IS ADMINISTERED ON A DECREE CLOCK. ONICL runs the import regime, the
     restitution (the per-quintal subsidy paid to importers) is switched on and off, and the
     customs duty on SOFT WHEAT is raised to protect the harvest and suspended to secure supply
     -- by decree, published in the Bulletin Officiel, clustered at the marketing-year boundary.
     That is a genuine administered event on WHEAT, with a real placebo: the same boundary days
     in the years when the duty did not move.

  4. THE WEATHER IS THE FISCAL POLICY. The agricultural campaign runs September to May, the
     barrage (dam) fill rate is published as a national number, and a drought year flips Morocco
     from a cereal EXPORTER of its own durum surplus to a 5-7 mt importer while GDP loses two
     points. No other pack on this desk has a rainfall series that swings a whole trade account.

  5. THERE IS NO REFINERY. The Samir refinery has been shut since August 2015, so Morocco
     imports REFINED PRODUCT, not crude. That is a different channel from a crude importer's:
     the exposure is to the CRACK and to product freight, and crude is only the first leg of it.
     The gas picture is the same shape: the Maghreb-Europe pipeline was closed by Algeria on
     2021-10-31, the Nigeria-Morocco pipeline is a decade-long project, and the Xlinks UK
     interconnector is a dated foreign policy decision -- every one of them a weak XNGUSD edge
     that says so on its face.

  6. THE CLOCK ITSELF MOVES FOR RAMADAN. Morocco keeps UTC+1 all year ("heure legale", since
     2018-10-28) EXCEPT that it returns to UTC+0 for Ramadan -- from the Sunday before the
     fast at 03:00 to the Sunday after Aid al-Fitr at 02:00. The whole Moroccan business day,
     the Casablanca session and the reference-rate publication move one hour LATER IN UTC for
     about five weeks a year. No other country on this desk does that, a session study that
     pools those weeks is measuring two different hours, and the pack carries the window as a
     declared state with the matched-weekday control beside it.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDMAD, EURMAD, the MASI, the 13-week Treasury bill, the
Moroccan eurobond curve, the OCP bond, the bureaux-de-change cash rate and the CRU/Argus DAP
assessment are all ABSENT from `data/universe/universe.json`. Every one is named in
`TRANSMISSION_TARGETS` with the broker symbols its mechanism reaches, so an absent instrument
produces a transmission hypothesis and never a cell that can never be filled (L1.49).

THE TWO-LANE ORDER (2026-09-06). Moroccan market commentary is company-heavy -- Attijariwafa,
Maroc Telecom, LafargeHolcim Maroc, Managem, Cosumar, Taqa Morocco -- and every one of those is
an EVENT-lane instrument. They enter this pack only as ACTORS (a sugar refiner that buys raws, a
miller that buys soft wheat, a bank whose Spanish parent is the transmission leg), and the
instruments those actors move are softs, energy, metals, the euro legs and the European indices.
No share CFD appears in any instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "MA"
NAME = "Morocco"
REGION_COMMAND = "mea"             # the framework's command; the forest is mena
REGION_DESK = "MENA"
FOREST = "mena"
CURRENCY = "MAD"
FISCAL_YEAR_END = "12-31"          # the loi de finances runs on the calendar year since 2019
NATIVE_LANGUAGES: tuple[str, ...] = ("ar", "fr", "ber", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the dirham
EXPORT_ECONOMY = "commodity_exporter"          # phosphate rock and fertiliser are the world price
RETAIL_LEVERAGE_REGIME = "restricted"          # Office des Changes: residents may not margin abroad
MISSION = ("mine Morocco as the basket-pegged, band-widening, phosphate-holding and "
           "decree-administered economy it is: the quarterly Conseil and the taux directeur, the "
           "60/40 basket and its band edge, OCP's fertiliser price inside the planting decision, "
           "the ONICL cereal tender and the soft-wheat duty switch, the barrage fill rate, the "
           "refined-product import, and the Ramadan return to UTC+0 that moves the whole "
           "Moroccan day one hour later in UTC for five weeks a year")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The dirham itself is absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURUSD", "USDX",                                  # the two legs of the 60/40 basket
    "WHEAT", "CORN", "SOYBEAN",                        # the fertiliser input and the cereal tender
    "SUGARRAW", "SUGAR",                               # COSUMAR's raws and the subsidised white
    "XBRUSD", "XTIUSD", "XNGUSD",                      # refined product, the crack, the pipelines
    "E35", "FRA40",                                    # Spain and France: trade, banks, tourism
    "EURTRY", "EURZAR",                                # the frontier/EM stress beta in euro terms
    "XAUUSD",                                          # reserves, retail demand and the Aid season
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/MAD and EUR/MAD (the Bank Al-Maghrib reference rate)",
     "venue": "Bank Al-Maghrib / the interbank FX market",
     "why": "the currency every mechanism here is about, absent from the broker; the 60/40 "
            "basket makes EURUSD the readable leg and the band edge the readable state",
     "proxies": ("EURUSD", "USDX", "EURTRY")},
    {"name": "The bureaux-de-change and informal cash dirham rate",
     "venue": "licensed bureaux de change and the parallel market",
     "why": "the second price of the dirham under exchange control; its spread to the reference "
            "rate is the capital-control stress state MA-B conditions on",
     "proxies": ("EURUSD", "XAUUSD")},
    {"name": "MASI and MSI20 (Casablanca Stock Exchange indices)",
     "venue": "Bourse de Casablanca",
     "why": "no CFD is quoted; the foreign-ownership share and the 10% price limit are read "
            "instead, and the European bank parents carry the executable leg",
     "proxies": ("E35", "FRA40")},
    {"name": "The 13/26/52-week Treasury bill and the BDT curve",
     "venue": "Direction du Tresor primary auctions",
     "why": "the domestic rate path and the consensus between two quarterly Conseil meetings",
     "proxies": ("EURUSD", "XAUUSD")},
    {"name": "Morocco's EUR and USD eurobonds and the sovereign spread",
     "venue": "OTC", "why": "the external-financing channel; Morocco is investment grade at one "
                            "agency and sub-investment at another, which is itself the state",
     "proxies": ("EURTRY", "EURZAR", "EURUSD")},
    {"name": "CRU / Argus / Profercy DAP-TSP and phosphate rock assessments",
     "venue": "price reporting agencies",
     "why": "the actual phosphate price; LICENSED and never scraped, so the fertiliser cost "
            "enters the pack through the planting-decision crops it moves",
     "proxies": ("CORN", "WHEAT", "SOYBEAN")},
    {"name": "ONICL soft-wheat import tenders and the restitution notices",
     "venue": "ONICL / the millers' federations",
     "why": "the state's cereal trade decision, dated and published in the Bulletin Officiel",
     "proxies": ("WHEAT", "CORN")},
    {"name": "Platts/Argus refined-product cargo assessments for Mohammedia and Jorf Lasfar",
     "venue": "price reporting agencies",
     "why": "with Samir shut, Morocco buys PRODUCT; the crack is the exposure and XBRUSD is only "
            "its first leg, which is stated on every energy edge",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "The Maghreb-Europe and Nigeria-Morocco gas pipelines and the LNG tender",
     "venue": "ONEE / the Ministry of Energy",
     "why": "Algeria closed the GME on 2021-10-31 and Morocco now imports regasified cargoes "
            "through Spain; the true leg is TTF, which is absent, so XNGUSD is a weak proxy",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "The Office des Changes MRE remittance and tourism receipts",
     "venue": "Office des Changes",
     "why": "about 8-9% of GDP in EUR-denominated inflows with a summer peak; the conversion "
            "leg is the euro itself, and the seasonal window is the object",
     "proxies": ("EURUSD", "XAUUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank Al-Maghrib -- Conseil de Bank Al-Maghrib",
    "short": "BAM",
    "framework": "band",
    "committee": "the Conseil: the Wali (Governor), the Director of the Treasury, and six "
                 "independent members appointed by the King and the head of government",
    "policy_instrument": "the taux directeur (the rate of the 7-day advances), inside a corridor "
                         "whose floor is the 24-hour deposit facility and whose ceiling is the "
                         "24-hour advance",
    "mandate": "price stability under the 2019 statute, alongside the exchange-rate regime the "
               "government sets after consulting the bank; an inflation target is NOT announced "
               "as a number, which is why a 'surprise' here is measured against the taux "
               "directeur path and never against a published target",
    "decision_rule": "FOUR scheduled Conseil meetings a year -- March, June, September and "
                     "December -- on a calendar Bank Al-Maghrib publishes in advance; the "
                     "communique and the Wali's press conference land the same afternoon",
    "decision_calendar_rule": "four meetings a year, usually the third or fourth Tuesday of the "
                              "quarter's last month, published at bkam.ma; the announcement "
                              "minute must be stamped from the communique, never assumed",
    "decision_dates": (
        "2022-03-22", "2022-06-21", "2022-09-27", "2022-12-20",
        "2023-03-21", "2023-06-20", "2023-09-26", "2023-12-19",
        "2024-03-19", "2024-06-25", "2024-09-24", "2024-12-17",
        "2025-03-18", "2025-06-24", "2025-09-23", "2025-12-16"),
    "dates_status": "2022-2025: the quarterly Conseil days as carried by the communiques and the "
                    "trade press; RE-VERIFY each one against the bkam.ma communique before a "
                    "cell is compiled on it, because the Conseil occasionally moves within the "
                    "month. 2026: NOT LISTED -- Bank Al-Maghrib publishes the calendar and this "
                    "pack refuses to invent it (L1.28a)",
    "decision_time_utc": "15:00",
    "announce_local": "mid-afternoon Africa/Casablanca (UTC+1 year-round, UTC+0 in Ramadan); the "
                      "communique is followed by the Wali's press conference",
    "dst_rule": "Morocco keeps UTC+1 all year ('heure legale', permanent since 2018-10-28) and "
                "returns to UTC+0 FOR RAMADAN ONLY, so the UTC minute of a Casablanca event "
                "moves one hour LATER for about five weeks each year",
    "minutes_lag_days": 0,
    "publication_classes": ("communique_du_conseil", "rapport_sur_la_politique_monetaire",
                            "rapport_annuel", "statistiques_monetaires", "cours_de_reference",
                            "adjudication_avances_7_jours", "adjudication_de_devises"),
    "policy_rate_series": "BAM:taux_directeur",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the 13-week Treasury-bill cut-off and the 3-month interbank rate between "
                       "meetings; the bank research houses (Attijari Global Research, BMCE "
                       "Capital, CDG Capital) publish a pre-Conseil expectation",
    "consensus_proxy_trap": "the interbank rate is pinned to the taux directeur by the weekly "
                            "7-day advance, so it moves with the ALLOTMENT and not only with the "
                            "expectation; a move there is a liquidity fact first",
    "reserves_clock": "official reserve assets are published monthly in the statistiques "
                      "monetaires and weekly in the bank's own indicators; an IMF facility draw "
                      "or a eurobond issue appears as a single step",
    "programme": "Morocco has used PRECAUTIONARY IMF facilities (the Precautionary and Liquidity "
                 "Line, then the Flexible Credit Line approved 2023-04-03, plus a Resilience and "
                 "Sustainability Facility) -- the country is NOT under a disbursing adjustment "
                 "programme, so the IMF calendar here is an Article IV and review clock rather "
                 "than a tranche clock, which is the opposite of the Pakistani case",
    "off_cycle": ("2020-03-17 emergency cut to 2.00% ahead of the lockdown",
                  "2020-06-16 cut to 1.50%"),
    "root": "https://www.bkam.ma",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank Al-Maghrib cours de reference (the official dirham fixing)",
     "local": "published each business day around 12:30 Africa/Casablanca",
     "time_utc": "11:30", "time_utc_dst": "12:30",
     "dst_rule": "UTC+1 all year; UTC+0 in Ramadan, so the UTC minute moves one hour LATER",
     "instruments": ("EURUSD", "USDX"), "window_minutes": 30,
     "why": "the official dirham reference the customs, the importers and the band are read "
            "against; the basket's arithmetic makes EURUSD its readable leg"},
    {"name": "Bank Al-Maghrib FX auction (adjudication de devises)",
     "local": "announced and settled intraday when the rate approaches a band edge",
     "time_utc": "10:00", "time_utc_dst": "11:00", "dst_rule": "UTC+1; UTC+0 in Ramadan",
     "instruments": ("EURUSD", "USDX"), "window_minutes": 60,
     "why": "the central bank is the counterparty at the edge; the auction is the reaction "
            "function MA-B conditions on"},
    {"name": "Weekly 7-day advance tender (avances a 7 jours)",
     "local": "announced Tuesday, settled Wednesday, Africa/Casablanca",
     "time_utc": "09:00", "time_utc_dst": "10:00", "dst_rule": "UTC+1; UTC+0 in Ramadan",
     "instruments": ("EURUSD",), "window_minutes": 60,
     "why": "the allotment against the banks' liquidity deficit is the operational policy stance "
            "between two quarterly Conseil meetings"},
    {"name": "Casablanca Stock Exchange closing auction (MASI fixing)",
     "local": "15:30 Africa/Casablanca", "time_utc": "14:30", "time_utc_dst": "15:30",
     "dst_rule": "UTC+1; UTC+0 in Ramadan", "instruments": ("E35", "FRA40"),
     "window_minutes": 30,
     "why": "the domestic close; no MASI CFD exists, so the European parents' indices carry it"},
    {"name": "LBMA gold price PM auction (the dirham gold reference's dollar leg)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the reference the Moroccan retail gold price and the reserve valuation derive from"},
    {"name": "Jorf Lasfar phosphate and fertiliser cargo assessment window",
     "local": "weekly, published by the price reporting agencies", "time_utc": "16:00",
     "time_utc_dst": "16:00", "dst_rule": "none (a PRA publication, not a local fixing)",
     "instruments": ("CORN", "WHEAT", "SOYBEAN"), "window_minutes": 120,
     "why": "the DAP/TSP price that enters the planting decision; LICENSED ground, so the "
            "assessment is registered and the CROPS are what the pack measures"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Weekly 7-day advance tender", "kind": "weekday", "weekday": 1, "roll": "next",
     "window_utc": ("08:00", "11:00"), "instruments": ("EURUSD",),
     "why": "Bank Al-Maghrib announces the allotment every Tuesday and settles it Wednesday"},
    {"name": "Treasury bill (BDT) primary auction", "kind": "weekday", "weekday": 1,
     "roll": "next", "window_utc": ("09:00", "13:00"), "instruments": ("EURUSD", "XAUUSD"),
     "why": "the Direction du Tresor auctions on Tuesdays; the cut-off is the domestic rate path"},
    {"name": "Casablanca Stock Exchange T+2 settlement and the month-end index review",
     "kind": "month_end", "roll": "previous", "window_utc": ("13:00", "15:00"),
     "instruments": ("E35", "FRA40"),
     "why": "Maroclear settles T+2; the free-float and MASI reviews cluster at the month end"},
    {"name": "Month-end importer FX demand (energy and cereal letters of credit)",
     "kind": "month_end", "roll": "previous", "window_utc": ("08:00", "14:00"),
     "instruments": ("EURUSD", "XBRUSD", "WHEAT"),
     "why": "the product cargoes and the cereal tenders are settled into the last business days, "
            "which is when the reference rate is pushed toward the weak edge"},
    {"name": "Fiscal year end (31 December) and the loi de finances", "kind": "fiscal_year_end",
     "roll": "previous", "window_utc": ("08:00", "16:00"), "instruments": ("EURUSD", "XAUUSD"),
     "why": "the budget year is the calendar year; the subsidy (compensation) envelope, the "
            "customs tariff schedule and the eurobond programme are all dated to it"},
    {"name": "Quarter-end Conseil and Article IV review dates", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("13:00", "17:00"), "instruments": ("EURUSD",),
     "why": "the Conseil sits in the last month of each quarter; the IMF review calendar tracks "
            "the same boundaries"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bourse de Casablanca -- MASI, MSI20, MASI ESG",
     "index_symbols": (),
     "open_local": "09:30 (pre-opening from 09:00)", "close_local": "15:30",
     "open_utc": "08:30", "close_utc": "14:30",
     "dst_rule": "UTC+1 all year, UTC+0 IN RAMADAN -- the session's UTC window moves to "
                 "09:30-15:30 for about five weeks a year",
     "auction": "pre-opening call 09:00-09:30, continuous trading, closing call at 15:30",
     "expiry_rule": "no listed index derivatives; a futures market has been announced for years "
                    "and has not launched, so there is no expiry clock to mine",
     "holidays": "the national calendar including the moon-sighted feasts; the session does not "
                 "shorten for Ramadan but the whole local clock moves to UTC+0",
     "notes": "NO CFD IS QUOTED on the MASI, so the index enters only as a transmission target; "
              "the 10% daily price limit per security (and the resulting queue) is the "
              "microstructure fact MA-K studies, and the AMMC publishes the foreign-ownership "
              "share annually rather than daily, which bounds what MA-K can ever measure"},
    {"name": "The interbank FX market and the licensed bureaux de change",
     "index_symbols": (), "open_local": "08:30", "close_local": "15:30",
     "open_utc": "07:30", "close_utc": "14:30", "dst_rule": "UTC+1; UTC+0 in Ramadan",
     "auction": "Bank Al-Maghrib's FX auctions when the rate approaches a band edge",
     "expiry_rule": "forwards and options are dealt under Office des Changes authorisation and "
                    "are not an exchange clock",
     "holidays": "the banking calendar",
     "notes": "thin and administered; the cash market's spread to the reference rate is the "
              "capital-control stress observable"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "ma_reference_rate", "start_utc": "11:00", "end_utc": "12:00",
     "notes": "the cours de reference is published around 12:30 local; in Ramadan the same local "
              "minute is 12:30 UTC, which is why this window is declared twice"},
    {"name": "ma_reference_rate_ramadan", "start_utc": "12:00", "end_utc": "13:00",
     "notes": "the Ramadan UTC+0 leg of the same publication"},
    {"name": "ma_bourse_standard", "start_utc": "08:30", "end_utc": "14:30",
     "notes": "the Casablanca session outside Ramadan (local UTC+1)"},
    {"name": "ma_bourse_ramadan", "start_utc": "09:30", "end_utc": "15:30",
     "notes": "the SAME local hours during Ramadan, when the country is on UTC+0; a session "
              "study that pools the two is measuring two different hours"},
    {"name": "ma_conseil_afternoon", "start_utc": "14:00", "end_utc": "17:00",
     "notes": "the quarterly Conseil communique and the Wali's press conference"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Conseil de Bank Al-Maghrib communique and the monetary policy report",
     "cadence": "quarterly", "time_utc": "15:00", "source": "Bank Al-Maghrib",
     "actual_series": "BAM:taux_directeur", "expected_series": "UNMEASURED",
     "notes": "four a year; the press conference carries the inflation projection revision"},
    {"name": "Cours de reference (the daily dirham fixing)", "cadence": "daily",
     "time_utc": "11:30", "source": "Bank Al-Maghrib", "actual_series": "BAM:reference_rate",
     "expected_series": "UNMEASURED",
     "notes": "every business day; the band bounds are derived from the basket, not published"},
    {"name": "Indice des prix a la consommation (IPC)", "cadence": "monthly", "time_utc": "10:00",
     "source": "Haut-Commissariat au Plan", "actual_series": "HCP:ipc",
     "expected_series": "UNMEASURED",
     "notes": "around the 20th for the prior month; the food line carries the drought"},
    {"name": "Indicateurs mensuels des echanges exterieurs (trade, MRE, tourism)",
     "cadence": "monthly", "time_utc": "12:00", "source": "Office des Changes",
     "actual_series": "OC:balance_commerciale", "expected_series": "UNMEASURED",
     "notes": "the MRE transfer and travel-receipt lines are the two EUR inflows of MA-J"},
    {"name": "Situation des barrages (dam fill rate)", "cadence": "weekly", "time_utc": "09:00",
     "source": "Ministere de l'Equipement et de l'Eau", "actual_series": "MEE:taux_remplissage",
     "expected_series": "n/a",
     "notes": "the national fill percentage; the single best early read on the campaign"},
    {"name": "ONICL cereal situation: stocks, collection, imports, restitution notices",
     "cadence": "monthly", "time_utc": "12:00", "source": "ONICL",
     "actual_series": "ONICL:imports", "expected_series": "n/a",
     "notes": "the state's own count of what came in and at what subsidy"},
    {"name": "Bulletin Officiel customs decrees (soft-wheat duty, tariff suspensions)",
     "cadence": "monthly", "time_utc": "UNMEASURED", "source": "SGG / ADII",
     "actual_series": "BO:decrets_douane", "expected_series": "n/a",
     "notes": "irregular and dated; the decree is the event, the press report is the stamp"},
    {"name": "OCP Group quarterly and annual results (volumes and realised prices)",
     "cadence": "quarterly", "time_utc": "16:00", "source": "OCP Group",
     "actual_series": "OCP:export_volumes", "expected_series": "n/a",
     "notes": "the group is a bond issuer and publishes; the PRA price is LICENSED and absent"},
)

# --------------------------------------------------------------------------- holidays
#: FIXED national holidays. Ras as-Sana al-Amazighia (14 January) became a PAID national holiday
#: by royal decision in 2023 and was first observed on 2024-01-14 -- a new closed day that a
#: study pooling 2019-2025 will otherwise mislabel. Morocco does NOT substitute a holiday that
#: falls at the weekend: the day is simply lost, which is itself a liquidity fact.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Nouvel An / راس السنة الميلادية"),
    (1, 11, "Manifeste de l'Independance / ذكرى تقديم وثيقة الاستقلال"),
    (1, 14, "Ras as-Sana al-Amazighia / ⵢⴻⵏⵏⴰⵢⴻⵔ (paid national holiday since 2024)"),
    (5, 1, "Fete du Travail / عيد الشغل"),
    (7, 30, "Fete du Trone / عيد العرش"),
    (8, 14, "Oued Ed-Dahab / ذكرى استرجاع وادي الذهب"),
    (8, 20, "Revolution du Roi et du Peuple / ثورة الملك والشعب"),
    (8, 21, "Fete de la Jeunesse / عيد الشباب"),
    (11, 6, "Marche Verte / ذكرى المسيرة الخضراء"),
    (11, 18, "Fete de l'Independance / عيد الاستقلال"),
)
#: The bank calendar adds nothing Morocco's national calendar does not already close, but the
#: 2 January half-year/annual closing is a settlement convention rather than a holiday and is
#: carried in SETTLEMENT_CONVENTIONS instead.
BANK_HOLIDAYS: tuple[tuple[int, int, str], ...] = ()

#: THE MOON-SIGHTED FEASTS, ANNOUNCED for 2024-2025 and PROJECTED for 2026. The Ministry of
#: Habous and Islamic Affairs announces the sighting the EVENING BEFORE, and Morocco frequently
#: lands one day AFTER Saudi Arabia -- so a Gulf calendar is the wrong calendar here and a
#: projected row can be a day off. Each row: (date, name, status).
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 4, 10), "Aid al-Fitr (day 1) / عيد الفطر", "ANNOUNCED"),
           (date(2024, 4, 11), "Aid al-Fitr (day 2) / عيد الفطر", "ANNOUNCED"),
           (date(2024, 6, 17), "Aid al-Adha (day 1) / عيد الأضحى", "ANNOUNCED"),
           (date(2024, 6, 18), "Aid al-Adha (day 2) / عيد الأضحى", "ANNOUNCED"),
           (date(2024, 7, 8), "Fatih Muharram / فاتح محرم", "ANNOUNCED"),
           (date(2024, 9, 16), "Aid al-Mawlid (day 1) / عيد المولد النبوي", "PROJECTED"),
           (date(2024, 9, 17), "Aid al-Mawlid (day 2) / عيد المولد النبوي", "PROJECTED")),
    2025: ((date(2025, 3, 31), "Aid al-Fitr (day 1) / عيد الفطر", "ANNOUNCED"),
           (date(2025, 4, 1), "Aid al-Fitr (day 2) / عيد الفطر", "ANNOUNCED"),
           (date(2025, 6, 7), "Aid al-Adha (day 1 Saturday) / عيد الأضحى", "ANNOUNCED"),
           (date(2025, 6, 8), "Aid al-Adha (day 2 Sunday) / عيد الأضحى", "ANNOUNCED"),
           (date(2025, 6, 27), "Fatih Muharram / فاتح محرم", "PROJECTED"),
           (date(2025, 9, 5), "Aid al-Mawlid (day 1) / عيد المولد النبوي", "PROJECTED"),
           (date(2025, 9, 6), "Aid al-Mawlid (day 2) / عيد المولد النبوي", "PROJECTED")),
    2026: ((date(2026, 3, 20), "Aid al-Fitr (day 1) / عيد الفطر", "PROJECTED"),
           (date(2026, 3, 21), "Aid al-Fitr (day 2) / عيد الفطر", "PROJECTED"),
           (date(2026, 5, 27), "Aid al-Adha (day 1) / عيد الأضحى", "PROJECTED"),
           (date(2026, 5, 28), "Aid al-Adha (day 2) / عيد الأضحى", "PROJECTED"),
           (date(2026, 6, 17), "Fatih Muharram / فاتح محرم", "PROJECTED"),
           (date(2026, 8, 25), "Aid al-Mawlid (day 1) / عيد المولد النبوي", "PROJECTED"),
           (date(2026, 8, 26), "Aid al-Mawlid (day 2) / عيد المولد النبوي", "PROJECTED")),
}
#: One-off closures and clock facts no recurring rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 1, 14): "first observance of the Amazigh New Year as a paid national holiday "
                       "(a Sunday in 2024, so no session was lost)",
    date(2025, 7, 30): "Fete du Trone on a Wednesday; the banks and the bourse closed",
}

#: THE RAMADAN CLOCK. Morocco keeps UTC+1 all year and RETURNS TO UTC+0 FOR RAMADAN -- by decree,
#: from the Sunday before the fast at 03:00 to the Sunday after Aid al-Fitr at 02:00. Rows are
#: (gmt_start, gmt_end, status); the two dates are the Sundays, derived by that rule and checked
#: against the published decree for the ANNOUNCED years.
RAMADAN_CLOCK: dict[int, tuple[date, date, str]] = {
    2022: (date(2022, 3, 27), date(2022, 5, 8), "ANNOUNCED"),
    2023: (date(2023, 3, 19), date(2023, 4, 23), "ANNOUNCED"),
    2024: (date(2024, 3, 10), date(2024, 4, 14), "ANNOUNCED"),
    2025: (date(2025, 2, 23), date(2025, 4, 6), "ANNOUNCED"),
    2026: (date(2026, 2, 15), date(2026, 3, 22), "PROJECTED"),
}

#: THE SOFT-WHEAT CUSTOMS DUTY, switched by decree. The duty is raised to protect the domestic
#: harvest and suspended (with a restitution paid to importers) when the crop fails, and the
#: switch clusters at the MARKETING-YEAR BOUNDARY: restoration into the May-June harvest,
#: suspension into the October-November import season. Rows are (date, action, status), and
#: PRESS_REPORTED means exactly that -- the date as carried by the trade press, to be confirmed
#: against the Bulletin Officiel number before any cell is compiled on it. Nothing here is
#: presented as a verified BO citation, because it is not one.
DUTY_DECREES: tuple[tuple[date, str, str], ...] = (
    (date(2021, 5, 1), "duty restored at the harvest", "PRESS_REPORTED"),
    (date(2021, 11, 1), "duty suspended and the restitution opened", "PRESS_REPORTED"),
    (date(2022, 5, 1), "suspension extended through the drought year", "PRESS_REPORTED"),
    (date(2022, 11, 1), "suspension extended into the import season", "PRESS_REPORTED"),
    (date(2023, 5, 1), "suspension extended; the harvest failed again", "PRESS_REPORTED"),
    (date(2023, 11, 1), "restitution reopened for the import season", "PRESS_REPORTED"),
    (date(2024, 6, 1), "duty restored at the harvest", "PRESS_REPORTED"),
    (date(2024, 10, 1), "duty suspended for the import season", "PRESS_REPORTED"),
    (date(2025, 5, 1), "duty restored at the harvest", "PRESS_REPORTED"),
)
#: The rule the decrees follow when the pack cannot cite one: the marketing-year boundary days.
CAMPAIGN_BOUNDARY_DAYS: tuple[int, ...] = (1,)
CAMPAIGN_BOUNDARY_MONTHS: tuple[int, ...] = (5, 6, 10, 11)


def national_holidays(year: int) -> dict[date, str]:
    """National holidays: the fixed ones, the moon-sighted ones as announced or projected, and
    the one-off declarations. Morocco does NOT substitute a weekend holiday -- the day is lost,
    which a liquidity study must carry rather than silently gaining a Monday."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL:
        out[date(year, m, d)] = name
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = name
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    out = national_holidays(year)
    for m, d, name in BANK_HOLIDAYS:
        out[date(year, m, d)] = name
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """Bourse de Casablanca closed days: the bank calendar on weekdays only, because a Saturday
    closure costs no session and must not enter a holiday-liquidity sample as one."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def announced_dates(year: int) -> dict[date, str]:
    """Only the moon-sighted dates that were ANNOUNCED. A study that pools PROJECTED rows into
    the announced sample must say so: Morocco's sighting often lands a day after the Gulf's."""
    return {d: n for d, n, st in LUNAR_HOLIDAYS.get(year, ()) if st == "ANNOUNCED"}


def ramadan_clock_window(year: int) -> tuple[date, date, str] | None:
    """The UTC+0 window for a year as (start Sunday, end Sunday, status), or None when the pack
    has not declared it. Inside this window every Moroccan local hour is one hour LATER in UTC."""
    return RAMADAN_CLOCK.get(year)


def is_gmt_window(day: date) -> bool:
    """True when Morocco is on UTC+0 on this date (the Ramadan clock), False when on UTC+1."""
    got = RAMADAN_CLOCK.get(day.year)
    return got is not None and got[0] <= day < got[1]


def utc_offset_hours(day: date) -> int:
    """Morocco's UTC offset on a date: 1 all year, 0 inside the declared Ramadan window."""
    return 0 if is_gmt_window(day) else 1


def duty_switch_dates(status: str = "PRESS_REPORTED") -> list[date]:
    """The soft-wheat duty decree dates at or above the given confidence label."""
    order = {"PRESS_REPORTED": 0, "BO_VERIFIED": 1}
    floor = order.get(status, 0)
    return [d for d, _a, st in DUTY_DECREES if order.get(st, 0) >= floor]


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_plus_declared_table",
    "authority": "the Ministry of Labour's decree fixes the paid national holidays; the Ministry "
                 "of Habous and Islamic Affairs announces the moon sighting the EVENING BEFORE, "
                 "and Morocco often lands one day after Saudi Arabia",
    "rule": "TEN fixed national days -- 1 Jan, 11 Jan (Manifesto of Independence), 14 Jan "
            "(Amazigh New Year, a paid holiday since 2024), 1 May, 30 July (Throne Day), 14 Aug "
            "(Oued Ed-Dahab), 20 Aug (Revolution of the King and the People), 21 Aug (Youth "
            "Day), 6 Nov (Green March) and 18 Nov (Independence Day) -- computed by "
            "`national_holidays(year)`; PLUS four moon-sighted feasts declared in a table "
            "because no rule computes them: Aid al-Fitr (2 days), Aid al-Adha (2 days), Fatih "
            "Muharram (1 day) and Aid al-Mawlid (2 days), each fixed by the sighting the "
            "evening before and carried ANNOUNCED or PROJECTED. NO WEEKEND SUBSTITUTION: a "
            "holiday on a Saturday or Sunday is lost. THE CLOCK ALSO MOVES: Morocco keeps UTC+1 "
            "all year ('heure legale' since 2018-10-28) and returns to UTC+0 from the Sunday "
            "before Ramadan at 03:00 until the Sunday after Aid al-Fitr at 02:00, so for about "
            "five weeks every Moroccan session and publication is one hour LATER in UTC.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "the national calendar on weekdays; the Casablanca session keeps its LOCAL "
                   "hours in Ramadan and therefore moves in UTC",
    "moon_sighting_rule": "DECLARED, not inferred: the ANNOUNCED rows are the announced "
                          "closures, the PROJECTED rows may be one day off, and a Gulf calendar "
                          "is the wrong calendar for Morocco",
    "moving_feasts": "the lunar feasts drift about eleven days earlier each solar year",
    "ramadan_clock_rule": "UTC+0 from the Sunday before Ramadan at 03:00 to the Sunday after "
                          "Aid al-Fitr at 02:00; see RAMADAN_CLOCK and `utc_offset_hours`",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "ANNOUNCED for the fixed days and for Aid al-Fitr and Aid al-Adha; "
                     "PROJECTED for Aid al-Mawlid",
               2025: "ANNOUNCED for the fixed days, Aid al-Fitr and Aid al-Adha; PROJECTED for "
                     "Fatih Muharram and Aid al-Mawlid",
               2026: "ESTIMATE for every moon-sighted row; the fixed days are certain"},
    "known_dates": {
        "2024-01-14": "the first Amazigh New Year observed as a paid national holiday",
        "2024-04-10": "Aid al-Fitr day 1 as announced after the 9 April sighting",
        "2025-03-31": "Aid al-Fitr day 1 (Monday), announced the evening before",
        "2025-06-07": "Aid al-Adha on a Saturday; the sacrifice was called off, the closure "
                      "stood",
        "2026-03-20": "PROJECTED Aid al-Fitr; the announced date can differ by a day",
        "2026-07-30": "Fete du Trone, a fixed solar date and certain in every year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "announced_fn": announced_dates,
    "ramadan_fn": ramadan_clock_window,
    "utc_offset_fn": utc_offset_hours,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "AMMC / Bourse de Casablanca foreign ownership of the market capitalisation",
     "root": "https://www.ammc.ma/fr/espace-publications",
     "fields": ("foreign_share_pct", "strategic_vs_portfolio", "by_sector", "by_investor_type"),
     "frequency": "annual", "snapshot": "31 December", "publish_utc": "12:00", "lag_days": 180,
     "licence": "free, public", "available": True,
     "why": "the only published measure of foreign positioning in Moroccan equities; about "
            "two-thirds of it is STRATEGIC (the European bank and industrial parents) and not "
            "tradeable float, which is the fact that bounds MA-K",
     "pit_warning": "ANNUAL and six months late; it can condition an era, never a week"},
    {"name": "Bank Al-Maghrib banking liquidity position and the 7-day advance allotment",
     "root": "https://www.bkam.ma/Marches/Principaux-indicateurs/Marche-monetaire",
     "fields": ("liquidity_deficit_mad", "advances_7d_allotted", "bid_to_cover",
                "overnight_rate"),
     "frequency": "weekly", "snapshot": "Tuesday tender", "publish_utc": "10:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the operational stance between two quarterly Conseil meetings; a widening deficit "
            "is the bank funding the drought and the cereal import bill",
     "pit_warning": "the allotment is known at the tender; the deficit estimate is revised"},
    {"name": "Office des Changes monthly external indicators (MRE, travel, trade)",
     "root": "https://www.oc.gov.ma/fr/etudes-et-statistiques/indicateurs-mensuels",
     "fields": ("mre_transfers_mad", "travel_receipts_mad", "imports_by_group",
                "cereal_import_bill", "energy_import_bill"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 30, "licence": "free, public", "available": True,
     "why": "the two EUR inflows (remittances, tourism) and the two import bills (energy, "
            "cereals) in one release; the seasonal shape is the object of MA-J",
     "pit_warning": "a month stale; never a same-month conditioner"},
    {"name": "a CFTC or exchange-traded dirham positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no dirham future trades on any exchange the desk can read, and no "
            "COT contract exists for MAD",
     "pit_warning": "DOES NOT EXIST: dirham positioning is UNMEASURED and is never proxied by "
                    "the EUR or USD COT legs, which are positions in the BASKET's components "
                    "and not in the dirham"},
)

# --------------------------------------------------------------------------- terminology
#: FOUR LANGUAGES, AND THE PACK MEANS IT. Modern Standard Arabic is the language of the decrees
#: and the Arabic press (Hespress, Assabah); Darija is the language of the retail ground; FRENCH
#: is the working language of Bank Al-Maghrib, the Bourse, the bank research houses and the
#: entire French-language press, so a French-only query and an Arabic-only query reach DIFFERENT
#: halves of this country; and Tamazight is an official language since the 2011 constitution and
#: the 2024 Amazigh New Year holiday, carried here in Tifinagh with its transliteration.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "MA-A": ("بنك المغرب", "سعر الفائدة", "سعر الفائدة الرئيسي", "مجلس بنك المغرب", "التضخم",
             "السياسة النقدية", "البلاغ الصحفي", "taux directeur", "Conseil de Bank Al-Maghrib",
             "politique monetaire", "communique du Conseil", "Wali de Bank Al-Maghrib",
             "rapport sur la politique monetaire", "policy rate decision"),
    "MA-B": ("الدرهم", "سلة العملات", "سعر الصرف", "نطاق التقلب", "تعويم الدرهم",
             "سعر الصرف المرجعي", "مرونة سعر الصرف", "dirham", "panier de devises",
             "cours de reference", "bande de fluctuation", "regime de change",
             "flexibilite du dirham", "adjudication de devises", "60/40 EUR USD basket"),
    "MA-C": ("السيولة البنكية", "التسبيقات لمدة 7 أيام", "سوق ما بين البنوك", "الخزينة",
             "أذون الخزينة", "المناقصة", "avances a 7 jours", "injection de liquidite",
             "marche monetaire", "bons du Tresor", "adjudication BDT", "taux interbancaire",
             "deficit de liquidite"),
    "MA-D": ("الفوسفاط", "المكتب الشريف للفوسفاط", "الأسمدة", "التصدير", "الجرف الأصفر",
             "phosphate", "OCP", "engrais", "DAP", "TSP", "acide phosphorique", "Jorf Lasfar",
             "phosphate rock reserves", "fertiliser affordability"),
    "MA-E": ("القمح اللين", "القمح الصلب", "الحبوب", "الاستيراد", "المكتب الوطني المهني للحبوب",
             "الدعم", "الشعير", "ble tendre", "ble dur", "cereales", "ONICL", "restitution",
             "prime forfaitaire", "appel d'offres", "minoteries", "orge"),
    "MA-F": ("رسوم الاستيراد", "الرسم الجمركي", "الجريدة الرسمية", "مرسوم", "تعليق الرسوم",
             "droit de douane", "Bulletin Officiel", "decret", "suspension des droits",
             "ADII", "tarif douanier", "campagne de commercialisation"),
    "MA-G": ("الجفاف", "السدود", "نسبة ملء السدود", "التساقطات المطرية", "الموسم الفلاحي",
             "المحصول", "الحقينة", "secheresse", "barrage", "taux de remplissage des barrages",
             "campagne agricole", "pluviometrie", "recolte", "Plan Maroc Vert",
             "Generation Green", "ⴰⵎⴰⵏ (aman: water, Amazigh)", "ⴰⵏⵥⴰⵔ (anzar: rain, Amazigh)",
             "ⴰⴽⴰⵍ (akal: the land, Amazigh)", "ⵉⵔⴷⴻⵏ (irden: wheat, Amazigh)"),
    "MA-H": ("المحروقات", "المصفاة", "سامير", "استيراد الوقود", "الغازوال", "برميل النفط",
             "produits raffines", "Samir", "Mohammedia", "gasoil", "importation de carburant",
             "crack spread", "soutes"),
    "MA-I": ("الغاز الطبيعي", "أنبوب الغاز المغرب أوروبا", "أنبوب الغاز نيجيريا المغرب",
             "الكهرباء", "الطاقة المتجددة", "gazoduc Maghreb Europe", "GME", "ONEE", "ANRE",
             "Xlinks", "Noor Ouarzazate", "interconnexion electrique", "regazeification"),
    "MA-J": ("مغاربة العالم", "تحويلات المغاربة المقيمين بالخارج", "عملية مرحبا", "السياحة",
             "المداخيل السياحية", "العودة", "transferts MRE", "Marocains residant a l'etranger",
             "operation Marhaba", "recettes voyages", "saison estivale", "Royal Air Maroc",
             "ⵉⴷⵔⵉⵎⴻⵏ (idrimen: money, Amazigh)"),
    "MA-K": ("بورصة الدار البيضاء", "مؤشر مازي", "حصة الأجانب", "الاكتتاب", "التداول",
             "Bourse de Casablanca", "MASI", "MSI20", "seuil de variation 10%", "Maroclear",
             "AMMC", "capitalisation boursiere", "detention etrangere", "introduction en bourse"),
    "MA-L": ("رمضان", "الساعة القانونية", "التوقيت الرسمي", "عيد الفطر", "عيد الأضحى",
             "فاتح محرم", "عيد المولد النبوي", "رؤية الهلال", "heure legale", "GMT+1",
             "retour a GMT", "Aid al-Fitr", "Aid al-Adha", "ⵢⴻⵏⵏⴰⵢⴻⵔ (Yennayer: the "
             "Amazigh New Year, 14 January)"),
    "MA-M": ("صندوق المقاصة", "الدعم", "غاز البوطان", "السكر", "الدقيق المدعم", "قانون المالية",
             "Caisse de compensation", "subvention", "butane", "sucre", "farine subventionnee",
             "loi de finances", "COSUMAR", "sucre brut importe"),
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

#: Arabic (with the presentation forms the web serves) and Tifinagh, so a test can assert that
#: this pack did not quietly become a French glossary of an Arabic-speaking country.
_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
                  (0xFE70, 0xFEFF))
_TIFINAGH_RANGES = ((0x2D30, 0x2D7F),)
#: French working vocabulary the pack must carry: Bank Al-Maghrib, the Bourse, the research
#: houses and the whole French-language press run in it, and an Arabic-only crawl misses them.
FRENCH_MARKERS: tuple[str, ...] = (
    "taux directeur", "dirham", "cours de reference", "campagne agricole", "barrage",
    "restitution", "ble tendre", "Bulletin Officiel", "Caisse de compensation",
    "Bourse de Casablanca", "transferts MRE", "operation Marhaba", "panier de devises")


def has_arabic(text: str) -> bool:
    """True when the text contains at least one Arabic codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _ARABIC_RANGES) for ch in str(text))


def has_tifinagh(text: str) -> bool:
    """True when the text contains at least one Tifinagh codepoint (Tamazight)."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _TIFINAGH_RANGES) for ch in str(text))


def arabic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_arabic(t)]


def tifinagh_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_tifinagh(t)]


def french_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared French marker actually present in the terminology table."""
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in FRENCH_MARKERS if any(m in t for t in flat)]


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
    """A layer this country has nothing in, declared BY NAME with the reason (L1.28a)."""
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
        "ma_bkam", "Bank Al-Maghrib: Conseil communiques, cours de reference, money market, "
                   "FX auctions, annual report", layer="official",
        roots=("https://www.bkam.ma/Politique-monetaire", "https://www.bkam.ma/Marches",
               "https://www.bkam.ma/Publications-et-recherche",
               "https://www.bkam.ma/Statistiques"),
        queries=("بلاغ مجلس بنك المغرب", "سعر الفائدة الرئيسي", "سعر الصرف المرجعي",
                 "التسبيقات لمدة 7 أيام", "communique du Conseil", "taux directeur",
                 "cours de reference", "avances a 7 jours", "adjudication de devises",
                 "rapport sur la politique monetaire"),
        languages=("fr", "ar", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (bkam.ma terms)",
        notes="the Conseil communique is dated and timed; the daily cours de reference is the "
              "band's own measuring stick and the Arabic and French releases are posted side by "
              "side, which is the cheapest place to learn this country's own vocabulary"),
    source_class(
        "ma_hcp", "Haut-Commissariat au Plan: IPC, national accounts, conjuncture surveys, "
                  "the agricultural campaign and the census", layer="official",
        roots=("https://www.hcp.ma/Indice-des-prix-a-la-consommation_r93.html",
               "https://www.hcp.ma/Comptes-nationaux_r10.html",
               "https://www.hcp.ma/downloads/"),
        queries=("مؤشر أسعار الاستهلاك", "التضخم", "النمو الاقتصادي", "الموسم الفلاحي",
                 "indice des prix a la consommation", "comptes nationaux", "budget economique",
                 "campagne agricole", "enquete de conjoncture"),
        languages=("fr", "ar"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the budget economique previsionnel published each July carries the HCP's own "
              "cereal-harvest assumption, which is the number the whole fiscal year is built on"),
    source_class(
        "ma_finances_tresor", "Ministere de l'Economie et des Finances and the Direction du "
                              "Tresor: loi de finances, BDT auctions, compensation, debt",
        layer="official",
        roots=("https://www.finances.gov.ma", "https://www.finances.gov.ma/fr/Pages/"
               "adjudications.aspx", "https://depf.finances.gov.ma"),
        queries=("قانون المالية", "صندوق المقاصة", "أذون الخزينة", "المديونية",
                 "loi de finances", "adjudication des bons du Tresor", "caisse de compensation",
                 "note de conjoncture DEPF", "dette du Tresor"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the compensation (subsidy) envelope in the loi de finances is the fiscal cost of "
              "the butane and flour prices; the DEPF note de conjoncture is the state's own "
              "monthly read of the same data the pack mines"),
    source_class(
        "ma_douane_bo", "ADII (customs) and the Secretariat General du Gouvernement: the tariff "
                        "schedule, the circulars and the Bulletin Officiel decrees",
        layer="official",
        roots=("https://www.douane.gov.ma", "http://www.sgg.gov.ma/BulletinOfficiel.aspx"),
        queries=("الرسم الجمركي على القمح اللين", "تعليق رسوم الاستيراد", "الجريدة الرسمية",
                 "مرسوم", "droit de douane ble tendre", "suspension des droits d'importation",
                 "Bulletin Officiel", "circulaire ADII", "tarif douanier"),
        languages=("ar", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE DECREE IS THE EVENT of MA-F; the Bulletin Officiel is the only citable stamp "
              "and the trade press is the only same-day one, which is exactly why the pack's "
              "duty table is labelled PRESS_REPORTED until a BO number is attached to it"),
    source_class(
        "ma_onicl_agri", "ONICL and the Ministry of Agriculture: cereal stocks, collection, "
                         "imports, restitution notices and the campaign bulletins",
        layer="official",
        roots=("http://www.onicl.org.ma", "https://www.agriculture.gov.ma",
               "http://www.onicl.org.ma/portail/situation-du-marche"),
        queries=("المكتب الوطني المهني للحبوب والقطاني", "القمح اللين", "المخزون", "الاستيراد",
                 "ONICL situation du marche", "restitution ble tendre", "prime forfaitaire",
                 "collecte de ble", "importation de cereales", "campagne agricole"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ONICL's monthly situation is a counted physical flow: stocks, arrivals at the "
              "mills and imports by origin, which is the only series that tells a drought from "
              "a price move"),
    source_class(
        "ma_office_changes", "Office des Changes: balance of payments, MRE transfers, travel "
                             "receipts, trade by product group, the FX regulation",
        layer="official",
        roots=("https://www.oc.gov.ma/fr/etudes-et-statistiques/indicateurs-mensuels",
               "https://www.oc.gov.ma/fr/reglementation"),
        queries=("مكتب الصرف", "تحويلات مغاربة العالم", "المداخيل السياحية", "الميزان التجاري",
                 "Office des Changes", "transferts MRE", "recettes voyages",
                 "balance commerciale", "instruction generale des operations de change"),
        languages=("fr", "ar"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the exchange-control regulation itself is the reason Moroccan retail cannot hold "
              "an offshore margin account, and the monthly indicators are the MRE and tourism "
              "series MA-J is built on"),
    source_class(
        "ma_imf", "IMF Morocco country page: Article IV staff reports, the Flexible Credit Line "
                  "and the Resilience and Sustainability Facility reviews", layer="official",
        roots=("https://www.imf.org/en/Countries/MAR",),
        queries=("Morocco Article IV", "Flexible Credit Line Morocco", "Resilience and "
                 "Sustainability Facility", "exchange rate flexibility Morocco",
                 "external sector assessment"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Article IV's exchange-rate annex is the only public document that discusses "
              "the BAND's next widening; the facility is PRECAUTIONARY, so its calendar is a "
              "review clock and never a disbursement clock"),
    # ---- institutional
    source_class(
        "ma_bourse_ammc", "Bourse de Casablanca, AMMC and Maroclear: the bulletin de la cote, "
                          "indices, circuit breakers, IPO prospectuses, foreign ownership",
        layer="institutional",
        roots=("https://www.casablanca-bourse.com", "https://www.ammc.ma",
               "https://www.maroclear.com"),
        queries=("بورصة الدار البيضاء", "مؤشر مازي", "حصة الأجانب", "الاكتتاب",
                 "bulletin de la cote", "MASI", "seuil de variation", "detention etrangere",
                 "note d'information AMMC", "capitalisation boursiere"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the 10% per-security price limit makes a shock a QUEUE rather than a print, so "
              "the index's measured volatility understates the shock -- the reason MA-K is a "
              "mechanics domain and not a return domain"),
    source_class(
        "ma_ocp_soe", "OCP Group, ONEE, ONCF and the other state enterprises: results, bond "
                      "prospectuses, volumes and investment programmes", layer="institutional",
        roots=("https://www.ocpgroup.ma/fr/investors", "http://www.one.org.ma",
               "https://www.ocpgroup.ma/fr/media"),
        queries=("المكتب الشريف للفوسفاط", "الأسمدة", "التصدير", "OCP resultats", "engrais DAP",
                 "capacite de production", "Jorf Lasfar", "ONEE production electrique",
                 "obligation OCP"),
        languages=("fr", "en", "ar"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (issuer disclosure)",
        notes="OCP is a bond issuer and therefore discloses volumes and realised prices; the "
              "GROUP is an actor here and never an instrument -- the two-lane order (2026-09-06) "
              "forbids hunting a single name, and OCP is not listed in any case"),
    source_class(
        "ma_federations", "Trade bodies: CGEM, the millers' federations (FNM/FNBT), COSUMAR and "
                          "the sugar interprofession, FENAGRI, AMITH (textiles), CNT (tourism), "
                          "AMICA (automotive)", layer="institutional",
        roots=("https://www.cgem.ma", "https://www.fnm.ma", "https://www.amith.ma",
               "https://www.fenagri.ma"),
        queries=("الفيدرالية الوطنية للمطاحن", "جمعية المصدرين", "الدقيق المدعم",
                 "federation des minoteries", "interprofession sucriere", "CGEM communique",
                 "exportations textiles", "filiere agroalimentaire"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the millers lobby for the duty suspension and the restitution IN DATED PRESS "
              "RELEASES, which is the cheapest leading indicator of an MA-F decree"),
    source_class(
        "ma_bank_research", "Bank research published openly: Attijari Global Research, BMCE "
                            "Capital Research, CDG Capital Insight, Valoris, Sogecapital",
        layer="institutional",
        roots=("https://www.attijariwafabank.com/fr/attijari-global-research",
               "https://www.bmcecapital.com", "https://www.cdgcapital.ma"),
        queries=("previsions taux directeur", "strategie actions Maroc", "flash marche",
                 "note de recherche", "perspectives macroeconomiques Maroc",
                 "توقعات سعر الفائدة"),
        languages=("fr", "ar"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the pre-Conseil expectation these houses publish is the only stated consensus in "
              "the country; it is kept as the EXPECTATION source MA-A measures a surprise "
              "against, never as a view the desk adopts"),
    # ---- academic
    source_class(
        "ma_academic", "Policy Center for the New South, CNRST/IMIST theses, Universite "
                       "Mohammed V, Al Akhawayn, Cadi Ayyad, ERF working papers",
        layer="academic",
        roots=("https://www.policycenter.ma/publications", "https://www.imist.ma",
               "https://toubkal.imist.ma", "https://erf.org.eg/publications/"),
        queries=("regime de change Maroc", "pass-through taux de change dirham",
                 "transferts des migrants Maroc", "politique monetaire marocaine",
                 "secheresse et croissance Maroc", "phosphate world market power"),
        languages=("fr", "en", "ar"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the exchange-rate-flexibility literature written in Rabat is the mechanism source "
              "for MA-B; every paper is a hypothesis until the desk reproduces it"),
    source_class(
        "ma_agronomy", "INRA Maroc, IAV Hassan II and the agronomic institutes: yield models, "
                       "sowing dates, fertiliser response trials", layer="academic",
        roots=("https://www.inra.org.ma", "https://www.iav.ac.ma"),
        queries=("rendement cereales Maroc", "date de semis", "fertilisation phosphatee",
                 "stress hydrique ble", "الإنتاجية الفلاحية", "التسميد الفوسفاطي"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="the fertiliser-response trials are what make the phosphate-into-planting edge a "
              "mechanism rather than a correlation: they say how much yield a farmer loses by "
              "cutting the phosphate rate, which is the size of the substitution"),
    # ---- practitioner
    source_class(
        "ma_practitioner_fr", "The French-language market desk press: Medias24, Le Boursier, "
                              "Boursenews, EcoActu, Challenge, La Vie eco, Finances News",
        layer="practitioner",
        roots=("https://medias24.com/category/economie/", "https://www.leboursier.ma",
               "https://www.boursenews.ma", "https://www.ecoactu.ma"),
        queries=("taux directeur previsions", "seance de la bourse", "dirham face a l'euro",
                 "importation de ble", "subvention du ble tendre", "resultats OCP",
                 "adjudication du Tresor", "deficit de liquidite bancaire"),
        languages=("fr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Medias24 and Le Boursier carry the dated tender, decree and auction news hours "
              "before the official page updates, and their Conseil previews are the closest "
              "thing this market has to a consensus tape"),
    source_class(
        "ma_practitioner_ar", "The Arabic-language business press and its Darija commentary: "
                              "Hespress economie, Assabah, Al Akhbar, Alyaoum24 business pages",
        layer="practitioner",
        roots=("https://www.hespress.com/economie", "https://assabah.ma",
               "https://alyaoum24.com/category/economy"),
        queries=("سعر الفائدة", "الدرهم", "أسعار المحروقات", "ثمن الدقيق", "استيراد القمح",
                 "غلاء الأسعار", "صندوق المقاصة", "بورصة الدار البيضاء"),
        languages=("ar",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the Arabic press reports the SUBSIDISED prices (flour, butane, sugar) and the "
              "street reaction to them, which the French business press underweights; a "
              "French-only crawl of Morocco reads the half of the country that trades and "
              "misses the half the subsidy regime is written for"),
    # ---- retail ecology
    source_class(
        "ma_retail_forums", "Moroccan retail communities: r/Morocco, Facebook bourse groups, "
                            "YouTube and TikTok Darija market channels, Wafabourse user threads",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/Morocco/",
               "https://www.youtube.com/results?search_query=bourse+casablanca+darija",
               "https://www.facebook.com/groups/boursedecasablanca"),
        queries=("بورصة الدار البيضاء نصائح", "شنو نشري", "الاستثمار في البورصة",
                 "comment investir en bourse Maroc", "dirham euro marche noir",
                 "acheter de l'or au Maroc"),
        languages=("ar", "fr"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT and never a source of edge: single-name tips belong to the "
              "event lane, but the retail vocabulary around the cash-dirham premium and the "
              "gold counters dates the exchange-control stress episodes MA-B studies"),
    source_class(
        "ma_forex_sellers", "Darija and French 'forex' signal sellers and prop-firm affiliates "
                            "targeting Moroccan retail on Telegram, YouTube and TikTok",
        layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=forex+maroc+darija",
               "https://t.me/s/forexmaroc"),
        queries=("فوركس المغرب", "تداول الذهب", "prop firm maroc", "trading darija",
                 "signaux forex gratuits", "compte demo"),
        languages=("ar", "fr"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="ILLEGAL UNDER EXCHANGE CONTROL and advertised anyway: the Office des Changes "
              "forbids a resident from funding an offshore margin account, so this ground "
              "measures an unlicensed retail base rather than a regulated flow; kept because "
              "the XAUUSD stop clusters it advertises are a real microstructure observable"),
    # ---- app ecosystem
    source_class(
        "ma_payment_rails", "The payment and transfer rails: CMI card statistics, Bank "
                            "Al-Maghrib's payment-infrastructure report, the mobile wallets, "
                            "Wafacash / Cash Plus / Barid Cash and the MRE bank apps",
        layer="app_ecosystem",
        roots=("https://www.cmi.co.ma", "https://www.bkam.ma/Systemes-et-moyens-de-paiement",
               "https://www.wafacash.com", "https://www.cashplus.ma"),
        queries=("الأداء الإلكتروني", "تحويل الأموال", "المحفظة الإلكترونية",
                 "statistiques monetique CMI", "paiement mobile", "transfert d'argent MRE",
                 "wallet M-Wallet", "retrait par carte etrangere"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free statistics; app stores public",
        notes="CMI publishes FOREIGN-CARD activity in Morocco monthly, which is a near-real-time "
              "tourism proxy that leads the Office des Changes travel receipts by about six "
              "weeks -- the one app-layer series in this pack with a real lead"),
    source_class(
        "ma_p2p_commentary", "Press and regulator commentary on the parallel cash dirham and the "
                             "USDT-MAD peer-to-peer premium as a capital-control observable",
        layer="app_ecosystem",
        roots=("https://medias24.com/?s=crypto", "https://www.bkam.ma/Communiques"),
        queries=("العملات المشفرة", "سوق الصرف الموازي", "marche noir du dirham",
                 "prime sur l'euro cash", "crypto interdit Maroc", "projet de loi crypto"),
        languages=("fr", "ar"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="PUBLIC COMMENTARY ONLY: no venue feed, no order book, no exchange named as a "
              "source (mandate 2026-08-18). The premium is a dirham stress observable reported "
              "in the press and carried at low weight beside the bureaux-de-change spread"),
    # ---- media
    source_class(
        "ma_wire_broadcast", "MAP (the state wire), 2M and SNRT economie, Le Matin, "
                             "L'Economiste, Aujourd'hui le Maroc, TelQuel, Hespress",
        layer="media",
        roots=("https://www.mapnews.ma", "https://lematin.ma/economie",
               "https://www.leconomiste.com", "https://telquel.ma", "https://www.hespress.com"),
        queries=("بنك المغرب يقرر", "أسعار المحروقات اليوم", "المسيرة الخضراء",
                 "Bank Al-Maghrib maintient", "le dirham s'apprecie", "prix a la pompe",
                 "communique du ministere", "sechersse au Maroc"),
        languages=("fr", "ar"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="MAP carries the official minute of a Conseil or a decree when the institution's "
              "own page carries only the date; TelQuel is the one outlet that reports the "
              "politics of the subsidy and the clock change rather than only the number"),
    source_class(
        "ma_licensed_assessments", "Licensed terminals and price reporting agencies: Bloomberg, "
                                   "Refinitiv, and CRU / Argus / Profercy / DTN for phosphate "
                                   "rock, DAP, TSP and ammonia", layer="media",
        roots=("https://www.crugroup.com", "https://www.argusmedia.com"),
        queries=("DAP Morocco fob assessment", "phosphate rock contract price",
                 "TSP Brazil cfr", "ammonia Tampa settlement"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED: the DAP and rock assessments are the actual phosphate "
              "price and they are paywalled, so MA-D is measured on the CROPS the fertiliser "
              "cost reaches and on OCP's own disclosed realisations -- the absence is named "
              "rather than worked around"),
    # ---- archive
    source_class(
        "ma_archive_official", "The Bulletin Officiel full run, Bank Al-Maghrib annual reports, "
                               "HCP statistical yearbooks, Office des Changes historical balance "
                               "of payments", layer="archive",
        roots=("http://www.sgg.gov.ma/BulletinOfficiel.aspx",
               "https://www.bkam.ma/Publications-et-recherche/Publications-institutionnelles",
               "https://www.hcp.ma/Annuaire-statistique-du-Maroc_r90.html"),
        queries=("الجريدة الرسمية أرشيف", "التقرير السنوي لبنك المغرب", "Bulletin Officiel "
                 "archives", "rapport annuel Bank Al-Maghrib", "annuaire statistique du Maroc",
                 "historique balance des paiements"),
        languages=("ar", "fr"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Bulletin Officiel is where a duty decree becomes citable; the BAM annual "
              "report carries the reconstructed basket weights and the band history, which is "
              "the only way to date the 2015 reweighting and the two widenings from a document"),
    source_class(
        "ma_wayback", "web.archive.org snapshots of the ONICL market pages, the bkam.ma daily "
                      "reference-rate table and the ministries' pages that overwrite in place",
        layer="archive",
        roots=("https://web.archive.org/web/*/onicl.org.ma*",
               "https://web.archive.org/web/*/bkam.ma*"),
        queries=("onicl situation du marche archive", "bkam cours de reference archive",
                 "taux de remplissage des barrages archive"),
        languages=("fr", "ar", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE MOROCCAN OFFICIAL WEB OVERWRITES IN PLACE: the barrage fill page and the "
              "ONICL situation page show TODAY and keep no history, so the only point-in-time "
              "vintage of either is the crawl somebody took; without this layer MA-G is "
              "reconstructible only from press quotes"),
    # ---- physical economy
    source_class(
        "ma_ports", "Agence Nationale des Ports traffic, Tanger Med, Jorf Lasfar, Casablanca, "
                    "Safi and Nador West Med, plus the public port-call and AIS ground",
        layer="physical_economy",
        roots=("https://www.anp.org.ma", "https://www.tangermed.ma",
               "https://www.marsamaroc.co.ma"),
        queries=("حركة الموانئ", "ميناء الجرف الأصفر", "trafic portuaire", "Jorf Lasfar "
                 "phosphate", "Tanger Med volumes", "escale navire cereales", "debarquement "
                 "de ble"),
        languages=("fr", "ar", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Jorf Lasfar is the phosphate export gate and the grain discharge port at once, so "
              "its call list is the physical counterpart of both MA-D and MA-E; ANP publishes "
              "tonnage by product quarterly and the port-call ground is what fills the gaps"),
    source_class(
        "ma_water_energy", "The barrage fill rate, the Direction de la Meteorologie Nationale, "
                           "ONEE electricity, ANRE and the pipeline/interconnector projects",
        layer="physical_economy",
        roots=("https://www.equipement.gov.ma", "https://www.marocmeteo.ma",
               "http://www.one.org.ma", "https://www.anre.ma"),
        queries=("نسبة ملء السدود", "التساقطات المطرية", "الجفاف", "taux de remplissage des "
                 "barrages", "bulletin meteorologique", "production electrique ONEE",
                 "gazoduc Nigeria Maroc", "interconnexion Maroc Espagne"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the national fill percentage is published as ONE number that the whole country "
              "quotes, and it is the earliest public read on the cereal campaign -- months "
              "before the HCP's harvest estimate and a year before the trade account shows it"),
    source_class(
        "ma_usda_fao_igc", "USDA FAS GAIN reports, FAO GIEWS and the IGC for Moroccan grain, "
                           "feed, sugar and oilseeds", layer="physical_economy",
        roots=("https://fas.usda.gov/data/search?f%5B0%5D=country%3A%22Morocco%22",
               "https://www.fao.org/giews/countrybrief/country.jsp?code=MAR",
               "https://www.igc.int"),
        queries=("Morocco grain and feed annual", "Morocco sugar annual", "GIEWS Morocco",
                 "Morocco wheat import forecast", "Morocco barley import"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work)",
        notes="the import forecasts the grain market actually reads for Morocco, dated and "
              "revisable; the GAIN report is also where the duty and restitution regime is "
              "described in English with its effective dates"),
    # ---- source graph
    source_class(
        "ma_source_graph", "Who cites whom: Bank Al-Maghrib -> the research houses -> Medias24 "
                           "and Le Boursier -> the retail groups; the SGG decree -> the ADII "
                           "circular -> the millers' release; OCP -> the PRA assessment -> the "
                           "wires", layer="source_graph",
        roots=("https://www.bkam.ma/Communiques", "https://medias24.com",
               "https://www.hespress.com/economie"),
        queries=("selon des sources", "حسب مصادر", "selon Bank Al-Maghrib", "d'apres le "
                 "Bulletin Officiel", "نقلا عن", "citant le ministere",
                 "selon les professionnels du secteur"),
        languages=("fr", "ar"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'selon des sources' and 'حسب مصادر' mark the unattributed leak that precedes a "
              "decree by a day or two in this country; the graph is how a leak is told from a "
              "repost, and it is the only way to date an MA-F decree before the BO prints it"),
)

LAYER_ABSENCES: dict[str, str] = {}


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
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Bank Al-Maghrib taux directeur decisions and Conseil communiques", "source": "BAM",
     "coverage": "1995 onward (quarterly Conseil format from 2006)", "frequency": "4 per year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2006-03", "pit_feasible": True,
     "assets": ("EURUSD", "XAUUSD", "E35"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "bkam.ma politique monetaire: the communique and the quarterly monetary "
                     "policy report; the announcement minute is stamped from MAP when the "
                     "communique carries only a date"},
    {"name": "Cours de reference: the daily official dirham fixing against EUR and USD",
     "source": "Bank Al-Maghrib", "coverage": "1996 onward, daily",
     "frequency": "daily (business days)", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "1996-01",
     "pit_feasible": True, "assets": ("EURUSD", "USDX"),
     "mechanism_families": ("fixing", "band_state"),
     "how_to_fetch": "bkam.ma marches/cours-de-change; the page OVERWRITES IN PLACE, so the "
                     "only vintage is a daily crawl or the Wayback snapshot"},
    {"name": "The band and the basket: weights, bounds and the widening decrees",
     "source": "BAM annual reports, the Ministry of Finance decrees, IMF Article IV annexes",
     "coverage": "2015-04 reweighting to 60/40; 2018-01 and 2020-03 widenings",
     "frequency": "irregular, dated", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2015-04", "pit_feasible": True,
     "assets": ("EURUSD", "USDX", "EURTRY"),
     "mechanism_families": ("regime_break", "administered_price"),
     "how_to_fetch": "the decree in the Bulletin Officiel plus the BAM annual report's exchange "
                     "chapter; the band BOUNDS are derived from the basket and are not published "
                     "as a series, which is why the distance-to-edge state must be computed"},
    {"name": "Weekly 7-day advance tender and the banking liquidity deficit", "source": "BAM",
     "coverage": "2009 onward", "frequency": "weekly", "publication_lag_days": 0.0,
     "revisions": "the deficit forecast is revised; the allotment is not",
     "licence": "free, public", "history_from": "2009-01", "pit_feasible": True,
     "assets": ("EURUSD",), "mechanism_families": ("liquidity", "calendar_settlement"),
     "how_to_fetch": "bkam.ma marche monetaire; the Tuesday announcement and Wednesday value"},
    {"name": "Office des Changes monthly external indicators (MRE, travel, trade by group)",
     "source": "Office des Changes", "coverage": "1998 onward", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "minor, next month", "licence": "free, public",
     "history_from": "1998-01", "pit_feasible": True, "assets": ("EURUSD", "XAUUSD"),
     "mechanism_families": ("seasonal_flow", "external_balance"),
     "how_to_fetch": "oc.gov.ma indicateurs mensuels; the MRE and travel lines are the summer "
                     "seasonal of MA-J and the energy and cereal lines are the import bill"},
    {"name": "HCP consumer price index and the budget economique previsionnel", "source": "HCP",
     "coverage": "CPI 2006 base onward; the budget economique each July and January",
     "frequency": "monthly / semi-annual", "publication_lag_days": 20.0,
     "revisions": "rebasing only", "licence": "free, public", "history_from": "2006-01",
     "pit_feasible": True, "assets": ("WHEAT", "SUGAR", "XBRUSD"),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "hcp.ma; the July budget economique carries the HCP's cereal-harvest "
                     "assumption, which is the fiscal year's single largest swing factor"},
    {"name": "ONICL cereal situation: stocks, collection, imports by origin, restitution",
     "source": "ONICL", "coverage": "2005 onward", "frequency": "monthly",
     "publication_lag_days": 15.0, "revisions": "cumulative; rarely restated",
     "licence": "free, public", "history_from": "2005-09", "pit_feasible": False,
     "assets": ("WHEAT", "CORN"), "mechanism_families": ("supply_count", "import_demand"),
     "how_to_fetch": "onicl.org.ma situation du marche; PIT IS PARTIAL because the page is "
                     "overwritten in place -- a cell compiled on an un-archived month is "
                     "UNMEASURED rather than assumed"},
    {"name": "Soft-wheat customs duty and restitution decrees (Bulletin Officiel)",
     "source": "SGG / ADII / the Ministry of Agriculture", "coverage": "2008 onward",
     "frequency": "irregular, dated", "publication_lag_days": 3.0, "revisions": "never",
     "licence": "free, public", "history_from": "2008-01", "pit_feasible": True,
     "assets": ("WHEAT", "CORN"),
     "mechanism_families": ("administered_price", "trade_decision"),
     "how_to_fetch": "sgg.gov.ma Bulletin Officiel search plus the ADII circular; the pack's own "
                     "DUTY_DECREES table is PRESS_REPORTED until a BO number is attached"},
    {"name": "National barrage fill rate and the DMN rainfall bulletins",
     "source": "Ministere de l'Equipement et de l'Eau / DMN", "coverage": "2000 onward",
     "frequency": "weekly (fill) and daily (rainfall)", "publication_lag_days": 1.0,
     "revisions": "never", "licence": "free, public", "history_from": "2000-09",
     "pit_feasible": False, "assets": ("WHEAT", "CORN", "SUGAR"),
     "mechanism_families": ("weather", "supply_count"),
     "how_to_fetch": "equipement.gov.ma situation des barrages; OVERWRITTEN IN PLACE, so the "
                     "history is a crawl or the Wayback snapshots -- the archive layer exists "
                     "for exactly this series"},
    {"name": "OCP volumes, realised prices and the public fertiliser assessments",
     "source": "OCP Group disclosure; CRU / Argus for the price", "coverage": "2016 onward",
     "frequency": "quarterly (issuer) / weekly (assessment)", "publication_lag_days": 45.0,
     "revisions": "never", "licence": "issuer disclosure free; assessments LICENSED",
     "history_from": "2016-03", "pit_feasible": False,
     "assets": ("CORN", "WHEAT", "SOYBEAN"),
     "mechanism_families": ("input_cost", "terms_of_trade"),
     "how_to_fetch": "ocpgroup.ma investors for volumes and realisations; the ASSESSMENT is "
                     "paywalled and machine_use_allowed=false, so the price leg is UNMEASURED "
                     "and the crops are what the pack actually tests"},
    {"name": "Bourse de Casablanca: MASI, volumes, and the AMMC foreign-ownership report",
     "source": "Bourse de Casablanca / AMMC", "coverage": "2002 onward (index), 2010 onward "
                                                          "(ownership)",
     "frequency": "daily / annual", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2002-01", "pit_feasible": True,
     "assets": ("E35", "FRA40"), "mechanism_families": ("equity_mechanics", "positioning"),
     "how_to_fetch": "casablanca-bourse.com bulletin de la cote; no MASI CFD exists, so the "
                     "index is a conditioner and the European parents carry the executable leg"},
    {"name": "Refined-product imports, the butane subsidy and the pump price",
     "source": "Ministere de la Transition Energetique / ANRE / Caisse de compensation",
     "coverage": "2015 onward (post-Samir)", "frequency": "monthly",
     "publication_lag_days": 40.0, "revisions": "minor", "licence": "free, public",
     "history_from": "2015-09", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("import_demand", "administered_price"),
     "how_to_fetch": "the ministry's monthly energy bulletin plus the Office des Changes energy "
                     "import line; the butane price is ADMINISTERED and its subsidy cost is in "
                     "the loi de finances"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The Conseil de Bank Al-Maghrib",
     "holds": "the taux directeur, the weekly 7-day advance that funds a structural banking "
              "liquidity deficit of roughly MAD 100-150bn, and about US$35-38bn of reserves",
     "forced_to": ("decide at four scheduled meetings a year -- March, June, September and "
                   "December -- and publish the communique the same afternoon",
                   "publish a cours de reference every business day",
                   "defend the band it is given, by auction, at either edge"),
     "when": "mid-afternoon Africa/Casablanca on the meeting day (about 15:00 UTC; one hour "
             "later in UTC if the meeting falls inside the Ramadan clock window)",
     "information": ("the banking system's liquidity position in real time",
                     "the reserve and FX-auction book", "the Treasury's issuance plan",
                     "the harvest estimate before the HCP publishes it"),
     "constraints": ("an exchange-rate regime the GOVERNMENT sets, not the bank",
                     "no announced numeric inflation target, so a surprise has no published "
                     "benchmark to be measured against",
                     "a structural liquidity deficit that must be refinanced weekly",
                     "the compensation bill and the cereal import bill as fiscal facts"),
     "instruments": ("EURUSD", "XAUUSD", "E35"),
     "counterparties": ("the commercial banks at the 7-day tender", "the Direction du Tresor",
                        "the IMF under the precautionary facility",
                        "the importers who buy dollars at the auction"),
     "observables": ("the communique and the press conference",
                     "the weekly allotment and the bid-to-cover",
                     "the daily cours de reference and its distance to the band edge",
                     "the monetary statistics"),
     "impact": "a decision moves the Treasury-bill curve immediately; the dirham itself cannot "
               "move more than the band allows, so the executable effect is on the EUR/USD leg "
               "of the basket and on the European indices that hold the bank parents",
     "persistence": "the level effect lasts a full quarter by construction -- there is no "
                    "intermeeting decision except in an emergency",
     "falsifier": "the same window on the four nearest non-meeting Tuesdays; an effect that "
                  "survives there is a weekday effect wearing the Conseil's hat, and a "
                  "decision-day move on EURUSD that matches an ECB day is a euro event",
     "notes": "FOUR decisions a year is a third of a normal central bank's sample, which is the "
              "binding constraint on MA-A and is stated rather than worked around"},
    {"name": "The Bank Al-Maghrib FX desk as the band's counterparty",
     "holds": "the reference rate, the auction, and the reserves that back the band",
     "forced_to": ("publish a reference rate derived from the 60/40 basket every business day",
                   "stand at the edge: sell dollars at the weak edge and buy at the strong one",
                   "widen the band only when the government decrees it"),
     "when": "the reference rate around 12:30 local; auctions intraday when the rate approaches "
             "an edge",
     "information": ("the banks' end-of-day FX positions",
                     "the importers' forward book under exchange control",
                     "the MRE and tourism inflow before the Office des Changes publishes it"),
     "constraints": ("the band's arithmetic: +/-5.0% since 2020-03-09",
                     "the Office des Changes rules that keep residents out of the market",
                     "a reserve cover measured in months of imports"),
     "instruments": ("EURUSD", "USDX"),
     "counterparties": ("the commercial banks", "the importers and exporters",
                        "the bureaux de change at the cash margin"),
     "observables": ("the daily reference rate and its distance to each edge",
                     "the auction announcements", "the reserve series",
                     "the bureaux-de-change spread"),
     "impact": "the dirham's own move is bounded; the INFORMATION is in where inside the band it "
               "sits and in whether the bank had to act, which conditions the euro leg",
     "persistence": "the band regime persists for years -- three regimes since 2015",
     "falsifier": "the distance-to-edge state carries no information about the next month's "
                  "EURUSD path beyond what the euro-dollar tape already carries, measured with "
                  "the same state built on a SHUFFLED reference-rate series",
     "notes": "the state variable of MA-B; it is computed from the basket, never published"},
    {"name": "The Direction du Tresor and the Ministry of Finance",
     "holds": "the domestic BDT programme, the eurobond programme and the compensation envelope",
     "forced_to": ("auction Treasury bills on a published Tuesday calendar",
                   "fund the subsidy bill whatever the butane and wheat price does",
                   "set the exchange-rate regime, including any further band widening"),
     "when": "weekly auctions; the loi de finances in October-December; eurobonds opportunistic",
     "information": ("the cash position and the subsidy accrual",
                     "the government's intention on the band, before the market"),
     "constraints": ("a deficit target agreed with the IMF under the precautionary facility",
                     "the political impossibility of letting the flour and butane price move",
                     "the drought's cost to revenue and to the wage bill"),
     "instruments": ("EURUSD", "XAUUSD", "EURTRY"),
     "counterparties": ("the domestic banks and insurers at the BDT auction",
                        "the international bond market", "the IMF"),
     "observables": ("the auction results and the cut-off yields",
                     "the loi de finances compensation line", "the eurobond announcements"),
     "impact": "the domestic curve is set here; a eurobond is a dated reserve step and a "
               "sovereign-spread event the frontier complex trades",
     "persistence": "one fiscal year for the envelope; one auction for the curve",
     "falsifier": "eurobond and auction windows carry no abnormal move on the euro cross or the "
                  "frontier-stress legs against the matched weekday control",
     "notes": "the band is the GOVERNMENT's instrument, which is why this actor and not the "
              "central bank is the one to watch for the next widening"},
    {"name": "OCP Group as the world's phosphate swing supplier",
     "holds": "about 70% of world phosphate rock reserves and a third of world traded rock and "
              "phosphoric acid capacity, with the Jorf Lasfar and Safi complexes",
     "forced_to": ("clear its production into an export market every quarter",
                   "price DAP and TSP against the farmer's affordability, not only its own cost",
                   "supply India and Brazil on annual and spot terms and publish as a bond "
                   "issuer"),
     "when": "quarterly disclosure; the fertiliser season runs into the northern spring planting "
             "and the Brazilian safrinha",
     "information": ("its own order book and the affordability of the next season",
                     "the Indian subsidy decision before the market reads it",
                     "vessel line-ups at Jorf Lasfar"),
     "constraints": ("the rock is a fixed asset and the plants run at capacity",
                     "Chinese export policy, which is the other swing supplier",
                     "the ammonia and sulphur input cost"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "counterparties": ("Indian and Brazilian importers", "the world's farmers",
                        "the ammonia and sulphur sellers"),
     "observables": ("the quarterly volumes and realised prices",
                     "the licensed DAP and rock assessments (which the desk may not scrape)",
                     "Jorf Lasfar sailings"),
     "impact": "an unaffordable phosphate price cuts applied rates and acreage, which is a "
               "SUPPLY effect on next season's corn and wheat -- the direction is INPUT into "
               "the planting decision, not a Moroccan push on Chicago, and the pack says so",
     "persistence": "one fertiliser season; the 2021-22 affordability shock is the reference",
     "falsifier": "seasons in which the DAP-to-corn price ratio moved sharply show no change in "
                  "USDA's applied-rate or acreage estimates, or the same move appears in years "
                  "when the ratio did not move",
     "notes": "the strongest structural edge in the pack and the one whose price leg is behind "
              "a paywall; the crops are therefore what is measured"},
    {"name": "ONICL as the cereal import authority",
     "holds": "the import regime, the restitution and the state's view of the stock position",
     "forced_to": ("keep the mills supplied through a failed harvest",
                   "publish the monthly situation of stocks, collection and imports",
                   "open a restitution when the world price makes the subsidised flour price "
                   "impossible"),
     "when": "the marketing year turns at the May-June harvest; the import season runs "
             "October-April",
     "information": ("the true stock position and the mills' order book",
                     "the harvest estimate before it is public"),
     "constraints": ("the fixed subsidised price of the national flour",
                     "the fiscal cost of the restitution",
                     "the domestic harvest, which it does not control"),
     "instruments": ("WHEAT", "CORN"),
     "counterparties": ("the millers' federations", "the French and Black Sea exporters",
                        "the Treasury that pays the restitution"),
     "observables": ("the monthly situation", "the restitution notices",
                     "the import arrivals by origin at Casablanca and Jorf Lasfar"),
     "impact": "a 5-7 mt soft-wheat import programme is a real share of French and Black Sea "
               "exportable surplus, and the tenders are read as Mediterranean demand",
     "persistence": "one marketing year",
     "falsifier": "import-season months with a restitution open show no abnormal WHEAT move "
                  "against the matched control, or the same move appears in months with none",
     "notes": "France is the marginal origin, which is why the wheat channel and the euro "
              "channel are correlated and must be controlled for each other"},
    {"name": "The customs administration (ADII) and the soft-wheat duty decree",
     "holds": "the tariff schedule and the power to suspend it",
     "forced_to": ("raise the duty to protect the domestic harvest at the marketing-year turn",
                   "suspend it when the crop fails and the mills must import",
                   "publish every change in the Bulletin Officiel"),
     "when": "the restoration clusters into May-June and the suspension into October-November; "
             "the decree is published within days of the decision",
     "information": ("the harvest estimate and the stock position before the market",
                     "the millers' lobbying position"),
     "constraints": ("the subsidised flour price the duty is supposed to protect",
                     "the farm lobby at harvest and the miller lobby in the import season",
                     "the free-trade agreements that already zero some origins"),
     "instruments": ("WHEAT", "CORN"),
     "counterparties": ("the importers and millers", "the farmers", "the exporting origins"),
     "observables": ("the Bulletin Officiel decree", "the ADII circular",
                     "the trade press report a day or two EARLIER"),
     "impact": "a suspension opens a 5-7 mt import window and a restoration closes it; the "
               "decision is administered, dated and therefore mineable",
     "persistence": "one half of a marketing year",
     "falsifier": "the decree windows on WHEAT match the same boundary days in years when no "
                  "decree landed, which is the pack's own out-of-season placebo",
     "notes": "the pack's decree dates are PRESS_REPORTED and must carry a BO number before any "
              "cell compiled on them is promoted -- the honesty is the whole point"},
    {"name": "The millers' federations and the subsidised flour circuit",
     "holds": "the milling capacity and the quota of subsidised national flour",
     "forced_to": ("buy imported soft wheat when the domestic crop fails",
                   "sell the national flour at an administered price whatever the wheat cost",
                   "lobby for the restitution and the duty suspension in dated press releases"),
     "when": "purchasing follows the import season; the lobbying precedes the decree",
     "information": ("their own stock cover in weeks", "the freight and origin spreads"),
     "constraints": ("the fixed flour price", "the quota", "the wheat quality the mills need"),
     "instruments": ("WHEAT",),
     "counterparties": ("ONICL and the Treasury", "the French and Black Sea exporters",
                        "the bakeries"),
     "observables": ("the federations' press releases", "the import arrivals",
                     "the flour price at the shop, which does not move"),
     "impact": "the millers are the transmission from a world wheat price to a Moroccan fiscal "
               "cost; the price the consumer sees is fixed, so the whole shock lands on the "
               "budget, which is why the import decision is political",
     "persistence": "one import season",
     "falsifier": "a federation release calling for a suspension is NOT followed by a decree "
                  "within a quarter in most instances, which would refute the lobbying lead",
     "notes": "an actor, never an instrument: the listed millers are event-lane names"},
    {"name": "COSUMAR and the subsidised sugar circuit",
     "holds": "effectively the whole national sugar refining and beet/cane collection",
     "forced_to": ("import raw sugar to cover the roughly half of consumption the domestic beet "
                   "and cane crop cannot supply",
                   "sell at the administered subsidised price",
                   "run the refinery through the drought years when the beet crop fails"),
     "when": "raw purchases follow the crop year; the subsidy is set in the loi de finances",
     "information": ("the beet and cane harvest before the market",
                     "its own raw purchase programme"),
     "constraints": ("the administered retail price", "the irrigation water the beet needs",
                     "the raw sugar world price it cannot pass on"),
     "instruments": ("SUGARRAW", "SUGAR"),
     "counterparties": ("the raw sugar exporters", "the Caisse de compensation",
                        "the beet growers"),
     "observables": ("the import volumes in the Office des Changes trade lines",
                     "the compensation line for sugar", "the beet area planted"),
     "impact": "Morocco is a structural raw-sugar importer of roughly 1 mt a year, which is a "
               "real share of the refining demand the raws market prices",
     "persistence": "one crop year",
     "falsifier": "a drought year with a collapsed beet crop shows no rise in the raw import "
                  "line or in the world raws demand attributed to North Africa",
     "notes": "the two-lane order again: the refiner is an actor, the sugar contracts are the "
              "instruments"},
    {"name": "Moroccans residing abroad (MRE) as remittance senders",
     "holds": "about US$11-12bn a year of transfers, overwhelmingly EUR-denominated, plus the "
              "property and deposit stock they hold at home",
     "forced_to": ("send ahead of Aid al-Adha and the summer return",
                   "convert euro to dirham at the reference rate through the banks and the "
                   "transfer agents", "travel home in the Marhaba window"),
     "when": "the summer (July-August) carries the peak, with a second peak at Aid al-Adha",
     "information": ("the European labour market they live in",
                     "the rate the agents post against the bank rate"),
     "constraints": ("the European economy, principally France, Spain, Italy, Belgium and the "
                     "Netherlands", "the transfer fee and the agent network",
                     "the exchange-control rules on their own accounts"),
     "instruments": ("EURUSD", "XAUUSD"),
     "counterparties": ("the banks and the transfer agents", "the families receiving",
                        "the property market the flow reaches"),
     "observables": ("the monthly Office des Changes MRE line",
                     "the Marhaba crossing counts at Tanger Med and Algeciras",
                     "the foreign-card activity CMI publishes"),
     "impact": "the largest single FX inflow and the most seasonal; it is what keeps the "
               "reference rate off the weak edge in the summer",
     "persistence": "seasonal, every year, with the solar summer and the lunar Aid",
     "falsifier": "the summer months show no systematic position of the reference rate inside "
                  "the band relative to the rest of the year once the trade balance is "
                  "controlled, which would refute the seasonal-flow mechanism",
     "notes": "the lunar Aid and the solar summer are DIFFERENT clocks and must not be pooled"},
    {"name": "The tourism industry and the Marhaba operation",
     "holds": "about 14-17m arrivals and roughly US$9-11bn of travel receipts a year",
     "forced_to": ("run the Marhaba crossing operation every summer for the MRE returning by "
                   "car through Tanger Med and Algeciras",
                   "sell in euro and be paid in euro", "absorb the European booking cycle"),
     "when": "June to September, with the Marhaba window from early June to mid-September",
     "information": ("the forward booking curve", "the airline seat capacity"),
     "constraints": ("European consumer demand and the airline capacity",
                     "the ferry capacity at the Strait", "the World Cup 2030 build-out"),
     "instruments": ("EURUSD", "E35", "FRA40"),
     "counterparties": ("European tour operators and airlines", "Royal Air Maroc",
                        "the Spanish ports on the other side of the Strait"),
     "observables": ("the CMI foreign-card series (about six weeks ahead of the official data)",
                     "arrivals and receipts at the Observatoire du Tourisme",
                     "the Marhaba crossing counts"),
     "impact": "the second EUR inflow and the one that moves first when Europe slows; it is the "
               "channel through which a European recession reaches the dirham's band position",
     "persistence": "seasonal with a European business-cycle beta",
     "falsifier": "the CMI foreign-card series carries no lead on the Office des Changes travel "
                  "receipts once the calendar month is controlled, which would remove the only "
                  "fast tourism observable this pack has",
     "notes": "the one app-layer series in the pack with a genuine publication lead"},
    {"name": "The water authorities and the barrage system",
     "holds": "the dam storage, the irrigation allocations and the drinking-water priority",
     "forced_to": ("publish the national fill rate",
                   "cut irrigation to the large perimeters when the fill falls, which decides "
                   "the beet, citrus and cereal area",
                   "build desalination and inter-basin transfers on a decade clock"),
     "when": "the fill rises with the November-March rains and is spent through the summer",
     "information": ("the basin-by-basin storage and the snowpack",
                     "the allocation decisions before the farmers hear them"),
     "constraints": ("the rainfall, which nobody controls",
                     "the drinking-water priority over irrigation",
                     "six consecutive drought years to 2024 as the starting state"),
     "instruments": ("WHEAT", "CORN", "SUGARRAW"),
     "counterparties": ("the irrigated perimeters and their growers", "the cities",
                        "the beet and cane growers COSUMAR depends on"),
     "observables": ("the weekly national fill percentage", "the DMN rainfall bulletins",
                     "the irrigation allocation announcements"),
     "impact": "the fill rate at the end of March decides the cereal harvest and therefore the "
               "import programme, the duty decree and about two points of GDP",
     "persistence": "one campaign, but storage carries a multi-year memory",
     "falsifier": "the end-March fill rate carries no information about the eventual harvest or "
                  "the import volume once the rainfall total is controlled, which would make "
                  "the series decorative rather than leading",
     "notes": "the publication is OVERWRITTEN IN PLACE, so without the archive layer this "
              "mechanism has no point-in-time history at all"},
    {"name": "The Bourse de Casablanca, the AMMC and the domestic institutions",
     "holds": "the listed market, the 10% per-security price limit, and the captive domestic "
              "institutional base (CIMR, CDG, the insurers, the OPCVM)",
     "forced_to": ("halt a security that moves 10% in a session",
                   "settle T+2 through Maroclear",
                   "absorb an IPO or a state privatisation with domestic savings, because the "
                   "foreign float is small"),
     "when": "09:30-15:30 local, which is 08:30-14:30 UTC outside Ramadan and 09:30-15:30 UTC "
             "inside it",
     "information": ("the order book and the queue behind a limit",
                     "the institutions' mandated allocations"),
     "constraints": ("the price limit, which turns a shock into a queue",
                     "the exchange-control rules that keep foreign portfolio money small",
                     "a concentrated index dominated by banks and telecoms"),
     "instruments": ("E35", "FRA40"),
     "counterparties": ("the European bank and industrial parents of the listed names",
                        "the domestic pension and insurance funds"),
     "observables": ("the bulletin de la cote", "the number of securities at the limit",
                     "the AMMC annual foreign-ownership share"),
     "impact": "the index's measured volatility UNDERSTATES a shock because the limit defers it; "
               "the executable leg is the European parents' indices, not the MASI",
     "persistence": "the market-design facts are decade-scale",
     "falsifier": "days with many securities at the 10% limit show no abnormal next-day move on "
                  "the European index legs against the matched control -- the expected result, "
                  "which the pack records rather than hides",
     "notes": "a mechanics domain: the object is the queue, not the return"},
    {"name": "The Ministry of Habous and the clock: the moon sighting and the Ramadan GMT decree",
     "holds": "the announcement of the sighting and, with the government, the Ramadan return to "
              "UTC+0",
     "forced_to": ("observe on the 29th of the lunar month and announce the same evening",
                   "decree the return to UTC+0 before Ramadan and the return to UTC+1 after Aid",
                   "publish both in the Bulletin Officiel"),
     "when": "after sunset Rabat on the 29th; the clock decree lands days before the Sunday",
     "information": ("the astronomical prediction", "the provincial testimonies"),
     "constraints": ("the astronomical possibility of a sighting",
                     "Morocco's own practice, which frequently lands a day after Saudi Arabia"),
     "instruments": ("EURUSD", "XAUUSD"),
     "counterparties": ("the government that closes the banks and the bourse",
                        "every institution whose UTC publication minute then moves"),
     "observables": ("the announcement", "the clock decree",
                     "the shifted publication minute of the reference rate itself"),
     "impact": "for about five weeks a year every Moroccan session and publication is one hour "
               "LATER in UTC; a session study that pools those weeks is averaging two different "
               "hours of the global day",
     "persistence": "five weeks a year, every year, drifting eleven days earlier",
     "falsifier": "the Ramadan-window hour band shows the same behaviour as the matched "
                  "non-Ramadan weeks at the SAME UTC hour, in which case the shift carries no "
                  "measurable microstructure and the pack records that",
     "notes": "the only actor in this pack whose decision is astronomical, and the only clock "
              "change of its kind on this desk"},
    {"name": "The European trade and banking counterparties (Spain and France)",
     "holds": "about two-thirds of Moroccan trade and the parent balance sheets behind much of "
              "the listed banking sector; Spain is the first trading partner",
     "forced_to": ("buy the automotive, agricultural and textile exports",
                   "supply the wheat, the refined product and the regasified gas through Spain",
                   "consolidate the Moroccan subsidiaries into European accounts"),
     "when": "continuous, with the European business cycle and the summer tourism season",
     "information": ("their own order books and the Moroccan subsidiaries' results",
                     "the Spanish and French customs data on the same flows, published first"),
     "constraints": ("the European cycle", "the Strait's logistics capacity",
                     "the EU-Morocco agricultural agreement and its legal challenges"),
     "instruments": ("E35", "FRA40", "EURUSD"),
     "counterparties": ("Moroccan exporters and importers", "the Moroccan banks"),
     "observables": ("the Spanish and French trade statistics on the same flows",
                     "the parents' segment disclosures", "the Strait crossing counts"),
     "impact": "the executable leg of every Moroccan equity and trade mechanism; a Moroccan "
               "shock reaches this desk through the Spanish and French indices or not at all",
     "persistence": "structural",
     "falsifier": "Moroccan-specific events (a Conseil decision, a drought declaration, a duty "
                  "decree) carry no abnormal move on E35 or FRA40 beyond what the euro-area "
                  "tape already carries -- the honest expectation, and the pack measures it",
     "notes": "this actor is what keeps the pack from having no executable equity leg at all"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "MA-A", "title": "The quarterly Conseil and the taux directeur",
     "objects": ("the four scheduled decisions a year and the two 2020 emergency cuts",
                 "the communique's inflation-projection revision",
                 "the Treasury-bill cut-off drift between meetings",
                 "the research houses' published pre-Conseil expectation"),
     "conditions": ("the era: the 1.50% floor, the 2022-23 hiking cycle, the 2024-25 easing",
                    "whether the meeting fell inside the Ramadan clock window",
                    "the banking liquidity deficit at the meeting"),
     "instruments": ("EURUSD", "XAUUSD", "E35"),
     "controls": ("the same window on the four nearest non-meeting Tuesdays",
                  "the same window on ECB decision days, separating 'the euro moved' from "
                  "'Bank Al-Maghrib decided'",
                  "a placebo drawn from the Treasury-bill curve's daily noise"),
     "notes": "FOUR decisions a year: the sample is the binding constraint and is stated"},
    {"id": "MA-B", "title": "The 60/40 basket, the band and the distance to its edge",
     "objects": ("the daily cours de reference", "the derived band bounds",
                 "the 2015-04 reweighting and the 2018-01 and 2020-03 widenings",
                 "the FX auctions at the edge", "the bureaux-de-change cash spread"),
     "conditions": ("the band regime (+/-0.3%, +/-2.5%, +/-5.0%)",
                    "the distance-to-edge bucket",
                    "the season (the summer MRE and tourism inflow)"),
     "instruments": ("EURUSD", "USDX"),
     "controls": ("the same state built on a SHUFFLED reference-rate series (a block "
                  "permutation), which is the null for a state variable",
                  "the Tunisian dinar's basket, the sibling Maghreb managed rate, separating "
                  "'North Africa' from 'Morocco'",
                  "the same windows in the +/-0.3% era, when the state could not vary"),
     "notes": "MAD is absent; the basket's arithmetic is what makes EURUSD the readable leg"},
    {"id": "MA-C", "title": "The weekly 7-day advance and the structural liquidity deficit",
     "objects": ("the Tuesday allotment and the bid-to-cover", "the overnight rate's position "
                 "in the corridor", "the Treasury-bill auction the same day",
                 "the deficit's drift with the import bill"),
     "conditions": ("the size of the deficit", "the position in the reserve-requirement cycle",
                    "whether a Conseil fell in the same week"),
     "instruments": ("EURUSD",),
     "controls": ("the same window on Thursdays, which carry no tender",
                  "the matched weekday-plus-hour control on EURUSD",
                  "weeks in which the allotment was unchanged, as the null"),
     "notes": "the operational stance between two quarterly decisions"},
    {"id": "MA-D", "title": "Phosphate, fertiliser affordability and the planting decision",
     "objects": ("OCP's disclosed volumes and realised prices",
                 "the DAP-to-corn affordability ratio",
                 "the 2021-22 affordability shock", "Jorf Lasfar sailings"),
     "conditions": ("the affordability-ratio bucket", "Chinese export policy in the same season",
                    "the ammonia and sulphur input cost"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "controls": ("potash affordability over the same seasons, the other nutrient, separating "
                  "'fertiliser' from 'phosphate'",
                  "the same windows in seasons when the ratio did not move",
                  "USDA's applied-rate and acreage estimates as the independent read"),
     "notes": "INPUT direction, declared: the claim is about the planting decision, not about "
              "Morocco pushing Chicago, and the price leg itself is LICENSED and unreadable"},
    {"id": "MA-E", "title": "The cereal import: ONICL, the tender and the restitution",
     "objects": ("the monthly ONICL situation", "the restitution notices",
                 "arrivals by origin at Casablanca and Jorf Lasfar",
                 "the French and Black Sea origin spread"),
     "conditions": ("the harvest outcome (a 3 mt crop against a 10 mt one)",
                    "whether a restitution was open", "the stock cover in weeks"),
     "instruments": ("WHEAT", "CORN"),
     "controls": ("Algeria's OAIC tender windows, the neighbouring importer, separating 'North "
                  "African demand' from 'Moroccan demand'",
                  "the same months in a good-harvest year",
                  "a randomised-date null on the import-season months"),
     "notes": "France is the marginal origin, so the wheat and euro channels must be mutually "
              "controlled"},
    {"id": "MA-F", "title": "The soft-wheat customs duty switched by decree",
     "objects": ("the Bulletin Officiel decrees", "the ADII circulars",
                 "the millers' lobbying releases a fortnight earlier",
                 "the marketing-year boundary days"),
     "conditions": ("restoration or suspension", "the harvest that motivated it",
                    "whether a restitution accompanied it"),
     "instruments": ("WHEAT", "CORN"),
     "controls": ("the SAME boundary days in years when no decree landed -- the pack's own "
                  "out-of-season placebo",
                  "the matched weekday-plus-hour control on WHEAT",
                  "the millers' release date as an alternative event, to see which of the two "
                  "carries any move"),
     "notes": "the decree dates are PRESS_REPORTED until a BO number is attached; nothing "
              "compiled on them is promoted before that"},
    {"id": "MA-G", "title": "The campaign, the barrage fill and the drought flip",
     "objects": ("the weekly national fill rate", "the DMN rainfall bulletins",
                 "the HCP harvest estimate in the July budget economique",
                 "the six consecutive drought years to 2024"),
     "conditions": ("the end-March fill bucket", "the cumulative rainfall against the norm",
                    "the irrigation allocation decision"),
     "instruments": ("WHEAT", "CORN", "SUGARRAW"),
     "controls": ("Spanish and Algerian rainfall over the same window, the same weather system, "
                  "separating 'the western Mediterranean was dry' from 'Morocco was dry'",
                  "years with the same rainfall but a different fill, which separates storage "
                  "from precipitation",
                  "a randomised-date null on the weekly publication days"),
     "notes": "the series is overwritten in place; without the archive layer there is no PIT "
              "history and every cell here is NOT_PIT_SAFE by construction"},
    {"id": "MA-H", "title": "Refined product without a refinery",
     "objects": ("the post-2015 product import line", "the pump price and the butane subsidy",
                 "the Mohammedia and Jorf Lasfar cargo programme",
                 "the periodic proposals to restart Samir"),
     "conditions": ("the crack level", "the administered butane price and its subsidy cost",
                    "the season (winter heating and the summer driving peak)"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the same windows for a CRUDE-importing neighbour (Tunisia) with a refinery, "
                  "separating 'product importer' from 'oil importer'",
                  "the matched weekday control on XBRUSD",
                  "the pre-2015 era when Samir ran, as the regime control"),
     "notes": "an INPUT-direction mechanism; the exposure is the crack and the honest "
              "expectation is no outward effect on crude"},
    {"id": "MA-I", "title": "Gas and power: the closed pipeline and the interconnectors",
     "objects": ("the 2021-10-31 GME closure", "the reverse flow from Spain",
                 "the Nigeria-Morocco pipeline milestones", "the Xlinks UK decision",
                 "ONEE's generation mix"),
     "conditions": ("the state of the Algerian relationship",
                    "the European gas price regime", "the drought's effect on hydro"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("the TTF-linked European gas moves on the same dates, which is the real leg",
                  "non-event weeks", "the matched weekday control"),
     "notes": "TTF is absent and XNGUSD is Henry Hub; every reading here is declared a "
              "weak-proxy reading and is never promoted above HYPOTHESIS"},
    {"id": "MA-J", "title": "MRE remittances, tourism and the summer euro season",
     "objects": ("the monthly MRE and travel-receipt lines",
                 "the Marhaba crossing counts", "the CMI foreign-card series",
                 "the Aid al-Adha transfer peak"),
     "conditions": ("the solar summer window against the lunar Aid window",
                    "the European labour market", "the band position at the time"),
     "instruments": ("EURUSD", "XAUUSD", "FRA40"),
     "controls": ("the Egyptian and Tunisian remittance seasonality on the same months, which "
                  "separates 'a Mediterranean summer' from 'the Moroccan MRE'",
                  "the lunar Aid windows in years when they fall OUTSIDE the summer",
                  "the matched non-summer months"),
     "notes": "two different clocks -- the solar summer and the lunar Aid -- and pooling them "
              "is the mistake this domain exists to prevent"},
    {"id": "MA-K", "title": "The Casablanca market's mechanics and its European leg",
     "objects": ("the 10% per-security price limit and the queue behind it",
                 "the annual foreign-ownership share",
                 "the T+2 settlement and the index reviews",
                 "the European parents' consolidated exposure"),
     "conditions": ("the number of securities at the limit",
                    "whether a state privatisation or IPO was in the window",
                    "the euro-area risk regime"),
     "instruments": ("E35", "FRA40"),
     "controls": ("the same windows on the euro-area indices with no Moroccan event, which is "
                  "the base rate",
                  "Egyptian and Tunisian market events on the same dates",
                  "the matched weekday control"),
     "notes": "the MASI is a target and not an instrument; the object is the queue, not the "
              "return"},
    {"id": "MA-L", "title": "The Ramadan UTC+0 clock and the moon-sighted closures",
     "objects": ("the declared UTC+0 windows since 2022", "the announced feast closures",
                 "the projected rows that may be a day off",
                 "the reference-rate publication minute inside and outside the window"),
     "conditions": ("inside or outside the clock window",
                    "announced against projected closure",
                    "whether the feast fell at a weekend and was therefore lost"),
     "instruments": ("EURUSD", "XAUUSD", "E35"),
     "controls": ("the matched weekdays 26 weeks away at the SAME UTC hour, which is the only "
                  "way to tell a clock shift from a season",
                  "the same UTC hour in the weeks immediately before the window opens",
                  "the Turkish and Egyptian Ramadan weeks, which carry the fast WITHOUT the "
                  "clock change -- the cleanest control this pack has"),
     "notes": "the mechanism is the CLOCK, not the fast, and the Turkish control is what "
              "separates them"},
    {"id": "MA-M", "title": "Administered prices: compensation, butane, sugar and flour",
     "objects": ("the loi de finances compensation envelope",
                 "the butane bottle price, unchanged for decades and now being reformed",
                 "the subsidised flour quota", "the sugar subsidy per kilo"),
     "conditions": ("the world price of butane, wheat and raw sugar",
                    "the stage of the direct-aid reform that is replacing the subsidies",
                    "the fiscal year"),
     "instruments": ("XBRUSD", "WHEAT", "SUGARRAW"),
     "controls": ("Egypt's and Tunisia's subsidy reform dates on the same instruments",
                  "the same windows in years with no reform step",
                  "a randomised-date null on the announcement days"),
     "notes": "the consumer price does not move, so the entire world-price shock lands on the "
              "budget -- which is why these are fiscal events and not CPI events"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ma_bam_conseil_windows", "domain_ids": ("MA-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ma.miners:bam_conseil_windows",
     "needs": ("CENTRAL_BANK decision dates", "EURUSD, XAUUSD, E35, FRA40 H1 bars"),
     "notes": "four decisions a year, so the sample is small by construction and is reported"},
    {"name": "ma_basket_band_pressure", "domain_ids": ("MA-B",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ma.miners:basket_band_pressure",
     "needs": ("BAM:reference_rate", "EURUSD, USDX H1/D1 bars", "the band decree dates"),
     "notes": "the reference-rate lead plus the band-widening decrees as regime breaks"},
    {"name": "ma_advance_tender_week", "domain_ids": ("MA-C",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ma.miners:advance_tender_week",
     "needs": ("the Tuesday tender calendar", "EURUSD H1 bars"),
     "notes": "the Thursday placebo is built in, because a Tuesday effect is a weekday effect "
              "until it is told apart from one"},
    {"name": "ma_cereal_duty_switch", "domain_ids": ("MA-F", "MA-E"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ma.miners:cereal_duty_switch",
     "needs": ("DUTY_DECREES", "WHEAT, CORN H1 bars"),
     "notes": "the decree dates with the out-of-season boundary placebo beside them"},
    {"name": "ma_ramadan_clock_shift", "domain_ids": ("MA-L",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ma.miners:ramadan_clock_shift",
     "needs": ("RAMADAN_CLOCK", "EURUSD, XAUUSD, E35 H1 bars"),
     "notes": "Morocco's own session mechanism, with the matched-weekday control 26 weeks away"},
    {"name": "ma_transmission_seeds",
     "domain_ids": ("MA-D", "MA-E", "MA-G", "MA-H", "MA-I", "MA-J", "MA-K", "MA-M"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ma.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("MA-A",), "release_surprise": ("MA-E", "MA-J"),
    "calendar_settlement": ("MA-C", "MA-F"), "holiday_liquidity": ("MA-L",),
    "positioning": ("MA-K",), "carry_funding": ("MA-C", "MA-B"),
    "corporate_flow": ("MA-D", "MA-M"), "institutional_flow": ("MA-J", "MA-K"),
    "equity_mechanics": ("MA-K",), "derivatives_expiry": ("MA-K",),
    "failure": ("MA-H", "MA-I"), "residual": ("MA-B", "MA-G"),
    "transfer": ("MA-D", "MA-E"), "scouts": ("MA-G", "MA-L"),
    "session_microstructure": ("MA-L", "MA-K"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "MA-E1", "source": "OCP DAP/TSP export pricing and the affordability ratio",
     "target": "CORN", "targets": ("CORN", "WHEAT"), "to_country": "global", "sign": "+",
     "mechanism": "phosphate is the input the northern-hemisphere planting decision is made "
                  "against; an unaffordable DAP price cuts applied rates and acreage, which is "
                  "a supply effect on the next crop",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "OCP Group as the swing supplier", "constraint": "the farmer's affordability, not "
                                                               "OCP's cost",
     "flow": "input cost into acreage", "condition": "an affordability-ratio move above its "
                                                     "historical interquartile range",
     "control": "potash affordability over the same seasons; seasons with no ratio move",
     "falsifier": "seasons with a large DAP-to-corn ratio move show no change in USDA's applied "
                  "rate or acreage estimates", "evidence": "HYPOTHESIS"},
    {"id": "MA-E2", "source": "Phosphoric acid and TSP shipments to Brazil out of Jorf Lasfar",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN"), "to_country": "global", "sign": "+",
     "mechanism": "the safrinha and the Brazilian soybean crop are fertilised out of the same "
                  "Moroccan and Chinese supply; a shipment programme is the physical counterpart "
                  "of the South American planting budget",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "OCP and the Brazilian importers", "constraint": "vessel and port capacity",
     "flow": "fertiliser shipment", "condition": "the Brazilian planting window only",
     "control": "Chinese DAP export quota dates in the same months",
     "falsifier": "shipment programmes carry no information about Brazilian planted area beyond "
                  "the soybean-to-fertiliser price ratio already in the market",
     "evidence": "HYPOTHESIS"},
    {"id": "MA-E3", "source": "ONICL soft-wheat import programme in a failed-harvest year",
     "target": "WHEAT", "targets": ("WHEAT",), "to_country": "global", "sign": "+",
     "mechanism": "a 5-7 mt import programme is a real share of the French and Black Sea "
                  "exportable surplus and is read as Mediterranean demand",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "ONICL and the millers", "constraint": "the failed domestic harvest",
     "flow": "state-supported import", "condition": "an import-season month with a restitution "
                                                    "open",
     "control": "Algeria's OAIC tender windows; the same months in a good-harvest year",
     "falsifier": "import-season months with a restitution open match the matched-weekday "
                  "control on WHEAT", "evidence": "HYPOTHESIS"},
    {"id": "MA-E4", "source": "The soft-wheat customs duty decree (suspension or restoration)",
     "target": "WHEAT", "targets": ("WHEAT", "CORN"), "to_country": "global", "sign": "+",
     "mechanism": "the decree opens or closes the import window for a whole half-season; it is "
                  "an administered, dated decision and not a price response",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "ADII and the Ministry of Agriculture", "constraint": "the subsidised flour price",
     "flow": "tariff switch", "condition": "a decree date, not a boundary day without one",
     "control": "the same boundary days in years with no decree",
     "falsifier": "the decree windows match the out-of-season boundary placebo",
     "evidence": "HYPOTHESIS"},
    {"id": "MA-E5", "source": "The end-March national barrage fill rate",
     "target": "WHEAT", "targets": ("WHEAT", "CORN"), "to_country": "global", "sign": "-",
     "mechanism": "a low fill at the end of March means a failed cereal campaign, which converts "
                  "Morocco from a self-supplier into a 5-7 mt importer for the following year",
     "horizon": "1 to 6 months", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the water authorities and the growers", "constraint": "the rainfall",
     "flow": "harvest shortfall into import need",
     "condition": "the end-March fill in its lowest tercile",
     "control": "Spanish and Algerian rainfall over the same window; equal-rainfall years with "
                "different storage",
     "falsifier": "the end-March fill carries no information about the eventual import volume "
                  "once rainfall is controlled", "evidence": "HYPOTHESIS"},
    {"id": "MA-E6", "source": "Morocco's refined-product import programme (no domestic refinery)",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "with Samir shut since 2015 the country buys product rather than crude, so the "
                  "exposure is the CRACK and crude is only its first leg",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the product importers and the distributors",
     "constraint": "no refining capacity at all", "flow": "product import",
     "condition": "the winter and summer demand peaks",
     "control": "Tunisia, a crude importer WITH a refinery, over the same windows",
     "falsifier": "no move on XBRUSD beyond the matched control -- the expected result for a "
                  "price-taker, and the pack records it", "evidence": "HYPOTHESIS"},
    {"id": "MA-E7", "source": "The GME closure and the Spanish reverse-flow gas programme",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "Algeria closed the Maghreb-Europe pipeline on 2021-10-31 and Morocco now "
                  "buys regasified cargoes through Spain; the true leg is TTF and XNGUSD is "
                  "Henry Hub, so this edge is weak and says so",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "ONEE and the Ministry of Energy", "constraint": "no pipeline from the east",
     "flow": "cargo demand", "condition": "a tender or a pipeline announcement date",
     "control": "the TTF-linked moves on the same dates",
     "falsifier": "no measurable move on XNGUSD around Moroccan gas events -- the expected "
                  "result, which the pack publishes rather than hides", "evidence": "HYPOTHESIS"},
    {"id": "MA-E8", "source": "The summer MRE and tourism euro inflow",
     "target": "EURUSD", "targets": ("EURUSD",), "to_country": "global", "sign": "+",
     "mechanism": "about US$20bn a year of EUR-denominated inflow concentrated into a summer "
                  "window is a real conversion flow against a managed rate, and it decides where "
                  "inside the band the dirham sits",
     "horizon": "the July-September window", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "Moroccans residing abroad and the tourism industry",
     "constraint": "the European calendar and the Marhaba window",
     "flow": "EUR conversion", "condition": "the summer window only",
     "control": "Egyptian and Tunisian remittance seasonality; the non-summer months",
     "falsifier": "the summer window shows no systematic band position once the trade balance "
                  "is controlled", "evidence": "HYPOTHESIS"},
    {"id": "MA-E9", "source": "The band regime and the distance-to-edge state",
     "target": "EURUSD", "targets": ("EURUSD", "USDX"), "to_country": "global", "sign": "+",
     "mechanism": "the 60/40 basket means the dirham's two legs move against each other with "
                  "EURUSD; at the edge Bank Al-Maghrib is the counterparty and the reaction "
                  "function is known in advance",
     "horizon": "1 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Bank Al-Maghrib FX desk", "constraint": "the +/-5.0% band since 2020-03-09",
     "flow": "official intervention", "condition": "the rate within the outer quintile of the "
                                                   "band",
     "control": "the same state on a shuffled reference-rate series; the +/-0.3% era",
     "falsifier": "the distance-to-edge state carries no information about the EURUSD path "
                  "beyond what the euro-dollar tape already carries", "evidence": "HYPOTHESIS"},
    {"id": "MA-E10", "source": "COSUMAR's raw sugar import programme",
     "target": "SUGARRAW", "targets": ("SUGARRAW", "SUGAR"), "to_country": "global", "sign": "+",
     "mechanism": "Morocco imports roughly 1 mt of raws a year to cover the half of consumption "
                  "the domestic beet and cane cannot supply, and a drought year raises it",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "COSUMAR and the Caisse de compensation",
     "constraint": "the administered retail price and the irrigation water the beet needs",
     "flow": "refining demand", "condition": "a beet-crop shortfall year",
     "control": "Algeria's and Egypt's raw import programmes in the same months",
     "falsifier": "a collapsed beet crop is not followed by a higher raw import line within two "
                  "quarters", "evidence": "HYPOTHESIS"},
    {"id": "MA-E11", "source": "Moroccan sovereign issuance and the frontier-spread regime",
     "target": "EURTRY", "targets": ("EURTRY", "EURZAR"), "to_country": "global", "sign": "+",
     "mechanism": "Morocco is the investment-grade end of the MENA frontier complex, so its "
                  "issuance and rating events are read as a regional risk signal by the same "
                  "accounts that hold the weaker names",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Direction du Tresor and the rating agencies",
     "constraint": "the precautionary IMF facility and the deficit path",
     "flow": "portfolio reallocation", "condition": "an issuance or rating action date",
     "control": "the same windows around Egyptian and Tunisian rating actions",
     "falsifier": "Moroccan issuance and rating dates carry no abnormal move on the frontier "
                  "legs beyond the global risk tape", "evidence": "HYPOTHESIS"},
    {"id": "MA-E12", "source": "The Spanish and French trade and banking exposure to Morocco",
     "target": "E35", "targets": ("E35", "FRA40"), "to_country": "global", "sign": "+",
     "mechanism": "Spain is Morocco's first trading partner and the listed Moroccan banks and "
                  "industrials sit inside European groups, so a Moroccan shock reaches this desk "
                  "through the Iberian and French indices or not at all",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the European parents and exporters",
     "constraint": "the consolidation of the Moroccan subsidiaries",
     "flow": "earnings and trade exposure", "condition": "a Moroccan-specific event date",
     "control": "the same windows with no Moroccan event, which is the base rate",
     "falsifier": "Moroccan events carry no abnormal move on E35 or FRA40 beyond the euro-area "
                  "tape -- the honest expectation", "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the 80/20 basket and the +/-0.3% band", "start": "2010-01-01", "end": "2015-04-12",
     "regime": "the dirham pegged to a euro-heavy basket inside a band so narrow it was a peg "
               "in all but name; no distance-to-edge state could vary",
     "markers": ("2013-08-03 the first Precautionary and Liquidity Line",),
     "why_it_matters": "MA-B's state variable cannot exist here; pooling this era into a band "
                       "study measures a peg and calls it a band",
     "status": "SETTLED"},
    {"name": "the 60/40 reweighting", "start": "2015-04-13", "end": "2018-01-14",
     "regime": "the basket reweighted to 60% EUR / 40% USD on 2015-04-13, still inside "
               "+/-0.3%; the Samir refinery shut in August 2015 and the country became a pure "
               "product importer",
     "markers": ("2015-04-13 the reweighting", "2015-08 Samir halts and never restarts"),
     "why_it_matters": "the basket's arithmetic changes here, so every EURUSD-to-dirham mapping "
                       "before and after is a different function",
     "status": "SETTLED"},
    {"name": "the first widening to +/-2.5%", "start": "2018-01-15", "end": "2020-03-08",
     "regime": "the band widened to +/-2.5% on 2018-01-15 after a postponed 2017 launch and a "
               "speculative episode that cost reserves; the rate spent most of the era well "
               "inside the new band",
     "markers": ("2017-06 the postponed first attempt and the speculation episode",
                 "2018-01-15 the widening takes effect"),
     "why_it_matters": "the first era in which a distance-to-edge state can vary at all",
     "status": "SETTLED"},
    {"name": "the +/-5% band, the pandemic and the drought years", "start": "2020-03-09",
     "end": "2022-09-26",
     "regime": "the band widened to +/-5.0% on 2020-03-09 days before the lockdown; the taux "
               "directeur cut to 2.00% on 2020-03-17 and 1.50% on 2020-06-16 and held there; "
               "the 2021-10-31 GME closure and the start of consecutive drought years",
     "markers": ("2020-03-09 the second widening", "2020-03-17 the emergency cut",
                 "2021-10-31 Algeria closes the Maghreb-Europe pipeline"),
     "why_it_matters": "the widest band and the lowest rate at once; a decision sample from here "
                       "is one-sided and not exchangeable with the hiking cycle",
     "status": "SETTLED"},
    {"name": "the hiking cycle", "start": "2022-09-27", "end": "2024-06-24",
     "regime": "three hikes -- 2022-09-27, 2022-12-20 and 2023-03-21 -- took the taux directeur "
               "from 1.50% to 3.00%, which was then held for five consecutive Conseils while "
               "inflation fell back and the drought deepened",
     "markers": ("2022-09-27 the first hike in years", "2023-03-21 the 3.00% plateau",
                 "2023-04-03 the IMF Flexible Credit Line approved"),
     "why_it_matters": "the only modern Moroccan hiking sample, and it is three decisions long",
     "status": "SETTLED"},
    {"name": "the easing cycle and the water emergency", "start": "2024-06-25",
     "end": "2026-12-31",
     "regime": "cuts on 2024-06-25, 2024-12-17 and 2025-03-18 took the rate back toward 2.25%; "
               "the desalination and inter-basin transfer programme became the fiscal priority "
               "and the World Cup 2030 build-out began",
     "markers": ("2024-06-25 the first cut", "2025-03-18 the third cut"),
     "why_it_matters": "the current regime; the decision sample here is cuts and holds only",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the dirham is not quoted by this broker",
     "measured": "data/universe/universe.json holds no MAD symbol",
     "consequence": "every domestic mechanism terminates in the euro legs, the softs, the energy "
                    "legs, the European indices or gold; MAD is an INPUT, never a cell"},
    {"constraint": "the band bounds are DERIVED, never published",
     "measured": "Bank Al-Maghrib publishes the reference rate and the basket weights but not "
                 "the daily bounds",
     "consequence": "MA-B's state variable must be computed from the basket and the reference "
                    "rate, and the computation is part of the claim"},
    {"constraint": "the phosphate and fertiliser price assessments forbid machine extraction",
     "measured": "CRU, Argus and Profercy terms; registered machine_use_allowed=false",
     "consequence": "the DAP price leg is UNMEASURED and MA-D is tested on the crops and on "
                    "OCP's own disclosed realisations instead"},
    {"constraint": "the barrage fill and the ONICL situation pages are overwritten in place",
     "measured": "both publish TODAY's number and keep no history",
     "consequence": "their point-in-time history exists only in the archive layer's crawls, and "
                    "a cell compiled on an un-archived month is UNMEASURED rather than assumed"},
    {"constraint": "the soft-wheat duty decrees are carried here as PRESS_REPORTED",
     "measured": "DUTY_DECREES rows have no Bulletin Officiel number attached",
     "consequence": "MA-F may generate hypotheses and may not promote any cell until a BO "
                    "citation is attached to the date the cell was compiled on"},
    {"constraint": "the Conseil meets only four times a year",
     "measured": "four scheduled decisions plus two 2020 emergency cuts in the whole modern era",
     "consequence": "MA-A's event sample is a third of a normal central bank's; the pack reports "
                    "POORLY_MEASURED rather than pooling eras to manufacture events"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Office des Changes monthly MRE and travel receipts", "CMI foreign-card activity",
    "AMMC annual foreign-ownership share", "Bank Al-Maghrib 7-day advance allotment",
    "Direction du Tresor BDT auction results")
SERIES: dict[str, str] = {
    "MA_POLICY": "BAM:taux_directeur", "MA_REFERENCE": "BAM:reference_rate",
    "MA_LIQUIDITY": "BAM:liquidity_deficit", "MA_MRE": "OC:mre_transfers",
    "MA_TRAVEL": "OC:travel_receipts", "MA_CPI": "HCP:ipc",
    "MA_BARRAGE": "MEE:taux_remplissage", "MA_CEREAL_IMPORT": "ONICL:imports",
    "MA_DUTY": "BO:decrets_douane",
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
        "mission": MISSION, "ramadan_clock": RAMADAN_CLOCK, "duty_decrees": DUTY_DECREES,
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
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates),
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in FIXED_NATIONAL),
            "weekly_closed": (5, 6), "notes": HOLIDAYS_RULE["authority"]}


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


def campaign_boundary_days(start: date, end: date) -> list[date]:
    """The marketing-year boundary days inside a span: the 1st of May, June, October and
    November, which is where a soft-wheat duty decree lands when one lands at all."""
    out: list[date] = []
    for year in range(start.year, end.year + 1):
        for month in CAMPAIGN_BOUNDARY_MONTHS:
            for day in CAMPAIGN_BOUNDARY_DAYS:
                got = date(year, month, day)
                if start <= got <= end:
                    out.append(got)
    return sorted(out)


def gmt_window_weekdays(start: date, end: date) -> list[date]:
    """Every weekday inside a declared Ramadan UTC+0 window that also falls inside [start, end].
    These are the sessions whose UTC hour is one hour LATER than the rest of the year."""
    out: list[date] = []
    for lo, hi, _status in RAMADAN_CLOCK.values():
        day = lo
        while day < hi:
            if day.weekday() < 5 and start <= day <= end:
                out.append(day)
            day += timedelta(days=1)
    return sorted(out)
