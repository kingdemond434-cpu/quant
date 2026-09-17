"""TURKEY: a contingent liability that grows with depreciation, and a carry the broker taxes 7x.

WHAT TURKEY IS AS A MARKET MECHANISM. Five things belong to this economy and to no other in the
desk's book, and one measurement decides how every one of them may be traded:

  1. THE STATE IS SHORT ITS OWN CURRENCY, ON A PUBLISHED WEEKLY CLOCK. FX-protected deposits
     (kur korumalı mevduat, KKM) pay a lira depositor the difference whenever the lira falls by
     more than the deposit rate. The scheme's stock is published weekly, so the sovereign's
     exposure to its own exchange rate is a DATED PUBLIC NUMBER -- and it is a feedback loop,
     because the payout is financed in lira and the financing is itself lira-negative. Nowhere
     else in this department is a government's currency exposure both explicit and observable.

  2. THE INFLATION PRINT IS DISPUTED IN PUBLIC. TÜİK publishes the official CPI; ENAG, an
     academic group, publishes a far higher alternative on the same day. The desk keeps BOTH and
     labels them honestly: the official series is the one POLICY reacts to and is therefore the
     one an event study must use, while the GAP between them is a dated, measurable proxy for
     how far household expectations have detached from the official number. ENAG is registered
     CONTRADICTED and kept at low weight -- never dropped, because a contested measurement is
     itself a measurement.

  3. THE RESERVE NUMBER THAT MATTERS IS NOT THE HEADLINE ONE. The CBRT publishes gross reserves
     weekly and also the components from which NET RESERVES EXCLUDING SWAPS can be derived. The
     headline and the swap-excluded figure have diverged by tens of billions of dollars, and the
     market trades the second. A study that uses gross reserves is measuring a different variable
     from the one participants watch, and `TR-B` is built on that distinction.

  4. THE GOLD MARKET IS PHYSICAL AND HAS A FREE-MARKET PREMIUM. Turkey is among the largest
     bullion importers in the world; imports run through Borsa İstanbul's Precious Metals Market
     under licence, and the Grand Bazaar (Kapalıçarşı) quotes a free-market gram price. The
     PREMIUM of that price over the London-implied gram (XAUUSD × USDTRY ÷ 31.1035) is a direct
     read on household stress that no FX quote provides -- and the identity itself is `TR-F`'s
     mandatory negative control, exactly as XAUAUD is in the Australian pack.

  5. THE CLOCK NEVER MOVES AND THE CALENDAR MOVES ELEVEN DAYS A YEAR. Istanbul has been a fixed
     UTC+3 since 2016, so every Turkish event minute in UTC is stable all year -- one of only
     three countries in this department where that is true. Against that, the two Bayram closures
     drift about eleven days earlier each solar year and each is preceded by a HALF-DAY arife
     that a naive holiday table reads as a full session.

AND THE MEASUREMENT THAT SHAPES EVERY CELL, taken on this box 2026-09-17: USDTRY has 37,394 H1
bars to 2026-09-16, a median H1 spread over the last sixty days of 405 points -- about 8bp on a
rate of 48.66 -- and ZERO frozen bars. It is a working market, unlike the Russian tape next door.
The cost is in the CARRY: the broker's swap table charges -10,921 points per lot per night to be
long USDTRY and pays +1,481 to be short, an asymmetry of roughly 7.4 to one. Holding the
depreciation trade costs seven times what the carry trade pays. Every Turkish cell is therefore
DIRECTION-DEPENDENT by construction and `TR-E` exists to enforce it; EURTRY (1,587 points, ~28bp)
and GBPTRY (2,405 points, ~37bp) are three to four times more expensive again.

THE TWO-LANE ORDER. Turkish Airlines, the banks, Koç and Sabancı appear here only as ACTORS. BIST
30, BIST 100, the VIOP contracts, Turkish government bonds and the Kapalıçarşı quote are all
ABSENT from this broker and are named in `TRANSMISSION_TARGETS` with the symbols they reach.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# ruff: noqa: RUF001, RUF002, RUF003
# RUF001/RUF002 flag characters that resemble ASCII ones -- Turkish dotless i, the
# multiplication sign in the gram-altin identity. The rule guards IDENTIFIERS against
# homoglyph attacks; this file carries Turkish terminology as DATA, and a query stripped
# of its diacritics finds far less than it appears to. No identifier here is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "TR"
NAME = "Republic of Türkiye"
#: Canonical token from `country_lab.REGION_COMMANDS`; `REGION_DESK` is the desk-facing label.
REGION_COMMAND = "mea"
REGION_DESK = "TURKEY"
CURRENCY = "TRY"
FISCAL_YEAR_END = "12-31"
NATIVE_LANGUAGES: tuple[str, ...] = ("tr",)

#: Fusion-quotable instruments a Turkish mechanism can reach. Nothing here is an equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDTRY",                        # 37,394 H1 bars, ~8bp median spread, 0% frozen
    "EURTRY", "GBPTRY",              # ~28bp and ~37bp: three to four times the cost
    "XAUUSD", "XAGUSD", "XAUEUR",    # the gram-altın identity and the import bill
    "XTIUSD", "XBRUSD", "XNGUSD",    # a large net energy importer
    "XCUUSD",                        # industrial demand and the export mix
    "WHEAT", "CORN", "COTTON",       # a large wheat importer and a cotton processor
    "USDRUB",                        # the Russia corridor: trade, tourism, gas, payments
    "EURUSD", "USDX",                # the euro is the trade currency and the dollar the factor
    "GER40", "EUSTX50",              # Europe is the largest export market
    "US500", "UST10Y",               # global risk and duration controls
    "USDCNH",                        # the import competition and the Middle Corridor
)

#: Turkish objects this broker does not quote. Each names the symbols its mechanism reaches.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "BIST 30 and BIST 100 indices", "venue": "Borsa İstanbul",
     "why": "the domestic equity market; heavily retail, with circuit breakers and a history of "
            "short-selling bans that make its microstructure unlike any European index here",
     "proxies": ("USDTRY", "EUSTX50", "GER40")},
    {"name": "VİOP BIST 30 index futures", "venue": "Borsa İstanbul derivatives",
     "why": "expiry on the LAST BUSINESS DAY of the even months, cash settled to a time-weighted "
            "average of the index's last thirty minutes -- a closing-average settlement, not an "
            "opening one like Australia's",
     "proxies": ("USDTRY", "EUSTX50")},
    {"name": "Kapalıçarşı free-market gram gold quote", "venue": "the Grand Bazaar",
     "why": "THE PREMIUM over the London-implied gram price is a direct read on household stress; "
            "it widens when access to official channels tightens and it has no FX analogue",
     "proxies": ("XAUUSD", "USDTRY", "XAGUSD")},
    {"name": "Borsa İstanbul Precious Metals Market and the import licence regime",
     "venue": "Borsa İstanbul",
     "why": "bullion imports run through licensed members, so the import statistic is a "
            "regulated, dated quantity and an import QUOTA is a policy shock with a date",
     "proxies": ("XAUUSD", "XAGUSD", "USDTRY")},
    {"name": "CBRT policy rate and the TRY overnight and swap curve", "venue": "CBRT / OTC",
     "why": "no Turkish short-rate instrument is quoted here, so the policy expectation must be "
            "sourced externally or declared UNMEASURED for that meeting",
     "proxies": ("USDTRY", "EURTRY")},
    {"name": "Turkish government bonds (DİBS) and the Treasury auction calendar",
     "venue": "Hazine / Borsa İstanbul",
     "why": "the domestic funding clock; non-resident holdings of government paper are published "
            "weekly and are the closest thing Turkey has to a positioning series",
     "proxies": ("USDTRY", "UST10Y")},
    {"name": "KKM (kur korumalı mevduat) outstanding stock", "venue": "CBRT / BDDK",
     "why": "a contingent fiscal liability that grows with depreciation, published weekly; the "
            "feedback loop is the mechanism and the stock is the observable",
     "proxies": ("USDTRY", "EURTRY")},
    {"name": "ENAG alternative consumer price index", "venue": "Enflasyon Araştırma Grubu",
     "why": "an academic alternative to the official CPI, published the same day and far higher. "
            "The GAP is a dated expectations proxy; the level is contested and is kept as such",
     "proxies": ("USDTRY", "XAUUSD")},
    {"name": "Turkish tourism receipts and arrivals by origin", "venue": "TÜİK / TGA",
     "why": "tourism is a large seasonal FX inflow and Russian and German arrivals dominate its "
            "swing; the seasonal partially offsets the energy import bill",
     "proxies": ("USDTRY", "USDRUB", "GER40")},
    {"name": "BOTAŞ gas import contracts and the domestic tariff", "venue": "BOTAŞ / EPDK",
     "why": "a state importer selling below cost domestically; the subsidy is a fiscal transfer "
            "whose size moves with the gas price and the exchange rate together",
     "proxies": ("XNGUSD", "XBRUSD", "USDTRY")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of the Republic of Türkiye (Türkiye Cumhuriyet Merkez Bankası)",
    "short": "CBRT / TCMB",
    "framework": "inflation_targeter",
    "committee": "Para Politikası Kurulu (Monetary Policy Committee, PPK)",
    "policy_instrument": "the one-week repo auction rate (politika faizi), with an overnight "
                         "lending and borrowing corridor around it",
    "corridor": "overnight borrowing and lending rates either side of the policy rate; the "
                "EFFECTIVE funding cost has repeatedly differed from the announced policy rate "
                "through quantitative and macroprudential measures, which is a Turkish-specific "
                "trap: the headline rate is not always the rate that binds",
    "mandate": "price stability; an inflation target of 5% has been the stated medium-term "
               "anchor while realised inflation has been multiples of it for years",
    "decision_rule": "EIGHT scheduled meetings a year (reduced from twelve for 2024 onward), "
                     "with the decision and a summary published at 14:00 Istanbul and the "
                     "meeting summary (özet) some days later. The Inflation Report (Enflasyon "
                     "Raporu) is quarterly and carries the forecast path.",
    "announce_local": "14:00 Europe/Istanbul",
    "announce_utc": "11:00",
    "announce_utc_dst": "11:00",
    "dst_rule": "NONE. Türkiye abolished seasonal clock changes in 2016 and Istanbul is a fixed "
                "UTC+3. Turkish event minutes in UTC are stable all year -- one of only three "
                "countries in this department where that is true",
    "presser_utc": "",
    "minutes_lag_days": 5,
    "consensus_proxy": "NO ON-BROKER PROXY. The usable public expectations are the CBRT's own "
                       "Market Participants Survey (Piyasa Katılımcıları Anketi) and the press "
                       "polls; both are SURVEYS and a surprise built from them is a weaker "
                       "object than a traded curve",
    "consensus_proxy_trap": "the ANNOUNCED policy rate and the EFFECTIVE funding cost have "
                            "diverged repeatedly through reserve requirements, securities "
                            "maintenance and selective credit measures. A surprise measured "
                            "against the announced rate alone can be exactly backwards when the "
                            "tightening was delivered macroprudentially instead",
    "distinctive": "the policy rate went from 19% to 8.5% while inflation rose above 80%, and "
                   "then from 8.5% to 50% inside a year. NO OTHER CENTRAL BANK IN THIS "
                   "DEPARTMENT HAS REVERSED ITS REACTION FUNCTION SO COMPLETELY INSIDE ONE "
                   "SAMPLE, which is why TR-A is built on the eras rather than pooled across them",
    "balance_sheet_history": (
        "KKM (kur korumalı mevduat) from 20 December 2021: a state-backed FX-indexed deposit",
        "a large swap book with domestic banks and with other central banks, which is why the "
        "SWAP-EXCLUDED net reserve figure and the headline figure diverge",
        "securities maintenance and reserve requirement rules used as quantitative instruments",
        "the 2023 normalisation: simplification of the macroprudential framework and a return to "
        "conventional tightening"),
    "off_cycle": "the Committee has moved out of cycle and has also changed the effective funding "
                 "cost between meetings; each is its own class and none may be pooled",
    "other_clocks": (
        {"what": "Weekly Money and Banking Statistics (reserves, swaps, deposits, KKM)",
         "when_local": "Thursday 14:30 Istanbul", "when_utc": "11:30", "reference_lag_days": 7},
        {"what": "Weekly Securities Statistics (non-resident holdings of equities and bonds)",
         "when_local": "Thursday 14:30 Istanbul", "when_utc": "11:30", "reference_lag_days": 7},
        {"what": "TÜİK consumer price index",
         "when_local": "the 3rd of the month, 10:00 Istanbul", "when_utc": "07:00",
         "reference_lag_days": 3},
        {"what": "Inflation Report (Enflasyon Raporu) with the forecast path",
         "when_local": "quarterly", "when_utc": "07:00", "reference_lag_days": 0},
        {"what": "Market Participants Survey (Piyasa Katılımcıları Anketi)",
         "when_local": "monthly", "when_utc": "11:30", "reference_lag_days": 0},
    ),
    "root": "https://www.tcmb.gov.tr",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CBRT indicative exchange rates (gösterge niteliğindeki kurlar)",
     "local": "struck around 15:30 Istanbul and published for the following day's official use",
     "time_utc": "12:30", "time_utc_dst": "12:30", "dst_rule": "none (Istanbul is fixed UTC+3)",
     "instruments": ("USDTRY", "EURTRY"), "window_minutes": 30, "confidence": "SETTLED",
     "why": "the rate customs valuations, tax liabilities and many contracts are struck at; it is "
            "indicative rather than transactable, which is why an effect here would be "
            "informative rather than mechanical"},
    {"name": "CBRT Weekly Money and Banking Statistics release",
     "local": "Thursday 14:30 Istanbul", "time_utc": "11:30", "time_utc_dst": "11:30",
     "dst_rule": "none", "instruments": ("USDTRY", "EURTRY"), "window_minutes": 30,
     "confidence": "SETTLED",
     "why": "the SWAP-EXCLUDED net reserve figure is derived from this release, and it is the "
            "number the market trades rather than the headline gross figure"},
    {"name": "Borsa İstanbul closing auction",
     "local": "18:00-18:10 Istanbul", "time_utc": "15:00", "time_utc_dst": "15:00",
     "dst_rule": "none", "instruments": (), "window_minutes": 10, "confidence": "SETTLED",
     "why": "sets the official BIST close. The index is NOT quoted here, so this is a "
            "transmission-target clock: it matters because the equity close and the lira's "
            "European-afternoon liquidity peak coincide"},
    {"name": "VİOP BIST 30 futures settlement average",
     "local": "the time-weighted average of the index over the last 30 minutes of the expiry "
              "session, 17:30-18:00 Istanbul",
     "time_utc": "14:30", "time_utc_dst": "14:30", "dst_rule": "none", "instruments": (),
     "window_minutes": 30, "confidence": "DECLARED, VERIFY against borsaistanbul.com",
     "why": "a CLOSING-average settlement, the opposite of the Australian SPI's opening quotation. "
            "Turkish index expiry risk therefore sits in the last half hour, not in a gap"},
    {"name": "LBMA gold price and the gram altın identity",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "confidence": "SETTLED",
     "why": "GRAM ALTIN IS XAUUSD × USDTRY ÷ 31.1035 TO ROUNDING. Every claim about Turkish gold "
            "demand must clear that arithmetic identity before it is a claim about Turkey at "
            "all, exactly as XAUAUD must in the Australian pack"},
    {"name": "Kapalıçarşı free-market gram quote",
     "local": "bazaar hours, roughly 09:00-19:00 Istanbul", "time_utc": "06:00",
     "time_utc_dst": "06:00", "dst_rule": "none", "instruments": ("XAUUSD", "USDTRY"),
     "window_minutes": 600, "confidence": "DECLARED",
     "why": "the free-market premium over the London-implied gram is the household-stress "
            "observable; it is quoted publicly by dealers and aggregated by the financial press, "
            "and it has no equivalent anywhere else in this department"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "TRY spot value date", "kind": "weekday", "convention": "T+2",
     "rollover_utc": "21:00 (EST) / 22:00 (EDT), 17:00 America/New_York",
     "instruments": ("USDTRY", "EURTRY", "GBPTRY"),
     "why": "THE ROLLOVER IS THE MECHANISM HERE, not a footnote. The broker charges -10,921 "
            "points a night to hold long USDTRY and pays +1,481 short; Wednesday triples both. A "
            "carry study that nets these symmetrically is measuring a trade nobody can put on"},
    {"name": "exporter FX conversion requirement", "kind": "weekday",
     "convention": "a share of export proceeds must be sold to the central bank through the "
                   "intermediary bank; the share has been changed repeatedly by communiqué",
     "rollover_utc": "11:30", "instruments": ("USDTRY",),
     "why": "a decreed lira bid whose SIZE steps when the communiqué steps -- the same shape as "
            "the Russian surrender decree, and each amendment is a structural break"},
    {"name": "CPI release day", "kind": "day_of_month",
     "convention": "the 3rd of each month at 10:00 Istanbul",
     "rollover_utc": "07:00", "instruments": ("USDTRY", "EURTRY", "XAUUSD"),
     "why": "a fixed CALENDAR DAY rather than a weekday rule, so the release walks through the "
            "week and a day-of-week control is mandatory"},
    {"name": "weekly statistics day", "kind": "weekday",
     "convention": "Thursday 14:30 Istanbul for money, banking and securities statistics",
     "rollover_utc": "11:30", "instruments": ("USDTRY",), "weekday": 3,
     "why": "the highest-frequency official window in this pack; reserves, the KKM stock and "
            "non-resident flows all land in the same minute"},
    {"name": "Treasury domestic auction calendar", "kind": "month_end",
     "convention": "announced monthly in the three-month domestic borrowing strategy",
     "rollover_utc": "08:00", "instruments": ("USDTRY", "UST10Y"),
     "why": "the funding clock; the strategy is published in advance so the supply is known"},
    {"name": "budget year", "kind": "fiscal_year_end", "convention": "31 December",
     "rollover_utc": "", "instruments": ("USDTRY",),
     "why": "the Medium Term Programme (Orta Vadeli Program) is published in September and "
            "carries the official exchange-rate and inflation assumptions for the coming years -- "
            "a dated fiscal expectation of the same class as Australia's iron-ore assumption"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Borsa İstanbul -- equity market",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "18:00", "open_utc": "07:00", "close_utc": "15:00",
     "dst_rule": "none (Istanbul is fixed UTC+3)",
     "auction": "opening auction, a midday break historically, closing auction 18:00-18:10",
     "expiry_rule": "n/a (cash)",
     "holidays": "the Turkish national calendar, INCLUDING the half-day arifes before each Bayram",
     "notes": "heavily retail and subject to circuit breakers (devre kesici) and, historically, "
              "short-selling bans. Its microstructure is unlike any European index in this book "
              "and the index is not quoted here in any case"},
    {"name": "Borsa İstanbul -- VİOP derivatives",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "18:15", "open_utc": "06:30", "close_utc": "15:15",
     "dst_rule": "none", "auction": "n/a",
     "expiry_rule": "BIST 30 index futures trade the February, April, June, August, October and "
                    "December cycle and expire on the LAST BUSINESS DAY of the contract month, "
                    "cash settled to the time-weighted average of the index over the last thirty "
                    "minutes of that session",
     "holidays": "the Turkish national calendar",
     "notes": "the CLOSING-average settlement is the structural opposite of the Australian SPI's "
              "special OPENING quotation; Turkish expiry risk sits in the last half hour"},
    {"name": "Borsa İstanbul -- Precious Metals and Diamond Market",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "17:30", "open_utc": "06:30", "close_utc": "14:30",
     "dst_rule": "none", "auction": "continuous",
     "expiry_rule": "n/a",
     "holidays": "the Turkish national calendar",
     "notes": "BULLION IMPORTS RUN THROUGH LICENSED MEMBERS HERE. That makes the import statistic "
              "a regulated, dated quantity and makes an import QUOTA a policy shock with a date, "
              "which is how TR-F separates a demand story from an administrative one"},
)


# --------------------------------------------------------------------------- holidays
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    first += timedelta(days=(weekday - first.weekday()) % 7)
    return first + timedelta(days=7 * (n - 1))


#: Fixed-date Turkish public holidays. Note 28 October: a HALF DAY from 13:00, followed by the
#: full-day Republic Day on 29 October.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Yılbaşı (New Year's Day)"),
    (4, 23, "Ulusal Egemenlik ve Çocuk Bayramı (National Sovereignty and Children's Day)"),
    (5, 1, "Emek ve Dayanışma Günü (Labour and Solidarity Day)"),
    (5, 19, "Atatürk'ü Anma, Gençlik ve Spor Bayramı (Commemoration of Atatürk, Youth and Sports)"),
    (7, 15, "Demokrasi ve Millî Birlik Günü (Democracy and National Unity Day)"),
    (8, 30, "Zafer Bayramı (Victory Day)"),
    (10, 29, "Cumhuriyet Bayramı (Republic Day)"),
)

#: THE TWO BAYRAMS ARE PROCLAIMED, NOT COMPUTED, and they drift about eleven days earlier each
#: solar year. RAMAZAN BAYRAMI is three days and KURBAN BAYRAMI is four; each is preceded by an
#: ARIFE half-day from 13:00 that a naive table reads as a full session. Tabulated because the
#: official proclamation, not an astronomical formula, is the authority.
RAMAZAN_BAYRAMI: dict[int, date] = {
    2024: date(2024, 4, 10), 2025: date(2025, 3, 30), 2026: date(2026, 3, 20),
    2027: date(2027, 3, 10),
}
KURBAN_BAYRAMI: dict[int, date] = {
    2024: date(2024, 6, 16), 2025: date(2025, 6, 6), 2026: date(2026, 5, 27),
    2027: date(2027, 5, 17),
}


def national_holidays(year: int) -> dict[date, str]:
    """Türkiye's full-day public holidays for `year`: the fixed dates plus the two Bayrams.

    Ramazan Bayramı is THREE days and Kurban Bayramı is FOUR. Neither is Mondayised: Turkish law
    does not transfer a holiday that falls at a weekend, it is simply absorbed -- the same rule
    as Georgia's and the opposite of Russia's, Kazakhstan's and Azerbaijan's. The half-day arifes
    are NOT here; they are in `half_days` because a half session is not a closure and conflating
    the two is how a session filter silently drops or invents trading hours.
    """
    out: dict[date, str] = {}
    for month, day, label in FIXED_NATIONAL:
        out[date(year, month, day)] = label
    ramazan = RAMAZAN_BAYRAMI.get(year)
    if ramazan is not None:
        for offset in range(3):
            out[ramazan + timedelta(days=offset)] = f"Ramazan Bayramı, gün {offset + 1}"
    kurban = KURBAN_BAYRAMI.get(year)
    if kurban is not None:
        for offset in range(4):
            out[kurban + timedelta(days=offset)] = f"Kurban Bayramı, gün {offset + 1}"
    return dict(sorted(out.items()))


def half_days(year: int) -> dict[date, str]:
    """HALF SESSIONS, closing at 13:00 Istanbul: the arife before each Bayram, and 28 October.

    A half day is not a holiday and it is not a full session. A volatility or range study that
    treats an arife as an ordinary day is averaging a three-and-a-half-hour session into a sample
    of seven-hour ones, and the effect is large enough to manufacture a spurious calendar result.
    """
    out: dict[date, str] = {date(year, 10, 28): "Cumhuriyet Bayramı arifesi (half day from 13:00)"}
    ramazan = RAMAZAN_BAYRAMI.get(year)
    if ramazan is not None:
        out[ramazan - timedelta(days=1)] = "Ramazan Bayramı arifesi (half day from 13:00)"
    kurban = KURBAN_BAYRAMI.get(year)
    if kurban is not None:
        out[kurban - timedelta(days=1)] = "Kurban Bayramı arifesi (half day from 13:00)"
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The days Borsa İstanbul is CLOSED. Identical to the national full-day set: the exchange
    follows the national calendar and keeps no separate one."""
    return national_holidays(year)


