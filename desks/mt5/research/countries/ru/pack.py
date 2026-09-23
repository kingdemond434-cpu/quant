"""RUSSIA: a budget rule, a tax date, a frozen quote, and the commodity leg that is still tradeable.

WHAT RUSSIA IS AS A MARKET MECHANISM, AND WHY THE PACK IS SHAPED THE WAY IT IS. Four mechanisms
belong to this economy and to no other in the desk's book, and one measurement overrides all four
when it comes to deciding what may be traded:

  1. THE FISCAL RULE IS A PUBLISHED, DATED FX ORDER. Under the budget rule (бюджетное правило)
     the Ministry of Finance buys or sells foreign currency according to the gap between actual
     and BASE oil-and-gas revenues. The amount is ANNOUNCED, in roubles, on or about the third
     business day of each month, and the operations then run daily from the 7th of that month to
     the 6th of the next. Since 2023 the currency bought and sold is the renminbi, and the Bank
     of Russia additionally "mirrors" (зеркалирует) National Wealth Fund transactions on top.
     Almost nowhere else is a sovereign FX flow published in advance with a size and a date.

  2. THE TAX DATE IS A MONTHLY, MECHANICAL ROUBLE BID. Since 1 January 2023 the unified tax
     payment (единый налоговый платёж) falls on the 28th of each month, and the mineral
     extraction tax on oil (НДПИ) with it. Exporters holding dollars and renminbi must convert to
     roubles to pay, so the days running up to the 28th carry a structural rouble demand that is
     not a view and is not optional. Before 2023 the obligations were staggered across the 25th
     to the 28th, so the window itself MOVED -- and a study pooled across that boundary is
     averaging two different calendars.

  3. THE EXPORT-REVENUE SURRENDER IS A DECREE, NOT A MARKET. From October 2023 a presidential
     decree required named exporter groups to repatriate and SELL a share of their foreign
     currency earnings, with the thresholds changed several times since. The flow exists because
     a decree says so; its size moves when the decree moves and not when the price does.

  4. THE OFFICIAL RATE IS NO LONGER AN EXCHANGE RATE. After the Moscow Exchange and its clearing
     house were designated on 12 June 2024, exchange trading in dollars and euros stopped, and the
     Bank of Russia's official rate has since been computed from BANK OTC REPORTING rather than
     from exchange trades. The renminbi/rouble pair became the main exchange-traded FX pair. So
     there are now at least three different "USDRUB" numbers -- the CBR official rate, the
     domestic OTC rate, and whatever offshore print this broker quotes -- and they are not the
     same series. A pack that treats them as one is measuring a basis, not a currency.

AND THE MEASUREMENT THAT OVERRIDES ALL OF IT, taken on this box on 2026-09-17:

  * EURRUB's tape STOPS at 2022-02-28 (15,199 H1 bars, nothing after; collection-time spread
    1,397,460 points, about 14 roubles). It is a TRANSMISSION TARGET here, never an instrument.
  * USDRUB runs to 2026-09-16 but its median H1 spread over the last sixty days is 137,509 points
    -- 1.375 roubles, about 164bp on a rate of 84 -- against 453 points (about 6bp) through 2021,
    a 300-fold widening. And 30.6% of the last sixty days' hourly bars are FROZEN: open = high =
    low = close. A third of the recent tape is a stale quote rather than a market.

The consequence is written into every domain below: Russian mechanisms are hunted for their
effect on the COMMODITY LEG and on USDCNH, and USDRUB appears as a target only where the expected
move is large enough to clear a 164bp cost floor and only on horizons long enough that a frozen
bar does not decide the result. `RU-M` exists solely to keep that honest.

THE TWO-LANE ORDER AND THE UNIVERSE MANDATE. Gazprom, Rosneft, Nornickel, Rusal, Sberbank and
Lukoil appear in this pack ONLY as actors. IMOEX, RTS, OFZ and the CNY/RUB pair are transmission
targets. No crypto-exchange ground is touched anywhere (mandate of 2026-08-18).

LAWFULNESS AND SOURCING. Everything here is PUBLIC primary material: the Bank of Russia's own
publications, Minfin's monthly budget-rule announcements, Rosstat, and the Russian-language
academic and community web. The desk has no Russian venue access, no broker relationship, no
market-data licence and no exchange connectivity, and seeks none. Every source row says which of
those it is.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# ruff: noqa: RUF001, RUF002
# RUF001/RUF002 flag Cyrillic characters that look like Latin ones. They exist to catch
# homoglyph attacks in IDENTIFIERS; this file deliberately carries Russian-language
# terminology as DATA, because a text screen that cannot match "ключевая ставка" cannot
# find the Bank of Russia's own headline. Suppressed file-wide and explained here rather
# than scattered as per-line noqa, and no identifier in this module is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "RU"
NAME = "Russian Federation"
REGION_COMMAND = "russia_cis"
REGION_DESK = "RUSSIA"
CURRENCY = "RUB"
FISCAL_YEAR_END = "12-31"  # the federal budget year is the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("ru",)

#: Fusion-quotable instruments a Russian mechanism can reach. USDRUB is here but is COST-FENCED:
#: see ACCESS_CONSTRAINTS and RU-M. EURRUB is deliberately ABSENT -- its tape ends 2022-02-28.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDRUB",                          # quoted to 2026-09-16, ~164bp, 30.6% frozen bars
    "XBRUSD", "XTIUSD", "XNGUSD",      # the export complex: Urals prices off Brent
    "XPDUSD", "XPTUSD",                # Nornickel is ~40% of world palladium
    "XNIUSD", "XALUSD", "XCUUSD",      # nickel, aluminium, copper
    "XAUUSD", "XAGUSD",                # reserve accumulation and domestic gold purchase
    "WHEAT", "CORN",                   # the largest wheat exporter in the world
    "USDCNH",                          # the renminbi IS the budget rule's currency since 2023
    "USDTRY",                          # the Turkey trade and tourism channel
    "USDX", "EURUSD",                  # the dollar factor every RUB-adjacent cell needs
    "US500", "UST10Y",                 # global risk and duration controls
    "GER40", "EUSTX50",                # the European energy-cost channel
)

#: Instruments and series this pack's mechanisms are ABOUT that this broker does not quote, or
#: that it quotes but the desk refuses to compile cells against.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "EURRUB", "venue": "quoted by this broker but DEAD on this box",
     "why": "MEASURED 2026-09-17: EURRUB_H1.parquet holds 15,199 bars ending 2022-02-28 and "
            "nothing after; collection-time spread 1,397,460 points, about 14 roubles. A symbol "
            "with no tape after the event that defines the modern regime cannot carry a cell",
     "proxies": ("USDRUB", "EURUSD", "USDCNH")},
    {"name": "CNY/RUB (юань/рубль) on the Moscow Exchange",
     "venue": "MOEX",
     "why": "since June 2024 this is the MAIN exchange-traded FX pair in Russia and the currency "
            "the budget rule actually transacts; it is the domestic price the desk cannot see",
     "proxies": ("USDCNH", "USDRUB")},
    {"name": "Bank of Russia official rate (официальный курс)", "venue": "CBR",
     "why": "set around 13:00-13:30 Moscow and effective the NEXT calendar day; since June 2024 "
            "computed from bank OTC reporting rather than exchange trades. It is a DIFFERENT "
            "series from any offshore quote and the gap between them is a sanction basis",
     "proxies": ("USDRUB", "USDCNH")},
    {"name": "Urals crude and the Urals-Brent discount (дисконт)", "venue": "assessed, OTC",
     "why": "the export price is Brent MINUS a discount that moved from about $2 to more than $30 "
            "and back; treating Brent as the Russian export price is the single largest modelling "
            "error available here",
     "proxies": ("XBRUSD", "XTIUSD", "USDRUB")},
    {"name": "ESPO blend and the Asian export netback", "venue": "assessed, OTC",
     "why": "the eastern export grade; its discount to Brent differs from Urals' and re-routes "
            "with freight and insurance policy rather than with demand",
     "proxies": ("XBRUSD", "USDCNH")},
    {"name": "IMOEX and RTS indices", "venue": "MOEX",
     "why": "the domestic equity market; IMOEX is rouble-denominated and RTS is the same book in "
            "dollars, so the pair IS a currency observable -- and neither is quoted here",
     "proxies": ("USDRUB", "EUSTX50", "XBRUSD")},
    {"name": "OFZ and the RGBI government bond index", "venue": "MOEX",
     "why": "the domestic rates curve the key rate transmits into; the OFZ auction calendar is "
            "Wednesday and is the sovereign's own funding clock",
     "proxies": ("USDRUB", "UST10Y")},
    {"name": "Minfin monthly budget-rule FX operation announcement", "venue": "Minfin",
     "why": "an announced, sized, dated sovereign FX order; the announcement is the event and the "
            "daily operations are the flow",
     "proxies": ("USDRUB", "USDCNH")},
    {"name": "National Wealth Fund (ФНБ) and its mirroring operations",
     "venue": "Minfin/CBR",
     "why": "the fund's liquid part is the fiscal buffer; CBR mirrors its transactions on top of "
            "the budget rule, so the NET sovereign flow is the sum of two published numbers",
     "proxies": ("USDRUB", "USDCNH", "XAUUSD")},
    {"name": "Russian wheat export price and the export duty/quota",
     "venue": "assessed; Ministry of Agriculture",
     "why": "Russia is the world's largest wheat exporter; the floating export duty and the "
            "second-half-season quota are administrative supply shocks with published formulas",
     "proxies": ("WHEAT", "CORN")},
    {"name": "Nornickel palladium and nickel production guidance", "venue": "company disclosure",
     "why": "roughly 40% of world palladium and a large nickel share sit with one producer; a "
            "production or logistics event there is a global metal supply event",
     "proxies": ("XPDUSD", "XPTUSD", "XNIUSD")},
    {"name": "Gazprom pipeline flows to Europe and the Turkish corridor", "venue": "ENTSOG etc.",
     "why": "European gas cost, and therefore European industrial margin, depends on volumes "
            "published daily by the pipeline operators",
     "proxies": ("XNGUSD", "GER40", "EUSTX50")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Russia (Банк России / Центральный банк Российской Федерации)",
    "short": "CBR",
    "framework": "inflation_targeter",
    "committee": "Board of Directors (Совет директоров)",
    "policy_instrument": "the key rate (ключевая ставка) -- the one-week repo auction and deposit "
                         "operation rate, with a symmetric +/-100bp standing-facility corridor",
    "corridor": "the one-day standing deposit facility sits 100bp below the key rate and the "
                "standing lombard/repo facility 100bp above",
    "mandate": "4% annual consumer price inflation, a point target rather than a band",
    "decision_rule": "EIGHT scheduled meetings a year, always on a FRIDAY. Four of them are "
                     "'core' meetings accompanied by the Monetary Policy Report (Доклад о "
                     "денежно-кредитной политике) and by a published forecast for the AVERAGE key "
                     "rate over the coming years. The decision is released at 13:30 Moscow and "
                     "the Governor holds a press conference at 15:00 Moscow.",
    "announce_local": "13:30 Europe/Moscow",
    "announce_utc": "10:30",
    "announce_utc_dst": "10:30",
    "dst_rule": "NONE. Russia abolished seasonal clock changes in 2014 and Moscow has been a "
                "fixed UTC+3 since. This is a genuine convenience: unlike every other country in "
                "this department the Russian event minute in UTC never moves, so a fixed-UTC "
                "event window is correct all year",
    "presser_utc": "12:00",
    "minutes_lag_days": 0,
    "consensus_proxy": "there is NO on-broker consensus proxy and no accessible domestic curve. "
                       "The usable public expectations are the CBR's own macro survey of "
                       "professional forecasters and the Reuters/Interfax polls reported in the "
                       "Russian press. Both are SURVEYS, not traded curves, and a surprise built "
                       "from them is a weaker object than the Australian IB-implied surprise.",
    "consensus_proxy_trap": "the CBR publishes a forecast for the AVERAGE key rate over a calendar "
                            "year, not an end-of-period rate. A 'path revision' computed as if it "
                            "were an end-of-period forecast is arithmetically wrong, and the error "
                            "grows as the year progresses because the elapsed months are already "
                            "fixed inside the average",
    "distinctive": "the average-key-rate forecast range is a Russian-specific communication "
                   "instrument with no counterpart in the Australian or New Zealand packs; it is "
                   "a commitment about a PATH INTEGRAL rather than about a level",
    "crisis_history": ("2014-12-16: an overnight increase from 10.5% to 17% announced at 01:00 "
                       "Moscow -- the largest single move in the series",
                       "2022-02-28: an increase from 9.5% to 20% with capital controls, a "
                       "mandatory 80% export-revenue surrender and a closed exchange",
                       "2022-04 to 2022-09: the reversal back to 7.5% as the current account "
                       "surplus overwhelmed a closed capital account"),
    "off_cycle": "the CBR has moved out of cycle repeatedly and at extraordinary hours. Every "
                 "unscheduled decision is its own class and none may be pooled with the scheduled "
                 "eight",
    "other_clocks": (
        {"what": "Monetary Policy Report (Доклад о ДКП) with the average-key-rate forecast",
         "when_local": "13:30 Moscow on the four core decision days", "when_utc": "10:30",
         "reference_lag_days": 0},
        {"what": "weekly consumer price index (недельная инфляция) from Rosstat",
         "when_local": "Wednesday, about 19:00 Moscow", "when_utc": "16:00",
         "reference_lag_days": 3},
        {"what": "monthly balance of payments estimate",
         "when_local": "around the 9th-12th", "when_utc": "12:00", "reference_lag_days": 10},
        {"what": "CBR macro survey of professional forecasters",
         "when_local": "monthly, ahead of each decision", "when_utc": "12:00",
         "reference_lag_days": 0},
    ),
    "root": "https://www.cbr.ru",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Russia official rate (официальный курс доллара США)",
     "local": "computed around 13:00-13:30 Moscow and EFFECTIVE THE NEXT CALENDAR DAY",
     "time_utc": "10:30", "time_utc_dst": "10:30", "dst_rule": "none (Moscow is fixed UTC+3)",
     "instruments": ("USDRUB",), "window_minutes": 30, "confidence": "SETTLED",
     "why": "the rate every rouble contract, tax liability and budget line is struck at. The "
            "NEXT-DAY effective date is the trap: an event study that applies the official rate "
            "on its publication day is using tomorrow's number today"},
    {"name": "Bank of Russia official rate, post-June-2024 methodology",
     "local": "derived from BANK OTC REPORTING, not from exchange trades",
     "time_utc": "10:30", "time_utc_dst": "10:30", "dst_rule": "none",
     "instruments": ("USDRUB",), "window_minutes": 30,
     "confidence": "SETTLED as a fact; the resulting SERIES BREAK is the object",
     "why": "after the 12 June 2024 designation of the exchange and its clearing house, exchange "
            "trading in dollars and euros stopped. The official series continues but is a "
            "DIFFERENT construction from that date, and a level study that pools across it is "
            "joining two series that share a name and not a definition"},
    {"name": "MOEX CNY/RUB session",
     "local": "07:00-23:50 Moscow", "time_utc": "04:00", "time_utc_dst": "04:00",
     "dst_rule": "none", "instruments": ("USDCNH",), "window_minutes": 1190,
     "confidence": "DECLARED, VERIFY against moex.com",
     "why": "the renminbi pair is now the main exchange-traded FX market in Russia and the "
            "currency the budget rule transacts; the desk cannot see it and uses USDCNH as the "
            "only available proxy for its offshore twin"},
    {"name": "LBMA gold price and the CBR's domestic gold purchases",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "confidence": "SETTLED",
     "why": "domestic gold production is bought for reserves at a domestic price referencing the "
            "London benchmark; reserve composition shifted sharply toward gold and renminbi"},
    {"name": "Brent dated and the Urals assessment window",
     "local": "the London afternoon assessment", "time_utc": "16:30", "time_utc_dst": "15:30",
     "dst_rule": "GMT/BST", "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "confidence": "DECLARED",
     "why": "the Urals price is an ASSESSMENT against Brent, and the MET and export-duty formulas "
            "reference a published monthly average of it, so the fiscal transmission runs through "
            "a monthly average and not through the spot print"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "unified tax payment day (единый налоговый платёж)", "kind": "day_of_month",
     "convention": "the 28th of each month since 1 January 2023; the mineral extraction tax on "
                   "oil (НДПИ) falls on the same date",
     "rollover_utc": "10:30", "instruments": ("USDRUB", "USDCNH"),
     "why": "exporters holding foreign currency must convert to roubles to pay, so the days "
            "running up to the 28th carry a structural rouble bid. BEFORE 2023 the obligations "
            "were staggered across the 25th to the 28th: the window itself MOVED, and pooling "
            "across the boundary averages two different calendars"},
    {"name": "budget-rule FX operations window (бюджетное правило)", "kind": "day_of_month",
     "convention": "announced on or about the third business day; daily operations from the 7th "
                   "of the month to the 6th of the next",
     "rollover_utc": "10:00", "instruments": ("USDRUB", "USDCNH"),
     "why": "an ANNOUNCED, SIZED, DATED sovereign FX order. The announcement is an event; the "
            "operations are a flow; and they are not the same object"},
    {"name": "CBR mirroring of National Wealth Fund transactions", "kind": "day_of_month",
     "convention": "daily, alongside the budget-rule operations",
     "rollover_utc": "10:00", "instruments": ("USDRUB", "USDCNH"),
     "why": "the NET sovereign flow is the budget-rule amount PLUS the mirroring amount; using "
            "only the first understates it, sometimes by more than the first"},
    {"name": "Russian spot FX value date", "kind": "weekday",
     "convention": "domestic TOD/TOM convention (same day and next day) rather than T+2",
     "rollover_utc": "21:00 (EST) / 22:00 (EDT) for the offshore CFD",
     "instruments": ("USDRUB",),
     "why": "the domestic market settles TOD and TOM; the offshore CFD this desk quotes settles "
            "on the ordinary T+2 convention, so the two carry DIFFERENT forward points and the "
            "gap is part of the sanction basis"},
    {"name": "federal budget year", "kind": "fiscal_year_end", "convention": "31 December",
     "rollover_utc": "", "instruments": ("USDRUB",),
     "why": "the budget law is passed in the autumn for the calendar year; the base oil-and-gas "
            "revenue figure that drives the budget rule is set in it"},
    {"name": "New Year holiday block", "kind": "month_end",
     "convention": "1 to 8 January inclusive -- the longest scheduled market closure of any "
                   "country in this department",
     "rollover_utc": "", "instruments": ("USDRUB", "XBRUSD", "XNGUSD"),
     "why": "eight consecutive non-working days; the offshore CFD still quotes while the domestic "
            "market does not, so the January gap is a one-sided-book event and not a news event"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Moscow Exchange (MOEX) -- FX market",
     "index_symbols": (),
     "open_local": "07:00", "close_local": "23:50", "open_utc": "04:00", "close_utc": "20:50",
     "dst_rule": "none (Moscow is fixed UTC+3)",
     "auction": "continuous; no closing auction in FX",
     "expiry_rule": "n/a",
     "holidays": "the Russian government's annual holiday-transfer decree",
     "notes": "USD and EUR trading STOPPED on 12 June 2024 after the exchange and its clearing "
              "house were designated. CNY/RUB is the main pair now. The desk has no access and "
              "no data licence; this row exists so the absence is named rather than assumed"},
    {"name": "Moscow Exchange -- equity and derivatives",
     "index_symbols": (),
     "open_local": "09:50 (derivatives) / 09:59 (equities)", "close_local": "23:50",
     "open_utc": "06:50", "close_utc": "20:50", "dst_rule": "none",
     "auction": "opening and closing auctions on the equity market",
     "expiry_rule": "index futures (RTS, MIX) expire on the third Thursday of March, June, "
                    "September and December",
     "holidays": "the Russian government's annual holiday-transfer decree",
     "notes": "IMOEX is rouble-denominated and RTS is the same book in dollars; the RATIO of the "
              "two is a currency observable that needs no FX quote at all -- which is precisely "
              "why it is worth naming even though the desk cannot see either"},
    {"name": "St Petersburg International Mercantile Exchange (SPIMEX)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "18:30", "open_utc": "07:00", "close_utc": "15:30",
     "dst_rule": "none", "auction": "commodity auctions",
     "expiry_rule": "n/a",
     "holidays": "the Russian government's annual holiday-transfer decree",
     "notes": "domestic oil-product and gas auctions; the domestic wholesale fuel price is set "
              "here and is a politically-managed number rather than a market-clearing one"},
)


# --------------------------------------------------------------------------- holidays
def _next_working(day: date, taken: set[date]) -> date:
    while day.weekday() >= 5 or day in taken:
        day += timedelta(days=1)
    return day


#: The federal non-working holidays under Article 112 of the Labour Code. The New Year block is
#: 1-8 January inclusive -- the longest scheduled closure of any country in this department.
FIXED_FEDERAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Новогодние каникулы (New Year holidays, day 1)"),
    (1, 2, "Новогодние каникулы (day 2)"),
    (1, 3, "Новогодние каникулы (day 3)"),
    (1, 4, "Новогодние каникулы (day 4)"),
    (1, 5, "Новогодние каникулы (day 5)"),
    (1, 6, "Новогодние каникулы (day 6)"),
    (1, 7, "Рождество Христово (Orthodox Christmas)"),
    (1, 8, "Новогодние каникулы (day 8)"),
    (2, 23, "День защитника Отечества (Defender of the Fatherland Day)"),
    (3, 8, "Международный женский день (International Women's Day)"),
    (5, 1, "Праздник Весны и Труда (Spring and Labour Day)"),
    (5, 9, "День Победы (Victory Day)"),
    (6, 12, "День России (Russia Day)"),
    (11, 4, "День народного единства (Unity Day)"),
)


def national_holidays(year: int) -> dict[date, str]:
    """Russia's federal non-working days for `year`.

    THE RULE, AND ITS LIMIT. Article 112 of the Labour Code fixes the dates above and provides
    that a holiday falling on a Saturday or Sunday transfers (переносится) to the next working
    day. That much is computable and is what this function returns. The GOVERNMENT then issues an
    annual decree (постановление о переносе выходных дней) that moves additional days to build
    long weekends -- bridging a Tuesday holiday by making the Monday non-working and recovering it
    on a Saturday, for example. Those extra transfers are DECREED, not derivable, and this
    function does not invent them: `HOLIDAYS_RULE['decree_note']` says so, and a miner that needs
    the exact working calendar must read the decree.
    """
    out: dict[date, str] = {}
    taken: set[date] = set()
    for month, day, label in FIXED_FEDERAL:
        actual = date(year, month, day)
        out[actual] = label
        taken.add(actual)
    for month, day, label in FIXED_FEDERAL:
        actual = date(year, month, day)
        if actual.weekday() < 5:
            continue
        if month == 1 and day <= 8:
            continue  # the New Year block already covers the weekend days inside it
        moved = _next_working(actual + timedelta(days=1), taken)
        taken.add(moved)
        out[moved] = f"{label} — перенос (transferred)"
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The days the Russian domestic market is closed. Identical to the federal set: MOEX follows
    the government calendar and does not keep one of its own."""
    return national_holidays(year)


