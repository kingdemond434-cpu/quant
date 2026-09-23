"""NEPAL: a currency hard-pegged to India's, and therefore a lawful third-party read on India.

WHY NEPAL EARNS A PACK AND IS NOT A SMALLER BANGLADESH. Six things belong to this economy and to
no other on the desk's book:

  1. THE RUPEE IS PEGGED TO THE INDIAN RUPEE AT EXACTLY 1.60 NPR = 1 INR, AND HAS BEEN SINCE
     1993. That is not a managed float, not a basket and not a crawl: it is a hard, published,
     unbroken cross-rate maintained by Nepal Rastra Bank, and the Indian rupee circulates
     alongside the Nepalese one along the whole open border. The consequence is arithmetic:
     every USDINR move passes through to the NPR ONE FOR ONE, Nepal has no independent external
     price at all, and Nepal's entire external position is an amplified function of India's.
     THE BROKER QUOTES USDINR. So Nepal's own published data -- the NRB's reserve position, the
     import cover in months, the monthly remittance inflow -- is a LAWFUL, PUBLISHED,
     THIRD-PARTY READ ON INDIAN EXTERNAL CONDITIONS, produced by an institution with no reason
     to manage the Indian narrative, and nobody triangulates it. That is this pack's primary
     transmission edge and NP-A is built on it.

  2. REMITTANCES ARE ABOUT A QUARTER OF GDP -- the highest share of any economy of its size --
     AND THE NRB PUBLISHES THEM MONTHLY BY SOURCE COUNTRY in its `Current Macroeconomic and
     Financial Situation` report. A monthly, published, high-share flow series broken out by
     where the money was earned is a direct read on GULF, MALAYSIAN AND KOREAN LABOUR DEMAND.
     The Korea EPS quota for Nepali workers is published and dated on its own clock. That makes
     Nepal a measurable interaction with the `sa`, `ae`, `my` and `kr` packs rather than a
     country tested in isolation.

  3. THE 2022 IMPORT BAN WAS A REAL, DATED, PUBLISHED CAPITAL CONTROL. Facing an import cover
     that had fallen toward six months, Nepal BANNED the import of ten categories of "luxury"
     goods from 2022-04-26, extended it twice, and lifted it fully on 2022-12-15. A government
     that forbids the importation of motor cars to defend its reserves has produced an
     administered event with a measurable effect on the trade account, on the reserve series and
     -- through the peg -- on the same pressure India was managing with different tools. Almost
     no other economy on this desk's book has a control that blunt with dates that clean.

  4. HYDROPOWER IS A PHYSICAL CROSS-BORDER FLOW INTO THE INDIAN GRID, ON A MONSOON CLOCK. Nepal
     exports surplus generation to India in the wet season (roughly June to October) and imports
     in the dry season, under a long-term power trade agreement for up to 10,000 MW over ten
     years signed with India in January 2024. Generation is overwhelmingly run-of-river, so the
     export capacity is literally a function of rainfall, and the direction of the flow REVERSES
     twice a year on a date the monsoon sets. That is a genuine, published, seasonal
     cross-border energy series -- the opposite of a story.

  5. THE PETROLEUM PRICE IS ADMINISTERED ON A FORTNIGHTLY CLOCK BY A FOREIGN MONOPOLY SUPPLIER.
     Nepal Oil Corporation buys every litre of fuel from Indian Oil Corporation, and the
     transfer price is revised every fortnight -- the 1st and the 16th -- against the
     international product price. So XBRUSD reaches the Nepali price level through an
     ADMINISTERED, DATED, PUBLISHED step function rather than through a market, and the
     pass-through has a calendar a study can condition on.

  6. THE CALENDAR IS BIKRAM SAMBAT AND THE WEEKEND IS ONE DAY LONG. Nepal runs on a calendar
     about 56.7 years ahead of the Gregorian; the fiscal year begins on 1 Shrawan, in mid-July,
     which is DERIVABLE from the BS-Gregorian mapping and is derived here. Dashain and Tihar are
     lunar, move by weeks, and shut the economy for up to a fortnight in September or October --
     they cannot be computed from a weekday rule and are typed with the Nepal Calendar
     Determination Committee named as the authority. AND THE NATIONAL WEEKEND IS SATURDAY ONLY:
     a one-day weekend, with government offices open Sunday to Friday and NEPSE trading Sunday
     to Thursday. A study that assumes a Saturday-Sunday weekend for Nepal mislabels every
     Sunday in the sample as a non-trading day, which is the single most common way this
     jurisdiction is got wrong.

WHAT IS EXECUTABLE AND WHAT IS NOT. NPR is ABSENT from `data/universe/universe.json` and is
carried in `TRANSMISSION_TARGETS` with the 1.6 peg and its route through USDINR. NEPSE, the
NEPSE index, Nepali government bonds and the NRB's own bills are all absent and named. There are
no Nepali derivatives of any kind -- no options, no index futures, no COT -- and foreign
portfolio participation in NEPSE is essentially closed, so the positioning layer is DECLARED
absent at the series level rather than proxied.

THE TWO-LANE ORDER (2026-09-06) BITES HERE TOO. Nepali market commentary is almost entirely
single-name NEPSE equity talk -- the hydropower issues, the banks, the microfinance companies --
and none of it may mint a statistical hypothesis in this pack. Those names enter only as ACTORS,
and the instruments those actors move are USDINR, energy, gold and the regional FX legs.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "NP"
NAME = "Nepal"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`). Declared
#: even though the directory name would imply it, because an implied claim is not a measurement.
JURISDICTIONS: tuple[str, ...] = ("np",)
REGION_COMMAND = "asia"
REGION_DESK = "SOUTH_ASIA"
FOREST = "south_asia"
CURRENCY = "NPR"
#: THE FISCAL YEAR ENDS AT THE END OF ASHAD, which is mid-July in the Gregorian calendar and
#: moves by a day or two with the Bikram Sambat month. The framework wants an MM-DD anchor and
#: this is the honest one: `fiscal_year_bounds` carries the exact dates.
FISCAL_YEAR_END = "07-15"
NATIVE_LANGUAGES: tuple[str, ...] = ("ne", "mai", "bho", "new", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the Nepalese rupee
EXPORT_ECONOMY = "net_importer"    # remittances fund a structural trade deficit
RETAIL_LEVERAGE_REGIME = "restricted"          # residents may not hold offshore margin accounts
MISSION = ("mine Nepal as the hard-pegged, remittance-funded, India-facing economy it is: the "
           "1.60 NPR = 1 INR peg that makes Nepali external data a lawful third-party read on "
           "India, the NRB's monthly remittance-by-source-country series as a Gulf and East "
           "Asian labour-demand gauge, the dated 2022 luxury-import ban, the monsoon-clocked "
           "hydropower export into the Indian grid, the fortnightly IOC-to-NOC petroleum price "
           "revision, and the Bikram Sambat calendar with its one-day weekend and its "
           "fortnight-long Dashain and Tihar shutdown")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The Nepalese rupee is absent (see TRANSMISSION_TARGETS) and so
#: is every domestic listed instrument.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDINR",                                          # the peg's own leg, one for one
    "USDCNH",                                          # the northern border and the other patron
    "XAUUSD",                                          # the import quota and the border corridor
    "XBRUSD", "XNGUSD",                                # the administered fuel price and LPG
    "USDJPY",                                          # the regional funding and risk leg
    "USDKRW", "USDSGD", "USDTHB",                      # the labour-destination and ASEAN legs
    "US500",                                           # the global risk leg remittances ride
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "NPR (the Nepalese rupee) -- USD/NPR and INR/NPR",
     "venue": "Nepal Rastra Bank's published reference rate; the open Indian border",
     "why": "THE HARD PEG, AND IT IS THE PACK'S WHOLE FX STORY: 1.60 NPR = 1 INR since 1993, "
            "unbroken, published, with the Indian rupee circulating alongside along the border. "
            "USD/NPR is therefore USD/INR multiplied by 1.6 and carries no independent "
            "information at all -- which is exactly what makes NEPAL'S OWN EXTERNAL DATA a "
            "lawful third-party read on INDIA. `usdnpr_from_usdinr` is the arithmetic and "
            "USDINR is the only executable leg",
     "proxies": ("USDINR",)},
    {"name": "NEPSE and the NEPSE index",
     "venue": "Nepal Stock Exchange",
     "why": "no CFD is quoted, there are NO derivatives of any kind, and foreign portfolio "
            "participation is essentially closed, so the domestic equity market is a closed "
            "liquidity pool that cannot transmit; it is read as a DOMESTIC LIQUIDITY "
            "OBSERVABLE (margin lending, the broker-loan cap) and never traded",
     "proxies": ("USDINR",)},
    {"name": "Nepali government development bonds and NRB treasury bills",
     "venue": "Nepal Rastra Bank primary auctions",
     "why": "the domestic rate path and the banking system's liquidity, published at auction; "
            "no instrument is quotable, so the rate story routes into USDINR through the peg "
            "and into the Indian curve through the border",
     "proxies": ("USDINR",)},
    {"name": "The NOC administered retail petroleum price",
     "venue": "Nepal Oil Corporation, priced off Indian Oil Corporation's fortnightly revision",
     "why": "the domestic fuel price is a step function set on the 1st and the 16th against the "
            "international product price, so XBRUSD reaches Nepali inflation through an "
            "ADMINISTERED clock rather than a market; the price itself is not tradable and the "
            "crude and product legs are",
     "proxies": ("XBRUSD", "XNGUSD")},
    {"name": "Nepali large cardamom, orthodox tea and the trans-Himalayan trade",
     "venue": "the Birtamod and Biratnagar auction markets; Kerung/Rasuwagadhi and Tatopani",
     "why": "Nepal is the world's largest large-cardamom producer and almost the whole crop goes "
            "to India; there is no exchange, no futures and no public price series at a usable "
            "frequency, so the flow is read in the customs data and carries no executable leg "
            "of its own",
     "proxies": ("USDINR",)},
    {"name": "Nepali hydropower exported to the Indian grid",
     "venue": "the Indian Energy Exchange day-ahead market, through NEA's trading arrangements",
     "why": "a genuine physical cross-border electricity flow on a monsoon clock, settled in "
            "India at Indian prices; the Indian power exchange is not quoted here, so the "
            "seasonal reversal is read in the NEA and customs series and routed into USDINR and "
            "the energy complex it substitutes for",
     "proxies": ("USDINR", "XBRUSD", "XNGUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Nepal Rastra Bank / नेपाल राष्ट्र बैंक (NRB)",
    "short": "NRB",
    "framework": "peg",
    "committee": "the Board of Directors under the Governor; the Monetary Policy is issued as a "
                 "single ANNUAL document rather than decided at scheduled meetings",
    "policy_instrument": "the policy rate and the interest-rate corridor (the standing "
                         "liquidity facility as the ceiling and the deposit collection rate as "
                         "the floor), the cash reserve ratio, the statutory liquidity ratio and "
                         "an unusually active set of DIRECTED CREDIT and margin-lending limits",
    "mandate": "price and external stability, which under a hard peg to the Indian rupee means "
               "defending the RESERVE POSITION rather than an inflation number; inflation is "
               "imported from India by construction",
    "decision_rule": "ONE ANNUAL MONETARY POLICY published after the budget, at the start of the "
                     "fiscal year in mid-July (Shrawan), with QUARTERLY REVIEWS. The annual "
                     "document is the event; the reviews adjust it",
    "decision_calendar_rule": "the annual Monetary Policy lands in the weeks after 1 Shrawan "
                              "(mid-July) and the quarterly reviews follow the BS quarters; the "
                              "exact day is announced and must be stamped from the NRB's own "
                              "notice, never assumed from the Gregorian quarter",
    "decision_dates": (),
    "dates_status": "DECLARED EMPTY (L1.28a). The NRB does not publish a scheduled-meeting "
                    "calendar of the kind the generic miner expects: there is one annual policy "
                    "plus reviews, announced when issued. Inventing a quarterly grid here would "
                    "manufacture events that do not exist; the pack carries the RULE and the "
                    "fiscal-year anchor instead and stamps each actual date from the notice",
    "decision_time_utc": "",
    "announce_local": "Kathmandu (Asia/Kathmandu, UTC+05:45 -- a 45-minute offset, all year, "
                      "which is the only such offset any pack on this desk carries)",
    "dst_rule": "none; Nepal keeps UTC+05:45 all year. THE 45-MINUTE OFFSET IS NOT A CURIOSITY: "
                "any local publication hour maps to a UTC time ending in :15 or :45, so a "
                "window built on whole hours straddles the release",
    "minutes_lag_days": 0,
    "publication_classes": ("monetary_policy_annual", "quarterly_review",
                            "current_macroeconomic_and_financial_situation", "annual_report",
                            "banking_and_financial_statistics", "foreign_exchange_reference_rate",
                            "unified_directives"),
    "policy_rate_series": "NRB:policy_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the 91-day treasury bill cut-off and the interbank rate between policy "
                       "documents; there is no published survey of expectations in Nepal and "
                       "the pack says so rather than inventing one",
    "consensus_proxy_trap": "the interbank rate in Nepal is dominated by the BANKING SYSTEM'S "
                            "DEPOSIT CYCLE and by remittance seasonality, not by policy "
                            "expectations; a move there is a liquidity fact first and a policy "
                            "signal a distant second",
    "reserves_clock": "gross foreign exchange reserves and the IMPORT COVER IN MONTHS are "
                      "published monthly in the Current Macroeconomic and Financial Situation "
                      "report, on the BS month, about five to six weeks after the period",
    "programme": "Nepal has used an IMF Extended Credit Facility arrangement approved in January "
                 "2022, with periodic reviews and disbursements; the reviews are a dated clock "
                 "and, unlike Morocco's precautionary line, this one DISBURSES",
    "off_cycle": (),
    "root": "https://www.nrb.org.np",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "NRB daily foreign exchange reference rate",
     "local": "published each business day in Kathmandu; the INR leg is FIXED at 1.60 by the peg "
              "and every other currency is derived from the Indian rate",
     "time_utc": "03:15", "dst_rule": "none (Asia/Kathmandu is UTC+05:45 all year)",
     "instruments": ("USDINR",), "window_minutes": 45,
     "why": "THE FIXING IS ARITHMETIC, NOT A MARKET. The NRB's USD rate is the Indian rate times "
            "1.6, so the publication carries no Nepali information and the pack says so"},
    {"name": "The IOC-to-NOC fortnightly petroleum transfer price revision",
     "local": "the 1st and the 16th of each month, effective from midnight Kathmandu",
     "time_utc": "18:15", "dst_rule": "none",
     "instruments": ("XBRUSD", "XNGUSD"), "window_minutes": 120,
     "why": "the administered step by which the international product price becomes the Nepali "
            "pump price; the clock is published and `noc_revision_days` computes it"},
    {"name": "NEPSE closing price and the day's index",
     "local": "11:00-15:00 Kathmandu, Sunday to Thursday",
     "time_utc": "09:15", "dst_rule": "none",
     "instruments": ("USDINR",), "window_minutes": 30,
     "why": "the domestic equity close. NOT EXECUTABLE ANYWHERE: read as a liquidity observable "
            "only, because the market is closed to foreign portfolio participation"},
    {"name": "RBI reference rate for the Indian rupee (the peg's upstream fixing)",
     "local": "12:30 Asia/Kolkata", "time_utc": "07:00", "dst_rule": "none",
     "instruments": ("USDINR",), "window_minutes": 30,
     "why": "OWNED BY THE `ind` PACK. It is the only fixing that moves the Nepalese rupee, which "
            "is the whole point of the peg edge: the Nepali number reads on the Indian one"},
    {"name": "LBMA gold price PM auction (the import-quota and corridor leg)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the NRB sets a gold import quota in kilograms per day and the border corridor into "
            "India prices off this fix; the quota is the administered variable"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "NRB Current Macroeconomic and Financial Situation (the monthly BS report)",
     "kind": "day_of_month", "days": (10, 11, 12, 13, 14, 15), "roll": "next",
     "window_utc": ("04:00", "10:00"), "instruments": ("USDINR", "XAUUSD"),
     "why": "the monthly reserve, remittance and trade report, published on the BS month about "
            "five to six weeks after the period it covers"},
    {"name": "Department of Customs monthly foreign trade statistics",
     "kind": "day_of_month", "days": (15, 16, 17, 18, 19, 20), "roll": "next",
     "window_utc": ("04:00", "10:00"), "instruments": ("USDINR", "XAUUSD", "XBRUSD"),
     "why": "trade by commodity and by country on the BS month; the India share is the peg's "
            "own current-account channel and the gold line is the corridor"},
    {"name": "The IOC-NOC fortnightly petroleum price revision", "kind": "day_of_month",
     "days": (1, 16), "roll": "next", "window_utc": ("17:00", "20:00"),
     "instruments": ("XBRUSD", "XNGUSD"),
     "why": "the administered pass-through step; `noc_revision_days` computes the dates"},
    {"name": "Fiscal year boundary: 1 Shrawan and the end of Ashad (mid-July)",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("03:00", "12:00"),
     "instruments": ("USDINR", "XAUUSD"),
     "why": "THE BUDGET AND THE ANNUAL MONETARY POLICY BOTH HANG OFF IT. The boundary is "
            "derivable from the BS-Gregorian mapping and `fiscal_year_bounds` derives it"},
    {"name": "BS quarter ends and the NRB quarterly review", "kind": "fiscal_quarter_end",
     "roll": "previous", "window_utc": ("03:00", "12:00"), "instruments": ("USDINR",),
     "why": "the review clock follows the BIKRAM SAMBAT quarters, not the Gregorian ones, so a "
            "Gregorian quarter-end study is measuring the wrong boundary by two to six weeks"},
    {"name": "The Dashain and Tihar remittance and spending peak", "kind": "month_end",
     "roll": "previous", "window_utc": ("03:00", "12:00"),
     "instruments": ("USDINR", "XAUUSD"),
     "why": "the festival block is the single largest seasonal inflow and the single largest "
            "seasonal gold purchase of the Nepali year, and it MOVES BY WEEKS because it is "
            "lunar"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "NEPSE (Nepal Stock Exchange)",
     "index_symbols": (),
     "open_local": "11:00 (pre-open 10:30)", "close_local": "15:00",
     "open_utc": "05:15", "close_utc": "09:15",
     "dst_rule": "none (Asia/Kathmandu is UTC+05:45 all year)",
     "auction": "a pre-open call followed by continuous trading; circuit limits apply per "
                "security and at the index level",
     "expiry_rule": "NO DERIVATIVES OF ANY KIND. There are no options, no index futures, no "
                    "single-stock futures and no commodity exchange with a live contract, so "
                    "there is no expiry clock at all and the generic expiry miner correctly "
                    "reports UNMEASURED",
     "holidays": "the Nepali public-holiday calendar, which shuts for up to a fortnight at "
                 "Dashain and Tihar",
     "notes": "TRADES SUNDAY TO THURSDAY. No CFD is quoted, foreign portfolio participation is "
              "essentially closed, and the market is therefore a CLOSED LIQUIDITY POOL that "
              "cannot transmit -- it enters this pack as a domestic liquidity observable "
              "(margin lending against shares, the broker-loan cap) and never as an instrument"},
    {"name": "The Kathmandu interbank FX and the open Indian border",
     "index_symbols": (), "open_local": "10:00", "close_local": "16:00",
     "open_utc": "04:15", "close_utc": "10:15", "dst_rule": "none",
     "auction": "none; the INR leg is fixed by the peg and the NRB intermediates USD against it",
     "expiry_rule": "forwards are limited and permission-based under the exchange-control "
                    "regime; there is no exchange clock",
     "holidays": "the banking calendar, with Saturday the only weekly closure",
     "notes": "THE INDIAN RUPEE CIRCULATES ALONGSIDE THE NEPALESE ONE along the whole open "
              "border, which is the physical fact the peg is built on and the reason no "
              "parallel-rate premium of consequence exists against the INR"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "np_nepse_session", "start_utc": "05:15", "end_utc": "09:15",
     "notes": "NEPSE trades 11:00-15:00 Kathmandu, SUNDAY TO THURSDAY; the 45-minute offset "
              "makes every boundary land on a quarter hour in UTC"},
    {"name": "np_nrb_publication", "start_utc": "04:00", "end_utc": "10:00",
     "notes": "the NRB's own publication window in Kathmandu working hours; the monthly report, "
              "the auction results and the reference rate all land inside it"},
    {"name": "np_india_overlap", "start_utc": "03:45", "end_utc": "10:00",
     "notes": "the Indian session the peg runs through; USDINR is quoted here and this is the "
              "only window in which a Nepali observable has an executable counterpart"},
    {"name": "np_noc_revision_evening", "start_utc": "17:00", "end_utc": "20:00",
     "notes": "the fortnightly IOC-NOC petroleum revision, effective from Kathmandu midnight, "
              "which is 18:15 UTC"},
    {"name": "np_gulf_remittance_hours", "start_utc": "05:00", "end_utc": "14:00",
     "notes": "the Gulf working day in which most remittance transfers are actually initiated; "
              "the month-end and festival clustering is the object of NP-C"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "NRB Current Macroeconomic and Financial Situation (monthly)",
     "cadence": "monthly", "time_utc": "06:00", "source": "Nepal Rastra Bank",
     "actual_series": "NRB:macro_situation", "expected_series": "UNMEASURED",
     "notes": "THE PACK'S PRIMARY DOCUMENT: reserves, import cover in months, remittance "
              "inflows BY SOURCE COUNTRY, trade, inflation and credit, all in one report on the "
              "BS month, five to six weeks late"},
    {"name": "NRB annual Monetary Policy and its quarterly reviews",
     "cadence": "annual with quarterly reviews", "time_utc": "06:00",
     "source": "Nepal Rastra Bank", "actual_series": "NRB:policy_rate",
     "expected_series": "UNMEASURED",
     "notes": "issued after the budget at the start of the fiscal year (mid-July); the margin "
              "lending and directed-credit limits in it move the domestic market more than the "
              "rate does"},
    {"name": "Department of Customs monthly foreign trade statistics",
     "cadence": "monthly", "time_utc": "06:00", "source": "Department of Customs",
     "actual_series": "CUSTOMS:trade_by_country", "expected_series": "n/a",
     "notes": "by commodity and by country on the BS month; the India share, the gold line and "
              "the petroleum line are the three that matter here"},
    {"name": "National Statistics Office CPI and national accounts",
     "cadence": "monthly (CPI) and annual (accounts)", "time_utc": "06:00",
     "source": "National Statistics Office", "actual_series": "NSO:cpi",
     "expected_series": "UNMEASURED",
     "notes": "food carries a very large basket weight and the price level is substantially "
              "India's arriving through the open border and the peg"},
    {"name": "The federal budget (Jestha 15, about 29 May) and the fiscal-year opening",
     "cadence": "annual", "time_utc": "09:00", "source": "Ministry of Finance",
     "actual_series": "MOF:budget", "expected_series": "n/a",
     "notes": "presented about seven weeks before the fiscal year it funds begins on 1 Shrawan; "
              "the customs-duty schedule in it is the administered-tariff event"},
    {"name": "NEA generation, import and export of electricity",
     "cadence": "monthly and annual", "time_utc": "06:00",
     "source": "Nepal Electricity Authority", "actual_series": "NEA:power_trade",
     "expected_series": "n/a",
     "notes": "the monsoon reversal: export to India in the wet season, import in the dry one, "
              "under the 2024 long-term power trade agreement"},
    {"name": "NOC fortnightly petroleum price notice",
     "cadence": "fortnightly", "time_utc": "18:15", "source": "Nepal Oil Corporation",
     "actual_series": "NOC:retail_price", "expected_series": "n/a",
     "notes": "the 1st and the 16th; an administered step function on the international product "
              "price, which is the pass-through clock NP-F conditions on"},
    {"name": "Nepal Tourism Board monthly arrivals by air",
     "cadence": "monthly", "time_utc": "06:00", "source": "Nepal Tourism Board / Immigration",
     "actual_series": "NTB:arrivals", "expected_series": "n/a",
     "notes": "the autumn and spring trekking windows are a dated seasonal FX inflow that is "
              "small beside remittances and clean in its timing"},
    {"name": "Nepal Gazette (Nepal Rajpatra) notices",
     "cadence": "weekly and irregular", "time_utc": "UNMEASURED",
     "source": "Department of Printing / Law Commission",
     "actual_series": "GAZETTE:notices", "expected_series": "n/a",
     "notes": "an import ban, a quota, a duty change or a holiday declaration becomes citable "
              "only here; the 2022 luxury-import ban is a gazette notice with a date"},
)

# --------------------------------------------------------------------------- the peg
#: THE HARD CROSS-RATE. 1.60 Nepalese rupees per Indian rupee, fixed by Nepal Rastra Bank on
#: 1993-02-01 and unbroken since. It is the single most load-bearing number in this pack.
NPR_PER_INR = 1.60
PEG_SINCE = date(1993, 2, 1)


def npr_per_inr() -> float:
    """The published cross-rate. A function rather than a bare constant so a test asserts the
    ARITHMETIC and not a literal somebody could edit in two places."""
    return NPR_PER_INR


def usdnpr_from_usdinr(usdinr: float) -> float:
    """USD/NPR from USD/INR, which is the whole of Nepal's external price.

    THIS IS WHY NEPAL IS A READ ON INDIA. The rupee has no independent external value: USD/NPR
    is USD/INR times 1.6 by construction, so a Nepali reserve, import-cover or remittance number
    is a measurement of the SAME external pressure India is managing, produced by a different
    institution with a different incentive and published on a different clock.
    """
    return float(usdinr) * NPR_PER_INR


def peg_state(usdinr: float, reserves_usd_bn: float, monthly_imports_usd_bn: float
              ) -> dict[str, float]:
    """The peg's stress coordinates: the implied USD/NPR, and the IMPORT COVER IN MONTHS that is
    the number the NRB actually defends. Under a hard peg there is no exchange rate to watch, so
    the state variable is the reserve position and nothing else."""
    cover = (float(reserves_usd_bn) / float(monthly_imports_usd_bn)
             if monthly_imports_usd_bn else 0.0)
    return {"usdinr": float(usdinr), "usdnpr": usdnpr_from_usdinr(usdinr),
            "npr_per_inr": NPR_PER_INR,
            "reserves_usd_bn": float(reserves_usd_bn),
            "import_cover_months": cover,
            "below_seven_months": 1.0 if cover < 7.0 else 0.0}


# --------------------------------------------------------------------------- the BS calendar
#: THE BIKRAM SAMBAT FISCAL-YEAR ANCHOR. The Nepali fiscal year begins on 1 Shrawan, which falls
#: in mid-July, and ends at the close of Ashad. The BS year is about 56.7 years ahead of the
#: Gregorian, so BS 2081 opens in Gregorian 2024. The Gregorian date of 1 Shrawan moves by a day
#: with the solar transition, so the ANCHORS are declared from the Nepal Calendar Determination
#: Committee's published patro and the FUNCTION derives everything else from them. That is the
#: honest split: the mapping is a published astronomical fact, not a weekday rule.
SHRAWAN_1: dict[int, date] = {
    2078: date(2021, 7, 16),
    2079: date(2022, 7, 17),
    2080: date(2023, 7, 17),
    2081: date(2024, 7, 16),
    2082: date(2025, 7, 17),
    2083: date(2026, 7, 17),
    2084: date(2027, 7, 17),
}
#: How far ahead the BS year runs. Used to DERIVE a BS year from a Gregorian one when the anchor
#: table does not reach, rather than failing silently.
BS_MINUS_AD = 57                   # for a date on or after 1 Shrawan; 56 before it in that year


def bs_year_of(day: date) -> int:
    """The Bikram Sambat year a Gregorian date falls in, for FISCAL purposes.

    Derived from the anchor table where it reaches and from the BS-Gregorian offset where it
    does not, so a date outside the declared anchors still gets an answer rather than an
    exception -- and the answer says which side of the mid-July boundary it is on.
    """
    for bs in sorted(SHRAWAN_1, reverse=True):
        if day >= SHRAWAN_1[bs]:
            return bs
    approx = day.year + BS_MINUS_AD
    return approx if day >= date(day.year, 7, 17) else approx - 1


def fiscal_year_bounds(bs_year: int) -> tuple[date, date]:
    """The Gregorian bounds of Nepali fiscal year `bs_year`/`bs_year+1`: 1 Shrawan to the day
    before the next 1 Shrawan. DERIVED from the anchor table, never typed twice."""
    start = SHRAWAN_1.get(bs_year)
    if start is None:
        start = date(bs_year - BS_MINUS_AD, 7, 17)
    nxt = SHRAWAN_1.get(bs_year + 1)
    if nxt is None:
        nxt = date(bs_year + 1 - BS_MINUS_AD, 7, 17)
    return start, nxt - timedelta(days=1)


def fiscal_year_of(day: date) -> str:
    """The Nepali fiscal-year label a Gregorian date belongs to, e.g. '2082/83'.

    THE BOUNDARY IS MID-JULY, NOT 1 JANUARY AND NOT 1 APRIL. A study that stamps Nepali fiscal
    data to a Gregorian year is mislabelling roughly half of every year's observations.
    """
    bs = bs_year_of(day)
    return f"{bs}/{(bs + 1) % 100:02d}"


def fiscal_year_start(bs_year: int) -> date:
    """1 Shrawan of `bs_year` in the Gregorian calendar -- the day the budget takes effect and
    the annual Monetary Policy's clock starts."""
    return fiscal_year_bounds(bs_year)[0]