def bayram_windows(year: int) -> tuple[tuple[date, date], ...]:
    """The two extended closures as (first, last) full-day pairs, arife excluded.

    These are the longest scheduled Turkish closures and they MOVE about eleven days earlier each
    solar year, so a fixed-calendar seasonal will drift off them within three years.
    """
    out: list[tuple[date, date]] = []
    ramazan = RAMAZAN_BAYRAMI.get(year)
    if ramazan is not None:
        out.append((ramazan, ramazan + timedelta(days=2)))
    kurban = KURBAN_BAYRAMI.get(year)
    if kurban is not None:
        out.append((kurban, kurban + timedelta(days=3)))
    return tuple(out)


def viop_expiries(year: int) -> dict[date, str]:
    """VİOP BIST 30 index-futures expiry: the LAST BUSINESS DAY of February, April, June, August,
    October and December, skipping back over weekends and national holidays."""
    closed = set(national_holidays(year))
    out: dict[date, str] = {}
    for month in (2, 4, 6, 8, 10, 12):
        day = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(1)
        while day.weekday() >= 5 or day in closed:
            day -= timedelta(days=1)
        out[day] = f"VİOP BIST 30 expiry {year}-{month:02d}"
    return out


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_plus_proclaimed_lunar_table",
    "authority": "Law 2429 on national holidays and general holidays for the fixed dates; "
                 "official proclamation for the two Bayrams and for any additional bridging days",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "fixed_rule": "1 January, 23 April, 1 May, 19 May, 15 July, 30 August and 29 October",
    "lunar_rule": "Ramazan Bayramı is THREE full days and Kurban Bayramı is FOUR, both proclaimed "
                  "rather than computed, both drifting about eleven days earlier each solar year",
    "half_day_rule": "the arife before each Bayram and 28 October are HALF SESSIONS closing at "
                     "13:00 Istanbul. A half day is not a closure and not a full session; "
                     "conflating them is how a session filter invents or drops trading hours",
    "mondayisation_rule": "NONE. Turkish law absorbs a holiday that falls at a weekend rather "
                          "than transferring it -- the same as Georgia and the OPPOSITE of "
                          "Russia, Kazakhstan and Azerbaijan, all of which transfer",
    "bridging_note": "the government sometimes proclaims additional bridging days to extend a "
                     "Bayram into a full week, especially when the closure abuts a weekend. Those "
                     "are DECREED and not derivable; this module computes only the statutory set "
                     "and the extra days are UNMEASURED here rather than guessed",
    "known_dates": {
        "2026-03-19": "Ramazan Bayramı arifesi, a HALF DAY from 13:00",
        "2026-03-20": "Ramazan Bayramı day 1 (through 22 March)",
        "2026-05-26": "Kurban Bayramı arifesi, a HALF DAY from 13:00",
        "2026-05-27": "Kurban Bayramı day 1 (through 30 May) -- THE SAME DAY as Azerbaijan's "
                      "Qurban bayramı and Kazakhstan's Kurban Ait, so three markets in this "
                      "department close together",
        "2026-10-28": "Cumhuriyet Bayramı arifesi, a HALF DAY from 13:00",
        "2026-10-29": "Cumhuriyet Bayramı, a full closure",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "half_days_fn": half_days,
    "bayram_fn": bayram_windows,
    "expiry_fn": viop_expiries,
    "ramazan": RAMAZAN_BAYRAMI,
    "kurban": KURBAN_BAYRAMI,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = ""
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders for TRY", "root": "", "fields": (), "frequency": "n/a",
     "snapshot": "", "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "there is no liquid CME Turkish lira contract carrying a reportable COT series",
     "pit_warning": "DOES NOT EXIST. Lira positioning has NO COT series, and cot_currency on this "
                    "pack is deliberately empty. It must be reported UNMEASURED and never proxied "
                    "by another EM currency's COT, which is a different set of participants"},
    {"name": "CBRT Weekly Securities Statistics (non-resident holdings)",
     "root": "https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/",
     "fields": ("equities_held_by_non_residents", "gddS_held_by_non_residents", "weekly_change"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "11:30", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "THE CLOSEST THING TURKEY HAS TO A POSITIONING SERIES: weekly non-resident holdings "
            "of equities and government paper, in dollars, free and dated",
     "pit_warning": "the reference week ends the PRECEDING Friday, so the series is seven days "
                    "stale on release; and the dollar value mixes flow with valuation, which "
                    "must be separated or a price move is read as a flow"},
    {"name": "CBRT weekly reserves and the swap-excluded net figure",
     "root": "https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/",
     "fields": ("gross_reserves", "net_reserves", "swaps_with_banks", "net_ex_swap"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "11:30", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "the market trades the SWAP-EXCLUDED net figure, not the headline gross one; the two "
            "have diverged by tens of billions of dollars",
     "pit_warning": "the swap-excluded figure is DERIVED, not published directly, and different "
                    "analysts derive it differently. The derivation must be stated with the "
                    "result or two studies will disagree without either being wrong"},
    {"name": "BIST foreign ownership ratio", "root": "https://www.borsaistanbul.com/en/",
     "fields": ("foreign_ownership_pct", "free_float_share"), "frequency": "daily",
     "snapshot": "session close", "publish_utc": "15:30", "lag_days": 1,
     "licence": "free headline; detailed data licensed", "available": True,
     "why": "the equity side of the same non-resident flow, at daily rather than weekly frequency",
     "pit_warning": "the ratio moves with PRICE as well as with flow; a rally raises the ratio "
                    "with no purchase at all"},
    {"name": "KKM outstanding stock", "root": "https://www.bddk.org.tr/",
     "fields": ("kkm_stock_try", "kkm_stock_usd", "weekly_change", "corporate_share"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "11:30", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "not a positioning series in the usual sense but the closest public measure of how "
            "much of the domestic deposit base is EFFECTIVELY SHORT the lira with a state "
            "guarantee behind it",
     "pit_warning": "the stock is reported in lira and in dollars and the two tell different "
                    "stories during a depreciation; the dollar series is the exposure measure"},
)

# --------------------------------------------------------------------------- terminology
#: Turkish, with its diacritics intact. A query stripped of them ("kur korumali mevduat") finds
#: far less than it appears to, and the Grand Bazaar's vocabulary ("has altın", "çeyrek") has no
#: English search that reaches it at all.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "TR-A": ("faiz kararı", "politika faizi", "Para Politikası Kurulu", "PPK", "haftalık repo",
             "faiz koridoru", "sıkılaşma", "gevşeme", "sadeleşme", "ortodoks politika"),
    "TR-B": ("rezervler", "brüt rezerv", "net rezerv", "swap hariç net rezerv", "swap stoku",
             "rezerv erimesi", "haftalık para ve banka istatistikleri"),
    "TR-C": ("kur korumalı mevduat", "KKM", "kur farkı ödemesi", "Hazine yükü",
             "TL'ye geçiş", "liralaşma", "bakiye", "çıkış"),
    "TR-D": ("enflasyon", "TÜFE", "ÜFE", "çekirdek enflasyon", "C endeksi", "yıllık enflasyon",
             "ENAG", "beklenti anketi", "fiyat istikrarı"),
    "TR-E": ("kaldıraç", "teminat tamamlama", "swap maliyeti", "taşıma maliyeti", "gecelik faiz",
             "pozisyon taşıma", "carry", "faiz farkı"),
    "TR-F": ("gram altın", "has altın", "çeyrek altın", "yarım altın", "tam altın",
             "altın ithalatı", "külçe altın", "ziynet"),
    "TR-G": ("Kapalıçarşı", "serbest piyasa", "makas", "kuyumcu", "sarrafiye", "ons",
             "serbest piyasa kuru", "efektif"),
    "TR-H": ("BIST", "BIST 30", "BIST 100", "VİOP", "vade sonu", "uzlaşma fiyatı",
             "devre kesici", "açığa satış yasağı", "kapanış seansı"),
    "TR-I": ("Rusya ticareti", "doğalgaz", "turist sayısı", "Rus turist", "transit",
             "ödeme kanalı", "muhabir banka"),
    "TR-J": ("Hazine ihalesi", "DİBS", "iç borçlanma stratejisi", "itfa", "Orta Vadeli Program",
             "OVP", "bütçe açığı"),
    "TR-K": ("Ramazan Bayramı", "Kurban Bayramı", "arife", "yarım gün", "resmî tatil",
             "idari izin", "köprü tatil"),
    "TR-L": ("yabancı payı", "yabancı takas oranı", "portföy girişi", "sıcak para",
             "yurt dışı yerleşikler", "menkul kıymet istatistikleri"),
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
#: the only record that it was ever made. Turkey is the country in this department where that
#: rule does the most work, because its inflation print is publicly contested.
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")

#: The third label, and the only one the desk can EARN: whether anything from this source has
#: ever predicted anything. UNTESTED is the honest default and is not a criticism.
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
    searches "Turkish inflation" finds the small English-speaking corner of a very large Turkish
    ground and then reports that corner as if it were the ground.

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
    """A layer this country has nothing in, declared BY NAME with the reason."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    """How many real sources this pack names in each of the ten layers. An `absent_*` row does
    not count -- declaring a layer absent is honest, not coverage."""
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
    """Sources per layer, every empty layer named, and the numbers that must stay at zero."""
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


#: TÜRKİYE'S TEN LAYERS, in TURKISH WITH DIACRITICS. Turkey has the deepest retail trading
#: culture in this department outside Russia -- a large domestic terminal ecosystem, an enormous
#: forum and social-media layer, and a physical gold market with its own vocabulary -- and none
#: of it is reachable from English.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "tr_tcmb", "Central Bank of the Republic of Türkiye", layer="official",
        roots=("https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Announcements/",
               "https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/",
               "https://evds2.tcmb.gov.tr/"),
        queries=("faiz kararı", "politika faizi", "Para Politikası Kurulu", "PPK özeti",
                 "haftalık para ve banka istatistikleri", "rezervler", "swap stoku",
                 "menkul kıymet istatistikleri", "Enflasyon Raporu",
                 "Piyasa Katılımcıları Anketi", "EVDS"),
        languages=("tr", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="EVDS is a genuine open statistical API and is the single most useful official root "
              "in this pack. The SWAP-EXCLUDED net reserve figure is DERIVED from the weekly "
              "release, not published directly, and the derivation must travel with the result"),
    source_class(
        "tr_tuik", "Turkish Statistical Institute (TÜİK)", layer="official",
        roots=("https://data.tuik.gov.tr/", "https://www.tuik.gov.tr/"),
        queries=("TÜFE", "ÜFE", "enflasyon", "çekirdek enflasyon", "C endeksi",
                 "dış ticaret istatistikleri", "altın ithalatı", "turizm geliri",
                 "işgücü istatistikleri", "haber bülteni takvimi"),
        languages=("tr", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CPI lands on the 3rd at 10:00 Istanbul = 07:00 UTC, a fixed CALENDAR DAY that "
              "walks through the week, so a day-of-week control is mandatory. The monthly GOLD "
              "IMPORT value in the trade statistics is TR-F's quantity"),
    source_class(
        "tr_hazine_bddk", "Ministry of Treasury and Finance and the BDDK", layer="official",
        roots=("https://www.hmb.gov.tr/", "https://www.bddk.org.tr/",
               "https://www.sbb.gov.tr/orta-vadeli-programlar/"),
        queries=("Hazine ihalesi", "iç borçlanma stratejisi", "itfa takvimi", "bütçe "
                 "gerçekleşmeleri", "kur korumalı mevduat", "KKM bakiyesi", "Orta Vadeli Program",
                 "OVP kur varsayımı"),
        languages=("tr", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the KKM stock is published weekly and the Medium Term Programme carries the "
              "official exchange-rate assumption -- a dated fiscal expectation of the same class "
              "as Australia's iron-ore price deck, in an economy where it matters far more"),
    source_class(
        "tr_borsa_istanbul", "Borsa İstanbul", layer="institutional",
        roots=("https://www.borsaistanbul.com/en/", "https://www.borsaistanbul.com/tr/"),
        queries=("VİOP vade sonu", "uzlaşma fiyatı", "kapanış seansı", "devre kesici",
                 "açığa satış", "kıymetli madenler piyasası", "altın ithalat üyesi",
                 "yabancı takas oranı", "işlem takvimi"),
        languages=("tr", "en"), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free headline and end-of-day; depth LICENSED",
        notes="BULLION IMPORTS RUN THROUGH LICENSED MEMBERS OF THE PRECIOUS METALS MARKET, which "
              "makes the import statistic a regulated quantity and an import quota a dated policy "
              "shock. The VİOP settlement is a CLOSING average, the opposite of the Australian "
              "SPI's opening quotation"),
    source_class(
        "tr_tbb_tspb", "Banks Association of Türkiye, TSPB and the industry bodies",
        layer="institutional",
        roots=("https://www.tbb.org.tr/", "https://www.tspb.org.tr/"),
        queries=("bankacılık sektörü verileri", "mevduat dağılımı", "yatırımcı sayısı",
                 "aracı kurum verileri", "yerli yatırımcı", "hesap sayısı"),
        languages=("tr",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="TSPB publishes brokerage industry aggregates including INVESTOR AND ACCOUNT COUNTS "
              "-- the best public read on the size of the retail base that dominates BIST, which "
              "no official statistic captures"),
    source_class(
        "tr_multilateral", "IMF, OECD, World Bank and BIS Türkiye coverage",
        layer="institutional",
        roots=("https://www.imf.org/en/Countries/TUR", "https://data.oecd.org/",
               "https://www.bis.org/statistics/"),
        queries=("Article IV", "external financing requirement", "reserve adequacy",
                 "FX turnover", "triennial survey", "dolarizasyon"),
        languages=("en", "tr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the IMF's external financing requirement estimate is the standard framing for "
              "Turkish balance-of-payments stress and is the comparison TR-B needs"),
    source_class(
        "tr_tcmb_research", "CBRT working papers and Economic Notes", layer="academic",
        roots=("https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Publications/"
               "Research/Working+Papers/",),
        queries=("çalışma tebliği", "ekonomi notları", "kur geçişkenliği", "pass-through",
                 "rezerv yeterliliği", "dolarizasyon", "kredi kanalı"),
        languages=("tr", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the exchange-rate pass-through literature for Turkey is unusually large because "
              "the question has been unusually urgent; this is where the elasticities TR-D needs "
              "are estimated"),
    source_class(
        "tr_academic", "Turkish universities, DergiPark and the international literature",
        layer="academic",
        roots=("https://dergipark.org.tr/", "https://papers.ssrn.com/",
               "https://ideas.repec.org/"),
        queries=("kur korumalı mevduat etkisi", "enflasyon beklentileri", "altın talebi Türkiye",
                 "döviz kuru oynaklığı", "BIST volatilite", "Ramazan etkisi", "bayram etkisi"),
        languages=("tr", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="DergiPark is open access; other terms vary",
        notes="DergiPark is a free full-text Turkish academic archive and carries the domestic "
              "literature on the BAYRAM EFFECT and on household gold demand -- two mechanisms "
              "this pack tests that the international literature barely mentions"),
    source_class(
        "tr_enag", "ENAG, the Inflation Research Group", layer="academic",
        roots=("https://enagrup.org/",),
        queries=("ENAG", "ENAGrup", "E-TÜFE", "alternatif enflasyon", "gerçek enflasyon",
                 "enflasyon farkı"),
        languages=("tr",), access_label="PUBLIC", credibility="CONTRADICTED",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public web; automated extraction restricted",
        notes="AN ACADEMIC GROUP PUBLISHING AN ALTERNATIVE CPI FAR ABOVE THE OFFICIAL ONE, on the "
              "same day. CONTRADICTED AND KEPT AT LOW WEIGHT, NEVER DROPPED: the official series "
              "is what POLICY reacts to and is the one an event study must use, while the GAP "
              "between the two is a dated, measurable proxy for how far household expectations "
              "have detached from the official number. Deleting a contested measurement destroys "
              "the only record that the contest exists"),
    source_class(
        "tr_practitioner", "Turkish broker research, Matriks commentary and economist notes",
        layer="practitioner",
        roots=("https://www.isyatirim.com.tr/", "https://www.garantibbvayatirim.com.tr/",
               "https://www.matriksdata.com/"),
        queries=("strateji raporu", "günlük bülten", "kur beklentisi", "faiz beklentisi",
                 "hedef fiyat", "teknik analiz", "destek direnç", "piyasa yorumu"),
        languages=("tr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NOT_PREDICTIVE", machine_use_allowed=False,
        licence="public web; redistribution restricted",
        notes="NOT_PREDICTIVE is a measured verdict about published lira forecasts across the "
              "unorthodox era, not a slur: the consensus was directionally wrong for years, which "
              "is itself the most interesting fact about it. Read and cited, never scraped"),
    source_class(
        "tr_telegram_twitter", "Turkish macro Telegram channels and finance X/Twitter",
        layer="practitioner",
        roots=("https://t.me/s/", "https://x.com/"),
        queries=("rezerv verisi", "swap hariç net rezerv", "KKM bakiyesi", "TÜFE beklenti",
                 "kur tahmini", "faiz kararı bekleniyor", "dolar yorum"),
        languages=("tr",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public channels and accounts; automated extraction restricted",
        notes="the swap-excluded net reserve number is DERIVED and the derivation is argued out "
              "in public here every Thursday afternoon, which is where the market's working "
              "definition actually forms. A conditioning variable, never evidence"),
    source_class(
        "tr_eksi_sozluk", "Ekşi Sözlük", layer="retail_ecology",
        roots=("https://eksisozluk.com/",),
        queries=("dolar kuru", "enflasyon", "asgari ücret", "kira zammı", "altın almak",
                 "döviz bozdurmak", "kur korumalı mevduat", "borsa"),
        languages=("tr",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public collaborative dictionary; automated extraction restricted",
        notes="TURKEY'S DEFINING SOCIAL PLATFORM and a genuine high-frequency record of household "
              "inflation and currency expectation, timestamped entry by entry. FRINGE AND KEPT AT "
              "LOW WEIGHT: it is opinion, it is unrepresentative, and it is the only daily series "
              "on a belief that official surveys measure monthly"),
    source_class(
        "tr_investing_forums", "Investing.com Türkiye, Bigpara and the borsa forums",
        layer="retail_ecology",
        roots=("https://tr.investing.com/", "https://bigpara.hurriyet.com.tr/",
               "https://www.donanimhaber.com/forum/"),
        queries=("borsa forum", "hisse yorum", "tahtayı topluyorlar", "balina", "kısa pozisyon",
                 "teminat tamamlama", "marj çağrısı", "kaldıraçlı işlem"),
        languages=("tr",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public forums; automated extraction restricted",
        notes="BIST is unusually retail-dominated and the forums are where crowding and margin "
              "stress are described before they appear in any statistic. Low weight, never zero"),
    source_class(
        "tr_kuyumcu_social", "Jeweller and bullion-dealer social feeds", layer="retail_ecology",
        roots=("https://altinkaynak.com/", "https://www.harem.com.tr/", "https://t.me/s/"),
        queries=("gram altın fiyatı", "has altın", "çeyrek altın", "serbest piyasa",
                 "kuyumcu makas", "sarrafiye", "külçe altın", "Kapalıçarşı fiyat"),
        languages=("tr",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public dealer pages and channels; automated extraction restricted",
        notes="THE FREE-MARKET GOLD PREMIUM LIVES HERE. Dealers quote a gram price publicly all "
              "day; its spread over the London-implied gram is the household-stress observable "
              "TR-G is built on, and it exists in no official series"),
    source_class(
        "tr_matriks_ideal", "Matriks, İdeal Veri and the domestic terminal ecosystem",
        layer="app_ecosystem",
        roots=("https://www.matriksdata.com/", "https://www.idealdata.com.tr/",
               "https://www.foreks.com/"),
        queries=("Matriks", "İdeal Veri", "Foreks", "veri terminali", "derinlik", "kademe",
                 "emir defteri", "algoritmik işlem", "otomatik emir", "koşullu emir",
                 "sistem tüccarı"),
        languages=("tr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="commercial terminals; product pages public, data LICENSED",
        notes="TURKEY HAS ITS OWN DOMESTIC TERMINAL ECOSYSTEM, which most emerging markets do "
              "not. Matriks is to Turkish retail what QUIK is to Russian, with its own scripting "
              "and its own vocabulary ('kademe' for a price step, 'derinlik' for the book), and "
              "an English-language search reaches none of it"),
    source_class(
        "tr_mql5_tr", "MetaTrader Turkish sections and the robot market", layer="app_ecosystem",
        roots=("https://www.mql5.com/tr/market", "https://www.mql5.com/tr/code",
               "https://www.mql5.com/tr/forum"),
        queries=("uzman danışman", "al sat robotu", "EA", "MQL5", "strateji test edici",
                 "optimizasyon", "kayma", "gösterge", "USDTRY robotu", "altın robotu",
                 "skalping", "arbitraj", "martingale", "grid sistemi"),
        languages=("tr",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms; the desk already mines MQL5",
        notes="the MetaTrader TURKISH sections are large and are dominated by XAUUSD and USDTRY "
              "robots -- exactly the two instruments this pack cares about. 'Uzman danışman' is "
              "the Turkish for expert advisor and no English query finds these listings"),
    source_class(
        "tr_broker_apps", "Turkish retail brokerage and banking investment apps",
        layer="app_ecosystem",
        roots=("https://www.isyatirim.com.tr/", "https://www.midasmenkul.com/",
               "https://www.gedik.com/"),
        queries=("yatırım hesabı", "komisyon oranı", "kaldıraç oranı", "TL mevduat faizi",
                 "yurt dışı hisse", "Midas", "mobil uygulama", "emir iletim"),
        languages=("tr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public product pages; account data is PRIVATE and is never sought",
        notes="what Turkish retail can reach and at what leverage; the regulator caps FX leverage "
              "for residents, which shapes who is on the other side of a lira stop cascade. NO "
              "ACCOUNT-LEVEL DATA is sought"),
    source_class(
        "tr_press", "Dünya, Ekonomim, Bloomberg HT and the business press", layer="media",
        roots=("https://www.dunya.com/", "https://www.ekonomim.com/",
               "https://www.bloomberght.com/"),
        queries=("faiz kararı", "rezerv verisi", "enflasyon verisi", "KKM", "Hazine ihalesi",
                 "altın ithalatı", "turizm geliri", "cari açık"),
        languages=("tr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public web; automated extraction restricted",
        notes="Dünya and Ekonomim carry the fastest Turkish-language coverage of the weekly "
              "statistics; read and cited, never scraped"),
    source_class(
        "tr_intl_wires", "Reuters, Bloomberg and the international Türkiye desks", layer="media",
        roots=("https://www.reuters.com/world/middle-east/",
               "https://www.bloomberg.com/europe"),
        queries=("Turkish lira", "CBRT decision", "reserves", "rate cut", "inflation data"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="terminal and wire content is LICENSED; the desk holds no licence",
        notes="REGISTERED BECAUSE THE ABSENCE MATTERS: the wire timestamp is the market's event "
              "time for many lira stories and the desk cannot see it. Its best timestamp is a "
              "free outlet's republication, minutes to hours late -- a named limitation on every "
              "TR-A and TR-B event window"),
    source_class(
        "tr_wayback", "Internet Archive captures of tcmb.gov.tr, tuik.gov.tr and bddk.org.tr",
        layer="archive",
        roots=("https://web.archive.org/web/*/tcmb.gov.tr*",
               "https://web.archive.org/web/*/tuik.gov.tr*",
               "https://web.archive.org/web/*/bddk.org.tr*"),
        queries=("arşiv", "ilk yayın", "revize edildi", "kaldırılan veri", "eski bülten",
                 "yöntem değişikliği"),
        languages=("tr", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="TÜİK has revised methodology and reorganised its release pages more than once, and "
              "the KKM statistics moved between publishers during the wind-down. The Wayback "
              "capture is often the only surviving record of what a series said on the day"),
    source_class(
        "tr_national_archive", "Turkish national library and the newspaper archives",
        layer="archive",
        roots=("https://www.millikutuphane.gov.tr/", "https://www.dunya.com/arsiv"),
        queries=("arşiv", "1994 krizi", "2001 krizi", "2018 kur krizi", "devalüasyon",
                 "IMF programı", "tarihsel enflasyon"),
        languages=("tr",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public archive; reading-room and site terms govern reuse",
        notes="1994, 2001 and 2018 are the three crises every Turkish market participant reasons "
              "from, and the contemporaneous record is the only way to read an era as it was read "
              "at the time rather than as hindsight remembers it"),
    source_class(
        "tr_gold_physical", "Gold import statistics, BIST bullion flows and the refiners",
        layer="physical_economy",
        roots=("https://data.tuik.gov.tr/", "https://www.borsaistanbul.com/en/",
               "https://www.gold.org/goldhub/data"),
        queries=("altın ithalatı", "külçe altın ithalatı", "ithalat kotası", "rafineri",
                 "darphane", "ziynet altını", "yastık altı altın", "altın hesabı"),
        languages=("tr", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="TURKEY IS AMONG THE LARGEST PHYSICAL BULLION IMPORTERS IN THE WORLD and the "
              "monthly import value is published. An import QUOTA -- imposed when the current "
              "account needed protecting -- is a dated administrative shock, which is how TR-F "
              "separates a demand story from a policy one"),
    source_class(
        "tr_energy_physical", "BOTAŞ, EPİAŞ and the energy import bill", layer="physical_economy",
        roots=("https://www.botas.gov.tr/", "https://seffaflik.epias.com.tr/"),
        queries=("doğalgaz ithalatı", "BOTAŞ tarife", "elektrik tüketimi", "puant talep",
                 "gün öncesi piyasa", "ithalat faturası", "enerji ithalatı"),
        languages=("tr",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="EPİAŞ publishes hourly national electricity consumption and day-ahead prices FREE "
              "-- among the highest-frequency real-economy series in this department. Turkey is a "
              "large net energy importer, so the import bill is the current account's main swing "
              "and it moves with XBRUSD and the exchange rate together"),
    source_class(
        "tr_tourism_trade", "Tourism arrivals, receipts and the trade statistics",
        layer="physical_economy",
        roots=("https://data.tuik.gov.tr/", "https://www.ktb.gov.tr/"),
        queries=("turist sayısı", "turizm geliri", "Rus turist", "Alman turist",
                 "yabancı ziyaretçi", "dış ticaret açığı", "ihracat rakamları"),
        languages=("tr",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="tourism receipts are a large seasonal FX inflow that partially offsets the energy "
              "import bill; Russian and German arrivals dominate the swing, which is why TR-I "
              "reads the corridor through arrivals as well as through trade"),
    source_class(
        "tr_citation_graph", "DergiPark, OpenAlex and RePEc citation graphs", layer="source_graph",
        roots=("https://dergipark.org.tr/", "https://openalex.org/", "https://ideas.repec.org/"),
        queries=("atıf", "kaynakça", "kim atıf yapmış", "tekrarlanabilirlik",
                 "bayram etkisi literatür", "kur geçişkenliği atıf"),
        languages=("tr", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Turkish-language literature on the bayram effect is invisible in Western "
              "citation graphs; DergiPark's own graph is the only way to see whether a domestic "
              "calendar finding has been replicated or is one paper repeated"),
    source_class(
        "tr_code_graph", "GitHub clients for EVDS, BIST and the Turkish data APIs",
        layer="source_graph",
        roots=("https://github.com/search?q=evds+tcmb", "https://github.com/search?q=bist+data"),
        queries=("evds api", "tcmb evds python", "bist veri", "isyatirim scraper", "fork",
                 "bağımlılık"),
        languages=("tr", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="per-repository; check each, never vendor code",
        notes="that EVDS has many public clients and BIST depth has almost none is a direct "
              "measurement of which Turkish series practitioners can actually automate"),
    source_class(
        "tr_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en", "tr"), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="Turkey shares the Russia corridor with the RU, GE, AZ and KZ packs; the registry "
              "is what stops the same corridor being counted as five countries' coverage"),
)

#: All ten layers are populated. Turkey is the deepest native-language ground in this department
#: after Russia: its own domestic terminal ecosystem, an enormous social and forum layer, a
#: physical gold market with its own vocabulary, and a publicly CONTESTED inflation print -- the
#: single best example anywhere in this department of why contradicted material is kept.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CBRT policy rate decisions and PPK summaries", "source": "CBRT",
     "coverage": "2010 onward", "frequency": "8 per year (12 before 2024)",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("USDTRY", "EURTRY"),
     "fields": ("decision_date", "policy_rate_pct", "change_bp", "corridor", "statement_tr"),
     "pit_fields": ("release_ts_utc",),
     "mechanism_families": ("event_reaction", "policy_surprise"),
     "how_to_fetch": "tcmb.gov.tr announcements; 14:00 Istanbul = 11:00 UTC all year, no DST"},
    {"name": "CBRT Weekly Money and Banking Statistics", "source": "CBRT / EVDS",
     "coverage": "2005 onward", "frequency": "weekly", "publication_lag_days": 7.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("USDTRY", "EURTRY"),
     "fields": ("week_ending", "gross_reserves", "swaps_with_banks", "net_reserves",
                "net_ex_swap_derived", "fx_deposits"),
     "pit_fields": ("release_ts_utc", "week_ending", "derivation_version"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "EVDS series; the SWAP-EXCLUDED figure is DERIVED and analysts derive it "
                     "differently, so the derivation version must travel with every result"},
    {"name": "CBRT Weekly Securities Statistics (non-resident holdings)", "source": "CBRT",
     "coverage": "2005 onward", "frequency": "weekly", "publication_lag_days": 7.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("USDTRY", "UST10Y"),
     "fields": ("week_ending", "equities_usd", "gdds_usd", "weekly_change", "valuation_effect"),
     "pit_fields": ("release_ts_utc", "week_ending"),
     "mechanism_families": ("positioning", "institutional_flow"),
     "how_to_fetch": "EVDS; the dollar value mixes FLOW with VALUATION and the two must be "
                     "separated or a price move is read as a purchase"},
    {"name": "TÜİK consumer price index", "source": "TÜİK", "coverage": "1994 onward",
     "frequency": "monthly", "publication_lag_days": 3.0,
     "revisions": "headline not revised; the basket is re-weighted annually",
     "licence": "free, public", "history_from": "1994-01", "pit_feasible": True,
     "assets": ("USDTRY", "EURTRY", "XAUUSD"),
     "fields": ("reference_month", "cpi_mom", "cpi_yoy", "core_c", "ppi_mom", "food", "services"),
     "pit_fields": ("release_ts_utc", "vintage", "basket_version"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "data.tuik.gov.tr; the 3rd of the month at 07:00 UTC, a fixed CALENDAR DAY "
                     "that walks through the week, so a day-of-week control is mandatory"},
    {"name": "ENAG alternative consumer price index", "source": "Enflasyon Araştırma Grubu",
     "coverage": "2020 onward", "frequency": "monthly", "publication_lag_days": 3.0,
     "revisions": "not revised", "licence": "free, public", "history_from": "2020-09",
     "pit_feasible": True, "assets": ("USDTRY", "XAUUSD"),
     "fields": ("reference_month", "e_cpi_mom", "e_cpi_yoy", "gap_to_tuik"),
     "pit_fields": ("release_ts_utc",),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "enagrup.org. CONTRADICTED AND KEPT: the OFFICIAL series is what policy "
                     "reacts to and is the one an event study must use; the GAP between the two "
                     "is the dated expectations proxy and is the only thing this row is used for"},
    {"name": "KKM outstanding stock", "source": "BDDK and CBRT", "coverage": "2021 onward",
     "frequency": "weekly", "publication_lag_days": 7.0, "revisions": "revised",
     "licence": "free, public", "history_from": "2021-12", "pit_feasible": True,
     "assets": ("USDTRY", "EURTRY"),
     "fields": ("week_ending", "stock_try", "stock_usd", "weekly_change", "corporate_share"),
     "pit_fields": ("release_ts_utc", "week_ending", "publisher"),
     "mechanism_families": ("policy_shock", "institutional_flow"),
     "how_to_fetch": "BDDK weekly bulletins; THE PUBLISHER MOVED during the wind-down, so the "
                     "series has a join that must be handled rather than a break that is ignored"},
    {"name": "TÜİK foreign trade, including monthly gold imports", "source": "TÜİK",
     "coverage": "1996 onward", "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "revised", "licence": "free, public", "history_from": "1996-01",
     "pit_feasible": True, "assets": ("XAUUSD", "USDTRY", "XBRUSD"),
     "fields": ("reference_month", "exports", "imports", "gold_imports_usd", "energy_imports_usd",
                "trade_balance"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("terms_of_trade", "macro_condition"),
     "how_to_fetch": "data.tuik.gov.tr; the GOLD IMPORT line is TR-F's quantity and moves the "
                     "trade deficit visibly in stress months"},
    {"name": "Treasury domestic borrowing strategy and auction results",
     "source": "Ministry of Treasury and Finance", "coverage": "2005 onward",
     "frequency": "monthly strategy, per-auction results", "publication_lag_days": 0.0,
     "revisions": "final", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("USDTRY", "UST10Y"),
     "fields": ("auction_date", "instrument", "amount", "average_rate", "bid_to_cover",
                "redemption_schedule"),
     "pit_fields": ("result_ts_utc", "strategy_publish_ts_utc"),
     "mechanism_families": ("supply_shock", "institutional_flow"),
     "how_to_fetch": "hmb.gov.tr; the three-month strategy is published in advance so supply is "
                     "known before the auction"},
    {"name": "Medium Term Programme exchange-rate and inflation assumptions",
     "source": "Strategy and Budget Presidency", "coverage": "2006 onward", "frequency": "annual",
     "publication_lag_days": 0.0, "revisions": "superseded annually", "licence": "free, public",
     "history_from": "2006-09", "pit_feasible": True, "assets": ("USDTRY",),
     "fields": ("programme_year", "assumed_usdtry", "assumed_cpi", "assumed_growth"),
     "pit_fields": ("publish_ts_utc", "vintage"),
     "mechanism_families": ("macro_condition", "policy_shock"),
     "how_to_fetch": "sbb.gov.tr; published each September. The GAP between the assumption and "
                     "spot is a dated fiscal surprise of the same class as Australia's iron-ore "
                     "price deck, in an economy where the assumption is far more often wrong"},
    {"name": "Borsa İstanbul VİOP expiry calendar and settlement prices",
     "source": "Borsa İstanbul", "coverage": "2005 onward", "frequency": "bi-monthly expiries",
     "publication_lag_days": 0.0, "revisions": "rare", "licence": "free headline",
     "history_from": "2005-02", "pit_feasible": True, "assets": (),
     "fields": ("contract", "expiry_date", "settlement_price", "settlement_method"),
     "pit_fields": ("published_ts_utc",),
     "mechanism_families": ("derivatives_expiry",),
     "how_to_fetch": "borsaistanbul.com; the LAST BUSINESS DAY of the even months, settled to a "
                     "closing thirty-minute average. The index is not quoted here, so this feeds "
                     "a transmission hypothesis only"},
    {"name": "EPİAŞ hourly electricity consumption and day-ahead prices", "source": "EPİAŞ",
     "coverage": "2015 onward", "frequency": "hourly", "publication_lag_days": 0.0,
     "revisions": "final", "licence": "free, public", "history_from": "2015-01",
     "pit_feasible": True, "assets": ("USDTRY", "XNGUSD"),
     "fields": ("hour", "consumption_mwh", "day_ahead_price_try", "generation_mix"),
     "pit_fields": ("hour",), "mechanism_families": ("macro_condition",),
     "how_to_fetch": "seffaflik.epias.com.tr; HOURLY national consumption, free -- among the "
                     "highest-frequency real-economy series in this department and a genuine "
                     "nowcast for industrial activity"},
    {"name": "Tourism arrivals and receipts", "source": "TÜİK and the Ministry of Culture and "
                                                        "Tourism",
     "coverage": "2003 onward", "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2003-01",
     "pit_feasible": True, "assets": ("USDTRY", "USDRUB"),
     "fields": ("reference_month", "arrivals_total", "arrivals_russia", "arrivals_germany",
                "receipts_usd", "average_spend"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "ktb.gov.tr and TÜİK; the seasonal partially offsets the energy import bill"},
    {"name": "Desk MT5 TRY and gold tape", "source": "the desk's own Fusion tape",
     "coverage": "USDTRY 37,394 H1 bars from 2020-09-14 to 2026-09-16",
     "frequency": "tick to daily", "publication_lag_days": 0.0, "revisions": "append-only",
     "licence": "desk-owned", "history_from": "2020-09", "pit_feasible": True,
     "assets": ("USDTRY", "EURTRY", "GBPTRY", "XAUUSD"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time", "spread"), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet. MEASURED 2026-09-17: USDTRY "
                     "median H1 spread over the last 60 days 405 points (~8bp), ZERO frozen bars; "
                     "EURTRY 1,587 points (~28bp); GBPTRY 2,405 points (~37bp). The swap table is "
                     "-10,921 long against +1,481 short, an asymmetry of about 7.4 to one"},
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "CBRT Monetary Policy Committee (Para Politikası Kurulu)",
        "holds": "the one-week repo rate, an overnight corridor, a large swap book with domestic "
                 "and foreign counterparties, and a macroprudential toolkit that has at times "
                 "delivered the actual tightening",
        "forced_to": ("decide at eight scheduled meetings a year and publish at 14:00 Istanbul",
                      "publish a quarterly Inflation Report with a forecast path",
                      "publish weekly statistics from which its own reserve position can be "
                      "derived, whatever that position is"),
        "when": "14:00 Istanbul = 11:00 UTC ALL YEAR; Türkiye abolished seasonal clock changes in "
                "2016, so the event minute in UTC never moves",
        "information": ("bank-level FX and deposit flow through its own reporting",
                        "the securities and money statistics before publication"),
        "constraints": ("a 5% medium-term target against realised inflation many multiples of it",
                        "the KKM guarantee, which makes depreciation a direct fiscal cost",
                        "an external financing requirement that must be rolled continuously",
                        "the reserve position, which the market derives weekly whether or not the "
                        "Bank wishes it to"),
        "instruments": ("USDTRY", "EURTRY", "GBPTRY", "XAUUSD"),
        "counterparties": ("the domestic banking system", "the Treasury",
                           "foreign central banks through swap lines"),
        "observables": ("the decision and the PPK summary",
                        "the weekly swap-excluded net reserve figure",
                        "the Market Participants Survey",
                        "the Inflation Report forecast path"),
        "impact": "the largest single scheduled lira event; but the ANNOUNCED rate and the "
                  "EFFECTIVE funding cost have diverged repeatedly, so a surprise measured "
                  "against the announced rate alone can be exactly backwards",
        "persistence": "THE REACTION FUNCTION REVERSED COMPLETELY INSIDE THE SAMPLE: 19% to 8.5% "
                       "while inflation rose above 80%, then 8.5% to 50% inside a year. No pooled "
                       "estimate describes any of it, which is why TR-A is built on eras",
        "falsifier": "the same event-window statistic on the eight nearest non-meeting Thursdays. "
                     "A move that survives there is the weekly-statistics release, not the "
                     "decision -- and those two land on the same weekday",
        "notes": "the weekly statistics release at 11:30 UTC Thursday is the main confounder for "
                 "any Turkish event study and must be a second control, not an afterthought",
    },
    {
        "name": "The Treasury and the KKM guarantee",
        "holds": "a contingent liability that pays lira depositors the difference whenever the "
                 "lira falls by more than the deposit rate, with the stock published weekly",
        "forced_to": ("pay the exchange-rate difference when it is triggered -- a legal "
                      "obligation, not a discretionary support",
                      "finance that payment in lira, which is itself lira-negative",
                      "publish the outstanding stock and therefore its own exposure"),
        "when": "continuous exposure; the stock is published weekly and the payouts settle at "
                "each deposit's maturity",
        "information": ("the maturity ladder of the outstanding stock"),
        "constraints": ("the scheme's own rules, changed repeatedly by communiqué",
                        "the budget, which absorbs the cost",
                        "the wind-down policy from 2024, which is itself a dated policy sequence"),
        "instruments": ("USDTRY", "EURTRY"),
        "counterparties": ("domestic depositors, retail and corporate",
                           "the banks intermediating the scheme"),
        "observables": ("the weekly KKM stock in lira and in dollars",
                        "the corporate versus retail split",
                        "the wind-down trajectory"),
        "impact": "A FEEDBACK LOOP, and the pack's most distinctive mechanism: depreciation "
                  "triggers a fiscal payout, the payout is financed in lira, and the financing "
                  "is lira-negative. The stock measures how much of the deposit base is "
                  "effectively short the currency with the state behind it",
        "persistence": "introduced 20 December 2021 and wound down from 2024; the WIND-DOWN is as "
                       "informative as the introduction, because it says what the authorities "
                       "believe about the loop",
        "falsifier": "the lira-denominated and dollar-denominated stock series tell different "
                     "stories during a depreciation. If a claimed effect appears in the LIRA "
                     "series but not the DOLLAR one, it is the exchange rate revaluing the stock "
                     "and not a flow",
        "notes": "the publisher of the series MOVED during the wind-down, so the history has a "
                 "join that must be handled rather than a break that is ignored",
    },
    {
        "name": "Turkish households as gold and foreign-currency buyers",
        "holds": "deposits in lira, in foreign currency, and a very large stock of physical gold "
                 "held outside the banking system (yastık altı)",
        "forced_to": ("choose a store of value whenever real deposit rates go deeply negative -- "
                      "a decision the inflation rate forces rather than invites",
                      "buy physically when confidence in the official channel falls, which is "
                      "what the free-market premium measures"),
        "when": "continuous, concentrated after inflation prints and around policy surprises",
        "information": ("their own price experience, which the ENAG-TÜİK gap proxies"),
        "constraints": ("the real deposit rate",
                        "leverage caps on resident retail FX trading",
                        "gold import quotas when they are in force, which restrict supply"),
        "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
        "counterparties": ("the banks", "jewellers and bullion dealers", "the Grand Bazaar"),
        "observables": ("monthly gold import value",
                        "FX deposit share in the weekly statistics",
                        "the Kapalıçarşı free-market premium over the London-implied gram"),
        "impact": "the household bid is large enough to move the WORLD gold market in stress "
                  "months: Turkey is among the largest bullion importers and the demand is "
                  "expectation-driven rather than price-elastic",
        "persistence": "a multi-generational reflex reinforced by 1994, 2001 and 2018; the "
                       "MAGNITUDE scales with the real deposit rate, so it weakens when policy "
                       "turns genuinely orthodox",
        "falsifier": "GRAM ALTIN IS XAUUSD × USDTRY ÷ 31.1035. Any claim about Turkish gold "
                     "demand must first survive reconstructing the gram price from the two legs "
                     "and testing the RESIDUAL; an effect that does not survive it is arithmetic",
        "notes": "the same identity trap as XAUAUD in the Australian pack, in an economy where "
                 "the physical demand is genuinely large enough to matter globally",
    },
    {
        "name": "Turkish exporters under the FX conversion requirement",
        "holds": "export proceeds in foreign currency against a decreed obligation to sell a "
                 "share of them",
        "forced_to": ("sell a set share of export proceeds to the central bank through their "
                      "intermediary bank, at the prevailing rate",
                      "comply whatever the level of the exchange rate, because the share is set "
                      "by communiqué and not by negotiation"),
        "when": "on receipt of proceeds; the SHARE has been changed repeatedly by communiqué",
        "information": ("their own receivables schedule"),
        "constraints": ("the conversion communiqué in force at the time",
                        "European demand, which sets the proceeds",
                        "input costs that are largely imported and dollar-priced"),
        "instruments": ("USDTRY", "EURTRY", "GER40", "EUSTX50"),
        "counterparties": ("the central bank as ultimate buyer", "European importers"),
        "observables": ("monthly export values by destination",
                        "the conversion share in force, published by communiqué",
                        "the weekly statistics' FX position lines"),
        "impact": "a decreed lira bid whose SIZE steps when the communiqué steps -- structurally "
                  "identical to the Russian export-revenue surrender, and each amendment is a "
                  "break rather than a continuous variable",
        "persistence": "the requirement has existed in varying forms for years and its share has "
                       "moved by tens of percentage points; nothing about it is stable enough to "
                       "fit as a level",
        "falsifier": "the months before a given communiqué took effect. An effect present there "
                     "cannot be that communiqué's, and the amendment dates are the identification",
        "notes": "",
    },
    {
        "name": "Turkish banks under reserve requirements and securities maintenance",
        "holds": "a deposit base that has swung between lira, FX and KKM, and a securities "
                 "portfolio held to satisfy regulatory ratios rather than for return",
        "forced_to": ("hold government securities to satisfy maintenance ratios -- a forced bid "
                      "for domestic paper that has nothing to do with its yield",
                      "adjust FX positions to meet reserve requirements set in several currencies",
                      "intermediate the KKM scheme whether or not it is profitable"),
        "when": "reserve maintenance periods; rule changes arrive by communiqué with short notice",
        "information": ("their own deposit flow and FX position, daily"),
        "constraints": ("securities maintenance and reserve requirement rules, which have been "
                        "used as quantitative policy instruments",
                        "the KKM intermediation obligation",
                        "capital and liquidity ratios"),
        "instruments": ("USDTRY", "UST10Y"),
        "counterparties": ("the CBRT", "depositors", "the Treasury as issuer"),
        "observables": ("the weekly money and banking statistics",
                        "BDDK sector data",
                        "the deposit currency mix"),
        "impact": "THE FORCED SECURITIES BID IS WHY TURKISH BOND YIELDS AND POLICY RATES CAN "
                  "DISCONNECT: a regulatory holder is not a price-sensitive one, so the curve "
                  "stops carrying the information a curve normally carries",
        "persistence": "the framework was simplified from 2023; before that, tightening was "
                       "frequently delivered through these rules rather than through the rate, "
                       "which is the confounder TR-A must condition on",
        "falsifier": "compare the announced policy rate against the effective funding cost. Where "
                     "they diverge, a rate-surprise study is measuring the wrong instrument, and "
                     "that divergence is itself published",
        "notes": "",
    },
    {
        "name": "Bullion importers and the Borsa İstanbul Precious Metals Market",
        "holds": "the licensed channel through which physical gold enters the country",
        "forced_to": ("import through licensed members, because the channel is regulated",
                      "stop when an import quota is imposed, whatever the domestic demand"),
        "when": "continuous; quotas have been imposed when the current account needed protecting",
        "information": ("their own order books and the domestic premium"),
        "constraints": ("the import licence regime",
                        "quotas when in force",
                        "refining and logistics capacity"),
        "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
        "counterparties": ("international bullion banks", "domestic jewellers and dealers"),
        "observables": ("monthly gold import value in the trade statistics",
                        "BIST precious metals market volumes",
                        "the free-market premium, which WIDENS when the official channel is "
                        "restricted"),
        "impact": "an administrative supply constraint on a demand that does not fall when supply "
                  "does -- which is precisely why the free-market premium is the observable and "
                  "the import volume alone is not",
        "persistence": "the licence regime is structural; the quotas are episodic and dated",
        "falsifier": "a demand story and an administrative story predict OPPOSITE premium "
                     "behaviour: demand raises imports AND the premium together, a quota raises "
                     "the premium while imports FALL. The pair identifies which is operating",
        "notes": "this is the cleanest identification in the pack and it requires both series",
    },
    {
        "name": "Non-resident portfolio investors in Turkish assets",
        "holds": "equities and government paper, with holdings published weekly in dollars",
        "forced_to": ("report through the custody system, which is what makes the weekly series "
                      "exist",
                      "hedge or exit when the lira's carry no longer compensates the volatility"),
        "when": "continuous; the series is published every Thursday for the preceding Friday",
        "information": ("their own flow"),
        "constraints": ("mandate limits and index weights",
                        "the availability and cost of lira hedging, which has at times been "
                        "administratively restricted",
                        "convertibility in practice, which is not always the same as in law"),
        "instruments": ("USDTRY", "UST10Y", "EUSTX50"),
        "counterparties": ("domestic banks", "the Treasury at auction"),
        "observables": ("the weekly securities statistics in dollars",
                        "BIST foreign ownership ratio, daily",
                        "the weekly change decomposed into flow and valuation"),
        "impact": "the non-resident share fell from a large fraction of the government bond market "
                  "to a small one over the sample; the DEPARTURE was the flow, and what remains "
                  "is a much less price-sensitive holder base",
        "persistence": "a decade-long structural decline punctuated by brief re-entries after "
                       "each normalisation announcement",
        "falsifier": "the dollar value moves with PRICE as well as flow. A claimed inflow that "
                     "disappears once valuation is removed was a rally, not a purchase",
        "notes": "the closest thing Turkey has to a positioning series, and it is weekly and "
                 "seven days stale",
    },
    {
        "name": "Retail traders on BIST and in leveraged FX",
        "holds": "a large and growing share of BIST turnover, plus leveraged FX positions under "
                 "resident leverage caps",
        "forced_to": ("meet margin calls (teminat tamamlama) when a position moves against them",
                      "trade inside circuit breakers and, at times, short-selling bans"),
        "when": "continuous; concentrated around inflation prints and policy decisions",
        "information": ("nothing the market lacks; this participant is forced, not informed"),
        "constraints": ("resident FX leverage caps set by the regulator",
                        "circuit breakers and short-selling restrictions on BIST",
                        "broker maintenance margin, which binds in a fast move"),
        "instruments": ("USDTRY", "XAUUSD", "XAGUSD"),
        "counterparties": ("brokers and the dealers they hedge into"),
        "observables": ("TSPB investor and account counts",
                        "BIST turnover and the retail share",
                        "forum and social discussion of margin stress"),
        "impact": "BIST is unusually retail-dominated for a market of its size, so index moves "
                  "carry more forced-liquidation content and less institutional rebalancing than "
                  "a European index of similar capitalisation",
        "persistence": "the retail share grew sharply during the high-inflation years as equities "
                       "became an inflation hedge, and has not reverted",
        "falsifier": "the same asymmetry on a comparable EM index with a lower retail share. A "
                     "shared asymmetry is EM beta and not Turkish retail structure",
        "notes": "the index is not quoted here, so this actor reaches the desk through USDTRY and "
                 "gold rather than through equities",
    },
    {
        "name": "TÜİK as the publisher of the official price index",
        "holds": "a monopoly on the official CPI and a published release calendar",
        "forced_to": ("publish on the 3rd of each month at 10:00 Istanbul",
                      "re-weight the basket annually, which breaks long series"),
        "when": "the 3rd of the month, a fixed CALENDAR DAY that walks through the week",
        "information": ("the number before publication"),
        "constraints": ("the statistics law and the calendar",
                        "a methodology that is publicly disputed, which constrains nothing "
                        "legally and everything reputationally"),
        "instruments": ("USDTRY", "EURTRY", "XAUUSD"),
        "counterparties": ("the whole market at once", "the CBRT, which targets this series"),
        "observables": ("the release at 07:00 UTC",
                        "the gap to ENAG's alternative, published the same day"),
        "impact": "the single largest scheduled Turkish macro event after the rate decision. "
                  "POLICY REACTS TO THIS SERIES, so an event study must use it -- whatever a "
                  "session's private view of its accuracy",
        "persistence": "permanent as a class; the market's TRUST in it is the variable, and the "
                       "ENAG gap is the only dated measure of that trust",
        "falsifier": "the same 07:00 UTC window on days with no scheduled release. A systematic "
                     "move there is the hour, not the data",
        "notes": "",
    },
    {
        "name": "ENAG, the Inflation Research Group",
        "holds": "an independently computed alternative consumer price index, published monthly "
                 "on the same day as the official one and far above it",
        "forced_to": ("publish on its own announced schedule",
                      "defend a methodology that is contested in public"),
        "when": "the same day as the TÜİK release",
        "information": ("its own price collection"),
        "constraints": ("a smaller sample and a different basket than the official index",
                        "no statutory standing"),
        "instruments": ("USDTRY", "XAUUSD"),
        "counterparties": ("households and commentators who use it as a reference"),
        "observables": ("the ENAG print and the GAP to TÜİK"),
        "impact": "THE GAP IS THE OBJECT, NOT THE LEVEL. It is a dated, monthly, public proxy for "
                  "how far household inflation expectation has detached from the official number "
                  "-- and expectation is what drives the gold and FX substitution in TR-F",
        "persistence": "published since 2020; the gap has been persistently large and its "
                       "variation, not its level, is what this pack uses",
        "falsifier": "if the gap predicts nothing that the official series does not already "
                     "predict, this actor adds nothing and the row stands as a NOT_PREDICTIVE "
                     "finding rather than being deleted",
        "notes": "REGISTERED CONTRADICTED AND KEPT AT LOW WEIGHT. A contested measurement is "
                 "itself a measurement, and dropping it would destroy the only record that the "
                 "contest exists",
    },
    {
        "name": "Energy importers and BOTAŞ",
        "holds": "the import contracts for a country that buys most of its gas and oil abroad, "
                 "and a state seller that has sold below cost domestically",
        "forced_to": ("import whatever volume demand requires, priced in dollars",
                      "sell domestically at a regulated tariff, absorbing the difference"),
        "when": "continuous; the seasonal peak is winter and the tariff is set administratively",
        "information": ("their own contracted volumes and hedges"),
        "constraints": ("contracted take-or-pay volumes",
                        "the domestic tariff, which is a political variable",
                        "the exchange rate, which multiplies the dollar cost"),
        "instruments": ("XNGUSD", "XBRUSD", "XTIUSD", "USDTRY"),
        "counterparties": ("Russian, Azerbaijani, Iranian and LNG suppliers",
                           "domestic households and industry"),
        "observables": ("monthly energy import value in the trade statistics",
                        "EPİAŞ hourly consumption and day-ahead prices",
                        "tariff decisions"),
        "impact": "THE ENERGY IMPORT BILL IS THE CURRENT ACCOUNT'S MAIN SWING and it moves with "
                  "the oil price AND the exchange rate together, which is a multiplicative "
                  "exposure rather than an additive one",
        "persistence": "structural; Turkey's import dependence has not materially changed",
        "falsifier": "the import bill in DOLLARS against the bill in LIRA. If only the lira series "
                     "moves, the shock was the currency and not the commodity, and attributing it "
                     "to energy is backwards",
        "notes": "",
    },
    {
        "name": "Russian visitors, traders and the corridor",
        "holds": "the largest single source of tourist arrivals in many years, plus a trade and "
                 "payment corridor that widened sharply after 2022",
        "forced_to": ("route through Turkey when direct channels close",
                      "convert currency on arrival, which is a physical FX inflow"),
        "when": "the summer tourism peak; continuous trade and payment flow that steps with "
                "enforcement",
        "information": ("their own flows"),
        "constraints": ("secondary sanctions risk on Turkish banks, which has tightened",
                        "correspondent banking access",
                        "visa and flight capacity"),
        "instruments": ("USDTRY", "USDRUB", "XNGUSD"),
        "counterparties": ("Turkish banks, hotels and traders"),
        "observables": ("monthly arrivals by origin",
                        "tourism receipts",
                        "Turkey-Russia trade statistics, which step with enforcement"),
        "impact": "a seasonal FX inflow plus a friction-trade channel; the correlation between "
                  "USDTRY and USDRUB appears and disappears with enforcement rounds rather than "
                  "with any macro fundamental",
        "persistence": "the corridor has survived several enforcement rounds and narrowed at each",
        "falsifier": "the Georgian and Kazakh corridors at the same enforcement dates. A step in "
                     "all three is enforcement; a step in one is a local story",
        "notes": "the same mechanism as GE-F and KZ-I; measuring all three together is the "
                 "strongest available evidence that enforcement is the driver",
    },
    {
        "name": "Jewellers and the Grand Bazaar (Kapalıçarşı) dealers",
        "holds": "the physical retail gold market and the free-market quote that goes with it",
        "forced_to": ("quote a two-way price all day, in a market where the official channel can "
                      "be restricted without notice",
                      "widen when supply tightens, because they cannot manufacture metal"),
        "when": "bazaar hours, roughly 09:00-19:00 Istanbul",
        "information": ("physical availability before any statistic records it"),
        "constraints": ("physical supply through the licensed import channel",
                        "their own inventory",
                        "household demand, which is expectation-driven"),
        "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
        "counterparties": ("households", "licensed importers", "refiners"),
        "observables": ("the free-market gram quote",
                        "its PREMIUM over the London-implied gram",
                        "dealer spreads (makas)"),
        "impact": "THE PREMIUM IS A PURE STRESS OBSERVABLE with no FX analogue: it widens when "
                  "households want metal faster than the licensed channel can supply it, which is "
                  "exactly the state no official series captures",
        "persistence": "the market is centuries old and the premium behaviour has been stable "
                       "across every modern stress episode",
        "falsifier": "the premium should be near zero when imports are unrestricted and demand is "
                     "normal. A persistent premium in calm conditions means the quote is measuring "
                     "a dealer margin rather than scarcity",
        "notes": "quoted publicly by dealers and aggregated by the financial press; not on this "
                 "broker, so it is a transmission target with a named proxy",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "TR-A", "title": "Policy decisions across a reversed reaction function",
        "objects": ("the eight scheduled decisions at 11:00 UTC",
                    "the PPK summary some days later",
                    "the quarterly Inflation Report forecast path",
                    "the EFFECTIVE funding cost, which has diverged from the announced rate"),
        "conditions": ("THE ERA, always -- the policy rate went 19% to 8.5% while inflation rose "
                       "above 80%, then 8.5% to 50% in a year, and no pooled estimate describes "
                       "any of it",
                       "the announced rate AND the effective funding cost, because tightening was "
                       "at times delivered macroprudentially instead",
                       "a survey-based surprise, labelled as such; there is no traded curve here",
                       "the Thursday weekly-statistics release as a second control"),
        "instruments": ("USDTRY", "EURTRY", "GBPTRY", "XAUUSD"),
        "controls": ("the eight nearest non-meeting Thursdays -- which is where the weekly "
                     "statistics land, so this control does double duty",
                     "the same window on USDZAR or another high-carry EM, to separate a lira "
                     "event from an EM risk event",
                     "each era tested separately and the results compared rather than pooled",
                     "the effective-funding-cost series as an alternative treatment variable"),
        "notes": "the confounder here is unusually severe: the decision and the weekly statistics "
                 "share a weekday, and the announced rate is not always the binding one",
    },
    {
        "id": "TR-B", "title": "Reserves: the number the market trades is derived, not published",
        "objects": ("weekly gross reserves",
                    "the swap book with domestic and foreign counterparties",
                    "the DERIVED swap-excluded net reserve figure",
                    "the derivation itself, which analysts disagree about"),
        "conditions": ("the SWAP-EXCLUDED figure, not the headline gross one -- the two have "
                       "diverged by tens of billions of dollars",
                       "the derivation version carried with every result, because different "
                       "analysts derive it differently and two studies can disagree without "
                       "either being wrong",
                       "the seven-day publication lag, which is structural",
                       "the era, because the swap book's size is a policy choice"),
        "instruments": ("USDTRY", "EURTRY"),
        "controls": ("the gross series run deliberately as the WRONG answer, to publish the size "
                     "of the error a headline-reserve study would make",
                     "the same window on non-release Thursdays",
                     "another EM's reserve release at the same UTC minute",
                     "the IMF's reserve adequacy metric as an independent framing"),
        "notes": "the most Turkish thing about this domain is that the market's working "
                 "definition of the key number is settled on social media every Thursday "
                 "afternoon rather than by the publisher",
    },
    {
        "id": "TR-C", "title": "KKM: a contingent liability that grows with depreciation",
        "objects": ("the weekly outstanding stock in lira and in dollars",
                    "the corporate versus retail split",
                    "the trigger mechanism and its payout",
                    "the wind-down sequence from 2024"),
        "conditions": ("the DOLLAR series as the exposure measure; the lira series revalues with "
                       "the exchange rate and tells a different story during a depreciation",
                       "the publisher JOIN during the wind-down, handled rather than ignored",
                       "the feedback loop modelled explicitly: depreciation triggers a payout, "
                       "the payout is financed in lira, the financing is lira-negative"),
        "instruments": ("USDTRY", "EURTRY"),
        "controls": ("the lira-denominated stock as the deliberate wrong measure",
                     "the period before 20 December 2021, when the scheme did not exist",
                     "ordinary FX deposits over the same weeks, which carry no guarantee",
                     "the wind-down months, where the mechanism should WEAKEN if it is real"),
        "notes": "nowhere else in this department is a government's exposure to its own currency "
                 "both explicit and published weekly",
    },
    {
        "id": "TR-D", "title": "Two inflation prints and the gap between them",
        "objects": ("the TÜİK CPI on the 3rd at 07:00 UTC",
                    "the ENAG alternative published the same day",
                    "the GAP between them",
                    "the CBRT Market Participants Survey expectation"),
        "conditions": ("the OFFICIAL series for the event study, because policy reacts to it -- "
                       "whatever a session's private view of its accuracy",
                       "the GAP as a separate, dated expectations variable",
                       "the fixed calendar day, which walks through the week, so a day-of-week "
                       "control is mandatory",
                       "the annual basket re-weighting, which breaks long series"),
        "instruments": ("USDTRY", "EURTRY", "XAUUSD", "XAGUSD"),
        "controls": ("the same 07:00 UTC window on days with no scheduled release",
                     "day-of-week matched non-release days, since the 3rd walks",
                     "the survey expectation as an alternative surprise definition",
                     "the ENAG series alone, which should be WEAKER than the official one for "
                     "predicting policy and possibly STRONGER for predicting gold demand -- a "
                     "genuine, testable split"),
        "notes": "the pack's clearest example of why CONTRADICTED material is kept: the disputed "
                 "series is useless for one question and possibly the better series for another",
    },
    {
        "id": "TR-E", "title": "The carry, and a swap table that taxes one side seven times",
        "objects": ("the USDTRY swap rates: -10,921 long against +1,481 short per lot per night",
                    "the Wednesday triple charge",
                    "the policy rate differential",
                    "EURTRY and GBPTRY at 28bp and 37bp median spread"),
        "conditions": ("DIRECTION-DEPENDENT COST IN EVERY CELL -- a symmetric assumption flatters "
                       "the depreciation trade by roughly 7.4 to one",
                       "the Wednesday triple charge removed before any day-of-week statistic",
                       "the horizon, because a carry cost compounds and a spread does not",
                       "the cross chosen deliberately: EURTRY and GBPTRY cost three to four times "
                       "USDTRY and must clear proportionally more"),
        "instruments": ("USDTRY", "EURTRY", "GBPTRY", "USDRUB"),
        "controls": ("the same strategy costed symmetrically, published alongside, to show the "
                     "size of the error",
                     "the same mechanism on USDRUB, where the swap asymmetry is about 6.8 to one "
                     "-- a matched high-carry sanctioned comparison",
                     "gross-of-cost and net-of-cost Sharpe reported side by side, always",
                     "a zero-differential period, where the carry mechanism should vanish"),
        "notes": "this domain gates the others the way RU-M gates the Russian pack: not a caveat "
                 "section but a cost floor every Turkish cell must clear explicitly",
    },
    {
        "id": "TR-F", "title": "Gold: a world-scale physical demand behind an arithmetic identity",
        "objects": ("monthly gold import value",
                    "the gram altın price",
                    "the licensed import channel and its quotas",
                    "household FX and gold deposit substitution"),
        "conditions": ("THE IDENTITY DECOMPOSITION FIRST, ALWAYS: gram altın is XAUUSD × USDTRY ÷ "
                       "31.1035, so reconstruct it and test the RESIDUAL, never the level",
                       "import QUOTAS separated from demand, because they predict opposite "
                       "premium behaviour",
                       "the real deposit rate, which scales the substitution",
                       "the ENAG gap as the expectations conditioner"),
        "instruments": ("XAUUSD", "XAGUSD", "XAUEUR", "USDTRY"),
        "controls": ("the reconstructed gram price as the primary control -- an effect that does "
                     "not survive it is arithmetic, not a discovery",
                     "XAUEUR, where no comparable household demand exists",
                     "XAGUSD, where Turkish import share is far smaller",
                     "the quota months against the free-import months"),
        "notes": "the same trap as XAUAUD in the Australian pack, but here the physical demand is "
                 "genuinely large enough to move the world price, so the residual is worth hunting",
    },
    {
        "id": "TR-G", "title": "The Kapalıçarşı premium as a household-stress observable",
        "objects": ("the free-market gram quote",
                    "its premium over the London-implied gram",
                    "dealer spreads (makas)",
                    "import restrictions when in force"),
        "conditions": ("the PREMIUM, not the level, which is just the identity again",
                       "import restrictions separated from demand surges -- a quota raises the "
                       "premium while imports FALL, and demand raises both together",
                       "the quote is a transmission target: it is not on this broker and the "
                       "cells terminate in XAUUSD and USDTRY"),
        "instruments": ("XAUUSD", "USDTRY", "XAGUSD"),
        "controls": ("calm periods, where the premium should be near zero if it measures scarcity "
                     "rather than dealer margin",
                     "the import volume series, which identifies quota from demand",
                     "the official channel's own pricing over the same days"),
        "notes": "a stress observable with no FX analogue anywhere else in this department; the "
                 "identification in the controls is what makes it more than a curiosity",
    },
    {
        "id": "TR-H", "title": "BIST and VİOP mechanics as a transmission target",
        "objects": ("the 18:00-18:10 closing auction",
                    "VİOP BIST 30 expiry on the last business day of the even months",
                    "the CLOSING thirty-minute average settlement",
                    "circuit breakers and the history of short-selling bans"),
        "conditions": ("the index is NOT quoted here: this is a transmission-target domain",
                       "the settlement is a CLOSING average, the opposite of the Australian SPI's "
                       "opening quotation, so the risk sits in the last half hour",
                       "the retail dominance of BIST, which makes index moves carry more "
                       "forced-liquidation content than an equivalent European index"),
        "instruments": ("USDTRY", "EUSTX50", "GER40"),
        "controls": ("non-expiry months in the same cycle",
                     "EUSTX50 on the same dates, as the European control",
                     "the Australian SPI's opening settlement as the structural contrast",
                     "days with a circuit breaker against days without"),
        "notes": "included and declared rather than omitted, so a later session with a BIST quote "
                 "inherits the mechanics instead of rediscovering them",
    },
    {
        "id": "TR-I", "title": "The Russia corridor: tourism, trade, gas and payments",
        "objects": ("monthly arrivals by origin and tourism receipts",
                    "Turkey-Russia trade statistics and their step changes",
                    "gas import volumes and the payment arrangements",
                    "enforcement announcements and their dates"),
        "conditions": ("enforcement rounds as STEPS, not a continuous variable",
                       "tourism and trade as separate channels with different seasonals",
                       "the USDTRY-USDRUB correlation conditioned on enforcement, since it "
                       "appears and disappears with it rather than with any fundamental"),
        "instruments": ("USDTRY", "USDRUB", "XNGUSD"),
        "controls": ("the Georgian and Kazakh corridors at the same enforcement dates -- a step "
                     "in all three is enforcement and not geography",
                     "German arrivals over the same months, as the non-Russian tourism control",
                     "the pre-2022 sample",
                     "EM currencies with no such corridor"),
        "notes": "the same mechanism as GE-F and KZ-I; the three packs are written to be measured "
                 "together because that is the only way to identify enforcement as the driver",
    },
    {
        "id": "TR-J", "title": "The fiscal calendar and the official exchange-rate assumption",
        "objects": ("the Medium Term Programme's assumed exchange rate and inflation",
                    "the Treasury's three-month domestic borrowing strategy",
                    "auction results and the redemption schedule",
                    "the gap between the assumption and spot"),
        "conditions": ("the assumption-to-spot gap as a dated fiscal surprise",
                       "the strategy published in advance, so supply is known before the auction",
                       "the forced regulatory bid for domestic paper, which means auction "
                       "coverage is not a clean demand signal"),
        "instruments": ("USDTRY", "UST10Y"),
        "controls": ("weeks with no auction",
                     "the same statistic on another EM sovereign's auction days",
                     "the securities-maintenance rules in force, which determine how much of the "
                     "bid is regulatory rather than voluntary",
                     "the Australian and Azerbaijani published price assumptions as the "
                     "structural analogues"),
        "notes": "a published official exchange-rate assumption is the same object as Western "
                 "Australia's iron-ore price deck and Azerbaijan's budget oil price, in an "
                 "economy where it has been wrong by very large margins",
    },
    {
        "id": "TR-K", "title": "Bayram closures, half-day arifes and a clock that never moves",
        "objects": ("Ramazan Bayramı, three days, and Kurban Bayramı, four",
                    "the ARIFE half-days closing at 13:00 Istanbul",
                    "28 October, also a half day",
                    "the eleven-day annual drift of both Bayrams"),
        "conditions": ("HALF DAYS TREATED AS HALF DAYS -- a three-and-a-half-hour session averaged "
                       "into a sample of seven-hour ones will manufacture a calendar result",
                       "the Bayrams read from the proclaimed table, never computed",
                       "the eleven-day drift, so a fixed-calendar seasonal drifts off them in "
                       "three years",
                       "the fixed UTC+3 clock, which at least never moves"),
        "instruments": ("USDTRY", "EURTRY", "XAUUSD"),
        "controls": ("ordinary sessions matched on day of week",
                     "the Azerbaijani and Kazakh calendars, which share Kurban -- on 2026-05-27 "
                     "three markets in this department close together",
                     "the pre- and post-Bayram sessions separately, since a reopening after four "
                     "days is not the same as an ordinary open",
                     "a placebo Bayram shifted one week"),
        "notes": "the arife half-day is the detail a holiday table imported from another country "
                 "will always get wrong, and it is large enough to matter",
    },
    {
        "id": "TR-L", "title": "Non-resident flows as the only positioning series",
        "objects": ("weekly non-resident holdings of equities and government paper, in dollars",
                    "the BIST foreign ownership ratio, daily",
                    "the decomposition into flow and valuation",
                    "the multi-year structural departure"),
        "conditions": ("FLOW SEPARATED FROM VALUATION -- the dollar value moves with price, so a "
                       "rally raises the holding with no purchase at all",
                       "the seven-day publication lag",
                       "the era, because the holder base that remains is far less price-sensitive "
                       "than the one that left"),
        "instruments": ("USDTRY", "UST10Y", "EUSTX50"),
        "controls": ("the valuation-only reconstruction as the null",
                     "the daily ownership ratio against the weekly dollar series",
                     "another EM's non-resident series over the same period",
                     "the periods after each normalisation announcement, where re-entry should "
                     "appear if the announcements are credible"),
        "notes": "there is no COT for the lira; this is what the desk has instead, and it is "
                 "weekly, stale and contaminated by valuation -- which is stated rather than "
                 "worked around",
    },
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "tr_policy_era_event_study", "domain_ids": ("TR-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.tr.miners:policy_era_event_study",
     "needs": ("CBRT decision dates", "the effective funding cost series",
               "USDTRY and EURTRY M15 bars"),
     "notes": "tests each era separately and REFUSES a pooled estimate; the Thursday weekly-"
              "statistics release is a mandatory second control because it shares the weekday"},
    {"name": "tr_reserve_derivation", "domain_ids": ("TR-B",), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:reserve_derivation",
     "needs": ("CBRT weekly money and banking statistics", "USDTRY M15 bars"),
     "notes": "carries the derivation version with every result and publishes the gross-reserve "
              "version deliberately as the wrong answer"},
    {"name": "tr_kkm_feedback_loop", "domain_ids": ("TR-C",), "kind": "flow",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:kkm_feedback_loop",
     "needs": ("weekly KKM stock in TRY and USD", "USDTRY D1 bars"),
     "notes": "uses the DOLLAR series as the exposure measure and handles the publisher join; the "
              "lira series is the control, not the treatment"},
    {"name": "tr_two_inflation_prints", "domain_ids": ("TR-D",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:two_inflation_prints",
     "needs": ("TÜİK CPI", "ENAG alternative index", "USDTRY and XAUUSD M15 bars"),
     "notes": "the OFFICIAL series drives the policy event study and the GAP drives the gold "
              "substitution test; reports the day-of-week control first because the 3rd walks"},
    {"name": "tr_carry_cost_floor", "domain_ids": ("TR-E",), "kind": "microstructure",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.tr.miners:carry_cost_floor",
     "needs": ("USDTRY, EURTRY, GBPTRY H1 bars with spread", "the broker swap table"),
     "notes": "publishes the direction-dependent cost floor every other Turkish miner must clear; "
              "runs FIRST and gates the rest, exactly as RU-M does in the Russia pack"},
    {"name": "tr_gram_altin_residual", "domain_ids": ("TR-F",), "kind": "basis",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:gram_altin_residual",
     "needs": ("XAUUSD and USDTRY H1 bars", "monthly gold import values"),
     "notes": "reconstructs the gram price from the two legs and tests the RESIDUAL against the "
              "quoted spread; a residual inside the spread is UNMEASURED, never a finding"},
    {"name": "tr_bazaar_premium", "domain_ids": ("TR-G",), "kind": "basis",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:bazaar_premium",
     "needs": ("free-market gram quotes if obtainable", "XAUUSD and USDTRY bars",
               "gold import volumes"),
     "notes": "identifies quota from demand using the premium-and-volume PAIR; reports UNMEASURED "
              "when no free-market quote can be sourced rather than substituting the official one"},
    {"name": "tr_corridor_enforcement", "domain_ids": ("TR-I",), "kind": "policy",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:corridor_enforcement",
     "needs": ("enforcement dates", "Turkey-Russia trade and arrivals", "USDTRY and USDRUB bars"),
     "notes": "measures the Turkish, Georgian and Kazakh corridors TOGETHER; a step in all three "
              "at the same dates is the strongest available identification of enforcement"},
    {"name": "tr_bayram_calendar", "domain_ids": ("TR-K",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.tr.miners:bayram_calendar",
     "needs": ("the Turkish holiday and half-day tables", "USDTRY H1 bars"),
     "notes": "treats arifes as HALF SESSIONS and flags any window that averages one into a "
              "sample of full days; 2026-05-27 is the three-country shared closure"},
    {"name": "tr_nonresident_flow", "domain_ids": ("TR-L",), "kind": "flow",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.tr.miners:nonresident_flow",
     "needs": ("CBRT weekly securities statistics", "BIST foreign ownership ratio",
               "USDTRY D1 bars"),
     "notes": "separates flow from valuation before any claim; the valuation-only reconstruction "
              "is the null this miner must beat"},
)

# --------------------------------------------------------------------------- transmission edges
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "CBRT policy surprise against the Market Participants Survey", "target": "USDTRY",
     "sign": "-",
     "mechanism": "a hawkish surprise raises the expected lira carry and the credibility premium "
                  "attached to the normalisation",
     "horizon": "0 to 60 minutes",
     "condition": "the ERA, always; and the effective funding cost, because tightening has at "
                  "times been delivered macroprudentially rather than through the rate",
     "control": "the eight nearest non-meeting Thursdays, which is also where the weekly "
                "statistics land",
     "falsifier": "an equal move on non-meeting Thursdays, which would attribute the effect to "
                  "the weekly statistics rather than the decision"},
    {"source": "CBRT policy surprise", "target": "EURTRY", "sign": "-",
     "mechanism": "the same repricing in the cross that carries most of Turkey's trade; EURTRY is "
                  "the economically relevant rate for exporters even though USDTRY is the traded "
                  "one",
     "horizon": "0 to 2 sessions",
     "condition": "EURTRY costs about 28bp against USDTRY's 8bp, so the effect must be three "
                  "times larger to be tradeable here",
     "control": "EURUSD over the same window, to remove the euro leg",
     "falsifier": "an EURTRY move fully explained by EURUSD, which would make it a euro event"},
    {"source": "Swap-excluded net reserves (derived, weekly)", "target": "USDTRY", "sign": "-",
     "mechanism": "the market's working measure of how much genuine defensive capacity exists; a "
                  "fall is read as reduced ability to smooth",
     "horizon": "0 to 5 sessions",
     "condition": "the DERIVED figure, with the derivation version stated; the headline gross "
                  "series is a different variable",
     "control": "the gross series run deliberately as the wrong answer",
     "falsifier": "the gross series performing as well as the derived one, which would falsify "
                  "the whole premise of TR-B"},
    {"source": "TÜİK CPI surprise (07:00 UTC, the 3rd)", "target": "USDTRY", "sign": "-",
     "mechanism": "the official print is what policy reacts to, so a hot print raises the "
                  "expected policy response and, in the normalisation era, supports the lira",
     "horizon": "0 to 2 sessions",
     "condition": "the SIGN IS ERA-DEPENDENT: in the unorthodox era a hot print did not raise the "
                  "expected policy rate and the relationship inverts",
     "control": "the same UTC window on non-release days, matched on day of week",
     "falsifier": "a stable sign across both eras, which would falsify the era story"},
    {"source": "The ENAG-minus-TÜİK inflation gap", "target": "XAUUSD", "sign": "+",
     "mechanism": "the gap proxies how far household expectations have detached from the official "
                  "number, and detached expectations drive physical gold substitution in an "
                  "economy that is among the world's largest bullion importers",
     "horizon": "20 to 90 sessions",
     "condition": "the GAP, never the ENAG level; and conditioned on the real deposit rate",
     "control": "the official series alone, which is the null this edge must beat",
     "falsifier": "the gap adding nothing beyond the official series, which would leave ENAG as a "
                  "NOT_PREDICTIVE row rather than a deleted one"},
    {"source": "KKM outstanding stock in dollars", "target": "USDTRY", "sign": "+",
     "mechanism": "a large guaranteed stock means depreciation triggers a fiscal payout financed "
                  "in lira -- a feedback loop in which the defence of the currency is itself "
                  "currency-negative",
     "horizon": "20 to 120 sessions",
     "condition": "the DOLLAR series; the lira series revalues with the rate and is circular",
     "control": "ordinary FX deposits over the same weeks, which carry no guarantee",
     "falsifier": "an effect present in the lira series but not the dollar one, which would make "
                  "it revaluation rather than exposure"},
    {"source": "Turkish monthly gold imports", "target": "XAUUSD", "sign": "+",
     "mechanism": "Turkey is among the largest physical bullion importers and the demand is "
                  "expectation-driven rather than price-elastic, so it is a genuine world-market "
                  "bid rather than a local one",
     "horizon": "5 to 40 sessions",
     "condition": "import QUOTAS separated from demand: a quota raises the free-market premium "
                  "while imports FALL, and demand raises both together",
     "control": "Indian imports over the same months, the other large physical buyer",
     "falsifier": "an import surge with no premium move, which would mean the channel was "
                  "supply-driven rather than demand-driven"},
    {"source": "XAUUSD and USDTRY jointly", "target": "XAUEUR", "sign": "identity",
     "mechanism": "GRAM ALTIN IS XAUUSD × USDTRY ÷ 31.1035 to rounding, and XAUEUR is the same "
                  "arithmetic in another currency. This edge exists to be the NEGATIVE CONTROL "
                  "for every claim of Turkish gold demand",
     "horizon": "instantaneous",
     "condition": "always; the identity holds continuously",
     "control": "the reconstruction residual against the quoted spread",
     "falsifier": "a residual indistinguishable from spread and rounding, which means no Turkish "
                  "gold mechanism has been measured at all"},
    {"source": "XBRUSD", "target": "USDTRY", "sign": "+",
     "mechanism": "Turkey is a large net energy importer, so a higher crude price widens the "
                  "current account deficit; the exposure is MULTIPLICATIVE because the bill is "
                  "dollar-priced and the payer earns lira",
     "horizon": "20 to 90 sessions",
     "condition": "conditioned on USDX so a dollar move is not double-counted",
     "control": "the import bill in dollars against the bill in lira -- if only the lira series "
                "moves, the shock was the currency",
     "falsifier": "an oil beta no larger than in a net energy exporter's currency"},
    {"source": "Turkish tourism receipts", "target": "USDTRY", "sign": "-",
     "mechanism": "a large seasonal FX inflow that partially offsets the energy import bill; "
                  "Russian and German arrivals dominate the swing",
     "horizon": "the summer season",
     "condition": "arrivals by ORIGIN, since the Russian and German seasonals differ and the "
                  "Russian channel steps with enforcement",
     "control": "the energy import bill over the same months, the offsetting leg",
     "falsifier": "a tourism effect that does not weaken in a year of high energy prices, which "
                  "would falsify the offset story"},
    {"source": "USDRUB", "target": "USDTRY", "sign": "+",
     "mechanism": "Turkey is a principal corridor for Russian trade, tourism and payments; the "
                  "two currencies are linked by a FRICTION channel rather than any macro "
                  "fundamental, which is why the correlation steps with enforcement",
     "horizon": "5 to 60 sessions",
     "condition": "conditioned on enforcement events; outside them the link is weak",
     "control": "the Georgian and Kazakh corridors at the same dates",
     "falsifier": "a stable correlation independent of enforcement, making it generic EM beta"},
    {"source": "Non-resident holdings of Turkish securities (weekly, flow net of valuation)",
     "target": "USDTRY", "sign": "-",
     "mechanism": "the only positioning series the lira has; a genuine inflow is a dated foreign "
                  "bid and a departure is a dated sale",
     "horizon": "5 to 40 sessions",
     "condition": "FLOW separated from VALUATION -- a rally raises the dollar holding with no "
                  "purchase at all",
     "control": "the valuation-only reconstruction as the null",
     "falsifier": "the valuation-only series predicting as well as the flow series, which would "
                  "mean the whole thing is a price echo"},
    {"source": "VİOP BIST 30 expiry (last business day of the even months)", "target": "USDTRY",
     "sign": "two_sided",
     "mechanism": "a closing thirty-minute average settlement concentrates hedge unwinds into the "
                  "last half hour of a retail-dominated market, which spills into the lira's "
                  "European-afternoon liquidity window",
     "horizon": "the expiry session's last hour",
     "condition": "declared WEAK: the index is not quoted here, so the target is a spillover proxy",
     "control": "non-expiry months in the same cycle; and EUSTX50 on the same dates",
     "falsifier": "no measurable difference on expiry sessions, which would confirm the spillover "
                  "is too small to see from the currency"},
    {"source": "Medium Term Programme assumed USDTRY minus spot", "target": "USDTRY",
     "sign": "two_sided",
     "mechanism": "a published official exchange-rate assumption is a dated fiscal expectation; "
                  "the gap to spot measures how far reality has run from the plan and therefore "
                  "how much fiscal adjustment is pending",
     "horizon": "60 to 250 sessions",
     "condition": "measured at a fixed horizon; the programme is superseded each September",
     "control": "the Australian iron-ore and Azerbaijani oil-price assumptions as structural "
                "analogues in other packs",
     "falsifier": "no relationship, which would mean the assumption is understood as a "
                  "presentational number rather than a fiscal commitment"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "orthodox tightening and the 2018 crisis", "start": "2017-01-01",
     "end": "2019-07-24",
     "regime": "conventional policy under pressure, then the August 2018 currency crisis and an "
               "emergency tightening to 24%",
     "markers": ("2018-08 the currency crisis", "2018-09 the increase to 24%"),
     "why_it_matters": "the last period in which the announced rate and the effective funding "
                       "cost moved together; every relationship estimated here is conventional "
                       "and none of it survives into the next era",
     "status": "SETTLED"},
    {"name": "governor churn and the first easing", "start": "2019-07-25", "end": "2021-09-22",
     "regime": "rapid easing, a reversal in late 2020, and repeated changes at the top of the "
               "Bank; heavy use of macroprudential and swap instruments",
     "markers": ("multiple governor changes between 2019 and 2021",
                 "the late-2020 re-tightening and its reversal"),
     "why_it_matters": "the ANNOUNCED rate and the EFFECTIVE funding cost diverged materially "
                       "here, so a rate-surprise study is measuring an instrument that was not "
                       "doing the work",
     "status": "SETTLED"},
    {"name": "the unorthodox era and liraisation", "start": "2021-09-23", "end": "2023-06-21",
     "regime": "the policy rate cut from 19% to 8.5% while annual inflation rose above 80%; KKM "
               "introduced on 20 December 2021; heavy reserve use, a large swap book and "
               "extensive selective credit measures",
     "markers": ("2021-12-20 KKM introduced", "inflation above 80% in late 2022",
                 "the policy rate at 8.5%"),
     "why_it_matters": "THE REACTION FUNCTION WAS INVERTED. A hot inflation print did NOT raise "
                       "the expected policy rate, so TR-D's sign flips inside this window and any "
                       "estimate pooled across its boundary describes neither side",
     "status": "SETTLED"},
    {"name": "the normalisation", "start": "2023-06-22", "end": "2024-12-25",
     "regime": "a return to conventional tightening: the policy rate from 8.5% to 50% inside a "
               "year, simplification of the macroprudential framework, the KKM wind-down begun "
               "and reserves rebuilt",
     "markers": ("2023-06 the first increase of the cycle",
                 "2024-03 the policy rate reaching 50%",
                 "the KKM wind-down"),
     "why_it_matters": "the richest era for TR-A and TR-B: large, frequent, conventional "
                       "surprises against a reserve position the market could derive weekly",
     "status": "SETTLED"},
    {"name": "the easing cycle and its interruptions", "start": "2024-12-26", "end": "2099-12-31",
     "regime": "easing from 50% with at least one sharp interruption in March 2025 that cost "
               "reserves and reversed the direction temporarily",
     "markers": ("2024-12 the first cut of the cycle", "the March 2025 episode"),
     "why_it_matters": "UNVERIFIED TAIL. Anything this pack asserts about 2025-2026 Turkish "
                       "policy must be re-read from tcmb.gov.tr before a study conditions on it; "
                       "the desk's knowledge of this era is not point-in-time and is treated as "
                       "UNMEASURED until checked",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the USDTRY swap table is asymmetric by roughly 7.4 to one",
     "measured": "universe.json: swap_long -10,921, swap_short +1,481 points per lot per day",
     "consequence": "holding the depreciation trade costs about seven times what the carry trade "
                    "pays. COST MUST BE DIRECTION-DEPENDENT IN EVERY TURKISH CELL, and TR-E gates "
                    "the rest of the pack the way RU-M gates the Russian one"},
    {"constraint": "the crosses are three to four times more expensive than USDTRY",
     "measured": "median H1 spread over the last 60 days: USDTRY 405 points (~8bp on 48.66), "
                 "EURTRY 1,587 points (~28bp), GBPTRY 2,405 points (~37bp); zero frozen bars on "
                 "all three",
     "consequence": "an EURTRY or GBPTRY cell must clear proportionally more, and the choice of "
                    "cross is an economic decision rather than a convenience"},
    {"constraint": "no Turkish short-rate instrument is quoted here",
     "measured": "no TRY OIS, swap or bill future in data/universe/universe.json",
     "consequence": "the policy expectation must come from the CBRT survey or press polls, both "
                    "SURVEYS. A meeting with no sourced expectation has an UNMEASURED surprise, "
                    "never a zero one"},
    {"constraint": "the announced policy rate has not always been the binding rate",
     "measured": "the effective funding cost diverged from the announced rate through reserve "
                 "requirements, securities maintenance and selective credit measures",
     "consequence": "a surprise measured against the announced rate alone can be EXACTLY "
                    "BACKWARDS when the tightening was delivered macroprudentially; TR-A must "
                    "carry both series"},
    {"constraint": "the swap-excluded net reserve figure is DERIVED, not published",
     "measured": "the CBRT publishes the components weekly; the market's key number is computed "
                 "from them and analysts compute it differently",
     "consequence": "the derivation version must travel with every result, or two studies will "
                    "disagree without either being wrong"},
    {"constraint": "there is no COT series for the lira",
     "measured": "no liquid CME Turkish lira contract carries a reportable COT series",
     "consequence": "lira positioning is UNMEASURED except through the CBRT's weekly non-resident "
                    "securities holdings, which are seven days stale and mix flow with "
                    "valuation. cot_currency on this pack is deliberately empty and no other "
                    "EM currency's COT may be substituted"},
    {"constraint": "the official inflation print is publicly contested",
     "measured": "ENAG publishes an alternative CPI far above TÜİK's on the same day",
     "consequence": "BOTH ARE KEPT. The official series is what policy reacts to and is the one "
                    "an event study must use; the GAP is a separate dated variable. ENAG is "
                    "registered CONTRADICTED at low weight and is never dropped, because a "
                    "contested measurement is itself a measurement"},
    {"constraint": "BIST, VİOP and the Kapalıçarşı quote are not on this broker",
     "measured": "no Turkish index, future or bullion quote in the universe registry",
     "consequence": "TR-G, TR-H and part of TR-F are transmission-target domains; the free-market "
                    "gold premium in particular is the pack's most distinctive observable and the "
                    "desk cannot see it directly -- a NAMED GAP, not an omission"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, carrying the fields the frozen dataclass has no slot for
    alongside it so nothing is silently dropped."""
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