def tax_period_windows(year: int) -> dict[date, str]:
    """The unified tax payment date (the 28th) for each month, and the conversion window before it.

    Since 1 January 2023 the единый налоговый платёж falls on the 28th. Before that the
    obligations were staggered across the 25th to the 28th. This function returns the POST-2023
    rule; `HOLIDAYS_RULE['tax_rule']` states the pre-2023 one, and a study spanning the boundary
    must switch between them rather than applying one to both.
    """
    out: dict[date, str] = {}
    for month in range(1, 13):
        day = date(year, month, 28)
        out[day] = ("единый налоговый платёж / НДПИ (unified tax payment; exporter rouble demand "
                    "builds over the preceding five business days)")
    return out


def budget_rule_windows(year: int) -> dict[date, str]:
    """The budget-rule operating window: daily operations from the 7th of each month to the 6th of
    the next, with the amount announced on or about the third business day."""
    out: dict[date, str] = {}
    for month in range(1, 13):
        out[date(year, month, 7)] = ("бюджетное правило — operations begin (announced on or about "
                                     "the third business day of the month)")
    return out


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_labour_code_plus_annual_decree",
    "authority": "Article 112 of the Labour Code of the Russian Federation for the fixed dates "
                 "and the weekend-transfer rule; an annual government decree (постановление о "
                 "переносе выходных дней) for the additional bridging transfers",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "fixed_rule": "1-8 January (Новогодние каникулы, including Orthodox Christmas on 7 January), "
                  "23 February, 8 March, 1 May, 9 May, 12 June and 4 November",
    "transfer_rule": "a holiday falling on a Saturday or Sunday transfers to the next working "
                     "day; the New Year block already absorbs the weekend days inside it",
    "decree_note": "THE ANNUAL DECREE IS THE AUTHORITY AND IT IS NOT DERIVABLE. The government "
                   "moves additional days each year to build long weekends -- typically bridging "
                   "a mid-week holiday and recovering the day on a Saturday. This module computes "
                   "only the Labour Code rule; the decree's extra transfers are UNMEASURED here "
                   "and a miner needing the exact working calendar must read the decree rather "
                   "than trusting this function",
    "tax_rule": "the unified tax payment (единый налоговый платёж) falls on the 28th of each "
                "month since 1 January 2023; before that the obligations were staggered across "
                "the 25th to the 28th. A study spanning that boundary must switch rules",
    "known_dates": {
        "2026-01-01": "Новогодние каникулы begin; 1-8 January inclusive are non-working",
        "2026-01-07": "Рождество Христово (Orthodox Christmas), inside the New Year block",
        "2026-01-08": "the last day of the New Year block",
        "2026-02-23": "День защитника Отечества, a Monday -- no transfer needed",
        "2026-03-08": "Международный женский день falls on a SUNDAY; transfers to Monday "
                      "2026-03-09",
        "2026-05-01": "Праздник Весны и Труда, a Friday",
        "2026-05-09": "День Победы falls on a SATURDAY; transfers to Monday 2026-05-11",
        "2026-06-12": "День России, a Friday",
        "2026-11-04": "День народного единства, a Wednesday",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "tax_fn": tax_period_windows,
    "budget_rule_fn": budget_rule_windows,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = ""
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- CME Russian rouble futures (6R)",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "fields": (), "frequency": "weekly until 2022", "snapshot": "Tuesday close",
     "publish_utc": "", "lag_days": 3, "licence": "free, public", "available": False,
     "why": "the rouble contract was suspended and then delisted in 2022",
     "pit_warning": "THE SERIES ENDS IN 2022 AND THERE IS NO SUCCESSOR. Rouble positioning is "
                    "UNMEASURED from that point. It must be reported as UNMEASURED and never "
                    "back-filled, extrapolated or proxied with another currency's COT"},
    {"name": "MOEX open interest and the client-category breakdown", "root": "https://www.moex.com",
     "fields": ("open_interest", "individuals", "legal_entities", "non_residents"),
     "frequency": "daily", "snapshot": "session close", "publish_utc": "", "lag_days": 1,
     "licence": "exchange data; the desk has NO licence and NO access", "available": False,
     "why": "MOEX publishes an unusually detailed participant split, including retail versus "
            "institutional and resident versus non-resident",
     "pit_warning": "NOT ACCESSIBLE TO THIS DESK. Named so the gap is visible: this is the best "
                    "positioning data in the country and the desk does not have it"},
    {"name": "Bank of Russia balance of payments and the reserve composition",
     "root": "https://www.cbr.ru/statistics/macro_itm/svs/",
     "fields": ("current_account", "financial_account", "reserves_total", "gold_share"),
     "frequency": "monthly and quarterly", "snapshot": "period", "publish_utc": "12:00",
     "lag_days": 10, "licence": "free, public", "available": True,
     "why": "the current-account surplus IS the structural FX supply; reserve composition shifted "
            "sharply toward gold and renminbi after 2022 and the shift is published",
     "pit_warning": "the monthly estimate is revised materially in the quarterly figure; the "
                    "first estimate is the point-in-time datum and the revision is a second one"},
    {"name": "Minfin budget-rule monthly announcement",
     "root": "https://minfin.gov.ru/ru/perfomance/nationalwealthfund/",
     "fields": ("announced_amount_rub", "direction", "period_start", "period_end"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "12:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the only sovereign FX order in this department that is published IN ADVANCE with a "
            "size and a date",
     "pit_warning": "the announcement date moves with the business-day calendar; anchoring to a "
                    "fixed calendar day mis-times roughly a third of the sample"},
    {"name": "CBR macro survey of professional forecasters",
     "root": "https://www.cbr.ru/statistics/ddkp/mo_br/",
     "fields": ("key_rate_forecast", "cpi_forecast", "usdrub_forecast", "gdp_forecast"),
     "frequency": "monthly", "snapshot": "survey close", "publish_utc": "12:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the closest thing to a consensus for the key rate that the desk can lawfully reach",
     "pit_warning": "a SURVEY, not a traded curve. A surprise built from it is a weaker object "
                    "than one built from a market-implied path and must be labelled as such"},
)