# --------------------------------------------------------------------------- the weekend
#: NEPAL'S WEEKEND IS SATURDAY ONLY. Government offices work Sunday to Friday (Friday a short
#: day) and the weekly closure is Saturday alone -- a genuine one-day weekend that almost no
#: other jurisdiction on this desk's book has. NEPSE is the stricter case: it trades Sunday to
#: Thursday, so its own closure is Friday AND Saturday. The two are DIFFERENT and are declared
#: separately, because assuming a Saturday-Sunday weekend for Nepal mislabels every Sunday in
#: the sample as a non-trading day.
NATIONAL_WEEKEND: tuple[int, ...] = (5,)                  # Saturday only (Mon=0)
NEPSE_CLOSED_WEEKDAYS: tuple[int, ...] = (4, 5)           # Friday and Saturday


def is_national_weekend(day: date) -> bool:
    """True when the Nepali state's own weekly closure falls on this date: SATURDAY ONLY."""
    return day.weekday() in NATIONAL_WEEKEND


def is_nepse_session(day: date) -> bool:
    """True when NEPSE could trade: Sunday to Thursday, and not a declared public holiday."""
    return day.weekday() not in NEPSE_CLOSED_WEEKDAYS and day not in public_holidays(day.year)


def is_business_day(day: date) -> bool:
    """True when the Nepali state and the banks are open: not Saturday, not a public holiday."""
    return not is_national_weekend(day) and day not in public_holidays(day.year)


# --------------------------------------------------------------------------- holidays
#: FIXED GREGORIAN-ANCHORED PUBLIC HOLIDAYS. Some of these are BS dates that happen to map to a
#: near-fixed Gregorian day (Prithvi Jayanti on Poush 27, Democracy Day on Falgun 7, Republic
#: Day on Jestha 15, Constitution Day on Ashoj 3), and the one-day drift is why the table below
#: carries the actual dates and this tuple carries only the genuinely fixed ones.
FIXED_PUBLIC: tuple[tuple[int, int, str], ...] = (
    (1, 1, "अङ्ग्रेजी नयाँ वर्ष / English New Year (banking observance)"),
    (5, 1, "अन्तर्राष्ट्रिय श्रमिक दिवस / International Labour Day"),
    (12, 25, "क्रिसमस / Christmas Day"),
)

#: THE LUNAR AND BS-DATED PUBLIC HOLIDAYS, TYPED. Dashain and Tihar are lunar, move by weeks,
#: and shut the whole economy for up to a fortnight in September or October; Shivaratri, Holi,
#: Buddha Jayanti, Janai Purnima, Krishna Janmashtami and Chhath are lunar too. NONE of them can
#: be produced by a weekday rule. Rows are (date, name, status), and the status names the
#: authority: the NEPAL CALENDAR DETERMINATION COMMITTEE (पञ्चाङ्ग निर्णायक समिति) fixes the
#: national patro from which the government's holiday list is drawn. COMMITTEE_TABLE means the
#: date is taken from that published patro; PROJECTED means this pack computed it and the patro
#: has not been read for it. A PROJECTED row may be a day off and a cell compiled on one is a
#: hypothesis, never a promotion.
LUNAR_PUBLIC: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 1, 11), "पृथ्वी जयन्ती / Prithvi Jayanti", "COMMITTEE_TABLE"),
           (date(2024, 1, 15), "माघे संक्रान्ति / Maghe Sankranti", "COMMITTEE_TABLE"),
           (date(2024, 2, 19), "प्रजातन्त्र दिवस / Democracy Day", "COMMITTEE_TABLE"),
           (date(2024, 3, 8), "महाशिवरात्री / Maha Shivaratri", "COMMITTEE_TABLE"),
           (date(2024, 3, 24), "फागु पूर्णिमा / Holi (hills)", "COMMITTEE_TABLE"),
           (date(2024, 4, 13), "नेपाली नयाँ वर्ष / Nepali New Year (Baisakh 1)",
            "COMMITTEE_TABLE"),
           (date(2024, 5, 23), "बुद्ध जयन्ती / Buddha Jayanti", "COMMITTEE_TABLE"),
           (date(2024, 5, 28), "गणतन्त्र दिवस / Republic Day", "COMMITTEE_TABLE"),
           (date(2024, 8, 19), "जनै पूर्णिमा / Janai Purnima", "COMMITTEE_TABLE"),
           (date(2024, 8, 26), "कृष्ण जन्माष्टमी / Krishna Janmashtami", "COMMITTEE_TABLE"),
           (date(2024, 9, 19), "संविधान दिवस / Constitution Day", "COMMITTEE_TABLE"),
           (date(2024, 10, 10), "फूलपाती / Dashain: Phulpati", "COMMITTEE_TABLE"),
           (date(2024, 10, 11), "महाअष्टमी / Dashain: Maha Ashtami", "COMMITTEE_TABLE"),
           (date(2024, 10, 12), "विजया दशमी / Dashain: Vijaya Dashami", "COMMITTEE_TABLE"),
           (date(2024, 10, 31), "लक्ष्मी पूजा / Tihar: Laxmi Puja", "COMMITTEE_TABLE"),
           (date(2024, 11, 3), "भाइटीका / Tihar: Bhai Tika", "COMMITTEE_TABLE"),
           (date(2024, 11, 7), "छठ पर्व / Chhath", "COMMITTEE_TABLE")),
    2025: ((date(2025, 1, 11), "पृथ्वी जयन्ती / Prithvi Jayanti", "COMMITTEE_TABLE"),
           (date(2025, 1, 14), "माघे संक्रान्ति / Maghe Sankranti", "COMMITTEE_TABLE"),
           (date(2025, 2, 19), "प्रजातन्त्र दिवस / Democracy Day", "COMMITTEE_TABLE"),
           (date(2025, 2, 26), "महाशिवरात्री / Maha Shivaratri", "COMMITTEE_TABLE"),
           (date(2025, 3, 14), "फागु पूर्णिमा / Holi (hills)", "COMMITTEE_TABLE"),
           (date(2025, 4, 14), "नेपाली नयाँ वर्ष / Nepali New Year (Baisakh 1)",
            "COMMITTEE_TABLE"),
           (date(2025, 5, 12), "बुद्ध जयन्ती / Buddha Jayanti", "COMMITTEE_TABLE"),
           (date(2025, 5, 29), "गणतन्त्र दिवस / Republic Day", "COMMITTEE_TABLE"),
           (date(2025, 8, 9), "जनै पूर्णिमा / Janai Purnima", "COMMITTEE_TABLE"),
           (date(2025, 8, 16), "कृष्ण जन्माष्टमी / Krishna Janmashtami", "COMMITTEE_TABLE"),
           (date(2025, 9, 19), "संविधान दिवस / Constitution Day", "COMMITTEE_TABLE"),
           (date(2025, 9, 30), "फूलपाती / Dashain: Phulpati", "COMMITTEE_TABLE"),
           (date(2025, 10, 1), "महाअष्टमी / Dashain: Maha Ashtami", "COMMITTEE_TABLE"),
           (date(2025, 10, 2), "विजया दशमी / Dashain: Vijaya Dashami", "COMMITTEE_TABLE"),
           (date(2025, 10, 20), "लक्ष्मी पूजा / Tihar: Laxmi Puja", "COMMITTEE_TABLE"),
           (date(2025, 10, 23), "भाइटीका / Tihar: Bhai Tika", "COMMITTEE_TABLE"),
           (date(2025, 10, 27), "छठ पर्व / Chhath", "COMMITTEE_TABLE")),
    2026: ((date(2026, 1, 11), "पृथ्वी जयन्ती / Prithvi Jayanti", "COMMITTEE_TABLE"),
           (date(2026, 1, 15), "माघे संक्रान्ति / Maghe Sankranti", "COMMITTEE_TABLE"),
           (date(2026, 2, 15), "महाशिवरात्री / Maha Shivaratri", "PROJECTED"),
           (date(2026, 2, 19), "प्रजातन्त्र दिवस / Democracy Day", "COMMITTEE_TABLE"),
           (date(2026, 3, 4), "फागु पूर्णिमा / Holi (hills)", "PROJECTED"),
           (date(2026, 4, 14), "नेपाली नयाँ वर्ष / Nepali New Year (Baisakh 1)",
            "COMMITTEE_TABLE"),
           (date(2026, 5, 31), "बुद्ध जयन्ती / Buddha Jayanti", "PROJECTED"),
           (date(2026, 5, 29), "गणतन्त्र दिवस / Republic Day", "COMMITTEE_TABLE"),
           (date(2026, 8, 28), "जनै पूर्णिमा / Janai Purnima", "PROJECTED"),
           (date(2026, 9, 4), "कृष्ण जन्माष्टमी / Krishna Janmashtami", "PROJECTED"),
           (date(2026, 9, 20), "संविधान दिवस / Constitution Day", "COMMITTEE_TABLE"),
           (date(2026, 10, 18), "फूलपाती / Dashain: Phulpati", "PROJECTED"),
           (date(2026, 10, 19), "महाअष्टमी / Dashain: Maha Ashtami", "PROJECTED"),
           (date(2026, 10, 20), "विजया दशमी / Dashain: Vijaya Dashami", "PROJECTED"),
           (date(2026, 11, 8), "लक्ष्मी पूजा / Tihar: Laxmi Puja", "PROJECTED"),
           (date(2026, 11, 11), "भाइटीका / Tihar: Bhai Tika", "PROJECTED"),
           (date(2026, 11, 15), "छठ पर्व / Chhath", "PROJECTED")),
}
HOLIDAY_STATUSES: tuple[str, ...] = ("COMMITTEE_TABLE", "PROJECTED")

#: THE FESTIVAL SHUTDOWN WINDOW. Dashain runs from Ghatasthapana to Kojagrat Purnima and Tihar
#: follows a fortnight later; in practice the banks, the customs points and NEPSE close for the
#: Dashain block and again for Bhai Tika, and the whole economy is materially shut for up to a
#: fortnight. Rows are (start, end, status) and the window is the union of the two blocks.
FESTIVAL_SHUTDOWN: dict[int, tuple[date, date, str]] = {
    2024: (date(2024, 10, 10), date(2024, 11, 3), "COMMITTEE_TABLE"),
    2025: (date(2025, 9, 30), date(2025, 10, 23), "COMMITTEE_TABLE"),
    2026: (date(2026, 10, 18), date(2026, 11, 11), "PROJECTED"),
}

#: One-off closures and dated policy facts no recurring rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 10, 12): "Vijaya Dashami on a Saturday -- which in Nepal is the ONLY weekend day, "
                        "so the holiday cost no additional session and the block still ran",
    date(2025, 10, 2): "Vijaya Dashami on a Thursday, taking the whole NEPSE trading week with "
                       "it because the market's own weekend is Friday and Saturday",
}


