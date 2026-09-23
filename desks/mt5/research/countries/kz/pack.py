"""KAZAKHSTAN: an announced sovereign FX sale, a pipeline through another state's port, no quote.

WHAT KAZAKHSTAN IS AS A MARKET MECHANISM. Four things belong to this economy and to no other in
the desk's book:

  1. THE SOVEREIGN PUBLISHES NEXT MONTH'S FX ORDER. Transfers from the National Fund (Ұлттық қор /
     Национальный фонд) to the republican budget are funded by selling foreign currency on the
     Kazakhstan Stock Exchange, and the National Bank ANNOUNCES the planned monthly volume in
     advance. The unified pension fund (ЕНПФ) runs the opposite way, buying foreign assets on a
     published schedule. So Kazakhstan, like Russia, has a sovereign FX order with a size and a
     date -- and unlike Russia's, both legs are published and they partially offset.

  2. THE OIL LEAVES THROUGH A RUSSIAN PORT. Most Tengiz, Kashagan and Karachaganak volume moves
     through the Caspian Pipeline Consortium to Novorossiysk on the Russian Black Sea coast. A
     CPC loading suspension -- storm damage, mooring-point repairs, drone damage, an
     administrative order -- removes roughly 1.5% of world crude supply with hours of notice and
     is announced publicly. This is Kazakhstan's single largest transmission into an instrument
     the desk can trade, and it reaches XBRUSD, not anything Kazakh.

  3. ONE COMPANY IS ABOUT 40% OF WORLD URANIUM SUPPLY. Kazatomprom's production guidance and its
     subsoil-use tax changes are global uranium supply events. There is no uranium instrument in
     this broker's registry, so the mechanism is named as a transmission target with the energy
     and equity proxies it reaches rather than pretended into a cell.

  4. THE COUNTRY CHANGED ITS CLOCK. Kazakhstan unified onto a SINGLE time zone at UTC+5 on
     1 March 2024; Astana and Almaty had been UTC+6. Every Kazakh announcement's UTC minute moved
     by an hour on that date. An event study that applies one mapping across the boundary puts
     half its sample in the wrong bar, and this is the kind of fact that is invisible until it
     has already ruined a result.

WHAT IS EXECUTABLE. Nothing Kazakh. USDKZT is ABSENT from `data/universe/universe.json`, as are
the KASE index, the base rate, uranium, and every domestic bond. This pack is therefore
TRANSMISSION-ONLY by construction: every domain terminates in XBRUSD, XTIUSD, USDRUB, USDCNH,
XCUUSD, XZNUSD, XALUSD, XPBUSD, WHEAT or XAUUSD. That is stated once here and enforced in every
instrument tuple below, so no cell is ever compiled against a series the box cannot fill (L1.49).

THE TENGE'S REAL RELATIONSHIPS, for when a quote does arrive. KZT is a high-beta oil currency
with a heavy rouble correlation that is a TRADE and PAYMENT link rather than a macro one:
Kazakhstan is a re-export corridor, a large share of its imports are Russian, and its banks sit
between the two payment systems. The correlation therefore steps with enforcement rounds rather
than drifting with fundamentals -- the same shape as the Turkish corridor in the Russia pack.

LANGUAGES. Kazakh and Russian are both working languages of the primary sources; the National
Bank publishes in Kazakh, Russian and English, and the practitioner web is overwhelmingly
Russian. Both are carried in `TERMINOLOGY` because a screen holding only one will miss half the
primary material.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# ruff: noqa: RUF001
# RUF001/RUF002 flag Cyrillic characters that resemble Latin ones. The rule exists to catch
# homoglyph attacks in IDENTIFIERS; this file carries Kazakh and Russian terminology as DATA,
# because a screen that cannot match "базалық мөлшерлеме" cannot find the National Bank's own
# headline. Suppressed file-wide and explained here; no identifier in this module is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "KZ"
NAME = "Republic of Kazakhstan"
REGION_COMMAND = "russia_cis"
REGION_DESK = "CENTRAL_ASIA"
CURRENCY = "KZT"
FISCAL_YEAR_END = "12-31"
NATIVE_LANGUAGES: tuple[str, ...] = ("kk", "ru")

#: TRANSMISSION-ONLY. No Kazakh instrument is quoted by this broker, so every symbol here is a
#: FOREIGN one that a Kazakh mechanism reaches. Nothing here is an equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD",                 # CPC outages, Tengiz expansion, OPEC+ quota compliance
    "XNGUSD",                           # Karachaganak gas and the domestic price ceiling
    "XCUUSD", "XZNUSD", "XALUSD", "XPBUSD",  # copper, zinc, lead, ferroalloys
    "XAUUSD", "XAGUSD",                 # NBK gold purchases from domestic producers
    "WHEAT", "CORN",                    # a significant Central Asian grain exporter
    "USDRUB",                           # the rouble link is a trade and payment link
    "USDCNH",                           # the Belt-and-Road land corridor and copper/oil to China
    "USDTRY",                           # the Middle Corridor via the Caspian and Azerbaijan
    "USDX", "EURUSD",                   # the dollar factor
    "US500", "UST10Y",                  # global risk and duration controls
)

#: Everything Kazakh. Each names the universe symbols its mechanism actually reaches.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USDKZT (теңге / тенге)", "venue": "KASE and OTC",
     "why": "ABSENT from data/universe/universe.json. The tenge is a high-beta oil currency with "
            "a rouble correlation that is a trade and payment link rather than a macro one",
     "proxies": ("XBRUSD", "USDRUB", "USDCNH")},
    {"name": "National Bank of Kazakhstan base rate (базалық мөлшерлеме)", "venue": "NBK",
     "why": "the policy rate and its +/-100bp corridor; no Kazakh rate instrument is quoted here",
     "proxies": ("USDRUB", "XBRUSD")},
    {"name": "KASE index and the KASE FX morning session", "venue": "KASE",
     "why": "the official USDKZT weighted-average rate is struck in the morning session and "
            "applies the NEXT day; the exchange is where the National Fund's sales land",
     "proxies": ("USDRUB", "XBRUSD")},
    {"name": "Caspian Pipeline Consortium loadings at Novorossiysk", "venue": "CPC",
     "why": "roughly 1.5% of world crude leaves through one Russian terminal. A loading "
            "suspension is a dated, public, physical supply interruption with hours of notice",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "Tengiz Future Growth Project and Kashagan production", "venue": "TCO / NCOC",
     "why": "the two fields that determine whether Kazakhstan can meet or exceed its OPEC+ quota; "
            "expansion volumes are announced years ahead and delivered late",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "National Fund (Ұлттық қор) transfers and the NBK's announced FX sales",
     "venue": "Ministry of Finance / NBK",
     "why": "an ANNOUNCED monthly sovereign FX sale with a size; the pension fund's foreign-asset "
            "purchases run the other way and are also published, so the NET is two public numbers",
     "proxies": ("USDRUB", "XBRUSD")},
    {"name": "Kazatomprom uranium production guidance and subsoil-use tax",
     "venue": "company disclosure / Ministry of Energy",
     "why": "roughly 40% of world uranium supply from one producer; a guidance cut or a tax change "
            "is a global supply event and there is no uranium instrument in this registry",
     "proxies": ("XTIUSD", "XBRUSD", "US500")},
    {"name": "KEGOC and the domestic power balance", "venue": "KEGOC",
     "why": "a power-constrained economy where industrial output and crypto-mining load compete; "
            "a constraint here caps metals output",
     "proxies": ("XALUSD", "XCUUSD")},
    {"name": "Middle Corridor (Trans-Caspian) freight volumes",
     "venue": "Kazakhstan Temir Zholy / ADY",
     "why": "the re-routing of China-Europe freight away from Russia; volumes are published and "
            "the corridor links this pack to the Azerbaijani and Turkish ones",
     "proxies": ("USDCNH", "USDTRY", "USDRUB")},
    {"name": "Kazakh wheat export volumes and the Central Asian balance",
     "venue": "Ministry of Agriculture",
     "why": "Kazakhstan is the swing supplier into Central Asia and Afghanistan; export bans and "
            "rail-car shortages are recurring administrative supply shocks",
     "proxies": ("WHEAT", "CORN")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "National Bank of Kazakhstan (Қазақстан Ұлттық Банкі / Национальный Банк Казахстана)",
    "short": "NBK",
    "framework": "inflation_targeter",
    "committee": "Monetary Policy Committee",
    "policy_instrument": "the base rate (базалық мөлшерлеме / базовая ставка) with a symmetric "
                         "+/-100bp interest-rate corridor",
    "corridor": "the standing deposit facility sits 100bp below the base rate and the standing "
                "loan facility 100bp above; the TONIA overnight repo rate is the operating target",
    "mandate": "a 5% inflation target, approached through a medium-term trajectory rather than a "
               "fixed band; a free float has been the declared regime since August 2015",
    "decision_rule": "eight scheduled decisions a year, published with a press release and a "
                     "commentary; the Bank also publishes a monetary policy report quarterly",
    "announce_local": "15:00 Asia/Almaty",
    "announce_utc": "10:00",
    "announce_utc_dst": "10:00",
    "dst_rule": "NO seasonal clock change -- but the COUNTRY CHANGED ZONE. Kazakhstan unified "
                "onto UTC+5 on 1 March 2024; Astana and Almaty were UTC+6 before that date, so "
                "15:00 local was 09:00 UTC before 2024-03-01 and 10:00 UTC after. An event study "
                "applying one mapping across the boundary puts half its sample in the wrong bar",
    "presser_utc": "11:00",
    "minutes_lag_days": 0,
    "consensus_proxy": "NONE ON THIS BOX and none easily reachable. The usable public "
                       "expectations are the NBK's own analyst survey and press polls; both are "
                       "SURVEYS and a surprise built from them must be labelled as such",
    "consensus_proxy_trap": "the tenge's reaction to a base-rate move is confounded by the "
                            "National Fund's FX sales landing in the same week; the sovereign "
                            "flow and the policy event are not independent and an event study "
                            "that ignores the sales calendar attributes one to the other",
    "distinctive": "the National Bank is BOTH the monetary authority and the manager of the "
                   "National Fund's FX sales and the pension fund's asset purchases. It is on "
                   "both sides of its own currency market by mandate, which makes 'intervention' "
                   "and 'agency execution' genuinely hard to separate -- and the Bank publishes "
                   "monthly figures precisely because of that",
    "balance_sheet_history": (
        "August 2015: the float, after a defended band; the tenge moved about 25% in a day",
        "2016-2019: gradual de-dollarisation of deposits under a high base rate",
        "2022: an emergency increase and temporary controls after the January unrest and the "
        "February shock next door"),
    "off_cycle": "the Bank moved out of cycle in 2022; an unscheduled decision is its own class",
    "other_clocks": (
        {"what": "monthly announcement of planned National Fund FX sales",
         "when_local": "end of the preceding month", "when_utc": "10:00",
         "reference_lag_days": 0},
        {"what": "monthly CPI from the Bureau of National Statistics",
         "when_local": "the first days of the month", "when_utc": "05:00",
         "reference_lag_days": 3},
        {"what": "monthly balance of payments and external debt", "when_local": "quarterly",
         "when_utc": "10:00", "reference_lag_days": 75},
        {"what": "the official USDKZT rate from the KASE morning session",
         "when_local": "about 15:30 Almaty, EFFECTIVE THE NEXT DAY", "when_utc": "10:30",
         "reference_lag_days": 0},
    ),
    "root": "https://www.nationalbank.kz",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Official USDKZT rate from the KASE morning session",
     "local": "weighted average of the morning session, published about 15:30 Almaty and "
              "EFFECTIVE THE NEXT CALENDAR DAY",
     "time_utc": "10:30", "time_utc_dst": "10:30",
     "dst_rule": "none, but the zone moved from UTC+6 to UTC+5 on 2024-03-01",
     "instruments": (), "window_minutes": 270, "confidence": "DECLARED, VERIFY against kase.kz",
     "why": "every tenge contract and tax liability is struck at this rate. The NEXT-DAY effective "
            "date is the same trap as in the Russian pack: using it on its publication day is "
            "using tomorrow's number today"},
    {"name": "National Fund FX sales on KASE",
     "local": "spread across the KASE FX sessions through the month",
     "time_utc": "05:00", "time_utc_dst": "05:00", "dst_rule": "none",
     "instruments": ("USDRUB",), "window_minutes": 360, "confidence": "DECLARED",
     "why": "the sovereign order lands inside the exchange session; the monthly volume is "
            "announced in advance and the execution is spread, so the ANNOUNCEMENT and the FLOW "
            "are two separate objects"},
    {"name": "Brent dated, the reference for Kazakh export grades",
     "local": "the London afternoon assessment", "time_utc": "16:30", "time_utc_dst": "15:30",
     "dst_rule": "GMT/BST", "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "confidence": "SETTLED",
     "why": "CPC Blend and Tengiz crude price against Brent with a quality and freight "
            "differential; the differential widened materially after 2022 as buyers discriminated "
            "between Kazakh and Russian barrels loading at the SAME port"},
    {"name": "LBMA gold price and NBK domestic gold purchases",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "confidence": "SETTLED",
     "why": "the National Bank exercises a priority right to buy domestically-produced gold, so "
            "Kazakh mine output is partially withheld from the market by official policy"},
    {"name": "LME official settlement for the base metals complex",
     "local": "the second ring session", "time_utc": "12:45", "time_utc_dst": "11:45",
     "dst_rule": "GMT/BST", "instruments": ("XCUUSD", "XZNUSD", "XALUSD", "XPBUSD"),
     "window_minutes": 15, "confidence": "SETTLED",
     "why": "Kazakh copper, zinc, lead and ferroalloy output prices against LME; the desk's CFDs "
            "track those benchmarks"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "National Fund transfer and FX sale month", "kind": "month_end",
     "convention": "the planned monthly sale volume is announced at the end of the preceding "
                   "month and executed across the following month's sessions",
     "rollover_utc": "10:00", "instruments": ("USDRUB", "XBRUSD"),
     "why": "an announced sovereign order; the announcement is an event and the execution is a "
            "flow, and treating them as one loses the more tradeable of the two"},
    {"name": "pension fund (ЕНПФ) foreign asset purchases", "kind": "month_end",
     "convention": "monthly, on a published schedule, in the OPPOSITE direction to the National "
                   "Fund's sales",
     "rollover_utc": "10:00", "instruments": ("USDRUB",),
     "why": "the two legs partially offset; using only the National Fund's sale over-states the "
            "net sovereign flow, sometimes by most of it"},
    {"name": "Kazakh tax calendar", "kind": "day_of_month",
     "convention": "the corporate income tax and mineral extraction tax fall on the 25th of the "
                   "month following the reporting period",
     "rollover_utc": "10:00", "instruments": ("USDRUB",),
     "why": "the same exporter-conversion mechanism as the Russian tax period, on a DIFFERENT "
            "date; a study importing the Russian 28th into Kazakhstan is testing the wrong day"},
    {"name": "republican budget year", "kind": "fiscal_year_end", "convention": "31 December",
     "rollover_utc": "", "instruments": ("XBRUSD",),
     "why": "the budget law sets the guaranteed transfer from the National Fund for the year, "
            "which is the base size of the sovereign FX sale"},
    {"name": "OPEC+ quota compliance period", "kind": "month_end",
     "convention": "monthly production against quota, with a compensation schedule for any "
                   "overproduction",
     "rollover_utc": "", "instruments": ("XBRUSD", "XTIUSD"),
     "why": "Kazakhstan has repeatedly overproduced against quota because Tengiz and Kashagan "
            "volumes are contractually committed to foreign operators; the compensation schedule "
            "is published and is a dated future supply constraint"},
    {"name": "KASE settlement", "kind": "weekday", "convention": "T+0/T+1 on the FX market",
     "rollover_utc": "", "instruments": (),
     "why": "the domestic FX market settles same-day or next-day rather than T+2, so the forward "
            "points implied by a domestic quote are not comparable with an offshore one"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Kazakhstan Stock Exchange (KASE)",
     "index_symbols": (),
     "open_local": "11:00 (FX morning session from 11:00)", "close_local": "17:00",
     "open_utc": "06:00", "close_utc": "12:00",
     "dst_rule": "none; the zone moved UTC+6 to UTC+5 on 2024-03-01",
     "auction": "the FX morning session produces the weighted-average official rate",
     "expiry_rule": "n/a to this desk",
     "holidays": "the Kazakh national calendar",
     "notes": "the official USDKZT rate is struck HERE and applies the next day; this is also "
              "where the National Fund's sales and the pension fund's purchases land. The desk "
              "has no access and no data licence, so every KASE observable is UNMEASURED"},
    {"name": "Astana International Exchange (AIX), inside the AIFC",
     "index_symbols": (),
     "open_local": "11:00", "close_local": "17:00", "open_utc": "06:00", "close_utc": "12:00",
     "dst_rule": "none", "auction": "opening and closing auctions",
     "expiry_rule": "n/a",
     "holidays": "the Kazakh national calendar plus AIFC-specific days",
     "notes": "the AIFC operates under an ENGLISH COMMON LAW jurisdiction with its own courts and "
              "regulator -- a genuinely unusual institutional fact in this region, and the reason "
              "Kazakh sovereign and quasi-sovereign paper is placed here rather than only abroad"},
)


# --------------------------------------------------------------------------- holidays
def _next_working(day: date, taken: set[date]) -> date:
    while day.weekday() >= 5 or day in taken:
        day += timedelta(days=1)
    return day


#: The national holidays of the Republic of Kazakhstan. NAURYZ (Наурыз мейрамы) is the three-day
#: spring festival on 21, 22 and 23 March and is the largest closure of the Kazakh year.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Жаңа жыл (New Year), day 1"),
    (1, 2, "Жаңа жыл (New Year), day 2"),
    (3, 8, "Халықаралық әйелдер күні (International Women's Day)"),
    (3, 21, "Наурыз мейрамы (Nauryz), day 1"),
    (3, 22, "Наурыз мейрамы (Nauryz), day 2"),
    (3, 23, "Наурыз мейрамы (Nauryz), day 3"),
    (5, 1, "Қазақстан халқының бірлігі мерекесі (Unity Day)"),
    (5, 7, "Отан қорғаушы күні (Defender of the Fatherland Day)"),
    (5, 9, "Жеңіс күні (Victory Day)"),
    (7, 6, "Астана күні (Capital Day)"),
    (8, 30, "Конституция күні (Constitution Day)"),
    (10, 25, "Республика күні (Republic Day)"),
    (12, 16, "Тәуелсіздік күні (Independence Day)"),
)

#: KURBAN AIT is lunar and is PROCLAIMED, not computed. Kazakhstan observes the first day of Eid
#: al-Adha as a public holiday. Tabulated because an astronomical formula is not the authority.
KURBAN_AIT: dict[int, date] = {
    2024: date(2024, 6, 16), 2025: date(2025, 6, 6), 2026: date(2026, 5, 27),
    2027: date(2027, 5, 17),
}


def national_holidays(year: int) -> dict[date, str]:
    """Kazakhstan's national holidays for `year`, from the Labour Code's fixed dates plus the
    tabulated Kurban Ait.

    THE TRANSFER RULE AND ITS LIMIT. A holiday falling on a Saturday or Sunday gives a day of rest
    on the following working day, which this function computes. The GOVERNMENT then issues an
    annual decree moving additional days to build long weekends, exactly as in Russia, and those
    extra transfers are DECREED rather than derivable. `HOLIDAYS_RULE['decree_note']` says so.

    A SECOND CAVEAT, stated rather than hidden: the Kazakh holiday list has been AMENDED more than
    once in recent years. This table is the desk's declared set; a miner needing the exact working
    calendar must read the current Labour Code and the year's decree rather than trusting it.
    """
    out: dict[date, str] = {}
    taken: set[date] = set()
    for month, day, label in FIXED_NATIONAL:
        actual = date(year, month, day)
        out[actual] = label
        taken.add(actual)
    kurban = KURBAN_AIT.get(year)
    if kurban is not None:
        out.setdefault(kurban, "Құрбан айт (Kurban Ait)")
        taken.add(kurban)
    for month, day, label in FIXED_NATIONAL:
        actual = date(year, month, day)
        if actual.weekday() < 5:
            continue
        moved = _next_working(actual + timedelta(days=1), taken)
        taken.add(moved)
        out[moved] = f"{label} — ауыстыру (transferred)"
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """KASE and AIX follow the national calendar; there is no separate exchange calendar."""
    return national_holidays(year)


def nauryz(year: int) -> tuple[date, date, date]:
    """The three canonical Nauryz dates: 21, 22 and 23 March."""
    return (date(year, 3, 21), date(year, 3, 22), date(year, 3, 23))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_labour_code_plus_annual_decree_plus_lunar_table",
    "authority": "the Labour Code of the Republic of Kazakhstan for the fixed dates and the "
                 "weekend-transfer rule; an annual government decree for the bridging transfers; "
                 "official proclamation for Kurban Ait",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "fixed_rule": "1-2 January, 8 March, 21-23 March (Nauryz), 1 May, 7 May, 9 May, 6 July, "
                  "30 August, 25 October and 16 December, plus the first day of Kurban Ait",
    "transfer_rule": "a holiday falling on a weekend gives a day of rest on the following working "
                     "day",
    "decree_note": "THE ANNUAL DECREE IS THE AUTHORITY FOR THE BRIDGING TRANSFERS and it is not "
                   "derivable. This module computes only the Labour Code rule; the decree's extra "
                   "transfers are UNMEASURED here",
    "amendment_note": "the Kazakh holiday list has been AMENDED more than once in recent years. "
                      "This table is the desk's DECLARED set and is flagged for verification "
                      "rather than asserted as current",
    "lunar_note": "Kurban Ait is proclaimed, not computed; it is tabulated in KURBAN_AIT",
    "known_dates": {
        "2026-03-21": "Наурыз мейрамы day 1, a SATURDAY",
        "2026-03-22": "Наурыз мейрамы day 2, a SUNDAY",
        "2026-03-23": "Наурыз мейрамы day 3, a MONDAY -- the three canonical Nauryz dates are "
                      "21, 22 and 23 March and two of them fall on the weekend in 2026, so the "
                      "transfers extend the closure into the following week",
        "2026-05-27": "Құрбан айт (Kurban Ait), the same day as Turkey's Kurban Bayramı",
        "2026-01-01": "Жаңа жыл day 1, a Thursday",
        "2024-03-01": "NOT A HOLIDAY -- the date Kazakhstan unified onto UTC+5. Every Kazakh "
                      "event's UTC minute moves by an hour here",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "nauryz_fn": nauryz,
    "kurban": KURBAN_AIT,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = ""
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders for KZT", "root": "", "fields": (),
     "frequency": "n/a", "snapshot": "", "publish_utc": "", "lag_days": 0, "licence": "",
     "available": False,
     "why": "no CME tenge contract exists and none ever has",
     "pit_warning": "DOES NOT EXIST. Tenge positioning is UNMEASURED, permanently, and must be "
                    "reported as such rather than proxied by the rouble's (now also dead) series"},
    {"name": "NBK monthly announcement of planned National Fund FX sales",
     "root": "https://www.nationalbank.kz/en/news",
     "fields": ("planned_sale_usd", "month", "actual_sale_usd", "pension_fund_purchase_usd"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "10:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the sovereign's own FX order, announced in advance with a size. The pension fund's "
            "purchases are published alongside and run the OTHER way",
     "pit_warning": "the ANNOUNCED and ACTUAL volumes differ; the announcement is the "
                    "point-in-time datum and the actual is a second one published later"},
    {"name": "NBK international reserves and National Fund assets",
     "root": "https://www.nationalbank.kz/en/news/mezhdunarodnye-rezervy",
     "fields": ("gross_reserves", "gold_tonnes", "national_fund_usd"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "10:00", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "the Fund's size bounds the sale programme; the gold share reflects the Bank's "
            "priority-purchase right over domestic mine output",
     "pit_warning": "the preliminary figure is revised"},
    {"name": "KASE trading statistics and participant structure",
     "root": "https://kase.kz/en/", "fields": ("volume", "participants"),
     "frequency": "daily", "snapshot": "session", "publish_utc": "12:00", "lag_days": 1,
     "licence": "exchange data; the desk holds NO licence", "available": False,
     "why": "the only view of who is on the other side of the sovereign's sales",
     "pit_warning": "NOT ACCESSIBLE TO THIS DESK; named so the gap is visible"},
    {"name": "CPC loading programme and terminal status announcements",
     "root": "https://www.cpc.ru/en/press/news/", "fields": ("status", "monthly_programme_tonnes"),
     "frequency": "monthly programme, event-driven status", "snapshot": "month",
     "publish_utc": "08:00", "lag_days": 0, "licence": "free, public", "available": True,
     "why": "the single most tradeable Kazakh observable: a loading suspension removes roughly "
            "1.5% of world crude supply and reaches XBRUSD within minutes",
     "pit_warning": "status announcements arrive with little notice and are sometimes first "
                    "reported by shipping agents rather than by the consortium; the timestamp "
                    "matters more than the text"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "KZ-A": ("базалық мөлшерлеме", "базовая ставка", "Ұлттық Банк", "Национальный Банк",
             "инфляция", "ақша-несие саясаты", "денежно-кредитная политика", "дәлiз", "коридор"),
    "KZ-B": ("Ұлттық қор", "Национальный фонд", "трансферт", "кепілдендірілген трансферт",
             "гарантированный трансферт", "нысаналы трансферт", "валюта сату", "продажа валюты"),
    "KZ-C": ("ЕНПФ", "зейнетақы қоры", "пенсионный фонд", "шетелдік активтер",
             "иностранные активы"),
    "KZ-D": ("мұнай", "нефть", "Теңіз", "Тенгиз", "Қашаған", "Кашаган", "Қарашығанақ",
             "КТК", "CPC", "Новороссийск", "экспорт", "квота", "ОПЕК+"),
    "KZ-E": ("уран", "Қазатомөнеркәсіп", "Казатомпром", "өндіру", "добыча", "жер қойнауы салығы"),
    "KZ-F": ("мыс", "медь", "мырыш", "цинк", "қорғасын", "свинец", "ферроқорытпа",
             "ферросплавы"),
    "KZ-G": ("бидай", "пшеница", "астық", "зерно", "егін", "урожай", "экспортқа тыйым",
             "запрет на экспорт"),
    "KZ-H": ("теңге", "тенге", "ресми бағам", "официальный курс", "KASE", "биржа",
             "таңғы сессия", "утренняя сессия"),
    "KZ-I": ("Ресей", "Россия", "рубль", "реэкспорт", "төлем", "платежи", "санкциялар",
             "санкции", "параллельный импорт"),
    "KZ-J": ("Қытай", "Китай", "Белдеу және жол", "Пояс и путь", "транзит",
             "Орта дәліз", "Средний коридор"),
    "KZ-K": ("Наурыз", "Наурыз мейрамы", "Құрбан айт", "мереке", "праздник", "ауыстыру",
             "перенос"),
    "KZ-L": ("АХҚО", "МФЦА", "AIFC", "ағылшын құқығы", "английское право", "AIX"),
}

# --------------------------------------------------------------------------- sources
#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). Every source carries
#: EXACTLY ONE, and this pack must name at least one source in each layer or declare the layer
#: ABSENT with a reason. A country is never "covered" by five obvious sources: five official
#: roots is one layer done and nine layers missing, and the missing nine are where a mechanism
#: nobody has tested is still lying around.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: How the desk is allowed to reach a source. Three INDEPENDENT labels travel with every source
#: and this is the first: what the terms permit, which is a legal fact and not a quality one.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")

#: The second label: how much the desk believes the source, independent of what it may read.
#: FRINGE and CONTRADICTED material is KEPT as an evidence object at low weight and never
#: dropped -- a claim that looks false is still a dated, testable claim, and deleting it destroys
#: the only record that it was ever made.
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")

#: The third label, and the only one the desk can EARN: whether anything from this source has
#: ever predicted anything. UNTESTED is the honest default and is not a criticism.
#: NARRATIVE_FEATURE means the text conditions usefully even though its claims do not forecast.
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source, with the roots a crawler can start from and its three labels.

    `queries` are NATIVE-SCRIPT search terms and slang, never translated English: a miner that
    searches an English phrase on a Russian, Kazakh, Georgian, Azerbaijani or Turkish ground
    finds the small English-speaking corner of that ground and then reports the result as if it
    were the ground.

    `machine_use_allowed=True` registers a source whose terms forbid machine extraction. It is
    NEVER scraped and NEVER omitted: the row stays so the desk knows the ground exists, knows it
    was considered, and knows exactly why it is not being read.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} not one of "
                         f"{list(ACCESS_LABELS)}")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r} not one of "
                         f"{list(CREDIBILITY_LABELS)}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} not one of "
                         f"{list(PREDICTIVE_STATES)}")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this country has nothing in, declared BY NAME with the reason.

    A blank layer and an absent layer look identical in a table and mean opposite things: one is
    work not done, the other is a measurement. This row makes the second one visible (L1.28a).
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    """How many real sources this pack names in each of the ten layers. A zero is a hole, and an
    `absent_*` row does not count toward it -- declaring a layer absent is honest, not coverage.
    """
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def layer_terms() -> dict[str, tuple[str, ...]]:
    """The native-script query vocabulary this pack carries, grouped by layer. Derived from the
    sources themselves so it can never drift from what a crawler would actually search."""
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
    """Sources per layer, every empty layer named, and the two numbers that must stay at zero.

    `unexplained_missing` is a layer with no source AND no reason -- the exact shape of a pack
    that stopped at the five obvious official feeds. `machine_use_forbidden` is not a defect: it
    is the register of ground the desk knows about and deliberately does not scrape.
    """
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


#: KAZAKHSTAN'S TEN LAYERS, in KAZAKH AND RUSSIAN. The National Bank publishes in Kazakh, Russian
#: and English; the practitioner and retail web is overwhelmingly Russian; and the official
#: vocabulary is Kazakh. A screen carrying only one of the two languages misses half the primary
#: material and almost all of the community material. "Базалық мөлшерлеме" and "базовая ставка"
#: are the same rate in two languages and neither is spelled "base rate" anywhere that matters.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "kz_nbk", "National Bank of Kazakhstan", layer="official",
        roots=("https://www.nationalbank.kz/en/news",
               "https://www.nationalbank.kz/en/page/bazovaya-stavka",
               "https://www.nationalbank.kz/en/news/mezhdunarodnye-rezervy"),
        queries=("базалық мөлшерлеме", "базовая ставка", "Ұлттық Банк", "Национальный Банк",
                 "ақша-несие саясаты", "денежно-кредитная политика", "пайыздық дәліз",
                 "процентный коридор", "валюталық интервенция", "продажа валюты Нацфонда",
                 "алтын-валюта резервтері", "золотовалютные резервы"),
        languages=("kk", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the monthly FX-sale announcement carries a PLANNED volume and a later ACTUAL, "
              "which are two different point-in-time data. The local-to-UTC mapping CHANGED on "
              "2024-03-01 when the country unified onto UTC+5"),
    source_class(
        "kz_stat", "Bureau of National Statistics", layer="official",
        roots=("https://stat.gov.kz/en/", "https://stat.gov.kz/en/industries/economy/prices/"),
        queries=("инфляция", "тұтыну бағаларының индексі", "индекс потребительских цен",
                 "өнеркәсіп өндірісі", "промышленное производство", "сыртқы сауда",
                 "внешняя торговля"),
        languages=("kk", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CPI basket is re-weighted annually, which breaks long series silently"),
    source_class(
        "kz_ministries", "Ministry of Energy, Ministry of Agriculture and gov.kz",
        layer="official",
        roots=("https://www.gov.kz/memleket/entities/energo",
               "https://www.gov.kz/memleket/entities/moa",
               "https://www.gov.kz/memleket/entities/minfin"),
        queries=("мұнай өндіру", "добыча нефти", "экспорт нефти", "ОПЕК+ квота",
                 "компенсациялық кесте", "компенсационный график", "астық экспорты",
                 "экспорт зерна", "экспортқа тыйым", "запрет на экспорт", "Ұлттық қор трансферті"),
        languages=("kk", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the OPEC+ compensation schedule is published here and is a DATED FUTURE supply "
              "constraint -- a supply cut whose timing is known in advance, which is rare"),
    source_class(
        "kz_sanctions", "OFAC, EU and UK lists as they touch the Kazakh corridor",
        layer="official",
        roots=("https://ofac.treasury.gov/sanctions-list-service",
               "https://www.sanctionsmap.eu/"),
        queries=("re-export", "circumvention", "dual-use goods", "parallel import",
                 "параллельный импорт", "реэкспорт", "вторичные санкции", "комплаенс"),
        languages=("en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (government data)",
        notes="SANCTIONS ARE OFFICIAL PUBLIC DATA AND ARE USED AS DATA. Enforcement announcements "
              "are the dated events KZ-I's corridor steps on, and the list itself is the record "
              "of when each step happened"),
    source_class(
        "kz_kase_aix", "KASE, AIX and the AFSA regulator", layer="institutional",
        roots=("https://kase.kz/en/", "https://aix.kz/", "https://afsa.aifc.kz/"),
        queries=("KASE", "теңге бағамы", "курс тенге", "утренняя сессия", "таңғы сессия",
                 "средневзвешенный курс", "AIX", "АХҚО", "МФЦА", "ағылшын құқығы",
                 "английское право", "листинг"),
        languages=("kk", "ru", "en"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="exchange data; the desk holds NO licence",
        notes="the official USDKZT rate is struck in the KASE morning session and applies the "
              "NEXT day; this is also where the National Fund's sales land. NOT ACCESSIBLE to "
              "this desk, and registered so the gap is named. The AIFC is an ENGLISH-COMMON-LAW "
              "enclave with its own court and regulator, which is a genuinely unusual "
              "institutional fact in this region"),
    source_class(
        "kz_eabr_multilateral", "Eurasian Development Bank, ADB, EBRD and the IMF",
        layer="institutional",
        roots=("https://eabr.org/en/analytics/", "https://www.adb.org/countries/kazakhstan/",
               "https://www.imf.org/en/Countries/KAZ"),
        queries=("ЕАБР", "макроэкономический обзор", "Article IV", "Средний коридор",
                 "Орта дәліз", "региональная интеграция", "трансграничные платежи"),
        languages=("ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the EDB publishes the best free work on Middle Corridor capacity and on "
              "cross-border payment friction in the region -- the two mechanisms KZ-I and KZ-J "
              "are built on"),
    source_class(
        "kz_kazatomprom_ir", "Kazatomprom and the listed producers' investor disclosure",
        layer="institutional",
        roots=("https://www.kazatomprom.kz/en/", "https://kase.kz/en/issuers/"),
        queries=("өндіріс болжамы", "производственный прогноз", "guidance", "уран",
                 "жер қойнауын пайдалану салығы", "налог на добычу полезных ископаемых",
                 "серная кислота", "күкірт қышқылы"),
        languages=("kk", "ru", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="roughly 40% of world uranium supply from one producer, with SULPHURIC ACID "
              "availability as the unglamorous binding input. EVENT LANE ONLY for the single "
              "name; the pack uses it as an actor observable"),
    source_class(
        "kz_academic", "Narxoz, KIMEP, CyberLeninka and the regional literature",
        layer="academic",
        roots=("https://narxoz.edu.kz/", "https://www.kimep.kz/", "https://cyberleninka.ru/"),
        queries=("теңге бағамының факторлары", "факторы курса тенге", "нефтяная зависимость",
                 "мұнайға тәуелділік", "долларизация", "долларландыру",
                 "Ұлттық қор тиімділігі", "эффективность Нацфонда"),
        languages=("kk", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free reading; bulk download restricted",
        notes="the domestic literature on tenge determination and on National Fund policy is "
              "almost entirely Russian-language and almost entirely absent from Western indexes"),
    source_class(
        "kz_nbk_research", "National Bank research and the Monetary Policy Report",
        layer="academic",
        roots=("https://www.nationalbank.kz/en/page/issledovaniya",),
        queries=("зерттеу", "исследование", "трансмиссионный механизм",
                 "трансмиссиялық тетік", "инфляциялық күтулер", "инфляционные ожидания",
                 "прогноз"),
        languages=("kk", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Bank publishes its own analysis of a transmission channel that runs through "
              "deposit dollarisation rather than portfolio flow -- the mechanism KZ-A describes"),
    source_class(
        "kz_broker_research", "Halyk Finance, Freedom Finance research and Ranking.kz",
        layer="practitioner",
        roots=("https://halykfinance.kz/", "https://ffin.kz/", "https://ranking.kz/"),
        queries=("аналитикалық шолу", "аналитический обзор", "прогноз по тенге",
                 "теңге болжамы", "целевая цена", "банковский сектор", "банк секторы",
                 "нефтяные доходы"),
        languages=("kk", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NOT_PREDICTIVE", machine_use_allowed=True,
        licence="public web; redistribution restricted",
        notes="Ranking.kz aggregates domestic financial statistics into free charts that are "
              "faster than the official releases they are built from. NOT_PREDICTIVE is a "
              "measured verdict about published tenge forecasts, not a slur on the analysis"),
    source_class(
        "kz_telegram_macro", "Kazakh macro and market Telegram channels", layer="practitioner",
        roots=("https://t.me/s/",),
        queries=("Tengenomika", "теңге", "Нацфонд продажи", "валютные интервенции",
                 "инфляция Казахстан", "базовая ставка решение", "макро Казахстан"),
        languages=("ru", "kk"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="public channels; automated extraction restricted",
        notes="the fastest Kazakh macro commentary and the place a policy rumour is dated; a "
              "conditioning variable, never evidence"),
    source_class(
        "kz_tradernet_community", "Tradernet social feed and the Freedom Broker community",
        layer="retail_ecology",
        roots=("https://tradernet.kz/", "https://ffin.kz/"),
        queries=("Tradernet", "Фридом", "Freedom Broker", "инвестидея", "портфель",
                 "подписка на трейдера", "копирование сделок", "автоследование"),
        languages=("ru", "kk"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public social feed; automated extraction restricted",
        notes="Freedom is the dominant Kazakh retail broker and its Tradernet platform carries a "
              "SOCIAL FEED with published trader ideas and a follow mechanic. Heavy survivorship "
              "and heavy promotion; KEPT AT LOW WEIGHT, never dropped, because the follow counts "
              "are the only public read on retail crowding in this market"),
    source_class(
        "kz_kaspi_reddit", "Kaspi.kz community, Reddit and the Russian forums Kazakhs use",
        layer="retail_ecology",
        roots=("https://kaspi.kz/", "https://www.reddit.com/r/Kazakhstan/",
               "https://smart-lab.ru/"),
        queries=("Kaspi", "Каспи", "депозит ставка", "депозит мөлшерлемесі", "доллар алу",
                 "как купить доллары", "теңге әлсіреуі", "ослабление тенге", "смартлаб"),
        languages=("ru", "kk"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public social; automated extraction restricted",
        notes="Kaspi is a genuine super-app: most Kazakh retail financial behaviour passes "
              "through it, and household currency substitution is discussed there and on the "
              "Russian forums Kazakh traders also use. Low weight, never zero"),
    source_class(
        "kz_kursiv_forums", "Kursiv and LS comment threads", layer="retail_ecology",
        roots=("https://kursiv.media/", "https://lsm.kz/"),
        queries=("девальвация", "девальвация болады ма", "курс доллара прогноз",
                 "Нацфонд транш", "инфляция народная"),
        languages=("ru", "kk"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="public comment sections; automated extraction restricted",
        notes="devaluation expectation is the central Kazakh household variable and it is "
              "expressed here long before any survey measures it. FRINGE AND KEPT: the comment "
              "threads are frequently wrong and are the only high-frequency read on the belief"),
    source_class(
        "kz_tradernet_app", "Tradernet, Halyk Invest, Kaspi Investments and the broker APIs",
        layer="app_ecosystem",
        roots=("https://tradernet.kz/", "https://halykbank.kz/", "https://kaspi.kz/"),
        queries=("Tradernet API", "торговый терминал", "сауда терминалы", "мобильное приложение",
                 "комиссия брокера", "маржинальная торговля", "плечо", "шорт"),
        languages=("ru", "kk"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public product pages; account data is PRIVATE and is never sought",
        notes="which instruments Kazakh retail can reach and at what cost. NO ACCOUNT-LEVEL DATA "
              "is sought; that would be PRIVATE and is out of bounds"),
    source_class(
        "kz_metatrader_quik", "MetaTrader and QUIK as used by Kazakh brokers",
        layer="app_ecosystem",
        roots=("https://www.mql5.com/ru/market", "https://www.mql5.com/ru/code",
               "https://arqatech.com/ru/products/quik/"),
        queries=("алгоритмдік сауда", "алготрейдинг", "сауда роботы", "торговый робот",
                 "советник", "эксперт", "MQL5", "MQL4", "кодобаза", "QUIK", "стакан",
                 "скальпинг", "арбитраж", "тестер стратегий"),
        languages=("ru", "kk"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms",
        notes="Kazakh retail algorithmic trading runs on the SAME RUSSIAN-LANGUAGE ecosystems as "
              "Russia's -- MetaTrader's Russian sections and QUIK's LUA layer -- so the "
              "vocabulary and the code bases are shared and the KZ and RU packs mine one ground"),
    source_class(
        "kz_tradingview", "TradingView Russian-language scripts and ideas", layer="app_ecosystem",
        roots=("https://ru.tradingview.com/scripts/",),
        queries=("Pine Script", "индикатор", "стратегия", "идея", "нефть", "USDKZT",
                 "Brent анализ"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public with terms; automated extraction restricted",
        notes="registered and read, never scraped"),
    source_class(
        "kz_press", "Kursiv, LS, Forbes Kazakhstan, Kapital and Vlast", layer="media",
        roots=("https://kursiv.media/", "https://lsm.kz/", "https://forbes.kz/",
               "https://kapital.kz/", "https://vlast.kz/"),
        queries=("базовая ставка", "базалық мөлшерлеме", "Нацфонд", "Ұлттық қор",
                 "тенге", "теңге", "КТК", "Тенгиз", "Кашаган", "нефтедобыча",
                 "экспортная пошлина"),
        languages=("ru", "kk"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="public web; automated extraction restricted",
        notes="Vlast and LS carry the most independent coverage of National Fund policy; the "
              "others are faster. READ AND CITED, NEVER SCRAPED"),
    source_class(
        "kz_tengrinews", "Tengrinews and the general wire", layer="media",
        roots=("https://tengrinews.kz/", "https://www.inform.kz/"),
        queries=("жаңалықтар", "новости", "мереке", "праздник", "перенос выходных",
                 "жұмыс күні", "рабочий день"),
        languages=("kk", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the free, fast general wire; in practice the fastest public confirmation of the "
              "annual holiday-transfer decree, which HOLIDAYS_RULE declares it cannot compute"),
    source_class(
        "kz_wayback", "Internet Archive captures of nationalbank.kz, kase.kz and gov.kz",
        layer="archive",
        roots=("https://web.archive.org/web/*/nationalbank.kz*",
               "https://web.archive.org/web/*/kase.kz*",
               "https://web.archive.org/web/*/gov.kz*"),
        queries=("архив страницы", "первоначальная публикация", "изменение методики",
                 "удалённая публикация"),
        languages=("ru", "kk", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the planned-versus-actual FX sale volumes are published as news items that get "
              "reorganised; the Wayback capture is often the only surviving record of the "
              "PLANNED figure, which is the point-in-time datum KZ-B needs"),
    source_class(
        "kz_national_library", "National Library of Kazakhstan and the statistical archives",
        layer="archive",
        roots=("https://nlrk.kz/", "https://stat.gov.kz/"),
        queries=("мұрағат", "архив", "историческая статистика", "1999 девальвация",
                 "2009 девальвация", "2015 девальвация"),
        languages=("kk", "ru"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public archive; reading-room and site terms govern reuse",
        notes="three devaluations in sixteen years formed the household reflex KZ-A's "
              "transmission channel runs through; the contemporaneous record is how that reflex "
              "is dated rather than assumed"),
    source_class(
        "kz_cpc_rail", "CPC loadings, KTZ rail and the Middle Corridor operators",
        layer="physical_economy",
        roots=("https://www.cpc.ru/en/press/news/", "https://www.railways.kz/",
               "https://www.kmg.kz/en/"),
        queries=("КТК", "отгрузка", "Новороссийск", "приостановка отгрузки", "выносное "
                 "причальное устройство", "теміржол", "железная дорога", "погрузка",
                 "Орта дәліз", "Средний коридор", "Актау", "Курык", "паром"),
        languages=("ru", "kk", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S MOST TRADEABLE GROUND. A CPC loading suspension removes roughly 1.5% of "
              "world crude with hours of notice and reaches XBRUSD directly. Shipping agents "
              "frequently report it BEFORE the consortium does, so the first-public timestamp is "
              "the event time"),
    source_class(
        "kz_kegoc_energy", "KEGOC power system and the Ministry of Energy monthly data",
        layer="physical_economy",
        roots=("https://www.kegoc.kz/", "https://www.gov.kz/memleket/entities/energo"),
        queries=("электр энергиясы", "электроэнергия", "потребление", "дефицит мощности",
                 "мұнай өндіру", "добыча нефти", "переработка", "плановый ремонт",
                 "Тенгиз ремонт"),
        languages=("kk", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the domestic power balance is genuinely tight and caps metals output; scheduled "
              "field maintenance at Tengiz and Kashagan is announced and is a dated production "
              "constraint"),
    source_class(
        "kz_grain_physical", "Grain union, elevator stocks and export line-ups",
        layer="physical_economy",
        roots=("https://www.gov.kz/memleket/entities/moa", "https://www.apk-inform.com/"),
        queries=("астық қоры", "запасы зерна", "элеватор", "вагоны", "рейс", "квота на вагоны",
                 "экспорт пшеницы", "бидай экспорты", "Узбекистан", "Афганистан"),
        languages=("kk", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="mixed: ministry data is open, trade press is subscription",
        notes="RAIL-CAR AVAILABILITY, not price, is the binding constraint on Kazakh grain "
              "exports most years -- a physical bottleneck that no price series reveals"),
    source_class(
        "kz_citation_graph", "CyberLeninka, OpenAlex and the regional citation graph",
        layer="source_graph",
        roots=("https://cyberleninka.ru/", "https://openalex.org/"),
        queries=("цитирование", "дәйексөз", "список литературы", "кто цитирует"),
        languages=("ru", "kk", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free reading; bulk extraction restricted",
        notes="the Kazakh domestic literature is invisible in Western citation graphs; this is "
              "the only way to see whether a claim about tenge determination has been replicated"),
    source_class(
        "kz_code_graph", "GitHub and the shared Russian-language algo code graph",
        layer="source_graph",
        roots=("https://github.com/search?q=tradernet+api",
               "https://github.com/search?q=kase+api"),
        queries=("tradernet api", "kase api", "freedom broker api", "форк", "зависимости"),
        languages=("ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="per-repository; check each, never vendor code",
        notes="which Kazakh broker APIs have public clients is a direct map of what a domestic "
              "algorithmic participant can actually reach"),
    source_class(
        "kz_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en", "ru"), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="Kazakhstan shares most of its app and retail ground with Russia, so the registry's "
              "job here is to stop the same forum being counted twice as two countries' coverage"),
)

#: All ten layers are populated. The honest caveat is that Kazakhstan's APP_ECOSYSTEM and
#: RETAIL_ECOLOGY layers are LARGELY SHARED WITH RUSSIA -- the same MetaTrader Russian sections,
#: the same QUIK scripting layer, the same smart-lab -- which is a finding about the region and
#: not a shortcut: the source_graph layer exists partly to stop that shared ground being counted
#: twice as two separate countries' coverage.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "NBK base rate decisions", "source": "National Bank of Kazakhstan",
     "coverage": "2015 onward (the base rate was introduced in September 2015)",
     "frequency": "8 per year", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "free, public", "history_from": "2015-09", "pit_feasible": True,
     "assets": ("XBRUSD", "USDRUB"),
     "fields": ("decision_date", "base_rate_pct", "change_bp", "corridor_bp", "statement_text"),
     "pit_fields": ("release_ts_utc", "local_tz_at_release"),
     "mechanism_families": ("event_reaction", "policy_surprise"),
     "how_to_fetch": "nationalbank.kz news; NOTE the local-to-UTC mapping changes at 2024-03-01"},
    {"name": "NBK monthly National Fund FX sale announcement",
     "source": "National Bank of Kazakhstan", "coverage": "2017 onward", "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "the actual differs from the planned",
     "licence": "free, public", "history_from": "2017-01", "pit_feasible": True,
     "assets": ("USDRUB", "XBRUSD"),
     "fields": ("month", "planned_sale_usd_m", "actual_sale_usd_m", "pension_purchase_usd_m"),
     "pit_fields": ("announcement_ts_utc", "planned_flag"),
     "mechanism_families": ("sovereign_flow", "institutional_flow"),
     "how_to_fetch": "nationalbank.kz monthly news release, end of the preceding month"},
    {"name": "CPC monthly loading programme and terminal status",
     "source": "Caspian Pipeline Consortium", "coverage": "2010 onward",
     "frequency": "monthly programme plus event announcements", "publication_lag_days": 0.0,
     "revisions": "the programme is revised intra-month when loadings are interrupted",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "fields": ("month", "programme_tonnes", "status", "suspension_start", "suspension_end"),
     "pit_fields": ("announcement_ts_utc",),
     "mechanism_families": ("supply_shock", "event_reaction"),
     "how_to_fetch": "cpc.ru press news. THIS IS THE PACK'S MOST TRADEABLE DATASET"},
    {"name": "Bureau of National Statistics CPI", "source": "Bureau of National Statistics",
     "coverage": "1994 onward", "frequency": "monthly", "publication_lag_days": 3.0,
     "revisions": "revised; the basket is re-weighted annually", "licence": "free, public",
     "history_from": "1994-01", "pit_feasible": True, "assets": ("USDRUB",),
     "fields": ("reference_month", "cpi_mom", "cpi_yoy", "food", "non_food", "services"),
     "pit_fields": ("release_ts_utc", "vintage", "basket_version"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "stat.gov.kz price statistics"},
    {"name": "Kazakh crude production and export volumes", "source": "Ministry of Energy",
     "coverage": "2010 onward", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "fields": ("month", "production_kt", "export_kt", "cpc_share", "opec_quota",
                "compensation_due"),
     "pit_fields": ("publish_ts_utc", "vintage"),
     "mechanism_families": ("supply_shock", "terms_of_trade"),
     "how_to_fetch": "gov.kz Ministry of Energy monthly releases; the OPEC+ compensation schedule "
                     "is published separately and is a DATED FUTURE supply constraint"},
    {"name": "Kazatomprom production guidance and output",
     "source": "Kazatomprom company disclosure", "coverage": "2018 onward",
     "frequency": "quarterly plus guidance updates", "publication_lag_days": 30.0,
     "revisions": "guidance revised in public", "licence": "free, public",
     "history_from": "2018-11", "pit_feasible": True, "assets": ("XTIUSD", "US500"),
     "fields": ("period", "production_tu", "guidance_tu", "guidance_change", "subsoil_tax_note"),
     "pit_fields": ("announcement_ts_utc", "prior_guidance"),
     "mechanism_families": ("supply_shock",),
     "how_to_fetch": "kazatomprom.kz investor relations. NOTE: no uranium instrument exists in "
                     "this broker's registry, so this dataset feeds a TRANSMISSION hypothesis "
                     "only and every cell using it must name its proxy"},
    {"name": "Kazakh grain production and export", "source": "Ministry of Agriculture",
     "coverage": "2010 onward", "frequency": "monthly and seasonal",
     "publication_lag_days": 25.0, "revisions": "revised", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("WHEAT", "CORN"),
     "fields": ("period", "production_kt", "export_kt", "destination", "export_restriction"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("supply_shock", "policy_shock"),
     "how_to_fetch": "gov.kz Ministry of Agriculture; export bans and rail-car quotas are the "
                     "tradeable events, not the production level"},
    {"name": "NBK international reserves and National Fund assets",
     "source": "National Bank of Kazakhstan", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 7.0, "revisions": "the preliminary figure is revised",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XAUUSD", "USDRUB"),
     "fields": ("month", "gross_reserves_usd", "gold_tonnes", "national_fund_usd"),
     "pit_fields": ("publish_ts_utc", "preliminary_flag"),
     "mechanism_families": ("sovereign_flow",),
     "how_to_fetch": "nationalbank.kz reserves page"},
    {"name": "KASE market data (USDKZT official rate, index, volumes)",
     "source": "Kazakhstan Stock Exchange", "coverage": "n/a to this desk", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "n/a",
     "licence": "exchange data; NO LICENCE HELD", "history_from": "", "pit_feasible": False,
     "assets": (), "fields": (), "pit_fields": (),
     "mechanism_families": ("transmission_target",),
     "how_to_fetch": "NOT FETCHED. Named so the gap is explicit; USDKZT is UNMEASURED on this box"},
    {"name": "Desk MT5 commodity tape", "source": "the desk's own Fusion tape",
     "coverage": "2018 onward", "frequency": "tick to daily", "publication_lag_days": 0.0,
     "revisions": "append-only", "licence": "desk-owned", "history_from": "2018-01",
     "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "XCUUSD", "XZNUSD", "XALUSD", "WHEAT"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet -- the ONLY place a Kazakh "
                     "mechanism is executable on this box"},
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "National Bank of Kazakhstan as monetary authority",
        "holds": "the base rate, a +/-100bp corridor, and international reserves including a gold "
                 "stock built from a priority right over domestic mine output",
        "forced_to": ("decide at eight scheduled meetings a year and publish the same day",
                      "publish reserves and National Fund assets monthly",
                      "operate the corridor so that overnight TONIA tracks the base rate"),
        "when": "15:00 Almaty: 10:00 UTC since 2024-03-01 and 09:00 UTC before it, because the "
                "country changed time zone",
        "information": ("bank-level FX flow through the reporting it mandates",
                        "the National Fund's and pension fund's own schedules, which it executes"),
        "constraints": ("a 5% inflation target on a medium-term trajectory",
                        "a declared free float since August 2015",
                        "the awkward fact that it is BOTH the monetary authority and the agent "
                        "executing the sovereign's FX sales"),
        "instruments": ("XBRUSD", "USDRUB"),
        "counterparties": ("the domestic banking system", "the Ministry of Finance",
                           "the unified pension fund"),
        "observables": ("the base rate press release",
                        "monthly reserves and National Fund assets",
                        "the announced and actual FX sale volumes"),
        "impact": "the policy rate transmits to the tenge through deposit dollarisation rather "
                  "than through portfolio flow, because the domestic bond market is small and "
                  "foreign participation is limited",
        "persistence": "the framework has been stable since 2015; the ZONE CHANGE in March 2024 "
                       "is a break in the event clock and not in the economics, which makes it "
                       "the easiest kind of error to miss",
        "falsifier": "the same event-window statistic on the eight nearest non-meeting days. A "
                     "move that survives there is the hour, not the Bank -- and because the Bank "
                     "is also selling FX in the same week, the National Fund calendar must be a "
                     "second control or the two are confounded",
        "notes": "there is no on-broker instrument to measure this on; every KZ-A cell terminates "
                 "in XBRUSD or USDRUB and says so",
    },
    {
        "name": "The National Fund of Kazakhstan and its announced FX sales",
        "holds": "the sovereign oil fund, whose guaranteed and targeted transfers to the "
                 "republican budget are set in the budget law",
        "forced_to": ("fund the budget transfer by SELLING foreign currency on KASE, in a volume "
                      "announced in advance for each month",
                      "sell whatever the exchange rate, because the transfer is a legal "
                      "obligation of the budget"),
        "when": "the planned monthly volume is announced at the end of the preceding month; "
                "execution is spread across that month's exchange sessions",
        "information": ("actual budget execution before it is published"),
        "constraints": ("the budget law's transfer amount, revised only by supplementary budget",
                        "the Fund's own investment mandate and liquidity",
                        "a legislated minimum Fund balance"),
        "instruments": ("USDRUB", "XBRUSD"),
        "counterparties": ("KASE participants, principally the domestic banks",
                           "the unified pension fund, whose purchases run the other way"),
        "observables": ("the announced planned sale volume",
                        "the later actual volume, which differs",
                        "the pension fund's published foreign-asset purchases, which OFFSET"),
        "impact": "a sovereign FX order with a size and a date; the closest Kazakh analogue to "
                  "Russia's budget rule, and unusually the offsetting leg is published too",
        "persistence": "structural since the Fund was established; the SIZE tracks the oil price "
                       "with a budget-cycle lag, so it is largest exactly when the currency needs "
                       "it least",
        "falsifier": "months where the NET of the Fund's sale and the pension fund's purchase is "
                     "near zero. An effect that persists there was never the sovereign flow",
        "notes": "using only the sale leg over-states the net sovereign flow, sometimes by most "
                 "of it -- the same error as using Russia's budget rule without the mirroring",
    },
    {
        "name": "The unified pension fund (ЕНПФ) as a foreign-asset buyer",
        "holds": "the country's mandatory pension savings, managed with a rising allocation to "
                 "foreign assets",
        "forced_to": ("buy foreign currency to meet a target foreign-asset allocation, on a "
                      "published schedule",
                      "keep buying regardless of the exchange rate, because the mandate is an "
                      "allocation and not a view"),
        "when": "monthly, on a schedule published alongside the National Fund's sales",
        "information": ("its own contribution inflow"),
        "constraints": ("its investment declaration and the foreign-asset target",
                        "concentration limits on domestic paper, which FORCE the foreign "
                        "allocation as the fund outgrows the domestic market"),
        "instruments": ("USDRUB",),
        "counterparties": ("the National Bank, which executes for it", "KASE participants"),
        "observables": ("the published monthly foreign-asset purchase volume",
                        "the fund's asset allocation report"),
        "impact": "a structural, growing tenge SUPPLY that offsets the sovereign's demand; the "
                  "net of the two is the actual sovereign flow",
        "persistence": "structural and growing with the contribution base; the domestic market's "
                       "inability to absorb the fund is a one-way ratchet",
        "falsifier": "the net-of-both test above. If the sale leg alone explains the currency and "
                     "the purchase leg adds nothing, this actor is not separately real",
        "notes": "",
    },
    {
        "name": "Tengizchevroil, NCOC and Karachaganak as contract-bound producers",
        "holds": "the three giant fields that are most of Kazakh production, operated under "
                 "production-sharing agreements with foreign majors",
        "forced_to": ("produce to a contractual plan agreed with foreign operators, which is why "
                      "Kazakhstan has repeatedly OVERPRODUCED against its OPEC+ quota",
                      "ship through the routes that physically exist, principally CPC"),
        "when": "continuous production; the Tengiz expansion delivered in phases; OPEC+ "
                "compliance is measured monthly and compensation schedules are published",
        "information": ("their own field performance and maintenance schedules"),
        "constraints": ("production-sharing agreements that bind the state as much as the operator",
                        "the OPEC+ quota, which the state signed and the operators did not",
                        "export route capacity, which is the binding physical constraint"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "counterparties": ("the foreign operators", "CPC as the export route",
                           "OPEC+ as the quota authority"),
        "observables": ("monthly production and export volumes",
                        "the published OPEC+ compensation schedule",
                        "expansion project milestones"),
        "impact": "Kazakh overproduction is a recurring OPEC+ compliance story and the "
                  "compensation schedule is a DATED FUTURE supply constraint -- a rare thing: a "
                  "supply reduction whose timing is published in advance",
        "persistence": "structural while the production-sharing agreements stand; the conflict "
                       "between contractual volumes and quota volumes has no clean resolution",
        "falsifier": "the same statistic on other OPEC+ members with no comparable foreign "
                     "operator structure. Shared overproduction is a cartel-discipline story and "
                     "not a Kazakh contractual one",
        "notes": "the single names are ACTORS only",
    },
    {
        "name": "The Caspian Pipeline Consortium and the Novorossiysk terminal",
        "holds": "the export route for most Kazakh crude, terminating at a Russian Black Sea port",
        "forced_to": ("load through mooring points that are physically exposed to Black Sea "
                      "weather and, since 2022, to other hazards",
                      "publish a monthly loading programme and announce interruptions"),
        "when": "continuous loading; interruptions arrive with hours of notice",
        "information": ("terminal and mooring status before it is announced"),
        "constraints": ("the physical terminal, which has a small number of loading points",
                        "Russian regulatory authority over a route carrying Kazakh oil -- the "
                        "single largest political risk in Kazakh energy",
                        "weather in the Black Sea, which is a genuine seasonal constraint"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "counterparties": ("Kazakh producers", "Mediterranean and Asian refiners"),
        "observables": ("the monthly loading programme",
                        "suspension announcements and their timestamps",
                        "vessel line-ups reported by shipping agents, often FIRST"),
        "impact": "a loading suspension removes roughly 1.5% of world crude supply with hours of "
                  "notice. THIS IS THE PACK'S LARGEST TRANSMISSION and it lands in XBRUSD, an "
                  "instrument the desk trades",
        "persistence": "the route dependency is structural and has survived every attempt to "
                       "diversify; alternative routes (the Caspian to Baku, the China pipeline) "
                       "carry a fraction of the volume",
        "falsifier": "the same event-window statistic on XTIUSD, which shares the global price "
                     "but not the Black Sea route. A Brent-specific response is the route; a "
                     "shared one is a global price move",
        "notes": "shipping agents frequently report a suspension before the consortium does, so "
                 "the TIMESTAMP of first public report is the event time, not the press release",
    },
    {
        "name": "Kazatomprom and the world uranium supply concentration",
        "holds": "roughly 40% of world primary uranium supply, from in-situ leach operations with "
                 "long lead times",
        "forced_to": ("produce against long-term contracts and a published guidance range",
                      "pay a subsoil-use tax whose rate is set by legislation and has been "
                      "revised upward"),
        "when": "quarterly reporting; guidance updates as they occur; tax changes at legislation",
        "information": ("its own wellfield development status and sulphuric acid supply, which is "
                        "the real physical constraint"),
        "constraints": ("sulphuric acid availability, an unglamorous and genuinely binding input",
                        "the subsoil-use tax regime",
                        "long-term contract commitments that cap spot availability"),
        "instruments": ("XTIUSD", "US500"),
        "counterparties": ("utilities on long-term contracts", "the spot uranium market"),
        "observables": ("production guidance and its revisions",
                        "quarterly output against guidance",
                        "subsoil-use tax legislation"),
        "impact": "a guidance cut from this producer is a global uranium supply event. THERE IS "
                  "NO URANIUM INSTRUMENT IN THIS REGISTRY, so the mechanism is named and its "
                  "proxies declared rather than pretended into a cell",
        "persistence": "the concentration is structural; the demand side has strengthened with "
                       "nuclear restarts, so the same supply shock has a LARGER price effect each "
                       "year -- the opposite of the palladium case in the Russia pack",
        "falsifier": "there is no clean falsifier on this box, and that is the honest answer. "
                     "This actor is recorded as a NAMED GAP: a mechanism the desk believes in and "
                     "cannot test, which is a verdict and not an absence",
        "notes": "the single name is an ACTOR only",
    },
    {
        "name": "Kazakh base-metals producers (copper, zinc, lead, ferroalloys)",
        "holds": "significant copper, zinc, lead and ferroalloy capacity, power-constrained and "
                 "rail-constrained",
        "forced_to": ("ship by rail through Russia or China, because Kazakhstan is landlocked",
                      "run against a domestic power balance that is genuinely tight"),
        "when": "continuous production; rail capacity is seasonal and politically allocated",
        "information": ("their own output and rail allocation"),
        "constraints": ("landlocked geography -- every tonne crosses a border",
                        "the domestic power balance",
                        "rail-car availability, allocated administratively"),
        "instruments": ("XCUUSD", "XZNUSD", "XALUSD", "XPBUSD"),
        "counterparties": ("Chinese and European smelters and consumers",
                           "the rail operators of Russia and China"),
        "observables": ("monthly production and export statistics",
                        "LME inventory at the delivery points they use",
                        "rail tariff and allocation announcements"),
        "impact": "a second-order metals supply channel; it matters most as a CONTROL, because it "
                  "separates 'Kazakh output fell' from 'the metal rose'",
        "persistence": "structural; the power and rail constraints have tightened rather than "
                       "eased",
        "falsifier": "regress each metal on Kazakh output and on global inventory jointly. If the "
                     "output term is not separately significant, Kazakhstan is a price-taker in "
                     "that metal and this actor is not real for it",
        "notes": "",
    },
    {
        "name": "Kazakh grain exporters and the Central Asian balance",
        "holds": "the swing wheat supply into Central Asia, Afghanistan and Iran",
        "forced_to": ("clear the crop by rail, because there is no port",
                      "accept administrative export restrictions when domestic prices rise"),
        "when": "harvest from August; the export programme runs through the winter; export bans "
                "and rail quotas arrive with little notice",
        "information": ("their own stocks and rail allocations"),
        "constraints": ("rail-car availability, the binding constraint most years",
                        "export bans and quotas, which are administrative and sudden",
                        "competition from Russian wheat moving through the same rail network"),
        "instruments": ("WHEAT", "CORN"),
        "counterparties": ("Uzbek, Tajik, Afghan and Iranian buyers",
                           "Chinese buyers via the land route"),
        "observables": ("monthly export volumes by destination",
                        "export restriction announcements",
                        "the Kazakh-to-Russian wheat price differential"),
        "impact": "an administrative supply shock in a region the world wheat balance usually "
                  "ignores; the effect on the Chicago benchmark is small but the DIRECTION is "
                  "unambiguous when a ban lands",
        "persistence": "the seasonal is structural; the RESTRICTIONS are policy and step",
        "falsifier": "CORN, where the Kazakh share is negligible. A shared response is a grain-"
                     "complex move",
        "notes": "",
    },
    {
        "name": "Kazakh banks in the Russian payment corridor",
        "holds": "correspondent relationships on both sides of a sanctions boundary",
        "forced_to": ("choose between the Russian corridor and dollar correspondent access, "
                      "repeatedly, as enforcement tightens",
                      "de-risk quickly when a secondary-sanctions warning lands"),
        "when": "continuously; the corridor's cost steps with each enforcement round",
        "information": ("their own flow volumes and correspondent warnings"),
        "constraints": ("secondary sanctions risk",
                        "correspondent banking access, withdrawable at short notice",
                        "domestic regulatory expectations pulling the other way"),
        "instruments": ("USDRUB", "USDTRY"),
        "counterparties": ("Russian banks and corporates", "Western correspondent banks"),
        "observables": ("Kazakh-Russian trade statistics, which show the re-export channel",
                        "enforcement announcements and their dates",
                        "the KZT-RUB correlation, which steps rather than drifts"),
        "impact": "the tenge-rouble link is a TRADE AND PAYMENT link, not a macro one; it steps "
                  "with enforcement rather than drifting with fundamentals, which is the same "
                  "shape as the Turkish corridor",
        "persistence": "the channel has persisted through several enforcement rounds and adapted "
                       "each time; each round is a step in cost, not a closure",
        "falsifier": "the Kazakh-Russian trade statistics should step with each enforcement "
                     "round. If they do not, the flow is going somewhere else",
        "notes": "",
    },
    {
        "name": "The Astana International Financial Centre and its common-law jurisdiction",
        "holds": "an English-common-law enclave with its own court, regulator and exchange inside "
                 "a civil-law state",
        "forced_to": ("apply English common law by statute, which is what the enclave is FOR",
                      "maintain a regulatory standard acceptable to foreign counterparties"),
        "when": "continuous; issuance clusters when international markets are open to the region",
        "information": ("its own pipeline of listings"),
        "constraints": ("the enabling constitutional amendment, which is what makes it credible",
                        "the small size of the domestic investor base"),
        "instruments": ("UST10Y",),
        "counterparties": ("international investors in Kazakh sovereign and quasi-sovereign paper",
                           "domestic issuers seeking a credible legal venue"),
        "observables": ("AIX listings and volumes",
                        "the spread on Kazakh sovereign eurobonds",
                        "AIFC court decisions, which are published"),
        "impact": "institutional rather than price: it is why Kazakh credit prices differently "
                  "from its neighbours' despite similar macro, and credit spread is the "
                  "observable that carries it",
        "persistence": "structural since 2018 and untested by a genuine sovereign stress",
        "falsifier": "the Kazakh sovereign spread against a matched regional peer. If the enclave "
                     "adds nothing to the spread, it adds nothing that this desk can measure",
        "notes": "an unusual institution worth recording even though it is not directly tradeable "
                 "here",
    },
    {
        "name": "The Bureau of National Statistics",
        "holds": "the official macro dataset and a published release calendar",
        "forced_to": ("publish CPI in the first days of each month",
                      "revise when the basket is re-weighted annually"),
        "when": "the first days of the month, local time -- and the local-to-UTC mapping CHANGED "
                "on 2024-03-01",
        "information": ("the number before publication"),
        "constraints": ("the statistics law and the release calendar",
                        "a CPI basket re-weighted annually, which breaks long series"),
        "instruments": ("USDRUB",),
        "counterparties": ("the whole market at once", "the National Bank"),
        "observables": ("the CPI release",
                        "the gap between headline and core"),
        "impact": "inflation is the base rate's target, so the CPI print is the largest scheduled "
                  "Kazakh macro event -- and the desk has no instrument on which to measure its "
                  "effect, which is stated rather than worked around",
        "persistence": "permanent as a class",
        "falsifier": "THERE IS NO FALSIFIER AVAILABLE ON THIS BOX, and that is the finding "
                     "rather than an omission: with no Kazakh instrument quoted there is no "
                     "series on which a CPI release reaction could be measured, so the release "
                     "effect is UNMEASURED BY NAME (L1.28a) rather than assumed to be zero",
        "notes": "",
    },
    {
        "name": "Chinese buyers on the Belt and Road land corridor",
        "holds": "the demand side of Kazakh oil, copper and grain moving east by pipeline and rail",
        "forced_to": ("take contracted pipeline volumes",
                      "route around Russia when enforcement makes the northern route expensive, "
                      "which is what the Middle Corridor is"),
        "when": "continuous; the Middle Corridor's volumes are published and grew sharply after "
                "2022",
        "information": ("their own demand and inventory"),
        "constraints": ("pipeline and rail capacity, both finite",
                        "Caspian ferry capacity on the Middle Corridor, the genuine bottleneck"),
        "instruments": ("USDCNH", "XBRUSD", "XCUUSD"),
        "counterparties": ("Kazakh producers", "the rail and shipping operators"),
        "observables": ("Kazakhstan-China pipeline volumes",
                        "Middle Corridor freight volumes",
                        "China customs imports from Kazakhstan"),
        "impact": "a slow structural re-orientation east; it matters to this pack mainly as the "
                  "alternative to the CPC route, which is what makes CPC outages less than fully "
                  "catastrophic",
        "persistence": "growing; the corridor's capacity has expanded every year since 2022",
        "falsifier": "if a CPC outage produced no measurable increase in eastern routing, the "
                     "alternative route is not a real substitute and the outage effect on XBRUSD "
                     "should be LARGER, not smaller",
        "notes": "",
    },
    {
        "name": "Kazakh households and the dollarisation reflex",
        "holds": "tenge deposits with a long memory of two devaluations (2014 and 2015)",
        "forced_to": ("choose between a high deposit rate and a depreciation expectation whenever "
                      "the rate moves",
                      "convert quickly when the memory is triggered, which is why Kazakh "
                      "dollarisation moves in steps rather than trends"),
        "when": "concentrated after large rate or currency moves",
        "information": ("what everyone else has"),
        "constraints": ("the deposit rate differential between tenge and dollar deposits",
                        "deposit insurance rules that deliberately favour tenge deposits"),
        "instruments": ("USDRUB",),
        "counterparties": ("the domestic banks"),
        "observables": ("the deposit dollarisation ratio, published monthly",
                        "the base rate",
                        "cash foreign-currency demand"),
        "impact": "the main channel by which the base rate reaches the currency in an economy "
                  "with a small bond market; de-dollarisation is the National Bank's stated "
                  "objective and the ratio is its scorecard",
        "persistence": "the reflex is a generation old; the LEVEL of dollarisation has fallen "
                       "steadily under a high real rate, so the elasticity is falling too",
        "falsifier": "the same statistic in periods of low real rates. If dollarisation responds "
                     "identically, the rate is not the mechanism",
        "notes": "",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "KZ-A", "title": "Base rate decisions with no instrument to measure them on",
        "objects": ("the eight scheduled decisions", "the corridor",
                    "the monetary policy report", "the NBK analyst survey"),
        "conditions": ("the LOCAL-TO-UTC MAPPING, which changed on 2024-03-01 when the country "
                       "unified onto UTC+5",
                       "the National Fund sale calendar, because the Bank is selling FX in the "
                       "same week it is deciding and the two are confounded",
                       "a survey-based surprise, labelled as such"),
        "instruments": ("XBRUSD", "USDRUB"),
        "controls": ("the eight nearest non-meeting days at the same UTC minute",
                     "USDRUB, which shares the regional risk factor but not the Kazakh decision",
                     "the National Fund sale volume as a second conditioner, to separate the "
                     "policy event from the sovereign flow",
                     "the pre-2024-03-01 sample under BOTH UTC mappings, to demonstrate that the "
                     "zone change matters"),
        "notes": "there is no Kazakh instrument here. Every cell terminates in a foreign symbol "
                 "and says so; this domain exists to make that explicit rather than to pretend",
    },
    {
        "id": "KZ-B", "title": "The announced sovereign FX sale, net of the pension fund",
        "objects": ("the monthly announced National Fund sale volume",
                    "the later actual volume",
                    "the pension fund's published foreign-asset purchases",
                    "the NET of the two"),
        "conditions": ("the NET, always -- the sale leg alone over-states the sovereign flow",
                       "announcement and execution as two separate events",
                       "the budget cycle, because the transfer size is set in the budget law and "
                       "revised at supplementary budget"),
        "instruments": ("USDRUB", "XBRUSD"),
        "controls": ("months where the net is near zero",
                     "the announced-minus-actual difference as its own series",
                     "the same statistic on the Russian budget rule, a structurally identical "
                     "mechanism in a neighbouring economy",
                     "the pre-2017 sample, before the announcement practice began"),
        "notes": "the offsetting leg is PUBLISHED here, which Russia's is not; that makes "
                 "Kazakhstan the better test bed for whether an announced sovereign order moves "
                 "anything at all",
    },
    {
        "id": "KZ-C", "title": "CPC loadings as a dated global crude supply interruption",
        "objects": ("the monthly CPC loading programme",
                    "suspension announcements and their first public timestamp",
                    "the mooring-point count in service",
                    "Black Sea weather seasonality"),
        "conditions": ("the FIRST PUBLIC REPORT as the event time -- shipping agents frequently "
                       "report before the consortium does",
                       "the duration of the suspension, which is what sizes the supply loss",
                       "whether the eastern routes absorbed any of the volume",
                       "the season, because winter storms are a recurring cause"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "controls": ("XTIUSD, which shares the global price but not the Black Sea route -- a "
                     "Brent-specific response is the route and a shared one is a price move",
                     "storm days with no suspension",
                     "the same statistic on other single-terminal outages worldwide",
                     "a placebo suspension calendar"),
        "notes": "THE PACK'S LARGEST TRANSMISSION. Roughly 1.5% of world crude leaves through one "
                 "terminal, and the terminal is in another country",
    },
    {
        "id": "KZ-D", "title": "OPEC+ quota, contractual volumes and the compensation schedule",
        "objects": ("monthly production against quota",
                    "the published compensation schedule for overproduction",
                    "Tengiz expansion volumes",
                    "the production-sharing agreements that bind the state"),
        "conditions": ("the compensation schedule treated as a DATED FUTURE supply constraint, "
                       "which is what it is -- a rare object",
                       "the expansion delivery schedule, which has slipped repeatedly",
                       "whether the quota was actually enforced, which varies"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "controls": ("other OPEC+ members with no comparable foreign-operator structure",
                     "the pre-2020 sample, before the compensation mechanism existed",
                     "months with no compensation obligation",
                     "the announcement-versus-effective distinction on each schedule"),
        "notes": "a supply reduction whose timing is published in advance is unusual enough to be "
                 "worth a domain of its own",
    },
    {
        "id": "KZ-E", "title": "Uranium supply concentration as a NAMED GAP",
        "objects": ("Kazatomprom production guidance and its revisions",
                    "the subsoil-use tax regime",
                    "sulphuric acid availability, the physical constraint",
                    "long-term contract coverage"),
        "conditions": ("this domain has NO INSTRUMENT on this box and says so",
                       "the demand trend, which is strengthening with nuclear restarts, so the "
                       "same supply shock has a larger effect each year",
                       "guidance revisions rather than output levels"),
        "instruments": ("XTIUSD", "US500"),
        "controls": ("there is no clean control available here, which is the honest answer",
                     "the energy complex generally, as a weak proxy",
                     "a placebo guidance-revision calendar"),
        "notes": "recorded as UNMEASURED BY NAME rather than omitted (L1.28a). A mechanism the "
                 "desk believes in and cannot test is a verdict; leaving it out would be an "
                 "absence pretending to be a decision",
    },
    {
        "id": "KZ-F", "title": "Base metals: a landlocked price-taker",
        "objects": ("copper, zinc, lead and ferroalloy output",
                    "rail-car allocation and tariffs",
                    "the domestic power balance",
                    "LME inventory at the relevant delivery points"),
        "conditions": ("output and global inventory entered jointly, because the question is "
                       "whether Kazakhstan is a price-maker in any of these metals",
                       "rail and power constraints as the supply-side conditioners",
                       "the export destination split, which changed after 2022"),
        "instruments": ("XCUUSD", "XZNUSD", "XALUSD", "XPBUSD"),
        "controls": ("global inventory alone, as the null",
                     "the same regression for a metal where the Kazakh share is negligible",
                     "months with no rail or power constraint",
                     "a matched non-Kazakh producer country"),
        "notes": "",
    },
    {
        "id": "KZ-G", "title": "Grain: administrative supply shocks in a region nobody watches",
        "objects": ("the August harvest and the winter export programme",
                    "export bans and rail quotas, which arrive with little notice",
                    "the Kazakh-to-Russian wheat price differential",
                    "Central Asian and Afghan demand"),
        "conditions": ("restriction ANNOUNCEMENTS rather than production levels",
                       "the rail constraint, which binds most years",
                       "Russian wheat competing through the same rail network"),
        "instruments": ("WHEAT", "CORN"),
        "controls": ("CORN, where the Kazakh share is negligible",
                     "the northern-hemisphere harvest seasonal, which must be removed",
                     "months with no restriction",
                     "the Russian export-duty calendar, a competing shock in the same complex"),
        "notes": "",
    },
    {
        "id": "KZ-H", "title": "The tenge as a transmission target",
        "objects": ("USDKZT, absent from this broker's registry",
                    "the official rate from the KASE morning session, effective the next day",
                    "the tenge's oil beta",
                    "the tenge-rouble correlation"),
        "conditions": ("this domain is DECLARED UNMEASURED on this box",
                       "the next-day effective date, for whoever does get a quote",
                       "the rouble correlation as a TRADE AND PAYMENT link that steps with "
                       "enforcement rather than drifting with fundamentals"),
        "instruments": ("XBRUSD", "USDRUB", "USDCNH"),
        "controls": ("USDRUB as the nearest available regional proxy",
                     "XBRUSD as the oil leg",
                     "the enforcement-round calendar as the conditioning variable for the "
                     "correlation"),
        "notes": "included and declared rather than omitted, so that a later session with a quote "
                 "inherits the mechanics instead of rediscovering them",
    },
    {
        "id": "KZ-I", "title": "The Russian payment and re-export corridor",
        "objects": ("Kazakh-Russian trade statistics and their step changes",
                    "enforcement announcements and their dates",
                    "correspondent banking access",
                    "parallel-import flows"),
        "conditions": ("enforcement rounds as STEPS, not as a continuous variable",
                       "the trade statistics as the observable, because the payment flow itself "
                       "is invisible",
                       "the direction of re-export, which reversed for some goods"),
        "instruments": ("USDRUB", "USDTRY", "USDCNH"),
        "controls": ("the Turkish corridor, a structurally identical channel -- if both step at "
                     "the same enforcement dates, the mechanism is enforcement and not geography",
                     "regional currencies with no such corridor",
                     "the pre-2022 sample"),
        "notes": "this domain and the Turkish one in the TR pack are the same mechanism in two "
                 "places; measuring them together is the strongest available test",
    },
    {
        "id": "KZ-J", "title": "The Middle Corridor and the eastward re-orientation",
        "objects": ("Trans-Caspian freight volumes",
                    "Caspian ferry capacity, the genuine bottleneck",
                    "the Kazakhstan-China pipeline",
                    "China customs imports from Kazakhstan"),
        "conditions": ("capacity rather than demand as the binding constraint",
                       "the substitution against the northern route, which is the whole point",
                       "the link into the Azerbaijani and Turkish packs, since the corridor "
                       "physically runs through both"),
        "instruments": ("USDCNH", "XBRUSD", "USDTRY"),
        "controls": ("northern-route volumes over the same period",
                     "the pre-2022 sample, when the corridor was marginal",
                     "a CPC-outage-matched sample, testing whether eastern routing absorbs the "
                     "volume"),
        "notes": "",
    },
    {
        "id": "KZ-K", "title": "The Kazakh calendar: Nauryz, transfers and a moved time zone",
        "objects": ("Nauryz on 21, 22 and 23 March, the largest closure of the Kazakh year",
                    "the weekend-transfer rule and the annual bridging decree",
                    "Kurban Ait, proclaimed rather than computed",
                    "the 2024-03-01 unification onto UTC+5"),
        "conditions": ("the decree's bridging transfers declared UNMEASURED rather than guessed",
                       "Kurban Ait read from the table",
                       "the zone change applied to every pre-2024 event window"),
        "instruments": ("USDRUB", "XBRUSD"),
        "controls": ("the same statistic on Russian and Azerbaijani holidays, which overlap "
                     "partially and differ in detail",
                     "days when Kazakhstan is closed and Russia is open",
                     "the zone-change boundary as a natural experiment on the clock"),
        "notes": "the zone change is the kind of fact that is invisible until it has already "
                 "ruined a result; it is a domain object here for exactly that reason",
    },
    {
        "id": "KZ-L", "title": "The AIFC common-law enclave and Kazakh credit",
        "objects": ("the AIFC's English-common-law jurisdiction and its court",
                    "AIX listings",
                    "Kazakh sovereign and quasi-sovereign eurobond spreads",
                    "published AIFC court decisions"),
        "conditions": ("credit spread against a matched regional peer as the observable",
                       "the enclave untested by a genuine sovereign stress, so the evidence is "
                       "thin by construction"),
        "instruments": ("UST10Y", "US500"),
        "controls": ("a matched regional sovereign with no such enclave",
                     "the pre-2018 sample, before the AIFC existed",
                     "global EM credit spreads, to remove the risk factor"),
        "notes": "institutional rather than price; recorded because an unusual legal structure is "
                 "a real and rare research object even when it is hard to trade",
    },
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "kz_cpc_outage_event_study", "domain_ids": ("KZ-C",), "kind": "event",
     "cadence_s": 3600.0, "steerable": False, "wired": False,
     "entry": "countries.kz.miners:cpc_outage_event_study",
     "needs": ("CPC status announcements with first-public timestamps",
               "XBRUSD and XTIUSD M15 bars"),
     "notes": "uses the FIRST PUBLIC REPORT as the event time, not the press release; reports the "
              "XTIUSD control before the XBRUSD result"},
    {"name": "kz_sovereign_flow_net", "domain_ids": ("KZ-B",), "kind": "flow",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.kz.miners:sovereign_flow_net",
     "needs": ("NBK monthly FX sale announcements", "pension fund purchase schedule",
               "USDRUB and XBRUSD D1 bars"),
     "notes": "nets the two legs; refuses a sale-only measurement because it is known in advance "
              "to over-state the sovereign flow"},
    {"name": "kz_base_rate_confounded", "domain_ids": ("KZ-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.kz.miners:base_rate_confounded",
     "needs": ("NBK decision dates with local timezone at release", "XBRUSD and USDRUB M15 bars"),
     "notes": "applies the correct local-to-UTC mapping either side of 2024-03-01 and conditions "
              "on the National Fund sale calendar"},
    {"name": "kz_opec_compensation_schedule", "domain_ids": ("KZ-D",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.kz.miners:opec_compensation_schedule",
     "needs": ("published compensation schedules", "XBRUSD D1 bars"),
     "notes": "treats the schedule as a dated FUTURE supply constraint and tests the announcement "
              "and the effective month separately"},
    {"name": "kz_metals_price_taker_test", "domain_ids": ("KZ-F",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.kz.miners:metals_price_taker_test",
     "needs": ("Kazakh output statistics", "XCUUSD, XZNUSD, XALUSD, XPBUSD D1 bars"),
     "notes": "the null is that Kazakhstan is a price-taker; the miner must beat it"},
    {"name": "kz_grain_restriction_events", "domain_ids": ("KZ-G",), "kind": "policy",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.kz.miners:grain_restriction_events",
     "needs": ("export restriction announcements", "WHEAT and CORN D1 bars"),
     "notes": "runs against the Russian export-duty calendar as a competing shock"},
    {"name": "kz_corridor_enforcement_steps", "domain_ids": ("KZ-I", "KZ-J"), "kind": "policy",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.kz.miners:corridor_enforcement_steps",
     "needs": ("enforcement announcement dates", "trade statistics", "USDRUB and USDTRY D1 bars"),
     "notes": "measures the Kazakh and Turkish corridors TOGETHER; a step in both at the same "
              "dates is the strongest available evidence that enforcement is the mechanism"},
    {"name": "kz_calendar_and_clock", "domain_ids": ("KZ-K",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.kz.miners:calendar_and_clock",
     "needs": ("the Kazakh holiday calendar", "the 2024-03-01 zone change", "USDRUB H1 bars"),
     "notes": "publishes the zone-change boundary as a natural experiment and flags any event "
              "window that straddles it"},
)

# --------------------------------------------------------------------------- transmission edges
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "CPC loading suspension at Novorossiysk", "target": "XBRUSD", "sign": "+",
     "mechanism": "roughly 1.5% of world crude leaves through one terminal; a suspension is a "
                  "physical, dated supply interruption announced with hours of notice",
     "horizon": "0 to 5 sessions",
     "condition": "the FIRST PUBLIC REPORT is the event time, which is often a shipping agent "
                  "rather than the consortium",
     "control": "XTIUSD, which shares the global price but not the Black Sea route",
     "falsifier": "an equal XTIUSD response, which would make it a global price move"},
    {"source": "Tengiz and Kashagan expansion volumes", "target": "XBRUSD", "sign": "-",
     "mechanism": "contractually committed expansion volumes arrive whether or not the OPEC+ "
                  "quota allows them, so the supply is known years ahead and is inelastic",
     "horizon": "60 to 250 sessions",
     "condition": "delivery slippage must be modelled; these projects have slipped repeatedly",
     "control": "other non-OPEC supply additions over the same period",
     "falsifier": "no price response to a delivered expansion, which would mean the market had "
                  "fully priced the announced schedule"},
    {"source": "Kazakh OPEC+ compensation schedule", "target": "XBRUSD", "sign": "+",
     "mechanism": "a published, dated future supply reduction to offset past overproduction -- "
                  "unusually, a supply cut whose timing is known in advance",
     "horizon": "the compensation months",
     "condition": "only where the quota was actually enforced; enforcement has varied",
     "control": "other members' compensation schedules over the same months",
     "falsifier": "no response to a schedule the market can read, which would mean compensation "
                  "is not believed"},
    {"source": "NBK announced National Fund FX sale, net of pension fund purchases",
     "target": "USDRUB", "sign": "-",
     "mechanism": "a sovereign FX sale lands on the domestic exchange; the tenge is not quoted "
                  "here, so the regional proxy carries whatever spillover exists",
     "horizon": "the execution month",
     "condition": "the NET of both legs; and this edge is WEAK by construction because the target "
                  "is a proxy, which is stated rather than hidden",
     "control": "months where the net is near zero",
     "falsifier": "no measurable spillover into any quoted instrument, which would confirm that "
                  "the Kazakh sovereign flow is unmeasurable on this box"},
    {"source": "Kazatomprom production guidance revision", "target": "XTIUSD", "sign": "+",
     "mechanism": "a uranium supply cut raises the cost of the nuclear alternative and, weakly, "
                  "the value of competing energy; there is NO uranium instrument here, so this "
                  "edge is a declared weak proxy",
     "horizon": "20 to 120 sessions",
     "condition": "declared WEAK: the proxy relationship is indirect and the edge exists to name "
                  "the gap rather than to claim an effect",
     "control": "energy complex generally; a placebo guidance calendar",
     "falsifier": "no measurable relationship, which is the expected outcome and would confirm "
                  "the gap is real rather than merely unmeasured"},
    {"source": "Kazakh copper and zinc output", "target": "XCUUSD", "sign": "-",
     "mechanism": "a landlocked producer whose rail and power constraints bind; the question is "
                  "whether the output is large enough to be a price-maker in any of these metals",
     "horizon": "20 to 90 sessions",
     "condition": "entered jointly with global inventory; the null is price-taking",
     "control": "global inventory alone",
     "falsifier": "no separate significance for Kazakh output, which would confirm price-taking"},
    {"source": "Kazakh grain export restriction announcement", "target": "WHEAT", "sign": "+",
     "mechanism": "the swing supplier into Central Asia and Afghanistan withdraws; the effect on "
                  "the Chicago benchmark is small but the direction is unambiguous",
     "horizon": "1 to 20 sessions",
     "condition": "announcements, not production levels; the northern-hemisphere seasonal removed",
     "control": "CORN, where the Kazakh share is negligible",
     "falsifier": "an equal corn response, which would make it a grain-complex move"},
    {"source": "Enforcement rounds on the Kazakh-Russian payment corridor", "target": "USDRUB",
     "sign": "two_sided",
     "mechanism": "the corridor's cost steps with each enforcement round; the re-export channel "
                  "narrows and Russian import costs rise",
     "horizon": "5 to 60 sessions",
     "condition": "enforcement dates as STEPS; the trade statistics are the observable because "
                  "the payment flow is invisible",
     "control": "the Turkish corridor at the same dates -- a step in both is enforcement and not "
                "geography",
     "falsifier": "no step in either corridor's trade statistics at enforcement dates"},
    {"source": "Middle Corridor freight volumes", "target": "USDCNH", "sign": "-",
     "mechanism": "China-Europe freight re-routing away from Russia through Kazakhstan, the "
                  "Caspian, Azerbaijan and Turkey; capacity, not demand, is the constraint",
     "horizon": "60 to 250 sessions",
     "condition": "Caspian ferry capacity as the binding variable",
     "control": "northern-route volumes over the same period",
     "falsifier": "corridor growth with no corresponding northern-route decline, which would mean "
                  "it is new trade rather than re-routed trade"},
    {"source": "Kazakh base rate decision", "target": "USDRUB", "sign": "-",
     "mechanism": "the regional risk and policy factor; Kazakhstan and Russia share investors, a "
                  "payment corridor and an oil exposure, so a Kazakh tightening carries weak "
                  "regional information",
     "horizon": "0 to 5 sessions",
     "condition": "the correct local-to-UTC mapping either side of 2024-03-01; and the National "
                  "Fund sale calendar as a second conditioner",
     "control": "the eight nearest non-meeting days at the same UTC minute",
     "falsifier": "an equal move on non-meeting days, which would make it the hour"},
    {"source": "NBK priority purchase of domestic gold output", "target": "XAUUSD", "sign": "+",
     "mechanism": "the central bank exercises a priority right over domestically produced gold, "
                  "withholding mine supply from the market by official policy",
     "horizon": "60 to 250 sessions",
     "condition": "conditioned on total reserve growth, so a composition shift is not read as new "
                  "demand",
     "control": "XAGUSD, where no comparable official demand exists",
     "falsifier": "an equal silver response, which would make it a precious-complex move"},
    {"source": "Kazakh domestic power constraint", "target": "XALUSD", "sign": "+",
     "mechanism": "aluminium and ferroalloy smelting is power-intensive and the domestic balance "
                  "is genuinely tight; a constraint caps output directly",
     "horizon": "20 to 90 sessions",
     "condition": "only in constrained periods, which are published",
     "control": "XCUUSD, which is less power-intensive per tonne",
     "falsifier": "an equal copper response, which would make it a general metals move"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the managed band and the two devaluations", "start": "2014-02-11",
     "end": "2015-08-19",
     "regime": "a defended band, devalued in February 2014 and abandoned in August 2015",
     "markers": ("2014-02-11 the first devaluation", "2015-08-20 the float"),
     "why_it_matters": "the household dollarisation reflex that still drives KZ-A's transmission "
                       "channel was formed here; a pre-2015 currency series is a different "
                       "regime entirely",
     "status": "SETTLED"},
    {"name": "inflation targeting and de-dollarisation", "start": "2015-08-20",
     "end": "2020-02-29",
     "regime": "a free float, the base rate introduced in September 2015, and a sustained "
               "campaign to reduce deposit dollarisation under a high real rate",
     "markers": ("2015-09 the base rate introduced", "the dollarisation ratio falling steadily"),
     "why_it_matters": "the only era in which the framework operated without an external shock; "
                       "the baseline for every Kazakh reaction-function estimate",
     "status": "SETTLED"},
    {"name": "pandemic and the oil collapse", "start": "2020-03-01", "end": "2022-01-04",
     "regime": "rates cut and then raised as inflation returned; National Fund transfers "
               "increased to support the budget",
     "markers": ("2020-04 the OPEC+ production collapse",),
     "why_it_matters": "the National Fund's sale programme was at its largest here, which makes "
                       "it the best sample for KZ-B",
     "status": "SETTLED"},
    {"name": "January unrest and the February shock next door", "start": "2022-01-05",
     "end": "2022-12-31",
     "regime": "domestic unrest in January, then the sanctions shock on Kazakhstan's principal "
               "export route and payment corridor in February; an emergency rate increase and "
               "temporary controls",
     "markers": ("2022-01 the unrest", "2022-02-24", "2022-03 CPC loading interruptions"),
     "why_it_matters": "both of this pack's largest mechanisms -- the export route and the "
                       "payment corridor -- became political risks in the same year. Nothing may "
                       "be pooled across this",
     "status": "SETTLED"},
    {"name": "corridor, Middle Corridor and the Tengiz expansion", "start": "2023-01-01",
     "end": "2024-02-29",
     "regime": "the re-export corridor at its widest, Middle Corridor volumes growing, the "
               "Tengiz expansion approaching delivery, and repeated OPEC+ overproduction",
     "markers": ("Middle Corridor volumes roughly doubling",
                 "recurring OPEC+ compensation obligations"),
     "why_it_matters": "the era in which Kazakhstan's transmission channels re-oriented; the "
                       "corridor and quota mechanisms in KZ-D and KZ-I are fitted here",
     "status": "SETTLED"},
    {"name": "one time zone, and after", "start": "2024-03-01", "end": "2099-12-31",
     "regime": "the country unified onto UTC+5 on 1 March 2024; the Tengiz expansion delivering; "
               "enforcement rounds tightening the payment corridor",
     "markers": ("2024-03-01 the zone unification -- every Kazakh event's UTC minute moves",),
     "why_it_matters": "UNVERIFIED TAIL for anything after mid-2025, and the era boundary that "
                       "breaks every pre-2024 event window. The zone change is an economics-free "
                       "break in the clock, which is the easiest kind to miss and the hardest to "
                       "detect after the fact",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no Kazakh instrument is quoted by this broker",
     "measured": "USDKZT, the KASE index and every Kazakh bond are absent from "
                 "data/universe/universe.json",
     "consequence": "this pack is TRANSMISSION-ONLY by construction. Every domain terminates in a "
                    "foreign symbol, and KZ-H exists to declare the tenge UNMEASURED rather than "
                    "to work around it"},
    {"constraint": "there is no uranium instrument",
     "measured": "no uranium contract in the universe registry",
     "consequence": "the single largest Kazakh supply concentration -- roughly 40% of world "
                    "uranium -- is a NAMED GAP. KZ-E is recorded as UNMEASURED by name rather "
                    "than omitted, because an absence pretending to be a decision is worse than "
                    "a declared gap (L1.28a)"},
    {"constraint": "KASE and AIX data are licensed and the desk holds no licence",
     "measured": "kase.kz and aix.kz publish headline figures; trade-level data is licensed",
     "consequence": "the official USDKZT rate, exchange volumes and participant structure are all "
                    "UNMEASURED; the sovereign's sales land somewhere the desk cannot see"},
    {"constraint": "no tenge positioning series exists anywhere",
     "measured": "no CME contract has ever existed for KZT",
     "consequence": "tenge positioning is permanently UNMEASURED; cot_currency on this pack is "
                    "deliberately empty and no other currency's COT may be substituted"},
    {"constraint": "the local-to-UTC mapping changed on 2024-03-01",
     "measured": "Kazakhstan unified onto UTC+5; Astana and Almaty were UTC+6 before that date",
     "consequence": "every pre-2024 Kazakh event window must use the +6 mapping and every later "
                    "one the +5 mapping. A single mapping across the boundary puts half the "
                    "sample in the wrong bar, and the error is invisible in the data"},
    {"constraint": "the holiday list has been amended more than once",
     "measured": "the Labour Code's holiday schedule has changed in recent years and the annual "
                 "bridging decree is not derivable",
     "consequence": "HOLIDAYS_RULE carries a DECLARED set flagged for verification; the decree's "
                    "extra transfers are UNMEASURED and a miner needing the exact working "
                    "calendar must read the decree"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, carrying the transmission targets and access constraints
    alongside the frozen fields."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "datasets": DATASETS, "source_layers": SOURCE_LAYERS,
        "layer_absences": LAYER_ABSENCES, "layer_terms": layer_terms(),
        "source_layer_coverage": source_layer_coverage(),
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "cot_currency": COT_CURRENCY,
    }


def pack() -> Any:
    """`libs.research.country_lab.CountryPack` when that module has landed, else this mapping."""
    data = as_dict()
    try:
        from libs.research import country_lab
    except ImportError:
        return data
    cls = getattr(country_lab, "CountryPack", None)
    if cls is None:
        return data
    try:
        return cls(**{k: v for k, v in data.items() if k in _PACK_FIELDS})
    except (TypeError, ValueError):
        return data