# --------------------------------------------------------------------------- terminology
#: Russian is the working language of every primary source here. A screen that does not carry
#: these tokens will not find the CBR's own headline, let alone smart-lab's or Vedomosti's.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "RU-A": ("ключевая ставка", "Банк России", "Совет директоров", "заседание",
             "денежно-кредитная политика", "ДКП", "инфляция", "таргет", "повышение ставки",
             "снижение ставки", "жёсткая ДКП"),
    "RU-B": ("Доклад о денежно-кредитной политике", "среднегодовая ключевая ставка", "прогноз",
             "макроопрос", "ожидания аналитиков"),
    "RU-C": ("бюджетное правило", "базовые нефтегазовые доходы", "Минфин",
             "операции с валютой", "покупка валюты", "продажа валюты", "зеркалирование",
             "ФНБ", "Фонд национального благосостояния"),
    "RU-D": ("налоговый период", "единый налоговый платёж", "ЕНП", "НДПИ", "28-е число",
             "налоговые выплаты", "экспортёры", "конвертация"),
    "RU-E": ("валютная выручка", "обязательная продажа", "репатриация", "указ",
             "экспортёры", "норматив продажи"),
    "RU-F": ("Urals", "Юралс", "дисконт", "дисконт Urals к Brent", "ESPO", "ЭСПО",
             "экспортная пошлина", "потолок цен", "нефтегазовые доходы", "баррель"),
    "RU-G": ("официальный курс", "курс ЦБ", "биржевой курс", "внебиржевой курс",
             "юань", "CNY/RUB", "МосБиржа", "НКЦ", "торги долларом"),
    "RU-H": ("палладий", "никель", "алюминий", "Норникель", "Русал", "производство",
             "логистика", "поставки"),
    "RU-I": ("пшеница", "экспорт зерна", "экспортная пошлина на пшеницу", "квота",
             "урожай", "Минсельхоз"),
    "RU-J": ("газ", "трубопровод", "прокачка", "СПГ", "Газпром", "транзит"),
    "RU-K": ("ОФЗ", "аукцион Минфина", "РГБИ", "RGBI", "доходность", "размещение"),
    "RU-L": ("ИМОЭКС", "IMOEX", "РТС", "RTS", "индекс МосБиржи", "дивиденды", "отсечка"),
    "RU-M": ("спред", "ликвидность", "проскальзывание", "заморозка котировки",
             "нерезиденты", "счёт типа С", "санкции", "инфраструктурный риск"),
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