def public_holidays(year: int) -> dict[date, str]:
    """Nepal's public holidays for a Gregorian year: the fixed dates, the committee-table lunar
    and BS-dated ones, and the one-off declarations.

    NO WEEKEND SUBSTITUTION, and the weekend is ONE DAY. A holiday that lands on the Saturday
    costs nothing extra; one that lands on a Sunday costs a full session, which is the opposite
    of the intuition a Gregorian-weekend assumption produces.
    """
    out: dict[str, str] = {}
    for m, d, name in FIXED_PUBLIC:
        out[date(year, m, d).isoformat()] = name
    for day, name, status in LUNAR_PUBLIC.get(year, ()):
        out[day.isoformat()] = f"{name} [{status}]"
    for day, name in DECLARED_CLOSURES.items():
        # APPENDED, NEVER OVERWRITTEN: a one-off note about a day the recurring rules already
        # produce is extra information about that closure, and replacing the name would delete
        # the festival a study is trying to align on.
        if day.year == year:
            prior = out.get(day.isoformat())
            out[day.isoformat()] = f"{prior} -- {name}" if prior else name
    return {date.fromisoformat(k): v for k, v in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The closed days that cost a NEPSE session: a public holiday that is not already a Friday
    or a Saturday, because the exchange is shut on both of those anyway."""
    return {d: n for d, n in public_holidays(year).items()
            if d.weekday() not in NEPSE_CLOSED_WEEKDAYS}


def committee_dates(year: int) -> dict[date, str]:
    """Only the rows the Nepal Calendar Determination Committee's published patro carries. A
    study that pools PROJECTED rows into a committee-table sample must say so."""
    return {d: n for d, n, st in LUNAR_PUBLIC.get(year, ()) if st == "COMMITTEE_TABLE"}


def festival_shutdown_window(year: int) -> tuple[date, date, str] | None:
    """The Dashain-to-Tihar block for a year as (start, end, status), or None when the pack has
    not declared it. Inside it the banks, the customs points and NEPSE are materially shut and
    the remittance and gold-purchase peak runs."""
    return FESTIVAL_SHUTDOWN.get(year)


def in_festival_shutdown(day: date) -> bool:
    """True when a date falls inside the declared Dashain-Tihar block."""
    got = FESTIVAL_SHUTDOWN.get(day.year)
    return got is not None and got[0] <= day <= got[1]


#: THE FORTNIGHTLY PETROLEUM CLOCK. Indian Oil Corporation revises the transfer price to Nepal
#: Oil Corporation twice a month, on the 1st and the 16th, and NOC passes it through to the pump
#: with an administered margin. The clock is Gregorian, published and derivable.
NOC_REVISION_DAYS: tuple[int, ...] = (1, 16)


def noc_revision_days(start: date, end: date) -> list[date]:
    """Every IOC-to-NOC petroleum price revision date inside a span: the 1st and the 16th of
    each month. THE PASS-THROUGH IS A STEP FUNCTION ON A PUBLISHED CLOCK, which is what makes
    NP-F an administered-event domain and not a correlation."""
    out: list[date] = []
    year, month = start.year, start.month
    while date(year, month, 1) <= end:
        for day in NOC_REVISION_DAYS:
            got = date(year, month, day)
            if start <= got <= end:
                out.append(got)
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return sorted(out)


#: THE 2022 IMPORT BAN, DATED. Ten categories of "luxury" goods -- motor cars, motorcycles above
#: 150cc, mobile phones above a price threshold, liquor, toys, playing cards, diamonds, certain
#: snacks and tobacco -- were banned to defend a reserve position that had fallen toward six
#: months of import cover. Rows are (date, action, status). GAZETTED means a Nepal Gazette
#: notice exists for the date; PRESS_REPORTED means the date as carried by the press and to be
#: confirmed against the gazette before any cell is compiled on it.
IMPORT_CONTROLS: tuple[tuple[date, str, str], ...] = (
    (date(2021, 12, 20), "cash-margin requirement imposed on letters of credit for a widening "
                         "list of imports", "PRESS_REPORTED"),
    (date(2022, 4, 26), "outright ban on ten categories of luxury imports", "GAZETTED"),
    (date(2022, 7, 15), "ban extended into the new fiscal year", "GAZETTED"),
    (date(2022, 8, 30), "ban partially relaxed for some categories", "PRESS_REPORTED"),
    (date(2022, 12, 15), "ban lifted in full", "GAZETTED"),
    (date(2023, 5, 31), "cash-margin requirements progressively withdrawn as cover recovered",
     "PRESS_REPORTED"),
)


def import_control_dates(status: str = "PRESS_REPORTED") -> list[date]:
    """The import-control event dates at or above the given confidence label."""
    order = {"PRESS_REPORTED": 0, "GAZETTED": 1}
    floor = order.get(status, 0)
    return [d for d, _a, st in IMPORT_CONTROLS if order.get(st, 0) >= floor]


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "fixed_gregorian_plus_committee_table_plus_derived_fiscal_boundary",
    "authority": "the Government of Nepal publishes the annual public-holiday list in the Nepal "
                 "Gazette, drawn from the national patro fixed by the NEPAL CALENDAR "
                 "DETERMINATION COMMITTEE (पञ्चाङ्ग निर्णायक समिति); the fiscal-year boundary "
                 "is the BS-Gregorian mapping and is derived, not typed",
    "rule": "THREE GENERATORS AND A ONE-DAY WEEKEND. (1) THE WEEKLY CLOSURE IS SATURDAY ONLY -- "
            "a genuine one-day national weekend, with government offices open Sunday to Friday "
            "-- while NEPSE trades SUNDAY TO THURSDAY and is therefore shut on Friday as well; "
            "the two closures are different and are declared separately, because assuming a "
            "Saturday-Sunday weekend mislabels every Sunday in the sample as a non-trading day. "
            "(2) A SMALL SET OF FIXED GREGORIAN DAYS: 1 January, 1 May and 25 December. (3) THE "
            "LUNAR AND BS-DATED PUBLIC HOLIDAYS, TYPED from the committee's published patro "
            "because no weekday rule produces them: Prithvi Jayanti, Maghe Sankranti, Democracy "
            "Day, Maha Shivaratri, Holi, Nepali New Year (Baisakh 1, mid-April), Buddha "
            "Jayanti, Republic Day, Janai Purnima, Krishna Janmashtami, Constitution Day, the "
            "DASHAIN block (Phulpati, Maha Ashtami, Vijaya Dashami) and the TIHAR block (Laxmi "
            "Puja, Bhai Tika) and Chhath. DASHAIN AND TIHAR MOVE BY WEEKS and shut the economy "
            "for up to a fortnight in September or October; `festival_shutdown_window` carries "
            "the block. NO WEEKEND SUBSTITUTION. THE FISCAL YEAR IS DERIVED: it begins on 1 "
            "Shrawan in mid-July and `fiscal_year_bounds` computes it from the BS-Gregorian "
            "anchors. The clock is Asia/Kathmandu, UTC+05:45 all year -- a 45-minute offset, so "
            "every local hour lands on a quarter hour in UTC.",
    "years": (2024, 2025, 2026),
    "weekend": "SATURDAY ONLY for the state and the banks; Friday AND Saturday for NEPSE",
    "national_rule": "see `rule`; `public_holidays(year)` is the resolved form",
    "market_rule": "the public calendar minus the days NEPSE is shut anyway (Friday and "
                   "Saturday); `market_holidays(year)` is the resolved form",
    "lunar_rule": "COMMITTEE_TABLE, not inferred: the Nepal Calendar Determination Committee "
                  "fixes the national patro and the government's holiday list is drawn from it; "
                  "a PROJECTED row in this table is this pack's own computation awaiting that "
                  "patro and may be a day off",
    "fiscal_rule": "1 Shrawan to the end of Ashad, derived from SHRAWAN_1 by "
                   "`fiscal_year_bounds`; the budget is presented about seven weeks earlier and "
                   "the annual Monetary Policy follows the boundary",
    "distinguishing_fact": "A ONE-DAY WEEKEND AND A CALENDAR 56.7 YEARS AHEAD. Nepal is the only "
                           "jurisdiction in this package whose national weekly closure is a "
                           "single day and whose fiscal year turns in mid-July on a lunisolar "
                           "civil calendar",
    "table": {y: {d.isoformat(): n for d, n in public_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMMITTEE_TABLE for every lunar row",
               2025: "COMMITTEE_TABLE for every lunar row",
               2026: "COMMITTEE_TABLE for the BS-dated civil holidays; PROJECTED for Shivaratri, "
                     "Holi, Buddha Jayanti, Janai Purnima, Janmashtami, the Dashain and Tihar "
                     "blocks and Chhath until the patro is read"},
    "known_dates": {
        "2024-10-12": "Vijaya Dashami 2024 -- on a Saturday, which is Nepal's only weekend day",
        "2025-10-02": "Vijaya Dashami 2025 -- ten days EARLIER than 2024, which is what 'lunar' "
                      "costs a study that assumes an October window",
        "2026-10-20": "PROJECTED Vijaya Dashami 2026 -- eighteen days LATER than 2025",
        "2025-07-17": "1 Shrawan 2082: the fiscal year opens, derived not typed",
        "2022-04-26": "the luxury-import ban takes effect",
    },
    "fn": market_holidays,
    "national_fn": public_holidays,
    "committee_fn": committee_dates,
    "festival_fn": festival_shutdown_window,
    "fiscal_fn": fiscal_year_bounds,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "NRB gross foreign exchange reserves and the import cover in months",
     "root": "https://www.nrb.org.np/category/current-macroeconomic-and-financial-situation/",
     "fields": ("gross_reserves_usd", "nrb_held_reserves", "import_cover_months",
                "merchandise_cover_months", "bop_balance"),
     "frequency": "monthly (on the BS month)", "snapshot": "BS month end",
     "publish_utc": "06:00", "lag_days": 40, "licence": "free, public", "available": True,
     "why": "THE NUMBER THE PEG IS DEFENDED WITH, and therefore the only real state variable "
            "this economy has. Import cover falling toward six months in 2021-22 produced the "
            "luxury-import ban; the same series recovering past a year produced its removal",
     "pit_warning": "published on the BIKRAM SAMBAT month and five to six weeks late, so the "
                    "Gregorian stamp is a translation and must be carried as one"},
    {"name": "NRB monthly remittance inflows BY SOURCE COUNTRY",
     "root": "https://www.nrb.org.np/category/current-macroeconomic-and-financial-situation/",
     "fields": ("remittance_inflow_npr", "by_source_country", "workers_departed",
                "first_time_permits", "renewed_permits"),
     "frequency": "monthly", "snapshot": "BS month", "publish_utc": "06:00", "lag_days": 40,
     "licence": "free, public", "available": True,
     "why": "roughly a quarter of GDP, published monthly, split by where it was earned -- which "
            "makes it a direct read on GULF, MALAYSIAN and KOREAN labour demand and the "
            "interaction that stops this pack being tested alone",
     "pit_warning": "the labour-permit series beside it LEADS the money by three to nine months "
                    "and the two are routinely confused; the permit is the commitment and the "
                    "remittance is the cash"},
    {"name": "Department of Customs monthly trade by commodity and by country",
     "root": "https://www.customs.gov.np/en/monthlystats.html",
     "fields": ("imports_by_country", "exports_by_country", "gold_imports_kg",
                "petroleum_imports", "india_share"),
     "frequency": "monthly", "snapshot": "BS month", "publish_utc": "06:00", "lag_days": 30,
     "licence": "free, public", "available": True,
     "why": "the India share is the peg's own current-account channel, the gold line is the "
            "corridor and the petroleum line is the administered-price pass-through",
     "pit_warning": "BS-month stamped like everything else here; a Gregorian month comparison "
                    "is comparing two different fortnights"},
    {"name": "NEPSE margin lending and broker-loan exposure",
     "root": "https://www.nepalstock.com.np/",
     "fields": ("margin_lending_outstanding", "loan_against_shares", "broker_loan_cap",
                "turnover"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "09:00", "lag_days": 30,
     "licence": "free, public", "available": True,
     "why": "the ONLY domestic positioning series that exists, and it is a credit series rather "
            "than a position one: the NRB's cap on loans against shares is a policy variable "
            "that moves the domestic market directly",
     "pit_warning": "a CLOSED pool: foreign portfolio participation is essentially shut, so "
                    "this series says nothing about anything the desk can trade and is kept as "
                    "a domestic liquidity observable only"},
    {"name": "a CFTC, exchange or dealer positioning series for the Nepalese rupee",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no NPR future, forward or option trades on any exchange the desk "
            "can read, and no COT contract exists for the Nepalese rupee anywhere",
     "pit_warning": "DOES NOT EXIST: NPR positioning is UNMEASURED. The INR COT is not a proxy "
                    "for it -- it is a position in the currency the NPR is pegged TO, which is "
                    "the upstream leg and belongs to the `ind` pack"},
    {"name": "a Nepali derivatives, options or index-futures series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Nepal has no derivatives market of any kind -- no options, no "
            "index futures, no single-stock futures and no live commodity exchange contract",
     "pit_warning": "DOES NOT EXIST: there is no open interest, no implied volatility and no "
                    "expiry clock, so the generic expiry and options miners correctly report "
                    "UNMEASURED rather than reaching for an Indian substitute"},
)

# --------------------------------------------------------------------------- terminology
#: NEPALI IN DEVANAGARI IS THE WORKING LANGUAGE, and the pack means the script. The NRB's own
#: reports and the customs tables carry English alongside, which is why an English-only crawl
#: LOOKS adequate here and is not: the gazette, the festival calendar, the political coverage
#: and the whole retail market ecology (ShareSansar's comment threads, the Arthik Abhiyan
#: reporting, the Terai trade press in Maithili and Bhojpuri) run in Devanagari, and the English
#: corner is a summary written for outsiders.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "central_bank": ("नेपाल राष्ट्र बैंक", "मौद्रिक नीति", "नीतिगत दर", "ब्याजदर कोरिडोर",
                     "अनिवार्य नगद अनुपात", "खुला बजार कारोबार", "गभर्नर", "त्रैमासिक समीक्षा",
                     "स्थायी तरलता सुविधा"),
    "peg": ("स्थिर विनिमय दर", "भारुसँगको विनिमय दर", "एक भारु बराबर एक दशमलव छ रुपैयाँ",
            "विनिमय दर", "भारतीय रुपैयाँ", "खुला सिमाना", "परिवर्त्य विदेशी मुद्रा"),
    "reserves": ("विदेशी विनिमय सञ्चिति", "आयात धान्ने क्षमता", "शोधनान्तर स्थिति",
                 "चालु खाता", "सञ्चिति", "महिनाको आयात", "विदेशी मुद्रा सञ्चिति"),
    "remittance": ("विप्रेषण", "रेमिट्यान्स आप्रवाह", "वैदेशिक रोजगारी", "श्रम स्वीकृति",
                   "वैदेशिक रोजगार विभाग", "खाडी मुलुक", "मलेसिया", "कोरिया ईपीएस",
                   "हुण्डी"),
    "trade_and_customs": ("भन्सार विभाग", "आयात", "निर्यात", "व्यापार घाटा", "भन्सार महसुल",
                          "आयात प्रतिबन्ध", "विलासी वस्तु", "नगद मार्जिन", "प्रज्ञापनपत्र"),
    "energy": ("नेपाल विद्युत प्राधिकरण", "जलविद्युत", "विद्युत निर्यात", "विद्युत आयात",
               "ऊर्जा व्यापार सम्झौता", "मेगावाट", "नेपाल आयल निगम", "पेट्रोलियम मूल्य",
               "इन्धन मूल्य समायोजन"),
    "agriculture": ("अलैंची", "चिया", "इलाम", "अदुवा", "कृषि निर्यात", "मौसमी बाली",
                    "केरुङ नाका", "तातोपानी नाका", "हिमाली व्यापार"),
    "market": ("नेप्से", "नेपाल स्टक एक्सचेन्ज", "सेयर बजार", "धितो कर्जा", "सेयर धितो कर्जा",
               "परिसूचक", "कारोबार रकम", "ब्रोकर", "धितोपत्र बोर्ड"),
    "fiscal": ("अर्थ मन्त्रालय", "बजेट", "आर्थिक वर्ष", "राजस्व", "सार्वजनिक ऋण",
               "पुँजीगत खर्च", "वित्तीय नीति", "श्रावण एक", "असार मसान्त"),
    "calendar": ("विक्रम सम्बत", "पञ्चाङ्ग निर्णायक समिति", "दशैं", "तिहार", "विजया दशमी",
                 "भाइटीका", "लक्ष्मी पूजा", "छठ", "सार्वजनिक बिदा", "शनिबार बिदा",
                 "नेपाली नयाँ वर्ष", "बैशाख एक"),
    "tourism": ("पर्यटक आगमन", "ट्रेकिङ", "पर्वतारोहण", "पर्यटन बोर्ड", "शरद ऋतु",
                "वसन्त ऋतु", "त्रिभुवन अन्तर्राष्ट्रिय विमानस्थल"),
    "gold": ("सुन आयात", "सुनको कोटा", "सुन तस्करी", "गहना", "तोला", "सुनको मूल्य",
             "नेपाल सुनचाँदी व्यवसायी महासंघ"),
    "law_and_gazette": ("नेपाल राजपत्र", "कानून आयोग", "ऐन", "नियमावली", "सूचना",
                        "राजपत्रमा प्रकाशित", "मन्त्रिपरिषद् निर्णय"),
    "inflation": ("उपभोक्ता मूल्य सूचकांक", "मुद्रास्फीति", "खाद्य मूल्य", "गैरखाद्य मूल्य",
                  "राष्ट्रिय तथ्याङ्क कार्यालय", "मूल्यवृद्धि"),
    "labour_destinations": ("कतार", "साउदी अरब", "संयुक्त अरब इमिरेट्स", "मलेसिया",
                            "दक्षिण कोरिया", "जापान", "श्रम सम्झौता", "कामदार कोटा"),
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

#: Devanagari, so a test can assert that this pack did not quietly become an English glossary of
#: a Nepali-speaking country -- the failure this jurisdiction invites, because the NRB and the
#: customs department both publish an English summary beside the real thing.
_DEVANAGARI_RANGES = ((0x0900, 0x097F), (0xA8E0, 0xA8FF), (0x1CD0, 0x1CFF))
#: English working vocabulary the pack must ALSO carry: the NRB's own reports, the customs tables
#: and the IMF review documents are written in it, and a Devanagari-only crawl misses them.
ENGLISH_MARKERS: tuple[str, ...] = (
    "Current Macroeconomic and Financial Situation", "import cover", "remittance inflow",
    "Nepal Rastra Bank", "Department of Customs", "NEPSE", "Bikram Sambat",
    "Nepal Calendar Determination Committee", "Extended Credit Facility",
    "power trade agreement", "Nepal Oil Corporation", "Nepal Electricity Authority")


def has_devanagari(text: str) -> bool:
    """True when the text contains at least one Devanagari codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _DEVANAGARI_RANGES) for ch in str(text))


def devanagari_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_devanagari(t)]


