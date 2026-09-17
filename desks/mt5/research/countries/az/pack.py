"""AZERBAIJAN: a constant exchange rate, a published sovereign sale, and two pipelines.

WHAT AZERBAIJAN IS AS A MARKET MECHANISM. The organising fact is that THE PRICE CARRIES NO
INFORMATION. AZN has been held at 1.7000 to the dollar since 2017, so the exchange rate is a
policy constant and every question worth asking is about what maintains it. Four mechanisms
follow, and each is a domain below:

  1. THE PEG IS MAINTAINED BY A PUBLISHED AUCTION. The State Oil Fund (Dovlet Neft Fondu, SOFAZ)
     sells dollars at auctions organised by the Central Bank, and the results -- volume,
     participants, rate -- are published. A pegged currency whose DEFENCE is a dated, sized,
     public sovereign sale is a far better research object than the flat price series suggests:
     the auction volume is the peg's stress gauge, and it moves when the oil price moves.

  2. THE PEG'S FISCAL BACKING IS KNOWN IN ADVANCE. The Fund's transfer to the state budget is set
     in the budget law, the Fund's assets are reported quarterly, and the budget's break-even oil
     price is calculable. So the question "can the peg hold at this oil price?" has a published
     answer, updated on a known calendar. AZ-B is built on it.

  3. AZERBAIJAN EARNS ON PRICE WHERE GEORGIA EARNS ON VOLUME. Azeri Light leaves through BTC
     across Georgia to Ceyhan; Shah Deniz gas leaves through the Southern Gas Corridor across
     Georgia and Turkey to Italy. Azerbaijan's receipts scale with the PRICE of those barrels and
     molecules while Georgia's transit fees scale with their VOLUME. The two packs are a matched
     exposure pair and are written to be read together: a shock that moves both the same way is
     regional, and one that moves them oppositely is the price-versus-volume mechanism working.

  4. GAS BECAME A EUROPEAN POLICY VARIABLE. After 2022 Azerbaijani gas to Europe stopped being a
     minor diversification story and became the only non-Russian Caspian pipeline route the EU
     has. Volumes, contracts and expansion commitments are published and politically dated.

WHAT IS EXECUTABLE. Nothing Azerbaijani. AZN is ABSENT from `data/universe/universe.json`, as is
every Azerbaijani bond and the Baku Stock Exchange. This pack is TRANSMISSION-ONLY: every domain
terminates in XBRUSD, XTIUSD, XNGUSD, USDTRY, USDRUB, XAUUSD, EUSTX50, GER40 or USDCNH.

THE PEG IS THE PACK'S CENTRAL CAUTION. Because AZN does not move, any statistical test on it will
report a variance near zero and a Sharpe that is meaningless. AZ-A exists to say that explicitly:
the correct object is the AUCTION VOLUME and the BREAK-EVEN PRICE, not the rate, and a cell
fitted to a constant is not a discovery.

THE CALENDAR IS THREE CALENDARS. Novruz runs five days in March; Ramazan and Qurban bayrami are
lunar and PROCLAIMED rather than computed; and the fixed dates are a mix of Soviet-era and
independence observances. When holidays coincide or fall at a weekend, Azerbaijani labour law
TRANSFERS the day off -- a rule Georgia next door does not have, which is exactly the kind of
neighbour-to-neighbour difference an imported calendar gets wrong.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# ruff: noqa: RUF001
# RUF001 flags Cyrillic characters that resemble Latin ones. The rule guards IDENTIFIERS
# against homoglyph attacks; this file carries Azerbaijani and Russian terminology as DATA.
# No identifier in this module is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "AZ"
NAME = "Republic of Azerbaijan"
REGION_COMMAND = "russia_cis"
REGION_DESK = "CAUCASUS"
CURRENCY = "AZN"
FISCAL_YEAR_END = "12-31"
NATIVE_LANGUAGES: tuple[str, ...] = ("az", "ru")

#: TRANSMISSION-ONLY. No Azerbaijani instrument is quoted here. Nothing here is an equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD",            # Azeri Light through BTC to Ceyhan
    "XNGUSD",                      # Shah Deniz through the Southern Gas Corridor
    "USDTRY",                      # Turkey is the corridor terminus and the largest partner
    "USDRUB",                      # the northern trade and remittance link
    "XAUUSD", "XAGUSD",            # SOFAZ holds gold and the household reflex runs to it
    "USDCNH",                      # the Middle Corridor freight link
    "EUSTX50", "GER40",            # the European end of the gas corridor
    "WHEAT",                       # a large wheat importer: the food-price channel runs inward
    "XCUUSD",                      # regional metals
    "USDX", "EURUSD",              # the dollar factor; the peg makes this the binding one
    "US500", "UST10Y",             # global risk and duration controls
)

#: Everything Azerbaijani. Each names the universe symbols its mechanism reaches.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USDAZN (manat)", "venue": "CBA auctions and interbank",
     "why": "ABSENT from data/universe/universe.json, and PEGGED at 1.7000 since 2017 in any case. "
            "The price carries no information; the auction volume defending it does",
     "proxies": ("XBRUSD", "USDTRY", "USDRUB")},
    {"name": "SOFAZ FX auctions at the Central Bank", "venue": "CBA",
     "why": "THE PEG'S MAINTENANCE MECHANISM, published: volume, participants and rate. The "
            "auction volume is the peg's stress gauge and it moves with the oil price",
     "proxies": ("XBRUSD", "USDTRY")},
    {"name": "SOFAZ assets and the budget transfer", "venue": "SOFAZ / Ministry of Finance",
     "why": "the peg's fiscal backing, known in advance from the budget law and reported "
            "quarterly; the budget break-even oil price is calculable from it",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "Central Bank of Azerbaijan refinancing rate (ucot derecesi)", "venue": "CBA",
     "why": "the policy rate and its corridor. Under a peg the rate is a LIQUIDITY instrument "
            "rather than an exchange-rate one, which is the opposite of its role in Georgia",
     "proxies": ("USDTRY", "USDRUB")},
    {"name": "Azeri-Chirag-Gunashli production and Azeri Light exports",
     "venue": "BP-operated consortium",
     "why": "the mature core oil field; production has been declining for years and the decline "
            "rate is published, which makes it a KNOWN future supply reduction",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "Baku-Tbilisi-Ceyhan (BTC) pipeline throughput", "venue": "BTC Co.",
     "why": "the crude export route across Georgia to the Turkish Mediterranean; an interruption "
            "is a physical supply event shared with the Georgian pack",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "Shah Deniz and the Southern Gas Corridor (SCP, TANAP, TAP)",
     "venue": "consortium / TANAP / TAP",
     "why": "Europe's only non-Russian Caspian pipeline route; volumes, contracts and expansion "
            "commitments are published and politically dated",
     "proxies": ("XNGUSD", "EUSTX50", "GER40", "USDTRY")},
    {"name": "Baku Stock Exchange and Azerbaijani sovereign eurobonds", "venue": "BSE / LSE",
     "why": "the domestic market is small; the sovereign eurobond spread is the only liquid "
            "Azerbaijani credit observable and it is not quoted here",
     "proxies": ("UST10Y", "US500")},
    {"name": "Middle Corridor freight through Baku and the Caspian",
     "venue": "ADY / Baku International Sea Trade Port",
     "why": "the Trans-Caspian route from Kazakhstan to Turkey passes through Baku; Caspian ferry "
            "capacity is the bottleneck and links this pack to the Kazakh one",
     "proxies": ("USDCNH", "USDTRY")},
    {"name": "Azerbaijani gas swap arrangements with neighbours", "venue": "SOCAR",
     "why": "swap and re-export arrangements complicate the physical accounting of who supplies "
            "whom; a volume attributed to Azerbaijani production may be a swapped molecule",
     "proxies": ("XNGUSD", "USDTRY", "USDRUB")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of the Republic of Azerbaijan (Azerbaycan Respublikasinin Merkezi Banki)",
    "short": "CBA",
    "framework": "peg",
    "committee": "Management Board",
    "policy_instrument": "the refinancing rate (ucot derecesi) with an interest-rate corridor; "
                         "under the peg this is a LIQUIDITY instrument, not an exchange-rate one",
    "corridor": "a floor (deposit) and ceiling (lending) rate either side of the refinancing rate",
    "mandate": "price stability; in practice the de-facto US dollar peg at 1.7000 has been the "
               "operational anchor since 2017",
    "decision_rule": "scheduled decisions through the year with a published statement; the "
                     "decision calendar is announced in advance",
    "announce_local": "about 15:00 Asia/Baku",
    "announce_utc": "11:00",
    "announce_utc_dst": "11:00",
    "dst_rule": "NONE. Azerbaijan abolished seasonal clock changes in 2016 and Baku is a fixed "
                "UTC+4. Azerbaijani event minutes in UTC are stable all year",
    "presser_utc": "12:00",
    "minutes_lag_days": 0,
    "consensus_proxy": "NONE, AND NONE IS NEEDED IN THE USUAL SENSE. With a pegged rate the "
                       "market-relevant surprise is not the policy rate but the AUCTION VOLUME "
                       "and the budget break-even price. A rate-surprise study here would be "
                       "measuring an instrument that is not doing the work",
    "consensus_proxy_trap": "THE PEG ITSELF IS THE TRAP. Any statistical test on AZN reports a "
                            "variance near zero and a meaningless Sharpe. A cell fitted to a "
                            "constant is not a discovery, and AZ-A exists to refuse it",
    "distinctive": "the exchange rate is a POLICY CONSTANT maintained by a PUBLISHED sovereign "
                   "auction. Nowhere else in this department is the defence of a currency a dated, "
                   "sized, public event while the currency itself never moves",
    "balance_sheet_history": (
        "February 2015: a step devaluation from 0.7844 to 1.05 per dollar",
        "December 2015: a float announced, followed by a fall to about 1.55",
        "2017 onward: a de-facto re-peg at 1.7000, maintained by SOFAZ auctions ever since",
        "reserve composition includes gold, held by both the Bank and the Fund"),
    "off_cycle": "the two 2015 devaluations were the defining off-cycle events and both were "
                 "step changes announced without notice; each is its own class",
    "other_clocks": (
        {"what": "SOFAZ FX auction results", "when_local": "auction days",
         "when_utc": "11:00", "reference_lag_days": 0},
        {"what": "SOFAZ quarterly report and asset total", "when_local": "quarterly",
         "when_utc": "10:00", "reference_lag_days": 30},
        {"what": "monthly CPI from the State Statistical Committee",
         "when_local": "the first days of the month", "when_utc": "06:00",
         "reference_lag_days": 5},
        {"what": "the budget law and its oil-price assumption", "when_local": "December",
         "when_utc": "10:00", "reference_lag_days": 0},
    ),
    "root": "https://www.cbar.az",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CBA official AZN/USD rate",
     "local": "published each business day; HELD AT 1.7000 since 2017",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none (Baku is fixed UTC+4)",
     "instruments": (), "window_minutes": 30, "confidence": "SETTLED",
     "why": "a constant. Recorded so that no session mistakes the flat series for a measured "
            "market outcome: the rate is an administrative decision, not a price"},
    {"name": "SOFAZ FX auction at the Central Bank",
     "local": "auction days, results published the same day",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "USDTRY"), "window_minutes": 60,
     "confidence": "DECLARED, VERIFY against cbar.az and oilfund.az",
     "why": "THE OBJECT THAT MATTERS. The auction volume is the peg's stress gauge; it rises when "
            "the oil price falls and the budget needs more manat"},
    {"name": "Brent dated, the reference for Azeri Light",
     "local": "the London afternoon assessment", "time_utc": "16:30", "time_utc_dst": "15:30",
     "dst_rule": "GMT/BST", "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "confidence": "SETTLED",
     "why": "Azeri Light is a light sweet grade loading at Ceyhan and prices at a PREMIUM to "
            "Brent -- the opposite of the Urals discount in the Russia pack, and a useful "
            "contrast: one Caspian grade trades above the benchmark and one below, for reasons "
            "that are quality in one case and sanctions in the other"},
    {"name": "TTF and the European gas benchmark for Southern Gas Corridor volumes",
     "local": "the European gas trading day", "time_utc": "16:00", "time_utc_dst": "15:00",
     "dst_rule": "CET/CEST", "instruments": ("XNGUSD", "EUSTX50", "GER40"),
     "window_minutes": 60, "confidence": "DECLARED",
     "why": "Azerbaijani gas to Europe prices against European hubs, NOT against the desk's "
            "XNGUSD, which is Henry Hub. Every cell using XNGUSD as a European proxy must say so"},
    {"name": "LBMA gold price",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "confidence": "SETTLED",
     "why": "SOFAZ holds physical gold as part of its reserve allocation and reports the holding; "
            "the household safe-haven reflex runs to gold as well, because the currency is pegged "
            "and therefore offers no domestic hedge"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "SOFAZ transfer to the state budget", "kind": "quarter_end",
     "convention": "set in the budget law for the year and executed through the year; the annual "
                   "figure is the peg's fiscal backing",
     "rollover_utc": "10:00", "instruments": ("XBRUSD",),
     "why": "the transfer is legislated in advance, so the sovereign's manat need for the year is "
            "known before the year begins -- which makes the break-even oil price calculable"},
    {"name": "SOFAZ FX auction cycle", "kind": "weekday",
     "convention": "auctions held on announced days, results published same day",
     "rollover_utc": "11:00", "instruments": ("XBRUSD", "USDTRY"),
     "why": "the flow that defends the peg; volume is the stress gauge"},
    {"name": "budget year and the oil-price assumption", "kind": "fiscal_year_end",
     "convention": "31 December; the budget law carries an explicit oil-price assumption",
     "rollover_utc": "", "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the assumption is published, so the gap between it and spot is a measurable fiscal "
            "surprise -- the same object as the Western Australian royalty assumption in the AU "
            "pack, in a very different economy"},
    {"name": "gas contract delivery year", "kind": "fiscal_year_end",
     "convention": "Southern Gas Corridor contracts run on annual delivery commitments",
     "rollover_utc": "", "instruments": ("XNGUSD", "EUSTX50"),
     "why": "expansion commitments are announced years ahead with dated volumes, which makes "
            "European supply from this route a KNOWN future quantity"},
    {"name": "Azerbaijani tax calendar", "kind": "day_of_month",
     "convention": "monthly declarations and payments by the 20th",
     "rollover_utc": "", "instruments": (),
     "why": "a domestic manat demand on a fixed date; under a peg it has no exchange-rate "
            "consequence, which is itself the point"},
    {"name": "AZN spot value date", "kind": "weekday", "convention": "T+0/T+1 domestically",
     "rollover_utc": "", "instruments": (),
     "why": "the domestic market settles same-day or next-day; with a peg the forward points are "
            "an administered number rather than an interest-rate parity outcome"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Baku Stock Exchange (BSE)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "17:00", "open_utc": "06:00", "close_utc": "13:00",
     "dst_rule": "none (Baku is fixed UTC+4)", "auction": "call auctions",
     "expiry_rule": "n/a",
     "holidays": "the Azerbaijani national calendar",
     "notes": "small; dominated by government and SOCAR paper rather than equity. Listed so the "
              "absence of an Azerbaijani equity observable is named rather than implied"},
    {"name": "Central Bank auction platform",
     "index_symbols": (),
     "open_local": "auction days", "close_local": "auction days", "open_utc": "11:00",
     "close_utc": "12:00", "dst_rule": "none",
     "auction": "SOFAZ FX auctions are conducted here and the results published",
     "expiry_rule": "n/a",
     "holidays": "the Azerbaijani national calendar",
     "notes": "this is where the peg is actually defended. The desk has no access; the published "
              "results are the observable"},
    {"name": "Borsa Istanbul, the corridor terminus market",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "18:00", "open_utc": "07:00", "close_utc": "15:00",
     "dst_rule": "none (Istanbul is fixed UTC+3)", "auction": "closing auction 18:00-18:10",
     "expiry_rule": "see the Turkish pack",
     "holidays": "the Turkish calendar, which SHARES the two Islamic feasts with Azerbaijan but "
                 "differs on Novruz and on every national date",
     "notes": "Turkey is the corridor terminus and the largest trade partner; the shared Islamic "
              "feasts mean the two markets are shut together twice a year, which is a genuine "
              "regional liquidity event and not two coincidences"},
)


# --------------------------------------------------------------------------- holidays
def _next_working(day: date, taken: set[date]) -> date:
    while day.weekday() >= 5 or day in taken:
        day += timedelta(days=1)
    return day


#: Azerbaijan's fixed public holidays. NOVRUZ runs FIVE days, 20-24 March, and is the largest
#: closure of the Azerbaijani year -- longer than Kazakhstan's three-day Nauryz next door.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Yeni il bayrami (New Year), day 1"),
    (1, 2, "Yeni il bayrami (New Year), day 2"),
    (1, 20, "20 Yanvar faciesi (Black January, day of mourning)"),
    (3, 8, "Beynelxalq Qadinlar Gunu (International Women's Day)"),
    (3, 20, "Novruz bayrami, day 1"),
    (3, 21, "Novruz bayrami, day 2"),
    (3, 22, "Novruz bayrami, day 3"),
    (3, 23, "Novruz bayrami, day 4"),
    (3, 24, "Novruz bayrami, day 5"),
    (5, 9, "Fasizm uzerinde Qelebe Gunu (Victory over Fascism Day)"),
    (5, 28, "Musteqillik Gunu (Independence Day)"),
    (6, 15, "Milli Qurtulus Gunu (National Salvation Day)"),
    (6, 26, "Silahli Quvveler Gunu (Armed Forces Day)"),
    (11, 8, "Zefer Gunu (Victory Day)"),
    (11, 9, "Dovlet Bayragi Gunu (State Flag Day)"),
    (12, 31, "Dunya Azerbaycanlilarinin Hemreylik Gunu (Solidarity Day)"),
)

#: THE TWO ISLAMIC FEASTS ARE PROCLAIMED, NOT COMPUTED. Azerbaijan observes TWO days of each.
#: Tabulated because an astronomical formula is not the authority and the proclaimed date can
#: differ from the astronomical one by a day.
RAMAZAN_BAYRAMI: dict[int, date] = {
    2024: date(2024, 4, 10), 2025: date(2025, 3, 30), 2026: date(2026, 3, 20),
    2027: date(2027, 3, 10),
}
QURBAN_BAYRAMI: dict[int, date] = {
    2024: date(2024, 6, 16), 2025: date(2025, 6, 6), 2026: date(2026, 5, 27),
    2027: date(2027, 5, 17),
}


def national_holidays(year: int) -> dict[date, str]:
    """Azerbaijan's public holidays for `year`, from the fixed dates plus the two proclaimed
    Islamic feasts, with the labour-code transfer rule applied.

    THE TRANSFER RULE, which Georgia next door does NOT have: when a public holiday coincides
    with another public holiday, or falls on a weekend, the day off is moved to the following
    working day. In 2026 that rule does real work -- Ramazan bayrami falls on 20-21 March, INSIDE
    the five-day Novruz block, so both feast days collide with Novruz and transfer forward.

    The collision is not a quirk of one year. The Islamic calendar drifts about eleven days
    earlier each solar year, so Ramazan bayrami moves through Novruz over a run of years, and a
    calendar that does not handle the collision will silently lose or duplicate days in exactly
    the years when the closure is longest.
    """
    out: dict[date, str] = {}
    taken: set[date] = set()
    for month, day, label in FIXED_NATIONAL:
        actual = date(year, month, day)
        out[actual] = label
        taken.add(actual)
    for table, label in ((RAMAZAN_BAYRAMI, "Ramazan bayrami"),
                         (QURBAN_BAYRAMI, "Qurban bayrami")):
        first = table.get(year)
        if first is None:
            continue
        for offset in (0, 1):
            feast = first + timedelta(days=offset)
            if feast in taken or feast.weekday() >= 5:
                moved = _next_working(feast + timedelta(days=1), taken)
                taken.add(moved)
                out[moved] = f"{label}, day {offset + 1} — transferred"
            else:
                taken.add(feast)
                out[feast] = f"{label}, day {offset + 1}"
    for month, day, label in FIXED_NATIONAL:
        actual = date(year, month, day)
        if actual.weekday() < 5:
            continue
        moved = _next_working(actual + timedelta(days=1), taken)
        taken.add(moved)
        out[moved] = f"{label} — transferred"
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The Baku Stock Exchange and the CBA platform follow the national calendar."""
    return national_holidays(year)