#: RUSSIA'S TEN LAYERS. Every `queries` tuple below is RUSSIAN, in Cyrillic, including the slang.
#: This is not decoration: a screen searching "algorithmic trading Russia" finds the small
#: English-speaking corner of a very large Russian-language ground and then reports that corner as
#: if it were the ground. "Автоследование" (copy-trading as a regulated brokerage product),
#: "стакан" (the order book, literally "the glass"), "советник" (an MT4/MT5 expert advisor) and
#: "ЛЧИ" (the exchange's own public trading competition) have no English search that reaches them.
#:
#: SANCTIONS SOURCES ARE OFFICIAL PUBLIC DATA AND ARE USED AS DATA. OFAC, EU and UK designation
#: lists are published by governments, carry dates, and are the single best record of when a
#: channel closed. They are registered in the official layer like any other government series.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "ru_cbr", "Bank of Russia primary publications", layer="official",
        roots=("https://www.cbr.ru/press/keypr/", "https://www.cbr.ru/dkp/",
               "https://www.cbr.ru/statistics/", "https://www.cbr.ru/analytics/"),
        queries=("ключевая ставка", "решение по ключевой ставке", "Совет директоров",
                 "денежно-кредитная политика", "ДКП", "Доклад о денежно-кредитной политике",
                 "среднегодовая ключевая ставка", "официальный курс", "платёжный баланс",
                 "международные резервы", "макроопрос"),
        languages=("ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="13:30 Moscow = 10:30 UTC all year, no DST. The average-key-rate forecast is for a "
              "CALENDAR-YEAR AVERAGE and reading it as end-of-period is arithmetically wrong"),
    source_class(
        "ru_minfin", "Ministry of Finance and the budget rule", layer="official",
        roots=("https://minfin.gov.ru/ru/perfomance/nationalwealthfund/",
               "https://minfin.gov.ru/ru/press-center/"),
        queries=("бюджетное правило", "базовые нефтегазовые доходы", "покупка валюты",
                 "продажа валюты", "операции с иностранной валютой", "ФНБ",
                 "Фонд национального благосостояния", "нефтегазовые доходы", "аукцион ОФЗ"),
        languages=("ru",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the only sovereign FX order in this department published IN ADVANCE with a size "
              "and a date; the announcement DATE moves with the business-day calendar"),
    source_class(
        "ru_rosstat_fts", "Rosstat and the Federal Tax Service", layer="official",
        roots=("https://rosstat.gov.ru/statistics/price", "https://rosstat.gov.ru/",
               "https://www.nalog.gov.ru/"),
        queries=("недельная инфляция", "индекс потребительских цен", "ИПЦ",
                 "промышленное производство", "единый налоговый платёж", "ЕНП", "НДПИ",
                 "налоговый период", "28-е число"),
        languages=("ru",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the WEEKLY CPI is a partial-basket estimate that does not aggregate to the monthly "
              "figure; treating the two as one series is a common and material error"),
    source_class(
        "ru_customs", "Federal Customs Service trade statistics", layer="official",
        roots=("https://customs.gov.ru/statistic",),
        queries=("таможенная статистика", "экспорт", "импорт", "товарная структура",
                 "внешняя торговля"),
        languages=("ru",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PUBLICATION WAS SUSPENDED for extended periods after 2022 and resumed partially. "
              "An absent month is UNMEASURED, never a zero, and the gap is information about the "
              "disclosure regime rather than about trade"),
    source_class(
        "ru_sanctions", "OFAC, EU and UK designation lists and general licences",
        layer="official",
        roots=("https://ofac.treasury.gov/sanctions-list-service",
               "https://www.sanctionsmap.eu/",
               "https://www.gov.uk/government/collections/uk-sanctions-list"),
        queries=("designation", "general licence", "wind-down period", "price cap",
                 "SDN list", "блокирующие санкции", "потолок цен", "вторичные санкции"),
        languages=("en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (government data)",
        notes="SANCTIONS ARE OFFICIAL PUBLIC DATA AND ARE USED AS DATA. These lists carry exact "
              "dates and are the best available record of WHEN a channel closed -- the 12 June "
              "2024 exchange designation that ended dollar trading on MOEX is a dated row here, "
              "and RU-G's series break is read off it"),
    source_class(
        "ru_moex", "Moscow Exchange, NSD and SPIMEX", layer="institutional",
        roots=("https://www.moex.com", "https://www.nsd.ru/", "https://spimex.com"),
        queries=("МосБиржа", "НКЦ", "торги долларом", "юань рубль", "CNYRUB", "объём торгов",
                 "открытый интерес", "структура участников", "физические лица",
                 "нерезиденты", "срочный рынок", "фьючерс Si", "фьючерс RTS"),
        languages=("ru", "en"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="exchange data; the desk holds NO licence and seeks none",
        notes="MOEX publishes an unusually detailed participant split -- retail versus "
              "institutional, resident versus non-resident -- and it is THE BEST POSITIONING DATA "
              "IN THE COUNTRY. The desk does not have it. Registered so the gap is visible and "
              "named rather than silently absent"),
    source_class(
        "ru_naufor_acra", "NAUFOR, ACRA and Expert RA", layer="institutional",
        roots=("https://naufor.ru/", "https://www.acra-ratings.ru/", "https://raexpert.ru/"),
        queries=("НАУФОР", "саморегулируемая организация", "брокеры", "количество клиентов",
                 "рейтинговое агентство", "АКРА", "Эксперт РА", "кредитный рейтинг"),
        languages=("ru",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="NAUFOR publishes brokerage industry aggregates -- client counts, account activity "
              "-- which is the closest public read on the size of the retail base that dominates "
              "the domestic market after 2022"),
    source_class(
        "ru_multilateral", "IMF, World Bank and BIS Russia coverage", layer="institutional",
        roots=("https://www.imf.org/en/Countries/RUS", "https://www.bis.org/statistics/"),
        queries=("Article IV", "external sector", "reserve adequacy", "FX turnover",
                 "triennial survey"),
        languages=("en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="IMF engagement has been curtailed since 2022, so the recent series is THINNER than "
              "the historical one -- an absence that is itself dated and is not a data problem"),
    source_class(
        "ru_cbr_research", "Bank of Russia working papers and analytical notes",
        layer="academic",
        roots=("https://www.cbr.ru/analytics/dkp/", "https://www.cbr.ru/ec_research/"),
        queries=("серия докладов об экономических исследованиях", "аналитическая записка",
                 "трансмиссионный механизм", "бюджетное правило", "валютный курс",
                 "инфляционные ожидания", "эффект переноса"),
        languages=("ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CBR is unusually explicit in print about the budget rule's mechanics and the "
              "exchange-rate pass-through; these papers are the best free description of RU-C"),
    source_class(
        "ru_academic", "HSE, RANEPA, CyberLeninka and eLibrary", layer="academic",
        roots=("https://www.hse.ru/", "https://www.ranepa.ru/", "https://cyberleninka.ru/",
               "https://www.elibrary.ru/"),
        queries=("ВШЭ", "РАНХиГС", "КиберЛенинка", "РИНЦ", "валютный рынок",
                 "алгоритмическая торговля", "микроструктура рынка", "волатильность рубля",
                 "налоговый период и курс рубля"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free reading; bulk download restricted",
        notes="CyberLeninka is a free full-text Russian academic archive and is where the "
              "domestic literature on the tax-period FX seasonal actually lives -- a mechanism "
              "RU-D tests and Western literature has essentially never examined"),
    source_class(
        "ru_habr", "Habr finance and algorithmic-trading hubs", layer="practitioner",
        roots=("https://habr.com/ru/hubs/finance/", "https://habr.com/ru/hubs/algorithms/"),
        queries=("Habr", "хабр", "алготрейдинг", "торговый робот", "бэктест",
                 "тестирование стратегии", "коннектор к брокеру", "API брокера",
                 "машинное обучение в трейдинге", "QUIK", "стакан"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED",
        licence="public with terms; attribution required, bulk extraction restricted",
        notes="Habr is where Russian engineers write up how they CONNECTED to a broker, parsed "
              "the order book and backtested an idea. It is an implementation-level source: the "
              "claims are unverified but the plumbing descriptions are accurate and are how the "
              "desk learns what a domestic participant can actually see"),
    source_class(
        "ru_broker_research", "Finam, BCS, Otkritie and the Telegram analyst channels",
        layer="practitioner",
        roots=("https://www.finam.ru/analysis/", "https://bcs-express.ru/",
               "https://t.me/s/"),
        queries=("аналитика", "прогноз по рублю", "целевая цена", "идея дня",
                 "налоговый период поддержит рубль", "экспортёры продают валюту",
                 "MMI", "Холодный расчет", "макро телеграм"),
        languages=("ru",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="public channels and pages; automated extraction restricted",
        notes="THE TAX-PERIOD CLAIM LIVES HERE. 'Налоговый период поддержит рубль' is repeated "
              "every month by broker desks and Telegram macro channels; it is a dated, "
              "falsifiable mechanism claim and RU-D exists to test it rather than to believe it. "
              "NARRATIVE_FEATURE: useful as a conditioning variable even where the claims do not "
              "forecast"),
    source_class(
        "ru_smartlab", "smart-lab.ru", layer="retail_ecology",
        roots=("https://smart-lab.ru/", "https://smart-lab.ru/blog/",
               "https://smart-lab.ru/forum/"),
        queries=("смартлаб", "smart-lab", "плечо", "маржинколл", "слил депозит",
                 "разгон депозита", "шорт", "лонг", "стакан", "скальпинг", "арбитраж",
                 "алготрейдинг", "робот", "советник", "ЛЧИ", "Лучший частный инвестор"),
        languages=("ru",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public forum; automated extraction restricted",
        notes="THE DEEPEST RETAIL-QUANT FORUM IN THE LANGUAGE and a genuine seed source: traders "
              "post equity curves, robot logic and post-mortems. KEPT AT LOW WEIGHT, NEVER "
              "DROPPED -- most of it is survivorship and self-promotion, and the minority that is "
              "a dated mechanism claim is worth more than most sell-side research"),
    source_class(
        "ru_lchi", "ЛЧИ, the exchange's public trading competition", layer="retail_ecology",
        roots=("https://investor.moex.com/", "https://smart-lab.ru/lchi/"),
        queries=("ЛЧИ", "Лучший частный инвестор", "конкурс трейдеров", "доходность участника",
                 "эквити участника", "сделки участников", "номинация"),
        languages=("ru",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public results pages; automated extraction restricted",
        notes="AN EXCHANGE-RUN COMPETITION THAT PUBLISHES PARTICIPANT RESULTS. Almost nowhere "
              "else in this department does a venue publish per-trader outcomes. The survivorship "
              "is extreme -- only the winners are visible -- which is exactly why it is FRINGE-"
              "adjacent evidence about strategy families rather than about returns"),
    source_class(
        "ru_retail_forums", "banki.ru, mfd.ru and the broker communities", layer="retail_ecology",
        roots=("https://www.banki.ru/forum/", "https://forum.mfd.ru/forum/",
               "https://www.tbank.ru/invest/social/"),
        queries=("банки.ру форум", "mfd.ru", "Пульс", "Т-Инвестиции", "вклад под",
                 "ставка по вкладу", "валютный контроль", "перевод за границу",
                 "как купить валюту", "счёт типа С"),
        languages=("ru",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public forums; automated extraction restricted",
        notes="where household currency substitution is discussed in real time. RU's household "
              "channel is a monthly statistic officially and a daily conversation here; low "
              "weight, never zero"),
    source_class(
        "ru_quik_metatrader", "QUIK, the MetaTrader Russian ecosystem and the code bases",
        layer="app_ecosystem",
        roots=("https://arqatech.com/ru/products/quik/", "https://www.mql5.com/ru/code",
               "https://www.mql5.com/ru/forum", "https://www.mql5.com/ru/market"),
        queries=("QUIK", "КВИК", "LUA скрипт", "QLua", "советник", "эксперт", "MQL4", "MQL5",
                 "кодобаза", "тестер стратегий", "оптимизация", "проскальзывание",
                 "торговый робот", "индикатор", "стакан заявок", "мультивалютный советник"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms; the desk already mines MQL5",
        notes="QUIK is the dominant DOMESTIC terminal and its LUA scripting layer is a parallel "
              "ecosystem to MetaTrader's, with its own code bases and its own idioms. The "
              "MetaTrader Russian-language sections are older and larger than the English ones "
              "and are where the MT4-era robot culture actually lives"),
    source_class(
        "ru_algo_frameworks", "StockSharp, TSLab, Wealth-Lab and the Russian algo frameworks",
        layer="app_ecosystem",
        roots=("https://github.com/StockSharp/StockSharp", "https://tslab.pro/",
               "https://stocksharp.ru/"),
        queries=("StockSharp", "S#", "TSLab", "Wealth-Lab", "алготрейдинг",
                 "коннектор", "бэктестер", "HFT", "арбитраж", "скальпинг",
                 "исходный код робота", "фреймворк для трейдинга"),
        languages=("ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED",
        licence="per-repository licences; check each before reading, NEVER vendor code",
        notes="StockSharp is a large Russian open-source trading framework on GitHub; its issue "
              "tracker and connector list are a direct map of WHICH VENUES AND BROKERS domestic "
              "algorithmic traders actually reach, which no official source publishes"),
    source_class(
        "ru_autofollow", "Автоследование platforms and broker trading APIs",
        layer="app_ecosystem",
        roots=("https://www.comon.ru/", "https://fintarget.ru/",
               "https://www.tbank.ru/invest/open-api/"),
        queries=("автоследование", "автоследование стратегия", "подписчики стратегии",
                 "Comon", "Fintarget", "копирование сделок", "Tinkoff Invest API",
                 "API брокера", "торговый API", "песочница API"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public product pages; subscriber and performance data under site terms",
        notes="АВТОСЛЕДОВАНИЕ IS A REGULATED RUSSIAN BROKERAGE PRODUCT with no close Western "
              "analogue: retail subscribes to a strategy and the broker mirrors its trades into "
              "the subscriber's account. Published strategy track records and SUBSCRIBER COUNTS "
              "are a rare public measure of how crowded a retail strategy family is -- the "
              "closest thing Russia has to a positioning series the desk can lawfully see"),
    source_class(
        "ru_press", "RBC, Vedomosti, Interfax and Kommersant", layer="media",
        roots=("https://www.rbc.ru/finances/", "https://www.vedomosti.ru/finance",
               "https://www.interfax.ru/business", "https://www.kommersant.ru/finance"),
        queries=("ключевая ставка", "курс рубля", "экспортёры", "валютная выручка",
                 "обязательная продажа", "указ", "бюджетное правило", "нефтегазовые доходы",
                 "дисконт Urals"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="paywalls and site terms restrict automated extraction",
        notes="Interfax carries the fastest timestamps on policy announcements; the others carry "
              "the framing. READ AND CITED, NEVER SCRAPED. Treat the editorial line as a "
              "conditioning variable, not as evidence"),
    source_class(
        "ru_frank_media", "Frank Media and the independent financial press", layer="media",
        roots=("https://frankmedia.ru/", "https://www.forbes.ru/finansy"),
        queries=("банковский сектор", "отток вкладов", "нормативы", "санкции на банк",
                 "платежи через", "корреспондентские отношения"),
        languages=("ru",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public web; automated extraction restricted",
        notes="the banking-sector reporting that the official statistics stopped carrying after "
              "2022; genuinely additive and genuinely contested, hence its own row"),
    source_class(
        "ru_wayback", "Internet Archive captures of cbr.ru, moex.com and customs.gov.ru",
        layer="archive",
        roots=("https://web.archive.org/web/*/cbr.ru*",
               "https://web.archive.org/web/*/moex.com*",
               "https://web.archive.org/web/*/customs.gov.ru*"),
        queries=("архив страницы", "первоначальная публикация", "удалённая статистика",
                 "снятая публикация", "изменение методики"),
        languages=("ru", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="INDISPENSABLE HERE AND NOWHERE ELSE IN THIS DEPARTMENT TO THE SAME DEGREE. Russian "
              "statistical publication has been suspended, narrowed and re-scoped repeatedly "
              "since 2022, and the Wayback capture is often the only surviving record that a "
              "series existed, what it said, and on what date it stopped"),
    source_class(
        "ru_libraries", "Russian State Library and the newspaper archives", layer="archive",
        roots=("https://www.rsl.ru/", "https://www.kommersant.ru/archive"),
        queries=("архив", "исторические данные", "дефолт 1998", "деноминация",
                 "валютный коридор", "либерализация"),
        languages=("ru",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public archive; reading rooms and site terms govern reuse",
        notes="the 1998 default and the 2014 float are the two episodes every Russian market "
              "participant reasons from, and the contemporaneous record is the only way to read "
              "them as they were read at the time"),
    source_class(
        "ru_energy_physical", "Pipeline flows, CPC and tanker tracking", layer="physical_economy",
        roots=("https://transparency.entsog.eu/", "https://www.cpc.ru/en/press/news/",
               "https://www.marinetraffic.com/"),
        queries=("прокачка газа", "транзит", "КТК", "отгрузка", "Новороссийск", "Приморск",
                 "Усть-Луга", "танкер", "теневой флот", "фрахт", "дисконт"),
        languages=("ru", "en"), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="ENTSOG and CPC are OPEN_DATA; AIS history and cargo-level tracking are LICENSED "
                "and not held",
        notes="the physical half of RU-F and RU-J. ENTSOG publishes European pipeline entry "
              "flows free and daily, which is the best available read on the gas channel. Cargo-"
              "level tanker tracking would price the Urals discount directly and is LICENSED -- "
              "a NAMED GAP, not an omission"),
    source_class(
        "ru_power_industry", "System Operator electricity load and Rosstat industrial output",
        layer="physical_economy",
        roots=("https://www.so-ups.ru/functioning/ups/ups-indicators/",
               "https://rosstat.gov.ru/enterprise_industrial"),
        queries=("энергопотребление", "потребление электроэнергии", "ЕЭС России",
                 "суточный график", "промышленное производство", "грузооборот",
                 "погрузка на сети РЖД"),
        languages=("ru",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="DAILY NATIONAL ELECTRICITY CONSUMPTION, PUBLISHED FREE. In an economy whose "
              "official statistics have narrowed, a daily physical activity series that nobody "
              "has an incentive to massage is worth more than a monthly index. Railway loadings "
              "are the second such series"),
    source_class(
        "ru_agri_physical", "Wheat export duty, port line-ups and the grain union",
        layer="physical_economy",
        roots=("https://mcx.gov.ru/", "https://rusgrain.org/"),
        queries=("экспортная пошлина на пшеницу", "индикативная цена", "квота на экспорт",
                 "отгрузки зерна", "рейд", "малый флот", "Новороссийск зерно",
                 "Зерновой союз"),
        languages=("ru",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the floating duty is published WEEKLY with a formula and an EFFECTIVE DATE several "
              "days ahead -- an announcement-to-effective gap that is rare and is RU-I's object"),
    source_class(
        "ru_citation_graph", "CyberLeninka, eLibrary and OpenAlex citation graphs",
        layer="source_graph",
        roots=("https://cyberleninka.ru/", "https://openalex.org/",
               "https://www.elibrary.ru/"),
        queries=("цитирование", "список литературы", "индекс Хирша", "РИНЦ",
                 "кто цитирует", "воспроизводимость"),
        languages=("ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free reading; bulk extraction restricted",
        notes="the Russian domestic literature is largely invisible in Western citation graphs, "
              "so the RINTs/CyberLeninka graph is the only way to see whether a domestic claim "
              "about, say, the tax-period seasonal has been replicated or merely repeated"),
    source_class(
        "ru_code_graph", "GitHub forks and dependencies across the Russian algo ecosystem",
        layer="source_graph",
        roots=("https://github.com/StockSharp/StockSharp/network/members",
               "https://github.com/search?q=quik+lua", "https://gitflic.ru/"),
        queries=("StockSharp форк", "quik lua", "коннектор к QUIK", "tinkoff invest api python",
                 "moex api", "зависимости", "форки"),
        languages=("ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="per-repository; check each, never vendor code",
        notes="which connectors exist and which are maintained is a direct map of which VENUES "
              "and BROKERS domestic algorithmic traders can still reach after each enforcement "
              "round -- an access measurement that no official source publishes"),
    source_class(
        "ru_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en", "ru"), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="the edge set between this pack's sources and the desk's existing corpus"),
)

#: All ten layers are populated. Russia is the DEEPEST native-language ground in this department
#: -- a large retail-quant forum culture, two parallel terminal ecosystems, a regulated
#: copy-trading product and an exchange that runs a public trading competition -- and every one
#: of those is invisible to an English-language search.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CBR key rate decisions (ключевая ставка)", "source": "Bank of Russia",
     "coverage": "2013 onward (the key rate replaced the refinancing rate in September 2013)",
     "frequency": "8 scheduled per year plus off-cycle", "publication_lag_days": 0.0,
     "revisions": "never revised", "licence": "free, public", "history_from": "2013-09",
     "pit_feasible": True, "assets": ("USDRUB", "USDCNH"),
     "fields": ("decision_date", "key_rate_pct", "change_bp", "core_meeting_flag",
                "statement_text_ru"),
     "pit_fields": ("release_ts_utc", "scheduled_flag"),
     "mechanism_families": ("event_reaction", "policy_surprise"),
     "how_to_fetch": "cbr.ru/press/keypr/ -- 13:30 Moscow = 10:30 UTC all year, no DST"},
    {"name": "CBR average-key-rate forecast (Доклад о ДКП)", "source": "Bank of Russia",
     "coverage": "2021 onward", "frequency": "quarterly (the four core meetings)",
     "publication_lag_days": 0.0, "revisions": "each report supersedes the last",
     "licence": "free, public", "history_from": "2021-04", "pit_feasible": True,
     "assets": ("USDRUB", "USDCNH"),
     "fields": ("report_date", "year", "avg_key_rate_low", "avg_key_rate_high", "cpi_forecast",
                "gdp_forecast", "current_account_forecast"),
     "pit_fields": ("release_ts_utc", "vintage", "prior_vintage_ref"),
     "mechanism_families": ("forecast_revision", "policy_surprise"),
     "how_to_fetch": "cbr.ru/dkp/ -- NOTE the forecast is for the AVERAGE rate over a calendar "
                     "year, not an end-of-period rate; treating it as end-of-period is "
                     "arithmetically wrong and the error grows through the year"},
    {"name": "Minfin budget-rule FX operations announcement", "source": "Ministry of Finance",
     "coverage": "2017 onward, with a suspension in 2022", "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "not revised; occasionally amended mid-period",
     "licence": "free, public", "history_from": "2017-02", "pit_feasible": True,
     "assets": ("USDRUB", "USDCNH"),
     "fields": ("announcement_date", "period_start", "period_end", "amount_rub_per_day",
                "direction", "currency"),
     "pit_fields": ("announcement_ts_utc", "period_start"),
     "mechanism_families": ("institutional_flow", "sovereign_flow"),
     "how_to_fetch": "minfin.gov.ru press centre; operations run the 7th to the 6th and the "
                     "announcement lands on or about the third business day"},
    {"name": "CBR mirroring operations for the National Wealth Fund", "source": "Bank of Russia",
     "coverage": "2023 onward", "frequency": "announced in blocks, executed daily",
     "publication_lag_days": 0.0, "revisions": "not revised", "licence": "free, public",
     "history_from": "2023-01", "pit_feasible": True, "assets": ("USDRUB", "USDCNH"),
     "fields": ("announcement_date", "period", "daily_amount_rub", "direction"),
     "pit_fields": ("announcement_ts_utc",),
     "mechanism_families": ("sovereign_flow",),
     "how_to_fetch": "cbr.ru press releases. THE NET SOVEREIGN FLOW IS THIS PLUS THE BUDGET RULE; "
                     "using only one understates it, sometimes by more than the one used"},
    {"name": "Rosstat weekly and monthly consumer price index", "source": "Rosstat",
     "coverage": "1991 onward", "frequency": "weekly and monthly",
     "publication_lag_days": 3.0,
     "revisions": "the weekly series is a PARTIAL-BASKET estimate and does not aggregate to the "
                  "monthly figure; the monthly figure is revised",
     "licence": "free, public", "history_from": "1991-01", "pit_feasible": True,
     "assets": ("USDRUB",),
     "fields": ("reference_period", "cpi_wow", "cpi_mom", "cpi_yoy", "food", "non_food",
                "services"),
     "pit_fields": ("release_ts_utc", "vintage", "basket_version"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "rosstat.gov.ru price statistics; the weekly print lands Wednesday evening "
                     "Moscow and is the highest-frequency inflation series in this department"},
    {"name": "CBR balance of payments and reserve composition", "source": "Bank of Russia",
     "coverage": "1994 onward", "frequency": "monthly estimate, quarterly final",
     "publication_lag_days": 10.0,
     "revisions": "the monthly estimate is revised materially in the quarterly figure",
     "licence": "free, public", "history_from": "1994-01", "pit_feasible": True,
     "assets": ("USDRUB", "XAUUSD", "USDCNH"),
     "fields": ("period", "current_account", "trade_balance", "financial_account",
                "reserves_total", "gold_tonnes", "gold_share_pct"),
     "pit_fields": ("release_ts_utc", "vintage", "estimate_flag"),
     "mechanism_families": ("macro_condition", "sovereign_flow"),
     "how_to_fetch": "cbr.ru/statistics/macro_itm/svs/"},
    {"name": "Minfin oil-and-gas budget revenue and the Urals reference price",
     "source": "Ministry of Finance", "coverage": "2017 onward", "frequency": "monthly",
     "publication_lag_days": 3.0, "revisions": "not revised", "licence": "free, public",
     "history_from": "2017-01", "pit_feasible": True, "assets": ("XBRUSD", "USDRUB"),
     "fields": ("month", "oil_gas_revenue_rub", "base_revenue_rub", "urals_avg_usd",
                "met_rate", "export_duty"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("terms_of_trade", "sovereign_flow"),
     "how_to_fetch": "minfin.gov.ru monthly releases. THE FISCAL FORMULA REFERENCES A MONTHLY "
                     "AVERAGE Urals price, so the fiscal transmission runs through an average and "
                     "not through a spot print -- a spot-anchored study measures the wrong object"},
    {"name": "Russian wheat export duty and quota", "source": "Ministry of Agriculture",
     "coverage": "2021 onward", "frequency": "weekly duty, seasonal quota",
     "publication_lag_days": 0.0, "revisions": "not revised", "licence": "free, public",
     "history_from": "2021-06", "pit_feasible": True, "assets": ("WHEAT", "CORN"),
     "fields": ("effective_week", "duty_rub_per_tonne", "indicative_price_usd", "quota_tonnes"),
     "pit_fields": ("publish_ts_utc", "effective_week"),
     "mechanism_families": ("supply_shock", "policy_shock"),
     "how_to_fetch": "the floating duty is published weekly with a formula and an effective date "
                     "several days ahead; the ANNOUNCEMENT and the EFFECTIVE date are two events"},
    {"name": "MOEX market data (IMOEX, RTS, CNY/RUB, OFZ)", "source": "Moscow Exchange",
     "coverage": "n/a to this desk", "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "n/a", "licence": "exchange data; NO LICENCE HELD", "history_from": "",
     "pit_feasible": False, "assets": (),
     "fields": (), "pit_fields": (),
     "mechanism_families": ("transmission_target",),
     "how_to_fetch": "NOT FETCHED. Named so the gap is explicit: every MOEX-dependent observable "
                     "in this pack is UNMEASURED on this box and is declared so per domain"},
    {"name": "Desk MT5 USDRUB tape", "source": "the desk's own Fusion tape",
     "coverage": "2020-09-14 to 2026-09-16, 19,484 H1 bars",
     "frequency": "hourly", "publication_lag_days": 0.0, "revisions": "append-only",
     "licence": "desk-owned", "history_from": "2020-09", "pit_feasible": True,
     "assets": ("USDRUB",),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time", "spread"),
     "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/USDRUB_H1.parquet. MEASURED 2026-09-17: median "
                     "spread over the last 60 days 137,509 points (~164bp) against 453 points "
                     "(~6bp) in 2021, and 30.6% of recent bars FROZEN (o=h=l=c). The `spread` "
                     "column must be read on every bar and a frozen bar excluded, or a "
                     "mean-reversion study will find the broker's stale quote"},
    {"name": "Desk MT5 EURRUB tape", "source": "the desk's own Fusion tape",
     "coverage": "2017-10-31 to 2022-02-28, 15,199 H1 bars, NOTHING AFTER",
     "frequency": "hourly", "publication_lag_days": 0.0, "revisions": "append-only",
     "licence": "desk-owned", "history_from": "2017-10", "pit_feasible": True, "assets": (),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",),
     "mechanism_families": ("transmission_target",),
     "how_to_fetch": "desks/mt5/data/universe/EURRUB_H1.parquet. THE TAPE STOPS ON THE DAY THE "
                     "MODERN REGIME BEGINS. EURRUB is a transmission target in this pack and no "
                     "cell may be compiled against it"},
    {"name": "Desk MT5 commodity tape (Brent, gas, palladium, nickel, aluminium, wheat)",
     "source": "the desk's own Fusion tape", "coverage": "2018 onward",
     "frequency": "tick to daily",
     "publication_lag_days": 0.0, "revisions": "append-only", "licence": "desk-owned",
     "history_from": "2018-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XNGUSD", "XPDUSD", "XNIUSD", "XALUSD", "WHEAT"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet -- THIS is where Russian "
                     "mechanisms are actually tradeable on this box"},
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "Bank of Russia Board of Directors (Совет директоров Банка России)",
        "holds": "the key rate, a +/-100bp standing-facility corridor, the official exchange rate "
                 "methodology, and reserves whose composition shifted sharply toward gold and "
                 "renminbi after 2022",
        "forced_to": ("decide at eight scheduled Friday meetings a year and publish at 13:30 "
                      "Moscow",
                      "publish an average-key-rate forecast range at the four core meetings",
                      "set and publish an official rate every business day, effective the NEXT "
                      "calendar day"),
        "when": "13:30 Moscow = 10:30 UTC ALL YEAR -- Russia abolished seasonal clock changes in "
                "2014, so the event minute in UTC never moves",
        "information": ("weekly inflation before the market sees the monthly figure",
                        "the banking system's liquidity position, which it operates",
                        "bank-level FX flow through the reporting it mandates"),
        "constraints": ("a 4% point inflation target",
                        "a capital account that is administratively, not monetarily, controlled",
                        "the rate is the ONLY instrument that still works on the exchange rate "
                        "once the capital account is closed, which makes it blunter and larger"),
        "instruments": ("USDRUB", "USDCNH", "XAUUSD"),
        "counterparties": ("the domestic banking system",
                           "Minfin, whose budget-rule operations it executes and mirrors",
                           "exporters, through the surrender rules it administers"),
        "observables": ("the key rate press release at 10:30 UTC",
                        "the average-key-rate forecast range and its revision",
                        "the official rate and its next-day effective date",
                        "the CBR macro survey of professional forecasters"),
        "impact": "in a closed capital account the rate transmits to the currency through the "
                  "CARRY on domestic deposits and through import demand, not through portfolio "
                  "flow -- a slower and more nonlinear channel than in an open economy",
        "persistence": "the level lasts to the next meeting; the reaction FUNCTION changed "
                       "completely in 2022 when capital controls replaced the exchange rate as "
                       "the adjustment variable, and a pooled estimate spans two different regimes",
        "falsifier": "the same event-window statistic on the eight nearest non-meeting Fridays. "
                     "A move that survives there is a Friday effect, not the CBR",
        "notes": "the desk's USDRUB quote is an OFFSHORE print; the rate decision moves the "
                 "domestic market first and the offshore quote follows with a basis, so an "
                 "event study on this tape is measuring the basis as well as the reaction",
    },
    {
        "name": "Ministry of Finance under the budget rule (Минфин, бюджетное правило)",
        "holds": "the federal budget, the National Wealth Fund, and an FX operation obligation "
                 "defined by a formula rather than by discretion",
        "forced_to": ("buy foreign currency when oil-and-gas revenue exceeds the base figure and "
                      "SELL it when revenue falls short -- the sign is arithmetic, not a view",
                      "announce the amount, in roubles per day, on or about the third business "
                      "day of each month",
                      "execute daily from the 7th of the month to the 6th of the next"),
        "when": "the announcement on or about the third business day; operations from the 7th to "
                "the 6th of the following month",
        "information": ("actual oil-and-gas receipts before they are published",
                        "the Urals reference price used in the formula"),
        "constraints": ("the budget rule's formula and the base revenue figure set in the budget "
                        "law",
                        "the currency it may transact: since 2023 the renminbi, not the dollar",
                        "the liquid part of the National Wealth Fund, which caps the sell side"),
        "instruments": ("USDRUB", "USDCNH"),
        "counterparties": ("the Bank of Russia, which executes and mirrors the operations",
                           "the domestic FX market's remaining participants"),
        "observables": ("the monthly announcement with its amount and direction",
                        "the CBR's mirroring announcement, which must be ADDED to it",
                        "monthly oil-and-gas revenue against the base figure"),
        "impact": "an announced, sized, dated sovereign FX order. It is the most transparent "
                  "official flow in this department and the closest thing the desk has to a known "
                  "future order book",
        "persistence": "structural since 2017, SUSPENDED through much of 2022, and resumed with a "
                       "different currency and a different base; three regimes in eight years and "
                       "a pooled estimate describes none of them",
        "falsifier": "months where the announced amount is near zero. No order, so no effect -- "
                     "and an effect that persists there was never the budget rule",
        "notes": "the announcement DATE moves with the business-day calendar; anchoring to a "
                 "fixed calendar day mis-times roughly a third of the sample",
    },
    {
        "name": "Russian exporters meeting the monthly tax date (экспортёры, налоговый период)",
        "holds": "foreign-currency export receipts against rouble tax liabilities",
        "forced_to": ("convert foreign currency to roubles to pay the unified tax payment and the "
                      "mineral extraction tax on the 28th -- a legal obligation with a date",
                      "sell in size in the days immediately before, because the payment cannot "
                      "slip"),
        "when": "the five business days before the 28th of each month, since 1 January 2023. "
                "Before that the obligations were staggered across the 25th to the 28th and the "
                "window was WIDER and EARLIER",
        "information": ("their own liability, which they know a month ahead"),
        "constraints": ("the Tax Code's payment dates, which are not negotiable",
                        "the mineral extraction tax formula, which references a monthly average "
                        "Urals price and is therefore known before the payment date",
                        "whatever surrender requirement is in force at the time"),
        "instruments": ("USDRUB", "USDCNH"),
        "counterparties": ("the Federal Tax Service",
                           "the domestic banks that intermediate the conversion"),
        "observables": ("the calendar itself, which is the cleanest observable in this pack",
                        "monthly oil-and-gas revenue, which sizes the liability",
                        "the Urals monthly average, which enters the tax formula"),
        "impact": "a structural rouble bid concentrated in a five-day window each month; it is "
                  "the most-cited Russian FX seasonal and the easiest to test because the date is "
                  "known in advance and never moves",
        "persistence": "structural while the tax calendar stands; the WINDOW moved on 1 January "
                       "2023 when the unified payment date replaced the staggered schedule, and "
                       "that is a hard break in the seasonal",
        "falsifier": "the same day-of-month statistic on USDCNH and on other EM currencies with "
                     "no such tax date. A 25th-to-28th effect present in all of them is a "
                     "month-end effect and not a Russian tax effect",
        "notes": "this is the domain where a generic month-end study will find the right number "
                 "for the wrong reason; RU-D conditions on the tax rule explicitly",
    },
    {
        "name": "Exporters under the mandatory FX surrender decree (обязательная продажа)",
        "holds": "foreign-currency revenue subject to repatriation and sale requirements set by "
                 "presidential decree",
        "forced_to": ("repatriate a set share of export revenue and SELL a set share of what is "
                      "repatriated, on a timetable the decree specifies",
                      "comply whatever the level of the exchange rate"),
        "when": "continuous while a decree is in force; the thresholds have changed several times "
                "since October 2023",
        "information": ("their own receipts and the timing of their repatriation"),
        "constraints": ("the decree itself, which names the obligated groups",
                        "counter-sanctions and payment-channel friction, which can make "
                        "repatriation physically slow even when it is legally required",
                        "the availability of a convertible channel for the currency received"),
        "instruments": ("USDRUB", "USDCNH"),
        "counterparties": ("the domestic FX market",
                           "the authorities monitoring compliance"),
        "observables": ("the decree text and its amendments, which are published",
                        "CBR data on net FX sales by the largest exporters, published monthly",
                        "the current-account surplus, which bounds the flow"),
        "impact": "a rouble bid that exists because a decree says so; its SIZE steps when the "
                  "decree steps, which makes it a policy shock rather than a price response",
        "persistence": "entirely policy-dependent. Each amendment is a structural break, and "
                       "there have been several -- an effect fitted across them is fitted to an "
                       "average of different rules",
        "falsifier": "the same statistic in the months before October 2023, when no such "
                     "requirement was in force. An effect present there cannot be this mechanism",
        "notes": "CBR publishes monthly net FX sales by the largest exporters, which is the "
                 "actor's own ledger and the right control for any claimed surrender effect",
    },
    {
        "name": "Russian crude exporters and the Urals discount (Urals, дисконт)",
        "holds": "crude sold at an assessed price that is Brent MINUS a discount, with a separate "
                 "eastern grade (ESPO) carrying a different discount",
        "forced_to": ("sell into whatever channel remains open, at whatever discount it demands",
                      "pay mineral extraction tax on a formula referencing a published MONTHLY "
                      "AVERAGE price, whatever the spot price does afterwards"),
        "when": "continuous shipment; the fiscal consequence lands on the 28th and the price "
                "reference is a monthly average",
        "information": ("their own realised prices and freight costs before assessment"),
        "constraints": ("the price cap regime on crude from 5 December 2022 and on products from "
                        "5 February 2023",
                        "shipping, insurance and payment channel availability, which is the real "
                        "binding constraint rather than demand",
                        "the mineral extraction tax formula, which is legislated"),
        "instruments": ("XBRUSD", "XTIUSD", "USDRUB"),
        "counterparties": ("Indian, Chinese and Turkish refiners",
                           "the shipping and insurance market"),
        "observables": ("the Urals-Brent discount as assessed",
                        "the Minfin monthly Urals reference price used in the tax formula",
                        "seaborne export volumes from tracking services"),
        "impact": "the DISCOUNT, not the Brent price, determines Russian export revenue. The "
                  "discount moved from roughly $2 to more than $30 and back, so a period in which "
                  "Brent rose and Russian revenue fell is not a contradiction -- it is the "
                  "discount doing the work",
        "persistence": "the discount is a function of sanctions enforcement and freight, and it "
                       "steps with policy rather than drifting with price; it is the least "
                       "mean-reverting series in this pack",
        "falsifier": "regress Russian fiscal oil revenue on Brent alone and on Brent-minus-"
                     "discount. If the discount term is not separately significant, the whole "
                     "mechanism is Brent and this actor adds nothing",
        "notes": "treating XBRUSD as the Russian export price is the single largest modelling "
                 "error available in this pack",
    },
    {
        "name": "Nornickel and the palladium and nickel supply concentration",
        "holds": "roughly 40% of world palladium supply and a large share of high-grade nickel, "
                 "from a small number of Arctic sites with a single logistics corridor",
        "forced_to": ("ship through a constrained Arctic route with a seasonal window",
                      "meet long-term supply contracts from concentrated production"),
        "when": "continuous production; the logistics window and the maintenance calendar are "
                "seasonal; guidance is published with results",
        "information": ("its own production and logistics status before anyone else"),
        "constraints": ("physical concentration of the orebody, which cannot be diversified",
                        "Arctic logistics and the shipping season",
                        "environmental and safety incidents, which have repeatedly taken capacity "
                        "offline without notice"),
        "instruments": ("XPDUSD", "XPTUSD", "XNIUSD", "XCUUSD"),
        "counterparties": ("global autocatalyst manufacturers",
                           "stainless steel and battery producers"),
        "observables": ("production guidance and quarterly output",
                        "LME and exchange inventory levels",
                        "the palladium-platinum spread, which prices substitutability"),
        "impact": "a supply event at one producer is a GLOBAL metal supply event; palladium is "
                  "the most concentrated major metal in the desk's universe and its price "
                  "responds to single-site news in a way copper never does",
        "persistence": "structural while the concentration persists; palladium demand is eroding "
                       "with vehicle electrification, so the same supply shock has a smaller price "
                       "effect each year and a pooled beta over-states the current one",
        "falsifier": "the same statistic on XCUUSD, a metal with no comparable concentration. A "
                     "shared response is a risk or dollar move and not a supply event",
        "notes": "the single name is an ACTOR only; no share CFD appears in this pack",
    },
    {
        "name": "Russian wheat exporters and the floating export duty",
        "holds": "the largest wheat export programme in the world, subject to a floating export "
                 "duty and a second-half-season quota",
        "forced_to": ("pay a duty set by a published formula against an indicative price, "
                      "recalculated weekly",
                      "ship within a seasonal quota once it binds",
                      "clear the crop, because domestic storage and domestic demand cannot absorb "
                      "it"),
        "when": "harvest from July; the export programme runs through the season; the duty is "
                "published weekly with an effective date several days ahead",
        "information": ("their own forward sales and vessel line-ups"),
        "constraints": ("the export duty formula and the quota, both administrative",
                        "port and rail capacity in the Black Sea and Azov",
                        "freight, insurance and navigation risk"),
        "instruments": ("WHEAT", "CORN"),
        "counterparties": ("Egyptian, Turkish, Algerian and other state buyers",
                           "international grain trading houses"),
        "observables": ("the weekly published duty and its indicative price",
                        "the quota level and the date it binds",
                        "seaborne export volumes"),
        "impact": "an administrative supply shock on the largest exporter; the ANNOUNCEMENT "
                  "and its EFFECTIVE date are two separate events several days apart, which is "
                  "rare enough to be worth exploiting",
        "persistence": "the duty mechanism has been in force since mid-2021 and its formula has "
                       "been amended; each amendment is a break",
        "falsifier": "the same statistic on CORN, where the Russian export share is far smaller. "
                     "A shared response is a grain-complex move and not a Russian policy event",
        "notes": "the announcement-to-effective gap is the tradeable object here, not the duty "
                 "level",
    },
    {
        "name": "Gazprom and the European gas transmission channel",
        "holds": "pipeline export capacity to Europe and Turkey whose daily flows are published "
                 "by the receiving operators",
        "forced_to": ("nominate and deliver volumes that the receiving system publishes daily",
                      "accept whatever routes remain contractually and physically available"),
        "when": "daily nominations; the European storage cycle is seasonal and its trajectory is "
                "published",
        "information": ("its own field and compressor status"),
        "constraints": ("the physical routes that remain open",
                        "transit contracts and their expiry dates",
                        "European storage fill obligations on the demand side"),
        "instruments": ("XNGUSD", "GER40", "EUSTX50"),
        "counterparties": ("European utilities and the Turkish corridor",
                           "LNG suppliers competing for the same demand"),
        "observables": ("daily pipeline flows published by the receiving operators",
                        "European storage fill percentage",
                        "transit contract expiry dates, which are known years ahead"),
        "impact": "European gas cost, and therefore European industrial margin; the equity "
                  "channel into GER40 and EUSTX50 is as real as the commodity channel and is "
                  "better measured on this box, because the desk's gas quote is a US benchmark "
                  "and not a European one",
        "persistence": "the channel shrank drastically after 2022 and continues to shrink; a beta "
                       "fitted to 2021 is not the 2026 beta and the difference is structural",
        "falsifier": "the same statistic on XTIUSD. A European equity response present for oil as "
                     "well is an energy-complex move rather than a gas-supply event",
        "notes": "XNGUSD is Henry Hub, NOT the European benchmark; that mismatch must be stated "
                 "in every cell that uses it as a European gas proxy",
    },
    {
        "name": "Russian households as a domestic FX and gold demand source",
        "holds": "rouble savings with a long history of currency substitution, and, since 2022, "
                 "an abolished VAT on investment gold",
        "forced_to": ("choose between a deposit rate and an exchange-rate expectation whenever "
                      "the rate moves sharply -- a decision forced by the rate, not by a view",
                      "hold domestically, because external channels are largely closed"),
        "when": "concentrated after large rate moves and after depreciation episodes",
        "information": ("what everyone else has; this actor is reactive"),
        "constraints": ("capital controls limiting external transfer",
                        "cash foreign currency availability, which is administratively limited",
                        "the deposit rate, which at a high key rate becomes genuinely attractive"),
        "instruments": ("USDRUB", "XAUUSD"),
        "counterparties": ("domestic banks", "domestic gold dealers"),
        "observables": ("household deposit growth and its currency split, published by CBR",
                        "domestic gold purchases by households",
                        "cash foreign currency demand statistics"),
        "impact": "a high key rate converts household savings into rouble deposits and away from "
                  "currency substitution, which is the main channel by which the rate supports "
                  "the currency in a closed capital account",
        "persistence": "the behaviour is decades old; the CHANNEL changed in 2022 when external "
                       "options closed, so the elasticity is not comparable across that date",
        "falsifier": "the same statistic in a period of low key rates. If deposit growth responds "
                     "identically, the rate is not the mechanism",
        "notes": "",
    },
    {
        "name": "Foreign holders in type-C accounts (счета типа С)",
        "holds": "Russian assets frozen in restricted rouble accounts since 2022, unable to "
                 "repatriate",
        "forced_to": ("do nothing -- the constraint is that they CANNOT transact, which is a "
                      "forcing of the most absolute kind",
                      "accept whatever conversion or exchange scheme is offered"),
        "when": "since March 2022, continuously; exchange schemes have been offered episodically",
        "information": ("none beyond the public"),
        "constraints": ("the type-C account regime itself",
                        "counter-sanction rules on disposal",
                        "any exchange scheme's terms and caps"),
        "instruments": ("USDRUB",),
        "counterparties": ("the Russian authorities administering the regime",
                           "domestic buyers in any exchange scheme"),
        "observables": ("announcements of exchange schemes and their caps",
                        "the discount at which Russian assets trade in any offshore market",
                        "the offshore-to-official USDRUB basis"),
        "impact": "the absent seller. A large potential supply that CANNOT reach the market is "
                  "why the offshore and domestic prices can diverge for years without arbitrage",
        "persistence": "unchanged since 2022; each partial exchange scheme is a discrete event "
                       "rather than a trend",
        "falsifier": "the offshore-to-official basis should NARROW around any scheme that "
                     "genuinely releases assets. If it does not, the scheme released nothing and "
                     "the mechanism is unaffected",
        "notes": "this actor is the reason the desk's USDRUB quote and the CBR official rate are "
                 "different series rather than the same series at different venues",
    },
    {
        "name": "Rosstat as the publisher of the weekly inflation print",
        "holds": "a weekly partial-basket consumer price estimate published every Wednesday, "
                 "which almost no other country produces",
        "forced_to": ("publish weekly on a fixed schedule",
                      "publish a monthly figure that does NOT aggregate from the weekly series, "
                      "because the baskets differ"),
        "when": "Wednesday evening Moscow for the weekly print; mid-month for the monthly figure",
        "information": ("the collected prices before publication"),
        "constraints": ("the Federal Statistics Law and the published schedule",
                        "a weekly basket that is narrower than the monthly one by construction"),
        "instruments": ("USDRUB",),
        "counterparties": ("the whole market, and the CBR, which watches it closely"),
        "observables": ("the weekly week-on-week print",
                        "the monthly figure and the gap between the two",
                        "the CBR's own commentary on which it is reacting to"),
        "impact": "the highest-frequency inflation series in this department, in the country with "
                  "the most inflation-sensitive policy reaction function; it is the best "
                  "nowcasting input available for the key-rate decision",
        "persistence": "the series is long and stable; the RELATIONSHIP between the weekly and "
                       "monthly figures shifts with basket revisions",
        "falsifier": "the weekly print should predict the monthly figure. Where it does not, the "
                     "basket difference is doing the work and the weekly series is not a "
                     "high-frequency version of the monthly one",
        "notes": "treating the weekly and monthly series as one is a common and material error",
    },
    {
        "name": "Turkish and Gulf intermediaries in the re-routed trade",
        "holds": "the payment and logistics channels that replaced direct European ones after "
                 "2022",
        "forced_to": ("intermediate because the direct channel is closed, not because it is "
                      "efficient",
                      "price the friction into the goods and the payment"),
        "when": "continuous; the channel's cost steps with each enforcement action",
        "information": ("their own flow volumes"),
        "constraints": ("secondary sanctions risk, which prices the channel",
                        "correspondent banking access, which can be withdrawn at short notice"),
        "instruments": ("USDTRY", "USDRUB", "XBRUSD"),
        "counterparties": ("Russian exporters and importers",
                           "the ultimate buyers and sellers in third markets"),
        "observables": ("Turkish and Central Asian trade statistics, which show the re-routing",
                        "the Urals discount, which embeds the channel cost",
                        "enforcement announcements and their dates"),
        "impact": "the re-routing is why the Urals discount is a FRICTION price rather than a "
                  "demand price, and it links USDTRY and USDRUB in a way no macro fundamental does",
        "persistence": "the channel has persisted and adapted through several enforcement rounds; "
                       "each round is a step in the cost, not a closure",
        "falsifier": "the Turkish-Russian trade statistics should step with each enforcement "
                     "round. If they do not, the channel is not where the flow is going",
        "notes": "",
    },
    {
        "name": "The offshore CFD market maker quoting USDRUB to this desk",
        "holds": "an offshore rouble book with no access to the domestic market and no ability to "
                 "hedge in it",
        "forced_to": ("quote a price it cannot hedge, and therefore to quote it wide",
                      "freeze the quote when it has no reference at all -- which is what the 30.6% "
                      "frozen-bar measurement is showing"),
        "when": "continuously, and worst outside the Moscow session",
        "information": ("whatever offshore reference it can construct"),
        "constraints": ("no access to the domestic market",
                        "sanctions compliance on its own book",
                        "an inability to lay off risk, which is what sets the spread"),
        "instruments": ("USDRUB",),
        "counterparties": ("this desk, and every other offshore participant"),
        "observables": ("the `spread` column on the desk's own USDRUB tape",
                        "the frozen-bar share, measured at 30.6% over the last sixty days",
                        "the divergence between this quote and the CBR official rate"),
        "impact": "the desk's USDRUB series is this market maker's book, not Russia's currency. "
                  "Every Russian mechanism tested on it is tested through a 164bp spread and a "
                  "third of the bars being stale",
        "persistence": "the degradation began in 2022 and has not reversed; the 2021 tape and the "
                       "2026 tape are different instruments sharing a ticker",
        "falsifier": "measure the same mechanism on USDCNH and on the commodity leg. If it "
                     "survives there and not on USDRUB, the mechanism is real and USDRUB is the "
                     "problem; if it survives ONLY on USDRUB, it is the market maker",
        "notes": "this actor exists so that the tape's own pathology is a modelled object rather "
                 "than an unexamined assumption",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "RU-A", "title": "Key rate decisions in a closed capital account",
        "objects": ("the eight scheduled Friday decisions at 10:30 UTC, all year, no DST",
                    "the 15:00 Moscow press conference",
                    "the off-cycle decisions, which are their own class",
                    "the CBR macro survey as the only reachable consensus"),
        "conditions": ("the surprise built from the CBR survey or a press poll and LABELLED as "
                       "survey-based, because it is a weaker object than a traded curve",
                       "the capital-account regime, which changed completely in 2022",
                       "scheduled and off-cycle decisions kept apart",
                       "the target instrument: USDCNH and the commodity leg first, USDRUB only "
                       "where the expected move clears 164bp"),
        "instruments": ("USDRUB", "USDCNH", "XBRUSD", "USDX"),
        "controls": ("the same window on the eight nearest non-meeting Fridays",
                     "the same window on EURUSD and USDCNH, separating a rouble event from a "
                     "dollar or renminbi event",
                     "the pre-2022 sample, where the capital account was open and the "
                     "transmission channel was portfolio flow rather than deposit carry",
                     "the frozen-bar filter: a decision whose window is mostly frozen bars is "
                     "UNMEASURED, not a null result"),
        "notes": "the fixed UTC+3 clock is a genuine convenience here: unlike every other country "
                 "in this department the event minute never moves",
    },
    {
        "id": "RU-B", "title": "The average-key-rate forecast as a path commitment",
        "objects": ("the average-key-rate forecast range published at the four core meetings",
                    "the revision between reports",
                    "the CBR macro survey's own key-rate path",
                    "the gap between the Bank's forecast and the survey's"),
        "conditions": ("the AVERAGE construction handled correctly: the forecast is for a "
                       "calendar-year average, and the elapsed months are already fixed inside "
                       "it, so a naive end-of-period reading is arithmetically wrong and the "
                       "error grows through the year",
                       "the revision measured at a fixed horizon",
                       "core meetings only; the other four carry no forecast"),
        "instruments": ("USDRUB", "USDCNH", "XBRUSD"),
        "controls": ("the four non-core meetings, which should show nothing",
                     "the decision-day return alone, as the null this domain must beat",
                     "the survey path as an alternative forecast, to separate 'a forecast moved' "
                     "from 'the Bank's forecast moved'",
                     "a placebo revision drawn from the forecast's own revision distribution"),
        "notes": "a commitment about a PATH INTEGRAL rather than a level; no other pack in this "
                 "department has one and the arithmetic is the whole difficulty",
    },
    {
        "id": "RU-C", "title": "The budget rule as an announced sovereign FX order",
        "objects": ("the monthly announcement, in roubles per day, with a direction",
                    "the CBR mirroring amount, which must be ADDED to it",
                    "the operating window from the 7th to the 6th of the next month",
                    "monthly oil-and-gas revenue against the base figure"),
        "conditions": ("the NET sovereign amount -- budget rule plus mirroring; using one alone "
                       "understates it, sometimes by more than the one used",
                       "the announcement and the operating window as two separate events",
                       "the currency, which became the renminbi in 2023",
                       "the three regimes: pre-2022, the 2022 suspension, and the renminbi era"),
        "instruments": ("USDRUB", "USDCNH"),
        "controls": ("months where the net announced amount is near zero",
                     "the same statistic on USDCNH, which is where the operation actually "
                     "transacts and should therefore show it MORE clearly than USDRUB does",
                     "the pre-2017 sample, before the rule existed",
                     "a placebo window shifted by two weeks"),
        "notes": "the cleanest test of the pack: if an announced, sized, dated sovereign order "
                 "leaves no footprint, the desk's ability to measure Russian flow at all is in "
                 "question and that is itself the finding",
    },
    {
        "id": "RU-D", "title": "The tax period and the exporter rouble bid",
        "objects": ("the unified tax payment date, the 28th, since 1 January 2023",
                    "the pre-2023 staggered schedule from the 25th to the 28th",
                    "the mineral extraction tax on oil, due the same day",
                    "the five business days of conversion before the date"),
        "conditions": ("the rule switched at 1 January 2023 -- a study spanning the boundary must "
                       "use two windows, not one",
                       "the size of the liability, proxied by monthly oil-and-gas revenue",
                       "the Urals monthly average, which enters the tax formula and is known "
                       "before the payment date",
                       "holiday transfers, which move the effective last business day"),
        "instruments": ("USDRUB", "USDCNH"),
        "controls": ("the same day-of-month statistic on USDCNH and other EM currencies with no "
                     "such tax date -- an effect present in all of them is month-end, not tax",
                     "the pre-2023 window applied to the post-2023 sample, which should FAIL",
                     "months following low oil-and-gas revenue, where the liability is small",
                     "a placebo tax date on the 14th"),
        "notes": "the most-cited Russian FX seasonal and the one a generic month-end study will "
                 "reproduce for the wrong reason",
    },
    {
        "id": "RU-E", "title": "The mandatory FX surrender decree as a step function",
        "objects": ("the decree of October 2023 and each subsequent amendment",
                    "the named obligated exporter groups",
                    "CBR monthly data on net FX sales by the largest exporters",
                    "the current-account surplus, which bounds the flow"),
        "conditions": ("each amendment treated as a STRUCTURAL BREAK, not as a continuous "
                       "variable",
                       "the current account as the upper bound on what can be surrendered",
                       "payment-channel friction, which can delay repatriation even when it is "
                       "legally required"),
        "instruments": ("USDRUB", "USDCNH"),
        "controls": ("the months before October 2023, when no requirement was in force",
                     "CBR's published exporter net-sales series as the actor's own ledger",
                     "the same statistic on USDCNH",
                     "a placebo decree date"),
        "notes": "a flow that exists because a decree says so; it steps when the decree steps and "
                 "not when the price does, which is the opposite of a price-response mechanism",
    },
    {
        "id": "RU-F", "title": "The Urals discount, not the Brent price",
        "objects": ("the Urals-Brent discount as assessed",
                    "the ESPO discount, which differs and moves separately",
                    "the Minfin monthly Urals reference price used in the tax formula",
                    "the price cap dates: crude 5 December 2022, products 5 February 2023"),
        "conditions": ("the discount entered SEPARATELY from Brent -- the whole domain is that "
                       "they are two variables",
                       "the MONTHLY AVERAGE reference for the fiscal channel and the spot price "
                       "for the market channel; they are different transmissions",
                       "the enforcement regime, which steps the discount"),
        "instruments": ("XBRUSD", "XTIUSD", "USDRUB", "USDCNH"),
        "controls": ("Brent alone, as the null: if the discount term is not separately "
                     "significant the mechanism is Brent and this domain adds nothing",
                     "the same regression on USDCAD or USDNOK, energy exporters with no discount",
                     "the pre-2022 sample, when the discount was small and stable",
                     "the spot-anchored version run against the monthly-average version, to show "
                     "which transmission is being measured"),
        "notes": "treating XBRUSD as the Russian export price is the single largest modelling "
                 "error available in this pack, and this domain exists to make it impossible",
    },
    {
        "id": "RU-G", "title": "Three rouble prices and the basis between them",
        "objects": ("the CBR official rate, effective the NEXT calendar day",
                    "the domestic OTC rate, which the official rate is now derived from",
                    "the offshore CFD quote this desk actually holds",
                    "the June 2024 methodology break"),
        "conditions": ("the NEXT-DAY effective date applied correctly; using the official rate on "
                       "its publication day is using tomorrow's number today",
                       "the pre- and post-June-2024 official series treated as two constructions "
                       "sharing a name",
                       "the offshore quote treated as a separate instrument with its own basis"),
        "instruments": ("USDRUB", "USDCNH"),
        "controls": ("USDCNH, which is an offshore quote of a currency whose onshore twin the "
                     "desk also cannot see -- the same structural situation without the sanctions",
                     "the pre-2022 sample, when the three prices were one price",
                     "the frozen-bar filter",
                     "a synthetic offshore rate reconstructed from USDCNH and a CNY/RUB proxy"),
        "notes": "the basis IS the object here. There is no single 'USDRUB' and a study that "
                 "assumes one is measuring the gap between two of them without knowing it",
    },
    {
        "id": "RU-H", "title": "Concentrated metal supply: palladium, nickel, aluminium",
        "objects": ("palladium supply concentration of roughly 40% in one producer",
                    "high-grade nickel and the Arctic logistics window",
                    "aluminium and its own sanctions history",
                    "exchange inventory levels and the palladium-platinum spread"),
        "conditions": ("single-site events treated as global supply events, which they are",
                       "the demand trend, because palladium demand erodes with vehicle "
                       "electrification and the same shock has a smaller price effect each year",
                       "the substitution spread to platinum, which caps the palladium response"),
        "instruments": ("XPDUSD", "XPTUSD", "XNIUSD", "XALUSD", "XCUUSD"),
        "controls": ("XCUUSD, a metal with no comparable concentration -- a shared response is a "
                     "risk or dollar move",
                     "the platinum leg, which prices substitutability directly",
                     "the pre-2022 sample, when the logistics channel was different",
                     "a placebo event list drawn from routine corporate announcements"),
        "notes": "this is the domain where Russian mechanisms are MOST tradeable on this box, "
                 "because the instruments are liquid and the rouble is not involved at all",
    },
    {
        "id": "RU-I", "title": "Wheat: an administrative supply shock on the largest exporter",
        "objects": ("the weekly floating export duty and its indicative price",
                    "the ANNOUNCEMENT date and the EFFECTIVE date, several days apart",
                    "the second-half-season export quota",
                    "Black Sea and Azov logistics"),
        "conditions": ("the announcement-to-effective gap treated as the tradeable object, not "
                       "the duty level",
                       "each formula amendment treated as a break",
                       "the quota's binding date, which is when it matters and not when it is set",
                       "navigation and freight risk, which is a separate supply constraint"),
        "instruments": ("WHEAT", "CORN"),
        "controls": ("CORN, where the Russian export share is far smaller",
                     "the pre-June-2021 sample, before the duty mechanism existed",
                     "the northern-hemisphere harvest seasonal, which must be removed",
                     "weeks where the duty is unchanged"),
        "notes": "an announcement with a KNOWN future effective date is rare; most policy shocks "
                 "are effective on announcement and this one is not",
    },
    {
        "id": "RU-J", "title": "Gas flows into European industrial margin",
        "objects": ("daily pipeline flows published by the receiving operators",
                    "European storage fill trajectory",
                    "transit contract expiry dates, known years ahead",
                    "the LNG substitution margin"),
        "conditions": ("the desk's gas quote is HENRY HUB, not the European benchmark -- every "
                       "cell using XNGUSD as a European proxy must say so",
                       "the equity channel measured directly on GER40 and EUSTX50, which the desk "
                       "CAN see, rather than through a gas price it cannot",
                       "the post-2022 regime, in which the channel is far smaller"),
        "instruments": ("XNGUSD", "GER40", "EUSTX50", "XBRUSD"),
        "controls": ("XTIUSD: a European equity response present for oil too is an energy-complex "
                     "move and not a gas-supply event",
                     "US500, which has no comparable European gas exposure",
                     "the 2021 sample, where the beta was much larger, as an explicit regime "
                     "comparison",
                     "storage-fill-matched days"),
        "notes": "the honest form of this domain is an EQUITY domain: the desk can measure "
                 "European industrial margin far better than it can measure European gas",
    },
    {
        "id": "RU-K", "title": "OFZ supply and the domestic rates channel",
        "objects": ("the Wednesday OFZ auction calendar",
                    "auction coverage and the yield tail",
                    "the RGBI index",
                    "the key rate's transmission into the curve"),
        "conditions": ("this is a TRANSMISSION-TARGET domain: none of these series is on this box",
                       "the key rate as the only observable leg the desk can see",
                       "the offshore USDRUB basis as an indirect read on domestic conditions"),
        "instruments": ("USDRUB", "UST10Y"),
        "controls": ("the same statistic on days with no auction",
                     "UST10Y, to remove the global duration factor",
                     "the pre-2022 sample, when foreign participation in OFZ auctions was large "
                     "and the channel ran through portfolio flow"),
        "notes": "included and declared UNMEASURED rather than omitted: a domain the desk cannot "
                 "reach is a named gap, and L1.49 says a gate that never ran is a claim the desk "
                 "cannot cash",
    },
    {
        "id": "RU-L", "title": "IMOEX, RTS and the index ratio as a currency observable",
        "objects": ("IMOEX, denominated in roubles",
                    "RTS, the same book in dollars",
                    "the RATIO of the two, which is an exchange rate",
                    "the concentrated summer dividend season"),
        "conditions": ("neither index is on this box: this is a transmission-target domain",
                       "the ratio construction, which gives a currency series with no FX quote at "
                       "all -- a genuinely useful idea that the desk cannot currently execute",
                       "the dividend season, which is concentrated and large relative to the "
                       "index"),
        "instruments": ("USDRUB", "EUSTX50", "XBRUSD"),
        "controls": ("the offshore USDRUB quote against any reconstructed ratio",
                     "EUSTX50, as an unrelated equity control",
                     "the pre-2022 sample, when both indices were freely accessible"),
        "notes": "the IMOEX/RTS ratio is the most elegant unavailable observable in this pack and "
                 "is recorded here so that a later session with data access knows to use it",
    },
    {
        "id": "RU-M", "title": "The tape's own pathology: spread, frozen bars and the cost floor",
        "objects": ("the USDRUB median H1 spread: 137,509 points over the last sixty days against "
                    "453 points in 2021",
                    "the frozen-bar share: 30.6% of recent hourly bars have open = high = low = "
                    "close",
                    "the EURRUB tape, which stops at 2022-02-28",
                    "the swap table: -4,008.64 long against +589.48 short per lot per day"),
        "conditions": ("EVERY OTHER DOMAIN IN THIS PACK IS CONDITIONED ON THIS ONE. A USDRUB cell "
                       "must clear a ~164bp cost floor and must exclude frozen bars, or it is "
                       "measuring the broker",
                       "the swap asymmetry: holding the depreciation trade costs roughly 7x what "
                       "the carry trade pays, so direction-dependent cost is mandatory",
                       "horizons long enough that a frozen bar cannot decide the result"),
        "instruments": ("USDRUB", "USDCNH", "XBRUSD"),
        "controls": ("the same mechanism measured on USDCNH and the commodity leg: if it survives "
                     "there and not on USDRUB the mechanism is real and the tape is the problem; "
                     "if it survives ONLY on USDRUB it is the market maker",
                     "the 2021 sub-sample, where the spread was 6bp, as the 'what this would look "
                     "like on a working tape' comparison",
                     "a frozen-bar-only sample, which should show nothing at all and which will "
                     "show mean reversion if the estimator is broken",
                     "cost-gross versus cost-net Sharpe reported side by side, always"),
        "notes": "this domain is not a caveat section. It is a research object: the degradation "
                 "of a quote under sanctions is itself measurable, dated and interesting, and it "
                 "is the reason the rest of the pack aims at the commodity leg",
    },
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ru_key_rate_event_study", "domain_ids": ("RU-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ru.miners:key_rate_event_study",
     "needs": ("CBR decision dates", "the CBR macro survey", "USDRUB and USDCNH M15 bars"),
     "notes": "labels every surprise as SURVEY-BASED; excludes frozen bars and reports UNMEASURED "
              "for any window that is mostly frozen"},
    {"name": "ru_avg_rate_forecast_revision", "domain_ids": ("RU-B",), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:avg_rate_forecast_revision",
     "needs": ("every Monetary Policy Report vintage", "USDRUB and XBRUSD H1 bars"),
     "notes": "handles the calendar-year AVERAGE construction explicitly; a naive end-of-period "
              "reading is refused"},
    {"name": "ru_budget_rule_flow", "domain_ids": ("RU-C",), "kind": "flow",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:budget_rule_flow",
     "needs": ("Minfin monthly announcements", "CBR mirroring announcements",
               "USDRUB and USDCNH H1 bars"),
     "notes": "sums the budget rule and the mirroring into a NET sovereign amount; measures on "
              "USDCNH first because that is where the operation transacts"},
    {"name": "ru_tax_period_seasonal", "domain_ids": ("RU-D",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ru.miners:tax_period_seasonal",
     "needs": ("the tax calendar with the 2023 rule switch", "USDRUB and USDCNH H1 bars"),
     "notes": "switches window at 2023-01-01; runs the EM month-end control before reporting"},
    {"name": "ru_surrender_decree_steps", "domain_ids": ("RU-E",), "kind": "policy",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:surrender_decree_steps",
     "needs": ("decree dates and amendments", "CBR exporter net-sales series", "USDRUB H1 bars"),
     "notes": "treats each amendment as a break; a continuous-variable fit is refused"},
    {"name": "ru_urals_discount_decomposition", "domain_ids": ("RU-F",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:urals_discount_decomposition",
     "needs": ("an assessed Urals-Brent discount series", "Minfin monthly reference price",
               "XBRUSD D1 bars"),
     "notes": "enters Brent and the discount separately and reports the Brent-only null first"},
    {"name": "ru_three_prices_basis", "domain_ids": ("RU-G",), "kind": "basis",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:three_prices_basis",
     "needs": ("CBR official rate with its next-day effective date", "USDRUB H1 bars"),
     "notes": "applies the next-day effective date; splits the series at the June 2024 "
              "methodology change and refuses to pool across it"},
    {"name": "ru_metal_supply_concentration", "domain_ids": ("RU-H",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:metal_supply_concentration",
     "needs": ("XPDUSD, XPTUSD, XNIUSD, XALUSD, XCUUSD D1 bars", "a producer event list"),
     "notes": "the copper control is reported first; the palladium demand trend is conditioned on"},
    {"name": "ru_wheat_duty_gap", "domain_ids": ("RU-I",), "kind": "policy",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:wheat_duty_gap",
     "needs": ("weekly duty announcements with announcement and effective dates",
               "WHEAT and CORN D1 bars"),
     "notes": "the announcement-to-effective gap is the object; the duty level is the control"},
    {"name": "ru_gas_to_european_margin", "domain_ids": ("RU-J",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ru.miners:gas_to_european_margin",
     "needs": ("published pipeline flow series", "GER40, EUSTX50, XNGUSD D1 bars"),
     "notes": "states the Henry-Hub-versus-European-benchmark mismatch in every result; measures "
              "the equity leg directly because the desk can actually see it"},
    {"name": "ru_tape_pathology", "domain_ids": ("RU-M",), "kind": "microstructure",
     "cadence_s": 3600.0, "steerable": False, "wired": False,
     "entry": "countries.ru.miners:tape_pathology",
     "needs": ("USDRUB H1 bars with the spread column", "EURRUB H1 bars"),
     "notes": "publishes the frozen-bar share, the spread regime and the direction-dependent cost "
              "floor that every other Russian miner must clear; runs FIRST and gates the rest"},
)

# --------------------------------------------------------------------------- transmission edges
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "XBRUSD", "target": "USDRUB", "sign": "-",
     "mechanism": "oil-and-gas revenue is the largest single source of export receipts and of "
                  "federal revenue; a higher crude price means more foreign currency sold into a "
                  "market with a closed capital account",
     "horizon": "5 to 60 sessions",
     "condition": "the Urals DISCOUNT must be entered separately; Brent alone is the wrong "
                  "variable and the discount has ranged from about $2 to more than $30",
     "control": "USDCAD and USDNOK, energy exporters with no discount and an open capital account",
     "falsifier": "an oil beta in USDRUB no larger than in a non-exporter, which would mean the "
                  "channel is risk appetite and not export receipts"},
    {"source": "USDRUB", "target": "XAUUSD", "sign": "+",
     "mechanism": "rouble depreciation and a closed external channel push domestic savings into "
                  "gold, and the central bank's own reserve composition shifted sharply toward it "
                  "after 2022 -- two demand sources that arrive together",
     "horizon": "20 to 120 sessions",
     "condition": "the post-2022 regime only; before that the external channel was open and this "
                  "substitution did not exist at scale",
     "control": "the same statistic on USDTRY, another currency whose households buy gold under "
                "depreciation",
     "falsifier": "a gold response of the same size in the pre-2022 sample"},
    {"source": "Russian tax period (the 28th, unified tax payment)", "target": "USDRUB",
     "sign": "-",
     "mechanism": "exporters must convert foreign currency to roubles to pay a legal obligation "
                  "with a fixed date; the rouble bid is mechanical and builds over the preceding "
                  "five business days",
     "horizon": "the five business days before the 28th",
     "condition": "the post-2023 unified date; before 2023 the window was the 25th to the 28th "
                  "and a single window applied to both samples is wrong",
     "control": "the same day-of-month statistic on USDCNH and other EM currencies",
     "falsifier": "an equal day-of-month effect in currencies with no such tax date, which makes "
                  "it month-end rather than tax"},
    {"source": "Minfin budget-rule announcement plus CBR mirroring (net sovereign amount)",
     "target": "USDCNH", "sign": "two_sided",
     "mechanism": "the operation transacts in renminbi since 2023, so the renminbi pair is where "
                  "the sovereign order actually lands; the direction is the announced direction",
     "horizon": "the operating window, the 7th to the 6th",
     "condition": "the NET amount -- budget rule plus mirroring -- never one alone",
     "control": "months where the net amount is near zero",
     "falsifier": "no footprint in USDCNH from an announced, sized, dated order, which would mean "
                  "the order is too small relative to the offshore market to be visible"},
    {"source": "CBR key rate surprise against the macro survey", "target": "USDRUB", "sign": "-",
     "mechanism": "in a closed capital account the rate works through domestic deposit carry and "
                  "import demand rather than through portfolio flow; a hawkish surprise raises "
                  "the return on holding roubles",
     "horizon": "0 to 5 sessions",
     "condition": "survey-based surprise, labelled as such; and the window must clear the frozen-"
                  "bar filter or be reported UNMEASURED",
     "control": "the eight nearest non-meeting Fridays, and the same window on USDCNH",
     "falsifier": "an equal move on non-meeting Fridays, or a result driven by frozen bars"},
    {"source": "Nornickel palladium supply event", "target": "XPDUSD", "sign": "+",
     "mechanism": "roughly 40% of world supply from a small number of Arctic sites with one "
                  "logistics corridor; a single-site event is a global supply event",
     "horizon": "1 to 30 sessions",
     "condition": "conditioned on the palladium-platinum substitution spread, which caps the "
                  "response, and on the eroding demand trend",
     "control": "XCUUSD, a metal with no comparable concentration",
     "falsifier": "an equal copper response, which would make it a risk or dollar move"},
    {"source": "Russian wheat export duty announcement", "target": "WHEAT", "sign": "+",
     "mechanism": "an administrative supply restriction on the world's largest exporter; the duty "
                  "is announced with an EFFECTIVE date several days later, so there is a known "
                  "window between the news and the constraint",
     "horizon": "the announcement-to-effective gap, typically 3 to 7 sessions",
     "condition": "the gap is the object, not the duty level; each formula amendment is a break",
     "control": "CORN, where the Russian export share is far smaller",
     "falsifier": "an equal corn response, which would make it a grain-complex move"},
    {"source": "Gazprom pipeline flows to Europe", "target": "GER40", "sign": "+",
     "mechanism": "European gas cost drives European industrial margin; the equity leg is what "
                  "this desk can actually measure, because its gas quote is a US benchmark",
     "horizon": "1 to 20 sessions",
     "condition": "the Henry-Hub mismatch stated explicitly; the post-2022 regime, in which the "
                  "channel is far smaller than in 2021",
     "control": "US500, which has no comparable European gas exposure; and XTIUSD",
     "falsifier": "an equal US500 response, which would make it a global risk move"},
    {"source": "USDRUB", "target": "USDTRY", "sign": "+",
     "mechanism": "Turkey is a principal re-routing corridor for Russian trade, tourism and "
                  "payments; the two currencies are linked by a FRICTION channel rather than by "
                  "any macro fundamental, which is why the correlation appears and disappears "
                  "with enforcement rounds",
     "horizon": "5 to 60 sessions",
     "condition": "conditioned on enforcement events; outside them the link is weak",
     "control": "USDZAR and USDMXN, EM currencies with no such corridor",
     "falsifier": "a stable correlation independent of enforcement, which would make it generic "
                  "EM beta"},
    {"source": "Russian crude export volumes and the price cap regime", "target": "XBRUSD",
     "sign": "-",
     "mechanism": "the cap and its enforcement re-route rather than remove barrels; the global "
                  "price responds to whether the barrels arrive, and the discount absorbs the "
                  "friction",
     "horizon": "5 to 60 sessions",
     "condition": "cap dates 2022-12-05 for crude and 2023-02-05 for products are structural "
                  "breaks, not continuous variables",
     "control": "XTIUSD, which shares the global price but not the Russian supply detail",
     "falsifier": "a Brent response with no corresponding move in the discount, which would mean "
                  "the barrels were genuinely removed rather than re-routed"},
    {"source": "USDCNH", "target": "USDRUB", "sign": "+",
     "mechanism": "the renminbi is now the budget rule's operating currency and the main "
                  "exchange-traded FX pair in Russia, so the renminbi cross is the arithmetic "
                  "hinge between the rouble and the dollar",
     "horizon": "1 to 20 sessions",
     "condition": "the post-June-2024 regime, after exchange trading in dollars stopped",
     "control": "the pre-2022 sample, when the renminbi was not the hinge",
     "falsifier": "no strengthening of the relationship after June 2024, which would falsify the "
                  "hinge story"},
    {"source": "Russian household deposit growth under a high key rate", "target": "USDRUB",
     "sign": "-",
     "mechanism": "a high key rate converts household savings into rouble deposits and away from "
                  "currency substitution; in a closed capital account this is the main channel by "
                  "which the rate supports the currency",
     "horizon": "20 to 120 sessions",
     "condition": "the post-2022 closed-account regime; the elasticity is not comparable before it",
     "control": "the same statistic in low-key-rate periods",
     "falsifier": "identical deposit growth at low rates, which would mean the rate is not the "
                  "mechanism"},
    {"source": "CBR reserve accumulation in gold", "target": "XAUUSD", "sign": "+",
     "mechanism": "domestic gold production that can no longer be exported freely is bought for "
                  "reserves; the composition shift toward gold is published and is large relative "
                  "to annual mine supply",
     "horizon": "60 to 250 sessions",
     "condition": "the post-2022 regime; conditioned on total reserve growth so a composition "
                  "shift is not read as new demand",
     "control": "XAGUSD, where no comparable official demand exists",
     "falsifier": "an equal silver response, which would make it a precious-complex move"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "inflation targeting and the float", "start": "2014-11-10", "end": "2020-02-29",
     "regime": "a free float adopted in November 2014, a 4% inflation target from 2015, the "
               "budget rule from 2017, and an open capital account throughout",
     "markers": ("2014-11-10 the float", "2014-12-16 the overnight move to 17%",
                 "2017-02 the budget rule begins"),
     "why_it_matters": "the ONLY era in which the rouble behaved like an ordinary floating EM "
                       "currency with an open capital account; every textbook relationship that "
                       "works in this pack works here and only here",
     "status": "SETTLED"},
    {"name": "pandemic and the oil-price collapse", "start": "2020-03-01", "end": "2022-02-23",
     "regime": "rates cut to 4.25% and then raised through 2021 as inflation returned; the budget "
               "rule operating normally",
     "markers": ("2020-04 the OPEC+ collapse and recovery", "2021-03 the tightening cycle begins"),
     "why_it_matters": "the last normal period; the desk's USDRUB tape begins in September 2020, "
                       "so this era is most of the pre-break sample it holds",
     "status": "SETTLED"},
    {"name": "the February 2022 break and capital controls", "start": "2022-02-24",
     "end": "2022-06-30",
     "regime": "the key rate to 20%, an 80% mandatory export-revenue surrender, exchange closure, "
               "type-C accounts and a suspended budget rule",
     "markers": ("2022-02-28 the key rate to 20%", "2022-03 type-C accounts",
                 "2022-02-28 the EURRUB tape on this box STOPS"),
     "why_it_matters": "EVERY series in this pack breaks here. The desk's EURRUB tape ends on the "
                       "last day of this window's first week and never resumes; USDRUB's spread "
                       "begins the widening that reaches 300x. Nothing may be pooled across it",
     "status": "SETTLED"},
    {"name": "the closed-account surplus and the reversal", "start": "2022-07-01",
     "end": "2023-09-30",
     "regime": "rates back to 7.5% as a huge current-account surplus met a closed capital "
               "account; the budget rule resumed in renminbi in January 2023; the unified tax "
               "payment date arrived on 1 January 2023",
     "markers": ("2023-01-01 the unified tax payment date replaces the staggered schedule",
                 "2023-01 the budget rule resumes, in renminbi"),
     "why_it_matters": "two of this pack's three flow mechanisms changed shape here: the tax "
                       "window moved and the budget rule changed currency. RU-C and RU-D both "
                       "switch rules at these dates",
     "status": "SETTLED"},
    {"name": "surrender decrees and the tightening cycle", "start": "2023-10-01",
     "end": "2024-06-11",
     "regime": "mandatory FX surrender by named exporter groups from October 2023, and a key rate "
               "raised aggressively against domestic inflation",
     "markers": ("2023-10-11 the surrender decree", "the key rate above 16%"),
     "why_it_matters": "the surrender decree is a step function and each amendment is a break; "
                       "RU-E is built on this era's boundaries",
     "status": "SETTLED"},
    {"name": "after the exchange designation", "start": "2024-06-12", "end": "2099-12-31",
     "regime": "exchange trading in dollars and euros halted; the official rate computed from "
               "bank OTC reporting; CNY/RUB the main exchange-traded pair; the offshore quote "
               "this desk holds increasingly detached",
     "markers": ("2024-06-12 the exchange and clearing house designated",
                 "the official rate methodology changes",
                 "USDRUB median spread on this box reaching 137,509 points and 30.6% frozen bars"),
     "why_it_matters": "UNVERIFIED TAIL for anything after mid-2025, and the era in which the "
                       "desk's own tape stops being a market. Every RU-M measurement belongs "
                       "here, and any claim about 2025-2026 Russian policy must be re-read from "
                       "cbr.ru before a study conditions on it",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "EURRUB has no tape after 2022-02-28",
     "measured": "EURRUB_H1.parquet: 15,199 H1 bars, 2017-10-31 to 2022-02-28, nothing after. "
                 "universe.json carries spread_pts_at_collection = 1,397,460 (about 14 roubles)",
     "consequence": "EURRUB is a TRANSMISSION TARGET in this pack and is deliberately excluded "
                    "from executable_instruments. No cell may be compiled against it, and a "
                    "backtest that appears to run on it is running on a pre-2022 world"},
    {"constraint": "USDRUB is quoted but is roughly 300x more expensive than it was",
     "measured": "USDRUB_H1.parquet to 2026-09-16. Median H1 spread over the last 60 days: "
                 "137,509 points = 1.375 roubles = about 164bp on a rate of 84.03. Median H1 "
                 "spread through 2021: 453 points, about 6bp. universe.json: median 21,060, "
                 "collection-time 180,546",
     "consequence": "every USDRUB cell must clear a ~164bp cost floor. Intraday mechanisms are "
                    "arithmetically out of reach and must be declared so rather than tested and "
                    "reported as null"},
    {"constraint": "30.6% of recent USDRUB hourly bars are FROZEN",
     "measured": "over the last 60 days of the tape, 30.57% of H1 bars have open = high = low = "
                 "close",
     "consequence": "a third of the recent tape is a stale quote. Any estimator run without a "
                    "frozen-bar filter will find mean reversion that is the broker's quote "
                    "repeating, not the market returning. RU-M gates every other Russian miner"},
    {"constraint": "the USDRUB swap table is strongly asymmetric",
     "measured": "universe.json: swap_long -4,008.64, swap_short +589.48 points per lot per day",
     "consequence": "holding the depreciation trade costs roughly seven times what the carry "
                    "trade pays. Cost must be direction-dependent in every Russian cell, and a "
                    "symmetric cost assumption flatters the long-USDRUB side enormously"},
    {"constraint": "no Russian venue access, no broker relationship, no market-data licence",
     "measured": "MOEX, SPIMEX, IMOEX, RTS, OFZ, RGBI and CNY/RUB are absent from the universe "
                 "registry and the desk holds no licence for any of them",
     "consequence": "every domestic observable in this pack is a transmission target and is "
                    "declared UNMEASURED. RU-K and RU-L exist as NAMED GAPS rather than being "
                    "omitted, because an unmeasured domain is a verdict and an absent one is not"},
    {"constraint": "rouble positioning ends in 2022",
     "measured": "CME Russian rouble futures (6R) were suspended and delisted in 2022; the COT "
                 "series stops there and has no successor",
     "consequence": "rouble positioning is UNMEASURED from 2022 onward. It may not be "
                    "back-filled, extrapolated, or proxied by another currency's COT, and "
                    "cot_currency on this pack is deliberately empty"},
    {"constraint": "Russian customs publication was suspended and is only partially resumed",
     "measured": "customs.gov.ru suspended detailed trade publication for extended periods after "
                 "2022",
     "consequence": "an absent month is UNMEASURED, never zero. The publication GAP is itself "
                    "information about the disclosure regime and must not be interpolated"},
    {"constraint": "sources are public and primary only; nothing is scraped from a venue",
     "measured": "SOURCE_CLASSES lists cbr.ru, minfin.gov.ru, rosstat.gov.ru, customs.gov.ru, the "
                 "Russian academic web and the practitioner community web, each with its lane",
     "consequence": "the community sources (smart-lab, banki.ru forums, habr, public Telegram "
                    "channels, Russian-language repositories) are HYPOTHESIS SEEDS ONLY: they may "
                    "mint a mechanism claim and may never evidence one"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, carrying the access constraints and transmission targets
    alongside the frozen fields so nothing is silently dropped."""
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