def english_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared English marker actually present in the pack's own query ground."""
    flat = {q for sc in SOURCE_CLASSES for q in sc["queries"]}
    if terminology is not None:
        flat |= {t for terms in terminology.values() for t in terms}
    return [m for m in ENGLISH_MARKERS if any(m in t for t in flat)]


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
        "np_nrb", "Nepal Rastra Bank: the monthly Current Macroeconomic and Financial "
                  "Situation, the annual Monetary Policy and its reviews, banking and financial "
                  "statistics, the reference rate and the unified directives", layer="official",
        roots=("https://www.nrb.org.np/",
               "https://www.nrb.org.np/category/current-macroeconomic-and-financial-situation/",
               "https://www.nrb.org.np/category/monetary-policy/",
               "https://www.nrb.org.np/forex/"),
        queries=("नेपाल राष्ट्र बैंक मौद्रिक नीति", "देशको वर्तमान आर्थिक तथा वित्तीय स्थिति",
                 "विदेशी विनिमय सञ्चिति", "विप्रेषण आप्रवाह", "आयात धान्ने क्षमता",
                 "नीतिगत दर", "त्रैमासिक समीक्षा",
                 "Current Macroeconomic and Financial Situation", "import cover",
                 "remittance inflow", "Nepal Rastra Bank monetary policy"),
        languages=("ne", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S PRIMARY DOCUMENT. Reserves, import cover in months, remittances BY "
              "SOURCE COUNTRY, trade, inflation and credit in one monthly report -- and every "
              "row is stamped to the BIKRAM SAMBAT month, so the Gregorian date is a "
              "translation the collector must carry rather than assume"),
    source_class(
        "np_customs", "Department of Customs: monthly foreign trade statistics by commodity and "
                      "by country, the tariff schedule and the import-ban notices",
        layer="official",
        roots=("https://www.customs.gov.np/", "https://www.customs.gov.np/en/monthlystats.html",
               "https://www.customs.gov.np/en/tariff.html"),
        queries=("भन्सार विभाग मासिक तथ्याङ्क", "आयात निर्यात विवरण", "भन्सार महसुल दर",
                 "आयात प्रतिबन्ध सूचना", "सुन आयात", "पेट्रोलियम आयात",
                 "Department of Customs monthly statistics", "import export by country Nepal"),
        languages=("ne", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the India share is the peg's own current-account channel, the gold line is the "
              "border corridor and the petroleum line is the administered-price pass-through; "
              "this is the only Nepali series with a genuine commodity breakdown"),
    source_class(
        "np_nso_mof", "National Statistics Office and the Ministry of Finance: CPI, national "
                      "accounts, the labour force survey, the federal budget and the Economic "
                      "Survey", layer="official",
        roots=("https://nsonepal.gov.np/", "https://www.mof.gov.np/",
               "https://www.mof.gov.np/en/archive-documents/economic-survey-21.html"),
        queries=("राष्ट्रिय तथ्याङ्क कार्यालय", "उपभोक्ता मूल्य सूचकांक", "कुल गार्हस्थ्य उत्पादन",
                 "आर्थिक सर्वेक्षण", "बजेट वक्तव्य", "श्रमशक्ति सर्वेक्षण",
                 "Nepal economic survey", "consumer price index Nepal"),
        languages=("ne", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the budget is presented around Jestha 15 (about 29 May), seven weeks before the "
              "fiscal year it funds opens on 1 Shrawan -- a gap that is itself a dated event"),
    source_class(
        "np_gazette", "The Nepal Gazette (नेपाल राजपत्र) and the Nepal Law Commission: the "
                      "statutes, the regulations and the dated notices that make an import ban, "
                      "a quota or a holiday declaration citable", layer="official",
        roots=("https://www.lawcommission.gov.np/", "https://rajpatra.dop.gov.np/",
               "https://www.lawcommission.gov.np/np/"),
        queries=("नेपाल राजपत्र सूचना", "आयातमा प्रतिबन्ध सूचना", "मन्त्रिपरिषद् निर्णय",
                 "ऐन नियमावली", "सार्वजनिक बिदा सूचना", "राजपत्रमा प्रकाशित",
                 "Nepal Gazette notice", "Nepal Law Commission act"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE 2022 LUXURY-IMPORT BAN IS A GAZETTE NOTICE WITH A DATE, and so is its "
              "removal; IMPORT_CONTROLS labels each row GAZETTED or PRESS_REPORTED and the "
              "press-reported ones may not carry a promoted cell until a gazette number is "
              "attached"),
    source_class(
        "np_doed_nea", "Department of Electricity Development and the Nepal Electricity "
                       "Authority: licences, generation, the import and export of power to "
                       "India and the long-term power trade agreement", layer="official",
        roots=("https://www.doed.gov.np/", "https://www.nea.org.np/",
               "https://www.nea.org.np/annual_report"),
        queries=("विद्युत विकास विभाग", "जलविद्युत आयोजना अनुमतिपत्र", "विद्युत निर्यात भारत",
                 "विद्युत आयात", "ऊर्जा व्यापार सम्झौता", "नेपाल विद्युत प्राधिकरण वार्षिक "
                 "प्रतिवेदन", "Nepal power trade agreement India",
                 "Nepal Electricity Authority annual report", "NEA electricity export"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a GENUINE physical cross-border flow that REVERSES twice a year on the monsoon; "
              "run-of-river generation means the export capacity is literally rainfall, and the "
              "2024 agreement put a ten-year, 10,000 MW frame around it"),
    source_class(
        "np_india_mirror", "THE MIRROR GROUND, which is the point of this pack: the Reserve Bank "
                           "of India, Indian customs and the Indian power exchange -- the "
                           "upstream side of every Nepali series",
        layer="official",
        roots=("https://www.rbi.org.in/", "https://tradestat.commerce.gov.in/",
               "https://www.iexindia.com/"),
        queries=("RBI weekly statistical supplement reserves", "India Nepal trade statistics",
                 "Indian Energy Exchange day ahead price", "भारत नेपाल व्यापार",
                 "भारतीय रिजर्व बैंक सञ्चिति"),
        languages=("en", "ne"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="REGISTERED HERE AND OWNED BY `ind`. The whole edge is that the NEPALI number is "
              "an independent measurement of the INDIAN condition, so both sides must be read "
              "and the Indian side must never be re-derived here"),
    # ---- institutional
    source_class(
        "np_nepse_sebon", "NEPSE, SEBON (the securities board) and CDSC: the index, turnover, "
                          "margin lending against shares, the broker-loan cap and the listing "
                          "rules", layer="institutional",
        roots=("https://www.nepalstock.com.np/", "https://www.sebon.gov.np/",
               "https://www.cdscnp.com/"),
        queries=("नेप्से परिसूचक", "सेयर धितो कर्जा", "धितोपत्र बोर्ड नेपाल", "कारोबार रकम",
                 "ब्रोकर कमिसन", "मार्जिन कर्जा सीमा",
                 "NEPSE index turnover", "SEBON margin lending directive"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A CLOSED LIQUIDITY POOL: no derivatives at all and essentially no foreign "
              "portfolio participation, so this ground is a DOMESTIC CREDIT observable -- the "
              "NRB's cap on loans against shares moves it directly -- and never an instrument"),
    source_class(
        "np_banks_ficci", "The commercial banks, the Nepal Bankers' Association, the "
                          "remittance companies (IME, Prabhu, City Express) and the chambers "
                          "(FNCCI, CNI)", layer="institutional",
        roots=("https://www.nepalbankers.com.np/", "https://www.fncci.org/",
               "https://www.cnind.org/", "https://www.imeremit.com.np/"),
        queries=("नेपाल बैंकर्स संघ", "वाणिज्य बैंक निक्षेप", "रेमिट कम्पनी",
                 "उद्योग वाणिज्य महासंघ", "ब्याजदर सम्झौता", "तरलता अभाव",
                 "Nepal Bankers Association liquidity", "FNCCI statement"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the bankers' association publishes the deposit-rate agreement and the liquidity "
              "position before the NRB's monthly report does, which is the cheapest leading "
              "read on the banking cycle NP-H is about"),
    source_class(
        "np_imf_wb", "The IMF Nepal country page and the World Bank / ADB country programmes: "
                     "the Extended Credit Facility reviews, Article IV and the development "
                     "updates", layer="institutional",
        roots=("https://www.imf.org/en/Countries/NPL",
               "https://www.worldbank.org/en/country/nepal",
               "https://www.adb.org/countries/nepal/main"),
        queries=("IMF Nepal Extended Credit Facility review", "Nepal Article IV",
                 "World Bank Nepal development update", "अन्तर्राष्ट्रिय मुद्रा कोष नेपाल",
                 "विस्तारित कर्जा सुविधा"),
        languages=("en", "ne"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="UNLIKE A PRECAUTIONARY LINE, THIS ONE DISBURSES: the ECF reviews are a dated "
              "clock with money attached, and the staff reports are the only public documents "
              "that discuss the peg's sustainability at all"),
    # ---- academic
    source_class(
        "np_universities", "Tribhuvan University's Central Department of Economics, Kathmandu "
                           "University, the Nepal Rastra Bank Research Department's working "
                           "papers and the South Asian economics literature", layer="academic",
        roots=("https://www.nrb.org.np/category/nrb-working-paper/",
               "https://tribhuvan-university.edu.np/", "https://ku.edu.np/"),
        queries=("विप्रेषण र आर्थिक वृद्धि अध्ययन", "स्थिर विनिमय दर नेपाल अनुसन्धान",
                 "नेपाल मुद्रास्फीति भारत", "NRB working paper remittance",
                 "Nepal India exchange rate peg study", "remittance Dutch disease Nepal"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the NRB's own working-paper series is where the peg's pass-through and the "
              "remittance-to-inflation channel are actually estimated; every result is a "
              "hypothesis until the desk reproduces it on its own data"),
    source_class(
        "np_academic_index", "The open indexes and the South Asian policy institutes: OpenAlex, "
                             "CORE, NepJOL (the Nepal Journals Online archive), SAWTEE and the "
                             "Institute for Integrated Development Studies", layer="academic",
        roots=("https://www.nepjol.info/", "https://openalex.org/", "https://core.ac.uk/",
               "https://sawtee.org/"),
        queries=("NepJOL Nepal economy", "Nepal hydropower export economics",
                 "Nepal labour migration Gulf study", "नेपाल श्रम आप्रवासन अध्ययन",
                 "trans-Himalayan trade research"),
        languages=("en", "ne"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="NepJOL is a genuinely deep national open-access archive, which is unusual for an "
              "economy this size and is the reason the academic layer here is not thin"),
    # ---- practitioner
    source_class(
        "np_market_sites", "The Nepali market practitioner sites: ShareSansar, Merolagani, "
                           "NepaliPaisa, Bizmandu and Nepse Alpha -- daily market reports, "
                           "company filings in Nepali and the broker commentary",
        layer="practitioner",
        roots=("https://www.sharesansar.com/", "https://merolagani.com/",
               "https://www.nepalipaisa.com/", "https://bizmandu.com/"),
        queries=("आजको बजार समीक्षा", "नेप्से घट्यो", "लगानीकर्ता", "हाइड्रो सेयर",
                 "बोनस सेयर घोषणा", "बजार विश्लेषण", "तरलता र बजार"),
        languages=("ne", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="ALMOST ENTIRELY SINGLE-NAME NEPSE EQUITY TALK, which under the two-lane order "
              "(2026-09-06) may not mint a statistical hypothesis here at all. It is kept for "
              "the MACRO half -- the liquidity, margin-lending and remittance commentary -- and "
              "for the vocabulary, which is where the Nepali market's own words are"),
    source_class(
        "np_business_press", "The business desks: Arthik Abhiyan (आर्थिक अभियान), Nepal "
                             "Economic Forum, Karobar Daily and the New Business Age",
        layer="practitioner",
        roots=("https://www.abhiyandaily.com/", "https://nepaleconomicforum.org/",
               "https://www.newbusinessage.com/"),
        queries=("आर्थिक अभियान", "व्यापार घाटा बढ्यो", "विप्रेषण बढ्यो", "सञ्चिति घट्यो",
                 "बैंकिङ तरलता", "आयात प्रतिबन्ध असर", "Nepal Economic Forum analysis"),
        languages=("ne", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Arthik Abhiyan carries the reserve, remittance and trade figures the day the NRB "
              "posts them and usually with the BS-to-Gregorian translation already done, which "
              "is the cheapest way to date a monthly release"),
    # ---- retail ecology
    source_class(
        "np_retail_communities", "The Nepali retail investor and migrant-worker communities: "
                                 "r/Nepal and r/NepalStock, the ShareSansar comment threads, "
                                 "the Facebook NEPSE groups and the Gulf and Malaysia worker "
                                 "forums", layer="retail_ecology",
        roots=("https://www.reddit.com/r/Nepal/", "https://www.reddit.com/r/NepalStock/",
               "https://www.sharesansar.com/"),
        queries=("सेयर किन्ने कि नकिन्ने", "नेप्से कहाँ जान्छ", "धितो कर्जा ब्याज",
                 "खाडीमा काम", "श्रम स्वीकृति कति दिन", "हुण्डी दर", "कोरिया ईपीएस नतिजा"),
        languages=("ne", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE. Two things here are genuine "
              "observables: the HUNDI (informal transfer) rate chatter, which is the parallel "
              "price of the same remittance the NRB counts formally, and the labour-permit "
              "queue talk, which leads the permit statistics"),
    source_class(
        "np_hundi_chatter", "Public commentary on the informal transfer channel and the gold "
                            "corridor: the hundi rate against the formal remittance rate, and "
                            "the border gold trade", layer="retail_ecology",
        roots=("https://www.reddit.com/r/Nepal/", "https://www.abhiyandaily.com/",
               "https://www.onlinekhabar.com/"),
        queries=("हुण्डी दर आज", "हुण्डी कारोबार", "सुन तस्करी पक्राउ", "सुनको कोटा",
                 "अवैध सुन", "विदेशी मुद्रा अपचलन"),
        languages=("ne",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform and publisher terms; public posts only",
        notes="PUBLIC COMMENTARY ONLY, and it is the one place the SECOND price of a Nepali "
              "rupee shows up: the hundi spread to the formal channel is the capital-control "
              "stress observable NP-I conditions on, carried at low weight beside the NRB's "
              "formal remittance series"),
    # ---- app ecosystem
    source_class(
        "np_fintech_rails", "The payment and trading rails an actual Nepali uses: eSewa, "
                            "Khalti, IME Pay, ConnectIPS and the Nepal Clearing House, plus "
                            "MeroShare and the NEPSE TMS trading terminal", layer="app_ecosystem",
        roots=("https://esewa.com.np/", "https://khalti.com/", "https://www.nchl.com.np/",
               "https://meroshare.cdsc.com.np/"),
        queries=("इसेवा", "खल्ती", "कनेक्ट आईपीएस", "मेरो सेयर", "टीएमएस लगइन",
                 "डिजिटल भुक्तानी तथ्याङ्क", "मोबाइल बैंकिङ प्रयोगकर्ता"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free statistics; app stores public",
        notes="the Nepal Clearing House and the NRB publish digital-payment volumes, which is a "
              "genuine near-real-time domestic activity proxy in an economy whose official "
              "statistics arrive five weeks late on a different calendar"),
    source_class(
        "np_migration_apps", "The labour-migration rails: the Department of Foreign Employment's "
                             "permit system, the Korea EPS portal and the Gulf recruitment "
                             "platforms", layer="app_ecosystem",
        roots=("https://dofe.gov.np/", "https://www.eps.go.kr/", "https://fewb.gov.np/"),
        queries=("वैदेशिक रोजगार विभाग श्रम स्वीकृति", "ईपीएस कोरिया आवेदन",
                 "कामदार माग पत्र", "वैदेशिक रोजगार बोर्ड", "EPS Nepal quota"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PERMIT LEADS THE MONEY BY THREE TO NINE MONTHS. The Department of Foreign "
              "Employment's permit counts and the published Korea EPS quota are the forward "
              "half of the remittance series, and confusing the two is the standard error here"),
    # ---- media
    source_class(
        "np_nepali_press", "The Nepali-language press: Kantipur / eKantipur, Setopati, "
                           "Onlinekhabar, Nagarik and Ratopati", layer="media",
        roots=("https://ekantipur.com/", "https://www.setopati.com/",
               "https://www.onlinekhabar.com/", "https://nagariknews.nagariknetwork.com/"),
        queries=("अर्थतन्त्र समाचार", "राष्ट्र बैंकले भन्यो", "सरकारले निर्णय गर्‍यो",
                 "इन्धनको मूल्य बढ्यो", "विप्रेषण रेकर्ड", "भारतसँग विद्युत सम्झौता",
                 "बजेट ल्याइयो"),
        languages=("ne",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THE DEVANAGARI PRESS IS NOT THE ENGLISH ONE WITH DIFFERENT LETTERS: the fuel "
              "price notice, the festival calendar, the gazette notices and the political "
              "decisions behind an import control are reported here first and often only here"),
    source_class(
        "np_english_press", "The English-language press and the regional desks: the Kathmandu "
                            "Post, Nepali Times, the Himalayan Times, and the Indian coverage "
                            "of Nepal in the Hindu, Mint and the Indian Express",
        layer="media",
        roots=("https://kathmandupost.com/", "https://nepalitimes.com/",
               "https://thehimalayantimes.com/"),
        queries=("Nepal foreign exchange reserves", "Nepal remittance record",
                 "Nepal India power trade", "Nepal import ban luxury goods",
                 "Nepal Rastra Bank monetary policy review",
                 "Nepal Calendar Determination Committee holiday list"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the English press is the fastest route to a DATE and the slowest to a REASON; it "
              "is kept for stamping releases and never for the mechanism, which is in Nepali"),
    source_class(
        "np_licensed_terminals", "Licensed terminals and paywalled data: Bloomberg and "
                                 "Refinitiv for the INR leg and the South Asian curve, and the "
                                 "subscription tiers of the regional research houses",
        layer="media",
        roots=("https://www.bloomberg.com/", "https://www.lseg.com/en/data-analytics"),
        queries=("USDINR forward curve terminal", "Nepal sovereign risk research subscription",
                 "South Asia macro consensus estimates"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. There is NO published consensus for any Nepali "
              "release -- no survey, no economist poll -- so a 'surprise' in this pack is "
              "measured against a published trailing rule and the absence of a consensus is "
              "named rather than papered over with a terminal number the desk may not extract"),
    # ---- archive
    source_class(
        "np_archive_official", "The historical run: NRB annual reports and the Banking and "
                              "Financial Statistics series, the Economic Survey archive, the "
                              "Nepal Gazette back numbers and the Madan Puraskar Pustakalaya "
                              "digital collections", layer="archive",
        roots=("https://www.nrb.org.np/category/annual-reports/",
               "https://www.mof.gov.np/en/archive-documents/economic-survey-21.html",
               "https://rajpatra.dop.gov.np/", "https://madanpuraskar.org/"),
        queries=("नेपाल राष्ट्र बैंक वार्षिक प्रतिवेदन", "आर्थिक सर्वेक्षण पुरानो",
                 "राजपत्र पुरानो अंक", "बैंकिङ तथा वित्तीय तथ्याङ्क",
                 "Nepal Rastra Bank annual report archive"),
        languages=("ne", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE RUN IS REAL BUT INCOMPLETE, and the pack says so: the NRB's own series goes "
              "back decades in PDF, the gazette archive is only partly digitised, and the "
              "pre-2000 record is thin -- which bounds how far back any Nepali cell can reach"),
    source_class(
        "np_wayback", "web.archive.org snapshots of the NRB monthly report index, the customs "
                      "monthly statistics page and the NOC price notice page, all of which "
                      "overwrite in place", layer="archive",
        roots=("https://web.archive.org/web/*/nrb.org.np*",
               "https://web.archive.org/web/*/customs.gov.np*",
               "https://web.archive.org/web/*/noc.org.np*"),
        queries=("nrb current macroeconomic situation archive",
                 "customs.gov.np monthly statistics archive",
                 "Nepal Oil Corporation fuel price notice archive",
                 "Bikram Sambat to Gregorian conversion table"),
        languages=("ne", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE NOC PRICE PAGE SHOWS TODAY'S PRICE AND KEEPS NO HISTORY, and the customs "
              "monthly page is replaced each month; without this layer the fortnightly "
              "pass-through series of NP-F is reconstructible only from press quotes"),
    # ---- physical economy
    source_class(
        "np_border_transport", "The physical trade plane: the customs points (Birgunj, "
                               "Biratnagar, Bhairahawa, Rasuwagadhi/Kerung, Tatopani), the dry "
                               "ports, Tribhuvan International Airport and the Indian transit "
                               "corridor to Kolkata and Visakhapatnam", layer="physical_economy",
        roots=("https://www.customs.gov.np/en/customofficelist.html",
               "https://www.nitdb.org.np/", "https://www.tiairport.com.np/"),
        queries=("बिरगंज भन्सार", "रसुवागढी नाका", "तातोपानी नाका खुल्यो",
                 "सुक्खा बन्दरगाह", "कोलकाता बन्दरगाह ढुवानी", "विशाखापट्टनम मार्ग",
                 "त्रिभुवन विमानस्थल यात्रु"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A LANDLOCKED ECONOMY'S PHYSICAL PLANE IS ITS TRANSIT RIGHTS. Everything arrives "
              "through India or over two Himalayan passes, so a border closure is a supply "
              "shock with a date -- the 2015-16 blockade being the demonstration"),
    source_class(
        "np_power_water_weather", "The generation and weather plane: NEA generation and the "
                                  "Indian interconnections, the Department of Hydrology and "
                                  "Meteorology's monsoon bulletins, and the tourism arrivals by "
                                  "season", layer="physical_economy",
        roots=("https://www.nea.org.np/", "https://www.dhm.gov.np/",
               "https://ntb.gov.np/"),
        queries=("मनसुन पूर्वानुमान", "वर्षाको मात्रा", "जलविद्युत उत्पादन",
                 "विद्युत निर्यात मेगावाट", "पर्यटक आगमन तथ्याङ्क", "ट्रेकिङ सिजन",
                 "Nepal monsoon onset forecast"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="RUN-OF-RIVER GENERATION MEANS THE EXPORT IS LITERALLY RAINFALL. The monsoon "
              "bulletin is therefore an upstream input to a cross-border energy flow, and the "
              "trekking seasons are a small, cleanly dated FX inflow beside it"),
    # ---- source graph
    source_class(
        "np_source_graph", "Who cites whom: NRB -> Arthik Abhiyan and ShareSansar -> Kantipur "
                           "and Setopati -> the Facebook groups; the Nepal Gazette -> the "
                           "Nepali press -> the Indian desks; the Department of Foreign "
                           "Employment -> the Gulf recruitment chatter", layer="source_graph",
        roots=("https://www.nrb.org.np/", "https://www.sharesansar.com/",
               "https://ekantipur.com/", "https://www.setopati.com/"),
        queries=("स्रोतका अनुसार", "राष्ट्र बैंकका अनुसार", "उच्च अधिकारीले भने",
                 "नाम नबताउने सर्तमा", "विश्वस्त स्रोत", "according to NRB officials"),
        languages=("ne", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'स्रोतका अनुसार' and 'नाम नबताउने सर्तमा' mark the unattributed leak that "
              "precedes a gazette notice or a policy change here by a day or two; the graph is "
              "how a leak is told from a repost and how the BS-to-Gregorian date translation "
              "propagates through the tape"),
)

#: DECLARED EMPTY AND MEASURED, NOT ASSUMED. All ten layers carry a real, named root for Nepal.
#: The honest absences in this jurisdiction are INSTRUMENT- and SERIES-level, not layer-level --
#: no NPR contract anywhere, no derivatives market of any kind, no published consensus for any
#: release, and a domestic equity market closed to foreign participation -- and each is recorded
#: in `ACCESS_CONSTRAINTS` and in `POSITIONING_SOURCES` with `available=False`. Declaring a
#: layer absent while a real ground exists would be padding in reverse.
LAYER_ABSENCES: dict[str, str] = {}

#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually runs, per layer, in Nepali
#: Devanagari with the English working terms the official summaries use beside them.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("देशको वर्तमान आर्थिक तथा वित्तीय स्थिति", "विदेशी विनिमय सञ्चिति मासिक",
                 "विप्रेषण आप्रवाह देश अनुसार", "भन्सार विभाग मासिक तथ्याङ्क",
                 "नेपाल राजपत्र सूचना आयात", "मौद्रिक नीति त्रैमासिक समीक्षा",
                 "Current Macroeconomic and Financial Situation Nepal"),
    "institutional": ("नेप्से परिसूचक कारोबार", "सेयर धितो कर्जा सीमा",
                      "नेपाल बैंकर्स संघ निक्षेप ब्याजदर", "उद्योग वाणिज्य महासंघ विज्ञप्ति",
                      "IMF Nepal ECF review", "SEBON directive margin"),
    "academic": ("विप्रेषण र आर्थिक वृद्धि नेपाल अध्ययन", "स्थिर विनिमय दर पास-थ्रु अनुसन्धान",
                 "नेपाल श्रम आप्रवासन अध्ययन", "NRB working paper remittance inflation",
                 "Nepal hydropower export economics"),
    "practitioner": ("आजको बजार समीक्षा नेप्से", "तरलता अभाव बैंक", "विप्रेषण बढ्यो घट्यो",
                     "आयात प्रतिबन्धको असर", "बजार विश्लेषण हाइड्रो",
                     "Nepal Economic Forum analysis"),
    "retail_ecology": ("हुण्डी दर आज", "श्रम स्वीकृति लाइन", "कोरिया ईपीएस नतिजा",
                       "सेयर धितो कर्जा ब्याज", "खाडीमा तलब", "नेप्से कहाँ जान्छ"),
    "app_ecosystem": ("इसेवा भुक्तानी तथ्याङ्क", "खल्ती प्रयोगकर्ता", "मेरो सेयर लगइन",
                      "टीएमएस कारोबार", "कनेक्ट आईपीएस", "डिजिटल भुक्तानी वृद्धि"),
    "media": ("अर्थतन्त्र समाचार नेपाल", "इन्धनको मूल्य समायोजन", "भारतसँग विद्युत सम्झौता",
              "बजेट वक्तव्य समाचार", "Kathmandu Post economy", "Nepali Times remittance"),
    "archive": ("नेपाल राष्ट्र बैंक वार्षिक प्रतिवेदन पुरानो", "आर्थिक सर्वेक्षण संग्रह",
                "राजपत्र पुरानो अंक", "बैंकिङ तथा वित्तीय तथ्याङ्क संग्रह",
                "NOC fuel price notice archive"),
    "physical_economy": ("रसुवागढी नाका व्यापार", "तातोपानी नाका खुल्यो", "बिरगंज भन्सार ढुवानी",
                         "मनसुन पूर्वानुमान वर्षा", "जलविद्युत उत्पादन मेगावाट",
                         "पर्यटक आगमन तथ्याङ्क"),
    "source_graph": ("स्रोतका अनुसार", "राष्ट्र बैंकका अनुसार", "नाम नबताउने सर्तमा",
                     "उच्च अधिकारीले भने", "according to NRB officials"),
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
    for layer, extra in QUERY_TERRITORIES.items():
        if layer not in out:
            continue
        for q in extra:
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
            "query_territories": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; fringe "
                    "and contradicted PUBLIC material is kept as a low-weight evidence object "
                    "and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "NRB gross foreign exchange reserves and import cover in months",
     "source": "Nepal Rastra Bank", "coverage": "1990s onward, monthly on the BS month",
     "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "revised once with the annual report", "licence": "free, public",
     "history_from": "2000-07", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("external_stress", "policy_proxy"),
     "how_to_fetch": "nrb.org.np Current Macroeconomic and Financial Situation, monthly PDF and "
                     "Excel; take the reserve table AND the import-cover line, and carry the BS "
                     "month as the stamp rather than translating it silently"},
    {"name": "NRB monthly remittance inflows by source country",
     "source": "Nepal Rastra Bank", "coverage": "2000s onward, monthly",
     "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "occasionally restated", "licence": "free, public",
     "history_from": "2005-07", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "USDKRW"),
     "mechanism_families": ("cross_border_flow", "labour_demand", "seasonality"),
     "how_to_fetch": "the same monthly report's external-sector tables; the BY-SOURCE-COUNTRY "
                     "split is the whole point and is in the annexes, not the headline"},
    {"name": "Department of Foreign Employment labour permits (new and renewed)",
     "source": "Department of Foreign Employment", "coverage": "2008 onward, monthly and annual",
     "frequency": "monthly", "publication_lag_days": 45.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2008-07", "pit_feasible": True,
     "assets": ("USDINR", "USDKRW", "USDSGD"),
     "mechanism_families": ("labour_demand", "lead_indicator"),
     "how_to_fetch": "dofe.gov.np permit statistics and the Foreign Employment Board reports; "
                     "THE PERMIT LEADS THE MONEY by three to nine months and the two series "
                     "must never be used interchangeably"},
    {"name": "Korea EPS quota and selection results for Nepali workers",
     "source": "Korea Employment Permit System / DoFE",
     "coverage": "2008 onward, per intake", "frequency": "annual and per-intake",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2008-01", "pit_feasible": True,
     "assets": ("USDKRW", "USDINR"),
     "mechanism_families": ("labour_demand", "administered_event"),
     "how_to_fetch": "eps.go.kr notices and the DoFE announcements; the quota is PUBLISHED AND "
                     "DATED, which makes it one of the cleanest administered labour-demand "
                     "events in the desk's whole book"},
    {"name": "Department of Customs monthly trade by commodity and by country",
     "source": "Department of Customs", "coverage": "2000s onward, monthly on the BS month",
     "frequency": "monthly", "publication_lag_days": 30.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2010-07", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "XBRUSD"),
     "mechanism_families": ("trade_flow", "administered_event"),
     "how_to_fetch": "customs.gov.np/en/monthlystats.html -- the monthly workbook carries "
                     "imports and exports by HS code and by country; the India share, the gold "
                     "line and the petroleum line are the three columns this pack uses"},
    {"name": "The 2022 luxury-import ban and the cash-margin controls, dated",
     "source": "Nepal Gazette, NRB circulars, the trade press",
     "coverage": "2021-12 to 2023-05", "frequency": "irregular, dated",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2021-12", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("capital_controls", "administered_event"),
     "how_to_fetch": "assemble from the gazette notices and the NRB circulars; IMPORT_CONTROLS "
                     "carries each row labelled GAZETTED or PRESS_REPORTED and the "
                     "press-reported rows may not carry a promoted cell"},
    {"name": "NOC fortnightly retail petroleum price notices",
     "source": "Nepal Oil Corporation", "coverage": "2010s onward, twice a month",
     "frequency": "fortnightly", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2014-01", "pit_feasible": False,
     "assets": ("XBRUSD", "XNGUSD"),
     "mechanism_families": ("administered_event", "pass_through"),
     "how_to_fetch": "noc.org.np price notices, published on the 1st and the 16th. THE PAGE "
                     "SHOWS TODAY'S PRICE AND KEEPS NO HISTORY, so the series is "
                     "pit_feasible=false until the archive layer's snapshots back it"},
    {"name": "NEA electricity generation, import and export to India",
     "source": "Nepal Electricity Authority", "coverage": "2010s onward, monthly and annual",
     "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "restated in the annual report", "licence": "free, public",
     "history_from": "2015-07", "pit_feasible": True,
     "assets": ("USDINR", "XBRUSD", "XNGUSD"),
     "mechanism_families": ("physical_flow", "seasonality"),
     "how_to_fetch": "nea.org.np annual report and the monthly bulletins; the SIGN of the net "
                     "flow reverses twice a year on the monsoon, which is the object"},
    {"name": "Department of Hydrology and Meteorology monsoon onset, withdrawal and rainfall",
     "source": "DHM", "coverage": "long run, daily and seasonal", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True,
     "assets": ("USDINR", "XBRUSD"),
     "mechanism_families": ("weather", "lead_indicator"),
     "how_to_fetch": "dhm.gov.np bulletins; run-of-river generation makes rainfall the upstream "
                     "input to the power-export series, and the monsoon onset date is published"},
    {"name": "National Statistics Office consumer price index",
     "source": "National Statistics Office / NRB", "coverage": "2000s onward, monthly",
     "frequency": "monthly", "publication_lag_days": 35.0, "revisions": "rebased periodically",
     "licence": "free, public", "history_from": "2005-07", "pit_feasible": True,
     "assets": ("USDINR",),
     "mechanism_families": ("imported_inflation",),
     "how_to_fetch": "nsonepal.gov.np price statistics and the NRB monthly report's price "
                     "tables; with an open border and a hard peg this is substantially India's "
                     "price level arriving with a lag"},
    {"name": "NRB policy rate, the interest-rate corridor and the margin-lending limits",
     "source": "Nepal Rastra Bank", "coverage": "2016 onward (the corridor was introduced then)",
     "frequency": "annual with quarterly reviews", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2016-07",
     "pit_feasible": True, "assets": ("USDINR",),
     "mechanism_families": ("policy_surprise", "domestic_credit"),
     "how_to_fetch": "nrb.org.np monetary policy documents and the unified directives; the "
                     "DIRECTED-CREDIT and loan-against-shares limits move the domestic market "
                     "more than the rate does and are in the directives, not the headline"},
    {"name": "NEPSE index, turnover and margin lending against shares",
     "source": "NEPSE / SEBON / NRB", "coverage": "2010s onward, daily index, monthly credit",
     "frequency": "daily (index) and monthly (credit)", "publication_lag_days": 1.0,
     "revisions": "never", "licence": "free, public", "history_from": "2012-07",
     "pit_feasible": True, "assets": ("USDINR",),
     "mechanism_families": ("domestic_liquidity",),
     "how_to_fetch": "nepalstock.com.np daily summaries and the NRB's credit tables. A CLOSED "
                     "POOL: no derivatives and essentially no foreign participation, so this is "
                     "a domestic liquidity observable and never an instrument"},
    {"name": "Nepal Tourism Board monthly arrivals by air, with the trekking seasons",
     "source": "Nepal Tourism Board / Department of Immigration",
     "coverage": "2000s onward, monthly", "frequency": "monthly",
     "publication_lag_days": 20.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True,
     "assets": ("USDINR",),
     "mechanism_families": ("seasonality", "cross_border_flow"),
     "how_to_fetch": "ntb.gov.np arrival statistics; the autumn (Oct-Nov) and spring (Mar-May) "
                     "windows are a small, cleanly dated FX inflow beside the remittance series"},
    {"name": "IMF Extended Credit Facility review dates and disbursements",
     "source": "IMF", "coverage": "2022-01 onward", "frequency": "per review",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2022-01", "pit_feasible": True,
     "assets": ("USDINR",),
     "mechanism_families": ("administered_event", "external_stress"),
     "how_to_fetch": "imf.org Nepal country page; UNLIKE A PRECAUTIONARY LINE THIS ONE "
                     "DISBURSES, so each review is a dated reserve event as well as a document"},
    {"name": "Nepal Gazette notices: import controls, quotas, duties and holiday declarations",
     "source": "Department of Printing / Nepal Law Commission",
     "coverage": "the full run, partly digitised", "frequency": "weekly and irregular",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("administered_event", "regime_break"),
     "how_to_fetch": "rajpatra.dop.gov.np and lawcommission.gov.np; the digitised run is "
                     "INCOMPLETE and the pack says so -- an undigitised notice is UNMEASURED, "
                     "not absent"},
    {"name": "NRB gold import quota for banks (kilograms per day)",
     "source": "Nepal Rastra Bank circulars", "coverage": "2015 onward, irregular and dated",
     "frequency": "irregular", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2015-07", "pit_feasible": True,
     "assets": ("XAUUSD", "USDINR"),
     "mechanism_families": ("administered_event", "capital_controls"),
     "how_to_fetch": "nrb.org.np circulars and the trade press; the quota is an ADMINISTERED "
                     "supply constraint on a metal, and the gap between it and demand is what "
                     "the border corridor into India carries"},
    {"name": "Nepal Clearing House and NRB digital payment volumes",
     "source": "NCHL / Nepal Rastra Bank", "coverage": "2018 onward, monthly",
     "frequency": "monthly", "publication_lag_days": 30.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2018-07", "pit_feasible": True,
     "assets": ("USDINR",),
     "mechanism_families": ("high_frequency_proxy", "domestic_activity"),
     "how_to_fetch": "nchl.com.np and the NRB payment-systems reports; a near-real-time "
                     "domestic activity proxy in an economy whose official statistics arrive "
                     "five weeks late on a different calendar"},
    {"name": "Large cardamom and orthodox tea export volumes and prices",
     "source": "Department of Customs, the Trade and Export Promotion Centre",
     "coverage": "2010s onward, monthly", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2012-07", "pit_feasible": True,
     "assets": ("USDINR",),
     "mechanism_families": ("trade_flow", "seasonality"),
     "how_to_fetch": "the customs monthly workbook by HS code plus the TEPC reports; Nepal is "
                     "the world's largest large-cardamom producer and almost the whole crop "
                     "goes to India, but there is NO exchange and no public price at a usable "
                     "frequency, which bounds what this row can ever support"},
)
# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Nepal Rastra Bank as the keeper of a hard peg",
     "holds": "the 1.60 NPR = 1 INR cross-rate, the foreign exchange reserves that back it, the "
              "policy rate and corridor, and an unusually active set of directed-credit and "
              "margin-lending limits",
     "forced_to": ("hold the Indian rupee cross-rate at 1.60, unbroken since 1993",
                   "publish reserves and the IMPORT COVER IN MONTHS every month",
                   "issue one annual Monetary Policy after the budget, with quarterly reviews",
                   "defend the reserve position rather than an inflation number, because "
                   "inflation is India's arriving through an open border"),
     "when": "the monthly report about five to six weeks after the BS month; the annual policy "
             "in the weeks after 1 Shrawan (mid-July)",
     "information": ("the reserve position and the banking system's liquidity in real time",
                     "the remittance inflow before it is published",
                     "the letters of credit being opened against imports"),
     "constraints": ("A HARD PEG REMOVES THE EXCHANGE RATE AS AN INSTRUMENT ENTIRELY: there is "
                     "nothing to devalue and no band to widen",
                     "an open border across which the Indian rupee circulates freely",
                     "an IMF Extended Credit Facility with reviews that disburse",
                     "a banking system whose deposit growth is remittance-driven"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the Reserve Bank of India by construction",
                        "the commercial banks at the standing facility",
                        "the IMF under the facility", "the importers who need foreign exchange"),
     "observables": ("the monthly reserve and import-cover series",
                     "the remittance inflow by source country",
                     "the policy rate and the unified directives",
                     "the treasury-bill cut-off"),
     "impact": "the reserve position is the only real state variable in this economy; when it "
               "fell toward six months of cover the government banned the importation of motor "
               "cars, which is what a peg defence looks like when there is no rate to move",
     "persistence": "the peg has held for more than thirty years; the reserve cycle runs in "
                    "multi-quarter waves",
     "falsifier": "the Nepali reserve and cover series carry no information about USDINR beyond "
                  "what the RBI's own weekly reserve supplement already carries, tested with "
                  "the Indian series as the benchmark the Nepali one must beat",
     "notes": "THE POINT OF THE PACK IS IN THE FALSIFIER: this actor is a second, independent "
              "observer of the same external pressure India is managing"},
    {"name": "The migrant worker and the remittance channel",
     "holds": "roughly a quarter of national income, earned in the Gulf, Malaysia, Korea and "
              "India and sent home monthly",
     "forced_to": ("obtain a labour permit from the Department of Foreign Employment before "
                   "departure, which is counted and published",
                   "remit through a formal channel or through hundi, and the spread between "
                   "them is the capital-control observable",
                   "send more at Dashain and Tihar, which is the single largest seasonal inflow "
                   "of the year and MOVES BY WEEKS because the festivals are lunar"),
     "when": "monthly, clustered at the festival block and at the Gulf pay cycle",
     "information": ("the destination labour market's real demand months before the permit "
                     "statistics show it",
                     "the hundi rate against the formal one"),
     "constraints": ("destination-country quotas, above all the published Korea EPS quota",
                     "recruitment costs and the debt taken to pay them",
                     "an exchange-control regime that makes hundi illegal and common"),
     "instruments": ("USDINR", "XAUUSD", "USDKRW"),
     "counterparties": ("the Gulf, Malaysian and Korean employers",
                        "the remittance companies and the banks",
                        "the hundi network"),
     "observables": ("the NRB's monthly remittance inflow BY SOURCE COUNTRY",
                     "the DoFE permit counts, new and renewed",
                     "the published Korea EPS quota and selection results",
                     "the hundi rate chatter"),
     "impact": "funds a structural trade deficit and therefore the whole reserve position; a "
               "Gulf labour-demand shock is a Nepali balance-of-payments event with a lag",
     "persistence": "the permit leads the money by three to nine months and the stock of "
                    "workers abroad turns over on a multi-year cycle",
     "falsifier": "the by-source-country remittance split adds nothing to a model of Gulf and "
                  "East Asian labour demand that already contains those countries' own "
                  "published employment and oil-revenue series",
     "notes": "THE INTERACTION THAT STOPS THIS PACK BEING TESTED ALONE: `sa`, `ae`, `my` and "
              "`kr` own the other end of this flow"},
    {"name": "The Department of Customs and the importer at the Indian border",
     "holds": "the record of everything that crosses, by commodity and by country, and the "
               "tariff schedule that prices it",
     "forced_to": ("publish monthly trade statistics by HS code and by country",
                   "apply whatever import ban, quota or cash-margin requirement is gazetted",
                   "clear almost everything through India, because the country is landlocked "
                   "and the transit rights are Indian"),
     "when": "monthly, on the BS month, about a month after the period",
     "information": ("the letters of credit being opened before the goods move",
                     "the real compliance rate on a ban"),
     "constraints": ("Indian transit rights and two Himalayan passes as the only alternatives",
                     "a gazetted tariff schedule that changes with the budget",
                     "the physical throughput of Birgunj and Biratnagar"),
     "instruments": ("USDINR", "XAUUSD", "XBRUSD"),
     "counterparties": ("the Indian exporter and the Kolkata and Visakhapatnam ports",
                        "the Nepali importer and the banks financing them",
                        "the Chinese side at Rasuwagadhi and Tatopani"),
     "observables": ("the monthly trade workbook by country and commodity",
                     "the India share of imports", "the gold and petroleum lines",
                     "the border-point clearance volumes"),
     "impact": "the trade deficit this series measures is what the remittance inflow funds and "
               "what the reserve position absorbs; it is the middle term of the whole pack",
     "persistence": "the India share is structural and has not fallen materially in decades",
     "falsifier": "the Nepali import series carries no information about Indian export "
                  "conditions beyond India's own published trade data, measured on the mirror "
                  "series",
     "notes": "A LANDLOCKED ECONOMY'S CUSTOMS DATA IS ITS NEIGHBOUR'S EXPORT DATA SEEN FROM THE "
              "OTHER SIDE, which is precisely the third-party read this pack is built on"},
    {"name": "The Reserve Bank of India as the upstream authority",
     "holds": "the Indian rupee's external value, which by the peg is also the Nepalese rupee's",
     "forced_to": ("manage USDINR with the most active FX-smoothing book in EM Asia",
                   "publish reserves weekly, as of the preceding Friday"),
     "when": "the weekly statistical supplement and the bimonthly policy; the FX book is "
             "continuous",
     "information": ("its own intervention book in real time",
                     "the Indian current account before it is published"),
     "constraints": ("a large and open capital account",
                     "an inflation-targeting mandate that the smoothing book sits beside"),
     "instruments": ("USDINR",),
     "counterparties": ("the Indian banks and the offshore NDF market",
                        "Nepal Rastra Bank as a passive taker of the result"),
     "observables": ("USDINR itself", "the weekly reserve supplement",
                     "the bimonthly policy and its FX commentary"),
     "impact": "EVERY MOVE PASSES THROUGH TO THE NPR ONE FOR ONE. Nepal takes the result and "
               "has no instrument with which to respond",
     "persistence": "policy regimes run for governor terms; the smoothing behaviour is "
                    "structural",
     "falsifier": "USDINR's path is unaffected by anything Nepali, which is the honest prior in "
                  "one direction -- the pack's claim runs the OTHER way, that Nepali data "
                  "INFORMS about Indian conditions rather than moving them",
     "notes": "DECLARED AS A FOREIGN ACTOR ON PURPOSE. The `ind` pack owns this mechanism; "
              "naming it here is how the peg is carried without being duplicated"},
    {"name": "Nepal Oil Corporation as a state monopoly with a foreign supplier",
     "holds": "every litre of petroleum in the country, bought from Indian Oil Corporation and "
              "sold at an administered retail price",
     "forced_to": ("accept a transfer price revised every fortnight, on the 1st and the 16th",
                   "publish a retail price notice each time",
                   "absorb or pass through the difference under political pressure"),
     "when": "the 1st and the 16th of each month, effective from Kathmandu midnight",
     "information": ("the next fortnight's transfer price before it is published",
                     "its own accumulated loss or profit on the price it is holding"),
     "constraints": ("a single foreign supplier with no alternative",
                     "a retail price that is politically set and periodically frozen",
                     "storage measured in days"),
     "instruments": ("XBRUSD", "XNGUSD"),
     "counterparties": ("Indian Oil Corporation", "the Nepali consumer",
                        "the Ministry of Finance, which owns the loss"),
     "observables": ("the fortnightly price notices",
                     "the customs petroleum import line",
                     "NOC's own published accounts"),
     "impact": "the international product price becomes the Nepali price level through an "
               "ADMINISTERED STEP FUNCTION on a published clock, which is a pass-through with a "
               "calendar rather than a correlation",
     "persistence": "the fortnightly clock has run for years; the freezes are episodic and dated",
     "falsifier": "the pass-through on a revision date is indistinguishable from the "
                  "pass-through on the intervening days once the crude move is controlled for, "
                  "which would mean the administered clock carries no information",
     "notes": "NOC's price page keeps no history, so the series is pit_feasible=false until the "
              "archive layer backs it, and the dataset row says exactly that"},
    {"name": "The Nepal Electricity Authority and the monsoon",
     "holds": "the national grid, the Indian interconnections and a generation fleet that is "
              "overwhelmingly run-of-river",
     "forced_to": ("export surplus generation to India in the wet season and import in the dry "
                   "one, reversing the sign of the flow twice a year",
                   "operate inside the long-term power trade agreement signed with India in "
                   "January 2024",
                   "publish generation, import and export monthly and annually"),
     "when": "the reversal follows the monsoon onset and withdrawal, roughly June and October",
     "information": ("the reservoir and river-flow position before the bulletins publish it",
                     "the Indian day-ahead price it is selling into"),
     "constraints": ("RUN-OF-RIVER MEANS THE EXPORT IS LITERALLY RAINFALL",
                     "transmission capacity at the interconnections",
                     "Indian approval for each export arrangement"),
     "instruments": ("USDINR", "XBRUSD", "XNGUSD"),
     "counterparties": ("the Indian grid and the power exchange",
                        "the Nepali consumer", "the independent power producers"),
     "observables": ("NEA monthly generation, import and export",
                     "the DHM monsoon onset and rainfall bulletins",
                     "the customs electricity trade line"),
     "impact": "a genuine physical cross-border energy flow whose DIRECTION is a function of "
               "rainfall; it substitutes at the margin for Indian thermal generation",
     "persistence": "the seasonal pattern is annual and the capacity trend is multi-year",
     "falsifier": "the Nepali export volume carries no information about Indian power or "
                  "thermal-fuel conditions beyond what Indian generation data already carries",
     "notes": "the one mechanism in this pack that is PHYSICS rather than policy, which makes "
              "it the most falsifiable thing here"},
    {"name": "The Ministry of Finance and the mid-July fiscal boundary",
     "holds": "the budget, the customs-duty schedule and the capital-expenditure programme",
     "forced_to": ("present the budget on Jestha 15 (about 29 May), seven weeks before the "
                   "fiscal year it funds opens on 1 Shrawan",
                   "publish the Economic Survey beside it",
                   "spend a capital budget that historically clears late in the year"),
     "when": "the budget in late May; the fiscal year turning in mid-July on the BS calendar",
     "information": ("the duty schedule before it is announced",
                     "the real capital-spending position"),
     "constraints": ("a revenue base dominated by import duties, which the import controls "
                     "themselves reduce",
                     "a capital budget that is chronically under-executed",
                     "an IMF facility with structural benchmarks attached"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the NRB", "the importers who pay the duties", "the IMF"),
     "observables": ("the budget speech and the duty schedule",
                     "the Economic Survey", "monthly revenue collection"),
     "impact": "AN IMPORT-DUTY-FUNDED STATE THAT BANS IMPORTS TO DEFEND ITS RESERVES IS CUTTING "
               "ITS OWN REVENUE, which is the tension that dates the end of every control "
               "episode as reliably as the reserve recovery does",
     "persistence": "the fiscal year is annual and the boundary is derivable",
     "falsifier": "the budget date carries no market information beyond the duty schedule "
                  "published with it, tested against the customs series",
     "notes": "the fiscal boundary is DERIVED by `fiscal_year_bounds` and not typed, because the "
              "BS-Gregorian mapping is a published astronomical fact"},
    {"name": "The Nepali importer under a gazetted control",
     "holds": "the letters of credit, the cash margins and the inventory decision",
     "forced_to": ("stop importing a banned category on the gazette date",
                   "post whatever cash margin the NRB circular requires",
                   "front-run an anticipated ban, which is what makes the pre-announcement "
                   "window a real object"),
     "when": "the dated control episodes: from 2021-12 through 2022-12 and the withdrawal into "
             "2023",
     "information": ("the impending control before it is gazetted, through the source graph",
                     "the real inventory position"),
     "constraints": ("a gazette notice with immediate effect",
                     "financing costs on a cash margin",
                     "a border through which everything must still pass"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the Indian exporter", "the banks financing the letters of credit",
                        "the customs department"),
     "observables": ("the customs monthly series by commodity",
                     "the gazette notices", "the trade press's pre-ban reporting"),
     "impact": "a blunt, dated, measurable administered event on the trade account and, through "
               "it, on the reserve position the peg depends on",
     "persistence": "the 2022 episode ran eight months; the effect on the trade account was "
                    "immediate and the effect on cover took two quarters",
     "falsifier": "the banned categories' import collapse is matched by an equal collapse in "
                  "unbanned categories over the same months, which would make it demand rather "
                  "than the control",
     "notes": "IMPORT_CONTROLS labels each date GAZETTED or PRESS_REPORTED, and a "
              "press-reported date may generate a hypothesis and may never promote a cell"},
    {"name": "The commercial banks and the remittance-driven deposit cycle",
     "holds": "a deposit base whose growth is remittance-driven and a credit book the NRB "
              "directs by sector",
     "forced_to": ("meet the cash reserve and statutory liquidity ratios",
                   "respect the directed-credit floors and the loan-against-shares cap",
                   "fund a credit cycle from a deposit inflow they do not control"),
     "when": "continuously; the association publishes the deposit-rate agreement monthly and "
             "the NRB aggregates it in the monthly report",
     "information": ("the liquidity position before the NRB publishes it",
                     "the remittance inflow as it lands in the deposit accounts"),
     "constraints": ("a closed capital account with no offshore funding",
                     "an NRB that directs credit by sector and caps margin lending",
                     "a festival-season liquidity swing that is entirely seasonal"),
     "instruments": ("USDINR",),
     "counterparties": ("the depositors", "the NRB at the standing facility",
                        "the NEPSE margin borrower"),
     "observables": ("the bankers' association deposit-rate agreement",
                     "the interbank rate", "the NRB's credit and deposit tables",
                     "the loan-against-shares outstanding"),
     "impact": "the domestic transmission channel: a remittance surge becomes deposits becomes "
               "credit becomes, among other things, NEPSE margin lending",
     "persistence": "the liquidity cycle is seasonal on the festival block and structural on "
                    "the remittance trend",
     "falsifier": "the interbank rate's moves are explained by the seasonal deposit cycle alone, "
                  "with no residual attributable to policy -- which is the honest prior and "
                  "makes NP-H a measured refusal if it holds",
     "notes": "the interbank rate here is a LIQUIDITY fact first and a policy signal a distant "
              "second, and the pack states that rather than running a policy event study on it"},
    {"name": "The gold importer and the border corridor",
     "holds": "an NRB-set import quota in kilograms per day, and a demand that peaks at the "
              "festival block and at the wedding season",
     "forced_to": ("import within the quota the NRB sets by circular",
                   "sell into a market whose demand is festival-dated rather than "
                   "price-elastic"),
     "when": "the quota changes by dated circular; demand peaks at Dashain, Tihar and the "
             "wedding months",
     "information": ("the real demand at the quota's edge",
                     "the premium the corridor into India is paying"),
     "constraints": ("an administered quota that is routinely below demand",
                     "an open border with a much larger neighbour whose own duty regime changes",
                     "customs enforcement at the passes and the airport"),
     "instruments": ("XAUUSD", "USDINR"),
     "counterparties": ("the Nepali jeweller and household",
                        "the Indian market across the border", "the banks holding the quota"),
     "observables": ("the NRB quota circulars",
                     "the customs gold import line in kilograms",
                     "the seizure reports", "the domestic gold price against the world price"),
     "impact": "a real, administered, seasonal metal demand with a smuggling corridor attached; "
               "DECLARED MARGINAL for the world price and genuine for the direction",
     "persistence": "the quota is adjusted every few quarters; the seasonality is annual",
     "falsifier": "the Nepali gold import series carries no information about XAUUSD beyond "
                  "Indian gold demand and the Indian import-duty regime, which is the honest "
                  "prior and is what the `ind` interaction tests",
     "notes": "the claim is about a CHANNEL being open or shut, never about Nepal moving the "
              "London fix"},
    {"name": "NEPSE, SEBON and the domestic retail investor",
     "holds": "a closed equity market with no derivatives, essentially no foreign participation "
              "and a retail base that borrows against shares",
     "forced_to": ("trade Sunday to Thursday only",
                   "respect per-security and index circuit limits",
                   "operate inside the NRB's cap on loans against shares"),
     "when": "11:00-15:00 Kathmandu, Sunday to Thursday, closed for up to a fortnight at Dashain "
             "and Tihar",
     "information": ("the margin-lending position before the monthly credit tables publish it",
                     "the broker order book, which is published to nobody outside the exchange"),
     "constraints": ("NO DERIVATIVES OF ANY KIND -- no options, no futures, no expiry clock",
                     "a closed capital account that keeps foreign portfolio money out",
                     "a policy cap on margin credit that is the real driver"),
     "instruments": ("USDINR",),
     "counterparties": ("the domestic retail investor and the brokers",
                        "the banks lending against shares", "the NRB as the credit regulator"),
     "observables": ("the index and turnover", "loans against shares outstanding",
                     "the SEBON directives"),
     "impact": "NONE OUTSIDE NEPAL, and saying so is the point: a closed pool with no foreign "
               "participation cannot transmit, so this actor is a domestic liquidity observable "
               "and its single names are event lane under the two-lane order",
     "persistence": "the closure is structural and has not changed materially",
     "falsifier": "the NEPSE index carries information about anything executable -- the honest "
                  "prior is that it does not, and this actor exists so a miner does not reach "
                  "for it",
     "notes": "the pack's null actor on the equity side, the way the AMCM is Macau's on the "
              "monetary side"},
    {"name": "The Nepal Calendar Determination Committee",
     "holds": "the national patro from which the government's public-holiday list is drawn, and "
              "therefore the dates of Dashain, Tihar, Shivaratri, Holi and Buddha Jayanti",
     "forced_to": ("fix and publish the patro for each Bikram Sambat year",
                   "settle the festival dates that no weekday rule produces"),
     "when": "annually, ahead of the BS year; the government's holiday list follows in the "
             "Nepal Gazette",
     "information": ("the astronomical calculation before it is published",
                     "which of two candidate days a festival will fall on in a contested year"),
     "constraints": ("a lunisolar calculation that moves Dashain by up to three weeks between "
                     "adjacent years",
                     "a government holiday list that must be gazetted before the year begins"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the Government of Nepal", "the banks and NEPSE",
                        "every employer in the country"),
     "observables": ("the published patro", "the gazetted public-holiday list",
                     "the actual closure of the banks and the customs points"),
     "impact": "IT SETS WHEN THE COUNTRY STOPS. Vijaya Dashami fell on 12 October in 2024 and "
               "on 2 October in 2025 -- ten days apart -- and a study that assumes a fixed "
               "October window is measuring two different fortnights",
     "persistence": "annual, and the drift is the whole point",
     "falsifier": "the festival block's effect on remittances, gold purchases and market "
                  "activity is a calendar-month effect rather than a festival effect, tested by "
                  "aligning on the FESTIVAL date instead of the month",
     "notes": "the authority named in HOLIDAY_STATUSES; a PROJECTED row is this pack's own "
              "computation awaiting that patro and may be a day off"},
    {"name": "The Indian-border trader and the open-border arbitrage",
     "holds": "the practical consequence of a fixed cross-rate across a border people walk "
              "across: goods, cash and gold move to whichever side is cheaper that week",
     "forced_to": ("price against the Indian market continuously, because the customer can "
                   "simply cross",
                   "accept Indian rupees, which circulate freely on the Nepali side"),
     "when": "continuously; sharply at Indian duty changes and at Nepali control episodes",
     "information": ("the real price differential and the enforcement intensity that week",
                     "which side of the border the week's goods are actually moving toward"),
     "constraints": ("an 1,800-kilometre open border",
                     "customs enforcement that is episodic by construction",
                     "a fixed cross-rate that removes the exchange-rate part of the arbitrage"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the Indian wholesale market", "the Nepali retailer",
                        "the customs and police on both sides"),
     "observables": ("the gap between Nepali and Indian retail prices",
                     "the seizure reports", "the customs series' unexplained swings"),
     "impact": "THE PEG IS ENFORCED BY GEOGRAPHY, not only by policy: an open border with a "
               "fixed cross-rate means no parallel-rate premium of consequence can exist "
               "against the INR, which is why the hundi spread is about the DOLLAR leg and the "
               "channel, not about the rupee",
     "persistence": "structural and permanent",
     "falsifier": "a measurable and persistent NPR/INR premium exists in the informal market, "
                  "which would mean the peg is not in fact enforced by the border",
     "notes": "this actor is why NP-B's null is so strong and why the pack's edge runs through "
              "INFORMATION rather than through price"},
    {"name": "The IMF under an Extended Credit Facility that disburses",
     "holds": "a lending arrangement approved in January 2022 with reviews, disbursements and "
              "structural benchmarks attached",
     "forced_to": ("publish a staff report at each review",
                   "disburse on completion, which is a dated reserve event"),
     "when": "per review, on the facility's own schedule",
     "information": ("the reserve and fiscal position before publication",
                     "the authorities' own commitments"),
     "constraints": ("a programme whose benchmarks touch bank supervision and the fiscal "
                     "accounts",
                     "reviews that can be delayed, which is itself information",
                     "a member whose peg it can advise on and cannot change"),
     "instruments": ("USDINR",),
     "counterparties": ("Nepal Rastra Bank", "the Ministry of Finance",
                        "the World Bank and ADB programmes alongside it"),
     "observables": ("the review completions and the disbursement amounts",
                     "the staff reports", "the reserve series' step at disbursement"),
     "impact": "UNLIKE A PRECAUTIONARY LINE, THIS ONE MOVES MONEY: a completed review is a "
               "measurable step in the reserve series and a dated event in the peg's defence",
     "persistence": "the arrangement runs multiple years with reviews roughly half-yearly",
     "falsifier": "the reserve series shows no step at disbursement dates beyond the monthly "
                  "noise, which would mean the amounts are too small to matter",
     "notes": "the contrast with Morocco's precautionary facility is real and is why the two "
              "packs treat an IMF calendar differently"},
)
# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "NP-A", "title": "The 1.6 peg as a lawful third-party read on Indian external "
                            "conditions",
     "objects": ("the NRB's monthly gross reserves and import cover in months",
                 "the balance-of-payments line in the same report",
                 "the implied USD/NPR computed from USDINR by `usdnpr_from_usdinr`",
                 "the RBI's own weekly reserve supplement as the benchmark to beat"),
     "conditions": ("the import-cover bucket, with seven months as the historical stress line",
                    "whether the Nepali and Indian reserve series are diverging",
                    "the era: pre-2021 comfort, the 2021-22 squeeze, the post-2023 recovery"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the RBI's own weekly reserve supplement over the same window, which is the "
                  "benchmark the Nepali series must ADD to rather than merely echo",
                  "Bangladesh's and Sri Lanka's reserve series over the same months, the "
                  "sibling South Asian squeezes, separating 'the region' from 'India'",
                  "a block-permuted Nepali series as the null for a slow-moving state"),
     "notes": "THE PACK'S PRIMARY EDGE AND ITS HARDEST TEST. The claim is not that Nepal moves "
              "USDINR -- it obviously does not -- but that a second, independent, differently "
              "incentivised observer of the same external pressure carries information the "
              "Indian series does not. That is falsifiable and the control says how"},
    {"id": "NP-B", "title": "The peg's arithmetic and the absence of a Nepali FX price",
     "objects": ("the 1.60 cross-rate, unbroken since 1993-02-01",
                 "the NRB's daily reference rate, which is Indian arithmetic",
                 "the open border across which the Indian rupee circulates freely",
                 "the hundi spread, which is about the DOLLAR leg and not the rupee"),
     "conditions": ("whether a hundi premium is being reported at all",
                    "the exchange-control intensity of the period",
                    "the USDINR volatility regime the peg transmits"),
     "instruments": ("USDINR",),
     "controls": ("the `ind` pack's own USDINR study over the identical window -- a Nepali "
                  "claim must beat India's own measurement of its own rate to be Nepal's",
                  "a block-permuted USDINR series as the null",
                  "the same state in periods with no exchange-control episode"),
     "notes": "THE HONEST PRIOR IS THAT THIS DOMAIN FINDS NOTHING ON PRICE, and it exists to "
              "measure that rather than assume it. The peg is enforced by an 1,800-kilometre "
              "open border as much as by policy, so no NPR/INR premium of consequence can form"},
    {"id": "NP-C", "title": "Remittances by source country as a labour-demand gauge",
     "objects": ("the NRB's monthly remittance inflow split by where it was earned",
                 "the DoFE labour-permit counts, new and renewed, which LEAD the money",
                 "the published Korea EPS quota and selection results",
                 "the Dashain and Tihar inflow peak, which moves by weeks"),
     "conditions": ("the source-country mix and its change",
                    "whether the window contains the festival block",
                    "the permit-to-remittance lag regime, three to nine months"),
     "instruments": ("USDINR", "XAUUSD", "USDKRW"),
     "controls": ("the destination countries' own published employment, oil-revenue and "
                  "construction series, which is the benchmark the Nepali split must beat",
                  "the Bangladeshi and Sri Lankan remittance series over the same months, the "
                  "sibling flows out of the same Gulf labour market",
                  "a festival-aligned control, so the seasonal peak is not read as a trend"),
     "notes": "A QUARTER OF GDP, PUBLISHED MONTHLY, SPLIT BY SOURCE. This is the interaction "
              "that stops the pack being tested alone: `sa`, `ae`, `my` and `kr` own the other "
              "end of every one of these flows"},
    {"id": "NP-D", "title": "The 2022 import ban and the cash-margin controls",
     "objects": ("the dated gazette notices from 2021-12 through 2022-12",
                 "the customs series by banned and unbanned category",
                 "the reserve and import-cover series through the episode",
                 "the revenue cost to a state funded by import duties"),
     "conditions": ("which side of a gazette date the window sits on",
                    "the import-cover level that motivated the control",
                    "whether the row is GAZETTED or only PRESS_REPORTED"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the UNBANNED categories over the same months, which separates the control "
                  "from a demand collapse",
                  "Sri Lanka's and Pakistan's contemporaneous import restrictions, the sibling "
                  "South Asian episodes",
                  "the same months in the years before and after the episode"),
     "notes": "AN ADMINISTERED EVENT WITH DATES THIS CLEAN IS RARE. A government that forbids "
              "the importation of motor cars to defend its reserves has run an experiment, and "
              "the built-in tension -- an import-duty-funded state cutting its own revenue -- "
              "is what dates the end of the episode"},
    {"id": "NP-E", "title": "Hydropower export to India on the monsoon clock",
     "objects": ("NEA monthly generation, import and export",
                 "the sign reversal of the net flow, twice a year",
                 "the 2024 long-term power trade agreement's ten-year frame",
                 "the DHM monsoon onset and withdrawal dates"),
     "conditions": ("the season: wet-season export or dry-season import",
                    "the rainfall departure from normal",
                    "whether the window contains a monsoon onset or withdrawal date"),
     "instruments": ("USDINR", "XBRUSD", "XNGUSD"),
     "controls": ("Indian hydro generation over the same months, the upstream control that "
                  "separates 'the monsoon' from 'Nepal'",
                  "the same seasons in years before the export arrangements existed",
                  "a randomised-date null on the onset and withdrawal windows"),
     "notes": "THE ONE MECHANISM HERE THAT IS PHYSICS RATHER THAN POLICY, and therefore the "
              "most falsifiable: run-of-river generation makes the export capacity literally a "
              "function of rainfall and the direction of the flow reverses on a published date"},
    {"id": "NP-F", "title": "The fortnightly IOC-to-NOC petroleum pass-through",
     "objects": ("the revision dates, the 1st and the 16th, computed by `noc_revision_days`",
                 "the NOC retail price notices",
                 "the customs petroleum import line",
                 "the episodes in which the price was politically frozen"),
     "conditions": ("the size of the international product move since the last revision",
                    "whether the price was frozen in that fortnight",
                    "the direction, because a cut and a rise are politically asymmetric"),
     "instruments": ("XBRUSD", "XNGUSD"),
     "controls": ("the intervening non-revision days, which is the placebo that says whether "
                  "the administered clock carries anything at all",
                  "Indian retail fuel prices over the same fortnights, the upstream control",
                  "fortnights with no revision announced"),
     "notes": "AN ADMINISTERED STEP FUNCTION ON A PUBLISHED CLOCK. NOC's price page keeps no "
              "history, so the series is pit_feasible=false until the archive layer backs it "
              "and the dataset row says so"},
    {"id": "NP-G", "title": "The Bikram Sambat calendar, the one-day weekend and the "
                            "fortnight-long festival shutdown",
     "objects": ("the fiscal-year boundary at 1 Shrawan, derived by `fiscal_year_bounds`",
                 "the Dashain and Tihar block, which moves by weeks and shuts the economy",
                 "the SATURDAY-ONLY national weekend against NEPSE's Friday-and-Saturday one",
                 "the 45-minute UTC offset that puts every local hour on a quarter hour"),
     "conditions": ("whether the window falls inside the festival shutdown",
                    "whether it straddles the mid-July fiscal boundary",
                    "the weekday, with Sunday a full trading day and Saturday the only closure"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the same calendar weeks in years when the festival fell elsewhere, which is "
                  "the only way to tell a festival effect from an October effect",
                  "the Indian festival calendar, which overlaps but is not identical",
                  "matched weekdays outside the block"),
     "notes": "THE MOST COMMON WAY THIS JURISDICTION IS GOT WRONG is assuming a Saturday-Sunday "
              "weekend, which mislabels every Sunday in the sample; the second is assuming a "
              "fixed October festival window, which was 12 October in 2024 and 2 October in 2025"},
    {"id": "NP-H", "title": "The banking liquidity cycle and the NRB's directed credit",
     "objects": ("the interbank rate and the standing-facility use",
                 "the deposit-rate agreement the bankers' association publishes",
                 "the loan-against-shares cap and the directed-credit floors",
                 "the remittance inflow that drives deposit growth"),
     "conditions": ("the position in the festival deposit cycle",
                    "whether a directive changed the margin-lending cap in the window",
                    "the remittance trend"),
     "instruments": ("USDINR",),
     "controls": ("the seasonal deposit cycle alone as the benchmark any policy claim must "
                  "beat -- the honest prior is that it explains the whole of it",
                  "months with no directive change, as the null",
                  "the Indian interbank rate over the same months"),
     "notes": "THE INTERBANK RATE HERE IS A LIQUIDITY FACT FIRST. A policy event study on it is "
              "measuring the festival calendar unless the seasonal control is carried, and this "
              "domain is a measured refusal if the seasonal benchmark wins"},
    {"id": "NP-I", "title": "Gold: the NRB quota, the festival demand and the border corridor",
     "objects": ("the NRB's gold import quota in kilograms per day, set by dated circular",
                 "the customs gold import line",
                 "the festival and wedding demand peaks",
                 "the domestic price against the world price, and the seizure reports"),
     "conditions": ("whether the quota changed in the window",
                    "whether the window contains a festival block",
                    "the Indian import-duty regime, which sets the corridor's economics"),
     "instruments": ("XAUUSD", "USDINR"),
     "controls": ("Indian gold demand and the Indian import-duty dates over the same months, "
                  "which separates 'the subcontinent bought gold' from 'Nepal did'",
                  "quarters with no quota change",
                  "the festival-aligned control rather than the calendar month"),
     "notes": "DECLARED MARGINAL FOR THE WORLD PRICE AND GENUINE FOR THE DIRECTION. The claim "
              "is about an administered channel being open or shut, and the 2024 Indian duty "
              "cut is the natural experiment that tests it"},
    {"id": "NP-J", "title": "The landlocked transit constraint and the border points",
     "objects": ("the customs points at Birgunj, Biratnagar and Bhairahawa",
                 "the trans-Himalayan crossings at Rasuwagadhi/Kerung and Tatopani",
                 "the Indian transit corridor to Kolkata and Visakhapatnam",
                 "the 2015-16 border blockade as the demonstration"),
     "conditions": ("whether a border point was closed or congested in the window",
                    "the China-route share, which is small and politically salient",
                    "the era, because the blockade is a boundary a pooled study cannot cross"),
     "instruments": ("USDINR", "USDCNH"),
     "controls": ("the Indian export series over the same months, the mirror of the same flow",
                  "the months before and after a closure, matched on season",
                  "the unaffected border points as the within-country control"),
     "notes": "A LANDLOCKED ECONOMY'S PHYSICAL PLANE IS ITS TRANSIT RIGHTS, and the 2015-16 "
              "blockade is the dated proof that a political event at the border is a supply "
              "shock with a measurable price"},
    {"id": "NP-K", "title": "Imported inflation across an open border under a hard peg",
     "objects": ("the NSO consumer price index and its food weight",
                 "the Indian price level upstream of it",
                 "the fuel price step, which enters through NP-F's administered clock",
                 "the pass-through lag the NRB's own working papers estimate"),
     "conditions": ("the Indian CPI and WPI trend",
                    "whether a fuel revision fell in the window",
                    "the harvest and the monsoon outcome"),
     "instruments": ("USDINR", "XBRUSD"),
     "controls": ("the Indian CPI over the same months, which is the benchmark this series must "
                  "add to rather than echo",
                  "the Bangladeshi CPI, the sibling South Asian importer without the peg",
                  "months with no fuel revision"),
     "notes": "A TRANSFER TEST, NOT A DOMESTIC ONE. With a hard peg and an open border the "
              "Nepali price level is substantially India's arriving with a lag, and the domain "
              "exists to measure the LAG rather than to claim a Nepali price mechanism"},
    {"id": "NP-L", "title": "The mid-July fiscal boundary, the budget and the annual Monetary "
                            "Policy",
     "objects": ("the budget presented around Jestha 15 (about 29 May)",
                 "the fiscal year opening on 1 Shrawan, derived not typed",
                 "the annual Monetary Policy issued in the weeks after it",
                 "the customs-duty schedule that changes with the budget"),
     "conditions": ("whether the window straddles the fiscal boundary",
                    "whether a duty change was announced",
                    "the capital-spending position, which clears late by construction"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the same calendar weeks in the years the boundary fell a day either side, "
                  "which is what makes the BS derivation worth doing",
                  "the Indian budget date, a different boundary in the same neighbourhood",
                  "matched weeks with no fiscal event"),
     "notes": "THE BOUNDARY IS DERIVED BY `fiscal_year_bounds` FROM A PUBLISHED ASTRONOMICAL "
              "MAPPING, which is why this domain is a calendar mechanism and not a typed table"},
    {"id": "NP-M", "title": "The IMF facility that disburses, and the external programme clock",
     "objects": ("the Extended Credit Facility approved in January 2022",
                 "the review completions and the disbursement amounts",
                 "the step they produce in the reserve series",
                 "the structural benchmarks touching bank supervision and the accounts"),
     "conditions": ("whether the window contains a review completion",
                    "the reserve position going into it",
                    "whether the review was delayed, which is itself information"),
     "instruments": ("USDINR",),
     "controls": ("the reserve series' own monthly noise, which the step must exceed",
                  "the Sri Lankan and Pakistani programme calendars, the sibling South Asian "
                  "arrangements",
                  "months with no review"),
     "notes": "THE CONTRAST WITH A PRECAUTIONARY LINE IS THE POINT: this facility moves money, "
              "so a completed review is a dated reserve event and not only a document"},
    {"id": "NP-N", "title": "The closed domestic pool: NEPSE, margin credit and why it cannot "
                            "transmit",
     "objects": ("the NEPSE index and turnover",
                 "loans against shares outstanding and the NRB's cap on them",
                 "the absence of any derivatives market at all",
                 "the absence of foreign portfolio participation"),
     "conditions": ("whether the margin cap changed in the window",
                    "the domestic liquidity position",
                    "whether the window falls inside the festival shutdown"),
     "instruments": ("USDINR",),
     "controls": ("the domestic deposit and credit cycle, which is the benchmark any NEPSE "
                  "claim must beat",
                  "the Indian equity market over the same days, as the external null",
                  "the same windows with no directive change"),
     "notes": "A DOMAIN WHOSE EXPECTED ANSWER IS NO. It exists so a miner does not reach for "
              "the NEPSE index as if it were tradable, and so the single names in the Nepali "
              "market press stay firmly in the event lane where the two-lane order puts them"},
)

# --------------------------------------------------------------------------- cells
#: WHAT EACH DOMAIN MINTS. The horizon and mechanism family a cell inherits from its domain, so
#: a cell is never a cartesian product of nothing: every row is one real condition this pack's
#: own data plane can evaluate against one symbol the box can actually trade.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "NP-A": ("external_stress", "1 to 3 months"),
    "NP-B": ("band_state", "1 to 20 sessions"),
    "NP-C": ("labour_demand", "1 to 2 quarters"),
    "NP-D": ("capital_controls", "1 to 2 quarters"),
    "NP-E": ("physical_flow", "1 to 3 months"),
    "NP-F": ("administered_event", "0 to 5 sessions"),
    "NP-G": ("calendar_event", "0 to 10 sessions"),
    "NP-H": ("domestic_liquidity", "1 to 3 months"),
    "NP-I": ("administered_event", "1 to 3 months"),
    "NP-J": ("physical_flow", "1 to 2 quarters"),
    "NP-K": ("imported_inflation", "1 to 3 months"),
    "NP-L": ("calendar_event", "0 to 10 sessions"),
    "NP-M": ("administered_event", "0 to 10 sessions"),
    "NP-N": ("domestic_liquidity", "1 to 3 months"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS, for the one gauntlet.

    The cross product of each domain's own conditions with each domain's own EXECUTABLE
    instruments. It is a product and not a blow-up because both factors are already the pack's
    measured claims: a condition is a state this pack's data plane can evaluate, and an
    instrument is a symbol the broker registry carries.
    """
    execs = set(EXECUTABLE_INSTRUMENTS)
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon = DOMAIN_CELL_SPEC.get(did, ("mechanism", "1 to 10 sessions"))
        controls = tuple(dom["controls"])
        for symbol in dom["instruments"]:
            if symbol not in execs:
                continue
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{did}:{symbol}:C{i + 1}",
                    "domain": did, "symbol": symbol, "condition": condition,
                    "mechanism_family": family, "horizon": horizon,
                    "control": controls[i % len(controls)],
                    "why": str(dom["title"]),
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()

# --------------------------------------------------------------------------- interactions
#: HOW THIS COUNTRY IS NOT TESTED ALONE. Each row names another pack, the shared mechanism, the
#: observable that carries it and the executable targets.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "ind",
     "mechanism": "THE HARD PEG. 1.60 NPR = 1 INR since 1993, unbroken, with the Indian rupee "
                  "circulating freely across an 1,800-kilometre open border. Nepal has no "
                  "independent external price, which is exactly why its published reserve, "
                  "import-cover and remittance series are an independent third-party "
                  "measurement of the SAME external pressure India is managing -- produced by a "
                  "different institution, on a different calendar, with no reason to manage the "
                  "Indian narrative. The `ind` pack owns USDINR and the RBI's smoothing book; "
                  "this pack reads them and adds a second observer",
     "observable": "the NRB's monthly reserves and import cover against the RBI's weekly "
                   "reserve supplement, and the Nepali customs India-share against India's own "
                   "export data",
     "targets": ("USDINR", "XAUUSD"),
     "control": "the RBI's own series over the identical window -- the Nepali number must ADD "
                "to it, not echo it, and if it only echoes then this interaction is a measured "
                "refusal"},
    {"with": "sa",
     "mechanism": "Saudi Arabia is one of the two largest destinations for Nepali labour, and "
                  "the NRB publishes the remittance inflow BY SOURCE COUNTRY monthly. So the "
                  "Saudi construction and oil-revenue cycle arrives in Nepali data as a "
                  "published monthly number -- a read on Gulf labour demand from the receiving "
                  "end, which nobody triangulates",
     "observable": "the Saudi line of the NRB's remittance split and the DoFE permit counts to "
                   "Saudi Arabia, against Saudi non-oil activity and project awards",
     "targets": ("XBRUSD", "USDINR"),
     "control": "the Bangladeshi and Indian remittance series out of the same Gulf labour "
                "market, which separates 'Gulf demand' from 'Nepali supply'"},
    {"with": "ae",
     "mechanism": "the UAE is the other Gulf anchor of the same flow, with a different sector "
                  "mix -- services and logistics rather than construction -- so the UAE and "
                  "Saudi lines of the same NRB table moving apart is a compositional signal "
                  "about which part of the Gulf is hiring",
     "observable": "the UAE line of the remittance split and the permit counts to the UAE, "
                   "against Dubai's own activity and re-export series",
     "targets": ("XBRUSD", "USDINR"),
     "control": "the Saudi line of the same table in the same months -- a divergence inside one "
                "series is a cleaner test than either line against an external benchmark"},
    {"with": "my",
     "mechanism": "Malaysia is the largest non-Gulf destination and the one most sensitive to "
                  "manufacturing and palm-oil sector demand, and its intake has been switched "
                  "off and on by dated policy on both sides -- which makes the Malaysian line "
                  "an administered labour-demand event as well as a cyclical one",
     "observable": "the Malaysian line of the NRB remittance split, the permit counts, and the "
                   "dated Malaysian recruitment freezes and reopenings",
     "targets": ("USDSGD", "USDINR"),
     "control": "the Gulf lines of the same table over the same months, so a Malaysian freeze "
                "is told from a general slowdown"},
    {"with": "kr",
     "mechanism": "THE CLEANEST ADMINISTERED LABOUR EVENT ANYWHERE IN THIS BOOK: the Korea "
                  "Employment Permit System quota for Nepali workers is PUBLISHED AND DATED, "
                  "the selection results are published, and the wage is a multiple of the Gulf "
                  "one -- so a quota change is a dated, quantified shock to a published "
                  "remittance line with a known lag",
     "observable": "the Korea EPS quota and selection announcements against the Korean line of "
                   "the NRB remittance split, three to nine months later",
     "targets": ("USDKRW", "USDINR"),
     "control": "the other destination lines of the same table in the same months, and Korean "
                "small-manufacturer employment as the upstream demand control"},
    {"with": "bd",
     "mechanism": "Bangladesh is the sibling South Asian remittance-funded net importer that "
                  "went through the SAME reserve squeeze in 2021-23 WITHOUT a hard peg -- which "
                  "makes it the natural control that separates 'the region's external shock' "
                  "from 'what the peg did to Nepal'",
     "observable": "the two countries' reserve, import-cover and remittance series over the "
                   "2021-23 squeeze and the recovery",
     "targets": ("USDINR", "XAUUSD"),
     "control": "Sri Lanka as the third case, which defaulted -- three South Asian importers, "
                "three exchange-rate regimes, one external shock"},
    {"with": "lk",
     "mechanism": "Sri Lanka is the case where the same external squeeze ended in default and a "
                  "float; Nepal's import ban is what a country does instead when it will not "
                  "let the rate go. The pair dates the counterfactual for NP-D",
     "observable": "the import-control episodes in both countries against their reserve paths",
     "targets": ("USDINR", "XAUUSD"),
     "control": "the pre-episode years in both, matched on import cover"},
    {"with": "cn",
     "mechanism": "the northern border: the trans-Himalayan crossings at Rasuwagadhi/Kerung and "
                  "Tatopani are a small, politically salient and episodically closed trade "
                  "route, and their share is the measurable part of the 'India versus China' "
                  "question that dominates Nepali policy discussion",
     "observable": "the China share of the customs series and the crossing openings and "
                   "closures, against Chinese customs' own Nepal line",
     "targets": ("USDCNH", "USDINR"),
     "control": "the Indian border points over the same months -- a China-route gain that is "
                "not an India-route loss is new trade rather than diverted trade"},
)
# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "NP-T1",
     "source": "NRB monthly gross reserves and import cover, against the RBI's own weekly "
               "reserve supplement",
     "target": "USDINR", "targets": ("USDINR",), "to_country": "ind", "sign": "-",
     "mechanism": "THE PACK'S PRIMARY EDGE. The 1.6 peg means Nepal has no external price of "
                  "its own, so its published reserve and cover series is a SECOND, INDEPENDENT "
                  "MEASUREMENT of the same external pressure India manages -- produced by a "
                  "different institution, on a different calendar, with no incentive to manage "
                  "the Indian narrative",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 40.0,
     "actor": "Nepal Rastra Bank as the keeper of a hard peg",
     "constraint": "a peg that removes the exchange rate as an instrument, leaving the reserve "
                   "position as the only state variable",
     "flow": "regional external pressure into a published third-party reserve series",
     "condition": "the Nepali and Indian reserve series diverging beyond their historical range",
     "control": "the RBI's own weekly supplement over the same window, which the Nepali series "
                "must ADD to rather than echo; Bangladesh and Sri Lanka as the regional control",
     "falsifier": "the Nepali series carries no information about USDINR beyond what the RBI's "
                  "own reserve data already carries -- and if it only echoes, this edge is a "
                  "measured refusal rather than an edge",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T2",
     "source": "NRB monthly remittance inflow, Gulf lines (Saudi Arabia, UAE, Qatar)",
     "target": "XBRUSD", "targets": ("XBRUSD", "USDINR"), "to_country": "sa", "sign": "+",
     "mechanism": "roughly a quarter of Nepali GDP is earned abroad and the NRB publishes it BY "
                  "SOURCE COUNTRY every month, which makes the Gulf construction and "
                  "oil-revenue cycle visible from the receiving end on a monthly published "
                  "clock nobody triangulates",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 40.0,
     "actor": "the migrant worker and the remittance channel",
     "constraint": "destination-country quotas and recruitment costs",
     "flow": "Gulf labour demand into a published monthly transfer series",
     "condition": "a Gulf-line move beyond its trailing seasonal band",
     "control": "the destination countries' own employment and project-award series; the "
                "Bangladeshi and Indian remittance flows out of the same labour market",
     "falsifier": "the by-source split adds nothing to a model of Gulf labour demand built from "
                  "the Gulf's own published series",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T3",
     "source": "The published Korea EPS quota and selection results for Nepali workers",
     "target": "USDKRW", "targets": ("USDKRW", "USDINR"), "to_country": "kr", "sign": "+",
     "mechanism": "a DATED, PUBLISHED, QUANTIFIED administered shock to a specific published "
                  "remittance line with a known three-to-nine-month lag; the Korean wage is a "
                  "multiple of the Gulf one, so the quota moves the value of the flow more than "
                  "its headcount",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the Korea Employment Permit System and the Department of Foreign Employment",
     "constraint": "a quota set by Korean policy and allocated by examination",
     "flow": "an administered labour quota into a published remittance line",
     "condition": "a quota change or a selection announcement in the window",
     "control": "the other destination lines of the same table over the same months; Korean "
                "small-manufacturer employment as the upstream demand control",
     "falsifier": "quota announcements are followed by no measurable change in the Korean "
                  "remittance line at any lag, which would mean the quota is not binding",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T4",
     "source": "The 2022 luxury-import ban and the cash-margin controls, by gazette date",
     "target": "USDINR", "targets": ("USDINR", "XAUUSD"), "to_country": "ind", "sign": "-",
     "mechanism": "a blunt administered control on the trade account, imposed to defend a "
                  "reserve position under a peg that offers no other instrument; it is an "
                  "experiment with dates, and its end is dated by the revenue cost to an "
                  "import-duty-funded state as much as by the reserve recovery",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Nepali importer under a gazetted control",
     "constraint": "a gazette notice with immediate effect and a border everything still "
                   "crosses",
     "flow": "administered import control into the trade account into the reserve position",
     "condition": "a window containing a GAZETTED control date",
     "control": "the UNBANNED categories over the same months; Sri Lanka's and Pakistan's "
                "contemporaneous restrictions",
     "falsifier": "the banned categories' collapse is matched by an equal collapse in unbanned "
                  "categories, which would make it demand and not the control",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T5",
     "source": "NEA net electricity flow to India and the monsoon onset and withdrawal dates",
     "target": "USDINR", "targets": ("USDINR", "XBRUSD", "XNGUSD"), "to_country": "ind",
     "sign": "+",
     "mechanism": "run-of-river generation makes Nepal's export capacity literally a function "
                  "of rainfall, so the SIGN of a real cross-border energy flow reverses twice a "
                  "year on a published date and substitutes at the margin for Indian thermal "
                  "generation",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Nepal Electricity Authority and the monsoon",
     "constraint": "transmission capacity and Indian approval for each export arrangement",
     "flow": "rainfall into generation into a cross-border power flow",
     "condition": "a rainfall departure beyond its seasonal norm at the monsoon onset",
     "control": "Indian hydro generation over the same months; the same seasons before the "
                "export arrangements existed",
     "falsifier": "the Nepali export volume carries no information about Indian power or "
                  "thermal-fuel conditions beyond Indian generation data itself",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T6",
     "source": "The fortnightly IOC-to-NOC petroleum price revision, on the 1st and the 16th",
     "target": "XBRUSD", "targets": ("XBRUSD", "XNGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the international product price becomes a domestic price level through an "
                  "ADMINISTERED STEP FUNCTION on a published clock rather than through a "
                  "market, which gives the pass-through a calendar a study can condition on and "
                  "a placebo in the intervening days",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Nepal Oil Corporation as a monopoly with a single foreign supplier",
     "constraint": "a politically set retail price that is periodically frozen",
     "flow": "international product price into an administered retail step",
     "condition": "a product move beyond a threshold since the previous revision",
     "control": "the intervening non-revision days; Indian retail fuel prices over the same "
                "fortnights",
     "falsifier": "the revision-date behaviour is indistinguishable from the intervening days "
                  "once the crude move is controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T7",
     "source": "The Dashain and Tihar festival block, aligned on the festival rather than the "
               "calendar month",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDINR"), "to_country": "global", "sign": "+",
     "mechanism": "the single largest seasonal remittance inflow and the single largest "
                  "seasonal gold purchase of the Nepali year land inside a lunar block that "
                  "MOVES BY UP TO THREE WEEKS between adjacent years, so a month-aligned study "
                  "is averaging over two different events",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Nepal Calendar Determination Committee and the remitting worker",
     "constraint": "a lunisolar calendar that no weekday rule reproduces",
     "flow": "festival timing into remittance and gold demand",
     "condition": "a window inside the declared festival shutdown block",
     "control": "the same calendar weeks in years when the festival fell elsewhere; the Indian "
                "festival calendar, which overlaps and is not identical",
     "falsifier": "the effect is a calendar-month effect rather than a festival effect, which "
                  "the festival-aligned control decides directly",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T8",
     "source": "The NRB gold import quota and the Nepal-India corridor",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDINR"), "to_country": "ind", "sign": "+",
     "mechanism": "an administered supply constraint on a metal, set in kilograms per day by "
                  "dated circular, sitting beside an open border with a much larger market "
                  "whose own import duty sets the corridor's economics",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the gold importer and the border corridor",
     "constraint": "a quota routinely below demand and episodic customs enforcement",
     "flow": "quota and duty differential into physical metal movement",
     "condition": "a quota change or an Indian duty change in the window",
     "control": "Indian gold demand and the Indian duty dates over the same months; quarters "
                "with no quota change",
     "falsifier": "the Nepali gold import series adds nothing to Indian gold demand and the "
                  "Indian duty regime -- DECLARED MARGINAL for the world price on its face",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T9",
     "source": "The Nepali border points and the transit corridor, including the 2015-16 "
               "blockade",
     "target": "USDINR", "targets": ("USDINR", "USDCNH"), "to_country": "ind", "sign": "-",
     "mechanism": "a landlocked economy's supply is its transit rights; a political event at "
                  "the border is a supply shock with a date, and the 2015-16 blockade is the "
                  "demonstration that it reaches prices",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Department of Customs and the importer at the Indian border",
     "constraint": "Indian transit rights and two Himalayan passes as the only alternatives",
     "flow": "border closure into supply into the domestic price level",
     "condition": "a window containing a border closure or a congestion episode",
     "control": "the Indian export series over the same months; the unaffected border points "
                "as the within-country control",
     "falsifier": "the closure months are indistinguishable from matched open months once the "
                  "season and the Indian export cycle are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T10",
     "source": "The Nepali CPI against the Indian CPI under a hard peg and an open border",
     "target": "USDINR", "targets": ("USDINR", "XBRUSD"), "to_country": "ind", "sign": "+",
     "mechanism": "with no exchange rate to move and a border people walk across, Nepali "
                  "inflation is substantially Indian inflation arriving with a lag; the "
                  "measurable object is the LAG and the residual, not the level",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 35.0,
     "actor": "the Indian-border trader and the open-border arbitrage",
     "constraint": "an 1,800-kilometre open border and a fixed cross-rate",
     "flow": "Indian price level into Nepali price level",
     "condition": "a Nepali-minus-Indian inflation gap beyond its historical band",
     "control": "the Indian CPI over the same months as the benchmark; the Bangladeshi CPI as "
                "the sibling importer without the peg",
     "falsifier": "the residual after the Indian series is white noise, which would make this a "
                  "measured refusal and a useful one",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T11",
     "source": "IMF Extended Credit Facility review completions and disbursements",
     "target": "USDINR", "targets": ("USDINR",), "to_country": "ind", "sign": "-",
     "mechanism": "unlike a precautionary line this facility DISBURSES, so a completed review "
                  "is a dated step in the reserve series and a dated statement about the peg's "
                  "sustainability, published in a staff report",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the IMF under an Extended Credit Facility",
     "constraint": "structural benchmarks touching bank supervision and the fiscal accounts",
     "flow": "programme review into a reserve step",
     "condition": "a window containing a review completion or a publicised delay",
     "control": "the reserve series' own monthly noise; the Sri Lankan and Pakistani programme "
                "calendars",
     "falsifier": "no step is visible in the reserve series at disbursement dates beyond the "
                  "monthly noise, which would mean the amounts are too small to matter",
     "evidence": "HYPOTHESIS"},
    {"id": "NP-T12",
     "source": "The mid-July fiscal boundary at 1 Shrawan and the annual Monetary Policy",
     "target": "USDINR", "targets": ("USDINR", "XAUUSD"), "to_country": "ind", "sign": "+",
     "mechanism": "the budget lands about seven weeks before the year it funds opens, the duty "
                  "schedule changes with it, and the annual Monetary Policy follows the "
                  "boundary -- three dated events inside eight weeks on a calendar that is not "
                  "Gregorian and that a Gregorian study misplaces by two to six weeks",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Ministry of Finance and Nepal Rastra Bank",
     "constraint": "a Bikram Sambat fiscal boundary derived from a published astronomical "
                   "mapping",
     "flow": "fiscal and monetary calendar into import duties and directed credit",
     "condition": "a window straddling the derived fiscal boundary",
     "control": "the same calendar weeks in years when the boundary fell a day either side; "
                "matched weeks with no fiscal event",
     "falsifier": "boundary weeks are indistinguishable from matched non-boundary weeks once "
                  "the season is controlled for",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the peg established and the conflict years", "start": "1993-02-01",
     "end": "2006-11-20",
     "regime": "the 1.60 NPR = 1 INR cross-rate fixed on 1993-02-01 and held through a decade "
               "of internal conflict; remittances were a fraction of their later share and the "
               "external position was aid-funded",
     "markers": ("1993-02-01 the cross-rate fixed",
                 "2006-11-21 the Comprehensive Peace Agreement"),
     "why_it_matters": "the remittance channel that dominates every later mechanism barely "
                       "exists here; an elasticity fitted on this era is fitted on a different "
                       "economy",
     "status": "SETTLED"},
    {"name": "the remittance takeoff", "start": "2006-11-21", "end": "2015-04-24",
     "regime": "the post-conflict decade in which labour migration to the Gulf and Malaysia "
               "scaled and remittances rose toward a quarter of GDP; the permit system was "
               "built and the Korea EPS channel opened",
     "markers": ("2008 the Department of Foreign Employment permit series begins",
                 "2008 the first Korea EPS intakes"),
     "why_it_matters": "this is where the remittance-to-deposit-to-credit transmission that "
                       "NP-H is about actually forms",
     "status": "SETTLED"},
    {"name": "the earthquake and the border blockade", "start": "2015-04-25",
     "end": "2016-02-05",
     "regime": "the April 2015 earthquake followed by an unofficial border blockade from "
               "September 2015 to February 2016 that cut fuel and goods supply through India "
               "almost entirely; the demonstration that transit rights are this economy's "
               "supply",
     "markers": ("2015-04-25 the earthquake",
                 "2015-09 the blockade begins", "2016-02-05 the blockade ends"),
     "why_it_matters": "A BOUNDARY NO POOLED STUDY MAY CROSS: prices, trade and the fuel series "
                       "in these months are a supply shock, not a demand cycle, and the China "
                       "route's share was permanently repriced politically afterwards",
     "status": "SETTLED"},
    {"name": "the federal constitution and the pre-pandemic expansion", "start": "2016-02-06",
     "end": "2020-03-23",
     "regime": "reconstruction, the new federal structure, the interest-rate corridor "
               "introduced in 2016, rising imports and a widening trade deficit funded by "
               "remittances",
     "markers": ("2016-07 the interest-rate corridor introduced",
                 "2017-2018 the federal elections and the new structure"),
     "why_it_matters": "the first era in which the NRB has a corridor to operate, so NP-H's "
                       "policy variable exists here and not before",
     "status": "SETTLED"},
    {"name": "the pandemic and the reserve squeeze", "start": "2020-03-24", "end": "2022-12-14",
     "regime": "border closure and a remittance collapse, then a remittance recovery into an "
               "import surge that drove import cover toward six months; cash margins from "
               "December 2021, the luxury-import ban from 2022-04-26, and an IMF Extended "
               "Credit Facility approved in January 2022",
     "markers": ("2020-03-24 the national lockdown",
                 "2022-01 the IMF facility approved",
                 "2022-04-26 the luxury-import ban"),
     "why_it_matters": "THE ERA NP-D IS ABOUT. A peg with no rate to move defended itself with "
                       "an outright import ban, and the whole episode is dated",
     "status": "SETTLED"},
    {"name": "the recovery, the power trade agreement and the cover rebuild",
     "start": "2022-12-15", "end": "2026-12-31",
     "regime": "the ban lifted on 2022-12-15, record remittances, import cover rebuilt past a "
               "year, a long-term power trade agreement with India for up to 10,000 MW over ten "
               "years signed in January 2024, and a domestic credit cycle that did not follow "
               "the deposit recovery",
     "markers": ("2022-12-15 the ban lifted", "2024-01 the power trade agreement"),
     "why_it_matters": "the current regime and the only one whose data the desk can trade; the "
                       "power-export leg of NP-E only becomes a real series here",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the Nepalese rupee is not quoted by this broker",
     "measured": "data/universe/universe.json holds no NPR symbol",
     "consequence": "every domestic mechanism terminates in USDINR, gold, the energy legs or "
                    "the labour-destination FX legs; NPR is an INPUT, never a cell -- and "
                    "because of the peg it would carry no information even if it were quoted"},
    {"constraint": "NEPAL HAS NO DERIVATIVES MARKET OF ANY KIND",
     "measured": "no options, no index futures, no single-stock futures, no live commodity "
                 "exchange contract, and no COT for the NPR anywhere",
     "consequence": "there is no open interest, no implied volatility and no expiry clock; the "
                    "generic expiry, options and positioning miners correctly report UNMEASURED "
                    "rather than reaching for an Indian substitute"},
    {"constraint": "NEPSE is closed to foreign portfolio participation",
     "measured": "foreign portfolio investment in listed equity is essentially prohibited",
     "consequence": "the domestic equity market is a closed liquidity pool that cannot "
                    "transmit; it is a domestic credit observable and never an instrument, and "
                    "its single names are event lane under the two-lane order (2026-09-06)"},
    {"constraint": "every official series is stamped to the BIKRAM SAMBAT month",
     "measured": "the NRB's monthly report and the customs workbook are both BS-dated",
     "consequence": "a Gregorian month comparison is comparing two different fortnights; the "
                    "collector must carry the BS stamp and translate explicitly, and a cell "
                    "built on an untranslated stamp is UNMEASURED rather than approximate"},
    {"constraint": "THERE IS NO PUBLISHED CONSENSUS FOR ANY NEPALI RELEASE",
     "measured": "no economist survey, no expectations poll, no forecast panel exists",
     "consequence": "a 'surprise' in this pack is measured against a published trailing rule "
                    "and is labelled as such; the terminal consensus that exists for the INR "
                    "leg is LICENSED (machine_use_allowed=false) and is registered, not scraped"},
    {"constraint": "the NOC retail price page keeps no history",
     "measured": "the page shows today's price and is replaced at each revision",
     "consequence": "the fortnightly pass-through series is pit_feasible=false until the "
                    "archive layer's snapshots back it, and the dataset row says so"},
    {"constraint": "the Nepal Gazette's digitised run is incomplete",
     "measured": "rajpatra.dop.gov.np and lawcommission.gov.np cover recent years well and the "
                 "older run patchily",
     "consequence": "IMPORT_CONTROLS labels each row GAZETTED or PRESS_REPORTED; a "
                    "press-reported date may generate a hypothesis and may never promote a "
                    "cell, and an undigitised notice is UNMEASURED rather than absent"},
    {"constraint": "the monthly reports arrive five to six weeks after their period",
     "measured": "a 40-day publication lag on the NRB report and 30 days on customs",
     "consequence": "neither series can condition its own month; treating either as a leading "
                    "indicator is a look-ahead and the pack refuses it by construction"},
    {"constraint": "the national weekend is SATURDAY ONLY and NEPSE's is Friday and Saturday",
     "measured": "government offices work Sunday to Friday; NEPSE trades Sunday to Thursday",
     "consequence": "any study that assumes a Saturday-Sunday weekend mislabels every Sunday as "
                    "a non-trading day, which is the single most common error in this "
                    "jurisdiction; `is_national_weekend` and `is_nepse_session` are separate"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "NRB monthly remittance inflow by source country",
    "Department of Foreign Employment labour permits, new and renewed",
    "Korea EPS quota and selection results",
    "NRB gross reserves and import cover in months",
    "Department of Customs monthly trade by country and commodity",
    "NEPSE loans-against-shares outstanding and the NRB cap on them")

SERIES: dict[str, str] = {
    "NP_RESERVES": "NRB:gross_reserves", "NP_COVER": "NRB:import_cover_months",
    "NP_REMITTANCE": "NRB:remittance_inflow", "NP_REMITTANCE_BY_SOURCE":
        "NRB:remittance_by_source_country",
    "NP_PERMITS": "DOFE:labour_permits", "NP_EPS_QUOTA": "EPS:korea_quota",
    "NP_TRADE": "CUSTOMS:trade_by_country", "NP_GOLD_IMPORT": "CUSTOMS:gold_imports_kg",
    "NP_GOLD_QUOTA": "NRB:gold_import_quota", "NP_FUEL": "NOC:retail_price",
    "NP_POWER": "NEA:power_trade", "NP_CPI": "NSO:cpi", "NP_POLICY": "NRB:policy_rate",
    "NP_NEPSE": "NEPSE:index", "NP_MARGIN": "NRB:loans_against_shares",
    "NP_PEG": "computed:usdnpr_from_usdinr(USDINR)",
}

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "np_peg_read_on_india", "domain_ids": ("NP-A", "NP-B"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.np.pack:mine_peg_read_on_india",
     "needs": ("NRB:gross_reserves", "NRB:import_cover_months", "USDINR D1 bars"),
     "notes": "the peg arithmetic and the import-cover state buckets; the RBI's own series is "
              "the benchmark the Nepali one must add to rather than echo"},
    {"name": "np_remittance_seasons", "domain_ids": ("NP-C", "NP-G"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.np.pack:mine_remittance_seasons",
     "needs": ("FESTIVAL_SHUTDOWN", "NRB:remittance_by_source_country", "XAUUSD, USDINR D1"),
     "notes": "the festival-aligned inflow block rather than the calendar month, which is the "
              "only way to tell a festival effect from an October effect"},
    {"name": "np_fuel_revision_clock", "domain_ids": ("NP-F", "NP-K"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.np.pack:mine_fuel_revision_clock",
     "needs": ("noc_revision_days", "XBRUSD, XNGUSD H1 bars"),
     "notes": "the 1st and the 16th with the intervening non-revision days as the built-in "
              "placebo"},
    {"name": "np_import_control_events", "domain_ids": ("NP-D", "NP-I", "NP-J"), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.np.pack:mine_import_control_events",
     "needs": ("IMPORT_CONTROLS", "CUSTOMS:trade_by_country", "USDINR, XAUUSD D1 bars"),
     "notes": "the gazetted control dates with the unbanned-category control beside them; "
              "PRESS_REPORTED rows generate hypotheses and may never promote"},
    {"name": "np_fiscal_boundary", "domain_ids": ("NP-L", "NP-M", "NP-H"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.np.pack:mine_fiscal_boundary",
     "needs": ("SHRAWAN_1", "fiscal_year_bounds", "USDINR D1 bars"),
     "notes": "the mid-July Bikram Sambat boundary DERIVED rather than typed, with the budget "
              "seven weeks earlier and the annual Monetary Policy after it"},
    {"name": "np_transmission_seeds",
     "domain_ids": ("NP-E", "NP-N"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.np.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map and its sibling interactions as HYPOTHESIS discoveries, "
              "deduplicated by the registry"},
)

MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("NP-A", "NP-H"), "release_surprise": ("NP-A", "NP-C", "NP-K"),
    "calendar_settlement": ("NP-F", "NP-L"), "holiday_liquidity": ("NP-G",),
    "positioning": ("NP-N",), "carry_funding": ("NP-B", "NP-H"),
    "corporate_flow": ("NP-E", "NP-J"), "institutional_flow": ("NP-C", "NP-M"),
    "equity_mechanics": ("NP-N",), "derivatives_expiry": ("NP-N",),
    "failure": ("NP-D", "NP-J"), "residual": ("NP-K", "NP-B"),
    "transfer": ("NP-A", "NP-C"), "scouts": ("NP-E", "NP-I"),
    "session_microstructure": ("NP-G",),
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
        "jurisdictions": JURISDICTIONS,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "query_territories": QUERY_TERRITORIES,
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "cells": CELLS, "interactions": INTERACTIONS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "import_controls": IMPORT_CONTROLS,
        "peg": {"npr_per_inr": NPR_PER_INR, "since": PEG_SINCE.isoformat()},
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
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026.

    `weekly_closed` is (5,) and NOT (5, 6): Nepal's national weekend is SATURDAY ONLY, and
    handing the framework the Gregorian default here would silently delete every Sunday from
    the country's trading calendar.
    """
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates),
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in FIXED_PUBLIC),
            "weekly_closed": NATIONAL_WEEKEND, "notes": HOLIDAYS_RULE["authority"]}


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


# --------------------------------------------------------------- the department's own miners
#: Every `CUSTOM_MINERS` entry points at one of these. They are PURE PYTHON -- no network, no
#: LLM, no heavy import -- and they read only this pack's own tables.
def mine_peg_read_on_india(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """NP-A / NP-B: the peg arithmetic and the import-cover state buckets a cell conditions on.
    No data is fetched; the mapping USDINR -> USDNPR is deterministic and the cover buckets are
    the pack's declared stress ladder."""
    rows = [dict(peg_state(x, 15.0, 1.1), usdinr_bucket=f"inr_{i}")
            for i, x in enumerate((80.0, 83.0, 85.0, 87.0, 90.0))]
    ladder = [{"cover_months": c, "state": "STRESS" if c < 7.0 else "COMFORT"}
              for c in (4.0, 6.0, 7.0, 9.0, 13.0)]
    return {"miner": "np_peg_read_on_india", "domain_ids": ("NP-A", "NP-B"),
            "rows": tuple(rows), "ladder": tuple(ladder), "n": len(rows) + len(ladder),
            "symbols": ("USDINR", "XAUUSD"),
            "prior": "the peg carries NO price information; the claim is that the Nepali "
                     "reserve series carries INFORMATION the Indian one does not",
            "control": "the RBI's own weekly reserve supplement over the identical window"}


def mine_remittance_seasons(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """NP-C / NP-G: the festival-aligned inflow block for each declared year, with its drift
    against the previous year -- which is the number that kills a calendar-month study."""
    rows: list[dict[str, Any]] = []
    previous: date | None = None
    for year in sorted(FESTIVAL_SHUTDOWN):
        lo, hi, status = FESTIVAL_SHUTDOWN[year]
        drift = (lo - previous).days - 365 if previous is not None else 0
        rows.append({"year": year, "start": lo.isoformat(), "end": hi.isoformat(),
                     "status": status, "length_days": (hi - lo).days + 1,
                     "drift_vs_prior_year_days": drift})
        previous = lo
    return {"miner": "np_remittance_seasons", "domain_ids": ("NP-C", "NP-G"),
            "rows": tuple(rows), "n": len(rows), "symbols": ("XAUUSD", "USDINR", "USDKRW"),
            "control": "the same calendar weeks in years when the festival fell elsewhere -- "
                       "the only way to tell a festival effect from an October effect"}


def mine_fuel_revision_clock(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """NP-F / NP-K: the fortnightly IOC-to-NOC revision dates across the declared years, with
    the intervening days named as the placebo."""
    years = [int(y) for y in HOLIDAYS_RULE["years"]]
    lo, hi = date(min(years), 1, 1), date(max(years), 12, 31)
    days = noc_revision_days(lo, hi)
    return {"miner": "np_fuel_revision_clock", "domain_ids": ("NP-F", "NP-K"),
            "rows": tuple({"date": d.isoformat(), "half": 1 if d.day == 1 else 2,
                           "weekday": d.weekday(),
                           "is_national_weekend": is_national_weekend(d)} for d in days),
            "n": len(days), "symbols": ("XBRUSD", "XNGUSD"),
            "control": "the intervening non-revision days, which say whether the administered "
                       "clock carries anything the crude move does not"}


def mine_import_control_events(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """NP-D / NP-I / NP-J: the dated import-control episode, each row carrying its evidence
    label so a PRESS_REPORTED date can never promote a cell."""
    rows = [{"date": d.isoformat(), "action": a, "status": st,
             "promotable": st == "GAZETTED"} for d, a, st in IMPORT_CONTROLS]
    return {"miner": "np_import_control_events", "domain_ids": ("NP-D", "NP-I", "NP-J"),
            "rows": tuple(rows), "n": len(rows), "symbols": ("USDINR", "XAUUSD"),
            "control": "the UNBANNED categories over the same months; Sri Lanka's and "
                       "Pakistan's contemporaneous restrictions"}


def mine_fiscal_boundary(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """NP-L / NP-M / NP-H: the Bikram Sambat fiscal boundaries, DERIVED from the published
    BS-Gregorian anchors rather than typed, with the label a Gregorian study gets wrong."""
    rows = []
    for bs in sorted(SHRAWAN_1):
        start, end = fiscal_year_bounds(bs)
        rows.append({"bs_year": bs, "label": f"{bs}/{(bs + 1) % 100:02d}",
                     "start": start.isoformat(), "end": end.isoformat(),
                     "weekday_of_start": start.weekday()})
    return {"miner": "np_fiscal_boundary", "domain_ids": ("NP-L", "NP-M", "NP-H"),
            "rows": tuple(rows), "n": len(rows), "symbols": ("USDINR", "XAUUSD"),
            "control": "the same calendar weeks in years when the boundary fell a day either "
                       "side, which is what makes the derivation worth doing"}


def mine_transmission_seeds(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own map and its sibling interactions, as HYPOTHESIS rows the registry
    deduplicates. Nothing here is a measurement and every row says so."""
    rows = [{"id": str(e["id"]), "targets": tuple(e["targets"]), "evidence": str(e["evidence"]),
             "falsifier": str(e["falsifier"]), "control": str(e["control"])}
            for e in TRANSMISSION_EDGES_SEED]
    rows += [{"id": f"NP-X:{r['with']}", "targets": tuple(r["targets"]),
              "evidence": "HYPOTHESIS", "falsifier": str(r["control"]),
              "control": str(r["control"])} for r in INTERACTIONS]
    return {"miner": "np_transmission_seeds", "domain_ids": ("NP-E", "NP-N"),
            "rows": tuple(rows), "n": len(rows),
            "control": "every row is HYPOTHESIS until the gauntlet says otherwise"}


#: name -> callable, so the two registrations (CUSTOM_MINERS and this) are ONE set and a test
#: can assert it rather than trusting it.
MINERS: dict[str, Any] = {
    "mine_peg_read_on_india": mine_peg_read_on_india,
    "mine_remittance_seasons": mine_remittance_seasons,
    "mine_fuel_revision_clock": mine_fuel_revision_clock,
    "mine_import_control_events": mine_import_control_events,
    "mine_fiscal_boundary": mine_fiscal_boundary,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Runs this pack's own miners over its own tables and returns the
    report; when a department Ctx is given it emits each row through `ctx.record` as well.

    Pure Python: no network, no LLM, no heavy import. `unmeasured` is a first-class part of the
    answer -- a thing this pack knows it cannot see is a measurement and never a blank (L1.28a).
    """
    rows: list[dict[str, Any]] = []
    for name, fn in MINERS.items():
        got = fn(None, ctx)
        rows.append({"miner": name, "n": int(got.get("n", 0)),
                     "domain_ids": tuple(got.get("domain_ids", ()))})
        record = getattr(ctx, "record", None) if ctx is not None else None
        if callable(record):
            record(got)
    unmeasured = [str(c["constraint"]) for c in ACCESS_CONSTRAINTS]
    return {"code": CODE, "at": datetime.now(tz=UTC).date().isoformat(), "emitted": len(rows),
            "cells_emitted": len(cells()), "rows": tuple(rows),
            "unmeasured": tuple(unmeasured),
            "layers": source_layer_coverage()["n_layers_covered"],
            "interactions": tuple(str(r["with"]) for r in INTERACTIONS),
            "note": "pure-python department pass over this pack's own tables; every row is a "
                    "HYPOTHESIS for the one gauntlet and nothing here is a measurement"}