def novruz(year: int) -> tuple[date, ...]:
    """The five canonical Novruz dates: 20 to 24 March."""
    return tuple(date(year, 3, d) for d in range(20, 25))


def shared_islamic_closures(year: int) -> dict[date, str]:
    """The days Azerbaijan AND Turkey are both shut for the same Islamic feast.

    This is a genuine regional liquidity event rather than two coincidences: the corridor's
    origin and its terminus close together, twice a year, on dates that move about eleven days
    earlier each solar year.
    """
    out: dict[date, str] = {}
    for table, label in ((RAMAZAN_BAYRAMI, "Ramazan bayrami / Ramazan Bayrami"),
                         (QURBAN_BAYRAMI, "Qurban bayrami / Kurban Bayrami")):
        first = table.get(year)
        if first is None:
            continue
        for offset in range(3):
            out[first + timedelta(days=offset)] = (
                f"{label}: Azerbaijan and Turkey both closed (Turkey observes more days)")
    return dict(sorted(out.items()))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_labour_code_plus_proclaimed_lunar_table",
    "authority": "the Labour Code of the Republic of Azerbaijan for the fixed dates and the "
                 "transfer rule; official proclamation for the two Islamic feasts",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "fixed_rule": "1-2 January, 20 January, 8 March, 20-24 March (Novruz, FIVE days), 9 May, "
                  "28 May, 15 June, 26 June, 8 November, 9 November and 31 December",
    "lunar_rule": "two days each of Ramazan bayrami and Qurban bayrami, PROCLAIMED rather than "
                  "computed; the proclaimed date can differ from the astronomical one by a day",
    "transfer_rule": "a holiday coinciding with another holiday, or falling on a weekend, moves "
                     "to the following working day. GEORGIA NEXT DOOR HAS NO SUCH RULE, which is "
                     "exactly the kind of neighbour-to-neighbour difference an imported calendar "
                     "gets wrong",
    "collision_note": "the Islamic calendar drifts about eleven days earlier each solar year, so "
                      "Ramazan bayrami moves THROUGH the five-day Novruz block over a run of "
                      "years. In 2026 it falls on 20-21 March, inside Novruz, and both feast days "
                      "transfer forward. A calendar that does not handle the collision silently "
                      "loses or duplicates days in the years when the closure is longest",
    "known_dates": {
        "2026-03-20": "Novruz day 1, and also the proclaimed first day of Ramazan bayrami -- the "
                      "collision year",
        "2026-03-24": "Novruz day 5",
        "2026-05-27": "Qurban bayrami day 1, the SAME day as Turkey's Kurban Bayrami and "
                      "Kazakhstan's Kurban Ait",
        "2026-05-28": "Musteqillik Gunu (Independence Day) and Qurban bayrami day 2 collide",
        "2026-11-08": "Zefer Gunu, a SUNDAY; transfers to Monday 9 November, which is itself "
                      "State Flag Day, so it transfers again to Tuesday 10 November",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "novruz_fn": novruz,
    "shared_islamic_fn": shared_islamic_closures,
    "ramazan": RAMAZAN_BAYRAMI,
    "qurban": QURBAN_BAYRAMI,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = ""
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders for AZN", "root": "", "fields": (), "frequency": "n/a",
     "snapshot": "", "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "no CME manat contract exists and none ever has; a pegged currency has no speculative "
            "futures market to report",
     "pit_warning": "DOES NOT EXIST and would carry no information if it did, because the rate is "
                    "administered. Manat positioning is permanently UNMEASURED"},
    {"name": "SOFAZ FX auction results",
     "root": "https://www.cbar.az/page-41/currency-auctions",
     "fields": ("auction_date", "offered_usd", "sold_usd", "demand_usd", "participants", "rate"),
     "frequency": "auction days", "snapshot": "auction", "publish_utc": "11:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "THE PEG'S STRESS GAUGE. Volume rises when the oil price falls and the budget needs "
            "more manat; the demand-to-offered ratio measures pressure directly",
     "pit_warning": "the auction CALENDAR is announced ahead but the volume is not; use the "
                    "published result's own timestamp, never the auction date alone"},
    {"name": "SOFAZ quarterly report and asset total",
     "root": "https://www.oilfund.az/en/report-and-statistics",
     "fields": ("quarter", "assets_usd", "budget_transfer_usd", "gold_holding", "revenue_usd"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "10:00",
     "lag_days": 30, "licence": "free, public", "available": True,
     "why": "the peg's fiscal backing; the transfer is legislated in advance so the manat need is "
            "known before the year begins",
     "pit_warning": "a 30-day lag; the transfer AMOUNT for the year is known from the budget law "
                    "much earlier, and that is the point-in-time datum, not the quarterly report"},
    {"name": "CBA international reserves", "root": "https://www.cbar.az/page-41/statistics",
     "fields": ("month", "gross_reserves_usd", "change"), "frequency": "monthly",
     "snapshot": "month end", "publish_utc": "11:00", "lag_days": 7, "licence": "free, public",
     "available": True,
     "why": "the Bank's own buffer, separate from the Fund's; the split between the two is the "
            "institutional structure that makes the peg credible",
     "pit_warning": "revised; and reserve changes include valuation effects that are not defence "
                    "of the peg"},
    {"name": "State Statistical Committee trade and production",
     "root": "https://www.stat.gov.az/?lang=en",
     "fields": ("month", "oil_production", "gas_production", "exports", "imports", "partner"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "06:00", "lag_days": 25,
     "licence": "free, public", "available": True,
     "why": "the physical volumes behind the fiscal story",
     "pit_warning": "revised; gas SWAP arrangements mean a reported export volume may be a "
                    "swapped molecule rather than Azerbaijani production"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "AZ-A": ("manat", "sabit məzənnə", "dollara bağlılıq", "Mərkəzi Bank", "məzənnə siyasəti",
             "манат", "фиксированный курс", "привязка", "Центральный банк"),
    "AZ-B": ("Dövlət Neft Fondu", "SOFAZ", "transfer", "dövlət büdcəsi", "neftin qiyməti",
             "büdcə kəsiri", "Государственный нефтяной фонд", "трансферт", "бюджет"),
    "AZ-C": ("valyuta hərracı", "hərrac", "təklif", "tələb", "satış həcmi", "iştirakçılar",
             "валютный аукцион", "предложение", "спрос", "объём продажи"),
    "AZ-D": ("uçot dərəcəsi", "faiz dəhlizi", "likvidlik", "yenidən maliyyələşdirmə",
             "учетная ставка", "процентный коридор", "ликвидность"),
    "AZ-E": ("neft", "Azəri-Çıraq-Günəşli", "hasilat", "ixrac", "kəmər", "Ceyhan",
             "azalma tempi", "нефть", "добыча", "экспорт"),
    "AZ-F": ("qaz", "Şah Dəniz", "Cənub Qaz Dəhlizi", "ötürücü həcm", "genişləndirmə",
             "газ", "Шах-Дениз", "Южный газовый коридор", "прокачка"),
    "AZ-G": ("SOCAR", "svop", "təkrar ixrac", "tranzit", "mənşə", "СОКАР", "своп", "реэкспорт"),
    "AZ-H": ("Orta Dəhliz", "Xəzər", "bərə", "yük daşımaları", "liman dövriyyəsi",
             "Средний коридор", "Каспий", "паром", "грузоперевозки"),
    "AZ-I": ("inflyasiya", "istehlak qiymətləri indeksi", "real məzənnə", "rəqabətqabiliyyətlilik",
             "инфляция", "индекс потребительских цен", "реальный курс"),
    "AZ-J": ("Novruz bayramı", "Ramazan bayramı", "Qurban bayramı", "iş günü", "keçirmə",
             "bayram günləri", "Новруз", "Рамазан", "Курбан", "перенос"),
    "AZ-K": ("evrobond", "spred", "suveren reytinq", "kredit reytinqi",
             "еврооблигации", "спред", "суверенный рейтинг"),
    "AZ-L": ("qızıl", "qızıl külçə", "ehtiyatlar", "sərvət fondu", "zərgərlik",
             "золото", "резервы", "фонд благосостояния", "ювелирный"),
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

    `machine_use_allowed=False` registers a source whose terms forbid machine extraction. It is
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


#: AZERBAIJAN'S TEN LAYERS, in AZERBAIJANI AND RUSSIAN. Azerbaijani uses a Latin alphabet with
#: its own diacritics, so a query stripped of them ("ucot derecesi" for "uçot dərəcəsi") finds
#: much less than it appears to. Russian remains a working language of the practitioner and
#: retail web across the Caucasus, so both are carried on every row.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "az_cbar", "Central Bank of Azerbaijan", layer="official",
        roots=("https://www.cbar.az/page-41/currency-auctions",
               "https://www.cbar.az/page-41/statistics", "https://www.cbar.az/"),
        queries=("uçot dərəcəsi", "faiz dəhlizi", "valyuta hərracı", "məzənnə",
                 "manatın məzənnəsi", "beynəlxalq ehtiyatlar", "inflyasiya",
                 "учетная ставка", "валютный аукцион", "курс маната", "резервы"),
        languages=("az", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE AUCTION RESULTS ARE THE PACK'S CENTRAL SERIES. The official rate itself is a "
              "CONSTANT at 1.7000 since 2017 and carries no information; the volume defending it "
              "does, and the demand-to-offered ratio measures pressure directly"),
    source_class(
        "az_sofaz", "State Oil Fund of Azerbaijan (SOFAZ)", layer="official",
        roots=("https://www.oilfund.az/en/report-and-statistics",
               "https://www.oilfund.az/en/fund/investment-portfolio"),
        queries=("Dövlət Neft Fondu", "SOFAZ", "transfer", "dövlət büdcəsinə transfer",
                 "aktivlər", "qızıl", "Государственный нефтяной фонд", "трансферт", "активы"),
        languages=("az", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the peg's fiscal backing. The TRANSFER for the year is legislated in the budget "
              "law long before this quarterly report, and the budget law is the point-in-time "
              "datum -- the report confirms it 30 days late"),
    source_class(
        "az_stat_mof", "State Statistical Committee and the Ministry of Finance",
        layer="official",
        roots=("https://www.stat.gov.az/?lang=en", "https://www.maliyye.gov.az/en"),
        queries=("istehlak qiymətləri indeksi", "inflyasiya", "neft hasilatı", "qaz hasilatı",
                 "ixrac", "idxal", "büdcə", "neftin qiyməti fərziyyəsi",
                 "индекс потребительских цен", "добыча нефти", "бюджет"),
        languages=("az", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the budget law's PUBLISHED OIL-PRICE ASSUMPTION is AZ-B's predictor, and the "
              "production-minus-export gap in the statistics is AZ-F's swap estimate"),
    source_class(
        "az_bse_regulator", "Baku Stock Exchange and the market regulator", layer="institutional",
        roots=("https://www.bfb.az/en", "https://www.cbar.az/"),
        queries=("Bakı Fond Birjası", "istiqraz", "listinq", "dövlət istiqrazları",
                 "Бакинская фондовая биржа", "облигации"),
        languages=("az", "ru"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="NOT_PREDICTIVE", licence="free headline",
        notes="dominated by government and SOCAR paper rather than equity. NOT_PREDICTIVE is a "
              "measured verdict, not a slur: there is no Azerbaijani equity observable worth "
              "mining and the pack says so rather than implying one"),
    source_class(
        "az_energy_consortia", "BP Azerbaijan, TANAP, TAP and SOCAR disclosure",
        layer="institutional",
        roots=("https://www.bp.com/en_az/azerbaijan/home.html", "https://www.tanap.com/",
               "https://www.tap-ag.com/", "http://www.socar.az/"),
        queries=("Azəri-Çıraq-Günəşli", "Şah Dəniz", "hasilat", "genişləndirmə",
                 "Cənub Qaz Dəhlizi", "ötürücü həcm", "Азери-Чираг-Гюнешли", "Шах-Дениз",
                 "Южный газовый коридор", "прокачка"),
        languages=("az", "ru", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ACG's DECLINE PATH is published, which makes it a KNOWN future supply reduction "
              "and means only the DEVIATION from the path is news. Expansion commitments are "
              "dated years ahead. EVENT LANE ONLY for the single names"),
    source_class(
        "az_multilateral", "IMF, ADB, World Bank and the EU energy partnership",
        layer="institutional",
        roots=("https://www.imf.org/en/Countries/AZE",
               "https://www.adb.org/countries/azerbaijan/",
               "https://energy.ec.europa.eu/"),
        queries=("Article IV", "break-even oil price", "exchange rate regime", "peg",
                 "memorandum of understanding energy", "режим валютного курса"),
        languages=("en", "ru", "az"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the IMF publishes the BREAK-EVEN calculation this pack's AZ-B is built on, and the "
              "EU energy pages carry the dated volume commitments AZ-E measures"),
    source_class(
        "az_cbar_research", "CBA research and the Azerbaijani academic literature",
        layer="academic",
        roots=("https://www.cbar.az/page-42/publications", "https://cyberleninka.ru/",
               "https://ideas.repec.org/"),
        queries=("tədqiqat", "monetar transmissiya", "sabit məzənnə rejimi", "dollarlaşma",
                 "исследование", "фиксированный курс", "долларизация",
                 "oil fund and exchange rate peg"),
        languages=("az", "ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free reading; bulk download restricted",
        notes="the domestic literature on the 2015 devaluations is the only detailed account of "
              "how a peg in this region actually breaks -- the evidence behind AZ-A's refusal"),
    source_class(
        "az_dutch_disease_lit", "Resource-curse and peg-sustainability literature",
        layer="academic",
        roots=("https://papers.ssrn.com/", "https://www.nber.org/papers"),
        queries=("oil fund sustainability", "fixed exchange rate oil exporter",
                 "Dutch disease Caucasus", "fiscal break-even", "real exchange rate peg"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="per-paper",
        notes="AZ-I's claim -- that under a peg the REAL exchange rate adjusts through domestic "
              "prices -- is a standard result, and the literature is where its magnitude for "
              "comparable economies is calibrated"),
    source_class(
        "az_practitioner", "Local brokerages, consultancies and Caucasus analysts",
        layer="practitioner",
        roots=("https://report.az/en/", "https://www.trend.az/", "https://caliber.az/"),
        queries=("neft gəlirləri", "büdcə gəlirləri", "manatın sabitliyi", "hərrac həcmi",
                 "нефтяные доходы", "стабильность маната", "объём аукциона"),
        languages=("az", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public web; automated extraction restricted",
        notes="Azerbaijani market commentary is thin and close to official framing; treated as a "
              "conditioning variable rather than as independent analysis, and labelled honestly"),
    source_class(
        "az_telegram_analysts", "Azerbaijani and Russian-language economic Telegram channels",
        layer="practitioner",
        roots=("https://t.me/s/",),
        queries=("manat devalvasiya", "devalvasiya olacaq", "neft qiyməti büdcə",
                 "девальвация маната", "нефть и бюджет", "аукцион ЦБА"),
        languages=("az", "ru"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public channels; automated extraction restricted",
        notes="DEVALUATION RUMOUR IS THE MECHANISM HERE. With a pegged rate there is no price to "
              "express the belief, so it shows up as auction demand instead -- and the rumour is "
              "dated here before the auction shows it. FRINGE AND KEPT, at low weight"),
    source_class(
        "az_retail_forums", "Azerbaijani banking forums and Russian boards used locally",
        layer="retail_ecology",
        roots=("https://banker.az/", "https://www.reddit.com/r/azerbaijan/",
               "https://smart-lab.ru/"),
        queries=("əmanət faizi", "dollar almaq", "manatı dollara çevirmək", "bank depoziti",
                 "ставка по депозиту", "купить доллары", "перевести в доллары", "смартлаб"),
        languages=("az", "ru"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public forums; automated extraction restricted",
        notes="household currency substitution under a peg has nowhere to show except in "
              "conversion behaviour, and this is where it is discussed. Low weight, never zero"),
    source_class(
        "az_gold_bazaar", "Retail gold dealers and the physical bullion trade",
        layer="retail_ecology",
        roots=("https://www.cbar.az/", "https://t.me/s/"),
        queries=("qızıl külçə", "qızıl sikkə", "zərgərlik", "qızıl qiyməti",
                 "золотой слиток", "цена золота", "ювелирный"),
        languages=("az", "ru"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public listings and channels; automated extraction restricted",
        notes="A PEGGED CURRENCY OFFERS HOUSEHOLDS NO DEVALUATION HEDGE, so the hedge is "
              "physical. Retail bullion premia are the closest thing to a market-priced "
              "devaluation expectation that exists in this country, and they are FRINGE data"),
    source_class(
        "az_broker_apps", "Azerbaijani bank and brokerage apps", layer="app_ecosystem",
        roots=("https://www.pashabank.az/", "https://www.kapitalbank.az/",
               "https://www.bfb.az/en"),
        queries=("investisiya hesabı", "broker komissiyası", "mobil tətbiq",
                 "инвестиционный счёт", "комиссия брокера", "мобильное приложение"),
        languages=("az", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public product pages; account data is PRIVATE and is never sought",
        notes="a thin domestic investment-app layer; what exists is mostly deposit and FX "
              "conversion rather than securities. NO ACCOUNT-LEVEL DATA is sought"),
    source_class(
        "az_metatrader", "MetaTrader and TradingView as used in the Caucasus",
        layer="app_ecosystem",
        roots=("https://www.mql5.com/ru/market", "https://www.mql5.com/ru/code",
               "https://ru.tradingview.com/scripts/"),
        queries=("alqoritmik ticarət", "ticarət robotu", "алготрейдинг", "торговый робот",
                 "советник", "MQL5", "кодобаза", "стакан", "скальпинг", "арбитраж",
                 "тестер стратегий", "Pine Script", "Brent analiz"),
        languages=("az", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms",
        notes="Azerbaijan has no domestic algorithmic ecosystem; like Georgia it borrows the "
              "RUSSIAN-LANGUAGE MetaTrader ground, and the local retail interest is in BRENT and "
              "USDTRY rather than in any Azerbaijani instrument -- which is itself the finding"),
    source_class(
        "az_press", "Report.az, Trend, APA and Caliber", layer="media",
        roots=("https://report.az/en/", "https://www.trend.az/", "https://apa.az/en",
               "https://caliber.az/"),
        queries=("valyuta hərracı nəticələri", "SOFAZ transfer", "uçot dərəcəsi qərarı",
                 "neft ixracı", "результаты аукциона", "решение по ставке"),
        languages=("az", "ru", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Trend and Report carry the auction results fastest; the editorial line is close to "
              "official and is treated as such rather than as independent confirmation"),
    source_class(
        "az_regional_media", "JAMnews, OC Media, RFE/RL and Eurasianet", layer="media",
        roots=("https://jam-news.net/", "https://oc-media.org/", "https://eurasianet.org/"),
        queries=("Azerbaijan economy", "gas exports Europe", "Middle Corridor",
                 "экономика Азербайджана", "газ в Европу"),
        languages=("en", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the independent regional coverage the domestic outlets do not carry; essential "
              "for the swap-origin question in AZ-F, which is politically sensitive locally"),
    source_class(
        "az_wayback", "Internet Archive captures of cbar.az and oilfund.az", layer="archive",
        roots=("https://web.archive.org/web/*/cbar.az*",
               "https://web.archive.org/web/*/oilfund.az*"),
        queries=("arxiv", "архив страницы", "первоначальная публикация", "hərrac arxivi",
                 "архив аукционов"),
        languages=("az", "ru", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="auction result pages are reorganised and older results are pruned; the Wayback "
              "capture is often the only surviving record of a 2017-2019 auction, which is the "
              "baseline period AZ-C needs to know what 'normal' volume looks like"),
    source_class(
        "az_national_library", "National Library of Azerbaijan and the press archive",
        layer="archive",
        roots=("https://www.anl.az/",),
        queries=("arxiv", "2015 devalvasiya", "tarixi statistika", "архив",
                 "девальвация 2015", "историческая статистика"),
        languages=("az", "ru"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public archive; reading-room and site terms govern reuse",
        notes="the two 2015 devaluations are the only period in the modern series where the rate "
              "moved, and the contemporaneous record is how the household reflex behind AZ-L is "
              "dated rather than assumed"),
    source_class(
        "az_pipeline_physical", "BTC, SCP, TANAP and TAP throughput plus ENTSOG",
        layer="physical_economy",
        roots=("https://www.tanap.com/", "https://www.tap-ag.com/",
               "https://transparency.entsog.eu/"),
        queries=("ötürülən həcm", "boru kəməri", "Ceyhan yüklənməsi", "qaz ixracı",
                 "прокачка", "трубопровод", "отгрузка в Джейхане", "экспорт газа",
                 "entry point flows"),
        languages=("az", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ENTSOG publishes European pipeline ENTRY FLOWS free and daily, which is the best "
              "available physical read on the Southern Gas Corridor -- and far better than the "
              "desk's XNGUSD, which is a US benchmark"),
    source_class(
        "az_production_physical", "Field production, maintenance schedules and loadings",
        layer="physical_economy",
        roots=("https://www.stat.gov.az/?lang=en", "https://www.bp.com/en_az/azerbaijan/home.html"),
        queries=("neft hasilatı", "qaz hasilatı", "planlı təmir", "yükləmə qrafiki",
                 "добыча нефти", "плановый ремонт", "график отгрузок"),
        languages=("az", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="scheduled maintenance is announced and is a dated production constraint; the "
              "production-minus-export gap is the swap estimate AZ-F publishes"),
    source_class(
        "az_corridor_physical", "Baku port, ADY rail and Middle Corridor capacity",
        layer="physical_economy",
        roots=("https://portofbaku.com/", "https://ady.az/"),
        queries=("liman dövriyyəsi", "bərə", "Xəzər bərəsi", "yük daşımaları",
                 "Orta Dəhliz", "оборот порта", "паром", "Средний коридор"),
        languages=("az", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="CASPIAN FERRY CAPACITY is the genuine bottleneck on the Middle Corridor, and it "
              "is a physical count published by the port -- the shared observable with KZ-J"),
    source_class(
        "az_citation_graph", "OpenAlex, RePEc and CyberLeninka citation graphs",
        layer="source_graph",
        roots=("https://openalex.org/", "https://ideas.repec.org/", "https://cyberleninka.ru/"),
        queries=("cited by", "peg sustainability", "цитирование", "кто цитирует",
                 "oil fund literature"),
        languages=("en", "ru", "az"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the peg-sustainability literature is small and the graph shows which findings "
              "have been replicated for comparable oil exporters"),
    source_class(
        "az_code_graph", "GitHub clients for CBA and ENTSOG data", layer="source_graph",
        roots=("https://github.com/search?q=cbar.az", "https://github.com/search?q=entsog+api"),
        queries=("cbar api", "entsog api", "azerbaijan exchange rate", "форк", "зависимости"),
        languages=("en", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="per-repository; check each, never vendor code",
        notes="that public ENTSOG clients exist and public CBA clients largely do not is itself "
              "a measurement of which series practitioners consider worth automating"),
    source_class(
        "az_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en",), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="Azerbaijan shares its app ecosystem with Georgia and Russia and its physical "
              "corridor with Georgia, Turkey and Kazakhstan; the registry is what stops the same "
              "ground being counted as four countries' coverage"),
)

#: All ten layers are populated. Two honest caveats are recorded in the rows rather than hidden:
#: Azerbaijan has NO domestic algorithmic-trading ecosystem (it borrows the Russian-language
#: MetaTrader ground), and its practitioner layer is thin and close to official framing, which is
#: why those rows carry UNRELIABLE and NARRATIVE_FEATURE rather than RELIABLE.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "SOFAZ FX auction results", "source": "Central Bank of Azerbaijan",
     "coverage": "2017 onward", "frequency": "auction days", "publication_lag_days": 0.0,
     "revisions": "final", "licence": "free, public", "history_from": "2017-01",
     "pit_feasible": True, "assets": ("XBRUSD", "USDTRY"),
     "fields": ("auction_date", "offered_usd", "demand_usd", "sold_usd", "participants", "rate"),
     "pit_fields": ("result_ts_utc",),
     "mechanism_families": ("sovereign_flow", "policy_shock"),
     "how_to_fetch": "cbar.az currency auctions. THE PACK'S CENTRAL SERIES: the volume is the "
                     "peg's stress gauge and the demand-to-offered ratio measures pressure"},
    {"name": "SOFAZ quarterly report", "source": "State Oil Fund of Azerbaijan",
     "coverage": "2001 onward", "frequency": "quarterly", "publication_lag_days": 30.0,
     "revisions": "revised at annual audit", "licence": "free, public", "history_from": "2001-03",
     "pit_feasible": True, "assets": ("XBRUSD", "XAUUSD"),
     "fields": ("quarter", "assets_usd", "revenue_usd", "budget_transfer_usd", "gold_holding",
                "currency_composition"),
     "pit_fields": ("publish_ts_utc", "quarter_end"),
     "mechanism_families": ("sovereign_flow",),
     "how_to_fetch": "oilfund.az reports; the TRANSFER for the year is legislated earlier and is "
                     "the point-in-time datum, not this report"},
    {"name": "Azerbaijani budget law oil-price assumption", "source": "Ministry of Finance",
     "coverage": "2010 onward", "frequency": "annual plus amendments",
     "publication_lag_days": 0.0, "revisions": "amended by supplementary budget",
     "licence": "free, public", "history_from": "2010-12", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "fields": ("year", "assumed_oil_price_usd", "transfer_amount", "break_even_estimate"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("terms_of_trade", "policy_shock"),
     "how_to_fetch": "the budget law; the GAP between the assumption and spot Brent is a "
                     "measurable fiscal surprise and the peg's stress predictor"},
    {"name": "CBA refinancing rate decisions", "source": "Central Bank of Azerbaijan",
     "coverage": "2010 onward", "frequency": "scheduled through the year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("USDTRY", "USDRUB"),
     "fields": ("decision_date", "refinancing_rate_pct", "floor", "ceiling", "statement"),
     "pit_fields": ("release_ts_utc",),
     "mechanism_families": ("event_reaction",),
     "how_to_fetch": "cbar.az. Under a peg the rate is a LIQUIDITY instrument; a rate-surprise "
                     "study here measures an instrument that is not doing the work"},
    {"name": "Azerbaijani oil and gas production", "source": "State Statistical Committee",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("XBRUSD", "XNGUSD"),
     "fields": ("month", "oil_kt", "gas_mcm", "exports_oil", "exports_gas", "destination"),
     "pit_fields": ("publish_ts_utc", "vintage"),
     "mechanism_families": ("supply_shock", "terms_of_trade"),
     "how_to_fetch": "stat.gov.az. NOTE the SWAP arrangements: a reported export volume may be a "
                     "swapped molecule rather than Azerbaijani production, so origin is ambiguous"},
    {"name": "BTC pipeline throughput", "source": "consortium disclosure",
     "coverage": "2006 onward", "frequency": "quarterly", "publication_lag_days": 45.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2006-06",
     "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "fields": ("period", "throughput_mmbbl", "interruptions"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("supply_shock",),
     "how_to_fetch": "consortium quarterly reports; interruptions are announced separately and "
                     "those announcements are the tradeable events"},
    {"name": "Southern Gas Corridor volumes and expansion commitments",
     "source": "TANAP and TAP disclosure", "coverage": "2018 onward",
     "frequency": "annual and event-driven", "publication_lag_days": 30.0,
     "revisions": "expansion schedules slip", "licence": "free, public",
     "history_from": "2018-06", "pit_feasible": True,
     "assets": ("XNGUSD", "EUSTX50", "GER40"),
     "fields": ("period", "volume_bcm", "destination", "expansion_commitment_bcm",
                "commitment_date"),
     "pit_fields": ("announcement_ts_utc",),
     "mechanism_families": ("supply_shock",),
     "how_to_fetch": "tanap.com and tap-ag.com. Expansion commitments are dated years ahead, "
                     "which makes European supply from this route a KNOWN future quantity"},
    {"name": "CBA international reserves", "source": "Central Bank of Azerbaijan",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 7.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("XAUUSD",),
     "fields": ("month", "gross_reserves_usd", "change"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("sovereign_flow",),
     "how_to_fetch": "cbar.az statistics; the split between Bank reserves and Fund assets is the "
                     "institutional structure that makes the peg credible"},
    {"name": "State Statistical Committee consumer price index",
     "source": "State Statistical Committee", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 5.0, "revisions": "revised", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True, "assets": (),
     "fields": ("reference_month", "cpi_mom", "cpi_yoy", "food", "non_food", "services"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "stat.gov.az. Under a peg, domestic inflation is the ADJUSTMENT variable: "
                     "with a fixed nominal rate the real exchange rate moves through prices"},
    {"name": "Desk MT5 regional tape", "source": "the desk's own Fusion tape",
     "coverage": "2018 onward", "frequency": "tick to daily", "publication_lag_days": 0.0,
     "revisions": "append-only", "licence": "desk-owned", "history_from": "2018-01",
     "pit_feasible": True, "assets": ("XBRUSD", "XNGUSD", "USDTRY", "EUSTX50"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet -- the only place an "
                     "Azerbaijani mechanism is executable on this box"},
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "The State Oil Fund of Azerbaijan (SOFAZ) as the peg's funder",
        "holds": "a sovereign oil fund of the order of the country's annual GDP, including a "
                 "reported physical gold allocation",
        "forced_to": ("transfer a legislated amount to the state budget each year, whatever the "
                      "oil price",
                      "SELL dollars at Central Bank auctions to convert that transfer into manat",
                      "sell more when the oil price is lower, because the manat obligation is "
                      "fixed and the dollar revenue is not"),
        "when": "auctions on announced days through the year; the transfer amount is set in the "
                "budget law in December",
        "information": ("its own revenue receipts before publication",
                        "the budget's cash needs"),
        "constraints": ("the budget law's transfer amount, a legal obligation",
                        "the Fund's own investment mandate",
                        "the peg itself, which fixes the conversion rate and therefore the "
                        "dollar cost of any manat obligation"),
        "instruments": ("XBRUSD", "USDTRY", "XAUUSD"),
        "counterparties": ("the domestic banks bidding at the auctions",
                           "the state budget"),
        "observables": ("auction offered, demanded and sold volumes",
                        "the demand-to-offered ratio, which measures pressure directly",
                        "the Fund's quarterly assets and the legislated transfer"),
        "impact": "THE PEG'S MAINTENANCE MECHANISM. The auction volume is the stress gauge: it "
                  "rises when the oil price falls, because the manat obligation is fixed in "
                  "nominal terms and fewer dollars are arriving to meet it",
        "persistence": "structural since 2017; the Fund's size means the peg can be defended for "
                       "years at prices that would break a smaller sovereign, which is why the "
                       "BREAK-EVEN calculation matters more than any single month's auction",
        "falsifier": "regress the auction volume on the oil price. If volume does NOT rise as the "
                     "price falls, the mechanism this pack describes is not the one operating",
        "notes": "this actor is the reason the pack exists: a currency that never moves, defended "
                 "by a flow that is published",
    },
    {
        "name": "The Central Bank of Azerbaijan as peg administrator",
        "holds": "the official rate at 1.7000, its own reserves separate from the Fund's, and the "
                 "refinancing rate",
        "forced_to": ("publish an official rate every business day, which has been a constant "
                      "since 2017",
                      "organise and publish the SOFAZ auctions",
                      "use the refinancing rate as a LIQUIDITY instrument, because the exchange "
                      "rate is not available to it as a policy variable"),
        "when": "daily rate publication; scheduled rate decisions; auction days",
        "information": ("bank-level FX demand through its own reporting"),
        "constraints": ("the peg, which removes the exchange rate from the toolkit",
                        "its own reserves, which are smaller than the Fund's and are the second "
                        "line of defence rather than the first",
                        "domestic inflation, which is the adjustment variable under a fixed rate"),
        "instruments": ("USDTRY", "USDRUB"),
        "counterparties": ("the domestic banking system", "SOFAZ", "the Ministry of Finance"),
        "observables": ("the official rate, a constant",
                        "monthly reserves",
                        "the refinancing rate and its corridor"),
        "impact": "under a peg the rate decision is about domestic liquidity and credit, not "
                  "about the currency; a rate-surprise study on AZN is measuring an instrument "
                  "that is not doing the work",
        "persistence": "the peg has held since 2017 through a major oil drawdown and a war; that "
                       "is genuine evidence of commitment and not merely of luck",
        "falsifier": "the reserve series should be STABLE while the Fund's auction volume "
                     "absorbs the pressure. If Bank reserves are doing the work instead, the "
                     "institutional structure this pack describes is wrong",
        "notes": "",
    },
    {
        "name": "The Azeri-Chirag-Gunashli consortium and the declining core field",
        "holds": "the mature offshore oil complex that is most of Azerbaijani production",
        "forced_to": ("accept a published natural decline rate in a mature field",
                      "invest in compression and infill to slow it, on announced schedules"),
        "when": "continuous production; quarterly reporting; maintenance seasons are scheduled",
        "information": ("field performance before it is reported"),
        "constraints": ("reservoir physics, which is the most binding constraint in this pack",
                        "the production-sharing agreement's terms and its extension",
                        "the BTC route's capacity"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "counterparties": ("Mediterranean and European refiners", "the state as PSA partner"),
        "observables": ("quarterly production",
                        "the published decline rate",
                        "BTC throughput"),
        "impact": "a KNOWN FUTURE SUPPLY REDUCTION: unlike most supply stories this one is a "
                  "published physical trend rather than a policy decision, so it is priced far in "
                  "advance and the tradeable part is the DEVIATION from the decline path",
        "persistence": "decline is structural and has run for more than a decade",
        "falsifier": "the deviation from the published decline path, not the decline itself. If "
                     "only the level matters and deviations do not, the market has fully priced "
                     "the path and there is nothing here",
        "notes": "the single names are ACTORS only",
    },
    {
        "name": "Shah Deniz and the Southern Gas Corridor consortium",
        "holds": "the gas field and the pipeline chain that is Europe's only non-Russian Caspian "
                 "route",
        "forced_to": ("deliver contracted annual volumes to Turkish and Italian buyers",
                      "announce expansion commitments years ahead with dated volumes"),
        "when": "continuous delivery; expansion commitments on announced schedules that have "
                "slipped",
        "information": ("field and pipeline performance"),
        "constraints": ("field capacity, which caps expansion regardless of European demand",
                        "financing for expansion, which requires committed offtake",
                        "the transit chain across Georgia and Turkey"),
        "instruments": ("XNGUSD", "EUSTX50", "GER40", "USDTRY"),
        "counterparties": ("Turkish and Italian utilities", "European buyers seeking "
                           "diversification"),
        "observables": ("annual delivered volumes by destination",
                        "expansion commitment announcements and their dates",
                        "European gas hub prices, which are NOT the desk's XNGUSD"),
        "impact": "after 2022 this became a European POLICY variable rather than a commercial "
                  "one; the volumes are small relative to European demand but the political "
                  "weight is not, which is why announcements move sentiment more than molecules",
        "persistence": "structural and growing slowly; capacity is the binding limit and it is "
                       "published",
        "falsifier": "European gas prices and European equity should respond to VOLUME "
                     "announcements in proportion to the volume. If the response is larger than "
                     "the molecules justify, the mechanism is political signalling and should be "
                     "modelled as an announcement effect, not a supply effect",
        "notes": "",
    },
    {
        "name": "SOCAR and the gas swap arrangements",
        "holds": "the state energy company, its trading arm, and swap and re-export arrangements "
                 "with neighbours",
        "forced_to": ("meet contracted deliveries even when domestic production is short, which "
                      "is what the swaps are for",
                      "report volumes that may not correspond to physical origin"),
        "when": "continuous; swap arrangements are announced episodically",
        "information": ("the true physical origin of its delivered molecules"),
        "constraints": ("domestic production, which is capped",
                        "contracted delivery obligations",
                        "the political acceptability of each swap counterparty"),
        "instruments": ("XNGUSD", "USDTRY", "USDRUB"),
        "counterparties": ("neighbouring producers in swap arrangements",
                           "Turkish and European buyers"),
        "observables": ("reported export volumes by destination",
                        "swap announcements",
                        "the gap between domestic production and reported exports"),
        "impact": "the swaps make the physical accounting AMBIGUOUS: a volume attributed to "
                  "Azerbaijani production may be a swapped molecule. Any supply study that treats "
                  "reported exports as domestic production is measuring a trading arrangement",
        "persistence": "the arrangements have grown as European demand for non-Russian supply grew",
        "falsifier": "domestic production against reported exports. A persistent gap is swap "
                     "volume, and if the gap is large the 'Azerbaijani supply' story is partly a "
                     "re-export story",
        "notes": "this is the pack's most important measurement caveat on the gas side",
    },
    {
        "name": "The Ministry of Finance and the budget break-even",
        "holds": "the state budget, built on an explicit published oil-price assumption",
        "forced_to": ("publish an oil-price assumption in the budget law",
                      "fund the deficit from the Fund's transfer, which is legislated"),
        "when": "the budget law in December; supplementary budgets as needed",
        "information": ("budget execution before publication"),
        "constraints": ("the legislated transfer and deficit",
                        "a revenue base dominated by hydrocarbons",
                        "the peg, which converts a dollar revenue shortfall directly into a "
                        "manat financing need"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "counterparties": ("SOFAZ", "domestic and international creditors"),
        "observables": ("the published oil-price assumption",
                        "the gap between it and spot Brent",
                        "budget execution against plan"),
        "impact": "the assumption-to-spot gap is a measurable fiscal surprise and the best "
                  "available PREDICTOR of auction volume; it is the same object as the Western "
                  "Australian royalty assumption in the Australian pack, in a very different "
                  "economy",
        "persistence": "the practice of publishing an assumption is stable; the assumption's "
                       "conservatism varies with the political cycle",
        "falsifier": "regress auction volume on the assumption-to-spot gap. If the gap does not "
                     "predict the volume, the fiscal transmission this pack describes is not "
                     "operating",
        "notes": "",
    },
    {
        "name": "Azerbaijani households under a fixed nominal rate",
        "holds": "manat savings with a memory of two 2015 devaluations inside one year",
        "forced_to": ("choose between manat and dollar deposits with no exchange-rate signal to "
                      "guide them, because the rate is a constant",
                      "convert quickly when the peg's credibility is questioned, which is why "
                      "dollarisation here moves in steps"),
        "when": "concentrated around oil-price shocks and political events",
        "information": ("what everyone else has, plus a long memory"),
        "constraints": ("deposit rates on the two currencies",
                        "deposit insurance rules",
                        "the absence of any market signal about the peg, which means rumour does "
                        "the work a price would do elsewhere"),
        "instruments": ("XAUUSD", "USDTRY"),
        "counterparties": ("the domestic banks", "gold dealers"),
        "observables": ("deposit dollarisation ratios",
                        "gold demand",
                        "the auction demand-to-offered ratio, which captures bank demand driven "
                        "by household conversion"),
        "impact": "under a peg the household reflex shows up as AUCTION DEMAND rather than as a "
                  "price move -- the pressure has nowhere else to go, which is precisely what "
                  "makes the auction series informative",
        "persistence": "the 2015 memory is a decade old and still visible; each oil shock tests it",
        "falsifier": "the auction demand-to-offered ratio should spike on credibility events even "
                     "when the oil price has not moved. If it does not, household behaviour is "
                     "not reaching the auction and this actor is not measurable here",
        "notes": "",
    },
    {
        "name": "Turkey as corridor terminus and largest trade partner",
        "holds": "the destination of BTC crude and the first destination of Southern Gas Corridor "
                 "gas, plus the deepest market in the region",
        "forced_to": ("take contracted gas volumes",
                      "provide the corridor's transit and terminal capacity"),
        "when": "continuous; the two countries close together for the shared Islamic feasts",
        "information": ("its own demand and storage"),
        "constraints": ("pipeline and terminal capacity",
                        "Turkish energy policy and its own supplier diversification",
                        "a shared holiday calendar for the two Islamic feasts"),
        "instruments": ("USDTRY", "XNGUSD", "XBRUSD"),
        "counterparties": ("Azerbaijani producers", "European buyers further down the chain"),
        "observables": ("Turkish gas import statistics by origin",
                        "BTC loadings at Ceyhan",
                        "the shared holiday calendar"),
        "impact": "Turkey is where Azerbaijani volumes become visible in a liquid market; it is "
                  "also the pack's only liquid proxy, so USDTRY carries whatever Azerbaijani "
                  "signal reaches a quoted instrument",
        "persistence": "structural and deepening with each expansion commitment",
        "falsifier": "the shared Islamic closures are the cleanest test: on those days BOTH the "
                     "origin and the terminus are shut, so if regional liquidity effects are real "
                     "they should be largest there",
        "notes": "the shared closure is a genuine regional liquidity event, not two coincidences",
    },
    {
        "name": "The Middle Corridor through Baku and the Caspian",
        "holds": "the Trans-Caspian freight route from Kazakhstan through Azerbaijan to Turkey",
        "forced_to": ("handle whatever volume the ferry capacity allows, which is the bottleneck",
                      "invest in port and ferry capacity to grow"),
        "when": "continuous; volumes are published and grew sharply after 2022",
        "information": ("their own capacity and bookings"),
        "constraints": ("Caspian ferry capacity, the genuine physical bottleneck",
                        "port handling at Baku and Aktau",
                        "rail gauge changes along the route"),
        "instruments": ("USDCNH", "USDTRY"),
        "counterparties": ("Kazakh and Chinese shippers", "Turkish and European receivers"),
        "observables": ("Middle Corridor freight volumes",
                        "port throughput at Baku",
                        "transit times, which are the quality measure"),
        "impact": "a slow structural re-routing of China-Europe freight away from Russia; it "
                  "links this pack to the Kazakh one physically and is a shared observable",
        "persistence": "growing; capacity has expanded every year since 2022",
        "falsifier": "corridor growth should coincide with northern-route decline. Growth with no "
                     "decline is new trade rather than re-routed trade, and the mechanism is "
                     "different",
        "notes": "",
    },
    {
        "name": "The State Statistical Committee",
        "holds": "the official production, trade and price statistics",
        "forced_to": ("publish CPI in the first days of the month and trade with a 25-day lag",
                      "report export volumes that may include swapped molecules"),
        "when": "monthly, on a published calendar",
        "information": ("the numbers before publication"),
        "constraints": ("the statistics law and the calendar",
                        "an export accounting that cannot cleanly separate domestic production "
                        "from swap volume"),
        "instruments": ("XBRUSD", "XNGUSD"),
        "counterparties": ("the whole market at once"),
        "observables": ("the CPI release",
                        "monthly production and export volumes",
                        "the production-minus-export gap, which reveals swap volume"),
        "impact": "under a peg, CPI is the ADJUSTMENT VARIABLE: with a fixed nominal rate the real "
                  "exchange rate moves through domestic prices, so Azerbaijani inflation is the "
                  "competitiveness story that the exchange rate would tell elsewhere",
        "persistence": "permanent as a class",
        "falsifier": "the real exchange rate computed from CPI should move even though the "
                     "nominal rate does not. If it does not, the peg is not costing anything in "
                     "competitiveness, which would be a surprising and important finding",
        "notes": "",
    },
    {
        "name": "International rating agencies and sovereign eurobond holders",
        "holds": "Azerbaijani sovereign and SOCAR paper, priced on the peg's credibility",
        "forced_to": ("re-rate when the Fund's assets or the oil price move materially",
                      "hold or sell on a mandate rather than a view, in index funds"),
        "when": "scheduled rating review dates; continuous secondary trading",
        "information": ("the public fiscal data, and agency access to officials"),
        "constraints": ("rating methodology, which weights the Fund's assets heavily",
                        "index inclusion rules"),
        "instruments": ("UST10Y", "US500"),
        "counterparties": ("the sovereign and SOCAR as issuers"),
        "observables": ("the sovereign eurobond spread",
                        "rating review dates and outcomes",
                        "the Fund's reported assets, which drive the rating"),
        "impact": "the credit channel is the only place a market prices Azerbaijani risk "
                  "continuously, because the currency cannot; the spread is therefore the "
                  "country's de-facto risk price",
        "persistence": "structural; the rating has been stable and investment-grade-adjacent for "
                       "years on the strength of the Fund",
        "falsifier": "the spread against a matched oil-exporting peer around oil-price moves. If "
                     "Azerbaijan's spread is LESS oil-sensitive, the Fund is doing the work the "
                     "pack says it is",
        "notes": "",
    },
    {
        "name": "European buyers seeking non-Russian gas",
        "holds": "contracted and spot demand for Caspian gas as a diversification instrument",
        "forced_to": ("diversify by policy commitment after 2022, not only by price",
                      "commit to offtake before expansion can be financed"),
        "when": "contract negotiations and political announcements; delivery is continuous",
        "information": ("their own storage and demand"),
        "constraints": ("Southern Gas Corridor capacity, which is the binding limit",
                        "the political requirement to diversify, which is not price-elastic",
                        "competing LNG supply"),
        "instruments": ("XNGUSD", "EUSTX50", "GER40"),
        "counterparties": ("the Shah Deniz consortium", "SOCAR trading"),
        "observables": ("EU-Azerbaijan gas agreements and their dated volume commitments",
                        "delivered volumes to Italy and south-east Europe",
                        "European hub prices"),
        "impact": "demand that is partly POLICY rather than price makes the volume commitments "
                  "more credible than a commercial contract would be, and the announcements move "
                  "European sentiment more than the molecules justify",
        "persistence": "the policy commitment has held since 2022; capacity limits what it can "
                       "deliver",
        "falsifier": "European equity and gas response to a volume announcement, scaled by the "
                     "volume. A response larger than the molecules justify is announcement effect "
                     "and must be modelled as such",
        "notes": "",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "AZ-A", "title": "The peg: why the price is not the object",
        "objects": ("the official AZN/USD rate at 1.7000 since 2017",
                    "its variance, which is essentially zero",
                    "the 2015 step devaluations, the only moves in the modern series",
                    "the refinancing rate, which under a peg is a liquidity instrument"),
        "conditions": ("NO STATISTICAL TEST MAY BE RUN ON THE RATE ITSELF. A constant has a "
                       "variance near zero, and any Sharpe computed on it is an artefact of "
                       "division by a near-zero denominator",
                       "the correct objects are the AUCTION VOLUME and the BREAK-EVEN PRICE",
                       "the 2015 devaluations as their own class, not as observations"),
        "instruments": ("XBRUSD", "USDTRY", "USDRUB"),
        "controls": ("the auction volume series, which is what AZ-C measures instead",
                     "another pegged currency's series, to demonstrate the same pathology",
                     "the 2015 window, where the rate DID move, as the contrast"),
        "notes": "this domain exists to REFUSE a class of cell. A pack that let a miner fit a "
                 "mean-reversion model to a constant would produce a spectacular and entirely "
                 "false result, and the refusal is more valuable than any hypothesis here",
    },
    {
        "id": "AZ-B", "title": "The break-even oil price as the peg's stress predictor",
        "objects": ("the budget law's published oil-price assumption",
                    "the legislated SOFAZ transfer",
                    "the Fund's reported assets",
                    "the gap between the assumption and spot Brent"),
        "conditions": ("the assumption-to-spot gap as the predictor, measured at a fixed horizon",
                       "the Fund's assets as the buffer that determines how long the peg can hold",
                       "supplementary budgets, which revise the assumption mid-year"),
        "instruments": ("XBRUSD", "XTIUSD", "USDTRY"),
        "controls": ("the Fund's own asset trajectory as the independent check",
                     "a matched oil-exporting sovereign with a floating rate",
                     "years where the assumption was close to spot",
                     "the 2015 episode, where the gap became unsustainable"),
        "notes": "the same object as the Western Australian royalty assumption in the AU pack -- a "
                 "published fiscal price assumption -- in an economy where it decides whether the "
                 "currency regime survives rather than merely how large a surplus is",
    },
    {
        "id": "AZ-C", "title": "The auction as the peg's published defence",
        "objects": ("auction offered, demanded and sold volumes",
                    "the demand-to-offered ratio",
                    "the auction calendar",
                    "participant counts"),
        "conditions": ("volume regressed on the oil price, which is the mechanism's core claim",
                       "the demand-to-offered ratio as the pressure measure, not the volume alone",
                       "the result's own timestamp, because the calendar is announced but the "
                       "volume is not"),
        "instruments": ("XBRUSD", "USDTRY", "XAUUSD"),
        "controls": ("periods of stable oil prices, where volume should be flat",
                     "CBA reserves, which should be stable if the Fund is absorbing the pressure",
                     "the 2015 window, where the defence failed",
                     "household dollarisation, which should co-move with the demand ratio"),
        "notes": "THE PACK'S CENTRAL DOMAIN. A pegged currency whose defence is a dated, sized, "
                 "public auction is a better research object than the flat price suggests",
    },
    {
        "id": "AZ-D", "title": "Azeri Light: a premium grade and a published decline",
        "objects": ("ACG production and its published decline rate",
                    "BTC throughput",
                    "the Azeri Light premium to Brent",
                    "deviations from the announced decline path"),
        "conditions": ("the DEVIATION from the published decline path, not the decline itself, "
                       "which is priced years ahead",
                       "the premium to Brent, which is a QUALITY premium -- the opposite of the "
                       "Urals discount in the Russia pack",
                       "maintenance seasons, which are scheduled"),
        "instruments": ("XBRUSD", "XTIUSD"),
        "controls": ("the Urals discount over the same period: one Caspian grade above the "
                     "benchmark and one below, for quality in one case and sanctions in the other",
                     "other mature declining fields",
                     "scheduled maintenance months"),
        "notes": "a KNOWN FUTURE SUPPLY REDUCTION is rare; the tradeable part is the surprise "
                 "around a path everyone can read",
    },
    {
        "id": "AZ-E", "title": "The Southern Gas Corridor and European policy demand",
        "objects": ("Shah Deniz volumes to Turkey and Italy",
                    "TANAP and TAP capacity",
                    "expansion commitments with dated volumes",
                    "EU-Azerbaijan gas agreements"),
        "conditions": ("the desk's XNGUSD is HENRY HUB, not European -- every cell must say so",
                       "the European equity channel measured on EUSTX50 and GER40, which the desk "
                       "CAN see",
                       "the announcement response scaled by the actual volume, to separate "
                       "signalling from supply"),
        "instruments": ("XNGUSD", "EUSTX50", "GER40", "USDTRY"),
        "controls": ("US500, which has no European gas exposure",
                     "LNG supply announcements of comparable volume",
                     "the pre-2022 sample, when the corridor was a commercial story",
                     "the volume-scaled response as the explicit signalling test"),
        "notes": "after 2022 this stopped being commercial and became political; the honest form "
                 "of the domain models the announcement effect separately from the molecules",
    },
    {
        "id": "AZ-F", "title": "Gas swaps and the ambiguity of origin",
        "objects": ("reported export volumes by destination",
                    "domestic production",
                    "the production-minus-export gap",
                    "announced swap arrangements"),
        "conditions": ("the gap as the swap estimate",
                       "origin treated as AMBIGUOUS in every supply cell that uses reported "
                       "exports",
                       "swap announcements as discrete events"),
        "instruments": ("XNGUSD", "USDTRY", "USDRUB"),
        "controls": ("domestic production alone as the conservative supply measure",
                     "the counterparty's own reported exports, where published",
                     "periods with no announced swaps"),
        "notes": "the pack's most important measurement caveat on the gas side: a supply study "
                 "that treats reported exports as domestic production is measuring a trading "
                 "arrangement and calling it geology",
    },
    {
        "id": "AZ-G", "title": "Turkey as the only liquid proxy",
        "objects": ("USDTRY as the sole quoted regional instrument",
                    "Turkish gas imports from Azerbaijan",
                    "BTC loadings at Ceyhan",
                    "the shared Islamic holiday closures"),
        "conditions": ("USDTRY carries Turkish news as well as Azerbaijani, so the Turkish factor "
                       "must be removed before any Azerbaijani claim",
                       "the shared closures as the cleanest regional liquidity test",
                       "Turkish energy policy, which is a competing explanation for every "
                       "corridor observation"),
        "instruments": ("USDTRY", "XBRUSD", "XNGUSD"),
        "controls": ("Turkish domestic events with no Azerbaijani content, as the contamination "
                     "measure",
                     "days when Turkey is shut and Azerbaijan is not, and the reverse",
                     "the shared-closure days, where both are shut"),
        "notes": "every Azerbaijani signal that reaches a quoted instrument passes through Turkey, "
                 "so this domain is really about separating two countries inside one price",
    },
    {
        "id": "AZ-H", "title": "The Middle Corridor through Baku",
        "objects": ("Trans-Caspian freight volumes",
                    "Caspian ferry capacity, the bottleneck",
                    "Baku port throughput",
                    "transit times"),
        "conditions": ("capacity rather than demand as the binding constraint",
                       "substitution against the northern route as the mechanism",
                       "the shared observable with the Kazakh pack"),
        "instruments": ("USDCNH", "USDTRY"),
        "controls": ("northern-route volumes over the same period",
                     "the pre-2022 sample",
                     "the Kazakh end of the same corridor, which should move together"),
        "notes": "measuring this with KZ-J is the strongest available test: the two ends of one "
                 "corridor should move together, and if they do not the volumes are not the same "
                 "volumes",
    },
    {
        "id": "AZ-I", "title": "Inflation as the adjustment variable",
        "objects": ("monthly CPI",
                    "the real exchange rate computed from it",
                    "the refinancing rate's effect on domestic credit",
                    "wage and price dynamics under a fixed nominal rate"),
        "conditions": ("the REAL exchange rate as the object, since the nominal one is a constant",
                       "the refinancing rate as a credit instrument rather than a currency one",
                       "the pass-through from imported prices, which is direct under a peg"),
        "instruments": ("USDTRY", "USDX", "WHEAT"),
        "controls": ("a floating regional peer's real exchange rate over the same period",
                     "the imported-goods component of CPI",
                     "the pre-2017 floating window"),
        "notes": "under a peg the competitiveness story the exchange rate would tell elsewhere is "
                 "told by domestic prices instead; if the real rate does NOT move, the peg is "
                 "costless in competitiveness terms, which would be a genuinely surprising finding",
    },
    {
        "id": "AZ-J", "title": "Three calendars, a five-day Novruz, and a drifting collision",
        "objects": ("Novruz, five days from 20 to 24 March",
                    "Ramazan and Qurban bayrami, two days each, PROCLAIMED not computed",
                    "the transfer rule for coincident and weekend holidays",
                    "the collision of Ramazan bayrami with Novruz in 2026"),
        "conditions": ("the transfer rule applied -- Georgia next door has NO such rule",
                       "the Islamic feasts read from the proclaimed table, never computed",
                       "the eleven-day annual drift, which moves Ramazan bayrami through Novruz "
                       "over a run of years"),
        "instruments": ("USDTRY", "USDRUB", "XBRUSD"),
        "controls": ("the Turkish calendar, which SHARES the two Islamic feasts and differs on "
                     "everything else",
                     "the Georgian calendar next door, which transfers nothing",
                     "the Kazakh calendar, which shares Kurban and has a three-day Nauryz",
                     "collision years versus non-collision years"),
        "notes": "the collision is not a quirk of 2026: the lunar drift moves the feast through "
                 "Novruz over a run of years, and a calendar that does not handle it silently "
                 "loses or duplicates days in exactly the years when the closure is longest",
    },
    {
        "id": "AZ-K", "title": "Sovereign credit as the country's only continuous risk price",
        "objects": ("the sovereign and SOCAR eurobond spreads",
                    "rating review dates and outcomes",
                    "the Fund's assets, which drive the rating",
                    "index inclusion"),
        "conditions": ("the spread measured against a matched oil-exporting peer",
                       "rating reviews as scheduled events",
                       "the Fund's assets as the rating's principal input"),
        "instruments": ("UST10Y", "US500"),
        "controls": ("a matched oil-exporting sovereign with a FLOATING rate -- the difference in "
                     "oil sensitivity is the Fund's contribution",
                     "global EM credit spreads",
                     "non-review months"),
        "notes": "the currency cannot price risk because it is administered, so the credit market "
                 "does it instead; this is the only continuously-priced Azerbaijani risk object",
    },
    {
        "id": "AZ-L", "title": "Gold as the domestic hedge a pegged currency cannot provide",
        "objects": ("SOFAZ's reported physical gold holding",
                    "CBA reserve composition",
                    "domestic household gold demand",
                    "the absence of any domestic currency hedge"),
        "conditions": ("official and household demand separated, because they respond to "
                       "different things",
                       "the peg as the reason household demand exists: there is no domestic "
                       "instrument that hedges a devaluation",
                       "reserve composition changes reported quarterly"),
        "instruments": ("XAUUSD", "XAGUSD"),
        "controls": ("XAGUSD, where no comparable official demand exists",
                     "a floating regional peer's household gold demand",
                     "quarters with no reported composition change"),
        "notes": "a pegged currency offers households no way to hedge the tail risk of a "
                 "devaluation, so the hedge is physical; the 2015 memory is why the reflex exists",
    },
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "az_auction_volume_vs_oil", "domain_ids": ("AZ-C",), "kind": "flow",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.az.miners:auction_volume_vs_oil",
     "needs": ("SOFAZ auction results with timestamps", "XBRUSD D1 bars"),
     "notes": "the pack's core claim: auction volume rises as the oil price falls. If it does "
              "not, the mechanism described here is not the one operating"},
    {"name": "az_breakeven_gap", "domain_ids": ("AZ-B",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.az.miners:breakeven_gap",
     "needs": ("budget oil-price assumptions", "SOFAZ asset series", "XBRUSD D1 bars"),
     "notes": "regresses auction volume on the assumption-to-spot gap; the Fund's asset "
              "trajectory is the independent check"},
    {"name": "az_peg_refusal_guard", "domain_ids": ("AZ-A",), "kind": "failure",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.az.miners:peg_refusal_guard",
     "needs": ("any AZN series a future session might obtain",),
     "notes": "REFUSES any cell fitted to the pegged rate and says why; exists so that a later "
              "session with an AZN quote cannot accidentally fit a model to a constant"},
    {"name": "az_decline_path_deviation", "domain_ids": ("AZ-D",), "kind": "supply",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.az.miners:decline_path_deviation",
     "needs": ("ACG production and published decline path", "XBRUSD D1 bars"),
     "notes": "measures the DEVIATION from the announced path, not the decline; runs the Urals "
              "discount as the contrast"},
    {"name": "az_gas_announcement_vs_volume", "domain_ids": ("AZ-E",), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.az.miners:gas_announcement_vs_volume",
     "needs": ("SGC expansion announcements with dated volumes", "EUSTX50 and GER40 D1 bars"),
     "notes": "scales the response by the actual volume to separate political signalling from "
              "physical supply; states the Henry-Hub mismatch in every result"},
    {"name": "az_swap_origin_gap", "domain_ids": ("AZ-F",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.az.miners:swap_origin_gap",
     "needs": ("production and export statistics", "swap announcements"),
     "notes": "publishes the production-minus-export gap as the swap estimate and flags every "
              "supply cell that used reported exports as if they were production"},
    {"name": "az_turkey_contamination", "domain_ids": ("AZ-G",), "kind": "microstructure",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.az.miners:turkey_contamination",
     "needs": ("Turkish domestic event list", "USDTRY M15 bars", "Azerbaijani event list"),
     "notes": "measures how much of USDTRY's variance is Turkish before any Azerbaijani claim is "
              "made on it"},
    {"name": "az_shared_closure_liquidity", "domain_ids": ("AZ-J",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.az.miners:shared_closure_liquidity",
     "needs": ("Azerbaijani and Turkish holiday calendars", "USDTRY H1 bars"),
     "notes": "handles the Novruz collision explicitly; the shared Islamic closures are the "
              "cleanest regional liquidity test available in this region"},
)

# --------------------------------------------------------------------------- transmission edges
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "XBRUSD", "target": "USDTRY", "sign": "-",
     "mechanism": "Azerbaijan's oil revenue funds the transfer that funds the budget; the "
                  "regional proxy carries the Caucasus terms-of-trade signal because no "
                  "Azerbaijani instrument is quoted",
     "horizon": "20 to 90 sessions",
     "condition": "declared WEAK: Turkey is an oil IMPORTER, so the sign in USDTRY is Turkey's "
                  "own and the Azerbaijani content must be separated first",
     "control": "Turkish domestic events with no Azerbaijani content",
     "falsifier": "no residual Azerbaijani content after removing the Turkish factor, which would "
                  "mean Azerbaijani news does not reach a quoted instrument at all"},
    {"source": "SOFAZ auction volume", "target": "XBRUSD", "sign": "-",
     "mechanism": "the auction volume rises when the oil price falls, because the manat obligation "
                  "is fixed and fewer dollars are arriving; the volume is therefore a published, "
                  "dated READ on oil-revenue stress",
     "horizon": "20 to 90 sessions",
     "condition": "the relationship runs FROM oil TO volume; this edge is the inverse reading and "
                  "is useful as a confirmation rather than a predictor",
     "control": "periods of stable oil prices, where volume should be flat",
     "falsifier": "volume that does not rise as the price falls, which falsifies the pack's core "
                  "mechanism"},
    {"source": "Budget oil-price assumption minus spot Brent", "target": "XBRUSD",
     "sign": "two_sided",
     "mechanism": "the published assumption is a dated fiscal expectation; the gap to spot is a "
                  "measurable surprise and predicts auction volume",
     "horizon": "60 to 250 sessions",
     "condition": "measured at a fixed horizon; supplementary budgets revise the assumption",
     "control": "the Fund's asset trajectory as the independent check",
     "falsifier": "a gap that does not predict auction volume, which would break the fiscal "
                  "transmission this pack describes"},
    {"source": "BTC pipeline interruption", "target": "XBRUSD", "sign": "+",
     "mechanism": "Azeri Light's export route to the Mediterranean crosses Georgia; an "
                  "interruption is a physical supply event shared with the Georgian pack",
     "horizon": "0 to 10 sessions",
     "condition": "upstream production must be available or the interruption is not binding",
     "control": "XTIUSD, which shares the global price but not the route",
     "falsifier": "an equal XTIUSD response, which would make it a global price move"},
    {"source": "Southern Gas Corridor expansion commitment announcement", "target": "EUSTX50",
     "sign": "+",
     "mechanism": "Europe's only non-Russian Caspian route; after 2022 a dated volume commitment "
                  "is a policy event as much as a supply one and moves European industrial "
                  "sentiment",
     "horizon": "0 to 20 sessions",
     "condition": "the response must be SCALED BY VOLUME; a response larger than the molecules "
                  "justify is signalling and must be modelled separately",
     "control": "US500, which has no European gas exposure; and LNG announcements of comparable "
                "volume",
     "falsifier": "a volume-proportional response, which would mean it is supply and not "
                  "signalling -- the opposite of this edge's claim"},
    {"source": "Shah Deniz delivered volumes to Turkey", "target": "XNGUSD", "sign": "-",
     "mechanism": "Caspian gas displacing other supply into Turkey and onward to Europe",
     "horizon": "20 to 90 sessions",
     "condition": "declared WEAK: XNGUSD is HENRY HUB, not a European benchmark, and Azerbaijani "
                  "volumes are small relative to global gas",
     "control": "EUSTX50 and GER40, where the industrial-margin channel is measurable",
     "falsifier": "no measurable relationship, which is the expected outcome and would confirm "
                  "that the European channel must be measured on equity rather than on gas"},
    {"source": "ACG production deviation from the published decline path", "target": "XBRUSD",
     "sign": "-",
     "mechanism": "a KNOWN future supply reduction is priced in advance; only the deviation from "
                  "the announced path is news",
     "horizon": "20 to 120 sessions",
     "condition": "the deviation, never the level; the level is priced years ahead",
     "control": "the decline level itself, which should carry no information",
     "falsifier": "the level carrying information, which would mean the market has not priced a "
                  "path it can read"},
    {"source": "Azerbaijani gas swap arrangements", "target": "USDRUB", "sign": "two_sided",
     "mechanism": "swaps route molecules from one origin through another; a swap with a northern "
                  "counterparty is a re-export channel of the same class as the Georgian and "
                  "Kazakh ones",
     "horizon": "20 to 120 sessions",
     "condition": "the production-minus-export gap as the swap estimate; announcements as events",
     "control": "the counterparty's own reported exports where published",
     "falsifier": "no production-export gap, which would mean the swaps are small and the origin "
                  "ambiguity is not material"},
    {"source": "Shared Ramazan and Qurban bayrami closures (Azerbaijan and Turkey)",
     "target": "USDTRY", "sign": "two_sided",
     "mechanism": "the corridor's origin and its terminus close together, twice a year; the "
                  "regional book is thin on both sides at once",
     "horizon": "the closure days",
     "condition": "weekday closures only; and the Novruz collision years must be handled or the "
                  "day count is wrong",
     "control": "days when only one country is closed; and days when both are open",
     "falsifier": "no measurable difference in realised range or spread on the shared closures, "
                  "which would mean the offshore book fully replaces both domestic ones"},
    {"source": "SOFAZ gold holding and CBA reserve composition", "target": "XAUUSD", "sign": "+",
     "mechanism": "official demand from a sovereign fund, plus household demand that exists "
                  "BECAUSE the pegged currency offers no domestic devaluation hedge",
     "horizon": "60 to 250 sessions",
     "condition": "official and household demand separated; composition changes reported quarterly",
     "control": "XAGUSD, where no comparable official demand exists",
     "falsifier": "an equal silver response, which would make it a precious-complex move"},
    {"source": "Middle Corridor freight through Baku", "target": "USDCNH", "sign": "-",
     "mechanism": "China-Europe freight re-routing through the Caspian; ferry capacity is the "
                  "bottleneck and the corridor links this pack to the Kazakh one",
     "horizon": "60 to 250 sessions",
     "condition": "capacity as the binding variable, not demand",
     "control": "the Kazakh end of the same corridor, which should move together",
     "falsifier": "the two ends of one corridor moving differently, which would mean the volumes "
                  "are not the same volumes"},
    {"source": "Azerbaijani CPI (the real exchange rate under a fixed nominal rate)",
     "target": "USDTRY", "sign": "+",
     "mechanism": "with a constant nominal rate the real exchange rate adjusts through domestic "
                  "prices; Azerbaijani competitiveness against Turkey is therefore a CPI story",
     "horizon": "60 to 250 sessions",
     "condition": "the REAL rate, computed from both countries' CPI; the nominal rate is a "
                  "constant and carries nothing",
     "control": "a floating regional peer's real exchange rate",
     "falsifier": "a real rate that does not move despite a fixed nominal rate, which would mean "
                  "the peg is costless in competitiveness terms -- a surprising and important "
                  "finding if true"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the oil boom and the strong manat", "start": "2010-01-01", "end": "2015-02-20",
     "regime": "a managed rate near 0.78 per dollar through the high-oil-price years, with the "
               "Fund accumulating rapidly",
     "markers": ("peak ACG production and peak Fund accumulation",),
     "why_it_matters": "the accumulation that funded everything since; the regime is not "
                       "comparable with anything after 2015",
     "status": "SETTLED"},
    {"name": "the two devaluations", "start": "2015-02-21", "end": "2016-12-31",
     "regime": "a step devaluation in February 2015 from about 0.78 to 1.05, a float announced in "
               "December 2015, and a fall to about 1.55 -- two regime changes in one year",
     "markers": ("2015-02-21 the first devaluation", "2015-12-21 the float"),
     "why_it_matters": "THE ONLY PERIOD IN THE MODERN SERIES WHERE THE RATE MOVED, and the source "
                       "of the household dollarisation reflex that still drives AZ-L. Every "
                       "statistical property of the AZN series comes from these two days",
     "status": "SETTLED"},
    {"name": "the re-peg at 1.7000", "start": "2017-01-01", "end": "2020-02-29",
     "regime": "a de-facto peg at 1.7000 maintained by SOFAZ auctions, with reserves and Fund "
               "assets rebuilding",
     "markers": ("2017 the de-facto re-peg", "the auction mechanism becoming routine"),
     "why_it_matters": "the baseline for AZ-C: a period of stable oil prices where the auction "
                       "volume shows what 'normal' looks like",
     "status": "SETTLED"},
    {"name": "the pandemic oil collapse and the peg's first real test", "start": "2020-03-01",
     "end": "2021-12-31",
     "regime": "oil collapsing while the peg held; auction volumes rising sharply and the Fund "
               "drawing down",
     "markers": ("2020-04 the oil price collapse", "peak auction volumes"),
     "why_it_matters": "the cleanest natural experiment in the pack: a large oil shock with the "
                       "peg unchanged, so the entire adjustment is visible in the auction series",
     "status": "SETTLED"},
    {"name": "the European gas pivot", "start": "2022-01-01", "end": "2024-12-31",
     "regime": "Azerbaijani gas to Europe becoming a policy variable; expansion commitments; the "
               "Middle Corridor growing; oil revenue strong and the Fund rebuilding",
     "markers": ("2022 the EU-Azerbaijan gas memorandum",
                 "Middle Corridor volumes growing sharply"),
     "why_it_matters": "the era in which AZ-E stopped being a commercial domain and became a "
                       "political one, and the announcement effect began to exceed the molecules",
     "status": "SETTLED"},
    {"name": "declining oil, growing gas", "start": "2025-01-01", "end": "2099-12-31",
     "regime": "ACG decline continuing while gas expansion commitments accumulate; the peg "
               "holding on a Fund rebuilt through the high-price years",
     "markers": ("the crossover from an oil economy to a gas one",),
     "why_it_matters": "UNVERIFIED TAIL. Anything this pack asserts about 2025-2026 must be "
                       "re-read from cbar.az, oilfund.az and the consortium reports before a "
                       "study conditions on it",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "AZN is absent from the broker registry AND is a pegged constant",
     "measured": "no AZN symbol in data/universe/universe.json; the official rate has been "
                 "1.7000 since 2017",
     "consequence": "TWO independent reasons the currency cannot carry a cell. AZ-A exists to "
                    "refuse one explicitly: a statistical test on a constant reports a variance "
                    "near zero and a Sharpe that is an artefact of the denominator"},
    {"constraint": "no Azerbaijani instrument of any kind is quoted",
     "measured": "the Baku Stock Exchange and every Azerbaijani bond are absent from the registry",
     "consequence": "TRANSMISSION-ONLY by construction; every domain terminates in a foreign "
                    "symbol and USDTRY is the only regional proxy with real depth"},
    {"constraint": "USDTRY carries Turkish news as well as Azerbaijani",
     "measured": "the only liquid regional proxy is another country's currency",
     "consequence": "every Azerbaijani claim on USDTRY must first remove the Turkish factor. "
                    "AZ-G exists to measure the contamination before any claim is made"},
    {"constraint": "the desk's gas quote is Henry Hub, not European",
     "measured": "XNGUSD is a US benchmark",
     "consequence": "the Southern Gas Corridor edges are declared WEAK and the European channel "
                    "is measured on EUSTX50 and GER40 instead"},
    {"constraint": "gas swap arrangements make export origin ambiguous",
     "measured": "reported export volumes can exceed what domestic production supports",
     "consequence": "any supply study treating reported exports as domestic production is "
                    "measuring a trading arrangement. AZ-F publishes the production-minus-export "
                    "gap as the swap estimate"},
    {"constraint": "no manat positioning series exists and none could be informative",
     "measured": "no CME contract has ever existed for AZN; the rate is administered",
     "consequence": "manat positioning is permanently UNMEASURED; cot_currency is deliberately "
                    "empty"},
    {"constraint": "the Islamic feast dates are proclaimed, not computed",
     "measured": "the proclaimed date can differ from the astronomical one by a day",
     "consequence": "RAMAZAN_BAYRAMI and QURBAN_BAYRAMI are TABLES; a computed date is not the "
                    "authority. The 2026 collision with Novruz is handled explicitly because the "
                    "lunar drift moves the feast through Novruz over a run of years"},
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
